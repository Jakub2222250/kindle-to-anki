import json
import time
from typing import List, Tuple, Dict, Any

from kindle_to_anki.core.pricing.usage_dimension import UsageDimension
from kindle_to_anki.core.pricing.usage_scope import UsageScope
from kindle_to_anki.core.pricing.usage_breakdown import UsageBreakdown
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.core.pricing.token_estimator import count_tokens
from kindle_to_anki.core.pricing.realtime_cost_reporter import RealtimeCostReporter

from kindle_to_anki.platforms.platform_registry import PlatformRegistry
from kindle_to_anki.platforms.chat_completion_platform import ChatCompletionPlatform
from .schema import WSDInput, WSDOutput
from kindle_to_anki.language.language_helper import get_language_name_in_english
from kindle_to_anki.caching.wsd_cache import WSDCache


class ChatCompletionWSD:
    """
    Runtime for Word Sense Disambiguation using chat-completion LLMs.
    Supports multiple platforms and models.
    """

    id: str = "chat_completion_wsd"
    display_name: str = "Chat Completion WSD Runtime"
    supported_tasks = ["wsd"]
    supported_model_families = ["chat_completion"]
    supports_batching: bool = True

    def _estimate_output_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 50

    def _estimate_input_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 40

    def _build_prompt(self, items_json: str, source_language_name: str, target_language_name: str) -> str:
        return f"""Process the following {source_language_name} words and sentences. For each item, provide analysis in the specified format.

Items to process:
{items_json}

For each item, {self._get_wsd_llm_instructions(source_language_name, target_language_name)}

Respond with valid JSON as an object where keys are the UIDs and values are the analysis objects. No additional text."""

    def estimate_usage(self, items_count: int, config: RuntimeConfig) -> UsageBreakdown:
        model = ModelRegistry.get(config.model_id)
        source_language_name = get_language_name_in_english(config.source_language_code)
        target_language_name = get_language_name_in_english(config.target_language_code)
        static_prompt = self._build_prompt("placeholder", source_language_name, target_language_name)
        instruction_tokens = count_tokens(static_prompt, model)
        
        input_tokens_per_item = self._estimate_input_tokens_per_item(config)
        output_tokens_per_item = self._estimate_output_tokens_per_item(config)
        
        batch_size = config.batch_size
        assert batch_size is not None, "Batch size must be specified in RuntimeConfig"

        num_of_batches = (items_count + batch_size - 1) // batch_size

        estimated_input_tokens = (num_of_batches * instruction_tokens) + (input_tokens_per_item * items_count)
        estimated_output_tokens = output_tokens_per_item * items_count

        usage_breakdown = UsageBreakdown(
            scope=UsageScope(unit="notes", count=items_count),
            inputs={"tokens": UsageDimension(unit="tokens", quantity=estimated_input_tokens)},
            outputs={"tokens": UsageDimension(unit="tokens", quantity=estimated_output_tokens)},
            confidence="medium",
        )
        return usage_breakdown

    def disambiguate(self, wsd_inputs: List[WSDInput], runtime_config: RuntimeConfig, ignore_cache: bool = False, use_test_cache: bool = False) -> List[WSDOutput]:
        """
        Perform Word Sense Disambiguation on a list of WSDInput objects and return WSDOutput objects.
        """
        if not wsd_inputs:
            return []
        
        source_lang = runtime_config.source_language_code
        target_lang = runtime_config.target_language_code

        print("\nStarting Word Sense Disambiguation via LLM process...")

        # Get language names from the inputs
        source_language_name = get_language_name_in_english(source_lang)
        target_language_name = get_language_name_in_english(target_lang)

        # Setup cache
        language_pair_code = f"{source_lang}-{target_lang}"
        cache_suffix = language_pair_code + "_llm"
        if use_test_cache:
            cache_suffix += "_test"

        cache = WSDCache(cache_suffix=cache_suffix)

        # Filter inputs that need WSD and collect cached results
        inputs_needing_wsd = []
        outputs = []

        if not ignore_cache:
            cached_count = 0

            for wsd_input in wsd_inputs:
                cached_result = cache.get(wsd_input.uid)
                if cached_result:
                    cached_count += 1
                    wsd_output = WSDOutput(
                        definition=cached_result.get('definition', ''),
                        original_language_definition=cached_result.get('original_language_definition', ''),
                        cloze_deletion_score=cached_result.get('cloze_deletion_score', 0)
                    )
                    outputs.append(wsd_output)
                else:
                    inputs_needing_wsd.append(wsd_input)
                    outputs.append(None)  # Placeholder

            print(f"Found {cached_count} cached results, {len(inputs_needing_wsd)} inputs need LLM calls")
        else:
            inputs_needing_wsd = wsd_inputs
            outputs = [None] * len(wsd_inputs)
            print("Ignoring cache as per user request. Fresh results will be generated.")

        if not inputs_needing_wsd:
            print(f"{source_language_name} Word Sense Disambiguation (LLM) completed (all from cache).")
            return [output for output in outputs if output is not None]
        
        # Process inputs in batches with retry logic
        MAX_RETRIES = 1
        retries = 0
        failing_inputs = self._process_wsd_batches(inputs_needing_wsd, cache, source_language_name, target_language_name, runtime_config)

        while len(failing_inputs) > 0:
            print(f"{len(failing_inputs)} inputs failed LLM Word Sense Disambiguation.")
            
            if retries >= MAX_RETRIES:
                print("All successful WSD results already saved to cache. Running script again usually fixes the issue. Exiting.")
                raise RuntimeError("WSD failed after retries")
            
            if retries < MAX_RETRIES:
                retries += 1
                print(f"Retrying {len(failing_inputs)} failed inputs (attempt {retries} of {MAX_RETRIES})...")
                failing_inputs = self._process_wsd_batches(failing_inputs, cache, source_language_name, target_language_name, runtime_config)

        # Fill in the WSD results
        wsd_outputs = []
        for i, output in enumerate(outputs):
            if output is None:
                # This was a non-cached input, get from cache now
                wsd_input = wsd_inputs[i]
                cached_result = cache.get(wsd_input.uid)
                if cached_result:
                    wsd_output = WSDOutput(
                        definition=cached_result.get('definition', ''),
                        original_language_definition=cached_result.get('original_language_definition', ''),
                        cloze_deletion_score=cached_result.get('cloze_deletion_score', 0)
                    )
                    wsd_outputs.append(wsd_output)
                else:
                    # This shouldn't happen if everything worked correctly
                    wsd_outputs.append(WSDOutput(definition="", original_language_definition="", cloze_deletion_score=0))
            else:
                wsd_outputs.append(output)

        print(f"{source_language_name} Word Sense Disambiguation (LLM) completed.")
        return wsd_outputs

    def _get_wsd_llm_instructions(self, source_language_name: str, target_language_name: str) -> str:
        return f"""output JSON with:
1. definition: {target_language_name} definition of the lemma form (not the inflected input word), with the meaning determined by how the input word is used in the input sentence. Consider the part of speech when providing a concise dictionary-style gloss for the base form.
2. original_language_definition: {source_language_name} definition of the lemma form (not the inflected input word), with the meaning determined by how the input word is used in the input sentence. Consider the part of speech when providing a concise dictionary-style gloss for the base form.
3. cloze_deletion_score: Provide a score from 0 to 10 indicating how suitable the input sentence is for cloze deletion in Anki based on it and the input word where 0 means not suitable at all, 10 means very suitable"""

    def _make_batch_wsd_call(self, batch_inputs: List[WSDInput], processing_timestamp: str, source_language_name: str, target_language_name: str, runtime_config: RuntimeConfig) -> Tuple[Dict[str, Any], str, str]:
        """Make batch LLM API call for WSD"""
        items_list = []
        for input_item in batch_inputs:
            items_list.append(f'{{"uid": "{input_item.uid}", "word": "{input_item.word}", "lemma": "{input_item.lemma}", "pos": "{input_item.pos}", "sentence": "{input_item.sentence}"}}')

        items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

        prompt = self._build_prompt(items_json, source_language_name, target_language_name)

        # Get the model and platform
        model = ModelRegistry.get(runtime_config.model_id)
        platform = PlatformRegistry.get(model.platform_id)

        input_chars = len(prompt)
        input_tokens = count_tokens(prompt, model)
        estimated_output_tokens = len(batch_inputs) * self._estimate_output_tokens_per_item(runtime_config)

        cost_reporter = RealtimeCostReporter(model)
        estimated_cost_str = cost_reporter.estimate_cost(input_tokens, estimated_output_tokens, len(batch_inputs))

        print(f"  Making batch WSD API call for {len(batch_inputs)} inputs (in: {input_chars} chars / {input_tokens} tokens, out: ~{estimated_output_tokens} tokens, estimated cost: {estimated_cost_str})...")

        start_time = time.time()

        response_text = platform.call_api(runtime_config.model_id, prompt)

        elapsed = time.time() - start_time
        output_chars = len(response_text)
        output_tokens = count_tokens(response_text, model)

        actual_cost_str = cost_reporter.actual_cost(input_tokens, output_tokens, len(batch_inputs))
        print(f"  Batch WSD API call completed in {elapsed:.2f}s (in: {input_chars} chars / {input_tokens} tokens, out: {output_chars} chars / {output_tokens} tokens, actual cost: {actual_cost_str})")

        return json.loads(response_text), runtime_config.model_id, processing_timestamp

    def _process_wsd_batches(self, inputs_needing_wsd: List[WSDInput], cache: WSDCache, source_language_name: str, target_language_name: str, runtime_config: RuntimeConfig) -> List[WSDInput]:
        """Process inputs in batches for WSD"""

        # Capture timestamp at the start of WSD processing
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        total_batches = (len(inputs_needing_wsd) + runtime_config.batch_size - 1) // runtime_config.batch_size
        failing_inputs = []

        for i in range(0, len(inputs_needing_wsd), runtime_config.batch_size):
            batch = inputs_needing_wsd[i:i + runtime_config.batch_size]
            batch_num = (i // runtime_config.batch_size) + 1

            print(f"\nProcessing WSD batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            try:
                batch_results, model_used, timestamp = self._make_batch_wsd_call(batch, processing_timestamp, source_language_name, target_language_name, runtime_config)

                for input_item in batch:
                    if input_item.uid in batch_results:
                        wsd_data = batch_results[input_item.uid]

                        # Save to cache
                        cache.set(input_item.uid, wsd_data, model_used, timestamp)

                        print(f"  SUCCESS - enriched {input_item.word}")
                    else:
                        print(f"  FAILED - no result for {input_item.word}")
                        failing_inputs.append(input_item)

            except Exception as e:
                print(f"  BATCH FAILED - {str(e)}")
                failing_inputs.extend(batch)
                
        return failing_inputs
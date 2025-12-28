import json
import time
from typing import List, Tuple, Dict, Any
from typing_extensions import runtime

from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.pricing.usage_scope import UsageScope
from kindle_to_anki.core.pricing.usage_dimension import UsageDimension
from kindle_to_anki.core.pricing.usage_breakdown import UsageBreakdown
from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.core.pricing.token_estimator import count_tokens
from kindle_to_anki.core.pricing.token_pricing_policy import TokenPricingPolicy
from kindle_to_anki.platforms.platform_registry import PlatformRegistry

from .schema import LUIInput, LUIOutput
from kindle_to_anki.language.language_helper import get_language_name_in_english
from kindle_to_anki.caching.lui_cache import LUICache
from kindle_to_anki.llm.llm_helper import get_llm_lexical_unit_identification_instructions


class ChatCompletionLUI:
    """
    Runtime for Lexical Unit Identification using chat-completion LLMs.
    Supports multiple platforms and models.
    """
    id: str = "chat_completion_lui"
    display_name: str = "Chat Completion LUI Runtime"
    supported_tasks = ["lui"]
    supported_model_families = ["chat_completion"]
    supports_batching: bool = True


    def estimate_usage(self, items_count: int, runtime_config: RuntimeConfig) -> UsageBreakdown:
        # Returns estimated tokens per 1000 words (input, output)
        instruction_tokens = 500  # rough estimate for LUI instructions
        input_tokens_per_word = 5  # rough estimate
        output_tokens_per_word = 10  # rough estimate
        
        batch_size = runtime_config.batch_size
        assert batch_size is not None, "Batch size must be specified in RuntimeConfig"

        num_of_batches = (items_count + batch_size - 1) // batch_size

        estimated_input_tokens = (num_of_batches * instruction_tokens) + (input_tokens_per_word * items_count)
        estimated_output_tokens = output_tokens_per_word * items_count

        usage_breakdown = UsageBreakdown(
            scope=UsageScope(unit="notes", count=items_count),
            inputs={"tokens": UsageDimension(unit="tokens", quantity=estimated_input_tokens)},
            outputs={"tokens": UsageDimension(unit="tokens", quantity=estimated_output_tokens)},
            confidence="medium",
        )
        return usage_breakdown

    def identify(self, lui_inputs: List[LUIInput], runtime_config: RuntimeConfig, ignore_cache: bool = False, use_test_cache: bool = False) -> List[LUIOutput]:
        """
        Perform Lexical Unit Identification on a list of LUIInput objects and return LUIOutput objects.
        """
        source_lang = runtime_config.source_language_code
        target_lang = runtime_config.target_language_code
        
        print(f"\nStarting lexical unit identification (LLM) for {source_lang}...")

        language_pair_code = f"{source_lang}-{target_lang}"
        language_name = get_language_name_in_english(source_lang)

        cache_suffix = language_pair_code + "_llm"
        if use_test_cache:
            cache_suffix += "_test"

        cache = LUICache(cache_suffix=cache_suffix)

        # Filter inputs that need LUI and collect cached results
        inputs_needing_lui = []
        lui_outputs = []

        if not ignore_cache:
            cached_count = 0

            for lui_input in lui_inputs:
                cached_result = cache.get(lui_input.uid)
                if cached_result:
                    cached_count += 1
                    lui_output = LUIOutput(
                        lemma=cached_result.get('lemma', ''),
                        part_of_speech=cached_result.get('part_of_speech', ''),
                        aspect=cached_result.get('aspect', ''),
                        original_form=cached_result.get('original_form', lui_input.word),
                        unit_type=cached_result.get('unit_type', 'lemma')
                    )
                    lui_outputs.append(lui_output)
                else:
                    inputs_needing_lui.append(lui_input)

            print(f"Found {cached_count} cached identifications, {len(inputs_needing_lui)} inputs need LLM lexical unit identification")
        else:
            inputs_needing_lui = lui_inputs
            print("Ignoring cache as per user request. Fresh identifications will be generated.")

        if not inputs_needing_lui:
            print(f"{language_name} lexical unit identification (LLM) completed (all from cache).")
            return lui_outputs

        # Process inputs in batches with retry logic
        MAX_RETRIES = 1
        retries = 0
        new_outputs, failing_inputs = self._process_lui_batches(inputs_needing_lui, cache, language_name, source_lang, runtime_config)
        lui_outputs.extend(new_outputs)

        while len(failing_inputs) > 0:
            print(f"{len(failing_inputs)} inputs failed LLM lexical unit identification.")
            
            if retries >= MAX_RETRIES:
                print("All successful identification results already saved to cache. Running script again usually fixes the issue. Exiting.")
                raise RuntimeError("LUI processing failed after retries")
            
            if retries < MAX_RETRIES:
                retries += 1
                print(f"Retrying {len(failing_inputs)} failed inputs (attempt {retries} of {MAX_RETRIES})...")
                retry_outputs, failing_inputs = self._process_lui_batches(failing_inputs, cache, language_name, source_lang, runtime_config)
                lui_outputs.extend(retry_outputs)

        print(f"{language_name} lexical unit identification (LLM) completed.")
        return lui_outputs

    def _process_lui_batches(self, lui_inputs: List[LUIInput], cache: LUICache, language_name: str, language_code: str, runtime_config: RuntimeConfig) -> Tuple[List[LUIOutput], List[LUIInput]]:
        """Process inputs in batches for lexical unit identification"""

        # Capture timestamp at the start of LUI processing
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        total_batches = (len(lui_inputs) + runtime_config.batch_size - 1) // runtime_config.batch_size
        failing_inputs = []
        lui_outputs = []

        for i in range(0, len(lui_inputs), runtime_config.batch_size):
            batch = lui_inputs[i:i + runtime_config.batch_size]
            batch_num = (i // runtime_config.batch_size) + 1

            print(f"\nProcessing lexical unit identification batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            try:
                batch_results, model_used, timestamp = self._make_batch_lui_call(batch, processing_timestamp, language_name, language_code, runtime_config)

                for lui_input in batch:
                    if lui_input.uid in batch_results:
                        lui_data = batch_results[lui_input.uid]

                        # Create LUI result for caching
                        lui_result = {
                            "lemma": lui_data.get("lemma", ""),
                            "part_of_speech": lui_data.get("part_of_speech", ""),
                            "aspect": lui_data.get("aspect", ""),
                            "original_form": lui_data.get("original_form", lui_input.word),
                            "unit_type": lui_data.get("unit_type", "lemma")
                        }

                        # Save to cache
                        cache.set(lui_input.uid, lui_result, model_used, timestamp)

                        # Create LUIOutput
                        lui_output = LUIOutput(
                            lemma=lui_result["lemma"],
                            part_of_speech=lui_result["part_of_speech"],
                            aspect=lui_result["aspect"],
                            original_form=lui_result["original_form"],
                            unit_type=lui_result["unit_type"]
                        )
                        lui_outputs.append(lui_output)

                        print(f"  SUCCESS - identified {lui_input.word} → lemma: {lui_output.lemma}, pos: {lui_output.part_of_speech}")
                    else:
                        print(f"  FAILED - no LUI result for {lui_input.word}")
                        failing_inputs.append(lui_input)

            except Exception as e:
                print(f"  BATCH FAILED - {str(e)}")
                failing_inputs.extend(batch)
                
        return lui_outputs, failing_inputs

    def _make_batch_lui_call(self, batch_inputs: List[LUIInput], processing_timestamp: str, language_name: str, language_code: str, runtime_config: RuntimeConfig) -> Tuple[Dict[str, Any], str, str]:
        """Make batch LLM API call for lexical unit identification"""
        
        # Get the model and platform
        model = ModelRegistry.get(runtime_config.model_id)
        platform = PlatformRegistry.get(model.platform_id)
        
        items_list = []
        for lui_input in batch_inputs:
            items_list.append(f'{{"uid": "{lui_input.uid}", "word": "{lui_input.word}", "sentence": "{lui_input.sentence}"}}')

        items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

        prompt = get_llm_lexical_unit_identification_instructions(items_json, language_name, language_code)

        # Realtime price estimation (before making the API call)
        input_chars = len(prompt)
        input_tokens = count_tokens(prompt, model)
        estimated_output_tokens = len(batch_inputs) * 15  # rough estimate of 15 tokens per output

        estimated_usage_breakdown = UsageBreakdown(
            scope=UsageScope(unit="notes", count=len(batch_inputs)),
            inputs={"tokens": UsageDimension(unit="tokens", quantity=input_tokens)},
            outputs={"tokens": UsageDimension(unit="tokens", quantity=estimated_output_tokens)},
        )

        pricing_policy = TokenPricingPolicy(input_cost_per_1m=model.input_token_cost_per_1m, output_cost_per_1m=model.output_token_cost_per_1m)

        estimate_cost_value = pricing_policy.estimate_cost(estimated_usage_breakdown).usd
        estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"

        print(f"  Making batch lexical unit identification API call for {len(batch_inputs)} inputs ({input_chars} input chars, estimated cost: {estimated_cost_str})...")

        start_time = time.time()

        response = platform.call_api(runtime_config.model_id, prompt)

        elapsed = time.time() - start_time
        output_text = response
        
        # Realtime cost calculation (after receiving the response)
        output_chars = len(output_text)
        output_tokens = count_tokens(output_text, model)
        
        actual_usage_breakdown = UsageBreakdown(
            scope=UsageScope(unit="notes", count=len(batch_inputs)),
            inputs={"tokens": UsageDimension(unit="tokens", quantity=input_tokens)},
            outputs={"tokens": UsageDimension(unit="tokens", quantity=output_tokens)},
        )

        actual_cost = pricing_policy.estimate_cost(actual_usage_breakdown).usd
        actual_cost_str = f"${actual_cost:.6f}" if actual_cost is not None else "unknown"
        print(f"  Batch lexical unit identification API call completed in {elapsed:.2f}s ({output_chars} output chars, actual cost: {actual_cost_str})")

        return json.loads(output_text), runtime_config.model_id, processing_timestamp

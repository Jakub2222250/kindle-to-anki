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
from kindle_to_anki.tasks.translation.schema import TranslationInput, TranslationOutput
from kindle_to_anki.language.language_helper import get_language_name_in_english
from kindle_to_anki.caching.translation_cache import TranslationCache


class ChatCompletionTranslation:
    """
    Runtime for translation using chat-completion LLMs.
    Supports multiple platforms and models.
    """
    
    id: str = "chat_completion_translation"
    display_name: str = "Chat Completion Translation Runtime"
    supported_tasks = ["translation"]
    supported_model_families = ["chat_completion"]
    supports_batching: bool = True

    def _estimate_output_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 30

    def _estimate_input_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 20

    def _build_prompt(self, items_json: str, source_language_name: str, target_language_name: str) -> str:
        return f"""Translate the following {source_language_name} sentences to {target_language_name}.

Sentences to translate:
{items_json}

{self._get_llm_translation_instructions(source_language_name, target_language_name)}

Respond with valid JSON. No additional text."""

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

    def translate(self, translation_inputs: List[TranslationInput], runtime_config: RuntimeConfig, ignore_cache: bool = False, use_test_cache: bool = False) -> List[TranslationOutput]:
        """
        Translate a list of TranslationInput objects and return TranslationOutput objects.
        """
        if not translation_inputs:
            return []
        
        source_lang = runtime_config.source_language_code
        target_lang = runtime_config.target_language_code

        print("\nStarting context translation (LLM)...")

        # Get language names from the first input (assuming all have same language pair)
        source_language_name = get_language_name_in_english(source_lang)
        target_language_name = get_language_name_in_english(target_lang)

        # Setup cache
        language_pair_code = f"{source_lang}-{target_lang}"
        cache_suffix = language_pair_code + "_llm"
        if use_test_cache:
            cache_suffix += "_test"

        cache = TranslationCache(cache_suffix=cache_suffix)

        # Filter inputs that need translation and collect cached results
        inputs_needing_translation = []
        outputs = []

        if not ignore_cache:
            cached_count = 0

            for translation_input in translation_inputs:
                cached_result = cache.get(translation_input.uid)
                if cached_result:
                    cached_count += 1
                    translation_output = TranslationOutput(
                        translation=cached_result.get('context_translation', '')
                    )
                    outputs.append(translation_output)
                else:
                    inputs_needing_translation.append(translation_input)
                    outputs.append(None)  # Placeholder

            print(f"Found {cached_count} cached translations, {len(inputs_needing_translation)} inputs need LLM translation")
        else:
            inputs_needing_translation = translation_inputs
            outputs = [None] * len(translation_inputs)
            print("Ignoring cache as per user request. Fresh translations will be generated.")

        if not inputs_needing_translation:
            print(f"{source_language_name} context translation (LLM) completed (all from cache).")
            return [output for output in outputs if output is not None]

        # Process inputs in batches with retry logic
        MAX_RETRIES = 1
        retries = 0
        failing_inputs = self._process_translation_batches(inputs_needing_translation, cache, source_language_name, target_language_name, runtime_config)

        while len(failing_inputs) > 0:
            print(f"{len(failing_inputs)} inputs failed LLM translation.")
            
            if retries >= MAX_RETRIES:
                print("All successful translation results already saved to cache. Running script again usually fixes the issue. Exiting.")
                raise RuntimeError("Translation failed after retries")
            
            if retries < MAX_RETRIES:
                retries += 1
                print(f"Retrying {len(failing_inputs)} failed inputs (attempt {retries} of {MAX_RETRIES})...")
                failing_inputs = self._process_translation_batches(failing_inputs, cache, source_language_name, target_language_name, runtime_config)

        # Fill in the translated results
        translated_outputs = []
        input_index = 0
        for i, output in enumerate(outputs):
            if output is None:
                # This was a non-cached input, get from cache now
                translation_input = translation_inputs[i]
                cached_result = cache.get(translation_input.uid)
                if cached_result:
                    translation_output = TranslationOutput(
                        translation=cached_result.get('context_translation', '')
                    )
                    translated_outputs.append(translation_output)
                else:
                    # This shouldn't happen if everything worked correctly
                    translated_outputs.append(TranslationOutput(translation=""))
            else:
                translated_outputs.append(output)

        print(f"{source_language_name} context translation (LLM) completed.")
        return translated_outputs

    def _get_llm_translation_instructions(self, source_language_name: str, target_language_name: str) -> str:
        return f"""Translate the {source_language_name} sentences to {target_language_name}. Provide natural, accurate translations that preserve the meaning and context.

Output JSON as an object where keys are the UIDs and values are objects with:
- "context_translation": {target_language_name} translation of the sentence"""

    def _make_batch_translation_call(self, batch_inputs: List[TranslationInput], processing_timestamp: str, source_language_name: str, target_language_name: str, runtime_config: RuntimeConfig) -> Tuple[Dict[str, Any], str, str]:
        """Make batch LLM API call for translation"""
        items_list = []
        for input_item in batch_inputs:
            items_list.append(f'{{"uid": "{input_item.uid}", "sentence": "{input_item.context}"}}')

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

        items_json_tokens = count_tokens(items_json, model)
        print(f"    (Prompt contains {input_chars} chars / {input_tokens} tokens; items JSON part contains {items_json_tokens} tokens)")
        print(f"  Making batch translation API call for {len(batch_inputs)} inputs (in: {input_chars} chars / {input_tokens} tokens, out: ~{estimated_output_tokens} tokens, estimated cost: {estimated_cost_str})...")

        start_time = time.time()

        response_text = platform.call_api(runtime_config.model_id, prompt)

        elapsed = time.time() - start_time
        output_chars = len(response_text)
        output_tokens = count_tokens(response_text, model)

        actual_cost_str = cost_reporter.actual_cost(input_tokens, output_tokens, len(batch_inputs))
        print(f"  Batch translation API call completed in {elapsed:.2f}s (in: {input_chars} chars / {input_tokens} tokens, out: {output_chars} chars / {output_tokens} tokens, actual cost: {actual_cost_str})")

        return json.loads(response_text), runtime_config.model_id, processing_timestamp
    def _process_translation_batches(self, inputs_needing_translation: List[TranslationInput], cache: TranslationCache, source_language_name: str, target_language_name: str, runtime_config: RuntimeConfig) -> List[TranslationInput]:
        """Process inputs in batches for translation"""

        # Capture timestamp at the start of translation processing
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        total_batches = (len(inputs_needing_translation) + runtime_config.batch_size - 1) // runtime_config.batch_size
        failing_inputs = []

        for i in range(0, len(inputs_needing_translation), runtime_config.batch_size):
            batch = inputs_needing_translation[i:i + runtime_config.batch_size]
            batch_num = (i // runtime_config.batch_size) + 1

            print(f"\nProcessing translation batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            try:
                batch_results, model_used, timestamp = self._make_batch_translation_call(batch, processing_timestamp, source_language_name, target_language_name, runtime_config)

                for input_item in batch:
                    if input_item.uid in batch_results:
                        translation_data = batch_results[input_item.uid]

                        # Create translation result for caching
                        translation_result = {
                            "context_translation": translation_data.get("context_translation", "")
                        }

                        # Save to cache
                        cache.set(input_item.uid, translation_result, model_used, timestamp)

                        print(f"  SUCCESS - translated sentence for UID {input_item.uid}")
                    else:
                        print(f"  FAILED - no translation result for UID {input_item.uid}")
                        failing_inputs.append(input_item)

            except Exception as e:
                print(f"  BATCH FAILED - {str(e)}")
                failing_inputs.extend(batch)
                
        return failing_inputs

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
from .schema import SourceLanguageHintInput, SourceLanguageHintOutput
from kindle_to_anki.language.language_helper import get_language_name_in_english
from kindle_to_anki.caching.source_language_hint_cache import SourceLanguageHintCache


class ChatCompletionSourceLanguageHint:
    id: str = "chat_completion_source_language_hint"
    display_name: str = "Chat Completion Source Language Hint Runtime"
    supported_tasks = ["source_language_hint"]
    supported_model_families = ["chat_completion"]
    supports_batching: bool = True

    def _estimate_output_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 25

    def _estimate_input_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 100

    def _build_prompt(self, items_json: str, source_language_name: str) -> str:
        return f"""Provide {source_language_name} definition hints for the following words.

Items to process:
{items_json}

For each item, provide a {source_language_name} definition of the lemma form (not the inflected input word), with the meaning determined by how the input word is used in the input sentence. Consider the part of speech when providing a concise dictionary-style gloss for the base form. The lemma word should be hidden in the hint.

Respond with valid JSON as an object where keys are the UIDs and values are objects with source_language_hint. No additional text."""

    def estimate_usage(self, items_count: int, config: RuntimeConfig) -> UsageBreakdown:
        model = ModelRegistry.get(config.model_id)
        source_language_name = get_language_name_in_english(config.source_language_code)
        static_prompt = self._build_prompt("placeholder", source_language_name)
        instruction_tokens = count_tokens(static_prompt, model)
        
        input_tokens_per_item = self._estimate_input_tokens_per_item(config)
        output_tokens_per_item = self._estimate_output_tokens_per_item(config)
        
        batch_size = config.batch_size
        assert batch_size is not None

        num_of_batches = (items_count + batch_size - 1) // batch_size

        estimated_input_tokens = (num_of_batches * instruction_tokens) + (input_tokens_per_item * items_count)
        estimated_output_tokens = output_tokens_per_item * items_count

        return UsageBreakdown(
            scope=UsageScope(unit="notes", count=items_count),
            inputs={"tokens": UsageDimension(unit="tokens", quantity=estimated_input_tokens)},
            outputs={"tokens": UsageDimension(unit="tokens", quantity=estimated_output_tokens)},
            confidence="medium",
        )

    def generate(self, hint_inputs: List[SourceLanguageHintInput], runtime_config: RuntimeConfig, ignore_cache: bool = False, use_test_cache: bool = False) -> List[SourceLanguageHintOutput]:
        if not hint_inputs:
            return []
        
        source_lang = runtime_config.source_language_code

        print("\nStarting Source Language Hint generation via LLM...")

        source_language_name = get_language_name_in_english(source_lang)

        cache_suffix = source_lang + "_llm"
        if use_test_cache:
            cache_suffix += "_test"

        cache = SourceLanguageHintCache(cache_suffix=cache_suffix)

        inputs_needing_generation = []
        outputs = []

        if not ignore_cache:
            cached_count = 0
            for hint_input in hint_inputs:
                cached_result = cache.get(hint_input.uid)
                if cached_result:
                    cached_count += 1
                    outputs.append(SourceLanguageHintOutput(source_language_hint=cached_result.get('source_language_hint', '')))
                else:
                    inputs_needing_generation.append(hint_input)
                    outputs.append(None)
            print(f"Found {cached_count} cached results, {len(inputs_needing_generation)} inputs need LLM calls")
        else:
            inputs_needing_generation = hint_inputs
            outputs = [None] * len(hint_inputs)

        if not inputs_needing_generation:
            print(f"Source Language Hint generation completed (all from cache).")
            return [output for output in outputs if output is not None]

        MAX_RETRIES = 1
        retries = 0
        failing_inputs = self._process_batches(inputs_needing_generation, cache, source_language_name, runtime_config)

        while len(failing_inputs) > 0:
            if retries >= MAX_RETRIES:
                raise RuntimeError("Source language hint generation failed after retries")
            retries += 1
            failing_inputs = self._process_batches(failing_inputs, cache, source_language_name, runtime_config)

        hint_outputs = []
        for i, output in enumerate(outputs):
            if output is None:
                hint_input = hint_inputs[i]
                cached_result = cache.get(hint_input.uid)
                if cached_result:
                    hint_outputs.append(SourceLanguageHintOutput(source_language_hint=cached_result.get('source_language_hint', '')))
                else:
                    hint_outputs.append(SourceLanguageHintOutput(source_language_hint=''))
            else:
                hint_outputs.append(output)

        print(f"Source Language Hint generation completed.")
        return hint_outputs

    def _make_batch_call(self, batch_inputs: List[SourceLanguageHintInput], processing_timestamp: str, source_language_name: str, runtime_config: RuntimeConfig) -> Tuple[Dict[str, Any], str, str]:
        items_list = []
        for input_item in batch_inputs:
            items_list.append(f'{{"uid": "{input_item.uid}", "word": "{input_item.word}", "lemma": "{input_item.lemma}", "pos": "{input_item.pos}", "sentence": "{input_item.sentence}"}}')

        items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"
        prompt = self._build_prompt(items_json, source_language_name)

        model = ModelRegistry.get(runtime_config.model_id)
        platform = PlatformRegistry.get(model.platform_id)

        input_tokens = count_tokens(prompt, model)
        estimated_output_tokens = len(batch_inputs) * self._estimate_output_tokens_per_item(runtime_config)

        cost_reporter = RealtimeCostReporter(model)
        estimated_cost_str = cost_reporter.estimate_cost(input_tokens, estimated_output_tokens, len(batch_inputs))

        print(f"  Making batch source language hint API call for {len(batch_inputs)} inputs (est. cost: {estimated_cost_str})...")

        start_time = time.time()
        response_text = platform.call_api(runtime_config.model_id, prompt)
        elapsed = time.time() - start_time

        output_tokens = count_tokens(response_text, model)
        actual_cost_str = cost_reporter.actual_cost(input_tokens, output_tokens, len(batch_inputs))
        print(f"  Batch call completed in {elapsed:.2f}s (actual cost: {actual_cost_str})")

        return json.loads(response_text), runtime_config.model_id, processing_timestamp

    def _process_batches(self, inputs_needing_generation: List[SourceLanguageHintInput], cache: SourceLanguageHintCache, source_language_name: str, runtime_config: RuntimeConfig) -> List[SourceLanguageHintInput]:
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        total_batches = (len(inputs_needing_generation) + runtime_config.batch_size - 1) // runtime_config.batch_size
        failing_inputs = []

        for i in range(0, len(inputs_needing_generation), runtime_config.batch_size):
            batch = inputs_needing_generation[i:i + runtime_config.batch_size]
            batch_num = (i // runtime_config.batch_size) + 1
            print(f"\nProcessing source language hint batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            try:
                batch_results, model_used, timestamp = self._make_batch_call(batch, processing_timestamp, source_language_name, runtime_config)

                for input_item in batch:
                    if input_item.uid in batch_results:
                        cache.set(input_item.uid, batch_results[input_item.uid], model_used, timestamp)
                        print(f"  SUCCESS - generated hint for {input_item.word}")
                    else:
                        print(f"  FAILED - no result for {input_item.word}")
                        failing_inputs.append(input_item)
            except Exception as e:
                print(f"  BATCH FAILED - {str(e)}")
                failing_inputs.extend(batch)

        return failing_inputs

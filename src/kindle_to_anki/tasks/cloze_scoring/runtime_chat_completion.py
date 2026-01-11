import json
import time
from typing import List, Dict, Any

from kindle_to_anki.core.pricing.usage_dimension import UsageDimension
from kindle_to_anki.core.runtimes.batch_call_result import BatchCallResult
from kindle_to_anki.core.pricing.usage_scope import UsageScope
from kindle_to_anki.core.pricing.usage_breakdown import UsageBreakdown
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.core.pricing.token_estimator import count_tokens
from kindle_to_anki.core.pricing.realtime_cost_reporter import RealtimeCostReporter

from kindle_to_anki.platforms.platform_registry import PlatformRegistry
from kindle_to_anki.core.prompts import get_prompt
from .schema import ClozeScoringInput, ClozeScoringOutput
from kindle_to_anki.language.language_helper import get_language_name_in_english
from kindle_to_anki.caching.cloze_scoring_cache import ClozeScoringCache


class ChatCompletionClozeScoring:
    id: str = "chat_completion_cloze_scoring"
    display_name: str = "Chat Completion Cloze Scoring Runtime"
    supported_tasks = ["cloze_scoring"]
    supported_model_families = ["chat_completion"]
    supports_batching: bool = True

    def _estimate_output_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 15

    def _estimate_input_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 100

    def _build_prompt(self, items_json: str, source_language_name: str, prompt_id: str = None) -> str:
        prompt = get_prompt("cloze_scoring", prompt_id)
        return prompt.build(
            items_json=items_json,
            source_language_name=source_language_name,
        )

    def estimate_usage(self, items_count: int, config: RuntimeConfig) -> UsageBreakdown:
        model = ModelRegistry.get(config.model_id)
        source_language_name = get_language_name_in_english(config.source_language_code)
        static_prompt = self._build_prompt("placeholder", source_language_name, config.prompt_id)
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

    def score(self, scoring_inputs: List[ClozeScoringInput], runtime_config: RuntimeConfig, ignore_cache: bool = False, use_test_cache: bool = False) -> List[ClozeScoringOutput]:
        if not scoring_inputs:
            return []

        source_lang = runtime_config.source_language_code
        target_lang = runtime_config.target_language_code

        print("\nStarting Cloze Scoring via LLM...")

        source_language_name = get_language_name_in_english(source_lang)

        language_pair_code = f"{source_lang}-{target_lang}"
        cache_suffix = language_pair_code + "_llm"
        if use_test_cache:
            cache_suffix += "_test"

        cache = ClozeScoringCache(cache_suffix=cache_suffix)

        inputs_needing_scoring = []
        outputs = []

        if not ignore_cache:
            cached_count = 0
            for scoring_input in scoring_inputs:
                cached_result = cache.get(scoring_input.uid, self.id, runtime_config.model_id, runtime_config.prompt_id)
                if cached_result:
                    cached_count += 1
                    outputs.append(ClozeScoringOutput(cloze_deletion_score=cached_result.get('cloze_deletion_score', 0)))
                else:
                    inputs_needing_scoring.append(scoring_input)
                    outputs.append(None)
            print(f"Found {cached_count} cached results, {len(inputs_needing_scoring)} inputs need LLM calls")
        else:
            inputs_needing_scoring = scoring_inputs
            outputs = [None] * len(scoring_inputs)

        if not inputs_needing_scoring:
            print(f"Cloze Scoring completed (all from cache).")
            return [output for output in outputs if output is not None]

        MAX_RETRIES = 1
        retries = 0
        failing_inputs = self._process_batches(inputs_needing_scoring, cache, source_language_name, runtime_config)

        while len(failing_inputs) > 0:
            if retries >= MAX_RETRIES:
                raise RuntimeError("Cloze scoring failed after retries")
            retries += 1
            failing_inputs = self._process_batches(failing_inputs, cache, source_language_name, runtime_config)

        scoring_outputs = []
        for i, output in enumerate(outputs):
            if output is None:
                scoring_input = scoring_inputs[i]
                cached_result = cache.get(scoring_input.uid, self.id, runtime_config.model_id, runtime_config.prompt_id)
                if cached_result:
                    scoring_outputs.append(ClozeScoringOutput(cloze_deletion_score=cached_result.get('cloze_deletion_score', 0)))
                else:
                    scoring_outputs.append(ClozeScoringOutput(cloze_deletion_score=0))
            else:
                scoring_outputs.append(output)

        print(f"Cloze Scoring completed.")
        return scoring_outputs

    def _make_batch_call(self, batch_inputs: List[ClozeScoringInput], processing_timestamp: str, source_language_name: str, runtime_config: RuntimeConfig) -> BatchCallResult:
        items_list = []
        for input_item in batch_inputs:
            items_list.append(f'{{"uid": "{input_item.uid}", "word": "{input_item.word}", "sentence": "{input_item.sentence}"}}')

        items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"
        prompt = self._build_prompt(items_json, source_language_name, runtime_config.prompt_id)

        model = ModelRegistry.get(runtime_config.model_id)
        platform = PlatformRegistry.get(model.platform_id)

        input_tokens = count_tokens(prompt, model)
        estimated_output_tokens = len(batch_inputs) * self._estimate_output_tokens_per_item(runtime_config)

        cost_reporter = RealtimeCostReporter(model)
        estimated_cost_str = cost_reporter.estimate_cost(input_tokens, estimated_output_tokens, len(batch_inputs))

        print(f"  Making batch cloze scoring API call for {len(batch_inputs)} inputs (est. cost: {estimated_cost_str})...")

        start_time = time.time()

        try:
            response_text = platform.call_api(runtime_config.model_id, prompt)
        except Exception as e:
            print(f"  API call failed: {e}")
            return BatchCallResult(success=False, error=str(e))

        elapsed = time.time() - start_time

        output_tokens = count_tokens(response_text, model)
        actual_cost_str = cost_reporter.actual_cost(input_tokens, output_tokens, len(batch_inputs))
        print(f"  Batch call completed in {elapsed:.2f}s (actual cost: {actual_cost_str})")

        try:
            parsed_results = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"  Failed to parse API response as JSON: {e}")
            return BatchCallResult(success=False, error=f"JSON parse error: {e}")

        return BatchCallResult(success=True, results=parsed_results, model_id=runtime_config.model_id, timestamp=processing_timestamp)

    def _process_batches(self, inputs_needing_scoring: List[ClozeScoringInput], cache: ClozeScoringCache, source_language_name: str, runtime_config: RuntimeConfig) -> List[ClozeScoringInput]:
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        total_batches = (len(inputs_needing_scoring) + runtime_config.batch_size - 1) // runtime_config.batch_size
        failing_inputs = []

        for i in range(0, len(inputs_needing_scoring), runtime_config.batch_size):
            batch = inputs_needing_scoring[i:i + runtime_config.batch_size]
            batch_num = (i // runtime_config.batch_size) + 1
            print(f"\nProcessing cloze scoring batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            result = self._make_batch_call(batch, processing_timestamp, source_language_name, runtime_config)

            if not result.success:
                print(f"  BATCH FAILED - {result.error}")
                failing_inputs.extend(batch)
                continue

            for input_item in batch:
                if input_item.uid in result.results:
                    cache.set(input_item.uid, self.id, result.model_id, runtime_config.prompt_id, result.results[input_item.uid], result.timestamp)
                    print(f"  SUCCESS - scored {input_item.word}")
                else:
                    print(f"  FAILED - no result for {input_item.word}")
                    failing_inputs.append(input_item)

        return failing_inputs

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
from kindle_to_anki.platforms.chat_completion_platform import ChatCompletionPlatform
from kindle_to_anki.core.prompts import get_prompt
from .schema import CollocationInput, CollocationOutput
from kindle_to_anki.language.language_helper import get_language_name_in_english
from kindle_to_anki.caching.collocation_cache import CollocationCache


class ChatCompletionCollocation:
    """
    Runtime for collocation generation using chat-completion LLMs.
    Supports multiple platforms and models.
    """
    id: str = "chat_completion_collocation"
    display_name: str = "Chat Completion Collocation Runtime"
    supported_tasks = ["collocation"]
    supported_model_families = ["chat_completion"]
    supports_batching: bool = True

    def _estimate_output_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 60

    def _estimate_input_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 115

    def _build_prompt(self, items_json: str, source_language_name: str, prompt_id: str = None) -> str:
        prompt = get_prompt("collocation", prompt_id)
        return prompt.build(
            items_json=items_json,
            source_language_name=source_language_name,
        )

    def estimate_usage(self, items_count: int, config: RuntimeConfig) -> UsageBreakdown:
        model = ModelRegistry.get(config.model_id)
        source_language_name = get_language_name_in_english(config.source_language_code)
        target_language_name = get_language_name_in_english(config.target_language_code)
        static_prompt = self._build_prompt("placeholder", source_language_name, config.prompt_id)
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

    def generate_collocations(self, collocation_inputs: List[CollocationInput], runtime_config: RuntimeConfig, ignore_cache: bool = False, use_test_cache: bool = False) -> List[CollocationOutput]:
        """
        Generate collocations for a list of CollocationInput objects and return CollocationOutput objects.
        """
        if not collocation_inputs:
            return []

        source_lang = runtime_config.source_language_code
        target_lang = runtime_config.target_language_code

        print("\nStarting collocation generation (LLM)...")

        # Get language names from the inputs
        source_language_name = get_language_name_in_english(source_lang)

        # Setup cache
        language_pair_code = f"{source_lang}-{runtime_config.target_language_code}"
        cache_suffix = language_pair_code + "_llm"
        if use_test_cache:
            cache_suffix += "_test"

        cache = CollocationCache(cache_suffix=cache_suffix)

        # Filter inputs that need collocation generation and collect cached results
        inputs_needing_collocations = []
        outputs = []

        if not ignore_cache:
            cached_count = 0

            for collocation_input in collocation_inputs:
                cached_result = cache.get(collocation_input.uid, self.id, runtime_config.model_id, runtime_config.prompt_id)
                if cached_result:
                    cached_count += 1
                    collocations = cached_result.get('collocations', [])
                    collocation_output = CollocationOutput(
                        collocations=collocations if isinstance(collocations, list) else []
                    )
                    outputs.append(collocation_output)
                else:
                    inputs_needing_collocations.append(collocation_input)
                    outputs.append(None)  # Placeholder

            print(f"Found {cached_count} cached collocations, {len(inputs_needing_collocations)} inputs need LLM collocation analysis")
        else:
            inputs_needing_collocations = collocation_inputs
            outputs = [None] * len(collocation_inputs)
            print("Ignoring cache as per user request. Fresh collocations will be generated.")

        if not inputs_needing_collocations:
            print(f"{source_language_name} collocation generation (LLM) completed (all from cache).")
            return [output for output in outputs if output is not None]

        # Process inputs in batches with retry logic
        MAX_RETRIES = 1
        retries = 0
        failing_inputs = self._process_collocation_batches(inputs_needing_collocations, cache, source_language_name, runtime_config)

        while len(failing_inputs) > 0:
            print(f"{len(failing_inputs)} inputs failed LLM collocation analysis.")

            if retries >= MAX_RETRIES:
                print("All successful collocation results already saved to cache. Running script again usually fixes the issue. Exiting.")
                raise RuntimeError("Collocation generation failed after retries")

            if retries < MAX_RETRIES:
                retries += 1
                print(f"Retrying {len(failing_inputs)} failed inputs (attempt {retries} of {MAX_RETRIES})...")
                failing_inputs = self._process_collocation_batches(failing_inputs, cache, source_language_name, runtime_config)

        # Fill in the collocation results
        collocation_outputs = []
        for i, output in enumerate(outputs):
            if output is None:
                # This was a non-cached input, get from cache now
                collocation_input = collocation_inputs[i]
                cached_result = cache.get(collocation_input.uid, self.id, runtime_config.model_id, runtime_config.prompt_id)
                if cached_result:
                    collocations = cached_result.get('collocations', [])
                    collocation_output = CollocationOutput(
                        collocations=collocations if isinstance(collocations, list) else []
                    )
                    collocation_outputs.append(collocation_output)
                else:
                    # This shouldn't happen if everything worked correctly
                    collocation_outputs.append(CollocationOutput(collocations=[]))
            else:
                collocation_outputs.append(output)

        print(f"{source_language_name} collocation generation (LLM) completed.")
        return collocation_outputs

    def _make_batch_collocation_call(self, batch_inputs: List[CollocationInput], processing_timestamp: str, source_language_name: str, runtime_config: RuntimeConfig) -> BatchCallResult:
        """Make batch LLM API call for collocation generation. Returns BatchCallResult with success/failure state."""
        items_list = []
        for input_item in batch_inputs:
            items_list.append(f'{{"uid": "{input_item.uid}", "lemma": "{input_item.lemma}", "pos": "{input_item.pos}"}}')

        items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

        prompt = self._build_prompt(items_json, source_language_name, runtime_config.prompt_id)

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
        print(f"  Making batch collocation API call for {len(batch_inputs)} inputs (in: {input_chars} chars / {input_tokens} tokens, out: ~{estimated_output_tokens} tokens, estimated cost: {estimated_cost_str})...")

        start_time = time.time()

        try:
            response_text = platform.call_api(runtime_config.model_id, prompt)
        except Exception as e:
            print(f"  API call failed: {e}")
            return BatchCallResult(success=False, error=str(e))

        elapsed = time.time() - start_time
        output_chars = len(response_text)
        output_tokens = count_tokens(response_text, model)

        actual_cost_str = cost_reporter.actual_cost(input_tokens, output_tokens, len(batch_inputs))
        print(f"  Batch collocation API call completed in {elapsed:.2f}s (in: {input_chars} chars / {input_tokens} tokens, out: {output_chars} chars / {output_tokens} tokens, actual cost: {actual_cost_str})")

        try:
            parsed_results = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"  Failed to parse API response as JSON: {e}")
            return BatchCallResult(success=False, error=f"JSON parse error: {e}")

        return BatchCallResult(success=True, results=parsed_results, model_id=runtime_config.model_id, timestamp=processing_timestamp)

    def _process_collocation_batches(self, inputs_needing_collocations: List[CollocationInput], cache: CollocationCache, source_language_name: str, runtime_config: RuntimeConfig) -> List[CollocationInput]:
        """Process inputs in batches for collocation generation"""

        # Capture timestamp at the start of collocation processing
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        total_batches = (len(inputs_needing_collocations) + runtime_config.batch_size - 1) // runtime_config.batch_size
        failing_inputs = []

        for i in range(0, len(inputs_needing_collocations), runtime_config.batch_size):
            batch = inputs_needing_collocations[i:i + runtime_config.batch_size]
            batch_num = (i // runtime_config.batch_size) + 1

            print(f"\nProcessing collocation batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            result = self._make_batch_collocation_call(batch, processing_timestamp, source_language_name, runtime_config)

            if not result.success:
                print(f"  BATCH FAILED - {result.error}")
                failing_inputs.extend(batch)
                continue

            for input_item in batch:
                if input_item.uid in result.results:
                    collocation_data = result.results[input_item.uid]

                    # Create collocation result for caching
                    collocation_result = {
                        "collocations": collocation_data.get("collocations", [])
                    }

                    # Save to cache
                    cache.set(input_item.uid, self.id, result.model_id, runtime_config.prompt_id, collocation_result, result.timestamp)

                    print(f"  SUCCESS - found collocations for {input_item.lemma}")
                else:
                    print(f"  FAILED - no collocation result for {input_item.lemma}")
                    failing_inputs.append(input_item)

        return failing_inputs

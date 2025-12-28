import json
import time
from typing import List, Tuple, Dict, Any

from core.pricing.usage_dimension import UsageDimension
from core.pricing.usage_scope import UsageScope
from core.pricing.usage_breakdown import UsageBreakdown
from core.runtimes.runtime_config import RuntimeConfig
from core.models.registry import ModelRegistry
from core.pricing.token_estimator import count_tokens
from core.pricing.token_pricing_policy import TokenPricingPolicy

from platforms.platform_registry import PlatformRegistry
from platforms.chat_completion_platform import ChatCompletionPlatform
from .schema import CollocationInput, CollocationOutput
from language.language_helper import get_language_name_in_english
from caching.collocation_cache import CollocationCache


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

    def estimate_usage(self, items_count: int, config: RuntimeConfig) -> UsageBreakdown:
        # Returns estimated tokens per 1000 words (input, output)
        instruction_tokens = 500  # rough estimate for LUI instructions
        input_tokens_per_word = 5  # rough estimate
        output_tokens_per_word = 10  # rough estimate
        
        batch_size = config.batch_size
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
        target_language_name = get_language_name_in_english(target_lang)

        # Setup cache
        language_pair_code = f"{source_lang}-{target_lang}"
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
                cached_result = cache.get(collocation_input.uid)
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
        failing_inputs = self._process_collocation_batches(inputs_needing_collocations, cache, source_language_name, target_language_name, runtime_config)

        while len(failing_inputs) > 0:
            print(f"{len(failing_inputs)} inputs failed LLM collocation analysis.")
            
            if retries >= MAX_RETRIES:
                print("All successful collocation results already saved to cache. Running script again usually fixes the issue. Exiting.")
                raise RuntimeError("Collocation generation failed after retries")
            
            if retries < MAX_RETRIES:
                retries += 1
                print(f"Retrying {len(failing_inputs)} failed inputs (attempt {retries} of {MAX_RETRIES})...")
                failing_inputs = self._process_collocation_batches(failing_inputs, cache, source_language_name, target_language_name, runtime_config)

        # Fill in the collocation results
        collocation_outputs = []
        for i, output in enumerate(outputs):
            if output is None:
                # This was a non-cached input, get from cache now
                collocation_input = collocation_inputs[i]
                cached_result = cache.get(collocation_input.uid)
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

    def _get_llm_collocation_instructions(self, source_language_name: str, target_language_name: str) -> str:
        return f"""For each {source_language_name} word and sentence provided, find common {source_language_name} collocations or phrases that include the inflected input word.

Output JSON as an object where keys are the UIDs and values are objects with:
- "collocations": A JSON list of 0-3 short collocations in {source_language_name} that commonly use the input word form"""

    def _make_batch_collocation_call(self, batch_inputs: List[CollocationInput], processing_timestamp: str, source_language_name: str, target_language_name: str, runtime_config: RuntimeConfig) -> Tuple[Dict[str, Any], str, str]:
        """Make batch LLM API call for collocation generation"""
        items_list = []
        for input_item in batch_inputs:
            items_list.append(f'{{"uid": "{input_item.uid}", "word": "{input_item.word}", "lemma": "{input_item.lemma}", "pos": "{input_item.pos}", "sentence": "{input_item.sentence}"}}')

        items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

        prompt = f"""Find collocations for the following {source_language_name} words and sentences.

Words to analyze:
{items_json}

{self._get_llm_collocation_instructions(source_language_name, target_language_name)}

Respond with valid JSON. No additional text."""

        # Get the model and platform
        model = ModelRegistry.get(runtime_config.model_id)
        platform = PlatformRegistry.get(model.platform_id)

        # Realtime price estimation (before making the API call)
        input_chars = len(prompt)
        input_tokens = count_tokens(prompt, model)
        estimated_output_tokens = len(batch_inputs) * 15  # rough estimate of 15 tokens per output

        estimated_usage_breakdown = UsageBreakdown(
            scope=UsageScope(unit="notes", count=len(batch_inputs)),
            inputs={"tokens": UsageDimension(unit="tokens", quantity=input_tokens)},
            outputs={"tokens": UsageDimension(unit="tokens", quantity=estimated_output_tokens)},
        )

        pricing_policy = TokenPricingPolicy(input_cost_per_1m=model.input_cost_per_1m, output_cost_per_1m=model.output_cost_per_1m)

        estimate_cost_value = pricing_policy.estimate_cost(estimated_usage_breakdown).usd
        estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"

        print(f"  Making batch collocation API call for {len(batch_inputs)} inputs ({input_chars} input chars, estimated cost: {estimated_cost_str})...")

        start_time = time.time()

        response_text = platform.call_api(runtime_config.model_id, prompt)

        elapsed = time.time() - start_time
        output_chars = len(response_text)
        output_tokens = count_tokens(response_text, model)

        actual_usage_breakdown = UsageBreakdown(
            scope=UsageScope(unit="notes", count=len(batch_inputs)),
            inputs={"tokens": UsageDimension(unit="tokens", quantity=input_tokens)},
            outputs={"tokens": UsageDimension(unit="tokens", quantity=output_tokens)},
        )

        actual_cost = pricing_policy.estimate_cost(actual_usage_breakdown).usd
        actual_cost_str = f"${actual_cost:.6f}" if actual_cost is not None else "unknown"
        print(f"  Batch collocation API call completed in {elapsed:.2f}s ({output_chars} output chars, actual cost: {actual_cost_str})")

        return json.loads(response_text), runtime_config.model_id, processing_timestamp

    def _process_collocation_batches(self, inputs_needing_collocations: List[CollocationInput], cache: CollocationCache, source_language_name: str, target_language_name: str, runtime_config: RuntimeConfig) -> List[CollocationInput]:
        """Process inputs in batches for collocation generation"""

        # Capture timestamp at the start of collocation processing
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        total_batches = (len(inputs_needing_collocations) + runtime_config.batch_size - 1) // runtime_config.batch_size
        failing_inputs = []

        for i in range(0, len(inputs_needing_collocations), runtime_config.batch_size):
            batch = inputs_needing_collocations[i:i + runtime_config.batch_size]
            batch_num = (i // runtime_config.batch_size) + 1

            print(f"\nProcessing collocation batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            try:
                batch_results, model_used, timestamp = self._make_batch_collocation_call(batch, processing_timestamp, source_language_name, target_language_name, runtime_config)

                for input_item in batch:
                    if input_item.uid in batch_results:
                        collocation_data = batch_results[input_item.uid]

                        # Create collocation result for caching
                        collocation_result = {
                            "collocations": collocation_data.get("collocations", [])
                        }

                        # Save to cache
                        cache.set(input_item.uid, collocation_result, model_used, timestamp)

                        print(f"  SUCCESS - found collocations for {input_item.word}")
                    else:
                        print(f"  FAILED - no collocation result for {input_item.word}")
                        failing_inputs.append(input_item)

            except Exception as e:
                print(f"  BATCH FAILED - {str(e)}")
                failing_inputs.extend(batch)
                
        return failing_inputs
import json
import time
from typing import List, Tuple, Dict, Any

from platforms.chat_completion_platform import ChatCompletionPlatform
from .schema import CollocationInput, CollocationOutput
from language.language_helper import get_language_name_in_english
from caching.collocation_cache import CollocationCache
from llm.llm_helper import estimate_llm_cost, calculate_llm_cost


class ChatCompletionCollocation:
    """
    Runtime for collocation generation using chat-completion LLMs.
    Supports multiple platforms and models.
    """

    def __init__(self, platform: ChatCompletionPlatform, model_name: str, batch_size: int = 30):
        """
        platform: an instance of OpenAIPlatform or any platform implementing call_api()
        model_name: e.g., "gpt-5-mini", "gpt-5.1"
        batch_size: number of inputs to send per API call
        """
        self.platform = platform
        self.model_name = model_name
        self.batch_size = batch_size

    def generate_collocations(self, collocation_inputs: List[CollocationInput], source_lang: str, target_lang: str, ignore_cache: bool = False, use_test_cache: bool = False) -> List[CollocationOutput]:
        """
        Generate collocations for a list of CollocationInput objects and return CollocationOutput objects.
        """
        if not collocation_inputs:
            return []

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
        failing_inputs = self._process_collocation_batches(inputs_needing_collocations, cache, source_language_name, target_language_name)

        while len(failing_inputs) > 0:
            print(f"{len(failing_inputs)} inputs failed LLM collocation analysis.")
            
            if retries >= MAX_RETRIES:
                print("All successful collocation results already saved to cache. Running script again usually fixes the issue. Exiting.")
                raise RuntimeError("Collocation generation failed after retries")
            
            if retries < MAX_RETRIES:
                retries += 1
                print(f"Retrying {len(failing_inputs)} failed inputs (attempt {retries} of {MAX_RETRIES})...")
                failing_inputs = self._process_collocation_batches(failing_inputs, cache, source_language_name, target_language_name)

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

    def _make_batch_collocation_call(self, batch_inputs: List[CollocationInput], processing_timestamp: str, source_language_name: str, target_language_name: str) -> Tuple[Dict[str, Any], str, str]:
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

        input_chars = len(prompt)
        estimate_cost_value = estimate_llm_cost(prompt, len(batch_inputs), self.model_name)
        estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"
        print(f"  Making batch collocation API call for {len(batch_inputs)} inputs ({input_chars} input chars, estimated cost: {estimated_cost_str})...")
        start_time = time.time()

        messages = [{"role": "user", "content": prompt}]
        response_text = self.platform.call_api(self.model_name, messages)

        elapsed = time.time() - start_time
        output_chars = len(response_text)
        actual_cost = calculate_llm_cost(prompt, response_text, self.model_name)
        actual_cost_str = f"${actual_cost:.6f}" if actual_cost is not None else "unknown"
        print(f"  Batch collocation API call completed in {elapsed:.2f}s ({output_chars} output chars, actual cost: {actual_cost_str})")

        return json.loads(response_text), self.model_name, processing_timestamp

    def _process_collocation_batches(self, inputs_needing_collocations: List[CollocationInput], cache: CollocationCache, source_language_name: str, target_language_name: str) -> List[CollocationInput]:
        """Process inputs in batches for collocation generation"""

        # Capture timestamp at the start of collocation processing
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        total_batches = (len(inputs_needing_collocations) + self.batch_size - 1) // self.batch_size
        failing_inputs = []

        for i in range(0, len(inputs_needing_collocations), self.batch_size):
            batch = inputs_needing_collocations[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1

            print(f"\nProcessing collocation batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            try:
                batch_results, model_used, timestamp = self._make_batch_collocation_call(batch, processing_timestamp, source_language_name, target_language_name)

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
import json
import time
from typing import List, Tuple, Dict, Any

from kindle_to_anki.platforms.chat_completion_platform import ChatCompletionPlatform
from kindle_to_anki.tasks.wsd.schema import WSDInput, WSDOutput
from kindle_to_anki.language.language_helper import get_language_name_in_english
from kindle_to_anki.wsd.wsd_cache import WSDCache
from kindle_to_anki.llm.llm_helper import estimate_llm_cost, calculate_llm_cost


class ChatCompletionWSD:
    """
    Runtime for Word Sense Disambiguation using chat-completion LLMs.
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

    def disambiguate(self, wsd_inputs: List[WSDInput], source_lang: str, target_lang: str, ignore_cache: bool = False, use_test_cache: bool = False) -> List[WSDOutput]:
        """
        Perform Word Sense Disambiguation on a list of WSDInput objects and return WSDOutput objects.
        """
        if not wsd_inputs:
            return []

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
        failing_inputs = self._process_wsd_batches(inputs_needing_wsd, cache, source_language_name, target_language_name)

        while len(failing_inputs) > 0:
            print(f"{len(failing_inputs)} inputs failed LLM Word Sense Disambiguation.")
            
            if retries >= MAX_RETRIES:
                print("All successful WSD results already saved to cache. Running script again usually fixes the issue. Exiting.")
                raise RuntimeError("WSD failed after retries")
            
            if retries < MAX_RETRIES:
                retries += 1
                print(f"Retrying {len(failing_inputs)} failed inputs (attempt {retries} of {MAX_RETRIES})...")
                failing_inputs = self._process_wsd_batches(failing_inputs, cache, source_language_name, target_language_name)

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

    def _make_batch_wsd_call(self, batch_inputs: List[WSDInput], processing_timestamp: str, source_language_name: str, target_language_name: str) -> Tuple[Dict[str, Any], str, str]:
        """Make batch LLM API call for WSD"""
        items_list = []
        for input_item in batch_inputs:
            items_list.append(f'{{"uid": "{input_item.uid}", "word": "{input_item.word}", "lemma": "{input_item.lemma}", "pos": "{input_item.pos}", "sentence": "{input_item.sentence}"}}')

        items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

        prompt = f"""Process the following {source_language_name} words and sentences. For each item, provide analysis in the specified format.

Items to process:
{items_json}

For each item, {self._get_wsd_llm_instructions(source_language_name, target_language_name)}

Respond with valid JSON as an object where keys are the UIDs and values are the analysis objects. No additional text."""

        input_chars = len(prompt)
        estimate_cost_value = estimate_llm_cost(prompt, len(batch_inputs), self.model_name)
        estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"
        print(f"  Making batch WSD API call for {len(batch_inputs)} inputs ({input_chars} input chars, estimated cost: {estimated_cost_str})...")
        start_time = time.time()

        messages = [{"role": "user", "content": prompt}]
        response_text = self.platform.call_api(self.model_name, messages)

        elapsed = time.time() - start_time
        output_chars = len(response_text)
        actual_cost = calculate_llm_cost(prompt, response_text, self.model_name)
        actual_cost_str = f"${actual_cost:.6f}" if actual_cost is not None else "unknown"
        print(f"  Batch WSD API call completed in {elapsed:.2f}s ({output_chars} output chars, actual cost: {actual_cost_str})")

        return json.loads(response_text), self.model_name, processing_timestamp

    def _process_wsd_batches(self, inputs_needing_wsd: List[WSDInput], cache: WSDCache, source_language_name: str, target_language_name: str) -> List[WSDInput]:
        """Process inputs in batches for WSD"""

        # Capture timestamp at the start of WSD processing
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        total_batches = (len(inputs_needing_wsd) + self.batch_size - 1) // self.batch_size
        failing_inputs = []

        for i in range(0, len(inputs_needing_wsd), self.batch_size):
            batch = inputs_needing_wsd[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1

            print(f"\nProcessing WSD batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            try:
                batch_results, model_used, timestamp = self._make_batch_wsd_call(batch, processing_timestamp, source_language_name, target_language_name)

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
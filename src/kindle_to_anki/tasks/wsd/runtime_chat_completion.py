import json
import time
from typing import List, Dict, Any

from kindle_to_anki.logging import get_logger
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
from .schema import WSDInput, WSDOutput
from kindle_to_anki.language.language_helper import get_language_name_in_english
from kindle_to_anki.caching.wsd_cache import WSDCache
from kindle_to_anki.util.json_utils import strip_markdown_code_block


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
        return 25

    def _estimate_input_tokens_per_item(self, config: RuntimeConfig) -> int:
        return 125

    def _build_prompt(self, items_json: str, source_language_name: str, target_language_name: str, prompt_id: str = None) -> str:
        prompt = get_prompt("wsd", prompt_id)
        return prompt.build(
            items_json=items_json,
            source_language_name=source_language_name,
            target_language_name=target_language_name,
        )

    def estimate_usage(self, items_count: int, config: RuntimeConfig) -> UsageBreakdown:
        model = ModelRegistry.get(config.model_id)
        source_language_name = get_language_name_in_english(config.source_language_code)
        target_language_name = get_language_name_in_english(config.target_language_code)
        static_prompt = self._build_prompt("placeholder", source_language_name, target_language_name, config.prompt_id)
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
        logger = get_logger()

        logger.info("Starting Word Sense Disambiguation via LLM...")

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
                cached_result = cache.get(wsd_input.uid, self.id, runtime_config.model_id, runtime_config.prompt_id)
                if cached_result:
                    cached_count += 1
                    wsd_output = WSDOutput(
                        definition=cached_result.get('definition', '')
                    )
                    outputs.append(wsd_output)
                else:
                    inputs_needing_wsd.append(wsd_input)
                    outputs.append(None)  # Placeholder

            logger.info(f"Found {cached_count} cached results, {len(inputs_needing_wsd)} inputs need LLM calls")
        else:
            inputs_needing_wsd = wsd_inputs
            outputs = [None] * len(wsd_inputs)
            logger.info("Ignoring cache as per user request. Fresh results will be generated.")

        if not inputs_needing_wsd:
            logger.info(f"{source_language_name} Word Sense Disambiguation (LLM) completed (all from cache).")
            return [output for output in outputs if output is not None]

        # Process inputs in batches with retry logic
        MAX_RETRIES = 1
        retries = 0
        failing_inputs = self._process_wsd_batches(inputs_needing_wsd, cache, source_language_name, target_language_name, runtime_config)

        while len(failing_inputs) > 0:
            logger.warning(f"{len(failing_inputs)} inputs failed LLM Word Sense Disambiguation.")

            if retries >= MAX_RETRIES:
                logger.error("All successful WSD results already saved to cache. Running script again usually fixes the issue. Exiting.")
                raise RuntimeError("WSD failed after retries")

            if retries < MAX_RETRIES:
                retries += 1
                logger.info(f"Retrying {len(failing_inputs)} failed inputs (attempt {retries} of {MAX_RETRIES})...")
                failing_inputs = self._process_wsd_batches(failing_inputs, cache, source_language_name, target_language_name, runtime_config)

        # Fill in the WSD results
        wsd_outputs = []
        for i, output in enumerate(outputs):
            if output is None:
                # This was a non-cached input, get from cache now
                wsd_input = wsd_inputs[i]
                cached_result = cache.get(wsd_input.uid, self.id, runtime_config.model_id, runtime_config.prompt_id)
                if cached_result:
                    wsd_output = WSDOutput(
                        definition=cached_result.get('definition', '')
                    )
                    wsd_outputs.append(wsd_output)
                else:
                    # This shouldn't happen if everything worked correctly
                    wsd_outputs.append(WSDOutput(definition=""))
            else:
                wsd_outputs.append(output)

        logger.info(f"{source_language_name} Word Sense Disambiguation (LLM) completed.")
        return wsd_outputs

    def _make_batch_wsd_call(self, batch_inputs: List[WSDInput], processing_timestamp: str, source_language_name: str, target_language_name: str, runtime_config: RuntimeConfig) -> BatchCallResult:
        """Make batch LLM API call for WSD. Returns BatchCallResult with success/failure state."""
        logger = get_logger()
        items_list = []
        for input_item in batch_inputs:
            items_list.append(f'{{"uid": "{input_item.uid}", "word": "{input_item.word}", "lemma": "{input_item.lemma}", "pos": "{input_item.pos}", "sentence": "{input_item.sentence}"}}')

        items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

        prompt = self._build_prompt(items_json, source_language_name, target_language_name, runtime_config.prompt_id)

        # Get the model and platform
        model = ModelRegistry.get(runtime_config.model_id)
        platform = PlatformRegistry.get(model.platform_id)

        input_chars = len(prompt)
        input_tokens = count_tokens(prompt, model)
        estimated_output_tokens = len(batch_inputs) * self._estimate_output_tokens_per_item(runtime_config)

        cost_reporter = RealtimeCostReporter(model)
        estimated_cost_str = cost_reporter.estimate_cost(input_tokens, estimated_output_tokens, len(batch_inputs))

        items_json_tokens = count_tokens(items_json, model)
        logger.trace(f"Prompt contains {input_chars} chars / {input_tokens} tokens; items JSON part contains {items_json_tokens} tokens")
        logger.info(f"Making batch WSD API call for {len(batch_inputs)} inputs (in: {input_tokens} tokens, out: ~{estimated_output_tokens} tokens, est. cost: {estimated_cost_str})...")
        logger.debug(f"Full prompt:\n{prompt}")

        start_time = time.time()

        try:
            response_text = platform.call_api(runtime_config.model_id, prompt)
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return BatchCallResult(success=False, error=str(e))

        elapsed = time.time() - start_time
        output_chars = len(response_text)
        output_tokens = count_tokens(response_text, model)

        actual_cost_str = cost_reporter.actual_cost(input_tokens, output_tokens, len(batch_inputs))
        logger.info(f"Batch WSD API call completed in {elapsed:.2f}s (in: {input_tokens} tokens, out: {output_tokens} tokens, cost: {actual_cost_str})")
        logger.debug(f"Full response:\n{response_text}")

        try:
            parsed_results = json.loads(strip_markdown_code_block(response_text))
        except json.JSONDecodeError as e:
            preview = response_text[:500] if response_text else "(empty response)"
            logger.error(f"Failed to parse API response as JSON: {e}")
            logger.debug(f"Raw response preview: {preview}")
            return BatchCallResult(success=False, error=f"JSON parse error: {e}")

        return BatchCallResult(success=True, results=parsed_results, model_id=runtime_config.model_id, timestamp=processing_timestamp)

    def _process_wsd_batches(self, inputs_needing_wsd: List[WSDInput], cache: WSDCache, source_language_name: str, target_language_name: str, runtime_config: RuntimeConfig) -> List[WSDInput]:
        """Process inputs in batches for WSD"""
        logger = get_logger()

        # Capture timestamp at the start of WSD processing
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        total_batches = (len(inputs_needing_wsd) + runtime_config.batch_size - 1) // runtime_config.batch_size
        failing_inputs = []

        for i in range(0, len(inputs_needing_wsd), runtime_config.batch_size):
            batch = inputs_needing_wsd[i:i + runtime_config.batch_size]
            batch_num = (i // runtime_config.batch_size) + 1

            logger.info(f"Processing WSD batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            result = self._make_batch_wsd_call(batch, processing_timestamp, source_language_name, target_language_name, runtime_config)

            if not result.success:
                logger.error(f"BATCH FAILED - {result.error}")
                failing_inputs.extend(batch)
                continue

            for input_item in batch:
                if input_item.uid in result.results:
                    wsd_data = result.results[input_item.uid]

                    # Save to cache
                    cache.set(input_item.uid, self.id, result.model_id, runtime_config.prompt_id, wsd_data, result.timestamp)

                    logger.trace(f"enriched {input_item.word}")
                else:
                    logger.warning(f"no result for {input_item.word}")
                    failing_inputs.append(input_item)

        return failing_inputs

import json
import time
from typing import List, Tuple, Dict, Any
from typing_extensions import runtime

from kindle_to_anki.logging import get_logger, LogLevel
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.runtimes.batch_call_result import BatchCallResult
from kindle_to_anki.core.pricing.usage_scope import UsageScope
from kindle_to_anki.core.pricing.usage_dimension import UsageDimension
from kindle_to_anki.core.pricing.usage_breakdown import UsageBreakdown
from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.core.pricing.token_estimator import count_tokens
from kindle_to_anki.core.pricing.realtime_cost_reporter import RealtimeCostReporter
from kindle_to_anki.platforms.platform_registry import PlatformRegistry

from .schema import LUIInput, LUIOutput
from kindle_to_anki.language.language_helper import get_language_name_in_english
from kindle_to_anki.caching.lui_cache import LUICache
from kindle_to_anki.core.prompts import get_lui_prompt
from kindle_to_anki.util.json_utils import strip_markdown_code_block


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

    def _estimate_output_tokens_per_item(self, runtime_config: RuntimeConfig) -> int:
        if runtime_config.source_language_code == "pl":
            return 70
        return 70

    def _estimate_input_tokens_per_item(self, runtime_config: RuntimeConfig) -> int:
        if runtime_config.source_language_code == "pl":
            return 100
        return 100

    def _build_prompt(self, items_json: str, language_code: str, language_name: str, prompt_id: str = None) -> str:
        prompt = get_lui_prompt(language_code, prompt_id)
        # Generic prompt needs language_name, language-specific ones don't
        if "language_name" in prompt.spec.get("input_schema", {}):
            return prompt.build(items_json=items_json, language_name=language_name)
        return prompt.build(items_json=items_json)

    def estimate_usage(self, items_count: int, runtime_config: RuntimeConfig) -> UsageBreakdown:
        model = ModelRegistry.get(runtime_config.model_id)
        language_name = get_language_name_in_english(runtime_config.source_language_code)
        static_prompt = self._build_prompt("placeholder", runtime_config.source_language_code, language_name, runtime_config.prompt_id)
        instruction_tokens = count_tokens(static_prompt, model)

        input_tokens_per_word = self._estimate_input_tokens_per_item(runtime_config)
        output_tokens_per_word = self._estimate_output_tokens_per_item(runtime_config)

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
        Returns outputs in the same order as inputs.
        """
        source_lang = runtime_config.source_language_code
        target_lang = runtime_config.target_language_code
        logger = get_logger()

        logger.info(f"Starting lexical unit identification (LLM) for {source_lang}...")

        language_pair_code = f"{source_lang}-{target_lang}"
        language_name = get_language_name_in_english(source_lang)

        cache_suffix = language_pair_code + "_llm"
        if use_test_cache:
            cache_suffix += "_test"

        cache = LUICache(cache_suffix=cache_suffix)

        # Build output dict keyed by UID to maintain input order
        outputs_by_uid: Dict[str, LUIOutput] = {}
        inputs_needing_lui = []

        if not ignore_cache:
            cached_count = 0

            for lui_input in lui_inputs:
                cached_result = cache.get(lui_input.uid, self.id, runtime_config.model_id, runtime_config.prompt_id)
                if cached_result:
                    cached_count += 1
                    lui_output = LUIOutput(
                        lemma=cached_result.get('lemma', ''),
                        part_of_speech=cached_result.get('part_of_speech', ''),
                        aspect=cached_result.get('aspect', ''),
                        surface_lexical_unit=cached_result.get('surface_lexical_unit', lui_input.word),
                        unit_type=cached_result.get('unit_type', 'lemma')
                    )
                    outputs_by_uid[lui_input.uid] = lui_output
                else:
                    inputs_needing_lui.append(lui_input)

            logger.info(f"Found {cached_count} cached identifications, {len(inputs_needing_lui)} inputs need LLM lexical unit identification")
        else:
            inputs_needing_lui = lui_inputs
            logger.info("Ignoring cache as per user request. Fresh identifications will be generated.")

        if not inputs_needing_lui:
            logger.info(f"{language_name} lexical unit identification (LLM) completed (all from cache).")
            return [outputs_by_uid[lui_input.uid] for lui_input in lui_inputs]

        # Process inputs in batches with retry logic
        MAX_RETRIES = 1
        retries = 0
        new_outputs_by_uid, failing_inputs = self._process_lui_batches(inputs_needing_lui, cache, language_name, source_lang, runtime_config)
        outputs_by_uid.update(new_outputs_by_uid)

        while len(failing_inputs) > 0:
            logger.warning(f"{len(failing_inputs)} inputs failed LLM lexical unit identification.")

            if retries >= MAX_RETRIES:
                logger.error("All successful identification results already saved to cache. Running script again usually fixes the issue. Exiting.")
                raise RuntimeError("LUI processing failed after retries")

            if retries < MAX_RETRIES:
                retries += 1
                logger.info(f"Retrying {len(failing_inputs)} failed inputs (attempt {retries} of {MAX_RETRIES})...")
                retry_outputs_by_uid, failing_inputs = self._process_lui_batches(failing_inputs, cache, language_name, source_lang, runtime_config)
                outputs_by_uid.update(retry_outputs_by_uid)

        logger.info(f"{language_name} lexical unit identification (LLM) completed.")
        # Return outputs in original input order
        return [outputs_by_uid[lui_input.uid] for lui_input in lui_inputs]

    def _process_lui_batches(self, lui_inputs: List[LUIInput], cache: LUICache, language_name: str, language_code: str, runtime_config: RuntimeConfig) -> Tuple[Dict[str, LUIOutput], List[LUIInput]]:
        """Process inputs in batches for lexical unit identification. Returns outputs keyed by UID."""
        logger = get_logger()

        # Capture timestamp at the start of LUI processing
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        total_batches = (len(lui_inputs) + runtime_config.batch_size - 1) // runtime_config.batch_size
        failing_inputs = []
        outputs_by_uid: Dict[str, LUIOutput] = {}

        for i in range(0, len(lui_inputs), runtime_config.batch_size):
            batch = lui_inputs[i:i + runtime_config.batch_size]
            batch_num = (i // runtime_config.batch_size) + 1

            logger.info(f"Processing lexical unit identification batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            result = self._make_batch_lui_call(batch, processing_timestamp, language_name, language_code, runtime_config)

            if not result.success:
                logger.error(f"BATCH FAILED - {result.error}")
                failing_inputs.extend(batch)
                continue

            for lui_input in batch:
                if lui_input.uid in result.results:
                    lui_data = result.results[lui_input.uid]
                    surface_lexical_unit = lui_data.get("surface_lexical_unit", lui_input.word)

                    # Validate surface_lexical_unit exists in sentence
                    if surface_lexical_unit.lower() not in lui_input.sentence.lower():
                        logger.warning(f"surface_lexical_unit '{surface_lexical_unit}' not found in sentence for {lui_input.word}")
                        failing_inputs.append(lui_input)
                        continue

                    # Create LUI result for caching
                    lui_result = {
                        "lemma": lui_data.get("lemma", ""),
                        "part_of_speech": lui_data.get("part_of_speech", ""),
                        "aspect": lui_data.get("aspect", ""),
                        "surface_lexical_unit": surface_lexical_unit,
                        "unit_type": lui_data.get("unit_type", "lemma")
                    }

                    # Save to cache
                    cache.set(lui_input.uid, self.id, result.model_id, runtime_config.prompt_id, lui_result, result.timestamp)

                    # Create LUIOutput
                    lui_output = LUIOutput(
                        lemma=lui_result["lemma"],
                        part_of_speech=lui_result["part_of_speech"],
                        aspect=lui_result["aspect"],
                        surface_lexical_unit=lui_result["surface_lexical_unit"],
                        unit_type=lui_result["unit_type"]
                    )
                    outputs_by_uid[lui_input.uid] = lui_output

                    logger.trace(f"identified {lui_input.word} → lemma: {lui_output.lemma}, pos: {lui_output.part_of_speech}")
                else:
                    logger.warning(f"no LUI result for {lui_input.word}")
                    failing_inputs.append(lui_input)

        return outputs_by_uid, failing_inputs

    def _make_batch_lui_call(self, batch_inputs: List[LUIInput], processing_timestamp: str, language_name: str, language_code: str, runtime_config: RuntimeConfig) -> BatchCallResult:
        """Make batch LLM API call for lexical unit identification. Returns BatchCallResult with success/failure state."""
        logger = get_logger()

        # Get the model and platform
        model = ModelRegistry.get(runtime_config.model_id)
        platform = PlatformRegistry.get(model.platform_id)

        items_list = []
        for lui_input in batch_inputs:
            items_list.append(f'{{"uid": "{lui_input.uid}", "word": "{lui_input.word}", "sentence": "{lui_input.sentence}"}}')

        items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

        prompt = self._build_prompt(items_json, language_code, language_name, runtime_config.prompt_id)

        input_chars = len(prompt)
        input_tokens = count_tokens(prompt, model)
        estimated_output_tokens = len(batch_inputs) * self._estimate_output_tokens_per_item(runtime_config)

        cost_reporter = RealtimeCostReporter(model)
        estimated_cost_str = cost_reporter.estimate_cost(input_tokens, estimated_output_tokens, len(batch_inputs))

        items_json_tokens = count_tokens(items_json, model)
        logger.trace(f"Prompt contains {input_chars} chars / {input_tokens} tokens; items JSON part contains {items_json_tokens} tokens")
        logger.info(f"Making batch LUI API call for {len(batch_inputs)} inputs (in: {input_tokens} tokens, out: ~{estimated_output_tokens} tokens, est. cost: {estimated_cost_str})...")
        logger.debug(f"Full prompt:\n{prompt}")

        start_time = time.time()

        try:
            response = platform.call_api(runtime_config.model_id, prompt)
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return BatchCallResult(success=False, error=str(e))

        elapsed = time.time() - start_time
        output_text = response

        output_chars = len(output_text)
        output_tokens = count_tokens(output_text, model)

        actual_cost_str = cost_reporter.actual_cost(input_tokens, output_tokens, len(batch_inputs))
        logger.info(f"Batch LUI API call completed in {elapsed:.2f}s (in: {input_tokens} tokens, out: {output_tokens} tokens, cost: {actual_cost_str})")
        logger.debug(f"Full response:\n{output_text}")

        try:
            parsed_results = json.loads(strip_markdown_code_block(output_text))
        except json.JSONDecodeError as e:
            preview = output_text[:500] if output_text else "(empty response)"
            logger.error(f"Failed to parse API response as JSON: {e}")
            logger.debug(f"Raw response preview: {preview}")
            return BatchCallResult(success=False, error=f"JSON parse error: {e}")

        return BatchCallResult(success=True, results=parsed_results, model_id=runtime_config.model_id, timestamp=processing_timestamp)

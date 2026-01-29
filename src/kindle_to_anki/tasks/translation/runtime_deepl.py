import time
from typing import List

from kindle_to_anki.core.pricing.usage_dimension import UsageDimension
from kindle_to_anki.core.pricing.usage_scope import UsageScope
from kindle_to_anki.core.pricing.usage_breakdown import UsageBreakdown
from kindle_to_anki.core.pricing.character_pricing_policy import CharacterPricingPolicy
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig

from kindle_to_anki.platforms.platform_registry import PlatformRegistry
from kindle_to_anki.tasks.translation.schema import TranslationInput, TranslationOutput
from kindle_to_anki.caching.translation_cache import TranslationCache


# DeepL API Pro pricing: $20 per 1M characters
DEEPL_COST_PER_1M_CHARS = 20.00


class DeepLTranslation:
    """
    Runtime for translation using DeepL API.
    """

    id: str = "deepl_translation"
    display_name: str = "DeepL Translation Runtime"
    supported_tasks = ["translation"]
    supported_model_families = None
    supports_batching: bool = True

    def estimate_usage(self, items_count: int, config: RuntimeConfig) -> UsageBreakdown:
        # Estimate ~50 characters per context sentence
        chars_per_item = 50
        estimated_chars = chars_per_item * items_count

        return UsageBreakdown(
            scope=UsageScope(unit="notes", count=items_count),
            inputs={"characters": UsageDimension(unit="characters", quantity=estimated_chars)},
            outputs={},
            confidence="medium",
        )

    def translate(self, translation_inputs: List[TranslationInput], runtime_config: RuntimeConfig, ignore_cache: bool = False, use_test_cache: bool = False) -> List[TranslationOutput]:
        if not translation_inputs:
            return []

        source_lang = runtime_config.source_language_code.upper()
        target_lang = runtime_config.target_language_code.upper()

        get_logger().info("Starting context translation (DeepL)...")

        # Setup cache
        language_pair_code = f"{runtime_config.source_language_code}-{runtime_config.target_language_code}"
        cache_suffix = language_pair_code + "_deepl"
        if use_test_cache:
            cache_suffix += "_test"

        cache = TranslationCache(cache_suffix=cache_suffix)

        # Filter inputs that need translation
        inputs_needing_translation = []
        outputs = []

        if not ignore_cache:
            cached_count = 0
            for translation_input in translation_inputs:
                cached_result = cache.get(translation_input.uid, self.id, "deepl", "")
                if cached_result:
                    cached_count += 1
                    outputs.append(TranslationOutput(translation=cached_result.get('context_translation', '')))
                else:
                    inputs_needing_translation.append(translation_input)
                    outputs.append(None)
            get_logger().info(f"Found {cached_count} cached translations, {len(inputs_needing_translation)} need DeepL translation")
        else:
            inputs_needing_translation = translation_inputs
            outputs = [None] * len(translation_inputs)

        if not inputs_needing_translation:
            get_logger().info("DeepL translation completed (all from cache).")
            return [o for o in outputs if o is not None]

        # Process in batches
        failing_inputs = self._process_batches(inputs_needing_translation, cache, source_lang, target_lang, runtime_config)

        if failing_inputs:
            get_logger().warning(f"{len(failing_inputs)} inputs failed DeepL translation.")

        # Build final outputs
        translated_outputs = []
        for i, output in enumerate(outputs):
            if output is None:
                cached_result = cache.get(translation_inputs[i].uid, self.id, "deepl", "")
                if cached_result:
                    translated_outputs.append(TranslationOutput(translation=cached_result.get('context_translation', '')))
                else:
                    translated_outputs.append(TranslationOutput(translation=""))
            else:
                translated_outputs.append(output)

        get_logger().info("DeepL translation completed.")
        return translated_outputs

    def _process_batches(self, inputs: List[TranslationInput], cache: TranslationCache, source_lang: str, target_lang: str, config: RuntimeConfig) -> List[TranslationInput]:
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        batch_size = config.batch_size or 50  # DeepL allows up to 50 texts per request
        total_batches = (len(inputs) + batch_size - 1) // batch_size
        failing_inputs = []

        platform = PlatformRegistry.get("deepl")
        pricing_policy = CharacterPricingPolicy(cost_per_1m_chars=DEEPL_COST_PER_1M_CHARS)

        for i in range(0, len(inputs), batch_size):
            batch = inputs[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            get_logger().debug(f"Processing DeepL batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            texts = [inp.context for inp in batch]
            total_chars = sum(len(t) for t in texts)

            # Cost estimation
            usage = UsageBreakdown(
                scope=UsageScope(unit="notes", count=len(batch)),
                inputs={"characters": UsageDimension(unit="characters", quantity=total_chars)},
                outputs={},
                confidence="high",
            )
            est_cost = pricing_policy.estimate_cost(usage).usd
            get_logger().debug(f"  {total_chars} chars, estimated cost: ${est_cost:.6f}")

            start_time = time.time()

            try:
                translations = platform.translate(texts, target_lang, source_lang)
            except Exception as e:
                get_logger().error(f"  API call failed: {e}")
                failing_inputs.extend(batch)
                continue

            elapsed = time.time() - start_time
            get_logger().debug(f"  Batch completed in {elapsed:.2f}s")

            for inp, trans in zip(batch, translations):
                cache.set(inp.uid, self.id, "deepl", "", {"context_translation": trans}, processing_timestamp)
                get_logger().debug(f"  SUCCESS - translated UID {inp.uid}")

        return failing_inputs

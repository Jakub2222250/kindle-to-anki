import time
from typing import List

from core.pricing.usage_dimension import UsageDimension
from core.pricing.usage_scope import UsageScope
from core.pricing.usage_breakdown import UsageBreakdown
from core.pricing.character_pricing_policy import CharacterPricingPolicy
from core.runtimes.runtime_config import RuntimeConfig

from platforms.platform_registry import PlatformRegistry
from tasks.translation.schema import TranslationInput, TranslationOutput
from caching.translation_cache import TranslationCache


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

        print("\nStarting context translation (DeepL)...")

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
                cached_result = cache.get(translation_input.uid)
                if cached_result:
                    cached_count += 1
                    outputs.append(TranslationOutput(translation=cached_result.get('context_translation', '')))
                else:
                    inputs_needing_translation.append(translation_input)
                    outputs.append(None)
            print(f"Found {cached_count} cached translations, {len(inputs_needing_translation)} need DeepL translation")
        else:
            inputs_needing_translation = translation_inputs
            outputs = [None] * len(translation_inputs)

        if not inputs_needing_translation:
            print("DeepL translation completed (all from cache).")
            return [o for o in outputs if o is not None]

        # Process in batches
        failing_inputs = self._process_batches(inputs_needing_translation, cache, source_lang, target_lang, runtime_config)

        if failing_inputs:
            print(f"{len(failing_inputs)} inputs failed DeepL translation.")

        # Build final outputs
        translated_outputs = []
        for i, output in enumerate(outputs):
            if output is None:
                cached_result = cache.get(translation_inputs[i].uid)
                if cached_result:
                    translated_outputs.append(TranslationOutput(translation=cached_result.get('context_translation', '')))
                else:
                    translated_outputs.append(TranslationOutput(translation=""))
            else:
                translated_outputs.append(output)

        print("DeepL translation completed.")
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
            print(f"\nProcessing DeepL batch {batch_num}/{total_batches} ({len(batch)} inputs)")

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
            print(f"  {total_chars} chars, estimated cost: ${est_cost:.6f}")

            try:
                start_time = time.time()
                translations = platform.translate(texts, target_lang, source_lang)
                elapsed = time.time() - start_time

                print(f"  Batch completed in {elapsed:.2f}s")

                for inp, trans in zip(batch, translations):
                    cache.set(inp.uid, {"context_translation": trans}, "deepl", processing_timestamp)
                    print(f"  SUCCESS - translated UID {inp.uid}")

            except Exception as e:
                print(f"  BATCH FAILED - {str(e)}")
                failing_inputs.extend(batch)

        return failing_inputs

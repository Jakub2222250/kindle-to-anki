import time
from typing import List

from kindle_to_anki.core.pricing.usage_dimension import UsageDimension
from kindle_to_anki.core.pricing.usage_scope import UsageScope
from kindle_to_anki.core.pricing.usage_breakdown import UsageBreakdown
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig

from .schema import TranslationInput, TranslationOutput
from kindle_to_anki.caching.translation_cache import TranslationCache


class PolishLocalTranslation:
    """
    Runtime for translation using local MarianMT model for Polish to English translation.
    """

    id: str = "polish_local_translation"
    display_name: str = "Polish Local Translation Runtime"
    supported_tasks = ["translation"]
    supported_model_families = []
    supports_batching: bool = True

    def estimate_usage(self, items_count: int, config: RuntimeConfig) -> UsageBreakdown:
        return None

    def translate(self, translation_inputs: List[TranslationInput], ignore_cache: bool = False, use_test_cache: bool = False) -> List[TranslationOutput]:
        """
        Translate a list of TranslationInput objects and return TranslationOutput objects.

        NOTE: This runtime is specifically designed for Polish to English translation.
        source_lang and target_lang parameters are accepted for API compatibility but ignored.
        """
        if not translation_inputs:
            return []

        print("\nStarting Polish context translation (local MarianMT)...")

        # Setup cache
        cache_suffix = "pl-en_local"
        if use_test_cache:
            cache_suffix += "_test"

        cache = TranslationCache(cache_suffix=cache_suffix)

        # Filter inputs that need translation and collect cached results
        inputs_needing_translation = []
        outputs = []

        if not ignore_cache:
            cached_count = 0

            for translation_input in translation_inputs:
                cached_result = cache.get(translation_input.uid, self.id, self.model_name, "")
                if cached_result:
                    cached_count += 1
                    translation_output = TranslationOutput(
                        translation=cached_result.get('context_translation', '')
                    )
                    outputs.append(translation_output)
                else:
                    inputs_needing_translation.append(translation_input)
                    outputs.append(None)  # Placeholder

            print(f"Found {cached_count} cached translations, {len(inputs_needing_translation)} inputs need local translation")
        else:
            inputs_needing_translation = translation_inputs
            outputs = [None] * len(translation_inputs)
            print("Ignoring cache as per user request. Fresh translations will be generated.")

        if not inputs_needing_translation:
            print("Polish context translation (local MarianMT) completed (all from cache).")
            return [output for output in outputs if output is not None]

        # Process inputs in batches
        self._process_translation_batches(inputs_needing_translation, cache)

        # Fill in the translated results
        translated_outputs = []
        for i, output in enumerate(outputs):
            if output is None:
                # This was a non-cached input, get from cache now
                translation_input = translation_inputs[i]
                cached_result = cache.get(translation_input.uid, self.id, self.model_name, "")
                if cached_result:
                    translation_output = TranslationOutput(
                        translation=cached_result.get('context_translation', '')
                    )
                    translated_outputs.append(translation_output)
                else:
                    # This shouldn't happen if everything worked correctly
                    translated_outputs.append(TranslationOutput(translation=""))
            else:
                translated_outputs.append(output)

        print("Polish context translation (local MarianMT) completed.")
        return translated_outputs

    def _process_translation_batches(self, inputs_needing_translation: List[TranslationInput], cache: TranslationCache):
        """Process inputs in batches for translation using local MarianMT model"""

        # Capture timestamp at the start of translation processing
        processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        total_batches = (len(inputs_needing_translation) + self.batch_size - 1) // self.batch_size

        print(f"Translating {len(inputs_needing_translation)} inputs using local MarianMT model...")

        # Import transformers only when needed
        from transformers import MarianMTModel, MarianTokenizer

        # Load model and tokenizer
        tokenizer = MarianTokenizer.from_pretrained(self.model_name)
        model = MarianMTModel.from_pretrained(self.model_name)

        for i in range(0, len(inputs_needing_translation), self.batch_size):
            batch = inputs_needing_translation[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1

            print(f"  Processing translation batch {batch_num}/{total_batches} ({len(batch)} inputs)")

            # Extract texts for translation
            src_texts = [input_item.context for input_item in batch]

            # Translate batch
            tokenized = tokenizer(src_texts, return_tensors="pt", padding=True)
            translated = model.generate(**tokenized)
            results = tokenizer.batch_decode(translated, skip_special_tokens=True)

            # Save results to cache
            for input_item, translated_text in zip(batch, results):
                # Create translation result for caching
                translation_result = {
                    "context_translation": translated_text
                }

                # Save to cache
                cache.set(input_item.uid, self.id, self.model_name, "", translation_result, processing_timestamp)

                print(f"    SUCCESS - translated sentence for UID {input_item.uid}")

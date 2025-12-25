from anki.anki_note import AnkiNote
from translation.translation_cache import TranslationCache
import time


def translate_polish_context_to_english(notes: list[AnkiNote], ignore_cache=False, use_test_cache=False):
    """Translate Polish context notes to English"""

    print("\nStarting Polish context translation...")

    cache_suffix = "pl-en_local"
    if use_test_cache:
        cache_suffix += "_test"

    cache = TranslationCache(cache_suffix=cache_suffix)
    if not ignore_cache:
        print(f"Loaded translation cache with {len(cache.cache)} entries")
    else:
        print("Ignoring cache as per user request. Fresh translations will be generated.")

    # Capture timestamp at the start of translation processing
    processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    model_name = "Helsinki-NLP/opus-mt-pl-en"

    # Filter notes that need translation and collect cached results
    notes_needing_translation = []
    cached_count = 0

    for note in notes:
        if not note.context_sentence:
            continue

        cached_result = cache.get(note.uid)
        if cached_result:
            cached_count += 1
            note.context_translation = cached_result['context_translation']
        else:
            notes_needing_translation.append(note)

    print(f"Found {cached_count} cached translations, {len(notes_needing_translation)} notes need translation")

    if not notes_needing_translation:
        print("Polish context translation completed (all from cache).")
        return

    # Process notes that need translation
    print(f"\nTranslating {len(notes_needing_translation)} notes using local MarianMT model...")

    from transformers import MarianMTModel, MarianTokenizer
    src_texts = [note.context_sentence for note in notes_needing_translation]

    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)

    batch = tokenizer(src_texts, return_tensors="pt", padding=True)
    translated = model.generate(**batch)
    result = tokenizer.batch_decode(translated, skip_special_tokens=True)

    # Save results to cache and update notes
    for note, translated_text in zip(notes_needing_translation, result):
        note.context_translation = translated_text

        # Create translation result for caching
        translation_result = {
            "context_translation": translated_text
        }

        # Save to cache
        cache.set(note.uid, translation_result, model_name, processing_timestamp)

    print("Polish context translation completed.")




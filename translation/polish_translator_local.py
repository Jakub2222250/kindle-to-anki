from transformers import MarianMTModel, MarianTokenizer
from anki.anki_note import AnkiNote
from translation.translation_cache import TranslationCache
import time


def translate_polish_context_to_english(notes: list[AnkiNote], cache: TranslationCache):
    """Translate Polish context notes to English"""

    print("\nStarting Polish context translation...")

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


if __name__ == "__main__":
    # Example usage
    notes = [
        AnkiNote(
            word="przykład",
            stem="przykład",
            usage="To jest przykład zdania.",
            language="pl",
            book_name="Sample Book",
            position="123-456",
            timestamp="2024-01-01T12:00:00Z"
        ),
        AnkiNote(
            word="bawół",
            stem="bawołem",
            usage="Nie zapominajcie o czarodzieju Baruffio, który źle wypowiedział spółgłoskę i znalazł się na podłodze, przygnieciony bawołem.",
            language="pl",
            book_name="Sample Book",
            position="789-1011",
            timestamp="2024-01-01T12:05:00Z"
        )
    ]

    cache = TranslationCache(cache_suffix='pl_local_test')
    translate_polish_context_to_english(notes, cache)

    print()
    for note in notes:
        print(f"Original: {note.context_sentence}")
        print(f"Translated: {note.context_translation}")

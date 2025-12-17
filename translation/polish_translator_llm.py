import json
import time
from pathlib import Path
from openai import OpenAI
from anki.anki_note import AnkiNote
from translation.translation_cache import TranslationCache


# Configuration
BATCH_SIZE = 40
TRANSLATION_LLM = "gpt-5-mini"

# LLM translation instructions
LLM_TRANSLATION_INSTRUCTIONS = """Translate the Polish sentences to English. Provide natural, accurate translations that preserve the meaning and context.

Output JSON as an object where keys are the UIDs and values are objects with:
- "context_translation": English translation of the sentence"""


def estimate_translation_cost(input_chars, notes_count, model):
    """Estimate cost for translation API calls"""
    pricing = {
        "gpt-5": {"input_cost_per_1m_tokens": 1.25, "output_cost_per_1m_tokens": 10.00},
        "gpt-4.1": {"input_cost_per_1m_tokens": 2.00, "output_cost_per_1m_tokens": 8.00},
        "gpt-5-mini": {"input_cost_per_1m_tokens": 0.25, "output_cost_per_1m_tokens": 2.00},
    }

    ESTIMATED_CHARS_PER_TRANSLATION = 200

    input_tokens = input_chars / 4
    output_tokens = ESTIMATED_CHARS_PER_TRANSLATION * notes_count / 4

    if model not in pricing:
        return None

    input_cost = (input_tokens / 1_000_000) * pricing[model]["input_cost_per_1m_tokens"]
    output_cost = (output_tokens / 1_000_000) * pricing[model]["output_cost_per_1m_tokens"]

    return input_cost + output_cost


def make_batch_translation_call(batch_notes, processing_timestamp):
    """Make batch LLM API call for translation"""
    items_list = []
    for note in batch_notes:
        sentence = note.kindle_usage or note.context_sentence
        items_list.append(f'{{"uid": "{note.uid}", "sentence": "{sentence}"}}')

    items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

    prompt = f"""Translate the following Polish sentences to English.

Sentences to translate:
{items_json}

{LLM_TRANSLATION_INSTRUCTIONS}

Respond with valid JSON. No additional text."""

    input_chars = len(prompt)
    estimate_cost_value = estimate_translation_cost(input_chars, len(batch_notes), TRANSLATION_LLM)
    estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"
    print(f"  Making batch translation API call for {len(batch_notes)} notes ({input_chars} input chars, estimated cost: {estimated_cost_str})...")
    start_time = time.time()

    client = OpenAI()
    response = client.chat.completions.create(
        model=TRANSLATION_LLM,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed = time.time() - start_time
    output_chars = len(response.choices[0].message.content)
    print(f"  Batch translation API call completed in {elapsed:.2f}s ({output_chars} output chars)")

    return json.loads(response.choices[0].message.content), TRANSLATION_LLM, processing_timestamp


def process_translation_batches(notes_needing_translation: list[AnkiNote], cache: TranslationCache):
    """Process notes in batches for translation"""

    # Capture timestamp at the start of translation processing
    processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    total_batches = (len(notes_needing_translation) + BATCH_SIZE - 1) // BATCH_SIZE
    failing_notes = []

    for i in range(0, len(notes_needing_translation), BATCH_SIZE):
        batch = notes_needing_translation[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        print(f"\nProcessing translation batch {batch_num}/{total_batches} ({len(batch)} notes)")

        try:
            batch_results, model_used, timestamp = make_batch_translation_call(batch, processing_timestamp)

            for note in batch:
                if note.uid in batch_results:
                    translation_data = batch_results[note.uid]

                    # Create translation result for caching
                    translation_result = {
                        "context_translation": translation_data.get("context_translation", "")
                    }

                    # Save to cache
                    cache.set(note.uid, translation_result, model_used, timestamp)

                    # Apply to note
                    note.context_translation = translation_result["context_translation"]
                    print(f"  SUCCESS - translated sentence for {note.kindle_word}")
                else:
                    print(f"  FAILED - no translation result for {note.kindle_word}")
                    failing_notes.append(note)

        except Exception as e:
            print(f"  BATCH FAILED - {str(e)}")
            failing_notes.extend(batch)

    if len(failing_notes) > 0:
        print(f"{len(failing_notes)} notes failed LLM translation.")
        print("All successful translation results already saved to cache. Running script again usually fixes the issue. Exiting.")
        exit()


def translate_polish_context_to_english_llm(notes: list[AnkiNote], cache: TranslationCache):
    """Translate Polish context notes to English using LLM"""

    print("\nStarting Polish context translation (LLM)...")

    # Filter notes that need translation and collect cached results
    notes_needing_translation = []
    cached_count = 0

    for note in notes:
        sentence = note.kindle_usage or note.context_sentence
        if not sentence:
            continue

        cached_result = cache.get(note.uid)
        if cached_result:
            cached_count += 1
            note.context_translation = cached_result.get('context_translation', '')
        else:
            notes_needing_translation.append(note)

    print(f"Found {cached_count} cached translations, {len(notes_needing_translation)} notes need LLM translation")

    if not notes_needing_translation:
        print("Polish context translation (LLM) completed (all from cache).")
        return

    if len(notes_needing_translation) > 100:
        result = input(f"\nDo you want to proceed with LLM translation API calls for {len(notes_needing_translation)} notes? (y/n): ").strip().lower()
        if result != 'y' and result != 'yes':
            print("LLM translation process aborted by user.")
            exit()

    # Process notes in batches
    process_translation_batches(notes_needing_translation, cache)

    print("Polish context translation (LLM) completed.")


if __name__ == "__main__":
    # Example usage and testing
    notes = [
        AnkiNote(
            word="przykład",
            stem="przykład",
            usage="To jest przykład zdania do przetłumaczenia.",
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

    cache = TranslationCache(cache_suffix='pl_llm_test')
    translate_polish_context_to_english_llm(notes, cache)

    print()
    for note in notes:
        print(f"Original: {note.context_sentence}")
        print(f"Translated: {note.context_translation}")

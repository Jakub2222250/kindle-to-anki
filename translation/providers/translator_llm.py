import json
import time
from openai import OpenAI
from anki.anki_note import AnkiNote
from language.language_helper import get_language_name_in_english
from translation.translation_cache import TranslationCache
from llm.llm_helper import estimate_llm_cost, calculate_llm_cost


# Configuration
BATCH_SIZE = 40
TRANSLATION_LLM = "gpt-5"

# LLM translation instructions


def get_llm_translation_instructions(source_language_name: str, target_language_name: str) -> str:

    return f"""Translate the {source_language_name} sentences to {target_language_name}. Provide natural, accurate translations that preserve the meaning and context.

Output JSON as an object where keys are the UIDs and values are objects with:
- "context_translation": {target_language_name} translation of the sentence"""


def make_batch_translation_call(batch_notes, processing_timestamp, source_language_name, target_language_name):
    """Make batch LLM API call for translation"""
    items_list = []
    for note in batch_notes:
        sentence = note.kindle_usage or note.context_sentence
        items_list.append(f'{{"uid": "{note.uid}", "sentence": "{sentence}"}}')

    items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

    prompt = f"""Translate the following {source_language_name} sentences to {target_language_name}.

Sentences to translate:
{items_json}

{get_llm_translation_instructions(source_language_name, target_language_name)}

Respond with valid JSON. No additional text."""

    input_chars = len(prompt)
    estimate_cost_value = estimate_llm_cost(prompt, len(batch_notes), TRANSLATION_LLM)
    estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"
    print(f"  Making batch translation API call for {len(batch_notes)} notes ({input_chars} input chars, estimated cost: {estimated_cost_str})...")
    start_time = time.time()

    client = OpenAI()
    response = client.chat.completions.create(
        model=TRANSLATION_LLM,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed = time.time() - start_time
    output_text = response.choices[0].message.content
    output_chars = len(output_text)
    actual_cost = calculate_llm_cost(prompt, output_text, TRANSLATION_LLM)
    actual_cost_str = f"${actual_cost:.6f}" if actual_cost is not None else "unknown"
    print(f"  Batch translation API call completed in {elapsed:.2f}s ({output_chars} output chars, actual cost: {actual_cost_str})")

    return json.loads(output_text), TRANSLATION_LLM, processing_timestamp


def process_translation_batches(notes_needing_translation: list[AnkiNote], cache: TranslationCache, source_language_name: str, target_language_name: str):
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
            batch_results, model_used, timestamp = make_batch_translation_call(batch, processing_timestamp, source_language_name, target_language_name)

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
            
    return failing_notes


def translate_context_with_llm(notes: list[AnkiNote], source_lang_code: str, target_lang_code: str, ignore_cache=False, use_test_cache=False):
    """Translate context notes to using LLM"""

    print("\nStarting context translation (LLM)...")

    language_pair_code = f"{source_lang_code}-{target_lang_code}"
    source_language_name = get_language_name_in_english(source_lang_code)
    target_language_name = get_language_name_in_english(target_lang_code)

    cache_suffix = language_pair_code + "_llm"
    if use_test_cache:  
        cache_suffix += "_test"

    cache = TranslationCache(cache_suffix=cache_suffix)

    # Filter notes that need translation and collect cached results
    notes_needing_translation = []

    if not ignore_cache:
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
    else:
        notes_needing_translation = notes
        print("Ignoring cache as per user request. Fresh translations will be generated.")

    if not notes_needing_translation:
        print(f"{source_language_name} context translation (LLM) completed (all from cache).")
        return

    # Process notes in batches with retry logic
    MAX_RETRIES = 1
    retries = 0
    failing_notes = process_translation_batches(notes_needing_translation, cache, source_language_name, target_language_name)

    while len(failing_notes) > 0:
        print(f"{len(failing_notes)} notes failed LLM translation.")
        
        if retries >= MAX_RETRIES:
            print("All successful translation results already saved to cache. Running script again usually fixes the issue. Exiting.")
            exit()
        
        if retries < MAX_RETRIES:
            retries += 1
            print(f"Retrying {len(failing_notes)} failed notes (attempt {retries} of {MAX_RETRIES})...")
            failing_notes = process_translation_batches(failing_notes, cache, source_language_name, target_language_name)

    print(f"{source_language_name} context translation (LLM) completed.")


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

    translate_context_with_llm(notes, "pl", "en", ignore_cache=False, use_test_cache=True)

    print()
    for note in notes:
        print(f"Original: {note.context_sentence}")
        print(f"Translated: {note.context_translation}")

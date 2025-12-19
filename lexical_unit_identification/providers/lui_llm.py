import json
import time
from typing import List
from openai import OpenAI

from anki.anki_note import AnkiNote
from lexical_unit_identification.ma_cache import MACache
from language.language_helper import get_language_name_in_english
from llm.llm_helper import estimate_llm_cost, calculate_llm_cost, get_llm_lexical_unit_identification_instructions


# Configuration
BATCH_SIZE = 30
LUI_LLM = "gpt-5"


def make_batch_lui_call(batch_notes, processing_timestamp, language_name, language_code=""):
    """Make batch LLM API call for lexical unit identification"""
    items_list = []
    for note in batch_notes:
        sentence = note.kindle_usage or note.context_sentence or ""
        items_list.append(f'{{"uid": "{note.uid}", "word": "{note.kindle_word}", "sentence": "{sentence}"}}')

    items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

    prompt = get_llm_lexical_unit_identification_instructions(items_json, language_name, language_code)

    input_chars = len(prompt)
    estimate_cost_value = estimate_llm_cost(prompt, len(batch_notes), LUI_LLM)
    estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"
    print(f"  Making batch lexical unit identification API call for {len(batch_notes)} notes ({input_chars} input chars, estimated cost: {estimated_cost_str})...")
    start_time = time.time()

    client = OpenAI()
    response = client.chat.completions.create(
        model=LUI_LLM,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed = time.time() - start_time
    output_text = response.choices[0].message.content
    output_chars = len(output_text)
    actual_cost = calculate_llm_cost(prompt, output_text, LUI_LLM)
    actual_cost_str = f"${actual_cost:.6f}" if actual_cost is not None else "unknown"
    print(f"  Batch lexical unit identification API call completed in {elapsed:.2f}s ({output_chars} output chars, actual cost: {actual_cost_str})")

    return json.loads(output_text), LUI_LLM, processing_timestamp


def process_lui_batches(notes_needing_lui: List[AnkiNote], cache: MACache, language_name: str, language_code: str = ""):
    """Process notes in batches for lexical unit identification"""

    # Capture timestamp at the start of LUI processing
    processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    total_batches = (len(notes_needing_lui) + BATCH_SIZE - 1) // BATCH_SIZE
    failing_notes = []

    for i in range(0, len(notes_needing_lui), BATCH_SIZE):
        batch = notes_needing_lui[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        print(f"\nProcessing lexical unit identification batch {batch_num}/{total_batches} ({len(batch)} notes)")

        try:
            batch_results, model_used, timestamp = make_batch_lui_call(batch, processing_timestamp, language_name, language_code)

            for note in batch:
                if note.uid in batch_results:
                    lui_data = batch_results[note.uid]

                    # Create LUI result for caching
                    lui_result = {
                        "lemma": lui_data.get("lemma", ""),
                        "part_of_speech": lui_data.get("part_of_speech", ""),
                        "aspect": lui_data.get("aspect", ""),
                        "original_form": lui_data.get("original_form", note.kindle_word),
                        "unit_type": lui_data.get("unit_type", "lemma")
                    }

                    # Save to cache
                    cache.set(note.uid, lui_result, model_used, timestamp)

                    # Apply to note
                    note.expression = lui_result["lemma"]
                    note.part_of_speech = lui_result["part_of_speech"]
                    note.aspect = lui_result["aspect"]
                    note.original_form = lui_result["original_form"]
                    note.unit_type = lui_result["unit_type"]

                    print(f"  SUCCESS - identified {note.kindle_word} → lemma: {note.expression}, pos: {note.part_of_speech}")
                else:
                    print(f"  FAILED - no LUI result for {note.kindle_word}")
                    failing_notes.append(note)

        except Exception as e:
            print(f"  BATCH FAILED - {str(e)}")
            failing_notes.extend(batch)

    if len(failing_notes) > 0:
        print(f"{len(failing_notes)} notes failed LLM lexical unit identification.")
        print("All successful identification results already saved to cache. Running script again usually fixes the issue. Exiting.")
        exit()


def process_notes_with_llm_lui(notes: List[AnkiNote], source_language_code: str, target_language_code: str, ignore_cache=False, use_test_cache=False):
    """Process lexical unit identification for a list of notes using LLM"""

    print(f"\nStarting lexical unit identification (LLM) for {source_language_code}...")

    language_pair_code = f"{source_language_code}-{target_language_code}"
    language_name = get_language_name_in_english(source_language_code)

    cache_suffix = language_pair_code + "_llm"
    if use_test_cache:
        cache_suffix += "_test"

    cache = MACache(cache_suffix=cache_suffix)

    # Filter notes that need LUI and collect cached results
    notes_needing_lui = []

    if not ignore_cache:
        cached_count = 0

        for note in notes:
            cached_result = cache.get(note.uid)
            if cached_result:
                cached_count += 1
                note.expression = cached_result.get('lemma', '')
                note.part_of_speech = cached_result.get('part_of_speech', '')
                note.aspect = cached_result.get('aspect', '')
                note.original_form = cached_result.get('original_form', note.kindle_word)
                note.unit_type = cached_result.get('unit_type', 'lemma')
            else:
                notes_needing_lui.append(note)

        print(f"Found {cached_count} cached identifications, {len(notes_needing_lui)} notes need LLM lexical unit identification")
    else:
        notes_needing_lui = notes
        print("Ignoring cache as per user request. Fresh identifications will be generated.")

    if not notes_needing_lui:
        print(f"{language_name} lexical unit identification (LLM) completed (all from cache).")
        return

    if len(notes_needing_lui) > 100:
        result = input(f"\nDo you want to proceed with LLM lexical unit identification API calls for {len(notes_needing_lui)} notes? (y/n): ").strip().lower()
        if result != 'y' and result != 'yes':
            print("LLM lexical unit identification process aborted by user.")
            exit()

    # Process notes in batches
    process_lui_batches(notes_needing_lui, cache, language_name, source_language_code)

    print(f"{language_name} lexical unit identification (LLM) completed.")


if __name__ == "__main__":
    # Example usage and testing
    test_notes = [
        AnkiNote(
            word="się",
            stem="się",
            usage="Boi się ciemności.",
            language="pl",
            book_name="Test Book",
            position="123-456",
            timestamp="2024-01-01T12:00:00Z"
        ),
        AnkiNote(
            word="corriendo",
            stem="corriendo", 
            usage="El niño está corriendo en el parque.",
            language="es",
            book_name="Test Book",
            position="789-1011",
            timestamp="2024-01-01T12:05:00Z"
        ),
        AnkiNote(
            word="sich",
            stem="sich",
            usage="Er freut sich über das Geschenk.",
            language="de",
            book_name="Test Book", 
            position="1213-1415",
            timestamp="2024-01-01T12:10:00Z"
        )
    ]

    # Test with different languages
    for lang_code in ["pl", "es", "de"]:
        lang_notes = [note for note in test_notes if note.kindle_language == lang_code]
        if lang_notes:
            print(f"\n=== Testing {lang_code} ===")
            process_notes_with_llm_lui(lang_notes, lang_code, "en", ignore_cache=False, use_test_cache=True)

            for note in lang_notes:
                print(f"Word: {note.kindle_word}")
                print(f"Sentence: {note.kindle_usage}")
                print(f"Lemma: {note.expression}")
                print(f"POS: {note.part_of_speech}")
                print(f"Aspect: {note.aspect}")
                print(f"Original Form: {note.original_form}")
                print()

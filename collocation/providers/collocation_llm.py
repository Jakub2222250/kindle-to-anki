import json
import time
from openai import OpenAI
from anki.anki_note import AnkiNote
from collocation.collocation_cache import CollocationCache
from language.language_helper import get_language_name_in_english
from llm.llm_helper import estimate_llm_cost, calculate_llm_cost


# Configuration
BATCH_SIZE = 40
COLLOCATION_LLM = "gpt-5-mini"

# LLM collocation instructions


def get_llm_collocation_instructions(source_language_name: str, target_language_name: str) -> str:
    return f"""For each {source_language_name} word and sentence provided, find common {source_language_name} collocations or phrases that include the inflected input word.

Output JSON as an object where keys are the UIDs and values are objects with:
- "collocations": A JSON list of 0-3 short collocations in {source_language_name} that commonly use the input word form"""


def make_batch_collocation_call(batch_notes, processing_timestamp, source_language_name, target_language_name):
    """Make batch LLM API call for collocations"""
    items_list = []
    for note in batch_notes:
        pos_tag = getattr(note, 'pos_tag', 'unknown')
        items_list.append(f'{{"uid": "{note.uid}", "word": "{note.kindle_word}", "lemma": "{note.expression}", "pos": "{pos_tag}", "sentence": "{note.kindle_usage}"}}')

    items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

    prompt = f"""Find collocations for the following {source_language_name} words and sentences.

Words to analyze:
{items_json}

{get_llm_collocation_instructions(source_language_name, target_language_name)}

Respond with valid JSON. No additional text."""

    input_chars = len(prompt)
    estimate_cost_value = estimate_llm_cost(prompt, len(batch_notes), COLLOCATION_LLM)
    estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"
    print(f"  Making batch collocation API call for {len(batch_notes)} notes ({input_chars} input chars, estimated cost: {estimated_cost_str})...")
    start_time = time.time()

    client = OpenAI()
    response = client.chat.completions.create(
        model=COLLOCATION_LLM,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed = time.time() - start_time
    output_text = response.choices[0].message.content
    output_chars = len(output_text)
    actual_cost = calculate_llm_cost(prompt, output_text, COLLOCATION_LLM)
    actual_cost_str = f"${actual_cost:.6f}" if actual_cost is not None else "unknown"
    print(f"  Batch collocation API call completed in {elapsed:.2f}s ({output_chars} output chars, actual cost: {actual_cost_str})")

    return json.loads(output_text), COLLOCATION_LLM, processing_timestamp


def process_collocation_batches(notes_needing_collocations: list[AnkiNote], cache: CollocationCache, source_language_name: str, target_language_name: str):
    """Process notes in batches for collocation analysis"""

    # Capture timestamp at the start of collocation processing
    processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    total_batches = (len(notes_needing_collocations) + BATCH_SIZE - 1) // BATCH_SIZE
    failing_notes = []

    for i in range(0, len(notes_needing_collocations), BATCH_SIZE):
        batch = notes_needing_collocations[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        print(f"\nProcessing collocation batch {batch_num}/{total_batches} ({len(batch)} notes)")

        try:
            batch_results, model_used, timestamp = make_batch_collocation_call(batch, processing_timestamp, source_language_name, target_language_name)

            for note in batch:
                if note.uid in batch_results:
                    collocation_data = batch_results[note.uid]

                    # Create collocation result for caching
                    collocation_result = {
                        "collocations": collocation_data.get("collocations", [])
                    }

                    # Save to cache
                    cache.set(note.uid, collocation_result, model_used, timestamp)

                    # Apply to note
                    collocations = collocation_result["collocations"]
                    if isinstance(collocations, list):
                        note.collocations = ', '.join(collocations)
                    else:
                        note.collocations = str(collocations)

                    print(f"  SUCCESS - found collocations for {note.kindle_word}")
                else:
                    print(f"  FAILED - no collocation result for {note.kindle_word}")
                    failing_notes.append(note)

        except Exception as e:
            print(f"  BATCH FAILED - {str(e)}")
            failing_notes.extend(batch)
            
    return failing_notes


def generate_collocations_llm(notes: list[AnkiNote], source_language_code: str, target_language_code: str, ignore_cache=False, use_test_cache=False):
    """Generate collocations using LLM"""

    print("\nStarting collocation generation (LLM)...")

    language_pair_code = f"{source_language_code}-{target_language_code}"
    source_language_name = get_language_name_in_english(source_language_code)
    target_language_name = get_language_name_in_english(target_language_code)

    cache_suffix = language_pair_code + "_llm"
    if use_test_cache:
        cache_suffix += "_test"
    cache = CollocationCache(cache_suffix=cache_suffix)
    if not ignore_cache:
        print(f"Loaded collocation cache with {len(cache.cache)} entries")
    else:
        print("Ignoring cache as per user request. Fresh collocations will be generated.")

    # Filter notes that need collocation analysis and collect cached results
    notes_needing_collocations = []
    cached_count = 0

    for note in notes:
        if not note.kindle_usage or not note.expression:
            continue

        cached_result = cache.get(note.uid)
        if cached_result:
            cached_count += 1
            collocations = cached_result.get('collocations', [])
            if isinstance(collocations, list):
                note.collocations = ', '.join(collocations)
            else:
                note.collocations = str(collocations)
        else:
            notes_needing_collocations.append(note)

    print(f"Found {cached_count} cached collocations, {len(notes_needing_collocations)} notes need LLM collocation analysis")

    if not notes_needing_collocations:
        print(f"{source_language_name} collocation generation (LLM) completed (all from cache).")
        return

    # Process notes in batches with retry logic
    MAX_RETRIES = 1
    retries = 0
    failing_notes = process_collocation_batches(notes_needing_collocations, cache, source_language_name, target_language_name)

    while len(failing_notes) > 0:
        print(f"{len(failing_notes)} notes failed LLM collocation analysis.")
        
        if retries >= MAX_RETRIES:
            print("All successful collocation results already saved to cache. Running script again usually fixes the issue. Exiting.")
            exit()
        
        if retries < MAX_RETRIES:
            retries += 1
            print(f"Retrying {len(failing_notes)} failed notes (attempt {retries} of {MAX_RETRIES})...")
            failing_notes = process_collocation_batches(failing_notes, cache, source_language_name, target_language_name)

    print(f"{source_language_name} collocation generation (LLM) completed.")


if __name__ == "__main__":
    # Example usage and testing
    notes = [
        AnkiNote(
            word="dzieci",
            stem="dziecko",
            usage="Dzieci bawią się na placu zabaw.",
            language="pl",
            book_name="Sample Book",
            position="123-456",
            timestamp="2024-01-01T12:00:00Z"
        ),
        AnkiNote(
            word="książki",
            stem="książka",
            usage="Książki leżą na półce w bibliotece.",
            language="pl",
            book_name="Sample Book",
            position="789-1011",
            timestamp="2024-01-01T12:05:00Z"
        )
    ]

    generate_collocations_llm(notes, "pl", "en", ignore_cache=False, use_test_cache=True)

    print()
    for note in notes:
        print(f"Word: {note.kindle_word}")
        print(f"Collocations: {note.collocations}")
        print("---")

import json
import time
from openai import OpenAI
from anki.anki_note import AnkiNote
from wsd.wsd_cache import WSDCache
from llm.llm_helper import estimate_llm_cost, calculate_llm_cost

# Configuration
BATCH_SIZE = 30
BATCH_LLM = "gpt-5"

# Common LLM instructions


def get_wsd_llm_instructions(source_language_name: str, target_language_name: str) -> str:
    return f"""output JSON with:
1. definition: {target_language_name} definition of the lemma form (not the inflected input word), with the meaning determined by how the input word is used in the input sentence. Consider the part of speech when providing a concise dictionary-style gloss for the base form.
2. original_language_definition: {source_language_name} definition of the lemma form (not the inflected input word), with the meaning determined by how the input word is used in the input sentence. Consider the part of speech when providing a concise dictionary-style gloss for the base form.
3. cloze_deletion_score: Provide a score from 0 to 10 indicating how suitable the input sentence is for cloze deletion in Anki based on it and the input word where 0 means not suitable at all, 10 means very suitable"""


def make_batch_llm_call(batch_notes, processing_timestamp, source_language_name, target_language_name):
    """Make batch LLM API call for multiple notes"""
    items_list = []
    for note in batch_notes:
        pos_tag = getattr(note, 'pos_tag', 'unknown')
        items_list.append(f'{{"uid": "{note.uid}", "word": "{note.kindle_word}", "lemma": "{note.expression}", "pos": "{pos_tag}", "sentence": "{note.kindle_usage}"}}')

    items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

    prompt = f"""Process the following Polish words and sentences. For each item, provide analysis in the specified format.

Items to process:
{items_json}

For each item, {get_wsd_llm_instructions(source_language_name, target_language_name)}

Respond with valid JSON as an object where keys are the UIDs and values are the analysis objects. No additional text."""

    input_chars = len(prompt)
    estimate_cost_value = estimate_llm_cost(prompt, len(batch_notes), BATCH_LLM)
    estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"
    print(f"  Making batch API call for {len(batch_notes)} notes ({input_chars} input chars, estimated cost: {estimated_cost_str})...")
    start_time = time.time()

    client = OpenAI()
    response = client.chat.completions.create(
        model=BATCH_LLM,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed = time.time() - start_time
    output_text = response.choices[0].message.content
    output_chars = len(output_text)
    actual_cost = calculate_llm_cost(prompt, output_text, BATCH_LLM)
    actual_cost_str = f"${actual_cost:.6f}" if actual_cost is not None else "unknown"
    print(f"  Batch API call completed in {elapsed:.2f}s ({output_chars} output chars, actual cost: {actual_cost_str})")

    return json.loads(output_text), BATCH_LLM, processing_timestamp


def process_notes_in_batches(notes_needing_llm: list[AnkiNote], cache: WSDCache, source_language_name, target_language_name):

    # Capture timestamp at the start of LLM processing
    processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    total_batches = (len(notes_needing_llm) + BATCH_SIZE - 1) // BATCH_SIZE
    failing_notes = []
    for i in range(0, len(notes_needing_llm), BATCH_SIZE):
        batch = notes_needing_llm[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        print(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} notes)")

        try:
            batch_results, model_used, timestamp = make_batch_llm_call(batch, processing_timestamp, source_language_name, target_language_name)

            for note in batch:
                if note.uid in batch_results:
                    llm_data = batch_results[note.uid]
                    cache.set(note.uid, llm_data, model_used, timestamp)
                    note.apply_wsd_results(llm_data)
                    print(f"  SUCCESS - enriched {note.kindle_word}")
                else:
                    print(f"  FAILED - no result for {note.kindle_word}")
                    failing_notes.append(note)

        except Exception as e:
            print(f"  BATCH FAILED - {str(e)}")
            failing_notes.extend(batch)
            
    return failing_notes

    


def provide_wsd_with_llm(notes: list[AnkiNote], source_language_name, target_language_name, ignore_cache=False, use_test_cache=False):
    """Process Word Sense Disambiguation via LLM for all notes"""

    print("\nStarting Word Sense Disambiguation via LLM process...")

    language_pair_code = f"{source_language_name}-{target_language_name}"
    cache_suffix = language_pair_code + "_llm"
    if use_test_cache:
        cache_suffix += "_test"
    cache = WSDCache(cache_suffix=cache_suffix)

    # Phase 1: Collect notes that need Word Sense Disambiguation via LLM
    notes_needing_llm = []

    if not ignore_cache:
        cached_count = 0

        for note in notes:
            if not note.kindle_usage or not note.expression:
                continue

            cached_result = cache.get(note.uid)
            if cached_result:
                cached_count += 1
                note.apply_wsd_results(cached_result)
            else:
                notes_needing_llm.append(note)

        print(f"Found {cached_count} cached results, {len(notes_needing_llm)} notes need LLM calls")
    else:
        notes_needing_llm = notes
        print("Ignoring cache as per user request. Fresh results will be generated.")

    if not notes_needing_llm:
        return

    # Phase 2: Process notes in batches
    MAX_RETRIES = 1
    retries = 0
    failing_notes = process_notes_in_batches(notes_needing_llm, cache, source_language_name, target_language_name)

    while len(failing_notes) > 0:
        print(f"{len(failing_notes)} notes failed LLM based Word Sense Disambiguation.")
        
        if retries >= MAX_RETRIES:
            print("All successful LLM results already saved to cache. Running script again usually fixes the issue. Exiting.")
            exit()
        
        if retries < MAX_RETRIES:
            retries += 1
            print(f"Retrying {len(failing_notes)} failed notes (attempt {retries} of {MAX_RETRIES})...")
            failing_notes = process_notes_in_batches(failing_notes, cache, source_language_name, target_language_name)

    print("Word Sense Disambiguation via LLM process completed.")




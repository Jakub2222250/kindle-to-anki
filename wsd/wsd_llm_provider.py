import json
import time
from openai import OpenAI
from anki.anki_note import AnkiNote
from wsd.wsd_cache import WSDCache

# Configuration
BATCH_SIZE = 40
BATCH_LLM = "gpt-5"
FALLBACK_LLM = "gpt-5"

# Common LLM instructions
LLM_ANALYSIS_INSTRUCTIONS = """output JSON with:
1. definition: English definition of the lemma form (not the inflected input word), with the meaning determined by how the input word is used in the input sentence. Consider the part of speech when providing a concise dictionary-style gloss for the base form.
2. collocations: Any common Polish collocations or phrases that include the inflected input word as a JSON list of 0-3 short collocations in Polish
3. original_language_definition: Polish definition of the lemma form (not the inflected input word), with the meaning determined by how the input word is used in the input sentence. Consider the part of speech when providing a concise dictionary-style gloss for the base form.
4. cloze_deletion_score: Provide a score from 0 to 10 indicating how suitable the input sentence is for cloze deletion in Anki based on it and the input word where 0 means not suitable at all, 10 means very suitable"""


def estimate_cost(input_chars, notes_count, model):
    pricing = {
        "gpt-5": {"input_cost_per_1m_tokens": 1.25, "output_cost_per_1m_tokens": 10.00},
        "gpt-4.1": {"input_cost_per_1m_tokens": 2.00, "output_cost_per_1m_tokens": 8.00},
        "gpt-5-mini": {"input_cost_per_1m_tokens": 0.25, "output_cost_per_1m_tokens": 2.00},
    }

    ESTIMATED_CHARS_PER_NOTE = 400  # Reduced since we no longer include translation

    input_tokens = input_chars / 4
    output_tokens = ESTIMATED_CHARS_PER_NOTE * notes_count / 4

    if model not in pricing:
        return None

    input_cost = (input_tokens / 1_000_000) * pricing[model]["input_cost_per_1m_tokens"]
    output_cost = (output_tokens / 1_000_000) * pricing[model]["output_cost_per_1m_tokens"]

    return input_cost + output_cost


def make_batch_llm_call(batch_notes, processing_timestamp):
    """Make batch LLM API call for multiple notes"""
    items_list = []
    for note in batch_notes:
        pos_tag = getattr(note, 'pos_tag', 'unknown')
        items_list.append(f'{{"uid": "{note.uid}", "word": "{note.kindle_word}", "lemma": "{note.expression}", "pos": "{pos_tag}", "sentence": "{note.kindle_usage}"}}')

    items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

    prompt = f"""Process the following Polish words and sentences. For each item, provide analysis in the specified format.

Items to process:
{items_json}

For each item, {LLM_ANALYSIS_INSTRUCTIONS}

Respond with valid JSON as an object where keys are the UIDs and values are the analysis objects. No additional text."""

    input_chars = len(prompt)
    estimate_cost_value = estimate_cost(input_chars, len(batch_notes), BATCH_LLM)
    estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"
    print(f"  Making batch API call for {len(batch_notes)} notes ({input_chars} input chars, estimated cost: {estimated_cost_str})...")
    start_time = time.time()

    client = OpenAI()
    response = client.chat.completions.create(
        model=BATCH_LLM,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed = time.time() - start_time
    output_chars = len(response.choices[0].message.content)
    print(f"  Batch API call completed in {elapsed:.2f}s ({output_chars} output chars)")

    return json.loads(response.choices[0].message.content), BATCH_LLM, processing_timestamp


def process_notes_in_batches(notes_needing_llm: list[AnkiNote], cache: WSDCache):

    # Capture timestamp at the start of LLM processing
    processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    total_batches = (len(notes_needing_llm) + BATCH_SIZE - 1) // BATCH_SIZE
    failing_notes = []
    for i in range(0, len(notes_needing_llm), BATCH_SIZE):
        batch = notes_needing_llm[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        print(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} notes)")

        try:
            batch_results, model_used, timestamp = make_batch_llm_call(batch, processing_timestamp)

            for note in batch:
                if note.uid in batch_results:
                    llm_data = batch_results[note.uid]
                    cache.set(note.uid, llm_data, model_used, timestamp)
                    note.apply_llm_enrichment(llm_data)
                    print(f"  SUCCESS - enriched {note.kindle_word}")
                else:
                    print(f"  FAILED - no result for {note.kindle_word}")
                    failing_notes.append(note)

        except Exception as e:
            print(f"  BATCH FAILED - {str(e)}")
            failing_notes.extend(batch)

    if len(failing_notes) > 0:
        print(f"{len(failing_notes)} notes failed LLM enrichment.")
        print("All successful LLM results already saved to cache. Running script again usually fixes the issue. Exiting.")
        exit()


def provide_word_sense_disambiguation(notes: list[AnkiNote], source_language_code: str, target_language_code: str):
    """Process LLM enrichment for all notes"""

    print("\nStarting LLM enrichment process...")

    language_pair_code = source_language_code + "-" + target_language_code
    cache_suffix = language_pair_code + "_llm"

    cache = WSDCache(cache_suffix=cache_suffix)
    print(f"\nLoaded LLM cache with {len(cache.cache)} entries")

    # Phase 1: Collect notes that need LLM enrichment
    notes_needing_llm = []
    cached_count = 0

    for note in notes:
        if not note.kindle_usage or not note.expression:
            continue

        cached_result = cache.get(note.uid)
        if cached_result:
            cached_count += 1
            note.apply_llm_enrichment(cached_result)
        else:
            notes_needing_llm.append(note)

    print(f"Found {cached_count} cached results, {len(notes_needing_llm)} notes need LLM calls")

    if not notes_needing_llm:
        return

    if len(notes_needing_llm) > 200:
        result = input(f"\nDo you want to proceed with LLM API calls for {len(notes_needing_llm)} notes? (y/n): ").strip().lower()
        if result != 'y' and result != 'yes':
            print("LLM enrichment process aborted by user.")
            exit()

    # Phase 2: Process notes in batches
    process_notes_in_batches(notes_needing_llm, cache)

    print("LLM enrichment process completed.")


if __name__ == "__main__":

    # Integration test of LLM enrichment - focus on plural forms with singular lemmas
    test_cases = [
        {
            'kindle_word': 'dzieci',  # plural
            'lemma': 'dziecko',       # singular
            'sentence': 'Dzieci bawią się na placu zabaw.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'koty',    # plural
            'lemma': 'kot',           # singular
            'sentence': 'Koty lubią spać w słońcu.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'domy',    # plural
            'lemma': 'dom',           # singular
            'sentence': 'Domy na tej ulicy są bardzo stare.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'książki',  # plural
            'lemma': 'książka',       # singular
            'sentence': 'Książki leżą na półce w bibliotece.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'ludzie',  # plural
            'lemma': 'człowiek',      # singular (irregular)
            'sentence': 'Ludzie czekają na autobus.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'oczy',    # plural
            'lemma': 'oko',           # singular
            'sentence': 'Jego oczy błyszczą w ciemności.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'ręce',    # plural
            'lemma': 'ręka',          # singular
            'sentence': 'Mył ręce przed jedzeniem.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'pieniądze',  # plural
            'lemma': 'pieniądz',        # singular
            'sentence': 'Pieniądze leżą na stole.',
            'pos': 'noun'
        }
    ]

    notes = []
    for i, test_case in enumerate(test_cases):
        note = AnkiNote(test_case['kindle_word'], "", test_case['sentence'], "pl", "Test Book", f"loc_{i + 1}", "")
        # Set the lemma form that MA would have provided
        note.expression = test_case['lemma']
        note.pos_tag = test_case['pos']
        notes.append(note)

    print("=" * 80)
    print("LLM ENRICHMENT INTEGRATION TEST")
    print("=" * 80)
    print("Testing plural forms with singular lemmas to assess if definitions match lemma forms")
    print()

    provide_word_sense_disambiguation(notes, "pl_test")

    print("\n" + "=" * 80)
    print("TEST RESULTS FOR MANUAL ASSESSMENT")
    print("=" * 80)

    for i, test_case in enumerate(test_cases):
        note = notes[i]
        print(f"\nTest Case {i + 1}:")
        print(f"  Original word (plural): {note.kindle_word}")
        print(f"  Lemma (singular):       {note.expression}")
        print(f"  Sentence:               {note.kindle_usage}")
        print(f"  Definition:             {note.definition}")
        print(f"  Polish definition:      {note.original_language_hint}")
        print(f"  Cloze score:            {note.cloze_enabled}")
        print("-" * 60)

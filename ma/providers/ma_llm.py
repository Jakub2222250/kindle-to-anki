import json
import time
from typing import List
from openai import OpenAI

from anki.anki_note import AnkiNote
from ma.ma_cache import MACache
from language.language_helper import get_language_name_in_english


# Configuration
BATCH_SIZE = 30
MA_LLM = "gpt-5-mini"


def get_llm_morphological_analysis_instructions(language_name: str) -> str:
    """Get LLM instructions for morphological analysis"""
    return f"""You are a morphological analyzer for {language_name} focused on language learning.

For each word/phrase, provide:
- "lemma": The dictionary form (infinitive for verbs, singular nominative for nouns, etc.)
- "part_of_speech": One of: verb, noun, adj, adv, prep, conj, particle, det, pron, num, interj
- "aspect": For verbs only: "perf" (perfective), "impf" (imperfective), or "" (not applicable/unknown)
- "original_form": The exact form from the sentence that should be learned (may include particles, reflexive pronouns, etc.)

CRITICAL LEARNING-FOCUSED RULES:
1. For reflexive verbs (with reflexive pronouns like się, se, si, etc.): Include the reflexive pronoun in both lemma and original_form if it's essential to the verb's meaning
2. For phrasal verbs and idioms: Include the full phrase if learning the parts separately would be confusing
3. For particles that change meaning: Include them when they're semantically bound to the word
4. Prioritize what a language learner should memorize as a unit, not just grammatical correctness

Examples for different languages:
- Polish "bać się" (to be afraid) → lemma: "bać się", not just "bać"
- Spanish "darse cuenta" (to realize) → lemma: "darse cuenta", not just "dar"
- German "sich freuen" (to be happy) → lemma: "sich freuen", not just "freuen"
- French "se souvenir" (to remember) → lemma: "se souvenir", not just "souvenir"

Consider context to determine if particles belong to the target word or to other words in the sentence."""


def estimate_ma_cost(input_chars, notes_count, model):
    """Estimate cost for morphological analysis API calls"""
    pricing = {
        "gpt-5": {"input_cost_per_1m_tokens": 1.25, "output_cost_per_1m_tokens": 10.00},
        "gpt-4.1": {"input_cost_per_1m_tokens": 2.00, "output_cost_per_1m_tokens": 8.00},
        "gpt-5-mini": {"input_cost_per_1m_tokens": 0.25, "output_cost_per_1m_tokens": 2.00},
    }

    ESTIMATED_CHARS_PER_ANALYSIS = 150

    input_tokens = input_chars / 4
    output_tokens = ESTIMATED_CHARS_PER_ANALYSIS * notes_count / 4

    if model not in pricing:
        return None

    input_cost = (input_tokens / 1_000_000) * pricing[model]["input_cost_per_1m_tokens"]
    output_cost = (output_tokens / 1_000_000) * pricing[model]["output_cost_per_1m_tokens"]

    return input_cost + output_cost


def make_batch_ma_call(batch_notes, processing_timestamp, language_name):
    """Make batch LLM API call for morphological analysis"""
    items_list = []
    for note in batch_notes:
        sentence = note.kindle_usage or note.context_sentence or ""
        items_list.append(f'{{"uid": "{note.uid}", "word": "{note.kindle_word}", "sentence": "{sentence}"}}')

    items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

    prompt = f"""Analyze the morphology of the following {language_name} words in context.

Words to analyze:
{items_json}

{get_llm_morphological_analysis_instructions(language_name)}

Output JSON as an object where keys are the UIDs and values are objects with:
- "lemma": dictionary form
- "part_of_speech": grammatical category
- "aspect": verb aspect ("perf"/"impf"/"")
- "original_form": form to be learned (may include particles/reflexive pronouns)

Respond with valid JSON. No additional text."""

    input_chars = len(prompt)
    estimate_cost_value = estimate_ma_cost(input_chars, len(batch_notes), MA_LLM)
    estimated_cost_str = f"${estimate_cost_value:.6f}" if estimate_cost_value is not None else "unknown cost"
    print(f"  Making batch morphological analysis API call for {len(batch_notes)} notes ({input_chars} input chars, estimated cost: {estimated_cost_str})...")
    start_time = time.time()

    client = OpenAI()
    response = client.chat.completions.create(
        model=MA_LLM,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed = time.time() - start_time
    output_chars = len(response.choices[0].message.content)
    print(f"  Batch morphological analysis API call completed in {elapsed:.2f}s ({output_chars} output chars)")

    return json.loads(response.choices[0].message.content), MA_LLM, processing_timestamp


def process_ma_batches(notes_needing_ma: List[AnkiNote], cache: MACache, language_name: str):
    """Process notes in batches for morphological analysis"""

    # Capture timestamp at the start of MA processing
    processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    total_batches = (len(notes_needing_ma) + BATCH_SIZE - 1) // BATCH_SIZE
    failing_notes = []

    for i in range(0, len(notes_needing_ma), BATCH_SIZE):
        batch = notes_needing_ma[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        print(f"\nProcessing morphological analysis batch {batch_num}/{total_batches} ({len(batch)} notes)")

        try:
            batch_results, model_used, timestamp = make_batch_ma_call(batch, processing_timestamp, language_name)

            for note in batch:
                if note.uid in batch_results:
                    ma_data = batch_results[note.uid]

                    # Create MA result for caching
                    ma_result = {
                        "lemma": ma_data.get("lemma", ""),
                        "part_of_speech": ma_data.get("part_of_speech", ""),
                        "aspect": ma_data.get("aspect", ""),
                        "original_form": ma_data.get("original_form", note.kindle_word)
                    }

                    # Save to cache
                    cache.set(note.uid, ma_result, model_used, timestamp)

                    # Apply to note
                    note.expression = ma_result["lemma"]
                    note.part_of_speech = ma_result["part_of_speech"]
                    note.aspect = ma_result["aspect"]
                    note.original_form = ma_result["original_form"]

                    print(f"  SUCCESS - analyzed {note.kindle_word} → lemma: {note.expression}, pos: {note.part_of_speech}")
                else:
                    print(f"  FAILED - no MA result for {note.kindle_word}")
                    failing_notes.append(note)

        except Exception as e:
            print(f"  BATCH FAILED - {str(e)}")
            failing_notes.extend(batch)

    if len(failing_notes) > 0:
        print(f"{len(failing_notes)} notes failed LLM morphological analysis.")
        print("All successful analysis results already saved to cache. Running script again usually fixes the issue. Exiting.")
        exit()


def process_notes_with_llm_ma(notes: List[AnkiNote], source_language_code: str, target_language_code: str, ignore_cache=False, use_test_cache=False):
    """Process morphological analysis for a list of notes using LLM"""

    print(f"\nStarting morphological analysis (LLM) for {source_language_code}...")

    language_pair_code = f"{source_language_code}-{target_language_code}"
    language_name = get_language_name_in_english(source_language_code)

    cache_suffix = language_pair_code + "_llm"
    if use_test_cache:
        cache_suffix += "_test"

    cache = MACache(cache_suffix=cache_suffix)

    # Filter notes that need MA and collect cached results
    notes_needing_ma = []

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
            else:
                notes_needing_ma.append(note)

        print(f"Found {cached_count} cached analyses, {len(notes_needing_ma)} notes need LLM morphological analysis")
    else:
        notes_needing_ma = notes
        print("Ignoring cache as per user request. Fresh analyses will be generated.")

    if not notes_needing_ma:
        print(f"{language_name} morphological analysis (LLM) completed (all from cache).")
        return

    if len(notes_needing_ma) > 100:
        result = input(f"\nDo you want to proceed with LLM morphological analysis API calls for {len(notes_needing_ma)} notes? (y/n): ").strip().lower()
        if result != 'y' and result != 'yes':
            print("LLM morphological analysis process aborted by user.")
            exit()

    # Process notes in batches
    process_ma_batches(notes_needing_ma, cache, language_name)

    print(f"{language_name} morphological analysis (LLM) completed.")


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
            process_notes_with_llm_ma(lang_notes, lang_code, "en", ignore_cache=False, use_test_cache=True)

            for note in lang_notes:
                print(f"Word: {note.kindle_word}")
                print(f"Sentence: {note.kindle_usage}")
                print(f"Lemma: {note.expression}")
                print(f"POS: {note.part_of_speech}")
                print(f"Aspect: {note.aspect}")
                print(f"Original Form: {note.original_form}")
                print()

import json
from pathlib import Path
from openai import OpenAI
from anki_note import AnkiNote

# Configuration
BATCH_SIZE = 20
BATCH_LLM = "gpt-5-nano"
FALLBACK_LLM = "gpt-5-mini"


class LLMCache:
    def __init__(self, cache_dir="cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "llm_cache.json"

        # Load existing cache
        self.cache = self.load_cache()

    def load_cache(self):
        """Load cache from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}

    def save_cache(self):
        """Save cache to file"""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def get(self, uid):
        """Get cached LLM result for UID"""
        return self.cache.get(uid)

    def set(self, uid, llm_result):
        """Set cached LLM result for UID"""
        self.cache[uid] = llm_result
        self.save_cache()


def make_llm_call(word, stem, usage_context):
    """Make actual LLM API call"""
    prompt = f"""
    Given the Polish sentence: "{usage_context}" and the word "{word}" (lemma: {stem}), 
    output JSON with:
    1. definition: meaning of the word in this specific context (as a concise gloss without making reference to the context)
    2. translation: English translation of the entire sentence
    3. secondary_definitions: The other most known meanings of the lemma (as a list of concise glosses excluding the definition used in this context. Prioritize uniqueness over quantity)
    4. collocations: The most common Polish collocations or phrases that include this word (as a list of 0-4 short phrases in Polish)
    5. original_language_hint: A short Polish definition or explanation that is relevant to how the word is used in the given context (monolingual definition in Polish)

    Respond only with valid JSON, no additional text.
    """

    client = OpenAI()
    response = client.chat.completions.create(
        model=FALLBACK_LLM,
        messages=[{"role": "user", "content": prompt}]
    )

    return json.loads(response.choices[0].message.content)


def make_batch_llm_call(batch_notes):
    """Make batch LLM API call for multiple notes"""
    items_list = []
    for note in batch_notes:
        items_list.append(f'{{"uid": "{note.uid}", "word": "{note.word}", "lemma": "{note.stem}", "sentence": "{note.usage}"}}')

    items_json = "[\n  " + ",\n  ".join(items_list) + "\n]"

    prompt = f"""Process the following Polish words and sentences. For each item, provide analysis in the specified format.

Items to process:
{items_json}

For each item, output JSON with:
1. definition: meaning of the word in this specific context (as a concise gloss without making reference to the context)
2. translation: English translation of the entire sentence
3. secondary_definitions: The other most known meanings of the lemma (as a list of concise glosses excluding the definition used in this context. Prioritize uniqueness over quantity)
4. collocations: The most common Polish collocations or phrases that include this word (as a list of 0-4 short phrases in Polish)
5. original_language_hint: A short Polish definition or explanation that is relevant to how the word is used in the given context (monolingual definition in Polish)

Respond with valid JSON as an object where keys are the UIDs and values are the analysis objects. No additional text."""

    client = OpenAI()
    response = client.chat.completions.create(
        model=BATCH_LLM,
        messages=[{"role": "user", "content": prompt}]
    )

    return json.loads(response.choices[0].message.content)


def process_notes_in_batches(notes_needing_llm: list[AnkiNote], cache: LLMCache):
    total_batches = (len(notes_needing_llm) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(notes_needing_llm), BATCH_SIZE):
        batch = notes_needing_llm[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        print(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} notes)")

        try:
            batch_results = make_batch_llm_call(batch)

            for note in batch:
                if note.uid in batch_results:
                    llm_data = batch_results[note.uid]
                    cache.set(note.uid, llm_data)
                    note.apply_llm_enrichment(llm_data)
                    print(f"  SUCCESS - enriched {note.word}")
                else:
                    print(f"  FAILED - no result for {note.word}")

        except Exception as e:
            print(f"  BATCH FAILED - {str(e)}")
            # Fallback to individual calls for this batch
            for note in batch:
                try:
                    llm_data = make_llm_call(note.word, note.stem, note.usage)
                    cache.set(note.uid, llm_data)
                    note.apply_llm_enrichment(llm_data)
                    print(f"  FALLBACK SUCCESS - enriched {note.word}")
                except Exception as individual_error:
                    print(f"  FALLBACK FAILED - {note.word}: {str(individual_error)}")


def enrich_notes_with_llm(notes: list[AnkiNote], skip=False):
    """Process LLM enrichment for all notes"""
    cache = LLMCache()
    print(f"\nLoaded LLM cache with {len(cache.cache)} entries")

    # Phase 1: Collect notes that need LLM enrichment
    notes_needing_llm = []
    cached_count = 0

    for note in notes:
        if not note.usage or not note.stem:
            continue

        cached_result = cache.get(note.uid)
        if cached_result:
            cached_count += 1
            note.apply_llm_enrichment(cached_result)
        else:
            notes_needing_llm.append(note)

    print(f"Found {cached_count} cached results, {len(notes_needing_llm)} notes need LLM calls")

    if skip:
        print("LLM enrichment skipped as per user request.")

    if not notes_needing_llm:
        return

    # Phase 2: Process notes in batches
    process_notes_in_batches(notes_needing_llm, cache)

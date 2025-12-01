import json
from pathlib import Path
from openai import OpenAI
from anki_note import AnkiNote


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
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

    return json.loads(response.choices[0].message.content)


def process_llm_enrichment(note: AnkiNote, cache, skip=False):
    """Process LLM enrichment for a note using external cache management"""
    if not note.usage or not note.stem:
        print("  LLM enrichment: SKIPPED - no usage context or stem")
        return

    # Check cache first
    cached_result = cache.get(note.uid)
    if cached_result:
        print("  LLM enrichment: CACHE HIT")
        enriched_fields = note.apply_llm_enrichment(cached_result)
        if enriched_fields:
            print(f"  Applied cached enrichment: {', '.join(enriched_fields)}")
        return

    if skip:
        print("  LLM enrichment: SKIPPED by flag")
        return

    # Make LLM call if not cached
    try:
        print("  LLM enrichment: Requesting...")
        llm_data = make_llm_call(note.word, note.stem, note.usage)

        # Cache the result
        cache.set(note.uid, llm_data)

        # Apply enrichment to note
        enriched_fields = note.apply_llm_enrichment(llm_data)

        print(f"  LLM enrichment: SUCCESS - enriched {', '.join(enriched_fields) if enriched_fields else 'no new fields'}")

    except Exception as e:
        print(f"  LLM enrichment: FAILED - {str(e)}")


def batch_llm_enrichment(notes):
    """Process LLM enrichment for all notes"""
    cache = LLMCache()
    print(f"\nLoaded LLM cache with {len(cache.cache)} entries")

    total_notes = len(notes)
    processed_count = 0

    for note in notes:
        processed_count += 1
        print(f"\nLLM [{processed_count}/{total_notes}]")
        process_llm_enrichment(note, cache, skip=False)

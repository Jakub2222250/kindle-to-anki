import sqlite3
import sys
import json
from pathlib import Path
from openai import OpenAI
from anki_note import AnkiNote
import morfeusz2


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

    Respond only with valid JSON, no additional text.
    """

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": prompt}]
    )

    return json.loads(response.choices[0].message.content)


def analyze_with_morfeusz(word):
    """Analyze word with morfeusz2 to get lemma and part of speech"""
    if not morfeusz2 or not word:
        return None, None

    try:
        morf = morfeusz2.Morfeusz()
        analysis = morf.analyse(word.lower())

        if analysis:
            # morfeusz2 returns list of tuples: (start_pos, end_pos, interpretation)
            # where interpretation is a tuple: (lemma, tag, name_list)
            for start_pos, end_pos, interpretation in analysis:
                if interpretation and len(interpretation) >= 2:
                    lemma_raw = interpretation[1]
                    tag = interpretation[2]

                    lemma = lemma_raw.split(':')[0] if ':' in lemma_raw else lemma_raw
                    pos = tag.split(':')[0] if ':' in tag else tag

                    # Map morfeusz2 tags to more readable forms
                    pos_mapping = {
                        'subst': 'noun',
                        'adj': 'adjective', 
                        'adv': 'adverb',
                        'verb': 'verb',
                        'num': 'numeral',
                        'prep': 'preposition',
                        'conj': 'conjunction',
                        'qub': 'particle',
                        'xxx': 'unknown',
                        'ign': 'ignored'
                    }

                    readable_pos = pos_mapping.get(pos, pos)
                    return lemma, readable_pos

    except Exception as e:
        # If morfeusz2 analysis fails, return None values
        print(f"Morfeusz2 analysis error: {e}")
        pass

    return None, None


def process_morfeusz_enrichment(note):
    """Process morfeusz enrichment for a note"""
    if not note.word:
        print("  Morfeusz enrichment: SKIPPED - no word to analyze")
        return

    # Analyze word with morfeusz2
    morfeusz_stem, morfeusz_pos = analyze_with_morfeusz(note.word)

    enriched_fields = []

    # Prioritize morfeusz2 stem if available and different from current stem
    if morfeusz_stem and morfeusz_stem != note.stem:
        note.stem = morfeusz_stem
        enriched_fields.append('stem')

    # Use morfeusz2 POS if available and no POS was previously set
    if morfeusz_pos and not note.part_of_speech:
        note.part_of_speech = morfeusz_pos
        enriched_fields.append('part_of_speech')

    if enriched_fields:
        print(f"  Morfeusz enrichment: SUCCESS - enriched {', '.join(enriched_fields)}")
    else:
        print("  Morfeusz enrichment: No new information")


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


def read_vocab_from_db(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    query = """
    SELECT WORDS.word, WORDS.stem, LOOKUPS.usage, WORDS.lang, 
           BOOK_INFO.title, LOOKUPS.pos
    FROM LOOKUPS
    JOIN WORDS ON LOOKUPS.word_key = WORDS.id
    LEFT JOIN BOOK_INFO ON LOOKUPS.book_key = BOOK_INFO.id
    ORDER BY LOOKUPS.timestamp;
    """

    rows = cur.execute(query).fetchall()
    conn.close()
    return rows


def write_anki_import_file(vocab_data):
    Path("outputs").mkdir(exist_ok=True)
    anki_path = Path("outputs/anki_import.txt")

    # Initialize LLM cache at start of program
    cache = LLMCache()
    print(f"Loaded LLM cache with {len(cache.cache)} entries")

    with open(anki_path, "w", encoding="utf-8") as f:
        f.write("#separator:tab\n")
        f.write("#html:true\n")
        f.write("#tags:kindle_to_anki\n")

        notes = []
        total_words = len([row for row in vocab_data if row[1]])  # Count words with stems
        processed_count = 0

        for word, stem, usage, lang, book_title, pos in vocab_data:
            if stem:
                processed_count += 1
                print(f"\n[{processed_count}/{total_words}]")

                # Create AnkiNote with all data - setup is handled in constructor
                note = AnkiNote(
                    stem=stem,
                    word=word,
                    usage=usage,
                    book_name=book_title,
                    language=lang,
                    pos=pos
                )

                # Process morfeusz enrichment externally after note construction
                process_morfeusz_enrichment(note)

                # Process LLM enrichment externally after note construction
                process_llm_enrichment(note, cache, skip=True)

                notes.append(note)
                f.write(note.to_csv_line())

    print(f"Created Anki import file with {len(notes)} records at {anki_path}")


def export_kindle_vocab():
    # Get script directory and construct path to inputs/vocab.db
    script_dir = Path(__file__).parent
    db_path = script_dir / "inputs" / "vocab.db"

    if not db_path.exists():
        print(f"Error: vocab.db not found at {db_path}")
        print("Please place your Kindle vocab.db file in the 'inputs' folder relative to this script.")
        sys.exit(1)

    vocab_data = read_vocab_from_db(db_path)

    write_anki_import_file(vocab_data)


if __name__ == "__main__":
    export_kindle_vocab()

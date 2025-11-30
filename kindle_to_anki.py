import sqlite3
import sys
import unicodedata
import json
from pathlib import Path
from urllib.parse import quote
from openai import OpenAI

try:
    import morfeusz2
except ImportError:
    print("Warning: morfeusz2 not installed. Install with: pip install morfeusz2")
    morfeusz2 = None


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


class AnkiNote:
    def __init__(self, stem, word, part_of_speech="", 
                 definition="", secondary_definition="", 
                 usage="", context_translation="", 
                 notes="", book_name="", status="raw",
                 language=None, pos=None):
        self.word = word or ""
        self.definition = definition  # Main definition field for CSV output
        self.secondary_definition = secondary_definition
        self.usage = usage or ""
        self.context_translation = context_translation
        self.notes = notes
        self.book_name = book_name or ""
        self.status = status
        self.glosbe_url = ""  # Will be generated later

        # Initialize stem and part_of_speech (may be updated by morfeusz enrichment)
        self.stem = stem or ""
        self.part_of_speech = part_of_speech

        # Generate book abbreviation
        self.book_abbrev = self.generate_book_abbrev(self.book_name)

        # Set location with kindle_ prefix
        self.location = f"kindle_{pos}" if pos else ""

        # Generate UID (needs location to be set first)
        self.uid = self.generate_uid()

        # Generate Glosbe URL
        self.generate_glosbe_url()

        # Format usage text for HTML
        self.format_usage()

        # Set tags based on language and book abbreviation
        self.set_tags(language)

    def apply_llm_enrichment(self, llm_data):
        """Apply LLM enrichment data to the note"""
        if not llm_data:
            return []

        enriched_fields = []
        if llm_data.get('definition'):
            self.definition = llm_data['definition']  # Override glosbe_url with LLM definition
            enriched_fields.append('definition')

        if llm_data.get('translation') and not self.context_translation:
            self.context_translation = llm_data['translation']
            enriched_fields.append('translation')

        if llm_data.get('secondary_definitions') and not self.notes:
            # Join multiple definitions into notes
            if isinstance(llm_data['secondary_definitions'], list):
                self.notes = '; '.join(llm_data['secondary_definitions'])
            else:
                self.notes = str(llm_data['secondary_definitions'])
            enriched_fields.append('secondary_definitions')

        return enriched_fields

    def generate_book_abbrev(self, book_name):
        """Generate book abbreviation for use as tag"""
        if not book_name:
            return "unknown"

        # Remove diacritics by normalizing to NFD and filtering out combining characters
        normalized = unicodedata.normalize('NFD', book_name)
        without_diacritics = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')

        # Convert to lowercase and replace spaces with underscores
        # Remove punctuation except hyphens which become underscores
        result = without_diacritics.lower()
        result = result.replace('-', '_')

        # Remove other punctuation
        punctuation_to_remove = '.,!?;:"()[]{}'
        for punct in punctuation_to_remove:
            result = result.replace(punct, '')

        # Replace spaces with underscores and clean up multiple underscores
        result = result.replace(' ', '_')

        # Remove multiple consecutive underscores
        while '__' in result:
            result = result.replace('__', '_')

        # Remove leading/trailing underscores
        result = result.strip('_')

        return result if result else "unknown"

    def generate_uid(self):
        """Generate unique ID based on stem, book_abbrev, and location"""
        # Normalize stem part similar to book_abbrev
        stem_normalized = unicodedata.normalize('NFD', self.stem or "unknown")
        stem_part = ''.join(char for char in stem_normalized if unicodedata.category(char) != 'Mn')[:10]
        stem_part = stem_part.lower().replace(' ', '_')
        location_part = str(self.location).replace('kindle_', '') if self.location else "0"
        return f"{stem_part}_{self.book_abbrev}_{location_part}"

    def generate_glosbe_url(self, language="pl", target_language="en"):
        """Generate Glosbe URL for the stem word and set as backup definition"""
        if self.stem:
            encoded_word = quote(self.stem.strip().lower())
            self.glosbe_url = f"https://glosbe.com/{language}/{target_language}/{encoded_word}"

            # Set glosbe_url as backup definition if no definition exists
            if not self.definition:
                self.definition = self.glosbe_url

    def format_usage(self):
        """Format usage text for HTML display"""
        if self.usage:
            self.usage = self.usage.replace('\n', '<br>').replace('\r', '')

    def set_tags(self, language=None):
        """Set tags based on language and book abbreviation"""
        base_tags = ["kindle_to_anki"]

        if language:
            base_tags.append(language)

        if self.book_abbrev and self.book_abbrev != "unknown":
            base_tags.append(self.book_abbrev)

        self.tags = " ".join(base_tags)

    def to_csv_line(self):
        """Convert the note to a tab-separated CSV line"""
        return f"{self.uid}\t{self.stem}\t{self.word}\t{self.part_of_speech}\t{self.definition}\t{self.secondary_definition}\t{self.usage}\t{self.context_translation}\t{self.notes}\t{self.book_name}\t{self.location}\t{self.status}\t{self.tags}\n"


def make_llm_call(word, stem, usage_context):
    """Make actual LLM API call"""
    prompt = f"""
    Given the Polish sentence: "{usage_context}" and the word "{word}" (lemma: {stem}), 
    output JSON with:
    1. definition: meaning of the word in this specific context
    2. translation: English translation of the entire sentence
    3. secondary_definitions: other known senses/meanings of the lemma (as a list)

    Respond only with valid JSON, no additional text.
    """

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
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
                    lemma = interpretation[0]
                    tag = interpretation[1]

                    # Extract main POS from tag (first part before colon)
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


def process_llm_enrichment(note, cache):
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
                process_llm_enrichment(note, cache)

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

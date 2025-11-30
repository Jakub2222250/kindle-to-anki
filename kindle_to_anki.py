import sqlite3
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote


class AnkiNote:
    def __init__(self, stem, word, part_of_speech="part_of_speech_not_set", 
                 glosbe_url="", secondary_definition="secondary_definition_not_set", 
                 usage="", context_translation="context_translation_not_set", 
                 notes="notes_not_set", book_name="", location="", status="raw",
                 language=None, pos=None):
        self.stem = stem or ""
        self.word = word or ""
        self.part_of_speech = part_of_speech
        self.glosbe_url = glosbe_url
        self.secondary_definition = secondary_definition
        self.usage = usage or ""
        self.context_translation = context_translation
        self.notes = notes
        self.book_name = book_name or ""
        self.status = status

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
        """Generate unique ID based on stem, book_abbrev, location, and timestamp"""
        timestamp = int(time.time())
        # Normalize stem part similar to book_abbrev
        stem_normalized = unicodedata.normalize('NFD', self.stem or "unknown")
        stem_part = ''.join(char for char in stem_normalized if unicodedata.category(char) != 'Mn')[:10]
        stem_part = stem_part.lower().replace(' ', '_')
        location_part = str(self.location).replace('kindle_', '') if self.location else "0"
        return f"{stem_part}_{self.book_abbrev}_{location_part}_{timestamp}"

    def generate_glosbe_url(self, language="pl", target_language="en"):
        """Generate Glosbe URL for the stem word"""
        if self.stem:
            encoded_word = quote(self.stem.strip().lower())
            self.glosbe_url = f"https://glosbe.com/{language}/{target_language}/{encoded_word}"

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
        return f"{self.uid}\t{self.stem}\t{self.word}\t{self.part_of_speech}\t{self.glosbe_url}\t{self.secondary_definition}\t{self.usage}\t{self.context_translation}\t{self.notes}\t{self.book_name}\t{self.location}\t{self.status}\t{self.tags}\n"


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

    with open(anki_path, "w", encoding="utf-8") as f:
        f.write("#separator:tab\n")
        f.write("#html:true\n")
        f.write("#tags:kindle_to_anki\n")

        notes = []
        for word, stem, usage, lang, book_title, pos in vocab_data:
            if stem:
                # Create AnkiNote with all data - setup is handled in constructor
                note = AnkiNote(
                    stem=stem,
                    word=word,
                    usage=usage,
                    book_name=book_title,
                    language=lang,
                    pos=pos
                )

                notes.append(note)
                f.write(note.to_csv_line())

    print(f"Created Anki import file with {len(notes)} records at {anki_path}")


def export_kindle_vocab(db_path):
    vocab_data = read_vocab_from_db(db_path)
    write_anki_import_file(vocab_data)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python kindle_to_anki.py /path/to/vocab.db")
        sys.exit(1)

    export_kindle_vocab(sys.argv[1])

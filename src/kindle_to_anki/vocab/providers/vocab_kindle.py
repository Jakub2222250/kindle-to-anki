# NOTE: This file will be deleted soon. 
# It has been replaced by runtime_kindle.py in tasks/vocab/
# which follows the new runtime architecture pattern.

import sqlite3
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from anki.anki_note import AnkiNote


class KindleVocabProvider:
    """Kindle vocab.db provider for vocabulary data"""
    
    def __init__(self):
        # Project paths
        self.PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
        self.DATA_DIR = self.PROJECT_ROOT / "data"
        self.INPUTS_DIR = self.DATA_DIR / "inputs"
        self.OUTPUTS_DIR = self.DATA_DIR / "outputs"
    
    def get_kindle_vocab_count(self, db_path, timestamp=None):
        """Get count of kindle vocab builder entries available for import"""
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        if timestamp:
            query = """
            SELECT COUNT(*) FROM LOOKUPS
            JOIN WORDS ON LOOKUPS.word_key = WORDS.id
            WHERE WORDS.stem IS NOT NULL AND LOOKUPS.timestamp > ?
            """
            new_count = cur.execute(query, (timestamp,)).fetchone()[0]
        else:
            new_count = None

        # Get total count
        total_query = """
        SELECT COUNT(*) FROM LOOKUPS
        JOIN WORDS ON LOOKUPS.word_key = WORDS.id
        WHERE WORDS.stem IS NOT NULL
        """
        total_count = cur.execute(total_query).fetchone()[0]

        conn.close()
        return new_count, total_count

    def handle_incremental_import_choice(self, db_path, last_timestamp):
        """Handle user choice for incremental vs full import"""
        new_count, total_count = self.get_kindle_vocab_count(db_path, last_timestamp)

        last_time = datetime.fromtimestamp(last_timestamp / 1000)

        print(f"\nFound previous import timestamp: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"New kindle vocab builder entries since last import: {new_count}")
        print(f"Total kindle vocab builder entries available: {total_count}")

        print("Importing only new kindle vocab builder entries...")
        return self.read_vocab_from_db(db_path, last_timestamp)

    def read_vocab_from_db(self, db_path, timestamp=None):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        if timestamp:
            query = """
            SELECT WORDS.word, WORDS.stem, LOOKUPS.usage, WORDS.lang, 
                   BOOK_INFO.title, LOOKUPS.pos, LOOKUPS.timestamp
            FROM LOOKUPS
            JOIN WORDS ON LOOKUPS.word_key = WORDS.id
            LEFT JOIN BOOK_INFO ON LOOKUPS.book_key = BOOK_INFO.id
            WHERE LOOKUPS.timestamp > ?
            ORDER BY LOOKUPS.timestamp;
            """
            rows = cur.execute(query, (timestamp,)).fetchall()
        else:
            query = """
            SELECT WORDS.word, WORDS.stem, LOOKUPS.usage, WORDS.lang, 
                   BOOK_INFO.title, LOOKUPS.pos, LOOKUPS.timestamp
            FROM LOOKUPS
            JOIN WORDS ON LOOKUPS.word_key = WORDS.id
            LEFT JOIN BOOK_INFO ON LOOKUPS.book_key = BOOK_INFO.id
            ORDER BY LOOKUPS.timestamp;
            """
            rows = cur.execute(query).fetchall()

        conn.close()
        return rows

    def get_vocab_db(self):
        """Get vocab.db file, copying from Kindle device if possible"""
        # Attempt to copy vocab.db via batch script call
        print("\nAttempting to copy vocab.db from Kindle device...")

        try:
            copy_vocab_script = Path(__file__).parent.parent.parent / "copy_vocab.bat"
            retcode = subprocess.run([str(copy_vocab_script)], check=True).returncode
        except subprocess.CalledProcessError as e:
            retcode = 1

        if retcode != 0:
            print(f"Error: Failed to copy vocab.db from Kindle device. Continuing.")
        else:
            # Overwrite vocab.db in inputs/ with vocab_powershell_copy.db
            self.INPUTS_DIR.mkdir(parents=True, exist_ok=True)
            src_db = self.INPUTS_DIR / "vocab_powershell_copy.db"
            dest_db = self.INPUTS_DIR / "vocab.db"
            src_db.replace(dest_db)

            print(f'vocab.db copied from Kindle device successfully.')

        # Get path to inputs/vocab.db
        self.INPUTS_DIR.mkdir(parents=True, exist_ok=True)
        db_path = self.INPUTS_DIR / "vocab.db"

        if not db_path.exists():
            print(f"Error: vocab.db not found at {db_path}")
            print("Please place your Kindle vocab.db file in the 'data/inputs' folder at the project root.")
            sys.exit(1)

        return db_path

    def get_latest_vocab_data(self, db_path, last_vocab_entry_timestamp: datetime = None):
        """Get latest vocab data from Kindle database"""
        last_timestamp = last_vocab_entry_timestamp.timestamp() * 1000 if last_vocab_entry_timestamp else None

        # Handle import choice (incremental vs full)
        if last_timestamp:
            kindle_vocab_data = self.handle_incremental_import_choice(db_path, last_timestamp)
        else:
            _, total_count = self.get_kindle_vocab_count(db_path)
            print(f"No previous import found, importing all {total_count} notes...")
            kindle_vocab_data = self.read_vocab_from_db(db_path)

        if not kindle_vocab_data:
            print("No new notes to import.")
            exit()

        # Get the latest timestamp from the vocab data (timestamp is at index 6)
        latest_vocab_entry_timestamp = max(row[6] for row in kindle_vocab_data) if kindle_vocab_data else None

        notes_by_language = self.create_anki_notes(kindle_vocab_data)
        
        return notes_by_language, latest_vocab_entry_timestamp
    
    def create_anki_notes(self, kindle_vocab_data):
        """Create AnkiNotes from vocab_data retrieved from Kindle vocab.db"""
        notes_by_language = {}
        total_words = len([row for row in kindle_vocab_data if row[1]])  # Count words with stems
        processed_count = 0

        for word, stem, usage, lang, book_title, pos, timestamp in kindle_vocab_data:
            if stem:
                processed_count += 1
                # print(f"[{processed_count}/{total_words}] Found word: {word}")

                # Create AnkiNote with all data - setup is handled in constructor
                note = AnkiNote(
                    word=word,
                    stem=stem,
                    usage=usage,
                    language=lang,
                    book_name=book_title,
                    position=pos,
                    timestamp=timestamp
                )

                # Group by language
                if lang not in notes_by_language:
                    notes_by_language[lang] = []
                notes_by_language[lang].append(note)

        return notes_by_language

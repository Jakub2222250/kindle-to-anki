import sqlite3
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import List

from metadata.metdata_manager import MetadataManager
from tasks.collect_candidates.schema import CandidateOutput


class KindleCandidateRuntime:
    """
    Runtime for candidate collection from Kindle vocab.db files.
    """

    def __init__(self):
        # Project paths
        self.PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
        self.DATA_DIR = self.PROJECT_ROOT / "data"
        self.INPUTS_DIR = self.DATA_DIR / "inputs"
        self.OUTPUTS_DIR = self.DATA_DIR / "outputs"

    def collect_candidates(self) -> List[CandidateOutput]:
        """
        Collect candidate data from Kindle database.
        """
        print("\nStarting Kindle candidate collection...")
        
        # Ensure we have the vocab database
        db_path = self.INPUTS_DIR / "vocab.db"
        
        self._ensure_vocab_db(db_path)
        
        metadata_manager = MetadataManager()
        metadata = metadata_manager.load_metadata()
        
        last_timestamp_str = metadata.get("last_vocab_entry_timestamp")
        last_timestamp = datetime.fromisoformat(last_timestamp_str) if last_timestamp_str else None
        
        # Get candidate data based on input parameters
        if last_timestamp:
            vocab_data = self._handle_incremental_import(db_path, last_timestamp)
        else:
            _, total_count = self._get_kindle_vocab_count(db_path)
            print(f"No previous import found, collecting all {total_count} candidates...")
            vocab_data = self._read_vocab_from_db(db_path)

        if not vocab_data:
            print("No new candidates to collect.")
            return []

        # Convert raw data to CandidateOutput objects
        candidate_outputs = []
        total_words = len([row for row in vocab_data if row[1]])  # Count words with stems
        processed_count = 0

        for word, stem, usage, lang, book_title, pos, timestamp in vocab_data:
            if stem:  # Only process words with stems
                processed_count += 1
                # print(f"[{processed_count}/{total_words}] Found candidate: {word}")
                
                candidate_output = CandidateOutput(
                    word=word,
                    stem=stem,
                    usage=usage,
                    language=lang,
                    book_title=book_title,
                    position=pos,
                    timestamp=timestamp
                )
                candidate_outputs.append(candidate_output)

        print(f"Kindle candidate collection completed. Collected {len(candidate_outputs)} candidates.")
        return candidate_outputs

    def _ensure_vocab_db(self, provided_db_path: str) -> Path:
        """Ensure vocab.db is available, copying from Kindle device if needed"""
        db_path = Path(provided_db_path)
        
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
            if src_db.exists():
                src_db.replace(dest_db)
                print(f'vocab.db copied from Kindle device successfully.')
                db_path = dest_db

        # Final check for database existence
        if not db_path.exists():
            print(f"Error: vocab.db not found at {db_path}")
            print("Please place your Kindle vocab.db file in the 'data/inputs' folder at the project root.")
            sys.exit(1)

        return db_path

    def _get_kindle_vocab_count(self, db_path, timestamp=None):
        """Get count of kindle vocab builder entries available for import"""
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        if timestamp:
            query = """
            SELECT COUNT(*) FROM LOOKUPS
            JOIN WORDS ON LOOKUPS.word_key = WORDS.id
            WHERE WORDS.stem IS NOT NULL AND LOOKUPS.timestamp > ?
            """
            timestamp_ms = int(timestamp.timestamp() * 1000)
            new_count = cur.execute(query, (timestamp_ms,)).fetchone()[0]
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

    def _handle_incremental_import(self, db_path, last_timestamp: datetime):
        """Handle incremental import based on timestamp"""
        timestamp_ms = int(last_timestamp.timestamp() * 1000)
        new_count, total_count = self._get_kindle_vocab_count(db_path, last_timestamp)

        print(f"\nFound previous import timestamp: {last_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"New kindle vocab builder entries since last import: {new_count}")
        print(f"Total kindle vocab builder entries available: {total_count}")

        print("Collecting only new kindle vocab builder entries...")
        return self._read_vocab_from_db(db_path, timestamp_ms)

    def _read_vocab_from_db(self, db_path, timestamp=None):
        """Read vocabulary data from the Kindle database"""
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
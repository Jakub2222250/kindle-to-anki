import sqlite3
import subprocess
import sys
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import List

from kindle_to_anki.logging import get_logger
from kindle_to_anki.core.pricing.usage_breakdown import UsageBreakdown
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig

from .schema import CandidateOutput
from kindle_to_anki.metadata.metdata_manager import MetadataManager


class KindleCandidateRuntime:
    """
    Runtime for candidate collection from Kindle vocab.db files.
    """

    id: str = "kindle_candidate_collection"
    display_name: str = "Kindle Candidate Collection Runtime"
    supported_tasks = ["collect_candidates"]
    supported_model_families = []
    supports_batching: bool = True

    def estimate_usage(self, items_count: int, config: RuntimeConfig) -> UsageBreakdown:
        return None

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
        logger = get_logger()
        logger.info("Starting Kindle candidate collection...")

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
            logger.info(f"No previous import found, collecting all {total_count} candidates...")
            vocab_data = self._read_vocab_from_db(db_path)

        if not vocab_data:
            logger.info("No new candidates to collect.")
            return []

        # Convert raw data to CandidateOutput objects
        candidate_outputs = []
        total_words = len([row for row in vocab_data if row[1]])  # Count words with stems
        processed_count = 0

        for word, stem, usage, lang, book_title, pos, timestamp in vocab_data:
            if stem:  # Only process words with stems
                processed_count += 1

                # Generate UID using Kindle-specific formula
                uid = self._generate_uid(word, book_title, pos)

                # Convert epoch ms to datetime
                lookup_time = datetime.fromtimestamp(timestamp / 1000) if timestamp else None

                candidate_output = CandidateOutput(
                    uid=uid,
                    word=word,
                    usage=usage,
                    stem=stem,
                    language=lang,
                    book_title=book_title,
                    position=pos,
                    timestamp=lookup_time
                )
                candidate_outputs.append(candidate_output)

        logger.info(f"Kindle candidate collection completed. Collected {len(candidate_outputs)} candidates.")
        return candidate_outputs

    def _generate_uid(self, word: str, book_title: str, position: str) -> str:
        """Generate unique ID for Kindle vocabulary entry based on word, book, and location."""
        # Normalize word part (remove diacritics, lowercase, limit length)
        word_normalized = unicodedata.normalize('NFD', word or "unknown")
        word_part = ''.join(char for char in word_normalized if unicodedata.category(char) != 'Mn')[:10]
        word_part = word_part.lower().replace(' ', '_')

        # Generate book abbreviation
        book_abbrev = self._generate_book_abbrev(book_title)

        # Location part
        location_part = str(position) if position else "0"

        return f"{word_part}_{book_abbrev}_{location_part}"

    def _generate_book_abbrev(self, book_name: str) -> str:
        """Generate book abbreviation for use in UID and tags."""
        if not book_name:
            return "unknown"

        # Remove diacritics
        normalized = unicodedata.normalize('NFD', book_name)
        without_diacritics = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')

        result = without_diacritics.lower().replace('-', '_')

        # Remove punctuation
        for punct in '.,!?;:"()[]{}':
            result = result.replace(punct, '')

        result = result.replace(' ', '_')

        # Clean up multiple underscores
        while '__' in result:
            result = result.replace('__', '_')

        return result.strip('_') or "unknown"

    def _ensure_vocab_db(self, provided_db_path: str) -> Path:
        """Ensure vocab.db is available, copying from Kindle device if needed"""
        logger = get_logger()
        db_path = Path(provided_db_path)

        # Attempt to copy vocab.db via batch script call
        logger.info("Attempting to copy vocab.db from Kindle device...")

        try:
            copy_vocab_script = Path(__file__).parent.parent.parent / "copy_vocab.bat"
            retcode = subprocess.run([str(copy_vocab_script)], check=True).returncode
        except subprocess.CalledProcessError as e:
            retcode = 1

        if retcode != 0:
            logger.warning(f"Failed to copy vocab.db from Kindle device. Continuing.")
        else:
            # Overwrite vocab.db in inputs/ with vocab_powershell_copy.db
            self.INPUTS_DIR.mkdir(parents=True, exist_ok=True)
            src_db = self.INPUTS_DIR / "vocab_powershell_copy.db"
            dest_db = self.INPUTS_DIR / "vocab.db"
            if src_db.exists():
                src_db.replace(dest_db)
                logger.info(f'vocab.db copied from Kindle device successfully.')
                db_path = dest_db

        # Final check for database existence
        if not db_path.exists():
            logger.error(f"vocab.db not found at {db_path}")
            logger.error("Please place your Kindle vocab.db file in the 'data/inputs' folder at the project root.")
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
        logger = get_logger()
        timestamp_ms = int(last_timestamp.timestamp() * 1000)
        new_count, total_count = self._get_kindle_vocab_count(db_path, last_timestamp)

        logger.info(f"Found previous import timestamp: {last_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"New kindle vocab builder entries since last import: {new_count}")
        logger.trace(f"Total kindle vocab builder entries available: {total_count}")

        logger.info("Collecting only new kindle vocab builder entries...")
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

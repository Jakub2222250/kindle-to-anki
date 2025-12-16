import sqlite3
import subprocess
import sys
import json
import time
from pathlib import Path

from anki.anki_note import AnkiNote
from wsd.llm_enrichment import enrich_notes_with_llm
from ma.morphological_analyzer import process_morphological_enrichment
from pruning.pruning import prune_existing_notes_automatically, prune_existing_notes_by_UID, prune_notes_identified_as_redundant
from anki.anki_connect import AnkiConnect
import datetime


def load_metadata():
    """Load metadata from cache/metadata.json if it exists"""
    script_dir = Path(__file__).parent
    metadata_path = script_dir / "cache" / "metadata.json"

    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print("Warning: Could not read metadata.json, starting fresh")

    return {}


def save_metadata(metadata):
    """Save metadata to cache/metadata.json"""

    print("\nSaving last run time to metadata...")

    script_dir = Path(__file__).parent
    cache_dir = script_dir / "cache"
    cache_dir.mkdir(exist_ok=True)

    metadata_path = cache_dir / "metadata.json"

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved to {metadata_path}")


def save_script_run_timestamp(metadata):
    """Save the current timestamp as script run time to metadata"""
    current_time_ms = int(time.time() * 1000)
    metadata['last_script_run'] = current_time_ms
    save_metadata(metadata)


def get_kindle_vocab_count(db_path, timestamp=None):
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


def handle_incremental_import_choice(db_path, last_timestamp):
    """Handle user choice for incremental vs full import"""
    new_count, total_count = get_kindle_vocab_count(db_path, last_timestamp)

    last_time = datetime.datetime.fromtimestamp(last_timestamp / 1000)

    print(f"\nFound previous import timestamp: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"New kindle vocab builder entries since last import: {new_count}")
    print(f"Total kindle vocab builder entries available: {total_count}")

    print("Importing only new kindle vocab builder entries...")
    return read_vocab_from_db(db_path, last_timestamp)


def save_latest_vocab_builder_entry_timestamp(vocab_data, metadata):
    """Save the max timestamp from current import for future incremental imports"""
    if not vocab_data:
        return

    max_timestamp = max(row[6] for row in vocab_data)  # timestamp is at index 6
    human_readable_time = datetime.datetime.fromtimestamp(max_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
    print(f"\nMax timestamp from this import: {human_readable_time}")

    metadata['last_timestamp_import'] = max_timestamp
    save_metadata(metadata)
    print("Timestamp saved. Future runs will offer to import only newer notes.")


def read_vocab_from_db(db_path, timestamp=None):
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


def create_anki_notes(kindle_vocab_data):
    """Create AnkiNotes from vocab_data with morfeusz enrichment only"""
    notes_by_language = {}
    total_words = len([row for row in kindle_vocab_data if row[1]])  # Count words with stems
    processed_count = 0

    for word, stem, usage, lang, book_title, pos, timestamp in kindle_vocab_data:
        if stem:
            processed_count += 1
            print(f"[{processed_count}/{total_words}] Found word: {word}")

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


def write_anki_import_file(notes, language):
    print("\nWriting Anki import file...")
    Path("outputs").mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    anki_path = Path(f"outputs/{language}_anki_import_{timestamp}.txt")

    # Write notes to file
    with open(anki_path, "w", encoding="utf-8") as f:
        f.write("#separator:tab\n")
        f.write("#html:true\n")
        f.write("#tags:kindle_to_anki\n")

        for note in notes:
            f.write(note.to_csv_line())

    print(f"Created Anki import file with {len(notes)} records at {anki_path}")


def connect_to_anki():
    print("\nChecking AnkiConnect reachability...")
    anki_connect_instance = AnkiConnect()
    if not anki_connect_instance.is_reachable():
        print("AnkiConnect not reachable. Exiting.")
        exit(0)
    print("AnkiConnect is reachable.")
    return anki_connect_instance


def get_vocab_db():
    # Attempt to copy vocab.db via batch script call

    print("Attempting to copy vocab.db from Kindle device...")

    try:
        retcode = subprocess.run(["copy_vocab.bat"], check=True).returncode
    except subprocess.CalledProcessError as e:
        retcode = 1

    if retcode != 0:
        print(f"Error: Failed to copy vocab.db from Kindle device. Continuing.")
    else:
        # Overwrite vocab.db in inputs/ with vocab_powershell_copy.db
        script_dir = Path(__file__).parent
        out_dir = script_dir / "inputs"
        src_db = out_dir / "vocab_powershell_copy.db"
        dest_db = out_dir / "vocab.db"
        src_db.replace(dest_db)

        print(f'vocab.db copied from Kindle device successfully.')

    # Get script directory and construct path to inputs/vocab.db
    script_dir = Path(__file__).parent
    db_path = script_dir / "inputs" / "vocab.db"

    if not db_path.exists():
        print(f"Error: vocab.db not found at {db_path}")
        print("Please place your Kindle vocab.db file in the 'inputs' folder relative to this script.")
        sys.exit(1)

    return db_path


def get_latest_kindle_vocab_data(db_path, metadata):
    last_timestamp = metadata.get('last_timestamp_import')

    # Handle import choice (incremental vs full)
    if last_timestamp:
        kindle_vocab_data = handle_incremental_import_choice(db_path, last_timestamp)
    else:
        _, total_count = get_kindle_vocab_count(db_path)
        print(f"No previous import found, importing all {total_count} notes...")
        kindle_vocab_data = read_vocab_from_db(db_path)

    if not kindle_vocab_data:
        print("No new notes to import.")
        exit()

    return kindle_vocab_data


def get_existing_notes_by_language(anki_connect_instance, lang):
    print("\nChecking for existing notes in Anki...")
    existing_notes = anki_connect_instance.get_notes(language=lang)
    print(f"Retrieved {len(existing_notes)} existing notes from Anki for language: {lang}")
    return existing_notes


def export_kindle_vocab():

    print("Starting Kindle to Anki export process.")

    # Get path to vocab.db
    db_path = get_vocab_db()

    # Load existing metadata
    metadata = load_metadata()

    # Get latest kindle vocab data
    kindle_vocab_data = get_latest_kindle_vocab_data(db_path, metadata)

    # Create Anki notes from kindle vocab data
    notes_by_language = create_anki_notes(kindle_vocab_data)

    # Connect to AnkiConnect
    anki_connect_instance = connect_to_anki()

    for lang, notes in notes_by_language.items():

        # Get existing notes from Anki for this language
        existing_notes = get_existing_notes_by_language(anki_connect_instance, lang)

        # Prune existing notes by UID
        notes = prune_existing_notes_by_UID(notes, existing_notes)

        # Prune notes previously identified as redundant
        notes = prune_notes_identified_as_redundant(notes, cache_suffix=lang)

        # Enrich notes with morphological analysis
        process_morphological_enrichment(notes, lang)

        if not notes:
            print(f"No new notes to process for language: {lang}")
            continue

        # Enrich notes with LLM
        enrich_notes_with_llm(notes, lang)

        # Optionally prune existing notes automatically based on definition similarity
        notes = prune_existing_notes_automatically(notes, existing_notes, cache_suffix=lang)

        if len(notes) == 0:
            print(f"No new notes to add to Anki after pruning for language: {lang}")
            continue

        # Save results to Anki import file and via AnkiConnect
        write_anki_import_file(notes, lang)
        anki_connect_instance.create_notes_batch(notes, lang=lang)

    # Save script run timestamp
    save_script_run_timestamp(metadata)

    # Save timestamp for future incremental imports
    save_latest_vocab_builder_entry_timestamp(kindle_vocab_data, metadata)

    print("\nKindle to Anki export process completed successfully.")


if __name__ == "__main__":
    export_kindle_vocab()

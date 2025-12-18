import sqlite3
import subprocess
import sys
from pathlib import Path

from anki.anki_deck import AnkiDeck
from anki.anki_note import AnkiNote
from collocation.collocation import process_collocation_generation
from metadata.metdata_manager import MetadataManager
from translation.translation import process_context_translation
from wsd.wsd import provide_word_sense_disambiguation
from lexical_unit_identification.lexical_unit_identification import complete_lexical_unit_identification
from pruning.pruning import prune_existing_notes_automatically, prune_existing_notes_by_UID, prune_new_notes_against_eachother, prune_notes_identified_as_redundant
from anki.anki_connect import AnkiConnect
import datetime


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

    print(last_timestamp)

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


def get_anki_decks_by_source_language():
    anki_decks_list = [
        AnkiDeck(
            source_lang_code="pl",
            target_lang_code="en",
            parent_deck_name="Polish Vocab Discovery",
            ready_deck_name="Polish Vocab Discovery::Ready",
            staging_deck_name="Polish Vocab Discovery::Import"
        ),
        AnkiDeck(
            source_lang_code="es",
            target_lang_code="en",
            parent_deck_name="Spanish Vocab Discovery",
            ready_deck_name="Spanish Vocab Discovery::Ready",
            staging_deck_name="Spanish Vocab Discovery::Import"
        )
    ]

    anki_decks_by_source_language = {}
    for deck in anki_decks_list:
        anki_decks_by_source_language[deck.source_lang_code] = deck

    return anki_decks_by_source_language


def export_kindle_vocab():

    print("Starting Kindle to Anki export process.")

    # Get available anki decks by language pair
    anki_decks_by_source_language = get_anki_decks_by_source_language()

    # Get path to vocab.db
    db_path = get_vocab_db()

    # Load existing metadata
    script_dir = Path(__file__).parent
    metadata_manager = MetadataManager(script_dir)
    metadata = metadata_manager.load_metadata()

    # Get latest kindle vocab data
    kindle_vocab_data = get_latest_kindle_vocab_data(db_path, metadata)

    # Create Anki notes from kindle vocab data
    notes_by_language = create_anki_notes(kindle_vocab_data)

    # Connect to AnkiConnect
    anki_connect_instance = connect_to_anki()

    for source_lang_code, notes in notes_by_language.items():

        # Reference to anki deck for metadata
        anki_deck = anki_decks_by_source_language.get(source_lang_code)
        target_lang_code = anki_deck.target_lang_code
        language_pair_code = anki_deck.get_language_pair_code()

        # Get existing notes from Anki for this language
        existing_notes = anki_connect_instance.get_notes(anki_deck)

        # Prune existing notes by UID
        notes = prune_existing_notes_by_UID(notes, existing_notes)

        # Prune notes previously identified as redundant
        notes = prune_notes_identified_as_redundant(notes, cache_suffix=language_pair_code)

        # Enrich notes with morphological analysis
        complete_lexical_unit_identification(notes, source_lang_code, target_lang_code)

        if not notes:
            print(f"No new notes to process for language: {source_lang_code}")
            continue

        # Provide word sense disambiguation via LLM
        provide_word_sense_disambiguation(notes, source_lang_code, target_lang_code, ignore_cache=False)

        # Prune existing notes automatically based on definition similarity
        notes = prune_existing_notes_automatically(notes, existing_notes, cache_suffix=language_pair_code)

        # Prune duplicates new notes leaving the best one
        notes = prune_new_notes_against_eachother(notes)

        if len(notes) == 0:
            print(f"No new notes to add to Anki after pruning for language: {source_lang_code}")
            continue

        # Provide translations
        process_context_translation(notes, source_lang_code, target_lang_code, ignore_cache=False, use_llm=True)

        # Provide collocations
        process_collocation_generation(notes, source_lang_code, target_lang_code, ignore_cache=False)

        # Save results to Anki import file and via AnkiConnect
        write_anki_import_file(notes, source_lang_code)
        anki_connect_instance.create_notes_batch(anki_deck, notes)

    # Save script run timestamp
    metadata_manager.save_script_run_timestamp(metadata)

    # Save timestamp for future incremental imports
    metadata_manager.save_latest_vocab_builder_entry_timestamp(kindle_vocab_data, metadata)

    print("\nKindle to Anki export process completed successfully.")


if __name__ == "__main__":
    export_kindle_vocab()

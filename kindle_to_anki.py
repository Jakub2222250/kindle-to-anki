import sqlite3
import subprocess
import sys
import json
import time
from pathlib import Path
from anki_note import AnkiNote
import morfeusz2
from llm_enrichment import enrich_notes_with_llm
from anki_connect import AnkiConnect
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


def get_card_counts(db_path, timestamp=None):
    """Get count of cards available for import"""
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
    new_count, total_count = get_card_counts(db_path, last_timestamp)

    last_time = datetime.datetime.fromtimestamp(last_timestamp / 1000)

    print(f"Found previous import timestamp: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"New cards since last import: {new_count}")
    print(f"Total cards available: {total_count}")

    response = input(f"Import only {new_count} new cards since last import? (y/n): ").strip().lower()
    if response == 'y' or response == 'yes':
        print("Importing only new notes...")
        return read_vocab_from_db(db_path, last_timestamp)
    else:
        print(f"Importing all {total_count} notes...")
        return read_vocab_from_db(db_path)


def offer_to_save_timestamp(vocab_data, metadata):
    """Offer to save the max timestamp from current import for future incremental imports"""
    if not vocab_data:
        return

    max_timestamp = max(row[6] for row in vocab_data)  # timestamp is at index 6
    print(f"Max timestamp from this import: {max_timestamp}")

    response = input("Save this timestamp for future incremental imports? (y/n): ").strip().lower()
    if response == 'y' or response == 'yes':
        metadata['last_timestamp_import'] = max_timestamp
        save_metadata(metadata)
        print("Timestamp saved. Future runs will offer to import only newer notes.")


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
                        'fin': 'finite verb',
                        'ger': 'gerund',
                        'praet': 'preterite/past tense',
                        'ppas': 'past passive participle',
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
        return

    # Analyze word with morfeusz2
    morfeusz_stem, morfeusz_pos = analyze_with_morfeusz(note.word)

    # Prioritize morfeusz2 stem if available and different from current stem
    if morfeusz_stem and morfeusz_stem != note.stem:
        note.stem = morfeusz_stem

    # Use morfeusz2 POS if available and no POS was previously set
    if morfeusz_pos and not note.part_of_speech:
        note.part_of_speech = morfeusz_pos


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


def create_anki_notes(vocab_data):
    """Create AnkiNotes from vocab_data with morfeusz enrichment only"""
    notes_by_language = {}
    total_words = len([row for row in vocab_data if row[1]])  # Count words with stems
    processed_count = 0

    for word, stem, usage, lang, book_title, pos, timestamp in vocab_data:
        if stem:
            processed_count += 1
            print(f"[{processed_count}/{total_words}] Found word: {word}")

            # Create AnkiNote with all data - setup is handled in constructor
            note = AnkiNote(
                stem=stem,
                word=word,
                usage=usage,
                book_name=book_title,
                language=lang,
                pos=pos,
                timestamp=timestamp
            )

            # Process morfeusz enrichment externally after note construction
            process_morfeusz_enrichment(note)

            # Group by language
            if lang not in notes_by_language:
                notes_by_language[lang] = []
            notes_by_language[lang].append(note)

    return notes_by_language


def prune_existing_notes(notes, anki_connect_instance):
    """Remove notes that already exist in Anki based on UID"""

    if len(notes) == 0:
        return notes

    try:
        # Get existing cards from Anki
        existing_cards = anki_connect_instance.get_deck_cards()
        existing_uids = {card['UID'] for card in existing_cards if card['UID']}

        # Filter out notes that already exist
        new_notes = [note for note in notes if note.uid not in existing_uids]

        pruned_count = len(notes) - len(new_notes)
        if pruned_count > 0:
            print(f"Pruned {pruned_count} notes that already exist in Anki (based on UID)")

        return new_notes

    except Exception as e:
        print(f"Error: Could not check for existing notes in Anki: {e}")
        exit(0)


def write_anki_import_file(notes, language):
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


def export_kindle_vocab():

    anki_connect_instance = AnkiConnect()
    if not anki_connect_instance.is_reachable():
        print("AnkiConnect not reachable. Exiting.")
        exit(0)
    print("AnkiConnect is reachable.")

    # Attempt to copy vocab.db via batch script call
    response = input(f"Copy vocab.db from connected Kindle device? (y/n): ").strip().lower()
    if response == 'y' or response == 'yes':
        result = subprocess.run(["copy_vocab.bat"], check=True)

        if result.returncode != 0:
            print(f"Error: Failed to copy vocab.db from Kindle device with error {result.returncode}.")
            exit(1)
        else:
            print(f'vocab.db copied from Kindle device successfully.')

    # Get script directory and construct path to inputs/vocab.db
    script_dir = Path(__file__).parent
    db_path = script_dir / "inputs" / "vocab.db"

    if not db_path.exists():
        print(f"Error: vocab.db not found at {db_path}")
        print("Please place your Kindle vocab.db file in the 'inputs' folder relative to this script.")
        sys.exit(1)

    # Load existing metadata
    metadata = load_metadata()
    last_timestamp = metadata.get('last_timestamp_import')

    # Handle import choice (incremental vs full)
    if last_timestamp:
        vocab_data = handle_incremental_import_choice(db_path, last_timestamp)
    else:
        _, total_count = get_card_counts(db_path)
        print(f"No previous import found, importing all {total_count} notes...")
        vocab_data = read_vocab_from_db(db_path)

    if not vocab_data:
        print("No new notes to import.")
        return

    notes_by_language = create_anki_notes(vocab_data)

    for lang, notes in notes_by_language.items():
        # Prune existing notes before expensive LLM enrichment
        notes = prune_existing_notes(notes, anki_connect_instance)

        if not notes:
            print(f"No new notes to process for language: {lang}")
            continue

        print(f"Processing {len(notes)} new notes for {lang}...")
        enrich_notes_with_llm(notes, skip=False)
        write_anki_import_file(notes, lang)
        anki_connect_instance.create_notes_batch(notes, lang=lang)

    # Save script run timestamp
    save_script_run_timestamp(metadata)

    # Offer to save timestamp for future incremental imports
    offer_to_save_timestamp(vocab_data, metadata)


if __name__ == "__main__":
    export_kindle_vocab()

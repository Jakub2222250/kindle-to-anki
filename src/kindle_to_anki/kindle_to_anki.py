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
from vocab.vocab import get_vocab_db, get_latest_vocab_data
import datetime
from time import sleep

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INPUTS_DIR = DATA_DIR / "inputs"
OUTPUTS_DIR = DATA_DIR / "outputs"





def create_anki_notes(kindle_vocab_data):
    """Create AnkiNotes from vocab_data retrieved from Kindle vocab.db"""
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
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    anki_path = OUTPUTS_DIR / f"{language}_anki_import_{timestamp}.txt"

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

    # Load existing metadata
    script_dir = Path(__file__).parent
    metadata_manager = MetadataManager(script_dir)
    metadata = metadata_manager.load_metadata()

    # Get latest kindle vocab data
    db_path = get_vocab_db()
    kindle_vocab_data = get_latest_vocab_data(db_path, metadata)

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
        sleep(5)  # Opportunity to read output

        if len(notes) > 100:
            response = input(f"\nYou are about to process {len(notes)} notes for language: {source_lang_code}. Do you want to continue? (y/n): ").strip().lower()
            if response != 'y' and response != 'yes':
                print("Process aborted by user.")
                exit()

        # Enrich notes with lexical unit identification
        complete_lexical_unit_identification(notes, source_lang_code, target_lang_code)
        sleep(5)  # Opportunity to read output

        if not notes:
            print(f"No new notes to process for language: {source_lang_code}")
            continue

        # Provide word sense disambiguation via LLM
        provide_word_sense_disambiguation(notes, source_lang_code, target_lang_code, ignore_cache=False)
        sleep(5)  # Opportunity to read output

        # Prune existing notes automatically based on definition similarity
        notes = prune_existing_notes_automatically(notes, existing_notes, cache_suffix=language_pair_code)

        # Prune duplicates new notes leaving the best one
        notes = prune_new_notes_against_eachother(notes)
        sleep(5)  # Opportunity to read output

        if len(notes) == 0:
            print(f"No new notes to add to Anki after pruning for language: {source_lang_code}")
            continue

        # Provide translations
        process_context_translation(notes, source_lang_code, target_lang_code, ignore_cache=False, use_llm=True)
        sleep(5)  # Opportunity to read output

        # Provide collocations
        process_collocation_generation(notes, source_lang_code, target_lang_code, ignore_cache=False)
        sleep(5)  # Opportunity to read output

        # Save results to Anki import file and via AnkiConnect
        write_anki_import_file(notes, source_lang_code)
        anki_connect_instance.create_notes_batch(anki_deck, notes)
        sleep(5)  # Opportunity to read output

    # Save script run timestamp
    metadata_manager.save_script_run_timestamp(metadata)

    # Save timestamp for future incremental imports
    metadata_manager.save_latest_vocab_builder_entry_timestamp(kindle_vocab_data, metadata)

    print("\nKindle to Anki export process completed successfully.")


if __name__ == "__main__":
    export_kindle_vocab()

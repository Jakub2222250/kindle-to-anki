from export.export_anki import write_anki_import_file
from collocation.collocation import process_collocation_generation
from metadata.metdata_manager import MetadataManager
from configuration.config_manager import get_anki_decks_by_source_language
from translation.translation import process_context_translation
from wsd.wsd import provide_word_sense_disambiguation
from lexical_unit_identification.lexical_unit_identification import complete_lexical_unit_identification
from pruning.pruning import prune_existing_notes_automatically, prune_existing_notes_by_UID, prune_new_notes_against_eachother, prune_notes_identified_as_redundant
from anki.anki_connect import AnkiConnect
from vocab.vocab import get_vocab_db, get_latest_vocab_data

from time import sleep


def export_kindle_vocab():

    print("Starting Kindle to Anki export process.")

    # Get available anki decks by language pair
    anki_decks_by_source_language = get_anki_decks_by_source_language()

    # Load existing metadata
    metadata_manager = MetadataManager()
    metadata = metadata_manager.load_metadata()

    # Get latest kindle vocab data
    db_path = get_vocab_db()
    notes_by_language, latest_vocab_entry_timestamp = get_latest_vocab_data(db_path, metadata)

    # Connect to AnkiConnect
    anki_connect_instance = AnkiConnect()

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
    metadata_manager.save_latest_vocab_builder_entry_timestamp(latest_vocab_entry_timestamp, metadata)

    print("\nKindle to Anki export process completed successfully.")


if __name__ == "__main__":
    export_kindle_vocab()

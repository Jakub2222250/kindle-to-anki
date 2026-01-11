from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.configuration.config_manager import ConfigManager
from kindle_to_anki.configuration.options_display import show_selected_options
from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig

from kindle_to_anki.core.runtimes.runtime_registry import RuntimeRegistry
from kindle_to_anki.core.prompts import get_default_prompt_id, get_lui_default_prompt_id
from kindle_to_anki.tasks.collect_candidates.provider import CollectCandidatesProvider
from kindle_to_anki.tasks.translation.provider import TranslationProvider
from kindle_to_anki.tasks.wsd.provider import WSDProvider
from kindle_to_anki.tasks.hint.provider import HintProvider
from kindle_to_anki.tasks.cloze_scoring.provider import ClozeScoringProvider
from kindle_to_anki.tasks.usage_level.provider import UsageLevelProvider
from kindle_to_anki.tasks.collocation.provider import CollocationProvider
from kindle_to_anki.tasks.lui.provider import LUIProvider

from kindle_to_anki.metadata.metdata_manager import MetadataManager

from kindle_to_anki.export.export_anki import write_anki_import_file
from kindle_to_anki.pruning.pruning import prune_existing_notes_automatically, prune_existing_notes_by_UID, prune_new_notes_against_eachother, prune_notes_identified_as_redundant

from time import sleep


def export_kindle_vocab():

    SLEEP_TIME = 0

    print("Starting Kindle to Anki export process.")

    bootstrap_all()

    # Setup providers with their runtimes
    candidate_provider = CollectCandidatesProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("collect_candidates"))
    translation_provider = TranslationProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("translation"))
    wsd_provider = WSDProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("wsd"))
    hint_provider = HintProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("hint"))
    cloze_scoring_provider = ClozeScoringProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("cloze_scoring"))
    usage_level_provider = UsageLevelProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("usage_level"))
    collocation_provider = CollocationProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("collocation"))
    lui_provider = LUIProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("lui"))

    # Initialize configuration manager
    config_manager = ConfigManager()
    target_language_code = "en"

    # Get available anki decks by language pair
    anki_decks_by_source_language = config_manager.get_anki_decks_by_source_language()

    notes_by_language, latest_candidate_timestamp = candidate_provider.collect_candidates(
        runtime_choice="kindle"
    )

    if not notes_by_language or len(notes_by_language) == 0:
        print("No candidate notes collected. Exiting process.")
        return

    # Connect to AnkiConnect
    anki_connect_instance = AnkiConnect()

    for source_language_code, notes in notes_by_language.items():

        # Reference to anki deck for metadata
        anki_deck = anki_decks_by_source_language.get(source_language_code)
        target_language_code = anki_deck.target_language_code
        language_pair_code = anki_deck.get_language_pair_code()

        # Get existing notes from Anki for this language
        existing_notes = anki_connect_instance.get_notes(anki_deck)

        # Prune existing notes by UID
        notes = prune_existing_notes_by_UID(notes, existing_notes)
        if len(notes) == 0:
            print(f"No new notes to add to Anki after UID pruning for language: {source_language_code}")
            continue

        # Prune notes previously identified as redundant
        notes = prune_notes_identified_as_redundant(notes, cache_suffix=language_pair_code)
        if len(notes) == 0:
            print(f"No new notes to add to Anki after redundancy pruning for language: {source_language_code}")
            continue

        # Show selected configuration with cost estimates
        task_settings = {
            "lui": config_manager.get_task_setting("lui"),
            "wsd": config_manager.get_task_setting("wsd"),
            "hint": config_manager.get_task_setting("hint"),
            "cloze_scoring": config_manager.get_task_setting("cloze_scoring"),
            "usage_level": config_manager.get_task_setting("usage_level"),
            "translation": config_manager.get_task_setting("translation"),
            "collocation": config_manager.get_task_setting("collocation")
        }
        show_selected_options(task_settings, source_language_code, target_language_code, len(notes))

        sleep(SLEEP_TIME)  # Opportunity to read output

        if len(notes) > 100:
            response = input(f"\nYou are about to process {len(notes)} notes for language: {source_language_code}. Do you want to continue? (y/n): ").strip().lower()
            if response != 'y' and response != 'yes':
                print("Process aborted by user.")
                exit()

        # Enrich notes with lexical unit identification
        lui_setting = config_manager.get_task_setting("lui")
        lui_prompt_id = lui_setting.get("prompt_id") or get_lui_default_prompt_id(source_language_code)
        lui_provider.identify(
            notes=notes,
            runtime_choice=lui_setting["runtime"],
            runtime_config=RuntimeConfig(
                model_id=lui_setting["model_id"],
                batch_size=lui_setting["batch_size"],
                source_language_code=source_language_code,
                target_language_code=target_language_code,
                prompt_id=lui_prompt_id
            ),
            ignore_cache=False
        )
        sleep(SLEEP_TIME)  # Opportunity to read output

        if not notes:
            print(f"No new notes to process for language: {source_language_code}")
            continue

        # Provide word sense disambiguation via LLM
        wsd_setting = config_manager.get_task_setting("wsd")
        wsd_prompt_id = wsd_setting.get("prompt_id") or get_default_prompt_id("wsd")
        wsd_provider.disambiguate(
            notes=notes,
            runtime_choice=wsd_setting["runtime"],
            runtime_config=RuntimeConfig(
                model_id=wsd_setting["model_id"],
                batch_size=wsd_setting["batch_size"],
                source_language_code=source_language_code,
                target_language_code=target_language_code,
                prompt_id=wsd_prompt_id
            ),
            ignore_cache=False
        )
        sleep(SLEEP_TIME)  # Opportunity to read output

        # Prune existing notes automatically based on definition similarity
        notes = prune_existing_notes_automatically(notes, existing_notes, cache_suffix=language_pair_code)

        # Prune duplicates new notes leaving the best one
        notes = prune_new_notes_against_eachother(notes)
        sleep(SLEEP_TIME)  # Opportunity to read output

        if len(notes) == 0:
            print(f"No new notes to add to Anki after pruning for language: {source_language_code}")
            continue

        # Generate hints
        hint_setting = config_manager.get_task_setting("hint")
        if hint_setting.get("enabled", True):
            hint_prompt_id = hint_setting.get("prompt_id") or get_default_prompt_id("hint")
            hint_provider.generate(
                notes=notes,
                runtime_choice=hint_setting["runtime"],
                runtime_config=RuntimeConfig(
                    model_id=hint_setting["model_id"],
                    batch_size=hint_setting["batch_size"],
                    source_language_code=source_language_code,
                    target_language_code=target_language_code,
                    prompt_id=hint_prompt_id
                ),
                ignore_cache=False
            )
        sleep(SLEEP_TIME)  # Opportunity to read output

        # Score cloze deletion suitability
        cloze_setting = config_manager.get_task_setting("cloze_scoring")
        if cloze_setting.get("enabled", True):
            cloze_prompt_id = cloze_setting.get("prompt_id") or get_default_prompt_id("cloze_scoring")
            cloze_scoring_provider.score(
                notes=notes,
                runtime_choice=cloze_setting["runtime"],
                runtime_config=RuntimeConfig(
                    model_id=cloze_setting["model_id"],
                    batch_size=cloze_setting["batch_size"],
                    source_language_code=source_language_code,
                    target_language_code=target_language_code,
                    prompt_id=cloze_prompt_id
                ),
                ignore_cache=False
            )
        else:
            # When skipped, enable cloze by default
            for note in notes:
                note.cloze_enabled = "?"
        sleep(SLEEP_TIME)  # Opportunity to read output

        # Estimate usage level
        usage_level_setting = config_manager.get_task_setting("usage_level")
        if usage_level_setting.get("enabled", True):
            usage_level_prompt_id = usage_level_setting.get("prompt_id") or get_default_prompt_id("usage_level")
            usage_level_provider.estimate(
                notes=notes,
                runtime_choice=usage_level_setting["runtime"],
                runtime_config=RuntimeConfig(
                    model_id=usage_level_setting["model_id"],
                    batch_size=usage_level_setting["batch_size"],
                    source_language_code=source_language_code,
                    target_language_code=target_language_code,
                    prompt_id=usage_level_prompt_id
                ),
                ignore_cache=False
            )
        sleep(SLEEP_TIME)  # Opportunity to read output

        # Provide translations
        translation_setting = config_manager.get_task_setting("translation")
        translation_prompt_id = translation_setting.get("prompt_id") or get_default_prompt_id("translation")
        translation_provider.translate(
            notes=notes,
            runtime_choice=translation_setting["runtime"],
            runtime_config=RuntimeConfig(
                model_id=translation_setting["model_id"],
                batch_size=translation_setting["batch_size"],
                source_language_code=source_language_code,
                target_language_code=target_language_code,
                prompt_id=translation_prompt_id
            ),
            ignore_cache=False,
            use_test_cache=False
        )
        sleep(SLEEP_TIME)  # Opportunity to read output

        # Provide collocations
        collocation_setting = config_manager.get_task_setting("collocation")
        if collocation_setting.get("enabled", True):
            collocation_prompt_id = collocation_setting.get("prompt_id") or get_default_prompt_id("collocation")
            collocation_provider.generate_collocations(
                notes=notes,
                runtime_choice=collocation_setting["runtime"],
                runtime_config=RuntimeConfig(
                    model_id=collocation_setting["model_id"],
                    batch_size=collocation_setting["batch_size"],
                    source_language_code=source_language_code,
                    target_language_code=target_language_code,
                    prompt_id=collocation_prompt_id
                ),
                ignore_cache=False
            )
        sleep(SLEEP_TIME)  # Opportunity to read output

        # Save results to Anki import file and via AnkiConnect
        write_anki_import_file(notes, source_language_code)
        anki_connect_instance.create_notes_batch(anki_deck, notes)
        sleep(SLEEP_TIME)  # Opportunity to read output

    # Save timestamp for future incremental imports
    if latest_candidate_timestamp:
        metadata_manager = MetadataManager()
        metadata = metadata_manager.load_metadata()
        metadata_manager.save_latest_vocab_builder_entry_timestamp(latest_candidate_timestamp, metadata)

    print("\nKindle to Anki export process completed successfully.")


if __name__ == "__main__":
    export_kindle_vocab()

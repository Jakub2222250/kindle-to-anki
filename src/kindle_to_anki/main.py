from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.configuration.config_manager import ConfigManager
from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.core.pricing.token_pricing_policy import TokenPricingPolicy
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.runtimes.runtime_registry import RuntimeRegistry
from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.platforms.platform_registry import PlatformRegistry
from kindle_to_anki.tasks.tasks import TASKS

from kindle_to_anki.tasks.collect_candidates.provider import CollectCandidatesProvider
from kindle_to_anki.tasks.translation.provider import TranslationProvider
from kindle_to_anki.tasks.wsd.provider import WSDProvider
from kindle_to_anki.tasks.collocation.provider import CollocationProvider
from kindle_to_anki.tasks.lui.provider import LUIProvider

from kindle_to_anki.metadata.metdata_manager import MetadataManager

from kindle_to_anki.export.export_anki import write_anki_import_file
from kindle_to_anki.pruning.pruning import prune_existing_notes_automatically, prune_existing_notes_by_UID, prune_new_notes_against_eachother, prune_notes_identified_as_redundant

from time import sleep


def show_all_options(source_language_code: str, target_language_code: str):

    for task in TASKS:
        for runtime in RuntimeRegistry.list():

            if task not in runtime.supported_tasks:
                continue

            supports_model_families = runtime.supported_model_families
            if not supports_model_families or len(supports_model_families) == 0:
                usage_estimate = 0.0
                available = "Yes"
                print(f"Task: {task:20s}, Runtime: {runtime.id:30s}, Model: {'n/a':16s}, Cost/1000: ${usage_estimate:.4f}, Available: {available}")
            else:
                models_for_runtime = [
                    m for m in ModelRegistry.list()
                    if m.family in supports_model_families
                ]
                for model in models_for_runtime:
                    runtime_config = RuntimeConfig(
                        model_id=model.id,
                        batch_size=30,
                        source_language_code=source_language_code,
                        target_language_code=target_language_code
                    )

                    usage_estimate = runtime.estimate_usage(1000, runtime_config)

                    token_pricing_policy = TokenPricingPolicy(
                        input_cost_per_1m=model.input_token_cost_per_1m,
                        output_cost_per_1m=model.output_token_cost_per_1m,
                    )

                    usage_estimate = token_pricing_policy.estimate_cost(usage_estimate)
                    platform = PlatformRegistry.get(model.platform_id)
                    available = "Yes" if platform and platform.validate_credentials() else "No"
                    print(f"Task: {task:20s}, Runtime: {runtime.id:30s}, Model: {model.id:16s}, Cost/1000: ${usage_estimate.usd:.4f}, Available: {available}")


def export_kindle_vocab():

    print("Starting Kindle to Anki export process.")

    bootstrap_all()

    # Setup providers with their runtimes
    candidate_provider = CollectCandidatesProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("collect_candidates"))
    translation_provider = TranslationProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("translation"))
    wsd_provider = WSDProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("wsd"))
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
        
        show_all_options(source_language_code, target_language_code)

        # Reusable configs
        best_model_normal_batch = RuntimeConfig(
            model_id="gpt-5.1",
            batch_size=30,
            source_language_code=source_language_code,
            target_language_code=target_language_code
        )
        
        cheap_model_normal_batch = RuntimeConfig(
            model_id="gpt-5-mini",
            batch_size=30,
            source_language_code=source_language_code,
            target_language_code=target_language_code
        )

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

        sleep(5)  # Opportunity to read output

        if len(notes) > 100:
            response = input(f"\nYou are about to process {len(notes)} notes for language: {source_language_code}. Do you want to continue? (y/n): ").strip().lower()
            if response != 'y' and response != 'yes':
                print("Process aborted by user.")
                exit()

        # Enrich notes with lexical unit identification
        lui_provider.identify(
            notes=notes,
            runtime_choice="chat_completion_lui",
            runtime_config=best_model_normal_batch,
            ignore_cache=False
        )
        sleep(5)  # Opportunity to read output

        if not notes:
            print(f"No new notes to process for language: {source_language_code}")
            continue

        # Provide word sense disambiguation via LLM
        wsd_provider.disambiguate(
            notes=notes,
            runtime_choice="chat_completion_wsd",
            runtime_config=best_model_normal_batch,
            ignore_cache=False
        )
        sleep(5)  # Opportunity to read output

        # Prune existing notes automatically based on definition similarity
        notes = prune_existing_notes_automatically(notes, existing_notes, cache_suffix=language_pair_code)

        # Prune duplicates new notes leaving the best one
        notes = prune_new_notes_against_eachother(notes)
        sleep(5)  # Opportunity to read output

        if len(notes) == 0:
            print(f"No new notes to add to Anki after pruning for language: {source_language_code}")
            continue

        # Provide translations
        translation_provider.translate(
            notes=notes,
            runtime_choice="chat_completion_translation",
            runtime_config=best_model_normal_batch,
            ignore_cache=False,
            use_test_cache=False
        )
        sleep(5)  # Opportunity to read output

        # Provide collocations
        collocation_provider.generate_collocations(
            notes=notes,
            runtime_choice="chat_completion_collocation",
            runtime_config=cheap_model_normal_batch,
            ignore_cache=False
        )
        sleep(5)  # Opportunity to read output

        # Save results to Anki import file and via AnkiConnect
        write_anki_import_file(notes, source_language_code)
        anki_connect_instance.create_notes_batch(anki_deck, notes)
        sleep(5)  # Opportunity to read output

    # Save timestamp for future incremental imports
    if latest_candidate_timestamp:
        metadata_manager = MetadataManager()
        metadata = metadata_manager.load_metadata()
        metadata_manager.save_latest_vocab_builder_entry_timestamp(latest_candidate_timestamp, metadata)

    print("\nKindle to Anki export process completed successfully.")


if __name__ == "__main__":
    export_kindle_vocab()

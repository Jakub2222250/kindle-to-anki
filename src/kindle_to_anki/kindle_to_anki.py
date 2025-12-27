from turtle import mode
from anki.anki_connect import AnkiConnect
from configuration.config_manager import ConfigManager
from .tasks.tasks import TASKS
from .core.runtimes.runtime_registry import RuntimeRegistry
from .platforms.platform_registry import PlatformRegistry
from .core.models.registry import ModelRegistry
from platforms.openai_platform import OpenAIPlatform
from .core.models import models

from tasks.collect_candidates.provider import CollectCandidatesProvider
from tasks.collect_candidates.runtime_kindle import KindleCandidateRuntime
from tasks.translation.provider import TranslationProvider
from tasks.translation.runtime_polish_local import PolishLocalTranslation
from tasks.translation.runtime_chat_completion import ChatCompletionTranslation
from tasks.wsd.provider import WSDProvider
from tasks.wsd.runtime_chat_completion import ChatCompletionWSD
from tasks.collocation.provider import CollocationProvider
from tasks.collocation.runtime_chat_completion import ChatCompletionCollocation
from tasks.lui.provider import LUIProvider
from tasks.lui.runtime_chat_completion import ChatCompletionLUI

from metadata.metdata_manager import MetadataManager

from export.export_anki import write_anki_import_file
from pruning.pruning import prune_existing_notes_automatically, prune_existing_notes_by_UID, prune_new_notes_against_eachother, prune_notes_identified_as_redundant

from time import sleep


def get_all_registries():
    # Register Platforms
    platform_registry = PlatformRegistry()
    platform_registry.register(OpenAIPlatform())
    
    model_registry = ModelRegistry()
    
    # Register models
    model_registry.register(models.GPT_5_MINI)
    model_registry.register(models.GPT_5_1)

    # Register runtimes
    runtime_registry = RuntimeRegistry()
    runtime_registry.register(ChatCompletionLUI())
    
    return platform_registry, model_registry, runtime_registry

def show_all_options(platform_registry, model_registry, runtime_registry):
    for task in TASKS:
        for runtime in runtime_registry.list():

            if not runtime.supports_task(task):
                continue

            supports_model_families = runtime.supported_model_families
            if not supports_model_families or len(supports_model_families) == 0:
                ...
            else:
                models_for_runtime = [
                    m for m in model_registry.list()
                    if m.family in supports_model_families
                ]
                for model in models_for_runtime:
                    print(f"Task: {task}, Runtime: {runtime.id}, Model: {model.id}")


def export_kindle_vocab():

    print("Starting Kindle to Anki export process.")
    
    platform_registry, model_registry, runtime_registry = get_all_registries()
    show_all_options(platform_registry, model_registry, runtime_registry)
    
    # Setup the platform and runtimes
    platform = OpenAIPlatform()
    
    # Setup translation runtimes and provider
    translation_runtime = ChatCompletionTranslation(platform=platform, model_name="gpt-5", batch_size=30)
    polish_translator_local = PolishLocalTranslation(batch_size=30)
    translation_runtimes = {"gpt-5": translation_runtime, "polish_local": polish_translator_local}
    translation_provider = TranslationProvider(runtimes=translation_runtimes)
    
    # Setup candidate collection runtimes and provider
    kindle_runtime = KindleCandidateRuntime()
    candidate_runtimes = {"kindle": kindle_runtime}
    candidate_provider = CollectCandidatesProvider(runtimes=candidate_runtimes)
    
    # Setup WSD runtimes and provider
    wsd_runtime = ChatCompletionWSD(platform=platform, model_name="gpt-5", batch_size=30)
    wsd_runtimes = {"gpt-5": wsd_runtime}
    wsd_provider = WSDProvider(runtimes=wsd_runtimes)
    
    # Setup collocation runtimes and provider
    collocation_runtime = ChatCompletionCollocation(platform=platform, model_name="gpt-5", batch_size=30)
    collocation_runtimes = {"gpt-5": collocation_runtime}
    collocation_provider = CollocationProvider(runtimes=collocation_runtimes)
    
    # Setup LUI runtimes and provider
    lui_runtime = ChatCompletionLUI(platform=platform, model_name="gpt-5", batch_size=30)
    lui_runtimes = {"gpt-5": lui_runtime}
    lui_provider = LUIProvider(runtimes=lui_runtimes)

    # Initialize configuration manager
    config_manager = ConfigManager()
    
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

    for source_lang_code, notes in notes_by_language.items():

        # Reference to anki deck for metadata
        anki_deck = anki_decks_by_source_language.get(source_lang_code)
        target_lang_code = anki_deck.target_lang_code
        language_pair_code = anki_deck.get_language_pair_code()

        # Get existing notes from Anki for this language
        existing_notes = anki_connect_instance.get_notes(anki_deck)

        # Prune existing notes by UID
        notes = prune_existing_notes_by_UID(notes, existing_notes)
        if len(notes) == 0:
            print(f"No new notes to add to Anki after UID pruning for language: {source_lang_code}")
            continue

        # Prune notes previously identified as redundant
        notes = prune_notes_identified_as_redundant(notes, cache_suffix=language_pair_code)
        if len(notes) == 0:
            print(f"No new notes to add to Anki after redundancy pruning for language: {source_lang_code}")
            continue

        sleep(5)  # Opportunity to read output

        if len(notes) > 100:
            response = input(f"\nYou are about to process {len(notes)} notes for language: {source_lang_code}. Do you want to continue? (y/n): ").strip().lower()
            if response != 'y' and response != 'yes':
                print("Process aborted by user.")
                exit()

        # Enrich notes with lexical unit identification
        lui_provider.identify(
            notes=notes,
            runtime_choice="gpt-5",
            source_lang=source_lang_code,
            target_lang=target_lang_code,
            ignore_cache=False
        )
        sleep(5)  # Opportunity to read output

        if not notes:
            print(f"No new notes to process for language: {source_lang_code}")
            continue

        # Provide word sense disambiguation via LLM
        wsd_provider.disambiguate(
            notes=notes,
            runtime_choice="gpt-5",
            source_lang=source_lang_code,
            target_lang=target_lang_code,
            ignore_cache=False
        )
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
        translation_provider.translate(
            notes=notes,
            runtime_choice="gpt-5",
            source_lang=source_lang_code,
            target_lang=target_lang_code,
            ignore_cache=False,
            use_test_cache=False
        )
        sleep(5)  # Opportunity to read output

        # Provide collocations
        collocation_provider.generate_collocations(
            notes=notes,
            runtime_choice="gpt-5",
            source_lang=source_lang_code,
            target_lang=target_lang_code,
            ignore_cache=False
        )
        sleep(5)  # Opportunity to read output

        # Save results to Anki import file and via AnkiConnect
        write_anki_import_file(notes, source_lang_code)
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

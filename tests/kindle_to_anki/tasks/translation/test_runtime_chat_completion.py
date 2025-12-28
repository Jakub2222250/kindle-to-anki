#!/usr/bin/env python3
"""
Test for the new ChatCompletionTranslation runtime system.
This replaces the old test_translator_llm.py with the new structured approach.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))

from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.tasks.translation.runtime_chat_completion import ChatCompletionTranslation
from kindle_to_anki.tasks.translation.provider import TranslationProvider
from kindle_to_anki.tasks.translation.schema import TranslationInput, TranslationOutput


def test_runtime_chat_completion():
    """Test the new ChatCompletionTranslation runtime."""
    
    # Example usage and testing
    notes = [
        AnkiNote(
            word="przykład",
            stem="przykład",
            usage="To jest przykład zdania do przetłumaczenia.",
            language="pl",
            book_name="Sample Book",
            position="123-456",
            timestamp="2024-01-01T12:00:00Z"
        ),
        AnkiNote(
            word="bawół",
            stem="bawołem",
            usage="Nie zapominajcie o czarodzieju Baruffio, który źle wypowiedział spółgłoskę i znalazł się na podłodze, przygnieciony bawołem.",
            language="pl",
            book_name="Sample Book",
            position="789-1011",
            timestamp="2024-01-01T12:05:00Z"
        )
    ]

    # Setup runtime and config
    runtime = ChatCompletionTranslation()
    runtime_config = RuntimeConfig(model_id="gpt-5.1", batch_size=30)
    
    # Setup the provider
    runtimes = {"chat_completion_translation": runtime}
    provider = TranslationProvider(runtimes=runtimes)
    
    # Test translation via provider
    print("Testing translation via TranslationProvider...")
    translated_notes = provider.translate(
        notes=notes,
        runtime_choice="chat_completion_translation",
        runtime_config=runtime_config,
        source_lang="pl",
        target_lang="en",
        ignore_cache=False,
        use_test_cache=True
    )

    print("\nResults via TranslationProvider:")
    for note in translated_notes:
        print(f"Original: {note.context_sentence}")
        print(f"Translated: {note.context_translation}")
        print()


def test_direct_runtime_usage():
    """Test using the runtime directly with TranslationInput/Output schemas."""
    
    # Create translation inputs
    translation_inputs = [
        TranslationInput(
            uid="test-uid-1",
            context="To jest przykład zdania do przetłumaczenia."
        ),
        TranslationInput(
            uid="test-uid-2",
            context="Nie zapominajcie o czarodzieju Baruffio, który źle wypowiedział spółgłoskę."
        )
    ]
    
    # Setup runtime and config
    runtime = ChatCompletionTranslation()
    runtime_config = RuntimeConfig(model_id="gpt-5.1", batch_size=30)
    
    # Test direct translation
    print("Testing direct runtime usage...")
    translation_outputs = runtime.translate(
        translation_inputs=translation_inputs,
        source_lang="pl",
        target_lang="en",
        runtime_config=runtime_config,
        ignore_cache=False,
        use_test_cache=True
    )
    
    print("\nResults from direct runtime usage:")
    for translation_input, translation_output in zip(translation_inputs, translation_outputs):
        print(f"UID: {translation_input.uid}")
        print(f"Original: {translation_input.context}")
        print(f"Translated: {translation_output.translation}")
        print()

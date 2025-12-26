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
from kindle_to_anki.platforms.openai_platform import OpenAIPlatform
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

    # Setup the platform and runtime
    platform = OpenAIPlatform()
    runtime = ChatCompletionTranslation(platform=platform, model_name="gpt-5", batch_size=30)
    
    # Setup the provider
    runtimes = {"gpt-5": runtime}
    provider = TranslationProvider(runtimes=runtimes)
    
    # Test translation via provider
    print("Testing translation via TranslationProvider...")
    translated_notes = provider.translate(
        notes=notes,
        runtime_choice="gpt-5",
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
            context="To jest przykład zdania do przetłumaczenia.",
            source_lang="pl",
            target_lang="en"
        ),
        TranslationInput(
            uid="test-uid-2",
            context="Nie zapominajcie o czarodzieju Baruffio, który źle wypowiedział spółgłoskę.",
            source_lang="pl",
            target_lang="en"
        )
    ]
    
    # Setup runtime
    platform = OpenAIPlatform()
    runtime = ChatCompletionTranslation(platform=platform, model_name="gpt-5", batch_size=30)
    
    # Test direct translation
    print("Testing direct runtime usage...")
    translation_outputs = runtime.translate(
        translation_inputs=translation_inputs,
        ignore_cache=False,
        use_test_cache=True
    )
    
    print("\nResults from direct runtime usage:")
    for translation_input, translation_output in zip(translation_inputs, translation_outputs):
        print(f"UID: {translation_input.uid}")
        print(f"Original: {translation_input.context}")
        print(f"Translated: {translation_output.translation}")
        if translation_output.confidence:
            print(f"Confidence: {translation_output.confidence}")
        print()


def test_migration_compatibility():
    """Test that the migration helper provides backward compatibility."""
    
    from kindle_to_anki.tasks.translation.migration_helper import translate_context_with_llm
    
    notes = [
        AnkiNote(
            word="test",
            stem="test", 
            usage="To jest test kompatybilności wstecznej.",
            language="pl",
            book_name="Test Book",
            position="1-10",
            timestamp="2024-01-01T12:00:00Z"
        )
    ]
    
    print("Testing backward compatibility...")
    translate_context_with_llm(notes, "pl", "en", ignore_cache=False, use_test_cache=True)
    
    print("\nBackward compatibility test results:")
    for note in notes:
        print(f"Original: {note.context_sentence}")
        print(f"Translated: {note.context_translation}")
        print()


if __name__ == "__main__":
    print("Testing new ChatCompletionTranslation runtime system...")
    print("=" * 60)
    
    try:
        print("\n1. Testing via TranslationProvider:")
        test_runtime_chat_completion()
        
        print("\n2. Testing direct runtime usage:")
        test_direct_runtime_usage()
        
        print("\n3. Testing backward compatibility:")
        test_migration_compatibility()
        
        print("All tests completed successfully!")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
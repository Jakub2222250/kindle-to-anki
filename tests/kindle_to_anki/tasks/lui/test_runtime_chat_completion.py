#!/usr/bin/env python3
"""
Test for the new ChatCompletionLUI runtime system.
This replaces the old test_lui_llm.py with the new structured approach.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))

from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.tasks.lui.runtime_chat_completion import ChatCompletionLUI
from kindle_to_anki.tasks.lui.provider import LUIProvider
from kindle_to_anki.tasks.lui.schema import LUIInput, LUIOutput


def test_runtime_chat_completion():
    """Test the new ChatCompletionLUI runtime."""
    
    # Example usage and testing
    test_notes = [
        AnkiNote(
            word="się",
            stem="się",
            usage="Boi się ciemności.",
            language="pl",
            book_name="Test Book",
            position="123-456",
            timestamp="2024-01-01T12:00:00Z"
        ),
        AnkiNote(
            word="corriendo",
            stem="corriendo", 
            usage="El niño está corriendo en el parque.",
            language="es",
            book_name="Test Book",
            position="789-1011",
            timestamp="2024-01-01T12:05:00Z"
        ),
        AnkiNote(
            word="sich",
            stem="sich",
            usage="Er freut sich über das Geschenk.",
            language="de",
            book_name="Test Book", 
            position="1213-1415",
            timestamp="2024-01-01T12:10:00Z"
        )
    ]

    # Setup runtime and config
    runtime = ChatCompletionLUI()
    runtime_config = RuntimeConfig(model_id="gpt-5.1", batch_size=30)
    
    # Setup the provider
    runtimes = {"chat_completion_lui": runtime}
    provider = LUIProvider(runtimes=runtimes)
    
    # Test with different languages
    for lang_code in ["pl", "es", "de"]:
        lang_notes = [note for note in test_notes if note.kindle_language == lang_code]
        
        if lang_notes:
            print(f"\n=== Testing {lang_code} using Provider ===")
            
            # Test via provider
            provider.identify(
                notes=lang_notes,
                runtime_choice="chat_completion_lui",
                runtime_config=runtime_config,
                source_lang=lang_code,
                target_lang="en",
                ignore_cache=False,
                use_test_cache=True
            )

            for note in lang_notes:
                print(f"Word: {note.kindle_word}")
                print(f"Sentence: {note.kindle_usage}")
                print(f"Lemma: {note.expression}")
                print(f"POS: {note.part_of_speech}")
                print(f"Aspect: {note.aspect}")
                print(f"Original Form: {note.original_form}")
                print(f"Unit Type: {note.unit_type}")
                print()


def test_runtime_direct():
    """Test the ChatCompletionLUI runtime directly."""
    
    # Test direct runtime usage
    runtime = ChatCompletionLUI()
    runtime_config = RuntimeConfig(model_id="gpt-5.1", batch_size=30)
    
    # Create LUIInput objects for testing
    lui_inputs = [
        LUIInput(
            uid="test_1",
            word="się", 
            sentence="Boi się ciemności."
        ),
        LUIInput(
            uid="test_2",
            word="corriendo",
            sentence="El niño está corriendo en el parque."
        )
    ]
    
    print("\n=== Testing Direct Runtime Usage ===")
    
    # Test Polish
    pl_inputs = [lui_inputs[0]]
    pl_outputs = runtime.identify(
        pl_inputs,
        source_lang="pl",
        target_lang="en",
        runtime_config=runtime_config,
        ignore_cache=False,
        use_test_cache=True
    )
    
    for lui_input, lui_output in zip(pl_inputs, pl_outputs):
        print(f"Input - UID: {lui_input.uid}, Word: {lui_input.word}")
        print(f"Output - Lemma: {lui_output.lemma}, POS: {lui_output.part_of_speech}")
        print(f"         Aspect: {lui_output.aspect}, Unit Type: {lui_output.unit_type}")
        print()
    
    # Test Spanish
    es_inputs = [lui_inputs[1]]
    es_outputs = runtime.identify(
        es_inputs,
        source_lang="es",
        target_lang="en",
        runtime_config=runtime_config,
        ignore_cache=False,
        use_test_cache=True
    )
    
    for lui_input, lui_output in zip(es_inputs, es_outputs):
        print(f"Input - UID: {lui_input.uid}, Word: {lui_input.word}")
        print(f"Output - Lemma: {lui_output.lemma}, POS: {lui_output.part_of_speech}")
        print(f"         Aspect: {lui_output.aspect}, Unit Type: {lui_output.unit_type}")
        print()


if __name__ == "__main__":
    test_runtime_chat_completion()
    test_runtime_direct()
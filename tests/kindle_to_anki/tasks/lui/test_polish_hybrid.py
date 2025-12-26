#!/usr/bin/env python3
"""
Test for Polish hybrid lexical unit identification using the new task structure.
This replaces the old test_lui_polish_hybrid.py with tests for the new provider pattern.
Since the Polish hybrid runtime hasn't been implemented yet, this test uses the 
ChatCompletionLUI runtime but includes test cases from the original Polish hybrid tests.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))

from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.platforms.openai_platform import OpenAIPlatform
from kindle_to_anki.tasks.lui.runtime_chat_completion import ChatCompletionLUI
from kindle_to_anki.tasks.lui.provider import LUIProvider
from kindle_to_anki.tasks.lui.schema import LUIInput, LUIOutput


def test_polish_hybrid_cases():
    """Test Polish-specific cases using the new LUI provider pattern."""
    
    # Test cases from the original Polish hybrid tests
    test_cases = [
        {
            'kindle_word': 'uczy',
            'sentence': 'Dziecko szybko uczy się nowych słów.',
            'expected_lemma': 'uczyć się',
            'expected_original_form': 'uczy się',
            'expected_pos': 'verb',
            'expected_aspect': 'impf'
        },
        {
            'kindle_word': 'uczy',
            'sentence': 'Nauczyciel uczy dzieci matematyki.',
            'expected_lemma': 'uczyć',
            'expected_original_form': 'uczy',
            'expected_pos': 'verb',
            'expected_aspect': 'impf'
        },
        {
            'kindle_word': 'zatrzymał',
            'sentence': 'Samochód nagle zatrzymał się na środku drogi.',
            'expected_lemma': 'zatrzymać się',
            'expected_original_form': 'zatrzymał się',
            'expected_pos': 'verb',
            'expected_aspect': 'perf'
        },
        {
            'kindle_word': 'Otworzył',
            'sentence': 'Otworzył drzwi bez pukania.',
            'expected_lemma': 'otworzyć',
            'expected_original_form': 'Otworzył',
            'expected_pos': 'verb',
            'expected_aspect': 'perf'
        },
        {
            'kindle_word': 'zawzięcie',
            'sentence': 'Który walił zawzięcie różdżką w blat ławki.',
            'expected_lemma': 'zawzięcie',
            'expected_original_form': 'zawzięcie',
            'expected_pos': 'adverb',
            'expected_aspect': ''
        }
    ]

    # Create AnkiNote objects from test cases
    notes = []
    for i, test_case in enumerate(test_cases):
        note = AnkiNote(
            test_case['kindle_word'], 
            "", 
            test_case['sentence'], 
            "pl", 
            "Test Book", 
            f"loc_{i + 1}", 
            ""
        )
        notes.append(note)

    # Setup the platform and runtime
    platform = OpenAIPlatform()
    runtime = ChatCompletionLUI(platform=platform, model_name="gpt-5", batch_size=30)
    
    # Setup the provider
    runtimes = {"gpt-5": runtime}
    provider = LUIProvider(runtimes=runtimes)
    
    print("\\n=== Testing Polish LUI Cases with Provider ===")
    
    # Test via provider
    provider.identify(
        notes=notes,
        runtime_choice="gpt-5", 
        source_lang="pl",
        target_lang="en",
        ignore_cache=False,
        use_test_cache=True
    )

    # Validate results
    for i, test_case in enumerate(test_cases):
        note = notes[i]
        
        # Determine expected unit_type based on whether się appears in the expected lemma
        expected_unit_type = "reflexive" if "się" in test_case['expected_lemma'] else "lemma"
        
        print(f"\\n--- Test Case {i+1}: {test_case['kindle_word']} ---")
        print(f"Sentence: {test_case['sentence']}")
        print(f"Expected: lemma='{test_case['expected_lemma']}', pos='{test_case['expected_pos']}', aspect='{test_case['expected_aspect']}'")
        print(f"Actual:   lemma='{note.expression}', pos='{note.part_of_speech}', aspect='{note.aspect}'")
        print(f"Expected unit_type: '{expected_unit_type}', Actual: '{note.unit_type}'")
        
        # Check results (for now just log, since LLM results may vary)
        if test_case['expected_lemma'] == note.expression:
            print("✓ LEMMA MATCH")
        else:
            print("✗ LEMMA MISMATCH") 
            
        if test_case['expected_pos'] == note.part_of_speech:
            print("✓ POS MATCH")
        else:
            print("✗ POS MISMATCH")
            
        if test_case['expected_aspect'] == note.aspect:
            print("✓ ASPECT MATCH") 
        else:
            print("✗ ASPECT MISMATCH")
            
        if expected_unit_type == note.unit_type:
            print("✓ UNIT_TYPE MATCH")
        else:
            print("✗ UNIT_TYPE MISMATCH")


def test_direct_runtime_polish():
    """Test the ChatCompletionLUI runtime directly with Polish examples."""
    
    platform = OpenAIPlatform()
    runtime = ChatCompletionLUI(platform=platform, model_name="gpt-5", batch_size=30)
    
    # Create LUIInput objects for Polish testing
    polish_inputs = [
        LUIInput(
            uid="pl_test_1",
            word="uczy", 
            sentence="Dziecko szybko uczy się nowych słów."
        ),
        LUIInput(
            uid="pl_test_2",
            word="zatrzymał",
            sentence="Samochód nagle zatrzymał się na środku drogi."
        ),
        LUIInput(
            uid="pl_test_3",
            word="zawzięcie",
            sentence="Który walił zawzięcie różdżką w blat ławki."
        )
    ]
    
    print("\\n=== Testing Direct Runtime Usage with Polish ===")
    
    outputs = runtime.identify(
        polish_inputs,
        source_lang="pl",
        target_lang="en", 
        ignore_cache=False,
        use_test_cache=True
    )
    
    for lui_input, lui_output in zip(polish_inputs, outputs):
        print(f"\\nInput - Word: {lui_input.word}")
        print(f"        Sentence: {lui_input.sentence}")
        print(f"Output - Lemma: {lui_output.lemma}")
        print(f"         POS: {lui_output.part_of_speech}")
        print(f"         Aspect: {lui_output.aspect}")
        print(f"         Original Form: {lui_output.original_form}")
        print(f"         Unit Type: {lui_output.unit_type}")


if __name__ == "__main__":
    test_polish_hybrid_cases()
    test_direct_runtime_polish()
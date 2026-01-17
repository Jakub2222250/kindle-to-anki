#!/usr/bin/env python3
"""
Test for Polish hybrid lexical unit identification using the new task structure.
This replaces the old test_lui_polish_hybrid.py with tests for the new provider pattern.
Since the Polish hybrid runtime hasn't been implemented yet, this test uses the 
ChatCompletionLUI runtime but includes test cases from the original Polish hybrid tests.
"""

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.tasks.lui.runtime_chat_completion import ChatCompletionLUI
from kindle_to_anki.tasks.lui.provider import LUIProvider
from kindle_to_anki.tasks.lui.schema import LUIInput, LUIOutput

bootstrap_all()


def test_polish_hybrid_cases():
    """Test Polish-specific cases using the new LUI provider pattern."""

    # Test cases from the original Polish hybrid tests
    test_cases = [
        {
            'word': 'uczy',
            'sentence': 'Dziecko szybko uczy się nowych słów.',
            'expected_lemma': 'uczyć się',
            'expected_surface_lexical_unit': 'uczy się',
            'expected_pos': 'verb',
            'expected_aspect': 'impf'
        },
        {
            'word': 'uczy',
            'sentence': 'Nauczyciel uczy dzieci matematyki.',
            'expected_lemma': 'uczyć',
            'expected_surface_lexical_unit': 'uczy',
            'expected_pos': 'verb',
            'expected_aspect': 'impf'
        },
        {
            'word': 'zatrzymał',
            'sentence': 'Samochód nagle zatrzymał się na środku drogi.',
            'expected_lemma': 'zatrzymać się',
            'expected_surface_lexical_unit': 'zatrzymał się',
            'expected_pos': 'verb',
            'expected_aspect': 'perf'
        },
        {
            'word': 'Otworzył',
            'sentence': 'Otworzył drzwi bez pukania.',
            'expected_lemma': 'otworzyć',
            'expected_surface_lexical_unit': 'Otworzył',
            'expected_pos': 'verb',
            'expected_aspect': 'perf'
        },
        {
            'word': 'zawzięcie',
            'sentence': 'Który walił zawzięcie różdżką w blat ławki.',
            'expected_lemma': 'zawzięcie',
            'expected_surface_lexical_unit': 'zawzięcie',
            'expected_pos': 'adverb',
            'expected_aspect': ''
        }
    ]

    # Create AnkiNote objects from test cases
    notes = []
    for i, test_case in enumerate(test_cases):
        note = AnkiNote(
            word=test_case['word'],
            usage=test_case['sentence'],
            language="pl",
            uid=f"test_pl_hybrid_{i + 1}",
            book_name="Test Book",
            position=f"loc_{i + 1}"
        )
        notes.append(note)

    # Setup runtime and config
    runtime = ChatCompletionLUI()
    runtime_config = RuntimeConfig(model_id="gpt-5.1", batch_size=30, source_language_code="pl", target_language_code="en")

    # Setup the provider
    runtimes = {"chat_completion_lui": runtime}
    provider = LUIProvider(runtimes=runtimes)

    print("\n=== Testing Polish LUI Cases with Provider ===")

    # Test via provider
    provider.identify(
        notes=notes,
        runtime_choice="chat_completion_lui",
        runtime_config=runtime_config,
        ignore_cache=False,
        use_test_cache=True
    )

    # Validate results
    for i, test_case in enumerate(test_cases):
        note = notes[i]

        # Determine expected unit_type based on whether się appears in the expected lemma
        expected_unit_type = "reflexive" if "się" in test_case['expected_lemma'] else "lemma"

        print(f"\n--- Test Case {i + 1}: {test_case['word']} ---")
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

    runtime = ChatCompletionLUI()
    runtime_config = RuntimeConfig(model_id="gpt-5.1", batch_size=30, source_language_code="pl", target_language_code="en")

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

    print("\n=== Testing Direct Runtime Usage with Polish ===")

    outputs = runtime.identify(
        polish_inputs,
        runtime_config=runtime_config,
        ignore_cache=False,
        use_test_cache=True
    )

    for lui_input, lui_output in zip(polish_inputs, outputs):
        print(f"\nInput - Word: {lui_input.word}")
        print(f"        Sentence: {lui_input.sentence}")
        print(f"Output - Lemma: {lui_output.lemma}")
        print(f"         POS: {lui_output.part_of_speech}")
        print(f"         Aspect: {lui_output.aspect}")
        print(f"         Surface Lexical Unit: {lui_output.surface_lexical_unit}")
        print(f"         Unit Type: {lui_output.unit_type}")


if __name__ == "__main__":
    test_polish_hybrid_cases()
    test_direct_runtime_polish()

#!/usr/bin/env python3
"""
Simple test script to verify the new LLM-based morphological analysis works correctly.
"""

from ma.ma import process_morphological_enrichment
from anki.anki_note import AnkiNote
import sys
from pathlib import Path

# Add the project root to the path so we can import modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def create_test_note(word, sentence, language, uid_suffix=""):
    """Create a test note for morphological analysis"""
    return AnkiNote(
        word=word,
        stem="",
        usage=sentence,
        language=language,
        book_name="Test Book",
        position=f"test-{uid_suffix}",
        timestamp="2024-01-01T12:00:00Z",
        uid=f"test_{word}_{uid_suffix}"
    )


def test_llm_morphological_analysis():
    """Test the LLM-based morphological analysis with various languages"""

    print("=== Testing LLM-based Morphological Analysis ===\n")

    test_cases = [
        # Polish reflexive verbs
        {
            "word": "boi",
            "sentence": "On się nie boi ciemności.",
            "language": "pl",
            "description": "Polish reflexive verb (bać się)"
        },
        {
            "word": "myje",
            "sentence": "Myje naczynia po obiedzie.",
            "language": "pl", 
            "description": "Polish non-reflexive verb"
        },
        {
            "word": "myje",
            "sentence": "Myje się codziennie rano.",
            "language": "pl",
            "description": "Polish reflexive verb (myć się)"
        },
        # Spanish
        {
            "word": "corriendo",
            "sentence": "El niño está corriendo en el parque.",
            "language": "es",
            "description": "Spanish progressive verb form"
        },
        {
            "word": "me",
            "sentence": "Me gusta mucho la música.",
            "language": "es", 
            "description": "Spanish reflexive/indirect object"
        },
        # German
        {
            "word": "sich",
            "sentence": "Er freut sich über das Geschenk.",
            "language": "de",
            "description": "German reflexive pronoun"
        },
        {
            "word": "läuft",
            "sentence": "Er läuft schnell zur Schule.",
            "language": "de",
            "description": "German verb form"
        }
    ]

    for i, test_case in enumerate(test_cases):
        print(f"\n--- Test Case {i + 1}: {test_case['description']} ---")
        print(f"Word: {test_case['word']}")
        print(f"Sentence: {test_case['sentence']}")
        print(f"Language: {test_case['language']}")

        # Create test note
        note = create_test_note(
            test_case['word'],
            test_case['sentence'],
            test_case['language'],
            str(i + 1)
        )

        # Process with LLM (using cache, ignore_cache=False for efficiency in testing)
        try:
            process_morphological_enrichment(
                [note], 
                test_case['language'], 
                "en",  # target language
                ignore_cache=False,
                use_hybrid=False  # Force LLM usage
            )

            print(f"Results:")
            print(f"  Lemma: {note.expression}")
            print(f"  Part of Speech: {note.part_of_speech}")
            print(f"  Aspect: {note.aspect}")
            print(f"  Original Form: {note.original_form}")

        except Exception as e:
            print(f"ERROR: {str(e)}")
            print("This might be expected if OpenAI API key is not configured.")


def test_hybrid_vs_llm():
    """Test comparison between hybrid (Polish) and LLM approaches"""

    print("\n\n=== Testing Hybrid vs LLM (Polish only) ===\n")

    test_word = "boi"
    test_sentence = "On się nie boi ciemności."

    # Test with LLM
    note_llm = create_test_note(test_word, test_sentence, "pl", "llm")

    # Test with hybrid (if available)
    note_hybrid = create_test_note(test_word, test_sentence, "pl", "hybrid")

    try:
        print("Testing LLM approach:")
        process_morphological_enrichment(
            [note_llm], "pl", "en", 
            ignore_cache=False, use_hybrid=False
        )
        print(f"  LLM Results - Lemma: {note_llm.expression}, POS: {note_llm.part_of_speech}, Original: {note_llm.original_form}")

        print("\nTesting Hybrid approach:")
        process_morphological_enrichment(
            [note_hybrid], "pl", "en", 
            ignore_cache=False, use_hybrid=True
        )
        print(f"  Hybrid Results - Lemma: {note_hybrid.expression}, POS: {note_hybrid.part_of_speech}, Original: {note_hybrid.original_form}")

    except Exception as e:
        print(f"ERROR: {str(e)}")
        print("This might be expected if dependencies are missing or API key is not configured.")


if __name__ == "__main__":
    test_llm_morphological_analysis()
    test_hybrid_vs_llm()
    print("\n=== Test completed ===")

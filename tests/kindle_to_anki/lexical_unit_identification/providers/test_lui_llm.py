#!/usr/bin/env python3
"""
Integration test for LLM-based lexical unit identification.
"""

from kindle_to_anki.lexical_unit_identification.providers.lui_llm import process_notes_with_llm_lui
from kindle_to_anki.anki.anki_note import AnkiNote


def test_lui_llm():
    """Test LLM-based lexical unit identification with multiple languages."""
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

    # Test with different languages
    for lang_code in ["pl", "es", "de"]:
        lang_notes = [note for note in test_notes if note.kindle_language == lang_code]
        if lang_notes:
            print(f"\n=== Testing {lang_code} ===")
            process_notes_with_llm_lui(lang_notes, lang_code, "en", ignore_cache=False, use_test_cache=True)

            for note in lang_notes:
                print(f"Word: {note.kindle_word}")
                print(f"Sentence: {note.kindle_usage}")
                print(f"Lemma: {note.expression}")
                print(f"POS: {note.part_of_speech}")
                print(f"Aspect: {note.aspect}")
                print(f"Original Form: {note.original_form}")
                print()


if __name__ == "__main__":
    test_lui_llm()
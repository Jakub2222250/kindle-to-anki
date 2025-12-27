#!/usr/bin/env python3
"""
Integration test for Polish local translation.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))

from translation.providers.polish_translator_local import translate_polish_context_to_english
from anki.anki_note import AnkiNote


def test_polish_translator_local():
    """Test Polish context translation to English."""
    
    # Example usage
    notes = [
        AnkiNote(
            word="przykład",
            stem="przykład",
            usage="To jest przykład zdania.",
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

    translate_polish_context_to_english(notes, ignore_cache=False, use_test_cache=True)

    print()
    for note in notes:
        print(f"Original: {note.context_sentence}")
        print(f"Translated: {note.context_translation}")


if __name__ == "__main__":
    test_polish_translator_local()
#!/usr/bin/env python3
"""
Integration test for LLM-based translation.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))

from kindle_to_anki.translation.providers.translator_llm import translate_context_with_llm
from kindle_to_anki.anki.anki_note import AnkiNote


def test_translator_llm():
    """Test LLM-based context translation."""
    
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

    translate_context_with_llm(notes, "pl", "en", ignore_cache=False, use_test_cache=True)

    print()
    for note in notes:
        print(f"Original: {note.context_sentence}")
        print(f"Translated: {note.context_translation}")


if __name__ == "__main__":
    test_translator_llm()
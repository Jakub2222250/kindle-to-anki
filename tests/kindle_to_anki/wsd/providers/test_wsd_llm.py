#!/usr/bin/env python3
"""
Integration test for Word Sense Disambiguation via LLM.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))

from wsd.providers.wsd_llm import provide_wsd_with_llm
from anki.anki_note import AnkiNote


def test_wsd_llm():
    """Integration test of Word Sense Disambiguation via LLM - focus on plural forms with singular lemmas."""
    
    test_cases = [
        {
            'kindle_word': 'dzieci',  # plural
            'lemma': 'dziecko',       # singular
            'sentence': 'Dzieci bawią się na placu zabaw.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'koty',    # plural
            'lemma': 'kot',           # singular
            'sentence': 'Koty lubią spać w słońcu.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'domy',    # plural
            'lemma': 'dom',           # singular
            'sentence': 'Domy na tej ulicy są bardzo stare.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'książki',  # plural
            'lemma': 'książka',       # singular
            'sentence': 'Książki leżą na półce w bibliotece.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'ludzie',  # plural
            'lemma': 'człowiek',      # singular (irregular)
            'sentence': 'Ludzie czekają na autobus.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'oczy',    # plural
            'lemma': 'oko',           # singular
            'sentence': 'Jego oczy błyszczą w ciemności.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'ręce',    # plural
            'lemma': 'ręka',          # singular
            'sentence': 'Mył ręce przed jedzeniem.',
            'pos': 'noun'
        },
        {
            'kindle_word': 'pieniądze',  # plural
            'lemma': 'pieniądz',        # singular
            'sentence': 'Pieniądze leżą na stole.',
            'pos': 'noun'
        }
    ]

    notes = []
    for i, test_case in enumerate(test_cases):
        note = AnkiNote(test_case['kindle_word'], "", test_case['sentence'], "pl", "Test Book", f"loc_{i + 1}", "")
        # Set the lemma form that MA would have provided
        note.expression = test_case['lemma']
        note.pos_tag = test_case['pos']
        notes.append(note)

    print("=" * 80)
    print("WORD SENSE DISAMBIGUATION VIA LLM INTEGRATION TEST")
    print("=" * 80)
    print("Testing plural forms with singular lemmas to assess if definitions match lemma forms")
    print()

    provide_wsd_with_llm(notes, "pl", "en", ignore_cache=False, use_test_cache=True)

    print("\n" + "=" * 80)
    print("TEST RESULTS FOR MANUAL ASSESSMENT")
    print("=" * 80)

    for i, test_case in enumerate(test_cases):
        note = notes[i]
        print(f"\nTest Case {i + 1}:")
        print(f"  Original word (plural): {note.kindle_word}")
        print(f"  Lemma (singular):       {note.expression}")
        print(f"  Sentence:               {note.kindle_usage}")
        print(f"  Definition:             {note.definition}")
        print(f"  Polish definition:      {note.original_language_hint}")
        print(f"  Cloze score:            {note.cloze_enabled}")
        print("-" * 60)


if __name__ == "__main__":
    test_wsd_llm()
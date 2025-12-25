#!/usr/bin/env python3
"""
Integration test for Polish hybrid lexical unit identification.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))

from kindle_to_anki.lexical_unit_identification.providers.lui_polish_hybrid import process_notes_with_morfeusz
from kindle_to_anki.anki.anki_note import AnkiNote


def test_lui_polish_hybrid():
    """Integration test of the top level function of this module"""
    
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
            'expected_pos': 'adv',
            'expected_aspect': ''
        },
        {
            'kindle_word': 'zawzięcie',
            'sentence': 'Jego zawzięcie było godne podziwu.',
            'expected_lemma': 'zawziąć',
            'expected_original_form': 'zawzięcie',
            'expected_pos': 'noun',
            'expected_aspect': ''
        },
        {
            'kindle_word': 'podoba',
            'sentence': 'Ten obraz podoba się dzieciom.',
            'expected_lemma': 'podobać się',
            'expected_original_form': 'podoba się',
            'expected_pos': 'verb',
            'expected_aspect': 'impf'
        },
        {
            'kindle_word': 'Mył',
            'sentence': 'Mył naczynia po obiedzie.',
            'expected_lemma': 'myć',
            'expected_original_form': 'Mył',
            'expected_pos': 'verb',
            'expected_aspect': 'impf'
        },
        {
            'kindle_word': 'Mył się',
            'sentence': 'Mył się codziennie rano.',
            'expected_lemma': 'myć się',
            'expected_original_form': 'Mył się',
            'expected_pos': 'verb',
            'expected_aspect': 'impf'
        },
        {
            'kindle_word': 'Bił',
            'sentence': 'Bił się z bratem w dzieciństwie.',
            'expected_lemma': 'bić się',
            'expected_original_form': 'Bił się',
            'expected_pos': 'verb',
            'expected_aspect': 'impf'
        },
        {
            'kindle_word': 'Bił',
            'sentence': 'Bił rekord świata w pływaniu.',
            'expected_lemma': 'bić',
            'expected_original_form': 'Bił',
            'expected_pos': 'verb',
            'expected_aspect': 'impf'
        },
        {
            'kindle_word': 'nadzieja',
            'sentence': 'Mam nadzieję na dobrą ocenę.',
            'expected_lemma': 'nadzieja',
            'expected_original_form': 'nadzieja',
            'expected_pos': 'noun',
            'expected_aspect': ''
        },
        {
            'kindle_word': 'szybko',
            'sentence': 'Biegł szybko do szkoły.',
            'expected_lemma': 'szybko',
            'expected_original_form': 'szybko',
            'expected_pos': 'adv',
            'expected_aspect': ''
        },
        {
            'kindle_word': 'boi',
            'sentence': 'On się nie boi ciemności.',
            'expected_lemma': 'bać się',
            'expected_original_form': 'się nie boi',
            'expected_pos': 'verb',
            'expected_aspect': 'impf'
        },
        {
            'kindle_word': 'piękną',
            'sentence': 'Podziwiał piękną rzeźbę w muzeum.',
            'expected_lemma': 'piękny',
            'expected_original_form': 'piękną',
            'expected_pos': 'adj',
            'expected_aspect': ''
        },
        {
            'kindle_word': 'zjawy',
            'sentence': 'Nie pozbyłem się zjawy z Bandonu.',
            'expected_lemma': 'zjawa',
            'expected_original_form': 'zjawy',
            'expected_pos': 'noun',
            'expected_aspect': ''
        }
    ]

    notes = []
    for i, test_case in enumerate(test_cases):
        note = AnkiNote(test_case['kindle_word'], "", test_case['sentence'], "pl", "Test Book", f"loc_{i + 1}", "")
        notes.append(note)

    process_notes_with_morfeusz(notes, cache_suffix='pl-en_hybrid_test', ignore_cache=False)

    for i, test in enumerate(test_cases):
        note = notes[i]

        # Determine expected unit_type based on whether się appears in the expected lemma
        expected_unit_type = "reflexive" if "się" in test['expected_lemma'] else "lemma"

        if test['expected_lemma'] != note.expression:
            print(f"Test FAILED for word '{note.kindle_word}' in sentence '{note.kindle_usage}': expected lemma '{test['expected_lemma']}', got '{note.expression}'")
        else:
            print(f"Test PASSED for word '{note.kindle_word}' in sentence '{note.kindle_usage}': got expected lemma '{note.expression}'")

        if test['expected_original_form'] != note.original_form:
            print(f"Test FAILED for word '{note.kindle_word}' in sentence '{note.kindle_usage}': expected original form '{test['expected_original_form']}', got '{note.original_form}'")
        else:
            print(f"Test PASSED for word '{note.kindle_word}' in sentence '{note.kindle_usage}': got expected original form '{note.original_form}'")

        if test['expected_pos'] != note.part_of_speech:
            print(f"Test FAILED for word '{note.kindle_word}' in sentence '{note.kindle_usage}': expected pos '{test['expected_pos']}', got '{note.part_of_speech}'")
        else:
            print(f"Test PASSED for word '{note.kindle_word}' in sentence '{note.kindle_usage}': got expected pos '{note.part_of_speech}'")

        if test['expected_aspect'] != note.aspect:
            print(f"Test FAILED for word '{note.kindle_word}' in sentence '{note.kindle_usage}': expected aspect '{test['expected_aspect']}', got '{note.aspect}'")
        else:
            print(f"Test PASSED for word '{note.kindle_word}' in sentence '{note.kindle_usage}': got expected aspect '{note.aspect}'")

        if expected_unit_type != note.unit_type:
            print(f"Test FAILED for word '{note.kindle_word}' in sentence '{note.kindle_usage}': expected unit_type '{expected_unit_type}', got '{note.unit_type}'")
        else:
            print(f"Test PASSED for word '{note.kindle_word}' in sentence '{note.kindle_usage}': got expected unit_type '{note.unit_type}'")


if __name__ == "__main__":
    test_lui_polish_hybrid()
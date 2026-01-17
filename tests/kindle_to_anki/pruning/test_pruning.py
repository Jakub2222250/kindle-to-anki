#!/usr/bin/env python3
"""
Integration test for pruning functionality.
"""

from kindle_to_anki.pruning.pruning import prune_existing_notes_automatically
from kindle_to_anki.anki.anki_note import AnkiNote


def test_prune_existing_notes_automatically():
    """Integration test for prune_existing_notes_automatically function."""

    print("Testing prune_existing_notes_automatically function...")

    # Test cases with expected results
    test_cases = [
        {
            'expression': 'czytać',
            'part_of_speech': 'verb',
            'definition': 'to read books or texts',
            'word': 'czyta',
            'sentence': 'Jan często czyta książki w bibliotece.',
            'expected_retained': False  # Should be pruned due to similar definition
        },
        {
            'expression': 'biegać',
            'part_of_speech': 'verb',
            'definition': 'to run for exercise or sport',
            'word': 'biega',
            'sentence': 'Maria biega każdego ranka w parku.',
            'expected_retained': True  # Different definition, should be retained
        },
        {
            'expression': 'dom',
            'part_of_speech': 'noun',
            'definition': 'a building where people live, house',
            'word': 'dom',
            'sentence': 'Nasz dom znajduje się na wsi.',
            'expected_retained': False  # Should be pruned due to very similar definition
        },
        {
            'expression': 'szybko',
            'part_of_speech': 'adv',
            'definition': 'at high speed, quickly',
            'word': 'szybko',
            'sentence': 'Samochód jedzie bardzo szybko.',
            'expected_retained': True  # No matching existing note, should be retained
        },
        {
            'expression': 'biegać',
            'part_of_speech': 'noun',
            'definition': 'the act of running',
            'word': 'biegać',
            'sentence': 'Biegać to dobry sposób na ćwiczenie.',
            'expected_retained': True  # Different POS from existing note, should be retained
        }
    ]

    # Create test notes from test cases
    notes = []
    for i, test_case in enumerate(test_cases):
        note = AnkiNote(
            word=test_case['word'],
            usage=test_case['sentence'],
            language="pl",
            uid=f"test_pruning_{i + 1}",
            book_name="Test Book",
            position=f"loc_{i + 1}"
        )
        note.expression = test_case['expression']
        note.part_of_speech = test_case['part_of_speech']
        note.definition = test_case['definition']
        notes.append(note)

    # Create mock existing notes (simulating anki_connect.get_notes() response format)
    existing_notes = [
        {
            'UID': 'test_uid_1',
            'Expression': 'czytać',
            'Part_Of_Speech': 'verb',
            'Definition': 'to read written material',  # Similar to test case 1
            'Context_Sentence': 'Lubię czytać powieści.',
            'Context_Translation': 'I like to read novels.'
        },
        {
            'UID': 'test_uid_2',
            'Expression': 'biegać',
            'Part_Of_Speech': 'verb',
            'Definition': 'to move quickly on foot',  # Different from test case 2
            'Context_Sentence': 'Nie lubię biegać.',
            'Context_Translation': 'I don\'t like to run.'
        },
        {
            'UID': 'test_uid_3',
            'Expression': 'dom',
            'Part_Of_Speech': 'noun',
            'Definition': 'a dwelling, house where people reside',  # Very similar to test case 3
            'Context_Sentence': 'To jest mój dom.',
            'Context_Translation': 'This is my house.'
        }
    ]

    # Test the pruning function with auto_prune=True to skip user input
    pruned_notes = prune_existing_notes_automatically(notes, existing_notes, cache_suffix='pl-en_test')

    # Check results for each test case
    for test_case in test_cases:
        # Find the corresponding note in results
        note_retained = any(note.expression == test_case['expression'] and 
                            note.part_of_speech == test_case['part_of_speech'] and
                            note.definition == test_case['definition']
                            for note in pruned_notes)

        if test_case['expected_retained'] == note_retained:
            status = "PASSED"
        else:
            status = "FAILED"

        action = "retained" if note_retained else "pruned"
        expected_action = "retained" if test_case['expected_retained'] else "pruned"

        print(f"Test {status} for word '{test_case['expression']}' ({test_case['part_of_speech']}): expected {expected_action}, got {action}")

    print(f"\nSummary: {len(notes)} original notes, {len(pruned_notes)} retained after pruning")


if __name__ == "__main__":
    test_prune_existing_notes_automatically()

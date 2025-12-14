import textwrap
from anki.anki_note import AnkiNote
from thefuzz import fuzz


def prune_existing_notes_by_UID(notes: list[AnkiNote], existing_notes: list[dict]):
    """Remove notes that already exist in Anki based on UID"""

    if len(notes) == 0:
        return notes

    existing_uids = {note['UID'] for note in existing_notes if note['UID']}

    # Filter out notes that already exist
    new_notes = [note for note in notes if note.uid not in existing_uids]

    pruned_count = len(notes) - len(new_notes)
    if pruned_count > 0:
        print(f"Pruned {pruned_count} notes that already exist in Anki (based on UID)")

    return new_notes


def prune_existing_notes_by_expression(notes: list[AnkiNote], existing_notes: list[dict]):
    """ Option to opt out of expensive LLM activity for notes that already exist in Anki based on Expression field"""

    if len(notes) == 0:
        return notes

    print("\nChecking for notes with existing expressions in Anki...")

    existing_expressions = {note['Expression'] for note in existing_notes if note['Expression']}
    new_notes_that_are_duplicates = [note for note in notes if note.expression in existing_expressions]
    num_of_new_notes_that_are_duplicates = len(new_notes_that_are_duplicates)

    if num_of_new_notes_that_are_duplicates > 0:
        for note in new_notes_that_are_duplicates:
            print(f"  Found existing expression in Anki: {note.expression}")

        response = input(f"Process {num_of_new_notes_that_are_duplicates} notes with existing expressions? (Y/n): ").strip().lower()
        if response != 'y' and response != 'yes':
            print(f"Skipping {num_of_new_notes_that_are_duplicates} notes with existing expressions.")
            notes = [note for note in notes if note.expression not in existing_expressions]
    else:
        print("No notes with existing expressions found in Anki.")

    return notes


def evaluate_gloss_similarity(gloss1, gloss2) -> int:
    """Check if two glosses are pretty similar based on shared words."""
    return fuzz.token_set_ratio(gloss1, gloss2)


def prune_existing_notes_automatically(notes: list[AnkiNote], existing_notes: list[dict], auto_prune=False):

    pruned_notes = []

    for note in notes:
        is_redundant = False
        for existing_note in existing_notes:
            if note.expression == existing_note['Expression'] and note.part_of_speech == existing_note['Part_Of_Speech']:
                similarity_factor = evaluate_gloss_similarity(note.definition, existing_note['Definition'])
                print(f"Evaluating note for {note.expression}: similarity factor = {similarity_factor}%")
                if similarity_factor > 45:
                    is_redundant = True
                    if not auto_prune:
                        print(f"Note for {note.expression} detected as redundant due to high similarity_factor ({similarity_factor}%) with existing note.")
                    break
        if not is_redundant:
            pruned_notes.append(note)

    if len(pruned_notes) < len(notes):
        pruned_count = len(notes) - len(pruned_notes)

        if auto_prune:
            # Default behavior: omit redundant notes without prompting
            print("Redundant notes omitted automatically.")
            return pruned_notes

        print(f"{pruned_count} notes redundant to existing Anki notes (based on Expression, Part_Of_Speech, and Definition similarity)")

        result = input("Create notes for redundant entries anyway? (y/N): ").strip().lower()
        if result != 'y' and result != 'yes':
            print("Redundant notes omitted.")
        else:
            print("Redundant notes retained.")
            return notes

    return pruned_notes


if __name__ == "__main__":
    from anki.anki_note import AnkiNote

    # Integration test for prune_existing_notes_automatically
    print("Testing prune_existing_notes_automatically function...")

    # Test cases with expected results
    test_cases = [
        {
            'expression': 'czytać',
            'part_of_speech': 'verb',
            'definition': 'to read books or texts',
            'kindle_word': 'czyta',
            'sentence': 'Jan często czyta książki w bibliotece.',
            'expected_retained': False  # Should be pruned due to similar definition
        },
        {
            'expression': 'biegać',
            'part_of_speech': 'verb',
            'definition': 'to run for exercise or sport',
            'kindle_word': 'biega',
            'sentence': 'Maria biega każdego ranka w parku.',
            'expected_retained': True  # Different definition, should be retained
        },
        {
            'expression': 'dom',
            'part_of_speech': 'noun',
            'definition': 'a building where people live, house',
            'kindle_word': 'dom',
            'sentence': 'Nasz dom znajduje się na wsi.',
            'expected_retained': False  # Should be pruned due to very similar definition
        },
        {
            'expression': 'szybko',
            'part_of_speech': 'adv',
            'definition': 'at high speed, quickly',
            'kindle_word': 'szybko',
            'sentence': 'Samochód jedzie bardzo szybko.',
            'expected_retained': True  # No matching existing note, should be retained
        },
        {
            'expression': 'biegać',
            'part_of_speech': 'noun',
            'definition': 'the act of running',
            'kindle_word': 'biegać',
            'sentence': 'Biegać to dobry sposób na ćwiczenie.',
            'expected_retained': True  # Different POS from existing note, should be retained
        }
    ]

    # Create test notes from test cases
    notes = []
    for i, test_case in enumerate(test_cases):
        note = AnkiNote(test_case['kindle_word'], "", test_case['sentence'], "pl", "Test Book", f"loc_{i + 1}", "")
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
    pruned_notes = prune_existing_notes_automatically(notes, existing_notes, auto_prune=True)

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

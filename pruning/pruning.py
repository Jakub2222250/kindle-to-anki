import textwrap
from anki.anki_note import AnkiNote


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

        response = input(f"Process {num_of_new_notes_that_are_duplicates} notes with existing expressions? (y/n): ").strip().lower()
        if response != 'y' and response != 'yes':
            print(f"Skipping {num_of_new_notes_that_are_duplicates} notes with existing expressions.")
            notes = [note for note in notes if note.expression not in existing_expressions]
    else:
        print("No notes with existing expressions found in Anki.")

    return notes


def prune_existing_notes_manually(notes: list[AnkiNote], existing_notes: list[dict]):
    """Offer user to manually prune notes that exist in Anki based on Expression field"""
    if len(notes) == 0:
        return notes

    map_existing_expressions_to_notes = {}
    for existing_note in existing_notes:
        expr = existing_note['Expression']
        if expr not in map_existing_expressions_to_notes:
            map_existing_expressions_to_notes[expr] = []
        map_existing_expressions_to_notes[expr].append(existing_note)

    num_of_new_notes_that_are_duplicates = sum(1 for note in notes if note.expression in map_existing_expressions_to_notes)

    if num_of_new_notes_that_are_duplicates == 0:
        return notes

    pruned_notes = []

    print(f"\nFound {num_of_new_notes_that_are_duplicates} new notes with pre-existing expressions in Anki.")
    manually_prune = input("Would you like to manually prune these notes? (y/n): ").strip().lower()
    if manually_prune != 'y' and manually_prune != 'yes':
        include_all = input("Include all new notes with pre-existing expressions? (y/n): ").strip().lower()
        if include_all != 'y' and include_all != 'yes':
            return notes
        else:
            for note in notes:
                if note in map_existing_expressions_to_notes[note.expression]:
                    print(f"Omitting word: {note.expression}")
                    continue
                pruned_notes.append(note)
            return pruned_notes

    # Opted for manual route pruning
    for note in notes:
        if note.expression in map_existing_expressions_to_notes:
            existing_notes = map_existing_expressions_to_notes[note.expression]
            print(f"\n{note.expression}:")
            for existing_note in existing_notes:
                print(f"\n\t{existing_note['UID']}")
                print(textwrap.fill(f"Definition      : {existing_note['Definition']}", width=100, initial_indent="\t\t", subsequent_indent="\t\t"))
                print()
                print(textwrap.fill(f"Context Sentence: {existing_note['Context_Sentence']}", width=100, initial_indent="\t\t", subsequent_indent="\t\t"))
                print()
                print(textwrap.fill(f"Context Translation: {existing_note['Context_Translation']}", width=100, initial_indent="\t\t", subsequent_indent="\t\t"))
            print("\n\t Candidate note:")
            print(textwrap.fill(f"Definition      : {note.definition}", width=100, initial_indent="\t\t", subsequent_indent="\t\t"))
            print()
            print(textwrap.fill(f"Context Sentence: {note.context_sentence}", width=100, initial_indent="\t\t", subsequent_indent="\t\t"))
            print()
            print(textwrap.fill(f"Context Translation: {note.context_translation}", width=100, initial_indent="\t\t", subsequent_indent="\t\t"))
            response = input("\nAdd this note to Anki? (y/n): ").strip().lower()
            if response != 'y' and response != 'yes':
                print(f"Omitting candidate note for: {note.expression}")
                continue
            else:
                pruned_notes.append(note)
        else:
            pruned_notes.append(note)

    return pruned_notes

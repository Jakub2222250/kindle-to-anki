import json
import time
from pathlib import Path

from anki.anki_note import AnkiNote
from thefuzz import fuzz


class PruningCache:
    def __init__(self, cache_dir=".cache", cache_suffix='default'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / f"pruning_cache_{cache_suffix}.json"

        # Load existing cache
        self.cache = self.load_cache()

    def load_cache(self):
        """Load cache from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}

    def save_cache(self):
        """Save cache to file"""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def get(self, uid):
        """Get cached pruning result for UID"""
        cache_entry = self.cache.get(uid)
        if cache_entry and isinstance(cache_entry, dict) and "pruning_data" in cache_entry:
            return cache_entry["pruning_data"]
        return None

    def set(self, uid, is_redundant, similarity_factor=None, matched_expression=None, timestamp=None):
        """Set cached pruning result for UID"""
        cache_entry = {
            "pruning_data": {
                "is_redundant": is_redundant,
                "similarity_factor": similarity_factor,
                "matched_expression": matched_expression
            },
            "timestamp": timestamp
        }
        self.cache[uid] = cache_entry
        self.save_cache()


def prune_notes_identified_as_redundant(notes: list[AnkiNote], cache_suffix: str):
    """Remove notes that were previously identified as redundant based on cached results"""

    print("\nPruning notes previously identified as redundant...")

    if len(notes) == 0:
        return notes

    cache = PruningCache(cache_suffix=cache_suffix)
    print(f"Loaded pruning cache with {len(cache.cache)} entries")

    # Filter out notes that are cached as redundant
    non_redundant_notes = []
    cached_redundant_count = 0

    for note in notes:
        cached_result = cache.get(note.uid)
        if cached_result and cached_result.get('is_redundant', False):
            cached_redundant_count += 1
            print(f"  Pruning cached redundant note: {note.expression}")
        else:
            non_redundant_notes.append(note)

    print(f"Pruned {cached_redundant_count} notes previously identified as redundant")

    return non_redundant_notes


def prune_existing_notes_by_UID(notes: list[AnkiNote], existing_notes: list[dict]):
    """Remove notes that already exist in Anki based on UID"""

    print("\nPruning notes that already exist in Anki based on UID...")

    if len(notes) == 0:
        return notes

    existing_uids = {note['UID'] for note in existing_notes if note['UID']}

    # Filter out notes that already exist
    new_notes = [note for note in notes if note.uid not in existing_uids]

    pruned_count = len(notes) - len(new_notes)
    print(f"Pruned {pruned_count} notes that already exist in Anki (based on UID)")

    return new_notes


def prune_existing_notes_by_expression(notes: list[AnkiNote], existing_notes: list[dict]):
    """ Option to opt out of expensive LLM activity for notes that already exist in Anki based on Expression field
        TODO: Let each language define an expression + pos based pruning function if needed
    """

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


def prune_new_notes_against_eachother(notes: list[AnkiNote]):
    """Gather groups of notes with the same Expression, Part_Of_Speech, and similar Definition to prune duplicates among new notes.
       Choose the note with the highest cloze_deletion_score value, or the longest context_sentence, or the first one as a tiebreaker."""

    print("\nPruning duplicate notes among new notes based on Expression, Part_Of_Speech, and Definition similarity...")

    if len(notes) == 0:
        return notes

    # Initialize cache
    processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # Group notes by (expression, part_of_speech)
    groups = {}
    for note in notes:
        key = (note.expression, note.part_of_speech)
        if key not in groups:
            groups[key] = []
        groups[key].append(note)

    pruned_notes = []

    for (expression, pos), group in groups.items():
        if len(group) == 1:
            # No duplicates in this group
            pruned_notes.append(group[0])
            continue

        # Find duplicates based on definition similarity
        processed = set()
        for i, note in enumerate(group):
            if i in processed:
                continue

            # Find all similar notes in this group
            similar_notes = [note]
            similar_indices = [i]

            for j, other_note in enumerate(group[i + 1:], start=i + 1):
                if j in processed:
                    continue

                similarity_factor = evaluate_gloss_similarity(note.definition, other_note.definition)
                if similarity_factor > 45:
                    similar_notes.append(other_note)
                    similar_indices.append(j)

            # Mark all similar notes as processed
            processed.update(similar_indices)

            if len(similar_notes) == 1:
                # No similar notes found, keep the original
                pruned_notes.append(note)
            else:
                # Choose the best note from similar ones
                best_note = choose_best_note(similar_notes)
                pruned_notes.append(best_note)

    pruned_count = len(notes) - len(pruned_notes)
    print(f"Pruned {pruned_count} duplicate notes among new notes based on similarity.")

    return pruned_notes


def choose_best_note(notes: list[AnkiNote]) -> AnkiNote:
    """Choose the best note from a list of similar notes based on priority criteria."""

    # Priority 1: Highest cloze_deletion_score value
    max_cloze = max(note.cloze_deletion_score for note in notes)
    cloze_candidates = [note for note in notes if note.cloze_deletion_score == max_cloze]

    if len(cloze_candidates) == 1:
        return cloze_candidates[0]

    # Priority 2: Longest context_sentence
    max_context_length = max(len(note.context_sentence) for note in cloze_candidates)
    context_candidates = [note for note in cloze_candidates if len(note.context_sentence) == max_context_length]

    if len(context_candidates) == 1:
        return context_candidates[0]

    # Priority 3: First one as tiebreaker
    return context_candidates[0]


def prune_existing_notes_automatically(notes: list[AnkiNote], existing_notes: list[dict], cache_suffix: str):

    print("\nAutomatically pruning notes redundant to existing Anki notes based on Expression, Part_Of_Speech, and Definition similarity...")

    # Initialize cache
    cache = PruningCache(cache_suffix=cache_suffix)
    processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    pruned_notes = []

    for note in notes:
        is_redundant = False
        similarity_factor = None
        matched_expression = None

        for existing_note in existing_notes:
            if note.expression == existing_note['Expression'] and note.part_of_speech == existing_note['Part_Of_Speech']:
                similarity_factor = evaluate_gloss_similarity(note.definition, existing_note['Definition'])
                if similarity_factor > 45:
                    is_redundant = True
                    matched_expression = existing_note['Expression']
                    print(f"Note for {note.expression} detected as redundant due to high similarity_factor ({similarity_factor}%) with existing note.")
                    break

        # Cache the result
        cache.set(note.uid, is_redundant, similarity_factor, matched_expression, processing_timestamp)

        if not is_redundant:
            pruned_notes.append(note)

    pruned_count = len(notes) - len(pruned_notes)

    print(f"Skipping {pruned_count} redundant notes based on Expression, Part_Of_Speech, and Definition similarity.")

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

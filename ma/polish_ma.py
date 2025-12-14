import morfeusz2

from ma.polish_ma_llm import update_notes_with_llm
from ma.polish_ma_sgjp_helper import morfeusz_tag_to_pos_string

'''
Polish morphological analyzer using Morfeusz2 and LLM.
morfeusz reliably produces list of all candidate analyses for a given word.
LLM is used to select the best candidate based on context (sentence) AND to handle words with "się" particle.
'''


def select_first_candidate(candidates):
    return candidates[0]


def update_note_without_llm(note):
    candidates = note.morfeusz_candidates
    _, _, interpretation = select_first_candidate(candidates)

    # Extract lemma and tag
    lemma_raw = interpretation[1]
    lemma = lemma_raw.split(':')[0] if ':' in lemma_raw else lemma_raw
    tag = interpretation[2]

    # Map SGJP tag to readable POS
    readable_pos = morfeusz_tag_to_pos_string(tag)

    note.expression = lemma
    note.part_of_speech = readable_pos


def benefits_from_llm_wsd(note):
    # Identify if the word contains "się" particle
    has_sie_before_or_after = False

    # Identify if the word has only one candidate
    has_single_candidate = len(note.morfeusz_candidates) == 1

    return not has_sie_before_or_after and not has_single_candidate


def process_notes_with_morfeusz(notes):

    morf = morfeusz2.Morfeusz()
    notes_benefiting_llm_wsd = []

    for note in notes:
        # Get candidates
        candidates = morf.analyse(note.kindle_word.lower())
        note.morfeusz_candidates = candidates

        benefits_from_llm_wsd = benefits_from_llm_wsd(note)

        # Simple case
        if not benefits_from_llm_wsd:
            update_note_without_llm(note)
        else:
            notes_benefiting_llm_wsd.append(note)

    for note in notes_benefiting_llm_wsd:
        # See if cache contains LLM results already and remove from list
        pass

    if len(notes_benefiting_llm_wsd) > 0:
        print(f"{len(notes_benefiting_llm_wsd)} notes need LLM MA processing.")
        result = input("Proceed? (No means using first candidate without reflexive analysis) [y/N]: ")
        if result.lower() != 'y' and result.lower() != 'yes':
            for note in notes_benefiting_llm_wsd:
                update_note_without_llm(note)
            return

        # Call LLM disambiguation function
        update_notes_with_llm(notes_benefiting_llm_wsd)


if __name__ == "__main__":

    morf = morfeusz2.Morfeusz()

    # Test morfeusz2 analysis
    test_words = ["pobiec", "piękny", "szybko", "dom", "iść", "czytać", "ładniejszy", "zawzięcie"]
    for word in test_words:

        candidates = morf.analyse(word.lower())

        # Select the first candidate (to be improved later with llm and się analysis)
        for _, _, interpretation in candidates:
            # Extract lemma and tag
            lemma_raw = interpretation[1]
            lemma = lemma_raw.split(':')[0] if ':' in lemma_raw else lemma_raw
            tag = interpretation[2]

            # Map SGJP tag to readable POS
            readable_pos = morfeusz_tag_to_pos_string(tag)

            print(f"Word: {word}, Lemma: {lemma}, POS: {readable_pos}")

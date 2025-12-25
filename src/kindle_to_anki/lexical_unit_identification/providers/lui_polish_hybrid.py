import string

from lexical_unit_identification.providers.pl_en.ma_polish_hybrid_llm import update_notes_with_llm
from lexical_unit_identification.providers.pl_en.ma_polish_sgjp_helper import morfeusz_tag_to_pos_string, normalize_lemma
from anki.anki_note import AnkiNote


'''
Polish morphological analyzer using Morfeusz2 and LLM.
morfeusz reliably produces list of all candidate analyses for a given word.
LLM is used to select the best candidate based on context (sentence) AND to handle words with "się" particle.
'''


def select_first_candidate(candidates):
    return candidates[0]


def update_note_without_llm(note: AnkiNote):
    candidates = note.morfeusz_candidates
    _, _, interpretation = select_first_candidate(candidates)

    # Extract lemma and tag
    lemma_raw = interpretation[1]
    lemma = lemma_raw.split(':')[0] if ':' in lemma_raw else lemma_raw
    tag = interpretation[2]

    # Map SGJP tag to readable POS
    readable_pos, aspect = morfeusz_tag_to_pos_string(tag)

    note.morfeusz_tag = tag
    note.morfeusz_lemma = lemma
    note.part_of_speech = readable_pos
    note.aspect = aspect


def has_sie_adjacent_to_word(usage_text, target_word):
    """
    Check if 'się' appears immediately before or after the first occurrence of target_word.
    Handles punctuation cleanly by ignoring non-alphabetic characters when comparing.
    """
    lowercase_usage = usage_text.lower()
    words_list = lowercase_usage.split()

    # Find the first occurrence of the target_word
    target_word_lower = target_word.lower()
    target_index = None

    for i, word in enumerate(words_list):
        # Remove punctuation from word for comparison
        clean_word = ''.join(char for char in word if char.isalpha())
        if clean_word == target_word_lower:
            target_index = i
            break

    if target_index is None:
        return False

    # Check if "się" appears just before the target word
    if target_index > 0:
        prev_word = words_list[target_index - 1]
        clean_prev_word = ''.join(char for char in prev_word if char.isalpha())
        if clean_prev_word == "się":
            return True

    # Check if "się" appears just after the target word
    if target_index < len(words_list) - 1:
        next_word = words_list[target_index + 1]
        clean_next_word = ''.join(char for char in next_word if char.isalpha())
        if clean_next_word == "się":
            return True

    return False


def check_if_requires_llm_ma(note: AnkiNote):
    # Check if "się" is adjacent to the word
    has_sie_before_or_after = has_sie_adjacent_to_word(note.kindle_usage, note.kindle_word)

    # Identify if the word has only one candidate
    has_single_candidate = len(note.morfeusz_candidates) == 1

    return has_sie_before_or_after or not has_single_candidate


def absorb_nearest_sie(kindle_word, usage_text):
    """
    Find the nearest 'się' to the first occurrence of kindle_word and return
    all text between them (inclusive). Returns the absorbed phrase as a string.

    Args:
        kindle_word: The target word to find
        usage_text: The sentence containing the word

    Returns:
        String containing 'się' and all words between it and kindle_word
    """
    words_list = usage_text.split()

    # Find the first occurrence of the target word
    target_word_lower = kindle_word.lower()
    target_index = None

    for i, word in enumerate(words_list):
        # Remove punctuation from word for comparison
        clean_word = ''.join(char for char in word if char.isalpha())
        if clean_word.lower() == target_word_lower:
            target_index = i
            break

    if target_index is None:
        return kindle_word  # Fallback if word not found

    # Find all occurrences of "się"
    sie_indices = []
    for i, word in enumerate(words_list):
        clean_word = ''.join(char for char in word if char.isalpha())
        if clean_word.lower() == "się":
            sie_indices.append(i)

    if not sie_indices:
        return kindle_word  # No "się" found, return original word

    # Find the nearest "się" to the target word
    nearest_sie_index = min(sie_indices, key=lambda x: abs(x - target_index))

    # Determine the range to extract (inclusive)
    start_index = min(nearest_sie_index, target_index)
    end_index = max(nearest_sie_index, target_index)

    # Extract the words between and including "się" and the target word
    absorbed_words = words_list[start_index:end_index + 1]
    result = ' '.join(absorbed_words)

    # Trim punctuation from the beginning and end of the result
    result = result.strip(string.punctuation + ' ')

    return result


def process_notes_with_morfeusz(notes: list[AnkiNote], cache_suffix='pl-en_hybrid', ignore_cache=False, verbose=False):

    try:
        import morfeusz2
    except ImportError:
        raise ImportError("morfeusz2 library is required for Polish morphological analysis. Please install it via 'pip install morfeusz2'.")

    morf = morfeusz2.Morfeusz()
    notes_requiring_llm_ma = []
    num_notes_not_requiring_llm_ma = 0

    for note in notes:
        # Get candidates
        candidates = morf.analyse(note.kindle_word.lower())
        note.morfeusz_candidates = candidates

        requires_llm_ma = check_if_requires_llm_ma(note)

        # Simple case
        if not requires_llm_ma:
            update_note_without_llm(note)
            num_notes_not_requiring_llm_ma += 1
        else:
            notes_requiring_llm_ma.append(note)

    print(f"{num_notes_not_requiring_llm_ma} notes did not require LLM MA processing.")

    if len(notes_requiring_llm_ma) > 0:
        update_notes_with_llm(notes_requiring_llm_ma, cache_suffix=cache_suffix, ignore_cache=ignore_cache)

    # Post process notes by checking if się was absorbed
    for note in notes:
        if "się" in note.morfeusz_lemma:
            note.original_form = absorb_nearest_sie(note.kindle_word, note.kindle_usage)
            # Set unit_type to reflexive for verbs with się
            note.unit_type = "reflexive"
        else:
            # Set unit_type to lemma for regular words
            note.unit_type = "lemma"

        # Normalize morfeusz lemma to best lemma for Anki learning now that final POS is known
        # Morfeusz lemma already has "się" absorbed if applicable for verbs
        note.expression = normalize_lemma(note.original_form, note.morfeusz_lemma, note.part_of_speech, note.morfeusz_tag)

    # Log if expression, lemma or part_of_speech was changed
    if verbose:
        for note in notes:
            print("\nOriginal word:", note.kindle_word)
            print("  -> Expression (lemma):", note.expression)
            print("  -> Part of Speech:", note.part_of_speech)
            print("  -> Aspect:", note.aspect)
            if note.kindle_word != note.original_form:
                print("  -> Original Form:", note.original_form)




from os import read
import morfeusz2


def morfeusz_tag_to_pos_string(morf_tag: str) -> str:
    """
    Convert a full Morfeusz tag string into a learner-facing POS label,
    optionally augmented with verbal aspect.

    Examples:
      "praet:sg:m1:imperf" -> "verb (impf)"
      "inf:perf"           -> "verb (perf)"
      "subst:sg:nom:m1"    -> "noun"
    """

    if not morf_tag:
        return "other"

    parts = morf_tag.split(":")
    base = parts[0]
    features = set(parts[1:])

    # --- POS mapping (coarse) ---
    if base in {"subst", "depr", "ger", "brev"}:
        pos = "noun"

    elif base in {
        "fin", "inf", "impt", "praet", "bedzie",
        "pcon", "pant"
    }:
        pos = "verb"

    elif base in {"adj", "adja", "adjp", "pact", "ppas"}:
        pos = "adj"

    elif base == "adv":
        pos = "adv"

    elif base in {"ppron12", "ppron3", "siebie", "pron"}:
        pos = "pron"

    elif base in {"num", "numcol", "numord", "numfrac"}:
        pos = "num"

    elif base == "prep":
        pos = "prep"

    elif base == "conj":
        pos = "conj"

    elif base in {"qub", "part", "pred"}:
        pos = "part"

    elif base == "interj":
        pos = "interj"

    else:
        pos = "other"

    # --- Aspect extraction (verbs only) ---
    if pos == "verb":
        if "imperf" in features:
            return "verb (impf)"
        if "perf" in features:
            return "verb (perf)"
        # biaspectual or unresolved
        return "verb"

    return pos


def select_best_candidate(candidates):
    return candidates[0]


def analyze_with_morfeusz(word):
    """Analyze word with morfeusz2 to get lemma and part of speech"""

    morf = morfeusz2.Morfeusz()
    candidates = morf.analyse(word.lower())

    # Select the first candidate (to be improved later with llm and się analysis)
    _, _, interpretation = select_best_candidate(candidates)

    # Extract lemma and tag
    lemma_raw = interpretation[1]
    lemma = lemma_raw.split(':')[0] if ':' in lemma_raw else lemma_raw
    tag = interpretation[2]

    # Map SGJP tag to readable POS
    readable_pos = morfeusz_tag_to_pos_string(tag)

    return lemma, readable_pos


def process_notes_with_morfeusz(notes):

    stem_changes = []
    pos_changes = []

    for note in notes:
        # Analyze word with morfeusz2
        morfeusz_lemma, morfeusz_pos = analyze_with_morfeusz(note.kindle_word)

        if (morfeusz_lemma is None or morfeusz_pos is None):
            print(f"Morfeusz2 could not analyze the word: {note.kindle_word}")
            exit(0)

        # Prioritize morfeusz2 lemma if available and different from current expression
        if morfeusz_lemma != note.expression:
            stem_changes.append((note.kindle_word, note.expression, morfeusz_lemma))
            note.expression = morfeusz_lemma

        # Use morfeusz2 POS if available and no POS was previously set
        if morfeusz_pos != note.part_of_speech:
            pos_changes.append((note.kindle_word, note.part_of_speech, morfeusz_pos))
            note.part_of_speech = morfeusz_pos

    # Print changes grouped by type
    for stem_change in stem_changes:
        print(f"Stem change: {stem_change[0]} -> {stem_change[1]} -> {stem_change[2]}")
    for pos_change in pos_changes:
        print(f"POS change: {pos_change[0]} -> {pos_change[1]} -> {pos_change[2]}")


def process_morphological_enrichment(notes, language):
    """Process morfeusz enrichment for a list of notes"""

    print("\nStarting morphological enrichment...")

    if language == "pl":
        process_notes_with_morfeusz(notes)
    elif language == "es":
        print("Not supported yet")
        exit()
    else:
        print("Not supported yet")
        exit()

    print("Morphological enrichment completed.")


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

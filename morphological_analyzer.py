import morfeusz2
import stanza

from anki_note import AnkiNote

# Global variable to store the Stanza pipeline
_stanza_nlp = None


def get_stanza_pipeline():
    """Initialize Stanza pipeline for Polish (singleton pattern)"""
    global _stanza_nlp
    if _stanza_nlp is None:
        try:
            # Download Polish model if not already present
            stanza.download('pl', verbose=False)
            _stanza_nlp = stanza.Pipeline('pl', processors='tokenize,pos,lemma', verbose=False, use_gpu=False)
        except Exception as e:
            print(f"Failed to initialize Stanza: {e}")
            _stanza_nlp = False
    return _stanza_nlp if _stanza_nlp is not False else None


UPOS_TO_SGJP = {
    "NOUN": {"subst", "depr"},
    "PROPN": {"subst", "depr"},
    "ADJ": {"adj", "adjc", "adjp"},
    "ADV": {"adv", "fum"},
    "VERB": {"fin", "praet", "impt", "imps", "inf", "pcon", "pant",
             "ger", "pact", "ppas", "winien", "bedzie"},
    "AUX": {"fin", "praet", "impt", "imps", "inf", "pcon", "pant",
            "ger", "pact", "ppas", "winien", "bedzie"},
    "NUM": {"num", "numcol"},
    "PRON": {"ppronps", "ppron12", "ppron3", "siebie"},
    "DET": {"ppronps", "ppron12", "ppron3", "siebie"},
    "ADP": {"prep"},
    "CONJ": {"conj", "comp"},
    "SCONJ": {"conj", "comp"},
    "PART": {"qub"},
    "INTJ": {"interj", "burk"},
    "X": None,    # allow anything
}


def extract_sgjp_family(tag):
    """SGJP family = the first part before first colon."""
    return tag.split(":")[0]


def parse_stanza_feats(feats_str):
    if not feats_str:
        return {}
    out = {}
    for part in feats_str.split("|"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def tag_matches_stanza_feats(sgjp_tag, feats):
    """
    Very minimal feature alignment.
    You can expand if you need stricter matching.
    """
    feats = parse_stanza_feats(feats)
    if not feats:
        return True

    # Example: filter on Case for nouns/adjectives/pronouns
    case = None
    number = None
    gender = None

    parts = sgjp_tag.split(":")

    for p in parts:
        if p in {"nom", "gen", "dat", "acc", "inst", "loc", "voc"}:
            case = p
        elif p in {"sg", "pl"}:
            number = p
        elif p in {"m1", "m2", "m3", "f", "n", "n1", "n2"}:
            gender = p

    if "Case" in feats and case and feats["Case"].lower() != case:
        return False
    if "Number" in feats and number and feats["Number"].lower() != number:
        return False
    if "Gender" in feats and gender and feats["Gender"].lower().startswith(gender[0]) is False:
        return False

    return True


def pick_best_morfeusz(stanza_upos, stanza_feats, morph_candidates):
    """Return Morfeusz candidate (lemma, tag) best aligned with Stanza reading."""
    allowed = UPOS_TO_SGJP.get(stanza_upos)
    best = None

    for c in morph_candidates:
        lemma_m = c[2][1]
        tag_m = c[2][2]
        fam = extract_sgjp_family(tag_m)

        # 1. UPOS-compatible?
        if allowed is not None and fam not in allowed:
            print("not #1")
            continue

        # 2. Feature-compatible?
        if not tag_matches_stanza_feats(tag_m, stanza_feats):
            print("not #2")
            continue

        print("I actually used morph")
        best = (lemma_m, tag_m)
        break

    return best


def get_all_lemma_and_pos_candidates(note: AnkiNote):
    """Analyze word with morfeusz2 to get lemma and part of speech"""

    word = note.kindle_word

    if not morfeusz2 or not word:
        exit()

    morf = morfeusz2.Morfeusz()
    return morf.analyse(word.lower())


def analyze_with_hybrid_approach(note: AnkiNote):

    print(f"\nAnalyzing word: {note.kindle_word} with sentence: {note.context_sentence}")

    nlp = get_stanza_pipeline()

    stanza_lemma = None
    stanza_pos = None

    # Get the stanza analysis
    doc = nlp(note.context_sentence)
    for sentence in doc.sentences:
        for word in sentence.words:
            if word.text == note.kindle_word:
                stanza_lemma = word.lemma
                stanza_pos = word.upos
                stanza_feats = word.feats
                break

    if stanza_lemma is None or stanza_pos is None:
        exit()

    # Get morfeusz candidates
    morph_candidates = get_all_lemma_and_pos_candidates(note)

    # 3. Pick a Morfeusz reading consistent with Stanza
    best = pick_best_morfeusz(stanza_pos, stanza_feats, morph_candidates)

    if best:
        final_lemma, final_tag = best
    else:
        # fallback if nothing matches
        final_lemma, final_tag = stanza_lemma, stanza_pos

    print(f"Stanza (context-aware):", stanza_lemma, stanza_pos)
    print(f"Morfeusz candidates:")
    for candidate in morph_candidates:
        print(candidate)

    return final_lemma, final_tag


def process_notes_with_morfeusz(notes):

    stem_changes = []
    pos_changes = []

    for note in notes:
        # Use hybrid approach for better accuracy
        lemma, pos = analyze_with_hybrid_approach(note)

        # Update lemma if different
        if lemma != note.expression:
            stem_changes.append((note.kindle_word, note.expression, lemma))
            note.expression = lemma

        # Update POS if different
        if pos != note.part_of_speech:
            pos_changes.append((note.kindle_word, note.part_of_speech, pos))
            note.part_of_speech = pos

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

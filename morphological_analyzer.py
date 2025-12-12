import morfeusz2
import spacy

from anki_note import AnkiNote


def analyze_with_morfeusz(word):
    """Analyze word with morfeusz2 to get lemma and part of speech"""
    if not morfeusz2 or not word:
        return None, None

    try:
        morf = morfeusz2.Morfeusz()
        analysis = morf.analyse(word.lower())

        if analysis:
            # morfeusz2 returns list of tuples: (start_pos, end_pos, interpretation)
            # where interpretation is a tuple: (lemma, tag, name_list)
            for start_pos, end_pos, interpretation in analysis:
                if interpretation and len(interpretation) >= 2:
                    lemma_raw = interpretation[1]
                    tag = interpretation[2]

                    lemma = lemma_raw.split(':')[0] if ':' in lemma_raw else lemma_raw
                    pos = tag.split(':')[0] if ':' in tag else tag

                    # Map morfeusz2 tags to more readable forms
                    pos_mapping = {
                        'subst': 'noun',
                        'adj': 'adjective', 
                        'adv': 'adverb',
                        'verb': 'verb',
                        'num': 'numeral',
                        'prep': 'preposition',
                        'conj': 'conjunction',
                        'qub': 'particle',
                        'fin': 'finite verb',
                        'ger': 'gerund',
                        'praet': 'preterite/past tense',
                        'ppas': 'past passive participle',
                        'xxx': 'unknown',
                        'ign': 'ignored'
                    }

                    readable_pos = pos_mapping.get(pos, pos)
                    return lemma, readable_pos

    except Exception as e:
        # If morfeusz2 analysis fails, return None values
        print(f"Morfeusz2 analysis error: {e}")
        pass

    return None, None


def analyze_with_spacy(note: AnkiNote):
    # Load the Polish model
    nlp = spacy.load("pl_core_news_sm")

    doc = nlp(note.context_sentence)

    for token in doc:
        print(token.text, token.lemma_, token.pos_)

    exit()


def process_notes_with_morfeusz(notes):

    stem_changes = []
    pos_changes = []

    for note in notes:

        analyze_with_spacy(note)

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

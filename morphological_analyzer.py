import morfeusz2
import subprocess
import os
import json
from datetime import datetime

from anki_note import AnkiNote


def analyze_with_morfeusz(note: AnkiNote):
    """Analyze word with morfeusz2 and concraft-pl to get lemma and part of speech"""

    word = note.kindle_word
    sentence = note.context_sentence

    if not morfeusz2 or not word:
        return None, None

    # Step 1: Raw morph analysis from Morfeusz2
    morph = morfeusz2.Morfeusz()
    analyses = morph.analyse(sentence)

    # Step 2: Convert Morfeusz output to Concraft JSON lattice format
    lattice = []
    for (start, end, interpretation) in analyses:
        orth = interpretation[0]
        lemma = interpretation[1] 
        tag = interpretation[2]
        lattice.append({
            "start": start,
            "end": end,
            "orth": orth,
            "lemma": lemma,
            "tag": tag
        })

    # Write lattice to cache file with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    lattice_file = f'cache/concraft_lattice_{timestamp}.json'

    with open(lattice_file, 'w', encoding='utf-8') as f:
        json.dump(lattice, f, ensure_ascii=False)

    # Step 3: Call concraft-pl tag
    result = subprocess.run(['concraft-pl', 'tag', lattice_file], capture_output=True, text=True, encoding='utf-8')

    if result.returncode == 0:
        # Step 4: Parse Concraft JSON output
        disamb = json.loads(result.stdout)

        # Step 5: Find our target word with choice=1
        for tok in disamb:
            if tok.get("choice") == 1 and tok["orth"].lower() == word.lower():
                lemma = tok["lemma"]
                tag = tok["tag"]
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

    return None, None


def process_notes_with_morfeusz(notes):

    stem_changes = []
    pos_changes = []

    for note in notes:
        # Analyze word with morfeusz2
        morfeusz_lemma, morfeusz_pos = analyze_with_morfeusz(note)

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

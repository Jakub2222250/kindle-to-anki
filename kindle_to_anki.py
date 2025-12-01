import sqlite3
import sys
from pathlib import Path
from anki_note import AnkiNote
import morfeusz2
from llm_enrichment import batch_llm_enrichment


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


def process_morfeusz_enrichment(note):
    """Process morfeusz enrichment for a note"""
    if not note.word:
        print("  Morfeusz enrichment: SKIPPED - no word to analyze")
        return

    # Analyze word with morfeusz2
    morfeusz_stem, morfeusz_pos = analyze_with_morfeusz(note.word)

    enriched_fields = []

    # Prioritize morfeusz2 stem if available and different from current stem
    if morfeusz_stem and morfeusz_stem != note.stem:
        note.stem = morfeusz_stem
        enriched_fields.append('stem')

    # Use morfeusz2 POS if available and no POS was previously set
    if morfeusz_pos and not note.part_of_speech:
        note.part_of_speech = morfeusz_pos
        enriched_fields.append('part_of_speech')

    if enriched_fields:
        print(f"  Morfeusz enrichment: SUCCESS - enriched {', '.join(enriched_fields)}")
    else:
        print("  Morfeusz enrichment: No new information")


def read_vocab_from_db(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    query = """
    SELECT WORDS.word, WORDS.stem, LOOKUPS.usage, WORDS.lang, 
           BOOK_INFO.title, LOOKUPS.pos
    FROM LOOKUPS
    JOIN WORDS ON LOOKUPS.word_key = WORDS.id
    LEFT JOIN BOOK_INFO ON LOOKUPS.book_key = BOOK_INFO.id
    ORDER BY LOOKUPS.timestamp;
    """

    rows = cur.execute(query).fetchall()
    conn.close()
    return rows


def create_anki_notes(vocab_data):
    """Create AnkiNotes from vocab_data with morfeusz enrichment only"""
    notes = []
    total_words = len([row for row in vocab_data if row[1]])  # Count words with stems
    processed_count = 0

    for word, stem, usage, lang, book_title, pos in vocab_data:
        if stem:
            processed_count += 1
            print(f"\n[{processed_count}/{total_words}]")

            # Create AnkiNote with all data - setup is handled in constructor
            note = AnkiNote(
                stem=stem,
                word=word,
                usage=usage,
                book_name=book_title,
                language=lang,
                pos=pos
            )

            # Process morfeusz enrichment externally after note construction
            process_morfeusz_enrichment(note)

            notes.append(note)

    return notes


def write_anki_import_file(notes):
    Path("outputs").mkdir(exist_ok=True)
    anki_path = Path("outputs/anki_import.txt")

    # Write notes to file
    with open(anki_path, "w", encoding="utf-8") as f:
        f.write("#separator:tab\n")
        f.write("#html:true\n")
        f.write("#tags:kindle_to_anki\n")

        for note in notes:
            f.write(note.to_csv_line())

    print(f"Created Anki import file with {len(notes)} records at {anki_path}")


def export_kindle_vocab():
    # Get script directory and construct path to inputs/vocab.db
    script_dir = Path(__file__).parent
    db_path = script_dir / "inputs" / "vocab.db"

    if not db_path.exists():
        print(f"Error: vocab.db not found at {db_path}")
        print("Please place your Kindle vocab.db file in the 'inputs' folder relative to this script.")
        sys.exit(1)

    vocab_data = read_vocab_from_db(db_path)
    notes = create_anki_notes(vocab_data)
    batch_llm_enrichment(notes)
    write_anki_import_file(notes)


if __name__ == "__main__":
    export_kindle_vocab()

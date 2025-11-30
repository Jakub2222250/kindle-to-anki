import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote


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


def write_vocab_to_file(vocab_data):
    Path("outputs").mkdir(exist_ok=True)
    txt_path = Path("outputs/words.txt")

    with open(txt_path, "w", encoding="utf-8") as f:
        for word, stem, usage, lang, book_title, pos in vocab_data:
            if stem:
                encoded_word = quote(stem.strip().lower())
                glosbe_url = f"https://glosbe.com/pl/en/{encoded_word}"
                f.write(f"{stem}\n{usage}\n{glosbe_url}\n\n")

    print(f"Exported {len(vocab_data)} records to {txt_path}")


def write_anki_import_file(vocab_data):
    Path("outputs").mkdir(exist_ok=True)
    anki_path = Path("outputs/anki_import.txt")

    with open(anki_path, "w", encoding="utf-8") as f:
        f.write("#separator:tab\n")
        f.write("#html:true\n")
        f.write("#tags:kindle_to_anki\n")
        for word, stem, usage, lang, book_title, pos in vocab_data:
            if stem:
                encoded_word = quote(stem.strip().lower())
                glosbe_url = f"https://glosbe.com/pl/en/{encoded_word}"
                formatted_usage = usage.replace('\n', '<br>').replace('\r', '') if usage else ""
                book_name = book_title if book_title else ""
                language = lang if lang else ""
                location = pos if pos else ""
                tags = f"kindle_to_anki {language}" if language else "kindle_to_anki"
                f.write(f"{stem}\t{word}\tpart_of_speech_not_set\t{glosbe_url}\tsecondary_definition_not_set\t{formatted_usage}\tcontext_translation_not_set\tnotes_not_set\t{book_name}\tkindle_{location}\t{tags}\n")

    print(f"Created Anki import file with {len(vocab_data)} records at {anki_path}")


def export_kindle_vocab(db_path):
    vocab_data = read_vocab_from_db(db_path)
    write_vocab_to_file(vocab_data)
    write_anki_import_file(vocab_data)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python kindle_to_anki.py /path/to/vocab.db")
        sys.exit(1)

    export_kindle_vocab(sys.argv[1])

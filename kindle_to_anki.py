import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote


def export_kindle_vocab(db_path, txt_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    query = """
    SELECT WORDS.stem, LOOKUPS.usage
    FROM LOOKUPS
    JOIN WORDS ON LOOKUPS.word_key = WORDS.id
    ORDER BY LOOKUPS.timestamp;
    """

    rows = cur.execute(query).fetchall()

    with open(txt_path, "w", encoding="utf-8") as f:
        for stem, usage in rows:
            if stem:
                encoded_word = quote(stem.strip().lower())
                glosbe_url = f"https://glosbe.com/pl/en/{encoded_word}"
                f.write(f"{stem}\n{usage}\n{glosbe_url}\n\n")

    conn.close()
    print(f"Exported {len(rows)} records to {txt_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python kindle_to_anki.py /path/to/vocab.db /path/to/output.txt")
        sys.exit(1)

    export_kindle_vocab(sys.argv[1], sys.argv[2])

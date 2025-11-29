import sqlite3
import csv
import sys
from pathlib import Path


def export_kindle_vocab(db_path, csv_path):
    db_path = Path(db_path)
    csv_path = Path(csv_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    query = """
    SELECT
        WORDS.word,
        WORDS.stem,
        WORDS.lang,
        LOOKUPS.usage,
        BOOK_INFO.title AS book_title,
        BOOK_INFO.asin,
        LOOKUPS.timestamp
    FROM LOOKUPS
    JOIN WORDS ON LOOKUPS.word_key = WORDS.id
    LEFT JOIN BOOK_INFO ON LOOKUPS.book_key = BOOK_INFO.id
    ORDER BY LOOKUPS.timestamp;
    """

    rows = cur.execute(query).fetchall()
    headers = [d[0] for d in cur.description]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    conn.close()
    print(f"Exported {len(rows)} records to {csv_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python export_kindle_vocab.py /path/to/vocab.db /path/to/output.csv")
        sys.exit(1)

    export_kindle_vocab(sys.argv[1], sys.argv[2])

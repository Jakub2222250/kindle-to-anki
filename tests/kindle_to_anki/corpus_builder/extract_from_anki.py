#!/usr/bin/env python3
"""
Extract test corpus entries from existing Anki cards.
Queries AnkiConnect for cards and outputs JSONL for each task type.

Usage:
    py tests/kindle_to_anki/corpus_builder/extract_from_anki.py --source-lang pl --deck "Polish Vocab Discovery"
    py tests/kindle_to_anki/corpus_builder/extract_from_anki.py --source-lang pl --corpus wsd --limit 50
    py tests/kindle_to_anki/corpus_builder/extract_from_anki.py --source-lang es --overwrite
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.anki.constants import NOTE_TYPE_NAME


CORPUS_DIRS = {
    "wsd": Path(__file__).parent.parent / "tasks/wsd/fixtures",
    "collocation": Path(__file__).parent.parent / "tasks/collocation/fixtures",
    "hint": Path(__file__).parent.parent / "tasks/hint/fixtures",
    "cloze_scoring": Path(__file__).parent.parent / "tasks/cloze_scoring/fixtures",
}


@dataclass
class WSDCorpusEntry:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str
    source_lang: str
    target_lang: str


@dataclass
class CollocationCorpusEntry:
    uid: str
    lemma: str
    pos: str
    source_lang: str


@dataclass
class HintCorpusEntry:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str
    source_lang: str
    target_lang: str


@dataclass
class ClozeScoringCorpusEntry:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str
    source_lang: str


def generate_uid(prefix: str, *args) -> str:
    """Generate a deterministic UID from content."""
    content = "|".join(str(a) for a in args)
    hash_part = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"{prefix}_{hash_part}"


def extract_notes_from_anki(deck_name: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch notes from Anki via AnkiConnect."""
    anki = AnkiConnect()

    if deck_name:
        query = f'"deck:{deck_name}" "note:{NOTE_TYPE_NAME}"'
    else:
        query = f'"note:{NOTE_TYPE_NAME}"'

    note_ids = anki._invoke("findNotes", {"query": query})
    if limit:
        note_ids = note_ids[:limit]

    if not note_ids:
        print(f"No notes found for query: {query}")
        return []

    notes_info = anki._invoke("notesInfo", {"notes": note_ids})
    return notes_info


def note_to_wsd_entry(note: Dict, source_lang: str, target_lang: str) -> Optional[WSDCorpusEntry]:
    """Convert Anki note to WSD corpus entry."""
    fields = note.get("fields", {})

    word = fields.get("Raw_Lookup_String", {}).get("value", "").strip()
    lemma = fields.get("Expression", {}).get("value", "").strip()
    pos = fields.get("Part_Of_Speech", {}).get("value", "").strip().lower()
    sentence = fields.get("Raw_Context_Text", {}).get("value", "").strip()

    if not all([word, lemma, sentence]):
        return None

    # Normalize POS
    pos_map = {"rzeczownik": "noun", "czasownik": "verb", "przymiotnik": "adj", "przysłówek": "adv"}
    pos = pos_map.get(pos, pos)

    uid = generate_uid(f"{source_lang}_{target_lang}", lemma, sentence[:50])

    return WSDCorpusEntry(
        uid=uid,
        word=word,
        lemma=lemma,
        pos=pos,
        sentence=sentence,
        source_lang=source_lang,
        target_lang=target_lang,
    )


def note_to_collocation_entry(note: Dict, source_lang: str) -> Optional[CollocationCorpusEntry]:
    """Convert Anki note to collocation corpus entry."""
    fields = note.get("fields", {})

    lemma = fields.get("Expression", {}).get("value", "").strip()
    pos = fields.get("Part_Of_Speech", {}).get("value", "").strip().lower()

    if not lemma:
        return None

    pos_map = {"rzeczownik": "noun", "czasownik": "verb", "przymiotnik": "adj", "przysłówek": "adv"}
    pos = pos_map.get(pos, pos)

    uid = generate_uid(f"{source_lang}_coll", lemma, pos)

    return CollocationCorpusEntry(uid=uid, lemma=lemma, pos=pos, source_lang=source_lang)


def note_to_hint_entry(note: Dict, source_lang: str, target_lang: str) -> Optional[HintCorpusEntry]:
    """Convert Anki note to hint corpus entry."""
    wsd = note_to_wsd_entry(note, source_lang, target_lang)
    if not wsd:
        return None

    return HintCorpusEntry(
        uid=generate_uid(f"{source_lang}_hint", wsd.lemma, wsd.sentence[:50]),
        word=wsd.word,
        lemma=wsd.lemma,
        pos=wsd.pos,
        sentence=wsd.sentence,
        source_lang=source_lang,
        target_lang=target_lang,
    )


def note_to_cloze_scoring_entry(note: Dict, source_lang: str) -> Optional[ClozeScoringCorpusEntry]:
    """Convert Anki note to cloze scoring corpus entry."""
    fields = note.get("fields", {})

    word = fields.get("Raw_Lookup_String", {}).get("value", "").strip()
    lemma = fields.get("Expression", {}).get("value", "").strip()
    pos = fields.get("Part_Of_Speech", {}).get("value", "").strip().lower()
    sentence = fields.get("Raw_Context_Text", {}).get("value", "").strip()

    if not all([word, lemma, sentence]):
        return None

    pos_map = {"rzeczownik": "noun", "czasownik": "verb", "przymiotnik": "adj", "przysłówek": "adv"}
    pos = pos_map.get(pos, pos)

    uid = generate_uid(f"{source_lang}_cloze", lemma, sentence[:50])

    return ClozeScoringCorpusEntry(
        uid=uid,
        word=word,
        lemma=lemma,
        pos=pos,
        sentence=sentence,
        source_lang=source_lang,
    )


def save_corpus(entries: List[Any], corpus_type: str, source_lang: str, append: bool = True):
    """Save corpus entries to JSONL file."""
    output_dir = CORPUS_DIRS[corpus_type]
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{corpus_type}_corpus_{source_lang}.jsonl"
    output_path = output_dir / filename

    # Load existing UIDs to avoid duplicates
    existing_uids = set()
    if append and output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    existing_uids.add(data.get("uid"))

    new_entries = [e for e in entries if e.uid not in existing_uids]

    mode = "a" if append else "w"
    with open(output_path, mode, encoding="utf-8") as f:
        for entry in new_entries:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    print(f"Saved {len(new_entries)} new entries to {output_path} ({len(existing_uids)} existing)")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Extract test corpus from Anki cards")
    parser.add_argument("--deck", help="Anki deck name to extract from")
    parser.add_argument("--source-lang", required=True, help="Source language code (e.g., pl)")
    parser.add_argument("--target-lang", default="en", help="Target language code (default: en)")
    parser.add_argument("--corpus", choices=["wsd", "collocation", "hint", "cloze_scoring", "all"], default="all",
                        help="Which corpus to generate")
    parser.add_argument("--limit", type=int, help="Max notes to process")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite instead of append")

    args = parser.parse_args()

    print(f"Extracting from Anki (deck: {args.deck or 'all'})...")
    notes = extract_notes_from_anki(args.deck, args.limit)
    print(f"Found {len(notes)} notes")

    if args.corpus in ("wsd", "all"):
        entries = [e for e in (note_to_wsd_entry(n, args.source_lang, args.target_lang) for n in notes) if e]
        save_corpus(entries, "wsd", args.source_lang, append=not args.overwrite)

    if args.corpus in ("collocation", "all"):
        entries = [e for e in (note_to_collocation_entry(n, args.source_lang) for n in notes) if e]
        # Dedupe by lemma+pos
        seen = set()
        unique = []
        for e in entries:
            key = (e.lemma, e.pos)
            if key not in seen:
                seen.add(key)
                unique.append(e)
        save_corpus(unique, "collocation", args.source_lang, append=not args.overwrite)

    if args.corpus in ("hint", "all"):
        entries = [e for e in (note_to_hint_entry(n, args.source_lang, args.target_lang) for n in notes) if e]
        save_corpus(entries, "hint", args.source_lang, append=not args.overwrite)

    if args.corpus in ("cloze_scoring", "all"):
        entries = [e for e in (note_to_cloze_scoring_entry(n, args.source_lang) for n in notes) if e]
        save_corpus(entries, "cloze_scoring", args.source_lang, append=not args.overwrite)


if __name__ == "__main__":
    main()

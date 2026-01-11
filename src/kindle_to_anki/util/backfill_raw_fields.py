"""
One-off script to backfill Raw_Context_Text and Raw_Lookup_String fields for existing Anki cards.

This script:
1. Reads vocab.db to get original Kindle lookup data
2. Finds Anki cards where Raw_Context_Text or Raw_Lookup_String are blank
3. Matches cards to vocab.db entries by UID when possible
4. Uses heuristics to back-calculate values when not found in vocab.db
"""

import re
import sqlite3
from pathlib import Path

from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.anki.anki_deck import AnkiDeck
from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.configuration.config_manager import ConfigManager


PROJECT_ROOT = Path(__file__).parent.parent.parent
VOCAB_DB_PATH = PROJECT_ROOT / "data" / "inputs" / "vocab.db"


def read_all_vocab_entries(db_path: Path) -> list[dict]:
    """Read all vocabulary entries from Kindle database"""
    if not db_path.exists():
        print(f"Warning: vocab.db not found at {db_path}")
        return []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    query = """
    SELECT WORDS.word, WORDS.stem, LOOKUPS.usage, WORDS.lang, 
           BOOK_INFO.title, LOOKUPS.pos, LOOKUPS.timestamp
    FROM LOOKUPS
    JOIN WORDS ON LOOKUPS.word_key = WORDS.id
    LEFT JOIN BOOK_INFO ON LOOKUPS.book_key = BOOK_INFO.id
    ORDER BY LOOKUPS.timestamp;
    """
    rows = cur.execute(query).fetchall()
    conn.close()

    entries = []
    for word, stem, usage, lang, book_title, pos, timestamp in rows:
        # Create temporary AnkiNote to generate UID
        note = AnkiNote(
            word=word,
            stem=stem,
            usage=usage,
            language=lang,
            book_name=book_title,
            position=pos,
            timestamp=timestamp
        )
        entries.append({
            'uid': note.uid,
            'raw_lookup_string': word,
            'raw_context_text': usage,
        })

    return entries


def get_anki_notes_needing_backfill(anki: AnkiConnect) -> list[dict]:
    """Get all Anki notes where Raw_Context_Text or Raw_Lookup_String are blank"""

    # Query for notes with blank raw fields
    query = f'"note:{anki.note_type}" (Raw_Context_Text: OR Raw_Lookup_String:)'

    try:
        note_ids = anki._invoke("findNotes", {"query": query})
    except Exception:
        # Fallback: get all notes and filter
        query = f'"note:{anki.note_type}"'
        note_ids = anki._invoke("findNotes", {"query": query})

    if not note_ids:
        return []

    notes_info = anki._invoke("notesInfo", {"notes": note_ids})

    notes_needing_update = []
    for note in notes_info:
        fields = note.get('fields', {})
        raw_context = fields.get('Raw_Context_Text', {}).get('value', '').strip()
        raw_lookup = fields.get('Raw_Lookup_String', {}).get('value', '').strip()

        # Only include notes where either field is blank
        if not raw_context or not raw_lookup:
            notes_needing_update.append({
                'note_id': note.get('noteId'),
                'uid': fields.get('UID', {}).get('value', '').strip(),
                'context_sentence': fields.get('Context_Sentence', {}).get('value', '').strip(),
                'surface_lexical_unit': fields.get('Surface_Lexical_Unit', {}).get('value', '').strip(),
                'existing_raw_context': raw_context,
                'existing_raw_lookup': raw_lookup,
            })

    return notes_needing_update


def extract_bold_text(html: str) -> list[str]:
    """Extract text within <b> tags"""
    pattern = r'<b>(.*?)</b>'
    matches = re.findall(pattern, html, re.IGNORECASE)
    return matches


def remove_bold_tags(html: str) -> str:
    """Remove <b> and </b> tags from HTML"""
    return html.replace('<b>', '').replace('</b>', '')


def extract_uid_prefix(uid: str) -> str:
    """Extract the first part of UID before the first underscore"""
    if '_' in uid:
        return uid.split('_')[0]
    return uid


def back_calculate_raw_fields(note: dict) -> tuple[str, str, list[str]]:
    """
    Back-calculate Raw_Context_Text and Raw_Lookup_String from existing fields.
    Returns (raw_context_text, raw_lookup_string, log_messages)
    """
    logs = []
    context_sentence = note['context_sentence']
    uid = note['uid']
    surface_lexical_unit = note['surface_lexical_unit']

    # Raw_Context_Text is simply the context sentence without bold tags
    raw_context_text = remove_bold_tags(context_sentence)

    # Try to extract Raw_Lookup_String from bold text
    bold_texts = extract_bold_text(context_sentence)

    if len(bold_texts) == 1:
        # Single bold section - check if it's one word
        bold_content = bold_texts[0].strip()
        words_in_bold = bold_content.split()

        if len(words_in_bold) == 1:
            raw_lookup_string = bold_content
        else:
            # Multiple words in bold - use UID prefix heuristic
            uid_prefix = extract_uid_prefix(uid)
            logs.append(f"HEURISTIC: Multiple words in bold '{bold_content}', using UID prefix '{uid_prefix}'")

            # Find the word in bold that matches UID prefix (case-insensitive)
            matching_word = None
            for word in words_in_bold:
                if word.lower() == uid_prefix.lower():
                    matching_word = word
                    break

            if matching_word:
                raw_lookup_string = matching_word
                logs.append(f"  -> Found matching word: '{matching_word}'")
            else:
                # Use surface_lexical_unit if available, otherwise first word
                if surface_lexical_unit and len(surface_lexical_unit.split()) == 1:
                    raw_lookup_string = surface_lexical_unit
                    logs.append(f"  -> Using Surface_Lexical_Unit: '{surface_lexical_unit}'")
                else:
                    raw_lookup_string = words_in_bold[0]
                    logs.append(f"  -> Fallback to first word: '{raw_lookup_string}'")

    elif len(bold_texts) > 1:
        # Multiple bold sections - use UID prefix heuristic
        uid_prefix = extract_uid_prefix(uid)
        logs.append(f"HEURISTIC: Multiple bold sections {bold_texts}, using UID prefix '{uid_prefix}'")

        # Find which bold section contains the UID prefix
        matching_text = None
        for bold_text in bold_texts:
            if uid_prefix.lower() in bold_text.lower():
                matching_text = bold_text.strip()
                break

        if matching_text:
            words = matching_text.split()
            if len(words) == 1:
                raw_lookup_string = matching_text
            else:
                # Find exact word match
                for word in words:
                    if word.lower() == uid_prefix.lower():
                        raw_lookup_string = word
                        break
                else:
                    raw_lookup_string = words[0]
            logs.append(f"  -> Selected: '{raw_lookup_string}'")
        else:
            # Fallback to surface_lexical_unit or first bold text
            if surface_lexical_unit and len(surface_lexical_unit.split()) == 1:
                raw_lookup_string = surface_lexical_unit
                logs.append(f"  -> Using Surface_Lexical_Unit: '{surface_lexical_unit}'")
            else:
                raw_lookup_string = bold_texts[0].split()[0] if bold_texts[0] else ""
                logs.append(f"  -> Fallback to first bold: '{raw_lookup_string}'")

    else:
        # No bold text found - use surface_lexical_unit or UID prefix
        logs.append(f"HEURISTIC: No bold text in context, using fallback")
        if surface_lexical_unit and len(surface_lexical_unit.split()) == 1:
            raw_lookup_string = surface_lexical_unit
            logs.append(f"  -> Using Surface_Lexical_Unit: '{raw_lookup_string}'")
        else:
            uid_prefix = extract_uid_prefix(uid)
            raw_lookup_string = uid_prefix
            logs.append(f"  -> Using UID prefix: '{raw_lookup_string}'")

    return raw_context_text, raw_lookup_string, logs


def backfill_raw_fields(dry_run: bool = True, limit: int = 10, source_filter: str = None):
    """
    Main function to backfill Raw_Context_Text and Raw_Lookup_String fields.

    Args:
        dry_run: If True, only print what would be changed without applying
        limit: Maximum number of changes to show/apply
        source_filter: 'vocab' for only vocab.db matches, 'heuristic' for only heuristics, None for all
    """
    print("=" * 70)
    print("Backfill Raw_Context_Text and Raw_Lookup_String Fields")
    print("=" * 70)

    # Connect to Anki
    try:
        anki = AnkiConnect()
    except SystemExit:
        print("Error: Could not connect to AnkiConnect")
        return

    if not anki.is_reachable():
        print("Error: AnkiConnect is not reachable. Ensure Anki is running.")
        return

    # Load first deck from config
    config = ConfigManager()
    decks = list(config.get_anki_decks_by_source_language().values())
    if not decks:
        print("Error: No decks configured in config.json")
        return
    deck = decks[0]
    print(f"Using deck: {deck.parent_deck_name}")

    # Read vocab.db
    print(f"\nReading vocab.db from {VOCAB_DB_PATH}...")
    vocab_entries = read_all_vocab_entries(VOCAB_DB_PATH)
    print(f"Found {len(vocab_entries)} entries in vocab.db")

    # Create lookup by UID
    vocab_by_uid = {entry['uid']: entry for entry in vocab_entries}

    # Get notes needing backfill
    print("\nFetching Anki notes with blank raw fields...")
    notes_needing_update = get_anki_notes_needing_backfill(anki)
    print(f"Found {len(notes_needing_update)} notes needing update")

    if not notes_needing_update:
        print("\nNo notes need updating. Done!")
        return

    # Process notes
    updates = []
    vocab_matched = 0
    heuristic_used = 0

    for note in notes_needing_update:
        uid = note['uid']
        fields_to_update = {}
        logs = []
        source = ""

        # Check if we have this in vocab.db
        if uid in vocab_by_uid:
            vocab_entry = vocab_by_uid[uid]
            source = "vocab.db"
            vocab_matched += 1

            if not note['existing_raw_context']:
                fields_to_update['Raw_Context_Text'] = vocab_entry['raw_context_text']
            if not note['existing_raw_lookup']:
                fields_to_update['Raw_Lookup_String'] = vocab_entry['raw_lookup_string']
        else:
            # Back-calculate from existing fields
            source = "heuristic"
            heuristic_used += 1
            raw_context, raw_lookup, logs = back_calculate_raw_fields(note)

            if not note['existing_raw_context']:
                fields_to_update['Raw_Context_Text'] = raw_context
            if not note['existing_raw_lookup']:
                fields_to_update['Raw_Lookup_String'] = raw_lookup

        if fields_to_update:
            # Apply source filter if specified
            if source_filter == 'vocab' and source != 'vocab.db':
                continue
            if source_filter == 'heuristic' and source != 'heuristic':
                continue

            updates.append({
                'uid': uid,
                'note_id': note['note_id'],
                'fields': fields_to_update,
                'source': source,
                'logs': logs,
                'context_sentence': note['context_sentence'][:80] + '...' if len(note['context_sentence']) > 80 else note['context_sentence'],
            })

    print(f"\n{'=' * 70}")
    print(f"Summary: {len(updates)} notes to update")
    print(f"  - From vocab.db: {vocab_matched}")
    print(f"  - Using heuristics: {heuristic_used}")
    print(f"{'=' * 70}")

    # Show updates (limited)
    shown = 0
    for update in updates:
        if shown >= limit:
            remaining = len(updates) - limit
            print(f"\n... and {remaining} more updates")
            break

        shown += 1
        print(f"\n[{shown}] UID: {update['uid']}")
        print(f"    Source: {update['source']}")
        print(f"    Context: {update['context_sentence']}")

        for field, value in update['fields'].items():
            display_value = value[:60] + '...' if len(value) > 60 else value
            print(f"    -> {field}: '{display_value}'")

        for log in update['logs']:
            print(f"    {log}")

    if dry_run:
        print(f"\n{'=' * 70}")
        print("DRY RUN - No changes applied")
        print("To apply changes, set dry_run=False")
        print(f"{'=' * 70}")
    else:
        # Apply updates
        print(f"\n{'=' * 70}")
        print(f"Applying {len(updates)} updates...")

        card_updates = [
            {'UID': u['uid'], 'fields': u['fields']}
            for u in updates
        ]
        anki.update_notes_fields(card_updates, deck.parent_deck_name)

        print("Updates applied successfully!")
        print(f"{'=' * 70}")


if __name__ == "__main__":
    # Run in dry-run mode, showing up to 10 changes
    # source_filter: 'vocab' for only vocab.db matches, 'heuristic' for only heuristics, None for all
    backfill_raw_fields(dry_run=False, limit=10, source_filter='heuristic')

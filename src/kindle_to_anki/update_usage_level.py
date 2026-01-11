"""
One-off script to update Usage_Level field for new Anki cards using WSD task.
Reads cards, runs WSD without cache, updates only Usage_Level.
"""

from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.anki.constants import NOTE_TYPE_NAME
from kindle_to_anki.configuration.config_manager import ConfigManager
from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.runtimes.runtime_registry import RuntimeRegistry
from kindle_to_anki.tasks.usage_level.schema import UsageLevelInput


def main():
    bootstrap_all()

    config_manager = ConfigManager()
    anki_decks = config_manager.get_anki_decks_by_source_language()

    # Get Polish deck config
    pl_deck = anki_decks.get("pl")
    if not pl_deck:
        print("No Polish deck configured")
        return

    # Get usage_level task settings
    ul_settings = config_manager.get_task_setting("usage_level")
    runtime_id = ul_settings.get("runtime", "chat_completion_usage_level")
    model_id = ul_settings.get("model_id", "gpt-5.1")
    batch_size = ul_settings.get("batch_size", 30)

    runtime_config = RuntimeConfig(
        model_id=model_id,
        batch_size=batch_size,
        source_language_code=pl_deck.source_language_code,
        target_language_code=pl_deck.target_language_code
    )

    # Get usage_level runtime
    ul_runtimes = RuntimeRegistry.find_by_task_as_dict("usage_level")
    ul_runtime = ul_runtimes.get(runtime_id)
    if not ul_runtime:
        print(f"usage_level runtime '{runtime_id}' not found")
        return

    anki = AnkiConnect()

    # Find cards in the parent deck
    query = f'"deck:{pl_deck.parent_deck_name}" "note:{NOTE_TYPE_NAME}"'
    print(f"Searching with query: {query}")

    note_ids = anki._invoke("findNotes", {"query": query})
    if not note_ids:
        print("No new cards found")
        return

    print(f"Found {len(note_ids)} new cards")

    # Get note info
    notes_info = anki._invoke("notesInfo", {"notes": note_ids})

    # Build usage_level inputs from card data (skip those with existing Usage_Level)
    ul_inputs = []
    note_id_map = {}  # uid -> note_id
    skipped = 0

    for note in notes_info:
        fields = note.get('fields', {})
        uid = fields.get('UID', {}).get('value', '').strip()
        expression = fields.get('Expression', {}).get('value', '').strip()
        surface_lexical_unit = fields.get('Surface_Lexical_Unit', {}).get('value', '').strip()
        context = fields.get('Context_Sentence', {}).get('value', '').strip()
        pos = fields.get('Part_Of_Speech', {}).get('value', '').strip() or 'unknown'
        existing_usage_level = fields.get('Usage_Level', {}).get('value', '').strip()
        definition = fields.get('Definition', {}).get('value', '').strip()

        if existing_usage_level:
            skipped += 1
            continue

        if uid and expression and context and definition:
            ul_input = UsageLevelInput(
                uid=uid,
                word=surface_lexical_unit or expression,
                lemma=expression,
                pos=pos,
                sentence=context,
                definition=definition
            )
            ul_inputs.append(ul_input)
            note_id_map[uid] = note.get('noteId')

    print(f"Skipped {skipped} cards with existing Usage_Level")

    if not ul_inputs:
        print("No valid inputs for usage_level")
        return

    print(f"Processing {len(ul_inputs)} cards in batches of {batch_size}")

    # Process in batches
    for batch_idx in range(0, len(ul_inputs), batch_size):
        batch_inputs = ul_inputs[batch_idx:batch_idx + batch_size]
        batch_num = (batch_idx // batch_size) + 1
        total_batches = (len(ul_inputs) + batch_size - 1) // batch_size

        print(f"\nBatch {batch_num}/{total_batches}: Running usage_level on {len(batch_inputs)} cards (ignore_cache=True)")

        # Run usage_level with ignore_cache=True
        ul_outputs = ul_runtime.estimate(batch_inputs, runtime_config, ignore_cache=True)

        # Build batch update actions
        actions = []
        for ul_input, ul_output in zip(batch_inputs, ul_outputs):
            if ul_output.usage_level is not None:
                note_id = note_id_map[ul_input.uid]
                actions.append({
                    "action": "updateNoteFields",
                    "params": {
                        "note": {
                            "id": note_id,
                            "fields": {"Usage_Level": str(ul_output.usage_level)}
                        }
                    }
                })
                print(f"  Queued {ul_input.uid}: Usage_Level={ul_output.usage_level}")

        # Update all cards in one API call
        if actions:
            try:
                anki._invoke("multi", {"actions": actions})
                print(f"  Updated {len(actions)} cards")
            except Exception as e:
                print(f"  Batch update failed: {e}")

        # Exit after first batch for inspection (remove this line to process all)
        print("\nExiting after first batch for inspection. Remove exit() to process all.")
        exit()

    print("Done")


if __name__ == "__main__":
    main()

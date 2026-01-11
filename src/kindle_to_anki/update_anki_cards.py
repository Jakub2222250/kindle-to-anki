"""
Interactive script to update existing Anki cards by running selected tasks.
Supports configurable filtering (new/old cards, deck selection) and task options.
"""

import json
from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.anki.constants import NOTE_TYPE_NAME
from kindle_to_anki.configuration.config_manager import ConfigManager
from kindle_to_anki.configuration.options_display import show_task_options
from kindle_to_anki.configuration.prompts import prompt_choice, prompt_yes_no, prompt_int, prompt_choice_by_index
from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.core.prompts import get_default_prompt_id
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.runtimes.runtime_registry import RuntimeRegistry
from kindle_to_anki.tasks.wsd.schema import WSDInput, WSDOutput
from kindle_to_anki.tasks.hint.schema import HintInput, HintOutput
from kindle_to_anki.tasks.lui.schema import LUIInput, LUIOutput
from kindle_to_anki.tasks.collocation.schema import CollocationInput, CollocationOutput


AVAILABLE_TASKS = {
    "wsd": {
        "name": "Word Sense Disambiguation",
        "runtime_key": "wsd",
        "input_class": WSDInput,
        "output_field": "Definition",
        "output_attr": "definition",
        "runtime_method": "disambiguate",
    },
    "hint": {
        "name": "Hint Generation",
        "runtime_key": "hint",
        "input_class": HintInput,
        "output_field": "Hint",
        "output_attr": "hint",
        "runtime_method": "generate",
    },
    "lui": {
        "name": "Lexical Unit Identification",
        "runtime_key": "lui",
        "input_class": LUIInput,
        "output_fields": ["Expression", "Part_Of_Speech", "Aspect", "Surface_Lexical_Unit", "Unit_Type"],
        "output_attrs": ["lemma", "part_of_speech", "aspect", "surface_lexical_unit", "unit_type"],
        "runtime_method": "identify",
    },
    "collocation": {
        "name": "Collocation Generation",
        "runtime_key": "collocation",
        "input_class": CollocationInput,
        "output_field": "Collocations",
        "output_attr": "collocations",
        "runtime_method": "generate_collocations",
    },
}


def get_deck_filter_options(deck) -> list[str]:
    """Build list of deck filter options based on config."""
    options = [
        f"parent: {deck.parent_deck_name}",
        f"staging: {deck.staging_deck_name}",
    ]
    return options


def build_anki_query(deck, deck_choice: str, card_age: str) -> str:
    """Build Anki search query based on user choices."""
    # Determine deck filter
    if deck_choice.startswith("parent:"):
        deck_filter = f'"deck:{deck.parent_deck_name}"'
    elif deck_choice.startswith("staging:"):
        deck_filter = f'"deck:{deck.staging_deck_name}"'
    else:
        deck_filter = f'"deck:{deck.parent_deck_name}"'

    # Determine card age filter
    age_filter = ""
    if card_age == "new":
        age_filter = "is:new"
    elif card_age == "learning":
        age_filter = "is:learn"
    elif card_age == "review":
        age_filter = "is:review"
    elif card_age == "suspended":
        age_filter = "is:suspended"

    query = f'{deck_filter} "note:{NOTE_TYPE_NAME}"'
    if age_filter:
        query += f" {age_filter}"

    return query


def build_task_input(task_key: str, note: dict) -> object:
    """Build task input from note fields."""
    fields = note.get('fields', {})
    uid = fields.get('UID', {}).get('value', '').strip()
    expression = fields.get('Expression', {}).get('value', '').strip()
    surface_lexical_unit = fields.get('Surface_Lexical_Unit', {}).get('value', '').strip()
    context = fields.get('Context_Sentence', {}).get('value', '').strip()
    pos = fields.get('Part_Of_Speech', {}).get('value', '').strip() or 'unknown'
    raw_lookup = fields.get('Raw_Lookup_String', {}).get('value', '').strip()
    raw_context = fields.get('Raw_Context_Text', {}).get('value', '').strip()

    task_info = AVAILABLE_TASKS[task_key]
    input_class = task_info["input_class"]

    if task_key == "lui":
        # LUI uses raw lookup word and raw context
        word = raw_lookup or surface_lexical_unit or expression
        sentence = raw_context or context
        if not (uid and word and sentence):
            return None
        return input_class(uid=uid, word=word, sentence=sentence)

    elif task_key == "collocation":
        # Collocation uses lemma and pos
        if not (uid and expression):
            return None
        return input_class(uid=uid, lemma=expression, pos=pos)

    else:
        # WSD, hint use full context
        if not (uid and expression and context):
            return None
        return input_class(
            uid=uid,
            word=surface_lexical_unit or expression,
            lemma=expression,
            pos=pos,
            sentence=context,
        )


def get_note_task_metadata(note: dict, task_key: str) -> dict | None:
    """Extract metadata for a specific task from note's Generation_Metadata field."""
    fields = note.get('fields', {})
    metadata_str = fields.get('Generation_Metadata', {}).get('value', '').strip()
    if not metadata_str:
        return None
    try:
        metadata = json.loads(metadata_str)
        return metadata.get(task_key)
    except json.JSONDecodeError:
        return None


def metadata_matches(note: dict, task_key: str, runtime_id: str, model_id: str, prompt_id: str | None) -> bool:
    """Check if note's metadata matches the expected configuration."""
    task_meta = get_note_task_metadata(note, task_key)
    if not task_meta:
        return False
    # Missing "prompt" key is treated as None/default
    stored_prompt = task_meta.get("prompt")
    return (
        task_meta.get("runtime") == runtime_id
        and task_meta.get("model") == model_id
        and stored_prompt == prompt_id
    )


def build_generation_metadata_update(existing_metadata_str: str, task_key: str, runtime_id: str, model_id: str, prompt_id: str | None) -> str:
    """Build updated Generation_Metadata JSON string with new task metadata."""
    try:
        metadata = json.loads(existing_metadata_str) if existing_metadata_str else {}
    except json.JSONDecodeError:
        metadata = {}
    task_meta = {"runtime": runtime_id, "model": model_id}
    if prompt_id:
        task_meta["prompt"] = prompt_id
    metadata[task_key] = task_meta
    return json.dumps(metadata)


def run_task_on_notes(
    task_key: str,
    notes_info: list,
    runtime,
    runtime_config: RuntimeConfig,
    anki: AnkiConnect,
    ignore_cache: bool,
    batch_size: int,
    dry_run: bool = False,
    runtime_id: str = None,
):
    """Run the selected task on notes and update Anki."""
    task_info = AVAILABLE_TASKS[task_key]
    runtime_method = task_info["runtime_method"]

    # Handle single vs multi-field outputs
    output_fields = task_info.get("output_fields", [task_info.get("output_field")])
    output_attrs = task_info.get("output_attrs", [task_info.get("output_attr")])

    # Build inputs
    task_inputs = []
    note_id_map = {}
    note_metadata_map = {}  # uid -> existing metadata string

    for note in notes_info:
        task_input = build_task_input(task_key, note)
        if task_input:
            task_inputs.append(task_input)
            note_id_map[task_input.uid] = note.get('noteId')
            fields = note.get('fields', {})
            note_metadata_map[task_input.uid] = fields.get('Generation_Metadata', {}).get('value', '')

    if not task_inputs:
        print("No valid inputs for task")
        return

    print(f"Processing {len(task_inputs)} cards in batches of {batch_size}")

    if dry_run:
        print("DRY RUN - no changes will be made")
        for inp in task_inputs[:10]:
            # Handle different input types
            word_attr = getattr(inp, 'word', None) or getattr(inp, 'lemma', None) or ''
            print(f"  Would process: {inp.uid} - {word_attr}")
        if len(task_inputs) > 10:
            print(f"  ... and {len(task_inputs) - 10} more")
        return

    # Process in batches
    total_updated = 0
    for batch_idx in range(0, len(task_inputs), batch_size):
        batch_inputs = task_inputs[batch_idx:batch_idx + batch_size]
        batch_num = (batch_idx // batch_size) + 1
        total_batches = (len(task_inputs) + batch_size - 1) // batch_size

        print(f"\nBatch {batch_num}/{total_batches}: Running {task_key} on {len(batch_inputs)} cards (ignore_cache={ignore_cache})")

        # Run task
        method = getattr(runtime, runtime_method)
        outputs = method(batch_inputs, runtime_config, ignore_cache=ignore_cache)

        # Build batch update actions
        actions = []
        for task_input, output in zip(batch_inputs, outputs):
            note_id = note_id_map[task_input.uid]
            existing_meta = note_metadata_map.get(task_input.uid, '')
            new_meta = build_generation_metadata_update(
                existing_meta, task_key, runtime_id,
                runtime_config.model_id, runtime_config.prompt_id
            )

            # Build fields dict from output
            fields_update = {"Generation_Metadata": new_meta}
            preview_parts = []

            for field, attr in zip(output_fields, output_attrs):
                value = getattr(output, attr, None)
                if value is not None:
                    # Handle list outputs (e.g., collocations)
                    if isinstance(value, list):
                        value = ", ".join(str(v) for v in value)
                    fields_update[field] = str(value)
                    preview = str(value)[:30] + "..." if len(str(value)) > 30 else str(value)
                    preview_parts.append(f"{field}={preview}")

            if len(fields_update) > 1:  # More than just metadata
                actions.append({
                    "action": "updateNoteFields",
                    "params": {
                        "note": {
                            "id": note_id,
                            "fields": fields_update
                        }
                    }
                })
                print(f"  Queued {task_input.uid}: {', '.join(preview_parts[:2])}")

        # Update cards
        if actions:
            try:
                anki.update_notes_by_id(actions)
                total_updated += len(actions)
            except Exception as e:
                print(f"  Batch update failed: {e}")

    print(f"\nDone. Total updated: {total_updated}")


def main():
    bootstrap_all()

    config_manager = ConfigManager()
    anki_decks = config_manager.get_anki_decks_by_source_language()

    # Select language/deck
    available_langs = list(anki_decks.keys())
    if not available_langs:
        print("No decks configured")
        return

    if len(available_langs) == 1:
        lang = available_langs[0]
        print(f"Using deck for language: {lang}")
    else:
        lang = prompt_choice("Select language:", available_langs, available_langs[0])

    deck = anki_decks[lang]

    # Select task
    task_key = prompt_choice(
        "Select task to run:",
        list(AVAILABLE_TASKS.keys()),
        "wsd"
    )
    task_info = AVAILABLE_TASKS[task_key]
    print(f"Selected: {task_info['name']}")

    # Get task settings from config
    task_settings = config_manager.get_task_setting(task_key)
    default_runtime_id = task_settings.get("runtime", f"chat_completion_{task_key}")
    default_model_id = task_settings.get("model_id", "gpt-5.1")
    default_batch_size = task_settings.get("batch_size", 30)
    default_prompt_id = task_settings.get("prompt_id")

    # Ask about config override
    use_custom_config = prompt_yes_no("\nUse custom configuration (instead of config.json defaults)?", default=False)

    if use_custom_config:
        # Show available runtime/model options with costs
        options = show_task_options(task_key, deck.source_language_code, deck.target_language_code)
        if options:
            # Find current default index
            default_idx = 1
            for i, opt in enumerate(options, 1):
                if opt["runtime"] == default_runtime_id and opt["model_id"] == default_model_id:
                    default_idx = i
                    break
            choice_idx = prompt_choice_by_index("Select runtime/model option", options, default=default_idx)
            selected = options[choice_idx - 1]
            runtime_id = selected["runtime"]
            model_id = selected["model_id"]
        else:
            runtime_id = default_runtime_id
            model_id = default_model_id
        batch_size = prompt_int("Batch size", default_batch_size)
        prompt_id_input = input(f"Prompt ID [{default_prompt_id or 'None'}]: ").strip()
        prompt_id = prompt_id_input if prompt_id_input else default_prompt_id
    else:
        runtime_id = default_runtime_id
        model_id = default_model_id
        batch_size = default_batch_size
        prompt_id = default_prompt_id

    # Resolve effective prompt_id (use task default if none specified)
    if not prompt_id:
        prompt_id = get_default_prompt_id(task_key)

    print(f"\nUsing runtime: {runtime_id}, model: {model_id}, batch size: {batch_size}, prompt: {prompt_id}")

    # Deck filter
    deck_options = get_deck_filter_options(deck)
    deck_choice = prompt_choice("Select deck filter:", deck_options, deck_options[0])

    # Card age filter
    age_options = ["all", "new", "learning", "review", "suspended"]
    card_age = prompt_choice("Filter by card state:", age_options, "all")

    # Metadata filtering - only process cards that don't match current config
    filter_mismatched_metadata = prompt_yes_no(
        f"Only update cards with different/missing metadata for {task_key}?", default=True
    )

    # Cache options
    ignore_cache = prompt_yes_no("Ignore cache (force re-run)?", default=False)

    # Dry run option
    dry_run = prompt_yes_no("Dry run (preview only, no changes)?", default=False)

    # Card limit
    limit_input = input("Max cards to process (0 or blank for no limit): ").strip()
    card_limit = int(limit_input) if limit_input and limit_input.isdigit() and int(limit_input) > 0 else None

    # Build query and fetch cards
    query = build_anki_query(deck, deck_choice, card_age)
    print(f"\nAnki query: {query}")

    anki = AnkiConnect()
    note_ids = anki._invoke("findNotes", {"query": query})

    if not note_ids:
        print("No cards found matching query")
        return

    print(f"Found {len(note_ids)} cards matching query")

    # Get note info for filtering
    notes_info = anki._invoke("notesInfo", {"notes": note_ids})

    # Filter by metadata if requested (before applying limit)
    if filter_mismatched_metadata:
        filtered_notes = [
            note for note in notes_info
            if not metadata_matches(note, task_key, runtime_id, model_id, prompt_id)
        ]
        skipped_count = len(notes_info) - len(filtered_notes)
        if skipped_count:
            print(f"Filtered out {skipped_count} cards with matching metadata (already up-to-date)")
        notes_info = filtered_notes
        print(f"{len(notes_info)} cards need updating")

    if not notes_info:
        print("No cards need updating")
        return

    # Apply card limit (after metadata filtering)
    if card_limit and len(notes_info) > card_limit:
        notes_info = notes_info[:card_limit]
        print(f"Limiting to first {card_limit} cards")

    # Confirm before proceeding
    if not dry_run and not prompt_yes_no(f"Proceed with {len(notes_info)} cards?", default=True):
        print("Cancelled")
        return

    # Get runtime
    runtimes = RuntimeRegistry.find_by_task_as_dict(task_key)
    runtime = runtimes.get(runtime_id)
    if not runtime:
        print(f"Runtime '{runtime_id}' not found for task '{task_key}'")
        return

    runtime_config = RuntimeConfig(
        model_id=model_id,
        batch_size=batch_size,
        source_language_code=deck.source_language_code,
        target_language_code=deck.target_language_code,
        prompt_id=prompt_id,
    )

    run_task_on_notes(
        task_key=task_key,
        notes_info=notes_info,
        runtime=runtime,
        runtime_config=runtime_config,
        anki=anki,
        ignore_cache=ignore_cache,
        batch_size=batch_size,
        dry_run=dry_run,
        runtime_id=runtime_id,
    )


if __name__ == "__main__":
    main()

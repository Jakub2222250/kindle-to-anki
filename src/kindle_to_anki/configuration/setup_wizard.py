from kindle_to_anki.configuration.prompts import prompt_yes_no, prompt_choice_by_index as prompt_choice
import json
import urllib.request
import urllib.error
from pathlib import Path

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.configuration.options_display import show_task_options, get_options_for_task


class AnkiConnectHelper:
    """Lightweight AnkiConnect helper for deck operations."""

    def __init__(self):
        self.anki_url = "http://localhost:8765"

    def _invoke(self, action, params=None):
        request_json = {"action": action, "version": 6}
        if params:
            request_json["params"] = params
        try:
            request_data = json.dumps(request_json).encode('utf-8')
            request = urllib.request.Request(self.anki_url, request_data)
            response = urllib.request.urlopen(request)
            response_data = json.loads(response.read().decode('utf-8'))
            if response_data.get('error'):
                raise Exception(f"AnkiConnect error: {response_data['error']}")
            return response_data.get('result')
        except urllib.error.URLError:
            return None

    def is_reachable(self) -> bool:
        try:
            return self._invoke("version") is not None
        except Exception:
            return False

    def get_deck_names(self) -> list[str]:
        result = self._invoke("deckNames")
        return result if result else []

    def get_model_names(self) -> list[str]:
        result = self._invoke("modelNames")
        return result if result else []

    def create_deck(self, deck_name: str) -> bool:
        result = self._invoke("createDeck", {"deck": deck_name})
        return result is not None


DEFAULT_CONFIG = {
    "anki_decks": [],
    "task_settings": {
        "lui": {"runtime": "chat_completion_lui", "model_id": "gemini-2.5-flash", "batch_size": 30},
        "wsd": {"runtime": "chat_completion_wsd", "model_id": "gemini-2.5-flash", "batch_size": 30},
        "hint": {"enabled": True, "runtime": "chat_completion_hint", "model_id": "gemini-2.5-flash", "batch_size": 30},
        "cloze_scoring": {"enabled": True, "runtime": "chat_completion_cloze_scoring", "model_id": "gemini-2.5-flash", "batch_size": 30},
        "usage_level": {"enabled": True, "runtime": "chat_completion_usage_level", "model_id": "gemini-2.5-flash", "batch_size": 30},
        "translation": {"runtime": "chat_completion_translation", "model_id": "gemini-2.5-flash", "batch_size": 30},
        "collocation": {"enabled": True, "runtime": "chat_completion_collocation", "model_id": "gemini-2.0-flash", "batch_size": 30}
    }
}

CONFIGURABLE_TASKS = ["lui", "wsd", "hint", "cloze_scoring", "usage_level", "translation", "collocation"]
OPTIONAL_TASKS = ["hint", "cloze_scoring", "usage_level", "collocation"]


def get_config_path() -> Path:
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent.parent
    return project_root / "data" / "config" / "config.json"


def load_config() -> dict:
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_config(config: dict):
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    print(f"Configuration saved to {config_path}")


def offer_create_decks_in_anki(parent: str, staging: str):
    """Offer to create decks in Anki if missing."""
    helper = AnkiConnectHelper()
    if not helper.is_reachable():
        print("AnkiConnect not reachable. Skipping deck creation check.")
        return

    existing_decks = helper.get_deck_names()
    for deck_name in [parent, staging]:
        if deck_name in existing_decks:
            print(f"  \u2713 '{deck_name}' exists in Anki")
        else:
            if prompt_yes_no(f"Create '{deck_name}' in Anki?"):
                if helper.create_deck(deck_name):
                    print(f"  Created '{deck_name}'")
                else:
                    print(f"  Failed to create '{deck_name}'")


def add_deck(config: dict):
    print("\n--- Add New Deck ---")
    source = input("Source language code (e.g., es, de, fr): ").strip().lower()
    target = input("Target language code (e.g., en) [en]: ").strip().lower() or "en"
    parent = input(f"Parent deck name [Vocab Discovery]: ").strip() or "Vocab Discovery"
    staging = input(f"Staging/import deck name [{parent}::Import]: ").strip() or f"{parent}::Import"

    deck = {
        "source_language_code": source,
        "target_language_code": target,
        "parent_deck_name": parent,
        "staging_deck_name": staging
    }
    config["anki_decks"].append(deck)
    print(f"Added deck: {source} -> {target}")
    offer_create_decks_in_anki(parent, staging)


def remove_deck(config: dict):
    decks = config.get("anki_decks", [])
    if not decks:
        print("No decks to remove.")
        return

    print("\n--- Remove Deck ---")
    for i, deck in enumerate(decks, 1):
        print(f"  [{i}] {deck['source_language_code']} -> {deck['target_language_code']} ({deck['parent_deck_name']})")

    choice = prompt_choice("Select deck to remove", decks)
    removed = decks.pop(choice - 1)
    print(f"Removed deck: {removed['source_language_code']} -> {removed['target_language_code']}")


def edit_deck(config: dict):
    decks = config.get("anki_decks", [])
    if not decks:
        print("No decks to edit.")
        return

    print("\n--- Edit Deck ---")
    for i, deck in enumerate(decks, 1):
        print(f"  [{i}] {deck['source_language_code']} -> {deck['target_language_code']} ({deck['parent_deck_name']})")

    choice = prompt_choice("Select deck to edit", decks)
    deck = decks[choice - 1]

    new_parent = input(f"Parent deck name [{deck['parent_deck_name']}]: ").strip()
    if new_parent:
        deck["parent_deck_name"] = new_parent

    new_staging = input(f"Staging deck name [{deck['staging_deck_name']}]: ").strip()
    if new_staging:
        deck["staging_deck_name"] = new_staging

    print("Deck updated.")
    offer_create_decks_in_anki(deck["parent_deck_name"], deck["staging_deck_name"])


def manage_decks(config: dict):
    while True:
        decks = config.get("anki_decks", [])
        print("\n--- Deck Management ---")
        print(f"Current decks ({len(decks)}):")
        for deck in decks:
            print(f"  - {deck['source_language_code']} -> {deck['target_language_code']} | Parent: {deck['parent_deck_name']} | Import: {deck['staging_deck_name']}")

        print("\nOptions:")
        print("  [1] Add deck")
        print("  [2] Remove deck")
        print("  [3] Edit deck")
        print("  [4] Done")

        choice = input("Select option [4]: ").strip() or "4"
        if choice == "1":
            add_deck(config)
        elif choice == "2":
            remove_deck(config)
        elif choice == "3":
            edit_deck(config)
        elif choice == "4":
            break


def configure_task(config: dict, task: str, source_language_code: str, target_language_code: str):
    current = config["task_settings"].get(task, DEFAULT_CONFIG["task_settings"].get(task, {}))

    # Handle optional tasks
    if task in OPTIONAL_TASKS:
        is_enabled = current.get("enabled", True)
        status = "enabled" if is_enabled else "disabled"
        print(f"\nCurrent {task} setting: {status}, runtime={current.get('runtime')}, model={current.get('model_id')}")

        if prompt_yes_no(f"Enable {task}?", default=is_enabled):
            current["enabled"] = True
        else:
            current["enabled"] = False
            config["task_settings"][task] = current
            print(f"{task} disabled.")
            return
    else:
        print(f"\nCurrent {task} setting: runtime={current.get('runtime')}, model={current.get('model_id')}")

    if not prompt_yes_no(f"Change {task} runtime/model settings?", default=False):
        if task in OPTIONAL_TASKS:
            config["task_settings"][task] = current
        return

    options = show_task_options(task, source_language_code, target_language_code)
    if not options:
        print(f"No options available for task '{task}'")
        return

    # Find default index
    default_idx = 1
    for i, opt in enumerate(options, 1):
        if opt["runtime"] == current.get("runtime") and opt["model_id"] == current.get("model_id"):
            default_idx = i
            break

    choice = prompt_choice("Select option", options, default=default_idx)
    selected = options[choice - 1]

    new_setting = {
        "runtime": selected["runtime"],
        "model_id": selected["model_id"],
        "batch_size": 30
    }
    if task in OPTIONAL_TASKS:
        new_setting["enabled"] = current.get("enabled", True)

    config["task_settings"][task] = new_setting
    print(f"Updated {task}: runtime={selected['runtime']}, model={selected['model_id']}")


def configure_tasks(config: dict):
    decks = config.get("anki_decks", [])
    if not decks:
        print("Please add at least one deck first to configure tasks.")
        return

    # Use first deck's language pair for showing options
    source = decks[0]["source_language_code"]
    target = decks[0]["target_language_code"]

    print(f"\n--- Task Configuration (showing costs for {source}->{target}) ---")
    print("Note: Optional tasks can be disabled to reduce API costs.\n")
    for task in CONFIGURABLE_TASKS:
        configure_task(config, task, source, target)


def check_and_create_note_type():
    """Check if note type exists in Anki and offer to create if missing."""
    from kindle_to_anki.anki.constants import NOTE_TYPE_NAME
    from kindle_to_anki.anki.setup_note_type import setup_note_type

    helper = AnkiConnectHelper()
    if not helper.is_reachable():
        print("AnkiConnect not reachable. Skipping note type check.")
        return

    existing_models = helper.get_model_names()
    if NOTE_TYPE_NAME in existing_models:
        print(f"\u2713 Note type '{NOTE_TYPE_NAME}' exists")
    else:
        print(f"\u2717 Note type '{NOTE_TYPE_NAME}' missing")
        if prompt_yes_no(f"Create note type '{NOTE_TYPE_NAME}' in Anki?"):
            setup_note_type()


def run_setup_wizard():
    print("=== Kindle to Anki Configuration Setup ===\n")

    bootstrap_all()

    # Check note type at startup
    check_and_create_note_type()

    existing_config = load_config()

    if existing_config:
        print("Existing configuration found.")
        if prompt_yes_no("Modify existing configuration?"):
            config = existing_config
        else:
            if prompt_yes_no("Start fresh with defaults?", default=False):
                config = json.loads(json.dumps(DEFAULT_CONFIG))
            else:
                print("Setup cancelled.")
                return
    else:
        print("No configuration found. Starting with defaults.")
        config = json.loads(json.dumps(DEFAULT_CONFIG))

    # Main menu loop
    while True:
        print("\n=== Main Menu ===")
        print("  [1] Manage decks")
        print("  [2] Configure tasks")
        print("  [3] Save and exit")
        print("  [4] Exit without saving")

        choice = input("Select option: ").strip()
        if choice == "1":
            manage_decks(config)
        elif choice == "2":
            configure_tasks(config)
        elif choice == "3":
            save_config(config)
            break
        elif choice == "4":
            if prompt_yes_no("Exit without saving?", default=False):
                print("Exiting without saving.")
                break


if __name__ == "__main__":
    run_setup_wizard()

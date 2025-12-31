import json
from pathlib import Path

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.configuration.options_display import show_task_options, get_options_for_task


DEFAULT_CONFIG = {
    "anki_decks": [],
    "task_settings": {
        "lui": {"runtime": "chat_completion_lui", "model_id": "gpt-5.1", "batch_size": 30},
        "wsd": {"runtime": "chat_completion_wsd", "model_id": "gpt-5.1", "batch_size": 30},
        "translation": {"runtime": "chat_completion_translation", "model_id": "gpt-5.1", "batch_size": 30},
        "collocation": {"runtime": "chat_completion_collocation", "model_id": "gpt-5-mini", "batch_size": 30}
    }
}

CONFIGURABLE_TASKS = ["lui", "wsd", "translation", "collocation"]


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


def prompt_yes_no(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    response = input(f"{prompt} [{default_str}]: ").strip().lower()
    if not response:
        return default
    return response in ('y', 'yes')


def prompt_choice(prompt: str, options: list, default: int = 1) -> int:
    while True:
        response = input(f"{prompt} [default={default}]: ").strip()
        if not response:
            return default
        try:
            choice = int(response)
            if 1 <= choice <= len(options):
                return choice
        except ValueError:
            pass
        print(f"Please enter a number between 1 and {len(options)}")


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
    print(f"\nCurrent {task} setting: runtime={current.get('runtime')}, model={current.get('model_id')}")
    
    if not prompt_yes_no(f"Change {task} settings?", default=False):
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
    
    config["task_settings"][task] = {
        "runtime": selected["runtime"],
        "model_id": selected["model_id"],
        "batch_size": 30
    }
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
    for task in CONFIGURABLE_TASKS:
        configure_task(config, task, source, target)


def run_setup_wizard():
    print("=== Kindle to Anki Configuration Setup ===\n")
    
    bootstrap_all()
    
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

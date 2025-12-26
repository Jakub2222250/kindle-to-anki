import json
from pathlib import Path
from anki.anki_deck import AnkiDeck


def get_config_file_path():
    """Get the path to the anki_decks.json configuration file."""
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent.parent
    config_path = project_root / "data" / "config" / "anki_decks.json"
    return config_path


def load_anki_decks_config():
    """Load anki deck configuration from JSON file."""
    config_path = get_config_file_path()
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    return config_data


def get_anki_decks_by_source_language():
    """Get anki decks organized by source language code."""
    config_data = load_anki_decks_config()
    
    anki_decks_list = []
    for deck_config in config_data['anki_decks']:
        deck = AnkiDeck(
            source_lang_code=deck_config['source_lang_code'],
            target_lang_code=deck_config['target_lang_code'],
            parent_deck_name=deck_config['parent_deck_name'],
            ready_deck_name=deck_config['ready_deck_name'],
            staging_deck_name=deck_config['staging_deck_name']
        )
        anki_decks_list.append(deck)
    
    anki_decks_by_source_language = {}
    for deck in anki_decks_list:
        anki_decks_by_source_language[deck.source_lang_code] = deck
    
    return anki_decks_by_source_language
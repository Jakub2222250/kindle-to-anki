import json
from pathlib import Path
from anki.anki_deck import AnkiDeck


class ConfigManager:
    """Manages configuration loading and deck setup for the application."""
    
    def __init__(self):
        """Initialize ConfigManager and resolve configuration file path."""
        self._config_path = self._resolve_config_path()
        self._config_data = None
        self._anki_decks_by_source_language = None
    
    def _resolve_config_path(self):
        """Resolve the path to the anki_decks.json configuration file."""
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parent.parent.parent
        config_path = project_root / "data" / "config" / "anki_decks.json"
        return config_path
    
    @property
    def config_path(self):
        """Get the resolved configuration file path."""
        return self._config_path
    
    def load_config_data(self):
        """Load anki deck configuration from JSON file."""
        if self._config_data is None:
            if not self._config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self._config_path}")
            
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config_data = json.load(f)
        
        return self._config_data
    
    def get_anki_decks_by_source_language(self):
        """Get anki decks organized by source language code."""
        if self._anki_decks_by_source_language is None:
            config_data = self.load_config_data()
            
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
            
            self._anki_decks_by_source_language = {}
            for deck in anki_decks_list:
                self._anki_decks_by_source_language[deck.source_lang_code] = deck
        
        return self._anki_decks_by_source_language

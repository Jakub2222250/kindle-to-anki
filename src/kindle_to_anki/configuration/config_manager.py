import json
from pathlib import Path
from kindle_to_anki.anki.anki_deck import AnkiDeck


class ConfigManager:
    
    def __init__(self):
        self._config_path = self._resolve_config_path()
        self._config_data = None
        self._anki_decks_by_source_language = None
    
    def _resolve_config_path(self):
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parent.parent.parent
        config_path = project_root / "data" / "config" / "config.json"
        return config_path
    
    @property
    def config_path(self):
        return self._config_path
    
    def load_config_data(self):
        if self._config_data is None:
            if not self._config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self._config_path}")
            
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config_data = json.load(f)
        
        return self._config_data
    
    def get_anki_decks_by_source_language(self):
        if self._anki_decks_by_source_language is None:
            config_data = self.load_config_data()
            
            anki_decks_list = []
            for deck_config in config_data['anki_decks']:
                deck = AnkiDeck(
                    source_language_code=deck_config['source_language_code'],
                    target_language_code=deck_config['target_language_code'],
                    parent_deck_name=deck_config['parent_deck_name'],
                    staging_deck_name=deck_config['staging_deck_name']
                )
                anki_decks_list.append(deck)
            
            self._anki_decks_by_source_language = {}
            for deck in anki_decks_list:
                self._anki_decks_by_source_language[deck.source_language_code] = deck
        
        return self._anki_decks_by_source_language

    def get_task_setting(self, task_name: str) -> dict:
        config_data = self.load_config_data()
        return config_data.get('task_settings', {}).get(task_name, {})

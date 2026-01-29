import json
from pathlib import Path
from kindle_to_anki.anki.anki_deck import AnkiDeck
from kindle_to_anki.util.paths import get_config_path


class ConfigManager:

    def __init__(self):
        self._config_path = get_config_path()
        self._config_data = None
        self._anki_decks_by_source_language = None

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
                    staging_deck_name=deck_config['staging_deck_name'],
                    task_settings=deck_config.get('task_settings', {}),
                    preview_options=deck_config.get('preview_options')
                )
                anki_decks_list.append(deck)

            self._anki_decks_by_source_language = {}
            for deck in anki_decks_list:
                self._anki_decks_by_source_language[deck.source_language_code] = deck

        return self._anki_decks_by_source_language

    def get_task_setting(self, task_name: str, source_language_code: str) -> dict:
        """Get task setting for a specific deck by source language code."""
        decks = self.get_anki_decks_by_source_language()
        deck = decks.get(source_language_code)
        if deck:
            return deck.get_task_setting(task_name)
        return {}

    def save_preview_options(self, source_language_code: str, preview_options: dict):
        """Save preview options for a deck to the config file."""
        config_data = self.load_config_data()

        for deck_config in config_data['anki_decks']:
            if deck_config['source_language_code'] == source_language_code:
                deck_config['preview_options'] = preview_options
                break

        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        # Update cached deck object
        if self._anki_decks_by_source_language:
            deck = self._anki_decks_by_source_language.get(source_language_code)
            if deck:
                deck.preview_options = preview_options

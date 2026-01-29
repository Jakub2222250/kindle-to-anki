class AnkiDeck:
    def __init__(self, source_language_code: str, target_language_code: str, staging_deck_name: str, parent_deck_name: str, task_settings: dict = None, preview_options: dict = None):
        self.source_language_code = source_language_code
        self.target_language_code = target_language_code
        self.parent_deck_name = parent_deck_name
        self.staging_deck_name = staging_deck_name
        self.task_settings = task_settings or {}
        self.preview_options = preview_options or {"note_limit_enabled": True, "note_limit": 30}

    def get_language_pair_code(self):
        return f"{self.source_language_code}-{self.target_language_code}"

    def get_task_setting(self, task_name: str) -> dict:
        return self.task_settings.get(task_name, {})

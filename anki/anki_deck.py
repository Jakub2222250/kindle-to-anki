class AnkiDeck:
    def __init__(self, source_lang_code: str, target_lang_code: str, ready_deck_name: str, staging_deck_name: str, parent_deck_name: str):
        self.source_lang_code = source_lang_code
        self.target_lang_code = target_lang_code
        self.parent_deck_name = parent_deck_name
        self.ready_deck_name = ready_deck_name
        self.staging_deck_name = staging_deck_name

    def get_language_pair_code(self):
        return f"{self.source_lang_code}-{self.target_lang_code}"

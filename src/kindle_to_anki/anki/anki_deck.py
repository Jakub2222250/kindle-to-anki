class AnkiDeck:
    def __init__(self, source_language_code: str, target_language_code: str, staging_deck_name: str, parent_deck_name: str):
        self.source_language_code = source_language_code
        self.target_language_code = target_language_code
        self.parent_deck_name = parent_deck_name
        self.staging_deck_name = staging_deck_name

    def get_language_pair_code(self):
        return f"{self.source_language_code}-{self.target_language_code}"

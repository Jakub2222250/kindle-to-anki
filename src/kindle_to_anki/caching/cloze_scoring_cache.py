from kindle_to_anki.caching.base_cache import LLMCache


class ClozeScoringCache(LLMCache):
    def __init__(self, cache_dir=None, cache_suffix='default'):
        super().__init__("cloze_scoring_cache", cache_dir, cache_suffix)

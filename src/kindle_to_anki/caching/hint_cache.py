from kindle_to_anki.caching.base_cache import LLMCache


class HintCache(LLMCache):
    def __init__(self, cache_dir=None, cache_suffix='default'):
        super().__init__("hint_cache", cache_dir, cache_suffix)

from kindle_to_anki.caching.base_cache import LLMCache


class LUICache(LLMCache):
    def __init__(self, cache_dir=None, cache_suffix='default'):
        super().__init__("lui_cache", cache_dir, cache_suffix)

from kindle_to_anki.caching.base_cache import LLMCache


class UsageLevelCache(LLMCache):
    def __init__(self, cache_dir=None, cache_suffix='default'):
        super().__init__("usage_level_cache", cache_dir, cache_suffix)

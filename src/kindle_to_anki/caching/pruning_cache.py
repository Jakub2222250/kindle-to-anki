from kindle_to_anki.caching.base_cache import BaseCache


class PruningCache(BaseCache):
    """Cache for pruning results - not LLM-based, so no runtime/model/prompt keying."""

    def __init__(self, cache_dir=None, cache_suffix='default'):
        super().__init__("pruning_cache", cache_dir, cache_suffix)

    def get(self, uid):
        """Get cached pruning result for UID"""
        cache_entry = self.cache.get(uid)
        if cache_entry and isinstance(cache_entry, dict) and "data" in cache_entry:
            return cache_entry["data"]
        return None

    def set(self, uid, is_redundant, similarity_factor=None, matched_expression=None, timestamp=None):
        """Set cached pruning result for UID"""
        self.cache[uid] = {
            "data": {
                "is_redundant": is_redundant,
                "similarity_factor": similarity_factor,
                "matched_expression": matched_expression
            },
            "timestamp": timestamp
        }
        self._save_cache()

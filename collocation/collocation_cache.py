from pathlib import Path
import json


class CollocationCache:
    def __init__(self, cache_dir="cache", cache_suffix='default'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / f"collocation_cache_{cache_suffix}.json"

        # Load existing cache
        self.cache = self.load_cache()

    def load_cache(self):
        """Load cache from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}

    def save_cache(self):
        """Save cache to file"""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def get(self, uid):
        """Get cached collocation result for UID"""
        cache_entry = self.cache.get(uid)
        if cache_entry and isinstance(cache_entry, dict) and "collocation_data" in cache_entry:
            return cache_entry["collocation_data"]
        return None

    def set(self, uid, collocation_result, model_used=None, timestamp=None):
        """Set cached collocation result for UID"""
        cache_entry = {
            "collocation_data": collocation_result,
            "model_used": model_used,
            "timestamp": timestamp
        }
        self.cache[uid] = cache_entry
        self.save_cache()

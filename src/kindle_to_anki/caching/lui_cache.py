from pathlib import Path
import json


class LUICache:
    def __init__(self, cache_dir=None, cache_suffix='default'):
        if cache_dir is None:
            # Default to project root .cache directory
            project_root = Path(__file__).parent.parent.parent.parent
            cache_dir = project_root / ".cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / f"lui_cache_{cache_suffix}.json"

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
        """Get cached MA result for UID"""
        cache_entry = self.cache.get(uid)
        if cache_entry and isinstance(cache_entry, dict) and "ma_data" in cache_entry:
            return cache_entry["ma_data"]
        return None

    def set(self, uid, ma_result, model_used=None, timestamp=None):
        """Set cached MA result for UID"""
        cache_entry = {
            "ma_data": ma_result,
            "model_used": model_used,
            "timestamp": timestamp
        }
        self.cache[uid] = cache_entry
        self.save_cache()

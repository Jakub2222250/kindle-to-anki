from pathlib import Path
import json


class SourceLanguageHintCache:
    def __init__(self, cache_dir=None, cache_suffix='default'):
        if cache_dir is None:
            project_root = Path(__file__).parent.parent.parent.parent
            cache_dir = project_root / ".cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / f"source_language_hint_cache_{cache_suffix}.json"
        self.cache = self.load_cache()

    def load_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}

    def save_cache(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def get(self, uid):
        cache_entry = self.cache.get(uid)
        if cache_entry and isinstance(cache_entry, dict) and "data" in cache_entry:
            return cache_entry["data"]
        return None

    def set(self, uid, result, model_used=None, timestamp=None):
        cache_entry = {
            "data": result,
            "model_used": model_used,
            "timestamp": timestamp
        }
        self.cache[uid] = cache_entry
        self.save_cache()

from pathlib import Path
import json


class BaseCache:
    """Base class for simple caches without runtime/model/prompt keying."""

    def __init__(self, cache_name: str, cache_dir=None, cache_suffix='default'):
        if cache_dir is None:
            project_root = Path(__file__).parent.parent.parent.parent
            cache_dir = project_root / ".cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / f"{cache_name}_{cache_suffix}.json"
        self.cache = self._load_cache()

    def _load_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}

    def _save_cache(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)


class LLMCache(BaseCache):
    """Cache for LLM results, keyed by UID -> (runtime + model + prompt) -> data."""

    def __init__(self, cache_name: str, cache_dir=None, cache_suffix='default'):
        super().__init__(cache_name, cache_dir, cache_suffix)

    def _make_key(self, runtime: str, model: str, prompt: str) -> str:
        return f"{runtime}|{model}|{prompt}"

    def get(self, uid: str, runtime: str, model: str, prompt: str):
        """Get cached result for UID with specific runtime/model/prompt combination."""
        uid_entries = self.cache.get(uid)
        if not uid_entries or not isinstance(uid_entries, dict):
            return None
        key = self._make_key(runtime, model, prompt)
        entry = uid_entries.get(key)
        if entry and isinstance(entry, dict) and "data" in entry:
            return entry["data"]
        return None

    def set(self, uid: str, runtime: str, model: str, prompt: str, result, timestamp=None):
        """Set cached result for UID with specific runtime/model/prompt combination."""
        if uid not in self.cache:
            self.cache[uid] = {}
        key = self._make_key(runtime, model, prompt)
        self.cache[uid][key] = {
            "data": result,
            "timestamp": timestamp
        }
        self._save_cache()

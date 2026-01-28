from datetime import datetime, timezone
import json
from pathlib import Path

from kindle_to_anki.util.paths import get_metadata_dir


class MetadataManager:

    def __init__(self):
        self.metadata_path = get_metadata_dir() / "metadata.json"

    def load_metadata(self):
        """Load metadata from metadata/metadata.json if it exists"""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                print("Warning: Could not read metadata.json, starting fresh")
                exit()

        return {}

    def save_metadata(self, metadata):
        """Save metadata to metadata/metadata.json"""
        print("\nSaving metadata...")
        self.metadata_path.parent.mkdir(exist_ok=True)

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"Metadata saved to {self.metadata_path}")

    def save_latest_vocab_builder_entry_timestamp(self, max_timestamp: datetime, metadata):
        """Save the max timestamp from current import for future incremental imports"""
        max_iso_timestamp = max_timestamp.isoformat()

        print(f"\nMax timestamp from this import: {max_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        metadata['last_vocab_entry_timestamp'] = max_iso_timestamp
        self.save_metadata(metadata)
        print("Timestamp saved. Future runs will offer to import only newer notes.")

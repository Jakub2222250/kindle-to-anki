import json
import time
from pathlib import Path


class MetadataManager:

    def __init__(self):
        script_dir = Path(__file__).parent
        self.metadata_path = script_dir / ".metadata" / "metadata.json"

    def load_metadata(self):
        """Load metadata from metadata/metadata.json if it exists"""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                print("Warning: Could not read metadata.json, starting fresh")

        return {}

    def save_metadata(self, metadata):
        """Save metadata to metadata/metadata.json"""

        print("\nSaving last run time to metadata...")

        self.metadata_path.parent.mkdir(exist_ok=True)

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"Metadata saved to {self.metadata_path}")

    def save_script_run_timestamp(self, metadata):
        """Save the current timestamp as script run time to metadata"""
        current_time_ms = int(time.time() * 1000)
        metadata['last_script_run'] = current_time_ms
        self.save_metadata(metadata)

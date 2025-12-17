import json
import time
from pathlib import Path


class MetadataManager:
    def load_metadata():
        """Load metadata from metadata/metadata.json if it exists"""
        script_dir = Path(__file__).parent
        metadata_path = script_dir / ".metadata" / "metadata.json"

        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                print("Warning: Could not read metadata.json, starting fresh")

        return {}

    def save_metadata(metadata):
        """Save metadata to metadata/metadata.json"""

        print("\nSaving last run time to metadata...")

        script_dir = Path(__file__).parent
        metadata_dir = script_dir / ".metadata"
        metadata_dir.mkdir(exist_ok=True)

        metadata_path = metadata_dir / "metadata.json"

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"Metadata saved to {metadata_path}")

    def save_script_run_timestamp(metadata):
        """Save the current timestamp as script run time to metadata"""
        current_time_ms = int(time.time() * 1000)
        metadata['last_script_run'] = current_time_ms
        MetadataManager.save_metadata(metadata)

from datetime import datetime
import json
import time


class MetadataManager:

    def __init__(self, script_dir):
        # Use project root for .metadata folder
        project_root = script_dir.parent.parent
        self.metadata_path = project_root / ".metadata" / "metadata.json"

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

    def save_latest_vocab_builder_entry_timestamp(self, vocab_data, metadata):
        """Save the max timestamp from current import for future incremental imports"""
        if not vocab_data:
            return

        max_timestamp = max(row[6] for row in vocab_data)  # timestamp is at index 6
        human_readable_time = datetime.fromtimestamp(max_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        print(f"\nMax timestamp from this import: {human_readable_time}")

        metadata['last_timestamp_import'] = max_timestamp
        self.save_metadata(metadata)
        print("Timestamp saved. Future runs will offer to import only newer notes.")

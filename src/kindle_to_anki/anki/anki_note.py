from datetime import datetime
import hashlib
import json
import unicodedata


class AnkiNote:
    """
    Represents a vocabulary note for Anki import.

    Required fields (fundamental to any vocabulary lookup):
        - word: The looked-up word form
        - usage: Context sentence where the word appeared
        - language: Source language code

    Optional fields (may vary by vocabulary source):
        - uid: Unique identifier (if not provided, generated from word + usage hash)
        - stem: Base/dictionary form if known
        - book_name: Source book/document name
        - position: Location within the source
        - timestamp: When the lookup occurred
    """

    def __init__(
        self,
        word: str,
        usage: str,
        language: str,
        uid: str = None,
        *,  # Force remaining args to be keyword-only
        stem: str = None,
        book_name: str = None,
        position: str = None,
        timestamp: datetime = None
    ):
        # Required fields
        self.source_word = word
        self.source_usage = usage
        self.source_language = language

        # Generate UID if not provided
        self.uid = uid or self._generate_default_uid(word, usage)

        # Optional source metadata
        self.source_stem = stem
        self.source_book_name = book_name
        self.source_location = position
        self.source_timestamp = timestamp

        # Output fields derived from source
        self.expression = self.source_stem or ""
        self.surface_lexical_unit = self.source_word or ""
        self.context_sentence = self.source_usage or ""
        self.source_book = self.source_book_name or ""
        self.location = f"loc_{position}" if position else ""
        self.raw_context_text = self.source_usage or ""
        self.raw_lookup_string = self.source_word or ""

        # Processing output fields (populated by tasks)
        self.part_of_speech = ""
        self.definition = ""
        self.aspect = ""
        self.unit_type = "lemma"
        self.context_sentence_cloze = ""
        self.context_translation = ""
        self.collocations = ""
        self.original_language_hint = ""
        self.hint_test_enabled = ""
        self.notes = ""
        self.status = "raw"
        self.cloze_deletion_score = -1
        self.cloze_enabled = None
        self.generation_metadata = {}
        self.usage_level = ""

        # Generate book abbreviation for tagging
        self.book_abbrev = self.generate_book_abbrev(self.source_book_name)

        # Format usage text for HTML
        self.format_context_sentence()

        # Set tags based on language and book abbreviation
        self.set_tags(language)

    def apply_wsd_results(self, wsd_data):
        """Apply WSD data to the note"""
        if not wsd_data:
            return []

        if wsd_data.get('definition'):
            self.definition = wsd_data['definition']

    def apply_hint_results(self, data):
        """Apply hint results to the note"""
        if not data:
            return
        if data.get('hint'):
            self.original_language_hint = data['hint']

    def apply_cloze_scoring_results(self, data):
        """Apply cloze scoring results to the note"""
        if not data:
            return
        if data.get('cloze_deletion_score') is not None:
            score = data['cloze_deletion_score']
            self.cloze_deletion_score = score
            self.cloze_enabled = "True" if score >= 7 else None

    def apply_usage_level_results(self, data):
        """Apply usage level results to the note"""
        if not data:
            return
        if data.get('usage_level') is not None:
            self.usage_level = str(data['usage_level'])

    def generate_book_abbrev(self, book_name):
        """Generate book abbreviation for use as tag"""
        if not book_name:
            return "unknown"

        # Remove diacritics by normalizing to NFD and filtering out combining characters
        normalized = unicodedata.normalize('NFD', book_name)
        without_diacritics = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')

        # Convert to lowercase and replace spaces with underscores
        # Remove punctuation except hyphens which become underscores
        result = without_diacritics.lower()
        result = result.replace('-', '_')

        # Remove other punctuation
        punctuation_to_remove = '.,!?;:"()[]{}'
        for punct in punctuation_to_remove:
            result = result.replace(punct, '')

        # Replace spaces with underscores and clean up multiple underscores
        result = result.replace(' ', '_')

        # Remove multiple consecutive underscores
        while '__' in result:
            result = result.replace('__', '_')

        # Remove leading/trailing underscores
        result = result.strip('_')

        return result if result else "unknown"

    @staticmethod
    def normalize_for_uid(text: str, max_length: int = None) -> str:
        """Normalize text for use in UID generation (remove diacritics, lowercase, etc.)"""
        if not text:
            return "unknown"
        normalized = unicodedata.normalize('NFD', text)
        result = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')
        result = result.lower().replace(' ', '_')
        if max_length:
            result = result[:max_length]
        return result if result else "unknown"

    def format_context_sentence(self):
        """Format usage text for HTML display"""
        self.context_sentence = self.context_sentence.replace('\n', '<br>').replace('\r', '')

    def set_tags(self, language=None):
        """Set tags based on language and book abbreviation"""
        base_tags = ["kindle_to_anki"]

        if language:
            base_tags.append(language)

        if self.book_abbrev and self.book_abbrev != "unknown":
            base_tags.append(self.book_abbrev)

        self.tags = " ".join(base_tags)

    def _generate_default_uid(self, word: str, usage: str) -> str:
        """Generate a default UID from word and usage hash when not provided by runtime."""
        word_part = self.normalize_for_uid(word, max_length=10)
        usage_hash = hashlib.md5(usage.encode('utf-8')).hexdigest()[:8]
        return f"{word_part}_{usage_hash}"

    def get_context_sentence_cloze(self):
        """Get context sentence with word replaced by [...]"""
        if self.context_sentence and self.surface_lexical_unit:
            return self.context_sentence.replace(self.surface_lexical_unit, "<b>[...]</b>", 1)
        return ""

    def get_context_sentence_bold_word(self):
        """Get context sentence with word in bold"""
        if self.context_sentence and self.surface_lexical_unit:
            return self.context_sentence.replace(self.surface_lexical_unit, f"<b>{self.surface_lexical_unit}</b>", 1)
        return self.context_sentence or ""

    def get_cloze_enabled_output(self):
        """Get cloze enabled field formatted for output"""
        return "" if not self.cloze_enabled else str(self.cloze_enabled)

    def get_cloze_score_output(self):
        """Get cloze score field formatted for output"""
        return "" if self.cloze_deletion_score is None or self.cloze_deletion_score < 0 else str(self.cloze_deletion_score)

    def get_generation_metadata_output(self):
        """Get generation_metadata as JSON string for output"""
        return json.dumps(self.generation_metadata) if self.generation_metadata else ""

    def get_lookup_time(self):
        """Get timestamp formatted for display, using locale when available."""
        if not self.source_timestamp:
            return ""
        try:
            # Try locale-aware formatting
            return self.source_timestamp.strftime("%x %X")
        except Exception:
            # Fallback to ISO-ish format
            return self.source_timestamp.strftime("%Y-%m-%d %H:%M")

    def add_generation_metadata(self, task_id, runtime_id, model_id, prompt_id=None):
        """Add generation metadata for a task"""
        task_meta = {"runtime": runtime_id, "model": model_id}
        if prompt_id:
            task_meta["prompt"] = prompt_id
        self.generation_metadata[task_id] = task_meta

    def to_csv_line(self):
        """Convert the note to a tab-separated CSV line"""
        return (f"{self.uid}\t"
                f"{self.expression}\t"
                f"{self.definition}\t"
                f"{self.get_context_sentence_bold_word()}\t"
                f"{self.context_translation}\t"
                f"{self.part_of_speech}\t"
                f"{self.aspect}\t"
                f"{self.surface_lexical_unit}\t"
                f"{self.get_context_sentence_cloze()}\t"
                f"{self.collocations}\t"
                f"{self.original_language_hint}\t"
                f"{self.hint_test_enabled}\t"
                f"{self.notes}\t"
                f"{self.source_book}\t"
                f"{self.location}\t"
                f"{self.status}\t"
                f"{self.get_cloze_score_output()}\t"
                f"{self.get_cloze_enabled_output()}\t"
                f"{self.unit_type}\t"
                f"{self.get_generation_metadata_output()}\t"
                f"{self.usage_level}\t"
                f"{self.raw_context_text}\t"
                f"{self.raw_lookup_string}\t"
                f"{self.get_lookup_time()}\t"
                f"{self.tags}\n")

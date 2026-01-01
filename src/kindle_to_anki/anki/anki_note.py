import json
import unicodedata


class AnkiNote:
    def __init__(self, word, stem, usage, language, book_name, position, timestamp, uid=None):

        # Save off all original kindle fields that will not be modified
        self.kindle_word = word
        self.kindle_stem = stem
        self.kindle_usage = usage
        self.kindle_language = language
        self.kindle_book_name = book_name
        self.kindle_location = position
        self.kindle_timestamp = timestamp

        # Output fields
        self.uid = ""
        self.expression = self.kindle_stem or ""
        self.original_form = self.kindle_word or ""
        self.part_of_speech = ""
        self.definition = ""
        self.aspect = ""
        self.unit_type = "lemma"
        self.context_sentence = self.kindle_usage or ""
        self.context_sentence_cloze = ""
        self.context_translation = ""
        self.collocations = ""
        self.original_language_hint = ""
        self.notes = ""
        self.source_book = self.kindle_book_name or ""
        self.location = f"kindle_{position}" if position else ""
        self.status = "raw"
        self.cloze_deletion_score = -1
        self.cloze_enabled = None
        self.generation_metadata = {}
        self.usage_level = ""

        # Generate book abbreviation
        self.book_abbrev = self.generate_book_abbrev(self.kindle_book_name)

        # Generate UID (requires book abbreviation and location to be set first)
        self.uid = uid or self.generate_uid()

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
            self.cloze_enabled = score if score >= 7 else None

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

    def generate_uid(self):
        """Generate unique ID based on word, book_abbrev, and location"""
        # Normalize stem part similar to book_abbrev
        word_normalized = unicodedata.normalize('NFD', self.kindle_word or "unknown")
        stem_part = ''.join(char for char in word_normalized if unicodedata.category(char) != 'Mn')[:10]
        stem_part = stem_part.lower().replace(' ', '_')
        location_part = str(self.location).replace('kindle_', '') if self.location else "0"
        return f"{stem_part}_{self.book_abbrev}_{location_part}"

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

    def get_context_sentence_cloze(self):
        """Get context sentence with word replaced by [...]"""
        if self.context_sentence and self.original_form:
            return self.context_sentence.replace(self.original_form, "<b>[...]</b>", 1)
        return ""

    def get_context_sentence_bold_word(self):
        """Get context sentence with word in bold"""
        if self.context_sentence and self.original_form:
            return self.context_sentence.replace(self.original_form, f"<b>{self.original_form}</b>", 1)
        return self.context_sentence or ""

    def get_cloze_enabled_output(self):
        """Get cloze enabled field formatted for output"""
        return "" if not self.cloze_enabled else str(self.cloze_enabled)

    def get_generation_metadata_output(self):
        """Get generation_metadata as JSON string for output"""
        return json.dumps(self.generation_metadata) if self.generation_metadata else ""

    def add_generation_metadata(self, task_id, runtime_id, model_id):
        """Add generation metadata for a task"""
        self.generation_metadata[task_id] = {"runtime": runtime_id, "model": model_id}

    def to_csv_line(self):
        """Convert the note to a tab-separated CSV line"""
        return (f"{self.uid}\t"
                f"{self.expression}\t"
                f"{self.definition}\t"
                f"{self.get_context_sentence_bold_word()}\t"
                f"{self.context_translation}\t"
                f"{self.part_of_speech}\t"
                f"{self.aspect}\t"
                f"{self.original_form}\t"
                f"{self.get_context_sentence_cloze()}\t"
                f"{self.collocations}\t"
                f"{self.original_language_hint}\t"
                f"{self.notes}\t"
                f"{self.source_book}\t"
                f"{self.location}\t"
                f"{self.status}\t"
                f"{self.get_cloze_enabled_output()}\t"
                f"{self.unit_type}\t"
                f"{self.get_generation_metadata_output()}\t"
                f"{self.usage_level}\t"
                f"{self.tags}\n")

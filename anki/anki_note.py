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
        self.context_sentence = self.kindle_usage or ""
        self.context_sentence_cloze = ""
        self.context_translation = ""
        self.collocations = ""
        self.original_language_hint = ""
        self.notes = ""
        self.source_book = self.kindle_book_name or ""
        self.location = f"kindle_{position}" if position else ""
        self.status = "raw"
        self.cloze_enabled = None

        # Generate book abbreviation
        self.book_abbrev = self.generate_book_abbrev(self.kindle_book_name)

        # Generate UID (requires book abbreviation and location to be set first)
        self.uid = uid or self.generate_uid()

        # Format usage text for HTML
        self.format_context_sentence()

        # Set tags based on language and book abbreviation
        self.set_tags(language)

    def apply_llm_enrichment(self, llm_data):
        """Apply LLM enrichment data to the note (excluding translation and collocations which are handled separately)"""
        if not llm_data:
            return []

        if llm_data.get('definition'):
            self.definition = llm_data['definition']  # Override glosbe_url with LLM definition

        if llm_data.get('original_language_definition'):
            self.original_language_hint = llm_data['original_language_definition']

        if llm_data.get('cloze_deletion_score') is not None:
            score = llm_data['cloze_deletion_score']
            # Enable cloze if score is 7 or higher
            self.cloze_enabled = score if score >= 7 else None

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
                f"{self.tags}\n")

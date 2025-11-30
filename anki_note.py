import unicodedata
from urllib.parse import quote


class AnkiNote:
    def __init__(self, stem, word, part_of_speech="", 
                 definition="", secondary_definition="", 
                 usage="", context_translation="", 
                 notes="", book_name="", status="raw",
                 language=None, pos=None, collocations="", original_language_hint="",
                 cloze_enabled=False):
        self.word = word or ""
        self.definition = definition  # Main definition field for CSV output
        self.secondary_definition = secondary_definition
        self.usage = usage or ""
        self.context_translation = context_translation
        self.collocations = collocations
        self.original_language_hint = original_language_hint
        self.notes = notes
        self.book_name = book_name or ""
        self.status = status
        self.cloze_enabled = cloze_enabled
        self.glosbe_url = ""  # Will be generated later

        # Initialize stem and part_of_speech (may be updated by morfeusz enrichment)
        self.stem = stem or ""
        self.part_of_speech = part_of_speech

        # Generate book abbreviation
        self.book_abbrev = self.generate_book_abbrev(self.book_name)

        # Set location with kindle_ prefix
        self.location = f"kindle_{pos}" if pos else ""

        # Generate UID (needs location to be set first)
        self.uid = self.generate_uid()

        # Generate Glosbe URL
        self.generate_glosbe_url()

        # Format usage text for HTML
        self.format_usage()

        # Set tags based on language and book abbreviation
        self.set_tags(language)

    def apply_llm_enrichment(self, llm_data):
        """Apply LLM enrichment data to the note"""
        if not llm_data:
            return []

        enriched_fields = []
        if llm_data.get('definition'):
            self.definition = llm_data['definition']  # Override glosbe_url with LLM definition
            enriched_fields.append('definition')

        if llm_data.get('translation') and not self.context_translation:
            self.context_translation = llm_data['translation']
            enriched_fields.append('translation')

        if llm_data.get('secondary_definitions') and not self.notes:
            # Join multiple definitions into notes
            if isinstance(llm_data['secondary_definitions'], list):
                self.secondary_definition = ', '.join(llm_data['secondary_definitions'])
            else:
                self.notes = str(llm_data['secondary_definitions'])
            enriched_fields.append('secondary_definitions')

        if llm_data.get('collocations') and not self.collocations:
            if isinstance(llm_data['collocations'], list):
                self.collocations = ', '.join(llm_data['collocations'])
            else:
                self.collocations = str(llm_data['collocations'])
            enriched_fields.append('collocations')

        if llm_data.get('original_language_hint') and not self.original_language_hint:
            self.original_language_hint = llm_data['original_language_hint']
            enriched_fields.append('original_language_hint')

        return enriched_fields

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
        """Generate unique ID based on stem, book_abbrev, and location"""
        # Normalize stem part similar to book_abbrev
        stem_normalized = unicodedata.normalize('NFD', self.stem or "unknown")
        stem_part = ''.join(char for char in stem_normalized if unicodedata.category(char) != 'Mn')[:10]
        stem_part = stem_part.lower().replace(' ', '_')
        location_part = str(self.location).replace('kindle_', '') if self.location else "0"
        return f"{stem_part}_{self.book_abbrev}_{location_part}"

    def generate_glosbe_url(self, language="pl", target_language="en"):
        """Generate Glosbe URL for the stem word and set as backup definition"""
        if self.stem:
            encoded_word = quote(self.stem.strip().lower())
            self.glosbe_url = f"https://glosbe.com/{language}/{target_language}/{encoded_word}"

            # Set glosbe_url as backup definition if no definition exists
            if not self.definition:
                self.definition = self.glosbe_url

    def format_usage(self):
        """Format usage text for HTML display"""
        if self.usage:
            self.usage = self.usage.replace('\n', '<br>').replace('\r', '')

    def set_tags(self, language=None):
        """Set tags based on language and book abbreviation"""
        base_tags = ["kindle_to_anki"]

        if language:
            base_tags.append(language)

        if self.book_abbrev and self.book_abbrev != "unknown":
            base_tags.append(self.book_abbrev)

        self.tags = " ".join(base_tags)

    def to_csv_line(self):
        """Convert the note to a tab-separated CSV line"""
        # Create context_sentence_cloze by replacing the first occurrence of the word with [...] in usage
        context_cloze = ""
        if self.usage and self.word:
            context_cloze = self.usage.replace(self.word, "[...]", 1)  # Replace only first occurrence

        # Cloze_Enabled field - output blank if False, otherwise output the boolean value
        cloze_enabled_output = "" if not self.cloze_enabled else str(self.cloze_enabled)

        return f"{self.uid}\t{self.stem}\t{self.word}\t{self.part_of_speech}\t{self.definition}\t{self.secondary_definition}\t{self.usage}\t{context_cloze}\t{self.context_translation}\t{self.collocations}\t{self.original_language_hint}\t{self.notes}\t{self.book_name}\t{self.location}\t{self.status}\t{cloze_enabled_output}\t{self.tags}\n"

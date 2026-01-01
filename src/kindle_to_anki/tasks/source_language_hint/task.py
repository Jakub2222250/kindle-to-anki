from .schema import SourceLanguageHintInput, SourceLanguageHintOutput


class SourceLanguageHintTask:
    id = "source_language_hint"
    name = "Source Language Hint"
    description = "Provide source language definition hint for Anki cards"
    input_schema = SourceLanguageHintInput
    output_schema = SourceLanguageHintOutput

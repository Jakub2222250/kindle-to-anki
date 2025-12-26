from kindle_to_anki.tasks.translation.schema import TranslationInput, TranslationOutput


class TranslationTask:
    id = "translation"
    name = "Translation"
    description = "Translate source text into the target language for Anki cards"
    input_schema = TranslationInput
    output_schema = TranslationOutput

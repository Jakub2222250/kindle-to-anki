from kindle_to_anki.tasks.lui.schema import LUIInput, LUIOutput


class LUITask:
    id = "lui"
    name = "Lexical Unit Identification"
    description = "Identify lexical units (lemmas) and part of speech for vocabulary words"
    input_schema = LUIInput
    output_schema = LUIOutput
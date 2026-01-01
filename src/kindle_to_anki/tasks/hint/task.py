from .schema import HintInput, HintOutput


class HintTask:
    id = "hint"
    name = "Hint"
    description = "Provide source language definition hint for Anki cards"
    input_schema = HintInput
    output_schema = HintOutput

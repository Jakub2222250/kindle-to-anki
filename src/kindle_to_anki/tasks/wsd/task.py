from .schema import WSDInput, WSDOutput


class WSDTask:
    id = "wsd"
    name = "Word Sense Disambiguation"
    description = "Analyze word meanings in context and provide definitions for Anki cards"
    input_schema = WSDInput
    output_schema = WSDOutput
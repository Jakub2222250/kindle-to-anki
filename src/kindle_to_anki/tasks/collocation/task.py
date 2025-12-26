from .schema import CollocationInput, CollocationOutput


class CollocationTask:
    id = "collocation"
    name = "Collocation Generation"
    description = "Find common collocations and phrases for words in context"
    input_schema = CollocationInput
    output_schema = CollocationOutput
from .schema import ClozeScoringInput, ClozeScoringOutput


class ClozeScoringTask:
    id = "cloze_scoring"
    name = "Cloze Scoring"
    description = "Score sentence suitability for cloze deletion in Anki"
    input_schema = ClozeScoringInput
    output_schema = ClozeScoringOutput

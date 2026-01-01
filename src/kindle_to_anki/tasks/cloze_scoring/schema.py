from dataclasses import dataclass


@dataclass(frozen=True)
class ClozeScoringInput:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str


@dataclass(frozen=True)
class ClozeScoringOutput:
    cloze_deletion_score: int

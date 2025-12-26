from dataclasses import dataclass
from time import clock_getres


@dataclass(frozen=True)
class WSDInput:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str

@dataclass(frozen=True)
class WSDOutput:
    definition: str
    original_language_definition: str
    cloze_deletion_score: int

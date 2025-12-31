from dataclasses import dataclass


@dataclass(frozen=True)
class WSDInput:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str

from typing import Optional

@dataclass(frozen=True)
class WSDOutput:
    definition: str
    original_language_definition: str
    cloze_deletion_score: int
    usage_level: Optional[int] = None

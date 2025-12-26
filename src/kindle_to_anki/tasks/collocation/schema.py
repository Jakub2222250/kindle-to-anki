from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class CollocationInput:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str

@dataclass(frozen=True)
class CollocationOutput:
    collocations: List[str]

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class CollocationInput:
    uid: str
    lemma: str
    pos: str


@dataclass(frozen=True)
class CollocationOutput:
    collocations: List[str]

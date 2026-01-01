from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UsageLevelInput:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str
    definition: str


@dataclass(frozen=True)
class UsageLevelOutput:
    usage_level: Optional[int]

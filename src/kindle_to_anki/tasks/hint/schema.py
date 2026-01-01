from dataclasses import dataclass


@dataclass(frozen=True)
class HintInput:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str


@dataclass(frozen=True)
class HintOutput:
    hint: str

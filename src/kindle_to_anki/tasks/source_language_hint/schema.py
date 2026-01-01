from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLanguageHintInput:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str


@dataclass(frozen=True)
class SourceLanguageHintOutput:
    source_language_hint: str

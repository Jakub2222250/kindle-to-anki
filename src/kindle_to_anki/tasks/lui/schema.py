from dataclasses import dataclass


@dataclass(frozen=True)
class LUIInput:
    uid: str
    word: str
    sentence: str

@dataclass(frozen=True)
class LUIOutput:
    lemma: str
    part_of_speech: str
    aspect: str
    original_form: str
    unit_type: str
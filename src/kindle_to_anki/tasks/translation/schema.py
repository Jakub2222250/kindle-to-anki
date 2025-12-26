from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationInput:
    uid: str
    context: str

@dataclass(frozen=True)
class TranslationOutput:
    translation: str

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CandidateOutput:
    # Represents collected candidate entry
    word: str
    stem: str
    usage: str
    language: str
    book_title: Optional[str]
    position: Optional[str]
    timestamp: int

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass(frozen=True)
class CandidateInput:
    # Represents request for candidate data collection
    db_path: str
    last_timestamp: Optional[datetime] = None
    incremental: bool = True

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
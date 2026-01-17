from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class CandidateOutput:
    """
    Represents a collected candidate entry from a vocabulary source.

    Required fields:
        - word: The looked-up word form
        - usage: Context sentence
        - language: Source language code

    Optional fields (availability depends on vocabulary source):
        - uid: Unique identifier (if not provided, AnkiNote will generate one)
        - stem: Base/dictionary form
        - book_title: Source book/document name
        - position: Location within the source
        - timestamp: When the lookup occurred
    """
    word: str
    usage: str
    language: str
    uid: Optional[str] = None
    stem: Optional[str] = None
    book_title: Optional[str] = None
    position: Optional[str] = None
    timestamp: Optional[datetime] = None

from dataclasses import dataclass


@dataclass
class UsageScope:
    unit: str                   # "notes", "books", "documents"
    count: int
    note_uids: list[str] | None = None



from dataclasses import dataclass


@dataclass
class UsageEstimate:
    unit: str                    # "tokens", "characters", "requests", "seconds"
    quantity: int | float
    confidence: str             # "low", "medium", "high"
    notes: str | None = None

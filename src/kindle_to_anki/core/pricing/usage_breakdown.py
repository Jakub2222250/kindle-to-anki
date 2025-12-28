from dataclasses import dataclass

from .usage_scope import UsageScope

from .usage_dimension import UsageDimension


@dataclass
class UsageBreakdown:
    scope: UsageScope
    inputs: dict[str, UsageDimension]
    outputs: dict[str, UsageDimension]
    confidence: str | None = None             # "low", "medium", "high"
    notes: str | None = None

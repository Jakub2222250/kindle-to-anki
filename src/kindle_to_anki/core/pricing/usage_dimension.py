from dataclasses import dataclass


@dataclass
class UsageDimension:
    unit: str              # "tokens", "characters", "seconds", "requests"
    quantity: int | float

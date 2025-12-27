from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeConfig:
    model_id: str | None = None
    batch_size: int | None = None

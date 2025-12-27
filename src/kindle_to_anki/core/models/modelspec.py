from dataclasses import dataclass
from typing import Optional, Literal

ModelFamily = Literal["chat_completion", "embedding", "translation"]

@dataclass(frozen=True)
class ModelSpec:
    id: str                     # e.g. "gpt-5-mini"
    platform: str               # e.g. "openai"
    family: ModelFamily         # how it is invoked
    quality_tier: Literal["low", "medium", "high"]

    # Cost (USD per 1M tokens)
    input_token_cost_per_1m: Optional[float] = None
    output_token_cost_per_1m: Optional[float] = None

    # Operational characteristics
    typical_latency_ms: Optional[int] = None
    notes: Optional[str] = None
    supports_json: Optional[bool] = None

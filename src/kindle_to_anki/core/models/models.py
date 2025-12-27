from .modelspec import ModelSpec


GPT_5_MINI = ModelSpec(
    id="gpt-5-mini",
    platform="openai",
    family="chat_completion",
    quality_tier="medium",
    context_tokens=128_000,
    supports_json=True,
    input_cost=0.25,
    output_cost=2.00,
    typical_latency_ms=600,
)

GPT_5_1 = ModelSpec(
    id="gpt-5.1",
    platform="openai",
    family="chat_completion",
    quality_tier="high",
    context_tokens=256_000,
    supports_json=True,
    input_cost=1.25,
    output_cost=10.00,
    typical_latency_ms=900,
)

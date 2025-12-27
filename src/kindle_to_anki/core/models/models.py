from .modelspec import ModelSpec


GPT_5_MINI = ModelSpec(
    id="gpt-5-mini",
    platform_id="openai",
    family="chat_completion",
    quality_tier="medium",
    supports_json=True,
    input_token_cost_per_1m=0.25,
    output_token_cost_per_1m=2.00,
    typical_latency_ms=600,
)

GPT_5_1 = ModelSpec(
    id="gpt-5.1",
    platform_id="openai",
    family="chat_completion",
    quality_tier="high",
    supports_json=True,
    input_token_cost_per_1m=1.25,
    output_token_cost_per_1m=10.00,
    typical_latency_ms=900,
)

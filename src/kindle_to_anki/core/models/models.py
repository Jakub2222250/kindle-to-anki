from .modelspec import ModelSpec


GPT_5_MINI = ModelSpec(
    id="gpt-5-mini",
    platform_id="openai",
    family="chat_completion",
    quality_tier="medium",
    encoding="o200k_base",
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
    encoding="o200k_base",
    supports_json=True,
    input_token_cost_per_1m=1.25,
    output_token_cost_per_1m=10.00,
    typical_latency_ms=900,
)

GROK_4 = ModelSpec(
    id="grok-4",
    platform_id="grok",
    family="chat_completion",
    quality_tier="high",
    encoding="cl100k_base",
    supports_json=True,
    input_token_cost_per_1m=3.00,
    output_token_cost_per_1m=15.00,
    typical_latency_ms=800,
)

GROK_3_MINI = ModelSpec(
    id="grok-3-mini",
    platform_id="grok",
    family="chat_completion",
    quality_tier="medium",
    encoding="cl100k_base",
    supports_json=True,
    input_token_cost_per_1m=0.30,
    output_token_cost_per_1m=0.50,
    typical_latency_ms=500,
)

GEMINI_3_FLASH = ModelSpec(
    id="gemini-3-flash-preview",
    platform_id="gemini",
    family="chat_completion",
    quality_tier="medium",
    encoding="cl100k_base",
    supports_json=True,
    input_token_cost_per_1m=0.00,  # Free tier
    output_token_cost_per_1m=0.00,  # Free tier
    typical_latency_ms=700,
    rpm_limit=10,  # Free tier limits are dynamic, check AI Studio
    tpm_limit=250_000,
    rpd_limit=1500,
)

GEMINI_3_PRO = ModelSpec(
    id="gemini-3-pro-preview",
    platform_id="gemini",
    family="chat_completion",
    quality_tier="high",
    encoding="cl100k_base",
    supports_json=True,
    input_token_cost_per_1m=2.00,  # No free tier
    output_token_cost_per_1m=12.00,
    typical_latency_ms=1000,
)

GEMINI_2_5_FLASH = ModelSpec(
    id="gemini-2.5-flash",
    platform_id="gemini",
    family="chat_completion",
    quality_tier="medium",
    encoding="cl100k_base",
    supports_json=True,
    input_token_cost_per_1m=0.00,  # Free tier (paid: $0.15)
    output_token_cost_per_1m=0.00,  # Free tier (paid: $0.60)
    typical_latency_ms=500,
    rpm_limit=10,  # Free tier limits are dynamic, check AI Studio
    tpm_limit=250_000,
    rpd_limit=1500,
)

GEMINI_2_0_FLASH = ModelSpec(
    id="gemini-2.0-flash",
    platform_id="gemini",
    family="chat_completion",
    quality_tier="medium",
    encoding="cl100k_base",
    supports_json=True,
    input_token_cost_per_1m=0.00,  # Free tier (paid: $0.10)
    output_token_cost_per_1m=0.00,  # Free tier (paid: $0.40)
    typical_latency_ms=400,
    rpm_limit=10,  # Free tier limits are dynamic, check AI Studio
    tpm_limit=250_000,
    rpd_limit=1500,
)

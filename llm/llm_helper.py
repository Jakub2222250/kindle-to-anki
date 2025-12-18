try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

# Model-specific token-to-character ratios (fallback when tiktoken unavailable)
TOKEN_CHAR_RATIOS = {
    "gpt-4": 3.5,  # More accurate than 4 for most content
    "gpt-5": 3.5,
    "gpt-4.1": 3.5,
    "gpt-5-mini": 3.5,
    "gpt-3.5-turbo": 3.8,
}

# Consolidated pricing data
MODEL_PRICING = {
    "gpt-5": {"input_cost_per_1m_tokens": 1.25, "output_cost_per_1m_tokens": 10.00, "encoding": "o200k_base"},
    "gpt-4.1": {"input_cost_per_1m_tokens": 2.00, "output_cost_per_1m_tokens": 8.00, "encoding": "o200k_base"},
    "gpt-5-mini": {"input_cost_per_1m_tokens": 0.25, "output_cost_per_1m_tokens": 2.00, "encoding": "o200k_base"},
    "gpt-4": {"input_cost_per_1m_tokens": 30.00, "output_cost_per_1m_tokens": 60.00, "encoding": "cl100k_base"},
    "gpt-3.5-turbo": {"input_cost_per_1m_tokens": 1.50, "output_cost_per_1m_tokens": 2.00, "encoding": "cl100k_base"},
}


def count_tokens(text, model):
    """Count exact tokens using tiktoken when available, fallback to estimation"""
    if not text:
        return 0

    if TIKTOKEN_AVAILABLE and model in MODEL_PRICING:
        try:
            encoding_name = MODEL_PRICING[model]["encoding"]
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
        except Exception:
            # Fallback to ratio estimation if tiktoken fails
            pass

    # Fallback: use model-specific character-to-token ratio
    ratio = TOKEN_CHAR_RATIOS.get(model, 4.0)  # Default to 4 if model unknown
    return int(len(text) / ratio)


def estimate_llm_cost(input_text, notes_count, model):
    """Estimate cost for lexical unit identification API calls with improved accuracy"""
    if model not in MODEL_PRICING:
        return None

    # Use actual token counting for input
    if isinstance(input_text, str):
        input_tokens = count_tokens(input_text, model)
    else:
        # Fallback for when input_chars (int) is passed for backward compatibility
        input_tokens = input_text / TOKEN_CHAR_RATIOS.get(model, 4.0)

    # Improved output estimation based on model and task type
    # Different models tend to produce different output lengths
    ESTIMATED_TOKENS_PER_IDENTIFICATION = {
        "gpt-5": 45,      # More concise outputs
        "gpt-4.1": 50,    # Moderately verbose
        "gpt-5-mini": 40,  # Usually more concise
        "gpt-4": 55,      # Can be more verbose
        "gpt-3.5-turbo": 45,
    }

    tokens_per_id = ESTIMATED_TOKENS_PER_IDENTIFICATION.get(model, 50)
    output_tokens = tokens_per_id * notes_count

    pricing = MODEL_PRICING[model]
    input_cost = (input_tokens / 1_000_000) * pricing["input_cost_per_1m_tokens"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_cost_per_1m_tokens"]

    return input_cost + output_cost


def calculate_llm_cost(input_text, output_text, model):
    """Calculate exact cost for LLM API calls using precise token counting"""
    if model not in MODEL_PRICING:
        return None

    # Handle both text and character count inputs for backward compatibility
    if isinstance(input_text, str):
        input_tokens = count_tokens(input_text, model)
    else:
        # Backward compatibility: assume it's character count
        input_tokens = input_text / TOKEN_CHAR_RATIOS.get(model, 4.0)

    if isinstance(output_text, str):
        output_tokens = count_tokens(output_text, model)
    else:
        # Backward compatibility: assume it's character count
        output_tokens = output_text / TOKEN_CHAR_RATIOS.get(model, 4.0)

    pricing = MODEL_PRICING[model]
    input_cost = (input_tokens / 1_000_000) * pricing["input_cost_per_1m_tokens"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_cost_per_1m_tokens"]

    return input_cost + output_cost


def get_supported_models():
    """Return list of supported models for cost calculation"""
    return list(MODEL_PRICING.keys())


def get_model_info(model):
    """Get pricing and encoding info for a specific model"""
    return MODEL_PRICING.get(model, None)

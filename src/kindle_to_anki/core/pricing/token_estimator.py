from models.modelspec import ModelSpec
import tiktoken


try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False



def count_tokens(text: str, model: ModelSpec):
    """Count exact tokens using tiktoken when available, fallback to estimation"""
    if not text:
        return 0

    try:
        encoding_name = model.encoding
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to ratio estimation if tiktoken fails
        pass

    # Fallback: use model-specific character-to-token ratio
    ratio = 4.0
    return int(len(text) / ratio)

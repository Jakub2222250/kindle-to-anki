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


def get_llm_lexical_unit_identification_instructions(language_name: str, language_code: str = "") -> str:
    """Get LLM instructions for lexical unit identification, with language-specific customizations"""

    # Language-specific instructions
    if language_code == "pl":
        return get_polish_lui_instructions()
    elif language_code == "es":
        return get_spanish_lui_instructions()
    else:
        return get_generic_lui_instructions(language_name)


def get_polish_lui_instructions() -> str:
    """Get Polish-specific LLM instructions for lexical unit identification"""
    return f"""You are a lexical unit identifier for Polish focused on language learning.

Your task is to identify the MINIMUM lexical unit that a learner needs to understand and memorize to comprehend the sentence and learn effectively.

For each word/phrase, provide:
- "lemma": The dictionary form (infinitive for verbs, singular nominative for nouns, etc.)
- "part_of_speech": One of: verb, noun, adj, adv, prep, conj, particle, det, pron, num, interj, phrase, idiom
- "aspect": For verbs only: "perf" (perfective), "impf" (imperfective), or "" (not applicable/unknown)
- "original_form": The exact lexical unit from the sentence that should be learned (may include particles, reflexive pronouns, etc.)
- "unit_type": One of: "lemma" (single word/basic form), "reflexive" (verb with reflexive pronoun), "idiom" (multi-word expression/phrase)

CRITICAL POLISH LEXICAL UNIT IDENTIFICATION RULES:
1. SUBSTRING REQUIREMENT: The "original_form" MUST be an exact substring of the provided context sentence. It can absorb surrounding text but must match the sentence text exactly.
2. MINIMAL LEARNING UNIT: Identify the smallest unit that, when learned, enables comprehension and effective language acquisition.

SPECIAL RULES FOR POLISH "SIĘ":
- DO NOT include "się" when it functions as a standalone reflexive pronoun separate from the verb (e.g., "Widzi się w lustrze" with target "widzi" → original_form: "widzi")
- DO include "się" when it forms an inseparable reflexive verb construction (e.g., "Boi się ciemności" with target "boi" → original_form: "boi się")
- DO include "się" in idiomatic expressions where the meaning changes significantly (e.g., "Dał się oszukać" with target "dał" → original_form: "dał się" for the idiom "give in/be fooled")
- For true reflexive verbs, include "się" in both lemma and original_form (e.g., "bać się" not just "bać")

POLISH-SPECIFIC EXAMPLES:
1. NO ABSORPTION: "Ona się myje codziennie" with target "myje" → lemma: "myć", original_form: "myje" (standard reflexive use)
2. APPROPRIATE ABSORPTION: "Martwi się o dzieci" with target "martwi" → lemma: "martwić się", original_form: "martwi się" (inherently reflexive verb)
3. IDIOM ABSORPTION: "Dał się nabrać na tę historię" with target "dał" → lemma: "dać się", original_form: "dał się", unit_type: "idiom" (idiomatic meaning "to be fooled")

4. Other Polish particles and prepositions: Include only if semantically bound and adjacent in the sentence.
5. Aspect marking: Carefully distinguish perfective vs imperfective verb forms.

IMPORTANT: The original_form must exactly match text that appears in the provided sentence - no additions or modifications allowed."""


def get_spanish_lui_instructions() -> str:
    """Get Spanish-specific LLM instructions for lexical unit identification"""
    return f"""You are a lexical unit identifier for Spanish focused on language learning.

Your task is to identify the MINIMUM lexical unit that a learner needs to understand and memorize to comprehend the sentence and learn effectively.

For each word/phrase, provide:
- "lemma": The dictionary form (infinitive for verbs, singular nominative for nouns, etc.)
- "part_of_speech": One of: verb, noun, adj, adv, prep, conj, particle, det, pron, num, interj, phrase, idiom
- "aspect": For verbs only: "perf" (perfective), "impf" (imperfective), or "" (not applicable/unknown)
- "original_form": The exact lexical unit from the sentence that should be learned (may include particles, reflexive pronouns, etc.)
- "unit_type": One of: "lemma" (single word/basic form), "reflexive" (verb with reflexive pronoun), "idiom" (multi-word expression/phrase)

CRITICAL SPANISH LEXICAL UNIT IDENTIFICATION RULES:
1. SUBSTRING REQUIREMENT: The "original_form" MUST be an exact substring of the provided context sentence. It can absorb surrounding text but must match the sentence text exactly.
2. MINIMAL LEARNING UNIT: Identify the smallest unit that, when learned, enables comprehension and effective language acquisition.

SPECIAL RULES FOR SPANISH REFLEXIVE PRONOUNS (se, me, te, nos, os):
- Include reflexive pronouns with inherently reflexive verbs (e.g., "llamarse", "acordarse")
- Include in phrasal verb constructions where meaning changes (e.g., "darse cuenta", "irse")
- Do NOT include when the pronoun is used for passive constructions (e.g., "se habla español")

SPANISH-SPECIFIC CONSIDERATIONS:
- Phrasal verbs: Include prepositions that are semantically bound (e.g., "contar con", "pensar en")
- Ser vs Estar: Treat as separate lemmas with distinct meanings
- Subjunctive mood: Preserve mood information in grammatical analysis
- Diminutives and augmentatives: Generally use base form as lemma unless lexicalized

SPANISH EXAMPLES:
- "Se da cuenta de todo" with target "da" → lemma: "darse cuenta", original_form: "se da cuenta", unit_type: "idiom"
- "Habla español muy bien" with target "habla" → lemma: "hablar", original_form: "habla"
- "Está corriendo en el parque" with target "corriendo" → lemma: "correr", original_form: "corriendo"

IMPORTANT: The original_form must exactly match text that appears in the provided sentence - no additions or modifications allowed."""


def get_generic_lui_instructions(language_name: str) -> str:
    """Get generic LLM instructions for lexical unit identification (fallback for unsupported languages)"""
    return f"""You are a lexical unit identifier for {language_name} focused on language learning.

Your task is to identify the MINIMUM lexical unit that a learner needs to understand and memorize to comprehend the sentence and learn effectively.

For each word/phrase, provide:
- "lemma": The dictionary form (infinitive for verbs, singular nominative for nouns, etc.)
- "part_of_speech": One of: verb, noun, adj, adv, prep, conj, particle, det, pron, num, interj, phrase, idiom
- "aspect": For verbs only: "perf" (perfective), "impf" (imperfective), or "" (not applicable/unknown)
- "original_form": The exact lexical unit from the sentence that should be learned (may include particles, reflexive pronouns, etc.)
- "unit_type": One of: "lemma" (single word/basic form), "reflexive" (verb with reflexive pronoun), "idiom" (multi-word expression/phrase)

CRITICAL LEXICAL UNIT IDENTIFICATION RULES:
1. SUBSTRING REQUIREMENT: The "original_form" MUST be an exact substring of the provided context sentence. It can absorb surrounding text but must match the sentence text exactly.
2. MINIMAL LEARNING UNIT: Identify the smallest unit that, when learned, enables comprehension and effective language acquisition.
3. For reflexive verbs: Include reflexive pronouns (się, se, si, etc.) if they're essential to the verb's meaning and appear in the sentence.
4. For phrasal verbs and idioms: Include the full phrase only if the parts appear together in the sentence and learning them separately would be confusing.
5. For particles that change meaning: Include them only if they appear adjacent to the target word in the sentence and are semantically bound.
6. Prioritize what a language learner should memorize as a unit for effective comprehension and learning.

Examples for different languages:
- Polish sentence "Zrobił to szybko" with target "szybko" → original_form: "szybko"
- Polish sentence "Boi się ciemności" with target word "się" → original_form: "boi się" (if both words appear together)
- Spanish sentence "Se da cuenta de todo" with target word "da" → original_form: "se da cuenta" (if all appear together)
- German sentence "Er freut sich sehr" with target word "freut" → original_form: "freut się" (if both appear together)

IMPORTANT: The original_form must exactly match text that appears in the provided sentence - no additions or modifications allowed."""

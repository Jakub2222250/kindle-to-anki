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


def get_llm_lexical_unit_identification_instructions(items_json: str, language_name: str, language_code: str = "") -> str:
    """Get LLM instructions for lexical unit identification, with language-specific customizations"""

    # Language-specific instructions
    if language_code == "pl":
        return get_polish_lui_instructions(items_json)
    elif language_code == "es":
        return get_spanish_lui_instructions(items_json)
    else:
        return get_generic_lui_instructions(items_json, language_name)


def get_polish_lui_instructions(items_json: str) -> str:
    """Return the Polish lexical unit identifier instructions, ready for LLM consumption."""
    return f"""You are a lexical unit identifier for Polish, optimized for spaced-repetition learning.

TASK
Identify the SMALLEST lexical unit a learner must memorize to understand the sentence in context.
Do not over-absorb words unless meaning is lost without them.

Words to identify:
{items_json}

OUTPUT
Return a JSON object keyed by UID. Each value must contain:

- "lemma": dictionary form (verbs: infinitive; nouns: singular nominative)
- "part_of_speech": one of [verb, noun, adj, adv, prep, conj, particle, det, pron, num, interj, phrase]
- "aspect": verbs only: "perf", "impf", or ""
- "original_form": exact substring from the sentence (character-perfect match)
- "unit_type": one of ["lemma", "reflexive", "idiom"]

NO additional text. Valid JSON only.

HARD CONSTRAINTS
1. SUBSTRING RULE  
   "original_form" MUST appear verbatim in the sentence. No normalization, no expansion.

2. MINIMALITY RULE  
   Prefer the smallest unit that preserves meaning. Absorb additional tokens ONLY if meaning changes without them.

3. LEARNING PRIORITY  
   Optimize for efficient Anki cards: fewer units, higher semantic yield.

---

SIĘ HANDLING (POLISH-SPECIFIC)

Include "się" ONLY when it is lexically required.

INCLUDE "się" when:
- The verb is inherently reflexive and listed with "się" in dictionaries  
  (e.g., "bać się", "martwić się")
- The construction is idiomatic or non-compositional  
  (e.g., "dać się nabrać" → learn "dał się")

EXCLUDE "się" when:
- It is a syntactic reflexive with transparent meaning  
  (e.g., "Ona się myje" → learn "myje")
- It functions impersonally or passively without changing verb meaning

If excluded, do NOT include "się" in lemma or original_form.

---

UNIT_TYPE DEFINITIONS (NON-OVERLAPPING)

- "lemma"  
  Single-word lexical item; meaning preserved without additional tokens.

- "reflexive"  
  Lexicalized verb that requires "się" to retain its core meaning  
  (lemma includes "się").

- "idiom"  
  Multi-word expression whose meaning is non-compositional or significantly shifted.
  Absorb ONLY the minimal span that carries the idiomatic meaning.

Do NOT label compositional fixed phrases as idioms.

---

ASPECT RULES

- Use the verb's inherent lexical aspect, not contextual nuance.
- Biaspectual or unclear → "" (empty string).
- Do not guess.

---

ABSORPTION OF OTHER WORDS

- Prepositions/particles may be absorbed ONLY if:
  a) meaning is incomplete without them, AND
  b) they are adjacent in the sentence.

Never absorb arguments (objects, complements) unless idiomatic.

---

EXAMPLES (AUTHORITATIVE)

"Ona się myje codziennie"  
→ lemma: "myć", original_form: "myje", unit_type: "lemma"

"Martwi się o dzieci"  
→ lemma: "martwić się", original_form: "Martwi się", unit_type: "reflexive"

"Dał się nabrać na tę historię"  
→ lemma: "dać się", original_form: "Dał się", unit_type: "idiom"
"""


def get_spanish_lui_instructions(items_json: str) -> str:
    """Return the Spanish lexical unit identifier instructions, ready for LLM consumption."""
    return f"""You are a lexical unit identifier for Spanish, optimized for spaced-repetition learning.

TASK
Identify the SMALLEST lexical unit a learner must memorize to understand the sentence in context.
Do not over-absorb words unless meaning is lost without them.

Words to identify:
{items_json}

OUTPUT
Return a JSON object keyed by UID. Each value must contain:

- "lemma": dictionary form (verbs: infinitive; nouns: singular masculine)
- "part_of_speech": one of [verb, noun, adj, adv, prep, conj, particle, det, pron, num, interj, phrase]
- "aspect": verbs only: "perf", "impf", or ""
- "original_form": exact substring from the sentence (character-perfect match)
- "unit_type": one of ["lemma", "reflexive", "idiom"]

NO additional text. Valid JSON only.

HARD CONSTRAINTS
1. SUBSTRING RULE  
   "original_form" MUST appear verbatim in the sentence. No normalization, no expansion.

2. MINIMALITY RULE  
   Prefer the smallest unit that preserves meaning. Absorb additional tokens ONLY if meaning changes without them.

3. LEARNING PRIORITY  
   Optimize for efficient Anki cards: fewer units, higher semantic yield.

---

REFLEXIVE PRONOUNS HANDLING (SPANISH-SPECIFIC)

Include reflexive pronouns (se, me, te, nos, os) ONLY when lexically required.

INCLUDE reflexive pronouns when:
- The verb is inherently reflexive and listed with pronoun in dictionaries  
  (e.g., "acordarse", "llamarse", "quejarse")
- The construction is idiomatic or changes core meaning  
  (e.g., "darse cuenta", "irse", "ponerse" + adjective)
- Pronominal verbs with distinct meanings from non-reflexive forms  
  (e.g., "ir" vs "irse", "poner" vs "ponerse")

EXCLUDE reflexive pronouns when:
- Used for passive/impersonal constructions  
  (e.g., "Se habla español" → learn "habla")
- Reciprocal actions with transparent meaning  
  (e.g., "Se aman" → learn "aman")
- Optional reflexive with same core meaning  
  (e.g., "(Se) comió la manzana" → learn "comió")

If excluded, do NOT include pronoun in lemma or original_form.

---

UNIT_TYPE DEFINITIONS (NON-OVERLAPPING)

- "lemma"  
  Single-word lexical item; meaning preserved without additional tokens.

- "reflexive"  
  Inherently reflexive verb that requires pronoun to retain core meaning  
  (lemma includes reflexive pronoun).

- "idiom"  
  Multi-word expression whose meaning is non-compositional or significantly shifted.  
  Absorb ONLY the minimal span that carries the idiomatic meaning.

Do NOT label transparent phrasal constructions as idioms.

---

SPANISH-SPECIFIC CONSIDERATIONS

- SER vs ESTAR: Treat as distinct lemmas with different meanings
- PHRASAL VERBS: Include semantically bound prepositions ("contar con", "pensar en")
- SUBJUNCTIVE: Use infinitive as lemma regardless of mood
- DIMINUTIVES: Use base form unless lexicalized ("abuelita" → "abuela")
- GENDER AGREEMENT: Use masculine singular for adjectives when possible

---

ABSORPTION RULES

- Prepositions/particles may be absorbed ONLY if:
  a) meaning is incomplete without them, AND
  b) they are adjacent in the sentence.

Never absorb arguments (direct objects, complements) unless idiomatic.

---

EXAMPLES (AUTHORITATIVE)

"Se da cuenta de la situación"  
→ lemma: "darse cuenta", original_form: "Se da cuenta", unit_type: "idiom"

"Habla español perfectamente"  
→ lemma: "hablar", original_form: "Habla", unit_type: "lemma"

"Se llama María"  
→ lemma: "llamarse", original_form: "Se llama", unit_type: "reflexive"

"Se venden libros aquí"  
→ lemma: "vender", original_form: "venden", unit_type: "lemma"""


def get_generic_lui_instructions(items_json: str, language_name: str) -> str:
    """Return generic lexical unit identifier instructions for any language, ready for LLM consumption."""
    return f"""You are a lexical unit identifier for {language_name}, optimized for spaced-repetition learning.

TASK
Identify the SMALLEST lexical unit a learner must memorize to understand the sentence in context.
Do not over-absorb words unless meaning is lost without them.

Words to identify:
{items_json}

OUTPUT
Return a JSON object keyed by UID. Each value must contain:

- "lemma": dictionary form (verbs: infinitive; nouns: singular nominative/base form)
- "part_of_speech": one of [verb, noun, adj, adv, prep, conj, particle, det, pron, num, interj, phrase]
- "aspect": verbs only: "perf", "impf", or "" (if not applicable)
- "original_form": exact substring from the sentence (character-perfect match)
- "unit_type": one of ["lemma", "reflexive", "idiom"]

NO additional text. Valid JSON only.

HARD CONSTRAINTS
1. SUBSTRING RULE  
   "original_form" MUST appear verbatim in the sentence. No normalization, no expansion.

2. MINIMALITY RULE  
   Prefer the smallest unit that preserves meaning. Absorb additional tokens ONLY if meaning changes without them.

3. LEARNING PRIORITY  
   Optimize for efficient Anki cards: fewer units, higher semantic yield.

---

REFLEXIVE/PARTICLE HANDLING (LANGUAGE-ADAPTIVE)

Include particles, reflexive pronouns, or clitics ONLY when lexically required.

INCLUDE when:
- The construction is inherently bound and listed together in dictionaries
- The particle/pronoun changes the core meaning significantly
- The construction is idiomatic or non-compositional
- Separation would create confusion for learners

EXCLUDE when:
- The particle/pronoun has transparent grammatical function
- The construction is purely syntactic or stylistic
- The base verb meaning remains essentially the same

If excluded, do NOT include particle/pronoun in lemma or original_form.

---

UNIT_TYPE DEFINITIONS (NON-OVERLAPPING)

- "lemma"  
  Single-word lexical item; meaning preserved without additional tokens.

- "reflexive"  
  Verb construction that requires a reflexive pronoun/particle to retain core meaning  
  (lemma includes the bound element).

- "idiom"  
  Multi-word expression whose meaning is non-compositional or significantly shifted.  
  Absorb ONLY the minimal span that carries the idiomatic meaning.

Do NOT label transparent multi-word constructions as idioms.

---

UNIVERSAL CONSIDERATIONS

- PHRASAL VERBS: Include particles/prepositions only if semantically bound
- COMPOUND FORMS: Prefer base forms unless compound is lexicalized
- INFLECTION: Use citation form (infinitive, nominative, etc.) as lemma
- DERIVATION: Consider whether derived form has distinct meaning
- CASE/AGREEMENT: Normalize to base form unless meaning-bearing

---

ABSORPTION RULES

- Particles/prepositions may be absorbed ONLY if:
  a) meaning is incomplete without them, AND
  b) they are adjacent in the sentence.

Never absorb arguments (objects, complements) unless truly idiomatic.

---

GUIDELINES FOR COMMON LANGUAGE FEATURES

- Auxiliary verbs: Usually exclude from content verb lemmas
- Articles: Generally exclude unless part of fixed expression
- Copulas: Treat as separate lemmas from predicates  
- Modal verbs: Separate from main verbs unless fused
- Negation: Include only if lexicalized with the verb
- Clitics: Include only if meaning-changing or obligatory

Prioritize what creates the most effective learning unit for spaced repetition."""

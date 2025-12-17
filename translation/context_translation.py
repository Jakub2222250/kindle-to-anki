from translation.polish_translator_local import translate_polish_context_to_english
from translation.polish_translator_llm import translate_polish_context_to_english_llm
from translation.translation_cache import TranslationCache


def process_context_translation(notes, language, cache_suffix='default', ignore_cache=False, use_llm=False):
    """Process context translation for a list of notes

    Args:
        notes: List of AnkiNote objects to translate
        language: Language code (e.g., 'pl', 'es') 
        cache_suffix: Cache file suffix for translation cache
        ignore_cache: Whether to ignore existing cache
        use_llm: Whether to use LLM translator instead of local model (for Polish only)
    """

    print("\nStarting context translation...")

    cache = TranslationCache(cache_suffix=cache_suffix)

    if not ignore_cache:
        print(f"Loaded translation cache with {len(cache.cache)} entries")
    else:
        print("Ignoring cache as per user request. Fresh translations will be generated.")

    if language == "pl":
        if use_llm:
            translate_polish_context_to_english_llm(notes, cache)
        else:
            translate_polish_context_to_english(notes, cache)
    elif language == "es":
        print("Context translation for Spanish is not supported yet")
        exit()
    else:
        print("Context translation for this language is not supported yet")
        exit()

    print("Context translation completed.")

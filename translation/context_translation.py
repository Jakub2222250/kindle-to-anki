from translation.polish_translator_local import translate_polish_context_to_english
from translation.translator_llm import translate_context_with_llm
from translation.translation_cache import TranslationCache


def process_context_translation(notes, source_lang_code: str, target_lang_code: str, ignore_cache=False, use_llm=False):
    """Process context translation for a list of notes

    Args:
        notes: List of AnkiNote objects to translate
        language: Language code (e.g., 'pl', 'es') 
        cache_suffix: Cache file suffix for translation cache
        ignore_cache: Whether to ignore existing cache
        use_llm: Whether to use LLM translator instead of local model (for Polish only)
    """

    print("\nStarting context translation...")

    language_pair_code = f"{source_lang_code}-{target_lang_code}"

    cache = TranslationCache(cache_suffix=language_pair_code)
    if not ignore_cache:
        print(f"Loaded translation cache with {len(cache.cache)} entries")
    else:
        print("Ignoring cache as per user request. Fresh translations will be generated.")

    if source_lang_code == "pl":
        if not use_llm and target_lang_code == "en":
            translate_polish_context_to_english(notes, ignore_cache=ignore_cache)
        else:
            translate_context_with_llm(notes, source_lang_code, target_lang_code, ignore_cache=ignore_cache)
    else:
        translate_context_with_llm(notes, source_lang_code, target_lang_code, ignore_cache=ignore_cache)

    print("Context translation completed.")

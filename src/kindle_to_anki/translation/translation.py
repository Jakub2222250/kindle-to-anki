from translation.providers.polish_translator_local import translate_polish_context_to_english
from translation.providers.translator_llm import translate_context_with_llm

# Import new runtime system
try:
    from tasks.translation.migration_helper import translate_context_with_llm as translate_context_with_llm_new
    NEW_RUNTIME_AVAILABLE = True
except ImportError:
    NEW_RUNTIME_AVAILABLE = False


def process_context_translation(notes, source_lang_code: str, target_lang_code: str, ignore_cache=False, use_llm=False, use_new_runtime=False):
    """Process context translation for a list of notes

    Args:
        notes: List of AnkiNote objects to translate
        source_lang_code: Source language code (e.g., 'pl', 'es') 
        target_lang_code: Target language code (e.g., 'en')
        ignore_cache: Whether to ignore existing cache
        use_llm: Whether to use LLM translator instead of local model (for Polish only)
        use_new_runtime: Whether to use the new structured runtime system (experimental)
    """

    print("\nStarting context translation...")
    language_pair_code = f"{source_lang_code}-{target_lang_code}"

    if source_lang_code == "pl":
        if not use_llm and target_lang_code == "en":
            translate_polish_context_to_english(notes, ignore_cache=ignore_cache)
        else:
            if use_new_runtime and NEW_RUNTIME_AVAILABLE:
                print("Using new structured runtime system...")
                translate_context_with_llm_new(notes, source_lang_code, target_lang_code, ignore_cache=ignore_cache)
            else:
                translate_context_with_llm(notes, source_lang_code, target_lang_code, ignore_cache=ignore_cache)
    else:
        if use_new_runtime and NEW_RUNTIME_AVAILABLE:
            print("Using new structured runtime system...")
            translate_context_with_llm_new(notes, source_lang_code, target_lang_code, ignore_cache=ignore_cache)
        else:
            translate_context_with_llm(notes, source_lang_code, target_lang_code, ignore_cache=ignore_cache)

    print("Context translation completed.")

from translation.polish_translator import translate_polish_context_to_english
from translation.translation_cache import TranslationCache


def process_context_translation(notes, language, cache_suffix='default', ignore_cache=False):
    """Process context translation for a list of notes"""

    print("\nStarting context translation...")

    cache = TranslationCache(cache_suffix=cache_suffix)

    if not ignore_cache:
        print(f"Loaded translation cache with {len(cache.cache)} entries")
    else:
        print("Ignoring cache as per user request. Fresh translations will be generated.")

    if language == "pl":
        translate_polish_context_to_english(notes, cache)
    elif language == "es":
        print("Context translation for Spanish is not supported yet")
        exit()
    else:
        print("Context translation for this language is not supported yet")
        exit()

    print("Context translation completed.")

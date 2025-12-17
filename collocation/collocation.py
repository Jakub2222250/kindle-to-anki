from collocation.collocation_llm import generate_polish_collocations_llm
from collocation.collocation_cache import CollocationCache


def process_collocation_generation(notes, language, cache_suffix='default', ignore_cache=False, use_llm=True):
    """Process collocation generation for a list of notes

    Args:
        notes: List of AnkiNote objects to generate collocations for
        language: Language code (e.g., 'pl', 'es') 
        cache_suffix: Cache file suffix for collocation cache
        ignore_cache: Whether to ignore existing cache
        use_llm: Whether to use LLM for collocation generation (currently only LLM is supported)
    """

    print("\nStarting collocation generation...")

    cache = CollocationCache(cache_suffix=cache_suffix)

    if not ignore_cache:
        print(f"Loaded collocation cache with {len(cache.cache)} entries")
    else:
        print("Ignoring cache as per user request. Fresh collocations will be generated.")

    if language == "pl":
        if use_llm:
            generate_polish_collocations_llm(notes, cache)
        else:
            print("Only LLM-based collocation generation is currently supported for Polish")
            exit()
    elif language == "es":
        print("Collocation generation for Spanish is not supported yet")
        exit()
    else:
        print("Collocation generation for this language is not supported yet")
        exit()

    print("Collocation generation completed.")

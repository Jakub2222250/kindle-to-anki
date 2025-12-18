from collocation.providers.collocation_llm import generate_collocations_llm


def process_collocation_generation(notes, source_language_code: str, target_language_code: str, ignore_cache=False):
    """Process collocation generation for a list of notes"""

    print("\nStarting collocation generation...")
    generate_collocations_llm(notes, source_language_code, target_language_code, ignore_cache=ignore_cache)

    print("Collocation generation completed.")

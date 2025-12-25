from lexical_unit_identification.providers.lui_llm import process_notes_with_llm_lui
from lexical_unit_identification.providers.lui_polish_hybrid import process_notes_with_morfeusz


def complete_lexical_unit_identification(notes, source_language_code: str, target_language_code: str, ignore_cache: bool = False, use_hybrid: bool = False):
    """Process lexical unit identification for a list of notes

    Args:
        notes: List of AnkiNote objects to process
        source_language_code: Source language code (e.g., 'pl', 'es', 'de')
        target_language_code: Target language code (e.g., 'en')
        ignore_cache: Whether to ignore cached results
        use_hybrid: Whether to use language-specific hybrid approach (Polish only) instead of LLM
    """

    print("\nStarting lexical unit identification...")

    if use_hybrid and source_language_code == "pl" and target_language_code == "en":
        # Use the Polish-specific hybrid approach (Morfeusz2 + LLM)
        print("Using Polish hybrid lexical unit identification (Morfeusz2 + LLM)...")
        process_notes_with_morfeusz(notes, ignore_cache=ignore_cache)
    else:
        # Use the language-agnostic LLM approach (default)
        print(f"Using LLM-based lexical unit identification for {source_language_code}...")
        process_notes_with_llm_lui(notes, source_language_code, target_language_code, ignore_cache=ignore_cache)

    print("lexical unit identification completed.")

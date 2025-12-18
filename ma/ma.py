from ma.providers.ma_polish_hybrid import process_notes_with_morfeusz


def process_morphological_enrichment(notes, source_language_code: str, target_language_code: str, ignore_cache: bool = False):
    """Process morfeusz enrichment for a list of notes"""

    print("\nStarting morphological enrichment...")

    if source_language_code == "pl" and target_language_code == "en":
        process_notes_with_morfeusz(notes, ignore_cache=ignore_cache)
    elif source_language_code == "es":
        print("Not supported yet")
        exit()
    else:
        print("Not supported yet")
        exit()

    print("Morphological enrichment completed.")

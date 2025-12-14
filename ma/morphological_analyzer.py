from ma.polish_ma import process_notes_with_morfeusz


def process_morphological_enrichment(notes, language):
    """Process morfeusz enrichment for a list of notes"""

    print("\nStarting morphological enrichment...")

    if language == "pl":
        process_notes_with_morfeusz(notes)
    elif language == "es":
        print("Not supported yet")
        exit()
    else:
        print("Not supported yet")
        exit()

    print("Morphological enrichment completed.")

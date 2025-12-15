from anki.anki_connect import AnkiConnect
from anki.anki_note import AnkiNote
from ma.morphological_analyzer import process_morphological_enrichment


def get_all_notes(lang: str) -> list[dict]:
    """
    Retrieve all notes for a given language from Anki.
    """
    anki_connect_instance = AnkiConnect()

    if not anki_connect_instance.is_reachable():
        print("AnkiConnect is not reachable. Please ensure Anki is running with AnkiConnect installed and enabled.")
        exit(1)

    existing_notes = anki_connect_instance.get_notes(lang)

    uid_to_old_note_info_dict = {note["UID"]: note for note in existing_notes}

    notes = []

    for existing_note in existing_notes:
        # Generate AnkiNote objects from existing notes for reprocessing morphological analysis
        clean_context_sentence = existing_note.get("Context_Sentence", "").replace("<b>", "").replace("</b>", "").strip()

        note = AnkiNote(
            word=existing_note.get("Original_Form", ""),
            stem=existing_note.get("Expression", ""),
            usage=clean_context_sentence,
            language=lang,
            book_name=existing_note.get("Source_Book", ""),
            position="",
            timestamp="",
            uid=existing_note.get("UID", "")
        )

        notes.append(note)

    return uid_to_old_note_info_dict, notes


def generate_card_updates(uid_to_old_note_info_dict: dict, notes_to_reprocess: list[AnkiNote]) -> list[dict]:
    card_updates = []

    for note in notes_to_reprocess:

        old_note = uid_to_old_note_info_dict[note.uid]

        fields = dict()

        if old_note["Expression"] != note.expression:
            fields["Expression"] = note.expression

        if old_note["Original_Form"] != note.original_form:
            fields["Original_Form"] = note.original_form

        if old_note["Part_Of_Speech"] != note.part_of_speech:
            fields["Part_Of_Speech"] = note.part_of_speech

        if old_note["Context_Sentence"] != note.get_context_sentence_bold_word():
            fields["Context_Sentence"] = note.get_context_sentence_bold_word()
            fields["Context_Sentence_Cloze"] = note.get_context_sentence_cloze()

        if old_note.get("Aspect", "") != note.aspect:
            fields["Aspect"] = note.aspect

        if not fields:
            continue  # No changes detected

        card_update = {
            "UID": note.uid,
            "fields": fields
        }
        card_updates.append(card_update)

    for card_update in card_updates:
        old_note = uid_to_old_note_info_dict[card_update["UID"]]

        print(f"Card Update UID: {card_update['UID']}")
        for field, value in card_update["fields"].items():
            print(f"  {field}: {old_note[field]} [{value}]")

    return card_updates


if __name__ == "__main__":

    for lang in ["pl"]:
        print(f"\nProcessing language: {lang}")

        uid_to_old_note_info_dict, notes = get_all_notes(lang)

        # Do filtering in memory
        notes_to_reprocess = []

        for note in notes:
            existing_note = uid_to_old_note_info_dict[note.uid]

            # Avoid words that were manually or automatically updated with się or idiom
            if (len(existing_note["Expression"].split()) == 2 and "się" in existing_note["Expression"].split()):
                # Set the kindle_word back to without się for typical MA behavior
                note.kindle_word = existing_note["Expression"].replace(" się", "").replace("się ", "")
                notes_to_reprocess.append(note)
            elif existing_note["Part_Of_Speech"] == "adj":
                notes_to_reprocess.append(note)
            else:
                num_of_unsuitable_notes += 1

        print(f"Identified {num_of_unsuitable_notes} unsuitable notes with multiple word original_form. Skipping these.")
        print(f"\nReprocessing {len(notes_to_reprocess)} notes for morphological enrichment...")

        for note in notes_to_reprocess:
            print(note.kindle_word)

        process_morphological_enrichment(notes_to_reprocess, lang, ignore_cache=True)

        # Save morphological analysis updated fields back to Anki only
        card_updates = generate_card_updates(uid_to_old_note_info_dict, notes_to_reprocess)

        # Don't save until verified
        # anki_connect_instance.update_notes_fields(card_updates)

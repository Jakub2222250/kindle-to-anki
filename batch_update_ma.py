import json
from anki.anki_connect import AnkiConnect
from anki.anki_note import AnkiNote
from ma.morphological_analyzer import process_morphological_enrichment


if __name__ == "__main__":

    anki_connect_instance = AnkiConnect()

    for lang in ["pl"]:
        print(f"\nProcessing language: {lang}")

        existing_notes_as_dict = anki_connect_instance.get_notes(lang)

        notes_to_reprocess = []
        num_of_unsuitable_notes = 0

        for existing_note in existing_notes_as_dict:
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

            # Avoid words that were manually or automatically updated with się or idiom
            if len(note.kindle_word.split()) == 1:
                notes_to_reprocess.append(note)
            else:
                num_of_unsuitable_notes += 1

        print(f"Identified {num_of_unsuitable_notes} unsuitable notes with multiple word original_form. Skipping these.")

        print(f"\nReprocessing {len(notes_to_reprocess)} notes for morphological enrichment...")

        process_morphological_enrichment(notes_to_reprocess, lang)

        # Save morphological analysis updated fields back to Anki only
        card_updates = []

        for note in notes_to_reprocess:
            card_update = {
                "UID": note.uid,
                "fields": {
                    "Expression": note.expression,
                    "Original_Form": note.original_form,
                    "Part_Of_Speech": note.part_of_speech,
                    "Context_Sentence": note.get_context_sentence_bold_word(),
                    "Context_Sentence_Cloze": note.get_context_sentence_cloze(),
                    "Aspect": note.aspect
                }
            }
            card_updates.append(card_update)

        anki_connect_instance.update_notes_fields(card_updates[:10])

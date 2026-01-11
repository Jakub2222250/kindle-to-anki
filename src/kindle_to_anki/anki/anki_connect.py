import json
import urllib.request
import urllib.error

from kindle_to_anki.anki.anki_deck import AnkiDeck
from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.anki.constants import NOTE_TYPE_NAME


class AnkiConnect:
    """Super minimal AnkiConnect wrapper for Polish Vocab Discovery deck"""

    def __init__(self):
        self.anki_url = "http://localhost:8765"
        self.note_type = NOTE_TYPE_NAME

        # Confirm AnkiConnect is reachable
        print("\nChecking AnkiConnect reachability...")
        if not self.is_reachable():
            print("AnkiConnect not reachable. Exiting.")
            exit(0)
        print("AnkiConnect is reachable.")

    def _invoke(self, action, params=None):
        """Send request to AnkiConnect"""
        request_json = {
            "action": action,
            "version": 6
        }
        if params:
            request_json["params"] = params

        try:
            request_data = json.dumps(request_json).encode('utf-8')
            request = urllib.request.Request(self.anki_url, request_data)
            response = urllib.request.urlopen(request)
            response_data = json.loads(response.read().decode('utf-8'))

            if response_data.get('error'):
                raise Exception(f"AnkiConnect error: {response_data['error']}")

            return response_data.get('result')

        except urllib.error.URLError as e:
            raise Exception(f"Failed to connect to AnkiConnect: {e}")
        except Exception as e:
            raise Exception(f"AnkiConnect request failed: {e}")

    def is_reachable(self):
        """Check if AnkiConnect is reachable"""
        try:
            self._invoke("version")
            return True
        except Exception:
            return False

    def get_model_names(self):
        """Get list of existing note type names"""
        return self._invoke("modelNames")

    def create_model(self, model_name, fields, css, card_templates):
        """Create a new note type/model"""
        return self._invoke("createModel", {
            "modelName": model_name,
            "inOrderFields": fields,
            "css": css,
            "cardTemplates": card_templates
        })

    def get_notes(self, anki_deck: AnkiDeck):
        """Get all notes from the specified deck with Expression, Context_Sentence, and Definition fields"""

        print(f"\nFetching notes from Anki deck: '{anki_deck.parent_deck_name}'...")

        try:
            # Find all note IDs in the deck with the specified note type
            query = f'"deck:{anki_deck.parent_deck_name}" "note:{self.note_type}"'
            note_ids = self._invoke("findNotes", {"query": query})

            if not note_ids:
                return []

            # Get note info for all found notes
            notes_info = self._invoke("notesInfo", {"notes": note_ids})

            # Extract the requested fields
            notes_data = []
            for note in notes_info:
                fields = note.get('fields', {})
                note_data = {
                    'UID': fields.get('UID', {}).get('value', '').strip(),
                    'Surface_Lexical_Unit': fields.get('Surface_Lexical_Unit', {}).get('value', '').strip(),
                    'Expression': fields.get('Expression', {}).get('value', '').strip(),
                    'Context_Sentence': fields.get('Context_Sentence', {}).get('value', '').strip(),
                    'Context_Translation': fields.get('Context_Translation', {}).get('value', '').strip(),
                    'Part_Of_Speech': fields.get('Part_Of_Speech', {}).get('value', '').strip(),
                    'Definition': fields.get('Definition', {}).get('value', '').strip(),
                    'Aspect': fields.get('Aspect', {}).get('value', '').strip(),
                }

                notes_data.append(note_data)

            print("Notes fetch completed.")

            return notes_data

        except Exception as e:
            raise Exception(f"Failed to get deck notes: {e}")

    def create_notes_batch(self, anki_deck: AnkiDeck, anki_notes: list[AnkiNote]):
        """Create multiple notes in Anki from a list of AnkiNote objects"""
        print(f"\nCreating {len(anki_notes)} notes in Anki...")
        try:
            notes_data = []

            for anki_note in anki_notes:
                # Map AnkiNote fields to Anki note fields based on readme field order
                fields = {
                    "UID": anki_note.uid,
                    "Expression": anki_note.expression,
                    "Surface_Lexical_Unit": anki_note.surface_lexical_unit,
                    "Part_Of_Speech": anki_note.part_of_speech,
                    "Definition": anki_note.definition,
                    "Aspect": anki_note.aspect,
                    "Context_Sentence": anki_note.get_context_sentence_bold_word(),
                    "Context_Sentence_Cloze": anki_note.get_context_sentence_cloze(),
                    "Context_Translation": anki_note.context_translation,
                    "Collocations": anki_note.collocations,
                    "Original_Language_Hint": anki_note.original_language_hint,
                    "Hint_Test_Enabled": anki_note.hint_test_enabled,
                    "Notes": anki_note.notes,
                    "Source_Book": anki_note.source_book,
                    "Location": anki_note.location,
                    "Status": anki_note.status,
                    "Cloze_Enabled": anki_note.get_cloze_enabled_output(),
                    "Unit_Type": anki_note.unit_type,
                    "Generation_Metadata": anki_note.get_generation_metadata_output(),
                    "Usage_Level": anki_note.usage_level
                }

                note_data = {
                    "deckName": anki_deck.staging_deck_name,
                    "modelName": self.note_type,
                    "fields": fields,
                    "tags": anki_note.tags.split() if anki_note.tags else ["kindle_to_anki"]
                }

                notes_data.append(note_data)

            # Use addNotes action for batch creation
            result = self._invoke("addNotes", {"notes": notes_data})
            print("Notes creation completed.")
            return result  # Returns list of note IDs (or null for failed notes)

        except Exception as e:
            error_str = str(e)
            if "model was not found" in error_str:
                print(f"\nError: Note type '{self.note_type}' not found in Anki.")
                print("Run 'py -m kindle_to_anki.anki.setup_note_type' to create it.")
                exit(1)
            raise Exception(f"Failed to create notes batch: {e}")

    def get_uid_to_note_id_map(self):
        """Get a mapping from UID to Anki note ID for all notes in the deck"""
        try:
            query = f'"deck:{self.parent_deck_name}" "note:{self.note_type}"'
            note_ids = self._invoke("findNotes", {"query": query})

            if not note_ids:
                return {}

            notes_info = self._invoke("notesInfo", {"notes": note_ids})

            uid_to_note_id = {}
            for note in notes_info:
                fields = note.get('fields', {})
                uid = fields.get('UID', {}).get('value', '')
                if uid:
                    uid_to_note_id[uid] = note.get('noteId')

            return uid_to_note_id

        except Exception as e:
            raise Exception(f"Failed to get UID to note ID map: {e}")

    def update_notes_fields(self, card_updates):
        """Update multiple notes' fields using UID as note ID"""
        if not card_updates:
            print("No card updates provided")
            return []

        print(f"\nUpdating {len(card_updates)} notes in Anki...")

        successful_updates = []
        failed_updates = []

        uid_to_note_id_map = self.get_uid_to_note_id_map()

        for update in card_updates:
            uid = update.get('UID')
            fields_to_update = update.get('fields', {})

            id = int(uid_to_note_id_map[uid])

            if not uid or uid not in uid_to_note_id_map:
                print("Probably never happens")
                exit()

            print("Updating fields for UID:", uid, id)

            # Use UID directly as note ID
            try:
                self._invoke("updateNoteFields", {
                    "note": {
                        "id": id,
                        "fields": fields_to_update
                    }
                })
                successful_updates.append(uid)
            except Exception as e:
                failed_updates.append(f"Failed to update UID {uid}: {e}")

        print(f"Successfully updated {len(successful_updates)} notes")
        if failed_updates:
            print(f"Failed to update {len(failed_updates)} notes:")
            for failure in failed_updates:
                print(f"  {failure}")

        return successful_updates


if __name__ == "__main__":
    anki = AnkiConnect()

    # Test connection
    if anki.is_reachable():
        print("AnkiConnect is reachable!")

        # Get notes
        try:
            notes = anki.get_notes()
            print(f"Found {len(notes)} notes in deck")

            # Show first few notes as example
            for i, note in enumerate(notes[:3]):
                print(f"\nNote {i + 1}:")
                print(f"  Expression: {note['Expression']}")
                print(f"  Context: {note['Context_Sentence']}")
                print(f"  Definition: {note['Definition']}")
        except Exception as e:
            print(f"Error getting notes: {e}")

    else:
        print("AnkiConnect is not reachable. Make sure Anki is running with AnkiConnect addon installed.")

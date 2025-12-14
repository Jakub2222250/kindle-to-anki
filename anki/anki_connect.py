import json
import urllib.request
import urllib.error


class AnkiConnect:
    """Super minimal AnkiConnect wrapper for Polish Vocab Discovery deck"""

    def __init__(self):
        self.anki_url = "http://localhost:8765"
        self.ready_deck_name = "Polish Vocab Discovery::Ready"
        self.staging_deck_name = "Polish Vocab Discovery::Import"
        self.parent_deck_name = "Polish Vocab Discovery"
        self.note_type = "My Foreign Language Reading Words Note Type"

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

    def get_notes(self, language=None):
        """Get all notes from the specified deck with Expression, Context_Sentence, and Definition fields"""
        try:
            # Find all note IDs in the deck with the specified note type
            query = f'"deck:{self.parent_deck_name}" "note:{self.note_type}"'
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
                    'UID': fields.get('UID', {}).get('value', ''),
                    'Expression': fields.get('Expression', {}).get('value', ''),
                    'Context_Sentence': fields.get('Context_Sentence', {}).get('value', ''),
                    'Context_Translation': fields.get('Context_Translation', {}).get('value', ''),
                    'Part_Of_Speech': fields.get('Part_Of_Speech', {}).get('value', ''),
                    'Definition': fields.get('Definition', {}).get('value', '')
                }
                notes_data.append(note_data)

            return notes_data

        except Exception as e:
            raise Exception(f"Failed to get deck notes: {e}")

    def create_notes_batch(self, anki_notes, lang=None):
        """Create multiple notes in Anki from a list of AnkiNote objects"""
        print(f"\nCreating {len(anki_notes)} notes in Anki...")
        try:
            notes_data = []

            for anki_note in anki_notes:
                # Map AnkiNote fields to Anki note fields based on readme field order
                fields = {
                    "UID": anki_note.uid,
                    "Expression": anki_note.expression,
                    "Original_Form": anki_note.original_form,
                    "Part_Of_Speech": anki_note.part_of_speech,
                    "Definition": anki_note.definition,
                    "Secondary_Definitions": anki_note.secondary_definitions,
                    "Context_Sentence": anki_note.get_context_sentence_bold_word(),
                    "Context_Sentence_Cloze": anki_note.get_context_sentence_cloze(),
                    "Context_Translation": anki_note.context_translation,
                    "Collocations": anki_note.collocations,
                    "Original_Language_Hint": anki_note.original_language_hint,
                    "Notes": anki_note.notes,
                    "Source_Book": anki_note.source_book,
                    "Location": anki_note.location,
                    "Status": anki_note.status,
                    "Cloze_Enabled": anki_note.get_cloze_enabled_output()
                }

                note_data = {
                    "deckName": self.staging_deck_name,
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
            raise Exception(f"Failed to create notes batch: {e}")


# Example usage
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

"""Setup the required Anki note type via AnkiConnect"""
import json
import urllib.request
from pathlib import Path


def invoke(action, params=None):
    request_json = {"action": action, "version": 6}
    if params:
        request_json["params"] = params
    request_data = json.dumps(request_json).encode('utf-8')
    request = urllib.request.Request("http://localhost:8765", request_data)
    response = urllib.request.urlopen(request)
    response_data = json.loads(response.read().decode('utf-8'))
    if response_data.get('error'):
        raise Exception(f"AnkiConnect error: {response_data['error']}")
    return response_data.get('result')


TEMPLATES_DIR = Path(__file__).parent / "templates"

NOTE_TYPE_NAME = "My Foreign Language Reading Words Note Type"

FIELDS = [
    "UID",
    "Expression",
    "Definition",
    "Context_Sentence",
    "Context_Translation",
    "Part_Of_Speech",
    "Aspect",
    "Original_Form",
    "Context_Sentence_Cloze",
    "Collocations",
    "Original_Language_Hint",
    "Notes",
    "Source_Book",
    "Location",
    "Status",
    "Cloze_Enabled",
    "Unit_Type",
    "Generation_Metadata",
]

CARD_TEMPLATES = [
    ("Recognition", "recognition"),
    ("Production", "production"),
    ("Cloze Deletion", "cloze_deletion"),
]


def load_template(name):
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


def get_card_templates():
    templates = []
    for display_name, file_prefix in CARD_TEMPLATES:
        templates.append({
            "Name": display_name,
            "Front": load_template(f"{file_prefix}_front.html"),
            "Back": load_template(f"{file_prefix}_back.html"),
        })
    return templates


def setup_note_type():
    print("Checking AnkiConnect connection...")
    try:
        invoke("version")
    except Exception as e:
        print(f"Cannot connect to AnkiConnect. Make sure Anki is running.\nError: {e}")
        return False

    existing = invoke("modelNames")
    if NOTE_TYPE_NAME in existing:
        print(f"Note type '{NOTE_TYPE_NAME}' already exists.")
        return True

    print(f"Creating note type '{NOTE_TYPE_NAME}'...")
    invoke("createModel", {
        "modelName": NOTE_TYPE_NAME,
        "inOrderFields": FIELDS,
        "css": load_template("style.css"),
        "cardTemplates": get_card_templates()
    })
    print("Note type created successfully!")
    return True


if __name__ == "__main__":
    setup_note_type()

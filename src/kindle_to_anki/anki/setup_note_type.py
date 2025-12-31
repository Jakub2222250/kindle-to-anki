"""Setup the required Anki note type via AnkiConnect"""
from pathlib import Path
from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.anki.constants import NOTE_TYPE_NAME


TEMPLATES_DIR = Path(__file__).parent / "templates"

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
    "Usage_Level",
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
    try:
        anki = AnkiConnect()
    except SystemExit:
        return False

    if NOTE_TYPE_NAME in anki.get_model_names():
        print(f"Note type '{NOTE_TYPE_NAME}' already exists.")
        return True

    print(f"Creating note type '{NOTE_TYPE_NAME}'...")
    anki.create_model(NOTE_TYPE_NAME, FIELDS, load_template("style.css"), get_card_templates())
    print("Note type created successfully!")
    return True


if __name__ == "__main__":
    setup_note_type()

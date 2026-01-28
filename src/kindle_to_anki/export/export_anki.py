from pathlib import Path
import datetime

from kindle_to_anki.util.paths import get_outputs_dir


def write_anki_import_file(notes, language):
    print("\nWriting Anki import file...")

    outputs_dir = get_outputs_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    anki_path = outputs_dir / f"{language}_anki_import_{timestamp}.txt"

    # Write notes to file
    with open(anki_path, "w", encoding="utf-8") as f:
        f.write("#separator:tab\n")
        f.write("#html:true\n")
        f.write("#tags:kindle_to_anki\n")

        for note in notes:
            f.write(note.to_csv_line())

    print(f"Created Anki import file with {len(notes)} records at {anki_path}")

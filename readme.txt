1. Copy "Internal Storage/system/vocabulary/vocab.db" from Kindle to "./inputs/vocab.db"
2. Run kindle_to_anki.py
3. Import "outputs/anki_import.txt" into Anki
4. Manually review new cards
    a. Read through and fix generated "Definition", "Context_Translation"
    b. Decide if "Cloze_Enabled" should be set to True
6. Delete "Internal Storage/system/vocabulary/vocab.db" on of the kindle


Fields to write out in order:
UID
Expression
Original_Form
Part_Of_Speech
Definition
Secondary_Definition
Context_Sentence
Context_Sentence_Cloze (NEW)
Context_Translation
Collocations (NEW)
Original_Language_Hint (NEW)
Notes
Source_Book
Location
Status
Cloze_Enabled
Tags

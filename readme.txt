1. Copy "Internal Storage/system/vocabulary/vocab.db" from Kindle to "./inputs/vocab.db"
2. Run kindle_to_anki.py
3. Import "outputs/anki_import.txt" into Anki
4. Manually review new notes
    a. Read through and fix generated "Definition", "Context_Translation"
    b. Decide if "Cloze_Enabled" should be set to True
6. Delete "Internal Storage/system/vocabulary/vocab.db" on of the kindle


Fields to write out in order:
1: UID
2: Expression
3: Original_Form
4: Part_Of_Speech
5: Definition
6: Secondary_Definitions
7: Context_Sentence
8: Context_Sentence_Cloze
9: Context_Translation
10: Collocations
11: Original_Language_Hint
12: Notes
13: Source_Book
14: Location
15: Status
16: Cloze_Enabled
Tags

# Running stuff
kindle_to_anki.bat
py -m ma.polish_ma

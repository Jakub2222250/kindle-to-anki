# Importing Cards
kindle_to_anki.bat

# Reviewing cards manually
# It's important to manually decide which generated cards are worth studying now
# Put the relevant cards into ::Ready, and suspend and put into ::Quarantine the more obscure ones

1. Card browser notes view
2. Sort by creation date, select top ~50, add a tag called "batch"
3. Add filter tag:batch
4. For each note (using arrow keys):
   - If note is useful, common, relevant, something you want to be able to start saying, do nothing
   - If note is not worth studying now, crtl+J to suspend all cards in the note
5. Add "is:suspended" to filter and move those cards to ::Quarantine deck
6. Now change filter to "-is:suspended" and move those cards to ::Ready deck
7. Change filter to only "tag:batch" and action remove tags... "batch"


Fields to write out in order (ordering based on manual categorizing ease in Anki UI)
1: UID
2: Expression
3: Definition
4: Context_Sentence
5: Context_Translation
6: Part_Of_Speech
7: Aspect
8: Original_Form
9: Context_Sentence_Cloze
10: Collocations
11: Original_Language_Hint
12: Notes
13: Source_Book
14: Location
15: Status
16: Cloze_Enabled
Tags


# Running integration/unit tests
py -m ma.polish_ma
py -m ma.polish_ma_sgjp_helper
py -m pruning.pruning
py -m wsd.llm_enrichment

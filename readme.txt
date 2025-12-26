# Installation Guide
py -m pip install openai
py -m pip install thefuzz
Set OPENAI_API_KEY = <> environment variable
Add Anki Add-On: AnkiConnect  (2055492159)
Add Anki Add-On: Advanced Browser (874215009)

# Optionally clean out Vocab Builder time to time
Remove Internal Storage/vocabulary/vocab.db
Remove Internal Storage/vocabulary/vocab.db-* auxiliary files
Disconnect, restart kindle, look up a word (pretty quickly after to avoid some cache recovering original)

# TODO
Publish autopep8 formatting ruleset

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
17: Unit_Type
Tags


# Running integration/unit tests - NEW TASKS ARCHITECTURE

# Run all tests at once:
py tests/run_all_tests.py

# Run individual integration tests for new tasks architecture:
py tests/kindle_to_anki/tasks/collect_candidates/test_runtime_kindle.py
py tests/kindle_to_anki/tasks/translation/test_runtime_chat_completion.py
py tests/kindle_to_anki/tasks/translation/test_runtime_llm.py
py tests/kindle_to_anki/tasks/wsd/test_runtime_llm.py
py tests/kindle_to_anki/tasks/collocation/test_runtime_llm.py

# Legacy tests (for old architecture - will be deprecated):
py tests/kindle_to_anki/pruning/test_pruning.py

# DEPRECATED - Old provider architecture tests (use tasks/ tests instead):
# py tests/kindle_to_anki/lexical_unit_identification/providers/test_lui_llm.py
# py tests/kindle_to_anki/lexical_unit_identification/providers/test_lui_polish_hybrid.py
# py tests/kindle_to_anki/lexical_unit_identification/providers/pl_en/test_ma_polish_sgjp_helper.py
# py tests/kindle_to_anki/wsd/providers/test_wsd_llm.py
# py tests/kindle_to_anki/translation/providers/test_polish_translator_local.py
# py tests/kindle_to_anki/translation/providers/test_translator_llm.py

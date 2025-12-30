# Kindle to Anki

Converts Kindle Vocabulary Builder lookups into Anki flashcards with AI-generated definitions, translations, and context.

## Why Anki?

Anki's spaced repetition algorithm is one of the most effective tools for long-term vocabulary retention. While Kindle's built-in Vocabulary Builder is convenient, it has limitations:

- **Context-specific definitions**: Kindle shows generic dictionary entries. This tool performs word sense disambiguation to display only the meaning relevant to your reading context.
- **Optimal lexical units**: Rather than looking up single words, the tool identifies the smallest unit worth learning—whether that's an idiom, phrasal verb, or collocation.
- **Cloze deletions**: Cards use cloze format to test active recall of the word in its original sentence context.
- **Collocations**: Cards include common word pairings to help you use new vocabulary naturally.

## How It Works

Each major step of language analysis—lexical unit identification, word sense disambiguation, translation, and collocations—leverages LLM APIs such as OpenAI GPT. This project has no affiliation with OpenAI or any other provider and is free to use; you provide your own API keys.

API costs are generally inexpensive: on the order of $1–2 per 1000 words collected in my experience.

The provider/runtime architecture allows each step to be implemented differently—for example, using a local LLM if desired. Even the Kindle Vocabulary Builder card collection can be replaced with a different source if implemented.

Additional features:
- **AnkiConnect integration**: Sends generated cards directly to Anki—no manual import needed.
- **Smart duplicate detection**: Prunes duplicates automatically, but keeps repeated words if they appear in different contexts with different meanings.
- **Incremental imports**: Tracks timestamps of previous imports to avoid reprocessing.
- **API result caching**: Caches LLM responses to avoid repeated calls in case of failures or restarts.

## Prerequisites

- [Python](https://www.python.org/downloads/)
- [Anki Desktop](https://apps.ankiweb.net/)

## Installation

### 1. Install Python Dependencies
```
py -m pip install -e .
```

### 2. Set Up OpenAI API Key
Get your API key from https://platform.openai.com/api-keys then set environment variable:
```
set OPENAI_API_KEY=your-key-here
```

### 3. Install Anki Add-ons
With Anki open, go to Tools → Add-ons → Get Add-ons and install:
- AnkiConnect: 2055492159

### 4. Create Note Type
With Anki running:
```
py -m kindle_to_anki.anki.setup_note_type
```

### 5. Configuration
Copy the sample config and edit as needed:
```
copy data\config\config.sample.json data\config\config.json
```
Edit `data/config/config.json` to configure your language pairs, deck names, and task settings.

## Getting Vocabulary Data

**Option A: Automatic (Windows)**
Connect your Kindle via USB. The script will automatically find `vocab.db`.

**Option B: Manual**
Copy `vocab.db` from your Kindle's `Internal Storage/vocabulary/` folder to `data/inputs/`.

## Usage

### Import Cards
```
py -m kindle_to_anki.main
```

### Manually validate Cards (Optional)

You may want to manually validate auto-generated notes before committing to learning them, or prioritize more relevant cards first. If so, set up a parent deck with subdecks:
- `Language::Import` — where new cards land
- `Language::Quarantine` — less relevant cards you want to learn later
- `Language::Ready` — vetted cards for study

In `config.json`, set `parent_deck_name` to your parent deck (e.g., `Polish Vocab Discovery`) and `staging_deck_name` to the import subdeck (e.g., `Polish Vocab Discovery::Import`).

Install the **Advanced Browser** add-on (874215009) to sort by creation date and other useful fields.

**Review workflow:**
1. Open card browser, sort by creation date
2. Select recent cards, tag as "batch"
3. Filter `tag:batch`, review each:
   - Useful → leave as-is
   - Not worth studying → Ctrl+J to suspend
4. Filter `tag:batch is:suspended` → move to `::Quarantine`
5. Filter `tag:batch -is:suspended` → move to `::Ready`
6. Remove "batch" tag

## Maintenance

### Clear Vocabulary Builder (Optional)
To reset Kindle's vocab.db:
1. Delete `Internal Storage/vocabulary/vocab.db` and auxiliary files
2. Disconnect and restart Kindle
3. Look up a word quickly before cache recovers

## Running Tests
```
py tests/kindle_to_anki/tasks/collect_candidates/test_runtime_kindle.py
py tests/kindle_to_anki/tasks/translation/test_runtime_chat_completion.py
py tests/kindle_to_anki/tasks/wsd/test_runtime_llm.py
py tests/kindle_to_anki/tasks/collocation/test_runtime_llm.py
py tests/kindle_to_anki/pruning/test_pruning.py
```

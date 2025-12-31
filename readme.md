# Kindle to Anki

Transform your Kindle vocabulary lookups into high-quality Anki flashcards—automatically.

## Why This Tool?

When you look up a word on your Kindle, it gets saved to the Vocabulary Builder. This tool takes those lookups and creates flashcards that are optimized for long-term retention:

- **Context-aware definitions**: Generic dictionary entries don't help when a word has multiple meanings. This tool performs word sense disambiguation to show only the definition relevant to your reading context.
- **Optimal lexical units**: Identifies what's actually worth learning—whether that's a single word, an idiom, a phrasal verb, or a collocation.
- **Cloze deletions**: Test active recall by filling in the blank in the original sentence where you encountered the word.
- **Collocations**: Learn common word pairings to use new vocabulary naturally.
- **Direct Anki sync**: Cards are sent directly to Anki via AnkiConnect—no manual import files needed.
- **Smart duplicate handling**: Automatically detects duplicates, but keeps repeated words when they appear in different contexts with different meanings.
- **Incremental imports**: Only processes new vocabulary entries since your last import.
- **Resilient processing**: Caches API responses to avoid repeated calls if something fails mid-run.

## Card Types

The note type generates three card types for comprehensive vocabulary learning:

**Recognition** — Recognize the word's meaning from context.

| Front | Back |
|:-----:|:----:|
| <img width="300" alt="Recognition" src="https://github.com/user-attachments/assets/718a02be-e92c-47b7-927d-dcfed04eee35" /> | <img width="300" alt="Recognition Back" src="https://github.com/user-attachments/assets/ebc793bd-d93b-47aa-9f50-714f0f6eb861" /> |

**Production** — Produce the word from its definition.

| Front | Back |
|:-----:|:----:|
| <img width="300" alt="Production" src="https://github.com/user-attachments/assets/6ff2376b-a124-43da-a87c-ab57c231f352" /> | <img width="300" alt="Production Back" src="https://github.com/user-attachments/assets/cb161da5-7982-4324-97cd-7b994416f52e" /> |

**Cloze Deletion** — Fill in the blank in the original sentence.

| Front | Back |
|:-----:|:----:|
| <img width="300" alt="Cloze" src="https://github.com/user-attachments/assets/6f6074e7-3732-4bf6-9cd2-3a141f68fd28" /> | <img width="300" alt="Cloze Back" src="https://github.com/user-attachments/assets/1709a8fe-e143-462a-a0b2-67642ac5b7c8" /> |

## How It Works

Each processing step—lexical unit identification, word sense disambiguation, translation, and collocations—uses LLM APIs such as OpenAI GPT. This project has no affiliation with OpenAI or any other provider; you provide your own API keys.

API costs are modest: roughly $1–2 per 1000 words in my experience.

The modular architecture allows each step to use a different provider—including local LLMs if desired. The vocabulary source can also be swapped out if you want to use something other than Kindle.

## Prerequisites

- [Python](https://www.python.org/downloads/)
- [Anki Desktop](https://apps.ankiweb.net/)
- [OpenAI API account](https://platform.openai.com/) — $5 in API credits covers approximately 1500–2000 flashcards

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

### 4. Configuration
Run the setup wizard to configure your decks and task settings (will also create the note type if missing):
```
py -m kindle_to_anki.configuration.setup_wizard
```
Alternatively, copy the sample config and edit manually:
```
copy data\config\config.sample.json data\config\config.json
```

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

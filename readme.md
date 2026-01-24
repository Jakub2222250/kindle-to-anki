# Kindle to Anki

Transform your Kindle vocabulary lookups into high-quality Anki flashcards—automatically.

Built for foreign language learners reading books in their target language. When you look up unfamiliar words on your Kindle, this tool turns them into flashcards with context-aware definitions and translations to your native language. I (the author) use it for studying Polish with English translations, but it works with any language pair.

## Why This Tool?

This tool takes your Kindle Vocabulary Builder lookups and creates flashcards optimized for long-term retention:

- **Context-aware definitions**: Generic dictionary entries don't help when a word has multiple meanings. This tool performs word sense disambiguation to show only the definition relevant to your reading context.
- **Optimal lexical units**: Identifies what's actually worth learning—whether that's a single word, an idiom, a phrasal verb, or a collocation.
- **Cloze deletions**: Test active recall by filling in the blank in the original sentence where you encountered the word.
- **Collocations**: Learn common word pairings to use new vocabulary naturally.
- **Usage level ranking**: Each word is tagged with its frequency/importance level, letting you prioritize the most useful vocabulary first.
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

## API Costs

This tool uses LLM APIs to process vocabulary. The recommended provider is **Google Gemini**, which offers a generous free tier sufficient for most users.

With Gemini's free tier, you can process hundreds of words daily at no cost. For heavier usage, paid tiers are available at roughly $0.50 per 1000 words.

## Prerequisites

- [Python](https://www.python.org/downloads/)
- [Anki Desktop](https://apps.ankiweb.net/)
- [Google AI Studio account](https://aistudio.google.com/) — free tier available
- Kindle eReader
- Desire to learn foreign language words optimally

## Installation

### 1. Install Python Dependencies
```
py -m pip install -e .
```

### 2. Set Up Gemini API Key
Get your free API key from https://aistudio.google.com/apikey then set environment variable:
```
set GEMINI_API_KEY=your-key-here
```

> **Alternative providers:** OpenAI and Grok are also supported. Set `OPENAI_API_KEY` or `GROK_API_KEY` and update the model in config.json.

### 3. Install Anki Add-ons
With Anki open, go to Tools → Add-ons → Get Add-ons and install:
- AnkiConnect: 2055492159

### 4. Configuration
Launch the UI and use the Setup Wizard to configure your decks and task settings:
```
py -m kindle_to_anki.ui.app
```
Click **Setup Wizard** to:
- Add/remove language decks
- Configure source and target languages
- Set task-specific settings (models, batch sizes) per deck
- Create the Anki note type if missing

Alternatively, copy the sample config and edit manually:
```
copy data\config\config.sample.json data\config\config.json
```

### Deck Setup

You may want to manually validate auto-generated notes before committing to learning them, or prioritize more relevant cards first. If so, set up a parent deck with subdecks:
- `Language::Import` — where new cards land
- `Language::Quarantine` — less relevant cards you want to learn later
- `Language::Ready` — vetted cards for study

In `config.json`, set `parent_deck_name` to your parent deck (e.g., `Polish Vocab Discovery`) and `staging_deck_name` to the import subdeck (e.g., `Polish Vocab Discovery::Import`).

Install the **Advanced Browser** add-on (874215009) to sort by creation date and other useful fields.

## Kindle Dictionary Setup

For Vocabulary Builder to capture your lookups, you need a dictionary for your target language:

1. **Built-in dictionaries**: Check if Kindle has a dictionary for your language. Go to Settings → Language & Dictionaries → Dictionaries to see available options and set a default.

2. **Third-party dictionaries**: If no built-in option exists, [Reader Dict](https://www.reader-dict.com/) offers quality dictionaries for many languages.

3. **Catch-all dictionary**: By default, Vocabulary Builder only captures words that exist in your dictionary. To capture *every* word you look up (even if undefined), install [catch-all-mobi](https://github.com/Jakub2222250/catch-all-mobi)—this ensures no lookup is missed.

## Getting Vocabulary Data

**Option A: Automatic (Windows only)**
Connect your Kindle via USB. The script will automatically find `vocab.db`.

**Option B: Manual**
Copy `vocab.db` from your Kindle's `Internal Storage/vocabulary/` folder to `data/inputs/`.

## Usage

### Launch the UI
```
py -m kindle_to_anki.ui.app
```

### Export Vocabulary to Anki
From the main screen, click **Export Vocabulary** to:
- Read vocabulary from your Kindle
- Process words through all configured tasks (disambiguation, translation, hints, etc.)
- Create flashcards in Anki via AnkiConnect

Progress and logs are displayed in real-time.

### Adjust Settings
Click **Setup Wizard** anytime to modify task settings, models, or deck configuration.

### Update Existing Cards
To retroactively update existing Anki cards by re-running specific tasks (e.g., regenerate definitions with a new prompt, recalculate usage levels):
```
py -m kindle_to_anki.update_anki_cards
```

This interactive script lets you:
- Select which task(s) to run: WSD, hints, collocations, translations, usage levels, cloze scoring
- Filter cards by deck, card state (new/learning/review), or custom Anki query
- Preview changes before applying them
- Update cards in batches

## Anki Usage

### Recommended Settings

If you're new to Anki, these settings work well for vocabulary learning:

1. **Enable FSRS** (modern spaced repetition algorithm):
   - Go to deck options (gear icon next to deck) → FSRS section
   - Enable "FSRS" toggle
   - Click "Optimize" after you have 1000+ reviews for personalized intervals

2. **Daily limits** (in deck options):
   - New cards/day: **20** (adjust based on your time—each new card adds ~1 min/day of future reviews)
   - Maximum reviews/day: **9999** (don't limit reviews; limiting creates a backlog)

3. **Learning steps** (in deck options → New Cards):
   - Learning steps: `1m 10m` (default is fine for most users)
   - Graduating interval: `1` day

4. **Display settings** (Tools → Preferences → Review):
   - Show remaining card count: helpful for motivation
   - Show next review time above buttons: helps you understand the algorithm

### Filtering by Usage Level

Each card is tagged with a `Usage_Level` from 1-5, where **5 = most common/useful words** and **1 = rare words**. Use this to prioritize high-value vocabulary.

**Find cards by usage level:**
- In the browser (Browse button), use the search filter:
  - `Usage_Level:5` — most common words
  - `Usage_Level:4 OR Usage_Level:5` — common words
  - `Usage_Level:1 OR Usage_Level:2` — rare words (consider suspending)

### Moving Cards Between Decks

To move vetted cards from Import to Ready:

1. Open the browser (Browse button or `B`)
2. Search for cards in your import deck: `deck:"Polish Vocab Discovery::Import"`
3. Optionally filter by usage level: `deck:"Polish Vocab Discovery::Import" Usage_Level:5`
4. Select cards (`Ctrl+A` for all, or `Ctrl+Click` for specific cards)
5. Right-click → Change Deck → select your Ready deck

**Workflow tip:** Review new imports periodically. Move good cards to Ready, and cards you want to defer to Quarantine.

## Maintenance

### Clear Vocabulary Builder
Your Kindle can store a maximum of about 2000 vocabulary words.

To reset Kindle's vocab.db:

1. https://github.com/eichtml/Lexindle?tab=readme-ov-file#%EF%B8%8F-important-kindle-vocabulary-limit

   If those instructions fail:
   1. Save vocab.db to your PC first, then use it to overwrite vocab.db on the kindle
   2. Click "sync" on kindle before restarting

## Running Tests
```
py tests/kindle_to_anki/tasks/collect_candidates/test_runtime_kindle.py
py tests/kindle_to_anki/tasks/translation/test_runtime_chat_completion.py
py tests/kindle_to_anki/tasks/wsd/test_runtime_llm.py
py tests/kindle_to_anki/tasks/collocation/test_runtime_llm.py
py tests/kindle_to_anki/pruning/test_pruning.py
```

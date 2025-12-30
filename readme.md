# Kindle to Anki

Converts Kindle Vocabulary Builder lookups into Anki flashcards with AI-generated definitions, translations, and context.

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
- Advanced Browser: 874215009

### 4. Create Note Type
With Anki running:
```
py src/kindle_to_anki/anki/setup_note_type.py
```

### 5. Configuration
Copy the sample config and edit as needed:
```
copy data\config\config.sample.json data\config\config.json
```
Edit `data/config/config.json` to configure your language pairs, deck names, and task settings.

## Getting Vocabulary Data

**Option A: Automatic (Windows 10)**
Connect your Kindle via USB. The script will automatically find `vocab.db`.

**Option B: Manual**
Copy `vocab.db` from your Kindle's `Internal Storage/vocabulary/` folder to `data/inputs/`.

## Usage

### Import Cards
```
kindle_to_anki.bat
```

### Review Cards
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

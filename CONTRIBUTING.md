# Contributing

Thanks for your interest in contributing!

## Areas for Contribution

- **New vocabulary sources**: Implement alternatives to Kindle's vocab.db (e.g., Kobo, manual input, browser extensions)
- **Language support**: Add or improve language-specific LUI prompts in `tasks/lui/lui_prompts.py`
- **Alternative LLM providers**: Add new platforms in `platforms/`
- **Card templates**: Improve HTML/CSS in `anki/templates/`
- **Bug fixes and documentation**

## Development Setup

```bash
py -m pip install -e .
set OPENAI_API_KEY=your-key-here
```

## Architecture Notes

The project uses a task/runtime pattern:
- **Tasks** (`tasks/`) define what needs to happen (translation, WSD, etc.)
- **Runtimes** implement how (OpenAI, DeepL, local LLM, etc.)
- **Platforms** (`platforms/`) wrap API clients

Each task has a cache to avoid redundant API calls during development.

## Pull Requests

1. Fork and create a feature branch
2. Keep changes focused and minimal
3. Test with your own API keys before submitting
4. Update documentation if adding features

## Code Style

- Follow existing patterns in the codebase
- No strict formatter enforced—just keep it readable

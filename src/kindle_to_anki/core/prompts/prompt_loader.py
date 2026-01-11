"""Central loader for versioned prompt templates."""

import json
from pathlib import Path
from typing import Dict, Any, List

# Base path for all task prompts
TASKS_DIR = Path(__file__).parent.parent.parent / "tasks"


class PromptSpec:
    """Holds prompt specification and template."""

    def __init__(self, spec: Dict[str, Any], template: str):
        self.spec = spec
        self.template = template
        self.id = spec.get("id", "unknown")
        self.version = spec.get("version", "0.0")

    def build(self, **kwargs) -> str:
        return self.template.format(**kwargs)


class PromptLoader:
    """Loads prompt specs and templates from disk."""

    _cache: Dict[str, PromptSpec] = {}

    @classmethod
    def list_prompts(cls, task: str) -> List[str]:
        """Return all available prompt IDs for a task."""
        prompts_dir = TASKS_DIR / task / "prompts"
        if not prompts_dir.exists():
            return []
        return [p.stem for p in prompts_dir.glob("*.json")]

    @classmethod
    def load(cls, task: str, prompt_id: str) -> PromptSpec:
        cache_key = f"{task}/{prompt_id}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        prompts_dir = TASKS_DIR / task / "prompts"
        spec_path = prompts_dir / f"{prompt_id}.json"
        template_path = prompts_dir / f"{prompt_id}.template.txt"

        with open(spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)

        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        prompt_spec = PromptSpec(spec, template)
        cls._cache[cache_key] = prompt_spec
        return prompt_spec


# Default prompts per task
DEFAULT_PROMPTS = {
    "wsd": "wsd_v3",
    "usage_level": "usage_level_v1",
    "translation": "translation_v1",
    "collocation": "collocation_v1",
    "hint": "hint_v2",
    "cloze_scoring": "cloze_scoring_v1",
}

# LUI has language-specific defaults
LUI_LANGUAGE_DEFAULTS = {
    "pl": "lui_pl_v1",
    "es": "lui_es_v1",
}
LUI_GENERIC_DEFAULT = "lui_generic_v1"


def get_default_prompt_id(task: str) -> str | None:
    """Get the default prompt_id for a task."""
    return DEFAULT_PROMPTS.get(task)


def get_prompt(task: str, prompt_id: str = None) -> PromptSpec:
    """Get a prompt by task and optional id. Uses default if id not specified."""
    if prompt_id is None:
        prompt_id = DEFAULT_PROMPTS.get(task)
        if prompt_id is None:
            raise ValueError(f"No default prompt configured for task: {task}")
    return PromptLoader.load(task, prompt_id)


def get_lui_prompt(language_code: str, prompt_id: str = None) -> PromptSpec:
    """Get LUI prompt, with language-specific defaults."""
    if prompt_id is None:
        prompt_id = LUI_LANGUAGE_DEFAULTS.get(language_code, LUI_GENERIC_DEFAULT)
    return PromptLoader.load("lui", prompt_id)

"""Utilities for JSON parsing from LLM responses."""


def strip_markdown_code_block(text: str) -> str:
    """Strip markdown code blocks (```json ... ```) from LLM responses."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines)
    return text

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


def sanitize_project_name(name: str) -> str:
    """Remove invalid filename characters."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def format_field_label(name: str) -> str:
    """Convert an internal key like "story_preferences" into a friendly label."""

    if not name:
        return ""

    cleaned = name.replace("_", " ").replace("[", " ").replace("]", " ")
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:]


def summarize_value_for_prompt(value: Any) -> str:
    """Produce a readable summary for context shown to the language model."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        parts = [summarize_value_for_prompt(v) for v in value]
        parts = [p for p in parts if p]
        return ", ".join(parts)
    if isinstance(value, dict):
        segments = []
        for key, val in value.items():
            summary = summarize_value_for_prompt(val)
            if summary:
                segments.append(f"{format_field_label(str(key))}: {summary}")
        return "; ".join(segments)
    return str(value)


@dataclass(frozen=True)
class PromptSpec:
    """Normalized prompt metadata shared between the UI and text generator."""

    instruction: str = ""
    max_tokens: Optional[int] = None

    @classmethod
    def from_config(cls, config: Any) -> "PromptSpec":
        """Create a :class:`PromptSpec` from raw JSON template data.

        The templates may store prompts as plain strings (legacy behaviour) or as
        objects containing additional metadata such as ``max_tokens``.  This
        helper normalizes both representations.
        """

        if isinstance(config, cls):
            return config

        instruction = ""
        max_tokens: Optional[int] = None

        if isinstance(config, dict):
            raw_instruction = config.get("instruction")
            if not isinstance(raw_instruction, str):
                raw_instruction = config.get("prompt") or config.get("text") or ""
            instruction = raw_instruction.strip()

            raw_tokens = config.get("max_tokens")
            if isinstance(raw_tokens, int) and raw_tokens > 0:
                max_tokens = raw_tokens
        elif isinstance(config, str):
            instruction = config.strip()

        return cls(instruction=instruction, max_tokens=max_tokens)


from __future__ import annotations

import re
from typing import Any


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

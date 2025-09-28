from __future__ import annotations
import re


def sanitize_project_name(name: str) -> str:
    """Remove invalid filename characters."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)

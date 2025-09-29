from __future__ import annotations

import os
from typing import Any, Dict, List

from .project import Project
from .logger import Logger
from .utils import summarize_value_for_prompt, format_field_label


class StorylineManager:
    """Manage storyline persistence and prompting metadata."""

    TEMPLATE_FILENAME = "storyline_template.json"
    PROMPT_FILENAME = "storyline_template_prompt.json"
    DEFAULT_TEMPLATE: Dict[str, Any] = {"title": "", "summary": "", "turns": []}
    DEFAULT_INSTRUCTION = (
        "Write the next major beat of the storyline in 2-4 sentences, highlighting"
        " conflicts, stakes, and hooks for the players."
    )

    def __init__(self, project: Project, logger: Logger | None = None):
        self.project = project
        self.logger = logger
        self.prompt_config: Dict[str, Any] = {}

    # --- Template / persistence helpers ---
    def load_prompt_config(self) -> Dict[str, Any]:
        data = self.project.load_prompt_template(self.PROMPT_FILENAME)
        if not isinstance(data, dict):
            data = {}
        self.prompt_config = data
        return data

    def ensure_initialized(self, project_folder: str) -> None:
        path = self.project.storyline_path(project_folder)
        if os.path.exists(path):
            return
        template = self.project.load_template(self.TEMPLATE_FILENAME)
        if not isinstance(template, dict) or not template:
            template = dict(self.DEFAULT_TEMPLATE)
        cleared = self.project.clear_template(template)
        if not isinstance(cleared, dict):
            cleared = dict(self.DEFAULT_TEMPLATE)
        cleared.setdefault("turns", [])
        if not isinstance(cleared["turns"], list):
            cleared["turns"] = []
        self.project.save_json(cleared, path)
        if self.logger:
            self.logger.log("StorylineManager: created storyline file")

    def load(self, project_folder: str) -> Dict[str, Any]:
        self.ensure_initialized(project_folder)
        return self.project.read_json(self.project.storyline_path(project_folder))

    def save(self, project_folder: str, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            data = dict(self.DEFAULT_TEMPLATE)
        turns = data.get("turns")
        if not isinstance(turns, list):
            data["turns"] = []
        self.project.save_json(data, self.project.storyline_path(project_folder))

    def get_turns(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        turns = []
        for turn in data.get("turns", []):
            if isinstance(turn, dict):
                content = str(turn.get("content", "") or "")
                origin = str(turn.get("origin", turn.get("author", "user")) or "user")
            else:
                content = str(turn)
                origin = "user"
            turns.append({"content": content, "origin": origin})
        return turns

    def update_turns(self, state: Dict[str, Any], turns: List[Dict[str, Any]]) -> Dict[str, Any]:
        data = dict(state or {})
        normalized: List[Dict[str, Any]] = []
        for turn in turns:
            content = str(turn.get("content", "") or "")
            origin = str(turn.get("origin", "user") or "user")
            normalized.append({"content": content, "origin": origin})
        data["turns"] = normalized
        return data

    # --- Prompt helpers ---
    def instruction_for_turn(self, index: int) -> str:
        config = self.prompt_config or {}
        instructions = config.get("turn_instructions")
        if isinstance(instructions, list) and index < len(instructions):
            candidate = instructions[index]
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        default = config.get("default_instruction")
        if isinstance(default, str) and default.strip():
            return default.strip()
        return self.DEFAULT_INSTRUCTION

    def build_prompt_context(
        self,
        project_folder: str,
        turns: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        context: Dict[str, str] = {}

        # World & story summary
        try:
            story_data = self.project.read_json(self.project.story_path(project_folder))
        except FileNotFoundError:
            story_data = None
        except Exception:
            story_data = None
        if story_data:
            summary = summarize_value_for_prompt(story_data)
            if summary:
                context["World & Story"] = summary

        # Character summary
        character_summaries: List[str] = []
        for name in sorted(self.project.list_characters(project_folder)):
            try:
                char_data = self.project.read_json(
                    self.project.character_path(project_folder, name)
                )
            except FileNotFoundError:
                continue
            except Exception:
                continue
            summary = summarize_value_for_prompt(char_data)
            label = format_field_label(name)
            if summary:
                character_summaries.append(f"{label}: {summary}")
            else:
                character_summaries.append(label)
        if character_summaries:
            context["Key Characters"] = "; ".join(character_summaries)

        # Existing turns
        if turns:
            turn_summaries: List[str] = []
            for idx, turn in enumerate(turns):
                summary = summarize_value_for_prompt(turn.get("content", ""))
                if summary:
                    turn_summaries.append(f"{idx + 1}. {summary}")
            if turn_summaries:
                context["Existing Storyline Turns"] = " | ".join(turn_summaries)

        return context

    def turn_label(self, turn: Dict[str, Any], index: int) -> str:
        summary = summarize_value_for_prompt(turn.get("content", ""))
        summary = " ".join(summary.split()) if summary else "<empty>"
        if len(summary) > 80:
            summary = summary[:77] + "..."
        return f"{index + 1}. {summary}"

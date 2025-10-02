from __future__ import annotations
from typing import Dict, Iterable, List, Sequence

from .autofill import AutofillService
from .logger import Logger
from .project import Project
from .storyline import StorylineManager


class StoryWriter:
    """Turn structured storyline turns into long-form narrative prose."""

    def __init__(
        self,
        project: Project,
        storyline_manager: StorylineManager,
        autofill: AutofillService | None,
        logger: Logger | None = None,
        *,
        max_chunk_chars: int = 1800,
        story_so_far_limit: int = 3200,
    ) -> None:
        self.project = project
        self.storyline_manager = storyline_manager
        self.autofill = autofill
        self.logger = logger
        self.max_chunk_chars = max_chunk_chars
        self.story_so_far_limit = story_so_far_limit

    # ------------------------------------------------------------------
    # Public API
    def generate_story(
        self,
        project_folder: str,
        turns: Sequence[Dict[str, object]],
        *,
        stub_mode: bool = False,
    ) -> str:
        """Generate a cohesive story from storyline turns."""

        summaries = self.prepare_turn_summaries(turns)
        if not summaries:
            return ""

        context_text = self._build_world_context(project_folder)

        story_sections: List[str] = []
        story_so_far = ""

        for chunk in self._chunk_summaries(summaries):
            prompt = self._compose_prompt(chunk, context_text, story_so_far)
            section = ""
            if self.autofill and not stub_mode:
                try:
                    section = self.autofill.generate(prompt).strip()
                except Exception as exc:  # pragma: no cover - defensive
                    if self.logger:
                        self.logger.log(
                            "StoryWriter: autofill failed: %s", exc
                        )
                    section = ""
            if not section:
                # Fallback to a lightly formatted version of the beats
                section = chunk

            cleaned = section.strip()
            if cleaned:
                story_sections.append(cleaned)
                story_so_far = (story_so_far + "\n\n" + cleaned).strip()

        return "\n\n".join(section for section in story_sections if section).strip()

    # ------------------------------------------------------------------
    # Prompt composition helpers
    def _compose_prompt(
        self, chunk: str, context_text: str, story_so_far: str
    ) -> str:
        excerpt = story_so_far[-self.story_so_far_limit :].strip()

        parts: List[str] = [
            (
                "You are an expert long-form fiction writer tasked with turning "
                "structured story beats from a tabletop role-playing game into "
                "immersive prose. Maintain continuity, consistent character "
                "voices, and coherent pacing."
            ),
            (
                "Write 3-6 paragraphs in third-person past tense. Include rich "
                "sensory detail, emotional beats, and connective tissue between "
                "events while respecting the provided sequence."
            ),
        ]

        if context_text:
            parts.append("World and character context:\n" + context_text)

        if excerpt:
            parts.append(
                f"Story so far (last {self.story_so_far_limit} chars):\n{excerpt}"
            )
        else:
            parts.append("Story so far: [Start of story]")

        parts.append("Story beats to cover:\n" + chunk)
        parts.append("Produce only the narrative continuation.")
        return "\n\n".join(parts)

    def _build_world_context(self, project_folder: str) -> str:
        context_map = self.storyline_manager.build_prompt_context(project_folder, [])
        lines = []
        for key, value in context_map.items():
            if value:
                lines.append(f"{key}: {value}")
        return "\n".join(lines).strip()

    def _chunk_summaries(self, summaries: Sequence[str]) -> List[str]:
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for summary in summaries:
            text = summary.strip()
            if not text:
                continue

            if len(text) > self.max_chunk_chars:
                # Flush existing chunk before handling oversized entry
                if current:
                    chunks.append("\n\n".join(current))
                    current = []
                    current_len = 0
                for part in self._split_large_entry(text):
                    chunks.append(part)
                continue

            added_length = len(text) + (2 if current else 0)
            if current and current_len + added_length > self.max_chunk_chars:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0

            current.append(text)
            current_len += len(text) + 2

        if current:
            chunks.append("\n\n".join(current))

        return chunks

    def _split_large_entry(self, text: str) -> List[str]:
        parts: List[str] = []
        start = 0
        length = len(text)
        while start < length:
            end = min(start + self.max_chunk_chars, length)
            parts.append(text[start:end].strip())
            start = end
        return [part for part in parts if part]

    # ------------------------------------------------------------------
    # Static helpers
    @staticmethod
    def prepare_turn_summaries(
        turns: Iterable[Dict[str, object]]
    ) -> List[str]:
        summaries: List[str] = []
        for index, turn in enumerate(turns, start=1):
            if not isinstance(turn, dict):
                continue
            content = str(turn.get("content", "") or "").strip()
            if not content:
                continue

            lines = [f"Turn {index}: {content}"]

            player_actions = turn.get("player_actions")
            if isinstance(player_actions, dict):
                actions_text = StoryWriter._format_mapping("Action", player_actions)
                if actions_text:
                    lines.append(actions_text)

            outcomes = turn.get("per_player_outcomes")
            if isinstance(outcomes, dict):
                outcome_text = StoryWriter._format_mapping("Outcome", outcomes)
                if outcome_text:
                    lines.append(outcome_text)

            reflections = turn.get("player_reflections")
            if isinstance(reflections, dict):
                reflection_text = StoryWriter._format_mapping(
                    "Reflection", reflections
                )
                if reflection_text:
                    lines.append(reflection_text)

            summaries.append("\n".join(lines))

        return summaries

    @staticmethod
    def _format_mapping(label: str, values: Dict[str, object]) -> str:
        parts: List[str] = []
        for key in sorted(values):
            value = values.get(key)
            text = str(value or "").strip()
            key_text = str(key or "").strip()
            if text and key_text:
                parts.append(f"{key_text}: {text}")
        if not parts:
            return ""
        return f"{label}s: " + "; ".join(parts)


__all__ = ["StoryWriter"]


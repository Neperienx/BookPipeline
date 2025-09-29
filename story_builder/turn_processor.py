from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, MutableMapping

from .logger import Logger
from .project import Project
from .storyline import StorylineManager


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return text.strip()


def _clean_sequence(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, Iterable):  # type: ignore[unreachable]
        candidates = list(value)
    else:
        return []
    cleaned: List[str] = []
    for candidate in candidates:
        text = _clean_text(candidate)
        if text:
            cleaned.append(text)
    return cleaned


@dataclass
class PlayerTurnRecord:
    """Structured snapshot for a single player's experience of a turn."""

    turn: int
    action: str
    outcome: str
    global_summary: str
    reflection: str = ""
    candidate_actions: List[str] | None = None

    def to_dict(self) -> Dict[str, object]:
        data: Dict[str, object] = {
            "turn": self.turn,
            "action": self.action,
            "outcome": self.outcome,
            "global_summary": self.global_summary,
            "reflection": self.reflection,
        }
        if self.candidate_actions:
            data["candidate_actions"] = list(self.candidate_actions)
        else:
            data["candidate_actions"] = []
        return data


class TurnProcessor:
    """Persist the full lifecycle for a multiplayer storytelling turn."""

    def __init__(
        self,
        project: Project,
        storyline_manager: StorylineManager | None = None,
        logger: Logger | None = None,
    ) -> None:
        self.project = project
        self.storyline_manager = storyline_manager or StorylineManager(project)
        self.logger = logger

    # --- Public API -------------------------------------------------
    def process_turn(
        self,
        project_folder: str,
        player_actions: Mapping[str, str] | None,
        gm_summary: str,
        per_player_outcomes: Mapping[str, str] | None,
        player_reflections: Mapping[str, object] | None = None,
    ) -> Dict[str, object]:
        """Record the outcome of a turn across global and per-player storylines."""

        normalized_actions = self._normalize_mapping(player_actions)
        normalized_outcomes = self._normalize_mapping(per_player_outcomes)
        reflections = player_reflections or {}

        storyline_state = self.storyline_manager.load(project_folder)
        turns = self.storyline_manager.get_turns(storyline_state)
        turn_number = len(turns) + 1

        turn_entry: Dict[str, object] = {
            "turn": turn_number,
            "content": _clean_text(gm_summary),
            "origin": "gm",
            "player_actions": normalized_actions,
            "per_player_outcomes": normalized_outcomes,
        }

        turns.append(turn_entry)
        storyline_state = self.storyline_manager.update_turns(storyline_state, turns)
        self.storyline_manager.save(project_folder, storyline_state)

        impacted_players = set(normalized_actions) | set(normalized_outcomes) | set(reflections)
        for player in sorted(impacted_players):
            self._append_player_turn(
                project_folder,
                player,
                turn_number,
                gm_summary,
                normalized_actions.get(player, ""),
                normalized_outcomes.get(player, ""),
                reflections.get(player),
            )

        result: Dict[str, object] = {
            "turn": turn_number,
            "storyline_entry": turn_entry,
            "players": {
                player: self._load_player_state(project_folder, player)
                for player in impacted_players
            },
        }

        if self.logger:
            self.logger.log(
                "TurnProcessor: processed turn %s for players %s",
                turn_number,
                ", ".join(sorted(impacted_players)),
            )

        return result

    # --- Internal helpers ------------------------------------------
    def _normalize_mapping(
        self, values: Mapping[str, str] | None
    ) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        if not values:
            return normalized
        for key, value in values.items():
            cleaned_key = _clean_text(key)
            if not cleaned_key:
                continue
            normalized[cleaned_key] = _clean_text(value)
        return normalized

    def _append_player_turn(
        self,
        project_folder: str,
        player: str,
        turn_number: int,
        gm_summary: str,
        action: str,
        outcome: str,
        reflection_payload: object,
    ) -> None:
        path = self.project.character_path(project_folder, player)
        state = self._load_player_state(project_folder, player)

        reflection_text, candidate_actions = self._normalize_reflection(reflection_payload)

        record = PlayerTurnRecord(
            turn=turn_number,
            action=action,
            outcome=outcome,
            global_summary=_clean_text(gm_summary),
            reflection=reflection_text,
            candidate_actions=candidate_actions or None,
        )

        state_turns = state.setdefault("turns", [])
        if not isinstance(state_turns, list):
            state_turns = []
        state_turns.append(record.to_dict())
        state["turns"] = state_turns

        state.setdefault("name", player)
        state["last_turn"] = turn_number

        self.project.save_json(state, path)

    def _load_player_state(self, project_folder: str, player: str) -> Dict[str, object]:
        path = self.project.character_path(project_folder, player)
        try:
            data = self.project.read_json(path)
        except FileNotFoundError:
            data = {}
        except Exception:
            data = {}

        if not isinstance(data, MutableMapping):
            data = {}
        data = dict(data)
        data.setdefault("name", player)
        turns = data.get("turns")
        if not isinstance(turns, list):
            turns = []
        data["turns"] = turns
        if "last_turn" in data and not isinstance(data["last_turn"], int):
            try:
                data["last_turn"] = int(data["last_turn"])
            except Exception:
                data["last_turn"] = len(turns)
        else:
            data.setdefault("last_turn", len(turns))
        return data

    def _normalize_reflection(self, payload: object) -> tuple[str, List[str]]:
        if payload is None:
            return "", []

        if isinstance(payload, Mapping):
            notes_sources: List[str] = []
            for key in ("notes", "thoughts", "reflection"):
                if key in payload:
                    text = _clean_text(payload.get(key))
                    if text:
                        notes_sources.append(text)
            notes = "\n\n".join(notes_sources)
            candidates: List[str] = []
            for key in ("candidate_actions", "plans", "next_actions", "next_steps"):
                if key in payload:
                    candidates.extend(_clean_sequence(payload.get(key)))
            return notes, candidates

        if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            return "", _clean_sequence(payload)

        return _clean_text(payload), []

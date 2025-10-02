from __future__ import annotations

from pathlib import Path

from story_builder.project import Project, ProjectPaths
from story_builder.storyline import StorylineManager
from story_builder.story_writer import StoryWriter


class StubAutofill:
    def __init__(self):
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"Section {len(self.prompts)}"


def _make_project(tmp_path: Path) -> tuple[Project, StorylineManager, str]:
    paths = ProjectPaths()
    paths.projects_root = str(tmp_path)
    project = Project(paths)
    project_folder = tmp_path / "demo"
    project_folder.mkdir()
    project.save_json({"world": "Test world"}, project.story_path(str(project_folder)))
    return project, StorylineManager(project), str(project_folder)


def test_prepare_turn_summaries_includes_actions_and_outcomes():
    turns = [
        {
            "content": "The heroes confront the dragon in its lair.",
            "player_actions": {"Alyx": "Charges forward", "Bryn": "Casts ice"},
            "per_player_outcomes": {"Alyx": "Knocked back", "Bryn": "Spell fizzles"},
        }
    ]

    summaries = StoryWriter.prepare_turn_summaries(turns)

    assert len(summaries) == 1
    summary = summaries[0]
    assert "Turn 1" in summary
    assert "Alyx: Charges forward" in summary
    assert "Bryn: Spell fizzles" in summary


def test_generate_story_chunks_and_tracks_context(tmp_path: Path):
    project, manager, project_folder = _make_project(tmp_path)
    autofill = StubAutofill()
    writer = StoryWriter(
        project,
        manager,
        autofill,
        logger=None,
        max_chunk_chars=80,
        story_so_far_limit=40,
    )

    turns = [
        {"content": f"Beat {idx} description."} for idx in range(1, 7)
    ]

    story = writer.generate_story(project_folder, turns, stub_mode=False)

    # Multiple prompts should be issued because of the tight chunk limit
    assert len(autofill.prompts) >= 2
    assert story.strip()
    if len(autofill.prompts) == 2:
        assert story.strip() == "Section 1\n\nSection 2"

    # Later prompts should include the story-so-far excerpt marker
    for prompt in autofill.prompts[1:]:
        assert "Story so far (last 40 chars):" in prompt

import os
import shutil


def _make_paths(tmp_path):
    from story_builder.project import ProjectPaths

    paths = ProjectPaths()
    base = tmp_path / "turns"
    base.mkdir()
    paths.base_dir = str(base)
    paths.templates_dir = str(base / "json_templates")
    paths.projects_root = str(base / "json_projects")
    os.makedirs(paths.templates_dir, exist_ok=True)
    os.makedirs(paths.projects_root, exist_ok=True)

    repo_templates = os.path.join(os.path.dirname(os.path.dirname(__file__)), "json_templates")
    shutil.copy(os.path.join(repo_templates, "storyline_template.json"), paths.templates_dir)
    shutil.copy(os.path.join(repo_templates, "storyline_template_prompt.json"), paths.templates_dir)

    return paths


def test_turn_processor_writes_storyline_and_players(tmp_path):
    from story_builder.project import Project
    from story_builder.storyline import StorylineManager
    from story_builder.turn_processor import TurnProcessor

    paths = _make_paths(tmp_path)
    project = Project(paths)
    storyline = StorylineManager(project)
    processor = TurnProcessor(project, storyline)

    project_folder = os.path.join(paths.projects_root, "campaign")
    os.makedirs(project_folder, exist_ok=True)

    turn_result = processor.process_turn(
        project_folder,
        "The relic hums as Aria studies it while Bram keeps watch.",
        {"Aria": "Study the relic", "Bram": "Guard the door"},
        {
            "Aria": "She deciphers a hidden rune and gains new insight.",
            "Bram": "He spots approaching footsteps in time to warn the team.",
        },
        {
            "Aria": {
                "notes": "Need to cross-reference rune patterns.",
                "candidate_actions": ["Consult the archivist"],
            },
            "Bram": "Stay alert for the next watch.",
        },
    )

    assert turn_result["turn"] == 1

    storyline_path = project.storyline_path(project_folder)
    data = project.read_json(storyline_path)
    assert data["turns"][0]["content"].startswith("The relic hums")
    assert data["turns"][0]["player_actions"]["Aria"] == "Study the relic"
    assert data["turns"][0]["per_player_outcomes"]["Bram"].startswith("He spots")

    aria_file = project.character_path(project_folder, "Aria")
    aria = project.read_json(aria_file)
    assert aria["turns"][0]["global_summary"].startswith("The relic hums")
    assert aria["turns"][0]["action"] == "Study the relic"
    assert aria["turns"][0]["candidate_actions"] == ["Consult the archivist"]

    bram_file = project.character_path(project_folder, "Bram")
    bram = project.read_json(bram_file)
    assert bram["turns"][0]["reflection"] == "Stay alert for the next watch."
    assert bram["turns"][0]["candidate_actions"] == []

    processor.process_turn(
        project_folder,
        "The party advances carefully into the corridor.",
        {"Aria": "Lead the team toward the footsteps"},
        {"Bram": "He points out a tripwire before anyone triggers it."},
        {"Aria": {"thoughts": "Need backup soon.", "plans": "Find allies"}},
    )

    aria = project.read_json(aria_file)
    assert len(aria["turns"]) == 2
    assert aria["turns"][1]["turn"] == 2
    assert aria["turns"][1]["candidate_actions"] == ["Find allies"]

    bram = project.read_json(bram_file)
    assert len(bram["turns"]) == 2  # Second turn still records outcome even without action
    assert bram["turns"][1]["outcome"].startswith("He points out a tripwire")

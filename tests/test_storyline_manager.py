import os
import shutil

def _make_paths(tmp_path):
    from story_builder.project import ProjectPaths

    paths = ProjectPaths()
    base = tmp_path / "storyline"
    base.mkdir()
    paths.base_dir = str(base)
    paths.templates_dir = str(base / "json_templates")
    paths.projects_root = str(base / "json_projects")
    os.makedirs(paths.templates_dir, exist_ok=True)
    os.makedirs(paths.projects_root, exist_ok=True)

    repo_templates = os.path.join(os.path.dirname(os.path.dirname(__file__)), "json_templates")
    for name in ["storyline_template.json", "storyline_template_prompt.json"]:
        shutil.copy(os.path.join(repo_templates, name), paths.templates_dir)

    return paths


def test_storyline_manager_initializes_and_persists(tmp_path):
    from story_builder.project import Project
    from story_builder.storyline import StorylineManager

    paths = _make_paths(tmp_path)
    project = Project(paths)
    manager = StorylineManager(project)

    project_folder = os.path.join(paths.projects_root, "demo")
    os.makedirs(project_folder, exist_ok=True)

    data = manager.load(project_folder)
    assert data["turns"] == []

    turns = [{"content": "Opening scene", "origin": "user"}]
    state = manager.update_turns(data, turns)
    manager.save(project_folder, state)

    reloaded = manager.load(project_folder)
    assert reloaded["turns"][0]["content"] == "Opening scene"


def test_storyline_prompt_helpers(tmp_path):
    from story_builder.project import Project
    from story_builder.storyline import StorylineManager

    paths = _make_paths(tmp_path)
    project = Project(paths)
    manager = StorylineManager(project)
    manager.load_prompt_config()

    first_instruction = manager.instruction_for_turn(0)
    fallback_instruction = manager.instruction_for_turn(10)

    assert "hook" in first_instruction.lower()
    assert "storyline" in fallback_instruction.lower()

    project_folder = os.path.join(paths.projects_root, "demo")
    os.makedirs(project.characters_dir(project_folder), exist_ok=True)
    manager.ensure_initialized(project_folder)

    project.save_json(
        {"story_preferences": {"setting": "Sky city"}},
        project.story_path(project_folder),
    )
    project.save_json(
        {"name": "Aria", "role": "wizard"},
        project.character_path(project_folder, "aria"),
    )

    turns = [{"content": "The heroes arrive in the floating market."}]
    context = manager.build_prompt_context(project_folder, turns)

    combined = "\n".join(context.values())
    assert "sky city" in combined.lower()
    assert "aria" in combined.lower()
    assert "1." in combined

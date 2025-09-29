import os
import json
import shutil
import tempfile
import pytest

from story_builder.app import StoryBuilderApp
from story_builder.project import ProjectPaths
from story_builder.storyline import StorylineManager
from story_builder.turn_processor import TurnProcessor

# ------------------
# Helpers
# ------------------

class DummyVar:
    def __init__(self, val=False): self.val = val
    def get(self): return self.val

def make_app(tmpdir):
    """Return a StoryBuilderApp wired to use tmpdir as projects_root, with no real Tk."""
    paths = ProjectPaths()
    paths.projects_root = tmpdir
    app = StoryBuilderApp()
    app.paths = paths

    class DummyRoot: pass
    app.root = DummyRoot()
    app.stub_mode = DummyVar(False)
    app.full_edit_mode = DummyVar(False)
    app.debug_mode = DummyVar(False)

    from story_builder.logger import Logger
    from story_builder.autofill import AutofillService
    from story_builder.dialogs import DialogRunner
    from story_builder.editor import FieldWalker

    app.logger = Logger()
    app.autofill = AutofillService(app.stub_mode)
    app.dialog_runner = DialogRunner(app.root, app.autofill, app.logger)
    app.field_walker = FieldWalker(app.dialog_runner, app.full_edit_mode, app.logger)

    import story_builder.app as app_module
    app_module.messagebox.showinfo = lambda *a, **k: None

    return app

# ------------------
# Tests
# ------------------

def test_create_project():
    tmpdir = tempfile.mkdtemp()
    app = make_app(tmpdir)

    project_name = "test_project"
    folder = app.paths.project_folder(project_name)
    os.makedirs(app.project.characters_dir(folder), exist_ok=True)

    # Create a Story.json
    template = {"story_preferences": {"setting": ""}, "world_details": {}}
    app.project.save_json(template, app.project.story_path(folder))

    # Assertions
    assert os.path.isdir(folder)
    assert os.path.isdir(app.project.characters_dir(folder))
    assert os.path.isfile(app.project.story_path(folder))

    shutil.rmtree(tmpdir)


def test_edit_world_manual_and_autofill():
    tmpdir = tempfile.mkdtemp()
    app = make_app(tmpdir)
    folder = app.paths.project_folder("test_project")
    os.makedirs(app.project.characters_dir(folder), exist_ok=True)

    story_path = app.project.story_path(folder)
    template = {"story_preferences": {"setting": "", "tone": ""}}
    app.project.save_json(template, story_path)

    # First field returns "test", second field comes from stub autofill
    responses = iter(["test"])
    app.dialog_runner.ask_field = lambda *a, **k: next(responses, app.autofill.generate("tone"))
    app.autofill.generate = lambda prompt: "ABCD"

    app._edit_world(folder)

    with open(story_path, "r", encoding="utf-8") as f:
        story = json.load(f)

    assert story["story_preferences"]["setting"] == "test"
    assert story["story_preferences"]["tone"] == "ABCD"

    shutil.rmtree(tmpdir)


def test_create_character(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    app = make_app(tmpdir)
    folder = app.paths.project_folder("test_project")
    os.makedirs(app.project.characters_dir(folder), exist_ok=True)

    # Monkeypatch askstring to return test_character
    monkeypatch.setattr("story_builder.app.simpledialog.askstring", lambda *a, **k: "test_character")

    # Prevent GUI dialog during edit
    monkeypatch.setattr(app.dialog_runner, "ask_field", lambda *a, **k: "")

    app._create_character(folder)

    char_path = app.project.character_path(folder, "test_character")
    assert os.path.isfile(char_path)

    shutil.rmtree(tmpdir)


def test_edit_character_manual_and_autofill():
    tmpdir = tempfile.mkdtemp()
    app = make_app(tmpdir)
    folder = app.paths.project_folder("test_project")
    os.makedirs(app.project.characters_dir(folder), exist_ok=True)

    char_path = app.project.character_path(folder, "test_character")
    app.project.save_json({"name": "", "role": ""}, char_path)

    # First response = "heroic", then stub autofill
    responses = iter(["heroic"])
    app.dialog_runner.ask_field = lambda *a, **k: next(responses, app.autofill.generate("role"))
    app.autofill.generate = lambda prompt: "WXYZ"

    app._edit_character(folder, preselected="test_character")

    with open(char_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["name"] == "heroic" or data["role"] == "WXYZ"

    shutil.rmtree(tmpdir)


def test_autofill_storyline_turn():
    tmpdir = tempfile.mkdtemp()
    app = make_app(tmpdir)
    folder = app.paths.project_folder("test_project")
    os.makedirs(app.project.characters_dir(folder), exist_ok=True)

    # Create template files
    story_path = app.project.story_path(folder)
    app.project.save_json({"title": "", "summary": ""}, story_path)

    # Create characters
    app.project.save_json({}, app.project.character_path(folder, "Hero"))
    app.project.save_json({}, app.project.character_path(folder, "Villain"))

    app.storyline_manager = StorylineManager(app.project, app.logger)
    app.storyline_manager.ensure_initialized(folder)
    app.storyline_manager.load_prompt_config()
    app.turn_processor = TurnProcessor(app.project, app.storyline_manager, app.logger)

    app.storyline_state = app.storyline_manager.load(folder)
    app.storyline_turns = app.storyline_manager.get_turns(app.storyline_state)

    class DummyListbox:
        def delete(self, *args, **kwargs):
            pass

        def insert(self, *args, **kwargs):
            pass

        def selection_clear(self, *args, **kwargs):
            pass

        def selection_set(self, *args, **kwargs):
            pass

        def size(self):
            return 0

    app.storyline_listbox = DummyListbox()
    app.listbox = DummyListbox()

    responses = iter([
        "Hero action",
        "Villain action",
        "GM summary",
        "Hero outcome",
        "Hero reflection",
        "Villain outcome",
        "Villain reflection",
    ])
    app.autofill.generate = lambda prompt: next(responses)

    app._autofill_storyline_turn(folder)

    storyline_path = app.project.storyline_path(folder)
    with open(storyline_path, "r", encoding="utf-8") as f:
        storyline_data = json.load(f)

    assert len(storyline_data.get("turns", [])) == 1
    turn_entry = storyline_data["turns"][0]
    assert turn_entry["content"] == "GM summary"
    assert turn_entry["player_actions"]["Hero"] == "Hero action"
    assert turn_entry["per_player_outcomes"]["Villain"] == "Villain outcome"

    hero_path = app.project.character_path(folder, "Hero")
    with open(hero_path, "r", encoding="utf-8") as f:
        hero_data = json.load(f)

    assert hero_data["turns"][0]["action"] == "Hero action"
    assert hero_data["turns"][0]["reflection"] == "Hero reflection"

    shutil.rmtree(tmpdir)

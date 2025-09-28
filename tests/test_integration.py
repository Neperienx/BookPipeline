import os
import json
import shutil
import tempfile
import pytest

from story_builder.app import StoryBuilderApp
from story_builder.project import ProjectPaths

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

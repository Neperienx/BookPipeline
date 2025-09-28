import json
import tempfile
import os
from story_builder.project import ProjectPaths, Project

def test_clear_template_and_save_load():
    paths = ProjectPaths()
    project = Project(paths)

    template = {
        "story_preferences": {"setting": "fantasy", "themes": ["magic", "dark"]},
        "world_details": {"magic_level": "high"}
    }
    cleared = project.clear_template(template)
    assert cleared["story_preferences"]["setting"] == ""
    assert cleared["story_preferences"]["themes"] == []
    assert cleared["world_details"]["magic_level"] == ""

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "test.json")
        project.save_json(cleared, json_path)
        loaded = project.read_json(json_path)
        assert loaded == cleared

import json
from pathlib import Path

from story_builder.dialogs import DialogRunner
from story_builder.editor import FieldWalker
from story_builder.logger import Logger


class DummyVar:
    def __init__(self, val=False):
        self._val = val

    def get(self):
        return self._val


class CaptureDialog:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.exit_early = False
        self.calls = []

    def ask_field(self, title, key, suggestion, prompt_instruction=None, context=None):
        self.calls.append(
            {
                "title": title,
                "key": key,
                "suggestion": suggestion,
                "prompt_instruction": prompt_instruction,
                "context": context,
            }
        )
        try:
            return next(self.responses)
        except StopIteration:
            return suggestion or ""


def test_fieldwalker_includes_existing_context_for_autofill():
    data = json.loads(Path("tests/sample_data/story_example.json").read_text())
    prompts = {
        "story_preferences": {
            "tone": "Suggest a fitting tone (serious, lighthearted, grimdark, whimsical) for the story."
        }
    }

    dialog = CaptureDialog(responses=["Whimsical"])
    walker = FieldWalker(dialog, full_edit_mode_var=DummyVar(False), logger=Logger())
    walker.walk(data, prompts)

    tone_call = next(call for call in dialog.calls if call["key"] == "tone")
    assert tone_call["prompt_instruction"].startswith("Suggest a fitting tone")
    assert tone_call["context"] == {
        "setting": "A sprawling space station on the edge of a nebula",
        "themes": "Exploration, Political intrigue",
    }


def test_build_prompt_formats_context_and_instruction():
    context = {
        "setting": "A sprawling space station on the edge of a nebula",
        "themes": ["Exploration", "Political intrigue"],
    }

    prompt = DialogRunner.build_prompt(
        key="tone",
        current_value="",
        instruction="Suggest a fitting tone (serious, lighthearted, grimdark, whimsical) for the story.",
        context=context,
    )

    assert "You are a story writing assistant" in prompt
    assert "This is what I have so far:" in prompt
    assert "- Setting: A sprawling space station on the edge of a nebula" in prompt
    assert "- Themes: Exploration, Political intrigue" in prompt
    assert "Suggest a fitting tone" in prompt
    assert "For the Tone I currently have" not in prompt

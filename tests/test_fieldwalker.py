from story_builder.editor import FieldWalker
import copy

from story_builder.logger import Logger
from story_builder.utils import format_field_label

class DummyDialog:
    def __init__(self, responses, autofill=None):
        self.responses = iter(responses)
        self.exit_early = False
        self.captured = []
        self.autofill = autofill

    def ask_field(
        self,
        title,
        key,
        suggestion,
        prompt_instruction=None,
        context=None,
        prompt_spec=None,
    ):
        self.captured.append({
            "title": title,
            "key": key,
            "suggestion": suggestion,
            "prompt_instruction": prompt_instruction,
            "context": context,
            "prompt_spec": prompt_spec,
        })
        try:
            return next(self.responses)
        except StopIteration:
            return suggestion or ""

class DummyVar:
    def __init__(self, val): self._val = val
    def get(self): return self._val


class DummyAutofill:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, prompt_text: str, max_tokens=None):
        self.calls.append({"prompt": prompt_text, "max_tokens": max_tokens})
        try:
            return next(self.responses)
        except StopIteration:
            return ""

def test_fieldwalker_prompts_and_fills():
    dialog = DummyDialog(responses=["sci-fi", "epic"])
    logger = Logger()  # won’t print since no enabled_var
    walker = FieldWalker(dialog, full_edit_mode_var=DummyVar(False), logger=logger)

    data = {"story_preferences": {"setting": "", "scope": ""}}
    prompts = {"story_preferences": {"setting": "genre", "scope": "scale"}}
    filled = walker.walk(data, prompts)

    assert filled["story_preferences"]["setting"] == "sci-fi"
    assert filled["story_preferences"]["scope"] == "epic"

    assert dialog.captured[0]["prompt_instruction"] == "genre"
    assert dialog.captured[0]["context"] == {}

    scope_call = dialog.captured[1]
    assert scope_call["prompt_instruction"] == "scale"
    assert scope_call["context"] == {"setting": "sci-fi"}


def test_auto_generate_uses_autofill_and_context():
    autofill = DummyAutofill(responses=["Captain Lyra Voss", "Shade, The Whispering Gale"])
    dialog = DummyDialog(responses=[], autofill=autofill)
    logger = Logger()
    walker = FieldWalker(dialog, full_edit_mode_var=DummyVar(False), logger=logger)

    data = {
        "basic_information": {
            "name": "",
            "aliases": []
        }
    }
    prompts = {
        "basic_information": {
            "name": {"instruction": "Provide a distinctive full name.", "max_tokens": 32},
            "aliases": {"instruction": "List aliases, comma-separated."}
        }
    }

    story_context = {"setting": "A floating archipelago in a shattered sky"}
    steps = []

    def on_field(path, root):
        steps.append((list(path), copy.deepcopy(root)))

    walker.auto_generate(
        data,
        prompts,
        user_prompt="a daring skyship captain",
        story_context=story_context,
        on_field_filled=on_field,
    )

    assert data["basic_information"]["name"] == "Captain Lyra Voss"
    assert data["basic_information"]["aliases"] == ["Shade", "The Whispering Gale"]

    assert len(autofill.calls) == 2
    assert "Creative guidance from the user: a daring skyship captain." in autofill.calls[0]["prompt"]
    expected_path = f"{format_field_label('basic_information')} > {format_field_label('name')}"
    assert expected_path in autofill.calls[0]["prompt"]
    assert autofill.calls[0]["max_tokens"] == 32
    assert any(path == ["basic_information", "name"] for path, _ in steps)
    assert any(path == ["basic_information", "aliases"] for path, _ in steps)

from story_builder.editor import FieldWalker
from story_builder.logger import Logger

class DummyDialog:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.exit_early = False
    def ask_field(self, title, key, suggestion, prompt_text=None):
        try:
            return next(self.responses)
        except StopIteration:
            return suggestion or ""

class DummyVar:
    def __init__(self, val): self._val = val
    def get(self): return self._val

def test_fieldwalker_prompts_and_fills():
    dialog = DummyDialog(responses=["sci-fi", "epic"])
    logger = Logger()  # won’t print since no enabled_var
    walker = FieldWalker(dialog, full_edit_mode_var=DummyVar(False), logger=logger)

    data = {"story_preferences": {"setting": "", "scope": ""}}
    prompts = {"story_preferences": {"setting": "genre", "scope": "scale"}}
    filled = walker.walk(data, prompts)

    assert filled["story_preferences"]["setting"] == "sci-fi"
    assert filled["story_preferences"]["scope"] == "epic"

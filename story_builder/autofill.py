from __future__ import annotations
import random
import string
from typing import Optional


try:
    import src.text_generator as tg # your local GPT generator
except Exception:
    tg = None


class AutofillService:
    def __init__(self, stub_mode_var: Optional[object] = None, max_new_tokens: int = 50):
        self._stub_mode_var = stub_mode_var
        self.max_new_tokens = max_new_tokens


    def _stub_mode(self) -> bool:
        try:
            return bool(self._stub_mode_var.get()) if self._stub_mode_var is not None else False
        except Exception:
            return False


    def generate(self, prompt_text: str) -> str:
        if self._stub_mode():
            return "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if tg is None:
        # Fallback if text_generator isn't available
            return "".join(random.choices(string.ascii_lowercase, k=12))
        gen = tg.TextGenerator(max_new_tokens=self.max_new_tokens)
        out = gen.generate_text(prompt_text)
        return (out or "").strip()
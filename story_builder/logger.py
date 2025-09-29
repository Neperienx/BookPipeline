from __future__ import annotations
from typing import Optional

class Logger:
    """Lightweight logger that can be toggled via a tk.BooleanVar-like object."""

    def __init__(self, enabled_var: Optional[object] = None, log_file: Optional[str] = None):
        self._enabled_var = enabled_var
        self.log_file = log_file

    def enabled(self) -> bool:
        try:
            return bool(self._enabled_var.get()) if self._enabled_var is not None else False
        except Exception:
            return False

    def log(self, msg: str, *args, **kwargs) -> None:
        if not self.enabled():
            return
        if args:
            try:
                formatted = msg % args
            except Exception:
                formatted = str(msg)
        elif kwargs:
            try:
                formatted = msg % kwargs
            except Exception:
                formatted = str(msg)
        else:
            formatted = str(msg)
        print(formatted)
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(formatted + "\n")
            except Exception:
                pass

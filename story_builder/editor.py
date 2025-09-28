from __future__ import annotations
from typing import Any, Dict
from .dialogs import DialogRunner
from .logger import Logger


class FieldWalker:
    """Walks a nested dict of strings/lists, prompting the user for empty fields.
    Keeps filled values unless Full Edit Mode is enabled.
    """


    def __init__(self, dialog: DialogRunner, full_edit_mode_var, logger: Logger):
        self.dialog = dialog
        self.full_edit_mode_var = full_edit_mode_var
        self.logger = logger

    def _full_edit(self) -> bool:
        try:
            return bool(self.full_edit_mode_var.get())
        except Exception:
            return False
        


    def walk(self, data: Dict[str, Any], prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(prompt_data, dict):
            prompt_data = {}
        self.logger.log(f"FieldWalker.walk: start (full_edit={self._full_edit()})")
        self._walk_dict(data, prompt_data, title_key=None)
        return data
    
    def _walk_dict(self, data: Dict[str, Any], prompt_data: Dict[str, Any], title_key: str | None):
        for key, value in list(data.items()):
            if self.dialog.exit_early:
                self.logger.log("FieldWalker: exit_early flagged -> stop walking")
                return


            p = prompt_data.get(key, {}) if isinstance(prompt_data, dict) else {}


            if value is None:
                value = ""
                data[key] = value


            self.logger.log(f"FieldWalker: key={key!r}, type={type(value).__name__}")


            if isinstance(value, dict):
                self._walk_dict(value, p if isinstance(p, dict) else {}, title_key=key)
            elif isinstance(value, list):
                filled = self._prompt_list(key, value, p)
                data[key] = filled
            else:
                data[key] = self._prompt_string(key, str(value), p)


    def _prompt_string(self, key: str, value: str, p) -> str:
        if value.strip() == "" or self._full_edit():
            user_input = self.dialog.ask_field(self._title(key), key, value, prompt_text=p if isinstance(p, str) else "")
            self.logger.log(f"string filled -> {key} = {user_input!r}")
            return user_input or ""
        else:
            self.logger.log(f"string kept -> {key} = {value!r}")
            return value


    def _prompt_list(self, key: str, value_list: list, p) -> list:
        if not value_list or self._full_edit():
            placeholder = p if isinstance(p, str) else f"Enter values for {key}, comma-separated"
            user_input = self.dialog.ask_field(self._title(key), key, "", prompt_text=placeholder)
            new = [x.strip() for x in user_input.split(",") if x.strip()] if user_input else []
            self.logger.log(f"list fill -> {key} = {new}")
            return new
        
        new_list = []
        for idx, v in enumerate(value_list):
            if self.dialog.exit_early:
                break
            if v is None:
                v = ""
            if isinstance(v, str):
                if v.strip() == "":
                    user_input = self.dialog.ask_field(self._title(f"{key}[{idx}]"), f"{key}[{idx}]", v, prompt_text=p if isinstance(p, str) else "")
                    self.logger.log(f"list item filled -> {key}[{idx}] = {user_input!r}")
                    new_list.append(user_input or "")
                else:
                    new_list.append(v)
                    self.logger.log(f"list item kept -> {key}[{idx}] = {v!r}")
            elif isinstance(v, dict):
                # Recurse dict inside list
                self._walk_dict(v, p if isinstance(p, dict) else {}, title_key=f"{key}[{idx}]")
                new_list.append(v)
            else:
                user_input = self.dialog.ask_field(self._title(f"{key}[{idx}]"), f"{key}[{idx}]", str(v), prompt_text=p if isinstance(p, str) else "")
                new_list.append(user_input or "")
                return new_list


    @staticmethod
    def _title(key: str) -> str:
        return f"Edit: {key}"
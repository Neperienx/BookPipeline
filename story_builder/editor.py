from __future__ import annotations
import json
from typing import Any, Dict, List

from .dialogs import DialogRunner
from .logger import Logger
from .utils import format_field_label, summarize_value_for_prompt, PromptSpec


class FieldWalker:
    """Walks a nested dict of strings/lists, prompting the user for empty fields.
    Keeps filled values unless Full Edit Mode is enabled.
    """

    IMPORTANT_CONTEXT_KEYS = {"setting", "themes", "magic_level"}

    def __init__(self, dialog: DialogRunner, full_edit_mode_var, logger: Logger):
        self.dialog = dialog
        self.full_edit_mode_var = full_edit_mode_var
        self.logger = logger
        self._global_context: Dict[str, str] = {}

    def _full_edit(self) -> bool:
        try:
            return bool(self.full_edit_mode_var.get())
        except Exception:
            return False
        


    def walk(self, data: Dict[str, Any], prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(prompt_data, dict):
            prompt_data = {}
        self.logger.log(f"FieldWalker.walk: start (full_edit={self._full_edit()})")
        self._global_context = self._gather_global_context(data)
        self._walk_dict(data, prompt_data, title_key=None)
        return data

    def auto_generate(
        self,
        data: Dict[str, Any],
        prompt_data: Dict[str, Any],
        *,
        user_prompt: str = "",
        story_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Automatically populate every field using the Autofill service."""

        autofill = getattr(self.dialog, "autofill", None)
        if autofill is None:
            raise RuntimeError("Autofill service is required for auto generation")

        story_context = story_context or {}
        if not isinstance(prompt_data, dict):
            prompt_data = {}

        self.logger.log("FieldWalker.auto_generate: start")
        self._auto_fill_dict(
            data,
            prompt_data,
            path=[],
            root=data,
            autofill=autofill,
            user_prompt=user_prompt or "",
            story_context=story_context,
        )
        self.logger.log("FieldWalker.auto_generate: complete")
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
                filled = self._prompt_list(key, value, p, data)
                data[key] = filled
            else:
                data[key] = self._prompt_string(key, str(value), p, data)

    def _auto_fill_dict(
        self,
        node: Dict[str, Any],
        prompt_data: Dict[str, Any],
        *,
        path: List[str],
        root: Dict[str, Any],
        autofill,
        user_prompt: str,
        story_context: Dict[str, Any],
    ) -> None:
        for key, value in node.items():
            sub_prompt = prompt_data.get(key, {}) if isinstance(prompt_data, dict) else {}
            current_path = path + [key]

            if isinstance(value, dict):
                if not isinstance(sub_prompt, dict):
                    sub_prompt = {}
                self._auto_fill_dict(
                    value,
                    sub_prompt,
                    path=current_path,
                    root=root,
                    autofill=autofill,
                    user_prompt=user_prompt,
                    story_context=story_context,
                )
            elif isinstance(value, list):
                filled_list = self._auto_fill_list(
                    current_path,
                    value,
                    sub_prompt,
                    root,
                    autofill,
                    user_prompt,
                    story_context,
                )
                node[key] = filled_list
            else:
                node[key] = self._auto_fill_string(
                    current_path,
                    str(value),
                    sub_prompt,
                    root,
                    autofill,
                    user_prompt,
                    story_context,
                )


    def _prompt_string(self, key: str, value: str, p, container: Dict[str, Any]) -> str:
        spec = PromptSpec.from_config(p)
        if value.strip() == "" or self._full_edit():
            instruction = spec.instruction
            context = self._context_snapshot(container, exclude_key=key)
            user_input = self.dialog.ask_field(
                self._title(key),
                key,
                value,
                prompt_instruction=instruction,
                prompt_spec=spec,
                context=context,
            )
            self.logger.log(f"string filled -> {key} = {user_input!r}")
            return user_input or ""
        else:
            self.logger.log(f"string kept -> {key} = {value!r}")
            return value


    def _prompt_list(self, key: str, value_list: list, p, container: Dict[str, Any]) -> list:
        spec = PromptSpec.from_config(p)
        instruction = spec.instruction
        context = self._context_snapshot(container, exclude_key=key)
        if not value_list or self._full_edit():
            placeholder = instruction or f"Enter values for {format_field_label(key)}, comma-separated"
            user_input = self.dialog.ask_field(
                self._title(key),
                key,
                "",
                prompt_instruction=placeholder,
                prompt_spec=spec,
                context=context,
            )
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
                    item_context = self._list_item_context(key, context, value_list, idx)
                    user_input = self.dialog.ask_field(
                        self._title(f"{key}[{idx}]"),
                        f"{key}[{idx}]",
                        v,
                        prompt_instruction=instruction,
                        prompt_spec=spec,
                        context=item_context,
                    )
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
                item_context = self._list_item_context(key, context, value_list, idx)
                user_input = self.dialog.ask_field(
                    self._title(f"{key}[{idx}]"),
                    f"{key}[{idx}]",
                    str(v),
                    prompt_instruction=instruction,
                    prompt_spec=spec,
                    context=item_context,
                )
                new_list.append(user_input or "")
                return new_list

        return new_list

    def _auto_fill_string(
        self,
        path: List[str],
        value: str,
        prompt_config,
        root: Dict[str, Any],
        autofill,
        user_prompt: str,
        story_context: Dict[str, Any],
    ) -> str:
        spec = PromptSpec.from_config(prompt_config)
        prompt_text = self._build_auto_prompt(
            path,
            root,
            user_prompt=user_prompt,
            story_context=story_context,
            instruction=spec.instruction,
        )
        response = self._call_autofill(autofill, prompt_text, spec)
        filled = (response or value or "").strip()
        self.logger.log(f"auto fill string -> {'/'.join(path)} = {filled!r}")
        return filled

    def _auto_fill_list(
        self,
        path: List[str],
        value_list: list,
        prompt_config,
        root: Dict[str, Any],
        autofill,
        user_prompt: str,
        story_context: Dict[str, Any],
    ) -> list:
        spec = PromptSpec.from_config(prompt_config)
        prompt_text = self._build_auto_prompt(
            path,
            root,
            user_prompt=user_prompt,
            story_context=story_context,
            instruction=spec.instruction,
        )
        response = self._call_autofill(autofill, prompt_text, spec)
        parsed = self._parse_list_response(response)
        self.logger.log(f"auto fill list -> {'/'.join(path)} = {parsed}")
        return parsed

    def _call_autofill(self, autofill, prompt_text: str, spec: PromptSpec) -> str:
        max_tokens = spec.max_tokens
        try:
            if max_tokens is not None:
                return autofill.generate(prompt_text, max_tokens=max_tokens)
            return autofill.generate(prompt_text)
        except Exception as exc:  # pragma: no cover - safeguard against runtime errors
            self.logger.log(f"Autofill error for prompt: {exc}")
            return ""

    def _build_auto_prompt(
        self,
        path: List[str],
        root: Dict[str, Any],
        *,
        user_prompt: str,
        story_context: Dict[str, Any],
        instruction: str,
    ) -> str:
        category_label = self._path_label(path)
        baseline = user_prompt.strip()
        if not baseline:
            baseline = "No additional creative guidance was provided."
        existing_details = summarize_value_for_prompt(root).strip()
        if not existing_details:
            existing_details = "No details have been established yet."
        world_summary = summarize_value_for_prompt(story_context).strip()
        if not world_summary:
            world_summary = "No world-building information is currently available."

        lines = [
            f"The user wants to generate a character with this as a baseline {baseline}.",
            f"Those are the informations that we have so far: {existing_details}.",
            f"The character will be placed in a story with those premisses: {world_summary}.",
            f"Right now we want to fill out the information for this category: {category_label}.",
        ]

        instruction = (instruction or "").strip()
        if instruction:
            lines.append(instruction)
        lines.append("Come up with content to fill out just this field for this character.")

        return "\n".join(lines)

    def _parse_list_response(self, response: str) -> list:
        if not response:
            return []
        response = response.strip()
        try:
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass

        items: List[str] = []
        for raw in response.replace("\r", "\n").split("\n"):
            parts = [p.strip() for p in raw.split(",")]
            for part in parts:
                cleaned = part.strip().lstrip("-•*").strip()
                if cleaned:
                    items.append(cleaned)
        return items

    def _path_label(self, path: List[str]) -> str:
        if not path:
            return ""
        return " > ".join(format_field_label(p) for p in path)


    @staticmethod
    def _title(key: str) -> str:
        return f"Edit: {key}"

    def _context_snapshot(self, container: Dict[str, Any], exclude_key: str) -> Dict[str, str]:
        context: Dict[str, str] = {}
        for key, value in container.items():
            if key == exclude_key:
                continue
            summary = summarize_value_for_prompt(value)
            if summary:
                context[key] = summary
        for key, summary in self._global_context.items():
            if key == exclude_key:
                continue
            context.setdefault(key, summary)
        return context

    def _list_item_context(self, key: str, base_context: Dict[str, str], value_list: list, idx: int) -> Dict[str, str]:
        item_context = dict(base_context)
        existing = []
        for i, item in enumerate(value_list):
            if i == idx:
                continue
            summary = summarize_value_for_prompt(item)
            if summary:
                existing.append(summary)
        if existing:
            item_context[f"Other {format_field_label(key)} entries"] = ", ".join(existing)
        return item_context

    def _gather_global_context(self, data: Dict[str, Any]) -> Dict[str, str]:
        found: Dict[str, str] = {}

        def visit(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    key_lower = key.lower()
                    if key_lower in self.IMPORTANT_CONTEXT_KEYS:
                        summary = summarize_value_for_prompt(value)
                        if summary:
                            found[key_lower] = summary
                    visit(value)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(data)
        return found

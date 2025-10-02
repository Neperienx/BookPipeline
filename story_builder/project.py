from __future__ import annotations
import os
import json
from typing import Any, Dict
from tkinter import messagebox


class ProjectPaths:
    """Holds and prepares common paths (keeps original relative layout)."""


    def __init__(self):
        # Keep compatibility with your original two-levels-up layout
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = base_dir
        self.templates_dir = os.path.join(base_dir, "json_templates")
        self.projects_root = os.path.join(base_dir, "json_projects")
        os.makedirs(self.templates_dir, exist_ok=True)
        os.makedirs(self.projects_root, exist_ok=True)


    def project_folder(self, name: str) -> str:
        return os.path.join(self.projects_root, name)


class Project:
    def __init__(self, paths: ProjectPaths):
        self.paths = paths


    # --- JSON IO ---
    def save_json(self, data: Dict[str, Any], path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


    def read_json(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


# --- Templates ---
    def load_template(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.paths.templates_dir, filename)
        if not os.path.exists(path):
            messagebox.showerror("Missing Template", f"Template '{filename}' not found in {self.paths.templates_dir}.")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


    def load_prompt_template(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.paths.templates_dir, filename)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


    def clear_template(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self.clear_template(v) for k, v in data.items()}
        elif isinstance(data, list):
            return []
        elif isinstance(data, str):
            return ""
        else:
            return ""


    # --- Story paths ---
    def story_path(self, project_folder: str) -> str:
        return os.path.join(project_folder, "Story.json")


    def storyline_path(self, project_folder: str) -> str:
        return os.path.join(project_folder, "Storyline.json")

    def story_output_dir(self, project_folder: str) -> str:
        """Return the folder where compiled stories should be written."""

        directory = os.path.join(project_folder, "Stories")
        os.makedirs(directory, exist_ok=True)
        return directory


    # --- Characters ---
    def characters_dir(self, project_folder: str) -> str:
        d = os.path.join(project_folder, "Characters")
        os.makedirs(d, exist_ok=True)
        return d


    def character_path(self, project_folder: str, name: str) -> str:
        return os.path.join(self.characters_dir(project_folder), f"{name}.json")


    def list_characters(self, project_folder: str):
        d = self.characters_dir(project_folder)
        return [f[:-5] for f in os.listdir(d) if f.endswith(".json")]

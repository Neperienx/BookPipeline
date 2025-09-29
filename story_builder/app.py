from __future__ import annotations

import os
from typing import Any

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from .logger import Logger
from .autofill import AutofillService
from .dialogs import DialogRunner
from .editor import FieldWalker
from .project import ProjectPaths, Project
from .storyline import StorylineManager
from .utils import sanitize_project_name

class StoryBuilderApp:
    def __init__(self):
        self.paths = ProjectPaths()
        self.root: tk.Tk | None = None
        self.stub_mode = None
        self.full_edit_mode = None
        self.debug_mode = None
        self.logger: Logger | None = None
        self.autofill: AutofillService | None = None
        self.dialog_runner: DialogRunner | None = None
        self.field_walker: FieldWalker | None = None
        self.project = Project(self.paths)
        self.storyline_manager: StorylineManager | None = None
        self.storyline_state: dict[str, Any] = {}
        self.storyline_turns: list[dict[str, Any]] = []
        self.storyline_listbox: tk.Listbox | None = None

    # --- App lifecycle ---
    def run(self):
        # Initial chooser (modal, no main window yet)
        tmp = tk.Tk(); tmp.withdraw()
        choice = messagebox.askyesno("Story Builder", "Do you want to create a new project?\nYes = New, No = Open Existing")
        if choice:
            project_name = simpledialog.askstring("New Project", "Enter project name:")
            if not project_name:
                return
            project_name = sanitize_project_name(project_name)
            folder = self.paths.project_folder(project_name)
            os.makedirs(self.project.characters_dir(folder), exist_ok=True)
            template = self.project.load_template("story_template.json")
            cleared = self.project.clear_template(template)
            self.project.save_json(cleared, self.project.story_path(folder))
            messagebox.showinfo("Success", f"Project '{project_name}' created!")
            tmp.destroy()
            self.open_project(folder)
        else:
            folder = filedialog.askdirectory(initialdir=self.paths.projects_root, title="Select Project Folder")
            tmp.destroy()
            if folder:
                self.open_project(folder)

    def open_project(self, project_folder: str):
        # Main window
        self.root = tk.Tk()
        self.root.title(f"Project: {os.path.basename(project_folder)}")


        # Toggle vars
        self.stub_mode = tk.BooleanVar(value=False)
        self.full_edit_mode = tk.BooleanVar(value=False)
        self.debug_mode = tk.BooleanVar(value=False)


        # Services
        log_file = os.path.join(project_folder, "debug.log")
        self.logger = Logger(self.debug_mode, log_file)
        self.autofill = AutofillService(self.stub_mode)
        self.dialog_runner = DialogRunner(self.root, self.autofill, self.logger)
        self.field_walker = FieldWalker(self.dialog_runner, self.full_edit_mode, self.logger)
        self.storyline_manager = StorylineManager(self.project, self.logger)
        self.storyline_manager.load_prompt_config()
        self.storyline_manager.ensure_initialized(project_folder)
        self.storyline_state = {}
        self.storyline_turns = []


        # Notebook UI
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)


        # World tab
        frame_world = ttk.Frame(notebook)
        notebook.add(frame_world, text="World & Story")
        ttk.Button(frame_world, text="Edit World", command=lambda: self._edit_world(project_folder)).pack(padx=20, pady=20)


        # Characters tab
        frame_chars = ttk.Frame(notebook)
        notebook.add(frame_chars, text="Characters")


        self.listbox = tk.Listbox(frame_chars)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)


        btn_frame = tk.Frame(frame_chars)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)


        ttk.Button(btn_frame, text="New", command=lambda: [self._create_character(project_folder), self._refresh_character_list(project_folder)]).pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Edit", command=lambda: self._edit_character(project_folder)).pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Delete", command=lambda: self._delete_character(project_folder)).pack(fill=tk.X, pady=5)


        self._refresh_character_list(project_folder)


        # Storyline tab
        frame_storyline = ttk.Frame(notebook)
        notebook.add(frame_storyline, text="Write Storyline")


        self.storyline_listbox = tk.Listbox(frame_storyline)
        self.storyline_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)


        storyline_btns = ttk.Frame(frame_storyline)
        storyline_btns.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)


        ttk.Button(
            storyline_btns,
            text="Add Turn",
            command=lambda: self._add_storyline_turn(project_folder),
        ).pack(fill=tk.X, pady=5)


        ttk.Button(
            storyline_btns,
            text="Edit Turn",
            command=lambda: self._edit_storyline_turn(project_folder),
        ).pack(fill=tk.X, pady=5)


        ttk.Button(
            storyline_btns,
            text="Delete Turn",
            command=lambda: self._delete_storyline_turn(project_folder),
        ).pack(fill=tk.X, pady=5)


        ttk.Button(
            storyline_btns,
            text="Move Up",
            command=lambda: self._move_storyline_turn(project_folder, -1),
        ).pack(fill=tk.X, pady=5)


        ttk.Button(
            storyline_btns,
            text="Move Down",
            command=lambda: self._move_storyline_turn(project_folder, 1),
        ).pack(fill=tk.X, pady=5)


        self._load_storyline(project_folder)


        # Toggles row
        ttk.Checkbutton(self.root, text="Stub mode (fake Autofill)", variable=self.stub_mode).pack(pady=5)
        ttk.Checkbutton(self.root, text="Full Edit Mode (prompt all fields)", variable=self.full_edit_mode).pack(pady=5)
        ttk.Checkbutton(self.root, text="Debug logging (writes debug.log)", variable=self.debug_mode).pack(pady=5)


        self.root.mainloop()

    # --- World ---
    def _edit_world(self, project_folder: str):
        self.dialog_runner.exit_early = False # reset per session
        story_path = self.project.story_path(project_folder)
        if not os.path.exists(story_path):
            template = self.project.load_template("story_template.json")
            cleared = self.project.clear_template(template)
            self.project.save_json(cleared, story_path)
            self.logger.log("_edit_world: created Story.json from template")


        data = self.project.read_json(story_path)
        prompts = self.project.load_prompt_template("story_template_prompt.json")
        updated = self.field_walker.walk(data, prompts)
        self.project.save_json(updated, story_path)
        self.logger.log("_edit_world: saved")
        messagebox.showinfo("Saved", f"World for '{os.path.basename(project_folder)}' updated!")


    def _selected_character(self) -> str | None:
        if not self.listbox.curselection():
            return None
        return self.listbox.get(tk.ACTIVE)


    def _refresh_character_list(self, project_folder: str):
        self.listbox.delete(0, tk.END)
        for name in self.project.list_characters(project_folder):
            self.listbox.insert(tk.END, name)


    def _create_character(self, project_folder: str):
        name = simpledialog.askstring("New Character", "Enter character name:")
        if not name:
            return
        char_path = self.project.character_path(project_folder, name)
        if not os.path.exists(char_path):
            template = self.project.load_template("character_template.json")
            cleared = self.project.clear_template(template)
            self.project.save_json(cleared, char_path)


        self._edit_character(project_folder, preselected=name)


    def _edit_character(self, project_folder: str, preselected: str | None = None):
        name = preselected or self._selected_character()
        if not name:
            return
        self.dialog_runner.exit_early = False # reset per session


        char_path = self.project.character_path(project_folder, name)
        if not os.path.exists(char_path):
            template = self.project.load_template("character_template.json")
            cleared = self.project.clear_template(template)
            self.project.save_json(cleared, char_path)
            self.logger.log("_edit_character: created character from template")


        data = self.project.read_json(char_path)
        prompts = self.project.load_prompt_template("character_template_prompt.json")
        updated = self.field_walker.walk(data, prompts)
        self.project.save_json(updated, char_path)
        self.logger.log("_edit_character: saved")
        messagebox.showinfo("Saved", f"Character '{name}' updated!")


    def _delete_character(self, project_folder: str):
        name = self._selected_character()
        if not name:
            return
        path = self.project.character_path(project_folder, name)
        if os.path.exists(path):
            os.remove(path)
            messagebox.showinfo("Deleted", f"Character '{name}' removed!")
            self._refresh_character_list(project_folder)


    # --- Storyline ---
    def _load_storyline(self, project_folder: str):
        if not self.storyline_manager:
            return
        self.storyline_state = self.storyline_manager.load(project_folder)
        self.storyline_turns = self.storyline_manager.get_turns(self.storyline_state)
        self._refresh_storyline_list()


    def _refresh_storyline_list(self):
        if not self.storyline_listbox:
            return
        self.storyline_listbox.delete(0, tk.END)
        if not self.storyline_manager:
            return
        for idx, turn in enumerate(self.storyline_turns):
            label = self.storyline_manager.turn_label(turn, idx)
            self.storyline_listbox.insert(tk.END, label)


    def _selected_storyline_index(self) -> int | None:
        if not self.storyline_listbox:
            return None
        selection = self.storyline_listbox.curselection()
        if not selection:
            return None
        return int(selection[0])


    def _persist_storyline(self, project_folder: str):
        if not self.storyline_manager:
            return
        self.storyline_state = self.storyline_manager.update_turns(
            self.storyline_state,
            self.storyline_turns,
        )
        self.storyline_manager.save(project_folder, self.storyline_state)
        if self.logger:
            self.logger.log(f"storyline saved with {len(self.storyline_turns)} turns")


    def _add_storyline_turn(self, project_folder: str):
        if not self.storyline_manager or not self.dialog_runner:
            return
        index = len(self.storyline_turns)
        instruction = self.storyline_manager.instruction_for_turn(index)
        context = self.storyline_manager.build_prompt_context(project_folder, self.storyline_turns)
        value = self.dialog_runner.ask_field(
            title=f"Storyline Turn {index + 1}",
            key=f"turn_{index + 1}",
            suggestion="",
            prompt_instruction=instruction,
            context=context,
        )
        value = value.strip()
        if value == "":
            return
        self.storyline_turns.append({"content": value, "origin": "user"})
        self._persist_storyline(project_folder)
        self._refresh_storyline_list()
        if self.storyline_listbox:
            self.storyline_listbox.selection_clear(0, tk.END)
            last_index = self.storyline_listbox.size() - 1
            if last_index >= 0:
                self.storyline_listbox.selection_set(last_index)
        if self.logger:
            self.logger.log(f"storyline turn {index + 1} added")


    def _edit_storyline_turn(self, project_folder: str):
        if not self.storyline_manager or not self.dialog_runner:
            return
        index = self._selected_storyline_index()
        if index is None or index >= len(self.storyline_turns):
            return
        current = self.storyline_turns[index]
        instruction = self.storyline_manager.instruction_for_turn(index)
        context = self.storyline_manager.build_prompt_context(project_folder, self.storyline_turns)
        updated = self.dialog_runner.ask_field(
            title=f"Edit Storyline Turn {index + 1}",
            key=f"turn_{index + 1}",
            suggestion=current.get("content", ""),
            prompt_instruction=instruction,
            context=context,
        )
        self.storyline_turns[index]["content"] = updated.strip()
        self._persist_storyline(project_folder)
        self._refresh_storyline_list()
        if self.storyline_listbox and index < self.storyline_listbox.size():
            self.storyline_listbox.selection_clear(0, tk.END)
            self.storyline_listbox.selection_set(index)
        if self.logger:
            self.logger.log(f"storyline turn {index + 1} edited")


    def _delete_storyline_turn(self, project_folder: str):
        index = self._selected_storyline_index()
        if index is None or index >= len(self.storyline_turns):
            return
        del self.storyline_turns[index]
        self._persist_storyline(project_folder)
        self._refresh_storyline_list()
        if self.storyline_listbox:
            size = self.storyline_listbox.size()
            if size:
                new_index = min(index, size - 1)
                self.storyline_listbox.selection_clear(0, tk.END)
                self.storyline_listbox.selection_set(new_index)
        if self.logger:
            self.logger.log(f"storyline turn {index + 1} deleted")


    def _move_storyline_turn(self, project_folder: str, delta: int):
        if not self.storyline_turns:
            return
        index = self._selected_storyline_index()
        if index is None:
            return
        new_index = index + delta
        if new_index < 0 or new_index >= len(self.storyline_turns):
            return
        self.storyline_turns[index], self.storyline_turns[new_index] = (
            self.storyline_turns[new_index],
            self.storyline_turns[index],
        )
        self._persist_storyline(project_folder)
        self._refresh_storyline_list()
        if self.storyline_listbox and new_index < self.storyline_listbox.size():
            self.storyline_listbox.selection_clear(0, tk.END)
            self.storyline_listbox.selection_set(new_index)
        if self.logger:
            self.logger.log(
                f"storyline turn moved from {index + 1} to {new_index + 1}"
            )

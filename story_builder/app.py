from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from .logger import Logger
from .autofill import AutofillService
from .dialogs import DialogRunner
from .editor import FieldWalker
from .project import ProjectPaths, Project
from .storyline import StorylineManager
from .turn_processor import TurnProcessor
from .utils import sanitize_project_name
from .story_writer import StoryWriter

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
        self.turn_processor: TurnProcessor | None = None
        self.storyline_state: dict[str, Any] = {}
        self.storyline_turns: list[dict[str, Any]] = []
        self.storyline_listbox: tk.Listbox | None = None
        self.story_folder_var: tk.StringVar | None = None
        self.story_folder_display_var: tk.StringVar | None = None

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
        self.turn_processor = TurnProcessor(self.project, self.storyline_manager, self.logger)
        self.storyline_state = {}
        self.storyline_turns = []
        self.story_folder_var = tk.StringVar(value="")
        self.story_folder_display_var = tk.StringVar(value="(not set)")
        self.project.story_output_dir(project_folder)


        # Notebook UI
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)


        # World tab
        frame_world = ttk.Frame(notebook)
        notebook.add(frame_world, text="World & Story")
        ttk.Button(
            frame_world,
            text="Edit World",
            command=lambda: self._edit_world(project_folder),
        ).pack(padx=20, pady=(20, 10))
        ttk.Button(
            frame_world,
            text="Autofill World",
            command=lambda: self._autofill_world(project_folder),
        ).pack(padx=20, pady=(0, 20))


        # Characters tab
        frame_chars = ttk.Frame(notebook)
        notebook.add(frame_chars, text="Characters")


        self.listbox = tk.Listbox(frame_chars)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)


        btn_frame = tk.Frame(frame_chars)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)


        ttk.Button(btn_frame, text="New", command=lambda: [self._create_character(project_folder), self._refresh_character_list(project_folder)]).pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Autogenerate", command=lambda: self._autogenerate_character(project_folder)).pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Edit", command=lambda: self._edit_character(project_folder)).pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Delete", command=lambda: self._delete_character(project_folder)).pack(fill=tk.X, pady=5)


        self._refresh_character_list(project_folder)


        # Storyline tab
        frame_storyline = ttk.Frame(notebook)
        notebook.add(frame_storyline, text="Write Storyline")


        storyline_content = ttk.Frame(frame_storyline)
        storyline_content.pack(fill=tk.BOTH, expand=True)


        self.storyline_listbox = tk.Listbox(storyline_content)
        self.storyline_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)


        storyline_btns = ttk.Frame(storyline_content)
        storyline_btns.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)


        ttk.Button(
            storyline_btns,
            text="Add Turn",
            command=lambda: self._add_storyline_turn(project_folder),
        ).pack(fill=tk.X, pady=5)


        ttk.Button(
            storyline_btns,
            text="Autofill Turn",
            command=lambda: self._autofill_storyline_turn(project_folder),
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

        ttk.Separator(storyline_btns, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        ttk.Button(
            storyline_btns,
            text="New Story Folder",
            command=lambda: self._create_story_folder(project_folder),
        ).pack(fill=tk.X, pady=5)

        ttk.Button(
            storyline_btns,
            text="Select Story Folder",
            command=lambda: self._select_story_folder(project_folder),
        ).pack(fill=tk.X, pady=5)

        ttk.Button(
            storyline_btns,
            text="Write Story",
            command=lambda: self._write_story(project_folder),
        ).pack(fill=tk.X, pady=5)

        story_folder_frame = ttk.Frame(frame_storyline)
        story_folder_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Label(story_folder_frame, text="Story folder:").pack(side=tk.LEFT)
        ttk.Label(
            story_folder_frame,
            textvariable=self.story_folder_display_var,
        ).pack(side=tk.LEFT, padx=5)


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


    def _autofill_world(self, project_folder: str):
        if not self.field_walker or not self.autofill:
            return

        story_path = self.project.story_path(project_folder)
        if not os.path.exists(story_path):
            template = self.project.load_template("story_template.json")
            cleared = self.project.clear_template(template)
            self.project.save_json(cleared, story_path)
            if self.logger:
                self.logger.log("_autofill_world: created Story.json from template")

        data = self.project.read_json(story_path)
        prompts = self.project.load_prompt_template("story_template_prompt.json")

        user_prompt = simpledialog.askstring(
            "World Autofill",
            "Provide creative guidance for the world (optional):",
        )
        if user_prompt is None:
            return

        def save_partial(path: list[str], root_data: dict[str, Any]) -> None:
            try:
                self.project.save_json(root_data, story_path)
            except Exception as exc:  # pragma: no cover - defensive save guard
                if self.logger:
                    self.logger.log("_autofill_world: incremental save failed: %s", exc)

        self.field_walker.auto_generate(
            data,
            prompts,
            user_prompt=user_prompt or "",
            story_context={},
            on_field_filled=save_partial,
        )
        self.project.save_json(data, story_path)
        if self.logger:
            self.logger.log("_autofill_world: completed and saved")
        messagebox.showinfo(
            "Saved",
            f"World for '{os.path.basename(project_folder)}' auto-filled!",
        )


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


    def _autogenerate_character(self, project_folder: str):
        if not self.field_walker:
            return
        name = simpledialog.askstring("Autogenerate Character", "Enter character name:")
        if not name:
            return

        char_path = self.project.character_path(project_folder, name)
        if os.path.exists(char_path):
            overwrite = messagebox.askyesno(
                "Overwrite Character",
                f"A character named '{name}' already exists. Overwrite with a new auto-generated profile?",
            )
            if not overwrite:
                return

        template = self.project.load_template("character_template.json")
        cleared = self.project.clear_template(template)
        self.project.save_json(cleared, char_path)

        prompt = simpledialog.askstring(
            "Character Prompt",
            "Provide a short prompt to guide generation (optional):",
        )
        if prompt is None:
            return

        story_context = {}
        story_path = self.project.story_path(project_folder)
        if os.path.exists(story_path):
            try:
                story_context = self.project.read_json(story_path)
            except Exception:
                story_context = {}

        data = self.project.read_json(char_path)
        prompts = self.project.load_prompt_template("character_template_prompt.json")

        def save_partial(path: list[str], root_data: dict[str, Any]) -> None:
            try:
                self.project.save_json(root_data, char_path)
            except Exception as exc:  # pragma: no cover - defensive save guard
                if self.logger:
                    self.logger.log("_autogenerate_character: incremental save failed: %s", exc)

        self.field_walker.auto_generate(
            data,
            prompts,
            user_prompt=prompt or "",
            story_context=story_context,
            on_field_filled=save_partial,
        )
        self.project.save_json(data, char_path)
        if self.logger:
            self.logger.log("_autogenerate_character: saved")

        self._refresh_character_list(project_folder)
        if self.listbox is not None:
            names = self.listbox.get(0, tk.END)
            try:
                index = names.index(name)
            except ValueError:
                index = None
            if index is not None:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(index)
                self.listbox.activate(index)

        messagebox.showinfo("Generated", f"Character '{name}' generated!")


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
        if self.story_folder_var:
            raw_folder = str(self.storyline_state.get("story_folder", "") or "")
            self.story_folder_var.set(raw_folder)
            self._update_story_folder_display(project_folder)
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
        self._apply_story_folder_to_state()
        self.storyline_manager.save(project_folder, self.storyline_state)
        if self.logger:
            self.logger.log(f"storyline saved with {len(self.storyline_turns)} turns")


    def _apply_story_folder_to_state(self):
        if self.story_folder_var is None:
            return
        folder_value = self.story_folder_var.get().strip()
        if folder_value:
            self.storyline_state["story_folder"] = folder_value
        else:
            self.storyline_state.pop("story_folder", None)


    def _update_story_folder_display(self, project_folder: str):
        if not self.story_folder_var or not self.story_folder_display_var:
            return
        raw_value = self.story_folder_var.get().strip()
        if not raw_value:
            self.story_folder_display_var.set("(not set)")
            return
        if os.path.isabs(raw_value):
            display = raw_value
        else:
            display = raw_value
        self.story_folder_display_var.set(display)


    def _get_story_folder_path(self, project_folder: str) -> str:
        if not self.story_folder_var:
            return ""
        raw_value = self.story_folder_var.get().strip()
        if not raw_value:
            return ""
        if os.path.isabs(raw_value):
            return raw_value
        return os.path.join(project_folder, raw_value)


    def _create_story_folder(self, project_folder: str):
        base_dir = self.project.story_output_dir(project_folder)
        folder_name = simpledialog.askstring(
            "New Story Folder", "Enter a name for the story folder:", parent=self.root
        )
        if not folder_name:
            return
        sanitized = sanitize_project_name(folder_name)
        if not sanitized:
            messagebox.showerror("Invalid Name", "Please provide a valid folder name.")
            return
        path = os.path.join(base_dir, sanitized)
        os.makedirs(path, exist_ok=True)
        relative_path = os.path.relpath(path, project_folder)
        if self.story_folder_var:
            self.story_folder_var.set(relative_path)
            self._apply_story_folder_to_state()
            self._update_story_folder_display(project_folder)
            if self.storyline_manager:
                self.storyline_manager.save(project_folder, self.storyline_state)
        messagebox.showinfo("Story Folder", f"Story folder ready at {relative_path}.")


    def _select_story_folder(self, project_folder: str):
        initial = self.project.story_output_dir(project_folder)
        selected = filedialog.askdirectory(
            title="Select Story Folder", initialdir=initial, mustexist=False
        )
        if not selected:
            return
        os.makedirs(selected, exist_ok=True)
        try:
            relative = os.path.relpath(selected, project_folder)
        except ValueError:
            relative = selected
        if relative.startswith(".."):
            value = selected
        else:
            value = relative
        if self.story_folder_var:
            self.story_folder_var.set(value)
            self._apply_story_folder_to_state()
            self._update_story_folder_display(project_folder)
            if self.storyline_manager:
                self.storyline_manager.save(project_folder, self.storyline_state)


    def _write_story(self, project_folder: str):
        if not self.storyline_manager:
            return
        folder_path = self._get_story_folder_path(project_folder)
        if not folder_path:
            messagebox.showwarning(
                "Story Folder Required",
                "Please create or select a story folder before writing the story.",
            )
            return
        if not self.storyline_turns:
            messagebox.showinfo("No Storyline", "Add storyline turns before writing a story.")
            return
        writer = StoryWriter(
            self.project,
            self.storyline_manager,
            self.autofill,
            self.logger,
        )
        stub_mode_enabled = False
        try:
            stub_mode_enabled = bool(self.stub_mode.get()) if self.stub_mode else False
        except Exception:
            stub_mode_enabled = False
        try:
            story_text = writer.generate_story(
                project_folder,
                self.storyline_turns,
                stub_mode=stub_mode_enabled,
            )
        except Exception as exc:  # pragma: no cover - defensive
            if self.logger:
                self.logger.log("Failed to generate story: %s", exc)
            messagebox.showerror(
                "Generation Failed",
                "An error occurred while generating the story. See logs for details.",
            )
            return
        if not story_text.strip():
            messagebox.showwarning(
                "Empty Story",
                "The generated story was empty. Please review your storyline and try again.",
            )
            return

        os.makedirs(folder_path, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"story_{timestamp}.txt"
        output_path = os.path.join(folder_path, filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(story_text.strip() + "\n")
        messagebox.showinfo("Story Saved", f"Story saved to {output_path}.")


    def _add_storyline_turn(self, project_folder: str):
        if (
            not self.storyline_manager
            or not self.dialog_runner
            or not self.turn_processor
        ):
            return
        self.dialog_runner.exit_early = False
        index = len(self.storyline_turns)
        instruction_spec = self.storyline_manager.instruction_for_turn(index)
        instruction = instruction_spec.instruction
        base_context = self.storyline_manager.build_prompt_context(
            project_folder, self.storyline_turns
        )

        player_actions: dict[str, str] = {}
        per_player_outcomes: dict[str, str] = {}
        player_reflections: dict[str, str] = {}

        players = sorted(set(self.project.list_characters(project_folder)))
        for player in players:
            action_context = dict(base_context)
            action_context.update({
                "player": player,
                "declared_actions": dict(player_actions),
            })
            action = self.dialog_runner.ask_field(
                title=f"{player} Action",
                key=f"{player}_action_turn_{index + 1}",
                suggestion="",
                prompt_instruction=(
                    f"Describe what {player} attempted during this turn."
                ),
                context=action_context,
            ).strip()
            if self.dialog_runner.exit_early:
                self.dialog_runner.exit_early = False
                return
            if action:
                player_actions[player] = action

        gm_context = dict(base_context)
        if player_actions:
            gm_context["player_actions"] = dict(player_actions)

        gm_summary = self.dialog_runner.ask_field(
            title=f"Storyline Turn {index + 1}",
            key=f"turn_{index + 1}",
            suggestion="",
            prompt_instruction=instruction,
            context=gm_context,
            prompt_spec=instruction_spec,
        )
        if self.dialog_runner.exit_early:
            self.dialog_runner.exit_early = False
            return
        gm_summary = gm_summary.strip()
        if gm_summary == "":
            return

        for player in players:
            action = player_actions.get(player, "")

            outcome_context = dict(base_context)
            outcome_context.update({
                "gm_summary": gm_summary,
                "player": player,
                "player_action": action,
                "player_actions": dict(player_actions),
            })

            outcome = self.dialog_runner.ask_field(
                title=f"{player} Outcome",
                key=f"{player}_outcome_turn_{index + 1}",
                suggestion="",
                prompt_instruction=(
                    f"Summarize the consequences for {player} this turn."
                ),
                context=outcome_context,
            ).strip()
            if self.dialog_runner.exit_early:
                self.dialog_runner.exit_early = False
                return
            if outcome:
                per_player_outcomes[player] = outcome

            reflection_context = dict(outcome_context)
            reflection_context.update({
                "player_outcome": outcome,
            })

            reflection = self.dialog_runner.ask_field(
                title=f"{player} Reflection",
                key=f"{player}_reflection_turn_{index + 1}",
                suggestion="",
                prompt_instruction=(
                    f"Capture {player}'s thoughts, plans, or next steps."
                ),
                context=reflection_context,
            ).strip()
            if self.dialog_runner.exit_early:
                self.dialog_runner.exit_early = False
                return
            if reflection:
                player_reflections[player] = reflection

        turn_result = self.turn_processor.process_turn(
            project_folder,
            gm_summary,
            player_actions or None,
            per_player_outcomes or None,
            player_reflections or None,
        )

        storyline_entry = turn_result.get("storyline_entry")
        if storyline_entry:
            self.storyline_turns.append(storyline_entry)
        self.storyline_state = self.storyline_manager.update_turns(
            self.storyline_state,
            self.storyline_turns,
        )
        self._refresh_storyline_list()
        if self.storyline_listbox:
            self.storyline_listbox.selection_clear(0, tk.END)
            last_index = self.storyline_listbox.size() - 1
            if last_index >= 0:
                self.storyline_listbox.selection_set(last_index)
        self._refresh_character_list(project_folder)
        if self.logger:
            impacted = ", ".join(sorted((turn_result.get("players") or {}).keys()))
            self.logger.log(
                "storyline turn %s added (players: %s)",
                index + 1,
                impacted or "none",
            )


    def _autofill_storyline_turn(self, project_folder: str):
        if (
            not self.storyline_manager
            or not self.turn_processor
            or not self.dialog_runner
            or not self.autofill
        ):
            return

        index = len(self.storyline_turns)
        instruction_spec = self.storyline_manager.instruction_for_turn(index)
        instruction = instruction_spec.instruction
        base_context = self.storyline_manager.build_prompt_context(
            project_folder, self.storyline_turns
        )

        players = sorted(set(self.project.list_characters(project_folder)))

        player_actions: dict[str, str] = {}
        per_player_outcomes: dict[str, str] = {}
        player_reflections: dict[str, str] = {}

        for player in players:
            action_context = dict(base_context)
            action_context.update(
                {
                    "player": player,
                    "declared_actions": dict(player_actions),
                }
            )
            prompt = self.dialog_runner.build_prompt(
                key=f"{player}_action_turn_{index + 1}",
                current_value="",
                instruction=f"Describe what {player} attempted during this turn.",
                context=action_context,
            )
            action = self.autofill.generate(prompt).strip()
            if action:
                player_actions[player] = action

        gm_context = dict(base_context)
        if player_actions:
            gm_context["player_actions"] = dict(player_actions)

        gm_prompt = self.dialog_runner.build_prompt(
            key=f"turn_{index + 1}",
            current_value="",
            instruction=instruction,
            context=gm_context,
        )
        if instruction_spec.max_tokens is not None:
            gm_summary = self.autofill.generate(
                gm_prompt, max_tokens=instruction_spec.max_tokens
            ).strip()
        else:
            gm_summary = self.autofill.generate(gm_prompt).strip()
        if not gm_summary:
            return

        for player in players:
            action = player_actions.get(player, "")
            outcome_context = dict(base_context)
            outcome_context.update(
                {
                    "gm_summary": gm_summary,
                    "player": player,
                    "player_action": action,
                    "player_actions": dict(player_actions),
                }
            )
            outcome_prompt = self.dialog_runner.build_prompt(
                key=f"{player}_outcome_turn_{index + 1}",
                current_value="",
                instruction=f"Summarize the consequences for {player} this turn.",
                context=outcome_context,
            )
            outcome = self.autofill.generate(outcome_prompt).strip()
            if outcome:
                per_player_outcomes[player] = outcome

            reflection_context = dict(outcome_context)
            reflection_context.update({"player_outcome": outcome})

            reflection_prompt = self.dialog_runner.build_prompt(
                key=f"{player}_reflection_turn_{index + 1}",
                current_value="",
                instruction=f"Capture {player}'s thoughts, plans, or next steps.",
                context=reflection_context,
            )
            reflection = self.autofill.generate(reflection_prompt).strip()
            if reflection:
                player_reflections[player] = reflection

        turn_result = self.turn_processor.process_turn(
            project_folder,
            gm_summary,
            player_actions or None,
            per_player_outcomes or None,
            player_reflections or None,
        )

        storyline_entry = turn_result.get("storyline_entry")
        if isinstance(storyline_entry, dict):
            self.storyline_turns.append(storyline_entry)
            self.storyline_state = self.storyline_manager.update_turns(
                self.storyline_state,
                self.storyline_turns,
            )
            self._refresh_storyline_list()
            if self.storyline_listbox:
                self.storyline_listbox.selection_clear(0, tk.END)
                last_index = self.storyline_listbox.size() - 1
                if last_index >= 0:
                    self.storyline_listbox.selection_set(last_index)

        self._refresh_character_list(project_folder)

        if self.logger:
            impacted = ", ".join(sorted((turn_result.get("players") or {}).keys()))
            self.logger.log(
                "storyline turn %s autofilled (players: %s)",
                index + 1,
                impacted or "none",
            )


    def _edit_storyline_turn(self, project_folder: str):
        if not self.storyline_manager or not self.dialog_runner:
            return
        index = self._selected_storyline_index()
        if index is None or index >= len(self.storyline_turns):
            return
        current = self.storyline_turns[index]
        instruction_spec = self.storyline_manager.instruction_for_turn(index)
        instruction = instruction_spec.instruction
        context = self.storyline_manager.build_prompt_context(project_folder, self.storyline_turns)
        updated = self.dialog_runner.ask_field(
            title=f"Edit Storyline Turn {index + 1}",
            key=f"turn_{index + 1}",
            suggestion=current.get("content", ""),
            prompt_instruction=instruction,
            context=context,
            prompt_spec=instruction_spec,
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

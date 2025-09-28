from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from typing import Optional
from .autofill import AutofillService
from .logger import Logger


class DialogRunner:
    def __init__(self, root: tk.Tk, autofill: AutofillService, logger: Logger):
        self.root = root
        self.autofill = autofill
        self.logger = logger
        self.exit_early = False


    def ask_field(self, title: str, key: str, suggestion: Optional[str], prompt_text: Optional[str] = None) -> str:
        if suggestion is None:
            suggestion = ""


        dialog = tk.Toplevel(self.root)
        dialog.title(title)


        label_text = f"{key} (current: {suggestion})"
        self.logger.log(f"ask_field -> {label_text}")
        tk.Label(dialog, text=label_text, justify=tk.LEFT, wraplength=520).pack(padx=10, pady=10)


        entry = tk.Entry(dialog, width=70)
        entry.pack(padx=10, pady=5)
        entry.insert(0, suggestion)


        result = {"value": suggestion}


        def on_ok():
            result["value"] = entry.get() or ""
            self.logger.log(f"ask_field OK -> {key} = {result['value']!r}")
            dialog.destroy()


        def on_cancel():
            result["value"] = suggestion or ""
            self.logger.log(f"ask_field SKIP -> {key} keeps {result['value']!r}")
            dialog.destroy()


        def on_exit():
            self.exit_early = True
            self.logger.log("ask_field EXIT pressed -> exit_early=True")
            dialog.destroy()


        def on_autofill():
            val = self.autofill.generate(prompt_text or f"Suggest something for {key}")
            entry.delete(0, tk.END)
            entry.insert(0, val)
            self.logger.log(f"ask_field AUTOFILL -> {key} = {val!r}")


        tk.Button(dialog, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5, pady=10)
        tk.Button(dialog, text="Skip", command=on_cancel).pack(side=tk.LEFT, padx=5, pady=10)
        tk.Button(dialog, text="Autofill", command=on_autofill).pack(side=tk.LEFT, padx=5, pady=10)
        tk.Button(dialog, text="Exit", command=on_exit).pack(side=tk.RIGHT, padx=5, pady=10)


        # Closing acts like Skip (does not set exit_early)
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)


        dialog.wait_window()
        return result["value"] or ""
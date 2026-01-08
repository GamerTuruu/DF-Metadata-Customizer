"""Filename Component."""

import tkinter as tk
from pathlib import Path
from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent


class FilenameComponent(AppComponent):
    """Filename editing component."""

    @override
    def setup_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        ctk.CTkLabel(self, text="Filename:").grid(row=0, column=0, sticky="e", padx=(6, 6), pady=(6, 2))
        self.filename_var = tk.StringVar()
        self.filename_entry = ctk.CTkEntry(self, textvariable=self.filename_var)
        self.filename_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=(6, 2))
        self.filename_entry.bind("<KeyRelease>", self.on_filename_changed)

        self.filename_save_btn = ctk.CTkButton(
            self,
            text="Rename File",
            width=100,
            command=self.app.rename_current_file,
            state="disabled",
        )
        self.filename_save_btn.grid(row=0, column=2, padx=(0, 6), pady=(6, 2))

    @override
    def register_events(self) -> None:
        self.app.bind("<<FilenameComponent:UpdateFilename>>", self.on_update_filename_event)

    def on_update_filename_event(self, _event: tk.Event | None = None) -> None:
        """Update filename entry when event is triggered."""
        if self.app.current_index is not None and self.app.mp3_files:
            path = self.app.mp3_files[self.app.current_index]
            filename = Path(path).name
            self.update_filename(filename)

    def update_filename(self, filename: str) -> None:
        """Update the filename entry field."""
        self.filename_var.set(filename)
        self.filename_save_btn.configure(state="disabled")

    def on_filename_changed(self, _event: tk.Event | None = None) -> None:
        """Enable/disable rename button based on filename changes."""
        if self.app.current_index is None:
            self.filename_save_btn.configure(state="disabled")
            return

        current_path = self.app.mp3_files[self.app.current_index]
        current_filename = Path(current_path).name
        new_filename = self.filename_var.get().strip()

        # Enable button only if filename has changed and is not empty
        if new_filename and new_filename != current_filename:
            self.filename_save_btn.configure(state="normal")
        else:
            self.filename_save_btn.configure(state="disabled")

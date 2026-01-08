"""Song Controls Component."""

import tkinter as tk
from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent


class SongControlsComponent(AppComponent):
    """Song controls component for folder selection, search, and select all."""

    @override
    def initialize_state(self) -> None:
        self.search_var = tk.StringVar()
        self.select_all_var = tk.BooleanVar(value=False)

    @override
    def setup_ui(self) -> None:
        self.configure(fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)  # Give more weight to search

        self.btn_select_folder = ctk.CTkButton(
            self,
            text="Select Folder",
            command=self.app.select_folder,
        )
        self.btn_select_folder.grid(row=0, column=0, padx=(0, 8))

        self.entry_search = ctk.CTkEntry(
            self,
            placeholder_text="Search title / artist / coverartist / disc / track / special / version=latest",
            textvariable=self.search_var,
        )
        self.entry_search.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.entry_search.bind("<KeyRelease>", self.on_search_keyrelease)

        self.chk_select_all = ctk.CTkCheckBox(
            self,
            text="Select All",
            variable=self.select_all_var,
            command=self.app.on_select_all,
        )
        self.chk_select_all.grid(row=0, column=2, padx=(0, 0))

    def on_search_keyrelease(self, _event: tk.Event | None = None) -> None:
        """Debounced search handler."""
        if hasattr(self, "_search_after_id"):
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after_idle(self._trigger_refresh)

    def _trigger_refresh(self) -> None:
        self.app.event_generate("<<TreeComponent:RefreshTree>>")

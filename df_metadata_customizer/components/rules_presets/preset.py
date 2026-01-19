"""Preset Component."""

import logging
import tkinter as tk
from tkinter import ttk
from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent

logger = logging.getLogger(__name__)


class PresetComponent(AppComponent):
    """Preset selection and management component."""

    @override
    def setup_ui(self) -> None:
        self.configure(fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Presets:").grid(row=0, column=0, padx=(4, 8), sticky="w")

        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(self, textvariable=self.preset_var, state="readonly", width=20)
        self.preset_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.preset_combo.bind("<<ComboboxSelected>>", self.app.on_preset_selected)

        ctk.CTkButton(self, text="Save Preset", command=self.app.save_preset, width=80).grid(row=0, column=2, padx=4)
        ctk.CTkButton(self, text="Delete", command=self.app.delete_preset, width=60).grid(row=0, column=3, padx=4)

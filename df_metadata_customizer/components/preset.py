"""Preset Component."""

import logging
import tkinter as tk
from tkinter import ttk
from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent
from df_metadata_customizer.settings_manager import SettingsManager

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

        # Theme toggle button
        self.theme_btn = ctk.CTkButton(
            self,
            text="",
            width=40,
            height=30,
            command=self.app.toggle_theme,
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
        )
        self.theme_btn.grid(row=0, column=4, padx=(8, 0))
        self.update_theme()

    @override
    def update_theme(self) -> None:
        try:
            if SettingsManager.is_dark_mode():
                # Currently dark, show light theme button
                self.theme_btn.configure(
                    text="☀️",
                    fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"],
                    hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"],
                    text_color=ctk.ThemeManager.theme["CTkButton"]["text_color"],
                )
            else:
                # Currently light, show dark theme button
                self.theme_btn.configure(
                    text="🌙",
                    fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"],
                    hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"],
                    text_color=ctk.ThemeManager.theme["CTkButton"]["text_color"],
                )
        except Exception:
            logger.exception("Error updating theme button")

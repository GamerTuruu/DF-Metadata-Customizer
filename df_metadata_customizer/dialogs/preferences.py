"""Preferences Dialog."""

import logging
from typing import TYPE_CHECKING

import customtkinter as ctk

from df_metadata_customizer.dialogs.app_dialog import AppDialog
from df_metadata_customizer.settings_manager import SettingsManager

if TYPE_CHECKING:
    from df_metadata_customizer.database_reformatter import DFApp

logger = logging.getLogger(__name__)


class PreferencesDialog(AppDialog):
    """Dialog to edit application preferences."""

    def __init__(self, parent: "DFApp") -> None:
        """Initialize the preferences dialog."""
        super().__init__(parent, "Preferences", geometry="400x200")
        self.app = parent

        # Make modal
        self.grab_set()

        # UI Elements
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Settings
        self.auto_reopen_var = ctk.BooleanVar(value=SettingsManager.auto_reopen_last_folder or False)

        self.chk_auto_reopen = ctk.CTkCheckBox(
            self.main_frame,
            text="Auto-reopen last folder on startup",
            variable=self.auto_reopen_var,
            onvalue=True,
            offvalue=False,
        )
        self.chk_auto_reopen.pack(anchor="w", pady=10, padx=10)

        # Buttons
        self.btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.btn_frame.pack(fill="x", pady=(20, 0), side="bottom")

        self.btn_save = ctk.CTkButton(self.btn_frame, text="Save", command=self.save_preferences)
        self.btn_save.pack(side="left", padx=10, expand=True)

        self.btn_cancel = ctk.CTkButton(
            self.btn_frame,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
        )
        self.btn_cancel.pack(side="right", padx=10, expand=True)

        self.focus_force()

    def save_preferences(self) -> None:
        """Save preferences and close dialog."""
        SettingsManager.auto_reopen_last_folder = self.auto_reopen_var.get()
        SettingsManager.save_settings()
        self.destroy()

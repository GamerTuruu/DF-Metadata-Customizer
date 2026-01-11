"""App Menu component."""
import tkinter as tk
from tkinter import messagebox
from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent
from df_metadata_customizer.settings_manager import SettingsManager


class AppMenuComponent(AppComponent):
    """Top window menu to edit settings."""

    @override
    def setup_ui(self) -> None:
        bar_bg_color = ("gray90", "gray10")
        self.configure(height=20, corner_radius=0, fg_color=bar_bg_color)

        self.file_menu_btn = ctk.CTkButton(
            self,
            text="File",
            width=50,
            height=20,
            corner_radius=5,
            fg_color=bar_bg_color,
            hover_color=("gray75", "gray18"),
            text_color=("gray10", "gray90"),
            anchor="center",
            command=self._show_file_menu,
        )
        self.file_menu_btn.pack(side="left", padx=0, pady=0)

        self._create_file_menu()
        self.update_theme()

    def _create_file_menu(self) -> None:
        """Create the file menu structure."""
        self.file_menu = tk.Menu(self.app, tearoff=0)
        self.file_menu.add_command(label="Open Folder", command=self.app.select_folder)
        self.file_menu.add_command(
            label="Save Settings",
            command=lambda: [self.app.save_settings(), messagebox.showinfo("Settings", "Settings saved successfully.")],
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.app._on_close)  # noqa: SLF001

    @override
    def update_theme(self) -> None:
        """Update component based on current theme."""
        try:
            dark = SettingsManager.is_dark_mode()

            if dark:
                bg_color, fg_color, active_bg, active_fg = "gray15", "gray90", "gray18", "white"
            else:
                bg_color, fg_color, active_bg, active_fg = "gray90", "gray10", "gray75", "black"

            self.file_menu.configure(
                background=bg_color,
                foreground=fg_color,
                activebackground=active_bg,
                activeforeground=active_fg,
            )
        except Exception:
            pass

    def _show_file_menu(self) -> None:
        """Show the file menu dropdown."""
        try:
            x = self.file_menu_btn.winfo_rootx()
            y = self.file_menu_btn.winfo_rooty() + self.file_menu_btn.winfo_height()
            self.file_menu.tk_popup(x, y, 0)
        finally:
            self.file_menu.grab_release()

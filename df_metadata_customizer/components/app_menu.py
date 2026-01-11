"""App Menu component."""
import tkinter as tk
from tkinter import messagebox
from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent


class AppMenuComponent(AppComponent):
    """Top window menu to edit settings."""

    @override
    def setup_ui(self) -> None:
        bar_bg_color = ("gray90", "gray11")
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

    def _show_file_menu(self) -> None:
        """Show the file menu dropdown."""
        menu = tk.Menu(self.app, tearoff=0)
        menu.add_command(label="Open Folder", command=self.app.select_folder)
        menu.add_command(
            label="Save Settings",
            command=lambda: [self.app.save_settings(), messagebox.showinfo("Settings", "Settings saved successfully.")],
        )
        menu.add_separator()
        menu.add_command(label="Exit", command=self.app._on_close)  # noqa: SLF001

        try:
            x = self.file_menu_btn.winfo_rootx()
            y = self.file_menu_btn.winfo_rooty() + self.file_menu_btn.winfo_height()
            menu.tk_popup(x, y, 0)
        finally:
            menu.grab_release()

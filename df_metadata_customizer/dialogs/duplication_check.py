"""Duplication Check Dialog."""

import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

from df_metadata_customizer import song_utils
from df_metadata_customizer.dialogs.progress import ProgressDialog
from df_metadata_customizer.settings_manager import SettingsManager

if TYPE_CHECKING:
    from df_metadata_customizer.database_reformatter import DFApp

logger = logging.getLogger(__name__)


class DuplicationCheckDialog(ctk.CTkToplevel):
    """Dialog to check for duplicate songs."""

    def __init__(self, parent: "DFApp") -> None:
        """Initialize the duplication check dialog."""
        super().__init__(parent)
        self.app = parent
        self.title("Duplication Check")
        self.geometry("450x200")
        self.resizable(width=False, height=False)

        # Center the dialog
        self.transient(parent)

        self.update_idletasks()
        parent.update_idletasks()

        # Center the window
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        width = self.winfo_width()
        height = self.winfo_height()

        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        self.geometry(f"+{x}+{y}")

        # UI Elements
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.info_label = ctk.CTkLabel(
            self.main_frame,
            text="This tool checks for purely exact audio content duplication.\n"
            "It calculates a hash of the audio data, ignoring metadata tags.\n\n"
            f"Files to check: {len(self.app.song_files)}",
            justify="center",
            wraplength=400,
        )
        self.info_label.pack(pady=(20, 20))

        self.btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.btn_frame.pack(fill="x", pady=(10, 0))

        self.btn_start = ctk.CTkButton(self.btn_frame, text="Start", command=self.start_check)
        self.btn_start.pack(side="left", padx=10, expand=True)

        self.btn_cancel = ctk.CTkButton(
            self.btn_frame,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
        )
        self.btn_cancel.pack(side="right", padx=10, expand=True)

    def start_check(self) -> None:
        """Start the duplication check process."""
        self.withdraw()  # Hide this dialog

        progress = ProgressDialog(self.app, title="Checking for duplicates...")

        hashes: dict[str, list[str]] = defaultdict(list)
        total_files = len(self.app.song_files)

        for i, file_path in enumerate(self.app.song_files):
            if not progress.update_progress(i, total_files, f"Hashing: {Path(file_path).name}"):
                logger.info("Duplication check cancelled.")
                self.destroy()
                return

            try:
                # Use the new function we are adding
                audio_hash = song_utils.get_audio_hash(file_path)
                if audio_hash:
                    hashes[audio_hash].append(file_path)
            except Exception:
                logger.exception("Failed to hash %s", file_path)

        progress.destroy()

        # Filter for duplicates (more than 1 file with same hash)
        duplicates = {h: paths for h, paths in hashes.items() if len(paths) > 1}

        self.show_results(duplicates)
        self.destroy()

    def show_results(self, duplicates: dict[str, list[str]]) -> None:  # TODO: Add option to filter the songlist after
        """Show the results of the check."""
        result_window = ctk.CTkToplevel(self.app)
        result_window.title("Duplication Results")
        result_window.geometry("800x500")

        msg = f"Found {len(duplicates)} sets of duplicates.\n"
        if not duplicates:
            msg += "No exact audio duplicates found."

        text_area = ctk.CTkTextbox(result_window)
        text_area.pack(fill="both", expand=True, padx=10, pady=10)

        text_font = ctk.CTkFont(family="Consolas", size=11)
        text_area.configure(font=text_font)

        text_area.insert("1.0", msg + "\n")

        root_folder_str = SettingsManager.last_folder_opened
        root_folder = Path(root_folder_str) if root_folder_str else None

        if root_folder:
            text_area.insert("end", f"Files relative to: {root_folder}\n")
        else:
            text_area.insert("end", "Files shown with absolute paths (no root folder detected)\n")

        text_area.insert("end", "-" * 60 + "\n")

        for i, (h, paths) in enumerate(duplicates.items(), 1):
            text_area.insert("end", f"Group {i} (Hash: {h[:8]}...):\n")
            for p in paths:
                display_path = p
                if root_folder:
                    try:  # Try absolute resolution first just in case p is not abs
                        abs_p = Path(p).resolve()
                        abs_root = root_folder.resolve()
                        display_path = os.path.relpath(abs_p, abs_root)
                    except Exception:  # noqa: S110
                        pass  # Keep original path if error

                text_area.insert("end", f"  - {display_path}\n")
            text_area.insert("end", "\n")

        text_area.configure(state="disabled")

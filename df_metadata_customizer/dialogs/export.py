"""Export Dialog."""

import json
import logging
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk

from df_metadata_customizer import song_utils
from df_metadata_customizer.dialogs.app_dialog import AppDialog
from df_metadata_customizer.dialogs.progress import ProgressDialog

if TYPE_CHECKING:
    from df_metadata_customizer.database_reformatter import DFApp

logger = logging.getLogger(__name__)


class ExportDialog(AppDialog):
    """Dialog to export metadata to JSON files."""

    def __init__(self, parent: "DFApp") -> None:
        """Initialize the export dialog."""
        super().__init__(parent, "Export Metadata", geometry="450x250")
        self.app = parent
        self.export_folder: str | None = None

        # UI Elements
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Folder Selection
        self.folder_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.folder_frame.pack(fill="x", pady=(10, 20))

        self.folder_label = ctk.CTkEntry(self.folder_frame, placeholder_text="Select destination folder...")
        self.folder_label.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_browse = ctk.CTkButton(self.folder_frame, text="Browse", width=80, command=self.select_folder)
        self.btn_browse.pack(side="right")

        # Info Label
        self.info_label = ctk.CTkLabel(
            self.main_frame,
            text=f"Files to export: {len(self.app.song_files)}",
            justify="center",
        )
        self.info_label.pack(pady=(0, 20))

        # Buttons
        self.btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.btn_frame.pack(fill="x", pady=(10, 0), side="bottom")

        self.btn_export = ctk.CTkButton(self.btn_frame, text="Export", command=self.start_export)
        self.btn_export.pack(side="left", padx=10, expand=True)

        self.btn_cancel = ctk.CTkButton(
            self.btn_frame,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
        )
        self.btn_cancel.pack(side="right", padx=10, expand=True)

    def select_folder(self) -> None:
        """Open folder browser."""
        folder = filedialog.askdirectory(title="Select Destination Folder")
        if folder:
            self.export_folder = folder
            self.folder_label.delete(0, "end")
            self.folder_label.insert(0, folder)

    def start_export(self) -> None:
        """Start the export process."""
        if not self.export_folder:
            messagebox.showwarning("Missing Folder", "Please select a destination folder.")
            return

        if not self.app.song_files:
            messagebox.showwarning("No Songs", "No songs loaded to export.")
            return

        self.withdraw()  # Hide dialog

        progress = ProgressDialog(self.app, title="Exporting Metadata...")

        total_files = len(self.app.song_files)
        exported_count = 0
        current_folder = Path(self.app.current_folder) if self.app.current_folder else None

        for i, file_path in enumerate(self.app.song_files):
            p = Path(file_path)
            if not progress.update_progress(i, total_files, f"Exporting: {p.name}"):
                logger.info("Export cancelled.")
                self.destroy()
                return

            try:
                # Get raw metadata
                data = song_utils.extract_json_from_song(file_path)
                if data:
                    # Determine output path
                    if current_folder:
                        try:
                            rel_path = p.relative_to(current_folder)
                        except ValueError:
                            # If not relative (shouldn't happen often in this app context), use name
                            rel_path = Path(p.name)
                    else:
                        rel_path = Path(p.name)

                    # Construct output path with .json extension
                    out_path = Path(self.export_folder) / rel_path.with_suffix(".json")

                    # Create directories
                    out_path.parent.mkdir(parents=True, exist_ok=True)

                    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

                    exported_count += 1
            except Exception:
                logger.exception("Failed to export metadata for %s", file_path)

        progress.destroy()

        messagebox.showinfo(
            "Export Complete",
            f"Successfully exported {exported_count} JSON files.\nDestination: {self.export_folder}",
        )
        self.destroy()

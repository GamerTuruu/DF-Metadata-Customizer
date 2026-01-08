"""JSON Editor Component."""

import contextlib
import json
import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, override

import customtkinter as ctk

from df_metadata_customizer import mp3_utils
from df_metadata_customizer.components.app_component import AppComponent
from df_metadata_customizer.file_manager import FileManager

if TYPE_CHECKING:
    from df_metadata_customizer.song_metadata import SongMetadata


logger = logging.getLogger(__name__)


class JSONEditComponent(AppComponent):
    """JSON Editor component for viewing and editing JSON metadata."""

    @override
    def setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # JSON viewer
        json_frame = ctk.CTkFrame(self)
        json_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        json_frame.grid_rowconfigure(1, weight=1)
        json_frame.grid_columnconfigure(0, weight=1)
        json_frame.grid_columnconfigure(1, weight=0)

        json_header = ctk.CTkFrame(json_frame, fg_color="transparent")
        json_header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 4))
        json_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(json_header, text="JSON (from comment)").grid(row=0, column=0, sticky="w")
        self.json_save_btn = ctk.CTkButton(
            json_header,
            text="Save JSON",
            width=80,
            command=self.save_json_to_file,
            state="disabled",
        )
        self.json_save_btn.grid(row=0, column=1, padx=(8, 0))

        self.json_text = tk.Text(json_frame, wrap="none", height=12)
        self.update_theme()
        self.json_text.grid(row=1, column=0, sticky="nsew", padx=(6, 0), pady=(0, 6))
        self.json_text.bind("<KeyRelease>", self.on_json_changed)

        self.json_scroll = ttk.Scrollbar(json_frame, orient="vertical", command=self.json_text.yview)
        self.json_text.configure(yscrollcommand=self.json_scroll.set)
        self.json_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 6))

        # Cover preview
        cover_frame = ctk.CTkFrame(self)
        cover_frame.grid(row=0, column=1, sticky="nsew")
        cover_frame.grid_rowconfigure(0, weight=1)

        self.cover_display = ctk.CTkLabel(cover_frame, text="Loading cover...", corner_radius=8, justify="center")
        self.cover_display.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

    @override
    def update_theme(self) -> None:
        try:
            if self.app.is_dark_mode:
                self.json_text.configure(bg="#2b2b2b", fg="white", insertbackground="white", selectbackground="#1f6aa5")
            else:
                self.json_text.configure(bg="white", fg="black", insertbackground="black", selectbackground="#0078d7")
        except Exception:
            logger.exception("Error updating JSON text style")

    @override
    def register_events(self) -> None:
        self.app.bind("<<JSONEditComponent:UpdateJSON>>", self.on_update_json_event)

    def on_update_json_event(self, _event: tk.Event | None = None) -> None:
        """Update the JSON text area when event is triggered."""
        if self.app.current_metadata:
            self.update_json(self.app.current_metadata)

    def update_json(self, metadata: "SongMetadata") -> None:
        """Update the JSON text area with metadata."""
        self.json_text.delete("1.0", "end")
        if metadata.raw_data:
            try:
                # FIXED: Ensure proper encoding for JSON dump
                json_str = json.dumps(metadata.raw_data, indent=2, ensure_ascii=False)
                self.json_text.insert("1.0", json_str)
            except Exception:
                logger.exception("Error displaying JSON with UTF-8 encoding")
                # Fallback: try with ASCII encoding
                try:
                    json_str = json.dumps(metadata.raw_data, indent=2, ensure_ascii=True)
                    self.json_text.insert("1.0", json_str)
                except Exception:
                    self.json_text.insert("1.0", "Error displaying JSON data")
        else:
            self.json_text.insert("1.0", "No JSON found in comments")
        # Disable JSON save button initially (no changes yet)
        self.json_save_btn.configure(state="disabled")

    def on_json_changed(self, _event: tk.Event | None = None) -> None:
        """Enable/disable save button based on JSON changes."""
        if self.app.current_index is None:
            self.json_save_btn.configure(state="disabled")
            return

        current_text = self.json_text.get("1.0", "end-1c").strip()

        # Get original JSON from metadata
        original_json = ""
        if self.app.current_metadata and self.app.current_metadata.raw_data:
            with contextlib.suppress(Exception):
                original_json = json.dumps(self.app.current_metadata.raw_data, indent=2, ensure_ascii=False)

        # Enable button only if text has changed and is not empty
        if current_text and current_text != original_json:
            self.json_save_btn.configure(state="normal")
        else:
            self.json_save_btn.configure(state="disabled")

    def save_json_to_file(self) -> None:
        """Save the edited JSON back to the current MP3 file."""
        if self.app.current_index is None or not self.app.mp3_files:
            messagebox.showwarning("No file selected", "Please select a file first")
            return

        # Get the edited JSON text
        json_text = self.json_text.get("1.0", "end-1c").strip()

        if not json_text:
            messagebox.showwarning("Empty JSON", "JSON text is empty")
            return

        try:
            # Use FileManager to prepare JSON
            full_comment, json_data = FileManager.prepare_json_for_save(json_text)

        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"The JSON is invalid:\n{e!s}")
            return

        # Confirm save
        path = self.app.mp3_files[self.app.current_index]
        filename = Path(path).name
        result = messagebox.askyesno("Confirm Save", f"Save JSON changes to:\n{filename}?")

        if not result:
            return

        # Show saving indicator
        _original_text = self.app.lbl_file_info.cget("text")
        self.app.lbl_file_info.configure(text=f"Saving JSON to {filename}...")
        self.app.update_idletasks()

        def on_save_complete(filename: str, *, success: bool) -> None:
            if success:
                # Update cache with new data
                self.app.file_manager.update_file_data(path, json_data)
                self.app.current_metadata = self.app.file_manager.get_metadata(path)

                # Update the treeview with new data
                self.app.update_tree_row(self.app.current_index, json_data)

                self.app.lbl_file_info.configure(text=f"JSON saved to {filename}")
                messagebox.showinfo("Success", f"JSON successfully saved to {filename}")

                # Update preview with new data
                self.app.output_preview_component.update_preview()

                # Disable save button after successful save
                self.json_save_btn.configure(state="disabled")
            else:
                self.app.lbl_file_info.configure(text=f"Failed to save JSON to {filename}")
                messagebox.showerror("Error", f"Failed to save JSON to {filename}")

        # Save JSON
        saved = mp3_utils.write_json_to_mp3(path, full_comment)
        self.after(0, lambda: on_save_complete(filename, success=saved))

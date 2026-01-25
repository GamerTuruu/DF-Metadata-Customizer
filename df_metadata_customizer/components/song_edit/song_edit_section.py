"""Song Edit Component."""

import logging
import shutil
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import override

import customtkinter as ctk
from PIL import Image

from df_metadata_customizer import song_utils
from df_metadata_customizer.components.app_component import AppComponent
from df_metadata_customizer.components.song_edit.cover_display import CoverDisplayComponent
from df_metadata_customizer.components.song_edit.metadata_editor import MetadataEditorComponent
from df_metadata_customizer.song_metadata import MetadataFields, SongMetadata

logger = logging.getLogger(__name__)


class SongEditComponent(AppComponent):
    """Song Edit component for viewing and editing song details."""

    @override
    def initialize_state(self) -> None:
        self.current_metadata: SongMetadata | None = None
        self.pending_cover_path: str | None = None
        self.is_copy_mode = False
        self.adding_new_song = False
        self.new_song_source_path: str | None = None

    @override
    def setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 1. Song Title Header (centered)
        self.title_label = ctk.CTkLabel(
            self,
            text="No song selected",
            anchor="center",
            font=("Segoe UI", 16, "bold"),
            text_color=("gray20", "gray80"),
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        # 2. Info Header (smaller, centered)
        self.info_label = ctk.CTkLabel(
            self,
            text="",
            anchor="center",
            font=("Segoe UI", 13),
            text_color="gray70",
        )
        self.info_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        # 3. Main Content Area (vertical layout)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=1)

        # Cover Art (centered)
        self.cover_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.cover_container.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 10))
        self.cover_container.grid_columnconfigure(0, weight=1)

        self.cover_component = CoverDisplayComponent(
            self.cover_container,
            self.app,
            on_change_click=self.change_cover_art,
            width=200,
            height=200,
        )
        self.cover_component.grid(row=0, column=0, padx=5, pady=5)

        # Metadata Editor (left-justified, expands)
        self.metadata_editor = MetadataEditorComponent(
            self.content_frame,
            self.app,
            on_change=self._check_for_changes,
        )
        self.metadata_editor.grid(row=1, column=0, sticky="nsew", padx=5, pady=0)

        # 4. Message Area (above controls)
        self.message_frame = ctk.CTkFrame(self, fg_color="transparent", height=20)
        self.message_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 0))
        self.message_frame.grid_propagate(flag=False)

        self.copy_label = ctk.CTkLabel(
            self.message_frame,
            text="",
            text_color=["#FFC107", "#FFA000"],
            font=("Segoe UI", 11),
        )
        self.copy_label.pack(side="bottom", pady=0)

        # 5. Bottom Controls
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=10)

        self.btn_add = ctk.CTkButton(self.controls_frame, text="Add Song", command=self.start_add_song_flow, width=100)
        self.btn_add.pack(side="left", padx=5, anchor="s")

        # Save default button colors
        self._btn_add_default_fg = self.btn_add.cget("fg_color")
        self._btn_add_default_hover = self.btn_add.cget("hover_color")

        self.btn_copy = ctk.CTkButton(
            self.controls_frame,
            text="Copy Data",
            command=self.toggle_copy_mode,
            fg_color="gray50",
            width=100,
        )
        self.btn_copy.pack(side="left", padx=5, anchor="s")

        # Spacer
        ctk.CTkFrame(self.controls_frame, fg_color="transparent", height=1).pack(side="left", fill="x", expand=True)

        self.btn_confirm = ctk.CTkButton(
            self.controls_frame,
            text="Confirm Changes",
            command=self.confirm_changes,
            fg_color="green",
            state="disabled",
            width=140,
        )
        self.btn_confirm.pack(side="right", padx=5, anchor="s")

    def _check_for_changes(self) -> None:
        """Check for pending changes and update confirm button."""
        has_changes = self.metadata_editor.has_unsaved_changes()

        title = self.current_metadata.raw_data.get(MetadataFields.TITLE) or Path(self.current_metadata.path).stem

        if self.adding_new_song or has_changes:
            self.title_label.configure(text=f"[Unsaved] {title}", text_color=("#FFB300", "#FF8F00"))
            self.btn_confirm.configure(state="normal")
        else:
            self.title_label.configure(text=title, text_color=("gray20", "gray80"))
            self.btn_confirm.configure(state="disabled")

    def update_view(self, metadata: SongMetadata | None, *, forced: bool = False) -> None:
        """Update the view with a song metadata object."""
        # Check copy mode
        if self.is_copy_mode and metadata and not forced:
            self._handle_copy_from_metadata(metadata)
            return

        if not self.adding_new_song and not self.is_copy_mode:
            self.current_metadata = metadata
            # Clear success message when navigating normally
            self.copy_label.configure(text="")

        if metadata:
            # Update title
            self._update_header_text(metadata.path)

            should_update_originals = forced or not self.adding_new_song
            self.metadata_editor.load_metadata(metadata, update_original=should_update_originals)
            self._check_for_changes()

            # If we are just viewing, we reset pending states unless we are "Adding"
            if not self.adding_new_song:
                self.pending_cover_path = None
                self.new_song_source_path = None
        else:
            self.title_label.configure(text="No song selected")
            self.info_label.configure(text="")
            self.metadata_editor.load_metadata(None)
            self.cover_component.update_image(None)
            self._check_for_changes()

    def _update_header_text(self, path: str) -> None:
        """Update info label text."""
        try:
            rel_path = Path(path).relative_to(Path(self.app.current_folder).parent)
        except Exception:
            rel_path = Path(path).name

        if self.adding_new_song and self.new_song_source_path:
            self.info_label.configure(text=f"Adding: {self.new_song_source_path}\n→ {path}")
        else:
            self.info_label.configure(text=f"{rel_path}")

    def display_cover(self, ctk_image: ctk.CTkImage | None) -> None:
        """Update cover image (called externally or internally)."""
        if not self.is_copy_mode:
            self.cover_component.update_image(ctk_image)

    def show_loading_cover(self) -> None:
        """Show loading state for cover."""
        if not self.is_copy_mode:
            self.cover_component.show_loading()

    def show_no_cover(self, message: str = "No cover") -> None:
        """Show no cover state."""
        if not self.is_copy_mode:
            self.cover_component.show_no_cover(message)

    def show_cover_error(self, message: str = "No cover (error)") -> None:
        """Show error state for cover."""
        if not self.is_copy_mode:
            self.cover_component.show_error(message)

    def _reload_selected_song(self) -> None:
        """Reload the currently selected song from the app."""
        selected_items = self.app.tree_component.tree.selection()
        if selected_items:
            try:
                # Tree selection returns IIDs which are ints in our app
                iid = selected_items[0]
                idx = int(iid)
                if 0 <= idx < len(self.app.song_files):
                    path = self.app.song_files[idx]
                    metadata = self.app.file_manager.get_metadata(path)
                    self.update_view(metadata)
                    return
            except (ValueError, IndexError):
                pass

        # No selection or invalid
        self.update_view(None)

    def start_add_song_flow(self) -> None:
        """Handle 'Add Song' button click."""
        if self.adding_new_song:
            # Cancel Logic
            self.adding_new_song = False
            self.new_song_source_path = None
            self.pending_cover_path = None

            # Reset UI
            self.btn_add.configure(
                text="Add Song",
                fg_color=self._btn_add_default_fg,
                hover_color=self._btn_add_default_hover,
            )
            self._reload_selected_song()
            return

        file_path = filedialog.askopenfilename(
            title="Select Song to Add",
            filetypes=[("Audio Files", [f"*{ext}" for ext in song_utils.SUPPORTED_FILES_TYPES])],
        )
        if not file_path:
            return

        self.adding_new_song = True
        self.new_song_source_path = file_path

        # Update button to Cancel state
        self.btn_add.configure(text="Cancel Add", fg_color="red", hover_color="darkred")

        # Load metadata from this file
        data = self.app.file_manager.get_metadata(file_path)

        # Determine likely output path
        current_folder = self.app.current_folder
        if current_folder and Path(current_folder).exists():
            out_path = Path(current_folder) / Path(file_path).name
        else:
            out_path = Path(file_path)  # Fallback

        self.update_view(data, forced=True)
        # Override header
        self.info_label.configure(text=f"Adding: {Path(file_path).name} \nTo: {out_path}")

        # Load its cover
        self.app.load_cover_art(file_path)

        messagebox.showinfo(
            "Add Song",
            "Edit details and click Confirm to save the new song.\nYou will be asked for the save location.",
        )

    def toggle_copy_mode(self) -> None:
        """Toggle 'Copy Data' mode."""
        self.is_copy_mode = not self.is_copy_mode
        if self.is_copy_mode:
            # Entering copy mode
            self.btn_copy.configure(
                fg_color=["#FFC107", "#FFA000"],
                hover_color=["#FFB300", "#FF8F00"],
                border_width=2,
                text="Copying...",
                text_color="black",
            )

            self.copy_label.configure(text="Select source song...", text_color=["#FFC107", "#FFA000"])

        else:
            # Exiting copy mode
            self.btn_copy.configure(
                fg_color="gray50",
                hover_color=["gray43", "gray35"],
                border_width=0,
                text="Copy Data",
                text_color=["gray98", "#DCE4EE"],
            )

            # If we cancelled (label text is "Select source..."), clear it.
            # If we succeeded (label text is "Copied..."), keep it.
            current_text = self.copy_label.cget("text")
            if current_text == "Select source song...":
                self.copy_label.configure(text="")

    def _handle_copy_from_metadata(self, metadata: SongMetadata) -> None:
        """Copy data from selected metadata into editor."""
        # Use import_metadata to treat changes as manual edits (unsaved)
        self.metadata_editor.import_metadata(metadata)

        rel_path = Path(metadata.path).name
        completion_msg = f"Copied data from: {rel_path}"

        # Set success message before toggling off
        self.copy_label.configure(text=completion_msg, text_color=["#FFC107", "#FFA000"])

        self.toggle_copy_mode()  # Turn off
        self._check_for_changes()

    def change_cover_art(self) -> None:
        """Handle clicking the cover art."""
        if not self.current_metadata and not self.adding_new_song:
            return

        file_path = filedialog.askopenfilename(
            title="Select Cover Art",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp")],
        )
        if not file_path:
            return

        # Case 1: Adding New Song
        # Since the file doesn't exist at the destination yet, we can't save the cover to it.
        # We must keep the "pending" behavior.
        if self.adding_new_song:
            self.pending_cover_path = file_path

            try:
                pil_image = Image.open(file_path)
                ctk_img = self.app.cover_cache.put(file_path, pil_image, resize=True)
                if ctk_img:
                    self.cover_component.update_image(ctk_img)
                    base_text = self.info_label.cget("text").split(" *")[0]
                    self.info_label.configure(text=base_text + " *Cover Changed*")
                else:
                    messagebox.showerror("Error", "Failed to process image")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {e}")
            return

        # Case 2: Editing Existing Song(s)
        # Apply changes immediately as requested.
        try:
            # Determine targets
            targets = [self.current_metadata.path]

            # Check if we have a selection in the tree that we should apply to
            selected_items = self.app.tree_component.tree.selection()
            if len(selected_items) > 0:
                selected_paths = []
                for iid in selected_items:
                    try:
                        idx = int(iid)
                        if 0 <= idx < len(self.app.song_files):
                            selected_paths.append(self.app.song_files[idx])
                    except ValueError:
                        continue

                # If valid selection found, use it
                if selected_paths:
                    targets = selected_paths

            # If current song is not in the selection (weird edge case), ensure at least update current view.
            # Standard logic: if selection exists, operate on selection. If not, operate on current view.
            # The logic above defaults to current view, creating list from selection if exists.

            # Confirmation
            msg = f"Update cover art for: {Path(self.current_metadata.path).name}"
            if len(targets) > 1:
                msg = f"Update cover art for {len(targets)} selected files?"

            if not messagebox.askyesno("Confirm Cover Update", msg):
                return

            # Read bytes directly from the new image file
            cover_bytes = Path(file_path).read_bytes()

            # Determine mime type
            mime_type = "image/jpeg"
            enc_lower = file_path.lower()
            if enc_lower.endswith(".png"):
                mime_type = "image/png"
            elif enc_lower.endswith(".bmp"):
                mime_type = "image/bmp"

            # Apply
            pil_image = Image.open(file_path)
            success_count = 0
            for path in targets:
                if song_utils.write_id3_tags(path, cover_bytes=cover_bytes, cover_mime=mime_type):
                    success_count += 1

                # Update the cache and view
                img = self.app.cover_cache.put(path, pil_image, resize=True)
                if path == self.current_metadata.path:
                    self.cover_component.update_image(img)

            # Commit changes (if manager needs it)
            self.app.file_manager.commit()

            # Reset pending state if any
            self.pending_cover_path = None

            # Clean label (remove previous *Cover Changed* if present)
            base_text = self.info_label.cget("text").split(" *")[0]
            self.info_label.configure(text=base_text)

            messagebox.showinfo("Success", f"Cover art updated for {success_count} files.")

        except Exception as e:
            logger.exception("Failed to update cover art")
            messagebox.showerror("Error", f"Failed to update cover art: {e}")

    def confirm_changes(self) -> None:
        """Save changes to file(s)."""
        ui_data = self.metadata_editor.get_current_data()

        # 1. Prepare JSON Data
        json_data = {}
        for ui_key, json_key in self.metadata_editor.KEY_MAP.items():
            if ui_key in ui_data:
                json_data[json_key] = ui_data[ui_key]

        # Add xxHash if requested
        if self.metadata_editor.should_include_hash():
            path_to_hash = None
            if self.adding_new_song and self.new_song_source_path:
                path_to_hash = self.new_song_source_path
            elif self.current_metadata and self.current_metadata.path:
                path_to_hash = self.current_metadata.path

            if path_to_hash:
                h = song_utils.get_audio_hash(path_to_hash)
                if h:
                    json_data["xxHash"] = h

        # 2. Prepare ID3 Data
        id3_data = {}
        if MetadataFields.UI_ID3_TITLE in ui_data:
            id3_data["title"] = ui_data[MetadataFields.UI_ID3_TITLE]
        if MetadataFields.UI_ID3_ARTIST in ui_data:
            id3_data["artist"] = ui_data[MetadataFields.UI_ID3_ARTIST]
        if MetadataFields.UI_ID3_ALBUM in ui_data:
            id3_data["album"] = ui_data[MetadataFields.UI_ID3_ALBUM]
        if MetadataFields.UI_ID3_TRACK in ui_data:
            id3_data["track"] = ui_data[MetadataFields.UI_ID3_TRACK]
        if MetadataFields.UI_ID3_DISC in ui_data:
            id3_data["disc"] = ui_data[MetadataFields.UI_ID3_DISC]
        if MetadataFields.UI_ID3_DATE in ui_data:
            id3_data["date"] = ui_data[MetadataFields.UI_ID3_DATE]

        target_path = None
        final_dest_path = None

        # Logic for Adding vs Editing
        if self.adding_new_song:
            initial_file = Path(self.new_song_source_path).name

            # Determine initial dir for save dialog
            current_folder = self.app.current_folder
            start_dir = (
                current_folder
                if current_folder and Path(current_folder).exists()
                else str(Path(self.new_song_source_path).parent)
            )

            out_path = filedialog.asksaveasfilename(
                title="Save New Song As",
                initialdir=start_dir,
                initialfile=initial_file,
                filetypes=[("Audio", "*.mp3 *.flac")],
            )
            if not out_path:
                return

            final_dest_path = out_path
            target_path = final_dest_path

            msg = f"Adding New Song:\nFrom: {self.new_song_source_path}\nTo: {final_dest_path}"

        else:
            if not self.current_metadata:
                return

            main_path = self.current_metadata.path
            target_path = main_path

            msg = f"Updating Metadata for: {Path(main_path).name}"

        if not messagebox.askyesno("Confirm Changes", msg):
            return

        try:
            # 1. Copy file
            if self.adding_new_song and final_dest_path:
                shutil.copy2(self.new_song_source_path, final_dest_path)

            # 2. metadata (JSON + ID3)

            if target_path:
                # Write JSON
                song_utils.write_json_to_song(target_path, json_data)

                # Write ID3 (Standard Tags)
                song_utils.write_id3_tags(target_path, **id3_data)

                # Update file manager cache
                self.app.file_manager.update_file_data(target_path, json_data)

            # 3. Cover Art
            # Only write cover if pending change exists or adding new song
            if self.pending_cover_path:
                cover_bytes = None
                cover_mime = "image/jpeg"

                # If pending path is an image file
                if self.pending_cover_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                    cover_bytes = Path(self.pending_cover_path).read_bytes()
                    if self.pending_cover_path.lower().endswith(".png"):
                        cover_mime = "image/png"
                    elif self.pending_cover_path.lower().endswith(".bmp"):
                        cover_mime = "image/bmp"

                # If pending path is a song file (copy from another song)
                elif self.pending_cover_path.lower().endswith(tuple(song_utils.SUPPORTED_FILES_TYPES)):
                    # extract cover
                    img = song_utils.read_cover_from_song(self.pending_cover_path)
                    if img:
                        # Convert PIL to bytes
                        b = BytesIO()
                        img.save(b, format="JPEG")
                        cover_bytes = b.getvalue()
                        # cover_mime stays jpeg

                if cover_bytes and target_path:
                    song_utils.write_id3_tags(target_path, cover_bytes=cover_bytes, cover_mime=cover_mime)

            # 4. Update song list and treeview
            if self.adding_new_song and target_path:
                try:
                    path_str = str(Path(target_path))
                    should_add = False

                    if self.app.current_folder:
                        curr_folder_path = Path(self.app.current_folder).resolve()
                        target_path_obj = Path(target_path).resolve()

                        # Check if target is inside current folder (or subfolder)
                        # Iterate parents to support subfolders
                        if curr_folder_path == target_path_obj.parent or curr_folder_path in target_path_obj.parents:
                            should_add = True
                    else:
                        should_add = True

                    if should_add and path_str not in self.app.song_files:
                        self.app.song_files.append(path_str)
                        self.app.populate_tree_fast()

                except Exception:
                    logger.exception("Failed to add new song to view")

            # Commit and Refresh
            self.app.file_manager.commit()

            self.adding_new_song = False
            self.new_song_source_path = None
            self.pending_cover_path = None
            self.is_copy_mode = False
            self.btn_confirm.configure(state="disabled")

            # Reset Add Button state
            self.btn_add.configure(
                text="Add Song",
                fg_color=self._btn_add_default_fg,
                hover_color=self._btn_add_default_hover,
            )

            messagebox.showinfo("Success", "Changes saved successfully.")
            self.app.refresh_tree()

        except Exception as e:
            logger.exception("Failed to save changes")
            messagebox.showerror("Error", f"Failed to save changes: {e}")

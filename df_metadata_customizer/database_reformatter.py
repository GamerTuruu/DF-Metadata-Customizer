"""Database Reformatter Application - Main Window and Logic."""

import contextlib
import logging
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from typing import TYPE_CHECKING, Final

import customtkinter as ctk
from rich.logging import RichHandler

from df_metadata_customizer import song_utils
from df_metadata_customizer.components import (
    AppMenuComponent,
    JSONEditComponent,
    SongControlsComponent,
    SongEditComponent,
    SortingComponent,
    StatisticsComponent,
    TreeComponent,
)
from df_metadata_customizer.components.rules_presets import (
    ApplyComponent,
    FilenameComponent,
    OutputPreviewComponent,
    PresetComponent,
    RuleTabsComponent,
)
from df_metadata_customizer.dialogs import ConfirmDialog, ProgressDialog
from df_metadata_customizer.file_manager import FileManager
from df_metadata_customizer.image_utils import LRUCTKImageCache
from df_metadata_customizer.rule_manager import RuleManager
from df_metadata_customizer.settings_manager import SettingsManager
from df_metadata_customizer.song_metadata import MetadataFields
from df_metadata_customizer.widgets import RuleRow

if TYPE_CHECKING:
    from df_metadata_customizer.song_metadata import SongMetadata

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("dark-blue")

logging_handler = RichHandler(
    show_time=True,
    show_level=True,
    show_path=False,
    markup=False,
    rich_tracebacks=True,
)
logging.basicConfig(level=logging.DEBUG, format="%(message)s", handlers=[logging_handler])
logging.getLogger("PIL").setLevel(logging.INFO)  # Suppress PIL debug logs

logger = logging.getLogger(__name__)


class DFApp(ctk.CTk):
    """Main application window for Database Reformatter.

    Separated into components.
    Logic between multiple separate components should be handled here.
    """

    RULE_OPS: Final = [
        "is",
        "contains",
        "starts with",
        "ends with",
        "is empty",
        "is not empty",
        "is latest version",
        "is not latest version",
    ]

    def __init__(self) -> None:
        """Initialize the main application window."""
        super().__init__()
        self.title("Database Reformatter — Metadata Customizer")

        # Window size
        if self.winfo_screenheight() >= 1440:  # 1440p+ -> 1080p
            width, height = 1920, 1080
        else:
            width, height = 1280, 720

        self.geometry(f"{width}x{height}")
        self.minsize(960, 540)

        # Center the window
        self.update_idletasks()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"+{x}+{y}")

        SettingsManager.initialize()
        self.file_manager = FileManager()

        # Data model
        self.song_files = []  # list of file paths
        self.current_index = None
        self.current_folder: str | None = None
        self.current_metadata: SongMetadata | None = None

        self.visible_file_indices = []  # Track visible files for prev/next navigation
        self.progress_dialog = None  # Progress dialog reference
        self.operation_in_progress = False  # Prevent multiple operations

        # Theme management
        self.theme_icon_cache = {}  # Cache for theme icons

        # Cover image settings - OPTIMIZED
        self.cover_cache = LRUCTKImageCache(max_size=50)  # Optimized cache
        self.last_cover_request_time = 0.0  # Track last cover request time for throttling

        # Maximum number of allowed sort rules (including the primary rule)
        self.max_rules_per_tab = 50

        # Build UI
        self._build_ui()
        self.update()

        # Load saved settings (if any)
        with contextlib.suppress(Exception):
            self.load_settings()

        # default presets container
        self.presets = {}

        # Ensure settings are saved on exit
        with contextlib.suppress(Exception):
            self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        # Top Menu Bar
        self.menu_component = AppMenuComponent(self, self)
        self.menu_component.pack(side="top", fill="x")

        # Use a PanedWindow for draggable splitter
        self.paned = tk.PanedWindow(
            self,
            orient="horizontal",
            sashrelief="raised",
            sashwidth=6,
        )  # TODO: Convert to ttk.PanedWindow
        self.paned.pack(fill="both", expand=True, padx=8, pady=8)

        # Left (song list) frame
        self.left_frame = ctk.CTkFrame(self.paned, corner_radius=8)
        self.paned.add(self.left_frame, minsize=620)  # left bigger by default

        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(2, weight=1)  # Treeview row expands
        self.left_frame.grid_rowconfigure(3, weight=0)  # Status row fixed
        self.left_frame.grid_rowconfigure(4, weight=0)  # Bottom status row fixed

        # Top controls: folder select + search + select all
        self.song_controls_component = SongControlsComponent(self.left_frame, self)
        self.song_controls_component.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))

        # Sort controls
        self.sorting_component = SortingComponent(self.left_frame, self)
        self.sorting_component.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        # Treeview song list
        self.tree_component = TreeComponent(self.left_frame, self)
        self.tree_component.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 4))

        # Status panel - NEW: Simple button that shows popup
        self.statistics_component = StatisticsComponent(self.left_frame, self, fg_color="transparent")
        self.statistics_component.grid(row=3, column=0, sticky="ew", padx=8, pady=(4, 4))

        # Bottom status row (file info + selection info)
        status_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        status_frame.grid(row=4, column=0, sticky="ew", padx=8, pady=(4, 8))
        status_frame.grid_columnconfigure(0, weight=1)

        self.lbl_file_info = ctk.CTkLabel(status_frame, text="No folder selected")
        self.lbl_file_info.grid(row=0, column=0, sticky="w")

        self.lbl_selection_info = ctk.CTkLabel(status_frame, text="0 song(s) selected")
        self.lbl_selection_info.grid(row=0, column=1, sticky="e", padx=(0, 8))

        self.btn_prev = ctk.CTkButton(
            status_frame,
            text="◀ Prev",
            width=70,
            command=self.prev_file,
        )
        self.btn_prev.grid(row=0, column=2, sticky="e", padx=(0, 4))
        self.btn_next = ctk.CTkButton(
            status_frame,
            text="Next ▶",
            width=70,
            command=self.next_file,
        )
        self.btn_next.grid(row=0, column=3, sticky="e")

        # Right (metadata & rules) frame
        self.right_frame = ctk.CTkFrame(self.paned, corner_radius=8)
        self.paned.add(self.right_frame, minsize=480)

        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(2, weight=1)

        # View Switcher
        self.view_switcher = ctk.CTkSegmentedButton(
            self.right_frame,
            values=["Rules + Presets", "Song Edit"],
            command=self.switch_right_view,
        )
        self.view_switcher.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        self.view_switcher.set("Rules + Presets")

        # --- Rules View Frame ---
        self.rules_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.rules_frame.grid_columnconfigure(0, weight=1)
        self.rules_frame.grid_rowconfigure(1, weight=1)

        # Preset controls
        self.preset_component = PresetComponent(self.rules_frame, self)
        self.preset_component.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 6))

        # Rule Tabs
        self.rule_tabs_component = RuleTabsComponent(self.rules_frame, self)
        self.rule_tabs_component.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 6))

        # JSON Editor
        self.json_edit_component = JSONEditComponent(self.rules_frame, self)
        self.json_edit_component.grid(row=2, column=0, sticky="ew", padx=0, pady=(0, 6))
        self.rules_frame.grid_rowconfigure(2, weight=0)

        # Output Preview
        self.output_preview_component = OutputPreviewComponent(self.rules_frame, self)
        self.output_preview_component.grid(row=3, column=0, sticky="ew", padx=0, pady=(0, 8))

        # Filename Editing
        self.filename_component = FilenameComponent(self.rules_frame, self)
        self.filename_component.grid(row=4, column=0, sticky="ew", padx=0, pady=(0, 8))

        # Apply Component
        self.apply_component = ApplyComponent(self.rules_frame, self)
        self.apply_component.grid(row=5, column=0, sticky="ew", padx=0, pady=(0, 8))

        # --- Edit View Frame ---
        self.edit_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.edit_frame.grid_columnconfigure(0, weight=1)
        self.edit_frame.grid_rowconfigure(0, weight=1)

        self.song_edit_component = SongEditComponent(self.edit_frame, self)
        self.song_edit_component.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Show default view
        self.rules_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Set default sash location after window appears
        self.after(150, lambda: self.paned.sash_place(0, int(self.winfo_screenwidth() * 0.62), 0))
        # Initialize rule tab button states
        self.rule_tabs_component.update_rule_tab_buttons()

    def switch_right_view(self, value: str) -> None:
        """Switch between Rules and Song Edit views."""
        if value == "Rules + Presets":
            self.edit_frame.grid_forget()
            self.rules_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        else:
            self.rules_frame.grid_forget()
            self.edit_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))

    # -------------------------
    # FIXED: Tree population with correct column order
    # -------------------------
    def populate_tree_fast(self) -> None:
        """Populate tree with threaded data loading and multi-sort."""
        self.lbl_file_info.configure(text=f"Loading {len(self.song_files)} files...")
        self.update_idletasks()

        def update_loading_progress(current: int, total: int) -> None:
            if self.progress_dialog:
                self.progress_dialog.update_progress(
                    current,
                    total,
                    f"Loading metadata... {current}/{total}",
                )

        def load_file_data_worker() -> None:
            """Load file data in background thread."""
            total = len(self.song_files)

            # Pre-load all file data first
            for i, p in enumerate(self.song_files):
                # Check for cancellation
                if self.progress_dialog and self.progress_dialog.cancelled:
                    self.after_idle(lambda: on_data_loaded(success=False))
                    return

                self.file_manager.get_file_data(p)

                # Update progress every 10 files
                if i % 10 == 0:
                    self.after_idle(lambda idx=i: update_loading_progress(idx, total))

            # Done
            self.after_idle(lambda: on_data_loaded(success=True))

        def on_data_loaded(*, success: bool) -> None:
            if not success or (self.progress_dialog and self.progress_dialog.cancelled):
                self.lbl_file_info.configure(text="Loading cancelled")
                self.song_controls_component.btn_select_folder.configure(state="normal")
                self.operation_in_progress = False
                if self.progress_dialog:
                    self.progress_dialog.destroy()
                    self.progress_dialog = None
                return

            # Get view data from FileManager
            df = self.file_manager.get_view_data(self.song_files)

            # Apply multi-level sorting using Polars
            sorted_df = RuleManager.apply_multi_sort_polars(self.sorting_component.sort_rules, df)

            # Clear tree first
            for it in self.tree_component.tree.get_children():
                self.tree_component.tree.delete(it)

            # Populate tree in batches for better performance
            self.visible_file_indices = []

            # Convert to list of dicts for iteration (still needed for treeview insertion)
            sorted_rows = sorted_df.to_dicts()

            batch_size = 50

            def populate_batch(start_idx: int) -> None:
                end_idx = min(start_idx + batch_size, len(sorted_rows))
                for i in range(start_idx, end_idx):
                    row = sorted_rows[i]
                    orig_idx = row["orig_index"]

                    self.tree_component.tree.insert(
                        "",
                        "end",
                        iid=str(orig_idx),
                        values=self.tree_component.get_row_values(row),
                    )
                    self.visible_file_indices.append(orig_idx)

                # Update progress for tree population
                if self.progress_dialog:
                    self.progress_dialog.update_progress(
                        end_idx,
                        len(sorted_rows),
                        f"Building list... {end_idx}/{len(sorted_rows)}",
                    )

                if end_idx < len(sorted_rows):
                    # Schedule next batch
                    self.after(1, lambda: populate_batch(end_idx))
                else:
                    # All data loaded
                    if self.tree_component.tree.get_children():
                        self.tree_component.tree.selection_set(self.tree_component.tree.get_children()[0])
                        self.on_tree_select()

                    self.lbl_file_info.configure(text=f"Loaded {len(self.song_files)} files")
                    self.song_controls_component.btn_select_folder.configure(state="normal")
                    self.operation_in_progress = False

                    # Calculate statistics after loading
                    self.statistics_component.calculate_statistics()

                    # Close progress dialog after a brief delay
                    if self.progress_dialog:
                        self.after(500, self.progress_dialog.destroy)
                        self.progress_dialog = None

            # Start batch population
            populate_batch(0)

        # Start background loading
        threading.Thread(
            target=load_file_data_worker,
            daemon=True,
        ).start()

    # Cover Image Functions
    def load_current_cover(self) -> None:
        """Load cover image for current song."""
        if self.current_index is None or not self.song_files:
            return

        path = self.song_files[self.current_index]

        # Prevent UI blocking
        current_time = time.time()
        if current_time - self.last_cover_request_time < 0.1:  # TODO: Remove on non-performant mode
            return
        self.last_cover_request_time = current_time

        # Check cache first - this is very fast
        cached_img = self.cover_cache.get(path)
        if cached_img:
            self.display_cover_image(cached_img)
            return

        # Show loading message
        self.song_edit_component.show_loading_cover()

        # Load art when free
        threading.Thread(target=self.load_cover_art, args=(path,), daemon=True).start()

    def load_cover_art(self, path: str) -> None:
        """Request loading of cover art for the given file path."""
        try:
            img = song_utils.read_cover_from_song(path)
            if img:
                ctk_image = self.cover_cache.put(path, img)
                self.display_cover_image(ctk_image)
            else:
                self.song_edit_component.show_no_cover()

        except Exception:
            logger.exception("Error loading cover")
            self.song_edit_component.show_cover_error()

    def display_cover_image(self, ctk_image: ctk.CTkImage | None) -> None:
        """Display cover image centered in the square container."""
        if not ctk_image:
            self.song_edit_component.show_no_cover()
            return

        try:
            self.song_edit_component.display_cover(ctk_image)
        except Exception:
            logger.exception("Error displaying cover")
            self.song_edit_component.show_cover_error("Error loading cover")

    def toggle_theme(self, theme: str | None = None) -> None:
        """Toggle between dark and light themes."""
        try:
            if theme is not None:
                SettingsManager.theme = theme
            elif SettingsManager.theme == "System":
                # If system, switch to explicit dark
                SettingsManager.theme = "Dark"
            elif SettingsManager.theme == "Dark":
                SettingsManager.theme = "Light"
            else:
                SettingsManager.theme = "Dark"

            # Apply the theme
            ctk.set_appearance_mode(SettingsManager.theme)

            # Update all theme-dependent elements
            self.menu_component.update_theme()
            self.tree_component.update_theme()
            self.song_edit_component.update_theme()
            self.json_edit_component.update_theme()
            self.output_preview_component.update_theme()

            # Refresh the tree to apply new styles
            if self.tree_component.tree.get_children():
                self.after(0, self.refresh_tree)

            # Always load cover after theme change
            self.song_edit_component.show_loading_cover()
            if self.current_index is not None:
                self.load_current_cover()
            else:
                self.song_edit_component.show_no_cover()

        except Exception:
            logger.exception("Error toggling theme")

    # -------------------------
    # Settings persistence
    # -------------------------
    def save_settings(self) -> None:
        """Save UI settings to a JSON file."""
        try:
            # sash ratio
            try:
                sash_pos = self.paned.sash_coord(0)[0]  # Get the x position of the sash
                total = self.paned.winfo_width() or 1
                SettingsManager.sash_ratio = float(sash_pos) / float(total)
            except (AttributeError, IndexError, TypeError):
                SettingsManager.sash_ratio = None

            # column order and widths
            try:
                SettingsManager.column_order = self.tree_component.column_order
                widths = {}
                for col in self.tree_component.column_order:
                    try:
                        info = self.tree_component.tree.column(col)
                        widths[col] = int(info.get("width", 0))
                    except Exception:
                        widths[col] = 0
                SettingsManager.column_widths = widths
            except Exception:
                SettingsManager.column_order = self.tree_component.column_order
                SettingsManager.column_widths = {}

            # sort rules
            try:
                SettingsManager.sort_rules = RuleManager.get_sort_rules(self.sorting_component.sort_rules)
            except Exception:
                SettingsManager.sort_rules = []

            # write file
            SettingsManager.save_settings()
        except Exception:
            logger.exception("Error saving settings")

    def load_settings(self) -> None:
        """Load UI settings from JSON file and apply them where possible."""
        # Theme
        try:
            th = SettingsManager.theme
            if th:
                self.current_theme = th
                self.toggle_theme(theme=th)
        except Exception:
            logger.exception("Error loading theme setting")

        try:
            # last folder
            # Check for last folder opened
            self.after_idle(self.check_last_folder)

            # column order & widths
            col_order = SettingsManager.column_order
            col_widths = SettingsManager.column_widths
            if col_order and isinstance(col_order, list):
                # apply order
                self.tree_component.column_order = col_order
                # rebuild columns to new order
                self.tree_component.rebuild_tree_columns()
                # apply widths
                for c, w in (col_widths or {}).items():
                    with contextlib.suppress(Exception):
                        self.tree_component.tree.column(c, width=int(w))
        except Exception:
            logger.exception("Error loading column settings")

        try:
            # sort rules
            sort_rules = SettingsManager.sort_rules or []
            if isinstance(sort_rules, list) and sort_rules:
                # ensure at least one rule exists
                # clear existing additional rules and set values
                # there is always at least one sort rule created in UI
                # set values for existing rules and add extras if needed
                for i, r in enumerate(sort_rules):
                    with contextlib.suppress(Exception):
                        if i < len(self.sorting_component.sort_rules):
                            self.sorting_component.sort_rules[i].field_var.set(
                                r.get("field", MetadataFields.get_ui_keys()[0]),
                            )
                            self.sorting_component.sort_rules[i].order_var.set(r.get("order", "asc"))
                        else:
                            self.sorting_component.add_sort_rule(is_first=False)
                            self.sorting_component.sort_rules[-1].field_var.set(
                                r.get("field", MetadataFields.get_ui_keys()[0]),
                            )
                            self.sorting_component.sort_rules[-1].order_var.set(r.get("order", "asc"))
        except Exception:
            logger.exception("Error loading sort rules")

        try:
            # sash ratio - apply after window is laid out
            sash_ratio = SettingsManager.sash_ratio
            if sash_ratio is not None:

                def apply_ratio(attempts: int = 0) -> None:
                    with contextlib.suppress(Exception):
                        total = self.paned.winfo_width()
                        if total and attempts < 10:
                            pos = int(total * float(sash_ratio))
                            try:
                                self.paned.sash_place(0, pos, 0)
                            except Exception:
                                with contextlib.suppress(Exception):
                                    self.paned.sash_coord(0)[0]
                        # try again shortly if not yet sized
                        elif attempts < 10:
                            self.after(150, lambda: apply_ratio(attempts + 1))

                self.after(200, lambda: apply_ratio(0))
        except Exception:
            logger.exception("Error loading sash ratio")

    def check_last_folder(self) -> None:
        """Check if there is a last opened folder and prompt the user to load it."""
        if not SettingsManager.last_folder_opened or not Path(SettingsManager.last_folder_opened).exists():
            return

        if SettingsManager.auto_reopen_last_folder is True:
            self.select_folder(SettingsManager.last_folder_opened)
            return

        if SettingsManager.auto_reopen_last_folder is False:
            return

        # If None, ask the user
        dialog = ConfirmDialog(
            self,
            "Load Last Folder",
            f"Do you want to load the last opened folder?\n{SettingsManager.last_folder_opened}",
            checkbox_text="Remember my choice",
        )

        if dialog.result:
            if dialog.checkbox_checked:
                SettingsManager.auto_reopen_last_folder = True
                self.save_settings()
            self.select_folder(SettingsManager.last_folder_opened)
        elif dialog.checkbox_checked:  # User said NO and checked "Remember my choice"
            SettingsManager.auto_reopen_last_folder = False
            self.save_settings()

    def _on_close(self) -> None:
        with contextlib.suppress(Exception):
            self.save_settings()

        try:
            self.destroy()
        except Exception:
            with contextlib.suppress(Exception):
                self.quit()

    def update_tree_row(self, index: int, json_data: dict[str, str]) -> None:
        """Update a specific row in the treeview with new JSON data."""
        if index < 0 or index >= len(self.song_files):
            return

        path = self.song_files[index]
        # Create field values dictionary
        field_values = {
            MetadataFields.UI_TITLE: json_data.get(MetadataFields.TITLE) or Path(path).stem,
            MetadataFields.UI_ARTIST: json_data.get(MetadataFields.ARTIST) or "",
            MetadataFields.UI_COVER_ARTIST: json_data.get(MetadataFields.COVER_ARTIST) or "",
            MetadataFields.UI_VERSION: json_data.get(MetadataFields.VERSION) or "",
            MetadataFields.UI_DISC: json_data.get(MetadataFields.DISC) or "",
            MetadataFields.UI_TRACK: json_data.get(MetadataFields.TRACK) or "",
            MetadataFields.UI_DATE: json_data.get(MetadataFields.DATE) or "",
            MetadataFields.UI_COMMENT: json_data.get(MetadataFields.COMMENT) or "",
            MetadataFields.UI_SPECIAL: json_data.get(MetadataFields.SPECIAL) or "",
            MetadataFields.UI_FILE: Path(path).name,
        }

        # Create values tuple in the current column order
        values = tuple(field_values[col] for col in self.tree_component.column_order)

        # Update the treeview item
        self.tree_component.tree.item(str(index), values=values)

    # -------------------------
    # Filename Editing Functions
    # -------------------------
    def rename_current_file(self) -> None:
        """Rename the current file to the new filename."""
        if self.current_index is None:
            return

        current_path = self.song_files[self.current_index]
        current_filename = Path(current_path).name
        new_filename = self.filename_component.filename_var.get().strip()

        if not new_filename:
            messagebox.showwarning("Empty filename", "Please enter a new filename")
            return

        if new_filename == current_filename:
            messagebox.showinfo("No change", "Filename is the same as current")
            return

        # Ensure the new filename has a supported extension
        if not any(new_filename.lower().endswith(ext) for ext in song_utils.SUPPORTED_FILES_TYPES):
            messagebox.showwarning("Invalid filename", "Filename must end with a valid extension")
            return

        # Get directory and construct new path
        directory = Path(current_path).parent
        new_path = str(directory / new_filename)

        # Check if target file already exists
        if Path(new_path).exists():
            result = messagebox.askyesno("File exists", f"A file named '{new_filename}' already exists.\nOverwrite it?")
            if not result:
                return

        # Confirm rename
        result = messagebox.askyesno("Confirm Rename", f"Rename:\n{current_filename}\nTo:\n{new_filename}?")
        if not result:
            return

        # Show renaming indicator
        _original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text=f"Renaming {current_filename}...")
        self.update_idletasks()

        def on_rename_complete(old_name: str, new_name_or_error: str, *, success: bool) -> None:
            if success:
                # Update the file path in our list
                self.song_files[self.current_index] = new_path

                # Update cache entries
                self.file_manager.update_file_path(current_path, new_path)
                self.cover_cache.update_file_path(current_path, new_path)

                # Update treeview
                if self.current_metadata:
                    self.update_tree_row(self.current_index, self.current_metadata.raw_data)

                # Update filename entry to show new name
                self.filename_component.filename_var.set(new_name_or_error)
                self.filename_component.filename_save_btn.configure(state="disabled")

                self.lbl_file_info.configure(text=f"Renamed {old_name} to {new_name_or_error}")
                messagebox.showinfo("Success", f"File renamed successfully!\n\n{old_name} → {new_name_or_error}")
            else:
                self.lbl_file_info.configure(text=f"Failed to rename {old_name}")
                messagebox.showerror("Error", f"Failed to rename file:\n{new_name_or_error}")

        error_message = ""
        try:
            renamed = Path(current_path).rename(new_path)
        except Exception as e:
            error_message = str(e)

        self.after_idle(lambda: on_rename_complete(current_filename, error_message or new_filename, success=renamed))

    # -------------------------
    # File / tree operations
    # -------------------------
    def select_folder(self, folder_path: str | None = None) -> None:
        """Handle folder selection and song scanning with progress dialog."""
        if self.operation_in_progress:
            return

        folder = folder_path
        if not folder:
            folder = filedialog.askdirectory()

        if not folder:
            return

        SettingsManager.last_folder_opened = folder

        self.operation_in_progress = True
        self.song_controls_component.btn_select_folder.configure(state="disabled")

        # Clear cache when loading new folder
        self.display_cover_image(None)
        self.update_idletasks()
        self.song_edit_component.cover_component.update()
        self.file_manager.clear()
        # self.cover_cache.clear()  # Causes issues with reloading

        # Show loading state immediately
        self.lbl_file_info.configure(text="Scanning folder...")
        self.update_idletasks()

        # Create and show progress dialog IMMEDIATELY
        self.progress_dialog = ProgressDialog(self, "Loading Folder")
        self.progress_dialog.update_progress(0, 100, "Finding song files...")

        def update_scan_progress(count: int) -> None:
            if self.progress_dialog:
                self.progress_dialog.update_progress(count, count, f"Found {count} files...")

        # Scan in background thread
        def scan_folder() -> None:
            try:
                files = []
                count = 0

                # Use pathlib for faster file discovery
                for p in Path(folder).rglob("*"):
                    # Check for cancellation
                    if self.progress_dialog and self.progress_dialog.cancelled:
                        self.after_idle(lambda: on_scan_complete(None))
                        return

                    if p.is_file() and p.suffix.lower() in song_utils.SUPPORTED_FILES_TYPES:
                        files.append(str(p))
                        count += 1
                        # Update progress every 10 files
                        if count % 10 == 0:
                            self.after_idle(lambda c=count: update_scan_progress(c))

                self.after_idle(lambda: on_scan_complete(files))
            except Exception:
                logger.exception("Error scanning folder")
                self.after_idle(lambda: on_scan_complete([]))

        def on_scan_complete(files: list[str] | None) -> None:
            if files is None:  # Cancelled
                self.lbl_file_info.configure(text="Scan cancelled")
                self.song_controls_component.btn_select_folder.configure(state="normal")
                self.operation_in_progress = False

                if self.progress_dialog:
                    self.progress_dialog.destroy()
                    self.progress_dialog = None
                return

            self.song_files = files
            if not self.song_files:
                messagebox.showwarning("No files", "No song files found in that folder")
                self.lbl_file_info.configure(text="No files")
                self.song_controls_component.btn_select_folder.configure(state="normal")
                self.operation_in_progress = False
                if self.progress_dialog:
                    self.progress_dialog.destroy()
                    self.progress_dialog = None
                return

            # Update progress for metadata loading
            if self.progress_dialog:
                self.progress_dialog.label.configure(text="Loading file metadata...")
                self.progress_dialog.progress.set(0)

            self.current_folder = folder

            # Use optimized population
            self.populate_tree_fast()

        # Start background scan
        threading.Thread(target=scan_folder, daemon=True).start()

    def refresh_tree(self, *_args: list) -> None:
        """Refresh tree with search filtering and multi-sort. Supports structured filters including version=latest."""
        q_raw = self.song_controls_component.search_var.get().strip()

        # Get view data from FileManager
        df = self.file_manager.get_view_data(self.song_files)

        # Apply search filters
        filters, free_terms = RuleManager.parse_search_query(q_raw)
        filtered_df = RuleManager.apply_search_filter(df, filters, free_terms)

        # Apply multi-level sort
        sorted_df = RuleManager.apply_multi_sort_polars(self.sorting_component.sort_rules, filtered_df)

        # Clear tree
        for it in self.tree_component.tree.get_children():
            self.tree_component.tree.delete(it)
        self.visible_file_indices = []

        # Insert sorted matches into the tree
        sorted_rows = sorted_df.to_dicts()
        for row in sorted_rows:
            orig_idx = row["orig_index"]
            self.tree_component.tree.insert(
                "",
                "end",
                iid=str(orig_idx),
                values=self.tree_component.get_row_values(row),
            )
            self.visible_file_indices.append(orig_idx)

        # Update search info label with count and filter summary
        info = f"{len(self.visible_file_indices)} songs found"
        if filters or free_terms:
            parts = [f"{f['field']} {f['op']} {f['value']}" for f in filters] + [f"'{t}'" for t in free_terms]
            info += " | " + ", ".join(parts)
        self.sorting_component.search_info_label.configure(text=info)

        # Update statistics for filtered results
        self.statistics_component.calculate_statistics()

    def on_tree_select(self, _event: tk.Event | None = None) -> None:
        """Handle tree selection change."""
        sel = self.tree_component.tree.selection()
        # Update selection count
        self.lbl_selection_info.configure(text=f"{len(sel)} song(s) selected")

        if not sel:
            return
        iid = sel[0]
        try:
            idx = int(iid)
        except Exception:
            return
        if idx < 0 or idx >= len(self.song_files):
            return
        self.current_index = idx
        self.load_current()

    def load_current(self) -> None:
        """Load current song data."""
        if self.current_index is None or not self.song_files:
            return
        path = self.song_files[self.current_index]
        self.lbl_file_info.configure(
            text=f"{self.current_index + 1}/{len(self.song_files)}  —  {Path(path).name}",
        )

        # Load metadata
        self.current_metadata = self.file_manager.get_metadata(path)

        # Update components
        self.event_generate("<<JSONEditComponent:UpdateJSON>>")
        self.event_generate("<<FilenameComponent:UpdateFilename>>")

        # FIXED: Update preview FIRST, then load cover
        self.output_preview_component.update_preview()

        # Load cover AFTER preview is updated
        self.load_current_cover()

        # Update Song Edit View
        self.after_idle(lambda: self.song_edit_component.update_view(self.current_metadata))

    def prev_file(self) -> None:
        """Navigate to previous file in the visible list."""
        if not self.visible_file_indices:
            return

        current_visible_index = None
        if self.current_index is not None:
            try:
                current_visible_index = self.visible_file_indices.index(self.current_index)
            except ValueError:
                current_visible_index = None

        if current_visible_index is None or current_visible_index <= 0:
            return

        # Get previous file index from visible list
        prev_index = self.visible_file_indices[current_visible_index - 1]
        self.tree_component.tree.selection_set(str(prev_index))
        self.current_index = prev_index
        self.load_current()

    def next_file(self) -> None:
        """Navigate to next file in the visible list."""
        if not self.visible_file_indices:
            return

        current_visible_index = None
        if self.current_index is not None:
            try:
                current_visible_index = self.visible_file_indices.index(self.current_index)
            except ValueError:
                current_visible_index = None

        if current_visible_index is None or current_visible_index >= len(self.visible_file_indices) - 1:
            return

        # Get next file index from visible list
        next_index = self.visible_file_indices[current_visible_index + 1]
        self.tree_component.tree.selection_set(str(next_index))
        self.current_index = next_index
        self.load_current()

    def on_select_all(self) -> None:
        """Handle select all checkbox toggle."""
        sel = self.song_controls_component.select_all_var.get()
        if sel:
            # select all visible
            self.tree_component.tree.selection_set(self.tree_component.tree.get_children())
        else:
            self.tree_component.tree.selection_remove(self.tree_component.tree.get_children())
        # Update selection count
        self.lbl_selection_info.configure(text=f"{len(self.tree_component.tree.selection())} song(s) selected")

    # -------------------------
    # Rule evaluation
    # -------------------------
    def collect_rules_for_tab(self, key: str) -> list[dict[str, str]]:
        """Key in 'title','artist','album' - Enhanced for AND/OR grouping."""
        container = self.rule_tabs_component.rule_containers.get(key)
        if not container:
            return []
        rules = []
        slaves = container.pack_slaves()
        children = [w for w in slaves if isinstance(w, RuleRow)]

        for i, widget in enumerate(children):
            rule_data = widget.get_rule()
            # Ensure first rule has proper logic flag
            if i == 0:
                rule_data["is_first"] = True
            rules.append(rule_data)

        return rules

    # Apply metadata to files
    # -------------------------
    def apply_to_selected(self) -> None:
        """Apply metadata changes to selected files."""
        if self.operation_in_progress:
            messagebox.showinfo("Operation in progress", "Please wait for the current operation to complete.")
            return

        sel = self.tree_component.tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select rows in the song list first")
            return

        paths = [self.song_files[int(iid)] for iid in sel]

        # Collect rules on main thread BEFORE starting background thread
        title_rules = self.collect_rules_for_tab("title")
        artist_rules = self.collect_rules_for_tab("artist")
        album_rules = self.collect_rules_for_tab("album")

        self.operation_in_progress = True

        # Show immediate feedback
        self.lbl_file_info.configure(text=f"Starting to apply to {len(paths)} files...")
        self.update_idletasks()

        # Create and show progress dialog IMMEDIATELY
        self.progress_dialog = ProgressDialog(self, "Applying Metadata")
        self.progress_dialog.update_progress(0, len(paths), "Starting...")

        def update_apply_progress(current: int, total: int, text: str) -> None:
            if self.progress_dialog:
                self.progress_dialog.update_progress(current, total, text)

        def apply_in_background() -> None:
            """Apply metadata changes in background thread."""
            success_count = 0
            total = len(paths)
            errors = []

            for i, p in enumerate(paths):
                if self.progress_dialog and self.progress_dialog.cancelled:
                    break

                try:
                    metadata = self.file_manager.get_metadata(p)
                    if not metadata.raw_data:
                        errors.append(f"No metadata: {Path(p).name}")
                        continue

                    new_title = RuleManager.apply_rules_list(
                        title_rules,
                        metadata,
                    )
                    new_artist = RuleManager.apply_rules_list(
                        artist_rules,
                        metadata,
                    )
                    new_album = RuleManager.apply_rules_list(
                        album_rules,
                        metadata,
                    )

                    # write tags
                    cover_bytes = None
                    cover_mime = "image/jpeg"

                    if song_utils.write_id3_tags(
                        p,
                        title=new_title,
                        artist=new_artist,
                        album=new_album,
                        track=metadata.track,
                        disc=metadata.disc,
                        date=metadata.date,
                        cover_bytes=cover_bytes,
                        cover_mime=cover_mime,
                    ):
                        success_count += 1
                    else:
                        errors.append(f"Failed to write: {Path(p).name}")

                except Exception as e:
                    errors.append(f"Error with {Path(p).name}: {e!s}")

                # Update progress
                self.after_idle(
                    lambda idx=i, path=p: update_apply_progress(
                        idx + 1,
                        total,
                        f"Applying to {idx + 1}/{total}: {Path(path).name}",
                    ),
                )

            # Done
            self.after_idle(lambda: on_apply_complete((success_count, errors)))

        def on_apply_complete(result: tuple[int, list[str]]) -> None:
            """Handle completion of apply operation."""
            success_count, errors = result

            # Close progress dialog
            if self.progress_dialog:
                self.progress_dialog.destroy()
                self.progress_dialog = None

            # Show results
            if errors:
                error_msg = f"Applied to {success_count}/{len(paths)} files\n\nErrors ({len(errors)}):\n" + "\n".join(
                    errors[:5],
                )  # Show first 5 errors
                if len(errors) > 5:
                    error_msg += f"\n... and {len(errors) - 5} more errors"
                messagebox.showwarning("Application Complete with Errors", error_msg)
            else:
                messagebox.showinfo("Success", f"Successfully applied to {success_count} files")

            self.lbl_file_info.configure(text=f"Applied to {success_count}/{len(paths)} files")
            self.operation_in_progress = False

        # Start background application
        threading.Thread(
            target=apply_in_background,
            daemon=True,
        ).start()

    def apply_to_all(self) -> None:
        """Apply metadata changes to all loaded files with confirmation."""
        if not self.song_files:
            messagebox.showwarning("No files", "Load a folder first")
            return

        # Show confirmation with file count
        res = messagebox.askyesno("Confirm", f"Apply to all {len(self.song_files)} files?")
        if not res:
            return

        # Select all files for processing
        self.tree_component.tree.selection_set(self.tree_component.tree.get_children())
        self.apply_to_selected()

    # -------------------------
    # Preset save/load - UPDATED: Individual files in presets folder
    # -------------------------
    def save_preset(self) -> None:
        """Save current rules as a preset in individual file in presets folder."""
        name = simpledialog.askstring("Preset name", "Preset name:")
        if not name:
            return

        # Show saving indicator
        original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text="Saving preset...")
        self.update_idletasks()

        preset = {
            "title": self.collect_rules_for_tab("title"),
            "artist": self.collect_rules_for_tab("artist"),
            "album": self.collect_rules_for_tab("album"),
        }

        try:
            # Save as individual file in presets folder
            SettingsManager.save_preset(name, preset)

            # update combobox list
            self._reload_presets()
            self.lbl_file_info.configure(text=original_text)
            messagebox.showinfo("Saved", f"Preset '{name}' saved successfully!")
        except Exception as e:
            self.lbl_file_info.configure(text=original_text)
            messagebox.showerror("Error", f"Could not save preset: {e}")

    def _reload_presets(self) -> None:
        """Reload presets from individual files in presets folder."""
        try:
            vals = SettingsManager.list_presets()
            self.preset_component.preset_combo["values"] = vals
        except Exception:
            logger.exception("Error loading presets")
            self.preset_component.preset_combo["values"] = []

    def delete_preset(self) -> None:
        """Delete the selected preset."""
        name = self.preset_component.preset_var.get()
        if not name:
            return

        # Show deleting indicator
        original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text="Deleting preset...")
        self.update_idletasks()

        try:
            confirm = messagebox.askyesno("Delete", f"Delete preset '{name}'?")
            if confirm:
                SettingsManager.delete_preset(name)
                self._reload_presets()
                self.preset_component.preset_var.set("")  # Clear current selection
                self.lbl_file_info.configure(text=original_text)
                messagebox.showinfo("Deleted", f"Preset '{name}' deleted successfully!")
            else:
                self.lbl_file_info.configure(text=original_text)
        except FileNotFoundError:
            self.lbl_file_info.configure(text=original_text)
            messagebox.showwarning("Not Found", f"Preset '{name}' not found")
        except Exception as e:
            self.lbl_file_info.configure(text=original_text)
            messagebox.showerror("Error", f"Could not delete preset: {e}")

    def on_preset_selected(self, _event: tk.Event | None = None) -> None:
        """Handle preset selection from the combobox."""
        name = self.preset_component.preset_var.get()
        if not name:
            return

        # Show loading indicator
        original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text=f"Loading preset '{name}'...")
        self.update_idletasks()

        try:
            try:
                preset = SettingsManager.load_preset(name)
            except FileNotFoundError:
                self.lbl_file_info.configure(text=original_text)
                messagebox.showwarning("Not Found", f"Preset file '{name}.json' not found")
                return

            if not preset:
                self.lbl_file_info.configure(text=original_text)
                return

            # In on_preset_selected method, update the rule loading section:
            for key in ("title", "artist", "album"):
                cont = self.rule_tabs_component.rule_containers.get(key)
                # destroy existing RuleRow children
                for w in cont.winfo_children():
                    w.destroy()
                rules = preset.get(key, [])

                # Apply rule limit when loading from preset
                rules_to_load = rules[: self.max_rules_per_tab]

                for i, r in enumerate(rules_to_load):
                    is_first = i == 0
                    row = RuleRow(
                        cont,
                        DFApp.RULE_OPS,
                        move_callback=self.rule_tabs_component.move_rule,
                        delete_callback=self.rule_tabs_component.delete_rule,
                        is_first=is_first,
                    )
                    row.pack(fill="x", padx=6, pady=3)
                    row.field_var.set(r.get("if_field", MetadataFields.get_json_keys()[0]))
                    row.op_var.set(r.get("if_operator", DFApp.RULE_OPS[0]))
                    row.value_entry.insert(0, r.get("if_value", ""))
                    row.template_entry.insert(0, r.get("then_template", ""))
                    # Set logic for non-first rules
                    if not is_first:
                        row.logic_var.set(r.get("logic", "AND"))

                # Update arrow states
                self.rule_tabs_component.update_rule_button_states(cont)

            # Update button states after loading preset
            self.rule_tabs_component.update_rule_tab_buttons()
            self.lbl_file_info.configure(text=f"Loaded preset '{name}'")
            self.output_preview_component.update_preview()

            # Reset to original text after a delay
            self.after_idle(lambda: self.lbl_file_info.configure(text=original_text))

        except Exception as e:
            self.lbl_file_info.configure(text=original_text)
            messagebox.showerror("Error", f"Could not load preset: {e}")

    # -------------------------
    # Helper methods
    # -------------------------

    def run(self) -> None:
        """Run the main application loop."""
        # load presets combobox
        self._reload_presets()
        self.mainloop()


def main() -> None:
    """Run main entry point."""
    app = DFApp()
    app.run()


if __name__ == "__main__":
    main()

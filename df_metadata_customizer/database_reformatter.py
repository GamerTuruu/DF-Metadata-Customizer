"""Database Reformatter Application - Main Window and Logic."""

import contextlib
import json
import shutil
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import TYPE_CHECKING, Final

import customtkinter as ctk
from PIL import Image

from df_metadata_customizer import image_utils, mp3_utils
from df_metadata_customizer.dialogs import ProgressDialog, StatisticsDialog
from df_metadata_customizer.file_manager import FileManager
from df_metadata_customizer.image_utils import OptimizedImageCache
from df_metadata_customizer.rule_manager import RuleManager
from df_metadata_customizer.settings_manager import SettingsManager
from df_metadata_customizer.song_metadata import MetadataFields
from df_metadata_customizer.widgets import RuleRow, SortRuleRow

if TYPE_CHECKING:
    from df_metadata_customizer.song_metadata import SongMetadata

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("dark-blue")


class DFApp(ctk.CTk):
    """Main application window for Database Reformatter."""

    COLUMN_ORDER: Final = [
        MetadataFields.UI_TITLE,
        MetadataFields.UI_ARTIST,
        MetadataFields.UI_COVER_ARTIST,
        MetadataFields.UI_VERSION,
        MetadataFields.UI_DISC,
        MetadataFields.UI_TRACK,
        MetadataFields.UI_DATE,
        MetadataFields.UI_COMMENT,
        MetadataFields.UI_SPECIAL,
        MetadataFields.UI_FILE,
    ]

    def __init__(self) -> None:
        """Initialize the main application window."""
        super().__init__()
        self.title("Database Reformatter — Metadata Customizer")
        self.geometry("1350x820")
        self.minsize(1100, 700)

        self.settings_manager = SettingsManager()
        self.file_manager = FileManager()

        # Data model
        self.mp3_files = []  # list of file paths
        self.current_index = None
        self.current_metadata: SongMetadata | None = None
        self.current_cover_bytes = None

        self.visible_file_indices = []  # Track visible files for prev/next navigation
        self.progress_dialog = None  # Progress dialog reference
        self.operation_in_progress = False  # Prevent multiple operations

        # Theme management
        self.current_theme = "System"  # Start with system theme
        self.theme_icon_cache = {}  # Cache for theme icons

        # Cover image settings - OPTIMIZED
        self.cover_cache = OptimizedImageCache(max_size=50)  # Optimized cache
        self.current_cover_image = None  # Track current cover to prevent garbage collection
        self.cover_loading_queue = []  # Queue for cover loading requests
        self.cover_loading_thread = None  # Dedicated thread for cover loading
        self.cover_loading_active = False  # Control flag for cover loading thread
        self.last_cover_request_time = 0  # Throttle cover loading

        # Statistics
        self.stats = {
            "all_songs": 0,
            "unique_ta": 0,
            "unique_tac": 0,
            "neuro_solos_unique": 0,
            "neuro_solos_total": 0,
            "evil_solos_unique": 0,
            "evil_solos_total": 0,
            "duets_unique": 0,
            "duets_total": 0,
            "other_unique": 0,
            "other_total": 0,
        }

        # Default fields/operators
        self.rule_ops = [
            "is",
            "contains",
            "starts with",
            "ends with",
            "is empty",
            "is not empty",
            "is latest version",
            "is not latest version",
        ]

        # Maximum number of allowed sort rules (including the primary rule)
        self.max_sort_rules = 5
        self.max_rules_per_tab = 50

        # Build UI
        self._build_ui()
        # Load saved settings (if any)
        with contextlib.suppress(Exception):
            self.load_settings()
        # default presets container
        self.presets = {}

        # Start cover loading thread
        self._start_cover_loading_thread()

        # Ensure settings are saved on exit
        with contextlib.suppress(Exception):
            self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _start_cover_loading_thread(self) -> None:
        """Start the dedicated cover loading thread."""
        self.cover_loading_active = True
        self.cover_loading_thread = threading.Thread(target=self._cover_loading_worker, daemon=True)
        self.cover_loading_thread.start()

    def _cover_loading_worker(self) -> None:
        """Worker thread for loading cover images."""
        while self.cover_loading_active:
            if self.cover_loading_queue:
                path, callback = self.cover_loading_queue.pop(0)
                try:
                    # Load cover image
                    img = mp3_utils.read_cover_from_mp3(path)
                    if img:
                        # Pre-optimize the image for display
                        optimized_img = image_utils.optimize_image_for_display(img)
                        # Cache the optimized image
                        self.cover_cache.put(path, optimized_img)
                        # Call callback in main thread
                        if callback:
                            self.after(0, lambda: callback(optimized_img))
                    elif callback:
                        self.after(0, lambda: callback(None))
                except Exception as e:
                    print(f"Error loading cover in worker: {e}")
                    if callback:
                        self.after(0, lambda: callback(None))
            else:
                # FIXED: Longer sleep to reduce CPU usage
                time.sleep(0.05)  # Increased from 0.01 to 0.05

    def force_preview_update(self) -> None:
        """Force immediate preview update, bypassing any cover loading delays."""
        if self.current_metadata:
            self.update_preview()

    def _build_ui(self) -> None:
        # Use a PanedWindow for draggable splitter
        self.paned = tk.PanedWindow(self, orient="horizontal", sashrelief="raised", sashwidth=6)
        self.paned.pack(fill="both", expand=True, padx=8, pady=8)

        # Left (song list) frame
        self.left_frame = ctk.CTkFrame(self.paned, corner_radius=8)
        self.paned.add(self.left_frame, minsize=620)  # left bigger by default

        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(2, weight=1)  # Treeview row expands
        self.left_frame.grid_rowconfigure(3, weight=0)  # Status row fixed
        self.left_frame.grid_rowconfigure(4, weight=0)  # Bottom status row fixed

        # Top controls: folder select + search + select all
        top_ctl = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        top_ctl.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        top_ctl.grid_columnconfigure(1, weight=1)  # Give more weight to search

        self.btn_select_folder = ctk.CTkButton(top_ctl, text="Select Folder", command=self.select_folder)
        self.btn_select_folder.grid(row=0, column=0, padx=(0, 8))

        self.search_var = tk.StringVar()
        self.entry_search = ctk.CTkEntry(
            top_ctl,
            placeholder_text="Search title / artist / coverartist / disc / track / special / version=latest",
            textvariable=self.search_var,
        )
        self.entry_search.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.entry_search.bind("<KeyRelease>", self.on_search_keyrelease)

        self.select_all_var = tk.BooleanVar(value=False)
        self.chk_select_all = ctk.CTkCheckBox(
            top_ctl,
            text="Select All",
            variable=self.select_all_var,
            command=self.on_select_all,
        )
        self.chk_select_all.grid(row=0, column=2, padx=(0, 0))

        # Sort controls
        sort_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        sort_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))
        sort_frame.grid_columnconfigure(1, weight=1)

        # Sort container for multiple sort rules
        self.sort_container = ctk.CTkFrame(sort_frame, fg_color="transparent")
        self.sort_container.grid(row=0, column=0, columnspan=4, sticky="ew", pady=2)
        self.sort_container.grid_columnconfigure(1, weight=1)

        # Add first sort rule (cannot be deleted)
        self.sort_rules = []
        self.add_sort_rule(is_first=True)

        # Add sort rule button
        self.add_sort_btn = ctk.CTkButton(sort_frame, text="+ Add Sort", width=80, command=lambda: self.add_sort_rule())
        self.add_sort_btn.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Search info label (next to Add Sort)
        self.search_info_label = ctk.CTkLabel(sort_frame, text="", anchor="w")
        self.search_info_label.grid(row=1, column=1, sticky="w", padx=(12, 0))

        # Treeview song list
        tree_frame = ctk.CTkFrame(self.left_frame)
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 4))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Extended columns to show all JSON elements
        self.tree = ttk.Treeview(tree_frame, columns=DFApp.COLUMN_ORDER, show="headings", selectmode="extended")

        # Configure treeview style - will be updated by theme
        self.style = ttk.Style()
        self._update_treeview_style()

        # Configure columns
        column_configs = {
            MetadataFields.UI_TITLE: ("Title", 280, "w"),
            MetadataFields.UI_ARTIST: ("Artist", 275, "w"),
            MetadataFields.UI_COVER_ARTIST: ("Cover Artist", 95, "w"),
            MetadataFields.UI_VERSION: ("Version", 65, "center"),
            MetadataFields.UI_DISC: ("Disc", 35, "center"),
            MetadataFields.UI_TRACK: ("Track", 55, "center"),
            MetadataFields.UI_DATE: ("Date", 85, "center"),
            MetadataFields.UI_COMMENT: ("Comment", 80, "w"),
            MetadataFields.UI_SPECIAL: ("Special", 60, "center"),
            MetadataFields.UI_FILE: ("File", 120, "w"),
        }

        for col in DFApp.COLUMN_ORDER:
            heading, width, anchor = column_configs[col]
            self.tree.heading(col, text=heading)
            # Disable automatic stretching so horizontal scrollbar appears
            self.tree.column(col, width=width, anchor=anchor, stretch=False)

        # Enable column reordering
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.dragged_column = None
        # Track header currently highlighted during drag (for visual feedback)
        self._highlighted_column = None

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        # Double-click to play song
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Vertical scrollbar
        self.tree_scroll_v = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scroll_v.set)

        # Horizontal scrollbar
        self.tree_scroll_h = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=self.tree_scroll_h.set)

        # Grid the tree and scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree_scroll_v.grid(row=0, column=1, sticky="ns")
        self.tree_scroll_h.grid(row=1, column=0, sticky="ew")

        # Status panel - NEW: Simple button that shows popup
        status_btn_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        status_btn_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=(4, 4))
        status_btn_frame.grid_columnconfigure(0, weight=1)

        self.status_btn = ctk.CTkButton(
            status_btn_frame,
            text="📊 Show Statistics 📊",
            command=self.show_statistics_popup,
            fg_color="#444",
            hover_color="#555",
            height=28,
        )
        self.status_btn.grid(row=0, column=0, sticky="w")

        self.status_label = ctk.CTkLabel(status_btn_frame, text="All songs: 0 | Unique (T,A): 0", anchor="w")
        self.status_label.grid(row=0, column=1, sticky="e")

        # Bottom status row (file info + selection info)
        status_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        status_frame.grid(row=4, column=0, sticky="ew", padx=8, pady=(4, 8))
        status_frame.grid_columnconfigure(0, weight=1)

        self.lbl_file_info = ctk.CTkLabel(status_frame, text="No folder selected")
        self.lbl_file_info.grid(row=0, column=0, sticky="w")

        self.lbl_selection_info = ctk.CTkLabel(status_frame, text="0 song(s) selected")
        self.lbl_selection_info.grid(row=0, column=1, sticky="e")

        # Right (metadata & rules) frame
        self.right_frame = ctk.CTkFrame(self.paned, corner_radius=8)
        self.paned.add(self.right_frame, minsize=480)

        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(1, weight=1)  # tab area expands
        self.right_frame.grid_rowconfigure(2, weight=2)  # preview area expands

        # Preset controls with theme toggle
        preset_row = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        preset_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        preset_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(preset_row, text="Presets:").grid(row=0, column=0, padx=(4, 8), sticky="w")
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(preset_row, textvariable=self.preset_var, state="readonly", width=20)
        self.preset_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_selected)

        ctk.CTkButton(preset_row, text="Save Preset", command=self.save_preset, width=80).grid(row=0, column=2, padx=4)
        ctk.CTkButton(preset_row, text="Delete", command=self.delete_preset, width=60).grid(row=0, column=3, padx=4)

        # Theme toggle button - FIXED: Better contrast for moon icon
        self.theme_btn = ctk.CTkButton(
            preset_row,
            text="",
            width=40,
            height=30,
            command=self.toggle_theme,
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
        )
        self.theme_btn.grid(row=0, column=4, padx=(8, 0))
        self._update_theme_button()

        # Tabs for rule builders - FIXED LAYOUT (no blank space)
        self.tabview = ctk.CTkTabview(self.right_frame)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 6))  # Reduced top padding

        # We'll keep rule containers per tab in a dict
        self.rule_containers: dict[str, ctk.CTkFrame] = {}
        for name in ("Title", "Artist", "Album"):
            tab = self.tabview.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(1, weight=1)  # Make the scrollable area expand

            # Create a header frame with label and add button FOR EACH TAB
            header_frame = ctk.CTkFrame(tab, fg_color="transparent")
            header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))
            header_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(header_frame, text=f"{name} Rules", font=ctk.CTkFont(weight="bold")).grid(
                row=0,
                column=0,
                sticky="w",
                padx=8,
            )

            add_btn = ctk.CTkButton(
                header_frame,
                text="+ Add Rule",
                width=80,
                command=lambda n=name: self.add_rule_to_tab(n),
            )
            add_btn.grid(row=0, column=1, padx=8, pady=2, sticky="e")

            wrapper = ctk.CTkFrame(tab)
            wrapper.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
            wrapper.grid_columnconfigure(0, weight=1)
            wrapper.grid_rowconfigure(0, weight=1)

            # Scrollable container for rules
            scroll = ctk.CTkScrollableFrame(wrapper)
            scroll.grid(row=0, column=0, sticky="nsew")
            scroll.grid_columnconfigure(0, weight=1)

            # store container
            self.rule_containers[name.lower()] = scroll

        # Preview area (JSON, Cover, Output)
        preview_outer = ctk.CTkFrame(self.right_frame)
        preview_outer.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))  # Reduced top padding
        preview_outer.grid_columnconfigure(0, weight=2)
        preview_outer.grid_columnconfigure(1, weight=1)
        preview_outer.grid_rowconfigure(0, weight=1)

        # JSON viewer with save button
        json_frame = ctk.CTkFrame(preview_outer)
        json_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        json_frame.grid_rowconfigure(1, weight=1)
        json_frame.grid_columnconfigure(0, weight=1)
        json_frame.grid_columnconfigure(1, weight=0)

        # JSON header with save button
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

        # Configure text widget for theme
        self.json_text = tk.Text(json_frame, wrap="none", height=12)
        self._update_json_text_style()
        self.json_text.grid(row=1, column=0, sticky="nsew", padx=(6, 0), pady=(0, 6))
        self.json_text.bind("<KeyRelease>", self.on_json_changed)
        self.json_scroll = ttk.Scrollbar(json_frame, orient="vertical", command=self.json_text.yview)
        self.json_text.configure(yscrollcommand=self.json_scroll.set)
        self.json_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 6))

        # Cover preview on right - REMOVED: Cover toggle button and "Cover Preview" text
        cover_frame = ctk.CTkFrame(preview_outer)
        cover_frame.grid(row=0, column=1, sticky="nsew")
        cover_frame.grid_rowconfigure(0, weight=1)

        # Cover display only - no header with toggle button
        self.cover_display = ctk.CTkLabel(cover_frame, text="Loading cover...", corner_radius=8, justify="center")
        self.cover_display.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        # Output preview (Title, Artist, Album, Disc, Track, Versions)
        out_frame = ctk.CTkFrame(self.right_frame)
        out_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        out_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(out_frame, text="New Title:").grid(row=0, column=0, sticky="e", padx=(6, 6), pady=(6, 2))
        self.lbl_out_title = ctk.CTkLabel(out_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_title.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=(6, 2))

        ctk.CTkLabel(out_frame, text="New Artist:").grid(row=1, column=0, sticky="e", padx=(6, 6), pady=(2, 2))
        self.lbl_out_artist = ctk.CTkLabel(out_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_artist.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=(2, 2))

        ctk.CTkLabel(out_frame, text="New Album:").grid(row=2, column=0, sticky="e", padx=(6, 6), pady=(2, 6))
        self.lbl_out_album = ctk.CTkLabel(out_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_album.grid(row=2, column=1, sticky="ew", padx=(0, 6), pady=(2, 6))

        # Disc / Track / Versions / Date small labels
        dt_frame = ctk.CTkFrame(out_frame, fg_color="transparent")
        dt_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        dt_frame.grid_columnconfigure((1, 3, 5, 7), weight=1)

        ctk.CTkLabel(dt_frame, text="Disc:").grid(row=0, column=0, sticky="e", padx=(0, 4))
        self.lbl_out_disc = ctk.CTkLabel(dt_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_disc.grid(row=0, column=1, sticky="w", padx=(0, 12))

        ctk.CTkLabel(dt_frame, text="Track:").grid(row=0, column=2, sticky="e", padx=(0, 4))
        self.lbl_out_track = ctk.CTkLabel(dt_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_track.grid(row=0, column=3, sticky="w", padx=(0, 12))

        ctk.CTkLabel(dt_frame, text="All Versions:").grid(row=0, column=4, sticky="e", padx=(0, 4))
        self.lbl_out_versions = ctk.CTkLabel(dt_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_versions.grid(row=0, column=5, sticky="w", padx=(0, 12))

        ctk.CTkLabel(dt_frame, text="Date:").grid(row=0, column=6, sticky="e", padx=(0, 4))
        self.lbl_out_date = ctk.CTkLabel(dt_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_date.grid(row=0, column=7, sticky="w", padx=(0, 12))

        # Filename editing section
        filename_frame = ctk.CTkFrame(self.right_frame)
        filename_frame.grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 8))
        filename_frame.grid_columnconfigure(1, weight=1)
        filename_frame.grid_columnconfigure(2, weight=0)

        ctk.CTkLabel(filename_frame, text="Filename:").grid(row=0, column=0, sticky="e", padx=(6, 6), pady=(6, 2))
        self.filename_var = tk.StringVar()
        self.filename_entry = ctk.CTkEntry(filename_frame, textvariable=self.filename_var)
        self.filename_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=(6, 2))
        self.filename_entry.bind("<KeyRelease>", self.on_filename_changed)

        self.filename_save_btn = ctk.CTkButton(
            filename_frame,
            text="Rename File",
            width=100,
            command=self.rename_current_file,
            state="disabled",
        )
        self.filename_save_btn.grid(row=0, column=2, padx=(0, 6), pady=(6, 2))

        # Update output preview styles
        self._update_output_preview_style()

        # Bottom buttons (Prev/Next/Apply Selected/Apply All) in one row
        bottom = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=8, pady=(0, 8))
        bottom.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(bottom, text="◀ Prev", command=self.prev_file).grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        ctk.CTkButton(bottom, text="Next ▶", command=self.next_file).grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        ctk.CTkButton(bottom, text="Apply to Selected", command=self.apply_to_selected).grid(
            row=0,
            column=2,
            padx=6,
            pady=6,
            sticky="ew",
        )
        ctk.CTkButton(bottom, text="Apply to All", command=self.apply_to_all).grid(
            row=0,
            column=3,
            padx=6,
            pady=6,
            sticky="ew",
        )

        # Set default sash location after window appears
        self.after(150, lambda: self.paned.sash_place(0, int(self.winfo_screenwidth() * 0.62), 0))
        # Initialize rule tab button states
        self.update_rule_tab_buttons()

    # -------------------------
    # NEW: Statistics calculation with improved categorization
    # -------------------------
    def calculate_statistics(self) -> None:
        """Calculate comprehensive statistics about the loaded songs."""
        if not self.mp3_files:
            self.stats = dict.fromkeys(self.stats, 0)
            self._update_status_display()
            print("No files loaded, stats reset to 0")
            return

        # Delegate calculation to FileManager
        self.stats = self.file_manager.calculate_statistics()

        print("Statistics calculated:")
        for key, value in self.stats.items():
            print(f"  {key}: {value}")

        # Update the status display
        self._update_status_display()

    def _update_status_display(self) -> None:
        """Update the main status display."""
        self.status_label.configure(
            text=f"All songs: {self.stats.get('all_songs', 0)} | Unique (T,A): {self.stats.get('unique_ta', 0)}",
        )

    def show_statistics_popup(self) -> None:
        """Show statistics in a popup window."""
        if hasattr(self, "_status_popup") and self._status_popup.winfo_exists():
            self._status_popup.focus_set()
            return

        self._status_popup = StatisticsDialog(self, self.stats)

    # -------------------------
    # NEW: Multi-level Sorting Methods
    # -------------------------
    def add_sort_rule(self, *, is_first: bool = False) -> None:
        """Add a new sort rule row."""
        # Enforce maximum number of sort rules
        if len(self.sort_rules) >= self.max_sort_rules:
            with contextlib.suppress(Exception):
                messagebox.showinfo("Sort limit", f"Maximum of {self.max_sort_rules} sort levels reached")
            return

        row = SortRuleRow(
            self.sort_container,
            move_callback=self.move_sort_rule,
            delete_callback=self.delete_sort_rule,
            is_first=is_first,
        )
        row.pack(fill="x", padx=0, pady=2)
        self.sort_rules.append(row)

        if is_first:
            row.field_var.set(MetadataFields.UI_TITLE)
        else:
            row.field_var.set(MetadataFields.UI_ARTIST)

        # Bind change events to refresh tree
        row.field_menu.configure(command=lambda _val=None: self.refresh_tree())
        row.order_menu.configure(command=lambda _val=None: self.refresh_tree())

        # Update button visibility for all rules
        self.update_sort_rule_buttons()

        # Disable add button if we've reached the max
        if hasattr(self, "add_sort_btn"):
            self.add_sort_btn.configure(state="disabled" if len(self.sort_rules) >= self.max_sort_rules else "normal")

    def move_sort_rule(self, widget: SortRuleRow, direction: int) -> None:
        """Move a sort rule up or down."""
        # Find current index; don't allow the primary (index 0) to be moved
        try:
            idx = self.sort_rules.index(widget)
        except ValueError:
            return

        if idx == 0:
            return  # primary rule cannot be moved

        new_idx = idx + direction

        # Disallow moves that go out of bounds or into the primary slot (0)
        if new_idx < 1 or new_idx >= len(self.sort_rules):
            return

        # Perform the move
        self.sort_rules.pop(idx)
        self.sort_rules.insert(new_idx, widget)

        # Repack and update UI
        self.repack_sort_rules()
        self.update_sort_rule_buttons()
        self.refresh_tree()

    def delete_sort_rule(self, widget: SortRuleRow) -> None:
        """Delete a sort rule (except the first one)."""
        try:
            idx = self.sort_rules.index(widget)
        except ValueError:
            return

        # Don't allow deleting the primary rule at index 0
        if idx == 0:
            return

        # Remove the widget
        self.sort_rules.pop(idx)
        widget.destroy()

        # Repack and refresh
        self.repack_sort_rules()
        self.update_sort_rule_buttons()
        self.refresh_tree()

    def repack_sort_rules(self) -> None:
        """Repack all sort rules in current order."""
        # Clear the container
        for child in self.sort_container.winfo_children():
            child.pack_forget()

        # Repack in current order
        for rule in self.sort_rules:
            rule.pack(fill="x", padx=0, pady=2)
        # Ensure is_first flag is kept in sync with position (only index 0 is primary)
        for i, rule in enumerate(self.sort_rules):
            rule.is_first = i == 0
            try:
                if rule.is_first:
                    rule.sort_label.configure(text="Sort by:")
                else:
                    rule.sort_label.configure(text="then by:")
            except Exception:
                pass

    def update_sort_rule_buttons(self) -> None:
        """Update button visibility for sort rules."""
        for i, rule in enumerate(self.sort_rules):
            if hasattr(rule, "up_btn"):
                # First rule (index 0) is always first and can't be moved up
                # Rule at position 1 can't move up (would become first)
                rule.up_btn.configure(state="normal" if i > 1 else "disabled")
            if hasattr(rule, "down_btn"):
                # Can't move down if it's the last rule or if moving down would make it first
                rule.down_btn.configure(state="normal" if i < len(self.sort_rules) - 1 and i != 0 else "disabled")

        # Also update Add button state according to max allowed rules
        if hasattr(self, "add_sort_btn"):
            with contextlib.suppress(Exception):
                self.add_sort_btn.configure(
                    state="disabled" if len(self.sort_rules) >= self.max_sort_rules else "normal",
                )

    def on_tree_double_click(self, _event: tk.Event) -> None:
        """Play the selected song when double-clicked."""
        sel = self.tree.selection()
        if not sel:
            return

        iid = sel[0]
        try:
            idx = int(iid)
        except Exception:
            return

        if idx < 0 or idx >= len(self.mp3_files):
            return

        try:
            if not mp3_utils.play_song(self.mp3_files[idx]):
                mp3_utils.show_audio_player_instructions()
        except Exception as e:
            messagebox.showerror("Playback Error", f"Could not play file:\n{e!s}")

    def on_json_changed(self, _event: tk.Event | None = None) -> None:
        """Enable/disable JSON save button based on changes."""
        if self.current_index is None or not self.current_metadata:
            self.json_save_btn.configure(state="disabled")
            return

        try:
            current_text = self.json_text.get("1.0", "end-1c").strip()

            original_text = json.dumps(self.current_metadata.raw_data, indent=2, ensure_ascii=False)

            # Enable button only if JSON has changed
            if current_text != original_text:
                # Validate JSON syntax
                try:
                    json.loads(current_text)
                    self.json_save_btn.configure(state="normal")
                except json.JSONDecodeError:
                    self.json_save_btn.configure(state="disabled")
            else:
                self.json_save_btn.configure(state="disabled")
        except Exception:
            self.json_save_btn.configure(state="disabled")

    # -------------------------
    # FIXED: Tree population with correct column order
    # -------------------------
    def populate_tree_fast(self) -> None:
        """Populate tree with threaded data loading and multi-sort."""
        self.lbl_file_info.configure(text=f"Loading {len(self.mp3_files)} files...")
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
            total = len(self.mp3_files)

            # Pre-load all file data first
            for i, p in enumerate(self.mp3_files):
                # Check for cancellation
                if self.progress_dialog and self.progress_dialog.cancelled:
                    self.after(0, lambda: on_data_loaded(success=False))
                    return

                self.file_manager.get_file_data(p)

                # Update progress every 10 files
                if i % 10 == 0:
                    self.after(0, lambda idx=i: update_loading_progress(idx, total))

            # Done
            self.after(0, lambda: on_data_loaded(success=True))

        def on_data_loaded(*, success: bool) -> None:
            if not success or (self.progress_dialog and self.progress_dialog.cancelled):
                self.lbl_file_info.configure(text="Loading cancelled")
                self.btn_select_folder.configure(state="normal")
                self.operation_in_progress = False
                if self.progress_dialog:
                    self.progress_dialog.destroy()
                    self.progress_dialog = None
                return

            # Get view data from FileManager
            df = self.file_manager.get_view_data(self.mp3_files)

            # Apply multi-level sorting using Polars
            sorted_df = RuleManager.apply_multi_sort_polars(self.sort_rules, df)

            # Clear tree first
            for it in self.tree.get_children():
                self.tree.delete(it)

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

                    self.tree.insert("", "end", iid=str(orig_idx), values=self._get_row_values(row))
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
                    if self.tree.get_children():
                        self.tree.selection_set(self.tree.get_children()[0])
                        self.on_tree_select()

                    self.lbl_file_info.configure(text=f"Loaded {len(self.mp3_files)} files")
                    self.btn_select_folder.configure(state="normal")
                    self.operation_in_progress = False

                    # Calculate statistics after loading
                    self.calculate_statistics()

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

    # -------------------------
    # UPDATED: Theme methods to prevent freezing
    # -------------------------
    def _update_treeview_style(self) -> None:
        """Update treeview style based on current theme."""
        try:
            if self.current_theme == "Dark" or (self.current_theme == "System" and ctk.get_appearance_mode() == "Dark"):
                # Dark theme
                self.style.theme_use("default")
                self.style.configure(
                    "Treeview",
                    background="#2b2b2b",
                    foreground="white",
                    fieldbackground="#2b2b2b",
                    borderwidth=0,
                )
                self.style.configure("Treeview.Heading", background="#3b3b3b", foreground="white", relief="flat")
                self.style.map("Treeview", background=[("selected", "#1f6aa5")])
                self.style.map("Treeview.Heading", background=[("active", "#4b4b4b")])
            else:
                # Light theme
                self.style.theme_use("default")
                self.style.configure(
                    "Treeview",
                    background="white",
                    foreground="black",
                    fieldbackground="white",
                    borderwidth=0,
                )
                self.style.configure("Treeview.Heading", background="#f0f0f0", foreground="black", relief="flat")
                self.style.map("Treeview", background=[("selected", "#0078d7")])
                self.style.map("Treeview.Heading", background=[("active", "#e0e0e0")])
        except Exception as e:
            print(f"Error updating treeview style: {e}")

    def _update_json_text_style(self) -> None:
        """Update JSON text widget style based on current theme."""
        try:
            if self.current_theme == "Dark" or (self.current_theme == "System" and ctk.get_appearance_mode() == "Dark"):
                # Dark theme
                self.json_text.configure(bg="#2b2b2b", fg="white", insertbackground="white", selectbackground="#1f6aa5")
            else:
                # Light theme
                self.json_text.configure(bg="white", fg="black", insertbackground="black", selectbackground="#0078d7")
        except Exception as e:
            print(f"Error updating JSON text style: {e}")

    def _update_output_preview_style(self) -> None:
        """Update output preview labels style based on current theme."""
        try:
            if self.current_theme == "Dark" or (self.current_theme == "System" and ctk.get_appearance_mode() == "Dark"):
                # Dark theme
                bg_color = "#3b3b3b"
                text_color = "white"
            else:
                # Light theme
                bg_color = "#e0e0e0"
                text_color = "black"

            # Update all output preview labels (including Date)
            for label in [
                self.lbl_out_title,
                self.lbl_out_artist,
                self.lbl_out_album,
                self.lbl_out_disc,
                self.lbl_out_track,
                self.lbl_out_versions,
                self.lbl_out_date,
            ]:
                label.configure(fg_color=bg_color, text_color=text_color)
        except Exception as e:
            print(f"Error updating output preview style: {e}")

    def _update_theme_button(self) -> None:
        """Update theme button icon based on current theme - Make it look like other buttons."""
        try:
            if self.current_theme == "Dark" or (self.current_theme == "System" and ctk.get_appearance_mode() == "Dark"):
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
        except Exception as e:
            print(f"Error updating theme button: {e}")

    # -------------------------
    # OPTIMIZED: Cover image handling with dedicated thread
    # -------------------------
    def _safe_cover_display_update(self, text: str, clear_image: bool = False) -> None:
        """Safely update cover display without causing Tcl errors."""
        try:
            if clear_image:
                # Clear image reference first using a safer approach
                self.cover_display.configure(image=None)
                self.current_cover_image = None
            self.cover_display.configure(text=text)
        except Exception:
            # If we get an error, try a more aggressive approach
            try:
                self.cover_display.configure(image=None, text=text)
                self.current_cover_image = None
            except Exception:
                # Final fallback - just set text
                with contextlib.suppress(Exception):
                    self.cover_display.configure(text=text)

    def load_current_cover(self) -> None:
        """Load cover image for current song - FIXED: More aggressive throttling."""
        if self.current_index is None or not self.mp3_files:
            return

        path = self.mp3_files[self.current_index]

        # FIXED: More aggressive throttling to prevent UI blocking
        current_time = time.time()
        if current_time - self.last_cover_request_time < 0.3:  # Increased from 100ms to 300ms
            return
        self.last_cover_request_time = current_time

        # Check cache first - this is very fast
        cached_img = self.cover_cache.get(path)
        if cached_img:
            self.display_cover_image(cached_img)
            return

        # Show loading message
        self._safe_cover_display_update("Loading cover...")

        # FIXED: Clear previous cover requests to prevent queue buildup
        self.cover_loading_queue.clear()

        # Add to loading queue for background processing
        self.cover_loading_queue.append((path, self._on_cover_loaded))

    def _on_cover_loaded(self, img: Image.Image | None) -> None:
        """When cover is loaded in background."""
        if img:
            self.display_cover_image(img)
        else:
            self._safe_cover_display_update("No cover", clear_image=True)

    def display_cover_image(self, img: Image.Image | None) -> None:
        """Display cover image centered in the square container."""
        if not img:
            self._safe_cover_display_update("No cover", clear_image=True)
            return

        try:
            # The image is already optimized to fit within 200x200 square
            # Convert to CTkImage for display
            ctk_image = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(img.width, img.height),  # Use the actual dimensions of the optimized image
            )

            # Update display - the label will center the image automatically
            self.cover_display.configure(image=ctk_image, text="")
            self.current_cover_image = ctk_image

        except Exception as e:
            print(f"Error displaying cover: {e}")
            self._safe_cover_display_update("Error loading cover", clear_image=True)

    def toggle_theme(self) -> None:
        """Toggle between dark and light themes."""
        try:
            if self.current_theme == "System":
                # If system, switch to explicit dark
                self.current_theme = "Dark"
            elif self.current_theme == "Dark":
                self.current_theme = "Light"
            else:
                self.current_theme = "Dark"

            # Apply the theme
            ctk.set_appearance_mode(self.current_theme)

            # Update all theme-dependent elements with error handling
            self._update_treeview_style()
            self._update_json_text_style()
            self._update_output_preview_style()
            self._update_theme_button()

            # Refresh the tree to apply new styles - with delay to prevent freezing
            if self.tree.get_children():
                self.after(100, self.refresh_tree)

            # Always load cover after theme change
            self._safe_cover_display_update("Loading cover...")
            if self.current_index is not None:
                self.load_current_cover()
            else:
                self._safe_cover_display_update("No cover", clear_image=True)
        except Exception as e:
            print(f"Error toggling theme: {e}")

    # -------------------------
    # UPDATED: Search with version=latest support
    # -------------------------
    def on_search_keyrelease(self, _event: tk.Event | None = None) -> None:
        """Debounced search handler."""
        if hasattr(self, "_search_after_id"):
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(300, self.refresh_tree)  # 300ms delay

    def on_tree_click(self, event: tk.Event) -> None:
        """Handle column header clicks for reordering."""
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            column = self.tree.identify_column(event.x)
            column_index = int(column.replace("#", "")) - 1
            if 0 <= column_index < len(DFApp.COLUMN_ORDER):
                self.dragged_column = DFApp.COLUMN_ORDER[column_index]
                self.tree.bind("<B1-Motion>", self.on_column_drag)
                self.tree.bind("<ButtonRelease-1>", self.on_column_drop)

    def on_column_drag(self, event: tk.Event) -> None:
        """Visual feedback during column drag."""
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            column = self.tree.identify_column(event.x)
            try:
                column_index = int(column.replace("#", "")) - 1
            except Exception:
                column_index = None

            if column_index is not None and 0 <= column_index < len(DFApp.COLUMN_ORDER):
                target = DFApp.COLUMN_ORDER[column_index]
                # Only update if changed
                if target != self._highlighted_column:
                    # clear previous
                    if self._highlighted_column:
                        with contextlib.suppress(Exception):
                            self.tree.heading(self._highlighted_column, background="")
                    # set new highlight (color depends on theme)
                    try:
                        hl = "#4b94d6" if (self.current_theme == "Light") else "#3b6ea0"
                        self.tree.heading(target, background=hl)
                        self._highlighted_column = target
                    except Exception:
                        self._highlighted_column = None

    def on_column_drop(self, event: tk.Event) -> None:
        """Handle column reordering when dropped."""
        self.tree.unbind("<B1-Motion>")
        self.tree.unbind("<ButtonRelease-1>")
        # clear any header highlight
        if self._highlighted_column:
            with contextlib.suppress(Exception):
                self.tree.heading(self._highlighted_column, background="")
            self._highlighted_column = None

        if self.dragged_column:
            region = self.tree.identify_region(event.x, event.y)
            if region == "heading":
                column = self.tree.identify_column(event.x)
                try:
                    drop_index = int(column.replace("#", "")) - 1
                except Exception:
                    drop_index = None

                if drop_index is not None and 0 <= drop_index < len(DFApp.COLUMN_ORDER):
                    # Reorder the columns
                    current_index = DFApp.COLUMN_ORDER.index(self.dragged_column)
                    if current_index != drop_index:
                        DFApp.COLUMN_ORDER.pop(current_index)
                        DFApp.COLUMN_ORDER.insert(drop_index, self.dragged_column)
                        self.rebuild_tree_columns()

            self.dragged_column = None

    def rebuild_tree_columns(self) -> None:
        """Rebuild tree columns with new order."""
        # Save current selection and scroll position
        selection = self.tree.selection()
        scroll_v = self.tree.yview()
        scroll_h = self.tree.xview()
        # Reconfigure columns
        # Remember previous column order and sizes so we can remap values
        prev_columns = list(self.tree["columns"])

        # Capture current widths and stretch settings to preserve them
        prev_col_width = {}
        prev_col_stretch = {}
        for col in prev_columns:
            try:
                info = self.tree.column(col)
                prev_col_width[col] = int(info.get("width", info.get("minwidth", 100)))
                prev_col_stretch[col] = bool(info.get("stretch", False))
            except Exception:
                prev_col_width[col] = 100
                prev_col_stretch[col] = False

        for col in prev_columns:
            with contextlib.suppress(Exception):
                self.tree.heading(col, text="")

        column_configs = {
            MetadataFields.UI_TITLE: ("Title", 180, "w"),
            MetadataFields.UI_ARTIST: ("Artist", 100, "w"),
            MetadataFields.UI_COVER_ARTIST: ("Cover Artist", 100, "w"),
            MetadataFields.UI_VERSION: ("Version", 70, "center"),
            MetadataFields.UI_DISC: ("Disc", 40, "center"),
            MetadataFields.UI_TRACK: ("Track", 40, "center"),
            MetadataFields.UI_DATE: ("Date", 70, "center"),
            MetadataFields.UI_COMMENT: ("Comment", 120, "w"),
            MetadataFields.UI_SPECIAL: ("Special", 60, "center"),
            MetadataFields.UI_FILE: ("File", 120, "w"),
        }

        # Recreate columns in new order
        new_columns = list(DFApp.COLUMN_ORDER)
        self.tree["columns"] = new_columns

        for col in new_columns:
            heading, fallback_width, anchor = column_configs.get(col, (col, 100, "w"))
            # prefer previous width if available, else fallback
            width = prev_col_width.get(col, fallback_width)
            stretch = prev_col_stretch.get(col, False)
            try:
                self.tree.heading(col, text=heading)
                # Reapply preserved width/stretch to avoid reset after reorder
                self.tree.column(col, width=width, anchor=anchor, stretch=stretch)
            except Exception:
                pass

        # Remap existing item values from prev_columns -> new_columns
        try:
            # Build mapping from field name to index in previous values
            prev_index = {name: idx for idx, name in enumerate(prev_columns)}
            for iid in self.tree.get_children():
                vals = list(self.tree.item(iid, "values") or [])
                # create dict of previous values
                vals_map = {}
                for name, idx in prev_index.items():
                    try:
                        vals_map[name] = vals[idx]
                    except Exception:
                        vals_map[name] = ""

                # Build new values tuple according to new_columns order
                new_vals = [vals_map.get(name, "") for name in new_columns]
                self.tree.item(iid, values=tuple(new_vals))
        except Exception:
            pass

        # Restore selection and scroll position
        if selection:
            with contextlib.suppress(Exception):
                self.tree.selection_set(selection)
        try:
            self.tree.yview_moveto(scroll_v[0])
            self.tree.xview_moveto(scroll_h[0])
        except Exception:
            pass

    # -------------------------
    # Settings persistence
    # -------------------------
    def save_settings(self) -> None:
        """Save UI settings to a JSON file."""
        try:
            data = {}
            # sash ratio
            try:
                sash_pos = self.paned.sashpos(0)
                total = self.paned.winfo_width() or 1
                data["sash_ratio"] = float(sash_pos) / float(total)
            except Exception:
                data["sash_ratio"] = None

            # column order and widths
            try:
                data["column_order"] = DFApp.COLUMN_ORDER
                widths = {}
                for col in DFApp.COLUMN_ORDER:
                    try:
                        info = self.tree.column(col)
                        widths[col] = int(info.get("width", 0))
                    except Exception:
                        widths[col] = 0
                data["column_widths"] = widths
            except Exception:
                data["column_order"] = DFApp.COLUMN_ORDER
                data["column_widths"] = {}

            # sort rules
            try:
                data["sort_rules"] = RuleManager.get_sort_rules(self.sort_rules)
            except Exception:
                data["sort_rules"] = []

            # other UI prefs
            data["theme"] = str(self.current_theme)

            # write file
            self.settings_manager.save_settings(data)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self) -> None:
        """Load UI settings from JSON file and apply them where possible."""
        data = self.settings_manager.load_settings()
        if not data:
            return

        # theme
        with contextlib.suppress(Exception):
            th = data.get("theme")
            if th:
                self.current_theme = th
                ctk.set_appearance_mode(self.current_theme)
                self._update_theme_button()
                self._update_treeview_style()
                self._update_json_text_style()
                self._update_output_preview_style()

            # column order & widths
            col_order = data.get("column_order")
            col_widths = data.get("column_widths", {})
            if col_order and isinstance(col_order, list):
                # apply order
                DFApp.COLUMN_ORDER = col_order
                # rebuild columns to new order
                self.rebuild_tree_columns()
                # apply widths
                for c, w in (col_widths or {}).items():
                    with contextlib.suppress(Exception):
                        self.tree.column(c, width=int(w))

            # sort rules
            sort_rules = data.get("sort_rules") or []
            if isinstance(sort_rules, list) and sort_rules:
                # ensure at least one rule exists
                # clear existing additional rules and set values
                # there is always at least one sort rule created in UI
                # set values for existing rules and add extras if needed
                for i, r in enumerate(sort_rules):
                    with contextlib.suppress(Exception):
                        if i < len(self.sort_rules):
                            self.sort_rules[i].field_var.set(r.get("field", MetadataFields.get_ui_keys()[0]))
                            self.sort_rules[i].order_var.set(r.get("order", "asc"))
                        else:
                                self.add_sort_rule(is_first=False)
                                self.sort_rules[-1].field_var.set(r.get("field", MetadataFields.get_ui_keys()[0]))
                                self.sort_rules[-1].order_var.set(r.get("order", "asc"))

            # sash ratio - apply after window is laid out
            sash_ratio = data.get("sash_ratio")
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
                                    self.paned.sashpos(0)
                        # try again shortly if not yet sized
                        elif attempts < 10:
                            self.after(150, lambda: apply_ratio(attempts + 1))

                self.after(200, lambda: apply_ratio(0))

            # Always load cover if available
            if self.current_index is not None:
                self.load_current_cover()
            else:
                self._safe_cover_display_update("No cover", clear_image=True)

    def _on_close(self) -> None:
        with contextlib.suppress(Exception):
            self.cover_loading_active = False  # Stop the cover loading thread
            self.save_settings()

        try:
            self.destroy()
        except Exception:
            with contextlib.suppress(Exception):
                self.quit()

    def _get_row_values(self, row: dict) -> tuple:
        """Extract and format values for treeview columns from a data row."""
        values = []
        for col in DFApp.COLUMN_ORDER:
            data_key = RuleManager.COL_MAP.get(col)
            if col == MetadataFields.UI_VERSION:
                v = row.get(MetadataFields.VERSION, 0.0)
                val = str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
            else:
                val = row.get(data_key, "") if data_key else ""
            values.append(str(val))
        return tuple(values)

    # -------------------------
    # JSON Editing Functions
    # -------------------------
    def save_json_to_file(self) -> None:
        """Save the edited JSON back to the current MP3 file."""
        if self.current_index is None or not self.mp3_files:
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
        path = self.mp3_files[self.current_index]
        filename = Path(path).name
        result = messagebox.askyesno("Confirm Save", f"Save JSON changes to:\n{filename}?")

        if not result:
            return

        # Show saving indicator
        _original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text=f"Saving JSON to {filename}...")
        self.update_idletasks()

        def save_json() -> tuple[bool, str]:
            # Write the full comment text directly
            success = mp3_utils.write_json_to_mp3(path, full_comment)
            return success, filename

        def on_save_complete(result: tuple[bool, str]) -> None:
            success, filename = result
            if success:
                # Update cache with new data
                self.file_manager.update_file_data(path, json_data)
                self.current_metadata = self.file_manager.get_metadata(path)

                # Update the treeview with new data
                self.update_tree_row(self.current_index, json_data)

                self.lbl_file_info.configure(text=f"JSON saved to {filename}")
                messagebox.showinfo("Success", f"JSON successfully saved to {filename}")

                # Update preview with new data
                self.update_preview()

                # Disable save button after successful save
                self.json_save_btn.configure(state="disabled")
            else:
                self.lbl_file_info.configure(text=f"Failed to save JSON to {filename}")
                messagebox.showerror("Error", f"Failed to save JSON to {filename}")

        threading.Thread(target=lambda: self.after(0, lambda: on_save_complete(save_json())), daemon=True).start()

    def update_tree_row(self, index: int, json_data: dict[str, str]) -> None:
        """Update a specific row in the treeview with new JSON data."""
        if index < 0 or index >= len(self.mp3_files):
            return

        path = self.mp3_files[index]
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
        values = tuple(field_values[col] for col in DFApp.COLUMN_ORDER)

        # Update the treeview item
        self.tree.item(str(index), values=values)

    # -------------------------
    # Filename Editing Functions
    # -------------------------
    def on_filename_changed(self, _event: tk.Event | None = None) -> None:
        """Enable/disable rename button based on filename changes."""
        if self.current_index is None:
            self.filename_save_btn.configure(state="disabled")
            return

        current_path = self.mp3_files[self.current_index]
        current_filename = Path(current_path).name
        new_filename = self.filename_var.get().strip()

        # Enable button only if filename has changed and is not empty
        if new_filename and new_filename != current_filename:
            self.filename_save_btn.configure(state="normal")
        else:
            self.filename_save_btn.configure(state="disabled")

    def rename_current_file(self) -> None:
        """Rename the current file to the new filename."""
        if self.current_index is None:
            return

        current_path = self.mp3_files[self.current_index]
        current_filename = Path(current_path).name
        new_filename = self.filename_var.get().strip()

        if not new_filename:
            messagebox.showwarning("Empty filename", "Please enter a new filename")
            return

        if new_filename == current_filename:
            messagebox.showinfo("No change", "Filename is the same as current")
            return

        # Ensure the new filename has .mp3 extension
        if not new_filename.lower().endswith(".mp3"):
            new_filename += ".mp3"

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

        # Rename in background thread
        def rename_file() -> tuple[bool, str, str]:
            try:
                # Use shutil.move to handle cross-device moves if needed
                shutil.move(current_path, new_path)
            except Exception as e:
                return False, current_filename, str(e)
            return True, current_filename, new_filename

        def on_rename_complete(result: tuple[bool, str, str]) -> None:
            success, old_name, new_name_or_error = result
            if success:
                # Update the file path in our list
                self.mp3_files[self.current_index] = new_path

                # Update cache entries
                self.file_manager.update_file_path(current_path, new_path)

                if current_path in self.cover_cache:
                    self.cover_cache[new_path] = self.cover_cache.pop(current_path)

                # Update treeview
                if self.current_metadata:
                    self.update_tree_row(self.current_index, self.current_metadata.raw_data)

                # Update filename entry to show new name
                self.filename_var.set(new_name_or_error)
                self.filename_save_btn.configure(state="disabled")

                self.lbl_file_info.configure(text=f"Renamed {old_name} to {new_name_or_error}")
                messagebox.showinfo("Success", f"File renamed successfully!\n\n{old_name} → {new_name_or_error}")
            else:
                self.lbl_file_info.configure(text=f"Failed to rename {old_name}")
                messagebox.showerror("Error", f"Failed to rename file:\n{new_name_or_error}")

        threading.Thread(target=lambda: self.after(0, lambda: on_rename_complete(rename_file())), daemon=True).start()

    def move_rule(self, widget: RuleRow, direction: int) -> None:
        """Move a rule up or down."""
        container = widget.master

        # Use pack_slaves to get the current visual order
        slaves = container.pack_slaves()
        children = [w for w in slaves if isinstance(w, RuleRow)]

        try:
            idx = children.index(widget)
        except ValueError:
            return

        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(children):
            return

        # Swap in list
        children.pop(idx)
        children.insert(new_idx, widget)

        # Repack all RuleRows
        for child in children:
            child.pack_forget()

        for i, child in enumerate(children):
            child.pack(fill="x", padx=6, pady=3)
            # Update visual state
            child.set_first(is_first=i == 0)
            child.set_button_states(is_top=i == 0, is_bottom=i == len(children) - 1)

        self.force_preview_update()

    def delete_rule(self, widget: RuleRow) -> None:
        """Delete a rule from its container - UPDATED: With button state update."""
        container = widget.master
        children = [w for w in container.winfo_children() if isinstance(w, RuleRow)]

        if widget not in children:
            return

        # Remove the widget
        widget.destroy()

        # Update button states for remaining rules
        self.after(10, lambda: self.update_rule_button_states(container))

        # Update button states after deletion (rules are now below limit)
        self.update_rule_tab_buttons()
        self.update_preview()

    def add_rule_to_tab(self, tab_name: str) -> None:
        """Add a rule to the specified tab - UPDATED: With rule limit check."""
        container = self.rule_containers.get(tab_name.lower())
        if container:
            # Count current rules in this tab
            current_rules = len([w for w in container.winfo_children() if isinstance(w, RuleRow)])

            # Check if we've reached the limit
            if current_rules >= self.max_rules_per_tab:
                messagebox.showinfo("Rule limit", f"Maximum of {self.max_rules_per_tab} rules reached for {tab_name}")
                return

            self.add_rule(container)

            # Update button states after adding
            self.update_rule_tab_buttons()

    def update_rule_tab_buttons(self) -> None:
        """Update the Add Rule buttons for each tab based on rule counts."""
        for tab_name, container in self.rule_containers.items():
            # Count current rules in this tab
            current_rules = len([w for w in container.winfo_children() if isinstance(w, RuleRow)])

            # Find the Add Rule button for this tab
            # We need to get to the header frame that contains the button
            tab = self.tabview.tab(tab_name.capitalize())
            if tab:
                # The header frame is the first child of the tab (row 0)
                header_frame = tab.grid_slaves(row=0, column=0)
                if header_frame:
                    header_frame = header_frame[0]
                    # The Add Rule button is in column 1 of the header frame
                    add_buttons = header_frame.grid_slaves(row=0, column=1)
                    if add_buttons:
                        add_button = add_buttons[0]
                        # Disable button if max rules reached
                        if current_rules >= self.max_rules_per_tab:
                            add_button.configure(state="disabled")
                        else:
                            add_button.configure(state="normal")

    def add_rule(self, container: ctk.CTkFrame) -> None:
        """Add a rule row to the specified container."""
        # Count current rules to determine if this is the first one
        current_rules = len([w for w in container.winfo_children() if isinstance(w, RuleRow)])
        is_first = current_rules == 0

        row = RuleRow(
            container,
            self.rule_ops,
            move_callback=self.move_rule,
            delete_callback=self.delete_rule,
            is_first=is_first,
        )
        row.pack(fill="x", padx=6, pady=3)

        # default template suggestions based on container tab
        parent_tab = self._container_to_tab(container)
        if parent_tab == "title":
            row.template_entry.insert(0, f"{{{MetadataFields.COVER_ARTIST}}} - {{{MetadataFields.TITLE}}}")
        elif parent_tab == "artist":
            row.template_entry.insert(0, f"{{{MetadataFields.COVER_ARTIST}}}")
        elif parent_tab == "album":
            row.template_entry.insert(0, f"Archive VOL {{{MetadataFields.DISC}}}")

        # FIXED: Use force preview update for immediate response
        def update_callback(*args) -> None:
            self.force_preview_update()

        row.field_var.trace("w", update_callback)
        row.op_var.trace("w", update_callback)
        row.logic_var.trace("w", update_callback)  # Add logic change listener
        row.value_entry.bind("<KeyRelease>", lambda _e: self.force_preview_update())
        row.template_entry.bind("<KeyRelease>", lambda _e: self.force_preview_update())

        # Update button states for all rules in this container
        self.update_rule_button_states(container)

        # Update button states after adding
        self.update_rule_tab_buttons()
        # Initial update
        self.force_preview_update()

    # -------------------------
    # File / tree operations
    # -------------------------
    def select_folder(self) -> None:
        """Handle folder selection and MP3 scanning with progress dialog."""
        if self.operation_in_progress:
            return

        folder = filedialog.askdirectory()
        if not folder:
            return

        self.operation_in_progress = True
        self.btn_select_folder.configure(state="disabled")

        # Clear cache when loading new folder
        self.file_manager.clear()
        self.cover_cache.clear()
        mp3_utils.extract_json_from_mp3.cache_clear()

        # Show loading state immediately
        self.lbl_file_info.configure(text="Scanning folder...")
        self.update_idletasks()

        # Create and show progress dialog IMMEDIATELY
        self.progress_dialog = ProgressDialog(self, "Loading Folder")
        self.progress_dialog.update_progress(0, 100, "Finding MP3 files...")

        def update_scan_progress(count: int) -> None:
            if self.progress_dialog:
                self.progress_dialog.update_progress(count, count, f"Found {count} files...")

        # Scan in background thread
        def scan_folder() -> None:
            try:
                files = []
                count = 0

                # Use pathlib for faster file discovery
                for p in Path(folder).glob("**/*.mp3"):
                    # Check for cancellation
                    if self.progress_dialog and self.progress_dialog.cancelled:
                        self.after(0, lambda: on_scan_complete(None))
                        return

                    if p.is_file() and p.suffix.lower() == ".mp3":
                        files.append(str(p))
                        count += 1
                        # Update progress every 10 files
                        if count % 10 == 0:
                            self.after(0, lambda c=count: update_scan_progress(c))

                self.after(0, lambda: on_scan_complete(files))
            except Exception as e:
                print(f"Error scanning folder: {e}")
                self.after(0, lambda: on_scan_complete([]))

        def on_scan_complete(files: list[str] | None) -> None:
            if files is None:  # Cancelled
                self.lbl_file_info.configure(text="Scan cancelled")
                self.btn_select_folder.configure(state="normal")
                self.operation_in_progress = False

                if self.progress_dialog:
                    self.progress_dialog.destroy()
                    self.progress_dialog = None
                return

            self.mp3_files = files
            if not self.mp3_files:
                messagebox.showwarning("No files", "No mp3 files found in that folder")
                self.lbl_file_info.configure(text="No files")
                self.btn_select_folder.configure(state="normal")
                self.operation_in_progress = False
                if self.progress_dialog:
                    self.progress_dialog.destroy()
                    self.progress_dialog = None
                return

            # Update progress for metadata loading
            if self.progress_dialog:
                self.progress_dialog.label.configure(text="Loading file metadata...")
                self.progress_dialog.progress.set(0)

            # Use optimized population
            self.populate_tree_fast()

        # Start background scan
        threading.Thread(target=scan_folder, daemon=True).start()

    def refresh_tree(self) -> None:
        """Refresh tree with search filtering and multi-sort. Supports structured filters including version=latest."""
        q_raw = self.search_var.get().strip()

        # Get view data from FileManager
        df = self.file_manager.get_view_data(self.mp3_files)

        # Apply search filters
        filters, free_terms = RuleManager.parse_search_query(q_raw)
        filtered_df = RuleManager.apply_search_filter(df, filters, free_terms)

        # Apply multi-level sort
        sorted_df = RuleManager.apply_multi_sort_polars(self.sort_rules, filtered_df)

        # Clear tree
        for it in self.tree.get_children():
            self.tree.delete(it)
        self.visible_file_indices = []

        # Insert sorted matches into the tree
        sorted_rows = sorted_df.to_dicts()
        for row in sorted_rows:
            orig_idx = row["orig_index"]
            self.tree.insert("", "end", iid=str(orig_idx), values=self._get_row_values(row))
            self.visible_file_indices.append(orig_idx)

        # Update search info label with count and filter summary
        info = f"{len(self.visible_file_indices)} songs found"
        if filters or free_terms:
            parts = [f"{f['field']} {f['op']} {f['value']}" for f in filters] + [f"'{t}'" for t in free_terms]
            info += " | " + ", ".join(parts)
        self.search_info_label.configure(text=info)

        # Update statistics for filtered results
        self.calculate_statistics()

    def on_tree_select(self, _event: tk.Event | None = None) -> None:
        """Handle tree selection change."""
        sel = self.tree.selection()
        # Update selection count
        self.lbl_selection_info.configure(text=f"{len(sel)} song(s) selected")

        if not sel:
            return
        iid = sel[0]
        try:
            idx = int(iid)
        except Exception:
            return
        if idx < 0 or idx >= len(self.mp3_files):
            return
        self.current_index = idx
        self.load_current()

    def load_current(self) -> None:
        """Load current song data."""
        if self.current_index is None or not self.mp3_files:
            return
        path = self.mp3_files[self.current_index]
        self.lbl_file_info.configure(
            text=f"{self.current_index + 1}/{len(self.mp3_files)}  —  {Path(path).name}",
        )

        # Load metadata
        self.current_metadata = self.file_manager.get_metadata(path)

        # Show JSON
        self.json_text.delete("1.0", "end")
        if self.current_metadata.raw_data:
            try:
                # FIXED: Ensure proper encoding for JSON dump
                json_str = json.dumps(self.current_metadata.raw_data, indent=2, ensure_ascii=False)
                self.json_text.insert("1.0", json_str)
            except Exception as e:
                print(f"Error displaying JSON: {e}")
                # Fallback: try with ASCII encoding
                try:
                    json_str = json.dumps(self.current_metadata.raw_data, indent=2, ensure_ascii=True)
                    self.json_text.insert("1.0", json_str)
                except Exception:
                    self.json_text.insert("1.0", "Error displaying JSON data")
        else:
            self.json_text.insert("1.0", "No JSON found in comments")

        # Disable JSON save button initially (no changes yet)
        self.json_save_btn.configure(state="disabled")

        # Load current filename
        current_filename = Path(path).name
        self.filename_var.set(current_filename)
        self.filename_save_btn.configure(state="disabled")

        # FIXED: Update preview FIRST, then load cover
        self.update_preview()

        # Load cover AFTER preview is updated
        self.load_current_cover()

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
        self.tree.selection_set(str(prev_index))
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
        self.tree.selection_set(str(next_index))
        self.current_index = next_index
        self.load_current()

    def on_select_all(self) -> None:
        """Handle select all checkbox toggle."""
        sel = self.select_all_var.get()
        if sel:
            # select all visible
            self.tree.selection_set(self.tree.get_children())
        else:
            self.tree.selection_remove(self.tree.get_children())
        # Update selection count
        self.lbl_selection_info.configure(text=f"{len(self.tree.selection())} song(s) selected")

    # -------------------------
    # Rule evaluation & preview
    # -------------------------
    def update_preview(self) -> None:
        """Update the output preview based on current rules and selected JSON."""
        if not self.current_metadata:
            self.lbl_out_title.configure(text="")
            self.lbl_out_artist.configure(text="")
            self.lbl_out_album.configure(text="")
            self.lbl_out_disc.configure(text="")
            self.lbl_out_track.configure(text="")
            self.lbl_out_versions.configure(text="")
            return

        metadata = self.current_metadata

        # FIXED: Use the correct method to collect rules for each tab
        new_title = RuleManager.apply_rules_list(
            self.collect_rules_for_tab("title"),
            metadata,
        )
        new_artist = RuleManager.apply_rules_list(
            self.collect_rules_for_tab("artist"),
            metadata,
        )
        new_album = RuleManager.apply_rules_list(
            self.collect_rules_for_tab("album"),
            metadata,
        )

        # FIXED: Safe text setting for non-ASCII characters
        try:
            self.lbl_out_title.configure(text=new_title)
            self.lbl_out_artist.configure(text=new_artist)
            self.lbl_out_album.configure(text=new_album)
            self.lbl_out_disc.configure(text=metadata.disc)
            self.lbl_out_track.configure(text=metadata.track)
            self.lbl_out_date.configure(text=metadata.date)
        except Exception as e:
            print(f"Error setting preview text: {e}")
            # Fallback: set empty text to avoid freezing
            self.lbl_out_title.configure(text="")
            self.lbl_out_artist.configure(text="")
            self.lbl_out_album.configure(text="")

        # Show all versions for current song (considering title + artist + coverartist)
        song_key = f"{metadata.title}|{metadata.artist}|{metadata.coverartist}"

        versions = self.file_manager.get_song_versions(song_key)
        if versions:
            formatted_versions = []
            for v in versions:
                if isinstance(v, float) and v.is_integer():
                    formatted_versions.append(str(int(v)))
                else:
                    formatted_versions.append(str(v))
            versions_text = ", ".join(formatted_versions)
            self.lbl_out_versions.configure(text=versions_text)
        else:
            self.lbl_out_versions.configure(text="")

    def safe_update_preview(self) -> None:
        """Safe wrapper for update_preview with exception handling."""
        try:
            self.update_preview()
        except Exception as e:
            print(f"Critical error in preview update: {e}")
            # Emergency fallback - clear all previews
            self.lbl_out_title.configure(text="")
            self.lbl_out_artist.configure(text="")
            self.lbl_out_album.configure(text="")
            self.lbl_out_disc.configure(text="")
            self.lbl_out_track.configure(text="")
            self.lbl_out_versions.configure(text="")

    def collect_rules_for_tab(self, key: str) -> list[dict[str, str]]:
        """Key in 'title','artist','album' - Enhanced for AND/OR grouping."""
        container = self.rule_containers.get(key)
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

    def debug_rules(self) -> None:
        """Debug method to see what rules are loaded."""
        print("=== DEBUG RULES ===")
        for tab in ["title", "artist", "album"]:
            rules = self.collect_rules_for_tab(tab)
            print(f"{tab.upper()} rules: {len(rules)}")
            for i, rule in enumerate(rules):
                print(
                    f"  Rule {i}: IF {rule.get('if_field')} {rule.get('if_operator')} '{rule.get('if_value')}' THEN '{rule.get('then_template')}'",
                )
        print("===================")

    # -------------------------
    # Apply metadata to files
    # -------------------------
    def apply_to_selected(self) -> None:
        """Apply metadata changes to selected files."""
        if self.operation_in_progress:
            messagebox.showinfo("Operation in progress", "Please wait for the current operation to complete.")
            return

        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select rows in the song list first")
            return

        paths = [self.mp3_files[int(iid)] for iid in sel]

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

                    if mp3_utils.write_id3_tags(
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

                # Update progress - FORCE UPDATE
                self.after(
                    0,
                    lambda idx=i, path=p: update_apply_progress(
                        idx + 1,
                        total,
                        f"Applying to {idx + 1}/{total}: {Path(path).name}",
                    ),
                )

            # Done
            self.after(0, lambda: on_apply_complete((success_count, errors)))

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
        if not self.mp3_files:
            messagebox.showwarning("No files", "Load a folder first")
            return

        # Show confirmation with file count
        res = messagebox.askyesno("Confirm", f"Apply to all {len(self.mp3_files)} files?")
        if not res:
            return

        # Select all files for processing
        self.tree.selection_set(self.tree.get_children())
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
            self.settings_manager.save_preset(name, preset)

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
            vals = self.settings_manager.list_presets()
            self.preset_combo["values"] = vals
        except Exception as e:
            print(f"Error loading presets: {e}")
            self.preset_combo["values"] = []

    def delete_preset(self) -> None:
        """Delete the selected preset."""
        name = self.preset_var.get()
        if not name:
            return

        # Show deleting indicator
        original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text="Deleting preset...")
        self.update_idletasks()

        try:
            confirm = messagebox.askyesno("Delete", f"Delete preset '{name}'?")
            if confirm:
                self.settings_manager.delete_preset(name)
                self._reload_presets()
                self.preset_var.set("")  # Clear current selection
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
        name = self.preset_var.get()
        if not name:
            return

        # Show loading indicator
        original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text=f"Loading preset '{name}'...")
        self.update_idletasks()

        try:
            try:
                preset = self.settings_manager.load_preset(name)
            except FileNotFoundError:
                self.lbl_file_info.configure(text=original_text)
                messagebox.showwarning("Not Found", f"Preset file '{name}.json' not found")
                return

            if not preset:
                self.lbl_file_info.configure(text=original_text)
                return

            # In on_preset_selected method, update the rule loading section:
            for key in ("title", "artist", "album"):
                cont = self.rule_containers.get(key)
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
                        self.rule_ops,
                        move_callback=self.move_rule,
                        delete_callback=self.delete_rule,
                        is_first=is_first,
                    )
                    row.pack(fill="x", padx=6, pady=3)
                    row.field_var.set(r.get("if_field", MetadataFields.get_json_keys()[0]))
                    row.op_var.set(r.get("if_operator", self.rule_ops[0]))
                    row.value_entry.insert(0, r.get("if_value", ""))
                    row.template_entry.insert(0, r.get("then_template", ""))
                    # Set logic for non-first rules
                    if not is_first:
                        row.logic_var.set(r.get("logic", "AND"))

                # Update arrow states
                self.update_rule_button_states(cont)

            # Update button states after loading preset
            self.update_rule_tab_buttons()
            self.lbl_file_info.configure(text=f"Loaded preset '{name}'")
            self.update_preview()

            # Reset to original text after a delay
            self.after(2000, lambda: self.lbl_file_info.configure(text=original_text))

        except Exception as e:
            self.lbl_file_info.configure(text=original_text)
            messagebox.showerror("Error", f"Could not load preset: {e}")

    # -------------------------
    # Helper methods
    # -------------------------
    def _container_to_tab(self, container: ctk.CTkFrame) -> str:
        """Get tab name from container widget."""
        for tab_name, cont in self.rule_containers.items():
            if cont == container:
                return tab_name
        return "title"

    def update_rule_button_states(self, container: ctk.CTkFrame) -> None:
        """Update button states for rules in a container."""
        slaves = container.pack_slaves()
        children = [w for w in slaves if isinstance(w, RuleRow)]

        for i, child in enumerate(children):
            child.set_first(is_first=i == 0)
            child.set_button_states(is_top=i == 0, is_bottom=i == len(children) - 1)

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

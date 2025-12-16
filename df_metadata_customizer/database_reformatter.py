import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import customtkinter as ctk
from PIL import Image

from df_metadata_customizer.dialogs import ProgressDialog, StatisticsDialog
from df_metadata_customizer.image_utils import OptimizedImageCache
from  df_metadata_customizer import image_utils, mp3_utils
from df_metadata_customizer.widgets import RuleRow, SortRuleRow

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("dark-blue")


class DFApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Database Reformatter — Metadata Customizer")
        self.geometry("1350x820")
        self.minsize(1100, 700)

        # Data model
        self.mp3_files = []  # list of file paths
        self.current_index = None
        self.current_json = None
        self.current_json_prefix = None  # Store the text before JSON
        self.current_cover_bytes = None
        self.latest_versions = {}  # title -> latest version string
        self.song_versions = {}  # title -> [versions]
        # Updated column order to include 'special' and remove forward slash handling
        self.column_order = [
            "title",
            "artist",
            "coverartist",
            "version",
            "disc",
            "track",
            "date",
            "comment",
            "special",
            "file",
        ]
        self.file_data_cache = {}  # Cache for file metadata (stores tuple: (json_data, prefix_text))
        self.scan_thread = None  # Background scanning thread
        self.visible_file_indices = []  # Track visible files for prev/next navigation
        self.progress_dialog = None  # Progress dialog reference
        self.operation_in_progress = False  # Prevent multiple operations

        # Theme management
        self.current_theme = "System"  # Start with system theme
        self.theme_icon_cache = {}  # Cache for theme icons

        # Cover image settings - OPTIMIZED
        self.show_covers = True  # Covers are always ON
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

        # Default fields/operators - UPDATED: Added Special field
        self.rule_fields = [
            "Title",
            "Artist",
            "CoverArtist",
            "Version",
            "Discnumber",
            "Track",
            "Date",
            "Comment",
            "Special",
        ]
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

        # Sort fields - UPDATED: Added special field
        self.sort_fields = [
            "title",
            "artist",
            "coverartist",
            "version",
            "disc",
            "track",
            "date",
            "comment",
            "special",
            "file",
        ]
        # Maximum number of allowed sort rules (including the primary rule)
        self.max_sort_rules = 5
        self.max_rules_per_tab = 50

        # Build UI
        self._build_ui()
        # Load saved settings (if any)
        try:
            self.load_settings()
        except Exception:
            pass
        # default presets container
        self.presets = {}

        # Start cover loading thread
        self._start_cover_loading_thread()

        # Ensure settings are saved on exit
        try:
            self.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

    def _start_cover_loading_thread(self):
        """Start the dedicated cover loading thread"""
        self.cover_loading_active = True
        self.cover_loading_thread = threading.Thread(target=self._cover_loading_worker, daemon=True)
        self.cover_loading_thread.start()

    def _cover_loading_worker(self):
        """Worker thread for loading cover images - FIXED: Better queue management"""
        while self.cover_loading_active:
            if self.cover_loading_queue:
                path, callback = self.cover_loading_queue.pop(0)
                try:
                    # Load cover image
                    img, _ = mp3_utils.read_cover_from_mp3(path)
                    if img:
                        # Pre-optimize the image for display
                        optimized_img = image_utils.optimize_image_for_display(img)
                        # Cache the optimized image
                        self.cover_cache.put(path, optimized_img)
                        # Call callback in main thread
                        if callback:
                            self.after(0, lambda: callback(optimized_img))
                    else:
                        if callback:
                            self.after(0, lambda: callback(None))
                except Exception as e:
                    print(f"Error loading cover in worker: {e}")
                    if callback:
                        self.after(0, lambda: callback(None))
            else:
                # FIXED: Longer sleep to reduce CPU usage
                time.sleep(0.05)  # Increased from 0.01 to 0.05

    def force_preview_update(self):
        """Force immediate preview update, bypassing any cover loading delays"""
        if self.current_json:
            self.update_preview()

    def _build_ui(self):
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
        top_ctl.grid_columnconfigure(2, weight=1)  # Give more weight to search

        self.btn_select_folder = ctk.CTkButton(top_ctl, text="Select Folder", command=self.select_folder)
        self.btn_select_folder.grid(row=0, column=0, padx=(0, 8))

        self.btn_scan_versions = ctk.CTkButton(top_ctl, text="Scan Versions", command=self.scan_versions)
        self.btn_scan_versions.grid(row=0, column=1, padx=(0, 8))

        self.search_var = tk.StringVar()
        self.entry_search = ctk.CTkEntry(
            top_ctl,
            placeholder_text="Search title / artist / coverartist / disc / track / special / version=latest",
            textvariable=self.search_var,
        )
        self.entry_search.grid(row=0, column=2, sticky="ew", padx=(0, 8))
        self.entry_search.bind("<KeyRelease>", self.on_search_keyrelease)

        self.select_all_var = tk.BooleanVar(value=False)
        self.chk_select_all = ctk.CTkCheckBox(
            top_ctl, text="Select All", variable=self.select_all_var, command=self.on_select_all
        )
        self.chk_select_all.grid(row=0, column=3, padx=(0, 0))

        # Sort controls - NEW MULTI-LEVEL SORTING
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
        self.add_sort_btn = ctk.CTkButton(sort_frame, text="+ Add Sort", width=80, command=self.add_sort_rule)
        self.add_sort_btn.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Search info label (next to Add Sort)
        self.search_info_label = ctk.CTkLabel(sort_frame, text="", anchor="w")
        self.search_info_label.grid(row=1, column=1, sticky="w", padx=(12, 0))

        # Treeview song list
        tree_frame = ctk.CTkFrame(self.left_frame)
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 4))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Extended columns to show all JSON elements including Comment and Special
        columns = tuple(self.column_order)
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="extended")

        # Configure treeview style - will be updated by theme
        self.style = ttk.Style()
        self._update_treeview_style()

        # Configure columns - UPDATED: Added special column
        column_configs = {
            "title": ("Title", 280, "w"),
            "artist": ("Artist", 275, "w"),
            "coverartist": ("Cover Artist", 95, "w"),
            "version": ("Version", 65, "center"),
            "disc": ("Disc", 35, "center"),
            "track": ("Track", 55, "center"),
            "date": ("Date", 85, "center"),
            "comment": ("Comment", 80, "w"),
            "special": ("Special", 60, "center"),
            "file": ("File", 120, "w"),
        }

        for col in self.column_order:
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
        self.rule_containers = {}
        for name in ("Title", "Artist", "Album"):
            tab = self.tabview.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(1, weight=1)  # Make the scrollable area expand

            # Create a header frame with label and add button FOR EACH TAB
            header_frame = ctk.CTkFrame(tab, fg_color="transparent")
            header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))
            header_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(header_frame, text=f"{name} Rules", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, sticky="w", padx=8
            )

            add_btn = ctk.CTkButton(
                header_frame, text="+ Add Rule", width=80, command=lambda n=name: self.add_rule_to_tab(n)
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
            json_header, text="Save JSON", width=80, command=self.save_json_to_file, state="disabled"
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
    def calculate_statistics(self):
        """Calculate comprehensive statistics about the loaded songs"""
        if not self.mp3_files:
            self.stats = {key: 0 for key in self.stats.keys()}
            self._update_status_display()
            print("No files loaded, stats reset to 0")
            return

        # Initialize counters
        unique_ta = set()
        unique_tac = set()
        neuro_solos_unique = set()
        neuro_solos_total = 0
        evil_solos_unique = set()
        evil_solos_total = 0
        duets_unique = set()
        duets_total = 0
        other_unique = set()
        other_total = 0

        # Process all files
        processed = 0
        for file_path in self.mp3_files:
            jsond = self.get_file_data(file_path)
            if not jsond:
                continue

            title = jsond.get("Title", "").strip()
            artist = jsond.get("Artist", "").strip()
            coverartist = jsond.get("CoverArtist", "").strip()

            # Skip if missing essential data
            if not title:
                continue

            # Unique combinations
            ta_key = f"{title}|{artist}"
            tac_key = f"{title}|{artist}|{coverartist}"

            unique_ta.add(ta_key)
            unique_tac.add(tac_key)

            # Categorize based on CoverArtist
            if coverartist == "Neuro & Evil":
                duets_unique.add(ta_key)
                duets_total += 1
            elif coverartist == "Neuro":
                neuro_solos_unique.add(ta_key)
                neuro_solos_total += 1
            elif coverartist == "Evil":
                evil_solos_unique.add(ta_key)
                evil_solos_total += 1
            else:
                other_unique.add(ta_key)
                other_total += 1

            processed += 1
            if processed % 100 == 0:
                print(f"Processed {processed}/{len(self.mp3_files)} files...")

        # Update statistics
        self.stats = {
            "all_songs": len(self.mp3_files),
            "unique_ta": len(unique_ta),
            "unique_tac": len(unique_tac),
            "neuro_solos_unique": len(neuro_solos_unique),
            "neuro_solos_total": neuro_solos_total,
            "evil_solos_unique": len(evil_solos_unique),
            "evil_solos_total": evil_solos_total,
            "duets_unique": len(duets_unique),
            "duets_total": duets_total,
            "other_unique": len(other_unique),
            "other_total": other_total,
        }

        print(f"Statistics calculated:")
        for key, value in self.stats.items():
            print(f"  {key}: {value}")

        # Update the status display
        self._update_status_display()

    def _update_status_display(self):
        """Update the main status display"""
        self.status_label.configure(
            text=f"All songs: {self.stats.get('all_songs', 0)} | Unique (T,A): {self.stats.get('unique_ta', 0)}"
        )

    def show_statistics_popup(self):
        """Show statistics in a popup window"""
        if hasattr(self, "_status_popup") and self._status_popup.winfo_exists():
            self._status_popup.focus_set()
            return

        self._status_popup = StatisticsDialog(self, self.stats)

    # -------------------------
    # NEW: Multi-level Sorting Methods
    # -------------------------
    def add_sort_rule(self, is_first=False):
        """Add a new sort rule row"""
        # Enforce maximum number of sort rules
        if len(self.sort_rules) >= self.max_sort_rules:
            try:
                messagebox.showinfo("Sort limit", f"Maximum of {self.max_sort_rules} sort levels reached")
            except Exception:
                pass
            return

        row = SortRuleRow(
            self.sort_container,
            self.sort_fields,
            move_callback=self.move_sort_rule,
            delete_callback=self.delete_sort_rule,
            is_first=is_first,
        )
        row.pack(fill="x", padx=0, pady=2)
        self.sort_rules.append(row)

        # Set default values - TITLE BY DEFAULT instead of disc
        if is_first:
            row.field_var.set("title")  # Changed from "disc" to "title"
        else:
            row.field_var.set("artist")  # Changed from "title" to "artist"

        # Bind change events to refresh tree
        row.field_menu.configure(command=lambda val=None: self.refresh_tree())
        row.order_menu.configure(command=lambda val=None: self.refresh_tree())

        # Update button visibility for all rules
        self.update_sort_rule_buttons()

        # Disable add button if we've reached the max
        if hasattr(self, "add_sort_btn"):
            self.add_sort_btn.configure(state="disabled" if len(self.sort_rules) >= self.max_sort_rules else "normal")

    def move_sort_rule(self, widget, direction):
        """Move a sort rule up or down"""
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

    def delete_sort_rule(self, widget):
        """Delete a sort rule (except the first one)"""
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

    def repack_sort_rules(self):
        """Repack all sort rules in current order"""
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

    def update_sort_rule_buttons(self):
        """Update button visibility for sort rules"""
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
            try:
                self.add_sort_btn.configure(
                    state="disabled" if len(self.sort_rules) >= self.max_sort_rules else "normal"
                )
            except Exception:
                pass

    def get_sort_rules(self):
        """Get list of sort rules as dictionaries"""
        return [rule.get_sort_rule() for rule in self.sort_rules]

    def apply_multi_sort(self, file_data):
        """Apply multiple sort rules to file data"""
        if not self.sort_rules:
            return file_data

        rules = self.get_sort_rules()

        def sort_key(item):
            """Create a sort key based on multiple rules"""
            key_parts = []
            for rule in rules:
                field = rule["field"]
                order = rule["order"]

                # Get the value for this field (item[0] is index, rest are data)
                field_index = [
                    "title",
                    "artist",
                    "coverartist",
                    "version",
                    "disc",
                    "track",
                    "date",
                    "comment",
                    "special",
                    "file",
                ].index(field)
                value = item[field_index + 1]  # +1 because item[0] is the original index

                # Convert to appropriate type for sorting
                if field in ["disc", "track", "special"]:
                    try:
                        value = int(value) if value else 0
                    except (ValueError, TypeError):
                        value = 0
                elif field in ["version"]:
                    try:
                        # Try to extract numbers from version string
                        nums = re.findall(r"\d+", str(value))
                        value = int(nums[0]) if nums else 0
                    except (ValueError, TypeError):
                        value = 0
                else:
                    value = str(value).lower()

                # Reverse order if descending
                if order == "desc":
                    if isinstance(value, (int, float)):
                        value = -value
                    else:
                        # For strings, we'll handle in the sort function
                        pass

                key_parts.append(value)
            return tuple(key_parts)

        # Sort the data
        try:
            sorted_data = sorted(file_data, key=sort_key)

            # For descending string sorts, we need to handle them separately
            for i, rule in enumerate(rules):
                if rule["order"] == "desc" and rule["field"] in [
                    "title",
                    "artist",
                    "coverartist",
                    "comment",
                    "file",
                    "date",
                ]:
                    # Reverse the order for this specific field level
                    # This is a simplified approach - for true multi-level descending sorts,
                    # we'd need a more complex algorithm
                    if i == 0:  # Only apply to primary sort for simplicity
                        sorted_data.reverse()
                    break

        except Exception as e:
            print(f"Sorting error: {e}")
            return file_data

        return sorted_data

    def on_tree_double_click(self, event):
        """Play the selected song when double-clicked"""
        sel = self.tree.selection()
        if not sel:
            return

        iid = sel[0]
        try:
            idx = int(iid)
        except:
            return

        if idx < 0 or idx >= len(self.mp3_files):
            return

        try:
            if not mp3_utils.play_song(self.mp3_files[idx]):
                self.show_audio_player_instructions()
        except Exception as e:
            messagebox.showerror("Playback Error", f"Could not play file:\n{str(e)}")

    def show_audio_player_instructions(self):
        """Show instructions for installing audio players on Ubuntu"""
        instructions = """To play audio files, you need a media player installed.

    Recommended players for Ubuntu:
    1. mpv (lightweight): sudo apt install mpv
    2. VLC (full-featured): sudo apt install vlc
    3. Rhythmbox (music player): sudo apt install rhythmbox

    After installation, try double-clicking again."""

        messagebox.showinfo("Media Player Required", instructions)

    # -------------------------
    # NEW: JSON change detection
    # -------------------------
    def on_json_changed(self, event=None):
        """Enable/disable JSON save button based on changes"""
        if self.current_index is None or not self.current_json:
            self.json_save_btn.configure(state="disabled")
            return

        try:
            current_text = self.json_text.get("1.0", "end-1c").strip()

            # Reconstruct original JSON with prefix
            original_json = {}
            if self.current_json_prefix:
                original_json["_prefix"] = self.current_json_prefix
            if self.current_json:
                original_json.update(self.current_json)

            original_text = json.dumps(original_json, indent=2, ensure_ascii=False)

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
    def populate_tree_fast(self):
        """OPTIMIZED: Populate tree with threaded data loading and multi-sort"""
        self.lbl_file_info.configure(text=f"Loading {len(self.mp3_files)} files...")
        self.update_idletasks()

        def load_file_data_batch():
            """Load file data in batches for better performance"""
            file_data = []
            total = len(self.mp3_files)

            # Pre-load all file data first
            for i, p in enumerate(self.mp3_files):
                jsond, prefix = self.get_file_data_with_prefix(p)
                # Create a dictionary with all field values
                field_values = {
                    "title": jsond.get("Title") or os.path.splitext(os.path.basename(p))[0],
                    "artist": jsond.get("Artist") or "",
                    "coverartist": jsond.get("CoverArtist") or "",
                    "version": jsond.get("Version") or "",
                    "disc": jsond.get("Discnumber") or "",
                    "track": jsond.get("Track") or "",
                    "date": jsond.get("Date") or "",
                    "comment": jsond.get("Comment") or "",
                    "special": jsond.get("Special") or "",
                    "file": os.path.basename(p),
                }

                # Store the original index and field values
                file_data.append((i, field_values))

                # Update progress every 10 files
                if i % 10 == 0 and self.progress_dialog:
                    if not self.progress_dialog.update_progress(i, total, f"Loading metadata... {i}/{total}"):
                        return None

            return file_data

        def on_data_loaded(file_data):
            if file_data is None or (self.progress_dialog and self.progress_dialog.cancelled):
                self.lbl_file_info.configure(text="Loading cancelled")
                self.btn_select_folder.configure(state="normal")
                self.operation_in_progress = False
                if self.progress_dialog:
                    self.progress_dialog.destroy()
                    self.progress_dialog = None
                return

            # Apply multi-level sorting
            sorted_data = self.apply_multi_sort_with_dict(file_data)

            # Clear tree first
            for it in self.tree.get_children():
                self.tree.delete(it)

            # Populate tree in batches for better performance
            self.visible_file_indices = []
            batch_size = 50

            def populate_batch(start_idx):
                end_idx = min(start_idx + batch_size, len(sorted_data))
                for i in range(start_idx, end_idx):
                    orig_idx, field_values = sorted_data[i]
                    # Create values tuple in the current column order
                    values = tuple(field_values[col] for col in self.column_order)
                    self.tree.insert("", "end", iid=str(orig_idx), values=values)
                    self.visible_file_indices.append(orig_idx)

                # Update progress for tree population
                if self.progress_dialog:
                    self.progress_dialog.update_progress(
                        end_idx, len(sorted_data), f"Building list... {end_idx}/{len(sorted_data)}"
                    )

                if end_idx < len(sorted_data):
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

                    # Auto-scan versions after loading
                    self.after(500, self.auto_scan_versions)

                    # Close progress dialog after a brief delay
                    if self.progress_dialog:
                        self.after(500, self.progress_dialog.destroy)
                        self.progress_dialog = None

            # Start batch population
            populate_batch(0)

        # Start background loading
        threading.Thread(
            target=lambda: self.after(0, lambda: on_data_loaded(load_file_data_batch())), daemon=True
        ).start()

    def apply_multi_sort_with_dict(self, file_data):
        """Apply multiple sort rules to file data stored as dictionaries"""
        if not self.sort_rules:
            return file_data

        rules = self.get_sort_rules()

        def sort_key(item):
            """Create a sort key based on multiple rules"""
            orig_idx, field_values = item
            key_parts = []
            for rule in rules:
                field = rule["field"]
                order = rule["order"]

                # Get the value for this field from the dictionary
                value = field_values.get(field, "")

                # Convert to appropriate type for sorting
                if field in ["disc", "track", "special"]:
                    try:
                        value = int(value) if value else 0
                    except (ValueError, TypeError):
                        value = 0
                elif field in ["version"]:
                    try:
                        # Try to extract numbers from version string
                        nums = re.findall(r"\d+", str(value))
                        value = int(nums[0]) if nums else 0
                    except (ValueError, TypeError):
                        value = 0
                else:
                    value = str(value).lower()

                # Reverse order if descending
                if order == "desc":
                    if isinstance(value, (int, float)):
                        value = -value
                    else:
                        # For strings, we'll handle in the sort function
                        pass

                key_parts.append(value)
            return tuple(key_parts)

        # Sort the data
        try:
            sorted_data = sorted(file_data, key=sort_key)

            # For descending string sorts, we need to handle them separately
            for i, rule in enumerate(rules):
                if rule["order"] == "desc" and rule["field"] in [
                    "title",
                    "artist",
                    "coverartist",
                    "comment",
                    "file",
                    "date",
                ]:
                    # Reverse the order for this specific field level
                    # This is a simplified approach - for true multi-level descending sorts,
                    # we'd need a more complex algorithm
                    if i == 0:  # Only apply to primary sort for simplicity
                        sorted_data.reverse()
                    break

        except Exception as e:
            print(f"Sorting error: {e}")
            return file_data

        return sorted_data

    # -------------------------
    # NEW: File data methods with prefix support
    # -------------------------
    def get_file_data_with_prefix(self, file_path):
        """Get both JSON data and prefix text - FIXED: Better encoding handling"""
        if file_path not in self.file_data_cache:
            jsond, prefix = mp3_utils.extract_json_from_mp3_cached(file_path) or ({}, "")

            # FIXED: Clean up any encoding issues in the JSON data
            if jsond:
                cleaned_jsond = {}
                for key, value in jsond.items():
                    if isinstance(value, bytes):
                        try:
                            cleaned_jsond[key] = value.decode("utf-8")
                        except UnicodeDecodeError:
                            try:
                                cleaned_jsond[key] = value.decode("latin-1")
                            except:
                                cleaned_jsond[key] = str(value)
                    else:
                        cleaned_jsond[key] = value
                jsond = cleaned_jsond

            self.file_data_cache[file_path] = (jsond, prefix)
        return self.file_data_cache[file_path]

    def get_file_data(self, file_path):
        """Get cached file data with fallback (backward compatibility)"""
        jsond, prefix = self.get_file_data_with_prefix(file_path)
        return jsond

    # -------------------------
    # NEW: Auto-scan versions
    # -------------------------
    def auto_scan_versions(self):
        """Automatically scan versions after loading a folder"""
        if not self.mp3_files:
            return

        def scan_in_background():
            song_versions = {}
            total = len(self.mp3_files)
            completed = 0

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(self.get_file_data, p): p for p in self.mp3_files}
                for future in as_completed(futures):
                    p = futures[future]
                    try:
                        j = future.result()
                        if not j:
                            continue
                        title = j.get("Title", "")
                        artist = j.get("Artist", "")
                        coverartist = j.get("CoverArtist", "")
                        version = j.get("Version", "0")

                        # Create a unique key that considers title, artist, AND coverartist
                        song_key = f"{title}|{artist}|{coverartist}"

                        if song_key not in song_versions:
                            song_versions[song_key] = []
                        song_versions[song_key].append(version)
                    except Exception as e:
                        print(f"Error scanning {p}: {e}")
                    finally:
                        completed += 1

            # Compute latest versions
            latest_versions = {}
            for song_key, versions in song_versions.items():
                parsed = []
                for v in versions:
                    nums = re.findall(r"\d+", str(v))
                    if nums:
                        parsed.append([int(x) for x in nums])
                    else:
                        parsed.append([0])
                # find max by lexicographic comparison
                max_idx = 0
                for i, p in enumerate(parsed):
                    if p > parsed[max_idx]:
                        max_idx = i
                latest_versions[song_key] = versions[max_idx]

            return song_versions, latest_versions

        def on_scan_complete(result):
            self.song_versions, self.latest_versions = result
            # Update preview to show versions
            self.update_preview()

        # Start background scanning silently (no UI feedback)
        threading.Thread(
            target=lambda: self.after(0, lambda: on_scan_complete(scan_in_background())), daemon=True
        ).start()

    # -------------------------
    # UPDATED: Theme methods to prevent freezing
    # -------------------------
    def _update_treeview_style(self):
        """Update treeview style based on current theme"""
        try:
            if self.current_theme == "Dark" or (self.current_theme == "System" and ctk.get_appearance_mode() == "Dark"):
                # Dark theme
                self.style.theme_use("default")
                self.style.configure(
                    "Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0
                )
                self.style.configure("Treeview.Heading", background="#3b3b3b", foreground="white", relief="flat")
                self.style.map("Treeview", background=[("selected", "#1f6aa5")])
                self.style.map("Treeview.Heading", background=[("active", "#4b4b4b")])
            else:
                # Light theme
                self.style.theme_use("default")
                self.style.configure(
                    "Treeview", background="white", foreground="black", fieldbackground="white", borderwidth=0
                )
                self.style.configure("Treeview.Heading", background="#f0f0f0", foreground="black", relief="flat")
                self.style.map("Treeview", background=[("selected", "#0078d7")])
                self.style.map("Treeview.Heading", background=[("active", "#e0e0e0")])
        except Exception as e:
            print(f"Error updating treeview style: {e}")

    def _update_json_text_style(self):
        """Update JSON text widget style based on current theme"""
        try:
            if self.current_theme == "Dark" or (self.current_theme == "System" and ctk.get_appearance_mode() == "Dark"):
                # Dark theme
                self.json_text.configure(bg="#2b2b2b", fg="white", insertbackground="white", selectbackground="#1f6aa5")
            else:
                # Light theme
                self.json_text.configure(bg="white", fg="black", insertbackground="black", selectbackground="#0078d7")
        except Exception as e:
            print(f"Error updating JSON text style: {e}")

    def _update_output_preview_style(self):
        """Update output preview labels style based on current theme"""
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

    def _update_theme_button(self):
        """Update theme button icon based on current theme - Make it look like other buttons"""
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
    def _safe_cover_display_update(self, text, clear_image=False):
        """Safely update cover display without causing Tcl errors"""
        try:
            if clear_image:
                # Clear image reference first using a safer approach
                self.cover_display.configure(image="")
                self.current_cover_image = None
            self.cover_display.configure(text=text)
        except Exception as e:
            # If we get an error, try a more aggressive approach
            try:
                self.cover_display.configure(image="", text=text)
                self.current_cover_image = None
            except Exception:
                # Final fallback - just set text
                try:
                    self.cover_display.configure(text=text)
                except Exception:
                    pass

    def load_current_cover(self):
        """Load cover image for current song - FIXED: More aggressive throttling"""
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

    def _on_cover_loaded(self, img):
        """Callback when cover is loaded in background"""
        if img:
            self.display_cover_image(img)
        else:
            self._safe_cover_display_update("No cover", clear_image=True)

    def display_cover_image(self, img):
        """Display cover image centered in the square container"""
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

    def toggle_theme(self):
        """Toggle between dark and light themes"""
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
    def on_search_keyrelease(self, event=None):
        """Debounced search handler"""
        if hasattr(self, "_search_after_id"):
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(300, self.refresh_tree)  # 300ms delay

    def _parse_search_query(self, q):
        """Parse search query into structured filters and free-text terms.

        Supports expressions like: Artist=randomName Disc=3.2 version=latest
        Operators supported: ==, !=, >=, <=, >, <, =, ~, !~
        - '=' is treated as substring contains (case-insensitive)
        - '==' exact equality (case-insensitive)
        - '~' contains (alias for '=')
        - '!~' and '!=' negative contains
        - Special handling for 'version=latest'
        Numeric comparisons attempt float conversion, else lexicographic.
        Returns (filters, free_terms) where filters is a list of dicts
        with keys: field, op, value
        """
        if not q:
            return [], []

        q_orig = q
        filters = []
        # allowed fields (case-insensitive) - UPDATED: Added special field
        allowed = {
            f: f
            for f in [
                "title",
                "artist",
                "coverartist",
                "version",
                "disc",
                "track",
                "date",
                "comment",
                "special",
                "file",
            ]
        }

        # regex to find key<op>value tokens; value may be quoted
        token_re = re.compile(
            r"(?i)\b(title|artist|coverartist|version|disc|track|date|comment|special|file)\s*(==|!=|>=|<=|>|<|=|~|!~)\s*(?:\"([^\"]+)\"|'([^']+)'|(\S+))"
        )

        # find all matches
        for m in token_re.finditer(q_orig):
            key = m.group(1).lower()
            op = m.group(2)
            val = m.group(3) or m.group(4) or m.group(5) or ""

            # Special handling for version=latest
            if key == "version" and val.lower() == "latest":
                # Convert to special filter for latest versions
                filters.append({"field": key, "op": "==", "value": "_latest_"})
            else:
                filters.append({"field": key, "op": op, "value": val})

        # remove matched portions from query to leave free text
        q_clean = token_re.sub("", q_orig)

        # remaining free terms (split by whitespace, ignore empty)
        free_terms = [t.lower() for t in re.split(r"\s+", q_clean.strip()) if t.strip()]

        return filters, free_terms

    def _match_filters(self, filters, free_terms, row_vals):
        """Evaluate whether a row (tuple with fields) matches filters and free terms.

        row_vals: dict mapping lowercase field names to values (strings)
        """
        # First evaluate structured filters
        for flt in filters:
            field = flt.get("field")
            op = flt.get("op")
            val = str(flt.get("value", "")).lower()

            field_val = str(row_vals.get(field, ""))
            field_val_l = field_val.lower()

            # Special handling for version=latest - FIXED: Use same key format as elsewhere
            if field == "version" and val == "_latest_":
                title = row_vals.get("title", "")
                artist = row_vals.get("artist", "")
                coverartist = row_vals.get("coverartist", "")
                version = field_val

                # Create the same unique key used in version scanning
                song_key = f"{title}|{artist}|{coverartist}"

                # Check if this version is the latest for this specific song key
                if song_key in self.latest_versions and version == self.latest_versions[song_key]:
                    continue  # It is the latest version, continue to next filter
                else:
                    return False  # Not the latest version, filter fails

            # Try numeric comparison when possible
            if op in (">", "<", ">=", "<="):
                try:
                    a = float(field_val)
                    b = float(val)
                except Exception:
                    # fallback to lexicographic
                    a = field_val_l
                    b = val

                try:
                    if op == ">" and not (a > b):
                        return False
                    if op == "<" and not (a < b):
                        return False
                    if op == ">=" and not (a >= b):
                        return False
                    if op == "<=" and not (a <= b):
                        return False
                except Exception:
                    return False
            elif op in ("=", "~"):
                # contains (case-insensitive)
                if val not in field_val_l:
                    return False
            elif op == "==":
                if field_val_l != val:
                    return False
            elif op in ("!=", "!~"):
                if val in field_val_l:
                    return False
            else:
                # unknown operator - fail safe
                return False

        # Then evaluate free text terms (all must be present somewhere)
        if free_terms:
            hay = " ".join([str(v).lower() for v in row_vals.values()])
            for t in free_terms:
                if t not in hay:
                    return False

        return True

    def on_tree_click(self, event):
        """Handle column header clicks for reordering"""
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            column = self.tree.identify_column(event.x)
            column_index = int(column.replace("#", "")) - 1
            if 0 <= column_index < len(self.column_order):
                self.dragged_column = self.column_order[column_index]
                self.tree.bind("<B1-Motion>", self.on_column_drag)
                self.tree.bind("<ButtonRelease-1>", self.on_column_drop)

    def on_column_drag(self, event):
        """Visual feedback during column drag"""
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            column = self.tree.identify_column(event.x)
            try:
                column_index = int(column.replace("#", "")) - 1
            except Exception:
                column_index = None

            if column_index is not None and 0 <= column_index < len(self.column_order):
                target = self.column_order[column_index]
                # Only update if changed
                if target != self._highlighted_column:
                    # clear previous
                    if self._highlighted_column:
                        try:
                            self.tree.heading(self._highlighted_column, background="")
                        except Exception:
                            pass
                    # set new highlight (color depends on theme)
                    try:
                        hl = "#4b94d6" if (self.current_theme == "Light") else "#3b6ea0"
                        self.tree.heading(target, background=hl)
                        self._highlighted_column = target
                    except Exception:
                        self._highlighted_column = None

    def on_column_drop(self, event):
        """Handle column reordering when dropped"""
        self.tree.unbind("<B1-Motion>")
        self.tree.unbind("<ButtonRelease-1>")
        # clear any header highlight
        if self._highlighted_column:
            try:
                self.tree.heading(self._highlighted_column, background="")
            except Exception:
                pass
            self._highlighted_column = None

        if self.dragged_column:
            region = self.tree.identify_region(event.x, event.y)
            if region == "heading":
                column = self.tree.identify_column(event.x)
                try:
                    drop_index = int(column.replace("#", "")) - 1
                except Exception:
                    drop_index = None

                if drop_index is not None and 0 <= drop_index < len(self.column_order):
                    # Reorder the columns
                    current_index = self.column_order.index(self.dragged_column)
                    if current_index != drop_index:
                        self.column_order.pop(current_index)
                        self.column_order.insert(drop_index, self.dragged_column)
                        self.rebuild_tree_columns()

            self.dragged_column = None

    def rebuild_tree_columns(self):
        """Rebuild tree columns with new order"""
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
            try:
                self.tree.heading(col, text="")
            except Exception:
                pass

        column_configs = {
            "title": ("Title", 180, "w"),
            "artist": ("Artist", 100, "w"),
            "coverartist": ("Cover Artist", 100, "w"),
            "version": ("Version", 70, "center"),
            "disc": ("Disc", 40, "center"),
            "track": ("Track", 40, "center"),
            "date": ("Date", 70, "center"),
            "comment": ("Comment", 120, "w"),
            "special": ("Special", 60, "center"),  # NEW: Added Special column
            "file": ("File", 120, "w"),
        }

        # Recreate columns in new order
        new_columns = list(self.column_order)
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
            try:
                self.tree.selection_set(selection)
            except Exception:
                pass
        try:
            self.tree.yview_moveto(scroll_v[0])
            self.tree.xview_moveto(scroll_h[0])
        except Exception:
            pass

    # -------------------------
    # Settings persistence
    # -------------------------
    @property
    def settings_path(self):
        try:
            if getattr(sys, "frozen", False):
                # Running as bundled executable
                base = Path(sys.executable).parent
            else:
                # Running as script
                base = Path(__file__).resolve().parent.parent
            return base / "df_metadata_customizer_settings.json"
        except Exception:
            # Fallback to current working directory
            return Path("df_metadata_customizer_settings.json")

    def save_settings(self):
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
                data["column_order"] = list(self.column_order)
                widths = {}
                for col in self.column_order:
                    try:
                        info = self.tree.column(col)
                        widths[col] = int(info.get("width", 0))
                    except Exception:
                        widths[col] = 0
                data["column_widths"] = widths
            except Exception:
                data["column_order"] = self.column_order
                data["column_widths"] = {}

            # sort rules
            try:
                data["sort_rules"] = self.get_sort_rules()
            except Exception:
                data["sort_rules"] = []

            # other UI prefs
            data["show_covers"] = bool(self.show_covers)
            data["theme"] = str(self.current_theme)

            # write file
            p = self.settings_path
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self):
        """Load UI settings from JSON file and apply them where possible."""
        p = self.settings_path
        if not p.exists():
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        # theme
        try:
            th = data.get("theme")
            if th:
                self.current_theme = th
                ctk.set_appearance_mode(self.current_theme)
                self._update_theme_button()
                self._update_treeview_style()
                self._update_json_text_style()
                self._update_output_preview_style()
        except Exception:
            pass

        # show covers - REMOVED: No longer toggleable, always True
        self.show_covers = True

        # column order & widths
        try:
            col_order = data.get("column_order")
            col_widths = data.get("column_widths", {})
            if col_order and isinstance(col_order, list):
                # apply order
                self.column_order = col_order
                # rebuild columns to new order
                try:
                    self.rebuild_tree_columns()
                except Exception:
                    pass
                # apply widths
                try:
                    for c, w in (col_widths or {}).items():
                        try:
                            self.tree.column(c, width=int(w))
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        # sort rules
        try:
            sort_rules = data.get("sort_rules") or []
            if isinstance(sort_rules, list) and sort_rules:
                # ensure at least one rule exists
                # clear existing additional rules and set values
                # there is always at least one sort rule created in UI
                # set values for existing rules and add extras if needed
                for i, r in enumerate(sort_rules):
                    if i < len(self.sort_rules):
                        try:
                            self.sort_rules[i].field_var.set(r.get("field", self.sort_fields[0]))
                            self.sort_rules[i].order_var.set(r.get("order", "asc"))
                        except Exception:
                            pass
                    else:
                        try:
                            self.add_sort_rule(is_first=False)
                            self.sort_rules[-1].field_var.set(r.get("field", self.sort_fields[0]))
                            self.sort_rules[-1].order_var.set(r.get("order", "asc"))
                        except Exception:
                            pass
        except Exception:
            pass

        # sash ratio - apply after window is laid out
        try:
            sash_ratio = data.get("sash_ratio")
            if sash_ratio is not None:

                def apply_ratio(attempts=0):
                    try:
                        total = self.paned.winfo_width()
                        if total and attempts < 10:
                            pos = int(total * float(sash_ratio))
                            try:
                                self.paned.sash_place(0, pos, 0)
                            except Exception:
                                try:
                                    self.paned.sashpos(0)
                                except Exception:
                                    pass
                        else:
                            # try again shortly if not yet sized
                            if attempts < 10:
                                self.after(150, lambda: apply_ratio(attempts + 1))
                    except Exception:
                        pass

                self.after(200, lambda: apply_ratio(0))
        except Exception:
            pass

        # Always load cover if available
        try:
            if self.current_index is not None:
                self.load_current_cover()
            else:
                self._safe_cover_display_update("No cover", clear_image=True)
        except Exception:
            pass

    def _on_close(self):
        try:
            self.cover_loading_active = False  # Stop the cover loading thread
            self.save_settings()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            try:
                self.quit()
            except Exception:
                pass

    # -------------------------
    # Rule tab creation - FIXED LAYOUT
    # -------------------------
    def _create_rule_tab(self, name):
        # This method is now handled in _build_ui with the improved layout
        pass

    def add_rule_to_tab(self, tab_name):
        """Add a rule to the specified tab"""
        container = self.rule_containers.get(tab_name.lower())
        if container:
            self.add_rule(container)

    # -------------------------
    # JSON Editing Functions - UPDATED with prefix support
    # -------------------------
    def save_json_to_file(self):
        """Save the edited JSON back to the current MP3 file"""
        if self.current_index is None or not self.mp3_files:
            messagebox.showwarning("No file selected", "Please select a file first")
            return

        # Get the edited JSON text
        json_text = self.json_text.get("1.0", "end-1c").strip()

        if not json_text:
            messagebox.showwarning("Empty JSON", "JSON text is empty")
            return

        try:
            # Parse the JSON to validate it
            edited_data = json.loads(json_text)

            # Check if this is our wrapper format with _prefix
            prefix_text = ""
            json_data = edited_data

            if "_prefix" in edited_data:
                prefix_text = edited_data["_prefix"]
                # Create a copy without the _prefix field for the actual JSON data
                json_data = {k: v for k, v in edited_data.items() if k != "_prefix"}

            # FIXED: Check if prefix ends with space and handle accordingly
            if prefix_text:
                # Remove any trailing space from prefix and concatenate directly
                prefix_clean = prefix_text.rstrip()
                full_comment = f"{prefix_clean}{json.dumps(json_data, ensure_ascii=False, separators=(',', ':'))}"
            else:
                # If no prefix, just use the JSON with compact formatting
                full_comment = json.dumps(json_data, ensure_ascii=False, separators=(",", ":"))

        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"The JSON is invalid:\n{str(e)}")
            return

        # Confirm save
        path = self.mp3_files[self.current_index]
        filename = os.path.basename(path)
        result = messagebox.askyesno("Confirm Save", f"Save JSON changes to:\n{filename}?")

        if not result:
            return

        # Show saving indicator
        original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text=f"Saving JSON to {filename}...")
        self.update_idletasks()

        def save_json():
            # Write the full comment text directly
            success = mp3_utils.write_json_to_mp3(path, full_comment)
            return success, filename

        def on_save_complete(result):
            success, filename = result
            if success:
                # Update cache with new data
                self.file_data_cache[path] = (json_data, prefix_text)
                self.current_json = json_data
                self.current_json_prefix = prefix_text

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

    def update_tree_row(self, index, json_data):
        """Update a specific row in the treeview with new JSON data"""
        if index < 0 or index >= len(self.mp3_files):
            return

        path = self.mp3_files[index]
        # Create field values dictionary
        field_values = {
            "title": json_data.get("Title") or os.path.splitext(os.path.basename(path))[0],
            "artist": json_data.get("Artist") or "",
            "coverartist": json_data.get("CoverArtist") or "",
            "version": json_data.get("Version") or "",
            "disc": json_data.get("Discnumber") or "",
            "track": json_data.get("Track") or "",
            "date": json_data.get("Date") or "",
            "comment": json_data.get("Comment") or "",
            "special": json_data.get("Special") or "",
            "file": os.path.basename(path),
        }

        # Create values tuple in the current column order
        values = tuple(field_values[col] for col in self.column_order)

        # Update the treeview item
        self.tree.item(str(index), values=values)

    # -------------------------
    # Filename Editing Functions
    # -------------------------
    def on_filename_changed(self, event=None):
        """Enable/disable rename button based on filename changes"""
        if self.current_index is None:
            self.filename_save_btn.configure(state="disabled")
            return

        current_path = self.mp3_files[self.current_index]
        current_filename = os.path.basename(current_path)
        new_filename = self.filename_var.get().strip()

        # Enable button only if filename has changed and is not empty
        if new_filename and new_filename != current_filename:
            self.filename_save_btn.configure(state="normal")
        else:
            self.filename_save_btn.configure(state="disabled")

    def rename_current_file(self):
        """Rename the current file to the new filename"""
        if self.current_index is None:
            return

        current_path = self.mp3_files[self.current_index]
        current_filename = os.path.basename(current_path)
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
        directory = os.path.dirname(current_path)
        new_path = os.path.join(directory, new_filename)

        # Check if target file already exists
        if os.path.exists(new_path):
            result = messagebox.askyesno("File exists", f"A file named '{new_filename}' already exists.\nOverwrite it?")
            if not result:
                return

        # Confirm rename
        result = messagebox.askyesno("Confirm Rename", f"Rename:\n{current_filename}\nTo:\n{new_filename}?")
        if not result:
            return

        # Show renaming indicator
        original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text=f"Renaming {current_filename}...")
        self.update_idletasks()

        # Rename in background thread
        def rename_file():
            try:
                # Use shutil.move to handle cross-device moves if needed
                shutil.move(current_path, new_path)
                return True, current_filename, new_filename
            except Exception as e:
                return False, current_filename, str(e)

        def on_rename_complete(result):
            success, old_name, new_name_or_error = result
            if success:
                # Update the file path in our list
                self.mp3_files[self.current_index] = new_path

                # Update cache entries
                if current_path in self.file_data_cache:
                    self.file_data_cache[new_path] = self.file_data_cache.pop(current_path)
                if current_path in self.cover_cache:
                    self.cover_cache[new_path] = self.cover_cache.pop(current_path)

                # Update treeview
                if self.current_json:
                    self.update_tree_row(self.current_index, self.current_json)

                # Update filename entry to show new name
                self.filename_var.set(new_name_or_error)
                self.filename_save_btn.configure(state="disabled")

                self.lbl_file_info.configure(text=f"Renamed {old_name} to {new_name_or_error}")
                messagebox.showinfo("Success", f"File renamed successfully!\n\n{old_name} → {new_name_or_error}")
            else:
                self.lbl_file_info.configure(text=f"Failed to rename {old_name}")
                messagebox.showerror("Error", f"Failed to rename file:\n{new_name_or_error}")

        threading.Thread(target=lambda: self.after(0, lambda: on_rename_complete(rename_file())), daemon=True).start()

    def delete_rule(self, widget):
        """Delete a rule from its container - UPDATED: With button state update"""
        container = widget.master
        children = [w for w in container.winfo_children() if isinstance(w, RuleRow)]

        if widget not in children:
            return

        # Remove the widget
        widget.destroy()

        # Update button states after deletion (rules are now below limit)
        self.update_rule_tab_buttons()
        self.update_preview()

    def add_rule_to_tab(self, tab_name):
        """Add a rule to the specified tab - UPDATED: With rule limit check"""
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

    def update_rule_tab_buttons(self):
        """Update the Add Rule buttons for each tab based on rule counts"""
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

    def collect_rules_for(self, tab):
        """Return list of rule dicts for tab name (title/artist/album)."""
        container = self.rule_containers.get(tab)
        if not container:
            return []
        rules = []
        for w in container.winfo_children():
            if isinstance(w, RuleRow):
                rules.append(w.get_rule())
        return rules

    def add_rule(self, container):
        # Count current rules to determine if this is the first one
        current_rules = len([w for w in container.winfo_children() if isinstance(w, RuleRow)])
        is_first = current_rules == 0

        row = RuleRow(container, self.rule_fields, self.rule_ops, delete_callback=self.delete_rule, is_first=is_first)
        row.pack(fill="x", padx=6, pady=3)

        # default template suggestions based on container tab
        parent_tab = self._container_to_tab(container)
        if parent_tab == "title":
            row.template_entry.insert(0, "{CoverArtist} - {Title}")
        elif parent_tab == "artist":
            row.template_entry.insert(0, "{CoverArtist}")
        elif parent_tab == "album":
            row.template_entry.insert(0, "Archive VOL {Discnumber}")

        # FIXED: Use force preview update for immediate response
        def update_callback(*args):
            self.force_preview_update()

        row.field_var.trace("w", update_callback)
        row.op_var.trace("w", update_callback)
        row.logic_var.trace("w", update_callback)  # Add logic change listener
        row.value_entry.bind("<KeyRelease>", lambda e: self.force_preview_update())
        row.template_entry.bind("<KeyRelease>", lambda e: self.force_preview_update())

        # Update button states after adding
        self.update_rule_tab_buttons()
        # Initial update
        self.force_preview_update()

    # -------------------------
    # File / tree operations - FIXED PROGRESS DIALOG
    # -------------------------
    def select_folder(self):
        if self.operation_in_progress:
            return

        folder = filedialog.askdirectory()
        if not folder:
            return

        self.operation_in_progress = True
        self.btn_select_folder.configure(state="disabled")

        # Clear cache when loading new folder
        self.file_data_cache.clear()
        self.cover_cache.clear()
        mp3_utils.extract_json_from_mp3_cached.cache_clear()

        # Show loading state immediately
        self.lbl_file_info.configure(text="Scanning folder...")
        self.update_idletasks()

        # Create and show progress dialog IMMEDIATELY
        self.progress_dialog = ProgressDialog(self, "Loading Folder")
        self.progress_dialog.update_progress(0, 100, "Finding MP3 files...")

        # Scan in background thread
        def scan_folder():
            try:
                files = []
                count = 0

                # Use pathlib for faster file discovery
                for p in Path(folder).glob("**/*.mp3"):
                    if p.is_file() and p.suffix.lower() == ".mp3":
                        files.append(str(p))
                        count += 1
                        # Update progress every 10 files
                        if count % 10 == 0 and self.progress_dialog:
                            if not self.progress_dialog.update_progress(count, count, f"Found {count} files..."):
                                return None
                return files
            except Exception as e:
                print(f"Error scanning folder: {e}")
                return []

        def on_scan_complete(files):
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
        threading.Thread(target=lambda: self.after(0, lambda: on_scan_complete(scan_folder())), daemon=True).start()

    def refresh_tree(self):
        """Refresh tree with search filtering and multi-sort. Supports structured filters including version=latest."""
        q_raw = self.search_var.get().strip()

        # Build file_data list first
        file_data = []
        for i, p in enumerate(self.mp3_files):
            jsond = self.get_file_data(p)
            # Create field values dictionary
            field_values = {
                "title": jsond.get("Title") or os.path.splitext(os.path.basename(p))[0],
                "artist": jsond.get("Artist") or "",
                "coverartist": jsond.get("CoverArtist") or "",
                "version": jsond.get("Version") or "",
                "disc": jsond.get("Discnumber") or "",
                "track": jsond.get("Track") or "",
                "date": jsond.get("Date") or "",
                "comment": jsond.get("Comment") or "",
                "special": jsond.get("Special") or "",
                "file": os.path.basename(p),
            }
            file_data.append((i, field_values))

        # If no query, just sort & show all
        if not q_raw:
            sorted_data = self.apply_multi_sort_with_dict(file_data)
            for it in self.tree.get_children():
                self.tree.delete(it)
            self.visible_file_indices = []
            for orig_idx, field_values in sorted_data:
                # Create values tuple in the current column order
                values = tuple(field_values[col] for col in self.column_order)
                self.tree.insert("", "end", iid=str(orig_idx), values=values)
                self.visible_file_indices.append(orig_idx)
            # Update search info label
            self.search_info_label.configure(text=f"{len(self.visible_file_indices)} songs found")
            # Update statistics
            self.calculate_statistics()
            return

        # Parse query into structured filters and free text terms - UPDATED: Added special field and version=latest
        filters, free_terms = self._parse_search_query(q_raw)

        # Clear existing tree
        for it in self.tree.get_children():
            self.tree.delete(it)
        self.visible_file_indices = []

        # Evaluate each row against filters, collect matches
        matches = []
        for orig_idx, field_values in file_data:
            try:
                if self._match_filters(filters, free_terms, field_values):
                    matches.append((orig_idx, field_values))
            except Exception:
                continue

        # Apply multi-level sort to the filtered matches so search+sort combine
        try:
            sorted_matches = self.apply_multi_sort_with_dict(matches)
        except Exception:
            sorted_matches = matches

        # Insert sorted matches into the tree
        for orig_idx, field_values in sorted_matches:
            try:
                # Create values tuple in the current column order
                values = tuple(field_values[col] for col in self.column_order)
                self.tree.insert("", "end", iid=str(orig_idx), values=values)
                self.visible_file_indices.append(orig_idx)
            except Exception:
                continue

        # Update search info label with count and filter summary
        info = f"{len(self.visible_file_indices)} songs found"
        if filters or free_terms:
            parts = []
            for f in filters:
                parts.append(f"{f['field']} {f['op']} {f['value']}")
            for t in free_terms:
                parts.append(f"'{t}'")
            info += " | " + ", ".join(parts)
        self.search_info_label.configure(text=info)

        # Update statistics for filtered results
        self.calculate_statistics()

    def on_tree_select(self, event=None):
        sel = self.tree.selection()
        # Update selection count
        self.lbl_selection_info.configure(text=f"{len(sel)} song(s) selected")

        if not sel:
            return
        iid = sel[0]
        try:
            idx = int(iid)
        except:
            return
        if idx < 0 or idx >= len(self.mp3_files):
            return
        self.current_index = idx
        self.load_current()

    def load_current(self):
        """Load current song data - FIXED: Better non-ASCII handling in JSON display"""
        if self.current_index is None or not self.mp3_files:
            return
        path = self.mp3_files[self.current_index]
        self.lbl_file_info.configure(
            text=f"{self.current_index + 1}/{len(self.mp3_files)}  —  {os.path.basename(path)}"
        )

        # Load JSON from cache (with prefix)
        json_data, prefix_text = self.get_file_data_with_prefix(path)
        self.current_json = json_data
        self.current_json_prefix = prefix_text

        # show JSON with prefix as a wrapper - FIXED: Better encoding handling
        self.json_text.delete("1.0", "end")
        if self.current_json or self.current_json_prefix:
            # Create a wrapper JSON that includes both prefix and original data
            wrapper_json = {}
            if self.current_json_prefix:
                wrapper_json["_prefix"] = self.current_json_prefix
            if self.current_json:
                wrapper_json.update(self.current_json)

            try:
                # FIXED: Ensure proper encoding for JSON dump
                json_str = json.dumps(wrapper_json, indent=2, ensure_ascii=False)
                self.json_text.insert("1.0", json_str)
            except Exception as e:
                print(f"Error displaying JSON: {e}")
                # Fallback: try with ASCII encoding
                try:
                    json_str = json.dumps(wrapper_json, indent=2, ensure_ascii=True)
                    self.json_text.insert("1.0", json_str)
                except:
                    self.json_text.insert("1.0", "Error displaying JSON data")
        else:
            self.json_text.insert("1.0", "No JSON found in comments")

        # Disable JSON save button initially (no changes yet)
        self.json_save_btn.configure(state="disabled")

        # Load current filename
        current_filename = os.path.basename(path)
        self.filename_var.set(current_filename)
        self.filename_save_btn.configure(state="disabled")

        # FIXED: Update preview FIRST, then load cover
        self.update_preview()

        # Load cover AFTER preview is updated
        self.load_current_cover()

    def prev_file(self):
        """Navigate to previous file in the visible list"""
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

    def next_file(self):
        """Navigate to next file in the visible list"""
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

    def on_select_all(self):
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
    def update_preview(self):
        if not self.current_json:
            self.lbl_out_title.configure(text="")
            self.lbl_out_artist.configure(text="")
            self.lbl_out_album.configure(text="")
            self.lbl_out_disc.configure(text="")
            self.lbl_out_track.configure(text="")
            self.lbl_out_versions.configure(text="")
            return

        # FIXED: Better handling of non-ASCII characters
        def safe_get(field):
            value = self.current_json.get(field, "")
            # Ensure we return a proper string, handling any encoding issues
            if isinstance(value, bytes):
                try:
                    return value.decode("utf-8")
                except:
                    return str(value)
            return str(value) if value is not None else ""

        fv = {
            "Date": safe_get("Date"),
            "Title": safe_get("Title"),
            "Artist": safe_get("Artist"),
            "CoverArtist": safe_get("CoverArtist"),
            "Version": safe_get("Version"),
            "Discnumber": safe_get("Discnumber"),
            "Track": safe_get("Track"),
            "Comment": safe_get("Comment"),
            "Special": safe_get("Special"),
        }

        # REMOVED: Problematic debug print that causes encoding errors
        # print(f"Field values - Title: {repr(fv['Title'])}, Artist: {repr(fv['Artist'])}, CoverArtist: {repr(fv['CoverArtist'])}")

        # FIXED: Use the correct method to collect rules for each tab
        new_title = self._apply_rules_list(self.collect_rules_for_tab("title"), fv)
        new_artist = self._apply_rules_list(self.collect_rules_for_tab("artist"), fv)
        new_album = self._apply_rules_list(self.collect_rules_for_tab("album"), fv)

        # REMOVED: Problematic debug print
        # print(f"Preview - Title: '{new_title}', Artist: '{new_artist}', Album: '{new_album}'")

        # FIXED: Safe text setting for non-ASCII characters
        try:
            self.lbl_out_title.configure(text=new_title)
            self.lbl_out_artist.configure(text=new_artist)
            self.lbl_out_album.configure(text=new_album)
            self.lbl_out_disc.configure(text=fv.get("Discnumber", ""))
            self.lbl_out_track.configure(text=fv.get("Track", ""))
            self.lbl_out_date.configure(text=fv.get("Date", ""))
        except Exception as e:
            print(f"Error setting preview text: {e}")
            # Fallback: set empty text to avoid freezing
            self.lbl_out_title.configure(text="")
            self.lbl_out_artist.configure(text="")
            self.lbl_out_album.configure(text="")

        # Show all versions for current song (considering title + artist + coverartist)
        current_title = fv.get("Title", "")
        current_artist = fv.get("Artist", "")
        current_coverartist = fv.get("CoverArtist", "")

        # Create a unique key that considers all three fields
        song_key = f"{current_title}|{current_artist}|{current_coverartist}"

        if song_key and song_key in self.song_versions:
            versions = self.song_versions[song_key]
            versions_text = ", ".join(sorted(set(versions)))  # Remove duplicates and sort
            self.lbl_out_versions.configure(text=versions_text)
        else:
            self.lbl_out_versions.configure(text="")

    def safe_update_preview(self):
        """Safe wrapper for update_preview with exception handling"""
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

    def collect_rules_for_tab(self, key):
        """key in 'title','artist','album' - Enhanced for AND/OR grouping"""
        container = self.rule_containers.get(key)
        if not container:
            return []
        rules = []
        children = [w for w in container.winfo_children() if isinstance(w, RuleRow)]

        for i, widget in enumerate(children):
            rule_data = widget.get_rule()
            # Ensure first rule has proper logic flag
            if i == 0:
                rule_data["is_first"] = True
            rules.append(rule_data)

        return rules

    def _apply_rules_list(self, rules, fv):
        """Apply rules list to field values with AND/OR grouping"""
        if not rules:
            # Return appropriate default based on context
            if rules is self.collect_rules_for_tab("title"):
                return fv.get("Title", "")
            elif rules is self.collect_rules_for_tab("artist"):
                return fv.get("Artist", "")
            elif rules is self.collect_rules_for_tab("album"):
                return fv.get("Album", "")
            return ""

        # Group rules by logical blocks
        rule_blocks = self._group_rules_by_logic(rules)

        # Evaluate each rule block
        for block in rule_blocks:
            if self._eval_rule_block(block, fv):
                # Get the template from the last rule in the block (where the THEN is defined)
                template = block[-1].get("then_template", "")
                result = self._apply_template(template, fv)
                if result.strip():
                    return result
                else:
                    # Fallback to original field if template is empty
                    if "title" in str(rules):
                        return fv.get("Title", "")
                    elif "artist" in str(rules):
                        return fv.get("Artist", "")
                    elif "album" in str(rules):
                        return fv.get("Album", "")

        # No rules matched, return original field
        if rules is self.collect_rules_for_tab("title"):
            return fv.get("Title", "")
        elif rules is self.collect_rules_for_tab("artist"):
            return fv.get("Artist", "")
        elif rules is self.collect_rules_for_tab("album"):
            return fv.get("Album", "")
        return ""

    def _group_rules_by_logic(self, rules):
        """Group rules into logical blocks based on AND/OR operators"""
        if not rules:
            return []

        blocks = []
        current_block = []

        for i, rule in enumerate(rules):
            # First rule always starts a block
            if i == 0:
                current_block.append(rule)
                continue

            logic = rule.get("logic", "AND")

            if logic == "AND":
                # AND continues the current block
                current_block.append(rule)
            else:
                # OR starts a new block
                if current_block:
                    blocks.append(current_block)
                current_block = [rule]

        # Don't forget the last block
        if current_block:
            blocks.append(current_block)

        return blocks

    def _eval_rule_block(self, rule_block, fv):
        """Evaluate a block of rules with AND logic (all rules in block must match)"""
        if not rule_block:
            return False

        for rule in rule_block:
            if not self._eval_single_rule(rule, fv):
                return False

        return True

    def _eval_single_rule(self, rule, fv):
        """Evaluate a single rule (moved from _eval_rule)"""
        field = rule.get("if_field", "")
        op = rule.get("if_operator", "")
        val = rule.get("if_value", "")
        actual = str(fv.get(field, ""))

        if op == "is":
            return actual == val
        if op == "contains":
            return val in actual
        if op == "starts with":
            return actual.startswith(val)
        if op == "ends with":
            return actual.endswith(val)
        if op == "is empty":
            return actual == ""
        if op == "is not empty":
            return actual != ""
        if op == "is latest version":
            title = fv.get("Title", "")
            artist = fv.get("Artist", "")
            coverartist = fv.get("CoverArtist", "")
            version = fv.get("Version", "0")
            return self.is_latest_version_full(title, artist, coverartist, version)
        if op == "is not latest version":
            title = fv.get("Title", "")
            artist = fv.get("Artist", "")
            coverartist = fv.get("CoverArtist", "")
            version = fv.get("Version", "0")
            return not self.is_latest_version_full(title, artist, coverartist, version)
        return False

    # Update the is_latest_version method to handle full song key
    def is_latest_version_full(self, title, artist, coverartist, version):
        if not self.latest_versions:
            return True

        song_key = f"{title}|{artist}|{coverartist}"
        return self.latest_versions.get(song_key, version) == version

    def _apply_template(self, template, fv):
        """Apply template with field values."""
        if not template:
            return ""

        try:
            result = template
            for k, v in fv.items():
                placeholder = "{" + k + "}"
                if placeholder in result:
                    # FIXED: Safe string replacement for non-ASCII
                    safe_value = str(v) if v is not None else ""
                    result = result.replace(placeholder, safe_value)

            # Also handle common field names that might be in the template
            common_fields = {
                "Title": fv.get("Title", ""),
                "Artist": fv.get("Artist", ""),
                "CoverArtist": fv.get("CoverArtist", ""),
                "Version": fv.get("Version", ""),
                "Discnumber": fv.get("Discnumber", ""),
                "Track": fv.get("Track", ""),
                "Date": fv.get("Date", ""),
                "Comment": fv.get("Comment", ""),
                "Special": fv.get("Special", ""),
            }

            for field_name, field_value in common_fields.items():
                placeholder = "{" + field_name + "}"
                if placeholder in result:
                    safe_value = str(field_value) if field_value is not None else ""
                    result = result.replace(placeholder, safe_value)
        except Exception as e:
            print(f"Error applying template '{template}': {e}")
            return ""
        return result

    def debug_rules(self):
        """Debug method to see what rules are loaded"""
        print("=== DEBUG RULES ===")
        for tab in ["title", "artist", "album"]:
            rules = self.collect_rules_for_tab(tab)
            print(f"{tab.upper()} rules: {len(rules)}")
            for i, rule in enumerate(rules):
                print(
                    f"  Rule {i}: IF {rule.get('if_field')} {rule.get('if_operator')} '{rule.get('if_value')}' THEN '{rule.get('then_template')}'"
                )
        print("===================")

    # -------------------------
    # Version scanning - UPDATED with auto-scan
    # -------------------------
    def scan_versions(self):
        if not self.mp3_files:
            messagebox.showwarning("No files", "Load a folder first")
            return

        self.btn_scan_versions.configure(state="disabled", text="Scanning...")

        def scan_in_background():
            song_versions = {}
            total = len(self.mp3_files)
            completed = 0

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(self.get_file_data, p): p for p in self.mp3_files}
                for future in as_completed(futures):
                    p = futures[future]
                    try:
                        j = future.result()
                        if not j:
                            continue
                        title = j.get("Title", "")
                        artist = j.get("Artist", "")
                        coverartist = j.get("CoverArtist", "")
                        version = j.get("Version", "0")

                        # Create a unique key that considers title, artist, AND coverartist
                        song_key = f"{title}|{artist}|{coverartist}"

                        if song_key not in song_versions:
                            song_versions[song_key] = []
                        song_versions[song_key].append(version)
                    except Exception as e:
                        print(f"Error scanning {p}: {e}")
                    finally:
                        completed += 1

            # Compute latest versions
            latest_versions = {}
            for song_key, versions in song_versions.items():
                parsed = []
                for v in versions:
                    nums = re.findall(r"\d+", str(v))
                    if nums:
                        parsed.append([int(x) for x in nums])
                    else:
                        parsed.append([0])
                # find max by lexicographic comparison
                max_idx = 0
                for i, p in enumerate(parsed):
                    if p > parsed[max_idx]:
                        max_idx = i
                latest_versions[song_key] = versions[max_idx]

            return song_versions, latest_versions

        def on_scan_complete(result):
            self.song_versions, self.latest_versions = result
            self.btn_scan_versions.configure(state="normal", text="Scan Versions")
            messagebox.showinfo("Scan Complete", f"Scanned {len(self.song_versions)} unique songs.")
            # Refresh preview to show versions
            self.update_preview()

        # Start background scanning
        threading.Thread(
            target=lambda: self.after(0, lambda: on_scan_complete(scan_in_background())), daemon=True
        ).start()

    def is_latest_version(self, title, version):
        if not self.latest_versions:
            return True

        # Find the song key for this title (we need to search since we don't have artist/coverartist here)
        for song_key, latest_version in self.latest_versions.items():
            if title in song_key:  # Simple matching - could be improved
                return latest_version == version
        return True

    # -------------------------
    # Apply metadata to files - FIXED PROGRESS DIALOG
    # -------------------------
    def apply_to_selected(self):
        if self.operation_in_progress:
            messagebox.showinfo("Operation in progress", "Please wait for the current operation to complete.")
            return

        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select rows in the song list first")
            return

        paths = [self.mp3_files[int(iid)] for iid in sel]

        self.operation_in_progress = True

        # Show immediate feedback
        self.lbl_file_info.configure(text=f"Starting to apply to {len(paths)} files...")
        self.update_idletasks()

        # Create and show progress dialog IMMEDIATELY
        self.progress_dialog = ProgressDialog(self, "Applying Metadata")
        self.progress_dialog.update_progress(0, len(paths), "Starting...")

        def apply_in_background():
            success_count = 0
            total = len(paths)
            errors = []

            for i, p in enumerate(paths):
                if self.progress_dialog and self.progress_dialog.cancelled:
                    break

                try:
                    j = self.get_file_data(p)
                    if not j:
                        errors.append(f"No metadata: {os.path.basename(p)}")
                        continue

                    fv = {
                        "Date": j.get("Date", ""),
                        "Title": j.get("Title", ""),
                        "Artist": j.get("Artist", ""),
                        "CoverArtist": j.get("CoverArtist", ""),
                        "Version": j.get("Version", "0"),
                        "Discnumber": j.get("Discnumber", ""),
                        "Track": j.get("Track", ""),
                        "Comment": j.get("Comment", ""),
                        "Special": j.get("Special", ""),  # NEW: Added Special field
                    }
                    new_title = self._apply_rules_list(self.collect_rules_for_tab("title"), fv)
                    new_artist = self._apply_rules_list(self.collect_rules_for_tab("artist"), fv)
                    new_album = self._apply_rules_list(self.collect_rules_for_tab("album"), fv)

                    # write tags
                    cover_bytes = None
                    cover_mime = "image/jpeg"

                    if mp3_utils.write_id3_tags(
                        p,
                        title=new_title,
                        artist=new_artist,
                        album=new_album,
                        track=fv.get("Track", None),
                        disc=fv.get("Discnumber", None),
                        date=fv.get("Date", None),
                        cover_bytes=cover_bytes,
                        cover_mime=cover_mime,
                    ):
                        success_count += 1
                    else:
                        errors.append(f"Failed to write: {os.path.basename(p)}")

                except Exception as e:
                    errors.append(f"Error with {os.path.basename(p)}: {str(e)}")

                # Update progress - FORCE UPDATE
                if self.progress_dialog:
                    self.progress_dialog.update_progress(
                        i + 1, total, f"Applying to {i + 1}/{total}: {os.path.basename(p)}"
                    )

            return success_count, errors

        def on_apply_complete(result):
            success_count, errors = result

            # Close progress dialog
            if self.progress_dialog:
                self.progress_dialog.destroy()
                self.progress_dialog = None

            # Show results
            if errors:
                error_msg = f"Applied to {success_count}/{len(paths)} files\n\nErrors ({len(errors)}):\n" + "\n".join(
                    errors[:5]
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
            target=lambda: self.after(0, lambda: on_apply_complete(apply_in_background())), daemon=True
        ).start()

    def apply_to_all(self):
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
    @property
    def presets_folder(self):
        """Get the presets folder path"""
        try:
            if getattr(sys, "frozen", False):
                # Running as bundled executable
                base = Path(sys.executable).parent
            else:
                # Running as script
                base = Path(__file__).resolve().parent.parent

            presets_folder = base / "presets"
            presets_folder.mkdir(exist_ok=True)  # Create if doesn't exist
            return presets_folder
        except Exception:
            # Fallback to current working directory
            presets_folder = Path("presets")
            presets_folder.mkdir(exist_ok=True)
            return presets_folder

    def save_preset(self):
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
            preset_file = self.presets_folder / f"{name}.json"
            with open(preset_file, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2, ensure_ascii=False)

            # update combobox list
            self._reload_presets()
            self.lbl_file_info.configure(text=original_text)
            messagebox.showinfo("Saved", f"Preset '{name}' saved successfully!")
        except Exception as e:
            self.lbl_file_info.configure(text=original_text)
            messagebox.showerror("Error", f"Could not save preset: {e}")

    def _reload_presets(self):
        """Reload presets from individual files in presets folder"""
        try:
            presets_folder = self.presets_folder
            vals = []

            # Get all .json files in presets folder
            for preset_file in presets_folder.glob("*.json"):
                try:
                    # Use filename without extension as preset name
                    preset_name = preset_file.stem
                    vals.append(preset_name)
                except Exception:
                    continue

            # Sort alphabetically
            vals.sort()
            self.preset_combo["values"] = vals
        except Exception as e:
            print(f"Error loading presets: {e}")
            self.preset_combo["values"] = []

    def delete_preset(self):
        name = self.preset_var.get()
        if not name:
            return

        # Show deleting indicator
        original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text="Deleting preset...")
        self.update_idletasks()

        try:
            preset_file = self.presets_folder / f"{name}.json"

            if preset_file.exists():
                confirm = messagebox.askyesno("Delete", f"Delete preset '{name}'?")
                if confirm:
                    preset_file.unlink()  # Delete the file
                    self._reload_presets()
                    self.preset_var.set("")  # Clear current selection
                    self.lbl_file_info.configure(text=original_text)
                    messagebox.showinfo("Deleted", f"Preset '{name}' deleted successfully!")
                else:
                    self.lbl_file_info.configure(text=original_text)
            else:
                self.lbl_file_info.configure(text=original_text)
                messagebox.showwarning("Not Found", f"Preset '{name}' not found")
        except Exception as e:
            self.lbl_file_info.configure(text=original_text)
            messagebox.showerror("Error", f"Could not delete preset: {e}")

    def on_preset_selected(self, event=None):
        name = self.preset_var.get()
        if not name:
            return

        # Show loading indicator
        original_text = self.lbl_file_info.cget("text")
        self.lbl_file_info.configure(text=f"Loading preset '{name}'...")
        self.update_idletasks()

        try:
            preset_file = self.presets_folder / f"{name}.json"

            if not preset_file.exists():
                self.lbl_file_info.configure(text=original_text)
                messagebox.showwarning("Not Found", f"Preset file '{name}.json' not found")
                return

            with open(preset_file, "r", encoding="utf-8") as f:
                preset = json.load(f)

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
                        cont, self.rule_fields, self.rule_ops, delete_callback=self.delete_rule, is_first=is_first
                    )
                    row.pack(fill="x", padx=6, pady=3)
                    row.field_var.set(r.get("if_field", self.rule_fields[0]))
                    row.op_var.set(r.get("if_operator", self.rule_ops[0]))
                    row.value_entry.insert(0, r.get("if_value", ""))
                    row.template_entry.insert(0, r.get("then_template", ""))
                    # Set logic for non-first rules
                    if not is_first:
                        row.logic_var.set(r.get("logic", "AND"))

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
    def _container_to_tab(self, container):
        """Get tab name from container widget"""
        for tab_name, cont in self.rule_containers.items():
            if cont == container:
                return tab_name
        return "title"

    def update_rule_button_states(self, container):
        """Update button states for rules in a container"""
        children = [w for w in container.winfo_children() if isinstance(w, RuleRow)]
        for i, child in enumerate(children):
            child.set_button_states(i == 0, i == len(children) - 1)

    def run(self):
        # load presets combobox
        self._reload_presets()
        self.mainloop()

def main():
    app = DFApp()
    app.run()


if __name__ == "__main__":
    main()

"""Tree View Component."""

import contextlib
import json
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import override

from df_metadata_customizer import song_utils
from df_metadata_customizer.components.app_component import AppComponent
from df_metadata_customizer.rule_manager import RuleManager
from df_metadata_customizer.settings_manager import SettingsManager
from df_metadata_customizer.song_metadata import MetadataFields

logger = logging.getLogger(__name__)


class TreeComponent(AppComponent):
    """Tree view component for song list."""

    @override
    def initialize_state(self) -> None:
        self.dragged_column = None
        self.highlighted_column = None

        self.column_order = [
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

    @override
    def setup_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Extended columns to show all JSON elements
        self.tree = ttk.Treeview(
            self,
            columns=self.column_order,
            show="headings",
            selectmode="extended",
        )

        # Configure treeview style - will be updated by theme
        self.style = ttk.Style()
        self.update_theme()

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

        for col in self.column_order:
            heading, width, anchor = column_configs[col]
            self.tree.heading(col, text=heading)
            # Disable automatic stretching so horizontal scrollbar appears
            self.tree.column(col, width=width, anchor=anchor, stretch=False)

        # Enable column reordering
        self.tree.bind("<Button-1>", self.on_tree_click)

        self.tree.bind("<<TreeviewSelect>>", self.app.on_tree_select)
        # Double-click to play song
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Right-click context menu
        self.tree.bind("<Button-3>", self.on_tree_right_click)
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Copy", command=lambda: None)
        self.context_menu.add_command(label="Copy JSON", command=lambda: None)

        # Vertical scrollbar
        self.tree_scroll_v = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scroll_v.set)

        # Horizontal scrollbar
        self.tree_scroll_h = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=self.tree_scroll_h.set)

        # Grid the tree and scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree_scroll_v.grid(row=0, column=1, sticky="ns")
        self.tree_scroll_h.grid(row=1, column=0, sticky="ew")

    @override
    def update_theme(self) -> None:
        try:
            dark = SettingsManager.is_dark_mode()
            self.style.theme_use("default")
            self.style.configure(
                "Treeview",
                background="#2b2b2b" if dark else "white",
                foreground="white" if dark else "black",
                fieldbackground="#2b2b2b" if dark else "white",
                borderwidth=0,
            )
            self.style.configure(
                "Treeview.Heading",
                background="#3b3b3b" if dark else "#f0f0f0",
                foreground="white" if dark else "black",
                relief="flat",
            )
            self.style.map(
                "Treeview",
                background=[("selected", "#1f6aa5" if dark else "#0078d7")],
            )
            self.style.map(
                "Treeview.Heading",
                background=[("active", "#4b4b4b" if dark else "#e0e0e0")],
            )
        except Exception:
            logger.exception("Error updating treeview style")

    @override
    def register_events(self) -> None:
        self.app.bind("<<TreeComponent:RefreshTree>>", self.app.refresh_tree)

    def on_tree_click(self, event: tk.Event) -> None:
        """Handle column header clicks for reordering."""
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            column = self.tree.identify_column(event.x)
            column_index = int(column.replace("#", "")) - 1
            if 0 <= column_index < len(self.column_order):
                self.dragged_column = self.column_order[column_index]
                self.tree.bind("<B1-Motion>", self.on_column_drag)
                self.tree.bind("<ButtonRelease-1>", self.on_column_drop)

    def on_tree_right_click(self, event: tk.Event) -> None:
        """Handle right-click context menu to copy cell value."""
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            row_id = self.tree.identify_row(event.y)
            col = self.tree.identify_column(event.x)

            if row_id and col:
                try:
                    # Determine column index from identifier like '#1'
                    col_index = int(col.replace("#", "")) - 1
                    values = self.tree.item(row_id, "values")

                    if 0 <= col_index < len(values):
                        # Get column name
                        col_id = self.column_order[col_index]
                        col_name = self.tree.heading(col_id, "text")

                        value = str(values[col_index])

                        # Copy <Col>
                        self.context_menu.entryconfigure(
                            0,
                            label=f"Copy {col_name}",
                            command=lambda: self.copy_to_clipboard(value),
                        )

                        # Copy JSON
                        try:
                            idx = int(row_id)
                            path = self.app.song_files[idx]
                            metadata = self.app.file_manager.get_metadata(path)
                            json_data = json.dumps(metadata.raw_data, indent=2)
                            self.context_menu.entryconfigure(
                                1,
                                state="normal",
                                command=lambda: self.copy_to_clipboard(json_data),
                            )
                        except Exception:
                            self.context_menu.entryconfigure(1, state="disabled")

                        self.context_menu.tk_popup(event.x_root, event.y_root)
                except ValueError:
                    pass

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text to system clipboard."""
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()  # Required to finalize clipboard update

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

        if idx < 0 or idx >= len(self.app.song_files):
            return

        try:
            if not song_utils.play_song(self.app.song_files[idx]):
                song_utils.show_audio_player_instructions()
        except Exception as e:
            messagebox.showerror("Playback Error", f"Could not play file:\n{e!s}")

    def on_column_drag(self, event: tk.Event) -> None:
        """Visual feedback during column drag."""
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
                if target != self.highlighted_column:
                    # clear previous
                    if self.highlighted_column:
                        with contextlib.suppress(Exception):
                            self.tree.heading(self.highlighted_column, background="")
                    # set new highlight (color depends on theme)
                    try:
                        hl = "#4b94d6" if (SettingsManager.theme == "Light") else "#3b6ea0"
                        self.tree.heading(target, background=hl)
                        self.highlighted_column = target
                    except Exception:
                        self.highlighted_column = None

    def on_column_drop(self, event: tk.Event) -> None:
        """Handle column reordering when dropped."""
        self.tree.unbind("<B1-Motion>")
        self.tree.unbind("<ButtonRelease-1>")
        # clear any header highlight
        if self.highlighted_column:
            with contextlib.suppress(Exception):
                self.tree.heading(self.highlighted_column, background="")
            self.highlighted_column = None

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
            with contextlib.suppress(Exception):
                self.tree.selection_set(selection)
        try:
            self.tree.yview_moveto(scroll_v[0])
            self.tree.xview_moveto(scroll_h[0])
        except Exception:
            pass

    def get_row_values(self, row: dict) -> tuple:
        """Extract and format values for treeview columns from a data row."""
        values = []
        for col in self.column_order:
            data_key = RuleManager.COL_MAP.get(col)
            if col == MetadataFields.UI_VERSION:
                v = row.get(MetadataFields.VERSION, 0.0)
                val = str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
            else:
                val = row.get(data_key, "") if data_key else ""
            values.append(str(val))
        return tuple(values)

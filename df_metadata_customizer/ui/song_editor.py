"""Song editor panel UI and actions."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QAbstractItemView,
    QGroupBox,
    QFormLayout,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QScrollArea,
    QMenu,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFontMetrics, QCursor

from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TRCK, TPOS, TDRC, TPE2, APIC, COMM

from df_metadata_customizer.core.metadata import MetadataFields
from df_metadata_customizer.core.settings_manager import SettingsManager
from df_metadata_customizer.core.song_utils import extract_json_from_song, get_id3_tags, get_cover_art
from df_metadata_customizer.core.preset_service import PresetService
from df_metadata_customizer.core.remuxer import remux_song
from df_metadata_customizer.core.audio_hash import get_audio_hash
from df_metadata_customizer.ui.rule_widgets import NoScrollComboBox
from df_metadata_customizer.ui.platform_utils import open_file_with_player, get_available_players


ALBUM_ARTIST = "QueenPb + vedal987"


class SongEditorManager:
    """Manage the Song Edit tab UI and actions."""

    def __init__(self, parent, preset_service: PresetService):
        self.parent = parent
        self.pending_songs: list[dict[str, Any]] = []
        self.current_edit_id: int | None = None
        self.preset_service = preset_service
        self._next_id = 1
        self._current_cover_bytes: bytes | None = None
        self._persistent_date: str | None = None  # Keep track of user-set date
        self._persistent_disc: str | None = None  # Keep track of user-set disc
        self._active_menu = None  # Track active context menu
        self._original_id3: dict[str, str] = {}  # Store original ID3 values from file
        self._preset_applied: bool = False  # Track if preset has been applied
        self._theme_colors: dict | None = None
        self._is_dark: bool = True

        self.pending_tree: QTreeWidget | None = None
        self.source_label: QLabel | None = None
        self.preset_combo: NoScrollComboBox | None = None
        self.cover_label: QLabel | None = None
        self.add_btn: QPushButton | None = None
        self.update_btn: QPushButton | None = None

        self.json_fields: dict[str, QLineEdit] = {}
        self.id3_fields: dict[str, QLineEdit] = {}

    def _get_ui_scale(self) -> float:
        """Get UI scale factor from settings."""
        try:
            return SettingsManager.ui_scale or 1.0
        except:
            return 1.0

    def _scale(self, value: int) -> int:
        """Scale a value by the current UI scale factor."""
        return int(value * self._get_ui_scale())

    def _elide_text(self, text: str, font: QFontMetrics, width: int) -> str:
        """Elide text with ... if it exceeds width."""
        return font.elidedText(text, Qt.TextElideMode.ElideMiddle, width)

    def _style_input_field(self, widget: QLineEdit) -> None:
        """Apply consistent styling to input fields."""
        c = self._theme_colors or {
            "bg_primary": "#1e1e1e",
            "border": "#3d3d3d",
            "text": "#ffffff",
            "button": "#0d47a1",
        }
        widget.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['bg_primary']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 2px solid {c['button']}; }}
        """)

    def _set_field_tooltip(self, widget, full_text: str) -> None:
        """Set tooltip on a widget to show full text if it exists."""
        if full_text and hasattr(widget, 'setToolTip'):
            widget.setToolTip(str(full_text))

    def _validate_numeric_field(self, field: QLineEdit) -> None:
        """Validate that field contains only numbers and decimal point."""
        text = field.text()
        cursor_pos = field.cursorPosition()
        # Allow only digits and decimal point
        cleaned = ''.join(c for c in text if c.isdigit() or c == '.')
        if cleaned != text:
            field.blockSignals(True)
            field.setText(cleaned)
            field.setCursorPosition(min(cursor_pos, len(cleaned)))
            field.blockSignals(False)

    def _validate_track_field(self, field: QLineEdit) -> None:
        """Validate that field contains only numbers and forward slash (for track format like 5/12)."""
        text = field.text()
        cursor_pos = field.cursorPosition()
        # Allow only digits and forward slash
        cleaned = ''.join(c for c in text if c.isdigit() or c == '/')
        if cleaned != text:
            field.blockSignals(True)
            field.setText(cleaned)
            field.setCursorPosition(min(cursor_pos, len(cleaned)))
            field.blockSignals(False)

    def _sanitize_filename(self, text: str) -> str:
        """Sanitize text for use in filename by replacing invalid characters."""
        # Replace invalid filename characters with underscores or alternatives
        replacements = {
            '\\': ' backslash ',
            '/': ' slash ',
            ':': ' ',
            '*': '_',
            '?': ' ',
            '"': "'",
            '<': '[',
            '>': ']',
            '|': '_'
        }
        result = text
        for invalid, replacement in replacements.items():
            result = result.replace(invalid, replacement)
        return result.strip()

    def _format_number_for_filename(self, value: str | int | float) -> str:
        """Format a number without .0 for integers. If value contains '/', use only the first number."""
        try:
            # Handle track format like "5/12" - use only first number
            if isinstance(value, str) and "/" in value:
                value = value.split("/")[0].strip()
            num = float(value) if isinstance(value, str) else value
            return str(int(num)) if num == int(num) else str(num)
        except (ValueError, TypeError):
            return str(value)

    def _generate_filename(self, json_data: dict, source_ext: str = ".mp3") -> str:
        """Generate filename from JSON metadata: {3 padded track}. {Artist} - {Title} ({CoverArtist}.v{Version}).ext"""
        track = json_data.get(MetadataFields.TRACK, "1")
        artist = json_data.get(MetadataFields.ARTIST, "Unknown")
        title = json_data.get(MetadataFields.TITLE, "Untitled")
        cover_artist = json_data.get(MetadataFields.COVER_ARTIST, "Unknown")
        version = json_data.get(MetadataFields.VERSION, "1")
        
        # Format track with 3-digit padding
        track_num = self._format_number_for_filename(track)
        track_padded = str(track_num).zfill(3)
        
        # Format version without .0
        version_formatted = self._format_number_for_filename(version)
        
        # Sanitize all parts
        artist_safe = self._sanitize_filename(artist)
        title_safe = self._sanitize_filename(title)
        cover_artist_safe = self._sanitize_filename(cover_artist)
        
        # Build filename
        if str(cover_artist).strip() in ("Neuro", "Evil"):
            filename_suffix = f"({cover_artist_safe}.v{version_formatted})"
        else:
            filename_suffix = f"(Duet.v{version_formatted}) ({cover_artist_safe})"
        filename = f"{track_padded}. {artist_safe} - {title_safe} {filename_suffix}{source_ext}"
        return filename

    def create_song_edit_tab(self):
        """Create song metadata editor for adding new songs."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)


        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # Top: Editor
        editor_panel = QFrame()
        editor_panel.setMinimumHeight(250)  # Prevent complete collapse
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(8)

        source_row = QHBoxLayout()
        self.source_label = QLabel("Source: (none)")
        self.source_label.setStyleSheet("color: #aaaaaa;")
        self.source_label.setWordWrap(False)
        self.source_label.setMaximumWidth(600)
        self.source_label.setTextFormat(Qt.TextFormat.PlainText)
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        source_row.addWidget(self.source_label, 1)

        pick_btn = QPushButton("Add New Song")
        pick_btn.clicked.connect(self.pick_source_file)
        source_row.addWidget(pick_btn)
        editor_layout.addLayout(source_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QFrame()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)

        # JSON Metadata
        json_group = QGroupBox("JSON Metadata")
        json_form = QFormLayout(json_group)
        self.json_fields = self._create_json_fields(json_form)
        scroll_layout.addWidget(json_group)

        # ID3 Metadata
        id3_group = QGroupBox("ID3v2.4 Tags")
        id3_form = QFormLayout(id3_group)
        self.id3_fields = self._create_id3_fields(id3_form)

        # Initialize default JSON/ID3 values on first load
        self._fill_json_fields({})
        self._fill_id3_fields({})

        scroll_layout.addWidget(id3_group)

        # Cover
        cover_group = QGroupBox("Cover Art")
        cover_layout = QVBoxLayout(cover_group)
        self.cover_label = QLabel("No cover")
        self.cover_label.setFixedSize(160, 160)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("border: 1px solid #3d3d3d;")
        cover_layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignHCenter)

        cover_btns = QHBoxLayout()
        load_cover_btn = QPushButton("Load Cover")
        load_cover_btn.clicked.connect(self.load_cover_from_file)
        cover_btns.addWidget(load_cover_btn)

        clear_cover_btn = QPushButton("Clear")
        clear_cover_btn.clicked.connect(self.clear_cover)
        cover_btns.addWidget(clear_cover_btn)
        cover_layout.addLayout(cover_btns)
        scroll_layout.addWidget(cover_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        editor_layout.addWidget(scroll, 1)

        # Editor buttons
        editor_btns = QHBoxLayout()
        self.add_btn = QPushButton("Add to List")
        self.add_btn.clicked.connect(self.add_or_update_pending)
        editor_btns.addWidget(self.add_btn)

        self.update_btn = QPushButton("Update Selected")
        self.update_btn.clicked.connect(self.update_selected_pending)
        editor_btns.addWidget(self.update_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset_editor)
        editor_btns.addWidget(reset_btn)
        editor_btns.addStretch()
        editor_layout.addLayout(editor_btns)
        self._update_action_button_styles()

        splitter.addWidget(editor_panel)

        # Bottom: Pending list
        pending_panel = QFrame()
        pending_panel.setMinimumHeight(150)  # Prevent complete collapse
        pending_layout = QVBoxLayout(pending_panel)
        pending_layout.setContentsMargins(0, 0, 0, 0)
        pending_layout.setSpacing(6)

        pending_label = QLabel("Pending New Songs")
        pending_label.setStyleSheet("font-weight: bold;")
        pending_layout.addWidget(pending_label)

        self.pending_tree = QTreeWidget()
        self.pending_tree.setMouseTracking(True)
        self.pending_tree.setColumnCount(6)
        self.pending_tree.setHeaderLabels(["Source File", "Filename", "Title", "Artist", "Track", "Date"])
        self.pending_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pending_tree.itemDoubleClicked.connect(self._on_pending_play_song)
        self.pending_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pending_tree.customContextMenuRequested.connect(self._on_pending_right_click)
        
        # Apply styling with column separators like main tree
        self.pending_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #252525;
                border: 1px solid #3d3d3d;
                gridline-color: #3d3d3d;
            }
            QTreeWidget::item {
                border-right: 1px solid #3d3d3d;
                padding: 2px;
            }
            QTreeWidget::item:selected { background-color: #0d47a1; }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 4px;
                border: none;
                border-right: 1px solid #555555;
                border-bottom: 1px solid #555555;
            }
        """)
        
        # Load saved column widths or set defaults
        pending_widths = SettingsManager.pending_column_widths or [180, 250, 150, 120, 60, 80]
        header = self.pending_tree.header()
        for i, width in enumerate(pending_widths):
            self.pending_tree.setColumnWidth(i, width)
        header.sectionResized.connect(self._on_pending_column_resized)
        
        pending_layout.addWidget(self.pending_tree, 1)

        pending_btns = QHBoxLayout()
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_selected_pending)
        pending_btns.addWidget(remove_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_pending_list)
        pending_btns.addWidget(clear_btn)

        save_all_btn = QPushButton("Save All")
        save_all_btn.setStyleSheet("background-color: #0d47a1; color: white;")
        save_all_btn.clicked.connect(self.save_all_pending)
        pending_btns.addWidget(save_all_btn)

        pending_layout.addLayout(pending_btns)
        splitter.addWidget(pending_panel)

        splitter.setSizes([500, 200])
        layout.addWidget(splitter, 1)

        return frame

    def _create_json_fields(self, form: QFormLayout) -> dict[str, QLineEdit]:
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        h_scale = self._scale(32)
        label_w1 = self._scale(140)
        label_w2 = self._scale(75)
        label_w3 = self._scale(100)
        spacing = self._scale(12)
        
        out: dict[str, QLineEdit] = {}
        
        # Row 1: Title (full width)
        title_edit = QLineEdit()
        title_edit.setFixedHeight(h_scale)
        self._style_input_field(title_edit)
        form.addRow("Title:", title_edit)
        out[MetadataFields.TITLE] = title_edit
        
        # Row 2: Artist (full width)
        artist_edit = QLineEdit()
        artist_edit.setFixedHeight(h_scale)
        self._style_input_field(artist_edit)
        form.addRow("Artist:", artist_edit)
        out[MetadataFields.ARTIST] = artist_edit
        
        # Row 3: Cover Artist, Version, Date (compact)
        compact_row1 = QHBoxLayout()
        compact_row1.setSpacing(spacing)
        compact_row1.setContentsMargins(0, 0, 0, 0)
        compact_row1.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        cover_artist_label = QLabel("Cover Artist:")
        cover_artist_label.setFixedWidth(label_w1)
        cover_artist_label.setFixedHeight(h_scale)
        cover_artist_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        cover_artist_edit = QLineEdit()
        cover_artist_edit.setFixedHeight(h_scale)
        cover_artist_edit.setMinimumWidth(self._scale(60))
        self._style_input_field(cover_artist_edit)
        compact_row1.addWidget(cover_artist_label)
        compact_row1.addWidget(cover_artist_edit, 1)
        out[MetadataFields.COVER_ARTIST] = cover_artist_edit
        
        version_label = QLabel("Version:")
        version_label.setFixedWidth(label_w2)
        version_label.setFixedHeight(h_scale)
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        version_edit = QLineEdit()
        version_edit.setFixedHeight(h_scale)
        version_edit.setMinimumWidth(self._scale(40))
        self._style_input_field(version_edit)
        version_edit.textChanged.connect(lambda: self._validate_numeric_field(version_edit))
        compact_row1.addWidget(version_label)
        compact_row1.addWidget(version_edit, 1)
        out[MetadataFields.VERSION] = version_edit
        
        date_label = QLabel("Date:")
        date_label.setFixedWidth(label_w3)
        date_label.setFixedHeight(h_scale)
        date_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        date_edit = QLineEdit()
        date_edit.setFixedHeight(h_scale)
        date_edit.setMinimumWidth(self._scale(60))
        self._style_input_field(date_edit)
        compact_row1.addWidget(date_label)
        compact_row1.addWidget(date_edit, 1)
        out[MetadataFields.DATE] = date_edit
        form.addRow(compact_row1)
        
        # Row 4: Disc, Track, Special (compact)
        compact_row2 = QHBoxLayout()
        compact_row2.setSpacing(spacing)
        compact_row2.setContentsMargins(0, 0, 0, 0)
        compact_row2.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        disc_label = QLabel("Disc:")
        disc_label.setFixedWidth(label_w1)
        disc_label.setFixedHeight(h_scale)
        disc_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        disc_edit = QLineEdit()
        disc_edit.setFixedHeight(h_scale)
        disc_edit.setMinimumWidth(self._scale(40))
        self._style_input_field(disc_edit)
        disc_edit.textChanged.connect(lambda: self._validate_numeric_field(disc_edit))
        compact_row2.addWidget(disc_label)
        compact_row2.addWidget(disc_edit, 1)
        out[MetadataFields.DISC] = disc_edit
        
        track_label = QLabel("Track:")
        track_label.setFixedWidth(label_w2)
        track_label.setFixedHeight(h_scale)
        track_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        track_edit = QLineEdit()
        track_edit.setFixedHeight(h_scale)
        track_edit.setMinimumWidth(self._scale(40))
        self._style_input_field(track_edit)
        track_edit.textChanged.connect(lambda: self._validate_track_field(track_edit))
        compact_row2.addWidget(track_label)
        compact_row2.addWidget(track_edit, 1)
        out[MetadataFields.TRACK] = track_edit
        
        special_label = QLabel("Special:")
        special_label.setFixedWidth(label_w3)
        special_label.setFixedHeight(h_scale)
        special_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        special_edit = QLineEdit()
        special_edit.setFixedHeight(h_scale)
        special_edit.setMinimumWidth(self._scale(40))
        self._style_input_field(special_edit)
        special_edit.textChanged.connect(lambda: self._validate_numeric_field(special_edit))
        compact_row2.addWidget(special_label)
        compact_row2.addWidget(special_edit, 1)
        out[MetadataFields.SPECIAL] = special_edit
        form.addRow(compact_row2)
        
        # Row 5: Comment (full width)
        comment_edit = QLineEdit()
        comment_edit.setFixedHeight(h_scale)
        self._style_input_field(comment_edit)
        form.addRow("Comment:", comment_edit)
        out[MetadataFields.COMMENT] = comment_edit
        
        # Row 6: xxHash (full width, read-only)
        xxhash_display = QLabel("-")
        xxhash_display.setStyleSheet("color: #888888; font-style: italic;")
        xxhash_display.setFixedHeight(h_scale)
        form.addRow("xxHash:", xxhash_display)
        out["xxHash"] = xxhash_display
        
        # Connect signals to update ID3 display fields when JSON fields change
        if MetadataFields.DISC in out:
            out[MetadataFields.DISC].textChanged.connect(self._update_id3_from_json)
        if MetadataFields.TRACK in out:
            out[MetadataFields.TRACK].textChanged.connect(self._update_id3_from_json)
        if MetadataFields.DATE in out:
            out[MetadataFields.DATE].textChanged.connect(self._update_id3_from_json)
        if MetadataFields.COMMENT in out:
            out[MetadataFields.COMMENT].textChanged.connect(self._update_id3_from_json)
        
        return out

    def _create_id3_fields(self, form: QFormLayout) -> dict[str, QLineEdit]:
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        h_scale = self._scale(32)
        label_w1 = self._scale(110)
        label_w2 = self._scale(65)
        label_w3 = self._scale(50)
        spacing = self._scale(12)
        
        out: dict[str, QLineEdit] = {}
        
        # Row 0: Preset selector with Apply button
        preset_row = QHBoxLayout()
        preset_row.setSpacing(spacing)
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.preset_combo = NoScrollComboBox()
        self.preset_combo.setFixedHeight(h_scale)
        self.preset_combo.setMinimumWidth(self._scale(220))
        self.preset_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
                padding-right: 20px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
                background-color: transparent;
            }
            QComboBox::down-arrow {
                image: none;  /* We draw the arrow manually in paintEvent */
            }
        """)
        self._load_presets()
        preset_row.addWidget(self.preset_combo, 1)
        
        apply_preset_btn = QPushButton("Apply")
        apply_preset_btn.setFixedHeight(h_scale)
        apply_preset_btn.setMaximumWidth(self._scale(80))
        apply_preset_btn.clicked.connect(self.apply_preset_to_id3)
        preset_row.addWidget(apply_preset_btn)

        clear_preset_btn = QPushButton("Clear")
        clear_preset_btn.setFixedHeight(h_scale)
        clear_preset_btn.setMaximumWidth(self._scale(80))
        clear_preset_btn.clicked.connect(self._clear_preset)
        preset_row.addWidget(clear_preset_btn)
        
        form.addRow("Preset:", preset_row)
        
        # Row 1: Title (full width)
        title_edit = QLineEdit()
        title_edit.setFixedHeight(h_scale)
        self._style_input_field(title_edit)
        title_edit.textChanged.connect(lambda: self._on_id3_field_edited())
        form.addRow("Title:", title_edit)
        out["Title"] = title_edit
        
        # Row 2: Artist (full width)
        artist_edit = QLineEdit()
        artist_edit.setFixedHeight(h_scale)
        self._style_input_field(artist_edit)
        artist_edit.textChanged.connect(lambda: self._on_id3_field_edited())
        form.addRow("Artist:", artist_edit)
        out["Artist"] = artist_edit
        
        # Row 3: Album (full width)
        album_edit = QLineEdit()
        album_edit.setFixedHeight(h_scale)
        self._style_input_field(album_edit)
        album_edit.textChanged.connect(lambda: self._on_id3_field_edited())
        form.addRow("Album:", album_edit)
        out["Album"] = album_edit
        
        # Row 4: Disc, Track, Date (compact, display-only, driven by JSON)
        compact_row = QHBoxLayout()
        compact_row.setSpacing(spacing)
        compact_row.setContentsMargins(0, 0, 0, 0)
        compact_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        disc_label = QLabel("Disc:")
        disc_label.setFixedWidth(label_w1)
        disc_label.setFixedHeight(h_scale)
        disc_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        disc_display = QLabel("-")
        disc_display.setFixedHeight(h_scale)
        disc_display.setMinimumWidth(self._scale(40))
        disc_display.setStyleSheet("color: #888888;")
        disc_display.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        compact_row.addWidget(disc_label)
        compact_row.addWidget(disc_display, 1)
        out["Discnumber"] = disc_display
        
        track_label = QLabel("Track:")
        track_label.setFixedWidth(label_w2)
        track_label.setFixedHeight(h_scale)
        track_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        track_display = QLabel("-")
        track_display.setFixedHeight(h_scale)
        track_display.setMinimumWidth(self._scale(40))
        track_display.setStyleSheet("color: #888888;")
        track_display.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        compact_row.addWidget(track_label)
        compact_row.addWidget(track_display, 1)
        out["Track"] = track_display
        
        date_label = QLabel("Year:")
        date_label.setFixedWidth(label_w3)
        date_label.setFixedHeight(h_scale)
        date_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        date_display = QLabel("-")
        date_display.setFixedHeight(h_scale)
        date_display.setMinimumWidth(self._scale(40))
        date_display.setStyleSheet("color: #888888;")
        date_display.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        compact_row.addWidget(date_label)
        compact_row.addWidget(date_display, 1)
        out["Date"] = date_display
        form.addRow(compact_row)
        
        # Row 5: COMM:eng preview (shows what will be written to ID3)
        comm_eng_display = QLabel("-")
        comm_eng_display.setStyleSheet("color: #888888;")
        comm_eng_display.setFixedHeight(h_scale)
        comm_eng_display.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        form.addRow("COMM:eng:", comm_eng_display)
        out["COMM_eng_preview"] = comm_eng_display
        
        # Row 6: Filename (auto-generated from JSON, display-only)
        filename_display = QLabel("-")
        filename_display.setStyleSheet("color: #888888; font-style: italic;")
        filename_display.setFixedHeight(h_scale)
        filename_display.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        form.addRow("Filename:", filename_display)
        out["Filename"] = filename_display
        
        return out

    def _load_presets(self) -> None:
        if self.preset_combo is None:
            return
        self.preset_combo.clear()
        try:
            presets = self.preset_service.list_presets() or []
            if not presets:
                presets = [p.stem for p in SettingsManager.get_presets_folder().glob("*.json")]
            if presets:
                self.preset_combo.addItems(sorted(presets))
        except Exception as e:
            print(f"Error loading presets: {e}")
            import traceback
            traceback.print_exc()

    def pick_source_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent,
            "Select Source MP3",
            "",
            "MP3 Files (*.mp3)",
        )
        if not file_path:
            return
        self.load_from_path(file_path)

    def copy_as_new_song(self, file_data: dict) -> None:
        """Copy only Title and Artist from selected song, don't change source."""
        raw_json = file_data.get("raw_json", {})
        title = raw_json.get(MetadataFields.TITLE, "")
        artist = raw_json.get(MetadataFields.ARTIST, "")
        
        # Only fill Title and Artist fields
        if MetadataFields.TITLE in self.json_fields:
            self.json_fields[MetadataFields.TITLE].setText(title)
        if MetadataFields.ARTIST in self.json_fields:
            self.json_fields[MetadataFields.ARTIST].setText(artist)
        
        # Don't change source or other fields, just copy these two values
        self.current_edit_id = None

    def load_from_path(self, file_path: str, json_data: dict | None = None) -> None:
        jsond = json_data or extract_json_from_song(file_path) or {}
        id3 = get_id3_tags(file_path)
        cover = get_cover_art(file_path)

        # Store original ID3 values and mark preset as not applied
        self._original_id3 = id3.copy()
        self._preset_applied = False

        # Remux and compute xxHash when file is chosen
        try:
            temp_output = Path(file_path).parent / f"temp_{Path(file_path).stem}.mp3"
            remux_song(file_path, str(temp_output))
            xxhash_value = get_audio_hash(str(temp_output)) or ""
            if temp_output.exists():
                temp_output.unlink()
            if xxhash_value:
                jsond["xxHash"] = xxhash_value
        except Exception as e:
            print(f"Warning: Could not compute xxHash: {e}")

        self._current_cover_bytes = cover
        self._apply_cover_preview(cover)

        self._set_source_label(file_path)
        self._fill_json_fields(jsond)
        self._fill_id3_fields(id3)
        self.current_edit_id = None
        self._update_action_button_styles()

    def _set_source_label(self, path: str) -> None:
        if self.source_label:
            # Truncate long paths from the middle
            if len(path) > 70:
                parts = Path(path).parts
                if len(parts) > 3:
                    display_path = str(Path(parts[0]) / "..." / parts[-2] / parts[-1])
                else:
                    display_path = f"...{path[-67:]}"
            else:
                display_path = path
            self.source_label.setText(f"Source: {display_path}")
            self.source_label.setToolTip(path)

    def _fill_json_fields(self, jsond: dict) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        
        for key, field in self.json_fields.items():
            if key == "xxHash":
                # xxHash is display-only
                if isinstance(field, QLabel):
                    xxhash_val = jsond.get("xxHash", "-")
                    field.setText(str(xxhash_val) if xxhash_val else "-")
                    self._set_field_tooltip(field, str(xxhash_val) if xxhash_val else "-")
            else:
                if hasattr(field, 'setText'):
                    value = jsond.get(key, "")
                    # Set defaults for Special, Date, and Comment
                    if key == MetadataFields.SPECIAL and not value:
                        value = "0"
                    elif key == MetadataFields.DATE and not value:
                        value = self._persistent_date or today
                    elif key == MetadataFields.COMMENT and not value:
                        value = "None"
                    field.setText(str(value))
                    self._set_field_tooltip(field, str(value))
        # Sync comment to ID3 display
        self._sync_comment_to_id3(jsond.get(MetadataFields.COMMENT, ""))
        # Update ID3 display fields (Disc, Track, Date) from JSON
        self._update_id3_display_fields(jsond)
        # Update filename display and COMM:eng preview
        self._update_filename_display(jsond)
        self._update_comm_eng_preview(jsond)

    def _update_id3_display_fields(self, jsond: dict) -> None:
        """Update the display-only ID3 fields from JSON field values."""
        # Read from self.json_fields UI widgets, not from jsond parameter
        if "Discnumber" in self.id3_fields:
            field = self.id3_fields["Discnumber"]
            if isinstance(field, QLabel):
                disc_val = ""
                if MetadataFields.DISC in self.json_fields:
                    json_field = self.json_fields[MetadataFields.DISC]
                    if hasattr(json_field, 'text'):
                        disc_val = json_field.text().strip()
                field.setText(str(disc_val) if disc_val else "-")
                self._set_field_tooltip(field, str(disc_val) if disc_val else "-")
        
        if "Track" in self.id3_fields:
            field = self.id3_fields["Track"]
            if isinstance(field, QLabel):
                track_val = ""
                if MetadataFields.TRACK in self.json_fields:
                    json_field = self.json_fields[MetadataFields.TRACK]
                    if hasattr(json_field, 'text'):
                        track_val = json_field.text().strip()
                field.setText(str(track_val) if track_val else "-")
                self._set_field_tooltip(field, str(track_val) if track_val else "-")
        
        if "Date" in self.id3_fields:
            field = self.id3_fields["Date"]
            if isinstance(field, QLabel):
                date_val = ""
                full_date_val = ""
                if MetadataFields.DATE in self.json_fields:
                    json_field = self.json_fields[MetadataFields.DATE]
                    if hasattr(json_field, 'text'):
                        full_date = json_field.text().strip()
                        full_date_val = full_date
                        # Extract just the year from yyyy-mm-dd format
                        if full_date and len(full_date) >= 4:
                            date_val = full_date[:4]
                        else:
                            date_val = full_date
                field.setText(str(date_val) if date_val else "-")
                # Show the full date in tooltip
                self._set_field_tooltip(field, full_date_val if full_date_val else "-")

    def _update_id3_from_json(self) -> None:
        """Update ID3 display fields and previews when JSON fields change."""
        self._update_id3_display_fields({})
        # Also update COMM:eng preview
        json_data = self._collect_json_data()
        self._update_comm_eng_preview(json_data)
        self._update_filename_display(json_data)

    def _fill_id3_fields(self, id3: dict) -> None:
        for key, field in self.id3_fields.items():
            if key == "Filename":
                # Filename is auto-generated, skip
                continue
            if isinstance(field, QLabel):
                # Skip label fields
                continue
            value = str(id3.get(key, ""))
            field.setText(value)
            self._set_field_tooltip(field, value)
        # Update styling based on whether original values are shown
        self._update_id3_field_styling()

    def _update_filename_display(self, jsond: dict) -> None:
        """Update the filename display based on JSON data."""
        if "Filename" in self.id3_fields:
            filename_field = self.id3_fields["Filename"]
            if isinstance(filename_field, QLabel):
                # Get source extension, default to .mp3
                source_path = self._current_source_path()
                source_ext = Path(source_path).suffix if source_path else ".mp3"
                filename = self._generate_filename(jsond, source_ext)
                filename_field.setText(filename)
                self._set_field_tooltip(filename_field, filename)
        # Update COMM:eng preview
        self._update_comm_eng_preview(jsond)

    def _update_comm_eng_preview(self, jsond: dict) -> None:
        """Update the COMM:eng preview based on JSON data."""
        if "COMM_eng_preview" not in self.id3_fields:
            return
        field = self.id3_fields["COMM_eng_preview"]
        if not isinstance(field, QLabel):
            return
        
        comment_text = jsond.get(MetadataFields.COMMENT)
        date_str = jsond.get(MetadataFields.DATE, datetime.now().strftime("%Y-%m-%d"))
        
        # If comment is None or "None" string, just use date
        if comment_text is None or str(comment_text).strip().lower() == "none":
            comm_text = date_str
        else:
            comm_text = f"{date_str} //{comment_text}"
        
        field.setText(comm_text)
        self._set_field_tooltip(field, comm_text)

    def _on_id3_field_edited(self) -> None:
        """Handle manual edits to ID3 fields - update styling to reflect changes."""
        # Update styling when user manually edits fields
        self._update_id3_field_styling()

    def _update_id3_field_styling(self) -> None:
        """Update styling of ID3 fields to show if they're original (italic) or modified (normal)."""
        c = self._theme_colors or {
            "bg_primary": "#1e1e1e",
            "bg_secondary": "#2b2b2b",
            "border": "#3d3d3d",
            "text": "#ffffff",
            "text_secondary": "#888888",
            "button": "#0d47a1",
        }
        dim_bg = c.get("bg_secondary", c["bg_primary"])
        dim_text = c.get("text_secondary", "#888888")
        for key, field in self.id3_fields.items():
            if key in ("Filename", "Discnumber", "Track", "Date", "COMM_eng_preview", "Comment"):
                # Skip fields that are display-only or driven by JSON
                continue
            if isinstance(field, QLabel):
                continue
            if not isinstance(field, QLineEdit):
                continue
            
            # Check if current value matches original value
            current_value = field.text().strip()
            original_value = self._original_id3.get(key, "").strip()
            
            # If no preset applied and value matches original, show in italic/dimmed
            if not self._preset_applied and current_value == original_value and original_value:
                field.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {dim_bg};
                        color: {dim_text};
                        border: 1px solid {c['border']};
                        border-radius: 4px;
                        padding: 4px 8px;
                        font-style: italic;
                    }}
                    QLineEdit:focus {{ border: 2px solid {c['button']}; }}
                """)
            else:
                # Normal styling for modified or preset-applied values
                self._style_input_field(field)


    def _apply_cover_preview(self, cover_bytes: bytes | None) -> None:
        if not self.cover_label:
            return
        if not cover_bytes:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("No cover")
            return
        pixmap = QPixmap()
        pixmap.loadFromData(cover_bytes)
        if not pixmap.isNull():
            self.cover_label.setPixmap(pixmap.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.cover_label.setText("")
        else:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("Invalid cover")

    def load_cover_from_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent,
            "Select Cover Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if not file_path:
            return
        try:
            cover_bytes = Path(file_path).read_bytes()
            self._current_cover_bytes = cover_bytes
            self._apply_cover_preview(cover_bytes)
        except Exception as e:
            QMessageBox.warning(self.parent, "Error", f"Failed to load cover: {e}")

    def load_cover_from_source(self) -> None:
        source_path = self._current_source_path()
        if not source_path:
            return
        cover = get_cover_art(source_path)
        self._current_cover_bytes = cover
        self._apply_cover_preview(cover)

    def clear_cover(self) -> None:
        self._current_cover_bytes = None
        self._apply_cover_preview(None)

    def _current_source_path(self) -> str:
        if not self.source_label:
            return ""
        text = self.source_label.text().replace("Source:", "", 1).strip()
        return text if text and text != "(none)" else ""

    def _collect_json_data(self) -> dict:
        data = {}
        for key, field in self.json_fields.items():
            if key == "xxHash":
                # xxHash is display-only, get from label
                if isinstance(field, QLabel):
                    xxhash_val = field.text().strip()
                    if xxhash_val and xxhash_val != "-":
                        data[key] = xxhash_val
            else:
                if hasattr(field, 'text'):
                    data[key] = field.text().strip()
        # Sync comment to ID3 display
        self._sync_comment_to_id3(data.get(MetadataFields.COMMENT, ""))
        # Update filename display
        self._update_filename_display(data)
        return data

    def _sync_comment_to_id3(self, comment_text: str) -> None:
        """Update ID3 comment display with JSON comment text."""
        if "Comment" in self.id3_fields:
            comment_field = self.id3_fields["Comment"]
            if isinstance(comment_field, QLabel):
                comment_field.setText(comment_text if comment_text else "(empty)")

    def _collect_id3_data(self) -> dict:
        data = {}
        for key, field in self.id3_fields.items():
            # Skip fields that come from JSON (Discnumber, Track, Date)
            if key in ("Discnumber", "Track", "Date", "COMM_eng_preview", "Filename"):
                continue
            if key == "Comment":
                # Comment is always taken from JSON
                data[key] = self.json_fields.get(MetadataFields.COMMENT, QLineEdit()).text().strip()
            else:
                data[key] = field.text().strip() if isinstance(field, QLineEdit) else ""
        # Add Disc, Track, Date from JSON data
        data["Discnumber"] = self.json_fields.get(MetadataFields.DISC, QLineEdit()).text().strip() if MetadataFields.DISC in self.json_fields else ""
        data["Track"] = self.json_fields.get(MetadataFields.TRACK, QLineEdit()).text().strip() if MetadataFields.TRACK in self.json_fields else ""
        data["Date"] = self.json_fields.get(MetadataFields.DATE, QLineEdit()).text().strip() if MetadataFields.DATE in self.json_fields else ""
        data["AlbumArtist"] = ALBUM_ARTIST
        return data

    def _new_entry_id(self) -> int:
        val = self._next_id
        self._next_id += 1
        return val

    def add_or_update_pending(self) -> None:
        source_path = self._current_source_path()
        if not source_path:
            QMessageBox.warning(self.parent, "Missing Source", "Please choose a source audio file.")
            return

        json_data = self._collect_json_data()
        id3_data = self._collect_id3_data()

        # Get source file extension
        source_ext = Path(source_path).suffix if source_path else ".mp3"

        entry = {
            "id": self._new_entry_id() if self.current_edit_id is None else self.current_edit_id,
            "source_path": source_path,
            "filename": self._generate_filename(json_data, source_ext),
            "json": json_data,
            "id3": id3_data,
            "cover": self._current_cover_bytes,
        }

        if self.current_edit_id is None:
            self.pending_songs.append(entry)
        else:
            self._replace_pending(entry)

        self.refresh_pending_tree()
        self.current_edit_id = None
        self.reset_editor()
        self._auto_increment_track()

    def update_selected_pending(self) -> None:
        if self.current_edit_id is None:
            QMessageBox.information(self.parent, "No Selection", "Select a pending song to update.")
            return
        self.add_or_update_pending()

    def _replace_pending(self, entry: dict) -> None:
        for i, item in enumerate(self.pending_songs):
            if item.get("id") == entry.get("id"):
                self.pending_songs[i] = entry
                return

    def refresh_pending_tree(self) -> None:
        if not self.pending_tree:
            return
        self.pending_tree.clear()

        items = sorted(self.pending_songs, key=lambda x: x.get("filename", "").lower())
        for entry in items:
            json_data = entry.get("json", {})
            source_path = entry.get("source_path", "")
            source_filename = Path(source_path).name if source_path else ""
            item = QTreeWidgetItem([
                source_filename,
                entry.get("filename", ""),
                json_data.get(MetadataFields.TITLE, ""),
                json_data.get(MetadataFields.ARTIST, ""),
                json_data.get(MetadataFields.TRACK, ""),
                json_data.get(MetadataFields.DATE, ""),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, entry.get("id"))
            self.pending_tree.addTopLevelItem(item)

    def _on_pending_play_song(self, item: QTreeWidgetItem, column: int) -> None:
        """Play the source song file on double-click."""
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        for entry in self.pending_songs:
            if entry.get("id") == entry_id:
                source_path = entry.get("source_path", "")
                if source_path and Path(source_path).exists():
                    try:
                        # Use default_player if set, otherwise use system default
                        if SettingsManager.default_player:
                            open_file_with_player(source_path, SettingsManager.default_player)
                        else:
                            from df_metadata_customizer.ui.platform_utils import open_file_with_default_app
                            open_file_with_default_app(source_path)
                    except Exception as e:
                        QMessageBox.warning(self.parent, "Error", f"Cannot play file: {e}")
                return
    
    def _pending_play_with_player(self, item: QTreeWidgetItem, player_path: str) -> None:
        """Play pending file with specified player."""
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        for entry in self.pending_songs:
            if entry.get("id") == entry_id:
                source_path = entry.get("source_path", "")
                if source_path and Path(source_path).exists():
                    try:
                        open_file_with_player(source_path, player_path)
                    except Exception as e:
                        QMessageBox.warning(self.parent, "Error", f"Cannot play file: {e}")
                return
    
    def _pending_play_with_custom_player(self, item: QTreeWidgetItem) -> None:
        """Play pending file with custom player entered by user."""
        from PySide6.QtWidgets import QInputDialog, QFileDialog
        import platform
        
        # Ask if user wants to browse or enter path manually
        choice, ok = QInputDialog.getItem(
            self.parent,
            "Select Input Method",
            "How would you like to specify the player?",
            ["Browse for executable...", "Enter path or command manually..."],
            0,
            False
        )
        
        player_path = None
        
        if ok and choice:
            if choice == "Browse for executable...":
                # Open file browser
                if platform.system() == "Windows":
                    file_filter = "Executable Files (*.exe);;All Files (*.*)"
                else:
                    file_filter = "All Files (*)"
                
                player_path, _ = QFileDialog.getOpenFileName(
                    self.parent,
                    "Select Media Player",
                    "",
                    file_filter
                )
            else:
                # Manual input
                player_path, ok2 = QInputDialog.getText(
                    self.parent,
                    "Custom Player",
                    "Enter player path or command:",
                    text=SettingsManager.default_player or ""
                )
                if not ok2:
                    return
        else:
            return
        
        if player_path:
            entry_id = item.data(0, Qt.ItemDataRole.UserRole)
            for entry in self.pending_songs:
                if entry.get("id") == entry_id:
                    source_path = entry.get("source_path", "")
                    if source_path and Path(source_path).exists():
                        try:
                            open_file_with_player(source_path, player_path)
                            # Ask if user wants to set as default
                            reply = QMessageBox.question(
                                self.parent,
                                "Set as Default Player?",
                                f"Do you want to set this as your default player?\n\nPlayer: {player_path}",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.Yes
                            )
                            if reply == QMessageBox.StandardButton.Yes:
                                SettingsManager.default_player = player_path
                                SettingsManager.save_settings()
                        except Exception as e:
                            QMessageBox.warning(self.parent, "Error", f"Cannot play file: {e}")
                    return

    def _set_default_player(self, player_path: str) -> None:
        """Set the specified player as the default player."""
        SettingsManager.default_player = player_path
        SettingsManager.save_settings()
        # Show a brief notification
        QMessageBox.information(
            self.parent,
            "Default Player Set",
            f"Default player has been set successfully.",
            QMessageBox.StandardButton.Ok
        )

    def _on_pending_column_resized(self, logicalIndex: int, oldSize: int, newSize: int) -> None:
        """Save pending column widths when user resizes columns."""
        try:
            if not self.pending_tree:
                return
            widths = [self.pending_tree.columnWidth(i) for i in range(self.pending_tree.columnCount())]
            SettingsManager.pending_column_widths = widths
        except Exception as e:
            print(f"Error saving pending column widths: {e}")

    def _on_pending_right_click(self, position) -> None:
        """Show context menu for pending songs."""
        # Close any existing menu first
        if self._active_menu:
            self._active_menu.close()
            self._active_menu = None
        
        item = self.pending_tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self.parent)
        self._active_menu = menu
        c = getattr(self.parent, "theme_colors", None) or {}
        is_dark = SettingsManager.theme == "dark"
        menu_bg = c.get("bg_primary", "#1e1e1e" if is_dark else "#ffffff")
        menu_text = c.get("text", "#cccccc" if is_dark else "#3b3b3b")
        menu_border = c.get("border", "#454545" if is_dark else "#e5e5e5")
        menu_accent = c.get("button", "#0e639c" if is_dark else "#007acc")
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {menu_bg};
                color: {menu_text};
                border: 1px solid {menu_border};
            }}
            QMenu::item:selected {{
                background-color: {menu_accent};
                color: #ffffff;
            }}
        """)
        
        # Play (with system default)
        action = menu.addAction("▶️ Play")
        action.triggered.connect(lambda: self._on_pending_play_song(item, 0))
        
        # Play With (submenu)
        available_players = get_available_players()
        if available_players or SettingsManager.default_player:
            play_with_menu = menu.addMenu("▶️ Play With")
            
            # Check if default player is in available list
            available_paths = [p[1] for p in available_players]
            has_custom_default = (
                SettingsManager.default_player and 
                SettingsManager.default_player not in available_paths
            )
            
            # Add custom player at top if it's the default and not in list
            if has_custom_default:
                player_name = Path(SettingsManager.default_player).name
                player_submenu = play_with_menu.addMenu(f"✓ {player_name} (Custom)")
                
                # Play action
                action = player_submenu.addAction("▶️ Play")
                action.triggered.connect(
                    lambda checked=False, p=SettingsManager.default_player: 
                    self._pending_play_with_player(item, p)
                )
                
                # Set as default action (already is default)
                action = player_submenu.addAction("⭐ Set as Default")
                action.setEnabled(False)  # Already default
                
                play_with_menu.addSeparator()
            
            for player_name, player_path in available_players:
                # Create submenu for each player with options
                player_submenu = play_with_menu.addMenu(player_name)
                
                # Add checkmark if this is the default player
                if SettingsManager.default_player == player_path:
                    player_submenu.setTitle(f"✓ {player_name}")
                
                # Play action
                action = player_submenu.addAction("▶️ Play")
                action.triggered.connect(lambda checked=False, p=player_path: self._pending_play_with_player(item, p))
                
                # Set as default action
                action = player_submenu.addAction("⭐ Set as Default")
                action.triggered.connect(lambda checked=False, p=player_path: self._set_default_player(p))
            
            play_with_menu.addSeparator()
            action = play_with_menu.addAction("Custom Player...")
            action.triggered.connect(lambda: self._pending_play_with_custom_player(item))
        
        menu.addSeparator()
        
        edit_action = menu.addAction("✏️ Edit")
        edit_action.triggered.connect(lambda: self._load_pending_entry(item))
        
        menu.addSeparator()
        
        remove_action = menu.addAction("🗑️ Remove")
        remove_action.triggered.connect(lambda: self._remove_pending_by_item(item))
        
        menu.exec(QCursor.pos())

    def _load_pending_entry(self, item: QTreeWidgetItem) -> None:
        """Load a pending entry into the editor."""
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        for entry in self.pending_songs:
            if entry.get("id") == entry_id:
                self.current_edit_id = entry_id
                self._set_source_label(entry.get("source_path", ""))
                self._fill_json_fields(entry.get("json", {}))
                self._fill_id3_fields(entry.get("id3", {}))
                self._current_cover_bytes = entry.get("cover")
                self._apply_cover_preview(self._current_cover_bytes)
                self._update_action_button_styles()
                return

    def _remove_pending_by_item(self, item: QTreeWidgetItem) -> None:
        """Remove a pending entry by item reference."""
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        self.pending_songs = [e for e in self.pending_songs if e.get("id") != entry_id]
        if self.current_edit_id == entry_id:
            self.current_edit_id = None
            self._update_action_button_styles()
        self.refresh_pending_tree()

    def remove_selected_pending(self) -> None:
        if not self.pending_tree:
            return
        current = self.pending_tree.currentItem()
        if not current:
            return
        entry_id = current.data(0, Qt.ItemDataRole.UserRole)
        self.pending_songs = [e for e in self.pending_songs if e.get("id") != entry_id]
        self.current_edit_id = None
        self.refresh_pending_tree()

    def clear_pending_list(self) -> None:
        self.pending_songs = []
        self.current_edit_id = None
        self._update_action_button_styles()
        if self.pending_tree:
            self.pending_tree.clear()

    def reset_editor(self) -> None:
        self._set_source_label("(none)")
        self._original_id3 = {}
        self._preset_applied = False
        self._fill_json_fields({})
        self._fill_id3_fields({})
        self._current_cover_bytes = None
        self._apply_cover_preview(None)
        self.current_edit_id = None
        self._update_action_button_styles()
        
        # Set defaults
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Set Special to 0 by default
        if MetadataFields.SPECIAL in self.json_fields:
            self.json_fields[MetadataFields.SPECIAL].setText("0")
        
        # Set Date to today if not already set or use persistent date
        if MetadataFields.DATE in self.json_fields:
            if self._persistent_date:
                self.json_fields[MetadataFields.DATE].setText(self._persistent_date)
            else:
                self.json_fields[MetadataFields.DATE].setText(today)
        
        # Comment should be None by default
        if MetadataFields.COMMENT in self.json_fields:
            self.json_fields[MetadataFields.COMMENT].setText("None")

    def _update_action_button_styles(self) -> None:
        if not self.add_btn or not self.update_btn:
            return
        active_style = "background-color: #0d47a1; color: white;"
        inactive_style = ""
        if self.current_edit_id is None:
            self.add_btn.setStyleSheet(active_style)
            self.update_btn.setStyleSheet(inactive_style)
        else:
            self.add_btn.setStyleSheet(inactive_style)
            self.update_btn.setStyleSheet(active_style)

    def _auto_increment_track(self) -> None:
        """Auto-increment track and keep disc consistent if they are set."""
        # Keep persistent date
        date_field = self.json_fields.get(MetadataFields.DATE)
        if date_field:
            self._persistent_date = date_field.text().strip()
        
        # Keep persistent disc
        disc_field = self.json_fields.get(MetadataFields.DISC)
        if disc_field:
            disc_val = disc_field.text().strip()
            if disc_val:
                self._persistent_disc = disc_val
        
        # Auto-increment track if disc is set
        track_field = self.json_fields.get(MetadataFields.TRACK)
        if not track_field or not self._persistent_disc:
            return
        
        next_track = self._next_track_number()
        if next_track is not None:
            track_field.setText(str(next_track))

    def _next_track_number(self) -> int | None:
        """Get the next track number based on pending songs with same disc."""
        if not self._persistent_disc:
            return None
        
        tracks = []
        for entry in self.pending_songs:
            disc_val = str(entry.get("json", {}).get(MetadataFields.DISC, "")).strip()
            track_val = str(entry.get("json", {}).get(MetadataFields.TRACK, "")).strip()
            # Only count tracks from the same disc
            if disc_val == self._persistent_disc and track_val.isdigit():
                tracks.append(int(track_val))
        
        if not tracks:
            return None
        return max(tracks) + 1

    def _clear_preset(self) -> None:
        """Clear preset selection and restore original ID3 values."""
        if self.preset_combo:
            self.preset_combo.setCurrentIndex(-1)
        
        # Restore original ID3 values
        if self._original_id3:
            for key in ["Title", "Artist", "Album"]:
                if key in self.id3_fields and key in self._original_id3:
                    field = self.id3_fields[key]
                    if isinstance(field, QLineEdit):
                        field.setText(self._original_id3.get(key, ""))
        
        # Mark preset as not applied and update styling
        self._preset_applied = False
        self._update_id3_field_styling()

    def apply_preset_to_id3(self) -> None:
        if self.preset_combo is None:
            return
        preset_name = self.preset_combo.currentText().strip()
        if not preset_name:
            return
        preset_file = SettingsManager.get_presets_folder() / f"{preset_name}.json"
        if not preset_file.exists():
            QMessageBox.warning(self.parent, "Preset Missing", f"Preset '{preset_name}' not found.")
            return
        try:
            preset_data = json.loads(preset_file.read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.warning(self.parent, "Error", f"Failed to load preset: {e}")
            return

        base = self._collect_json_data()
        album_seed = self.id3_fields.get("Album").text().strip() if self.id3_fields.get("Album") else ""
        base["Album"] = album_seed

        title_rules = preset_data.get("title", [])
        artist_rules = preset_data.get("artist", [])
        album_rules = preset_data.get("album", [])

        # Check if preset has any rules at all
        has_any_rules = bool(title_rules or artist_rules or album_rules)

        base = self._apply_rules_to_field(base, title_rules, MetadataFields.TITLE)
        base = self._apply_rules_to_field(base, artist_rules, MetadataFields.ARTIST)
        base = self._apply_rules_to_field(base, album_rules, "Album")

        # Block signals to prevent textChanged from triggering styling updates during preset application
        if self.id3_fields.get("Title"):
            self.id3_fields["Title"].blockSignals(True)
            self.id3_fields["Title"].setText(str(base.get(MetadataFields.TITLE, "")))
            self.id3_fields["Title"].blockSignals(False)
        if self.id3_fields.get("Artist"):
            self.id3_fields["Artist"].blockSignals(True)
            self.id3_fields["Artist"].setText(str(base.get(MetadataFields.ARTIST, "")))
            self.id3_fields["Artist"].blockSignals(False)
        if self.id3_fields.get("Album"):
            self.id3_fields["Album"].blockSignals(True)
            self.id3_fields["Album"].setText(str(base.get("Album", "")))
            self.id3_fields["Album"].blockSignals(False)
        
        # Only mark preset as applied if it actually has rules
        self._preset_applied = has_any_rules
        self._update_id3_field_styling()

    def _apply_rules_to_field(self, data: dict, rules: list[dict], target_field: str) -> dict:
        result = dict(data)
        if not rules:
            return result

        i = 0
        while i < len(rules):
            rule_data = rules[i]
            logic = rule_data.get("logic", "AND")
            if_field = rule_data.get("if_field", "")
            if_operator = rule_data.get("if_operator", "")
            if_value = rule_data.get("if_value", "")
            then_template = rule_data.get("then_template", "")
            is_first = rule_data.get("is_first", False)

            is_group_marker = (logic in ["AND", "OR"]) and not then_template
            is_first_with_template = is_first and then_template

            if is_first_with_template and self._rule_matches(result, if_field, if_operator, if_value):
                result[target_field] = self._render_template(then_template, result)
                break

            if logic == "OR" and then_template and self._rule_matches(result, if_field, if_operator, if_value):
                result[target_field] = self._render_template(then_template, result)
                break

            if (is_group_marker or (is_first and not then_template)) and self._rule_matches(result, if_field, if_operator, if_value):
                j = i + 1
                result_found = False
                group_field, group_operator, group_value = if_field, if_operator, if_value

                while j < len(rules) and not result_found:
                    next_rule = rules[j]
                    next_logic = next_rule.get("logic", "AND")
                    next_field = next_rule.get("if_field", "")
                    next_operator = next_rule.get("if_operator", "")
                    next_value = next_rule.get("if_value", "")
                    next_template = next_rule.get("then_template", "")
                    next_is_first = next_rule.get("is_first", False)

                    if next_is_first and next_template:
                        break

                    if next_logic == "AND" and not next_template and not next_is_first:
                        if not (next_field == group_field and next_operator == group_operator and next_value == group_value):
                            break
                    elif next_logic == "OR" and not next_template:
                        if not (next_field == group_field and next_operator == group_operator and next_value == group_value):
                            break
                    elif next_is_first and not next_template:
                        break
                    elif next_logic == "AND" and next_template:
                        if self._rule_matches(result, next_field, next_operator, next_value):
                            result[target_field] = self._render_template(next_template, result)
                            result_found = True
                            break
                    j += 1

                if result_found:
                    break

            i += 1

        return result

    def _rule_matches(self, json_data: dict, field: str, operator: str, condition: str) -> bool:
        field_value = str(json_data.get(field, "")).lower()
        condition_lower = str(condition).lower()

        if operator == "is":
            return field_value == condition_lower
        if operator == "contains":
            return condition_lower in field_value
        if operator == "starts with":
            return field_value.startswith(condition_lower)
        if operator == "ends with":
            return field_value.endswith(condition_lower)
        if operator == "is empty":
            return field_value == ""
        if operator == "is not empty":
            return field_value != ""
        if operator == "is latest version":
            return json_data.get("_is_latest", False)
        if operator == "is not latest version":
            return not json_data.get("_is_latest", False)
        return False

    def _render_template(self, template: str, data: dict) -> str:
        def repl(match):
            key = match.group(1)
            val = data.get(key, "")
            if isinstance(val, (int, float)):
                if isinstance(val, float) and val.is_integer():
                    return str(int(val))
                return str(val)
            return str(val)

        return re.sub(r"\{([^}]+)\}", repl, template or "")

    def save_all_pending(self) -> None:
        if not self.pending_songs:
            QMessageBox.information(self.parent, "No Items", "No pending songs to save.")
            return

        out_dir = QFileDialog.getExistingDirectory(self.parent, "Select Output Folder")
        if not out_dir:
            return

        errors = []
        for entry in self.pending_songs:
            source_path = entry.get("source_path", "")
            filename = entry.get("filename", "")
            if not source_path or not filename:
                continue

            output_path = str(Path(out_dir) / filename)
            try:
                remux_song(source_path, output_path)
                if not Path(output_path).exists():
                    errors.append(f"Remux failed: {filename}")
                    continue

                json_data = dict(entry.get("json", {}))
                id3_data = dict(entry.get("id3", {}))
                cover = entry.get("cover")

                # Apply album artist and compute xxHash
                id3_data["AlbumArtist"] = ALBUM_ARTIST
                json_data["xxHash"] = get_audio_hash(output_path) or ""

                self._write_id3_v24(output_path, json_data, id3_data, cover)
            except Exception as e:
                errors.append(f"{filename}: {e}")

        if errors:
            QMessageBox.warning(self.parent, "Save Completed with Errors", "\n".join(errors))
        else:
            QMessageBox.information(self.parent, "Saved", f"Saved {len(self.pending_songs)} song(s).")
        self.clear_pending_list()

    def _write_id3_v24(self, path: str, json_data: dict, id3_data: dict, cover_bytes: bytes | None) -> None:
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()

        def set_or_clear(frame_id: str, frame_obj):
            if frame_obj is None:
                tags.delall(frame_id)
            else:
                tags.setall(frame_id, [frame_obj])

        title = id3_data.get("Title") or json_data.get(MetadataFields.TITLE, "")
        artist = id3_data.get("Artist") or json_data.get(MetadataFields.ARTIST, "")
        album = id3_data.get("Album", "")
        track = id3_data.get("Track") or json_data.get(MetadataFields.TRACK, "")
        disc = id3_data.get("Discnumber") or json_data.get(MetadataFields.DISC, "")
        date = id3_data.get("Date") or json_data.get(MetadataFields.DATE, "")
        
        # Extract year from date (yyyy-mm-dd -> yyyy) for TDRC tag
        year = ""
        if date:
            date_str = str(date).strip()
            if len(date_str) >= 4:
                year = date_str[:4]
            else:
                year = date_str

        set_or_clear("TIT2", TIT2(encoding=3, text=str(title)) if title else None)
        set_or_clear("TPE1", TPE1(encoding=3, text=str(artist)) if artist else None)
        set_or_clear("TALB", TALB(encoding=3, text=str(album)) if album else None)
        set_or_clear("TRCK", TRCK(encoding=3, text=str(track)) if track else None)
        set_or_clear("TPOS", TPOS(encoding=3, text=str(disc)) if disc else None)
        set_or_clear("TDRC", TDRC(encoding=3, text=year) if year else None)
        set_or_clear("TPE2", TPE2(encoding=3, text=ALBUM_ARTIST))

        # Format COMM:eng with date and optional comment
        tags.delall("COMM::eng")
        comment_text = json_data.get(MetadataFields.COMMENT)
        date_str = json_data.get(MetadataFields.DATE, datetime.now().strftime("%Y-%m-%d"))
        # If comment is None or "None" string, just use date
        if comment_text is None or str(comment_text).strip().lower() == "none":
            comm_text = date_str
        else:
            comm_text = f"{date_str} //{comment_text}"
        tags.add(COMM(encoding=3, lang="eng", desc="", text=comm_text))
        
        # Keep the JSON in ved language for compatibility
        tags.delall("COMM::ved")
        json_str = json.dumps(json_data, ensure_ascii=False, separators=(",", ":"))
        tags.add(COMM(encoding=3, lang="ved", desc="", text=json_str))

        if cover_bytes:
            tags.delall("APIC")
            tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="", data=cover_bytes))

        tags.save(path, v2_version=4)    
    def update_theme(self, theme_colors: dict, is_dark: bool):
        """Update song editor components with current theme colors."""
        self._theme_colors = theme_colors
        self._is_dark = is_dark
        c = theme_colors
        
        # Update textboxes (metadata fields) with proper light theme colors
        field_bg = c['bg_primary']
        field_border = c['border']
        field_text = c['text']
        field_focus = c['button']
        
        text_style = f"""
            QLineEdit {{
                background-color: {field_bg};
                color: {field_text};
                border: 1px solid {field_border};
                padding: 4px;
                border-radius: 3px;
            }}
            QLineEdit:focus {{ border: 2px solid {field_focus}; }}
        """
        
        # Update JSON fields
        for field_widget in self.json_fields.values():
            if hasattr(field_widget, 'setStyleSheet'):
                field_widget.setStyleSheet(text_style)
        
        # Update ID3 fields
        for field_widget in self.id3_fields.values():
            if hasattr(field_widget, 'setStyleSheet'):
                field_widget.setStyleSheet(text_style)
        
        # Update pending tree
        if hasattr(self, 'pending_tree') and self.pending_tree:
            hover_color = '#2a2d2e' if is_dark else '#f0f0f0'
            header_bg = '#252526' if is_dark else '#f3f3f3'
            border_light = '#454545' if is_dark else '#d4d4d4'
            
            self.pending_tree.setStyleSheet(f"""
                QTreeWidget {{
                    background-color: {c['bg_primary']};
                    color: {c['text']};
                    border: 1px solid {c['border']};
                    gridline-color: {c['border']};
                }}
                QTreeWidget::item {{
                    border-right: 1px solid {c['border']};
                    padding: 2px;
                }}
                QTreeWidget::item:selected {{ background-color: {c['button']}; color: #ffffff; }}
                QHeaderView::section {{
                    background-color: {header_bg};
                    color: {c['text']};
                    padding: 4px;
                    border: none;
                    border-right: 1px solid {border_light};
                    border-bottom: 1px solid {border_light};
                }}
            """)
        
        # Update preset combo in song edit
        if hasattr(self, 'preset_combo') and self.preset_combo:
            dropdown_bg = '#2d2d30' if is_dark else '#ffffff'
            self.preset_combo.setStyleSheet(f"""
                QComboBox {{
                    background-color: {c['bg_primary']};
                    color: {c['text']};
                    border: 1px solid {c['border']};
                    border-radius: 4px;
                    padding: 4px;
                    padding-right: 20px;
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 20px;
                    background-color: transparent;
                }}
                QComboBox::down-arrow {{
                    image: none;  /* We draw the arrow manually in paintEvent */
                }}
                QComboBox QAbstractItemView {{
                    background-color: {dropdown_bg};
                    color: {c['text']};
                    selection-background-color: {c['button']};
                    selection-color: #ffffff;
                }}
            """)
        
        # Update save all button
        if hasattr(self, 'save_all_btn'):
            button_hover = c.get('button_hover', c['button'])
            for btn in [self.save_all_btn] if hasattr(self, 'save_all_btn') else []:
                if btn:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {c['button']};
                            color: white;
                            border: none;
                            border-radius: 3px;
                            padding: 6px;
                        }}
                        QPushButton:hover {{
                            background-color: {button_hover};
                        }}
                    """)

        # Re-apply ID3 styling to reflect theme and original/modified state
        self._update_id3_field_styling()
"""Song editor panel UI and actions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
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
    QMessageBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TRCK, TPOS, TDRC, TPE2, APIC, COMM

from df_metadata_customizer.core.metadata import MetadataFields
from df_metadata_customizer.core.settings_manager import SettingsManager
from df_metadata_customizer.core.song_utils import extract_json_from_song, get_id3_tags, get_cover_art
from df_metadata_customizer.core.preset_service import PresetService
from df_metadata_customizer.ui.rule_widgets import NoScrollComboBox

from remuxer import remux_song
from hash_mutagen import get_audio_hash


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

        self.pending_tree: QTreeWidget | None = None
        self.source_label: QLabel | None = None
        self.preset_combo: NoScrollComboBox | None = None
        self.cover_label: QLabel | None = None

        self.json_fields: dict[str, QLineEdit] = {}
        self.id3_fields: dict[str, QLineEdit] = {}

    def create_song_edit_tab(self):
        """Create song metadata editor for adding new songs."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("➕ Add New Songs")
        title.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # Top: Editor
        editor_panel = QFrame()
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

        pick_btn = QPushButton("Choose Source")
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

        preset_row = QHBoxLayout()
        preset_label = QLabel("Preset:")
        preset_row.addWidget(preset_label)
        self.preset_combo = NoScrollComboBox()
        self._load_presets()
        preset_row.addWidget(self.preset_combo, 1)
        preset_apply = QPushButton("Apply Preset to ID3")
        preset_apply.clicked.connect(self.apply_preset_to_id3)
        preset_row.addWidget(preset_apply)
        id3_form.addRow(preset_row)
        scroll_layout.addWidget(id3_group)

        # Cover
        cover_group = QGroupBox("Cover Art")
        cover_layout = QVBoxLayout(cover_group)
        self.cover_label = QLabel("No cover")
        self.cover_label.setFixedSize(160, 160)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("border: 1px solid #3d3d3d;")
        cover_layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignLeft)

        cover_btns = QHBoxLayout()
        load_cover_btn = QPushButton("Load Cover")
        load_cover_btn.clicked.connect(self.load_cover_from_file)
        cover_btns.addWidget(load_cover_btn)

        from_source_btn = QPushButton("Use Source Cover")
        from_source_btn.clicked.connect(self.load_cover_from_source)
        cover_btns.addWidget(from_source_btn)

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
        add_btn = QPushButton("Add to List")
        add_btn.setStyleSheet("background-color: #0d47a1; color: white;")
        add_btn.clicked.connect(self.add_or_update_pending)
        editor_btns.addWidget(add_btn)

        update_btn = QPushButton("Update Selected")
        update_btn.clicked.connect(self.update_selected_pending)
        editor_btns.addWidget(update_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset_editor)
        editor_btns.addWidget(reset_btn)
        editor_btns.addStretch()
        editor_layout.addLayout(editor_btns)

        splitter.addWidget(editor_panel)

        # Bottom: Pending list
        pending_panel = QFrame()
        pending_layout = QVBoxLayout(pending_panel)
        pending_layout.setContentsMargins(0, 0, 0, 0)
        pending_layout.setSpacing(6)

        pending_label = QLabel("Pending New Songs")
        pending_label.setStyleSheet("font-weight: bold;")
        pending_layout.addWidget(pending_label)

        self.pending_tree = QTreeWidget()
        self.pending_tree.setColumnCount(5)
        self.pending_tree.setHeaderLabels(["Filename", "Title", "Artist", "Track", "Date"])
        self.pending_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pending_tree.itemClicked.connect(self._on_pending_selected)
        self.pending_tree.setStyleSheet("""
            QTreeWidget { background-color: #252525; border: 1px solid #3d3d3d; }
            QTreeWidget::item:selected { background-color: #0d47a1; }
        """)
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
        fields = {
            MetadataFields.TITLE: "Title",
            MetadataFields.ARTIST: "Artist",
            MetadataFields.COVER_ARTIST: "Cover Artist",
            MetadataFields.DATE: "Date",
            MetadataFields.VERSION: "Version",
            MetadataFields.DISC: "Disc",
            MetadataFields.TRACK: "Track",
            MetadataFields.COMMENT: "Comment",
            MetadataFields.SPECIAL: "Special",
        }
        out: dict[str, QLineEdit] = {}
        for key, label in fields.items():
            edit = QLineEdit()
            form.addRow(f"{label}:", edit)
            out[key] = edit
        return out

    def _create_id3_fields(self, form: QFormLayout) -> dict[str, QLineEdit]:
        fields = {
            "Title": "Title",
            "Artist": "Artist",
            "Album": "Album",
            "Track": "Track",
            "Discnumber": "Disc",
            "Date": "Date",
            "AlbumArtist": "Album Artist",
        }
        out: dict[str, QLineEdit] = {}
        for key, label in fields.items():
            edit = QLineEdit()
            if key == "AlbumArtist":
                edit.setText(ALBUM_ARTIST)
                edit.setReadOnly(True)
            form.addRow(f"{label}:", edit)
            out[key] = edit
        return out

    def _load_presets(self) -> None:
        if not self.preset_combo:
            return
        self.preset_combo.clear()
        try:
            presets = self.preset_service.list_presets()
            if not presets:
                presets = ["Default", "TuruuMGL", "mm2wood"]
            self.preset_combo.addItems(sorted(presets))
        except Exception as e:
            print(f"Error loading presets: {e}")
            self.preset_combo.addItems(["Default", "TuruuMGL", "mm2wood"])

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
        file_path = file_data.get("path", "")
        if not file_path:
            return
        self.load_from_path(file_path, file_data.get("raw_json"))

    def load_from_path(self, file_path: str, json_data: dict | None = None) -> None:
        jsond = json_data or extract_json_from_song(file_path) or {}
        id3 = get_id3_tags(file_path)
        cover = get_cover_art(file_path)

        self._current_cover_bytes = cover
        self._apply_cover_preview(cover)

        self._set_source_label(file_path)
        self._fill_json_fields(jsond)
        self._fill_id3_fields(id3)
        self.current_edit_id = None

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
        for key, field in self.json_fields.items():
            field.setText(str(jsond.get(key, "")))

    def _fill_id3_fields(self, id3: dict) -> None:
        for key, field in self.id3_fields.items():
            if key == "AlbumArtist":
                field.setText(ALBUM_ARTIST)
                continue
            field.setText(str(id3.get(key, "")))

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
            data[key] = field.text().strip()
        return data

    def _collect_id3_data(self) -> dict:
        data = {}
        for key, field in self.id3_fields.items():
            if key == "AlbumArtist":
                data[key] = ALBUM_ARTIST
            else:
                data[key] = field.text().strip()
        return data

    def _new_entry_id(self) -> int:
        val = self._next_id
        self._next_id += 1
        return val

    def add_or_update_pending(self) -> None:
        source_path = self._current_source_path()
        if not source_path:
            QMessageBox.warning(self.parent, "Missing Source", "Please choose a source MP3 file.")
            return

        json_data = self._collect_json_data()
        id3_data = self._collect_id3_data()

        entry = {
            "id": self._new_entry_id() if self.current_edit_id is None else self.current_edit_id,
            "source_path": source_path,
            "filename": Path(source_path).name,
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
            item = QTreeWidgetItem([
                entry.get("filename", ""),
                json_data.get(MetadataFields.TITLE, ""),
                json_data.get(MetadataFields.ARTIST, ""),
                json_data.get(MetadataFields.TRACK, ""),
                json_data.get(MetadataFields.DATE, ""),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, entry.get("id"))
            self.pending_tree.addTopLevelItem(item)

    def _on_pending_selected(self, item: QTreeWidgetItem) -> None:
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        for entry in self.pending_songs:
            if entry.get("id") == entry_id:
                self.current_edit_id = entry_id
                self._set_source_label(entry.get("source_path", ""))
                self._fill_json_fields(entry.get("json", {}))
                self._fill_id3_fields(entry.get("id3", {}))
                self._current_cover_bytes = entry.get("cover")
                self._apply_cover_preview(self._current_cover_bytes)
                return

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
        if self.pending_tree:
            self.pending_tree.clear()

    def reset_editor(self) -> None:
        self._set_source_label("(none)")
        self._fill_json_fields({})
        self._fill_id3_fields({})
        self._current_cover_bytes = None
        self._apply_cover_preview(None)
        self.current_edit_id = None

    def _auto_increment_track(self) -> None:
        track_field = self.json_fields.get(MetadataFields.TRACK)
        if not track_field:
            return
        next_track = self._next_track_number()
        if next_track is not None:
            track_field.setText(str(next_track))

    def _next_track_number(self) -> int | None:
        tracks = []
        for entry in self.pending_songs:
            val = str(entry.get("json", {}).get(MetadataFields.TRACK, "")).strip()
            if val.isdigit():
                tracks.append(int(val))
        if not tracks:
            return None
        return max(tracks) + 1

    def apply_preset_to_id3(self) -> None:
        if not self.preset_combo:
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

        base = self._apply_rules_to_field(base, title_rules, MetadataFields.TITLE)
        base = self._apply_rules_to_field(base, artist_rules, MetadataFields.ARTIST)
        base = self._apply_rules_to_field(base, album_rules, "Album")

        if self.id3_fields.get("Title"):
            self.id3_fields["Title"].setText(str(base.get(MetadataFields.TITLE, "")))
        if self.id3_fields.get("Artist"):
            self.id3_fields["Artist"].setText(str(base.get(MetadataFields.ARTIST, "")))
        if self.id3_fields.get("Album"):
            self.id3_fields["Album"].setText(str(base.get("Album", "")))

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

        set_or_clear("TIT2", TIT2(encoding=3, text=str(title)) if title else None)
        set_or_clear("TPE1", TPE1(encoding=3, text=str(artist)) if artist else None)
        set_or_clear("TALB", TALB(encoding=3, text=str(album)) if album else None)
        set_or_clear("TRCK", TRCK(encoding=3, text=str(track)) if track else None)
        set_or_clear("TPOS", TPOS(encoding=3, text=str(disc)) if disc else None)
        set_or_clear("TDRC", TDRC(encoding=3, text=str(date)) if date else None)
        set_or_clear("TPE2", TPE2(encoding=3, text=ALBUM_ARTIST))

        tags.delall("COMM::ved")
        json_str = json.dumps(json_data, ensure_ascii=False, separators=(",", ":"))
        tags.add(COMM(encoding=3, lang="ved", desc="", text=json_str))

        if cover_bytes:
            tags.delall("APIC")
            tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="", data=cover_bytes))

        tags.save(path, v2_version=4)

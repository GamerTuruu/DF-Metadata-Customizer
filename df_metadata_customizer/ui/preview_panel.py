"""Preview panel logic for rule application and UI updates."""

import json
import re
from pathlib import Path

from PySide6.QtCore import Qt

from df_metadata_customizer.core.metadata import MetadataFields
from df_metadata_customizer.core.song_utils import get_id3_tags
from df_metadata_customizer.core.settings_manager import SettingsManager


class PreviewPanelManager:
    """Manage preview panel updates based on selected file and rules."""

    def __init__(self, parent):
        self.parent = parent

    def update_preview_info(self):
        """Update preview info based on selected file."""
        if self.parent.current_selected_file is None or self.parent.current_selected_file >= len(self.parent.song_files):
            return

        file_data = self.parent.song_files[self.parent.current_selected_file]

        # Display raw JSON - format with integer numbers
        self.parent.json_editor.blockSignals(True)
        raw_json = file_data.get('raw_json', {})
        json_str = json.dumps(raw_json, indent=2, ensure_ascii=False)
        json_str = re.sub(r'(\d)\.0([,\n])', r'\1\2', json_str)
        self.parent.json_editor.setText(json_str)
        self.parent.json_editor.blockSignals(False)
        self.parent.save_json_btn.setEnabled(False)

        # Update output preview labels - show what rules will produce
        id3_data = get_id3_tags(file_data.get("path", ""))

        def get_tag_value(field_key, fallback="-"):
            value = file_data.get(field_key, "")
            if value not in ("", None):
                return value
            raw_value = raw_json.get(field_key, "")
            if raw_value not in ("", None):
                return raw_value
            return id3_data.get(field_key, fallback)

        title = get_tag_value(MetadataFields.TITLE)
        artist = get_tag_value(MetadataFields.ARTIST)
        album = get_tag_value("Album")
        disc = get_tag_value(MetadataFields.DISC)
        track = get_tag_value(MetadataFields.TRACK)
        date = get_tag_value(MetadataFields.DATE)

        # Apply rules to get preview of what ID3 tags will be
        preview_data = file_data.copy()
        rule_applied = {
            MetadataFields.TITLE: False,
            MetadataFields.ARTIST: False,
            "Album": False,
        }
        tab_targets = {
            "title": MetadataFields.TITLE,
            "artist": MetadataFields.ARTIST,
            "album": "Album",
        }
        for tab_name in ["title", "artist", "album"]:
            rules = self.parent.rules_panel_manager.collect_rules_for_tab(tab_name)
            target_field = tab_targets.get(tab_name, "")

            i = 0
            while i < len(rules):
                rule_data = rules[i]
                try:
                    logic = rule_data.get("logic", "AND")
                    if_field = rule_data.get("if_field", "")
                    if_operator = rule_data.get("if_operator", "")
                    if_value = rule_data.get("if_value", "")
                    then_template = rule_data.get("then_template", "")
                    is_first = rule_data.get("is_first", False)

                    is_group_marker = (logic in ["AND", "OR"]) and not then_template
                    is_first_with_template = is_first and then_template

                    if is_first_with_template and self.parent.rule_applier.rule_matches(preview_data, if_field, if_operator, if_value):
                        preview_data[target_field] = self.parent.rule_applier.render_template(then_template, preview_data)
                        rule_applied[target_field] = True
                        break

                    if logic == "OR" and then_template and self.parent.rule_applier.rule_matches(preview_data, if_field, if_operator, if_value):
                        preview_data[target_field] = self.parent.rule_applier.render_template(then_template, preview_data)
                        rule_applied[target_field] = True
                        break

                    if (is_group_marker or (is_first and not then_template)) and self.parent.rule_applier.rule_matches(preview_data, if_field, if_operator, if_value):
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
                                if self.parent.rule_applier.rule_matches(preview_data, next_field, next_operator, next_value):
                                    preview_data[target_field] = self.parent.rule_applier.render_template(next_template, preview_data)
                                    rule_applied[target_field] = True
                                    result_found = True
                                    break

                            j += 1

                        if result_found:
                            break

                except Exception:
                    pass
                i += 1

        preview_title = preview_data.get(MetadataFields.TITLE, title)
        preview_artist = preview_data.get(MetadataFields.ARTIST, artist)
        preview_album = preview_data.get("Album", album)

        if not rule_applied.get(MetadataFields.TITLE, False):
            preview_title = id3_data.get("Title", preview_title)
        if not rule_applied.get(MetadataFields.ARTIST, False):
            preview_artist = id3_data.get("Artist", preview_artist)
        if not rule_applied.get("Album", False):
            preview_album = id3_data.get("Album", preview_album)

        song_key = (title, artist, file_data.get(MetadataFields.COVER_ARTIST, ""))
        versions = []
        for f in self.parent.song_files:
            f_key = (
                f.get(MetadataFields.TITLE, ""),
                f.get(MetadataFields.ARTIST, ""),
                f.get(MetadataFields.COVER_ARTIST, ""),
            )
            if f_key == song_key:
                ver = f.get(MetadataFields.VERSION, "")
                if ver and ver not in versions:
                    versions.append(str(ver))
        versions.sort()

        def fmt_num(val):
            if val == "-":
                return "-"
            try:
                num = float(val)
                return str(int(num)) if num == int(num) else str(num)
            except Exception:
                return str(val)

        c = getattr(self.parent, "theme_colors", None) or {}
        is_dark = SettingsManager.theme == "dark"
        preview_bg = "#2d2d30" if is_dark else "#f3f3f3"
        preview_border = "#454545" if is_dark else "#d4d4d4"
        base_text = c.get("text", "#cccccc" if is_dark else "#3b3b3b")
        dim_text = "#666666" if is_dark else "#777777"

        preview_box_style = f"""
            QLabel {{
                background-color: {preview_bg};
                border: 1px solid {preview_border};
                border-radius: 4px;
                padding: 4px 6px;
                min-height: 20px;
            }}
        """

        title_color = base_text if rule_applied.get(MetadataFields.TITLE, False) else dim_text
        artist_color = base_text if rule_applied.get(MetadataFields.ARTIST, False) else dim_text
        album_color = base_text if rule_applied.get("Album", False) else dim_text

        title_style = "font-style: italic;" if not rule_applied.get(MetadataFields.TITLE, False) else ""
        artist_style = "font-style: italic;" if not rule_applied.get(MetadataFields.ARTIST, False) else ""
        album_style = "font-style: italic;" if not rule_applied.get("Album", False) else ""

        self.parent.preview_title_label.setText(preview_title)
        self.parent.preview_title_label.setStyleSheet(preview_box_style + f"\n            QLabel {{ color: {title_color}; {title_style}}}")
        self.parent.preview_artist_label.setText(preview_artist)
        self.parent.preview_artist_label.setStyleSheet(preview_box_style + f"\n            QLabel {{ color: {artist_color}; {artist_style}}}")
        self.parent.preview_album_label.setText(preview_album)
        self.parent.preview_album_label.setStyleSheet(preview_box_style + f"\n            QLabel {{ color: {album_color}; {album_style}}}")
        self.parent.preview_disc_label.setText(fmt_num(disc))
        self.parent.preview_track_label.setText(fmt_num(track))
        self.parent.preview_date_label.setText(date)

        current_version = str(file_data.get(MetadataFields.VERSION, "-"))
        normalized_current = fmt_num(current_version)
        versions_list = []
        for ver in versions:
            ver_display = fmt_num(ver)
            if normalized_current != "-" and ver_display == normalized_current:
                versions_list.append(
                    f"<span style='color: #4CAF50; font-weight: bold;'>{ver_display}</span>"
                )
            else:
                versions_list.append(ver_display)
        versions_display = ", ".join(versions_list) if versions_list else "-"
        self.parent.preview_version_label.setText(versions_display)
        self.parent.preview_version_label.setTextFormat(Qt.TextFormat.RichText)

        filename = file_data.get('path', '')
        self.parent.filename_preview.blockSignals(True)
        if filename:
            self.parent.original_filename = str(Path(filename).name)
            self.parent.filename_preview.setText(self.parent.original_filename)
        else:
            self.parent.original_filename = ""
            self.parent.filename_preview.setText("")
        self.parent.filename_preview.blockSignals(False)
        self.parent.save_filename_btn.setEnabled(False)

        self.parent.cover_manager.load_cover_image(file_data)
        self.parent.update_selection_info()
    
    def update_theme(self, theme_colors: dict, is_dark: bool):
        """Update preview labels with current theme colors."""
        c = theme_colors
        
        # Create preview box style based on theme colors
        preview_bg = '#2d2d30' if is_dark else '#f3f3f3'
        preview_border = '#454545' if is_dark else '#d4d4d4'
        preview_text = '#cccccc' if is_dark else '#3b3b3b'
        
        preview_box_style = f"""
            QLabel {{
                background-color: {preview_bg};
                border: 1px solid {preview_border};
                border-radius: 4px;
                padding: 4px 6px;
                min-height: 20px;
                color: {preview_text};
            }}
        """
        
        # Update all preview labels
        for label_name in ['preview_title_label', 'preview_artist_label', 'preview_album_label', 
                          'preview_disc_label', 'preview_track_label', 'preview_date_label', 
                          'preview_version_label']:
            if hasattr(self.parent, label_name):
                label = getattr(self.parent, label_name)
                if label:
                    label.setStyleSheet(preview_box_style)
        
        # Update filename preview
        if hasattr(self.parent, 'filename_preview') and self.parent.filename_preview:
            self.parent.filename_preview.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {c['bg_primary']};
                    color: {c['text']};
                    border: 1px solid {c['border']};
                    border-radius: 4px;
                    padding: 4px 8px;
                }}
                QLineEdit:focus {{ border: 2px solid {c['button']}; }}
            """)

"""Rules panel UI and rule builder logic."""

import logging
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton,
    QLabel, QTextEdit, QLineEdit, QTabWidget, QApplication
)
from PyQt6.QtCore import Qt

from df_metadata_customizer.core import SettingsManager
from df_metadata_customizer.ui.rule_widgets import RuleRow

logger = logging.getLogger(__name__)


class RulesPanelManager:
    """Manage the Rules + Presets tab and rule builder operations."""

    def __init__(self, parent, preset_manager):
        self.parent = parent
        self.preset_manager = preset_manager

    def create_rules_tab(self):
        """Create rules and presets tab with rule builder."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Preset controls at the top
        preset_frame, self.parent.preset_combo = self.preset_manager.create_preset_controls()
        layout.addWidget(preset_frame, 0, Qt.AlignmentFlag.AlignTop)

        # Rule Tabs for Title/Artist/Album
        rule_tabs = QTabWidget()
        rule_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3d3d3d;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border: 1px solid #3d3d3d;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #0d47a1;
                border-color: #0d47a1;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3d3d3d;
            }
        """)

        # Create tabs for Title, Artist, Album
        for tab_name in ["Title", "Artist", "Album"]:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setContentsMargins(8, 4, 8, 4)
            tab_layout.setSpacing(4)

            # Header with label and add button
            header = QFrame()
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(0, 0, 0, 0)

            label = QLabel(f"{tab_name} Rules")
            label.setStyleSheet("font-weight: bold; font-size: 12pt;")
            header_layout.addWidget(label)

            header_layout.addStretch()

            add_btn = QPushButton("+ Add Rule")
            add_btn.setFixedWidth(100)
            add_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d47a1;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
            """)
            add_btn.clicked.connect(lambda checked, t=tab_name.lower(): self.add_rule_to_tab(t))
            header_layout.addWidget(add_btn)

            tab_layout.addWidget(header)

            # Scrollable area for rules
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("""
                QScrollArea {
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    background-color: #1e1e1e;
                }
            """)

            # Container for rule rows
            rule_container = QWidget()
            rule_layout = QVBoxLayout(rule_container)
            rule_layout.setContentsMargins(4, 4, 4, 4)
            rule_layout.setSpacing(4)
            rule_layout.addStretch()

            scroll.setWidget(rule_container)
            scroll.setMinimumHeight(150)
            scroll.setMaximumHeight(300)
            tab_layout.addWidget(scroll)

            rule_tabs.addTab(tab_widget, tab_name)
            self.parent.rule_containers[tab_name.lower()] = rule_container

        layout.addWidget(rule_tabs, 1)  # Stretch to fill

        # JSON Editor section with save button and cover image
        json_header = QHBoxLayout()
        json_header.addWidget(QLabel("Raw JSON:"))
        self.parent.save_json_btn = QPushButton("Save JSON")
        self.parent.save_json_btn.setEnabled(False)
        self.parent.save_json_btn.setFixedSize(100, 28)
        self.parent.save_json_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: #aaaaaa;
                border: none;
                border-radius: 3px;
                padding: 4px;
            }
            QPushButton:enabled {
                background-color: #0d47a1;
                color: white;
            }
            QPushButton:enabled:hover {
                background-color: #1565c0;
            }
        """)
        self.parent.save_json_btn.clicked.connect(self.parent.save_json_changes)
        json_header.addStretch()
        json_header.addWidget(self.parent.save_json_btn)
        layout.addLayout(json_header)

        # JSON + Cover row
        json_cover_row = QHBoxLayout()
        json_cover_row.setSpacing(6)

        self.parent.json_editor = QTextEdit()
        self.parent.json_editor.setMinimumHeight(180)
        json_font_size = 10 * SettingsManager.ui_scale
        self.parent.json_editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
                font-family: 'Courier New', monospace;
                font-size: {json_font_size}pt;
            }}
        """)
        self.parent.json_editor.textChanged.connect(self.parent.on_json_changed)
        json_cover_row.addWidget(self.parent.json_editor, 1)

        # Cover image with hover button
        cover_container = QFrame()
        cover_container.setFixedSize(180, 180)
        cover_container.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)
        cover_layout = QVBoxLayout(cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)

        self.parent.cover_display = QLabel()
        self.parent.cover_display.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
            }
        """)
        self.parent.cover_display.setScaledContents(True)
        self.parent.cover_display.setText("No cover")
        self.parent.cover_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_layout.addWidget(self.parent.cover_display)

        # Change cover button (overlay on top, hidden by default)
        self.parent.change_cover_btn = QPushButton("Change Cover")
        self.parent.change_cover_btn.setParent(cover_container)
        self.parent.change_cover_btn.setFixedSize(120, 32)
        self.parent.change_cover_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(13, 71, 161, 0.9);
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)
        self.parent.change_cover_btn.hide()
        if hasattr(self.parent, 'cover_manager'):
            self.parent.change_cover_btn.clicked.connect(self.parent.cover_manager.change_cover_image)
        else:
            self.parent.change_cover_btn.clicked.connect(self.parent.change_cover_image)

        def center_button():
            btn_width = self.parent.change_cover_btn.width()
            btn_height = self.parent.change_cover_btn.height()
            container_width = cover_container.width()
            container_height = cover_container.height()
            x = (container_width - btn_width) // 2
            y = (container_height - btn_height) // 2
            self.parent.change_cover_btn.setGeometry(x, y, btn_width, btn_height)

        self.parent.change_cover_btn.showEvent = lambda event: center_button()

        cover_container.enterEvent = lambda event: self.parent.change_cover_btn.show()
        cover_container.leaveEvent = lambda event: self.parent.change_cover_btn.hide()

        json_cover_row.addWidget(cover_container, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(json_cover_row)

        # Output preview with labels outside boxes
        layout.addWidget(QLabel("Output Preview:"))

        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(4)

        preview_box_style = """
            QLabel {
                background-color: #1f1f1f;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px 6px;
                min-height: 20px;
            }
        """

        label_width = 70

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_label = QLabel("Title:")
        title_label.setFixedWidth(label_width)
        title_row.addWidget(title_label, 0)
        self.parent.preview_title_label = QLabel("-")
        self.parent.preview_title_label.setStyleSheet(preview_box_style + "color: #9cdcfe;")
        title_row.addWidget(self.parent.preview_title_label, 1)
        preview_layout.addLayout(title_row)

        artist_row = QHBoxLayout()
        artist_row.setContentsMargins(0, 0, 0, 0)
        artist_row.setSpacing(8)
        artist_label = QLabel("Artist:")
        artist_label.setFixedWidth(label_width)
        artist_row.addWidget(artist_label, 0)
        self.parent.preview_artist_label = QLabel("-")
        self.parent.preview_artist_label.setStyleSheet(preview_box_style + "color: #c586c0;")
        artist_row.addWidget(self.parent.preview_artist_label, 1)
        preview_layout.addLayout(artist_row)

        album_row = QHBoxLayout()
        album_row.setContentsMargins(0, 0, 0, 0)
        album_row.setSpacing(8)
        album_label = QLabel("Album:")
        album_label.setFixedWidth(label_width)
        album_row.addWidget(album_label, 0)
        self.parent.preview_album_label = QLabel("-")
        self.parent.preview_album_label.setStyleSheet(preview_box_style + "color: #4ec9b0;")
        album_row.addWidget(self.parent.preview_album_label, 1)
        preview_layout.addLayout(album_row)

        song_container = QHBoxLayout()
        song_container.setContentsMargins(0, 0, 0, 0)
        song_container.setSpacing(4)

        song_box_row = QVBoxLayout()
        song_box_row.setContentsMargins(0, 0, 0, 0)
        song_box_row.setSpacing(0)
        song_label = QLabel("Song")
        song_label.setFixedWidth(label_width)
        song_label2 = QLabel("details:")
        song_label2.setFixedWidth(label_width)
        song_box_row.addWidget(song_label, 0)
        song_box_row.addWidget(song_label2, 1)
        song_container.addLayout(song_box_row, 0)

        disc_box_row = QVBoxLayout()
        disc_box_row.setContentsMargins(0, 0, 0, 0)
        disc_box_row.setSpacing(2)
        disc_box_row.addWidget(QLabel("Disc"), 0)
        self.parent.preview_disc_label = QLabel("-")
        self.parent.preview_disc_label.setStyleSheet(preview_box_style + "color: #dcdcaa;")
        disc_box_row.addWidget(self.parent.preview_disc_label, 1)
        song_container.addLayout(disc_box_row)

        track_box_row = QVBoxLayout()
        track_box_row.setContentsMargins(0, 0, 0, 0)
        track_box_row.setSpacing(2)
        track_box_row.addWidget(QLabel("Track"), 0)
        self.parent.preview_track_label = QLabel("-")
        self.parent.preview_track_label.setStyleSheet(preview_box_style + "color: #dcdcaa;")
        track_box_row.addWidget(self.parent.preview_track_label, 1)
        song_container.addLayout(track_box_row)

        version_box_row = QVBoxLayout()
        version_box_row.setContentsMargins(0, 0, 0, 0)
        version_box_row.setSpacing(2)
        version_box_row.addWidget(QLabel("Versions"), 0)
        self.parent.preview_version_label = QLabel("-")
        self.parent.preview_version_label.setStyleSheet(preview_box_style + "color: #f5a623;")
        version_box_row.addWidget(self.parent.preview_version_label, 1)
        song_container.addLayout(version_box_row)

        date_box_row = QVBoxLayout()
        date_box_row.setContentsMargins(0, 0, 0, 0)
        date_box_row.setSpacing(2)
        date_box_row.addWidget(QLabel("Date"), 0)
        self.parent.preview_date_label = QLabel("-")
        self.parent.preview_date_label.setStyleSheet(preview_box_style + "color: #dcdcaa;")
        date_box_row.addWidget(self.parent.preview_date_label, 1)
        song_container.addLayout(date_box_row)

        preview_layout.addLayout(song_container)
        layout.addLayout(preview_layout)

        # Filename editor with save button
        filename_row = QHBoxLayout()
        filename_row.addWidget(QLabel("Filename:"))
        self.parent.filename_preview = QLineEdit()
        self.parent.filename_preview.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)
        self.parent.filename_preview.textChanged.connect(self.parent.on_filename_changed)
        filename_row.addWidget(self.parent.filename_preview, 1)

        self.parent.save_filename_btn = QPushButton("Save Filename")
        self.parent.save_filename_btn.setEnabled(False)
        self.parent.save_filename_btn.setFixedSize(140, 28)
        self.parent.save_filename_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: #aaaaaa;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QPushButton:enabled {
                background-color: #0d47a1;
                color: white;
            }
            QPushButton:enabled:hover {
                background-color: #1565c0;
            }
        """)
        self.parent.save_filename_btn.clicked.connect(self.parent.save_filename_changes)
        filename_row.addWidget(self.parent.save_filename_btn)
        layout.addLayout(filename_row)

        layout.addStretch()

        # Apply buttons at bottom
        apply_frame = self._create_apply_buttons()
        layout.addWidget(apply_frame)

        return frame

    def _create_apply_buttons(self):
        """Create apply buttons."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        apply_selected = QPushButton("Apply to Selected")
        apply_selected.setFixedHeight(36)
        apply_selected.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        apply_selected.clicked.connect(self.preset_manager.apply_preset_to_selected)
        layout.addWidget(apply_selected)

        apply_all = QPushButton("Apply to All")
        apply_all.setFixedHeight(36)
        apply_all.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        apply_all.clicked.connect(self.preset_manager.apply_preset_to_all)
        layout.addWidget(apply_all)

        return frame

    def add_rule_to_tab(self, tab_name: str):
        """Add a new rule to the specified tab."""
        container = self.parent.rule_containers.get(tab_name)
        if not container:
            return

        layout = container.layout()
        rule_count = sum(1 for i in range(layout.count())
                        if isinstance(layout.itemAt(i).widget(), RuleRow))

        if rule_count >= self.parent.max_rules_per_tab:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self.parent, "Rule Limit",
                f"Maximum of {self.parent.max_rules_per_tab} rules reached for {tab_name.title()}")
            return

        rule_row = RuleRow(self.parent.RULE_OPS)
        rule_row.delete_requested.connect(self.delete_rule)
        rule_row.move_up_requested.connect(self.move_rule_up)
        rule_row.move_down_requested.connect(self.move_rule_down)
        rule_row.rule_changed.connect(self.update_output_preview)

        layout.insertWidget(layout.count() - 1, rule_row)
        self.update_rule_button_states(container)

    def delete_rule(self, rule_row):
        """Delete a rule row."""
        container = rule_row.parent()
        layout = container.layout()

        layout.removeWidget(rule_row)
        rule_row.deleteLater()

        self.update_rule_button_states(container)
        self.update_output_preview()

    def move_rule_up(self, rule_row):
        """Move rule up in the list."""
        container = rule_row.parent()
        layout = container.layout()

        index = layout.indexOf(rule_row)
        if index > 0:
            prev_item = layout.itemAt(index - 1)
            if prev_item and isinstance(prev_item.widget(), RuleRow):
                prev_widget = prev_item.widget()
                current_data = rule_row.get_rule_data()
                prev_data = prev_widget.get_rule_data()

                layout.removeWidget(rule_row)
                layout.removeWidget(prev_widget)

                new_prev = RuleRow(self.parent.RULE_OPS)
                new_prev.set_rule_data(current_data)
                new_prev.delete_requested.connect(self.delete_rule)
                new_prev.move_up_requested.connect(self.move_rule_up)
                new_prev.move_down_requested.connect(self.move_rule_down)
                new_prev.rule_changed.connect(self.update_output_preview)

                new_current = RuleRow(self.parent.RULE_OPS)
                new_current.set_rule_data(prev_data)
                new_current.delete_requested.connect(self.delete_rule)
                new_current.move_up_requested.connect(self.move_rule_up)
                new_current.move_down_requested.connect(self.move_rule_down)
                new_current.rule_changed.connect(self.update_output_preview)

                layout.insertWidget(index - 1, new_prev)
                layout.insertWidget(index, new_current)

                prev_widget.deleteLater()
                rule_row.deleteLater()

                self.update_rule_button_states(container)
                self.update_output_preview()

    def move_rule_down(self, rule_row):
        """Move rule down in the list."""
        container = rule_row.parent()
        layout = container.layout()

        index = layout.indexOf(rule_row)
        if index < layout.count() - 2:
            next_item = layout.itemAt(index + 1)
            if next_item and isinstance(next_item.widget(), RuleRow):
                next_widget = next_item.widget()
                current_data = rule_row.get_rule_data()
                next_data = next_widget.get_rule_data()

                layout.removeWidget(rule_row)
                layout.removeWidget(next_widget)

                new_current = RuleRow(self.parent.RULE_OPS)
                new_current.set_rule_data(next_data)
                new_current.delete_requested.connect(self.delete_rule)
                new_current.move_up_requested.connect(self.move_rule_up)
                new_current.move_down_requested.connect(self.move_rule_down)
                new_current.rule_changed.connect(self.update_output_preview)

                new_next = RuleRow(self.parent.RULE_OPS)
                new_next.set_rule_data(current_data)
                new_next.delete_requested.connect(self.delete_rule)
                new_next.move_up_requested.connect(self.move_rule_up)
                new_next.move_down_requested.connect(self.move_rule_down)
                new_next.rule_changed.connect(self.update_output_preview)

                layout.insertWidget(index, new_current)
                layout.insertWidget(index + 1, new_next)

                rule_row.deleteLater()
                next_widget.deleteLater()

                self.update_rule_button_states(container)
                self.update_output_preview()

    def update_rule_button_states(self, container):
        """Update up/down button states based on position."""
        layout = container.layout()
        rules = []

        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if isinstance(widget, RuleRow):
                rules.append(widget)

        for idx, rule in enumerate(rules):
            if hasattr(rule, 'up_btn'):
                rule.up_btn.setEnabled(idx > 0)

            if hasattr(rule, 'down_btn'):
                rule.down_btn.setEnabled(idx < len(rules) - 1)

    def collect_rules_for_tab(self, tab_name: str) -> list:
        """Collect all rules from a tab."""
        container = self.parent.rule_containers.get(tab_name)
        if not container:
            return []

        rules = []
        layout = container.layout()
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if isinstance(widget, RuleRow):
                rules.append(widget.get_rule_data())

        return rules

    def load_rules_to_tab(self, tab_name: str, rules: list):
        """Load rules into a tab."""
        container = self.parent.rule_containers.get(tab_name)
        if not container:
            return

        layout = container.layout()
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, rule_data in enumerate(rules[:self.parent.max_rules_per_tab]):
            rule_row = RuleRow(self.parent.RULE_OPS)
            rule_row.delete_requested.connect(self.delete_rule)
            rule_row.move_up_requested.connect(self.move_rule_up)
            rule_row.move_down_requested.connect(self.move_rule_down)
            rule_row.rule_changed.connect(self.update_output_preview)

            layout.insertWidget(idx, rule_row)
            rule_row.show()
            rule_row.set_rule_data(rule_data)
            # Verify template was set
            if rule_data.get('then_template'):
                logger.debug(f"Loaded rule {idx} with template: {rule_data['then_template']}")

        self.update_rule_button_states(container)
        layout.update()
        container.updateGeometry()
        QApplication.processEvents()

    def update_output_preview(self):
        """Update output preview based on current rules and selected file."""
        if self.parent.current_selected_file is None or self.parent.current_selected_file >= len(self.parent.song_files):
            return

        self.parent.update_preview_info()

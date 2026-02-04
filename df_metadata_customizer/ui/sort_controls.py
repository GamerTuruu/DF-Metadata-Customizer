"""Multi-level sort controls component."""

from typing import List, Dict, Any, Callable
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt
from df_metadata_customizer.ui.rule_widgets import NoScrollComboBox
from df_metadata_customizer.core import SettingsManager


class SortControlsManager:
    """Manages multi-level sort controls UI and state."""
    
    def __init__(self, parent, on_sort_changed_callback: Callable):
        self.parent = parent
        self.on_sort_changed = on_sort_changed_callback
        self.sort_rules_list: List[Dict[str, Any]] = []
        self.sort_controls_container = None
        self.add_sort_btn = None
        self.expanded = False
        self.toggle_btn = None
        self.summary_label = None
        self.details_container = None
        
    def create_sort_controls(self) -> QFrame:
        """Create collapsible multi-level sort controls."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        main_layout = QVBoxLayout(frame)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
        
        # Header row with toggle and summary
        header_frame = QFrame()
        header_frame.setStyleSheet("QFrame { background-color: transparent; }")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        
        # Toggle button
        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setFixedSize(28, 28)
        self.toggle_btn.clicked.connect(self._toggle_expanded)
        self.toggle_btn.setToolTip("Collapse/Expand sort controls")
        self.toggle_btn.setStyleSheet("QPushButton { font-weight: bold; font-size: 12px; }")
        header_layout.addWidget(self.toggle_btn)
        
        # Add button - moved next to toggle for better visibility
        self.add_sort_btn = QPushButton("+")
        self.add_sort_btn.setFixedSize(28, 28)
        self.add_sort_btn.clicked.connect(self.add_sort_rule)
        self.add_sort_btn.setToolTip("Add another sort level (max 5)")
        self.add_sort_btn.setStyleSheet("QPushButton { font-weight: bold; font-size: 14px; }")
        header_layout.addWidget(self.add_sort_btn)
        
        # Summary label
        self.summary_label = QLabel("Sort by: Title ↑")
        self.summary_label.setStyleSheet("QLabel { font-weight: bold; }")
        header_layout.addWidget(self.summary_label)
        
        header_layout.addStretch()
        main_layout.addWidget(header_frame)
        
        # Details container (collapsible) - directly contains sort rules
        self.details_container = QFrame()
        self.details_container.setStyleSheet("QFrame { background-color: transparent; }")
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(28, 4, 0, 4)
        details_layout.setSpacing(3)
        
        # Container for sort rules - added directly to details_layout
        self.sort_controls_container = QFrame()
        self.sort_controls_container.setStyleSheet("QFrame { background-color: transparent; }")
        container_layout = QVBoxLayout(self.sort_controls_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(3)
        
        # Add first sort rule
        self._add_sort_rule_widget(0, is_first=True)
        
        self.sort_controls_container.setLayout(container_layout)
        details_layout.addWidget(self.sort_controls_container)
        
        main_layout.addWidget(self.details_container)
        
        # Set initial collapsed state
        self.details_container.setVisible(self.expanded)
        
        return frame
    
    
    def _toggle_expanded(self):
        """Toggle the expanded/collapsed state."""
        self.expanded = not self.expanded
        self.details_container.setVisible(self.expanded)
        self.toggle_btn.setText("▼" if self.expanded else "▶")
    
    def _update_summary(self):
        """Update the summary label to show current sort configuration."""
        if not self.sort_rules_list:
            self.summary_label.setText("Sort by: (none)")
            return
        
        summary_parts = []
        for rule_info in self.sort_rules_list:
            field = rule_info['field'].currentText()
            is_asc = rule_info['order'].currentText() == "Asc"
            arrow = "↑" if is_asc else "↓"
            summary_parts.append(f"{field} {arrow}")
        
        summary_text = ", ".join(summary_parts)
        self.summary_label.setText(f"Sort by: {summary_text}")
    
    def _add_sort_rule_widget(self, index: int, is_first: bool = False):
        """Add a sort rule widget to the container."""
        if len(self.sort_rules_list) >= 5:
            return
        
        # Rule frame (horizontal layout for this rule)
        rule_frame = QFrame()
        rule_frame.setStyleSheet("QFrame { background-color: transparent; border: none; }")
        
        rule_layout = QHBoxLayout(rule_frame)
        rule_layout.setContentsMargins(0, 2, 0, 2)
        rule_layout.setSpacing(6)
        
        # Priority label
        priority_label = QLabel(f"{len(self.sort_rules_list) + 1}.")
        priority_label.setFixedWidth(20)
        priority_label.setStyleSheet("QLabel { font-weight: bold; }")
        rule_layout.addWidget(priority_label)
        
        # Field selector - stretches to fill available space
        field_combo = NoScrollComboBox()
        field_combo.addItem("Title")
        field_combo.addItem("Artist")
        field_combo.addItem("Cover Artist")
        field_combo.addItem("Version")
        field_combo.addItem("Date")
        field_combo.addItem("Disc")
        field_combo.addItem("Track")
        field_combo.addItem("Special")
        field_combo.addItem("Filename")
        if not is_first:
            field_combo.setCurrentText("Artist")
        field_combo.setMinimumWidth(110)
        field_combo.setMaxVisibleItems(15)
        field_combo.currentTextChanged.connect(self._on_rule_changed)
        rule_layout.addWidget(field_combo, 1)  # stretch factor of 1
        
        # Order selector - made bigger
        order_combo = NoScrollComboBox()
        order_combo.addItems(["Asc", "Desc"])
        order_combo.setFixedWidth(80)
        order_combo.setMaxVisibleItems(10)
        order_combo.currentTextChanged.connect(self._on_rule_changed)
        rule_layout.addWidget(order_combo)
        
        # Move up button
        up_btn = QPushButton("▲")
        up_btn.setFixedSize(26, 26)
        up_btn.setToolTip("Move up")
        up_btn.clicked.connect(lambda checked=False, rule_frame=rule_frame: self._move_sort_rule_by_frame(rule_frame, -1))
        rule_layout.addWidget(up_btn)
        
        # Move down button
        down_btn = QPushButton("▼")
        down_btn.setFixedSize(26, 26)
        down_btn.setToolTip("Move down")
        down_btn.clicked.connect(lambda checked=False, rule_frame=rule_frame: self._move_sort_rule_by_frame(rule_frame, 1))
        rule_layout.addWidget(down_btn)
        
        # Remove button - red color to indicate delete action
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(26, 26)
        remove_btn.setToolTip("Remove this sort level")
        remove_btn.setStyleSheet("QPushButton { background-color: #c73939; color: white; font-weight: bold; border-radius: 3px; } QPushButton:hover { background-color: #e74c3c; }")
        remove_btn.clicked.connect(lambda checked=False, rule_frame=rule_frame: self._remove_sort_rule_by_frame(rule_frame))
        rule_layout.addWidget(remove_btn)
        
        rule_frame.setLayout(rule_layout)
        
        # Add to container
        container_layout = self.sort_controls_container.layout()
        container_layout.addWidget(rule_frame)
        
        self.sort_rules_list.append({
            'frame': rule_frame,
            'field': field_combo,
            'order': order_combo,
            'up_btn': up_btn,
            'down_btn': down_btn,
            'remove_btn': remove_btn,
            'priority_label': priority_label,
            'is_first': is_first
        })
        self._update_sort_button_states()
        self._update_summary()
        if hasattr(self.parent, "theme_colors") and self.parent.theme_colors:
            self.update_theme(self.parent.theme_colors, SettingsManager.theme == "dark")
    
    def _on_rule_changed(self):
        """Handle when a sort rule is changed."""
        self._update_summary()
        self.on_sort_changed()
    
    
    def add_sort_rule(self):
        """Add another sort level."""
        if len(self.sort_rules_list) >= 5:
            QMessageBox.information(self.parent, "Limit", "Maximum 5 sort levels allowed.")
            return
        
        self._add_sort_rule_widget(len(self.sort_rules_list), is_first=False)
        self._update_priority_labels()
        self._on_rule_changed()
    
    def remove_sort_rule(self, index: int):
        """Remove a sort rule."""
        if index >= 0 and index < len(self.sort_rules_list):
            rule_info = self.sort_rules_list[index]
            container_layout = self.sort_controls_container.layout()
            container_layout.removeWidget(rule_info['frame'])
            rule_info['frame'].deleteLater()
            self.sort_rules_list.pop(index)
            self._update_priority_labels()
            self._update_sort_button_states()
            self._update_summary()
            self.on_sort_changed()
    
    
    def _remove_sort_rule_by_frame(self, frame):
        """Remove a sort rule by frame reference."""
        for i, rule_info in enumerate(self.sort_rules_list):
            if rule_info['frame'] is frame:
                self.remove_sort_rule(i)
                break
    
    def _update_priority_labels(self):
        """Update priority numbers after reordering or adding/removing."""
        for idx, rule_info in enumerate(self.sort_rules_list):
            rule_info['priority_label'].setText(f"{idx + 1}.")
    
    def _move_sort_rule_by_frame(self, frame, direction):
        """Move a sort rule by frame reference. direction: -1 for up, 1 for down."""
        for i, rule_info in enumerate(self.sort_rules_list):
            if rule_info['frame'] is frame:
                if direction == -1 and i > 0:  # Move up
                    self.sort_rules_list[i - 1], self.sort_rules_list[i] = \
                        self.sort_rules_list[i], self.sort_rules_list[i - 1]
                    self._rebuild_sort_ui()
                    self._on_rule_changed()
                elif direction == 1 and i < len(self.sort_rules_list) - 1:  # Move down
                    self.sort_rules_list[i], self.sort_rules_list[i + 1] = \
                        self.sort_rules_list[i + 1], self.sort_rules_list[i]
                    self._rebuild_sort_ui()
                    self._on_rule_changed()
                break
    
    
    def _rebuild_sort_ui(self):
        """Rebuild sort rules UI after reordering."""
        container_layout = self.sort_controls_container.layout()
        
        # Remove all widgets from layout
        while container_layout.count() > 0:
            item = container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Recreate frames for each sort rule
        for idx, rule_info in enumerate(self.sort_rules_list):
            old_frame = rule_info['frame']
            is_first = (idx == 0)
            
            # Get current values from old frame
            field_text = rule_info['field'].currentText()
            order_text = rule_info['order'].currentText()
            
            # Create new frame
            new_frame = QFrame()
            new_frame.setStyleSheet("QFrame { background-color: transparent; border: none; }")
            
            new_layout = QHBoxLayout(new_frame)
            new_layout.setContentsMargins(0, 2, 0, 2)
            new_layout.setSpacing(6)
            
            # Priority label
            priority_label = QLabel(f"{idx + 1}.")
            priority_label.setFixedWidth(20)
            priority_label.setStyleSheet("QLabel { font-weight: bold; }")
            new_layout.addWidget(priority_label)
            
            # Field selector
            new_field_combo = NoScrollComboBox()
            new_field_combo.addItems(["Title", "Artist", "Cover Artist", "Version", "Date", "Disc", "Track", "Special", "Filename"])
            new_field_combo.setCurrentText(field_text)
            new_field_combo.setMinimumWidth(110)
            new_field_combo.setMaxVisibleItems(15)
            new_field_combo.currentTextChanged.connect(self._on_rule_changed)
            new_layout.addWidget(new_field_combo, 1)
            
            # Order selector
            new_order_combo = NoScrollComboBox()
            new_order_combo.addItems(["Asc", "Desc"])
            new_order_combo.setCurrentText(order_text)
            new_order_combo.setFixedWidth(80)
            new_order_combo.setMaxVisibleItems(10)
            new_order_combo.currentTextChanged.connect(self._on_rule_changed)
            new_layout.addWidget(new_order_combo)
            
            # Move up button
            up_btn = QPushButton("▲")
            up_btn.setFixedSize(26, 26)
            up_btn.setToolTip("Move up")
            up_btn.clicked.connect(lambda checked=False, frame=new_frame: self._move_sort_rule_by_frame(frame, -1))
            new_layout.addWidget(up_btn)
            
            # Move down button
            down_btn = QPushButton("▼")
            down_btn.setFixedSize(26, 26)
            down_btn.setToolTip("Move down")
            down_btn.clicked.connect(lambda checked=False, frame=new_frame: self._move_sort_rule_by_frame(frame, 1))
            new_layout.addWidget(down_btn)
            
            # Remove button
            remove_btn = QPushButton("✕")
            remove_btn.setFixedSize(26, 26)
            remove_btn.setToolTip("Remove this sort level")
            remove_btn.setStyleSheet("QPushButton { background-color: #c73939; color: white; font-weight: bold; border-radius: 3px; } QPushButton:hover { background-color: #e74c3c; }")
            remove_btn.clicked.connect(lambda checked=False, frame=new_frame: self._remove_sort_rule_by_frame(frame))
            new_layout.addWidget(remove_btn)
            
            new_frame.setLayout(new_layout)
            
            # Update rule_info with new widgets
            rule_info['frame'] = new_frame
            rule_info['field'] = new_field_combo
            rule_info['order'] = new_order_combo
            rule_info['up_btn'] = up_btn
            rule_info['down_btn'] = down_btn
            rule_info['remove_btn'] = remove_btn
            rule_info['priority_label'] = priority_label
            rule_info['is_first'] = is_first
            
            # Add to layout
            container_layout.addWidget(new_frame)
            
            # Delete old frame
            old_frame.deleteLater()
        
        self._update_sort_button_states()
        self._update_summary()
        if hasattr(self.parent, "theme_colors") and self.parent.theme_colors:
            self.update_theme(self.parent.theme_colors, SettingsManager.theme == "dark")


    def _update_sort_button_states(self):
        """Enable/disable sort rule buttons based on position and count."""
        total = len(self.sort_rules_list)
        for idx, rule_info in enumerate(self.sort_rules_list):
            up_btn = rule_info.get('up_btn')
            down_btn = rule_info.get('down_btn')
            remove_btn = rule_info.get('remove_btn')
            if up_btn:
                up_btn.setEnabled(idx > 0)
            if down_btn:
                down_btn.setEnabled(idx < total - 1)
            if remove_btn:
                remove_btn.setEnabled(total > 1)
        
        # Update add button state
        if self.add_sort_btn:
            self.add_sort_btn.setEnabled(total < 5)
    
    def get_sort_rules(self) -> List[tuple]:
        """Get current sort rules as list of (field, ascending) tuples."""
        rules = []
        for rule_info in self.sort_rules_list:
            field = rule_info['field'].currentText()
            ascending = rule_info['order'].currentText() == "Asc"
            rules.append((field, ascending))
        return rules
    
    def update_theme(self, theme_colors: dict, is_dark: bool):
        """Update sort controls with current theme colors."""
        c = theme_colors
        
        button_pressed = '#2a2d2e' if is_dark else '#d8d8d8'
        button_disabled = '#252526' if is_dark else '#f3f3f3'
        text_disabled = '#858585' if is_dark else '#999999'
        
        # Button colors
        button_bg = c['bg_tertiary'] if is_dark else '#e8e8e8'
        button_hover = c['bg_secondary'] if is_dark else '#d4d4d4'
        button_text = c['text'] if is_dark else '#2d2d2d'
        
        dropdown_bg = '#2d2d2d' if is_dark else '#ffffff'
        combo_stylesheet = f"""
            QComboBox {{
                background-color: {c['bg_primary']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 4px;
                padding-right: 20px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
                background-color: transparent;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {dropdown_bg};
                color: {c['text']};
                selection-background-color: {c['button']};
                selection-color: #ffffff;
            }}
        """
        
        button_stylesheet = f"""
            QPushButton {{
                background-color: {button_bg};
                color: {button_text};
                border: 1px solid {c['border']};
                border-radius: 3px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {button_hover};
            }}
            QPushButton:pressed {{
                background-color: {button_pressed};
            }}
            QPushButton:disabled {{
                background-color: {button_disabled};
                color: {text_disabled};
                border: 1px solid {c['border']};
            }}
        """
        
        # Update toggle button with high contrast
        toggle_bg = c['button']
        toggle_text = '#ffffff'
        toggle_border = c['button']
        if self.toggle_btn:
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {toggle_bg};
                    color: {toggle_text};
                    border: 2px solid {toggle_border};
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {button_hover};
                    border-color: {button_hover};
                }}
                QPushButton:pressed {{
                    background-color: {button_pressed};
                }}
            """)
        
        # Update add button
        if self.add_sort_btn:
            self.add_sort_btn.setStyleSheet(button_stylesheet)
        
        # Update summary label
        if self.summary_label:
            self.summary_label.setStyleSheet(f"QLabel {{ font-weight: bold; color: {c['text']}; }}")
        
        # Update all sort control widgets
        for rule_info in self.sort_rules_list:
            # Update comboboxes
            field_combo = rule_info.get('field')
            order_combo = rule_info.get('order')
            if field_combo:
                field_combo.setStyleSheet(combo_stylesheet)
            if order_combo:
                order_combo.setStyleSheet(combo_stylesheet)
            
            # Update priority label
            priority_label = rule_info.get('priority_label')
            if priority_label:
                priority_label.setStyleSheet(f"QLabel {{ font-weight: bold; color: {c['text']}; }}")
            
            # Update buttons - separate styling for remove button
            for btn_key in ['up_btn', 'down_btn']:
                btn = rule_info.get(btn_key)
                if btn:
                    btn.setStyleSheet(button_stylesheet)
            
            # Remove button gets red styling
            remove_btn = rule_info.get('remove_btn')
            if remove_btn:
                remove_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #c73939;
                        color: white;
                        font-weight: bold;
                        border: 1px solid #a02828;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #e74c3c;
                    }
                    QPushButton:pressed {
                        background-color: #a02828;
                    }
                    QPushButton:disabled {
                        background-color: #8b3a3a;
                        color: #cccccc;
                    }
                """)
"""Multi-level sort controls component."""

from typing import List, Dict, Any, Callable
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QPushButton, QLabel, QMessageBox
)
from df_metadata_customizer.ui.rule_widgets import NoScrollComboBox


class SortControlsManager:
    """Manages multi-level sort controls UI and state."""
    
    def __init__(self, parent, on_sort_changed_callback: Callable):
        self.parent = parent
        self.on_sort_changed = on_sort_changed_callback
        self.sort_rules_list: List[Dict[str, Any]] = []
        self.sort_controls_container = None
        self.add_sort_btn = None
        
    def create_sort_controls(self) -> QFrame:
        """Create multi-level sort controls."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # + button
        self.add_sort_btn = QPushButton("+")
        self.add_sort_btn.setFixedSize(30, 30)
        self.add_sort_btn.clicked.connect(self.add_sort_rule)
        self.add_sort_btn.setToolTip("Add another sort level (max 5)")
        layout.addWidget(self.add_sort_btn)
        
        # Sort label
        layout.addWidget(QLabel("Sort by:"))
        
        # Container for sort rules
        self.sort_controls_container = QFrame()
        self.sort_controls_container.setStyleSheet("QFrame { background-color: transparent; }")
        container_layout = QHBoxLayout(self.sort_controls_container)
        container_layout.setContentsMargins(6, 0, 0, 0)
        container_layout.setSpacing(4)
        
        # Add first sort rule
        self._add_sort_rule_widget(0, is_first=True)
        
        self.sort_controls_container.setLayout(container_layout)
        layout.addWidget(self.sort_controls_container)
        layout.addStretch()
        
        return frame
    
    def _add_sort_rule_widget(self, index: int, is_first: bool = False):
        """Add a sort rule widget to the container."""
        if len(self.sort_rules_list) >= 5:
            return
        
        # Initial styling
        rule_frame = QFrame()
        rule_frame.setStyleSheet("QFrame { background-color: transparent; border: none; padding: 2px; }")
        
        rule_layout = QHBoxLayout(rule_frame)
        rule_layout.setContentsMargins(4, 2, 4, 2)
        rule_layout.setSpacing(4)
        
        # Field selector
        field_combo = NoScrollComboBox()
        field_combo.addItem("Title")
        field_combo.addItem("Artist")
        field_combo.addItem("Cover Artist")
        field_combo.addItem("Version")
        field_combo.addItem("Date")
        field_combo.addItem("Disc")
        field_combo.addItem("Track")
        field_combo.addItem("File")
        field_combo.addItem("Special")
        if not is_first:
            field_combo.setCurrentText("Artist")
        field_combo.setFixedWidth(100)
        field_combo.currentTextChanged.connect(self.on_sort_changed)
        rule_layout.addWidget(field_combo)
        
        # Order selector
        order_combo = NoScrollComboBox()
        order_combo.addItems(["Asc", "Desc"])
        order_combo.setFixedWidth(60)
        order_combo.currentTextChanged.connect(self.on_sort_changed)
        rule_layout.addWidget(order_combo)
        
        # Move up button
        up_btn = QPushButton("◀")
        up_btn.setFixedSize(25, 25)
        up_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #888;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #484848;
                color: #aaa;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #555;
                border: 1px solid #444;
            }
        """)
        up_btn.clicked.connect(lambda checked=False, rule_frame=rule_frame: self._move_sort_rule_by_frame(rule_frame, -1))
        rule_layout.addWidget(up_btn)
        
        # Move down button
        down_btn = QPushButton("▶")
        down_btn.setFixedSize(25, 25)
        down_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #888;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #484848;
                color: #aaa;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #555;
                border: 1px solid #444;
            }
        """)
        down_btn.clicked.connect(lambda checked=False, rule_frame=rule_frame: self._move_sort_rule_by_frame(rule_frame, 1))
        rule_layout.addWidget(down_btn)
        
        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(25, 25)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #999;
                border: 1px solid #555;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #484848;
                color: #aaa;
                border: 1px solid #666;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #555;
                border: 1px solid #444;
            }
        """)
        remove_btn.clicked.connect(lambda checked=False, rule_frame=rule_frame: self._remove_sort_rule_by_frame(rule_frame))
        rule_layout.addWidget(remove_btn)
        
        rule_layout.addStretch()
        rule_frame.setLayout(rule_layout)
        
        # Add to container
        container_layout = self.sort_controls_container.layout()
        container_layout.insertWidget(container_layout.count(), rule_frame)
        
        self.sort_rules_list.append({
            'frame': rule_frame,
            'field': field_combo,
            'order': order_combo,
            'up_btn': up_btn,
            'down_btn': down_btn,
            'remove_btn': remove_btn,
            'is_first': is_first
        })
        self._update_sort_button_states()
    
    def add_sort_rule(self):
        """Add another sort level."""
        if len(self.sort_rules_list) >= 5:
            QMessageBox.information(self.parent, "Limit", "Maximum 5 sort levels allowed.")
            return
        
        self._add_sort_rule_widget(len(self.sort_rules_list), is_first=False)
        self.on_sort_changed()
    
    def remove_sort_rule(self, index: int):
        """Remove a sort rule."""
        if index >= 0 and index < len(self.sort_rules_list):
            rule_info = self.sort_rules_list[index]
            container_layout = self.sort_controls_container.layout()
            container_layout.removeWidget(rule_info['frame'])
            rule_info['frame'].deleteLater()
            self.sort_rules_list.pop(index)
            self._update_sort_button_states()
            self.on_sort_changed()
    
    def _remove_sort_rule_by_frame(self, frame):
        """Remove a sort rule by frame reference."""
        for i, rule_info in enumerate(self.sort_rules_list):
            if rule_info['frame'] is frame:
                self.remove_sort_rule(i)
                break
    
    def _move_sort_rule_by_frame(self, frame, direction):
        """Move a sort rule by frame reference. direction: -1 for up, 1 for down."""
        for i, rule_info in enumerate(self.sort_rules_list):
            if rule_info['frame'] is frame:
                if direction == -1 and i > 0:  # Move up
                    self.sort_rules_list[i - 1], self.sort_rules_list[i] = \
                        self.sort_rules_list[i], self.sort_rules_list[i - 1]
                    self._rebuild_sort_ui()
                    self.on_sort_changed()
                elif direction == 1 and i < len(self.sort_rules_list) - 1:  # Move down
                    self.sort_rules_list[i], self.sort_rules_list[i + 1] = \
                        self.sort_rules_list[i + 1], self.sort_rules_list[i]
                    self._rebuild_sort_ui()
                    self.on_sort_changed()
                break
    
    def _rebuild_sort_ui(self):
        """Rebuild sort rules UI after reordering."""
        container_layout = self.sort_controls_container.layout()
        
        # Remove all widgets from layout
        while container_layout.count() > 0:
            item = container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Recreate frames for each sort rule with correct is_first status
        for idx, rule_info in enumerate(self.sort_rules_list):
            old_frame = rule_info['frame']
            is_first = (idx == 0)
            
            # Get current values from old frame
            field_text = rule_info['field'].currentText()
            order_text = rule_info['order'].currentText()
            
            # Create new frame
            new_frame = QFrame()
            new_frame.setStyleSheet("QFrame { background-color: transparent; border: none; padding: 2px; }")
            
            new_layout = QHBoxLayout(new_frame)
            new_layout.setContentsMargins(4, 2, 4, 2)
            new_layout.setSpacing(4)
            
            # Field selector
            new_field_combo = NoScrollComboBox()
            new_field_combo.addItems(["Title", "Artist", "Cover Artist", "Version", "Date", "Disc", "Track", "File", "Special"])
            new_field_combo.setCurrentText(field_text)
            new_field_combo.setFixedWidth(100)
            new_field_combo.currentTextChanged.connect(self.on_sort_changed)
            new_layout.addWidget(new_field_combo)
            
            # Order selector
            new_order_combo = NoScrollComboBox()
            new_order_combo.addItems(["Asc", "Desc"])
            new_order_combo.setCurrentText(order_text)
            new_order_combo.setFixedWidth(60)
            new_order_combo.currentTextChanged.connect(self.on_sort_changed)
            new_layout.addWidget(new_order_combo)
            
            # Move up button
            up_btn = QPushButton("◀")
            up_btn.setFixedSize(25, 25)
            up_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: #888;
                    border: 1px solid #555;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #484848;
                    color: #aaa;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
                QPushButton:disabled {
                    background-color: #2b2b2b;
                    color: #555;
                    border: 1px solid #444;
                }
            """)
            up_btn.clicked.connect(lambda checked=False, frame=new_frame: self._move_sort_rule_by_frame(frame, -1))
            new_layout.addWidget(up_btn)
            
            # Move down button
            down_btn = QPushButton("▶")
            down_btn.setFixedSize(25, 25)
            down_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: #888;
                    border: 1px solid #555;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #484848;
                    color: #aaa;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
                QPushButton:disabled {
                    background-color: #2b2b2b;
                    color: #555;
                    border: 1px solid #444;
                }
            """)
            down_btn.clicked.connect(lambda checked=False, frame=new_frame: self._move_sort_rule_by_frame(frame, 1))
            new_layout.addWidget(down_btn)
            
            # Remove button
            remove_btn = QPushButton("✕")
            remove_btn.setFixedSize(25, 25)
            remove_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: #999;
                    border: 1px solid #555;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #484848;
                    color: #aaa;
                    border: 1px solid #666;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
                QPushButton:disabled {
                    background-color: #2b2b2b;
                    color: #555;
                    border: 1px solid #444;
                }
            """)
            remove_btn.clicked.connect(lambda checked=False, frame=new_frame: self._remove_sort_rule_by_frame(frame))
            new_layout.addWidget(remove_btn)
            
            new_layout.addStretch()
            new_frame.setLayout(new_layout)
            
            # Update rule_info with new widgets
            rule_info['frame'] = new_frame
            rule_info['field'] = new_field_combo
            rule_info['order'] = new_order_combo
            rule_info['up_btn'] = up_btn
            rule_info['down_btn'] = down_btn
            rule_info['remove_btn'] = remove_btn
            rule_info['is_first'] = is_first
            
            # Add to layout
            container_layout.addWidget(new_frame)
            
            # Delete old frame
            old_frame.deleteLater()
        
        container_layout.addStretch()
        self._update_sort_button_states()

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
    
    def get_sort_rules(self) -> List[tuple]:
        """Get current sort rules as list of (field, ascending) tuples."""
        rules = []
        for rule_info in self.sort_rules_list:
            field = rule_info['field'].currentText()
            ascending = rule_info['order'].currentText() == "Asc"
            rules.append((field, ascending))
        return rules

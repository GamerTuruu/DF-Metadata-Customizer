"""Rule Builder Widgets for PySide6."""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal, QEvent
from df_metadata_customizer.core.metadata import MetadataFields


class NoScrollComboBox(QComboBox):
    """ComboBox that ignores mouse wheel events."""
    
    def wheelEvent(self, event):
        """Ignore wheel events to prevent accidental changes."""
        event.ignore()


class RuleRow(QFrame):
    """A single rule row with IF-THEN logic."""
    
    rule_changed = Signal()
    delete_requested = Signal(object)
    move_up_requested = Signal(object)
    move_down_requested = Signal(object)
    
    def __init__(self, operators: list, parent=None):
        super().__init__(parent)
        
        self.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        # Logic selector (AND/OR)s
        self.logic_combo = NoScrollComboBox()
        self.logic_combo.addItems(["AND", "OR"])
        self.logic_combo.setFixedWidth(55)
        self.logic_combo.currentTextChanged.connect(self.rule_changed.emit)
        layout.addWidget(self.logic_combo)
        
        # IF label
        if_label = QLabel("IF")
        if_label.setStyleSheet("font-weight: bold; color: #90ee90;")
        layout.addWidget(if_label)
        
        # Field selector
        self.field_combo = NoScrollComboBox()
        field_names = [
            "Title", "Artist", "CoverArtist", "Album", "Version",
            "Date", "Disc", "Track", "File", "Special"
        ]
        self.field_combo.addItems(field_names)
        self.field_combo.setFixedWidth(120)
        self.field_combo.currentTextChanged.connect(self.rule_changed.emit)
        layout.addWidget(self.field_combo)
        
        # Operator selector
        self.op_combo = NoScrollComboBox()
        self.op_combo.addItems(operators)
        self.op_combo.setFixedWidth(100)
        self.op_combo.currentTextChanged.connect(self.rule_changed.emit)
        layout.addWidget(self.op_combo)
        
        # Value entry
        self.value_entry = QLineEdit()
        self.value_entry.setPlaceholderText("value (leave empty for 'is empty' etc.)")
        self.value_entry.textChanged.connect(self.rule_changed.emit)
        layout.addWidget(self.value_entry, 1)
        
        # THEN label
        then_label = QLabel("THEN")
        then_label.setStyleSheet("font-weight: bold; color: #90ee90;")
        layout.addWidget(then_label)
        
        # Template entry
        self.template_entry = QLineEdit()
        self.template_entry.setPlaceholderText("e.g. {Title} - {Artist}")
        self.template_entry.textChanged.connect(self.rule_changed.emit)
        layout.addWidget(self.template_entry, 1)
        
        # Move up button
        self.up_btn = QPushButton("▲")
        self.up_btn.setFixedSize(28, 28)
        self.up_btn.clicked.connect(lambda: self.move_up_requested.emit(self))
        layout.addWidget(self.up_btn)
        
        # Move down button
        self.down_btn = QPushButton("▼")
        self.down_btn.setFixedSize(28, 28)
        self.down_btn.clicked.connect(lambda: self.move_down_requested.emit(self))
        layout.addWidget(self.down_btn)
        
        # Delete button
        delete_btn = QPushButton("✖")
        delete_btn.setFixedSize(28, 28)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #b33333;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c55555;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        layout.addWidget(delete_btn)
        
        # Store is_first flag (not shown in UI, but preserved from presets)
        self.is_first = False
    
    def get_logic(self):
        """Get AND/OR logic."""
        if self.logic_combo:
            return self.logic_combo.currentText()
        return "AND"
    
    def set_logic(self, logic: str):
        """Set AND/OR logic."""
        if self.logic_combo:
            self.logic_combo.setCurrentText(logic)
    
    def get_rule_data(self):
        """Get rule as dictionary."""
        data = {
            "logic": self.get_logic(),
            "if_field": self.field_combo.currentText(),
            "if_operator": self.op_combo.currentText(),
            "if_value": self.value_entry.text(),
            "then_template": self.template_entry.text()
        }
        if self.is_first:
            data["is_first"] = True
        return data
    
    def set_rule_data(self, data: dict):
        """Load rule from dictionary."""
        # Block signals while setting data to avoid premature updates
        widgets = [self.field_combo, self.op_combo, self.value_entry, self.template_entry]
        if self.logic_combo:
            widgets.insert(0, self.logic_combo)
        
        for widget in widgets:
            widget.blockSignals(True)
        
        try:
            if "logic" in data and self.logic_combo:
                self.logic_combo.setCurrentText(data["logic"])
            if "if_field" in data:
                self.field_combo.setCurrentText(data["if_field"])
            if "if_operator" in data:
                self.op_combo.setCurrentText(data["if_operator"])
            if "if_value" in data:
                self.value_entry.setText(data["if_value"])
            if "then_template" in data:
                self.template_entry.setText(data["then_template"])
            # Store is_first flag
            self.is_first = data.get("is_first", False)
        finally:
            # Unblock signals and emit update
            for widget in widgets:
                widget.blockSignals(False)

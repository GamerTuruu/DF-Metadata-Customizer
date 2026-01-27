"""Preset maker/editor dialog."""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QComboBox,
    QSpinBox,
    QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from df_metadata_customizer.core.preset_service import (
    Preset,
    PresetRule,
    PresetCondition,
    PresetAction,
)
from df_metadata_customizer.core.metadata import MetadataFields


class PresetMakerDialog(QDialog):
    """Dialog for creating and editing presets."""

    def __init__(self, preset: Preset | None = None, parent=None) -> None:
        """Initialize preset maker dialog."""
        super().__init__(parent)
        
        self.setWindowTitle("Preset Maker")
        self.setGeometry(100, 100, 900, 600)
        self.preset = preset or Preset(name="New Preset")
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup UI."""
        layout = QVBoxLayout()
        
        # Preset info
        info_layout = QHBoxLayout()
        
        info_layout.addWidget(QLabel("Preset Name:"))
        self.name_input = QLineEdit()
        self.name_input.setText(self.preset.name)
        info_layout.addWidget(self.name_input)
        
        info_layout.addWidget(QLabel("Description:"))
        self.desc_input = QLineEdit()
        self.desc_input.setText(self.preset.description or "")
        info_layout.addWidget(self.desc_input)
        
        layout.addLayout(info_layout)
        
        # Rules table
        layout.addWidget(QLabel("Rules:"))
        
        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(6)
        self.rules_table.setHorizontalHeaderLabels([
            "Name",
            "Condition Field",
            "Operator",
            "Value",
            "Action Field",
            "New Value",
        ])
        
        header = self.rules_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Populate existing rules
        for rule in self.preset.rules:
            self._add_rule_to_table(rule)
        
        layout.addWidget(self.rules_table)
        
        # Add rule button
        add_rule_btn = QPushButton("➕ Add Rule")
        add_rule_btn.clicked.connect(self._add_empty_rule)
        layout.addWidget(add_rule_btn)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        delete_btn = QPushButton("🗑️ Delete Rule")
        delete_btn.clicked.connect(self._delete_rule)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("💾 Save Preset")
        save_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(delete_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def _add_rule_to_table(self, rule: PresetRule) -> None:
        """Add a rule to the table."""
        row = self.rules_table.rowCount()
        self.rules_table.insertRow(row)
        
        self.rules_table.setItem(row, 0, QTableWidgetItem(rule.name))
        self.rules_table.setItem(row, 1, QTableWidgetItem(rule.condition.field))
        
        operator_combo = QComboBox()
        operator_combo.addItems([
            "is",
            "contains",
            "starts with",
            "ends with",
            "is empty",
            "is not empty",
        ])
        operator_combo.setCurrentText(rule.condition.operator)
        self.rules_table.setCellWidget(row, 2, operator_combo)
        
        self.rules_table.setItem(row, 3, QTableWidgetItem(rule.condition.value))
        self.rules_table.setItem(row, 4, QTableWidgetItem(rule.action.field))
        self.rules_table.setItem(row, 5, QTableWidgetItem(rule.action.value))

    def _add_empty_rule(self) -> None:
        """Add empty rule row."""
        row = self.rules_table.rowCount()
        self.rules_table.insertRow(row)
        
        # Add operator combo
        operator_combo = QComboBox()
        operator_combo.addItems([
            "is",
            "contains",
            "starts with",
            "ends with",
            "is empty",
            "is not empty",
        ])
        self.rules_table.setCellWidget(row, 2, operator_combo)

    def _delete_rule(self) -> None:
        """Delete selected rule."""
        current_row = self.rules_table.currentRow()
        if current_row >= 0:
            self.rules_table.removeRow(current_row)

    def get_preset(self) -> Preset:
        """Get the edited preset."""
        self.preset.name = self.name_input.text()
        self.preset.description = self.desc_input.text()
        
        # Extract rules from table
        rules = []
        for row in range(self.rules_table.rowCount()):
            name = self.rules_table.item(row, 0)
            cond_field = self.rules_table.item(row, 1)
            operator_widget = self.rules_table.cellWidget(row, 2)
            cond_value = self.rules_table.item(row, 3)
            action_field = self.rules_table.item(row, 4)
            action_value = self.rules_table.item(row, 5)
            
            if (
                name and cond_field and operator_widget and
                action_field and action_value
            ):
                rule = PresetRule(
                    name=name.text(),
                    condition=PresetCondition(
                        field=cond_field.text(),
                        operator=operator_widget.currentText(),
                        value=cond_value.text() if cond_value else "",
                    ),
                    action=PresetAction(
                        field=action_field.text(),
                        value=action_value.text(),
                    ),
                )
                rules.append(rule)
        
        self.preset.rules = rules
        return self.preset

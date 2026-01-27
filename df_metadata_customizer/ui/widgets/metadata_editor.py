"""Editable metadata editor widget."""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QFormLayout,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from df_metadata_customizer.core.metadata import MetadataFields


class MetadataEditorWidget(QWidget):
    """Widget for editing metadata fields."""

    metadata_changed = pyqtSignal(dict)
    save_clicked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        """Initialize metadata editor."""
        super().__init__(parent)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Metadata Editor")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Scroll area for form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        form_widget = QWidget()
        form_layout = QFormLayout()
        
        # Create input fields
        self.fields = {}
        
        field_names = [
            (MetadataFields.TITLE, "Title"),
            (MetadataFields.ARTIST, "Artist"),
            (MetadataFields.COVER_ARTIST, "Cover Artist"),
            (MetadataFields.VERSION, "Version"),
            (MetadataFields.DATE, "Date"),
            (MetadataFields.DISC, "Disc"),
            (MetadataFields.TRACK, "Track"),
            (MetadataFields.COMMENT, "Comment"),
            (MetadataFields.SPECIAL, "Special"),
        ]
        
        for field_key, field_label in field_names:
            field_input = QLineEdit()
            field_input.setPlaceholderText(f"Enter {field_label.lower()}...")
            self.fields[field_key] = field_input
            form_layout.addRow(QLabel(field_label + ":"), field_input)
        
        form_widget.setLayout(form_layout)
        scroll.setWidget(form_widget)
        
        layout.addWidget(scroll)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("💾 Save Changes")
        save_btn.clicked.connect(self._on_save)
        
        reset_btn = QPushButton("↺ Reset")
        reset_btn.clicked.connect(self._on_reset)
        
        button_layout.addWidget(reset_btn)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self._current_data = {}

    def load_metadata(self, metadata: dict) -> None:
        """Load metadata into editor."""
        self._current_data = dict(metadata)
        
        for field_key, field_input in self.fields.items():
            value = metadata.get(field_key, "")
            field_input.setText(str(value))

    def _on_save(self) -> None:
        """Save changes."""
        data = {}
        for field_key, field_input in self.fields.items():
            value = field_input.text()
            if value:
                data[field_key] = value
        
        self.metadata_changed.emit(data)
        self.save_clicked.emit()

    def _on_reset(self) -> None:
        """Reset to original values."""
        self.load_metadata(self._current_data)

    def clear(self) -> None:
        """Clear all fields."""
        for field_input in self.fields.values():
            field_input.clear()
        self._current_data = {}

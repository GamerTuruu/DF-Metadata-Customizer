"""Search and filter widget for file tree."""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QComboBox, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal, Qt


class SearchWidget(QWidget):
    """Widget for searching and filtering files."""

    search_changed = pyqtSignal(str)
    filter_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        """Initialize search widget."""
        super().__init__(parent)
        
        layout = QHBoxLayout()
        
        # Search field
        layout.addWidget(QLabel("🔍 Search:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by title, artist, version...")
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)
        
        # Filter dropdown
        layout.addWidget(QLabel("Filter:"))
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "All Files",
            "Latest Version Only",
            "By Artist",
            "By Date",
            "By Disc",
        ])
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        layout.addWidget(self.filter_combo)
        
        # Clear button
        clear_btn = QPushButton("✕ Clear")
        clear_btn.clicked.connect(self._clear_search)
        layout.addWidget(clear_btn)
        
        layout.addStretch()
        
        self.setLayout(layout)

    def _on_search_changed(self) -> None:
        """Handle search text change."""
        self.search_changed.emit(self.search_input.text())

    def _on_filter_changed(self) -> None:
        """Handle filter change."""
        self.filter_changed.emit(self.filter_combo.currentText())

    def _clear_search(self) -> None:
        """Clear search field."""
        self.search_input.clear()

    def get_search_query(self) -> str:
        """Get current search query."""
        return self.search_input.text()

    def get_filter(self) -> str:
        """Get current filter."""
        return self.filter_combo.currentText()

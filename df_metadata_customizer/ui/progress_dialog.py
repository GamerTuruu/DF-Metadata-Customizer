"""Progress Dialog for long-running operations."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QFrame
)
from PySide6.QtCore import Qt
from df_metadata_customizer.core import SettingsManager
from df_metadata_customizer.ui.styles import get_theme_colors


class ProgressDialog(QDialog):
    """Dialog showing progress of long operations."""
    
    def __init__(self, title: str = "Processing", parent=None):
        super().__init__()
        self.setWindowTitle(title)
        # Wayland-compatible: Use Dialog flag for proper window management
        self.setWindowFlags(Qt.Dialog)
        self.setModal(False)
        self.setMinimumWidth(400)
        self.cancelled = False
        
        c = get_theme_colors(SettingsManager.theme)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_secondary']};
            }}
            QLabel {{
                color: {c['text']};
                font-size: 11pt;
            }}
            QPushButton {{
                background-color: #b33333;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: #c55555;
            }}
            QProgressBar {{
                border: 1px solid {c['border']};
                border-radius: 4px;
                text-align: center;
                background-color: {c['bg_primary']};
                color: {c['text']};
            }}
            QProgressBar::chunk {{
                background-color: {c['button']};
                border-radius: 3px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Status label
        self.status_label = QLabel("Initializing...")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        layout.addWidget(self.cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)
    
    def update_progress(self, current: int, total: int, text: str = ""):
        """Update progress bar and text."""
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
        
        if text:
            self.status_label.setText(text)
        else:
            self.status_label.setText(f"Processing {current} of {total}...")
        
        self.progress_bar.setFormat(f"{current}/{total}")
    
    def cancel(self):
        """Mark as cancelled."""
        self.cancelled = True
        self.status_label.setText("Cancelling...")
        self.cancel_btn.setEnabled(False)

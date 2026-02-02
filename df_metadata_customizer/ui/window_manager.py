"""Window management, lifecycle, and preferences."""

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QCheckBox, QDoubleSpinBox, QPushButton, QScrollArea, 
    QFrame, QInputDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont

from df_metadata_customizer.core import SettingsManager

logger = logging.getLogger(__name__)


class WindowManager:
    """Manages window lifecycle, preferences, and theme."""
    
    def __init__(self, window):
        self.window = window
    
    def center_window(self):
        """Center window on screen."""
        screen = self.window.screen().geometry()
        x = (screen.width() - self.window.width()) // 2
        y = (screen.height() - self.window.height()) // 2
        self.window.move(x, y)
    
    def apply_theme_from_system(self):
        """Apply theme based on system settings."""
        theme = SettingsManager.get_theme("System")
        self.window.current_theme = theme
        self.window._apply_theme()
    
    def apply_ui_scale(self):
        """Apply UI scale factor from settings."""
        scale = SettingsManager.get_ui_scale(1.0)
        self.window._apply_ui_scale()
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.information(
            self.window,
            "About Database Formatter",
            "Database Formatter v2.0\n"
            "MP3 Metadata Customizer\n\n"
            "Organize, manage, and customize metadata for your music library."
        )
    
    def show_preferences(self):
        """Show preferences dialog."""
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Preferences")
        dialog.setMinimumWidth(500)
        dialog.setStyleSheet("""
            QDialog { background-color: #2b2b2b; }
            QLabel { color: #ffffff; }
            QComboBox { background-color: #1e1e1e; color: #ffffff; border: 1px solid #3d3d3d; }
            QPushButton { background-color: #0d47a1; color: white; border: none; padding: 6px 12px; }
            QPushButton:hover { background-color: #1565c0; }
        """)
        
        layout = QVBoxLayout(dialog)
        
        # Theme preference
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        theme_combo = QComboBox()
        theme_combo.addItems(["Light", "Dark", "System"])
        current_theme = SettingsManager.get_theme("System")
        theme_combo.setCurrentText(current_theme)
        theme_layout.addWidget(theme_combo)
        layout.addLayout(theme_layout)
        
        # UI Scale
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("UI Scale:"))
        scale_spin = QDoubleSpinBox()
        scale_spin.setRange(0.8, 2.0)
        scale_spin.setSingleStep(0.1)
        scale_spin.setValue(SettingsManager.get_ui_scale(1.0))
        scale_layout.addWidget(scale_spin)
        layout.addLayout(scale_layout)
        
        # Auto reopen last folder
        auto_reopen = QCheckBox("Reopen last folder on startup")
        auto_reopen.setChecked(SettingsManager.get_auto_reopen_folder(True))
        layout.addWidget(auto_reopen)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        reset_btn = QPushButton("Reset All Settings")
        
        save_btn.clicked.connect(lambda: self._save_preferences(
            dialog, auto_reopen.isChecked(), 
            theme_combo.currentText(), scale_spin.value()
        ))
        cancel_btn.clicked.connect(dialog.reject)
        reset_btn.clicked.connect(lambda: self._reset_all_settings(dialog))
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(reset_btn)
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def _save_preferences(self, dialog, auto_reopen: bool, theme: str, ui_scale: float):
        """Save preferences."""
        SettingsManager.set_theme(theme)
        SettingsManager.set_ui_scale(ui_scale)
        SettingsManager.set_auto_reopen_folder(auto_reopen)
        self.window.current_theme = theme
        self.window._apply_theme()
        self.window._apply_ui_scale()
        dialog.accept()
    
    def _reset_all_settings(self, dialog):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            dialog,
            "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            SettingsManager.clear_all()
            dialog.accept()
            QMessageBox.information(dialog, "Success", "Settings reset. Please restart the application.")
    
    def save_settings(self):
        """Save current window settings."""
        try:
            SettingsManager.set_window_geometry(self.window.geometry())
            SettingsManager.set_window_state(self.window.windowState())
            if hasattr(self.window, 'main_splitter'):
                SettingsManager.set_splitter_sizes(self.window.main_splitter.sizes())
            if hasattr(self.window, 'current_folder') and self.window.current_folder:
                SettingsManager.set_last_folder(self.window.current_folder)
        except Exception as e:
            logger.debug(f"Error saving settings: {e}")
    
    def load_settings(self):
        """Load saved window settings."""
        try:
            geometry = SettingsManager.get_window_geometry()
            if geometry:
                self.window.restoreGeometry(geometry)
            
            state = SettingsManager.get_window_state()
            if state:
                self.window.restoreState(state)
            
            sizes = SettingsManager.get_splitter_sizes()
            if sizes and hasattr(self.window, 'main_splitter'):
                self.window.main_splitter.setSizes(sizes)
        except Exception as e:
            logger.debug(f"Error loading settings: {e}")
    
    def closeEvent(self):
        """Handle window close event."""
        self.save_settings()

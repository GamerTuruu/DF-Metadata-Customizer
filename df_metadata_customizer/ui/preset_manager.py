"""Preset management component for handling preset operations."""

import json
import logging
from pathlib import Path
from typing import Callable
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt

from df_metadata_customizer.core import SettingsManager, PresetService
from df_metadata_customizer.core.preset_service import Preset
from df_metadata_customizer.core.song_utils import write_id3_tags
from df_metadata_customizer.ui.rule_widgets import NoScrollComboBox

logger = logging.getLogger(__name__)


class PresetManager:
    """Manages preset operations: load, save, create, delete, and apply."""
    
    def __init__(self, parent, preset_service: PresetService):
        self.parent = parent
        self.preset_service = preset_service
        self.preset_combo = None
    
    def create_preset_controls(self) -> tuple:
        """Create preset controls panel."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        label = QLabel("Preset:")
        label.setFixedWidth(65)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        self.preset_combo = NoScrollComboBox()
        self.preset_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        self.preset_combo.currentTextChanged.connect(self.on_preset_selected)
        layout.addWidget(self.preset_combo)
        
        new_btn = QPushButton("New")
        new_btn.setFixedSize(80, 32)
        new_btn.clicked.connect(self.create_new_preset)
        layout.addWidget(new_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.setFixedSize(80, 32)
        delete_btn.clicked.connect(self.delete_preset)
        layout.addWidget(delete_btn)
        
        save_btn = QPushButton("Save")
        save_btn.setFixedSize(80, 32)
        save_btn.clicked.connect(self.save_preset)
        layout.addWidget(save_btn)
        
        return frame, self.preset_combo
    
    def load_presets(self):
        """Load available presets into combo box."""
        try:
            presets = self.preset_service.list_presets()
            if presets:
                self.preset_combo.addItems(presets)
            else:
                self.preset_combo.addItems(["Default", "TuruuMGL", "mm2wood"])
        except Exception as e:
            logger.warning(f"Error loading presets: {e}")
            self.preset_combo.addItems(["Default", "TuruuMGL", "mm2wood"])
    
    def on_preset_selected(self):
        """Handle preset selection and load rules into tabs."""
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            return
        
        try:
            preset_file = SettingsManager.get_presets_folder() / f"{preset_name}.json"
            
            if not preset_file.exists():
                QMessageBox.warning(self.parent, "Error", f"Preset file '{preset_name}' not found")
                return
            
            with preset_file.open("r", encoding="utf-8") as f:
                preset_data = json.load(f)
            
            # Display in JSON editor
            if hasattr(self.parent, 'json_editor'):
                self.parent.json_editor.setText(json.dumps(preset_data, indent=2))
            
            # Load rules into respective tabs
            for tab_name in ["title", "artist", "album"]:
                rules = preset_data.get(tab_name, [])
                if hasattr(self.parent, 'rules_panel_manager'):
                    self.parent.rules_panel_manager.load_rules_to_tab(tab_name, rules)
                else:
                    self.parent.load_rules_to_tab(tab_name, rules)
            
            # Update preview
            if hasattr(self.parent, 'rules_panel_manager'):
                self.parent.rules_panel_manager.update_output_preview()
            elif hasattr(self.parent, 'update_output_preview'):
                self.parent.update_output_preview()
            
            if hasattr(self.parent, 'file_info_label'):
                self.parent.file_info_label.setText(f"Loaded preset '{preset_name}'")
        except Exception as e:
            logger.exception(f"Error loading preset: {e}")
            QMessageBox.warning(self.parent, "Error", f"Failed to load preset: {e}")
    
    def create_new_preset(self):
        """Create new preset."""
        name, ok = QInputDialog.getText(self.parent, "New Preset", "Preset name:")
        if ok and name:
            try:
                new_preset = Preset(name=name, description="")
                self.preset_service.save_preset(new_preset)
                self.preset_combo.addItem(name)
                QMessageBox.information(self.parent, "Success", f"Preset '{name}' created!")
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", f"Failed to create preset:\n{e}")
    
    def delete_preset(self):
        """Delete preset."""
        name = self.preset_combo.currentText()
        
        if name in ["Default", "TuruuMGL", "mm2wood"]:
            QMessageBox.warning(self.parent, "Warning", "Cannot delete built-in presets.")
            return
        
        reply = QMessageBox.question(self.parent, "Delete Preset", f"Delete preset '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.preset_service.delete_preset(name)
                idx = self.preset_combo.currentIndex()
                self.preset_combo.removeItem(idx)
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", f"Failed to delete preset:\n{e}")
    
    def save_preset(self):
        """Save current rules as preset."""
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            QMessageBox.warning(self.parent, "Warning", "Please select or create a preset first.")
            return
        
        try:
            # Collect rules from all tabs
            if hasattr(self.parent, 'rules_panel_manager'):
                preset_data = {
                    "title": self.parent.rules_panel_manager.collect_rules_for_tab("title"),
                    "artist": self.parent.rules_panel_manager.collect_rules_for_tab("artist"),
                    "album": self.parent.rules_panel_manager.collect_rules_for_tab("album"),
                }
            else:
                preset_data = {
                    "title": self.parent.collect_rules_for_tab("title"),
                    "artist": self.parent.collect_rules_for_tab("artist"),
                    "album": self.parent.collect_rules_for_tab("album"),
                }
            
            # Save preset file
            preset_file = SettingsManager.get_presets_folder() / f"{preset_name}.json"
            with preset_file.open("w", encoding="utf-8") as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)
            
            # Update JSON editor
            if hasattr(self.parent, 'json_editor'):
                self.parent.json_editor.setText(json.dumps(preset_data, indent=2))
            
            QMessageBox.information(self.parent, "Success", f"Preset '{preset_name}' saved!")
            if hasattr(self.parent, 'file_info_label'):
                self.parent.file_info_label.setText(f"Saved preset '{preset_name}'")
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", f"Failed to save preset:\n{e}")
            logger.exception("Error saving preset")
    
    def apply_preset_to_selected(self):
        """Apply preset to selected files."""
        selected = self.parent.tree.selectedItems()
        if not selected:
            QMessageBox.warning(self.parent, "Warning", "No files selected.")
            return
        
        preset_name = self.preset_combo.currentText()
        
        reply = QMessageBox.question(self.parent, "Apply Preset",
            f"Apply preset '{preset_name}' to {len(selected)} file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                indices = []
                for item in selected:
                    idx = item.data(0, Qt.ItemDataRole.UserRole)
                    if idx is not None:
                        indices.append(idx)
                
                applied = 0
                for idx in indices:
                    if idx < len(self.parent.song_files):
                        file_data = self.parent.song_files[idx]
                        file_path = file_data.get("path", "")
                        raw_json = file_data.get("raw_json", {}) or {}
                        updated_json = self.parent._apply_rules_to_metadata(raw_json)
                        id3_payload = self.parent._build_id3_metadata(raw_json, file_path, updated_json)
                        if file_path and write_id3_tags(file_path, id3_payload):
                            applied += 1

                # Refresh the folder to reload file data
                self.parent.refresh_current_folder()

                QMessageBox.information(self.parent, "Success",
                    f"Applied preset '{preset_name}' to {applied} file(s)!")
                
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", f"Failed to apply preset:\n{e}")
    
    def apply_preset_to_all(self):
        """Apply preset to all files."""
        if not self.parent.song_files:
            QMessageBox.warning(self.parent, "Warning", "No files loaded.")
            return
        
        preset_name = self.preset_combo.currentText()
        reply = QMessageBox.question(self.parent, "Apply Preset",
            f"Apply preset '{preset_name}' to ALL {len(self.parent.song_files)} files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                applied = 0
                for idx in range(len(self.parent.song_files)):
                    file_data = self.parent.song_files[idx]
                    file_path = file_data.get("path", "")
                    raw_json = file_data.get("raw_json", {}) or {}
                    updated_json = self.parent._apply_rules_to_metadata(raw_json)
                    id3_payload = self.parent._build_id3_metadata(raw_json, file_path, updated_json)
                    if file_path and write_id3_tags(file_path, id3_payload):
                        applied += 1

                # Refresh the folder to reload file data
                self.parent.refresh_current_folder()

                QMessageBox.information(self.parent, "Success",
                    f"Applied preset '{preset_name}' to {applied} file(s)!")
                
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", f"Failed to apply preset:\n{e}")

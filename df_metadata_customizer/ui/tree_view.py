"""Tree view component for displaying song metadata."""

import json
import logging
from pathlib import Path
from typing import List, Callable
from PyQt6.QtWidgets import (
    QTreeWidget, QMenu, QMessageBox, QApplication, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

from df_metadata_customizer.core import SettingsManager
from df_metadata_customizer.ui.platform_utils import open_file_with_default_app, open_folder_with_file_manager

logger = logging.getLogger(__name__)


class TreeViewManager:
    """Manages the tree view for song metadata display."""
    
    def __init__(self, parent, tree_columns: List, song_files: List):
        self.parent = parent
        self.tree_columns = tree_columns
        # Note: Don't store song_files reference, always access parent.song_files
        self.tree = None
    
    def create_tree_view(self) -> QTreeWidget:
        """Create tree view with all metadata columns."""
        tree = QTreeWidget()
        
        # Set columns
        col_labels = []
        for f in self.tree_columns:
            if hasattr(f, 'value'):
                col_labels.append(f.value)
            else:
                col_labels.append(str(f))
        
        tree.setColumnCount(len(col_labels))
        tree.setHeaderLabels(col_labels)
        
        # Remove tree indentation (left gap in first column)
        tree.setIndentation(0)
        
        # Enable column reordering
        header = tree.header()
        header.setSectionsMovable(True)
        header.setFirstSectionMovable(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.sectionMoved.connect(self.on_column_moved)
        
        # Set column widths
        widths = [150, 120, 100, 70, 80, 50, 50, 150, 80]
        for i, w in enumerate(widths[:len(col_labels)]):
            tree.setColumnWidth(i, w)
        
        # Selection mode
        tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        tree.itemDoubleClicked.connect(self.on_tree_item_double_clicked)
        tree.itemClicked.connect(self.on_tree_item_clicked)
        
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(self.on_tree_right_click)
        
        # Connect currentItemChanged for keyboard navigation
        tree.currentItemChanged.connect(self.on_tree_current_item_changed)
        
        tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                gridline-color: #3d3d3d;
            }
            QTreeWidget::item {
                border-right: 1px solid #3d3d3d;
                padding: 2px;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #2d2d2d;
            }
            QTreeWidget::item:selected {
                background-color: #0d47a1;
            }
            QTreeWidget::item:selected:hover {
                background-color: #1565c0;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 4px;
                border: none;
                border-right: 1px solid #555555;
                border-bottom: 1px solid #555555;
            }
        """)
        
        tree.itemSelectionChanged.connect(self.parent.on_tree_selection_changed)
        self.tree = tree
        return tree
    
    def on_column_moved(self, logicalIndex, oldVisualIndex, newVisualIndex):
        """Save column order when user reorders columns."""
        try:
            header = self.tree.header()
            order = [header.visualIndex(i) for i in range(header.count())]
            SettingsManager.column_order = order
        except Exception as e:
            logger.debug(f"Error saving column order: {e}")
    
    def on_tree_current_item_changed(self, current, previous):
        """Handle current item change (keyboard navigation)."""
        if current:
            self.parent.current_selected_file = current.data(0, Qt.ItemDataRole.UserRole)
            self.parent.current_index = self.tree.indexOfTopLevelItem(current)
            self.parent.update_preview_info()
    
    def on_tree_item_clicked(self, item, column):
        """Handle tree item click - show info for clicked item."""
        # Don't clear selection - let Qt handle multi-select (Ctrl/Shift)
        self.parent.current_selected_file = item.data(0, Qt.ItemDataRole.UserRole)
        self.parent.current_index = self.tree.indexOfTopLevelItem(item)
        self.parent.update_preview_info()
    
    def on_tree_item_double_clicked(self, item, column):
        """Handle tree item double-click - play the file."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.parent.song_files):
            file_path = self.parent.song_files[idx].get('path', '')
            if file_path:
                try:
                    open_file_with_default_app(file_path)
                except Exception as e:
                    QMessageBox.warning(self.parent, "Error", f"Cannot open file: {e}")
    
    def on_tree_right_click(self, position):
        """Show context menu on right-click."""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self.parent)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QMenu::item:selected {
                background-color: #0d47a1;
            }
        """)
        
        # Play
        action = menu.addAction("▶️ Play")
        action.triggered.connect(lambda: self.play_file(item))

        if hasattr(self.parent, "is_song_edit_active") and self.parent.is_song_edit_active():
            action = menu.addAction("➕ Copy as New Song")
            action.triggered.connect(lambda: self.copy_as_new_song(item))
        
        menu.addSeparator()
        
        # Copy field value from clicked column
        column = self.tree.columnAt(position.x())
        if 0 <= column < len(self.tree_columns):
            field_name = self.tree_columns[column]
            field_display = field_name.replace('_', ' ').title()
            action = menu.addAction(f"📋 Copy {field_display}")
            action.triggered.connect(lambda: self.copy_field_value(item, column))
        
        menu.addSeparator()
        
        # Go to file location
        action = menu.addAction("Go to File Location")
        action.triggered.connect(lambda: self.goto_file_location(item))
        
        menu.exec(QCursor.pos())
    
    def play_file(self, item):
        """Play file."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.parent.song_files):
            file_path = self.parent.song_files[idx].get('path', '')
            if file_path:
                try:
                    open_file_with_default_app(file_path)
                except Exception as e:
                    QMessageBox.warning(self.parent, "Error", f"Cannot play file: {e}")
    
    def copy_metadata(self, item):
        """Copy song metadata to clipboard."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.parent.song_files):
            file_data = self.parent.song_files[idx]
            metadata_text = json.dumps(file_data, indent=2)
            
            app = QApplication.instance()
            clipboard = app.clipboard()
            clipboard.setText(metadata_text)
            
            QMessageBox.information(self.parent, "Success", "Metadata copied to clipboard!")
    
    def copy_field_value(self, item, column):
        """Copy single field value to clipboard."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.parent.song_files):
            file_data = self.parent.song_files[idx]
            field_name = self.tree_columns[column]
            value = file_data.get(field_name, '')
            
            app = QApplication.instance()
            clipboard = app.clipboard()
            clipboard.setText(str(value))
            
            field_display = field_name.replace('_', ' ').title()
            QMessageBox.information(self.parent, "Success", f"{field_display} copied to clipboard!")
    
    def copy_all_metadata(self, items):
        """Copy all selected metadata."""
        all_data = []
        for item in items:
            idx = item.data(0, Qt.ItemDataRole.UserRole)
            if idx is not None and idx < len(self.parent.song_files):
                all_data.append(self.parent.song_files[idx])
        
        metadata_text = json.dumps(all_data, indent=2)
        
        app = QApplication.instance()
        clipboard = app.clipboard()
        clipboard.setText(metadata_text)
        
        QMessageBox.information(self.parent, "Success", f"Metadata for {len(items)} songs copied!")
    
    def goto_file_location(self, item):
        """Open file location in file manager and select the file."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.parent.song_files):
            file_path = self.parent.song_files[idx].get('path', '')
            if file_path:
                try:
                    open_folder_with_file_manager(str(Path(file_path).parent), file_path)
                except Exception as e:
                    QMessageBox.warning(self.parent, "Error", f"Cannot open folder: {e}")

    def copy_as_new_song(self, item):
        """Copy selected song into Song Edit tab for adding as new song."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self.parent.song_files):
            return
        file_data = self.parent.song_files[idx]
        if hasattr(self.parent, "song_editor_manager"):
            self.parent.song_editor_manager.copy_as_new_song(file_data)
        if hasattr(self.parent, "tabs") and self.parent.tabs is not None:
            for i in range(self.parent.tabs.count()):
                if self.parent.tabs.tabText(i) == "Song Edit":
                    self.parent.tabs.setCurrentIndex(i)
                    break

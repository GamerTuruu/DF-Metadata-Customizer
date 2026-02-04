"""Tree view component for displaying song metadata."""

import json
import logging
from pathlib import Path
from typing import List, Callable
from PySide6.QtWidgets import (
    QTreeWidget, QMenu, QMessageBox, QApplication, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

from df_metadata_customizer.core import SettingsManager
from df_metadata_customizer.ui.platform_utils import (
    open_file_with_default_app, 
    open_folder_with_file_manager,
    open_file_with_player,
    get_available_players
)

logger = logging.getLogger(__name__)


class TreeViewManager:
    """Manages the tree view for song metadata display."""
    
    def __init__(self, parent, tree_columns: List, song_files: List):
        self.parent = parent
        self.tree_columns = tree_columns
        # Note: Don't store song_files reference, always access parent.song_files
        self.tree = None
        self._active_menu = None  # Track active context menu
    
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
        widths = [250, 250, 130, 40, 110, 20, 85, 20, 350]
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
        
        # Stylesheet will be set by update_tree_stylesheet
        
        tree.itemSelectionChanged.connect(self.parent.on_tree_selection_changed)
        self.tree = tree
        return tree
    
    def update_tree_stylesheet(self, theme_colors: dict):
        """Update tree stylesheet with current theme colors - VS Code Modern themes."""
        if self.tree:
            c = theme_colors
            is_dark = c.get('bg_primary', '#1e1e1e') == '#1e1e1e'
            
            if is_dark:
                # VS Code Dark Modern
                hover_color = '#2a2d2e'      # Subtle hover
                header_bg = '#252526'         # Sidebar color
                border_light = '#454545'
            else:
                # VS Code Light Modern
                hover_color = '#f0f0f0'       # Light hover
                header_bg = '#f3f3f3'         # Sidebar color
                border_light = '#d4d4d4'

            selection_hover = c.get('selection_hover', c['selection'])
            
            self.tree.setStyleSheet(f"""
                QTreeWidget {{
                    background-color: {c['bg_primary']};
                    color: {c['text']};
                    border: 1px solid {c['border']};
                    border-radius: 4px;
                    gridline-color: {c['border']};
                }}
                QTreeWidget::item {{
                    border-right: 1px solid {c['border']};
                    padding: 2px;
                }}
                QTreeWidget::item:hover:!selected {{
                    background-color: {hover_color};
                }}
                QTreeWidget::item:selected {{
                    background-color: {c['button']};
                    color: #ffffff;
                }}
                QTreeWidget::item:selected:hover {{
                    background-color: {selection_hover};
                }}
                QHeaderView::section {{
                    background-color: {header_bg};
                    color: {c['text']};
                    padding: 4px;
                    border: none;
                    border-right: 1px solid {border_light};
                    border-bottom: 1px solid {border_light};
                }}
            """)
    
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
            # Only update preview if not currently sorting
            if not getattr(self.parent, '_is_sorting', False):
                self.parent.update_preview_info()
    
    def on_tree_item_clicked(self, item, column):
        """Handle tree item click - show info for clicked item."""
        # Don't clear selection - let Qt handle multi-select (Ctrl/Shift)
        self.parent.current_selected_file = item.data(0, Qt.ItemDataRole.UserRole)
        self.parent.current_index = self.tree.indexOfTopLevelItem(item)
        # Only update preview if not currently sorting
        if not getattr(self.parent, '_is_sorting', False):
            self.parent.update_preview_info()
    
    def on_tree_item_double_clicked(self, item, column):
        """Handle tree item double-click - play the file."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.parent.song_files):
            file_path = self.parent.song_files[idx].get('path', '')
            if file_path:
                try:
                    # Use default_player if set, otherwise use system default
                    if SettingsManager.default_player:
                        open_file_with_player(file_path, SettingsManager.default_player)
                    else:
                        open_file_with_default_app(file_path)
                except Exception as e:
                    QMessageBox.warning(self.parent, "Error", f"Cannot open file: {e}")
    
    def on_tree_right_click(self, position):
        """Show context menu on right-click."""
        # Close any existing menu first
        if self._active_menu:
            self._active_menu.close()
            self._active_menu = None
        
        item = self.tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self.parent)
        self._active_menu = menu
        c = getattr(self.parent, "theme_colors", None) or {}
        is_dark = SettingsManager.theme == "dark"
        menu_bg = c.get("bg_primary", "#1e1e1e" if is_dark else "#ffffff")
        menu_text = c.get("text", "#cccccc" if is_dark else "#3b3b3b")
        menu_border = c.get("border", "#454545" if is_dark else "#e5e5e5")
        menu_accent = c.get("button", "#0e639c" if is_dark else "#007acc")
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {menu_bg};
                color: {menu_text};
                border: 1px solid {menu_border};
            }}
            QMenu::item:selected {{
                background-color: {menu_accent};
                color: #ffffff;
            }}
        """)
        
        # Play (with system default)
        action = menu.addAction("▶️ Play")
        action.triggered.connect(lambda: self.play_file(item))
        
        # Play With (submenu with available players)
        available_players = get_available_players()
        if available_players or SettingsManager.default_player:
            play_with_menu = menu.addMenu("▶️ Play With")
            
            # Check if default player is in available list
            available_paths = [p[1] for p in available_players]
            has_custom_default = (
                SettingsManager.default_player and 
                SettingsManager.default_player not in available_paths
            )
            
            # Add custom player at top if it's the default and not in list
            if has_custom_default:
                player_name = Path(SettingsManager.default_player).name
                player_submenu = play_with_menu.addMenu(f"✓ {player_name} (Custom)")
                
                # Play action
                action = player_submenu.addAction("▶️ Play")
                action.triggered.connect(
                    lambda checked=False, p=SettingsManager.default_player: 
                    self.play_file_with_player(item, p)
                )
                
                # Set as default action (already is default)
                action = player_submenu.addAction("⭐ Set as Default")
                action.setEnabled(False)  # Already default
                
                play_with_menu.addSeparator()
            
            for player_name, player_path in available_players:
                # Create submenu for each player with options
                player_submenu = play_with_menu.addMenu(player_name)
                
                # Add checkmark if this is the default player
                if SettingsManager.default_player == player_path:
                    player_submenu.setTitle(f"✓ {player_name}")
                
                # Play action
                action = player_submenu.addAction("▶️ Play")
                action.triggered.connect(lambda checked=False, p=player_path: self.play_file_with_player(item, p))
                
                # Set as default action
                action = player_submenu.addAction("⭐ Set as Default")
                action.triggered.connect(lambda checked=False, p=player_path: self._set_default_player(p))
            
            play_with_menu.addSeparator()
            action = play_with_menu.addAction("Custom Player...")
            action.triggered.connect(lambda: self.play_file_with_custom_player(item))

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
        """Play file with system default application."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.parent.song_files):
            file_path = self.parent.song_files[idx].get('path', '')
            if file_path:
                try:
                    open_file_with_default_app(file_path)
                except Exception as e:
                    QMessageBox.warning(self.parent, "Error", f"Cannot play file: {e}")
    
    def play_file_with_player(self, item, player_path):
        """Play file with specified player."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.parent.song_files):
            file_path = self.parent.song_files[idx].get('path', '')
            if file_path:
                try:
                    open_file_with_player(file_path, player_path)
                except Exception as e:
                    QMessageBox.warning(self.parent, "Error", f"Cannot play file: {e}")
    
    def play_file_with_custom_player(self, item):
        """Play file with custom player path entered by user."""
        from PySide6.QtWidgets import QInputDialog, QFileDialog
        import platform
        
        # Ask if user wants to browse or enter path manually
        choice, ok = QInputDialog.getItem(
            self.parent,
            "Select Input Method",
            "How would you like to specify the player?",
            ["Browse for executable...", "Enter path or command manually..."],
            0,
            False
        )
        
        player_path = None
        
        if ok and choice:
            if choice == "Browse for executable...":
                # Open file browser
                if platform.system() == "Windows":
                    file_filter = "Executable Files (*.exe);;All Files (*.*)"
                else:
                    file_filter = "All Files (*)"
                
                player_path, _ = QFileDialog.getOpenFileName(
                    self.parent,
                    "Select Media Player",
                    "",
                    file_filter
                )
            else:
                # Manual input
                player_path, ok2 = QInputDialog.getText(
                    self.parent,
                    "Custom Player",
                    "Enter player path or command:",
                    text=SettingsManager.default_player or ""
                )
                if not ok2:
                    return
        else:
            return
        
        if player_path:
            try:
                idx = item.data(0, Qt.ItemDataRole.UserRole)
                if idx is not None and idx < len(self.parent.song_files):
                    file_path = self.parent.song_files[idx].get('path', '')
                    if file_path:
                        open_file_with_player(file_path, player_path)
                        # Ask if user wants to set as default
                        reply = QMessageBox.question(
                            self.parent,
                            "Set as Default Player?",
                            f"Do you want to set this as your default player?\n\nPlayer: {player_path}",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.Yes
                        )
                        if reply == QMessageBox.StandardButton.Yes:
                            SettingsManager.default_player = player_path
                            SettingsManager.save_settings()
            except Exception as e:
                QMessageBox.warning(self.parent, "Error", f"Cannot play file: {e}")
    
    def _set_default_player(self, player_path: str) -> None:
        """Set the specified player as the default player."""
        SettingsManager.default_player = player_path
        SettingsManager.save_settings()
        # Show a brief notification
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self.parent,
            "Default Player Set",
            f"Default player has been set successfully.",
            QMessageBox.StandardButton.Ok
        )
    
    
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

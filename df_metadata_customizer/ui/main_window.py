"""PyQt6 Main Window - COMPLETE with ALL fixes and features."""

import sys
import json
import logging
import contextlib
from pathlib import Path
from typing import Optional, Any, Dict, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton,
    QLabel, QFrame, QScrollArea, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QComboBox, QTabWidget, QApplication, QHeaderView, QInputDialog,
    QTextEdit, QMenu, QAbstractItemView, QDialog, QCheckBox, QDoubleSpinBox, QStackedLayout
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont

from df_metadata_customizer.core import FileManager, SettingsManager, PresetService, RuleManager
from df_metadata_customizer.core.metadata import MetadataFields
from df_metadata_customizer.core.song_utils import write_json_to_song
from df_metadata_customizer.ui.progress_dialog import ProgressDialog
from df_metadata_customizer.ui.menu_bar import setup_menubar
from df_metadata_customizer.ui.song_controls import create_song_controls
from df_metadata_customizer.ui.status_bar import create_status_bar
from df_metadata_customizer.ui.sort_controls import SortControlsManager
from df_metadata_customizer.ui.tree_view import TreeViewManager
from df_metadata_customizer.ui.preset_manager import PresetManager
from df_metadata_customizer.ui.rules_panel import RulesPanelManager
from df_metadata_customizer.ui.song_editor import SongEditorManager
from df_metadata_customizer.ui.cover_manager import CoverManager
from df_metadata_customizer.ui.preview_panel import PreviewPanelManager
from df_metadata_customizer.ui.search_handler import SearchHandler
from df_metadata_customizer.ui.sort_handler import SortHandler
from df_metadata_customizer.ui.rule_applier import RuleApplier

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Complete PyQt6 main window with ALL features."""

    RULE_OPS = [
        "is", "contains", "starts with", "ends with",
        "is empty", "is not empty", "is latest version", "is not latest version"
    ]

    TREE_COLUMNS = [
        MetadataFields.TITLE,
        MetadataFields.ARTIST,
        MetadataFields.COVER_ARTIST,
        MetadataFields.VERSION,
        MetadataFields.DATE,
        MetadataFields.DISC,
        MetadataFields.TRACK,
        MetadataFields.FILE,
        MetadataFields.SPECIAL,
    ]

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DF Metadata Customizer")
        self.resize(1400, 900)

        SettingsManager.initialize()
        self.file_manager = FileManager()
        self.preset_service = PresetService(SettingsManager.get_presets_folder())
        self.rule_manager = RuleManager()

        self.song_files: List[Dict] = []
        self.current_index = None
        self.current_folder = None
        self.filtered_indices: List[int] = []
        self.current_theme = "System"
        self.sort_rules: List[tuple] = [("Title", True)]
        self.current_selected_file = None
        self.all_selected = False

        self.tree = None
        self.search_input = None
        self.sort_controls_manager = SortControlsManager(self, self.on_sort_changed)
        self.tree_view_manager = None
        self.preset_manager = PresetManager(self, self.preset_service)
        self.rules_panel_manager = RulesPanelManager(self, self.preset_manager)
        self.song_editor_manager = SongEditorManager(self, self.preset_service)
        self.cover_manager = CoverManager(self)
        self.preview_panel_manager = PreviewPanelManager(self)
        self.search_handler = SearchHandler(self)
        self.sort_handler = SortHandler(self, self.sort_controls_manager)
        self.rule_applier = RuleApplier(self)

        self.preset_combo = None
        self.file_info_label = None
        self.selection_info_label = None
        self.json_editor = None
        self.output_preview = None
        self.filename_preview = None
        self.rules_info = None
        self.cover_display = None
        self.save_json_btn = None
        self.save_filename_btn = None
        self.preview_title_label = None
        self.preview_artist_label = None
        self.preview_album_label = None
        self.preview_details_label = None
        self.preview_versions_label = None
        self.original_filename = ""
        self.metadata_fields = {}
        self.rule_containers = {}
        self.max_rules_per_tab = 50
        self._last_ui_scale = 1.0

        self._setup_ui()

        self.preset_manager.load_presets()
        self._apply_theme_from_system()
        self._apply_ui_scale()

        with contextlib.suppress(Exception):
            self.load_settings()

        self.show()
        with contextlib.suppress(Exception):
            self.check_last_folder()

    def _setup_ui(self):
        """Setup the main UI layout."""
        setup_menubar(self, self.menuBar())

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(6)
        self.main_splitter.setStyleSheet("QSplitter::handle { background-color: #3d3d3d; }")

        left_frame = self._create_left_frame()
        right_frame = self._create_right_frame()

        self.main_splitter.addWidget(left_frame)
        self.main_splitter.addWidget(right_frame)
        self.main_splitter.setSizes([800, 600])

        layout.addWidget(self.main_splitter)

    def _create_left_frame(self):
        """Create left frame with song list and controls."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #2b2b2b; border-radius: 8px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        song_controls_frame, song_controls_refs = create_song_controls(self)
        self.search_input = song_controls_refs['search_input']
        self.filtered_count_label = song_controls_refs['filtered_count_label']
        layout.addWidget(song_controls_frame)

        sort_controls = self.sort_controls_manager.create_sort_controls()
        layout.addWidget(sort_controls)

        self.tree_view_manager = TreeViewManager(self, self.TREE_COLUMNS, self.song_files)
        self.tree = self.tree_view_manager.create_tree_view()
        layout.addWidget(self.tree, 1)

        status_frame, status_refs = create_status_bar(self)
        self.file_info_label = status_refs['file_info_label']
        self.selection_info_label = status_refs['selection_info_label']
        layout.addWidget(status_frame)

        return frame

    def _create_right_frame(self):
        """Create right frame with tabs."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #2b2b2b; border-radius: 8px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        
        tabs = QTabWidget()
        self.tabs = tabs
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3d3d3d; }
            QTabBar::tab {
                background-color: #1e1e1e;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0d47a1;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3d3d3d;
            }
        """)
        
        # Rules tab
        rules_widget = self._create_rules_tab()
        tabs.addTab(rules_widget, "Rules + Presets")
        
        # Song Edit tab
        edit_widget = self._create_song_edit_tab()
        tabs.addTab(edit_widget, "Song Edit")
        
        layout.addWidget(tabs)
        return frame
    
    def _create_rules_tab(self):
        """Create rules and presets tab with rule builder."""
        return self.rules_panel_manager.create_rules_tab()
    
    
    def _create_song_edit_tab(self):
        """Create song metadata editor."""
        return self.song_editor_manager.create_song_edit_tab()

    def is_song_edit_active(self) -> bool:
        """Return True if Song Edit tab is active."""
        if not hasattr(self, "tabs") or self.tabs is None:
            return False
        return self.tabs.tabText(self.tabs.currentIndex()) == "Song Edit"
    
    def _apply_theme_from_system(self):
        """Apply theme based on user preference."""
        theme = (SettingsManager.theme or "dark").lower()
        self.current_theme = theme
        self._apply_theme(theme)
    
    def _apply_ui_scale(self):
        """Apply UI scale from settings (handled in main(), this is for tracking)."""
        self._last_ui_scale = SettingsManager.ui_scale
    
    def _apply_theme(self, theme: str = "dark"):
        """Apply theme."""
        if theme == "dark" or theme.lower() == "dark":
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(13, 71, 161))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
            self.setPalette(palette)
            self.setStyleSheet("")
            SettingsManager.theme = "dark"
        else:
            # Light theme with comprehensive styling
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(250, 250, 250))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
            palette.setColor(QPalette.ColorRole.Text, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(13, 71, 161))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Link, QColor(13, 71, 161))
            palette.setColor(QPalette.ColorRole.LinkVisited, QColor(106, 17, 203))
            palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(150, 150, 150))
            self.setPalette(palette)
            # Comprehensive stylesheet for light theme
            self.setStyleSheet("""
                QMainWindow, QDialog { background-color: #fafafa; }
                QFrame { background-color: #fafafa; border: none; }
                QLabel { color: #1e1e1e; background-color: transparent; }
                QLineEdit { background-color: #ffffff; color: #1e1e1e; border: 1px solid #d0d0d0; padding: 4px; border-radius: 3px; }
                QComboBox { background-color: #f0f0f0; color: #1e1e1e; border: 1px solid #d0d0d0; padding: 4px; border-radius: 3px; }
                QComboBox::drop-down { border: none; }
                QComboBox QAbstractItemView { background-color: #ffffff; color: #1e1e1e; selection-background-color: #0d47a1; }
                QPushButton { background-color: #f0f0f0; color: #1e1e1e; border: 1px solid #d0d0d0; padding: 6px; border-radius: 3px; }
                QPushButton:hover { background-color: #e0e0e0; }
                QPushButton:pressed { background-color: #d0d0d0; }
                QTreeWidget { background-color: #ffffff; color: #1e1e1e; border: 1px solid #d0d0d0; }
                QTreeWidget::item:selected { background-color: #0d47a1; color: #ffffff; }
                QTreeWidget::item:hover { background-color: #e8e8e8; }
                QTextEdit, QPlainTextEdit { background-color: #ffffff; color: #1e1e1e; border: 1px solid #d0d0d0; }
                QCheckBox { color: #1e1e1e; }
                QRadioButton { color: #1e1e1e; }
                QGroupBox { color: #1e1e1e; border: 1px solid #d0d0d0; border-radius: 4px; margin-top: 10px; padding-top: 10px; }
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }
                QMenuBar { background-color: #f0f0f0; color: #1e1e1e; }
                QMenuBar::item:selected { background-color: #0d47a1; color: #ffffff; }
                QMenu { background-color: #ffffff; color: #1e1e1e; border: 1px solid #d0d0d0; }
                QMenu::item:selected { background-color: #0d47a1; color: #ffffff; }
                QTabWidget::pane { border: 1px solid #d0d0d0; background-color: #fafafa; }
                QTabBar::tab { background-color: #e0e0e0; color: #1e1e1e; padding: 8px; border: 1px solid #d0d0d0; }
                QTabBar::tab:selected { background-color: #fafafa; border-bottom: none; }
            """)
            SettingsManager.theme = "light"
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        # Ctrl+F to focus search
        if event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.search_input.setFocus()
            self.search_input.selectAll()
            event.accept()
        # ESC to clear search
        elif event.key() == Qt.Key.Key_Escape:
            self.search_input.clear()
            self.search_input.clearFocus()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    # ===== FILE OPERATIONS =====
    
    def open_folder(self):
        """Open folder dialog."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with MP3s")
        if folder:
            self.load_folder(folder, show_dialogs=True)
    
    def refresh_current_folder(self, show_dialogs=False):
        """Refresh the current folder to reload all files."""
        if self.current_folder:
            self.load_folder(self.current_folder, show_dialogs=show_dialogs)
        else:
            QMessageBox.information(self, "No Folder", "No folder is currently loaded. Please select a folder first.")
    
    def load_folder(self, folder_path: str, show_dialogs=True):
        """Load files from folder.
        
        Args:
            folder_path: Path to folder to load
            show_dialogs: If True, show progress and success dialogs
        """
        try:
            # Show progress dialog only if requested
            progress = None
            if show_dialogs:
                progress = ProgressDialog("Loading Files", self)
                progress.show()
                QApplication.processEvents()
            
            self.file_manager.load_folder(folder_path)
            self.song_files = self.file_manager.get_all_files()
            self.current_folder = folder_path
            self.filtered_indices = list(range(len(self.song_files)))
            
            SettingsManager.last_folder_opened = folder_path
            
            # Apply sorting before populating tree
            self.on_sort_changed()
            
            if progress:
                progress.close()
            
            # Show result only if requested
            if show_dialogs:
                QMessageBox.information(
                    self, 
                    "Load Complete",
                    f"Successfully loaded {len(self.song_files)} files from:\n{folder_path}"
                )
            
            self.file_info_label.setText(f"✓ Loaded {len(self.song_files)} files")
            if show_dialogs:
                self.search_input.clear()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load folder:\n{e}")
            logger.exception("Error loading folder")
    
    def check_last_folder(self):
        """Auto-load last folder."""
        try:
            last_folder = getattr(SettingsManager, 'last_folder_opened', None)
            auto_reopen = getattr(SettingsManager, 'auto_reopen_last_folder', None)
            
            if not last_folder or not Path(last_folder).exists():
                return
            
            # First time - ask user to set preference
            if auto_reopen is None:
                reply = QMessageBox.question(
                    self, 
                    "Auto-Reopen Last Folder",
                    f"Do you want to automatically reopen the last folder on startup?\n\nLast folder: {last_folder}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                auto_reopen = reply == QMessageBox.StandardButton.Yes
                SettingsManager.auto_reopen_last_folder = auto_reopen
                SettingsManager.save_settings()
            
            # If auto-reopen enabled, load automatically
            if auto_reopen:
                self.load_folder(last_folder, show_dialogs=True)
            # If disabled, ask each time
            elif auto_reopen is False:
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Question)
                msg_box.setWindowTitle("Open Last Folder")
                msg_box.setText(f"Do you want to open the last folder?\n\n{last_folder}")
                
                yes_btn = msg_box.addButton("Yes", QMessageBox.ButtonRole.YesRole)
                no_btn = msg_box.addButton("No", QMessageBox.ButtonRole.NoRole)
                auto_btn = msg_box.addButton("Yes, and don't ask again", QMessageBox.ButtonRole.AcceptRole)
                
                msg_box.exec()
                clicked = msg_box.clickedButton()
                
                if clicked == yes_btn or clicked == auto_btn:
                    self.load_folder(last_folder, show_dialogs=True)
                
                # Enable auto-reopen if user clicked "don't ask again"
                if clicked == auto_btn:
                    SettingsManager.auto_reopen_last_folder = True
                    SettingsManager.save_settings()
                    
        except Exception as e:
            logger.debug(f"Error loading last folder: {e}")
    
    def populate_tree(self):
        """Populate tree with songs."""
        self.tree.clear()
        
        # Map tree columns to actual file data keys
        column_map = {
            0: "Title",           # Title
            1: "Artist",          # Artist
            2: "CoverArtist",     # Cover Artist
            3: "Version",         # Version
            4: "Date",            # Date
            5: "Discnumber",      # Disc
            6: "Track",           # Track
            7: "path",            # File
            8: "Special",         # Special
        }
        
        for idx in self.filtered_indices:
            if idx >= len(self.song_files):
                continue
            
            file_data = self.song_files[idx]
            item = QTreeWidgetItem(self.tree)
            
            # Set all columns
            for col_idx in range(9):
                key = column_map.get(col_idx, "")
                value = file_data.get(key, "")
                if value is None:
                    value = ""
                # Format version numbers - remove .0 for whole numbers
                if key == "Version" and value:
                    try:
                        ver = float(value)
                        if ver == int(ver):
                            value = str(int(ver))
                        else:
                            value = str(ver)
                    except:
                        pass
                # For File column, show only filename not full path
                if key == "path" and value:
                    value = Path(value).name
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 60:
                    value_str = value_str[:57] + "..."
                item.setText(col_idx, value_str)
                item.setTextAlignment(col_idx, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            item.setData(0, Qt.ItemDataRole.UserRole, idx)
        
        self.update_selection_info()
    
    def _extract_numeric_value(self, value_str: str) -> tuple:
        """Extract numeric value from string, returning (has_denominator, numeric_value).
        
        This allows sorting single-number tracks before multi-number tracks.
        Returns: (0, numeric_value) for "69", (1, numeric_value) for "69/100"
        """
        try:
            # Try direct conversion first (single number like "69")
            num = float(value_str)
            return (0, num)  # 0 = no denominator
        except ValueError:
            # Handle "number1/number2" format by taking the first number
            value_str = str(value_str).strip()
            if "/" in value_str:
                first_part = value_str.split("/")[0].strip()
                try:
                    num = float(first_part)
                    return (1, num)  # 1 = has denominator
                except ValueError:
                    return (2, float('nan'))  # 2 = error
            return (2, float('nan'))  # 2 = error
    
    def _get_numeric_value_for_search(self, value_str: str) -> float:
        """Extract just the numeric value for search comparisons (used in on_search_changed)."""
        try:
            # Try direct conversion first (single number like "69")
            return float(value_str)
        except ValueError:
            # Handle "number1/number2" format by taking the first number
            value_str = str(value_str).strip()
            if "/" in value_str:
                first_part = value_str.split("/")[0].strip()
                try:
                    return float(first_part)
                except ValueError:
                    return float('nan')
            return float('nan')
    
    def _parse_search_value(self, value_str: str) -> str:
        """Parse search value, handling quoted strings."""
        value_str = value_str.strip()
        # Remove quotes if present
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1].lower()
        return value_str.lower()

    def _is_latest_version_match(self, file_data: dict, want_latest: bool) -> bool:
        """Return True if file_data matches latest/not-latest version for its song ID."""
        song_id = file_data.get("song_id")
        if not song_id:
            title = file_data.get(MetadataFields.TITLE, "")
            artist = file_data.get(MetadataFields.ARTIST, "")
            cover_artist = file_data.get(MetadataFields.COVER_ARTIST, "")
            song_id = f"{title}|{artist}|{cover_artist}"

        version = file_data.get(MetadataFields.VERSION, 0)
        try:
            version = float(version)
        except (ValueError, TypeError):
            version = 0.0

        return self.file_manager.is_latest_version(song_id, version) == want_latest
    
    def on_search_changed(self):
        """Filter with advanced search."""
        query = self.search_input.text().strip()
        self.filtered_indices = []
        
        if not query:
            # No query, show all
            self.filtered_indices = list(range(len(self.song_files)))
        else:
            for i, file_data in enumerate(self.song_files):
                match = False
                
                # Check for advanced operators (order matters - check longer operators first)
                if "!=" in query:
                    # Not equal
                    parts = query.split("!=", 1)
                    if len(parts) == 2:
                        search_field = parts[0].strip().lower()
                        search_value = self._parse_search_value(parts[1])

                        if search_field == "version" and search_value in {"latest", "not latest", "not_latest", "notlatest"}:
                            want_latest = (search_value == "latest")
                            match = not self._is_latest_version_match(file_data, want_latest)
                        else:
                            for key, value in file_data.items():
                                if search_field in key.lower():
                                    if str(value).lower() != search_value:
                                        match = True
                                        break
                
                elif "==" in query:
                    # Exact match
                    parts = query.split("==", 1)
                    if len(parts) == 2:
                        search_field = parts[0].strip().lower()
                        search_value = self._parse_search_value(parts[1])

                        if search_field == "version" and search_value in {"latest", "not latest", "not_latest", "notlatest"}:
                            want_latest = (search_value == "latest")
                            match = self._is_latest_version_match(file_data, want_latest)
                        else:
                            for key, value in file_data.items():
                                if search_field in key.lower():
                                    if str(value).lower() == search_value:
                                        match = True
                                        break
                
                elif ">=" in query:
                    # Greater than or equal
                    parts = query.split(">=", 1)
                    if len(parts) == 2:
                        search_field, search_value = parts[0].strip().lower(), parts[1].strip()
                        for key, value in file_data.items():
                            if search_field in key.lower():
                                try:
                                    if self._get_numeric_value_for_search(str(value)) >= float(search_value):
                                        match = True
                                        break
                                except:
                                    pass
                
                elif "<=" in query:
                    # Less than or equal
                    parts = query.split("<=", 1)
                    if len(parts) == 2:
                        search_field, search_value = parts[0].strip().lower(), parts[1].strip()
                        for key, value in file_data.items():
                            if search_field in key.lower():
                                try:
                                    if self._get_numeric_value_for_search(str(value)) <= float(search_value):
                                        match = True
                                        break
                                except:
                                    pass
                
                elif ">" in query:
                    # Greater than
                    parts = query.split(">", 1)
                    if len(parts) == 2:
                        search_field, search_value = parts[0].strip().lower(), parts[1].strip()
                        for key, value in file_data.items():
                            if search_field in key.lower():
                                try:
                                    if self._get_numeric_value_for_search(str(value)) > float(search_value):
                                        match = True
                                        break
                                except:
                                    pass
                
                elif "<" in query:
                    # Less than
                    parts = query.split("<", 1)
                    if len(parts) == 2:
                        search_field, search_value = parts[0].strip().lower(), parts[1].strip()
                        for key, value in file_data.items():
                            if search_field in key.lower():
                                try:
                                    if self._get_numeric_value_for_search(str(value)) < float(search_value):
                                        match = True
                                        break
                                except:
                                    pass
                
                elif "=" in query:
                    # Contains match
                    parts = query.split("=", 1)
                    if len(parts) == 2:
                        search_field = parts[0].strip().lower()
                        search_value = self._parse_search_value(parts[1])

                        if search_field == "version" and search_value in {"latest", "not latest", "not_latest", "notlatest"}:
                            want_latest = (search_value == "latest")
                            match = self._is_latest_version_match(file_data, want_latest)
                        else:
                            for key, value in file_data.items():
                                if search_field in key.lower():
                                    if search_value in str(value).lower():
                                        match = True
                                        break
                
                else:
                    # Simple text search across multiple fields
                    query_lower = query.lower()
                    search_fields = ["Title", "Artist", "CoverArtist", "Special", "Version"]
                    
                    for field in search_fields:
                        if query_lower in str(file_data.get(field, "")).lower():
                            match = True
                            break
                
                if match:
                    self.filtered_indices.append(i)
        
        # Update filtered count label
        self.filtered_count_label.setText(f"{len(self.filtered_indices)} found")
        
        # Apply sorting after filtering
        self.on_sort_changed()
    
    def on_sort_changed(self):
        """Apply multi-level sorting."""
        self.sort_handler.apply_sort()
    
    def on_tree_selection_changed(self):
        """Handle selection changes."""
        self.update_selection_info()
    
    def update_selection_info(self):
        """Update selection info."""
        count = len(self.tree.selectedItems())
        self.selection_info_label.setText(f"{count} song(s) selected")
    
    def toggle_select_all(self):
        """Toggle select all."""
        if self.tree.topLevelItemCount() == 0:
            return
        
        # Check if all are selected
        all_selected = all(self.tree.topLevelItem(i).isSelected() 
                          for i in range(self.tree.topLevelItemCount()))
        
        # Toggle
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setSelected(not all_selected)
    
    def _apply_rules_to_metadata(self, metadata: dict) -> dict:
        """Apply current rule tabs to metadata and return updated dict."""
        return self.rule_applier.apply_rules_to_metadata(metadata)

    def _build_id3_metadata(self, raw_json: dict, file_path: str, rule_result: dict) -> dict:
        """Build ID3 metadata dict to write, using current ID3 and rule output."""
        return self.rule_applier.build_id3_metadata(raw_json, file_path, rule_result)
    
    def update_preview_info(self):
        """Update preview info based on selected file."""
        self.preview_panel_manager.update_preview_info()
    
    
    def on_json_changed(self):
        """Enable save button when JSON is changed."""
        if self.save_json_btn:
            self.save_json_btn.setEnabled(True)
    
    def save_json_changes(self):
        """Save JSON changes to file data and MP3 COMM:ved tag."""
        try:
            # Parse the JSON to validate it
            json_text = self.json_editor.toPlainText().strip()
            if not json_text:
                QMessageBox.warning(self, "Empty JSON", "JSON text is empty")
                return
                
            new_data = json.loads(json_text)
            
            if self.current_selected_file is not None and self.current_selected_file < len(self.song_files):
                file_path = self.song_files[self.current_selected_file].get('path')
                if not file_path:
                    QMessageBox.warning(self, "Error", "No file path found")
                    return
                
                # Write to actual MP3 file COMM:ved tag (compacted format)
                if not write_json_to_song(file_path, new_data):
                    QMessageBox.critical(self, "Error", "Failed to save JSON to file")
                    return
                
                # Update in-memory data after successful save
                self.song_files[self.current_selected_file]['raw_json'] = new_data
                
                self.save_json_btn.setEnabled(False)
                # Refresh the folder to reload file data
                self.refresh_current_folder()
                QMessageBox.information(self, "Success", "JSON updated successfully!")
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Error", f"Invalid JSON: {e}")
    
    def on_filename_changed(self):
        """Enable save button when filename is changed."""
        if self.save_filename_btn and self.filename_preview.text() != self.original_filename:
            self.save_filename_btn.setEnabled(True)
        elif self.save_filename_btn:
            self.save_filename_btn.setEnabled(False)
    
    def save_filename_changes(self):
        """Save filename changes."""
        if self.current_selected_file is None or self.current_selected_file >= len(self.song_files):
            return
        
        file_data = self.song_files[self.current_selected_file]
        old_path = file_data.get('path', '')
        if not old_path or not Path(old_path).exists():
            QMessageBox.warning(self, "Warning", "File not found.")
            return
        
        new_filename = self.filename_preview.text().strip()
        if not new_filename:
            QMessageBox.warning(self, "Warning", "Filename cannot be empty.")
            return
        
        old_path_obj = Path(old_path)
        new_path = old_path_obj.parent / new_filename
        
        try:
            old_path_obj.rename(new_path)
            file_data['path'] = str(new_path)
            self.original_filename = new_filename
            self.save_filename_btn.setEnabled(False)
            # Refresh the folder to reload file data
            self.refresh_current_folder()
            QMessageBox.information(self, "Success", f"Renamed to {new_filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to rename file: {e}")
    
    def prev_file(self):
        """Previous file."""
        if self.current_index is not None and self.current_index > 0:
            self.current_index -= 1
            item = self.tree.topLevelItem(self.current_index)
            if item:
                self.tree.setCurrentItem(item)
    
    def next_file(self):
        """Next file."""
        max_idx = self.tree.topLevelItemCount()
        if self.current_index is not None and self.current_index < max_idx - 1:
            self.current_index += 1
            item = self.tree.topLevelItem(self.current_index)
            if item:
                self.tree.setCurrentItem(item)
    
    # ===== PRESET OPERATIONS =====
    




    
    # ===== STATISTICS =====
    
    def show_statistics(self):
        """Show statistics."""
        if not self.song_files:
            QMessageBox.warning(self, "Warning", "No files loaded.")
            return
        
        # Basic stats
        total = len(self.song_files)
        
        # Count unique combinations
        title_artist = set()
        title_artist_cover = set()
        
        # Count by artist
        neuro_count = 0
        evil_count = 0
        neuro_evil_count = 0
        other_count = 0
        
        for f in self.song_files:
            artist = f.get(MetadataFields.ARTIST, "")
            title = f.get(MetadataFields.TITLE, "")
            cover_artist = f.get(MetadataFields.COVER_ARTIST, "")
            
            # Track combinations
            title_artist.add((title, artist))
            title_artist_cover.add((title, artist, cover_artist))
            
            # Track artist types (using cover artist)
            cover_artist_lower = cover_artist.lower()
            if "neuro" in cover_artist_lower and "evil" in cover_artist_lower:
                neuro_evil_count += 1
            elif "neuro" in cover_artist_lower:
                neuro_count += 1
            elif "evil" in cover_artist_lower:
                evil_count += 1
            else:
                other_count += 1
        
        stats_text = f"""Total Songs: {total}

Unique Combinations:
  • Title + Artist: {len(title_artist)}
  • Title + Artist + CoverArtist: {len(title_artist_cover)}

By Artist:
  • Neuro only: {neuro_count}
  • Evil only: {evil_count}
  • Neuro & Evil: {neuro_evil_count}
  • Others: {other_count}"""
        
        QMessageBox.information(self, "Statistics", stats_text)
    
    # ===== MENU ACTIONS =====
    
    def undo(self):
        """Undo."""
        QMessageBox.information(self, "Info", "Coming soon.")
    
    def redo(self):
        """Redo."""
        QMessageBox.information(self, "Info", "Coming soon.")
    
    def show_about(self):
        """About."""
        QMessageBox.information(self, "About",
            "Database Formatter v2.0\n"
            "MP3 Metadata Customizer\n\n"
            "✓ REST API\n"
            "✓ CLI Commands\n"
            "✓ PyQt6 GUI")
    
    def show_preferences(self):
        """Show preferences dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Preferences")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        
        # Auto-reopen section
        auto_group = QFrame()
        auto_group.setStyleSheet("QFrame { background-color: #2d2d2d; border-radius: 4px; padding: 10px; }")
        auto_layout = QVBoxLayout(auto_group)
        
        auto_label = QLabel("Startup Behavior")
        auto_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        auto_layout.addWidget(auto_label)
        
        auto_check = QCheckBox("Automatically reopen last folder on startup")
        auto_check.setChecked(SettingsManager.auto_reopen_last_folder or False)
        auto_layout.addWidget(auto_check)
        
        last_folder = SettingsManager.last_folder_opened
        if last_folder:
            folder_label = QLabel(f"Last folder: {last_folder}")
            folder_label.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
            folder_label.setWordWrap(True)
            auto_layout.addWidget(folder_label)
        
        layout.addWidget(auto_group)
        
        # Theme selection section
        theme_group = QFrame()
        theme_group.setStyleSheet("QFrame { background-color: #2d2d2d; border-radius: 4px; padding: 10px; }")
        theme_layout = QVBoxLayout(theme_group)
        
        theme_label = QLabel("Appearance")
        theme_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        theme_layout.addWidget(theme_label)
        
        theme_combo = QComboBox()
        theme_combo.addItems(["Dark", "Light"])
        # Get current theme and normalize capitalization
        current_theme = SettingsManager.theme or "dark"
        if current_theme.lower() == "dark":
            current_theme = "Dark"
        elif current_theme.lower() == "light":
            current_theme = "Light"
        theme_combo.setCurrentText(current_theme)
        theme_layout.addWidget(theme_combo)
        
        # UI Scale
        scale_label = QLabel("UI Scale:")
        theme_layout.addWidget(scale_label)
        
        scale_spin = QDoubleSpinBox()
        scale_spin.setRange(0.75, 2.0)
        scale_spin.setSingleStep(0.05)
        scale_spin.setValue(SettingsManager.ui_scale)
        scale_spin.setSuffix("x")
        scale_spin.setDecimals(2)
        theme_layout.addWidget(scale_spin)
        
        layout.addWidget(theme_group)
        
        # Reset all settings button
        reset_btn = QPushButton("Reset All Settings")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #b33333;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #c55555; }
        """)
        reset_btn.clicked.connect(lambda: self._reset_all_settings(dialog))
        layout.addWidget(reset_btn)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(80)
        save_btn.clicked.connect(lambda: self._save_preferences(dialog, auto_check.isChecked(), theme_combo.currentText(), scale_spin.value()))
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def _save_preferences(self, dialog, auto_reopen, theme, ui_scale):
        """Save preferences."""
        old_ui_scale = SettingsManager.ui_scale
        SettingsManager.auto_reopen_last_folder = auto_reopen
        # Normalize theme to lowercase for storage
        SettingsManager.theme = theme.lower()
        SettingsManager.ui_scale = ui_scale
        SettingsManager.save_settings()
        self._apply_theme_from_system()
        
        dialog.accept()
        
        # Check if UI scale changed
        if abs(ui_scale - old_ui_scale) > 0.01:
            QMessageBox.information(self, "Success", 
                "Preferences saved!\n\n"
                "UI scale change requires app restart to take full effect.\n"
                "Please close and reopen the application.")
        else:
            QMessageBox.information(self, "Success", "Preferences saved!")
    
    def _reset_all_settings(self, dialog):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset All Settings",
            "Are you sure you want to reset all settings to defaults?\n\n"
            "This will:\n"
            "• Clear window size and position\n"
            "• Reset column widths and order\n"
            "• Clear last folder\n"
            "• Reset auto-reopen preference",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Reset all settings
            SettingsManager.theme = "dark"
            SettingsManager.ui_scale = 1.0
            SettingsManager.last_folder_opened = None
            SettingsManager.auto_reopen_last_folder = False
            SettingsManager.column_order = None
            SettingsManager.column_widths = {}
            SettingsManager.window_width = 1400
            SettingsManager.window_height = 900
            SettingsManager.splitter_sizes = []
            SettingsManager.save_settings()
            self._apply_theme_from_system()
            
            # Apply immediately
            self.resize(1400, 900)
            
            # Reset column widths and order
            if hasattr(self, 'tree'):
                widths = [150, 120, 100, 70, 80, 50, 50, 150, 80]
                for i, w in enumerate(widths[:self.tree.columnCount()]):
                    self.tree.setColumnWidth(i, w)
                
                # Reset column order
                header = self.tree.header()
                for i in range(header.count()):
                    header.moveSection(header.visualIndex(i), i)
            
            # Reset splitter to default proportions (62:38)
            if hasattr(self, 'main_splitter'):
                total_width = self.main_splitter.width()
                self.main_splitter.setSizes([int(total_width * 0.62), int(total_width * 0.38)])
            
            dialog.accept()
            QMessageBox.information(
                self,
                "Settings Reset",
                "All settings have been reset to defaults."
            )
    
    # ===== SETTINGS =====
    
    def save_settings(self):
        """Save settings."""
        try:
            SettingsManager.window_width = self.width()
            SettingsManager.window_height = self.height()
            if hasattr(self, 'main_splitter'):
                SettingsManager.splitter_sizes = self.main_splitter.sizes()
            
            # Save column widths
            if hasattr(self, 'tree'):
                widths = {}
                for i, col in enumerate(self.TREE_COLUMNS):
                    col_name = col.value if hasattr(col, 'value') else str(col)
                    widths[col_name] = self.tree.columnWidth(i)
                SettingsManager.column_widths = widths
            
            # Save sort rules
            if self.sort_controls_manager.sort_rules_list:
                SettingsManager.sort_rules = [
                    (rule_info['field'].currentText(), rule_info['order'].currentText() == "Asc")
                    for rule_info in self.sort_controls_manager.sort_rules_list
                ]
            
            SettingsManager.save_settings()
        except Exception as e:
            logger.debug(f"Error saving settings: {e}")
    
    def load_settings(self):
        """Load settings."""
        try:
            if hasattr(SettingsManager, 'window_width'):
                self.resize(SettingsManager.window_width, SettingsManager.window_height)
            
            if hasattr(SettingsManager, 'theme'):
                self.current_theme = SettingsManager.theme or "System"
                self._apply_theme_from_system()
            
            if hasattr(self, 'main_splitter') and SettingsManager.splitter_sizes:
                self.main_splitter.setSizes(SettingsManager.splitter_sizes)
            
            # Restore column widths
            if hasattr(self, 'tree') and SettingsManager.column_widths:
                for i, col in enumerate(self.TREE_COLUMNS):
                    col_name = col.value if hasattr(col, 'value') else str(col)
                    if col_name in SettingsManager.column_widths:
                        self.tree.setColumnWidth(i, SettingsManager.column_widths[col_name])
            
            # Restore column order
            if hasattr(self, 'tree') and SettingsManager.column_order:
                header = self.tree.header()
                if len(SettingsManager.column_order) == header.count():
                    for logical_index, visual_index in enumerate(SettingsManager.column_order):
                        header.moveSection(header.visualIndex(logical_index), visual_index)
            
            # Restore sort rules
            if hasattr(SettingsManager, 'sort_rules') and SettingsManager.sort_rules:
                # Clear existing (except first which is always Title)
                while len(self.sort_controls_manager.sort_rules_list) > 1:
                    self.sort_controls_manager.remove_sort_rule(1)

                # Update first rule if needed
                if len(self.sort_controls_manager.sort_rules_list) > 0:
                    first_rule = SettingsManager.sort_rules[0]
                    self.sort_controls_manager.sort_rules_list[0]['field'].setCurrentText(first_rule[0])
                    self.sort_controls_manager.sort_rules_list[0]['order'].setCurrentText(
                        "Asc" if first_rule[1] else "Desc"
                    )

                # Add additional rules
                for rule in SettingsManager.sort_rules[1:]:
                    self.sort_controls_manager.add_sort_rule()
                    rule_info = self.sort_controls_manager.sort_rules_list[-1]
                    rule_info['field'].setCurrentText(rule[0])
                    rule_info['order'].setCurrentText("Asc" if rule[1] else "Desc")
        except Exception as e:
            logger.debug(f"Error loading settings: {e}")
    
    def rename_current_file(self):
        """Rename the currently selected file."""
        if self.current_selected_file is None or self.current_selected_file >= len(self.song_files):
            QMessageBox.warning(self, "Warning", "No file selected.")
            return
        
        file_data = self.song_files[self.current_selected_file]
        old_path = Path(file_data.get('path', ""))
        
        if not old_path.exists():
            QMessageBox.warning(self, "Warning", "File not found.")
            return
        
        # Get new name
        new_name, ok = QInputDialog.getText(
            self, "Rename File",
            f"Current: {old_path.name}\n\nNew name:",
            text=old_path.name
        )
        
        if not ok or not new_name:
            return
        
        try:
            new_path = old_path.parent / new_name
            
            if new_path.exists():
                QMessageBox.warning(self, "Warning", "A file with that name already exists.")
                return
            
            # Rename the file
            old_path.rename(new_path)
            
            # Update file data
            file_data['path'] = str(new_path)
            self.song_files[self.current_selected_file] = file_data
            
            # Update tree view
            self.populate_tree()
            
            QMessageBox.information(self, "Success", f"File renamed to:\n{new_name}")
            self.file_info_label.setText(f"Renamed file to {new_name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to rename file:\n{e}")
            logger.exception("Error renaming file")
    
    def closeEvent(self, event):
        """Handle close."""
        self.save_settings()
        event.accept()


def main():
    """Entry point."""
    # Set UI scale BEFORE creating QApplication
    import os
    from df_metadata_customizer.core.settings_manager import SettingsManager
    SettingsManager.initialize()
    ui_scale = SettingsManager.ui_scale
    if ui_scale != 1.0:
        os.environ['QT_SCALE_FACTOR'] = str(ui_scale)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Apply font scaling if needed
    if ui_scale != 1.0:
        base_font = app.font()
        base_font.setPointSizeF(base_font.pointSizeF() * ui_scale)
        app.setFont(base_font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

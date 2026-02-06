"""PySide6 Main Window - COMPLETE with ALL fixes and features."""

import sys
import json
import logging
import contextlib
from pathlib import Path
from typing import Optional, Any, Dict, List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton,
    QLabel, QFrame, QScrollArea, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QComboBox, QTabWidget, QApplication, QHeaderView, QInputDialog,
    QTextEdit, QMenu, QAbstractItemView, QDialog, QCheckBox, QDoubleSpinBox, QStackedLayout
)
from PySide6.QtCore import Qt, QSize, QTimer, QByteArray
from PySide6.QtGui import QIcon, QPalette, QColor, QFont

from df_metadata_customizer.core import FileManager, SettingsManager, PresetService, RuleManager
from df_metadata_customizer.core.metadata import MetadataFields
from df_metadata_customizer.core.song_utils import write_json_to_song
from df_metadata_customizer.ui.progress_dialog import ProgressDialog
from df_metadata_customizer.ui.menu_bar import setup_menubar
from df_metadata_customizer.ui.song_controls import create_song_controls
from df_metadata_customizer.ui.status_bar import create_status_bar
from df_metadata_customizer.ui.sort_controls import SortControlsManager
from df_metadata_customizer.ui.styles import get_theme_colors
from df_metadata_customizer.ui.tree_view import TreeViewManager
from df_metadata_customizer.ui.preset_manager import PresetManager
from df_metadata_customizer.ui.rules_panel import RulesPanelManager
from df_metadata_customizer.ui.song_editor import SongEditorManager
from df_metadata_customizer.ui import custom_dialogs

from df_metadata_customizer.ui.cover_manager import CoverManager
from df_metadata_customizer.ui.preview_panel import PreviewPanelManager
from df_metadata_customizer.ui.search_handler import SearchHandler
from df_metadata_customizer.ui.sort_handler import SortHandler
from df_metadata_customizer.ui.rule_applier import RuleApplier
from df_metadata_customizer.ui.rule_widgets import NoScrollComboBox

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Complete PySide6 main window with ALL features."""

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
        MetadataFields.SPECIAL,
        MetadataFields.FILE,
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
        
        # Theme-aware colors (updated in _apply_theme) - VS Code Modern themes
        self.theme_colors = {
            'bg_primary': '#1e1e1e',      # VS Code Dark Modern: editor background
            'bg_secondary': '#252526',     # VS Code Dark Modern: sidebar
            'bg_tertiary': '#2d2d30',      # VS Code Dark Modern: darker elements
            'border': '#454545',           # VS Code Dark Modern: borders
            'text': '#cccccc',             # VS Code Dark Modern: text
            'text_secondary': '#858585',   # VS Code Dark Modern: dimmed text
            'button': '#0e639c',           # VS Code Dark Modern: button
            'selection': '#264f78',        # VS Code Dark Modern: selection
        }

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
        
        # Debounce timer for sort operations to prevent cascading updates
        self._sort_debounce_timer = QTimer()
        self._sort_debounce_timer.setSingleShot(True)
        self._sort_debounce_timer.timeout.connect(self._apply_sort)
        self._sort_debounce_delay = 50  # milliseconds
        self._is_sorting = False  # Flag to prevent preview updates during sort

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
        # Stylesheet will be set by _refresh_theme_colors()

        left_frame = self._create_left_frame()
        right_frame = self._create_right_frame()

        self.main_splitter.addWidget(left_frame)
        self.main_splitter.addWidget(right_frame)
        self.main_splitter.setSizes([800, 600])

        layout.addWidget(self.main_splitter)
        
        # Apply initial theme colors to dynamic stylesheets
        self._refresh_theme_colors()

    def _create_left_frame(self):
        """Create left frame with song list and controls."""
        frame = QFrame()
        self.left_frame = frame  # Store reference for theme updates
        # Stylesheet will be set by _refresh_theme_colors()
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
        self.right_frame = frame  # Store reference for theme updates
        # Stylesheet will be set by _refresh_theme_colors()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        
        tabs = QTabWidget()
        self.tabs = tabs
        # Stylesheet will be set by _refresh_theme_colors()
        
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
        # Determine theme - either from setting or from system
        if SettingsManager.follow_system_theme or SettingsManager.theme == "system":
            theme = self._get_system_theme()
        else:
            theme = (SettingsManager.theme or "dark").lower()
        self.current_theme = theme
        self._apply_theme(theme)
    
    def _get_system_theme(self) -> str:
        """Detect system theme preference (dark or light)."""
        try:
            # Try using platform-specific methods
            app = QApplication.instance()
            if app:
                # Check system palette for hint - if button is darker, likely dark theme
                button_color = app.palette().color(QPalette.ColorRole.Button)
                brightness = button_color.lightness()
                # If brightness is less than 128 (middle of 0-255), consider it dark
                return "dark" if brightness < 128 else "light"
        except Exception:
            pass
        # Default to dark theme
        return "dark"
    
    def _apply_ui_scale(self):
        """Apply UI scale from settings (handled in main(), this is for tracking)."""
        self._last_ui_scale = SettingsManager.ui_scale
    
    def _apply_theme(self, theme: str = "dark"):
        """Apply theme to application - VS Code Modern themes."""
        app = QApplication.instance()
        if theme == "dark" or theme.lower() == "dark":
            # VS Code Dark Modern color palette
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))           # #1e1e1e
            palette.setColor(QPalette.ColorRole.WindowText, QColor(204, 204, 204))   # #cccccc
            palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))            # #1e1e1e
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(37, 37, 38))   # #252526
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(37, 37, 38))     # #252526
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(204, 204, 204))  # #cccccc
            palette.setColor(QPalette.ColorRole.Text, QColor(204, 204, 204))         # #cccccc
            palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 48))          # #2d2d30
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(204, 204, 204))   # #cccccc
            palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))       # Errors
            palette.setColor(QPalette.ColorRole.Link, QColor(58, 150, 221))          # #3a96dd
            palette.setColor(QPalette.ColorRole.Highlight, QColor(38, 79, 120))      # #264f78
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(133, 133, 133))  # #858585
            # Apply to application instance so all widgets inherit it
            if app:
                app.setPalette(palette)
            self.setPalette(palette)
            SettingsManager.theme = "dark"
            # VS Code Dark Modern comprehensive stylesheet
            self.setStyleSheet("""
                QMainWindow, QDialog { background-color: #1e1e1e; color: #cccccc; }
                QFrame { border: none; }
                QLabel { color: #cccccc; background-color: transparent; }
                QToolTip { background-color: #252526; color: #cccccc; border: 1px solid #454545; }
                QComboBox::drop-down { border: none; }
            """)
            # Update theme colors - centralized palette
            self.theme_colors = get_theme_colors("dark")
            self._refresh_theme_colors()
        else:
            # VS Code Light Modern color palette
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))        # #ffffff
            palette.setColor(QPalette.ColorRole.WindowText, QColor(59, 59, 59))       # #3b3b3b
            palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))          # #ffffff
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(243, 243, 243)) # #f3f3f3
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(243, 243, 243))   # #f3f3f3
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(59, 59, 59))      # #3b3b3b
            palette.setColor(QPalette.ColorRole.Text, QColor(59, 59, 59))             # #3b3b3b
            palette.setColor(QPalette.ColorRole.Button, QColor(243, 243, 243))        # #f3f3f3
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(59, 59, 59))       # #3b3b3b
            palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 122, 204))       # #007acc
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Link, QColor(0, 122, 204))            # #007acc
            palette.setColor(QPalette.ColorRole.LinkVisited, QColor(135, 107, 196))   # #876bc4
            palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(150, 150, 150))
            # Apply to application instance so all widgets inherit it
            if app:
                app.setPalette(palette)
            self.setPalette(palette)
            SettingsManager.theme = "light"
            # Update theme colors - centralized palette
            self.theme_colors = get_theme_colors("light")
            self._refresh_theme_colors()
            # VS Code Light Modern comprehensive stylesheet
            self.setStyleSheet("""
                QMainWindow, QDialog { background-color: #ffffff; }
                QFrame { background-color: #ffffff; border: none; }
                QLabel { color: #3b3b3b; background-color: transparent; }
                QLineEdit { background-color: #ffffff; color: #3b3b3b; border: 1px solid #e5e5e5; padding: 4px; border-radius: 3px; }
                QComboBox { background-color: #f3f3f3; color: #3b3b3b; border: 1px solid #e5e5e5; padding: 4px; border-radius: 3px; }
                QComboBox::drop-down { border: none; }
                QComboBox QAbstractItemView { background-color: #ffffff; color: #3b3b3b; selection-background-color: #007acc; selection-color: #ffffff; }
                QPushButton { background-color: #f3f3f3; color: #3b3b3b; border: 1px solid #e5e5e5; padding: 6px; border-radius: 3px; }
                QPushButton:hover { background-color: #e8e8e8; }
                QPushButton:pressed { background-color: #d8d8d8; }
                QTreeWidget { background-color: #ffffff; color: #3b3b3b; border: 1px solid #e5e5e5; }
                QTreeWidget::item:selected { background-color: #007acc; color: #ffffff; }
                QTreeWidget::item:hover { background-color: #f0f0f0; }
                QTextEdit, QPlainTextEdit { background-color: #ffffff; color: #3b3b3b; border: 1px solid #e5e5e5; }
                QCheckBox { color: #3b3b3b; }
                QRadioButton { color: #3b3b3b; }
                QGroupBox { color: #3b3b3b; border: 1px solid #e5e5e5; border-radius: 4px; margin-top: 10px; padding-top: 10px; }
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }
                QMenuBar { background-color: #f3f3f3; color: #3b3b3b; }
                QMenuBar::item:selected { background-color: #007acc; color: #ffffff; }
                QMenu { background-color: #ffffff; color: #3b3b3b; border: 1px solid #e5e5e5; }
                QMenu::item:selected { background-color: #007acc; color: #ffffff; }
                QTabWidget::pane { border: 1px solid #e5e5e5; background-color: #ffffff; }
                QTabBar::tab { background-color: #e8e8e8; color: #3b3b3b; padding: 8px; border: 1px solid #e5e5e5; }
                QTabBar::tab:selected { background-color: #ffffff; border-bottom: none; }
            """)
    
    def _refresh_theme_colors(self):
        """Refresh all hardcoded stylesheets with current theme colors."""
        c = self.theme_colors
        is_dark = SettingsManager.theme == "dark"
        
        # Update splitter
        if hasattr(self, 'main_splitter'):
            self.main_splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {c['border']}; }}")
        
        # Update left and right frames
        frame_style = f"QFrame {{ background-color: {c['bg_secondary']}; border-radius: 8px; }}"
        if hasattr(self, 'left_frame'):
            self.left_frame.setStyleSheet(frame_style)
        if hasattr(self, 'right_frame'):
            self.right_frame.setStyleSheet(frame_style)
        
        # Update search input
        if hasattr(self, 'search_input') and self.search_input:
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {c['bg_primary']};
                    color: {c['text']};
                    border: 1px solid {c['border']};
                    border-radius: 4px;
                    padding: 4px 8px;
                }}
                QLineEdit:focus {{ border: 2px solid {c['button']}; }}
            """)
        
        # Update song control buttons
        button_hover = c.get('button_hover', c['button'])
        button_pressed = c.get('button_pressed', c['button'])
        
        button_style = f"""
            QPushButton {{
                background-color: {c['button']};
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {button_hover}; }}
            QPushButton:pressed {{ background-color: {button_pressed}; }}
        """
        
        for btn_name in ['folder_btn', 'refresh_btn', 'select_all_btn']:
            if hasattr(self, btn_name) and getattr(self, btn_name):
                getattr(self, btn_name).setStyleSheet(button_style)
        
        # Update filtered count label
        if hasattr(self, 'filtered_count_label') and self.filtered_count_label:
            label_color = '#bbb' if is_dark else '#777'
            self.filtered_count_label.setStyleSheet(f"color: {label_color}; font-size: 11px;")
        
        # Update menubar
        if hasattr(self, 'menuBar'):
            menubar = self.menuBar()
            if menubar:
                if is_dark:
                    menubar.setStyleSheet(f"""
                        QMenuBar {{
                            background-color: {c['bg_primary']};
                            color: {c['text']};
                            border-bottom: 1px solid {c['border']};
                        }}
                        QMenuBar::item:selected {{ background-color: {c['bg_tertiary']}; }}
                        QMenu {{
                            background-color: {c['bg_primary']};
                            color: {c['text']};
                            border: 1px solid {c['border']};
                        }}
                        QMenu::item:selected {{ background-color: {c['button']}; color: #ffffff; }}
                    """)
                else:
                    menubar.setStyleSheet(f"""
                        QMenuBar {{
                            background-color: {c['bg_secondary']};
                            color: {c['text']};
                            border-bottom: 1px solid {c['border']};
                        }}
                        QMenuBar::item:selected {{ background-color: {c['button']}; color: #ffffff; }}
                        QMenu {{
                            background-color: {c['bg_primary']};
                            color: {c['text']};
                            border: 1px solid {c['border']};
                        }}
                        QMenu::item:selected {{ background-color: {c['button']}; color: #ffffff; }}
                    """)
        
        # Update tabs
        if hasattr(self, 'tabs'):
            if is_dark:
                tab_style = f"""
                    QTabWidget::pane {{ border: 1px solid {c['border']}; }}
                    QTabBar::tab {{
                        background-color: {c['bg_primary']};
                        color: {c['text']};
                        padding: 8px 16px;
                        margin-right: 2px;
                    }}
                    QTabBar::tab:selected {{
                        background-color: {c['button']};
                        color: #ffffff;
                    }}
                    QTabBar::tab:hover:!selected {{
                        background-color: {c['border']};
                    }}
                """
            else:
                tab_style = f"""
                    QTabWidget::pane {{ border: 1px solid {c['border']}; background-color: {c['bg_secondary']}; }}
                    QTabBar::tab {{
                        background-color: {c['bg_tertiary']};
                        color: {c['text']};
                        padding: 8px 16px;
                        margin-right: 2px;
                        border: 1px solid {c['border']};
                    }}
                    QTabBar::tab {{
                        background-color: #e8e8e8;
                        color: {c['text']};
                        padding: 8px 16px;
                        margin-right: 2px;
                        border: 1px solid {c['border']};
                    }}
                    QTabBar::tab:selected {{
                        background-color: {c['button']};
                        color: #ffffff;
                        border-bottom: 1px solid {c['button']};
                    }}
                    QTabBar::tab:hover:!selected {{
                        background-color: #dcdcdc;
                    }}
                """
            self.tabs.setStyleSheet(tab_style)
        
        # Update tree view
        if hasattr(self, 'tree_view_manager') and self.tree_view_manager:
            self.tree_view_manager.update_tree_stylesheet(c)
        
        # Update preset combo
        if hasattr(self, 'preset_manager') and self.preset_manager:
            self.preset_manager.update_preset_stylesheet(c)
        
        # Update cover container
        if hasattr(self, 'cover_container') and self.cover_container:
            cover_style = f"""
                QFrame {{
                    background-color: {c['bg_primary']};
                    border: 1px solid {c['border']};
                    border-radius: 4px;
                }}
            """
            self.cover_container.setStyleSheet(cover_style)
        
        # Update song editor components
        if hasattr(self, 'song_editor_manager') and self.song_editor_manager:
            self.song_editor_manager.update_theme(c, is_dark)
        
        # Update sort controls
        if hasattr(self, 'sort_controls_manager') and self.sort_controls_manager:
            self.sort_controls_manager.update_theme(c, is_dark)
        
        # Update rules panel
        if hasattr(self, 'rules_panel_manager') and self.rules_panel_manager:
            self.rules_panel_manager.update_theme(c, is_dark)
        
        # Update preview panel
        if hasattr(self, 'preview_panel_manager') and self.preview_panel_manager:
            self.preview_panel_manager.update_theme(c, is_dark)
    
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
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with Audio Files")
        if folder:
            self.load_folder(folder, show_dialogs=True)
    
    def refresh_current_folder(self, show_dialogs=False):
        """Refresh the current folder to reload all files."""
        if self.current_folder:
            self.load_folder(self.current_folder, show_dialogs=show_dialogs)
        else:
            custom_dialogs.information(self, "No Folder", "No folder is currently loaded. Please select a folder first.")
    
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
                custom_dialogs.information(
                    self, 
                    "Load Complete",
                    f"Successfully loaded {len(self.song_files)} files from:\n{folder_path}"
                )
            
            self.file_info_label.setText(f"✓ Loaded {len(self.song_files)} files")
            if show_dialogs:
                self.search_input.clear()
            
        except Exception as e:
            custom_dialogs.critical(self, "Error", f"Failed to load folder:\n{e}")
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
                msg_box = QMessageBox()
                msg_box.setWindowFlags(Qt.Dialog)
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
    
    def populate_tree(self, preserve_selection=False):
        """Populate tree with songs.
        
        Args:
            preserve_selection: If True, preserve previously selected items by their data indices
        """
        # Set flag to prevent cascading preview updates during tree rebuild
        self._is_sorting = True
        
        # Block signals to prevent cascading updates during tree rebuild
        self.tree.blockSignals(True)
        
        # Save selection before clearing
        selected_indices = set()
        if preserve_selection:
            for item in self.tree.selectedItems():
                idx = item.data(0, Qt.ItemDataRole.UserRole)
                if idx is not None:
                    selected_indices.add(idx)
        
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
            7: "Special",         # Special
            8: "path",            # Filename
        }
        
        for tree_row, idx in enumerate(self.filtered_indices):
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
                is_truncated = len(value_str) > 60
                if is_truncated:
                    value_str = value_str[:57] + "..."
                item.setText(col_idx, value_str)
                # Add tooltip if text was truncated or if it's the path column
                if is_truncated or key == "path":
                    item.setToolTip(col_idx, str(value))
                item.setTextAlignment(col_idx, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            item.setData(0, Qt.ItemDataRole.UserRole, idx)
            
            # Restore selection for items that were previously selected
            if idx in selected_indices:
                item.setSelected(True)
        
        # Re-enable signals
        self.tree.blockSignals(False)
        
        # Emit selection changed only once after all items are added
        self.update_selection_info()
        
        # Clear flag to allow preview updates again
        self._is_sorting = False
    
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
    
    def _parse_search_value(self, value_str: str) -> tuple[str, bool]:
        """Parse search value, handling quoted strings.
        
        Returns:
            tuple: (parsed_value, is_exact_match)
                - parsed_value: the cleaned search value
                - is_exact_match: True if quotes were used (indicating exact match wanted)
        """
        value_str = value_str.strip()
        # Check if quotes are present (indicates exact match desired)
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1].lower(), True
        return value_str.lower(), False

    def _normalize_version_compare(self, field_value: str, search_value: str) -> bool:
        """Compare version values, treating integers and floats as equivalent.
        
        Examples: "1" == "1.0", "2" == "2.0", etc.
        """
        try:
            # Convert both to float for comparison
            field_float = float(field_value)
            search_float = float(search_value)
            return field_float == search_float
        except (ValueError, TypeError):
            # Fallback to string comparison if not numeric
            return str(field_value).lower() == str(search_value).lower()

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
                        search_value, is_exact = self._parse_search_value(parts[1])

                        if search_field == "version" and search_value in {"latest", "not latest", "not_latest", "notlatest"}:
                            want_latest = (search_value == "latest")
                            match = not self._is_latest_version_match(file_data, want_latest)
                        else:
                            for key, value in file_data.items():
                                if search_field in key.lower():
                                    # Special handling for version field to treat 1 == 1.0
                                    if key.lower() == "version":
                                        if not self._normalize_version_compare(str(value), search_value):
                                            match = True
                                            break
                                    else:
                                        if str(value).lower() != search_value:
                                            match = True
                                            break
                
                elif "==" in query:
                    # Exact match (or quoted with =)
                    parts = query.split("==", 1)
                    if len(parts) == 2:
                        search_field = parts[0].strip().lower()
                        search_value, is_exact = self._parse_search_value(parts[1])

                        if search_field == "version" and search_value in {"latest", "not latest", "not_latest", "notlatest"}:
                            want_latest = (search_value == "latest")
                            match = self._is_latest_version_match(file_data, want_latest)
                        else:
                            for key, value in file_data.items():
                                if search_field in key.lower():
                                    # Special handling for version field to treat 1 == 1.0
                                    if key.lower() == "version":
                                        if self._normalize_version_compare(str(value), search_value):
                                            match = True
                                            break
                                    else:
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
                    # Contains match (or exact match if quoted)
                    parts = query.split("=", 1)
                    if len(parts) == 2:
                        search_field = parts[0].strip().lower()
                        search_value, is_exact = self._parse_search_value(parts[1])

                        if search_field == "version" and search_value in {"latest", "not latest", "not_latest", "notlatest"}:
                            want_latest = (search_value == "latest")
                            match = self._is_latest_version_match(file_data, want_latest)
                        else:
                            for key, value in file_data.items():
                                if search_field in key.lower():
                                    value_lower = str(value).lower()
                                    # Special handling for version field to treat 1 == 1.0
                                    if key.lower() == "version":
                                        if self._normalize_version_compare(str(value), search_value):
                                            match = True
                                            break
                                    elif is_exact:
                                        # If quoted, do exact match
                                        if value_lower == search_value:
                                            match = True
                                            break
                                    else:
                                        # Otherwise do contains match
                                        if search_value in value_lower:
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
        """Apply multi-level sorting with debouncing to prevent cascading updates."""
        # Reset debounce timer - this prevents rapid successive sorts
        self._sort_debounce_timer.stop()
        self._sort_debounce_timer.start(self._sort_debounce_delay)
    
    def _apply_sort(self):
        """Internal method to actually apply the sort (called by debounce timer)."""
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
        """Save JSON changes to file data and audio file metadata."""
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
                
                # Write to actual audio file metadata tag (compacted format)
                if not write_json_to_song(file_path, new_data):
                    QMessageBox.critical(self, "Error", "Failed to save JSON to file")
                    return
                
                # Update in-memory data after successful save
                self.song_files[self.current_selected_file]['raw_json'] = new_data
                
                self.save_json_btn.setEnabled(False)
                # Refresh the folder to reload file data
                self.refresh_current_folder()
                custom_dialogs.information(self, "Success", "JSON updated successfully!")
        except json.JSONDecodeError as e:
            custom_dialogs.critical(self, "Error", f"Invalid JSON: {e}")
    
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
    
    def show_about(self):
        """About."""
        QMessageBox.information(
            self,
            "About DF Metadata Customizer",
            "DF Metadata Customizer v2.0.0\n"
            "Audio Metadata Editor\n"
            "Supports: MP3, FLAC, OGG, M4A, WAV, OPUS\n\n"
            "A powerful tool for managing cover song collections with:\n"
            "• Rule-based metadata editing\n"
            "• Multi-level sorting (up to 5 fields)\n"
            "• Advanced search with filters\n"
            "• JSON metadata support\n"
            "• Direct song playback\n"
            "• Cover art management\n"
            "• Batch processing\n\n"
            "Built with PySide6 (Qt6) for modern UI\n"
            "Created for the Neuro-sama fan community\n\n"
            "Licensed under MIT License\n"
            "GitHub: github.com/gamerturuu/df-metadata-customizer"
        )
    
    def show_preferences(self):
        """Show preferences dialog."""
        dialog = QDialog()
        dialog.setWindowFlags(Qt.Dialog)
        dialog.setWindowTitle("Preferences")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        
        c = self.theme_colors
        
        # Auto-reopen section
        auto_group = QFrame()
        auto_group.setStyleSheet(f"QFrame {{ background-color: {c['bg_tertiary']}; border-radius: 4px; padding: 10px; }}")
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
            folder_label.setStyleSheet(f"color: {c['text_secondary']}; font-size: 9pt;")
            folder_label.setWordWrap(True)
            auto_layout.addWidget(folder_label)
        
        layout.addWidget(auto_group)
        
        # Theme selection section
        theme_group = QFrame()
        theme_group.setStyleSheet(f"QFrame {{ background-color: {c['bg_tertiary']}; border-radius: 4px; padding: 10px; }}")
        theme_layout = QVBoxLayout(theme_group)
        
        theme_label = QLabel("Appearance")
        theme_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        theme_layout.addWidget(theme_label)

        theme_combo = NoScrollComboBox()
        theme_combo.addItems(["System", "Dark", "Light"])
        # Get current theme and normalize capitalization
        current_theme = SettingsManager.theme or "system"
        if current_theme.lower() == "dark":
            current_theme = "Dark"
        elif current_theme.lower() == "light":
            current_theme = "Light"
        elif current_theme.lower() == "system":
            current_theme = "System"
        theme_combo.setCurrentText(current_theme)
        # Style the theme combo with dropdown arrow
        dropdown_bg = '#2d2d2d' if c.get('bg_primary') == '#1e1e1e' else '#ffffff'
        theme_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {c['bg_primary']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 4px;
                padding-right: 18px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 18px;
                background-color: transparent;
            }}
            QComboBox QAbstractItemView {{
                background-color: {dropdown_bg};
                color: {c['text']};
                selection-background-color: {c['button']};
                selection-color: #ffffff;
            }}
        """)
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
        SettingsManager.follow_system_theme = SettingsManager.theme == "system"
        SettingsManager.ui_scale = ui_scale
        SettingsManager.save_settings()
        self._apply_theme_from_system()
        
        dialog.accept()
        
        # Check if UI scale changed
        if abs(ui_scale - old_ui_scale) > 0.01:
            custom_dialogs.information(self, "Success", 
                "Preferences saved!\n\n"
                "UI scale change requires app restart to take full effect.\n"
                "Please close and reopen the application.")
        else:
            custom_dialogs.information(self, "Success", "Preferences saved!")
    
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
            # Use Qt's native geometry saving (includes position, size, maximized state)
            geom_bytes = self.saveGeometry()
            SettingsManager.window_geometry = geom_bytes.toBase64().data().decode('ascii')
            
            # Save window state (docking, toolbars, etc)
            state_bytes = self.saveState()
            SettingsManager.window_state = state_bytes.toBase64().data().decode('ascii')
            
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
            # Restore Qt's native geometry (position, size, maximized state)
            if SettingsManager.window_geometry:
                try:
                    geom_bytes = QByteArray.fromBase64(SettingsManager.window_geometry.encode('ascii'))
                    self.restoreGeometry(geom_bytes)
                except Exception as e:
                    logger.debug(f"Error restoring geometry: {e}")
                    # Fallback to old size settings
                    if hasattr(SettingsManager, 'window_width'):
                        self.resize(SettingsManager.window_width, SettingsManager.window_height)
            elif hasattr(SettingsManager, 'window_width'):
                # Fallback for old settings format
                self.resize(SettingsManager.window_width, SettingsManager.window_height)
            
            # Restore window state (docking, toolbars, etc)
            if SettingsManager.window_state:
                try:
                    state_bytes = QByteArray.fromBase64(SettingsManager.window_state.encode('ascii'))
                    self.restoreState(state_bytes)
                except Exception as e:
                    logger.debug(f"Error restoring state: {e}")
            
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
    
    # Improve Wayland window management compatibility
    os.environ.setdefault('QT_QPA_PLATFORM_THEME', 'gnome')
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Apply theme palette to the application (critical for AppImage) - VS Code Modern themes
    theme = (SettingsManager.theme or "dark").lower()
    if theme == "dark":
        # VS Code Dark Modern palette
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))           # #1e1e1e
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(204, 204, 204))   # #cccccc
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))            # #1e1e1e
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(37, 37, 38))   # #252526
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(37, 37, 38))     # #252526
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(204, 204, 204))  # #cccccc
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(204, 204, 204))         # #cccccc
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 48))          # #2d2d30
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(204, 204, 204))   # #cccccc
        dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))       # Errors
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(58, 150, 221))          # #3a96dd
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(38, 79, 120))      # #264f78
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(133, 133, 133))  # #858585
        app.setPalette(dark_palette)
    
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

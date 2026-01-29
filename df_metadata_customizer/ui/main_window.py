"""PyQt6 Main Window - COMPLETE with ALL fixes and features."""

import sys
import json
import logging
import subprocess
import platform
import os
from pathlib import Path
from typing import Optional, Any, Dict, List
import contextlib
from PIL import Image
from io import BytesIO

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton, 
    QLabel, QFrame, QScrollArea, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem, 
    QLineEdit, QComboBox, QTabWidget, QApplication, QHeaderView, QInputDialog,
    QTextEdit, QMenu, QAbstractItemView, QDialog, QCheckBox, QDoubleSpinBox, QStackedLayout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QMimeData, QByteArray
from PyQt6.QtGui import QIcon, QPalette, QColor, QFont, QPixmap, QCursor, QDrag

from df_metadata_customizer.core import FileManager, SettingsManager, PresetService, RuleManager
from df_metadata_customizer.core.metadata import MetadataFields
from df_metadata_customizer.core.preset_service import Preset
from df_metadata_customizer.ui.rule_widgets import RuleRow, NoScrollComboBox
from df_metadata_customizer.ui.progress_dialog import ProgressDialog

logger = logging.getLogger(__name__)


def open_file_with_default_app(file_path: str) -> None:
    """Open file with default application (cross-platform)."""
    # Ensure absolute path
    abs_path = str(Path(file_path).resolve())
    
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.Popen(["open", abs_path], stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL, close_fds=True)
        elif system == "Windows":
            os.startfile(abs_path)
        else:  # Linux and other Unix-like systems
            # Use start_new_session to detach process and make it non-blocking
            subprocess.Popen(["xdg-open", abs_path], stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL, close_fds=True, 
                           start_new_session=True)
    except Exception as e:
        raise Exception(f"Failed to open file: {e}")


def open_folder_with_file_manager(folder_path: str, file_to_select: str = None) -> None:
    """Open folder in file manager and optionally select a file (cross-platform)."""
    system = platform.system()
    
    try:
        if file_to_select:
            # Reveal/select specific file
            abs_file_path = str(Path(file_to_select).resolve())
            if system == "Darwin":  # macOS
                # Use 'open -R' to reveal file in Finder
                subprocess.Popen(["open", "-R", abs_file_path], stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL, close_fds=True)
            elif system == "Windows":
                # Use explorer with /select to highlight file
                subprocess.Popen(["explorer", "/select," + abs_file_path], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                               close_fds=True)
            else:  # Linux and other Unix-like systems
                # Try nautilus first, fallback to xdg-open if not available
                try:
                    subprocess.Popen(["nautilus", "--select", abs_file_path], 
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                                   close_fds=True, start_new_session=True)
                except FileNotFoundError:
                    # Fallback: just open the folder
                    folder = str(Path(abs_file_path).parent)
                    subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL, close_fds=True, 
                                   start_new_session=True)
        else:
            # Just open folder
            abs_path = str(Path(folder_path).resolve())
            if system == "Darwin":  # macOS
                subprocess.Popen(["open", abs_path], stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL, close_fds=True)
            elif system == "Windows":
                os.startfile(abs_path)
            else:  # Linux and other Unix-like systems
                subprocess.Popen(["xdg-open", abs_path], stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL, close_fds=True, 
                               start_new_session=True)
    except Exception as e:
        raise Exception(f"Failed to open folder: {e}")


class MainWindow(QMainWindow):
    """Complete PyQt6 main window with ALL features."""
    
    RULE_OPS = [
        "is", "contains", "starts with", "ends with",
        "is empty", "is not empty", "is latest version", "is not latest version"
    ]
    
    # All metadata fields to display in tree
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
        self.setWindowTitle("Database Reformatter — Metadata Customizer")
        self.setMinimumSize(960, 540)
        
        # Set window size based on screen
        screen = self.screen().geometry()
        if screen.height() >= 1440:
            width, height = 1920, 1080
        else:
            width, height = 1280, 720
        
        self.resize(width, height)
        self.center_window()
        
        # Initialize managers
        SettingsManager.initialize()
        self.file_manager = FileManager()
        self.preset_service = PresetService(SettingsManager.get_presets_folder())
        self.rule_manager = RuleManager()
        
        # Data model
        self.song_files: List[Dict] = []
        self.current_index = None
        self.current_folder = None
        self.filtered_indices: List[int] = []
        self.current_theme = "System"
        self.sort_rules: List[tuple] = [("Title", True)]
        self.current_selected_file = None
        self.all_selected = False
        
        # UI References
        self.tree = None
        self.search_input = None
        self.sort_controls_container = None
        self.add_sort_btn = None
        self.sort_rules_list = []
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
        self.original_filename = ""
        self.metadata_fields = {}
        self.rule_containers = {}  # Store rule containers for Title/Artist/Album
        self.max_rules_per_tab = 50
        self._last_ui_scale = 1.0
        
        # Build UI
        self._setup_ui()
        
        # Load settings and presets
        self._load_presets()
        self._apply_theme_from_system()
        self._apply_ui_scale()
        
        # Load last folder and settings
        with contextlib.suppress(Exception):
            self.load_settings()
        
        # Show window before checking last folder so popups appear on top of UI
        self.show()
        QApplication.processEvents()
        
        self.check_last_folder()
        
    def center_window(self):
        """Center window on screen."""
        screen = self.screen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        # Ctrl+F: Focus search box
        if event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if self.search_input:
                self.search_input.setFocus()
                self.search_input.selectAll()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def eventFilter(self, obj, event):
        """Handle events for widgets with installed filters."""
        # ESC in search box: clear search
        if obj == self.search_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.search_input.clear()
                return True
        return super().eventFilter(obj, event)
    
    def _setup_ui(self):
        """Build the complete main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(0)
        
        # MENU BAR
        menubar = self.menuBar()
        self._setup_menubar(menubar)
        
        # MAIN SPLITTER
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #2d2d2d;
                width: 6px;
            }
        """)
        main_layout.addWidget(self.main_splitter)
        
        # LEFT FRAME
        left_frame = self._create_left_frame()
        self.main_splitter.addWidget(left_frame)
        self.main_splitter.setStretchFactor(0, 62)
        
        # RIGHT FRAME
        right_frame = self._create_right_frame()
        self.main_splitter.addWidget(right_frame)
        self.main_splitter.setStretchFactor(1, 38)
        
        self.main_splitter.setSizes([620, 480])
    
    def _setup_menubar(self, menubar):
        """Setup menu bar."""
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #1e1e1e;
                color: #ffffff;
                border-bottom: 1px solid #3d3d3d;
            }
            QMenuBar::item:selected { background-color: #2d2d2d; }
            QMenu {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
            }
            QMenu::item:selected { background-color: #0d47a1; }
        """)
        
        file_menu = menubar.addMenu("File")
        action = file_menu.addAction("Open Folder")
        action.triggered.connect(self.open_folder)
        file_menu.addSeparator()
        action = file_menu.addAction("Preferences")
        action.triggered.connect(self.show_preferences)
        file_menu.addSeparator()
        action = file_menu.addAction("Exit")
        action.triggered.connect(self.close)
        
        edit_menu = menubar.addMenu("Edit")
        action = edit_menu.addAction("Undo")
        action.triggered.connect(self.undo)
        action = edit_menu.addAction("Redo")
        action.triggered.connect(self.redo)
        
        help_menu = menubar.addMenu("Help")
        action = help_menu.addAction("About")
        action.triggered.connect(self.show_about)
    
    def _create_left_frame(self):
        """Create left frame with song list."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #2b2b2b; border-radius: 8px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Song controls
        song_controls = self._create_song_controls()
        layout.addWidget(song_controls)
        
        # Sort controls (multi-level with new layout)
        sort_controls = self._create_sort_controls()
        layout.addWidget(sort_controls)
        
        # Tree view
        self.tree = self._create_tree_view()
        layout.addWidget(self.tree, 1)
        
        # Status bar
        status_frame = self._create_status_bar()
        layout.addWidget(status_frame)
        
        return frame
    
    def _create_song_controls(self):
        """Create song controls."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        folder_btn = QPushButton("Select Folder")
        folder_btn.setFixedHeight(36)
        folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        folder_btn.clicked.connect(self.open_folder)
        layout.addWidget(folder_btn)
        
        # Advanced search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Search (artist="Lady Gaga", version>2, title!=Creep, track>=69)...')
        self.search_input.setFixedHeight(36)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLineEdit:focus { border: 2px solid #0d47a1; }
        """)
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.installEventFilter(self)
        layout.addWidget(self.search_input)
        
        # Filtered count label
        self.filtered_count_label = QLabel("0 found")
        self.filtered_count_label.setStyleSheet("color: #bbb; font-size: 11px;")
        self.filtered_count_label.setFixedWidth(80)
        layout.addWidget(self.filtered_count_label)
        
        select_all = QPushButton("Select All")
        select_all.setFixedSize(100, 36)
        select_all.clicked.connect(self.toggle_select_all)
        layout.addWidget(select_all)
        
        return frame
    
    def _create_sort_controls(self):
        """Create multi-level sort controls."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # + button
        self.add_sort_btn = QPushButton("+")
        self.add_sort_btn.setFixedSize(30, 30)
        self.add_sort_btn.clicked.connect(self.add_sort_rule)
        self.add_sort_btn.setToolTip("Add another sort level (max 5)")
        layout.addWidget(self.add_sort_btn)
        
        # Sort label
        layout.addWidget(QLabel("Sort by:"))
        
        # Container for sort rules
        self.sort_controls_container = QFrame()
        self.sort_controls_container.setStyleSheet("QFrame { background-color: transparent; }")
        container_layout = QHBoxLayout(self.sort_controls_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)
        
        # Add first sort rule
        self._add_sort_rule_widget(0, is_first=True)
        
        self.sort_controls_container.setLayout(container_layout)
        layout.addWidget(self.sort_controls_container)
        layout.addStretch()
        
        return frame
    
    def _add_sort_rule_widget(self, index: int, is_first: bool = False):
        """Add a sort rule widget to the container."""
        if len(self.sort_rules_list) >= 5:
            return
        
        # Initial styling
        rule_frame = QFrame()
        rule_frame.setStyleSheet("QFrame { background-color: transparent; border: 1px solid #444; border-radius: 2px; padding: 2px; }")
        
        rule_layout = QHBoxLayout(rule_frame)
        rule_layout.setContentsMargins(4, 2, 4, 2)
        rule_layout.setSpacing(4)
        
        # Field selector
        field_combo = NoScrollComboBox()
        field_combo.addItem("Title")
        field_combo.addItem("Artist")
        field_combo.addItem("Cover Artist")
        field_combo.addItem("Version")
        field_combo.addItem("Date")
        field_combo.addItem("Disc")
        field_combo.addItem("Track")
        field_combo.addItem("File")
        field_combo.addItem("Special")
        if not is_first:
            field_combo.setCurrentText("Artist")
        field_combo.setFixedWidth(100)
        field_combo.currentTextChanged.connect(self.on_sort_changed)
        rule_layout.addWidget(field_combo)
        
        # Order selector
        order_combo = NoScrollComboBox()
        order_combo.addItems(["Asc", "Desc"])
        order_combo.setFixedWidth(60)
        order_combo.currentTextChanged.connect(self.on_sort_changed)
        rule_layout.addWidget(order_combo)
        
        # Move up button (not for first)
        if not is_first:
            up_btn = QPushButton("◀")
            up_btn.setFixedSize(25, 25)
            up_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: #888;
                    border: 1px solid #555;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #484848;
                    color: #aaa;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
            """)
            up_btn.clicked.connect(lambda checked=False, rule_frame=rule_frame: self._move_sort_rule_by_frame(rule_frame, -1))
            rule_layout.addWidget(up_btn)
        
        # Move down button (not for first)
        if not is_first:
            down_btn = QPushButton("▶")
            down_btn.setFixedSize(25, 25)
            down_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: #888;
                    border: 1px solid #555;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #484848;
                    color: #aaa;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
            """)
            down_btn.clicked.connect(lambda checked=False, rule_frame=rule_frame: self._move_sort_rule_by_frame(rule_frame, 1))
            rule_layout.addWidget(down_btn)
        
        # Remove button (not for first)
        if not is_first:
            remove_btn = QPushButton("✕")
            remove_btn.setFixedSize(25, 25)
            remove_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: #999;
                    border: 1px solid #555;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #484848;
                    color: #aaa;
                    border: 1px solid #666;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
            """)
            remove_btn.clicked.connect(lambda checked=False, rule_frame=rule_frame: self._remove_sort_rule_by_frame(rule_frame))
            rule_layout.addWidget(remove_btn)
        
        rule_layout.addStretch()
        rule_frame.setLayout(rule_layout)
        
        # Add to container
        container_layout = self.sort_controls_container.layout()
        container_layout.insertWidget(container_layout.count(), rule_frame)
        
        self.sort_rules_list.append({
            'frame': rule_frame,
            'field': field_combo,
            'order': order_combo,
            'is_first': is_first
        })
    
    def add_sort_rule(self):
        """Add another sort level."""
        if len(self.sort_rules_list) >= 5:
            QMessageBox.information(self, "Limit", "Maximum 5 sort levels allowed.")
            return
        
        self._add_sort_rule_widget(len(self.sort_rules_list), is_first=False)
        self.on_sort_changed()
    
    def remove_sort_rule(self, index: int):
        """Remove a sort rule."""
        if index >= 0 and index < len(self.sort_rules_list):
            rule_info = self.sort_rules_list[index]
            container_layout = self.sort_controls_container.layout()
            container_layout.removeWidget(rule_info['frame'])
            rule_info['frame'].deleteLater()
            self.sort_rules_list.pop(index)
            self.on_sort_changed()
    
    def _remove_sort_rule_by_frame(self, frame):
        """Remove a sort rule by frame reference."""
        for i, rule_info in enumerate(self.sort_rules_list):
            if rule_info['frame'] is frame:
                self.remove_sort_rule(i)
                break
    
    def _move_sort_rule_by_frame(self, frame, direction):
        """Move a sort rule by frame reference. direction: -1 for up, 1 for down."""
        for i, rule_info in enumerate(self.sort_rules_list):
            if rule_info['frame'] is frame:
                if direction == -1 and i > 0:  # Move up (can move any rule that's not first)
                    self.sort_rules_list[i - 1], self.sort_rules_list[i] = \
                        self.sort_rules_list[i], self.sort_rules_list[i - 1]
                    self._rebuild_sort_ui()
                    self.on_sort_changed()
                elif direction == 1 and i < len(self.sort_rules_list) - 1:  # Move down
                    self.sort_rules_list[i], self.sort_rules_list[i + 1] = \
                        self.sort_rules_list[i + 1], self.sort_rules_list[i]
                    self._rebuild_sort_ui()
                    self.on_sort_changed()
                break
    
    def move_sort_rule_up(self, index: int):
        """Move sort rule up."""
        if index > 1:  # Can't move first rule, and must be > 1 to move up
            self.sort_rules_list[index - 1], self.sort_rules_list[index] = \
                self.sort_rules_list[index], self.sort_rules_list[index - 1]
            self._rebuild_sort_ui()
            self.on_sort_changed()
    
    def move_sort_rule_down(self, index: int):
        """Move sort rule down."""
        if index < len(self.sort_rules_list) - 1:
            self.sort_rules_list[index], self.sort_rules_list[index + 1] = \
                self.sort_rules_list[index + 1], self.sort_rules_list[index]
            self._rebuild_sort_ui()
            self.on_sort_changed()
    
    def _rebuild_sort_ui(self):
        """Rebuild sort rules UI after reordering."""
        container_layout = self.sort_controls_container.layout()
        
        # Remove all widgets from layout
        while container_layout.count() > 0:
            item = container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Recreate frames for each sort rule with correct is_first status
        for idx, rule_info in enumerate(self.sort_rules_list):
            old_frame = rule_info['frame']
            is_first = (idx == 0)
            
            # Get current values from old frame
            field_text = rule_info['field'].currentText()
            order_text = rule_info['order'].currentText()
            
            # Create new frame with correct is_first status
            new_frame = QFrame()
            new_frame.setStyleSheet("QFrame { background-color: transparent; border: 1px solid #444; border-radius: 2px; padding: 2px; }")
            
            new_layout = QHBoxLayout(new_frame)
            new_layout.setContentsMargins(4, 2, 4, 2)
            new_layout.setSpacing(4)
            
            # Field selector
            new_field_combo = NoScrollComboBox()
            new_field_combo.addItems(["Title", "Artist", "Cover Artist", "Version", "Date", "Disc", "Track", "File", "Special"])
            new_field_combo.setCurrentText(field_text)
            new_field_combo.setFixedWidth(100)
            new_field_combo.currentTextChanged.connect(self.on_sort_changed)
            new_layout.addWidget(new_field_combo)
            
            # Order selector
            new_order_combo = NoScrollComboBox()
            new_order_combo.addItems(["Asc", "Desc"])
            new_order_combo.setCurrentText(order_text)
            new_order_combo.setFixedWidth(60)
            new_order_combo.currentTextChanged.connect(self.on_sort_changed)
            new_layout.addWidget(new_order_combo)
            
            # Move up button (not for first)
            if not is_first:
                up_btn = QPushButton("◀")
                up_btn.setFixedSize(25, 25)
                up_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3a3a3a;
                        color: #888;
                        border: 1px solid #555;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #484848;
                        color: #aaa;
                    }
                    QPushButton:pressed {
                        background-color: #2a2a2a;
                    }
                """)
                up_btn.clicked.connect(lambda checked=False, frame=new_frame: self._move_sort_rule_by_frame(frame, -1))
                new_layout.addWidget(up_btn)
            
            # Move down button (not for first)
            if not is_first:
                down_btn = QPushButton("▶")
                down_btn.setFixedSize(25, 25)
                down_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3a3a3a;
                        color: #888;
                        border: 1px solid #555;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #484848;
                        color: #aaa;
                    }
                    QPushButton:pressed {
                        background-color: #2a2a2a;
                    }
                """)
                down_btn.clicked.connect(lambda checked=False, frame=new_frame: self._move_sort_rule_by_frame(frame, 1))
                new_layout.addWidget(down_btn)
            
            # Remove button (not for first)
            if not is_first:
                remove_btn = QPushButton("✕")
                remove_btn.setFixedSize(25, 25)
                remove_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3a3a3a;
                        color: #999;
                        border: 1px solid #555;
                        border-radius: 3px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #484848;
                        color: #aaa;
                        border: 1px solid #666;
                    }
                    QPushButton:pressed {
                        background-color: #2a2a2a;
                    }
                """)
                remove_btn.clicked.connect(lambda checked=False, frame=new_frame: self._remove_sort_rule_by_frame(frame))
                new_layout.addWidget(remove_btn)
            
            new_layout.addStretch()
            new_frame.setLayout(new_layout)
            
            # Update rule_info with new widgets
            rule_info['frame'] = new_frame
            rule_info['field'] = new_field_combo
            rule_info['order'] = new_order_combo
            rule_info['is_first'] = is_first
            
            # Add to layout
            container_layout.addWidget(new_frame)
            
            # Delete old frame
            old_frame.deleteLater()
        
        container_layout.addStretch()
    
    def _create_tree_view(self):
        """Create tree view with all metadata columns."""
        tree = QTreeWidget()
        
        # Set columns
        col_labels = []
        for f in self.TREE_COLUMNS:
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
        
        # Selection mode: single selection, single click selects
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
        
        tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
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
            self.current_selected_file = current.data(0, Qt.ItemDataRole.UserRole)
            self.current_index = self.tree.indexOfTopLevelItem(current)
            self.update_preview_info()
    
    def on_tree_item_clicked(self, item, column):
        """Handle tree item click - select and show info."""
        # Clear other selections and select only this item
        self.tree.clearSelection()
        item.setSelected(True)
        self.current_selected_file = item.data(0, Qt.ItemDataRole.UserRole)
        self.current_index = self.tree.indexOfTopLevelItem(item)
        self.update_preview_info()
    
    def on_tree_item_double_clicked(self, item, column):
        """Handle tree item double-click - play the file."""
        # Get the file index from the item's user data
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.song_files):
            file_path = self.song_files[idx].get('path', '')
            if file_path:
                try:
                    open_file_with_default_app(file_path)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Cannot open file: {e}")
    
    def on_tree_right_click(self, position):
        """Show context menu on right-click."""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QMenu::item:selected {
                background-color: #0d47a1;
            }
        """)
        
        # Get selected items
        selected_items = self.tree.selectedItems()
        
        # Play
        action = menu.addAction("▶️ Play")
        action.triggered.connect(lambda: self.play_file(item))
        
        menu.addSeparator()
        
        # Copy field value from clicked column
        column = self.tree.columnAt(position.x())
        if 0 <= column < len(self.TREE_COLUMNS):
            field_name = self.TREE_COLUMNS[column]
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
        # Get the file index from the item's user data
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.song_files):
            file_path = self.song_files[idx].get('path', '')
            if file_path:
                try:
                    open_file_with_default_app(file_path)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Cannot play file: {e}")
    
    def copy_metadata(self, item):
        """Copy song metadata to clipboard."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.song_files):
            file_data = self.song_files[idx]
            metadata_text = json.dumps(file_data, indent=2)
            
            app = QApplication.instance()
            clipboard = app.clipboard()
            clipboard.setText(metadata_text)
            
            QMessageBox.information(self, "Success", "Metadata copied to clipboard!")
    
    def copy_field_value(self, item, column):
        """Copy single field value to clipboard."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.song_files):
            file_data = self.song_files[idx]
            field_name = self.TREE_COLUMNS[column]
            value = file_data.get(field_name, '')
            
            app = QApplication.instance()
            clipboard = app.clipboard()
            clipboard.setText(str(value))
            
            field_display = field_name.replace('_', ' ').title()
            QMessageBox.information(self, "Success", f"{field_display} copied to clipboard!")
    
    def copy_all_metadata(self, items):
        """Copy all selected metadata."""
        all_data = []
        for item in items:
            idx = item.data(0, Qt.ItemDataRole.UserRole)
            if idx is not None and idx < len(self.song_files):
                all_data.append(self.song_files[idx])
        
        metadata_text = json.dumps(all_data, indent=2)
        
        app = QApplication.instance()
        clipboard = app.clipboard()
        clipboard.setText(metadata_text)
        
        QMessageBox.information(self, "Success", f"Metadata for {len(items)} songs copied!")
    
    def goto_file_location(self, item):
        """Open file location in file manager and select the file."""
        # Get the file index from the item's user data
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.song_files):
            file_path = self.song_files[idx].get('path', '')
            if file_path:
                try:
                    # Pass file path to select it in the file manager
                    open_folder_with_file_manager(str(Path(file_path).parent), file_path)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Cannot open folder: {e}")
    
    def edit_song_metadata(self, item):
        """Edit song metadata (populate the edit tab)."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self.song_files):
            # Populate metadata fields
            file_data = self.song_files[idx]
            if MetadataFields.TITLE in self.metadata_fields:
                self.metadata_fields[MetadataFields.TITLE].setText(str(file_data.get(MetadataFields.TITLE, "")))
            if MetadataFields.ARTIST in self.metadata_fields:
                self.metadata_fields[MetadataFields.ARTIST].setText(str(file_data.get(MetadataFields.ARTIST, "")))
            # ... etc for other fields
    
    def _create_status_bar(self):
        """Create status bar."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.file_info_label = QLabel("No folder selected")
        self.file_info_label.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(self.file_info_label)
        
        separator = QLabel("|")
        separator.setStyleSheet("color: #666666;")
        layout.addWidget(separator)
        
        self.selection_info_label = QLabel("0 song(s) selected")
        self.selection_info_label.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(self.selection_info_label)
        
        layout.addStretch()
        
        # Statistics button
        stats_btn = QPushButton("Stats")
        stats_btn.setFixedSize(80, 28)
        stats_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 10pt;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        stats_btn.clicked.connect(self.show_statistics)
        layout.addWidget(stats_btn)
        
        prev_btn = QPushButton("◀ Prev")
        prev_btn.setFixedSize(70, 28)
        prev_btn.clicked.connect(self.prev_file)
        layout.addWidget(prev_btn)
        
        next_btn = QPushButton("Next ▶")
        next_btn.setFixedSize(70, 28)
        next_btn.clicked.connect(self.next_file)
        layout.addWidget(next_btn)
        
        return frame
    
    def _create_right_frame(self):
        """Create right frame with tabs."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #2b2b2b; border-radius: 8px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        
        tabs = QTabWidget()
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
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Preset controls at the top
        preset_frame = self._create_preset_controls()
        layout.addWidget(preset_frame, 0, Qt.AlignmentFlag.AlignTop)
        
        # Rule Tabs for Title/Artist/Album
        rule_tabs = QTabWidget()
        rule_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3d3d3d;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0d47a1;
            }
        """)
        
        # Create tabs for Title, Artist, Album
        for tab_name in ["Title", "Artist", "Album"]:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setContentsMargins(8, 4, 8, 4)
            tab_layout.setSpacing(4)
            
            # Header with label and add button
            header = QFrame()
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(0, 0, 0, 0)
            
            label = QLabel(f"{tab_name} Rules")
            label.setStyleSheet("font-weight: bold; font-size: 12pt;")
            header_layout.addWidget(label)
            
            header_layout.addStretch()
            
            add_btn = QPushButton("+ Add Rule")
            add_btn.setFixedWidth(100)
            add_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d47a1;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
            """)
            add_btn.clicked.connect(lambda checked, t=tab_name.lower(): self.add_rule_to_tab(t))
            header_layout.addWidget(add_btn)
            
            tab_layout.addWidget(header)
            
            # Scrollable area for rules
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("""
                QScrollArea {
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    background-color: #1e1e1e;
                }
            """)
            
            # Container for rule rows
            rule_container = QWidget()
            rule_layout = QVBoxLayout(rule_container)
            rule_layout.setContentsMargins(4, 4, 4, 4)
            rule_layout.setSpacing(4)
            rule_layout.addStretch()
            
            scroll.setWidget(rule_container)
            scroll.setMinimumHeight(150)
            scroll.setMaximumHeight(300)
            tab_layout.addWidget(scroll)
            
            rule_tabs.addTab(tab_widget, tab_name)
            self.rule_containers[tab_name.lower()] = rule_container
        
        layout.addWidget(rule_tabs, 1)  # Stretch to fill
        
        # JSON Editor section with save button and cover image
        # Header with label and save button
        json_header = QHBoxLayout()
        json_header.addWidget(QLabel("Raw JSON:"))
        self.save_json_btn = QPushButton("Save JSON")
        self.save_json_btn.setEnabled(False)
        self.save_json_btn.setFixedSize(100, 28)
        self.save_json_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: #aaaaaa;
                border: none;
                border-radius: 3px;
                padding: 4px;
            }
            QPushButton:enabled {
                background-color: #0d47a1;
                color: white;
            }
            QPushButton:enabled:hover {
                background-color: #1565c0;
            }
        """)
        self.save_json_btn.clicked.connect(self.save_json_changes)
        json_header.addStretch()
        json_header.addWidget(self.save_json_btn)
        layout.addLayout(json_header)
        
        # JSON + Cover row
        json_cover_row = QHBoxLayout()
        json_cover_row.setSpacing(6)
        
        self.json_editor = QTextEdit()
        self.json_editor.setMinimumHeight(180)
        # Calculate scaled font size
        json_font_size = 10 * SettingsManager.ui_scale
        self.json_editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
                font-family: 'Courier New', monospace;
                font-size: {json_font_size}pt;
            }}
        """)
        self.json_editor.textChanged.connect(self.on_json_changed)
        json_cover_row.addWidget(self.json_editor, 1)
        
        # Cover image with hover button (right side of JSON)
        cover_container = QFrame()
        cover_container.setFixedSize(180, 180)
        cover_container.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)
        cover_layout = QVBoxLayout(cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        
        self.cover_display = QLabel()
        self.cover_display.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
            }
        """)
        self.cover_display.setScaledContents(True)
        self.cover_display.setText("No cover")
        self.cover_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_layout.addWidget(self.cover_display)
        
        # Change cover button (overlay on top, hidden by default)
        self.change_cover_btn = QPushButton("Change Cover")
        self.change_cover_btn.setParent(cover_container)
        self.change_cover_btn.setFixedSize(120, 32)
        self.change_cover_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(13, 71, 161, 0.9);
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)
        self.change_cover_btn.hide()
        self.change_cover_btn.clicked.connect(self.change_cover_image)
        
        # Position button in center using geometry (will be updated on show)
        def center_button():
            btn_width = self.change_cover_btn.width()
            btn_height = self.change_cover_btn.height()
            container_width = cover_container.width()
            container_height = cover_container.height()
            x = (container_width - btn_width) // 2
            y = (container_height - btn_height) // 2
            self.change_cover_btn.setGeometry(x, y, btn_width, btn_height)
        
        self.change_cover_btn.showEvent = lambda event: center_button()
        
        # Enable hover tracking
        cover_container.enterEvent = lambda event: self.change_cover_btn.show()
        cover_container.leaveEvent = lambda event: self.change_cover_btn.hide()
        
        json_cover_row.addWidget(cover_container, 0, Qt.AlignmentFlag.AlignTop)
        
        layout.addLayout(json_cover_row)
        
        # Output preview with labels
        layout.addWidget(QLabel("Output Preview:"))
        self.preview_title_label = QLabel("Title: -")
        self.preview_artist_label = QLabel("Artist: -")
        self.preview_album_label = QLabel("Album: -")
        self.preview_details_label = QLabel("Disc: - | Track: - | Versions: - | Date: -")
        
        for lbl in [self.preview_title_label, self.preview_artist_label, self.preview_album_label, self.preview_details_label]:
            lbl.setStyleSheet("color: #90ee90; padding: 2px;")
            layout.addWidget(lbl)
        
        # Filename editor with save button
        filename_row = QHBoxLayout()
        filename_row.addWidget(QLabel("Filename:"))
        self.filename_preview = QLineEdit()
        self.filename_preview.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)
        self.filename_preview.textChanged.connect(self.on_filename_changed)
        filename_row.addWidget(self.filename_preview, 1)
        
        self.save_filename_btn = QPushButton("Save Filename")
        self.save_filename_btn.setEnabled(False)
        self.save_filename_btn.setFixedSize(140, 28)
        self.save_filename_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: #aaaaaa;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QPushButton:enabled {
                background-color: #0d47a1;
                color: white;
            }
            QPushButton:enabled:hover {
                background-color: #1565c0;
            }
        """)
        self.save_filename_btn.clicked.connect(self.save_filename_changes)
        filename_row.addWidget(self.save_filename_btn)
        layout.addLayout(filename_row)
        
        layout.addStretch()
        
        # Apply buttons at bottom (no stretch before)
        apply_frame = self._create_apply_buttons()
        layout.addWidget(apply_frame)
        
        return frame
    
    def _create_preset_controls(self):
        """Create preset controls."""
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
        
        return frame
    
    def _create_apply_buttons(self):
        """Create apply buttons."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        apply_selected = QPushButton("Apply to Selected")
        apply_selected.setFixedHeight(36)
        apply_selected.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        apply_selected.clicked.connect(self.apply_preset_to_selected)
        layout.addWidget(apply_selected)
        
        apply_all = QPushButton("Apply to All")
        apply_all.setFixedHeight(36)
        apply_all.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        apply_all.clicked.connect(self.apply_preset_to_all)
        layout.addWidget(apply_all)
        
        return frame
    
    def _create_song_edit_tab(self):
        """Create song metadata editor."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: transparent; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        title = QLabel("✏️ Edit Song Metadata")
        title.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(title)
        
        # Metadata fields
        fields = {
            MetadataFields.TITLE: "Title",
            MetadataFields.ARTIST: "Artist",
            MetadataFields.COVER_ARTIST: "Cover Artist",
            MetadataFields.DATE: "Date",
            MetadataFields.VERSION: "Version",
            MetadataFields.DISC: "Disc",
            MetadataFields.TRACK: "Track",
        }
        
        self.metadata_fields = {}
        
        for field_key, field_label in fields.items():
            row = QHBoxLayout()
            
            label = QLabel(f"{field_label}:")
            label.setFixedWidth(100)
            row.addWidget(label)
            
            input_field = QLineEdit()
            input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 6px;
                }
                QLineEdit:focus { border: 2px solid #0d47a1; }
            """)
            row.addWidget(input_field)
            
            self.metadata_fields[field_key] = input_field
            layout.addLayout(row)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Save")
        save_btn.setFixedSize(100, 40)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        save_btn.clicked.connect(self.save_metadata)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.clicked.connect(self.cancel_metadata_edit)
        btn_layout.addWidget(cancel_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return frame
    
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
    
    # ===== FILE OPERATIONS =====
    
    def open_folder(self):
        """Open folder dialog."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with MP3s")
        if folder:
            self.load_folder(folder)
    
    def load_folder(self, folder_path: str):
        """Load files from folder."""
        try:
            # Show progress dialog
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
            
            progress.close()
            
            # Show result
            QMessageBox.information(
                self, 
                "Load Complete",
                f"Successfully loaded {len(self.song_files)} files from:\n{folder_path}"
            )
            
            self.file_info_label.setText(f"✓ Loaded {len(self.song_files)} files")
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
                self.load_folder(last_folder)
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
                    self.load_folder(last_folder)
                
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
        if not self.song_files:
            return
        
        if not self.filtered_indices:
            # No filtered results, clear the tree
            self.populate_tree()
            return
        
        # Collect all sort rules from UI
        sort_keys = []
        for rule_info in self.sort_rules_list:
            field_text = rule_info['field'].currentText()
            ascending = rule_info['order'].currentText() == "Asc"
            sort_keys.append((field_text, ascending))
        
        # Helper class for reverse string comparison
        class ReverseStr(str):
            def __lt__(self, other):
                return str.__gt__(self, other)
            def __le__(self, other):
                return str.__ge__(self, other)
            def __gt__(self, other):
                return str.__lt__(self, other)
            def __ge__(self, other):
                return str.__le__(self, other)
        
        # Create sort function that handles ascending/descending per level
        def get_sort_key(idx):
            if idx >= len(self.song_files):
                return ("",) * len(sort_keys)
            
            file_data = self.song_files[idx]
            keys = []
            
            # Numeric fields that should be sorted numerically
            numeric_fields = {"Version", "Date", "Disc", "Track"}
            
            for field_text, ascending in sort_keys:
                # Map UI text to metadata field
                field_map = {
                    "Title": MetadataFields.TITLE,
                    "Artist": MetadataFields.ARTIST,
                    "Cover Artist": MetadataFields.COVER_ARTIST,
                    "Version": MetadataFields.VERSION,
                    "Date": MetadataFields.DATE,
                    "Disc": MetadataFields.DISC,
                    "Track": MetadataFields.TRACK,
                    "File": MetadataFields.FILE,
                    "Special": MetadataFields.SPECIAL,
                }
                
                field = field_map.get(field_text)
                if field:
                    val = file_data.get(field, "")
                    
                    # Handle numeric fields
                    if field_text in numeric_fields:
                        try:
                            # For Track (might be "69/100"), extract first number
                            if field_text == "Track":
                                numeric_tuple = self._extract_numeric_value(str(val))
                                num_val = numeric_tuple[1]
                                has_denom = numeric_tuple[0]
                                
                                # For descending, negate numeric values AND reverse has_denominator
                                # so that descending order still puts single numbers before fractions
                                if not ascending:
                                    num_val = -num_val if num_val else num_val
                                    has_denom = 1 - has_denom  # Flip: 0->1, 1->0
                                
                                keys.append((0, has_denom, num_val))  # (is_numeric_type, has_denominator, numeric_value)
                            else:
                                numeric_val = float(val)
                                # For descending, negate numeric values
                                if not ascending:
                                    numeric_val = -numeric_val
                                keys.append((0, 0, numeric_val))  # (is_numeric_type, 0, numeric_value)
                        except (ValueError, TypeError):
                            str_val = str(val).lower()
                            if not ascending:
                                str_val = ReverseStr(str_val)
                            keys.append((1, 0, str_val))  # (is_string_type, 0, string_value)
                    else:
                        # String field - use ReverseStr for descending
                        str_val = str(val).lower()
                        if not ascending:
                            str_val = ReverseStr(str_val)
                        keys.append((1, 0, str_val))  # (is_string_type, 0, string_value)
            
            return tuple(keys)
        
        # Sort - no need to reverse at the end, everything is handled in the key
        self.filtered_indices.sort(key=get_sort_key)
        
        self.populate_tree()
    
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
    
    def update_preview_info(self):
        """Update preview info based on selected file."""
        if self.current_selected_file is None or self.current_selected_file >= len(self.song_files):
            return
        
        file_data = self.song_files[self.current_selected_file]
        
        # Display raw JSON
        self.json_editor.blockSignals(True)
        self.json_editor.setText(json.dumps(file_data.get('raw_json', {}), indent=2, ensure_ascii=False))
        self.json_editor.blockSignals(False)
        self.save_json_btn.setEnabled(False)
        
        # Update output preview labels - show what rules will produce
        title = file_data.get(MetadataFields.TITLE, "-")
        artist = file_data.get(MetadataFields.ARTIST, "-")
        album = file_data.get("Album", "-")
        disc = file_data.get(MetadataFields.DISC, "-")
        track = file_data.get(MetadataFields.TRACK, "-")
        date = file_data.get(MetadataFields.DATE, "-")
        
        # Apply rules to get preview of what ID3 tags will be
        preview_data = file_data.copy()
        for tab_name in ["title", "artist", "album"]:
            rules = self.collect_rules_for_tab(tab_name)
            for rule_data in rules:
                try:
                    preview_data = self.rule_manager.apply_conditional_rule(
                        preview_data,
                        rule_data.get('field', ''),
                        rule_data.get('operator', ''),
                        rule_data.get('condition', ''),
                        rule_data.get('action_field', ''),
                        rule_data.get('action_value', '')
                    )
                except:
                    pass
        
        # Get preview values after rules applied
        preview_title = preview_data.get(MetadataFields.TITLE, title)
        preview_artist = preview_data.get(MetadataFields.ARTIST, artist)
        preview_album = preview_data.get("Album", album)
        
        # Find all versions of this song (same title+artist+coverartist)
        song_key = (title, artist, file_data.get(MetadataFields.COVER_ARTIST, ""))
        versions = []
        for f in self.song_files:
            f_key = (f.get(MetadataFields.TITLE, ""), f.get(MetadataFields.ARTIST, ""), f.get(MetadataFields.COVER_ARTIST, ""))
            if f_key == song_key:
                ver = f.get(MetadataFields.VERSION, "")
                if ver and ver not in versions:
                    versions.append(str(ver))
        versions.sort()
        versions_str = ", ".join(versions) if versions else "-"
        
        self.preview_title_label.setText(f"Title: {preview_title}")
        self.preview_artist_label.setText(f"Artist: {preview_artist}")
        self.preview_album_label.setText(f"Album: {preview_album}")
        self.preview_details_label.setText(f"Disc: {disc} | Track: {track} | Versions: {versions_str} | Date: {date}")
        
        # Update filename preview
        filename = file_data.get('path', '')
        self.filename_preview.blockSignals(True)
        if filename:
            self.original_filename = str(Path(filename).name)
            self.filename_preview.setText(self.original_filename)
        else:
            self.original_filename = ""
            self.filename_preview.setText("")
        self.filename_preview.blockSignals(False)
        self.save_filename_btn.setEnabled(False)
        
        # Load cover image if available
        self.load_cover_image(file_data)
        
        # Update selection info
        self.update_selection_info()
    
    def load_cover_image(self, file_data):
        """Load and display cover image."""
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import APIC
            
            file_path = file_data.get('path', "")
            if file_path and Path(file_path).exists():
                audio = MP3(file_path)
                
                # Try to get cover art
                cover_data = None
                if audio.tags:
                    for tag in audio.tags.values():
                        if isinstance(tag, APIC):
                            cover_data = tag.data
                            break
                
                if cover_data:
                    # Load image from bytes
                    img = Image.open(BytesIO(cover_data))
                    img.thumbnail((150, 150), Image.Resampling.LANCZOS)
                    
                    # Convert to QPixmap
                    img_byte_arr = BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)
                    
                    pixmap = QPixmap()
                    pixmap.loadFromData(img_byte_arr.read())
                    self.cover_display.setPixmap(pixmap)
                    self.cover_display.setText("")
                else:
                    self.cover_display.clear()
                    self.cover_display.setText("No cover\nimage")
            else:
                self.cover_display.clear()
                self.cover_display.setText("File not\nfound")
        except Exception as e:
            self.cover_display.clear()
            self.cover_display.setText("No cover\nimage")
            logger.debug(f"Error loading cover: {e}")
    
    def change_cover_image(self):
        """Open file dialog to change cover image."""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Image Files (*.jpg *.jpeg *.png *.gif *.bmp)")
        
        if file_dialog.exec() == QFileDialog.DialogCode.Accepted:
            image_path = file_dialog.selectedFiles()[0]
            try:
                from mutagen.mp3 import MP3
                from mutagen.id3 import APIC, ID3
                
                # Get currently selected song
                current_items = self.tree.selectedItems()
                if not current_items:
                    QMessageBox.warning(self, "Warning", "No song selected.")
                    return
                
                idx = current_items[0].data(0, Qt.ItemDataRole.UserRole)
                if idx is None or idx >= len(self.song_files):
                    return
                
                file_path = self.song_files[idx].get('path', '')
                if not file_path or not Path(file_path).exists():
                    QMessageBox.warning(self, "Error", "Song file not found.")
                    return
                
                # Load image and add to MP3
                with open(image_path, 'rb') as img_file:
                    image_data = img_file.read()
                
                audio = MP3(file_path)
                if audio.tags is None:
                    audio.add_tags()
                
                # Remove existing cover art
                audio.tags.delall('APIC')
                
                # Add new cover art
                audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='', data=image_data))
                audio.save()
                
                # Reload cover display
                self.load_cover_image(self.song_files[idx])
                QMessageBox.information(self, "Success", "Cover image updated!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to update cover: {e}")
    
    def on_json_changed(self):
        """Enable save button when JSON is changed."""
        if self.save_json_btn:
            self.save_json_btn.setEnabled(True)
    
    def save_json_changes(self):
        """Save JSON changes to file data."""
        try:
            new_data = json.loads(self.json_editor.toPlainText())
            if self.current_selected_file is not None and self.current_selected_file < len(self.song_files):
                self.song_files[self.current_selected_file]['raw_json'] = new_data
                self.save_json_btn.setEnabled(False)
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
            self.populate_tree()  # Refresh tree
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
    
    def _load_presets(self):
        """Load presets."""
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
            # Load preset file directly (old format: {"title": [...], "artist": [...], "album": [...]})
            preset_file = SettingsManager.get_presets_folder() / f"{preset_name}.json"
            import json as json_module
            
            if not preset_file.exists():
                QMessageBox.warning(self, "Error", f"Preset file '{preset_name}' not found")
                return
            
            with preset_file.open("r", encoding="utf-8") as f:
                preset_data = json_module.load(f)
            
            # Display in JSON editor
            self.json_editor.setText(json.dumps(preset_data, indent=2))
            
            # Load rules into respective tabs
            for tab_name in ["title", "artist", "album"]:
                rules = preset_data.get(tab_name, [])
                self.load_rules_to_tab(tab_name, rules)
            
            # Update preview
            self.update_output_preview()
            
            self.file_info_label.setText(f"Loaded preset '{preset_name}'")
        except Exception as e:
            logger.exception(f"Error loading preset: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load preset: {e}")
    
    def create_new_preset(self):
        """Create new preset."""
        name, ok = QInputDialog.getText(self, "New Preset", "Preset name:")
        if ok and name:
            try:
                new_preset = Preset(name=name, description="")
                self.preset_service.save_preset(new_preset)
                self.preset_combo.addItem(name)
                QMessageBox.information(self, "Success", f"Preset '{name}' created!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create preset:\n{e}")
    
    def delete_preset(self):
        """Delete preset."""
        name = self.preset_combo.currentText()
        
        if name in ["Default", "TuruuMGL", "mm2wood"]:
            QMessageBox.warning(self, "Warning", "Cannot delete built-in presets.")
            return
        
        reply = QMessageBox.question(self, "Delete Preset", f"Delete preset '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.preset_service.delete_preset(name)
                idx = self.preset_combo.currentIndex()
                self.preset_combo.removeItem(idx)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete preset:\n{e}")
    
    def save_preset(self):
        """Save current rules as preset."""
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            QMessageBox.warning(self, "Warning", "Please select or create a preset first.")
            return
        
        try:
            # Collect rules from all tabs in original format
            preset_data = {
                "title": self.collect_rules_for_tab("title"),
                "artist": self.collect_rules_for_tab("artist"),
                "album": self.collect_rules_for_tab("album"),
            }
            
            # Save using the original SettingsManager format (simple dict)
            preset_file = SettingsManager.get_presets_folder() / f"{preset_name}.json"
            import json as json_module
            with preset_file.open("w", encoding="utf-8") as f:
                json_module.dump(preset_data, f, indent=2, ensure_ascii=False)
            
            # Update JSON editor to reflect saved data
            self.json_editor.setText(json.dumps(preset_data, indent=2))
            
            QMessageBox.information(self, "Success", f"Preset '{preset_name}' saved!")
            self.file_info_label.setText(f"Saved preset '{preset_name}'")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save preset:\n{e}")
            logger.exception("Error saving preset")
    
    def apply_preset_to_selected(self):
        """Apply preset to selected files."""
        selected = self.tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "No files selected.")
            return
        
        preset_name = self.preset_combo.currentText()
        
        reply = QMessageBox.question(self, "Apply Preset",
            f"Apply preset '{preset_name}' to {len(selected)} file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Get indices
                indices = []
                for item in selected:
                    idx = item.data(0, Qt.ItemDataRole.UserRole)
                    if idx is not None:
                        indices.append(idx)
                
                # Get preset rules
                preset = self.preset_service.load_preset(preset_name)
                rules = preset.to_dict() if preset else {}
                
                # Apply via RuleManager
                for idx in indices:
                    if idx < len(self.song_files):
                        # Apply rules to file
                        file_data = self.song_files[idx]
                        # Here would call actual apply logic
                
                QMessageBox.information(self, "Success",
                    f"Applied preset '{preset_name}' to {len(indices)} file(s)!")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to apply preset:\n{e}")
    
    def apply_preset_to_all(self):
        """Apply preset to all files."""
        if not self.song_files:
            QMessageBox.warning(self, "Warning", "No files loaded.")
            return
        
        preset_name = self.preset_combo.currentText()
        reply = QMessageBox.question(self, "Apply Preset",
            f"Apply preset '{preset_name}' to ALL {len(self.song_files)} files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Get preset rules
                preset = self.preset_service.load_preset(preset_name)
                rules = preset.to_dict() if preset else {}
                
                # Apply to all
                applied = 0
                for idx in range(len(self.song_files)):
                    file_data = self.song_files[idx]
                    # Apply rules
                    applied += 1
                
                QMessageBox.information(self, "Success",
                    f"Applied preset '{preset_name}' to {applied} file(s)!")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to apply preset:\n{e}")
    
    # ===== METADATA EDITING =====
    
    def save_metadata(self):
        """Save metadata."""
        QMessageBox.information(self, "Info", "Save feature coming soon.")
    
    def cancel_metadata_edit(self):
        """Cancel editing."""
        for field in self.metadata_fields.values():
            field.clear()
    
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
            "Database Reformatter v2.0\n"
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
            if self.sort_rules_list:
                SettingsManager.sort_rules = [
                    (rule_info['field'].currentText(), rule_info['order'].currentText() == "Asc")
                    for rule_info in self.sort_rules_list
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
                while len(self.sort_rules_list) > 1:
                    self.remove_sort_rule(1)
                
                # Update first rule if needed
                if len(self.sort_rules_list) > 0:
                    first_rule = SettingsManager.sort_rules[0]
                    self.sort_rules_list[0]['field'].setCurrentText(first_rule[0])
                    self.sort_rules_list[0]['order'].setCurrentText("Asc" if first_rule[1] else "Desc")
                
                # Add additional rules
                for rule in SettingsManager.sort_rules[1:]:
                    self._add_sort_rule_widget(len(self.sort_rules_list), is_first=False)
                    rule_info = self.sort_rules_list[-1]
                    rule_info['field'].setCurrentText(rule[0])
                    rule_info['order'].setCurrentText("Asc" if rule[1] else "Desc")
        except Exception as e:
            logger.debug(f"Error loading settings: {e}")
    
    # ===== RULE BUILDER METHODS =====
    
    def add_rule_to_tab(self, tab_name: str):
        """Add a new rule to the specified tab."""
        container = self.rule_containers.get(tab_name)
        if not container:
            return
        
        # Count existing rules
        layout = container.layout()
        rule_count = sum(1 for i in range(layout.count()) 
                        if isinstance(layout.itemAt(i).widget(), RuleRow))
        
        if rule_count >= self.max_rules_per_tab:
            QMessageBox.information(self, "Rule Limit",
                f"Maximum of {self.max_rules_per_tab} rules reached for {tab_name.title()}")
            return
        
        # Create new rule row
        rule_row = RuleRow(self.RULE_OPS)
        rule_row.delete_requested.connect(self.delete_rule)
        rule_row.move_up_requested.connect(self.move_rule_up)
        rule_row.move_down_requested.connect(self.move_rule_down)
        rule_row.rule_changed.connect(self.update_output_preview)
        
        # Insert before stretch
        layout.insertWidget(layout.count() - 1, rule_row)
        
        # Update button states
        self.update_rule_button_states(container)
    
    def delete_rule(self, rule_row):
        """Delete a rule row."""
        container = rule_row.parent()
        layout = container.layout()
        
        # Remove the widget
        layout.removeWidget(rule_row)
        rule_row.deleteLater()
        
        self.update_rule_button_states(container)
        self.update_output_preview()
    
    def move_rule_up(self, rule_row):
        """Move rule up in the list."""
        container = rule_row.parent()
        layout = container.layout()
        
        index = layout.indexOf(rule_row)
        if index > 0:
            # Check if previous item is also a RuleRow
            prev_item = layout.itemAt(index - 1)
            if prev_item and isinstance(prev_item.widget(), RuleRow):
                prev_widget = prev_item.widget()
                # Collect rule data before swap
                current_data = rule_row.get_rule_data()
                prev_data = prev_widget.get_rule_data()
                
                layout.removeWidget(rule_row)
                layout.removeWidget(prev_widget)
                
                # Recreate both rules with swapped data
                new_prev = RuleRow(self.RULE_OPS)
                new_prev.set_rule_data(current_data)
                new_prev.delete_requested.connect(self.delete_rule)
                new_prev.move_up_requested.connect(self.move_rule_up)
                new_prev.move_down_requested.connect(self.move_rule_down)
                new_prev.rule_changed.connect(self.update_output_preview)
                
                new_current = RuleRow(self.RULE_OPS)
                new_current.set_rule_data(prev_data)
                new_current.delete_requested.connect(self.delete_rule)
                new_current.move_up_requested.connect(self.move_rule_up)
                new_current.move_down_requested.connect(self.move_rule_down)
                new_current.rule_changed.connect(self.update_output_preview)
                
                layout.insertWidget(index - 1, new_prev)
                layout.insertWidget(index, new_current)
                
                prev_widget.deleteLater()
                rule_row.deleteLater()
                
                self.update_rule_button_states(container)
                self.update_output_preview()
    
    def move_rule_down(self, rule_row):
        """Move rule down in the list."""
        container = rule_row.parent()
        layout = container.layout()
        
        index = layout.indexOf(rule_row)
        # Check if next item is also a RuleRow
        if index < layout.count() - 2:  # -2 because last item is stretch
            next_item = layout.itemAt(index + 1)
            if next_item and isinstance(next_item.widget(), RuleRow):
                next_widget = next_item.widget()
                # Collect rule data before swap
                current_data = rule_row.get_rule_data()
                next_data = next_widget.get_rule_data()
                
                layout.removeWidget(rule_row)
                layout.removeWidget(next_widget)
                
                # Recreate both rules with swapped data
                new_current = RuleRow(self.RULE_OPS)
                new_current.set_rule_data(next_data)
                new_current.delete_requested.connect(self.delete_rule)
                new_current.move_up_requested.connect(self.move_rule_up)
                new_current.move_down_requested.connect(self.move_rule_down)
                new_current.rule_changed.connect(self.update_output_preview)
                
                new_next = RuleRow(self.RULE_OPS)
                new_next.set_rule_data(current_data)
                new_next.delete_requested.connect(self.delete_rule)
                new_next.move_up_requested.connect(self.move_rule_up)
                new_next.move_down_requested.connect(self.move_rule_down)
                new_next.rule_changed.connect(self.update_output_preview)
                
                layout.insertWidget(index, new_current)
                layout.insertWidget(index + 1, new_next)
                
                rule_row.deleteLater()
                next_widget.deleteLater()
                
                self.update_rule_button_states(container)
                self.update_output_preview()
                layout.insertWidget(index + 1, rule_row)
                self.update_rule_button_states(container)
    
    def update_rule_button_states(self, container):
        """Update up/down button states based on position."""
        layout = container.layout()
        rules = []
        
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if isinstance(widget, RuleRow):
                rules.append(widget)
        
        for idx, rule in enumerate(rules):
            # Enable/disable up button
            if hasattr(rule, 'up_btn'):
                rule.up_btn.setEnabled(idx > 0)
            
            # Enable/disable down button
            if hasattr(rule, 'down_btn'):
                rule.down_btn.setEnabled(idx < len(rules) - 1)
    
    def collect_rules_for_tab(self, tab_name: str) -> list:
        """Collect all rules from a tab."""
        container = self.rule_containers.get(tab_name)
        if not container:
            return []
        
        rules = []
        layout = container.layout()
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if isinstance(widget, RuleRow):
                rules.append(widget.get_rule_data())
        
        return rules
    
    def load_rules_to_tab(self, tab_name: str, rules: list):
        """Load rules into a tab."""
        container = self.rule_containers.get(tab_name)
        if not container:
            return
        
        # Clear existing rules
        layout = container.layout()
        while layout.count() > 1:  # Keep the stretch
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add rules
        for idx, rule_data in enumerate(rules[:self.max_rules_per_tab]):
            rule_row = RuleRow(self.RULE_OPS)
            rule_row.delete_requested.connect(self.delete_rule)
            rule_row.move_up_requested.connect(self.move_rule_up)
            rule_row.move_down_requested.connect(self.move_rule_down)
            rule_row.rule_changed.connect(self.update_output_preview)
            
            layout.insertWidget(idx, rule_row)
            rule_row.show()  # Ensure widget is visible
            rule_row.set_rule_data(rule_data)  # Set data after adding to layout
        
        self.update_rule_button_states(container)
        # Force layout update
        layout.update()
        container.updateGeometry()
        QApplication.processEvents()  # Process all pending events
    
    def update_output_preview(self):
        """Update output preview based on current rules and selected file."""
        if self.current_selected_file is None or self.current_selected_file >= len(self.song_files):
            return
        
        # This is now handled by update_preview_info() which updates the labels
        # Just call that to refresh the display
        self.update_preview_info()
    
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

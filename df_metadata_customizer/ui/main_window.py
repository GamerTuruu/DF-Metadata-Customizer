"""PyQt6 Main Application Window."""

import sys
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QPushButton,
    QFileDialog,
    QStatusBar,
    QLabel,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QLineEdit,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont

from df_metadata_customizer.core import FileManager, SettingsManager, PresetService, song_utils
from df_metadata_customizer.core.metadata import MetadataFields
from df_metadata_customizer.ui.styles.themes import get_theme
from df_metadata_customizer.ui.widgets import SearchWidget, MetadataEditorWidget, UndoRedoManager, APIServerWidget
from df_metadata_customizer.ui.dialogs import PresetMakerDialog
from df_metadata_customizer.core.preset_service import Preset

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()
        
        self.setWindowTitle("Database Reformatter — Metadata Customizer v2.0")
        self.setGeometry(100, 100, 1280, 720)
        self.setMinimumSize(960, 540)
        
        # Initialize managers
        SettingsManager.initialize()
        self.file_manager = FileManager()
        self.preset_service = PresetService(SettingsManager.get_presets_folder())
        
        # Get theme from settings
        self.current_theme = SettingsManager.theme.lower() if SettingsManager.theme else "system"
        
        # Undo/Redo manager
        self.undo_redo_manager = UndoRedoManager()
        
        # Current selected file
        self.current_file_path = None
        
        # Setup UI
        self._setup_ui()
        
        # Apply theme
        self._apply_theme()
        
        # Restore last folder if auto_reopen is enabled
        if SettingsManager.auto_reopen_last_folder and SettingsManager.last_folder_opened:
            QTimer.singleShot(500, lambda: self._load_folder(SettingsManager.last_folder_opened))

    def _setup_ui(self) -> None:
        """Setup the UI components."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Tab widget
        tabs = QTabWidget()
        
        # Simple Tab
        simple_tab = self._create_simple_tab()
        tabs.addTab(simple_tab, "Simple")
        
        # Advanced Tab
        advanced_tab = self._create_advanced_tab()
        tabs.addTab(advanced_tab, "Advanced")
        
        # Presets Tab
        presets_tab = self._create_presets_tab()
        tabs.addTab(presets_tab, "Presets")
        
        # Settings Tab
        settings_tab = self._create_settings_tab()
        tabs.addTab(settings_tab, "Settings")
        
        main_layout.addWidget(tabs)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _create_simple_tab(self) -> QWidget:
        """Create the simple/basic tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # File selector
        file_layout = QHBoxLayout()
        self.folder_label = QLineEdit()
        self.folder_label.setReadOnly(True)
        self.folder_label.setPlaceholderText("No folder selected...")
        
        select_btn = QPushButton("📁 Select Folder")
        select_btn.clicked.connect(self._select_folder)
        
        file_layout.addWidget(QLabel("Folder:"))
        file_layout.addWidget(self.folder_label)
        file_layout.addWidget(select_btn)
        
        layout.addLayout(file_layout)
        
        # Search widget
        self.search_widget = SearchWidget()
        self.search_widget.search_changed.connect(self._on_search_changed)
        self.search_widget.filter_changed.connect(self._on_filter_changed)
        layout.addWidget(self.search_widget)
        
        # File tree and metadata (splitter)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # File list
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Title", "Artist", "Version"])
        self.file_tree.setColumnCount(3)
        self.file_tree.itemSelectionChanged.connect(self._on_file_selected)
        
        # Metadata editor
        self.metadata_editor = MetadataEditorWidget()
        self.metadata_editor.save_clicked.connect(self._on_metadata_save)
        self.metadata_editor.metadata_changed.connect(self._on_metadata_changed)
        
        splitter.addWidget(self.file_tree)
        splitter.addWidget(self.metadata_editor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        undo_btn = QPushButton("↶ Undo")
        undo_btn.clicked.connect(self._undo)
        
        redo_btn = QPushButton("↷ Redo")
        redo_btn.clicked.connect(self._redo)
        
        action_layout.addWidget(undo_btn)
        action_layout.addWidget(redo_btn)
        action_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_files)
        
        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.clicked.connect(self._clear_files)
        
        action_layout.addWidget(refresh_btn)
        action_layout.addWidget(clear_btn)
        
        layout.addLayout(action_layout)
        
        widget.setLayout(layout)
        return widget

    def _create_advanced_tab(self) -> QWidget:
        """Create the advanced tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Advanced Features - Coming Soon")
        label.setFont(QFont("Arial", 14))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget

    def _create_presets_tab(self) -> QWidget:
        """Create the presets tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Preset list
        self.preset_tree = QTreeWidget()
        self.preset_tree.setHeaderLabels(["Preset Name", "Rules", "Description"])
        self.preset_tree.setColumnCount(3)
        
        self._populate_presets()
        
        layout.addWidget(QLabel("Available Presets:"))
        layout.addWidget(self.preset_tree)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        refresh_presets_btn = QPushButton("🔄 Refresh")
        refresh_presets_btn.clicked.connect(self._populate_presets)
        
        new_preset_btn = QPushButton("➕ New Preset")
        new_preset_btn.clicked.connect(self._new_preset)
        
        edit_preset_btn = QPushButton("✏️ Edit Preset")
        edit_preset_btn.clicked.connect(self._edit_preset)
        
        apply_preset_btn = QPushButton("✨ Apply Preset")
        apply_preset_btn.clicked.connect(self._apply_preset)
        
        delete_preset_btn = QPushButton("🗑️ Delete Preset")
        delete_preset_btn.clicked.connect(self._delete_preset)
        
        action_layout.addWidget(refresh_presets_btn)
        action_layout.addWidget(new_preset_btn)
        action_layout.addWidget(edit_preset_btn)
        action_layout.addWidget(apply_preset_btn)
        action_layout.addWidget(delete_preset_btn)
        
        layout.addLayout(action_layout)
        
        widget.setLayout(layout)
        return widget

    def _create_settings_tab(self) -> QWidget:
        """Create the settings tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # API Server controls
        layout.addWidget(QLabel("API Server:"))
        self.api_server_widget = APIServerWidget()
        layout.addWidget(self.api_server_widget)
        
        layout.addWidget(QLabel(""))
        
        # Theme selector
        layout.addWidget(QLabel("Theme:"))
        theme_layout = QHBoxLayout()
        
        light_btn = QPushButton("☀️ Light")
        light_btn.clicked.connect(lambda: self._set_theme("light"))
        
        dark_btn = QPushButton("🌙 Dark")
        dark_btn.clicked.connect(lambda: self._set_theme("dark"))
        
        auto_btn = QPushButton("🔄 System")
        auto_btn.clicked.connect(lambda: self._set_theme("system"))
        
        theme_layout.addWidget(light_btn)
        theme_layout.addWidget(dark_btn)
        theme_layout.addWidget(auto_btn)
        theme_layout.addStretch()
        
        layout.addLayout(theme_layout)
        
        # Add more settings later
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget

    def _select_folder(self) -> None:
        """Open folder selection dialog."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_label.setText(folder)
            self.status_bar.showMessage(f"Loading files from {folder}...")
            
            # Load files in background
            QTimer.singleShot(100, lambda: self._load_folder(folder))

    def _load_folder(self, folder_path: str) -> None:
        """Load files from folder."""
        try:
            self.file_manager.load_folder(folder_path)
            SettingsManager.last_folder_opened = folder_path
            SettingsManager.save_settings()
            
            self._populate_file_tree()
            
            file_count = self.file_manager.df.height
            self.status_bar.showMessage(f"Loaded {file_count} files")
            logger.info(f"Loaded {file_count} files from {folder_path}")
        except Exception as e:
            self.status_bar.showMessage(f"Error loading files: {e}")
            logger.exception(f"Error loading folder: {folder_path}")

    def _populate_file_tree(self) -> None:
        """Populate file tree with loaded files."""
        self.file_tree.clear()
        
        files = self.file_manager.get_all_files()
        for file_data in files:
            title = file_data.get(MetadataFields.TITLE, "Unknown")
            artist = file_data.get(MetadataFields.ARTIST, "Unknown")
            version = str(file_data.get(MetadataFields.VERSION, ""))
            
            item = QTreeWidgetItem([title, artist, version])
            item.setData(0, Qt.ItemDataRole.UserRole, file_data["path"])
            self.file_tree.addTopLevelItem(item)
        
        self.file_tree.resizeColumnToContents(0)
        self.file_tree.resizeColumnToContents(1)

    def _on_file_selected(self) -> None:
        """Handle file selection."""
        selected = self.file_tree.selectedItems()
        if not selected:
            self.metadata_editor.clear()
            self.current_file_path = None
            return
        
        item = selected[0]
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        self.current_file_path = file_path
        
        song = self.file_manager.get_file_by_path(file_path)
        if song:
            metadata = song.raw_data
            self.metadata_editor.load_metadata(metadata)

    def _refresh_files(self) -> None:
        """Refresh file list."""
        folder = self.folder_label.text()
        if folder:
            self._load_folder(folder)

    def _clear_files(self) -> None:
        """Clear loaded files."""
        self.file_manager.clear()
        self.file_tree.clear()
        self.metadata_display.clear()
        self.status_bar.showMessage("Files cleared")

    def _populate_presets(self) -> None:
        """Populate preset list."""
        self.preset_tree.clear()
        
        presets = self.preset_service.list_presets()
        for preset_name in presets:
            preset = self.preset_service.load_preset(preset_name)
            if preset:
                item = QTreeWidgetItem([
                    preset.name,
                    str(len(preset.rules)),
                    preset.description or "No description"
                ])
                self.preset_tree.addTopLevelItem(item)
        
        self.preset_tree.resizeColumnToContents(0)

    def _new_preset(self) -> None:
        """Create a new preset."""
        dialog = PresetMakerDialog(Preset(name="New Preset"), self)
        if dialog.exec() == PresetMakerDialog.DialogCode.Accepted:
            preset = dialog.get_preset()
            if preset.name:
                success = self.preset_service.save_preset(preset)
                if success:
                    self.status_bar.showMessage(f"Preset created: {preset.name}")
                    self._populate_presets()
                else:
                    QMessageBox.warning(self, "Error", "Failed to save preset")

    def _edit_preset(self) -> None:
        """Edit selected preset."""
        selected = self.preset_tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Error", "Please select a preset to edit")
            return
        
        preset_name = selected[0].text(0)
        preset = self.preset_service.load_preset(preset_name)
        
        if not preset:
            QMessageBox.warning(self, "Error", "Failed to load preset")
            return
        
        dialog = PresetMakerDialog(preset, self)
        if dialog.exec() == PresetMakerDialog.DialogCode.Accepted:
            preset = dialog.get_preset()
            success = self.preset_service.save_preset(preset)
            if success:
                self.status_bar.showMessage(f"Preset updated: {preset.name}")
                self._populate_presets()
            else:
                QMessageBox.warning(self, "Error", "Failed to save preset")

    def _apply_preset(self) -> None:
        """Apply selected preset to loaded files."""
        selected = self.preset_tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Error", "Please select a preset to apply")
            return
        
        if not self.current_file_path:
            QMessageBox.warning(self, "Error", "Please select a file first")
            return
        
        preset_name = selected[0].text(0)
        preset = self.preset_service.load_preset(preset_name)
        
        if not preset:
            QMessageBox.warning(self, "Error", "Failed to load preset")
            return
        
        # Get current metadata
        json_data = song_utils.extract_json_from_song(self.current_file_path) or {}
        
        # Apply preset
        result = self.preset_service.apply_preset(preset, json_data)
        
        # Update file manager and write to file
        self.file_manager.update_file_data(self.current_file_path, result)
        success = song_utils.write_json_to_song(self.current_file_path, result)
        
        if success:
            # Add to undo stack
            def undo_fn():
                song_utils.write_json_to_song(self.current_file_path, json_data)
                self.metadata_editor.load_metadata(json_data)
            
            def redo_fn():
                song_utils.write_json_to_song(self.current_file_path, result)
                self.metadata_editor.load_metadata(result)
            
            self.undo_redo_manager.add_action(f"Apply {preset_name}", undo_fn, redo_fn)
            
            # Reload metadata
            self.metadata_editor.load_metadata(result)
            self.status_bar.showMessage(f"Preset applied: {preset_name}")
        else:
            QMessageBox.warning(self, "Error", "Failed to apply preset")

    def _delete_preset(self) -> None:
        """Delete selected preset."""
        selected = self.preset_tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Error", "Please select a preset to delete")
            return
        
        preset_name = selected[0].text(0)
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete preset '{preset_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success = self.preset_service.delete_preset(preset_name)
            if success:
                self.status_bar.showMessage(f"Preset deleted: {preset_name}")
                self._populate_presets()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete preset")

    def _on_search_changed(self, query: str) -> None:
        """Handle search query change."""
        self._filter_file_tree(query)

    def _on_filter_changed(self, filter_name: str) -> None:
        """Handle filter change."""
        self._filter_file_tree(self.search_widget.get_search_query())

    def _filter_file_tree(self, query: str) -> None:
        """Filter file tree based on search query."""
        self.file_tree.clear()
        
        files = self.file_manager.get_all_files()
        
        # Apply search
        from df_metadata_customizer.core import RuleManager
        filters, free_terms = RuleManager.parse_search_query(query)
        
        if query:
            filtered_df = RuleManager.apply_search_filter(
                self.file_manager.df,
                filters,
                free_terms,
            )
            files = filtered_df.to_dicts()
        
        # Apply additional filter
        filter_name = self.search_widget.get_filter()
        if filter_name == "Latest Version Only":
            files = [f for f in files if self.file_manager.is_latest_version(
                f"{f.get(MetadataFields.TITLE)}|{f.get(MetadataFields.ARTIST)}|{f.get(MetadataFields.COVER_ARTIST)}",
                float(f.get(MetadataFields.VERSION, 0))
            )]
        
        # Populate tree
        for file_data in files:
            title = file_data.get(MetadataFields.TITLE, "Unknown")
            artist = file_data.get(MetadataFields.ARTIST, "Unknown")
            version = str(file_data.get(MetadataFields.VERSION, ""))
            
            item = QTreeWidgetItem([title, artist, version])
            item.setData(0, Qt.ItemDataRole.UserRole, file_data["path"])
            self.file_tree.addTopLevelItem(item)
        
        self.file_tree.resizeColumnToContents(0)
        self.file_tree.resizeColumnToContents(1)

    def _on_metadata_changed(self, metadata: dict) -> None:
        """Handle metadata change."""
        pass  # Changes are pending until save

    def _on_metadata_save(self) -> None:
        """Handle metadata save."""
        if not self.current_file_path:
            QMessageBox.warning(self, "Error", "No file selected")
            return
        
        # Get current data
        old_data = song_utils.extract_json_from_song(self.current_file_path) or {}
        
        # Get new data from editor
        new_data = {}
        for field_key, field_input in self.metadata_editor.fields.items():
            value = field_input.text()
            if value:
                new_data[field_key] = value
        
        # Write to file
        success = song_utils.write_json_to_song(self.current_file_path, new_data)
        
        if success:
            # Add to undo stack
            def undo_fn():
                song_utils.write_json_to_song(self.current_file_path, old_data)
                self.metadata_editor.load_metadata(old_data)
            
            def redo_fn():
                song_utils.write_json_to_song(self.current_file_path, new_data)
                self.metadata_editor.load_metadata(new_data)
            
            self.undo_redo_manager.add_action("Edit metadata", undo_fn, redo_fn)
            
            self.status_bar.showMessage("Metadata saved")
        else:
            QMessageBox.warning(self, "Error", "Failed to save metadata")

    def _undo(self) -> None:
        """Undo last action."""
        if self.undo_redo_manager.undo():
            undo_name = self.undo_redo_manager.get_undo_name()
            self.status_bar.showMessage(f"Undone: {undo_name or 'last action'}")
        else:
            self.status_bar.showMessage("Nothing to undo")

    def _redo(self) -> None:
        """Redo last undone action."""
        if self.undo_redo_manager.redo():
            redo_name = self.undo_redo_manager.get_redo_name()
            self.status_bar.showMessage(f"Redone: {redo_name or 'last action'}")
        else:
            self.status_bar.showMessage("Nothing to redo")

    def _set_theme(self, theme: str) -> None:
        """Set application theme."""
        self.current_theme = theme
        SettingsManager.theme = theme
        SettingsManager.save_settings()
        self._apply_theme()
        self.status_bar.showMessage(f"Theme changed to {theme}")

    def _apply_theme(self) -> None:
        """Apply the current theme."""
        if self.current_theme == "dark":
            stylesheet = get_theme("dark")
        else:
            stylesheet = get_theme("light")
        
        self.setStyleSheet(stylesheet)


def main() -> None:
    """Launch the PyQt6 UI application."""
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


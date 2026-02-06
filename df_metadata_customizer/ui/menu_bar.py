"""Menu bar setup and management."""

from PySide6.QtWidgets import QMenuBar


def setup_menubar(window, menubar: QMenuBar) -> None:
    """Setup menu bar with File, Edit, and Help menus."""
    # Stylesheet will be set by _refresh_theme_colors() in main_window
    
    # File menu
    file_menu = menubar.addMenu("File")
    action = file_menu.addAction("Open Folder")
    action.triggered.connect(window.open_folder)
    file_menu.addSeparator()
    action = file_menu.addAction("Preferences")
    action.triggered.connect(window.show_preferences)
    file_menu.addSeparator()
    action = file_menu.addAction("Exit")
    action.triggered.connect(window.close)
    
    # Help menu
    help_menu = menubar.addMenu("Help")
    action = help_menu.addAction("About")
    action.triggered.connect(window.show_about)

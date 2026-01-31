"""Menu bar setup and management."""

from PyQt6.QtWidgets import QMenuBar


def setup_menubar(window, menubar: QMenuBar) -> None:
    """Setup menu bar with File, Edit, and Help menus."""
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
    
    # Edit menu
    edit_menu = menubar.addMenu("Edit")
    action = edit_menu.addAction("Undo")
    action.triggered.connect(window.undo)
    action = edit_menu.addAction("Redo")
    action.triggered.connect(window.redo)
    
    # Help menu
    help_menu = menubar.addMenu("Help")
    action = help_menu.addAction("About")
    action.triggered.connect(window.show_about)

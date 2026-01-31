"""UI Styling constants and utilities."""

# Color scheme
BACKGROUND_PRIMARY = "#1e1e1e"
BACKGROUND_SECONDARY = "#2b2b2b"
BACKGROUND_TERTIARY = "#2d2d2d"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#aaaaaa"
TEXT_TERTIARY = "#888"
BORDER_COLOR = "#3d3d3d"
BORDER_LIGHT = "#555555"
BORDER_DARK = "#444"
BUTTON_PRIMARY = "#0d47a1"
BUTTON_PRIMARY_HOVER = "#1565c0"
BUTTON_SECONDARY = "#3a3a3a"
BUTTON_SECONDARY_HOVER = "#484848"
SELECTION_COLOR = "#0d47a1"
SELECTION_HOVER = "#1565c0"

# Style sheets
MENUBAR_STYLESHEET = """
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
"""

SPLITTER_STYLESHEET = """
QSplitter::handle {
    background-color: #2d2d2d;
    width: 6px;
}
"""

BUTTON_PRIMARY_STYLESHEET = """
QPushButton {
    background-color: #0d47a1;
    color: white;
    border: none;
    border-radius: 4px;
    font-weight: bold;
    padding: 6px 12px;
}
QPushButton:hover { background-color: #1565c0; }
"""

BUTTON_SMALL_STYLESHEET = """
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
QPushButton:disabled {
    background-color: #2b2b2b;
    color: #555;
    border: 1px solid #444;
}
"""

LINEEDIT_STYLESHEET = """
QLineEdit {
    background-color: #1e1e1e;
    color: #ffffff;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus { border: 2px solid #0d47a1; }
"""

TREE_STYLESHEET = """
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
"""

TAB_STYLESHEET = """
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
"""

FRAME_TRANSPARENT = "QFrame { background-color: transparent; }"
FRAME_PRIMARY = "QFrame { background-color: #2b2b2b; border-radius: 8px; }"

LABEL_SECONDARY = "color: #aaaaaa;"


def apply_styles(**kwargs):
    """Apply multiple styles to a widget."""
    for widget, stylesheet in kwargs.items():
        if widget and hasattr(widget, 'setStyleSheet'):
            widget.setStyleSheet(stylesheet)

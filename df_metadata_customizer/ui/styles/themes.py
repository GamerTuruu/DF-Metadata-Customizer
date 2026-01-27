"""PyQt6 theme and style management."""

LIGHT_THEME = """
QMainWindow {
    background-color: #ffffff;
    color: #000000;
}

QWidget {
    background-color: #ffffff;
    color: #000000;
}

QTabWidget::pane {
    border: 1px solid #e0e0e0;
}

QTabBar::tab {
    background-color: #f5f5f5;
    color: #000000;
    padding: 8px 20px;
    border: 1px solid #e0e0e0;
}

QTabBar::tab:selected {
    background-color: #2196F3;
    color: #ffffff;
}

QPushButton {
    background-color: #2196F3;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #1976D2;
}

QPushButton:pressed {
    background-color: #1565C0;
}

QLineEdit, QTextEdit {
    background-color: #f5f5f5;
    color: #000000;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 8px;
}

QTreeWidget {
    background-color: #fafafa;
    color: #000000;
    border: 1px solid #e0e0e0;
}

QHeaderView::section {
    background-color: #f5f5f5;
    color: #000000;
    padding: 8px;
    border: 1px solid #e0e0e0;
}

QStatusBar {
    background-color: #f5f5f5;
    color: #000000;
    border-top: 1px solid #e0e0e0;
}

QMenuBar {
    background-color: #ffffff;
    color: #000000;
}

QMenu {
    background-color: #ffffff;
    color: #000000;
}

QMenu::item:selected {
    background-color: #2196F3;
    color: #ffffff;
}
"""

DARK_THEME = """
QMainWindow {
    background-color: #1e1e1e;
    color: #ffffff;
}

QWidget {
    background-color: #1e1e1e;
    color: #ffffff;
}

QTabWidget::pane {
    border: 1px solid #3e3e3e;
}

QTabBar::tab {
    background-color: #2d2d2d;
    color: #ffffff;
    padding: 8px 20px;
    border: 1px solid #3e3e3e;
}

QTabBar::tab:selected {
    background-color: #2196F3;
    color: #ffffff;
}

QPushButton {
    background-color: #2196F3;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #1976D2;
}

QPushButton:pressed {
    background-color: #1565C0;
}

QLineEdit, QTextEdit {
    background-color: #2d2d2d;
    color: #ffffff;
    border: 1px solid #3e3e3e;
    border-radius: 4px;
    padding: 8px;
}

QTreeWidget {
    background-color: #252525;
    color: #ffffff;
    border: 1px solid #3e3e3e;
}

QHeaderView::section {
    background-color: #2d2d2d;
    color: #ffffff;
    padding: 8px;
    border: 1px solid #3e3e3e;
}

QStatusBar {
    background-color: #2d2d2d;
    color: #ffffff;
    border-top: 1px solid #3e3e3e;
}

QMenuBar {
    background-color: #1e1e1e;
    color: #ffffff;
}

QMenu {
    background-color: #2d2d2d;
    color: #ffffff;
}

QMenu::item:selected {
    background-color: #2196F3;
    color: #ffffff;
}
"""


def get_theme(theme_name: str) -> str:
    """Get theme stylesheet."""
    if theme_name == "dark":
        return DARK_THEME
    return LIGHT_THEME

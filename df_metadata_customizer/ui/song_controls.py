"""Song controls component with folder selection and search."""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QLineEdit, QLabel
from df_metadata_customizer.ui.styles import BUTTON_PRIMARY_STYLESHEET, LINEEDIT_STYLESHEET


def create_song_controls(parent):
    """Create song controls panel with folder button, search, and select all."""
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
    folder_btn.clicked.connect(parent.open_folder)
    layout.addWidget(folder_btn)
    
    # Refresh button
    refresh_btn = QPushButton("↻")
    refresh_btn.setFixedSize(36, 36)
    refresh_btn.setToolTip("Refresh file list")
    refresh_btn.setStyleSheet("""
        QPushButton {
            background-color: #0d47a1;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 18px;
            font-weight: bold;
        }
        QPushButton:hover { background-color: #1565c0; }
        QPushButton:pressed { background-color: #0a3270; }
    """)
    refresh_btn.clicked.connect(lambda: parent.refresh_current_folder(show_dialogs=True))
    layout.addWidget(refresh_btn)
    
    # Advanced search
    search_input = QLineEdit()
    search_input.setPlaceholderText('Search (artist="Lady Gaga", version>2, title!=Creep, track>=69)...')
    search_input.setFixedHeight(36)
    search_input.setStyleSheet("""
        QLineEdit {
            background-color: #1e1e1e;
            color: #ffffff;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QLineEdit:focus { border: 2px solid #0d47a1; }
    """)
    search_input.textChanged.connect(parent.on_search_changed)
    search_input.installEventFilter(parent)
    layout.addWidget(search_input)
    
    # Filtered count label
    filtered_count_label = QLabel("0 found")
    filtered_count_label.setStyleSheet("color: #bbb; font-size: 11px;")
    filtered_count_label.setFixedWidth(80)
    layout.addWidget(filtered_count_label)
    
    select_all = QPushButton("Select All")
    select_all.setFixedSize(100, 36)
    select_all.clicked.connect(parent.toggle_select_all)
    layout.addWidget(select_all)
    
    return frame, {
        'folder_btn': folder_btn,
        'refresh_btn': refresh_btn,
        'search_input': search_input,
        'filtered_count_label': filtered_count_label,
        'select_all_btn': select_all
    }

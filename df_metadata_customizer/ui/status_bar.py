"""Status bar component for displaying file and selection information."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from df_metadata_customizer.ui.styles import LABEL_SECONDARY, BUTTON_PRIMARY_STYLESHEET


def create_status_bar(parent):
    """Create status bar with file info and navigation controls."""
    frame = QFrame()
    frame.setStyleSheet("QFrame { background-color: transparent; }")
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    
    file_info_label = QLabel("No folder selected")
    file_info_label.setStyleSheet("color: #aaaaaa;")
    layout.addWidget(file_info_label)
    
    separator = QLabel("|")
    separator.setStyleSheet("color: #666666;")
    layout.addWidget(separator)
    
    selection_info_label = QLabel("0 song(s) selected")
    selection_info_label.setStyleSheet("color: #aaaaaa;")
    layout.addWidget(selection_info_label)
    
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
    stats_btn.clicked.connect(parent.show_statistics)
    layout.addWidget(stats_btn)
    
    prev_btn = QPushButton("◀ Prev")
    prev_btn.setFixedSize(70, 28)
    prev_btn.clicked.connect(parent.prev_file)
    layout.addWidget(prev_btn)
    
    next_btn = QPushButton("Next ▶")
    next_btn.setFixedSize(70, 28)
    next_btn.clicked.connect(parent.next_file)
    layout.addWidget(next_btn)
    
    return frame, {
        'file_info_label': file_info_label,
        'selection_info_label': selection_info_label,
        'stats_btn': stats_btn,
        'prev_btn': prev_btn,
        'next_btn': next_btn
    }

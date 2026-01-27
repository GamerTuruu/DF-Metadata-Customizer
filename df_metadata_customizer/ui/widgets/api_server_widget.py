"""API server control widget for PyQt6 UI."""

import subprocess
import threading
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class APIServerWidget(QWidget):
    """Widget for controlling API server."""

    server_started = pyqtSignal()
    server_stopped = pyqtSignal()

    def __init__(self, parent=None) -> None:
        """Initialize API server widget."""
        super().__init__(parent)
        
        self.server_process = None
        self.is_running = False
        
        layout = QHBoxLayout()
        
        # Status label
        self.status_label = QLabel("🔴 API Server: Offline")
        layout.addWidget(self.status_label)
        
        # Port selector
        layout.addWidget(QLabel("Port:"))
        self.port_spinbox = QSpinBox()
        self.port_spinbox.setMinimum(1024)
        self.port_spinbox.setMaximum(65535)
        self.port_spinbox.setValue(8000)
        self.port_spinbox.setEnabled(True)
        layout.addWidget(self.port_spinbox)
        
        # Start button
        self.start_btn = QPushButton("▶️ Start API")
        self.start_btn.clicked.connect(self._start_server)
        layout.addWidget(self.start_btn)
        
        # Stop button
        self.stop_btn = QPushButton("⏹️ Stop API")
        self.stop_btn.clicked.connect(self._stop_server)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        # Open docs button
        self.docs_btn = QPushButton("📖 API Docs")
        self.docs_btn.clicked.connect(self._open_docs)
        self.docs_btn.setEnabled(False)
        layout.addWidget(self.docs_btn)
        
        layout.addStretch()
        
        self.setLayout(layout)

    def _start_server(self) -> None:
        """Start API server in background."""
        if self.is_running:
            return
        
        port = self.port_spinbox.value()
        
        # Start server in thread
        thread = threading.Thread(target=self._run_server, args=(port,), daemon=True)
        thread.start()
        
        self.is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.port_spinbox.setEnabled(False)
        self.docs_btn.setEnabled(True)
        
        self.status_label.setText(f"🟢 API Server: Running on port {port}")
        self.server_started.emit()

    def _run_server(self, port: int) -> None:
        """Run API server."""
        try:
            import sys
            from pathlib import Path
            
            # Run API server
            self.server_process = subprocess.Popen(
                [sys.executable, "-m", "df_metadata_customizer", "api"],
                env={**subprocess.os.environ, "PORT": str(port)},
            )
            
            # Wait for process
            self.server_process.wait()
        except Exception as e:
            self.status_label.setText(f"❌ Error: {str(e)}")
            self.is_running = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.port_spinbox.setEnabled(True)
            self.docs_btn.setEnabled(False)

    def _stop_server(self) -> None:
        """Stop API server."""
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None
        
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.port_spinbox.setEnabled(True)
        self.docs_btn.setEnabled(False)
        
        self.status_label.setText("🔴 API Server: Offline")
        self.server_stopped.emit()

    def _open_docs(self) -> None:
        """Open API documentation in browser."""
        import webbrowser
        port = self.port_spinbox.value()
        webbrowser.open(f"http://localhost:{port}/docs")

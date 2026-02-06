"""Custom dialog classes with improved UX.

Dialogs can be dismissed with ESC key for faster workflow.
On non-Wayland systems, click-outside may work via focus loss.
"""

from PySide6.QtWidgets import QDialog, QMessageBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent


class _ClickOutsideMixin:
    """Mixin to improve dialog dismissal UX."""
    
    def _setup_click_outside(self, enabled=True):
        """Initialize ESC key support."""
        self._click_outside_enabled = enabled
    
    def keyPressEvent(self, event):
        """Handle ESC key to dismiss dialog quickly."""
        if event.key() == Qt.Key_Escape and self._click_outside_enabled:
            self._handle_click_outside()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def event(self, event):
        """Try to detect focus loss on non-Wayland systems."""
        if event.type() == QEvent.WindowDeactivate and self._click_outside_enabled:
            # Only works on X11, ignored on Wayland
            if self.isVisible():
                QTimer = __import__('PySide6.QtCore', fromlist=['QTimer']).QTimer
                QTimer.singleShot(50, self._try_click_outside)
        return super().event(event)
    
    def _try_click_outside(self):
        """Attempt click-outside dismissal (X11 only)."""
        if self.isVisible() and self._click_outside_enabled:
            self._handle_click_outside()


class ClickOutsideDialog(_ClickOutsideMixin, QDialog):
    """QDialog with click-outside-to-dismiss support."""
    
    def __init__(self, parent=None, default_action="accept", enable_click_outside=True):
        super().__init__(parent)
        self.default_action = default_action
        self._setup_click_outside(enable_click_outside)
        self.setWindowFlags(Qt.Dialog)
        self.setModal(True)
    
    def _handle_click_outside(self):
        """Handle click outside dialog."""
        if not self.isVisible():
            return
        if self.default_action == "accept":
            self.accept()
        elif self.default_action == "reject":
            self.reject()
        else:
            self.close()


class ClickOutsideMessageBox(_ClickOutsideMixin, QDialog):
    """Custom message box with click-outside-to-dismiss support."""
    
    Ok, Cancel, Yes, No = QMessageBox.Ok, QMessageBox.Cancel, QMessageBox.Yes, QMessageBox.No
    
    def __init__(self, parent=None, title="", text="", buttons=QMessageBox.Ok, 
                 default_button=None, enable_click_outside=True):
        super().__init__(parent)
        self._result = default_button or QMessageBox.Ok
        self._default_button = self._result
        self._setup_click_outside(enable_click_outside)
        
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog)
        self.setModal(True)
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        msg_label = QLabel(text)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        # Create buttons dynamically
        for button_type, label in [(QMessageBox.Ok, "OK"), (QMessageBox.Yes, "Yes"), 
                                     (QMessageBox.No, "No"), (QMessageBox.Cancel, "Cancel")]:
            if buttons & button_type:
                btn = QPushButton(label)
                btn.clicked.connect(lambda checked, bt=button_type: self._set_result_and_close(bt))
                btn_layout.addWidget(btn)
                if default_button == button_type:
                    btn.setDefault(True)
                    btn.setFocus()
        
        layout.addLayout(btn_layout)
    
    def _handle_click_outside(self):
        """Handle click outside - trigger default button."""
        if self.isVisible():
            self._result = self._default_button
            self.accept()
    
    def _set_result_and_close(self, result):
        """Set result and close dialog."""
        self._result = result
        self.accept()
    
    def result_value(self):
        """Get the result value."""
        return self._result


# Convenience functions
def _show_dialog(parent, title, text, buttons, default_button, enable_click_outside):
    """Helper to show dialog and return result."""
    if enable_click_outside:
        dialog = ClickOutsideMessageBox(parent, title, text, buttons, default_button, True)
        dialog.exec()
        return dialog.result_value()
    return None


def information(parent, title: str, text: str, enable_click_outside: bool = True):
    """Show information message (click outside to dismiss)."""
    if enable_click_outside:
        return _show_dialog(parent, title, text, QMessageBox.Ok, QMessageBox.Ok, True)
    return QMessageBox.information(parent, title, text)


def warning(parent, title: str, text: str, enable_click_outside: bool = True):
    """Show warning message (click outside to dismiss)."""
    if enable_click_outside:
        return _show_dialog(parent, title, text, QMessageBox.Ok, QMessageBox.Ok, True)
    return QMessageBox.warning(parent, title, text)


def critical(parent, title: str, text: str, enable_click_outside: bool = True):
    """Show error message (click outside to dismiss)."""
    if enable_click_outside:
        return _show_dialog(parent, title, text, QMessageBox.Ok, QMessageBox.Ok, True)
    return QMessageBox.critical(parent, title, text)


def question(parent, title: str, text: str, default_yes: bool = False,
             enable_click_outside: bool = True, buttons=QMessageBox.Yes | QMessageBox.No):
    """Show question dialog (click outside triggers default)."""
    default_button = QMessageBox.Yes if default_yes else QMessageBox.No
    if enable_click_outside:
        return _show_dialog(parent, title, text, buttons, default_button, True)
    return QMessageBox.question(parent, title, text, buttons)




def show_info_message(parent, title: str, text: str, auto_dismiss: bool = True):
    """
    Show information message with optional click-outside dismissal.
    
    Args:
        parent: Parent widget
        title: Dialog title
        text: Message text
        auto_dismiss: If True, clicking outside will dismiss (default: True)
    
    Returns:
        Dialog result
    """
    msg = ClickOutsideMessageBox(parent)
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(QMessageBox.Ok)
    
    if auto_dismiss:
        msg.set_click_outside_default(QMessageBox.Ok)
    
    return msg.exec()


def show_warning_message(parent, title: str, text: str, auto_dismiss: bool = True):
    """
    Show warning message with optional click-outside dismissal.
    
    Args:
        parent: Parent widget
        title: Dialog title
        text: Message text
        auto_dismiss: If True, clicking outside will dismiss (default: True)
    
    Returns:
        Dialog result
    """
    msg = ClickOutsideMessageBox(parent)
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(QMessageBox.Ok)
    
    if auto_dismiss:
        msg.set_click_outside_default(QMessageBox.Ok)
    
    return msg.exec()


def show_error_message(parent, title: str, text: str, auto_dismiss: bool = True):
    """
    Show error message with optional click-outside dismissal.
    
    Args:
        parent: Parent widget
        title: Dialog title
        text: Message text
        auto_dismiss: If True, clicking outside will dismiss (default: True)
    
    Returns:
        Dialog result
    """
    msg = ClickOutsideMessageBox(parent)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(QMessageBox.Ok)
    
    if auto_dismiss:
        msg.set_click_outside_default(QMessageBox.Ok)
    
    return msg.exec()


def show_question(parent, title: str, text: str, default_yes: bool = False, 
                  buttons=QMessageBox.Yes | QMessageBox.No):
    """
    Show question dialog with click-outside support.
    
    Args:
        parent: Parent widget
        title: Dialog title
        text: Message text
        default_yes: If True, clicking outside acts as "Yes", otherwise "No"
        buttons: Standard buttons to show
    
    Returns:
        Dialog result (StandardButton value)
    """
    msg = ClickOutsideMessageBox(parent)
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(buttons)
    
    # Set default button for click-outside
    default_button = QMessageBox.Yes if default_yes else QMessageBox.No
    msg.set_click_outside_default(default_button)
    msg.setDefaultButton(default_button)
    
    return msg.exec()


class ProgressDialogClickOutside(QDialog):
    """
    Progress dialog that can be dismissed by clicking outside (cancels operation).
    """
    
    def __init__(self, title: str = "Processing", parent=None):
        from df_metadata_customizer.ui.progress_dialog import ProgressDialog
        
        # Initialize with standard progress dialog
        super().__init__(parent)
        self._progress = ProgressDialog(title, parent)
        self._progress.setParent(self)
        
        # Enable click-outside to cancel
        self.setWindowModality(Qt.ApplicationModal)
    
    def mousePressEvent(self, event):
        """Click outside cancels the operation."""
        if not self._progress.geometry().contains(event.pos()):
            self._progress.cancel()
        super().mousePressEvent(event)
    
    def update_progress(self, current: int, total: int, text: str = ""):
        """Forward to internal progress dialog."""
        self._progress.update_progress(current, total, text)
    
    @property
    def cancelled(self):
        """Check if operation was cancelled."""
        return self._progress.cancelled
    
    def show(self):
        """Show the progress dialog."""
        self._progress.show()
    
    def close(self):
        """Close the progress dialog."""
        self._progress.close()

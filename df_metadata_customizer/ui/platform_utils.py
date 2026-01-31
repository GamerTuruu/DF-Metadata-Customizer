"""Cross-platform file and folder operations utilities."""

import subprocess
import platform
import os
from pathlib import Path


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

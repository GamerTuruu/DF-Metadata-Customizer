"""Cross-platform file and folder operations utilities."""

import subprocess
import platform
import os
import shutil
from pathlib import Path
from typing import List, Tuple


def get_available_players() -> List[Tuple[str, str]]:
    """Get list of available media players on the system.
    
    Returns:
        List of tuples (display_name, command/path)
    """
    system = platform.system()
    players = []
    
    if system == "Darwin":  # macOS
        # Common macOS players
        common_players = [
            ("iTunes/Music", "/Applications/Music.app"),
            ("VLC", "/Applications/VLC.app"),
            ("Spotify", "/Applications/Spotify.app"),
            ("QuickTime", "/Applications/QuickTime Player.app"),
            ("IINA", "/Applications/IINA.app"),
            ("mpv", "mpv"),
        ]
        for name, path in common_players:
            if "/" in path and path.startswith("/Applications"):
                if Path(path).exists():
                    players.append((name, path))
            else:
                if shutil.which(path):
                    players.append((name, path))
    
    elif system == "Windows":
        # Common Windows players
        common_players = [
            ("Windows Media Player", "wmplayer.exe"),
            ("VLC", "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"),
            ("VLC (32-bit)", "C:\\Program Files (x86)\\VideoLAN\\VLC\\vlc.exe"),
            ("Spotify", "C:\\Users\\{username}\\AppData\\Roaming\\Spotify\\Spotify.exe"),
            ("foobar2000", "C:\\Program Files\\foobar2000\\foobar2000.exe"),
            ("foobar2000 (32-bit)", "C:\\Program Files (x86)\\foobar2000\\foobar2000.exe"),
            ("MPC-HC", "C:\\Program Files\\MPC-HC\\mpc-hc.exe"),
            ("MPC-HC (32-bit)", "C:\\Program Files (x86)\\MPC-HC\\mpc-hc.exe"),
        ]
        
        for name, path in common_players:
            if "{username}" in path:
                path = path.format(username=os.getenv("USERNAME", ""))
            if Path(path).exists():
                players.append((name, path))
            elif name == "Windows Media Player" and shutil.which(path):
                players.append((name, path))
    
    else:  # Linux
        # Common Linux players
        common_players = [
            ("VLC", "vlc"),
            ("mpv", "mpv"),
            ("ffplay", "ffplay"),
            ("GNOME Music", "gnome-music"),
            ("Totem", "totem"),
            ("Lollypop", "lollypop"),
            ("Rhythmbox", "rhythmbox"),
            ("Audacious", "audacious"),
            ("Clementine", "clementine"),
            ("Amarok", "amarok"),
            ("Elisa", "elisa"),
            ("Strawberry", "strawberry"),
            ("Cantata", "cantata"),
            ("cplay", "cplay"),
            ("MPC", "mpc"),
        ]
        for name, cmd in common_players:
            if shutil.which(cmd):
                players.append((name, cmd))
    
    return players


def open_file_with_player(file_path: str, player_path: str | None = None) -> None:
    """Open file with specified player or default application.
    
    Args:
        file_path: Path to the file to open
        player_path: Path or command to player. If None, uses default app.
    """
    abs_path = str(Path(file_path).resolve())
    system = platform.system()
    
    try:
        if player_path is None:
            # Use default application
            if system == "Darwin":
                subprocess.Popen(["open", abs_path], stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL, close_fds=True)
            elif system == "Windows":
                os.startfile(abs_path)
            else:  # Linux
                subprocess.Popen(["xdg-open", abs_path], stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL, close_fds=True, 
                               start_new_session=True)
        else:
            # Use specified player
            if system == "Darwin" and player_path.endswith(".app"):
                # macOS app bundle
                subprocess.Popen(["open", "-a", player_path, abs_path], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                               close_fds=True)
            elif system == "Windows":
                subprocess.Popen([player_path, abs_path], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                               close_fds=True)
            else:  # Linux
                subprocess.Popen([player_path, abs_path], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                               close_fds=True, start_new_session=True)
    except Exception as e:
        raise Exception(f"Failed to open file with player: {e}")


def open_file_with_default_app(file_path: str) -> None:
    """Open file with default application (cross-platform)."""
    open_file_with_player(file_path, None)


def open_folder_with_file_manager(folder_path: str, file_to_select: str = None) -> None:
    """Open folder in file manager and optionally select a file (cross-platform)."""
    system = platform.system()
    
    try:
        if file_to_select:
            # Reveal/select specific file
            abs_file_path = str(Path(file_to_select).resolve())
            if system == "Darwin":  # macOS
                # Use 'open -R' to reveal file in Finder
                subprocess.Popen(["open", "-R", abs_file_path], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL, 
                               close_fds=True)
            elif system == "Windows":
                # Use explorer with /select to highlight file
                # Use shell=True and full environment for compiled executables
                subprocess.Popen(f'explorer /select,"{abs_file_path}"', 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL, 
                               close_fds=True,
                               shell=True,
                               env=os.environ.copy())
            else:  # Linux and other Unix-like systems
                # Try nautilus first, fallback to other options
                abs_file_path_safe = abs_file_path.replace('"', '\\"')
                
                if shutil.which("nautilus"):
                    subprocess.Popen(f'nautilus --select "{abs_file_path_safe}"',
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL, 
                                   close_fds=True, 
                                   start_new_session=True,
                                   shell=True,
                                   env=os.environ.copy())
                elif shutil.which("nemo"):  # Cinnamon file manager
                    subprocess.Popen(f'nemo --select "{abs_file_path_safe}"',
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL, 
                                   close_fds=True, 
                                   start_new_session=True,
                                   shell=True,
                                   env=os.environ.copy())
                elif shutil.which("dolphin"):  # KDE file manager
                    subprocess.Popen(f'dolphin --select "{abs_file_path_safe}"',
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL, 
                                   close_fds=True, 
                                   start_new_session=True,
                                   shell=True,
                                   env=os.environ.copy())
                elif shutil.which("thunar"):  # XFCE file manager
                    subprocess.Popen(f'thunar "{Path(abs_file_path).parent}"',
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL, 
                                   close_fds=True, 
                                   start_new_session=True,
                                   shell=True,
                                   env=os.environ.copy())
                else:
                    # Fallback: use xdg-open
                    folder = str(Path(abs_file_path).parent)
                    subprocess.Popen(f'xdg-open "{folder}"', 
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL, 
                                   close_fds=True, 
                                   start_new_session=True,
                                   shell=True,
                                   env=os.environ.copy())
        else:
            # Just open folder
            abs_path = str(Path(folder_path).resolve())
            if system == "Darwin":  # macOS
                subprocess.Popen(["open", abs_path], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL, 
                               close_fds=True)
            elif system == "Windows":
                # Use shell=True and full environment for compiled executables
                subprocess.Popen(f'explorer "{abs_path}"', 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL, 
                               close_fds=True,
                               shell=True,
                               env=os.environ.copy())
            else:  # Linux and other Unix-like systems
                # Use shell=True for better environment handling in compiled apps
                subprocess.Popen(f'xdg-open "{abs_path}"',
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL, 
                               close_fds=True, 
                               start_new_session=True,
                               shell=True,
                               env=os.environ.copy())
    except Exception as e:
        raise Exception(f"Failed to open folder: {e}")

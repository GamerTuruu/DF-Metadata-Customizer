"""Cross-platform file and folder operations utilities."""

import subprocess
import platform
import os
import shutil
from pathlib import Path
from typing import List, Tuple


def _get_host_env():
    """Get environment for subprocess with proper AppImage/Wayland support.
    
    When running from AppImage, we need to preserve host environment variables
    for display servers (X11/Wayland) and desktop integration to work properly.
    """
    env = os.environ.copy()
    
    # For AppImage: Preserve original environment variables
    # AppImage sets APPIMAGE_* variables with original values
    if 'APPIMAGE' in env:
        # Restore original PATH to access host binaries
        original_path = env.get('APPIMAGE_ORIGINAL_PATH')
        if original_path:
            env['PATH'] = original_path
        else:
            fallback_path = env.get('PATH', '')
            if '/usr/bin' not in fallback_path:
                env['PATH'] = f"/usr/local/bin:/usr/bin:/bin:{fallback_path}"
        
        # Ensure display server variables are set
        for var in ['DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR', 
                    'DBUS_SESSION_BUS_ADDRESS', 'XDG_SESSION_TYPE',
                    'GDK_BACKEND', 'QT_QPA_PLATFORM']:
            original_var = f'APPIMAGE_ORIGINAL_{var}'
            if original_var in env:
                env[var] = env[original_var]
        
        # Provide a safe default for XDG_RUNTIME_DIR if missing
        if not env.get('XDG_RUNTIME_DIR'):
            env['XDG_RUNTIME_DIR'] = f"/run/user/{os.getuid()}"
        
        # Provide a default DBus session address if missing
        if not env.get('DBUS_SESSION_BUS_ADDRESS') and env.get('XDG_RUNTIME_DIR'):
            env['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path={env['XDG_RUNTIME_DIR']}/bus"
    
    return env


def _try_run(command: list[str], env: dict) -> bool:
    """Run a command and return True if it likely launched successfully."""
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
            env=env,
            timeout=3,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


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
                               start_new_session=True, env=_get_host_env())
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
                               close_fds=True, start_new_session=True,
                               env=_get_host_env())
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
                # Try file managers in order of preference
                # Use list arguments instead of shell=True for better Wayland compatibility
                env = _get_host_env()
                file_uri = Path(abs_file_path).as_uri()
                parent_folder = str(Path(abs_file_path).parent)

                if shutil.which("nautilus"):
                    if _try_run(["nautilus", "--select", abs_file_path], env):
                        return
                    if _try_run(["nautilus", "--select", file_uri], env):
                        return
                if shutil.which("nemo"):
                    if _try_run(["nemo", "--select", abs_file_path], env):
                        return
                if shutil.which("dolphin"):
                    if _try_run(["dolphin", "--select", abs_file_path], env):
                        return
                if shutil.which("thunar"):
                    if _try_run(["thunar", parent_folder], env):
                        return
                if shutil.which("pcmanfm"):
                    if _try_run(["pcmanfm", parent_folder], env):
                        return
                if shutil.which("gio"):
                    if _try_run(["gio", "open", parent_folder], env):
                        return

                # Fallback: use xdg-open on parent folder
                if _try_run(["xdg-open", parent_folder], env):
                    return
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
                # Use argument list for better Wayland compatibility
                env = _get_host_env()
                if _try_run(["xdg-open", abs_path], env):
                    return
                if shutil.which("gio"):
                    _try_run(["gio", "open", abs_path], env)
    except Exception as e:
        raise Exception(f"Failed to open folder: {e}")

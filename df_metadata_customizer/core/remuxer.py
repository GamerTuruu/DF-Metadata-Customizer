"""Audio remuxing utilities using ffmpeg."""

import subprocess
from pathlib import Path
from df_metadata_customizer.core.error_logger import ErrorLogger


def remux_song(file_path: str, new_path: str) -> tuple[bool, str]:
    """
    Remux an audio file using ffmpeg while preserving metadata.
    
    Args:
        file_path: Path to the source audio file
        new_path: Path for the output remuxed file
    
    Returns:
        Tuple of (success: bool, error_message: str)
    """
    filename = Path(file_path).name
    
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", file_path,
                "-map_metadata", "0",
                "-c:a", "copy",
                "-write_xing", "1",
                new_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode != 0:
            error_msg = f"ffmpeg returned code {result.returncode}"
            stderr_preview = result.stderr[:500] if result.stderr else "No error output"
            full_error = f"{error_msg}. Stderr: {stderr_preview}"
            ErrorLogger.log_remux_error(filename, full_error)
            return False, error_msg
        
        # Verify output file was created
        if not Path(new_path).exists():
            error_msg = "Output file was not created"
            ErrorLogger.log_remux_error(filename, error_msg)
            return False, error_msg
        
        return True, ""
        
    except FileNotFoundError:
        error_msg = "ffmpeg not found. Please install ffmpeg and add it to PATH"
        ErrorLogger.log_remux_error(filename, error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        ErrorLogger.log_remux_error(filename, error_msg)
        return False, error_msg

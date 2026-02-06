"""Audio remuxing utilities using ffmpeg."""

import subprocess


def remux_song(file_path: str, new_path: str) -> None:
    """
    Remux an audio file using ffmpeg while preserving metadata.
    
    Args:
        file_path: Path to the source audio file
        new_path: Path for the output remuxed file
    """
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
            print(f"Error: ffmpeg encountered an issue. Stderr: {result.stderr}")
            return
    except Exception as e:
        print("Error:", e)
        return

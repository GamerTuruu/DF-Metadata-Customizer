"""Utilities for reading/writing MP3 ID3 tags and embedded JSON metadata."""

import contextlib
import json
import logging
import os
import platform
import shutil
import subprocess
from io import BytesIO
from tkinter import messagebox

from mutagen.id3 import APIC, COMM, ID3, TALB, TDRC, TIT2, TPE1, TPOS, TRCK, ID3NoHeaderError
from PIL import Image
from tinytag import TinyTag

logger = logging.getLogger(__name__)


def extract_json_from_mp3(path: str) -> dict | None:
    """Return parsed JSON dict or None."""
    try:
        tags = TinyTag.get(path, tags=True, image=False)

        # tag.comment and tag.other['comment'] may contain JSON texts
        texts = tags.other.get("comment") or []  # All entries in other are lists
        if tags.comment:
            texts.append(tags.comment)

        if not texts:
            return None

        # Combine jsons
        comm_data = {}
        for text in texts:
            with contextlib.suppress(json.JSONDecodeError):
                comm_data.update(json.loads(text))

    except Exception:
        logger.exception("Error parsing JSON from file comment")
        return None

    return comm_data


def write_json_to_mp3(path: str, json_data: dict | str) -> bool:
    """Write JSON data back to MP3 comment tag."""
    try:
        # Try to load existing tags or create new ones
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()

        # Remove existing COMM frames
        tags.delall("COMM::ved")

        # Convert JSON to string and create new COMM frame
        # FIXED: Don't double-encode the JSON, just use the string directly
        json_str = json_data if isinstance(json_data, str) else json.dumps(json_data, ensure_ascii=False)

        # FIXED: Create COMM frame with proper encoding and description
        tags.add(
            COMM(
                encoding=3,  # UTF-8
                lang="ved",  # Use 'ved' for custom archive
                desc="",  # Empty description
                text=json_str,
            ),
        )

        # Save the tags
        tags.save(path)
    except Exception:
        logger.exception("Error writing JSON to MP3")
        return False
    return True


def read_cover_from_mp3(path: str) -> Image.Image | None:
    """Return (PIL Image, mime) or (None, None)."""
    try:
        tags = TinyTag.get(path, tags=True, image=True)
        img = tags.images.any
        if img:
            return Image.open(BytesIO(img.data))

    except Exception:
        logger.exception("Error reading cover image")
        return None
    return None


def write_id3_tags(
    path: str,
    title: str | None = None,
    artist: str | None = None,
    album: str | None = None,
    track: str | None = None,
    disc: str | None = None,
    date: str | None = None,
    cover_bytes: bytes | None = None,
    cover_mime: str = "image/jpeg",
):
    """Write provided tags to file (only provided ones). Returns True/False."""
    try:
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()
        if title is not None:
            tags.delall("TIT2")
            tags.add(TIT2(encoding=3, text=title))
        if artist is not None:
            tags.delall("TPE1")
            tags.add(TPE1(encoding=3, text=artist))
        if album is not None:
            tags.delall("TALB")
            tags.add(TALB(encoding=3, text=album))
        if date is not None:
            tags.delall("TDRC")
            tags.add(TDRC(encoding=3, text=str(date)))
        if track is not None:
            tags.delall("TRCK")
            tags.add(TRCK(encoding=3, text=str(track)))
        if disc is not None:
            tags.delall("TPOS")
            tags.add(TPOS(encoding=3, text=str(disc)))
        if cover_bytes:
            tags.delall("APIC")
            tags.add(APIC(encoding=3, mime=cover_mime, type=3, desc="Cover", data=cover_bytes))
        tags.save(path)
    except Exception:
        logger.exception("Error writing tags")
        return False
    return True


def play_song(file_path: str) -> bool:
    """Play a song using the system's default audio player."""
    if platform.system() == "Windows":
        os.startfile(file_path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.run(["open", file_path], check=False)
    else:  # Linux and other Unix-like
        # Try multiple methods for Linux/Ubuntu
        methods = [
            # Method 1: Try xdg-open (most common)
            ["xdg-open", file_path],
            # Method 2: Try mpv (common media player)
            ["mpv", "--no-terminal", file_path],
            # Method 3: Try vlc
            ["vlc", file_path],
            # Method 4: Try rhythmbox (Ubuntu default music player)
            ["rhythmbox", file_path],
            # Method 5: Try totem (GNOME video player)
            ["totem", file_path],
            # Method 6: Try mplayer (fallback)
            ["mplayer", file_path],
        ]

        success = False

        for cmd in methods:
            try:
                # Check if command exists
                if shutil.which(cmd[0]) is not None:
                    # Run with subprocess.Popen to avoid blocking
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    success = True
                    logger.info("Playing with: %s", " ".join(cmd))
                    break
            except Exception:
                logger.exception("Error playing audio with command: %s", " ".join(cmd))
                continue

        return success
    return True


def show_audio_player_instructions() -> None:
    """Show instructions for installing audio players on Ubuntu."""
    instructions = """To play audio files, you need a media player installed.

Recommended players for Ubuntu:
1. mpv (lightweight): sudo apt install mpv
2. VLC (full-featured): sudo apt install vlc
3. Rhythmbox (music player): sudo apt install rhythmbox

After installation, try double-clicking again."""

    messagebox.showinfo("Media Player Required", instructions)

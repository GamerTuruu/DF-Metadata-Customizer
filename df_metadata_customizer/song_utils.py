"""Utilities for reading/writing Song ID3 tags and embedded JSON metadata."""

import contextlib
import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from tkinter import messagebox

import xxhash
from mutagen.id3 import APIC, COMM, ID3, TALB, TDRC, TIT2, TPE1, TPOS, TRCK, ID3NoHeaderError
from PIL import Image
from tinytag import TinyTag

logger = logging.getLogger(__name__)

SUPPORTED_FILES_TYPES = {".mp3"}  # set(TinyTag.SUPPORTED_FILE_EXTENSIONS)


def extract_json_from_song(path: str) -> dict | None:
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
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                comm_data.update(json.loads(text))

    except Exception:
        logger.exception("Error parsing JSON from file comment")
        return None

    return comm_data


def get_id3_tags(path: str) -> dict[str, str]:
    """Return dictionary of standard ID3 tags."""
    try:
        tags = TinyTag.get(path, tags=True, image=False)
    except Exception:
        logger.exception("Error reading ID3 tags")
        return {}

    return {
        "Title": tags.title or "",
        "Artist": tags.artist or "",
        "Album": tags.album or "",
        "Track": str(tags.track) or "",
        "Discnumber": str(tags.disc) or "",
        "Date": tags.year or "",
    }


def write_json_to_song(path: str, json_data: dict | str) -> bool:
    """Write JSON data back to song comment tag."""
    try:
        # Try to load existing tags or create new ones
        try:
            tags = ID3(path).getall
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
        logger.exception("Error writing JSON to song")
        return False
    return True


def read_cover_from_song(path: str) -> Image.Image | None:
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
) -> bool:
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


def get_audio_hash(file_path: str) -> str | None:
    """Calculate xxhash (xxh64) of audio content, stripping ID3 tags."""
    try:
        try:
            audio_tags = ID3(file_path)
            header_size = audio_tags.size
        except ID3NoHeaderError:
            header_size = 0

        file_data = Path(file_path).read_bytes()

        # Check for ID3v1 footer (always 128 bytes at the end starting with 'TAG')
        footer_size = 128 if file_data[-128:].startswith(b"TAG") else 0

        # Slice the data to extract only the audio frames
        end_index = len(file_data) - footer_size
        raw_audio = file_data[header_size:end_index]

        return xxhash.xxh64(raw_audio).hexdigest()

    except Exception:
        logger.exception("Error calculating audio hash")
        return None

def get_audio_hash_legacy(path: str) -> str | None:
    """Calculate SHA256 hash of the audio content, ignoring ID3v1/v2 tags.

    Returns hex digest string or None on error.
    """
    try:
        sha256 = hashlib.sha256()
        with Path(path).open("rb") as f:
            # Check for ID3v2 at start
            # Structure: https://id3.org/id3v2.4.0-structure#section-3
            header = f.read(10)
            start_offset = 0

            if header.startswith(b"ID3") and len(header) == 10:
                # Calculate ID3v2 size
                version = header[3]
                size_bytes = header[6:10]

                if version < 3:
                    # Normal 32-bit integer (rare ID3v2.2)
                    # Spec: https://id3.org/id3v2.2.0
                    size = (size_bytes[0] << 24) | (size_bytes[1] << 16) | (size_bytes[2] << 8) | size_bytes[3]
                else:
                    # Sync-safe integer (ID3v2.3, v2.4)
                    # Decoding: https://id3.org/id3v2.4.0-structure#section-3.2
                    size = (
                        ((size_bytes[0] & 0x7F) << 21)
                        | ((size_bytes[1] & 0x7F) << 14)
                        | ((size_bytes[2] & 0x7F) << 7)
                        | (size_bytes[3] & 0x7F)
                    )

                start_offset = size + 10  # Header (10) + Data

                # Check for Footer present flag (Bit 4 of byte 5)
                # Only valid for ID3v2.4, but harmless to check if flags exist
                # Spec: https://id3.org/id3v2.4.0-structure#section-3.4
                if version >= 4:
                    flags = header[5]
                    if flags & 0x10:
                        start_offset += 10  # Footer size

            # Check for ID3v1 at end
            # Spec: https://id3.org/ID3v1
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            end_offset = file_size

            # ID3v1 is last 128 bytes if it starts with TAG
            if file_size > 128:
                f.seek(-128, os.SEEK_END)
                if f.read(3) == b"TAG":
                    end_offset = file_size - 128

            # Read audio data
            f.seek(start_offset)
            bytes_to_read = end_offset - start_offset

            if bytes_to_read <= 0:
                # Fallback: just hash the whole file if parsing failed
                # or offsets are invalid
                f.seek(0)
                bytes_to_read = file_size

            # Read in chunks
            chunk_size = 65536
            while bytes_to_read > 0:
                chunk = f.read(min(chunk_size, bytes_to_read))
                if not chunk:
                    break
                sha256.update(chunk)
                bytes_to_read -= len(chunk)

        return sha256.hexdigest()
    except Exception:
        logger.exception("Error calculating audio hash")
        return None

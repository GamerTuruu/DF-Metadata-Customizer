"""Core utilities for reading/writing Song ID3 tags and embedded JSON metadata."""

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

from mutagen.id3 import APIC, COMM, ID3, TALB, TDRC, TIT2, TPE1, TPOS, TRCK, ID3NoHeaderError
from PIL import Image
from tinytag import TinyTag

logger = logging.getLogger(__name__)

SUPPORTED_FILES_TYPES = {".mp3"}


def extract_json_from_song(path: str) -> dict | None:
    """Return parsed JSON dict or None."""
    if not path:
        return None
    
    try:
        tags = TinyTag.get(path, tags=True, image=False)
        if not tags:
            return None

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

    except Exception as e:
        logger.debug(f"Could not extract JSON from {path}: {e}")
        return None

    return comm_data


def get_id3_tags(path: str) -> dict[str, str]:
    """Return dictionary of standard ID3 tags."""
    if not path:
        return {}
    
    try:
        tags = TinyTag.get(path, tags=True, image=False)
    except Exception:
        logger.debug(f"Error reading ID3 tags from {path}")
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
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()

        # Remove existing COMM frames
        tags.delall("COMM::ved")

        # Convert JSON to compact string format for saving
        if isinstance(json_data, str):
            # If string provided, parse and re-compact it
            parsed = json.loads(json_data)
            json_str = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
        else:
            # Compact the dict
            json_str = json.dumps(json_data, ensure_ascii=False, separators=(",", ":"))

        # Create COMM frame with UTF-8 encoding
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


def write_id3_tags(path: str, metadata: dict) -> bool:
    """Write standard ID3 tags (title/artist/album/track/disc/date)."""
    try:
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()

        def set_or_clear(frame_id: str, frame_obj):
            if frame_obj is None:
                tags.delall(frame_id)
            else:
                tags.setall(frame_id, [frame_obj])

        title = str(metadata.get("Title", "")).strip()
        artist = str(metadata.get("Artist", "")).strip()
        album = str(metadata.get("Album", "")).strip()
        track = str(metadata.get("Track", "")).strip()
        disc = str(metadata.get("Discnumber", "") or metadata.get("Disc", "")).strip()
        date = str(metadata.get("Date", "")).strip()

        set_or_clear("TIT2", TIT2(encoding=3, text=title) if title else None)
        set_or_clear("TPE1", TPE1(encoding=3, text=artist) if artist else None)
        set_or_clear("TALB", TALB(encoding=3, text=album) if album else None)
        set_or_clear("TRCK", TRCK(encoding=3, text=track) if track else None)
        set_or_clear("TPOS", TPOS(encoding=3, text=disc) if disc else None)
        set_or_clear("TDRC", TDRC(encoding=3, text=date) if date else None)

        tags.save(path)
        return True
    except Exception:
        logger.exception("Error writing ID3 tags")
        return False


def get_cover_art(path: str) -> bytes | None:
    """Extract cover art from MP3 file."""
    try:
        tags = ID3(path)
        for frame in tags.values():
            if isinstance(frame, APIC):
                return frame.data
    except Exception:
        logger.exception("Error reading cover art")
    return None


def set_cover_art(path: str, image_data: bytes) -> bool:
    """Set cover art for an MP3 file."""
    try:
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()

        # Remove existing APIC frames
        tags.delall("APIC")

        # Add new cover art
        tags.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,  # Front cover
                desc="",
                data=image_data,
            ),
        )

        tags.save(path)
        return True
    except Exception:
        logger.exception("Error setting cover art")
        return False


def get_file_hash(path: str) -> str:
    """Get SHA256 hash of file for change detection."""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        logger.exception("Error calculating file hash")
        return ""


def play_audio_file(path: str) -> bool:
    """Open audio file with default player."""
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        elif platform.system() == "Windows":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        logger.exception("Error playing audio file")
        return False

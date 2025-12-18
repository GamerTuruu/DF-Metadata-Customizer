"""Utilities for reading/writing MP3 ID3 tags and embedded JSON metadata."""
import json
import os
import platform
import re
from functools import lru_cache
from io import BytesIO
import shutil
import subprocess

from mutagen.id3 import APIC, COMM, ID3, TALB, TDRC, TIT2, TPE1, TPOS, TRCK, ID3NoHeaderError
from mutagen.mp3 import MP3
from PIL import Image

JSON_FIND_RE = re.compile(r"\{.*\}", re.DOTALL)


@lru_cache(maxsize=1000)
def extract_json_from_mp3_cached(path):
    """Cached version of extract_json_from_mp3"""
    return extract_json_from_mp3(path)


def extract_json_from_mp3(path):
    """Return (parsed JSON dict, prefix_text) or (None, None)."""
    try:
        audio = MP3(path)
        if not audio.tags:
            return None, None
        # Gather COMM frames
        comms = [v for k, v in audio.tags.items() if k.startswith("COMM")]
        for c in comms:
            text = ""
            try:
                # COMM frame: .text may be list
                text = "".join(c.text) if hasattr(c, "text") else str(c)
            except Exception:
                text = str(c)
            m = JSON_FIND_RE.search(text)
            if m:
                raw_json = m.group(0)
                # FIXED: Get the exact prefix without adding extra space
                prefix_text = text[: m.start()].strip()

                try:
                    json_data = json.loads(raw_json)
                    return json_data, prefix_text
                except Exception:
                    # try sanitize
                    try:
                        json_data = json.loads(raw_json.replace("'", '"'))
                        return json_data, prefix_text
                    except Exception:
                        continue
        return None, None
    except Exception:
        return None, None


def write_json_to_mp3(path, json_data):
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
        if isinstance(json_data, str):
            # If it's already a string, use it directly
            json_str = json_data
        else:
            # If it's a dict, convert to JSON string
            json_str = json.dumps(json_data, ensure_ascii=False)

        # FIXED: Create COMM frame with proper encoding and description
        tags.add(
            COMM(
                encoding=3,  # UTF-8
                lang="ved",  # Use 'ved' for custom archive
                desc="",  # Empty description
                text=json_str,
            )
        )

        # Save the tags
        tags.save(path)
        return True
    except Exception as e:
        print(f"Error writing JSON to MP3: {e}")
        return False


def read_cover_from_mp3(path):
    """Return (PIL Image, mime) or (None, None)."""
    try:
        tags = ID3(path)
    except Exception:
        return None, None
    apics = tags.getall("APIC")
    if not apics:
        return None, None
    ap = apics[0]
    try:
        img = Image.open(BytesIO(ap.data))
        return img, ap.mime
    except Exception:
        return None, None


def write_id3_tags(
    path,
    title=None,
    artist=None,
    album=None,
    track=None,
    disc=None,
    date=None,
    cover_bytes=None,
    cover_mime="image/jpeg",
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
    except Exception as e:
        print("Error writing tags:", e)
        return False
    return True

def play_song(file_path) -> bool:
    """Play a song using the system's default audio player - IMPROVED for Ubuntu"""
    if platform.system() == "Windows":
        os.startfile(file_path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.run(["open", file_path])
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
        error_message = ""

        for cmd in methods:
            try:
                # Check if command exists
                if shutil.which(cmd[0]) is not None:
                    # Run with subprocess.Popen to avoid blocking
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    success = True
                    print(f"Playing with: {' '.join(cmd)}")
                    break
            except Exception as e:
                error_message = str(e)
                continue

        return success
    return True

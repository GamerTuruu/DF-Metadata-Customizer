"""Audio hashing utilities for comparing raw audio data."""

import xxhash
from mutagen.id3 import ID3, ID3NoHeaderError


def get_audio_hash(file_path: str) -> str | None:
    """
    Calculate hash of raw audio data (excluding metadata tags).
    
    This function strips ID3v2 headers and ID3v1 footers before hashing,
    allowing comparison of the actual audio content regardless of metadata.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Hexadecimal hash string, or None if an error occurred
    """
    try:
        # Get ID3v2 header size
        try:
            audio_tags = ID3(file_path)
            header_size = audio_tags.size  # Full tag size including header
        except ID3NoHeaderError:
            header_size = 0

        # Read the entire file
        with open(file_path, 'rb') as f:
            file_data = f.read()

        # Check for ID3v1 footer (128 bytes at the end starting with 'TAG')
        footer_size = 128 if file_data[-128:].startswith(b'TAG') else 0
        
        # Extract only the audio frames (strip header and footer)
        end_index = len(file_data) - footer_size
        raw_audio = file_data[header_size:end_index]

        # Hash the raw audio
        return xxhash.xxh64(raw_audio).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

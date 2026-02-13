"""Audio hashing utilities for comparing raw audio data."""

import mmap
import os

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
        try:
            audio_tags = ID3(file_path)
            header_size = audio_tags.size  # Mutagen provides the full tag size including header
        except ID3NoHeaderError:
            header_size = 0

        with open(file_path, 'rb') as f:
            file_data = f.read()

        footer_size = 128 if file_data[-128:].startswith(b'TAG') else 0
        
        end_index = len(file_data) - footer_size
        raw_audio = file_data[header_size:end_index]

        return xxhash.xxh64(raw_audio).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def get_audio_hash_optimized(file_path: str, chunk_size: int = 65536) -> str | None:
    """
    Calculate hash of raw audio data using streaming for better memory efficiency.
    
    This optimized version reads the file in chunks, making it more suitable
    for large files without loading the entire file into memory at once.
    
    Args:
        file_path: Path to the audio file
        chunk_size: Size of chunks to read (default: 64KB)
        
    Returns:
        Hexadecimal hash string, or None if an error occurred
    """
    try:
        # 1. Calculate boundaries without reading data
        try:
            audio_tags = ID3(file_path)
            header_size = audio_tags.size
        except ID3NoHeaderError:
            header_size = 0

        file_size = os.path.getsize(file_path)
        
        # Check for ID3v1 footer (128 bytes at end)
        footer_size = 0
        with open(file_path, 'rb') as f:
            if file_size > 128:
                f.seek(-128, os.SEEK_END)
                if f.read(3) == b'TAG':
                    footer_size = 128

            # 2. Stream the audio data to the hasher
            hasher = xxhash.xxh64()
            f.seek(header_size)
            
            # Calculate how many bytes we actually need to hash
            remaining_bytes = file_size - header_size - footer_size
            
            while remaining_bytes > 0:
                # Read either the chunk size or what's left
                to_read = min(chunk_size, remaining_bytes)
                data = f.read(to_read)
                if not data:
                    break
                hasher.update(data)
                remaining_bytes -= len(data)

        return hasher.hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def get_audio_hash_fast(file_path: str) -> str | None:
    """
    Calculate hash of raw audio data using memory mapping for maximum performance.
    
    This version uses memory mapping which is significantly faster for large files
    as it avoids copying data into Python's memory space.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Hexadecimal hash string, or None if an error occurred
    """
    try:
        # 1. Get header size without reading the whole file
        try:
            audio_tags = ID3(file_path)
            header_size = audio_tags.size
        except ID3NoHeaderError:
            header_size = 0

        file_size = os.path.getsize(file_path)
        
        with open(file_path, 'rb') as f:
            # 2. Check for ID3v1 footer (last 128 bytes) without reading whole file
            footer_size = 0
            if file_size > 128:
                f.seek(-128, os.SEEK_END)
                if f.read(3) == b'TAG':
                    footer_size = 128
            
            # 3. Use memory mapping for the "raw" audio portion
            # This is significantly faster for large files
            if file_size - header_size - footer_size <= 0:
                return None

            with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:
                # Slice the mmap (this is a memory view, not a copy)
                raw_audio_view = mm[header_size : file_size - footer_size]
                return xxhash.xxh64(raw_audio_view).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def get_audio_hash_short(file_path: str) -> str | None:
    """
    Calculate hash of only the last 500 bytes of raw audio data.
    
    This is a quick fingerprinting method that hashes only a small portion
    of the audio. Useful for fast comparisons when full hashing is not needed.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Hexadecimal hash string, or None if an error occurred
    """
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()

        footer_size = 128 if file_data[-128:].startswith(b'TAG') else 0
        
        end_index = len(file_data) - footer_size
        raw_audio = file_data[end_index-500:end_index]

        return xxhash.xxh64(raw_audio).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def get_audio_hash_short_fast(file_path: str) -> str | None:
    """
    Calculate hash of only the last 1000 bytes using optimized seeking.
    
    Combines the speed of minimal data reading with efficient file seeking.
    Most efficient method for quick fingerprinting of audio files.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Hexadecimal hash string, or None if an error occurred
    """
    try:
        file_size = os.path.getsize(file_path)
        footer_size = 0
        with open(file_path, 'rb') as f:
            if file_size > 128:
                f.seek(-128, os.SEEK_END)
                if f.read(3) == b'TAG':
                    footer_size = 128

            f.seek(-1000, os.SEEK_END-footer_size)
            data = f.read(1000)

        return xxhash.xxh64(data).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

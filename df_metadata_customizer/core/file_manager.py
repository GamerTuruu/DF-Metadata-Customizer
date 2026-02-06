"""Core file manager for metadata caching and management."""

import json
import logging
import re
from pathlib import Path

import polars as pl

from df_metadata_customizer.core.metadata import MetadataFields, SongMetadata
from df_metadata_customizer.core.song_utils import extract_json_from_song, get_id3_tags

logger = logging.getLogger(__name__)


class FileManager:
    """Manages file metadata using Polars DataFrame."""

    def __init__(self) -> None:
        """Initialize DataFrame storage."""
        # Schema for the DataFrame
        self.schema = {
            "path": pl.Utf8,
            "song_id": pl.Utf8,
            MetadataFields.TITLE: pl.Utf8,
            MetadataFields.ARTIST: pl.Utf8,
            MetadataFields.COVER_ARTIST: pl.Utf8,
            MetadataFields.VERSION: pl.Float64,
            MetadataFields.DISC: pl.Utf8,
            MetadataFields.TRACK: pl.Utf8,
            MetadataFields.DATE: pl.Utf8,
            MetadataFields.COMMENT: pl.Utf8,
            MetadataFields.SPECIAL: pl.Utf8,
            "raw_json": pl.Object,
        }
        self.df = pl.DataFrame(schema=self.schema)
        # Staging area for new/modified data before commit to DF
        self._staging: dict[str, dict] = {}

    def commit(self) -> None:
        """Commit staged changes to the DataFrame."""
        if not self._staging:
            return

        # Convert staging to rows
        rows = []
        for path, jsond in self._staging.items():
            title = jsond.get(MetadataFields.TITLE, "")
            artist = jsond.get(MetadataFields.ARTIST, "")
            cover_artist = jsond.get(MetadataFields.COVER_ARTIST, "")
            song_id = f"{title}|{artist}|{cover_artist}"

            # Robust version parsing
            raw_ver = jsond.get(MetadataFields.VERSION, 0)
            try:
                version = float(raw_ver)
            except (ValueError, TypeError):
                # Try extracting number (including decimals)
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(raw_ver))
                version = float(nums[0]) if nums else 0.0

            rows.append(
                {
                    "path": path,
                    "song_id": song_id,
                    MetadataFields.TITLE: title,
                    MetadataFields.ARTIST: artist,
                    MetadataFields.COVER_ARTIST: cover_artist,
                    MetadataFields.VERSION: version,
                    MetadataFields.DISC: jsond.get(MetadataFields.DISC, ""),
                    MetadataFields.TRACK: jsond.get(MetadataFields.TRACK, ""),
                    MetadataFields.DATE: jsond.get(MetadataFields.DATE, ""),
                    MetadataFields.COMMENT: jsond.get(MetadataFields.COMMENT, ""),
                    MetadataFields.SPECIAL: jsond.get(MetadataFields.SPECIAL, ""),
                    "raw_json": jsond,
                },
            )

        new_df = pl.DataFrame(rows, schema=self.schema, orient="row")

        # Remove existing paths from main DF that are in staging
        if self.df.height > 0:
            staging_paths = list(self._staging.keys())
            self.df = self.df.filter(~pl.col("path").is_in(staging_paths))
            self.df = self.df.vstack(new_df)
        else:
            self.df = new_df

        self._staging.clear()

    def get_song_versions(self, song_id: str) -> list[float]:
        """Get all versions for a song ID."""
        self.commit()
        if self.df.height == 0:
            return []

        # Filter DF by song_id
        versions = self.df.filter(pl.col("song_id") == song_id).select(MetadataFields.VERSION).unique().to_series().to_list()
        return sorted(versions) if versions else []

    def get_latest_version(self, song_id: str) -> float:
        """Get latest version string for a song ID."""
        versions = self.get_song_versions(song_id)
        if not versions:
            return 0.0

        return max(versions)

    def is_latest_version(self, song_id: str, version: float) -> bool:
        """Check if a given version is the latest for a song ID."""
        return version == self.get_latest_version(song_id)

    def update_file_data(self, file_path: str, json_data: dict) -> None:
        """Update the file data cache (stages change)."""
        self._staging[file_path] = json_data

    def update_file_path(self, old_path: str, new_path: str) -> None:
        """Update the file path in the cache (e.g., if a file is renamed)."""
        # Get data first
        data = self.get_file_data(old_path)

        # Remove old from staging if present
        if old_path in self._staging:
            del self._staging[old_path]

        # Remove old from DF if present
        if self.df.height > 0:
            self.df = self.df.filter(pl.col("path") != old_path)

        # Add new to staging
        self._staging[new_path] = data

    def clear(self) -> None:
        """Clear the file data cache."""
        self.df = self.df.clear()
        self._staging.clear()

    def get_file_data(self, file_path: str) -> dict:
        """Get JSON data from a file."""
        # Check staging first
        if file_path in self._staging:
            return self._staging[file_path]

        # Check DataFrame
        if self.df.height > 0:
            # Filter for the path
            res = self.df.filter(pl.col("path") == file_path)
            if not res.is_empty():
                row = res.row(0, named=True)
                return row["raw_json"]

        # Not found, load from disk
        jsond = extract_json_from_song(file_path) or {}
        return jsond

    def load_folder(self, folder_path: str | Path) -> None:
        """Load all supported audio files from a folder."""
        folder = Path(folder_path)
        if not folder.is_dir():
            logger.error(f"Folder not found: {folder}")
            return

        # Clear existing data
        self.clear()

        # Find all supported audio files
        from df_metadata_customizer.core.song_utils import SUPPORTED_FILES_TYPES
        audio_files = []
        for ext in SUPPORTED_FILES_TYPES:
            audio_files.extend(folder.rglob(f"*{ext}"))
        
        logger.info(f"Found {len(audio_files)} audio files in {folder}")

        for audio_file in audio_files:
            file_path = str(audio_file.resolve())
            json_data = extract_json_from_song(file_path) or {}
            self.update_file_data(file_path, json_data)

        self.commit()

    def get_all_files(self) -> list[dict]:
        """Get all loaded files as list of dictionaries."""
        self.commit()
        if self.df.height == 0:
            return []
        return self.df.to_dicts()

    def get_file_by_path(self, file_path: str) -> SongMetadata | None:
        """Get SongMetadata object for a specific file."""
        json_data = self.get_file_data(file_path)
        if not json_data:
            return None

        title = json_data.get(MetadataFields.TITLE, "")
        artist = json_data.get(MetadataFields.ARTIST, "")
        cover_artist = json_data.get(MetadataFields.COVER_ARTIST, "")
        song_id = f"{title}|{artist}|{cover_artist}"
        version = json_data.get(MetadataFields.VERSION, 0)
        is_latest = self.is_latest_version(song_id, float(version))

        id3_data = get_id3_tags(file_path)

        return SongMetadata(json_data, file_path, is_latest=is_latest, id3_data=id3_data)

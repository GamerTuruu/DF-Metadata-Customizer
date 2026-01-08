"""Utility file to manage file metadata and caching."""

import json
import re
from pathlib import Path

import polars as pl

from df_metadata_customizer import mp3_utils
from df_metadata_customizer.song_metadata import MetadataFields, SongMetadata


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
        versions = self.df.filter(pl.col("song_id") == song_id).select("Version").unique().to_series().to_list()
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
        jsond = mp3_utils.extract_json_from_mp3(file_path) or {}

        if jsond:
            cleaned_jsond = {}
            for key, value in jsond.items():
                if isinstance(value, bytes):
                    try:
                        cleaned_jsond[key] = value.decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            cleaned_jsond[key] = value.decode("latin-1")
                        except Exception:
                            cleaned_jsond[key] = str(value)
                else:
                    cleaned_jsond[key] = value
            jsond = cleaned_jsond

        # Stage the loaded data
        self._staging[file_path] = jsond
        return jsond

    def get_metadata(self, file_path: str) -> SongMetadata:
        """Get SongMetadata object for a file."""
        jsond = self.get_file_data(file_path)

        # Calculate is_latest
        title = jsond.get(MetadataFields.TITLE, "") or Path(file_path).stem
        artist = jsond.get(MetadataFields.ARTIST, "")
        cover_artist = jsond.get(MetadataFields.COVER_ARTIST, "")
        song_id = f"{title}|{artist}|{cover_artist}"

        # Parse version
        raw_ver = jsond.get(MetadataFields.VERSION, 0)
        try:
            version = float(raw_ver)
        except (ValueError, TypeError):
            version = 0.0

        is_latest = self.is_latest_version(song_id, version)

        return SongMetadata(jsond, file_path, is_latest=is_latest)

    def get_view_data(self, paths: list[str]) -> pl.DataFrame:
        """Get data for specific paths in order, formatted for treeview."""
        # Ensure any staged changes are applied before querying
        self.commit()

        if not paths:
            return pl.DataFrame()

        # Create a DF from the requested paths to preserve order and index
        paths_df = pl.DataFrame({"path": paths, "orig_index": range(len(paths))})

        if self.df.height == 0:
            # Return empty data structure with correct schema if no data loaded
            cols = [
                MetadataFields.UI_TITLE,
                MetadataFields.UI_ARTIST,
                MetadataFields.UI_COVER_ARTIST,
                MetadataFields.UI_VERSION,
                MetadataFields.UI_DISC,
                MetadataFields.UI_TRACK,
                MetadataFields.UI_DATE,
                MetadataFields.UI_COMMENT,
                MetadataFields.UI_SPECIAL,
                MetadataFields.UI_FILE,
            ]
            # Create empty columns with appropriate types
            return paths_df.with_columns(
                [pl.lit("").alias(c) for c in cols if c != MetadataFields.UI_FILE],
            ).with_columns(pl.lit("").alias(MetadataFields.UI_FILE))

        # Join with stored data
        joined = paths_df.join(self.df, on="path", how="left")

        # Fill nulls for files not in DF
        joined = joined.with_columns(pl.col(pl.Utf8).fill_null(""))
        joined = joined.with_columns(pl.col(pl.Int64).fill_null(0))
        joined = joined.with_columns(pl.col(pl.Float64).fill_null(0.0))

        # Add 'file' column (filename) using map_elements for safety with paths
        return joined.with_columns(
            pl.col("path")
            .map_elements(lambda p: Path(p).name if p else "", return_dtype=pl.Utf8)
            .alias(MetadataFields.FILE),
        )

    def calculate_statistics(self) -> dict:
        """Calculate statistics using Polars."""
        # Ensure any staged changes are applied before calculating
        self.commit()

        if self.df.height == 0:
            return dict.fromkeys(
                [
                    "all_songs",
                    "unique_ta",
                    "unique_tac",
                    "neuro_solos_unique",
                    "neuro_solos_total",
                    "evil_solos_unique",
                    "evil_solos_total",
                    "duets_unique",
                    "duets_total",
                    "other_unique",
                    "other_total",
                ],
                0,
            )

        df = self.df

        # Filter out empty titles
        df = df.filter(pl.col(MetadataFields.TITLE).str.strip_chars() != "")

        stats = {}
        stats["all_songs"] = df.height

        # Unique TA
        stats["unique_ta"] = df.select([MetadataFields.TITLE, MetadataFields.ARTIST]).n_unique()

        # Unique TAC
        stats["unique_tac"] = df.select(
            [MetadataFields.TITLE, MetadataFields.ARTIST, MetadataFields.COVER_ARTIST],
        ).n_unique()

        # Categories
        # Neuro
        neuro_df = df.filter(pl.col(MetadataFields.COVER_ARTIST) == "Neuro")
        stats["neuro_solos_total"] = neuro_df.height
        stats["neuro_solos_unique"] = neuro_df.select([MetadataFields.TITLE, MetadataFields.ARTIST]).n_unique()

        # Evil
        evil_df = df.filter(pl.col(MetadataFields.COVER_ARTIST) == "Evil")
        stats["evil_solos_total"] = evil_df.height
        stats["evil_solos_unique"] = evil_df.select([MetadataFields.TITLE, MetadataFields.ARTIST]).n_unique()

        # Duets
        duets_df = df.filter(pl.col(MetadataFields.COVER_ARTIST) == "Neuro & Evil")
        stats["duets_total"] = duets_df.height
        stats["duets_unique"] = duets_df.select([MetadataFields.TITLE, MetadataFields.ARTIST]).n_unique()

        # Other
        other_df = df.filter(~pl.col(MetadataFields.COVER_ARTIST).is_in(["Neuro", "Evil", "Neuro & Evil"]))
        stats["other_total"] = other_df.height
        stats["other_unique"] = other_df.select([MetadataFields.TITLE, MetadataFields.ARTIST]).n_unique()

        return stats

    @staticmethod
    def prepare_json_for_save(json_text: str) -> tuple[str, dict]:
        """Parse JSON text and prepare it for saving to MP3."""
        # Parse the JSON to validate it
        json_data = json.loads(json_text)

        full_comment = json.dumps(json_data, ensure_ascii=False, separators=(",", ":"))

        return full_comment, json_data

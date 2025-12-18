"""Utility file to manage file metadata and caching."""

import re
from pathlib import Path

import polars as pl

from df_metadata_customizer import mp3_utils


class FileManager:
    """Manages file metadata using Polars DataFrame."""

    def __init__(self) -> None:
        """Initialize DataFrame storage."""
        # Schema for the DataFrame
        self.schema = {
            "path": pl.Utf8,
            "song_id": pl.Utf8,
            "Title": pl.Utf8,
            "Artist": pl.Utf8,
            "CoverArtist": pl.Utf8,
            "Version": pl.Float64,
            "Discnumber": pl.Utf8,
            "Track": pl.Utf8,
            "Date": pl.Utf8,
            "Comment": pl.Utf8,
            "Special": pl.Utf8,
            "_prefix": pl.Utf8,
            "raw_json": pl.Object,
            "is_latest": pl.Boolean,
        }
        self.df = pl.DataFrame(schema=self.schema)
        # Staging area for new/modified data before commit to DF
        self._staging: dict[str, tuple[dict, str]] = {}

    def commit(self) -> None:
        """Commit staged changes to the DataFrame."""
        if not self._staging:
            return

        # Convert staging to rows
        rows = []
        for path, (jsond, prefix) in self._staging.items():
            title = jsond.get("Title", "")
            artist = jsond.get("Artist", "")
            cover_artist = jsond.get("CoverArtist", "")
            song_id = f"{title}|{artist}|{cover_artist}"

            # Robust version parsing
            raw_ver = jsond.get("Version", 0)
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
                    "Title": title,
                    "Artist": artist,
                    "CoverArtist": cover_artist,
                    "Version": version,
                    "Discnumber": jsond.get("Discnumber", ""),
                    "Track": jsond.get("Track", ""),
                    "Date": jsond.get("Date", ""),
                    "Comment": jsond.get("Comment", ""),
                    "Special": jsond.get("Special", ""),
                    "_prefix": prefix,
                    "raw_json": jsond,
                    "is_latest": False,
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

    def update_version_info(self) -> None:
        """Recalculate version info and update DataFrame is_latest column."""
        self.commit()
        if self.df.height == 0:
            return

        # Group by song_id to find versions
        grouped = self.df.group_by("song_id").agg(
            pl.col("Version"),
            pl.col("path"),
        )

        latest_paths = set()

        for row in grouped.iter_rows(named=True):
            versions = row["Version"]
            paths = row["path"]

            if not versions:
                continue

            # Find latest version
            max_ver = max(versions)

            # Identify paths that have this version
            for i, v in enumerate(versions):
                if v == max_ver:
                    latest_paths.add(paths[i])

        # Update is_latest column in DF
        self.df = self.df.with_columns(pl.col("path").is_in(latest_paths).alias("is_latest"))

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
        latest_version = self.get_latest_version(song_id)
        return version == latest_version

    def update_file_data(self, file_path: str, json_data: dict, prefix_text: str) -> None:
        """Update the file data cache (stages change)."""
        self._staging[file_path] = (json_data, prefix_text)

    def update_file_path(self, old_path: str, new_path: str) -> None:
        """Update the file path in the cache (e.g., if a file is renamed)."""
        # Get data first
        data = self.get_file_data_with_prefix(old_path)

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

    def get_file_data_with_prefix(self, file_path: str) -> tuple[dict, str]:
        """Get both JSON data and prefix text."""
        # Check staging first
        if file_path in self._staging:
            return self._staging[file_path]

        # Check DataFrame
        if self.df.height > 0:
            # Filter for the path
            res = self.df.filter(pl.col("path") == file_path)
            if not res.is_empty():
                row = res.row(0, named=True)
                return row["raw_json"], row["_prefix"]

        # Not found, load from disk
        jsond, prefix = mp3_utils.extract_json_from_mp3_cached(file_path) or ({}, "")

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
        self._staging[file_path] = (jsond, prefix)
        return jsond, prefix

    def get_file_data(self, file_path: str) -> dict:
        """Get cached file data with fallback (backward compatibility)."""
        jsond, _prefix = self.get_file_data_with_prefix(file_path)
        return jsond

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
            cols = ["Title", "Artist", "CoverArtist", "Version", "Discnumber", "Track", "Date", "Comment", "Special", "file"]
            # Create empty columns with appropriate types
            return paths_df.with_columns([pl.lit("").alias(c) for c in cols if c != "file"]).with_columns(pl.lit("").alias("file"))

        # Join with stored data
        joined = paths_df.join(self.df, on="path", how="left")

        # Fill nulls for files not in DF
        joined = joined.with_columns(pl.col(pl.Utf8).fill_null(""))
        joined = joined.with_columns(pl.col(pl.Int64).fill_null(0))
        joined = joined.with_columns(pl.col(pl.Float64).fill_null(0.0))

        # Add 'file' column (filename) using map_elements for safety with paths
        return joined.with_columns(
            pl.col("path").map_elements(lambda p: Path(p).name if p else "", return_dtype=pl.Utf8).alias("file")
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
        df = df.filter(pl.col("Title").str.strip_chars() != "")

        stats = {}
        stats["all_songs"] = df.height

        # Unique TA
        stats["unique_ta"] = df.select(["Title", "Artist"]).n_unique()

        # Unique TAC
        stats["unique_tac"] = df.select(["Title", "Artist", "CoverArtist"]).n_unique()

        # Categories
        # Neuro
        neuro_df = df.filter(pl.col("CoverArtist") == "Neuro")
        stats["neuro_solos_total"] = neuro_df.height
        stats["neuro_solos_unique"] = neuro_df.select(["Title", "Artist"]).n_unique()

        # Evil
        evil_df = df.filter(pl.col("CoverArtist") == "Evil")
        stats["evil_solos_total"] = evil_df.height
        stats["evil_solos_unique"] = evil_df.select(["Title", "Artist"]).n_unique()

        # Duets
        duets_df = df.filter(pl.col("CoverArtist") == "Neuro & Evil")
        stats["duets_total"] = duets_df.height
        stats["duets_unique"] = duets_df.select(["Title", "Artist"]).n_unique()

        # Other
        other_df = df.filter(~pl.col("CoverArtist").is_in(["Neuro", "Evil", "Neuro & Evil"]))
        stats["other_total"] = other_df.height
        stats["other_unique"] = other_df.select(["Title", "Artist"]).n_unique()

        return stats

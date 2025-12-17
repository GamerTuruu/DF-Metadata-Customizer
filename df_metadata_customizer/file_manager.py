"""Utility file to manage file metadata and caching."""

from df_metadata_customizer import mp3_utils


class FileManager:
    """Manages file metadata."""

    def __init__(self) -> None:
        """Initialize wrapped dictionary file data."""
        # Cache for file metadata (stores tuple: (json_data, prefix_text))
        self.file_data_cache: dict[str, tuple[dict, str]] = {}

    def update_file_data(self, file_path: str, json_data: dict, prefix_text: str) -> None:
        """Update the file data cache."""
        self.file_data_cache[file_path] = (json_data, prefix_text)

    def update_file_path(self, old_path: str, new_path: str) -> None:
        """Update the file path in the cache (e.g., if a file is renamed)."""
        if old_path in self.file_data_cache:
            self.file_data_cache[new_path] = self.file_data_cache.pop(old_path)

    def clear(self) -> None:
        """Clear the file data cache."""
        self.file_data_cache.clear()

    def get_file_data_with_prefix(self, file_path: str) -> tuple[dict, str]:
        """Get both JSON data and prefix text."""
        if file_path not in self.file_data_cache:
            jsond, prefix = mp3_utils.extract_json_from_mp3_cached(file_path) or ({}, "")

            # FIXED: Clean up any encoding issues in the JSON data
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

            self.file_data_cache[file_path] = (jsond, prefix)
        return self.file_data_cache[file_path]

    def get_file_data(self, file_path: str) -> dict:
        """Get cached file data with fallback (backward compatibility)."""
        jsond, _prefix = self.get_file_data_with_prefix(file_path)
        return jsond

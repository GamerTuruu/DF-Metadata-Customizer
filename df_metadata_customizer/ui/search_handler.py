"""Search handling utilities for filtering songs."""

from df_metadata_customizer.core.metadata import MetadataFields


class SearchHandler:
    """Handle advanced search queries and filtering."""

    def __init__(self, parent):
        self.parent = parent

    def _extract_numeric_value(self, value_str: str) -> tuple:
        """Extract numeric value and whether it contains denominator (track format)."""
        value_str = str(value_str).strip()
        if not value_str:
            return 0, 0

        if "/" in value_str:
            first, *_ = value_str.split("/", 1)
            try:
                return 1, float(first.strip())
            except ValueError:
                return 1, 0

        try:
            return 0, float(value_str)
        except ValueError:
            return 0, 0

    def _get_numeric_value_for_search(self, value_str: str) -> float:
        """Extract numeric value for search comparisons."""
        try:
            return float(value_str)
        except ValueError:
            value_str = str(value_str).strip()
            if "/" in value_str:
                first_part = value_str.split("/")[0].strip()
                try:
                    return float(first_part)
                except ValueError:
                    return float('nan')
            return float('nan')

    def _parse_search_value(self, value_str: str) -> str:
        """Parse search value, handling quoted strings."""
        value_str = value_str.strip()
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1].lower()
        return value_str.lower()

    def _is_latest_version_match(self, file_data: dict, want_latest: bool) -> bool:
        """Return True if file_data matches latest/not-latest version for its song ID."""
        song_id = file_data.get("song_id")
        if not song_id:
            title = file_data.get(MetadataFields.TITLE, "")
            artist = file_data.get(MetadataFields.ARTIST, "")
            cover_artist = file_data.get(MetadataFields.COVER_ARTIST, "")
            song_id = f"{title}|{artist}|{cover_artist}"

        version = file_data.get(MetadataFields.VERSION, 0)
        try:
            version = float(version)
        except (ValueError, TypeError):
            version = 0.0

        return self.parent.file_manager.is_latest_version(song_id, version) == want_latest

    def apply_search(self, query: str):
        """Filter songs with advanced search and refresh sort."""
        query = query.strip()
        self.parent.filtered_indices = []

        if not query:
            self.parent.filtered_indices = list(range(len(self.parent.song_files)))
        else:
            for i, file_data in enumerate(self.parent.song_files):
                match = False

                if "!=" in query:
                    parts = query.split("!=", 1)
                    if len(parts) == 2:
                        search_field = parts[0].strip().lower()
                        search_value = self._parse_search_value(parts[1])

                        if search_field == "version" and search_value in {"latest", "not latest", "not_latest", "notlatest"}:
                            want_latest = (search_value == "latest")
                            match = not self._is_latest_version_match(file_data, want_latest)
                        else:
                            for key, value in file_data.items():
                                if search_field in key.lower():
                                    if str(value).lower() != search_value:
                                        match = True
                                        break

                elif "==" in query:
                    parts = query.split("==", 1)
                    if len(parts) == 2:
                        search_field = parts[0].strip().lower()
                        search_value = self._parse_search_value(parts[1])

                        if search_field == "version" and search_value in {"latest", "not latest", "not_latest", "notlatest"}:
                            want_latest = (search_value == "latest")
                            match = self._is_latest_version_match(file_data, want_latest)
                        else:
                            for key, value in file_data.items():
                                if search_field in key.lower():
                                    if str(value).lower() == search_value:
                                        match = True
                                        break

                elif ">=" in query:
                    parts = query.split(">=", 1)
                    if len(parts) == 2:
                        search_field, search_value = parts[0].strip().lower(), parts[1].strip()
                        for key, value in file_data.items():
                            if search_field in key.lower():
                                try:
                                    if self._get_numeric_value_for_search(str(value)) >= float(search_value):
                                        match = True
                                        break
                                except Exception:
                                    pass

                elif "<=" in query:
                    parts = query.split("<=", 1)
                    if len(parts) == 2:
                        search_field, search_value = parts[0].strip().lower(), parts[1].strip()
                        for key, value in file_data.items():
                            if search_field in key.lower():
                                try:
                                    if self._get_numeric_value_for_search(str(value)) <= float(search_value):
                                        match = True
                                        break
                                except Exception:
                                    pass

                elif ">" in query:
                    parts = query.split(">", 1)
                    if len(parts) == 2:
                        search_field, search_value = parts[0].strip().lower(), parts[1].strip()
                        for key, value in file_data.items():
                            if search_field in key.lower():
                                try:
                                    if self._get_numeric_value_for_search(str(value)) > float(search_value):
                                        match = True
                                        break
                                except Exception:
                                    pass

                elif "<" in query:
                    parts = query.split("<", 1)
                    if len(parts) == 2:
                        search_field, search_value = parts[0].strip().lower(), parts[1].strip()
                        for key, value in file_data.items():
                            if search_field in key.lower():
                                try:
                                    if self._get_numeric_value_for_search(str(value)) < float(search_value):
                                        match = True
                                        break
                                except Exception:
                                    pass

                elif "=" in query:
                    parts = query.split("=", 1)
                    if len(parts) == 2:
                        search_field = parts[0].strip().lower()
                        search_value = self._parse_search_value(parts[1])

                        if search_field == "version" and search_value in {"latest", "not latest", "not_latest", "notlatest"}:
                            want_latest = (search_value == "latest")
                            match = self._is_latest_version_match(file_data, want_latest)
                        else:
                            for key, value in file_data.items():
                                if search_field in key.lower():
                                    if search_value in str(value).lower():
                                        match = True
                                        break

                else:
                    query_lower = query.lower()
                    search_fields = ["Title", "Artist", "CoverArtist", "Special", "Version"]
                    for field in search_fields:
                        if query_lower in str(file_data.get(field, "")).lower():
                            match = True
                            break

                if match:
                    self.parent.filtered_indices.append(i)

        self.parent.filtered_count_label.setText(f"{len(self.parent.filtered_indices)} found")
        if hasattr(self.parent, 'sort_handler'):
            self.parent.sort_handler.apply_sort()
        else:
            self.parent.on_sort_changed()

"""Sorting handler for multi-level sorting."""

from df_metadata_customizer.core.metadata import MetadataFields


class ReverseStr(str):
    """String subclass that reverses comparison operators for descending sort."""
    __slots__ = ()
    
    def __lt__(self, other):
        return str.__gt__(self, other)
    
    def __le__(self, other):
        return str.__ge__(self, other)
    
    def __gt__(self, other):
        return str.__lt__(self, other)
    
    def __ge__(self, other):
        return str.__le__(self, other)


class SortHandler:
    """Handle multi-level sorting using SortControlsManager rules."""

    def __init__(self, parent, sort_controls_manager):
        self.parent = parent
        self.sort_controls_manager = sort_controls_manager
        self._sort_key_cache = {}  # Cache for computed sort keys

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

    def apply_sort(self):
        """Apply multi-level sorting to filtered indices."""
        if not self.parent.song_files:
            return

        if not self.parent.filtered_indices:
            self.parent.populate_tree()
            return

        sort_keys = self.sort_controls_manager.get_sort_rules()
        
        # Clear cache since sort rules changed
        self._sort_key_cache.clear()

        def get_sort_key(idx):
            # Check cache first (massive speedup on re-sorts)
            if idx in self._sort_key_cache:
                return self._sort_key_cache[idx]
            
            if idx >= len(self.parent.song_files):
                result = ("",) * len(sort_keys)
            else:
                file_data = self.parent.song_files[idx]
                keys = []
                numeric_fields = {"Version", "Date", "Disc", "Track"}

                for field_text, ascending in sort_keys:
                    field_map = {
                        "Title": MetadataFields.TITLE,
                        "Artist": MetadataFields.ARTIST,
                        "Cover Artist": MetadataFields.COVER_ARTIST,
                        "Version": MetadataFields.VERSION,
                        "Date": MetadataFields.DATE,
                        "Disc": MetadataFields.DISC,
                        "Track": MetadataFields.TRACK,
                        "Special": MetadataFields.SPECIAL,
                        "Filename": MetadataFields.FILE,
                    }

                    field = field_map.get(field_text)
                    if field:
                        val = file_data.get(field, "")

                        if field_text in numeric_fields:
                            try:
                                if field_text == "Track":
                                    has_denom, num_val = self._extract_numeric_value(str(val))
                                    if not ascending:
                                        num_val = -num_val if num_val else num_val
                                        has_denom = 1 - has_denom
                                    keys.append((0, has_denom, num_val))
                                else:
                                    numeric_val = float(val)
                                    if not ascending:
                                        numeric_val = -numeric_val
                                    keys.append((0, 0, numeric_val))
                            except (ValueError, TypeError):
                                str_val = str(val).lower()
                                if not ascending:
                                    str_val = ReverseStr(str_val)
                                keys.append((1, 0, str_val))
                        else:
                            str_val = str(val).lower()
                            if not ascending:
                                str_val = ReverseStr(str_val)
                            keys.append((1, 0, str_val))

                result = tuple(keys)
            
            # Cache the result
            self._sort_key_cache[idx] = result
            return result

        self.parent.filtered_indices.sort(key=get_sort_key)
        # Preserve selection and pass sort keys for efficient update
        self.parent.populate_tree(preserve_selection=True)

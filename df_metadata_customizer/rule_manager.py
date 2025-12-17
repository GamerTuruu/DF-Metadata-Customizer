""" "Rule management for metadata customization."""

import re
import warnings

from df_metadata_customizer.widgets import SortRuleRow


class RuleManager:
    """Utility class for managing and applying metadata rules."""

    @staticmethod
    def group_rules_by_logic(rules: list[dict[str, str]]) -> list[list[dict]]:
        """Group rules into logical blocks based on AND/OR operators."""
        if not rules:
            return []

        blocks = []
        current_block = []

        for i, rule in enumerate(rules):
            if i == 0:
                current_block.append(rule)
                continue
            logic = rule.get("logic", "AND")
            if logic == "AND":
                current_block.append(rule)
            else:
                if current_block:
                    blocks.append(current_block)
                current_block = [rule]
        if current_block:
            blocks.append(current_block)
        return blocks

    @staticmethod
    def eval_rule_block(
        rule_block: list[dict[str, str]],
        fv: dict[str, str],
        latest_versions: dict | None = None,
    ) -> bool:
        """Evaluate a block of rules with AND logic (all rules in block must match)."""
        if not rule_block:
            return False
        return all(RuleManager.eval_single_rule(rule, fv, latest_versions) for rule in rule_block)

    @staticmethod
    def eval_single_rule(rule: dict[str, str], fv: dict[str, str], latest_versions: dict | None = None) -> bool:
        """Evaluate a single rule."""
        field = rule.get("if_field", "")
        op = rule.get("if_operator", "")
        val = rule.get("if_value", "")
        actual = str(fv.get(field, ""))

        if op == "is":
            return actual == val
        if op == "contains":
            return val in actual
        if op == "starts with":
            return actual.startswith(val)
        if op == "ends with":
            return actual.endswith(val)
        if op == "is empty":
            return actual == ""
        if op == "is not empty":
            return actual != ""
        if op == "is latest version":
            title = fv.get("Title", "")
            artist = fv.get("Artist", "")
            coverartist = fv.get("CoverArtist", "")
            version = fv.get("Version", "0")
            return RuleManager.is_latest_version_full(title, artist, coverartist, version, latest_versions)
        if op == "is not latest version":
            title = fv.get("Title", "")
            artist = fv.get("Artist", "")
            coverartist = fv.get("CoverArtist", "")
            version = fv.get("Version", "0")
            return not RuleManager.is_latest_version_full(title, artist, coverartist, version, latest_versions)
        return False

    @staticmethod
    def is_latest_version(title: str, version: str, latest_versions: dict | None = None) -> bool:
        """Check if the given title and version is the latest version."""
        warnings.warn(
            "is_latest_version is deprecated, use is_latest_version_full instead",
            DeprecationWarning,
            stacklevel=2,
        )

        if not latest_versions:
            return True

        # Find the song key for this title (we need to search since we don't have artist/coverartist here)
        for song_key, latest_version in latest_versions.items():
            if title in song_key:  # Simple matching - could be improved
                return latest_version == version
        return True

    @staticmethod
    def is_latest_version_full(
        title: str,
        artist: str,
        coverartist: str,
        version: str,
        latest_versions: dict | None = None,
    ) -> bool:
        """Check if the given title, artist, coverartist, and version is the latest version."""
        if not latest_versions:
            return True
        song_key = f"{title}|{artist}|{coverartist}"
        return latest_versions.get(song_key, version) == version

    @staticmethod
    def apply_template(template: str, fv: dict[str, str]) -> str:
        """Apply template with field values."""
        if not template:
            return ""
        try:
            result = template
            for k, v in fv.items():
                placeholder = "{" + k + "}"
                if placeholder in result:
                    safe_value = str(v) if v is not None else ""
                    result = result.replace(placeholder, safe_value)
            # Also handle common field names
            common_fields = {
                "Title": fv.get("Title", ""),
                "Artist": fv.get("Artist", ""),
                "CoverArtist": fv.get("CoverArtist", ""),
                "Version": fv.get("Version", ""),
                "Discnumber": fv.get("Discnumber", ""),
                "Track": fv.get("Track", ""),
                "Date": fv.get("Date", ""),
                "Comment": fv.get("Comment", ""),
                "Special": fv.get("Special", ""),
            }
            for field_name, field_value in common_fields.items():
                placeholder = "{" + field_name + "}"
                if placeholder in result:
                    safe_value = str(field_value) if field_value is not None else ""
                    result = result.replace(placeholder, safe_value)
        except Exception:
            return ""
        return result

    @staticmethod
    def apply_rules_list(rules: list[dict[str, str]], fv: dict[str, str], latest_versions: dict | None = None) -> str:
        """Apply rules list to field values with AND/OR grouping."""
        if not rules:
            return ""
        rule_blocks = RuleManager.group_rules_by_logic(rules)
        for block in rule_blocks:
            if RuleManager.eval_rule_block(block, fv, latest_versions):
                template = block[-1].get("then_template", "")
                result = RuleManager.apply_template(template, fv)
                if result.strip():
                    return result
        return ""

    @staticmethod
    def get_sort_rules(sort_rules: list[SortRuleRow]) -> list[dict]:
        """Get list of sort rules as dictionaries."""
        return [rule.get_sort_rule() for rule in sort_rules]

    @staticmethod
    def apply_multi_sort(sort_rules: list[SortRuleRow], file_data: dict) -> dict | list:
        """Apply multiple sort rules to file data."""
        warnings.warn(
            "apply_multi_sort is deprecated, use apply_multi_sort_with_dict instead",
            DeprecationWarning,
            stacklevel=2,
        )

        rules = RuleManager.get_sort_rules(sort_rules)

        if not rules:
            return file_data

        def sort_key(item: tuple[int, dict]) -> tuple:
            """Create a sort key based on multiple rules."""
            key_parts = []
            for rule in rules:
                field = rule["field"]
                order = rule["order"]

                # Get the value for this field (item[0] is index, rest are data)
                field_index = [
                    "title",
                    "artist",
                    "coverartist",
                    "version",
                    "disc",
                    "track",
                    "date",
                    "comment",
                    "special",
                    "file",
                ].index(field)
                value = item[field_index + 1]  # +1 because item[0] is the original index

                # Convert to appropriate type for sorting
                if field in ["disc", "track", "special"]:
                    try:
                        value = int(value) if value else 0
                    except (ValueError, TypeError):
                        value = 0
                elif field in ["version"]:
                    try:
                        # Try to extract numbers from version string
                        nums = re.findall(r"\d+", str(value))
                        value = int(nums[0]) if nums else 0
                    except (ValueError, TypeError):
                        value = 0
                else:
                    value = str(value).lower()

                # Reverse order if descending
                if order == "desc":
                    if isinstance(value, (int, float)):
                        value = -value
                    else:
                        # For strings, we'll handle in the sort function
                        pass

                key_parts.append(value)
            return tuple(key_parts)

        # Sort the data
        try:
            sorted_data = sorted(file_data, key=sort_key)

            # For descending string sorts, we need to handle them separately
            for i, rule in enumerate(rules):
                if rule["order"] == "desc" and rule["field"] in [
                    "title",
                    "artist",
                    "coverartist",
                    "comment",
                    "file",
                    "date",
                ]:
                    # Reverse the order for this specific field level
                    # This is a simplified approach - for true multi-level descending sorts,
                    # we'd need a more complex algorithm
                    if i == 0:  # Only apply to primary sort for simplicity
                        sorted_data.reverse()
                    break

        except Exception as e:
            print(f"Sorting error: {e}")
            return file_data

        return sorted_data

    @staticmethod
    def apply_multi_sort_with_dict(sort_rules: list[SortRuleRow], file_data: dict) -> dict:
        """Apply multiple sort rules to file data stored as dictionaries."""
        rules = RuleManager.get_sort_rules(sort_rules)

        if not rules:
            return file_data

        def sort_key(item: tuple[int, dict]) -> tuple:
            """Create a sort key based on multiple rules."""
            _orig_idx, field_values = item
            key_parts = []
            for rule in rules:
                field = rule["field"]
                order = rule["order"]

                # Get the value for this field from the dictionary
                value = field_values.get(field, "")

                # Convert to appropriate type for sorting
                if field in ["disc", "track", "special"]:
                    try:
                        value = int(value) if value else 0
                    except (ValueError, TypeError):
                        value = 0
                elif field in ["version"]:
                    try:
                        # Try to extract numbers from version string
                        nums = re.findall(r"\d+", str(value))
                        value = int(nums[0]) if nums else 0
                    except (ValueError, TypeError):
                        value = 0
                else:
                    value = str(value).lower()

                # Reverse order if descending
                if order == "desc":
                    if isinstance(value, (int, float)):
                        value = -value
                    else:
                        # For strings, we'll handle in the sort function
                        pass

                key_parts.append(value)
            return tuple(key_parts)

        # Sort the data
        try:
            sorted_data = sorted(file_data, key=sort_key)

            # For descending string sorts, we need to handle them separately
            for i, rule in enumerate(rules):
                if rule["order"] == "desc" and rule["field"] in [
                    "title",
                    "artist",
                    "coverartist",
                    "comment",
                    "file",
                    "date",
                ]:
                    # Reverse the order for this specific field level
                    # This is a simplified approach - for true multi-level descending sorts,
                    # we'd need a more complex algorithm
                    if i == 0:  # Only apply to primary sort for simplicity
                        sorted_data.reverse()
                    break

        except Exception as e:
            print(f"Sorting error: {e}")
            return file_data

        return sorted_data

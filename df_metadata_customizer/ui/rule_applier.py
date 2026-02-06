"""Rule application logic for metadata updates."""

import re

from df_metadata_customizer.core.metadata import MetadataFields
from df_metadata_customizer.core.song_utils import get_id3_tags


class RuleApplier:
    """Apply rule logic to metadata and build ID3 payloads."""

    def __init__(self, parent):
        self.parent = parent

    def rule_matches(self, json_data: dict, field: str, operator: str, condition: str) -> bool:
        """Check if a rule condition matches against json data."""
        field_value = str(json_data.get(field, "")).lower()
        condition_lower = str(condition).lower()

        if operator == "is":
            return field_value == condition_lower
        if operator == "contains":
            return condition_lower in field_value
        if operator == "starts with":
            return field_value.startswith(condition_lower)
        if operator == "ends with":
            return field_value.endswith(condition_lower)
        if operator == "is empty":
            return field_value == ""
        if operator == "is not empty":
            return field_value != ""
        if operator == "is latest version":
            return json_data.get("_is_latest", False)
        if operator == "is not latest version":
            return not json_data.get("_is_latest", False)
        return False

    def render_template(self, template: str, data: dict) -> str:
        """Render a template like '{Artist} ({CoverArtist})' using data values."""
        def repl(match):
            key = match.group(1)
            val = data.get(key, "")
            if isinstance(val, (int, float)):
                if isinstance(val, float) and val.is_integer():
                    return str(int(val))
                return str(val)
            return str(val)

        return re.sub(r"\{([^}]+)\}", repl, template or "")

    def apply_rules_to_metadata(self, metadata: dict) -> dict:
        """Apply current rule tabs to metadata and return updated dict."""
        result = metadata.copy()
        tab_targets = {
            "title": MetadataFields.TITLE,
            "artist": MetadataFields.ARTIST,
            "album": "Album",
        }

        for tab_name in ["title", "artist", "album"]:
            rules = self.parent.rules_panel_manager.collect_rules_for_tab(tab_name)
            target_field = tab_targets.get(tab_name, "")
            if not rules or not target_field:
                continue

            i = 0
            while i < len(rules):
                rule_data = rules[i]
                try:
                    logic = rule_data.get("logic", "AND")
                    if_field = rule_data.get("if_field", "")
                    if_operator = rule_data.get("if_operator", "")
                    if_value = rule_data.get("if_value", "")
                    then_template = rule_data.get("then_template", "")
                    is_first = rule_data.get("is_first", False)

                    is_group_marker = (logic in ["AND", "OR"]) and not then_template
                    is_first_with_template = is_first and then_template

                    if is_first_with_template and self.rule_matches(result, if_field, if_operator, if_value):
                        result[target_field] = self.render_template(then_template, result)
                        break

                    if logic == "OR" and then_template and self.rule_matches(result, if_field, if_operator, if_value):
                        result[target_field] = self.render_template(then_template, result)
                        break

                    if (is_group_marker or (is_first and not then_template)) and self.rule_matches(result, if_field, if_operator, if_value):
                        j = i + 1
                        result_found = False
                        group_field, group_operator, group_value = if_field, if_operator, if_value

                        while j < len(rules) and not result_found:
                            next_rule = rules[j]
                            next_logic = next_rule.get("logic", "AND")
                            next_field = next_rule.get("if_field", "")
                            next_operator = next_rule.get("if_operator", "")
                            next_value = next_rule.get("if_value", "")
                            next_template = next_rule.get("then_template", "")
                            next_is_first = next_rule.get("is_first", False)

                            if next_is_first and next_template:
                                break

                            if next_logic == "AND" and not next_template and not next_is_first:
                                if not (next_field == group_field and next_operator == group_operator and next_value == group_value):
                                    break
                            elif next_logic == "OR" and not next_template:
                                if not (next_field == group_field and next_operator == group_operator and next_value == group_value):
                                    break
                            elif next_is_first and not next_template:
                                break
                            elif next_logic == "AND" and next_template:
                                if self.rule_matches(result, next_field, next_operator, next_value):
                                    result[target_field] = self.render_template(next_template, result)
                                    result_found = True
                                    break
                            j += 1

                        if result_found:
                            break

                except Exception:
                    pass
                i += 1

        return result

    def build_id3_metadata(self, raw_json: dict, file_path: str, rule_result: dict) -> dict:
        """Build ID3 metadata dict to write, using current ID3 and rule output."""
        id3_data = get_id3_tags(file_path) if file_path else {}
        id3_out = dict(id3_data)

        id3_out["Title"] = str(rule_result.get(MetadataFields.TITLE, id3_out.get("Title", "")))
        id3_out["Artist"] = str(rule_result.get(MetadataFields.ARTIST, id3_out.get("Artist", "")))
        id3_out["Album"] = str(rule_result.get("Album", id3_out.get("Album", "")))

        if not id3_out.get("Track"):
            id3_out["Track"] = str(raw_json.get(MetadataFields.TRACK, ""))
        if not id3_out.get("Discnumber"):
            id3_out["Discnumber"] = str(raw_json.get(MetadataFields.DISC, ""))
        if not id3_out.get("Date"):
            id3_out["Date"] = str(raw_json.get(MetadataFields.DATE, ""))

        return id3_out

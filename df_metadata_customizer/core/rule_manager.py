"""Core rule management for metadata customization."""

import logging
import re
from typing import Final

import polars as pl

from df_metadata_customizer.core.metadata import MetadataFields

logger = logging.getLogger(__name__)


class RuleManager:
    """Utility class for managing and applying metadata rules."""

    COL_MAP: Final = {
        MetadataFields.UI_TITLE: MetadataFields.TITLE,
        MetadataFields.UI_ARTIST: MetadataFields.ARTIST,
        MetadataFields.UI_COVER_ARTIST: MetadataFields.COVER_ARTIST,
        MetadataFields.UI_VERSION: MetadataFields.VERSION,
        MetadataFields.UI_DISC: MetadataFields.DISC,
        MetadataFields.UI_TRACK: MetadataFields.TRACK,
        MetadataFields.UI_DATE: MetadataFields.DATE,
        MetadataFields.UI_COMMENT: MetadataFields.COMMENT,
        MetadataFields.UI_SPECIAL: MetadataFields.SPECIAL,
        MetadataFields.UI_FILE: MetadataFields.FILE,
    }

    @staticmethod
    def parse_search_query(q: str) -> tuple[list[dict[str, str]], list[str]]:
        """Parse search query into structured filters and free-text terms."""
        if not q:
            return [], []

        q_orig = q
        filters = []

        # regex to find key<op>value tokens; value may be quoted
        fields_pattern = "|".join(re.escape(k) for k in MetadataFields.get_ui_keys())
        token_re = re.compile(
            rf"(?i)\b({fields_pattern})\s*(==|!=|>=|<=|>|<|=|~|!~)\s*(?:\"([^\"]+)\"|'([^']+)'|(\S+))",
        )

        # find all matches
        for m in token_re.finditer(q_orig):
            key = m.group(1).lower()
            op = m.group(2)
            val = m.group(3) or m.group(4) or m.group(5) or ""

            # Special handling for version=latest
            if key == MetadataFields.UI_VERSION and val.lower() == "latest":
                filters.append({"field": key, "op": "==", "value": "_latest_"})
            else:
                filters.append({"field": key, "op": op, "value": val})

        # remove matched portions from query to leave free text
        q_clean = token_re.sub("", q_orig)

        # remaining free terms (split by whitespace, ignore empty)
        free_terms = [t.lower() for t in re.split(r"\s+", q_clean.strip()) if t.strip()]

        return filters, free_terms

    @staticmethod
    def apply_search_filter(
        df: pl.DataFrame,
        filters: list[dict[str, str]],
        free_terms: list[str],
    ) -> pl.DataFrame:
        """Apply search filters to Polars DataFrame."""
        if df.height == 0:
            return df

        filtered_df = df

        for flt in filters:
            field = flt["field"]
            op = flt["op"]
            val = flt["value"]
            col_name = RuleManager.COL_MAP.get(field, field)

            if col_name not in filtered_df.columns and field != MetadataFields.UI_VERSION:
                continue

            # Special handling for version=latest
            if field == MetadataFields.UI_VERSION and val == "_latest_":
                if "is_latest" in filtered_df.columns:
                    filtered_df = filtered_df.filter(pl.col("is_latest"))
                continue

            col_expr = pl.col(col_name)

            # Handle numeric version comparison
            if col_name == MetadataFields.VERSION:
                try:
                    val_float = float(val)
                    if op == ">":
                        filtered_df = filtered_df.filter(col_expr > val_float)
                    elif op == "<":
                        filtered_df = filtered_df.filter(col_expr < val_float)
                    elif op == ">=":
                        filtered_df = filtered_df.filter(col_expr >= val_float)
                    elif op == "<=":
                        filtered_df = filtered_df.filter(col_expr <= val_float)
                    elif op == "==":
                        filtered_df = filtered_df.filter(col_expr == val_float)
                    elif op in ("!=", "!~"):
                        filtered_df = filtered_df.filter(col_expr != val_float)
                except ValueError:
                    pass
                continue

            # String comparison
            if op == ">":
                filtered_df = filtered_df.filter(col_expr.str.to_lowercase() > val.lower())
            elif op == "<":
                filtered_df = filtered_df.filter(col_expr.str.to_lowercase() < val.lower())
            elif op == ">=":
                filtered_df = filtered_df.filter(col_expr.str.to_lowercase() >= val.lower())
            elif op == "<=":
                filtered_df = filtered_df.filter(col_expr.str.to_lowercase() <= val.lower())
            elif op in ("=", "~"):  # Contains
                filtered_df = filtered_df.filter(col_expr.str.to_lowercase().str.contains(re.escape(val.lower())))
            elif op == "==":  # Exact
                filtered_df = filtered_df.filter(col_expr.str.to_lowercase() == val.lower())
            elif op in ("!=", "!~"):  # Not contains
                filtered_df = filtered_df.filter(~col_expr.str.to_lowercase().str.contains(re.escape(val.lower())))

        # Free terms
        if free_terms:
            search_cols = [pl.col(c) for c in RuleManager.COL_MAP.values() if c in filtered_df.columns]
            if search_cols:
                concat_expr = pl.concat_str(search_cols, separator=" ").str.to_lowercase()
                for term in free_terms:
                    filtered_df = filtered_df.filter(concat_expr.str.contains(re.escape(term)))

        return filtered_df

    @staticmethod
    def apply_conditional_rule(
        json_data: dict,
        field: str,
        operator: str,
        condition: str,
        action_field: str,
        action_value: str,
    ) -> dict:
        """Apply a single conditional rule to metadata."""
        # Check if condition matches
        matches = False
        field_value = str(json_data.get(field, "")).lower()
        condition_lower = str(condition).lower()

        if operator == "is":
            matches = field_value == condition_lower
        elif operator == "contains":
            matches = condition_lower in field_value
        elif operator == "starts with":
            matches = field_value.startswith(condition_lower)
        elif operator == "ends with":
            matches = field_value.endswith(condition_lower)
        elif operator == "is empty":
            matches = field_value == ""
        elif operator == "is not empty":
            matches = field_value != ""
        elif operator == "is latest version":
            matches = json_data.get("_is_latest", False)
        elif operator == "is not latest version":
            matches = not json_data.get("_is_latest", False)

        # If condition matches, apply action
        if matches:
            json_data[action_field] = action_value

        return json_data

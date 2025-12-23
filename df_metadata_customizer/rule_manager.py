"""Rule management for metadata customization."""

import re
from typing import Final

import polars as pl

from df_metadata_customizer.song_metadata import MetadataFields, SongMetadata
from df_metadata_customizer.widgets import SortRuleRow


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

            # Numeric comparison - simplified to string comparison for now
            # as most fields are Utf8 in schema
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
        metadata: SongMetadata,
    ) -> bool:
        """Evaluate a block of rules with AND logic (all rules in block must match)."""
        if not rule_block:
            return False
        return all(RuleManager.eval_single_rule(rule, metadata) for rule in rule_block)

    @staticmethod
    def eval_single_rule(rule: dict[str, str], metadata: SongMetadata) -> bool:
        """Evaluate a single rule."""
        field = rule.get("if_field", "")
        op = rule.get("if_operator", "")
        val = rule.get("if_value", "")

        actual = metadata.get(field)

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
            return metadata.is_latest
        if op == "is not latest version":
            return not metadata.is_latest
        return False

    @staticmethod
    def apply_template(template: str, metadata: SongMetadata) -> str:
        """Apply template with field values."""
        if not template:
            return ""
        try:
            return re.sub(r"\{([^}]+)\}", lambda m: metadata.get(m.group(1)), template)
        except Exception:
            return ""

    @staticmethod
    def apply_rules_list(rules: list[dict[str, str]], metadata: SongMetadata) -> str:
        """Apply rules list to field values with AND/OR grouping."""
        if not rules:
            return ""
        rule_blocks = RuleManager.group_rules_by_logic(rules)
        for block in rule_blocks:
            if RuleManager.eval_rule_block(block, metadata):
                template = block[-1].get("then_template", "")
                result = RuleManager.apply_template(template, metadata)
                if result.strip():
                    return result
        return ""

    @staticmethod
    def get_sort_rules(sort_rules: list[SortRuleRow]) -> list[dict]:
        """Get list of sort rules as dictionaries."""
        return [rule.get_sort_rule() for rule in sort_rules]

    @staticmethod
    def apply_multi_sort_polars(sort_rules: list[SortRuleRow], df: pl.DataFrame) -> pl.DataFrame:
        """Apply multiple sort rules to Polars DataFrame."""
        rules = RuleManager.get_sort_rules(sort_rules)
        if not rules:
            return df

        sort_exprs = []
        by_cols = []
        descending = []

        for i, rule in enumerate(rules):
            field = rule["field"]
            col_name = RuleManager.COL_MAP.get(field, field)
            if col_name not in df.columns:
                continue

            is_desc = rule["order"] == "desc"
            base_col = pl.col(col_name)

            match field:
                case MetadataFields.UI_TRACK:
                    # Track: split into number and total
                    cols = [f"_sort_{i}_n", f"_sort_{i}_t"]
                    sort_exprs.extend(
                        [
                            base_col.str.extract(r"^(\d+)", 1).cast(pl.Int64, strict=False).fill_null(0).alias(cols[0]),
                            base_col.str.extract(r"/(\d+)", 1).cast(pl.Int64, strict=False).fill_null(0).alias(cols[1]),
                        ],
                    )
                    by_cols.extend(cols)
                    descending.extend([is_desc, is_desc])

                case MetadataFields.UI_DISC | MetadataFields.UI_SPECIAL:
                    # Integer fields
                    col = f"_sort_{i}"
                    sort_exprs.append(base_col.cast(pl.Int64, strict=False).fill_null(0).alias(col))
                    by_cols.append(col)
                    descending.append(is_desc)

                case MetadataFields.UI_VERSION:
                    # Float fields
                    col = f"_sort_{i}"
                    sort_exprs.append(base_col.fill_null(0.0).alias(col))
                    by_cols.append(col)
                    descending.append(is_desc)

                case _:
                    # String fields (case-insensitive)
                    col = f"_sort_{i}"
                    sort_exprs.append(base_col.str.to_lowercase().alias(col))
                    by_cols.append(col)
                    descending.append(is_desc)

        if by_cols:
            return df.with_columns(sort_exprs).sort(by_cols, descending=descending, maintain_order=True).drop(by_cols)

        return df

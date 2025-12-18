""" "Rule management for metadata customization."""

import re
import warnings

import polars as pl

from df_metadata_customizer.widgets import SortRuleRow


class RuleManager:
    """Utility class for managing and applying metadata rules."""

    @staticmethod
    def parse_search_query(q: str) -> tuple[list[dict[str, str]], list[str]]:
        """Parse search query into structured filters and free-text terms."""
        if not q:
            return [], []

        q_orig = q
        filters = []

        # regex to find key<op>value tokens; value may be quoted
        token_re = re.compile(
            r"(?i)\b(title|artist|coverartist|version|disc|track|date|comment|special|file)\s*(==|!=|>=|<=|>|<|=|~|!~)\s*(?:\"([^\"]+)\"|'([^']+)'|(\S+))",
        )

        # find all matches
        for m in token_re.finditer(q_orig):
            key = m.group(1).lower()
            op = m.group(2)
            val = m.group(3) or m.group(4) or m.group(5) or ""

            # Special handling for version=latest
            if key == "version" and val.lower() == "latest":
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

        # Map UI field names to DataFrame columns
        col_map = {
            "title": "Title",
            "artist": "Artist",
            "coverartist": "CoverArtist",
            "version": "Version",
            "disc": "Discnumber",
            "track": "Track",
            "date": "Date",
            "comment": "Comment",
            "special": "Special",
            "file": "file",
        }

        for flt in filters:
            field = flt["field"]
            op = flt["op"]
            val = flt["value"]
            col_name = col_map.get(field, field)

            if col_name not in filtered_df.columns and field != "version":
                continue

            # Special handling for version=latest
            if field == "version" and val == "_latest_":
                if "is_latest" in filtered_df.columns:
                    filtered_df = filtered_df.filter(pl.col("is_latest"))
                continue

            col_expr = pl.col(col_name)

            # Handle numeric version comparison
            if col_name == "Version":
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
            search_cols = [pl.col(c) for c in col_map.values() if c in filtered_df.columns]
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
        fv: dict[str, str | bool],
    ) -> bool:
        """Evaluate a block of rules with AND logic (all rules in block must match)."""
        if not rule_block:
            return False
        return all(RuleManager.eval_single_rule(rule, fv) for rule in rule_block)

    @staticmethod
    def eval_single_rule(rule: dict[str, str], fv: dict[str, str | bool]) -> bool:
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
            return bool(fv.get("is_latest", False))
        if op == "is not latest version":
            return not bool(fv.get("is_latest", False))
        return False

    @staticmethod
    def apply_template(template: str, fv: dict[str, str | bool]) -> str:
        """Apply template with field values."""
        if not template:
            return ""
        try:
            result = template
            for k, v in fv.items():
                if k == "is_latest":
                    continue
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
    def apply_rules_list(rules: list[dict[str, str]], fv: dict[str, str | bool]) -> str:
        """Apply rules list to field values with AND/OR grouping."""
        if not rules:
            return ""
        rule_blocks = RuleManager.group_rules_by_logic(rules)
        for block in rule_blocks:
            if RuleManager.eval_rule_block(block, fv):
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
    def apply_multi_sort_polars(sort_rules: list[SortRuleRow], df: pl.DataFrame) -> pl.DataFrame:
        """Apply multiple sort rules to Polars DataFrame."""
        rules = RuleManager.get_sort_rules(sort_rules)
        if not rules:
            return df

        by = []
        descending = []
        temp_cols = []

        # We need to create temporary columns for sorting to handle types and case-insensitivity
        df_sorted = df

        for i, rule in enumerate(rules):
            field = rule["field"]
            order = rule["order"]

            # Map UI field names to DataFrame columns
            col_name = {
                "title": "Title",
                "artist": "Artist",
                "coverartist": "CoverArtist",
                "version": "Version",
                "disc": "Discnumber",
                "track": "Track",
                "date": "Date",
                "comment": "Comment",
                "special": "Special",
                "file": "file",
            }.get(field, field)

            # Check if column exists
            if col_name not in df.columns:
                continue

            temp_col = f"_sort_{i}"
            expr = pl.col(col_name)

            # Handle numeric casting for specific columns
            if field in ["disc", "track", "special"]:
                # Cast to Int64, fill null/error with 0
                expr = expr.cast(pl.Int64, strict=False).fill_null(0)
            elif field == "version":
                # Already Float64
                expr = expr.fill_null(0.0)
            else:
                # String sort - lowercase for case insensitive
                expr = expr.str.to_lowercase()

            df_sorted = df_sorted.with_columns(expr.alias(temp_col))
            by.append(temp_col)
            descending.append(order == "desc")
            temp_cols.append(temp_col)

        if by:
            df_sorted = df_sorted.sort(by, descending=descending)
            df_sorted = df_sorted.drop(temp_cols)

        return df_sorted

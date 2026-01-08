"""Sorting Component."""

import contextlib
from tkinter import messagebox
from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent
from df_metadata_customizer.song_metadata import MetadataFields
from df_metadata_customizer.widgets import SortRuleRow


class SortingComponent(AppComponent):
    """Sorting component for managing sort rules in the song list."""

    @override
    def initialize_state(self) -> None:
        self.max_sort_rules = 5
        self.sort_rules: list[SortRuleRow] = []

    @override
    def setup_ui(self) -> None:
        self.configure(fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)

        # Sort container for multiple sort rules
        self.sort_container = ctk.CTkFrame(self, fg_color="transparent")
        self.sort_container.grid(row=0, column=0, columnspan=4, sticky="ew", pady=2)
        self.sort_container.grid_columnconfigure(1, weight=1)

        # Add first sort rule (cannot be deleted)
        self.add_sort_rule(is_first=True)

        # Add sort rule button
        self.add_sort_btn = ctk.CTkButton(self, text="+ Add Sort", width=80, command=lambda: self.add_sort_rule())
        self.add_sort_btn.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Search info label (next to Add Sort)
        self.search_info_label = ctk.CTkLabel(self, text="", anchor="w")
        self.search_info_label.grid(row=1, column=1, sticky="w", padx=(12, 0))

    def add_sort_rule(self, *, is_first: bool = False) -> None:
        """Add a new sort rule row."""
        # Enforce maximum number of sort rules
        if len(self.sort_rules) >= self.max_sort_rules:
            with contextlib.suppress(Exception):
                messagebox.showinfo("Sort limit", f"Maximum of {self.max_sort_rules} sort levels reached")
            return

        row = SortRuleRow(
            self.sort_container,
            move_callback=self.move_sort_rule,
            delete_callback=self.delete_sort_rule,
            is_first=is_first,
        )
        row.pack(fill="x", padx=0, pady=2)
        self.sort_rules.append(row)

        if is_first:
            row.field_var.set(MetadataFields.UI_TITLE)
        else:
            row.field_var.set(MetadataFields.UI_ARTIST)

        # Bind change events to refresh tree
        row.field_menu.configure(command=lambda _val=None: self.app.refresh_tree())
        row.order_menu.configure(command=lambda _val=None: self.app.refresh_tree())

        # Update button visibility for all rules
        self.update_sort_rule_buttons()

        # Disable add button if we've reached the max
        if hasattr(self, "add_sort_btn"):
            self.add_sort_btn.configure(state="disabled" if len(self.sort_rules) >= self.max_sort_rules else "normal")

    def move_sort_rule(self, widget: SortRuleRow, direction: int) -> None:
        """Move a sort rule up or down."""
        # Find current index; don't allow the primary (index 0) to be moved
        try:
            idx = self.sort_rules.index(widget)
        except ValueError:
            return

        if idx == 0:
            return  # primary rule cannot be moved

        new_idx = idx + direction

        # Disallow moves that go out of bounds or into the primary slot (0)
        if new_idx < 1 or new_idx >= len(self.sort_rules):
            return

        # Perform the move
        self.sort_rules.pop(idx)
        self.sort_rules.insert(new_idx, widget)

        # Repack and update UI
        self.repack_sort_rules()
        self.update_sort_rule_buttons()
        self.app.refresh_tree()

    def delete_sort_rule(self, widget: SortRuleRow) -> None:
        """Delete a sort rule (except the first one)."""
        try:
            idx = self.sort_rules.index(widget)
        except ValueError:
            return

        # Don't allow deleting the primary rule at index 0
        if idx == 0:
            return

        # Remove the widget
        self.sort_rules.pop(idx)
        widget.destroy()

        # Repack and refresh
        self.repack_sort_rules()
        self.update_sort_rule_buttons()
        self.app.refresh_tree()

    def repack_sort_rules(self) -> None:
        """Repack all sort rules in current order."""
        # Clear the container
        for child in self.sort_container.winfo_children():
            child.pack_forget()

        # Repack in current order
        for rule in self.sort_rules:
            rule.pack(fill="x", padx=0, pady=2)
        # Ensure is_first flag is kept in sync with position (only index 0 is primary)
        for i, rule in enumerate(self.sort_rules):
            rule.is_first = i == 0
            try:
                if rule.is_first:
                    rule.sort_label.configure(text="Sort by:")
                else:
                    rule.sort_label.configure(text="then by:")
            except Exception:
                pass

    def update_sort_rule_buttons(self) -> None:
        """Update button visibility for sort rules."""
        for i, rule in enumerate(self.sort_rules):
            if hasattr(rule, "up_btn"):
                # First rule (index 0) is always first and can't be moved up
                # Rule at position 1 can't move up (would become first)
                rule.up_btn.configure(state="normal" if i > 1 else "disabled")
            if hasattr(rule, "down_btn"):
                # Can't move down if it's the last rule or if moving down would make it first
                rule.down_btn.configure(state="normal" if i < len(self.sort_rules) - 1 and i != 0 else "disabled")

        # Also update Add button state according to max allowed rules
        if hasattr(self, "add_sort_btn"):
            with contextlib.suppress(Exception):
                self.add_sort_btn.configure(
                    state="disabled" if len(self.sort_rules) >= self.max_sort_rules else "normal",
                )

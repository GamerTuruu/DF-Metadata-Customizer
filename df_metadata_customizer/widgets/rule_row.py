"""Rule Row widgets for Rule Builder."""

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from df_metadata_customizer.song_metadata import MetadataFields


class SortRuleRow(ctk.CTkFrame):
    """A row widget representing a single sort rule."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        move_callback: Callable[["SortRuleRow", int], None],
        delete_callback: Callable[["SortRuleRow"], None],
        *,
        is_first: bool = False,
        **kwargs: dict,
    ) -> None:
        """Create a SortRuleRow widget."""
        super().__init__(master, **kwargs)
        self.is_first = is_first
        self.move_callback = move_callback
        self.delete_callback = delete_callback

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_columnconfigure(3, weight=0)
        self.grid_columnconfigure(4, weight=0)

        if is_first:
            self.sort_label = ctk.CTkLabel(self, text="Sort by:")
            self.sort_label.grid(row=0, column=0, padx=(6, 8), pady=6, sticky="w")
        else:
            self.sort_label = ctk.CTkLabel(self, text="then by:")
            self.sort_label.grid(row=0, column=0, padx=(6, 8), pady=6, sticky="w")

        self.field_var = tk.StringVar()
        self.field_menu = ctk.CTkOptionMenu(
            self,
            values=MetadataFields.get_ui_keys(),
            variable=self.field_var,
            width=120,
        )
        self.field_menu.grid(row=0, column=1, padx=4, pady=6, sticky="ew")

        self.order_var = tk.StringVar(value="asc")
        self.order_menu = ctk.CTkOptionMenu(self, values=["asc", "desc"], variable=self.order_var, width=80)
        self.order_menu.grid(row=0, column=2, padx=4, pady=6, sticky="w")

        if not is_first:
            self.up_btn = ctk.CTkButton(self, text="▲", width=28, command=lambda: move_callback(self, -1))
            self.up_btn.grid(row=0, column=3, padx=2, pady=6)

            self.down_btn = ctk.CTkButton(self, text="▼", width=28, command=lambda: move_callback(self, 1))
            self.down_btn.grid(row=0, column=4, padx=2, pady=6)

            self.del_btn = ctk.CTkButton(
                self,
                text="✖",
                width=28,
                fg_color="#b33",
                hover_color="#c55",
                command=lambda: delete_callback(self),
            )
            self.del_btn.grid(row=0, column=5, padx=(2, 6), pady=6)

    def get_sort_rule(self) -> dict[str, str]:
        """Return the sort rule configuration as a dictionary."""
        return {"field": self.field_var.get(), "order": self.order_var.get()}


class RuleRow(ctk.CTkFrame):
    """A row widget representing a single metadata processing rule."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        operators: list[str],
        move_callback: Callable[["RuleRow", int], None],
        delete_callback: Callable[["RuleRow"], None],
        *,
        is_first: bool = False,
        **kwargs: dict,
    ) -> None:
        """Create a RuleRow widget."""
        super().__init__(master, **kwargs)
        self.delete_callback = delete_callback
        self.move_callback = move_callback
        self.is_first = is_first

        # layout
        self.grid_columnconfigure(0, weight=0)  # AND/OR label
        self.grid_columnconfigure(1, weight=0)  # IF label
        self.grid_columnconfigure(2, weight=0)  # Field dropdown
        self.grid_columnconfigure(3, weight=0)  # Operator dropdown
        self.grid_columnconfigure(4, weight=1)  # Value entry
        self.grid_columnconfigure(5, weight=0)  # THEN label
        self.grid_columnconfigure(6, weight=1)  # Template entry
        self.grid_columnconfigure(7, weight=0)  # Up button
        self.grid_columnconfigure(8, weight=0)  # Down button
        self.grid_columnconfigure(9, weight=0)  # Delete button

        # AND/OR selector (hidden for first rule)
        self.logic_var = tk.StringVar(value="AND")
        self._create_logic_widget()

        self.if_label = ctk.CTkLabel(self, text="IF")
        self.if_label.grid(row=0, column=1, padx=(4, 4), pady=3, sticky="w")

        self.field_var = tk.StringVar()
        self.field_menu = ctk.CTkOptionMenu(
            self,
            values=MetadataFields.get_json_keys(),
            variable=self.field_var,
            width=120,
        )
        self.field_menu.grid(row=0, column=2, padx=4, pady=3, sticky="w")
        self.field_var.set(MetadataFields.get_json_keys()[0])

        self.op_var = tk.StringVar()
        self.op_menu = ctk.CTkOptionMenu(self, values=operators, variable=self.op_var, width=140)
        self.op_menu.grid(row=0, column=3, padx=4, pady=3, sticky="w")
        self.op_var.set(operators[0])

        self.value_entry = ctk.CTkEntry(self, placeholder_text="value (leave empty for 'is empty' etc.)")
        self.value_entry.grid(row=0, column=4, padx=6, pady=3, sticky="ew")

        self.then_label = ctk.CTkLabel(self, text="THEN")
        self.then_label.grid(row=0, column=5, padx=(10, 4), pady=3, sticky="w")

        self.template_entry = ctk.CTkEntry(self, placeholder_text="{Artist} (feat. {CoverArtist})")
        self.template_entry.grid(row=0, column=6, padx=6, pady=3, sticky="ew")

        self.up_btn = ctk.CTkButton(self, text="▲", width=28, command=lambda: move_callback(self, -1))
        self.up_btn.grid(row=0, column=7, padx=(6, 2), pady=3)

        self.down_btn = ctk.CTkButton(self, text="▼", width=28, command=lambda: move_callback(self, 1))
        self.down_btn.grid(row=0, column=8, padx=2, pady=3)

        # Only delete button, no up/down buttons
        self.del_btn = ctk.CTkButton(
            self,
            text="✖",
            width=28,
            fg_color="#b33",
            hover_color="#c55",
            command=lambda: delete_callback(self),
        )
        self.del_btn.grid(row=0, column=9, padx=(2, 8), pady=3)

    def _create_logic_widget(self) -> None:
        """Create or recreate the logic operator widget (AND/OR or empty label)."""
        if hasattr(self, "logic_widget"):
            self.logic_widget.destroy()

        if not self.is_first:
            self.logic_widget = ctk.CTkOptionMenu(self, values=["AND", "OR"], variable=self.logic_var, width=60)
        else:
            self.logic_widget = ctk.CTkLabel(self, text="", width=60)

        self.logic_widget.grid(row=0, column=0, padx=(6, 4), pady=3, sticky="w")

    def set_first(self, *, is_first: bool) -> None:
        """Update the rule's status as the first rule in the list."""
        if self.is_first != is_first:
            self.is_first = is_first
            self._create_logic_widget()

    def set_button_states(self, *, is_top: bool, is_bottom: bool) -> None:
        """Enable or disable move buttons based on position."""
        self.up_btn.configure(state="disabled" if is_top else "normal")
        self.down_btn.configure(state="disabled" if is_bottom else "normal")

    def get_rule(self) -> dict[str, str]:
        """Return the rule configuration as a dictionary."""
        return {
            "logic": self.logic_var.get() if not self.is_first else "AND",  # First rule defaults to AND
            "if_field": self.field_var.get(),
            "if_operator": self.op_var.get(),
            "if_value": self.value_entry.get(),
            "then_template": self.template_entry.get(),
        }

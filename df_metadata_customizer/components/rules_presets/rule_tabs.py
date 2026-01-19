"""Rule Tabs Component."""

import platform
from tkinter import messagebox
from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent
from df_metadata_customizer.song_metadata import MetadataFields
from df_metadata_customizer.widgets import RuleRow


class RuleTabsComponent(AppComponent):
    """Component managing rule tabs for Title, Artist, and Album."""

    @override
    def initialize_state(self) -> None:
        self.rule_containers: dict[str, ctk.CTkFrame] = {}

    @override
    def setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self, command=self._on_tab_changed)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        for name in ("Title", "Artist", "Album"):
            tab = self.tabview.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(1, weight=1)

            header_frame = ctk.CTkFrame(tab, fg_color="transparent")
            header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))
            header_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(header_frame, text=f"{name} Rules", font=ctk.CTkFont(weight="bold")).grid(
                row=0,
                column=0,
                sticky="w",
                padx=8,
            )

            add_btn = ctk.CTkButton(
                header_frame,
                text="+ Add Rule",
                width=80,
                command=lambda n=name: self.add_rule_to_tab(n),
            )
            add_btn.grid(row=0, column=1, padx=8, pady=2, sticky="e")

            wrapper = ctk.CTkFrame(tab)
            wrapper.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
            wrapper.grid_columnconfigure(0, weight=1)
            wrapper.grid_rowconfigure(0, weight=1)

            scroll = ctk.CTkScrollableFrame(wrapper)
            scroll.grid(row=0, column=0, sticky="nsew")
            scroll.grid_columnconfigure(0, weight=1)

            self._setup_scroll_events(scroll)
            self.rule_containers[name.lower()] = scroll

    def _on_tab_changed(self) -> None:
        """Handle tab change events to update scroll bindings."""
        current_tab = self.tabview.get().lower()
        container = self.rule_containers.get(current_tab)
        if container:
            container.update()
            self._setup_scroll_events(container)

    def add_rule_to_tab(self, tab_name: str) -> None:
        """Add a rule to the specified tab - UPDATED: With rule limit check."""
        container = self.rule_containers.get(tab_name.lower())
        if container:
            # Count current rules in this tab
            current_rules = len([w for w in container.winfo_children() if isinstance(w, RuleRow)])

            # Check if we've reached the limit
            if current_rules >= self.app.max_rules_per_tab:
                messagebox.showinfo(
                    "Rule limit",
                    f"Maximum of {self.app.max_rules_per_tab} rules reached for {tab_name}",
                )
                return

            self.add_rule(container)

            # Update button states after adding
            self.update_rule_tab_buttons()

    def add_rule(self, container: ctk.CTkFrame) -> None:
        """Add a rule row to the specified container."""
        # Count current rules to determine if this is the first one
        current_rules = len([w for w in container.winfo_children() if isinstance(w, RuleRow)])
        is_first = current_rules == 0

        row = RuleRow(
            container,
            self.app.RULE_OPS,
            move_callback=self.move_rule,
            delete_callback=self.delete_rule,
            is_first=is_first,
        )
        row.pack(fill="x", padx=6, pady=3)

        # default template suggestions based on container tab
        parent_tab = self.container_to_tab(container)
        if parent_tab == "title":
            row.template_entry.insert(0, f"{{{MetadataFields.COVER_ARTIST}}} - {{{MetadataFields.TITLE}}}")
        elif parent_tab == "artist":
            row.template_entry.insert(0, f"{{{MetadataFields.COVER_ARTIST}}}")
        elif parent_tab == "album":
            row.template_entry.insert(0, f"Archive VOL {{{MetadataFields.DISC}}}")

        # FIXED: Use force preview update for immediate response
        def update_callback(*_args: tuple) -> None:
            self.app.output_preview_component.update_preview()

        row.field_var.trace("w", update_callback)
        row.op_var.trace("w", update_callback)
        row.logic_var.trace("w", update_callback)  # Add logic change listener
        row.value_entry.bind("<KeyRelease>", lambda _e: self.app.output_preview_component.update_preview())
        row.template_entry.bind("<KeyRelease>", lambda _e: self.app.output_preview_component.update_preview())

        # Update button states for all rules in this container
        self.update_rule_button_states(container)

        # Update button states after adding
        self.update_rule_tab_buttons()
        # Initial update
        self.app.output_preview_component.update_preview()

    def move_rule(self, widget: RuleRow, direction: int) -> None:
        """Move a rule up or down."""
        container = widget.master

        # Use pack_slaves to get the current visual order
        slaves = container.pack_slaves()
        children = [w for w in slaves if isinstance(w, RuleRow)]

        try:
            idx = children.index(widget)
        except ValueError:
            return

        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(children):
            return

        # Swap in list
        children.pop(idx)
        children.insert(new_idx, widget)

        # Repack all RuleRows
        for child in children:
            child.pack_forget()

        for i, child in enumerate(children):
            child.pack(fill="x", padx=6, pady=3)
            # Update visual state
            child.set_first(is_first=i == 0)
            child.set_button_states(is_top=i == 0, is_bottom=i == len(children) - 1)

    def delete_rule(self, widget: RuleRow) -> None:
        """Delete a rule from its container."""
        container = widget.master
        children = [w for w in container.winfo_children() if isinstance(w, RuleRow)]

        if widget not in children:
            return

        # Remove the widget
        widget.destroy()

        # Update button states for remaining rules
        self.after(0, lambda: self.update_rule_button_states(container))

        # Update button states after deletion (rules are now below limit)
        self.update_rule_tab_buttons()
        self.app.output_preview_component.update_preview()

    def update_rule_tab_buttons(self) -> None:
        """Update the Add Rule buttons for each tab based on rule counts."""
        for tab_name, container in self.rule_containers.items():
            # Count current rules in this tab
            current_rules = len([w for w in container.winfo_children() if isinstance(w, RuleRow)])

            # Find the Add Rule button for this tab
            # We need to get to the header frame that contains the button
            tab = self.tabview.tab(tab_name.capitalize())
            if tab:
                # The header frame is the first child of the tab (row 0)
                header_frame = tab.grid_slaves(row=0, column=0)
                if header_frame:
                    header_frame = header_frame[0]
                    # The Add Rule button is in column 1 of the header frame
                    add_buttons = header_frame.grid_slaves(row=0, column=1)
                    if add_buttons:
                        add_button = add_buttons[0]
                        # Disable button if max rules reached
                        if current_rules >= self.app.max_rules_per_tab:
                            add_button.configure(state="disabled")
                        else:
                            add_button.configure(state="normal")

            self._setup_scroll_events(container)

    def _setup_scroll_events(self, scroll_frame: ctk.CTkScrollableFrame) -> None:
        """Set up mouse wheel scrolling for a scrollable frame."""
        if not hasattr(scroll_frame, "_parent_canvas"):
            return

        if platform.system() == "Linux" and scroll_frame.winfo_viewable():

            def _scroll(amount: int) -> None:
                if scroll_frame._parent_canvas.yview() != (0.0, 1.0):  # noqa: SLF001
                    scroll_frame._parent_canvas.yview("scroll", amount, "units")  # noqa: SLF001

            scroll_frame.bind_all("<Button-4>", lambda _: _scroll(-1))
            scroll_frame.bind_all("<Button-5>", lambda _: _scroll(1))

    def container_to_tab(self, container: ctk.CTkFrame) -> str:
        """Get tab name from container widget."""
        for tab_name, cont in self.rule_containers.items():
            if cont == container:
                return tab_name
        return "title"

    def update_rule_button_states(self, container: ctk.CTkFrame) -> None:
        """Update button states for rules in a container."""
        slaves = container.pack_slaves()
        children = [w for w in slaves if isinstance(w, RuleRow)]

        for i, child in enumerate(children):
            child.set_first(is_first=i == 0)
            child.set_button_states(is_top=i == 0, is_bottom=i == len(children) - 1)

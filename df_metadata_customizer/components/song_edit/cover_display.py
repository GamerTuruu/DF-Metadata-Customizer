"""Cover Art Display Component for Song Edit Section."""

import tkinter as tk
from collections.abc import Callable
from typing import TYPE_CHECKING, override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent

if TYPE_CHECKING:
    from df_metadata_customizer.database_reformatter import DFApp


class CoverDisplayComponent(AppComponent):
    """Component to display and interact with cover art."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        app: "DFApp",
        on_change_click: Callable[[], None],
        **kwargs: dict,
    ) -> None:
        """Initialize the CoverDisplayComponent."""
        self.on_change_click = on_change_click
        super().__init__(parent, app, **kwargs)

    @override
    def initialize_state(self) -> None:
        """Initialize component state."""
        self.tooltip_label: ctk.CTkToplevel | None = None
        self._check_job: str | None = None

    @override
    def setup_ui(self) -> None:
        """Build the UI for the component."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main container for the image
        self.image_container = ctk.CTkFrame(self, fg_color="transparent")
        self.image_container.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.image_container.grid_columnconfigure(0, weight=1)
        self.image_container.grid_rowconfigure(0, weight=1)

        self.cover_label = ctk.CTkLabel(
            self.image_container,
            text="No Cover\nClick to Add",
            corner_radius=6,
            fg_color=("gray85", "gray20"),
        )
        self.cover_label.grid(row=0, column=0, sticky="nsew")

        # Overlay for hover effect
        self.overlay_label = ctk.CTkLabel(
            self.image_container,
            text="Change Cover",
            fg_color=("#EBEBEB", "#242424"),
            corner_radius=6,
            font=("Segoe UI", 12, "bold"),
        )

        # Helper icon (Question mark)
        self.help_icon = ctk.CTkLabel(
            self,
            text="?",
            width=20,
            height=20,
            corner_radius=10,
            fg_color="gray50",
            text_color="white",
            font=("Arial", 12, "bold"),
        )
        self.help_icon.place(relx=1.0, rely=0.0, anchor="ne", x=-5, y=5)

        # Bind events for hover and click
        for widget in [self, self.image_container, self.cover_label, self.overlay_label, self.help_icon]:
            widget.bind("<Enter>", self._schedule_check)

        # Click handling
        self.cover_label.bind("<Button-1>", self._on_click)
        self.overlay_label.bind("<Button-1>", self._on_click)
        self.bind("<Button-1>", self._on_click)

    def update_image(self, ctk_image: ctk.CTkImage | None) -> None:
        """Update the displayed image."""
        if ctk_image:
            self.cover_label.configure(image=ctk_image, text="")
        else:
            self.cover_label.configure(image=None, text="No Cover\nClick to Add")

    def show_loading(self) -> None:
        """Show loading state."""
        self.cover_label.configure(image=None, text="Loading cover...")

    def show_no_cover(self, message: str = "No cover") -> None:
        """Show no cover state with optional message."""
        self.cover_label.configure(image=None, text=message)

    def show_error(self, message: str = "No cover (error)") -> None:
        """Show error state."""
        self.cover_label.configure(image=None, text=message)

    def _schedule_check(self, _event: tk.Event) -> None:
        """Start the hover check loop if not running."""
        if self._check_job:
            return
        self._check_hover()

    def _check_hover(self) -> None:
        """Periodically check mouse position to manage hover states."""
        try:
            x, y = self.winfo_pointerxy()

            # 1. Check if inside main component
            widget_x = self.winfo_rootx()
            widget_y = self.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()

            is_inside_main = (widget_x <= x <= widget_x + w) and (widget_y <= y <= widget_y + h)

            if not is_inside_main:
                self._set_overlay_visible(visible=False)
                self._hide_tooltip()
                self._check_job = None
                return  # Stop the loop

            # 2. Inside main component -> Show overlay
            self._set_overlay_visible(visible=True)

            # 3. Check help icon specifically (for tooltip)
            if self.help_icon.winfo_viewable():
                icon_x = self.help_icon.winfo_rootx()
                icon_y = self.help_icon.winfo_rooty()
                icon_w = self.help_icon.winfo_width()
                icon_h = self.help_icon.winfo_height()

                is_over_icon = (icon_x <= x <= icon_x + icon_w) and (icon_y <= y <= icon_y + icon_h)

                if is_over_icon:
                    self._show_tooltip()
                else:
                    self._hide_tooltip()

            # Schedule next check
            self._check_job = self.after(100, self._check_hover)

        except Exception:
            # If widget destroyed or error, stop loop
            self._check_job = None

    def _set_overlay_visible(self, *, visible: bool) -> None:
        """Show or hide the 'Change Cover' overlay."""
        if visible:
            self.overlay_label.grid(row=0, column=0, sticky="nsew")
            self.overlay_label.tkraise()
            self.cover_label.configure(cursor="hand2")
            self.overlay_label.configure(cursor="hand2")
            self.configure(border_width=2, border_color=("#FFF8DC", "#4B4520"))
        else:
            self.overlay_label.grid_forget()
            self.cover_label.configure(cursor="")
            self.overlay_label.configure(cursor="")
            self.configure(border_width=0)

    def _on_click(self, _event: tk.Event) -> None:
        """Handle click event."""
        if self.on_change_click:
            self.on_change_click()

    def _show_tooltip(self) -> None:
        """Show explanation tooltip."""
        if self.tooltip_label:
            return  # Already shown

        self.tooltip_label = ctk.CTkToplevel(self)
        self.tooltip_label.wm_overrideredirect(boolean=True)
        self.tooltip_label.attributes("-topmost", True)
        self.tooltip_label.configure(fg_color=("gray85", "gray20"))

        # Position near help icon
        x = self.help_icon.winfo_rootx() + 25
        y = self.help_icon.winfo_rooty()

        self.tooltip_label.geometry(f"+{x}+{y}")

        label = ctk.CTkLabel(
            self.tooltip_label,
            text="Click to change cover art\nCan select multiple to change in bulk",
            font=("Segoe UI", 12),
            padx=8,
            pady=4,
        )
        label.pack()

    def _hide_tooltip(self) -> None:
        """Hide tooltip."""
        if self.tooltip_label:
            self.tooltip_label.destroy()
            self.tooltip_label = None

"""Components Base Class."""

from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from df_metadata_customizer.database_reformatter import DFApp


class AppComponent(ctk.CTkFrame):
    """Base class for UI components that are part of the DFApp.

    Should not contain functions that depend on other components directly.
    """

    def __init__(self, parent: ctk.CTkBaseClass, app: "DFApp", **kwargs: dict) -> None:
        """Set up the AppComponent."""
        super().__init__(parent, **kwargs)
        self.app = app
        self.initialize_state()
        self.setup_ui()
        self.register_events()

    def initialize_state(self) -> None:
        """Initialize component state before UI setup."""

    def setup_ui(self) -> None:
        """Build the UI for the component."""

    def register_events(self) -> None:
        """Register virtual events.

        Format should be "<<Class:EventName>>".
        """

    def update_theme(self) -> None:
        """Update component based on current theme.

        This function should be safe to call at any time.
        """

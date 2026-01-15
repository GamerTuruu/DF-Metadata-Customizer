"""Apply Component."""

from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent


class ApplyComponent(AppComponent):
    """Apply component with apply buttons."""

    @override
    def setup_ui(self) -> None:
        self.configure(fg_color="transparent")
        self.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(self, text="Apply to Selected", command=self.app.apply_to_selected).grid(
            row=0,
            column=0,
            padx=6,
            pady=6,
            sticky="ew",
        )
        ctk.CTkButton(self, text="Apply to All", command=self.app.apply_to_all).grid(
            row=0,
            column=1,
            padx=6,
            pady=6,
            sticky="ew",
        )

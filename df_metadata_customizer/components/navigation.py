"""Navigation Component."""

from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent


class NavigationComponent(AppComponent):
    """Navigation component with file navigation and apply buttons."""

    @override
    def setup_ui(self) -> None:
        self.configure(fg_color="transparent")
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(self, text="◀ Prev", command=self.app.prev_file).grid(
            row=0,
            column=0,
            padx=6,
            pady=6,
            sticky="ew",
        )
        ctk.CTkButton(self, text="Next ▶", command=self.app.next_file).grid(
            row=0,
            column=1,
            padx=6,
            pady=6,
            sticky="ew",
        )
        ctk.CTkButton(self, text="Apply to Selected", command=self.app.apply_to_selected).grid(
            row=0,
            column=2,
            padx=6,
            pady=6,
            sticky="ew",
        )
        ctk.CTkButton(self, text="Apply to All", command=self.app.apply_to_all).grid(
            row=0,
            column=3,
            padx=6,
            pady=6,
            sticky="ew",
        )

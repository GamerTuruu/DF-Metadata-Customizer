"""Base dialog classes."""

import customtkinter as ctk


class AppDialog(ctk.CTkToplevel):
    """A base dialog that centers itself on the parent."""

    def __init__(
        self,
        parent: ctk.CTk,
        title: str,
        geometry: str | None = None,
        resizable: tuple[bool, bool] = (False, False),
    ) -> None:
        """Initialize the dialog."""
        super().__init__(parent)
        self.title(title)

        if geometry:
            self.geometry(geometry)

        if resizable:
            self.resizable(width=resizable[0], height=resizable[1])

        # Center the dialog on the parent
        self.transient(parent)
        self.center_on_parent(parent)

    def center_on_parent(self, parent: ctk.CTk) -> None:
        """Center the window on the parent."""
        self.update_idletasks()
        parent.update_idletasks()

        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        width = self.winfo_width()
        height = self.winfo_height()

        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        self.geometry(f"+{x}+{y}")

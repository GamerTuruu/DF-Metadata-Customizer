"""Confirmation popups."""

import tkinter as tk

import customtkinter as ctk


class ConfirmDialog(ctk.CTkToplevel):
    """A confirmation dialog with an optional checkbox."""

    def __init__(
        self,
        parent: ctk.CTk,
        title: str,
        message: str,
        checkbox_text: str = "Remember my choice",
    ) -> None:
        """Initialize the dialog."""
        super().__init__(parent)
        self.title(title)
        self.geometry("400x200")
        self.resizable(width=False, height=False)

        self.result = False
        self.checkbox_checked = False

        # Center the dialog on the parent
        self.transient(parent)

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

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main frame
        self.frame = ctk.CTkFrame(self)
        self.frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_columnconfigure(1, weight=0)  # Button column
        self.frame.grid_rowconfigure(2, weight=1)  # Push buttons down

        # Message
        self.label = ctk.CTkLabel(self.frame, text=message, wraplength=350)
        self.label.grid(row=0, column=0, columnspan=2, pady=(10, 20), sticky="n")

        # Checkbox (Bottom Left)
        self.checkbox_var = tk.BooleanVar(value=False)
        self.checkbox = ctk.CTkCheckBox(self.frame, text=checkbox_text, variable=self.checkbox_var)
        self.checkbox.grid(row=2, column=0, sticky="sw", padx=(10, 0), pady=(0, 10))

        # Buttons Frame (Bottom Right)
        btn_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        btn_frame.grid(row=2, column=1, sticky="se", padx=(0, 10), pady=(0, 10))

        # Yes Button
        self.yes_button = ctk.CTkButton(btn_frame, text="Yes", command=self.on_yes, width=80)
        self.yes_button.pack(side="left", padx=(0, 10))

        # No Button
        self.no_button = ctk.CTkButton(
            btn_frame,
            text="No",
            command=self.on_no,
            width=80,
            fg_color="transparent",
            border_width=2,
        )
        self.no_button.pack(side="left")

        self.protocol("WM_DELETE_WINDOW", self.on_no)
        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def on_yes(self) -> None:
        """Handle Yes button click."""
        self.result = True
        self.checkbox_checked = self.checkbox_var.get()
        self.destroy()

    def on_no(self) -> None:
        """Handle No button click."""
        self.result = False
        self.checkbox_checked = self.checkbox_var.get()
        self.destroy()

"""Display progress during long operations."""

import customtkinter as ctk


class ProgressDialog(ctk.CTkToplevel):
    """Display the progress of a generic operation."""

    def __init__(self, parent: ctk.CTk, title: str = "Processing...") -> None:
        """Display the progress of a generic operation."""
        super().__init__(parent)
        self.title(title)
        self.geometry("400x120")
        self.resizable(width=False, height=False)

        # Center the dialog
        self.transient(parent)

        self.update_idletasks()
        parent.update_idletasks()

        # Center the window
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        width = self.winfo_width()
        height = self.winfo_height()

        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        self.geometry(f"+{x}+{y}")

        # Make it modal
        self.focus_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.label = ctk.CTkLabel(self, text="Starting...")
        self.label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self.progress = ctk.CTkProgressBar(self)
        self.progress.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.progress.set(0)

        self.percent_label = ctk.CTkLabel(self, text="0%")
        self.percent_label.grid(row=1, column=0, padx=20, pady=10, sticky="e")

        self.cancel_button = ctk.CTkButton(self, text="Cancel", command=self.cancel, height=38, width=150)
        self.cancel_button.grid(row=2, column=0, padx=20, pady=(10, 20))

        self.cancelled = False

        # Force the window to appear immediately
        self.update()
        self.wait_visibility()
        self.grab_set()

    def update_progress(self, current: int, total: int, text: str = "") -> bool:
        """Update progress bar. Returns False if cancelled."""
        if self.cancelled:
            return False

        progress = current / total if total > 0 else 0
        self.progress.set(progress)
        self.percent_label.configure(text=f"{int(progress * 100)}%")

        if text:
            self.label.configure(text=text)
        else:
            self.label.configure(text=f"Processing {current} of {total} files...")

        # Force update
        self.update_idletasks()
        self.update()
        return True

    def cancel(self) -> None:
        """Cancel the dialog."""
        self.cancelled = True
        self.label.configure(text="Cancelling...")
        self.cancel_button.configure(state="disabled")
        self.update()

"""Helper dialog windows."""

import tkinter as tk

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
        self.grab_set()

        # Center the window
        self.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        x = parent_x + (parent_width - 400) // 2
        y = parent_y + (parent_height - 120) // 2
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


class StatisticsDialog(ctk.CTkToplevel):
    """Popup window to show various song statistics."""

    def __init__(self, parent: ctk.CTk, stats: dict[str, int]) -> None:
        """Popup window to show various song statistics."""
        super().__init__(parent)
        self.title("Song Statistics")
        self.geometry("320x520")  # Slightly taller
        self.resizable(width=False, height=False)

        # Make it transient first
        self.transient(parent)

        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create main frame with padding
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        main_frame.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ctk.CTkLabel(main_frame, text="📊 Song Statistics", font=ctk.CTkFont(weight="bold", size=18))
        title_label.grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Statistics rows
        stats_data = [
            ("🎵 All Songs:", "all_songs"),
            ("🎯 Unique (Title+Artist):", "unique_ta"),
            ("🎯 Unique (Title+Artist+Cover):", "unique_tac"),
            ("", "spacer1"),  # Spacer
            ("🧠 Neuro Solos (unique):", "neuro_solos_unique"),
            ("🧠 Neuro Solos (total):", "neuro_solos_total"),
            ("", "spacer2"),  # Spacer
            ("😈 Evil Solos (unique):", "evil_solos_unique"),
            ("😈 Evil Solos (total):", "evil_solos_total"),
            ("", "spacer3"),  # Spacer
            ("👥 Duets (unique):", "duets_unique"),
            ("👥 Duets (total):", "duets_total"),
            ("", "spacer4"),  # Spacer
            ("📚 Other Songs (unique):", "other_unique"),
            ("📚 Other Songs (total):", "other_total"),
        ]

        self.stat_labels = {}
        row_idx = 1

        for label_text, stat_key in stats_data:
            if "spacer" in stat_key:
                # Empty row as spacer
                spacer = ctk.CTkLabel(main_frame, text="")
                spacer.grid(row=row_idx, column=0, pady=3)
                row_idx += 1
                continue

            # Create frame for each stat row
            stat_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            stat_frame.grid(row=row_idx, column=0, sticky="ew", pady=1)
            stat_frame.grid_columnconfigure(0, weight=1)
            stat_frame.grid_columnconfigure(1, weight=0)

            # Label
            label = ctk.CTkLabel(stat_frame, text=label_text, anchor="w", font=ctk.CTkFont(size=13))
            label.grid(row=0, column=0, sticky="w", padx=(0, 10))

            # Value (with highlighting)
            value = stats.get(stat_key, 0)
            value_label = ctk.CTkLabel(
                stat_frame,
                text=str(value),
                font=ctk.CTkFont(weight="bold", size=14),
                text_color="#4cc9f0",
            )  # Bright blue
            value_label.grid(row=0, column=1, sticky="e")

            self.stat_labels[stat_key] = value_label
            row_idx += 1

        # Add a separator before close button
        separator = ctk.CTkFrame(main_frame, height=2, fg_color="#444")
        separator.grid(row=row_idx, column=0, sticky="ew", pady=15)
        row_idx += 1

        # Close button
        close_btn = ctk.CTkButton(
            main_frame,
            text="Close",
            command=self.destroy,
            width=120,
            height=35,
            fg_color="#3b8ed0",
            hover_color="#367abf",
        )
        close_btn.grid(row=row_idx, column=0, pady=(5, 0))

        # Update window to ensure it's visible
        self.update()
        self.update_idletasks()

        # Now make it modal - FIXED: Wait until window is viewable
        self.focus_set()

        # Try grab with error handling
        try:
            self.grab_set()
        except tk.TclError as e:
            print(f"Warning: Could not grab focus: {e}")
            # Window might already have focus

        # Force update of stats
        self.update_stats(stats)

    def update_stats(self, stats: dict[str, int]) -> None:
        """Update all statistics displays."""
        for key, label in self.stat_labels.items():
            if key in stats:
                value = stats[key]
                label.configure(text=str(value))


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

        # Center the dialog on the SCREEN
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = (screen_width - 400) // 2
        y = (screen_height - 200) // 2
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

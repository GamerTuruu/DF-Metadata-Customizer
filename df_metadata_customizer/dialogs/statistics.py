"""Display various statistics and information."""

import logging
import tkinter as tk

import customtkinter as ctk

logger = logging.getLogger(__name__)


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

        self.stat_labels: dict[str, ctk.CTkLabel] = {}
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

        # Force update of stats
        self.update_stats(stats)

    def update_stats(self, stats: dict[str, int]) -> None:
        """Update all statistics displays."""
        for key, label in self.stat_labels.items():
            if key in stats:
                value = stats[key]
                label.configure(text=str(value))

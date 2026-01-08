"""Output Preview Component."""

import logging
from typing import override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import AppComponent
from df_metadata_customizer.rule_manager import RuleManager

logger = logging.getLogger(__name__)


class OutputPreviewComponent(AppComponent):
    """Output Preview Component to see the output of metadata rules in real-time."""

    @override
    def setup_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="New Title:").grid(row=0, column=0, sticky="e", padx=(6, 6), pady=(6, 2))
        self.lbl_out_title = ctk.CTkLabel(self, text="", anchor="w", corner_radius=6)
        self.lbl_out_title.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=(6, 2))

        ctk.CTkLabel(self, text="New Artist:").grid(row=1, column=0, sticky="e", padx=(6, 6), pady=(2, 2))
        self.lbl_out_artist = ctk.CTkLabel(self, text="", anchor="w", corner_radius=6)
        self.lbl_out_artist.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=(2, 2))

        ctk.CTkLabel(self, text="New Album:").grid(row=2, column=0, sticky="e", padx=(6, 6), pady=(2, 6))
        self.lbl_out_album = ctk.CTkLabel(self, text="", anchor="w", corner_radius=6)
        self.lbl_out_album.grid(row=2, column=1, sticky="ew", padx=(0, 6), pady=(2, 6))

        dt_frame = ctk.CTkFrame(self, fg_color="transparent")
        dt_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        dt_frame.grid_columnconfigure((1, 3, 5, 7), weight=1)

        ctk.CTkLabel(dt_frame, text="Disc:").grid(row=0, column=0, sticky="e", padx=(0, 4))
        self.lbl_out_disc = ctk.CTkLabel(dt_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_disc.grid(row=0, column=1, sticky="w", padx=(0, 12))

        ctk.CTkLabel(dt_frame, text="Track:").grid(row=0, column=2, sticky="e", padx=(0, 4))
        self.lbl_out_track = ctk.CTkLabel(dt_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_track.grid(row=0, column=3, sticky="w", padx=(0, 12))

        ctk.CTkLabel(dt_frame, text="All Versions:").grid(row=0, column=4, sticky="e", padx=(0, 4))
        self.lbl_out_versions = ctk.CTkLabel(dt_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_versions.grid(row=0, column=5, sticky="w", padx=(0, 12))

        ctk.CTkLabel(dt_frame, text="Date:").grid(row=0, column=6, sticky="e", padx=(0, 4))
        self.lbl_out_date = ctk.CTkLabel(dt_frame, text="", anchor="w", corner_radius=6)
        self.lbl_out_date.grid(row=0, column=7, sticky="w", padx=(0, 12))

        self.update_theme()

    @override
    def update_theme(self) -> None:
        try:
            if self.app.is_dark_mode:
                # Dark theme
                bg_color = "#3b3b3b"
                text_color = "white"
            else:
                # Light theme
                bg_color = "#e0e0e0"
                text_color = "black"

            # Update all output preview labels (including Date)
            for label in [
                self.lbl_out_title,
                self.lbl_out_artist,
                self.lbl_out_album,
                self.lbl_out_disc,
                self.lbl_out_track,
                self.lbl_out_versions,
                self.lbl_out_date,
            ]:
                label.configure(fg_color=bg_color, text_color=text_color)
        except Exception:
            logger.exception("Error updating output preview style")

    def update_preview(self) -> None:
        """Update the output preview based on current rules and selected JSON."""
        if not self.app.current_metadata:
            self.lbl_out_title.configure(text="")
            self.lbl_out_artist.configure(text="")
            self.lbl_out_album.configure(text="")
            self.lbl_out_disc.configure(text="")
            self.lbl_out_track.configure(text="")
            self.lbl_out_versions.configure(text="")
            return

        metadata = self.app.current_metadata

        # Collect new values based on rules
        new_title = RuleManager.apply_rules_list(
            self.app.collect_rules_for_tab("title"),
            metadata,
        )
        new_artist = RuleManager.apply_rules_list(
            self.app.collect_rules_for_tab("artist"),
            metadata,
        )
        new_album = RuleManager.apply_rules_list(
            self.app.collect_rules_for_tab("album"),
            metadata,
        )

        # Display new values
        try:
            self.lbl_out_title.configure(text=new_title)
            self.lbl_out_artist.configure(text=new_artist)
            self.lbl_out_album.configure(text=new_album)
            self.lbl_out_disc.configure(text=metadata.disc)
            self.lbl_out_track.configure(text=metadata.track)
            self.lbl_out_date.configure(text=metadata.date)

        except Exception:
            logger.exception("Error setting preview text")
            self.lbl_out_title.configure(text="")
            self.lbl_out_artist.configure(text="")
            self.lbl_out_album.configure(text="")

        # Show all versions for current song (considering title + artist + coverartist)
        song_key = f"{metadata.title}|{metadata.artist}|{metadata.coverartist}"

        versions = self.app.file_manager.get_song_versions(song_key)
        if versions:
            formatted_versions = []
            for v in versions:
                if isinstance(v, float) and v.is_integer():
                    formatted_versions.append(str(int(v)))
                else:
                    formatted_versions.append(str(v))
            versions_text = ", ".join(formatted_versions)
            self.lbl_out_versions.configure(text=versions_text)
        else:
            self.lbl_out_versions.configure(text="")

"""Metadata Editor Component for Song Edit Section."""

from typing import Final, override

import customtkinter as ctk

from df_metadata_customizer.components.app_component import ScrollableAppComponent
from df_metadata_customizer.song_metadata import MetadataFields, SongMetadata


class MetadataEditorComponent(ScrollableAppComponent):
    """Component for editing song metadata (properties + JSON)."""

    KEY_MAP: Final = {
        MetadataFields.UI_TITLE: MetadataFields.TITLE,
        MetadataFields.UI_ARTIST: MetadataFields.ARTIST,
        MetadataFields.UI_COVER_ARTIST: MetadataFields.COVER_ARTIST,
        MetadataFields.UI_VERSION: MetadataFields.VERSION,
        MetadataFields.UI_DISC: MetadataFields.DISC,
        MetadataFields.UI_TRACK: MetadataFields.TRACK,
        MetadataFields.UI_DATE: MetadataFields.DATE,
        MetadataFields.UI_COMMENT: MetadataFields.COMMENT,
        MetadataFields.UI_SPECIAL: MetadataFields.SPECIAL,
    }

    ID3_FIELDS: Final = [
        (MetadataFields.UI_ID3_TITLE, "Title"),
        (MetadataFields.UI_ID3_ARTIST, "Artist"),
        (MetadataFields.UI_ID3_ALBUM, "Album"),
        (MetadataFields.UI_ID3_TRACK, "Track"),
        (MetadataFields.UI_ID3_DISC, "Disc"),
        (MetadataFields.UI_ID3_DATE, "Date"),
    ]

    JSON_FIELDS: Final = [
        (MetadataFields.UI_TITLE, "Title"),
        (MetadataFields.UI_ARTIST, "Artist"),
        (MetadataFields.UI_DATE, "Date"),
        (MetadataFields.UI_COVER_ARTIST, "Cover Artist"),
        (MetadataFields.UI_VERSION, "Version"),
        (MetadataFields.UI_DISC, "Discnumber"),
        (MetadataFields.UI_TRACK, "Track"),
        (MetadataFields.UI_COMMENT, "Comment"),
        (MetadataFields.UI_SPECIAL, "Special"),
    ]

    @override
    def initialize_state(self) -> None:
        """Initialize component state."""
        self.entries: dict[str, ctk.CTkEntry] = {}
        self.original_values: dict[str, str] = {}

    @override
    def setup_ui(self) -> None:
        """Build the UI for the component."""
        self.grid_columnconfigure(1, weight=1)
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create entry widgets for fields."""
        current_row = 0

        # Section: ID3 Properties
        lbl_id3 = ctk.CTkLabel(self, text="Properties (ID3)", font=("Segoe UI", 14, "bold"))
        lbl_id3.grid(row=current_row, column=0, columnspan=2, sticky="w", pady=(5, 5))
        current_row += 1

        for key, label in self.ID3_FIELDS:
            self._add_field(key, label, current_row)
            current_row += 1

        # Section: Internal Metadata (JSON)
        lbl_json = ctk.CTkLabel(self, text="Internal Metadata (JSON)", font=("Segoe UI", 14, "bold"))
        lbl_json.grid(row=current_row, column=0, columnspan=2, sticky="w", pady=(15, 5))
        current_row += 1

        for key, label in self.JSON_FIELDS:
            self._add_field(key, label, current_row)
            current_row += 1

    def _add_field(self, key: str, label_text: str, row: int) -> None:
        """Add a labeled entry field."""
        lbl = ctk.CTkLabel(self, text=label_text, anchor="w")
        lbl.grid(row=row, column=0, sticky="w", padx=5, pady=2)

        entry = ctk.CTkEntry(self)
        entry.grid(row=row, column=1, sticky="ew", padx=5, pady=2)

        # Bind change event to checking against original
        entry.bind("<KeyRelease>", lambda e, k=key: self._on_text_change(k))

        self.entries[key] = entry

    def load_metadata(self, metadata: SongMetadata | None) -> None:
        """Load metadata into fields."""
        self.original_values = {}

        if metadata:
            for key, _ in self.ID3_FIELDS + self.JSON_FIELDS:
                val = metadata.get(key)
                self.original_values[key] = val

                entry = self.entries[key]
                entry.delete(0, "end")
                entry.insert(0, val)
                self._update_entry_state(key)
        else:
            # Clear fields
            for entry in self.entries.values():
                entry.delete(0, "end")
                entry.configure(fg_color=["#F9F9FA", "#343638"])  # Default colors

    def get_current_data(self) -> dict[str, str]:
        """Return dictionary of current values."""
        return {key: entry.get().strip() for key, entry in self.entries.items()}

    def import_metadata(self, metadata: SongMetadata) -> None:
        """Import metadata values into fields without resetting original values."""
        if not metadata:
            return

        for key, _ in self.ID3_FIELDS + self.JSON_FIELDS:
            # Use the same keys as load_metadata
            val = metadata.get(key)

            entry = self.entries[key]
            entry.delete(0, "end")
            entry.insert(0, val)
            self._update_entry_state(key)

    def _on_text_change(self, key: str) -> None:
        """Check if value changed and update UI."""
        self._update_entry_state(key)

    def _update_entry_state(self, key: str) -> None:
        """Update entry visual state based on modification."""
        entry = self.entries[key]
        current_val = entry.get()
        original_val = self.original_values.get(key, "")

        # Visual highlight if changed
        if current_val != original_val:
            # Yellowish highlight for unsaved changes
            entry.configure(fg_color=["#FFF8DC", "#4B4520"])  # light/dark mode yellow
        else:
            # Reset to default
            entry.configure(fg_color=["#F9F9FA", "#343638"])

    def has_unsaved_changes(self) -> bool:
        """Check if any field has been modified."""
        return any(entry.get() != self.original_values.get(key, "") for key, entry in self.entries.items())

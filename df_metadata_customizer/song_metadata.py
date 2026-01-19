"""Song metadata wrapper providing safe access and defaults."""

from enum import StrEnum


class MetadataFields(StrEnum):
    """Centralized field names for metadata and UI."""

    # JSON keys
    TITLE = "Title"
    ARTIST = "Artist"
    COVER_ARTIST = "CoverArtist"
    VERSION = "Version"
    DISC = "Discnumber"
    TRACK = "Track"
    DATE = "Date"
    COMMENT = "Comment"
    SPECIAL = "Special"
    FILE = "file"

    # UI keys
    UI_TITLE = "title"
    UI_ARTIST = "artist"
    UI_COVER_ARTIST = "coverartist"
    UI_VERSION = "version"
    UI_DISC = "disc"
    UI_TRACK = "track"
    UI_DATE = "date"
    UI_COMMENT = "comment"
    UI_SPECIAL = "special"
    UI_FILE = "file"

    # ID3 specific UI keys
    UI_ID3_TITLE = "id3_title"
    UI_ID3_ARTIST = "id3_artist"
    UI_ID3_ALBUM = "id3_album"
    UI_ID3_TRACK = "id3_track"
    UI_ID3_DISC = "id3_disc"
    UI_ID3_DATE = "id3_date"

    @classmethod
    def get_json_keys(cls) -> list[str]:
        """Return list of all JSON keys."""
        return [m.value for m in cls if not m.name.startswith("UI_")]

    @classmethod
    def get_ui_keys(cls) -> list[str]:
        """Return list of all UI keys."""
        return [m.value for m in cls if m.name.startswith("UI_")]


class SongMetadata:
    """A wrapper around song metadata that provides safe access and defaults."""

    def __init__(
        self,
        data: dict,
        path: str,
        *,
        is_latest: bool = False,
        id3_data: dict[str, str] | None = None,
    ) -> None:
        """Initialize SongMetadata."""
        self._data = data
        self._id3_data = id3_data or {}
        self.path = path
        self._is_latest = is_latest

    def get(self, field: str) -> str:
        """Get value from metadata using properties or raw data."""
        f = field.lower()

        # ID3 overrides
        if f == MetadataFields.UI_ID3_TITLE:
            return self._id3_data.get("Title", "")
        if f == MetadataFields.UI_ID3_ARTIST:
            return self._id3_data.get("Artist", "")
        if f == MetadataFields.UI_ID3_ALBUM:
            return self._id3_data.get("Album", "")
        if f == MetadataFields.UI_ID3_TRACK:
            return self._id3_data.get("Track", "")
        if f == MetadataFields.UI_ID3_DISC:
            # Check both key variants just in case
            return self._id3_data.get("Discnumber") or self._id3_data.get("Disc", "")
        if f == MetadataFields.UI_ID3_DATE:
            return self._id3_data.get("Date", "")

        # JSON / Standard access
        if f == MetadataFields.UI_TITLE:
            return self.title
        if f == MetadataFields.UI_ARTIST:
            return self.artist
        if f == MetadataFields.UI_COVER_ARTIST:
            return self.coverartist
        if f == MetadataFields.UI_VERSION:
            return self.version_str
        if f in (MetadataFields.UI_DISC, MetadataFields.DISC.lower()):
            return self.disc
        if f == MetadataFields.UI_TRACK:
            return self.track
        if f == MetadataFields.UI_DATE:
            return self.date
        if f == MetadataFields.UI_COMMENT:
            return self.comment
        if f == MetadataFields.UI_SPECIAL:
            return self.special

        val = self._data.get(field)
        return str(val) if val is not None else ""

    @property
    def raw_data(self) -> dict:
        """Return the raw metadata dictionary."""
        return self._data

    @property
    def title(self) -> str:
        """Return the song title."""
        return self._data.get(MetadataFields.TITLE) or ""

    @property
    def artist(self) -> str:
        """Return the song artist."""
        return self._data.get(MetadataFields.ARTIST) or ""

    @property
    def coverartist(self) -> str:
        """Return the cover artist."""
        return self._data.get(MetadataFields.COVER_ARTIST) or ""

    @property
    def version_str(self) -> str:
        """Return the version as a string."""
        v = self._data.get(MetadataFields.VERSION, 0)
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)

    @property
    def disc(self) -> str:
        """Return the disc number."""
        return self._data.get(MetadataFields.DISC) or ""

    @property
    def track(self) -> str:
        """Return the track number."""
        return self._data.get(MetadataFields.TRACK) or ""

    @property
    def date(self) -> str:
        """Return the release date."""
        return self._data.get(MetadataFields.DATE) or ""

    @property
    def comment(self) -> str:
        """Return the song comment."""
        return self._data.get(MetadataFields.COMMENT) or ""

    @property
    def special(self) -> str:
        """Return the special field value."""
        return self._data.get(MetadataFields.SPECIAL) or ""

    @property
    def is_latest(self) -> bool:
        """Return whether this is the latest version."""
        return self._is_latest

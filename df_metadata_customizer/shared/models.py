"""Shared data models used across API, CLI, and UI."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any
from enum import Enum


class RuleOperator(str, Enum):
    """Rule operators for conditional logic."""

    IS = "is"
    CONTAINS = "contains"
    STARTS_WITH = "starts with"
    ENDS_WITH = "ends with"
    IS_EMPTY = "is empty"
    IS_NOT_EMPTY = "is not empty"
    IS_LATEST_VERSION = "is latest version"
    IS_NOT_LATEST_VERSION = "is not latest version"


@dataclass
class SongMetadataModel:
    """Represents MP3 metadata for a song."""

    file_path: Path
    title: Optional[str] = None
    artist: Optional[str] = None
    cover_artist: Optional[str] = None
    date: Optional[str] = None
    version: Optional[str] = None
    discnumber: Optional[int] = None
    track: Optional[int] = None
    comment: Optional[str] = None
    special: Optional[str] = None


@dataclass
class PresetRule:
    """Represents a single rule in a preset."""

    field: str
    operator: RuleOperator
    condition: str
    action_field: str
    action_value: str


@dataclass
class PresetModel:
    """Represents a preset configuration."""

    name: str
    description: Optional[str] = None
    rules: list[PresetRule] = None
    metadata: dict[str, Any] = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.rules is None:
            self.rules = []
        if self.metadata is None:
            self.metadata = {}

"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, Field
from typing import Optional, Any


class SongMetadataResponse(BaseModel):
    """Response model for song metadata."""

    file_path: str
    title: Optional[str] = None
    artist: Optional[str] = None
    cover_artist: Optional[str] = None
    date: Optional[str] = None
    version: Optional[str] = None
    disc: Optional[str] = None
    track: Optional[str] = None
    comment: Optional[str] = None
    special: Optional[str] = None
    is_latest: bool = False


class PresetConditionModel(BaseModel):
    """Model for preset condition."""

    field: str
    operator: str = Field(
        ...,
        description="One of: is, contains, starts with, ends with, is empty, is not empty, is latest version, is not latest version",
    )
    value: str = ""


class PresetActionModel(BaseModel):
    """Model for preset action."""

    field: str
    value: str


class PresetRuleModel(BaseModel):
    """Model for preset rule."""

    name: str
    description: Optional[str] = ""
    enabled: bool = True
    logic: str = "AND"
    condition: PresetConditionModel
    action: PresetActionModel


class PresetModel(BaseModel):
    """Model for preset."""

    name: str
    description: Optional[str] = ""
    rules: list[PresetRuleModel] = []
    metadata: Optional[dict[str, Any]] = {}
    version: str = "1.0"


class SearchQueryModel(BaseModel):
    """Model for search query."""

    query: str = ""
    limit: int = 100


class BatchApplyRequest(BaseModel):
    """Request model for batch preset application."""

    preset_name: str
    file_paths: list[str]


class StatusResponse(BaseModel):
    """General status response."""

    success: bool
    message: str
    data: Optional[Any] = None


class FileListResponse(BaseModel):
    """Response model for file listing."""

    total: int
    files: list[SongMetadataResponse]


class PresetListResponse(BaseModel):
    """Response model for preset listing."""

    presets: list[str]

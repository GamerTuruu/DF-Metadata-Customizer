"""API routes for file and metadata operations."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from df_metadata_customizer.core import FileManager, RuleManager, SettingsManager, PresetService
from df_metadata_customizer.core.metadata import MetadataFields
from df_metadata_customizer.core import song_utils
from df_metadata_customizer.api.models import (
    SongMetadataResponse,
    StatusResponse,
    FileListResponse,
    SearchQueryModel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])

# Global state
_file_manager: FileManager | None = None
_rule_manager: RuleManager | None = None
_settings_manager: SettingsManager | None = None
_preset_service: PresetService | None = None


def init_managers() -> None:
    """Initialize managers."""
    global _file_manager, _rule_manager, _settings_manager, _preset_service

    _file_manager = FileManager()
    _rule_manager = RuleManager()
    _settings_manager = SettingsManager()
    SettingsManager.initialize()
    _preset_service = PresetService(SettingsManager.get_presets_folder())


@router.post("/load-folder", response_model=StatusResponse)
async def load_folder(folder_path: str) -> StatusResponse:
    """Load all MP3 files from a folder."""
    if not _file_manager:
        init_managers()

    try:
        path = Path(folder_path)
        if not path.is_dir():
            raise ValueError("Invalid folder path")

        _file_manager.load_folder(folder_path)
        SettingsManager.last_folder_opened = folder_path
        SettingsManager.save_settings()

        logger.info(f"Loaded folder: {folder_path}")
        return StatusResponse(
            success=True,
            message=f"Loaded {_file_manager.df.height} files from {folder_path}",
            data={"count": _file_manager.df.height},
        )
    except Exception as e:
        logger.exception(f"Error loading folder: {folder_path}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list", response_model=FileListResponse)
async def list_files(limit: int = 100, offset: int = 0) -> FileListResponse:
    """List loaded files."""
    if not _file_manager:
        init_managers()

    try:
        _file_manager.commit()
        all_files = _file_manager.get_all_files()

        paginated_files = all_files[offset : offset + limit]

        files = []
        for file_data in paginated_files:
            song = _file_manager.get_file_by_path(file_data["path"])
            if song:
                files.append(
                    SongMetadataResponse(
                        file_path=song.path,
                        title=song.title,
                        artist=song.artist,
                        cover_artist=song.coverartist,
                        date=song.date,
                        version=song.version_str,
                        disc=song.disc,
                        track=song.track,
                        comment=song.comment,
                        special=song.special,
                        is_latest=song.is_latest,
                    )
                )

        return FileListResponse(total=len(all_files), files=files)
    except Exception as e:
        logger.exception("Error listing files")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get/{file_path:path}", response_model=SongMetadataResponse)
async def get_file_metadata(file_path: str) -> SongMetadataResponse:
    """Get metadata for a specific file."""
    if not _file_manager:
        init_managers()

    try:
        song = _file_manager.get_file_by_path(file_path)
        if not song:
            raise ValueError("File not found")

        return SongMetadataResponse(
            file_path=song.path,
            title=song.title,
            artist=song.artist,
            cover_artist=song.coverartist,
            date=song.date,
            version=song.version_str,
            disc=song.disc,
            track=song.track,
            comment=song.comment,
            special=song.special,
            is_latest=song.is_latest,
        )
    except Exception as e:
        logger.exception(f"Error getting file metadata: {file_path}")
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/update/{file_path:path}", response_model=StatusResponse)
async def update_file_metadata(file_path: str, metadata: dict) -> StatusResponse:
    """Update metadata for a file."""
    if not _file_manager:
        init_managers()

    try:
        # Update in file manager
        _file_manager.update_file_data(file_path, metadata)
        _file_manager.commit()

        # Write to actual MP3 file
        success = song_utils.write_json_to_song(file_path, metadata)

        if not success:
            raise ValueError("Failed to write metadata to file")

        logger.info(f"Updated metadata for: {file_path}")
        return StatusResponse(success=True, message="Metadata updated successfully")
    except Exception as e:
        logger.exception(f"Error updating file metadata: {file_path}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/search", response_model=FileListResponse)
async def search_files(search: SearchQueryModel) -> FileListResponse:
    """Search loaded files."""
    if not _file_manager:
        init_managers()

    try:
        _file_manager.commit()

        # Parse search query
        filters, free_terms = _rule_manager.parse_search_query(search.query)

        # Apply filters to dataframe
        filtered_df = _rule_manager.apply_search_filter(_file_manager.df, filters, free_terms)

        # Limit results
        filtered_df = filtered_df.limit(search.limit)

        files = []
        for row in filtered_df.to_dicts():
            song = _file_manager.get_file_by_path(row["path"])
            if song:
                files.append(
                    SongMetadataResponse(
                        file_path=song.path,
                        title=song.title,
                        artist=song.artist,
                        cover_artist=song.coverartist,
                        date=song.date,
                        version=song.version_str,
                        disc=song.disc,
                        track=song.track,
                        comment=song.comment,
                        special=song.special,
                        is_latest=song.is_latest,
                    )
                )

        return FileListResponse(total=len(files), files=files)
    except Exception as e:
        logger.exception(f"Error searching files: {search.query}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/clear", response_model=StatusResponse)
async def clear_files() -> StatusResponse:
    """Clear all loaded files."""
    if not _file_manager:
        init_managers()

    try:
        _file_manager.clear()
        return StatusResponse(success=True, message="Files cleared successfully")
    except Exception as e:
        logger.exception("Error clearing files")
        raise HTTPException(status_code=500, detail=str(e))

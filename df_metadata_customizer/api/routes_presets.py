"""API routes for preset operations."""

import logging

from fastapi import APIRouter, HTTPException
from df_metadata_customizer.core import SettingsManager, PresetService
from df_metadata_customizer.core.preset_service import Preset, PresetCondition, PresetAction, PresetRule
from df_metadata_customizer.api.models import (
    PresetModel,
    PresetListResponse,
    StatusResponse,
    BatchApplyRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/presets", tags=["presets"])

# Global state
_preset_service: PresetService | None = None


def init_preset_service() -> None:
    """Initialize preset service."""
    global _preset_service
    SettingsManager.initialize()
    _preset_service = PresetService(SettingsManager.get_presets_folder())


@router.get("/list", response_model=PresetListResponse)
async def list_presets() -> PresetListResponse:
    """List all available presets."""
    if not _preset_service:
        init_preset_service()

    try:
        presets = _preset_service.list_presets()
        return PresetListResponse(presets=presets)
    except Exception as e:
        logger.exception("Error listing presets")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get/{preset_name}", response_model=PresetModel)
async def get_preset(preset_name: str) -> PresetModel:
    """Get a specific preset."""
    if not _preset_service:
        init_preset_service()

    try:
        preset = _preset_service.load_preset(preset_name)
        if not preset:
            raise ValueError("Preset not found")

        return PresetModel(
            name=preset.name,
            description=preset.description,
            version=preset.version,
            rules=[
                {
                    "name": rule.name,
                    "description": rule.description,
                    "enabled": rule.enabled,
                    "logic": rule.logic,
                    "condition": {
                        "field": rule.condition.field,
                        "operator": rule.condition.operator,
                        "value": rule.condition.value,
                    },
                    "action": {
                        "field": rule.action.field,
                        "value": rule.action.value,
                    },
                }
                for rule in preset.rules
            ],
            metadata=preset.metadata,
        )
    except Exception as e:
        logger.exception(f"Error getting preset: {preset_name}")
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/create", response_model=StatusResponse)
async def create_preset(preset_data: PresetModel) -> StatusResponse:
    """Create or update a preset."""
    if not _preset_service:
        init_preset_service()

    try:
        # Convert API model to core model
        rules = []
        for rule_data in preset_data.rules:
            rule = PresetRule(
                name=rule_data.name,
                description=rule_data.description,
                enabled=rule_data.enabled,
                logic=rule_data.logic,
                condition=PresetCondition(
                    field=rule_data.condition.field,
                    operator=rule_data.condition.operator,
                    value=rule_data.condition.value,
                ),
                action=PresetAction(
                    field=rule_data.action.field,
                    value=rule_data.action.value,
                ),
            )
            rules.append(rule)

        preset = Preset(
            name=preset_data.name,
            description=preset_data.description,
            rules=rules,
            metadata=preset_data.metadata or {},
            version=preset_data.version,
        )

        success = _preset_service.save_preset(preset)
        if not success:
            raise ValueError("Failed to save preset")

        logger.info(f"Preset created: {preset_data.name}")
        return StatusResponse(success=True, message=f"Preset '{preset_data.name}' created successfully")
    except Exception as e:
        logger.exception(f"Error creating preset: {preset_data.name}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/delete/{preset_name}", response_model=StatusResponse)
async def delete_preset(preset_name: str) -> StatusResponse:
    """Delete a preset."""
    if not _preset_service:
        init_preset_service()

    try:
        success = _preset_service.delete_preset(preset_name)
        if not success:
            raise ValueError("Preset not found")

        logger.info(f"Preset deleted: {preset_name}")
        return StatusResponse(success=True, message=f"Preset '{preset_name}' deleted successfully")
    except Exception as e:
        logger.exception(f"Error deleting preset: {preset_name}")
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/apply", response_model=StatusResponse)
async def apply_preset(request: BatchApplyRequest) -> StatusResponse:
    """Apply a preset to metadata."""
    if not _preset_service:
        init_preset_service()

    try:
        preset = _preset_service.load_preset(request.preset_name)
        if not preset:
            raise ValueError(f"Preset '{request.preset_name}' not found")

        # Apply to each file
        applied_count = 0
        for file_path in request.file_paths:
            try:
                # Get current metadata
                import json
                from df_metadata_customizer.core import song_utils

                json_data = song_utils.extract_json_from_song(file_path) or {}

                # Apply preset rules
                result = _preset_service.apply_preset(preset, json_data)

                # Write back to file
                success = song_utils.write_json_to_song(file_path, result)
                if success:
                    applied_count += 1
            except Exception as e:
                logger.warning(f"Failed to apply preset to {file_path}: {e}")
                continue

        logger.info(f"Preset applied to {applied_count}/{len(request.file_paths)} files")
        return StatusResponse(
            success=True,
            message=f"Preset applied to {applied_count}/{len(request.file_paths)} files",
            data={"applied": applied_count, "total": len(request.file_paths)},
        )
    except Exception as e:
        logger.exception(f"Error applying preset: {request.preset_name}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/validate", response_model=StatusResponse)
async def validate_preset(preset_data: PresetModel) -> StatusResponse:
    """Validate a preset configuration."""
    try:
        if not preset_data.name:
            raise ValueError("Preset name is required")

        if not preset_data.rules:
            raise ValueError("At least one rule is required")

        for rule in preset_data.rules:
            if not rule.name:
                raise ValueError("Rule name is required")
            if not rule.condition.field:
                raise ValueError("Condition field is required")
            if not rule.action.field:
                raise ValueError("Action field is required")

        logger.info(f"Preset validation passed: {preset_data.name}")
        return StatusResponse(success=True, message="Preset is valid")
    except Exception as e:
        logger.exception(f"Preset validation failed")
        raise HTTPException(status_code=400, detail=str(e))

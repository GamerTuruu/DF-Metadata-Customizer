"""Core business logic module - UI-independent metadata processing."""

from df_metadata_customizer.core.metadata import MetadataFields, SongMetadata
from df_metadata_customizer.core.file_manager import FileManager
from df_metadata_customizer.core.rule_manager import RuleManager
from df_metadata_customizer.core.settings_manager import SettingsManager
from df_metadata_customizer.core.preset_service import Preset, PresetRule, PresetService, PresetCondition, PresetAction
from df_metadata_customizer.core import song_utils

__all__ = [
    "MetadataFields",
    "SongMetadata",
    "FileManager",
    "RuleManager",
    "SettingsManager",
    "Preset",
    "PresetRule",
    "PresetService",
    "PresetCondition",
    "PresetAction",
    "song_utils",
]

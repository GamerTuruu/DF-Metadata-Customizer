"""Manages application settings and presets persistence."""

import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SettingsManager:
    """Manages application settings and presets persistence."""

    APP_NAME = "df_metadata_customizer"

    @classmethod
    def initialize(cls) -> None:
        """Initialize SettingsManager."""
        cls._extract_bundled()

    @classmethod
    def _extract_bundled(cls) -> None:
        """Ensure bundled presets are copied to the external presets folder."""
        if not getattr(sys, "frozen", False):
            return

        # Internal bundled path
        bundle_dir = Path(getattr(sys, "_MEIPASS", ""))
        bundled_presets = bundle_dir / "presets"

        # External user-facing path
        target_presets = cls.get_base_dir() / "presets"

        if bundled_presets.exists() and not target_presets.exists():
            shutil.copytree(bundled_presets, target_presets)

    @classmethod
    def get_base_dir(cls) -> Path:
        """Get the base directory for the application."""
        if getattr(sys, "frozen", False):
            # Running as bundled executable
            return Path(sys.executable).parent
        # Running as script - assuming this file is in df_metadata_customizer/
        return Path(__file__).resolve().parent.parent

    @classmethod
    def get_settings_path(cls) -> Path:
        """Get the path to the settings file."""
        return cls.get_base_dir() / f"{cls.APP_NAME}_settings.json"

    @classmethod
    def get_presets_folder(cls) -> Path:
        """Get the presets folder path, creating it if necessary."""
        folder = cls.get_base_dir() / "presets"
        folder.mkdir(exist_ok=True)
        return folder

    @classmethod
    def save_settings(cls, data: dict[str, Any]) -> None:
        """Save settings dictionary to JSON file."""
        try:
            with cls.get_settings_path().open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            logger.exception("Error saving settings")

    @classmethod
    def load_settings(cls) -> dict[str, Any]:
        """Load settings from JSON file."""
        if not cls.get_settings_path().exists():
            return {}
        try:
            with cls.get_settings_path().open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.exception("Error loading settings")
            return {}

    @classmethod
    def save_preset(cls, name: str, preset_data: dict[str, list[dict[str, Any]]]) -> None:
        """Save a preset to a JSON file."""
        preset_file = cls.get_presets_folder() / f"{name}.json"
        with preset_file.open("w", encoding="utf-8") as f:
            json.dump(preset_data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load_preset(cls, name: str) -> dict[str, list[dict[str, Any]]]:
        """Load a preset from a JSON file."""
        preset_file = cls.get_presets_folder() / f"{name}.json"
        if not preset_file.exists():
            msg = f"Preset file '{name}.json' not found"
            raise FileNotFoundError(msg)

        with preset_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def delete_preset(cls, name: str) -> None:
        """Delete a preset file."""
        preset_file = cls.get_presets_folder() / f"{name}.json"
        if preset_file.exists():
            preset_file.unlink()
        else:
            msg = f"Preset '{name}' not found"
            raise FileNotFoundError(msg)

    @classmethod
    def list_presets(cls) -> list[str]:
        """List all available presets."""
        try:
            vals = []
            for preset_file in cls.get_presets_folder().glob("*.json"):
                try:
                    vals.append(preset_file.stem)
                except Exception:
                    continue
            vals.sort()
        except Exception:
            return []
        return vals

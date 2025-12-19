"""Manages application settings and presets persistence."""

import json
import sys
from pathlib import Path
from typing import Any


class SettingsManager:
    """Manages application settings and presets persistence."""

    def __init__(self, app_name: str = "df_metadata_customizer") -> None:
        """Initialize SettingsManager with application name."""
        self.app_name = app_name

    @property
    def base_dir(self) -> Path:
        """Get the base directory for the application."""
        if getattr(sys, "frozen", False):
            # Running as bundled executable
            return Path(sys.executable).parent
        # Running as script - assuming this file is in df_metadata_customizer/
        return Path(__file__).resolve().parent.parent

    @property
    def settings_path(self) -> Path:
        """Get the path to the settings file."""
        return self.base_dir / f"{self.app_name}_settings.json"

    @property
    def presets_folder(self) -> Path:
        """Get the presets folder path, creating it if necessary."""
        folder = self.base_dir / "presets"
        folder.mkdir(exist_ok=True)
        return folder

    def save_settings(self, data: dict[str, Any]) -> None:
        """Save settings dictionary to JSON file."""
        try:
            with self.settings_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self) -> dict[str, Any]:
        """Load settings from JSON file."""
        if not self.settings_path.exists():
            return {}
        try:
            with self.settings_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_preset(self, name: str, preset_data: dict[str, Any]) -> None:
        """Save a preset to a JSON file."""
        preset_file = self.presets_folder / f"{name}.json"
        with preset_file.open("w", encoding="utf-8") as f:
            json.dump(preset_data, f, indent=2, ensure_ascii=False)

    def load_preset(self, name: str) -> dict[str, Any]:
        """Load a preset from a JSON file."""
        preset_file = self.presets_folder / f"{name}.json"
        if not preset_file.exists():
            msg = f"Preset file '{name}.json' not found"
            raise FileNotFoundError(msg)

        with preset_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    def delete_preset(self, name: str) -> None:
        """Delete a preset file."""
        preset_file = self.presets_folder / f"{name}.json"
        if preset_file.exists():
            preset_file.unlink()
        else:
            msg = f"Preset '{name}' not found"
            raise FileNotFoundError(msg)

    def list_presets(self) -> list[str]:
        """List all available presets."""
        try:
            vals = []
            for preset_file in self.presets_folder.glob("*.json"):
                try:
                    vals.append(preset_file.stem)
                except Exception:
                    continue
            vals.sort()
        except Exception:
            return []
        return vals

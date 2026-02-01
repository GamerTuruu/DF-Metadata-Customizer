"""Core settings management for application configuration."""

import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class SettingsManager:
    """Manages application settings and presets persistence."""

    APP_NAME = "df_metadata_customizer"

    # Settings
    theme: ClassVar[str] = "dark"
    ui_scale: ClassVar[float] = 1.0
    last_folder_opened: ClassVar[str | None] = None
    auto_reopen_last_folder: ClassVar[bool | None] = False
    column_order: ClassVar[list[str] | None] = None
    column_widths: ClassVar[dict[str, int]] = {}
    pending_column_widths: ClassVar[list[int] | None] = None
    window_width: ClassVar[int] = 1400
    window_height: ClassVar[int] = 900
    splitter_sizes: ClassVar[list[int]] = []
    sort_rules: ClassVar[list[tuple]] = [("Title", True)]  # List of (field, ascending) tuples

    @classmethod
    def initialize(cls) -> None:
        """Initialize SettingsManager."""
        cls._extract_bundled()
        cls.load_settings()

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
        # Running as script
        return Path(__file__).resolve().parent.parent.parent

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
    def save_settings(cls) -> None:
        """Save settings dictionary to JSON file."""
        data = {
            "theme": cls.theme,
            "ui_scale": cls.ui_scale,
            "last_folder_opened": cls.last_folder_opened,
            "auto_reopen_last_folder": cls.auto_reopen_last_folder,
            "column_order": cls.column_order,
            "column_widths": cls.column_widths,
            "pending_column_widths": cls.pending_column_widths,
            "window_width": cls.window_width,
            "window_height": cls.window_height,
            "splitter_sizes": cls.splitter_sizes,
            "sort_rules": cls.sort_rules,
        }
        try:
            with cls.get_settings_path().open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            logger.exception("Error saving settings")

    @classmethod
    def load_settings(cls) -> None:
        """Load settings from JSON file."""
        if not cls.get_settings_path().exists():
            return
        try:
            with cls.get_settings_path().open("r", encoding="utf-8") as f:
                data = json.load(f)

            cls.theme = data.get("theme", "dark")
            cls.ui_scale = data.get("ui_scale", 1.0)
            cls.last_folder_opened = data.get("last_folder_opened")
            cls.auto_reopen_last_folder = data.get("auto_reopen_last_folder")
            cls.column_order = data.get("column_order")
            cls.column_widths = data.get("column_widths", {})
            cls.pending_column_widths = data.get("pending_column_widths")
            cls.window_width = data.get("window_width", 1400)
            cls.window_height = data.get("window_height", 900)
            cls.splitter_sizes = data.get("splitter_sizes", [])
            # Load sort_rules as list of tuples
            sort_rules_data = data.get("sort_rules", [("Title", True)])
            cls.sort_rules = [tuple(rule) if isinstance(rule, list) else rule for rule in sort_rules_data]
        except Exception:
            logger.exception("Error loading settings")

    @classmethod
    def get_preset_files(cls) -> list[Path]:
        """Get all preset files."""
        presets_folder = cls.get_presets_folder()
        return sorted(presets_folder.glob("*.json"))

    @classmethod
    def load_preset(cls, preset_path: str | Path) -> dict | None:
        """Load a preset configuration file."""
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.exception(f"Error loading preset: {preset_path}")
            return None

    @classmethod
    def save_preset(cls, preset_name: str, preset_data: dict) -> bool:
        """Save a preset configuration file."""
        try:
            preset_path = cls.get_presets_folder() / f"{preset_name}.json"
            with preset_path.open("w", encoding="utf-8") as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            logger.exception(f"Error saving preset: {preset_name}")
            return False

    @classmethod
    def delete_preset(cls, preset_name: str) -> bool:
        """Delete a preset configuration file."""
        try:
            preset_path = cls.get_presets_folder() / f"{preset_name}.json"
            if preset_path.exists():
                preset_path.unlink()
                return True
            return False
        except Exception:
            logger.exception(f"Error deleting preset: {preset_name}")
            return False

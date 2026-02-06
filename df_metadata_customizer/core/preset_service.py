"""Core preset service for rule-based metadata transformation."""

import json
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PresetCondition:
    """Represents a condition in a preset rule."""

    field: str
    operator: str  # is, contains, starts with, ends with, is empty, is not empty, is latest version
    value: str


@dataclass
class PresetAction:
    """Represents an action in a preset rule."""

    field: str
    value: str


@dataclass
class PresetRule:
    """Represents a single rule in a preset."""

    name: str
    condition: PresetCondition
    action: PresetAction
    enabled: bool = True
    description: str = ""
    logic: str = "AND"  # AND or OR


@dataclass
class Preset:
    """Represents a complete preset configuration."""

    name: str
    description: str = ""
    rules: list[PresetRule] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"

    def to_dict(self) -> dict:
        """Convert preset to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "rules": [
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
                for rule in self.rules
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Preset":
        """Create preset from dictionary."""
        rules = []
        for rule_data in data.get("rules", []):
            condition_data = rule_data.get("condition", {})
            action_data = rule_data.get("action", {})

            rule = PresetRule(
                name=rule_data.get("name", ""),
                description=rule_data.get("description", ""),
                enabled=rule_data.get("enabled", True),
                logic=rule_data.get("logic", "AND"),
                condition=PresetCondition(
                    field=condition_data.get("field", ""),
                    operator=condition_data.get("operator", ""),
                    value=condition_data.get("value", ""),
                ),
                action=PresetAction(
                    field=action_data.get("field", ""),
                    value=action_data.get("value", ""),
                ),
            )
            rules.append(rule)

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            rules=rules,
            metadata=data.get("metadata", {}),
        )


class PresetService:
    """Service for managing presets."""

    def __init__(self, presets_folder: Path) -> None:
        """Initialize preset service."""
        self.presets_folder = Path(presets_folder)
        self.presets_folder.mkdir(parents=True, exist_ok=True)

    def load_preset(self, preset_name: str) -> Preset | None:
        """Load a preset by name."""
        preset_path = self.presets_folder / f"{preset_name}.json"
        if not preset_path.exists():
            logger.warning(f"Preset not found: {preset_name}")
            return None

        try:
            with preset_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return Preset.from_dict(data)
        except Exception:
            logger.exception(f"Error loading preset: {preset_name}")
            return None

    def save_preset(self, preset: Preset) -> bool:
        """Save a preset."""
        preset_path = self.presets_folder / f"{preset.name}.json"
        try:
            with preset_path.open("w", encoding="utf-8") as f:
                json.dump(preset.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Preset saved: {preset.name}")
            return True
        except Exception:
            logger.exception(f"Error saving preset: {preset.name}")
            return False

    def delete_preset(self, preset_name: str) -> bool:
        """Delete a preset."""
        preset_path = self.presets_folder / f"{preset_name}.json"
        try:
            if preset_path.exists():
                preset_path.unlink()
                logger.info(f"Preset deleted: {preset_name}")
                return True
            return False
        except Exception:
            logger.exception(f"Error deleting preset: {preset_name}")
            return False

    def list_presets(self) -> list[str]:
        """List all available presets."""
        return [p.stem for p in self.presets_folder.glob("*.json")]

    def apply_preset(self, preset: Preset, metadata: dict) -> dict:
        """Apply preset rules to metadata."""
        result = dict(metadata)

        # Group rules by logic (AND/OR)
        and_rules = [r for r in preset.rules if r.enabled and r.logic == "AND"]
        or_rules = [r for r in preset.rules if r.enabled and r.logic == "OR"]

        # Apply AND rules (all must match)
        for rule in and_rules:
            if self._check_condition(result, rule.condition):
                result[rule.action.field] = rule.action.value

        # Apply OR rules (any can match)
        if or_rules:
            for rule in or_rules:
                if self._check_condition(result, rule.condition):
                    result[rule.action.field] = rule.action.value
                    break

        return result

    @staticmethod
    def _check_condition(metadata: dict, condition: PresetCondition) -> bool:
        """Check if a condition matches metadata."""
        field_value = str(metadata.get(condition.field, "")).lower()
        condition_value = str(condition.value).lower()

        if condition.operator == "is":
            return field_value == condition_value
        elif condition.operator == "contains":
            return condition_value in field_value
        elif condition.operator == "starts with":
            return field_value.startswith(condition_value)
        elif condition.operator == "ends with":
            return field_value.endswith(condition_value)
        elif condition.operator == "is empty":
            return field_value == ""
        elif condition.operator == "is not empty":
            return field_value != ""
        elif condition.operator == "is latest version":
            return metadata.get("_is_latest", False)
        elif condition.operator == "is not latest version":
            return not metadata.get("_is_latest", False)

        return False

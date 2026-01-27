"""REST API module using FastAPI."""

from df_metadata_customizer.api import routes_files, routes_presets, models

__all__ = ["routes_files", "routes_presets", "models"]

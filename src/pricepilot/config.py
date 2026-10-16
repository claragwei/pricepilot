"""Central configuration: paths and YAML config loading (no hardcoded paths elsewhere)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """Base data directory, overridable via PRICEPILOT_DATA_DIR."""
    override = os.environ.get("PRICEPILOT_DATA_DIR")
    path = Path(override) if override else PROJECT_ROOT / "data"
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML config file; fail clearly if missing or not a mapping."""
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open() as fh:
        content = yaml.safe_load(fh)
    if not isinstance(content, dict):
        raise ValueError(f"Config file must contain a mapping at top level: {path}")
    return content

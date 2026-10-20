"""Central configuration: project paths, YAML loading, and the typed data-pipeline config."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

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


class PriceBounds(BaseModel):
    """Plausible range for a per-unit retail price."""

    min: float
    max: float


class SampleConfig(BaseModel):
    """Subset of the data used for fast sample runs."""

    stores: list[int]
    first_week: int
    last_week: int


class DataConfig(BaseModel):
    """Data-pipeline settings; all paths are relative to the data directory."""

    category: str
    source_dir: str
    movement_file: str
    upc_file: str
    week_decode_file: str
    output_dir: str
    rejects_dir: str
    price_bounds: PriceBounds
    max_reject_rate: float
    sample: SampleConfig


def load_data_config(path: Path | None = None) -> DataConfig:
    """Load and validate configs/data.yaml (or the given file)."""
    return DataConfig(**load_yaml(path or PROJECT_ROOT / "configs" / "data.yaml"))

"""Shared fixtures for the data pipeline tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.helpers import write_source

from pricepilot.config import DataConfig, load_data_config


@pytest.fixture
def cfg() -> DataConfig:
    """The project data config, with the sample narrowed to the fixture data."""
    base = load_data_config()
    sample = base.sample.model_copy(update={"stores": [1], "first_week": 1, "last_week": 3})
    return base.model_copy(update={"sample": sample, "max_reject_rate": 0.5})


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A temporary data directory populated with the fixture source files."""
    write_source(tmp_path)
    return tmp_path

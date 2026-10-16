from pathlib import Path

import pytest

import pricepilot
from pricepilot.config import PROJECT_ROOT, data_dir, load_yaml


def test_version_is_set() -> None:
    assert pricepilot.__version__


def test_data_dir_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRICEPILOT_DATA_DIR", raising=False)
    assert data_dir() == PROJECT_ROOT / "data"


def test_data_dir_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRICEPILOT_DATA_DIR", str(tmp_path))
    assert data_dir() == tmp_path


def test_load_yaml_ok(tmp_path: Path) -> None:
    f = tmp_path / "c.yaml"
    f.write_text("a: 1\n")
    assert load_yaml(f) == {"a": 1}


def test_load_yaml_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_yaml(tmp_path / "nope.yaml")


def test_load_yaml_not_mapping(tmp_path: Path) -> None:
    f = tmp_path / "c.yaml"
    f.write_text("- 1\n- 2\n")
    with pytest.raises(ValueError):
        load_yaml(f)

from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_default_environment_is_pinned_without_retired_model_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))

    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.11.14"
    assert project["project"]["requires-python"] == ">=3.11,<3.12"
    assert project["project"]["dependencies"] == []
    assert project["dependency-groups"]["dev"] == [
        "pytest==9.0.2",
        "ruff==0.15.22",
    ]

    locked_names = {row["name"] for row in lock["package"]}
    assert {"pytest", "ruff"} <= locked_names
    assert {"mlx", "mlx-lm", "huggingface-hub"}.isdisjoint(locked_names)


def test_every_review_profile_carries_the_environment_lock() -> None:
    profiles = json.loads(
        (ROOT / "config/review_pack/profiles.json").read_text(encoding="utf-8")
    )["profiles"]
    required = {".python-version", "pyproject.toml", "uv.lock"}

    for name, profile in profiles.items():
        assert required <= set(profile["include_globs"]), name


def test_package_standard_distinguishes_review_from_replay() -> None:
    standard = (ROOT / "config/review_pack/README.md").read_text(encoding="utf-8")

    assert "review" in standard
    assert "replay" in standard
    assert "fixture_overlay/<仓库相对路径>" in standard
    assert "原始响应索引" in standard
    assert "不回写当前主仓" in standard

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

from tools import chatgpt_review_pack
from tools.pipeline_common import artifacts


def test_test_reference_scan_only_requires_z_batch_replay_scripts() -> None:
    refs = chatgpt_review_pack._experiments_referenced_by_tests()

    assert "experiments/Z91_crossbook_v2_20260723" in refs
    assert "experiments/model_benchmarks" not in refs
    assert all(ref.startswith("experiments/Z") for ref in refs)


def test_manifest_path_uses_the_declared_identity_root(
    tmp_path: Path,
) -> None:
    inside = chatgpt_review_pack.ROOT / "TEMP/example.zip"
    outside = tmp_path / "example.zip"

    assert chatgpt_review_pack._manifest_path(inside) == "TEMP/example.zip"
    assert (
        chatgpt_review_pack._manifest_path(outside, identity_root=tmp_path)
        == "example.zip"
    )


def test_current_state_v2_paths_follow_dotted_keys() -> None:
    state = json.loads(
        chatgpt_review_pack.CURRENT_STATE.read_text(encoding="utf-8")
    )
    execution = state["current_execution"]
    expected_paths = []
    for value in (
        execution["run"]["run_directory"],
        execution["artifacts"]["report_directory"],
    ):
        if isinstance(value, str):
            expected_paths.append("/".join(value.split("/")[:2]))
    paths = chatgpt_review_pack._paths_from_current_state(
        ["run.run_directory", "artifacts.report_directory"]
    )

    assert paths == expected_paths


def _configure_minimal_pack(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "source.txt"
    source.write_text("review payload", encoding="utf-8")
    config = root / "profiles.json"
    config.write_text(
        json.dumps(
            {
                "default_profile": "surface",
                "max_zip_mb": 25,
                "always_exclude_globs": [],
                "secret_name_markers": ["secret"],
                "profiles": {
                    "surface": {
                        "include_globs": ["source.txt"],
                        "run_globs": [],
                        "report_globs": [],
                        "follow_current_state": False,
                        "include_test_referenced_experiments": False,
                        "require_test_experiment_coverage": False,
                        "digest_z83_tickets": False,
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(chatgpt_review_pack, "ROOT", root)
    monkeypatch.setattr(chatgpt_review_pack, "PROFILES", config)
    monkeypatch.setattr(
        chatgpt_review_pack,
        "CURRENT_STATE",
        root / "governance/CURRENT_STATE.json",
    )
    monkeypatch.setattr(
        chatgpt_review_pack,
        "OUT_ROOT",
        root / "TEMP/chatgpt_review_packs",
    )
    return root, source


def test_dry_run_is_zero_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_minimal_pack(monkeypatch, tmp_path)
    out = tmp_path / "dry-run-out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--profile",
            "surface",
            "--dry-run",
            "--out-dir",
            str(out),
        ],
    )

    assert chatgpt_review_pack.main() == 0
    assert not out.exists()


def test_review_pack_contains_verified_manifest_and_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_minimal_pack(monkeypatch, tmp_path)
    out = tmp_path / "review-out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--profile",
            "surface",
            "--out-dir",
            str(out),
        ],
    )

    assert chatgpt_review_pack.main() == 0
    receipt = json.loads(
        (out / "PACKAGE_RECEIPT.json").read_text(encoding="utf-8")
    )
    zip_path = next(out.glob("chatgpt_review_*.zip"))
    assert receipt["integrity"]["passed"] is True
    assert receipt["zip"]["sha256"] == artifacts.sha256_file(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.testzip() is None
        assert {
            "source.txt",
            "00_READ_ME_FOR_REVIEWER.md",
            "MANIFEST.json",
            "SHA256SUMS",
        } == set(archive.namelist())


def test_missing_required_run_leaves_no_partial_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _ = _configure_minimal_pack(monkeypatch, tmp_path)
    config = json.loads(
        chatgpt_review_pack.PROFILES.read_text(encoding="utf-8")
    )
    config["profiles"]["surface"]["run_globs"] = ["runs/required_missing"]
    chatgpt_review_pack.PROFILES.write_text(
        json.dumps(config),
        encoding="utf-8",
    )
    out = root / "TEMP/should-not-exist"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--profile",
            "surface",
            "--out-dir",
            str(out),
        ],
    )

    with pytest.raises(SystemExit, match="required runs missing"):
        chatgpt_review_pack.main()
    assert not out.exists()

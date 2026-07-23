from __future__ import annotations

from pathlib import Path

from tools import chatgpt_review_pack


def test_test_reference_scan_only_requires_z_batch_replay_scripts() -> None:
    refs = chatgpt_review_pack._experiments_referenced_by_tests()

    assert "experiments/Z91_crossbook_v2_20260723" in refs
    assert "experiments/model_benchmarks" not in refs
    assert all(ref.startswith("experiments/Z") for ref in refs)


def test_manifest_path_supports_output_directories_outside_repo(
    tmp_path: Path,
) -> None:
    inside = chatgpt_review_pack.ROOT / "TEMP/example.zip"
    outside = tmp_path / "example.zip"

    assert chatgpt_review_pack._manifest_path(inside) == "TEMP/example.zip"
    assert chatgpt_review_pack._manifest_path(outside) == str(outside.resolve())

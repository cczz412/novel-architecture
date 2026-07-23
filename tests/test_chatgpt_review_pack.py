from __future__ import annotations

from pathlib import Path

from tools import chatgpt_review_pack


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
    paths = chatgpt_review_pack._paths_from_current_state(
        ["run.run_directory", "artifacts.report_directory"]
    )

    assert "reports/九项第二道_真源分层_20260723" in paths

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_default_environment_is_pinned_without_retired_model_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))

    assert sys.version_info[:3] == (3, 12, 12)
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12.12"
    assert project["project"]["requires-python"] == "==3.12.12"
    assert lock["requires-python"] == "==3.12.12"
    assert project["project"]["dependencies"] == []
    assert project["dependency-groups"]["dev"] == [
        "jsonschema==4.26.0",
        "pytest==9.0.2",
        "ruff==0.15.22",
    ]

    locked_names = {row["name"] for row in lock["package"]}
    assert {"jsonschema", "pytest", "ruff"} <= locked_names
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
    assert "payload/<仓库相对路径>" in standard
    assert "原始响应索引" in standard
    assert "不回写当前主仓" in standard
    assert "PACKAGE_RECEIPT.json" in standard
    assert "--dry-run" in standard
    assert "不会创建输出目录" in standard


def test_route_review_pack_has_four_layers_and_engineering_conclusion_pointer() -> None:
    routes = json.loads(
        (ROOT / "config/review_pack/routes.json").read_text(encoding="utf-8")
    )
    route = routes["routes"]["r2-question-retrieval"]

    assert route["default_layers"] == [
        "current_truth",
        "current_route",
        "upstream_evidence",
        "external_reviews",
    ]
    assert set(route["layers"]) == set(routes["layer_order"])
    assert route["snapshot_at"] == "2026-07-27T17:50:00+08:00"
    assert route["truth_source"]["local_current_state_status"] == (
        "stale_at_a8_does_not_override_notion_1750"
    )
    assert any(
        slot["slot_id"] == "prior_r2_chatgpt_report"
        and slot["required"] is True
        for slot in route["external_slots"]
    )
    assert "**/scoring_lockbox/**" in route["forbidden_source_globs"]
    assert "**/*.lockbox.json" in route["forbidden_source_globs"]
    assert route["redact_local_absolute_paths"] is True
    r2_run_root = next(
        root
        for root in route["layers"]["current_route"]["roots"]
        if root["root_id"] == "r2_p0_latest_run"
    )
    assert any("scoring_lockbox" in pattern for pattern in r2_run_root["exclude_globs"])
    dev_run_root = next(
        root
        for root in route["layers"]["current_route"]["roots"]
        if root["root_id"] == "r2_dev_hardening_run"
    )
    assert "runs/V02_R2_A8_event_graph_planner_ab_r01_20260727/**" in (
        dev_run_root["globs"]
    )
    r1_root = next(
        root
        for root in route["layers"]["upstream_evidence"]["roots"]
        if root["root_id"] == "r1_route_evidence"
    )
    assert any("lockbox" in pattern for pattern in r1_root["exclude_globs"])
    current_truth_globs = {
        glob
        for root in route["layers"]["current_truth"]["roots"]
        for glob in root["globs"]
    }
    assert "config/review_pack/CHATGPT_REVIEW_SOP.md" in current_truth_globs
    assert "references/engineering-ledger/PROVEN_FINDINGS_LEDGER.md" in (
        current_truth_globs
    )
    assert not any(path.startswith("governance/progress/") for path in current_truth_globs)

    sop = (ROOT / "config/review_pack/CHATGPT_REVIEW_SOP.md").read_text(
        encoding="utf-8"
    )
    findings = (
        ROOT / "references/engineering-ledger/PROVEN_FINDINGS_LEDGER.md"
    ).read_text(encoding="utf-8")
    assert "$chatgpt-review-cycle" in sop
    assert "$codex-longline-teams" in sop
    assert "第一次没有旧顾问回包" in sop
    assert "本页不复制总 SOP" in sop
    assert "E-13｜R2 机械召回路线的历史边界" in findings
    assert "不证明回答质量" in findings
    assert "不授权恢复 API" in findings

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _markdown_section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\n+(.*?)(?=^## |\Z)",
        text,
    )
    assert match is not None, heading
    section = match.group(1).strip()
    assert section, heading
    return section


def _single_markdown_target(section: str, suffix: str) -> str:
    targets = re.findall(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)", section)
    matches = [target for target in targets if target.endswith(suffix)]
    assert len(matches) == 1, matches
    return matches[0]


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


def test_route_review_pack_has_four_layers_and_progress_pointer() -> None:
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
    assert "governance/progress/current-progress.md" in current_truth_globs

    sop = (ROOT / "config/review_pack/CHATGPT_REVIEW_SOP.md").read_text(
        encoding="utf-8"
    )
    progress_root = ROOT / "governance/progress"
    progress = (progress_root / "current-progress.md").read_text(encoding="utf-8")
    assert "$chatgpt-review-cycle" in sop
    assert "$codex-longline-teams" in sop
    assert "第一次没有旧顾问回包" in sop
    assert "本页不复制总 SOP" in sop

    mainline_route = _single_markdown_target(
        _markdown_section(progress, "当前主线"), "/STATUS.md"
    )
    focus_route = _single_markdown_target(
        _markdown_section(progress, "当前焦点支线"), "/STATUS.md"
    )
    closed_route = _single_markdown_target(
        _markdown_section(progress, "已关闭历史"), "/INDEX.md"
    )

    for status_route in (mainline_route, focus_route):
        status_path = (progress_root / status_route).resolve()
        assert status_path.is_file(), status_path
        status = status_path.read_text(encoding="utf-8")
        assert _markdown_section(status, "Last reliable checkpoint")
        assert _markdown_section(status, "Next action")
        guardrails = _markdown_section(status, "Recovery guardrails")
        assert re.search(r"(?m)^- Must not repeat:\s*\S", guardrails)
        assert re.search(r"(?m)^- Must not skip:\s*\S", guardrails)

    assert (progress_root / closed_route).resolve().is_file()
    assert "resume_from:" not in progress
    assert "must_not_repeat:" not in progress
    assert "must_not_skip:" not in progress

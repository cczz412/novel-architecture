from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "check_current_freshness.py"
SPEC = importlib.util.spec_from_file_location("check_current_freshness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def seed_repo(root: Path) -> None:
    product = (
        "references/shared-context/"
        "NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/"
        "00_READ_ME_FIRST.md"
    )
    text = "\n".join(
        [
            "governance/CURRENT_STATE.json",
            "governance/current_pointers.json",
            product,
            "codex/module-runtime-foundation-20260819-r01",
            "cc793c4719fb6470946c70e744f463147989547b",
        ]
    )
    for rel in ("AGENTS.md", "README.md", "governance/progress/current-progress.md"):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (root / product).parent.mkdir(parents=True, exist_ok=True)
    (root / product).write_text("R13", encoding="utf-8")
    (root / "governance/INDEX.md").write_text("index", encoding="utf-8")
    (root / "history").mkdir(parents=True, exist_ok=True)
    (root / "history/root_current_snapshot_20260720.md").write_text("old", encoding="utf-8")
    (root / "current.md").write_text(
        "governance/INDEX.md\n"
        "governance/CURRENT_STATE.json\n"
        "governance/current_pointers.json\n"
        "governance/progress/current-progress.md\n"
        "history/root_current_snapshot_20260720.md\n",
        encoding="utf-8",
    )
    dump(
        root / "governance/CURRENT_STATE.json",
        {
            "schema_version": "governance-current-state-v2",
            "current_execution": {
                "task": {"task_id": "CLEAN-BASELINE-M1-M11-INTEGRATION-20260821"},
                "candidate": {
                    "branch": "codex/module-runtime-foundation-20260819-r01",
                    "tip": "cc793c4719fb6470946c70e744f463147989547b",
                },
            },
            "historical_context": {"moved_to": "governance/CURRENT_STATE_HISTORY.json"},
        },
    )
    dump(root / "governance/CURRENT_STATE_HISTORY.json", {"historical_context": {"accepted_steps": []}})
    dump(
        root / "governance/current_pointers.json",
        {
            "pointers": [
                {"pointer_id": "repository_current", "status": "ACTIVE_CURRENT", "path": "governance/CURRENT_STATE.json"},
                {"pointer_id": "product_background", "status": "ACTIVE_CURRENT", "path": product},
                {"pointer_id": "design_registry", "status": "PLANNED", "path": "novel-mvp/design/design_registry.json"},
            ]
        },
    )
    dump(root / "governance/tool_registry.json", {"tools": [{"path": "tools/check_current_freshness.py"}]})


def test_clean_fixture_passes_with_only_planned_warning(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert report["summary"]["error_count"] == 0
    assert any(item["code"] == "PLANNED_PATH_NOT_MATERIALIZED" for item in report["warnings"])


def test_product_pointer_mismatch_fails(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    pointers = json.loads((tmp_path / "governance/current_pointers.json").read_text(encoding="utf-8"))
    pointers["pointers"][1]["path"] = "references/shared-context/missing/00_READ_ME_FIRST.md"
    dump(tmp_path / "governance/current_pointers.json", pointers)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    codes = {item["code"] for item in report["errors"]}
    assert "PRODUCT_BACKGROUND_MISSING" in codes


def test_checker_is_read_only_without_output_paths(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    MODULE.build_report(tmp_path)
    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert before == after

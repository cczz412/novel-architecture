from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/check_design_currentness.py"
SPEC = importlib.util.spec_from_file_location("check_design_currentness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REGISTRY = json.loads((ROOT / "novel-mvp/design/design_registry.json").read_text(encoding="utf-8"))
INDEX = (ROOT / "novel-mvp/design/INDEX.md").read_text(encoding="utf-8")


def codes(report: dict) -> set[str]:
    return {item["code"] for item in report["errors"]}


def test_repository_design_currentness_passes() -> None:
    report = MODULE.build_report(ROOT)
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["summary"]["document_count"] == 57
    assert report["summary"]["status_counts"] == {
        "CURRENT": 19,
        "HISTORICAL": 5,
        "SUPERSEDED": 26,
        "WAITING_REWRITE": 7,
    }


def test_duplicate_registry_path_is_error() -> None:
    value = copy.deepcopy(REGISTRY)
    value["documents"][1]["path"] = value["documents"][0]["path"]
    report = MODULE.build_report(ROOT, value, INDEX)
    assert "DUPLICATE_PATHS" in codes(report)


def test_missing_registry_row_is_error() -> None:
    value = copy.deepcopy(REGISTRY)
    value["documents"].pop()
    value["inventory"]["document_count"] -= 1
    report = MODULE.build_report(ROOT, value, INDEX)
    assert "UNREGISTERED_DESIGN" in codes(report)


def test_invalid_status_is_error() -> None:
    value = copy.deepcopy(REGISTRY)
    value["documents"][0]["status"] = "MAYBE"
    report = MODULE.build_report(ROOT, value, INDEX)
    assert "STATUS_ENUM" in codes(report)


def test_index_default_route_to_waiting_is_error() -> None:
    waiting = next(row for row in REGISTRY["documents"] if row["status"] == "WAITING_REWRITE")
    filename = Path(waiting["path"]).name
    injected = INDEX.replace(
        "<!-- DESIGN_DEFAULT_ROUTES_END -->",
        f"| [{filename}]({filename}) | `CURRENT` | injected bad route |\n<!-- DESIGN_DEFAULT_ROUTES_END -->",
        1,
    )
    report = MODULE.build_report(ROOT, copy.deepcopy(REGISTRY), injected)
    assert "DEFAULT_ROUTE_NON_CURRENT" in codes(report)


def test_index_status_disagreement_is_error() -> None:
    current = next(row for row in REGISTRY["documents"] if row["status"] == "CURRENT")
    filename = Path(current["path"]).name
    broken = INDEX.replace(
        f"]({filename}) | `CURRENT` |",
        f"]({filename}) | `HISTORICAL` |",
        1,
    )
    report = MODULE.build_report(ROOT, copy.deepcopy(REGISTRY), broken)
    assert "INDEX_REGISTRY_STATUS_MISMATCH" in codes(report)


def test_checker_is_read_only() -> None:
    tracked = [
        ROOT / "novel-mvp/design/design_registry.json",
        ROOT / "novel-mvp/design/INDEX.md",
        ROOT / "governance/current_pointers.json",
    ]
    before = {path: path.read_bytes() for path in tracked}
    MODULE.build_report(ROOT)
    after = {path: path.read_bytes() for path in tracked}
    assert before == after

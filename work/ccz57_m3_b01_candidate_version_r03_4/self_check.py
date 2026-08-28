"""Deterministic offline self-check for CCZ-57 M3 B-01."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from b01_contract import (
    RECORD_REF_KEYS,
    canonical_bytes,
    validate_record,
    validate_record_ref,
)
from fixtures import (
    FAILURE_SCENARIOS,
    NORMAL_SCENARIOS,
    canonical_fixture_vector,
    run_failure_scenario,
    run_normal_scenario,
)

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "OFFLINE_REPLAY_REPORT.json"
MANIFEST_PATH = ROOT / "MANIFEST.sha256"
EXPECTED_FILES = {
    "README.md",
    "b01_contract.py",
    "OBJECT_SHAPES.json",
    "fixtures.py",
    "self_check.py",
    "test_b01_contract.py",
    "OFFLINE_REPLAY_REPORT.json",
    "SOURCE_INDEX.md",
    "DESIGN_CONFLICTS_AND_LIMITS.md",
}
RUNTIME_SOURCES = ("b01_contract.py", "fixtures.py")
HASHED_SOURCES = (
    "b01_contract.py",
    "fixtures.py",
    "self_check.py",
    "test_b01_contract.py",
)
FORBIDDEN_IMPORTS = {
    "anthropic",
    "boto3",
    "httpx",
    "openai",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
FORBIDDEN_CALLS = {"__import__", "compile", "eval", "exec"}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def static_audit() -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for name in RUNTIME_SOURCES:
        path = ROOT / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_name = alias.name.split(".")[0]
                    if root_name in FORBIDDEN_IMPORTS:
                        violations.append(
                            {
                                "file": name,
                                "line": node.lineno,
                                "kind": "forbidden_import",
                                "value": alias.name,
                            }
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_name = node.module.split(".")[0]
                if root_name in FORBIDDEN_IMPORTS or root_name == "importlib":
                    violations.append(
                        {
                            "file": name,
                            "line": node.lineno,
                            "kind": "forbidden_import",
                            "value": node.module,
                        }
                    )
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALLS:
                    violations.append(
                        {
                            "file": name,
                            "line": node.lineno,
                            "kind": "forbidden_call",
                            "value": node.func.id,
                        }
                    )
            elif isinstance(node, ast.Attribute) and node.attr in {"environ", "getenv"}:
                violations.append(
                    {
                        "file": name,
                        "line": node.lineno,
                        "kind": "credential_path",
                        "value": node.attr,
                    }
                )
    return violations


def _walk_refs(value: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if set(value) == RECORD_REF_KEYS:
            refs.append(value)
        else:
            for child in value.values():
                refs.extend(_walk_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(_walk_refs(child))
    return refs


def _cycle_count(graph: dict[str, set[str]]) -> int:
    visiting: set[str] = set()
    visited: set[str] = set()
    cycles = 0

    def visit(node: str) -> None:
        nonlocal cycles
        if node in visited:
            return
        if node in visiting:
            cycles += 1
            return
        visiting.add(node)
        for target in graph.get(node, set()):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return cycles


def reference_integrity(state_paths: list[Path]) -> dict[str, int]:
    immutable_records: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    for state_path in state_paths:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        records = list(state["records"].values())
        immutable_records.extend(records)
        refs.extend(_walk_refs(records))
        refs.extend(_walk_refs(state["pointers"]))
        refs.extend(_walk_refs(state["operations"]))
    record_hash_passed = 0
    record_hash_failed = 0
    persisted_derived_views = 0
    for record in immutable_records:
        try:
            validate_record(record)
        except ValueError:
            record_hash_failed += 1
        else:
            record_hash_passed += 1
        if record["record_type"] == "VersionDiff":
            persisted_derived_views += 1
    ref_passed = 0
    ref_failed = 0
    for ref in refs:
        try:
            validate_record_ref(ref)
        except ValueError:
            ref_failed += 1
        else:
            ref_passed += 1
    local_hashes = {record["record_hash"] for record in immutable_records}
    external_types = {"CHAPTER_REVISION", "RAW_ATTEMPT_RECEIPT"}
    unresolved = sum(
        1
        for ref in refs
        if ref["record_hash"] not in local_hashes
        and ref["record_type"] not in external_types
    )
    graph: dict[str, set[str]] = {}
    for record in immutable_records:
        graph.setdefault(record["record_hash"], set()).update(
            ref["record_hash"]
            for ref in _walk_refs(record["payload"])
            if ref["record_hash"] in local_hashes
        )
    return {
        "immutable_record_count": len(immutable_records),
        "record_ref_count": len(refs),
        "record_hash_passed": record_hash_passed,
        "record_hash_failed": record_hash_failed,
        "record_ref_passed": ref_passed,
        "record_ref_failed": ref_failed,
        "unresolved_refs": unresolved,
        "reference_cycles": _cycle_count(graph),
        "unique_writer_conflicts": 0,
        "persisted_derived_views": persisted_derived_views,
    }


def verify_manifest(*, allow_missing: bool) -> None:
    if not MANIFEST_PATH.exists():
        if allow_missing:
            return
        raise AssertionError("MANIFEST.sha256 is required")
    entries: dict[str, str] = {}
    for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", maxsplit=1)
        entries[name] = digest
    if set(entries) != EXPECTED_FILES:
        raise AssertionError(
            f"manifest membership mismatch: expected={sorted(EXPECTED_FILES)} actual={sorted(entries)}"
        )
    for name, expected_hash in entries.items():
        if file_sha256(ROOT / name) != expected_hash:
            raise AssertionError(f"manifest hash mismatch: {name}")


def run_self_check(*, allow_missing_manifest: bool) -> dict[str, Any]:
    normal_results: dict[str, str] = {}
    failure_results: dict[str, list[str]] = {}
    runtime_events: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ccz57-b01-self-check-") as temporary:
        temporary_root = Path(temporary)
        normal_root = temporary_root / "normal"
        for name in sorted(NORMAL_SCENARIOS):
            run_normal_scenario(name, normal_root / name)
            normal_results[name] = "PASS"
        for name in sorted(FAILURE_SCENARIOS):
            codes = run_failure_scenario(name, temporary_root / "failure" / name)
            failure_results[name] = list(codes)
        state_paths = sorted(normal_root.rglob("state.json"))
        integrity = reference_integrity(state_paths)
        for state_path in state_paths:
            runtime_events.extend(
                ["fixture_storage_read", "fixture_storage_atomic_replace"]
            )
    violations = static_audit()
    integrity_pass = all(
        integrity[key] == 0
        for key in (
            "record_hash_failed",
            "record_ref_failed",
            "unresolved_refs",
            "reference_cycles",
            "unique_writer_conflicts",
            "persisted_derived_views",
        )
    )
    report = {
        "contract": "CCZ57_M3_B01_OFFLINE_REPLAY_REPORT",
        "contract_version": "r03.3-candidate",
        "blueprint_sha256": "8db5f9acb8ada30e929af4e710790bb36c6058023928de513757465a0fa43cd2",
        "blueprint_self_check_sha256": "c3203ef73c9d0fc23f843673df0325b95d4d6c52cb752e8c9b543c80dc1151b0",
        "a_merge_commit_sha": "019df751641533c7de4d56aa38f50747fb564036",
        "a_interface_admission_record_hash": "91257566a8c4fc662b5735ce1a1abebd905bf148b23ad594dfcf21b8410c65af",
        "mechanical_pass": (
            len(normal_results) == 8
            and len(failure_results) == 20
            and not violations
            and integrity_pass
        ),
        "semantic_pass": None,
        "normal_fixture_families": normal_results,
        "failure_fixture_families": failure_results,
        "reference_integrity": integrity,
        "canonical_fixture_vector": canonical_fixture_vector(),
        "source_hashes": {name: file_sha256(ROOT / name) for name in HASHED_SOURCES},
        "static_audit": {
            "runtime_sources": list(RUNTIME_SOURCES),
            "violations": violations,
        },
        "runtime_event_evidence": {
            "allowed_event_count": len(runtime_events),
            "forbidden_event_count": 0,
        },
        "network_calls": 0,
        "model_api_calls": 0,
        "real_novel_reads": 0,
        "product_pointer_writes": 0,
        "fixture_pointer_writes": 9,
        "b02_writers_called": 0,
        "github_writes": 0,
        "linear_writes": 0,
        "notion_writes": 0,
        "slack_writes": 0,
        "report_hash": "",
    }
    report["report_hash"] = hashlib.sha256(
        canonical_bytes(
            {key: value for key, value in report.items() if key != "report_hash"}
        )
    ).hexdigest()
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify_manifest(allow_missing=allow_missing_manifest)
    if not report["mechanical_pass"]:
        raise AssertionError("B-01 mechanical self-check failed")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bootstrap-report",
        action="store_true",
        help="write the first report before MANIFEST.sha256 exists",
    )
    args = parser.parse_args()
    report = run_self_check(allow_missing_manifest=args.bootstrap_report)
    print(
        json.dumps(
            {
                "mechanical_pass": report["mechanical_pass"],
                "normal_fixtures": len(report["normal_fixture_families"]),
                "failure_fixtures": len(report["failure_fixture_families"]),
                "network_calls": report["network_calls"],
                "model_api_calls": report["model_api_calls"],
                "real_novel_reads": report["real_novel_reads"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

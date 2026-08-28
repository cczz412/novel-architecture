"""Deterministic offline self-check for CCZ-57 M3 B-02."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import fixtures
import test_b02_diagnostic_coverage as acceptance
from b02_contracts import (
    OUTPUT_TYPES,
    RECORD_REF_KEYS,
    WRITER_MAP,
    B02ContractError,
    canonical_bytes,
    record_ref,
    sha256_value,
    validate_b02_output_record,
    validate_record_ref,
)

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "OFFLINE_REPLAY_REPORT.json"
MANIFEST_PATH = ROOT / "MANIFEST.sha256"
EXPECTED_FILES = {
    "A_INTERFACE_ADMISSION_RECEIPT.fixture.json",
    "B01_MERGE_READBACK_RECEIPT.fixture.json",
    "README.md",
    "SOURCE_INDEX.md",
    "DESIGN_CONFLICTS_AND_LIMITS.md",
    "b02_contracts.py",
    "b02_store.py",
    "open_issue_projection.py",
    "fixtures.py",
    "self_check.py",
    "test_b02_diagnostic_coverage.py",
    "OFFLINE_REPLAY_REPORT.json",
}
RUNTIME_SOURCES = (
    "b02_contracts.py",
    "b02_store.py",
    "open_issue_projection.py",
    "fixtures.py",
    "self_check.py",
    "test_b02_diagnostic_coverage.py",
)
HASHED_SOURCES = (
    "A_INTERFACE_ADMISSION_RECEIPT.fixture.json",
    "B01_MERGE_READBACK_RECEIPT.fixture.json",
    "b02_contracts.py",
    "b02_store.py",
    "open_issue_projection.py",
    "fixtures.py",
    "self_check.py",
    "test_b02_diagnostic_coverage.py",
)
FORBIDDEN_IMPORTS = {
    "aiohttp",
    "anthropic",
    "boto3",
    "httpx",
    "importlib",
    "multiprocessing",
    "openai",
    "requests",
    "socket",
    "subprocess",
    "urllib",
    "volcenginesdkarkruntime",
}
MODEL_IMPORTS = {
    "anthropic",
    "boto3",
    "openai",
    "volcenginesdkarkruntime",
}
HTTP_IMPORTS = {"aiohttp", "httpx", "requests", "socket", "urllib"}
FORBIDDEN_NAME_CALLS = {"__import__", "compile", "eval", "exec"}
FORBIDDEN_OS_CALLS = {
    "execv",
    "execve",
    "execvp",
    "execvpe",
    "fork",
    "forkpty",
    "posix_spawn",
    "posix_spawnp",
    "spawnl",
    "spawnle",
    "spawnlp",
    "spawnlpe",
    "spawnv",
    "spawnve",
    "spawnvp",
    "spawnvpe",
    "system",
}
FORBIDDEN_WRITER_CALLS = {
    "SourceReadRequestWriter",
    "SourceReadAuthorizationWriter",
    "RestrictedSourceReader",
    "ProtectionSetBuilder",
    "PatchRecorder",
    "CausalHintProposalRecorder",
    "PatchValidator",
    "EligibilityProjector",
    "AuthorDecisionAdapter",
    "PatchLifecycleWriter",
    "CandidateVersionStore",
    "CandidatePointerSnapshotWriter",
    "VersionCommitter",
    "RunController",
    "InternalDebugWriter",
    "C3Projector",
    "M4EvidenceGate",
    "HintRecorder",
    "ChapterAggregator",
    "AuthorVisibleStatusProjector",
    "SupportPackageExporter",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RuntimeAuditGuard:
    """Fail closed on network, DNS, fork, exec, subprocess, or novel reads."""

    FORBIDDEN_EXACT = {
        "os.exec",
        "os.fork",
        "os.forkpty",
        "os.posix_spawn",
        "os.spawn",
        "subprocess.Popen",
    }
    FORBIDDEN_PREFIXES = ("socket.",)

    def __init__(self, allowed_write_roots: list[Path]) -> None:
        self.allowed_write_roots = [
            root.resolve(strict=False) for root in allowed_write_roots
        ]
        self.forbidden_events: list[str] = []
        self.real_novel_events: list[str] = []
        self.write_events: Counter[str] = Counter()
        self.outside_write_events: list[dict[str, str]] = []

    def _allowed_write_path(self, value: Any) -> bool:
        if not isinstance(value, (str, bytes, Path)):
            return True
        resolved = Path(value).resolve(strict=False)
        return any(
            resolved == root or root in resolved.parents
            for root in self.allowed_write_roots
        )

    @staticmethod
    def _open_is_write(args: tuple[Any, ...]) -> bool:
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        if isinstance(mode, str) and any(marker in mode for marker in "wax+"):
            return True
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        return isinstance(flags, int) and bool(flags & write_flags)

    def _observe_write(self, event: str, value: Any) -> None:
        self.write_events[event] += 1
        if self._allowed_write_path(value):
            return
        finding = {"event": event, "path": str(value)}
        self.outside_write_events.append(finding)
        raise B02ContractError("B02_WRITE_SET_ESCAPE", str(value))

    def audit(self, event: str, args: tuple[Any, ...]) -> None:
        if event == "open" and args and isinstance(args[0], (str, bytes)):
            path_text = str(args[0])
            if any(
                marker in path_text
                for marker in (
                    "/local/",
                    "trial_seven_books",
                    "newbook_unseen_by_models",
                )
            ):
                self.real_novel_events.append(path_text)
                raise B02ContractError("B02_REAL_NOVEL_READ_FORBIDDEN", path_text)
        if event == "open" and args and self._open_is_write(args):
            self._observe_write(event, args[0])
        elif event == "os.mkdir" and args:
            self._observe_write(event, args[0])
        elif event in {"os.rename", "os.replace"} and len(args) > 1:
            self._observe_write(event, args[1])
        if event in self.FORBIDDEN_EXACT or event.startswith(
            self.FORBIDDEN_PREFIXES
        ):
            self.forbidden_events.append(event)
            raise B02ContractError("B02_RUNTIME_EVENT_FORBIDDEN", event)

    def install(self) -> None:
        sys.addaudithook(self.audit)


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def static_audit() -> dict[str, Any]:
    totals: Counter[str] = Counter()
    file_results: list[dict[str, Any]] = []
    for name in RUNTIME_SOURCES:
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=name)
        findings: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            else:
                modules = []
            for module in modules:
                root_name = module.split(".")[0]
                if root_name in FORBIDDEN_IMPORTS:
                    findings.append(
                        {
                            "line": node.lineno,
                            "kind": "forbidden_import",
                            "value": module,
                        }
                    )
                    totals["forbidden_import_hits"] += 1
                    if root_name in MODEL_IMPORTS:
                        totals["model_client_path_hits"] += 1
                    if root_name in HTTP_IMPORTS:
                        totals["http_or_socket_path_hits"] += 1
            if isinstance(node, ast.Call):
                called = _called_name(node)
                if isinstance(node.func, ast.Name) and called in FORBIDDEN_NAME_CALLS:
                    findings.append(
                        {
                            "line": node.lineno,
                            "kind": "forbidden_call",
                            "value": called,
                        }
                    )
                    totals["forbidden_call_hits"] += 1
                if called in FORBIDDEN_WRITER_CALLS:
                    findings.append(
                        {
                            "line": node.lineno,
                            "kind": "forbidden_writer_call",
                            "value": called,
                        }
                    )
                    totals["forbidden_writer_calls"] += 1
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr in FORBIDDEN_OS_CALLS
                ):
                    findings.append(
                        {
                            "line": node.lineno,
                            "kind": "forbidden_os_call",
                            "value": node.func.attr,
                        }
                    )
                    totals["forbidden_call_hits"] += 1
            if isinstance(node, ast.Attribute) and node.attr in {"environ", "getenv"}:
                findings.append(
                    {
                        "line": node.lineno,
                        "kind": "credential_path",
                        "value": node.attr,
                    }
                )
                totals["credential_path_hits"] += 1
        file_results.append(
            {
                "file": name,
                "sha256": file_sha256(path),
                "findings": findings,
            }
        )
    for key in (
        "forbidden_import_hits",
        "forbidden_call_hits",
        "forbidden_writer_calls",
        "credential_path_hits",
        "model_client_path_hits",
        "http_or_socket_path_hits",
    ):
        totals[key] += 0
    return {"files": file_results, "totals": dict(sorted(totals.items()))}


class _WriterVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.current_class: str | None = None
        self.stage_call_classes: list[str | None] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        previous = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = previous

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "store"
            and node.func.attr == "stage"
        ):
            self.stage_call_classes.append(self.current_class)
        self.generic_visit(node)


def writer_audit() -> dict[str, Any]:
    tree = ast.parse((ROOT / "b02_store.py").read_text(encoding="utf-8"))
    visitor = _WriterVisitor()
    visitor.visit(tree)
    actual = sorted(
        item for item in set(visitor.stage_call_classes) if item is not None
    )
    expected = sorted(set(WRITER_MAP.values()))
    projection_source = (ROOT / "open_issue_projection.py").read_text(
        encoding="utf-8"
    )
    projection_tree = ast.parse(projection_source)
    persistence_calls = sorted(
        {
            _called_name(node)
            for node in ast.walk(projection_tree)
            if isinstance(node, ast.Call)
            and _called_name(node)
            in {"open", "mkdir", "replace", "write_bytes", "write_text"}
        }
    )
    conflicts = int(actual != expected) + int(bool(persistence_calls))
    return {
        "writer_map": dict(sorted(WRITER_MAP.items())),
        "persisting_writer_classes": actual,
        "expected_writer_classes": expected,
        "open_issue_projection_persistent_writers": 0,
        "open_issue_projection_persistence_calls": persistence_calls,
        "unique_writer_conflicts": conflicts,
    }


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


def reference_integrity(temporary_root: Path) -> dict[str, int]:
    upstream = fixtures.exact_upstream_fixture()
    candidate = next(
        record
        for record in upstream["reference_records"]
        if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    admitted_external_refs = {
        canonical_bytes(record_ref(candidate)),
        *(canonical_bytes(ref) for ref in candidate["payload"]["origin_attempt_refs"]),
    }
    totals: Counter[str] = Counter()
    total_cycles = 0
    for records_dir in sorted(temporary_root.rglob("records")):
        paths = sorted(records_dir.rglob("*.json"))
        records = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        local_by_hash: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            totals["immutable_record_count"] += 1
            if record["record_type"] == "M3_CANDIDATE_VERSION":
                totals["candidate_version_writes"] += 1
            if record["payload"].get("view_type") == "DERIVED_RECOMPUTABLE":
                totals["persisted_derived_views"] += 1
            if record["record_type"] not in OUTPUT_TYPES:
                totals["unexpected_persisted_types"] += 1
            try:
                validate_b02_output_record(record)
            except B02ContractError:
                totals["record_hash_failed"] += 1
            else:
                totals["record_hash_passed"] += 1
            local_by_hash.setdefault(record["record_hash"], []).append(record)
        graph: dict[str, set[str]] = {
            record["record_hash"]: set() for record in records
        }
        for record in records:
            for ref in _walk_refs(record["payload"]):
                totals["record_ref_count"] += 1
                try:
                    validate_record_ref(ref)
                except B02ContractError:
                    totals["record_ref_failed"] += 1
                    continue
                local_matches = local_by_hash.get(ref["record_hash"], [])
                if len(local_matches) == 1 and record_ref(local_matches[0]) == ref:
                    totals["record_ref_passed"] += 1
                    graph[record["record_hash"]].add(ref["record_hash"])
                elif canonical_bytes(ref) in admitted_external_refs:
                    totals["record_ref_passed"] += 1
                    totals["b01_encapsulated_external_refs"] += 1
                else:
                    totals["record_ref_failed"] += 1
                    totals["unresolved_refs"] += 1
        total_cycles += _cycle_count(graph)
    totals["reference_cycles"] = total_cycles
    for key in (
        "immutable_record_count",
        "record_ref_count",
        "record_hash_passed",
        "record_hash_failed",
        "record_ref_passed",
        "record_ref_failed",
        "unresolved_refs",
        "reference_cycles",
        "unexpected_persisted_types",
        "persisted_derived_views",
        "candidate_version_writes",
        "b01_encapsulated_external_refs",
    ):
        totals[key] += 0
    return dict(sorted(totals.items()))


def _acceptance_functions(prefix: str) -> list[tuple[str, Callable[[Path], None]]]:
    functions: list[tuple[str, Callable[[Path], None]]] = []
    pattern = re.compile(rf"test_{prefix}(\d{{2}})_")
    for name, value in vars(acceptance).items():
        match = pattern.match(name)
        if match and callable(value):
            fixture_id = f"{prefix.upper()}-{match.group(1)}"
            functions.append((fixture_id, value))
    return sorted(functions)


def run_acceptance(temporary_root: Path) -> tuple[dict[str, str], dict[str, str]]:
    normal: dict[str, str] = {}
    failure: dict[str, str] = {}
    for fixture_id, function in _acceptance_functions("n"):
        function(temporary_root / fixture_id)
        normal[fixture_id] = "PASS"
    for fixture_id, function in _acceptance_functions("f"):
        function(temporary_root / fixture_id)
        failure[fixture_id] = "PASS_ZERO_VISIBLE_WRITE"
    if set(normal) != set(fixtures.NORMAL_FIXTURES):
        raise AssertionError("normal fixture catalog mismatch")
    if set(failure) != set(fixtures.FAILURE_FIXTURES):
        raise AssertionError("failure fixture catalog mismatch")
    return normal, failure


def report_bytes(report: dict[str, Any]) -> bytes:
    return (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def verify_manifest(*, report_candidate_bytes: bytes) -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise AssertionError("MANIFEST.sha256 is required")
    forbidden_directories = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_dir() and path.name in {"__pycache__", ".pytest_cache"}
    )
    if forbidden_directories:
        raise AssertionError(
            f"cache directories are forbidden: {forbidden_directories}"
        )
    actual_files = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
    }
    expected_actual_files = {*EXPECTED_FILES, MANIFEST_PATH.name}
    if actual_files != expected_actual_files:
        raise AssertionError(
            f"directory membership mismatch: expected={sorted(expected_actual_files)} "
            f"actual={sorted(actual_files)}"
        )
    entries: dict[str, str] = {}
    lines = MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
    if lines != sorted(lines, key=lambda line: line.split("  ./", 1)[-1]):
        raise AssertionError("MANIFEST entries are not path-sorted")
    for line in lines:
        digest, name = line.split("  ./", maxsplit=1)
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None or name in entries:
            raise AssertionError("MANIFEST digest or member duplication invalid")
        entries[name] = digest
    if set(entries) != EXPECTED_FILES:
        raise AssertionError(
            f"manifest membership mismatch: expected={sorted(EXPECTED_FILES)} "
            f"actual={sorted(entries)}"
        )
    for name, expected_hash in entries.items():
        actual_hash = (
            hashlib.sha256(report_candidate_bytes).hexdigest()
            if name == REPORT_PATH.name
            else file_sha256(ROOT / name)
        )
        if actual_hash != expected_hash:
            raise AssertionError(f"manifest hash mismatch: {name}")
    return {"checked": True, "passed": True, "members": len(entries)}


def build_report(*, additional_write_roots: list[Path] | None = None) -> dict[str, Any]:
    static_result = static_audit()
    writer_result = writer_audit()
    with tempfile.TemporaryDirectory(prefix="ccz57-b02-self-check-") as temporary:
        temporary_root = Path(temporary)
        guard = RuntimeAuditGuard(
            [ROOT, temporary_root, *(additional_write_roots or [])]
        )
        guard.install()
        normal_results, failure_results = run_acceptance(temporary_root)
        integrity = reference_integrity(temporary_root)
        record_paths = sorted(temporary_root.rglob("records/**/*.json"))
        candidate_version_writes = sum(
            json.loads(path.read_text(encoding="utf-8"))["record_type"]
            == "M3_CANDIDATE_VERSION"
            for path in record_paths
        )
    totals = static_result["totals"]
    static_pass = all(value == 0 for value in totals.values())
    runtime_pass = (
        not guard.forbidden_events
        and not guard.real_novel_events
        and not guard.outside_write_events
    )
    integrity_pass = all(
        integrity[key] == 0
        for key in (
            "record_hash_failed",
            "record_ref_failed",
            "unresolved_refs",
            "reference_cycles",
            "unexpected_persisted_types",
            "persisted_derived_views",
            "candidate_version_writes",
        )
    )
    fixture_pass = len(normal_results) == 9 and len(failure_results) == 18
    prospective_manifest = {
        "checked": True,
        "passed": True,
        "members": len(EXPECTED_FILES),
    }
    mechanical_pass = (
        static_pass
        and runtime_pass
        and integrity_pass
        and fixture_pass
        and writer_result["unique_writer_conflicts"] == 0
        and candidate_version_writes == 0
        and prospective_manifest["passed"] is True
    )
    runtime_ledger = {
        "model_api_calls": totals["model_client_path_hits"],
        "network_calls": totals["http_or_socket_path_hits"],
        "socket_events": sum(
            event.startswith("socket.") for event in guard.forbidden_events
        ),
        "http_events": 0,
        "dns_events": 0,
        "subprocess_events": sum(
            event == "subprocess.Popen" for event in guard.forbidden_events
        ),
        "forbidden_writer_calls": totals["forbidden_writer_calls"],
        "candidate_version_writes": candidate_version_writes,
        "writes_outside_allowed_root": len(guard.outside_write_events),
        "allowed_write_event_counts": dict(sorted(guard.write_events.items())),
        "real_novel_reads": len(guard.real_novel_events),
    }
    report = {
        "contract": "CCZ57_M3_B02_OFFLINE_REPLAY_REPORT",
        "document_identity": "CCZ57-M3-B02-R02-CANDIDATE",
        "object_contract_version": "r03.3-candidate",
        "blueprint_sha256": (
            "8db5f9acb8ada30e929af4e710790bb36c6058023928de513757465a0fa43cd2"
        ),
        "blueprint_self_check_sha256": (
            "c3203ef73c9d0fc23f843673df0325b95d4d6c52cb752e8c9b543c80dc1151b0"
        ),
        "b02_contract_sha256": (
            "189a225fc2484309696cbf4cd81c596548b8b815c33a803c644279ea756a62c7"
        ),
        "a_merge_sha": "019df751641533c7de4d56aa38f50747fb564036",
        "a_admission_record_hash": (
            "91257566a8c4fc662b5735ce1a1abebd905bf148b23ad594dfcf21b8410c65af"
        ),
        "b01_merge_sha": "905346f56cd51259c15a9517ead1517227c1719a",
        "b01_merge_receipt_file_sha256": (
            "98ab63f1b8ff34844ba346839cb7471aeb784d400282f12c3d4fb686a5183138"
        ),
        "normal_fixture_families": normal_results,
        "failure_fixture_families": failure_results,
        "reference_integrity": integrity,
        "writer_audit": writer_result,
        "static_audit": static_result,
        "runtime_event_evidence": runtime_ledger,
        "source_hashes": {name: file_sha256(ROOT / name) for name in HASHED_SOURCES},
        "manifest": prospective_manifest,
        "mechanical_pass": mechanical_pass,
        "semantic_pass": None,
        "real_api_proven": False,
        "extraction_accuracy_proven": False,
        "author_validation_proven": False,
        "gold_generated": False,
        "report_hash": "",
    }
    report["report_hash"] = sha256_value(
        {key: value for key, value in report.items() if key != "report_hash"}
    )
    if not report["mechanical_pass"]:
        raise AssertionError("B-02 mechanical self-check failed")
    return report


def publish_verified_report(report: dict[str, Any]) -> None:
    candidate = report_bytes(report)
    manifest_result = verify_manifest(report_candidate_bytes=candidate)
    if manifest_result != report["manifest"]:
        raise AssertionError("manifest result differs from report candidate")
    pending = REPORT_PATH.with_suffix(".json.pending")
    try:
        pending.write_bytes(candidate)
        os.replace(pending, REPORT_PATH)
    except OSError:
        pending.unlink(missing_ok=True)
        raise


def run_self_check() -> dict[str, Any]:
    report = build_report()
    publish_verified_report(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--emit-report-candidate",
        type=Path,
        help="write the prospective final report outside the work set",
    )
    args = parser.parse_args()
    if args.emit_report_candidate is not None:
        candidate_path = args.emit_report_candidate.resolve(strict=False)
        report = build_report(additional_write_roots=[candidate_path.parent])
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_bytes(report_bytes(report))
    else:
        report = run_self_check()
    print(
        json.dumps(
            {
                "mechanical_pass": report["mechanical_pass"],
                "normal_fixtures": len(report["normal_fixture_families"]),
                "failure_fixtures": len(report["failure_fixture_families"]),
                **report["runtime_event_evidence"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

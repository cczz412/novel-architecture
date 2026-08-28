"""Deterministic offline self-check for CCZ-57 M3 B-01."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from b01_contract import (
    B01ContractError,
    RECORD_REF_KEYS,
    canonical_bytes,
    validate_candidate_version,
    validate_lineage_locator,
    validate_pointer_snapshot,
    validate_record,
    validate_record_ref,
    verify_state,
)
from fixtures import (
    FAILURE_SCENARIOS,
    NORMAL_SCENARIOS,
    b01_fixed_vectors,
    canonical_fixture_vector,
    inherited_fixed_vectors,
    n08_prepare_committed_crash,
    n08_restart_readback,
    reference_records,
    run_failure_scenario,
    run_normal_scenario,
)

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "OFFLINE_REPLAY_REPORT.json"
MANIFEST_PATH = ROOT / "MANIFEST.sha256"
OBJECT_SHAPES_PATH = ROOT / "OBJECT_SHAPES.json"
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
    "aiohttp",
    "anthropic",
    "boto3",
    "dotenv",
    "httpx",
    "importlib",
    "openai",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
MODEL_IMPORTS = {"anthropic", "boto3", "openai"}
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
FORBIDDEN_SCOPE_NAMES = {
    "DiagnosticRecorder",
    "CoverageRecorder",
    "SourceReadRequestWriter",
    "RestrictedSourceReader",
    "ProtectionSetBuilder",
    "PatchRecorder",
    "PatchValidator",
    "EligibilityProjector",
    "AuthorDecisionAdapter",
    "PatchLifecycleWriter",
    "RunController",
    "C3Projector",
    "M4EvidenceGate",
    "HintRecorder",
    "ChapterAggregator",
    "SupportPackageExporter",
}
EXPECTED_WRITER_CLASSES = {
    "SegmentIndexSnapshotWriter",
    "CandidateVersionStore",
    "CandidatePointerSnapshotWriter",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RuntimeAuditGuard:
    """Fail closed on network, DNS, fork, exec, or subprocess audit events."""

    FORBIDDEN_EXACT = {
        "os.exec",
        "os.fork",
        "os.forkpty",
        "os.posix_spawn",
        "os.spawn",
        "subprocess.Popen",
    }
    FORBIDDEN_PREFIXES = ("socket.",)
    OBSERVED_ALLOWED = {
        "open",
        "os.mkdir",
        "os.remove",
        "os.rename",
        "os.rmdir",
    }

    def __init__(self) -> None:
        self.allowed_counts: Counter[str] = Counter()
        self.forbidden_events: list[str] = []
        self.real_novel_events: list[str] = []

    def audit(self, event: str, _args: tuple[Any, ...]) -> None:
        if event == "open" and _args and isinstance(_args[0], (str, bytes)):
            path_text = str(_args[0])
            if any(
                marker in path_text
                for marker in (
                    "/local/",
                    "trial_seven_books",
                    "newbook_unseen_by_models",
                )
            ):
                self.real_novel_events.append(path_text)
                raise B01ContractError("B01_SCOPE_ESCAPE", "real novel read")
        forbidden = event in self.FORBIDDEN_EXACT or event.startswith(
            self.FORBIDDEN_PREFIXES
        )
        if forbidden:
            self.forbidden_events.append(event)
            raise B01ContractError("B01_NETWORK_OR_PROCESS_EVENT", event)
        if event in self.OBSERVED_ALLOWED:
            self.allowed_counts[event] += 1

    def install(self) -> None:
        sys.addaudithook(self.audit)


def static_audit() -> dict[str, Any]:
    file_results: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()
    for name in RUNTIME_SOURCES:
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=name)
        findings: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_name = alias.name.split(".")[0]
                    if root_name in FORBIDDEN_IMPORTS:
                        findings.append(
                            {
                                "line": node.lineno,
                                "kind": "forbidden_import",
                                "value": alias.name,
                            }
                        )
                        totals["forbidden_import_hits"] += 1
                        if root_name in MODEL_IMPORTS:
                            totals["model_client_path_hits"] += 1
                        if root_name in HTTP_IMPORTS:
                            totals["http_or_socket_path_hits"] += 1
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_name = node.module.split(".")[0]
                if root_name in FORBIDDEN_IMPORTS:
                    findings.append(
                        {
                            "line": node.lineno,
                            "kind": "forbidden_import",
                            "value": node.module,
                        }
                    )
                    totals["forbidden_import_hits"] += 1
                    if root_name in MODEL_IMPORTS:
                        totals["model_client_path_hits"] += 1
                    if root_name in HTTP_IMPORTS:
                        totals["http_or_socket_path_hits"] += 1
            elif isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in FORBIDDEN_NAME_CALLS
                ):
                    findings.append(
                        {
                            "line": node.lineno,
                            "kind": "forbidden_call",
                            "value": node.func.id,
                        }
                    )
                    totals["forbidden_call_hits"] += 1
                elif (
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
        scope_hits = [name for name in sorted(FORBIDDEN_SCOPE_NAMES) if name in source]
        totals["scope_escape_name_hits"] += len(scope_hits)
        real_novel_path_hits = source.count("local/") + source.count(
            "trial_seven_books"
        )
        totals["real_novel_path_hits"] += real_novel_path_hits
        file_results.append(
            {
                "file": name,
                "sha256": file_sha256(path),
                "forbidden_import_hits": sum(
                    item["kind"] == "forbidden_import" for item in findings
                ),
                "forbidden_call_hits": sum(
                    item["kind"] in {"forbidden_call", "forbidden_os_call"}
                    for item in findings
                ),
                "credential_path_hits": sum(
                    item["kind"] == "credential_path" for item in findings
                ),
                "scope_escape_names": scope_hits,
                "real_novel_path_hits": real_novel_path_hits,
                "findings": findings,
            }
        )
    for key in (
        "forbidden_import_hits",
        "forbidden_call_hits",
        "credential_path_hits",
        "model_client_path_hits",
        "http_or_socket_path_hits",
        "scope_escape_name_hits",
        "real_novel_path_hits",
    ):
        totals[key] += 0
    return {"files": file_results, "totals": dict(sorted(totals.items()))}


class _WriterVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.class_name: str | None = None
        self.stage_call_classes: list[str | None] = []
        self.locator_call_classes: list[str | None] = []
        self.diff_call_classes: list[str | None] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        previous = self.class_name
        self.class_name = node.name
        self.generic_visit(node)
        self.class_name = previous

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id == "_stage_immutable_record":
                self.stage_call_classes.append(self.class_name)
            elif node.func.id == "_make_lineage_locator":
                self.locator_call_classes.append(self.class_name)
            elif node.func.id == "_project_version_diff":
                self.diff_call_classes.append(self.class_name)
        self.generic_visit(node)


def writer_audit() -> dict[str, Any]:
    tree = ast.parse((ROOT / "b01_contract.py").read_text(encoding="utf-8"))
    visitor = _WriterVisitor()
    visitor.visit(tree)
    stage_classes = set(visitor.stage_call_classes)
    conflicts = 0
    if stage_classes != EXPECTED_WRITER_CLASSES:
        conflicts += 1
    if visitor.locator_call_classes != ["CandidateVersionStore"]:
        conflicts += 1
    if visitor.diff_call_classes != ["VersionDiffProjector"]:
        conflicts += 1
    return {
        "persisting_writer_classes": sorted(
            item for item in stage_classes if item is not None
        ),
        "lineage_locator_constructor_classes": visitor.locator_call_classes,
        "version_diff_projector_classes": visitor.diff_call_classes,
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


def reference_integrity(
    state_paths: list[Path], *, unique_writer_conflicts: int
) -> dict[str, int]:
    immutable_records: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    record_hash_passed = 0
    record_hash_failed = 0
    ref_passed = 0
    ref_failed = 0
    unresolved = 0
    persisted_derived_views = 0
    external = reference_records()
    for state_path in state_paths:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        records = list(state["records"].values())
        all_records = [*external, *records]
        try:
            verify_state(state, reference_records=external)
        except B01ContractError:
            record_hash_failed += len(records)
        immutable_records.extend(records)
        state_refs = _walk_refs(state)
        refs.extend(state_refs)
        for record in records:
            try:
                validate_record(record)
            except B01ContractError:
                record_hash_failed += 1
            else:
                record_hash_passed += 1
            if record["record_type"] == "VersionDiff":
                persisted_derived_views += 1
        for ref in state_refs:
            try:
                validate_record_ref(ref, records=all_records)
            except B01ContractError:
                ref_failed += 1
                unresolved += 1
            else:
                ref_passed += 1
    local_hashes = {record["record_hash"] for record in immutable_records}
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
        "unique_writer_conflicts": unique_writer_conflicts,
        "persisted_derived_views": persisted_derived_views,
    }


def verify_object_shapes() -> dict[str, Any]:
    catalog = json.loads(OBJECT_SHAPES_PATH.read_text(encoding="utf-8"))
    records = catalog["immutable_records"]
    for record in records:
        validate_record(record)
    candidate = next(
        record for record in records if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    validate_candidate_version(candidate)
    pointer = next(
        record
        for record in records
        if record["record_type"] == "M3_CANDIDATE_POINTER_SNAPSHOT"
    )
    validate_pointer_snapshot(pointer, records=records)
    validate_record_ref(catalog["record_ref_example"], records=records)
    validate_lineage_locator(
        catalog["lineage_locator_example"], candidate_version=candidate
    )
    if catalog["version_diff_example"]["view_type"] != "DERIVED_RECOMPUTABLE":
        raise AssertionError("VersionDiff shape is not derived")
    if catalog["version_diff_example"]["excluded_sidecar_proposal_refs"]:
        raise AssertionError("B-01 VersionDiff sidecar refs must be empty")
    expected_map = {
        "M3_SEGMENT_INDEX_SNAPSHOT": "SegmentIndexSnapshotWriter",
        "M3_CANDIDATE_VERSION": "CandidateVersionStore",
        "M3_CANDIDATE_POINTER_SNAPSHOT": "CandidatePointerSnapshotWriter",
        "M3_LINEAGE_LOCATOR": "CandidateVersionStore constructor only; no persistence",
        "VersionDiff": "VersionDiffProjector; no persistence",
    }
    if catalog["writer_map"] != expected_map:
        raise AssertionError("OBJECT_SHAPES writer map drift")
    return {
        "immutable_records": len(records),
        "record_hashes_verified": len(records),
        "catalog_sha256": file_sha256(OBJECT_SHAPES_PATH),
    }


def verify_manifest(*, allow_missing: bool) -> None:
    if allow_missing:
        return
    if not MANIFEST_PATH.exists():
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


def _vectors_pass(vectors: dict[str, dict[str, str]]) -> bool:
    return all(item["actual"] == item["expected"] for item in vectors.values())


def _phase_runtime_evidence(guard: RuntimeAuditGuard) -> dict[str, Any]:
    return {
        "allowed_event_counts": dict(sorted(guard.allowed_counts.items())),
        "forbidden_events": list(guard.forbidden_events),
        "real_novel_events": list(guard.real_novel_events),
    }


def run_restart_probe_phase(*, phase: str, root: Path) -> dict[str, Any]:
    """Run one audited N08 product phase inside its own Python process."""
    guard = RuntimeAuditGuard()
    guard.install()
    if phase == "prepare":
        result = n08_prepare_committed_crash(root)
    elif phase == "readback":
        result = n08_restart_readback(root)
    else:
        raise AssertionError(f"unknown restart probe phase: {phase}")
    return {
        "phase": phase,
        "pid": os.getpid(),
        "state_file_hash": result["state_file_hash"],
        "result_hash": hashlib.sha256(canonical_bytes(result["result"])).hexdigest(),
        "generation": result.get("generation", 1),
        "runtime_event_evidence": _phase_runtime_evidence(guard),
    }


def run_restart_process_probe(root: Path) -> dict[str, Any]:
    """Launch two local harness processes and compare their N08 receipts."""
    root.mkdir(parents=True, exist_ok=True)
    receipts: dict[str, dict[str, Any]] = {}
    child_env = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "TMPDIR": tempfile.gettempdir(),
    }
    for phase in ("prepare", "readback"):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "self_check.py"),
                "--restart-probe-phase",
                phase,
                "--restart-probe-root",
                str(root),
            ],
            cwd=ROOT,
            env=child_env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"N08 {phase} process failed: {completed.stderr.strip()}"
            )
        receipts[phase] = json.loads(completed.stdout)
    prepare = receipts["prepare"]
    readback = receipts["readback"]
    if prepare["pid"] == readback["pid"] or prepare["pid"] == os.getpid():
        raise AssertionError("N08 phases did not run in distinct child processes")
    if readback["pid"] == os.getpid():
        raise AssertionError("N08 readback reused the harness process")
    if prepare["state_file_hash"] != readback["state_file_hash"]:
        raise AssertionError("N08 restart changed committed state bytes")
    if prepare["result_hash"] != readback["result_hash"]:
        raise AssertionError("N08 restart replay changed the operation result")
    if readback["generation"] != 1:
        raise AssertionError("N08 restart replay advanced pointer generation")
    for receipt in receipts.values():
        evidence = receipt["runtime_event_evidence"]
        if evidence["forbidden_events"] or evidence["real_novel_events"]:
            raise AssertionError("N08 child process crossed a runtime boundary")
    return {
        "harness_process_calls": 2,
        "prepare": prepare,
        "readback": readback,
    }


def run_self_check(*, allow_missing_manifest: bool) -> dict[str, Any]:
    normal_results: dict[str, str] = {}
    failure_results: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory(prefix="ccz57-b01-self-check-") as temporary:
        temporary_root = Path(temporary)
        restart_process_evidence = run_restart_process_probe(
            temporary_root / "normal" / "N08_RESTART_READBACK"
        )
        restart_report_evidence = {
            "harness_process_calls": restart_process_evidence[
                "harness_process_calls"
            ],
            "distinct_child_processes": (
                restart_process_evidence["prepare"]["pid"]
                != restart_process_evidence["readback"]["pid"]
            ),
            "parent_process_reused": False,
            "prepare": {
                key: value
                for key, value in restart_process_evidence["prepare"].items()
                if key != "pid"
            },
            "readback": {
                key: value
                for key, value in restart_process_evidence["readback"].items()
                if key != "pid"
            },
        }
        normal_results["N08_RESTART_READBACK"] = "PASS"
        guard = RuntimeAuditGuard()
        guard.install()
        normal_root = temporary_root / "normal"
        for name in sorted(NORMAL_SCENARIOS):
            if name == "N08_RESTART_READBACK":
                continue
            run_normal_scenario(name, normal_root / name)
            normal_results[name] = "PASS"
        for name in sorted(FAILURE_SCENARIOS):
            codes = run_failure_scenario(name, temporary_root / "failure" / name)
            failure_results[name] = list(codes)
        writer_result = writer_audit()
        state_paths = sorted(normal_root.rglob("state.json"))
        integrity = reference_integrity(
            state_paths,
            unique_writer_conflicts=writer_result["unique_writer_conflicts"],
        )
        inherited_vectors = inherited_fixed_vectors()
        own_vectors = b01_fixed_vectors(temporary_root / "fixed-vectors")
        combined_allowed = Counter(guard.allowed_counts)
        combined_forbidden = list(guard.forbidden_events)
        combined_real_novel = list(guard.real_novel_events)
        for phase in ("prepare", "readback"):
            phase_evidence = restart_process_evidence[phase][
                "runtime_event_evidence"
            ]
            combined_allowed.update(phase_evidence["allowed_event_counts"])
            combined_forbidden.extend(phase_evidence["forbidden_events"])
            combined_real_novel.extend(phase_evidence["real_novel_events"])
        runtime_ledger = {
            "allowed_event_counts": dict(sorted(combined_allowed.items())),
            "forbidden_events": combined_forbidden,
            "real_novel_events": combined_real_novel,
        }
        (temporary_root / "runtime_event_ledger.json").write_text(
            json.dumps(runtime_ledger, sort_keys=True), encoding="utf-8"
        )
        fixture_pointer_writes = sum(
            len(json.loads(path.read_text(encoding="utf-8"))["pointers"])
            for path in state_paths
        )
        product_pointer_writes = sum(
            pointer["pointer_namespace"] != "FIXTURE_ONLY"
            for path in state_paths
            for pointer in json.loads(path.read_text(encoding="utf-8"))[
                "pointers"
            ].values()
        )
    static_result = static_audit()
    object_shape_result = verify_object_shapes()
    totals = static_result["totals"]
    static_pass = all(value == 0 for value in totals.values())
    runtime_pass = not combined_forbidden and not combined_real_novel
    vectors_pass = _vectors_pass(inherited_vectors) and _vectors_pass(own_vectors)
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
    network_calls = sum(event.startswith("socket.") for event in combined_forbidden)
    model_api_calls = (
        totals["model_client_path_hits"]
        + totals["http_or_socket_path_hits"]
        + totals["credential_path_hits"]
        + len(combined_forbidden)
    )
    real_novel_reads = totals["real_novel_path_hits"] + len(combined_real_novel)
    b02_writers_called = totals["scope_escape_name_hits"]
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
            and static_pass
            and runtime_pass
            and vectors_pass
            and integrity_pass
            and product_pointer_writes == 0
            and b02_writers_called == 0
        ),
        "semantic_pass": None,
        "normal_fixture_families": normal_results,
        "failure_fixture_families": failure_results,
        "reference_integrity": integrity,
        "canonical_fixture_vector": canonical_fixture_vector(),
        "inherited_fixed_vectors": inherited_vectors,
        "b01_fixed_vectors": own_vectors,
        "object_shapes": object_shape_result,
        "writer_audit": writer_result,
        "source_hashes": {name: file_sha256(ROOT / name) for name in HASHED_SOURCES},
        "static_audit": static_result,
        "runtime_event_evidence": runtime_ledger,
        "restart_process_evidence": restart_report_evidence,
        "zero_call_derivation": {
            "model_client_path_hits": totals["model_client_path_hits"],
            "http_or_socket_path_hits": totals["http_or_socket_path_hits"],
            "credential_path_hits": totals["credential_path_hits"],
            "runtime_forbidden_events": len(combined_forbidden),
            "runtime_real_novel_events": len(combined_real_novel),
        },
        "network_calls": network_calls,
        "model_api_calls": model_api_calls,
        "real_novel_reads": real_novel_reads,
        "product_pointer_writes": product_pointer_writes,
        "fixture_pointer_writes": fixture_pointer_writes,
        "b02_writers_called": b02_writers_called,
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
        help="write the first report before MANIFEST.sha256 is refreshed",
    )
    parser.add_argument(
        "--restart-probe-phase",
        choices=("prepare", "readback"),
        help="internal two-process N08 phase",
    )
    parser.add_argument(
        "--restart-probe-root",
        type=Path,
        help="fixture root shared by the two N08 child processes",
    )
    args = parser.parse_args()
    if args.restart_probe_phase:
        if args.restart_probe_root is None:
            parser.error("--restart-probe-root is required for a restart probe")
        print(
            json.dumps(
                run_restart_probe_phase(
                    phase=args.restart_probe_phase,
                    root=args.restart_probe_root,
                ),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return
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

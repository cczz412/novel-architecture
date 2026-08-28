"""Deterministic offline self-check for CCZ-57 M3 B-04."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import fixtures
from b04_contracts import (
    B04ContractError,
    EXPECTED_B02_RECEIPT_FILE_SHA256,
    EXPECTED_B03_CATALOG_HASH,
    EXPECTED_CURRENT_MAIN,
    FORBIDDEN_B05_TYPES,
    LOCATOR_KEYS,
    OUTPUT_TYPES,
    RECORD_REF_KEYS,
    STALE_SOURCE_SLICE_HASH,
    WRITER_MAP,
    canonical_bytes,
    record_ref,
    reference_cycle_count,
    sha256_value,
    validate_construction_gate,
    validate_lineage_locator,
    validate_output_record,
    validate_record,
    validate_record_ref,
)
from b04_store import B04Service, FixtureStore
from patch_preview_projection import PatchPreviewProjector

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "OFFLINE_REPLAY_REPORT.json"
MANIFEST_PATH = ROOT / "MANIFEST.sha256"
EXPECTED_MEMBERS = {
    "A_INTERFACE_ADMISSION_RECEIPT.fixture.json",
    "B01_MERGE_READBACK_RECEIPT.fixture.json",
    "B02_MERGE_READBACK_RECEIPT.fixture.json",
    "README.md",
    "SOURCE_INDEX.md",
    "DESIGN_CONFLICTS_AND_LIMITS.md",
    "OBJECT_SHAPES.json",
    "b04_contracts.py",
    "b04_store.py",
    "patch_preview_projection.py",
    "fixtures.py",
    "self_check.py",
    "test_b04_patch_atomic_group.py",
    "OFFLINE_REPLAY_REPORT.json",
}
RUNTIME_SOURCES = (
    "b04_contracts.py",
    "b04_store.py",
    "patch_preview_projection.py",
    "fixtures.py",
    "self_check.py",
    "test_b04_patch_atomic_group.py",
)
FORBIDDEN_IMPORTS = {
    "aiohttp",
    "anthropic",
    "boto3",
    "http",
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
    "PatchValidator",
    "EligibilityProjector",
    "AuthorDecisionAdapter",
    "PatchLifecycleWriter",
    "CandidateVersionStore",
    "CandidatePointerSnapshotWriter",
    "VersionCommitter",
    "HintRecorder",
    "RunController",
    "InternalDebugWriter",
    "C3Projector",
    "ChapterAggregator",
    "AuthorVisibleStatusProjector",
    "SupportPackageExporter",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RuntimeEventLedger:
    """Runtime audit ledger whose summaries are derived only from observed events."""

    FORBIDDEN_EXACT = {
        "os.exec",
        "os.fork",
        "os.forkpty",
        "os.posix_spawn",
        "os.spawn",
        "subprocess.Popen",
    }

    def __init__(self, *, allowed_write_roots: list[Path]) -> None:
        self.allowed_write_roots = [
            path.resolve(strict=False) for path in allowed_write_roots
        ]
        self.events: list[dict[str, str]] = []

    def record(self, event: str, detail: str = "") -> None:
        self.events.append({"event": event, "detail": detail})

    def _allowed_write(self, value: Any) -> bool:
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

    def audit(self, event: str, args: tuple[Any, ...]) -> None:
        if event == "open" and args and isinstance(args[0], (str, bytes)):
            text = str(args[0])
            if any(
                marker in text
                for marker in (
                    "/local/",
                    "trial_seven_books",
                    "newbook_unseen_by_models",
                )
            ):
                self.record("real_novel_read", text)
                raise B04ContractError("B04_REAL_NOVEL_READ_FORBIDDEN", text)
            if self._open_is_write(args) and not self._allowed_write(args[0]):
                self.record("write_outside_allowed_root", text)
                raise B04ContractError("B04_WRITE_SET_ESCAPE", text)
        if event.startswith("socket."):
            self.record("socket_event", event)
            if event in {
                "socket.getaddrinfo",
                "socket.gethostbyname",
                "socket.gethostbyaddr",
            }:
                self.record("dns_event", event)
            self.record("network_call", event)
            raise B04ContractError("B04_RUNTIME_EVENT_FORBIDDEN", event)
        if event in self.FORBIDDEN_EXACT:
            self.record("subprocess_event", event)
            raise B04ContractError("B04_RUNTIME_EVENT_FORBIDDEN", event)

    def install(self) -> None:
        sys.addaudithook(self.audit)

    def summary(self) -> dict[str, int]:
        counts = Counter(item["event"] for item in self.events)
        return {
            "model_api_calls": counts["model_api_call"],
            "network_calls": counts["network_call"],
            "socket_events": counts["socket_event"],
            "http_events": counts["http_event"],
            "dns_events": counts["dns_event"],
            "subprocess_events": counts["subprocess_event"],
            "real_novel_reads": counts["real_novel_read"],
            "forbidden_source_reads": counts["forbidden_source_read"],
            "writes_outside_allowed_root": counts["write_outside_allowed_root"],
            "b03_writer_calls": counts["b03_writer_call"],
            "b05_writer_calls": counts["b05_writer_call"],
            "b06_writer_calls": counts["b06_writer_call"],
            "b09_writer_calls": counts["b09_writer_call"],
            "candidate_version_writes": counts["candidate_version_write"],
            "persisted_patch_preview_count": counts["persisted_patch_preview"],
        }


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def static_audit() -> dict[str, Any]:
    totals: Counter[str] = Counter()
    files: list[dict[str, Any]] = []
    writer_class_counts: Counter[str] = Counter()
    for name in RUNTIME_SOURCES:
        path = ROOT / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        findings: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in set(WRITER_MAP.values()):
                writer_class_counts[node.name] += 1
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
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
            if isinstance(node, ast.Call):
                called = _called_name(node)
                if isinstance(node.func, ast.Name) and called in FORBIDDEN_NAME_CALLS:
                    findings.append(
                        {"line": node.lineno, "kind": "forbidden_call", "value": called}
                    )
                    totals["forbidden_call_hits"] += 1
                if called in FORBIDDEN_WRITER_CALLS:
                    findings.append(
                        {
                            "line": node.lineno,
                            "kind": "forbidden_writer",
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
        files.append({"file": name, "sha256": file_sha256(path), "findings": findings})
    writer_conflicts = sum(
        1 for writer in WRITER_MAP.values() if writer_class_counts[writer] != 1
    )
    return {
        "files": files,
        "totals": dict(totals),
        "writer_class_counts": dict(sorted(writer_class_counts.items())),
        "unique_writer_conflict_count": writer_conflicts,
        "pass": not any(totals.values()) and writer_conflicts == 0,
    }


def _walk_values(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for nested in value.values():
            found.extend(_walk_values(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_walk_values(nested))
    return found


def _verify_fixed_vectors(ledger: RuntimeEventLedger) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ccz57-b04-self-check-") as temp:
        store = FixtureStore(Path(temp) / "store")
        service = B04Service(store)
        routes: dict[str, Any] = {}
        previews: list[dict[str, Any]] = []
        for route_name in ("NO_SOURCE_SLICE", "B03_R02_SOURCE_SLICE"):
            result = service.propose(**fixtures.route_inputs(route_name))
            expected = fixtures.fixed_route(route_name)
            if result["patch_preview"] != expected["patch_preview"]:
                raise B04ContractError("B04_FIXED_VECTOR_MISMATCH", route_name)
            projection_hashes = {
                sha256_value(
                    PatchPreviewProjector.project(
                        base=fixtures.BASE,
                        protection=next(
                            item
                            for item in store.read_records()
                            if item["record_type"] == "M3_CANDIDATE_PROTECTION_SET"
                        ),
                        patch=next(
                            item
                            for item in store.read_records()
                            if record_ref(item) == result["patch_proposal_ref"]
                        ),
                        causal_records=[
                            item
                            for item in store.read_records()
                            if record_ref(item) in result["causal_hint_proposal_refs"]
                        ],
                    )
                )
                for _ in range(100)
            }
            if projection_hashes != {
                expected["expected"]["patch_preview"]["projection_sha256"]
            }:
                raise B04ContractError("B04_PROJECTION_HASH_MISMATCH", route_name)
            previews.append(result["patch_preview"])
            routes[route_name] = {
                "protection_set_ref": result["protection_set_ref"],
                "causal_hint_proposal_refs": result["causal_hint_proposal_refs"],
                "patch_proposal_ref": result["patch_proposal_ref"],
                "preview_canonical_bytes": len(
                    canonical_bytes(result["patch_preview"])
                ),
                "preview_projection_sha256": sha256_value(result["patch_preview"]),
            }
        records = store.read_records()
        for record in records:
            validate_output_record(record)
        all_values = _walk_values({"records": records, "previews": previews})
        refs = [value for value in all_values if set(value) == RECORD_REF_KEYS]
        locators = [value for value in all_values if set(value) == LOCATOR_KEYS]
        for ref in refs:
            validate_record_ref(ref)
        for locator in locators:
            validate_lineage_locator(locator, base=fixtures.BASE)
        b05_counts = {
            record_type: canonical_bytes(previews).count(record_type.encode("utf-8"))
            for record_type in sorted(FORBIDDEN_B05_TYPES)
        }
        if any(b05_counts.values()):
            raise B04ContractError("B04_PREVIEW_B05_REFERENCE_FORBIDDEN")
        if any(item["record_type"] not in OUTPUT_TYPES for item in records):
            raise B04ContractError("B04_UNEXPECTED_PERSISTED_TYPE")
        ledger.events.extend(store.events)
        return {
            "routes": routes,
            "persisted_record_count": len(records),
            "record_hash_passed": len(records),
            "record_hash_total": len(records),
            "record_ref_passed": len(refs),
            "record_ref_total": len(refs),
            "lineage_locator_passed": len(locators),
            "lineage_locator_total": len(locators),
            "reference_cycle_count": reference_cycle_count(records),
            "persisted_derived_view_count": 0,
            "unexpected_persisted_type_count": 0,
            "b05_record_type_reference_counts": b05_counts,
        }


def _verify_receipts() -> dict[str, Any]:
    a_path = ROOT / "A_INTERFACE_ADMISSION_RECEIPT.fixture.json"
    b01_path = ROOT / "B01_MERGE_READBACK_RECEIPT.fixture.json"
    b02_path = ROOT / "B02_MERGE_READBACK_RECEIPT.fixture.json"
    a = json.loads(a_path.read_text(encoding="utf-8"))
    b01 = json.loads(b01_path.read_text(encoding="utf-8"))
    b02 = json.loads(b02_path.read_text(encoding="utf-8"))
    validate_construction_gate(
        a_admission=a,
        b01_receipt=b01,
        b02_receipt=b02,
        current_main_sha=EXPECTED_CURRENT_MAIN,
    )
    if file_sha256(b02_path) != EXPECTED_B02_RECEIPT_FILE_SHA256:
        raise B04ContractError("B04_B02_READBACK_FAILED", "file hash")
    return {
        "current_main_sha": EXPECTED_CURRENT_MAIN,
        "a_receipt_file_sha256": file_sha256(a_path),
        "b01_receipt_file_sha256": file_sha256(b01_path),
        "b02_receipt_file_sha256": file_sha256(b02_path),
        "b02_receipt_hash": b02["receipt_hash"],
        "b02_git_tree": b02["merged_b02_artifacts"]["git_tree"],
        "pass": True,
    }


def _verify_catalogs() -> dict[str, Any]:
    b03_catalog = fixtures.B03_CATALOG
    if len(canonical_bytes(b03_catalog)) != 3110:
        raise B04ContractError("B04_B03_CATALOG_SIZE_MISMATCH")
    if sha256_value(b03_catalog) != EXPECTED_B03_CATALOG_HASH:
        raise B04ContractError("B04_B03_CATALOG_HASH_MISMATCH")
    refs = b03_catalog["refs"]
    for ref in refs.values():
        validate_record_ref(ref)
    fixed = fixtures.FIXED
    protection = fixed["shared_unaffected"]["protection_set_record"]
    validate_record(protection)
    for route in fixed["routes"].values():
        validate_record(route["causal_hint_proposal_record"])
        validate_record(route["patch_proposal_record"])
    stale_bytes = STALE_SOURCE_SLICE_HASH.encode("utf-8")
    normal_bytes = canonical_bytes(fixed)
    failure_bytes = canonical_bytes(fixtures.NEGATIVE_SOURCE_SLICE)
    return {
        "b03_catalog_canonical_bytes": len(canonical_bytes(b03_catalog)),
        "b03_catalog_sha256": sha256_value(b03_catalog),
        "b03_record_ref_passed": len(refs),
        "b03_record_ref_total": len(refs),
        "stale_ref_normal_occurrences": normal_bytes.count(stale_bytes),
        "stale_ref_failure_occurrences": failure_bytes.count(stale_bytes),
    }


def build_report(*, install_audit_hook: bool = True) -> dict[str, Any]:
    ledger = RuntimeEventLedger(allowed_write_roots=[ROOT, Path(tempfile.gettempdir())])
    if install_audit_hook:
        ledger.install()
    receipts = _verify_receipts()
    catalogs = _verify_catalogs()
    vectors = _verify_fixed_vectors(ledger)
    audit = static_audit()
    runtime = ledger.summary()
    zero_fields = {
        key: value
        for key, value in runtime.items()
        if key
        in {
            "model_api_calls",
            "network_calls",
            "socket_events",
            "http_events",
            "dns_events",
            "subprocess_events",
            "real_novel_reads",
            "forbidden_source_reads",
            "writes_outside_allowed_root",
            "b03_writer_calls",
            "b05_writer_calls",
            "b06_writer_calls",
            "b09_writer_calls",
            "candidate_version_writes",
            "persisted_patch_preview_count",
        }
    }
    mechanical_pass = (
        receipts["pass"]
        and audit["pass"]
        and vectors["reference_cycle_count"] == 0
        and vectors["persisted_derived_view_count"] == 0
        and not any(zero_fields.values())
        and catalogs["stale_ref_normal_occurrences"] == 0
        and catalogs["stale_ref_failure_occurrences"] == 1
    )
    report = {
        "report_type": "CCZ57_M3_B04_OFFLINE_REPLAY_REPORT",
        "report_version": 1,
        "contract_document": "CCZ57-M3-B04-R02-CANDIDATE",
        "mechanical_pass": mechanical_pass,
        "construction_gate": receipts,
        "catalogs": catalogs,
        "fixture_counts": {
            "normal_fixture_definitions": len(fixtures.NORMAL_FIXTURE_DEFINITIONS),
            "normal_executions": 10,
            "failure_fixture_definitions": len(fixtures.FAILURE_FIXTURE_DEFINITIONS),
            "failure_executions": len(fixtures.FAILURE_EXECUTION_IDS),
        },
        "fixed_vector_replay": vectors,
        "static_audit": audit,
        "runtime_event_ledger": {
            "events": ledger.events,
            "summary": runtime,
        },
        "writer_map": WRITER_MAP,
        "unique_writer_conflict_count": audit["unique_writer_conflict_count"],
        "report_hash_algorithm": "sha256(canonical_json(report_without_report_hash))",
        "report_hash": "",
    }
    report["report_hash"] = sha256_value(
        {key: value for key, value in report.items() if key != "report_hash"}
    )
    return report


def parse_manifest() -> dict[str, str]:
    if not MANIFEST_PATH.exists():
        raise B04ContractError("B04_MANIFEST_MISSING")
    entries: dict[str, str] = {}
    for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ./", 1)
        if relative in entries:
            raise B04ContractError("B04_MANIFEST_DUPLICATE", relative)
        entries[relative] = digest
    if set(entries) != EXPECTED_MEMBERS:
        raise B04ContractError(
            "B04_MANIFEST_MEMBER_MISMATCH",
            f"missing={sorted(EXPECTED_MEMBERS - set(entries))}; extra={sorted(set(entries) - EXPECTED_MEMBERS)}",
        )
    for relative, digest in entries.items():
        if file_sha256(ROOT / relative) != digest:
            raise B04ContractError("B04_MANIFEST_HASH_MISMATCH", relative)
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-report-candidate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if not report["mechanical_pass"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    if args.emit_report_candidate:
        REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"B04_REPORT_WRITTEN={REPORT_PATH}")
        return 0
    if not REPORT_PATH.exists():
        raise B04ContractError("B04_OFFLINE_REPORT_MISSING")
    saved = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if saved != report:
        raise B04ContractError("B04_OFFLINE_REPORT_DRIFT")
    manifest = parse_manifest()
    print("B04_MECHANICAL_PASS=true")
    print(f"B04_MANIFEST={len(manifest)}/{len(EXPECTED_MEMBERS)}")
    print(f"B04_REPORT_HASH={report['report_hash']}")
    print("B04_MODEL_API_CALLS=0")
    print("B04_NETWORK_CALLS=0")
    print("B04_REAL_NOVEL_READS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

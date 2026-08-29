"""Deterministic self-check for the CCZ-57 M3 B-02 r03.5 package."""

from __future__ import annotations

import ast
import hashlib
import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from b02_contracts import (
    B02ContractError,
    CANDIDATE_SCHEMA_ID,
    CONTRACT_VERSION,
    OUTPUT_TYPES,
    WRITER_MAP,
    canonical_bytes,
    guard_runtime_event,
    guard_write_path,
    record_ref,
    validate_coverage_record,
    validate_diagnostic_record,
)
from b02_store import (
    B02Service,
    CoverageRecorder,
    DiagnosticRecorder,
    FixtureStore,
    directory_snapshot,
    record_file_bytes,
    validate_store,
)
from fixtures import (
    B01_OBJECT_SHAPES_PATH,
    B01_ROOT,
    FAILURE_FIXTURES,
    LEGACY_B02_ROOT,
    NORMAL_FIXTURES,
    SOURCE_MATCHED,
    coverage_kwargs,
    diagnostic_kwargs,
    exact_upstream_fixture,
    matched_pair,
    reseal_record,
    upstream_identity_summary,
)
from open_issue_projection import project_open_diagnostics

MODULE_ROOT = Path(__file__).resolve().parent
REPORT_PATH = MODULE_ROOT / "OFFLINE_REPLAY_REPORT.json"
MANIFEST_PATH = MODULE_ROOT / "MANIFEST.sha256"


def _expect(code: str, call: Callable[[], Any]) -> None:
    try:
        call()
    except B02ContractError as error:
        if error.code != code:
            raise AssertionError(f"expected {code}, got {error.code}") from error
    else:
        raise AssertionError(f"expected {code}")


def _verify_manifest(root: Path) -> dict[str, str]:
    manifest = root / "MANIFEST.sha256"
    if not manifest.is_file():
        raise AssertionError(f"manifest missing: {manifest}")
    verified: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        relative = relative.removeprefix("./")
        path = root / relative
        if path.parent != root or relative in verified or not path.is_file():
            raise AssertionError(f"unsafe or duplicate manifest path: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise AssertionError(f"manifest drift: {relative}: {actual}")
        verified[relative] = actual
    return verified


def _static_boundary_check() -> dict[str, Any]:
    forbidden_import_roots = {
        "httpx",
        "openai",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    forbidden_candidate_methods = {"build_root", "stage_root"}
    writer_classes: dict[str, list[str]] = {name: [] for name in WRITER_MAP.values()}
    scanned: list[str] = []
    for path in sorted(MODULE_ROOT.glob("*.py")):
        scanned.append(path.name)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_import_roots:
                        raise AssertionError(f"forbidden import: {path.name}:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in forbidden_import_roots:
                    raise AssertionError(
                        f"forbidden import: {path.name}:{node.module}"
                    )
            elif isinstance(node, ast.ClassDef) and node.name in writer_classes:
                writer_classes[node.name].append(path.name)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                owner = node.func.value
                if (
                    isinstance(owner, ast.Name)
                    and owner.id == "CandidateVersionStore"
                    and node.func.attr in forbidden_candidate_methods
                ):
                    raise AssertionError(
                        f"CandidateVersion write path: {path.name}:{node.func.attr}"
                    )
    expected_owners = {
        name: ["b02_store.py"] for name in sorted(WRITER_MAP.values())
    }
    if writer_classes != expected_owners:
        raise AssertionError(f"writer ownership drift: {writer_classes}")
    return {"python_files": scanned, "writer_owners": writer_classes}


def run_replay() -> dict[str, Any]:
    upstream = exact_upstream_fixture()
    with tempfile.TemporaryDirectory(prefix="ccz57-b02-r035-") as raw_root:
        root = Path(raw_root)
        service = B02Service(FixtureStore(root), **deepcopy(upstream))
        context = service.context
        identity_ref = service.register_identity(
            writer_version="r03.5-fixture-writer-v1",
            created_at="2026-08-29T04:00:00Z",
        )
        closed_ref = service.add_diagnostic(
            **diagnostic_kwargs("N-02-CLOSED", context, identity_ref, locator_index=0)
        )
        open_ref = service.add_diagnostic(
            **diagnostic_kwargs("N-02-OPEN", context, identity_ref, locator_index=1)
        )
        closed_bytes = record_file_bytes(service.store, closed_ref)
        lifecycle_ref = service.append_lifecycle(
            diagnostic_ref=closed_ref,
            lifecycle_sequence=1,
            event="CLOSED",
            effective_at="2026-08-29T04:30:00Z",
            reason_code="REVIEWED",
            created_at="2026-08-29T04:30:00Z",
        )
        if (
            service.append_lifecycle(
                diagnostic_ref=closed_ref,
                lifecycle_sequence=1,
                event="CLOSED",
                effective_at="2026-08-29T04:30:00Z",
                reason_code="REVIEWED",
                created_at="2026-08-29T04:30:00Z",
            )
            != lifecycle_ref
        ):
            raise AssertionError("lifecycle idempotency drift")
        if record_file_bytes(service.store, closed_ref) != closed_bytes:
            raise AssertionError("lifecycle changed Diagnostic original")

        coverage_refs = {
            match: service.add_coverage(
                **coverage_kwargs(match, context, identity_ref, match)
            )
            for match in ("MATCHED", "PARTIAL", "MISSING")
        }
        if (
            service.add_coverage(
                **coverage_kwargs("MISSING", context, identity_ref, "MISSING")
            )
            != coverage_refs["MISSING"]
        ):
            raise AssertionError("Coverage idempotency drift")
        restarted = B02Service(FixtureStore(root), **deepcopy(upstream))
        validate_store(restarted.store, context=restarted.context)
        if (
            restarted.add_coverage(
                **coverage_kwargs(
                    "MISSING", restarted.context, identity_ref, "MISSING"
                )
            )
            != coverage_refs["MISSING"]
        ):
            raise AssertionError("Coverage restart idempotency drift")
        records = service.store.read_records()
        validate_store(service.store, context=service.context)
        before_projection = directory_snapshot(root)
        projection = project_open_diagnostics(context=service.context, records=records)
        if directory_snapshot(root) != before_projection:
            raise AssertionError("projection persisted state")
        if projection["open_diagnostic_refs"] != [open_ref]:
            raise AssertionError("open Diagnostic projection drift")
        if "evidence" in projection["open_diagnostics"][0]:
            raise AssertionError("projection copied source prose")

        coverages = {
            record["payload"]["candidate_match"]: record
            for record in records
            if record["record_type"] == "M3_COVERAGE_OBSERVATION"
        }
        if coverages["MISSING"]["payload"]["matched_candidate_bindings"]:
            raise AssertionError("MISSING retained matched refs")
        for match in ("MATCHED", "PARTIAL"):
            pair = coverages[match]["payload"]["matched_candidate_bindings"][0]
            if (
                pair["lineage_locator"]["lineage_id"]
                != pair["evidence_locator"]["lineage_id"]
                or pair["lineage_locator"]["candidate_version_ref"]
                != record_ref(context["candidate_version"])
            ):
                raise AssertionError(f"{match} locator pair drift")

        before_failure = directory_snapshot(root)
        missing_evidence = diagnostic_kwargs("F-02", context, identity_ref)
        missing_evidence["evidence_locator"] = None
        _expect(
            "B02_MATCHED_BINDING_INVALID",
            lambda: service.add_diagnostic(**missing_evidence),
        )
        if directory_snapshot(root) != before_failure:
            raise AssertionError("failed Diagnostic wrote bytes")

        mismatched_diagnostic = diagnostic_kwargs("F-03", context, identity_ref)
        mismatched_diagnostic["evidence_locator"] = deepcopy(
            context["evidence_locators"][1]
        )
        _expect(
            "B02_MATCHED_BINDING_INVALID",
            lambda: service.add_diagnostic(**mismatched_diagnostic),
        )

        missing_with_pair = coverage_kwargs(
            "F-04", context, identity_ref, "MISSING"
        )
        missing_with_pair["matched_candidate_bindings"] = [matched_pair(context)]
        _expect(
            "B02_MISSING_MATCHED_REFS_FORBIDDEN",
            lambda: service.add_coverage(**missing_with_pair),
        )
        for match in ("PARTIAL", "MATCHED"):
            without_pair = coverage_kwargs("F-05", context, identity_ref, match)
            without_pair["matched_candidate_bindings"] = []
            _expect(
                "B02_MATCHED_BINDING_REQUIRED",
                lambda without_pair=without_pair: service.add_coverage(**without_pair),
            )
        outside_source = coverage_kwargs("F-06", context, identity_ref, "MISSING")
        outside_source["source_evidence"] = "这句话不在合成章节里。"
        _expect(
            "B02_SOURCE_EVIDENCE_NOT_IN_EXACT_CHAPTER",
            lambda: service.add_coverage(**outside_source),
        )

        source_record = CoverageRecorder.build(
            context=context,
            **coverage_kwargs("F-07", context, identity_ref, "MISSING"),
        )
        hash_drift = deepcopy(source_record)
        hash_drift["payload"]["source_evidence_binding"]["evidence_sha256"] = (
            "f" * 64
        )
        location_drift = deepcopy(source_record)
        location_drift["payload"]["source_evidence_binding"]["match_locations"][0][
            "start_byte"
        ] += 1
        for tampered in (hash_drift, location_drift):
            tampered = reseal_record(tampered)
            _expect(
                "B02_SOURCE_EVIDENCE_INVALID",
                lambda tampered=tampered: validate_coverage_record(
                    tampered, context=context, records=records
                ),
            )

        diagnostic_for_drift = DiagnosticRecorder.build(
            context=context,
            **diagnostic_kwargs("F-08", context, identity_ref),
        )
        coverage_for_drift = CoverageRecorder.build(
            context=context,
            **coverage_kwargs("F-08", context, identity_ref, "MISSING"),
        )
        for source, validator in (
            (diagnostic_for_drift, validate_diagnostic_record),
            (coverage_for_drift, validate_coverage_record),
        ):
            candidate_drift = deepcopy(source)
            candidate_drift["payload"]["base_candidate_version_ref"][
                "record_hash"
            ] = "f" * 64
            candidate_drift = reseal_record(candidate_drift)
            _expect(
                "B02_SCOPE_MISMATCH",
                lambda record=candidate_drift, validator=validator: validator(
                    record, context=context, records=records
                ),
            )

        collision = coverage_kwargs("F-09", context, identity_ref, "MISSING")
        service.add_coverage(**collision)
        collision["source_evidence"] = SOURCE_MATCHED
        _expect(
            "B02_IMMUTABLE_ALREADY_EXISTS",
            lambda: service.add_coverage(**collision),
        )

        _expect(
            "B02_LIFECYCLE_SEQUENCE_CONFLICT",
            lambda: service.append_lifecycle(
                diagnostic_ref=closed_ref,
                lifecycle_sequence=1,
                event="CLOSED",
                effective_at="2026-08-29T04:30:00Z",
                reason_code="DIFFERENT_BYTES",
                created_at="2026-08-29T04:30:00Z",
            ),
        )
        _expect(
            "B02_LIFECYCLE_TIME_CONFLICT",
            lambda: service.append_lifecycle(
                diagnostic_ref=closed_ref,
                lifecycle_sequence=2,
                event="SUPERSEDED_BY_PATCH_REVIEW",
                effective_at="2026-08-29T04:30:00Z",
                reason_code="SAME_TIME",
                created_at="2026-08-29T04:30:00Z",
            ),
        )
        _expect(
            "B02_LIFECYCLE_TERMINAL",
            lambda: service.append_lifecycle(
                diagnostic_ref=closed_ref,
                lifecycle_sequence=2,
                event="CLOSED",
                effective_at="2026-08-29T04:31:00Z",
                reason_code="AGAIN",
                created_at="2026-08-29T04:31:00Z",
            ),
        )

        order_root = root / "lifecycle-order"
        order_service = B02Service(FixtureStore(order_root), **deepcopy(upstream))
        order_identity = order_service.register_identity(
            writer_version="r03.5-fixture-writer-v1",
            created_at="2026-08-29T04:00:00Z",
        )
        order_context = order_service.context
        order_diagnostic = order_service.add_diagnostic(
            **diagnostic_kwargs("F-10-ORDER", order_context, order_identity)
        )
        order_service.append_lifecycle(
            diagnostic_ref=order_diagnostic,
            lifecycle_sequence=2,
            event="CLOSED",
            effective_at="2026-08-29T04:32:00Z",
            reason_code="SECOND",
            created_at="2026-08-29T04:32:00Z",
        )
        _expect(
            "B02_LIFECYCLE_ORDER_CONFLICT",
            lambda: order_service.append_lifecycle(
                diagnostic_ref=order_diagnostic,
                lifecycle_sequence=1,
                event="CLOSED",
                effective_at="2026-08-29T04:31:00Z",
                reason_code="FIRST",
                created_at="2026-08-29T04:31:00Z",
            ),
        )

        legacy_upstream = deepcopy(upstream)
        legacy_catalog = json.loads(B01_OBJECT_SHAPES_PATH.read_text(encoding="utf-8"))
        legacy_upstream["candidate_version"] = legacy_catalog[
            "legacy_candidate_example"
        ]
        _expect(
            "B02_UPSTREAM_CONTEXT_INVALID",
            lambda: B02Service(
                FixtureStore(root / "legacy-admission"), **legacy_upstream
            ),
        )

        failure_root = root / "transaction-failure"
        failing = B02Service(
            FixtureStore(failure_root, failure_point="after_pending_write"),
            **deepcopy(upstream),
        )
        _expect(
            "B02_SIMULATED_TRANSACTION_FAILURE",
            lambda: failing.register_identity(
                writer_version="r03.5-fixture-writer-v1",
                created_at="2026-08-29T04:00:00Z",
            ),
        )
        if directory_snapshot(failure_root):
            raise AssertionError("transaction failure left bytes")

        decomposed = "甲看见e\u0301。"
        ordinary = "Cafe\u0301"
        reopened = json.loads(
            canonical_bytes(
                {
                    "ordinary_label": ordinary,
                    "source_evidence_binding": {"evidence": decomposed},
                }
            )
        )
        if (
            reopened["source_evidence_binding"]["evidence"].encode("utf-8")
            != decomposed.encode("utf-8")
            or reopened["ordinary_label"] != "Café"
        ):
            raise AssertionError("source Unicode preservation drift")

        _expect(
            "B02_WRITE_SET_ESCAPE",
            lambda: guard_write_path(
                "work/ccz57_m3_b02_diagnostic_coverage_r03_4/escape"
            ),
        )
        for event in (
            "network",
            "model_api",
            "subprocess",
            "real_novel_read",
        ):
            _expect(
                "B02_RUNTIME_EVENT_FORBIDDEN",
                lambda event=event: guard_runtime_event(event),
            )
        for event in ("patch_write", "candidate_version_write", "pointer_write"):
            _expect(
                "B02_CANDIDATE_WRITE_FORBIDDEN",
                lambda event=event: guard_runtime_event(event),
            )

        counts = {
            record_type: sum(
                record["record_type"] == record_type for record in records
            )
            for record_type in sorted(OUTPUT_TYPES)
        }
        record_hashes = sorted(record["record_hash"] for record in records)

    legacy_files = _verify_manifest(LEGACY_B02_ROOT)
    b01_files = _verify_manifest(B01_ROOT)
    static = _static_boundary_check()
    return {
        "report_contract": "CCZ57_M3_B02_R03_5_OFFLINE_REPLAY",
        "contract_version": CONTRACT_VERSION,
        "candidate_schema_id": CANDIDATE_SCHEMA_ID,
        "upstream_identity": upstream_identity_summary(),
        "writer_map": WRITER_MAP,
        "normal_fixtures": {
            fixture_id: {"description": description, "result": "PASS"}
            for fixture_id, description in NORMAL_FIXTURES.items()
        },
        "failure_fixtures": {
            fixture_id: {"description": description, "result": "PASS"}
            for fixture_id, description in FAILURE_FIXTURES.items()
        },
        "replay_evidence": {
            "record_counts": counts,
            "record_hashes": record_hashes,
            "closed_diagnostic_ref": closed_ref,
            "open_diagnostic_ref": open_ref,
            "lifecycle_ref": lifecycle_ref,
            "coverage_refs": coverage_refs,
            "projection_open_count": projection["open_count"],
        },
        "source_evidence_unicode_policy": {
            "source_evidence": "PRESERVE_ORIGINAL_CODE_POINTS_AND_UTF8_BYTES",
            "ordinary_fields": "NFC",
            "decomposed_unicode_regression": "PASS",
        },
        "legacy_r03_3": {
            "mode": "READ_ONLY",
            "manifest_verified_files": sorted(legacy_files),
        },
        "b01_r03_5": {
            "mode": "READ_ONLY",
            "manifest_verified_files": sorted(b01_files),
        },
        "static_boundary": static,
        "runtime_event_evidence": {
            "model_api_calls": 0,
            "network_calls": 0,
            "real_novel_reads": 0,
            "patch_writes": 0,
            "candidate_version_writes": 0,
            "write_set_escapes": 0,
        },
        "result": "PASS",
    }


def main() -> None:
    expected = run_replay()
    actual = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if actual != expected:
        raise AssertionError("OFFLINE_REPLAY_REPORT.json drift")
    manifest_files = _verify_manifest(MODULE_ROOT)
    if "OFFLINE_REPLAY_REPORT.json" not in manifest_files:
        raise AssertionError("report missing from MANIFEST")
    print(
        json.dumps(
            {
                "contract_version": CONTRACT_VERSION,
                "manifest_files": len(manifest_files),
                "normal_fixtures": len(NORMAL_FIXTURES),
                "failure_fixtures": len(FAILURE_FIXTURES),
                "result": "PASS",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

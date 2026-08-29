from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from b02_contracts import (
    B02ContractError,
    CANDIDATE_SCHEMA_ID,
    CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION,
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
    DiagnosticLifecycleWriter,
    DiagnosticRecorder,
    DiagnosticRecorderIdentityRegistry,
    FixtureStore,
    directory_snapshot,
    record_file_bytes,
    validate_store,
)
from fixtures import (
    LEGACY_B02_ROOT,
    SOURCE_EMPTY_BASELINE_MISSING,
    SOURCE_MATCHED,
    coverage_kwargs,
    diagnostic_kwargs,
    empty_upstream_fixture,
    exact_upstream_fixture,
    matched_pair,
    reseal_record,
)
from open_issue_projection import project_open_diagnostics


def assert_error(code: str, call) -> B02ContractError:
    with pytest.raises(B02ContractError) as caught:
        call()
    assert caught.value.code == code
    return caught.value


def make_service(
    root: Path, *, failure_point: str | None = None
) -> tuple[B02Service, dict, dict]:
    upstream = exact_upstream_fixture()
    service = B02Service(
        FixtureStore(root, failure_point=failure_point), **deepcopy(upstream)
    )
    identity_ref = service.register_identity(
        writer_version="r03.5-fixture-writer-v1",
        created_at="2026-08-29T04:00:00Z",
    )
    return service, service.context, identity_ref


def stored_by_type(store: FixtureStore, record_type: str) -> list[dict]:
    return [
        record for record in store.read_records() if record["record_type"] == record_type
    ]


def verify_manifest(root: Path) -> None:
    for line in (root / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        path = root / relative.removeprefix("./")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_contract_identity_and_exact_four_writer_surface() -> None:
    assert CONTRACT_VERSION == "r03.5-candidate"
    assert LEGACY_CONTRACT_VERSION == "r03.3-candidate"
    assert CANDIDATE_SCHEMA_ID == "novel-fact-extraction-v2.1"
    assert OUTPUT_TYPES == set(WRITER_MAP)
    assert WRITER_MAP == {
        "M3_DIAGNOSTIC_RECORDER_IDENTITY": "DiagnosticRecorderIdentityRegistry",
        "M3_DIAGNOSTIC": "DiagnosticRecorder",
        "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT": "DiagnosticLifecycleWriter",
        "M3_COVERAGE_OBSERVATION": "CoverageRecorder",
    }
    assert {
        DiagnosticRecorderIdentityRegistry.WRITER_NAME,
        DiagnosticRecorder.WRITER_NAME,
        DiagnosticLifecycleWriter.WRITER_NAME,
        CoverageRecorder.WRITER_NAME,
    } == set(WRITER_MAP.values())


def test_diagnostic_is_entry_and_evidence_level_and_idempotent(tmp_path: Path) -> None:
    service, context, identity_ref = make_service(tmp_path)
    kwargs = diagnostic_kwargs("N-02", context, identity_ref)
    diagnostic_ref = service.add_diagnostic(**kwargs)
    original = stored_by_type(service.store, "M3_DIAGNOSTIC")[0]
    original_bytes = record_file_bytes(service.store, diagnostic_ref)
    target = original["payload"]["target"]

    assert target["kind"] == "CANDIDATE_ITEM_EVIDENCE"
    assert set(target) == {"kind", "lineage_locator", "evidence_locator"}
    assert target["lineage_locator"]["lineage_id"] == target["evidence_locator"][
        "lineage_id"
    ]
    assert target["lineage_locator"]["candidate_version_ref"] == record_ref(
        context["candidate_version"]
    )
    assert target["evidence_locator"]["candidate_version_ref"] == record_ref(
        context["candidate_version"]
    )
    assert "evidence_refs" not in original["payload"]
    assert "origin_attempt_refs" not in original["payload"]

    assert service.add_diagnostic(**kwargs) == diagnostic_ref
    assert record_file_bytes(service.store, diagnostic_ref) == original_bytes
    assert len(stored_by_type(service.store, "M3_DIAGNOSTIC")) == 1
    validate_store(service.store, context=service.context)


def test_missing_diagnostic_evidence_locator_fails_before_write(tmp_path: Path) -> None:
    service, context, identity_ref = make_service(tmp_path)
    before = directory_snapshot(tmp_path)
    kwargs = diagnostic_kwargs("F-02", context, identity_ref)
    kwargs["evidence_locator"] = None
    assert_error("B02_MATCHED_BINDING_INVALID", lambda: service.add_diagnostic(**kwargs))
    assert directory_snapshot(tmp_path) == before
    assert not stored_by_type(service.store, "M3_DIAGNOSTIC")


def test_diagnostic_rejects_locator_pair_from_different_items(tmp_path: Path) -> None:
    service, context, identity_ref = make_service(tmp_path)
    kwargs = diagnostic_kwargs("F-03", context, identity_ref)
    kwargs["evidence_locator"] = deepcopy(context["evidence_locators"][1])
    before = directory_snapshot(tmp_path)
    assert_error("B02_MATCHED_BINDING_INVALID", lambda: service.add_diagnostic(**kwargs))
    assert directory_snapshot(tmp_path) == before


def test_coverage_shapes_for_matched_partial_and_missing(tmp_path: Path) -> None:
    service, context, identity_ref = make_service(tmp_path)
    refs = {
        match: service.add_coverage(
            **coverage_kwargs(f"N-{index}", context, identity_ref, match)
        )
        for index, match in enumerate(("MATCHED", "PARTIAL", "MISSING"), start=4)
    }
    records = {
        record["payload"]["candidate_match"]: record
        for record in stored_by_type(service.store, "M3_COVERAGE_OBSERVATION")
    }
    assert set(records) == {"MATCHED", "PARTIAL", "MISSING"}

    for match, record in records.items():
        payload = record["payload"]
        binding = payload["source_evidence_binding"]
        evidence_bytes = binding["evidence"].encode("utf-8")
        assert payload["base_candidate_version_ref"] == record_ref(
            context["candidate_version"]
        )
        assert payload["candidate_schema_id"] == CANDIDATE_SCHEMA_ID
        assert payload["chapter_revision_ref"] == context["candidate_version"][
            "payload"
        ]["chapter_revision_ref"]
        assert binding["evidence_sha256"] == hashlib.sha256(evidence_bytes).hexdigest()
        assert binding["match_locations"]
        assert record_file_bytes(service.store, refs[match]) == canonical_bytes(record)

    assert records["MISSING"]["payload"]["matched_candidate_bindings"] == []
    for match in ("MATCHED", "PARTIAL"):
        pairs = records[match]["payload"]["matched_candidate_bindings"]
        assert len(pairs) == 1
        pair = pairs[0]
        assert pair["lineage_locator"]["candidate_version_ref"] == record_ref(
            context["candidate_version"]
        )
        assert pair["evidence_locator"]["candidate_version_ref"] == record_ref(
            context["candidate_version"]
        )
        assert pair["lineage_locator"]["lineage_id"] == pair["evidence_locator"][
            "lineage_id"
        ]
    validate_store(service.store, context=service.context)


def test_empty_candidate_version_admits_missing_coverage(tmp_path: Path) -> None:
    upstream = empty_upstream_fixture()
    service = B02Service(FixtureStore(tmp_path), **deepcopy(upstream))
    identity_ref = service.register_identity(
        writer_version="r03.5-fixture-writer-v1",
        created_at="2026-08-29T04:00:00Z",
    )

    coverage_ref = service.add_coverage(
        **coverage_kwargs(
            "N-10",
            service.context,
            identity_ref,
            "MISSING",
            source_evidence=SOURCE_EMPTY_BASELINE_MISSING,
        )
    )
    coverage = stored_by_type(service.store, "M3_COVERAGE_OBSERVATION")[0]
    binding = coverage["payload"]["source_evidence_binding"]

    assert service.context["candidate_version"]["payload"]["items"] == []
    assert service.context["lineage_locators"] == []
    assert service.context["evidence_locators"] == []
    assert coverage["payload"]["candidate_match"] == "MISSING"
    assert coverage["payload"]["matched_candidate_bindings"] == []
    assert binding["evidence"] == SOURCE_EMPTY_BASELINE_MISSING
    assert binding["evidence_sha256"] == hashlib.sha256(
        SOURCE_EMPTY_BASELINE_MISSING.encode("utf-8")
    ).hexdigest()
    assert binding["sentence_count"] == 1
    assert len(binding["match_locations"]) == 1
    assert binding["match_locations"][0]["seg"] == 2
    assert record_file_bytes(service.store, coverage_ref) == canonical_bytes(coverage)
    validate_store(service.store, context=service.context)


@pytest.mark.parametrize("candidate_match", ["PARTIAL", "MATCHED"])
def test_partial_and_matched_require_locator_pair(
    tmp_path: Path, candidate_match: str
) -> None:
    service, context, identity_ref = make_service(tmp_path)
    kwargs = coverage_kwargs("F-05", context, identity_ref, candidate_match)
    kwargs["matched_candidate_bindings"] = []
    before = directory_snapshot(tmp_path)
    assert_error("B02_MATCHED_BINDING_REQUIRED", lambda: service.add_coverage(**kwargs))
    assert directory_snapshot(tmp_path) == before


def test_missing_forbids_matched_locator_pair(tmp_path: Path) -> None:
    service, context, identity_ref = make_service(tmp_path)
    kwargs = coverage_kwargs("F-04", context, identity_ref, "MISSING")
    kwargs["matched_candidate_bindings"] = [matched_pair(context)]
    before = directory_snapshot(tmp_path)
    assert_error(
        "B02_MISSING_MATCHED_REFS_FORBIDDEN",
        lambda: service.add_coverage(**kwargs),
    )
    assert directory_snapshot(tmp_path) == before


def test_coverage_rejects_mismatched_locator_pair(tmp_path: Path) -> None:
    service, context, identity_ref = make_service(tmp_path)
    kwargs = coverage_kwargs("F-PAIR", context, identity_ref, "PARTIAL")
    kwargs["matched_candidate_bindings"] = [
        {
            "lineage_locator": deepcopy(context["lineage_locators"][0]),
            "evidence_locator": deepcopy(context["evidence_locators"][1]),
        }
    ]
    assert_error("B02_MATCHED_BINDING_INVALID", lambda: service.add_coverage(**kwargs))


def test_source_evidence_must_resolve_to_exact_chapter_bytes(tmp_path: Path) -> None:
    service, context, identity_ref = make_service(tmp_path)
    kwargs = coverage_kwargs("F-06", context, identity_ref, "MISSING")
    kwargs["source_evidence"] = "这句话不在合成章节里。"
    before = directory_snapshot(tmp_path)
    assert_error(
        "B02_SOURCE_EVIDENCE_NOT_IN_EXACT_CHAPTER",
        lambda: service.add_coverage(**kwargs),
    )
    assert directory_snapshot(tmp_path) == before


def test_tampered_source_binding_hash_and_location_are_rejected(tmp_path: Path) -> None:
    service, context, identity_ref = make_service(tmp_path)
    record = CoverageRecorder.build(
        context=context,
        **coverage_kwargs("F-07", context, identity_ref, "MISSING"),
    )
    records = service.store.read_records()
    for mutator in (
        lambda binding: binding.__setitem__("evidence_sha256", "f" * 64),
        lambda binding: binding["match_locations"][0].__setitem__("start_byte", 1),
    ):
        mutated = deepcopy(record)
        mutator(mutated["payload"]["source_evidence_binding"])
        mutated = reseal_record(mutated)
        assert_error(
            "B02_SOURCE_EVIDENCE_INVALID",
            lambda mutated=mutated: validate_coverage_record(
                mutated, context=context, records=records
            ),
        )


def test_decomposed_unicode_source_evidence_survives_canonical_round_trip() -> None:
    evidence = "甲看见e\u0301。"
    ordinary = "Cafe\u0301"
    payload = {
        "ordinary_label": ordinary,
        "source_evidence_binding": {
            "evidence": evidence,
            "evidence_sha256": hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
        },
    }
    encoded = canonical_bytes(payload)
    reopened = json.loads(encoded)
    assert reopened["source_evidence_binding"]["evidence"] == evidence
    assert reopened["source_evidence_binding"]["evidence"].encode("utf-8") == (
        evidence.encode("utf-8")
    )
    assert reopened["source_evidence_binding"]["evidence"] != "甲看见é。"
    assert reopened["ordinary_label"] == "Café"


def test_exact_candidate_revision_and_contract_binding_reject_drift(
    tmp_path: Path,
) -> None:
    service, context, identity_ref = make_service(tmp_path)
    diagnostic = DiagnosticRecorder.build(
        context=context, **diagnostic_kwargs("F-08-D", context, identity_ref)
    )
    coverage = CoverageRecorder.build(
        context=context,
        **coverage_kwargs("F-08-C", context, identity_ref, "MISSING"),
    )
    records = service.store.read_records()

    for source, validator in (
        (diagnostic, validate_diagnostic_record),
        (coverage, validate_coverage_record),
    ):
        candidate_drift = deepcopy(source)
        candidate_drift["payload"]["base_candidate_version_ref"]["record_hash"] = (
            "f" * 64
        )
        candidate_drift = reseal_record(candidate_drift)
        assert_error(
            "B02_SCOPE_MISMATCH",
            lambda record=candidate_drift, validator=validator: validator(
                record, context=context, records=records
            ),
        )

        revision_drift = deepcopy(source)
        revision_drift["payload"]["chapter_revision_ref"]["revision_no"] += 1
        revision_drift = reseal_record(revision_drift)
        assert_error(
            "B02_SCOPE_MISMATCH",
            lambda record=revision_drift, validator=validator: validator(
                record, context=context, records=records
            ),
        )

        contract_drift = deepcopy(source)
        contract_drift["contract_version"] = LEGACY_CONTRACT_VERSION
        contract_drift = reseal_record(contract_drift)
        assert_error(
            "B02_UPSTREAM_CONTRACT_DRIFT",
            lambda record=contract_drift, validator=validator: validator(
                record, context=context, records=records
            ),
        )


def test_legacy_candidate_is_rejected_and_old_b02_manifest_still_matches(
    tmp_path: Path,
) -> None:
    upstream = exact_upstream_fixture()
    catalog = json.loads(
        (
            LEGACY_B02_ROOT.parent
            / "ccz57_m3_b01_candidate_version_r03_5"
            / "OBJECT_SHAPES.json"
        ).read_text(encoding="utf-8")
    )
    legacy = catalog["legacy_candidate_example"]
    upstream["candidate_version"] = legacy
    with pytest.raises(B02ContractError) as caught:
        B02Service(FixtureStore(tmp_path), **upstream)
    assert caught.value.code == "B02_UPSTREAM_CONTEXT_INVALID"
    verify_manifest(LEGACY_B02_ROOT)


def test_lifecycle_changes_only_status_and_projection_is_nonpersistent(
    tmp_path: Path,
) -> None:
    service, context, identity_ref = make_service(tmp_path)
    closed_ref = service.add_diagnostic(
        **diagnostic_kwargs("N-03-CLOSED", context, identity_ref, locator_index=0)
    )
    open_ref = service.add_diagnostic(
        **diagnostic_kwargs("N-03-OPEN", context, identity_ref, locator_index=1)
    )
    original_bytes = record_file_bytes(service.store, closed_ref)
    service.append_lifecycle(
        diagnostic_ref=closed_ref,
        lifecycle_sequence=1,
        event="CLOSED",
        effective_at="2026-08-29T04:30:00Z",
        reason_code="REVIEWED",
        created_at="2026-08-29T04:30:00Z",
    )
    assert record_file_bytes(service.store, closed_ref) == original_bytes
    before_projection = directory_snapshot(tmp_path)
    projection = project_open_diagnostics(
        context=service.context, records=service.store.read_records()
    )
    assert directory_snapshot(tmp_path) == before_projection
    assert projection["open_diagnostic_refs"] == [open_ref]
    assert projection["open_count"] == 1
    summary = projection["open_diagnostics"][0]
    assert summary["diagnostic_ref"] == open_ref
    assert "evidence" not in summary
    assert set(summary) == {
        "diagnostic_ref",
        "lineage_id",
        "item_json_pointer",
        "lineage_locator_hash",
        "evidence_json_pointer",
        "evidence_sha256",
        "evidence_locator_hash",
    }


def test_lifecycle_rejects_duplicate_order_time_and_after_terminal(
    tmp_path: Path,
) -> None:
    service, context, identity_ref = make_service(tmp_path)
    diagnostic_ref = service.add_diagnostic(
        **diagnostic_kwargs("F-10", context, identity_ref)
    )
    first = {
        "diagnostic_ref": diagnostic_ref,
        "lifecycle_sequence": 1,
        "event": "CLOSED",
        "effective_at": "2026-08-29T04:30:00Z",
        "reason_code": "REVIEWED",
        "created_at": "2026-08-29T04:30:00Z",
    }
    first_ref = service.append_lifecycle(**first)
    assert service.append_lifecycle(**first) == first_ref
    changed_same_sequence = deepcopy(first)
    changed_same_sequence["reason_code"] = "DIFFERENT_BYTES"
    assert_error(
        "B02_LIFECYCLE_SEQUENCE_CONFLICT",
        lambda: service.append_lifecycle(**changed_same_sequence),
    )
    same_time_different_event = deepcopy(first)
    same_time_different_event["lifecycle_sequence"] = 2
    same_time_different_event["event"] = "SUPERSEDED_BY_PATCH_REVIEW"
    same_time_different_event["reason_code"] = "SAME_TIME"
    assert_error(
        "B02_LIFECYCLE_TIME_CONFLICT",
        lambda: service.append_lifecycle(**same_time_different_event),
    )
    assert_error(
        "B02_LIFECYCLE_TERMINAL",
        lambda: service.append_lifecycle(
            diagnostic_ref=diagnostic_ref,
            lifecycle_sequence=2,
            event="CLOSED",
            effective_at="2026-08-29T04:31:00Z",
            reason_code="AGAIN",
            created_at="2026-08-29T04:31:00Z",
        ),
    )

    other_root = tmp_path.parent / f"{tmp_path.name}-order"
    other, other_context, other_identity = make_service(other_root)
    other_ref = other.add_diagnostic(
        **diagnostic_kwargs("F-10-ORDER", other_context, other_identity)
    )
    other.append_lifecycle(
        diagnostic_ref=other_ref,
        lifecycle_sequence=2,
        event="CLOSED",
        effective_at="2026-08-29T04:32:00Z",
        reason_code="SECOND",
        created_at="2026-08-29T04:32:00Z",
    )
    assert_error(
        "B02_LIFECYCLE_ORDER_CONFLICT",
        lambda: other.append_lifecycle(
            diagnostic_ref=other_ref,
            lifecycle_sequence=1,
            event="CLOSED",
            effective_at="2026-08-29T04:31:00Z",
            reason_code="FIRST",
            created_at="2026-08-29T04:31:00Z",
        ),
    )


def test_immutable_collision_and_transaction_cleanup(tmp_path: Path) -> None:
    service, context, identity_ref = make_service(tmp_path / "collision")
    first = coverage_kwargs("F-09", context, identity_ref, "MISSING")
    service.add_coverage(**first)
    changed = deepcopy(first)
    changed["source_evidence"] = SOURCE_MATCHED
    assert_error("B02_IMMUTABLE_ALREADY_EXISTS", lambda: service.add_coverage(**changed))

    failing_root = tmp_path / "transaction"
    upstream = exact_upstream_fixture()
    failing_service = B02Service(
        FixtureStore(failing_root, failure_point="after_pending_write"), **upstream
    )
    assert_error(
        "B02_SIMULATED_TRANSACTION_FAILURE",
        lambda: failing_service.register_identity(
            writer_version="r03.5-fixture-writer-v1",
            created_at="2026-08-29T04:00:00Z",
        ),
    )
    assert directory_snapshot(failing_root) == {}


def test_guards_block_write_escape_and_forbidden_runtime_paths() -> None:
    assert_error(
        "B02_WRITE_SET_ESCAPE",
        lambda: guard_write_path("work/ccz57_m3_b02_diagnostic_coverage_r03_4/x"),
    )
    for event in (
        "network",
        "model_api",
        "subprocess",
        "dynamic_import",
        "real_novel_read",
    ):
        assert_error("B02_RUNTIME_EVENT_FORBIDDEN", lambda event=event: guard_runtime_event(event))
    for event in ("patch_write", "candidate_version_write", "pointer_write"):
        assert_error("B02_CANDIDATE_WRITE_FORBIDDEN", lambda event=event: guard_runtime_event(event))

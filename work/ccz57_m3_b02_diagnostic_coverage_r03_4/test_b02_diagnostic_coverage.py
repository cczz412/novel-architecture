"""Directed N-01..N-09 and F-01..F-18 acceptance for B-02."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest

import b02_store as store_module
import fixtures as fx
from b02_contracts import (
    B02ContractError,
    canonical_bytes,
    guard_runtime_event,
    record_ref,
    sha256_value,
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
)
from open_issue_projection import project_open_diagnostics


def _service(
    root: Path, upstream: dict[str, Any] | None = None
) -> tuple[FixtureStore, B02Service, dict[str, Any]]:
    exact = fx.exact_upstream_fixture() if upstream is None else upstream
    store = FixtureStore(root)
    service = B02Service(store, **exact)
    return store, service, exact


def _identity(service: B02Service) -> dict[str, Any]:
    return service.register_identity(
        writer_version="b02-fixture-v1", created_at="2026-08-28T12:01:00Z"
    )


def _resolve(store: FixtureStore, ref: dict[str, Any]) -> dict[str, Any]:
    matches = [item for item in store.read_records() if record_ref(item) == ref]
    assert len(matches) == 1
    return matches[0]


def _add_diagnostic(
    service: B02Service,
    fixture_id: str,
    identity_ref: dict[str, Any],
    **overrides: Any,
) -> dict[str, Any]:
    kwargs = fx.diagnostic_kwargs(fixture_id, service.context, identity_ref)
    kwargs.update(overrides)
    return service.add_diagnostic(**kwargs)


def _assert_failure_without_visible_write(
    root: Path,
    action: Callable[[], Any],
    expected_codes: set[str] | None = None,
) -> B02ContractError:
    before = directory_snapshot(root)
    with pytest.raises(B02ContractError) as caught:
        action()
    after = directory_snapshot(root)
    assert after == before
    if expected_codes is not None:
        assert caught.value.code in expected_codes
    return caught.value


def _new_paths(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return set(after) - set(before)


def _new_file_paths(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {path for path in _new_paths(before, after) if path.startswith("file:")}


def test_n01_writer_identity_original(tmp_path: Path) -> None:
    assert list(fx.NORMAL_FIXTURES) == [f"N-{index:02d}" for index in range(1, 10)]
    assert list(fx.FAILURE_FIXTURES) == [f"F-{index:02d}" for index in range(1, 19)]
    b01 = fx.exact_b01_objects()
    assert b01["catalog_path"] == fx.B01_OBJECT_SHAPES_PATH
    assert b01["candidate_version"]["record_type"] == "M3_CANDIDATE_VERSION"
    assert b01["segment_index"]["record_type"] == "M3_SEGMENT_INDEX_SNAPSHOT"

    store, service, _ = _service(tmp_path / "N-01")
    identity_ref = _identity(service)
    identity = _resolve(store, identity_ref)
    assert identity["record_type"] == "M3_DIAGNOSTIC_RECORDER_IDENTITY"
    assert identity["payload"] == {
        "writer": "DiagnosticRecorder",
        "writer_version": "b02-fixture-v1",
    }


def test_n02_open_diagnostic(tmp_path: Path) -> None:
    store, service, _ = _service(tmp_path / "N-02")
    identity_ref = _identity(service)
    diagnostic_ref = _add_diagnostic(service, "N-02", identity_ref)
    diagnostic = _resolve(store, diagnostic_ref)
    assert diagnostic["payload"]["target"]["kind"] == "LINEAGE"
    assert diagnostic["payload"]["writer_identity_ref"] == identity_ref
    projected = project_open_diagnostics(
        context=service.context, records=store.read_records()
    )
    assert projected["open_diagnostic_refs"] == [diagnostic_ref]
    assert projected["open_count"] == 1


def test_n03_superseded_append_preserves_diagnostic_bytes(tmp_path: Path) -> None:
    store, service, _ = _service(tmp_path / "N-03")
    identity_ref = _identity(service)
    diagnostic_ref = _add_diagnostic(service, "N-03", identity_ref)
    assert diagnostic_ref["record_id"].endswith(
        fx.deterministic_sha("N-03:diagnostic")[:32]
    )
    diagnostic = _resolve(store, diagnostic_ref)
    path = store.path_for(diagnostic)
    raw_before = record_file_bytes(store, diagnostic_ref)
    size_before = path.stat().st_size
    hash_before = diagnostic["record_hash"]
    before = directory_snapshot(store.root)

    service.append_lifecycle(
        diagnostic_ref=diagnostic_ref,
        lifecycle_sequence=1,
        event="SUPERSEDED_BY_PATCH_REVIEW",
        effective_at="2026-08-28T12:30:00Z",
        reason_code="PATCH_REVIEW_ACCEPTED",
        created_at="2026-08-28T12:30:00Z",
    )

    after = directory_snapshot(store.root)
    assert record_file_bytes(store, diagnostic_ref) == raw_before
    assert path.stat().st_size == size_before
    assert _resolve(store, diagnostic_ref)["record_hash"] == hash_before
    new_paths = _new_file_paths(before, after)
    assert len(new_paths) == 1
    assert "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT" in next(iter(new_paths))
    assert project_open_diagnostics(
        context=service.context, records=store.read_records()
    )["open_count"] == 0


def test_n04_closed_append_uses_distinct_diagnostic_and_preserves_bytes(
    tmp_path: Path,
) -> None:
    store, service, _ = _service(tmp_path / "N-04")
    identity_ref = _identity(service)
    diagnostic_ref = _add_diagnostic(service, "N-04", identity_ref)
    assert diagnostic_ref["record_id"].endswith(
        fx.deterministic_sha("N-04:diagnostic")[:32]
    )
    assert not diagnostic_ref["record_id"].endswith(
        fx.deterministic_sha("N-03:diagnostic")[:32]
    )
    diagnostic = _resolve(store, diagnostic_ref)
    path = store.path_for(diagnostic)
    raw_before = record_file_bytes(store, diagnostic_ref)
    size_before = path.stat().st_size
    hash_before = diagnostic["record_hash"]
    before = directory_snapshot(store.root)

    service.append_lifecycle(
        diagnostic_ref=diagnostic_ref,
        lifecycle_sequence=1,
        event="CLOSED",
        effective_at="2026-08-28T12:31:00Z",
        reason_code="MANUAL_REVIEW_COMPLETE",
        created_at="2026-08-28T12:31:00Z",
    )

    after = directory_snapshot(store.root)
    assert record_file_bytes(store, diagnostic_ref) == raw_before
    assert path.stat().st_size == size_before
    assert _resolve(store, diagnostic_ref)["record_hash"] == hash_before
    new_paths = _new_file_paths(before, after)
    assert len(new_paths) == 1
    assert "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT" in next(iter(new_paths))
    assert project_open_diagnostics(
        context=service.context, records=store.read_records()
    )["open_count"] == 0


def test_n05_matched_coverage_does_not_modify_candidate(tmp_path: Path) -> None:
    store, service, _ = _service(tmp_path / "N-05")
    identity_ref = _identity(service)
    candidate_before = canonical_bytes(service.context["candidate_version"])
    coverage_ref = service.add_coverage(
        **fx.coverage_kwargs("N-05", identity_ref, "MATCHED")
    )
    coverage = _resolve(store, coverage_ref)
    assert coverage["payload"]["candidate_match"] == "MATCHED"
    assert canonical_bytes(service.context["candidate_version"]) == candidate_before


def test_n06_missing_coverage_does_not_create_candidate_or_read_novel(
    tmp_path: Path,
) -> None:
    store, service, _ = _service(tmp_path / "N-06")
    identity_ref = _identity(service)
    b01_catalog_hash = hashlib.sha256(fx.B01_OBJECT_SHAPES_PATH.read_bytes()).hexdigest()
    coverage_ref = service.add_coverage(
        **fx.coverage_kwargs("N-06", identity_ref, "MISSING")
    )
    coverage = _resolve(store, coverage_ref)
    assert coverage["payload"]["candidate_match"] == "MISSING"
    assert all(
        item["record_type"] != "M3_CANDIDATE_VERSION"
        for item in store.read_records()
    )
    assert hashlib.sha256(fx.B01_OBJECT_SHAPES_PATH.read_bytes()).hexdigest() == (
        b01_catalog_hash
    )
    assert "real_novel_read" not in store.events


def test_n07_partial_coverage_keeps_observation_identity_and_span_hash(
    tmp_path: Path,
) -> None:
    store, service, _ = _service(tmp_path / "N-07")
    identity_ref = _identity(service)
    kwargs = fx.coverage_kwargs("N-07", identity_ref, "PARTIAL")
    coverage_ref = service.add_coverage(**kwargs)
    payload = _resolve(store, coverage_ref)["payload"]
    assert payload["candidate_match"] == "PARTIAL"
    assert payload["source_observation_id"] == kwargs["source_observation_id"]
    assert payload["source_span_hash"] == kwargs["source_span_hash"]


def test_n08_mixed_projection_returns_only_open_diagnostic(tmp_path: Path) -> None:
    store, service, _ = _service(tmp_path / "N-08")
    identity_ref = _identity(service)
    open_ref = _add_diagnostic(service, "N-08-OPEN", identity_ref)
    superseded_ref = _add_diagnostic(service, "N-08-SUPERSEDED", identity_ref)
    closed_ref = _add_diagnostic(service, "N-08-CLOSED", identity_ref)
    service.append_lifecycle(
        diagnostic_ref=superseded_ref,
        lifecycle_sequence=1,
        event="SUPERSEDED_BY_PATCH_REVIEW",
        effective_at="2026-08-28T12:30:00Z",
        reason_code="PATCH_REVIEW_ACCEPTED",
        created_at="2026-08-28T12:30:00Z",
    )
    service.append_lifecycle(
        diagnostic_ref=closed_ref,
        lifecycle_sequence=1,
        event="CLOSED",
        effective_at="2026-08-28T12:31:00Z",
        reason_code="MANUAL_REVIEW_COMPLETE",
        created_at="2026-08-28T12:31:00Z",
    )
    result = project_open_diagnostics(
        context=service.context, records=store.read_records()
    )
    assert result["open_diagnostic_refs"] == [open_ref]
    assert superseded_ref not in result["open_diagnostic_refs"]
    assert closed_ref not in result["open_diagnostic_refs"]


def test_n09_projection_is_identical_after_read_order_shuffle(tmp_path: Path) -> None:
    store, service, _ = _service(tmp_path / "N-09")
    identity_ref = _identity(service)
    _add_diagnostic(service, "N-09-OPEN-B", identity_ref)
    open_a = _add_diagnostic(service, "N-09-OPEN-A", identity_ref)
    closed_ref = _add_diagnostic(service, "N-09-CLOSED", identity_ref)
    service.append_lifecycle(
        diagnostic_ref=closed_ref,
        lifecycle_sequence=1,
        event="CLOSED",
        effective_at="2026-08-28T12:31:00Z",
        reason_code="MANUAL_REVIEW_COMPLETE",
        created_at="2026-08-28T12:31:00Z",
    )
    records = store.read_records()
    ordered = project_open_diagnostics(context=service.context, records=records)
    reversed_result = project_open_diagnostics(
        context=service.context, records=list(reversed(records))
    )
    interleaved = records[::2] + records[1::2]
    shuffled_result = project_open_diagnostics(
        context=service.context, records=interleaved
    )
    assert canonical_bytes(ordered) == canonical_bytes(reversed_result)
    assert canonical_bytes(ordered) == canonical_bytes(shuffled_result)
    assert open_a in ordered["open_diagnostic_refs"]
    assert ordered["open_diagnostic_refs"] == sorted(
        ordered["open_diagnostic_refs"],
        key=lambda ref: (ref["record_id"], ref["record_version"], ref["record_hash"]),
    )


def test_f01_global_a_missing_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-01"
    upstream = fx.exact_upstream_fixture()
    upstream["admission_bytes"] = None
    _assert_failure_without_visible_write(
        root,
        lambda: _service(root, upstream),
        {"B02_A_ADMISSION_REQUIRED"},
    )

    build_store, build_service, _ = _service(tmp_path / "F-01-build")
    identity_ref = _identity(build_service)
    identity = _resolve(build_store, identity_ref)
    diagnostic = DiagnosticRecorder.build(
        context=build_service.context,
        **fx.diagnostic_kwargs("F-01-BYPASS", build_service.context, identity_ref),
    )
    lifecycle = DiagnosticLifecycleWriter.build(
        diagnostic_ref=record_ref(diagnostic),
        lifecycle_sequence=1,
        event="CLOSED",
        effective_at="2026-08-28T12:30:00Z",
        reason_code="DIRECT_BYPASS",
        created_at="2026-08-28T12:30:00Z",
    )
    coverage = CoverageRecorder.build(
        context=build_service.context,
        **fx.coverage_kwargs("F-01-BYPASS", identity_ref, "MATCHED"),
    )
    direct_calls = (
        lambda store: DiagnosticRecorderIdentityRegistry.register(
            identity, commit_record=None
        ),
        lambda store: DiagnosticRecorder.record(
            store,
            diagnostic,
            context=build_service.context,
            commit_record=None,
        ),
        lambda store: DiagnosticLifecycleWriter.append(
            store, lifecycle, commit_record=None
        ),
        lambda store: CoverageRecorder.record(
            store,
            coverage,
            context=build_service.context,
            commit_record=None,
        ),
    )
    for index, direct_call in enumerate(direct_calls, start=1):
        bypass_root = tmp_path / f"F-01-direct-writer-{index}"
        locked_store = FixtureStore(bypass_root)
        _assert_failure_without_visible_write(
            bypass_root,
            lambda direct_call=direct_call, store=locked_store: direct_call(store),
            {"B02_ADMISSION_CAPABILITY_REQUIRED"},
        )

    assert not hasattr(store_module, "_STORE_ADMISSION_TOKEN")
    assert not hasattr(build_store, "stage")
    assert not hasattr(build_store, "_unlock_after_admission")
    assert not hasattr(build_store, "_admission_capability")
    assert not hasattr(build_service, "_writer_capability")
    with pytest.raises(AttributeError):
        build_store._admission_capability = object()  # type: ignore[attr-defined]


def test_f02_global_a_drift_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-02"
    upstream = fx.exact_upstream_fixture()
    upstream["admission_bytes"] = upstream["admission_bytes"].replace(
        b"019df751641533c7de4d56aa38f50747fb564036", b"0" * 40, 1
    )
    _assert_failure_without_visible_write(
        root,
        lambda: _service(root, upstream),
        {"B02_A_ADMISSION_DRIFT"},
    )


def test_f03_b01_merge_receipt_missing_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-03"
    upstream = fx.exact_upstream_fixture()
    upstream["merge_receipt_bytes"] = None
    _assert_failure_without_visible_write(
        root,
        lambda: _service(root, upstream),
        {"B02_B01_MERGE_REQUIRED"},
    )


def test_f04_b01_merge_unreachable_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-04"
    upstream = fx.exact_upstream_fixture()
    upstream["merge_receipt_bytes"] = upstream["merge_receipt_bytes"].replace(
        b'"merge_commit_reachable_from_current_main": true',
        b'"merge_commit_reachable_from_current_main": false',
        1,
    )
    _assert_failure_without_visible_write(
        root,
        lambda: _service(root, upstream),
        {"B02_B01_MERGE_REQUIRED", "B02_B01_MAIN_UNREACHABLE"},
    )


def test_f05_b01_record_ref_drift_has_zero_visible_write(tmp_path: Path) -> None:
    cases = (
        (
            b"09e4a6f59c35d7a9694976e6fb5bf3f41690dd322deb2f57aa7e9969a9c187cf",
            b"0" * 64,
        ),
        (b"POLICY_FIXTURE_READ_ONLY", b"RUN_INTERNAL_READ_ONLY"),
    )
    for index, (old, new) in enumerate(cases, start=1):
        root = tmp_path / f"F-05-{index}"
        upstream = fx.exact_upstream_fixture()
        upstream["merge_receipt_bytes"] = upstream["merge_receipt_bytes"].replace(
            old, new, 1
        )
        _assert_failure_without_visible_write(
            root,
            lambda upstream=upstream, root=root: _service(root, upstream),
            {"B02_B01_MERGE_REQUIRED", "B02_B01_RECORD_REF_DRIFT"},
        )

    forged_root = tmp_path / "F-05-forged-but-internally-consistent"
    forged = fx.exact_upstream_fixture()
    candidate = next(
        record
        for record in forged["reference_records"]
        if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    fake_candidate = deepcopy(candidate)
    fake_candidate["payload"]["items"][0]["text"] = (
        "fabricated candidate that never came from merged B-01"
    )
    fake_candidate["payload"]["version_payload_hash"] = sha256_value(
        {
            key: value
            for key, value in fake_candidate["payload"].items()
            if key != "version_payload_hash"
        }
    )
    fake_candidate = fx.reseal_record(fake_candidate)
    forged["reference_records"] = [
        fake_candidate if record is candidate else record
        for record in forged["reference_records"]
    ]
    fake_locator = deepcopy(forged["lineage_locators"][0])
    fake_locator["candidate_version_ref"] = record_ref(fake_candidate)
    fake_locator["locator_hash"] = sha256_value(
        {
            key: value
            for key, value in fake_locator.items()
            if key != "locator_hash"
        }
    )
    forged["lineage_locators"] = [fake_locator]
    _assert_failure_without_visible_write(
        forged_root,
        lambda: _service(forged_root, forged),
        {"B02_B01_RECORD_REF_DRIFT"},
    )


def test_f06_lineage_locator_invalid_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-06"
    upstream = fx.exact_upstream_fixture()
    upstream["lineage_locators"][0]["json_pointer"] = "/items/999"
    _assert_failure_without_visible_write(
        root,
        lambda: _service(root, upstream),
        {"B02_LINEAGE_LOCATOR_INVALID"},
    )


def test_f07_evidence_out_of_scope_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-07"
    store, service, _ = _service(root)
    identity_ref = _identity(service)
    invalid_evidence = deepcopy(service.context["origin_attempt_refs"][0])
    invalid_evidence["record_id"] = "attempt_outside_candidate_version"
    invalid_evidence["record_hash"] = "f" * 64
    kwargs = fx.diagnostic_kwargs("F-07", service.context, identity_ref)
    kwargs["evidence_refs"] = [invalid_evidence]
    _assert_failure_without_visible_write(
        store.root,
        lambda: service.add_diagnostic(**kwargs),
        {"B02_EVIDENCE_OUT_OF_SCOPE"},
    )

    sealed_before = canonical_bytes(service.context)
    exposed = service.context
    exposed["origin_attempt_refs"].append(invalid_evidence)
    exposed["candidate_version"]["record_hash"] = "e" * 64
    exposed["lineage_locators"][0]["lineage_locator_hash"] = "d" * 64
    exposed["candidate_version"]["payload"]["chapter_revision_ref"][
        "revision_no"
    ] = 999
    assert canonical_bytes(service.context) == sealed_before
    with pytest.raises(AttributeError):
        service.context = exposed  # type: ignore[misc]

    forged_kwargs = fx.diagnostic_kwargs("F-07-CONTEXT", exposed, identity_ref)
    _assert_failure_without_visible_write(
        store.root,
        lambda: service.add_diagnostic(**forged_kwargs),
        {"B02_EVIDENCE_OUT_OF_SCOPE", "B02_LINEAGE_LOCATOR_INVALID"},
    )


def test_f08_diagnostic_overwrite_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-08"
    store, service, _ = _service(root)
    identity_ref = _identity(service)
    _add_diagnostic(service, "F-08", identity_ref, axis="FACT_COMPLETENESS")
    _assert_failure_without_visible_write(
        store.root,
        lambda: _add_diagnostic(
            service, "F-08", identity_ref, axis="CONTRADICTORY_AXIS"
        ),
        {"B02_IMMUTABLE_ALREADY_EXISTS"},
    )


def test_f09_same_identity_different_bytes_has_zero_visible_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "F-09"
    store, service, _ = _service(root)
    _identity(service)
    _assert_failure_without_visible_write(
        store.root,
        lambda: service.register_identity(
            writer_version="b02-fixture-v1", created_at="2026-08-28T12:02:00Z"
        ),
        {"B02_IMMUTABLE_ALREADY_EXISTS"},
    )


def test_f10_lifecycle_same_sequence_conflict_has_zero_visible_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "F-10"
    store, service, _ = _service(root)
    identity_ref = _identity(service)
    diagnostic_ref = _add_diagnostic(service, "F-10", identity_ref)
    service.append_lifecycle(
        diagnostic_ref=diagnostic_ref,
        lifecycle_sequence=1,
        event="SUPERSEDED_BY_PATCH_REVIEW",
        effective_at="2026-08-28T12:30:00Z",
        reason_code="PATCH_REVIEW_ACCEPTED",
        created_at="2026-08-28T12:30:00Z",
    )
    _assert_failure_without_visible_write(
        store.root,
        lambda: service.append_lifecycle(
            diagnostic_ref=diagnostic_ref,
            lifecycle_sequence=1,
            event="CLOSED",
            effective_at="2026-08-28T12:31:00Z",
            reason_code="MANUAL_REVIEW_COMPLETE",
            created_at="2026-08-28T12:31:00Z",
        ),
        {"B02_LIFECYCLE_SEQUENCE_CONFLICT"},
    )


def test_f11_lifecycle_reverse_order_has_zero_visible_write(tmp_path: Path) -> None:
    sequence_root = tmp_path / "F-11-sequence"
    store, service, _ = _service(sequence_root)
    identity_ref = _identity(service)
    diagnostic_ref = _add_diagnostic(service, "F-11-SEQUENCE", identity_ref)
    service.append_lifecycle(
        diagnostic_ref=diagnostic_ref,
        lifecycle_sequence=2,
        event="CLOSED",
        effective_at="2026-08-28T12:30:00Z",
        reason_code="MANUAL_REVIEW_COMPLETE",
        created_at="2026-08-28T12:30:00Z",
    )
    _assert_failure_without_visible_write(
        store.root,
        lambda: service.append_lifecycle(
            diagnostic_ref=diagnostic_ref,
            lifecycle_sequence=1,
            event="CLOSED",
            effective_at="2026-08-28T12:31:00Z",
            reason_code="LATE_LOWER_SEQUENCE",
            created_at="2026-08-28T12:31:00Z",
        ),
        {"B02_LIFECYCLE_ORDER_CONFLICT"},
    )

    time_root = tmp_path / "F-11-time"
    time_store, time_service, _ = _service(time_root)
    time_identity = _identity(time_service)
    time_diagnostic = _add_diagnostic(time_service, "F-11-TIME", time_identity)
    _assert_failure_without_visible_write(
        time_store.root,
        lambda: time_service.append_lifecycle(
            diagnostic_ref=time_diagnostic,
            lifecycle_sequence=1,
            event="CLOSED",
            effective_at="2026-08-28T12:09:59Z",
            reason_code="TIME_BEFORE_DIAGNOSTIC",
            created_at="2026-08-28T12:30:00Z",
        ),
        {"B02_LIFECYCLE_ORDER_CONFLICT"},
    )


def test_f12_same_time_different_event_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-12"
    store, service, _ = _service(root)
    identity_ref = _identity(service)
    diagnostic_ref = _add_diagnostic(service, "F-12", identity_ref)
    first = DiagnosticLifecycleWriter.build(
        diagnostic_ref=diagnostic_ref,
        lifecycle_sequence=1,
        event="SUPERSEDED_BY_PATCH_REVIEW",
        effective_at="2026-08-28T12:30:00Z",
        reason_code="PATCH_REVIEW_ACCEPTED",
        created_at="2026-08-28T12:30:00Z",
    )
    second = DiagnosticLifecycleWriter.build(
        diagnostic_ref=diagnostic_ref,
        lifecycle_sequence=2,
        event="CLOSED",
        effective_at="2026-08-28T12:30:00Z",
        reason_code="MANUAL_REVIEW_COMPLETE",
        created_at="2026-08-28T12:31:00Z",
    )
    records = [*store.read_records(), first, second]
    _assert_failure_without_visible_write(
        store.root,
        lambda: project_open_diagnostics(context=service.context, records=records),
        {"B02_PROJECTION_INVALID"},
    )

    before_time = DiagnosticLifecycleWriter.build(
        diagnostic_ref=diagnostic_ref,
        lifecycle_sequence=1,
        event="CLOSED",
        effective_at="2026-08-28T12:09:59Z",
        reason_code="TIME_BEFORE_DIAGNOSTIC",
        created_at="2026-08-28T12:30:00Z",
    )
    _assert_failure_without_visible_write(
        store.root,
        lambda: project_open_diagnostics(
            context=service.context,
            records=[*store.read_records(), before_time],
        ),
        {"B02_PROJECTION_INVALID"},
    )


def test_f13_append_after_terminal_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-13"
    store, service, _ = _service(root)
    identity_ref = _identity(service)
    diagnostic_ref = _add_diagnostic(service, "F-13", identity_ref)
    service.append_lifecycle(
        diagnostic_ref=diagnostic_ref,
        lifecycle_sequence=1,
        event="CLOSED",
        effective_at="2026-08-28T12:30:00Z",
        reason_code="MANUAL_REVIEW_COMPLETE",
        created_at="2026-08-28T12:30:00Z",
    )
    _assert_failure_without_visible_write(
        store.root,
        lambda: service.append_lifecycle(
            diagnostic_ref=diagnostic_ref,
            lifecycle_sequence=2,
            event="CLOSED",
            effective_at="2026-08-28T12:31:00Z",
            reason_code="ILLEGAL_REOPEN_ATTEMPT",
            created_at="2026-08-28T12:31:00Z",
        ),
        {"B02_LIFECYCLE_TERMINAL"},
    )


def test_f14_revision_or_segment_drift_has_zero_visible_write(tmp_path: Path) -> None:
    diagnostic_root = tmp_path / "F-14-diagnostic"
    store, service, _ = _service(diagnostic_root)
    identity_ref = _identity(service)
    diagnostic = DiagnosticRecorder.build(
        context=service.context,
        **fx.diagnostic_kwargs("F-14-D", service.context, identity_ref),
    )
    diagnostic["payload"]["seg"] = 2
    diagnostic = fx.reseal_record(diagnostic)
    _assert_failure_without_visible_write(
        store.root,
        lambda: DiagnosticRecorder.record(
            store,
            diagnostic,
            context=service.context,
            commit_record=lambda _: pytest.fail("invalid Diagnostic reached commit"),
        ),
        {"B02_SCOPE_MISMATCH"},
    )

    coverage_root = tmp_path / "F-14-coverage"
    coverage_store, coverage_service, _ = _service(coverage_root)
    coverage_identity = _identity(coverage_service)
    coverage = CoverageRecorder.build(
        context=coverage_service.context,
        **fx.coverage_kwargs("F-14-C", coverage_identity, "MATCHED"),
    )
    coverage["payload"]["chapter_revision_ref"]["revision_no"] = 8
    coverage = fx.reseal_record(coverage)
    _assert_failure_without_visible_write(
        coverage_store.root,
        lambda: CoverageRecorder.record(
            coverage_store,
            coverage,
            context=coverage_service.context,
            commit_record=lambda _: pytest.fail("invalid Coverage reached commit"),
        ),
        {"B02_SCOPE_MISMATCH"},
    )


def test_f15_invalid_coverage_enum_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-15"
    store, service, _ = _service(root)
    identity_ref = _identity(service)
    invalid = CoverageRecorder.build(
        context=service.context,
        **fx.coverage_kwargs("F-15", identity_ref, "UNKNOWN"),
    )
    _assert_failure_without_visible_write(
        store.root,
        lambda: CoverageRecorder.record(
            store,
            invalid,
            context=service.context,
            commit_record=lambda _: pytest.fail("invalid Coverage reached commit"),
        ),
        {"B02_COVERAGE_MATCH_INVALID"},
    )


def test_f16_candidate_and_pointer_writes_are_guarded_with_zero_visible_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "F-16"
    for event in ("candidate_version_write", "pointer_write"):
        _assert_failure_without_visible_write(
            root,
            lambda event=event: guard_runtime_event(event),
            {"B02_CANDIDATE_WRITE_FORBIDDEN"},
        )


def test_f17_write_set_escape_has_zero_visible_write(tmp_path: Path) -> None:
    root = tmp_path / "F-17"
    repository_root = Path(__file__).resolve().parents[2]
    outside_write_set = repository_root / "work" / "f17-outside-b02-write-set"
    _assert_failure_without_visible_write(
        root,
        lambda: FixtureStore(outside_write_set),
        {"B02_WRITE_SET_ESCAPE"},
    )

    valid_store, valid_service, _ = _service(tmp_path / "F-17-envelope-source")
    valid_identity_ref = _identity(valid_service)
    valid_identity = _resolve(valid_store, valid_identity_ref)
    envelope_cases = (
        ("record_type", "/tmp/b02-path-escape"),
        ("record_version", 2),
        ("source_module", "M4"),
        ("access", "PUBLIC"),
        ("retention_class", "EPHEMERAL"),
    )
    envelope_store = FixtureStore(tmp_path / "F-17-envelope")
    for field, value in envelope_cases:
        mutated = deepcopy(valid_identity)
        mutated[field] = value
        mutated = fx.reseal_record(mutated)
        _assert_failure_without_visible_write(
            envelope_store.root,
            lambda mutated=mutated: envelope_store.path_for(mutated),
            {"B02_OUTPUT_ENVELOPE_INVALID"},
        )

    for failure_point in (
        "after_mkdir",
        "after_pending_write",
        "after_candidate_readback",
    ):
        failure_root = tmp_path / f"F-17-{failure_point}"
        failing_store = FixtureStore(failure_root, failure_point=failure_point)
        failing_service = B02Service(
            failing_store, **fx.exact_upstream_fixture()
        )
        _assert_failure_without_visible_write(
            failure_root,
            lambda service=failing_service: service.register_identity(
                writer_version="b02-fixture-v1",
                created_at="2026-08-28T12:01:00Z",
            ),
            {"B02_SIMULATED_TRANSACTION_FAILURE"},
        )
        assert "immutable_record_atomic_write" not in failing_store.events

    replace_root = tmp_path / "F-17-replace-syscall"
    replace_store = FixtureStore(replace_root)
    replace_service = B02Service(replace_store, **fx.exact_upstream_fixture())

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated replace syscall failure")

    original_replace = store_module.os.replace
    store_module.os.replace = fail_replace
    try:
        _assert_failure_without_visible_write(
            replace_root,
            lambda: replace_service.register_identity(
                writer_version="b02-fixture-v1",
                created_at="2026-08-28T12:01:00Z",
            ),
            {"B02_TRANSACTION_WRITE_FAILED"},
        )
    finally:
        store_module.os.replace = original_replace
    assert "private_candidate_readback_validated" in replace_store.events
    assert "immutable_record_atomic_write" not in replace_store.events

    pending_root = tmp_path / "F-17-preexisting-pending"
    pending_store = FixtureStore(pending_root)
    pending_path = pending_root / "records" / "M3_DIAGNOSTIC" / "stale.pending"
    pending_path.parent.mkdir(parents=True)
    pending_path.write_bytes(b"stale")
    _assert_failure_without_visible_write(
        pending_root,
        pending_store.read_records,
        {"B02_TRANSACTION_PENDING_FOUND"},
    )

    self_check_source = (Path(__file__).resolve().parent / "self_check.py").read_text(
        encoding="utf-8"
    )
    assert "additional_write_roots" not in self_check_source
    assert "candidate_path" not in self_check_source
    assert 'action="store_true"' in self_check_source


def test_f18_runtime_paths_are_guarded_with_zero_visible_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "F-18"
    forbidden = (
        "network",
        "socket",
        "http",
        "dns",
        "model_api",
        "subprocess",
        "fork",
        "exec",
        "dynamic_import",
        "dynamic_eval",
    )
    for event in forbidden:
        _assert_failure_without_visible_write(
            root,
            lambda event=event: guard_runtime_event(event),
            {"B02_RUNTIME_EVENT_FORBIDDEN"},
        )

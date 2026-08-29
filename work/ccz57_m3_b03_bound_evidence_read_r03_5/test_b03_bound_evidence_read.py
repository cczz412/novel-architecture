"""Offline acceptance checks for the r03.5 bound-evidence B-03 shell."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from b03_contracts import (
    B03ContractError,
    REPOSITORY_ROOT,
    build_output_record,
    current_trusted_time_head,
    make_input_record,
    record_ref,
    require_current_trusted_time,
)
from fixtures import (
    exact_context,
    policy_record,
    product_input,
    trusted_time_records,
)
from service import B03Service

MODULE_ROOT = Path(__file__).resolve().parent


def make_service(
    tmp_path: Path, *, times: list[dict[str, object]] | None = None
) -> B03Service:
    return B03Service(
        tmp_path / "b03-state",
        upstream=exact_context(),
        policy=policy_record(),
        trusted_times=trusted_time_records() if times is None else times,
    )


def admitted_chain(
    instance: B03Service,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    request = instance.request(
        product_input(instance.context), created_at="2026-08-29T06:01:00Z"
    )
    consent = instance.consent(
        request,
        actor="fixture-author",
        created_at="2026-08-29T06:01:01Z",
    )
    authorization = instance.authorize(
        request, consent, created_at="2026-08-29T06:01:02Z"
    )
    return request, consent, authorization


def trusted_time(sequence: int, timestamp: str) -> dict[str, object]:
    return make_input_record(
        record_type="M3_TRUSTED_TIME_RECEIPT",
        record_id=f"time:fixture:{sequence}",
        created_at="2026-08-29T06:00:00Z",
        payload={
            "time_source_id": "fixture-clock-b03",
            "trusted_evaluation_time": timestamp,
            "monotonic_sequence": sequence,
            "clock_mode": "DETERMINISTIC_FIXTURE",
        },
    )


def code(error: pytest.ExceptionInfo[B03ContractError]) -> str:
    return error.value.code


def test_candidate_fact_reads_only_bound_evidence_without_public_store(
    tmp_path: Path,
) -> None:
    instance = make_service(tmp_path)
    request, consent, authorization = admitted_chain(instance)
    source_slice = instance.read(request, consent, authorization)
    core = instance.slice_core(source_slice)
    assert core is not None
    expected = instance.context["candidate_version"]["payload"]["items"][0]["evidence"]
    assert instance.read_slice_content(source_slice) == expected
    assert instance.plaintext_present(source_slice)
    binding = core["core"]["payload"]["evidence_binding"]
    assert len(binding["match_locations"]) == 2
    assert "range" not in core["core"]["payload"]
    assert not hasattr(instance, "store")
    assert not hasattr(instance, "append_record")
    assert instance.state_counts() == {
        "records": 3,
        "source_slices": 1,
        "tombstones": 0,
    }


@pytest.mark.parametrize(
    "field",
    [
        "range",
        "requested_range",
        "authorized_range",
        "start",
        "end",
        "max_chars",
        "max_characters",
    ],
)
def test_legacy_caller_ranges_are_rejected_before_any_write(
    tmp_path: Path, field: str
) -> None:
    instance = make_service(tmp_path)
    rejected = product_input(instance.context)
    rejected[field] = 1
    before = instance.snapshot()
    with pytest.raises(B03ContractError) as caught:
        instance.request(rejected, created_at="2026-08-29T06:01:00Z")
    assert code(caught) == "B03_CALLER_RANGE_FORBIDDEN"
    assert instance.snapshot() == before == {}


def test_formal_ledger_route_fails_closed_without_adapter(tmp_path: Path) -> None:
    instance = make_service(tmp_path)
    rejected = product_input(instance.context)
    rejected["subject"] = {"kind": "FORMAL_LEDGER_ITEM"}
    with pytest.raises(B03ContractError) as caught:
        instance.request(rejected, created_at="2026-08-29T06:01:00Z")
    assert code(caught) == "B03_FORMAL_LEDGER_ADAPTER_REQUIRED"
    assert instance.snapshot() == {}
    assert instance.events == ()


def test_binding_drift_fails_before_request_write(tmp_path: Path) -> None:
    instance = make_service(tmp_path)
    rejected = product_input(instance.context)
    rejected["evidence_binding"] = deepcopy(rejected["evidence_binding"])
    rejected["evidence_binding"]["binding_hash"] = "0" * 64
    with pytest.raises(B03ContractError) as caught:
        instance.request(rejected, created_at="2026-08-29T06:01:00Z")
    assert code(caught) == "B03_EVIDENCE_BINDING_DRIFT"
    assert instance.snapshot() == {}


def test_empty_actor_is_rejected_before_consent_write(tmp_path: Path) -> None:
    instance = make_service(tmp_path)
    request = instance.request(
        product_input(instance.context), created_at="2026-08-29T06:01:00Z"
    )
    before = instance.snapshot()
    with pytest.raises(B03ContractError) as caught:
        instance.consent(request, actor="", created_at="2026-08-29T06:01:01Z")
    assert code(caught) == "B03_CONSENT_INVALID"
    assert instance.snapshot() == before
    assert instance.state_counts()["records"] == 1


def test_stolen_internal_capability_still_cannot_commit_bad_or_paired_records(
    tmp_path: Path,
) -> None:
    instance = make_service(tmp_path)
    request = instance.request(
        product_input(instance.context), created_at="2026-08-29T06:01:00Z"
    )
    forged_consent = build_output_record(
        record_type="M3_SOURCE_READ_CONSENT",
        created_at="2026-08-29T06:01:01Z",
        payload={
            "request_ref": request,
            "policy_ref": record_ref(instance.policy),
            "actor_identity": "",
            "authorization_mode": "POLICY_FIXTURE_ONLY",
            "purpose": "BOUND_EVIDENCE_REVIEW",
            "request_scope_hash": "0" * 64,
            "issued_at": "2026-08-29T06:01:00Z",
            "expires_at": "2026-08-29T06:10:00Z",
            "consent_sequence": 0,
        },
    )
    store = getattr(instance, "_B03Service__store")
    capability = getattr(instance, "_B03Service__commit_capability")
    before = instance.snapshot()
    with pytest.raises(B03ContractError) as caught:
        store.append_record(
            forged_consent,
            expected_type="M3_SOURCE_READ_CONSENT",
            commit_capability=capability,
        )
    assert code(caught) == "B03_REQUEST_SCOPE_HASH_MISMATCH"
    assert instance.snapshot() == before

    forged_retention = build_output_record(
        record_type="M3_SOURCE_SLICE_RETENTION_RECEIPT",
        created_at="2026-08-29T06:02:00Z",
        payload={},
    )
    with pytest.raises(B03ContractError) as caught:
        store.append_record(
            forged_retention,
            expected_type="M3_SOURCE_SLICE_RETENTION_RECEIPT",
            commit_capability=capability,
        )
    assert code(caught) == "B03_WRITER_SCOPE_ESCAPE"
    assert instance.snapshot() == before


def test_consent_cannot_authorize_a_different_request_or_purpose(
    tmp_path: Path,
) -> None:
    instance = make_service(tmp_path)
    first = product_input(instance.context)
    request_one = instance.request(first, created_at="2026-08-29T06:01:00Z")
    consent_one = instance.consent(
        request_one,
        actor="fixture-author",
        created_at="2026-08-29T06:01:01Z",
    )
    second = product_input(instance.context)
    second["purpose"] = "OTHER_REVIEW"
    request_two = instance.request(second, created_at="2026-08-29T06:01:03Z")
    before = instance.snapshot()
    with pytest.raises(B03ContractError) as caught:
        instance.authorize(request_two, consent_one, created_at="2026-08-29T06:01:04Z")
    assert code(caught) == "B03_REQUEST_SCOPE_HASH_MISMATCH"
    assert instance.snapshot() == before


def test_individually_valid_request_and_authorization_chains_cannot_be_spliced(
    tmp_path: Path,
) -> None:
    instance = make_service(tmp_path)
    request_one, _, _ = admitted_chain(instance)
    second = product_input(instance.context)
    second["purpose"] = "OTHER_REVIEW"
    request_two = instance.request(second, created_at="2026-08-29T06:01:03Z")
    consent_two = instance.consent(
        request_two,
        actor="fixture-author",
        created_at="2026-08-29T06:01:04Z",
    )
    authorization_two = instance.authorize(
        request_two,
        consent_two,
        created_at="2026-08-29T06:01:05Z",
    )
    before = instance.snapshot()
    with pytest.raises(B03ContractError) as caught:
        instance.read(request_one, consent_two, authorization_two)
    assert code(caught) == "B03_AUTHORIZATION_BINDING_DRIFT"
    assert instance.snapshot() == before
    assert instance.state_counts()["source_slices"] == 0


def test_revocation_atomically_purges_plaintext_and_slice_core(tmp_path: Path) -> None:
    instance = make_service(tmp_path)
    request, consent, authorization = admitted_chain(instance)
    source_slice = instance.read(request, consent, authorization)
    lifecycle_ref = instance.lifecycle(
        consent,
        event="REVOKED",
        effective_at="2026-08-29T06:02:00Z",
        created_at="2026-08-29T06:02:00Z",
    )
    assert lifecycle_ref["record_type"] == "M3_SOURCE_READ_CONSENT_LIFECYCLE_RECEIPT"
    assert not instance.plaintext_present(source_slice)
    assert instance.slice_core(source_slice) is None
    assert instance.tombstone(source_slice) is not None
    assert instance.state_counts() == {
        "records": 5,
        "source_slices": 0,
        "tombstones": 1,
    }
    with pytest.raises(B03ContractError) as caught:
        instance.read_slice_content(source_slice)
    assert code(caught) == "TOMBSTONED_CONTENT_UNAVAILABLE"


def test_manual_purge_keeps_only_five_key_tombstone_and_receipt(tmp_path: Path) -> None:
    instance = make_service(tmp_path)
    request, consent, authorization = admitted_chain(instance)
    source_slice = instance.read(request, consent, authorization)
    expected = instance.context["candidate_version"]["payload"]["items"][0]["evidence"]
    assert not instance.state_contains(expected)
    assert instance.content_file_contains(expected)
    receipt = instance.purge(source_slice)
    tombstone = instance.tombstone(source_slice)
    assert receipt["record_type"] == "M3_SOURCE_SLICE_RETENTION_RECEIPT"
    assert tombstone is not None
    assert set(tombstone) == {
        "authorized_source_slice_ref",
        "evidence_binding_hash",
        "evidence_sha256",
        "content_bytes_retained",
        "storage_state",
    }
    assert instance.slice_core(source_slice) is None
    assert not instance.plaintext_present(source_slice)
    assert not instance.state_contains(expected)
    assert not instance.content_file_contains(expected)
    assert instance.storage_residue() == []
    assert instance.state_counts() == {
        "records": 4,
        "source_slices": 0,
        "tombstones": 1,
    }


def test_tombstone_hashes_are_derived_from_the_sealed_slice(tmp_path: Path) -> None:
    instance = make_service(tmp_path)
    request, consent, authorization = admitted_chain(instance)
    source_slice = instance.read(request, consent, authorization)
    binding = instance.slice_core(source_slice)["core"]["payload"]["evidence_binding"]
    instance.purge(source_slice)
    tombstone = instance.tombstone(source_slice)
    assert tombstone["evidence_binding_hash"] == binding["binding_hash"]
    assert tombstone["evidence_sha256"] == binding["evidence_sha256"]


def test_stale_trusted_time_ref_is_rejected(tmp_path: Path) -> None:
    instance = make_service(tmp_path)
    stale = record_ref(instance.trusted_times[0])
    with pytest.raises(B03ContractError) as caught:
        require_current_trusted_time(stale, instance.trusted_times)
    assert code(caught) == "B03_TRUSTED_TIME_STALE"
    assert instance.snapshot() == {}


def test_revocation_between_h1_and_h2_never_publishes_plaintext(tmp_path: Path) -> None:
    instance = make_service(tmp_path)
    request, consent, authorization = admitted_chain(instance)

    def revoke() -> None:
        instance.set_test_hook("before_publish", None)
        instance.lifecycle(
            consent,
            event="REVOKED",
            effective_at="2026-08-29T06:02:00Z",
            created_at="2026-08-29T06:02:00Z",
        )

    instance.set_test_hook("before_publish", revoke)
    with pytest.raises(B03ContractError) as caught:
        instance.read(request, consent, authorization)
    assert code(caught) == "B03_SOURCE_READ_NOT_ACTIVE"
    assert instance.state_counts()["source_slices"] == 0
    assert instance.state_counts()["tombstones"] == 0


def test_publish_transaction_baseexception_rolls_back_and_reopens_cleanly(
    tmp_path: Path,
) -> None:
    instance = make_service(tmp_path)
    request, consent, authorization = admitted_chain(instance)
    before = instance.snapshot()

    def interrupt() -> None:
        raise KeyboardInterrupt("simulated process interruption")

    instance.set_test_hook("before_transaction_commit", interrupt)
    with pytest.raises(KeyboardInterrupt):
        instance.read(request, consent, authorization)
    instance.set_test_hook("before_transaction_commit", None)
    assert instance.snapshot() == before
    assert instance.state_counts()["source_slices"] == 0
    instance.close()
    reopened = make_service(tmp_path)
    assert reopened.snapshot() == before
    assert reopened.state_counts()["source_slices"] == 0
    assert reopened.storage_residue() == []


def test_retention_transaction_failure_restores_plaintext_and_core(
    tmp_path: Path,
) -> None:
    instance = make_service(tmp_path)
    request, consent, authorization = admitted_chain(instance)
    source_slice = instance.read(request, consent, authorization)
    before = instance.snapshot()

    def fail_commit() -> None:
        raise OSError("simulated retention commit failure")

    instance.set_test_hook("before_transaction_commit", fail_commit)
    with pytest.raises(OSError):
        instance.purge(source_slice)
    instance.set_test_hook("before_transaction_commit", None)
    assert instance.snapshot() == before
    assert instance.plaintext_present(source_slice)
    assert instance.slice_core(source_slice) is not None
    assert instance.tombstone(source_slice) is None
    assert instance.storage_residue() == []


def test_lifecycle_and_purge_are_one_transaction(tmp_path: Path) -> None:
    instance = make_service(tmp_path)
    request, consent, authorization = admitted_chain(instance)
    source_slice = instance.read(request, consent, authorization)
    before = instance.snapshot()

    def interrupt() -> None:
        raise KeyboardInterrupt("lifecycle transaction interrupted")

    instance.set_test_hook("before_transaction_commit", interrupt)
    with pytest.raises(KeyboardInterrupt):
        instance.lifecycle(
            consent,
            event="REVOKED",
            effective_at="2026-08-29T06:02:00Z",
            created_at="2026-08-29T06:02:00Z",
        )
    instance.set_test_hook("before_transaction_commit", None)
    assert instance.snapshot() == before
    assert instance.plaintext_present(source_slice)
    assert instance.tombstone(source_slice) is None


def test_time_head_and_expiry_purge_are_one_transaction(tmp_path: Path) -> None:
    instance = make_service(tmp_path)
    request, consent, authorization = admitted_chain(instance)
    source_slice = instance.read(request, consent, authorization)
    before = instance.snapshot()

    def interrupt() -> None:
        raise KeyboardInterrupt("time transaction interrupted")

    instance.set_test_hook("before_transaction_commit", interrupt)
    with pytest.raises(KeyboardInterrupt):
        instance.advance_trusted_time(trusted_time(3, "2026-08-29T06:11:00Z"))
    instance.set_test_hook("before_transaction_commit", None)
    assert instance.snapshot() == before
    assert instance.trusted_times[-1]["payload"]["monotonic_sequence"] == 2
    assert instance.plaintext_present(source_slice)
    instance.advance_trusted_time(trusted_time(3, "2026-08-29T06:11:00Z"))
    assert instance.trusted_times[-1]["payload"]["monotonic_sequence"] == 3
    assert not instance.plaintext_present(source_slice)
    assert instance.tombstone(source_slice) is not None


def test_invalid_lifecycle_and_superseded_without_replacement_write_nothing(
    tmp_path: Path,
) -> None:
    instance = make_service(tmp_path)
    _, consent, _ = admitted_chain(instance)
    before = instance.snapshot()
    with pytest.raises(B03ContractError) as caught:
        instance.lifecycle(
            consent,
            event="INVALID",
            effective_at="2026-08-29T06:02:00Z",
            created_at="2026-08-29T06:02:00Z",
        )
    assert code(caught) == "B03_LIFECYCLE_INVALID"
    assert instance.snapshot() == before
    with pytest.raises(B03ContractError) as caught:
        instance.lifecycle(
            consent,
            event="SUPERSEDED",
            effective_at="2026-08-29T06:02:00Z",
            created_at="2026-08-29T06:02:00Z",
        )
    assert code(caught) == "B03_LIFECYCLE_REPLACEMENT_INVALID"
    assert instance.snapshot() == before


def test_public_context_policy_and_time_copies_cannot_change_admission(
    tmp_path: Path,
) -> None:
    instance = make_service(tmp_path)
    exposed_context = instance.context
    exposed_policy = instance.policy
    exposed_times = instance.trusted_times
    exposed_context["candidate_version"]["payload"]["items"][0]["evidence"] = "forged"
    exposed_policy["payload"]["adjacent_prose_access"] = "ALLOW"
    exposed_times.append(trusted_time(3, "2026-08-29T06:03:00Z"))
    request, consent, authorization = admitted_chain(instance)
    source_slice = instance.read(request, consent, authorization)
    assert instance.read_slice_content(source_slice) == "甲走进北塔。"
    assert instance.trusted_times[-1]["payload"]["monotonic_sequence"] == 2


def test_new_authoritative_time_head_purges_for_old_service_instance(
    tmp_path: Path,
) -> None:
    root_times = trusted_time_records()
    old_instance = make_service(tmp_path, times=root_times)
    request, consent, authorization = admitted_chain(old_instance)
    source_slice = old_instance.read(request, consent, authorization)
    later_chain = [*root_times, trusted_time(3, "2026-08-29T06:11:00Z")]
    new_instance = make_service(tmp_path, times=later_chain)
    assert new_instance.tombstone(source_slice) is not None
    assert not old_instance.plaintext_present(source_slice)
    assert old_instance.trusted_times[-1]["payload"]["monotonic_sequence"] == 3
    with pytest.raises(B03ContractError) as caught:
        old_instance.read_slice_content(source_slice)
    assert code(caught) == "TOMBSTONED_CONTENT_UNAVAILABLE"


def test_stale_service_reopen_cannot_replace_newer_time_head(tmp_path: Path) -> None:
    first = make_service(tmp_path)
    first.advance_trusted_time(trusted_time(3, "2026-08-29T06:03:00Z"))
    with pytest.raises(B03ContractError) as caught:
        make_service(tmp_path, times=trusted_time_records())
    assert code(caught) == "B03_TRUSTED_TIME_STALE"
    assert first.trusted_times[-1]["payload"]["monotonic_sequence"] == 3


def test_write_root_outside_temp_or_unique_write_set_is_rejected(
    tmp_path: Path,
) -> None:
    escape = MODULE_ROOT.parent / f"_b03_escape_{tmp_path.name}"
    assert not escape.exists()
    with pytest.raises(B03ContractError) as caught:
        B03Service(
            escape,
            upstream=exact_context(),
            policy=policy_record(),
            trusted_times=trusted_time_records(),
        )
    assert code(caught) == "B03_WRITE_SET_VIOLATION"
    assert not escape.exists()
    assert escape.parent == REPOSITORY_ROOT / "work"


def test_symlink_root_and_database_file_are_rejected_before_use(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(target, target_is_directory=True)
    with pytest.raises(B03ContractError) as caught:
        B03Service(
            linked_root,
            upstream=exact_context(),
            policy=policy_record(),
            trusted_times=trusted_time_records(),
        )
    assert code(caught) == "B03_WRITE_SET_VIOLATION"

    database_root = tmp_path / "database-root"
    database_root.mkdir()
    outside = tmp_path / "outside.sqlite3"
    outside.write_bytes(b"do-not-touch")
    (database_root / "immutable-state.sqlite3").symlink_to(outside)
    with pytest.raises(B03ContractError) as caught:
        B03Service(
            database_root,
            upstream=exact_context(),
            policy=policy_record(),
            trusted_times=trusted_time_records(),
        )
    assert code(caught) == "B03_WRITE_SET_VIOLATION"
    assert outside.read_bytes() == b"do-not-touch"


def test_trusted_time_chain_still_rejects_ambiguous_same_sequence(
    tmp_path: Path,
) -> None:
    chain = trusted_time_records()
    drift = trusted_time(2, "2026-08-29T06:04:00Z")
    with pytest.raises(B03ContractError) as caught:
        current_trusted_time_head([*chain, drift])
    assert code(caught) == "B03_TRUSTED_TIME_HEAD_AMBIGUOUS"

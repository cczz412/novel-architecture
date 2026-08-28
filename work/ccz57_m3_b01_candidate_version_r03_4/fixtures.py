"""Synthetic normal and failure fixtures for the B-01 offline contract."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from b01_contract import (
    B01ContractError,
    B01Service,
    FixtureStore,
    build_root_candidate_version,
    canonical_bytes,
    guard_runtime_event,
    guard_write_path,
    make_lineage_locator,
    make_read_only_child,
    project_version_diff,
    sha256_value,
    state_counts,
    state_file_hash,
    validate_candidate_version,
    validate_lineage_locator,
)

CREATED_AT = "2026-08-28T12:00:00Z"
REVIEWED_HEAD_SHA = "9eafdac71f412be3f7b8ad5fd81ffc84c3de3a26"
MERGE_COMMIT_SHA = "019df751641533c7de4d56aa38f50747fb564036"
INTERFACE_MANIFEST_HASH = (
    "50c5c74c67678565693dd86c27dab20319a0d107bb9d196b21d23643843ca860"
)
REVISION_TEXT_SHA256 = sha256_value("synthetic chapter revision text")


def external_ref(
    record_type: str,
    record_id: str,
    *,
    record_version: int = 1,
    source_module: str,
) -> dict[str, Any]:
    return {
        "contract": "M3_IMMUTABLE_RECORD",
        "contract_version": "r03.3-candidate",
        "record_type": record_type,
        "record_id": record_id,
        "record_version": record_version,
        "record_contract_version": "r03.3-candidate",
        "record_hash": sha256_value(
            {
                "record_type": record_type,
                "record_id": record_id,
                "record_version": record_version,
                "source_module": source_module,
            }
        ),
        "access": "INTERNAL",
        "source_module": source_module,
    }


def valid_admission() -> dict[str, Any]:
    return {
        "receipt_type": "A_INTERFACE_ADMISSION_RECEIPT",
        "reviewed_head_sha": REVIEWED_HEAD_SHA,
        "merge_time_head_sha": REVIEWED_HEAD_SHA,
        "merge_commit_sha": MERGE_COMMIT_SHA,
        "current_main_sha": MERGE_COMMIT_SHA,
        "main_contains_merge": True,
        "readback_ok": True,
        "interface_manifest_hash": INTERFACE_MANIFEST_HASH,
        "expected_interface_manifest_hash": INTERFACE_MANIFEST_HASH,
    }


def chapter_revision_ref() -> dict[str, Any]:
    return external_ref(
        "CHAPTER_REVISION",
        "synthetic-chapter-001",
        record_version=7,
        source_module="FIXTURE-CHAPTER-STORE",
    )


def attempt_refs() -> list[dict[str, Any]]:
    return [
        external_ref(
            "RAW_ATTEMPT_RECEIPT",
            "synthetic-attempt-001",
            source_module="CCZ57-M3-A",
        )
    ]


def segment_inputs() -> list[dict[str, Any]]:
    return [
        {
            "seg": 1,
            "start_offset": 0,
            "end_offset": 12,
            "responsibility_text": "synthetic-a",
        },
        {
            "seg": 2,
            "start_offset": 12,
            "end_offset": 23,
            "responsibility_text": "synthetic-b",
        },
    ]


def base_request(*, raw_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "admission": valid_admission(),
        "project_scope_id": "fixture-project-001",
        "author_workspace_logical_key": "fixture-workspace-001",
        "chapter_revision_ref": chapter_revision_ref(),
        "revision_text_sha256": REVISION_TEXT_SHA256,
        "segment_inputs": segment_inputs(),
        "seg": 1,
        "origin_attempt_refs": attempt_refs(),
        "raw_items": (
            [{"text": "synthetic fact", "quote": "synthetic quote"}]
            if raw_items is None
            else raw_items
        ),
        "operation_id": "fixture-operation-001",
        "created_at": CREATED_AT,
    }


def _load_state(root: Path) -> dict[str, Any]:
    return json.loads((root / "state.json").read_text(encoding="utf-8"))


def _record_by_type(root: Path, record_type: str) -> dict[str, Any]:
    matches = [
        record
        for record in _load_state(root)["records"].values()
        if record["record_type"] == record_type
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one {record_type}, got {len(matches)}")
    return matches[0]


def _initialize(root: Path, **overrides: Any) -> dict[str, Any]:
    request = base_request()
    request.update(overrides)
    return B01Service(FixtureStore(root)).initialize_root_baseline(**request)


def _rehash_record(record: dict[str, Any]) -> None:
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )


def _capture_unchanged(
    root: Path, expected_code: str, action: Callable[[], Any]
) -> str:
    before_counts = state_counts(root / "state.json")
    before_hash = state_file_hash(root / "state.json")
    try:
        action()
    except B01ContractError as error:
        if error.code != expected_code:
            raise AssertionError(
                f"expected {expected_code}, got {error.code}"
            ) from error
    else:
        raise AssertionError(f"expected {expected_code}")
    after_counts = state_counts(root / "state.json")
    after_hash = state_file_hash(root / "state.json")
    if after_counts != before_counts or after_hash != before_hash:
        raise AssertionError(f"failure {expected_code} changed fixture state")
    return expected_code


def n01_nonempty_baseline(root: Path) -> dict[str, Any]:
    result = _initialize(root)
    candidate = _record_by_type(root, "M3_CANDIDATE_VERSION")
    if len(candidate["payload"]["items"]) != 1:
        raise AssertionError("nonempty baseline lost its item")
    return result


def n02_empty_baseline(root: Path) -> dict[str, Any]:
    result = _initialize(root, raw_items=[])
    candidate = _record_by_type(root, "M3_CANDIDATE_VERSION")
    if candidate["payload"]["items"] or candidate["payload"]["lineage_index"]:
        raise AssertionError("empty baseline is inconsistent")
    return result


def n03_segment_index_replay(root: Path) -> dict[str, Any]:
    left = root / "left"
    right = root / "right"
    left_result = _initialize(left)
    right_result = _initialize(right)
    if (
        left_result["segment_index_snapshot_ref"]
        != right_result["segment_index_snapshot_ref"]
    ):
        raise AssertionError("segment index replay drifted")
    return left_result


def n04_pointer_initialization(root: Path) -> dict[str, Any]:
    result = _initialize(root)
    if state_counts(root / "state.json") != (3, 1, 1):
        raise AssertionError("atomic initialization did not publish 3+1+1")
    return result


def n05_operation_idempotent_replay(root: Path) -> dict[str, Any]:
    first = _initialize(root)
    before_hash = state_file_hash(root / "state.json")
    second = _initialize(root)
    if first != second or state_file_hash(root / "state.json") != before_hash:
        raise AssertionError("same operation replay was not idempotent")
    return second


def n06_lineage_locator_resolution(root: Path) -> dict[str, Any]:
    result = _initialize(root)
    candidate = _record_by_type(root, "M3_CANDIDATE_VERSION")
    lineage_id = candidate["payload"]["items"][0]["lineage_id"]
    locator = make_lineage_locator(candidate, lineage_id)
    validate_lineage_locator(locator)
    if locator["json_pointer"] != "/items/0":
        raise AssertionError("locator did not resolve to the first item")
    return {**result, "lineage_locator": locator}


def n07_parent_child_read_only_diff(root: Path) -> dict[str, Any]:
    result = _initialize(root)
    parent = _record_by_type(root, "M3_CANDIDATE_VERSION")
    child = make_read_only_child(parent, [{"text": "synthetic fact revised"}])
    before_hash = state_file_hash(root / "state.json")
    view = project_version_diff(parent, child)
    if view["changed_json_pointers"] != ["/items/0"]:
        raise AssertionError("read-only diff did not identify the changed item")
    if state_file_hash(root / "state.json") != before_hash:
        raise AssertionError("derived diff was persisted")
    return {**result, "version_diff": view, "version_diff_hash": sha256_value(view)}


def n08_restart_readback(root: Path) -> dict[str, Any]:
    request = base_request()
    request["crash_point"] = "after_commit_before_readback"
    try:
        B01Service(FixtureStore(root)).initialize_root_baseline(**request)
    except B01ContractError as error:
        if error.code != "B01_SIMULATED_CRASH_AFTER_COMMIT":
            raise
    else:
        raise AssertionError("restart fixture did not simulate a crash")
    reopened = FixtureStore(root).read()
    if len(reopened["records"]) != 3 or len(reopened["pointers"]) != 1:
        raise AssertionError("committed transaction was incomplete after restart")
    return deepcopy(reopened["operations"]["fixture-operation-001"]["result"])


NORMAL_SCENARIOS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "N01_NONEMPTY_BASELINE": n01_nonempty_baseline,
    "N02_EMPTY_BASELINE": n02_empty_baseline,
    "N03_SEGMENT_INDEX_REPLAY": n03_segment_index_replay,
    "N04_POINTER_INITIALIZATION": n04_pointer_initialization,
    "N05_OPERATION_IDEMPOTENT_REPLAY": n05_operation_idempotent_replay,
    "N06_LINEAGE_LOCATOR_RESOLUTION": n06_lineage_locator_resolution,
    "N07_PARENT_CHILD_READ_ONLY_DIFF": n07_parent_child_read_only_diff,
    "N08_RESTART_READBACK": n08_restart_readback,
}


def f01_admission_missing(root: Path) -> tuple[str, ...]:
    return (
        _capture_unchanged(
            root, "B01_A_ADMISSION_REQUIRED", lambda: _initialize(root, admission={})
        ),
    )


def f02_head_mismatch(root: Path) -> tuple[str, ...]:
    admission = valid_admission()
    admission["merge_time_head_sha"] = "0" * 40
    return (
        _capture_unchanged(
            root,
            "B01_A_ADMISSION_HEAD_MISMATCH",
            lambda: _initialize(root, admission=admission),
        ),
    )


def f03_main_readback_invalid(root: Path) -> tuple[str, ...]:
    admission = valid_admission()
    admission["readback_ok"] = False
    return (
        _capture_unchanged(
            root,
            "B01_A_ADMISSION_READBACK_INVALID",
            lambda: _initialize(root, admission=admission),
        ),
    )


def f04_manifest_drift(root: Path) -> tuple[str, ...]:
    admission = valid_admission()
    admission["interface_manifest_hash"] = "0" * 64
    return (
        _capture_unchanged(
            root,
            "B01_A_INTERFACE_DRIFT",
            lambda: _initialize(root, admission=admission),
        ),
    )


def f05_attempt_ref_invalid(root: Path) -> tuple[str, ...]:
    refs = attempt_refs()
    refs[0]["record_type"] = "NOT_AN_ATTEMPT"
    return (
        _capture_unchanged(
            root,
            "B01_ATTEMPT_REF_INVALID",
            lambda: _initialize(root, origin_attempt_refs=refs),
        ),
    )


def f06_segment_source_mismatch(root: Path) -> tuple[str, ...]:
    ref = chapter_revision_ref()
    ref["record_type"] = "OTHER_REVISION"
    return (
        _capture_unchanged(
            root,
            "B01_SEGMENT_SOURCE_MISMATCH",
            lambda: _initialize(root, chapter_revision_ref=ref),
        ),
    )


def f07_segment_number_invalid(root: Path) -> tuple[str, ...]:
    segments = segment_inputs()
    segments[0]["seg"] = 2
    return (
        _capture_unchanged(
            root,
            "B01_SEGMENT_INDEX_INVALID",
            lambda: _initialize(root, segment_inputs=segments),
        ),
    )


def f08_segment_range_invalid(root: Path) -> tuple[str, ...]:
    segments = segment_inputs()
    segments[1]["start_offset"] = 11
    return (
        _capture_unchanged(
            root,
            "B01_SEGMENT_INDEX_INVALID",
            lambda: _initialize(root, segment_inputs=segments),
        ),
    )


def f09_segment_text_hash_mismatch(root: Path) -> tuple[str, ...]:
    segments = segment_inputs()
    segments[0]["responsibility_text_sha256"] = "0" * 64
    return (
        _capture_unchanged(
            root,
            "B01_SEGMENT_TEXT_HASH_MISMATCH",
            lambda: _initialize(root, segment_inputs=segments),
        ),
    )


def f10_candidate_fields_invalid(root: Path) -> tuple[str, ...]:
    items = [{"text": "synthetic", "status": "forbidden"}]
    return (
        _capture_unchanged(
            root,
            "B01_CANDIDATE_VERSION_INVALID",
            lambda: _initialize(root, raw_items=items),
        ),
    )


def _valid_candidate() -> dict[str, Any]:
    return build_root_candidate_version(
        chapter_revision_ref=chapter_revision_ref(),
        seg=1,
        origin_attempt_refs=attempt_refs(),
        raw_items=[{"text": "a"}, {"text": "b"}],
        created_at=CREATED_AT,
    )


def f11_item_hash_mismatch(root: Path) -> tuple[str, ...]:
    candidate = _valid_candidate()
    candidate["payload"]["items"][0]["item_hash"] = "0" * 64
    _rehash_record(candidate)
    return (
        _capture_unchanged(
            root,
            "B01_ITEM_HASH_MISMATCH",
            lambda: validate_candidate_version(candidate),
        ),
    )


def f12_duplicate_lineage(root: Path) -> tuple[str, ...]:
    candidate = _valid_candidate()
    duplicate = candidate["payload"]["items"][0]["lineage_id"]
    candidate["payload"]["items"][1]["lineage_id"] = duplicate
    _rehash_record(candidate)
    return (
        _capture_unchanged(
            root,
            "B01_DUPLICATE_LINEAGE_ID",
            lambda: validate_candidate_version(candidate),
        ),
    )


def f13_lineage_index_invalid(root: Path) -> tuple[str, ...]:
    candidate = _valid_candidate()
    candidate["payload"]["lineage_index"][0]["json_pointer"] = "/items/99"
    _rehash_record(candidate)
    return (
        _capture_unchanged(
            root,
            "B01_LINEAGE_INDEX_INVALID",
            lambda: validate_candidate_version(candidate),
        ),
    )


def f14_empty_baseline_inconsistent(root: Path) -> tuple[str, ...]:
    candidate = build_root_candidate_version(
        chapter_revision_ref=chapter_revision_ref(),
        seg=1,
        origin_attempt_refs=attempt_refs(),
        raw_items=[],
        created_at=CREATED_AT,
    )
    candidate["payload"]["lineage_index"] = [
        {"lineage_id": "lin_invalid", "json_pointer": "/items/0", "item_hash": "0" * 64}
    ]
    _rehash_record(candidate)
    return (
        _capture_unchanged(
            root,
            "B01_EMPTY_BASELINE_INVALID",
            lambda: validate_candidate_version(candidate),
        ),
    )


def f15_child_creation_out_of_scope(root: Path) -> tuple[str, ...]:
    candidate = _valid_candidate()
    child = make_read_only_child(candidate, [{"text": "child"}])
    return (
        _capture_unchanged(
            root,
            "B01_CHILD_CREATION_OUT_OF_SCOPE",
            lambda: validate_candidate_version(child),
        ),
    )


def f16_pointer_scope_mismatch(root: Path) -> tuple[str, ...]:
    return (
        _capture_unchanged(
            root,
            "B01_POINTER_SCOPE_MISMATCH",
            lambda: _initialize(root, pointer_namespace="PRODUCT"),
        ),
    )


def f17_pointer_already_initialized(root: Path) -> tuple[str, ...]:
    _initialize(root)
    return (
        _capture_unchanged(
            root,
            "B01_POINTER_ALREADY_INITIALIZED",
            lambda: _initialize(root, operation_id="fixture-operation-002"),
        ),
    )


def f18_operation_conflict(root: Path) -> tuple[str, ...]:
    _initialize(root)
    return (
        _capture_unchanged(
            root,
            "B01_OPERATION_CONFLICT",
            lambda: _initialize(root, raw_items=[{"text": "changed"}]),
        ),
    )


def f19_diff_invalid_or_persisted(root: Path) -> tuple[str, ...]:
    parent = _valid_candidate()
    child = make_read_only_child(parent, [{"text": "changed"}])
    bad_child = deepcopy(child)
    bad_child["payload"]["parent_candidate_version_ref"] = None
    bad_child["payload"]["version_payload_hash"] = sha256_value(
        {
            key: value
            for key, value in bad_child["payload"].items()
            if key != "version_payload_hash"
        }
    )
    _rehash_record(bad_child)
    invalid = _capture_unchanged(
        root,
        "B01_VERSION_DIFF_INVALID",
        lambda: project_version_diff(parent, bad_child),
    )
    persisted = _capture_unchanged(
        root,
        "B01_DERIVED_VIEW_PERSIST_FORBIDDEN",
        lambda: project_version_diff(parent, child, persist=True),
    )
    return (invalid, persisted)


def f20_boundary_or_runtime_event(root: Path) -> tuple[str, ...]:
    escaped = _capture_unchanged(
        root,
        "B01_WRITE_SET_ESCAPE",
        lambda: guard_write_path("work/another_ticket/file.json"),
    )
    event = _capture_unchanged(
        root, "B01_NETWORK_OR_PROCESS_EVENT", lambda: guard_runtime_event("network")
    )
    return (escaped, event)


FAILURE_SCENARIOS: dict[str, Callable[[Path], tuple[str, ...]]] = {
    "F01_A_ADMISSION_MISSING": f01_admission_missing,
    "F02_A_HEAD_MISMATCH": f02_head_mismatch,
    "F03_A_MAIN_READBACK_INVALID": f03_main_readback_invalid,
    "F04_A_INTERFACE_MANIFEST_DRIFT": f04_manifest_drift,
    "F05_ATTEMPT_REF_INVALID": f05_attempt_ref_invalid,
    "F06_SEGMENT_SOURCE_MISMATCH": f06_segment_source_mismatch,
    "F07_SEGMENT_NUMBER_INVALID": f07_segment_number_invalid,
    "F08_SEGMENT_RANGE_INVALID": f08_segment_range_invalid,
    "F09_SEGMENT_TEXT_HASH_MISMATCH": f09_segment_text_hash_mismatch,
    "F10_CANDIDATE_FIELDS_INVALID": f10_candidate_fields_invalid,
    "F11_ITEM_HASH_MISMATCH": f11_item_hash_mismatch,
    "F12_DUPLICATE_LINEAGE_ID": f12_duplicate_lineage,
    "F13_LINEAGE_INDEX_INVALID": f13_lineage_index_invalid,
    "F14_EMPTY_BASELINE_INCONSISTENT": f14_empty_baseline_inconsistent,
    "F15_CHILD_CREATION_OUT_OF_SCOPE": f15_child_creation_out_of_scope,
    "F16_POINTER_SCOPE_MISMATCH": f16_pointer_scope_mismatch,
    "F17_POINTER_ALREADY_INITIALIZED": f17_pointer_already_initialized,
    "F18_OPERATION_CONFLICT": f18_operation_conflict,
    "F19_VERSION_DIFF_INVALID_OR_PERSISTED": f19_diff_invalid_or_persisted,
    "F20_WRITE_SET_OR_RUNTIME_BOUNDARY": f20_boundary_or_runtime_event,
}


def run_normal_scenario(name: str, root: Path) -> dict[str, Any]:
    return NORMAL_SCENARIOS[name](root)


def run_failure_scenario(name: str, root: Path) -> tuple[str, ...]:
    return FAILURE_SCENARIOS[name](root)


def scenario_record_refs(
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    for state_path in sorted(root.rglob("state.json")):
        state = json.loads(state_path.read_text(encoding="utf-8"))
        records.extend(state["records"].values())
        refs.extend(state["pointers"].values())
        for operation in state["operations"].values():
            refs.extend(
                value
                for key, value in operation["result"].items()
                if key.endswith("_ref")
            )
    return records, refs


def canonical_fixture_vector() -> dict[str, str]:
    value = {"z": "e\u0301", "a": [3, True, None, "synthetic"]}
    return {
        "canonical_utf8_hex": canonical_bytes(value).hex(),
        "sha256": sha256_value(value),
    }

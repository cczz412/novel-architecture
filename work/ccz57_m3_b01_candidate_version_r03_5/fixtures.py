"""Synthetic normal and failure fixtures for the B-01 offline contract."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from b01_contract import (
    B01ContractError,
    B01Service,
    CANDIDATE_SCHEMA_ID,
    CandidateVersionStore,
    FixtureStore,
    LEGACY_CONTRACT_VERSION,
    SegmentIndexSnapshotWriter,
    VersionDiffProjector,
    build_extraction_input_binding,
    canonical_bytes,
    guard_runtime_event,
    guard_write_path,
    make_fixture_input_record,
    make_legacy_read_only_candidate_fixture,
    make_read_only_child_fixture,
    read_legacy_candidate_version,
    record_ref,
    sha256_value,
    state_counts,
    state_file_hash,
    validate_candidate_version,
    validate_evidence_locator,
    validate_lineage_locator,
    verify_state,
)

CREATED_AT = "2026-08-28T12:00:00Z"
REPLAY_CREATED_AT = "2026-08-28T12:01:00Z"
ADMISSION_CREATED_AT = "2026-08-28T03:26:14Z"
REVIEWED_HEAD_SHA = "9eafdac71f412be3f7b8ad5fd81ffc84c3de3a26"
MERGE_COMMIT_SHA = "019df751641533c7de4d56aa38f50747fb564036"
INTERFACE_MANIFEST_PAYLOAD_HASH = (
    "50c5c74c67678565693dd86c27dab20319a0d107bb9d196b21d23643843ca860"
)

RESPONSIBILITY_TEXT_1 = "甲走进北塔。甲拿起铜钥匙。甲走进北塔。"
RESPONSIBILITY_TEXT_2 = "乙停在门外。"
REVISION_TEXT = RESPONSIBILITY_TEXT_1 + RESPONSIBILITY_TEXT_2
REVISION_TEXT_SHA256 = hashlib.sha256(REVISION_TEXT.encode("utf-8")).hexdigest()


def review_receipt_record() -> dict[str, Any]:
    return make_fixture_input_record(
        record_type="A_EXACT_HEAD_REVIEW_RECEIPT",
        record_id="a_exact_review_9eafdac_20260828",
        record_version=1,
        source_module="A_REVIEW_IMPORT",
        access="RUN_INTERNAL_READ_ONLY",
        retention_class="CORE_IMMUTABLE_AUDIT",
        created_at=ADMISSION_CREATED_AT,
        payload={
            "repository": "cczz412/novel-architecture",
            "pr_number": 186,
            "base_sha": "d4f0398cf9c7a0a1cb7c281adafdb91a40ff2000",
            "head_sha": REVIEWED_HEAD_SHA,
            "review_result": "PASS",
            "source_file_sha256": "267ce10e7612dc32df8d64b7a23cee3f30223195d01e1ec9f5ae32a72c21aa3f",
            "scope": "A_STAGE_EXACT_HEAD_MECHANICAL_REVIEW_ONLY",
        },
        contract_version=LEGACY_CONTRACT_VERSION,
    )


def interface_manifest_record() -> dict[str, Any]:
    return make_fixture_input_record(
        record_type="A_INTERFACE_MANIFEST",
        record_id="a_interface_manifest_main_019df751_20260828",
        record_version=1,
        source_module="A_INTERFACE_MANIFEST_READER",
        access="RUN_INTERNAL_READ_ONLY",
        retention_class="CORE_IMMUTABLE_AUDIT",
        created_at=ADMISSION_CREATED_AT,
        payload={
            "repository": "cczz412/novel-architecture",
            "issue_number": 176,
            "interface_names": [
                "RawAttempt",
                "ProviderTurn",
                "MechanicalGate",
                "C3Preview",
            ],
            "manifest_mode": "MERGED_CURRENT_MAIN_READBACK",
        },
        contract_version=LEGACY_CONTRACT_VERSION,
    )


def attempt_record(record_id: str = "attempt_fixture_001") -> dict[str, Any]:
    return make_fixture_input_record(
        record_type="A_RAW_ATTEMPT_RECEIPT",
        record_id=record_id,
        record_version=1,
        source_module="A_STAGE_FIXTURE",
        access="POLICY_FIXTURE_READ_ONLY",
        retention_class="CORE_IMMUTABLE_AUDIT",
        created_at=CREATED_AT,
        payload={
            "run_id": "synthetic-run-001",
            "attempt_no": 1,
            "mechanical_gate": "PASS",
            "request_sha256": "1" * 64,
            "response_sha256": "2" * 64,
        },
        contract_version=LEGACY_CONTRACT_VERSION,
    )


def source_generation_record(
    *, generation_hex: str = "a", revision_ref: dict[str, Any] | None = None
) -> dict[str, Any]:
    revision = chapter_revision_ref() if revision_ref is None else revision_ref
    return make_fixture_input_record(
        record_type="M1_ACCEPTED_SOURCE_GENERATION",
        record_id=f"m1-generation-{generation_hex}",
        record_version=1,
        source_module="M1_READ_ONLY_ADAPTER",
        access="POLICY_FIXTURE_READ_ONLY",
        retention_class="CORE_IMMUTABLE_AUDIT",
        created_at=CREATED_AT,
        payload={
            "workspace_generation_schema": "author-workspace-generation-v1",
            "chapter_admission_identity": "AUTHOR_WORKSPACE_INITIAL_CHAPTER_ADMISSION_R01",
            "workspace_generation_id": f"g_{generation_hex * 64}",
            "manifest_sha256": generation_hex * 64,
            "chapter_revision_ref": revision,
        },
    )


def material_record(
    material_kind: str,
    *,
    source_generation: dict[str, Any] | None = None,
    digest_char: str = "b",
) -> dict[str, Any]:
    generation = (
        source_generation_record() if source_generation is None else source_generation
    )
    return make_fixture_input_record(
        record_type="M1_WRITING_MATERIAL",
        record_id=f"m1-material-{material_kind.lower()}",
        record_version=1,
        source_module="M1_READ_ONLY_ADAPTER",
        access="POLICY_FIXTURE_READ_ONLY",
        retention_class="CORE_IMMUTABLE_AUDIT",
        created_at=CREATED_AT,
        payload={
            "material_kind": material_kind,
            "accepted_source_generation_ref": record_ref(generation),
            "material_contract": "novel-fact-p3-context-card-v1",
            "material_version": "v1",
            "material_sha256": digest_char * 64,
        },
    )


def writing_material_bindings(
    *, source_generation: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    generation = (
        source_generation_record() if source_generation is None else source_generation
    )
    core = material_record(
        "CORE_CHARACTER", source_generation=generation, digest_char="b"
    )
    genre = material_record("GENRE", source_generation=generation, digest_char="c")
    return [
        {"material_kind": "CORE_CHARACTER", "material_ref": record_ref(core)},
        {"material_kind": "GENRE", "material_ref": record_ref(genre)},
    ]


def reference_records(
    *, source_generation: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    generation = (
        source_generation_record() if source_generation is None else source_generation
    )
    return [
        review_receipt_record(),
        interface_manifest_record(),
        attempt_record(),
        generation,
        material_record(
            "CORE_CHARACTER", source_generation=generation, digest_char="b"
        ),
        material_record("GENRE", source_generation=generation, digest_char="c"),
    ]


def valid_admission() -> dict[str, Any]:
    review = review_receipt_record()
    manifest = interface_manifest_record()
    return make_fixture_input_record(
        record_type="M3_A_INTERFACE_ADMISSION_RECEIPT",
        record_id="a_admission_pr186_019df751_20260828",
        record_version=1,
        source_module="M3_B_ADMISSION",
        access="RUN_INTERNAL_READ_ONLY",
        retention_class="CORE_IMMUTABLE_AUDIT",
        created_at=ADMISSION_CREATED_AT,
        payload={
            "repository": "cczz412/novel-architecture",
            "issue_number": 176,
            "pr_number": 186,
            "review_receipt_ref": record_ref(review),
            "reviewed_pr_head_sha": REVIEWED_HEAD_SHA,
            "pr_head_sha_at_merge": REVIEWED_HEAD_SHA,
            "reviewed_head_equals_merge_head": True,
            "merge_commit_sha": MERGE_COMMIT_SHA,
            "current_main_sha": MERGE_COMMIT_SHA,
            "merge_commit_reachable_from_current_main": True,
            "a_interface_manifest_ref": record_ref(manifest),
            "a_interface_manifest_sha256": INTERFACE_MANIFEST_PAYLOAD_HASH,
            "current_main_readback_passed": True,
            "pr_gate_observation": "SUCCESS_RUN_33137839343_JOB_98741762882",
            "admission_mode": "MERGED_CURRENT_MAIN_EXACT_HEAD",
            "admission_result": "PASS",
            "b_code_start_authorized": True,
        },
        contract_version=LEGACY_CONTRACT_VERSION,
    )


def chapter_revision_ref() -> dict[str, Any]:
    return {
        "chapter_id": "synthetic-chapter-001",
        "revision_no": 7,
        "revision_text_sha256": REVISION_TEXT_SHA256,
    }


def attempt_refs() -> list[dict[str, Any]]:
    return [record_ref(attempt_record())]


def segment_inputs() -> list[dict[str, Any]]:
    first_end = len(RESPONSIBILITY_TEXT_1.encode("utf-8"))
    second_end = first_end + len(RESPONSIBILITY_TEXT_2.encode("utf-8"))
    return [
        {
            "seg": 1,
            "start_byte": 0,
            "end_byte": first_end,
            "responsibility_text": RESPONSIBILITY_TEXT_1,
        },
        {
            "seg": 2,
            "start_byte": first_end,
            "end_byte": second_end,
            "responsibility_text": RESPONSIBILITY_TEXT_2,
        },
    ]


def base_request(*, raw_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    generation = source_generation_record()
    return {
        "admission": valid_admission(),
        "reference_records": reference_records(source_generation=generation),
        "project_scope_id": "fixture-project-001",
        "author_workspace_logical_key": "fixture-workspace-001",
        "chapter_revision_ref": chapter_revision_ref(),
        "accepted_source_generation_ref": record_ref(generation),
        "writing_material_refs": writing_material_bindings(
            source_generation=generation
        ),
        "source_module_identity": "B01_SYNTHETIC_FIXTURE",
        "segment_inputs": segment_inputs(),
        "seg": 1,
        "origin_attempt_refs": attempt_refs(),
        "raw_items": (
            [
                {
                    "fact": "甲进入北塔。",
                    "status": "已发生",
                    "evidence": "甲走进北塔。",
                },
                {
                    "fact": "甲拿起铜钥匙。",
                    "status": "已发生",
                    "evidence": "甲拿起铜钥匙。",
                    "speaker": "旁白",
                },
            ]
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


def _all_candidate_refs(root: Path) -> list[dict[str, Any]]:
    return [
        *reference_records(),
        _record_by_type(root, "M3_SEGMENT_INDEX_SNAPSHOT"),
    ]


def _initialize(root: Path, **overrides: Any) -> dict[str, Any]:
    request = base_request()
    request.update(overrides)
    return B01Service(FixtureStore(root)).initialize_root_baseline(**request)


def _rehash_record(record: dict[str, Any]) -> None:
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )


def directory_snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _capture_unchanged(
    root: Path, expected_code: str, action: Callable[[], Any]
) -> str:
    before_counts = state_counts(root / "state.json")
    before_hash = state_file_hash(root / "state.json")
    before_directory = directory_snapshot(root)
    try:
        action()
    except B01ContractError as error:
        if error.code != expected_code:
            raise AssertionError(
                f"expected {expected_code}, got {error.code}"
            ) from error
    else:
        raise AssertionError(f"expected {expected_code}")
    if (
        state_counts(root / "state.json") != before_counts
        or state_file_hash(root / "state.json") != before_hash
        or directory_snapshot(root) != before_directory
    ):
        raise AssertionError(f"failure {expected_code} changed fixture state")
    return expected_code


def n01_nonempty_baseline(root: Path) -> dict[str, Any]:
    result = _initialize(root)
    candidate = _record_by_type(root, "M3_CANDIDATE_VERSION")
    if len(candidate["payload"]["items"]) != 2:
        raise AssertionError("nonempty baseline must contain two items")
    validate_candidate_version(candidate, reference_records=_all_candidate_refs(root))
    if candidate["payload"]["candidate_schema_id"] != CANDIDATE_SCHEMA_ID:
        raise AssertionError("candidate schema drift")
    if (
        len(candidate["payload"]["items"][0]["evidence_binding"]["match_locations"])
        != 2
    ):
        raise AssertionError("repeated evidence locations were not retained")
    return result


def n02_empty_baseline(root: Path) -> dict[str, Any]:
    result = _initialize(
        root, raw_items=[], seg=2, operation_id="fixture-operation-empty"
    )
    candidate = _record_by_type(root, "M3_CANDIDATE_VERSION")
    if candidate["payload"]["items"] or candidate["payload"]["lineage_index"]:
        raise AssertionError("empty baseline is inconsistent")
    return result


def n03_segment_index_replay(root: Path) -> dict[str, Any]:
    first = _initialize(root)
    before = directory_snapshot(root)
    second = _initialize(root, created_at=REPLAY_CREATED_AT)
    if first["segment_index_snapshot_ref"] != second["segment_index_snapshot_ref"]:
        raise AssertionError("segment index ref drifted")
    if directory_snapshot(root) != before or state_counts(root / "state.json") != (
        3,
        1,
        1,
    ):
        raise AssertionError("segment index replay changed state")
    return second


def n04_pointer_initialization(root: Path) -> dict[str, Any]:
    result = _initialize(root)
    state = _load_state(root)
    if state_counts(root / "state.json") != (3, 1, 1):
        raise AssertionError("atomic initialization did not publish 3+1+1")
    pointer = next(iter(state["pointers"].values()))
    if pointer["generation"] != 1 or pointer["pointer_namespace"] != "FIXTURE_ONLY":
        raise AssertionError("live pointer state is incomplete")
    return result


def n05_operation_idempotent_replay(root: Path) -> dict[str, Any]:
    first = _initialize(root)
    before = directory_snapshot(root)
    second = _initialize(root, created_at=REPLAY_CREATED_AT)
    if first != second or directory_snapshot(root) != before:
        raise AssertionError("same operation replay was not idempotent")
    if next(iter(_load_state(root)["pointers"].values()))["generation"] != 1:
        raise AssertionError("replay increased generation")
    return second


def n06_lineage_locator_resolution(root: Path) -> dict[str, Any]:
    result = _initialize(root)
    candidate = _record_by_type(root, "M3_CANDIDATE_VERSION")
    locators = []
    evidence_locators = []
    all_refs = _all_candidate_refs(root)
    for index, item in enumerate(candidate["payload"]["items"]):
        locator = CandidateVersionStore.lineage_locator(
            candidate, item["lineage_id"], reference_records=all_refs
        )
        validate_lineage_locator(
            locator,
            candidate_version=candidate,
            reference_records=all_refs,
        )
        if locator["json_pointer"] != f"/items/{index}":
            raise AssertionError("locator pointer mismatch")
        locators.append(locator)
        evidence_locator = CandidateVersionStore.evidence_locator(
            candidate,
            item["lineage_id"],
            reference_records=all_refs,
        )
        validate_evidence_locator(
            evidence_locator,
            candidate_version=candidate,
            reference_records=all_refs,
        )
        evidence_locators.append(evidence_locator)
    return {
        **result,
        "lineage_locators": locators,
        "evidence_locators": evidence_locators,
    }


def n07_parent_child_read_only_diff(root: Path) -> dict[str, Any]:
    result = _initialize(root)
    parent = _record_by_type(root, "M3_CANDIDATE_VERSION")
    all_refs = _all_candidate_refs(root)
    child = make_read_only_child_fixture(
        parent,
        [
            {
                "fact": "甲已经进入北塔。",
                "status": "已发生",
                "evidence": "甲走进北塔。",
            },
            {
                "fact": "甲拿起铜钥匙。",
                "status": "已发生",
                "evidence": "甲拿起铜钥匙。",
                "speaker": "旁白",
            },
        ],
        reference_records=all_refs,
    )
    if (
        child["payload"]["items"][0]["lineage_id"]
        != parent["payload"]["items"][0]["lineage_id"]
    ):
        raise AssertionError("child fixture did not preserve lineage")
    before = directory_snapshot(root)
    view = VersionDiffProjector.project(parent, child, reference_records=all_refs)
    if view["changed_json_pointers"] != ["/items/0/fact"]:
        raise AssertionError("read-only diff did not identify the exact changed field")
    if directory_snapshot(root) != before:
        raise AssertionError("derived diff was persisted")
    return {**result, "version_diff": view, "version_diff_hash": sha256_value(view)}


def n09_legacy_read_only(root: Path) -> dict[str, Any]:
    legacy = make_legacy_read_only_candidate_fixture(
        chapter_revision_ref=chapter_revision_ref(),
        seg=1,
        origin_attempt_refs=attempt_refs(),
        raw_items=[{"text": "历史候选", "quote": "甲走进北塔。"}],
        created_at=CREATED_AT,
    )
    summary = read_legacy_candidate_version(legacy)
    if summary["mode"] != "LEGACY_READ_ONLY" or summary["evidence_locator_available"]:
        raise AssertionError("legacy object was upgraded")
    return {"legacy_record_hash": legacy["record_hash"], "summary": summary}


def n10_material_generation_changes_identity(root: Path) -> dict[str, Any]:
    first_root = root / "generation-a"
    second_root = root / "generation-d"
    first = _initialize(first_root)
    generation = source_generation_record(generation_hex="d")
    second_refs = reference_records(source_generation=generation)
    second = _initialize(
        second_root,
        reference_records=second_refs,
        accepted_source_generation_ref=record_ref(generation),
        writing_material_refs=writing_material_bindings(source_generation=generation),
    )
    first_candidate = _record_by_type(first_root, "M3_CANDIDATE_VERSION")
    second_candidate = _record_by_type(second_root, "M3_CANDIDATE_VERSION")
    if (
        first_candidate["payload"]["extraction_input_binding"]["input_binding_hash"]
        == second_candidate["payload"]["extraction_input_binding"]["input_binding_hash"]
        or first["candidate_version_ref"] == second["candidate_version_ref"]
    ):
        raise AssertionError("source generation did not change candidate identity")
    return {
        "first_candidate_ref": first["candidate_version_ref"],
        "second_candidate_ref": second["candidate_version_ref"],
    }


def n08_prepare_committed_crash(root: Path) -> dict[str, Any]:
    """Commit the transaction and stop before readback in process phase one."""
    request = base_request()
    request["crash_point"] = "after_commit_before_readback"
    try:
        B01Service(FixtureStore(root)).initialize_root_baseline(**request)
    except B01ContractError as error:
        if error.code != "B01_SIMULATED_CRASH_AFTER_COMMIT":
            raise
    else:
        raise AssertionError("restart fixture did not simulate a crash")
    committed = FixtureStore(root).read()
    verify_state(committed, reference_records=reference_records())
    if state_counts(root / "state.json") != (3, 1, 1):
        raise AssertionError("committed transaction was incomplete before restart")
    return {
        "result": deepcopy(committed["operations"]["fixture-operation-001"]["result"]),
        "state_file_hash": state_file_hash(root / "state.json"),
    }


def n08_restart_readback(root: Path) -> dict[str, Any]:
    """Reopen and replay phase-one state in a separately launched process."""
    before_hash = state_file_hash(root / "state.json")
    if before_hash is None:
        raise AssertionError("N08 requires committed state from a prior process")
    reopened = FixtureStore(root).read()
    verify_state(reopened, reference_records=reference_records())
    if state_counts(root / "state.json") != (3, 1, 1):
        raise AssertionError("committed transaction was incomplete after restart")
    original_result = deepcopy(
        reopened["operations"]["fixture-operation-001"]["result"]
    )
    replay_result = B01Service(FixtureStore(root)).initialize_root_baseline(
        **base_request()
    )
    if replay_result != original_result:
        raise AssertionError("restart replay did not return the original result")
    if state_counts(root / "state.json") != (3, 1, 1):
        raise AssertionError("restart replay repeated initialization")
    after_hash = state_file_hash(root / "state.json")
    if after_hash != before_hash:
        raise AssertionError("restart replay changed committed state bytes")
    replayed = FixtureStore(root).read()
    verify_state(replayed, reference_records=reference_records())
    live_pointer = next(iter(replayed["pointers"].values()))
    if live_pointer["generation"] != 1:
        raise AssertionError("restart replay advanced pointer generation")
    return {
        "result": replay_result,
        "state_file_hash": after_hash,
        "generation": live_pointer["generation"],
    }


NORMAL_SCENARIOS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "N01_NONEMPTY_BASELINE": n01_nonempty_baseline,
    "N02_EMPTY_BASELINE": n02_empty_baseline,
    "N03_SEGMENT_INDEX_REPLAY": n03_segment_index_replay,
    "N04_POINTER_INITIALIZATION": n04_pointer_initialization,
    "N05_OPERATION_IDEMPOTENT_REPLAY": n05_operation_idempotent_replay,
    "N06_LINEAGE_LOCATOR_RESOLUTION": n06_lineage_locator_resolution,
    "N07_PARENT_CHILD_READ_ONLY_DIFF": n07_parent_child_read_only_diff,
    "N08_RESTART_READBACK": n08_restart_readback,
    "N09_LEGACY_READ_ONLY": n09_legacy_read_only,
    "N10_MATERIAL_GENERATION_CHANGES_IDENTITY": n10_material_generation_changes_identity,
}


def f01_admission_missing(root: Path) -> tuple[str, ...]:
    return (
        _capture_unchanged(
            root, "B01_A_ADMISSION_REQUIRED", lambda: _initialize(root, admission={})
        ),
    )


def f02_head_mismatch(root: Path) -> tuple[str, ...]:
    admission = valid_admission()
    admission["payload"]["pr_head_sha_at_merge"] = "0" * 40
    _rehash_record(admission)
    return (
        _capture_unchanged(
            root,
            "B01_A_ADMISSION_HEAD_MISMATCH",
            lambda: _initialize(root, admission=admission),
        ),
    )


def f03_main_readback_invalid(root: Path) -> tuple[str, ...]:
    admission = valid_admission()
    admission["payload"]["current_main_readback_passed"] = False
    _rehash_record(admission)
    return (
        _capture_unchanged(
            root,
            "B01_A_ADMISSION_READBACK_INVALID",
            lambda: _initialize(root, admission=admission),
        ),
    )


def f04_manifest_drift(root: Path) -> tuple[str, ...]:
    references = reference_records()
    manifest = next(
        record
        for record in references
        if record["record_type"] == "A_INTERFACE_MANIFEST"
    )
    manifest["payload"]["interface_names"].append("DRIFT")
    _rehash_record(manifest)
    return (
        _capture_unchanged(
            root,
            "B01_A_INTERFACE_DRIFT",
            lambda: _initialize(root, reference_records=references),
        ),
    )


def f05_attempt_ref_invalid(root: Path) -> tuple[str, ...]:
    refs = attempt_refs()
    refs[0]["record_hash"] = "0" * 64
    return (
        _capture_unchanged(
            root,
            "B01_ATTEMPT_REF_INVALID",
            lambda: _initialize(root, origin_attempt_refs=refs),
        ),
    )


def f06_segment_source_mismatch(root: Path) -> tuple[str, ...]:
    return (
        _capture_unchanged(
            root,
            "B01_SEGMENT_SOURCE_MISMATCH",
            lambda: _initialize(root, source_module_identity="UNKNOWN"),
        ),
    )


def f07_segment_number_invalid(root: Path) -> tuple[str, ...]:
    segments = segment_inputs()
    segments[0]["seg"] = 0
    return (
        _capture_unchanged(
            root,
            "B01_SEGMENT_INDEX_INVALID",
            lambda: _initialize(root, segment_inputs=segments),
        ),
    )


def f08_segment_range_invalid(root: Path) -> tuple[str, ...]:
    segments = segment_inputs()
    segments[1]["start_byte"] -= 1
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
    return (
        _capture_unchanged(
            root,
            "B01_CANDIDATE_VERSION_INVALID",
            lambda: _initialize(
                root,
                raw_items=[
                    {
                        "fact": "synthetic",
                        "status": "forbidden",
                        "evidence": "甲走进北塔。",
                    }
                ],
            ),
        ),
    )


def _valid_candidate_parts(
    *, raw_items: list[dict[str, Any]] | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    generation = source_generation_record()
    references = reference_records(source_generation=generation)
    materials = writing_material_bindings(source_generation=generation)
    binding = build_extraction_input_binding(
        accepted_source_generation_ref=record_ref(generation),
        chapter_revision_ref=chapter_revision_ref(),
        writing_material_refs=materials,
        reference_records=references,
    )
    segment_record = SegmentIndexSnapshotWriter.build(
        project_scope_id="fixture-project-001",
        author_workspace_logical_key="fixture-workspace-001",
        chapter_revision_ref=chapter_revision_ref(),
        accepted_source_generation_ref=record_ref(generation),
        reference_records=references,
        source_module_identity="B01_SYNTHETIC_FIXTURE",
        segment_inputs=segment_inputs(),
        created_at=CREATED_AT,
    )
    candidate = CandidateVersionStore.build_root(
        chapter_revision_ref=chapter_revision_ref(),
        seg=1,
        author_workspace_logical_key="fixture-workspace-001",
        extraction_input_binding=binding,
        segment_index_record=segment_record,
        origin_attempt_refs=attempt_refs(),
        reference_records=references,
        segment_inputs=segment_inputs(),
        raw_items=(base_request()["raw_items"] if raw_items is None else raw_items),
        created_at=CREATED_AT,
    )
    return candidate, [segment_record, *references]


def _valid_candidate() -> dict[str, Any]:
    return _valid_candidate_parts()[0]


def _valid_candidate_refs() -> list[dict[str, Any]]:
    return _valid_candidate_parts()[1]


def f11_item_hash_mismatch(root: Path) -> tuple[str, ...]:
    candidate = _valid_candidate()
    candidate["payload"]["items"][0]["item_hash"] = "0" * 64
    _rehash_record(candidate)
    return (
        _capture_unchanged(
            root,
            "B01_ITEM_HASH_MISMATCH",
            lambda: validate_candidate_version(
                candidate, reference_records=_valid_candidate_refs()
            ),
        ),
    )


def f12_duplicate_lineage(root: Path) -> tuple[str, ...]:
    candidate = _valid_candidate()
    candidate["payload"]["items"][1]["lineage_id"] = candidate["payload"]["items"][0][
        "lineage_id"
    ]
    _rehash_record(candidate)
    return (
        _capture_unchanged(
            root,
            "B01_DUPLICATE_LINEAGE_ID",
            lambda: validate_candidate_version(
                candidate, reference_records=_valid_candidate_refs()
            ),
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
            lambda: validate_candidate_version(
                candidate, reference_records=_valid_candidate_refs()
            ),
        ),
    )


def f14_empty_baseline_inconsistent(root: Path) -> tuple[str, ...]:
    candidate, candidate_refs = _valid_candidate_parts(raw_items=[])
    candidate["payload"]["lineage_index"] = [
        {"lineage_id": "lin_invalid", "json_pointer": "/items/0", "item_hash": "0" * 64}
    ]
    _rehash_record(candidate)
    return (
        _capture_unchanged(
            root,
            "B01_EMPTY_BASELINE_INVALID",
            lambda: validate_candidate_version(
                candidate, reference_records=candidate_refs
            ),
        ),
    )


def f15_child_creation_out_of_scope(root: Path) -> tuple[str, ...]:
    parent, candidate_refs = _valid_candidate_parts()
    child = make_read_only_child_fixture(
        parent,
        [
            {
                "fact": "子版本改写了事实。",
                "status": "已发生",
                "evidence": "甲走进北塔。",
            },
            {
                "fact": "甲拿起铜钥匙。",
                "status": "已发生",
                "evidence": "甲拿起铜钥匙。",
                "speaker": "旁白",
            },
        ],
        reference_records=candidate_refs,
    )
    return (
        _capture_unchanged(
            root,
            "B01_CHILD_CREATION_OUT_OF_SCOPE",
            lambda: CandidateVersionStore.stage_root(
                FixtureStore.empty_state(),
                child,
                author_workspace_logical_key="fixture-author-workspace",
                reference_records=candidate_refs,
            ),
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
    changed = [
        {
            "fact": "甲进入另一座塔。",
            "status": "已发生",
            "evidence": "甲走进北塔。",
        },
        {
            "fact": "甲拿起铜钥匙。",
            "status": "已发生",
            "evidence": "甲拿起铜钥匙。",
            "speaker": "旁白",
        },
    ]
    return (
        _capture_unchanged(
            root, "B01_OPERATION_CONFLICT", lambda: _initialize(root, raw_items=changed)
        ),
    )


def f19_diff_invalid_or_persisted(root: Path) -> tuple[str, ...]:
    parent, candidate_refs = _valid_candidate_parts()
    child = make_read_only_child_fixture(
        parent,
        [
            {
                "fact": "甲已经进入北塔。",
                "status": "已发生",
                "evidence": "甲走进北塔。",
            },
            {
                "fact": "甲拿起铜钥匙。",
                "status": "已发生",
                "evidence": "甲拿起铜钥匙。",
                "speaker": "旁白",
            },
        ],
        reference_records=candidate_refs,
    )
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
        lambda: VersionDiffProjector.project(
            parent, bad_child, reference_records=candidate_refs
        ),
    )
    persisted = _capture_unchanged(
        root,
        "B01_DERIVED_VIEW_PERSIST_FORBIDDEN",
        lambda: VersionDiffProjector.project(
            parent, child, persist=True, reference_records=candidate_refs
        ),
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


def f21_source_generation_mismatch(root: Path) -> tuple[str, ...]:
    generation_a = source_generation_record()
    generation_d = source_generation_record(generation_hex="d")
    references = [
        *reference_records(source_generation=generation_a),
        generation_d,
    ]
    return (
        _capture_unchanged(
            root,
            "B01_SOURCE_GENERATION_MISMATCH",
            lambda: _initialize(
                root,
                reference_records=references,
                accepted_source_generation_ref=record_ref(generation_d),
                writing_material_refs=writing_material_bindings(
                    source_generation=generation_a
                ),
            ),
        ),
    )


def f22_required_material_missing(root: Path) -> tuple[str, ...]:
    generation = source_generation_record()
    core = material_record("CORE_CHARACTER", source_generation=generation)
    return (
        _capture_unchanged(
            root,
            "B01_WRITING_MATERIAL_INVALID",
            lambda: _initialize(
                root,
                reference_records=[
                    review_receipt_record(),
                    interface_manifest_record(),
                    attempt_record(),
                    generation,
                    core,
                ],
                accepted_source_generation_ref=record_ref(generation),
                writing_material_refs=[
                    {
                        "material_kind": "CORE_CHARACTER",
                        "material_ref": record_ref(core),
                    }
                ],
            ),
        ),
    )


def f23_evidence_not_in_chapter(root: Path) -> tuple[str, ...]:
    return (
        _capture_unchanged(
            root,
            "B01_EVIDENCE_NOT_IN_EXACT_CHAPTER",
            lambda: _initialize(
                root,
                raw_items=[
                    {
                        "fact": "不存在的事实。",
                        "status": "已发生",
                        "evidence": "这一句不在章节里。",
                    }
                ],
            ),
        ),
    )


def f24_evidence_sentence_limit(root: Path) -> tuple[str, ...]:
    return (
        _capture_unchanged(
            root,
            "B01_EVIDENCE_SENTENCE_LIMIT",
            lambda: _initialize(
                root,
                raw_items=[
                    {
                        "fact": "三句证据。",
                        "status": "已发生",
                        "evidence": RESPONSIBILITY_TEXT_1,
                    }
                ],
            ),
        ),
    )


def f25_caller_location_rejected(root: Path) -> tuple[str, ...]:
    return (
        _capture_unchanged(
            root,
            "B01_CANDIDATE_VERSION_INVALID",
            lambda: _initialize(
                root,
                raw_items=[
                    {
                        "fact": "甲进入北塔。",
                        "status": "已发生",
                        "evidence": "甲走进北塔。",
                        "match_locations": [{"seg": 1, "start_byte": 0, "end_byte": 3}],
                    }
                ],
            ),
        ),
    )


def f26_legacy_writer_rejected(root: Path) -> tuple[str, ...]:
    legacy = make_legacy_read_only_candidate_fixture(
        chapter_revision_ref=chapter_revision_ref(),
        seg=1,
        origin_attempt_refs=attempt_refs(),
        raw_items=[{"text": "历史候选", "quote": "甲走进北塔。"}],
        created_at=CREATED_AT,
    )
    return (
        _capture_unchanged(
            root,
            "B01_CANDIDATE_VERSION_INVALID",
            lambda: CandidateVersionStore.stage_root(
                FixtureStore.empty_state(),
                legacy,
                author_workspace_logical_key="fixture-workspace-001",
                reference_records=_valid_candidate_refs(),
            ),
        ),
    )


FAILURE_SCENARIOS: dict[str, Callable[[Path], tuple[str, ...]]] = {
    "F01_ADMISSION_MISSING": f01_admission_missing,
    "F02_REVIEWED_HEAD_MERGE_HEAD_MISMATCH": f02_head_mismatch,
    "F03_MAIN_READBACK_INVALID": f03_main_readback_invalid,
    "F04_A_MANIFEST_DRIFT": f04_manifest_drift,
    "F05_A_ATTEMPT_REF_INVALID": f05_attempt_ref_invalid,
    "F06_SEGMENT_SOURCE_MISMATCH": f06_segment_source_mismatch,
    "F07_SEGMENT_NUMBER_INVALID": f07_segment_number_invalid,
    "F08_SEGMENT_RANGE_INVALID": f08_segment_range_invalid,
    "F09_RESPONSIBILITY_HASH_INVALID": f09_segment_text_hash_mismatch,
    "F10_CANDIDATE_FIELDS_INVALID": f10_candidate_fields_invalid,
    "F11_ITEM_HASH_MISMATCH": f11_item_hash_mismatch,
    "F12_DUPLICATE_LINEAGE": f12_duplicate_lineage,
    "F13_LINEAGE_INDEX_INVALID": f13_lineage_index_invalid,
    "F14_EMPTY_BASELINE_INCONSISTENT": f14_empty_baseline_inconsistent,
    "F15_CHILD_CREATION_REQUESTED": f15_child_creation_out_of_scope,
    "F16_POINTER_SCOPE_MISMATCH": f16_pointer_scope_mismatch,
    "F17_POINTER_ALREADY_INITIALIZED": f17_pointer_already_initialized,
    "F18_OPERATION_CONFLICT": f18_operation_conflict,
    "F19_VERSION_DIFF_INVALID": f19_diff_invalid_or_persisted,
    "F20_BOUNDARY_ESCAPE": f20_boundary_or_runtime_event,
    "F21_SOURCE_GENERATION_MISMATCH": f21_source_generation_mismatch,
    "F22_REQUIRED_MATERIAL_MISSING": f22_required_material_missing,
    "F23_EVIDENCE_NOT_IN_CHAPTER": f23_evidence_not_in_chapter,
    "F24_EVIDENCE_SENTENCE_LIMIT": f24_evidence_sentence_limit,
    "F25_CALLER_LOCATION_REJECTED": f25_caller_location_rejected,
    "F26_LEGACY_WRITER_REJECTED": f26_legacy_writer_rejected,
}


def run_normal_scenario(name: str, root: Path) -> dict[str, Any]:
    if name == "N08_RESTART_READBACK":
        raise AssertionError("N08 must run through the two-process self-check harness")
    return NORMAL_SCENARIOS[name](root)


def run_failure_scenario(name: str, root: Path) -> tuple[str, ...]:
    return FAILURE_SCENARIOS[name](root)


def inherited_fixed_vectors() -> dict[str, dict[str, Any]]:
    parent_preimage = {
        "chapter_revision_ref": {
            "chapter_id": "fixture-c01",
            "revision_no": 2,
            "revision_text_sha256": "1" * 64,
        },
        "seg": 1,
        "parent_candidate_version_ref": None,
        "origin_attempt_refs": [
            {
                "contract": "M3_RECORD_REF",
                "contract_version": "r03.3-candidate",
                "record_type": "A_RAW_ATTEMPT_RECEIPT",
                "record_id": "attempt_fixture_001",
                "record_version": 1,
                "record_contract_version": "r03.3-candidate",
                "record_hash": "cd541e3c19f34ba05c60682ec9f7c752afa1b8577c6402f56bc260abd21e6f25",
                "access": "POLICY_FIXTURE_READ_ONLY",
                "source_module": "A_STAGE_FIXTURE",
            }
        ],
        "origin_commit_intent_ref": None,
        "items": [
            {
                "lineage_id": "lin_fact_001",
                "text": "角色甲进入北塔。",
                "quote": "角色甲走进北塔。",
                "item_hash": "4e3b0c357533bf3384927e89eef01268ec99cef732643bd4d854636c9dac8ea6",
            },
            {
                "lineage_id": "lin_fact_002",
                "text": "角色甲持有一把铜钥匙。",
                "quote": "铜钥匙在角色甲手中。",
                "item_hash": "5fab26a641f3e8788268ff01ebfcf5f584e113b95d13cf0521b346a916580547",
            },
        ],
        "lineage_index": [
            {
                "lineage_id": "lin_fact_001",
                "json_pointer": "/items/0",
                "item_hash": "4e3b0c357533bf3384927e89eef01268ec99cef732643bd4d854636c9dac8ea6",
            },
            {
                "lineage_id": "lin_fact_002",
                "json_pointer": "/items/1",
                "item_hash": "5fab26a641f3e8788268ff01ebfcf5f584e113b95d13cf0521b346a916580547",
            },
        ],
    }
    empty_preimage = {
        "chapter_revision_ref": {
            "chapter_id": "fixture-c01",
            "revision_no": 2,
            "revision_text_sha256": "1" * 64,
        },
        "seg": 2,
        "parent_candidate_version_ref": None,
        "origin_attempt_refs": [
            {
                "contract": "M3_RECORD_REF",
                "contract_version": "r03.3-candidate",
                "record_type": "A_RAW_ATTEMPT_RECEIPT",
                "record_id": "attempt_fixture_seg2",
                "record_version": 1,
                "record_contract_version": "r03.3-candidate",
                "record_hash": "aad5e1019d5ab7d1a429f69b94ea00f08bc9ee0e9e3568bac80630008bfee43b",
                "access": "POLICY_FIXTURE_READ_ONLY",
                "source_module": "A_STAGE_FIXTURE",
            }
        ],
        "origin_commit_intent_ref": None,
        "items": [],
        "lineage_index": [],
    }
    locator_preimage = {
        "contract": "M3_LINEAGE_LOCATOR",
        "contract_version": "r03.3-candidate",
        "candidate_version_ref": {
            "contract": "M3_RECORD_REF",
            "contract_version": "r03.3-candidate",
            "record_type": "M3_CANDIDATE_VERSION",
            "record_id": "cv_fixture_parent",
            "record_version": 3,
            "record_contract_version": "r03.3-candidate",
            "record_hash": "64405e245bd4e1d758f3848984e318acfd7912c48558f81e3aee1318eeb88f26",
            "access": "POLICY_FIXTURE_READ_ONLY",
            "source_module": "M3",
        },
        "lineage_id": "lin_fact_001",
        "json_pointer": "/items/0",
        "item_hash": "4e3b0c357533bf3384927e89eef01268ec99cef732643bd4d854636c9dac8ea6",
    }
    return {
        "parent_version_payload_hash": {
            "actual": sha256_value(parent_preimage),
            "expected": "27495dc404c3448063651be0672487332700c1624c14338a1e1712b995a0da7f",
        },
        "empty_version_payload_hash": {
            "actual": sha256_value(empty_preimage),
            "expected": "1e60cd9513280b78f7cbf9c4bf54f5f2a932a40bfcc88a0adc990c140ea74823",
        },
        "lineage_locator_hash": {
            "actual": sha256_value(locator_preimage),
            "expected": "f43f65f5435f6b7cedb4ddcc3078e9437fbf58d17a8885e3b2427e2793a0180d",
        },
    }


B01_EXPECTED_FIXED_VECTORS = {
    "candidate_version_payload_hash": "89fd57fc802a3d7311e2605ee856db033c957c178079d92367cdd9741486ef3c",
    "candidate_record_hash": "9dd89591a193754f96a7c7d3b595d16c459c01f0c4073699c5353780679f0e30",
    "segment_record_hash": "cd286d6c8a65eee0b79b41a162a809527bb3e3dd2b90c3f63680948c6962b18f",
    "pointer_snapshot_request_hash": "c0a61292f19fc5fe93e494e805613dcda3901784dcbc99f8feba71ea7755f0df",
    "pointer_record_hash": "f414ec685388c519afd8e495d69c32c6afc99cf3b5bbbdb161f4e85585d1c10a",
    "lineage_locator_hash": "18565157b3e39d4c57d43fa5974132693d0ee9cabb3e7bada631ac804445a839",
    "evidence_locator_hash": "3a78dcd55c2934662497ab14a5704ed56afd43c4fdc16b46f24d5601a7409180",
    "version_diff_detached_hash": "7e635e4cae960ca74b66cdce5ded583ffa947d31956b126e3fe83dc8697144d2",
}


def b01_fixed_vectors(root: Path) -> dict[str, dict[str, str]]:
    n07 = n07_parent_child_read_only_diff(root)
    candidate = _record_by_type(root, "M3_CANDIDATE_VERSION")
    segment = _record_by_type(root, "M3_SEGMENT_INDEX_SNAPSHOT")
    pointer = _record_by_type(root, "M3_CANDIDATE_POINTER_SNAPSHOT")
    all_refs = _all_candidate_refs(root)
    locator = CandidateVersionStore.lineage_locator(
        candidate,
        candidate["payload"]["items"][0]["lineage_id"],
        reference_records=all_refs,
    )
    evidence_locator = CandidateVersionStore.evidence_locator(
        candidate,
        candidate["payload"]["items"][0]["lineage_id"],
        reference_records=all_refs,
    )
    actual = {
        "candidate_version_payload_hash": candidate["payload"]["version_payload_hash"],
        "candidate_record_hash": candidate["record_hash"],
        "segment_record_hash": segment["record_hash"],
        "pointer_snapshot_request_hash": pointer["payload"]["snapshot_request_hash"],
        "pointer_record_hash": pointer["record_hash"],
        "lineage_locator_hash": locator["locator_hash"],
        "evidence_locator_hash": evidence_locator["locator_hash"],
        "version_diff_detached_hash": n07["version_diff_hash"],
    }
    return {
        key: {"actual": value, "expected": B01_EXPECTED_FIXED_VECTORS[key]}
        for key, value in actual.items()
    }


def canonical_fixture_vector() -> dict[str, str]:
    value = {"z": "e\u0301", "a": [3, True, None, "synthetic"]}
    return {
        "canonical_utf8_hex": canonical_bytes(value).hex(),
        "sha256": sha256_value(value),
    }

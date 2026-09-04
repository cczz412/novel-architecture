"""Product-scoped B-01 root composition over the single CandidateAuthorityStore."""

from __future__ import annotations

import hashlib
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B01_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b01_candidate_version_r03_5"
AUTHORITY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_candidate_authority_r01"
for candidate in (REPOSITORY_ROOT, B01_ROOT, AUTHORITY_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from b01_contract import (  # noqa: E402
    IMMUTABLE_RETENTION,
    PRODUCT_AUTHORITY_PROFILE,
    PRODUCT_CONTRACT_VERSION,
    PRODUCT_READ_ONLY_ACCESS,
    CandidateVersionStore,
    canonical_bytes,
    make_read_only_input_record,
    record_ref,
    sha256_value,
)
from candidate_authority import (  # noqa: E402
    CandidateAuthorityStore,
    CandidateRootInitializer,
)
from shadow_fixtures import MutableRootAuthorityReader, authority_snapshot  # noqa: E402
from work.ccz57_m3_b01_candidate_version_r03_5 import (  # noqa: E402
    fixtures as b01_fixtures,
)

PRODUCT_PROJECT_SCOPE_ID = "product-project-001"
PRODUCT_WORKSPACE_KEY = "product-workspace-001"
PRODUCT_SOURCE_IDENTITY = "CCZ142_READ_ONLY_ADAPTER"


def _rehash(record: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(record)
    result["record_hash"] = sha256_value(
        {key: value for key, value in result.items() if key != "record_hash"}
    )
    return result


def _product_upstream_record(record: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(record)
    result["access"] = PRODUCT_READ_ONLY_ACCESS
    return _rehash(result)


def _product_attempt_record() -> dict[str, Any]:
    return make_read_only_input_record(
        record_type="A_RAW_ATTEMPT_RECEIPT",
        record_id="ccz142-product-attempt-001",
        record_version=1,
        source_module="CCZ142_READ_ONLY_ADAPTER",
        access=PRODUCT_READ_ONLY_ACCESS,
        retention_class=IMMUTABLE_RETENTION,
        created_at=b01_fixtures.CREATED_AT,
        payload={
            "run_id": "ccz142-product-run-001",
            "attempt_no": 1,
            "mechanical_gate": "PASS",
            "request_sha256": "1" * 64,
            "response_sha256": "2" * 64,
        },
        contract_version=PRODUCT_CONTRACT_VERSION,
    )


def product_root_request(
    *,
    operation_id: str = "product-root-operation-001",
    project_scope_id: str = PRODUCT_PROJECT_SCOPE_ID,
    chapter_id: str = "product-chapter-001",
    revision_no: int = 1,
    seg: int = 1,
) -> dict[str, Any]:
    segment_inputs = b01_fixtures.segment_inputs()
    revision_text = "".join(item["responsibility_text"] for item in segment_inputs)
    revision_ref = {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": hashlib.sha256(
            revision_text.encode("utf-8")
        ).hexdigest(),
    }
    fixture_generation = b01_fixtures.source_generation_record(
        generation_hex="d",
        revision_ref=revision_ref,
    )
    generation = _product_upstream_record(fixture_generation)
    core = _product_upstream_record(
        b01_fixtures.material_record(
            "CORE_CHARACTER",
            source_generation=generation,
            digest_char="e",
            record_id_suffix="-product",
        )
    )
    genre = _product_upstream_record(
        b01_fixtures.material_record(
            "GENRE",
            source_generation=generation,
            digest_char="f",
            record_id_suffix="-product",
        )
    )
    attempt = _product_attempt_record()
    raw_items = (
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
        if seg == 1
        else [
            {
                "fact": "乙停在门外。",
                "status": "已发生",
                "evidence": "乙停在门外。",
                "speaker": "旁白",
            }
        ]
    )
    return {
        "admission": b01_fixtures.valid_admission(),
        "reference_records": [
            b01_fixtures.review_receipt_record(),
            b01_fixtures.interface_manifest_record(),
            attempt,
            generation,
            core,
            genre,
        ],
        "project_scope_id": project_scope_id,
        "author_workspace_logical_key": PRODUCT_WORKSPACE_KEY,
        "chapter_revision_ref": revision_ref,
        "accepted_source_generation_ref": record_ref(generation),
        "writing_material_refs": [
            {"material_kind": "CORE_CHARACTER", "material_ref": record_ref(core)},
            {"material_kind": "GENRE", "material_ref": record_ref(genre)},
        ],
        "source_module_identity": PRODUCT_SOURCE_IDENTITY,
        "segment_inputs": segment_inputs,
        "seg": seg,
        "origin_attempt_refs": [record_ref(attempt)],
        "raw_items": raw_items,
        "operation_id": operation_id,
        "created_at": b01_fixtures.CREATED_AT,
        "input_generation_id": generation["payload"]["workspace_generation_id"],
    }


def new_product_store(
    root: Path,
    *,
    project_scope_id: str = PRODUCT_PROJECT_SCOPE_ID,
    root_failure_point: str | None = None,
) -> CandidateAuthorityStore:
    store = CandidateAuthorityStore(
        root,
        project_scope_id=project_scope_id,
        root_failure_point=root_failure_point,
        authority_profile=PRODUCT_AUTHORITY_PROFILE,
    )
    store.initialize_authority_schema()
    return store


def initialize_product_root(
    root: Path,
    *,
    request: dict[str, Any] | None = None,
) -> tuple[CandidateAuthorityStore, dict[str, Any], dict[str, Any]]:
    prepared = product_root_request() if request is None else deepcopy(request)
    store = new_product_store(
        root,
        project_scope_id=prepared["project_scope_id"],
    )
    initializer = CandidateRootInitializer(
        store=store,
        authority_reader=MutableRootAuthorityReader(authority_snapshot(prepared)),
    )
    result = initializer.initialize_root(prepared)
    return store, prepared, result


def initialize_product_read_only_source_fixture(
    root: Path,
    *,
    product_request: dict[str, Any] | None = None,
) -> tuple[CandidateAuthorityStore, dict[str, Any], dict[str, Any]]:
    """Build a fixture-namespace source whose actual upstream refs are product read-only."""

    prepared = (
        product_root_request() if product_request is None else deepcopy(product_request)
    )
    fixture_attempt = b01_fixtures.attempt_record()
    source_request = deepcopy(prepared)
    source_request["operation_id"] = f"source:{prepared['operation_id']}"
    source_request["reference_records"] = [
        record
        for record in source_request["reference_records"]
        if record["record_type"] != "A_RAW_ATTEMPT_RECEIPT"
    ]
    source_request["reference_records"].append(fixture_attempt)
    source_request["origin_attempt_refs"] = [record_ref(fixture_attempt)]
    return initialize_fixture_source(root, request=source_request)


def initialize_fixture_source(
    root: Path,
    *,
    request: dict[str, Any],
) -> tuple[CandidateAuthorityStore, dict[str, Any], dict[str, Any]]:
    """Persist one validated fixture-profile source for read-only migration probes."""

    source_request = deepcopy(request)
    if "input_generation_id" not in source_request:
        accepted_generation_ref = source_request["accepted_source_generation_ref"]
        accepted_generation = next(
            record
            for record in source_request["reference_records"]
            if record_ref(record) == accepted_generation_ref
        )
        source_request["input_generation_id"] = accepted_generation["payload"][
            "workspace_generation_id"
        ]
    store = CandidateAuthorityStore(
        root,
        project_scope_id=source_request["project_scope_id"],
    )
    store.initialize_authority_schema()
    initializer = CandidateRootInitializer(
        store=store,
        authority_reader=MutableRootAuthorityReader(authority_snapshot(source_request)),
    )
    result = initializer.initialize_root(source_request)
    return store, source_request, result


def product_b01_scope(
    store: CandidateAuthorityStore,
    request: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    candidate = store.read_candidate(result["candidate_version_ref"])
    segment = store.read_aux_record(result["segment_index_snapshot_ref"])
    pointer_snapshot = store.read_aux_record(result["candidate_pointer_snapshot_ref"])
    pointer = store.read_pointer(result["logical_pointer_key"])
    validation_records = [*request["reference_records"], deepcopy(segment)]
    lineages = [
        CandidateVersionStore.lineage_locator(
            candidate,
            item["lineage_id"],
            reference_records=validation_records,
        )
        for item in candidate["payload"]["items"]
    ]
    evidence = [
        CandidateVersionStore.evidence_locator(
            candidate,
            item["lineage_id"],
            reference_records=validation_records,
        )
        for item in candidate["payload"]["items"]
    ]
    if canonical_bytes(pointer["current_candidate_version_ref"]) != canonical_bytes(
        record_ref(candidate)
    ):
        raise AssertionError("PRODUCT_ROOT_POINTER_MISMATCH")
    return {
        "segment_index": segment,
        "candidate_version": candidate,
        "pointer_snapshot": pointer_snapshot,
        "live_pointer": pointer,
        "reference_records": deepcopy(request["reference_records"]),
        "segment_inputs": deepcopy(request["segment_inputs"]),
        "lineage_locators": lineages,
        "evidence_locators": evidence,
    }

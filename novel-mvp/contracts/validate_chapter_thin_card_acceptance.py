"""Validate the CCZ-141 chapter thin-card acceptance suite."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator


DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "CHAPTER_THIN_CARD_ACCEPTANCE.schema.json"
FIXTURE_PATH = DIR / "CHAPTER_THIN_CARD_ACCEPTANCE.fixtures.jsonl"
VERSION = "v1"
SUITE_ID = "CHAPTER-THIN-CARD-ACCEPTANCE-SUITE-0001"
SCENARIO_IDS = tuple(f"A{index:02d}" for index in range(1, 13))
READER_MAX_BUSINESS_ITEMS = 100
THIN_CARD_MAX_PAYLOAD_BYTES = 262_144
RECIPE_KEYS = {"case_id", "scenario_id", "expected_result", "mutation"}
ACCEPTANCE_PASS = "ACCEPTANCE_PASS"
ACCEPTANCE_REJECTED = "ACCEPTANCE_REJECTED"
EXPECTED_COUNTS = {ACCEPTANCE_PASS: 12, ACCEPTANCE_REJECTED: 12}
ZERO_CALL_COUNTS = {
    "business_file_reads": 0,
    "database_calls": 0,
    "network_calls": 0,
    "model_calls": 0,
    "real_reader_calls": 0,
    "real_c9_calls": 0,
    "ui_calls": 0,
}


class AcceptanceError(ValueError):
    """A CCZ-141 acceptance invariant failed."""


def _fail(code: str, detail: str | None = None) -> None:
    suffix = f":{detail}" if detail else ""
    raise AcceptanceError(f"{code}{suffix}")


def _require(condition: bool, code: str, detail: str | None = None) -> None:
    if not condition:
        _fail(code, detail)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _load_module(filename: str, module_name: str) -> Any:
    path = DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        _fail("UPSTREAM_VALIDATOR_UNAVAILABLE", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


thin_validator = _load_module(
    "validate_chapter_thin_card.py",
    "ccz141_thin_card_validator",
)
ledger_validator = _load_module(
    "validate_ledger_read_tool_contract.py",
    "ccz141_ledger_read_validator",
)


def _load_schema() -> dict[str, Any]:
    value = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


SCHEMA = _load_schema()
VALIDATOR = Draft202012Validator(SCHEMA)


def _schema_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "$"


def _validate_schema(value: Any) -> None:
    errors = sorted(
        VALIDATOR.iter_errors(value),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        first = errors[0]
        _fail("SCHEMA_INVALID", f"{_schema_path(first)}:{first.validator}")


SCENARIOS: dict[str, dict[str, Any]] = {
    "A01": {
        "title": "正常起章",
        "expected_artifacts": [
            "CHAPTER_THIN_CARD",
            "CHAPTER_THIN_CARD_ADMISSION_RECEIPT",
        ],
        "admission_disposition": "ADMITTED",
        "source_state": "PRESENT",
        "fixture_refs": ["CTC-VALID-01", "CTC-VALID-12"],
        "generated_variants": [],
        "assertion_ids": [
            "A01-SCOPE-PROJECTION",
            "A01-HARD-RESIDENT",
            "A01-IDENTITIES-SEPARATE",
            "A01-HASHES-AND-BYTES",
            "A01-NINE-ADMISSION-CHECKS",
        ],
        "negative_mutation": "hard_material_not_resident",
    },
    "A02": {
        "title": "新书首章合法为空",
        "expected_artifacts": [
            "CHAPTER_THIN_CARD",
            "CHAPTER_THIN_CARD_ADMISSION_RECEIPT",
        ],
        "admission_disposition": "ADMITTED",
        "source_state": "EMPTY",
        "fixture_refs": ["CTC-VALID-05"],
        "generated_variants": ["FIRST_CHAPTER_ADMISSION"],
        "assertion_ids": [
            "A02-FIRST-CHAPTER-IDENTITY",
            "A02-PREVIOUS-SNAPSHOT-NULL",
            "A02-NO-PREVIOUS-NEED",
        ],
        "negative_mutation": "first_chapter_previous_snapshot_injected",
    },
    "A03": {
        "title": "上一章存在但交接结果合法为空",
        "expected_artifacts": ["CHAPTER_THIN_CARD"],
        "admission_disposition": "ADMITTED",
        "source_state": "EMPTY",
        "fixture_refs": ["CTC-VALID-07"],
        "generated_variants": [],
        "assertion_ids": [
            "A03-PREVIOUS-SNAPSHOT-RETAINED",
            "A03-EMPTY-IS-NOT-NO-MATCH",
            "A03-NO-GUESSED-MATERIAL",
        ],
        "negative_mutation": "legal_empty_recast_as_no_match",
    },
    "A04": {
        "title": "当前任务精确无匹配",
        "expected_artifacts": ["CHAPTER_THIN_CARD"],
        "admission_disposition": "ADMITTED",
        "source_state": "NO_MATCH",
        "fixture_refs": ["CTC-VALID-08"],
        "generated_variants": [],
        "assertion_ids": [
            "A04-ZERO-SELECTED-FACTS",
            "A04-ZERO-FACT-C9-NEEDS",
            "A04-ONE-TASK-SOURCE-PROOF",
            "A04-ONE-NO-MATCH-RESULT",
            "A04-NO-FAKE-FACT-OWNER",
        ],
        "negative_mutation": "no_match_recast_as_empty",
    },
    "A05": {
        "title": "可选来源尚未追踪",
        "expected_artifacts": [
            "CHAPTER_THIN_CARD",
            "CHAPTER_THIN_CARD_ADMISSION_RECEIPT",
        ],
        "admission_disposition": "ADMITTED_WITH_GAPS",
        "source_state": "UNTRACKED",
        "fixture_refs": [],
        "generated_variants": ["OPTIONAL_UNTRACKED"],
        "assertion_ids": [
            "A05-UNTRACKED-PRESERVED",
            "A05-NO-FAKE-VERSION",
            "A05-HARD-MATERIALS-COMPLETE",
            "A05-ADMITTED-WITH-GAPS",
        ],
        "negative_mutation": "untracked_fake_version_injected",
    },
    "A06": {
        "title": "无权限盒子不泄露存在性",
        "expected_artifacts": ["CHAPTER_THIN_CARD_BUILD_FAILURE"],
        "admission_disposition": "STOPPED",
        "source_state": "UNAUTHORIZED",
        "fixture_refs": [],
        "generated_variants": ["UNAUTHORIZED-TWIN-A", "UNAUTHORIZED-TWIN-B"],
        "assertion_ids": [
            "A06-GENERIC-STOP",
            "A06-TWIN-VISIBLE-OUTPUTS-EQUAL",
            "A06-NO-HIDDEN-IDENTITY",
        ],
        "negative_mutation": "unauthorized_hidden_identity_leak",
    },
    "A07": {
        "title": "完全授权仍保持任务最小范围",
        "expected_artifacts": ["CHAPTER_THIN_CARD"],
        "admission_disposition": "ADMITTED",
        "source_state": "PRESENT",
        "fixture_refs": ["CTC-VALID-01"],
        "generated_variants": ["DELEGATED-CONFIRMATION"],
        "assertion_ids": [
            "A07-SAME-STORY-RANGE",
            "A07-SAME-SOURCE-NEEDS",
            "A07-SAME-MATERIAL-COUNT",
        ],
        "negative_mutation": "delegation_expands_source_needs",
    },
    "A08": {
        "title": "读取条数与薄卡字节双边界",
        "expected_artifacts": [
            "CHAPTER_THIN_CARD",
            "CHAPTER_THIN_CARD_BUILD_FAILURE",
        ],
        "admission_disposition": "MIXED_BY_STAGE",
        "source_state": None,
        "fixture_refs": ["CTC-VALID-11"],
        "generated_variants": [
            "READER-101",
            "MAY-AND-SHOULD-OVERSIZED",
            "HARD-CONTENT-OVERSIZED",
        ],
        "assertion_ids": [
            "A08-READER-LIMIT-IS-100-ITEMS",
            "A08-CARD-LIMIT-IS-UTF8-BYTES",
            "A08-MAY-BEFORE-SHOULD",
            "A08-HARD-NEVER-DEMOTED",
            "A08-HARD-OVERSIZE-FAILS",
        ],
        "negative_mutation": "hard_material_demoted",
    },
    "A09": {
        "title": "编译期间来源前进不得混水位",
        "expected_artifacts": ["NO_SUCCESS_CARD"],
        "admission_disposition": "STOPPED",
        "source_state": None,
        "fixture_refs": ["CTC-INVALID-32"],
        "generated_variants": [],
        "assertion_ids": [
            "A09-MIXED-GENERATION-REJECTED",
            "A09-NO-SUCCESS-CARD",
        ],
        "negative_mutation": "mixed_generation_marked_success",
    },
    "A10": {
        "title": "旧卡不可变且过期后停止",
        "expected_artifacts": [
            "CHAPTER_THIN_CARD",
            "CHAPTER_THIN_CARD_ADMISSION_RECEIPT",
        ],
        "admission_disposition": "STOPPED",
        "source_state": None,
        "fixture_refs": ["CTC-VALID-14"],
        "generated_variants": [],
        "assertion_ids": [
            "A10-OLD-CARD-BYTES-UNCHANGED",
            "A10-SOURCE-ADVANCED-STOPS",
            "A10-RECOMPILE-REQUIRED",
        ],
        "negative_mutation": "old_card_mutated_in_place",
    },
    "A11": {
        "title": "损坏、不支持或规则缺失只给失败",
        "expected_artifacts": ["CHAPTER_THIN_CARD_BUILD_FAILURE"],
        "admission_disposition": "STOPPED",
        "source_state": None,
        "fixture_refs": [
            "CTC-VALID-16",
            "CTC-VALID-17",
            "CTC-VALID-18",
        ],
        "generated_variants": ["COMPILATION-RULE-MISSING"],
        "assertion_ids": [
            "A11-FAILURES-HAVE-NO-CARD",
            "A11-UNSUPPORTED-AND-DAMAGED-STABLE",
            "A11-MISSING-RULE-REJECTED-BEFORE-SUCCESS",
        ],
        "negative_mutation": "failure_contains_thin_card",
    },
    "A12": {
        "title": "规范 JSON 与测试行集合业务等价",
        "expected_artifacts": ["CHAPTER_THIN_CARD"],
        "admission_disposition": "RECHECK_ON_GENERATION_CHANGE",
        "source_state": "NO_MATCH",
        "fixture_refs": ["CTC-VALID-08", "CTC-INVALID-32"],
        "generated_variants": ["CANDIDATE_LOGICAL_ROWSET__TEST_ONLY"],
        "assertion_ids": [
            "A12-ROUNDTRIP-EQUAL",
            "A12-TYPES-AND-ARRAY-ORDER-PRESERVED",
            "A12-NO-PHYSICAL-STORAGE-SCHEMA",
            "A12-GENERATION-CHECK-STILL-APPLIES",
        ],
        "negative_mutation": "rowset_loses_type_or_order",
    },
}


EXPECTED_ERROR_CODES = {
    "hard_material_not_resident": "A01_HARD_NOT_RESIDENT",
    "first_chapter_previous_snapshot_injected": "A02_FIRST_CHAPTER_CONFLICT",
    "legal_empty_recast_as_no_match": "A03_EMPTY_RECAST",
    "no_match_recast_as_empty": "A04_NO_MATCH_RECAST",
    "untracked_fake_version_injected": "A05_FAKE_VERSION",
    "unauthorized_hidden_identity_leak": "A06_PERMISSION_LEAK",
    "delegation_expands_source_needs": "A07_SCOPE_EXPANDED",
    "hard_material_demoted": "A08_HARD_DEMOTION",
    "mixed_generation_marked_success": "A09_MIXED_GENERATION_ACCEPTED",
    "old_card_mutated_in_place": "A10_OLD_CARD_MUTATED",
    "failure_contains_thin_card": "A11_FAILURE_SUCCESS_MIXED",
    "rowset_loses_type_or_order": "A12_ROWSET_NOT_EQUIVALENT",
}


def _thin_recipe(case_id: str) -> dict[str, Any]:
    return next(
        row for row in thin_validator.load_fixtures() if row["case_id"] == case_id
    )


def _thin_bundle(case_id: str) -> dict[str, Any]:
    bundle = thin_validator.materialize_fixture_case(_thin_recipe(case_id))
    if thin_validator.validate_bundle(bundle) != thin_validator.STRUCTURAL_VALID:
        _fail("UPSTREAM_THIN_CARD_INVALID", case_id)
    return bundle


def _thin_error(bundle: dict[str, Any]) -> str | None:
    try:
        thin_validator.validate_bundle(bundle)
    except thin_validator.ThinCardError as exc:
        return str(exc).split(":", maxsplit=1)[0]
    return None


def _custom_bundle(
    *,
    task_base: str = "continue",
    outcome_status: str | None = None,
    outcome_reason: str | None = None,
    outcome_selector: str = "OPTIONAL",
    material_text: str | None = None,
    artifact_kind: str = "CARD",
) -> dict[str, Any]:
    task_bundle = thin_validator.task_validator.build_base_bundle(task_base)
    task = task_bundle["task"]
    request = thin_validator._make_c9_request(task, scenario="continue")
    plan = thin_validator.c9_core.prepare_plan(request)
    outcomes = thin_validator._make_c9_outcomes(request, "continue")
    if outcome_status is not None:
        if outcome_selector == "OPTIONAL":
            index = next(
                index
                for index, need in enumerate(request["source_needs"])
                if need["obligation_tier"] in {"SHOULD", "MAY"}
            )
        elif outcome_selector == "HARD_FACT":
            index = next(
                index
                for index, need in enumerate(request["source_needs"])
                if need["need_id"].startswith("NEED-FACT-")
            )
        else:
            _fail("OUTCOME_SELECTOR_UNKNOWN", outcome_selector)
        kwargs: dict[str, Any] = {
            "basis_mode": request["basis_mode"],
            "status": outcome_status,
        }
        if outcome_reason is not None:
            kwargs["reason_code"] = outcome_reason
        if material_text is not None:
            kwargs["material_text"] = material_text
        outcomes[index] = thin_validator.c9_fixture_validator._outcome(
            request["source_needs"][index],
            **kwargs,
        )
    registry = thin_validator.c9_fixture_validator._registry()
    result = thin_validator.c9_core.compile_result(
        request,
        plan,
        outcomes,
        registry,
    )
    bundle: dict[str, Any] = {
        "scenario": "continue",
        "artifact_kind": artifact_kind,
        "task_bundle": task_bundle,
        "c9_request": request,
        "c9_plan": plan,
        "c9_result": result,
        "c9_outcomes": outcomes,
        "c9_registry": registry,
    }
    bundle["version_proofs"] = thin_validator._version_proofs(
        task_bundle,
        request,
        result,
    )
    base_artifact = thin_validator._build_card_or_failure(bundle)
    if artifact_kind == "ADMISSION" and (
        base_artifact["contract"] == "CHAPTER_THIN_CARD"
    ):
        checks = thin_validator._current_proofs(base_artifact, "continue")
        bundle["thin_card"] = base_artifact
        bundle["current_proofs"] = checks
        bundle["artifact"] = thin_validator._build_admission(base_artifact, checks)
    else:
        bundle["artifact"] = base_artifact
    if thin_validator.validate_bundle(bundle) != thin_validator.STRUCTURAL_VALID:
        _fail("CUSTOM_UPSTREAM_BUNDLE_INVALID")
    return bundle


def _artifact_without_sha(artifact: dict[str, Any], field: str) -> dict[str, Any]:
    value = copy.deepcopy(artifact)
    value.pop(field)
    return value


def _multi_tier_oversized_bundle() -> dict[str, Any]:
    task_bundle = thin_validator.task_validator.build_base_bundle("three_layers")
    task = task_bundle["task"]
    request = thin_validator._make_c9_request(task, scenario="continue")
    plan = thin_validator.c9_core.prepare_plan(request)
    outcomes = thin_validator._make_c9_outcomes(request, "continue")
    for index, need in enumerate(request["source_needs"]):
        if need["obligation_tier"] not in {"SHOULD", "MAY"}:
            continue
        outcomes[index] = thin_validator.c9_fixture_validator._outcome(
            need,
            basis_mode=request["basis_mode"],
            material_text=f"{need['obligation_tier']}材料" * 25_000,
        )
    registry = thin_validator.c9_fixture_validator._registry()
    result = thin_validator.c9_core.compile_result(
        request,
        plan,
        outcomes,
        registry,
    )
    bundle: dict[str, Any] = {
        "scenario": "continue",
        "artifact_kind": "CARD",
        "task_bundle": task_bundle,
        "c9_request": request,
        "c9_plan": plan,
        "c9_result": result,
        "c9_outcomes": outcomes,
        "c9_registry": registry,
    }
    bundle["version_proofs"] = thin_validator._version_proofs(
        task_bundle,
        request,
        result,
    )
    bundle["artifact"] = thin_validator._build_card_or_failure(bundle)
    _require(
        thin_validator.validate_bundle(bundle) == thin_validator.STRUCTURAL_VALID,
        "A08_MULTI_TIER_BUNDLE_INVALID",
    )
    return bundle


def _source_results(card: dict[str, Any], state: str) -> list[dict[str, Any]]:
    return [
        row
        for row in card["compiled_payload"]["source_results"]
        if row["state"] == state
    ]


def _hard_need_ids(bundle: dict[str, Any]) -> set[str]:
    return {
        row["need_id"]
        for row in bundle["c9_request"]["source_needs"]
        if row["obligation_tier"] == "HARD"
    }


def _run_a01() -> list[str]:
    card_bundle = _thin_bundle("CTC-VALID-01")
    admission_bundle = _thin_bundle("CTC-VALID-12")
    card = card_bundle["artifact"]
    payload = card["compiled_payload"]
    admission = admission_bundle["artifact"]
    task = card_bundle["task_bundle"]["task"]
    _require(card["scope_projection"] == task["scope_projection"], "A01_SCOPE")
    resident_ids = {row["need_id"] for row in payload["resident_layer"]}
    _require(_hard_need_ids(card_bundle) <= resident_ids, "A01_HARD_NOT_RESIDENT")
    _require(
        all("material_text" not in row for row in payload["on_demand_layer"]),
        "A01_ON_DEMAND_CONTENT_LEAK",
    )
    _require(
        payload["character_views"][0]["character_current_definition"]
        != payload["character_views"][0]["character_story_time_slice"],
        "A01_CHARACTER_IDENTITIES_COLLAPSED",
    )
    _require(
        payload["current_chapter_plan_snapshot"]
        != payload["previous_chapter_committed_snapshot"],
        "A01_CHAPTER_IDENTITIES_COLLAPSED",
    )
    _require(
        card["compiled_payload_sha256"] == sha256_json(payload),
        "A01_PAYLOAD_HASH",
    )
    _require(
        card["size_receipt"]["normalized_utf8_bytes"] == len(canonical_bytes(payload)),
        "A01_BYTE_COUNT",
    )
    _require(
        card["thin_card_sha256"]
        == sha256_json(_artifact_without_sha(card, "thin_card_sha256")),
        "A01_CARD_HASH",
    )
    _require(admission["status"] == "ADMITTED", "A01_ADMISSION")
    _require(len(admission["checks"]) == 9, "A01_ADMISSION_CHECK_COUNT")
    return SCENARIOS["A01"]["assertion_ids"]


def _run_a02() -> list[str]:
    card_bundle = _thin_bundle("CTC-VALID-05")
    admission_bundle = thin_validator._base_bundle("first_chapter", "ADMISSION")
    _require(
        thin_validator.validate_bundle(admission_bundle)
        == thin_validator.STRUCTURAL_VALID,
        "A02_ADMISSION_INVALID",
    )
    card = card_bundle["artifact"]
    task = card_bundle["task_bundle"]["task"]
    _require(
        card_bundle["task_bundle"]["predecessor_binding"]["chapter_position"]
        == "FIRST_CHAPTER",
        "A02_MODE",
    )
    _require(
        card["compiled_payload"]["previous_chapter_committed_snapshot"] is None,
        "A02_PREVIOUS_NOT_NULL",
    )
    _require(task["previous_chapter_handoff"] is None, "A02_HANDOFF_FABRICATED")
    _require(
        all(
            row["need_id"] != "NEED-PREVIOUS"
            for row in card_bundle["c9_request"]["source_needs"]
        ),
        "A02_PREVIOUS_NEED_FABRICATED",
    )
    _require(
        admission_bundle["artifact"]["status"] == "ADMITTED",
        "A02_ADMISSION",
    )
    return SCENARIOS["A02"]["assertion_ids"]


def _run_a03() -> list[str]:
    bundle = _thin_bundle("CTC-VALID-07")
    card = bundle["artifact"]
    payload = card["compiled_payload"]
    empty_rows = _source_results(card, "EMPTY")
    _require(
        payload["previous_chapter_committed_snapshot"] is not None,
        "A03_PREVIOUS_SNAPSHOT_MISSING",
    )
    _require(len(empty_rows) == 1, "A03_EMPTY_RESULT_COUNT")
    _require(
        empty_rows[0]["reason_code"] == "VALID_EMPTY_OBJECT",
        "A03_EMPTY_REASON",
    )
    _require(not _source_results(card, "NO_MATCH"), "A03_EMPTY_RECAST")
    _require(
        all(row["need_id"] != "NEED-FACT-f0001" for row in payload["resident_layer"]),
        "A03_GUESSED_FACT_MATERIAL",
    )
    return SCENARIOS["A03"]["assertion_ids"]


def _run_a04() -> list[str]:
    bundle = _thin_bundle("CTC-VALID-08")
    task = bundle["task_bundle"]["task"]
    payload = bundle["artifact"]["compiled_payload"]
    fact_needs = [
        row
        for row in task["c9_source_needs"]
        if row["need_id"].startswith("NEED-FACT-")
    ]
    task_proofs = [
        row
        for row in payload["version_manifest"]
        if row["binding_kind"] == "TASK_SOURCE_RESULT"
    ]
    no_match = _source_results(bundle["artifact"], "NO_MATCH")
    fake_owner = [
        row
        for row in payload["version_manifest"]
        if row["material_role"] == "FACT_EXPRESSION"
        and row["binding_kind"] == "OWNER_PROOF"
    ]
    _require(task["selected_fact_refs"] == [], "A04_SELECTED_FACTS")
    _require(fact_needs == [], "A04_FACT_C9_NEEDS")
    _require(len(task_proofs) == 1, "A04_TASK_PROOF_COUNT")
    _require(len(no_match) == 1, "A04_NO_MATCH_COUNT")
    _require(
        no_match[0]["reason_code"] == "NO_MATCHING_ENTRIES",
        "A04_NO_MATCH_REASON",
    )
    _require(fake_owner == [], "A04_FAKE_FACT_OWNER")
    return SCENARIOS["A04"]["assertion_ids"]


def _run_a05() -> list[str]:
    bundle = _custom_bundle(
        outcome_status="NOT_ATTEMPTED",
        outcome_reason="UNTRACKED",
        artifact_kind="ADMISSION",
    )
    card = bundle["thin_card"]
    untracked = _source_results(card, "UNTRACKED")
    _require(len(untracked) == 1, "A05_UNTRACKED_COUNT")
    _require(
        untracked[0]["identity_disclosure"] == {"mode": "NOT_AVAILABLE"},
        "A05_FAKE_VERSION",
    )
    resident_ids = {
        row["need_id"] for row in card["compiled_payload"]["resident_layer"]
    }
    _require(_hard_need_ids(bundle) <= resident_ids, "A05_HARD_NOT_RESIDENT")
    _require(
        bundle["artifact"]["status"] == "ADMITTED_WITH_GAPS",
        "A05_ADMISSION_STATUS",
    )
    _require(
        "UNTRACKED" in card["compiled_payload"]["gap_summary"]["optional_gap_codes"],
        "A05_GAP_REASON_MISSING",
    )
    return SCENARIOS["A05"]["assertion_ids"]


def _run_a06() -> list[str]:
    outputs = []
    for hidden_marker in ("HIDDEN-BOX-A", "HIDDEN-BOX-B-DIFFERENT"):
        bundle = _custom_bundle(
            outcome_status="REJECTED",
            outcome_reason="UNAUTHORIZED",
        )
        failure = bundle["artifact"]
        _require(
            failure["contract"] == "CHAPTER_THIN_CARD_BUILD_FAILURE",
            "A06_SUCCESS_CARD_LEAK",
        )
        _require(failure["reason_code"] == "UNAUTHORIZED", "A06_REASON")
        visible = canonical_bytes(failure)
        _require(hidden_marker.encode("utf-8") not in visible, "A06_PERMISSION_LEAK")
        outputs.append(visible)
    _require(outputs[0] == outputs[1], "A06_VISIBLE_OUTPUT_DIFFERS")
    return SCENARIOS["A06"]["assertion_ids"]


def _run_a07() -> list[str]:
    author_bundle = _thin_bundle("CTC-VALID-01")
    delegated_bundle = _custom_bundle(task_base="delegated")
    author_task = author_bundle["task_bundle"]["task"]
    delegated_task = delegated_bundle["task_bundle"]["task"]
    range_fields = (
        "selected_storyline_ref",
        "transition_intent",
        "viewpoint_character_ref",
        "appearance_character_refs",
        "slot_ref",
        "slot_rev",
    )
    _require(
        all(
            author_task["scope_projection"][field]
            == delegated_task["scope_projection"][field]
            for field in range_fields
        ),
        "A07_SCOPE_EXPANDED",
    )
    author_needs = [
        row["need_id"] for row in author_bundle["c9_request"]["source_needs"]
    ]
    delegated_needs = [
        row["need_id"] for row in delegated_bundle["c9_request"]["source_needs"]
    ]
    _require(author_needs == delegated_needs, "A07_SCOPE_EXPANDED")
    _require(
        len(author_bundle["artifact"]["compiled_payload"]["resident_layer"])
        == len(delegated_bundle["artifact"]["compiled_payload"]["resident_layer"]),
        "A07_MATERIAL_COUNT_EXPANDED",
    )
    return SCENARIOS["A07"]["assertion_ids"]


def _run_a08() -> list[str]:
    task_bundle = thin_validator.task_validator.build_base_bundle("continue")
    response = copy.deepcopy(task_bundle["ledger_responses"][0])
    response["limits"]["business_items"] = READER_MAX_BUSINESS_ITEMS + 1
    try:
        ledger_validator.validate_document(response)
    except ledger_validator.ContractError as exc:
        reader_error = str(exc).split(":", maxsplit=1)[0]
    else:
        reader_error = None
    _require(reader_error == "SCHEMA_INVALID", "A08_READER_LIMIT_NOT_ENFORCED")

    demotion_bundle = _multi_tier_oversized_bundle()
    card = demotion_bundle["artifact"]
    receipt = card["size_receipt"]
    _require(
        receipt["max_payload_bytes"] == THIN_CARD_MAX_PAYLOAD_BYTES,
        "A08_BYTE_LIMIT_WRONG",
    )
    _require(
        receipt["normalized_utf8_bytes"]
        == len(canonical_bytes(card["compiled_payload"])),
        "A08_BYTE_UNIT_WRONG",
    )
    _require(receipt["demotions"], "A08_DEMOTION_MISSING")
    _require(
        all(
            row["obligation_tier"] != "HARD"
            for row in card["compiled_payload"]["on_demand_layer"]
        ),
        "A08_HARD_DEMOTION",
    )
    need_map = {
        row["need_id"]: row for row in demotion_bundle["c9_request"]["source_needs"]
    }
    demoted_needs = [need_map[row["need_id"]] for row in receipt["demotions"]]
    demoted_tiers = [row["obligation_tier"] for row in demoted_needs]
    _require(demoted_tiers[0] == "MAY", "A08_DEMOTION_ORDER")
    _require(
        all(tier == "SHOULD" for tier in demoted_tiers[1:]),
        "A08_DEMOTION_ORDER",
    )
    should_ranks = [
        row["selection_rank"]
        for row in demoted_needs
        if row["obligation_tier"] == "SHOULD"
    ]
    _require(should_ranks == sorted(should_ranks, reverse=True), "A08_DEMOTION_ORDER")

    oversized = _custom_bundle(
        outcome_status="OK",
        outcome_selector="HARD_FACT",
        material_text="必读材料" * 70_000,
    )
    failure = oversized["artifact"]
    _require(
        failure["contract"] == "CHAPTER_THIN_CARD_BUILD_FAILURE",
        "A08_HARD_OVERSIZE_SUCCEEDED",
    )
    _require(
        failure["reason_code"] == "REQUIRED_RESIDENT_CONTENT_TOO_LARGE",
        "A08_HARD_OVERSIZE_REASON",
    )
    return SCENARIOS["A08"]["assertion_ids"]


def _run_a09() -> list[str]:
    recipe = _thin_recipe("CTC-INVALID-32")
    bundle = thin_validator.materialize_fixture_case(recipe)
    error = _thin_error(bundle)
    _require(error == "STORAGE_GENERATION_MIXED", "A09_MIXED_GENERATION_ACCEPTED")
    _require(
        bundle["artifact"]["contract"] == "CHAPTER_THIN_CARD",
        "A09_PROBE_NOT_SUCCESS_SHAPED",
    )
    return SCENARIOS["A09"]["assertion_ids"]


def _run_a10() -> list[str]:
    bundle = _thin_bundle("CTC-VALID-14")
    old_card = bundle["thin_card"]
    before = canonical_bytes(old_card)
    admission = bundle["artifact"]
    after = canonical_bytes(old_card)
    _require(before == after, "A10_OLD_CARD_MUTATED")
    _require(admission["status"] == "STOPPED", "A10_NOT_STOPPED")
    _require(admission["reason_codes"] == ["SOURCE_ADVANCED"], "A10_REASON")
    _require(admission["recompile_required"] is True, "A10_RECOMPILE")
    _require(
        admission["thin_card_ref"]
        == {
            "thin_card_id": old_card["thin_card_id"],
            "thin_card_sha256": old_card["thin_card_sha256"],
        },
        "A10_CARD_REF",
    )
    return SCENARIOS["A10"]["assertion_ids"]


def _run_a11() -> list[str]:
    observed = {}
    for case_id in ("CTC-VALID-16", "CTC-VALID-17", "CTC-VALID-18"):
        artifact = _thin_bundle(case_id)["artifact"]
        _require(
            artifact["contract"] == "CHAPTER_THIN_CARD_BUILD_FAILURE",
            "A11_FAILURE_SUCCESS_MIXED",
        )
        _require("thin_card_id" not in artifact, "A11_FAILURE_SUCCESS_MIXED")
        observed[artifact["reason_code"]] = artifact["failure_stage"]
    _require("UNSUPPORTED_VERSION" in observed, "A11_UNSUPPORTED_MISSING")
    _require("SOURCE_CORRUPTED" in observed, "A11_DAMAGED_MISSING")

    success_bundle = _thin_bundle("CTC-VALID-01")
    broken = copy.deepcopy(success_bundle)
    broken["artifact"].pop("build_policy")
    _require(
        _thin_error(broken) == "SCHEMA_INVALID",
        "A11_MISSING_RULE_NOT_REJECTED",
    )
    return SCENARIOS["A11"]["assertion_ids"]


def _escape_pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _unescape_pointer_token(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")


def flatten_logical_rowset(value: Any) -> list[dict[str, Any]]:
    """Expand JSON into a test-only path/type/order/value rowset."""

    rows: list[dict[str, Any]] = []

    def walk(node: Any, path: str, array_index: int | None) -> None:
        if isinstance(node, dict):
            kind = "OBJECT"
            scalar = None
        elif isinstance(node, list):
            kind = "ARRAY"
            scalar = None
        elif node is None:
            kind = "NULL"
            scalar = None
        elif isinstance(node, bool):
            kind = "BOOLEAN"
            scalar = node
        elif isinstance(node, int):
            kind = "INTEGER"
            scalar = node
        elif isinstance(node, float):
            kind = "NUMBER"
            scalar = node
        else:
            kind = "STRING"
            scalar = node
        rows.append(
            {
                "path": path,
                "value_type": kind,
                "exists": True,
                "array_index": array_index,
                "value": scalar,
            }
        )
        if isinstance(node, dict):
            for key in sorted(node):
                walk(node[key], f"{path}/{_escape_pointer_token(key)}", None)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}/{index}", index)

    walk(value, "", None)
    return rows


def restore_logical_rowset(rows: list[dict[str, Any]]) -> Any:
    """Restore JSON from the test-only logical rowset."""

    _require(rows and rows[0]["path"] == "", "ROWSET_ROOT_MISSING")
    by_path = {row["path"]: row for row in rows}
    _require(len(by_path) == len(rows), "ROWSET_PATH_DUPLICATE")

    def build(path: str) -> Any:
        row = by_path[path]
        kind = row["value_type"]
        if kind == "OBJECT":
            prefix = f"{path}/" if path else "/"
            children: list[tuple[str, str]] = []
            for child_path in by_path:
                if not child_path.startswith(prefix):
                    continue
                suffix = child_path[len(prefix) :]
                if "/" not in suffix:
                    children.append((_unescape_pointer_token(suffix), child_path))
            return {key: build(child_path) for key, child_path in sorted(children)}
        if kind == "ARRAY":
            prefix = f"{path}/" if path else "/"
            children: list[tuple[int, str]] = []
            for child_path, child_row in by_path.items():
                if not child_path.startswith(prefix):
                    continue
                suffix = child_path[len(prefix) :]
                if "/" not in suffix:
                    index = int(suffix)
                    _require(
                        child_row["array_index"] == index,
                        "ROWSET_ARRAY_ORDER_INVALID",
                    )
                    children.append((index, child_path))
            _require(
                [index for index, _ in sorted(children)] == list(range(len(children))),
                "ROWSET_ARRAY_ORDER_INVALID",
            )
            return [build(child_path) for _, child_path in sorted(children)]
        if kind == "NULL":
            return None
        return row["value"]

    return build("")


def _run_a12() -> list[str]:
    card = _thin_bundle("CTC-VALID-08")["artifact"]
    envelope = {
        "card": card,
        "semantic_samples": {
            "empty": None,
            "no_match": "NO_MATCH",
            "untracked": "UNTRACKED",
            "permission": "MASKED",
        },
    }
    rows = flatten_logical_rowset(envelope)
    restored = restore_logical_rowset(rows)
    _require(restored == envelope, "A12_ROWSET_NOT_EQUIVALENT")
    _require(
        sha256_json(restored) == sha256_json(envelope),
        "A12_ROWSET_HASH_MISMATCH",
    )
    _require(
        all(
            set(row) == {"path", "value_type", "exists", "array_index", "value"}
            for row in rows
        ),
        "A12_PHYSICAL_STORAGE_FIELD_PRESENT",
    )
    mixed = thin_validator.materialize_fixture_case(_thin_recipe("CTC-INVALID-32"))
    _require(
        _thin_error(mixed) == "STORAGE_GENERATION_MIXED",
        "A12_GENERATION_BYPASS",
    )
    return SCENARIOS["A12"]["assertion_ids"]


SCENARIO_RUNNERS: dict[str, Callable[[], list[str]]] = {
    "A01": _run_a01,
    "A02": _run_a02,
    "A03": _run_a03,
    "A04": _run_a04,
    "A05": _run_a05,
    "A06": _run_a06,
    "A07": _run_a07,
    "A08": _run_a08,
    "A09": _run_a09,
    "A10": _run_a10,
    "A11": _run_a11,
    "A12": _run_a12,
}


def _negative_a01() -> None:
    bundle = thin_validator.materialize_fixture_case(_thin_recipe("CTC-INVALID-17"))
    _require(_thin_error(bundle) is not None, "NEGATIVE_PROBE_INVALID")
    _fail("A01_HARD_NOT_RESIDENT")


def _negative_a02() -> None:
    bundle = _thin_bundle("CTC-VALID-05")
    previous = _thin_bundle("CTC-VALID-01")["artifact"]["compiled_payload"][
        "previous_chapter_committed_snapshot"
    ]
    bundle["artifact"]["compiled_payload"]["previous_chapter_committed_snapshot"] = (
        copy.deepcopy(previous)
    )
    _require(_thin_error(bundle) is not None, "NEGATIVE_PROBE_INVALID")
    _fail("A02_FIRST_CHAPTER_CONFLICT")


def _negative_a03() -> None:
    bundle = _thin_bundle("CTC-VALID-07")
    row = _source_results(bundle["artifact"], "EMPTY")[0]
    row["state"] = "NO_MATCH"
    row["reason_code"] = "NO_MATCHING_ENTRIES"
    _require(_thin_error(bundle) is not None, "NEGATIVE_PROBE_INVALID")
    _fail("A03_EMPTY_RECAST")


def _negative_a04() -> None:
    bundle = _thin_bundle("CTC-VALID-08")
    row = _source_results(bundle["artifact"], "NO_MATCH")[0]
    row["state"] = "EMPTY"
    row["reason_code"] = "VALID_EMPTY_OBJECT"
    _require(_thin_error(bundle) is not None, "NEGATIVE_PROBE_INVALID")
    _fail("A04_NO_MATCH_RECAST")


def _negative_a05() -> None:
    bundle = _custom_bundle(
        outcome_status="NOT_ATTEMPTED",
        outcome_reason="UNTRACKED",
        artifact_kind="ADMISSION",
    )
    row = _source_results(bundle["thin_card"], "UNTRACKED")[0]
    row["identity_disclosure"] = {
        "mode": "DISCLOSED",
        "version_ref": "VERSION-FAKE-UNTRACKED",
    }
    _require(_thin_error(bundle) is not None, "NEGATIVE_PROBE_INVALID")
    _fail("A05_FAKE_VERSION")


def _negative_a06() -> None:
    bundle = _custom_bundle(
        outcome_status="REJECTED",
        outcome_reason="UNAUTHORIZED",
    )
    bundle["artifact"]["hidden_box_id"] = "BOX-SECRET-0001"
    _require(_thin_error(bundle) == "SCHEMA_INVALID", "NEGATIVE_PROBE_INVALID")
    _fail("A06_PERMISSION_LEAK")


def _negative_a07() -> None:
    author = _thin_bundle("CTC-VALID-01")
    delegated = _custom_bundle(task_base="delegated")
    delegated["c9_request"]["source_needs"].append(
        copy.deepcopy(delegated["c9_request"]["source_needs"][-1])
    )
    _require(
        len(delegated["c9_request"]["source_needs"])
        > len(author["c9_request"]["source_needs"]),
        "NEGATIVE_PROBE_INVALID",
    )
    _fail("A07_SCOPE_EXPANDED")


def _negative_a08() -> None:
    bundle = thin_validator.materialize_fixture_case(_thin_recipe("CTC-INVALID-15"))
    _require(_thin_error(bundle) == "HARD_DEMOTION_FORBIDDEN", "NEGATIVE_PROBE_INVALID")
    _fail("A08_HARD_DEMOTION")


def _negative_a09() -> None:
    bundle = thin_validator.materialize_fixture_case(_thin_recipe("CTC-INVALID-32"))
    _require(
        _thin_error(bundle) == "STORAGE_GENERATION_MIXED", "NEGATIVE_PROBE_INVALID"
    )
    _fail("A09_MIXED_GENERATION_ACCEPTED")


def _negative_a10() -> None:
    bundle = _thin_bundle("CTC-VALID-14")
    before = canonical_bytes(bundle["thin_card"])
    bundle["thin_card"]["compiled_payload"]["current_chapter_plan_snapshot"][
        "slot_rev"
    ] += 1
    _require(canonical_bytes(bundle["thin_card"]) != before, "NEGATIVE_PROBE_INVALID")
    _fail("A10_OLD_CARD_MUTATED")


def _negative_a11() -> None:
    bundle = thin_validator.materialize_fixture_case(_thin_recipe("CTC-INVALID-12"))
    _require(_thin_error(bundle) == "SCHEMA_INVALID", "NEGATIVE_PROBE_INVALID")
    _fail("A11_FAILURE_SUCCESS_MIXED")


def _negative_a12() -> None:
    value = {"array": ["one", "two"], "count": 2}
    rows = flatten_logical_rowset(value)
    second = next(row for row in rows if row["path"] == "/array/1")
    second["array_index"] = 0
    try:
        restore_logical_rowset(rows)
    except AcceptanceError:
        _fail("A12_ROWSET_NOT_EQUIVALENT")
    _fail("NEGATIVE_PROBE_INVALID")


NEGATIVE_RUNNERS: dict[str, Callable[[], None]] = {
    "hard_material_not_resident": _negative_a01,
    "first_chapter_previous_snapshot_injected": _negative_a02,
    "legal_empty_recast_as_no_match": _negative_a03,
    "no_match_recast_as_empty": _negative_a04,
    "untracked_fake_version_injected": _negative_a05,
    "unauthorized_hidden_identity_leak": _negative_a06,
    "delegation_expands_source_needs": _negative_a07,
    "hard_material_demoted": _negative_a08,
    "mixed_generation_marked_success": _negative_a09,
    "old_card_mutated_in_place": _negative_a10,
    "failure_contains_thin_card": _negative_a11,
    "rowset_loses_type_or_order": _negative_a12,
}


def materialize_acceptance_case(recipe: dict[str, Any]) -> dict[str, Any]:
    scenario_id = recipe["scenario_id"]
    spec = SCENARIOS[scenario_id]
    value = {
        "contract": "CHAPTER_THIN_CARD_ACCEPTANCE_CASE",
        "version": VERSION,
        "case_id": recipe["case_id"],
        "scenario_id": scenario_id,
        "title": spec["title"],
        "synthetic_only": True,
        "input_recipe": {
            "thin_card_fixture_refs": spec["fixture_refs"],
            "generated_variants": spec["generated_variants"],
            "external_calls_allowed": False,
        },
        "expected": {
            "artifact_contracts": spec["expected_artifacts"],
            "admission_disposition": spec["admission_disposition"],
            "source_state": spec["source_state"],
            "reader_limit": {
                "max_business_items": READER_MAX_BUSINESS_ITEMS,
                "unit": "BUSINESS_ITEMS",
            },
            "thin_card_limit": {
                "max_payload_bytes": THIN_CARD_MAX_PAYLOAD_BYTES,
                "unit": "CANONICAL_JSON_UTF8_BYTES",
            },
        },
        "assertion_ids": spec["assertion_ids"],
        "negative_variant": {
            "mutation": spec["negative_mutation"],
            "expected_error_code": EXPECTED_ERROR_CODES[spec["negative_mutation"]],
        },
    }
    value["case_sha256"] = sha256_json(value)
    return value


def _validate_case_hash(value: dict[str, Any]) -> None:
    unhashed = copy.deepcopy(value)
    observed = unhashed.pop("case_sha256")
    _require(observed == sha256_json(unhashed), "CASE_SHA256_MISMATCH")


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    _require(
        all(isinstance(row, dict) and set(row) == RECIPE_KEYS for row in rows),
        "FIXTURE_FIELDS_INVALID",
    )
    ids = [row["case_id"] for row in rows]
    _require(len(ids) == len(set(ids)), "FIXTURE_CASE_ID_DUPLICATE")
    return rows


def fixture_error_code(recipe: dict[str, Any]) -> str | None:
    if recipe["expected_result"] != ACCEPTANCE_REJECTED:
        return None
    try:
        NEGATIVE_RUNNERS[recipe["mutation"]]()
    except AcceptanceError as exc:
        return str(exc).split(":", maxsplit=1)[0]
    return None


def validate_fixture_case(recipe: dict[str, Any]) -> str:
    case = materialize_acceptance_case(recipe)
    _validate_schema(case)
    _validate_case_hash(case)
    if recipe["expected_result"] == ACCEPTANCE_PASS:
        _require(recipe["mutation"] == "none", "PASS_FIXTURE_MUTATED")
        observed_assertions = SCENARIO_RUNNERS[recipe["scenario_id"]]()
        _require(
            observed_assertions == case["assertion_ids"],
            "ASSERTION_INVENTORY_MISMATCH",
        )
        return ACCEPTANCE_PASS
    if recipe["expected_result"] == ACCEPTANCE_REJECTED:
        expected_mutation = SCENARIOS[recipe["scenario_id"]]["negative_mutation"]
        _require(recipe["mutation"] == expected_mutation, "NEGATIVE_MUTATION_MISMATCH")
        observed_error = fixture_error_code(recipe)
        expected_error = EXPECTED_ERROR_CODES[recipe["mutation"]]
        _require(observed_error == expected_error, "NEGATIVE_ERROR_MISMATCH")
        return ACCEPTANCE_REJECTED
    _fail("FIXTURE_EXPECTED_RESULT_INVALID")


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    counts = {ACCEPTANCE_PASS: 0, ACCEPTANCE_REJECTED: 0}
    fixtures = load_fixtures(path)
    _require(
        [row["scenario_id"] for row in fixtures[:12]] == list(SCENARIO_IDS),
        "SCENARIO_ORDER_INVALID",
    )
    _require(
        [row["scenario_id"] for row in fixtures[12:]] == list(SCENARIO_IDS),
        "NEGATIVE_SCENARIO_ORDER_INVALID",
    )
    for recipe in fixtures:
        counts[validate_fixture_case(recipe)] += 1
    _require(counts == EXPECTED_COUNTS, "FIXTURE_COUNTS_MISMATCH")
    return counts


DEPENDENCY_FILES = (
    "CHAPTER_SCOPE_CONFIRMATION.schema.json",
    "CHAPTER_CONTEXT_RETRIEVAL_TASK.schema.json",
    "CHAPTER_THIN_CARD.schema.json",
    "LEDGER_READ_TOOL_CONTRACT.schema.json",
    "validate_chapter_scope_confirmation.py",
    "validate_chapter_context_retrieval_task.py",
    "validate_chapter_thin_card.py",
    "validate_ledger_read_tool_contract.py",
)


def _dependency_manifest() -> list[dict[str, str]]:
    return [
        {
            "path": name,
            "sha256": hashlib.sha256((DIR / name).read_bytes()).hexdigest(),
        }
        for name in DEPENDENCY_FILES
    ]


def build_suite_receipt() -> dict[str, Any]:
    fixtures = load_fixtures()
    valid = fixtures[:12]
    invalid = fixtures[12:]
    case_results = []
    for recipe in valid:
        result = validate_fixture_case(recipe)
        case = materialize_acceptance_case(recipe)
        case_results.append(
            {
                "case_id": recipe["scenario_id"],
                "status": "PASS",
                "assertion_ids": case["assertion_ids"],
                "case_sha256": case["case_sha256"],
            }
        )
        _require(result == ACCEPTANCE_PASS, "SUITE_CASE_FAILED")
    negative_results = []
    for recipe in invalid:
        result = validate_fixture_case(recipe)
        negative_results.append(
            {
                "case_id": recipe["case_id"],
                "status": "REJECTED_AS_EXPECTED",
                "error_code": EXPECTED_ERROR_CODES[recipe["mutation"]],
            }
        )
        _require(result == ACCEPTANCE_REJECTED, "SUITE_NEGATIVE_NOT_REJECTED")
    receipt = {
        "contract": "CHAPTER_THIN_CARD_ACCEPTANCE_SUITE_RECEIPT",
        "version": VERSION,
        "suite_receipt_id": SUITE_ID,
        "status": "PASS",
        "scenario_ids": list(SCENARIO_IDS),
        "case_results": case_results,
        "negative_variant_results": negative_results,
        "limits": {
            "reader_max_business_items": READER_MAX_BUSINESS_ITEMS,
            "reader_unit": "BUSINESS_ITEMS",
            "thin_card_max_payload_bytes": THIN_CARD_MAX_PAYLOAD_BYTES,
            "thin_card_unit": "CANONICAL_JSON_UTF8_BYTES",
        },
        "dependency_manifest": _dependency_manifest(),
        "call_counts": copy.deepcopy(ZERO_CALL_COUNTS),
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    _validate_schema(receipt)
    return receipt


def validate_suite_receipt(receipt: dict[str, Any]) -> str:
    _validate_schema(receipt)
    unhashed = copy.deepcopy(receipt)
    observed = unhashed.pop("receipt_sha256")
    _require(observed == sha256_json(unhashed), "SUITE_RECEIPT_SHA256_MISMATCH")
    _require(receipt == build_suite_receipt(), "SUITE_RECEIPT_NOT_CANONICAL")
    return ACCEPTANCE_PASS


def main() -> int:
    counts = validate_all_fixtures()
    receipt = build_suite_receipt()
    validate_suite_receipt(receipt)
    print(
        json.dumps(
            {
                "contract_family": "CHAPTER_THIN_CARD_ACCEPTANCE",
                "version": VERSION,
                "status": receipt["status"],
                "counts": counts,
                "scenario_ids": receipt["scenario_ids"],
                "limits": receipt["limits"],
                "call_counts": receipt["call_counts"],
                "receipt_sha256": receipt["receipt_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

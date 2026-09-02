from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
CONTRACTS = PRODUCT_ROOT / "contracts"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import unified_retrieval_core as core
finally:
    sys.path.pop(0)


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, CONTRACTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger_validator = _load(
    "c9_test_ledger_validator",
    "validate_ledger_read_tool_contract.py",
)
provenance_validator = _load(
    "c9_test_provenance_validator",
    "validate_traceable_provenance_seal.py",
)
settlement_validator = _load(
    "c9_test_settlement_validator",
    "validate_chapter_settlement_seal.py",
)
summary_validator = _load(
    "c9_test_summary_validator",
    "validate_chapter_layered_summary.py",
)


def _scope() -> dict[str, Any]:
    return {
        "author_id": "AUTHOR-0001",
        "project_id": "PROJECT-0001",
        "task_id": "TASK-C9-TEST",
        "consumer_id": "CCZ-139-NEXT-CHAPTER",
        "workpoint_ref": "chapter:c13",
        "story_scope_ref": "story-phase:phase-02",
        "sandbox_ref": "sandbox:c13",
        "upstream_card_ref": "card:next-chapter-c13",
    }


def _need(
    need_id: str,
    *,
    layer: str = "LEDGER_OBJECT",
    parent: str | None = None,
    source_contract: str = "LEDGER_READ_TOOL_CONTRACT",
    obligation: str = "HARD",
    rank: int | None = None,
    tokens: int = 20,
    trigger: str = "INITIAL",
) -> dict[str, Any]:
    return {
        "need_id": need_id,
        "evidence_layer": layer,
        "parent_need_id": parent,
        "source_contract": source_contract,
        "source_contract_version": core.SOURCE_CONTRACT_VERSIONS[source_contract],
        "object_ref": f"test://{need_id}",
        "actuality_class": "CURRENT_FACT_OR_STATE",
        "obligation_tier": obligation,
        "selection_rank": rank,
        "task_relation": f"当前测试任务需要 {need_id}",
        "estimated_tokens": tokens,
        "recall_disposition": "RETRIEVABLE",
        "recall_handle": f"test-recall://{need_id}",
        "expansion_trigger": trigger,
    }


def _request(
    needs: list[dict[str, Any]],
    *,
    basis_mode: str = "current_at_start",
    behavior: str = "WARN_AND_CONTINUE",
    budget: int = 300,
) -> dict[str, Any]:
    return core.seal_request(
        {
            "contract": "C9_RETRIEVAL_REQUEST",
            "version": core.VERSION,
            "scope": _scope(),
            "basis_mode": basis_mode,
            "task_actuality_scope": "CURRENT_TRUTH_REQUIRED",
            "budget": {
                "limit_tokens": budget,
                "estimator_ref": "test-estimator-v1",
            },
            "gap_policy": {
                "policy_ref": "test-gap-policy-v1",
                "missing_required_behavior": behavior,
            },
            "source_needs": copy.deepcopy(needs),
        }
    )


def _ledger_response(case_id: str) -> dict[str, Any]:
    case = next(
        row for row in ledger_validator.load_fixtures()
        if row["case_id"] == case_id
    )
    return copy.deepcopy(case["document"])


def _provenance(case_id: str = "TPS-VALID-01") -> dict[str, Any]:
    case = next(
        row for row in provenance_validator.load_fixtures()
        if row["case_id"] == case_id
    )
    return copy.deepcopy(case["document"])


def _summary_bundle() -> dict[str, Any]:
    return summary_validator.build_base_bundle("valid_phase")


def _registry(summary_bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = summary_bundle or _summary_bundle()

    def validate_summary(document: Any) -> str:
        return summary_validator.validate_summary(
            document,
            bundle["settlements"],
            bundle["summaries"],
        )

    return {
        "LEDGER_READ_TOOL_CONTRACT": ledger_validator.validate_document,
        "TRACEABLE_PROVENANCE_SEAL": provenance_validator.validate_seal,
        "CHAPTER_SETTLEMENT_SEAL": settlement_validator.validate_settlement,
        "CHAPTER_LAYERED_SUMMARY": validate_summary,
    }


def _outcome(
    need: dict[str, Any],
    document: dict[str, Any],
    text: str | None,
) -> dict[str, Any]:
    return {
        "need_id": need["need_id"],
        "source_status": document.get("status", "OK"),
        "reason_code": document.get("reason_code"),
        "source_document": copy.deepcopy(document),
        "material_text": text,
        "validator_id": f"test-validator:{need['source_contract']}",
    }


def _not_attempted(need: dict[str, Any]) -> dict[str, Any]:
    return {
        "need_id": need["need_id"],
        "source_status": "NOT_ATTEMPTED",
        "reason_code": "OWNER_RUNTIME_NOT_AVAILABLE",
        "source_document": None,
        "material_text": None,
        "validator_id": None,
    }


def test_real_adjacent_validators_feed_one_deterministic_three_layer_run() -> None:
    needs = [
        _need("NEED-SETTLEMENT", source_contract="CHAPTER_SETTLEMENT_SEAL"),
        _need(
            "NEED-SUMMARY",
            source_contract="CHAPTER_LAYERED_SUMMARY",
            obligation="SHOULD",
            rank=1,
        ),
        _need(
            "NEED-FORMATION",
            layer="FORMATION_BASIS",
            parent="NEED-SETTLEMENT",
            source_contract="TRACEABLE_PROVENANCE_SEAL",
            obligation="SHOULD",
            rank=2,
            trigger="CONFLICT_DETECTED",
        ),
        _need(
            "NEED-ORIGINAL",
            layer="ORIGINAL_EVIDENCE",
            parent="NEED-FORMATION",
            obligation="MAY",
            rank=3,
            trigger="AUDIT_REQUIRED",
        ),
    ]
    request = _request(needs)
    plan = core.prepare_plan(request)
    summary_bundle = _summary_bundle()
    documents = [
        settlement_validator.build_base_document("resolved_full"),
        summary_bundle["document"],
        _provenance(),
        _ledger_response("LR-VALID-07"),
    ]
    outcomes = [
        _outcome(need, document, f"{need['need_id']} 的合成内容")
        for need, document in zip(needs, documents, strict=True)
    ]
    before_request = copy.deepcopy(request)
    before_outcomes = copy.deepcopy(outcomes)

    first = core.compile_result(
        request,
        plan,
        outcomes,
        _registry(summary_bundle),
    )
    second = core.compile_result(
        request,
        plan,
        outcomes,
        _registry(summary_bundle),
    )

    assert first == second
    assert first["status"] == "READY"
    assert first["replay_status"] == "AUDITABLE_CURRENT_NOT_REPLAYABLE"
    assert [row["evidence_layer"] for row in first["material_package"]["loaded"]] == [
        "LEDGER_OBJECT",
        "LEDGER_OBJECT",
        "FORMATION_BASIS",
        "ORIGINAL_EVIDENCE",
    ]
    assert first["short_receipt"]["scope"] == request["scope"]
    assert first["short_receipt"]["required_missing"] == 0
    assert request == before_request
    assert outcomes == before_outcomes


def test_core_reuses_packer_selection_omissions_and_why_loaded(monkeypatch) -> None:
    needs = [
        _need("NEED-HARD", tokens=30),
        _need("NEED-OPTIONAL", obligation="SHOULD", rank=1, tokens=30),
    ]
    request = _request(needs, budget=30)
    outcomes = [
        _outcome(need, _ledger_response("LR-VALID-07"), f"材料 {need['need_id']}")
        for need in needs
    ]
    calls: list[dict[str, Any]] = []
    real_pack = core.packer.pack_context

    def spy(value):
        calls.append(copy.deepcopy(value))
        return real_pack(value)

    monkeypatch.setattr(core.packer, "pack_context", spy)
    result = core.compile_result(
        request,
        core.prepare_plan(request),
        outcomes,
        _registry(),
    )

    assert len(calls) == 2
    expected = real_pack(calls[0])
    assert [row["need_id"] for row in result["material_package"]["loaded"]] == (
        expected["load_ids"]
    )
    assert {
        row["need_id"]: row["why_loaded"]
        for row in result["material_package"]["loaded"]
    } == expected["why_loaded"]
    assert result["material_package"]["omitted"][0]["reason"] == (
        "BUDGET_OPTIONAL_DEFERRED"
    )
    assert result["material_package"]["omitted"][0]["source_validation"][
        "validation_result"
    ] == "LEDGER_READ_RESPONSE_VALID"


def test_disconnected_layer_and_cross_project_source_are_rejected() -> None:
    disconnected = _need(
        "NEED-FORMATION",
        layer="FORMATION_BASIS",
        parent="NEED-NOT-PRESENT",
        source_contract="TRACEABLE_PROVENANCE_SEAL",
        trigger="AUDIT_REQUIRED",
    )
    request = _request([disconnected])
    with pytest.raises(
        core.C9RetrievalError,
        match="NEED_PARENT_MUST_PRECEDE_CHILD",
    ):
        core.prepare_plan(request)

    need = _need("NEED-CROSS-PROJECT")
    request = _request([need])
    document = _ledger_response("LR-VALID-07")
    document["receipt"]["project_id"] = "PROJECT-OTHER"
    document["receipt"]["basis_sha256"] = ledger_validator.basis_sha256(document)
    result = core.compile_result(
        request,
        core.prepare_plan(request),
        [_outcome(need, document, "禁止串入的材料")],
        _registry(),
    )
    assert result["status"] == "STOPPED"
    assert result["material_package"]["loaded"] == []
    assert "禁止串入的材料" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize(
    ("behavior", "expected_status"),
    [
        ("WARN_AND_CONTINUE", "READY_WITH_GAPS"),
        ("AUTO_CONTINUE", "READY_WITH_GAPS"),
        ("BLOCK", "STOPPED"),
    ],
)
def test_missing_required_material_obeys_gate_without_creating_hypotheses(
    behavior: str,
    expected_status: str,
) -> None:
    needs = [_need("NEED-PRESENT"), _need("NEED-EMPTY")]
    request = _request(needs, behavior=behavior)
    outcomes = [
        _outcome(needs[0], _ledger_response("LR-VALID-07"), "已存在材料"),
        _outcome(needs[1], _ledger_response("LR-VALID-08"), None),
    ]
    result = core.compile_result(
        request,
        core.prepare_plan(request),
        outcomes,
        _registry(),
    )

    assert result["status"] == expected_status
    assert result["short_receipt"]["required_missing"] >= 1
    assert "hypothesis" not in json.dumps(result, ensure_ascii=False).lower()
    if expected_status == "STOPPED":
        assert result["material_package"]["loaded"] == []
    else:
        assert [row["need_id"] for row in result["material_package"]["loaded"]] == [
            "NEED-PRESENT"
        ]


def test_owner_unresolved_material_is_visible_but_never_leaked() -> None:
    needs = [
        _need("NEED-PRESENT"),
        _need(
            "NEED-OWNER-UNRESOLVED",
            layer="FORMATION_BASIS",
            parent="NEED-PRESENT",
            source_contract="TRACEABLE_PROVENANCE_SEAL",
            trigger="LOW_CONFIDENCE",
        ),
    ]
    request = _request(needs)
    outcomes = [
        _outcome(needs[0], _ledger_response("LR-VALID-07"), "可用材料"),
        _outcome(
            needs[1],
            _provenance("TPS-UNRESOLVED-01"),
            "不得进入材料包的未解析内容",
        ),
    ]
    result = core.compile_result(
        request,
        core.prepare_plan(request),
        outcomes,
        _registry(),
    )

    assert result["status"] == "READY_WITH_GAPS"
    outstanding = result["material_package"]["outstanding"]
    assert outstanding[0]["category"] == "UNRESOLVED"
    assert outstanding[0]["reason_code"] == "OWNER_UNRESOLVED"
    assert "不得进入材料包" not in json.dumps(result, ensure_ascii=False)


def test_not_attempted_owner_reader_is_reported_without_being_invoked() -> None:
    needs = [_need("NEED-PRESENT"), _need("NEED-NOT-OPEN")]
    request = _request(needs)
    outcomes = [
        _outcome(needs[0], _ledger_response("LR-VALID-07"), "可用材料"),
        _not_attempted(needs[1]),
    ]
    registry = _registry()
    result = core.compile_result(
        request,
        core.prepare_plan(request),
        outcomes,
        registry,
    )

    assert result["status"] == "READY_WITH_GAPS"
    row = result["material_package"]["outstanding"][0]
    assert row["category"] == "NOT_READ"
    assert row["source_validation"] is None


def test_current_and_pinned_runs_have_distinct_replay_claims() -> None:
    need = _need("NEED-SETTLEMENT", source_contract="CHAPTER_SETTLEMENT_SEAL")
    document = settlement_validator.build_base_document("resolved_full")
    outcome = _outcome(need, document, "章节结算投影")

    current_request = _request([need], basis_mode="current_at_start")
    current = core.compile_result(
        current_request,
        core.prepare_plan(current_request),
        [outcome],
        _registry(),
    )
    pinned_request = _request([need], basis_mode="pinned_manifest")
    pinned = core.compile_result(
        pinned_request,
        core.prepare_plan(pinned_request),
        [outcome],
        _registry(),
    )

    assert current["replay_status"] == "AUDITABLE_CURRENT_NOT_REPLAYABLE"
    assert pinned["replay_status"] == "REPLAYABLE_PINNED"
    assert current["run_sha256"] != pinned["run_sha256"]


def test_corrupt_source_validator_stops_without_exposing_material() -> None:
    need = _need("NEED-CORRUPT")
    request = _request([need])
    secret = "不应进入错误文本的材料"

    def reject_source(_document: Any) -> Any:
        raise ValueError("synthetic corruption")

    result = core.compile_result(
        request,
        core.prepare_plan(request),
        [_outcome(need, _ledger_response("LR-VALID-07"), secret)],
        {"LEDGER_READ_TOOL_CONTRACT": reject_source},
    )
    assert result["status"] == "STOPPED"
    assert result["material_package"]["loaded"] == []
    assert result["material_package"]["outstanding"][0]["reason_code"] == (
        "SOURCE_CORRUPTED"
    )
    assert result["material_package"]["outstanding"][0]["source_validation"][
        "validation_result"
    ] == "SOURCE_VALIDATION_FAILED"
    assert secret not in json.dumps(result, ensure_ascii=False)


def test_validator_registry_rejects_unknown_or_non_callable_entries() -> None:
    need = _need("NEED-REGISTRY")
    request = _request([need])
    plan = core.prepare_plan(request)
    outcome = _outcome(need, _ledger_response("LR-VALID-07"), "可用材料")

    with pytest.raises(
        core.C9RetrievalError,
        match="SOURCE_VALIDATOR_REGISTRY_CONTRACT_FORBIDDEN",
    ):
        core.compile_result(
            request,
            plan,
            [outcome],
            {
                "LEDGER_READ_TOOL_CONTRACT": ledger_validator.validate_document,
                "UNAUTHORIZED_BLOB": lambda value: value,
            },
        )
    with pytest.raises(
        core.C9RetrievalError,
        match="SOURCE_VALIDATOR_NOT_CALLABLE",
    ):
        core.compile_result(
            request,
            plan,
            [outcome],
            {"LEDGER_READ_TOOL_CONTRACT": "not-callable"},
        )


@pytest.mark.parametrize("behavior", ["AUTO_CONTINUE", "WARN_AND_CONTINUE"])
def test_all_missing_sources_still_honor_continue_on_gap(behavior: str) -> None:
    needs = [_need("NEED-EMPTY"), _need("NEED-NOT-OPEN")]
    request = _request(needs, behavior=behavior)
    outcomes = [
        _outcome(needs[0], _ledger_response("LR-VALID-08"), None),
        _not_attempted(needs[1]),
    ]

    result = core.compile_result(
        request,
        core.prepare_plan(request),
        outcomes,
        _registry(),
    )

    assert result["status"] == "READY_WITH_GAPS"
    assert result["material_package"]["loaded"] == []
    assert result["short_receipt"]["required_missing"] == 2
    assert [row["source_status"] for row in result["material_package"]["outstanding"]] == [
        "EMPTY",
        "NOT_ATTEMPTED",
    ]


def test_optional_only_empty_run_is_not_misreported_as_ready() -> None:
    needs = [
        _need("NEED-SHOULD", obligation="SHOULD", rank=1),
        _need("NEED-MAY", obligation="MAY", rank=2),
    ]
    request = _request(needs)
    outcomes = [
        _outcome(needs[0], _ledger_response("LR-VALID-08"), None),
        _not_attempted(needs[1]),
    ]

    result = core.compile_result(
        request,
        core.prepare_plan(request),
        outcomes,
        _registry(),
    )

    assert result["status"] == "READY_WITH_GAPS"
    assert result["short_receipt"]["required_total"] == 0
    assert result["short_receipt"]["required_missing"] == 0
    assert result["material_package"]["loaded"] == []
    assert result["material_package"]["outstanding"]


def test_optional_materials_all_omitted_by_budget_return_gap_receipt() -> None:
    needs = [
        _need("NEED-SHOULD", obligation="SHOULD", rank=1, tokens=20),
        _need("NEED-MAY", obligation="MAY", rank=2, tokens=20),
    ]
    request = _request(needs, budget=1)
    outcomes = [
        _outcome(need, _ledger_response("LR-VALID-07"), f"材料 {need['need_id']}")
        for need in needs
    ]

    result = core.compile_result(
        request,
        core.prepare_plan(request),
        outcomes,
        _registry(),
    )

    assert result["status"] == "READY_WITH_GAPS"
    assert result["material_package"]["loaded"] == []
    assert [row["need_id"] for row in result["material_package"]["omitted"]] == [
        "NEED-SHOULD",
        "NEED-MAY",
    ]
    assert result["short_receipt"]["omitted_count"] == 2


def test_runtime_need_id_validation_matches_published_schema() -> None:
    request = _request([_need("NEED-valid")])
    request["source_needs"][0]["need_id"] = "NEED-a/b"
    request = core.seal_request(request)

    with pytest.raises(core.C9RetrievalError, match="NEED_ID_INVALID"):
        core.prepare_plan(request)


def test_trace_source_fields_cannot_be_resealed_into_a_false_audit_trail() -> None:
    needs = [_need("NEED-PRESENT"), _need("NEED-EMPTY")]
    request = _request(needs)
    outcomes = [
        _outcome(needs[0], _ledger_response("LR-VALID-07"), "可用材料"),
        _outcome(needs[1], _ledger_response("LR-VALID-08"), None),
    ]
    plan = core.prepare_plan(request)
    result = core.compile_result(request, plan, outcomes, _registry())
    changed = copy.deepcopy(result)
    changed["trace_log"]["events"][1]["source_status"] = "REJECTED"
    changed["trace_log"].pop("trace_log_sha256")
    changed["trace_log"]["trace_log_sha256"] = core.sha256_json(changed["trace_log"])
    changed["short_receipt"]["trace_log_sha256"] = changed["trace_log"][
        "trace_log_sha256"
    ]
    changed["short_receipt"].pop("receipt_sha256")
    changed["short_receipt"]["receipt_sha256"] = core.sha256_json(
        changed["short_receipt"]
    )
    changed.pop("run_sha256")
    changed["run_sha256"] = core.sha256_json(changed)

    with pytest.raises(core.C9RetrievalError, match="TRACE_EVENT_MISMATCH"):
        core.validate_result(changed, request, plan)

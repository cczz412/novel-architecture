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
    trigger_provenance = None
    if parent is not None:
        decision = {
            "need_id": need_id,
            "parent_need_id": parent,
            "decision_code": trigger,
        }
        trigger_provenance = {
            "decision_contract": "SYNTHETIC_TASK_PLAN_DECISION",
            "decision_contract_version": "v1",
            "decision_object_ref": f"decision://{need_id}",
            "decision_object_sha256": core.sha256_json(decision),
            "producer_component_id": "TEST_TASK_PLANNER",
            "decision_code": trigger,
            "parent_need_id": parent,
        }
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
        "trigger_provenance": trigger_provenance,
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
        row for row in ledger_validator.load_fixtures() if row["case_id"] == case_id
    )
    return copy.deepcopy(case["document"])


def _provenance(case_id: str = "TPS-VALID-01") -> dict[str, Any]:
    case = next(
        row for row in provenance_validator.load_fixtures() if row["case_id"] == case_id
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

    validators = {
        "LEDGER_READ_TOOL_CONTRACT": ledger_validator.validate_document,
        "TRACEABLE_PROVENANCE_SEAL": provenance_validator.validate_seal,
        "CHAPTER_SETTLEMENT_SEAL": settlement_validator.validate_settlement,
        "CHAPTER_LAYERED_SUMMARY": validate_summary,
    }

    def bind_projection(
        document: dict[str, Any],
        need: dict[str, Any],
        material_text: str | None,
        basis_mode: str,
    ) -> dict[str, Any]:
        if need["source_contract"] == "LEDGER_READ_TOOL_CONTRACT":
            receipt = document.get("receipt", {})
            truth_scope = {
                "author_id": receipt.get("author_id"),
                "project_id": receipt.get("project_id"),
            }
            read_request_id = document.get("request_id")
            basis_sha256 = receipt.get("basis_sha256")
            manifest = receipt.get("source_manifest")
        else:
            scope = document.get("truth_scope_ref", {})
            truth_scope = {
                "author_id": scope.get("principal_author_id"),
                "project_id": scope.get("project_id"),
            }
            read_request_id = f"SYNTHETIC-READ-{need['need_id']}"
            basis_sha256 = core.sha256_json(
                {"document": core.sha256_json(document), "need": need["need_id"]}
            )
            manifest = [{"source_object_sha256": core.sha256_json(document)}]
        if basis_mode == "pinned_manifest":
            pin_proof_status = (
                "PINNED_INVALID"
                if document.get("reason_code") == "INVALID_PIN_SET"
                else "PINNED_VALID"
            )
            source_manifest_sha256 = core.sha256_json(manifest)
        else:
            pin_proof_status = "CURRENT_AT_START"
            source_manifest_sha256 = (
                core.sha256_json(manifest) if manifest is not None else None
            )
        selector = {
            "selector_kind": "SYNTHETIC_TEST_PROJECTION",
            "selector_ref": f"projection://{need['need_id']}",
        }
        selector["selector_sha256"] = core.sha256_json(selector)
        return {
            "canonical_object_ref": need["object_ref"],
            "truth_scope_ref": truth_scope,
            "source_object_sha256": core.sha256_json(document),
            "source_revision_ref": (
                document.get("settlement_sha256")
                or document.get("summary_sha256")
                or document.get("seal_sha256")
                or document.get("request_id")
            ),
            "basis_mode": basis_mode,
            "read_request_id": read_request_id,
            "basis_sha256": basis_sha256,
            "source_manifest_sha256": source_manifest_sha256,
            "projection_selector": selector,
            "projected_material_sha256": (
                core._sha256_text(material_text) if material_text is not None else None
            ),
            "pin_proof_status": pin_proof_status,
        }

    return {
        source_contract: {
            "source_contract": source_contract,
            "source_contract_version": core.SOURCE_CONTRACT_VERSIONS[source_contract],
            "validator_id": f"test-validator:{source_contract}:v1",
            "validate_document": validator,
            "bind_projection": bind_projection,
        }
        for source_contract, validator in validators.items()
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
    }


def _not_attempted(need: dict[str, Any]) -> dict[str, Any]:
    return {
        "need_id": need["need_id"],
        "source_status": "NOT_ATTEMPTED",
        "reason_code": "OWNER_RUNTIME_NOT_AVAILABLE",
        "source_document": None,
        "material_text": None,
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
    assert (
        result["material_package"]["omitted"][0]["source_validation"][
            "validation_result"
        ]
        == "LEDGER_READ_RESPONSE_VALID"
    )


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

    registry = _registry()
    registry["LEDGER_READ_TOOL_CONTRACT"]["validate_document"] = reject_source
    result = core.compile_result(
        request,
        core.prepare_plan(request),
        [_outcome(need, _ledger_response("LR-VALID-07"), secret)],
        registry,
    )
    assert result["status"] == "STOPPED"
    assert result["material_package"]["loaded"] == []
    assert result["material_package"]["outstanding"][0]["reason_code"] == (
        "SOURCE_CORRUPTED"
    )
    assert (
        result["material_package"]["outstanding"][0]["source_validation"][
            "validation_result"
        ]
        == "SOURCE_VALIDATION_FAILED"
    )
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
    bad_registry = _registry()
    bad_registry["LEDGER_READ_TOOL_CONTRACT"]["bind_projection"] = "not-callable"
    with pytest.raises(core.C9RetrievalError, match="SOURCE_REGISTRY_CALLABLE_INVALID"):
        core.compile_result(
            request,
            plan,
            [outcome],
            bad_registry,
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
    assert [
        row["source_status"] for row in result["material_package"]["outstanding"]
    ] == [
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

    with pytest.raises(
        core.C9RetrievalError,
        match="RESULT_NOT_EXACT_SOURCE_RECOMPILE",
    ):
        core.validate_result(changed, request, plan, outcomes, _registry())


@pytest.mark.parametrize(
    "mismatch",
    ["object_ref", "material_text", "selector", "ledger_basis"],
)
def test_source_binding_rejects_unrelated_objects_and_arbitrary_material(
    mismatch: str,
) -> None:
    need = _need("NEED-BOUND")
    request = _request([need])
    outcome = _outcome(need, _ledger_response("LR-VALID-07"), "调用方材料")
    registry = _registry()
    entry = registry["LEDGER_READ_TOOL_CONTRACT"]
    real_binder = entry["bind_projection"]

    def mismatched_binder(document, bound_need, material_text, basis_mode):
        binding = real_binder(
            document,
            bound_need,
            material_text if mismatch == "object_ref" else "来源实际投影",
            basis_mode,
        )
        if mismatch == "object_ref":
            binding["canonical_object_ref"] = "ledger://another-object"
        elif mismatch == "selector":
            binding["projection_selector"]["selector_ref"] = "projection://wrong"
        elif mismatch == "ledger_basis":
            binding["basis_sha256"] = "f" * 64
        return binding

    entry["bind_projection"] = mismatched_binder
    result = core.compile_result(
        request,
        core.prepare_plan(request),
        [outcome],
        registry,
    )

    assert result["status"] == "STOPPED"
    assert result["material_package"]["loaded"] == []
    failure = result["material_package"]["outstanding"][0]["source_validation"]
    assert failure["failure_code"] in {
        "SOURCE_BINDING_OBJECT_REF_MISMATCH",
        "SOURCE_BINDING_MATERIAL_SHA256_MISMATCH",
        "PROJECTION_SELECTOR_SHA256_MISMATCH",
        "LEDGER_SOURCE_BINDING_BASIS_MISMATCH",
    }
    assert "调用方材料" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("parent_state", ["EMPTY", "NOT_ATTEMPTED", "OWNER_UNRESOLVED"])
def test_unusable_ancestor_never_allows_an_orphan_descendant(
    parent_state: str,
) -> None:
    ledger = _need("NEED-LEDGER")
    formation = _need(
        "NEED-FORMATION",
        layer="FORMATION_BASIS",
        parent="NEED-LEDGER",
        source_contract="TRACEABLE_PROVENANCE_SEAL",
        obligation="SHOULD",
        rank=1,
        trigger="CONFLICT_DETECTED",
    )
    needs = [ledger, formation]
    outcomes = [
        _outcome(ledger, _ledger_response("LR-VALID-07"), "账目材料"),
        _outcome(formation, _provenance(), "形成依据"),
    ]
    if parent_state == "EMPTY":
        outcomes[0] = _outcome(ledger, _ledger_response("LR-VALID-08"), None)
    elif parent_state == "NOT_ATTEMPTED":
        outcomes[0] = _not_attempted(ledger)
    else:
        original = _need(
            "NEED-ORIGINAL",
            layer="ORIGINAL_EVIDENCE",
            parent="NEED-FORMATION",
            obligation="MAY",
            rank=2,
            trigger="AUDIT_REQUIRED",
        )
        needs.append(original)
        outcomes[1] = _outcome(
            formation,
            _provenance("TPS-UNRESOLVED-01"),
            "不得装入的未解析形成依据",
        )
        outcomes.append(_outcome(original, _ledger_response("LR-VALID-07"), "原文证据"))

    request = _request(needs)
    result = core.compile_result(
        request,
        core.prepare_plan(request),
        outcomes,
        _registry(),
    )

    loaded_ids = {row["need_id"] for row in result["material_package"]["loaded"]}
    if parent_state != "OWNER_UNRESOLVED":
        assert "NEED-FORMATION" not in loaded_ids
    if parent_state == "OWNER_UNRESOLVED":
        assert "NEED-ORIGINAL" not in loaded_ids
        blocked_id = "NEED-ORIGINAL"
    else:
        blocked_id = "NEED-FORMATION"
    blocked = next(
        row
        for row in result["material_package"]["outstanding"]
        if row["need_id"] == blocked_id
    )
    assert blocked["category"] == "DEPENDENCY_BLOCKED"
    assert blocked["reason_code"] == "ANCESTOR_SOURCE_UNAVAILABLE"


def test_child_selected_by_packer_is_removed_when_parent_is_budget_omitted() -> None:
    parent = _need(
        "NEED-PARENT",
        obligation="SHOULD",
        rank=2,
        tokens=20,
    )
    child = _need(
        "NEED-CHILD",
        layer="FORMATION_BASIS",
        parent="NEED-PARENT",
        source_contract="TRACEABLE_PROVENANCE_SEAL",
        obligation="SHOULD",
        rank=1,
        tokens=10,
        trigger="AUDIT_REQUIRED",
    )
    request = _request([parent, child], budget=10)
    outcomes = [
        _outcome(parent, _ledger_response("LR-VALID-07"), "父层材料"),
        _outcome(child, _provenance(), "子层材料"),
    ]

    result = core.compile_result(
        request,
        core.prepare_plan(request),
        outcomes,
        _registry(),
    )

    assert result["status"] == "READY_WITH_GAPS"
    assert result["material_package"]["loaded"] == []
    omitted = {
        row["need_id"]: row["reason"] for row in result["material_package"]["omitted"]
    }
    assert omitted["NEED-PARENT"] == "BUDGET_OPTIONAL_DEFERRED"
    assert omitted["NEED-CHILD"] == "ANCESTOR_NOT_LOADED"


@pytest.mark.parametrize(
    "pin_problem", ["missing_proof", "mixed_current", "invalid_pin"]
)
def test_pinned_request_needs_complete_valid_source_proof(pin_problem: str) -> None:
    source_contract = (
        "LEDGER_READ_TOOL_CONTRACT"
        if pin_problem == "invalid_pin"
        else "CHAPTER_SETTLEMENT_SEAL"
    )
    need = _need("NEED-PIN", source_contract=source_contract)
    request = _request([need], basis_mode="pinned_manifest")
    document = (
        _ledger_response("LR-INVALID-14")
        if pin_problem == "invalid_pin"
        else settlement_validator.build_base_document("resolved_full")
    )
    outcome = _outcome(need, document, None if pin_problem == "invalid_pin" else "材料")
    registry = _registry()
    if pin_problem != "invalid_pin":
        entry = registry[source_contract]
        real_binder = entry["bind_projection"]

        def incomplete_binder(document, bound_need, material_text, basis_mode):
            binding = real_binder(document, bound_need, material_text, basis_mode)
            if pin_problem == "missing_proof":
                binding["source_manifest_sha256"] = None
            else:
                binding["pin_proof_status"] = "CURRENT_AT_START"
            return binding

        entry["bind_projection"] = incomplete_binder

    result = core.compile_result(
        request,
        core.prepare_plan(request),
        [outcome],
        registry,
    )

    assert result["status"] == "STOPPED"
    assert result["replay_status"] == "PINNED_REQUEST_NOT_REPLAYABLE"


def _reseal_changed_result(result: dict[str, Any]) -> None:
    package = result["material_package"]
    package.pop("package_sha256", None)
    package["package_sha256"] = core.sha256_json(package)
    trace = result["trace_log"]
    trace.pop("trace_log_sha256", None)
    trace["trace_log_sha256"] = core.sha256_json(trace)
    receipt = result["short_receipt"]
    receipt["package_sha256"] = package["package_sha256"]
    receipt["trace_log_sha256"] = trace["trace_log_sha256"]
    receipt.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = core.sha256_json(receipt)
    result.pop("run_sha256", None)
    result["run_sha256"] = core.sha256_json(result)


@pytest.mark.parametrize(
    "mutation",
    ["block_status", "material", "validator_identity", "source_status"],
)
def test_strong_validation_rejects_coordinated_resealed_results(mutation: str) -> None:
    need = _need("NEED-STRONG")
    request = _request(
        [need],
        behavior="BLOCK" if mutation == "block_status" else "WARN_AND_CONTINUE",
    )
    outcomes = [
        _outcome(
            need,
            _ledger_response(
                "LR-VALID-08"
                if mutation in {"block_status", "source_status"}
                else "LR-VALID-07"
            ),
            None if mutation in {"block_status", "source_status"} else "原始材料",
        )
    ]
    plan = core.prepare_plan(request)
    registry = _registry()
    result = core.compile_result(request, plan, outcomes, registry)
    changed = copy.deepcopy(result)

    if mutation == "block_status":
        changed["status"] = "READY_WITH_GAPS"
        changed["short_receipt"]["status"] = "READY_WITH_GAPS"
    elif mutation == "material":
        loaded = changed["material_package"]["loaded"][0]
        loaded["material_text"] = "协调替换后的材料"
        loaded["material_sha256"] = core._sha256_text(loaded["material_text"])
        binding = loaded["source_validation"]["source_binding"]
        binding["projected_material_sha256"] = loaded["material_sha256"]
        binding.pop("binding_receipt_sha256")
        binding["binding_receipt_sha256"] = core.sha256_json(binding)
        changed["trace_log"]["events"][0]["binding_receipt_sha256"] = binding[
            "binding_receipt_sha256"
        ]
    elif mutation == "validator_identity":
        validation = changed["material_package"]["loaded"][0]["source_validation"]
        validation["validator_id"] = "fake-official-validator-v999"
        binding = validation["source_binding"]
        binding["validator_id"] = validation["validator_id"]
        binding.pop("binding_receipt_sha256")
        binding["binding_receipt_sha256"] = core.sha256_json(binding)
        changed["trace_log"]["events"][0]["binding_receipt_sha256"] = binding[
            "binding_receipt_sha256"
        ]
    else:
        outstanding = changed["material_package"]["outstanding"][0]
        outstanding["source_status"] = "REJECTED"
        outstanding["reason_code"] = "SYNTHETIC_OTHER_REASON"
        changed["trace_log"]["events"][0]["source_status"] = "REJECTED"
        changed["trace_log"]["events"][0]["reason_code"] = "SYNTHETIC_OTHER_REASON"
        changed["short_receipt"]["warnings"] = [
            "MISSING_REQUIRED:NEED-STRONG:SYNTHETIC_OTHER_REASON"
        ]
    _reseal_changed_result(changed)

    with pytest.raises(
        core.C9RetrievalError,
        match="RESULT_NOT_EXACT_SOURCE_RECOMPILE",
    ):
        core.validate_result(changed, request, plan, outcomes, registry)


def test_source_outcome_cannot_self_report_validator_identity() -> None:
    need = _need("NEED-NO-SELF-REPORT")
    request = _request([need])
    outcome = _outcome(need, _ledger_response("LR-VALID-07"), "材料")
    outcome["validator_id"] = "fake-official-validator"

    with pytest.raises(core.C9RetrievalError, match="SOURCE_OUTCOME_FIELDS_INVALID"):
        core.compile_result(
            request,
            core.prepare_plan(request),
            [outcome],
            _registry(),
        )


@pytest.mark.parametrize(
    "registry_problem", ["missing_field", "wrong_contract", "wrong_version"]
)
def test_trusted_registry_entry_identity_is_closed(registry_problem: str) -> None:
    need = _need("NEED-REGISTRY-IDENTITY")
    request = _request([need])
    registry = _registry()
    entry = registry["LEDGER_READ_TOOL_CONTRACT"]
    if registry_problem == "missing_field":
        entry.pop("validator_id")
        expected = "SOURCE_REGISTRY_ENTRY_FIELDS_INVALID"
    elif registry_problem == "wrong_contract":
        entry["source_contract"] = "CHAPTER_SETTLEMENT_SEAL"
        expected = "SOURCE_REGISTRY_CONTRACT_MISMATCH"
    else:
        entry["source_contract_version"] = "ledger-read-tool-contract-v999"
        expected = "SOURCE_REGISTRY_VERSION_MISMATCH"

    with pytest.raises(core.C9RetrievalError, match=expected):
        core.compile_result(
            request,
            core.prepare_plan(request),
            [_outcome(need, _ledger_response("LR-VALID-07"), "材料")],
            registry,
        )


@pytest.mark.parametrize(
    "trigger_problem",
    ["missing", "wrong_parent", "wrong_code", "bad_sha", "stronger_child"],
)
def test_deep_need_requires_bound_trigger_provenance(trigger_problem: str) -> None:
    parent = _need("NEED-TRIGGER-PARENT")
    child = _need(
        "NEED-TRIGGER-CHILD",
        layer="FORMATION_BASIS",
        parent=parent["need_id"],
        source_contract="TRACEABLE_PROVENANCE_SEAL",
        obligation="SHOULD",
        rank=1,
        trigger="AUDIT_REQUIRED",
    )
    if trigger_problem == "missing":
        child["trigger_provenance"] = None
        expected = "DEEP_NEED_TRIGGER_PROVENANCE_REQUIRED"
    elif trigger_problem == "wrong_parent":
        child["trigger_provenance"]["parent_need_id"] = "NEED-OTHER"
        expected = "TRIGGER_PROVENANCE_PARENT_MISMATCH"
    elif trigger_problem == "wrong_code":
        child["trigger_provenance"]["decision_code"] = "LOW_CONFIDENCE"
        expected = "TRIGGER_PROVENANCE_DECISION_CODE_MISMATCH"
    elif trigger_problem == "bad_sha":
        child["trigger_provenance"]["decision_object_sha256"] = "not-a-sha"
        expected = "TRIGGER_PROVENANCE_DECISION_SHA256_INVALID"
    else:
        parent["obligation_tier"] = "MAY"
        parent["selection_rank"] = 2
        child["obligation_tier"] = "SHOULD"
        expected = "CHILD_OBLIGATION_STRONGER_THAN_PARENT"
    request = _request([parent, child])

    with pytest.raises(core.C9RetrievalError, match=expected):
        core.prepare_plan(request)


def test_trace_projects_exact_trigger_provenance() -> None:
    parent = _need("NEED-TRACE-PARENT")
    child = _need(
        "NEED-TRACE-CHILD",
        layer="FORMATION_BASIS",
        parent=parent["need_id"],
        source_contract="TRACEABLE_PROVENANCE_SEAL",
        obligation="SHOULD",
        rank=1,
        trigger="HIGH_IMPACT_DECISION",
    )
    request = _request([parent, child])
    result = core.compile_result(
        request,
        core.prepare_plan(request),
        [
            _outcome(parent, _ledger_response("LR-VALID-07"), "账目"),
            _outcome(child, _provenance(), "形成依据"),
        ],
        _registry(),
    )

    assert (
        result["trace_log"]["events"][1]["trigger_provenance"]
        == child["trigger_provenance"]
    )

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
PACKER_SCRIPT = PRODUCT_ROOT / "mvp" / "packer.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import packer
finally:
    sys.path.pop(0)


def _material(
    *,
    material_id: str,
    tokens: int,
    actuality: str,
    obligation: str,
    rank: int | None,
    relation: str,
    recall: str,
    handle: str | None,
    unresolved_reason: str | None,
) -> dict:
    return {
        "id": material_id,
        "estimated_tokens": tokens,
        "actuality_class": actuality,
        "obligation_tier": obligation,
        "selection_rank": rank,
        "task_relation": relation,
        "recall_disposition": recall,
        "recall_handle": handle,
        "unresolved_reason": unresolved_reason,
    }


def _request(*materials: dict, budget: int, scope: str = "CURRENT_TRUTH_REQUIRED") -> dict:
    return {
        "task_id": "TASK-001",
        "task_actuality_scope": scope,
        "budget_tokens": budget,
        "token_estimator_ref": "fixture-estimator-v1",
        "candidate_materials": list(materials),
    }


def test_legal_pack_keeps_hard_first_and_explains_every_loaded_id() -> None:
    hard_fact = _material(
        material_id="FACT-01",
        tokens=40,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="HARD",
        rank=None,
        relation="当前场景必须承接这个已发生事实",
        recall="RETRIEVABLE",
        handle="fact://FACT-01",
        unresolved_reason=None,
    )
    hard_pin = _material(
        material_id="PIN-01",
        tokens=30,
        actuality="ACTIVE_CONSTRAINT",
        obligation="HARD",
        rank=None,
        relation="作者 pin 在当前任务仍生效",
        recall="NOT_RETRIEVABLE",
        handle=None,
        unresolved_reason=None,
    )
    should = _material(
        material_id="SUPPORT-01",
        tokens=20,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="SHOULD",
        rank=1,
        relation="能帮助区分相近状态",
        recall="RETRIEVABLE",
        handle="fact://SUPPORT-01",
        unresolved_reason=None,
    )
    request = _request(hard_fact, should, hard_pin, budget=90)
    before = copy.deepcopy(request)

    result = packer.pack_context(request)

    assert result["decision_state"] == "READY"
    assert result["load_ids"] == ["FACT-01", "PIN-01", "SUPPORT-01"]
    assert result["loaded_token_estimate"] == result["budget_tokens"] == 90
    assert set(result["why_loaded"]) == set(result["load_ids"])
    assert "HARD 保底义务" in result["why_loaded"]["PIN-01"]
    assert "rank=1" in result["why_loaded"]["SUPPORT-01"]
    assert result["omitted"] == []
    assert result["unresolved"] == []
    assert result["errors"] == []
    assert request == before
    json.dumps(result, ensure_ascii=False)


def test_budget_is_hard_cap_and_optional_material_becomes_visible_omission() -> None:
    hard = _material(
        material_id="HARD-01",
        tokens=70,
        actuality="ACTIVE_CONSTRAINT",
        obligation="HARD",
        rank=None,
        relation="不可丢的本章禁做条",
        recall="NOT_RETRIEVABLE",
        handle=None,
        unresolved_reason=None,
    )
    optional = _material(
        material_id="MAY-01",
        tokens=20,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="MAY",
        rank=1,
        relation="支持性证据坐标",
        recall="RETRIEVABLE",
        handle="evidence://MAY-01",
        unresolved_reason=None,
    )

    result = packer.pack_context(_request(hard, optional, budget=80))

    assert result["decision_state"] == "READY"
    assert result["load_ids"] == ["HARD-01"]
    assert result["loaded_token_estimate"] == 70
    assert result["loaded_token_estimate"] <= result["budget_tokens"]
    assert result["omitted"] == [
        {
            "id": "MAY-01",
            "reason": "BUDGET_OPTIONAL_DEFERRED",
            "recall_disposition": "RETRIEVABLE",
            "recall_handle": "evidence://MAY-01",
        }
    ]


def test_hard_set_over_budget_stops_without_returning_a_partial_package() -> None:
    hard_a = _material(
        material_id="HARD-A",
        tokens=60,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="HARD",
        rank=None,
        relation="当前入口状态",
        recall="NOT_RETRIEVABLE",
        handle=None,
        unresolved_reason=None,
    )
    hard_b = _material(
        material_id="HARD-B",
        tokens=50,
        actuality="ACTIVE_CONSTRAINT",
        obligation="HARD",
        rank=None,
        relation="作者不可违反约束",
        recall="NOT_RETRIEVABLE",
        handle=None,
        unresolved_reason=None,
    )

    result = packer.pack_context(_request(hard_a, hard_b, budget=100))

    assert result["decision_state"] == "STOP_HARD_BUDGET"
    assert result["load_ids"] == []
    assert result["loaded_token_estimate"] == 0
    assert result["errors"][0]["code"] == "M11_HARD_OBLIGATIONS_EXCEED_BUDGET"
    assert "110 token" in result["errors"][0]["detail"]


def test_future_material_outside_current_scope_is_never_silently_lost() -> None:
    current = _material(
        material_id="CURRENT-01",
        tokens=30,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="HARD",
        rank=None,
        relation="当前状态",
        recall="NOT_RETRIEVABLE",
        handle=None,
        unresolved_reason=None,
    )
    future = _material(
        material_id="FUTURE-01",
        tokens=10,
        actuality="FUTURE_PLAN_OR_PROJECTION",
        obligation="MAY",
        rank=1,
        relation="未来计划，不是当前事实",
        recall="RETRIEVABLE",
        handle="plan://FUTURE-01",
        unresolved_reason=None,
    )

    result = packer.pack_context(_request(current, future, budget=100))

    assert result["decision_state"] == "READY"
    assert result["load_ids"] == ["CURRENT-01"]
    assert result["omitted"] == [
        {
            "id": "FUTURE-01",
            "reason": "OUTSIDE_TASK_ACTUALITY_SCOPE",
            "recall_disposition": "RETRIEVABLE",
            "recall_handle": "plan://FUTURE-01",
        }
    ]


def test_explicit_unresolved_material_stops_and_is_listed_for_caller() -> None:
    unresolved = _material(
        material_id="STATE-OPEN-01",
        tokens=25,
        actuality="UNRESOLVED",
        obligation="HARD",
        rank=None,
        relation="任务依赖邀请是否接受",
        recall="RETRIEVABLE",
        handle="fact://STATE-OPEN-01",
        unresolved_reason="来源明确登记为尚待作者确认",
    )

    result = packer.pack_context(_request(unresolved, budget=100))

    assert result["decision_state"] == "STOP_UNRESOLVED"
    assert result["load_ids"] == []
    assert result["unresolved"] == [
        {
            "id": "STATE-OPEN-01",
            "reason": "来源明确登记为尚待作者确认",
            "obligation_tier": "HARD",
        }
    ]
    assert result["errors"][0]["code"] == "M11_UNRESOLVED_REQUIRES_CALLER_DECISION"


def test_missing_explicit_recall_input_is_rejected_instead_of_defaulted() -> None:
    material = _material(
        material_id="FACT-01",
        tokens=10,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="SHOULD",
        rank=1,
        relation="近章支持事实",
        recall="RETRIEVABLE",
        handle="fact://FACT-01",
        unresolved_reason=None,
    )
    material.pop("recall_disposition")

    result = packer.pack_context(_request(material, budget=100))

    assert result["decision_state"] == "STOP_INPUT_INVALID"
    assert result["errors"] == [
        {
            "code": "M11_MATERIAL_FIELD_MISSING",
            "detail": "candidate_materials[0] 缺字段：recall_disposition",
        }
    ]


@pytest.mark.parametrize(
    "missing_field",
    ["task_id", "task_actuality_scope", "budget_tokens", "token_estimator_ref"],
)
def test_missing_task_or_budget_input_is_rejected(missing_field: str) -> None:
    material = _material(
        material_id="FACT-01",
        tokens=10,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="HARD",
        rank=None,
        relation="当前任务入口",
        recall="NOT_RETRIEVABLE",
        handle=None,
        unresolved_reason=None,
    )
    request = _request(material, budget=100)
    request.pop(missing_field)

    result = packer.pack_context(request)

    assert result["decision_state"] == "STOP_INPUT_INVALID"
    assert result["errors"][0]["code"] == "M11_REQUEST_FIELD_MISSING"
    assert missing_field in result["errors"][0]["detail"]


@pytest.mark.parametrize(
    "missing_field",
    ["actuality_class", "obligation_tier", "recall_disposition", "unresolved_reason"],
)
def test_missing_material_semantics_are_rejected(missing_field: str) -> None:
    material = _material(
        material_id="FACT-01",
        tokens=10,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="HARD",
        rank=None,
        relation="当前任务入口",
        recall="NOT_RETRIEVABLE",
        handle=None,
        unresolved_reason=None,
    )
    material.pop(missing_field)

    result = packer.pack_context(_request(material, budget=100))

    assert result["decision_state"] == "STOP_INPUT_INVALID"
    assert result["errors"][0]["code"] == "M11_MATERIAL_FIELD_MISSING"
    assert missing_field in result["errors"][0]["detail"]


def test_non_string_actuality_is_rejected_without_python_exception() -> None:
    material = _material(
        material_id="FACT-01",
        tokens=10,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="HARD",
        rank=None,
        relation="当前任务入口",
        recall="NOT_RETRIEVABLE",
        handle=None,
        unresolved_reason=None,
    )
    material["actuality_class"] = ["CURRENT_FACT_OR_STATE"]

    result = packer.pack_context(_request(material, budget=100))

    assert result["decision_state"] == "STOP_INPUT_INVALID"
    assert result["errors"][0]["code"] == "M11_ACTUALITY_INVALID"


def test_direct_script_demo_shows_author_visible_load_and_omission() -> None:
    completed = subprocess.run(
        [sys.executable, str(PACKER_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["decision_state"] == "READY"
    assert result["load_ids"] == ["DEMO-AUTHOR-PIN"]
    assert result["omitted"] == [
        {
            "id": "DEMO-SUPPORT-EVIDENCE",
            "reason": "BUDGET_OPTIONAL_DEFERRED",
            "recall_disposition": "RETRIEVABLE",
            "recall_handle": "demo://evidence/identity",
        }
    ]
    assert "作者要求本场不能揭开角色真实身份" in result["why_loaded"]["DEMO-AUTHOR-PIN"]

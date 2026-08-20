"""M11 最小可运行上下文打包器。

这是可用原型，不是正式 C9 合同。调用者必须显式提供任务范围、预算、
素材的 actuality／obligation／recall 信息；本模块只做确定性筛选、预算记账
和失败关闭，不替上游推断这些语义。
"""

from __future__ import annotations

import json
from typing import Any, Literal, TypedDict


TaskActualityScope = Literal[
    "CURRENT_TRUTH_REQUIRED",
    "FUTURE_MATERIAL_EXPLICITLY_IN_SCOPE",
]
ActualityClass = Literal[
    "CURRENT_FACT_OR_STATE",
    "ACTIVE_CONSTRAINT",
    "FUTURE_PLAN_OR_PROJECTION",
    "UNRESOLVED",
]
ObligationTier = Literal["HARD", "SHOULD", "MAY"]
RecallDisposition = Literal["RETRIEVABLE", "NOT_RETRIEVABLE"]

TASK_SCOPES = {
    "CURRENT_TRUTH_REQUIRED",
    "FUTURE_MATERIAL_EXPLICITLY_IN_SCOPE",
}
ACTUALITY_CLASSES = {
    "CURRENT_FACT_OR_STATE",
    "ACTIVE_CONSTRAINT",
    "FUTURE_PLAN_OR_PROJECTION",
    "UNRESOLVED",
}
OBLIGATION_TIERS = {"HARD", "SHOULD", "MAY"}
RECALL_DISPOSITIONS = {"RETRIEVABLE", "NOT_RETRIEVABLE"}


class CandidateMaterial(TypedDict):
    id: str
    estimated_tokens: int
    actuality_class: ActualityClass
    obligation_tier: ObligationTier
    selection_rank: int | None
    task_relation: str
    recall_disposition: RecallDisposition
    recall_handle: str | None
    unresolved_reason: str | None


class PackRequest(TypedDict):
    task_id: str
    task_actuality_scope: TaskActualityScope
    budget_tokens: int
    token_estimator_ref: str
    candidate_materials: list[CandidateMaterial]


class Omission(TypedDict):
    id: str
    reason: str
    recall_disposition: RecallDisposition
    recall_handle: str | None


class UnresolvedMaterial(TypedDict):
    id: str
    reason: str
    obligation_tier: ObligationTier


class PackerError(TypedDict):
    code: str
    detail: str


class C9Prototype(TypedDict):
    decision_state: str
    load_ids: list[str]
    omitted: list[Omission]
    unresolved: list[UnresolvedMaterial]
    loaded_token_estimate: int
    budget_tokens: int | None
    why_loaded: dict[str, str]
    errors: list[PackerError]


REQUIRED_REQUEST_FIELDS = {
    "task_id",
    "task_actuality_scope",
    "budget_tokens",
    "token_estimator_ref",
    "candidate_materials",
}
REQUIRED_MATERIAL_FIELDS = {
    "id",
    "estimated_tokens",
    "actuality_class",
    "obligation_tier",
    "selection_rank",
    "task_relation",
    "recall_disposition",
    "recall_handle",
    "unresolved_reason",
}


def _stop(
    state: str,
    code: str,
    detail: str,
    *,
    budget_tokens: int | None,
    omitted: list[Omission] | None = None,
    unresolved: list[UnresolvedMaterial] | None = None,
) -> C9Prototype:
    return {
        "decision_state": state,
        "load_ids": [],
        "omitted": list(omitted or []),
        "unresolved": list(unresolved or []),
        "loaded_token_estimate": 0,
        "budget_tokens": budget_tokens,
        "why_loaded": {},
        "errors": [{"code": code, "detail": detail}],
    }


def _input_error(
    code: str,
    detail: str,
    budget_tokens: int | None,
) -> C9Prototype:
    return _stop(
        "STOP_INPUT_INVALID",
        code,
        detail,
        budget_tokens=budget_tokens,
    )


def _valid_int(value: object, *, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _validate_material(
    raw: object,
    index: int,
    budget_tokens: int,
) -> C9Prototype | None:
    if not isinstance(raw, dict):
        return _input_error(
            "M11_MATERIAL_NOT_OBJECT",
            f"candidate_materials[{index}] 必须是对象",
            budget_tokens,
        )
    missing = sorted(REQUIRED_MATERIAL_FIELDS - raw.keys())
    if missing:
        return _input_error(
            "M11_MATERIAL_FIELD_MISSING",
            f"candidate_materials[{index}] 缺字段：{', '.join(missing)}",
            budget_tokens,
        )
    material_id = raw["id"]
    if not isinstance(material_id, str) or not material_id.strip():
        return _input_error(
            "M11_MATERIAL_ID_INVALID",
            f"candidate_materials[{index}].id 必须是非空字符串",
            budget_tokens,
        )
    if not _valid_int(raw["estimated_tokens"], minimum=0):
        return _input_error(
            "M11_TOKEN_ESTIMATE_INVALID",
            f"{material_id}.estimated_tokens 必须是非负整数",
            budget_tokens,
        )
    if (
        not isinstance(raw["actuality_class"], str)
        or raw["actuality_class"] not in ACTUALITY_CLASSES
    ):
        return _input_error(
            "M11_ACTUALITY_INVALID",
            f"{material_id}.actuality_class 未显式给出合法值",
            budget_tokens,
        )
    if (
        not isinstance(raw["obligation_tier"], str)
        or raw["obligation_tier"] not in OBLIGATION_TIERS
    ):
        return _input_error(
            "M11_OBLIGATION_INVALID",
            f"{material_id}.obligation_tier 未显式给出合法值",
            budget_tokens,
        )
    if not isinstance(raw["task_relation"], str) or not raw["task_relation"].strip():
        return _input_error(
            "M11_TASK_RELATION_MISSING",
            f"{material_id}.task_relation 必须由调用者说明",
            budget_tokens,
        )
    if (
        not isinstance(raw["recall_disposition"], str)
        or raw["recall_disposition"] not in RECALL_DISPOSITIONS
    ):
        return _input_error(
            "M11_RECALL_DISPOSITION_INVALID",
            f"{material_id}.recall_disposition 未显式给出合法值",
            budget_tokens,
        )
    recall_handle = raw["recall_handle"]
    if raw["recall_disposition"] == "RETRIEVABLE":
        if not isinstance(recall_handle, str) or not recall_handle.strip():
            return _input_error(
                "M11_RECALL_HANDLE_MISSING",
                f"{material_id} 标为可回取时必须给 recall_handle",
                budget_tokens,
            )
    elif recall_handle is not None:
        return _input_error(
            "M11_RECALL_HANDLE_CONFLICT",
            f"{material_id} 标为不可回取时 recall_handle 必须为 null",
            budget_tokens,
        )
    actuality = raw["actuality_class"]
    unresolved_reason = raw["unresolved_reason"]
    if actuality == "UNRESOLVED":
        if not isinstance(unresolved_reason, str) or not unresolved_reason.strip():
            return _input_error(
                "M11_UNRESOLVED_REASON_MISSING",
                f"{material_id} 标为 unresolved 时必须说明原因",
                budget_tokens,
            )
    elif unresolved_reason is not None:
        return _input_error(
            "M11_UNRESOLVED_REASON_CONFLICT",
            f"{material_id} 不是 unresolved，unresolved_reason 必须为 null",
            budget_tokens,
        )
    rank = raw["selection_rank"]
    if raw["obligation_tier"] in {"SHOULD", "MAY"}:
        if not _valid_int(rank, minimum=0):
            return _input_error(
                "M11_SELECTION_RANK_MISSING",
                f"{material_id} 是可选义务，必须给非负 selection_rank",
                budget_tokens,
            )
    elif rank is not None:
        return _input_error(
            "M11_HARD_RANK_CONFLICT",
            f"{material_id} 是 HARD，selection_rank 必须显式为 null",
            budget_tokens,
        )
    return None


def _omission(item: CandidateMaterial, reason: str) -> Omission:
    return {
        "id": item["id"],
        "reason": reason,
        "recall_disposition": item["recall_disposition"],
        "recall_handle": item["recall_handle"],
    }


def _why_loaded(item: CandidateMaterial) -> str:
    relation = item["task_relation"].strip()
    if item["obligation_tier"] == "HARD":
        return f"HARD 保底义务；{relation}"
    return (
        f"{item['obligation_tier']}，rank={item['selection_rank']}，"
        f"在保底集之后仍有预算；{relation}"
    )


def pack_context(request: PackRequest | dict[str, Any]) -> C9Prototype:
    """按显式输入生成一个确定性的 C9 prototype。

    ``task_id`` 只用于关联任务，绝不代表授权。任何 required 字段、
    unresolved 决策或 HARD 预算不足都会失败关闭，不会静默补默认值。
    """

    if not isinstance(request, dict):
        return _input_error(
            "M11_REQUEST_NOT_OBJECT",
            "request 必须是对象",
            None,
        )
    missing = sorted(REQUIRED_REQUEST_FIELDS - request.keys())
    raw_budget = request.get("budget_tokens")
    visible_budget = raw_budget if _valid_int(raw_budget, minimum=1) else None
    if missing:
        return _input_error(
            "M11_REQUEST_FIELD_MISSING",
            f"request 缺字段：{', '.join(missing)}",
            visible_budget,
        )
    task_id = request["task_id"]
    if not isinstance(task_id, str) or not task_id.strip():
        return _input_error(
            "M11_TASK_ID_INVALID",
            "task_id 必须是非空关联 ID，且不代表授权",
            visible_budget,
        )
    scope = request["task_actuality_scope"]
    if not isinstance(scope, str) or scope not in TASK_SCOPES:
        return _input_error(
            "M11_TASK_SCOPE_INVALID",
            "task_actuality_scope 必须由调用者显式给出合法值",
            visible_budget,
        )
    if not _valid_int(raw_budget, minimum=1):
        return _input_error(
            "M11_BUDGET_INVALID",
            "budget_tokens 必须是正整数硬上限",
            None,
        )
    budget_tokens = raw_budget
    estimator = request["token_estimator_ref"]
    if not isinstance(estimator, str) or not estimator.strip():
        return _input_error(
            "M11_TOKEN_ESTIMATOR_REF_MISSING",
            "token_estimator_ref 必须由调用者显式给出",
            budget_tokens,
        )
    raw_materials = request["candidate_materials"]
    if not isinstance(raw_materials, list) or not raw_materials:
        return _input_error(
            "M11_CANDIDATE_MATERIALS_INVALID",
            "candidate_materials 必须是非空列表",
            budget_tokens,
        )
    for index, raw in enumerate(raw_materials):
        failure = _validate_material(raw, index, budget_tokens)
        if failure is not None:
            return failure
    materials: list[CandidateMaterial] = raw_materials
    ids = [item["id"] for item in materials]
    if len(ids) != len(set(ids)):
        return _input_error(
            "M11_MATERIAL_ID_DUPLICATE",
            "candidate_materials.id 必须唯一",
            budget_tokens,
        )

    unresolved: list[UnresolvedMaterial] = [
        {
            "id": item["id"],
            "reason": item["unresolved_reason"] or "",
            "obligation_tier": item["obligation_tier"],
        }
        for item in materials
        if item["actuality_class"] == "UNRESOLVED"
    ]
    if unresolved:
        return _stop(
            "STOP_UNRESOLVED",
            "M11_UNRESOLVED_REQUIRES_CALLER_DECISION",
            "存在调用者明确登记的未决状态；本原型不替上游判定",
            budget_tokens=budget_tokens,
            unresolved=unresolved,
        )

    compatible: list[CandidateMaterial] = []
    omitted: list[Omission] = []
    for item in materials:
        is_future = item["actuality_class"] == "FUTURE_PLAN_OR_PROJECTION"
        if scope == "CURRENT_TRUTH_REQUIRED" and is_future:
            if item["obligation_tier"] == "HARD":
                return _stop(
                    "STOP_CONFLICT",
                    "M11_ACTUALITY_HARD_CONFLICT",
                    f"{item['id']} 同时标为未来材料和当前任务 HARD",
                    budget_tokens=budget_tokens,
                )
            omitted.append(_omission(item, "OUTSIDE_TASK_ACTUALITY_SCOPE"))
            continue
        compatible.append(item)

    hard = sorted(
        (item for item in compatible if item["obligation_tier"] == "HARD"),
        key=lambda item: item["id"],
    )
    hard_tokens = sum(item["estimated_tokens"] for item in hard)
    if hard_tokens > budget_tokens:
        return _stop(
            "STOP_HARD_BUDGET",
            "M11_HARD_OBLIGATIONS_EXCEED_BUDGET",
            f"HARD 合计 {hard_tokens} token，超过预算 {budget_tokens}",
            budget_tokens=budget_tokens,
            omitted=omitted,
        )

    loaded = list(hard)
    used = hard_tokens
    optional = sorted(
        (
            item
            for item in compatible
            if item["obligation_tier"] in {"SHOULD", "MAY"}
        ),
        key=lambda item: (
            0 if item["obligation_tier"] == "SHOULD" else 1,
            item["selection_rank"],
            item["id"],
        ),
    )
    for item in optional:
        item_tokens = item["estimated_tokens"]
        if used + item_tokens <= budget_tokens:
            loaded.append(item)
            used += item_tokens
        else:
            omitted.append(_omission(item, "BUDGET_OPTIONAL_DEFERRED"))

    load_ids = [item["id"] for item in loaded]
    recomputed = sum(item["estimated_tokens"] for item in loaded)
    if recomputed != used or used > budget_tokens:
        return _stop(
            "STOP_VERIFICATION",
            "M11_BUDGET_ACCOUNTING_MISMATCH",
            "最终预算复算失败",
            budget_tokens=budget_tokens,
            omitted=omitted,
        )
    return {
        "decision_state": "READY",
        "load_ids": load_ids,
        "omitted": omitted,
        "unresolved": [],
        "loaded_token_estimate": used,
        "budget_tokens": budget_tokens,
        "why_loaded": {item["id"]: _why_loaded(item) for item in loaded},
        "errors": [],
    }


def _run_synthetic_demo() -> None:
    """直接运行本文件时，展示一份不接触真实小说的最小作者可见结果。"""

    request: PackRequest = {
        "task_id": "DEMO-NEXT-SCENE",
        "task_actuality_scope": "CURRENT_TRUTH_REQUIRED",
        "budget_tokens": 70,
        "token_estimator_ref": "demo-estimator-v1",
        "candidate_materials": [
            {
                "id": "DEMO-AUTHOR-PIN",
                "estimated_tokens": 50,
                "actuality_class": "ACTIVE_CONSTRAINT",
                "obligation_tier": "HARD",
                "selection_rank": None,
                "task_relation": "作者要求本场不能揭开角色真实身份",
                "recall_disposition": "NOT_RETRIEVABLE",
                "recall_handle": None,
                "unresolved_reason": None,
            },
            {
                "id": "DEMO-SUPPORT-EVIDENCE",
                "estimated_tokens": 30,
                "actuality_class": "CURRENT_FACT_OR_STATE",
                "obligation_tier": "SHOULD",
                "selection_rank": 1,
                "task_relation": "支持上述限制的旧章证据坐标",
                "recall_disposition": "RETRIEVABLE",
                "recall_handle": "demo://evidence/identity",
                "unresolved_reason": None,
            },
        ],
    }
    print(json.dumps(pack_context(request), ensure_ascii=False, indent=2))


__all__ = [
    "C9Prototype",
    "CandidateMaterial",
    "PackRequest",
    "pack_context",
]


if __name__ == "__main__":
    _run_synthetic_demo()

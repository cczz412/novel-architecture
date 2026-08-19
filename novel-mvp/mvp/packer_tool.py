"""M11 纯对象打包器的独立本地文件工具。

``execute`` 只接对象，复用现役 ``packer.pack_context`` 的 actuality、义务、
rank、未决和回取规则。Path 只存在于 LOCAL_FILESYSTEM_ONLY CLI 适配层。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, TextIO

if __package__:
    from . import packer
else:  # 允许直接运行本地文件工具。
    import packer


TRANSPORT_SCOPE = "LOCAL_FILESYSTEM_ONLY"
ESTIMATOR_IDENTITY = "M11_FIXED_MECHANICAL_LOOKUP_V1"
PROTOTYPE_IDENTITY = "M11_CONTEXT_PACK_FILE_TOOL_PROTOTYPE"
PROTOTYPE_VERSION = "v1"
REQUEST_FIELDS = frozenset(
    {
        "task_id",
        "task_actuality_scope",
        "budget_tokens",
        "token_estimator",
        "candidate_materials",
    }
)
ESTIMATOR_FIELDS = frozenset({"identity", "estimates"})
RESULT_FIELDS = frozenset(
    {
        "prototype",
        "task_receipt",
        "decision_state",
        "loaded",
        "omitted",
        "why_loaded",
        "unresolved",
        "budget",
        "errors",
    }
)
RENDERABLE_STATES = frozenset(
    {"READY", "STOP_UNRESOLVED", "STOP_HARD_BUDGET"}
)
TASK_RECEIPT_FIELDS = frozenset(
    {"task_id", "task_actuality_scope", "normalized_request_sha256"}
)
BUDGET_FIELDS = frozenset(
    {"limit_tokens", "used_tokens", "estimator_identity"}
)
OMISSION_FIELDS = frozenset(
    {"id", "reason", "recall_disposition", "recall_handle"}
)
AUTHOR_SAFE_OMISSION_REASON_LABELS = {
    "OUTSIDE_TASK_ACTUALITY_SCOPE": "超出当前故事时点或本次任务允许范围",
    "BUDGET_OPTIONAL_DEFERRED": "本次预算未装入",
}
UNRESOLVED_FIELDS = frozenset({"id", "reason", "obligation_tier"})
ERROR_FIELDS = frozenset({"code", "detail"})


class PackerToolError(RuntimeError):
    """文件工具在产生可信的 M11 原型结果前失败关闭。"""


def _valid_int(value: object, *, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _valid_task_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= 200
        and not any(
            ord(character) < 32 or ord(character) == 127
            for character in value
        )
    )


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _normalized_request_payload(request: dict[str, Any]) -> dict[str, Any]:
    materials = sorted(
        (copy.deepcopy(item) for item in request["candidate_materials"]),
        key=lambda item: item["id"],
    )
    estimates = request["token_estimator"]["estimates"]
    return {
        "task_id": request["task_id"],
        "task_actuality_scope": request["task_actuality_scope"],
        "budget_tokens": request["budget_tokens"],
        "token_estimator": {
            "identity": request["token_estimator"]["identity"],
            "estimates": {
                material["id"]: estimates[material["id"]]
                for material in materials
            },
        },
        "candidate_materials": materials,
    }


def _request_sha256(request: dict[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(_normalized_request_payload(request))
    ).hexdigest()


def _strict_request(
    request: object,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    if not isinstance(request, dict):
        raise PackerToolError("REQUEST_NOT_OBJECT")
    missing = sorted(REQUEST_FIELDS - request.keys())
    extra = sorted(request.keys() - REQUEST_FIELDS)
    if missing:
        raise PackerToolError(f"REQUEST_MISSING_FIELDS:{','.join(missing)}")
    if extra:
        raise PackerToolError(f"REQUEST_UNKNOWN_FIELDS:{','.join(extra)}")

    task_id = request["task_id"]
    if not _valid_task_id(task_id):
        raise PackerToolError("TASK_ID_INVALID")
    task_scope = request["task_actuality_scope"]
    if not isinstance(task_scope, str) or task_scope not in packer.TASK_SCOPES:
        raise PackerToolError("TASK_ACTUALITY_SCOPE_INVALID")
    budget_tokens = request["budget_tokens"]
    if not _valid_int(budget_tokens, minimum=1):
        raise PackerToolError("BUDGET_TOKENS_INVALID")

    materials = request["candidate_materials"]
    if not isinstance(materials, list) or not materials:
        raise PackerToolError("CANDIDATE_MATERIALS_MUST_BE_NONEMPTY_LIST")
    ids: list[str] = []
    for index, material in enumerate(materials):
        if not isinstance(material, dict):
            raise PackerToolError(f"MATERIAL_NOT_OBJECT:{index}")
        missing_material = sorted(packer.REQUIRED_MATERIAL_FIELDS - material.keys())
        extra_material = sorted(material.keys() - packer.REQUIRED_MATERIAL_FIELDS)
        if missing_material:
            raise PackerToolError(
                f"MATERIAL_MISSING_FIELDS:{index}:{','.join(missing_material)}"
            )
        if extra_material:
            raise PackerToolError(
                f"MATERIAL_UNKNOWN_FIELDS:{index}:{','.join(extra_material)}"
            )
        material_id = material.get("id")
        if not isinstance(material_id, str) or not material_id.strip():
            raise PackerToolError(f"MATERIAL_ID_INVALID:{index}")
        ids.append(material_id)
    if len(ids) != len(set(ids)):
        raise PackerToolError("MATERIAL_ID_DUPLICATE")

    estimator = request["token_estimator"]
    if not isinstance(estimator, dict) or set(estimator) != ESTIMATOR_FIELDS:
        raise PackerToolError("TOKEN_ESTIMATOR_SHAPE_INVALID")
    identity = estimator["identity"]
    if identity != ESTIMATOR_IDENTITY:
        raise PackerToolError("TOKEN_ESTIMATOR_IDENTITY_INVALID")
    estimates = estimator["estimates"]
    if not isinstance(estimates, dict) or set(estimates) != set(ids):
        raise PackerToolError("TOKEN_ESTIMATE_LOOKUP_KEYS_MISMATCH")
    for material in materials:
        material_id = material["id"]
        estimate = estimates[material_id]
        if not _valid_int(estimate, minimum=0):
            raise PackerToolError(f"TOKEN_ESTIMATE_LOOKUP_INVALID:{material_id}")
        if estimate != material["estimated_tokens"]:
            raise PackerToolError(f"TOKEN_ESTIMATE_DRIFT:{material_id}")

    normalized_request = _normalized_request_payload(request)
    normalized_materials = normalized_request["candidate_materials"]

    core_request = {
        "task_id": task_id,
        "task_actuality_scope": task_scope,
        "budget_tokens": budget_tokens,
        "token_estimator_ref": identity,
        "candidate_materials": normalized_materials,
    }
    task_receipt = {
        "task_id": task_id,
        "task_actuality_scope": task_scope,
        "normalized_request_sha256": _request_sha256(request),
    }
    return core_request, identity, task_receipt


def _verify_ready_result(
    core_result: dict[str, Any],
    materials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {material["id"]: material for material in materials}
    load_ids = core_result["load_ids"]
    if len(load_ids) != len(set(load_ids)) or any(item_id not in by_id for item_id in load_ids):
        raise PackerToolError("PACKER_LOADED_IDS_INVALID")
    omitted = core_result["omitted"]
    omitted_ids: list[str] = []
    for row in omitted:
        if not isinstance(row, dict) or row.get("id") not in by_id:
            raise PackerToolError("PACKER_OMISSION_INVALID")
        material = by_id[row["id"]]
        if (
            row.get("recall_disposition") != material["recall_disposition"]
            or row.get("recall_handle") != material["recall_handle"]
        ):
            raise PackerToolError(f"PACKER_RECALL_DRIFT:{row['id']}")
        omitted_ids.append(row["id"])
    if set(load_ids).intersection(omitted_ids):
        raise PackerToolError("PACKER_LOADED_OMITTED_OVERLAP")
    if set(load_ids).union(omitted_ids) != set(by_id):
        raise PackerToolError("PACKER_MATERIAL_COVERAGE_GAP")
    loaded = [copy.deepcopy(by_id[item_id]) for item_id in load_ids]
    recomputed = sum(item["estimated_tokens"] for item in loaded)
    if (
        recomputed != core_result["loaded_token_estimate"]
        or recomputed > core_result["budget_tokens"]
    ):
        raise PackerToolError("PACKER_BUDGET_VERIFICATION_FAILED")
    return loaded


def execute(request: dict) -> dict:
    """产生稳定的 M11 原型上下文包；不读写任何路径。"""
    core_request, estimator_identity, task_receipt = _strict_request(request)
    core_result = packer.pack_context(core_request)
    if core_result["decision_state"] == "STOP_INPUT_INVALID":
        error = core_result["errors"][0]
        raise PackerToolError(f"{error['code']}:{error['detail']}")

    materials = core_request["candidate_materials"]
    loaded: list[dict[str, Any]] = []
    if core_result["decision_state"] == "READY":
        loaded = _verify_ready_result(core_result, materials)
    elif core_result["load_ids"] or core_result["loaded_token_estimate"] != 0:
        raise PackerToolError("PACKER_STOP_RETURNED_PARTIAL_PACKAGE")

    return {
        "prototype": {
            "identity": PROTOTYPE_IDENTITY,
            "version": PROTOTYPE_VERSION,
        },
        "task_receipt": task_receipt,
        "decision_state": core_result["decision_state"],
        "loaded": loaded,
        "omitted": copy.deepcopy(core_result["omitted"]),
        "why_loaded": copy.deepcopy(core_result["why_loaded"]),
        "unresolved": copy.deepcopy(core_result["unresolved"]),
        "budget": {
            "limit_tokens": core_result["budget_tokens"],
            "used_tokens": core_result["loaded_token_estimate"],
            "estimator_identity": estimator_identity,
        },
        "errors": copy.deepcopy(core_result["errors"]),
    }


def _validated_loaded_material(
    material: object,
    index: int,
    budget_tokens: int,
) -> dict[str, Any]:
    if not isinstance(material, dict) or set(material) != packer.REQUIRED_MATERIAL_FIELDS:
        raise PackerToolError(f"RENDER_LOADED_MATERIAL_SHAPE_INVALID:{index}")
    failure = packer._validate_material(material, index, budget_tokens)
    if failure is not None:
        error = failure["errors"][0]
        raise PackerToolError(
            f"RENDER_LOADED_MATERIAL_INVALID:{index}:{error['code']}"
        )
    if material["actuality_class"] == "UNRESOLVED":
        raise PackerToolError(f"RENDER_LOADED_MATERIAL_UNRESOLVED:{index}")
    return copy.deepcopy(material)


def _validated_omission(row: object, index: int) -> dict[str, Any]:
    if not isinstance(row, dict) or set(row) != OMISSION_FIELDS:
        raise PackerToolError(f"RENDER_OMISSION_SHAPE_INVALID:{index}")
    material_id = row["id"]
    reason = row["reason"]
    disposition = row["recall_disposition"]
    handle = row["recall_handle"]
    if not isinstance(material_id, str) or not material_id.strip():
        raise PackerToolError(f"RENDER_OMISSION_ID_INVALID:{index}")
    if not isinstance(reason, str) or not reason.strip():
        raise PackerToolError(f"RENDER_OMISSION_REASON_INVALID:{index}")
    if (
        not isinstance(disposition, str)
        or disposition not in packer.RECALL_DISPOSITIONS
    ):
        raise PackerToolError(f"RENDER_OMISSION_RECALL_INVALID:{index}")
    if disposition == "RETRIEVABLE":
        if not isinstance(handle, str) or not handle.strip():
            raise PackerToolError(f"RENDER_OMISSION_HANDLE_MISSING:{index}")
    elif handle is not None:
        raise PackerToolError(f"RENDER_OMISSION_HANDLE_CONFLICT:{index}")
    return copy.deepcopy(row)


def _validated_unresolved(row: object, index: int) -> dict[str, Any]:
    if not isinstance(row, dict) or set(row) != UNRESOLVED_FIELDS:
        raise PackerToolError(f"RENDER_UNRESOLVED_SHAPE_INVALID:{index}")
    if not isinstance(row["id"], str) or not row["id"].strip():
        raise PackerToolError(f"RENDER_UNRESOLVED_ID_INVALID:{index}")
    if not isinstance(row["reason"], str) or not row["reason"].strip():
        raise PackerToolError(f"RENDER_UNRESOLVED_REASON_INVALID:{index}")
    if (
        not isinstance(row["obligation_tier"], str)
        or row["obligation_tier"] not in packer.OBLIGATION_TIERS
    ):
        raise PackerToolError(f"RENDER_UNRESOLVED_OBLIGATION_INVALID:{index}")
    return copy.deepcopy(row)


def _validated_errors(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise PackerToolError("RENDER_ERRORS_NOT_LIST")
    errors: list[dict[str, str]] = []
    for index, row in enumerate(value):
        if (
            not isinstance(row, dict)
            or set(row) != ERROR_FIELDS
            or not isinstance(row["code"], str)
            or not row["code"].strip()
            or not isinstance(row["detail"], str)
            or not row["detail"].strip()
        ):
            raise PackerToolError(f"RENDER_ERROR_SHAPE_INVALID:{index}")
        errors.append(copy.deepcopy(row))
    return errors


def validate_render_result(value: object) -> dict[str, Any]:
    """严格校验已有原型结果，不重新打包或补写字段。"""

    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        raise PackerToolError("RENDER_RESULT_SHAPE_INVALID")

    prototype = value["prototype"]
    if prototype != {"identity": PROTOTYPE_IDENTITY, "version": PROTOTYPE_VERSION}:
        raise PackerToolError("RENDER_PROTOTYPE_IDENTITY_INVALID")

    receipt = value["task_receipt"]
    if not isinstance(receipt, dict) or set(receipt) != TASK_RECEIPT_FIELDS:
        raise PackerToolError("RENDER_TASK_RECEIPT_SHAPE_INVALID")
    if not _valid_task_id(receipt["task_id"]):
        raise PackerToolError("RENDER_TASK_ID_INVALID")
    if (
        not isinstance(receipt["task_actuality_scope"], str)
        or receipt["task_actuality_scope"] not in packer.TASK_SCOPES
    ):
        raise PackerToolError("RENDER_TASK_SCOPE_INVALID")
    if not _valid_sha256(receipt["normalized_request_sha256"]):
        raise PackerToolError("RENDER_REQUEST_SHA_INVALID")

    budget = value["budget"]
    if not isinstance(budget, dict) or set(budget) != BUDGET_FIELDS:
        raise PackerToolError("RENDER_BUDGET_SHAPE_INVALID")
    if (
        not _valid_int(budget["limit_tokens"], minimum=1)
        or not _valid_int(budget["used_tokens"], minimum=0)
        or budget["used_tokens"] > budget["limit_tokens"]
        or budget["estimator_identity"] != ESTIMATOR_IDENTITY
    ):
        raise PackerToolError("RENDER_BUDGET_INVALID")

    decision_state = value["decision_state"]
    if not isinstance(decision_state, str) or decision_state not in RENDERABLE_STATES:
        raise PackerToolError("RENDER_DECISION_STATE_NOT_SUPPORTED")
    if not isinstance(value["loaded"], list):
        raise PackerToolError("RENDER_LOADED_NOT_LIST")
    loaded = [
        _validated_loaded_material(row, index, budget["limit_tokens"])
        for index, row in enumerate(value["loaded"])
    ]
    if not isinstance(value["omitted"], list):
        raise PackerToolError("RENDER_OMITTED_NOT_LIST")
    omitted = [
        _validated_omission(row, index)
        for index, row in enumerate(value["omitted"])
    ]
    if not isinstance(value["unresolved"], list):
        raise PackerToolError("RENDER_UNRESOLVED_NOT_LIST")
    unresolved = [
        _validated_unresolved(row, index)
        for index, row in enumerate(value["unresolved"])
    ]
    errors = _validated_errors(value["errors"])

    why_loaded = value["why_loaded"]
    if not isinstance(why_loaded, dict) or any(
        not isinstance(material_id, str)
        or not isinstance(reason, str)
        or not reason.strip()
        for material_id, reason in why_loaded.items()
    ):
        raise PackerToolError("RENDER_WHY_LOADED_INVALID")

    loaded_ids = [row["id"] for row in loaded]
    omitted_ids = [row["id"] for row in omitted]
    unresolved_ids = [row["id"] for row in unresolved]
    all_ids = loaded_ids + omitted_ids + unresolved_ids
    if len(all_ids) != len(set(all_ids)):
        raise PackerToolError("RENDER_MATERIAL_ID_DUPLICATE_OR_OVERLAP")
    if set(why_loaded) != set(loaded_ids):
        raise PackerToolError("RENDER_LOADED_REASON_COUNT_MISMATCH")
    used_tokens = sum(row["estimated_tokens"] for row in loaded)
    if used_tokens != budget["used_tokens"]:
        raise PackerToolError("RENDER_LOADED_TOKEN_MISMATCH")
    if receipt["task_actuality_scope"] == "CURRENT_TRUTH_REQUIRED" and any(
        row["actuality_class"] == "FUTURE_PLAN_OR_PROJECTION"
        for row in loaded
    ):
        raise PackerToolError("RENDER_LOADED_ACTUALITY_SCOPE_CONFLICT")

    if decision_state == "READY":
        if unresolved or errors:
            raise PackerToolError("RENDER_READY_STATE_CONTRADICTION")
    elif decision_state == "STOP_UNRESOLVED":
        if (
            loaded
            or omitted
            or why_loaded
            or budget["used_tokens"] != 0
            or not unresolved
            or len(errors) != 1
            or errors[0]["code"] != "M11_UNRESOLVED_REQUIRES_CALLER_DECISION"
        ):
            raise PackerToolError("RENDER_UNRESOLVED_STATE_CONTRADICTION")
    elif (
        loaded
        or why_loaded
        or unresolved
        or budget["used_tokens"] != 0
        or len(errors) != 1
        or errors[0]["code"] != "M11_HARD_OBLIGATIONS_EXCEED_BUDGET"
    ):
        raise PackerToolError("RENDER_HARD_BUDGET_STATE_CONTRADICTION")

    return {
        "prototype": copy.deepcopy(prototype),
        "task_receipt": copy.deepcopy(receipt),
        "decision_state": decision_state,
        "loaded": loaded,
        "omitted": omitted,
        "why_loaded": copy.deepcopy(why_loaded),
        "unresolved": unresolved,
        "budget": copy.deepcopy(budget),
        "errors": errors,
    }


def _render_recall(row: dict[str, Any]) -> str:
    if row["recall_disposition"] == "RETRIEVABLE":
        return f"可回取，入口 {row['recall_handle']}"
    return "不可回取，无回取入口"


def _state_descriptions() -> dict[str, str]:
    return {
        "READY": "已形成本次 M11 原型包；不代表正式 C9 或生产可用",
        "STOP_UNRESOLVED": "存在未决事项；本次没有自动解决，也没有形成上下文包",
        "STOP_HARD_BUDGET": "硬性材料超过本次预算；本次没有形成上下文包",
    }


def _render_identity_lines(result: dict[str, Any], *, title: str) -> list[str]:
    receipt = result["task_receipt"]
    budget = result["budget"]
    return [
        title,
        f"原型：{result['prototype']['identity']} / {result['prototype']['version']}",
        f"任务：{receipt['task_id']}",
        f"事实范围：{receipt['task_actuality_scope']}",
        f"请求摘要：{receipt['normalized_request_sha256']}",
        (
            f"预算：{budget['used_tokens']} / {budget['limit_tokens']} token；"
            f"估算器：{budget['estimator_identity']}"
        ),
        (
            f"最终状态：{result['decision_state']}（"
            f"{_state_descriptions()[result['decision_state']]}）"
        ),
    ]


def _render_loaded_lines(result: dict[str, Any]) -> list[str]:
    lines = [f"已装入材料（{len(result['loaded'])}）"]
    if result["loaded"]:
        for index, material in enumerate(result["loaded"], start=1):
            rank = (
                "不适用"
                if material["selection_rank"] is None
                else str(material["selection_rank"])
            )
            lines.extend(
                [
                    (
                        f"{index}. {material['id']}｜义务 "
                        f"{material['obligation_tier']}｜排序 {rank}｜"
                        f"{material['estimated_tokens']} token"
                    ),
                    f"   装入原因：{result['why_loaded'][material['id']]}",
                ]
            )
    else:
        lines.append("- 无")
    return lines


def _render_unresolved_lines(result: dict[str, Any]) -> list[str]:
    lines = [f"未决事项（{len(result['unresolved'])}）"]
    if result["unresolved"]:
        for index, row in enumerate(result["unresolved"], start=1):
            lines.append(
                f"{index}. {row['id']}｜义务 {row['obligation_tier']}｜"
                f"原因 {row['reason']}"
            )
    else:
        lines.append("- 无")
    return lines


def _render_error_lines(result: dict[str, Any]) -> list[str]:
    lines = [f"停止／错误说明（{len(result['errors'])}）"]
    if result["errors"]:
        for index, row in enumerate(result["errors"], start=1):
            lines.append(f"{index}. {row['code']}｜{row['detail']}")
    else:
        lines.append("- 无")
    return lines


def _render_closing_note() -> list[str]:
    return [
        "说明：“本次未装入”不代表永久删除；"
        "“未决”仍等待上游或作者处理，不代表系统已自动解决。",
    ]


def _author_safe_omission_lines(omitted: list[dict[str, Any]]) -> list[str]:
    counts = {reason: 0 for reason in AUTHOR_SAFE_OMISSION_REASON_LABELS}
    recheckable = 0
    for row in omitted:
        reason = row["reason"]
        if reason not in AUTHOR_SAFE_OMISSION_REASON_LABELS:
            raise PackerToolError("AUTHOR_SAFE_OMISSION_REASON_UNKNOWN")
        counts[reason] += 1
        if row["recall_disposition"] == "RETRIEVABLE":
            recheckable += 1
    lines = [
        "被挡材料",
        f"已阻断 {len(omitted)} 条",
    ]
    for reason, label in AUTHOR_SAFE_OMISSION_REASON_LABELS.items():
        lines.append(f"{label}：{counts[reason]} 条")
    lines.append(f"可由系统重新检查：{recheckable} 条")
    return lines


def render(value: object) -> str:
    """把已有 M11 原型结果排版为人读清单，不修改决策。"""

    result = validate_render_result(value)
    lines = _render_identity_lines(result, title="M11 上下文装包清单（原型）")
    lines.extend(["", *_render_loaded_lines(result)])
    lines.extend(["", f"本次未装入材料（{len(result['omitted'])}）"])
    if result["omitted"]:
        for index, row in enumerate(result["omitted"], start=1):
            lines.append(
                f"{index}. {row['id']}｜原因 {row['reason']}｜"
                f"回取：{_render_recall(row)}"
            )
    else:
        lines.append("- 无")
    lines.extend(["", *_render_unresolved_lines(result)])
    lines.extend(["", *_render_error_lines(result)])
    lines.extend(["", *_render_closing_note()])
    return "\n".join(lines) + "\n"


def render_author_safe(value: object) -> str:
    """把已有 M11 原型结果排版为作者页；被挡材料只出分桶计数。"""

    result = validate_render_result(value)
    lines = _render_identity_lines(result, title="M11 作者安全装包说明（原型）")
    lines.extend(["", *_render_loaded_lines(result)])
    lines.extend(["", *_author_safe_omission_lines(result["omitted"])])
    lines.extend(["", *_render_unresolved_lines(result)])
    lines.extend(["", *_render_error_lines(result)])
    lines.extend(["", *_render_closing_note()])
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise PackerToolError(f"FILE_NOT_UTF8:{path}") from exc
    except json.JSONDecodeError as exc:
        raise PackerToolError(f"FILE_NOT_JSON:{path}:{exc}") from exc


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = None
        _fsync_directory(path.parent)
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = value.encode("utf-8")
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = None
        _fsync_directory(path.parent)
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="M11 LOCAL_FILESYSTEM_ONLY 上下文打包工具")
    parser.add_argument("--input", help="打包请求或已有结果 JSON；不给时从 stdin 读")
    parser.add_argument("--output", help="本地结果文件；不给时写 stdout")
    render_mode = parser.add_mutually_exclusive_group()
    render_mode.add_argument(
        "--render",
        action="store_true",
        help="把已有 M11 原型结果严格校验后排版为人读清单",
    )
    render_mode.add_argument(
        "--render-author-safe",
        action="store_true",
        help="把已有 M11 原型结果严格校验后排版为作者安全说明；不展示被挡材料身份",
    )
    args = parser.parse_args(argv)
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        if args.input:
            request = _read_json(Path(args.input))
        else:
            try:
                request = json.load(stdin)
            except json.JSONDecodeError as exc:
                raise PackerToolError(f"STDIN_NOT_JSON:{exc}") from exc
        if args.render or args.render_author_safe:
            rendered = (
                render_author_safe(request)
                if args.render_author_safe
                else render(request)
            )
            if args.output:
                _write_text_atomic(Path(args.output), rendered)
            else:
                stdout.write(rendered)
                stdout.flush()
        else:
            result = execute(request)
            if args.output:
                _write_json_atomic(Path(args.output), result)
            else:
                json.dump(result, stdout, ensure_ascii=False, sort_keys=True, indent=2)
                stdout.write("\n")
                stdout.flush()
    except (PackerToolError, OSError) as exc:
        stderr.write(f"M11_PACKER_TOOL_REJECTED:{exc}\n")
        stderr.flush()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

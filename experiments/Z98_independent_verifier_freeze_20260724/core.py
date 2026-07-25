"""第98道独立核验冻结件的纯程序合同。

本模块只做确定性 JSON 构造和严格校验。它不读环境变量值、不访问网络，
也不把裁判结论写回候选结果。
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from experiments.Z98_knife_a_patch_step1_20260724.core import (
    Z98ContractError,
    validate_atom_batch,
    validate_patch,
)


class Z98VerifierContractError(ValueError):
    """独立核验冻结或动态绑定合同不成立。"""


PROVIDER_ID = "qianwen_platform"
MODEL_ID = "qwen3.7-max-2026-05-20"
API_KEY_ENV = "DASHSCOPE_API_KEY"
MODEL_FAMILY = "qwen"
TESTED_MODEL_FAMILY = "deepseek"
OUTPUT_TOKEN_LIMIT = 4000
TIMEOUT_SECONDS = 120
TOTAL_COST_CAP_CNY = 10
MICRO_CNY_PER_CNY = 1_000_000
TOTAL_COST_CAP_MICRO_CNY = TOTAL_COST_CAP_CNY * MICRO_CNY_PER_CNY
TOTAL_TOKEN_CAP = 500_000
INPUT_PRICE_CNY_PER_MILLION_TOKENS = 12
OUTPUT_PRICE_CNY_PER_MILLION_TOKENS = 36
QWEN_CALIBRATION_MAX_PROMPT_TOKENS = 11_395
QWEN_CALIBRATION_MESSAGE_CHARS = 23_202
QWEN_PROJECTION_SAFETY_NUMERATOR = 5
QWEN_PROJECTION_SAFETY_DENOMINATOR = 4

_VERDICT_TOP_KEYS = frozenset({"schema", "case_id", "items", "receipt"})
_VERDICT_ITEM_KEYS = frozenset(
    {
        "item_id",
        "verdict",
        "fact_support",
        "qualifier_support",
        "anchor_support",
        "atomicity",
        "reason_codes",
    }
)
_VERDICT_RECEIPT_KEYS = frozenset({"returned_item_ids"})
_FACT_SUPPORT = frozenset({"SUPPORTED", "PARTIAL", "UNSUPPORTED"})
_QUALIFIER_SUPPORT = frozenset(
    {"COMPLETE", "PARTIAL", "INCORRECT", "NOT_APPLICABLE"}
)
_ANCHOR_SUPPORT = frozenset({"FULL", "PARTIAL", "UNSUPPORTED", "INVALID_ID"})
_ATOMICITY = frozenset({"ATOMIC", "COMPOUND"})
_REASON_CODES = frozenset(
    {
        "NONE",
        "FACT_PARTIAL",
        "FACT_UNSUPPORTED",
        "QUALIFIER_MISSING",
        "QUALIFIER_INCORRECT",
        "ANCHOR_PARTIAL",
        "ANCHOR_UNSUPPORTED",
        "ANCHOR_INVALID",
        "NOT_ATOMIC",
        "CONTEXT_INSUFFICIENT",
    }
)
_FORBIDDEN_MODEL_VISIBLE_KEYS = frozenset(
    {
        "provider",
        "provider_id",
        "provider_lane",
        "tested_provider",
        "arm",
        "arm_id",
        "arm_name",
        "contract_mode",
        "gold",
        "golden",
        "answer",
        "answers",
        "human_verdict",
        "human_judgment",
        "historical_score",
        "historical_scores",
        "repair_log",
        "repair_logs",
    }
)
_FORBIDDEN_MODEL_VISIBLE_MARKERS = (
    "sensenova",
    "tencent_tokenhub",
    "deepseek-v4",
    "single_patch",
    "atom_batch_v2",
    "金标",
    "人工判词",
    "历史成绩",
    "修复日志",
)
_P2_PLACEHOLDER = "__Z98_RUNTIME_P2_RESULT__"
_CALL_ATTEMPT_KEYS = frozenset(
    {
        "schema_version",
        "node_id",
        "tested_lane",
        "provider",
        "model",
        "request_path",
        "request_sha256",
        "response_path",
        "response_sha256",
        "attempt_number",
        "http_status",
        "finish_reason",
    }
)
_USAGE_KEYS = frozenset(
    {
        "schema_version",
        "node_id",
        "tested_lane",
        "provider",
        "model",
        "request_path",
        "request_sha256",
        "response_path",
        "response_sha256",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    }
)


def stable_json_bytes(value: Any) -> bytes:
    """把 JSON 兼容值编码成可重复的 UTF-8 字节。"""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    """返回小写 SHA-256。"""

    return hashlib.sha256(data).hexdigest()


def conservative_prompt_token_projection(messages: Any) -> int:
    """按封存 Qwen 实账最高比例再乘 1.25，估算完整动态输入。"""

    message_chars = len(
        json.dumps(
            messages,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    if message_chars <= 0:
        raise Z98VerifierContractError("裁判 messages 不得为空")
    numerator = (
        message_chars
        * QWEN_CALIBRATION_MAX_PROMPT_TOKENS
        * QWEN_PROJECTION_SAFETY_NUMERATOR
    )
    denominator = (
        QWEN_CALIBRATION_MESSAGE_CHARS
        * QWEN_PROJECTION_SAFETY_DENOMINATOR
    )
    return math.ceil(numerator / denominator)


def conservative_cost_cap_micro_cny(token_cap: int) -> int:
    """按全部 token 都走输出价计算单次最坏金额上限。"""

    if not isinstance(token_cap, int) or isinstance(token_cap, bool):
        raise Z98VerifierContractError("token_cap 必须是正整数")
    if token_cap <= 0:
        raise Z98VerifierContractError("token_cap 必须是正整数")
    return token_cap * OUTPUT_PRICE_CNY_PER_MILLION_TOKENS


def enforce_cost_gate_before_send(
    *,
    actual_accumulated_micro_cny: int,
    next_conservative_cap_micro_cny: int,
) -> dict[str, int | bool]:
    """发送前执行金额硬闸；超出整轮 10 元就拒绝。"""

    for value, label in (
        (actual_accumulated_micro_cny, "actual_accumulated_micro_cny"),
        (next_conservative_cap_micro_cny, "next_conservative_cap_micro_cny"),
    ):
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
        ):
            raise Z98VerifierContractError(f"{label} 必须是非负整数")
    projected = (
        actual_accumulated_micro_cny + next_conservative_cap_micro_cny
    )
    if projected > TOTAL_COST_CAP_MICRO_CNY:
        raise Z98VerifierContractError(
            "裁判通道金额帽将超过 10 元，发送前硬停"
        )
    return {
        "allowed": True,
        "actual_accumulated_micro_cny": actual_accumulated_micro_cny,
        "next_conservative_cap_micro_cny": (
            next_conservative_cap_micro_cny
        ),
        "projected_micro_cny": projected,
        "round_cap_micro_cny": TOTAL_COST_CAP_MICRO_CNY,
    }


def enforce_token_gate_before_send(
    *,
    actual_accumulated_tokens: int,
    next_conservative_token_projection: int,
) -> dict[str, int | bool]:
    """发送前执行 CZ 直批 50 万 token 整轮硬闸。"""

    for value, label in (
        (actual_accumulated_tokens, "actual_accumulated_tokens"),
        (
            next_conservative_token_projection,
            "next_conservative_token_projection",
        ),
    ):
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
        ):
            raise Z98VerifierContractError(f"{label} 必须是非负整数")
    projected = (
        actual_accumulated_tokens + next_conservative_token_projection
    )
    if projected > TOTAL_TOKEN_CAP:
        raise Z98VerifierContractError(
            "裁判通道将超过 CZ 直批 50 万 token 总帽，发送前硬停"
        )
    return {
        "allowed": True,
        "actual_accumulated_tokens": actual_accumulated_tokens,
        "next_conservative_token_projection": (
            next_conservative_token_projection
        ),
        "projected_tokens": projected,
        "round_cap_tokens": TOTAL_TOKEN_CAP,
    }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Z98VerifierContractError(f"{label} 必须是对象")
    return value


def _strict_keys(
    value: Mapping[str, Any],
    expected: set[str] | frozenset[str],
    label: str,
) -> None:
    missing = set(expected) - set(value)
    extra = set(value) - set(expected)
    if missing:
        raise Z98VerifierContractError(f"{label} 缺字段：{sorted(missing)}")
    if extra:
        raise Z98VerifierContractError(
            f"{label} 含未知字段：{sorted(extra)}"
        )


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise Z98VerifierContractError(f"{label} 必须是非空字符串")
    return value


def _string_list(
    value: Any,
    label: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        raise Z98VerifierContractError(f"{label} 必须是数组")
    if not allow_empty and not value:
        raise Z98VerifierContractError(f"{label} 不得为空")
    if any(not isinstance(item, str) or not item for item in value):
        raise Z98VerifierContractError(f"{label} 只能含非空字符串")
    if len(value) != len(set(value)):
        raise Z98VerifierContractError(f"{label} 含重复项")
    return list(value)


def _strict_json_loads(raw: str | bytes, label: str) -> Any:
    """严格解析 JSON，任何层级的重复键与 NaN/Infinity 都拒绝。"""

    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Z98VerifierContractError(f"{label} 不是 UTF-8") from exc
    elif isinstance(raw, str):
        text = raw
    else:
        raise Z98VerifierContractError(f"{label} 必须是字符串或字节")

    def reject_duplicate_pairs(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise Z98VerifierContractError(
                    f"{label} 含重复 JSON 键：{key}"
                )
            result[key] = value
        return result

    def reject_nonstandard_constant(value: str) -> None:
        raise Z98VerifierContractError(
            f"{label} 含非标准 JSON 常量：{value}"
        )

    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_pairs,
            parse_constant=reject_nonstandard_constant,
        )
    except json.JSONDecodeError as exc:
        raise Z98VerifierContractError(f"{label} 不是严格 JSON") from exc


def scan_model_visible_leaks(value: Any, path: str = "$") -> list[dict[str, str]]:
    """扫描裁判可见面里的臂身份、答案面和修复日志泄漏。"""

    hits: list[dict[str, str]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text.casefold() in _FORBIDDEN_MODEL_VISIBLE_KEYS:
                hits.append(
                    {
                        "path": f"{path}.{key_text}",
                        "reason": "forbidden_key",
                    }
                )
            hits.extend(
                scan_model_visible_leaks(child, f"{path}.{key_text}")
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(scan_model_visible_leaks(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.casefold()
        for marker in _FORBIDDEN_MODEL_VISIBLE_MARKERS:
            if marker.casefold() in lowered:
                hits.append(
                    {
                        "path": path,
                        "reason": f"forbidden_marker:{marker}",
                    }
                )
    return hits


def verifier_response_contract(
    case_id: str,
    item_ids: Sequence[str],
) -> dict[str, Any]:
    """构造模型可见的只判不改输出合同。"""

    if not item_ids:
        raise Z98VerifierContractError("核验项不得为空")
    return {
        "schema": "z98-independent-verdict-v1",
        "case_id": case_id,
        "item_ids_in_order": list(item_ids),
        "item_fields": {
            "item_id": "必须逐字复制对应 item_id",
            "verdict": ["PASS", "REJECT"],
            "fact_support": sorted(_FACT_SUPPORT),
            "qualifier_support": sorted(_QUALIFIER_SUPPORT),
            "anchor_support": sorted(_ANCHOR_SUPPORT),
            "atomicity": sorted(_ATOMICITY),
            "reason_codes": sorted(_REASON_CODES),
        },
        "rules": [
            "只判断，不改写事件，不补锚，不给修复建议。",
            "items 数量、顺序和 item_id 必须与输入完全一致。",
            (
                "只有事实受支持、限定完整或不适用、锚全托住、且内容原子化时，"
                "verdict 才能为 PASS，reason_codes 必须且只能为 [\"NONE\"]。"
            ),
            "其他情况 verdict 必须为 REJECT，且 reason_codes 不得含 NONE。",
            "只输出一个 JSON 对象，不得输出解释段、Markdown 或合同外字段。",
        ],
    }


def _source_items_from_repair_request(
    repair_request: Mapping[str, Any],
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """从冻结 P2 请求机械提取裁判可见源事件与锚。"""

    model_visible = _mapping(
        repair_request.get("model_visible"),
        "repair_request.model_visible",
    )
    messages = model_visible.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise Z98VerifierContractError("冻结 P2 messages 结构非法")
    user_message = _mapping(messages[1], "repair_request.user_message")
    content = _nonempty_string(
        user_message.get("content"),
        "repair_request.user_message.content",
    )
    payload = _strict_json_loads(content, "冻结 P2 user content")
    payload = _mapping(payload, "repair_request.user_payload")
    mode = repair_request.get("contract_mode")
    source_rows: list[Mapping[str, Any]]
    if mode == "single_patch":
        source_rows = [_mapping(payload.get("input"), "single input")]
    elif mode == "atom_batch_v2":
        slots = payload.get("slots")
        if not isinstance(slots, list) or not slots:
            raise Z98VerifierContractError("batch slots 必须是非空数组")
        source_rows = [
            _mapping(row, f"batch slots[{index}]")
            for index, row in enumerate(slots)
        ]
    else:
        raise Z98VerifierContractError("冻结 P2 contract_mode 非法")

    items: list[dict[str, Any]] = []
    source_slot_ids: list[str] = []
    for index, row in enumerate(source_rows, start=1):
        slot_id = _nonempty_string(row.get("slot_id"), "source slot_id")
        source_slot_ids.append(slot_id)
        source_span_ids = _string_list(
            row.get("source_span_ids"),
            "source_span_ids",
        )
        anchors = row.get("anchor_candidates")
        if not isinstance(anchors, list) or not anchors:
            raise Z98VerifierContractError("anchor_candidates 必须是非空数组")
        normalized_anchors: list[dict[str, str]] = []
        for anchor_index, anchor in enumerate(anchors):
            anchor_row = _mapping(
                anchor,
                f"anchor_candidates[{anchor_index}]",
            )
            if set(anchor_row) != {"span_id", "quote"}:
                raise Z98VerifierContractError("候选锚字段集合漂移")
            normalized_anchors.append(
                {
                    "span_id": _nonempty_string(
                        anchor_row["span_id"],
                        "anchor.span_id",
                    ),
                    "quote": _nonempty_string(
                        anchor_row["quote"],
                        "anchor.quote",
                    ),
                }
            )
        items.append(
            {
                "item_id": f"ITEM-{index:02d}",
                "source_event": _nonempty_string(
                    row.get("source_event"),
                    "source_event",
                ),
                "source_span_ids": source_span_ids,
                "candidate_anchors": normalized_anchors,
            }
        )
    return str(mode), items, source_slot_ids


def make_verifier_template(
    *,
    template_id: str,
    repair_request_path: str,
    repair_request_bytes: bytes,
    verification_token_cap: int,
) -> dict[str, Any]:
    """从一份冻结 P2 请求生成一份盲裁判模板。"""

    if verification_token_cap <= 0:
        raise Z98VerifierContractError("逐模板 token 帽必须为正整数")
    repair_request = _strict_json_loads(
        repair_request_bytes,
        "冻结 P2 请求",
    )
    repair_request = _mapping(repair_request, "repair_request")
    mode, source_items, source_slot_ids = _source_items_from_repair_request(
        repair_request
    )
    request_id = _nonempty_string(
        repair_request.get("request_id"),
        "repair_request.request_id",
    )
    case_id = f"CASE-{sha256_bytes(request_id.encode('utf-8'))[:16].upper()}"
    visible_items = [
        {
            **deepcopy(source_item),
            "candidate_result": {
                "runtime_placeholder": _P2_PLACEHOLDER,
            },
        }
        for source_item in source_items
    ]
    item_ids = [str(row["item_id"]) for row in source_items]
    user_payload = {
        "case_id": case_id,
        "task": (
            "逐项判断候选结果是否被源事件与候选锚支撑；"
            "只判不改，不得补写事件或锚。"
        ),
        "items": visible_items,
        "output_contract": verifier_response_contract(case_id, item_ids),
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是独立事实核验裁判。你只依据本请求中的源事件、候选锚和"
                "候选结果作判断；不得使用外部知识，不得修改候选结果，不得提出"
                "修复方案。严格按输出合同返回单个 JSON 对象。"
            ),
        },
        {
            "role": "user",
            "content": stable_json_bytes(user_payload).decode("utf-8"),
        },
    ]
    leak_hits = scan_model_visible_leaks(messages)
    if leak_hits:
        raise Z98VerifierContractError(
            f"裁判模板可见面命中泄漏：{leak_hits}"
        )
    source_data = {
        "case_id": case_id,
        "items": source_items,
    }
    return {
        "schema_version": "z98-independent-verifier-template-v1",
        "template_id": template_id,
        "status": "FROZEN_WAITING_P2_RESPONSE",
        "model_visible": {"messages": messages},
        "private_binding": {
            "repair_request_path": repair_request_path,
            "repair_request_sha256": sha256_bytes(repair_request_bytes),
            "repair_request_id": request_id,
            "repair_contract_mode": mode,
            "source_slot_ids": source_slot_ids,
            "case_id": case_id,
            "item_ids": item_ids,
            "source_data_sha256": sha256_bytes(stable_json_bytes(source_data)),
            "verification_token_cap": verification_token_cap,
            "dynamic_request_status": "PENDING_P2_RESPONSE",
        },
    }


def _normalized_candidate_results(
    *,
    mode: str,
    p2_payload: Any,
    expected_slot_ids: Sequence[str],
) -> list[dict[str, Any]]:
    if mode == "single_patch":
        try:
            patch = validate_patch(p2_payload)
        except Z98ContractError as exc:
            raise Z98VerifierContractError(
                f"单条 P2 响应拒收：{exc}"
            ) from exc
        return [{"result_kind": "PATCH", "payload": patch}]
    if mode != "atom_batch_v2":
        raise Z98VerifierContractError("模板私有 contract_mode 非法")
    try:
        batch = validate_atom_batch(
            p2_payload,
            expected_slot_ids=list(expected_slot_ids),
        )
    except Z98ContractError as exc:
        raise Z98VerifierContractError(f"批式 P2 响应拒收：{exc}") from exc
    normalized: list[dict[str, Any]] = []
    for item in batch["items"]:
        status = item["status"]
        if status == "ok":
            normalized.append(
                {
                    "result_kind": "PATCH",
                    "payload": item["atom"],
                }
            )
        elif status == "split_required":
            normalized.append(
                {
                    "result_kind": "SPLIT_REQUIRED",
                    "payload": {"split_span_ids": item["split_span_ids"]},
                }
            )
        elif status == "needs_context":
            normalized.append(
                {
                    "result_kind": "NEEDS_CONTEXT",
                    "payload": {
                        "missing_context_codes": item[
                            "missing_context_codes"
                        ]
                    },
                }
            )
        else:
            normalized.append(
                {
                    "result_kind": "UNSUPPORTED",
                    "payload": None,
                }
            )
    return normalized


def make_synthetic_repair_transport_tickets(
    *,
    repair_node: Mapping[str, Any],
    p2_response_path: str,
    p2_response_bytes: bytes,
) -> tuple[bytes, bytes]:
    """为 0 调用测试构造与某个 repair_node 对齐的合成运输票。"""

    response_sha = sha256_bytes(p2_response_bytes)
    common = {
        "node_id": repair_node["node_id"],
        "tested_lane": repair_node["tested_lane"],
        "provider": repair_node["tested_provider"],
        "model": repair_node["tested_model"],
        "request_path": repair_node["repair_request_path"],
        "request_sha256": repair_node["repair_request_sha256"],
        "response_path": p2_response_path,
        "response_sha256": response_sha,
    }
    call_attempt = {
        "schema_version": "z98-repair-call-attempt-v1",
        **common,
        "attempt_number": 1,
        "http_status": 200,
        "finish_reason": "stop",
    }
    usage = {
        "schema_version": "z98-repair-usage-v1",
        **common,
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "total_tokens": 2,
    }
    return stable_json_bytes(call_attempt), stable_json_bytes(usage)


def _positive_int(value: Any, label: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise Z98VerifierContractError(f"{label} 必须是正整数")
    return value


def _validate_graph_and_transport_binding(
    *,
    template: Mapping[str, Any],
    expected_template_sha256: str,
    repair_request_bytes: bytes,
    p2_response_path: str,
    p2_response_bytes: bytes,
    repair_node: Mapping[str, Any],
    judge_node: Mapping[str, Any],
    call_attempt_path: str,
    call_attempt_bytes: bytes,
    usage_path: str,
    usage_bytes: bytes,
) -> dict[str, Any]:
    """核死图 predecessor 与 P2 三票的跨臂身份。"""

    repair_node_id = _nonempty_string(
        repair_node.get("node_id"),
        "repair_node.node_id",
    )
    judge_node_id = _nonempty_string(
        judge_node.get("node_id"),
        "judge_node.node_id",
    )
    if repair_node.get("node_kind") != "repair":
        raise Z98VerifierContractError("predecessor 不是 repair_node")
    if judge_node.get("node_kind") != "independent_judge":
        raise Z98VerifierContractError("目标节点不是 judge_node")
    if judge_node.get("depends_on") != [repair_node_id]:
        raise Z98VerifierContractError(
            "judge_node 必须且只能绑定唯一 predecessor repair_node"
        )
    if judge_node.get("sequence") != repair_node.get("sequence") + 1:
        raise Z98VerifierContractError("judge_node 与 predecessor 顺序不相邻")
    lane = _nonempty_string(
        repair_node.get("tested_lane"),
        "repair_node.tested_lane",
    )
    tested_provider = _nonempty_string(
        repair_node.get("tested_provider"),
        "repair_node.tested_provider",
    )
    tested_model = _nonempty_string(
        repair_node.get("tested_model"),
        "repair_node.tested_model",
    )
    if judge_node.get("tested_lane_private") != lane:
        raise Z98VerifierContractError("judge_node tested lane 交叉错接")
    if judge_node.get("chapter_id") != repair_node.get("chapter_id"):
        raise Z98VerifierContractError("judge_node chapter 交叉错接")
    if (
        judge_node.get("contract_mode_private")
        != repair_node.get("contract_mode")
    ):
        raise Z98VerifierContractError("judge_node contract 交叉错接")
    if judge_node.get("judge_provider") != PROVIDER_ID:
        raise Z98VerifierContractError("judge provider 漂移")
    if judge_node.get("judge_model") != MODEL_ID:
        raise Z98VerifierContractError("judge model 漂移")
    if (
        judge_node.get("verifier_template_sha256")
        != expected_template_sha256
    ):
        raise Z98VerifierContractError("judge_node template SHA 漂移")
    template_binding = _mapping(
        template.get("private_binding"),
        "private_binding",
    )
    expected_repair_sha = _nonempty_string(
        template_binding.get("repair_request_sha256"),
        "repair_request_sha256",
    )
    actual_repair_sha = sha256_bytes(repair_request_bytes)
    if (
        repair_node.get("repair_request_path")
        != template_binding.get("repair_request_path")
        or repair_node.get("repair_request_sha256") != expected_repair_sha
        or actual_repair_sha != expected_repair_sha
    ):
        raise Z98VerifierContractError("repair_node 请求路径或 SHA 交叉错接")
    if not p2_response_path:
        raise Z98VerifierContractError("P2 raw response 路径不得为空")
    if not call_attempt_path or not usage_path:
        raise Z98VerifierContractError("call_attempt/usage 路径不得为空")
    response_sha = sha256_bytes(p2_response_bytes)

    call_attempt_raw = _strict_json_loads(
        call_attempt_bytes,
        "call_attempt",
    )
    call_attempt = _mapping(call_attempt_raw, "call_attempt")
    _strict_keys(call_attempt, _CALL_ATTEMPT_KEYS, "call_attempt")
    if call_attempt["schema_version"] != "z98-repair-call-attempt-v1":
        raise Z98VerifierContractError("call_attempt schema 非法")
    if (
        call_attempt["node_id"] != repair_node_id
        or call_attempt["tested_lane"] != lane
        or call_attempt["provider"] != tested_provider
        or call_attempt["model"] != tested_model
        or call_attempt["request_path"]
        != repair_node["repair_request_path"]
        or call_attempt["request_sha256"] != expected_repair_sha
        or call_attempt["response_path"] != p2_response_path
        or call_attempt["response_sha256"] != response_sha
    ):
        raise Z98VerifierContractError(
            "call_attempt 与 repair request/response/provider/model 不一致"
        )
    _positive_int(call_attempt["attempt_number"], "attempt_number")
    http_status = _positive_int(call_attempt["http_status"], "http_status")
    if not 200 <= http_status < 300:
        raise Z98VerifierContractError("call_attempt 不是成功 HTTP")
    if call_attempt["finish_reason"] != "stop":
        raise Z98VerifierContractError("call_attempt finish_reason 非 stop")

    usage_raw = _strict_json_loads(usage_bytes, "usage")
    usage = _mapping(usage_raw, "usage")
    _strict_keys(usage, _USAGE_KEYS, "usage")
    if usage["schema_version"] != "z98-repair-usage-v1":
        raise Z98VerifierContractError("usage schema 非法")
    if (
        usage["node_id"] != repair_node_id
        or usage["tested_lane"] != lane
        or usage["provider"] != tested_provider
        or usage["model"] != tested_model
        or usage["request_path"] != repair_node["repair_request_path"]
        or usage["request_sha256"] != expected_repair_sha
        or usage["response_path"] != p2_response_path
        or usage["response_sha256"] != response_sha
    ):
        raise Z98VerifierContractError(
            "usage 与 repair request/response/provider/model 不一致"
        )
    prompt_tokens = _positive_int(usage["prompt_tokens"], "prompt_tokens")
    completion_tokens = _positive_int(
        usage["completion_tokens"],
        "completion_tokens",
    )
    total_tokens = _positive_int(usage["total_tokens"], "total_tokens")
    if prompt_tokens + completion_tokens != total_tokens:
        raise Z98VerifierContractError("usage token 分项与总数不一致")
    return {
        "judge_node_id": judge_node_id,
        "repair_node_id": repair_node_id,
        "tested_lane": lane,
        "tested_provider": tested_provider,
        "tested_model": tested_model,
        "repair_raw_response_path": p2_response_path,
        "repair_raw_response_sha256": response_sha,
        "repair_call_attempt_path": call_attempt_path,
        "repair_call_attempt_sha256": sha256_bytes(call_attempt_bytes),
        "repair_usage_path": usage_path,
        "repair_usage_sha256": sha256_bytes(usage_bytes),
    }


def render_dynamic_verifier_request(
    template: Mapping[str, Any],
    *,
    expected_template_sha256: str,
    repair_request_bytes: bytes,
    p2_response_path: str,
    p2_response_bytes: bytes,
    repair_node: Mapping[str, Any],
    judge_node: Mapping[str, Any],
    call_attempt_path: str,
    call_attempt_bytes: bytes,
    usage_path: str,
    usage_bytes: bytes,
    actual_accumulated_tokens: int,
    actual_accumulated_micro_cny: int,
) -> dict[str, Any]:
    """P2 响应落盘后，机械渲染并绑定一份待发送裁判请求。"""

    template_bytes = stable_json_bytes(template)
    actual_template_sha = sha256_bytes(template_bytes)
    if actual_template_sha != expected_template_sha256:
        raise Z98VerifierContractError("裁判模板 SHA 漂移")
    transport_binding = _validate_graph_and_transport_binding(
        template=template,
        expected_template_sha256=expected_template_sha256,
        repair_request_bytes=repair_request_bytes,
        p2_response_path=p2_response_path,
        p2_response_bytes=p2_response_bytes,
        repair_node=repair_node,
        judge_node=judge_node,
        call_attempt_path=call_attempt_path,
        call_attempt_bytes=call_attempt_bytes,
        usage_path=usage_path,
        usage_bytes=usage_bytes,
    )
    binding = _mapping(template.get("private_binding"), "private_binding")
    expected_repair_sha = _nonempty_string(
        binding.get("repair_request_sha256"),
        "repair_request_sha256",
    )
    actual_repair_sha = sha256_bytes(repair_request_bytes)
    if actual_repair_sha != expected_repair_sha:
        raise Z98VerifierContractError("冻结 P2 请求 SHA 漂移")
    repair_request = _strict_json_loads(
        repair_request_bytes,
        "P2 请求",
    )
    p2_payload = _strict_json_loads(
        p2_response_bytes,
        "P2 响应",
    )

    mode, source_items, source_slot_ids = _source_items_from_repair_request(
        _mapping(repair_request, "repair_request")
    )
    if mode != binding.get("repair_contract_mode"):
        raise Z98VerifierContractError("P2 请求合同模式与模板绑定不一致")
    if source_slot_ids != binding.get("source_slot_ids"):
        raise Z98VerifierContractError("P2 请求 slot 顺序与模板绑定不一致")
    source_data = {
        "case_id": binding.get("case_id"),
        "items": source_items,
    }
    if sha256_bytes(stable_json_bytes(source_data)) != binding.get(
        "source_data_sha256"
    ):
        raise Z98VerifierContractError("源事件或候选锚 SHA 漂移")

    candidate_results = _normalized_candidate_results(
        mode=mode,
        p2_payload=p2_payload,
        expected_slot_ids=source_slot_ids,
    )
    item_ids = binding.get("item_ids")
    if not isinstance(item_ids, list) or len(item_ids) != len(candidate_results):
        raise Z98VerifierContractError("裁判 item 映射数量漂移")

    model_visible = deepcopy(
        _mapping(template.get("model_visible"), "model_visible")
    )
    messages = model_visible.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise Z98VerifierContractError("裁判模板 messages 结构漂移")
    user_message = _mapping(messages[1], "verifier user_message")
    user_payload = _strict_json_loads(
        _nonempty_string(user_message.get("content"), "user content"),
        "裁判模板 user content",
    )
    visible_items = user_payload.get("items")
    if not isinstance(visible_items, list):
        raise Z98VerifierContractError("裁判模板 items 非法")
    if len(visible_items) != len(candidate_results):
        raise Z98VerifierContractError("裁判模板 items 数量漂移")
    for index, result in enumerate(candidate_results):
        placeholder = visible_items[index].get("candidate_result")
        if placeholder != {"runtime_placeholder": _P2_PLACEHOLDER}:
            raise Z98VerifierContractError("P2 运行时占位符漂移")
        visible_items[index]["candidate_result"] = result
    messages[1]["content"] = stable_json_bytes(user_payload).decode("utf-8")
    leak_hits = scan_model_visible_leaks(messages)
    if leak_hits:
        raise Z98VerifierContractError(
            f"动态裁判请求命中泄漏：{leak_hits}"
        )

    request_body = {
        "model": MODEL_ID,
        "messages": messages,
        "temperature": 0.0,
        "n": 1,
        "max_completion_tokens": OUTPUT_TOKEN_LIMIT,
        "enable_thinking": False,
        "stream": False,
    }
    request_body_bytes = stable_json_bytes(request_body)
    prompt_token_projection = conservative_prompt_token_projection(messages)
    total_token_projection = prompt_token_projection + OUTPUT_TOKEN_LIMIT
    cost_projection_micro_cny = conservative_cost_cap_micro_cny(
        total_token_projection
    )
    token_gate = enforce_token_gate_before_send(
        actual_accumulated_tokens=actual_accumulated_tokens,
        next_conservative_token_projection=total_token_projection,
    )
    cost_gate = enforce_cost_gate_before_send(
        actual_accumulated_micro_cny=actual_accumulated_micro_cny,
        next_conservative_cap_micro_cny=cost_projection_micro_cny,
    )
    return {
        "schema_version": "z98-dynamic-verifier-request-v1",
        "status": "FROZEN_READY_FOR_CATALOG_PREFLIGHT_NOT_SENT",
        "transport": {
            "provider": PROVIDER_ID,
            "endpoint": "/chat/completions",
            "timeout_seconds": TIMEOUT_SECONDS,
            "api_key_env": API_KEY_ENV,
            "api_key_value_read_or_logged": False,
            "live_exact_model_catalog_check": "PENDING_BEFORE_SEND",
            "response_format": None,
        },
        "request_body": request_body,
        "budget_preflight": {
            "status": "PASS_BEFORE_SEND",
            "calculation_scope": (
                "完整动态 messages，已包含实际 P2 candidate_result"
            ),
            "message_chars": len(
                json.dumps(
                    messages,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
            "conservative_prompt_token_projection": (
                prompt_token_projection
            ),
            "max_completion_tokens": OUTPUT_TOKEN_LIMIT,
            "conservative_total_token_projection": total_token_projection,
            "conservative_cost_projection_micro_cny": (
                cost_projection_micro_cny
            ),
            "token_gate": token_gate,
            "cost_gate": cost_gate,
            "formal_account_still_only_accepts_usage": True,
        },
        "source_binding": {
            **transport_binding,
            "repair_request_sha256": actual_repair_sha,
            "p2_response_sha256": sha256_bytes(p2_response_bytes),
            "template_sha256": actual_template_sha,
            "source_data_sha256": binding["source_data_sha256"],
            "dynamic_request_body_sha256": sha256_bytes(request_body_bytes),
        },
    }


def parse_verifier_content(
    raw_content: str | bytes,
    *,
    expected_case_id: str,
    expected_item_ids: Sequence[str],
) -> dict[str, Any]:
    """严格解析裁判正文；未知字段、顺序漂移和自相矛盾都拒收。"""

    payload = _strict_json_loads(raw_content, "裁判正文")
    row = _mapping(payload, "verdict")
    _strict_keys(row, _VERDICT_TOP_KEYS, "verdict")
    if row["schema"] != "z98-independent-verdict-v1":
        raise Z98VerifierContractError("verdict.schema 非法")
    if row["case_id"] != expected_case_id:
        raise Z98VerifierContractError("case_id 与冻结模板不一致")
    items = row["items"]
    if not isinstance(items, list) or not items:
        raise Z98VerifierContractError("verdict.items 必须是非空数组")
    actual_item_ids: list[str] = []
    for index, item in enumerate(items):
        item_row = _mapping(item, f"verdict.items[{index}]")
        _strict_keys(item_row, _VERDICT_ITEM_KEYS, f"verdict.items[{index}]")
        item_id = _nonempty_string(item_row["item_id"], "item_id")
        actual_item_ids.append(item_id)
        verdict = item_row["verdict"]
        fact_support = item_row["fact_support"]
        qualifier_support = item_row["qualifier_support"]
        anchor_support = item_row["anchor_support"]
        atomicity = item_row["atomicity"]
        if verdict not in {"PASS", "REJECT"}:
            raise Z98VerifierContractError("verdict 值非法")
        if fact_support not in _FACT_SUPPORT:
            raise Z98VerifierContractError("fact_support 值非法")
        if qualifier_support not in _QUALIFIER_SUPPORT:
            raise Z98VerifierContractError("qualifier_support 值非法")
        if anchor_support not in _ANCHOR_SUPPORT:
            raise Z98VerifierContractError("anchor_support 值非法")
        if atomicity not in _ATOMICITY:
            raise Z98VerifierContractError("atomicity 值非法")
        reason_codes = _string_list(item_row["reason_codes"], "reason_codes")
        if not set(reason_codes) <= _REASON_CODES:
            raise Z98VerifierContractError("reason_codes 含非法值")
        pass_conditions = (
            fact_support == "SUPPORTED"
            and qualifier_support in {"COMPLETE", "NOT_APPLICABLE"}
            and anchor_support == "FULL"
            and atomicity == "ATOMIC"
        )
        if verdict == "PASS":
            if not pass_conditions or reason_codes != ["NONE"]:
                raise Z98VerifierContractError("PASS 判词与分项状态矛盾")
        elif "NONE" in reason_codes or pass_conditions:
            raise Z98VerifierContractError("REJECT 判词与分项状态矛盾")
    if actual_item_ids != list(expected_item_ids):
        raise Z98VerifierContractError("裁判 item 数量、顺序或身份漂移")
    receipt = _mapping(row["receipt"], "verdict.receipt")
    _strict_keys(receipt, _VERDICT_RECEIPT_KEYS, "verdict.receipt")
    returned = _string_list(
        receipt["returned_item_ids"],
        "returned_item_ids",
    )
    if returned != list(expected_item_ids):
        raise Z98VerifierContractError("receipt item 顺序漂移")
    return dict(row)

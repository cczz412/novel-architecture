"""第98道裁判冻结件的预算可执行性与盲判侧信道审计。

这里只读已经封存的千问实账和本轮模板，不访问网络，也不把经验估算
冒充精确 tokenizer 结果。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from .core import (
    Z98VerifierContractError,
    conservative_prompt_token_projection,
    sha256_bytes,
)


_CALIBRATION_SOURCES = (
    {
        "run_id": (
            "MB_X01_C0003_qianwen_qwen3.7-plus_structured_r05_20260723"
        ),
        "request_path": (
            "experiments/model_benchmarks/"
            "MB_X01_C0003_qianwen_qwen3.7-plus_structured_r05_20260723/"
            "prepared/request_body.json"
        ),
        "request_sha256": (
            "5e8c9079aae0b648fde5fdbed287c7343dbfd49f26a182727a71302e8efd2f07"
        ),
        "usage_path": (
            "experiments/model_benchmarks/"
            "MB_X01_C0003_qianwen_qwen3.7-plus_structured_r05_20260723/"
            "transport/usage.jsonl"
        ),
        "usage_sha256": (
            "ce37b48588fff67398a63aa5155ad166e6866c0058cfa2f5c166d2f28de6d409"
        ),
    },
    {
        "run_id": (
            "MB_X01_C0003_qianwen_qwen3.7-plus_thinking32k_t02_r06_20260723"
        ),
        "request_path": (
            "experiments/model_benchmarks/"
            "MB_X01_C0003_qianwen_qwen3.7-plus_thinking32k_t02_r06_20260723/"
            "prepared/request_body.json"
        ),
        "request_sha256": (
            "993dca0da61048a50097e09e53375f6bc8ccde11ef261762091bf0d7817e8ca5"
        ),
        "usage_path": (
            "experiments/model_benchmarks/"
            "MB_X01_C0003_qianwen_qwen3.7-plus_thinking32k_t02_r06_20260723/"
            "transport/usage.jsonl"
        ),
        "usage_sha256": (
            "66f03b9b34bc6eb9eeba37a5c06b90d8804e13aa9211380de269d26054296cbb"
        ),
    },
)


def _compact_message_char_count(messages: Any) -> int:
    encoded = json.dumps(
        messages,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return len(encoded)


def _read_one_jsonl(path: Path) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise Z98VerifierContractError(
            f"经验标定 usage 必须且只能有一行：{path}"
        )
    return rows[0]


def _load_calibrations(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in _CALIBRATION_SOURCES:
        request_path = repo_root / source["request_path"]
        usage_path = repo_root / source["usage_path"]
        request_bytes = request_path.read_bytes()
        usage_bytes = usage_path.read_bytes()
        if sha256_bytes(request_bytes) != source["request_sha256"]:
            raise Z98VerifierContractError("千问经验标定请求 SHA 漂移")
        if sha256_bytes(usage_bytes) != source["usage_sha256"]:
            raise Z98VerifierContractError("千问经验标定 usage SHA 漂移")
        request = json.loads(request_bytes)
        usage_row = _read_one_jsonl(usage_path)
        prompt_tokens = usage_row.get("usage", {}).get("prompt_tokens")
        if not isinstance(prompt_tokens, int) or prompt_tokens <= 0:
            raise Z98VerifierContractError("千问经验标定缺 prompt_tokens")
        message_chars = _compact_message_char_count(
            request.get("messages")
        )
        if message_chars <= 0:
            raise Z98VerifierContractError("千问经验标定 messages 为空")
        rows.append(
            {
                **source,
                "model_id": request.get("model"),
                "message_chars": message_chars,
                "prompt_tokens": prompt_tokens,
                "tokens_per_million_message_chars_floor": (
                    prompt_tokens * 1_000_000 // message_chars
                ),
            }
        )
    return rows


def build_feasibility_receipt(
    *,
    repo_root: Path,
    templates: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """用封存实账审计预算，并记录单条/批式结构侧信道。"""

    calibration_rows = _load_calibrations(repo_root)
    min_calibration = min(
        calibration_rows,
        key=lambda row: row["prompt_tokens"] / row["message_chars"],
    )
    max_calibration = max(
        calibration_rows,
        key=lambda row: row["prompt_tokens"] / row["message_chars"],
    )

    template_rows: list[dict[str, Any]] = []
    mode_item_counts: dict[str, set[int]] = {}
    for template_path, template in sorted(templates.items()):
        binding = template.get("private_binding")
        visible = template.get("model_visible")
        if not isinstance(binding, Mapping) or not isinstance(
            visible,
            Mapping,
        ):
            raise Z98VerifierContractError("裁判模板结构非法")
        mode = binding.get("repair_contract_mode")
        item_ids = binding.get("item_ids")
        token_cap = binding.get("verification_token_cap")
        if (
            not isinstance(mode, str)
            or not isinstance(item_ids, list)
            or not item_ids
            or not isinstance(token_cap, int)
            or token_cap <= 0
        ):
            raise Z98VerifierContractError("裁判模板私有绑定非法")
        message_chars = _compact_message_char_count(
            visible.get("messages")
        )
        projected_min = math.ceil(
            message_chars
            * min_calibration["prompt_tokens"]
            / min_calibration["message_chars"]
        )
        projected_max = math.ceil(
            message_chars
            * max_calibration["prompt_tokens"]
            / max_calibration["message_chars"]
        )
        conservative_projection = math.ceil(
            message_chars
            * max_calibration["prompt_tokens"]
            * 5
            / (max_calibration["message_chars"] * 4)
        )
        frozen_projection = conservative_prompt_token_projection(
            visible.get("messages")
        )
        if conservative_projection != frozen_projection:
            raise Z98VerifierContractError("Qwen 保守输入投影规则漂移")
        item_count = len(item_ids)
        mode_item_counts.setdefault(mode, set()).add(item_count)
        template_rows.append(
            {
                "template_path": template_path,
                "template_id": template.get("template_id"),
                "contract_mode_private": mode,
                "item_count_visible": item_count,
                "message_chars_before_candidate_result": message_chars,
                "verification_total_token_cap": token_cap,
                "empirical_prompt_projection_min": projected_min,
                "empirical_prompt_projection_max": projected_max,
                "conservative_projection_1_25x": (
                    conservative_projection
                ),
                "projected_input_alone_exceeds_total_cap": (
                    projected_min > token_cap
                ),
            }
        )

    projected_over_count = sum(
        bool(row["projected_input_alone_exceeds_total_cap"])
        for row in template_rows
    )
    single_counts = sorted(mode_item_counts.get("single_patch", set()))
    batch_counts = sorted(mode_item_counts.get("atom_batch_v2", set()))
    structural_identity_inferable = (
        bool(single_counts)
        and bool(batch_counts)
        and set(single_counts).isdisjoint(batch_counts)
    )
    authorized_round_token_cap = 500_000
    conservative_two_lane_tokens = 2 * sum(
        int(row["conservative_projection_1_25x"]) + 4_000
        for row in template_rows
    )
    conservative_two_lane_cost_micro_cny = (
        conservative_two_lane_tokens * 36
    )
    if conservative_two_lane_tokens > authorized_round_token_cap:
        raise Z98VerifierContractError("CZ 直批 50 万 token 总帽不足")
    if conservative_two_lane_cost_micro_cny > 10_000_000:
        raise Z98VerifierContractError("裁判保守金额投影超过 10 元")
    return {
        "schema_version": "z98-verifier-feasibility-audit-v1",
        "status": (
            "PASS_WITH_RUNTIME_BUDGET_GATE_AND_DECLARED_"
            "CARDINALITY_LIMITATION"
        ),
        "hard_stop_reasons": [],
        "exact_qwen3_7_max_tokenizer": {
            "status": "NOT_AVAILABLE_IN_REPO",
            "consequence": (
                "经验投影只作发网前风险闸，不冒充精确 tokenizer 真值"
            ),
        },
        "calibration": {
            "scope": (
                "仓内两次封存 Qwen3.7 Plus 实账；与 Max 同系列但非同一型号"
            ),
            "use_boundary": (
                "只证明当前无法机械确认不超帽；不作正式 token 结算"
            ),
            "sources": calibration_rows,
            "minimum_observed_ratio_source": min_calibration["run_id"],
            "maximum_observed_ratio_source": max_calibration["run_id"],
        },
        "budget_audit": {
            "template_count": len(template_rows),
            "candidate_result_inserted": False,
            "projected_input_over_total_cap_count": projected_over_count,
            "all_templates_projected_over_total_cap": (
                projected_over_count == len(template_rows)
            ),
            "templates": template_rows,
            "legacy_pre_registered_per_request_caps": {
                "status": "SUPERSEDED_AS_SEND_BLOCKER_BY_CZ_DIRECT_ALLOWANCE",
                "still_reported_for_experiment_variance": True,
                "projected_over_cap_count": projected_over_count,
            },
            "cz_direct_round_allowance": {
                "source": (
                    "CZ 当前对话直令：Qwen3.7 Max 有50万 tokens额度，"
                    "所以先放心测"
                ),
                "total_token_cap": authorized_round_token_cap,
                "static_before_candidate_two_lane_token_projection": (
                    conservative_two_lane_tokens
                ),
                "static_before_candidate_two_lane_cost_micro_cny": (
                    conservative_two_lane_cost_micro_cny
                ),
                "cost_cap_micro_cny": 10_000_000,
                "static_projection_within_token_cap": True,
                "static_projection_within_cost_cap": True,
                "full_round_completion_guaranteed": False,
                "runtime_dynamic_request_gate_required": True,
                "runtime_rule": (
                    "实际 P2 结果插入后，按完整动态 messages 重算输入投影，"
                    "再把4k输出上限计入50万token与10元双闸"
                ),
                "formal_account_still_only_accepts_usage": True,
            },
            "formal_usage_status": "UNMEASURED_ZERO_CALL",
        },
        "identity_blindness_audit": {
            "explicit_labels_hidden": True,
            "single_item_counts": single_counts,
            "batch_item_counts": batch_counts,
            "structural_identity_inferable": structural_identity_inferable,
            "classification": (
                "KNOWN_CARDINALITY_SIDE_CHANNEL_NOT_EXPLICIT_IDENTITY_LABEL"
            ),
            "blocking": False,
            "boundary": (
                "裁判看不到平台、臂名或合同名；可从 items 数量猜测分组规模，"
                "该限制单列，不冒充完全统计盲化"
            ),
        },
        "model_api_calls": 0,
        "provider_catalog_requests": 0,
        "network_attempts": 0,
        "usage_tokens": 0,
    }

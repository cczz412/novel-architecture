"""第98道独立核验冻结包生成器（0 调用、0 网络）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import (
    API_KEY_ENV,
    MODEL_FAMILY,
    MODEL_ID,
    INPUT_PRICE_CNY_PER_MILLION_TOKENS,
    OUTPUT_TOKEN_LIMIT,
    OUTPUT_PRICE_CNY_PER_MILLION_TOKENS,
    PROVIDER_ID,
    TESTED_MODEL_FAMILY,
    TIMEOUT_SECONDS,
    TOTAL_COST_CAP_CNY,
    TOTAL_COST_CAP_MICRO_CNY,
    TOTAL_TOKEN_CAP,
    Z98VerifierContractError,
    _strict_json_loads,
    conservative_cost_cap_micro_cny,
    make_synthetic_repair_transport_tickets,
    make_verifier_template,
    parse_verifier_content,
    render_dynamic_verifier_request,
    scan_model_visible_leaks,
    sha256_bytes,
    stable_json_bytes,
)
from .feasibility import build_feasibility_receipt


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
STEP1_ROOT_REL = "runs/Z98_刀A小额补丁实验_步一备料_v1.0_20260724"
STEP1_MANIFEST_REL = f"{STEP1_ROOT_REL}/bundle_manifest.json"
STEP1_MANIFEST_SHA256 = (
    "cc531aae0aed79af1cc2811ec4af41aa214f24738271db98b2888d5b9e43ee20"
)
STEP1_BUDGET_REL = f"{STEP1_ROOT_REL}/receipts/budget_receipt.json"
STEP1_BUDGET_SHA256 = (
    "8bab43e27d3f062958cfed88ebc79959dd472cedd5b8fcb277d2e4bf0b85f03c"
)
STEP1_REQUEST_AUTHORITY_AGGREGATE_SHA256 = (
    "d10179c500d98e79adb90c98fe4b7c571c18c191ab4da322cf610d04db90bb70"
)
QIANWEN_CONFIG_REL = "config/providers/qianwen_platform_multi_model.json"
VERDICT_SCHEMA_PATH = (
    PACKAGE_ROOT / "contracts/z98_independent_verdict_v1.schema.json"
)
JUDGE_AUTHORITY_PATH = PACKAGE_ROOT / "design/judge_authority_contract.json"
CHAPTER_ORDER = ("ch0003", "ch0013", "ch0019")
LANES: tuple[dict[str, str], ...] = (
    {
        "lane_id": "flash",
        "provider": "sensenova",
        "model": "deepseek-v4-flash",
    },
    {
        "lane_id": "pro",
        "provider": "tencent_tokenhub",
        "model": "deepseek-v4-pro-202606",
    },
)


def _load_json_bytes(path: Path) -> tuple[Any, bytes]:
    data = path.read_bytes()
    return json.loads(data), data


def _verify_sha(data: bytes, expected: str, label: str) -> None:
    actual = sha256_bytes(data)
    if actual != expected:
        raise Z98VerifierContractError(
            f"{label} SHA 漂移：expected={expected}, actual={actual}"
        )


def _manifest_index(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise Z98VerifierContractError("步一 manifest.files 非法")
    index: dict[str, dict[str, Any]] = {}
    for row in files:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise Z98VerifierContractError("步一 manifest 文件行非法")
        path = str(row["path"])
        if path in index:
            raise Z98VerifierContractError("步一 manifest 路径重复")
        index[path] = row
    return index


def _request_paths(manifest_index: dict[str, dict[str, Any]]) -> list[str]:
    requests = sorted(
        path
        for path in manifest_index
        if path.startswith("requests/") and path.endswith(".json")
    )
    if len(requests) != 17:
        raise Z98VerifierContractError(
            f"冻结 P2 请求数量漂移：expected=17, actual={len(requests)}"
        )
    return requests


def _recompute_authority_request_listing(
    repository: Path,
    request_paths: list[str],
) -> dict[str, Any]:
    """按权威算法复算 d101 请求集合清单。"""

    full_paths = sorted(
        f"{STEP1_ROOT_REL}/{request_path}" for request_path in request_paths
    )
    rows: list[dict[str, Any]] = []
    lines: list[str] = []
    for line_number, repo_relative_path in enumerate(full_paths, start=1):
        data = (repository / repo_relative_path).read_bytes()
        file_sha = sha256_bytes(data)
        line = f"{file_sha}  {repo_relative_path}\n"
        lines.append(line)
        rows.append(
            {
                "line_number": line_number,
                "path": repo_relative_path,
                "sha256": file_sha,
                "listing_line": line,
            }
        )
    listing_bytes = "".join(lines).encode("utf-8")
    actual = sha256_bytes(listing_bytes)
    if actual != STEP1_REQUEST_AUTHORITY_AGGREGATE_SHA256:
        raise Z98VerifierContractError(
            "冻结 P2 请求权威集合 SHA 复算不等于 d101，硬停"
        )
    return {
        "listing_rule": (
            "按 repo-relative 全路径 UTF-8 字典序排序；每行"
            "`sha256␠␠path\\n`；对整份 UTF-8 清单取 SHA-256"
        ),
        "listing_line_count": len(rows),
        "listing_byte_count": len(listing_bytes),
        "listing_rows": rows,
        "recomputed_aggregate_listing_sha256": actual,
        "authority_aggregate_listing_sha256": (
            STEP1_REQUEST_AUTHORITY_AGGREGATE_SHA256
        ),
        "matches_authority": True,
    }


def _budget_maps(
    budget: dict[str, Any],
    request_paths: list[str],
) -> tuple[dict[str, int], dict[str, int]]:
    p2_caps: dict[str, int] = {}
    verification_caps: dict[str, int] = {}
    chapters = budget.get("chapters")
    if not isinstance(chapters, list):
        raise Z98VerifierContractError("步一预算章节表非法")
    by_chapter = {
        str(row["chapter_id"]): row
        for row in chapters
        if isinstance(row, dict) and "chapter_id" in row
    }
    if set(by_chapter) != set(CHAPTER_ORDER):
        raise Z98VerifierContractError("步一预算章节集合漂移")
    for chapter_id in CHAPTER_ORDER:
        row = by_chapter[chapter_id]
        modes = row.get("contract_modes")
        if not isinstance(modes, dict):
            raise Z98VerifierContractError("步一预算合同模式表非法")
        single_paths = sorted(
            path
            for path in request_paths
            if path.startswith(f"requests/single/{chapter_id}/")
        )
        batch_paths = sorted(
            path
            for path in request_paths
            if path.startswith(f"requests/atom_batch_v2/{chapter_id}/")
        )
        if len(batch_paths) != 1:
            raise Z98VerifierContractError(f"{chapter_id} 批式请求数量漂移")
        for mode_name, paths in (
            ("single_patch", single_paths),
            ("atom_batch_v2", batch_paths),
        ):
            mode = modes.get(mode_name)
            if not isinstance(mode, dict):
                raise Z98VerifierContractError(
                    f"{chapter_id}/{mode_name} 预算缺失"
                )
            p2_list = mode.get("p2_per_request_token_caps")
            verification_list = mode.get(
                "verification_per_request_token_caps"
            )
            if (
                not isinstance(p2_list, list)
                or not isinstance(verification_list, list)
                or len(p2_list) != len(paths)
                or len(verification_list) != len(paths)
            ):
                raise Z98VerifierContractError(
                    f"{chapter_id}/{mode_name} 逐请求预算数量漂移"
                )
            for path, p2_cap, verification_cap in zip(
                paths,
                p2_list,
                verification_list,
                strict=True,
            ):
                if (
                    not isinstance(p2_cap, int)
                    or p2_cap <= 0
                    or not isinstance(verification_cap, int)
                    or verification_cap <= 0
                ):
                    raise Z98VerifierContractError("逐请求 token 帽非法")
                p2_caps[path] = p2_cap
                verification_caps[path] = verification_cap
    if set(p2_caps) != set(request_paths):
        raise Z98VerifierContractError("P2 预算未覆盖全部请求")
    if set(verification_caps) != set(request_paths):
        raise Z98VerifierContractError("核验预算未覆盖全部请求")
    return p2_caps, verification_caps


def _stable_request_order(request_paths: list[str]) -> list[str]:
    ordered: list[str] = []
    for chapter_id in CHAPTER_ORDER:
        ordered.extend(
            sorted(
                path
                for path in request_paths
                if path.startswith(f"requests/single/{chapter_id}/")
            )
        )
        ordered.extend(
            sorted(
                path
                for path in request_paths
                if path.startswith(
                    f"requests/atom_batch_v2/{chapter_id}/"
                )
            )
        )
    if sorted(ordered) != sorted(request_paths):
        raise Z98VerifierContractError("请求固定顺序遗漏或重复")
    return ordered


def _verify_qianwen_local_config(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / QIANWEN_CONFIG_REL
    config, raw = _load_json_bytes(config_path)
    if config.get("provider") != PROVIDER_ID:
        raise Z98VerifierContractError("千问 provider 身份漂移")
    if config.get("api_key_env") != API_KEY_ENV:
        raise Z98VerifierContractError("千问密钥环境变量名漂移")
    models = config.get("models")
    if not isinstance(models, list):
        raise Z98VerifierContractError("千问模型登记表非法")
    alias_rows = [
        row
        for row in models
        if isinstance(row, dict) and row.get("model_id") == "qwen3.7-max"
    ]
    if len(alias_rows) != 1 or alias_rows[0].get("call_ready") is not True:
        raise Z98VerifierContractError("本地 Qwen3.7 Max 基础通道未登记可用")
    snapshot_rows = [
        row
        for row in models
        if isinstance(row, dict) and row.get("model_id") == MODEL_ID
    ]
    if len(snapshot_rows) != 1:
        raise Z98VerifierContractError("固定文本快照必须且只能登记一条")
    snapshot = snapshot_rows[0]
    required_snapshot_fields = {
        "call_ready": True,
        "fixed_snapshot": True,
        "structured_output": False,
        "live_catalog_check_required_before_run": True,
    }
    if any(
        snapshot.get(field) is not expected
        for field, expected in required_snapshot_fields.items()
    ):
        raise Z98VerifierContractError("固定文本快照能力边界登记漂移")
    return {
        "path": QIANWEN_CONFIG_REL,
        "sha256": sha256_bytes(raw),
        "provider": config["provider"],
        "api_key_env": config["api_key_env"],
        "configured_alias": "qwen3.7-max",
        "authority_exact_model_id": MODEL_ID,
        "fixed_snapshot": True,
        "structured_output": False,
        "exact_model_live_catalog_status": "PENDING_BEFORE_NETWORK_RELEASE",
        "model_api_calls": 0,
        "provider_catalog_requests": 0,
        "network_attempts": 0,
        "secret_value_read_or_logged": False,
    }


def _execution_sequence(
    mappings: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    previous_node_id: str | None = None
    sequence = 0
    for lane in LANES:
        for mapping in mappings:
            sequence += 1
            repair_node_id = f"NODE-{sequence:03d}-REPAIR"
            repair_node = {
                "sequence": sequence,
                "node_id": repair_node_id,
                "node_kind": "repair",
                "status": "FROZEN_NOT_SENT",
                "depends_on": [previous_node_id] if previous_node_id else [],
                "tested_lane": lane["lane_id"],
                "tested_provider": lane["provider"],
                "tested_model": lane["model"],
                "chapter_id": mapping["chapter_id"],
                "contract_mode": mapping["contract_mode"],
                "repair_request_path": mapping["repair_request_path"],
                "repair_request_sha256": mapping["repair_request_sha256"],
                "token_cap": mapping["p2_token_cap"],
            }
            nodes.append(repair_node)
            previous_node_id = repair_node_id
            sequence += 1
            judge_node_id = f"NODE-{sequence:03d}-JUDGE"
            static_total_tokens = int(
                mapping["static_before_candidate_total_token_projection"]
            )
            conservative_cost = conservative_cost_cap_micro_cny(
                static_total_tokens
            )
            judge_node = {
                "sequence": sequence,
                "node_id": judge_node_id,
                "node_kind": "independent_judge",
                "status": "FROZEN_WAITING_P2_RESPONSE",
                "depends_on": [repair_node_id],
                "tested_lane_private": lane["lane_id"],
                "chapter_id": mapping["chapter_id"],
                "contract_mode_private": mapping["contract_mode"],
                "verifier_template_path": mapping["verifier_template_path"],
                "verifier_template_sha256": mapping[
                    "verifier_template_sha256"
                ],
                "judge_provider": PROVIDER_ID,
                "judge_model": MODEL_ID,
                "legacy_verification_token_cap": mapping[
                    "verification_token_cap"
                ],
                "static_before_candidate_prompt_token_projection": mapping[
                    "static_before_candidate_prompt_token_projection"
                ],
                "max_completion_tokens": OUTPUT_TOKEN_LIMIT,
                "static_before_candidate_total_token_projection": (
                    static_total_tokens
                ),
                "round_token_cap": TOTAL_TOKEN_CAP,
                "cost_cap_cny_shared_round": TOTAL_COST_CAP_CNY,
                "static_before_candidate_cost_projection_micro_cny": (
                    conservative_cost
                ),
                "runtime_budget_rule": (
                    "P2结果落盘并插入完整动态messages后重算；"
                    "静态投影不得充当发送闸"
                ),
                "send_preflight_token_gate": (
                    "actual_accumulated_tokens + "
                    "next_conservative_token_projection <= 500000"
                ),
                "send_preflight_cost_gate": (
                    "actual_accumulated_micro_cny + "
                    "next_conservative_cap_micro_cny <= 10000000"
                ),
                "dynamic_request_sha_status": "PENDING_P2_RESPONSE",
            }
            nodes.append(judge_node)
            previous_node_id = judge_node_id
    if sequence != 68 or len(nodes) != 68:
        raise Z98VerifierContractError("68 节点执行序列数量漂移")
    return {
        "schema_version": "z98-execution-sequence-68-v1",
        "status": "FROZEN_NOT_SENT",
        "total_nodes": 68,
        "repair_nodes": 34,
        "independent_judge_nodes": 34,
        "tested_lane_order": [lane["lane_id"] for lane in LANES],
        "judge_lane": {
            "provider": PROVIDER_ID,
            "model": MODEL_ID,
            "family": MODEL_FAMILY,
            "live_catalog_check": "PENDING_BEFORE_NETWORK_RELEASE",
        },
        "nodes": nodes,
    }


def _dynamic_binding_rule() -> dict[str, Any]:
    return {
        "schema_version": "z98-dynamic-request-binding-rule-v1",
        "status": "FROZEN",
        "render_time": "after_p2_raw_response_is_fsynced_before_judge_send",
        "required_sha_bindings": [
            "repair_request_sha256",
            "p2_response_sha256",
            "repair_raw_response_sha256",
            "repair_call_attempt_sha256",
            "repair_usage_sha256",
            "template_sha256",
            "source_data_sha256",
            "dynamic_request_body_sha256",
        ],
        "renderer": (
            "experiments.Z98_independent_verifier_freeze_20260724.core."
            "render_dynamic_verifier_request"
        ),
        "requirements": [
            "P2 响应须先按对应冻结合同严格解析。",
            "冻结 P2 请求、模板或源事件与候选锚任一 SHA 漂移即拒绝。",
            (
                "judge_node 必须且只能绑定唯一 predecessor repair_node；"
                "三票的 lane/provider/model/request/response 必须与该 repair_node 一致。"
            ),
            (
                "raw response、call_attempt、usage 路径与文件 SHA 全部进入"
                "动态请求 source_binding。"
            ),
            "单条与批式结果机械归一成同一种裁判 items 结构。",
            "动态可见面再次做身份与答案面泄漏扫描。",
            "发送前落 dynamic_request_body_sha256；不得先发后补。",
            (
                "实际 P2 结果插入完整动态 messages 后，必须重新估算本次"
                "输入与4k输出合计，再过50万token和10元双闸；"
                "静态模板投影不得直接放行。"
            ),
        ],
        "live_catalog_gate": {
            "exact_model_id": MODEL_ID,
            "status": "PENDING_BEFORE_NETWORK_RELEASE",
            "failure_action": "HARD_STOP_NO_ALIAS_NO_FAILOVER",
        },
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def _graph_transport_binding_preflight(
    execution: dict[str, Any],
) -> dict[str, Any]:
    nodes = execution["nodes"]
    by_id = {str(node["node_id"]): node for node in nodes}
    if len(by_id) != 68:
        raise Z98VerifierContractError("68 图 node_id 不唯一")
    rows: list[dict[str, Any]] = []
    for judge in nodes:
        if judge["node_kind"] != "independent_judge":
            continue
        depends_on = judge.get("depends_on")
        if not isinstance(depends_on, list) or len(depends_on) != 1:
            raise Z98VerifierContractError("judge predecessor 不是唯一值")
        repair = by_id.get(str(depends_on[0]))
        if repair is None or repair.get("node_kind") != "repair":
            raise Z98VerifierContractError("judge predecessor 不是 repair_node")
        if judge["sequence"] != repair["sequence"] + 1:
            raise Z98VerifierContractError("judge 与 repair 顺序不相邻")
        if (
            judge["tested_lane_private"] != repair["tested_lane"]
            or judge["chapter_id"] != repair["chapter_id"]
            or judge["contract_mode_private"] != repair["contract_mode"]
        ):
            raise Z98VerifierContractError("judge 与 repair 私有身份错接")
        runtime_root = f"runtime/{repair['node_id']}"
        rows.append(
            {
                "judge_node_id": judge["node_id"],
                "predecessor_repair_node_id": repair["node_id"],
                "tested_lane_private": repair["tested_lane"],
                "tested_provider_private": repair["tested_provider"],
                "tested_model_private": repair["tested_model"],
                "repair_request_path": repair["repair_request_path"],
                "repair_request_sha256": repair["repair_request_sha256"],
                "expected_runtime_ticket_paths": {
                    "raw_response": f"{runtime_root}/raw_response.json",
                    "call_attempt": f"{runtime_root}/call_attempt.json",
                    "usage": f"{runtime_root}/usage.json",
                },
                "runtime_ticket_status": "PENDING_REPAIR_CALL",
            }
        )
    if len(rows) != 34:
        raise Z98VerifierContractError("图运输绑定应有 34 行")
    return {
        "schema_version": "z98-graph-transport-binding-preflight-v1",
        "status": "PASS_ZERO_CALL_GRAPH_FROZEN",
        "binding_count": len(rows),
        "unique_judge_nodes": len({row["judge_node_id"] for row in rows}),
        "unique_predecessor_repair_nodes": len(
            {row["predecessor_repair_node_id"] for row in rows}
        ),
        "ticket_contract": {
            "raw_response": "路径＋文件SHA＋响应内容",
            "call_attempt": (
                "路径＋文件SHA＋lane/provider/model/request/response/HTTP字段"
            ),
            "usage": (
                "路径＋文件SHA＋lane/provider/model/request/response/token字段"
            ),
        },
        "bindings": rows,
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def _run_canaries(
    *,
    mappings: list[dict[str, Any]],
    templates: dict[str, dict[str, Any]],
    execution: dict[str, Any],
    authority: dict[str, Any],
) -> dict[str, Any]:
    visible_values = [
        template["model_visible"] for template in templates.values()
    ]
    leak_hits = scan_model_visible_leaks(visible_values)
    request_profile = authority["request_profile"]
    cases = [
        {
            "case": "template_count_17",
            "pass": len(mappings) == 17 and len(templates) == 17,
        },
        {
            "case": "execution_nodes_68",
            "pass": (
                execution["total_nodes"] == 68
                and execution["repair_nodes"] == 34
                and execution["independent_judge_nodes"] == 34
            ),
        },
        {
            "case": "model_visible_leak_zero",
            "pass": not leak_hits,
            "hits": leak_hits,
        },
        {
            "case": "cross_family_judge",
            "pass": MODEL_FAMILY != TESTED_MODEL_FAMILY,
        },
        {
            "case": "provider_profile_frozen",
            "pass": (
                authority["provider"]["provider_id"] == PROVIDER_ID
                and authority["provider"]["exact_model_id"] == MODEL_ID
                and authority["provider"]["api_key_env"] == API_KEY_ENV
            ),
        },
        {
            "case": "request_parameters_frozen",
            "pass": (
                request_profile["temperature"] == 0.0
                and request_profile["n"] == 1
                and request_profile["max_completion_tokens"]
                == OUTPUT_TOKEN_LIMIT
                and request_profile["timeout_seconds"] == TIMEOUT_SECONDS
                and request_profile["direct_http_body_enable_thinking"]
                is False
                and request_profile["response_format"] is None
            ),
        },
        {
            "case": "cost_cap_cny_10",
            "pass": authority["budget"]["total_cost_cap_cny"]
            == TOTAL_COST_CAP_CNY,
        },
        {
            "case": "cz_round_token_cap_500k",
            "pass": authority["budget"][
                "cz_direct_round_token_allowance"
            ]
            == TOTAL_TOKEN_CAP,
        },
    ]
    return {
        "schema_version": "z98-verifier-freeze-canary-v1",
        "status": "PASS" if all(row["pass"] for row in cases) else "FAIL",
        "cases": cases,
    }


def _strict_parser_reject_preflight(
    repository: Path,
) -> dict[str, Any]:
    """把严格 JSON 与合同外字段拒收结果单独落票。"""

    reject_cases = {
        "duplicate_key_top_level": '{"a":1,"a":2}',
        "duplicate_key_nested_single_patch": (
            '{"event":{"actor":"甲","actor":"乙"}}'
        ),
        "duplicate_key_nested_atom_batch_v2": (
            '{"patches":[{"slot_id":"S1","slot_id":"S2"}]}'
        ),
        "nonstandard_nan": '{"score":NaN}',
        "nonstandard_infinity": '{"score":Infinity}',
    }
    cases: list[dict[str, Any]] = []
    for name, raw in reject_cases.items():
        rejected = False
        try:
            _strict_json_loads(raw, name)
        except Z98VerifierContractError:
            rejected = True
        cases.append(
            {
                "case": name,
                "expected": "REJECT",
                "observed": "REJECT" if rejected else "ACCEPT",
                "pass": rejected,
            }
        )

    unknown_field = stable_json_bytes(
        {
            "schema": "z98-independent-verdict-v1",
            "case_id": "CANARY",
            "items": [],
            "receipt": {"returned_item_ids": []},
            "unexpected": True,
        }
    )
    unknown_rejected = False
    try:
        parse_verifier_content(
            unknown_field,
            expected_case_id="CANARY",
            expected_item_ids=[],
        )
    except Z98VerifierContractError:
        unknown_rejected = True
    cases.append(
        {
            "case": "verdict_unknown_top_level_field",
            "expected": "REJECT",
            "observed": "REJECT" if unknown_rejected else "ACCEPT",
            "pass": unknown_rejected,
        }
    )

    well_formed = _strict_json_loads(
        '{"event":{"actor":"甲","action":"记录"}}',
        "well_formed_json",
    )
    cases.append(
        {
            "case": "well_formed_json_control",
            "expected": "ACCEPT",
            "observed": "ACCEPT" if isinstance(well_formed, dict) else "REJECT",
            "pass": isinstance(well_formed, dict),
        }
    )
    source_paths = [
        (
            "experiments/Z98_independent_verifier_freeze_20260724/"
            "core.py"
        ),
        "tests/test_z98_independent_verifier_freeze.py",
    ]
    source_rows = [
        {
            "path": path,
            "sha256": sha256_bytes((repository / path).read_bytes()),
        }
        for path in source_paths
    ]
    return {
        "schema_version": "z98-strict-parser-reject-preflight-v1",
        "status": "PASS" if all(row["pass"] for row in cases) else "FAIL",
        "cases": cases,
        "source_files": source_rows,
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def _synthetic_patch(source: dict[str, Any]) -> dict[str, Any]:
    """构造只用于 0 调用机械预演的合规修复对象。"""

    span_ids = source.get("source_span_ids")
    if not isinstance(span_ids, list) or not span_ids:
        raise Z98VerifierContractError("预算预演源条目缺 source_span_ids")
    source_event_id = source.get("source_event_id")
    if not isinstance(source_event_id, str) or not source_event_id:
        raise Z98VerifierContractError("预算预演源条目缺 source_event_id")
    return {
        "op": "KEEP",
        "target_event_ids": [source_event_id],
        "source_span_ids": [span_ids[0]],
        "actor": "预算预演主体",
        "predicate": "核对",
        "object_or_result": "预算预演事实",
        "hard_qualifiers": [],
        "fact_class": "event",
        "speaker": None,
        "anchor_candidates": [span_ids[0]],
    }


def _synthetic_p2_response(
    repair_request_bytes: bytes,
) -> bytes:
    """从冻结修复请求机械构造合规 P2 响应，不调用模型。"""

    request = _strict_json_loads(
        repair_request_bytes,
        "预算预演修复请求",
    )
    model_visible = request.get("model_visible")
    if not isinstance(model_visible, dict):
        raise Z98VerifierContractError("预算预演修复请求缺 model_visible")
    messages = model_visible.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise Z98VerifierContractError("预算预演修复请求 messages 非法")
    user_message = messages[1]
    if not isinstance(user_message, dict):
        raise Z98VerifierContractError("预算预演 user message 非法")
    payload = _strict_json_loads(
        user_message.get("content"),
        "预算预演修复请求 user content",
    )
    if not isinstance(payload, dict):
        raise Z98VerifierContractError("预算预演修复请求正文非法")
    mode = request.get("contract_mode")
    if mode == "single_patch":
        source = payload.get("input")
        if not isinstance(source, dict):
            raise Z98VerifierContractError("预算预演单条输入非法")
        return json.dumps(
            _synthetic_patch(source),
            ensure_ascii=False,
        ).encode("utf-8")
    if mode != "atom_batch_v2":
        raise Z98VerifierContractError("预算预演合同模式非法")
    slots = payload.get("slots")
    if not isinstance(slots, list) or not slots:
        raise Z98VerifierContractError("预算预演批式 slots 非法")
    response = {
        "schema": "atom-batch-v2",
        "request_id": request.get("request_id"),
        "items": [
            {
                "slot_id": slot["slot_id"],
                "status": "ok",
                "atom": _synthetic_patch(slot),
                "split_span_ids": [],
                "missing_context_codes": [],
            }
            for slot in slots
        ],
        "receipt": {
            "returned_slot_ids": [slot["slot_id"] for slot in slots],
        },
    }
    return json.dumps(response, ensure_ascii=False).encode("utf-8")


def _dynamic_budget_gate_canary(
    *,
    repository: Path,
    mappings: list[dict[str, Any]],
    templates: dict[str, dict[str, Any]],
    execution: dict[str, Any],
) -> dict[str, Any]:
    """沿真实渲染路径验证动态 token 与金额双闸会拒绝越界发送。"""

    mapping = mappings[0]
    template_path = str(mapping["verifier_template_path"])
    template = templates[template_path]
    repair_request_path = str(mapping["repair_request_path"])
    repair_request_bytes = (repository / repair_request_path).read_bytes()
    p2_response_bytes = _synthetic_p2_response(repair_request_bytes)
    judge_node = next(
        node
        for node in execution["nodes"]
        if node["node_kind"] == "independent_judge"
        and node["verifier_template_path"] == template_path
        and node["tested_lane_private"] == "flash"
    )
    by_id = {
        str(node["node_id"]): node for node in execution["nodes"]
    }
    repair_node = by_id[str(judge_node["depends_on"][0])]
    runtime_root = f"runtime/{repair_node['node_id']}"
    p2_response_path = f"{runtime_root}/raw_response.json"
    call_attempt_bytes, usage_bytes = (
        make_synthetic_repair_transport_tickets(
            repair_node=repair_node,
            p2_response_path=p2_response_path,
            p2_response_bytes=p2_response_bytes,
        )
    )
    common = {
        "expected_template_sha256": mapping[
            "verifier_template_sha256"
        ],
        "repair_request_bytes": repair_request_bytes,
        "p2_response_path": p2_response_path,
        "p2_response_bytes": p2_response_bytes,
        "repair_node": repair_node,
        "judge_node": judge_node,
        "call_attempt_path": f"{runtime_root}/call_attempt.json",
        "call_attempt_bytes": call_attempt_bytes,
        "usage_path": f"{runtime_root}/usage.json",
        "usage_bytes": usage_bytes,
    }
    ready = render_dynamic_verifier_request(
        template,
        actual_accumulated_tokens=0,
        actual_accumulated_micro_cny=0,
        **common,
    )
    cases: list[dict[str, Any]] = []
    for name, accumulated_tokens, accumulated_micro_cny, marker in (
        ("token_cap_reject", TOTAL_TOKEN_CAP, 0, "50 万 token"),
        (
            "cost_cap_reject",
            0,
            TOTAL_COST_CAP_MICRO_CNY,
            "金额帽",
        ),
    ):
        rejected = False
        error_text = ""
        try:
            render_dynamic_verifier_request(
                template,
                actual_accumulated_tokens=accumulated_tokens,
                actual_accumulated_micro_cny=accumulated_micro_cny,
                **common,
            )
        except Z98VerifierContractError as exc:
            error_text = str(exc)
            rejected = marker in error_text
        cases.append(
            {
                "case": name,
                "expected": "REJECT_BEFORE_SEND",
                "observed": (
                    "REJECT_BEFORE_SEND" if rejected else "NOT_REJECTED"
                ),
                "error": error_text,
                "pass": rejected,
            }
        )
    request_body = ready["request_body"]
    return {
        "schema_version": "z98-dynamic-budget-gate-canary-v1",
        "status": "PASS" if all(row["pass"] for row in cases) else "FAIL",
        "path_exercised": (
            "render_dynamic_verifier_request after actual P2 insertion"
        ),
        "template_path": template_path,
        "template_sha256": mapping["verifier_template_sha256"],
        "repair_request_path": repair_request_path,
        "repair_request_sha256": sha256_bytes(repair_request_bytes),
        "synthetic_p2_response_sha256": sha256_bytes(p2_response_bytes),
        "dynamic_messages_sha256": sha256_bytes(
            stable_json_bytes(request_body["messages"])
        ),
        "dynamic_request_body_sha256": ready["source_binding"][
            "dynamic_request_body_sha256"
        ],
        "baseline_budget_preflight": ready["budget_preflight"],
        "source_files": [
            {
                "path": path,
                "sha256": sha256_bytes((repository / path).read_bytes()),
            }
            for path in (
                (
                    "experiments/"
                    "Z98_independent_verifier_freeze_20260724/core.py"
                ),
                (
                    "experiments/"
                    "Z98_independent_verifier_freeze_20260724/pipeline.py"
                ),
                "tests/test_z98_independent_verifier_freeze.py",
            )
        ],
        "cases": cases,
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def build_bundle(
    bundle_root: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """生成 17 模板与 68 节点冻结包；目标目录必须为空。"""

    repository = (repo_root or REPO_ROOT).resolve()
    target = bundle_root.resolve()
    if target.exists() and any(target.iterdir()):
        raise Z98VerifierContractError(f"目标目录非空，拒绝覆盖：{target}")
    target.mkdir(parents=True, exist_ok=True)

    manifest, manifest_bytes = _load_json_bytes(repository / STEP1_MANIFEST_REL)
    _verify_sha(manifest_bytes, STEP1_MANIFEST_SHA256, "步一 manifest")
    manifest_index = _manifest_index(manifest)
    request_paths = _request_paths(manifest_index)
    authority_request_listing = _recompute_authority_request_listing(
        repository,
        request_paths,
    )
    ordered_paths = _stable_request_order(request_paths)
    budget, budget_bytes = _load_json_bytes(repository / STEP1_BUDGET_REL)
    _verify_sha(budget_bytes, STEP1_BUDGET_SHA256, "步一 budget receipt")
    p2_caps, verification_caps = _budget_maps(budget, ordered_paths)

    provider_receipt = _verify_qianwen_local_config(repository)
    authority, authority_bytes = _load_json_bytes(JUDGE_AUTHORITY_PATH)
    verdict_schema, verdict_schema_bytes = _load_json_bytes(
        VERDICT_SCHEMA_PATH
    )
    if authority["provider"]["exact_model_id"] != MODEL_ID:
        raise Z98VerifierContractError("裁判 authority 精确模型漂移")
    if verdict_schema.get("$id") != "z98_independent_verdict_v1.schema.json":
        raise Z98VerifierContractError("裁判输出 schema 身份漂移")

    request_before: list[dict[str, Any]] = []
    templates: dict[str, dict[str, Any]] = {}
    mappings: list[dict[str, Any]] = []
    for index, request_path in enumerate(ordered_paths, start=1):
        source_path = repository / STEP1_ROOT_REL / request_path
        source_bytes = source_path.read_bytes()
        manifest_row = manifest_index[request_path]
        expected_sha = manifest_row.get("sha256")
        if not isinstance(expected_sha, str):
            raise Z98VerifierContractError("步一请求 manifest SHA 缺失")
        _verify_sha(source_bytes, expected_sha, request_path)
        request_before.append(
            {
                "path": f"{STEP1_ROOT_REL}/{request_path}",
                "sha256": expected_sha,
                "byte_count": len(source_bytes),
            }
        )
        template_id = f"Z98-JUDGE-TEMPLATE-{index:02d}"
        template = make_verifier_template(
            template_id=template_id,
            repair_request_path=f"{STEP1_ROOT_REL}/{request_path}",
            repair_request_bytes=source_bytes,
            verification_token_cap=verification_caps[request_path],
        )
        template_path = f"templates/{template_id}.json"
        template_sha = sha256_bytes(stable_json_bytes(template))
        templates[template_path] = template
        binding = template["private_binding"]
        repair_request = json.loads(source_bytes)
        mappings.append(
            {
                "template_id": template_id,
                "template_index": index,
                "chapter_id": str(repair_request["chapter_id"]),
                "contract_mode": str(repair_request["contract_mode"]),
                "repair_request_path": f"{STEP1_ROOT_REL}/{request_path}",
                "repair_request_sha256": expected_sha,
                "repair_request_id": str(repair_request["request_id"]),
                "source_slot_ids": binding["source_slot_ids"],
                "source_data_sha256": binding["source_data_sha256"],
                "verifier_template_path": template_path,
                "verifier_template_sha256": template_sha,
                "p2_token_cap": p2_caps[request_path],
                "verification_token_cap": verification_caps[request_path],
                "dynamic_request_status": "PENDING_P2_RESPONSE",
            }
        )

    feasibility_receipt = build_feasibility_receipt(
        repo_root=repository,
        templates=templates,
    )
    feasibility_by_template = {
        row["template_path"]: row
        for row in feasibility_receipt["budget_audit"]["templates"]
    }
    for mapping in mappings:
        projection = feasibility_by_template[
            mapping["verifier_template_path"]
        ]
        mapping["static_before_candidate_prompt_token_projection"] = projection[
            "conservative_projection_1_25x"
        ]
        mapping["static_before_candidate_total_token_projection"] = (
            mapping["static_before_candidate_prompt_token_projection"]
            + OUTPUT_TOKEN_LIMIT
        )

    request_after = []
    for row in request_before:
        data = (repository / row["path"]).read_bytes()
        _verify_sha(data, row["sha256"], row["path"])
        request_after.append(
            {
                "path": row["path"],
                "sha256": sha256_bytes(data),
                "byte_count": len(data),
            }
        )
    contract_paths = (
        "contracts/knife_a_patch_v1.schema.json",
        "contracts/atom_batch_v2.schema.json",
    )
    contract_rows = []
    for contract_path in contract_paths:
        data = (repository / STEP1_ROOT_REL / contract_path).read_bytes()
        manifest_row = manifest_index[contract_path]
        _verify_sha(data, str(manifest_row["sha256"]), contract_path)
        contract_rows.append(
            {
                "path": f"{STEP1_ROOT_REL}/{contract_path}",
                "sha256": sha256_bytes(data),
                "byte_count": len(data),
            }
        )
    immutability_receipt = {
        "schema_version": "z98-repair-source-immutability-v1",
        "status": (
            "PASS_UNCHANGED"
            if request_before == request_after
            else "HARD_STOP_CHANGED"
        ),
        "request_count": len(request_before),
        "authority_listing_replay": authority_request_listing,
        "local_listing_sha256": sha256_bytes(
            stable_json_bytes(request_before)
        ),
        "before": request_before,
        "after": request_after,
        "contracts_unchanged": contract_rows,
    }
    if immutability_receipt["status"] != "PASS_UNCHANGED":
        raise Z98VerifierContractError("冻结修复请求在构造期间发生漂移")

    execution = _execution_sequence(mappings)
    graph_transport_binding = _graph_transport_binding_preflight(execution)
    dynamic_binding_rule = _dynamic_binding_rule()
    dynamic_budget_canary = _dynamic_budget_gate_canary(
        repository=repository,
        mappings=mappings,
        templates=templates,
        execution=execution,
    )
    if dynamic_budget_canary["status"] != "PASS":
        raise Z98VerifierContractError("动态预算双闸预演未全过")
    canary = _run_canaries(
        mappings=mappings,
        templates=templates,
        execution=execution,
        authority=authority,
    )
    if canary["status"] != "PASS":
        raise Z98VerifierContractError("独立核验冻结 CANARY 未全过")
    strict_parser_receipt = _strict_parser_reject_preflight(repository)
    if strict_parser_receipt["status"] != "PASS":
        raise Z98VerifierContractError("严格解析与拒收预演未全过")
    visible_hits: list[dict[str, Any]] = []
    for template_path, template in templates.items():
        for hit in scan_model_visible_leaks(template["model_visible"]):
            visible_hits.append({"template_path": template_path, **hit})
    leak_receipt = {
        "schema_version": "z98-verifier-model-window-leak-scan-v1",
        "status": "PASS" if not visible_hits else "FAIL",
        "template_count": len(templates),
        "forbidden_hit_count": len(visible_hits),
        "hits": visible_hits,
        "forbidden_material": [
            "tested provider/lane",
            "single or batch contract identity",
            "gold or answers",
            "human verdicts",
            "historical scores",
            "repair logs",
        ],
    }
    if visible_hits:
        raise Z98VerifierContractError("裁判模板可见面泄漏")

    budget_receipt = {
        "schema_version": "z98-verifier-budget-freeze-v1",
        "status": "FROZEN_WITH_CZ_500K_OVERRIDE_NOT_MEASURED",
        "source_budget_path": STEP1_BUDGET_REL,
        "source_budget_sha256": STEP1_BUDGET_SHA256,
        "judge_calls": 34,
        "price_snapshot": {
            "currency": "CNY",
            "unit": "per_million_tokens",
            "input_price": INPUT_PRICE_CNY_PER_MILLION_TOKENS,
            "output_price": OUTPUT_PRICE_CNY_PER_MILLION_TOKENS,
            "conservative_rule": (
                "每次裁判的全部 token 帽都按输出价 36 计算最坏金额"
            ),
        },
        "templates": [
            {
                "template_id": row["template_id"],
                "chapter_id": row["chapter_id"],
                "legacy_verification_token_cap": row[
                    "verification_token_cap"
                ],
                "static_before_candidate_prompt_token_projection": row[
                    "static_before_candidate_prompt_token_projection"
                ],
                "max_completion_tokens": OUTPUT_TOKEN_LIMIT,
                "static_before_candidate_total_token_projection": row[
                    "static_before_candidate_total_token_projection"
                ],
                "call_count": 2,
                "tested_lanes_private": ["flash", "pro"],
            }
            for row in mappings
        ],
        "calls": [
            {
                "node_id": node["node_id"],
                "chapter_id": node["chapter_id"],
                "tested_lane_private": node["tested_lane_private"],
                "contract_mode_private": node["contract_mode_private"],
                "legacy_verification_token_cap": node[
                    "legacy_verification_token_cap"
                ],
                "static_before_candidate_prompt_token_projection": node[
                    "static_before_candidate_prompt_token_projection"
                ],
                "max_completion_tokens": node["max_completion_tokens"],
                "static_before_candidate_total_token_projection": node[
                    "static_before_candidate_total_token_projection"
                ],
                "static_before_candidate_cost_projection_micro_cny": node[
                    "static_before_candidate_cost_projection_micro_cny"
                ],
                "status": "FROZEN_WAITING_P2_RESPONSE",
            }
            for node in execution["nodes"]
            if node["node_kind"] == "independent_judge"
        ],
        "legacy_judge_total_token_cap": 2
        * sum(row["verification_token_cap"] for row in mappings),
        "legacy_cap_status": (
            "保留作实验设计差异账；CZ 当前对话直批50万后不再作发送阻断"
        ),
        "judge_round_token_cap": TOTAL_TOKEN_CAP,
        "static_before_candidate_round_token_projection": sum(
            node["static_before_candidate_total_token_projection"]
            for node in execution["nodes"]
            if node["node_kind"] == "independent_judge"
        ),
        "judge_total_cost_cap_cny": TOTAL_COST_CAP_CNY,
        "judge_total_cost_cap_micro_cny": TOTAL_COST_CAP_MICRO_CNY,
        "static_before_candidate_round_cost_projection_micro_cny": sum(
            node["static_before_candidate_cost_projection_micro_cny"]
            for node in execution["nodes"]
            if node["node_kind"] == "independent_judge"
        ),
        "send_preflight_rule": {
            "token_formula": (
                "actual_accumulated_tokens + "
                "next_conservative_token_projection <= 500000"
            ),
            "formula": (
                "actual_accumulated_micro_cny + "
                "next_conservative_cap_micro_cny <= 10000000"
            ),
            "over_cap_action": "HARD_STOP_BEFORE_SEND_NO_SELF_INCREASE",
            "actual_accumulated_source": "formal provider usage and price ledger",
            "next_call_cap_source": (
                "实际P2插入后的完整动态messages经验保守投影＋4k输出上限"
                " × output_price_micro_cny_per_token"
            ),
            "static_projection_must_not_authorize_send": True,
        },
        "formal_account_only_accepts_usage": True,
        "actual_usage_tokens": None,
        "actual_cost_cny": None,
    }
    if budget_receipt["legacy_judge_total_token_cap"] != 33312:
        raise Z98VerifierContractError("34 次裁判旧设计 token 帽漂移")
    if (
        budget_receipt[
            "static_before_candidate_round_token_projection"
        ]
        != feasibility_receipt["budget_audit"][
            "cz_direct_round_allowance"
        ]["static_before_candidate_two_lane_token_projection"]
    ):
        raise Z98VerifierContractError("34 次裁判保守 token 投影漂移")
    if (
        budget_receipt[
            "static_before_candidate_round_cost_projection_micro_cny"
        ]
        != feasibility_receipt["budget_audit"][
            "cz_direct_round_allowance"
        ]["static_before_candidate_two_lane_cost_micro_cny"]
    ):
        raise Z98VerifierContractError("34 次裁判金额最坏值漂移")

    preflight = {
        "schema_version": "z98-independent-verifier-freeze-preflight-v1",
        "status": "PASS_ZERO_CALL_FROZEN_AWAITING_UNIFIED_REVIEW",
        "step2_release_allowed": False,
        "release_boundary": (
            "本冻结包统一审收 PASS 后，才按 Notion 17:15 放行令恢复发网"
        ),
        "template_count": len(templates),
        "repair_nodes": 34,
        "independent_judge_nodes": 34,
        "execution_nodes": 68,
        "judge_provider": PROVIDER_ID,
        "judge_exact_model": MODEL_ID,
        "live_exact_model_catalog_check": "PENDING_BEFORE_NETWORK_RELEASE",
        "model_api_calls": 0,
        "provider_catalog_requests": 0,
        "network_attempts": 0,
        "usage_tokens": 0,
        "secret_values_read_or_logged": False,
        "repair_request_set_unchanged": True,
        "repair_contracts_unchanged": True,
        "quality_status": "UNJUDGED",
        "cz_direct_round_token_cap": TOTAL_TOKEN_CAP,
        "cardinality_side_channel_declared": True,
        "feasibility_status": feasibility_receipt["status"],
    }

    files: dict[str, bytes] = {
        "contracts/z98_independent_verdict_v1.schema.json": (
            verdict_schema_bytes
        ),
        "design/judge_authority_contract.json": authority_bytes,
    }
    for path, template in templates.items():
        files[path] = stable_json_bytes(template)
    artifacts = {
        "mappings/verifier_mapping.json": {
            "schema_version": "z98-verifier-mapping-v1",
            "mapping_count": len(mappings),
            "mappings": mappings,
            "model_visible_explicit_identity_labels_hidden": True,
            "cardinality_side_channel_declared": True,
            "full_statistical_contract_identity_blind": False,
        },
        "execution/sequence_68.json": execution,
        "design/dynamic_request_binding_rule.json": dynamic_binding_rule,
        "receipts/graph_transport_binding_preflight.json": (
            graph_transport_binding
        ),
        "receipts/provider_local_config_receipt.json": provider_receipt,
        "receipts/repair_source_immutability.json": immutability_receipt,
        "receipts/verifier_budget_receipt.json": budget_receipt,
        "receipts/verifier_feasibility_audit.json": feasibility_receipt,
        "receipts/model_window_leak_scan.json": leak_receipt,
        "receipts/canary_receipt.json": canary,
        "receipts/strict_parser_reject_preflight.json": (
            strict_parser_receipt
        ),
        "receipts/dynamic_budget_gate_canary.json": (
            dynamic_budget_canary
        ),
        "preflight.json": preflight,
    }
    for path, value in artifacts.items():
        files[path] = stable_json_bytes(value)
    manifest_rows = [
        {
            "path": path,
            "sha256": sha256_bytes(data),
            "byte_count": len(data),
        }
        for path, data in sorted(files.items())
    ]
    output_manifest = {
        "schema_version": "z98-independent-verifier-freeze-manifest-v1",
        "file_count_excluding_manifest": len(manifest_rows),
        "files": manifest_rows,
    }
    files["bundle_manifest.json"] = stable_json_bytes(output_manifest)
    for path, data in sorted(files.items()):
        output = target / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    return {
        "status": preflight["status"],
        "bundle_root": str(target),
        "file_count": len(files),
        "manifest_sha256": sha256_bytes(files["bundle_manifest.json"]),
        "template_count": len(templates),
        "execution_nodes": 68,
        "model_api_calls": 0,
        "network_attempts": 0,
        "step2_release_allowed": False,
    }

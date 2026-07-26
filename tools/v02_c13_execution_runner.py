#!/usr/bin/env python3
"""V02/C13 r07 正式 90 节点执行器。

本文件只负责把 r02/r03/r04 已签工件接成可复验的执行状态机：

- r03 的 90 个冻结请求按固定顺序重签独立顺序票；
- 请求、响应原包先落盘，之后才做机械合同判定；
- 只允许从完整检查点前缀后的第一个未尝试节点续跑；
- 每家 30、整轮 90 的逻辑题位硬帽由程序机械强制；
- 真运输必须持有绑定本 runner、顺序票、预演票、Git 冻结点、
  三家型号票与密钥存在性证明的 execute 票；
- 主读数臂型号闸失败时整轮硬停；复现臂型号闸失败时，该家 30
  个题位逐位封签为 ``SKIPPED_PROVIDER_GATE``，其余家按原顺序继续。

本轮权威令没有给出重试次数与连续失败阈值的数值。为不从旧路线
静默继承，本版采用最保守且可审计的冻结值：每题总尝试 1 次（0
重试），连续 1 次运输失败即整轮硬停。若以后获准放宽，必须新开
runner 版本；不得回写本文件对应的已封运行。

``rehearse`` 只使用注入的假运输层，不读密钥、不访问网络。它会：

1. 跑满 90 节点，并覆盖正常 JSON、非 JSON、截断、重复回包；
2. 在完整检查点边界暂停一次，再从下一未尝试节点续跑；
3. 用独立探针证明超时会在第一个节点硬停；
4. 证明没有 execute 票时，真运输入口在读取密钥前拒绝。

所有最终输出均为 ``PROVISIONAL_AI_DOWNSTREAM`` 诊断候选，不产生
路线胜负、不改金标、不改默认链、不写 outbox。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


def _discover_repo_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (
            (parent / "AGENTS.md").is_file()
            and (parent / "governance").is_dir()
            and (parent / "experiments").is_dir()
        ):
            return parent
    raise RuntimeError("找不到小说架构仓库根目录")


ROOT = _discover_repo_root(Path(__file__).resolve().parent)
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
PROGRAM_DIR = V02_ROOT / "V02_C13_downstream_consumer_program_20260725"
SOURCE_R02 = V02_ROOT / "V02_C13_downstream_consumer_r02_20260726"
SOURCE_R03 = V02_ROOT / "V02_C13_downstream_consumer_wire_r03_20260726"
SOURCE_R04 = (
    V02_ROOT
    / "V02_C13_downstream_consumer_signoff_floor_v2_r04_20260726"
)
R04_PROGRAM = PROGRAM_DIR / "v02_c13_signoff_floor_v2.py"
WIRE_PLAN_PATH = SOURCE_R03 / "plans/wire_dispatch_plan.json"
DEFAULT_RUN_DIR = (
    ROOT / "runs/V02_C13_downstream_consumer_execution_r06_20260726"
)

if str(PROGRAM_DIR) not in sys.path:
    sys.path.insert(0, str(PROGRAM_DIR))

import v02_c13_downstream_consumer as c13  # noqa: E402
import v02_c13_signoff_floor_v2 as r04  # noqa: E402

if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import v02_c13_catalog_gate as catalog_gate  # noqa: E402


CONTRACT_VERSION = "v02-c13-execution-runner-r06.v1"
EXECUTE_TICKET_SCHEMA = "v02-c13-execute-ticket.v1"
AUTHORITY_PAGE = (
    "https://app.notion.com/p/3a85cadc4d0f81eabe45e5dea9292f68"
)

EXPECTED_R02_MANIFEST_SHA256 = (
    "aaf69c7c6f53a21b864580558de5398e0314154a0e96f5869af70556e42c9344"
)
EXPECTED_R02_ARTIFACT_SET_SHA256 = (
    "d20c194fec453fc3c55a09b7088c59b7435d23118f0207ba6f8a8f8af6e19c9c"
)
EXPECTED_R03_MANIFEST_SHA256 = (
    "5867b6ae1425758a890e463ab3049227227b037a07b7fdd5e7d38296a6357daf"
)
EXPECTED_R03_ARTIFACT_SET_SHA256 = (
    "62bce83e9e4701f171016dc2c090659991d837cc7027b94dcf3b6f21b192cf60"
)
EXPECTED_R04_PROGRAM_SHA256 = (
    "bf969b134f84b42568fa00538dd80e9d3f00a36c9450b17d3c6c8cb82a527891"
)
EXPECTED_R04_MANIFEST_SHA256 = (
    "c02eccffe98122686c7c97211f7c3d5f09f6683e391c70b39c90f7f129cf7218"
)
EXPECTED_R04_ARTIFACT_SET_SHA256 = (
    "42720aec48750f6d274de43df8e9ea14c41ff76b33c929d1a3eaba4442a70632"
)
EXPECTED_PROMPT_SET_SHA256 = (
    "1302b5fbda68f0b525d2e32267cd2084a1032be1d8a8335a92f869a451570b3f"
)
EXPECTED_WIRE_PLAN_SHA256 = (
    "e5c8c9f0d2e3e2f8d298638e8618fa2476230dd370a651af68f28f5b2561748c"
)

EXPECTED_PROVIDER_MODELS = {
    "qianwen_platform": "qwen3.7-max-2026-05-20",
    "volcengine_ark": "doubao-seed-2-1-pro-260628",
    "tencent_tokenhub": "minimax-m3",
}
EXPECTED_PROVIDER_GATE_STATUS = {
    "qianwen_platform": "PASS_EXACT_MODEL_SINGLE_MINIMAL_HANDSHAKE",
    "volcengine_ark": "PASS_EXACT_MODEL_SINGLE_MINIMAL_HANDSHAKE",
    "tencent_tokenhub": "PASS_EXACT_MODEL_LIVE_CATALOG",
}
MAIN_PROVIDER_ID = "qianwen_platform"
REPLICA_PROVIDER_IDS = frozenset(
    {"volcengine_ark", "tencent_tokenhub"}
)
PROVIDER_GATE_FAILED = "PROVIDER_GATE_FAILED"

TOTAL_NODE_HARD_CAP = 90
PER_PROVIDER_NODE_HARD_CAP = 30
MAX_TRANSPORT_ATTEMPTS_PER_NODE = 1
MAX_TRANSPORT_RETRIES_PER_NODE = 0
CONSECUTIVE_TRANSPORT_FAILURE_HARD_STOP = 1

NARROW_GIT_REQUIRED_RUNTIME_PATHS = frozenset(
    {
        "config/providers/c13_provider_catalog_gate_v1.json",
        (
            "experiments/extraction_redesign_v02_overnight_20260725/"
            "V02_C13_downstream_consumer_program_20260725/"
            "v02_c13_downstream_consumer.py"
        ),
        (
            "experiments/extraction_redesign_v02_overnight_20260725/"
            "V02_C13_downstream_consumer_program_20260725/"
            "v02_c13_provider_wire.py"
        ),
        (
            "experiments/extraction_redesign_v02_overnight_20260725/"
            "V02_C13_downstream_consumer_program_20260725/"
            "v02_c13_signoff_floor_v2.py"
        ),
        "tools/v02_c13_catalog_gate.py",
        "tools/v02_c13_execution_runner.py",
    }
)

TERMINAL_NODE_STATUSES = {
    "ACCEPTED",
    "REJECTED_CONTRACT",
    "HARD_STOP_TRANSPORT",
    "SKIPPED_PROVIDER_GATE",
}
RESUMABLE_NODE_STATUSES = {
    "ACCEPTED",
    "REJECTED_CONTRACT",
    "SKIPPED_PROVIDER_GATE",
}


class C13ExecutionError(RuntimeError):
    """C13 执行工件或状态不满足冻结合同。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


class C13TransportHardStop(C13ExecutionError):
    """运输失败已触发预写整轮止损线。"""


@dataclass(frozen=True)
class TransportOutcome:
    """一次运输尝试的原始结果；判断前不做清洗。"""

    kind: str
    http_status: int | None
    raw_response: bytes | None
    headers: Mapping[str, str] = field(default_factory=dict)
    error_code: str | None = None
    detail: str | None = None


Transport = Callable[[Mapping[str, Any], bytes, int], TransportOutcome]


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _is_sha256(value: Any) -> bool:
    return bool(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value))


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise C13ExecutionError(
            "json_read_failed",
            f"JSON 读取失败：{_display_path(path)}",
        ) from exc


def _write_exclusive(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise C13ExecutionError(
            "immutable_artifact_exists",
            f"不可变工件已存在，禁止覆盖：{_display_path(path)}",
        ) from exc


def _write_or_verify(path: Path, raw: bytes) -> str:
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise C13ExecutionError(
                "immutable_artifact_drift",
                f"既有工件与重建字节不一致：{_display_path(path)}",
            )
        return "REUSED_EXACT_BYTES"
    _write_exclusive(path, raw)
    return "CREATED"


def _verify_manifest_tree(
    directory: Path,
    *,
    manifest_sha256: str,
    artifact_set_sha256: str,
) -> dict[str, Any]:
    manifest_path = directory / "artifact_manifest.json"
    if sha256_file(manifest_path) != manifest_sha256:
        raise C13ExecutionError(
            "source_manifest_sha_drift",
            f"冻结 manifest 漂移：{_display_path(manifest_path)}",
        )
    manifest = _read_json(manifest_path)
    if manifest.get("artifact_set_sha256") != artifact_set_sha256:
        raise C13ExecutionError(
            "source_artifact_set_sha_drift",
            f"冻结工件集合 SHA 漂移：{_display_path(directory)}",
        )
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise C13ExecutionError(
            "source_manifest_rows_missing",
            "冻结 manifest 没有逐文件行",
        )
    expected: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise C13ExecutionError(
                "source_manifest_row_invalid",
                "冻结 manifest 行不是对象",
            )
        relative = row.get("path")
        digest = row.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative == "artifact_manifest.json"
            or relative in expected
            or not _is_sha256(digest)
        ):
            raise C13ExecutionError(
                "source_manifest_row_invalid",
                "冻结 manifest 行字段非法、重复或指向自身",
            )
        expected[relative] = str(digest)
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    }
    if actual != set(expected):
        raise C13ExecutionError(
            "source_manifest_not_closed",
            f"冻结工件集合不闭合：{_display_path(directory)}",
        )
    for relative, digest in expected.items():
        if sha256_file(directory / relative) != digest:
            raise C13ExecutionError(
                "source_file_sha_drift",
                f"冻结实物 SHA 漂移：{relative}",
            )
    rebuilt = sha256_bytes(canonical_bytes(expected))
    if rebuilt != artifact_set_sha256:
        raise C13ExecutionError(
            "source_artifact_set_rebuild_drift",
            f"冻结工件集合重建 SHA 漂移：{_display_path(directory)}",
        )
    return {
        "manifest_path": _display_path(manifest_path),
        "manifest_sha256": manifest_sha256,
        "artifact_set_sha256": rebuilt,
        "file_total": len(expected),
    }


def _verify_signed_sources() -> dict[str, Any]:
    r02 = _verify_manifest_tree(
        SOURCE_R02,
        manifest_sha256=EXPECTED_R02_MANIFEST_SHA256,
        artifact_set_sha256=EXPECTED_R02_ARTIFACT_SET_SHA256,
    )
    r03 = _verify_manifest_tree(
        SOURCE_R03,
        manifest_sha256=EXPECTED_R03_MANIFEST_SHA256,
        artifact_set_sha256=EXPECTED_R03_ARTIFACT_SET_SHA256,
    )
    r04 = _verify_manifest_tree(
        SOURCE_R04,
        manifest_sha256=EXPECTED_R04_MANIFEST_SHA256,
        artifact_set_sha256=EXPECTED_R04_ARTIFACT_SET_SHA256,
    )
    if sha256_file(R04_PROGRAM) != EXPECTED_R04_PROGRAM_SHA256:
        raise C13ExecutionError(
            "r04_program_sha_drift",
            "r04 判定器程序 SHA 漂移，APPROVED_TO_SEND 自动失效",
        )
    if sha256_file(WIRE_PLAN_PATH) != EXPECTED_WIRE_PLAN_SHA256:
        raise C13ExecutionError(
            "wire_plan_sha_drift",
            "r03 90 位运输计划 SHA 漂移",
        )
    prompt_review = _read_json(
        SOURCE_R02 / "prompt_review/exact_visible_messages.json"
    )
    if prompt_review.get("prompt_set_sha256") != EXPECTED_PROMPT_SET_SHA256:
        raise C13ExecutionError(
            "prompt_set_sha_drift",
            "r02 逐字题面集合 SHA 漂移",
        )
    return {
        "r02": r02,
        "r03": r03,
        "r04": r04,
        "approved_to_send": {
            "authority_page": AUTHORITY_PAGE,
            "r02_prompt_set_sha256": EXPECTED_PROMPT_SET_SHA256,
            "r04_program_sha256": EXPECTED_R04_PROGRAM_SHA256,
            "r04_artifact_set_sha256": EXPECTED_R04_ARTIFACT_SET_SHA256,
        },
        "wire_plan_sha256": EXPECTED_WIRE_PLAN_SHA256,
    }


def _profile(provider_id: str) -> dict[str, Any]:
    path = SOURCE_R03 / f"profiles/{provider_id}.json"
    profile = _read_json(path)
    if (
        profile.get("provider_id") != provider_id
        or profile.get("model_id") != EXPECTED_PROVIDER_MODELS.get(provider_id)
        or not isinstance(profile.get("response_contract"), Mapping)
        or not isinstance(profile.get("api_key_env"), str)
        or not isinstance(profile.get("base_url"), str)
        or not isinstance(profile.get("endpoint"), str)
    ):
        raise C13ExecutionError(
            "provider_profile_drift",
            f"供应商冻结 profile 漂移：{provider_id}",
        )
    return profile


def _parse_material_from_body(body: Mapping[str, Any]) -> dict[str, Any]:
    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise C13ExecutionError(
            "request_messages_invalid",
            "冻结请求必须恰有 system/user 两条消息",
        )
    user = messages[1]
    if not isinstance(user, Mapping) or not isinstance(user.get("content"), str):
        raise C13ExecutionError(
            "request_user_content_invalid",
            "冻结请求 user content 非字符串",
        )
    try:
        visible = json.loads(user["content"])
    except json.JSONDecodeError as exc:
        raise C13ExecutionError(
            "request_user_content_not_json",
            "冻结请求 user content 不是 JSON",
        ) from exc
    material = visible.get("material") if isinstance(visible, Mapping) else None
    if not isinstance(material, Mapping):
        raise C13ExecutionError(
            "request_material_missing",
            "冻结请求没有 material 对象",
        )
    facts = material.get("facts")
    if not isinstance(facts, list):
        raise C13ExecutionError(
            "request_facts_invalid",
            "冻结请求 material.facts 不是数组",
        )
    fact_ids: list[str] = []
    for row in facts:
        if (
            not isinstance(row, Mapping)
            or not isinstance(row.get("fact_id"), str)
            or not isinstance(row.get("fact"), str)
        ):
            raise C13ExecutionError(
                "request_fact_invalid",
                "冻结请求含非法事实行",
            )
        fact_ids.append(str(row["fact_id"]))
    if len(fact_ids) != len(set(fact_ids)):
        raise C13ExecutionError(
            "request_fact_id_duplicate",
            "冻结请求 fact_id 重复",
        )
    material_id = material.get("material_id")
    if not isinstance(material_id, str) or not material_id:
        raise C13ExecutionError(
            "request_material_id_invalid",
            "冻结请求 material_id 缺失",
        )
    return {
        "material_id": material_id,
        "allowed_fact_ids": sorted(fact_ids),
        "fact_total": len(fact_ids),
    }


def build_run_plan() -> dict[str, Any]:
    """从 r03 固定行生成 r06 自己的 90 节点顺序票。"""

    sources = _verify_signed_sources()
    wire_plan = _read_json(WIRE_PLAN_PATH)
    rows = wire_plan.get("rows")
    if (
        not isinstance(rows, list)
        or len(rows) != TOTAL_NODE_HARD_CAP
        or wire_plan.get("dispatch_total") != TOTAL_NODE_HARD_CAP
        or wire_plan.get("per_provider_hard_cap")
        != PER_PROVIDER_NODE_HARD_CAP
        or wire_plan.get("private_c13_request_wrapper_may_be_sent") is not False
    ):
        raise C13ExecutionError(
            "wire_plan_shape_invalid",
            "r03 运输计划不是冻结的 90／每家30 结构",
        )

    nodes: list[dict[str, Any]] = []
    provider_counts: Counter[str] = Counter()
    dispatch_ids: set[str] = set()
    for sequence, source_row in enumerate(rows, start=1):
        if not isinstance(source_row, Mapping):
            raise C13ExecutionError(
                "wire_plan_row_invalid",
                f"r03 第 {sequence} 行不是对象",
            )
        provider_id = source_row.get("provider_id")
        dispatch_id = source_row.get("dispatch_id")
        call_id = source_row.get("base_call_id")
        task = source_row.get("task")
        if (
            provider_id not in EXPECTED_PROVIDER_MODELS
            or not isinstance(dispatch_id, str)
            or dispatch_id in dispatch_ids
            or not isinstance(call_id, str)
            or not re.fullmatch(r"C13-N\d{2}", call_id)
            or task not in {"A", "B", "C"}
            or source_row.get("status") != "FROZEN_NOT_SENT"
        ):
            raise C13ExecutionError(
                "wire_plan_row_invalid",
                f"r03 第 {sequence} 行身份、任务或状态非法",
            )
        body_relative = source_row.get("body_path")
        if not isinstance(body_relative, str):
            raise C13ExecutionError(
                "wire_body_path_invalid",
                f"r03 第 {sequence} 行 body_path 非法",
            )
        body_path = SOURCE_R03 / body_relative
        body_raw = body_path.read_bytes()
        if sha256_bytes(body_raw) != source_row.get("body_sha256"):
            raise C13ExecutionError(
                "wire_body_sha_drift",
                f"r03 第 {sequence} 行 body SHA 漂移",
            )
        body = _read_json(body_path)
        profile = _profile(str(provider_id))
        if (
            body.get("model") != profile["model_id"]
            or source_row.get("model_id") != profile["model_id"]
            or source_row.get("url")
            != f"{profile['base_url']}{profile['endpoint']}"
            or source_row.get("timeout_seconds") != profile["timeout_seconds"]
        ):
            raise C13ExecutionError(
                "wire_profile_binding_drift",
                f"r03 第 {sequence} 行未精确绑定 profile",
            )
        material = _parse_material_from_body(body)
        provider_counts[str(provider_id)] += 1
        dispatch_ids.add(dispatch_id)
        nodes.append(
            {
                "sequence": sequence,
                "node_id": f"C13-R06-{sequence:03d}",
                "dispatch_id": dispatch_id,
                "provider_id": provider_id,
                "model_id": profile["model_id"],
                "api_key_env": profile["api_key_env"],
                "url": source_row["url"],
                "timeout_seconds": source_row["timeout_seconds"],
                "base_call_id": call_id,
                "task": task,
                "floor_kind": source_row.get("floor_kind"),
                "body_path": _display_path(body_path),
                "body_sha256": source_row["body_sha256"],
                "messages_sha256": source_row["messages_sha256"],
                "response_profile_path": _display_path(
                    SOURCE_R03 / f"profiles/{provider_id}.json"
                ),
                "response_profile_sha256": sha256_file(
                    SOURCE_R03 / f"profiles/{provider_id}.json"
                ),
                "expected_material_id": material["material_id"],
                "allowed_fact_ids": material["allowed_fact_ids"],
                "fact_total": material["fact_total"],
            }
        )
    if provider_counts != Counter(
        {provider_id: PER_PROVIDER_NODE_HARD_CAP for provider_id in EXPECTED_PROVIDER_MODELS}
    ):
        raise C13ExecutionError(
            "provider_node_cap_shape_invalid",
            f"每家题位数不是30：{dict(provider_counts)}",
        )

    order_rows = [
        {
            "sequence": row["sequence"],
            "node_id": row["node_id"],
            "dispatch_id": row["dispatch_id"],
            "provider_id": row["provider_id"],
            "base_call_id": row["base_call_id"],
            "task": row["task"],
            "floor_kind": row["floor_kind"],
            "body_sha256": row["body_sha256"],
            "messages_sha256": row["messages_sha256"],
        }
        for row in nodes
    ]
    node_order_sha256 = sha256_bytes(canonical_bytes(order_rows))
    return {
        "schema_version": "v02-c13-r06-run-plan.v1",
        "contract_version": CONTRACT_VERSION,
        "diagnostic_tier": "PROVISIONAL_AI_DOWNSTREAM",
        "run_policy": {
            "total_node_hard_cap": TOTAL_NODE_HARD_CAP,
            "per_provider_node_hard_cap": PER_PROVIDER_NODE_HARD_CAP,
            "max_transport_attempts_per_node": MAX_TRANSPORT_ATTEMPTS_PER_NODE,
            "max_transport_retries_per_node": MAX_TRANSPORT_RETRIES_PER_NODE,
            "consecutive_transport_failure_hard_stop": (
                CONSECUTIVE_TRANSPORT_FAILURE_HARD_STOP
            ),
            "quality_retry_allowed": False,
            "change_question_on_retry_allowed": False,
            "automatic_provider_fallback_allowed": False,
        },
        "authority": sources,
        "wire_plan_path": _display_path(WIRE_PLAN_PATH),
        "wire_plan_sha256": EXPECTED_WIRE_PLAN_SHA256,
        "node_order_sha256": node_order_sha256,
        "nodes": nodes,
    }


def _ticket_template(
    *,
    run_id: str,
    run_plan_sha256: str,
    node_order_sha256: str,
) -> dict[str, Any]:
    run_path = _display_path(Path(run_id))
    run_identity = {
        "run_id": Path(run_id).name,
        "run_path": run_path,
        "node_order_sha256": node_order_sha256,
    }
    return {
        "schema_version": EXECUTE_TICKET_SCHEMA,
        "status": "NOT_APPROVED_TEMPLATE_ONLY",
        "execute_allowed": False,
        "run_id": Path(run_id).name,
        "run_path": run_path,
        "run_path_identity_sha256": sha256_bytes(canonical_bytes(run_identity)),
        "authority_page": AUTHORITY_PAGE,
        "approved_to_send_bound": {
            "r02_prompt_set_sha256": EXPECTED_PROMPT_SET_SHA256,
            "r04_program_sha256": EXPECTED_R04_PROGRAM_SHA256,
            "r04_artifact_set_sha256": EXPECTED_R04_ARTIFACT_SET_SHA256,
        },
        "runner_sha256": sha256_file(Path(__file__)),
        "run_plan_sha256": run_plan_sha256,
        "node_order_sha256": node_order_sha256,
        "wire_plan_sha256": EXPECTED_WIRE_PLAN_SHA256,
        "transport_policy": {
            "max_transport_attempts_per_node": MAX_TRANSPORT_ATTEMPTS_PER_NODE,
            "max_transport_retries_per_node": MAX_TRANSPORT_RETRIES_PER_NODE,
            "consecutive_transport_failure_hard_stop": (
                CONSECUTIVE_TRANSPORT_FAILURE_HARD_STOP
            ),
            "per_provider_node_hard_cap": PER_PROVIDER_NODE_HARD_CAP,
            "total_node_hard_cap": TOTAL_NODE_HARD_CAP,
        },
        "narrow_git_freeze": {
            "commit_sha": "REQUIRED_FULL_40_HEX",
            "committed_at": "REQUIRED_ISO8601",
            "pushed": False,
            "allowed_file_manifest_path": "REQUIRED_REPO_RELATIVE_PATH",
            "allowed_file_manifest_sha256": "REQUIRED_SHA256",
        },
        "zero_call_rehearsal_receipt": {
            "path": "REQUIRED",
            "sha256": "REQUIRED_SHA256",
            "run_id": "REQUIRED_REHEARSAL_RUN_ID",
            "runner_sha256": sha256_file(Path(__file__)),
            "run_plan_sha256": run_plan_sha256,
            "node_order_sha256": node_order_sha256,
        },
        "key_presence": {
            provider_id: False for provider_id in EXPECTED_PROVIDER_MODELS
        },
        "provider_gate_receipts": [
            {
                "provider_id": provider_id,
                "exact_model_id": model_id,
                "attempt_no": 1,
                "attempt_ledger_path": "REQUIRED",
                "attempt_ledger_sha256": "REQUIRED_SHA256",
                "raw_response_path": "REQUIRED",
                "raw_response_sha256": "REQUIRED_SHA256",
                "receipt_path": "REQUIRED",
                "receipt_sha256": "REQUIRED_SHA256",
                "status": EXPECTED_PROVIDER_GATE_STATUS[provider_id],
            }
            for provider_id, model_id in EXPECTED_PROVIDER_MODELS.items()
        ],
        "provider_gate_failures": [],
        "approved_at": "REQUIRED_ISO8601",
    }


def prepare(run_dir: Path) -> dict[str, Any]:
    """冻结 r06 顺序票与执行票模板；0 API、0 网络。"""

    run_dir = run_dir.resolve()
    plan = build_run_plan()
    plan_path = run_dir / "prepared/run_plan.json"
    order_path = run_dir / "prepared/node_order.json"
    source_path = run_dir / "prepared/source_receipt.json"

    order = {
        "schema_version": "v02-c13-r06-node-order.v1",
        "contract_version": CONTRACT_VERSION,
        "node_total": len(plan["nodes"]),
        "per_provider_hard_cap": PER_PROVIDER_NODE_HARD_CAP,
        "total_hard_cap": TOTAL_NODE_HARD_CAP,
        "max_transport_attempts_per_node": MAX_TRANSPORT_ATTEMPTS_PER_NODE,
        "max_transport_retries_per_node": MAX_TRANSPORT_RETRIES_PER_NODE,
        "consecutive_transport_failure_hard_stop": (
            CONSECUTIVE_TRANSPORT_FAILURE_HARD_STOP
        ),
        "source_wire_plan_sha256": EXPECTED_WIRE_PLAN_SHA256,
        "node_order_sha256": plan["node_order_sha256"],
        "rows": [
            {
                key: row[key]
                for key in (
                    "sequence",
                    "node_id",
                    "dispatch_id",
                    "provider_id",
                    "base_call_id",
                    "task",
                    "floor_kind",
                    "body_sha256",
                    "messages_sha256",
                )
            }
            for row in plan["nodes"]
        ],
    }
    rebuilt_order_sha = sha256_bytes(canonical_bytes(order["rows"]))
    if rebuilt_order_sha != plan["node_order_sha256"]:
        raise C13ExecutionError(
            "node_order_sha_internal_mismatch",
            "r06 90 节点顺序 SHA 内部不一致",
        )
    source_receipt = {
        "schema_version": "v02-c13-r06-source-receipt.v1",
        "run_id": run_dir.name,
        "contract_version": CONTRACT_VERSION,
        "runner_path": _display_path(Path(__file__)),
        "runner_sha256": sha256_file(Path(__file__)),
        "approved_to_send_bound": plan["authority"]["approved_to_send"],
        "r02_manifest_sha256": EXPECTED_R02_MANIFEST_SHA256,
        "r02_artifact_set_sha256": EXPECTED_R02_ARTIFACT_SET_SHA256,
        "r03_manifest_sha256": EXPECTED_R03_MANIFEST_SHA256,
        "r03_artifact_set_sha256": EXPECTED_R03_ARTIFACT_SET_SHA256,
        "r04_manifest_sha256": EXPECTED_R04_MANIFEST_SHA256,
        "r04_artifact_set_sha256": EXPECTED_R04_ARTIFACT_SET_SHA256,
        "wire_plan_sha256": EXPECTED_WIRE_PLAN_SHA256,
        "node_order_sha256": plan["node_order_sha256"],
        "model_api_requests": 0,
        "network_attempts": 0,
        "key_values_read": 0,
        "execute_allowed": False,
    }
    _write_or_verify(plan_path, canonical_bytes(plan))
    _write_or_verify(order_path, canonical_bytes(order))
    _write_or_verify(source_path, canonical_bytes(source_receipt))
    plan_sha = sha256_file(plan_path)
    template = _ticket_template(
        run_id=_display_path(run_dir),
        run_plan_sha256=plan_sha,
        node_order_sha256=plan["node_order_sha256"],
    )
    _write_or_verify(
        run_dir / "prepared/execute_ticket_TEMPLATE.json",
        canonical_bytes(template),
    )
    receipt = verify_prepared(run_dir)
    return {
        **receipt,
        "status": "PREPARED_ZERO_CALL_EXECUTE_TICKET_REQUIRED",
        "execute_allowed": False,
    }


def verify_prepared(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    rebuilt = build_run_plan()
    plan_path = run_dir / "prepared/run_plan.json"
    order_path = run_dir / "prepared/node_order.json"
    source_path = run_dir / "prepared/source_receipt.json"
    template_path = run_dir / "prepared/execute_ticket_TEMPLATE.json"
    for path in (plan_path, order_path, source_path, template_path):
        if not path.is_file():
            raise C13ExecutionError(
                "prepared_artifact_missing",
                f"缺少 r06 准备工件：{_display_path(path)}",
            )
    plan = _read_json(plan_path)
    if plan != rebuilt:
        raise C13ExecutionError(
            "prepared_run_plan_drift",
            "r06 run_plan 与签源重建结果不一致",
        )
    order = _read_json(order_path)
    if (
        order.get("node_total") != TOTAL_NODE_HARD_CAP
        or order.get("node_order_sha256") != plan["node_order_sha256"]
        or sha256_bytes(canonical_bytes(order.get("rows")))
        != plan["node_order_sha256"]
    ):
        raise C13ExecutionError(
            "prepared_node_order_drift",
            "r06 节点顺序票漂移",
        )
    source = _read_json(source_path)
    if (
        source.get("runner_sha256") != sha256_file(Path(__file__))
        or source.get("node_order_sha256") != plan["node_order_sha256"]
        or source.get("execute_allowed") is not False
        or source.get("model_api_requests") != 0
        or source.get("network_attempts") != 0
        or source.get("key_values_read") != 0
    ):
        raise C13ExecutionError(
            "prepared_source_receipt_drift",
            "r06 来源票或零调用边界漂移",
        )
    expected_template = _ticket_template(
        run_id=_display_path(run_dir),
        run_plan_sha256=sha256_file(plan_path),
        node_order_sha256=plan["node_order_sha256"],
    )
    if _read_json(template_path) != expected_template:
        raise C13ExecutionError(
            "execute_ticket_template_drift",
            "execute 票模板漂移",
        )
    return {
        "run_id": run_dir.name,
        "run_plan_sha256": sha256_file(plan_path),
        "node_order_sha256": plan["node_order_sha256"],
        "wire_plan_sha256": EXPECTED_WIRE_PLAN_SHA256,
        "runner_sha256": sha256_file(Path(__file__)),
        "node_total": len(plan["nodes"]),
        "per_provider": dict(
            Counter(str(row["provider_id"]) for row in plan["nodes"])
        ),
        "max_transport_attempts_per_node": MAX_TRANSPORT_ATTEMPTS_PER_NODE,
        "max_transport_retries_per_node": MAX_TRANSPORT_RETRIES_PER_NODE,
        "consecutive_transport_failure_hard_stop": (
            CONSECUTIVE_TRANSPORT_FAILURE_HARD_STOP
        ),
        "model_api_requests": 0,
        "network_attempts": 0,
        "key_values_read": 0,
    }


def _safe_node_dir(node: Mapping[str, Any]) -> str:
    dispatch = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(node["dispatch_id"]))
    return f"{int(node['sequence']):03d}_{dispatch}"


def _node_root(run_dir: Path, node: Mapping[str, Any]) -> Path:
    return run_dir / "runtime/nodes" / _safe_node_dir(node)


def _checkpoint_paths(run_dir: Path, node: Mapping[str, Any]) -> dict[str, Path]:
    root = _node_root(run_dir, node)
    return {
        "provider_gate_skip": root / "00_provider_gate_skip.json",
        "request": root / "01_request.raw",
        "response": root / "02_response.raw",
        "response_absent": root / "02_response_absent.json",
        "judgment": root / "03_mechanical_judgment.json",
        "attempt": root / "04_usage_and_attempt.json",
        "seal": root / "05_seal.json",
        "attempt_reservation": (
            root / "attempts/attempt_01/00_reservation.json"
        ),
        "attempt_response": (
            root / "attempts/attempt_01/01_raw_response.raw"
        ),
        "attempt_response_absent": (
            root / "attempts/attempt_01/01_no_response.json"
        ),
    }


def _provider_gate_scope(
    statuses: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """把三家型号闸结果机械化成唯一执行范围。"""

    normalized = (
        {
            provider_id: "PASS"
            for provider_id in EXPECTED_PROVIDER_MODELS
        }
        if statuses is None
        else dict(statuses)
    )
    if set(normalized) != set(EXPECTED_PROVIDER_MODELS) or any(
        status not in {"PASS", PROVIDER_GATE_FAILED}
        for status in normalized.values()
    ):
        raise C13ExecutionError(
            "provider_gate_scope_invalid",
            "型号闸执行范围必须逐家且只能是 PASS／PROVIDER_GATE_FAILED",
        )
    if normalized[MAIN_PROVIDER_ID] != "PASS":
        raise C13ExecutionError(
            "main_provider_gate_failed",
            "主读数臂 Qwen 3.7 Max 型号闸失败；整轮不得只跑复现臂",
        )
    skipped = sorted(
        provider_id
        for provider_id in REPLICA_PROVIDER_IDS
        if normalized[provider_id] == PROVIDER_GATE_FAILED
    )
    eligible = [
        provider_id
        for provider_id in EXPECTED_PROVIDER_MODELS
        if provider_id not in skipped
    ]
    return {
        "statuses": normalized,
        "eligible_provider_ids": eligible,
        "skipped_provider_ids": skipped,
        "planned_node_total": TOTAL_NODE_HARD_CAP,
        "sent_node_hard_cap": (
            len(eligible) * PER_PROVIDER_NODE_HARD_CAP
        ),
        "skipped_node_total": (
            len(skipped) * PER_PROVIDER_NODE_HARD_CAP
        ),
        "unused_quota_reallocated": False,
    }


def _provider_gate_statuses_from_ticket(
    ticket: Mapping[str, Any],
) -> dict[str, str]:
    statuses = {
        str(row["provider_id"]): "PASS"
        for row in ticket["provider_gate_receipts"]
    }
    statuses.update(
        {
            str(row["provider_id"]): PROVIDER_GATE_FAILED
            for row in ticket["provider_gate_failures"]
        }
    )
    return statuses


def _write_provider_gate_skip_checkpoint(
    run_dir: Path,
    *,
    node: Mapping[str, Any],
    execution_kind: str,
) -> dict[str, Any]:
    """不发请求，只把已失败复现臂的题位逐位封签为跳过。"""

    paths = _checkpoint_paths(run_dir, node)
    skip = {
        "schema_version": "v02-c13-r07-provider-gate-skip.v1",
        "node_id": node["node_id"],
        "dispatch_id": node["dispatch_id"],
        "provider_id": node["provider_id"],
        "exact_model_id": node["model_id"],
        "status": "SKIPPED_PROVIDER_GATE",
        "reason_code": PROVIDER_GATE_FAILED,
        "model_api_requests": 0,
        "network_attempts": 0,
        "quota_reallocated": False,
    }
    _write_exclusive(
        paths["provider_gate_skip"],
        canonical_bytes(skip),
    )
    seal = {
        "schema_version": "v02-c13-r06-node-seal.v1",
        "contract_version": CONTRACT_VERSION,
        "node_id": node["node_id"],
        "node_sequence": node["sequence"],
        "dispatch_id": node["dispatch_id"],
        "provider_id": node["provider_id"],
        "base_call_id": node["base_call_id"],
        "task": node["task"],
        "status": "SKIPPED_PROVIDER_GATE",
        "execution_kind": execution_kind,
        "sealed_at": _now_iso(),
        "node_order_sha256": _read_json(
            run_dir / "prepared/run_plan.json"
        )["node_order_sha256"],
        "artifacts": {
            "provider_gate_skip": {
                "path": _display_path(paths["provider_gate_skip"]),
                "sha256": sha256_file(paths["provider_gate_skip"]),
            }
        },
    }
    _write_exclusive(paths["seal"], canonical_bytes(seal))
    return _validate_checkpoint(run_dir, node)


def _task_b_evidence_paths(
    run_dir: Path,
    node: Mapping[str, Any],
) -> dict[str, Path]:
    provider_id = str(node["provider_id"])
    call_id = str(node["base_call_id"])
    return {
        "task_b_raw_response": (
            run_dir
            / "raw_responses"
            / provider_id
            / call_id
            / "attempt_01.raw"
        ),
        "task_b_claim_ledger": (
            run_dir
            / "ledgers"
            / "claim"
            / provider_id
            / call_id
            / "attempt_01.json"
        ),
        "task_b_contract_ledger": (
            run_dir
            / "ledgers"
            / "contract"
            / provider_id
            / call_id
            / "attempt_01.json"
        ),
    }


def _validate_checkpoint(
    run_dir: Path,
    node: Mapping[str, Any],
) -> dict[str, Any]:
    paths = _checkpoint_paths(run_dir, node)
    if not paths["seal"].is_file():
        raise C13ExecutionError(
            "checkpoint_seal_missing",
            f"{node['node_id']} 缺封签",
        )
    seal = _read_json(paths["seal"])
    if (
        seal.get("schema_version") != "v02-c13-r06-node-seal.v1"
        or seal.get("contract_version") != CONTRACT_VERSION
        or seal.get("node_id") != node["node_id"]
        or seal.get("node_sequence") != node["sequence"]
        or seal.get("dispatch_id") != node["dispatch_id"]
        or seal.get("node_order_sha256")
        != _read_json(run_dir / "prepared/run_plan.json")["node_order_sha256"]
        or seal.get("status") not in TERMINAL_NODE_STATUSES
    ):
        raise C13ExecutionError(
            "checkpoint_seal_invalid",
            f"{node['node_id']} 封签字段漂移",
        )
    artifact_rows = seal.get("artifacts")
    if not isinstance(artifact_rows, Mapping):
        raise C13ExecutionError(
            "checkpoint_artifact_map_invalid",
            f"{node['node_id']} 封签缺工件表",
        )
    if seal["status"] == "SKIPPED_PROVIDER_GATE":
        skip_path = paths["provider_gate_skip"]
        forbidden_paths = [
            paths[name]
            for name in (
                "request",
                "response",
                "response_absent",
                "judgment",
                "attempt",
                "attempt_reservation",
                "attempt_response",
                "attempt_response_absent",
            )
        ]
        forbidden_paths.extend(_task_b_evidence_paths(run_dir, node).values())
        if (
            set(artifact_rows) != {"provider_gate_skip"}
            or not skip_path.is_file()
            or any(path.is_file() for path in forbidden_paths)
        ):
            raise C13ExecutionError(
                "checkpoint_provider_gate_skip_artifacts_invalid",
                f"{node['node_id']} 跳过封签夹带了请求、响应或判词",
            )
        row = artifact_rows["provider_gate_skip"]
        skip = _read_json(skip_path)
        if (
            not isinstance(row, Mapping)
            or row.get("path") != _display_path(skip_path)
            or row.get("sha256") != sha256_file(skip_path)
            or skip
            != {
                "schema_version": "v02-c13-r07-provider-gate-skip.v1",
                "node_id": node["node_id"],
                "dispatch_id": node["dispatch_id"],
                "provider_id": node["provider_id"],
                "exact_model_id": node["model_id"],
                "status": "SKIPPED_PROVIDER_GATE",
                "reason_code": PROVIDER_GATE_FAILED,
                "model_api_requests": 0,
                "network_attempts": 0,
                "quota_reallocated": False,
            }
        ):
            raise C13ExecutionError(
                "checkpoint_provider_gate_skip_invalid",
                f"{node['node_id']} 跳过票字段或 SHA 漂移",
            )
        return dict(seal)
    if paths["response"].is_file() == paths["response_absent"].is_file():
        raise C13ExecutionError(
            "checkpoint_response_cardinality_invalid",
            f"{node['node_id']} 响应原包与缺包票必须恰好一份",
        )
    if (
        paths["attempt_response"].is_file()
        == paths["attempt_response_absent"].is_file()
    ):
        raise C13ExecutionError(
            "checkpoint_attempt_response_cardinality_invalid",
            f"{node['node_id']} 首次尝试原包与缺包票必须恰好一份",
        )
    judgment_payload = _read_json(paths["judgment"])
    judgment = judgment_payload.get("judgment")
    if not isinstance(judgment, Mapping):
        raise C13ExecutionError(
            "checkpoint_judgment_invalid",
            f"{node['node_id']} 机械判词结构非法",
        )
    task_b_ledgers = judgment.get("task_b_ledgers")
    has_task_b_ledgers = isinstance(task_b_ledgers, Mapping)
    task_b_paths = _task_b_evidence_paths(run_dir, node)
    task_b_any_evidence = any(path.is_file() for path in task_b_paths.values())
    if task_b_any_evidence != has_task_b_ledgers:
        raise C13ExecutionError(
            "checkpoint_task_b_evidence_unsealed",
            f"{node['node_id']} 任务B原包或双账未完整纳入节点封签",
        )
    expected_names = {
        "request",
        "response_or_absent",
        "judgment",
        "usage_and_attempt",
        "attempt_reservation",
        "attempt_response_or_absent",
    }
    if has_task_b_ledgers:
        expected_names.update(task_b_paths)
    if set(artifact_rows) != expected_names:
        raise C13ExecutionError(
            "checkpoint_artifact_map_invalid",
            f"{node['node_id']} 五件套字段不完整",
        )
    actual_paths = {
        "request": paths["request"],
        "response_or_absent": (
            paths["response"]
            if paths["response"].is_file()
            else paths["response_absent"]
        ),
        "judgment": paths["judgment"],
        "usage_and_attempt": paths["attempt"],
        "attempt_reservation": paths["attempt_reservation"],
        "attempt_response_or_absent": (
            paths["attempt_response"]
            if paths["attempt_response"].is_file()
            else paths["attempt_response_absent"]
        ),
    }
    if has_task_b_ledgers:
        actual_paths.update(task_b_paths)
    for name, path in actual_paths.items():
        row = artifact_rows[name]
        if (
            not isinstance(row, Mapping)
            or not path.is_file()
            or row.get("path") != _display_path(path)
            or row.get("sha256") != sha256_file(path)
        ):
            raise C13ExecutionError(
                "checkpoint_artifact_drift",
                f"{node['node_id']} 工件漂移：{name}",
            )
    if sha256_file(paths["request"]) != node["body_sha256"]:
        raise C13ExecutionError(
            "checkpoint_request_not_frozen",
            f"{node['node_id']} 请求不再等于 r03 冻结字节",
        )
    reservation = _read_json(paths["attempt_reservation"])
    if reservation != {
        "schema_version": "v02-c13-r06-attempt-reservation.v1",
        "node_id": node["node_id"],
        "dispatch_id": node["dispatch_id"],
        "attempt_no": 1,
        "request_sha256": node["body_sha256"],
        "execution_kind": seal["execution_kind"],
        "reserved_at": reservation.get("reserved_at"),
        "max_transport_attempts_per_node": (
            MAX_TRANSPORT_ATTEMPTS_PER_NODE
        ),
    } or not isinstance(reservation.get("reserved_at"), str):
        raise C13ExecutionError(
            "checkpoint_attempt_reservation_invalid",
            f"{node['node_id']} 尝试预留票字段漂移",
        )
    attempt = _read_json(paths["attempt"])
    if (
        attempt.get("node_id") != node["node_id"]
        or attempt.get("dispatch_id") != node["dispatch_id"]
        or attempt.get("attempt_no") != 1
        or attempt.get("request_sha256") != node["body_sha256"]
        or attempt.get("started_at") != reservation["reserved_at"]
    ):
        raise C13ExecutionError(
            "checkpoint_attempt_identity_invalid",
            f"{node['node_id']} usage／运输账没有绑定首次预留",
        )
    if paths["response"].is_file():
        response_sha = sha256_file(paths["response"])
        if (
            sha256_file(paths["attempt_response"]) != response_sha
            or attempt.get("raw_response_sha256") != response_sha
            or judgment.get("raw_response_sha256") != response_sha
        ):
            raise C13ExecutionError(
                "checkpoint_attempt_raw_response_mismatch",
                f"{node['node_id']} 首包、节点响应、判词三者 SHA 不一致",
            )
    else:
        response_absent = _read_json(paths["response_absent"])
        attempt_absent = _read_json(paths["attempt_response_absent"])
        if (
            attempt.get("raw_response_sha256") is not None
            or judgment.get("raw_response_sha256") is not None
            or attempt_absent
            != {
                "kind": response_absent.get("reason"),
                "error_code": response_absent.get("error_code"),
                "detail": response_absent.get("detail"),
            }
        ):
            raise C13ExecutionError(
                "checkpoint_attempt_absence_mismatch",
                f"{node['node_id']} 缺响应票与运输账不一致",
            )
    if has_task_b_ledgers:
        if not paths["response"].is_file():
            raise C13ExecutionError(
                "checkpoint_task_b_without_response",
                f"{node['node_id']} 任务B双账没有节点原始响应",
            )
        verified = r04.verify_task_b_dual_ledgers(
            task_b_paths["task_b_claim_ledger"],
            task_b_paths["task_b_contract_ledger"],
        )
        expected_task_b_refs = {
            "claim_ledger_path": _display_path(
                task_b_paths["task_b_claim_ledger"]
            ),
            "contract_ledger_path": _display_path(
                task_b_paths["task_b_contract_ledger"]
            ),
        }
        response_sha = sha256_file(paths["response"])
        if (
            dict(task_b_ledgers) != expected_task_b_refs
            or verified.get("provider_id") != node["provider_id"]
            or verified.get("call_id") != node["base_call_id"]
            or verified.get("attempt_no") != 1
            or verified.get("request_body_sha256") != node["body_sha256"]
            or verified.get("raw_response_sha256") != response_sha
            or sha256_file(task_b_paths["task_b_raw_response"])
            != response_sha
        ):
            raise C13ExecutionError(
                "checkpoint_task_b_identity_mismatch",
                f"{node['node_id']} 任务B原包／CLAIM／合同账未锁到本节点",
            )
    return dict(seal)


def _node_has_evidence(run_dir: Path, node: Mapping[str, Any]) -> bool:
    root = _node_root(run_dir, node)
    return root.exists() and any(path.is_file() for path in root.rglob("*"))


def audit_resume_position(run_dir: Path) -> dict[str, Any]:
    """只从完整连续前缀的下一未尝试节点续跑。"""

    verify_prepared(run_dir)
    plan = _read_json(run_dir / "prepared/run_plan.json")
    completed: list[str] = []
    first_open: str | None = None
    provider_counts: Counter[str] = Counter()
    hard_stop_node: str | None = None
    for node in plan["nodes"]:
        paths = _checkpoint_paths(run_dir, node)
        if paths["seal"].is_file():
            if first_open is not None:
                raise C13ExecutionError(
                    "checkpoint_noncontiguous",
                    "完整检查点不是连续前缀，疑似人工挑轮",
                )
            seal = _validate_checkpoint(run_dir, node)
            completed.append(str(node["node_id"]))
            provider_counts[str(node["provider_id"])] += 1
            if seal["status"] == "HARD_STOP_TRANSPORT":
                hard_stop_node = str(node["node_id"])
            continue
        if _node_has_evidence(run_dir, node):
            raise C13ExecutionError(
                "attempt_without_complete_checkpoint",
                f"{node['node_id']} 有请求／尝试证据但无完整封签，禁止重发",
            )
        if first_open is None:
            first_open = str(node["node_id"])
    if len(completed) > TOTAL_NODE_HARD_CAP or any(
        count > PER_PROVIDER_NODE_HARD_CAP
        for count in provider_counts.values()
    ):
        raise C13ExecutionError(
            "logical_node_cap_exceeded",
            "既有检查点已超过 90／每家30 硬帽",
        )
    if hard_stop_node is not None:
        status = "HARD_STOP_NOT_RESUMABLE"
        next_node = None
    elif len(completed) == TOTAL_NODE_HARD_CAP:
        status = "COMPLETE_90"
        next_node = None
    else:
        status = "RESUMABLE_AT_NEXT_UNATTEMPTED_NODE"
        next_node = first_open
    return {
        "status": status,
        "completed_prefix_count": len(completed),
        "completed_node_ids": completed,
        "next_node_id": next_node,
        "hard_stop_node_id": hard_stop_node,
        "per_provider_completed": dict(provider_counts),
        "attempted_node_may_be_resent": False,
    }


def _extract_generic_task_judgment(
    raw_response: bytes,
    *,
    node: Mapping[str, Any],
) -> dict[str, Any]:
    profile = _profile(str(node["provider_id"]))
    envelope = r04._extract_provider_response_content(
        raw_response,
        expected_model_id=str(node["model_id"]),
        response_contract=profile["response_contract"],
    )
    failures = list(envelope["failure_codes"])
    payload: Mapping[str, Any] | None = None
    summary: dict[str, Any] = {}
    content_bytes = envelope["content_bytes"]
    if content_bytes is not None:
        try:
            decoded = json.loads(content_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            failures.append("TASK_CONTENT_NOT_STRICT_JSON")
        else:
            if isinstance(decoded, Mapping):
                payload = decoded
            else:
                failures.append("TASK_CONTENT_NOT_JSON_OBJECT")
    if payload is not None:
        try:
            allowed = set(str(value) for value in node["allowed_fact_ids"])
            if node["task"] == "A":
                validated = c13.validate_task_a(
                    payload,
                    expected_material_id=str(node["expected_material_id"]),
                    allowed_fact_ids=allowed,
                )
                gaps = validated["gaps"]
                summary = {
                    "outline_beat_total": len(validated["outline_beats"]),
                    "gap_total": len(gaps),
                    "missing_bucket_counts": dict(
                        Counter(str(row["missing_bucket"]) for row in gaps)
                    ),
                }
            elif node["task"] == "C":
                validated = c13.validate_task_c(
                    payload,
                    expected_material_id=str(node["expected_material_id"]),
                    allowed_fact_ids=allowed,
                )
                summary = {
                    "rating_total": len(validated["ratings"]),
                    "usability_label_counts": dict(
                        Counter(str(row["label"]) for row in validated["ratings"])
                    ),
                }
            else:
                raise C13ExecutionError(
                    "internal_task_dispatch_error",
                    "task B 不得进入 A/C 通用判定入口",
                )
        except (c13.C13Error, KeyError, TypeError, ValueError) as exc:
            failures.append("TASK_CONTRACT_REJECTED")
            summary = {"contract_error": str(exc)}
    return {
        "accepted": not failures,
        "failure_codes": sorted(set(failures)),
        "provider_response": {
            key: value
            for key, value in envelope.items()
            if key != "content_bytes"
        },
        "task_summary": summary,
    }


def _evaluate_response(
    raw_response: bytes,
    *,
    run_dir: Path,
    node: Mapping[str, Any],
    attempt_no: int,
    previous_raw_sha: set[str],
    previous_response_ids: set[str],
) -> dict[str, Any]:
    raw_sha = sha256_bytes(raw_response)
    if node["task"] == "B":
        verified = r04.persist_observe_and_validate_task_b(
            raw_response,
            ledger_root=run_dir,
            provider_id=str(node["provider_id"]),
            call_id=str(node["base_call_id"]),
            attempt_no=attempt_no,
        )
        contract = _read_json(
            _resolve_recorded_path(str(verified["contract_ledger_path"]))
        )
        validation = contract["validation"]
        accepted = validation["accepted"] is True
        failures: list[str] = []
        provider_response = validation.get("provider_response", {})
        for code in provider_response.get("failure_codes", []):
            failures.append(str(code))
        task_b = validation.get("task_b", {})
        if task_b.get("accepted") is not True:
            failures.append(
                str(task_b.get("failure_code") or "TASK_B_CONTRACT_REJECTED")
            )
        claim = _read_json(
            _resolve_recorded_path(str(verified["claim_ledger_path"]))
        )
        observation = claim["observation"]
        judgment = {
            "accepted": accepted,
            "failure_codes": sorted(set(failures)),
            "provider_response": provider_response,
            "task_summary": {
                "claim_observable": observation.get("observable"),
                "claim_count": observation.get("claim_count"),
                "contract_accepted": accepted,
            },
            "task_b_ledgers": {
                "claim_ledger_path": verified["claim_ledger_path"],
                "contract_ledger_path": verified["contract_ledger_path"],
            },
        }
    else:
        judgment = _extract_generic_task_judgment(
            raw_response,
            node=node,
        )
    metadata = judgment.get("provider_response", {}).get("metadata", {})
    response_id = (
        metadata.get("provider_response_id")
        if isinstance(metadata, Mapping)
        else None
    )
    duplicate_codes: list[str] = []
    if raw_sha in previous_raw_sha:
        duplicate_codes.append("DUPLICATE_RAW_RESPONSE_SHA")
    if isinstance(response_id, str) and response_id in previous_response_ids:
        duplicate_codes.append("DUPLICATE_PROVIDER_RESPONSE_ID")
    if duplicate_codes:
        judgment["accepted"] = False
        judgment["failure_codes"] = sorted(
            set(judgment.get("failure_codes", [])) | set(duplicate_codes)
        )
    judgment["raw_response_sha256"] = raw_sha
    judgment["provider_response_id"] = response_id
    return judgment


def _prior_response_identities(
    run_dir: Path,
    nodes: Sequence[Mapping[str, Any]],
) -> tuple[set[str], set[str]]:
    raw_shas: set[str] = set()
    response_ids: set[str] = set()
    for node in nodes:
        paths = _checkpoint_paths(run_dir, node)
        if not paths["seal"].is_file():
            continue
        seal = _read_json(paths["seal"])
        if seal.get("status") == "SKIPPED_PROVIDER_GATE":
            continue
        judgment = _read_json(paths["judgment"])
        raw_sha = judgment.get("raw_response_sha256")
        response_id = judgment.get("provider_response_id")
        if isinstance(raw_sha, str):
            raw_shas.add(raw_sha)
        if isinstance(response_id, str):
            response_ids.add(response_id)
    return raw_shas, response_ids


def _write_node_checkpoint(
    run_dir: Path,
    *,
    node: Mapping[str, Any],
    request_raw: bytes,
    outcome: TransportOutcome,
    judgment: Mapping[str, Any],
    execution_kind: str,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    paths = _checkpoint_paths(run_dir, node)
    _write_or_verify(paths["request"], request_raw)
    if outcome.raw_response is not None:
        _write_or_verify(paths["response"], outcome.raw_response)
        response_path = paths["response"]
    else:
        absent = {
            "schema_version": "v02-c13-r06-response-absent.v1",
            "node_id": node["node_id"],
            "reason": outcome.kind,
            "error_code": outcome.error_code,
            "detail": outcome.detail,
        }
        _write_or_verify(paths["response_absent"], canonical_bytes(absent))
        response_path = paths["response_absent"]
    judgment_payload = {
        "schema_version": "v02-c13-r06-mechanical-judgment.v1",
        "node_id": node["node_id"],
        "dispatch_id": node["dispatch_id"],
        "provider_id": node["provider_id"],
        "task": node["task"],
        "execution_kind": execution_kind,
        "judgment": copy.deepcopy(dict(judgment)),
        "quality_verdict": "NOT_A_QUALITY_VERDICT",
    }
    _write_or_verify(paths["judgment"], canonical_bytes(judgment_payload))
    usage: Mapping[str, Any] | None = None
    if outcome.raw_response is not None:
        try:
            envelope = json.loads(outcome.raw_response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            envelope = None
        if isinstance(envelope, Mapping) and isinstance(
            envelope.get("usage"),
            Mapping,
        ):
            usage = dict(envelope["usage"])
    attempt_payload = {
        "schema_version": "v02-c13-r06-usage-and-attempt.v1",
        "node_id": node["node_id"],
        "dispatch_id": node["dispatch_id"],
        "attempt_no": 1,
        "started_at": started_at,
        "finished_at": finished_at,
        "max_transport_attempts_per_node": MAX_TRANSPORT_ATTEMPTS_PER_NODE,
        "max_transport_retries_per_node": MAX_TRANSPORT_RETRIES_PER_NODE,
        "transport_kind": outcome.kind,
        "http_status": outcome.http_status,
        "headers": dict(outcome.headers),
        "error_code": outcome.error_code,
        "detail": outcome.detail,
        "request_sha256": sha256_bytes(request_raw),
        "raw_response_sha256": (
            sha256_bytes(outcome.raw_response)
            if outcome.raw_response is not None
            else None
        ),
        "usage": usage if usage is not None else "unknown",
    }
    _write_or_verify(paths["attempt"], canonical_bytes(attempt_payload))
    if outcome.kind != "success" or outcome.http_status != 200:
        status = "HARD_STOP_TRANSPORT"
    elif judgment.get("accepted") is True:
        status = "ACCEPTED"
    else:
        status = "REJECTED_CONTRACT"
    artifact_paths = {
        "request": paths["request"],
        "response_or_absent": response_path,
        "judgment": paths["judgment"],
        "usage_and_attempt": paths["attempt"],
        "attempt_reservation": paths["attempt_reservation"],
        "attempt_response_or_absent": (
            paths["attempt_response"]
            if paths["attempt_response"].is_file()
            else paths["attempt_response_absent"]
        ),
    }
    if isinstance(judgment.get("task_b_ledgers"), Mapping):
        artifact_paths.update(_task_b_evidence_paths(run_dir, node))
    seal = {
        "schema_version": "v02-c13-r06-node-seal.v1",
        "contract_version": CONTRACT_VERSION,
        "node_id": node["node_id"],
        "node_sequence": node["sequence"],
        "dispatch_id": node["dispatch_id"],
        "provider_id": node["provider_id"],
        "base_call_id": node["base_call_id"],
        "task": node["task"],
        "status": status,
        "execution_kind": execution_kind,
        "sealed_at": _now_iso(),
        "node_order_sha256": _read_json(
            run_dir / "prepared/run_plan.json"
        )["node_order_sha256"],
        "artifacts": {
            name: {
                "path": _display_path(path),
                "sha256": sha256_file(path),
            }
            for name, path in artifact_paths.items()
        },
    }
    _write_or_verify(paths["seal"], canonical_bytes(seal))
    _validate_checkpoint(run_dir, node)
    return seal


def _write_hard_stop(
    run_dir: Path,
    *,
    node: Mapping[str, Any],
    reason_code: str,
    detail: str,
) -> dict[str, Any]:
    path = run_dir / "runtime/hard_stop.json"
    payload = {
        "schema_version": "v02-c13-r06-hard-stop.v1",
        "status": "HARD_STOP",
        "reason_code": reason_code,
        "detail": detail,
        "node_id": node["node_id"],
        "dispatch_id": node["dispatch_id"],
        "consecutive_transport_failure_count": 1,
        "consecutive_transport_failure_hard_stop": (
            CONSECUTIVE_TRANSPORT_FAILURE_HARD_STOP
        ),
        "attempted_node_may_be_resent": False,
        "quality_verdict": "NOT_REACHED",
    }
    _write_or_verify(path, canonical_bytes(payload))
    return payload


def execute_with_transport(
    run_dir: Path,
    *,
    transport: Transport,
    execution_kind: str,
    stop_after_completed: int | None = None,
    live_execute_ticket_path: Path | None = None,
    provider_gate_statuses: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """按固定顺序执行；transport 可由测试注入，函数自身不挑结果。"""

    if execution_kind not in {"REHEARSAL_FAKE_TRANSPORT", "LIVE_AUTHORIZED"}:
        raise C13ExecutionError(
            "execution_kind_invalid",
            "execution_kind 只能是假运输预演或已授权真运输",
        )
    if execution_kind == "LIVE_AUTHORIZED":
        ticket = _validate_execute_ticket(run_dir, live_execute_ticket_path)
        ticket_gate_statuses = _provider_gate_statuses_from_ticket(ticket)
        if (
            provider_gate_statuses is not None
            and dict(provider_gate_statuses) != ticket_gate_statuses
        ):
            raise C13ExecutionError(
                "provider_gate_scope_ticket_mismatch",
                "调用方给出的型号闸范围不等于已签 execute 票",
            )
        provider_gate_statuses = ticket_gate_statuses
    elif live_execute_ticket_path is not None:
        raise C13ExecutionError(
            "rehearsal_execute_ticket_forbidden",
            "假运输预演不得携带真执行票",
        )
    gate_scope = _provider_gate_scope(provider_gate_statuses)
    verify_prepared(run_dir)
    plan = _read_json(run_dir / "prepared/run_plan.json")
    position = audit_resume_position(run_dir)
    if position["status"] == "HARD_STOP_NOT_RESUMABLE":
        raise C13ExecutionError(
            "run_already_hard_stopped",
            "本运行已有运输硬停，不得同目录续发",
        )
    if position["status"] == "COMPLETE_90":
        return finalize(run_dir)
    completed = int(position["completed_prefix_count"])
    if stop_after_completed is not None and (
        stop_after_completed < completed
        or stop_after_completed > TOTAL_NODE_HARD_CAP
    ):
        raise C13ExecutionError(
            "stop_after_invalid",
            "stop_after_completed 不在可续跑区间",
        )

    previous_raw_sha, previous_response_ids = _prior_response_identities(
        run_dir,
        plan["nodes"],
    )
    for node in plan["nodes"][completed:]:
        if stop_after_completed is not None and completed >= stop_after_completed:
            return {
                "status": "PAUSED_AT_COMPLETE_CHECKPOINT_BOUNDARY",
                "completed_prefix_count": completed,
                "next_node_id": node["node_id"],
                "attempted_node_may_be_resent": False,
            }
        if completed >= TOTAL_NODE_HARD_CAP:
            raise C13ExecutionError(
                "total_node_cap_exceeded",
                "即将超过整轮 90 题硬帽",
            )
        if node["provider_id"] in gate_scope["skipped_provider_ids"]:
            _write_provider_gate_skip_checkpoint(
                run_dir,
                node=node,
                execution_kind=execution_kind,
            )
            completed += 1
            continue
        provider_done = sum(
            1
            for prior in plan["nodes"][:completed]
            if prior["provider_id"] == node["provider_id"]
        )
        if provider_done >= PER_PROVIDER_NODE_HARD_CAP:
            raise C13ExecutionError(
                "provider_node_cap_exceeded",
                f"{node['provider_id']} 即将超过 30 题硬帽",
            )
        source_request = ROOT / str(node["body_path"])
        request_raw = source_request.read_bytes()
        if sha256_bytes(request_raw) != node["body_sha256"]:
            raise C13ExecutionError(
                "request_sha_drift_before_send",
                f"{node['node_id']} 发送前请求 SHA 漂移",
            )
        paths = _checkpoint_paths(run_dir, node)
        _write_exclusive(paths["request"], request_raw)
        started_at = _now_iso()
        reservation = {
            "schema_version": "v02-c13-r06-attempt-reservation.v1",
            "node_id": node["node_id"],
            "dispatch_id": node["dispatch_id"],
            "attempt_no": 1,
            "request_sha256": sha256_bytes(request_raw),
            "execution_kind": execution_kind,
            "reserved_at": started_at,
            "max_transport_attempts_per_node": (
                MAX_TRANSPORT_ATTEMPTS_PER_NODE
            ),
        }
        _write_exclusive(
            _node_root(run_dir, node)
            / "attempts/attempt_01/00_reservation.json",
            canonical_bytes(reservation),
        )
        try:
            outcome = transport(node, request_raw, 1)
            if not isinstance(outcome, TransportOutcome):
                raise C13ExecutionError(
                    "transport_outcome_invalid",
                    "运输注入点没有返回 TransportOutcome",
                )
        except Exception as exc:  # noqa: BLE001 - 新失败面必须落硬停票
            outcome = TransportOutcome(
                kind="transport_exception",
                http_status=None,
                raw_response=None,
                error_code="UNEXPECTED_TRANSPORT_EXCEPTION",
                detail=f"{type(exc).__name__}: {exc}",
            )
        if outcome.raw_response is not None:
            _write_exclusive(
                _node_root(run_dir, node)
                / "attempts/attempt_01/01_raw_response.raw",
                outcome.raw_response,
            )
        else:
            _write_exclusive(
                _node_root(run_dir, node)
                / "attempts/attempt_01/01_no_response.json",
                canonical_bytes(
                    {
                        "kind": outcome.kind,
                        "error_code": outcome.error_code,
                        "detail": outcome.detail,
                    }
                ),
            )

        if (
            outcome.kind == "success"
            and outcome.http_status == 200
            and outcome.raw_response is not None
        ):
            try:
                judgment = _evaluate_response(
                    outcome.raw_response,
                    run_dir=run_dir,
                    node=node,
                    attempt_no=1,
                    previous_raw_sha=previous_raw_sha,
                    previous_response_ids=previous_response_ids,
                )
            except Exception as exc:  # noqa: BLE001 - 原包已落盘，随后硬停
                outcome = TransportOutcome(
                    kind="judgment_exception",
                    http_status=outcome.http_status,
                    raw_response=outcome.raw_response,
                    headers=outcome.headers,
                    error_code="UNEXPECTED_JUDGMENT_EXCEPTION",
                    detail=f"{type(exc).__name__}: {exc}",
                )
                judgment = {
                    "accepted": False,
                    "failure_codes": ["UNEXPECTED_JUDGMENT_EXCEPTION"],
                    "provider_response": {},
                    "task_summary": {},
                    "raw_response_sha256": sha256_bytes(
                        outcome.raw_response
                    ),
                    "provider_response_id": None,
                }
        else:
            judgment = {
                "accepted": False,
                "failure_codes": [
                    str(outcome.error_code or "TRANSPORT_FAILURE")
                ],
                "provider_response": {},
                "task_summary": {},
                "raw_response_sha256": (
                    sha256_bytes(outcome.raw_response)
                    if outcome.raw_response is not None
                    else None
                ),
                "provider_response_id": None,
            }
        seal = _write_node_checkpoint(
            run_dir,
            node=node,
            request_raw=request_raw,
            outcome=outcome,
            judgment=judgment,
            execution_kind=execution_kind,
            started_at=started_at,
            finished_at=_now_iso(),
        )
        completed += 1
        raw_sha = judgment.get("raw_response_sha256")
        response_id = judgment.get("provider_response_id")
        if isinstance(raw_sha, str):
            previous_raw_sha.add(raw_sha)
        if isinstance(response_id, str):
            previous_response_ids.add(response_id)
        if seal["status"] == "HARD_STOP_TRANSPORT":
            hard_stop = _write_hard_stop(
                run_dir,
                node=node,
                reason_code=str(outcome.error_code or "TRANSPORT_FAILURE"),
                detail=str(outcome.detail or outcome.kind),
            )
            raise C13TransportHardStop(
                str(hard_stop["reason_code"]),
                f"{node['node_id']} 运输失败；最保守连续失败阈值=1，整轮硬停",
            )
    return finalize(run_dir)


def _task_b_floor_pairs(
    run_dir: Path,
    *,
    provider_id: str,
    nodes: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for node in nodes:
        if node["provider_id"] != provider_id or node["task"] != "B":
            continue
        call_id = str(node["base_call_id"])
        pairs.append(
            {
                "claim_ledger_path": str(
                    (
                        run_dir
                        / f"ledgers/claim/{provider_id}/{call_id}/attempt_01.json"
                    ).resolve()
                ),
                "contract_ledger_path": str(
                    (
                        run_dir
                        / f"ledgers/contract/{provider_id}/{call_id}/attempt_01.json"
                    ).resolve()
                ),
            }
        )
    if len(pairs) != 10:
        raise C13ExecutionError(
            "task_b_floor_pair_total_invalid",
            f"{provider_id} 的任务 B 双账不是10对",
        )
    return pairs


def finalize(run_dir: Path) -> dict[str, Any]:
    """从 90 份完整检查点重放收口；不产生路线胜负。"""

    run_dir = run_dir.resolve()
    plan = _read_json(run_dir / "prepared/run_plan.json")
    position = audit_resume_position(run_dir)
    if position["status"] != "COMPLETE_90":
        raise C13ExecutionError(
            "finalize_before_complete_90",
            f"只有90节点完整且无运输硬停才可收口：{position['status']}",
        )
    provider_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    usage_total = 0
    usage_unknown = 0
    missing_buckets: dict[str, Counter[str]] = {
        provider_id: Counter() for provider_id in EXPECTED_PROVIDER_MODELS
    }
    skipped_provider_ids: set[str] = set()
    for node in plan["nodes"]:
        seal = _validate_checkpoint(run_dir, node)
        provider_counts[str(node["provider_id"])] += 1
        status_counts[str(seal["status"])] += 1
        task_counts[str(node["task"])] += 1
        if seal["status"] == "SKIPPED_PROVIDER_GATE":
            skipped_provider_ids.add(str(node["provider_id"]))
            continue
        attempt = _read_json(_checkpoint_paths(run_dir, node)["attempt"])
        usage = attempt.get("usage")
        if isinstance(usage, Mapping) and type(usage.get("total_tokens")) is int:
            usage_total += int(usage["total_tokens"])
        else:
            usage_unknown += 1
        judgment = _read_json(
            _checkpoint_paths(run_dir, node)["judgment"]
        )["judgment"]
        bucket_counts = judgment.get("task_summary", {}).get(
            "missing_bucket_counts",
            {},
        )
        if isinstance(bucket_counts, Mapping):
            for bucket, count in bucket_counts.items():
                if type(count) is int and count >= 0:
                    missing_buckets[str(node["provider_id"])][str(bucket)] += count
    if provider_counts != Counter(
        {provider_id: 30 for provider_id in EXPECTED_PROVIDER_MODELS}
    ):
        raise C13ExecutionError(
            "finalize_provider_denominator_drift",
            "收口时每家不再是30节点",
        )
    if any(
        sum(
            1
            for node in plan["nodes"]
            if node["provider_id"] == provider_id
            and _read_json(_checkpoint_paths(run_dir, node)["seal"])[
                "status"
            ]
            == "SKIPPED_PROVIDER_GATE"
        )
        not in {0, PER_PROVIDER_NODE_HARD_CAP}
        for provider_id in EXPECTED_PROVIDER_MODELS
    ):
        raise C13ExecutionError(
            "finalize_provider_gate_skip_partial",
            "供应商型号闸跳过必须逐家整30题，禁止局部跳过",
        )
    provider_floors = {
        provider_id: (
            {
                "status": PROVIDER_GATE_FAILED,
                "readout_included": False,
                "node_total_sent": 0,
                "node_total_skipped": PER_PROVIDER_NODE_HARD_CAP,
            }
            if provider_id in skipped_provider_ids
            else r04.evaluate_provider_claim_floor(
                _task_b_floor_pairs(
                    run_dir,
                    provider_id=provider_id,
                    nodes=plan["nodes"],
                ),
                provider_id=provider_id,
            )
        )
        for provider_id in EXPECTED_PROVIDER_MODELS
    }
    top3 = {
        provider_id: [
            {"missing_bucket": bucket, "count": count}
            for bucket, count in counts.most_common(3)
        ]
        for provider_id, counts in missing_buckets.items()
    }
    receipt = {
        "schema_version": "v02-c13-r07-finalize-receipt.v1",
        "status": (
            "COMPLETE_PROVIDER_ISOLATED_DIAGNOSTIC_ONLY"
            if skipped_provider_ids
            else "COMPLETE_90_DIAGNOSTIC_ONLY"
        ),
        "diagnostic_tier": "PROVISIONAL_AI_DOWNSTREAM",
        "quality_verdict": "NOT_A_QUALITY_VERDICT",
        "route_winner_declared": False,
        "default_chain_changed": False,
        "gold_changed": False,
        "outbox_written": False,
        "run_id": run_dir.name,
        "runner_sha256": sha256_file(Path(__file__)),
        "run_plan_sha256": sha256_file(run_dir / "prepared/run_plan.json"),
        "node_order_sha256": plan["node_order_sha256"],
        "wire_plan_sha256": EXPECTED_WIRE_PLAN_SHA256,
        "node_total": TOTAL_NODE_HARD_CAP,
        "planned_node_total": TOTAL_NODE_HARD_CAP,
        "sent_node_total": (
            TOTAL_NODE_HARD_CAP
            - len(skipped_provider_ids) * PER_PROVIDER_NODE_HARD_CAP
        ),
        "skipped_node_total": (
            len(skipped_provider_ids) * PER_PROVIDER_NODE_HARD_CAP
        ),
        "skipped_provider_ids": sorted(skipped_provider_ids),
        "unused_quota_reallocated": False,
        "per_provider_node_total": dict(provider_counts),
        "task_node_total": dict(task_counts),
        "node_status_counts": dict(status_counts),
        "usage_total_tokens_known": usage_total,
        "usage_unknown_node_total": usage_unknown,
        "provider_claim_floor_v2": provider_floors,
        "missing_bucket_top3_by_provider": top3,
        "provider_scores_merged_averaged_or_weighted": False,
        "prior_leak_risk_names": True,
    }
    path = run_dir / "final/finalize_receipt.json"
    _write_or_verify(path, canonical_bytes(receipt))
    return {
        **receipt,
        "finalize_receipt_path": _display_path(path),
        "finalize_receipt_sha256": sha256_file(path),
    }


def _valid_fake_payload(node: Mapping[str, Any]) -> dict[str, Any]:
    base = {
        "material_id": node["expected_material_id"],
        "external_knowledge_used": False,
        "task": node["task"],
    }
    if node["task"] == "A":
        return {**base, "outline_beats": [], "gaps": []}
    if node["task"] == "B":
        return {
            **base,
            "answers": [
                {
                    "question_family": family,
                    "status": "MATERIAL_INSUFFICIENT",
                    "answer": "",
                    "supporting_fact_ids": [],
                    "missing_bucket": "FACT_NOT_EXTRACTED",
                    "missing_reason": "假运输预演：材料不足",
                }
                for family in c13.QUESTION_FAMILIES
            ],
        }
    return {
        **base,
        "ratings": [
            {
                "fact_id": fact_id,
                "label": "USABLE",
                "reason": "假运输预演",
            }
            for fact_id in node["allowed_fact_ids"]
        ],
    }


def _fake_envelope(
    node: Mapping[str, Any],
    *,
    response_id: str,
    content: str,
    finish_reason: str = "stop",
) -> bytes:
    return canonical_bytes(
        {
            "id": response_id,
            "model": node["model_id"],
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "reasoning_content": "fake-rehearsal",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "total_tokens": 20,
            },
        }
    )


class RehearsalTransport:
    """确定性假运输；不读取环境变量、不创建网络对象。"""

    def __init__(self, scenario: str = "full"):
        self.scenario = scenario
        self.calls: list[str] = []
        self.first_response: bytes | None = None

    def __call__(
        self,
        node: Mapping[str, Any],
        request_raw: bytes,
        attempt_no: int,
    ) -> TransportOutcome:
        if (
            attempt_no != 1
            or sha256_bytes(request_raw) != node["body_sha256"]
        ):
            raise C13ExecutionError(
                "fake_transport_request_drift",
                "假运输收到的不是冻结请求或第1次尝试",
            )
        self.calls.append(str(node["node_id"]))
        sequence = int(node["sequence"])
        if self.scenario == "timeout_first" and sequence == 1:
            return TransportOutcome(
                kind="timeout",
                http_status=None,
                raw_response=None,
                error_code="SIMULATED_TIMEOUT",
                detail="zero-call timeout probe",
            )
        if sequence == 2:
            raw = _fake_envelope(
                node,
                response_id=f"fake-{node['node_id']}",
                content="not-json",
            )
        elif sequence == 3:
            raw = _fake_envelope(
                node,
                response_id=f"fake-{node['node_id']}",
                content='{"truncated":',
                finish_reason="length",
            )
        elif sequence == 4 and self.first_response is not None:
            raw = self.first_response
        else:
            raw = _fake_envelope(
                node,
                response_id=f"fake-{node['node_id']}",
                content=json.dumps(
                    _valid_fake_payload(node),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
        if sequence == 1:
            self.first_response = raw
        return TransportOutcome(
            kind="success",
            http_status=200,
            raw_response=raw,
            headers={"x-fake-transport": "true"},
        )


def _resolve_recorded_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _require_path_within(path: Path, root: Path, *, label: str) -> Path:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise C13ExecutionError(
            "execute_ticket_artifact_path_out_of_scope",
            f"{label} 不在当前运行预写目录内",
        ) from exc
    return path


def _parse_iso8601(value: Any, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise C13ExecutionError(
            "execute_ticket_time_invalid",
            f"execute 票的 {field_name} 不是有效时间",
        )
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise C13ExecutionError(
            "execute_ticket_time_invalid",
            f"execute 票的 {field_name} 不是 ISO8601 时间",
        ) from exc
    if parsed.tzinfo is None:
        raise C13ExecutionError(
            "execute_ticket_time_invalid",
            f"execute 票的 {field_name} 必须带时区",
        )
    return parsed


def _require_provider_gate_time_order(
    *,
    provider_id: str,
    git_committed_at: datetime,
    started_at: datetime,
    finished_at: datetime,
    execute_approved_at: datetime,
) -> None:
    if not (
        git_committed_at
        < started_at
        <= finished_at
        <= execute_approved_at
    ):
        raise C13ExecutionError(
            "execute_ticket_provider_gate_attempt_time_invalid",
            (
                f"{provider_id} 型号验票时间没有满足"
                " Git冻结<发起<=结束<=execute批准"
            ),
        )


def _git_bytes(*args: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise C13ExecutionError(
            "execute_ticket_git_read_failed",
            f"无法机械回读 Git：git {' '.join(args)}",
        ) from exc
    return completed.stdout


def _git_text(*args: str) -> str:
    return _git_bytes(*args).decode("utf-8").strip()


def _repo_relative_regular_file(value: Any, *, field_name: str) -> tuple[str, Path]:
    if not isinstance(value, str) or not value.strip():
        raise C13ExecutionError(
            "execute_ticket_repo_path_invalid",
            f"{field_name} 缺仓库相对路径",
        )
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise C13ExecutionError(
            "execute_ticket_repo_path_invalid",
            f"{field_name} 必须是仓库内相对路径",
        )
    normalized = candidate.as_posix()
    path = ROOT / normalized
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise C13ExecutionError(
            "execute_ticket_repo_path_invalid",
            f"{field_name} 越出仓库",
        ) from exc
    if path.is_symlink() or not path.is_file():
        raise C13ExecutionError(
            "execute_ticket_repo_file_missing",
            f"{field_name} 不是仓库内普通文件：{normalized}",
        )
    return normalized, path


def _validate_narrow_git_freeze(
    run_dir: Path,
    freeze: Any,
    *,
    approved_at: Any,
) -> dict[str, Any]:
    """回 Git 对象与工作树复核窄提交；不只信 execute 票面。"""

    expected_fields = {
        "commit_sha",
        "committed_at",
        "pushed",
        "allowed_file_manifest_path",
        "allowed_file_manifest_sha256",
    }
    if not isinstance(freeze, Mapping) or set(freeze) != expected_fields:
        raise C13ExecutionError(
            "execute_ticket_git_freeze_invalid",
            "窄 Git 冻结票字段不完整或夹带未定义字段",
        )
    commit_sha = str(freeze["commit_sha"])
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise C13ExecutionError(
            "execute_ticket_git_freeze_invalid",
            "窄 Git 冻结必须写完整 40 位 commit",
        )
    if freeze["pushed"] is not False:
        raise C13ExecutionError(
            "execute_ticket_git_freeze_invalid",
            "权威令要求只提交不推送，pushed 必须为 false",
        )
    resolved_commit = _git_text("rev-parse", "--verify", f"{commit_sha}^{{commit}}")
    current_head = _git_text("rev-parse", "HEAD")
    if resolved_commit != commit_sha or current_head != commit_sha:
        raise C13ExecutionError(
            "execute_ticket_git_head_mismatch",
            "当前 HEAD 不是 execute 票冻结的窄提交",
        )
    git_committed_at_raw = _git_text("show", "-s", "--format=%cI", commit_sha)
    git_committed_at = _parse_iso8601(
        git_committed_at_raw,
        field_name="Git commit 实际时间",
    )
    ticket_committed_at = _parse_iso8601(
        freeze["committed_at"],
        field_name="committed_at",
    )
    approved_time = _parse_iso8601(approved_at, field_name="approved_at")
    if (
        ticket_committed_at != git_committed_at
        or git_committed_at > approved_time
    ):
        raise C13ExecutionError(
            "execute_ticket_git_time_mismatch",
            "提交时间不等于 Git 实物或晚于 execute 批准时间",
        )

    manifest_rel, manifest_path = _repo_relative_regular_file(
        freeze["allowed_file_manifest_path"],
        field_name="allowed_file_manifest_path",
    )
    manifest_raw = manifest_path.read_bytes()
    if sha256_bytes(manifest_raw) != freeze["allowed_file_manifest_sha256"]:
        raise C13ExecutionError(
            "execute_ticket_git_manifest_sha_drift",
            "白名单 manifest 实物 SHA 漂移",
        )
    if _git_bytes("show", f"{commit_sha}:{manifest_rel}") != manifest_raw:
        raise C13ExecutionError(
            "execute_ticket_git_manifest_not_in_commit",
            "白名单 manifest 与冻结 commit 内字节不一致",
        )
    manifest = _read_json(manifest_path)
    schema_version = manifest.get("schema_version")
    if schema_version == "v02-c13-r06-narrow-git-allowlist.v1":
        if (
            set(manifest) != {"schema_version", "files"}
            or not isinstance(manifest.get("files"), list)
            or not manifest["files"]
        ):
            raise C13ExecutionError(
                "execute_ticket_git_manifest_contract_invalid",
                "白名单 manifest 不符合 r06 窄冻结合同",
        )
        changed_rows = list(manifest["files"])
        runtime_rows = list(manifest["files"])
    elif schema_version == "v02-c13-r07-narrow-git-delta-allowlist.v1":
        if (
            set(manifest)
            != {"schema_version", "base_commit_sha", "files", "runtime_files"}
            or not isinstance(manifest.get("files"), list)
            or not manifest["files"]
            or not isinstance(manifest.get("runtime_files"), list)
            or not manifest["runtime_files"]
            or not re.fullmatch(
                r"[0-9a-f]{40}",
                str(manifest.get("base_commit_sha", "")),
            )
        ):
            raise C13ExecutionError(
                "execute_ticket_git_manifest_contract_invalid",
                "白名单 manifest 不符合 r07 增量窄冻结合同",
            )
        expected_parent = str(manifest["base_commit_sha"])
        actual_parent = _git_text("rev-parse", f"{commit_sha}^")
        if actual_parent != expected_parent:
            raise C13ExecutionError(
                "execute_ticket_git_parent_mismatch",
                "r07 窄提交的父提交不等于 r06 冻结点",
            )
        changed_rows = list(manifest["files"])
        runtime_rows = list(manifest["runtime_files"])
    else:
        raise C13ExecutionError(
            "execute_ticket_git_manifest_contract_invalid",
            "白名单 manifest 版本不是 r06 全量或 r07 增量合同",
        )

    seen: set[str] = set()
    changed_seen: set[str] = set()
    expected_sha_by_rel: dict[str, str] = {}
    for source_name, row in [
        *(("changed", row) for row in changed_rows),
        *(("runtime", row) for row in runtime_rows),
    ]:
        if not isinstance(row, Mapping) or set(row) != {"path", "sha256"}:
            raise C13ExecutionError(
                "execute_ticket_git_manifest_contract_invalid",
                "白名单每行只能含 path 与 sha256",
            )
        rel, path = _repo_relative_regular_file(
            row["path"],
            field_name="allowed file path",
        )
        if not _is_sha256(row["sha256"]):
            raise C13ExecutionError(
                "execute_ticket_git_manifest_contract_invalid",
                "白名单 SHA 不是64位小写十六进制",
            )
        if (
            rel in expected_sha_by_rel
            and expected_sha_by_rel[rel] != row["sha256"]
        ):
            raise C13ExecutionError(
                "execute_ticket_git_manifest_contract_invalid",
                "同一白名单文件在改动表与运行表登记了不同 SHA",
            )
        if source_name == "changed" and rel in changed_seen:
            raise C13ExecutionError(
                "execute_ticket_git_manifest_contract_invalid",
                "改动白名单文件重复",
            )
        expected_sha_by_rel[rel] = str(row["sha256"])
        if (
            rel.startswith("config/gold/")
            or "/gold/" in rel
            or re.search(r"(^|/)(?:\\.env|.*secret.*|.*api[_-]?key.*)$", rel, re.I)
        ):
            raise C13ExecutionError(
                "execute_ticket_git_manifest_forbidden_path",
                f"窄提交白名单含金标或密钥路径：{rel}",
            )
        current_raw = path.read_bytes()
        committed_raw = _git_bytes("show", f"{commit_sha}:{rel}")
        if (
            sha256_bytes(current_raw) != row["sha256"]
            or sha256_bytes(committed_raw) != row["sha256"]
            or current_raw != committed_raw
        ):
            raise C13ExecutionError(
                "execute_ticket_git_allowlist_drift",
                f"白名单文件未与 commit／工作树三向一致：{rel}",
            )
        seen.add(rel)
        if source_name == "changed":
            changed_seen.add(rel)
    if not NARROW_GIT_REQUIRED_RUNTIME_PATHS.issubset(seen):
        missing = sorted(NARROW_GIT_REQUIRED_RUNTIME_PATHS - seen)
        raise C13ExecutionError(
            "execute_ticket_git_runtime_path_missing",
            f"窄提交白名单缺运行关键件：{missing}",
        )
    if not any(
        rel.startswith("tests/test_v02_c13_") and rel.endswith(".py")
        for rel in changed_seen
    ):
        raise C13ExecutionError(
            "execute_ticket_git_test_path_missing",
            "窄提交白名单没有 C13 定向测试",
        )
    changed_paths = {
        line
        for line in _git_text(
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit_sha,
        ).splitlines()
        if line
    }
    expected_changed_paths = changed_seen | {manifest_rel}
    if changed_paths != expected_changed_paths:
        raise C13ExecutionError(
            "execute_ticket_git_commit_scope_mismatch",
            "窄提交实际改动路径不等于白名单＋manifest；存在夹带或漏登",
        )

    response_paths = [
        path
        for pattern in (
            "runtime/nodes/*/attempts/attempt_*/01_raw_response.raw",
            "runtime/nodes/*/attempts/attempt_*/01_no_response.json",
        )
        for path in run_dir.glob(pattern)
    ]
    reservation_paths = list(
        run_dir.glob(
            "runtime/nodes/*/attempts/attempt_*/00_reservation.json"
        )
    )
    reservation_times = [
        _parse_iso8601(
            _read_json(path).get("reserved_at"),
            field_name=f"{_display_path(path)}.reserved_at",
        )
        for path in reservation_paths
    ]
    if any(reserved_at <= git_committed_at for reserved_at in reservation_times):
        raise C13ExecutionError(
            "execute_ticket_git_commit_not_before_reservation",
            "窄提交时间没有早于既有题位尝试预留",
        )
    if any(
        datetime.fromtimestamp(path.stat().st_mtime, tz=git_committed_at.tzinfo)
        <= git_committed_at
        for path in response_paths
    ):
        raise C13ExecutionError(
            "execute_ticket_git_commit_not_before_unseal",
            "窄提交时间没有早于既有响应拆封工件",
        )
    return {
        "commit_sha": commit_sha,
        "committed_at": git_committed_at_raw,
        "allowed_file_manifest_path": manifest_rel,
        "allowed_file_manifest_sha256": sha256_bytes(manifest_raw),
        "allowed_file_total": len(seen),
        "runtime_required_file_total": len(
            NARROW_GIT_REQUIRED_RUNTIME_PATHS
        ),
        "response_artifact_total_checked": len(response_paths),
        "reservation_total_checked": len(reservation_paths),
    }


def _validate_execute_ticket(
    run_dir: Path,
    ticket_path: Path | None,
) -> dict[str, Any]:
    """先验执行票；调用方不得用模板或型号子票代替。"""

    if ticket_path is None or not ticket_path.is_file():
        raise C13ExecutionError(
            "execute_ticket_required_before_live_transport",
            "真运输必须先提供全局 execute 票；当前不会读取密钥",
        )
    ticket = _read_json(ticket_path)
    required = {
        "schema_version",
        "status",
        "execute_allowed",
        "run_id",
        "run_path",
        "run_path_identity_sha256",
        "authority_page",
        "approved_to_send_bound",
        "runner_sha256",
        "run_plan_sha256",
        "node_order_sha256",
        "wire_plan_sha256",
        "transport_policy",
        "narrow_git_freeze",
        "zero_call_rehearsal_receipt",
        "key_presence",
        "provider_gate_receipts",
        "provider_gate_failures",
        "approved_at",
    }
    if set(ticket) != required:
        raise C13ExecutionError(
            "execute_ticket_fields_invalid",
            "execute 票字段不完整或夹带未定义字段",
        )
    plan = _read_json(run_dir / "prepared/run_plan.json")
    expected_bound = {
        "r02_prompt_set_sha256": EXPECTED_PROMPT_SET_SHA256,
        "r04_program_sha256": EXPECTED_R04_PROGRAM_SHA256,
        "r04_artifact_set_sha256": EXPECTED_R04_ARTIFACT_SET_SHA256,
    }
    expected_policy = {
        "max_transport_attempts_per_node": MAX_TRANSPORT_ATTEMPTS_PER_NODE,
        "max_transport_retries_per_node": MAX_TRANSPORT_RETRIES_PER_NODE,
        "consecutive_transport_failure_hard_stop": (
            CONSECUTIVE_TRANSPORT_FAILURE_HARD_STOP
        ),
        "per_provider_node_hard_cap": PER_PROVIDER_NODE_HARD_CAP,
        "total_node_hard_cap": TOTAL_NODE_HARD_CAP,
    }
    try:
        run_relative = run_dir.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise C13ExecutionError(
            "execute_ticket_run_path_outside_repo",
            "真运行目录必须在本仓 runs/ 下",
        ) from exc
    if not run_relative.startswith("runs/"):
        raise C13ExecutionError(
            "execute_ticket_run_path_outside_runs",
            "真运行目录必须在本仓 runs/ 下",
        )
    run_identity = {
        "run_id": run_dir.name,
        "run_path": run_relative,
        "node_order_sha256": plan["node_order_sha256"],
    }
    if (
        ticket["schema_version"] != EXECUTE_TICKET_SCHEMA
        or ticket["status"] != "APPROVED_TO_EXECUTE"
        or ticket["execute_allowed"] is not True
        or ticket["run_id"] != run_dir.name
        or ticket["run_path"] != run_relative
        or ticket["run_path_identity_sha256"]
        != sha256_bytes(canonical_bytes(run_identity))
        or ticket["authority_page"] != AUTHORITY_PAGE
        or ticket["approved_to_send_bound"] != expected_bound
        or ticket["runner_sha256"] != sha256_file(Path(__file__))
        or ticket["run_plan_sha256"]
        != sha256_file(run_dir / "prepared/run_plan.json")
        or ticket["node_order_sha256"] != plan["node_order_sha256"]
        or ticket["wire_plan_sha256"] != EXPECTED_WIRE_PLAN_SHA256
        or ticket["transport_policy"] != expected_policy
    ):
        raise C13ExecutionError(
            "execute_ticket_binding_mismatch",
            "execute 票没有精确绑定本 runner／顺序／签字／运输策略",
        )
    git_freeze_receipt = _validate_narrow_git_freeze(
        run_dir,
        ticket["narrow_git_freeze"],
        approved_at=ticket["approved_at"],
    )
    if ticket["key_presence"] != {
        provider_id: True for provider_id in EXPECTED_PROVIDER_MODELS
    }:
        raise C13ExecutionError(
            "execute_ticket_key_presence_invalid",
            "execute 票没有三把密钥存在性布尔证明",
        )
    rehearsal_ref = ticket["zero_call_rehearsal_receipt"]
    if not isinstance(rehearsal_ref, Mapping) or set(rehearsal_ref) != {
        "path",
        "sha256",
        "run_id",
        "runner_sha256",
        "run_plan_sha256",
        "node_order_sha256",
    }:
        raise C13ExecutionError(
            "execute_ticket_rehearsal_ref_invalid",
            "execute 票没有唯一预演票引用",
        )
    rehearsal_path = _resolve_recorded_path(str(rehearsal_ref["path"]))
    if (
        not rehearsal_path.is_file()
        or sha256_file(rehearsal_path) != rehearsal_ref["sha256"]
    ):
        raise C13ExecutionError(
            "execute_ticket_rehearsal_sha_drift",
            "execute 票引用的零调用预演票漂移",
        )
    rehearsal = _read_json(rehearsal_path)
    if (
        rehearsal.get("status") != "PASS_ZERO_CALL_FULL_CHAIN_REHEARSAL"
        or rehearsal.get("run_id") != rehearsal_ref["run_id"]
        or rehearsal.get("runner_sha256") != sha256_file(Path(__file__))
        or rehearsal_ref["runner_sha256"] != sha256_file(Path(__file__))
        or rehearsal.get("run_plan_sha256")
        != sha256_file(run_dir / "prepared/run_plan.json")
        or rehearsal_ref["run_plan_sha256"]
        != sha256_file(run_dir / "prepared/run_plan.json")
        or rehearsal.get("node_order_sha256") != plan["node_order_sha256"]
        or rehearsal_ref["node_order_sha256"] != plan["node_order_sha256"]
        or rehearsal.get("node_total") != TOTAL_NODE_HARD_CAP
        or rehearsal.get("model_api_requests") != 0
        or rehearsal.get("network_attempts") != 0
    ):
        raise C13ExecutionError(
            "execute_ticket_rehearsal_not_pass",
            "execute 票引用的预演票不是 90 节点零调用 PASS",
        )
    gate_refs = ticket["provider_gate_receipts"]
    failure_refs = ticket["provider_gate_failures"]
    if (
        not isinstance(gate_refs, list)
        or not isinstance(failure_refs, list)
        or len(gate_refs) + len(failure_refs) != 3
    ):
        raise C13ExecutionError(
            "execute_ticket_provider_gate_total_invalid",
            "execute 票必须用 PASS 票或失败票恰好覆盖三家型号闸",
        )
    seen: set[str] = set()
    for ref in gate_refs:
        if not isinstance(ref, Mapping) or set(ref) != {
            "provider_id",
            "exact_model_id",
            "attempt_no",
            "attempt_ledger_path",
            "attempt_ledger_sha256",
            "raw_response_path",
            "raw_response_sha256",
            "receipt_path",
            "receipt_sha256",
            "status",
        }:
            raise C13ExecutionError(
                "execute_ticket_provider_gate_fields_invalid",
                "型号子票引用字段不合同",
            )
        provider_id = str(ref["provider_id"])
        if (
            provider_id in seen
            or ref["exact_model_id"] != EXPECTED_PROVIDER_MODELS.get(provider_id)
            or ref["attempt_no"] != 1
            or ref["status"] != EXPECTED_PROVIDER_GATE_STATUS.get(provider_id)
        ):
            raise C13ExecutionError(
                "execute_ticket_provider_gate_identity_invalid",
                "型号子票身份、型号或状态不匹配",
            )
        gate_root = (
            run_dir / "prepared/provider_gates" / provider_id
        ).resolve()
        attempt_path = _require_path_within(
            _resolve_recorded_path(str(ref["attempt_ledger_path"])),
            gate_root,
            label=f"{provider_id} attempt ledger",
        )
        raw_path = _require_path_within(
            _resolve_recorded_path(str(ref["raw_response_path"])),
            gate_root,
            label=f"{provider_id} raw response",
        )
        receipt_path = _require_path_within(
            _resolve_recorded_path(str(ref["receipt_path"])),
            gate_root,
            label=f"{provider_id} receipt",
        )
        if (
            not attempt_path.is_file()
            or sha256_file(attempt_path) != ref["attempt_ledger_sha256"]
            or not raw_path.is_file()
            or sha256_file(raw_path) != ref["raw_response_sha256"]
            or not receipt_path.is_file()
            or sha256_file(receipt_path) != ref["receipt_sha256"]
        ):
            raise C13ExecutionError(
                "execute_ticket_provider_gate_sha_drift",
                f"{provider_id} 型号原始响应或子票实物漂移",
            )
        attempt = _read_json(attempt_path)
        expected_attempt_fields = {
            "schema_version",
            "provider_id",
            "exact_model_id",
            "attempt_no",
            "attempt_total",
            "request_method",
            "request_url",
            "request_body_path",
            "request_body_sha256",
            "raw_response_path",
            "raw_response_sha256",
            "http_status",
            "started_at",
            "finished_at",
            "counts_toward_c13_90_prompt_cap",
        }
        profile = catalog_gate.provider_contract(provider_id)
        request_contract = profile.get("request_contract")
        if not isinstance(request_contract, Mapping):
            raise C13ExecutionError(
                "execute_ticket_provider_gate_request_contract_missing",
                f"{provider_id} 型号闸缺冻结请求合同",
            )
        if (
            not isinstance(attempt, Mapping)
            or set(attempt) != expected_attempt_fields
            or attempt.get("schema_version")
            != "v02-c13-provider-gate-attempt.v1"
            or attempt.get("provider_id") != provider_id
            or attempt.get("exact_model_id") != ref["exact_model_id"]
            or attempt.get("attempt_no") != 1
            or attempt.get("attempt_total") != 1
            or attempt.get("request_method") != request_contract.get("method")
            or attempt.get("request_url") != request_contract.get("url")
            or attempt.get("raw_response_path")
            != str(ref["raw_response_path"])
            or attempt.get("raw_response_sha256")
            != ref["raw_response_sha256"]
            or attempt.get("http_status") != 200
            or attempt.get("counts_toward_c13_90_prompt_cap") is not False
        ):
            raise C13ExecutionError(
                "execute_ticket_provider_gate_attempt_invalid",
                f"{provider_id} 型号验票不是冻结请求的唯一一次独立尝试",
            )
        started_at = _parse_iso8601(
            attempt.get("started_at"),
            field_name=f"{provider_id}.started_at",
        )
        finished_at = _parse_iso8601(
            attempt.get("finished_at"),
            field_name=f"{provider_id}.finished_at",
        )
        git_committed_at = _parse_iso8601(
            git_freeze_receipt["committed_at"],
            field_name="Git commit 实际时间",
        )
        execute_approved_at = _parse_iso8601(
            ticket["approved_at"],
            field_name="approved_at",
        )
        _require_provider_gate_time_order(
            provider_id=provider_id,
            git_committed_at=git_committed_at,
            started_at=started_at,
            finished_at=finished_at,
            execute_approved_at=execute_approved_at,
        )
        if request_contract.get("method") == "POST":
            request_path = _require_path_within(
                _resolve_recorded_path(
                    str(attempt.get("request_body_path"))
                ),
                gate_root,
                label=f"{provider_id} frozen gate request",
            )
            expected_request = catalog_gate.canonical_bytes(
                catalog_gate.frozen_minimal_handshake_body(provider_id)
            )
            if (
                not request_path.is_file()
                or request_path.read_bytes() != expected_request
                or sha256_bytes(expected_request)
                != attempt.get("request_body_sha256")
            ):
                raise C13ExecutionError(
                    "execute_ticket_provider_gate_request_drift",
                    f"{provider_id} 最小握手请求不等于冻结请求",
                )
        elif (
            attempt.get("request_body_path") is not None
            or attempt.get("request_body_sha256") is not None
        ):
            raise C13ExecutionError(
                "execute_ticket_provider_gate_request_drift",
                f"{provider_id} GET /v1/models 不得伪造请求体",
            )
        raw_response = raw_path.read_bytes()
        if sha256_bytes(raw_response) != ref["raw_response_sha256"]:
            raise C13ExecutionError(
                "execute_ticket_provider_gate_raw_sha_drift",
                f"{provider_id} 型号原始响应 SHA 漂移",
            )
        try:
            replayed = catalog_gate.verify_saved_ticket(
                provider_id,
                raw_response,
                attempt_no=int(ref["attempt_no"]),
            )
        except catalog_gate.C13CatalogGateError as exc:
            raise C13ExecutionError(
                "execute_ticket_provider_gate_replay_failed",
                f"{provider_id} 型号原始响应无法离线重放",
            ) from exc
        receipt = _read_json(receipt_path)
        if receipt != replayed:
            raise C13ExecutionError(
                "execute_ticket_provider_gate_receipt_not_reproducible",
                f"{provider_id} 型号子票不是原始响应的确定性重放结果",
            )
        if (
            receipt.get("provider_id") != provider_id
            or receipt.get("exact_model_id") != ref["exact_model_id"]
            or receipt.get("status") != ref["status"]
            or receipt.get("attempt_no") != 1
            or receipt.get("raw_response_sha256")
            != ref["raw_response_sha256"]
            or receipt.get("counts_toward_c13_90_prompt_cap") is not False
            or receipt.get("automatic_fallback_allowed") is not False
        ):
            raise C13ExecutionError(
                "execute_ticket_provider_gate_receipt_invalid",
                f"{provider_id} 型号子票内容不合同",
            )
        seen.add(provider_id)
    for ref in failure_refs:
        if not isinstance(ref, Mapping) or set(ref) != {
            "provider_id",
            "exact_model_id",
            "failure_path",
            "failure_sha256",
            "status",
        }:
            raise C13ExecutionError(
                "execute_ticket_provider_gate_failure_fields_invalid",
                "型号失败票引用字段不合同",
            )
        provider_id = str(ref["provider_id"])
        if (
            provider_id in seen
            or provider_id not in REPLICA_PROVIDER_IDS
            or ref["exact_model_id"] != EXPECTED_PROVIDER_MODELS[provider_id]
            or ref["status"] != PROVIDER_GATE_FAILED
        ):
            raise C13ExecutionError(
                "execute_ticket_provider_gate_failure_identity_invalid",
                "只有复现臂可带精确绑定的型号失败票",
            )
        gate_root = (
            run_dir / "prepared/provider_gates" / provider_id
        ).resolve()
        failure_path = _require_path_within(
            _resolve_recorded_path(str(ref["failure_path"])),
            gate_root,
            label=f"{provider_id} provider gate failure",
        )
        if (
            not failure_path.is_file()
            or not _is_sha256(ref["failure_sha256"])
            or sha256_file(failure_path) != ref["failure_sha256"]
        ):
            raise C13ExecutionError(
                "execute_ticket_provider_gate_failure_sha_drift",
                f"{provider_id} 型号失败票实物漂移",
            )
        failure = _read_json(failure_path)
        if (
            failure.get("provider_id") != provider_id
            or failure.get("exact_model_id")
            != EXPECTED_PROVIDER_MODELS[provider_id]
            or failure.get("status")
            != "HARD_STOP_PROVIDER_DO_NOT_SEND_C13_90_PROMPTS"
            or failure.get("automatic_fallback_allowed") is not False
            or failure.get("network_attempt_total") not in {0, 1}
        ):
            raise C13ExecutionError(
                "execute_ticket_provider_gate_failure_invalid",
                f"{provider_id} 型号失败票不能证明该家独立停用",
            )
        started_at = _parse_iso8601(
            failure.get("started_at"),
            field_name=f"{provider_id}.failed_gate_started_at",
        )
        finished_at = _parse_iso8601(
            failure.get("finished_at"),
            field_name=f"{provider_id}.failed_gate_finished_at",
        )
        _require_provider_gate_time_order(
            provider_id=provider_id,
            git_committed_at=_parse_iso8601(
                git_freeze_receipt["committed_at"],
                field_name="Git commit 实际时间",
            ),
            started_at=started_at,
            finished_at=finished_at,
            execute_approved_at=_parse_iso8601(
                ticket["approved_at"],
                field_name="approved_at",
            ),
        )
        seen.add(provider_id)
    if seen != set(EXPECTED_PROVIDER_MODELS):
        raise C13ExecutionError(
            "execute_ticket_provider_gate_missing",
            "execute 票型号子票缺家或越界",
        )
    _provider_gate_scope(_provider_gate_statuses_from_ticket(ticket))
    _parse_iso8601(ticket["approved_at"], field_name="approved_at")
    if git_freeze_receipt["allowed_file_total"] < len(
        NARROW_GIT_REQUIRED_RUNTIME_PATHS
    ):
        raise C13ExecutionError(
            "execute_ticket_git_allowlist_total_invalid",
            "窄提交白名单数量小于运行关键件数量",
        )
    return dict(ticket)


def _load_live_keys_after_ticket(
    plan: Mapping[str, Any],
    *,
    eligible_provider_ids: Sequence[str] | None = None,
) -> dict[str, str]:
    keys: dict[str, str] = {}
    eligible = (
        list(EXPECTED_PROVIDER_MODELS)
        if eligible_provider_ids is None
        else list(eligible_provider_ids)
    )
    if not set(eligible).issubset(EXPECTED_PROVIDER_MODELS):
        raise C13ExecutionError(
            "eligible_provider_ids_invalid",
            "待发网供应商范围越出冻结三家目录",
        )
    for provider_id in eligible:
        nodes = [
            node for node in plan["nodes"] if node["provider_id"] == provider_id
        ]
        env_names = {str(node["api_key_env"]) for node in nodes}
        if len(env_names) != 1:
            raise C13ExecutionError(
                "provider_key_env_drift",
                f"{provider_id} 的环境变量名不唯一",
            )
        env_name = next(iter(env_names))
        value = os.environ.get(env_name)
        if not value:
            raise C13ExecutionError(
                "provider_key_missing_after_ticket",
                f"{provider_id} 的 {env_name} 未加载",
            )
        keys[provider_id] = value
    return keys


def _live_http_transport(keys: Mapping[str, str]) -> Transport:
    """生成真运输函数；只在 execute 票过闸并读到密钥后调用。"""

    def send(
        node: Mapping[str, Any],
        request_raw: bytes,
        attempt_no: int,
    ) -> TransportOutcome:
        if attempt_no != 1:
            raise C13ExecutionError(
                "live_attempt_cap_exceeded",
                "本版每题总尝试硬顶为1",
            )
        provider_id = str(node["provider_id"])
        request = urllib.request.Request(
            str(node["url"]),
            data=request_raw,
            method="POST",
            headers={
                "Authorization": f"Bearer {keys[provider_id]}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=int(node["timeout_seconds"]),
            ) as response:
                raw = response.read()
                headers = {key: value for key, value in response.headers.items()}
                return TransportOutcome(
                    kind="success",
                    http_status=int(response.status),
                    raw_response=raw,
                    headers=headers,
                )
        except urllib.error.HTTPError as exc:
            return TransportOutcome(
                kind="http_error",
                http_status=int(exc.code),
                raw_response=exc.read(),
                headers={key: value for key, value in exc.headers.items()},
                error_code=f"HTTP_{exc.code}",
                detail=str(exc),
            )
        except TimeoutError as exc:
            return TransportOutcome(
                kind="timeout",
                http_status=None,
                raw_response=None,
                error_code="TIMEOUT",
                detail=str(exc),
            )
        except urllib.error.URLError as exc:
            return TransportOutcome(
                kind="network_error",
                http_status=None,
                raw_response=None,
                error_code="URL_ERROR",
                detail=str(exc),
            )

    return send


def run_live(
    run_dir: Path,
    *,
    execute_ticket_path: Path | None,
) -> dict[str, Any]:
    """真运输入口：execute 票先于密钥读取和任何网络对象。"""

    verify_prepared(run_dir)
    ticket = _validate_execute_ticket(run_dir, execute_ticket_path)
    _write_or_verify(
        run_dir / "runtime/authority/execute_ticket.json",
        canonical_bytes(ticket),
    )
    plan = _read_json(run_dir / "prepared/run_plan.json")
    gate_statuses = _provider_gate_statuses_from_ticket(ticket)
    gate_scope = _provider_gate_scope(gate_statuses)
    keys = _load_live_keys_after_ticket(
        plan,
        eligible_provider_ids=gate_scope["eligible_provider_ids"],
    )
    return execute_with_transport(
        run_dir,
        transport=_live_http_transport(keys),
        execution_kind="LIVE_AUTHORIZED",
        provider_gate_statuses=gate_statuses,
        live_execute_ticket_path=(
            run_dir / "runtime/authority/execute_ticket.json"
        ),
    )


def rehearse(run_dir: Path) -> dict[str, Any]:
    """完成 90 节点假运输预演，并附超时／无票拒绝探针。"""

    run_dir = run_dir.resolve()
    prepare(run_dir)
    full_transport = RehearsalTransport("full")
    paused = execute_with_transport(
        run_dir,
        transport=full_transport,
        execution_kind="REHEARSAL_FAKE_TRANSPORT",
        stop_after_completed=45,
    )
    if (
        paused.get("status") != "PAUSED_AT_COMPLETE_CHECKPOINT_BOUNDARY"
        or paused.get("completed_prefix_count") != 45
    ):
        raise C13ExecutionError(
            "rehearsal_checkpoint_pause_failed",
            "预演没有在完整45节点边界停住",
        )
    completed = execute_with_transport(
        run_dir,
        transport=full_transport,
        execution_kind="REHEARSAL_FAKE_TRANSPORT",
    )

    timeout_dir = run_dir / "rehearsal_probes/timeout_hard_stop"
    prepare(timeout_dir)
    timeout_transport = RehearsalTransport("timeout_first")
    timeout_reason: str | None = None
    try:
        execute_with_transport(
            timeout_dir,
            transport=timeout_transport,
            execution_kind="REHEARSAL_FAKE_TRANSPORT",
        )
    except C13TransportHardStop as exc:
        timeout_reason = exc.reason_code
    if (
        timeout_reason != "SIMULATED_TIMEOUT"
        or len(timeout_transport.calls) != 1
        or audit_resume_position(timeout_dir)["status"]
        != "HARD_STOP_NOT_RESUMABLE"
    ):
        raise C13ExecutionError(
            "rehearsal_timeout_hard_stop_failed",
            "超时探针没有在首节点整轮硬停",
        )

    unsigned_reason: str | None = None
    try:
        _validate_execute_ticket(run_dir, None)
    except C13ExecutionError as exc:
        unsigned_reason = exc.reason_code
    if unsigned_reason != "execute_ticket_required_before_live_transport":
        raise C13ExecutionError(
            "rehearsal_unsigned_live_rejection_failed",
            "无 execute 票没有在密钥与网络前被拒绝",
        )

    single_replica_dir = (
        run_dir / "rehearsal_probes/single_replica_gate_failed"
    )
    prepare(single_replica_dir)
    single_replica_transport = RehearsalTransport("full")
    single_replica = execute_with_transport(
        single_replica_dir,
        transport=single_replica_transport,
        execution_kind="REHEARSAL_FAKE_TRANSPORT",
        provider_gate_statuses={
            "qianwen_platform": "PASS",
            "volcengine_ark": PROVIDER_GATE_FAILED,
            "tencent_tokenhub": "PASS",
        },
    )

    both_replicas_dir = (
        run_dir / "rehearsal_probes/both_replica_gates_failed"
    )
    prepare(both_replicas_dir)
    both_replicas_transport = RehearsalTransport("full")
    both_replicas = execute_with_transport(
        both_replicas_dir,
        transport=both_replicas_transport,
        execution_kind="REHEARSAL_FAKE_TRANSPORT",
        provider_gate_statuses={
            "qianwen_platform": "PASS",
            "volcengine_ark": PROVIDER_GATE_FAILED,
            "tencent_tokenhub": PROVIDER_GATE_FAILED,
        },
    )

    main_failed_dir = run_dir / "rehearsal_probes/main_gate_failed"
    prepare(main_failed_dir)
    main_failed_transport = RehearsalTransport("full")
    main_failed_reason: str | None = None
    try:
        execute_with_transport(
            main_failed_dir,
            transport=main_failed_transport,
            execution_kind="REHEARSAL_FAKE_TRANSPORT",
            provider_gate_statuses={
                "qianwen_platform": PROVIDER_GATE_FAILED,
                "volcengine_ark": "PASS",
                "tencent_tokenhub": "PASS",
            },
        )
    except C13ExecutionError as exc:
        main_failed_reason = exc.reason_code

    rejected_codes: Counter[str] = Counter()
    for node in _read_json(run_dir / "prepared/run_plan.json")["nodes"]:
        judgment = _read_json(
            _checkpoint_paths(run_dir, node)["judgment"]
        )["judgment"]
        for code in judgment.get("failure_codes", []):
            rejected_codes[str(code)] += 1
    required_observations = {
        "normal_json": completed["node_status_counts"].get("ACCEPTED", 0) > 0,
        "non_json": (
            rejected_codes["PROVIDER_RESPONSE_CONTENT_NOT_STRICT_JSON"] > 0
            or rejected_codes["TASK_CONTENT_NOT_STRICT_JSON"] > 0
        ),
        "truncated": (
            rejected_codes["PROVIDER_RESPONSE_FINISH_REASON_NOT_STOP"] > 0
        ),
        "duplicate_response": (
            rejected_codes["DUPLICATE_RAW_RESPONSE_SHA"] > 0
            or rejected_codes["DUPLICATE_PROVIDER_RESPONSE_ID"] > 0
        ),
        "timeout_hard_stop": timeout_reason == "SIMULATED_TIMEOUT",
        "checkpoint_resume": paused["completed_prefix_count"] == 45,
        "unsigned_live_denied": unsigned_reason
        == "execute_ticket_required_before_live_transport",
        "single_replica_gate_failure_isolated": (
            len(single_replica_transport.calls) == 60
            and single_replica.get("sent_node_total") == 60
            and single_replica.get("skipped_node_total") == 30
            and single_replica.get("skipped_provider_ids")
            == ["volcengine_ark"]
            and single_replica.get("unused_quota_reallocated") is False
        ),
        "both_replica_gate_failures_isolated": (
            len(both_replicas_transport.calls) == 30
            and both_replicas.get("sent_node_total") == 30
            and both_replicas.get("skipped_node_total") == 60
            and both_replicas.get("skipped_provider_ids")
            == ["tencent_tokenhub", "volcengine_ark"]
            and both_replicas.get("unused_quota_reallocated") is False
        ),
        "main_gate_failure_stops_before_transport": (
            main_failed_reason == "main_provider_gate_failed"
            and len(main_failed_transport.calls) == 0
            and audit_resume_position(main_failed_dir)[
                "completed_prefix_count"
            ]
            == 0
        ),
    }
    if not all(required_observations.values()):
        raise C13ExecutionError(
            "rehearsal_required_scenarios_missing",
            f"假运输没有覆盖全部必测场景：{required_observations}",
        )
    receipt = {
        "schema_version": "v02-c13-r07-zero-call-rehearsal.v1",
        "status": "PASS_ZERO_CALL_FULL_CHAIN_REHEARSAL",
        "run_id": run_dir.name,
        "runner_sha256": sha256_file(Path(__file__)),
        "run_plan_sha256": sha256_file(run_dir / "prepared/run_plan.json"),
        "node_order_sha256": completed["node_order_sha256"],
        "node_total": completed["node_total"],
        "per_provider_node_total": completed["per_provider_node_total"],
        "max_transport_attempts_per_node": MAX_TRANSPORT_ATTEMPTS_PER_NODE,
        "max_transport_retries_per_node": MAX_TRANSPORT_RETRIES_PER_NODE,
        "consecutive_transport_failure_hard_stop": (
            CONSECUTIVE_TRANSPORT_FAILURE_HARD_STOP
        ),
        "scenarios": required_observations,
        "paused_after_complete_checkpoint_total": 45,
        "resumed_from_node": "C13-R06-046",
        "timeout_probe_call_total": len(timeout_transport.calls),
        "timeout_probe_hard_stop_reason": timeout_reason,
        "unsigned_live_rejection_reason": unsigned_reason,
        "single_replica_gate_failure_transport_call_total": len(
            single_replica_transport.calls
        ),
        "both_replica_gate_failure_transport_call_total": len(
            both_replicas_transport.calls
        ),
        "main_gate_failure_transport_call_total": len(
            main_failed_transport.calls
        ),
        "main_gate_failure_reason": main_failed_reason,
        "model_api_requests": 0,
        "network_attempts": 0,
        "key_values_read": 0,
        "quality_verdict": "NOT_A_QUALITY_VERDICT",
    }
    path = run_dir / "rehearsal/rehearsal_receipt.json"
    _write_or_verify(path, canonical_bytes(receipt))
    return {
        **receipt,
        "rehearsal_receipt_path": _display_path(path),
        "rehearsal_receipt_sha256": sha256_file(path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "prepare",
            "verify",
            "status",
            "rehearse",
            "run",
            "resume",
            "finalize",
        ),
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--execute-ticket", type=Path)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(args.run_dir)
    elif args.command == "verify":
        result = verify_prepared(args.run_dir)
    elif args.command == "status":
        result = audit_resume_position(args.run_dir)
    elif args.command == "rehearse":
        result = rehearse(args.run_dir)
    elif args.command in {"run", "resume"}:
        result = run_live(
            args.run_dir,
            execute_ticket_path=args.execute_ticket,
        )
    else:
        result = finalize(args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

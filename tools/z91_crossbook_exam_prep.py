#!/usr/bin/env python3
"""第91道步一：冻结跨书同卷、云平台 Pro 适配候选与无金标判分尺。

本工具只构造文件，不加载密钥、不访问网络、不调用模型。步二须在 Notion 审收并
拍定判分尺及 Pro 通道后，另由通用模型横测薄壳发送。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import z68_revised_request_pilot as z68
import z79_fact_sheet_v3_pilot as z79
import z80_fact_sheet_v4_crossbook_pilot as z80
from zbatch_modules.evidence_catalog import (
    build_evidence_catalog,
    evidence_catalog_coverage,
    nonspace_chars,
)
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "Z91_双臂跨书基线_步一试卷_v1.2_20260723"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_ID
ADAPTERS_PATH = ROOT / "config/model_benchmarks/provider_adapters.json"
ACCESS_POLICY_PATH = ROOT / "config/providers/provider_access_policy.json"
TEMPLATE_PATH = ROOT / (
    "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry03/"
    "prepared_requests/ch0003.json"
)
TEMPLATE_SHA256 = "18fe2a9e9d2f0a4d48b5b4de29803a90c0db0fe1087080ff8f68d00b81e98eb4"
PROMPT_PACKAGE_PATH = ROOT / (
    "runs/Z79_X01_事实说明书注入包v3_三章复验_v1.0_20260721_transport_retry01/"
    "prompt_candidates/事实说明书注入包_v3.json"
)
PROMPT_PACKAGE_SHA256 = "a302920537349d37c75d5bac9df19a83bfab667891458ef65de9d98e84bc2116"

SELECTED_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_key": "X02-C0031",
        "book_id": "X02",
        "book": "十日终焉",
        "chapter": 31,
        "source": "TEMP/X批材料包_20260716/books/X02_十日终焉/chapters/0031_第31章_鼠类游戏.txt",
        "source_sha256": "c1eed251e687332b49fb709565f9a70620e262527212824468c9a160cb491da1",
        "selection_reason": "现代悬疑游戏章；对话、规则、推理、失败与新决策连续出现，专测条件和行动结果是否被压缩。",
        "probe_seeds": (
            ("background", "第一次主动参与游戏"),
            ("cognition", "不提前知晓游戏类型"),
            ("action", "直接将一个货架推倒"),
            ("state_change", "关闭了白炽灯"),
            ("condition", "还剩十秒"),
            ("rule", "门票需要消耗一个「道」"),
        ),
    },
    {
        "case_key": "X03-C0019",
        "book_id": "X03",
        "book": "清河仙族",
        "chapter": 19,
        "source": "TEMP/X批材料包_20260716/books/X03_清河仙族/chapters/0019_第19章_金网伏妖.txt",
        "source_sha256": "dc72f94776344a69e00c0635cf823501f7adf5f14785aa6b10fda91e95b9e3fc",
        "selection_reason": "群体战斗与战利品分配章；多主体、因果链、命令和暗中行动密集，专测主体归属与原子化。",
        "probe_seeds": (
            ("causal_action", "给二长老宋长风创造机会"),
            ("condition", "十六名阵法师的驱动之下"),
            ("command", "大喊一声“变阵”"),
            ("allocation_rule", "二级妖兽归我刘家"),
            ("hidden_action", "暗中传了一道密音"),
            ("inference", "手札中记载“水灵果树”"),
        ),
    },
    {
        "case_key": "X04-C0046",
        "book_id": "X04",
        "book": "仙笼",
        "chapter": 46,
        "source": "TEMP/X批材料包_20260716/books/X04_仙笼/chapters/0046_第46章_符钱灵石体系.txt",
        "source_sha256": "ec92bbf4f47f0fa94a0d3f35fa89ad50c21484a64bb321d2e29f02e15c471b00",
        "selection_reason": "设定说明、历史沿革、人物计划和末尾情报并存，专测背景事实、长期规则与当章行动能否分开。",
        "probe_seeds": (
            ("rank_rule", "九品境界的道童们"),
            ("history", "符钱这种东西"),
            ("state", "攥紧了袖子中的两枚灵石"),
            ("goal", "关键药物，缺一不可"),
            ("resource_rule", "有一缕灵气作为补贴"),
            ("revelation", "下了狠注"),
        ),
    },
)

PROVIDER_ARMS: tuple[dict[str, str], ...] = (
    {
        "arm_id": "pro_primary_tencent",
        "provider": "tencent_tokenhub",
        "model_id": "deepseek-v4-pro-202606",
        "profile_id": "deepseek_v4_pro_medium_prompt_json",
        "role": "recommended_primary_pending_step2_approval",
    },
    {
        "arm_id": "pro_standby_qianwen",
        "provider": "qianwen_platform",
        "model_id": "deepseek-v4-pro",
        "profile_id": "deepseek_v4_pro_medium_prompt_json",
        "role": "standby_new_run_only_no_automatic_failover",
    },
    {
        "arm_id": "pro_standby_volcengine",
        "provider": "volcengine_ark",
        "model_id": "deepseek-v4-pro-260425",
        "profile_id": "deepseek_v4_pro_medium_prompt_json",
        "role": "standby_new_run_only_no_automatic_failover",
    },
)

FORBIDDEN_VISIBLE_MARKERS = (
    "GOLD-C0003-",
    "structure-gold-v1.2",
    "严格命中",
    "semantic_shadow",
    "第3章结构层金标",
    "现役122条",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ZBatchError(f"JSON 顶层不是对象：{path}")
    return value


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_exclusive(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _assert_pin(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or sha256_file(path) != expected:
        raise ZBatchError(f"{label}缺失或 SHA 漂移：{path}")


def _parse_chapter(spec: Mapping[str, Any]) -> tuple[str, str, bytes]:
    source = ROOT / str(spec["source"])
    raw = source.read_bytes()
    if sha256_bytes(raw) != spec["source_sha256"]:
        raise ZBatchError(f"{spec['case_key']} X批源文件 SHA 漂移")
    text = raw.decode("utf-8")
    heading, separator, tail = text.partition("\n")
    if not separator or not heading.strip():
        raise ZBatchError(f"{spec['case_key']} 源文件缺章头")
    body = tail.lstrip("\r\n")
    if not body.strip():
        raise ZBatchError(f"{spec['case_key']} 正文为空")
    return heading.rstrip("\r"), body, raw


def _build_catalog(spec: Mapping[str, Any], body: str) -> dict[str, Any]:
    chapter = int(spec["chapter"])
    first = build_evidence_catalog(chapter, body)
    second = build_evidence_catalog(chapter, body)
    if first != second:
        raise ZBatchError(f"{spec['case_key']} 证据目录两次生成不一致")
    coverage = evidence_catalog_coverage(body, first)
    expected_ids = [f"E{index:04d}" for index in range(1, len(first) + 1)]
    if (
        coverage != 1.0
        or [row["anchor_id"] for row in first] != expected_ids
        or any(str(row["quote"]) not in body for row in first)
        or any(not 10 <= nonspace_chars(str(row["quote"])) <= 25 for row in first)
    ):
        raise ZBatchError(f"{spec['case_key']} 冻结证据目录机械闸失败")
    return {
        "schema_version": "z91-frozen-evidence-catalog-v1",
        "book_id": spec["book_id"],
        "book": spec["book"],
        "chapter": chapter,
        "coverage": coverage,
        "entries": first,
    }


def _instantiate_messages(
    spec: Mapping[str, Any], body: str, catalog: Mapping[str, Any], filename: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    material = {"text": body, "filename": filename, "catalog": catalog}
    z80_spec = {
        "case_key": spec["case_key"],
        "book_id": spec["book_id"],
        "book": spec["book"],
        "unit": spec["chapter"],
        "kind": "crossbook",
    }
    template_body, diff = z80._instantiate_crossbook_v3(z80_spec, material)
    messages = copy.deepcopy(template_body["messages"])
    visible = "\n".join(row["content"] for row in messages)
    hits = [marker for marker in FORBIDDEN_VISIBLE_MARKERS if marker in visible]
    if hits:
        raise ZBatchError(f"{spec['case_key']} 请求夹入判分材料：{hits}")
    if z68.extract_text_payload(messages[1]["content"]) != body:
        raise ZBatchError(f"{spec['case_key']} 连续正文实例化漂移")
    if z68.extract_catalog_payload(messages[1]["content"]) != z68.compact_catalog(
        catalog["entries"]
    ):
        raise ZBatchError(f"{spec['case_key']} 冻结目录实例化漂移")
    return messages, diff


def _resolve_profile(arm: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    adapters = read_json(ADAPTERS_PATH)
    provider_adapter = adapters.get("providers", {}).get(arm["provider"])
    if not isinstance(provider_adapter, dict):
        raise ZBatchError(f"供应商未登记：{arm['provider']}")
    config_path = ROOT / str(provider_adapter["provider_config"])
    provider = read_json(config_path)
    models = [
        row
        for row in provider.get("models", [])
        if isinstance(row, dict) and row.get("model_id") == arm["model_id"]
    ]
    if len(models) != 1 or models[0].get("call_ready") is not True:
        raise ZBatchError(f"模型未按精确 ID 准入：{arm['provider']}／{arm['model_id']}")
    profile = provider_adapter.get("profiles", {}).get(arm["profile_id"])
    if not isinstance(profile, dict) or arm["model_id"] not in profile.get(
        "validated_model_ids", []
    ):
        raise ZBatchError(f"模型与兼容档未配对：{arm['provider']}／{arm['model_id']}")
    return provider, profile


def _apply_profile(
    base: Mapping[str, Any], arm: Mapping[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    provider, profile = _resolve_profile(arm)
    body = copy.deepcopy(dict(base))
    body["model"] = arm["model_id"]
    for field in profile.get("drop_fields", []):
        body.pop(str(field), None)
    for field, value in profile.get("set_fields", {}).items():
        body[str(field)] = copy.deepcopy(value)
    for field in profile.get("keep_fields", []):
        if body.get(field) != base.get(field):
            raise ZBatchError(f"兼容档保持字段漂移：{arm['arm_id']}／{field}")
    if body["messages"] != base["messages"]:
        raise ZBatchError(f"{arm['arm_id']} 模型可见消息漂移")
    if profile.get("single_sample_via_response_gate") is True:
        if "n" in body:
            raise ZBatchError(f"{arm['arm_id']} 仍夹带 n")
    elif body.get("n") != 1:
        raise ZBatchError(f"{arm['arm_id']} 单次采样字段漂移")
    return body, {
        "schema_version": "z91-provider-compatibility-diff-v1",
        "arm_id": arm["arm_id"],
        "role": arm["role"],
        "provider": provider["provider"],
        "model_id": arm["model_id"],
        "profile_id": arm["profile_id"],
        "key_env": provider["api_key_env"],
        "messages_byte_equal": canonical_bytes(body["messages"])
        == canonical_bytes(base["messages"]),
        "messages_sha256": canonical_sha(body["messages"]),
        "changed_top_level_fields": sorted(
            key
            for key in set(base) | set(body)
            if base.get(key) != body.get(key)
        ),
        "compatibility_notes": profile.get("compatibility_notes", []),
        "send_status": "locked_pending_z91_step1_rubric_and_provider_approval",
    }


def _probe_slots(
    spec: Mapping[str, Any], catalog: Mapping[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (category, needle) in enumerate(spec["probe_seeds"], 1):
        matches = [row for row in catalog["entries"] if needle in row["quote"]]
        if len(matches) != 1:
            raise ZBatchError(
                f"{spec['case_key']} 探针种子未唯一命中：{category}／{needle}／{len(matches)}"
            )
        rows.append(
            {
                "probe_id": f"{spec['case_key']}-P{index:02d}",
                "category": category,
                "anchor_id": matches[0]["anchor_id"],
                "source_quote": matches[0]["quote"],
                "source_fact": None,
                "status": "slot_frozen_fact_pending_rubric_approval",
                "truth_role": "source_probe_not_gold_not_recall_denominator",
            }
        )
    return rows


def rubric_candidate() -> dict[str, Any]:
    return {
        "schema_version": "z91-crossbook-blind-probe-rubric-candidate-v1",
        "status": "candidate_pending_cz_approval_step2_locked",
        "name": "跨书盲审探针差分尺 v0 候选",
        "truth_boundary": [
            "这些章节没有正式金标，禁止报告严格命中率、召回率或正式准确率。",
            "每章六个探针槽只冻结来源位置；CZ 审尺后、模型发网前由两名复核者独立写出来源事实并封存SHA，不能看双臂输出，也不能反向进入模型请求。",
            "双臂输出先匿名化再语义复核，回包件仍是银标观察件。",
        ],
        "per_chapter_human_budget": {
            "source_probe_facts": 6,
            "output_fact_groups": 12,
            "total_judgments": 18,
            "three_chapter_total": 54,
            "independent_reviewers": 2,
            "planned_review_actions": 108,
            "disagreement_rule": "两名复核者任一字段不同即交第三名只看该字段裁决，原始两票不回写。",
        },
        "arm_blinding": {
            "labels": ["A", "B"],
            "mapping_rule": "每章取 sha256(case_key|messages_sha256) 的首位十六进制；偶数时Flash=A，奇数时Flash=B。映射票单独封存，语义复核完成前不展示。",
            "input_to_reviewers": "只给匿名事件、锚与冻结正文，不给模型名、usage、耗时或历史成绩。",
        },
        "output_group_sampling_algorithm": {
            "step_1": "两名复核者在盲臂条件下把语义同一事实对齐为等价组；分歧交第三名裁决。",
            "event_key": "每条事件以 sha256(canonical_json({event, sorted_unique_anchor_ids})) 定身份。",
            "group_key": "每个等价组以成员 event_key 升序数组的 sha256 定身份。",
            "strata": ["both_arms", "A_only", "B_only"],
            "selection": "每层按 group_key 升序先取4组；某层不足4组时，缺额依次从 both_arms、A_only、B_only 尚未入选组的 group_key 升序池补齐，已选组跳过。",
            "short_total": "三层全部组仍不足12时全部复核，分母用实际组数；实际组数少于8时只报描述账，不判方向领先。",
            "no_cherry_pick": "任何人工不能按质量好坏换组；抽样清单与全部候选 group_key 一并回传。",
        },
        "judgment_dimensions": [
            "原文明示事实是否被完整抽出",
            "一条是否只装一个事实，主体／动作／结果／明示限定是否齐",
            "是否过度合并、漏掉条件、把推断写成事实或改变认知强度",
            "所挂锚对事件关键主张是完整支撑、部分支撑还是不支撑",
        ],
        "reported_metrics": [
            "机械三闸",
            "锚不托条数与比例",
            "来源探针覆盖数／6（只叫覆盖，不叫召回）",
            "抽样原子事实完整数／实际抽样组数",
            "Flash 与 Pro 同事实、各自独有及退化差分",
            "逐章 token、耗时、finish_reason 与运输账",
        ],
        "scoring_formulas": {
            "source_probe_hit": "该探针事实的主体、动作／状态、结果及原文明示限定全部出现，且至少一条所挂锚完整支撑；否则记partial或miss，只有hit计入覆盖。",
            "probe_coverage": "每臂 hit_count/6；partial与miss逐条另列。",
            "atomic_complete": "选中等价组中，该臂存在单一原子事件，主体＋动作／状态＋结果＋原文明示限定齐全，未混入第二事实，且锚完整支撑时计1，否则计0。",
            "atomic_completeness_rate": "atomic_complete_count/actual_sampled_group_count。缺席组计0。",
            "anchor_non_support_rate": "选中组内该臂被审事件中，关键主张没有被任一所挂锚完整支撑的事件数/该臂被审事件总数。",
            "semantic_error_count": "编造、改认知强度、错主体、错因果每组至多计1，同时保留多标签明细。",
        },
        "directional_lead_rule": {
            "minimum_books": 2,
            "pro_probe_gain": "至少2本书的 Pro hit_count-Flash hit_count≥2，且第三本不得小于0。",
            "atomic_completeness": "三章合计 Pro atomic_complete_count≥Flash，且任何单章 Pro 不得比 Flash 低2组或以上。",
            "anchor_support": "每臂先将三章锚不托事件数相加作分子、三章被审事件数相加作分母，用总分子/总分母算加权率；Pro加权率≤Flash，且不得新增正文编造或认知强度错误。分母为0时该轮只报描述账。",
            "final_state": "上述所有条件全满足且三章分母均有效时，唯一结果记 pro_directional_lead；其余情况统一记 no_crossbook_pro_lead，只在明细列不足条件，不再使用‘平局／不稳定／明显反向’等可二次解释的状态词。",
            "minimum_sample": "任一章实际抽样组数少于8，只报描述账，整轮不得判方向领先。",
        },
        "production_candidate_extra_gate": [
            "Pro 抽样锚不托必须为0",
            "不得出现新语义失败面",
            "所有机械闸全过",
            "仍只上桌，不自动固化或升默认",
        ],
        "invalid_sample_rules": [
            "冻结正文、目录或 messages SHA 不一致",
            "finish_reason 异常或输出截断",
            "非法／目录外锚或机械合同失败",
            "单章只判无效，不重跑挑结果",
        ],
        "hard_stop_rules": [
            "新增正文没有的事实",
            "改变认知／意愿／推断强度",
            "结构越权或金标／答案进入请求",
        ],
    }


def provider_plan() -> dict[str, Any]:
    policy = read_json(ACCESS_POLICY_PATH)
    official = policy.get("providers", {}).get("deepseek_official", {})
    if official.get("default_action") != "deny" or "permanently_disabled" not in str(
        official.get("status")
    ):
        raise ZBatchError("DeepSeek 官方永久禁用策略漂移")
    return {
        "schema_version": "z91-cloud-pro-provider-plan-v1",
        "status": "candidate_pending_step2_approval_no_network",
        "user_correction": "Pro 只能取三家已配置云平台额度；当前没有正向要求使用 DeepSeek 官方 API，官方直连永久禁用。",
        "official_deepseek_api": "forbidden_not_a_fallback",
        "one_provider_per_round_rule": "同一轮 Pro 三章必须全用同一家平台；不得按章混平台，不得跨平台自动故障转移。换平台须另开运行编号并重新并列条件。",
        "recommended_primary": {
            "provider": "tencent_tokenhub",
            "model_id": "deepseek-v4-pro-202606",
            "reason": "固定版本、三章可同一精确型号，medium 在该平台明确映射为实际 high；现有 TokenHub 配额可用。发网前仍须 GET /v1/models 确认精确型号 online。",
            "quota_estimate": "按 Z89 单章约37226总token粗估，三章约111678 token；腾讯202606固定版按当前Token Plan文档1 token≈1点，仅作额度预估，实际以usage和控制台为准。",
        },
        "standbys": [
            {
                "provider": "qianwen_platform",
                "model_id": "deepseek-v4-pro",
                "caveat": "当前钥匙登记为标准按量通道，不冒充Token Plan；不支持response_format与n，需本地JSON闸。",
            },
            {
                "provider": "volcengine_ark",
                "model_id": "deepseek-v4-pro-260425",
                "caveat": "公开能力表未确认该型号支持结构化输出，且medium不映射high；只能作为另开轮次的条件成绩。",
            },
        ],
        "step1_transport": {
            "model_api_calls": 0,
            "network_attempts": 0,
            "tokens": 0,
            "keys_loaded": False,
        },
        "step2_release_gate": [
            "CZ／云端审收并拍定无金标判分尺",
            "拍定本轮唯一 Pro 平台和精确 model_id",
            "主平台在线模型目录闸通过",
            "同卷 messages SHA 复验通过",
        ],
    }


def _protection_snapshot() -> dict[str, Any]:
    protected = z79.assert_protected()["formal_and_z75"]
    return {
        "formal": protected["formal"],
        "outbox": protected["outbox"],
        "z75_untracked_artifacts": protected["z75_untracked_artifacts"],
    }


def _source_pin(path: Path, role: str) -> dict[str, Any]:
    if not path.is_file():
        raise ZBatchError(f"源钉文件不存在：{path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(path),
        "role": role,
    }


def build_payloads() -> tuple[dict[str, bytes], dict[str, Any]]:
    _assert_pin(TEMPLATE_PATH, TEMPLATE_SHA256, "v3第3章请求模板")
    _assert_pin(PROMPT_PACKAGE_PATH, PROMPT_PACKAGE_SHA256, "v3注入包")
    payloads: dict[str, bytes] = {}
    selections: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    message_shas: dict[str, str] = {}
    request_matrix: list[dict[str, Any]] = []

    for spec in SELECTED_CASES:
        heading, body, raw = _parse_chapter(spec)
        catalog = _build_catalog(spec, body)
        source_name = Path(str(spec["source"])).name
        messages, instantiation_diff = _instantiate_messages(
            spec, body, catalog, source_name
        )
        message_sha = canonical_sha(messages)
        message_shas[str(spec["case_key"])] = message_sha
        base = {
            "model": "deepseek-v4-flash",
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 32000,
            "n": 1,
            "response_format": {"type": "json_object"},
            "reasoning_effort": "medium",
        }
        case_dir = f"cases/{spec['case_key']}"
        payloads[f"{case_dir}/source_original.txt"] = raw
        payloads[f"{case_dir}/chapter_body.txt"] = body.encode("utf-8")
        payloads[f"{case_dir}/evidence_catalog.json"] = json_bytes(catalog)
        payloads[f"{case_dir}/messages.json"] = json_bytes(messages)
        payloads[f"{case_dir}/instantiation_diff.json"] = json_bytes(
            instantiation_diff
        )
        payloads[f"{case_dir}/requests/flash_sensenova.json"] = json_bytes(base)
        request_matrix.append(
            {
                "case_key": spec["case_key"],
                "arm_id": "flash_sensenova",
                "provider": "sensenova",
                "model_id": "deepseek-v4-flash",
                "messages_sha256": message_sha,
                "request_status": "frozen_step2_locked",
            }
        )
        for arm in PROVIDER_ARMS:
            candidate, diff = _apply_profile(base, arm)
            payloads[
                f"{case_dir}/requests/{arm['arm_id']}.json"
            ] = json_bytes(candidate)
            payloads[
                f"{case_dir}/requests/{arm['arm_id']}_compatibility_diff.json"
            ] = json_bytes(diff)
            request_matrix.append(
                {
                    "case_key": spec["case_key"],
                    "arm_id": arm["arm_id"],
                    "provider": arm["provider"],
                    "model_id": arm["model_id"],
                    "messages_sha256": diff["messages_sha256"],
                    "messages_byte_equal_to_flash": diff["messages_byte_equal"],
                    "request_status": diff["send_status"],
                }
            )
        case_probes = _probe_slots(spec, catalog)
        probes.extend(case_probes)
        selections.append(
            {
                "case_key": spec["case_key"],
                "book_id": spec["book_id"],
                "book": spec["book"],
                "chapter": spec["chapter"],
                "heading": heading,
                "source_path": spec["source"],
                "source_file_sha256": spec["source_sha256"],
                "frozen_body_sha256": sha256_bytes(body.encode("utf-8")),
                "frozen_body_nonspace_chars": nonspace_chars(body),
                "catalog_entry_count": len(catalog["entries"]),
                "catalog_entries_sha256": canonical_sha(catalog["entries"]),
                "catalog_coverage": catalog["coverage"],
                "messages_sha256": message_sha,
                "selection_reason": spec["selection_reason"],
                "probe_slot_count": len(case_probes),
            }
        )

    if any(not row.get("messages_byte_equal_to_flash", True) for row in request_matrix):
        raise ZBatchError("云平台候选请求与 Flash 的模型可见消息不一致")
    selection_doc = {
        "schema_version": "z91-crossbook-exam-selection-v1",
        "status": "step1_frozen_step2_locked",
        "selection_rule": "三本异质题材各取一章；X01第3章不入卷；只覆盖方向性跨书复验，不冒充总体泛化。",
        "cases": selections,
    }
    probe_doc = {
        "schema_version": "z91-source-probe-slots-v1",
        "status": "locations_frozen_answers_pending_rubric_approval",
        "seed": "z91-rubric-v0|book|chapter|source-sha",
        "slot_count": len(probes),
        "gold_status": "not_gold_not_silver_answer_set",
        "request_visibility": "program_side_only_never_in_model_request",
        "slots": probes,
    }
    provider_doc = provider_plan()
    rubric_doc = rubric_candidate()
    matrix_doc = {
        "schema_version": "z91-request-matrix-v1",
        "status": "prepared_not_sent",
        "rows": request_matrix,
        "messages_identity": message_shas,
        "single_provider_per_pro_round": True,
        "primary_pro_arm": "pro_primary_tencent",
        "step2_locked": True,
    }
    adapters = read_json(ADAPTERS_PATH)
    provider_configs = {
        provider_id: _source_pin(
            ROOT / adapters["providers"][provider_id]["provider_config"],
            "provider_channel_contract",
        )
        for provider_id in (
            "qianwen_platform",
            "tencent_tokenhub",
            "volcengine_ark",
        )
    }
    source_pins = {
        "schema_version": "z91-source-pins-v1",
        "v3_request_template": {
            "path": TEMPLATE_PATH.relative_to(ROOT).as_posix(),
            "sha256": TEMPLATE_SHA256,
            "role": "model_visible_template_messages_only",
        },
        "v3_prompt_package": {
            "path": PROMPT_PACKAGE_PATH.relative_to(ROOT).as_posix(),
            "sha256": PROMPT_PACKAGE_SHA256,
            "role": "prompt_identity_read_only",
        },
        "adapter_contract": {
            "path": ADAPTERS_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(ADAPTERS_PATH),
        },
        "access_policy": {
            "path": ACCESS_POLICY_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(ACCESS_POLICY_PATH),
        },
        "provider_configs": provider_configs,
        "generator_dependencies": {
            "z91_prepare": _source_pin(
                Path(__file__).resolve(), "step1_generator"
            ),
            "evidence_catalog": _source_pin(
                ROOT / "tools/zbatch_modules/evidence_catalog.py",
                "frozen_catalog_generator",
            ),
            "z68_instantiation_helpers": _source_pin(
                ROOT / "tools/z68_revised_request_pilot.py",
                "chapter_and_catalog_replacement_helpers",
            ),
            "z79_v3_contract": _source_pin(
                ROOT / "tools/z79_fact_sheet_v3_pilot.py",
                "v3_final_reminder_and_contract_identity",
            ),
            "z80_crossbook_instantiation": _source_pin(
                ROOT / "tools/z80_fact_sheet_v4_crossbook_pilot.py",
                "crossbook_v3_message_instantiator",
            ),
        },
    }
    payloads["selection.json"] = json_bytes(selection_doc)
    payloads["probe_slots.json"] = json_bytes(probe_doc)
    payloads["rubric_candidate.json"] = json_bytes(rubric_doc)
    payloads["provider_plan.json"] = json_bytes(provider_doc)
    payloads["request_matrix.json"] = json_bytes(matrix_doc)
    payloads["provenance/source_pins.json"] = json_bytes(source_pins)
    receipt = {
        "schema_version": "z91-step1-preparation-receipt-v1",
        "run_id": RUN_ID,
        "status": "step1_prepared_zero_call_awaiting_notion_review",
        "selected_books": 3,
        "selected_chapters": 3,
        "probe_slots": 18,
        "model_api_calls": 0,
        "network_attempts": 0,
        "tokens": 0,
        "keys_loaded": False,
        "deepseek_official_api_used": False,
        "default_chain_changed": False,
        "formal_gold_changed": False,
        "active_122_changed": False,
        "classification_rules_changed": False,
        "outbox_changed": False,
        "step2_locked": True,
        "payload_vector_sha256": canonical_sha(
            {name: sha256_bytes(raw) for name, raw in sorted(payloads.items())}
        ),
    }
    payloads["receipt.json"] = json_bytes(receipt)
    meta = {
        "selection": selection_doc,
        "provider_plan": provider_doc,
        "rubric": rubric_doc,
        "receipt": receipt,
    }
    return payloads, meta


def audit_run(run_dir: Path, *, allow_unsealed: bool = False) -> dict[str, Any]:
    manifest = read_json(run_dir / "artifact_manifest.json")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise ZBatchError("工件清单为空")
    if rows != sorted(rows, key=lambda row: row.get("path", "")):
        raise ZBatchError("工件清单没有按路径稳定排序")
    paths = [row.get("path") for row in rows]
    if any(not isinstance(path, str) or not path for path in paths):
        raise ZBatchError("工件清单含空路径")
    if len(paths) != len(set(paths)):
        raise ZBatchError("工件清单含重复路径")
    expected_vector = canonical_sha(rows)
    if manifest.get("vector_sha256") != expected_vector:
        raise ZBatchError("工件清单向量 SHA 不能由清单重建")
    for row in rows:
        path = run_dir / row["path"]
        if (
            not path.is_file()
            or path.stat().st_size != row.get("bytes")
            or sha256_file(path) != row["sha256"]
        ):
            raise ZBatchError(f"工件清单 SHA 漂移：{row['path']}")
    expected_sums = "".join(
        f"{row['sha256']}  {row['path']}\n" for row in rows
    ).encode()
    sums_path = run_dir / "SHA256SUMS"
    if not sums_path.is_file() or sums_path.read_bytes() != expected_sums:
        raise ZBatchError("SHA256SUMS 不能由工件清单重建")
    verification_path = run_dir / "mechanical_verification.json"
    if not allow_unsealed and not verification_path.is_file():
        raise ZBatchError("运行目录缺最终机械保护票")
    allowed_files = set(paths) | {"artifact_manifest.json", "SHA256SUMS"}
    if verification_path.is_file():
        allowed_files.add("mechanical_verification.json")
    actual_files = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != allowed_files:
        raise ZBatchError(
            "运行目录出现未登记或缺失文件："
            f"extra={sorted(actual_files - allowed_files)}, "
            f"missing={sorted(allowed_files - actual_files)}"
        )
    selection = read_json(run_dir / "selection.json")
    matrix = read_json(run_dir / "request_matrix.json")
    probes = read_json(run_dir / "probe_slots.json")
    receipt = read_json(run_dir / "receipt.json")
    if (
        len(selection.get("cases", [])) != 3
        or probes.get("slot_count") != 18
        or len(matrix.get("rows", [])) != 12
        or receipt.get("model_api_calls") != 0
        or receipt.get("step2_locked") is not True
    ):
        raise ZBatchError("步一数量或零调用钢线漂移")
    message_groups: dict[str, set[str]] = {}
    for row in matrix["rows"]:
        message_groups.setdefault(row["case_key"], set()).add(row["messages_sha256"])
    if any(len(values) != 1 for values in message_groups.values()):
        raise ZBatchError("同章双臂 messages SHA 不一致")
    request_bytes = b"".join(
        (run_dir / row["path"]).read_bytes()
        for row in rows
        if "/requests/" in row["path"] and not row["path"].endswith("_diff.json")
    )
    if any(marker.encode("utf-8") in request_bytes for marker in FORBIDDEN_VISIBLE_MARKERS):
        raise ZBatchError("模型请求出现判分材料")
    receipt_vector = canonical_sha(
        {row["path"]: row["sha256"] for row in rows if row["path"] != "receipt.json"}
    )
    receipt_payload = read_json(run_dir / "receipt.json")
    if receipt_payload.get("payload_vector_sha256") != receipt_vector:
        raise ZBatchError("回执 payload 向量不能由非回执工件重建")
    core = {
        "status": "pass",
        "manifest_files": len(rows),
        "manifest_vector_sha256": expected_vector,
        "case_count": 3,
        "probe_slot_count": 18,
        "request_count": 12,
        "messages_identity_groups": {
            key: sorted(values) for key, values in sorted(message_groups.items())
        },
        "model_api_calls": 0,
        "network_attempts": 0,
        "step2_locked": True,
    }
    if verification_path.is_file() and not allow_unsealed:
        verification = read_json(verification_path)
        current_build_vector = {row["path"]: row["sha256"] for row in rows}
        current_protected = _protection_snapshot()
        expected_verification = {
            "schema_version": "z91-step1-mechanical-verification-v1",
            "status": "pass_twice_identical",
            "build_vector_first": current_build_vector,
            "build_vector_second": current_build_vector,
            "build_vectors_equal": True,
            "audit_first": core,
            "audit_second": core,
            "audit_vectors_equal": True,
            "protected_before": current_protected,
            "protected_after": current_protected,
            "protected_unchanged": True,
        }
        if verification != expected_verification:
            raise ZBatchError("最终机械保护票不能由现有工件与保护件重建")
    return core


def prepare(run_dir: Path) -> dict[str, Any]:
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝覆盖或复跑：{run_dir}")
    before = _protection_snapshot()
    first_payloads, meta = build_payloads()
    second_payloads, _ = build_payloads()
    first_vector = {name: sha256_bytes(raw) for name, raw in sorted(first_payloads.items())}
    second_vector = {
        name: sha256_bytes(raw) for name, raw in sorted(second_payloads.items())
    }
    if first_vector != second_vector:
        raise ZBatchError("零调用准备工件连续两次构造不一致")
    run_dir.mkdir(parents=True, exist_ok=False)
    for relative, raw in sorted(first_payloads.items()):
        write_exclusive(run_dir / relative, raw)
    rows = [
        {
            "path": relative,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
        }
        for relative, raw in sorted(first_payloads.items())
    ]
    manifest = {
        "schema_version": "z91-artifact-manifest-v1",
        "status": "prepared_not_sent",
        "files": rows,
        "vector_sha256": canonical_sha(rows),
    }
    write_exclusive(run_dir / "artifact_manifest.json", json_bytes(manifest))
    sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in rows).encode()
    write_exclusive(run_dir / "SHA256SUMS", sums)
    audit_first = audit_run(run_dir, allow_unsealed=True)
    audit_second = audit_run(run_dir, allow_unsealed=True)
    if audit_first != audit_second:
        raise ZBatchError("机械回读连续两次不一致")
    after = _protection_snapshot()
    if after != before:
        raise ZBatchError("保护件或 outbox 漂移")
    verification = {
        "schema_version": "z91-step1-mechanical-verification-v1",
        "status": "pass_twice_identical",
        "build_vector_first": first_vector,
        "build_vector_second": second_vector,
        "build_vectors_equal": True,
        "audit_first": audit_first,
        "audit_second": audit_second,
        "audit_vectors_equal": True,
        "protected_before": before,
        "protected_after": after,
        "protected_unchanged": True,
    }
    write_exclusive(
        run_dir / "mechanical_verification.json", json_bytes(verification)
    )
    sealed_audit = audit_run(run_dir)
    if sealed_audit != audit_first:
        raise ZBatchError("最终封存回读与封存前回读不一致")
    return {
        **meta["receipt"],
        "run_dir": run_dir.relative_to(ROOT).as_posix()
        if run_dir.is_relative_to(ROOT)
        else str(run_dir),
        "artifact_manifest_sha256": sha256_file(run_dir / "artifact_manifest.json"),
        "mechanical_verification_sha256": sha256_file(
            run_dir / "mechanical_verification.json"
        ),
        "selection_sha256": sha256_file(run_dir / "selection.json"),
        "provider_plan_sha256": sha256_file(run_dir / "provider_plan.json"),
        "rubric_candidate_sha256": sha256_file(run_dir / "rubric_candidate.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    result = audit_run(args.audit) if args.audit else prepare(args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

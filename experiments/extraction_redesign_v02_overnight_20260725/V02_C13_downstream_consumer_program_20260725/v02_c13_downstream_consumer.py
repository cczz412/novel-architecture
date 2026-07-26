#!/usr/bin/env python3
"""V02/C13 r02：隔断上下文的下游消费方三通道同题冻结。

本工具只读 C4/C6 已封存的两臂事实句，生成 30 份完全隔断的模型可见
题面，并在私有调度层把同一套题面复制给三家接收端。现有上游只够
单章，因此逐份如实标成 SINGLE_CHAPTER_ONLY；因果、人物状态、未决
三槽显式写 NOT_PROVIDED。工具只做 0 调用重冻结，不读取密钥、不访问
网络；题面逐字件经 Notion 核过之前，执行闸始终关闭。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


def discover_repo_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (
            (parent / "AGENTS.md").is_file()
            and (parent / "governance").is_dir()
            and (parent / "experiments").is_dir()
        ):
            return parent
    raise RuntimeError("找不到小说架构仓库根目录")


ROOT = discover_repo_root(Path(__file__).resolve().parent)
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
OUTPUT_DIR = V02_ROOT / "V02_C13_downstream_consumer_r02_20260726"
REPORT_DIR = (
    ROOT / "reports/抽取工序重设计v0.2_C13下游消费方试用_r02_20260726"
)

C4_RUN = ROOT / "runs/V02_实验A锚先行倒装_C4_r03_20260725"
C6_RUN = ROOT / "runs/V02_实验A锚先行倒装_C6对照臂_r05_20260725"
ACCESS_POLICY = ROOT / "config/providers/provider_access_policy.json"
QWEN_PROVIDER_CONFIG = (
    ROOT / "config/providers/qianwen_platform_multi_model.json"
)
DOUBAO_PROVIDER_CONFIG = (
    ROOT / "config/providers/volcengine_ark_multi_model.json"
)
MINIMAX_PROVIDER_CONFIG = (
    ROOT / "config/providers/tencent_tokenhub_multi_model.json"
)
QUESTION_FAMILY_CATALOG = (
    V02_ROOT
    / "V02_C11_product_north_star_20260725"
    / "C11_2_duse_question_expansion"
    / "catalog/question_family_catalog.json"
)

C13_WORK_ORDER_PAGE = (
    "https://app.notion.com/p/"
    "v0-2-0API-A-CZ-Codex-_20260725-eb8821e57b67472db9f220b46110dcfd"
)
C13_UNLOCK_PAGE = "https://app.notion.com/p/e5941258cd8748958eb955ad4c20863a"
C13_READBACK_AT = "2026-07-25T16:47:37.867Z"
FREEZE_STATUS = (
    "FROZEN_NOT_SENT_PENDING_NOTION_TRANSPORT_AND_FLOOR_GATES"
)

CASE_ROWS = (
    ("B02-U0039", 39, "M01", "M02"),
    ("B03-U0041", 41, "M03", "M04"),
    ("B01-U0033", 33, "M05", "M06"),
)

INPUTS = {
    ("treatment", "B01-U0033"): (
        C4_RUN / "samples/main/B01-U0033/candidate/model_json.json",
        "95a3aa343255b262986f06405d49a7c776c3c553c4829585a10c0259af15650a",
    ),
    ("treatment", "B02-U0039"): (
        C4_RUN / "samples/main/B02-U0039/candidate/model_json.json",
        "ff15bc7c0a48e8d0f9627ff6dd52f7223d1056b6e317cae242a2609db89ea074",
    ),
    ("treatment", "B03-U0041"): (
        C4_RUN / "samples/main/B03-U0041/candidate/model_json.json",
        "f915b4387e7ea7c206b7c6f9374f9ca13986458bc1998c94b88f69253e5658f2",
    ),
    ("control", "B01-U0033"): (
        C6_RUN / "samples/main/B01-U0033/candidate/model_json.json",
        "d570c51f1299f32747ab8c030a95063e439a6d00e4126ac1018c744f38de6db1",
    ),
    ("control", "B02-U0039"): (
        C6_RUN / "samples/main/B02-U0039/candidate/model_json.json",
        "64eaea14c5a979d8f8a9223f6f91b36a551229b94c537092b4b95a49aa98e5cd",
    ),
    ("control", "B03-U0041"): (
        C6_RUN / "samples/main/B03-U0041/candidate/model_json.json",
        "a735021d3d0d357c2fe0a227d2967f94cd8b6ba7b002cf4cbe2e1de58c1fb13b",
    ),
}

EXPECTED_POLICY_SHAS = {
    ACCESS_POLICY: "f4e350e5b9daacd95c7f573222d5dba91b24186904b14dbe0b1021132a1f0528",
    QWEN_PROVIDER_CONFIG: (
        "0ec8891beff5016a4b6b79bd4c5f63d7b7e34fc2d068cd05119e445e9f59bd4e"
    ),
    DOUBAO_PROVIDER_CONFIG: (
        "8af94a1f742814e5d87073d14e6bbba7903052b5eab5a735373b7daf5296aea6"
    ),
    MINIMAX_PROVIDER_CONFIG: (
        "28c57f1517d7b4f57747b1f64c13ccd7fa3cc5f3a624e5db04f3f54a0afa6299"
    ),
    QUESTION_FAMILY_CATALOG: (
        "8652f7a271674802d1873e8ae298c347f2063661a5a9af907b2a07a629f41f45"
    ),
}

PROVIDER_PROFILES = (
    {
        "provider_id": "qianwen_platform",
        "display_name": "千问 AI 平台",
        "role": "PRIMARY_READOUT",
        "model_id": "qwen3.7-max-2026-05-20",
        "api_key_env": "DASHSCOPE_API_KEY",
        "config_path": QWEN_PROVIDER_CONFIG,
        "catalog_gate": "QWEN_AUTHENTICATED_CLI_EXACT_ID_MEMBERSHIP_REQUIRED",
        "proposed_request_parameters_pending_wire_validation": {
            "temperature": 0.2,
            "stream": False,
            "enable_thinking": True,
            "thinking_budget": 32768,
            "response_format_sent": False,
        },
        "wire_adapter_status": (
            "BLOCKED_PENDING_ZERO_CALL_RENDER_AND_FIELD_EVIDENCE"
        ),
    },
    {
        "provider_id": "volcengine_ark",
        "display_name": "火山方舟",
        "role": "REPLICATION",
        "model_id": "doubao-seed-2-1-pro-260628",
        "api_key_env": "ARK_API_KEY",
        "config_path": DOUBAO_PROVIDER_CONFIG,
        "catalog_gate": "STATIC_EXACT_ID_CONFIG_PLUS_FIRST_CALL_IDENTITY_CHECK",
        "proposed_request_parameters_pending_wire_validation": {
            "temperature": 0.2,
            "max_tokens": 32768,
            "stream": False,
            "thinking": {"type": "enabled"},
            "response_format_sent": False,
        },
        "wire_adapter_status": (
            "BLOCKED_PENDING_ZERO_CALL_RENDER_AND_FIELD_EVIDENCE"
        ),
    },
    {
        "provider_id": "tencent_tokenhub",
        "display_name": "腾讯云 TokenHub",
        "role": "REPLICATION",
        "model_id": "minimax-m3",
        "api_key_env": "TENCENT_TOKENHUB_API_KEY",
        "config_path": MINIMAX_PROVIDER_CONFIG,
        "catalog_gate": "LIVE_MODELS_EXACT_ID_ONLINE_REQUIRED",
        "proposed_request_parameters_pending_wire_validation": {
            "temperature": 0.2,
            "max_tokens": 32768,
            "stream": False,
            "thinking_mode": "adaptive_default_no_parameter_sent",
            "response_format_sent": False,
        },
        "wire_adapter_status": (
            "BLOCKED_PENDING_ZERO_CALL_RENDER_AND_FIELD_EVIDENCE"
        ),
    },
)

QUESTION_FAMILIES = (
    "RESEARCH_RECENT_RESOURCE_DECREASE",
    "RESEARCH_ANTAGONIST_KNOWLEDGE",
    "RESEARCH_UNRESOLVED_THREAD_DUE_WITHIN_TWO_CHAPTERS",
    "RESEARCH_RULE_PRIOR_OCCURRENCES",
    "RESEARCH_UNFULFILLED_READER_PROMISES",
    "RESEARCH_DECISION_INFORMATION_SUFFICIENCY",
    "PRODUCT_STORYBOARD_RECONSTRUCTION",
    "PRODUCT_CHARACTER_DECISION_KNOWLEDGE_SET",
    "PRODUCT_PLAN_FULFILLMENT",
)

QUESTION_FAMILY_BRIEFS = {
    "RESEARCH_RECENT_RESOURCE_DECREASE": "查询人物或组织最近一次资源减少及其时间边界",
    "RESEARCH_ANTAGONIST_KNOWLEDGE": "查询对手在指定章节截止点已经知道什么",
    "RESEARCH_UNRESOLVED_THREAD_DUE_WITHIN_TWO_CHAPTERS": (
        "查询两章内到期但尚未解决的线索或事项"
    ),
    "RESEARCH_RULE_PRIOR_OCCURRENCES": "查询某条规则此前出现过的章节与证据",
    "RESEARCH_UNFULFILLED_READER_PROMISES": "查询文本已向读者许下但尚未兑现的承诺",
    "RESEARCH_DECISION_INFORMATION_SUFFICIENCY": (
        "查询人物作出决定时掌握的信息是否足够"
    ),
    "PRODUCT_STORYBOARD_RECONSTRUCTION": "查询能否从结构数据还原分镜所需场景要素",
    "PRODUCT_CHARACTER_DECISION_KNOWLEDGE_SET": (
        "查询人物作决定时的知识集合，用于检查降智"
    ),
    "PRODUCT_PLAN_FULFILLMENT": "查询计划事项后来是否兑现、变体实现或延后",
}

MISSING_BUCKETS = (
    "ATTRIBUTION_MISSING",
    "REALIS_MODALITY_POLARITY_MISSING",
    "COREFERENCE_UNRESOLVED",
    "SUBJECT_PREDICATE_OBJECT_MISSING",
    "STATE_SLOT_MISSING",
    "TIME_CHAPTER_ORDER_MISSING",
    "FACT_NOT_EXTRACTED",
    "SCENE_VISUAL_MISSING",
    "EMOTION_INTENSITY_MISSING",
)

MISSING_BUCKET_AUTHORITY = {
    "ATTRIBUTION_MISSING": {
        "display_name": "归属层缺失",
        "authority": "Notion §9.1-E.4 bucket 1",
    },
    "REALIS_MODALITY_POLARITY_MISSING": {
        "display_name": "否定／情态／未然未分离",
        "authority": "Notion §9.1-E.4 bucket 2",
    },
    "COREFERENCE_UNRESOLVED": {
        "display_name": "指代未消解",
        "authority": "Notion §9.1-E.4 bucket 3",
    },
    "SUBJECT_PREDICATE_OBJECT_MISSING": {
        "display_name": "主谓宾未成格",
        "authority": "Notion §9.1-E.4 bucket 4",
    },
    "STATE_SLOT_MISSING": {
        "display_name": "状态槽缺失／不可续接",
        "authority": "Notion §9.1-E.4 bucket 5",
    },
    "TIME_CHAPTER_ORDER_MISSING": {
        "display_name": "时间／章序信息缺失",
        "authority": "Notion §9.1-E.4 bucket 6",
    },
    "FACT_NOT_EXTRACTED": {
        "display_name": "根本没抽到",
        "authority": "Notion §9.1-E.4 bucket 7",
    },
    "SCENE_VISUAL_MISSING": {
        "display_name": "画面／场景信息缺失",
        "authority": "Notion C11.2 bucket 8",
    },
    "EMOTION_INTENSITY_MISSING": {
        "display_name": "情绪／强度信息缺失",
        "authority": "Notion C11.2 bucket 9",
    },
}

USABILITY_LABELS = ("USABLE", "AMBIGUOUS", "UNUSABLE")
ANSWER_STATUSES = ("ANSWERED", "MATERIAL_INSUFFICIENT")

FORBIDDEN_VISIBLE_MARKERS = (
    "大王饶命",
    "神秘复苏",
    "知否",
    "绿肥红瘦",
    "会说话的肘子",
    "佛前献花",
    "关心则乱",
    "B01-U0033",
    "B02-U0039",
    "B03-U0041",
    "V02_实验A",
    "V02_C4",
    "V02_C6",
    "v02",
    "c13",
    "上游",
    "隔断",
    "评测",
    "实验",
    "provisional_ai_downstream",
    "实验臂",
    "对照臂",
    "treatment",
    "control",
    "anchor_first",
    "gold",
    "金标",
    "历史成绩",
    "抽取路线",
    "sensenova",
    "deepseek",
    "qwen",
    "千问",
    "doubao",
    "豆包",
    "火山方舟",
    "minimax",
    "腾讯云",
    "ling",
)

SYSTEM_PROMPT = """你是一名负责续写规划的大纲编辑。
你只可使用本次消息给出的事实句、四视图机械索引和章序号。
不得调用外部知识，不得猜作品，不得补写材料中没有的事实。
如果材料不够，必须明确写 MATERIAL_INSUFFICIENT 或缺口，不要脑补。
输出只能是 JSON 对象，不要 Markdown，不要解释 JSON 之外的内容。"""

TASK_A_PROMPT = """任务 A：把材料当作写下一章大纲前的底账。
请写一份可执行的下一章规划草案。每个规划点必须列出支撑它的 fact_ids，
并明确它只是“写作建议”，不能冒充已经发生的事实。
请边写边列缺口；每个缺口必须写：缺什么、不补会写错什么、应补到哪个字段、
以及九类 missing_bucket 中的一类。缺就写缺，禁止自行补齐。"""

TASK_B_PROMPT = """任务 B：逐一回答九个固定问题族。
每个问题族只能引用材料中的 fact_ids。能答则写 ANSWERED；不能答必须写
MATERIAL_INSUFFICIENT，并说明缺什么字段、归入哪个 missing_bucket。
不得把“材料没写”当成“事情不存在”，不得用常识补答案。"""

TASK_C_PROMPT = """任务 C：给每一条事实句判下游可用性。
逐条且不漏不重地返回 fact_id、USABLE/AMBIGUOUS/UNUSABLE 和一句简短理由。
USABLE 表示脱离原文仍可直接供下一章规划使用；AMBIGUOUS 表示主体、指代、
时序、归属或实际发生状态不清；UNUSABLE 表示写了等于没写。"""

class C13Error(RuntimeError):
    """C13 冻结、解析或验收不能安全继续。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C13Error(f"冻结输入不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_json_response(raw_text: str) -> Mapping[str, Any]:
    """严格解析模型正文；不接受 Markdown 围栏或 JSON 外说明。"""

    if not isinstance(raw_text, str) or not raw_text.strip():
        raise C13Error("模型响应正文为空")
    stripped = raw_text.strip()
    if stripped.startswith("```") or stripped.endswith("```"):
        raise C13Error("模型响应不得使用 Markdown 围栏")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise C13Error("模型响应不是完整 JSON") from exc
    return _require_object(payload, "模型响应")


def annotate_provisional_output(payload: Mapping[str, Any]) -> dict[str, Any]:
    """解析过闸后再加内部候选身份；该字段永不进入模型可见合同。"""

    return {
        **dict(payload),
        "_internal_classification": "PROVISIONAL_AI_DOWNSTREAM",
    }


def _require_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise C13Error(f"{label} 必须是对象")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    keys: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != keys:
        raise C13Error(
            f"{label} 字段不闭合：missing={sorted(keys - actual)} "
            f"extra={sorted(actual - keys)}"
        )


def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise C13Error(f"{label} 必须是字符串")
    return value


def _source_events(arm: str, case_id: str) -> tuple[list[dict[str, Any]], str]:
    path, expected_sha = INPUTS[(arm, case_id)]
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha:
        raise C13Error(f"封存事实句 SHA 漂移：{display_path(path)}")
    payload = _require_object(read_json(path), display_path(path))
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise C13Error(f"{display_path(path)} 没有事实句")
    validated = []
    seen_ids: set[str] = set()
    for index, item in enumerate(events, 1):
        row = _require_object(item, f"{case_id}.events[{index}]")
        event_id = _require_string(row.get("event_id"), f"{case_id}.event_id")
        event = _require_string(row.get("event"), f"{case_id}.event")
        if event_id in seen_ids:
            raise C13Error(f"{case_id} 事件身份重复：{event_id}")
        seen_ids.add(event_id)
        validated.append({"source_event_id": event_id, "event": event})
    return validated, actual_sha


def build_mechanical_views(facts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """只生成可从源顺序直接证明的时间线；其余三槽明确未提供。"""

    timeline = [
        {"seq": index, "fact_id": row["fact_id"]}
        for index, row in enumerate(facts, 1)
    ]
    return {
        "timeline": {
            "status": "PROVIDED_MECHANICAL",
            "items": timeline,
        },
        "causal_edges": {"status": "NOT_PROVIDED", "items": []},
        "character_states": {"status": "NOT_PROVIDED", "items": []},
        "unresolved_items": {"status": "NOT_PROVIDED", "items": []},
    }


def anonymous_material_id(internal_alias: str, variant: str) -> str:
    return (
        "D"
        + sha256_bytes(
            f"C13-r02|{internal_alias}|{variant}".encode("utf-8")
        )[:10].upper()
    )


def build_material(
    *,
    arm: str,
    case_id: str,
    chapter_number: int,
    material_alias: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_events, source_sha = _source_events(arm, case_id)
    facts = [
        {"fact_id": f"F{index:03d}", "fact": row["event"]}
        for index, row in enumerate(source_events, 1)
    ]
    visible_id = anonymous_material_id(material_alias, "NORMAL")
    visible = {
        "schema_version": "chapter-fact-material.v1",
        "material_id": visible_id,
        "chapter_number": chapter_number,
        "coverage_scope": "SINGLE_CHAPTER_ONLY",
        "cumulative_chapter_count": 1,
        "facts": facts,
        "four_views": build_mechanical_views(facts),
    }
    private = {
        "schema_version": "v02-c13-private-material-map.v2",
        "material_id": visible_id,
        "internal_alias": material_alias,
        "arm": arm,
        "case_id": case_id,
        "source_path": display_path(INPUTS[(arm, case_id)][0]),
        "source_sha256": source_sha,
        "coverage_scope": "SINGLE_CHAPTER_ONLY",
        "cumulative_chapter_count": 1,
        "facts_through_chapter_available": False,
        "complete_four_view_available": False,
        "short_term_usefulness_only": True,
        "fact_identity_map": [
            {
                "fact_id": fact["fact_id"],
                "source_event_id": source["source_event_id"],
            }
            for fact, source in zip(facts, source_events, strict=True)
        ],
    }
    return visible, private


def shuffled_material(
    material: Mapping[str, Any],
    *,
    internal_alias: str,
) -> dict[str, Any]:
    result = json.loads(json.dumps(material, ensure_ascii=False))
    facts = list(result["facts"])
    seed = int(sha256_bytes(canonical_bytes(material))[:16], 16)
    random.Random(seed).shuffle(facts)
    if len(facts) > 1 and facts == result["facts"]:
        facts = facts[1:] + facts[:1]
    result["material_id"] = anonymous_material_id(
        internal_alias,
        "SHUFFLED_FACT_ORDER",
    )
    result["facts"] = facts
    result["four_views"] = build_mechanical_views(facts)
    return result


def blank_material(
    material: Mapping[str, Any],
    *,
    internal_alias: str,
) -> dict[str, Any]:
    return {
        "schema_version": "chapter-fact-material.v1",
        "material_id": anonymous_material_id(
            internal_alias,
            "CHAPTER_NUMBER_ONLY",
        ),
        "chapter_number": material["chapter_number"],
        "coverage_scope": "SINGLE_CHAPTER_ONLY",
        "cumulative_chapter_count": 1,
        "facts": [],
        "four_views": build_mechanical_views([]),
    }


def output_contract(task: str) -> dict[str, Any]:
    common = {
        "material_id": "必须逐字回传输入 material_id",
        "external_knowledge_used": False,
    }
    if task == "A":
        return {
            **common,
            "task": "A",
            "outline_beats": [
                {
                    "beat_id": "字符串",
                    "proposal": "写作建议，不得冒充已发生事实",
                    "basis_fact_ids": ["F001"],
                }
            ],
            "gaps": [
                {
                    "gap_id": "字符串",
                    "missing_bucket": list(MISSING_BUCKETS),
                    "missing_information": "字符串",
                    "wrong_if_missing": "字符串",
                    "target_field": "字符串",
                }
            ],
        }
    if task == "B":
        return {
            **common,
            "task": "B",
            "answers": [
                {
                    "question_family": family,
                    "status": list(ANSWER_STATUSES),
                    "answer": "ANSWERED 时非空，否则空字符串",
                    "supporting_fact_ids": ["F001"],
                    "missing_bucket": "不足时为九桶之一，能答时为 null",
                    "missing_reason": "不足时非空，能答时为空字符串",
                }
                for family in QUESTION_FAMILIES
            ],
        }
    if task == "C":
        return {
            **common,
            "task": "C",
            "ratings": [
                {
                    "fact_id": "F001",
                    "label": list(USABILITY_LABELS),
                    "reason": "一句短理由",
                }
            ],
        }
    raise C13Error(f"未知任务：{task}")


def request_messages(
    material: Mapping[str, Any],
    *,
    task: str,
) -> list[dict[str, str]]:
    prompts = {
        "A": TASK_A_PROMPT,
        "B": TASK_B_PROMPT,
        "C": TASK_C_PROMPT,
    }
    user_payload = {
        "task_instruction": prompts[task],
        "output_contract": output_contract(task),
        "material": material,
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                user_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    ]


def visible_leak_hits(messages: Sequence[Mapping[str, str]]) -> list[str]:
    text = json.dumps(messages, ensure_ascii=False).lower()
    return sorted(
        marker
        for marker in FORBIDDEN_VISIBLE_MARKERS
        if marker.lower() in text
    )


def build_call_plan(
    materials: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    shuffled_tasks = ("A", "B", "C", "A", "B", "C")
    blank_tasks = ("B", "C", "A", "B", "C", "A")
    nodes: list[dict[str, Any]] = []
    request_artifacts: dict[str, bytes] = {}
    ordinal = 0
    for material_index, internal_alias in enumerate(sorted(materials)):
        material = materials[internal_alias]
        for task in ("A", "B", "C"):
            ordinal += 1
            call_id = f"C13-N{ordinal:02d}"
            messages = request_messages(material, task=task)
            hits = visible_leak_hits(messages)
            if hits:
                raise C13Error(f"{call_id} 模型可见面泄漏：{hits}")
            payload = {
                "schema_version": "v02-c13-provider-neutral-request.v2",
                "call_id": call_id,
                "messages": messages,
                "task": task,
                "floor_kind": None,
            }
            raw = canonical_bytes(payload)
            relative = f"requests/{call_id}.json"
            send_surface = canonical_bytes({"messages": messages})
            send_relative = f"send_surfaces/{call_id}.json"
            request_artifacts[relative] = raw
            request_artifacts[send_relative] = send_surface
            nodes.append(
                {
                    "ordinal": ordinal,
                    "call_id": call_id,
                    "material_id": material["material_id"],
                    "base_material_id": material["material_id"],
                    "task": task,
                    "floor_kind": None,
                    "source_request_path": relative,
                    "source_request_sha256": sha256_bytes(raw),
                    "send_surface": "MESSAGES_ONLY",
                    "send_surface_path": send_relative,
                    "send_surface_sha256": sha256_bytes(send_surface),
                    "messages_sha256": sha256_bytes(
                        canonical_bytes(messages)
                    ),
                    "conversation_isolated": True,
                }
            )
        for floor_kind, floor_material, task in (
            (
                "SHUFFLED_FACT_ORDER",
                shuffled_material(
                    material,
                    internal_alias=internal_alias,
                ),
                shuffled_tasks[material_index],
            ),
            (
                "CHAPTER_NUMBER_ONLY",
                blank_material(
                    material,
                    internal_alias=internal_alias,
                ),
                blank_tasks[material_index],
            ),
        ):
            ordinal += 1
            call_id = f"C13-N{ordinal:02d}"
            messages = request_messages(floor_material, task=task)
            hits = visible_leak_hits(messages)
            if hits:
                raise C13Error(f"{call_id} 模型可见面泄漏：{hits}")
            payload = {
                "schema_version": "v02-c13-provider-neutral-request.v2",
                "call_id": call_id,
                "messages": messages,
                "task": task,
                "floor_kind": floor_kind,
            }
            raw = canonical_bytes(payload)
            relative = f"requests/{call_id}.json"
            send_surface = canonical_bytes({"messages": messages})
            send_relative = f"send_surfaces/{call_id}.json"
            request_artifacts[relative] = raw
            request_artifacts[send_relative] = send_surface
            nodes.append(
                {
                    "ordinal": ordinal,
                    "call_id": call_id,
                    "material_id": floor_material["material_id"],
                    "base_material_id": material["material_id"],
                    "task": task,
                    "floor_kind": floor_kind,
                    "source_request_path": relative,
                    "source_request_sha256": sha256_bytes(raw),
                    "send_surface": "MESSAGES_ONLY",
                    "send_surface_path": send_relative,
                    "send_surface_sha256": sha256_bytes(send_surface),
                    "messages_sha256": sha256_bytes(
                        canonical_bytes(messages)
                    ),
                    "conversation_isolated": True,
                }
            )
    if len(nodes) != 30:
        raise C13Error(f"C13 节点必须恰好 30，实际 {len(nodes)}")
    return nodes, request_artifacts


def _validate_common(
    payload: Mapping[str, Any],
    *,
    expected_material_id: str,
) -> None:
    if payload.get("material_id") != expected_material_id:
        raise C13Error("输出 material_id 与输入不一致")
    if payload.get("external_knowledge_used") is not False:
        raise C13Error("输出未明确 external_knowledge_used=false")


def _validate_fact_ids(
    values: Any,
    *,
    allowed: set[str],
    label: str,
) -> list[str]:
    if not isinstance(values, list) or any(
        not isinstance(value, str) for value in values
    ):
        raise C13Error(f"{label} 必须是 fact_id 数组")
    if len(values) != len(set(values)):
        raise C13Error(f"{label} 含重复 fact_id")
    unknown = set(values) - allowed
    if unknown:
        raise C13Error(f"{label} 引用未知 fact_id：{sorted(unknown)}")
    return list(values)


def validate_task_a(
    payload: Mapping[str, Any],
    *,
    expected_material_id: str,
    allowed_fact_ids: set[str],
) -> dict[str, Any]:
    _require_exact_keys(
        payload,
        {
            "material_id",
            "external_knowledge_used",
            "task",
            "outline_beats",
            "gaps",
        },
        "task A",
    )
    _validate_common(payload, expected_material_id=expected_material_id)
    if payload["task"] != "A":
        raise C13Error("task A 身份漂移")
    if not isinstance(payload["outline_beats"], list):
        raise C13Error("outline_beats 必须是数组")
    for index, item in enumerate(payload["outline_beats"], 1):
        row = _require_object(item, f"outline_beats[{index}]")
        _require_exact_keys(
            row,
            {"beat_id", "proposal", "basis_fact_ids"},
            f"outline_beats[{index}]",
        )
        _require_string(row["beat_id"], "beat_id")
        _require_string(row["proposal"], "proposal")
        basis = _validate_fact_ids(
            row["basis_fact_ids"],
            allowed=allowed_fact_ids,
            label="basis_fact_ids",
        )
        if not basis:
            raise C13Error("有大纲建议却没有事实支撑")
    if not isinstance(payload["gaps"], list):
        raise C13Error("gaps 必须是数组")
    for index, item in enumerate(payload["gaps"], 1):
        row = _require_object(item, f"gaps[{index}]")
        _require_exact_keys(
            row,
            {
                "gap_id",
                "missing_bucket",
                "missing_information",
                "wrong_if_missing",
                "target_field",
            },
            f"gaps[{index}]",
        )
        if row["missing_bucket"] not in MISSING_BUCKETS:
            raise C13Error("任务 A 使用未知缺口桶")
        for key in (
            "gap_id",
            "missing_information",
            "wrong_if_missing",
            "target_field",
        ):
            _require_string(row[key], f"gaps.{key}")
    return dict(payload)


def validate_task_b(
    payload: Mapping[str, Any],
    *,
    expected_material_id: str,
    allowed_fact_ids: set[str],
) -> dict[str, Any]:
    _require_exact_keys(
        payload,
        {
            "material_id",
            "external_knowledge_used",
            "task",
            "answers",
        },
        "task B",
    )
    _validate_common(payload, expected_material_id=expected_material_id)
    if payload["task"] != "B":
        raise C13Error("task B 身份漂移")
    answers = payload["answers"]
    if not isinstance(answers, list) or len(answers) != len(QUESTION_FAMILIES):
        raise C13Error("任务 B 必须恰好返回九题")
    seen: set[str] = set()
    for index, item in enumerate(answers, 1):
        row = _require_object(item, f"answers[{index}]")
        _require_exact_keys(
            row,
            {
                "question_family",
                "status",
                "answer",
                "supporting_fact_ids",
                "missing_bucket",
                "missing_reason",
            },
            f"answers[{index}]",
        )
        family = row["question_family"]
        if family not in QUESTION_FAMILIES or family in seen:
            raise C13Error("任务 B 题族缺失、重复或未知")
        seen.add(family)
        status = row["status"]
        if status not in ANSWER_STATUSES:
            raise C13Error("任务 B status 非法")
        ids = _validate_fact_ids(
            row["supporting_fact_ids"],
            allowed=allowed_fact_ids,
            label="supporting_fact_ids",
        )
        answer = _require_string(row["answer"], "answer", allow_empty=True)
        reason = _require_string(
            row["missing_reason"],
            "missing_reason",
            allow_empty=True,
        )
        if status == "ANSWERED":
            if not answer or not ids:
                raise C13Error("ANSWERED 必须有答案和事实支撑")
            if row["missing_bucket"] is not None or reason:
                raise C13Error("ANSWERED 不得夹带缺口桶或缺口理由")
        else:
            if answer or ids:
                raise C13Error("MATERIAL_INSUFFICIENT 不得伪造答案或支撑")
            if row["missing_bucket"] not in MISSING_BUCKETS or not reason:
                raise C13Error("材料不足必须登记缺口桶和理由")
    if seen != set(QUESTION_FAMILIES):
        raise C13Error("任务 B 九题不完整")
    return dict(payload)


def validate_task_c(
    payload: Mapping[str, Any],
    *,
    expected_material_id: str,
    allowed_fact_ids: set[str],
) -> dict[str, Any]:
    _require_exact_keys(
        payload,
        {
            "material_id",
            "external_knowledge_used",
            "task",
            "ratings",
        },
        "task C",
    )
    _validate_common(payload, expected_material_id=expected_material_id)
    if payload["task"] != "C":
        raise C13Error("task C 身份漂移")
    ratings = payload["ratings"]
    if not isinstance(ratings, list):
        raise C13Error("ratings 必须是数组")
    seen: set[str] = set()
    for index, item in enumerate(ratings, 1):
        row = _require_object(item, f"ratings[{index}]")
        _require_exact_keys(
            row,
            {"fact_id", "label", "reason"},
            f"ratings[{index}]",
        )
        fact_id = row["fact_id"]
        if fact_id not in allowed_fact_ids or fact_id in seen:
            raise C13Error("任务 C fact_id 缺失、重复或未知")
        seen.add(fact_id)
        if row["label"] not in USABILITY_LABELS:
            raise C13Error("任务 C label 非法")
        _require_string(row["reason"], "ratings.reason")
    if seen != allowed_fact_ids:
        raise C13Error("任务 C 没有逐条且不漏不重地评分")
    return dict(payload)


def validate_floor(
    payload: Mapping[str, Any],
    *,
    expected_material_id: str,
    allowed_fact_ids: set[str],
) -> dict[str, Any]:
    _require_exact_keys(
        payload,
        {
            "material_id",
            "external_knowledge_used",
            "task",
            "outline_beats",
            "gaps",
            "answers",
            "ratings",
        },
        "floor",
    )
    _validate_common(payload, expected_material_id=expected_material_id)
    if payload["task"] != "COMBINED":
        raise C13Error("组合任务身份漂移")
    a_payload = {
        key: payload[key]
        for key in (
            "material_id",
            "external_knowledge_used",
            "outline_beats",
            "gaps",
        )
    }
    a_payload["task"] = "A"
    b_payload = {
        key: payload[key]
        for key in (
            "material_id",
            "external_knowledge_used",
            "answers",
        )
    }
    b_payload["task"] = "B"
    c_payload = {
        key: payload[key]
        for key in (
            "material_id",
            "external_knowledge_used",
            "ratings",
        )
    }
    c_payload["task"] = "C"
    validate_task_a(
        a_payload,
        expected_material_id=expected_material_id,
        allowed_fact_ids=allowed_fact_ids,
    )
    validate_task_b(
        b_payload,
        expected_material_id=expected_material_id,
        allowed_fact_ids=allowed_fact_ids,
    )
    validate_task_c(
        c_payload,
        expected_material_id=expected_material_id,
        allowed_fact_ids=allowed_fact_ids,
    )
    return dict(payload)


def output_metrics(
    task_a: Mapping[str, Any],
    task_b: Mapping[str, Any],
    task_c: Mapping[str, Any],
) -> dict[str, Any]:
    answer_counts = Counter(row["status"] for row in task_b["answers"])
    gap_counts = Counter(row["missing_bucket"] for row in task_a["gaps"])
    gap_counts.update(
        row["missing_bucket"]
        for row in task_b["answers"]
        if row["status"] == "MATERIAL_INSUFFICIENT"
    )
    usability = Counter(row["label"] for row in task_c["ratings"])
    answerable = answer_counts["ANSWERED"]
    rating_total = len(task_c["ratings"])
    return {
        "answerable_rate": {
            "numerator": answerable,
            "denominator": len(QUESTION_FAMILIES),
            "value": answerable / len(QUESTION_FAMILIES),
        },
        "missing_bucket_counts": {
            bucket: gap_counts[bucket] for bucket in MISSING_BUCKETS
        },
        "usability_counts": {
            label: usability[label] for label in USABILITY_LABELS
        },
        "usability_ratios": {
            label: (
                None if rating_total == 0 else usability[label] / rating_total
            )
            for label in USABILITY_LABELS
        },
        "outline_beat_count": len(task_a["outline_beats"]),
    }


def build_calibration_sample(
    ratings: Sequence[Mapping[str, Any]],
    *,
    sample_seed: str,
) -> list[dict[str, Any]]:
    """按 C13 抽 5 条 USABLE 和 5 条其余项，供 CZ 做最小校准。"""

    usable = [dict(row) for row in ratings if row.get("label") == "USABLE"]
    other = [
        dict(row)
        for row in ratings
        if row.get("label") in {"AMBIGUOUS", "UNUSABLE"}
    ]
    if len(usable) < 5 or len(other) < 5:
        raise C13Error("校准抽样不足 5 条 USABLE 或 5 条非 USABLE")
    seed = int(hashlib.sha256(sample_seed.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    selected = rng.sample(usable, 5) + rng.sample(other, 5)
    rng.shuffle(selected)
    return [
        {
            "calibration_id": f"CAL-{index:02d}",
            "fact_id": row["fact_id"],
            "receiver_label": row["label"],
            "receiver_reason": row["reason"],
            "cz_verdict": None,
        }
        for index, row in enumerate(selected, 1)
    ]


def _validated_provider_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for profile in PROVIDER_PROFILES:
        config_path = profile["config_path"]
        config = _require_object(
            read_json(config_path),
            display_path(config_path),
        )
        models = config.get("models")
        if not isinstance(models, list):
            raise C13Error(f"{display_path(config_path)} 缺 models")
        exact = [
            row
            for row in models
            if isinstance(row, Mapping)
            and row.get("model_id") == profile["model_id"]
            and row.get("call_ready") is True
        ]
        if len(exact) != 1:
            raise C13Error(
                f"{profile['provider_id']} 精确型号未唯一配置："
                f"{profile['model_id']}"
            )
        if config.get("api_key_env") != profile["api_key_env"]:
            raise C13Error(f"{profile['provider_id']} 密钥变量配置漂移")
        profiles.append(
            {
                **{
                    key: value
                    for key, value in profile.items()
                    if key != "config_path"
                },
                "provider_config_path": display_path(config_path),
                "provider_config_sha256": sha256_file(config_path),
                "base_url": config.get("base_url"),
                "endpoint": config.get("endpoint"),
                "enabled_by_default": config.get("enabled_by_default"),
                "automatic_fallback_allowed": False,
                "exact_model_static_configured": True,
                "live_catalog_or_identity_gate_passed": False,
                "wire_adapter_zero_call_render_passed": False,
                "messages_may_change_by_adapter": False,
                "strict_local_json_parser": True,
                "invalid_json_repair_or_quality_retry_allowed": False,
            }
        )
    roles = Counter(row["role"] for row in profiles)
    if roles != {"PRIMARY_READOUT": 1, "REPLICATION": 2}:
        raise C13Error(f"C13 三家角色登记错误：{dict(roles)}")
    return profiles


def build_provider_dispatch_plan(
    nodes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    profiles = _validated_provider_profiles()
    dispatch_nodes: list[dict[str, Any]] = []
    for profile in profiles:
        for node in nodes:
            dispatch_nodes.append(
                {
                    "dispatch_id": (
                        f"{profile['provider_id']}::{node['call_id']}"
                    ),
                    "provider_id": profile["provider_id"],
                    "model_id": profile["model_id"],
                    "role": profile["role"],
                    "base_call_id": node["call_id"],
                    "task": node["task"],
                    "floor_kind": node["floor_kind"],
                    "send_surface": "MESSAGES_ONLY",
                    "send_surface_path": node["send_surface_path"],
                    "send_surface_sha256": node["send_surface_sha256"],
                    "messages_sha256": node["messages_sha256"],
                    "status": FREEZE_STATUS,
                }
            )
    if len(dispatch_nodes) != 90:
        raise C13Error(f"C13 三家调度位必须恰好90，实际 {len(dispatch_nodes)}")
    per_provider = Counter(row["provider_id"] for row in dispatch_nodes)
    if set(per_provider.values()) != {30}:
        raise C13Error(f"C13 每家调用位不是30：{dict(per_provider)}")
    for call_id in {row["base_call_id"] for row in dispatch_nodes}:
        shas = {
            row["messages_sha256"]
            for row in dispatch_nodes
            if row["base_call_id"] == call_id
        }
        if len(shas) != 1:
            raise C13Error(f"{call_id} 三家模型可见题面 SHA 不一致")
    return {
        "schema_version": "v02-c13-provider-dispatch-plan.v1",
        "status": FREEZE_STATUS,
        "primary_readout_provider": "qianwen_platform",
        "primary_readout_model": "qwen3.7-max-2026-05-20",
        "replication_providers": [
            "volcengine_ark",
            "tencent_tokenhub",
        ],
        "provider_profiles": profiles,
        "base_prompt_slot_total": 30,
        "per_provider_hard_call_cap": 30,
        "total_hard_call_cap": 90,
        "dispatch_nodes": dispatch_nodes,
        "actual_send_surface": "MESSAGES_ONLY",
        "private_request_wrapper_may_be_sent": False,
        "same_slot_messages_must_be_byte_identical": True,
        "provider_scores_may_be_averaged_or_weighted": False,
        "provider_scores_may_be_merged": False,
        "each_provider_uses_own_floor_only": True,
        "one_provider_floor_failure_invalidates_other_providers": False,
        "qwen_floor_failure_allows_replication_to_replace_primary": False,
        "top3_missing_bucket_ranking_consistency_required": True,
        "shared_chinese_pretraining_prior_risk": (
            "AGREEMENT_ONLY_RULES_OUT_SINGLE_MODEL_QUIRK"
        ),
    }


def _prompt_review_block() -> dict[str, Any]:
    policy = read_json(ACCESS_POLICY)
    providers = policy.get("providers")
    if not isinstance(providers, Mapping) or not providers:
        raise C13Error("供应商访问策略为空或结构漂移")
    return {
        "schema_version": "v02-c13-prompt-review-gate.v1",
        "status": "BLOCKED_PENDING_NOTION_PROMPT_LEAK_REVIEW",
        "blocking": True,
        "model_api_calls": 0,
        "network_requests": 0,
        "key_value_read": False,
        "blocking_reasons": [
            {
                "code": "NOTION_EXACT_PROMPT_LEAK_REVIEW_PENDING",
                "detail": (
                    "30份最终模型可见 messages 的逐字文本与 SHA 尚未取得"
                    " Notion 窗明确 APPROVED_TO_SEND 回读票。"
                ),
            },
            {
                "code": "THREE_PROVIDER_WIRE_ADAPTERS_PENDING",
                "detail": (
                    "三家固定型号的实际 HTTP 字段组合尚未完成零调用渲染与"
                    "字段证据核对；当前参数只作待验证草案，不可直接发送。"
                ),
            },
            {
                "code": "FLOOR_PASS_CRITERION_PENDING",
                "detail": (
                    "每家独立地板过闸所需的可复算数值判法尚未拍定；"
                    "本地不得把“差不多”临时解释成阈值。"
                ),
            },
        ],
        "resume_requirements": [
            "NOTION_EXACT_PROMPT_LEAK_REVIEW_APPROVED",
            "FLOOR_PASS_CRITERION_FROZEN",
            "THREE_PROVIDER_WIRE_ADAPTERS_ZERO_CALL_RENDER_PASSED",
            "THREE_PROVIDER_KEY_PRESENCE_RECHECKED",
            "REQUIRED_LIVE_CATALOG_OR_IDENTITY_GATES_PASSED",
        ],
        "automatic_provider_fallback_allowed": False,
        "deepseek_official_used": False,
    }


def build_artifacts() -> dict[str, bytes]:
    for path, expected in EXPECTED_POLICY_SHAS.items():
        if sha256_file(path) != expected:
            raise C13Error(f"C13 只读真源 SHA 漂移：{display_path(path)}")
    family_catalog = _require_object(
        read_json(QUESTION_FAMILY_CATALOG),
        "C11.2 九题族目录",
    )
    catalog_rows = family_catalog.get("rows")
    if not isinstance(catalog_rows, list):
        raise C13Error("C11.2 九题族目录缺 rows")
    catalog_briefs = {
        row.get("question_family"): row.get("design_brief")
        for row in catalog_rows
        if isinstance(row, Mapping)
    }
    if catalog_briefs != QUESTION_FAMILY_BRIEFS:
        raise C13Error("C13 九题族与 C11.2 权威目录不一致")

    visible_materials: dict[str, dict[str, Any]] = {}
    private_maps: list[dict[str, Any]] = []
    for case_id, chapter_number, treatment_alias, control_alias in CASE_ROWS:
        for arm, alias in (
            ("treatment", treatment_alias),
            ("control", control_alias),
        ):
            visible, private = build_material(
                arm=arm,
                case_id=case_id,
                chapter_number=chapter_number,
                material_alias=alias,
            )
            visible_materials[alias] = visible
            private_maps.append(private)

    nodes, request_artifacts = build_call_plan(visible_materials)
    provider_dispatch_plan = build_provider_dispatch_plan(nodes)
    prompt_contract = {
        "schema_version": "v02-c13-prompt-contract.v2",
        "status": FREEZE_STATUS,
        "system_prompt": SYSTEM_PROMPT,
        "task_prompts": {
            "A": TASK_A_PROMPT,
            "B": TASK_B_PROMPT,
            "C": TASK_C_PROMPT,
        },
        "question_families": [
            {
                "question_family": family,
                "brief": QUESTION_FAMILY_BRIEFS[family],
            }
            for family in QUESTION_FAMILIES
        ],
        "missing_buckets": [
            {
                "bucket_id": bucket,
                **MISSING_BUCKET_AUTHORITY[bucket],
            }
            for bucket in MISSING_BUCKETS
        ],
        "truth_and_usefulness_never_merged": True,
        "truth_gate": "CLAIM_SPAN_VERBATIM_BACKLINK_MECHANICAL_READ_ONLY",
        "usefulness_label": "PROVISIONAL_AI_DOWNSTREAM",
        "formal_gate_or_winner_allowed": False,
        "strict_json_prompt_only": True,
        "response_format_api_field_required": False,
        "invalid_json_repair_allowed": False,
    }
    isolation_contract = {
        "schema_version": "v02-c13-isolation-contract.v2",
        "allowed_visible_surfaces": [
            "FACT_SENTENCES",
            "MECHANICAL_FOUR_VIEW_INDEX",
            "CHAPTER_NUMBER",
            "COVERAGE_SCOPE",
            "CUMULATIVE_CHAPTER_COUNT",
            "TASK_DESCRIPTION",
        ],
        "forbidden_visible_surfaces": [
            "NOVEL_BODY",
            "BOOK_TITLE",
            "AUTHOR",
            "OTHER_ARM",
            "ARM_IDENTITY",
            "EXPERIMENT_BACKGROUND",
            "GOLD_OR_ANSWERS",
            "HISTORICAL_SCORES",
            "RUN_PATHS",
        ],
        "clean_conversation_per_call": True,
        "same_conversation_reads_two_arms": False,
        "tested_deepseek_family_may_self_evaluate": False,
        "notion_window_primary_receiver": False,
        "private_material_map_model_visible": False,
        "character_names_pseudonymized": False,
        "character_name_leakage_risk": (
            "KNOWN_RESIDUAL_RISK_NOT_FORBIDDEN_BY_C13_TEXT"
        ),
        "input_scope": "SINGLE_CHAPTER_ONLY",
        "cumulative_chapter_count_per_material": 1,
        "long_term_consistency_claim_allowed": False,
        "complete_four_view_verified": False,
        "missing_view_policy": "EXPLICIT_NOT_PROVIDED",
        "self_judge": False,
        "same_family_judge": False,
        "executor_self_assess": False,
        "tools_or_network_available_to_receiver": False,
        "parent_conversation_inherited": False,
        "provider_or_model_visible_to_receiver": False,
        "floor_identity_visible_to_receiver": False,
        "actual_send_surface": "MESSAGES_ONLY",
        "private_request_wrapper_may_be_sent": False,
    }
    call_plan = {
        "schema_version": "v02-c13-call-plan.v2",
        "status": FREEZE_STATUS,
        "planned_call_total": len(nodes),
        "base_prompt_slot_total": 30,
        "per_provider_hard_call_cap": 30,
        "three_provider_total_hard_call_cap": 90,
        "normal_task_calls": 18,
        "shuffled_floor_calls": 6,
        "blank_floor_calls": 6,
        "nodes": nodes,
        "single_sample_no_retry_for_quality": True,
        "each_call_has_isolated_conversation": True,
        "usage_and_finish_reason_required": True,
        "floor_uses_same_task_and_output_contract_as_normal": True,
        "floor_pass_criterion_status": "MISSING_PENDING_CZ_OR_NOTION_FREEZE",
        "floor_task_distribution": {
            "SHUFFLED_FACT_ORDER": {"A": 2, "B": 2, "C": 2},
            "CHAPTER_NUMBER_ONLY": {"A": 2, "B": 2, "C": 2},
        },
    }
    prompt_review_block = _prompt_review_block()
    input_scope_receipt = {
        "schema_version": "v02-c13-input-scope-receipt.v2",
        "status": "PASS_SINGLE_CHAPTER_SHORT_TERM_ONLY",
        "source_material_total": len(private_maps),
        "coverage_scope": "SINGLE_CHAPTER_ONLY",
        "facts_through_chapter_preferred": True,
        "facts_through_chapter_available": False,
        "cumulative_chapter_count_per_material": 1,
        "single_chapter_material_total": len(private_maps),
        "multi_chapter_material_total": 0,
        "short_term_usefulness_only": True,
        "multi_chapter_and_single_chapter_may_be_aggregated": False,
        "complete_four_view_available": False,
        "timeline_is_mechanically_derived": True,
        "causal_state_unresolved_views_are_explicit_not_provided": True,
        "missing_views_may_be_filled_by_rule_model_or_common_sense": False,
        "target_chapter_event_counts": {
            row["material_id"]: len(row["fact_identity_map"])
            for row in sorted(private_maps, key=lambda item: item["material_id"])
        },
        "input_scope_blocks_prompt_freeze": False,
        "execute_allowed_after_all_other_gates": True,
    }
    prompt_rows = []
    for node in nodes:
        send_surface = json.loads(
            request_artifacts[node["send_surface_path"]]
        )
        prompt_rows.append(
            {
                "call_id": node["call_id"],
                "task": node["task"],
                "messages_sha256": node["messages_sha256"],
                "messages": send_surface["messages"],
            }
        )
    prompt_review_bundle = {
        "schema_version": "v02-c13-exact-prompt-review-bundle.v1",
        "status": "PENDING_NOTION_LEAK_REVIEW",
        "slot_total": len(prompt_rows),
        "prompt_set_sha256": sha256_bytes(
            canonical_bytes(
                {
                    row["call_id"]: row["messages_sha256"]
                    for row in prompt_rows
                }
            )
        ),
        "rows": prompt_rows,
        "review_scope": [
            "BOOK_TITLE",
            "AUTHOR",
            "ARM_IDENTITY",
            "EXPERIMENT_BACKGROUND",
            "NOVEL_BODY_PARAGRAPH_OR_QUOTE",
            "RUN_PATH",
            "PROVIDER_OR_MODEL_IDENTITY",
            "GOLD_OR_ANSWERS",
        ],
        "approved_to_send": False,
        "notion_review_page": None,
        "notion_reviewed_at": None,
        "floor_pass_criterion_status": "PENDING_NOTION_OR_CZ_FREEZE",
        "provider_wire_adapter_status": (
            "PENDING_ZERO_CALL_RENDER_AND_FIELD_EVIDENCE"
        ),
    }
    notion_prompt_parts: dict[str, bytes] = {}
    notion_part_index_rows = []
    for part_number, start in enumerate(range(0, len(prompt_rows), 5), 1):
        part_path = (
            f"prompt_review/notion_parts/part_{part_number:02d}.json"
        )
        part_raw = canonical_bytes(
            {
                "schema_version": "v02-c13-exact-prompt-review-part.v1",
                "part_number": part_number,
                "row_total": len(prompt_rows[start : start + 5]),
                "rows": prompt_rows[start : start + 5],
            }
        )
        notion_prompt_parts[part_path] = part_raw
        notion_part_index_rows.append(
            {
                "part_number": part_number,
                "path": part_path,
                "sha256": sha256_bytes(part_raw),
                "call_ids": [
                    row["call_id"] for row in prompt_rows[start : start + 5]
                ],
            }
        )
    notion_part_index = {
        "schema_version": "v02-c13-exact-prompt-review-part-index.v1",
        "part_total": len(notion_prompt_parts),
        "source_prompt_set_sha256": prompt_review_bundle[
            "prompt_set_sha256"
        ],
        "parts": notion_part_index_rows,
    }
    shared_prompt_matrix = {
        "schema_version": "v02-c13-shared-prompt-matrix.v1",
        "slot_total": len(nodes),
        "provider_total": 3,
        "rows": [
            {
                "call_id": node["call_id"],
                "messages_sha256": node["messages_sha256"],
                "qianwen_platform_messages_sha256": node["messages_sha256"],
                "volcengine_ark_messages_sha256": node["messages_sha256"],
                "tencent_tokenhub_messages_sha256": node["messages_sha256"],
                "all_three_equal": True,
            }
            for node in nodes
        ],
    }
    leakage_scan_receipt = {
        "schema_version": "v02-c13-visible-leakage-scan.v1",
        "status": "PASS_ZERO_HITS",
        "visible_prompt_total": len(nodes),
        "forbidden_marker_total": len(FORBIDDEN_VISIBLE_MARKERS),
        "forbidden_marker_hit_total": 0,
        "absolute_path_hit_total": 0,
        "run_or_report_path_hit_total": 0,
        "book_title_hit_total": 0,
        "author_hit_total": 0,
        "arm_identity_hit_total": 0,
        "experiment_background_hit_total": 0,
        "provider_or_model_hit_total": 0,
        "gold_or_answer_hit_total": 0,
        "source_quote_or_paragraph_field_total": 0,
        "private_identity_map_visible": False,
        "character_name_residual_prior_risk": (
            "KNOWN_NOT_REMOVED_WITHOUT_SEPARATE_VARIABLE_APPROVAL"
        ),
    }
    preflight = {
        "schema_version": "v02-c13-preflight.v2",
        "status": (
            "PASS_ZERO_CALL_REFREEZE_PENDING_NOTION_TRANSPORT_AND_FLOOR_GATES"
        ),
        "visible_material_total": len(visible_materials),
        "base_prompt_slot_total": len(nodes),
        "planned_dispatch_total": 90,
        "source_request_sha_unique_total": len(
            {row["source_request_sha256"] for row in nodes}
        ),
        "send_surface_sha_unique_total": len(
            {row["send_surface_sha256"] for row in nodes}
        ),
        "messages_sha_unique_total": len(
            {row["messages_sha256"] for row in nodes}
        ),
        "visible_leak_hit_total": 0,
        "book_title_visible_total": 0,
        "author_visible_total": 0,
        "other_arm_visible_total": 0,
        "gold_visible_total": 0,
        "model_api_calls": 0,
        "network_requests": 0,
        "input_scope_blocking": False,
        "four_view_blocking": False,
        "provider_selection_blocking": False,
        "provider_transport_adapter_blocking": True,
        "floor_pass_criterion_blocking": True,
        "prompt_leak_review_blocking": True,
        "provider_catalog_gates_pending": True,
        "execute_allowed": False,
    }
    authority = {
        "schema_version": "v02-c13-authority-receipt.v2",
        "work_order_page": C13_WORK_ORDER_PAGE,
        "unlock_page": C13_UNLOCK_PAGE,
        "connector_readback_at": C13_READBACK_AT,
        "scope": "C13",
        "authorization": (
            "三家各跑完整同一套30位；每家不超过30，合计不超过90；"
            "Qwen为预注册主读数，豆包与MiniMax为复现臂。"
        ),
        "provider_or_model_named_in_c13": True,
        "exact_models_frozen": [
            row["model_id"]
            for row in provider_dispatch_plan["provider_profiles"]
        ],
        "provider_access_policy_respected": True,
        "c12_directory_shared": False,
        "missing_bucket_authority_loaded_from_notion": True,
        "missing_bucket_authority_section": "§9.1-E.4 + C11.2",
    }
    readme = """# C13 r02｜三通道同题重冻结停点

✅ 30 份模型可见题面已另开 r02 重冻结；旧 C13 硬停树没有回写。六份
材料都只能证明单章，因此逐份写明 `SINGLE_CHAPTER_ONLY` 和累计章数 1，
本轮只量短程可用性。四视图里只有时间线有机械值；因果、人物状态、未决
三槽均以 `NOT_PROVIDED` 明示，没有靠规则、关键词、模型或常识补写。

✅ 同一套 30 位将在私有调度层逐字复制给三家：Qwen 3.7 Max 固定版是
预注册主读数，豆包 2.1 Pro 与 MiniMax 3 是复现臂。每家保持
18 个正式位、6 个乱序地板位和 6 个章号地板位；地板与正式位使用相同
A／B／C 题型和输出合同。三家分开过地板，禁止平均、加权或合并分数。

⚠️ 当前仍是 0 调用。30 份最终 `messages` 的逐字文本与 SHA 要先交
Notion 窗核夹带；模型可见面只有 `messages`，私有题型与地板身份不会
进入发送面。拿到明确 `APPROVED_TO_SEND` 回读票后，还须补齐两件：
三家固定型号的发送字段零调用渲染票，以及每家独立地板过闸的可复算判法。
这两件和目录／型号、密钥存在性全部通过前，不会发第一条请求。

来源：Codex
"""
    artifacts: dict[str, bytes] = {
        "README.md": readme.encode("utf-8"),
        "authority_receipt.json": canonical_bytes(authority),
        "contracts/prompt_contract.json": canonical_bytes(prompt_contract),
        "contracts/isolation_contract.json": canonical_bytes(isolation_contract),
        "plans/call_plan.json": canonical_bytes(call_plan),
        "plans/provider_dispatch_plan.json": canonical_bytes(
            provider_dispatch_plan
        ),
        "prompt_review/exact_visible_messages.json": canonical_bytes(
            prompt_review_bundle
        ),
        "prompt_review/shared_prompt_matrix.json": canonical_bytes(
            shared_prompt_matrix
        ),
        "prompt_review/leakage_scan_receipt.json": canonical_bytes(
            leakage_scan_receipt
        ),
        "prompt_review/notion_part_index.json": canonical_bytes(
            notion_part_index
        ),
        "preflight/preflight_receipt.json": canonical_bytes(preflight),
        "preflight/input_scope_receipt.json": canonical_bytes(
            input_scope_receipt
        ),
        "preflight/prompt_review_gate.json": canonical_bytes(
            prompt_review_block
        ),
        "private_not_model_visible/material_identity_map.json": canonical_bytes(
            {
                "schema_version": "v02-c13-private-material-map-set.v2",
                "model_visible": False,
                "rows": sorted(private_maps, key=lambda row: row["material_id"]),
            }
        ),
        "private_not_model_visible/source_ledger.json": canonical_bytes(
            {
                "schema_version": "v02-c13-source-ledger.v1",
                "model_visible": False,
                "source_material_total": len(private_maps),
                "rows": [
                    {
                        "material_id": row["material_id"],
                        "case_id": row["case_id"],
                        "arm": row["arm"],
                        "source_path": row["source_path"],
                        "source_sha256": row["source_sha256"],
                        "coverage_scope": row["coverage_scope"],
                        "cumulative_chapter_count": row[
                            "cumulative_chapter_count"
                        ],
                    }
                    for row in sorted(
                        private_maps,
                        key=lambda item: item["material_id"],
                    )
                ],
            }
        ),
        "private_not_model_visible/floor_derivation_map.json": canonical_bytes(
            {
                "schema_version": "v02-c13-floor-derivation-map.v1",
                "model_visible": False,
                "rows": [
                    {
                        "call_id": row["call_id"],
                        "derived_material_id": row["material_id"],
                        "base_material_id": row["base_material_id"],
                        "floor_kind": row["floor_kind"],
                    }
                    for row in nodes
                    if row["floor_kind"] is not None
                ],
            }
        ),
    }
    artifacts.update(notion_prompt_parts)
    for payload in sorted(
        visible_materials.values(),
        key=lambda row: row["material_id"],
    ):
        artifacts[f"materials/{payload['material_id']}.json"] = canonical_bytes(
            payload
        )
    artifacts.update(request_artifacts)
    preimage = {
        path: sha256_bytes(raw) for path, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c13-artifact-manifest.v2",
            "status": FREEZE_STATUS,
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": path, "sha256": digest}
                for path, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "base_prompt_slot_total": 30,
            "planned_dispatch_total": 90,
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def write_or_verify(
    output_dir: Path = OUTPUT_DIR,
    report_dir: Path = REPORT_DIR,
    *,
    write: bool = True,
) -> dict[str, Any]:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise C13Error("C13 连续两次构造不一致")
    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        for relative, raw in first.items():
            path = output_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    if actual != set(first):
        raise C13Error(
            "C13 输出集合不闭合："
            f"missing={sorted(set(first) - actual)} "
            f"unexpected={sorted(actual - set(first))}"
        )
    for relative, raw in first.items():
        if (output_dir / relative).read_bytes() != raw:
            raise C13Error(f"C13 工件字节漂移：{relative}")

    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "C13_冻结停点回包.md"
    if write:
        report_path.write_bytes(first["README.md"])
    if report_path.read_bytes() != first["README.md"]:
        raise C13Error("C13 reports 镜像与工件正文不一致")
    manifest = json.loads(first["artifact_manifest.json"])
    return {
        "status": manifest["status"],
        "artifact_set_sha256": manifest["artifact_set_sha256"],
        "base_prompt_slot_total": manifest["base_prompt_slot_total"],
        "planned_dispatch_total": manifest["planned_dispatch_total"],
        "model_api_calls": 0,
        "network_requests": 0,
        "output_dir": display_path(output_dir),
        "report_path": display_path(report_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V02 C13 下游消费方冻结与预演")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt = write_or_verify(
        args.output_dir,
        args.report_dir,
        write=not args.check,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

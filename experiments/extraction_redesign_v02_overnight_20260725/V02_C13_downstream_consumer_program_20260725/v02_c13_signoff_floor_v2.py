#!/usr/bin/env python3
"""C13 r04：签票证明与预验收 CLAIM 地板判定器 v2。

本工具只读 r02 的 30 份冻结题面与 r03 的 90 份冻结运输外壳，生成：

- 三份可直接贴到 Notion 正文审查的逐字题面；
- 30 位差异表、90 份黑名单扫描和允许差异证明；
- 预验收 CLAIM 统计合同与可复用判定器。

本文件不读取密钥、不访问网络、不发送模型请求，也不回写 r02/r03。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import v02_c13_downstream_consumer as c13


ROOT = Path(__file__).resolve().parents[3]
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
SOURCE_R02 = V02_ROOT / "V02_C13_downstream_consumer_r02_20260726"
SOURCE_R03 = V02_ROOT / "V02_C13_downstream_consumer_wire_r03_20260726"
OUTPUT_DIR = (
    V02_ROOT
    / "V02_C13_downstream_consumer_signoff_floor_v2_r04_20260726"
)
REPORT_DIR = (
    ROOT
    / "reports/抽取工序重设计v0.2_C13签票证明与地板判定器_r04_20260726"
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
EXPECTED_PROMPT_SET_SHA256 = (
    "1302b5fbda68f0b525d2e32267cd2084a1032be1d8a8335a92f869a451570b3f"
)
EXPECTED_C13_PROGRAM_SHA256 = (
    # M1-04：只跟随供应商访问策略重签，不改题面、判据或发送合同。
    "909c9b6671c9b6151511e5794085eb062e9a9880aa59638a4d4afc504ed24508"
)

AUTHORITY_PAGE = "https://app.notion.com/p/3a85cadc4d0f81eabe45e5dea9292f68"
AUTHORITY_DECISION_AT = "2026-07-26T06:25:00+08:00"
SAMPLE_CALL_IDS = ("C13-N01", "C13-N14", "C13-N05")
EXPECTED_PROVIDER_IDS = (
    "qianwen_platform",
    "volcengine_ark",
    "tencent_tokenhub",
)
EXPECTED_DENOMINATORS = {
    "FORMAL": 54,
    "SHUFFLED_FACT_ORDER": 18,
    "CHAPTER_NUMBER_ONLY": 18,
}

ALLOWED_USER_VARIATION_PATHS = (
    "/task_instruction",
    "/output_contract",
    "/material/material_id",
    "/material/chapter_number",
    "/material/facts",
    "/material/four_views/timeline/items",
)

EXPECTED_USER_TOP_KEYS = {"material", "output_contract", "task_instruction"}
EXPECTED_MATERIAL_KEYS = {
    "schema_version",
    "material_id",
    "chapter_number",
    "coverage_scope",
    "cumulative_chapter_count",
    "facts",
    "four_views",
}
EXPECTED_VIEW_KEYS = {
    "timeline",
    "causal_edges",
    "character_states",
    "unresolved_items",
}
EXPECTED_VIEW_SLOT_KEYS = {"status", "items"}
EXPECTED_FACT_KEYS = {"fact_id", "fact"}
EXPECTED_TIMELINE_ITEM_KEYS = {"seq", "fact_id"}

MESSAGE_BLACKLIST_RULES: tuple[dict[str, str], ...] = (
    {
        "rule_id": "BOOK_TITLE_OR_ALIAS",
        "pattern": r"大王饶命|神秘复苏|知否知否应是绿肥红瘦|知否",
    },
    {
        "rule_id": "AUTHOR_OR_PEN_NAME",
        "pattern": r"会说话的肘子|佛前献花|关心则乱|作者",
    },
    {
        "rule_id": "EXPERIMENT_IDENTITY",
        "pattern": (
            r"实验臂|对照臂|实验|对照|评测|"
            r"\barm\b|\bbaseline\b|\bablation\b|\bbenchmark\b|"
            r"\btreatment\b|\bcontrol\b"
        ),
    },
    {
        "rule_id": "FLOOR_IDENTITY",
        "pattern": r"地板|打乱|乱序|\bfloor\b|\bshuffle(?:d)?\b|\bblank\b",
    },
    {
        "rule_id": "GOLD_OR_INTERNAL_METRIC",
        "pattern": r"金标|\bgold\b|config/gold|claim_span|\bqcr\b",
    },
    {
        "rule_id": "LOCAL_PATH",
        "pattern": (
            r"/Users/|file://|(?:^|[\s\"'])runs/|(?:^|[\s\"'])reports/|"
            r"(?:^|[\s\"'])experiments/|(?:^|[\s\"'])config/"
        ),
    },
    {
        "rule_id": "BATCH_ID",
        "pattern": r"\bC12\b|\bC13\b|\bV02\b",
    },
    {
        "rule_id": "MODEL_OR_PROVIDER",
        "pattern": (
            r"\bqwen\b|千问|\bdeepseek\b|\bdoubao\b|豆包|"
            r"\bminimax\b|\bling\b|\bsensenova\b|商汤|"
            r"\btokenhub\b|腾讯|火山|\bvolcengine\b|\bdashscope\b|"
            r"\bprovider\b|供应商"
        ),
    },
    {
        "rule_id": "INTERNAL_DENOMINATOR_CONTEXT",
        "pattern": (
            r"(?:分母|denominator|计分|覆盖率|原子数|事实数|样本数|题数)"
            r"[^\n]{0,12}(?:49|321)\b|"
            r"\b(?:49|321)[^\n]{0,12}"
            r"(?:分母|denominator|原子|事实|样本|题)|"
            r"\b\d+\s*/\s*(?:49|321)\b"
        ),
    },
)

FORBIDDEN_WIRE_KEYS = {
    "authorization",
    "headers",
    "api_key",
    "api_key_value",
    "secret",
    "secret_value",
    "tools",
    "tool_choice",
}
FORBIDDEN_WIRE_VALUE_PATTERNS = (
    re.compile(r"authorization\s*:\s*bearer", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]+", re.IGNORECASE),
)


class C13R04Error(RuntimeError):
    """r04 冻结或验收不满足机械合同。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise C13R04Error(f"JSON 读取失败：{path}") from exc


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _verify_manifest_tree(
    directory: Path,
    *,
    expected_manifest_sha256: str,
    expected_artifact_set_sha256: str,
) -> dict[str, Any]:
    manifest_path = directory / "artifact_manifest.json"
    if sha256_file(manifest_path) != expected_manifest_sha256:
        raise C13R04Error(f"冻结清单 SHA 漂移：{display_path(manifest_path)}")
    manifest = read_json(manifest_path)
    if manifest.get("artifact_set_sha256") != expected_artifact_set_sha256:
        raise C13R04Error(f"冻结工件集合 SHA 漂移：{display_path(directory)}")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise C13R04Error(f"冻结清单没有逐文件记录：{display_path(directory)}")
    expected: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise C13R04Error("冻结清单行不是对象")
        relative = row.get("path")
        digest = row.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative == "artifact_manifest.json"
            or relative in expected
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise C13R04Error("冻结清单行字段非法、重复或指向自身")
        expected[relative] = digest
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    }
    if actual != set(expected):
        raise C13R04Error(
            f"冻结工件集合不闭合：{display_path(directory)} "
            f"missing={sorted(set(expected) - actual)} "
            f"unexpected={sorted(actual - set(expected))}"
        )
    for relative, digest in expected.items():
        if sha256_file(directory / relative) != digest:
            raise C13R04Error(f"冻结实物 SHA 漂移：{relative}")
    rebuilt = sha256_bytes(canonical_bytes(expected))
    if rebuilt != expected_artifact_set_sha256:
        raise C13R04Error(f"冻结工件集合重建 SHA 漂移：{display_path(directory)}")
    return {
        "manifest_sha256": expected_manifest_sha256,
        "artifact_set_sha256": rebuilt,
        "verified_file_total": len(expected),
        "manifest_paths": sorted(expected),
    }


def _load_sources() -> dict[str, Any]:
    if sha256_file(Path(c13.__file__)) != EXPECTED_C13_PROGRAM_SHA256:
        raise C13R04Error("r02 题面生成器 SHA 漂移")
    r02_verification = _verify_manifest_tree(
        SOURCE_R02,
        expected_manifest_sha256=EXPECTED_R02_MANIFEST_SHA256,
        expected_artifact_set_sha256=EXPECTED_R02_ARTIFACT_SET_SHA256,
    )
    r03_verification = _verify_manifest_tree(
        SOURCE_R03,
        expected_manifest_sha256=EXPECTED_R03_MANIFEST_SHA256,
        expected_artifact_set_sha256=EXPECTED_R03_ARTIFACT_SET_SHA256,
    )
    prompt_bundle = read_json(
        SOURCE_R02 / "prompt_review/exact_visible_messages.json"
    )
    if prompt_bundle.get("prompt_set_sha256") != EXPECTED_PROMPT_SET_SHA256:
        raise C13R04Error("r02 题面集合 SHA 漂移")
    call_plan = read_json(SOURCE_R02 / "plans/call_plan.json")
    wire_plan = read_json(SOURCE_R03 / "plans/wire_dispatch_plan.json")
    rows = prompt_bundle.get("rows")
    if not isinstance(rows, list) or len(rows) != 30:
        raise C13R04Error("r02 逐字题面不是 30 份")
    nodes = call_plan.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != 30:
        raise C13R04Error("r02 调用计划不是 30 位")
    wire_rows = wire_plan.get("rows")
    if not isinstance(wire_rows, list) or len(wire_rows) != 90:
        raise C13R04Error("r03 运输外壳不是 90 份")
    return {
        "r02_verification": r02_verification,
        "r03_verification": r03_verification,
        "prompt_bundle": prompt_bundle,
        "call_plan": call_plan,
        "wire_plan": wire_plan,
    }


def _parse_prompt_row(row: Mapping[str, Any]) -> dict[str, Any]:
    messages = row.get("messages")
    if (
        not isinstance(messages, list)
        or len(messages) != 2
        or not all(isinstance(message, Mapping) for message in messages)
        or messages[0].get("role") != "system"
        or messages[1].get("role") != "user"
        or any(set(message) != {"role", "content"} for message in messages)
    ):
        raise C13R04Error(f"{row.get('call_id')} 消息结构不是固定两条")
    if not all(isinstance(message["content"], str) for message in messages):
        raise C13R04Error(f"{row.get('call_id')} 消息正文不是字符串")
    try:
        user_payload = json.loads(messages[1]["content"])
    except json.JSONDecodeError as exc:
        raise C13R04Error(f"{row.get('call_id')} user 正文不是 JSON") from exc
    if not isinstance(user_payload, Mapping):
        raise C13R04Error(f"{row.get('call_id')} user JSON 不是对象")
    if set(user_payload) != EXPECTED_USER_TOP_KEYS:
        raise C13R04Error(f"{row.get('call_id')} user 顶层字段漂移")
    material = user_payload.get("material")
    if not isinstance(material, Mapping) or set(material) != EXPECTED_MATERIAL_KEYS:
        raise C13R04Error(f"{row.get('call_id')} material 字段漂移")
    views = material.get("four_views")
    if not isinstance(views, Mapping) or set(views) != EXPECTED_VIEW_KEYS:
        raise C13R04Error(f"{row.get('call_id')} four_views 字段漂移")
    for name, value in views.items():
        if not isinstance(value, Mapping) or set(value) != EXPECTED_VIEW_SLOT_KEYS:
            raise C13R04Error(f"{row.get('call_id')} {name} 字段漂移")
    facts = material.get("facts")
    timeline = views["timeline"].get("items")
    if not isinstance(facts, list) or not isinstance(timeline, list):
        raise C13R04Error(f"{row.get('call_id')} facts 或 timeline 不是数组")
    if any(not isinstance(item, Mapping) or set(item) != EXPECTED_FACT_KEYS for item in facts):
        raise C13R04Error(f"{row.get('call_id')} fact 行字段漂移")
    if any(
        not isinstance(item, Mapping) or set(item) != EXPECTED_TIMELINE_ITEM_KEYS
        for item in timeline
    ):
        raise C13R04Error(f"{row.get('call_id')} timeline 行字段漂移")
    return {
        "call_id": row["call_id"],
        "task": row["task"],
        "messages": messages,
        "messages_sha256": sha256_bytes(canonical_bytes(messages)),
        "system_prompt": messages[0]["content"],
        "user_payload": dict(user_payload),
        "material": dict(material),
    }


def _normalize_prompt(parsed: Mapping[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(parsed["user_payload"])
    normalized["task_instruction"] = "<TASK_TEMPLATE_CHOICE>"
    normalized["output_contract"] = "<OUTPUT_CONTRACT_TEMPLATE_CHOICE>"
    normalized["material"]["material_id"] = "<MATERIAL_ID>"
    normalized["material"]["chapter_number"] = "<CHAPTER_NUMBER>"
    normalized["material"]["facts"] = "<FACTS>"
    normalized["material"]["four_views"]["timeline"]["items"] = "<TIMELINE_ITEMS>"
    return {
        "messages": [
            {"role": "system", "content": "<GLOBAL_SYSTEM_PROMPT>"},
            {
                "role": "user",
                "content": normalized,
            },
        ]
    }


def _material_multiset(facts: Sequence[Mapping[str, Any]]) -> Counter[bytes]:
    return Counter(canonical_bytes(dict(item)) for item in facts)


def _validate_material_derivation(
    parsed: Mapping[str, Any],
    plan_node: Mapping[str, Any],
) -> dict[str, Any]:
    material = parsed["material"]
    base_material_id = str(plan_node["base_material_id"])
    base = read_json(SOURCE_R02 / f"materials/{base_material_id}.json")
    floor_kind = plan_node.get("floor_kind")
    if material["schema_version"] != "chapter-fact-material.v1":
        raise C13R04Error(f"{parsed['call_id']} material schema 漂移")
    if material["coverage_scope"] != "SINGLE_CHAPTER_ONLY":
        raise C13R04Error(f"{parsed['call_id']} coverage_scope 漂移")
    if material["cumulative_chapter_count"] != 1:
        raise C13R04Error(f"{parsed['call_id']} 累计章数不是 1")
    if material["chapter_number"] != base["chapter_number"]:
        raise C13R04Error(f"{parsed['call_id']} 章号与底料不一致")
    facts = material["facts"]
    timeline = material["four_views"]["timeline"]["items"]
    if material["four_views"]["timeline"]["status"] != "PROVIDED_MECHANICAL":
        raise C13R04Error(f"{parsed['call_id']} timeline 状态漂移")
    for slot in ("causal_edges", "character_states", "unresolved_items"):
        if material["four_views"][slot] != {
            "status": "NOT_PROVIDED",
            "items": [],
        }:
            raise C13R04Error(f"{parsed['call_id']} {slot} 非冻结空槽")
    expected_timeline = [
        {"seq": index, "fact_id": fact["fact_id"]}
        for index, fact in enumerate(facts, 1)
    ]
    if timeline != expected_timeline:
        raise C13R04Error(f"{parsed['call_id']} timeline 没有机械跟随 facts")

    if floor_kind is None:
        if material != base:
            raise C13R04Error(f"{parsed['call_id']} 正式位没有逐字复用冻结材料")
        derivation = "FORMAL_EXACT_FROZEN_MATERIAL"
    elif floor_kind == "SHUFFLED_FACT_ORDER":
        if (
            len(facts) != len(base["facts"])
            or _material_multiset(facts) != _material_multiset(base["facts"])
        ):
            raise C13R04Error(f"{parsed['call_id']} 乱序位增删改了事实")
        if len(facts) > 1 and facts == base["facts"]:
            raise C13R04Error(f"{parsed['call_id']} 乱序位实际没有改变顺序")
        derivation = "SHUFFLE_ONLY_SAME_FACT_MULTISET"
    elif floor_kind == "CHAPTER_NUMBER_ONLY":
        if facts or timeline:
            raise C13R04Error(f"{parsed['call_id']} 章号位夹带事实或时间线")
        derivation = "CHAPTER_ONLY_EMPTY_FACTS_AND_TIMELINE"
    else:
        raise C13R04Error(f"{parsed['call_id']} 未知题型")
    return {
        "derivation": derivation,
        "fact_sentence_total": len(facts),
        "timeline_item_total": len(timeline),
        "base_material_id": base_material_id,
        "floor_kind": floor_kind or "FORMAL",
    }


def _build_prompt_evidence(
    prompt_bundle: Mapping[str, Any],
    call_plan: Mapping[str, Any],
) -> dict[str, Any]:
    rows = {
        str(row["call_id"]): _parse_prompt_row(row)
        for row in prompt_bundle["rows"]
    }
    nodes = {str(row["call_id"]): row for row in call_plan["nodes"]}
    if set(rows) != set(nodes) or len(rows) != 30:
        raise C13R04Error("30 份题面与调用计划未一一对应")

    system_variants = {row["system_prompt"] for row in rows.values()}
    if system_variants != {c13.SYSTEM_PROMPT}:
        raise C13R04Error("system prompt 没有逐字等于钉住程序常量")
    expected_task_prompts = {
        "A": c13.TASK_A_PROMPT,
        "B": c13.TASK_B_PROMPT,
        "C": c13.TASK_C_PROMPT,
    }
    task_templates: dict[str, dict[str, Any]] = {}
    task_template_hashes: dict[str, dict[str, str]] = {}
    for task in ("A", "B", "C"):
        task_rows = [row for row in rows.values() if row["task"] == task]
        if len(task_rows) != 10:
            raise C13R04Error(f"任务 {task} 不是 10 份")
        instruction = expected_task_prompts[task]
        contract = c13.output_contract(task)
        if any(
            row["user_payload"]["task_instruction"] != instruction
            for row in task_rows
        ):
            raise C13R04Error(f"任务 {task} 说明没有逐字等于钉住程序常量")
        if any(
            row["user_payload"]["output_contract"] != contract
            for row in task_rows
        ):
            raise C13R04Error(f"任务 {task} 输出合同没有逐字等于钉住程序常量")
        task_templates[task] = {
            "task_instruction": instruction,
            "output_contract": contract,
        }
        task_template_hashes[task] = {
            "task_instruction_sha256": sha256_bytes(instruction.encode("utf-8")),
            "output_contract_sha256": sha256_bytes(canonical_bytes(contract)),
        }

    normalized_hashes = {
        sha256_bytes(canonical_bytes(_normalize_prompt(row)))
        for row in rows.values()
    }
    if len(normalized_hashes) != 1:
        raise C13R04Error("允许字段规范化后仍出现多个题面模板")

    table_rows: list[dict[str, Any]] = []
    for call_id in sorted(rows):
        parsed = rows[call_id]
        node = nodes[call_id]
        if parsed["task"] != node["task"]:
            raise C13R04Error(f"{call_id} 任务身份与调用计划不一致")
        if parsed["messages_sha256"] != node["messages_sha256"]:
            raise C13R04Error(f"{call_id} messages SHA 与调用计划不一致")
        derivation = _validate_material_derivation(parsed, node)
        material = parsed["material"]
        table_rows.append(
            {
                "call_id": call_id,
                "task": parsed["task"],
                "prompt_kind": derivation["floor_kind"],
                "cumulative_chapter_count": material[
                    "cumulative_chapter_count"
                ],
                "fact_sentence_total": derivation["fact_sentence_total"],
                "timeline_item_total": derivation["timeline_item_total"],
                "material_sha256": sha256_bytes(canonical_bytes(material)),
                "messages_sha256": parsed["messages_sha256"],
                "derivation": derivation["derivation"],
                "observed_variable_paths": list(ALLOWED_USER_VARIATION_PATHS),
                "unexpected_variable_paths": [],
            }
        )

    sample_rows = [rows[call_id] for call_id in SAMPLE_CALL_IDS]
    sample_kinds = {
        nodes[row["call_id"]].get("floor_kind") or "FORMAL"
        for row in sample_rows
    }
    sample_tasks = {row["task"] for row in sample_rows}
    if sample_kinds != {
        "FORMAL",
        "SHUFFLED_FACT_ORDER",
        "CHAPTER_NUMBER_ONLY",
    } or sample_tasks != {"A", "B", "C"}:
        raise C13R04Error("三份代表题面没有同时覆盖三种材料形态与 A/B/C")

    return {
        "parsed_rows": rows,
        "nodes": nodes,
        "table_rows": table_rows,
        "task_templates": task_templates,
        "task_template_hashes": task_template_hashes,
        "system_prompt": next(iter(system_variants)),
        "system_prompt_sha256": sha256_bytes(
            next(iter(system_variants)).encode("utf-8")
        ),
        "normalized_template_sha256": next(iter(normalized_hashes)),
    }


def _compile_blacklist_rules() -> tuple[tuple[str, re.Pattern[str]], ...]:
    return tuple(
        (
            rule["rule_id"],
            re.compile(rule["pattern"], re.IGNORECASE),
        )
        for rule in MESSAGE_BLACKLIST_RULES
    )


def scan_messages_blacklist(
    messages: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    rules = _compile_blacklist_rules()
    for message_index, message in enumerate(messages):
        content = message.get("content")
        if not isinstance(content, str):
            hits.append(
                {
                    "rule_id": "NON_STRING_MESSAGE_CONTENT",
                    "message_index": message_index,
                    "role": message.get("role"),
                    "matched_text": repr(content),
                }
            )
            continue
        normalized_content = unicodedata.normalize("NFKC", content)
        for rule_id, pattern in rules:
            for match in pattern.finditer(normalized_content):
                hits.append(
                    {
                        "rule_id": rule_id,
                        "message_index": message_index,
                        "role": message.get("role"),
                        "matched_text": match.group(0),
                    }
                )
    return hits


def _walk_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.append(str(key).lower())
            keys.extend(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_walk_keys(child))
    return keys


def scan_wire_security(body: Mapping[str, Any]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for key in _walk_keys(body):
        if key in FORBIDDEN_WIRE_KEYS:
            hits.append({"rule_id": "FORBIDDEN_WIRE_KEY", "matched_text": key})
    raw = json.dumps(body, ensure_ascii=False)
    for pattern in FORBIDDEN_WIRE_VALUE_PATTERNS:
        for match in pattern.finditer(raw):
            hits.append(
                {
                    "rule_id": "SECRET_OR_AUTHORIZATION_SHAPE",
                    "matched_text": match.group(0),
                }
            )
    return hits


def _build_wire_evidence(
    prompt_evidence: Mapping[str, Any],
    wire_plan: Mapping[str, Any],
    r03_manifest_paths: set[str],
) -> dict[str, Any]:
    parsed_rows = prompt_evidence["parsed_rows"]
    profile_fields = {
        provider_id: set(
            read_json(SOURCE_R03 / f"profiles/{provider_id}.json")[
                "allowed_body_fields"
            ]
        )
        for provider_id in EXPECTED_PROVIDER_IDS
    }
    binding_rows: list[dict[str, Any]] = []
    scan_rows: list[dict[str, Any]] = []
    expected_pairs = {
        (provider_id, call_id)
        for provider_id in EXPECTED_PROVIDER_IDS
        for call_id in parsed_rows
    }
    actual_pairs: set[tuple[str, str]] = set()

    for row in wire_plan["rows"]:
        provider_id = str(row["provider_id"])
        call_id = str(row["base_call_id"])
        pair = (provider_id, call_id)
        if pair in actual_pairs:
            raise C13R04Error(f"运输位重复：{provider_id}/{call_id}")
        actual_pairs.add(pair)
        if pair not in expected_pairs:
            raise C13R04Error(f"运输位越界：{provider_id}/{call_id}")
        body_path = str(row["body_path"])
        if body_path not in r03_manifest_paths:
            raise C13R04Error(f"运输 body 未被 r03 总清单收录：{body_path}")
        body = read_json(SOURCE_R03 / body_path)
        if not isinstance(body, Mapping):
            raise C13R04Error(f"运输 body 不是对象：{body_path}")
        source_messages = parsed_rows[call_id]["messages"]
        body_messages = body.get("messages")
        source_messages_sha256 = sha256_bytes(canonical_bytes(source_messages))
        body_messages_sha256 = sha256_bytes(canonical_bytes(body_messages))
        fields_match = set(body) == profile_fields[provider_id]
        messages_equal = body_messages == source_messages
        body_sha256 = sha256_file(SOURCE_R03 / body_path)
        if body_sha256 != row["body_sha256"]:
            raise C13R04Error(f"运输 body SHA 与 r03 计划不一致：{body_path}")
        if not fields_match or not messages_equal:
            raise C13R04Error(f"运输 body 字段或 messages 漂移：{body_path}")

        message_hits = scan_messages_blacklist(body_messages)
        wire_hits = scan_wire_security(body)
        binding_rows.append(
            {
                "provider_id": provider_id,
                "call_id": call_id,
                "source_prompt_path": (
                    "prompt_review/exact_visible_messages.json"
                ),
                "source_messages_sha256": source_messages_sha256,
                "wire_body_path": body_path,
                "wire_body_sha256": body_sha256,
                "wire_messages_sha256": body_messages_sha256,
                "messages_byte_equal": messages_equal,
                "body_field_set_exact": fields_match,
                "body_fields": sorted(body),
                "manifest_member": True,
            }
        )
        scan_rows.append(
            {
                "provider_id": provider_id,
                "call_id": call_id,
                "wire_body_path": body_path,
                "wire_body_sha256": body_sha256,
                "messages_sha256": body_messages_sha256,
                "message_blacklist_hits": message_hits,
                "message_blacklist_hit_total": len(message_hits),
                "wire_security_hits": wire_hits,
                "wire_security_hit_total": len(wire_hits),
            }
        )

    if actual_pairs != expected_pairs:
        raise C13R04Error(
            "30 题 × 3 家运输笛卡尔积不闭合："
            f"missing={sorted(expected_pairs - actual_pairs)} "
            f"unexpected={sorted(actual_pairs - expected_pairs)}"
        )
    if any(
        row["message_blacklist_hit_total"] or row["wire_security_hit_total"]
        for row in scan_rows
    ):
        raise C13R04Error("90 份运输件出现黑名单或密钥／授权形态命中")
    return {
        "binding_rows": sorted(
            binding_rows,
            key=lambda row: (row["provider_id"], row["call_id"]),
        ),
        "scan_rows": sorted(
            scan_rows,
            key=lambda row: (row["provider_id"], row["call_id"]),
        ),
    }


def _nonempty_answer(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def observe_task_b_claims(
    payload: Any,
    *,
    allowed_fact_ids: set[str],
) -> dict[str, Any]:
    """在合同验收前观察任务 B 原始声称，不修 JSON、不补字段。"""

    reasons: list[str] = []
    if not isinstance(payload, Mapping):
        return {
            "observable": False,
            "claim_count": None,
            "question_total": 0,
            "failure_codes": ["CLAIM_UNOBSERVABLE_PAYLOAD_NOT_OBJECT"],
            "questions": [],
        }
    answers = payload.get("answers")
    if not isinstance(answers, list):
        return {
            "observable": False,
            "claim_count": None,
            "question_total": 0,
            "failure_codes": ["CLAIM_UNOBSERVABLE_ANSWERS_NOT_ARRAY"],
            "questions": [],
        }

    questions: list[dict[str, Any]] = []
    seen: set[str] = set()
    observable = True
    for index, raw_row in enumerate(answers):
        if not isinstance(raw_row, Mapping):
            observable = False
            reasons.append("CLAIM_UNOBSERVABLE_ANSWER_ROW_NOT_OBJECT")
            questions.append(
                {
                    "index": index,
                    "question_family": None,
                    "claim": None,
                    "failure_codes": ["ANSWER_ROW_NOT_OBJECT"],
                }
            )
            continue
        family = raw_row.get("question_family")
        status = raw_row.get("status")
        answer_present = "answer" in raw_row
        answer_nonempty = (
            _nonempty_answer(raw_row.get("answer")) if answer_present else False
        )
        ids = raw_row.get("supporting_fact_ids")
        row_failures: list[str] = []
        if (
            not isinstance(family, str)
            or family not in c13.QUESTION_FAMILIES
            or family in seen
        ):
            observable = False
            row_failures.append("QUESTION_FAMILY_MISSING_DUPLICATE_OR_UNKNOWN")
        else:
            seen.add(family)
        if not isinstance(status, str) or status not in c13.ANSWER_STATUSES:
            observable = False
            row_failures.append("STATUS_MISSING_OR_UNKNOWN")
        if not answer_present:
            observable = False
            row_failures.append("ANSWER_FIELD_MISSING")
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            observable = False
            row_failures.append("SUPPORTING_FACT_IDS_MALFORMED")
            unknown_ids: list[str] = []
            any_ids = bool(ids)
        else:
            unknown_ids = sorted(set(ids) - allowed_fact_ids)
            any_ids = bool(ids)
        claimed = (
            status == "ANSWERED"
            or answer_nonempty
            or bool(unknown_ids)
        )
        questions.append(
            {
                "index": index,
                "question_family": family,
                "status": status,
                "answer_nonempty": answer_nonempty,
                "supporting_fact_id_present": any_ids,
                "unknown_fact_ids": unknown_ids,
                "claim": claimed,
                "failure_codes": row_failures,
            }
        )
        reasons.extend(row_failures)

    if len(answers) != len(c13.QUESTION_FAMILIES):
        observable = False
        reasons.append("QUESTION_COUNT_NOT_NINE")
    if seen != set(c13.QUESTION_FAMILIES):
        observable = False
        reasons.append("QUESTION_FAMILY_SET_INCOMPLETE")
    claim_count = sum(row.get("claim") is True for row in questions)
    return {
        "observable": observable,
        "claim_count": claim_count if observable else None,
        "observed_claim_count_before_hard_stop": claim_count,
        "question_total": len(questions),
        "failure_codes": sorted(set(reasons)),
        "questions": questions,
    }


def observe_raw_json_task_b_claims(
    raw_response: bytes | str,
    *,
    allowed_fact_ids: set[str],
) -> dict[str, Any]:
    """从逐字原始最终 JSON 观察 CLAIM；解析失败绝不按 0 声称处理。"""

    raw = (
        raw_response.decode("utf-8")
        if isinstance(raw_response, bytes)
        else raw_response
    )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "observable": False,
            "claim_count": None,
            "question_total": 0,
            "failure_codes": ["CLAIM_UNOBSERVABLE_NON_JSON"],
            "questions": [],
        }
    return observe_task_b_claims(
        payload,
        allowed_fact_ids=allowed_fact_ids,
    )


def observe_then_validate_task_b(
    payload: Any,
    *,
    expected_material_id: str,
    allowed_fact_ids: set[str],
) -> dict[str, Any]:
    """保留 CLAIM 账，再单独执行现役合同验收。"""

    claim = observe_task_b_claims(payload, allowed_fact_ids=allowed_fact_ids)
    try:
        if not isinstance(payload, Mapping):
            raise C13R04Error("任务 B 响应不是对象")
        c13.validate_task_b(
            payload,
            expected_material_id=expected_material_id,
            allowed_fact_ids=allowed_fact_ids,
        )
    except (c13.C13Error, C13R04Error) as exc:
        contract = {
            "accepted": False,
            "failure_code": "TASK_B_CONTRACT_REJECTED",
            "failure_detail": str(exc),
        }
    else:
        contract = {
            "accepted": True,
            "failure_code": None,
            "failure_detail": None,
        }
    return {"claim_ledger": claim, "contract_ledger": contract}


def _strict_sha256(value: str, *, label: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise C13R04Error(f"{label} 不是 64 位小写 SHA256")
    return value


def _resolve_recorded_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _write_exclusive(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError as exc:
        raise C13R04Error(f"审计工件已存在，禁止覆盖：{display_path(path)}") from exc


def _write_or_verify_exact(path: Path, raw: bytes) -> str:
    if path.exists():
        if path.read_bytes() != raw:
            raise C13R04Error(
                f"既有审计工件与重建字节不一致：{display_path(path)}"
            )
        return "REUSED_EXACT_BYTES"
    _write_exclusive(path, raw)
    return "CREATED"


def _resolve_frozen_task_b_binding(
    *,
    provider_id: str,
    call_id: str,
) -> dict[str, Any]:
    """只按供应商＋题位定位 r03 冻结 body，不接受调用方自报请求。"""

    if provider_id not in EXPECTED_PROVIDER_IDS:
        raise C13R04Error("响应使用了未知供应商身份")
    if not re.fullmatch(r"C13-N\d{2}", call_id):
        raise C13R04Error("call_id 不属于冻结 C13 题位")
    sources = _load_sources()
    prompt_evidence = _build_prompt_evidence(
        sources["prompt_bundle"],
        sources["call_plan"],
    )
    node = prompt_evidence["nodes"].get(call_id)
    parsed = prompt_evidence["parsed_rows"].get(call_id)
    if node is None or parsed is None or node.get("task") != "B":
        raise C13R04Error("该 call_id 不是冻结的任务 B 题位")
    matches = [
        row
        for row in sources["wire_plan"]["rows"]
        if row.get("provider_id") == provider_id
        and row.get("base_call_id") == call_id
    ]
    if len(matches) != 1:
        raise C13R04Error("r03 找不到唯一供应商＋题位绑定")
    wire_row = matches[0]
    expected_relative = f"wire/{provider_id}/{call_id}.json"
    if wire_row.get("body_path") != expected_relative:
        raise C13R04Error("r03 运输 body 路径不符合精确冻结身份")
    if expected_relative not in set(
        sources["r03_verification"]["manifest_paths"]
    ):
        raise C13R04Error("r03 运输 body 未被冻结清单收录")
    request_body_path = SOURCE_R03 / expected_relative
    request_body_sha256 = sha256_file(request_body_path)
    if request_body_sha256 != wire_row.get("body_sha256"):
        raise C13R04Error("r03 运输 body SHA 与顺序票不一致")
    body = read_json(request_body_path)
    if body.get("messages") != parsed["messages"]:
        raise C13R04Error("r03 运输 body 与 r02 冻结 messages 不一致")
    material = parsed["material"]
    profile_path = SOURCE_R03 / f"profiles/{provider_id}.json"
    if f"profiles/{provider_id}.json" not in set(
        sources["r03_verification"]["manifest_paths"]
    ):
        raise C13R04Error("供应商响应合同未被冻结清单收录")
    profile = read_json(profile_path)
    if profile.get("provider_id") != provider_id:
        raise C13R04Error("供应商响应合同身份漂移")
    response_contract = profile.get("response_contract")
    if not isinstance(response_contract, Mapping):
        raise C13R04Error("供应商响应合同缺失")
    allowed_fact_ids = {
        str(row["fact_id"])
        for row in material["facts"]
    }
    return {
        "request_body_path": request_body_path,
        "request_body_sha256": request_body_sha256,
        "expected_material_id": str(material["material_id"]),
        "allowed_fact_ids": allowed_fact_ids,
        "expected_model_id": str(profile["model_id"]),
        "response_contract": dict(response_contract),
        "response_profile_path": profile_path,
        "response_profile_sha256": sha256_file(profile_path),
    }


def _reasoning_observed(
    message: Mapping[str, Any],
    usage: Mapping[str, Any],
) -> bool:
    reasoning = message.get("reasoning_content")
    if "reasoning_content" in message and isinstance(reasoning, str):
        return True
    stack: list[Any] = [usage]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            for key, child in value.items():
                normalized = str(key).lower()
                if (
                    ("reasoning" in normalized or "thinking" in normalized)
                ):
                    return True
                stack.append(child)
        elif isinstance(value, list):
            stack.extend(value)
    return False


def _extract_provider_response_content(
    raw_response: bytes,
    *,
    expected_model_id: str,
    response_contract: Mapping[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []
    try:
        decoded = raw_response.decode("utf-8")
        envelope = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "accepted": False,
            "failure_codes": ["PROVIDER_RESPONSE_NOT_UTF8_JSON"],
            "failure_detail": str(exc),
            "content_bytes": None,
            "metadata": {
                "provider_response_id": None,
                "response_model_id": None,
                "finish_reason": None,
                "usage_sha256": None,
                "model_content_sha256": None,
            },
        }
    if not isinstance(envelope, Mapping):
        failures.append("PROVIDER_RESPONSE_NOT_OBJECT")
        envelope = {}
    choices = envelope.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        failures.append("PROVIDER_RESPONSE_CHOICE_TOTAL_NOT_ONE")
        choice: Mapping[str, Any] = {}
    elif not isinstance(choices[0], Mapping):
        failures.append("PROVIDER_RESPONSE_CHOICE_NOT_OBJECT")
        choice = {}
    else:
        choice = choices[0]
    finish_reason = choice.get("finish_reason")
    if finish_reason != response_contract.get("finish_reason_required"):
        failures.append("PROVIDER_RESPONSE_FINISH_REASON_NOT_STOP")
    message = choice.get("message")
    if not isinstance(message, Mapping):
        failures.append("PROVIDER_RESPONSE_MESSAGE_NOT_OBJECT")
        message = {}
    content = message.get("content")
    if not isinstance(content, str):
        failures.append("PROVIDER_RESPONSE_CONTENT_NOT_STRING")
        content_bytes = None
    else:
        content_bytes = content.encode("utf-8")
        try:
            content_payload = json.loads(content)
        except json.JSONDecodeError:
            failures.append("PROVIDER_RESPONSE_CONTENT_NOT_STRICT_JSON")
        else:
            if not isinstance(content_payload, Mapping):
                failures.append("PROVIDER_RESPONSE_CONTENT_NOT_JSON_OBJECT")
    model_id = envelope.get("model")
    if model_id != expected_model_id:
        failures.append("PROVIDER_RESPONSE_MODEL_IDENTITY_MISMATCH")
    usage = envelope.get("usage")
    if not isinstance(usage, Mapping) or not usage:
        failures.append("PROVIDER_RESPONSE_USAGE_MISSING")
        usage = {}
    response_id = envelope.get("id") or envelope.get("request_id")
    if not isinstance(response_id, str) or not response_id.strip():
        failures.append("PROVIDER_RESPONSE_REQUEST_ID_MISSING")
        response_id = None
    if not _reasoning_observed(message, usage):
        failures.append("PROVIDER_RESPONSE_REASONING_NOT_OBSERVED")
    metadata = {
        "provider_response_id": response_id,
        "response_model_id": model_id,
        "finish_reason": finish_reason,
        "usage_sha256": (
            sha256_bytes(canonical_bytes(usage)) if usage else None
        ),
        "model_content_sha256": (
            sha256_bytes(content_bytes)
            if content_bytes is not None
            else None
        ),
    }
    return {
        "accepted": not failures,
        "failure_codes": sorted(set(failures)),
        "failure_detail": None,
        "content_bytes": content_bytes,
        "metadata": metadata,
    }


def _evaluate_raw_task_b_against_frozen_binding(
    raw_response: bytes,
    *,
    expected_material_id: str,
    allowed_fact_ids: set[str],
    expected_model_id: str,
    response_contract: Mapping[str, Any],
) -> dict[str, Any]:
    transport = _extract_provider_response_content(
        raw_response,
        expected_model_id=expected_model_id,
        response_contract=response_contract,
    )
    content_bytes = transport["content_bytes"]
    if content_bytes is None:
        claim_observation = {
            "observable": False,
            "claim_count": None,
            "question_total": 0,
            "failure_codes": [
                "CLAIM_UNOBSERVABLE_MODEL_CONTENT_NOT_LOCATABLE"
            ],
            "questions": [],
        }
        task_validation = {
            "accepted": False,
            "failure_code": "TASK_B_NOT_REACHED_MODEL_CONTENT_NOT_LOCATABLE",
            "failure_detail": None,
        }
    else:
        claim_observation = observe_raw_json_task_b_claims(
            content_bytes,
            allowed_fact_ids=allowed_fact_ids,
        )
        try:
            payload = json.loads(content_bytes.decode("utf-8"))
        except json.JSONDecodeError as exc:
            task_validation = {
                "accepted": False,
                "failure_code": "TASK_B_CONTRACT_REJECTED_NON_JSON",
                "failure_detail": str(exc),
            }
        else:
            validated = observe_then_validate_task_b(
                payload,
                expected_material_id=expected_material_id,
                allowed_fact_ids=allowed_fact_ids,
            )
            task_validation = validated["contract_ledger"]
            if validated["claim_ledger"] != claim_observation:
                raise C13R04Error("原始字节观察账与解析对象观察账不一致")
    contract_validation = {
        "accepted": (
            transport["accepted"] is True
            and task_validation["accepted"] is True
        ),
        "provider_response": {
            key: value
            for key, value in transport.items()
            if key != "content_bytes"
        },
        "task_b": task_validation,
    }
    return {
        "claim_observation": claim_observation,
        "contract_validation": contract_validation,
        "audit_metadata": transport["metadata"],
    }


def verify_task_b_dual_ledgers(
    claim_ledger_path: Path,
    contract_ledger_path: Path,
) -> dict[str, Any]:
    """复验一条 CLAIM 账与合同账共享同一请求／响应身份。"""

    claim = read_json(claim_ledger_path)
    contract = read_json(contract_ledger_path)
    identity_fields = (
        "provider_id",
        "call_id",
        "attempt_no",
        "request_body_sha256",
        "raw_response_sha256",
    )
    claim_identity = {field: claim.get(field) for field in identity_fields}
    contract_identity = {
        field: contract.get(field) for field in identity_fields
    }
    if claim_identity != contract_identity:
        raise C13R04Error("CLAIM 账与合同账身份不一致")
    provider_id = claim_identity["provider_id"]
    if provider_id not in EXPECTED_PROVIDER_IDS:
        raise C13R04Error("双账使用了未知供应商身份")
    if (
        type(claim_identity["attempt_no"]) is not int
        or claim_identity["attempt_no"] < 1
    ):
        raise C13R04Error("双账 attempt_no 非法")
    _strict_sha256(
        str(claim_identity["request_body_sha256"]),
        label="request_body_sha256",
    )
    _strict_sha256(
        str(claim_identity["raw_response_sha256"]),
        label="raw_response_sha256",
    )
    frozen = _resolve_frozen_task_b_binding(
        provider_id=str(provider_id),
        call_id=str(claim_identity["call_id"]),
    )
    request_path = _resolve_recorded_path(str(claim["request_body_path"]))
    raw_path = _resolve_recorded_path(str(claim["raw_response_path"]))
    if contract.get("request_body_path") != claim.get("request_body_path"):
        raise C13R04Error("双账 request_body_path 不一致")
    if contract.get("raw_response_path") != claim.get("raw_response_path"):
        raise C13R04Error("双账 raw_response_path 不一致")
    for field in (
        "provider_response_id",
        "response_model_id",
        "finish_reason",
        "usage_sha256",
        "model_content_sha256",
        "response_profile_path",
        "response_profile_sha256",
    ):
        if contract.get(field) != claim.get(field):
            raise C13R04Error(f"双账 {field} 不一致")
    if request_path != frozen["request_body_path"]:
        raise C13R04Error("双账没有绑定到 r03 精确冻结请求")
    if claim_identity["request_body_sha256"] != frozen["request_body_sha256"]:
        raise C13R04Error("双账请求 SHA 不是 r03 精确冻结值")
    if sha256_file(request_path) != claim_identity["request_body_sha256"]:
        raise C13R04Error("双账绑定的请求实物 SHA 漂移")
    if sha256_file(raw_path) != claim_identity["raw_response_sha256"]:
        raise C13R04Error("双账绑定的原始响应 SHA 漂移")
    observation = claim.get("observation")
    validation = contract.get("validation")
    if not isinstance(observation, Mapping):
        raise C13R04Error("CLAIM 账缺 observation")
    if not isinstance(validation, Mapping):
        raise C13R04Error("合同账缺 validation")
    if type(validation.get("accepted")) is not bool:
        raise C13R04Error("合同账 accepted 不是布尔值")
    replay = _evaluate_raw_task_b_against_frozen_binding(
        raw_path.read_bytes(),
        expected_material_id=frozen["expected_material_id"],
        allowed_fact_ids=frozen["allowed_fact_ids"],
        expected_model_id=frozen["expected_model_id"],
        response_contract=frozen["response_contract"],
    )
    expected_metadata = {
        **replay["audit_metadata"],
        "response_profile_path": display_path(
            frozen["response_profile_path"]
        ),
        "response_profile_sha256": frozen["response_profile_sha256"],
    }
    for field, expected_value in expected_metadata.items():
        if claim.get(field) != expected_value:
            raise C13R04Error(f"双账 {field} 无法从原始响应重算")
    if replay["claim_observation"] != observation:
        raise C13R04Error("CLAIM 账无法从原始响应逐字重算")
    if replay["contract_validation"] != validation:
        raise C13R04Error("合同账无法从原始响应逐字重算")
    return {
        **claim_identity,
        "observable": observation.get("observable"),
        "claim_count": observation.get("claim_count"),
        "contract_accepted": validation["accepted"],
        "claim_ledger_path": display_path(claim_ledger_path),
        "contract_ledger_path": display_path(contract_ledger_path),
        "raw_response_path": display_path(raw_path),
        "request_body_path": display_path(request_path),
    }


def persist_observe_and_validate_task_b(
    raw_response: bytes,
    *,
    ledger_root: Path,
    provider_id: str,
    call_id: str,
    attempt_no: int,
) -> dict[str, Any]:
    """先封原始响应，再写分离的 CLAIM 账和合同账。"""

    if not isinstance(raw_response, bytes):
        raise C13R04Error("原始响应必须以 bytes 传入，禁止先清洗再落盘")
    if type(attempt_no) is not int or attempt_no < 1:
        raise C13R04Error("attempt_no 必须是正整数")
    frozen = _resolve_frozen_task_b_binding(
        provider_id=provider_id,
        call_id=call_id,
    )
    request_body_path = frozen["request_body_path"]
    expected_request_body_sha256 = frozen["request_body_sha256"]

    stem = f"attempt_{attempt_no:02d}"
    raw_path = (
        ledger_root
        / "raw_responses"
        / provider_id
        / call_id
        / f"{stem}.raw"
    )
    claim_path = (
        ledger_root
        / "ledgers/claim"
        / provider_id
        / call_id
        / f"{stem}.json"
    )
    contract_path = (
        ledger_root
        / "ledgers/contract"
        / provider_id
        / call_id
        / f"{stem}.json"
    )
    if not raw_path.exists() and (claim_path.exists() or contract_path.exists()):
        raise C13R04Error("双账先于原始响应出现，禁止补造原始包")
    raw_write_status = _write_or_verify_exact(raw_path, raw_response)
    raw_response_sha256 = sha256_file(raw_path)
    identity = {
        "provider_id": provider_id,
        "call_id": call_id,
        "attempt_no": attempt_no,
        "request_body_sha256": expected_request_body_sha256,
        "raw_response_sha256": raw_response_sha256,
    }
    evaluated = _evaluate_raw_task_b_against_frozen_binding(
        raw_response,
        expected_material_id=frozen["expected_material_id"],
        allowed_fact_ids=frozen["allowed_fact_ids"],
        expected_model_id=frozen["expected_model_id"],
        response_contract=frozen["response_contract"],
    )
    claim_observation = evaluated["claim_observation"]
    contract_validation = evaluated["contract_validation"]

    common_paths = {
        "request_body_path": display_path(request_body_path),
        "raw_response_path": display_path(raw_path),
        **evaluated["audit_metadata"],
        "response_profile_path": display_path(
            frozen["response_profile_path"]
        ),
        "response_profile_sha256": frozen["response_profile_sha256"],
    }
    claim_ledger = {
        "schema_version": "v02-c13-task-b-claim-ledger.v2",
        **identity,
        **common_paths,
        "statistics_stage": "BEFORE_CONTRACT_VALIDATION",
        "observation": claim_observation,
    }
    contract_ledger = {
        "schema_version": "v02-c13-task-b-contract-ledger.v2",
        **identity,
        **common_paths,
        "validation": contract_validation,
    }
    claim_write_status = _write_or_verify_exact(
        claim_path,
        canonical_bytes(claim_ledger),
    )
    contract_write_status = _write_or_verify_exact(
        contract_path,
        canonical_bytes(contract_ledger),
    )
    verified = verify_task_b_dual_ledgers(claim_path, contract_path)
    return {
        **verified,
        "write_status": {
            "raw_response": raw_write_status,
            "claim_ledger": claim_write_status,
            "contract_ledger": contract_write_status,
        },
    }


def _evaluate_provider_claim_floor_from_verified_rows(
    observations: Sequence[Mapping[str, Any]],
    *,
    provider_id: str,
) -> dict[str, Any]:
    """只对已经逐对复验的行做 54/18/18 纯算术聚合。"""

    if provider_id not in EXPECTED_PROVIDER_IDS:
        raise C13R04Error("地板判定使用了未知供应商身份")
    if any(row.get("provider_id") != provider_id for row in observations):
        raise C13R04Error("一家供应商的地板账混入了其他供应商")
    call_plan_nodes = _load_sources()["call_plan"]["nodes"]
    b_nodes = [row for row in call_plan_nodes if row.get("task") == "B"]
    expected = {str(row["call_id"]): row for row in b_nodes}
    observed_ids = Counter(row.get("call_id") for row in observations)
    expected_ids = Counter({call_id: 1 for call_id in expected})
    if observed_ids != expected_ids:
        raise C13R04Error("一家供应商的任务 B 观察行缺失、重复或越界")
    by_call = {str(row["call_id"]): row for row in observations}
    unobservable = [
        call_id
        for call_id, row in by_call.items()
        if row.get("observable") is not True
        or type(row.get("claim_count")) is not int
        or type(row.get("contract_accepted")) is not bool
    ]
    if unobservable:
        return {
            "status": "HARD_STOP_CLAIM_UNOBSERVABLE",
            "claim_observation_complete": False,
            "unobservable_call_ids": sorted(unobservable),
            "formal_claim_count": None,
            "shuffle_claim_count": None,
            "blank_claim_count": None,
            "denominators": dict(EXPECTED_DENOMINATORS),
            "quality_verdict": "NOT_REACHED",
        }
    if any(
        row["claim_count"] < 0 or row["claim_count"] > 9
        for row in by_call.values()
    ):
        raise C13R04Error("单个任务 B 的 claim_count 超出 0..9")

    formal_nodes = [row for row in b_nodes if row.get("floor_kind") is None]
    shuffle_nodes = [
        row
        for row in b_nodes
        if row.get("floor_kind") == "SHUFFLED_FACT_ORDER"
    ]
    blank_nodes = [
        row
        for row in b_nodes
        if row.get("floor_kind") == "CHAPTER_NUMBER_ONLY"
    ]
    if (len(formal_nodes), len(shuffle_nodes), len(blank_nodes)) != (6, 2, 2):
        raise C13R04Error("任务 B 调用结构不是每家 6/2/2")

    f = sum(by_call[str(row["call_id"])]["claim_count"] for row in formal_nodes)
    s = sum(by_call[str(row["call_id"])]["claim_count"] for row in shuffle_nodes)
    b = sum(by_call[str(row["call_id"])]["claim_count"] for row in blank_nodes)
    if (f > 54) or (s > 18) or (b > 18):
        raise C13R04Error("CLAIM 聚合超过冻结分母")

    formal_by_base = {
        str(row["base_material_id"]): by_call[str(row["call_id"])]["claim_count"]
        for row in formal_nodes
    }
    pair_rows: list[dict[str, Any]] = []
    for row in shuffle_nodes:
        base_material_id = str(row["base_material_id"])
        if base_material_id not in formal_by_base:
            raise C13R04Error("乱序位找不到同材料正式任务 B")
        formal_count = formal_by_base[base_material_id]
        shuffle_count = by_call[str(row["call_id"])]["claim_count"]
        delta_count = shuffle_count - formal_count
        pair_rows.append(
            {
                "base_material_id": base_material_id,
                "formal_claim_count": formal_count,
                "shuffle_claim_count": shuffle_count,
                "question_denominator": 9,
                "shuffle_minus_formal_count": delta_count,
                "shuffle_minus_formal_pp": delta_count / 9 * 100,
                "hard_stop": delta_count >= 1,
            }
        )
    shuffle_hard_stop = any(row["hard_stop"] for row in pair_rows)

    blank_hard_stop = b >= 5
    high_formal = f >= 22
    b1_pass = (f - 3 * b) >= 14 if high_formal else None
    b2_pass = f >= 9 * b if not high_formal else None
    invalid_reasons: list[str] = []
    if blank_hard_stop:
        invalid_reasons.append("CLAIM_BLANK_AT_LEAST_25_PERCENT")
    if high_formal and b1_pass is False:
        invalid_reasons.append("HIGH_FORMAL_BLANK_GAP_BELOW_25PP")
    if not high_formal and b2_pass is False:
        invalid_reasons.append("LOW_FORMAL_BLANK_EXCEEDS_ONE_THIRD")
    if shuffle_hard_stop:
        floor_claim_status = "HARD_STOP_SHUFFLE_REVERSE_ADVANTAGE"
    elif invalid_reasons:
        floor_claim_status = "INVALID_PROVIDER_FLOOR_CLAIM"
    elif high_formal:
        floor_claim_status = "VALID_FLOOR_SCREEN_NOT_QUALITY_VERDICT"
    else:
        floor_claim_status = "VALID_RUN_MATERIAL_INSUFFICIENT_NOT_MODEL_USABLE"

    contract_rejection_total = sum(
        row.get("contract_accepted") is False for row in by_call.values()
    )
    if floor_claim_status.startswith(("HARD_STOP", "INVALID")):
        status = floor_claim_status
    elif contract_rejection_total:
        status = "NOT_ACCEPTABLE_CONTRACT_REJECTIONS_PRESENT"
    else:
        status = floor_claim_status
    return {
        "status": status,
        "floor_claim_status": floor_claim_status,
        "claim_observation_complete": True,
        "denominators": dict(EXPECTED_DENOMINATORS),
        "formal_claim_count": f,
        "formal_claim_rate": f / 54,
        "shuffle_claim_count": s,
        "shuffle_claim_rate": s / 18,
        "blank_claim_count": b,
        "blank_claim_rate": b / 18,
        "high_formal_branch": high_formal,
        "blank_absolute_gate_pass": not blank_hard_stop,
        "b1_high_formal_gap_pass": b1_pass,
        "b2_low_formal_ratio_pass": b2_pass,
        "invalid_reasons": invalid_reasons,
        "shuffle_pairs": pair_rows,
        "shuffle_hard_stop": shuffle_hard_stop,
        "contract_rejection_total": contract_rejection_total,
        "provider_contract_status": (
            "PASS_ALL_TASK_B_RESPONSES"
            if contract_rejection_total == 0
            else "REJECTED_TASK_B_RESPONSES_PRESENT"
        ),
        "contract_rejections_do_not_remove_claims_or_denominator": True,
        "quality_verdict": "NOT_A_QUALITY_VERDICT",
    }


def _ledger_root_from_pair_path(
    ledger_path: Path,
    *,
    ledger_kind: str,
    provider_id: str,
    call_id: str,
    attempt_no: int,
) -> Path:
    """核对账本位于同一运行根的固定目录，不接受任意散装路径。"""

    resolved = ledger_path.resolve()
    if len(resolved.parents) < 5:
        raise C13R04Error("双账路径层级不足，无法识别运行根")
    ledger_root = resolved.parents[4]
    expected = (
        ledger_root
        / "ledgers"
        / ledger_kind
        / provider_id
        / call_id
        / f"attempt_{attempt_no:02d}.json"
    )
    if resolved != expected:
        raise C13R04Error("双账路径不符合冻结目录结构")
    return ledger_root


def evaluate_provider_claim_floor(
    ledger_pairs: Sequence[Mapping[str, Any]],
    *,
    provider_id: str,
) -> dict[str, Any]:
    """从一家供应商的 10 对双账强制重放后，再算 CLAIM 地板。

    对外入口不接收手填观察行。每个冻结任务 B 题位只允许一对双账；
    同一运行根出现额外／残缺尝试即硬停，禁止挑选某次结果。
    """

    if provider_id not in EXPECTED_PROVIDER_IDS:
        raise C13R04Error("地板判定使用了未知供应商身份")
    if not isinstance(ledger_pairs, Sequence) or isinstance(
        ledger_pairs, (str, bytes)
    ):
        raise C13R04Error("地板判定必须传入 10 对 CLAIM／合同账路径")

    required_pair_keys = {"claim_ledger_path", "contract_ledger_path"}
    verified_rows: list[dict[str, Any]] = []
    ledger_roots: set[Path] = set()
    supplied_claim_paths: set[Path] = set()
    supplied_contract_paths: set[Path] = set()
    supplied_raw_paths: set[Path] = set()
    for pair in ledger_pairs:
        if not isinstance(pair, Mapping) or set(pair) != required_pair_keys:
            raise C13R04Error(
                "每个地板输入只能含 claim_ledger_path 与 "
                "contract_ledger_path"
            )
        claim_path = Path(str(pair["claim_ledger_path"])).resolve()
        contract_path = Path(str(pair["contract_ledger_path"])).resolve()
        verified = verify_task_b_dual_ledgers(claim_path, contract_path)
        if verified["provider_id"] != provider_id:
            raise C13R04Error("一家供应商的地板账混入了其他供应商")
        attempt_no = verified["attempt_no"]
        call_id = str(verified["call_id"])
        claim_root = _ledger_root_from_pair_path(
            claim_path,
            ledger_kind="claim",
            provider_id=provider_id,
            call_id=call_id,
            attempt_no=attempt_no,
        )
        contract_root = _ledger_root_from_pair_path(
            contract_path,
            ledger_kind="contract",
            provider_id=provider_id,
            call_id=call_id,
            attempt_no=attempt_no,
        )
        if claim_root != contract_root:
            raise C13R04Error("CLAIM 账与合同账不在同一运行根")
        raw_path = Path(str(verified["raw_response_path"])).resolve()
        expected_raw_path = (
            claim_root
            / "raw_responses"
            / provider_id
            / call_id
            / f"attempt_{attempt_no:02d}.raw"
        )
        if raw_path != expected_raw_path:
            raise C13R04Error("原始响应不在双账运行根的固定目录")
        ledger_roots.add(claim_root)
        supplied_claim_paths.add(claim_path)
        supplied_contract_paths.add(contract_path)
        supplied_raw_paths.add(raw_path)
        verified_rows.append(verified)

    if len(ledger_roots) != 1:
        raise C13R04Error("一家供应商的 10 对双账必须来自同一运行根")
    ledger_root = next(iter(ledger_roots))
    actual_claim_paths = {
        path.resolve()
        for path in (
            ledger_root / "ledgers" / "claim" / provider_id
        ).glob("*/attempt_*.json")
    }
    actual_contract_paths = {
        path.resolve()
        for path in (
            ledger_root / "ledgers" / "contract" / provider_id
        ).glob("*/attempt_*.json")
    }
    actual_raw_paths = {
        path.resolve()
        for path in (
            ledger_root / "raw_responses" / provider_id
        ).glob("*/attempt_*.raw")
    }
    if (
        actual_claim_paths != supplied_claim_paths
        or actual_contract_paths != supplied_contract_paths
        or actual_raw_paths != supplied_raw_paths
    ):
        raise C13R04Error(
            "运行根存在未纳入汇总的额外／残缺尝试，禁止挑选结果"
        )

    result = _evaluate_provider_claim_floor_from_verified_rows(
        verified_rows,
        provider_id=provider_id,
    )
    result["evidence_gate"] = {
        "dual_ledger_pair_total": len(verified_rows),
        "ledger_root": display_path(ledger_root),
        "all_pairs_replayed_from_raw_provider_envelopes": True,
        "attempt_selection_rule": (
            "EXACTLY_ONE_COMPLETE_DUAL_LEDGER_PAIR_PER_FROZEN_CALL;"
            "ANY_EXTRA_OR_PARTIAL_ATTEMPT_HARD_STOPS"
        ),
        "attempts": [
            {
                "call_id": row["call_id"],
                "attempt_no": row["attempt_no"],
                "raw_response_sha256": row["raw_response_sha256"],
            }
            for row in sorted(
                verified_rows,
                key=lambda item: str(item["call_id"]),
            )
        ],
    }
    return result


def _markdown_table(rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "| call_id | 任务 | 题型 | 累计章数 | 事实句条数 | 材料 SHA |",
        "|---|---:|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {call_id} | {task} | {prompt_kind} | "
            "{cumulative_chapter_count} | {fact_sentence_total} | "
            "`{material_sha256}` |".format(**row)
        )
    return "\n".join(lines)


def _build_plaintext_review(
    prompt_evidence: Mapping[str, Any],
) -> str:
    rows = prompt_evidence["parsed_rows"]
    labels = {
        "C13-N01": "正式位代表｜任务 A",
        "C13-N14": "乱序位代表｜任务 C",
        "C13-N05": "章号空白位代表｜任务 B",
    }
    parts = [
        "# C13 r04｜可直接回贴 Notion 的三份逐字题面",
        "",
        "这三份直接来自 r02 冻结实物，不是聊天重抄。它们同时覆盖正式／乱序／章号空白三种材料形态与 A／B／C 三种任务。",
        "",
    ]
    for call_id in SAMPLE_CALL_IDS:
        row = rows[call_id]
        parts.extend(
            [
                f"## {labels[call_id]}｜`{call_id}`",
                "",
                f"- `messages_sha256`：`{row['messages_sha256']}`",
                "",
                "```json",
                json.dumps(row["messages"], ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    parts.extend(
        [
            "## 30 位唯一差异字段表",
            "",
            _markdown_table(prompt_evidence["table_rows"]),
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(parts)


def _floor_contract(program_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "v02-c13-floor-claim-gate.v2",
        "status": "FROZEN_ZERO_RESPONSE_NOT_EXECUTABLE",
        "authority_page": AUTHORITY_PAGE,
        "authority_decision_at": AUTHORITY_DECISION_AT,
        "program_path": display_path(Path(__file__)),
        "program_sha256": program_sha256,
        "statistics_stage": "BEFORE_CONTRACT_VALIDATION",
        "raw_response_definition": (
            "FULL_PROVIDER_RESPONSE_ENVELOPE_BYTES_NOT_EXTRACTED_CONTENT"
        ),
        "raw_response_must_be_persisted_before_claim_observation": True,
        "raw_response_persistence_order": [
            "persist_raw_response_bytes",
            "record_raw_response_sha256",
            "observe_pre_contract_claim",
            "run_contract_validation",
            "append_claim_and_contract_ledgers",
        ],
        "runtime_ledger_identity_exact_fields": [
            "provider_id",
            "call_id",
            "attempt_no",
            "request_body_sha256",
            "raw_response_sha256",
        ],
        "runtime_ledger_identity_fields_must_match_between_ledgers": True,
        "executable_pipeline_functions": {
            "persist_observe_validate": (
                "persist_observe_and_validate_task_b"
            ),
            "provider_response_extractor": (
                "_extract_provider_response_content"
            ),
            "dual_ledger_verifier": "verify_task_b_dual_ledgers",
            "provider_floor_evaluator": "evaluate_provider_claim_floor",
        },
        "claim_and_contract_ledgers_are_separate": True,
        "public_evaluator_input": (
            "TEN_CLAIM_AND_CONTRACT_LEDGER_PATH_PAIRS_ONLY"
        ),
        "public_evaluator_must_replay_every_pair_from_raw_response": True,
        "attempt_selection_rule": (
            "EXACTLY_ONE_COMPLETE_DUAL_LEDGER_PAIR_PER_FROZEN_CALL;"
            "ANY_EXTRA_OR_PARTIAL_ATTEMPT_HARD_STOPS"
        ),
        "handwritten_observation_rows_are_forbidden": True,
        "evaluation_scope": {
            "one_provider_per_evaluation": True,
            "every_observation_provider_id_must_equal_requested_provider": True,
            "cross_provider_pooling": False,
        },
        "contract_rejection_may_remove_claim_or_denominator": False,
        "provider_contract_rejection_claim_policy": (
            "OBSERVE_CLAIM_WHEN_MODEL_CONTENT_BYTES_ARE_LOCATABLE;"
            "ONLY_UNLOCATABLE_CONTENT_IS_UNOBSERVABLE"
        ),
        "claim_definition_any_of": [
            "status_strictly_equals_ANSWERED",
            "answer_field_is_nonempty",
            "supporting_fact_ids_contains_id_not_allowed_by_this_prompt",
        ],
        "unobservable_response_policy": (
            "HARD_STOP_NEVER_COUNT_AS_ZERO_CLAIM"
        ),
        "per_provider_denominators": dict(EXPECTED_DENOMINATORS),
        "thresholds": {
            "blank_absolute_invalid": {
                "formula": "blank_claim_count >= 5",
                "rate": ">=25%",
            },
            "high_formal_branch": {
                "formula": "formal_claim_count >= 22",
                "rate": ">=40%",
            },
            "high_formal_gap_pass": {
                "formula": "formal_claim_count - 3*blank_claim_count >= 14",
                "rate": "formal/54 - blank/18 >=25pp",
            },
            "low_formal_ratio_pass": {
                "formula": "formal_claim_count >= 9*blank_claim_count",
                "rate": "blank/18 <= (formal/54)/3",
            },
        },
        "shuffle_pairing": {
            "identity": "provider_id + base_material_id + task_B",
            "per_pair_question_denominator": 9,
            "report_each_pair": True,
            "hard_stop_formula": (
                "shuffle_claim_count - formal_claim_count >= 1"
            ),
            "meaning": "same_material_shuffle_minus_formal >10pp",
            "global_formal_minus_shuffle_is_forbidden": True,
        },
        "low_formal_protection_result": (
            "VALID_RUN_MATERIAL_INSUFFICIENT_NOT_MODEL_USABLE"
        ),
        "post_validation_r_blank_may_be_used_as_floor_evidence": False,
        "provider_results_may_be_averaged_weighted_or_cross_rescued": False,
        "prompt_or_provider_result_unsealed_total": 0,
        "model_api_calls": 0,
        "network_requests": 0,
        "execute_allowed": False,
        "git_commit_required_before_any_response_unseal": True,
        "git_commit_recorded": False,
    }


def build_artifacts() -> dict[str, bytes]:
    sources = _load_sources()
    prompt_evidence = _build_prompt_evidence(
        sources["prompt_bundle"],
        sources["call_plan"],
    )
    wire_evidence = _build_wire_evidence(
        prompt_evidence,
        sources["wire_plan"],
        set(sources["r03_verification"]["manifest_paths"]),
    )
    program_sha256 = sha256_file(Path(__file__))

    allowed_difference_contract = {
        "schema_version": "v02-c13-allowed-prompt-differences.v1",
        "status": "FROZEN_ALLOWLIST_ONLY",
        "authority_source_program_path": display_path(Path(c13.__file__)),
        "authority_source_program_sha256": EXPECTED_C13_PROGRAM_SHA256,
        "prompt_set_sha256": EXPECTED_PROMPT_SET_SHA256,
        "message_shape": [
            {"role": "system", "content": "GLOBAL_FROZEN_TEMPLATE"},
            {"role": "user", "content": "JSON_OBJECT"},
        ],
        "user_top_level_exact_keys": sorted(EXPECTED_USER_TOP_KEYS),
        "material_exact_keys": sorted(EXPECTED_MATERIAL_KEYS),
        "four_view_exact_keys": sorted(EXPECTED_VIEW_KEYS),
        "allowed_variable_paths": list(ALLOWED_USER_VARIATION_PATHS),
        "task_template_choice": {
            "allowed_tasks": ["A", "B", "C"],
            "task_instruction_and_output_contract_must_equal_frozen_template": True,
            "template_sha256": prompt_evidence["task_template_hashes"],
        },
        "material_derivation_rules": {
            "FORMAL": "exact_frozen_material",
            "SHUFFLED_FACT_ORDER": "same_fact_multiset_order_only",
            "CHAPTER_NUMBER_ONLY": "facts_and_timeline_empty",
        },
        "constant_fields": {
            "material.schema_version": "chapter-fact-material.v1",
            "material.coverage_scope": "SINGLE_CHAPTER_ONLY",
            "material.cumulative_chapter_count": 1,
            "material.four_views.timeline.status": "PROVIDED_MECHANICAL",
            "material.four_views.causal_edges": {
                "status": "NOT_PROVIDED",
                "items": [],
            },
            "material.four_views.character_states": {
                "status": "NOT_PROVIDED",
                "items": [],
            },
            "material.four_views.unresolved_items": {
                "status": "NOT_PROVIDED",
                "items": [],
            },
        },
        "unknown_key_or_outside_path_change_policy": "REJECT_WHOLE_BATCH",
    }
    allowed_difference_receipt = {
        "schema_version": "v02-c13-allowed-difference-receipt.v1",
        "status": "PASS_ZERO_OUTSIDE_ALLOWLIST",
        "validation_basis": [
            "PINNED_C13_PROGRAM_CONSTANTS",
            "EXACT_JSON_KEY_SETS",
            "EXACT_TASK_TEMPLATE_EQUALITY",
            "FORMAL_EXACT_FROZEN_MATERIAL",
            "SHUFFLE_SAME_MULTISET_AND_ORDER_CHANGED",
            "CHAPTER_ONLY_EMPTY_FACTS_AND_TIMELINE",
            "NORMALIZED_FULL_TEMPLATE_EQUALITY",
        ],
        "authority_source_program_sha256": EXPECTED_C13_PROGRAM_SHA256,
        "prompt_slot_total": 30,
        "system_prompt_variant_total": 1,
        "system_prompt_sha256": prompt_evidence["system_prompt_sha256"],
        "task_instruction_variant_per_task": {"A": 1, "B": 1, "C": 1},
        "output_contract_variant_per_task": {"A": 1, "B": 1, "C": 1},
        "normalized_template_variant_total": 1,
        "normalized_template_sha256": prompt_evidence[
            "normalized_template_sha256"
        ],
        "unexpected_variable_path_total": 0,
        "rows": prompt_evidence["table_rows"],
        "model_api_calls": 0,
        "network_requests": 0,
    }
    blacklist_receipt = {
        "schema_version": "v02-c13-wire-message-blacklist-scan.v1",
        "status": "PASS_DECLARED_RULES_ZERO_HITS",
        "unique_prompt_total": 30,
        "provider_total": 3,
        "wire_message_copy_total": 90,
        "semantic_independent_sample_total": 30,
        "rule_total": len(MESSAGE_BLACKLIST_RULES),
        "rules": list(MESSAGE_BLACKLIST_RULES),
        "message_blacklist_hit_total": 0,
        "wire_security_hit_total": 0,
        "rows": wire_evidence["scan_rows"],
        "prior_leak_risk_names": True,
        "prior_leak_risk_names_detector_present": False,
        "scope_limit": (
            "PROVES_ONLY_DECLARED_BLACKLIST_ZERO_HITS;"
            "DOES_NOT_CLAIM_ALLOWED_CHARACTER_OR_SETTING_NAMES_ARE_ABSENT"
        ),
        "unicode_normalization_before_scan": "NFKC",
        "chapter_only_floor_scope": (
            "EMPTY_MATERIAL_HALLUCINATION_AND_CROSS_REQUEST_CONTAMINATION_ONLY"
        ),
        "model_api_calls": 0,
        "network_requests": 0,
    }
    binding_receipt = {
        "schema_version": "v02-c13-source-to-wire-binding.v1",
        "status": "PASS_30_BY_3_CARTESIAN_PRODUCT",
        "source_prompt_set_sha256": EXPECTED_PROMPT_SET_SHA256,
        "source_prompt_total": 30,
        "provider_total": 3,
        "binding_total": 90,
        "binding_pass_total": 90,
        "messages_mismatch_total": 0,
        "field_set_mismatch_total": 0,
        "manifest_missing_total": 0,
        "rows": wire_evidence["binding_rows"],
    }
    floor_contract = _floor_contract(program_sha256)
    floor_freeze_receipt = {
        "schema_version": "v02-c13-floor-claim-freeze-receipt.v2",
        "status": "PASS_ZERO_RESPONSE_FROZEN_NOT_EXECUTABLE",
        "authority_page": AUTHORITY_PAGE,
        "authority_decision_at": AUTHORITY_DECISION_AT,
        "program_path": display_path(Path(__file__)),
        "program_sha256": program_sha256,
        "per_provider_denominators": dict(EXPECTED_DENOMINATORS),
        "prompt_or_provider_result_unsealed_total": 0,
        "response_file_total": 0,
        "model_api_calls": 0,
        "network_requests": 0,
        "key_value_read": False,
        "execute_allowed": False,
        "remaining_blockers": [
            "NOTION_APPROVED_TO_SEND_PENDING_A_B_C_AND_FLOOR_V2_REVIEW",
            "FLOOR_V2_GIT_COMMIT_TIMESTAMP_PENDING",
            "THREE_PROVIDER_KEY_PRESENCE_RECHECK_PENDING",
            "REQUIRED_LIVE_CATALOG_GATE_PENDING",
        ],
    }
    source_receipt = {
        "schema_version": "v02-c13-r04-source-verification.v1",
        "status": "PASS_SOURCE_TREES_UNCHANGED",
        "r02": sources["r02_verification"],
        "r03": sources["r03_verification"],
        "r02_program_sha256": EXPECTED_C13_PROGRAM_SHA256,
        "source_prompt_set_sha256": EXPECTED_PROMPT_SET_SHA256,
        "old_source_rewritten": False,
    }

    artifacts: dict[str, bytes] = {
        "contracts/allowed_difference_contract.json": canonical_bytes(
            allowed_difference_contract
        ),
        "contracts/floor_claim_v2_contract.json": canonical_bytes(
            floor_contract
        ),
        "preflight/floor_gate_v2_freeze_receipt.json": canonical_bytes(
            floor_freeze_receipt
        ),
        "preflight/source_verification_receipt.json": canonical_bytes(
            source_receipt
        ),
        "signoff/A_prompt_text_samples.md": _build_plaintext_review(
            prompt_evidence
        ).encode("utf-8"),
        "signoff/A_prompt_slot_diff_table.json": canonical_bytes(
            {
                "schema_version": "v02-c13-prompt-slot-diff-table.v1",
                "status": "PASS_30_SLOTS",
                "rows": prompt_evidence["table_rows"],
            }
        ),
        "signoff/A_prompt_slot_diff_table.md": (
            "# C13 r04｜30 位唯一差异字段表\n\n"
            + _markdown_table(prompt_evidence["table_rows"])
            + "\n\n来源：Codex\n"
        ).encode("utf-8"),
        "signoff/B_messages_blacklist_scan_receipt.json": canonical_bytes(
            blacklist_receipt
        ),
        "signoff/C_allowed_difference_receipt.json": canonical_bytes(
            allowed_difference_receipt
        ),
        "signoff/C_source_to_wire_binding_receipt.json": canonical_bytes(
            binding_receipt
        ),
    }
    readme = f"""# C13 r04｜签票证明＋地板判定器 v2

✅ A／B／C 三件签票证明已从冻结实物机械生成：

- 三份正文题面覆盖正式 A、乱序 C、章号空白 B；
- 30 位允许差异规范化后只有 1 个模板；
- 30 份唯一题面复制到三家形成 90 份运输件，逐位 `messages` SHA 全同；
- 90 份 `messages` 对施工令点名的黑名单规则命中 0，运输外壳密钥／
  授权形态命中 0。人物与设定专名按已拍口径允许保留，本票不冒充
  它们不存在。

✅ 地板判定器已改成先逐字封存供应商完整响应包，再按 r03 冻结响应
合同提取模型正文，分别写 CLAIM 账与合同账；复验时会从原包重新提取、
重新计数并逐字段对账。每家分母固定为正式 54／乱序 18／章号空白 18；
合同拒收不会删掉 CLAIM 或缩小分母，但会让整轮状态明确标成不可接收。
公开汇总只接受同一运行根的 10 对双账路径，不接受手填读数；每对都从
完整原包重放，同题位出现额外或残缺尝试即硬停，禁止挑选某一次结果。
模型正文不是合法 JSON 时仍会留下可重放的拒收双账，不会停在半成品。
章号空白只测空材料脑补和串请求污染，不再冒充人物专名先验探测器。

⚠️ 当前仍是 0 模型请求、0 网络、0 密钥读取，且
`execute_allowed=false`。Notion 重新签 `APPROVED_TO_SEND`、地板 v2
复核、Git 冻结提交、三把密钥存在性与实时目录闸没有全部通过前，
不得拆封结果或发第一条请求。

程序 SHA：`{program_sha256}`

来源：Codex
"""
    artifacts["README.md"] = readme.encode("utf-8")
    preimage = {
        path: sha256_bytes(raw)
        for path, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c13-r04-artifact-manifest.v1",
            "status": "PASS_ZERO_CALL_SIGNOFF_AND_FLOOR_V2_NOT_EXECUTABLE",
            "files": [
                {"path": path, "sha256": digest}
                for path, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "source_r02_manifest_sha256": EXPECTED_R02_MANIFEST_SHA256,
            "source_r03_manifest_sha256": EXPECTED_R03_MANIFEST_SHA256,
            "source_prompt_set_sha256": EXPECTED_PROMPT_SET_SHA256,
            "prompt_slot_total": 30,
            "wire_message_copy_total": 90,
            "message_blacklist_hit_total": 0,
            "unexpected_variable_path_total": 0,
            "model_api_calls": 0,
            "network_requests": 0,
            "key_value_read": False,
            "execute_allowed": False,
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
        raise C13R04Error("r04 连续两次构造字节不一致")
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
        raise C13R04Error(
            "r04 输出集合不闭合："
            f"missing={sorted(set(first) - actual)} "
            f"unexpected={sorted(actual - set(first))}"
        )
    for relative, raw in first.items():
        if (output_dir / relative).read_bytes() != raw:
            raise C13R04Error(f"r04 工件字节漂移：{relative}")

    report_path = report_dir / "C13_r04签票证明与地板判定器停点回包.md"
    if write:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(first["README.md"])
    if report_path.read_bytes() != first["README.md"]:
        raise C13R04Error("r04 reports 镜像与 README 不一致")
    manifest = json.loads(first["artifact_manifest.json"])
    return {
        "status": manifest["status"],
        "artifact_set_sha256": manifest["artifact_set_sha256"],
        "prompt_slot_total": manifest["prompt_slot_total"],
        "wire_message_copy_total": manifest["wire_message_copy_total"],
        "model_api_calls": 0,
        "network_requests": 0,
        "key_value_read": False,
        "execute_allowed": False,
        "output_dir": display_path(output_dir),
        "report_path": display_path(report_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="V02 C13 r04 签票证明与 CLAIM 地板判定器 v2"
    )
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

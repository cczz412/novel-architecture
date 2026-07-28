#!/usr/bin/env python3
"""R1 路线对比：冻结三条 Flash 路线、30 格评测真源并执行离线计分。

这个文件只负责生成冻结工件和离线计分，不读取密钥、不发网络请求。
正式发送由同目录的 ``v02_r1_route_runner.py`` 承担。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RUN_DIR = REPO_ROOT / "runs" / "V02_R1_route_comparison_r02_20260726"
C15_RUN_DIR = REPO_ROOT / "runs" / "V02_C15_pipeline_v1_r01_20260726"
SOURCE_CATALOG_DIR = C15_RUN_DIR / "s0" / "source_catalogs"
Z00L_PROMPT_PATH = (
    REPO_ROOT / "work" / "zbatch_prompts" / "candidates" / "extract_event_only_v1.0.md"
)
Z00L_CONTRACT_PATH = REPO_ROOT / "work" / "zbatch_contracts" / "z_event_v1.md"
PROVIDER_CONFIG_PATH = REPO_ROOT / "config" / "providers" / "sensenova_modular_v1.json"

CASE_IDS = ("B01-U0033", "B02-U0039", "B03-U0041")
CASE_CHAPTERS = {"B01-U0033": 33, "B02-U0039": 39, "B03-U0041": 41}
GOLD_POINTERS = {
    "B01-U0033": REPO_ROOT
    / "config"
    / "gold"
    / "Z74B_B01_U0033_structure_gold_current.json",
    "B02-U0039": REPO_ROOT
    / "config"
    / "gold"
    / "Z74B_B02_U0039_structure_gold_current.json",
    "B03-U0041": REPO_ROOT
    / "config"
    / "gold"
    / "Z74B_B03_U0041_structure_gold_current.json",
}

HOT_TYPES = (
    "CHARACTER_STATE_CHANGE",
    "KNOWLEDGE_OR_BELIEF_CHANGE",
    "GOAL_PLAN_PROMISE_THREAT",
    "RELATION_IDENTITY_OWNERSHIP_RESOURCE_LOCATION_CHANGE",
    "WORLD_RULE_ABILITY_LIMIT_COST",
    "KEY_CAUSAL_TRIGGER",
    "UNRESOLVED_FORESHADOW_RISK_TODO",
    "CHAPTER_EXIT_STATE",
)

AUTHOR_QUESTIONS = (
    ("R1-Q01", "主角当前在哪里，处于什么状态？"),
    ("R1-Q02", "本章发生了哪些会影响后续的状态变化？"),
    ("R1-Q03", "谁在本章新知道了什么？"),
    ("R1-Q04", "谁仍不知道什么，或误信了什么？"),
    ("R1-Q05", "本章新增了哪些目标、计划、承诺或威胁？"),
    ("R1-Q06", "本章有哪些关系、身份或归属发生了变化？"),
    ("R1-Q07", "哪些资源、物品、位置或能力发生了转移或改变？"),
    ("R1-Q08", "下一章必须继续处理哪些未决事项、风险或伏笔？"),
    ("R1-Q09", "本章关键结果由哪些因果触发？"),
    ("R1-Q10", "哪些内容只是角色相信、猜测或听说，而不是已确认的世界事实？"),
)

# 这张表只用于评测锁箱，不进入任何模型输入。每个金标原子可服务多个作者问题。
QUESTION_PART_MAP: dict[str, dict[str, list[str]]] = {
    "B01-U0033": {
        "R1-Q01": ["Z74B-B01-U0033-A10-R02", "Z74B-B01-U0033-A11-R01"],
        "R1-Q02": [
            "Z74B-B01-U0033-A03-R02",
            "Z74B-B01-U0033-A08",
            "Z74B-B01-U0033-A09",
            "Z74B-B01-U0033-A10-R02",
            "Z74B-B01-U0033-A17-R01",
            "Z74B-B01-U0033-A17-R02",
        ],
        "R1-Q03": [
            "Z74B-B01-U0033-A02",
            "Z74B-B01-U0033-A03-R01",
            "Z74B-B01-U0033-A04",
            "Z74B-B01-U0033-A05-R01",
            "Z74B-B01-U0033-A06",
            "Z74B-B01-U0033-A09",
            "Z74B-B01-U0033-A10-R01",
            "Z74B-B01-U0033-A15",
        ],
        "R1-Q04": [
            "Z74B-B01-U0033-A13",
            "Z74B-B01-U0033-A15",
        ],
        "R1-Q05": [
            "Z74B-B01-U0033-A01",
            "Z74B-B01-U0033-A03-R03",
            "Z74B-B01-U0033-A07",
            "Z74B-B01-U0033-A11-R02",
            "Z74B-B01-U0033-A11-R03",
            "Z74B-B01-U0033-A12",
            "Z74B-B01-U0033-A13",
            "Z74B-B01-U0033-A14",
            "Z74B-B01-U0033-A16",
            "Z74B-B01-U0033-A18",
        ],
        "R1-Q06": [
            "Z74B-B01-U0033-A08",
            "Z74B-B01-U0033-A11-R01",
            "Z74B-B01-U0033-A14",
            "Z74B-B01-U0033-A16",
            "Z74B-B01-U0033-A17-R01",
            "Z74B-B01-U0033-A17-R02",
            "Z74B-B01-U0033-A18",
        ],
        "R1-Q07": [
            "Z74B-B01-U0033-A08",
            "Z74B-B01-U0033-A17-R02",
            "Z74B-B01-U0033-A18",
        ],
        "R1-Q08": [
            "Z74B-B01-U0033-A01",
            "Z74B-B01-U0033-A13",
            "Z74B-B01-U0033-A14",
            "Z74B-B01-U0033-A16",
            "Z74B-B01-U0033-A18",
        ],
        "R1-Q09": [
            "Z74B-B01-U0033-A02",
            "Z74B-B01-U0033-A03-R01",
            "Z74B-B01-U0033-A03-R02",
            "Z74B-B01-U0033-A03-R03",
            "Z74B-B01-U0033-A05-R01",
        ],
        "R1-Q10": [
            "Z74B-B01-U0033-A01",
            "Z74B-B01-U0033-A11-R03",
            "Z74B-B01-U0033-A12",
            "Z74B-B01-U0033-A15",
        ],
    },
    "B02-U0039": {
        "R1-Q01": ["Z74B-B02-U0039-A03"],
        "R1-Q02": ["Z74B-B02-U0039-A03"],
        "R1-Q03": ["Z74B-B02-U0039-A04"],
        "R1-Q04": ["Z74B-B02-U0039-A05", "Z74B-B02-U0039-A08"],
        "R1-Q05": ["Z74B-B02-U0039-A02", "Z74B-B02-U0039-A06"],
        "R1-Q06": [],
        "R1-Q07": ["Z74B-B02-U0039-A03"],
        "R1-Q08": [
            "Z74B-B02-U0039-A02",
            "Z74B-B02-U0039-A05",
            "Z74B-B02-U0039-A06",
            "Z74B-B02-U0039-A07",
            "Z74B-B02-U0039-A08",
        ],
        "R1-Q09": ["Z74B-B02-U0039-A01", "Z74B-B02-U0039-A04"],
        "R1-Q10": [
            "Z74B-B02-U0039-A01",
            "Z74B-B02-U0039-A04",
            "Z74B-B02-U0039-A05",
            "Z74B-B02-U0039-A08",
        ],
    },
    "B03-U0041": {
        "R1-Q01": [
            "Z74B-B03-U0041-A01",
            "Z74B-B03-U0041-A02",
            "Z74B-B03-U0041-A13",
        ],
        "R1-Q02": [
            "Z74B-B03-U0041-A01",
            "Z74B-B03-U0041-A02",
            "Z74B-B03-U0041-A03-R01",
            "Z74B-B03-U0041-A07",
            "Z74B-B03-U0041-A11",
        ],
        "R1-Q03": ["Z74B-B03-U0041-A11", "Z74B-B03-U0041-A13"],
        "R1-Q04": [
            "Z74B-B03-U0041-A03-R02",
            "Z74B-B03-U0041-A04-R01",
            "Z74B-B03-U0041-A04-R02",
            "Z74B-B03-U0041-A06",
            "Z74B-B03-U0041-A10",
            "Z74B-B03-U0041-A11",
            "Z74B-B03-U0041-A12",
            "Z74B-B03-U0041-A13",
            "Z74B-B03-U0041-A14",
        ],
        "R1-Q05": [
            "Z74B-B03-U0041-A05",
            "Z74B-B03-U0041-A08",
            "Z74B-B03-U0041-A09",
        ],
        "R1-Q06": [],
        "R1-Q07": [
            "Z74B-B03-U0041-A01",
            "Z74B-B03-U0041-A03-R01",
            "Z74B-B03-U0041-A07",
            "Z74B-B03-U0041-A11",
        ],
        "R1-Q08": [
            "Z74B-B03-U0041-A04-R01",
            "Z74B-B03-U0041-A05",
            "Z74B-B03-U0041-A06",
            "Z74B-B03-U0041-A08",
            "Z74B-B03-U0041-A09",
            "Z74B-B03-U0041-A13",
            "Z74B-B03-U0041-A14",
        ],
        "R1-Q09": ["Z74B-B03-U0041-A07", "Z74B-B03-U0041-A14"],
        "R1-Q10": [
            "Z74B-B03-U0041-A03-R02",
            "Z74B-B03-U0041-A04-R01",
            "Z74B-B03-U0041-A04-R02",
            "Z74B-B03-U0041-A06",
            "Z74B-B03-U0041-A09",
            "Z74B-B03-U0041-A10",
            "Z74B-B03-U0041-A11",
            "Z74B-B03-U0041-A12",
            "Z74B-B03-U0041-A14",
        ],
    },
}

UNCERTAINTY_MARKERS = ("恐怕", "或许", "似乎", "可能", "未确认", "没有确认", "无法确认", "不相信", "认为", "推断", "判断", "疑问")
NEGATION_MARKERS = ("不", "未", "无", "没有", "不能", "无法", "不敢", "不想", "不得")


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def source_catalog(case_id: str) -> dict[str, Any]:
    return read_json(SOURCE_CATALOG_DIR / f"{case_id}.json")


def active_gold(case_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    pointer = read_json(GOLD_POINTERS[case_id])
    path = REPO_ROOT / pointer["active_gold"]["path"]
    if sha256_file(path) != pointer["active_gold"]["sha256"]:
        raise ValueError(f"{case_id} 正式金标 SHA 漂移")
    return path, pointer, read_json(path)


def formal_parts(case_id: str) -> dict[str, dict[str, Any]]:
    _, _, gold = active_gold(case_id)
    rows: dict[str, dict[str, Any]] = {}
    for item in gold["layered_items"]:
        for part in item.get("parts") or []:
            if part.get("formal_score_eligible"):
                rows[part["part_id"]] = part
    return rows


def overlapping_source_ids(
    sentences: Iterable[Mapping[str, Any]], start: int, end: int
) -> list[str]:
    return [
        str(row["sentence_id"])
        for row in sentences
        if int(row["char_end_exclusive"]) > start
        and int(row["char_start"]) < end
    ]


def question_reference_map() -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    gold_inputs: dict[str, Any] = {}
    for case_id in CASE_IDS:
        catalog = source_catalog(case_id)
        path, pointer, _ = active_gold(case_id)
        parts = formal_parts(case_id)
        gold_inputs[case_id] = {
            "pointer_path": str(GOLD_POINTERS[case_id].relative_to(REPO_ROOT)),
            "pointer_sha256": sha256_file(GOLD_POINTERS[case_id]),
            "formal_gold_path": str(path.relative_to(REPO_ROOT)),
            "formal_gold_sha256": pointer["active_gold"]["sha256"],
            "source_catalog_path": str(
                (SOURCE_CATALOG_DIR / f"{case_id}.json").relative_to(REPO_ROOT)
            ),
            "source_catalog_sha256": sha256_file(
                SOURCE_CATALOG_DIR / f"{case_id}.json"
            ),
        }
        for question_id, question_text in AUTHOR_QUESTIONS:
            part_ids = QUESTION_PART_MAP[case_id][question_id]
            required_parts = []
            for part_id in part_ids:
                part = parts.get(part_id)
                if part is None:
                    raise ValueError(f"{case_id} 找不到正式金标原子 {part_id}")
                groups = []
                for evidence in part.get("source_evidence") or []:
                    ids = overlapping_source_ids(
                        catalog["sentences"],
                        int(evidence["cache_body_start_char"]),
                        int(evidence["cache_body_end_char_exclusive"]),
                    )
                    if not ids:
                        raise ValueError(f"{part_id} 证据没有映到 S0 source ID")
                    groups.append(ids)
                claim = str(part["claim"])
                required_parts.append(
                    {
                        "part_id": part_id,
                        "source_id_groups": groups,
                        "must_retain_uncertainty": any(
                            marker in claim for marker in UNCERTAINTY_MARKERS
                        ),
                        "must_retain_negation": any(
                            marker in claim for marker in NEGATION_MARKERS
                        ),
                    }
                )
            cells.append(
                {
                    "cell_id": f"{case_id}::{question_id}",
                    "case_id": case_id,
                    "question_id": question_id,
                    "question_text": question_text,
                    "expected": "OPEN" if not required_parts else "ANSWERED",
                    "required_parts": required_parts,
                    "scoring_rule": (
                        "OPEN 无需材料；ANSWERED 须每个金标原子的每组证据至少命中一个"
                        "冻结 source ID。"
                    ),
                }
            )
    value = {
        "schema_version": "v02-r1-question-reference-map.v1",
        "model_visible": False,
        "formal_gold_payload_exported": False,
        "cell_total": 30,
        "gold_inputs": gold_inputs,
        "cells": cells,
        "reference_map_sha256": "",
    }
    value["reference_map_sha256"] = canonical_sha(
        {k: v for k, v in value.items() if k != "reference_map_sha256"}
    )
    return value


def z00l_output_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "z-event-v1",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "chapter", "coverage_audit", "events"],
        "properties": {
            "schema_version": {"const": "z-event-v1"},
            "chapter": {"type": "integer", "minimum": 1},
            "coverage_audit": {
                "type": "object",
                "additionalProperties": False,
                "required": ["status", "event_ids", "reason"],
                "properties": {
                    "status": {"enum": ["emitted", "none"]},
                    "event_ids": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                    "reason": {"type": "string", "minLength": 1},
                },
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["event_id", "event", "anchors"],
                    "properties": {
                        "event_id": {"type": "string", "minLength": 1},
                        "event": {"type": "string", "minLength": 1},
                        "anchors": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["anchor_id"],
                                "properties": {
                                    "anchor_id": {
                                        "type": "string",
                                        "minLength": 1,
                                    }
                                },
                            },
                        },
                    },
                },
            },
        },
    }


def hot_output_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "v02-r1-hot-material.v1",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "chapter", "scope_id", "facts", "cold_index"],
        "properties": {
            "schema_version": {"const": "v02-r1-hot-material.v1"},
            "chapter": {"type": "integer", "minimum": 1},
            "scope_id": {"type": "string", "minLength": 1},
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "fact_id",
                        "statement",
                        "category",
                        "actuality",
                        "source_ids",
                    ],
                    "properties": {
                        "fact_id": {"type": "string", "minLength": 1},
                        "statement": {"type": "string", "minLength": 1},
                        "category": {"enum": list(HOT_TYPES)},
                        "actuality": {
                            "enum": [
                                "CONFIRMED",
                                "BELIEVED",
                                "INFERRED",
                                "PLANNED",
                                "NEGATED",
                                "UNRESOLVED",
                            ]
                        },
                        "source_ids": {
                            "type": "array",
                            "minItems": 1,
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
            "cold_index": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["source_id", "reason"],
                    "properties": {
                        "source_id": {"type": "string", "minLength": 1},
                        "reason": {"const": "COLD_DETAIL_NOT_IN_LEDGER"},
                    },
                },
            },
        },
    }


def evidence_catalog(case_id: str, source_ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    catalog = source_catalog(case_id)
    selected = set(source_ids) if source_ids is not None else None
    return [
        {
            "anchor_id": row["sentence_id"],
            "chapter": CASE_CHAPTERS[case_id],
            "quote": row["original_text"],
            "body_start_char": row["char_start"],
            "body_end_char_exclusive": row["char_end_exclusive"],
        }
        for row in catalog["sentences"]
        if selected is None or row["sentence_id"] in selected
    ]


def two_chunks(case_id: str) -> list[dict[str, Any]]:
    catalog = source_catalog(case_id)
    length = len(catalog["source_text"])
    boundaries = [
        int(row["char_end_exclusive"])
        for row in catalog["paragraphs"][:-1]
        if 0 < int(row["char_end_exclusive"]) < length
    ]
    split = min(boundaries, key=lambda value: (abs(value - length / 2), value))
    chunks = []
    for index, (start, end) in enumerate(((0, split), (split, length)), start=1):
        source_ids = [
            row["sentence_id"]
            for row in catalog["sentences"]
            if int(row["char_end_exclusive"]) > start
            and int(row["char_start"]) < end
        ]
        chunks.append(
            {
                "scope_id": f"{case_id}-CHUNK-{index:02d}",
                "char_start": start,
                "char_end_exclusive": end,
                "source_ids": source_ids,
            }
        )
    return chunks


def render_z00l_user(case_id: str) -> str:
    template = Z00L_PROMPT_PATH.read_text(encoding="utf-8")
    replacements = {
        "{{CHAPTER_NUMBER}}": str(CASE_CHAPTERS[case_id]),
        "{{CHAPTER_PADDED}}": f"{CASE_CHAPTERS[case_id]:04d}",
        "{{CHAPTER_FILENAME}}": case_id,
        "{{EVIDENCE_CATALOG_JSON}}": json.dumps(
            evidence_catalog(case_id), ensure_ascii=False, separators=(",", ":")
        ),
    }
    for old, new in replacements.items():
        template = template.replace(old, new)
    if "{{" in template or "}}" in template:
        raise ValueError(f"{case_id} Z00l 模板仍有未实例化占位")
    return template


def hot_contract_text() -> str:
    return "\n".join(
        [
            "# R1 热事实范围合同 v0",
            "",
            "你只看当前冻结范围，不得使用范围之外或本章之后的知识。",
            "只抽取下列八类会被后续大纲编辑继续查询的热事实：",
            *[f"- {item}" for item in HOT_TYPES],
            "",
            "每条只写一个业务原子：只承担一个可独立查询、独立改状态、独立判真假的更新。",
            "主体、变化、对象和否定／未然／推断限定要齐。",
            "只能引用当前范围给出的 source ID，不输出原文短引，程序按 ID 逐字回填。",
            "不属于八类的冷事实不写进 facts，只登记相关 source ID 到 cold_index。",
            "没有的类型留空，不设条数下限，不得凑数。",
            "只输出符合 v02-r1-hot-material.v1 的 JSON 对象，不要解释或代码围栏。",
        ]
    )


def render_hot_user(case_id: str, scope: Mapping[str, Any]) -> str:
    catalog = source_catalog(case_id)
    by_id = {row["sentence_id"]: row for row in catalog["sentences"]}
    visible = [
        {"source_id": source_id, "text": by_id[source_id]["original_text"]}
        for source_id in scope["source_ids"]
    ]
    return "\n".join(
        [
            hot_contract_text(),
            "",
            f"当前章号：{CASE_CHAPTERS[case_id]}",
            f"当前范围 ID：{scope['scope_id']}",
            f"当前来源目录 SHA：{catalog['catalog_sha256']}",
            "",
            "当前冻结范围：",
            "```json",
            json.dumps(visible, ensure_ascii=False, separators=(",", ":")),
            "```",
        ]
    )


def request_body(messages: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "model": "deepseek-v4-flash",
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 65536,
        "n": 1,
        "reasoning_effort": "medium",
        "response_format": {"type": "json_object"},
    }


def frozen_requests() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
        rows.append(
            {
                "route_id": "A_FULL_ONCE_Z00L",
                "case_id": case_id,
                "scope_id": f"{case_id}-FULL",
                "contract": "CURRENT_Z00L_EXACT",
                "body": request_body(
                    [
                        {
                            "role": "system",
                            "content": "你只做证据约束的中性事件摘取，不做类型判断。只输出合法 JSON。",
                        },
                        {"role": "user", "content": render_z00l_user(case_id)},
                    ]
                ),
            }
        )
        full_scope = {
            "scope_id": f"{case_id}-FULL",
            "source_ids": [
                row["sentence_id"] for row in source_catalog(case_id)["sentences"]
            ],
        }
        rows.append(
            {
                "route_id": "B_HOT_FULL_ONCE",
                "case_id": case_id,
                "scope_id": full_scope["scope_id"],
                "contract": "HOT_FACTS_V0",
                "body": request_body(
                    [
                        {
                            "role": "system",
                            "content": "你只做证据约束的热事实抽取，不做正文外推断。只输出合法 JSON。",
                        },
                        {
                            "role": "user",
                            "content": render_hot_user(case_id, full_scope),
                        },
                    ]
                ),
            }
        )
        for chunk in two_chunks(case_id):
            rows.append(
                {
                    "route_id": "C_HOT_TWO_CHUNKS",
                    "case_id": case_id,
                    "scope_id": chunk["scope_id"],
                    "contract": "HOT_FACTS_V0",
                    "body": request_body(
                        [
                            {
                                "role": "system",
                                "content": "你只做证据约束的热事实抽取，不做正文外推断。只输出合法 JSON。",
                            },
                            {
                                "role": "user",
                                "content": render_hot_user(case_id, chunk),
                            },
                        ]
                    ),
                }
            )
    for index, row in enumerate(rows, start=1):
        row["call_id"] = f"R1-{index:02d}-{row['route_id']}-{row['scope_id']}"
        row["request_sha256"] = canonical_sha(row["body"])
    return rows


def preregistration() -> dict[str, Any]:
    requests = frozen_requests()
    value = {
        "schema_version": "v02-r1-route-comparison-preregistration.v2",
        "authority": {
            "notion_page_id": "1de0edcf446244f9ad04f0f3ef58a750",
            "revision": "修正令② 2026-07-26 20:45",
            "waiting_for_notion_signature": False,
        },
        "goal": "找出抽取步的质量与成本平衡口。",
        "routes": {
            "A_FULL_ONCE_Z00L": "现役 Z00l 合同，整章一次。",
            "B_HOT_FULL_ONCE": "热事实范围合同包，整章一次。",
            "C_HOT_TWO_CHUNKS": "热事实范围合同包，每章机械切成两块。",
        },
        "interpretation_boundary": (
            "B/C 相对 A 改的是范围合同包，包含输出形状；B 对 A 可看合同包收益，"
            "C 对 B 可看同一热事实合同下的分块收益，不冒充纯提示词单变量。"
        ),
        "question_set": {
            "questions": [
                {"question_id": qid, "question_text": text}
                for qid, text in AUTHOR_QUESTIONS
            ],
            "cell_total": 30,
            "sha256": canonical_sha(AUTHOR_QUESTIONS),
        },
        "quality_and_cost_gates": {
            "answerable_cells": "candidate >= A_FULL_ONCE_Z00L",
            "critical_errors": "candidate <= A_FULL_ONCE_Z00L",
            "material_row_reduction_minimum": 0.30,
            "material_output_token_reduction_minimum": 0.30,
            "all_four_required_for_candidate_win": True,
        },
        "reference_map_sha256": question_reference_map()["reference_map_sha256"],
        "provider": read_json(PROVIDER_CONFIG_PATH),
        "model": "deepseek-v4-flash",
        "route_call_budget": {
            "A_FULL_ONCE_Z00L": 3,
            "B_HOT_FULL_ONCE": 3,
            "C_HOT_TWO_CHUNKS": 6,
            "total": 12,
            "retry": 0,
            "supplier_quota_hard_stop": 500,
        },
        "requests": [
            {
                key: row[key]
                for key in (
                    "call_id",
                    "route_id",
                    "case_id",
                    "scope_id",
                    "contract",
                    "request_sha256",
                )
            }
            for row in requests
        ],
        "pre_send_gates": [
            "API_KEY_EXISTS_WITHOUT_READING_VALUE",
            "ALL_REQUEST_SHA_RECHECK",
            "FORMAL_GOLD_NOT_IN_MODEL_MESSAGES",
            "CALL_COUNT_WITHIN_500",
        ],
        "network_authorization": {
            "execute_allowed": True,
            "reason": "NOTION_20_45_CORRECTION_CANCELLED_PREREG_SIGNATURE_STOP",
        },
        "candidate_status": "candidate_silver_not_active",
        "preregistration_sha256": "",
    }
    value["preregistration_sha256"] = canonical_sha(
        {k: v for k, v in value.items() if k != "preregistration_sha256"}
    )
    return value


def build_artifacts() -> dict[str, bytes]:
    requests = frozen_requests()
    artifacts: dict[str, bytes] = {
        "preregistration.json": json_bytes(preregistration()),
        "question_reference_map.lockbox.json": json_bytes(question_reference_map()),
        "schemas/z_event_v1.schema.json": json_bytes(z00l_output_schema()),
        "schemas/hot_material_v1.schema.json": json_bytes(hot_output_schema()),
        "contracts/z00l_prompt_exact.md": Z00L_PROMPT_PATH.read_bytes(),
        "contracts/z_event_v1_exact.md": Z00L_CONTRACT_PATH.read_bytes(),
        "contracts/hot_facts_v0.md": (
            hot_contract_text() + "\n\n来源：Codex\n"
        ).encode("utf-8"),
    }
    for row in requests:
        artifacts[f"requests/{row['call_id']}.json"] = json_bytes(row)
    manifest = {
        "schema_version": "v02-r1-route-comparison-manifest.v1",
        "candidate_status": "candidate_silver_not_active",
        "model_api_calls": 0,
        "network_requests": 0,
        "git_commit_or_push": False,
        "artifacts": {
            path: hashlib.sha256(raw).hexdigest()
            for path, raw in sorted(artifacts.items())
        },
        "artifact_tree_sha256": "",
    }
    manifest["artifact_tree_sha256"] = canonical_sha(manifest["artifacts"])
    artifacts["manifest.json"] = json_bytes(manifest)
    return artifacts


def write_artifacts(output_dir: Path = RUN_DIR / "frozen") -> dict[str, Any]:
    artifacts = build_artifacts()
    for relative, raw in artifacts.items():
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    manifest = json.loads(artifacts["manifest.json"])
    return {
        "status": "FROZEN_EXECUTE_ALLOWED_BY_NOTION_20_45",
        "output_dir": str(output_dir),
        "artifact_tree_sha256": manifest["artifact_tree_sha256"],
        "request_count": 12,
        "model_api_calls": 0,
        "network_requests": 0,
        "execute_allowed": True,
    }


if __name__ == "__main__":
    print(json.dumps(write_artifacts(), ensure_ascii=False, indent=2, sort_keys=True))

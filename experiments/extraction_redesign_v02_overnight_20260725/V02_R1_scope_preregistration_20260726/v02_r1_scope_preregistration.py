#!/usr/bin/env python3
"""R1 范围实验预注册候选件。

本工具只生成离线预注册工件，不读取密钥，不导入网络客户端，不发送
模型请求。R1 的唯一变量是材料抽取范围：

- A：全量业务事实；
- B：八类热事实＋冷事实来源索引。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "V02_R1_scope_preregistration_20260726"
)
DEFAULT_REPORT_DIR = (
    REPO_ROOT / "reports" / "V02_R1_scope_preregistration_20260726"
)
C15_RUN_DIR = REPO_ROOT / "runs" / "V02_C15_pipeline_v1_r01_20260726"
C6_CONTROL_RUN_DIR = (
    REPO_ROOT / "runs" / "V02_实验A锚先行倒装_C6对照臂_r05_20260725"
)
C6_BASELINE_REQUEST = (
    C6_CONTROL_RUN_DIR
    / "samples"
    / "main"
    / "B02-U0039"
    / "transport"
    / "request.json"
)

CASE_IDS = ("B01-U0033", "B02-U0039", "B03-U0041")
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
EXPERIMENT_HARD_STOP_REASONS = (
    "WRONG_MODEL",
    "INPUT_BODY_OR_SHA_CHANGED",
    "FORMAL_GOLD_LEAKED_TO_MODEL_WINDOW",
    "EXECUTOR_BUG",
    "UNFROZEN_PROMPT_SENT",
    "PROVIDER_MODEL_ID_CHANGED",
)


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def author_question_set() -> dict[str, Any]:
    questions = [
        ("R1-Q01", "主角当前在哪里，处于什么状态？"),
        ("R1-Q02", "本章发生了哪些会影响后续的状态变化？"),
        ("R1-Q03", "谁在本章新知道了什么？"),
        ("R1-Q04", "谁仍不知道什么，或误信了什么？"),
        ("R1-Q05", "本章新增了哪些目标、计划、承诺或威胁？"),
        ("R1-Q06", "本章有哪些关系、身份或归属发生了变化？"),
        ("R1-Q07", "哪些资源、物品、位置或能力发生了转移或改变？"),
        ("R1-Q08", "下一章必须继续处理哪些未决事项、风险或伏笔？"),
        ("R1-Q09", "本章关键结果由哪些因果触发？"),
        (
            "R1-Q10",
            "哪些内容只是角色相信、猜测或听说，而不是已确认的世界事实？",
        ),
    ]
    value: dict[str, Any] = {
        "schema_version": "v02-r1-author-question-set.v1",
        "scope": "CHAPTER_LEVEL_REPEATED_FOR_EACH_OF_3_CASES",
        "question_count_per_chapter": 10,
        "scored_cell_total": 30,
        "questions": [
            {
                "question_id": question_id,
                "question_text": text,
                "answer_rule": (
                    "只认冻结材料中可追溯到 source ID 的回答；材料不足可记 OPEN，"
                    "不得用模型常识补全。"
                ),
            }
            for question_id, text in questions
        ],
        "model_visible": False,
        "frozen_before_send": True,
        "question_set_sha256": "",
    }
    value["question_set_sha256"] = canonical_sha(
        {key: item for key, item in value.items() if key != "question_set_sha256"}
    )
    return value


def decision_rule() -> dict[str, Any]:
    return {
        "schema_version": "v02-r1-decision-rule.v1",
        "winner": "B_ONLY_IF_ALL_THREE_GATES_PASS",
        "gates": {
            "answerable_question_count": {
                "formula": "B_answerable_cells >= A_answerable_cells",
                "denominator": 30,
                "open_is_answerable": False,
            },
            "critical_error_count": {
                "formula": "B_critical_errors <= A_critical_errors",
                "semantic_undecidable_result": "OPEN_NOT_FORCE_SCORED",
            },
            "material_reduction": {
                "fact_count_reduction_minimum": 0.30,
                "material_output_token_reduction_minimum": 0.30,
                "fact_count_formula": "1 - B_fact_count / A_fact_count",
                "material_output_token_formula": (
                    "1 - B_material_output_tokens / A_material_output_tokens"
                ),
                "material_output_tokens_definition": (
                    "provider usage completion_tokens minus "
                    "completion_tokens_details.reasoning_tokens"
                ),
                "aggregation": "SUM_ALL_6_CALLS_PER_ARM",
                "zero_or_missing_denominator": "MATERIALS_INSUFFICIENT",
            },
        },
        "threshold_rationale": (
            "30% 作为开跑前冻结的明显下降线；低于该值不把普通格式波动冒充"
            "范围收益，也不采用更激进的 50% 预设来逼迫少产出。"
        ),
        "question_adjudication": {
            "priority": [
                "MECHANICAL_ID_AND_SOURCE_TRACE",
                "FORMAL_GOLD_MAPPING_IN_EVALUATION_ONLY_LOCKBOX",
                "OPEN",
            ],
            "model_self_score_allowed": False,
            "formal_gold_model_visible": False,
            "question_reference_map_status": (
                "MUST_FREEZE_BEFORE_FIRST_API_CALL"
            ),
        },
        "negative_result_policy": (
            "模型质量失败记负成绩并跑完批次；只有预注册六类实验条件损坏才整批硬停。"
        ),
    }


def arm_a_output_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "z-event-v1",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "chapter", "events"],
        "properties": {
            "schema_version": {"const": "z-event-v1"},
            "chapter": {"type": "integer", "minimum": 1},
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


def arm_b_output_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "v02-r1-hot-material.v1",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "chapter",
            "chunk_id",
            "facts",
            "cold_index",
        ],
        "properties": {
            "schema_version": {
                "const": "v02-r1-hot-material.v1"
            },
            "chapter": {"type": "integer", "minimum": 1},
            "chunk_id": {"type": "string", "minLength": 1},
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


def current_full_contract_identity() -> dict[str, Any]:
    request = read_json(C6_BASELINE_REQUEST)
    body = request["body"]
    system = body["messages"][0]["content"]
    user = body["messages"][1]["content"]
    contract_prefix = user.split("\n当前章号：", maxsplit=1)[0]
    return {
        "source_request_path": str(C6_BASELINE_REQUEST.relative_to(REPO_ROOT)),
        "source_request_file_sha256": sha256_file(C6_BASELINE_REQUEST),
        "provider": request["provider"],
        "model": request["model"],
        "request_parameters": {
            key: body[key]
            for key in (
                "max_tokens",
                "model",
                "n",
                "reasoning_effort",
                "response_format",
                "temperature",
            )
        },
        "system_message": system,
        "system_message_sha256": hashlib.sha256(system.encode("utf-8")).hexdigest(),
        "user_contract_prefix": contract_prefix,
        "user_contract_prefix_sha256": hashlib.sha256(
            contract_prefix.encode("utf-8")
        ).hexdigest(),
        "output_schema_sha256": canonical_sha(arm_a_output_schema()),
    }


def shared_input_envelope() -> dict[str, Any]:
    baseline = current_full_contract_identity()
    return {
        "provider": baseline["provider"],
        "model": baseline["model"],
        "request_parameters": baseline["request_parameters"],
        "same_case_ids": list(CASE_IDS),
        "same_two_chunks_per_case": True,
        "same_visible_source_units": True,
        "same_source_id_closed_set": True,
        "same_program_quote_backfill": True,
        "same_retry_budget": 0,
    }


def arm_contract(arm: str) -> dict[str, Any]:
    baseline = current_full_contract_identity()
    if arm == "A":
        scope_rules = [
            "现役 Z00l 中性事件提取 Prompt v1.0 的合同前缀逐字复用。",
            "继续找出以后可能被读取的全部原子事件，不增加八类热事实过滤。",
            "继续输出 z-event-v1；不增加 cold_index 或 category 字段。",
        ]
        contract_id = "R1-A-Z00L-NEUTRAL-EVENT-v1"
        scope = "CURRENT_Z00L_FULL_NEUTRAL_EVENTS"
        output_schema = arm_a_output_schema()
        model_visible_contract = baseline["user_contract_prefix"]
        permitted_delta_from_current: list[str] = []
    elif arm == "B":
        scope_rules = [
            "facts 只保留冻结的八类热事实；不得规定或暗示条数下限。",
            "冷事实不写成事实条，只把相关 source ID 放进 cold_index，供以后按需回查。",
            "八类均须按正文实际出现情况抽取；没有就留空，不得凑数。",
        ]
        contract_id = "R1-B-HOT-FACTS-v0"
        scope = "HOT_FACTS_EIGHT_TYPES_PLUS_COLD_INDEX"
        output_schema = arm_b_output_schema()
        model_visible_contract = "\n".join(
            [
                "# R1 热事实范围合同 v0",
                "",
                "你只看当前冻结块，不得使用本章之后或材料之外的知识。",
                "只抽取下列八类会被后续大纲编辑继续查询的热事实：",
                *[f"- {item}" for item in HOT_TYPES],
                "",
                "每条只写一个事实头；主体、变化、对象和否定／未然／推断限定要齐。",
                "只能引用当前块给出的 source ID，不输出原文短引，程序按 ID 逐字回填。",
                "不属于八类的冷事实不写进 facts，只登记相关 source ID 到 cold_index。",
                "没有的类型留空，不设条数下限，不得凑数。",
                "只输出符合 v02-r1-hot-material.v1 的 JSON 对象，不要解释或代码围栏。",
            ]
        )
        permitted_delta_from_current = [
            "MODEL_VISIBLE_SCOPE_RULES",
            "OUTPUT_SCHEMA_FROM_Z_EVENT_V1_TO_V02_R1_HOT_MATERIAL_V1",
        ]
    else:
        raise ValueError(f"未知实验臂：{arm}")
    return {
        "schema_version": "v02-r1-arm-contract.v1",
        "arm": arm,
        "contract_id": contract_id,
        "scope": scope,
        "current_contract_baseline_identity": baseline,
        "shared_input_envelope": shared_input_envelope(),
        "scope_rules": scope_rules,
        "hot_type_enum": list(HOT_TYPES),
        "output_schema_sha256": canonical_sha(output_schema),
        "model_visible_contract": model_visible_contract,
        "model_visible_contract_sha256": hashlib.sha256(
            model_visible_contract.encode("utf-8")
        ).hexdigest(),
        "permitted_delta_from_current": permitted_delta_from_current,
        "program_quote_backfill": True,
        "model_writes_verbatim_quote": False,
        "candidate_status": "candidate_silver_not_active",
    }


def contract_sample(arm: str) -> dict[str, Any]:
    contract = arm_contract(arm)
    if arm == "A":
        output_shape = {
            "schema_version": "z-event-v1",
            "chapter": 1,
            "events": [
                {
                    "event_id": "EV-C0001-01",
                    "event": "本章明确发生或说出口的一件中性事实",
                    "anchors": [{"anchor_id": "S0001"}],
                }
            ],
        }
    else:
        output_shape = {
            "schema_version": "v02-r1-hot-material.v1",
            "chapter": 1,
            "chunk_id": "EXAMPLE-CHUNK-01",
            "facts": [
                {
                    "fact_id": "F001",
                    "statement": "某人物形成了一个以后需要兑现的计划。",
                    "category": "GOAL_PLAN_PROMISE_THREAT",
                    "actuality": "PLANNED",
                    "source_ids": ["S0001"],
                }
            ],
            "cold_index": [
                {
                    "source_id": "S0002",
                    "reason": "COLD_DETAIL_NOT_IN_LEDGER",
                }
            ],
        }
    return {
        "schema_version": "v02-r1-contract-sample.v1",
        "sample_only_not_executable": True,
        "contract": contract,
        "user_message_template": {
            "chapter": "<运行时注入>",
            "chunk_id": "<运行时注入>",
            "source_catalog_sha256": "<运行时注入>",
            "visible_source_units": [
                {
                    "source_id": "<冻结目录内ID>",
                    "text": "<冻结正文逐字片段>",
                }
            ],
        },
        "output_shape_example": output_shape,
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def experiment_chunk_plan(case_id: str) -> dict[str, Any]:
    path = C15_RUN_DIR / "s0" / "source_catalogs" / f"{case_id}.json"
    catalog = read_json(path)
    text_length = len(catalog["source_text"])
    paragraph_ends = [
        row["char_end_exclusive"]
        for row in catalog["paragraphs"][:-1]
        if 0 < row["char_end_exclusive"] < text_length
    ]
    if not paragraph_ends:
        raise ValueError(f"{case_id} 没有可用段落边界")
    midpoint = text_length / 2
    split = min(paragraph_ends, key=lambda value: (abs(value - midpoint), value))
    chunks = []
    for index, (start, end) in enumerate(
        ((0, split), (split, text_length)),
        start=1,
    ):
        source_ids = [
            row["sentence_id"]
            for row in catalog["sentences"]
            if row["char_end_exclusive"] > start
            and row["char_start"] < end
        ]
        chunks.append(
            {
                "chunk_id": f"{case_id}-R1-CHUNK-{index:02d}",
                "primary_range": {
                    "char_start": start,
                    "char_end_exclusive": end,
                },
                "visible_source_ids": source_ids,
                "context_only_ranges": [],
            }
        )
    value: dict[str, Any] = {
        "schema_version": "v02-r1-experiment-chunk-plan.v1",
        "case_id": case_id,
        "source_catalog_path": str(path.relative_to(REPO_ROOT)),
        "source_catalog_file_sha256": sha256_file(path),
        "source_catalog_sha256": catalog["catalog_sha256"],
        "policy": "R1_EXPERIMENT_ONLY_TWO_HALVES_NEAREST_PARAGRAPH",
        "general_s1_calibration_changed": False,
        "chunk_count": 2,
        "chunks": chunks,
        "plan_sha256": "",
    }
    value["plan_sha256"] = canonical_sha(
        {key: item for key, item in value.items() if key != "plan_sha256"}
    )
    return value


def call_matrix(plans: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arm in ("A", "B"):
        contract = arm_contract(arm)
        for plan in plans:
            for chunk in plan["chunks"]:
                rows.append(
                    {
                        "logical_call_id": (
                            f"R1-{arm}-{chunk['chunk_id']}"
                        ),
                        "arm": arm,
                        "contract_id": contract["contract_id"],
                        "case_id": plan["case_id"],
                        "chunk_id": chunk["chunk_id"],
                        "chunk_plan_sha256": plan["plan_sha256"],
                        "status": "FROZEN_TEMPLATE_NOT_SENT",
                    }
                )
    return rows


def preregistration() -> dict[str, Any]:
    questions = author_question_set()
    rule = decision_rule()
    plans = [experiment_chunk_plan(case_id) for case_id in CASE_IDS]
    calls = call_matrix(plans)
    value: dict[str, Any] = {
        "schema_version": "v02-r1-scope-preregistration.v1",
        "experiment_id": "V02-R1-SCOPE-20260726",
        "question": (
            "全量业务事实合同与八类热事实合同，哪份更省材料且不降低作者问题可回答性。"
        ),
        "single_variable": "MATERIAL_EXTRACTION_SCOPE_CONTRACT",
        "case_ids": list(CASE_IDS),
        "chunk_policy": (
            "每章固定两块，按字符中点最近段落边界切分；只供 R1 实验，"
            "不冒充 S1 通用块尺寸校准。"
        ),
        "arm_contract_sha256": {
            "A": canonical_sha(arm_contract("A")),
            "B": canonical_sha(arm_contract("B")),
        },
        "arm_output_schema_sha256": {
            "A": canonical_sha(arm_a_output_schema()),
            "B": canonical_sha(arm_b_output_schema()),
        },
        "arm_a_current_contract_identity": current_full_contract_identity(),
        "question_set_sha256": questions["question_set_sha256"],
        "decision_rule_sha256": canonical_sha(rule),
        "call_budget": {
            "A": 6,
            "B": 6,
            "total": 12,
            "retry": 0,
        },
        "model": {
            "provider": "sensenova",
            "model": "deepseek-v4-flash",
            "max_tokens": 65536,
            "same_parameters_both_arms": True,
        },
        "call_matrix": calls,
        "experiment_hard_stop_reasons": list(EXPERIMENT_HARD_STOP_REASONS),
        "quality_failure_policy": "NEGATIVE_SCORE_CONTINUE_BATCH",
        "pre_send_gates": [
            "NOTION_APPROVED_TO_SEND",
            "API_KEY_EXISTENCE_ONLY",
            "EXACT_MODEL_IDENTITY_TICKET",
            "ALL_REQUEST_SHA_RECHECK",
            "QUESTION_REFERENCE_MAP_FROZEN",
        ],
        "network_authorization": {
            "execute_allowed": False,
            "reason": "WAITING_NOTION_PREREGISTRATION_SIGNATURE",
        },
        "model_api_calls": 0,
        "network_requests": 0,
        "candidate_status": "candidate_silver_not_active",
        "preregistration_sha256": "",
    }
    value["preregistration_sha256"] = canonical_sha(
        {
            key: item
            for key, item in value.items()
            if key != "preregistration_sha256"
        }
    )
    return value


def build_artifacts() -> dict[str, bytes]:
    questions = author_question_set()
    rule = decision_rule()
    arm_a_schema = arm_a_output_schema()
    arm_b_schema = arm_b_output_schema()
    plans = [experiment_chunk_plan(case_id) for case_id in CASE_IDS]
    prereg = preregistration()
    artifacts = {
        "author_question_set.json": json_bytes(questions),
        "decision_rule.json": json_bytes(rule),
        "arm_A_z_event_v1.schema.json": json_bytes(arm_a_schema),
        "arm_B_hot_material.schema.json": json_bytes(arm_b_schema),
        "arm_A_full_contract_sample.json": json_bytes(contract_sample("A")),
        "arm_B_hot_contract_sample.json": json_bytes(contract_sample("B")),
        "preregistration.json": json_bytes(prereg),
    }
    for plan in plans:
        artifacts[f"chunk_plans/{plan['case_id']}.json"] = json_bytes(plan)
    manifest: dict[str, Any] = {
        "schema_version": "v02-r1-preregistration-manifest.v1",
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


def stop_report(artifacts: Mapping[str, bytes]) -> str:
    manifest = json.loads(artifacts["manifest.json"])
    prereg = json.loads(artifacts["preregistration.json"])
    questions = json.loads(artifacts["author_question_set.json"])
    lines = [
        "# R1 范围实验｜开跑前预注册停点回包",
        "",
        "✅ 0 模型 API／0 网络；当前 `execute_allowed=false`，等待 Notion 核签。",
        "",
        "## 作者问题集（每章同一套）",
        "",
    ]
    for row in questions["questions"]:
        lines.append(f"- {row['question_id']}：{row['question_text']}")
    lines.extend(
        [
            "",
            "## 降幅阈值",
            "",
            "- B 的 30 个作者问题可回答数不得低于 A。",
            "- B 的关键错误数不得高于 A；机械或金标映射裁不了的记 OPEN，不硬填。",
            "- B 的材料事实条数相对 A 至少下降 30%。",
            (
                "- B 的材料输出 token 相对 A 至少下降 30%；材料 token＝"
                "`completion_tokens - reasoning_tokens`，两臂各 6 次合计后比较。"
            ),
            "- 三条必须同时满足才判 B 胜，任何一条没过都不宣布 B 胜。",
            "",
            "## 两臂合同",
            "",
            "- 共同部分完全相同：同三章、同两块、同 source ID 闭集、程序回填逐字证据、同一 SenseNova V4 Flash、同参数、0 重试。",
            "- A：逐字绑定现役 Z00l 中性事件合同，继续输出 z-event-v1；不另写一份“看起来相同”的新合同。",
            "- B：facts 只保留八类热事实，冷事实只登记 source ID 索引；不设条数下限。",
            "- 两臂输出 schema 不强行伪装成同一份：A 保持现役；B 的范围收窄与对应 schema 一起记作唯一实验变量。",
            "- R1 固定两块只用于本实验，不改 C15 S1 通用校准红灯。",
            "",
            "## 发网边界",
            "",
            f"- 逻辑调用：A {prereg['call_budget']['A']}＋B {prereg['call_budget']['B']}＝{prereg['call_budget']['total']}，0 重试。",
            "- 实验输出差算负成绩并继续跑完；只有错模型、输入或 SHA 变、金标泄露、执行器 bug、题面非冻结版、通道换型号六类才整批硬停。",
            "- 发网前还须 Notion 核签、密钥存在性、精确型号票、请求 SHA 复核、评测区问题—金标映射冻结。",
            "",
            "## SHA",
            "",
            f"- 全件树 SHA：`{manifest['artifact_tree_sha256']}`",
        ]
    )
    for path, digest in manifest["artifacts"].items():
        lines.append(f"- `{path}`：`{digest}`")
    lines.extend(
        [
            "",
            "这些是候选银标预注册件；没有调用模型、没有改现役链、没有提交或推送。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(
    *,
    output_dir: Path,
    report_dir: Path,
) -> dict[str, Any]:
    artifacts = build_artifacts()
    for relative_path, raw in artifacts.items():
        target = output_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "R1_范围实验预注册停点回包.md"
    report_path.write_text(stop_report(artifacts), encoding="utf-8")
    manifest = json.loads(artifacts["manifest.json"])
    return {
        "status": "PASS_ZERO_API_ZERO_NETWORK_WAITING_NOTION_SIGNATURE",
        "output_dir": str(output_dir),
        "report_path": str(report_path),
        "artifact_tree_sha256": manifest["artifact_tree_sha256"],
        "model_api_calls": 0,
        "network_requests": 0,
        "execute_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
    )
    args = parser.parse_args()
    print(
        json.dumps(
            write_artifacts(
                output_dir=args.output_dir,
                report_dir=args.report_dir,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

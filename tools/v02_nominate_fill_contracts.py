#!/usr/bin/env python3
"""抽取工序重设计 v0.2：刀三“点名→填表”零调用设计件。

本工具只冻结两个候选 JSON 合同、严格示例、程序精确去重键与密度护栏。
它没有 HTTP 客户端，不接现役运行器，也不作语义合并或自动补删事实。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping, Sequence

from v02_gate_contracts import ContractValidationError, validate_against_schema


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "D_nominate_fill_design_v1.1"
)
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
HEX64 = "^[0-9a-f]{64}$"
NOMINATION_VERSION = "fact_head_nomination.v1"
FILL_VERSION = "fact_fill_and_anchor.v1"
ACTUALITY = (
    "occurred",
    "reported",
    "believed",
    "planned",
    "unresolved",
    "hypothetical",
)
POLARITY = ("affirmed", "negated", "uncertain")
PRIMARY_FUNCTIONS = (
    "timeline_event",
    "state_update",
    "issue_lifecycle",
    "causal_endpoint",
    "context_only",
)
RELATIONS = (
    "independent",
    "condition",
    "time",
    "motive",
    "method",
    "quantity",
    "location",
    "step",
    "completion",
    "duplicate_candidate",
)
QUALIFIER_TYPES = (
    "time",
    "condition",
    "purpose",
    "motive",
    "method",
    "quantity",
    "location",
    "attribution",
    "modality",
    "scope",
)


class NominateFillError(RuntimeError):
    """候选合同或机械设计件不满足冻结要求。"""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    return sha256_bytes(canonical_bytes(value))


def strict_object(
    properties: Mapping[str, Any],
    *,
    required: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": dict(properties),
        "required": list(required or properties),
    }


def string(*, minimum: int = 0, pattern: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "string", "minLength": minimum}
    if pattern is not None:
        result["pattern"] = pattern
    return result


def fact_head_schema() -> dict[str, Any]:
    return strict_object(
        {
            "subject": string(minimum=1),
            "predicate": string(minimum=1),
            "object": string(),
            "result": string(),
            "polarity": {"type": "string", "enum": list(POLARITY)},
            "actuality": {"type": "string", "enum": list(ACTUALITY)},
        }
    )


def source_span_schema() -> dict[str, Any]:
    return strict_object(
        {
            "block_id": string(minimum=1),
            "start_line": {"type": "integer", "minimum": 1},
            "end_line": {"type": "integer", "minimum": 1},
            "start_char": {"type": "integer", "minimum": 0},
            "end_char_exclusive": {"type": "integer", "minimum": 1},
        }
    )


def nomination_schema() -> dict[str, Any]:
    nomination = strict_object(
        {
            "nomination_id": string(
                pattern="^NH-C[0-9]{4}-B[0-9]{3}-[0-9]{3}$"
            ),
            "fact_head": fact_head_schema(),
            "primary_function": {
                "type": "string",
                "enum": list(PRIMARY_FUNCTIONS),
            },
            "ledger_writes": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": string(minimum=1),
            },
            "relation_to_previous": {
                "type": "string",
                "enum": list(RELATIONS),
            },
            "source_spans": {
                "type": "array",
                "minItems": 1,
                "items": source_span_schema(),
            },
            "nomination_status": {
                "type": "string",
                "const": "CANDIDATE_NOT_FILLED",
            },
        }
    )
    return {
        "$schema": DRAFT_2020_12,
        "$id": "https://local.invalid/contracts/v02/fact_head_nomination.v1.schema.json",
        "title": "点名阶段事实头候选合同",
        **strict_object(
            {
                "schema_version": {
                    "type": "string",
                    "const": NOMINATION_VERSION,
                },
                "chapter_id": string(pattern="^C[0-9]{4}$"),
                "source_hash": string(pattern=HEX64),
                "block_id": string(pattern="^B[0-9]{3}$"),
                "density": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH"],
                },
                "budget_status": {
                    "type": "string",
                    "enum": ["BUDGET_READY", "BUDGET_MISSING"],
                },
                "nominations": {
                    "type": "array",
                    "minItems": 1,
                    "items": nomination,
                },
            }
        ),
        "x_candidate_status": "candidate_silver_not_active",
        "x_stage_boundary": (
            "点名阶段只给事实头、功能、账本写入和原文位置；禁止锚 ID、"
            "评分、金标答案与最终事实 ID。"
        ),
    }


def fill_schema() -> dict[str, Any]:
    qualifier = strict_object(
        {
            "type": {"type": "string", "enum": list(QUALIFIER_TYPES)},
            "value": string(minimum=1),
            "source_span_ids": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": string(minimum=1),
            },
        }
    )
    obligation = strict_object(
        {
            "claim_span": string(minimum=1),
            "anchor_ids": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": string(pattern="^E[0-9]{4}$"),
            },
            "combination": {
                "type": "string",
                "enum": ["all_required", "any_one_sufficient"],
            },
        }
    )
    entry = strict_object(
        {
            "nomination_id": string(
                pattern="^NH-C[0-9]{4}-B[0-9]{3}-[0-9]{3}$"
            ),
            "fact_id": string(pattern="^F-C[0-9]{4}-[0-9]{3}$"),
            "fact_head": fact_head_schema(),
            "qualifiers": {
                "type": "array",
                "items": qualifier,
            },
            "minimal_anchor_ids": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": string(pattern="^E[0-9]{4}$"),
            },
            "support_obligations": {
                "type": "array",
                "minItems": 1,
                "items": obligation,
            },
            "dedup_key": string(pattern=HEX64),
            "density_guard_status": {
                "type": "string",
                "enum": [
                    "PASS",
                    "OVERFLOW_OBSERVE_NO_TRUNCATION",
                    "UNDERFILL_OBSERVE_NO_PADDING",
                    "GRANULARITY_ANOMALY_REVIEW",
                    "BUDGET_MISSING_HOLD",
                    "REVIEW_REQUIRED",
                ],
            },
        }
    )
    return {
        "$schema": DRAFT_2020_12,
        "$id": "https://local.invalid/contracts/v02/fact_fill_and_anchor.v1.schema.json",
        "title": "填表与锚定阶段候选合同",
        **strict_object(
            {
                "schema_version": {
                    "type": "string",
                    "const": FILL_VERSION,
                },
                "chapter_id": string(pattern="^C[0-9]{4}$"),
                "source_hash": string(pattern=HEX64),
                "block_id": string(pattern="^B[0-9]{3}$"),
                "nomination_contract_sha256": string(pattern=HEX64),
                "entries": {
                    "type": "array",
                    "minItems": 1,
                    "items": entry,
                },
            }
        ),
        "x_candidate_status": "candidate_silver_not_active",
        "x_stage_boundary": (
            "每条输出必须回指一个点名 ID；程序精确去重和密度护栏只标记，"
            "不得自动补事实、删正确事实或作语义合并。"
        ),
    }


def _base_fact_head() -> dict[str, str]:
    return {
        "subject": "甲",
        "predicate": "交出",
        "object": "钥匙",
        "result": "乙取得钥匙",
        "polarity": "affirmed",
        "actuality": "occurred",
    }


def valid_examples(schemas: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    nomination = {
        "schema_version": NOMINATION_VERSION,
        "chapter_id": "C0001",
        "source_hash": "a" * 64,
        "block_id": "B001",
        "density": "MEDIUM",
        "budget_status": "BUDGET_MISSING",
        "nominations": [
            {
                "nomination_id": "NH-C0001-B001-001",
                "fact_head": _base_fact_head(),
                "primary_function": "state_update",
                "ledger_writes": ["state:resource"],
                "relation_to_previous": "independent",
                "source_spans": [
                    {
                        "block_id": "B001",
                        "start_line": 2,
                        "end_line": 2,
                        "start_char": 10,
                        "end_char_exclusive": 18,
                    }
                ],
                "nomination_status": "CANDIDATE_NOT_FILLED",
            }
        ],
    }
    key = dedup_key(nomination["nominations"][0])
    fill = {
        "schema_version": FILL_VERSION,
        "chapter_id": "C0001",
        "source_hash": "a" * 64,
        "block_id": "B001",
        "nomination_contract_sha256": canonical_sha(nomination),
        "entries": [
            {
                "nomination_id": "NH-C0001-B001-001",
                "fact_id": "F-C0001-001",
                "fact_head": _base_fact_head(),
                "qualifiers": [],
                "minimal_anchor_ids": ["E0001"],
                "support_obligations": [
                    {
                        "claim_span": "甲交出钥匙",
                        "anchor_ids": ["E0001"],
                        "combination": "all_required",
                    }
                ],
                "dedup_key": key,
                "density_guard_status": "BUDGET_MISSING_HOLD",
            }
        ],
    }
    return {"nomination": nomination, "fill": fill}


def invalid_examples(valid: Mapping[str, Any]) -> dict[str, Any]:
    nomination = json.loads(json.dumps(valid["nomination"], ensure_ascii=False))
    nomination["nominations"][0]["minimal_anchor_ids"] = ["E0001"]
    fill = json.loads(json.dumps(valid["fill"], ensure_ascii=False))
    fill["entries"][0]["self_score"] = 1.0
    return {"nomination": nomination, "fill": fill}


def normalize_piece(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", text).strip()


def dedup_key(nomination: Mapping[str, Any]) -> str:
    fact = nomination.get("fact_head")
    if not isinstance(fact, Mapping):
        raise NominateFillError("点名条缺 fact_head")
    components = {
        field: normalize_piece(fact.get(field, ""))
        for field in (
            "subject",
            "predicate",
            "object",
            "result",
            "polarity",
            "actuality",
        )
    }
    components["primary_function"] = normalize_piece(
        nomination.get("primary_function", "")
    )
    ledgers = nomination.get("ledger_writes")
    if not isinstance(ledgers, list):
        raise NominateFillError("点名条缺 ledger_writes")
    components["ledger_writes"] = sorted(
        normalize_piece(value) for value in ledgers
    )
    return canonical_sha(components)


def dedup_decisions(nominations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """只找机械精确重复；不替程序做语义合并。"""

    groups: dict[str, list[str]] = {}
    for nomination in nominations:
        key = dedup_key(nomination)
        nomination_id = nomination.get("nomination_id")
        if not isinstance(nomination_id, str):
            raise NominateFillError("点名条缺 nomination_id")
        groups.setdefault(key, []).append(nomination_id)
    return [
        {
            "dedup_key": key,
            "nomination_ids": ids,
            "decision": (
                "EXACT_DUPLICATE_REVIEW_REQUIRED"
                if len(ids) > 1
                else "KEEP_UNIQUE"
            ),
            "automatic_merge": False,
        }
        for key, ids in sorted(groups.items())
    ]


def density_guard(
    *,
    observed_count: int,
    budget: int | str,
    control_count: int | str = "CONTROL_COUNT_MISSING",
) -> dict[str, Any]:
    if observed_count < 0:
        raise NominateFillError("条数不能为负")
    if budget == "BUDGET_MISSING":
        status = "BUDGET_MISSING_HOLD"
        floor = None
        ceiling = None
    elif isinstance(budget, int) and not isinstance(budget, bool) and budget > 0:
        floor = max(1, round(budget * 0.75))
        ceiling = round(budget * 1.25)
        if observed_count > 2 * budget:
            status = "GRANULARITY_ANOMALY_REVIEW"
        elif observed_count > ceiling:
            status = "OVERFLOW_OBSERVE_NO_TRUNCATION"
        elif observed_count < floor:
            status = "UNDERFILL_OBSERVE_NO_PADDING"
        else:
            status = "PASS"
    else:
        raise NominateFillError("budget 必须是正整数或 BUDGET_MISSING")
    amplification: float | str
    if isinstance(control_count, int) and not isinstance(control_count, bool):
        if control_count <= 0:
            raise NominateFillError("control_count 必须大于 0")
        amplification = observed_count / control_count
    elif control_count == "CONTROL_COUNT_MISSING":
        amplification = "CONTROL_COUNT_MISSING"
    else:
        raise NominateFillError(
            "control_count 必须是正整数或 CONTROL_COUNT_MISSING"
        )
    return {
        "schema_version": "v02-nominate-fill-density-guard.v1",
        "status": status,
        "observed_count": observed_count,
        "budget": budget,
        "floor_observation": floor,
        "ceiling_observation": ceiling,
        "control_count": control_count,
        "amplification_ratio": amplification,
        "automatic_padding": False,
        "automatic_truncation": False,
        "semantic_merge": False,
        "fcr_regression_check": "PENDING_EXPERIMENT_B",
    }


def validate_instance(instance: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    try:
        validate_against_schema(instance, schema)
    except ContractValidationError as exc:
        raise NominateFillError(str(exc)) from exc


def validate_nomination_fill_pair(
    nomination: Mapping[str, Any],
    fill: Mapping[str, Any],
) -> None:
    """同时核验两段合同，禁止填表件脱离本次点名产物自证。"""

    validate_instance(nomination, nomination_schema())
    validate_instance(fill, fill_schema())

    for field in ("chapter_id", "source_hash", "block_id"):
        if fill.get(field) != nomination.get(field):
            raise NominateFillError(f"跨合同字段不一致：{field}")
    if fill.get("nomination_contract_sha256") != canonical_sha(nomination):
        raise NominateFillError("填表件没有绑定本次点名产物 SHA")

    chapter_id = str(nomination["chapter_id"])
    block_id = str(nomination["block_id"])
    nominations = nomination.get("nominations")
    if not isinstance(nominations, list):
        raise NominateFillError("点名件缺 nominations")
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in nominations:
        nomination_id = str(row["nomination_id"])
        if nomination_id in by_id:
            raise NominateFillError(f"点名编号重复：{nomination_id}")
        if not nomination_id.startswith(f"NH-{chapter_id}-{block_id}-"):
            raise NominateFillError(f"点名编号与章块身份不一致：{nomination_id}")
        spans = row.get("source_spans")
        if not isinstance(spans, list):
            raise NominateFillError(f"{nomination_id} 缺 source_spans")
        for index, span in enumerate(spans):
            if span.get("block_id") != block_id:
                raise NominateFillError(
                    f"{nomination_id} 原文区间 {index} 跨出冻结块"
                )
            if int(span["end_line"]) < int(span["start_line"]):
                raise NominateFillError(
                    f"{nomination_id} 原文区间 {index} 行号逆序"
                )
            if int(span["end_char_exclusive"]) <= int(span["start_char"]):
                raise NominateFillError(
                    f"{nomination_id} 原文区间 {index} 字符位置逆序或为空"
                )
        by_id[nomination_id] = row

    entries = fill.get("entries")
    if not isinstance(entries, list):
        raise NominateFillError("填表件缺 entries")
    seen_nomination_ids: set[str] = set()
    seen_fact_ids: set[str] = set()
    for entry in entries:
        nomination_id = str(entry["nomination_id"])
        fact_id = str(entry["fact_id"])
        if nomination_id in seen_nomination_ids:
            raise NominateFillError(f"一个点名条被重复填表：{nomination_id}")
        if fact_id in seen_fact_ids:
            raise NominateFillError(f"事实编号重复：{fact_id}")
        source = by_id.get(nomination_id)
        if source is None:
            raise NominateFillError(f"填表件引用不存在的点名编号：{nomination_id}")
        if not fact_id.startswith(f"F-{chapter_id}-"):
            raise NominateFillError(f"事实编号与章节身份不一致：{fact_id}")
        if canonical_bytes(entry["fact_head"]) != canonical_bytes(
            source["fact_head"]
        ):
            raise NominateFillError(f"{nomination_id} 的事实头发生漂移")
        if entry.get("dedup_key") != dedup_key(source):
            raise NominateFillError(f"{nomination_id} 的去重键不可复算")
        obligation_anchors = {
            anchor_id
            for obligation in entry["support_obligations"]
            for anchor_id in obligation["anchor_ids"]
        }
        if set(entry["minimal_anchor_ids"]) != obligation_anchors:
            raise NominateFillError(
                f"{nomination_id} 的最小锚集与支撑义务锚并集不一致"
            )
        seen_nomination_ids.add(nomination_id)
        seen_fact_ids.add(fact_id)


def cross_contract_negative_examples(
    valid: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """冻结会被跨合同验证器拒绝的代表性反例。"""

    cases: dict[str, dict[str, Any]] = {}

    missing_id = json.loads(json.dumps(valid, ensure_ascii=False))
    missing_id["fill"]["entries"][0]["nomination_id"] = "NH-C0001-B001-999"
    cases["unknown_nomination_id"] = missing_id

    drifted_head = json.loads(json.dumps(valid, ensure_ascii=False))
    drifted_head["fill"]["entries"][0]["fact_head"]["predicate"] = "保管"
    cases["drifted_fact_head"] = drifted_head

    forged_key = json.loads(json.dumps(valid, ensure_ascii=False))
    forged_key["fill"]["entries"][0]["dedup_key"] = "f" * 64
    cases["forged_dedup_key"] = forged_key

    anchor_mismatch = json.loads(json.dumps(valid, ensure_ascii=False))
    anchor_mismatch["fill"]["entries"][0]["minimal_anchor_ids"].append("E0002")
    cases["minimal_anchor_mismatch"] = anchor_mismatch

    reversed_span = json.loads(json.dumps(valid, ensure_ascii=False))
    reversed_span["nomination"]["nominations"][0]["source_spans"][0][
        "end_char_exclusive"
    ] = 5
    reversed_span["fill"]["nomination_contract_sha256"] = canonical_sha(
        reversed_span["nomination"]
    )
    cases["reversed_source_span"] = reversed_span

    wrong_nomination_sha = json.loads(json.dumps(valid, ensure_ascii=False))
    wrong_nomination_sha["fill"]["nomination_contract_sha256"] = "b" * 64
    cases["wrong_nomination_artifact_sha"] = wrong_nomination_sha
    return cases


def build_artifacts() -> dict[str, bytes]:
    schemas = {
        "nomination": nomination_schema(),
        "fill": fill_schema(),
    }
    valid = valid_examples(schemas)
    invalid = invalid_examples(valid)
    invalid_rejections: dict[str, str] = {}
    for name in schemas:
        validate_instance(valid[name], schemas[name])
        try:
            validate_instance(invalid[name], schemas[name])
        except NominateFillError as exc:
            invalid_rejections[name] = str(exc)
        else:
            raise NominateFillError(f"{name} 非法反例意外通过")
    validate_nomination_fill_pair(valid["nomination"], valid["fill"])
    pair_rejections: dict[str, str] = {}
    pair_negative_examples = cross_contract_negative_examples(valid)
    for name, pair in sorted(pair_negative_examples.items()):
        try:
            validate_nomination_fill_pair(pair["nomination"], pair["fill"])
        except NominateFillError as exc:
            pair_rejections[name] = str(exc)
        else:
            raise NominateFillError(f"跨合同反例意外通过：{name}")

    duplicate_demo = json.loads(
        json.dumps(valid["nomination"]["nominations"], ensure_ascii=False)
    )
    duplicate_demo.append(
        {
            **duplicate_demo[0],
            "nomination_id": "NH-C0001-B001-002",
        }
    )
    dedup_demo = {
        "schema_version": "v02-nominate-fill-dedup-demo.v1",
        "status": "exact_duplicate_found_but_not_auto_merged",
        "rows": dedup_decisions(duplicate_demo),
    }
    density_demos = {
        "schema_version": "v02-nominate-fill-density-demo.v1",
        "missing_budget": density_guard(
            observed_count=12,
            budget="BUDGET_MISSING",
        ),
        "normal": density_guard(observed_count=32, budget=32, control_count=32),
        "overflow": density_guard(observed_count=50, budget=32, control_count=32),
        "granularity_anomaly": density_guard(
            observed_count=65,
            budget=32,
            control_count=32,
        ),
        "underfill": density_guard(
            observed_count=20,
            budget=32,
            control_count=32,
        ),
    }
    design = """# 刀三｜点名→填表候选设计

## 结论

本件只冻结两个候选合同与三道程序护栏，0 API、不启用、不接现役链。

1. `fact_head_nomination.v1` 只点名事实头，输出六值 fact_head、主功能、账本写入、与上一条关系和原文位置。这个阶段禁止输出锚 ID、评分、金标答案和最终 fact_id。
2. `fact_fill_and_anchor.v1` 逐条回指 nomination_id，再填必要限定、最小锚集和支撑义务。每个填表条只能来自一个点名条。
3. 跨合同验证器把填表件钉到本次点名产物 SHA，并复算点名编号、事实头、去重键、最小锚并集和原文区间；两段只过各自 schema 不算通过。
4. 程序去重只计算规范化后的机械精确键。相同键只记 `EXACT_DUPLICATE_REVIEW_REQUIRED`，不自动语义合并。
5. 密度护栏只观察，不补齐、不截断。预算缺失记 `BUDGET_MISSING_HOLD`；大于 2 倍预算只记颗粒度异常，不能靠删除事实过闸。

## 实验 B 才能回答的问题

- `q_missing`、`m_merge`、`s_strength` 是否相对下降至少 30%。
- 条数是否没有放大；若条数下降，FCR 是否不退。
- 单章成本除以 UCR 合格事实数是否不高于对照。

本设计不提前回答这些质量题，也不把候选合同升为默认。

来源：Codex
"""
    files: dict[str, bytes] = {
        "schemas/fact_head_nomination.v1.schema.json": json_bytes(
            schemas["nomination"]
        ),
        "schemas/fact_fill_and_anchor.v1.schema.json": json_bytes(schemas["fill"]),
        "examples/fact_head_nomination.valid.json": json_bytes(valid["nomination"]),
        "examples/fact_head_nomination.invalid.json": json_bytes(
            invalid["nomination"]
        ),
        "examples/fact_fill_and_anchor.valid.json": json_bytes(valid["fill"]),
        "examples/fact_fill_and_anchor.invalid.json": json_bytes(invalid["fill"]),
        "program/dedup_demo.json": json_bytes(dedup_demo),
        "program/density_guard_demo.json": json_bytes(density_demos),
        "program/cross_contract_validation_demo.json": json_bytes(
            {
                "schema_version": "v02-nominate-fill-pair-validation-demo.v1",
                "status": "valid_pair_passed_all_negative_pairs_rejected",
                "valid_nomination_sha256": canonical_sha(valid["nomination"]),
                "negative_case_rejections": pair_rejections,
            }
        ),
        "DESIGN.md": design.encode("utf-8"),
    }
    inventory = [
        {
            "path": path,
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
        }
        for path, raw in sorted(files.items())
    ]
    manifest = {
        "schema_version": "v02-nominate-fill-design-manifest.v1.1",
        "status": "candidate_silver_not_active",
        "contract_versions": [NOMINATION_VERSION, FILL_VERSION],
        "artifact_count_without_manifest": len(files),
        "inventory": inventory,
        "inventory_sha256": canonical_sha(inventory),
        "invalid_examples_rejected": invalid_rejections,
        "cross_contract_negative_examples_rejected": pair_rejections,
        "model_api_calls": 0,
        "network_requests": 0,
        "active_pipeline_changed": False,
        "formal_gold_changed": False,
    }
    files["artifact_manifest.json"] = json_bytes(manifest)
    return files


def write_artifacts(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(artifacts.items()):
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if not path.is_file() or path.read_bytes() != raw:
                raise NominateFillError(f"拒绝覆盖不同内容：{path}")
            continue
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)


def verify_artifacts(
    output_dir: Path,
    artifacts: Mapping[str, bytes],
) -> dict[str, Any]:
    missing: list[str] = []
    changed: list[str] = []
    for relative, raw in sorted(artifacts.items()):
        path = output_dir / relative
        if not path.is_file():
            missing.append(relative)
        elif path.read_bytes() != raw:
            changed.append(relative)
    return {
        "schema_version": "v02-nominate-fill-design-verification.v1",
        "status": "pass" if not missing and not changed else "fail",
        "artifact_count": len(artifacts),
        "missing": missing,
        "changed": changed,
        "artifact_vector_sha256": canonical_sha(
            {
                relative: sha256_bytes(raw)
                for relative, raw in sorted(artifacts.items())
            }
        ),
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "verify"):
        item = sub.add_parser(command)
        item.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifacts = build_artifacts()
    if args.command == "prepare":
        write_artifacts(args.output_dir, artifacts)
    result = verify_artifacts(args.output_dir, artifacts)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

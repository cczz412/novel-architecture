"""第97道零调用 RFU 建账、只读演示与双跑收口。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .core import (
    JUDGE_ELIGIBILITY_FIELDS,
    MATCH_VERDICT_FIELDS,
    compute_score_ticket,
    evaluate_canary_suite,
    sha256_bytes,
    stable_json_bytes,
    validate_candidate_claim,
    validate_judge_eligibility,
    validate_match_verdict,
    validate_rfu,
)
from .fixtures import (
    QUALIFIER_OVERLAY,
    Z89_QUALIFIER_STATUS,
    Z89_REASON_CODES,
    build_canary_suite,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parent
AUTHORITY_TIME = "2026-07-24T14:55:00+08:00"
AUTHORIZED_RUN_DIRECTORY = "runs/Z97_RFU建账与UCR五层候选_v1.0_20260724"
AUTHORIZED_REPORT_DIRECTORY = "reports/Z97_RFU建账与UCR五层候选_20260724"

GOLD_POINTER = "config/gold/X01_ch0003_structure_gold_current.json"
FORMAL_GOLD = (
    "reports/Z73_第3章金标v1.2定稿转正_20260721/"
    "第3章结构层金标v1.2.json"
)
Z89_ROOT = "runs/Z89_X01_DeepSeekV4Pro强模型对照_第3章_v1.0_20260723"
Z89_CATALOG = f"{Z89_ROOT}/inputs/evidence_catalogs/ch0003.json"
Z89_EVENTS = f"{Z89_ROOT}/main/01_extract/events/ch0003.json"
Z89_ADJUDICATION = f"{Z89_ROOT}/review/adjudication_completed.json"
Z89_SCORECARD = f"{Z89_ROOT}/final/scorecard.json"
RETRY03_ROOT = (
    "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_"
    "20260722_transport_retry03"
)
RETRY03_EVENTS = f"{RETRY03_ROOT}/main/01_extract/events/ch0003.json"
RETRY03_BUILD_RECEIPT = f"{RETRY03_ROOT}/review/build_receipt.json"
RETRY03_REJECTED_RAW = (
    f"{RETRY03_ROOT}/review/inspector/ch0003/run/responses/"
    "semantic_route/Z83-MAIN-CH0003-API_raw.json"
)

EXPECTED_SOURCE_SHA256 = {
    GOLD_POINTER: "6a5c785dc98381ff4d9b7e207c599c29914f394e4b43e399d37f65093cc5a60c",
    FORMAL_GOLD: "0df08ede4fa1a33f4bd9e1aea3e45387c8d77131ce79ff1496fe1320fa48a10e",
    Z89_CATALOG: "2cc50e9a0c8b5fb807641e09c74f1748cbe423bf0fa700dbbbaa84ba20e58132",
    Z89_EVENTS: "97f39e145c7774e5204983d1639ccde1f4be13f42fc6eb6a6306de6b42e5948d",
    Z89_ADJUDICATION: "ddb35e13502fd21545b2cadf65cc38f7acd1b986be1f8d1b8ff9ba217a3f4d4e",
    Z89_SCORECARD: "edb78f2d1a6bc2320e73e4912516ec8821fe5323b36feb79df64aba11119290c",
    RETRY03_EVENTS: "295c7f19dc46bd3c56e984ec701d40dcb34a68eef0a20ec3474cfb5f723d150a",
    RETRY03_BUILD_RECEIPT: "47ee947900efd506d87d909a9c579af2c0239e122516c89436666ae733cdef57",
}

CONTRACT_FILES = (
    "rfu.schema.json",
    "candidate_claim.schema.json",
    "match_verdict.schema.json",
    "judge_eligibility.schema.json",
    "score_ticket.schema.json",
)

PROTECTED_PATHS = (
    "config/gold",
    FORMAL_GOLD,
    RETRY03_ROOT,
    Z89_ROOT,
    "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/"
    "02_verify/valid_records.json",
    "config/defaults/zbatch_v1.2_full_chain.COMMITTED.json",
    "config/defaults/zbatch_v1.2_full_chain.json",
    "config/contracts/classify_rules_v1.2_semantic_identity_v1.json",
    "outbox",
)


class Z97PipelineError(RuntimeError):
    """第97道来源、隔离、输出或保护闸不成立。"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(stable_json_bytes(value))
    os.replace(temporary, path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class SourceReader:
    """只允许按预登记 SHA 读取来源，拒绝被退件与中间件。"""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.sequence = 0

    def json(
        self,
        relative: str,
        *,
        zone: str,
        answer_derived: bool,
    ) -> Any:
        if relative == RETRY03_REJECTED_RAW:
            raise Z97PipelineError("retry03 截断响应已明确拒收，禁止捞回")
        expected = EXPECTED_SOURCE_SHA256.get(relative)
        if expected is None:
            raise Z97PipelineError(f"来源不在精确白名单：{relative}")
        path = REPO_ROOT / relative
        if path.is_symlink():
            raise Z97PipelineError(f"来源不得是符号链接：{relative}")
        actual = sha256_file(path)
        if actual != expected:
            raise Z97PipelineError(
                f"来源 SHA 漂移：{relative} expected={expected} actual={actual}"
            )
        self.sequence += 1
        self.rows.append(
            {
                "sequence": self.sequence,
                "zone": zone,
                "path": relative,
                "sha256": actual,
                "answer_derived": answer_derived,
            }
        )
        return json.loads(path.read_text(encoding="utf-8"))


def _tree_fingerprint(relative_paths: Sequence[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for relative in relative_paths:
        root = REPO_ROOT / relative
        if not root.exists() and not root.is_symlink():
            rows.append(
                {
                    "path": relative,
                    "kind": "missing",
                    "sha256": None,
                }
            )
            continue
        if root.is_symlink():
            rows.append(
                {
                    "path": relative,
                    "kind": "symlink",
                    "target": os.readlink(root),
                    "sha256": sha256_bytes(os.readlink(root).encode("utf-8")),
                }
            )
            continue
        if root.is_file():
            rows.append(
                {
                    "path": relative,
                    "kind": "file",
                    "sha256": sha256_file(root),
                }
            )
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            rows.append(
                {
                    "path": path.relative_to(REPO_ROOT).as_posix(),
                    "kind": "file",
                    "sha256": sha256_file(path),
                }
            )
    return {
        "item_count": len(rows),
        "tree_sha256": sha256_bytes(stable_json_bytes(rows)),
        "rows": rows,
    }


def _catalog_by_anchor(catalog: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(catalog, Mapping) or not isinstance(catalog.get("entries"), list):
        raise Z97PipelineError("冻结锚目录缺 entries")
    by_anchor: dict[str, dict[str, Any]] = {}
    for row in catalog["entries"]:
        if not isinstance(row, Mapping):
            raise Z97PipelineError("冻结锚目录含非对象条目")
        anchor_id = row.get("anchor_id")
        quote = row.get("quote")
        if (
            not isinstance(anchor_id, str)
            or not re_full_anchor(anchor_id)
            or not isinstance(quote, str)
            or not quote
            or anchor_id in by_anchor
        ):
            raise Z97PipelineError("冻结锚目录含非法、空或重复条目")
        by_anchor[anchor_id] = dict(row)
    return by_anchor


def re_full_anchor(value: str) -> bool:
    return len(value) == 5 and value.startswith("E") and value[1:].isdigit()


def _scoreable_gold_parts(gold: Any) -> list[dict[str, Any]]:
    if not isinstance(gold, Mapping) or gold.get("schema_version") != "structure-gold-v1.2":
        raise Z97PipelineError("正式金标不是 structure-gold-v1.2")
    layered_items = gold.get("layered_items")
    if not isinstance(layered_items, list):
        raise Z97PipelineError("正式金标缺 layered_items")
    parts = [
        dict(part)
        for item in layered_items
        for part in item.get("parts", [])
        if part.get("score_in_single_chapter") is True
    ]
    if len(parts) != 23:
        raise Z97PipelineError(f"正式金标计分原子不是 23：{len(parts)}")
    part_ids = [part.get("part_id") for part in parts]
    if any(not isinstance(part_id, str) or not part_id for part_id in part_ids):
        raise Z97PipelineError("正式金标计分原子缺 part_id")
    if len(part_ids) != len(set(part_ids)):
        raise Z97PipelineError("正式金标计分 part_id 重复")
    return parts


def build_rfu_ledger(
    gold: Any,
    catalog: Any,
    *,
    gold_sha256: str,
    catalog_sha256: str,
) -> dict[str, Any]:
    """把正式 23 原子机械转成候选 RFU，不补未审限定。"""

    catalog_rows = _catalog_by_anchor(catalog)
    rfus: list[dict[str, Any]] = []
    for source_order, part in enumerate(_scoreable_gold_parts(gold), start=1):
        part_id = str(part["part_id"])
        claim = part.get("claim")
        evidence = part.get("source_evidence")
        if not isinstance(claim, str) or not claim:
            raise Z97PipelineError(f"{part_id} 缺金标主张")
        if not isinstance(evidence, list) or not evidence:
            raise Z97PipelineError(f"{part_id} 缺正式源证据")
        source_anchor_ids: list[str] = []
        for source in evidence:
            if not isinstance(source, Mapping):
                raise Z97PipelineError(f"{part_id} 的 source_evidence 非对象")
            anchor_id = source.get("anchor_id")
            quote = source.get("quote")
            if anchor_id not in catalog_rows:
                raise Z97PipelineError(f"{part_id} 引用目录外锚 {anchor_id}")
            if quote != catalog_rows[anchor_id]["quote"]:
                raise Z97PipelineError(f"{part_id} 的 {anchor_id} 短引与目录不一致")
            source_anchor_ids.append(f"ch0003:{anchor_id}")
        rfu = {
            "schema_version": "rfu-v1",
            "reference_version": "X01-ch0003-gold-v1.2-rfu-provisional-v1",
            "chapter_id": "ch0003",
            "rfu_id": part_id,
            "source_order": source_order,
            "fact_head": {
                "subject_entity_ids": [],
                "predicate": claim,
                "object_entity_ids": [],
                "result": "",
                "polarity": "positive",
                "actuality": "occurred",
            },
            "required_qualifiers": QUALIFIER_OVERLAY.get(part_id, []),
            "optional_details": [
                {
                    "kind": "formal_gold_claim",
                    "text": claim,
                },
                {
                    "kind": "qualifier_inventory_scope",
                    "value": (
                        "只登记Z89冻结判词与八反例已明确的限定；"
                        "不是G-REG完整扩标"
                    ),
                },
            ],
            "minimal_support_sets": [
                {
                    "support_set_id": f"{part_id}-GOLD-SOURCE-FULL",
                    "anchor_ids": source_anchor_ids,
                    "minimality": "not_adjudicated",
                    "basis": "formal_gold_source_evidence_full_set",
                }
            ],
            "pathology_tags": [],
            "criticality": "normal",
            "weight": 1,
            "provenance": {
                "origin": "human_gold",
                "annotators": ["formal_gold_v1.2_existing_approval_chain"],
                "adjudicator": "formal_gold_registry",
                "source_sha256": gold_sha256,
                "anchor_catalog_sha256": catalog_sha256,
            },
            "score_unit_source": {
                "part_id": part_id,
                "part_role": part.get("part_role"),
                "layer": part.get("layer"),
            },
            "qualifier_inventory_status": "provisional_known_gaps_only",
        }
        rfus.append(validate_rfu(rfu))
    return {
        "schema_version": "rfu-ledger-v1",
        "status": "candidate_reference_fixture_not_formal_metric_release",
        "reference_version": "X01-ch0003-gold-v1.2-rfu-provisional-v1",
        "chapter_id": "ch0003",
        "rfu_count": len(rfus),
        "formal_gold_denominator_read_only": 23,
        "qualifier_inventory_status": "not_exhaustively_adjudicated",
        "rfus": rfus,
    }


def _event_anchors(event: Mapping[str, Any], chapter: int) -> list[str]:
    raw_anchors = event.get("anchors")
    if not isinstance(raw_anchors, list) or not raw_anchors:
        raise Z97PipelineError(f"{event.get('event_id')} 缺锚")
    anchors: list[str] = []
    for row in raw_anchors:
        if not isinstance(row, Mapping):
            raise Z97PipelineError("事件锚不是对象")
        anchor_id = row.get("anchor_id")
        if not isinstance(anchor_id, str) or not re_full_anchor(anchor_id):
            raise Z97PipelineError("事件含非法 anchor_id")
        if row.get("chapter") != chapter:
            raise Z97PipelineError("事件锚章号漂移")
        anchors.append(f"ch{chapter:04d}:{anchor_id}")
    return list(dict.fromkeys(anchors))


def build_raw_candidate_claims(
    events_payload: Any,
    *,
    chapter: int,
    candidate_output_sha256: str,
    parse_origin: str,
    candidate_universe_complete: bool,
) -> dict[str, Any]:
    """一条事件机械生成一个候选主张；不做语义拆分。"""

    if (
        not isinstance(events_payload, Mapping)
        or events_payload.get("chapter") != chapter
        or not isinstance(events_payload.get("events"), list)
    ):
        raise Z97PipelineError("候选事件文件章号或结构非法")
    claims: list[dict[str, Any]] = []
    for event in events_payload["events"]:
        if not isinstance(event, Mapping):
            raise Z97PipelineError("候选事件含非对象条目")
        event_id = event.get("event_id")
        event_text = event.get("event")
        if not isinstance(event_id, str) or not event_id:
            raise Z97PipelineError("候选事件缺 event_id")
        if not isinstance(event_text, str) or not event_text:
            raise Z97PipelineError(f"{event_id} 缺事件句")
        anchors = _event_anchors(event, chapter)
        claim_id = f"{event_id}::CLAIM-001"
        claim = {
            "schema_version": "candidate-claim-v1",
            "chapter_id": f"ch{chapter:04d}",
            "event_id": event_id,
            "claim_id": claim_id,
            "clause_index": 0,
            "event_text": event_text,
            "fact_head": {
                "subject_entity_ids": [],
                "predicate": event_text,
                "object_entity_ids": [],
                "result": "",
                "polarity": "positive",
                "actuality": "occurred",
            },
            "qualifiers": [],
            "claim_components": [
                {
                    "component_id": f"{claim_id}::COMP-001",
                    "text": event_text,
                    "anchor_ids": anchors,
                }
            ],
            "listed_anchor_ids": anchors,
            "is_addressable": True,
            "atomic_clause_count": 1,
            "parse_origin": parse_origin,
            "candidate_output_sha256": candidate_output_sha256,
            "source_event_ids": [event_id],
        }
        claims.append(validate_candidate_claim(claim))
    return {
        "schema_version": "candidate-claim-ledger-v1",
        "chapter_id": f"ch{chapter:04d}",
        "candidate_output_sha256": candidate_output_sha256,
        "candidate_universe_complete": candidate_universe_complete,
        "claim_count": len(claims),
        "claims": claims,
    }


def build_z89_adjudicated_groups(
    events_payload: Any,
    adjudication: Any,
    *,
    candidate_output_sha256: str,
) -> dict[str, Any]:
    """按 Z89 既有判词分组，不新增语义拆分或合并决定。"""

    raw = build_raw_candidate_claims(
        events_payload,
        chapter=3,
        candidate_output_sha256=candidate_output_sha256,
        parse_origin="z89_event_passthrough_v1",
        candidate_universe_complete=False,
    )
    event_by_id = {
        claim["event_id"]: claim
        for claim in raw["claims"]
    }
    gold_rows = adjudication.get("gold_rows") if isinstance(adjudication, Mapping) else None
    if not isinstance(gold_rows, list) or len(gold_rows) != 23:
        raise Z97PipelineError("Z89 冻结判词不是 23 行")
    groups: list[dict[str, Any]] = []
    for row in gold_rows:
        if not isinstance(row, Mapping):
            raise Z97PipelineError("Z89 判词含非对象行")
        part_id = row.get("part_id")
        source_event_ids = row.get("candidate_event_ids")
        if not isinstance(part_id, str) or not isinstance(source_event_ids, list):
            raise Z97PipelineError("Z89 判词缺 part_id 或 candidate_event_ids")
        source_claims: list[dict[str, Any]] = []
        for event_id in source_event_ids:
            if event_id not in event_by_id:
                raise Z97PipelineError(f"Z89 判词引用未知事件 {event_id}")
            source_claims.append(event_by_id[event_id])
        claim_id = f"Z89::{part_id}"
        components: list[dict[str, Any]] = []
        listed_anchor_ids: list[str] = []
        texts: list[str] = []
        for index, source_claim in enumerate(source_claims, start=1):
            texts.append(source_claim["event_text"])
            anchors = source_claim["listed_anchor_ids"]
            listed_anchor_ids.extend(anchors)
            components.append(
                {
                    "component_id": f"{claim_id}::COMP-{index:03d}",
                    "text": source_claim["event_text"],
                    "anchor_ids": anchors,
                }
            )
        event_text = " ｜ ".join(texts)
        group = {
            "schema_version": "candidate-claim-v1",
            "chapter_id": "ch0003",
            "event_id": f"Z89-ADJ-GROUP::{part_id}",
            "claim_id": claim_id,
            "clause_index": 0,
            "event_text": event_text,
            "fact_head": {
                "subject_entity_ids": [],
                "predicate": event_text,
                "object_entity_ids": [],
                "result": "",
                "polarity": "positive",
                "actuality": "occurred",
            },
            "qualifiers": [],
            "claim_components": components,
            "listed_anchor_ids": list(dict.fromkeys(listed_anchor_ids)),
            "is_addressable": True,
            "atomic_clause_count": len(source_claims),
            "parse_origin": "z89_frozen_adjudication_group_v1",
            "candidate_output_sha256": candidate_output_sha256,
            "source_event_ids": list(source_event_ids),
        }
        groups.append(validate_candidate_claim(group))
    return {
        "schema_version": "candidate-claim-ledger-v1",
        "chapter_id": "ch0003",
        "candidate_output_sha256": candidate_output_sha256,
        "candidate_universe_complete": False,
        "universe_note": "只含Z89按23条金标形成的历史判词组，不等于56条完整输出主张宇宙",
        "claim_count": len(groups),
        "claims": groups,
    }


def _z89_judge_config(adjudication: Mapping[str, Any]) -> str:
    review_method = adjudication.get("review_method")
    if not isinstance(review_method, Mapping):
        raise Z97PipelineError("Z89 判词缺 review_method")
    return sha256_bytes(stable_json_bytes(review_method))


def build_z89_match_verdicts(
    rfu_ledger: Mapping[str, Any],
    group_ledger: Mapping[str, Any],
    adjudication: Mapping[str, Any],
    *,
    adjudication_sha256: str,
) -> dict[str, Any]:
    """把 Z89 既有三档判词转为 MatchVerdict，不重判。"""

    rfu_by_id = {row["rfu_id"]: row for row in rfu_ledger["rfus"]}
    group_by_id = {row["claim_id"]: row for row in group_ledger["claims"]}
    judge_config_sha256 = _z89_judge_config(adjudication)
    verdicts: list[dict[str, Any]] = []
    for row in adjudication["gold_rows"]:
        part_id = row["part_id"]
        historical_verdict = row["verdict"]
        claim_id = f"Z89::{part_id}"
        if part_id not in rfu_by_id or claim_id not in group_by_id:
            raise Z97PipelineError("Z89 判词无法对齐 RFU 或候选组")
        if historical_verdict == "strict_hit":
            head_match = "yes"
            anchor_status = "supported"
        elif historical_verdict == "semantic_shadow":
            head_match = "partial"
            anchor_status = "supported"
        elif historical_verdict == "coverage_only_invalid_support":
            head_match = "yes"
            anchor_status = "unsupported"
        else:
            raise Z97PipelineError(f"未知 Z89 判词：{historical_verdict}")
        expected_qualifier_ids = {
            qualifier["qualifier_id"]
            for qualifier in rfu_by_id[part_id]["required_qualifiers"]
        }
        frozen_qualifier_status = Z89_QUALIFIER_STATUS.get(part_id, {})
        if set(frozen_qualifier_status) != expected_qualifier_ids:
            raise Z97PipelineError(
                f"{part_id} 的限定没有逐项冻结状态，禁止默认填 present"
            )
        qualifier_results = [
            {
                "qualifier_id": qualifier["qualifier_id"],
                "status": frozen_qualifier_status[qualifier["qualifier_id"]],
            }
            for qualifier in rfu_by_id[part_id]["required_qualifiers"]
        ]
        claim = group_by_id[claim_id]
        frozen_reason = str(row["reason"])
        verdict = {
            "schema_version": "match-verdict-v1",
            "rfu_id": part_id,
            "claim_id": claim_id,
            "head_match": head_match,
            "reason_codes": Z89_REASON_CODES[part_id],
            "qualifier_results": qualifier_results,
            "anchor_component_results": [
                {
                    "component_id": component["component_id"],
                    "status": anchor_status,
                }
                for component in claim["claim_components"]
            ],
            "atomicity": (
                "merged_unaddressable"
                if "压在一条" in frozen_reason
                else (
                    "mechanically_splittable"
                    if len(claim["source_event_ids"]) > 1
                    else "atomic"
                )
            ),
            "confidence": 1.0,
            "judge_id": "z89_completed_local_semantic_review",
            "judge_config_sha256": judge_config_sha256,
            "candidate_arm": "z89_deepseek_v4_pro_single_sample",
            "human_review_required": False,
            "frozen_reason": frozen_reason,
            "adjudication_source_sha256": adjudication_sha256,
        }
        verdicts.append(validate_match_verdict(verdict))
    return {
        "schema_version": "match-verdict-ledger-v1",
        "status": "historical_frozen_verdicts_transcoded_not_rejudged",
        "verdict_count": len(verdicts),
        "adjudication_source_sha256": adjudication_sha256,
        "verdicts": verdicts,
    }


def _z89_judge_eligibility() -> dict[str, Any]:
    return {
        "schema_version": "judge-eligibility-v1",
        "candidate_provider": "deepseek-official-historical-z89",
        "candidate_family": "deepseek-v4-pro",
        "candidate_checkpoint": "deepseek-v4-pro-historical-z89",
        "candidate_training_lineage": "unknown",
        "judge_kind": "human_team_historical_semantic_review",
        "judge_provider": "local",
        "judge_family": "codex_luna_terra_sol",
        "judge_checkpoint": "z89_completed_review",
        "judge_training_lineage": "not_applicable",
        "same_family": False,
        "same_checkpoint": False,
        "judge_trained_on_scored_outputs": False,
        "candidate_identity_visible": True,
        "historical_scores_visible": True,
        "repair_logs_visible": False,
        "eligible": False,
        "main_judge": "human_required_for_any_formal_release",
        "reasons": [
            "Z89判词不是密封盲审",
            "候选身份与历史成绩对评审可见",
            "只准做历史离线演示",
        ],
    }


def _retry03_accounting_ticket(
    candidate_claims: Mapping[str, Any],
    build_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    if build_receipt.get("semantic_truth_pending") is not True:
        raise Z97PipelineError("retry03 语义待判边界与封存票不一致")
    return {
        "schema_version": "rfu-accounting-only-ticket-v1",
        "status": "not_computable_without_frozen_match_verdicts",
        "chapter_id": "ch0003",
        "candidate_claim_count": candidate_claims["claim_count"],
        "match_verdict_count": 0,
        "metrics": {
            "FCR": None,
            "QCR_full": None,
            "ASR_full": None,
            "UCR": None,
            "SOP": None,
        },
        "reason": "retry03检查员未完成，semantic_truth_pending=true；不得把未判当0分",
        "semantic_rejudgments": 0,
        "historical_scores_mutated": False,
        "rejected_raw_used": False,
    }


def _contract_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in CONTRACT_FILES:
        path = PACKAGE_ROOT / "contracts" / name
        json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_file(path),
            }
        )
    return rows


def _validate_emitted_contracts(
    rfu_ledger: Mapping[str, Any],
    claim_ledgers: Sequence[Mapping[str, Any]],
    verdict_ledger: Mapping[str, Any],
    eligibility: Mapping[str, Any],
    score_ticket: Mapping[str, Any],
) -> dict[str, Any]:
    """用代码合同逐份验产物，并核对严格 schema 的字段集合。"""

    rfu_count = sum(1 for row in rfu_ledger["rfus"] if validate_rfu(row))
    claim_count = sum(
        1
        for ledger in claim_ledgers
        for row in ledger["claims"]
        if validate_candidate_claim(row)
    )
    verdict_count = sum(
        1
        for row in verdict_ledger["verdicts"]
        if validate_match_verdict(row)
    )
    validate_judge_eligibility(eligibility)
    match_schema = read_json(PACKAGE_ROOT / "contracts" / "match_verdict.schema.json")
    judge_schema = read_json(PACKAGE_ROOT / "contracts" / "judge_eligibility.schema.json")
    score_schema = read_json(PACKAGE_ROOT / "contracts" / "score_ticket.schema.json")
    if set(match_schema["properties"]) != set(MATCH_VERDICT_FIELDS):
        raise Z97PipelineError("MatchVerdict schema 与代码字段集合漂移")
    if set(judge_schema["properties"]) != set(JUDGE_ELIGIBILITY_FIELDS):
        raise Z97PipelineError("裁判资格 schema 与代码字段集合漂移")
    if match_schema.get("additionalProperties") is not False:
        raise Z97PipelineError("MatchVerdict schema 必须拒绝额外字段")
    if judge_schema.get("additionalProperties") is not False:
        raise Z97PipelineError("裁判资格 schema 必须拒绝额外字段")
    if set(score_ticket) != set(score_schema["properties"]):
        raise Z97PipelineError("成绩票 schema 与实际顶层字段漂移")
    return {
        "schema_version": "z97-contract-validation-receipt-v1",
        "status": "PASS",
        "rfu_validated": rfu_count,
        "candidate_claims_validated": claim_count,
        "match_verdicts_validated": verdict_count,
        "judge_eligibility_validated": 1,
        "strict_schema_field_sets_aligned": True,
    }


def _tree_manifest(root: Path, *, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude or set()
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def _bundle_report_markdown(
    z89_ticket: Mapping[str, Any],
    retry03_ticket: Mapping[str, Any],
    canary_receipt: Mapping[str, Any],
) -> str:
    metrics = z89_ticket["metrics"]
    lines = [
        "# 第97道停点回包｜RFU 建账＋UCR 五层候选",
        "",
        "✅ 工程交件已完成：RFU／CandidateClaim／MatchVerdict／成绩票五份合同落地，",
        "三区分开；程序只算账，不生成语义判词，也没有接现役运行器。",
        "",
        "## 调用与边界",
        "",
        "- 模型 API 调用：0",
        "- 网络尝试：0",
        "- retry03 语义重判：0",
        "- 正式金标、历史成绩、现役 122 条、默认链、分类规则、outbox：均未改",
        "",
        "## 第3章试建账",
        "",
        "- 正式金标 v1.2：23 个计分原子机械转成候选 RFU",
        "- qualifier 清单只登记 Z89 既有判词与八反例已经明确的缺口，",
        "  尚不是 G-REG 完整扩标",
        f"- retry03：{retry03_ticket['candidate_claim_count']} 条候选主张已建账；",
        "  因无完成语义判词，五个读数全部保持“不可计分”，没有填成 0",
        "- Z89：只复用 23 行已封存历史判词做离线演示；不是密封盲审，",
        "  裁判资格表明确不具正式发布资格",
        "",
        "## Z89 离线演示的新列",
        "",
        f"- FCR：{metrics['FCR']['numerator']}/{metrics['FCR']['denominator']}",
        (
            "- QCR_full："
            f"{metrics['QCR_full']['numerator']}/"
            f"{metrics['QCR_full']['denominator']}"
        ),
        (
            "- ASR_full："
            f"{metrics['ASR_full']['numerator']}/"
            f"{metrics['ASR_full']['denominator']}"
        ),
        f"- UCR：{metrics['UCR']['numerator']}/{metrics['UCR']['denominator']}",
        (
            "- SOP："
            f"{metrics['SOP']['numerator']}/{metrics['SOP']['denominator']}；"
            "候选主张宇宙不完整，0.98 发布线不得判"
        ),
        "",
        "这些是并排新增的诊断列，旧 Z89 严格／有效／表面覆盖成绩只读照录，",
        "没有追改，也不能据此换主尺。",
        "",
        "## 回归与停点",
        "",
        f"- 八个 CANARY：{canary_receipt['case_count']}/8 PASS",
        "- 机械双跑：连续两次字节一致",
        "- MRP-72：未执行、未放行",
        "- 当前停点：工程候选可审；质量胜负不登记，人工扩标与正式换尺另拍",
        "",
        "来源：Codex",
        "",
    ]
    return "\n".join(lines)


def build_bundle(bundle_root: Path) -> dict[str, Any]:
    """在空目录内构建一份确定性 run/report 包。"""

    if bundle_root.exists():
        if any(bundle_root.iterdir()):
            raise Z97PipelineError("bundle_root 必须为空")
    else:
        bundle_root.mkdir(parents=True)
    run_root = bundle_root / "run"
    report_root = bundle_root / "report"
    run_root.mkdir()
    report_root.mkdir()

    protection_before = _tree_fingerprint(PROTECTED_PATHS)
    reader = SourceReader()
    pointer = reader.json(GOLD_POINTER, zone="J-REF", answer_derived=True)
    active_gold = pointer.get("active_gold") if isinstance(pointer, Mapping) else None
    if (
        not isinstance(active_gold, Mapping)
        or active_gold.get("path") != FORMAL_GOLD
        or active_gold.get("sha256") != EXPECTED_SOURCE_SHA256[FORMAL_GOLD]
        or active_gold.get("formal_denominator") != 23
    ):
        raise Z97PipelineError("现役金标指针未钉住 v1.2／23 分母")
    gold = reader.json(FORMAL_GOLD, zone="J-REF", answer_derived=True)
    catalog = reader.json(Z89_CATALOG, zone="J-REF", answer_derived=False)
    rfu_ledger = build_rfu_ledger(
        gold,
        catalog,
        gold_sha256=EXPECTED_SOURCE_SHA256[FORMAL_GOLD],
        catalog_sha256=EXPECTED_SOURCE_SHA256[Z89_CATALOG],
    )
    write_json(run_root / "J-REF" / "rfu_ledger.json", rfu_ledger)

    z89_events = reader.json(Z89_EVENTS, zone="J-MATCH", answer_derived=False)
    z89_adjudication = reader.json(
        Z89_ADJUDICATION,
        zone="J-MATCH",
        answer_derived=True,
    )
    z89_scorecard = reader.json(
        Z89_SCORECARD,
        zone="SCORE-LEGACY-READONLY",
        answer_derived=True,
    )
    z89_raw_claims = build_raw_candidate_claims(
        z89_events,
        chapter=3,
        candidate_output_sha256=EXPECTED_SOURCE_SHA256[Z89_EVENTS],
        parse_origin="z89_event_passthrough_v1",
        candidate_universe_complete=False,
    )
    z89_groups = build_z89_adjudicated_groups(
        z89_events,
        z89_adjudication,
        candidate_output_sha256=EXPECTED_SOURCE_SHA256[Z89_EVENTS],
    )
    z89_verdicts = build_z89_match_verdicts(
        rfu_ledger,
        z89_groups,
        z89_adjudication,
        adjudication_sha256=EXPECTED_SOURCE_SHA256[Z89_ADJUDICATION],
    )
    eligibility = _z89_judge_eligibility()
    z89_ticket = compute_score_ticket(
        rfu_ledger["rfus"],
        z89_groups["claims"],
        z89_verdicts["verdicts"],
        judge_eligibility=eligibility,
        candidate_universe_complete=False,
        legacy_metrics_read_only={
            "source_path": Z89_SCORECARD,
            "source_sha256": EXPECTED_SOURCE_SHA256[Z89_SCORECARD],
            "gold_chapter_3": z89_scorecard["gold_chapter_3"],
        },
        ticket_id="Z97-Z89-HISTORICAL-DEMO",
    )
    write_json(
        run_root / "J-MATCH" / "z89_candidate_claims_raw.json",
        z89_raw_claims,
    )
    write_json(
        run_root / "J-MATCH" / "z89_adjudicated_claim_groups.json",
        z89_groups,
    )
    write_json(
        run_root / "J-MATCH" / "z89_match_verdicts.json",
        z89_verdicts,
    )
    write_json(
        run_root / "J-MATCH" / "judge_eligibility.json",
        eligibility,
    )
    write_json(run_root / "SCORE" / "z89_score_ticket.json", z89_ticket)

    retry03_events = reader.json(
        RETRY03_EVENTS,
        zone="J-MATCH",
        answer_derived=False,
    )
    retry03_build_receipt = reader.json(
        RETRY03_BUILD_RECEIPT,
        zone="J-MATCH",
        answer_derived=True,
    )
    retry03_claims = build_raw_candidate_claims(
        retry03_events,
        chapter=3,
        candidate_output_sha256=EXPECTED_SOURCE_SHA256[RETRY03_EVENTS],
        parse_origin="retry03_event_passthrough_no_semantic_truth",
        candidate_universe_complete=False,
    )
    retry03_ticket = _retry03_accounting_ticket(
        retry03_claims,
        retry03_build_receipt,
    )
    contract_validation = _validate_emitted_contracts(
        rfu_ledger,
        [z89_raw_claims, z89_groups, retry03_claims],
        z89_verdicts,
        eligibility,
        z89_ticket,
    )
    write_json(
        run_root / "J-MATCH" / "retry03_candidate_claims.json",
        retry03_claims,
    )
    write_json(
        run_root / "SCORE" / "retry03_accounting_only_ticket.json",
        retry03_ticket,
    )
    write_json(
        run_root / "audit" / "contract_validation_receipt.json",
        contract_validation,
    )

    canary_suite = build_canary_suite()
    canary_receipt = evaluate_canary_suite(canary_suite)
    write_json(run_root / "CANARY" / "canary_suite.json", canary_suite)
    write_json(run_root / "CANARY" / "canary_receipt.json", canary_receipt)

    contract_manifest = _contract_manifest()
    source_seal = {
        "schema_version": "z97-source-seal-v1",
        "authority_time": AUTHORITY_TIME,
        "allowlisted_sources": [
            {
                "path": path,
                "sha256": sha256,
            }
            for path, sha256 in EXPECTED_SOURCE_SHA256.items()
        ],
        "forbidden_sources": [
            {
                "path": RETRY03_REJECTED_RAW,
                "reason": "finish_reason=length截断响应，禁止局部捞回",
            }
        ],
        "forbidden_source_used_count": 0,
        "contract_files": contract_manifest,
        "access_ledger": reader.rows,
        "zone_rule": {
            "J-REF": "只建参考事实单元",
            "J-MATCH": "只建候选主张并转录冻结人工判词",
            "SCORE": "只读三区冻结件机械计分，不回看正文补判",
        },
    }
    write_json(run_root / "audit" / "source_seal.json", source_seal)
    protection_after = _tree_fingerprint(PROTECTED_PATHS)
    if protection_before["tree_sha256"] != protection_after["tree_sha256"]:
        raise Z97PipelineError("保护面在构建期间发生漂移")
    protection_receipt = {
        "schema_version": "z97-protection-receipt-v1",
        "status": "PASS",
        "before": {
            "item_count": protection_before["item_count"],
            "tree_sha256": protection_before["tree_sha256"],
        },
        "after": {
            "item_count": protection_after["item_count"],
            "tree_sha256": protection_after["tree_sha256"],
        },
        "formal_gold_or_pointer_changed": False,
        "historical_scores_mutated": False,
        "candidate_connected_to_runner": False,
        "model_api_calls": 0,
        "network_attempts": 0,
    }
    write_json(run_root / "audit" / "protection_receipt.json", protection_receipt)

    validation_summary = {
        "schema_version": "z97-validation-summary-v1",
        "status": "PASS_ENGINEERING_CANDIDATE_QUALITY_UNJUDGED",
        "rfu_count": rfu_ledger["rfu_count"],
        "z89_raw_claim_count": z89_raw_claims["claim_count"],
        "z89_adjudicated_group_count": z89_groups["claim_count"],
        "z89_frozen_verdict_count": z89_verdicts["verdict_count"],
        "retry03_claim_count": retry03_claims["claim_count"],
        "retry03_frozen_verdict_count": 0,
        "retry03_metrics_computed": False,
        "canary_passed": canary_receipt["case_count"],
        "canary_total": 8,
        "candidate_connected_to_runner": False,
        "strict_metric_mutated": False,
        "mrp_72_release_gate_passed": False,
        "formal_quality_winner_registered": False,
    }
    write_json(run_root / "audit" / "validation_summary.json", validation_summary)
    run_manifest_rows = _tree_manifest(
        run_root,
        exclude={"run_manifest.json"},
    )
    write_json(
        run_root / "run_manifest.json",
        {
            "schema_version": "z97-run-manifest-v1",
            "run_id": "Z97-RFU-UCR-LEDGER-v1.0",
            "status": "candidate_engineering_complete_quality_unjudged",
            "authority_time": AUTHORITY_TIME,
            "files": run_manifest_rows,
            "files_manifest_sha256": sha256_bytes(
                stable_json_bytes(run_manifest_rows)
            ),
            "usage": {
                "model_api_logical_samples": 0,
                "model_api_network_attempts": 0,
                "model_api_usage_tokens": 0,
            },
        },
    )

    write_json(
        report_root / "RFU候选账本.json",
        rfu_ledger,
    )
    write_json(
        report_root / "UCR五层_Z89只读演示成绩单.json",
        z89_ticket,
    )
    write_json(
        report_root / "retry03不可计分说明票.json",
        retry03_ticket,
    )
    write_json(
        report_root / "CANARY八案回归票.json",
        canary_receipt,
    )
    write_json(
        report_root / "三区隔离与裁判资格表.json",
        {
            "schema_version": "z97-zone-and-judge-register-v1",
            "zones": source_seal["zone_rule"],
            "source_access_ledger": reader.rows,
            "z89": eligibility,
            "retry03": {
                "eligible": False,
                "main_judge": "human_required",
                "reason": "没有完成冻结MatchVerdict，程序不得补判",
            },
        },
    )
    write_text(
        report_root / "第97道停点回包.md",
        _bundle_report_markdown(
            z89_ticket,
            retry03_ticket,
            canary_receipt,
        ),
    )
    report_manifest_rows = _tree_manifest(
        report_root,
        exclude={"artifact_manifest.json", "机械双跑票.json"},
    )
    write_json(
        report_root / "artifact_manifest.json",
        {
            "schema_version": "z97-report-artifact-manifest-v1",
            "self_and_double_run_ticket_excluded": True,
            "files": report_manifest_rows,
            "files_manifest_sha256": sha256_bytes(
                stable_json_bytes(report_manifest_rows)
            ),
        },
    )
    return {
        "run_file_count": len(_tree_manifest(run_root)),
        "report_file_count": len(_tree_manifest(report_root)),
        "protection_sha256": protection_before["tree_sha256"],
    }


def _compare_bundle_trees(left: Path, right: Path) -> dict[str, Any]:
    left_rows = _tree_manifest(left)
    right_rows = _tree_manifest(right)
    if left_rows != right_rows:
        raise Z97PipelineError("两次机械构建的路径、字节或 SHA 不一致")
    return {
        "file_count": len(left_rows),
        "tree_sha256": sha256_bytes(stable_json_bytes(left_rows)),
    }


def _authorized_output_path(relative: str, parent_name: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    expected_parent = (REPO_ROOT / parent_name).resolve()
    if path.parent != expected_parent:
        raise Z97PipelineError(f"输出必须直接位于 {parent_name}/ 下")
    if path.exists():
        raise Z97PipelineError(f"运行目录已存在，拒绝覆盖：{relative}")
    return path


def execute_double_run(
    *,
    run_directory: str = AUTHORIZED_RUN_DIRECTORY,
    report_directory: str = AUTHORIZED_REPORT_DIRECTORY,
) -> dict[str, Any]:
    """双跑一致后才把候选工件复制到正式本地停点目录。"""

    if run_directory != AUTHORIZED_RUN_DIRECTORY:
        raise Z97PipelineError("只允许第97道已批准运行目录")
    if report_directory != AUTHORIZED_REPORT_DIRECTORY:
        raise Z97PipelineError("只允许第97道已批准报告目录")
    run_path = _authorized_output_path(run_directory, "runs")
    report_path = _authorized_output_path(report_directory, "reports")
    temp_parent = REPO_ROOT / "TEMP"
    temp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="z97_rfu_ucr_double_run_",
        dir=temp_parent,
    ) as temporary:
        temporary_root = Path(temporary)
        left = temporary_root / "A"
        right = temporary_root / "B"
        build_bundle(left)
        build_bundle(right)
        pre_ticket = _compare_bundle_trees(left, right)
        double_run_ticket = {
            "schema_version": "z97-double-run-ticket-v1",
            "status": "PASS",
            "run_count": 2,
            "pre_ticket_file_count": pre_ticket["file_count"],
            "pre_ticket_tree_sha256": pre_ticket["tree_sha256"],
            "byte_identical": True,
            "official_copy_verification_required": True,
            "official_copy_verification": "PASS_BY_EXECUTOR_OR_HARD_STOP",
        }
        write_json(left / "report" / "机械双跑票.json", double_run_ticket)
        write_json(right / "report" / "机械双跑票.json", double_run_ticket)
        final_compare = _compare_bundle_trees(left, right)
        shutil.copytree(left / "run", run_path)
        shutil.copytree(left / "report", report_path)
        official_run_compare = _compare_bundle_trees(left / "run", run_path)
        official_report_compare = _compare_bundle_trees(
            left / "report",
            report_path,
        )
    return {
        "status": "PASS",
        "run_directory": run_directory,
        "report_directory": report_directory,
        "double_run_file_count": final_compare["file_count"],
        "double_run_tree_sha256": final_compare["tree_sha256"],
        "official_run_copy_sha256": official_run_compare["tree_sha256"],
        "official_report_copy_sha256": official_report_compare["tree_sha256"],
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="第97道 RFU 建账与 UCR 五层候选双跑生成器"
    )
    parser.add_argument(
        "--run-directory",
        default=AUTHORIZED_RUN_DIRECTORY,
    )
    parser.add_argument(
        "--report-directory",
        default=AUTHORIZED_REPORT_DIRECTORY,
    )
    args = parser.parse_args()
    receipt = execute_double_run(
        run_directory=args.run_directory,
        report_directory=args.report_directory,
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import event_graph_planner as a8_graph
from . import r2_dev_hardening as hardening


ROUTE_OUTPUT_SCHEMA = "v02-r2-route-output.v1"
ROUTE_MANIFEST_SCHEMA = "v02-r2-dev-route-manifest.v2"
PLANNER_VISIBLE_SOURCE_SCHEMA = "r2-planner-visible-source.v1"
OBLIGATION_PLAN_SCHEMA = "r2-obligation-plan.v1"
QUERY_MAP_SCHEMA = "r2-query-map.v1"
SELECTION_PROJECTION_SCHEMA = "r2-selection-projection.v1"
BUDGETS = (300, 600, 900, 1200, 1500, 2000, 2500)
ROUTES = ("A0", "A1a", "A1b", "A1c", "A3", "A4")
SUPPORTED_ROUTES = (*ROUTES, "A4h", "A5", "A6", "A7", "A8")
CASE_IDS = ("B01-U0033", "B02-U0039", "B03-U0041")
FORBIDDEN_INPUT_PARTS = {"gold", "lockbox", "scoring_lockbox"}
PLAN_SPLIT_PATTERN = re.compile(r"[，,；;？?]|以及|或者|或|、")
ALIAS_PATTERN = re.compile(
    r"(?P<left>[\u4e00-\u9fff]{2,8})(?:又名|改名为|人称|号称)"
    r"(?P<right>[\u4e00-\u9fff]{2,8})"
)
NEIGHBOR_TRIGGERS = (
    "因为",
    "所以",
    "因此",
    "导致",
    "于是",
    "但是",
    "然而",
    "他",
    "她",
    "它",
    "这",
    "那",
    "其",
    "听说",
    "认为",
    "猜测",
)
GENERIC_CUE_LEXICON = {
    "state": (
        ("状态", "当前", "变化"),
        ("受伤", "清醒", "昏迷", "死亡", "活着", "离开", "到达", "位置"),
    ),
    "knowledge": (
        ("知道", "得知", "发现", "相信", "误信", "猜测", "听说"),
        ("得知", "发现", "认为", "误以为", "听见", "看见", "怀疑"),
    ),
    "goal": (
        ("目标", "计划", "承诺", "威胁"),
        ("决定", "准备", "打算", "必须", "答应", "要求", "警告"),
    ),
    "relation": (
        ("关系", "身份", "归属"),
        ("成为", "认出", "身份", "主人", "属于", "关系"),
    ),
    "resource": (
        ("资源", "物品", "位置", "能力"),
        ("得到", "失去", "交给", "带走", "移动", "能力", "位置"),
    ),
    "unresolved": (
        ("未决", "风险", "伏笔"),
        ("仍然", "尚未", "危险", "疑问", "秘密", "等待", "继续"),
    ),
    "cause": (
        ("因果", "触发", "结果"),
        ("因为", "所以", "因此", "导致", "于是", "结果"),
    ),
    "modality": (
        ("相信", "猜测", "听说", "确认"),
        ("认为", "猜测", "听说", "据说", "可能", "似乎", "确认"),
    ),
}

# 只把抽象作者问题翻译成正文里可观察的叙事动作词。
# 这里不含书名、人物名、题号、答案实体、来源 ID 或章内位置。
OBSERVABLE_NARRATIVE_BRIDGE = {
    "location_or_condition": (
        ("在哪里", "什么状态", "当前"),
        (
            "回到",
            "来到",
            "走进",
            "离开",
            "住在",
            "留在",
            "坐在",
            "站在",
            "躺在",
            "搬到",
            "赶到",
        ),
    ),
    "state_change": (
        ("状态变化", "发生了哪些", "影响后续", "变化"),
        (
            "开始",
            "变成",
            "改为",
            "不再",
            "已经",
            "终于",
            "恢复",
            "失去",
            "得到",
            "离开",
            "进入",
            "留下",
            "赶走",
            "收走",
            "送给",
            "卖掉",
            "搬去",
        ),
    ),
    "knowledge_change": (
        ("新知道", "不知道", "误信", "相信", "知情"),
        (
            "问道",
            "答道",
            "说道",
            "告诉",
            "听见",
            "看见",
            "明白",
            "知道",
            "发现",
            "猜测",
            "怀疑",
            "承认",
            "坦白",
            "隐瞒",
            "骗过",
            "误以为",
        ),
    ),
    "goal_or_commitment": (
        ("计划", "目标", "承诺", "威胁", "要求"),
        (
            "准备",
            "决定",
            "答应",
            "要求",
            "命令",
            "吩咐",
            "警告",
            "威胁",
            "保证",
            "约定",
            "打算",
            "计划",
        ),
    ),
    "identity_relation_ownership": (
        ("关系", "身份", "归属", "物品", "资源", "能力"),
        (
            "成为",
            "认出",
            "认作",
            "属于",
            "送给",
            "给了",
            "收下",
            "带走",
            "改名",
            "称为",
            "身份",
            "关系",
        ),
    ),
    "unresolved_or_causal": (
        ("未决", "风险", "伏笔", "因果", "触发", "结果"),
        (
            "还没",
            "尚未",
            "仍然",
            "继续",
            "等待",
            "担心",
            "秘密",
            "不知",
            "下落",
            "以后",
            "只因",
            "为了",
            "结果",
            "以致",
            "才会",
            "于是",
        ),
    ),
}

# A7 只用通用题型和正文可见词面提出“候选事实义务”。
# 这些词不包含书名、人物名、题号、答案实体、来源编号或章内位置。
FACT_OBLIGATION_ONTOLOGY = (
    {
        "ontology_id": "ONT-LOCATION-STATE",
        "question_triggers": ("在哪里", "什么状态", "当前"),
        "fact_types": ("LOCATION", "STATE"),
        "markers": (
            "回到",
            "来到",
            "走进",
            "离开",
            "住在",
            "留在",
            "坐在",
            "站在",
            "躺在",
            "清醒",
            "昏迷",
            "受伤",
            "活着",
        ),
    },
    {
        "ontology_id": "ONT-STATE-CHANGE",
        "question_triggers": ("状态变化", "影响后续", "发生了哪些"),
        "fact_types": ("STATE_CHANGE",),
        "markers": (
            "开始",
            "变成",
            "改为",
            "不再",
            "已经",
            "终于",
            "恢复",
            "失去",
            "得到",
            "离开",
            "进入",
            "留下",
            "赶走",
            "收走",
            "送给",
            "卖掉",
            "搬去",
        ),
    },
    {
        "ontology_id": "ONT-KNOWLEDGE-GAIN",
        "question_triggers": ("新知道", "得知", "知道了什么"),
        "fact_types": ("KNOWLEDGE_GAIN",),
        "markers": (
            "知道",
            "得知",
            "发现",
            "明白",
            "听见",
            "看见",
            "告诉",
            "坦白",
            "承认",
        ),
    },
    {
        "ontology_id": "ONT-EPISTEMIC-UNCERTAIN",
        "question_triggers": (
            "仍不知道",
            "误信",
            "相信",
            "猜测",
            "听说",
            "不是已确认",
        ),
        "fact_types": ("EPISTEMIC_UNCONFIRMED",),
        "markers": (
            "不知道",
            "不知",
            "误以为",
            "以为",
            "认为",
            "猜",
            "怀疑",
            "听说",
            "据说",
            "可能",
            "似乎",
        ),
    },
    {
        "ontology_id": "ONT-INTENT-COMMITMENT",
        "question_triggers": ("目标", "计划", "承诺", "威胁"),
        "fact_types": ("INTENT", "PLAN", "COMMITMENT", "THREAT"),
        "markers": (
            "准备",
            "决定",
            "打算",
            "计划",
            "答应",
            "要求",
            "命令",
            "吩咐",
            "警告",
            "威胁",
            "保证",
            "约定",
            "一定",
            "必须",
            "不再",
            "绝不",
            "以后",
            "将来",
        ),
    },
    {
        "ontology_id": "ONT-IDENTITY-RELATION",
        "question_triggers": ("关系", "身份", "归属"),
        "fact_types": ("RELATION_CHANGE", "IDENTITY_CHANGE", "OWNERSHIP_CHANGE"),
        "markers": (
            "成为",
            "认出",
            "认作",
            "改名",
            "称为",
            "属于",
            "主人",
            "身份",
            "关系",
            "嫁给",
            "娶",
            "收为",
        ),
    },
    {
        "ontology_id": "ONT-TRANSFER-ABILITY",
        "question_triggers": ("资源", "物品", "位置", "能力", "转移"),
        "fact_types": ("TRANSFER", "LOCATION_CHANGE", "ABILITY_CHANGE"),
        "markers": (
            "给",
            "送",
            "拿",
            "带走",
            "收下",
            "失去",
            "得到",
            "交给",
            "收走",
            "卖",
            "买",
            "搬",
            "离开",
            "来到",
            "能力",
        ),
    },
    {
        "ontology_id": "ONT-UNRESOLVED",
        "question_triggers": ("未决", "风险", "伏笔", "继续处理"),
        "fact_types": ("UNRESOLVED", "RISK", "FORESHADOW"),
        "markers": (
            "还没",
            "尚未",
            "仍然",
            "继续",
            "等待",
            "担心",
            "秘密",
            "下落",
            "不知",
            "以后",
            "将来",
            "危险",
        ),
    },
    {
        "ontology_id": "ONT-CAUSAL",
        "question_triggers": ("因果", "触发", "结果"),
        "fact_types": ("CAUSE", "RESULT"),
        "markers": (
            "因为",
            "所以",
            "因此",
            "于是",
            "导致",
            "才",
            "只因",
            "为了",
            "结果",
            "以致",
        ),
    },
)


class RouteRunnerError(ValueError):
    """R2 离线开发路线运行器拒收错误。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def _reject_forbidden_input_path(path: Path) -> None:
    lowered = {part.lower() for part in path.parts}
    if lowered & FORBIDDEN_INPUT_PARTS:
        raise RouteRunnerError(f"FORBIDDEN_ROUTE_INPUT_PATH:{path}")


def _load_questions(path: Path) -> list[dict[str, str]]:
    _reject_forbidden_input_path(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    allowed_top = {
        "schema_version",
        "scope",
        "question_count_per_chapter",
        "scored_cell_total",
        "questions",
        "model_visible",
        "frozen_before_send",
        "question_set_sha256",
    }
    if set(value) != allowed_top:
        raise RouteRunnerError("QUESTION_SET_FIELDS_INVALID")
    payload_without_hash = {
        key: item for key, item in value.items() if key != "question_set_sha256"
    }
    expected_question_set_sha256 = hashlib.sha256(
        json.dumps(
            payload_without_hash,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if value["question_set_sha256"] != expected_question_set_sha256:
        raise RouteRunnerError("QUESTION_SET_SHA_MISMATCH")
    questions = value["questions"]
    if not isinstance(questions, list) or len(questions) != 10:
        raise RouteRunnerError("QUESTION_SET_COUNT_INVALID")
    projected: list[dict[str, str]] = []
    for row in questions:
        if set(row) != {"question_id", "question_text", "answer_rule"}:
            raise RouteRunnerError("QUESTION_FIELDS_INVALID")
        projected.append(
            {
                "question_id": row["question_id"],
                "question_text": row["question_text"],
            }
        )
    return projected


def _load_catalogs(catalog_dir: Path) -> list[dict[str, Any]]:
    _reject_forbidden_input_path(catalog_dir)
    paths = sorted(catalog_dir.glob("*.json"))
    catalogs = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if [row.get("source_id") for row in catalogs] != list(CASE_IDS):
        raise RouteRunnerError("SOURCE_CATALOG_CASE_SET_INVALID")
    for path, catalog in zip(paths, catalogs, strict=True):
        if sha256_bytes(catalog["source_text"].encode("utf-8")) != catalog.get(
            "source_body_sha256"
        ):
            raise RouteRunnerError(f"SOURCE_BODY_SHA_MISMATCH:{path.name}")
        rebuilt = "".join(row["original_text"] for row in catalog["paragraphs"])
        if rebuilt != catalog["source_text"]:
            raise RouteRunnerError(f"SOURCE_PARAGRAPH_REBUILD_MISMATCH:{path.name}")
        payload_without_hash = dict(catalog)
        actual_payload_sha256 = payload_without_hash.pop(
            "catalog_payload_sha256",
            None,
        )
        expected_payload_sha256 = sha256_bytes(
            canonical_bytes(payload_without_hash)
        )
        if actual_payload_sha256 != expected_payload_sha256:
            raise RouteRunnerError(f"SOURCE_CATALOG_PAYLOAD_SHA_MISMATCH:{path.name}")
    return catalogs


def normalized_chars(text: str) -> str:
    return "".join(
        char.lower()
        for char in text
        if char.isalnum() or "\u4e00" <= char <= "\u9fff"
    )


def char_ngrams(text: str, sizes: Sequence[int] = (2, 3)) -> Counter[str]:
    normalized = normalized_chars(text)
    grams: Counter[str] = Counter()
    for size in sizes:
        for start in range(max(0, len(normalized) - size + 1)):
            grams[normalized[start : start + size]] += 1
    return grams


def build_sparse_index(catalogs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    document_frequency: Counter[str] = Counter()
    for catalog in catalogs:
        for paragraph in catalog["paragraphs"]:
            grams = char_ngrams(paragraph["original_text"])
            document_frequency.update(grams)
            documents.append(
                {
                    "case_id": catalog["source_id"],
                    "paragraph_id": paragraph["paragraph_id"],
                    "paragraph_index": int(paragraph["paragraph_id"].rsplit("P", 1)[1]),
                    "char_count": len(paragraph["original_text"]),
                    "original_text": paragraph["original_text"],
                    "grams": dict(grams),
                }
            )
    result: dict[str, Any] = {
        "schema_version": "v02-r2-route-sparse-index.v1",
        "method": "CHAR_2_3_GRAM_BM25_LIKE",
        "source_catalog_bindings": [
            {
                "source_id": catalog["source_id"],
                "source_body_sha256": catalog["source_body_sha256"],
                "catalog_payload_sha256": catalog["catalog_payload_sha256"],
            }
            for catalog in catalogs
        ],
        "document_count": len(documents),
        "document_frequency": dict(document_frequency),
        "documents": documents,
    }
    result["index_payload_sha256"] = sha256_bytes(canonical_bytes(result))
    return result


def rank_paragraphs(
    *,
    query_text: str,
    case_id: str,
    index: Mapping[str, Any],
) -> list[dict[str, Any]]:
    query = char_ngrams(query_text)
    case_docs = [row for row in index["documents"] if row["case_id"] == case_id]
    if not case_docs:
        raise RouteRunnerError(f"INDEX_CASE_MISSING:{case_id}")
    average_length = sum(sum(row["grams"].values()) for row in case_docs) / len(
        case_docs
    )
    total_documents = index["document_count"]
    doc_frequency = index["document_frequency"]
    scored: list[dict[str, Any]] = []
    for row in case_docs:
        frequencies = row["grams"]
        document_length = sum(frequencies.values())
        score = 0.0
        matched: list[str] = []
        for gram, query_frequency in query.items():
            term_frequency = frequencies.get(gram, 0)
            if not term_frequency:
                continue
            matched.append(gram)
            frequency = doc_frequency.get(gram, 0)
            inverse = math.log(
                1 + (total_documents - frequency + 0.5) / (frequency + 0.5)
            )
            denominator = term_frequency + 1.2 * (
                0.25 + 0.75 * document_length / max(average_length, 1)
            )
            score += (
                inverse
                * term_frequency
                * 2.2
                / denominator
                * (1 + math.log1p(query_frequency))
            )
        scored.append(
            {
                "paragraph_id": row["paragraph_id"],
                "paragraph_index": row["paragraph_index"],
                "score": round(score, 8),
                "matched_grams": sorted(matched),
                "char_count": row["char_count"],
                "original_text": row["original_text"],
            }
        )
    return sorted(scored, key=lambda row: (-row["score"], row["paragraph_id"]))


def plan_question(question_text: str) -> list[dict[str, Any]]:
    spans = [
        span.strip(" \n\t。")
        for span in PLAN_SPLIT_PATTERN.split(question_text)
        if span.strip(" \n\t。")
    ]
    if not spans:
        spans = [question_text]
    return [
        {
            "request_head_id": f"RH-{index:02d}",
            "question_span": span,
            "query_terms": [span],
        }
        for index, span in enumerate(spans, start=1)
    ]


def _planner_visible_source_projection(
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    projection: dict[str, Any] = {
        "schema_version": PLANNER_VISIBLE_SOURCE_SCHEMA,
        "source_id": catalog["source_id"],
        "source_body_sha256": catalog["source_body_sha256"],
        "source_text": catalog["source_text"],
        "paragraphs": [
            {
                "paragraph_id": row["paragraph_id"],
                "char_start": row["char_start"],
                "char_end_exclusive": row["char_end_exclusive"],
                "original_text": row["original_text"],
            }
            for row in catalog["paragraphs"]
        ],
        "sentences": [
            {
                "sentence_id": row["sentence_id"],
                "paragraph_id": row["paragraph_id"],
                "char_start": row["char_start"],
                "char_end_exclusive": row["char_end_exclusive"],
                "original_text": row["original_text"],
            }
            for row in catalog["sentences"]
        ],
    }
    projection["projection_payload_sha256"] = sha256_bytes(
        canonical_bytes(projection)
    )
    return projection


def _legacy_obligation_plan(
    *,
    question: Mapping[str, str],
    request_heads: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": OBLIGATION_PLAN_SCHEMA,
        "question_id": question["question_id"],
        "question_text_sha256": sha256_bytes(
            question["question_text"].encode("utf-8")
        ),
        "planner_kind": "LEGACY_PUNCTUATION_HEADS",
        "cardinality_policy": "MECHANICAL_HEAD_COUNT_ONLY",
        "completeness_claim": "NOT_SELF_CERTIFIED",
        "obligations": [
            {
                "obligation_id": row["request_head_id"],
                "question_span": row["question_span"],
                "status": "LEGACY_DIAGNOSTIC_NOT_FACT_TRUTH",
            }
            for row in request_heads
        ],
    }


def _legacy_query_map(
    *,
    route_id: str,
    case_id: str,
    question_id: str,
    queries: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_version": QUERY_MAP_SCHEMA,
        "route_id": route_id,
        "case_id": case_id,
        "question_id": question_id,
        "queries": [
            {
                "query_id": f"QRY-{index:03d}",
                "query_text": query,
                "origin_kind": "LEGACY_QUERY_GENERATOR",
            }
            for index, query in enumerate(queries, start=1)
        ],
    }


def plan_fact_obligations(question: Mapping[str, str]) -> dict[str, Any]:
    matched_specs = [
        spec
        for spec in FACT_OBLIGATION_ONTOLOGY
        if any(
            trigger in question["question_text"]
            for trigger in spec["question_triggers"]
        )
    ]
    if not matched_specs:
        raise RouteRunnerError(
            f"A7_OBLIGATION_TEMPLATE_NOT_FOUND:{question['question_id']}"
        )
    obligations = []
    for index, spec in enumerate(matched_specs, start=1):
        obligations.append(
            {
                "obligation_id": f"OB-{index:02d}",
                "operator": "COLLECT",
                "ontology_id": spec["ontology_id"],
                "fact_types": list(spec["fact_types"]),
                "required_slots": ["proposition"],
                "optional_slots": [
                    "actor",
                    "object",
                    "target",
                    "time_scope",
                    "speech_source",
                ],
                "preserve": ["polarity", "modality", "epistemic_status"],
                "cardinality": "UNKNOWN_OPEN_WORLD",
                "completeness_claim": "NOT_SELF_CERTIFIED",
                "markers": list(spec["markers"]),
            }
        )
    return {
        "schema_version": OBLIGATION_PLAN_SCHEMA,
        "question_id": question["question_id"],
        "question_text_sha256": sha256_bytes(
            question["question_text"].encode("utf-8")
        ),
        "ontology_sha256": sha256_bytes(
            canonical_bytes(FACT_OBLIGATION_ONTOLOGY)
        ),
        "planner_kind": "PROGRAM_ONTOLOGY_GROUNDED",
        "cardinality_policy": "UNKNOWN_OPEN_WORLD",
        "completeness_claim": "NOT_SELF_CERTIFIED",
        "obligations": obligations,
    }


def _trimmed_span(
    text: str,
    *,
    absolute_start: int,
) -> tuple[str, int, int]:
    left = len(text) - len(text.lstrip())
    right = len(text.rstrip())
    if right <= left:
        raise RouteRunnerError("A7_EMPTY_SOURCE_SPAN")
    return (
        text[left:right],
        absolute_start + left,
        absolute_start + right,
    )


def extract_candidate_frames(
    *,
    obligation_plan: Mapping[str, Any],
    planner_source: Mapping[str, Any],
) -> list[dict[str, Any]]:
    allowed_source_fields = {
        "schema_version",
        "source_id",
        "source_body_sha256",
        "source_text",
        "paragraphs",
        "sentences",
        "projection_payload_sha256",
    }
    if set(planner_source) != allowed_source_fields:
        raise RouteRunnerError("A7_PLANNER_SOURCE_FIELDS_INVALID")
    source_text = planner_source["source_text"]
    frames: list[dict[str, Any]] = []
    for obligation in obligation_plan["obligations"]:
        for sentence in planner_source["sentences"]:
            sentence_text = sentence["original_text"]
            matches = [
                (sentence_text.find(marker), marker)
                for marker in obligation["markers"]
                if marker in sentence_text
            ]
            if not matches:
                continue
            marker_start, marker = min(
                matches,
                key=lambda row: (row[0], -len(row[1]), row[1]),
            )
            surface, span_start, span_end = _trimmed_span(
                sentence_text,
                absolute_start=sentence["char_start"],
            )
            if source_text[span_start:span_end] != surface:
                raise RouteRunnerError("A7_SOURCE_SPAN_REBUILD_MISMATCH")
            predicate_start = sentence["char_start"] + marker_start
            predicate_end = predicate_start + len(marker)
            if source_text[predicate_start:predicate_end] != marker:
                raise RouteRunnerError("A7_PREDICATE_SPAN_REBUILD_MISMATCH")
            local_query_start = max(0, marker_start - 12)
            local_query_end = min(
                len(sentence_text),
                marker_start + len(marker) + 20,
            )
            query_surface, query_start, query_end = _trimmed_span(
                sentence_text[local_query_start:local_query_end],
                absolute_start=sentence["char_start"] + local_query_start,
            )
            if source_text[query_start:query_end] != query_surface:
                raise RouteRunnerError("A7_QUERY_SPAN_REBUILD_MISMATCH")
            polarity = (
                "NEGATED"
                if any(token in surface for token in ("不", "没", "未", "无"))
                else "AFFIRMATIVE_OR_UNSPECIFIED"
            )
            modality = (
                "FUTURE_OR_COMMITMENT"
                if any(
                    token in surface
                    for token in (
                        "准备",
                        "决定",
                        "打算",
                        "一定",
                        "必须",
                        "将来",
                        "以后",
                    )
                )
                else "ASSERTED_OR_UNSPECIFIED"
            )
            frames.append(
                {
                    "frame_id": (
                        f"CF-{planner_source['source_id']}-"
                        f"{obligation_plan['question_id']}-"
                        f"{len(frames) + 1:04d}"
                    ),
                    "question_id": obligation_plan["question_id"],
                    "obligation_id": obligation["obligation_id"],
                    "candidate_type": (
                        f"{obligation['fact_types'][0]}_CANDIDATE"
                    ),
                    "source_body_sha256": planner_source[
                        "source_body_sha256"
                    ],
                    "sentence_id": sentence["sentence_id"],
                    "paragraph_id": sentence["paragraph_id"],
                    "char_start": span_start,
                    "char_end_exclusive": span_end,
                    "surface_sha256": sha256_bytes(surface.encode("utf-8")),
                    "query_char_start": query_start,
                    "query_char_end_exclusive": query_end,
                    "query_surface_sha256": sha256_bytes(
                        query_surface.encode("utf-8")
                    ),
                    "slots": {
                        "predicate_span": [
                            predicate_start,
                            predicate_end,
                        ],
                        "proposition_span": [span_start, span_end],
                    },
                    "polarity": polarity,
                    "modality": modality,
                    "rule_ids": [
                        obligation["ontology_id"],
                        f"MARKER:{marker}",
                    ],
                    "status": "CANDIDATE_NOT_ANSWER",
                }
            )
    return frames


def build_a7_query_map(
    *,
    case_id: str,
    question_id: str,
    planner_source: Mapping[str, Any],
    frames: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source_text = planner_source["source_text"]
    grouped: dict[str, dict[str, Any]] = {}
    for frame in frames:
        query_text = source_text[
            frame["query_char_start"] : frame["query_char_end_exclusive"]
        ]
        if sha256_bytes(query_text.encode("utf-8")) != frame[
            "query_surface_sha256"
        ]:
            raise RouteRunnerError("A7_QUERY_SURFACE_SHA_MISMATCH")
        row = grouped.setdefault(
            query_text,
            {
                "query_text": query_text,
                "candidate_frame_ids": [],
                "origins": [
                    {
                        "kind": "SOURCE_EXACT_SPAN",
                        "source_body_sha256": frame["source_body_sha256"],
                        "char_start": frame["query_char_start"],
                        "char_end_exclusive": frame[
                            "query_char_end_exclusive"
                        ],
                    }
                ],
                "weight": 1,
            },
        )
        row["candidate_frame_ids"].append(frame["frame_id"])
    queries = []
    for index, query_text in enumerate(sorted(grouped), start=1):
        row = grouped[query_text]
        queries.append(
            {
                "query_id": f"QRY-{index:04d}",
                **row,
                "candidate_frame_ids": sorted(row["candidate_frame_ids"]),
            }
        )
    return {
        "schema_version": QUERY_MAP_SCHEMA,
        "route_id": "A7",
        "case_id": case_id,
        "question_id": question_id,
        "queries": queries,
    }


def selection_projection(cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    projection: dict[str, Any] = {
        "schema_version": SELECTION_PROJECTION_SCHEMA,
        "cells": [
            {
                "cell_id": cell["cell_id"],
                "selected_windows": [
                    {
                        "paragraph_id": row["paragraph_id"],
                        "rank": row["rank"],
                        "selection_reason": row["selection_reason"],
                    }
                    for row in cell["selected_windows"]
                ],
            }
            for cell in cells
        ],
    }
    projection["projection_payload_sha256"] = sha256_bytes(
        canonical_bytes(projection)
    )
    return projection


def _cue_terms(question_text: str) -> list[str]:
    terms: list[str] = []
    for triggers, cues in GENERIC_CUE_LEXICON.values():
        if any(trigger in question_text for trigger in triggers):
            terms.extend(cues)
    return sorted(set(terms))


def _observable_bridge_terms(question_text: str) -> list[str]:
    terms: list[str] = []
    for triggers, cues in OBSERVABLE_NARRATIVE_BRIDGE.values():
        if any(trigger in question_text for trigger in triggers):
            terms.extend(cues)
    return sorted(set(terms))


def _extract_high_confidence_aliases(
    catalogs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for catalog in catalogs:
        for sentence in catalog["sentences"]:
            for match in ALIAS_PATTERN.finditer(sentence["original_text"]):
                rows.append(
                    {
                        "case_id": catalog["source_id"],
                        "left": match.group("left"),
                        "right": match.group("right"),
                        "source_id": sentence["sentence_id"],
                        "char_start": sentence["char_start"] + match.start(),
                        "char_end_exclusive": sentence["char_start"] + match.end(),
                        "evidence_text": match.group(0),
                        "confidence_basis": "EXPLICIT_ALIAS_PHRASE_ONLY",
                    }
                )
    return rows


def _query_variants(
    *,
    route_id: str,
    question_text: str,
    plan: Sequence[Mapping[str, Any]],
    aliases: Sequence[Mapping[str, Any]],
    case_id: str,
) -> list[str]:
    if route_id == "A0":
        return [question_text]
    base = [head["question_span"] for head in plan]
    if route_id in {"A1a", "A1c", "A3"}:
        return base
    if route_id == "A1b":
        variants = list(base)
        for alias in aliases:
            if alias["case_id"] != case_id:
                continue
            if alias["left"] in question_text or alias["right"] in question_text:
                variants.extend([alias["left"], alias["right"]])
        return sorted(set(variants), key=variants.index)
    if route_id in {"A4", "A4h"}:
        return [*base, *_cue_terms(question_text)]
    if route_id in {"A5", "A6"}:
        return [
            *base,
            *_cue_terms(question_text),
            *_observable_bridge_terms(question_text),
        ]
    raise RouteRunnerError(f"ROUTE_ID_UNKNOWN:{route_id}")


def _merge_rankings(rankings: Sequence[Sequence[Mapping[str, Any]]]) -> list[dict]:
    merged: dict[str, dict[str, Any]] = {}
    for ranking_index, ranking in enumerate(rankings):
        for rank, row in enumerate(ranking):
            paragraph_id = row["paragraph_id"]
            score = float(row["score"])
            existing = merged.get(paragraph_id)
            weighted = score + 1 / (rank + 1) + 0.01 / (ranking_index + 1)
            if existing is None:
                merged[paragraph_id] = {
                    **row,
                    "merged_score": weighted,
                    "query_hit_count": 1,
                }
            else:
                existing["merged_score"] = max(existing["merged_score"], weighted)
                existing["query_hit_count"] += 1
    return sorted(
        merged.values(),
        key=lambda row: (
            -row["query_hit_count"],
            -row["merged_score"],
            row["paragraph_id"],
        ),
    )


def _merge_rankings_nonzero_fusion(
    rankings: Sequence[Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """只让真实词面命中的段落获得融合分，零命中段只作后置补余量。"""
    merged: dict[str, dict[str, Any]] = {}
    fallback: dict[str, dict[str, Any]] = {}
    for ranking_index, ranking in enumerate(rankings, start=1):
        query_id = f"QRY-{ranking_index:02d}"
        for rank, row in enumerate(ranking, start=1):
            paragraph_id = row["paragraph_id"]
            if not row.get("matched_grams"):
                fallback.setdefault(
                    paragraph_id,
                    {
                        **row,
                        "merged_score": 0.0,
                        "query_hit_count": 0,
                        "matched_query_ids": [],
                        "matched_grams": [],
                    },
                )
                continue
            score = float(row["score"])
            weighted = score + 1 / rank + 0.01 / ranking_index
            existing = merged.get(paragraph_id)
            if existing is None:
                merged[paragraph_id] = {
                    **row,
                    "merged_score": weighted,
                    "query_hit_count": 1,
                    "matched_query_ids": [query_id],
                    "matched_grams": sorted(set(row["matched_grams"])),
                }
            else:
                existing["merged_score"] = max(existing["merged_score"], weighted)
                existing["query_hit_count"] += 1
                existing["matched_query_ids"] = sorted(
                    {*existing["matched_query_ids"], query_id}
                )
                existing["matched_grams"] = sorted(
                    {*existing["matched_grams"], *row["matched_grams"]}
                )
    matched_rows = sorted(
        merged.values(),
        key=lambda row: (
            -row["query_hit_count"],
            -row["merged_score"],
            row["paragraph_id"],
        ),
    )
    fallback_rows = [
        row
        for paragraph_id, row in sorted(fallback.items())
        if paragraph_id not in merged
    ]
    return [*matched_rows, *fallback_rows]


def _pack_nonzero_fusion(
    rows: Sequence[Mapping[str, Any]],
    *,
    budget: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used = 0
    for rank, row in enumerate(rows, start=1):
        char_count = int(row["char_count"])
        if used + char_count > budget:
            continue
        actual_match = int(row["query_hit_count"]) > 0
        selected.append(
            {
                "paragraph_id": row["paragraph_id"],
                "rank": rank,
                "score": round(float(row["merged_score"]), 8),
                "char_count": char_count,
                "selection_reason": (
                    "ACTUAL_QUERY_MATCH" if actual_match else "UNMATCHED_FALLBACK"
                ),
                "matched_query_ids": list(row["matched_query_ids"]),
                "matched_grams": list(row["matched_grams"]),
            }
        )
        used += char_count
    return selected


def _pack_request_head_minimum_then_global_fill(
    rows: Sequence[Mapping[str, Any]],
    *,
    request_head_rankings: Sequence[Sequence[Mapping[str, Any]]],
    budget: int,
) -> list[dict[str, Any]]:
    """每个问题分头先保一份真实命中，再按 A5 全局顺序补满固定预算。"""
    global_rank_by_id = {
        row["paragraph_id"]: rank for rank, row in enumerate(rows, start=1)
    }
    rows_by_id = {row["paragraph_id"]: row for row in rows}
    selected_ids: set[str] = set()
    request_heads_by_id: dict[str, set[str]] = {}
    used = 0

    for head_index, ranking in enumerate(request_head_rankings, start=1):
        head_id = f"RH-{head_index:02d}"
        for candidate in ranking:
            if not candidate.get("matched_grams"):
                continue
            paragraph_id = candidate["paragraph_id"]
            if paragraph_id in selected_ids:
                request_heads_by_id.setdefault(paragraph_id, set()).add(head_id)
                break
            char_count = int(candidate["char_count"])
            if used + char_count > budget:
                continue
            selected_ids.add(paragraph_id)
            request_heads_by_id.setdefault(paragraph_id, set()).add(head_id)
            used += char_count
            break

    for row in rows:
        paragraph_id = row["paragraph_id"]
        if paragraph_id in selected_ids:
            continue
        char_count = int(row["char_count"])
        if used + char_count > budget:
            continue
        selected_ids.add(paragraph_id)
        used += char_count

    selected: list[dict[str, Any]] = []
    for paragraph_id in sorted(selected_ids, key=global_rank_by_id.__getitem__):
        row = rows_by_id[paragraph_id]
        actual_match = int(row["query_hit_count"]) > 0
        selected.append(
            {
                "paragraph_id": paragraph_id,
                "rank": global_rank_by_id[paragraph_id],
                "score": round(float(row["merged_score"]), 8),
                "char_count": int(row["char_count"]),
                "selection_reason": (
                    "ACTUAL_QUERY_MATCH" if actual_match else "UNMATCHED_FALLBACK"
                ),
                "request_head_ids": sorted(
                    request_heads_by_id.get(paragraph_id, set())
                ),
                "matched_query_ids": list(row["matched_query_ids"]),
                "matched_grams": list(row["matched_grams"]),
            }
        )
    return selected


def _pack_conditional_neighbors(
    rows: Sequence[Mapping[str, Any]],
    *,
    case_documents: Sequence[Mapping[str, Any]],
    budget: int,
) -> list[dict[str, Any]]:
    base_selected = _pack_budget(rows, budget=budget)
    selected_ids = {row["paragraph_id"] for row in base_selected}
    ranked_by_id = {row["paragraph_id"]: row for row in rows}
    by_index = {row["paragraph_index"]: row for row in case_documents}
    expanded: dict[str, dict[str, Any]] = {
        paragraph_id: dict(ranked_by_id[paragraph_id])
        for paragraph_id in selected_ids
    }
    for paragraph_id in sorted(selected_ids):
        row = ranked_by_id[paragraph_id]
        if not any(trigger in row["original_text"] for trigger in NEIGHBOR_TRIGGERS):
            continue
        for neighbor_index in (row["paragraph_index"] - 1, row["paragraph_index"] + 1):
            neighbor = by_index.get(neighbor_index)
            if neighbor is None or neighbor["paragraph_id"] in expanded:
                continue
            expanded[neighbor["paragraph_id"]] = {
                **neighbor,
                "score": row["score"],
                "merged_score": row["merged_score"] * 0.95,
                "query_hit_count": row["query_hit_count"],
                "neighbor_of": row["paragraph_id"],
            }
    reranked = sorted(
        expanded.values(),
        key=lambda row: (
            -row["query_hit_count"],
            -row["merged_score"],
            row["paragraph_id"],
        ),
    )
    return _pack_budget(reranked, budget=budget)


def _pack_budget(
    rows: Sequence[Mapping[str, Any]],
    *,
    budget: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used = 0
    for rank, row in enumerate(rows, start=1):
        char_count = int(row["char_count"])
        if used + char_count > budget:
            continue
        selected.append(
            {
                "paragraph_id": row["paragraph_id"],
                "rank": rank,
                "score": round(float(row["merged_score"]), 8),
                "char_count": char_count,
                "selection_reason": (
                    "CONDITIONAL_NEIGHBOR"
                    if "neighbor_of" in row
                    else "QUERY_RANKING"
                ),
            }
        )
        used += char_count
    return selected


def _pack_independent_head_quotas(
    rankings: Sequence[Sequence[Mapping[str, Any]]],
    *,
    budget: int,
) -> list[dict[str, Any]]:
    """每个请求头先独立取证，再在固定总预算内去重合并。"""
    if not rankings:
        return []
    per_head_quota = budget // len(rankings)
    selected_by_head: dict[str, set[str]] = {}
    for head_index, ranking in enumerate(rankings, start=1):
        head_used = 0
        head_id = f"RH-{head_index:02d}"
        for row in ranking:
            char_count = int(row["char_count"])
            if head_used + char_count > per_head_quota:
                continue
            selected_by_head.setdefault(row["paragraph_id"], set()).add(head_id)
            head_used += char_count

    merged = _merge_rankings(rankings)
    merged_by_id = {row["paragraph_id"]: row for row in merged}
    expected_head_ids = {f"RH-{index:02d}" for index in range(1, len(rankings) + 1)}
    represented_head_ids = {
        head_id for head_ids in selected_by_head.values() for head_id in head_ids
    }
    if represented_head_ids != expected_head_ids:
        raise RouteRunnerError("A3_REQUEST_HEAD_MINIMUM_WINDOW_UNSATISFIED")
    selected_ids = set(selected_by_head)
    used = sum(int(merged_by_id[paragraph_id]["char_count"]) for paragraph_id in selected_ids)
    leftover_ids: set[str] = set()
    for row in merged:
        paragraph_id = row["paragraph_id"]
        if paragraph_id in selected_ids:
            continue
        char_count = int(row["char_count"])
        if used + char_count > budget:
            continue
        selected_ids.add(paragraph_id)
        leftover_ids.add(paragraph_id)
        used += char_count

    selected: list[dict[str, Any]] = []
    for rank, row in enumerate(merged, start=1):
        paragraph_id = row["paragraph_id"]
        if paragraph_id not in selected_ids:
            continue
        selected.append(
            {
                "paragraph_id": paragraph_id,
                "rank": rank,
                "score": round(float(row["merged_score"]), 8),
                "char_count": int(row["char_count"]),
                "selection_reason": (
                    "MERGED_LEFTOVER_FILL"
                    if paragraph_id in leftover_ids
                    else "INDEPENDENT_REQUEST_HEAD_QUOTA"
                ),
                "request_head_ids": sorted(selected_by_head.get(paragraph_id, set())),
            }
        )
    if sum(row["char_count"] for row in selected) > budget:
        raise RouteRunnerError("A3_FIXED_BUDGET_EXCEEDED")
    return selected


def run_routes(
    *,
    workspace: Path,
    preregistered_manifest_path: Path,
    expected_manifest_sha256: str,
    output_dir: Path,
    route_ids: Sequence[str] = ROUTES,
    a8_event_graph_contract_path: Path | None = None,
    expected_a8_event_graph_contract_sha256: str | None = None,
) -> dict[str, Any]:
    route_ids = tuple(route_ids)
    if not route_ids or len(route_ids) != len(set(route_ids)):
        raise RouteRunnerError("ROUTE_SELECTION_INVALID")
    unknown_routes = sorted(set(route_ids) - set(SUPPORTED_ROUTES))
    if unknown_routes:
        raise RouteRunnerError(f"ROUTE_SELECTION_UNKNOWN:{unknown_routes}")
    a8_contract: dict[str, Any] | None = None
    if "A8" in route_ids:
        if (
            a8_event_graph_contract_path is None
            or expected_a8_event_graph_contract_sha256 is None
        ):
            raise RouteRunnerError("A8_EVENT_GRAPH_CONTRACT_REQUIRED")
        a8_contract = a8_graph.load_contract(
            a8_event_graph_contract_path,
            expected_sha256=expected_a8_event_graph_contract_sha256,
        )
    workspace_receipt = hardening.verify_route_workspace(
        workspace,
        preregistered_manifest_path=preregistered_manifest_path,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    questions = _load_questions(workspace / "question_set.json")
    catalogs = _load_catalogs(workspace / "source_catalog_v2")
    index = build_sparse_index(catalogs)
    aliases = _extract_high_confidence_aliases(catalogs)
    planner_visible_source_records: list[dict[str, str]] = []
    planner_visible_sources: dict[str, dict[str, Any]] = {}
    for catalog in catalogs:
        planner_projection = _planner_visible_source_projection(catalog)
        projection_path = (
            output_dir
            / "frozen/planner_visible_source_v1"
            / f"{catalog['source_id']}.json"
        )
        write_json(
            projection_path,
            planner_projection,
        )
        planner_visible_sources[catalog["source_id"]] = planner_projection
        planner_visible_source_records.append(
            {
                "source_id": catalog["source_id"],
                "path": projection_path.relative_to(output_dir).as_posix(),
                "sha256": sha256_file(projection_path),
            }
        )
    planner_visible_source_sha256 = sha256_bytes(
        canonical_bytes(planner_visible_source_records)
    )
    a8_event_graphs: dict[str, dict[str, Any]] = {}
    a8_event_graph_records: list[dict[str, str]] = []
    if "A8" in route_ids:
        if a8_contract is None:
            raise RouteRunnerError("A8_EVENT_GRAPH_CONTRACT_NOT_LOADED")
        for case_id in CASE_IDS:
            graph = a8_graph.build_event_graph(
                planner_visible_sources[case_id],
                a8_contract,
            )
            graph_path = (
                output_dir / "route_assets/event_graphs/A8" / f"{case_id}.json"
            )
            write_json(graph_path, graph)
            a8_event_graphs[case_id] = graph
            a8_event_graph_records.append(
                {
                    "source_id": case_id,
                    "path": graph_path.relative_to(output_dir).as_posix(),
                    "sha256": sha256_file(graph_path),
                }
            )
    write_json(output_dir / "frozen/question_projection.json", questions)
    write_json(output_dir / "frozen/source_bindings.json", index["source_catalog_bindings"])
    write_json(output_dir / "frozen/high_confidence_alias_ledger.json", aliases)
    write_json(
        output_dir / "frozen/generic_cue_lexicon.json",
        {
            "generic_cue_lexicon": GENERIC_CUE_LEXICON,
            "observable_narrative_bridge": OBSERVABLE_NARRATIVE_BRIDGE,
        },
    )
    write_json(output_dir / "route_assets/sparse_index.json", index)

    outputs: list[dict[str, Any]] = []
    route_obligation_plans: dict[str, dict[str, dict[str, Any]]] = {}
    route_query_maps: dict[str, dict[str, dict[str, Any]]] = {}
    route_candidate_frames: dict[
        str, dict[str, list[dict[str, Any]]]
    ] = {}
    route_event_triggers: dict[str, dict[str, dict[str, Any]]] = {}
    selection_projection_records: dict[str, list[dict[str, Any]]] = {}
    for route_id in route_ids:
        for budget in BUDGETS:
            cells: list[dict[str, Any]] = []
            for catalog in catalogs:
                case_id = catalog["source_id"]
                case_documents = [
                    row for row in index["documents"] if row["case_id"] == case_id
                ]
                for question in questions:
                    plan = plan_question(question["question_text"])
                    audit_key = f"{case_id}::{question['question_id']}"
                    event_trigger: dict[str, Any] | None = None
                    if route_id == "A8":
                        if a8_contract is None:
                            raise RouteRunnerError(
                                "A8_EVENT_GRAPH_CONTRACT_NOT_LOADED"
                            )
                        a5_queries = _query_variants(
                            route_id="A5",
                            question_text=question["question_text"],
                            plan=plan,
                            aliases=aliases,
                            case_id=case_id,
                        )
                        event_trigger = a8_graph.compile_event_queries(
                            question=question,
                            graph=a8_event_graphs[case_id],
                            contract=a8_contract,
                        )
                        query_map = a8_graph.build_a8_query_map(
                            case_id=case_id,
                            question_id=question["question_id"],
                            a5_queries=a5_queries,
                            trigger=event_trigger,
                        )
                        queries = [
                            row["query_text"] for row in query_map["queries"]
                        ]
                        obligation_plan = _legacy_obligation_plan(
                            question=question,
                            request_heads=plan,
                        )
                        candidate_frames = []
                    elif route_id == "A7":
                        obligation_plan = plan_fact_obligations(question)
                        candidate_frames = extract_candidate_frames(
                            obligation_plan=obligation_plan,
                            planner_source=planner_visible_sources[case_id],
                        )
                        query_map = build_a7_query_map(
                            case_id=case_id,
                            question_id=question["question_id"],
                            planner_source=planner_visible_sources[case_id],
                            frames=candidate_frames,
                        )
                        queries = [
                            row["query_text"] for row in query_map["queries"]
                        ]
                    else:
                        queries = _query_variants(
                            route_id=route_id,
                            question_text=question["question_text"],
                            plan=plan,
                            aliases=aliases,
                            case_id=case_id,
                        )
                        obligation_plan = _legacy_obligation_plan(
                            question=question,
                            request_heads=plan,
                        )
                        query_map = _legacy_query_map(
                            route_id=route_id,
                            case_id=case_id,
                            question_id=question["question_id"],
                            queries=queries,
                        )
                        candidate_frames = []
                    existing_plan = route_obligation_plans.setdefault(
                        route_id, {}
                    ).setdefault(audit_key, obligation_plan)
                    existing_query_map = route_query_maps.setdefault(
                        route_id, {}
                    ).setdefault(audit_key, query_map)
                    if existing_plan != obligation_plan:
                        raise RouteRunnerError(
                            f"OBLIGATION_PLAN_DRIFT:{route_id}:{audit_key}"
                        )
                    if existing_query_map != query_map:
                        raise RouteRunnerError(
                            f"QUERY_MAP_DRIFT:{route_id}:{audit_key}"
                        )
                    existing_frames = route_candidate_frames.setdefault(
                        route_id, {}
                    ).setdefault(audit_key, candidate_frames)
                    if existing_frames != candidate_frames:
                        raise RouteRunnerError(
                            f"CANDIDATE_FRAME_DRIFT:{route_id}:{audit_key}"
                        )
                    if event_trigger is not None:
                        existing_trigger = route_event_triggers.setdefault(
                            route_id, {}
                        ).setdefault(audit_key, event_trigger)
                        if existing_trigger != event_trigger:
                            raise RouteRunnerError(
                                f"EVENT_TRIGGER_DRIFT:{route_id}:{audit_key}"
                            )
                    rankings = [
                        rank_paragraphs(
                            query_text=query,
                            case_id=case_id,
                            index=index,
                        )
                        for query in queries
                    ]
                    merged = (
                        _merge_rankings_nonzero_fusion(rankings)
                        if route_id in {"A4h", "A5", "A6", "A7", "A8"}
                        else _merge_rankings(rankings)
                    )
                    if route_id == "A1c":
                        selected = _pack_conditional_neighbors(
                            merged,
                            case_documents=case_documents,
                            budget=budget,
                        )
                    elif route_id == "A3":
                        selected = _pack_independent_head_quotas(
                            rankings,
                            budget=budget,
                        )
                    elif route_id == "A6":
                        selected = _pack_request_head_minimum_then_global_fill(
                            merged,
                            request_head_rankings=rankings[: len(plan)],
                            budget=budget,
                        )
                    elif route_id in {"A4h", "A5", "A7", "A8"}:
                        selected = _pack_nonzero_fusion(merged, budget=budget)
                    else:
                        selected = _pack_budget(merged, budget=budget)
                    cell = {
                            "cell_id": f"{case_id}::{question['question_id']}",
                            "case_id": case_id,
                            "question_id": question["question_id"],
                            "request_heads": plan,
                            "query_variant_count": len(queries),
                            "selected_windows": selected,
                            "candidate_chars": sum(
                                row["char_count"] for row in selected
                            ),
                        }
                    if route_id in {"A4h", "A5", "A6", "A7", "A8"}:
                        actual = [
                            row
                            for row in selected
                            if row["selection_reason"] == "ACTUAL_QUERY_MATCH"
                        ]
                        fallback = [
                            row
                            for row in selected
                            if row["selection_reason"] == "UNMATCHED_FALLBACK"
                        ]
                        cell.update(
                            {
                                "actual_match_window_count": len(actual),
                                "actual_match_chars": sum(
                                    row["char_count"] for row in actual
                                ),
                                "fallback_window_count": len(fallback),
                                "fallback_chars": sum(
                                    row["char_count"] for row in fallback
                                ),
                            }
                        )
                    cells.append(cell)
            output: dict[str, Any] = {
                "schema_version": ROUTE_OUTPUT_SCHEMA,
                "candidate_status": "candidate_silver_not_active",
                "route_id": route_id,
                "budget_chars": budget,
                "question_projection_sha256": sha256_file(
                    output_dir / "frozen/question_projection.json"
                ),
                "index_payload_sha256": index["index_payload_sha256"],
                "alias_ledger_sha256": sha256_file(
                    output_dir / "frozen/high_confidence_alias_ledger.json"
                ),
                "cue_lexicon_sha256": sha256_file(
                    output_dir / "frozen/generic_cue_lexicon.json"
                ),
                "cells": cells,
                "model_api_calls": 0,
                "network_calls": 0,
            }
            output["output_payload_sha256"] = sha256_bytes(canonical_bytes(output))
            output_path = output_dir / "sealed_outputs" / route_id / f"{budget}.json"
            write_json(output_path, output)
            selection_path = (
                output_dir
                / "route_assets/selection_projections"
                / route_id
                / f"{budget}.json"
            )
            write_json(selection_path, selection_projection(cells))
            selection_projection_records.setdefault(route_id, []).append(
                {
                    "budget_chars": budget,
                    "path": selection_path.relative_to(output_dir).as_posix(),
                    "sha256": sha256_file(selection_path),
                }
            )
            outputs.append(
                {
                    "route_id": route_id,
                    "budget_chars": budget,
                    "path": output_path.relative_to(output_dir).as_posix(),
                    "sha256": sha256_file(output_path),
                }
            )

    obligation_plan_sha256: dict[str, str] = {}
    query_map_sha256: dict[str, str] = {}
    source_candidate_frames_sha256: dict[str, str] = {}
    for route_id in route_ids:
        obligation_path = (
            output_dir / "route_assets/obligation_plans" / f"{route_id}.json"
        )
        query_map_path = (
            output_dir / "route_assets/query_maps" / f"{route_id}.json"
        )
        candidate_frames_path = (
            output_dir
            / "route_assets/source_candidate_frames_v1"
            / f"{route_id}.json"
        )
        write_json(
            obligation_path,
            {
                "schema_version": "r2-obligation-plan-collection.v1",
                "route_id": route_id,
                "cells": [
                    {
                        "cell_id": key,
                        "plan": route_obligation_plans[route_id][key],
                    }
                    for key in sorted(route_obligation_plans[route_id])
                ],
            },
        )
        write_json(
            query_map_path,
            {
                "schema_version": "r2-query-map-collection.v1",
                "route_id": route_id,
                "cells": [
                    route_query_maps[route_id][key]
                    for key in sorted(route_query_maps[route_id])
                ],
            },
        )
        write_json(
            candidate_frames_path,
            {
                "schema_version": "r2-source-candidate-frame-collection.v1",
                "route_id": route_id,
                "cells": [
                    {
                        "cell_id": key,
                        "frames": route_candidate_frames[route_id][key],
                    }
                    for key in sorted(route_candidate_frames[route_id])
                ],
            },
        )
        obligation_plan_sha256[route_id] = sha256_file(obligation_path)
        query_map_sha256[route_id] = sha256_file(query_map_path)
        source_candidate_frames_sha256[route_id] = sha256_file(
            candidate_frames_path
        )

    if "A8" in route_ids:
        graph_collection: dict[str, Any] = {
            "schema_version": "r2-event-graph-collection.v1",
            "route_id": "A8",
            "graphs": a8_event_graph_records,
        }
        graph_collection["collection_payload_sha256"] = sha256_bytes(
            canonical_bytes(graph_collection)
        )
        graph_collection_path = (
            output_dir / "route_assets/event_graphs/A8_collection.json"
        )
        write_json(graph_collection_path, graph_collection)

        trigger_collection: dict[str, Any] = {
            "schema_version": "r2-event-trigger-collection.v1",
            "route_id": "A8",
            "cells": [
                route_event_triggers["A8"][key]
                for key in sorted(route_event_triggers["A8"])
            ],
        }
        trigger_collection["collection_payload_sha256"] = sha256_bytes(
            canonical_bytes(trigger_collection)
        )
        trigger_collection_path = (
            output_dir / "route_assets/event_triggers/A8.json"
        )
        write_json(trigger_collection_path, trigger_collection)

    parent_map = {
        "A0": None,
        "A1a": "A0",
        "A1b": "A1a",
        "A1c": "A1a",
        "A3": "A1a",
        "A4": "A0",
        "A4h": "A4",
        "A5": "A4h",
        "A6": "A5",
        "A7": "A5",
        "A8": "A5",
    }
    single_change = {
        "A0": "BASELINE_QUESTION_ONLY",
        "A1a": "PROGRAM_QUESTION_PLAN_ONLY",
        "A1b": "HIGH_CONFIDENCE_ALIAS_ONLY_ON_A1A",
        "A1c": "CONDITIONAL_NEIGHBOR_ONLY_ON_A1A",
        "A3": "INDEPENDENT_REQUEST_HEAD_QUOTA_AND_MERGE_ONLY",
        "A4": "GENERIC_CUE_LEXICON_ONLY",
        "A4h": "NONZERO_QUERY_HIT_ACCOUNTING_AND_FALLBACK_ORDER_ONLY",
        "A5": "OBSERVABLE_NARRATIVE_BRIDGE_ONLY_ON_A4H",
        "A6": "REQUEST_HEAD_MINIMUM_WINDOW_BEFORE_A5_GLOBAL_FILL_ONLY",
        "A7": "PROGRAM_ONTOLOGY_GROUNDED_OBLIGATION_PLANNER_ONLY",
        "A8": "A5_FROZEN_QUERY_PREFIX_PLUS_EXACT_RELATION_QUERY_APPEND_ONLY",
    }
    runner_sha256 = sha256_file(Path(__file__))
    hardening_sha256 = sha256_file(Path(hardening.__file__))
    index_builder_sha256 = sha256_bytes(
        inspect.getsource(build_sparse_index).encode("utf-8")
    )
    for route_id in route_ids:
        route_outputs = sorted(
            [row for row in outputs if row["route_id"] == route_id],
            key=lambda row: row["budget_chars"],
        )
        manifest = {
            "schema_version": ROUTE_MANIFEST_SCHEMA,
            "route_id": route_id,
            "parent_route_id": parent_map[route_id],
            "single_change": single_change[route_id],
            "budgets": list(BUDGETS),
            "question_projection_sha256": sha256_file(
                output_dir / "frozen/question_projection.json"
            ),
            "source_bindings_sha256": sha256_file(
                output_dir / "frozen/source_bindings.json"
            ),
            "workspace_manifest_sha256": expected_manifest_sha256,
            "index_payload_sha256": index["index_payload_sha256"],
            "runner_sha256": runner_sha256,
            "index_builder_sha256": index_builder_sha256,
            "hardening_sha256": hardening_sha256,
            "obligation_plan_sha256": obligation_plan_sha256[route_id],
            "query_map_sha256": query_map_sha256[route_id],
            "source_candidate_frames_sha256": (
                source_candidate_frames_sha256[route_id]
            ),
            "planner_visible_source_sha256": planner_visible_source_sha256,
            "selection_projection_records": selection_projection_records[
                route_id
            ],
            "planner_runner_sha256": runner_sha256,
            "opened_input_paths": [
                "question_set.json",
                *[
                    f"source_catalog_v2/{case_id}.json"
                    for case_id in CASE_IDS
                ],
            ],
            "hidden_root_mounted": False,
            "executor_kind": "ZERO_API_PYTHON",
            "sealed_output_collection_sha256": sha256_bytes(
                canonical_bytes(route_outputs)
            ),
            "model_api_calls": 0,
            "network_calls": 0,
        }
        manifest["manifest_payload_sha256"] = sha256_bytes(canonical_bytes(manifest))
        write_json(output_dir / "route_manifests" / f"{route_id}.json", manifest)

    route_manifest_records = [
        {
            "route_id": route_id,
            "path": f"route_manifests/{route_id}.json",
            "sha256": sha256_file(
                output_dir / "route_manifests" / f"{route_id}.json"
            ),
        }
        for route_id in route_ids
    ]

    receipt: dict[str, Any] = {
        "schema_version": "v02-r2-offline-route-run-receipt.v1",
        "candidate_status": "candidate_silver_not_active",
        "route_count": len(route_ids),
        "budget_count": len(BUDGETS),
        "cell_count_per_output": len(CASE_IDS) * len(questions),
        "sealed_output_count": len(outputs),
        "alias_count": len(aliases),
        "model_api_calls": 0,
        "network_calls": 0,
        "workspace_verification": workspace_receipt,
        "route_manifests": route_manifest_records,
        "outputs": outputs,
        "scoreable_claim": False,
        "interpretation_boundary": (
            "这里只封存无隐藏答案的候选窗口；质量与召回须由隔离评分入口读取后计算。"
        ),
    }
    receipt["receipt_payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    write_json(output_dir / "route_run_receipt.json", receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--routes",
        nargs="+",
        choices=SUPPORTED_ROUTES,
        default=list(ROUTES),
    )
    parser.add_argument("--a8-event-graph-contract", type=Path)
    parser.add_argument("--a8-event-graph-contract-sha256")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run_routes(
        workspace=args.workspace,
        preregistered_manifest_path=args.manifest,
        expected_manifest_sha256=args.manifest_sha256,
        output_dir=args.output_dir,
        route_ids=args.routes,
        a8_event_graph_contract_path=args.a8_event_graph_contract,
        expected_a8_event_graph_contract_sha256=(
            args.a8_event_graph_contract_sha256
        ),
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

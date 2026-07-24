"""第98道刀A步一的纯程序合同与确定性选择逻辑。

本模块不访问网络、不调用模型，也不读取金标或人工判词。外部输入只能
通过 ``SourceReader`` 的精确白名单进入。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from experiments.Z97_rfu_ucr_ledger_20260724.core import (
    Z97ContractError,
    validate_candidate_claim,
    validate_rfu,
)


class Z98ContractError(ValueError):
    """第98道步一合同或只读输入不成立。"""


RETRY03_ROOT = (
    "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_"
    "20260722_transport_retry03"
)
Z96_SUMMARY_PATH = (
    "runs/Z96_刀B_Aplus锚层与证据闭包_r02_20260724/"
    "pass1/pass_summary.json"
)
Z94_SINGLE_CONTRACT_PATH = (
    "runs/Z94_X01_Flash局部语义包_步二腾讯通道_v1.0_20260723/"
    "provenance/approved_supply/01_一对一单对象输出合同v1_候选草案.md"
)
Z97_RFU_SCHEMA_PATH = (
    "experiments/Z97_rfu_ucr_ledger_20260724/contracts/rfu.schema.json"
)
Z97_CLAIM_SCHEMA_PATH = (
    "experiments/Z97_rfu_ucr_ledger_20260724/contracts/"
    "candidate_claim.schema.json"
)

CHAPTER_SPECS: dict[str, dict[str, Any]] = {
    "ch0003": {
        "chapter_number": 3,
        "event_count": 58,
        "event_sha256": (
            "295c7f19dc46bd3c56e984ec701d40dcb34a68eef0a20ec3474cfb5f723d150a"
        ),
        "t1_total_tokens": 20035,
        "request_sha256": (
            "066c28910e612bb38e0db2bc28bde9f2f43b4349ef52774a275a68b347e28f80"
        ),
    },
    "ch0013": {
        "chapter_number": 13,
        "event_count": 46,
        "event_sha256": (
            "aeefcee35c56e52f82dc7382d1073902311c68947d4d8c518cfbf23816808898"
        ),
        "t1_total_tokens": 24586,
        "request_sha256": (
            "ef343a3c0f52e1727e0a00a3dcc301cff7d158671edbc30252532189eee90629"
        ),
    },
    "ch0019": {
        "chapter_number": 19,
        "event_count": 52,
        "event_sha256": (
            "2f7b9713149183a73d4b1b17a620cba3dabe146ff5935d8a43f1e15bd8243d30"
        ),
        "t1_total_tokens": 38676,
        "request_sha256": (
            "ef76edc3f27fc615a976ae5d9c0e6da7e333610c8b7e6e4f77c5ed027ea8c583"
        ),
    },
}
RETRY03_USAGE_SHA256 = (
    "ffec6350aa88c1bdd1d25da4c3d639f96c4584c3ae45da63f34e4e06b33b29e1"
)

_PATCH_FIELDS = frozenset(
    {
        "op",
        "target_event_ids",
        "source_span_ids",
        "actor",
        "predicate",
        "object_or_result",
        "hard_qualifiers",
        "fact_class",
        "speaker",
        "anchor_candidates",
    }
)
_PATCH_OPS = frozenset(
    {
        "KEEP",
        "ADD",
        "SPLIT",
        "NARROW",
        "RECLASSIFY",
        "ADD_ANCHOR_CANDIDATE",
    }
)
_FACT_CLASSES = frozenset(
    {
        "event",
        "state",
        "knowledge",
        "intention",
        "background",
        "dialogue",
        "setting",
    }
)
_QUALIFIER_KINDS = frozenset(
    {
        "time",
        "frequency",
        "condition",
        "source",
        "attribution",
        "modality",
        "purpose",
        "quantity",
        "location",
        "scope",
    }
)
_EVENT_ID_RE = re.compile(r"^EV-C\d{4}-\d{2,}$")
_SPAN_ID_RE = re.compile(r"^ch\d{4}:E\d{4}$")
_SLOT_ID_RE = re.compile(r"^SLOT-ch\d{4}-\d{2}$")
_RISK_MARKERS = (
    "如果",
    "因为",
    "因此",
    "所以",
    "但是",
    "然而",
    "并且",
    "以及",
    "随后",
    "后来",
    "曾经",
    "准备",
    "打算",
    "认为",
    "觉得",
    "告诉",
    "要求",
    "必须",
    "可能",
    "似乎",
    "疑惑",
    "决定",
    "希望",
    "为了",
    "直到",
    "除非",
)
_PUNCTUATION_MARKERS = ("，", "；", "：", "、", "？", "！")


def stable_json_bytes(value: Any) -> bytes:
    """把 JSON 兼容值编码成稳定字节。"""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    """返回小写 SHA-256。"""

    return hashlib.sha256(data).hexdigest()


def verify_sha(actual: str, expected: str, label: str) -> None:
    """发现源件 SHA 漂移就硬停。"""

    if actual != expected:
        raise Z98ContractError(
            f"{label} SHA 漂移：expected={expected}, actual={actual}"
        )


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Z98ContractError(f"{label} 必须是对象")
    return value


def _strict_keys(
    row: Mapping[str, Any],
    expected: set[str] | frozenset[str],
    label: str,
) -> None:
    missing = set(expected) - set(row)
    extra = set(row) - set(expected)
    if missing:
        raise Z98ContractError(f"{label} 缺字段：{sorted(missing)}")
    if extra:
        raise Z98ContractError(f"{label} 含未知字段：{sorted(extra)}")


def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        qualifier = "字符串" if allow_empty else "非空字符串"
        raise Z98ContractError(f"{label} 必须是{qualifier}")
    return value


def _require_string_list(
    value: Any,
    label: str,
    *,
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        raise Z98ContractError(f"{label} 必须是数组")
    if not allow_empty and not value:
        raise Z98ContractError(f"{label} 不得为空")
    if any(not isinstance(item, str) or not item for item in value):
        raise Z98ContractError(f"{label} 只能含非空字符串")
    if len(value) != len(set(value)):
        raise Z98ContractError(f"{label} 含重复项")
    return list(value)


def _require_span_ids(
    value: Any,
    label: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    spans = _require_string_list(value, label, allow_empty=allow_empty)
    if any(not _SPAN_ID_RE.fullmatch(span_id) for span_id in spans):
        raise Z98ContractError(f"{label} 必须使用 chNNNN:ENNNN")
    return spans


def validate_patch(value: Any) -> dict[str, Any]:
    """严格校验单个刀A补丁对象。"""

    row = _require_mapping(value, "patch")
    _strict_keys(row, _PATCH_FIELDS, "patch")
    op = row["op"]
    if op not in _PATCH_OPS:
        raise Z98ContractError("patch.op 非法")
    targets = _require_string_list(
        row["target_event_ids"],
        "patch.target_event_ids",
    )
    if len(targets) > 1 or any(not _EVENT_ID_RE.fullmatch(item) for item in targets):
        raise Z98ContractError("patch.target_event_ids 最多含一个合法事件 ID")
    if op == "ADD" and targets:
        raise Z98ContractError("ADD 不得绑定已有事件")
    if op != "ADD" and len(targets) != 1:
        raise Z98ContractError(f"{op} 必须绑定一个已有事件")
    _require_span_ids(row["source_span_ids"], "patch.source_span_ids")
    for field in ("actor", "predicate", "object_or_result"):
        _require_string(row[field], f"patch.{field}", allow_empty=True)
    if row["fact_class"] not in _FACT_CLASSES:
        raise Z98ContractError("patch.fact_class 非法")
    if row["speaker"] is not None:
        _require_string(row["speaker"], "patch.speaker")
    qualifiers = row["hard_qualifiers"]
    if not isinstance(qualifiers, list):
        raise Z98ContractError("patch.hard_qualifiers 必须是数组")
    for index, qualifier in enumerate(qualifiers):
        qualifier_row = _require_mapping(
            qualifier,
            f"patch.hard_qualifiers[{index}]",
        )
        _strict_keys(
            qualifier_row,
            {"kind", "value", "source_span_ids"},
            f"patch.hard_qualifiers[{index}]",
        )
        if qualifier_row["kind"] not in _QUALIFIER_KINDS:
            raise Z98ContractError("patch.hard_qualifiers.kind 非法")
        _require_string(
            qualifier_row["value"],
            f"patch.hard_qualifiers[{index}].value",
        )
        _require_span_ids(
            qualifier_row["source_span_ids"],
            f"patch.hard_qualifiers[{index}].source_span_ids",
        )
    _require_span_ids(
        row["anchor_candidates"],
        "patch.anchor_candidates",
        allow_empty=True,
    )
    return deepcopy(dict(row))


def validate_atom_batch(
    value: Any,
    *,
    expected_slot_ids: Sequence[str],
) -> dict[str, Any]:
    """校验批式响应并执行 JSON Schema 无法表达的 slot 等值闸。"""

    row = _require_mapping(value, "atom-batch-v2")
    _strict_keys(row, {"schema", "request_id", "items", "receipt"}, "atom-batch-v2")
    if row["schema"] != "atom-batch-v2":
        raise Z98ContractError("atom-batch-v2.schema 非法")
    _require_string(row["request_id"], "atom-batch-v2.request_id")
    expected = list(expected_slot_ids)
    if not 4 <= len(expected) <= 8 or len(expected) != len(set(expected)):
        raise Z98ContractError("预给 slot 必须为 4～8 个且不重复")
    if any(not _SLOT_ID_RE.fullmatch(slot) for slot in expected):
        raise Z98ContractError("预给 slot_id 格式非法")
    items = row["items"]
    if not isinstance(items, list) or not 4 <= len(items) <= 8:
        raise Z98ContractError("atom-batch-v2.items 必须为 4～8 项")
    returned: list[str] = []
    item_fields = {
        "slot_id",
        "status",
        "atom",
        "split_span_ids",
        "missing_context_codes",
    }
    valid_statuses = {"ok", "split_required", "needs_context", "unsupported"}
    for index, item in enumerate(items):
        item_row = _require_mapping(item, f"atom-batch-v2.items[{index}]")
        status = item_row.get("status")
        if status not in valid_statuses:
            raise Z98ContractError(f"atom-batch-v2.items[{index}].status 非法")
        _strict_keys(
            item_row,
            item_fields,
            f"atom-batch-v2.items[{index}]",
        )
        slot_id = _require_string(
            item_row["slot_id"],
            f"atom-batch-v2.items[{index}].slot_id",
        )
        if not _SLOT_ID_RE.fullmatch(slot_id):
            raise Z98ContractError("atom-batch-v2 slot_id 格式非法")
        returned.append(slot_id)
        if status == "ok":
            validate_patch(item_row["atom"])
            if item_row["split_span_ids"] or item_row["missing_context_codes"]:
                raise Z98ContractError("ok 只能填写 atom")
        elif status == "split_required":
            if item_row["atom"] is not None or item_row["missing_context_codes"]:
                raise Z98ContractError("split_required 只准填写 split_span_ids")
            _require_span_ids(
                item_row["split_span_ids"],
                f"atom-batch-v2.items[{index}].split_span_ids",
            )
        elif status == "needs_context":
            if item_row["atom"] is not None or item_row["split_span_ids"]:
                raise Z98ContractError(
                    "needs_context 只准填写 missing_context_codes"
                )
            context_codes = _require_string_list(
                item_row["missing_context_codes"],
                f"atom-batch-v2.items[{index}].missing_context_codes",
                allow_empty=False,
            )
            if any(
                code
                not in {
                    "speaker",
                    "antecedent",
                    "condition",
                    "source",
                }
                for code in context_codes
            ):
                raise Z98ContractError("needs_context 原因码非法")
        else:
            if (
                item_row["atom"] is not None
                or item_row["split_span_ids"]
                or item_row["missing_context_codes"]
            ):
                raise Z98ContractError("unsupported 不得夹带内容")
        if status != "needs_context" and item_row["missing_context_codes"]:
            raise Z98ContractError("非 needs_context 不得填写原因码")
        if status != "split_required" and item_row["split_span_ids"]:
            raise Z98ContractError("非 split_required 不得填写 span IDs")
        if status != "ok" and item_row["atom"] is not None:
            raise Z98ContractError("非 ok 不得填写 atom")
    if returned != expected:
        raise Z98ContractError("返回 slot 顺序或全集与程序预给值不相等")
    receipt = _require_mapping(row["receipt"], "atom-batch-v2.receipt")
    _strict_keys(
        receipt,
        {"returned_slot_ids"},
        "atom-batch-v2.receipt",
    )
    receipt_slots = _require_string_list(
        receipt["returned_slot_ids"],
        "atom-batch-v2.receipt.returned_slot_ids",
        allow_empty=False,
    )
    if receipt_slots != expected:
        raise Z98ContractError("receipt slot 集与程序预给值不相等")
    return deepcopy(dict(row))


def authorize_context_expansion(previous_expansion_count: int) -> int:
    """每个 slot 最多批准一次 needs_context 扩窗。"""

    if (
        not isinstance(previous_expansion_count, int)
        or isinstance(previous_expansion_count, bool)
        or previous_expansion_count < 0
    ):
        raise Z98ContractError("扩窗计数必须是非负整数")
    if previous_expansion_count >= 1:
        raise Z98ContractError("同一 slot 最多扩窗一次")
    return 1


_RFU_TOP_FIELDS = frozenset(
    {
        "schema_version",
        "reference_version",
        "chapter_id",
        "rfu_id",
        "source_order",
        "fact_head",
        "required_qualifiers",
        "optional_details",
        "minimal_support_sets",
        "pathology_tags",
        "criticality",
        "weight",
        "provenance",
    }
)
_RFU_PROVENANCE_FIELDS = frozenset(
    {
        "origin",
        "annotators",
        "adjudicator",
        "source_sha256",
        "anchor_catalog_sha256",
    }
)
_CLAIM_TOP_FIELDS = frozenset(
    {
        "schema_version",
        "chapter_id",
        "event_id",
        "claim_id",
        "clause_index",
        "event_text",
        "fact_head",
        "qualifiers",
        "claim_components",
        "listed_anchor_ids",
        "is_addressable",
        "atomic_clause_count",
        "parse_origin",
        "candidate_output_sha256",
        "source_event_ids",
    }
)


def validate_hardened_rfu(value: Any) -> dict[str, Any]:
    """在 Z97 合同之上只收紧未知字段，不改变已定义字段语义。"""

    try:
        validated = validate_rfu(value)
    except Z97ContractError as exc:
        raise Z98ContractError(str(exc)) from exc
    row = _require_mapping(validated, "RFU")
    unknown_top = set(row) - _RFU_TOP_FIELDS
    if unknown_top:
        raise Z98ContractError(f"RFU 含未知字段：{sorted(unknown_top)}")
    for index, support in enumerate(row["minimal_support_sets"]):
        support_row = _require_mapping(
            support,
            f"RFU.minimal_support_sets[{index}]",
        )
        extra = set(support_row) - {"support_set_id", "anchor_ids", "minimality"}
        if extra:
            raise Z98ContractError(
                "RFU minimal_support_sets 含未知字段："
                f"{sorted(extra)}"
            )
    provenance = _require_mapping(row["provenance"], "RFU.provenance")
    extra_provenance = set(provenance) - _RFU_PROVENANCE_FIELDS
    if extra_provenance:
        raise Z98ContractError(
            f"RFU provenance 含未知字段：{sorted(extra_provenance)}"
        )
    for detail in row["optional_details"]:
        if not (
            detail is None
            or isinstance(detail, (str, int, float, bool))
        ):
            raise Z98ContractError(
                "RFU optional_details 只接受 JSON 基础值"
            )
        if isinstance(detail, float) and not math.isfinite(detail):
            raise Z98ContractError(
                "RFU optional_details 不接受非有限数字"
            )
    return deepcopy(dict(row))


def validate_hardened_candidate_claim(value: Any) -> dict[str, Any]:
    """在 Z97 CandidateClaim 之上收紧顶层和限定对象。"""

    try:
        validated = validate_candidate_claim(value)
    except Z97ContractError as exc:
        raise Z98ContractError(str(exc)) from exc
    row = _require_mapping(validated, "CandidateClaim")
    unknown_top = set(row) - _CLAIM_TOP_FIELDS
    if unknown_top:
        raise Z98ContractError(
            f"CandidateClaim 含未知字段：{sorted(unknown_top)}"
        )
    for index, qualifier in enumerate(row["qualifiers"]):
        qualifier_row = _require_mapping(
            qualifier,
            f"CandidateClaim.qualifiers[{index}]",
        )
        extra = set(qualifier_row) - {
            "qualifier_id",
            "type",
            "normalized_value",
        }
        if extra:
            raise Z98ContractError(
                f"CandidateClaim qualifier 含未知字段：{sorted(extra)}"
            )
    return deepcopy(dict(row))


def _external_allowlist() -> frozenset[str]:
    paths = {
        f"{RETRY03_ROOT}/main/usage.jsonl",
        Z96_SUMMARY_PATH,
        Z94_SINGLE_CONTRACT_PATH,
        Z97_RFU_SCHEMA_PATH,
        Z97_CLAIM_SCHEMA_PATH,
    }
    for chapter in CHAPTER_SPECS:
        paths.add(f"{RETRY03_ROOT}/main/01_extract/events/{chapter}.json")
        paths.add(f"{RETRY03_ROOT}/inputs/evidence_catalogs/{chapter}.json")
        paths.add(f"{RETRY03_ROOT}/prepared_requests/{chapter}.json")
        paths.add(
            f"{RETRY03_ROOT}/main/requests/neutral_extract/"
            f"z83_main_{chapter}_request.json"
        )
    return frozenset(paths)


class SourceReader:
    """只允许读取第98道步一登记过的精确路径。"""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.allowed_paths = _external_allowlist()
        self.read_ledger: list[dict[str, Any]] = []

    def read_bytes(self, relative_path: str) -> bytes:
        if relative_path not in self.allowed_paths:
            raise Z98ContractError(f"SourceReader 拒绝未登记路径：{relative_path}")
        lowered = relative_path.casefold()
        forbidden = (
            "/gold",
            "score_only",
            "scoring_answers",
            "adjudication",
            "answer_bootstrap",
            "判词",
            "金标",
            "答案",
        )
        if any(marker in lowered for marker in forbidden):
            raise Z98ContractError(f"SourceReader 拒绝答案面路径：{relative_path}")
        resolved = (self.repo_root / relative_path).resolve()
        if self.repo_root not in resolved.parents:
            raise Z98ContractError("SourceReader 路径越出仓库")
        data = resolved.read_bytes()
        self.read_ledger.append(
            {
                "path": relative_path,
                "sha256": sha256_bytes(data),
                "byte_count": len(data),
            }
        )
        return data

    def read_json(self, relative_path: str) -> Any:
        return json.loads(self.read_bytes(relative_path))


def event_risk_breakdown(event: Mapping[str, Any]) -> dict[str, int]:
    """只看本轮事件与自带锚，给出可解释、稳定的风险排序分。"""

    text = _require_string(event.get("event"), "event.event")
    anchors = event.get("anchors")
    if not isinstance(anchors, list):
        raise Z98ContractError("event.anchors 必须是数组")
    marker_hits = sum(text.count(marker) for marker in _RISK_MARKERS)
    punctuation_hits = sum(text.count(marker) for marker in _PUNCTUATION_MARKERS)
    nonspace_length = len("".join(text.split()))
    anchor_count = len(anchors)
    score = (
        anchor_count * 50
        + marker_hits * 20
        + punctuation_hits * 10
        + min(nonspace_length, 100)
    )
    return {
        "anchor_count": anchor_count,
        "marker_hits": marker_hits,
        "punctuation_hits": punctuation_hits,
        "nonspace_length_capped": min(nonspace_length, 100),
        "risk_score": score,
    }


def select_slots(
    chapter_id: str,
    events: Sequence[Mapping[str, Any]],
    evidence_entries: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """按预写规则选章内小额修复位，不读任何答案。"""

    limit = min(6, math.floor(len(events) * 0.10))
    if limit < 4:
        raise Z98ContractError("本实验批式合同至少需要四个章内选择位")
    evidence_ids = [
        _require_string(entry.get("anchor_id"), "evidence.anchor_id")
        for entry in evidence_entries
    ]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise Z98ContractError(f"{chapter_id} 冻结目录锚 ID 重复")
    evidence_by_id = {
        str(entry["anchor_id"]): dict(entry) for entry in evidence_entries
    }
    index_by_id = {anchor_id: index for index, anchor_id in enumerate(evidence_ids)}
    ranked: list[tuple[int, str, Mapping[str, Any], dict[str, int]]] = []
    for event in events:
        event_id = _require_string(event.get("event_id"), "event.event_id")
        if not _EVENT_ID_RE.fullmatch(event_id):
            raise Z98ContractError(f"事件 ID 非法：{event_id}")
        breakdown = event_risk_breakdown(event)
        ranked.append(
            (
                -breakdown["risk_score"],
                event_id,
                event,
                breakdown,
            )
        )
    ranked.sort(key=lambda row: (row[0], row[1]))
    selected: list[dict[str, Any]] = []
    for slot_number, (_, event_id, event, breakdown) in enumerate(
        ranked[:limit],
        start=1,
    ):
        event_anchors = event.get("anchors")
        assert isinstance(event_anchors, list)
        raw_anchor_ids: list[str] = []
        for anchor in event_anchors:
            anchor_row = _require_mapping(anchor, f"{event_id}.anchors")
            anchor_id = _require_string(
                anchor_row.get("anchor_id"),
                f"{event_id}.anchor_id",
            )
            if anchor_id not in evidence_by_id:
                raise Z98ContractError(
                    f"{event_id} 引用的 {anchor_id} 不在冻结目录"
                )
            raw_anchor_ids.append(anchor_id)
        if not raw_anchor_ids:
            raise Z98ContractError(f"{event_id} 没有源锚，不能进入本轮")
        candidate_indices: set[int] = set()
        for anchor_id in raw_anchor_ids:
            anchor_index = index_by_id[anchor_id]
            for candidate_index in range(
                max(0, anchor_index - 1),
                min(len(evidence_entries), anchor_index + 2),
            ):
                candidate_indices.add(candidate_index)
        candidate_ids = [evidence_ids[index] for index in sorted(candidate_indices)]
        selected.append(
            {
                "slot_id": f"SLOT-{chapter_id}-{slot_number:02d}",
                "chapter_id": chapter_id,
                "source_event_id": event_id,
                "source_event": event["event"],
                "source_span_ids": [
                    f"{chapter_id}:{anchor_id}" for anchor_id in raw_anchor_ids
                ],
                "anchor_candidates": [
                    {
                        "span_id": f"{chapter_id}:{anchor_id}",
                        "quote": evidence_by_id[anchor_id]["quote"],
                    }
                    for anchor_id in candidate_ids
                ],
                "risk_breakdown": breakdown,
                "selection_tiebreak": "risk_score_desc_then_event_id_asc",
            }
        )
    return selected


def make_batch_groups(
    chapter_id: str,
    selected_slots: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """按章内共享锚邻域排序分组，绝不跨章拼批。"""

    if not 4 <= len(selected_slots) <= 6:
        raise Z98ContractError("本轮每章必须有 4～6 个选择位")
    for slot in selected_slots:
        if slot.get("chapter_id") != chapter_id:
            raise Z98ContractError("批式分组不得跨章")
    slot_anchor_sets = {
        str(slot["slot_id"]): {
            str(item["span_id"]) for item in slot["anchor_candidates"]
        }
        for slot in selected_slots
    }
    overlap_edges: list[list[str]] = []
    slot_ids = sorted(slot_anchor_sets)
    for left_index, left in enumerate(slot_ids):
        for right in slot_ids[left_index + 1 :]:
            if slot_anchor_sets[left] & slot_anchor_sets[right]:
                overlap_edges.append([left, right])
    ordered = sorted(
        selected_slots,
        key=lambda slot: (
            min(str(item["span_id"]) for item in slot["anchor_candidates"]),
            str(slot["slot_id"]),
        ),
    )
    return [
        {
            "batch_id": f"BATCH-{chapter_id}-01",
            "chapter_id": chapter_id,
            "slot_ids": [str(slot["slot_id"]) for slot in ordered],
            "shared_anchor_neighborhood_edges": overlap_edges,
            "grouping_rule": (
                "章内共享锚邻域连通优先；本章总位数已在4到8，"
                "不足4的余组只可与本章前组机械合并"
            ),
            "cross_chapter_merge": False,
        }
    ]


def allocate_integer_budget(total: int, count: int) -> list[int]:
    """把整数 token 帽稳定分配给逻辑请求。"""

    if total < 0 or count < 1:
        raise Z98ContractError("预算分配参数非法")
    base, remainder = divmod(total, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def build_budget_plan(
    chapter_id: str,
    *,
    selected_count: int,
    batch_count: int,
) -> dict[str, Any]:
    """冻结单章、双合同、双模型臂的调用与 token 上限。"""

    t1 = int(CHAPTER_SPECS[chapter_id]["t1_total_tokens"])
    p2_cap = math.floor(t1 * 0.25)
    verifier_cap = math.floor(t1 * 0.10)
    whole_chain_cap = math.floor(t1 * 1.35)
    if t1 + p2_cap + verifier_cap > whole_chain_cap:
        raise Z98ContractError("预算公式超过整链 1.35 倍上限")
    contracts = {
        "single_patch": {
            "p2_logical_requests": selected_count,
            "p2_per_request_token_caps": allocate_integer_budget(
                p2_cap,
                selected_count,
            ),
            "verification_logical_requests": selected_count,
            "verification_per_request_token_caps": allocate_integer_budget(
                verifier_cap,
                selected_count,
            ),
        },
        "atom_batch_v2": {
            "p2_logical_requests": batch_count,
            "p2_per_request_token_caps": allocate_integer_budget(
                p2_cap,
                batch_count,
            ),
            "verification_logical_requests": batch_count,
            "verification_per_request_token_caps": allocate_integer_budget(
                verifier_cap,
                batch_count,
            ),
        },
    }
    for contract in contracts.values():
        contract["p2_token_cap"] = sum(contract["p2_per_request_token_caps"])
        contract["verification_token_cap"] = sum(
            contract["verification_per_request_token_caps"]
        )
        contract["future_new_logical_requests"] = (
            contract["p2_logical_requests"]
            + contract["verification_logical_requests"]
        )
        contract["future_new_token_cap"] = (
            contract["p2_token_cap"] + contract["verification_token_cap"]
        )
        contract["actual_p2_usage_tokens"] = None
        contract["actual_verification_usage_tokens"] = None
    providers = {
        "flash": {
            "provider": "sensenova",
            "model": "deepseek-v4-flash",
            "pricing_status": "step2_usage_and_provider_bill_required",
        },
        "pro": {
            "provider": "tencent_tokenhub",
            "model": "deepseek-v4-pro-202606",
            "pricing_status": "step2_usage_and_provider_bill_required",
        },
    }
    return {
        "chapter_id": chapter_id,
        "selected_repair_count": selected_count,
        "historical_t1_reused_tokens": t1,
        "t1_new_calls": 0,
        "p2_token_cap": p2_cap,
        "independent_verification_token_cap": verifier_cap,
        "whole_chain_token_cap": whole_chain_cap,
        "whole_chain_formula_pass": (
            t1 + p2_cap + verifier_cap <= whole_chain_cap
        ),
        "actual_repair_usage_tokens": None,
        "actual_independent_verification_usage_tokens": None,
        "budget_compliance_status": "PRE_REGISTERED_NOT_MEASURED",
        "budget_gate_unit": "chapter_id × provider_lane × contract_mode",
        "budget_gate_formula": "T1 + T2 + qT3 <= floor(1.35 * T1)",
        "contract_modes": contracts,
        "future_model_lanes": providers,
        "monetary_cost_boundary": (
            "步一不联网、不猜单价；步二按每条usage和供应商账单分臂入账"
        ),
    }

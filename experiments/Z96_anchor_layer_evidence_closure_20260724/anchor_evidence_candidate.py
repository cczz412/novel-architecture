"""A+ 锚层与证据闭包候选。

这个模块只做确定性集合与跨度运算。语义承托答案必须由独立冻结夹具传入；
模块不会从事件句自动猜“必要锚”，也不会修改事件、锚、金标或历史成绩。
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from tools.zbatch_modules.extraction_coverage import (
    CoverageDiagnosticError,
    locate_catalog_spans,
)


class Z96CandidateError(ValueError):
    """候选输入或机械验收不符合冻结合同。"""


ANCHOR_ID_PATTERN = re.compile(r"^E\d{4}$")
TIME_CUES = (
    "随后",
    "之后",
    "此前",
    "当时",
    "此时",
    "早晨",
    "上午",
    "中午",
    "下午",
    "傍晚",
    "晚上",
    "第二天",
    "明天",
    "昨天",
    "后来",
)
COREFERENCE_CUES = ("他", "她", "它", "他们", "她们", "此人", "对方", "后者", "前者")
ALLOWED_EXPANSION_REASONS = {
    "SOURCE_SPAN_OUTSIDE_INITIAL_CLOSURE",
    "COREFERENCE_UNRESOLVED",
    "NEGATION_OR_CONDITION_BOUNDARY",
    "DIALOGUE_TURN_BOUNDARY",
}


def stable_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def catalog_entries(catalog: Any) -> list[dict[str, Any]]:
    if isinstance(catalog, dict):
        entries = catalog.get("entries")
    else:
        entries = catalog
    if not isinstance(entries, list) or not entries:
        raise Z96CandidateError("冻结锚目录没有可用 entries")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in entries:
        if not isinstance(row, dict):
            raise Z96CandidateError("冻结锚目录条目不是对象")
        anchor_id = row.get("anchor_id")
        quote = row.get("quote")
        if (
            not isinstance(anchor_id, str)
            or ANCHOR_ID_PATTERN.fullmatch(anchor_id) is None
            or not isinstance(quote, str)
            or not quote
        ):
            raise Z96CandidateError("冻结锚目录条目缺合法 anchor_id 或 quote")
        if anchor_id in seen:
            raise Z96CandidateError(f"冻结锚目录 anchor_id 重复：{anchor_id}")
        seen.add(anchor_id)
        result.append(dict(row))
    return result


def aligned_anchor_rows(chapter_text: str, entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    try:
        spans = locate_catalog_spans(chapter_text, [dict(row) for row in entries])
    except CoverageDiagnosticError as exc:
        raise Z96CandidateError(str(exc)) from exc
    rows: list[dict[str, Any]] = []
    for order, row in enumerate(entries):
        anchor_id = str(row["anchor_id"])
        start, end = spans[anchor_id]
        rows.append(
            {
                "anchor_id": anchor_id,
                "order": order,
                "start": start,
                "end": end,
                "quote": str(row["quote"]),
            }
        )
    return rows


def _order_index(aligned: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {str(row["anchor_id"]): int(row["order"]) for row in aligned}


def topology_candidate_ids(
    aligned: Sequence[Mapping[str, Any]],
    seed_anchor_ids: Sequence[str],
    *,
    max_hops: int = 2,
    maximum_between_gap: int = 8,
) -> list[str]:
    """按真实正文顺序召回锚；编号本身不承担区间语义。"""
    if max_hops < 0 or max_hops > 2:
        raise Z96CandidateError("max_hops 必须在 0..2")
    order = _order_index(aligned)
    seeds = list(dict.fromkeys(seed_anchor_ids))
    if not seeds:
        raise Z96CandidateError("候选召回缺 seed_anchor_ids")
    unknown = [anchor_id for anchor_id in seeds if anchor_id not in order]
    if unknown:
        raise Z96CandidateError(f"seed 锚不在冻结目录：{unknown}")

    positions = sorted(order[anchor_id] for anchor_id in seeds)
    selected: set[int] = set(positions)
    if len(positions) >= 2 and positions[-1] - positions[0] <= maximum_between_gap:
        selected.update(range(positions[0], positions[-1] + 1))
    for position in tuple(selected):
        selected.update(
            index
            for index in range(position - max_hops, position + max_hops + 1)
            if 0 <= index < len(aligned)
        )
    return [str(aligned[index]["anchor_id"]) for index in sorted(selected)]


def endpoint_span_pattern(
    *,
    aligned: Sequence[Mapping[str, Any]],
    selected_anchor_ids: Sequence[str],
    necessary_anchor_ids: Sequence[str],
) -> bool:
    """检测“只挂首尾、漏中间必要锚”；以正文顺序为准，不按 ID 猜范围。"""
    order = _order_index(aligned)
    selected = set(selected_anchor_ids)
    necessary = set(necessary_anchor_ids)
    if not necessary or not necessary.issubset(order):
        raise Z96CandidateError("必要锚集合为空或含目录外锚")
    positions = sorted(order[anchor_id] for anchor_id in necessary)
    if len(positions) < 3 or positions[-1] - positions[0] < 2:
        return False
    left = str(aligned[positions[0]]["anchor_id"])
    right = str(aligned[positions[-1]]["anchor_id"])
    interior = {
        str(aligned[index]["anchor_id"])
        for index in positions[1:-1]
    }
    return left in selected and right in selected and bool(interior - selected) and not bool(interior & selected)


def _claim_is_supported(claim: Mapping[str, Any], selected: set[str]) -> bool:
    groups = claim.get("sufficient_support_groups")
    if not isinstance(groups, list) or not groups:
        raise Z96CandidateError("主张缺 sufficient_support_groups")
    for group in groups:
        if not isinstance(group, list) or not group:
            raise Z96CandidateError("支撑组必须是非空数组")
        if set(map(str, group)).issubset(selected):
            return True
    return False


def evaluate_anchor_set(
    claim_units: Sequence[Mapping[str, Any]],
    selected_anchor_ids: Sequence[str],
) -> dict[str, Any]:
    selected = set(selected_anchor_ids)
    if len(selected) != len(selected_anchor_ids):
        raise Z96CandidateError("selected_anchor_ids 重复")
    claim_results: list[dict[str, Any]] = []
    supporting_selected: set[str] = set()
    for claim in claim_units:
        claim_id = str(claim.get("claim_id", ""))
        if not claim_id:
            raise Z96CandidateError("主张缺 claim_id")
        supported = _claim_is_supported(claim, selected)
        groups = claim["sufficient_support_groups"]
        if supported:
            for group in groups:
                group_set = set(map(str, group))
                if group_set.issubset(selected):
                    supporting_selected.update(group_set)
        claim_results.append({"claim_id": claim_id, "supported": supported})
    unsupported_selected = sorted(selected - supporting_selected)
    asr_full = all(row["supported"] for row in claim_results) and not unsupported_selected
    return {
        "ASR_full": asr_full,
        "claim_results": claim_results,
        "unsupported_selected_anchor_ids": unsupported_selected,
        "decision": "PASS" if asr_full else "REJECT",
        "reason_codes": [] if asr_full else (
            (["CLAIM_NOT_FULLY_SUPPORTED"] if not all(row["supported"] for row in claim_results) else [])
            + (["ANCHOR_DOES_NOT_SUPPORT_ANY_CLAIM"] if unsupported_selected else [])
        ),
    }


def derive_minimal_anchor_sets(
    claim_units: Sequence[Mapping[str, Any]],
    candidate_anchor_ids: Sequence[str],
    *,
    maximum_solutions: int = 64,
) -> dict[str, Any]:
    candidates = list(dict.fromkeys(candidate_anchor_ids))
    if len(candidates) != len(candidate_anchor_ids):
        raise Z96CandidateError("candidate_anchor_ids 重复")
    if len(candidates) > 18:
        raise Z96CandidateError("候选锚超过18个，拒绝指数枚举")
    solutions: list[list[str]] = []
    for size in range(1, len(candidates) + 1):
        for combination in itertools.combinations(candidates, size):
            result = evaluate_anchor_set(claim_units, combination)
            if result["ASR_full"]:
                solutions.append(list(combination))
                if len(solutions) >= maximum_solutions:
                    break
        if solutions:
            break
    return {
        "minimum_size": len(solutions[0]) if solutions else None,
        "primary": solutions[0] if solutions else [],
        "parallel_minimum_solutions": solutions,
        "parallel_solution_count": len(solutions),
        "complete_solution_found": bool(solutions),
    }


def render_reverse_check(
    source_claim_ids: Sequence[str],
    rendered_claim_ids: Sequence[str],
) -> dict[str, Any]:
    source = list(source_claim_ids)
    rendered = list(rendered_claim_ids)
    missing = sorted(set(source) - set(rendered))
    added = sorted(set(rendered) - set(source))
    duplicated = sorted({claim_id for claim_id in rendered if rendered.count(claim_id) > 1})
    passed = not missing and not added and not duplicated and len(source) == len(rendered)
    return {
        "passed": passed,
        "missing_claim_ids": missing,
        "new_claim_ids": added,
        "duplicated_claim_ids": duplicated,
        "decision": "PASS" if passed else "REJECT",
    }


def conservative_token_proxy(value: Any) -> int:
    """按模型可见稳定 JSON 的非空白码点计数；这是保守代理，不冒充供应商 usage。"""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sum(1 for char in text if not char.isspace())


def nearest_rank_percentile(values: Sequence[int], percentile: float) -> int:
    if not values:
        raise Z96CandidateError("百分位输入为空")
    if not 0 < percentile <= 1:
        raise Z96CandidateError("百分位必须在 (0,1]")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def build_lightweight_chapter_map(
    chapter_text: str,
    aligned: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    paragraphs = [part for part in re.split(r"\n[ \t\u3000]*\n|\n", chapter_text) if part.strip()]
    time_signal_ids: list[str] = []
    speaker_turn_ids: list[str] = []
    coreference_cue_ids: list[str] = []
    for row in aligned:
        anchor_id = str(row["anchor_id"])
        quote = str(row["quote"])
        if any(cue in quote for cue in TIME_CUES):
            time_signal_ids.append(f"TIME:{anchor_id}")
        if "“" in quote or "”" in quote or '"' in quote:
            speaker_turn_ids.append(f"TURN:{anchor_id}")
        if any(cue in quote for cue in COREFERENCE_CUES):
            coreference_cue_ids.append(f"COREF-CUE:{anchor_id}")
    ordered_anchor_ids = [str(row["anchor_id"]) for row in aligned]
    paragraph_ids = [f"P{index:04d}" for index in range(1, len(paragraphs) + 1)]

    def compact_index(values: Sequence[str]) -> dict[str, Any]:
        encoded = stable_json_bytes(list(values))
        return {
            "count": len(values),
            "first_id": values[0] if values else None,
            "last_id": values[-1] if values else None,
            "ordered_ids_sha256": sha256_bytes(encoded),
        }

    full_map = {
        "map_version": "z96-lightweight-chapter-map-v1",
        "ordered_anchor_ids": ordered_anchor_ids,
        "paragraph_ids": paragraph_ids,
        "scene_ids": ["SCENE-0001"],
        "time_signal_ids": time_signal_ids,
        "entity_ids": [],
        "speaker_turn_ids": speaker_turn_ids,
        "coreference_link_ids": [],
        "unresolved_coreference_cue_ids": coreference_cue_ids,
        "limitations": [
            "零路由重放不做实体识别或指代消歧；对应字段保留合同位置但不伪造结果。",
            "正文与短引只用于本地候选构造，不写入现役件。",
        ],
    }
    map_sha256 = sha256_bytes(stable_json_bytes(full_map))
    full_map["map_sha256"] = map_sha256
    full_map["model_visible_compact"] = {
        "map_version": full_map["map_version"],
        "map_sha256": map_sha256,
        "anchor_index": compact_index(ordered_anchor_ids),
        "paragraph_index": compact_index(paragraph_ids),
        "scene_ids": full_map["scene_ids"],
        "time_signal_index": compact_index(time_signal_ids),
        "entity_index": compact_index([]),
        "speaker_turn_index": compact_index(speaker_turn_ids),
        "coreference_link_index": compact_index([]),
        "unresolved_coreference_cue_index": compact_index(coreference_cue_ids),
    }
    return full_map


def build_evidence_closure_packet(
    *,
    case_id: str,
    event_text: str,
    chapter_map: Mapping[str, Any],
    aligned: Sequence[Mapping[str, Any]],
    seed_anchor_ids: Sequence[str],
    claim_span_seed_anchor_ids: Sequence[str] | None = None,
    claim_units_for_fixture: Sequence[Mapping[str, Any]] | None = None,
    necessary_anchor_ids_for_fixture: Sequence[str] | None = None,
    controlled_expansion_reason: str | None = None,
    controlled_expansion_seed_anchor_ids: Sequence[str] | None = None,
    max_hops: int = 2,
) -> dict[str, Any]:
    span_seeds = list(claim_span_seed_anchor_ids or [])
    candidate_ids = topology_candidate_ids(
        aligned,
        list(seed_anchor_ids) + span_seeds,
        max_hops=max_hops,
    )
    expansion_seeds = list(controlled_expansion_seed_anchor_ids or [])
    if controlled_expansion_reason is None and expansion_seeds:
        raise Z96CandidateError("受控扩窗给了 seed 但缺原因")
    if controlled_expansion_reason is not None:
        if controlled_expansion_reason not in ALLOWED_EXPANSION_REASONS:
            raise Z96CandidateError("受控扩窗原因不在冻结枚举")
        if not expansion_seeds:
            raise Z96CandidateError("受控扩窗缺 expansion seed")
        expanded = topology_candidate_ids(
            aligned,
            expansion_seeds,
            max_hops=max_hops,
        )
        order = _order_index(aligned)
        candidate_ids = sorted(
            set(candidate_ids) | set(expanded),
            key=order.__getitem__,
        )
    row_map = {str(row["anchor_id"]): row for row in aligned}
    positions = sorted(row_map[anchor_id]["order"] for anchor_id in candidate_ids)
    left_neighbor = (
        str(aligned[positions[0] - 1]["anchor_id"]) if positions and positions[0] > 0 else None
    )
    right_neighbor = (
        str(aligned[positions[-1] + 1]["anchor_id"])
        if positions and positions[-1] + 1 < len(aligned)
        else None
    )
    compact_map = chapter_map.get("model_visible_compact")
    if not isinstance(compact_map, Mapping):
        raise Z96CandidateError("全章轻量地图缺 model_visible_compact")
    model_visible = {
        "contract_version": "z96-evidence-closure-model-visible-v1",
        "case_id": case_id,
        "event": event_text,
        "chapter_map": dict(compact_map),
        "evidence_spans": [
            {
                "span_id": f"SPAN:{anchor_id}",
                "anchor_id": anchor_id,
                "quote": str(row_map[anchor_id]["quote"]),
                "start": int(row_map[anchor_id]["start"]),
                "end": int(row_map[anchor_id]["end"]),
            }
            for anchor_id in candidate_ids
        ],
        "alternative_atom_lattice": {
            "mode": "single_fact_candidates_only",
            "atom_ids": [
                str(row["claim_id"])
                for row in (claim_units_for_fixture or [])
                if isinstance(row, Mapping) and row.get("claim_id")
            ],
        },
        "boundary_context": {
            "left_anchor_id": left_neighbor,
            "right_anchor_id": right_neighbor,
        },
        "candidate_anchor_ids_are_seeds_not_whitelist": True,
        "claim_span_seed_count": len(span_seeds),
        "controlled_expansion_reason": controlled_expansion_reason,
        "max_relation_hops": max_hops,
    }
    necessary = list(dict.fromkeys(necessary_anchor_ids_for_fixture or []))
    recalled = [anchor_id for anchor_id in necessary if anchor_id in candidate_ids]
    offline_evaluation = {
        "fixture_used": necessary_anchor_ids_for_fixture is not None,
        "fixture_not_model_visible": True,
        "necessary_anchor_ids": necessary,
        "recalled_necessary_anchor_ids": recalled,
        "necessary_span_recall": (
            len(recalled) / len(necessary) if necessary else None
        ),
    }
    return {
        "schema_version": "z96-evidence-closure-packet-v1",
        "model_visible": model_visible,
        "program_side_full_chapter_map": dict(chapter_map),
        "offline_evaluation": offline_evaluation,
        "metrics": {
            "input_token_proxy": conservative_token_proxy(model_visible),
            "token_proxy_contract": "non_whitespace_unicode_codepoint_count_v1",
            "controlled_expansion_count": 1 if controlled_expansion_reason else 0,
        },
    }


def build_claim_fixture_from_required_anchors(
    *,
    case_id: str,
    required_anchor_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """离线验收夹具：每个冻结必要锚对应一个独立支撑单元。"""
    return [
        {
            "claim_id": f"{case_id}:CLAIM-{index:03d}",
            "sufficient_support_groups": [[anchor_id]],
            "source": "frozen_human_support_fixture",
        }
        for index, anchor_id in enumerate(dict.fromkeys(required_anchor_ids), 1)
    ]


def evaluate_fixture_replay(
    *,
    case_id: str,
    aligned: Sequence[Mapping[str, Any]],
    selected_anchor_ids: Sequence[str],
    necessary_anchor_ids: Sequence[str],
    claim_span_seed_anchor_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    claims = build_claim_fixture_from_required_anchors(
        case_id=case_id,
        required_anchor_ids=necessary_anchor_ids,
    )
    candidates = topology_candidate_ids(
        aligned,
        list(selected_anchor_ids) + list(claim_span_seed_anchor_ids or []),
        max_hops=2,
    )
    input_result = evaluate_anchor_set(claims, selected_anchor_ids)
    endpoint = endpoint_span_pattern(
        aligned=aligned,
        selected_anchor_ids=selected_anchor_ids,
        necessary_anchor_ids=necessary_anchor_ids,
    )
    if endpoint:
        input_result = dict(input_result)
        input_result["decision"] = "REJECT"
        input_result["ASR_full"] = False
        input_result["reason_codes"] = sorted(
            set(input_result["reason_codes"] + ["ENDPOINT_SPAN_PATTERN"])
        )
    minimal = derive_minimal_anchor_sets(claims, candidates)
    candidate_result = (
        evaluate_anchor_set(claims, minimal["primary"])
        if minimal["primary"]
        else {
            "ASR_full": False,
            "decision": "REJECT",
            "reason_codes": ["NO_COMPLETE_ANCHOR_SET"],
            "claim_results": [],
            "unsupported_selected_anchor_ids": [],
        }
    )
    reverse = render_reverse_check(
        [str(row["claim_id"]) for row in claims],
        [str(row["claim_id"]) for row in claims],
    )
    if not reverse["passed"]:
        candidate_result = dict(candidate_result)
        candidate_result["decision"] = "REJECT"
        candidate_result["ASR_full"] = False
        candidate_result["reason_codes"] = sorted(
            set(candidate_result["reason_codes"] + ["RENDER_REVERSE_CHECK_FAILED"])
        )
    return {
        "case_id": case_id,
        "selected_anchor_ids": list(selected_anchor_ids),
        "necessary_anchor_ids": list(necessary_anchor_ids),
        "program_candidate_anchor_ids": candidates,
        "claim_span_seed_anchor_ids": list(claim_span_seed_anchor_ids or []),
        "input_gate": input_result,
        "endpoint_span_pattern": endpoint,
        "minimal_complete_anchor_set": minimal,
        "candidate_gate": candidate_result,
        "render_reverse_check": reverse,
        "fixture_boundary": "冻结人工判词只用于离线验收，不是运行时自动真值。",
    }


def tree_fingerprint(root: Path, relative_paths: Iterable[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for relative in sorted(set(relative_paths)):
        path = root / relative
        if path.is_file():
            rows.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        elif path.is_dir():
            for child in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
                child_relative = child.relative_to(root).as_posix()
                rows.append(
                    {
                        "path": child_relative,
                        "bytes": child.stat().st_size,
                        "sha256": sha256_file(child),
                    }
                )
        else:
            raise Z96CandidateError(f"保护路径不存在：{relative}")
    summary = sha256_bytes(stable_json_bytes(rows))
    return {"file_count": len(rows), "summary_sha256": summary, "rows": rows}

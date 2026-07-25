#!/usr/bin/env python3
"""V02/C7：把冻结的 36 行人工判词队列导出成 Notion 安全表格。

这个工具只做展示层转换，不做语义判断：

- 保留 C6 队列原顺序与原选项顺序；
- CZ 判词列必须全部为空；
- 不输出正式金标 claim 或证据短引；
- 不生成推荐、相似度或模型建议；
- 候选事件句、候选锚 ID 与正文区间只作客观速查。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
C1_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "C_anchor_first_experiment"
)
C4_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C4_r03_20260725"
C6_QUEUE = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C6_control_and_crosswalk"
    / "crosswalk/human_verdict_queue.json"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C7_human_verdict_workspace"
)

EXPECTED_QUEUE_SHA256 = (
    "071ac5f887721339e2c88b1d3785638303613264d16c056b8478adee189c0dd4"
)
CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
CASE_LABELS = {
    "B02-U0039": "B02 U0039",
    "B03-U0041": "B03 U0041",
    "B01-U0033": "B01 U0033",
}
EXPECTED_PENDING_COUNTS = {
    "B02-U0039": 4,
    "B03-U0041": 10,
    "B01-U0033": 22,
}
EXPECTED_CHOICE_COUNT_DISTRIBUTION = {
    2: 8,
    3: 2,
    11: 10,
    14: 3,
    15: 13,
}
C75_AUTO_RESOLUTION_SEQUENCES = (16, 21, 22, 26, 27, 34, 35, 36)
EXPECTED_CZ_PENDING_COUNTS_AFTER_C75 = {
    "B02-U0039": 4,
    "B03-U0041": 10,
    "B01-U0033": 14,
}
C75_DECISION_NOTION_PAGE_ID = "eb8821e57b67472db9f220b46110dcfd"
C75_DECISION_AT = "2026-07-25 11:12"
NO_CORRESPONDENCE = "NO_CORRESPONDENCE"


class C7ExportError(RuntimeError):
    """C7 安全导出不能从冻结实物重建。"""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C7ExportError(f"文件不存在：{path}")
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _escape_cell(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "↵")
    )


def _candidate_lookup(
    case_id: str,
) -> tuple[dict[str, dict[str, Any]], str, str]:
    candidate_path = (
        C4_RUN_DIR / f"samples/main/{case_id}/candidate/model_json.json"
    )
    catalog_path = C1_DIR / f"catalogs/{case_id}.json"
    candidate = read_json(candidate_path)
    catalog = read_json(catalog_path)

    events = candidate.get("events")
    entries = catalog.get("entries")
    if (
        not isinstance(events, list)
        or not isinstance(entries, list)
        or catalog.get("case_id") != case_id
    ):
        raise C7ExportError(f"{case_id} 候选件或锚目录结构漂移")

    anchor_lookup = {
        str(row["anchor_id"]): row
        for row in entries
        if isinstance(row, Mapping) and isinstance(row.get("anchor_id"), str)
    }
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, Mapping):
            raise C7ExportError(f"{case_id} 候选事件不是对象")
        event_id = event.get("event_id")
        event_text = event.get("event")
        anchor_ids = event.get("minimal_anchor_ids")
        if (
            not isinstance(event_id, str)
            or not isinstance(event_text, str)
            or not isinstance(anchor_ids, list)
            or not anchor_ids
            or any(not isinstance(value, str) for value in anchor_ids)
        ):
            raise C7ExportError(f"{case_id} 候选事件合同缺字段")
        if event_id in result:
            raise C7ExportError(f"{case_id} 候选事件 ID 重复：{event_id}")
        ranges: list[dict[str, Any]] = []
        for anchor_id in anchor_ids:
            anchor = anchor_lookup.get(anchor_id)
            if anchor is None:
                raise C7ExportError(
                    f"{case_id} 候选锚不在冻结目录：{anchor_id}"
                )
            ranges.append(
                {
                    "anchor_id": anchor_id,
                    "start": int(anchor["body_start_char"]),
                    "end": int(anchor["body_end_char_exclusive"]),
                }
            )
        result[event_id] = {
            "event_id": event_id,
            "event_text": event_text,
            "event_text_sha256": sha256_bytes(event_text.encode("utf-8")),
            "anchor_ids": list(anchor_ids),
            "anchor_ranges": ranges,
        }
    return result, sha256_file(candidate_path), sha256_file(catalog_path)


def _format_ranges(ranges: list[Mapping[str, Any]]) -> str:
    return "；".join(
        f"{row.get('evidence_id', row.get('anchor_id'))}"
        f"[{int(row['start'])},{int(row['end'])})"
        for row in ranges
    )


def _queue_rows_and_catalogs() -> tuple[
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    queue_sha = sha256_file(C6_QUEUE)
    if queue_sha != EXPECTED_QUEUE_SHA256:
        raise C7ExportError("C6 人工判词队列 SHA 漂移")
    queue = read_json(C6_QUEUE)
    rows = queue.get("rows")
    if (
        queue.get("schema_version") != "v02-c6-human-verdict-queue.v1"
        or queue.get("row_total") != 36
        or not isinstance(rows, list)
        or len(rows) != 36
    ):
        raise C7ExportError("C6 人工判词队列身份或 36 行合同漂移")

    counts = {case_id: 0 for case_id in CASE_ORDER}
    choice_count_distribution: dict[int, int] = {}
    seen_atoms: set[str] = set()
    lookups: dict[str, dict[str, dict[str, Any]]] = {}
    candidate_catalogs: dict[str, list[dict[str, Any]]] = {}
    candidate_shas: dict[str, str] = {}
    catalog_shas: dict[str, str] = {}
    for case_id in CASE_ORDER:
        lookup, candidate_sha, catalog_sha = _candidate_lookup(case_id)
        lookups[case_id] = lookup
        candidate_catalogs[case_id] = list(lookup.values())
        candidate_shas[case_id] = candidate_sha
        catalog_shas[case_id] = catalog_sha

    exported_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise C7ExportError("C6 人工判词队列含非对象")
        case_id = row.get("case_id")
        atom_id = row.get("atom_id")
        verdict_fields = row.get("verdict_fields")
        choices = row.get("choices")
        ranges = row.get("gold_evidence_ranges")
        if (
            case_id not in CASE_ORDER
            or not isinstance(atom_id, str)
            or atom_id in seen_atoms
            or not isinstance(verdict_fields, Mapping)
            or any(value is not None for value in verdict_fields.values())
            or not isinstance(choices, list)
            or not choices
            or choices[-1].get("choice_id") != NO_CORRESPONDENCE
            or not isinstance(ranges, list)
            or not ranges
        ):
            raise C7ExportError(f"第 {index} 行结构、顺序或空判词合同漂移")
        seen_atoms.add(atom_id)
        counts[case_id] += 1
        choice_count_distribution[len(choices)] = (
            choice_count_distribution.get(len(choices), 0) + 1
        )

        option_rows: list[dict[str, Any]] = []
        for choice in choices:
            if not isinstance(choice, Mapping):
                raise C7ExportError(f"{atom_id} 可选项不是对象")
            choice_id = choice.get("choice_id")
            event_id = choice.get("candidate_event_id")
            if choice_id == NO_CORRESPONDENCE:
                if event_id is not None:
                    raise C7ExportError(f"{atom_id} 无对应选项夹带事件 ID")
                option_rows.append(
                    {
                        "choice_id": NO_CORRESPONDENCE,
                        "candidate_event_id": None,
                    }
                )
                continue
            if (
                not isinstance(choice_id, str)
                or not isinstance(event_id, str)
                or choice_id != f"MAP_TO::{event_id}"
                or event_id not in lookups[case_id]
            ):
                raise C7ExportError(f"{atom_id} 候选选项身份漂移")
            candidate = lookups[case_id][event_id]
            if candidate["event_text_sha256"] != choice.get(
                "candidate_text_sha256"
            ):
                raise C7ExportError(f"{atom_id} 候选事件文本 SHA 漂移")
            option_rows.append(
                {
                    "choice_id": choice_id,
                    "candidate_event_id": event_id,
                }
            )

        candidate_choice_rows = [
            option
            for option in option_rows
            if option["candidate_event_id"] is not None
        ]
        is_c75_auto_resolution = index in C75_AUTO_RESOLUTION_SEQUENCES
        if is_c75_auto_resolution:
            if (
                row.get("mechanical_failure_reason") != "AMBIGUOUS_ROUTE"
                or len(candidate_choice_rows) != 1
            ):
                raise C7ExportError(
                    f"C7.5 指定第 {index} 行不符合“单候选 N:1 歧义”条件"
                )
            mechanical_resolution = candidate_choice_rows[0]["choice_id"]
            resolution_source = "C7.5"
            work_status = "MECHANICALLY_RESOLVED_C7_5"
        else:
            mechanical_resolution = None
            resolution_source = None
            work_status = "WAITING_CZ"

        exported_rows.append(
            {
                "row_id": f"C7-{index:03d}",
                "sequence": index,
                "case_id": case_id,
                "chapter": CASE_LABELS[case_id],
                "atom_id": atom_id,
                "atom_position_hint": _format_ranges(ranges),
                "candidate_event_ids": [
                    option["candidate_event_id"]
                    for option in option_rows
                    if option["candidate_event_id"] is not None
                ],
                "mechanical_failure_reason": row.get(
                    "mechanical_failure_reason"
                ),
                "choices": option_rows,
                "cz_verdict": "",
                "mechanical_resolution": mechanical_resolution,
                "resolution_source": resolution_source,
                "work_status": work_status,
            }
        )

    if counts != EXPECTED_PENDING_COUNTS:
        raise C7ExportError(f"36 行章分布漂移：{counts}")
    if choice_count_distribution != EXPECTED_CHOICE_COUNT_DISTRIBUTION:
        raise C7ExportError(
            f"选项数分布漂移：{choice_count_distribution}"
        )
    auto_sequences = tuple(
        row["sequence"]
        for row in exported_rows
        if row["work_status"] == "MECHANICALLY_RESOLVED_C7_5"
    )
    if auto_sequences != C75_AUTO_RESOLUTION_SEQUENCES:
        raise C7ExportError(f"C7.5 自动处置行漂移：{auto_sequences}")
    pending_counts = {
        case_id: sum(
            row["case_id"] == case_id and row["work_status"] == "WAITING_CZ"
            for row in exported_rows
        )
        for case_id in CASE_ORDER
    }
    if pending_counts != EXPECTED_CZ_PENDING_COUNTS_AFTER_C75:
        raise C7ExportError(f"C7.5 后待 CZ 判词章分布漂移：{pending_counts}")
    remaining_ambiguous = [
        row
        for row in exported_rows
        if row["work_status"] == "WAITING_CZ"
        and row["mechanical_failure_reason"] == "AMBIGUOUS_ROUTE"
    ]
    remaining_no_position = [
        row
        for row in exported_rows
        if row["work_status"] == "WAITING_CZ"
        and row["mechanical_failure_reason"] == "NO_POSITION_ROUTE"
    ]
    if (
        [row["sequence"] for row in remaining_ambiguous] != [3, 15]
        or len(remaining_no_position) != 26
    ):
        raise C7ExportError("C7.5 后 26 无位置＋2 双候选结构漂移")

    provenance = {
        "source_queue_path": C6_QUEUE.relative_to(ROOT).as_posix(),
        "source_queue_sha256": queue_sha,
        "candidate_file_sha256_by_case": candidate_shas,
        "anchor_catalog_sha256_by_case": catalog_shas,
    }
    return exported_rows, candidate_catalogs, provenance


def _reason_display(reason: Any) -> str:
    labels = {
        "NO_POSITION_ROUTE": "无唯一位置路由（NO_POSITION_ROUTE）",
        "AMBIGUOUS_ROUTE": "位置路由不唯一（AMBIGUOUS_ROUTE）",
    }
    if reason not in labels:
        raise C7ExportError(f"未知机械失败原因：{reason}")
    return labels[str(reason)]


def _markdown(
    rows: list[Mapping[str, Any]],
    candidate_catalogs: Mapping[str, list[Mapping[str, Any]]],
    provenance: Mapping[str, Any],
) -> str:
    lines = [
        "> 当前状态：C7.5 已机械回填 8 条，剩余 CZ 待判 28 条。"
        "差一条也不冻结映射。",
        "",
        "填写方法：只在空着的“CZ 判词／机械回填”列填一个完整选项 ID，"
        "例如 `MAP_TO::EV-C0039-01` 或 `NO_CORRESPONDENCE`。"
        "已有“C7.5 机械回填”的 8 行不要改，其余列也不要改。",
        "",
        "这张表只给冻结身份、位置、候选事件和锚信息；"
        "没有方向提示、相似度分数或模型意见，也不含正式金标正文。",
        "",
        f"冻结队列 SHA：`{provenance['source_queue_sha256']}`",
        "",
        "## C7.5 已机械回填的 8 行（不占 CZ 人工判词）",
        "",
        "| 序号 | 章 | 原子 ID | 唯一候选 | 机械依据 |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        if row["work_status"] != "MECHANICALLY_RESOLVED_C7_5":
            continue
        lines.append(
            "| "
            + " | ".join(
                _escape_cell(cell)
                for cell in [
                    f"{row['sequence']:02d}",
                    row["chapter"],
                    row["atom_id"],
                    str(row["mechanical_resolution"]),
                    "C7.5：允许 N:1；本行只有一个候选事件",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "这 8 行是机械处置，不是模型建议，也不是人工预填。"
            "C6 原队列保持不动，处置另记 C7.5 派生层。",
            "",
        ]
    )
    sequence_start = 0
    for case_id in CASE_ORDER:
        chapter_rows = [row for row in rows if row["case_id"] == case_id]
        pending_total = sum(
            row["work_status"] == "WAITING_CZ" for row in chapter_rows
        )
        auto_total = len(chapter_rows) - pending_total
        lines.extend(
            [
                f"## {CASE_LABELS[case_id]}｜CZ 待判 {pending_total} 条"
                f"／C7.5 机械回填 {auto_total} 条",
                "",
                "| 序号 | 章 | 原子 ID | 原子定位提示 | 候选事件 ID（可多个） | 机械失败原因 | 可选项（含无对应） | CZ 判词／机械回填 |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for row in chapter_rows:
            sequence_start += 1
            event_ids = "；".join(row["candidate_event_ids"])
            choices = "；".join(
                (
                    option["choice_id"]
                    if option["choice_id"] != NO_CORRESPONDENCE
                    else f"{NO_CORRESPONDENCE}（无对应）"
                )
                for option in row["choices"]
            )
            resolution_display = (
                f"C7.5机械回填：{row['mechanical_resolution']}"
                if row["mechanical_resolution"] is not None
                else ""
            )
            cells = [
                f"{sequence_start:02d}",
                row["chapter"],
                row["atom_id"],
                row["atom_position_hint"],
                event_ids,
                _reason_display(row["mechanical_failure_reason"]),
                choices,
                resolution_display,
            ]
            lines.append("| " + " | ".join(_escape_cell(cell) for cell in cells) + " |")
        lines.append("")

    lines.extend(
        [
            "## 候选事件速查（只作客观查阅）",
            "",
            "下面按冻结顺序列候选事件句、锚 ID 和正文区间。"
            "它不是方向提示，选项仍以每行作业表为准。",
            "",
        ]
    )
    for case_id in CASE_ORDER:
        lines.extend(
            [
                f"### {CASE_LABELS[case_id]}",
                "",
                "| 候选事件 ID | 候选事件句 | 锚 ID | 正文区间 |",
                "|---|---|---|---|",
            ]
        )
        for event in candidate_catalogs[case_id]:
            ranges = "；".join(
                f"{item['anchor_id']}[{item['start']},{item['end']})"
                for item in event["anchor_ranges"]
            )
            cells = [
                event["event_id"],
                event["event_text"],
                "；".join(event["anchor_ids"]),
                ranges,
            ]
            lines.append("| " + " | ".join(_escape_cell(cell) for cell in cells) + " |")
        lines.append("")

    lines.extend(
        [
            "## 映射基数与“合并度”口径",
            "",
            "- 允许多个金标原子映到同一条事件；同一事件被使用后，不得阻止后续原子继续映入。",
            "- 实验臂与对照臂必须共用同一套 49 原子、同一版统计器，并逐事件登记所承载的原子清单。",
            "- C5 首屏必报：两臂事件数 129 vs 37、覆盖原子数、1:1 事件数、N:1 事件数、最大 N、承载量分布和逐章明细。",
            "- 程序必须核对：承载量分布加权后等于已映原子数，逐章合计能加回全局总账。",
            "- 错误率下降但 49 原子覆盖下降时，只能记“疑似以少产出换低错误率”，不得判过闸。",
            "",
            "## 冻结条件",
            "",
            "- C7.5 的 8 行机械处置齐套，加上剩余 28 行 CZ 判词齐套，才允许冻结映射。",
            "- 未填写行不得默认当成“无对应”。",
            "- 支撑义务层继续单独记诊断账，不与 49 个原子强行一一对应。",
            "- 映射冻结前，不复算 C5；本页不会触发 Ling 调用。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def build_artifacts() -> dict[str, bytes]:
    rows, candidate_catalogs, provenance = _queue_rows_and_catalogs()
    auto_resolutions = [
        {
            "sequence": row["sequence"],
            "row_id": row["row_id"],
            "case_id": row["case_id"],
            "atom_id": row["atom_id"],
            "resolved_choice_id": row["mechanical_resolution"],
            "resolved_candidate_event_id": row["candidate_event_ids"][0],
            "basis": "C7.5_SINGLE_CANDIDATE_N_TO_ONE_ALLOWED",
        }
        for row in rows
        if row["work_status"] == "MECHANICALLY_RESOLVED_C7_5"
    ]
    cardinality_policy = {
        "schema_version": "v02-c7-5-mapping-cardinality-policy.v1",
        "status": "ACTIVE_FOR_C7_MAPPING_AND_C5_RESCORE",
        "decision_source": {
            "notion_page_id": C75_DECISION_NOTION_PAGE_ID,
            "decided_at": C75_DECISION_AT,
            "decision": "ALLOW_N_GOLD_ATOMS_TO_ONE_EVENT",
        },
        "event_occupancy_rule": "NO_EXCLUSIVE_OCCUPANCY",
        "multiple_gold_atoms_may_map_to_same_event": True,
        "applies_equally_to_arms": ["control", "treatment"],
        "scoring_atom_set_size": 49,
        "same_scoring_atom_set_required_for_both_arms": True,
        "same_counter_version_required_for_both_arms": True,
        "arm_event_counts_for_front_screen": {
            "control": 129,
            "treatment": 37,
        },
        "merge_degree_definition": (
            "number_of_gold_scoring_atoms_mapped_to_each_mapped_event"
        ),
        "required_metrics_per_arm": [
            "produced_parent_event_total",
            "mapped_atom_total",
            "unmapped_atom_total",
            "coverage_rate",
            "mapped_parent_event_total",
            "mapped_event_degree_histogram",
            "one_to_one_mapped_event_count",
            "many_to_one_mapped_event_count",
            "maximum_atoms_per_mapped_event",
            "by_case_breakdown",
            "event_loads",
        ],
        "event_load_fields": [
            "case_id",
            "event_id",
            "atom_ids",
            "atom_count",
            "mapping_sources",
        ],
        "hard_invariants": [
            "each_atom_maps_to_exactly_one_event_or_no_correspondence",
            "event_may_carry_multiple_atoms",
            "atom_count_equals_len_atom_ids",
            "histogram_event_sum_equals_mapped_parent_event_total",
            "histogram_weighted_sum_equals_mapped_atom_total",
            "case_breakdowns_sum_to_arm_total",
            "both_arms_share_scoring_atom_set_and_counter_version",
            "all_28_cz_verdicts_present_before_freeze",
        ],
        "coverage_guard": (
            "error_rate_down_with_49_atom_coverage_down_cannot_pass"
        ),
        "coverage_guard_label": "疑似以少产出换低错误率",
        "auto_resolution_total": len(auto_resolutions),
        "auto_resolutions": auto_resolutions,
        "cz_pending_total": sum(
            row["work_status"] == "WAITING_CZ" for row in rows
        ),
        "mapping_freeze_allowed": False,
        "c5_rescore_allowed": False,
    }
    safe_document = {
        "schema_version": "v02-c7-human-verdict-safe-export.v1",
        "status": "WAITING_FOR_CZ_28_VERDICTS_C75_8_AUTO",
        "row_total": len(rows),
        "case_counts": EXPECTED_PENDING_COUNTS,
        "cz_pending_total": 28,
        "cz_pending_case_counts": EXPECTED_CZ_PENDING_COUNTS_AFTER_C75,
        "c7_5_mechanical_resolution_total": 8,
        "cz_verdict_filled": 0,
        "mapping_freeze_allowed": False,
        "c5_rescore_allowed": False,
        "model_api_calls": 0,
        "network_requests": 0,
        "recommendation_or_similarity_used": False,
        "formal_gold_text_emitted": False,
        "source": provenance,
        "rows": rows,
        "candidate_catalogs": candidate_catalogs,
    }
    markdown = _markdown(rows, candidate_catalogs, provenance)
    markdown_bytes = markdown.encode("utf-8")
    safe_json_bytes = canonical_bytes(safe_document)
    cardinality_policy_bytes = canonical_bytes(cardinality_policy)

    serialized = (
        markdown
        + safe_json_bytes.decode("utf-8")
        + cardinality_policy_bytes.decode("utf-8")
    )
    forbidden_field_names = (
        '"gold_claim"',
        '"quote"',
        '"similarity"',
        '"recommended_choice"',
        '"model_advice"',
    )
    forbidden_hits = [
        field for field in forbidden_field_names if field in serialized
    ]
    if forbidden_hits:
        raise C7ExportError(
            "安全导出含正式金标正文来源字段或方向提示字段："
            f"{forbidden_hits}"
        )
    if any(row["cz_verdict"] for row in rows):
        raise C7ExportError("CZ 判词列不是全空")
    if sum(
        row["mechanical_resolution"] is not None for row in rows
    ) != len(C75_AUTO_RESOLUTION_SEQUENCES):
        raise C7ExportError("C7.5 机械回填数不是 8")
    if any(
        row["choices"][-1]["choice_id"] != NO_CORRESPONDENCE
        for row in rows
    ):
        raise C7ExportError("有行缺少“无对应”选项")

    audit = {
        "schema_version": "v02-c7-export-audit.v1",
        "status": "PASS",
        "source_queue_sha256": provenance["source_queue_sha256"],
        "row_total": len(rows),
        "case_counts": EXPECTED_PENDING_COUNTS,
        "unique_atom_id_total": len({row["atom_id"] for row in rows}),
        "choice_count_distribution": {
            str(key): value
            for key, value in sorted(
                EXPECTED_CHOICE_COUNT_DISTRIBUTION.items()
            )
        },
        "cz_verdict_blank_total": sum(
            row["cz_verdict"] == "" for row in rows
        ),
        "display_result_blank_total": sum(
            row["mechanical_resolution"] is None for row in rows
        ),
        "c7_5_mechanical_resolution_total": sum(
            row["mechanical_resolution"] is not None for row in rows
        ),
        "cz_pending_total": sum(
            row["work_status"] == "WAITING_CZ" for row in rows
        ),
        "no_correspondence_option_total": sum(
            row["choices"][-1]["choice_id"] == NO_CORRESPONDENCE
            for row in rows
        ),
        "formal_gold_files_read": 0,
        "gold_claim_source_field_hit_total": int(
            '"gold_claim"' in serialized
        ),
        "gold_quote_source_field_hit_total": int('"quote"' in serialized),
        "source_whitelist": [
            "C6 frozen human verdict queue",
            "C4 candidate event output",
            "C1 anchor catalog identity and ranges",
        ],
        "direction_hint_field_hit_total": len(forbidden_hits),
        "model_api_calls": 0,
        "network_requests": 0,
        "mapping_freeze_allowed": False,
        "c5_rescore_allowed": False,
        "ling_l1_calls_allowed_now": False,
    }
    audit_bytes = canonical_bytes(audit)
    artifacts = {
        "notion_human_verdict_table.md": markdown_bytes,
        "notion_human_verdict_rows.json": safe_json_bytes,
        "c7_5_mapping_cardinality_policy.json": cardinality_policy_bytes,
        "leakage_and_completeness_ticket.json": audit_bytes,
    }
    manifest = {
        "schema_version": "v02-c7-artifact-manifest.v1",
        "status": "PASS",
        "source_queue_sha256": provenance["source_queue_sha256"],
        "artifacts": [
            {
                "path": name,
                "sha256": sha256_bytes(raw),
                "byte_count": len(raw),
            }
            for name, raw in sorted(artifacts.items())
        ],
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(manifest)
    return artifacts


def write_artifacts(output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = build_artifacts()
    for name, raw in artifacts.items():
        (output_dir / name).write_bytes(raw)
    return {name: sha256_bytes(raw) for name, raw in artifacts.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="导出 C7 的 36 行 Notion 人工判词安全表格"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    digests = write_artifacts(args.output_dir)
    print(
        json.dumps(
            {
                "status": "PASS",
                "output_dir": str(args.output_dir),
                "artifacts": digests,
                "model_api_calls": 0,
                "network_requests": 0,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

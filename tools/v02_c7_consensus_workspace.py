#!/usr/bin/env python3
"""V02/C7.6-C7.7：生成一对多机械回填与 AI 合议隔离工位。

本工具不调用模型，也不冻结最终映射：

- C7.6 只处理已拍定的序 03、15，并复核每个目标事件都与原子证据区间重叠；
- C7.7 只为剩余 26 个无位置路由原子生成逐条隔离包；
- 每个隔离包只含一个计分原子文本、该章候选事件与选项 ID；
- 不输出证据短引、整本金标、人工判词、历史成绩或任何推荐答案。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
V02_ROOT = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
)
C1_DIR = V02_ROOT / "C_anchor_first_experiment"
C6_QUEUE = (
    V02_ROOT
    / "V02_C6_control_and_crosswalk"
    / "crosswalk/human_verdict_queue.json"
)
C7_ROWS = (
    V02_ROOT
    / "V02_C7_human_verdict_workspace"
    / "notion_human_verdict_rows.json"
)
C75_POLICY = (
    V02_ROOT
    / "V02_C7_human_verdict_workspace"
    / "c7_5_mapping_cardinality_policy.json"
)
DEFAULT_OUTPUT_DIR = V02_ROOT / "V02_C7_6_7_ai_consensus_workspace"

EXPECTED_C6_QUEUE_SHA256 = (
    "071ac5f887721339e2c88b1d3785638303613264d16c056b8478adee189c0dd4"
)
CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
NO_CORRESPONDENCE = "NO_CORRESPONDENCE"
C76_RESOLUTIONS = {
    3: ("EV-C0039-05", "EV-C0039-06"),
    15: ("EV-C0033-06", "EV-C0033-11"),
}
C75_RESOLUTION_SEQUENCES = (16, 21, 22, 26, 27, 34, 35, 36)
C77_EXPECTED_SEQUENCES = tuple(
    value
    for value in range(1, 37)
    if value not in C75_RESOLUTION_SEQUENCES
    and value not in C76_RESOLUTIONS
)


class C7ConsensusError(RuntimeError):
    """C7.6/C7.7 工位无法从冻结实物安全重建。"""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C7ConsensusError(f"文件不存在：{path}")
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _manifest_rows() -> dict[str, Mapping[str, Any]]:
    manifest_path = C1_DIR / "source_manifest.json"
    manifest = read_json(manifest_path)
    chapters = manifest.get("chapters")
    if (
        manifest.get("schema_version")
        != "v02-anchor-first-source-manifest.v1"
        or not isinstance(chapters, list)
        or [row.get("case_id") for row in chapters] != list(CASE_ORDER)
    ):
        raise C7ConsensusError("C1 来源清单身份或章顺序漂移")
    return {str(row["case_id"]): row for row in chapters}


def _formal_claims_by_case() -> tuple[
    dict[str, dict[str, str]],
    dict[str, str],
]:
    claims_by_case: dict[str, dict[str, str]] = {}
    gold_shas: dict[str, str] = {}
    for case_id, manifest_row in _manifest_rows().items():
        gold_ref = manifest_row.get("formal_gold")
        if not isinstance(gold_ref, Mapping):
            raise C7ConsensusError(f"{case_id} 缺正式计分原子引用")
        gold_path = ROOT / str(gold_ref.get("path"))
        digest = sha256_file(gold_path)
        if digest != gold_ref.get("sha256"):
            raise C7ConsensusError(f"{case_id} 正式计分原子文件 SHA 漂移")
        document = read_json(gold_path)
        claims: dict[str, str] = {}
        for item in document.get("layered_items", []):
            if not isinstance(item, Mapping):
                continue
            for part in item.get("parts", []):
                if (
                    isinstance(part, Mapping)
                    and part.get("formal_score_eligible") is True
                    and part.get("score_in_single_chapter") is True
                ):
                    part_id = part.get("part_id")
                    claim = part.get("claim")
                    if (
                        not isinstance(part_id, str)
                        or not isinstance(claim, str)
                        or not claim.strip()
                        or part_id in claims
                    ):
                        raise C7ConsensusError(
                            f"{case_id} 计分原子身份或文本非法"
                        )
                    claims[part_id] = claim
        claims_by_case[case_id] = claims
        gold_shas[case_id] = digest
    return claims_by_case, gold_shas


def _source_rows() -> tuple[
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    Mapping[str, Any],
]:
    if sha256_file(C6_QUEUE) != EXPECTED_C6_QUEUE_SHA256:
        raise C7ConsensusError("C6 判词队列 SHA 漂移")
    c6 = read_json(C6_QUEUE)
    c7 = read_json(C7_ROWS)
    c6_rows = c6.get("rows")
    c7_rows = c7.get("rows")
    if (
        c6.get("row_total") != 36
        or not isinstance(c6_rows, list)
        or len(c6_rows) != 36
        or c7.get("row_total") != 36
        or not isinstance(c7_rows, list)
        or len(c7_rows) != 36
    ):
        raise C7ConsensusError("C6/C7 行数合同漂移")
    for sequence, (c6_row, c7_row) in enumerate(
        zip(c6_rows, c7_rows, strict=True),
        1,
    ):
        if (
            c7_row.get("sequence") != sequence
            or c6_row.get("atom_id") != c7_row.get("atom_id")
            or c6_row.get("case_id") != c7_row.get("case_id")
        ):
            raise C7ConsensusError(f"第 {sequence} 行 C6/C7 身份错位")
    return c6_rows, c7_rows, c7


def _range_overlap(left: Mapping[str, Any], right: Mapping[str, Any]) -> int:
    return max(
        0,
        min(int(left["end"]), int(right["end"]))
        - max(int(left["start"]), int(right["start"])),
    )


def _candidate_lookup(
    c7_document: Mapping[str, Any],
) -> dict[str, dict[str, Mapping[str, Any]]]:
    catalogs = c7_document.get("candidate_catalogs")
    if not isinstance(catalogs, Mapping):
        raise C7ConsensusError("C7 候选事件速查缺失")
    result: dict[str, dict[str, Mapping[str, Any]]] = {}
    for case_id in CASE_ORDER:
        rows = catalogs.get(case_id)
        if not isinstance(rows, list) or not rows:
            raise C7ConsensusError(f"{case_id} 候选事件速查缺失")
        case_lookup: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                raise C7ConsensusError(f"{case_id} 候选事件不是对象")
            event_id = row.get("event_id")
            if not isinstance(event_id, str) or event_id in case_lookup:
                raise C7ConsensusError(f"{case_id} 候选事件身份非法")
            case_lookup[event_id] = row
        result[case_id] = case_lookup
    return result


def _c76_resolutions(
    c6_rows: list[Mapping[str, Any]],
    c7_rows: list[Mapping[str, Any]],
    candidates: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    resolutions: list[dict[str, Any]] = []
    for sequence, event_ids in C76_RESOLUTIONS.items():
        c6_row = c6_rows[sequence - 1]
        c7_row = c7_rows[sequence - 1]
        case_id = str(c7_row["case_id"])
        if (
            c7_row.get("mechanical_failure_reason") != "AMBIGUOUS_ROUTE"
            or tuple(c7_row.get("candidate_event_ids", [])) != event_ids
        ):
            raise C7ConsensusError(f"C7.6 第 {sequence} 行候选集合漂移")
        atom_ranges = c6_row.get("gold_evidence_ranges")
        if not isinstance(atom_ranges, list) or not atom_ranges:
            raise C7ConsensusError(f"C7.6 第 {sequence} 行缺原子位置")
        overlap_receipts: list[dict[str, Any]] = []
        for event_id in event_ids:
            event = candidates[case_id].get(event_id)
            if not isinstance(event, Mapping):
                raise C7ConsensusError(
                    f"C7.6 第 {sequence} 行目标事件不存在：{event_id}"
                )
            anchor_ranges = event.get("anchor_ranges")
            if not isinstance(anchor_ranges, list) or not anchor_ranges:
                raise C7ConsensusError(
                    f"C7.6 第 {sequence} 行目标事件缺位置：{event_id}"
                )
            overlaps = [
                {
                    "atom_evidence_id": atom_range["evidence_id"],
                    "candidate_anchor_id": anchor_range["anchor_id"],
                    "overlap_char_count": _range_overlap(
                        atom_range,
                        anchor_range,
                    ),
                }
                for atom_range in atom_ranges
                for anchor_range in anchor_ranges
                if _range_overlap(atom_range, anchor_range) > 0
            ]
            if not overlaps:
                raise C7ConsensusError(
                    f"C7.6 第 {sequence} 行目标事件无位置重叠：{event_id}"
                )
            overlap_receipts.extend(overlaps)
        resolutions.append(
            {
                "sequence": sequence,
                "row_id": c7_row["row_id"],
                "case_id": case_id,
                "atom_id": c7_row["atom_id"],
                "resolved_candidate_event_ids": list(event_ids),
                "resolved_choice_ids": [
                    f"MAP_TO::{event_id}" for event_id in event_ids
                ],
                "split_degree": len(event_ids),
                "basis": "C7.6_ONE_ATOM_TO_MULTIPLE_EVENTS_ALLOWED",
                "position_overlap_verified": True,
                "overlap_receipts": overlap_receipts,
            }
        )
    return resolutions


def _consensus_packets(
    c6_rows: list[Mapping[str, Any]],
    c7_rows: list[Mapping[str, Any]],
    candidates: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> tuple[dict[str, bytes], list[dict[str, Any]], dict[str, str]]:
    claims_by_case, gold_shas = _formal_claims_by_case()
    packet_artifacts: dict[str, bytes] = {}
    packet_manifest: list[dict[str, Any]] = []

    for sequence in C77_EXPECTED_SEQUENCES:
        c6_row = c6_rows[sequence - 1]
        c7_row = c7_rows[sequence - 1]
        if (
            c7_row.get("mechanical_failure_reason") != "NO_POSITION_ROUTE"
            or c7_row.get("mechanical_resolution") is not None
        ):
            raise C7ConsensusError(
                f"C7.7 第 {sequence} 行不是待合议的无位置路由"
            )
        case_id = str(c7_row["case_id"])
        atom_id = str(c7_row["atom_id"])
        claim = claims_by_case[case_id].get(atom_id)
        if not isinstance(claim, str):
            raise C7ConsensusError(f"C7.7 找不到单条计分原子：{atom_id}")
        if sha256_bytes(claim.encode("utf-8")) != c6_row.get(
            "gold_claim_sha256"
        ):
            raise C7ConsensusError(f"C7.7 单条计分原子 SHA 漂移：{atom_id}")

        option_rows: list[dict[str, Any]] = []
        allowed_choice_ids: list[str] = []
        for choice in c7_row["choices"]:
            choice_id = str(choice["choice_id"])
            allowed_choice_ids.append(choice_id)
            if choice_id == NO_CORRESPONDENCE:
                option_rows.append(
                    {
                        "choice_id": NO_CORRESPONDENCE,
                        "candidate_event_text": None,
                    }
                )
                continue
            event_id = str(choice["candidate_event_id"])
            event = candidates[case_id].get(event_id)
            if not isinstance(event, Mapping):
                raise C7ConsensusError(
                    f"C7.7 候选事件不存在：{case_id}/{event_id}"
                )
            option_rows.append(
                {
                    "choice_id": choice_id,
                    "candidate_event_text": event["event_text"],
                }
            )

        packet = {
            "schema_version": "v02-c7-7-consensus-packet.v1",
            "packet_id": str(c7_row["row_id"]),
            "sequence": sequence,
            "case_id": case_id,
            "atom_id": atom_id,
            "scoring_atom_text": claim,
            "choices": option_rows,
            "output_contract": {
                "only_allowed_field": "selected_choice_ids",
                "selected_choice_ids": {
                    "type": "array",
                    "min_items": 1,
                    "unique_items": True,
                    "allowed_values": allowed_choice_ids,
                },
                "no_correspondence_is_exclusive": True,
                "reasoning_or_explanation_forbidden": True,
            },
            "decision_rule": (
                "只在候选事件明确承载该原子事实时选择对应 ID；"
                "一条原子可由多条候选事件共同承载；"
                "找不到明确对应时只选 NO_CORRESPONDENCE，禁止硬配。"
            ),
            "adjudication_identity": "working_verdict_not_gold",
        }
        raw = canonical_bytes(packet)
        relative_path = f"packets/{c7_row['row_id']}.json"
        packet_artifacts[relative_path] = raw
        packet_manifest.append(
            {
                "packet_id": c7_row["row_id"],
                "sequence": sequence,
                "case_id": case_id,
                "atom_id": atom_id,
                "packet_path": relative_path,
                "packet_sha256": sha256_bytes(raw),
                "scoring_atom_text_sha256": sha256_bytes(
                    claim.encode("utf-8")
                ),
                "choice_ids": allowed_choice_ids,
            }
        )

    if len(packet_manifest) != 26:
        raise C7ConsensusError("C7.7 合议隔离包不是 26 份")
    return packet_artifacts, packet_manifest, gold_shas


def _markdown_index(
    c76_resolutions: list[Mapping[str, Any]],
    packet_manifest: list[Mapping[str, Any]],
) -> str:
    lines = [
        "> 当前状态：C7.6 两行已机械回填；C7.7 的 26 行已拆成逐条隔离包。"
        "映射仍未冻结，C5 仍不得复算。",
        "",
        "## C7.6 两行机械回填",
        "",
        "| 序号 | 原子 ID | 回填选项 | 拆分度 | 依据 |",
        "|---|---|---|---:|---|",
    ]
    for row in c76_resolutions:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{int(row['sequence']):02d}",
                    str(row["atom_id"]),
                    "；".join(row["resolved_choice_ids"]),
                    str(row["split_degree"]),
                    "C7.6；全部目标事件均已过位置重叠复核",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## C7.7 合议工位",
            "",
            "- 共 26 份隔离包；每包只含一个计分原子文本与该行候选事件。",
            "- 至少两个独立 AI 背对背出票；只准返回选项 ID，不准解释。",
            "- 全票一致才形成工作判词；分歧行才交 CZ。",
            "- V4 Flash 不得自评，Ling 未完成摸底不得参评。",
            "- 工作判词不是金标，不修改六本金标及指针。",
            "",
            "| 序号 | 包 ID | 章 | 原子 ID | 包 SHA |",
            "|---|---|---|---|---|",
        ]
    )
    for row in packet_manifest:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{int(row['sequence']):02d}",
                    str(row["packet_id"]),
                    str(row["case_id"]),
                    str(row["atom_id"]),
                    f"`{row['packet_sha256']}`",
                ]
            )
            + " |"
        )
    lines.extend(["", "来源：Codex", ""])
    return "\n".join(lines)


def build_artifacts() -> dict[str, bytes]:
    c6_rows, c7_rows, c7_document = _source_rows()
    candidates = _candidate_lookup(c7_document)
    c76_resolutions = _c76_resolutions(c6_rows, c7_rows, candidates)
    packet_artifacts, packet_manifest, gold_shas = _consensus_packets(
        c6_rows,
        c7_rows,
        candidates,
    )

    c76_receipt = {
        "schema_version": "v02-c7-6-one-to-many-resolution.v1",
        "status": "PASS",
        "decision": "ALLOW_ONE_ATOM_TO_MULTIPLE_EVENTS",
        "decision_source": {
            "notion_ledger_url": (
                "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c"
            ),
            "decided_at": "2026-07-25 11:45",
        },
        "resolution_total": 2,
        "resolutions": c76_resolutions,
        "cz_or_ai_pending_total_after_c76": 26,
        "mapping_freeze_allowed": False,
        "c5_rescore_allowed": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    split_policy = {
        "schema_version": "v02-c7-6-split-degree-policy.v1",
        "status": "ACTIVE_FOR_C7_MAPPING_AND_C5_RESCORE",
        "predecessor_policy": {
            "path": C75_POLICY.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(C75_POLICY),
            "retained_rule": (
                "multiple_gold_atoms_may_map_to_same_event"
            ),
            "superseded_hard_invariant": (
                "each_atom_maps_to_exactly_one_event_or_no_correspondence"
            ),
        },
        "precedence_rule": (
            "C7.6 controls atom-to-event cardinality; "
            "C7.5 continues to control event-to-atom merge degree"
        ),
        "one_atom_may_map_to_multiple_events": True,
        "applies_equally_to_arms": ["control", "treatment"],
        "split_degree_definition": (
            "number_of_candidate_events_jointly_mapped_to_each_scoring_atom"
        ),
        "required_metrics_per_arm": [
            "mapped_atom_total",
            "unmapped_atom_total",
            "atom_split_degree_histogram",
            "one_event_atom_count",
            "multi_event_atom_count",
            "maximum_events_per_atom",
            "by_case_breakdown",
            "atom_loads",
        ],
        "atom_load_fields": [
            "case_id",
            "atom_id",
            "event_ids",
            "event_count",
            "mapping_sources",
        ],
        "hard_invariants": [
            "each_atom_maps_to_one_or_more_unique_events_or_no_correspondence",
            "no_correspondence_cannot_coexist_with_event_mapping",
            "histogram_atom_sum_equals_mapped_atom_total",
            "histogram_weighted_sum_equals_total_atom_event_links",
            "case_breakdowns_sum_to_arm_total",
            "both_arms_share_scoring_atom_set_and_counter_version",
        ],
        "front_screen_must_show": [
            "control_parent_event_total_129",
            "treatment_parent_event_total_37",
            "coverage",
            "merge_degree",
            "split_degree",
        ],
    }
    consensus_contract = {
        "schema_version": "v02-c7-7-ai-consensus-contract.v1",
        "status": "READY_FOR_INDEPENDENT_VOTES",
        "verdict_identity": "working_verdict_not_gold",
        "packet_total": 26,
        "minimum_independent_model_windows": 2,
        "back_to_back_required": True,
        "vote_visibility_before_commit": "HIDDEN_FROM_OTHER_VOTERS",
        "unanimity_required": True,
        "only_option_ids_allowed": True,
        "multiple_choice_ids_allowed_under_c7_6": True,
        "no_correspondence_is_exclusive": True,
        "disagreements_route_to": "CZ",
        "position_gap_default": "NO_CORRESPONDENCE_UNLESS_CLEAR_COUNTEREXAMPLE",
        "forbidden_voters": [
            "deepseek-v4-flash",
            "SenseNova V4 Flash",
            "Tencent V4 Flash",
            "Ling-3.0-flash",
        ],
        "controlled_exception": (
            "one_scoring_atom_text_per_packet_only; "
            "whole_gold_and_gold_evidence_quotes_forbidden"
        ),
        "forbidden_model_input": [
            "whole_gold_file",
            "other_scoring_atom_texts",
            "gold_evidence_quotes",
            "human_verdicts",
            "other_model_votes",
            "historical_scores",
            "repair_logs",
            "api_keys",
        ],
        "mapping_freeze_allowed": False,
        "c5_rescore_allowed": False,
    }
    packet_manifest_document = {
        "schema_version": "v02-c7-7-consensus-packet-manifest.v1",
        "status": "PASS",
        "packet_total": len(packet_manifest),
        "packets": packet_manifest,
        "source_c6_queue_sha256": sha256_file(C6_QUEUE),
        "source_c7_rows_sha256": sha256_file(C7_ROWS),
        "formal_gold_sha256_by_case": gold_shas,
        "whole_gold_emitted": False,
        "gold_evidence_quotes_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    leakage_ticket = {
        "schema_version": "v02-c7-7-consensus-leakage-ticket.v1",
        "status": "PASS",
        "packet_total": len(packet_manifest),
        "single_scoring_atom_text_per_packet": True,
        "other_scoring_atom_texts_per_packet": 0,
        "gold_evidence_quote_fields": 0,
        "formal_gold_paths_in_packets": 0,
        "api_key_hits": 0,
        "prefilled_vote_total": 0,
        "other_model_vote_visible_total": 0,
        "model_api_calls": 0,
        "network_requests": 0,
    }

    artifacts: dict[str, bytes] = {
        "c7_6_one_to_many_resolution.json": canonical_bytes(c76_receipt),
        "c7_6_split_degree_policy.json": canonical_bytes(split_policy),
        "c7_7_consensus_contract.json": canonical_bytes(consensus_contract),
        "c7_7_packet_manifest.json": canonical_bytes(
            packet_manifest_document
        ),
        "c7_7_leakage_ticket.json": canonical_bytes(leakage_ticket),
        "notion_consensus_index.md": _markdown_index(
            c76_resolutions,
            packet_manifest,
        ).encode("utf-8"),
        **packet_artifacts,
    }
    manifest = {
        "schema_version": "v02-c7-6-7-artifact-manifest.v1",
        "status": "PASS",
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
        "mapping_freeze_allowed": False,
        "c5_rescore_allowed": False,
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(manifest)
    return artifacts


def write_artifacts(output_dir: Path) -> dict[str, str]:
    artifacts = build_artifacts()
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, raw in artifacts.items():
        target = output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return {name: sha256_bytes(raw) for name, raw in artifacts.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成 C7.6 机械回填与 C7.7 AI 合议隔离工位"
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
                "artifact_total": len(digests),
                "c7_6_resolution_total": 2,
                "c7_7_packet_total": 26,
                "mapping_freeze_allowed": False,
                "c5_rescore_allowed": False,
                "sha256": digests,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

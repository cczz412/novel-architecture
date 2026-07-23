#!/usr/bin/env python3
"""第75道件②：聚合多方向人工判词、旧34条不劣化闸和 usage 账。

这个工具不做语义匹配，不从词面、锚点或事件句自动生成判词。
它只验证人工判词是否齐全、状态是否合法，然后按冻结口径计数。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD_POINTER = ROOT / "config/gold/X01_ch0003_structure_gold_current.json"
DEFAULT_BASELINE_SCORE = (
    ROOT / "reports/Z73_第3章金标v1.2定稿转正_20260721/"
    "四轮v1.1旧尺与v1.2新尺双列基线参照.json"
)
DEFAULT_OLD34_BASELINE = (
    ROOT / "reports/Z68续令_32k参数兼容修复与裸考成绩_20260720/"
    "现役122条五靶章语义diff.json"
)
TARGET_CHAPTERS = (3, 4, 5, 13, 19)
EXPECTED_DIRECTION_COUNT = 4

GOLD_VERDICTS = {
    "strict_hit",
    "semantic_shadow",
    "coverage_only_invalid_support",
    "miss",
}
CURRENT_VERDICTS = {"preserved", "partially_preserved", "not_observed"}
CURRENT_RANK = {"not_observed": 0, "partially_preserved": 1, "preserved": 2}
USAGE_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "total_tokens",
)


class ScoreError(RuntimeError):
    """评分聚合的输入不满足冻结口径。"""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScoreError(f"缺少输入文件：{display_path(path)}") from exc
    except json.JSONDecodeError as exc:
        raise ScoreError(f"JSON 无法解析：{display_path(path)}：{exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ScoreError(f"缺少 usage 账：{display_path(path)}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ScoreError(
                f"usage.jsonl 无法解析：{display_path(path)}:{line_number}：{exc}"
            ) from exc
        if not isinstance(value, dict):
            raise ScoreError(
                f"usage.jsonl 第 {line_number} 行必须是 JSON 对象：{display_path(path)}"
            )
        rows.append(dict(value))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ScoreError(f"{label} 必须是 JSON 对象")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ScoreError(f"{label} 必须是数组")
    return value


def require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ScoreError(f"{label} 必须是非负整数")
    return value


def resolve_pointer_path(pointer_path: Path, target: str) -> Path:
    target_path = Path(target)
    if target_path.is_absolute():
        return target_path
    # 现役指针的 path 以仓库根目录为基准。外部测试指针可放同目录。
    root_candidate = ROOT / target_path
    if root_candidate.exists():
        return root_candidate
    return pointer_path.parent / target_path


def load_formal_gold(pointer_path: Path) -> dict[str, Any]:
    pointer = require_mapping(read_json(pointer_path), "现役金标指针")
    active = require_mapping(pointer.get("active_gold"), "现役金标指针 active_gold")
    if active.get("version") != "v1.2":
        raise ScoreError("现役金标指针没有指向 v1.2，拒绝用旧尺聚合")
    denominator = require_nonnegative_int(
        active.get("formal_denominator"), "现役金标分母"
    )
    if denominator != 23:
        raise ScoreError(f"现役金标分母应为 23，实际为 {denominator}")
    target = active.get("path")
    if not isinstance(target, str) or not target:
        raise ScoreError("现役金标指针缺少 active_gold.path")
    gold_path = resolve_pointer_path(pointer_path, target)
    expected_sha = active.get("sha256")
    actual_sha = sha256_file(gold_path)
    if not isinstance(expected_sha, str) or actual_sha != expected_sha:
        raise ScoreError(
            f"现役金标实物 SHA 与指针不一致：指针={expected_sha}，实物={actual_sha}"
        )
    gold = require_mapping(read_json(gold_path), "第3章结构层金标 v1.2")
    if gold.get("schema_version") != "structure-gold-v1.2":
        raise ScoreError("现役金标 schema_version 不是 structure-gold-v1.2")

    scoreable: dict[str, dict[str, Any]] = {}
    for item_index, item_value in enumerate(
        require_list(gold.get("layered_items"), "现役金标 layered_items")
    ):
        item = require_mapping(item_value, f"layered_items[{item_index}]")
        for part_index, part_value in enumerate(
            require_list(item.get("parts"), f"layered_items[{item_index}].parts")
        ):
            part = require_mapping(
                part_value, f"layered_items[{item_index}].parts[{part_index}]"
            )
            if (
                part.get("layer") != "当章可知"
                or part.get("score_in_single_chapter") is not True
            ):
                continue
            part_id = part.get("part_id")
            if not isinstance(part_id, str) or not part_id:
                raise ScoreError("可计分金标条缺少 part_id")
            if part_id in scoreable:
                raise ScoreError(f"可计分金标 part_id 重复：{part_id}")
            claim = part.get("claim")
            if not isinstance(claim, str) or not claim:
                raise ScoreError(f"可计分金标 {part_id} 缺少 claim")
            scoreable[part_id] = dict(part)
    if len(scoreable) != denominator:
        raise ScoreError(
            f"现役金标指针分母为 {denominator}，实物可计分条为 {len(scoreable)}"
        )
    return {
        "pointer": dict(pointer),
        "pointer_path": pointer_path,
        "gold_path": gold_path,
        "gold_sha256": actual_sha,
        "denominator": denominator,
        "parts": scoreable,
    }


def score_summary(
    rows: Sequence[Mapping[str, Any]], denominator: int
) -> dict[str, Any]:
    counts = Counter(str(row["verdict"]) for row in rows)
    strict = counts["strict_hit"]
    shadow = counts["semantic_shadow"]
    invalid = counts["coverage_only_invalid_support"]
    miss = counts["miss"]
    effective = strict + shadow
    surface = effective + invalid
    if strict + shadow + invalid + miss != denominator:
        raise ScoreError("金标判词计数与正式分母不一致")
    return {
        "formal_denominator": denominator,
        "strict_hit": strict,
        "semantic_shadow": shadow,
        "effective_recall": effective,
        "surface_coverage": surface,
        "invalid_anchor_observation": invalid,
        "miss": miss,
        "strict_hit_rate": strict / denominator,
        "effective_recall_rate": effective / denominator,
        "surface_coverage_rate": surface / denominator,
    }


def load_baseline_reference(
    path: Path, *, gold_sha256: str, denominator: int
) -> dict[str, Any]:
    doc = require_mapping(read_json(path), "Z73 双列基线参照")
    formal = require_mapping(doc.get("formal_gold"), "Z73 双列基线 formal_gold")
    if formal.get("sha256") != gold_sha256 or formal.get("denominator") != denominator:
        raise ScoreError("Z73 双列基线与现役金标指针不一致")
    result: list[dict[str, Any]] = []
    for index, value in enumerate(
        require_list(doc.get("rounds"), "Z73 双列基线 rounds")
    ):
        row = require_mapping(value, f"Z73 rounds[{index}]")
        direction = row.get("round_id")
        score = require_mapping(row.get("v1_2_formal"), f"Z73 {direction} v1_2_formal")
        fields = {
            "strict_hit": require_nonnegative_int(
                score.get("strict_hit"), f"{direction} strict_hit"
            ),
            "semantic_shadow": require_nonnegative_int(
                score.get("semantic_shadow"), f"{direction} semantic_shadow"
            ),
            "effective_recall": require_nonnegative_int(
                score.get("effective_recall"), f"{direction} effective_recall"
            ),
            "surface_coverage": require_nonnegative_int(
                score.get("surface_coverage"), f"{direction} surface_coverage"
            ),
            "invalid_anchor_observation": require_nonnegative_int(
                score.get("invalid_anchor_observation"),
                f"{direction} invalid_anchor_observation",
            ),
            "miss": require_nonnegative_int(score.get("miss"), f"{direction} miss"),
        }
        if (
            fields["effective_recall"]
            != fields["strict_hit"] + fields["semantic_shadow"]
        ):
            raise ScoreError(f"Z73 {direction} 有效召回加和不一致")
        if (
            fields["surface_coverage"]
            != fields["effective_recall"] + fields["invalid_anchor_observation"]
        ):
            raise ScoreError(f"Z73 {direction} 表面覆盖加和不一致")
        if fields["surface_coverage"] + fields["miss"] != denominator:
            raise ScoreError(f"Z73 {direction} 计数与分母不一致")
        result.append({"round_id": direction, **fields})
    return {
        "source": display_path(path),
        "source_sha256": sha256_file(path),
        "comparison_only": "只作新尺基线参照，不追改旧轮成绩。",
        "rounds": result,
    }


def load_old34(path: Path) -> dict[str, Any]:
    doc = require_mapping(read_json(path), "Z68C 旧34条语义 diff")
    rows = require_list(doc.get("rows"), "Z68C 旧34条 rows")
    if len(rows) != 34:
        raise ScoreError(f"Z68C 旧基线必须恰好 34 条，实际 {len(rows)} 条")
    by_id: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    for index, value in enumerate(rows):
        row = require_mapping(value, f"Z68C rows[{index}]")
        record_id = row.get("record_id")
        verdict = row.get("verdict")
        if not isinstance(record_id, str) or not record_id:
            raise ScoreError(f"Z68C rows[{index}] 缺少 record_id")
        if record_id in by_id:
            raise ScoreError(f"Z68C 旧34条 record_id 重复：{record_id}")
        if verdict not in CURRENT_VERDICTS:
            raise ScoreError(f"Z68C {record_id} 的旧判词无效：{verdict}")
        chapter = row.get("chapter")
        if chapter not in TARGET_CHAPTERS:
            raise ScoreError(f"Z68C {record_id} 章号不在五靶章：{chapter}")
        by_id[record_id] = dict(row)
        counts[str(verdict)] += 1
    declared = require_mapping(doc.get("summary"), "Z68C 旧34条 summary")
    for verdict in CURRENT_VERDICTS:
        if declared.get(verdict) != counts[verdict]:
            raise ScoreError(f"Z68C 旧34条 summary 与逐条账不一致：{verdict}")
    return {
        "source": path,
        "sha256": sha256_file(path),
        "rows": by_id,
        "summary": {
            "total": len(by_id),
            "preserved": counts["preserved"],
            "partially_preserved": counts["partially_preserved"],
            "not_observed": counts["not_observed"],
        },
    }


def validate_candidate_ids(value: Any, label: str) -> list[str]:
    rows = require_list(value, label)
    if not all(isinstance(item, str) and item for item in rows):
        raise ScoreError(f"{label} 必须是非空字符串数组")
    if len(rows) != len(set(rows)):
        raise ScoreError(f"{label} 不得出现重复 ID")
    return list(rows)


def validate_note(row: Mapping[str, Any], label: str) -> str:
    note = row.get("semantic_review_note", row.get("reason"))
    if not isinstance(note, str) or not note.strip():
        raise ScoreError(
            f"{label} 缺少人工语义说明 semantic_review_note/reason"
        )
    return note


def validate_gold_rows(
    rows_value: Any, formal_parts: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows = require_list(rows_value, "gold_rows")
    by_id: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(rows):
        row = require_mapping(value, f"gold_rows[{index}]")
        # 人工判词允许两种已落盘的等价字段名；输出统一归一为 part_id。
        part_id = row.get("part_id", row.get("gold_part_id"))
        if not isinstance(part_id, str) or not part_id:
            raise ScoreError(f"gold_rows[{index}] 缺少 part_id/gold_part_id")
        if part_id in by_id:
            raise ScoreError(f"gold_rows 出现重复 part_id：{part_id}")
        verdict = row.get("verdict")
        if verdict not in GOLD_VERDICTS:
            raise ScoreError(f"gold_rows 的 {part_id} 判词无效：{verdict}")
        candidate_ids = validate_candidate_ids(
            row.get("candidate_event_ids"), f"gold_rows {part_id} candidate_event_ids"
        )
        note = validate_note(row, f"gold_rows {part_id}")
        by_id[part_id] = {
            "part_id": part_id,
            "claim": formal_parts.get(part_id, {}).get("claim"),
            "verdict": verdict,
            "candidate_event_ids": candidate_ids,
            "semantic_review_note": note,
        }
    expected = set(formal_parts)
    actual = set(by_id)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ScoreError(f"金标 23 条 ID 不齐：缺少={missing}，多出={extra}")
    return [by_id[part_id] for part_id in formal_parts]


def validate_current_rows(
    rows_value: Any, old34: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = require_list(rows_value, "current_rows")
    by_id: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(rows):
        row = require_mapping(value, f"current_rows[{index}]")
        record_id = row.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            raise ScoreError(f"current_rows[{index}] 缺少 record_id")
        if record_id in by_id:
            raise ScoreError(f"current_rows 出现重复 record_id：{record_id}")
        verdict = row.get("verdict")
        if verdict not in CURRENT_VERDICTS:
            raise ScoreError(f"current_rows 的 {record_id} 判词无效：{verdict}")
        candidate_ids = validate_candidate_ids(
            row.get("candidate_event_ids"),
            f"current_rows {record_id} candidate_event_ids",
        )
        note = validate_note(row, f"current_rows {record_id}")
        by_id[record_id] = {
            "record_id": record_id,
            "verdict": verdict,
            "candidate_event_ids": candidate_ids,
            "semantic_review_note": note,
        }
    expected = set(old34)
    actual = set(by_id)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ScoreError(f"旧34条 ID 不齐：缺少={missing}，多出={extra}")

    counts: Counter[str] = Counter()
    transitions: Counter[str] = Counter()
    rescued: list[str] = []
    improved: list[str] = []
    degraded: list[dict[str, Any]] = []
    ordered: list[dict[str, Any]] = []
    for record_id, old_row in old34.items():
        new_row = by_id[record_id]
        old_verdict = str(old_row["verdict"])
        new_verdict = str(new_row["verdict"])
        old_rank = CURRENT_RANK[old_verdict]
        new_rank = CURRENT_RANK[new_verdict]
        change = (
            "improved"
            if new_rank > old_rank
            else ("degraded" if new_rank < old_rank else "unchanged")
        )
        if change == "improved":
            improved.append(record_id)
        if old_verdict == "partially_preserved" and new_verdict == "preserved":
            rescued.append(record_id)
        if change == "degraded":
            degraded.append(
                {
                    "record_id": record_id,
                    "chapter": old_row.get("chapter"),
                    "old_verdict": old_verdict,
                    "new_verdict": new_verdict,
                }
            )
        counts[new_verdict] += 1
        transitions[f"{old_verdict}->{new_verdict}"] += 1
        ordered.append(
            {
                "chapter": old_row.get("chapter"),
                "record_id": record_id,
                "old_verdict": old_verdict,
                "verdict": new_verdict,
                "transition": f"{old_verdict}->{new_verdict}",
                "change": change,
                "candidate_event_ids": new_row["candidate_event_ids"],
                "semantic_review_note": new_row["semantic_review_note"],
            }
        )
    summary = {
        "total": len(ordered),
        "preserved": counts["preserved"],
        "partially_preserved": counts["partially_preserved"],
        "not_observed": counts["not_observed"],
    }
    comparison = {
        "rank_rule": "preserved > partially_preserved > not_observed",
        "transition_counts": dict(sorted(transitions.items())),
        "old_partial_rescued_count": len(rescued),
        "old_partial_rescued_ids": rescued,
        "all_improvement_count": len(improved),
        "all_improved_ids": improved,
        "degradation_count": len(degraded),
        "degradations": degraded,
        "old_34_no_degradation": not degraded,
    }
    return ordered, {"summary": summary, "comparison_to_z68c": comparison}


def validate_overflow_rows(value: Any) -> list[dict[str, Any]]:
    rows = require_list(value, "overflow_rows")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row_value in enumerate(rows):
        row = require_mapping(row_value, f"overflow_rows[{index}]")
        identity = next(
            (
                row.get(key)
                for key in ("event_id", "candidate_event_id", "overflow_id")
                if isinstance(row.get(key), str) and row.get(key)
            ),
            None,
        )
        if identity is None:
            raise ScoreError(
                f"overflow_rows[{index}] 必须含 event_id、candidate_event_id 或 overflow_id"
            )
        if identity in seen:
            raise ScoreError(f"overflow_rows 身份重复：{identity}")
        seen.add(identity)
        result.append(dict(row))
    return result


def chapter_from_usage(row: Mapping[str, Any], label: str) -> int:
    explicit = row.get("chapter")
    if isinstance(explicit, int) and not isinstance(explicit, bool):
        return explicit
    case_id = row.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ScoreError(f"{label} 缺少可识别章号的 chapter 或 case_id")
    matches = re.findall(r"(?:^|_)ch(\d{1,4})(?=_|$)", case_id, flags=re.IGNORECASE)
    if not matches and re.fullmatch(r"\d{1,4}", case_id):
        matches = [case_id]
    if len(matches) != 1:
        raise ScoreError(f"{label} 无法从 case_id 唯一识别章号：{case_id}")
    return int(matches[0])


def usage_score(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    by_chapter: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        label = f"usage.jsonl 第 {index + 1} 条"
        chapter = chapter_from_usage(row, label)
        if chapter not in TARGET_CHAPTERS:
            raise ScoreError(f"{label} 章号不在五靶章：{chapter}")
        if chapter in by_chapter:
            raise ScoreError(f"usage.jsonl 第 {chapter} 章出现多条正式用量记录")
        usage = require_mapping(row.get("usage"), f"{label} usage")
        prompt = require_nonnegative_int(
            usage.get("prompt_tokens"), f"{label} prompt_tokens"
        )
        completion = require_nonnegative_int(
            usage.get("completion_tokens"), f"{label} completion_tokens"
        )
        total = require_nonnegative_int(
            usage.get("total_tokens"), f"{label} total_tokens"
        )
        details_value = usage.get("completion_tokens_details", {})
        details = require_mapping(details_value, f"{label} completion_tokens_details")
        reasoning_value = usage.get(
            "reasoning_tokens", details.get("reasoning_tokens", 0)
        )
        reasoning = require_nonnegative_int(
            reasoning_value, f"{label} reasoning_tokens"
        )
        elapsed = require_nonnegative_int(row.get("elapsed_ms"), f"{label} elapsed_ms")
        by_chapter[chapter] = {
            "chapter": chapter,
            "case_id": row.get("case_id"),
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "reasoning_tokens": reasoning,
            "total_tokens": total,
            "elapsed_ms": elapsed,
            "finish_reason": row.get("finish_reason"),
            "stage_max_tokens": row.get("stage_max_tokens"),
        }
    missing = sorted(set(TARGET_CHAPTERS) - set(by_chapter))
    if missing or len(rows) != len(TARGET_CHAPTERS):
        raise ScoreError(
            f"usage.jsonl 必须每个靶章恰好一条：缺少章={missing}，实际行数={len(rows)}"
        )
    ordered = [by_chapter[chapter] for chapter in TARGET_CHAPTERS]
    totals = {
        field: sum(int(row[field]) for row in ordered)
        for field in (*USAGE_FIELDS, "elapsed_ms")
    }
    return {
        "source": display_path(path),
        "source_sha256": sha256_file(path),
        "source_of_truth": "usage.jsonl",
        "logical_samples": len(ordered),
        "by_chapter": ordered,
        "totals": totals,
    }


def score_direction(
    direction_id: str,
    adjudication_path: Path,
    usage_path: Path,
    *,
    formal_parts: Mapping[str, Mapping[str, Any]],
    denominator: int,
    old34: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    doc = require_mapping(read_json(adjudication_path), f"{direction_id} 人工判词")
    declared_direction = doc.get("direction_id")
    if declared_direction != direction_id:
        raise ScoreError(
            f"{direction_id} 人工判词内的 direction_id 不一致：{declared_direction}"
        )
    gold_rows = validate_gold_rows(doc.get("gold_rows"), formal_parts)
    current_rows, current_rollup = validate_current_rows(doc.get("current_rows"), old34)
    overflow_rows = validate_overflow_rows(doc.get("overflow_rows"))
    gold = score_summary(gold_rows, denominator)
    no_degradation = bool(current_rollup["comparison_to_z68c"]["old_34_no_degradation"])
    return {
        "direction_id": direction_id,
        "status": "candidate_silver_pass" if no_degradation else "hard_stop_no_repair",
        "sources": {
            "manual_adjudication": display_path(adjudication_path),
            "manual_adjudication_sha256": sha256_file(adjudication_path),
            "usage": display_path(usage_path),
            "usage_sha256": sha256_file(usage_path),
        },
        "semantic_boundary": "金标23条、旧34条及溢出均来自人工判词；本工具只验数和聚合，不自动判语义。",
        "gold_v1_2": {"summary": gold, "rows": gold_rows},
        "old_34_gate": {
            "summary": current_rollup["summary"],
            "comparison_to_z68c": current_rollup["comparison_to_z68c"],
            "quality_gate": {
                "passed": no_degradation,
                "disposition": (
                    "candidate_silver_pass" if no_degradation else "hard_stop_no_repair"
                ),
            },
            "rows": current_rows,
        },
        "usage": usage_score(usage_path),
        "overflow": {
            "status": "pending_adjudication_not_scored",
            "count": len(overflow_rows),
            "rows": overflow_rows,
        },
    }


def build_scorecard(
    direction_inputs: Mapping[str, tuple[Path, Path]],
    *,
    gold_pointer: Path = DEFAULT_GOLD_POINTER,
    baseline_score: Path = DEFAULT_BASELINE_SCORE,
    old34_baseline: Path = DEFAULT_OLD34_BASELINE,
    expected_direction_count: int = EXPECTED_DIRECTION_COUNT,
) -> dict[str, Any]:
    if len(direction_inputs) != expected_direction_count:
        raise ScoreError(
            f"本次完整方向聚合必须提供 {expected_direction_count} 个方向，实际 {len(direction_inputs)} 个"
        )
    formal = load_formal_gold(gold_pointer)
    baseline = load_baseline_reference(
        baseline_score,
        gold_sha256=str(formal["gold_sha256"]),
        denominator=int(formal["denominator"]),
    )
    old34_info = load_old34(old34_baseline)
    directions: list[dict[str, Any]] = []
    for direction_id, paths in direction_inputs.items():
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", direction_id):
            raise ScoreError(
                f"方向 ID 只能含字母、数字、点、下划线或短横线：{direction_id}"
            )
        adjudication_path, usage_path = paths
        directions.append(
            score_direction(
                direction_id,
                adjudication_path,
                usage_path,
                formal_parts=formal["parts"],
                denominator=int(formal["denominator"]),
                old34=old34_info["rows"],
            )
        )
    pass_ids = [
        row["direction_id"]
        for row in directions
        if row["old_34_gate"]["quality_gate"]["passed"]
    ]
    hard_stop_ids = [
        row["direction_id"]
        for row in directions
        if not row["old_34_gate"]["quality_gate"]["passed"]
    ]
    total_usage = {
        field: sum(int(row["usage"]["totals"][field]) for row in directions)
        for field in (*USAGE_FIELDS, "elapsed_ms")
    }
    return {
        "schema_version": "z75-multidirection-scorecard-v1",
        "task": "第75道件②",
        "status": "candidate_silver_only",
        "semantic_boundary": {
            "automatic_semantic_matching": False,
            "rule": "程序只聚合人工判词，不凭词面、锚点或句子相似度自动升降级。",
            "candidate_only": "全部方向仅是候选池银标，程序不选胜者、不升默认。",
        },
        "formal_gold": {
            "pointer_path": display_path(gold_pointer),
            "pointer_sha256": sha256_file(gold_pointer),
            "path": display_path(formal["gold_path"]),
            "sha256": formal["gold_sha256"],
            "version": "v1.2",
            "formal_denominator": formal["denominator"],
        },
        "z73_baseline_reference": baseline,
        "z68c_old_34_baseline": {
            "source": display_path(old34_info["source"]),
            "source_sha256": old34_info["sha256"],
            "summary": old34_info["summary"],
        },
        "directions": directions,
        "aggregate": {
            "direction_count": len(directions),
            "logical_samples_from_usage": sum(
                int(row["usage"]["logical_samples"]) for row in directions
            ),
            "old_34_no_degradation_directions": pass_ids,
            "hard_stop_directions": hard_stop_ids,
            "usage_totals": total_usage,
            "automatic_winner_selection": False,
            "promotion_requires_separate_approval": True,
        },
    }


def parse_assignments(values: Sequence[str], label: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        direction_id, separator, raw_path = value.partition("=")
        if not separator or not direction_id or not raw_path:
            raise ScoreError(f"{label} 格式必须是 方向ID=文件路径：{value}")
        if direction_id in result:
            raise ScoreError(f"{label} 方向重复：{direction_id}")
        result[direction_id] = Path(raw_path)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="聚合第75道四方向人工判词、旧34条不劣化闸和 usage 账。"
    )
    parser.add_argument(
        "--direction",
        action="append",
        required=True,
        metavar="方向ID=人工判词JSON",
        help="重复四次，为每个方向指定人工判词。",
    )
    parser.add_argument(
        "--usage",
        action="append",
        required=True,
        metavar="方向ID=usage.jsonl",
        help="重复四次，为每个方向指定真实用量账。",
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="候选银标聚合 JSON 输出路径。"
    )
    parser.add_argument(
        "--expected-direction-count",
        type=int,
        default=EXPECTED_DIRECTION_COUNT,
        help="完整五章方向数；运输硬停的部分方向另列，不能拿来凑数。",
    )
    parser.add_argument("--gold-pointer", type=Path, default=DEFAULT_GOLD_POINTER)
    parser.add_argument("--baseline-score", type=Path, default=DEFAULT_BASELINE_SCORE)
    parser.add_argument("--old34-baseline", type=Path, default=DEFAULT_OLD34_BASELINE)
    args = parser.parse_args(argv)

    direction_paths = parse_assignments(args.direction, "--direction")
    usage_paths = parse_assignments(args.usage, "--usage")
    if set(direction_paths) != set(usage_paths):
        raise ScoreError(
            "--direction 与 --usage 的方向 ID 不一致："
            f"判词={sorted(direction_paths)}，usage={sorted(usage_paths)}"
        )
    specs = {
        direction_id: (path, usage_paths[direction_id])
        for direction_id, path in direction_paths.items()
    }
    result = build_scorecard(
        specs,
        gold_pointer=args.gold_pointer,
        baseline_score=args.baseline_score,
        old34_baseline=args.old34_baseline,
        expected_direction_count=args.expected_direction_count,
    )
    write_json(args.output, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": display_path(args.output),
                "direction_count": result["aggregate"]["direction_count"],
                "hard_stop_directions": result["aggregate"]["hard_stop_directions"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScoreError as exc:
        raise SystemExit(f"评分聚合失败：{exc}") from exc

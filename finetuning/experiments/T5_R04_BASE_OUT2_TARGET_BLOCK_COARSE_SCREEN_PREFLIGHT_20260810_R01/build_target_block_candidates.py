from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REAL24 = ROOT / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
R08 = ROOT / "finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R08"
SOURCE_INDEX = REAL24 / "REAL24_SOURCE_INDEX.jsonl"
TXX = REAL24 / "REAL24_TXX_MAP.jsonl"
GOLD = REAL24 / "REAL24_GOLD_24.jsonl"
CANDIDATES = OUT / "TARGET_BLOCK_CANDIDATES.jsonl"
STATS = OUT / "BLOCK_STATS.json"

EXPECTED_SHA256 = {
    SOURCE_INDEX: "0fe7ecb1649b93e4faab3d253d8904bee7f1a7a3e6f7f0fbb8b8e722c405de97",
    TXX: "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    GOLD: "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    R08 / "00_READ_ME_FIRST.md": "c2104f10061e8310eee0772fb977def284a1fa54674c2f4b10dd3616eda9c751",
    R08 / "DECISION_REGISTRY.json": "b2afc3eb7ed4efd0ff43b50d87ecbbaff13eb406b0d5810a1308589873c139f8",
    R08 / "CONTEXT_HALO_RESULT_TICKET.json": "43d74a4198dd9ba5bdd0e03883447200f88e1a3c7bc4336fda76a6dd29af1662",
}

STAGE1_CASES = {"C01", "C02", "C05", "C09", "C10", "C14", "C23", "C24"}
STATUS = "CANDIDATE_PREFLIGHT_NOT_AUTHORIZED_NOT_RUN"
STRONG_END = set("。！？!?；;")
CLOSERS = set("”’」』）》】]）")
SHORT_CORE_MAX = 8
BANDS = {
    "BLOCK60": {"target": 60, "minimum": 40, "maximum": 90},
    "BLOCK300": {"target": 300, "minimum": 220, "maximum": 380},
}


@dataclass(frozen=True)
class Atom:
    start: int
    end: int
    boundary_after: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return ("\n".join(compact_json(row) for row in rows) + "\n").encode("utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actual = {path: file_sha256(path) for path in EXPECTED_SHA256}
    if actual != EXPECTED_SHA256:
        raise ValueError(
            "冻结输入SHA漂移："
            + compact_json({str(path.relative_to(ROOT)): digest for path, digest in actual.items()})
        )
    source_rows = read_jsonl(SOURCE_INDEX)
    txx_rows = read_jsonl(TXX)
    if len(source_rows) != 24 or len(txx_rows) != 24:
        raise ValueError("REAL24来源或Txx不是24题")
    source_ids = [row["case_id"] for row in source_rows]
    if source_ids != [row["case_id"] for row in txx_rows] or source_ids != [f"C{i:02d}" for i in range(1, 25)]:
        raise ValueError("REAL24来源与Txx题序不一致")
    for source, txx in zip(source_rows, txx_rows, strict=True):
        text = "".join(unit["text"] for unit in txx["target_units"])
        if sha256_bytes(text.encode("utf-8")) != source["target_sha256"]:
            raise ValueError(f"{source['case_id']} Txx不能重建冻结目标段")
        if source["target_end"] - source["target_start"] != len(text):
            raise ValueError(f"{source['case_id']} Unicode坐标长度不闭合")
    return source_rows, txx_rows


def semantic_core(text: str) -> str:
    return re.sub(r"[\s。！？!?；;，,：:、…“”‘’「」『』（）()【】\[\]—-]", "", text)


def natural_atoms(text: str) -> tuple[list[Atom], list[dict[str, Any]]]:
    atoms: list[Atom] = []
    start = 0
    index = 0
    while index < len(text):
        character = text[index]
        cut = False
        boundary = "SENTENCE"
        if character in STRONG_END:
            index += 1
            while index < len(text) and (text[index] in STRONG_END or text[index] in CLOSERS):
                index += 1
            while index < len(text) and text[index] in " \t":
                index += 1
            if index < len(text) and text[index] in "\r\n":
                while index < len(text) and text[index] in " \t\r\n":
                    index += 1
                boundary = "PARAGRAPH"
            cut = True
        elif character in "\r\n":
            index += 1
            while index < len(text) and text[index] in " \t\r\n":
                index += 1
            boundary = "PARAGRAPH"
            cut = True
        else:
            index += 1
        if cut and index > start:
            atoms.append(Atom(start, index, boundary))
            start = index
    if start < len(text):
        atoms.append(Atom(start, len(text), "TARGET_END"))
    if not atoms or atoms[0].start != 0 or atoms[-1].end != len(text):
        raise ValueError("自然原子不能完整覆盖目标段")

    merge_events: list[dict[str, Any]] = []
    position = 0
    while len(atoms) > 1 and position < len(atoms):
        atom = atoms[position]
        core_length = len(semantic_core(text[atom.start : atom.end]))
        if core_length > SHORT_CORE_MAX:
            position += 1
            continue
        if position + 1 < len(atoms):
            following = atoms[position + 1]
            merged = Atom(atom.start, following.end, following.boundary_after)
            direction = "NEXT"
            atoms[position : position + 2] = [merged]
        else:
            previous = atoms[position - 1]
            merged = Atom(previous.start, atom.end, atom.boundary_after)
            direction = "PREVIOUS"
            atoms[position - 1 : position + 1] = [merged]
            position -= 1
        merge_events.append(
            {
                "fragment_start": atom.start,
                "fragment_end": atom.end,
                "fragment_core_chars": core_length,
                "merged_direction": direction,
            }
        )
    if any(len(semantic_core(text[atom.start : atom.end])) <= SHORT_CORE_MAX for atom in atoms) and len(atoms) > 1:
        raise ValueError("仍有极短碎片独立成自然原子")
    return atoms, merge_events


def partition_atoms(atoms: list[Atom], target: int, minimum: int, maximum: int) -> list[tuple[int, int, str]]:
    count = len(atoms)
    best: list[tuple[tuple[int, int, int, int, int], list[tuple[int, int, str]]] | None] = [None] * (count + 1)
    best[count] = ((0, 0, 0, 0, 0), [])
    for first in range(count - 1, -1, -1):
        options = []
        for last in range(first + 1, count + 1):
            length = atoms[last - 1].end - atoms[first].start
            violation = int(not minimum <= length <= maximum)
            outside_chars = max(minimum - length, 0) + max(length - maximum, 0)
            deviation = abs(length - target)
            non_paragraph_boundary = int(last != count and atoms[last - 1].boundary_after != "PARAGRAPH")
            tail = best[last]
            if tail is None:
                continue
            tail_cost, tail_blocks = tail
            cost = (
                outside_chars + tail_cost[0],
                violation + tail_cost[1],
                deviation + tail_cost[2],
                non_paragraph_boundary + tail_cost[3],
                1 + tail_cost[4],
            )
            options.append(
                (
                    cost,
                    last,
                    [(atoms[first].start, atoms[last - 1].end, atoms[last - 1].boundary_after), *tail_blocks],
                )
            )
        if not options:
            raise ValueError("无法生成自然边界分块")
        _, _, selected_blocks = min(options, key=lambda item: (item[0], item[1]))
        selected_cost = min(options, key=lambda item: (item[0], item[1]))[0]
        best[first] = (selected_cost, selected_blocks)
    result = best[0]
    if result is None:
        raise ValueError("分块动态规划没有结果")
    return result[1]


def overlapping_unit_ids(units: list[dict[str, Any]], start: int, end: int) -> list[str]:
    return [unit["id"] for unit in units if unit["start"] < end and start < unit["end"]]


def make_candidate_rows(
    source_rows: list[dict[str, Any]], txx_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, list[tuple[int, int]]]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    spans_by_band: dict[str, dict[str, list[tuple[int, int]]]] = {band: {} for band in [*BANDS, "BLOCK600"]}
    merge_counts: dict[str, int] = {}
    for source, txx in zip(source_rows, txx_rows, strict=True):
        case_id = source["case_id"]
        text = "".join(unit["text"] for unit in txx["target_units"])
        atoms, merge_events = natural_atoms(text)
        merge_counts[case_id] = len(merge_events)
        band_blocks: dict[str, list[tuple[int, int, str]]] = {}
        for band, contract in BANDS.items():
            band_blocks[band] = partition_atoms(atoms, contract["target"], contract["minimum"], contract["maximum"])
        band_blocks["BLOCK600"] = [(0, len(text), "TARGET_END")]
        for band in ["BLOCK60", "BLOCK300", "BLOCK600"]:
            blocks = band_blocks[band]
            spans_by_band[band][case_id] = [(start, end) for start, end, _ in blocks]
            contract = BANDS.get(band)
            for block_index, (start, end, boundary_after) in enumerate(blocks, 1):
                block_text = text[start:end]
                preferred = True if contract is None else contract["minimum"] <= len(block_text) <= contract["maximum"]
                rows.append(
                    {
                        "schema_version": "base-out2-target-block-candidate/1.0",
                        "status": STATUS,
                        "band": band,
                        "case_id": case_id,
                        "block_id": f"{case_id}-B{band.removeprefix('BLOCK')}-{block_index:02d}",
                        "block_index": block_index,
                        "block_count_in_case": len(blocks),
                        "parent_target_sha256": source["target_sha256"],
                        "source_path": source["source_path"],
                        "source_sha256": source["source_sha256"],
                        "target_relative_start": start,
                        "target_relative_end": end,
                        "source_absolute_start": source["target_start"] + start,
                        "source_absolute_end": source["target_start"] + end,
                        "block_sha256": sha256_bytes(block_text.encode("utf-8")),
                        "unicode_codepoints": len(block_text),
                        "non_whitespace_codepoints": sum(not character.isspace() for character in block_text),
                        "end_boundary": boundary_after,
                        "preferred_length_range_met": preferred,
                        "overlapping_parent_txx_ids": overlapping_unit_ids(txx["target_units"], start, end),
                        "boundary_selection_uses_gold": False,
                        "model_visible_density_metadata": False,
                        "future_new_inference": band != "BLOCK600",
                    }
                )
    return rows, spans_by_band, merge_counts


def audit_after_boundaries_frozen(
    candidate_rows: list[dict[str, Any]],
    spans_by_band: dict[str, dict[str, list[tuple[int, int]]]],
    txx_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    gold_rows = read_jsonl(GOLD)
    if len(gold_rows) != 24 or [row["case_id"] for row in gold_rows] != [f"C{i:02d}" for i in range(1, 25)]:
        raise ValueError("Gold不是冻结的C01-C24")
    txx_by_case = {row["case_id"]: row for row in txx_rows}
    candidate_by_band_case: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in candidate_rows:
        candidate_by_band_case.setdefault((row["band"], row["case_id"]), []).append(row)
    result: dict[str, Any] = {}
    total_facts = sum(len(row["facts"]) for row in gold_rows)
    for band in ["BLOCK60", "BLOCK300", "BLOCK600"]:
        crossing_fact_ids: dict[str, list[str]] = {}
        contained = 0
        crossing = 0
        empty_blocks = 0
        case_stats: dict[str, Any] = {}
        for gold_row in gold_rows:
            case_id = gold_row["case_id"]
            units = {unit["id"]: (unit["start"], unit["end"]) for unit in txx_by_case[case_id]["target_units"]}
            blocks = spans_by_band[band][case_id]
            block_fact_counts = [0] * len(blocks)
            case_crossing: list[str] = []
            for fact_index, fact in enumerate(gold_row["facts"], start=1):
                evidence = fact["evidence_ids"]
                if not evidence or any(unit_id not in units for unit_id in evidence):
                    raise ValueError(f"{case_id} Gold evidence非法")
                evidence_start = min(units[unit_id][0] for unit_id in evidence)
                evidence_end = max(units[unit_id][1] for unit_id in evidence)
                owners = [
                    index
                    for index, (block_start, block_end) in enumerate(blocks)
                    if block_start <= evidence_start and evidence_end <= block_end
                ]
                if len(owners) == 1:
                    contained += 1
                    block_fact_counts[owners[0]] += 1
                else:
                    crossing += 1
                    case_crossing.append(f"{case_id}-F{fact_index:03d}")
            empty_blocks += sum(count == 0 for count in block_fact_counts)
            if case_crossing:
                crossing_fact_ids[case_id] = case_crossing
            case_stats[case_id] = {
                "blocks": len(blocks),
                "contained_gold_facts": sum(block_fact_counts),
                "crossing_gold_facts": len(case_crossing),
                "gold_empty_blocks": sum(count == 0 for count in block_fact_counts),
            }
        band_rows = [row for row in candidate_rows if row["band"] == band]
        lengths = sorted(row["unicode_codepoints"] for row in band_rows)
        minimum = BANDS.get(band, {}).get("minimum")
        maximum = BANDS.get(band, {}).get("maximum")
        under = 0 if minimum is None else sum(length < minimum for length in lengths)
        over = 0 if maximum is None else sum(length > maximum for length in lengths)
        result[band] = {
            "blocks_full24": len(band_rows),
            "conceptual_calls_full24": len(band_rows),
            "new_calls_full24": 0 if band == "BLOCK600" else len(band_rows),
            "blocks_stage1_8": sum(row["case_id"] in STAGE1_CASES for row in band_rows),
            "conceptual_calls_stage1_8": sum(row["case_id"] in STAGE1_CASES for row in band_rows),
            "new_calls_stage1_8": 0 if band == "BLOCK600" else sum(row["case_id"] in STAGE1_CASES for row in band_rows),
            "unicode_codepoints_min": lengths[0],
            "unicode_codepoints_median": (lengths[(len(lengths) - 1) // 2] + lengths[len(lengths) // 2]) / 2,
            "unicode_codepoints_max": lengths[-1],
            "text_empty_blocks": sum(length == 0 for length in lengths),
            "gold_empty_blocks": empty_blocks,
            "under_preferred_min_blocks": under,
            "over_preferred_max_blocks": over,
            "gold_facts_total": total_facts,
            "gold_facts_contained_within_one_block": contained,
            "gold_facts_crossing_blocks": crossing,
            "gold_fact_crossing_ratio": round(crossing / total_facts, 6),
            "crossing_fact_ids_by_case": crossing_fact_ids,
            "case_stats": case_stats,
        }
    return result


def build_outputs() -> tuple[bytes, bytes]:
    source_rows, txx_rows = verify_inputs()
    candidates, spans_by_band, merge_counts = make_candidate_rows(source_rows, txx_rows)
    audit = audit_after_boundaries_frozen(candidates, spans_by_band, txx_rows)
    target_lengths = [row["target_end"] - row["target_start"] for row in source_rows]
    stats = {
        "schema_version": "base-out2-target-block-coarse-screen-stats/1.0",
        "status": STATUS,
        "boundary_selection_stage": {
            "gold_read": False,
            "input_cases": 24,
            "target_unicode_codepoints_min": min(target_lengths),
            "target_unicode_codepoints_max": max(target_lengths),
            "short_fragment_core_chars_max": SHORT_CORE_MAX,
            "short_fragment_merge_events_total": sum(merge_counts.values()),
            "short_fragment_merge_events_by_case": merge_counts,
            "standalone_short_fragment_atoms_after_merge": 0,
        },
        "post_freeze_gold_audit_stage": {
            "gold_read_only_after_boundaries_frozen": True,
            "gold_moved_boundaries": False,
            "gold_facts_total": sum(len(row["facts"]) for row in read_jsonl(GOLD)),
            "bands": audit,
            "residual_crossings_are_reported_not_repaired": True,
        },
        "future_call_summary": {
            "full24_new_calls_block60_plus_block300": audit["BLOCK60"]["new_calls_full24"]
            + audit["BLOCK300"]["new_calls_full24"],
            "full24_block600_reused_calls": 24,
            "full24_block600_new_calls": 0,
            "stage1_cases": sorted(STAGE1_CASES),
            "stage1_new_calls_block60_plus_block300": audit["BLOCK60"]["new_calls_stage1_8"]
            + audit["BLOCK300"]["new_calls_stage1_8"],
            "stage1_block600_reused_calls": 8,
            "stage1_block600_new_calls": 0,
        },
        "meaning": {
            "fixed_halo_unicode_chars_each_side_max": 180,
            "same_original_target_covered_by_every_band": True,
            "small_block_outputs_aggregate_before_original_gold_scoring": True,
            "not_three_by_three": True,
            "candidate_only_not_request_or_gold": True,
        },
        "actions": {
            "model_loads": 0,
            "training": 0,
            "inference": 0,
            "api_calls": 0,
            "notion_actions": 0,
            "git_actions": 0,
            "current_or_production_actions": 0,
        },
    }
    return jsonl_bytes(candidates), json_bytes(stats)


def write_outputs() -> None:
    candidate_bytes, stats_bytes = build_outputs()
    CANDIDATES.write_bytes(candidate_bytes)
    STATS.write_bytes(stats_bytes)
    print(
        compact_json(
            {
                "status": "BUILT_CANDIDATE_PREFLIGHT",
                "candidates_sha256": sha256_bytes(candidate_bytes),
                "stats_sha256": sha256_bytes(stats_bytes),
            }
        )
    )


def check_outputs() -> None:
    candidate_bytes, stats_bytes = build_outputs()
    if CANDIDATES.read_bytes() != candidate_bytes or STATS.read_bytes() != stats_bytes:
        raise ValueError("候选或统计不是当前脚本的确定性输出")
    print(
        compact_json(
            {
                "status": "PASS_DETERMINISTIC_CHECK",
                "candidate_rows": len(read_jsonl(CANDIDATES)),
                "candidates_sha256": sha256_bytes(candidate_bytes),
                "stats_sha256": sha256_bytes(stats_bytes),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()
    if args.command == "build":
        write_outputs()
    else:
        check_outputs()


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
R01 = ROOT / "finetuning/experiments/T5_R04_BASE_OUT2_TARGET_BLOCK_COARSE_SCREEN_PREFLIGHT_20260810_R01"
R01_BUILDER = R01 / "build_target_block_candidates.py"
REAL24 = ROOT / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
SOURCE_INDEX = REAL24 / "REAL24_SOURCE_INDEX.jsonl"
TXX = REAL24 / "REAL24_TXX_MAP.jsonl"
GOLD = REAL24 / "REAL24_GOLD_24.jsonl"
PARENT_RUN = ROOT / "runs/T5_R04_READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_R01"
PARENT_RAW = PARENT_RUN / "inference/FULL24_MATCHED_RAW.jsonl"
H180_REQUEST = PARENT_RUN / "requests/full24/READ2.jsonl"
BASE_CONTEXT_FINAL = ROOT / "runs/T5_R04_BASE_CONTEXT_B_RELATIVE_SCREEN_R01/scoring/final/METRICS.json"
HALO_FINAL = ROOT / "runs/T5_R04_BASE_OUT2_CONTEXT_HALO_SCREEN_R01/scoring/final/METRICS.json"
HALO_RECEIPT = ROOT / "runs/T5_R04_BASE_OUT2_CONTEXT_HALO_SCREEN_R01/scoring/final/FINAL_RECEIPT.json"
CANDIDATES = OUT / "TARGET_BLOCK_CANDIDATES_R02.jsonl"
STATS = OUT / "BLOCK_STATS_R02.json"

EXPECTED_BOUNDARY_INPUT_SHA = {
    SOURCE_INDEX: "0fe7ecb1649b93e4faab3d253d8904bee7f1a7a3e6f7f0fbb8b8e722c405de97",
    TXX: "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    R01_BUILDER: "c57eea7991a31d95441efb3be3c94da6f51369ce410bca310e6784bad5624dba",
}
EXPECTED_POST_FREEZE_SHA = {
    GOLD: "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    PARENT_RAW: "f9bd1fc02f93cfb7c51193f1dc319753472949bc2bbde4360a6779c415cdb28e",
    H180_REQUEST: "126b0f0843fdd244f007a46361397f24f97ce8d71c73d760ae9ad5a6bf5b3088",
    BASE_CONTEXT_FINAL: "f625c10ecf0e1d4be8eade2032dc2fdbe6d398ac55a6ad89f47abffa117825c7",
    HALO_FINAL: "068c1341f0f4e48446dc175e0f2dee46078962f3f611e7505907e3cb886bafac",
    HALO_RECEIPT: "d874fca864278bd9002c1b6e2a9cee8d6abaada57e3522c36c34d30e5de49cfa",
}
STAGE1_CASES = {"C01", "C02", "C05", "C09", "C10", "C14", "C23", "C24"}
STATUS = "CANDIDATE_PREFLIGHT_R02_NOT_AUTHORIZED_NOT_RUN"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return (
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) for row in rows)
        + "\n"
    ).encode()


def load_r01() -> Any:
    spec = importlib.util.spec_from_file_location("target_block_r01_builder", R01_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("R01_BUILDER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify_boundary_inputs_only(r01: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actual = {path: sha256(path) for path in EXPECTED_BOUNDARY_INPUT_SHA}
    if actual != EXPECTED_BOUNDARY_INPUT_SHA:
        raise RuntimeError("BOUNDARY_INPUT_SHA_DRIFT")
    source_rows = read_jsonl(SOURCE_INDEX)
    txx_rows = read_jsonl(TXX)
    cases = [f"C{index:02d}" for index in range(1, 25)]
    if [row["case_id"] for row in source_rows] != cases or [row["case_id"] for row in txx_rows] != cases:
        raise RuntimeError("BOUNDARY_INPUT_CASE_ORDER_DRIFT")
    for source, txx in zip(source_rows, txx_rows, strict=True):
        target = "".join(unit["text"] for unit in txx["target_units"])
        if sha256_bytes(target.encode()) != source["target_sha256"]:
            raise RuntimeError(f"TARGET_SHA_DRIFT:{source['case_id']}")
        if source["target_end"] - source["target_start"] != len(target):
            raise RuntimeError(f"TARGET_COORDINATE_DRIFT:{source['case_id']}")
    return source_rows, txx_rows


def r02_rows(base_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dispositions = {
        "BLOCK60": "MECHANICAL_EXIT_TOO_FRAGMENTED_ZERO_MODEL_CALLS",
        "BLOCK300": "ONLY_STAGE1_CANDIDATE",
        "BLOCK600": "FROZEN_REUSE",
    }
    result = []
    for source in base_rows:
        row = dict(source)
        original_band = row["band"]
        row["status"] = STATUS
        row["screen_disposition"] = dispositions[original_band]
        row["future_new_inference"] = original_band == "BLOCK300"
        if original_band == "BLOCK600":
            row["band"] = "FULL_TARGET"
            row["block_id"] = f"{row['case_id']}-FULL-01"
            row["human_name_zh"] = "完整段档"
        result.append(row)
    return result


def exact_h180_projection() -> tuple[int, str]:
    selected = []
    count = 0
    for line in PARENT_RAW.read_bytes().splitlines(keepends=True):
        if json.loads(line).get("variant") == "BASE_READ2":
            selected.append(line)
            count += 1
    return count, sha256_bytes(b"".join(selected))


def post_freeze_audit(
    r01: Any,
    boundary_candidate_sha: str,
    base_rows: list[dict[str, Any]],
    spans: dict[str, dict[str, list[tuple[int, int]]]],
    txx_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    actual = {path: sha256(path) for path in EXPECTED_POST_FREEZE_SHA}
    if actual != EXPECTED_POST_FREEZE_SHA:
        raise RuntimeError("POST_FREEZE_INPUT_SHA_DRIFT")
    audit = r01.audit_after_boundaries_frozen(base_rows, spans, txx_rows)
    projection_rows, projection_sha = exact_h180_projection()
    if projection_rows != 24 or projection_sha != "c7f738181148acc4c06644e47058606b35f07b9a0603521ffdb98502267b1b97":
        raise RuntimeError("H180_BASE_READ2_PROJECTION_DRIFT")
    halo = read_json(HALO_FINAL)
    if halo["selection"]["candidates"]["H180"]["f1"] != 0.352941:
        raise RuntimeError("H180_FINAL_F1_DRIFT")
    reuse = {
        "full24_raw_path": str(PARENT_RAW.relative_to(ROOT)),
        "full24_raw_sha256": actual[PARENT_RAW],
        "projection_rule": "EXACT_ORIGINAL_BYTES_WHERE_VARIANT_EQUALS_BASE_READ2",
        "projection_rows": projection_rows,
        "projection_sha256": projection_sha,
        "actual_request_path": str(H180_REQUEST.relative_to(ROOT)),
        "actual_request_sha256": actual[H180_REQUEST],
        "base_context_final_path": str(BASE_CONTEXT_FINAL.relative_to(ROOT)),
        "base_context_final_sha256": actual[BASE_CONTEXT_FINAL],
        "halo_final_metrics_path": str(HALO_FINAL.relative_to(ROOT)),
        "halo_final_metrics_sha256": actual[HALO_FINAL],
        "halo_final_receipt_path": str(HALO_RECEIPT.relative_to(ROOT)),
        "halo_final_receipt_sha256": actual[HALO_RECEIPT],
        "recoverable_semantic_f1": 0.352941,
    }
    return audit, {
        "candidate_sha256_frozen_before_any_gold_read": boundary_candidate_sha,
        "gold_sha256_verified_after_candidate_freeze": actual[GOLD],
        "reuse": reuse,
    }


def old_txx_boundary_diagnostic(
    spans: dict[str, dict[str, list[tuple[int, int]]]],
    txx_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    txx_by_case = {row["case_id"]: row for row in txx_rows}
    full_internal = full_cut = stage_internal = stage_cut = 0
    for case_id, blocks in spans["BLOCK300"].items():
        old_boundaries = {unit["end"] for unit in txx_by_case[case_id]["target_units"][:-1]}
        internal = [end for _, end in blocks[:-1]]
        cut = sum(boundary not in old_boundaries for boundary in internal)
        full_internal += len(internal)
        full_cut += cut
        if case_id in STAGE1_CASES:
            stage_internal += len(internal)
            stage_cut += cut
    return {
        "full24_internal_block_boundaries": full_internal,
        "full24_boundaries_cutting_old_txx": full_cut,
        "stage1_internal_block_boundaries": stage_internal,
        "stage1_boundaries_cutting_old_txx": stage_cut,
        "resolution": "STAGE1_REGENERATES_BLOCK_LOCAL_TXX_WITH_THREE_LEVEL_COORDINATE_MAPPING",
    }


def build_outputs() -> tuple[bytes, bytes]:
    r01 = load_r01()
    source_rows, txx_rows = verify_boundary_inputs_only(r01)
    base_rows, spans, merge_counts = r01.make_candidate_rows(source_rows, txx_rows)
    candidates = r02_rows(base_rows)
    candidate_bytes = jsonl_bytes(candidates)
    candidate_sha = sha256_bytes(candidate_bytes)
    audit, order_evidence = post_freeze_audit(r01, candidate_sha, base_rows, spans, txx_rows)
    stage1 = {}
    for band in ("BLOCK60", "BLOCK300", "BLOCK600"):
        case_stats = audit[band]["case_stats"]
        stage1[band] = {
            "blocks": sum(case_stats[case]["blocks"] for case in STAGE1_CASES),
            "contained_gold_facts": sum(case_stats[case]["contained_gold_facts"] for case in STAGE1_CASES),
            "crossing_gold_facts": sum(case_stats[case]["crossing_gold_facts"] for case in STAGE1_CASES),
            "gold_empty_blocks": sum(case_stats[case]["gold_empty_blocks"] for case in STAGE1_CASES),
        }
    stats = {
        "schema_version": "base-out2-target-block-coarse-screen-stats/2.0",
        "status": STATUS,
        "evidence_order": {
            "before_boundary_freeze_read_paths": [
                str(SOURCE_INDEX.relative_to(ROOT)),
                str(TXX.relative_to(ROOT)),
                str(R01_BUILDER.relative_to(ROOT)),
            ],
            "gold_bytes_read_before_candidate_sha_freeze": False,
            "steps": [
                "VERIFY_SOURCE_INDEX_AND_TXX_ONLY",
                "BUILD_BOUNDARIES_WITHOUT_GOLD",
                "SERIALIZE_AND_SHA_FREEZE_CANDIDATES",
                "READ_AND_VERIFY_GOLD",
                "AUDIT_WITHOUT_MOVING_BOUNDARIES",
            ],
            **order_evidence,
        },
        "screen_disposition": {
            "BLOCK60": "MECHANICAL_EXIT_TOO_FRAGMENTED_ZERO_MODEL_CALLS",
            "BLOCK300": "ONLY_STAGE1_CANDIDATE",
            "FULL_TARGET": "FROZEN_REUSE",
        },
        "full24_audit": {
            "BLOCK60": audit["BLOCK60"],
            "BLOCK300": audit["BLOCK300"],
            "FULL_TARGET": audit["BLOCK600"],
        },
        "stage1_8_audit": {
            "case_ids": sorted(STAGE1_CASES),
            "gold_facts": 85,
            "BLOCK60": stage1["BLOCK60"],
            "BLOCK300": stage1["BLOCK300"],
            "FULL_TARGET": stage1["BLOCK600"],
        },
        "old_txx_boundary_diagnostic": old_txx_boundary_diagnostic(spans, txx_rows),
        "full_target_length_unicode_codepoints": {"min": 620, "median": 760.0, "max": 923},
        "short_fragment_merge_events": sum(merge_counts.values()),
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
    return candidate_bytes, json_bytes(stats)


def write_outputs() -> None:
    candidate_bytes, stats_bytes = build_outputs()
    CANDIDATES.write_bytes(candidate_bytes)
    STATS.write_bytes(stats_bytes)
    print(json.dumps({"status": "BUILT_R02", "candidate_sha256": sha256_bytes(candidate_bytes), "stats_sha256": sha256_bytes(stats_bytes)}))


def check_outputs() -> None:
    candidate_bytes, stats_bytes = build_outputs()
    if CANDIDATES.read_bytes() != candidate_bytes or STATS.read_bytes() != stats_bytes:
        raise RuntimeError("R02_OUTPUT_DRIFT")
    print(json.dumps({"status": "PASS_R02_DETERMINISM", "rows": len(read_jsonl(CANDIDATES))}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()
    write_outputs() if args.command == "build" else check_outputs()


if __name__ == "__main__":
    main()

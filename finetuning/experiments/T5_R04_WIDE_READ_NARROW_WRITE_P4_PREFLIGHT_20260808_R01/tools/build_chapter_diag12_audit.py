#!/usr/bin/env python3
"""Build the P4 complete-chapter eligibility audit from metadata only.

This tool never opens a chapter-text file. It reads manifests, locks, rights
receipts, source maps, and the formal-gold registry; chapter paths are checked
with stat only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
OLD_ROOT = REPO / ".local/T5_CHATGPT_PRO_5_ZIPS_R04_20260731/deliverable_r01"
OLD_MANIFEST = OLD_ROOT / "MANIFEST.jsonl"
OLD_LOCK = REPO / ".local/T5_CHATGPT_PRO_5_ZIPS_R04_20260731/chapter_selection_lock.tsv"
OLD_BUILD_RECEIPT = OLD_ROOT / "BUILD_RECEIPT.json"
OLD_RIGHTS_NOTICE = (
    REPO / ".local/T5_CHATGPT_PRO_5_ZIPS_R04_20260731/package_common/05_RIGHTS_AND_HOLDOUT_NOTICE.md"
)
WAVE_ROOT = Path(
    "/Users/a1234/挣钱/小说架构_隔离实验/"
    "T5_R04_EXPANSION_WAVE01_20260802_R01/deliverables/packages"
)
WAVE_REEXTRACT_RECEIPT = Path(
    "/Users/a1234/挣钱/小说架构_隔离实验/"
    "T5_R04_WAVE01_R02_FIVE_WINDOW_REEXTRACT_20260803_R01/receipts/BUILD_RECEIPT.json"
)
WAVE_CANDIDATE_RECEIPT = Path(
    "/Users/a1234/挣钱/小说架构_隔离实验/"
    "T5_R04_WAVE01_SECOND_TRAINING_CANDIDATE_20260803_R01/"
    "deliverables/AGGREGATE_BUILD_RECEIPT.json"
)
P04_SOURCE_MAP = Path(
    "/Users/a1234/挣钱/小说架构_隔离实验/"
    "T5_R04_EVIDENCE_ID_DUAL_LORA_20260804_R01/mapping/"
    "P04_PREFLIGHT_SOURCE_MAP_R01.jsonl"
)
TRAIN_SOURCE_MAP = Path(
    "/Users/a1234/挣钱/小说架构_隔离实验/"
    "T5_R04_EVIDENCE_ID_DUAL_LORA_20260804_R01/mapping/TRAIN_585_SOURCE_MAP.jsonl"
)
FORMAL_GOLD_REGISTRY = REPO / "config/gold/formal_gold_registry.json"
GOLD_CURRENT = REPO / "governance/indexes/gold_current.md"

BLOCKED_WAVE = {
    "T5W01-018": "BOOK_IDENTITY_CONFLICT",
    "T5W01-045": "MIXED_BOOK_TEXT_CONTAMINATION",
}
OLD_EVAL = {
    "T5R04-017",
    "T5R04-018",
    "T5R04-023",
    "T5R04-024",
    "T5R04-033",
    "T5R04-038",
    "T5R04-040",
    "T5R04-043",
}
IDENTITY_CONFLICT = {
    "T5R04-003",
    "T5R04-009",
    "T5R04-016",
    "T5R04-026",
    "T5R04-045",
    "T5W01-001",
    "T5W01-016",
    "T5W01-041",
    "T5W01-050",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def evidence(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def wave_rows() -> tuple[list[dict[str, Any]], list[Path], list[Path]]:
    rows: list[dict[str, Any]] = []
    manifests: list[Path] = []
    rights: list[Path] = []
    for batch_number in range(1, 6):
        batch = WAVE_ROOT / f"BATCH_{batch_number:02d}"
        manifest = batch / "BATCH_MANIFEST.json"
        checklist = batch / "RIGHTS_CHECKLIST.tsv"
        manifests.append(manifest)
        rights.append(checklist)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        for row in payload["samples"]:
            rows.append({**row, "batch_id": payload["batch_id"], "package_root": str(batch)})
    return rows, manifests, rights


def map_by_sample(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[row["sample_id"]].append(row)
    return out


def coord_summary(sample_id: str, rows: list[dict[str, Any]], registered_sha: str) -> dict[str, Any]:
    if not rows:
        return {
            "status": "NO_DOWNSTREAM_POINTER",
            "canonical_source_paths": [],
            "canonical_source_sha256": [],
            "downstream_chapter_ids": [],
            "downstream_chapter_sha256": [],
            "observed_responsibility_char_start": None,
            "observed_responsibility_char_end": None,
            "registered_chapter_sha_matches_downstream": False,
            "cross_sha_proof": False,
        }
    chapter_shas = sorted({row.get("chapter_sha256") for row in rows if row.get("chapter_sha256")})
    starts = [row["responsibility_char_start"] for row in rows]
    ends = [row["responsibility_char_end"] for row in rows]
    return {
        "status": "DOWNSTREAM_POINTER_PRESENT_CROSS_SHA_UNPROVEN",
        "canonical_source_paths": sorted({row["source_path"] for row in rows}),
        "canonical_source_sha256": sorted({row["source_sha256"] for row in rows}),
        "downstream_chapter_ids": sorted({row["chapter_id"] for row in rows}),
        "downstream_chapter_sha256": chapter_shas,
        "observed_responsibility_char_start": min(starts),
        "observed_responsibility_char_end": max(ends),
        "registered_chapter_sha_matches_downstream": registered_sha in chapter_shas,
        "cross_sha_proof": False,
        "special_gap": (
            "OBSERVED_COORDINATE_SPAN_493_CHARS_SHORTER_THAN_REGISTERED_CHAPTER"
            if sample_id == "T5W01-025"
            else None
        ),
    }


def build() -> dict[str, Any]:
    old = jsonl(OLD_MANIFEST)
    wave, wave_manifests, wave_rights = wave_rows()
    p04 = map_by_sample(jsonl(P04_SOURCE_MAP))
    train = map_by_sample(jsonl(TRAIN_SOURCE_MAP))
    train_sample_ids = set(train)
    wave_by_sha = defaultdict(list)
    for row in wave:
        wave_by_sha[row["chapter_sha256"]].append(row["sample_id"])

    candidates: list[dict[str, Any]] = []
    for row in old:
        source_path = Path(row["source_chapter"])
        copied_path = OLD_ROOT / "packages" / row["batch_id"] / row["copied_file"]
        same_wave_ids = sorted(wave_by_sha.get(row["sha256"], []))
        if row["sample_id"] in train_sample_ids:
            historical_split = "TRAIN"
            match_type = "SAMPLE_ID_IN_TRAIN_MAP"
            matched = [row["sample_id"]]
        elif any(sample_id in train_sample_ids for sample_id in same_wave_ids):
            historical_split = "TRAIN"
            match_type = "IDENTICAL_CHAPTER_SHA_TO_TRAINED_WAVE_SAMPLE"
            matched = same_wave_ids
        elif row["sample_id"] in OLD_EVAL:
            historical_split = "EVAL_HOLDOUT"
            match_type = "HISTORICAL_EVAL_REGISTRY"
            matched = [row["sample_id"]]
        else:
            raise RuntimeError(f"unclassified old candidate: {row['sample_id']}")
        failures = [
            "LOCAL_INTERNAL_DIAGNOSTIC_EVALUATION_RIGHT_NOT_EXPLICIT",
            "FORMAL_GOLD_NOT_FROZEN_BEFORE_SPLIT_WITH_ABSOLUTE_COORDINATES",
            "SOURCE_POINTER_SHA_NOT_LIVE_RECOMPUTED",
            "DOWNSTREAM_COORDINATE_CROSS_SHA_PROOF_MISSING",
            f"HISTORICAL_{historical_split}_CONTAMINATION",
        ]
        if row["sample_id"] in IDENTITY_CONFLICT:
            failures.append("CHAPTER_NUMBER_IDENTITY_CONFLICT")
        candidates.append(
            {
                "candidate_key": f"OLD_PREP_ONLY::{row['sample_id']}",
                "family": "OLD_PREP_ONLY_50",
                "sample_id": row["sample_id"],
                "batch_id": row["batch_id"],
                "title": row["title"],
                "author": row["author"],
                "declared_chapter_number": row["actual_chapter_number"],
                "source_sequence_number": None,
                "registered_source_path": str(source_path),
                "copied_path": str(copied_path),
                "registered_byte_count": row["byte_count"],
                "registered_sha256": row["sha256"],
                "source_path_exists": source_path.exists(),
                "copied_path_exists": copied_path.exists(),
                "source_byte_count_matches": source_path.exists()
                and source_path.stat().st_size == row["byte_count"],
                "copied_byte_count_matches": copied_path.exists()
                and copied_path.stat().st_size == row["byte_count"],
                "sha_live_recomputed": False,
                "rights": {
                    "third_party_annotation": row["third_party_annotation_rights"],
                    "training": row["training_rights"],
                    "local_internal_diag_eval": "NOT_EXPLICIT",
                    "evidence_ref": str(OLD_RIGHTS_NOTICE),
                },
                "identity": {
                    "status": (
                        "CHAPTER_NUMBER_CONFLICT"
                        if row["sample_id"] in IDENTITY_CONFLICT
                        else "REGISTERED_IDENTITY_NO_LIVE_RECHECK"
                    ),
                    "downstream_chapter_ids": sorted(
                        {item["chapter_id"] for item in p04.get(row["sample_id"], [])}
                    ),
                },
                "coordinates": coord_summary(
                    row["sample_id"], p04.get(row["sample_id"], []), row["sha256"]
                ),
                "gold": {
                    "status": "NO_FORMAL_PRE_SPLIT_WHOLE_CHAPTER_GOLD_WITH_COORDINATES",
                    "formal_registry_entry": None,
                    "pre_split_formally_frozen": False,
                    "anchor_mapping_status": "MISSING",
                },
                "contamination": {
                    "historical_split": historical_split,
                    "match_type": match_type,
                    "matched_sample_ids": matched,
                },
                "pointer_status": "REGISTERED_PATHS_PRESENT_SHA_NOT_LIVE_RECOMPUTED",
                "fail_reasons": failures,
                "eligible": False,
            }
        )

    for row in wave:
        copied_path = Path(row["package_root"]) / row["copied_file"]
        blocked = BLOCKED_WAVE.get(row["sample_id"])
        if blocked:
            historical_split = "BLOCKED_SOURCE_ANOMALY"
            match_type = blocked
        elif row["sample_id"] in train_sample_ids:
            historical_split = "TRAIN"
            match_type = "SAMPLE_ID_IN_TRAIN_MAP"
        else:
            raise RuntimeError(f"unclassified wave candidate: {row['sample_id']}")
        failures = [
            "LOCAL_INTERNAL_DIAGNOSTIC_EVALUATION_RIGHT_NOT_EXPLICIT",
            "FORMAL_GOLD_NOT_FROZEN_BEFORE_SPLIT_WITH_ABSOLUTE_COORDINATES",
            "ORIGINAL_SOURCE_PATH_NOT_REGISTERED_IN_WAVE_MANIFEST",
            "SOURCE_POINTER_SHA_NOT_LIVE_RECOMPUTED",
            "DOWNSTREAM_COORDINATE_CROSS_SHA_PROOF_MISSING",
            (
                "BLOCKED_SOURCE_ANOMALY"
                if blocked
                else "HISTORICAL_TRAIN_CONTAMINATION"
            ),
        ]
        if row["sample_id"] in IDENTITY_CONFLICT:
            failures.append("CHAPTER_NUMBER_IDENTITY_CONFLICT")
        candidates.append(
            {
                "candidate_key": f"WAVE01::{row['sample_id']}",
                "family": "WAVE01_50",
                "sample_id": row["sample_id"],
                "batch_id": row["batch_id"],
                "title": row["title"],
                "author": row["author"],
                "declared_chapter_number": row["declared_chapter_number"],
                "source_sequence_number": row["source_sequence_number"],
                "registered_source_path": None,
                "copied_path": str(copied_path),
                "registered_byte_count": row["chapter_byte_count"],
                "registered_sha256": row["chapter_sha256"],
                "source_path_exists": False,
                "copied_path_exists": copied_path.exists(),
                "source_byte_count_matches": False,
                "copied_byte_count_matches": copied_path.exists()
                and copied_path.stat().st_size == row["chapter_byte_count"],
                "sha_live_recomputed": False,
                "rights": {
                    "third_party_annotation": "CONFIRMED_BY_CZ",
                    "training": "CONFIRMED_BY_CZ",
                    "local_internal_diag_eval": "NOT_EXPLICIT",
                    "evidence_ref": str(
                        Path(row["package_root"]) / "RIGHTS_CHECKLIST.tsv"
                    ),
                },
                "identity": {
                    "status": (
                        blocked
                        or (
                            "CHAPTER_NUMBER_CONFLICT"
                            if row["sample_id"] in IDENTITY_CONFLICT
                            else "REGISTERED_IDENTITY_NO_LIVE_RECHECK"
                        )
                    ),
                    "downstream_chapter_ids": sorted(
                        {item["chapter_id"] for item in p04.get(row["sample_id"], [])}
                    ),
                },
                "coordinates": coord_summary(
                    row["sample_id"], p04.get(row["sample_id"], []), row["chapter_sha256"]
                ),
                "gold": {
                    "status": "CANDIDATE_ANNOTATION_WITHOUT_PRE_SPLIT_ABSOLUTE_COORDINATES",
                    "formal_registry_entry": None,
                    "pre_split_formally_frozen": False,
                    "anchor_mapping_status": "POST_HOC_CANDIDATE_NOT_FORMAL_GOLD",
                },
                "contamination": {
                    "historical_split": historical_split,
                    "match_type": match_type,
                    "matched_sample_ids": [row["sample_id"]],
                },
                "pointer_status": (
                    "BLOCKED_SOURCE_ANOMALY"
                    if blocked
                    else "PACKAGE_COPY_PRESENT_ORIGINAL_SOURCE_PATH_MISSING"
                ),
                "fail_reasons": failures,
                "eligible": False,
            }
        )

    if len(candidates) != 100:
        raise RuntimeError(f"candidate count drift: {len(candidates)}")
    unique_sha = {row["registered_sha256"] for row in candidates}
    if len(unique_sha) != 89:
        raise RuntimeError(f"unique chapter SHA count drift: {len(unique_sha)}")

    unique_status: dict[str, str] = {}
    for row in candidates:
        chapter_sha = row["registered_sha256"]
        split = row["contamination"]["historical_split"]
        prior = unique_status.get(chapter_sha)
        if prior and prior != split:
            raise RuntimeError(f"inconsistent split for chapter SHA {chapter_sha}: {prior} vs {split}")
        unique_status[chapter_sha] = split
    unique_counts = Counter(unique_status.values())
    expected_unique = {"TRAIN": 79, "EVAL_HOLDOUT": 8, "BLOCKED_SOURCE_ANOMALY": 2}
    if dict(unique_counts) != expected_unique:
        raise RuntimeError(f"unique split drift: {dict(unique_counts)}")

    batch_counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for row in candidates:
        family = row["family"]
        batch_counts[family][row["batch_id"]][row["contamination"]["historical_split"]] += 1

    evidence_paths = [
        OLD_MANIFEST,
        OLD_LOCK,
        OLD_BUILD_RECEIPT,
        OLD_RIGHTS_NOTICE,
        *wave_manifests,
        *wave_rights,
        WAVE_REEXTRACT_RECEIPT,
        WAVE_CANDIDATE_RECEIPT,
        P04_SOURCE_MAP,
        TRAIN_SOURCE_MAP,
        FORMAL_GOLD_REGISTRY,
        GOLD_CURRENT,
    ]
    return {
        "schema_version": "t5-r04-p4-chapter-diag12-eligibility-audit-v1",
        "task_id": "T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01",
        "audit_mode": "REGISTRY_ONLY_NO_CHAPTER_TEXT_READ",
        "target_count": 12,
        "candidate_record_count": 100,
        "candidate_family_counts": {"OLD_PREP_ONLY_50": 50, "WAVE01_50": 50},
        "wave_reextract_is_subset_not_added": 48,
        "cross_family_duplicate_sha_count": 11,
        "unique_chapter_sha_count": 89,
        "eligible_count": 0,
        "shortfall": 12,
        "final_status": "HARD_STOP_NO_ELIGIBLE_COMPLETE_CHAPTERS",
        "unique_chapter_disposition": expected_unique,
        "qualification_counts_over_unique_chapter_sha": {
            "explicit_local_internal_diagnostic_evaluation_right": 0,
            "formal_pre_split_gold_with_absolute_coordinates": 0,
            "uncontaminated_and_not_blocked": 0,
            "complete_cross_sha_coordinate_chain": 0,
            "live_source_sha_recomputed_in_p4": 0,
        },
        "coordinate_and_identity_gaps": {
            "chapter_number_identity_conflict_candidate_records": sorted(IDENTITY_CONFLICT),
            "downstream_pointer_records_with_cross_sha_proof": 0,
            "t5w01_025_coordinate_span_shortfall_chars": 493,
        },
        "formal_gold_registry": {
            "registered_inventory_units": 6,
            "t5_complete_chapter_fact_gold_entries": 0,
            "candidate_indexing_does_not_promote_gold": True,
        },
        "batch_disposition": {
            family: {
                batch: dict(counter)
                for batch, counter in sorted(batches.items())
            }
            for family, batches in sorted(batch_counts.items())
        },
        "aggregate_failures": [
            {
                "failure": "LOCAL_INTERNAL_DIAGNOSTIC_EVALUATION_RIGHT_NOT_EXPLICIT",
                "affected_unique_chapter_sha": 89,
            },
            {
                "failure": "FORMAL_PRE_SPLIT_GOLD_WITH_ABSOLUTE_COORDINATES_MISSING",
                "affected_unique_chapter_sha": 89,
            },
            {
                "failure": "NO_UNCONTAMINATED_OR_UNBLOCKED_CHAPTER",
                "affected_unique_chapter_sha": 89,
            },
            {
                "failure": "COMPLETE_CROSS_SHA_COORDINATE_CHAIN_MISSING",
                "affected_unique_chapter_sha": 89,
            },
            {
                "failure": "LIVE_SOURCE_SHA_NOT_RECOMPUTED_IN_REGISTRY_ONLY_AUDIT",
                "affected_unique_chapter_sha": 89,
            },
        ],
        "evidence_files": [evidence(path) for path in evidence_paths],
        "caveats": [
            "Chapter text bytes were not read or copied; path and size checks used stat only.",
            "Registered chapter SHA values were compared across manifests but not recomputed from chapter text.",
            "Wave micro-annotation and post-hoc anchor artifacts remain candidate evidence, not formal gold.",
            "Training permission and third-party annotation permission were not inferred to grant local diagnostic evaluation permission.",
        ],
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": payload["final_status"],
                "eligible_count": payload["eligible_count"],
                "candidate_record_count": payload["candidate_record_count"],
                "unique_chapter_sha_count": payload["unique_chapter_sha_count"],
                "output_sha256": sha256(args.out),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

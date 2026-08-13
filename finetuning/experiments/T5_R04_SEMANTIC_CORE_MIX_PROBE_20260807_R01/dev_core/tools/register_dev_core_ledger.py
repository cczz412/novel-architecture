#!/usr/bin/env python3
"""Idempotently reserve frozen DEV_CORE windows in the shared selection ledger."""

from __future__ import annotations

import json
import argparse
from pathlib import Path


REPO = Path(__file__).resolve().parents[5]
DEV = Path(__file__).resolve().parents[1]
LEDGER = REPO / "governance/progress/t5-r04-cross-window-material-selection-ledger.jsonl"
OWNER = "T5_R04_SEMANTIC_CORE_MIX_PROBE_20260807_R01"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canon(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default="r02_run_1")
    parser.add_argument("--release-prefix")
    parser.add_argument("--mark-semantic-reviewed", action="store_true")
    args = parser.parse_args()
    source_path = DEV / args.source_dir / "SOURCE_WINDOWS.jsonl"
    current = read_jsonl(LEDGER)
    if args.mark_semantic_reviewed:
        source_ids = {row["case_id"] for row in read_jsonl(source_path)}
        updated = 0
        for row in current:
            if (
                row.get("record_type") == "material_selection"
                and row.get("owner_thread_id") == OWNER
                and row.get("segment_id") in source_ids
                and row.get("selection_status") == "PROPOSED"
            ):
                row["semantic_review"] = "LOCAL_FULL_READ_R01_PENDING_INDEPENDENT_REVIEW"
                updated += 1
        if updated != len(source_ids):
            raise SystemExit(
                f"HARD_STOP semantic ledger update mismatch: updated={updated} expected={len(source_ids)}"
            )
        LEDGER.write_text("".join(canon(row) + "\n" for row in current), encoding="utf-8")
        print(json.dumps({"status": "SEMANTIC_REVIEW_MARKED", "count": updated}, ensure_ascii=False))
        return
    if args.release_prefix:
        released = 0
        for row in current:
            if (
                row.get("record_type") == "material_selection"
                and row.get("owner_thread_id") == OWNER
                and str(row.get("segment_id", "")).startswith(args.release_prefix)
                and row.get("selection_status") in {"PROPOSED", "PROPOSED_AUTHOR_PENDING", "SELECTED"}
            ):
                row["selection_status"] = "RELEASED"
                row["release_reason"] = "GLOBAL_SOURCE_POLLUTION_RULE_R02_REBUILD"
                released += 1
        LEDGER.write_text("".join(canon(row) + "\n" for row in current), encoding="utf-8")
        print(json.dumps({"status": "RELEASED", "count": released}, ensure_ascii=False))
        return
    source = read_jsonl(source_path)
    existing_ids = {
        row.get("segment_id")
        for row in current
        if row.get("record_type") == "material_selection"
        and row.get("selection_status") in {"PROPOSED", "PROPOSED_AUTHOR_PENDING", "SELECTED"}
    }
    conflict = sorted({row["case_id"] for row in source} & existing_ids)
    if conflict:
        owned = {
            row.get("segment_id")
            for row in current
            if row.get("record_type") == "material_selection" and row.get("owner_thread_id") == OWNER
        }
        if set(conflict) == {row["case_id"] for row in source} and owned == set(conflict):
            print(json.dumps({"status": "ALREADY_REGISTERED", "count": len(conflict)}, ensure_ascii=False))
            return
        raise SystemExit(f"HARD_STOP ledger segment_id collision: {conflict[:5]}")

    additions = []
    for row in source:
        additions.append({
            "record_type": "material_selection",
            "owner_thread_id": OWNER,
            "material_class": "NORMAL_NEW",
            "segment_id": row["case_id"],
            "book_title": row["book_title"],
            "author": row["author"],
            "platform": row["platform"],
            "chapter_pointer": row["chapter_pointer"],
            "chapter_sha256": row["chapter_sha256"],
            "segment_char_start": row["target_char_start"],
            "segment_char_end": row["target_char_end"],
            "segment_sha256": row["target_text_sha256"],
            "story_stage": row["story_stage"],
            "selection_status": "PROPOSED",
            "rights_state": row["rights_state"],
            "semantic_review": "PENDING_DEV_CORE_GOLD",
            "candidate_revision": "DEV_CORE_R01",
            "usage_scope": "INTERNAL_DEV_EVALUATION_ONLY",
        })

    payload = "".join(canon(row) + "\n" for row in current + additions)
    LEDGER.write_text(payload, encoding="utf-8")
    print(json.dumps({"status": "REGISTERED", "count": len(additions)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

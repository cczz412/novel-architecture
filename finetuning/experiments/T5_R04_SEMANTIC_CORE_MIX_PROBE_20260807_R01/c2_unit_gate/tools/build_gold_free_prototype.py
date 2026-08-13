#!/usr/bin/env python3
"""Select 40 deterministic prototype questions and strip all answer content."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from c2_unit_common import canonical_json, parse_question, sha256_text


def read_rows(path: Path, source_class: str) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            record = json.loads(line)
            messages = record.get("messages")
            if not isinstance(messages, list) or [m.get("role") for m in messages] != ["system", "user", "assistant"]:
                raise ValueError(f"unexpected message roles at {path}:{line_number}")
            question = parse_question(messages[0]["content"], messages[1]["content"])
            rows.append({
                "source_class": source_class,
                "source_path": str(path),
                "source_line_number": line_number,
                "question": question,
            })
    return rows


def select_quantile_unique(rows: list[dict], count: int, seed: str) -> list[dict]:
    by_sample: dict[str, list[dict]] = {}
    for row in rows:
        by_sample.setdefault(row["question"]["source_sample_id"], []).append(row)
    candidates = []
    for source_sample_id, group in by_sample.items():
        chosen = min(
            group,
            key=lambda row: hashlib.sha256(
                f"{seed}|{source_sample_id}|{row['question']['canonical_sample_id']}".encode()
            ).hexdigest(),
        )
        candidates.append(chosen)
    candidates.sort(key=lambda row: (len(row["question"]["target_text"]), row["question"]["canonical_sample_id"]))
    if len(candidates) < count:
        raise ValueError(f"need {count} unique source samples, only {len(candidates)} available")
    positions = [round(i * (len(candidates) - 1) / (count - 1)) for i in range(count)] if count > 1 else [0]
    selected = [candidates[pos] for pos in positions]
    if len({row["question"]["canonical_sample_id"] for row in selected}) != count:
        raise ValueError("quantile selection produced duplicates")
    return selected


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--positive-count", type=int, default=30)
    parser.add_argument("--special-count", type=int, default=10)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    positive_path = args.lab_root / "runtime_data/a_stage1_positive/train.jsonl"
    special_path = args.lab_root / "runtime_data/a_stage2_special/train.jsonl"
    exam_path = args.lab_root / "sealed/exams/a/QUESTIONS.jsonl"
    positive = read_rows(positive_path, "positive")
    special = read_rows(special_path, "special")
    selected = select_quantile_unique(positive, args.positive_count, "C2_UNIT_POSITIVE_R01")
    selected += select_quantile_unique(special, args.special_count, "C2_UNIT_SPECIAL_R01")

    old_exam_segments = set()
    with exam_path.open(encoding="utf-8") as handle:
        for line in handle:
            old_exam_segments.add(json.loads(line)["segment_id"])
    overlap = sorted({row["question"]["segment_id"] for row in selected} & old_exam_segments)
    if overlap:
        raise ValueError(f"prototype overlaps old frozen exam segments: {overlap}")

    questions = []
    bindings = []
    for order, row in enumerate(selected, 1):
        question = dict(row["question"])
        question["prototype_order"] = order
        question["source_class"] = row["source_class"]
        questions.append(question)
        bindings.append({
            "canonical_sample_id": question["canonical_sample_id"],
            "source_class": row["source_class"],
            "source_path": row["source_path"],
            "source_line_number": row["source_line_number"],
            "source_file_sha256": sha256_file(Path(row["source_path"])),
            "question_sha256": sha256_text(canonical_json(question)),
        })

    questions_path = args.out_dir / "PROTOTYPE_QUESTIONS_GOLD_FREE.jsonl"
    bindings_path = args.out_dir / "SOURCE_BINDINGS.jsonl"
    write_jsonl(questions_path, questions)
    write_jsonl(bindings_path, bindings)
    lock = {
        "schema_version": "t5-r04-c2-unit-prototype-lock-v1",
        "status": "LOCKED_GOLD_FREE_INPUT",
        "counts": {
            "total": len(questions),
            "positive": args.positive_count,
            "special": args.special_count,
            "unique_canonical_sample_ids": len({q["canonical_sample_id"] for q in questions}),
            "unique_source_sample_ids": len({q["source_sample_id"] for q in questions}),
            "old_frozen_exam_overlap": len(overlap),
        },
        "selection_rule": "one deterministic row per source_sample_id, then target-length quantile coverage",
        "selection_did_not_use_assistant": True,
        "atomizer_input_contains_assistant": False,
        "rights_scope": "INTERNAL_TRAINING_AND_EVALUATION_ONLY_INHERITED_FROM_SEALED_AC_CONTRACT",
        "artifacts": {
            "questions": {"path": questions_path.name, "sha256": sha256_file(questions_path)},
            "bindings": {"path": bindings_path.name, "sha256": sha256_file(bindings_path)},
            "source_a_positive": {"path": str(positive_path), "sha256": sha256_file(positive_path)},
            "source_a_special": {"path": str(special_path), "sha256": sha256_file(special_path)},
            "old_frozen_exam_questions": {"path": str(exam_path), "sha256": sha256_file(exam_path)},
        },
    }
    (args.out_dir / "PROTOTYPE_LOCK.json").write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

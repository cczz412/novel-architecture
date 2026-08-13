#!/usr/bin/env python3
"""Build C2 unit maps and rendered questions from a gold-free input only."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from c2_unit_common import atomize_question, canonical_json, render_c2_user


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
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-chars", type=int, default=80)
    parser.add_argument("--min-visible", type=int, default=8)
    parser.add_argument("--visible-bridge-units", type=int, default=3)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    questions = [json.loads(line) for line in args.questions.read_text(encoding="utf-8").splitlines()]
    if any("assistant" in canonical_json(question) for question in questions):
        raise ValueError("gold-free atomizer input contains an assistant key or value")

    maps = []
    rendered = []
    for question in questions:
        unit_map = atomize_question(
            question,
            max_chars=args.max_chars,
            min_visible=args.min_visible,
            visible_bridge_units=args.visible_bridge_units,
        )
        maps.append(unit_map)
        rendered.append({
            "schema_version": "t5-r04-c2-unit-rendered-question-v1",
            "canonical_sample_id": question["canonical_sample_id"],
            "messages": [
                {"role": "system", "content": question["system_text"]},
                {"role": "user", "content": render_c2_user(question, unit_map)},
            ],
        })

    maps_path = args.out_dir / "SOURCE_UNITS.jsonl"
    questions_path = args.out_dir / "C2_QUESTIONS.jsonl"
    write_jsonl(maps_path, maps)
    write_jsonl(questions_path, rendered)
    receipt = {
        "schema_version": "t5-r04-c2-unit-atomizer-receipt-v1",
        "status": "ATOMIZER_RENDERER_COMPLETE_PENDING_GOLD_AUDIT",
        "gold_read": False,
        "input": {"path": str(args.questions), "sha256": sha256_file(args.questions), "rows": len(questions)},
        "config": {
            "max_chars": args.max_chars,
            "min_visible_chars_for_tiny_merge": args.min_visible,
            "visible_bridge_units": args.visible_bridge_units,
            "split_order": ["natural_newline_or_strong_punctuation", "weak_punctuation", "hard_unicode_limit"],
        },
        "outputs": {
            "source_units": {"path": maps_path.name, "sha256": sha256_file(maps_path), "rows": len(maps)},
            "c2_questions": {"path": questions_path.name, "sha256": sha256_file(questions_path), "rows": len(rendered)},
        },
    }
    (args.out_dir / "ATOMIZER_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

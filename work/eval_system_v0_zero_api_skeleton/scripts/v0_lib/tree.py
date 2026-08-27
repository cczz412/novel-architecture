from __future__ import annotations

from pathlib import Path

REQUIRED_DIRS = (
    "common/versions",
    "common/runs",
    "common/artifacts",
    "common/assessments",
    "common/reviews",
    "evidence_gate",
    "exam",
    "api_eval",
    "schemas",
    "fixtures/synthetic",
    "reports",
    "scripts",
)

EMPTY_JSONL = (
    "common/versions/versions.jsonl",
    "common/runs/runs.jsonl",
    "common/artifacts/artifacts.jsonl",
    "common/assessments/assessments.jsonl",
    "common/reviews/reviews.jsonl",
    "evidence_gate/attempts.jsonl",
    "evidence_gate/comparisons.jsonl",
    "evidence_gate/mechanical.jsonl",
    "exam/items.jsonl",
    "exam/splits.jsonl",
    "exam/exposures.jsonl",
    "api_eval/cases.jsonl",
)


def tree_error(root: Path) -> str | None:
    for rel in REQUIRED_DIRS:
        path = root / rel
        if not path.is_dir():
            return f"MISSING_DIR:{rel}"
    for rel in EMPTY_JSONL:
        path = root / rel
        if not path.is_file():
            return f"MISSING_EMPTY_JSONL:{rel}"
        text = path.read_text(encoding="utf-8")
        if text.strip():
            return f"JSONL_NOT_EMPTY:{rel}"
    return None

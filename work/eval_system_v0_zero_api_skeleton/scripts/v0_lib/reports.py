from __future__ import annotations

from typing import Any

OVERALL_SCORE_KEYS = {"overall_score", "total_score", "总分", "macro_f1"}

ATTEMPT_COLUMNS = (
    "run_id",
    "attempt_id",
    "raw_sha256",
    "transport_ok",
    "parse_ok",
    "schema_ok",
    "failure_stage",
    "failure_code",
    "verdict",
    "reason_code",
)
PAIR_COLUMNS = (
    "comparison_id",
    "j1_ref",
    "j2_ref",
    "comparison_state",
    "semantic_result",
    "shared_deviation",
    "frozen_direction_version",
    "eligibility",
    "reason_code",
)
EXAM_COLUMNS = (
    "item_id",
    "item_version",
    "task_kind",
    "split",
    "leakage_group_uid",
    "exposure_kind",
    "reference_status",
    "unreviewed",
)
API_COLUMNS = (
    "case_id",
    "case_version",
    "mechanical_column",
    "semantic_main_column",
    "auxiliary_column",
    "experiment_factors",
    "comparable",
    "unreviewed",
)


def _has_overall_score(row: dict[str, Any]) -> bool:
    return any(key in row for key in OVERALL_SCORE_KEYS)


def build_reports(pack: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    attempts = []
    for row in pack.get("attempts") or []:
        attempts.append({key: row.get(key) for key in ATTEMPT_COLUMNS})
    pairs = []
    for row in pack.get("pairs") or []:
        pairs.append({key: row.get(key) for key in PAIR_COLUMNS})
    short_rows: list[dict[str, Any]] = []
    full_rows: list[dict[str, Any]] = []
    for row in pack.get("exam") or []:
        projected = {key: row.get(key) for key in EXAM_COLUMNS}
        kind = row.get("task_kind")
        if kind == "SHORT_DIAGNOSIS":
            short_rows.append(projected)
        elif kind == "FULL_CHAPTER":
            full_rows.append(projected)
    api_rows = []
    for row in pack.get("api_cases") or []:
        api_rows.append({key: row.get(key) for key in API_COLUMNS})
    return {
        "evidence_gate_attempt_mechanical": attempts,
        "evidence_gate_pair_comparison": pairs,
        "exam_short_diagnosis": short_rows,
        "exam_full_chapter": full_rows,
        "api_eval_three_columns": api_rows,
    }


def reports_error(tables: dict[str, list[dict[str, Any]]]) -> str | None:
    required = {
        "evidence_gate_attempt_mechanical": ATTEMPT_COLUMNS,
        "evidence_gate_pair_comparison": PAIR_COLUMNS,
        "exam_short_diagnosis": EXAM_COLUMNS,
        "exam_full_chapter": EXAM_COLUMNS,
        "api_eval_three_columns": API_COLUMNS,
    }
    if "exam_split_exposure_unreviewed" in tables:
        return "MIXED_EXAM_REPORT_FORBIDDEN"
    if set(tables) != set(required):
        return f"REPORT_TABLES_MISMATCH:{sorted(tables)}"
    for name, columns in required.items():
        rows = tables[name]
        if not rows:
            return f"REPORT_EMPTY:{name}"
        for row in rows:
            if _has_overall_score(row):
                return f"OVERALL_SCORE_FORBIDDEN:{name}"
            missing = [col for col in columns if col not in row]
            if missing:
                return f"REPORT_MISSING_COLUMNS:{name}:{missing}"
    if any(row.get("task_kind") != "SHORT_DIAGNOSIS" for row in tables["exam_short_diagnosis"]):
        return "SHORT_REPORT_MUST_NOT_MIX_FULL_CHAPTER"
    if any(row.get("task_kind") != "FULL_CHAPTER" for row in tables["exam_full_chapter"]):
        return "FULL_REPORT_MUST_NOT_MIX_SHORT_DIAGNOSIS"
    for row in tables["api_eval_three_columns"]:
        if row.get("mechanical_column") == "FAIL" and row.get("semantic_main_column") not in {
            "NOT_EVALUATED",
            None,
        }:
            return "API_MECHANICAL_FAIL_MUST_SHOW_NOT_EVALUATED"
        if row.get("unreviewed") is True and row.get("semantic_main_column") == "FAIL":
            return "UNREVIEWED_MUST_BE_OWN_COLUMN_NOT_FAIL"
    return None


def to_markdown(title: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"# {title}\n\n(empty)\n"
    columns = list(rows[0])
    lines = [f"# {title}", "", "| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_cell(row.get(col)) for col in columns) + " |")
    lines.append("")
    return "\n".join(lines)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("|", "/")
    return text

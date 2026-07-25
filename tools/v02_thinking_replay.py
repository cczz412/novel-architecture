#!/usr/bin/env python3
"""Replay twelve historical thinking traces against the frozen B2 gate contract.

This tool is deliberately offline.  It freezes every input byte and records the
input lock before decoding or judging the thinking traces.  Producer self-checks
remain diagnostic evidence and can never become a program-green ticket here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from tools import v02_gate_contracts as gates
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    import v02_gate_contracts as gates


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B3_thinking_replay"
)
DEFAULT_FIXTURE_DIR = DEFAULT_BUNDLE_DIR / "fixtures"
DEFAULT_B2_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B2_gate_contract_v0.1"
)
DEFAULT_SOURCE_TABLE = (
    REPO_ROOT
    / "experiments"
    / "Z99_external_finalization_supply_20260724"
    / "supply_tables"
    / "table_a_thinking_inputs.json"
)
DEFAULT_SHARED_DIR = (
    REPO_ROOT
    / "TEMP"
    / "extract_chain_consult_3win_20260724"
    / "00_shared"
    / "F_thinking_12"
)
DEFAULT_DIGEST = (
    REPO_ROOT
    / "TEMP"
    / "extract_chain_consult_3win_20260724"
    / "00_shared"
    / "H_failure_and_selfscore_DIGEST.md"
)

FIXTURE_NAMES = (
    "path_resolution_error.json",
    "snapshot_count_drift.json",
    "producer_five_layer_full_score.json",
    "sop_ucr_divergence.json",
)

FINDING_DEFINITIONS: dict[str, dict[str, str]] = {
    "B3_PATH_RESOLUTION_ERROR": {
        "b2_failure_code": "S6_FIVE_LAYER_RECOMPUTE_FAILED",
        "meaning": "历史执行中出现未解析路径，不能把该轮当成独立五层重算。",
    },
    "B3_SNAPSHOT_COUNT_DRIFT": {
        "b2_failure_code": "S6_SNAPSHOT_COUNT_MISMATCH",
        "meaning": "同一思考稿出现互不相等的计分总数快照。",
    },
    "B3_PRODUCER_FIVE_LAYER_FULL_SCORE": {
        "b2_failure_code": "R_PRODUCER_SELF_CHECK_AS_PROGRAM_GREEN",
        "meaning": "生产者自报五层满分只能作诊断，不能直接充当程序绿票。",
    },
    "B3_SOP_UCR_DIVERGENCE_NOT_GREEN": {
        "b2_failure_code": "R_PRODUCER_SELF_CHECK_AS_PROGRAM_GREEN",
        "meaning": "表面通过率不能替代可用率，更不能单独触发放行。",
    },
}

BASE_B2_FAILURE_CODES = (
    "R_PROGRAM_GREEN_MISSING",
    "R_JUDGE_GREEN_MISSING",
    "R_ENGINEERING_GREEN_MISSING",
    "R_HASH_UNLOCKED",
    "R_BUDGET_NOT_OK",
)

METRIC_NAMES: tuple[tuple[str, str], ...] = (
    ("FCR", "fcr"),
    ("QCR_full", "qcr_full"),
    ("ASR_full", "asr_full"),
    ("UCR", "ucr"),
    ("SOP", "sop"),
)


class ReplayValidationError(ValueError):
    """Raised when an input lock, fixture, or replay bundle is inconsistent."""


@dataclass(frozen=True)
class FrozenSource:
    """One canonical thinking source plus its shared review copy."""

    thinking_id: str
    table_row: Mapping[str, Any]
    source_path: str
    source_bytes: bytes
    shared_copy_path: str
    shared_copy_bytes: bytes
    shared_copy_relation: str


@dataclass(frozen=True)
class FrozenInputs:
    """All bytes needed for a replay, captured before trace analysis."""

    source_table_path: str
    source_table_bytes: bytes
    digest_path: str
    digest_bytes: bytes
    b2_manifest_path: str
    b2_manifest_bytes: bytes
    b2_contract_hash: str
    b2_check: Mapping[str, Any]
    sources: tuple[FrozenSource, ...]
    fixture_bytes: Mapping[str, bytes]
    input_lock: Mapping[str, Any]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ReplayValidationError(f"path is outside repository: {path}") from exc


def _read_required(path: Path) -> bytes:
    if not path.is_file():
        raise ReplayValidationError(f"required file is missing: {path}")
    return path.read_bytes()


def _source_order(row: Mapping[str, Any]) -> int:
    batch_order = {"UCR": 0, "blind": 1}
    batch = row.get("source_batch_code")
    if batch not in batch_order:
        raise ReplayValidationError(f"unknown source batch code: {batch!r}")
    try:
        slot = int(row["slot"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ReplayValidationError(f"invalid source slot: {row.get('slot')!r}") from exc
    return (slot - 1) * 2 + batch_order[batch] + 1


def _shared_copy_relation(source: bytes, shared: bytes) -> str:
    if source == shared:
        return "BYTE_IDENTICAL"
    if shared == source + b"\n" or source == shared + b"\n":
        return "TRAILING_LF_ONLY"
    raise ReplayValidationError(
        "shared thinking copy differs from the machine-table source beyond one "
        "trailing LF"
    )


def _validate_b2_codes() -> dict[str, str]:
    route_by_code = {
        fine_code: route
        for fine_code, _stage, route, _meaning in gates.FINE_CODE_ROWS
    }
    required = {
        *BASE_B2_FAILURE_CODES,
        *(row["b2_failure_code"] for row in FINDING_DEFINITIONS.values()),
    }
    missing = sorted(required - set(route_by_code))
    if missing:
        raise ReplayValidationError(
            f"B3 requested codes absent from frozen B2 contract: {missing}"
        )
    return route_by_code


def freeze_inputs(
    *,
    source_table_path: Path = DEFAULT_SOURCE_TABLE,
    shared_dir: Path = DEFAULT_SHARED_DIR,
    digest_path: Path = DEFAULT_DIGEST,
    fixture_dir: Path = DEFAULT_FIXTURE_DIR,
    b2_dir: Path = DEFAULT_B2_DIR,
) -> FrozenInputs:
    """Capture and hash every input before any thinking-trace analysis."""

    route_by_code = _validate_b2_codes()
    b2_check = gates.check_bundle(b2_dir)
    b2_manifest_path = b2_dir / "manifest.json"
    b2_manifest_bytes = _read_required(b2_manifest_path)
    b2_manifest = json.loads(b2_manifest_bytes)
    if b2_manifest["contract_hash"] != b2_check["contract_hash"]:
        raise ReplayValidationError("B2 manifest and validated contract hash differ")
    if b2_manifest["candidate_status"] != "candidate_silver_not_active":
        raise ReplayValidationError("B2 candidate isolation changed")
    if b2_manifest["producer_selfcheck_authority"] != (
        "DIAGNOSTIC_ONLY_NOT_GREEN_TICKET"
    ):
        raise ReplayValidationError("B2 producer-selfcheck authority changed")

    source_table_bytes = _read_required(source_table_path)
    source_table = json.loads(source_table_bytes)
    if source_table.get("schema_version") != "z99-thinking-supply-table-a-v1":
        raise ReplayValidationError("unexpected source-table schema")
    rows = source_table.get("rows")
    if not isinstance(rows, list) or len(rows) != 12:
        raise ReplayValidationError("source table must contain exactly twelve rows")
    ordered_rows = sorted(rows, key=_source_order)
    if [_source_order(row) for row in ordered_rows] != list(range(1, 13)):
        raise ReplayValidationError("source table does not map one-to-one to T01-T12")

    sources: list[FrozenSource] = []
    source_lock_rows: list[dict[str, Any]] = []
    for index, row in enumerate(ordered_rows, 1):
        thinking_id = f"T{index:02d}"
        raw_source_path = row.get("file_path")
        if not isinstance(raw_source_path, str):
            raise ReplayValidationError(f"{thinking_id}: source path is not a string")
        source_path = REPO_ROOT / raw_source_path
        source_bytes = _read_required(source_path)
        observed_sha = _sha256(source_bytes)
        if observed_sha != row.get("sha256"):
            raise ReplayValidationError(
                f"{thinking_id}: machine-table source SHA mismatch"
            )
        if len(source_bytes) != row.get("bytes"):
            raise ReplayValidationError(
                f"{thinking_id}: machine-table source byte count mismatch"
            )
        shared_candidates = sorted(shared_dir.glob(f"{index:02d}_*.md"))
        if len(shared_candidates) != 1:
            raise ReplayValidationError(
                f"{thinking_id}: expected one shared copy, got {len(shared_candidates)}"
            )
        shared_path = shared_candidates[0]
        shared_bytes = _read_required(shared_path)
        relation = _shared_copy_relation(source_bytes, shared_bytes)

        frozen_source = FrozenSource(
            thinking_id=thinking_id,
            table_row=dict(row),
            source_path=_repo_relative(source_path),
            source_bytes=source_bytes,
            shared_copy_path=_repo_relative(shared_path),
            shared_copy_bytes=shared_bytes,
            shared_copy_relation=relation,
        )
        sources.append(frozen_source)
        source_lock_rows.append(
            {
                "thinking_id": thinking_id,
                "source_batch_code": row["source_batch_code"],
                "slot": row["slot"],
                "window": row["window"],
                "book": row["book"],
                "bibliographic_unit": row["bibliographic_unit"],
                "canonical_source_path": frozen_source.source_path,
                "canonical_source_bytes": len(source_bytes),
                "canonical_source_sha256": observed_sha,
                "registered_unicode_char_count": row["unicode_char_count"],
                "shared_copy_path": frozen_source.shared_copy_path,
                "shared_copy_bytes": len(shared_bytes),
                "shared_copy_sha256": _sha256(shared_bytes),
                "shared_copy_relation": relation,
            }
        )

    digest_bytes = _read_required(digest_path)
    fixture_bytes = {
        name: _read_required(fixture_dir / name) for name in FIXTURE_NAMES
    }
    fixture_lock_rows = [
        {
            "path": f"fixtures/{name}",
            "bytes": len(data),
            "sha256": _sha256(data),
        }
        for name, data in sorted(fixture_bytes.items())
    ]
    freeze_inventory = {
        "source_table": {
            "path": _repo_relative(source_table_path),
            "bytes": len(source_table_bytes),
            "sha256": _sha256(source_table_bytes),
        },
        "digest": {
            "path": _repo_relative(digest_path),
            "bytes": len(digest_bytes),
            "sha256": _sha256(digest_bytes),
        },
        "b2_manifest": {
            "path": _repo_relative(b2_manifest_path),
            "bytes": len(b2_manifest_bytes),
            "sha256": _sha256(b2_manifest_bytes),
            "contract_hash": b2_manifest["contract_hash"],
        },
        "sources": source_lock_rows,
        "fixtures": fixture_lock_rows,
    }
    input_lock = {
        "schema_version": "v02-b3-thinking-input-lock-v0.1",
        "candidate_id": "B3_thinking_replay",
        "freeze_before_trace_decode": True,
        "source_authority": (
            "table_a_thinking_inputs.json 登记原件是判定真源；共享副本只作复核。"
        ),
        "shared_copy_equivalence_policy": [
            "BYTE_IDENTICAL",
            "TRAILING_LF_ONLY",
        ],
        "inventory": freeze_inventory,
        "freeze_content_sha256": _sha256(_canonical_bytes(freeze_inventory)),
        "b2_route_by_required_code": {
            code: route_by_code[code] for code in sorted(route_by_code) if code in {
                *BASE_B2_FAILURE_CODES,
                *(row["b2_failure_code"] for row in FINDING_DEFINITIONS.values()),
            }
        },
        "model_api_calls": 0,
        "network_requests": 0,
    }
    # The bytes and their lock are complete at this point.  Only now decode the
    # traces for the last machine-table integrity check; semantic analysis runs
    # later in build_artifacts_from_frozen().
    for source in sources:
        try:
            unicode_count = len(source.source_bytes.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ReplayValidationError(
                f"{source.thinking_id}: source is not UTF-8"
            ) from exc
        if unicode_count != source.table_row.get("unicode_char_count"):
            raise ReplayValidationError(
                f"{source.thinking_id}: machine-table Unicode count mismatch"
            )
    return FrozenInputs(
        source_table_path=_repo_relative(source_table_path),
        source_table_bytes=source_table_bytes,
        digest_path=_repo_relative(digest_path),
        digest_bytes=digest_bytes,
        b2_manifest_path=_repo_relative(b2_manifest_path),
        b2_manifest_bytes=b2_manifest_bytes,
        b2_contract_hash=b2_manifest["contract_hash"],
        b2_check=dict(b2_check),
        sources=tuple(sources),
        fixture_bytes=fixture_bytes,
        input_lock=input_lock,
    )


def _evidence(line_number: int, line: str) -> dict[str, Any]:
    return {
        "line_start": line_number,
        "line_end": line_number,
        "quote": line.strip(),
    }


def _path_errors(lines: Sequence[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    path_pattern = re.compile(
        r"FileNotFoundError:.*No such file or directory:\s*['\"]([^'\"]+)['\"]"
    )
    for line_number, line in enumerate(lines, 1):
        match = path_pattern.search(line)
        if match:
            results.append(
                {
                    **_evidence(line_number, line),
                    "missing_path": match.group(1),
                }
            )
    return results


def _snapshot_observations(lines: Sequence[str]) -> list[dict[str, Any]]:
    patterns = (
        ("part_counter_assert", re.compile(r"\bassert\s+part_counter\s*==\s*(\d+)")),
        ("total_output", re.compile(r"^\s*total\s+(\d+)\s*$")),
        (
            "scoreable_part_total",
            re.compile(r"['\"]scoreable_part_total['\"]\s*:\s*(\d+)"),
        ),
    )
    observed: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for line_number, line in enumerate(lines, 1):
        for label, pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            count = int(match.group(1))
            key = (label, line_number, count)
            if key in seen:
                continue
            seen.add(key)
            observed.append(
                {
                    **_evidence(line_number, line),
                    "observation_kind": label,
                    "count": count,
                }
            )
    return observed


def _metric_observations(lines: Sequence[str]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int, float]] = set()

    def add(
        metric: str,
        value: float,
        line_start: int,
        line_end: int,
        quote: str,
    ) -> None:
        key = (metric, line_start, line_end, value)
        if key in seen:
            return
        seen.add(key)
        observations.append(
            {
                "metric": metric,
                "value": value,
                "line_start": line_start,
                "line_end": line_end,
                "quote": quote.strip(),
            }
        )

    number = r"([01](?:\.\d+)?)"
    for line_number, line in enumerate(lines, 1):
        for display_name, metric in METRIC_NAMES:
            escaped = re.escape(display_name)
            rate_match = re.search(
                rf"['\"]?{escaped}['\"]?\s*:\s*\{{[^\n]*?"
                rf"['\"]?rate['\"]?\s*:\s*{number}",
                line,
            )
            if rate_match:
                add(metric, float(rate_match.group(1)), line_number, line_number, line)

            tuple_match = re.search(
                rf"['\"]?{escaped}['\"]?\s*:\s*\(([^)]*)\)",
                line,
            )
            if tuple_match:
                tuple_numbers = re.findall(r"[0-9]+(?:\.[0-9]+)?", tuple_match.group(1))
                if tuple_numbers:
                    add(
                        metric,
                        float(tuple_numbers[-1]),
                        line_number,
                        line_number,
                        line,
                    )

            plain_match = re.search(
                rf"['\"]?{escaped}['\"]?\s*:\s*{number}",
                line,
            )
            if plain_match:
                add(metric, float(plain_match.group(1)), line_number, line_number, line)

            if "|" in line:
                cells = [cell.strip() for cell in line.split("|")[1:-1]]
                if cells and cells[0] == display_name:
                    numeric = [
                        cell
                        for cell in cells[1:]
                        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", cell)
                    ]
                    if numeric:
                        add(
                            metric,
                            float(numeric[-1]),
                            line_number,
                            line_number,
                            line,
                        )

            key_pattern = re.compile(rf"['\"]?{escaped}['\"]?\s*:\s*\{{\s*$")
            if key_pattern.search(line):
                block_end = min(len(lines), line_number + 8)
                block = "\n".join(lines[line_number - 1 : block_end])
                block_rate = re.search(
                    rf"['\"]?rate['\"]?\s*:\s*{number}",
                    block,
                )
                if block_rate:
                    relative_end = block[: block_rate.end()].count("\n")
                    end_line = line_number + relative_end
                    quote = "\n".join(lines[line_number - 1 : end_line])
                    add(
                        metric,
                        float(block_rate.group(1)),
                        line_number,
                        end_line,
                        quote,
                    )
    return sorted(
        observations,
        key=lambda row: (row["line_start"], row["line_end"], row["metric"]),
    )


def _full_score_groups(
    observations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    one_observations = [
        row for row in observations if abs(float(row["value"]) - 1.0) < 1e-12
    ]
    groups: list[dict[str, Any]] = []
    seen_spans: set[tuple[int, int]] = set()
    for anchor in one_observations:
        start = int(anchor["line_start"])
        window = [
            row
            for row in one_observations
            if start <= int(row["line_start"]) <= start + 30
        ]
        chosen: dict[str, Mapping[str, Any]] = {}
        for row in window:
            chosen.setdefault(str(row["metric"]), row)
        required = {metric for _display, metric in METRIC_NAMES}
        if set(chosen) != required:
            continue
        end = max(int(row["line_end"]) for row in chosen.values())
        span = (start, end)
        if span in seen_spans:
            continue
        seen_spans.add(span)
        evidence_rows = sorted(
            chosen.values(),
            key=lambda row: (int(row["line_start"]), str(row["metric"])),
        )
        groups.append(
            {
                "line_start": start,
                "line_end": end,
                "metrics": {
                    metric: float(chosen[metric]["value"])
                    for _display, metric in METRIC_NAMES
                },
                "evidence": [dict(row) for row in evidence_rows],
            }
        )
    return groups


def _sop_ucr_divergences(
    observations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ucr_rows = [
        row
        for row in observations
        if row["metric"] == "ucr" and abs(float(row["value"]) - 0.0625) < 1e-12
    ]
    sop_rows = [
        row
        for row in observations
        if row["metric"] == "sop" and abs(float(row["value"]) - 1.0) < 1e-12
    ]
    groups: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for ucr in ucr_rows:
        for sop in sop_rows:
            if abs(int(ucr["line_start"]) - int(sop["line_start"])) > 12:
                continue
            span = (
                min(int(ucr["line_start"]), int(sop["line_start"])),
                max(int(ucr["line_end"]), int(sop["line_end"])),
            )
            if span in seen:
                continue
            seen.add(span)
            groups.append(
                {
                    "line_start": span[0],
                    "line_end": span[1],
                    "ucr": float(ucr["value"]),
                    "sop": float(sop["value"]),
                    "evidence": [dict(ucr), dict(sop)],
                }
            )
    return groups


def analyze_text(text: str) -> dict[str, Any]:
    """Run the four bounded detectors over already-frozen text."""

    lines = text.splitlines()
    path_errors = _path_errors(lines)
    snapshot_observations = _snapshot_observations(lines)
    metric_observations = _metric_observations(lines)
    full_score_groups = _full_score_groups(metric_observations)
    divergences = _sop_ucr_divergences(metric_observations)

    route_by_code = _validate_b2_codes()
    findings: list[dict[str, Any]] = []

    def append_finding(
        finding_code: str,
        details: Mapping[str, Any],
        evidence_rows: Sequence[Mapping[str, Any]],
    ) -> None:
        definition = FINDING_DEFINITIONS[finding_code]
        b2_code = definition["b2_failure_code"]
        findings.append(
            {
                "finding_code": finding_code,
                "b2_failure_code": b2_code,
                "b2_route": route_by_code[b2_code],
                "meaning": definition["meaning"],
                "details": dict(details),
                "evidence": [dict(row) for row in evidence_rows],
            }
        )

    if path_errors:
        append_finding(
            "B3_PATH_RESOLUTION_ERROR",
            {
                "path_error_count": len(path_errors),
                "missing_paths": [row["missing_path"] for row in path_errors],
            },
            path_errors,
        )

    unique_counts = sorted({row["count"] for row in snapshot_observations})
    if len(unique_counts) >= 2:
        append_finding(
            "B3_SNAPSHOT_COUNT_DRIFT",
            {"observed_counts": unique_counts},
            snapshot_observations,
        )

    if full_score_groups:
        append_finding(
            "B3_PRODUCER_FIVE_LAYER_FULL_SCORE",
            {
                "full_score_group_count": len(full_score_groups),
                "metrics": full_score_groups[0]["metrics"],
            },
            full_score_groups[0]["evidence"],
        )

    if divergences:
        append_finding(
            "B3_SOP_UCR_DIVERGENCE_NOT_GREEN",
            {
                "divergence_group_count": len(divergences),
                "sop": divergences[0]["sop"],
                "ucr": divergences[0]["ucr"],
            },
            divergences[0]["evidence"],
        )

    return {
        "detectors": {
            "path_resolution_errors": path_errors,
            "snapshot_count_observations": snapshot_observations,
            "metric_observations": metric_observations,
            "producer_five_layer_full_score_groups": full_score_groups,
            "sop_ucr_divergence_groups": divergences,
        },
        "findings": findings,
    }


def _add_source_path(
    finding: Mapping[str, Any],
    source_path: str,
) -> dict[str, Any]:
    copied = json.loads(json.dumps(finding, ensure_ascii=False))
    for row in copied["evidence"]:
        row["source_path"] = source_path
    return copied


def _build_replay_result(
    source: FrozenSource,
    *,
    b2_contract_hash: str,
) -> dict[str, Any]:
    analysis = analyze_text(source.source_bytes.decode("utf-8"))
    findings = [
        _add_source_path(finding, source.source_path)
        for finding in analysis["findings"]
    ]
    local_b2_codes = [
        finding["b2_failure_code"]
        for finding in findings
        if finding["b2_failure_code"] not in BASE_B2_FAILURE_CODES
    ]
    b2_failure_codes = list(dict.fromkeys([*BASE_B2_FAILURE_CODES, *local_b2_codes]))
    detector_counts = {
        "path_resolution_errors": len(
            analysis["detectors"]["path_resolution_errors"]
        ),
        "snapshot_count_observations": len(
            analysis["detectors"]["snapshot_count_observations"]
        ),
        "producer_five_layer_full_score_groups": len(
            analysis["detectors"]["producer_five_layer_full_score_groups"]
        ),
        "sop_ucr_divergence_groups": len(
            analysis["detectors"]["sop_ucr_divergence_groups"]
        ),
    }
    return {
        "schema_version": "v02-b3-thinking-replay-result-v0.1",
        "candidate_id": "B3_thinking_replay",
        "thinking_id": source.thinking_id,
        "source_identity": {
            "source_batch_code": source.table_row["source_batch_code"],
            "slot": source.table_row["slot"],
            "window": source.table_row["window"],
            "book": source.table_row["book"],
            "bibliographic_unit": source.table_row["bibliographic_unit"],
            "canonical_source_path": source.source_path,
            "canonical_source_sha256": _sha256(source.source_bytes),
            "shared_copy_path": source.shared_copy_path,
            "shared_copy_sha256": _sha256(source.shared_copy_bytes),
            "shared_copy_relation": source.shared_copy_relation,
        },
        "freeze_verified_before_analysis": True,
        "analysis_boundary": (
            "只做冻结全文中的四类机械症状定位；不把历史思考稿改判为正式质量分。"
        ),
        "b2_contract_hash": b2_contract_hash,
        "producer_selfcheck_authority": "DIAGNOSTIC_ONLY_NOT_GREEN_TICKET",
        "detector_counts": detector_counts,
        "findings": findings,
        "base_b2_failure_codes": list(BASE_B2_FAILURE_CODES),
        "b2_failure_codes": b2_failure_codes,
        "status": "HARD_STOP",
        "activation_allowed": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _locked_texts(frozen: FrozenInputs) -> dict[str, tuple[str, bytes]]:
    locked = {
        source.source_path: (source.thinking_id, source.source_bytes)
        for source in frozen.sources
    }
    locked[frozen.digest_path] = ("DIGEST", frozen.digest_bytes)
    return locked


def _validate_lineage_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    frozen: FrozenInputs,
    replay_text: str | None,
) -> list[dict[str, Any]]:
    locked = _locked_texts(frozen)
    verified: list[dict[str, Any]] = []
    replay_lines = {line.strip() for line in (replay_text or "").splitlines()}
    for row in rows:
        source_path = row.get("source_path")
        if source_path not in locked:
            raise ReplayValidationError(
                f"fixture lineage path is not frozen: {source_path!r}"
            )
        expected_thinking_id, data = locked[source_path]
        thinking_id = row.get("thinking_id", expected_thinking_id)
        if thinking_id != expected_thinking_id:
            raise ReplayValidationError(
                f"fixture lineage thinking ID mismatch for {source_path}"
            )
        line_start = row.get("line_start")
        line_end = row.get("line_end")
        if (
            not isinstance(line_start, int)
            or not isinstance(line_end, int)
            or line_start < 1
            or line_end < line_start
        ):
            raise ReplayValidationError("fixture lineage has invalid line range")
        source_lines = data.decode("utf-8").splitlines()
        if line_end > len(source_lines):
            raise ReplayValidationError(
                f"fixture lineage line range exceeds {source_path}"
            )
        actual = "\n".join(source_lines[line_start - 1 : line_end]).strip()
        quote = row.get("quote")
        if not isinstance(quote, str) or actual != quote.strip():
            raise ReplayValidationError(
                f"fixture lineage quote mismatch: {source_path}:{line_start}"
            )
        if replay_text is not None:
            for source_line in actual.splitlines():
                if source_line.strip() not in replay_lines:
                    raise ReplayValidationError(
                        "fixture replay text does not contain every lineage line"
                    )
        verified.append(
            {
                **dict(row),
                "source_sha256": _sha256(data),
                "lineage_check": "PASS",
            }
        )
    return verified


def _evaluate_fixture(
    name: str,
    data: bytes,
    *,
    frozen: FrozenInputs,
) -> dict[str, Any]:
    try:
        fixture = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ReplayValidationError(f"fixture is invalid JSON: {name}") from exc
    if fixture.get("schema_version") != "v02-b3-regression-fixture-v0.1":
        raise ReplayValidationError(f"unexpected fixture schema: {name}")
    if fixture.get("evidence_mode") != "AUTO_DISCOVERED_IN_FROZEN_FULL_TEXT":
        raise ReplayValidationError(f"fixture evidence boundary drifted: {name}")
    replay_text = fixture.get("replay_text")
    if not isinstance(replay_text, str) or not replay_text:
        raise ReplayValidationError(f"fixture replay text is empty: {name}")
    source_lineage = _validate_lineage_rows(
        fixture.get("source_lineage", []),
        frozen=frozen,
        replay_text=replay_text,
    )
    supporting_lineage = _validate_lineage_rows(
        fixture.get("supporting_lineage", []),
        frozen=frozen,
        replay_text=None,
    )

    expected = fixture.get("expected")
    if not isinstance(expected, dict) or expected.get("blocked") is not True:
        raise ReplayValidationError(f"fixture expected block is missing: {name}")
    expected_finding = expected.get("finding_code")
    if expected_finding not in FINDING_DEFINITIONS:
        raise ReplayValidationError(f"fixture expected finding is unknown: {name}")
    definition = FINDING_DEFINITIONS[expected_finding]
    if expected.get("b2_failure_code") != definition["b2_failure_code"]:
        raise ReplayValidationError(f"fixture B2 mapping drifted: {name}")

    analysis = analyze_text(replay_text)
    finding_by_code = {
        finding["finding_code"]: finding for finding in analysis["findings"]
    }
    observed = finding_by_code.get(expected_finding)
    blocked = (
        observed is not None
        and observed["b2_failure_code"] == expected["b2_failure_code"]
    )
    if expected_finding == "B3_PATH_RESOLUTION_ERROR" and observed:
        blocked = blocked and (
            observed["details"]["path_error_count"] == expected["path_error_count"]
        )
    elif expected_finding == "B3_SNAPSHOT_COUNT_DRIFT" and observed:
        blocked = blocked and (
            observed["details"]["observed_counts"] == expected["observed_counts"]
        )
    elif expected_finding == "B3_PRODUCER_FIVE_LAYER_FULL_SCORE" and observed:
        blocked = blocked and observed["details"]["metrics"] == expected["metrics"]
    elif expected_finding == "B3_SOP_UCR_DIVERGENCE_NOT_GREEN" and observed:
        blocked = blocked and (
            observed["details"]["sop"] == expected["sop"]
            and observed["details"]["ucr"] == expected["ucr"]
        )
    if not blocked:
        raise ReplayValidationError(
            f"regression fixture was not blocked as expected: {name}"
        )
    return {
        "schema_version": "v02-b3-regression-result-v0.1",
        "fixture_id": fixture["fixture_id"],
        "fixture_path": f"fixtures/{name}",
        "fixture_sha256": _sha256(data),
        "category": fixture["category"],
        "source_lineage": source_lineage,
        "supporting_lineage": supporting_lineage,
        "expected_finding_code": expected_finding,
        "detected_finding_codes": [
            finding["finding_code"] for finding in analysis["findings"]
        ],
        "detected_b2_failure_codes": [
            finding["b2_failure_code"] for finding in analysis["findings"]
        ],
        "details": observed["details"],
        "blocked": True,
        "result": "BLOCKED_AS_EXPECTED",
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _artifact_tree_hash(artifacts: Mapping[str, bytes]) -> str:
    rows = [
        {"path": path, "bytes": len(data), "sha256": _sha256(data)}
        for path, data in sorted(artifacts.items())
    ]
    return _sha256(_canonical_bytes(rows))


def build_artifacts_from_frozen(frozen: FrozenInputs) -> dict[str, bytes]:
    """Build outputs only after the caller has completed the input freeze."""

    artifacts: dict[str, bytes] = {
        "input_lock.json": _json_bytes(frozen.input_lock),
        **{
            f"fixtures/{name}": data
            for name, data in sorted(frozen.fixture_bytes.items())
        },
    }

    replay_results = [
        _build_replay_result(
            source,
            b2_contract_hash=frozen.b2_contract_hash,
        )
        for source in frozen.sources
    ]
    for result in replay_results:
        artifacts[f"replay_results/{result['thinking_id']}.json"] = _json_bytes(result)

    regression_results = [
        _evaluate_fixture(name, frozen.fixture_bytes[name], frozen=frozen)
        for name in FIXTURE_NAMES
    ]
    for result in regression_results:
        artifacts[
            f"regression_results/{result['fixture_id']}.json"
        ] = _json_bytes(result)

    status_counts: dict[str, int] = {}
    for result in replay_results:
        status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
    required_classes = {
        result["category"]: result["result"] for result in regression_results
    }
    acceptance = {
        "schema_version": "v02-b3-thinking-replay-acceptance-v0.1",
        "candidate_id": "B3_thinking_replay",
        "candidate_status": "candidate_silver_not_active",
        "b2_contract_hash": frozen.b2_contract_hash,
        "input_lock_sha256": _sha256(artifacts["input_lock.json"]),
        "checks": {
            "source_table_rows_sha_verified": len(frozen.sources),
            "shared_copy_relations_verified": len(frozen.sources),
            "replay_results_built": len(replay_results),
            "hard_stopped_results": status_counts.get("HARD_STOP", 0),
            "required_regression_classes": len(FIXTURE_NAMES),
            "required_regression_classes_blocked": sum(
                result["blocked"] for result in regression_results
            ),
            "required_class_results": required_classes,
            "freeze_before_trace_decode": True,
            "b2_bundle_validation": frozen.b2_check["result"],
            "producer_selfcheck_as_green_rejected": True,
            "activation_allowed": False,
        },
        "replay_statuses": [
            {
                "thinking_id": result["thinking_id"],
                "status": result["status"],
                "finding_codes": [
                    finding["finding_code"] for finding in result["findings"]
                ],
            }
            for result in replay_results
        ],
        "model_api_calls": 0,
        "network_requests": 0,
        "result": "PASS_4_OF_4_BLOCKED_12_OF_12_HARD_STOPPED",
    }
    if acceptance["checks"]["required_regression_classes_blocked"] != 4:
        raise ReplayValidationError("required regression acceptance is not 4/4")
    if acceptance["checks"]["hard_stopped_results"] != 12:
        raise ReplayValidationError("not all twelve historical traces hard-stopped")
    artifacts["acceptance_receipt.json"] = _json_bytes(acceptance)

    inventory = [
        {
            "path": path,
            "bytes": len(data),
            "sha256": _sha256(data),
        }
        for path, data in sorted(artifacts.items())
    ]
    finding_counts: dict[str, int] = {code: 0 for code in FINDING_DEFINITIONS}
    for result in replay_results:
        for finding in result["findings"]:
            finding_counts[finding["finding_code"]] += 1
    manifest = {
        "schema_version": "v02-b3-thinking-replay-manifest-v0.1",
        "candidate_id": "B3_thinking_replay",
        "candidate_status": "candidate_silver_not_active",
        "authority_boundary": {
            "work_order": "连夜施工令 B3",
            "contract": "B2_gate_contract_v0.1",
            "source_entrypoint": frozen.source_table_path,
            "source_truth": "机器表登记原件",
            "supporting_digest": frozen.digest_path,
        },
        "scope": {
            "historical_thinking_traces": 12,
            "regression_fixtures": 4,
            "model_api_calls": 0,
            "network_requests": 0,
            "active_pointer_changed": False,
            "formal_gold_changed": False,
            "default_chain_changed": False,
        },
        "freeze_protocol": {
            "freeze_before_trace_decode": True,
            "input_lock_sha256": _sha256(artifacts["input_lock.json"]),
            "freeze_content_sha256": frozen.input_lock["freeze_content_sha256"],
        },
        "b2_contract": {
            "manifest_path": frozen.b2_manifest_path,
            "manifest_sha256": _sha256(frozen.b2_manifest_bytes),
            "contract_hash": frozen.b2_contract_hash,
            "bundle_validation": frozen.b2_check["result"],
            "producer_selfcheck_authority": (
                "DIAGNOSTIC_ONLY_NOT_GREEN_TICKET"
            ),
        },
        "replay_summary": {
            "total": len(replay_results),
            "status_counts": status_counts,
            "finding_counts": finding_counts,
        },
        "four_class_regression": {
            "required": 4,
            "blocked": 4,
            "class_results": required_classes,
        },
        "artifact_count": len(inventory),
        "artifacts": inventory,
        "bundle_content_hash": _sha256(_canonical_bytes(inventory)),
        "release_isolation": {
            "program_green_issued": False,
            "judge_green_issued": False,
            "engineering_green": False,
            "activation_allowed": False,
        },
    }
    artifacts["manifest.json"] = _json_bytes(manifest)
    return artifacts


def build_artifacts(
    *,
    source_table_path: Path = DEFAULT_SOURCE_TABLE,
    shared_dir: Path = DEFAULT_SHARED_DIR,
    digest_path: Path = DEFAULT_DIGEST,
    fixture_dir: Path = DEFAULT_FIXTURE_DIR,
    b2_dir: Path = DEFAULT_B2_DIR,
) -> dict[str, bytes]:
    frozen = freeze_inputs(
        source_table_path=source_table_path,
        shared_dir=shared_dir,
        digest_path=digest_path,
        fixture_dir=fixture_dir,
        b2_dir=b2_dir,
    )
    return build_artifacts_from_frozen(frozen)


def write_artifacts(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, data in artifacts.items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _check_bundle_from_frozen(
    bundle_dir: Path,
    frozen: FrozenInputs,
) -> dict[str, Any]:
    expected = build_artifacts_from_frozen(frozen)
    missing: list[str] = []
    changed: list[str] = []
    for relative_path, expected_bytes in expected.items():
        path = bundle_dir / relative_path
        if not path.is_file():
            missing.append(relative_path)
        elif path.read_bytes() != expected_bytes:
            changed.append(relative_path)
    if missing or changed:
        raise ReplayValidationError(
            f"bundle differs from frozen replay; missing={missing}, changed={changed}"
        )
    acceptance = json.loads(expected["acceptance_receipt.json"])
    manifest = json.loads(expected["manifest.json"])
    return {
        "result": "PASS",
        "candidate_id": manifest["candidate_id"],
        "compared_file_count": len(expected),
        "source_replay_count": acceptance["checks"]["replay_results_built"],
        "hard_stopped_count": acceptance["checks"]["hard_stopped_results"],
        "regression_blocked": acceptance["checks"][
            "required_regression_classes_blocked"
        ],
        "b2_contract_hash": frozen.b2_contract_hash,
        "input_lock_sha256": manifest["freeze_protocol"]["input_lock_sha256"],
        "tree_sha256": _artifact_tree_hash(expected),
        "model_api_calls": 0,
        "network_requests": 0,
    }


def check_bundle(
    bundle_dir: Path,
    *,
    source_table_path: Path = DEFAULT_SOURCE_TABLE,
    shared_dir: Path = DEFAULT_SHARED_DIR,
    digest_path: Path = DEFAULT_DIGEST,
    b2_dir: Path = DEFAULT_B2_DIR,
) -> dict[str, Any]:
    frozen = freeze_inputs(
        source_table_path=source_table_path,
        shared_dir=shared_dir,
        digest_path=digest_path,
        fixture_dir=bundle_dir / "fixtures",
        b2_dir=b2_dir,
    )
    return _check_bundle_from_frozen(bundle_dir, frozen)


def write_double_run_receipt(
    bundle_dir: Path,
    *,
    source_table_path: Path = DEFAULT_SOURCE_TABLE,
    shared_dir: Path = DEFAULT_SHARED_DIR,
    digest_path: Path = DEFAULT_DIGEST,
    b2_dir: Path = DEFAULT_B2_DIR,
) -> dict[str, Any]:
    frozen = freeze_inputs(
        source_table_path=source_table_path,
        shared_dir=shared_dir,
        digest_path=digest_path,
        fixture_dir=bundle_dir / "fixtures",
        b2_dir=b2_dir,
    )
    first = build_artifacts_from_frozen(frozen)
    second = build_artifacts_from_frozen(frozen)
    if first != second:
        raise ReplayValidationError("two builds from one frozen input differ")

    with tempfile.TemporaryDirectory(prefix="v02-b3-pass1-") as first_tmp:
        with tempfile.TemporaryDirectory(prefix="v02-b3-pass2-") as second_tmp:
            first_dir = Path(first_tmp)
            second_dir = Path(second_tmp)
            write_artifacts(first_dir, first)
            write_artifacts(second_dir, second)
            first_readback = {
                path: (first_dir / path).read_bytes() for path in first
            }
            second_readback = {
                path: (second_dir / path).read_bytes() for path in second
            }
            if first_readback != second_readback:
                raise ReplayValidationError(
                    "two frozen-build directory readbacks differ"
                )
            _check_bundle_from_frozen(first_dir, frozen)
            _check_bundle_from_frozen(second_dir, frozen)

    target = {
        path: (bundle_dir / path).read_bytes()
        for path in first
        if (bundle_dir / path).is_file()
    }
    if target != first:
        missing = sorted(set(first) - set(target))
        changed = sorted(
            path for path in set(first) & set(target) if first[path] != target[path]
        )
        raise ReplayValidationError(
            f"target differs from frozen build; missing={missing}, changed={changed}"
        )
    tree_hash = _artifact_tree_hash(first)
    receipt = {
        "schema_version": "v02-b3-double-run-receipt-v0.1",
        "candidate_id": "B3_thinking_replay",
        "freeze_once_before_two_runs": True,
        "input_lock_sha256": _sha256(first["input_lock.json"]),
        "pass1_tree_sha256": tree_hash,
        "pass2_tree_sha256": _artifact_tree_hash(second),
        "target_tree_sha256": _artifact_tree_hash(target),
        "compared_file_count": len(first),
        "pass1_validation": "PASS",
        "pass2_validation": "PASS",
        "target_validation": "PASS",
        "byte_identical": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    (bundle_dir / "double_run_receipt.json").write_bytes(_json_bytes(receipt))
    return receipt


def _add_common_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-table",
        type=Path,
        default=DEFAULT_SOURCE_TABLE,
    )
    parser.add_argument(
        "--shared-dir",
        type=Path,
        default=DEFAULT_SHARED_DIR,
    )
    parser.add_argument(
        "--digest",
        type=Path,
        default=DEFAULT_DIGEST,
    )
    parser.add_argument(
        "--b2-dir",
        type=Path,
        default=DEFAULT_B2_DIR,
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline frozen replay for the twelve historical thinking traces."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--output-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    build.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    _add_common_input_args(build)

    validate = subparsers.add_parser("validate-bundle")
    validate.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    _add_common_input_args(validate)

    double_run = subparsers.add_parser("double-run")
    double_run.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    _add_common_input_args(double_run)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "build":
        artifacts = build_artifacts(
            source_table_path=args.source_table,
            shared_dir=args.shared_dir,
            digest_path=args.digest,
            fixture_dir=args.fixture_dir,
            b2_dir=args.b2_dir,
        )
        write_artifacts(args.output_dir, artifacts)
        result = {
            "result": "BUILT",
            "output_dir": str(args.output_dir),
            "file_count": len(artifacts),
            "tree_sha256": _artifact_tree_hash(artifacts),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    elif args.command == "validate-bundle":
        result = check_bundle(
            args.bundle_dir,
            source_table_path=args.source_table,
            shared_dir=args.shared_dir,
            digest_path=args.digest,
            b2_dir=args.b2_dir,
        )
    else:
        result = write_double_run_receipt(
            args.bundle_dir,
            source_table_path=args.source_table,
            shared_dir=args.shared_dir,
            digest_path=args.digest,
            b2_dir=args.b2_dir,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

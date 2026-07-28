from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from typing import Any, Mapping, Sequence

from . import qec_activate as qec
from . import route_runner


ROUTE_ID = "QEC-PSR"
CONTROL_ROUTE_ID = "QEC"
TRACE_SCHEMA = "v02-r2-qec-psr-protection-trace.v1"
TRACE_COLLECTION_SCHEMA = "v02-r2-qec-psr-protection-trace-collection.v1"


class QECPSRError(ValueError):
    """QEC-PSR 公开选择旁车拒收错误。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _payload_sha(value: Mapping[str, Any], field: str) -> str:
    payload = dict(value)
    payload.pop(field, None)
    return sha256_bytes(canonical_bytes(payload))


def _unique_by(
    rows: Sequence[Mapping[str, Any]], *, key: str, label: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if not isinstance(value, str) or not value:
            raise QECPSRError(f"QEC_PSR_{label}_KEY_INVALID")
        if value in result:
            raise QECPSRError(f"QEC_PSR_{label}_DUPLICATED:{value}")
        result[value] = dict(row)
    return result


def _question_state_prefix(trace: Mapping[str, Any]) -> dict[str, Any]:
    selected_ids: list[str] = []
    selected_set: set[str] = set()
    cursors: dict[str, int] = {}
    used_chars = 0
    for action in trace["actions"]:
        if action["reason_code"] == "A5_GLOBAL_RESIDUAL_FILL":
            break
        query_id = action["query_id"]
        cursor_after = action["cursor_after"]
        if query_id is not None and cursor_after is not None:
            cursors[query_id] = max(cursors.get(query_id, 0), int(cursor_after))
        if (
            action["operation"] == "FETCH_NEXT"
            and action["reason_code"] == "QUESTION_STATE_NEXT_BOUND_A5_STREAM"
        ):
            paragraph_id = action["paragraph_id"]
            if paragraph_id in selected_set:
                raise QECPSRError(
                    f"QEC_PSR_STATE_SELECTION_DUPLICATED:{trace['cell_id']}"
                )
            selected_ids.append(paragraph_id)
            selected_set.add(paragraph_id)
            used_chars += int(action["incremental_candidate_chars"])
    if list(trace["selected_window_ids"][: len(selected_ids)]) != selected_ids:
        raise QECPSRError(f"QEC_PSR_STATE_PREFIX_DRIFT:{trace['cell_id']}")
    return {
        "selected_ids": selected_ids,
        "selected_set": selected_set,
        "cursors": cursors,
        "used_chars": used_chars,
    }


def _merged_rows(rank_stream_cell: Mapping[str, Any]) -> list[dict[str, Any]]:
    rankings = [stream["records"] for stream in rank_stream_cell["streams"]]
    return route_runner._merge_rankings_nonzero_fusion(rankings)


def _protection_candidates(
    *,
    unit: str,
    query_ids_by_unit: Mapping[str, Sequence[str]],
    stream_by_id: Mapping[str, Mapping[str, Any]],
    cursors: Mapping[str, int],
    selected_set: set[str],
    control_set: set[str],
) -> list[tuple[int, str, str, Mapping[str, Any]]]:
    candidates: list[tuple[int, str, str, Mapping[str, Any]]] = []
    for query_id in query_ids_by_unit[unit]:
        stream = stream_by_id.get(query_id)
        if stream is None:
            raise QECPSRError(f"QEC_PSR_BOUND_QUERY_MISSING:{query_id}")
        cursor = int(cursors.get(query_id, 0))
        for record in stream["records"][cursor:]:
            if not record["matched_grams"] or float(record["score"]) <= 0:
                break
            paragraph_id = record["paragraph_id"]
            if paragraph_id in selected_set or paragraph_id in control_set:
                continue
            candidates.append(
                (int(record["rank"]), query_id, paragraph_id, record)
            )
    return sorted(candidates, key=lambda row: (row[0], row[1], row[2]))


def select_cell(
    *,
    plan: Mapping[str, Any],
    query_binding: Mapping[str, Any],
    rank_stream_cell: Mapping[str, Any],
    qec_trace: Mapping[str, Any],
    control_projection_cell: Mapping[str, Any],
    budget_chars: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cell_id = query_binding["cell_id"]
    if any(
        row["cell_id"] != cell_id
        for row in (rank_stream_cell, qec_trace, control_projection_cell)
    ):
        raise QECPSRError(f"QEC_PSR_CELL_BINDING_MISMATCH:{cell_id}")
    if qec_trace["budget_chars"] != budget_chars:
        raise QECPSRError(f"QEC_PSR_TRACE_BUDGET_MISMATCH:{cell_id}")
    if plan["question_id"] != qec_trace["question_id"]:
        raise QECPSRError(f"QEC_PSR_PLAN_BINDING_MISMATCH:{cell_id}")

    state = _question_state_prefix(qec_trace)
    selected_ids = list(state["selected_ids"])
    selected_set = set(state["selected_set"])
    used_chars = int(state["used_chars"])
    control_ids = [
        row["paragraph_id"] for row in control_projection_cell["selected_windows"]
    ]
    control_set = set(control_ids)
    if len(control_set) != len(control_ids):
        raise QECPSRError(f"QEC_PSR_CONTROL_SELECTION_DUPLICATED:{cell_id}")
    if not selected_set <= control_set:
        raise QECPSRError(f"QEC_PSR_STATE_OUTSIDE_CONTROL:{cell_id}")

    stream_by_id = {
        row["query_id"]: row for row in rank_stream_cell["streams"]
    }
    query_ids_by_unit: dict[str, list[str]] = defaultdict(list)
    for binding in query_binding["query_bindings"]:
        for unit in binding["bound_obligation_or_facet_ids"]:
            query_ids_by_unit[unit].append(binding["query_id"])
    units = qec.plan_units(plan)
    if any(not query_ids_by_unit[unit] for unit in units):
        raise QECPSRError(f"QEC_PSR_PLAN_UNIT_WITHOUT_QUERY:{cell_id}")

    protections: list[dict[str, Any]] = []
    for unit in units:
        candidates = _protection_candidates(
            unit=unit,
            query_ids_by_unit=query_ids_by_unit,
            stream_by_id=stream_by_id,
            cursors=state["cursors"],
            selected_set=selected_set,
            control_set=control_set,
        )
        for stream_rank, query_id, paragraph_id, record in candidates:
            char_count = int(record["char_count"])
            if used_chars + char_count > budget_chars:
                continue
            selected_ids.append(paragraph_id)
            selected_set.add(paragraph_id)
            used_chars += char_count
            protections.append(
                {
                    "plan_unit_id": unit,
                    "query_id": query_id,
                    "paragraph_id": paragraph_id,
                    "stream_rank": stream_rank,
                    "char_count": char_count,
                    "paragraph_sha256": record["paragraph_sha256"],
                    "matched_gram_count": len(record["matched_grams"]),
                }
            )
            break

    merged_rows = _merged_rows(rank_stream_cell)
    merged_by_id = {row["paragraph_id"]: row for row in merged_rows}
    merged_rank = {
        row["paragraph_id"]: index
        for index, row in enumerate(merged_rows, start=1)
    }
    for paragraph_id in selected_ids:
        if paragraph_id not in merged_by_id:
            raise QECPSRError(
                f"QEC_PSR_SELECTED_PARAGRAPH_OUTSIDE_FUSION:{cell_id}:{paragraph_id}"
            )
    for row in merged_rows:
        paragraph_id = row["paragraph_id"]
        if paragraph_id in selected_set:
            continue
        char_count = int(row["char_count"])
        if used_chars + char_count > budget_chars:
            continue
        selected_ids.append(paragraph_id)
        selected_set.add(paragraph_id)
        used_chars += char_count

    remaining_fit = [
        row["paragraph_id"]
        for row in merged_rows
        if row["paragraph_id"] not in selected_set
        and used_chars + int(row["char_count"]) <= budget_chars
    ]
    if remaining_fit:
        raise QECPSRError(f"QEC_PSR_RESIDUAL_FILL_NOT_MAXIMAL:{cell_id}")
    selected_windows = [
        qec._output_window(
            merged_by_id[paragraph_id], rank=merged_rank[paragraph_id]
        )
        for paragraph_id in selected_ids
    ]
    added = sorted(selected_set - control_set)
    removed = sorted(control_set - selected_set)
    trace: dict[str, Any] = {
        "schema_version": TRACE_SCHEMA,
        "route_id": ROUTE_ID,
        "control_route_id": CONTROL_ROUTE_ID,
        "cell_id": cell_id,
        "question_id": plan["question_id"],
        "budget_chars": budget_chars,
        "single_variable": {
            "name": "protected_outside_control_hit_per_plan_unit",
            "control": 0,
            "candidate": 1,
        },
        "state_selected_count": len(state["selected_ids"]),
        "state_source_chars": int(state["used_chars"]),
        "control_selected_ids": control_ids,
        "candidate_selected_ids": selected_ids,
        "candidate_source_chars": used_chars,
        "protections": protections,
        "added_vs_qec_control": added,
        "removed_vs_qec_control": removed,
        "eligible": bool(added or removed),
        "residual_fit_remaining_count": 0,
    }
    trace["trace_payload_sha256"] = _payload_sha(
        trace, "trace_payload_sha256"
    )
    return selected_windows, trace


def build_candidate(
    *,
    question_plan_collection: Mapping[str, Any],
    query_binding_collection: Mapping[str, Any],
    rank_stream_collection: Mapping[str, Any],
    qec_trace_collection: Mapping[str, Any],
    control_projection: Mapping[str, Any],
    control_output: Mapping[str, Any],
    budget_chars: int,
) -> dict[str, dict[str, Any]]:
    if control_output["route_id"] != CONTROL_ROUTE_ID:
        raise QECPSRError("QEC_PSR_CONTROL_OUTPUT_ROUTE_INVALID")
    if control_output["budget_chars"] != budget_chars:
        raise QECPSRError("QEC_PSR_CONTROL_OUTPUT_BUDGET_INVALID")
    plans = _unique_by(
        question_plan_collection["plans"], key="question_id", label="PLAN"
    )
    bindings = _unique_by(
        query_binding_collection["cells"], key="cell_id", label="BINDING"
    )
    rank_cells = _unique_by(
        rank_stream_collection["cells"], key="cell_id", label="RANK_CELL"
    )
    traces = _unique_by(
        qec_trace_collection["cells"], key="cell_id", label="TRACE"
    )
    controls = _unique_by(
        control_projection["cells"], key="cell_id", label="CONTROL_PROJECTION"
    )
    output_cells = _unique_by(
        control_output["cells"], key="cell_id", label="CONTROL_OUTPUT"
    )
    cell_ids = set(bindings)
    if not (
        cell_ids
        == set(rank_cells)
        == set(traces)
        == set(controls)
        == set(output_cells)
    ):
        raise QECPSRError("QEC_PSR_INPUT_CELL_SET_MISMATCH")

    candidate_cells: list[dict[str, Any]] = []
    trace_cells: list[dict[str, Any]] = []
    for control_cell in control_output["cells"]:
        cell_id = control_cell["cell_id"]
        question_id = control_cell["question_id"]
        selected_windows, trace = select_cell(
            plan=plans[question_id],
            query_binding=bindings[cell_id],
            rank_stream_cell=rank_cells[cell_id],
            qec_trace=traces[cell_id],
            control_projection_cell=controls[cell_id],
            budget_chars=budget_chars,
        )
        candidate_cell = copy.deepcopy(control_cell)
        candidate_cell["selected_windows"] = selected_windows
        candidate_cell["candidate_chars"] = sum(
            int(row["char_count"]) for row in selected_windows
        )
        actual = [
            row
            for row in selected_windows
            if row["selection_reason"] == "ACTUAL_QUERY_MATCH"
        ]
        fallback = [
            row
            for row in selected_windows
            if row["selection_reason"] == "UNMATCHED_FALLBACK"
        ]
        candidate_cell.update(
            {
                "actual_match_window_count": len(actual),
                "actual_match_chars": sum(int(row["char_count"]) for row in actual),
                "fallback_window_count": len(fallback),
                "fallback_chars": sum(int(row["char_count"]) for row in fallback),
            }
        )
        candidate_cells.append(candidate_cell)
        trace_cells.append(trace)

    output = copy.deepcopy(control_output)
    output["route_id"] = ROUTE_ID
    output["cells"] = candidate_cells
    output.pop("output_payload_sha256", None)
    output["output_payload_sha256"] = _payload_sha(
        output, "output_payload_sha256"
    )
    projection = route_runner.selection_projection(candidate_cells)
    trace_collection: dict[str, Any] = {
        "schema_version": TRACE_COLLECTION_SCHEMA,
        "route_id": ROUTE_ID,
        "control_route_id": CONTROL_ROUTE_ID,
        "budget_chars": budget_chars,
        "cell_count": len(trace_cells),
        "eligible_cell_count": sum(bool(row["eligible"]) for row in trace_cells),
        "protected_plan_unit_record_count": sum(
            len(row["protections"]) for row in trace_cells
        ),
        "cells": trace_cells,
        "model_api_calls": 0,
        "network_calls": 0,
    }
    trace_collection["collection_payload_sha256"] = _payload_sha(
        trace_collection, "collection_payload_sha256"
    )
    return {
        "sealed_output": output,
        "selection_projection": projection,
        "protection_trace": trace_collection,
    }

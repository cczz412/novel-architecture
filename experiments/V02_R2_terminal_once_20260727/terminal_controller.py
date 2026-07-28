from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.V02_R2_development_hardening_r01_20260727 import (
    qec_activate as qec,
)
from experiments.V02_R2_development_hardening_r01_20260727 import (
    route_runner as routes,
)


SCHEMA_VERSION = "v02-r2-terminal-controller.v1"
RUN_ID = "V02-R2-M1-03-terminal-reseal-r02-20260727"
CYCLE_ID = "review-cycle-6c0fe467-3fae-418d-a3c2-46fdb5f7c722"
TICKET_ID = "M3-05-R2-TERMINAL-30-RESEAL-20260727-2036"
ROUTE_IDS = ("A5", "QEC")
PRIMARY_BUDGET_CHARS = 2500
MODEL_PROFILE = "agent-plan_cn-beijing_personal"
MODEL_ID = "minimax-m3-modelhub"
EXPECTED_RESPONSE_MODEL = "minimax-m3"
MODEL_MAX_OUTPUT_TOKENS = 2048
MODEL_REASONING_EFFORT = "medium"
MAX_SELECTED_SOURCE_IDS = 12
QUESTION_TOTAL = 30
QUESTION_PER_CASE = 10
CASE_TOTAL = 3
MODULE_NAME = "experiments.V02_R2_terminal_once_20260727.terminal_controller"
PROCESS_PREFIX = f"uv run python -m {MODULE_NAME}"


class TerminalError(RuntimeError):
    """R2 一次性终验拒收错误。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TerminalError(f"JSON_INVALID:{path}") from exc


def write_json(path: Path, value: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value)
    if exclusive:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(canonical_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())


def iter_nodes(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from iter_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_nodes(child)


def _unique_by_canonical(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for value in values:
        converted = dict(value)
        unique.setdefault(sha256_bytes(canonical_bytes(converted)), converted)
    return list(unique.values())


def extract_catalogs(source_binding: Any) -> list[dict[str, Any]]:
    candidates = _unique_by_canonical(
        node
        for node in iter_nodes(source_binding)
        if isinstance(node.get("source_id"), str)
        and isinstance(node.get("source_text"), str)
        and isinstance(node.get("paragraphs"), list)
        and isinstance(node.get("sentences"), list)
    )
    if len(candidates) != CASE_TOTAL:
        raise TerminalError(f"SOURCE_CATALOG_COUNT_INVALID:{len(candidates)}")
    source_ids = [row["source_id"] for row in candidates]
    if len(source_ids) != len(set(source_ids)):
        raise TerminalError("SOURCE_CATALOG_ID_DUPLICATED")
    for catalog in candidates:
        source_text = catalog["source_text"]
        paragraphs = catalog["paragraphs"]
        sentences = catalog["sentences"]
        if not paragraphs or not sentences:
            raise TerminalError(f"SOURCE_CATALOG_EMPTY:{catalog['source_id']}")
        rebuilt = "".join(str(row.get("original_text", "")) for row in paragraphs)
        if rebuilt != source_text:
            raise TerminalError(f"SOURCE_PARAGRAPH_REBUILD_MISMATCH:{catalog['source_id']}")
        if catalog.get("source_body_sha256") not in {
            None,
            sha256_bytes(source_text.encode("utf-8")),
        }:
            raise TerminalError(f"SOURCE_BODY_SHA_MISMATCH:{catalog['source_id']}")
        paragraph_ids = {row.get("paragraph_id") for row in paragraphs}
        sentence_ids: set[str] = set()
        for sentence in sentences:
            sentence_id = sentence.get("sentence_id")
            if not isinstance(sentence_id, str) or not sentence_id:
                raise TerminalError(
                    f"SOURCE_SENTENCE_ID_INVALID:{catalog['source_id']}"
                )
            if sentence_id in sentence_ids:
                raise TerminalError(
                    f"SOURCE_SENTENCE_ID_DUPLICATED:{catalog['source_id']}"
                )
            sentence_ids.add(sentence_id)
            if sentence.get("paragraph_id") not in paragraph_ids:
                raise TerminalError(
                    f"SOURCE_SENTENCE_PARAGRAPH_INVALID:{catalog['source_id']}"
                )
            original_text = sentence.get("original_text")
            if not isinstance(original_text, str) or not original_text:
                raise TerminalError(
                    f"SOURCE_SENTENCE_TEXT_INVALID:{catalog['source_id']}"
                )
    return sorted(candidates, key=lambda row: row["source_id"])


def _question_rows(question_set: Any) -> list[dict[str, Any]]:
    rows = _unique_by_canonical(
        node
        for node in iter_nodes(question_set)
        if isinstance(node.get("question_id"), str)
        and (
            isinstance(node.get("question_text"), str)
            or isinstance(node.get("text"), str)
        )
    )
    if not rows:
        raise TerminalError("QUESTION_ROWS_MISSING")
    return rows


def extract_question_cells(
    question_set: Any,
    *,
    case_ids: Sequence[str],
) -> list[dict[str, str]]:
    rows = _question_rows(question_set)
    normalized: list[dict[str, str | None]] = []
    for row in rows:
        question_text = row.get("question_text", row.get("text"))
        case_id = row.get("case_id", row.get("source_id"))
        if case_id is not None and case_id not in case_ids:
            continue
        normalized.append(
            {
                "case_id": case_id,
                "question_id": row["question_id"],
                "question_text": question_text.strip(),
            }
        )
    explicit = [row for row in normalized if row["case_id"] is not None]
    generic = [row for row in normalized if row["case_id"] is None]
    cells: list[dict[str, str]] = []
    if len(explicit) == QUESTION_TOTAL and not generic:
        cells = [
            {
                "case_id": str(row["case_id"]),
                "question_id": str(row["question_id"]),
                "question_text": str(row["question_text"]),
            }
            for row in explicit
        ]
    elif len(generic) == QUESTION_PER_CASE and not explicit:
        for case_id in case_ids:
            for row in generic:
                cells.append(
                    {
                        "case_id": case_id,
                        "question_id": str(row["question_id"]),
                        "question_text": str(row["question_text"]),
                    }
                )
    else:
        raise TerminalError(
            f"QUESTION_LAYOUT_INVALID:explicit={len(explicit)}:generic={len(generic)}"
        )
    keys = [(row["case_id"], row["question_id"]) for row in cells]
    if len(keys) != QUESTION_TOTAL or len(keys) != len(set(keys)):
        raise TerminalError("QUESTION_CELL_COUNT_OR_KEY_INVALID")
    per_case = {
        case_id: sum(row["case_id"] == case_id for row in cells)
        for case_id in case_ids
    }
    if set(per_case.values()) != {QUESTION_PER_CASE}:
        raise TerminalError(f"QUESTION_PER_CASE_INVALID:{per_case}")
    return sorted(cells, key=lambda row: (row["case_id"], row["question_id"]))


def _legacy_query_map(
    *,
    route_id: str,
    case_id: str,
    question_id: str,
    queries: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_version": routes.QUERY_MAP_SCHEMA,
        "route_id": route_id,
        "case_id": case_id,
        "question_id": question_id,
        "queries": [
            {
                "query_id": f"QRY-{index:03d}",
                "query_text": query,
                "origin_kind": "LEGACY_A5_FROZEN_QUERY",
            }
            for index, query in enumerate(queries, start=1)
        ],
    }


def build_route_candidates(
    *,
    catalogs: Sequence[Mapping[str, Any]],
    question_cells: Sequence[Mapping[str, str]],
) -> dict[str, list[dict[str, Any]]]:
    index = routes.build_sparse_index(catalogs)
    aliases = routes._extract_high_confidence_aliases(catalogs)
    catalog_by_id = {row["source_id"]: row for row in catalogs}
    qec_program_sha = sha256_file(Path(qec.__file__))
    prepared: dict[str, dict[str, Any]] = {}
    rank_cells: list[dict[str, Any]] = []
    a5_maps: list[dict[str, Any]] = []
    for cell in question_cells:
        case_id = cell["case_id"]
        question_id = cell["question_id"]
        question_text = cell["question_text"]
        plan = routes.plan_question(question_text)
        queries = routes._query_variants(
            route_id="A5",
            question_text=question_text,
            plan=plan,
            aliases=aliases,
            case_id=case_id,
        )
        a5_map = _legacy_query_map(
            route_id="A5",
            case_id=case_id,
            question_id=question_id,
            queries=queries,
        )
        qec_map = _legacy_query_map(
            route_id="QEC",
            case_id=case_id,
            question_id=question_id,
            queries=queries,
        )
        rankings = [
            routes.rank_paragraphs(
                query_text=query,
                case_id=case_id,
                index=index,
            )
            for query in queries
        ]
        qec_plan = qec.build_question_plan(
            question_id=question_id,
            question_text=question_text,
            planner_artifact_sha256=qec_program_sha,
        )
        rank_cell = qec.build_rank_stream_cell(
            case_id=case_id,
            question_id=question_id,
            query_map=qec_map,
            rankings=rankings,
        )
        binding = qec.bind_a5_queries_to_units(plan=qec_plan, query_map=qec_map)
        key = f"{case_id}::{question_id}"
        prepared[key] = {
            "question": dict(cell),
            "a5_map": a5_map,
            "qec_map": qec_map,
            "rankings": rankings,
            "qec_plan": qec_plan,
            "rank_cell": rank_cell,
            "binding": binding,
            "merged": routes._merge_rankings_nonzero_fusion(rankings),
        }
        a5_maps.append(a5_map)
        rank_cells.append(rank_cell)
    a5_collection_sha = sha256_bytes(
        canonical_bytes(
            {
                "schema_version": "r2-query-map-collection.v1",
                "route_id": "A5",
                "cells": sorted(
                    a5_maps,
                    key=lambda row: f"{row['case_id']}::{row['question_id']}",
                ),
            }
        )
    )
    rank_collection_sha = sha256_bytes(
        canonical_bytes(qec.build_rank_stream_collection(rank_cells))
    )
    outputs: dict[str, list[dict[str, Any]]] = {route_id: [] for route_id in ROUTE_IDS}
    for key in sorted(prepared):
        row = prepared[key]
        cell = row["question"]
        case_id = cell["case_id"]
        catalog = catalog_by_id[case_id]
        paragraph_text_by_id = {
            paragraph["paragraph_id"]: paragraph["original_text"]
            for paragraph in catalog["paragraphs"]
        }
        a5_selected = routes._pack_nonzero_fusion(
            row["merged"],
            budget=PRIMARY_BUDGET_CHARS,
        )
        qec_selected, qec_trace = qec.execute_question_state(
            plan=row["qec_plan"],
            query_binding=row["binding"],
            rank_stream_cell=row["rank_cell"],
            merged_rows=row["merged"],
            paragraph_text_by_id=paragraph_text_by_id,
            budget_chars=PRIMARY_BUDGET_CHARS,
            a5_query_map_sha256=a5_collection_sha,
            rank_stream_manifest_sha256=rank_collection_sha,
        )
        for route_id, selected, trace_sha in (
            ("A5", a5_selected, None),
            ("QEC", qec_selected, qec_trace["trace_payload_sha256"]),
        ):
            candidate_sentences: list[dict[str, Any]] = []
            selected_paragraphs = {
                window["paragraph_id"] for window in selected
            }
            for sentence in catalog["sentences"]:
                if sentence["paragraph_id"] not in selected_paragraphs:
                    continue
                aliases_for_sentence = sorted(
                    {
                        sentence["sentence_id"],
                        *sentence.get("accepted_legacy_source_ids", []),
                    }
                )
                candidate_sentences.append(
                    {
                        "source_id": sentence["sentence_id"],
                        "source_id_aliases": aliases_for_sentence,
                        "paragraph_id": sentence["paragraph_id"],
                        "text": sentence["original_text"],
                    }
                )
            outputs[route_id].append(
                {
                    "route_id": route_id,
                    "cell_id": key,
                    "case_id": case_id,
                    "question_id": cell["question_id"],
                    "question_text": cell["question_text"],
                    "budget_chars": PRIMARY_BUDGET_CHARS,
                    "candidate_chars": sum(
                        int(window["char_count"]) for window in selected
                    ),
                    "selected_windows": selected,
                    "candidate_sentences": candidate_sentences,
                    "qec_trace_sha256": trace_sha,
                    "retrieval_policy_sha256": sha256_bytes(
                        canonical_bytes(
                            {
                                "route_id": route_id,
                                "budget_chars": PRIMARY_BUDGET_CHARS,
                                "a5_query_collection_sha256": a5_collection_sha,
                                "qec_rank_collection_sha256": rank_collection_sha,
                            }
                        )
                    ),
                }
            )
    if any(len(rows) != QUESTION_TOTAL for rows in outputs.values()):
        raise TerminalError("ROUTE_CANDIDATE_CELL_COUNT_INVALID")
    return outputs


def model_request_payload(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "v02-r2-terminal-evidence-selection-request.v1",
        "question_id": candidate["question_id"],
        "question": candidate["question_text"],
        "rules": {
            "select_only_ids_from_evidence": True,
            "select_minimum_direct_evidence": True,
            "maximum_selected_source_ids": MAX_SELECTED_SOURCE_IDS,
            "abstain_when_material_insufficient": True,
            "no_free_form_answer": True,
        },
        "evidence": [
            {
                "source_id": row["source_id"],
                "text": row["text"],
            }
            for row in candidate["candidate_sentences"]
        ],
        "required_output": {
            "status": "ANSWER or ABSTAIN",
            "selected_source_ids": ["source_id"],
        },
    }


def parse_model_selection(
    raw_envelope: Mapping[str, Any],
    *,
    allowed_source_ids: set[str],
) -> dict[str, Any]:
    if raw_envelope.get("model") != EXPECTED_RESPONSE_MODEL:
        raise TerminalError(
            f"MODEL_RESPONSE_ID_MISMATCH:{raw_envelope.get('model')}"
        )
    content = raw_envelope.get("content")
    if not isinstance(content, str) or not content.strip():
        raise TerminalError("MODEL_RESPONSE_CONTENT_EMPTY")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TerminalError("MODEL_RESPONSE_CONTENT_NOT_JSON") from exc
    if set(value) != {"status", "selected_source_ids"}:
        raise TerminalError("MODEL_SELECTION_FIELDS_INVALID")
    if value["status"] not in {"ANSWER", "ABSTAIN"}:
        raise TerminalError("MODEL_SELECTION_STATUS_INVALID")
    selected = value["selected_source_ids"]
    if (
        not isinstance(selected, list)
        or any(not isinstance(item, str) or not item for item in selected)
        or len(selected) != len(set(selected))
        or len(selected) > MAX_SELECTED_SOURCE_IDS
    ):
        raise TerminalError("MODEL_SELECTION_SOURCE_IDS_INVALID")
    unknown = sorted(set(selected) - allowed_source_ids)
    if unknown:
        raise TerminalError(f"MODEL_SELECTION_SOURCE_ID_UNKNOWN:{unknown}")
    if value["status"] == "ANSWER" and not selected:
        raise TerminalError("MODEL_SELECTION_ANSWER_EMPTY")
    if value["status"] == "ABSTAIN" and selected:
        raise TerminalError("MODEL_SELECTION_ABSTAIN_WITH_SOURCE")
    return {
        "status": value["status"],
        "selected_source_ids": selected,
    }


def invoke_model(
    *,
    request_path: Path,
    raw_response_path: Path,
) -> tuple[dict[str, Any], int]:
    command = [
        "arkcli",
        "+chat",
        "--model",
        MODEL_ID,
        "--format",
        "json",
        "--thinking",
        "disabled",
        "--reasoning-effort",
        MODEL_REASONING_EFFORT,
        "--temperature",
        "0",
        "--max-output-tokens",
        str(MODEL_MAX_OUTPUT_TOKENS),
        "--text-format",
        "json_object",
        "--no-progress",
        "--input",
        f"@{request_path}",
        "读取附件中的问题和候选证据。只按附件规则返回 JSON 对象，不要输出解释。",
    ]
    environment = os.environ.copy()
    environment.update(
        {
            "ARK_PROFILE": MODEL_PROFILE,
            "ARKCLI_CALLER_TYPE": "ai_agent",
            "ARKCLI_CALLER_NAME": "codex",
            "ARKCLI_SKILL_NAME": "arkcli-chat",
        }
    )
    started = time.monotonic_ns()
    completed = subprocess.run(
        command,
        cwd=request_path.parent,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=600,
        check=False,
    )
    elapsed_ms = max(0, (time.monotonic_ns() - started) // 1_000_000)
    raw_response_path.parent.mkdir(parents=True, exist_ok=True)
    raw_response_path.write_bytes(completed.stdout)
    stderr_path = raw_response_path.with_suffix(".stderr")
    stderr_path.write_bytes(completed.stderr)
    if completed.returncode != 0:
        raise TerminalError(f"MODEL_TRANSPORT_FAILED:{completed.returncode}")
    try:
        envelope = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TerminalError("MODEL_ENVELOPE_INVALID") from exc
    return envelope, elapsed_ms


def render_answer(
    *,
    candidate: Mapping[str, Any],
    selection: Mapping[str, Any],
    envelope: Mapping[str, Any] | None,
    request_sha256: str,
    raw_response_sha256: str | None,
    elapsed_ms: int,
    failure_code: str | None,
) -> dict[str, Any]:
    sentence_by_id = {
        row["source_id"]: row for row in candidate["candidate_sentences"]
    }
    selected = selection["selected_source_ids"]
    claims = [
        {
            "source_id": source_id,
            "statement_mode": "PROGRAM_BACKFILLED_EXTRACTIVE_VERBATIM",
            "statement": sentence_by_id[source_id]["text"],
            "statement_sha256": sha256_bytes(
                sentence_by_id[source_id]["text"].encode("utf-8")
            ),
            "source_id_aliases": sentence_by_id[source_id][
                "source_id_aliases"
            ],
        }
        for source_id in selected
    ]
    usage = envelope.get("usage", {}) if envelope is not None else {}
    answer: dict[str, Any] = {
        "schema_version": "v02-r2-terminal-extractive-answer.v1",
        "run_id": RUN_ID,
        "route_id": candidate["route_id"],
        "cell_id": candidate["cell_id"],
        "case_id": candidate["case_id"],
        "question_id": candidate["question_id"],
        "status": selection["status"] if failure_code is None else "FAILED",
        "claims": claims,
        "failure_code": failure_code,
        "request_sha256": request_sha256,
        "raw_response_sha256": raw_response_sha256,
        "response_model": envelope.get("model") if envelope else None,
        "response_id": envelope.get("id") if envelope else None,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "cost": {
            "logical_model_calls": 1,
            "model_attempts": 1,
            "retrieval_candidate_chars": candidate["candidate_chars"],
            "model_elapsed_ms": elapsed_ms,
        },
    }
    answer["answer_payload_sha256"] = sha256_bytes(canonical_bytes(answer))
    return answer


def _freeze_manifest(root: Path, *, excluded: set[str] | None = None) -> dict[str, Any]:
    excluded = excluded or set()
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        files.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    result = {
        "schema_version": "v02-r2-terminal-collection-manifest.v1",
        "file_count": len(files),
        "files": files,
    }
    result["manifest_payload_sha256"] = sha256_bytes(canonical_bytes(result))
    return result


def _assert_control_authority(
    *,
    run_dir: Path,
    authority_path: Path,
    stage: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    authority = load_json(authority_path)
    if authority.get("cycle_id") != CYCLE_ID:
        raise TerminalError("AUTHORITY_CYCLE_ID_MISMATCH")
    if authority.get("run_id") != RUN_ID:
        raise TerminalError("AUTHORITY_RUN_ID_MISMATCH")
    if authority.get("ticket_id") != TICKET_ID:
        raise TerminalError("AUTHORITY_TICKET_ID_MISMATCH")
    if authority.get("terminal_run_authorized") is not True:
        raise TerminalError("AUTHORITY_TERMINAL_RUN_NOT_ALLOWED")
    if authority.get("development_trial_runs") != 0:
        raise TerminalError("AUTHORITY_DEVELOPMENT_TRIAL_NOT_ZERO")
    if authority.get("terminal_run_limit") != 1:
        raise TerminalError("AUTHORITY_TERMINAL_RUN_LIMIT_INVALID")
    allowed_process = authority.get("allowed_processes", {}).get(stage)
    expected_process = f"{PROCESS_PREFIX} {stage}"
    if allowed_process != expected_process:
        raise TerminalError(f"AUTHORITY_PROCESS_NOT_ALLOWED:{stage}")
    freeze_bundle_path = run_dir / "control/terminal_freeze_bundle.json"
    expected_bundle_sha = authority.get("terminal_freeze_bundle_sha256")
    if sha256_file(freeze_bundle_path) != expected_bundle_sha:
        raise TerminalError("AUTHORITY_FREEZE_BUNDLE_DRIFT")
    bundle = load_json(freeze_bundle_path)
    if bundle.get("controller_sha256") != sha256_file(Path(__file__)):
        raise TerminalError("CONTROLLER_SHA_DRIFT")
    for record in bundle.get("public_artifacts", []):
        path = Path(record["path"])
        if not path.is_absolute():
            path = run_dir.parent.parent / path
        if not path.is_file() or sha256_file(path) != record["sha256"]:
            raise TerminalError(f"FROZEN_PUBLIC_ARTIFACT_DRIFT:{record['path']}")
    return authority, bundle


def _assert_exact_authorized_path(
    authority: Mapping[str, Any],
    *,
    label: str,
    path: Path,
) -> None:
    expected = authority.get("allowed_private_files", {}).get(label)
    if expected != str(path.resolve()):
        raise TerminalError(f"AUTHORITY_PRIVATE_PATH_MISMATCH:{label}")


def _copy_verified_private(
    *,
    source: Path,
    destination: Path,
    expected_sha256: str,
) -> None:
    if sha256_file(source) != expected_sha256:
        raise TerminalError(f"PRIVATE_SOURCE_SHA_MISMATCH:{source.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if sha256_file(destination) != expected_sha256:
        raise TerminalError(f"PRIVATE_COPY_SHA_MISMATCH:{destination.name}")


def run_terminal(
    *,
    run_dir: Path,
    authority_path: Path,
    source_binding_path: Path,
    question_set_path: Path,
) -> dict[str, Any]:
    authority, bundle = _assert_control_authority(
        run_dir=run_dir,
        authority_path=authority_path,
        stage="run",
    )
    _assert_exact_authorized_path(
        authority,
        label="source_bindings",
        path=source_binding_path,
    )
    _assert_exact_authorized_path(
        authority,
        label="question_set",
        path=question_set_path,
    )
    consumption_path = run_dir / "state/ticket_consumption.json"
    if consumption_path.exists() or (run_dir / "sealed_outputs").exists():
        raise TerminalError("TERMINAL_RUN_ALREADY_CONSUMED")
    consumption = {
        "schema_version": "v02-r2-terminal-ticket-consumption.v1",
        "ticket_id": TICKET_ID,
        "cycle_id": CYCLE_ID,
        "run_id": RUN_ID,
        "consumed_at_utc": utc_now(),
        "state": "CONSUMED",
        "run_limit": 1,
    }
    write_json(consumption_path, consumption, exclusive=True)
    workspace = run_dir / "model_workspace"
    if workspace.exists():
        existing = [path for path in workspace.rglob("*") if path.is_file()]
        if existing:
            raise TerminalError("MODEL_WORKSPACE_NOT_EMPTY_BEFORE_UNSEAL")
    source_copy = workspace / "private_inputs/source_bindings.json"
    question_copy = workspace / "private_inputs/question_set.json"
    _copy_verified_private(
        source=source_binding_path,
        destination=source_copy,
        expected_sha256=bundle["private_commitments"]["source_bindings_sha256"],
    )
    _copy_verified_private(
        source=question_set_path,
        destination=question_copy,
        expected_sha256=bundle["private_commitments"]["question_set_sha256"],
    )
    source_binding = load_json(source_copy)
    question_set = load_json(question_copy)
    catalogs = extract_catalogs(source_binding)
    question_cells = extract_question_cells(
        question_set,
        case_ids=[row["source_id"] for row in catalogs],
    )
    runtime_manifest = {
        "schema_version": "v02-r2-terminal-model-workspace-runtime.v1",
        "run_id": RUN_ID,
        "source_bindings_sha256": sha256_file(source_copy),
        "question_set_sha256": sha256_file(question_copy),
        "catalog_count": len(catalogs),
        "question_cell_count": len(question_cells),
        "gold_present": False,
        "forbidden_gold_file_count": sum(
            1
            for path in workspace.rglob("*")
            if path.is_file()
            and any(
                fragment in part.lower()
                for part in path.relative_to(workspace).parts
                for fragment in ("gold", "lockbox")
            )
        ),
    }
    if runtime_manifest["forbidden_gold_file_count"] != 0:
        raise TerminalError("MODEL_WORKSPACE_GOLD_PRESENT")
    runtime_manifest["manifest_payload_sha256"] = sha256_bytes(
        canonical_bytes(runtime_manifest)
    )
    write_json(workspace / "runtime_manifest.json", runtime_manifest)
    candidates = build_route_candidates(
        catalogs=catalogs,
        question_cells=question_cells,
    )
    attempt_ledger = run_dir / "execution/attempt_ledger.jsonl"
    answers_by_route: dict[str, list[dict[str, Any]]] = {
        route_id: [] for route_id in ROUTE_IDS
    }
    for route_id in ROUTE_IDS:
        for candidate in candidates[route_id]:
            logical_key = f"{RUN_ID}::{route_id}::{candidate['cell_id']}"
            request = model_request_payload(candidate)
            request_path = (
                run_dir
                / "execution/requests"
                / route_id
                / f"{candidate['cell_id'].replace('::', '__')}.json"
            )
            write_json(request_path, request, exclusive=True)
            request_sha = sha256_file(request_path)
            intent = {
                "schema_version": "v02-r2-terminal-attempt-ledger.v1",
                "at_utc": utc_now(),
                "logical_key": logical_key,
                "state": "INTENT_WRITTEN",
                "attempt": 1,
                "request_sha256": request_sha,
                "model_id": MODEL_ID,
                "profile": MODEL_PROFILE,
            }
            append_jsonl(attempt_ledger, intent)
            raw_path = (
                run_dir
                / "execution/raw_responses"
                / route_id
                / f"{candidate['cell_id'].replace('::', '__')}.json"
            )
            envelope: dict[str, Any] | None = None
            elapsed_ms = 0
            failure_code: str | None = None
            selection: dict[str, Any] = {
                "status": "ABSTAIN",
                "selected_source_ids": [],
            }
            try:
                envelope, elapsed_ms = invoke_model(
                    request_path=request_path,
                    raw_response_path=raw_path,
                )
                selection = parse_model_selection(
                    envelope,
                    allowed_source_ids={
                        row["source_id"]
                        for row in candidate["candidate_sentences"]
                    },
                )
            except (TerminalError, subprocess.TimeoutExpired) as exc:
                failure_code = type(exc).__name__
                if isinstance(exc, TerminalError):
                    failure_code = str(exc).split(":", 1)[0]
            raw_sha = sha256_file(raw_path) if raw_path.is_file() else None
            answer = render_answer(
                candidate=candidate,
                selection=selection,
                envelope=envelope,
                request_sha256=request_sha,
                raw_response_sha256=raw_sha,
                elapsed_ms=elapsed_ms,
                failure_code=failure_code,
            )
            answers_by_route[route_id].append(answer)
            append_jsonl(
                attempt_ledger,
                {
                    "schema_version": "v02-r2-terminal-attempt-ledger.v1",
                    "at_utc": utc_now(),
                    "logical_key": logical_key,
                    "state": "TERMINAL",
                    "attempt": 1,
                    "request_sha256": request_sha,
                    "raw_response_sha256": raw_sha,
                    "answer_payload_sha256": answer["answer_payload_sha256"],
                    "failure_code": failure_code,
                    "response_id": envelope.get("id") if envelope else None,
                    "response_model": envelope.get("model") if envelope else None,
                    "usage": answer["usage"],
                    "elapsed_ms": elapsed_ms,
                },
            )
        if len(answers_by_route[route_id]) != QUESTION_TOTAL:
            raise TerminalError(f"ROUTE_TERMINAL_COUNT_INVALID:{route_id}")
        route_output = {
            "schema_version": "v02-r2-terminal-route-output.v1",
            "run_id": RUN_ID,
            "route_id": route_id,
            "question_total": QUESTION_TOTAL,
            "answers": answers_by_route[route_id],
        }
        route_output["route_output_payload_sha256"] = sha256_bytes(
            canonical_bytes(route_output)
        )
        write_json(
            run_dir / f"sealed_outputs/{route_id}/answers.json",
            route_output,
            exclusive=True,
        )
    output_root = run_dir / "sealed_outputs"
    manifest = _freeze_manifest(output_root)
    write_json(
        output_root / "ALL_OUTPUTS_SEALED.json",
        manifest,
        exclusive=True,
    )
    for path in output_root.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    result = {
        "schema_version": "v02-r2-terminal-run-receipt.v1",
        "run_id": RUN_ID,
        "cycle_id": CYCLE_ID,
        "ticket_id": TICKET_ID,
        "status": "ALL_OUTPUTS_SEALED",
        "route_ids": list(ROUTE_IDS),
        "terminal_question_states_per_route": QUESTION_TOTAL,
        "model_api_logical_calls": QUESTION_TOTAL * len(ROUTE_IDS),
        "development_trial_runs": 0,
        "gold_opened": False,
        "output_manifest_sha256": sha256_file(
            output_root / "ALL_OUTPUTS_SEALED.json"
        ),
        "completed_at_utc": utc_now(),
    }
    result["receipt_payload_sha256"] = sha256_bytes(canonical_bytes(result))
    write_json(run_dir / "TERMINAL_RUN_RECEIPT.json", result, exclusive=True)
    return result


def _normalize_source_groups(value: Any) -> list[list[str]]:
    if not isinstance(value, list) or not value:
        return []
    if all(isinstance(item, str) and item for item in value):
        return [list(value)]
    groups: list[list[str]] = []
    for item in value:
        if isinstance(item, list) and item and all(
            isinstance(source_id, str) and source_id for source_id in item
        ):
            groups.append(list(item))
        elif isinstance(item, Mapping):
            nested = item.get("source_ids", item.get("sources"))
            groups.extend(_normalize_source_groups(nested))
    return groups


def _head_id(node: Mapping[str, Any]) -> str | None:
    for key in ("head_id", "part_id", "required_head_id", "id"):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def extract_gold_cells(gold_binding: Any) -> list[dict[str, Any]]:
    head_catalog: dict[str, list[list[str]]] = {}
    ambiguous_head_ids: set[str] = set()
    for node in iter_nodes(gold_binding):
        groups = _normalize_source_groups(node.get("source_id_groups"))
        identifier = _head_id(node)
        if identifier and groups:
            if identifier in ambiguous_head_ids:
                continue
            existing = head_catalog.setdefault(identifier, groups)
            if existing != groups:
                head_catalog.pop(identifier, None)
                ambiguous_head_ids.add(identifier)
    cells: list[dict[str, Any]] = []
    for node in iter_nodes(gold_binding):
        question_id = node.get("question_id")
        if not isinstance(question_id, str) or not question_id:
            continue
        case_id = node.get("case_id", node.get("source_id"))
        cell_id = node.get("cell_id")
        if not isinstance(case_id, str) and isinstance(cell_id, str) and "::" in cell_id:
            case_id = cell_id.split("::", 1)[0]
        if not isinstance(case_id, str) or not case_id:
            continue
        required_heads: list[dict[str, Any]] = []
        seen: set[str] = set()
        for child in iter_nodes(node):
            identifier = _head_id(child)
            groups = _normalize_source_groups(child.get("source_id_groups"))
            if identifier and groups and identifier not in seen:
                required_heads.append(
                    {"head_id": identifier, "source_id_groups": groups}
                )
                seen.add(identifier)
        referenced_ids: list[str] = []
        for key in ("required_head_ids", "required_heads", "head_ids"):
            value = node.get(key)
            if isinstance(value, list):
                referenced_ids.extend(
                    item
                    for item in value
                    if isinstance(item, str) and item in head_catalog
                )
        for identifier in referenced_ids:
            if identifier not in seen:
                required_heads.append(
                    {
                        "head_id": identifier,
                        "source_id_groups": head_catalog[identifier],
                    }
                )
                seen.add(identifier)
        if not required_heads:
            continue
        cells.append(
            {
                "cell_id": f"{case_id}::{question_id}",
                "case_id": case_id,
                "question_id": question_id,
                "answerability": node.get("answerability", "ANSWERABLE"),
                "required_heads": sorted(
                    required_heads,
                    key=lambda row: row["head_id"],
                ),
            }
        )
    unique: dict[str, dict[str, Any]] = {}
    for cell in cells:
        key = cell["cell_id"]
        if key in unique and unique[key] != cell:
            if len(cell["required_heads"]) > len(unique[key]["required_heads"]):
                unique[key] = cell
        else:
            unique[key] = cell
    if len(unique) != QUESTION_TOTAL:
        raise TerminalError(f"GOLD_CELL_COUNT_INVALID:{len(unique)}")
    return [unique[key] for key in sorted(unique)]


def score_answer(
    *,
    answer: Mapping[str, Any],
    gold: Mapping[str, Any],
) -> dict[str, Any]:
    claims = answer.get("claims", [])
    selected_equivalents: set[str] = set()
    selected_primary: list[str] = []
    for claim in claims:
        source_id = claim["source_id"]
        selected_primary.append(source_id)
        selected_equivalents.update(claim.get("source_id_aliases", [source_id]))
    head_results = []
    allowed_sources: set[str] = set()
    for head in gold["required_heads"]:
        groups = [set(group) for group in head["source_id_groups"]]
        for group in groups:
            allowed_sources.update(group)
        covered = any(group <= selected_equivalents for group in groups)
        head_results.append(
            {
                "head_id": head["head_id"],
                "covered": covered,
            }
        )
    answerability = gold.get("answerability", "ANSWERABLE")
    status = answer.get("status")
    full_supported = (
        answerability == "ANSWERABLE"
        and status == "ANSWER"
        and bool(head_results)
        and all(row["covered"] for row in head_results)
    )
    selected_outside_gold = sorted(selected_equivalents - allowed_sources)
    critical_error_codes: list[str] = []
    if selected_outside_gold:
        critical_error_codes.append("UNSUPPORTED_EXTRA_CLAIM")
    if answerability in {"UNANSWERABLE", "FALSE_PREMISE"} and status == "ANSWER":
        if not all(row["covered"] for row in head_results):
            critical_error_codes.append("FALSE_PREMISE_ACCEPTED")
    if status == "FAILED":
        result = "TRANSPORT_OR_SCHEMA_FAILURE"
    elif full_supported:
        result = "FULL_SUPPORTED"
    elif status == "ABSTAIN" and answerability != "ANSWERABLE":
        result = "CORRECT_ABSTAIN"
    elif status == "ABSTAIN":
        result = "WRONG_ABSTAIN"
    elif critical_error_codes:
        result = critical_error_codes[0]
    else:
        result = "PARTIAL_SUPPORTED"
    return {
        "cell_id": gold["cell_id"],
        "question_id": gold["question_id"],
        "result": result,
        "full_supported": full_supported,
        "critical_error": bool(critical_error_codes),
        "critical_error_codes": sorted(set(critical_error_codes)),
        "required_head_count": len(head_results),
        "covered_head_count": sum(row["covered"] for row in head_results),
        "head_results": head_results,
        "selected_source_ids": selected_primary,
        "selected_source_id_outside_gold": selected_outside_gold,
        "answer_payload_sha256": answer["answer_payload_sha256"],
        "cost": answer["cost"],
        "usage": answer["usage"],
    }


def score_terminal(
    *,
    run_dir: Path,
    authority_path: Path,
    gold_binding_path: Path,
) -> dict[str, Any]:
    authority, bundle = _assert_control_authority(
        run_dir=run_dir,
        authority_path=authority_path,
        stage="score",
    )
    _assert_exact_authorized_path(
        authority,
        label="gold_binding",
        path=gold_binding_path,
    )
    sealed_manifest_path = run_dir / "sealed_outputs/ALL_OUTPUTS_SEALED.json"
    if not sealed_manifest_path.is_file():
        raise TerminalError("ALL_OUTPUTS_NOT_SEALED")
    manifest = load_json(sealed_manifest_path)
    for record in manifest["files"]:
        path = run_dir / "sealed_outputs" / record["path"]
        if not path.is_file() or sha256_file(path) != record["sha256"]:
            raise TerminalError(f"SEALED_OUTPUT_DRIFT:{record['path']}")
    score_counter_path = run_dir / "scoring/score_counter.json"
    if score_counter_path.exists():
        raise TerminalError("TERMINAL_SCORE_ALREADY_USED")
    if sha256_file(gold_binding_path) != bundle["private_commitments"][
        "gold_binding_sha256"
    ]:
        raise TerminalError("GOLD_BINDING_SHA_MISMATCH")
    write_json(
        score_counter_path,
        {
            "schema_version": "v02-r2-terminal-score-counter.v1",
            "run_id": RUN_ID,
            "before": 0,
            "after": 1,
            "scoring_started_at_utc": utc_now(),
        },
        exclusive=True,
    )
    gold = load_json(gold_binding_path)
    gold_cells = extract_gold_cells(gold)
    gold_by_key = {row["cell_id"]: row for row in gold_cells}
    route_scorecards = []
    per_question_rows = []
    for route_id in ROUTE_IDS:
        route_output_path = run_dir / f"sealed_outputs/{route_id}/answers.json"
        route_output = load_json(route_output_path)
        answers = route_output["answers"]
        if len(answers) != QUESTION_TOTAL:
            raise TerminalError(f"SCORE_ROUTE_ANSWER_COUNT_INVALID:{route_id}")
        rows = []
        for answer in answers:
            key = answer["cell_id"]
            if key not in gold_by_key:
                raise TerminalError(f"SCORE_GOLD_CELL_MISSING:{key}")
            row = score_answer(answer=answer, gold=gold_by_key[key])
            row["route_id"] = route_id
            rows.append(row)
            per_question_rows.append(row)
        full_supported = sum(row["full_supported"] for row in rows)
        critical_errors = sum(row["critical_error"] for row in rows)
        total_tokens = sum(
            int(row["usage"].get("total_tokens") or 0) for row in rows
        )
        elapsed_ms = sum(int(row["cost"]["model_elapsed_ms"]) for row in rows)
        scorecard = {
            "route_id": route_id,
            "question_total": QUESTION_TOTAL,
            "full_supported_count": full_supported,
            "critical_error_count": critical_errors,
            "gate": {
                "full_supported_minimum": 15,
                "critical_error_maximum": 10,
            },
            "passed": full_supported >= 15 and critical_errors <= 10,
            "cost": {
                "logical_model_calls": QUESTION_TOTAL,
                "total_tokens_known": total_tokens,
                "total_model_elapsed_ms": elapsed_ms,
                "mean_tokens_per_question": round(
                    total_tokens / QUESTION_TOTAL, 2
                ),
                "mean_model_elapsed_ms_per_question": round(
                    elapsed_ms / QUESTION_TOTAL, 2
                ),
            },
        }
        route_scorecards.append(scorecard)
    scorecard = {
        "schema_version": "v02-r2-terminal-scorecard.v1",
        "ticket_id": TICKET_ID,
        "cycle_id": CYCLE_ID,
        "run_id": RUN_ID,
        "terminal_question_set_sha256": bundle["private_commitments"][
            "question_set_sha256"
        ],
        "gold_binding_sha256": bundle["private_commitments"][
            "gold_binding_sha256"
        ],
        "route_scorecards": route_scorecards,
        "per_question_rows": per_question_rows,
        "score_run_count": 1,
        "model_api_reruns": 0,
        "completed_at_utc": utc_now(),
    }
    scorecard["scorecard_payload_sha256"] = sha256_bytes(
        canonical_bytes(scorecard)
    )
    write_json(
        run_dir / "scoring/TERMINAL_SCORECARD.json",
        scorecard,
        exclusive=True,
    )
    return scorecard


def synthetic_catalog(case_id: str) -> dict[str, Any]:
    paragraphs = []
    sentences = []
    source_text = ""
    for index in range(1, 13):
        text = f"{case_id}人物在地点{index}完成事件{index}，因此状态发生变化。\n"
        start = len(source_text)
        source_text += text
        paragraph_id = f"{case_id}-P{index:04d}"
        sentence_id = f"{case_id}-S{index:04d}"
        paragraphs.append(
            {
                "paragraph_id": paragraph_id,
                "char_start": start,
                "char_end_exclusive": len(source_text),
                "original_text": text,
            }
        )
        sentences.append(
            {
                "sentence_id": sentence_id,
                "paragraph_id": paragraph_id,
                "char_start": start,
                "char_end_exclusive": len(source_text),
                "original_text": text,
                "accepted_legacy_source_ids": [],
            }
        )
    catalog = {
        "source_id": case_id,
        "source_text": source_text,
        "source_body_sha256": sha256_bytes(source_text.encode("utf-8")),
        "paragraphs": paragraphs,
        "sentences": sentences,
    }
    catalog["catalog_payload_sha256"] = sha256_bytes(canonical_bytes(catalog))
    return catalog


def zero_api_preflight(output_dir: Path) -> dict[str, Any]:
    catalogs = [synthetic_catalog(f"SYN-{index:02d}") for index in range(1, 4)]
    question_set = {
        "questions": [
            {
                "question_id": f"Q{index:02d}",
                "question_text": "主角当前在哪里，处于什么状态？"
                if index == 1
                else "本章发生了哪些会影响后续的状态变化？",
            }
            for index in range(1, 11)
        ]
    }
    cells = extract_question_cells(
        question_set,
        case_ids=[row["source_id"] for row in catalogs],
    )
    candidates = build_route_candidates(catalogs=catalogs, question_cells=cells)
    sample = candidates["A5"][0]
    request = model_request_payload(sample)
    chosen = sample["candidate_sentences"][0]["source_id"]
    envelope = {
        "id": "synthetic-response",
        "model": EXPECTED_RESPONSE_MODEL,
        "content": json.dumps(
            {"status": "ANSWER", "selected_source_ids": [chosen]},
            ensure_ascii=False,
        ),
        "usage": {
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
        },
    }
    selection = parse_model_selection(
        envelope,
        allowed_source_ids={
            row["source_id"] for row in sample["candidate_sentences"]
        },
    )
    answer = render_answer(
        candidate=sample,
        selection=selection,
        envelope=envelope,
        request_sha256=sha256_bytes(canonical_bytes(request)),
        raw_response_sha256=sha256_bytes(canonical_bytes(envelope)),
        elapsed_ms=1,
        failure_code=None,
    )
    gold_binding = {
        "cells": [
            {
                "case_id": case_id,
                "question_id": f"Q{index:02d}",
                "answerability": "ANSWERABLE",
                "required_heads": [
                    {
                        "head_id": f"H-{index:02d}",
                        "source_id_groups": [[f"{case_id}-S0001"]],
                    }
                ],
            }
            for case_id in (row["source_id"] for row in catalogs)
            for index in range(1, 11)
        ]
    }
    gold_cells = extract_gold_cells(gold_binding)
    score = score_answer(
        answer=answer,
        gold={
            **gold_cells[0],
            "cell_id": answer["cell_id"],
            "question_id": answer["question_id"],
        },
    )
    result = {
        "schema_version": "v02-r2-terminal-zero-api-preflight.v1",
        "status": "PASS",
        "catalog_count": len(catalogs),
        "question_cell_count": len(cells),
        "route_counts": {
            route_id: len(rows) for route_id, rows in candidates.items()
        },
        "request_schema_pass": bool(request["evidence"]),
        "selection_schema_pass": selection["status"] == "ANSWER",
        "program_backfill_pass": bool(answer["claims"]),
        "gold_adapter_cell_count": len(gold_cells),
        "score_adapter_result": score["result"],
        "model_api_calls": 0,
        "network_requests": 0,
        "terminal_private_files_read": 0,
    }
    result["receipt_payload_sha256"] = sha256_bytes(canonical_bytes(result))
    write_json(output_dir / "ZERO_API_PREFLIGHT_RECEIPT.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("zero-api-preflight")
    preflight.add_argument("--output-dir", type=Path, required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--run-dir", type=Path, required=True)
    run.add_argument("--authority", type=Path, required=True)
    run.add_argument("--source-bindings", type=Path, required=True)
    run.add_argument("--question-set", type=Path, required=True)
    score = subparsers.add_parser("score")
    score.add_argument("--run-dir", type=Path, required=True)
    score.add_argument("--authority", type=Path, required=True)
    score.add_argument("--gold-binding", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "zero-api-preflight":
        result = zero_api_preflight(args.output_dir.resolve())
    elif args.command == "run":
        result = run_terminal(
            run_dir=args.run_dir.resolve(),
            authority_path=args.authority.resolve(),
            source_binding_path=args.source_bindings.resolve(),
            question_set_path=args.question_set.resolve(),
        )
    elif args.command == "score":
        result = score_terminal(
            run_dir=args.run_dir.resolve(),
            authority_path=args.authority.resolve(),
            gold_binding_path=args.gold_binding.resolve(),
        )
    else:
        raise TerminalError(f"COMMAND_UNKNOWN:{args.command}")
    print(
        json.dumps(
            {
                "status": result.get("status", "PASS"),
                "schema_version": result["schema_version"],
                "receipt_payload_sha256": result.get(
                    "receipt_payload_sha256",
                    result.get("scorecard_payload_sha256"),
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

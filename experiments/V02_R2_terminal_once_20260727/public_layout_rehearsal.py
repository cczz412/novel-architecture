from __future__ import annotations

import argparse
import copy
import json
import os
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from experiments.V02_R2_terminal_once_20260727 import (
    terminal_controller as terminal,
)


SCHEMA_VERSION = "v02-r2-terminal-public-layout-rehearsal.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_REHEARSAL_SEMANTIC_STUBS = (
    "【公开合成占位】主角当前在哪里，处于什么状态？",
    "【公开合成占位】发生了哪些影响后续的状态变化？",
    "【公开合成占位】人物新知道了什么？",
    "【公开合成占位】人物仍不知道什么，又误信了什么？",
    "【公开合成占位】有哪些目标、计划、承诺与威胁？",
    "【公开合成占位】关系、身份与归属发生了什么变化？",
    "【公开合成占位】资源、物品、位置、能力发生了什么转移？",
    "【公开合成占位】有哪些未决事项、风险与伏笔？",
    "【公开合成占位】有哪些因果触发？",
    "【公开合成占位】人物相信、猜测、听说了什么，世界事实是什么？",
)


class PublicRehearsalError(terminal.TerminalError):
    """公开布局彩排拒收错误。"""


def _reject(code: str) -> None:
    raise PublicRehearsalError(code)


def _expect(condition: bool, code: str) -> None:
    if not condition:
        _reject(code)


def _as_mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _reject(code)
    return value


def _resolve_public_path(
    recorded: str | Path,
    *,
    project_root: Path,
    code: str,
) -> Path:
    raw = str(recorded)
    _expect(bool(raw) and "\x00" not in raw and "\\" not in raw, code)
    pure = PurePosixPath(raw)
    _expect(
        not pure.is_absolute()
        and bool(pure.parts)
        and all(part not in {"", ".", ".."} for part in pure.parts)
        and all(
            part.lower() != "sealed" and "private" not in part.lower()
            for part in pure.parts
        ),
        code,
    )
    path = project_root.joinpath(*pure.parts)
    current = project_root
    _expect(not stat.S_ISLNK(os.lstat(current).st_mode), code)
    for part in pure.parts:
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except OSError as exc:
            raise PublicRehearsalError(code) from exc
        _expect(not stat.S_ISLNK(mode), code)
    _expect(path.is_file(), code)
    return path


def _validate_contract(
    *,
    contract: Mapping[str, Any],
    contract_path: Path,
    ticket: Mapping[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    public_contract = _as_mapping(
        ticket.get("public_layout_contract"),
        "TICKET_PUBLIC_CONTRACT_MISSING",
    )
    _expect(
        public_contract.get("contract_path")
        and _resolve_public_path(
            str(public_contract["contract_path"]),
            project_root=project_root,
            code="TICKET_CONTRACT_PUBLIC_PATH_INVALID",
        )
        == contract_path.resolve(),
        "TICKET_CONTRACT_PATH_MISMATCH",
    )
    contract_sha = terminal.sha256_file(contract_path)
    _expect(
        public_contract.get("contract_sha256") == contract_sha,
        "TICKET_CONTRACT_SHA_MISMATCH",
    )
    _expect(
        contract.get("contract_id") == public_contract.get("contract_id"),
        "CONTRACT_ID_MISMATCH",
    )
    _expect(
        contract.get("layout_mode") == "generic_10x3",
        "CONTRACT_LAYOUT_MODE_INVALID",
    )
    consumer = _as_mapping(
        contract.get("consumer"),
        "CONTRACT_CONSUMER_MISSING",
    )
    _expect(
        consumer.get("parser_path") == public_contract.get("parser_path"),
        "CONTRACT_PARSER_PATH_MISMATCH",
    )
    parser_path = _resolve_public_path(
        str(consumer.get("parser_path", "")),
        project_root=project_root,
        code="CONTRACT_PARSER_PUBLIC_PATH_INVALID",
    )
    _expect(
        parser_path == Path(terminal.__file__).resolve(),
        "CONTRACT_PARSER_TARGET_MISMATCH",
    )
    parser_sha = terminal.sha256_file(parser_path)
    _expect(
        parser_sha
        == consumer.get("parser_sha256")
        == public_contract.get("parser_sha256"),
        "CONTRACT_PARSER_SHA_MISMATCH",
    )
    _expect(
        consumer.get("function") == "extract_question_cells",
        "CONTRACT_PARSER_FUNCTION_INVALID",
    )
    case_ids = consumer.get("synthetic_case_ids")
    _expect(
        isinstance(case_ids, list)
        and len(case_ids) == 3
        and len(set(case_ids)) == 3
        and all(isinstance(item, str) and item for item in case_ids),
        "CONTRACT_SYNTHETIC_CASE_IDS_INVALID",
    )
    _expect(
        consumer.get("expected_expanded_cell_total") == 30,
        "CONTRACT_EXPANDED_CELL_TOTAL_INVALID",
    )
    _expect(
        consumer.get("expected_cells_per_case") == 10,
        "CONTRACT_CELLS_PER_CASE_INVALID",
    )
    rehearsal = _as_mapping(
        contract.get("required_public_rehearsal"),
        "CONTRACT_REHEARSAL_GATE_MISSING",
    )
    _expect(
        rehearsal.get("model_api_calls") == 0
        and rehearsal.get("network_requests") == 0
        and rehearsal.get("private_terminal_files_read") == 0
        and rehearsal.get("expected_generic_row_total") == 10
        and rehearsal.get("expected_explicit_row_total") == 0
        and rehearsal.get("expected_expanded_cell_total") == 30
        and rehearsal.get("wrong_layout_rejection_required") is True,
        "CONTRACT_REHEARSAL_GATE_INVALID",
    )
    return {
        "contract_id": contract["contract_id"],
        "contract_sha256": contract_sha,
        "parser_path": str(parser_path),
        "parser_sha256": parser_sha,
        "parser_function": consumer["function"],
        "case_ids": list(case_ids),
    }


def _scan_forbidden_nodes(
    value: Any,
    *,
    question_row_ids: set[int],
) -> None:
    if isinstance(value, Mapping):
        for key in value:
            lowered = str(key).lower()
            if key == "case_id":
                _reject("SAMPLE_FORBIDDEN_CASE_ID")
            if key == "source_id":
                _reject("SAMPLE_FORBIDDEN_SOURCE_ID")
            if "gold" in lowered:
                _reject("SAMPLE_FORBIDDEN_GOLD_FIELD")
        if id(value) not in question_row_ids and any(
            key in value for key in ("question_id", "question_text", "answer_rule")
        ):
            _reject("SAMPLE_NESTED_QUESTION_NODE")
        for child in value.values():
            _scan_forbidden_nodes(
                child,
                question_row_ids=question_row_ids,
            )
    elif isinstance(value, list):
        for child in value:
            _scan_forbidden_nodes(
                child,
                question_row_ids=question_row_ids,
            )


def validate_public_sample(
    *,
    sample: Any,
    contract: Mapping[str, Any],
    contract_sha256: str,
) -> dict[str, Any]:
    sample = _as_mapping(sample, "SAMPLE_NOT_OBJECT")
    questions = sample.get("questions")
    _expect(isinstance(questions, list), "SAMPLE_QUESTIONS_NOT_LIST")
    question_row_ids = {id(row) for row in questions if isinstance(row, Mapping)}
    _scan_forbidden_nodes(
        sample,
        question_row_ids=question_row_ids,
    )

    schema = _as_mapping(
        contract.get("question_set_schema"),
        "CONTRACT_QUESTION_SCHEMA_MISSING",
    )
    exact_top_keys = schema.get("top_level_exact_keys")
    _expect(
        isinstance(exact_top_keys, list) and set(sample) == set(exact_top_keys),
        "SAMPLE_TOP_LEVEL_KEYS_INVALID",
    )
    constants = _as_mapping(
        schema.get("top_level_constants"),
        "CONTRACT_TOP_LEVEL_CONSTANTS_MISSING",
    )
    for key, expected in constants.items():
        _expect(
            sample.get(key) == expected,
            f"SAMPLE_TOP_LEVEL_CONSTANT_MISMATCH:{key}",
        )
    _expect(
        sample.get("layout_contract_sha256") == contract_sha256,
        "SAMPLE_CONTRACT_SHA_MISMATCH",
    )
    allowed_roles = schema.get("artifact_role_allowed_values")
    _expect(
        isinstance(allowed_roles, list)
        and sample.get("artifact_role") == "PUBLIC_SYNTHETIC_SAMPLE"
        and sample.get("artifact_role") in allowed_roles,
        "SAMPLE_ARTIFACT_ROLE_INVALID",
    )
    _expect(
        sample.get("model_visible_only_after_authorized_unseal") is False,
        "SAMPLE_MODEL_VISIBILITY_FLAG_INVALID",
    )

    expected_length = schema.get("questions_exact_length")
    _expect(
        len(questions) == expected_length == 10,
        "SAMPLE_QUESTION_COUNT_INVALID",
    )
    exact_row_keys = schema.get("question_row_exact_keys")
    _expect(
        isinstance(exact_row_keys, list),
        "CONTRACT_ROW_KEYS_INVALID",
    )
    pattern_text = schema.get("question_id_pattern")
    _expect(isinstance(pattern_text, str), "CONTRACT_ID_PATTERN_INVALID")
    pattern = re.compile(pattern_text)
    ids: list[str] = []
    for index, row in enumerate(questions):
        _expect(
            isinstance(row, Mapping),
            f"SAMPLE_QUESTION_ROW_NOT_OBJECT:{index}",
        )
        _expect(
            set(row) == set(exact_row_keys),
            f"SAMPLE_QUESTION_ROW_KEYS_INVALID:{index}",
        )
        question_id = row.get("question_id")
        _expect(
            isinstance(question_id, str) and pattern.fullmatch(question_id),
            f"SAMPLE_QUESTION_ID_INVALID:{index}",
        )
        for key in ("question_text", "answer_rule"):
            value = row.get(key)
            _expect(
                isinstance(value, str) and bool(value.strip()),
                f"SAMPLE_QUESTION_TEXT_FIELD_EMPTY:{index}:{key}",
            )
        ids.append(question_id)
    _expect(len(ids) == len(set(ids)), "SAMPLE_QUESTION_ID_DUPLICATED")
    _expect(ids == sorted(ids), "SAMPLE_QUESTION_ID_NOT_SORTED")

    payload = dict(sample)
    payload.pop("question_set_payload_sha256", None)
    payload_sha = terminal.sha256_bytes(terminal.canonical_bytes(payload))
    _expect(
        sample.get("question_set_payload_sha256") == payload_sha,
        "SAMPLE_PAYLOAD_SHA_MISMATCH",
    )
    return {
        "sample_payload_sha256": payload_sha,
        "generic_question_row_total": len(questions),
        "explicit_question_row_total": 0,
    }


def _validate_ticket(
    *,
    ticket: Mapping[str, Any],
    ticket_path: Path,
    sample_path: Path,
    expected_ticket_id: str,
    project_root: Path,
) -> dict[str, Any]:
    _expect(
        isinstance(expected_ticket_id, str)
        and bool(expected_ticket_id.strip())
        and ticket.get("ticket_id") == expected_ticket_id,
        "TICKET_ID_INVALID",
    )
    _expect(
        ticket.get("status")
        == "SEALED_AWAITING_MAINLINE1_PUBLIC_REHEARSAL_AND_NEW_AUTHORITY",
        "TICKET_STATUS_INVALID",
    )
    public_sample = _as_mapping(
        ticket.get("public_fake_sample"),
        "TICKET_PUBLIC_SAMPLE_MISSING",
    )
    _expect(
        public_sample.get("path")
        and _resolve_public_path(
            str(public_sample["path"]),
            project_root=project_root,
            code="TICKET_SAMPLE_PUBLIC_PATH_INVALID",
        )
        == sample_path.resolve(),
        "TICKET_SAMPLE_PATH_MISMATCH",
    )
    sample_sha = terminal.sha256_file(sample_path)
    _expect(
        public_sample.get("sha256") == sample_sha,
        "TICKET_SAMPLE_SHA_MISMATCH",
    )
    _expect(
        public_sample.get("real_source_or_chapter_id_count") == 0
        and public_sample.get("real_question_surface_count") == 0
        and public_sample.get("gold_field_count") == 0,
        "TICKET_SAMPLE_SAFETY_INVALID",
    )
    gate = _as_mapping(
        ticket.get("remaining_terminal_gate"),
        "TICKET_REMAINING_GATE_MISSING",
    )
    _expect(
        gate.get("mainline1_public_rehearsal_passed") is False
        and gate.get("new_mainline1_authority_ticket_issued") is False
        and gate.get("new_cycle_created") is False
        and gate.get("new_run_id_created") is False
        and gate.get("one_time_terminal_run_allowed") is False,
        "TICKET_PRE_REHEARSAL_GATE_ALREADY_OPEN",
    )
    zero_use = _as_mapping(
        ticket.get("zero_use_attestation"),
        "TICKET_ZERO_USE_ATTESTATION_MISSING",
    )
    _expect(
        all(
            zero_use.get(key) == 0
            for key in (
                "model_api_calls",
                "network_requests",
                "development_trial_runs",
                "terminal_requests",
                "terminal_runs",
                "score_runs",
            )
        ),
        "TICKET_ZERO_USE_ATTESTATION_INVALID",
    )
    return {
        "ticket_id": ticket["ticket_id"],
        "ticket_sha256": terminal.sha256_file(ticket_path),
        "sample_sha256": sample_sha,
    }


def _mutate_delete_top(value: dict[str, Any]) -> None:
    del value["schema_version"]


def _mutate_add_top(value: dict[str, Any]) -> None:
    value["unexpected"] = True


def _mutate_delete_row(value: dict[str, Any]) -> None:
    del value["questions"][0]["answer_rule"]


def _mutate_add_row(value: dict[str, Any]) -> None:
    value["questions"][0]["unexpected"] = True


def _mutate_duplicate_id(value: dict[str, Any]) -> None:
    value["questions"][1]["question_id"] = value["questions"][0]["question_id"]


def _mutate_unsorted(value: dict[str, Any]) -> None:
    value["questions"][0], value["questions"][1] = (
        value["questions"][1],
        value["questions"][0],
    )


def _mutate_nested_question(value: dict[str, Any]) -> None:
    value["metadata"] = {"question_id": "NESTED-Q01"}


def run_negative_suite(
    *,
    sample: Mapping[str, Any],
    contract: Mapping[str, Any],
    contract_sha256: str,
    case_ids: Sequence[str],
) -> list[dict[str, str]]:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("case_count_mismatch", lambda value: value.__setitem__("case_count", 2)),
        ("question_count_nine", lambda value: value["questions"].pop()),
        ("top_level_key_missing", _mutate_delete_top),
        ("top_level_key_extra", _mutate_add_top),
        ("row_key_missing", _mutate_delete_row),
        ("row_key_extra", _mutate_add_row),
        (
            "question_id_pattern_invalid",
            lambda value: value["questions"][0].__setitem__(
                "question_id",
                "bad-id",
            ),
        ),
        ("question_id_duplicated", _mutate_duplicate_id),
        ("question_id_unsorted", _mutate_unsorted),
        (
            "question_text_empty",
            lambda value: value["questions"][0].__setitem__(
                "question_text",
                " ",
            ),
        ),
        (
            "answer_rule_empty",
            lambda value: value["questions"][0].__setitem__(
                "answer_rule",
                "",
            ),
        ),
        (
            "forbidden_case_id",
            lambda value: value["questions"][0].__setitem__(
                "case_id",
                case_ids[0],
            ),
        ),
        (
            "forbidden_source_id",
            lambda value: value.__setitem__("source_id", "PRIVATE"),
        ),
        (
            "forbidden_gold_field",
            lambda value: value.__setitem__("gold_answers", []),
        ),
        ("nested_question_node", _mutate_nested_question),
        (
            "layout_mode_mismatch",
            lambda value: value.__setitem__("layout_mode", "explicit_30"),
        ),
        (
            "contract_id_mismatch",
            lambda value: value.__setitem__(
                "layout_contract_id",
                "OTHER-CONTRACT",
            ),
        ),
        (
            "contract_sha_mismatch",
            lambda value: value.__setitem__(
                "layout_contract_sha256",
                "0" * 64,
            ),
        ),
        (
            "schema_version_mismatch",
            lambda value: value.__setitem__(
                "schema_version",
                "wrong.schema",
            ),
        ),
        (
            "payload_sha_mismatch",
            lambda value: value["questions"][0].__setitem__(
                "question_text",
                value["questions"][0]["question_text"] + "变更",
            ),
        ),
    ]
    results: list[dict[str, str]] = []
    for name, mutate in mutations:
        changed = copy.deepcopy(sample)
        mutate(changed)
        try:
            validate_public_sample(
                sample=changed,
                contract=contract,
                contract_sha256=contract_sha256,
            )
        except PublicRehearsalError as exc:
            results.append(
                {
                    "case": name,
                    "status": "REJECTED",
                    "code": str(exc).split(":", 1)[0],
                }
            )
        else:
            _reject(f"NEGATIVE_CASE_NOT_REJECTED:{name}")

    explicit = copy.deepcopy(sample)
    explicit["questions"][0]["case_id"] = case_ids[0]
    try:
        terminal.extract_question_cells(explicit, case_ids=case_ids)
    except terminal.TerminalError as exc:
        _expect(
            str(exc).startswith("QUESTION_LAYOUT_INVALID"),
            "PARSER_WRONG_LAYOUT_REJECTION_CODE_INVALID",
        )
        results.append(
            {
                "case": "parser_mixed_explicit_generic_layout",
                "status": "REJECTED",
                "code": "QUESTION_LAYOUT_INVALID",
            }
        )
    else:
        _reject("PARSER_WRONG_LAYOUT_NOT_REJECTED")
    return results


def _run_offline_pipeline(
    *,
    sample: Mapping[str, Any],
    case_ids: Sequence[str],
) -> dict[str, Any]:
    catalogs = [terminal.synthetic_catalog(case_id) for case_id in case_ids]
    cells = terminal.extract_question_cells(sample, case_ids=case_ids)
    per_case = {
        case_id: sum(row["case_id"] == case_id for row in cells) for case_id in case_ids
    }
    _expect(len(cells) == 30, "PIPELINE_CELL_COUNT_INVALID")
    _expect(
        set(per_case.values()) == {10},
        "PIPELINE_PER_CASE_COUNT_INVALID",
    )
    question_ids = sorted({row["question_id"] for row in cells})
    _expect(
        len(question_ids) == len(PUBLIC_REHEARSAL_SEMANTIC_STUBS) == 10,
        "PIPELINE_SEMANTIC_STUB_COUNT_INVALID",
    )
    stub_by_question_id = dict(
        zip(
            question_ids,
            PUBLIC_REHEARSAL_SEMANTIC_STUBS,
            strict=True,
        )
    )
    adapted_cells = [
        {
            **cell,
            "question_text": stub_by_question_id[cell["question_id"]],
        }
        for cell in cells
    ]
    candidates = terminal.build_route_candidates(
        catalogs=catalogs,
        question_cells=adapted_cells,
    )
    gold_binding = {
        "cells": [
            {
                "case_id": cell["case_id"],
                "question_id": cell["question_id"],
                "answerability": "UNANSWERABLE",
                "required_heads": [
                    {
                        "head_id": (f"FAKE-{cell['case_id']}-{cell['question_id']}"),
                        "source_id_groups": [[f"{cell['case_id']}-S0001"]],
                    }
                ],
            }
            for cell in cells
        ]
    }
    gold_cells = terminal.extract_gold_cells(gold_binding)
    gold_by_cell = {row["cell_id"]: row for row in gold_cells}
    route_summaries: list[dict[str, Any]] = []
    total_requests = 0
    total_answers = 0
    total_score_rows = 0
    for route_id in terminal.ROUTE_IDS:
        route_answers: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidates[route_id], start=1):
            request = terminal.model_request_payload(candidate)
            envelope = {
                "id": f"public-rehearsal-{route_id}-{index:03d}",
                "model": terminal.EXPECTED_RESPONSE_MODEL,
                "content": json.dumps(
                    {
                        "status": "ABSTAIN",
                        "selected_source_ids": [],
                    },
                    ensure_ascii=False,
                ),
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
            selection = terminal.parse_model_selection(
                envelope,
                allowed_source_ids={
                    row["source_id"] for row in candidate["candidate_sentences"]
                },
            )
            answer = terminal.render_answer(
                candidate=candidate,
                selection=selection,
                envelope=envelope,
                request_sha256=terminal.sha256_bytes(terminal.canonical_bytes(request)),
                raw_response_sha256=terminal.sha256_bytes(
                    terminal.canonical_bytes(envelope)
                ),
                elapsed_ms=0,
                failure_code=None,
            )
            route_answers.append(answer)
            total_requests += 1
        score_rows = [
            terminal.score_answer(
                answer=answer,
                gold=gold_by_cell[answer["cell_id"]],
            )
            for answer in route_answers
        ]
        _expect(
            len(route_answers) == len(score_rows) == 30,
            f"PIPELINE_ROUTE_COUNT_INVALID:{route_id}",
        )
        _expect(
            all(row["result"] == "CORRECT_ABSTAIN" for row in score_rows),
            f"PIPELINE_SYNTHETIC_SCORE_INVALID:{route_id}",
        )
        route_summaries.append(
            {
                "route_id": route_id,
                "candidate_cell_count": len(candidates[route_id]),
                "request_adapter_count": len(route_answers),
                "answer_adapter_count": len(route_answers),
                "score_row_count": len(score_rows),
                "correct_synthetic_abstain_count": sum(
                    row["result"] == "CORRECT_ABSTAIN" for row in score_rows
                ),
                "critical_error_count": sum(
                    row["critical_error"] for row in score_rows
                ),
                "semantic_quality_gate_evaluated": False,
            }
        )
        total_answers += len(route_answers)
        total_score_rows += len(score_rows)
    return {
        "catalog_count": len(catalogs),
        "generic_question_row_total": 10,
        "explicit_question_row_total": 0,
        "expanded_question_cell_total": len(cells),
        "per_case_cell_count": per_case,
        "gold_adapter_cell_count": len(gold_cells),
        "public_rehearsal_semantic_stub_adapter": {
            "enabled": True,
            "scope": "PUBLIC_ZERO_API_REHEARSAL_ONLY",
            "reason": (
                "公开假题不对应开发集语义槽；仅替换离线规划文本，"
                "保留题号、格数和顺序，不进入正式运行。"
            ),
            "stub_count": len(PUBLIC_REHEARSAL_SEMANTIC_STUBS),
            "question_ids_preserved": True,
            "formal_runtime_allowed": False,
            "semantic_quality_evidence": False,
        },
        "route_summaries": route_summaries,
        "request_adapter_total": total_requests,
        "answer_adapter_total": total_answers,
        "score_row_total": total_score_rows,
        "semantic_quality_gate_evaluated": False,
    }


def run_rehearsal(
    *,
    ticket_path: Path,
    contract_path: Path,
    sample_path: Path,
    output_dir: Path,
    expected_ticket_id: str,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    project_root = project_root.resolve(strict=True)
    ticket_path = _resolve_public_path(
        ticket_path,
        project_root=project_root,
        code="TICKET_INPUT_PUBLIC_PATH_INVALID",
    )
    contract_path = _resolve_public_path(
        contract_path,
        project_root=project_root,
        code="CONTRACT_INPUT_PUBLIC_PATH_INVALID",
    )
    sample_path = _resolve_public_path(
        sample_path,
        project_root=project_root,
        code="SAMPLE_INPUT_PUBLIC_PATH_INVALID",
    )
    ticket = _as_mapping(
        terminal.load_json(ticket_path),
        "TICKET_NOT_OBJECT",
    )
    contract = _as_mapping(
        terminal.load_json(contract_path),
        "CONTRACT_NOT_OBJECT",
    )
    sample = _as_mapping(
        terminal.load_json(sample_path),
        "SAMPLE_NOT_OBJECT",
    )
    ticket_receipt = _validate_ticket(
        ticket=ticket,
        ticket_path=ticket_path,
        sample_path=sample_path,
        expected_ticket_id=expected_ticket_id,
        project_root=project_root,
    )
    contract_receipt = _validate_contract(
        contract=contract,
        contract_path=contract_path,
        ticket=ticket,
        project_root=project_root,
    )
    sample_receipt = validate_public_sample(
        sample=sample,
        contract=contract,
        contract_sha256=contract_receipt["contract_sha256"],
    )
    public_sample = _as_mapping(
        ticket["public_fake_sample"],
        "TICKET_PUBLIC_SAMPLE_MISSING",
    )
    _expect(
        public_sample.get("payload_sha256") == sample_receipt["sample_payload_sha256"],
        "TICKET_SAMPLE_PAYLOAD_SHA_MISMATCH",
    )
    negative_results = run_negative_suite(
        sample=sample,
        contract=contract,
        contract_sha256=contract_receipt["contract_sha256"],
        case_ids=contract_receipt["case_ids"],
    )
    pipeline = _run_offline_pipeline(
        sample=sample,
        case_ids=contract_receipt["case_ids"],
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "ticket": ticket_receipt,
        "contract": contract_receipt,
        "sample": sample_receipt,
        "pipeline": pipeline,
        "negative_layout_cases": negative_results,
        "negative_layout_case_total": len(negative_results),
        "wrong_layout_rejection_passed": all(
            row["status"] == "REJECTED" for row in negative_results
        ),
        "formal_cycle_created": False,
        "formal_run_created": False,
        "formal_authority_issued": False,
        "formal_terminal_ticket_consumed": False,
        "model_api_calls": 0,
        "network_requests": 0,
        "private_terminal_files_read": 0,
        "sealed_directory_reads": 0,
        "formal_terminal_runs": 0,
        "formal_score_runs": 0,
    }
    result["receipt_payload_sha256"] = terminal.sha256_bytes(
        terminal.canonical_bytes(result)
    )
    terminal.write_json(
        output_dir.resolve() / "PUBLIC_LAYOUT_REHEARSAL_RECEIPT.json",
        result,
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-ticket-id", required=True)
    parser.add_argument("--ticket", type=Path, required=True)
    parser.add_argument("--layout-contract", type=Path, required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_rehearsal(
        ticket_path=args.ticket,
        contract_path=args.layout_contract,
        sample_path=args.sample,
        output_dir=args.output_dir,
        expected_ticket_id=args.expected_ticket_id,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "schema_version": result["schema_version"],
                "receipt_payload_sha256": result["receipt_payload_sha256"],
                "expanded_question_cell_total": result["pipeline"][
                    "expanded_question_cell_total"
                ],
                "score_row_total": result["pipeline"]["score_row_total"],
                "negative_layout_case_total": result["negative_layout_case_total"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

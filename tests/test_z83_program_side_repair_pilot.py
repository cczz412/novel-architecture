from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

import z83_program_side_repair_pilot as z83
import z83_retry13_atomic_repair as retry13
from zbatch_modules.errors import ZBatchError


def _prepare(
    tmp_path: Path,
    name: str = "run",
    *,
    inspector_max_tokens: int = z83.INSPECTOR_BASE_MAX_TOKENS,
) -> Path:
    run_dir = tmp_path / name
    z83.prepare(
        run_dir,
        inspector_max_tokens=inspector_max_tokens,
        allow_test_run_dir=True,
    )
    return run_dir


def _prepare_retry04_review_from_retry03(
    tmp_path: Path,
    *,
    target_name: str = z83.APPROVED_COMPLETED_SEED_TARGET_NAME,
) -> Path:
    run_dir = _prepare(
        tmp_path,
        target_name,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    z83.seed_main_samples(
        run_dir,
        z83.ROOT / "runs" / z83.APPROVED_COMPLETED_SEED_SOURCE_NAME,
        allow_test_run_dir=True,
    )

    class NoCallTransport:
        def call(self, **_: object) -> None:
            raise AssertionError("retry04主样张复用不得发新请求")

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.ApiTransport,
            "from_bundle",
            return_value=NoCallTransport(),
        ):
            z83.run_main(run_dir, allow_test_run_dir=True)
    z83.verify_main(run_dir, allow_test_run_dir=True)
    z83.build_review(run_dir, phase="main")
    return run_dir


def _prepare_retry05_review_from_retry03(tmp_path: Path) -> Path:
    return _prepare_retry04_review_from_retry03(
        tmp_path,
        target_name=z83.APPROVED_QUOTE_CONSTRAINT_TARGET_NAME,
    )


def _prepare_retry06_review_from_retry03(tmp_path: Path) -> Path:
    return _prepare_retry04_review_from_retry03(
        tmp_path,
        target_name=z83.APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME,
    )


def _prepare_retry07_review_from_retry03(tmp_path: Path) -> Path:
    return _prepare_retry04_review_from_retry03(
        tmp_path,
        target_name=z83.APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME,
    )


def _prepare_retry08_review_from_retry03(tmp_path: Path) -> Path:
    return _prepare_retry04_review_from_retry03(
        tmp_path,
        target_name=z83.APPROVED_PUNCTUATION_UNIT_TARGET_NAME,
    )


def _prepare_retry09_review_from_retry03(tmp_path: Path) -> Path:
    return _prepare_retry04_review_from_retry03(
        tmp_path,
        target_name=z83.APPROVED_CAPACITY_OVERRIDE_TARGET_NAME,
    )


def _prepare_retry10_review_from_retry03(tmp_path: Path) -> Path:
    return _prepare_retry04_review_from_retry03(
        tmp_path,
        target_name=z83.APPROVED_THIRTEEN_RETRY_TARGET_NAME,
    )


def _prepare_retry11_review_from_retry03(tmp_path: Path) -> Path:
    return _prepare_retry04_review_from_retry03(
        tmp_path,
        target_name=z83.APPROVED_COUNT_CONTRACT_TARGET_NAME,
    )


def _prepare_retry12_review_from_retry03(tmp_path: Path) -> Path:
    return _prepare_retry04_review_from_retry03(
        tmp_path,
        target_name=z83.APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME,
    )


def _install_synthetic_exchange(
    *,
    stage_dir: Path,
    stage: str,
    case_id: str,
    body: dict,
    content_value: dict | list,
) -> SimpleNamespace:
    request_record = {
        "provider": "sensenova",
        "api_base_url": "https://token.sensenova.cn/v1",
        "api_endpoint": "/chat/completions",
        "stage": stage,
        "case_id": case_id,
        "contract_status": "approved_transport_reference",
        "unverified_candidate_override": False,
        "body": body,
        "_security": "no_api_key_no_authorization",
    }
    request_path = stage_dir / f"requests/{stage}/{case_id}_request.json"
    z83.write_json(request_path, request_record)
    content = json.dumps(content_value, ensure_ascii=False)
    raw = {
        "model": z83.api_transport.PINNED_MODEL,
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {},
    }
    raw_path = stage_dir / f"responses/{stage}/{case_id}_raw.json"
    z83.write_json(raw_path, raw)
    request_sha = z83.sha256_file(request_path)
    raw_sha = z83.sha256_file(raw_path)
    meta = {
        "requested_model": z83.api_transport.PINNED_MODEL,
        "response_model": z83.api_transport.PINNED_MODEL,
        "finish_reason": "stop",
        "request_sha256": request_sha,
        "raw_response_sha256": raw_sha,
    }
    z83.write_json(stage_dir / f"responses/{stage}/{case_id}_meta.json", meta)
    prior_attempts = len(z83.z68.read_jsonl(stage_dir / "call_attempts.jsonl"))
    z83.append_jsonl(
        stage_dir / "call_attempts.jsonl",
        {
            "call_number": prior_attempts + 1,
            "max_calls": z83.MAX_NETWORK_ATTEMPTS,
            "stage": stage,
            "case_id": case_id,
            "attempt": 1,
            "request_sha256": request_sha,
        },
    )
    z83.append_jsonl(
        stage_dir / "usage.jsonl",
        {
            **meta,
            "stage": stage,
            "case_id": case_id,
            "usage": {},
        },
    )
    return SimpleNamespace(content=content, request_record=request_record)


def _install_interrupted_main_prefix(run_dir: Path) -> None:
    """第3章完整成功，第13章只占到运输尝试后被人工中断。"""

    stage_dir = run_dir / "main"
    z83.write_json(
        stage_dir / "run_claim.json",
        {
            "schema_version": "z83-main-run-claim-v1",
            "status": "claimed_do_not_resume",
            "pid": 1,
            "claimed_at": "2026-07-22T00:00:00+08:00",
        },
    )
    chapter = 3
    case_id = "z83_main_ch0003"
    catalog = z83._catalog(run_dir, chapter)
    anchor_id = str(catalog[0]["anchor_id"])
    payload = {
        "schema_version": z83.neutral_extract.EVENT_SCHEMA_VERSION,
        "chapter": chapter,
        "events": [
            {
                "event_id": "EV-C0003-01",
                "event": "测试员检查样本并记录结果。",
                "anchors": [{"anchor_id": anchor_id}],
            }
        ],
    }
    result = _install_synthetic_exchange(
        stage_dir=stage_dir,
        stage="neutral_extract",
        case_id=case_id,
        body=z83.read_json(run_dir / "prepared_requests/ch0003.json"),
        content_value=payload,
    )
    parsed = z83.candidate_envelope.parse_json_content(result.content)
    model_path = stage_dir / "01_extract/model_json_original/ch0003.json"
    z83.write_json(model_path, parsed)
    analysis = z83.z77.analyze_main_response(parsed, chapter=3, catalog=catalog)
    assert analysis["hard_reasons"] == []
    z83.write_json(stage_dir / "01_extract/initial_audits/ch0003.json", analysis)
    receipt = {
        "schema_version": "z83-main-sample-exchange-v1",
        "chapter": 3,
        **z83._transport_receipt_fields(stage_dir, "neutral_extract", case_id),
        "prepared_request_path": "prepared_requests/ch0003.json",
        "prepared_request_sha256": z83.sha256_file(
            run_dir / "prepared_requests/ch0003.json"
        ),
        "parsed_model_path": z83._stage_relative(stage_dir, model_path),
        "parsed_model_file_sha256": z83.sha256_file(model_path),
        "parsed_model_canonical_sha256": z83.canonical_sha(parsed),
    }
    z83.append_jsonl(stage_dir / "main_sample_ledger.jsonl", receipt)

    incomplete_case = "z83_main_ch0013"
    incomplete_body = z83.read_json(run_dir / "prepared_requests/ch0013.json")
    request_record = {
        "provider": "sensenova",
        "api_base_url": "https://token.sensenova.cn/v1",
        "api_endpoint": "/chat/completions",
        "stage": "neutral_extract",
        "case_id": incomplete_case,
        "contract_status": "approved_transport_reference",
        "unverified_candidate_override": False,
        "body": incomplete_body,
        "_security": "no_api_key_no_authorization",
    }
    request_path = (
        stage_dir / f"requests/neutral_extract/{incomplete_case}_request.json"
    )
    z83.write_json(request_path, request_record)
    z83.append_jsonl(
        stage_dir / "call_attempts.jsonl",
        {
            "call_number": 2,
            "max_calls": z83.MAX_NETWORK_ATTEMPTS,
            "stage": "neutral_extract",
            "case_id": incomplete_case,
            "attempt": 1,
            "request_sha256": z83.sha256_file(request_path),
        },
    )
    hard_stop = {
        "schema_version": "z83-main-hard-stop-v1",
        "status": "hard_stop_no_unapproved_repair",
        "error_type": "KeyboardInterrupt",
        "error": "",
        "sampled_chapters": [3],
        "completed_chapters": [],
        "eligible_retry_candidates_by_chapter": {"3": 0, "13": 0, "19": 0},
        "network_attempts": 2,
        "targeted_retry_count": 0,
        "protected_unchanged": True,
    }
    z83.write_json(stage_dir / "hard_stop.json", hard_stop)
    z83.write_json(
        stage_dir / "run_manifest.json",
        {**hard_stop, "run_claim": z83.read_json(stage_dir / "run_claim.json")},
    )


def _install_historical_v3_main(run_dir: Path) -> None:
    source = z83.V3_RUN_DIR / "01_extract"
    target = run_dir / "main/01_extract"
    for relative in ("model_json_original", "model_json", "events", "program_audits"):
        shutil.copytree(source / relative, target / relative)
    (run_dir / "main").mkdir(parents=True, exist_ok=True)
    claim = {
        "schema_version": "z83-main-run-claim-v1",
        "status": "claimed_do_not_resume",
        "pid": 1,
        "claimed_at": "2026-07-22T00:00:00+08:00",
    }
    z83.write_json(run_dir / "main/run_claim.json", claim)
    sample_ledger = []
    for chapter in z83.TARGET_CHAPTERS:
        original = z83.read_json(target / f"model_json_original/ch{chapter:04d}.json")
        final = z83.read_json(target / f"events/ch{chapter:04d}.json")
        lineage, _ = z83._build_event_lineage(
            chapter=chapter,
            original=original,
            final=final,
            replacements={},
            retry_receipts={},
            stage="main_mechanical_retry",
        )
        z83.write_json(target / f"event_lineage/ch{chapter:04d}.json", lineage)
        case_id = f"z83_main_ch{chapter:04d}"
        _install_synthetic_exchange(
            stage_dir=run_dir / "main",
            stage="neutral_extract",
            case_id=case_id,
            body=z83.read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json"),
            content_value=original,
        )
        model_path = target / f"model_json_original/ch{chapter:04d}.json"
        receipt = {
            "schema_version": "z83-main-sample-exchange-v1",
            "chapter": chapter,
            **z83._transport_receipt_fields(
                run_dir / "main", "neutral_extract", case_id
            ),
            "prepared_request_path": f"prepared_requests/ch{chapter:04d}.json",
            "prepared_request_sha256": z83.sha256_file(
                run_dir / f"prepared_requests/ch{chapter:04d}.json"
            ),
            "parsed_model_path": z83._stage_relative(run_dir / "main", model_path),
            "parsed_model_file_sha256": z83.sha256_file(model_path),
            "parsed_model_canonical_sha256": z83.canonical_sha(original),
        }
        sample_ledger.append(receipt)
        z83.append_jsonl(run_dir / "main/main_sample_ledger.jsonl", receipt)
    z83.write_json(
        run_dir / "main/01_extract/metrics.json",
        {
            "schema_version": "z83-main-metrics-v1",
            "status": "completed_candidate_silver_only",
            "chapters_completed": list(z83.TARGET_CHAPTERS),
            "seeded_chapters": [],
            "newly_sampled_chapters": list(z83.TARGET_CHAPTERS),
            "main_logical_calls": 3,
            "main_live_logical_calls": 3,
            "main_reused_logical_samples": 0,
            "targeted_retry_logical_calls": 0,
            "network_attempts": 3,
            "network_attempts_imported": 0,
            "network_attempts_this_run": 3,
            "source_incomplete_attempts_not_imported": 0,
            "main_seed": None,
            "successful_responses": 3,
            "usage_totals": {},
            "targeted_retry_ledger": [],
            "main_sample_ledger": sample_ledger,
            "retry_by_chapter": {str(chapter): 0 for chapter in z83.TARGET_CHAPTERS},
        },
    )
    z83.write_json(
        run_dir / "main/run_manifest.json",
        {
            "schema_version": "z83-main-run-manifest-v1",
            "status": "completed_candidate_silver_only",
            "chapters_completed": list(z83.TARGET_CHAPTERS),
            "seeded_chapters": [],
            "newly_sampled_chapters": list(z83.TARGET_CHAPTERS),
            "run_claim": claim,
            "network_attempts": 3,
            "network_attempts_imported": 0,
            "source_incomplete_attempts_not_imported": 0,
            "main_seed": None,
            "targeted_retry_count": 0,
        },
    )


def _install_synthetic_retry13_atomic_candidate(run_dir: Path) -> None:
    """造一套不发网的 retry13 完整工件，专测审查桥与调用血缘。"""

    z83.seed_main_samples(
        run_dir,
        z83.ROOT / "runs" / z83.APPROVED_COMPLETED_SEED_SOURCE_NAME,
        allow_test_run_dir=True,
    )

    class NoCallTransport:
        def call(self, **_: object) -> None:
            raise AssertionError("retry13主样张复用不得发新请求")

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.ApiTransport,
            "from_bundle",
            return_value=NoCallTransport(),
        ):
            z83.run_main(run_dir, allow_test_run_dir=True)
    z83.verify_main(run_dir, allow_test_run_dir=True)
    z83.build_review(run_dir, phase="main")
    with mock.patch.object(retry13.z83, "verify_main", return_value={}):
        approved_plan = retry13.create_plan(run_dir)
    retry13.preflight(run_dir)
    main_events = z83._event_map(run_dir / "main")
    main_lineage = z83._validate_main_lineage(run_dir)["rows"]
    plan = approved_plan
    parents = []
    tasks = []
    for parent_ordinal, event_id in enumerate(retry13.PARENT_ORDER, 1):
        event = main_events[event_id]
        prior = main_lineage[event_id]
        specs = retry13._parent_task_specs(event_id)
        task_ids = []
        for fact_ordinal, spec in enumerate(specs, 1):
            task_id = retry13._task_id(event_id, fact_ordinal)
            task_ids.append(task_id)
            tasks.append(
                {
                    "task_id": task_id,
                    "parent_ordinal": parent_ordinal,
                    "parent_event_id": event_id,
                    "parent_event_sha256": z83.canonical_sha(event),
                    "source_event_id": prior["source_event_id"],
                    "source_event_sha256": prior["source_event_sha256"],
                    "source_identity_sha256": prior["source_identity_sha256"],
                    "chapter": int(event_id[4:8]),
                    "fact_ordinal": fact_ordinal,
                    "fact_count": len(specs),
                    "fact_target": spec["fact"],
                    "fact_target_sha256": retry13.canonical_sha(spec["fact"]),
                    "required_anchor_ids": [
                        str(event["anchors"][0]["anchor_id"])
                    ],
                    "anchor_binding_policy": "exact_program_prechecked_set",
                    "single_object_required": True,
                    "output_contract": retry13.CONTRACT_VERSION,
                }
            )
        parents.append(
            {
                "parent_ordinal": parent_ordinal,
                "event_id": event_id,
                "chapter": int(event_id[4:8]),
                "event_sha256": z83.canonical_sha(event),
                "source_event_id": prior["source_event_id"],
                "source_event_sha256": prior["source_event_sha256"],
                "source_identity_sha256": prior["source_identity_sha256"],
                "reason_codes": ["SEMANTIC_ANCHOR_UNSUPPORTED"],
                "route": "program_atomic_split",
                "fact_count": len(specs),
                "task_ids": task_ids,
                "counts_as_one_parent_rewrite": True,
                "facts_may_not_be_added_or_dropped": True,
            }
        )
    _unused_shape_fixture = {
        "schema_version": retry13.PLAN_SCHEMA,
        "status": "ready_zero_call",
        "run_id": run_dir.name,
        "parent_count": 13,
        "parents": parents,
        "atomic_split_total": 25,
        "logical_request_count": 32,
        "network_attempt_budget": 36,
        "tasks": tasks,
        "pending_parent_ids": [],
    }
    z83.write_json(run_dir / "repair/atomic_plan.json", plan)
    # 上面的简化形状只保留给旧测试语义对照，没有写入正式工件。
    assert _unused_shape_fixture["logical_request_count"] == 32
    parents = list(plan["parents"])
    tasks = list(plan["tasks"])
    preflight = retry13.verify_preflight(run_dir)
    preflight_receipt = z83.read_json(run_dir / "repair/atomic_preflight.json")
    preflight_by_task = {
        str(row["task_id"]): row for row in preflight_receipt["rows"]
    }
    route = z83.api_transport.TransportRoute.from_mapping(
        z83.load_bundle(run_dir).route
    )

    results = {}
    usage_rows = []
    attempt_rows = []
    reservation_rows = []
    fixture_started_at = datetime(
        2026, 7, 22, tzinfo=timezone(timedelta(hours=8))
    )
    previous_chapter: int | None = None
    for ordinal, task in enumerate(tasks, 1):
        anchor_ids = list(task["required_anchor_ids"])
        normalized = {
            "event": f"测试人物完成第{ordinal}项原子事实并留下明确结果。",
            "anchors": [{"anchor_id": anchor_id} for anchor_id in anchor_ids],
        }
        task_id = task["task_id"]
        preflight_row = preflight_by_task[task_id]
        prepared_path = run_dir / str(preflight_row["prepared_request_path"])
        body = z83.read_json(prepared_path)
        request_path, request_sha, _, wire_sha = retry13._build_request_artifact(
            run_dir=run_dir,
            plan=plan,
            task=task,
            preflight_row=preflight_row,
            body=body,
            route=route,
        )
        raw_path = run_dir / f"repair/raw_responses/single_object/{task_id}_raw.json"
        raw_payload = {
            "event": normalized["event"],
            "anchor_ids": anchor_ids,
        }
        raw_content = json.dumps(raw_payload, ensure_ascii=False)
        z83.write_json(
            raw_path,
            {
                "model": route.model,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": raw_content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
        raw_sha = z83.sha256_file(raw_path)
        started_at = fixture_started_at + timedelta(seconds=(ordinal - 1) * 31)
        finished_at = started_at + timedelta(seconds=1)
        spacing_seconds = (
            0.0
            if previous_chapter is None
            else 10.0
            if previous_chapter == task["chapter"]
            else 30.0
        )
        attempt = {
            "schema": z83.z83_retry_transport.ATTEMPT_LEDGER_SCHEMA,
            "logical_request_id": task_id,
            "chapter": task["chapter"],
            "attempt": 1,
            "http_status": 200,
            "outcome": "success",
            "request_sha256": request_sha,
            "raw_response_sha256": raw_sha,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "retry_after_raw": None,
            "retry_after_seconds": None,
            "wire_body_sha256": wire_sha,
            "request_artifact_sha256": request_sha,
            "error_code": None,
            "error_body_sha256": None,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "pre_request_spacing_planned_seconds": spacing_seconds,
            "pre_request_spacing_seconds": spacing_seconds,
            "retry_wait_seconds": 0.0,
            "retry_wait_actual_seconds": 0.0,
            "previous_attempt": None,
            "usage_status": "returned",
        }
        attempt["row_sha256"] = z83.canonical_sha(attempt)
        attempt_rows.append(attempt)
        previous_chapter = int(task["chapter"])
        reservation = {
            "schema": "z83-retry13-attempt-reservation-v1",
            "logical_request_id": task_id,
            "parent_event_id": task["parent_event_id"],
            "chapter": task["chapter"],
            "attempt": 1,
            "request_artifact_sha256": request_sha,
            "wire_body_sha256": wire_sha,
            "reserved_at": "2026-07-22T00:00:00+08:00",
            "state": "reserved_before_network_do_not_resend_if_unmatched",
        }
        reservation["row_sha256"] = z83.canonical_sha(reservation)
        reservation_rows.append(reservation)
        usage = {
            "schema_version": "z83-retry13-usage-v1",
            "logical_request_id": task_id,
            "parent_event_id": task["parent_event_id"],
            "chapter": task["chapter"],
            "request_artifact_sha256": request_sha,
            "raw_response_sha256": raw_sha,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "at": "2026-07-22T00:00:01+08:00",
        }
        usage["row_sha256"] = z83.canonical_sha(usage)
        usage_rows.append(usage)
        checkpoint_request = {
            "schema": "z83-retry13-checkpoint-request-v1",
            "logical_request_id": task_id,
            "request_artifact_path": request_path.relative_to(run_dir).as_posix(),
            "request_artifact_sha256": request_sha,
            "wire_body_sha256": wire_sha,
            "model": route.model,
            "stage": "targeted_retry_single_object",
            "contract_version": retry13.CONTRACT_VERSION,
        }
        checkpoint_response = {
            "schema": "z83-retry13-checkpoint-response-v1",
            "logical_request_id": task_id,
            "request_artifact_sha256": request_sha,
            "http_status": 200,
            "raw_response_path": raw_path.relative_to(run_dir).as_posix(),
            "raw_response_sha256": raw_sha,
            "response_model": route.model,
            "finish_reason": "stop",
            "content_sha256": hashlib.sha256(
                raw_content.encode("utf-8")
            ).hexdigest(),
            "error_code": None,
        }
        checkpoint_usage = {
            "schema": "z83-retry13-checkpoint-usage-v1",
            "logical_request_id": task_id,
            "request_artifact_sha256": request_sha,
            "raw_response_sha256": raw_sha,
            "usage": usage["usage"],
        }
        checkpoint_seal = z83.z83_retry_transport.write_checkpoint_bundle(
            run_dir / f"repair/checkpoints/{task_id}",
            request_record=checkpoint_request,
            response_record=checkpoint_response,
            usage_record=checkpoint_usage,
            attempt_rows=[attempt],
            contract_version=retry13.CONTRACT_VERSION,
            mechanical_verdict="pass",
        )
        result = retry13._task_result_document(
            run_dir=run_dir,
            task=task,
            request_record=checkpoint_request,
            raw_response_sha256=raw_sha,
            content=raw_content,
            normalized=normalized,
            diagnostics=[],
            checkpoint_seal=checkpoint_seal,
        )
        z83.write_json(run_dir / f"repair/results/{task_id}.json", result)
        results[task_id] = result
    for path, rows in (
        (run_dir / "repair/call_attempts.jsonl", attempt_rows),
        (run_dir / "repair/attempt_reservations.jsonl", reservation_rows),
        (run_dir / "repair/usage.jsonl", usage_rows),
    ):
        for row in rows:
            z83.append_jsonl(path, row)

    replacements, parent_ledgers = retry13.aggregate_parent_results(plan, results)
    targeted_rows = []
    for chapter in z83.TARGET_CHAPTERS:
        original = z83.read_json(z83._model_file(run_dir / "main", chapter))
        lineage_original = z83.read_json(z83._event_file(run_dir / "main", chapter))
        final_json = z83.z77.apply_replacements(
            original,
            chapter=chapter,
            replacements=replacements.get(chapter, {}),
        )
        materialized, audit = z83.neutral_extract.process_model_data(
            final_json,
            chapter=chapter,
            catalog=z83._catalog(run_dir, chapter),
        )
        receipts_by_index = {}
        for parent in parents:
            if parent["chapter"] != chapter:
                continue
            index = int(parent["event_id"].rsplit("-", 1)[1]) - 1
            parent_ledger = next(
                row
                for row in parent_ledgers
                if row["parent_event_id"] == parent["event_id"]
            )
            receipts_by_index[index] = {
                "reason_codes": parent["reason_codes"],
                **parent_ledger,
            }
        prior_rows = {
            event_id: row
            for event_id, row in main_lineage.items()
            if int(event_id[4:8]) == chapter
        }
        lineage, descendants = z83._build_event_lineage(
            chapter=chapter,
            original=lineage_original,
            final=materialized,
            replacements=replacements.get(chapter, {}),
            retry_receipts=receipts_by_index,
            stage="semantic_targeted_retry_atomic_program_split",
            prior_rows=prior_rows,
        )
        for index, receipt in sorted(receipts_by_index.items()):
            input_event_id = str(original["events"][index]["event_id"])
            parent = next(row for row in parents if row["event_id"] == input_event_id)
            row = {
                "schema_version": "z83-retry13-parent-rewrite-ledger-v1",
                "chapter": chapter,
                "original_event_id": input_event_id,
                "original_event_sha256": parent["event_sha256"],
                "source_event_id": parent["source_event_id"],
                "source_event_sha256": parent["source_event_sha256"],
                "source_identity_sha256": parent["source_identity_sha256"],
                "source_retry_count_before": prior_rows[input_event_id]["retry_count"],
                "source_retry_count_after": prior_rows[input_event_id]["retry_count"] + 1,
                "reason_codes": parent["reason_codes"],
                "materialized_event_ids": descendants[input_event_id],
                "replacement_count": receipt["replacement_count"],
                "child_results": receipt["child_results"],
                "fact_closed_set_semantic_review": "pending_not_inferred_from_sha",
            }
            row["row_sha256"] = z83.canonical_sha(row)
            targeted_rows.append(row)
        z83.write_json(
            run_dir / f"repair/01_extract/model_json/ch{chapter:04d}.json", final_json
        )
        z83.write_json(
            run_dir / f"repair/01_extract/events/ch{chapter:04d}.json", materialized
        )
        z83.write_json(
            run_dir / f"repair/01_extract/program_audits/ch{chapter:04d}.json", audit
        )
        z83.write_json(
            run_dir / f"repair/01_extract/event_lineage/ch{chapter:04d}.json", lineage
        )
    for row in targeted_rows:
        z83.append_jsonl(run_dir / "repair/targeted_retry_ledger.jsonl", row)
    claim = {
        "schema_version": "z83-retry13-run-claim-v1",
        "status": "running_do_not_resume_or_cherry_pick",
        "run_id": run_dir.name,
        "plan_sha256": z83.sha256_file(run_dir / "repair/atomic_plan.json"),
        "preflight_sha256": z83.sha256_file(
            run_dir / "repair/atomic_preflight.json"
        ),
        "preflight_verification_sha256": z83.canonical_sha(preflight),
        "logical_request_count": 32,
        "claimed_at": "2026-07-22T00:00:00+08:00",
    }
    z83.write_json(run_dir / "repair/retry13_run_claim.json", claim)
    mechanical = z83.verify_event_stage(
        run_dir,
        run_dir / "repair",
        schema_version="z83-retry13-repair-mechanical-verification-v1",
    )
    z83.write_json(
        run_dir / "repair/01_extract/metrics.json",
        {
            "schema_version": "z83-retry13-repair-metrics-v1",
            "status": "completed_candidate_silver_only_awaiting_targeted_semantic_review",
            "parent_rewrite_count": 13,
            "logical_request_count": 32,
            "network_attempts": 32,
            "http_429_count": 0,
            "usage_row_count": 32,
            "main_event_count": 156,
            "final_event_count": 175,
            "rewritten_descendant_count": 32,
            "main_event_count_by_chapter": {"3": 58, "13": 46, "19": 52},
            "final_event_count_by_chapter": {"3": 61, "13": 50, "19": 64},
            "rewritten_descendant_count_by_chapter": {"3": 7, "13": 7, "19": 18},
            "parent_ledgers": parent_ledgers,
            "mechanical_verification_sha256": retry13._stable_mechanical_verification_sha256(
                mechanical
            ),
            "candidate_silver_only": True,
        },
    )
    assert z83.read_json(run_dir / "repair/retry13_run_claim.json") == claim
    z83.write_json(
        run_dir / "repair/retry13_run_manifest.json",
        {
            "schema_version": "z83-retry13-run-manifest-v1",
            "status": "completed_candidate_silver_only_awaiting_targeted_semantic_review",
            "run_claim": claim,
            "logical_request_count": 32,
            "network_attempts": 32,
            "http_429_count": 0,
            "rewritten_descendant_count": 32,
            "final_event_count": 175,
            "prefix_cherry_picked": False,
            "candidate_silver_only": True,
        },
    )
    shutil.copytree(run_dir / "repair/01_extract", run_dir / "final/01_extract")
    z83.write_json(
        run_dir / "final/run_manifest.json",
        {
            "schema_version": "z83-retry13-final-event-manifest-v1",
            "status": "awaiting_targeted_semantic_review",
            "source_atomic_plan_sha256": z83.sha256_file(
                run_dir / "repair/atomic_plan.json"
            ),
            "parent_rewrite_count": 13,
            "logical_request_count": 32,
            "rewritten_descendant_count": 32,
            "final_event_count": 175,
            "candidate_silver_only": True,
        },
    )


def _completed_adjudication(run_dir: Path, phase: str = "main") -> dict:
    review_name = "review" if phase == "main" else "final_review"
    template = z83.read_json(run_dir / review_name / "adjudication_template.json")
    for row in template["anchor_rows"]:
        row["verdict"] = "valid"
        row["reason"] = "所挂冻结短引直接托住事件句全部明示主张。"
    v3 = z83.read_json(z83.V3_ADJUDICATION)
    current = {row["record_id"]: row for row in v3["current_rows"]}
    for row in template["current_rows"]:
        source = current[row["record_id"]]
        row["verdict"] = source["verdict"]
        row["candidate_event_ids"] = source["candidate_event_ids"]
        row["reason"] = source["note"]
        if row["record_id"] == "B-C0019-04":
            row["scale_note_acknowledged"] = True
    gold = {row["part_id"]: row for row in v3["gold_rows"]}
    for row in template["gold_rows"]:
        source = gold[row["part_id"]]
        verdict = source["verdict"]
        row["verdict"] = (
            "coverage_only_invalid_support"
            if verdict == "invalid_anchor_observation"
            else verdict
        )
        row["candidate_event_ids"] = source["candidate_event_ids"]
        row["reason"] = source["note"]
    for row in template["risk_rows"]:
        row["verdict"] = "clear"
        row["reason"] = "程序风险已逐条人工复核，本条无需定点重写。"
    template["reviewer"] = "test-reviewer"
    template["reviewed_at"] = "2026-07-22T00:00:00+08:00"
    return template


def _install_zero_retry_candidate(run_dir: Path) -> None:
    _install_historical_v3_main(run_dir)
    z83.build_review(run_dir, phase="main")
    adjudication = _completed_adjudication(run_dir)
    for row in adjudication["current_rows"]:
        if row["record_id"] in {"B-C0013-02", "B-C0019-04"}:
            row["verdict"] = "preserved"
            row["reason"] = "测试夹具把两条指定记录判为完整保留。"
    for row in adjudication["gold_rows"]:
        if row["verdict"] == "coverage_only_invalid_support":
            row["verdict"] = "semantic_shadow"
            row["reason"] = "测试夹具把来源关系判为有效语义影子。"
    main_path = run_dir / "review/adjudication_all_clear.json"
    z83.write_json(main_path, adjudication)
    _install_synthetic_inspector(run_dir, phase="main")
    assert z83.plan_retries(run_dir, main_path)["status"] == "no_retry_needed"
    assert z83.run_retries(run_dir)["targeted_retry_logical_calls"] == 0


def _install_synthetic_inspector(run_dir: Path, phase: str = "main") -> None:
    stage = run_dir / phase
    events = z83._event_map(stage)
    review_name = "review" if phase == "main" else "final_review"
    review_dir = run_dir / review_name
    root = review_dir / "inspector"
    risks_path = review_dir / "program_risks.json"
    risks = z83.read_json(risks_path)
    risks["forced_strong_event_ids"] = sorted(events)
    z83.write_json(risks_path, risks)
    build_receipt_path = review_dir / "build_receipt.json"
    build_receipt = z83.read_json(build_receipt_path)
    build_receipt["review_input_sha256"]["program_risks"] = z83.sha256_file(risks_path)
    z83.write_json(build_receipt_path, build_receipt)
    claim = {
        "schema_version": f"z83-{phase}-inspector-run-claim-v1",
        "status": "claimed_do_not_resume",
        "pid": 1,
        "claimed_at": "2026-07-22T00:00:00+08:00",
    }
    z83.write_json(root / "run_claim.json", claim)
    routes = []
    for chapter in z83.TARGET_CHAPTERS:
        batch = z83.pipeline_inspector.validate_review_batch(
            z83.read_json(review_dir / f"inspector_batches/ch{chapter:04d}.json")
        )
        forced = z83._direct_forced_routing(batch, set(events))
        routes.extend(forced)
        z83.write_json(
            root / f"ch{chapter:04d}/zero_call_all_forced.json",
            {
                "schema_version": "z83-inspector-all-forced-v1",
                "chapter": chapter,
                "model_api_calls": 0,
                "routes": forced,
            },
        )
    routes.sort(key=lambda row: row["item_id"])
    event_set_sha = {
        str(chapter): z83.sha256_file(z83._event_file(stage, chapter))
        for chapter in z83.TARGET_CHAPTERS
    }
    batch_sha = {
        str(chapter): z83.sha256_file(
            review_dir / f"inspector_batches/ch{chapter:04d}.json"
        )
        for chapter in z83.TARGET_CHAPTERS
    }
    receipt = {
        "schema_version": f"z83-{phase}-inspector-routing-v1",
        "status": "routing_complete_not_final_truth",
        "phase": phase,
        "run_claim": claim,
        "completed_chapters": list(z83.TARGET_CHAPTERS),
        "batch_invocations": 0,
        "logical_model_calls": 0,
        "global_logical_call_limit": z83.MAX_INSPECTOR_LOGICAL_CALLS,
        "network_attempts": 0,
        "event_set_sha256": event_set_sha,
        "inspector_batch_sha256": batch_sha,
        "program_risks_sha256": z83.sha256_file(risks_path),
        "event_count": len(events),
        "routes": routes,
        "routes_sha256": z83.canonical_sha(routes),
        "forced_strong_count": len(events),
        "final_truth": False,
    }
    combined_path = root / "combined_routing.json"
    z83.write_json(combined_path, receipt)
    z83.write_json(
        root / "run_manifest.json",
        {
            **receipt,
            "schema_version": f"z83-{phase}-inspector-run-manifest-v1",
            "status": "completed_routing_only_not_final_truth",
            "combined_routing_sha256": z83.sha256_file(combined_path),
        },
    )


def test_frozen_v3_sources_are_sha_pinned() -> None:
    receipt = z83.source_pins()
    assert receipt["status"] == "pass"
    assert len(receipt["rows"]) == 11
    assert z83.sha256_file(z83.V3_PACKAGE) == z83.V3_PACKAGE_SHA256


def test_formal_run_dir_allows_only_default_or_two_digit_transport_retry() -> None:
    z83.assert_safe_run_dir(z83.DEFAULT_RUN_DIR)
    z83.assert_safe_run_dir(
        z83.DEFAULT_RUN_DIR.with_name(f"{z83.RUN_ID}_transport_retry01")
    )

    rejected = [
        z83.DEFAULT_RUN_DIR.with_name(f"{z83.RUN_ID}_transport_retry1"),
        z83.DEFAULT_RUN_DIR.with_name(f"{z83.RUN_ID}_transport_retry001"),
        z83.DEFAULT_RUN_DIR.with_name(f"{z83.RUN_ID}_retry01"),
        z83.DEFAULT_RUN_DIR / f"{z83.RUN_ID}_transport_retry01",
    ]
    for run_dir in rejected:
        with pytest.raises(ZBatchError, match="新编号目录"):
            z83.assert_safe_run_dir(run_dir)


def test_formal_retry04_through_retry12_accept_only_completed_retry03_seed_source() -> (
    None
):
    source = z83.ROOT / "runs" / z83.APPROVED_COMPLETED_SEED_SOURCE_NAME
    for target_name in (
        z83.APPROVED_COMPLETED_SEED_TARGET_NAME,
        z83.APPROVED_QUOTE_CONSTRAINT_TARGET_NAME,
        z83.APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME,
        z83.APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME,
        z83.APPROVED_PUNCTUATION_UNIT_TARGET_NAME,
        z83.APPROVED_CAPACITY_OVERRIDE_TARGET_NAME,
        z83.APPROVED_THIRTEEN_RETRY_TARGET_NAME,
        z83.APPROVED_COUNT_CONTRACT_TARGET_NAME,
        z83.APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME,
        z83.APPROVED_Z94_LOCAL_SEMANTIC_SUPPLY_TARGET_NAME,
        z83.APPROVED_Z94_TENCENT_FLASH_TARGET_NAME,
    ):
        target = z83.ROOT / "runs" / target_name
        assert (
            z83._assert_seed_source_dir(
                source,
                target,
                allow_test_run_dir=False,
            )
            == "completed_main_retry03"
        )
        with pytest.raises(ZBatchError, match="只接受.*retry03"):
            z83._assert_seed_source_dir(
                z83.ROOT / "runs" / z83.APPROVED_SEED_SOURCE_NAME,
                target,
                allow_test_run_dir=False,
            )
        if target_name in {
            z83.APPROVED_QUOTE_CONSTRAINT_TARGET_NAME,
            z83.APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME,
            z83.APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME,
            z83.APPROVED_PUNCTUATION_UNIT_TARGET_NAME,
            z83.APPROVED_CAPACITY_OVERRIDE_TARGET_NAME,
            z83.APPROVED_THIRTEEN_RETRY_TARGET_NAME,
            z83.APPROVED_COUNT_CONTRACT_TARGET_NAME,
            z83.APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME,
        }:
            with pytest.raises(ZBatchError, match="只接受.*retry03"):
                z83._assert_seed_source_dir(
                    z83.ROOT / "runs" / z83.APPROVED_COMPLETED_SEED_TARGET_NAME,
                    target,
                    allow_test_run_dir=False,
                )


def test_z94_completed_retry03_seed_target_allowlist_rejects_lookalikes() -> None:
    source = z83.ROOT / "runs" / z83.APPROVED_COMPLETED_SEED_SOURCE_NAME
    for target_name in (
        z83.APPROVED_Z94_LOCAL_SEMANTIC_SUPPLY_TARGET_NAME,
        z83.APPROVED_Z94_TENCENT_FLASH_TARGET_NAME,
    ):
        with pytest.raises(ZBatchError, match="主样张复用只接受"):
            z83._assert_seed_source_dir(
                source,
                z83.ROOT / "runs" / f"{target_name}_unapproved",
                allow_test_run_dir=False,
            )


def test_retry05_refuses_main_run_without_completed_retry03_seed(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_QUOTE_CONSTRAINT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    with mock.patch.object(
        z83.api_transport.ApiTransport,
        "from_bundle",
        side_effect=AssertionError("禁止进入主采样运输层"),
    ):
        with pytest.raises(ZBatchError, match="必须先完整复用.*retry03"):
            z83.run_main(run_dir, allow_test_run_dir=True)
    assert not (run_dir / "main/run_claim.json").exists()


def test_prepare_pins_inspector_and_transport_sources(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    preflight_path = run_dir / "preflight.json"
    preflight = z83.read_json(preflight_path)
    dependencies = preflight["producer_dependencies"]
    assert set(dependencies) == {"pipeline_inspector", "api_transport"}
    for dependency in dependencies.values():
        source = z83.ROOT / dependency["path"]
        assert dependency["sha256"] == z83.sha256_file(source)

    preflight["producer_dependencies"]["pipeline_inspector"]["sha256"] = "0" * 64
    z83.write_json(preflight_path, preflight)
    with pytest.raises(ZBatchError, match="pipeline_inspector prepare 后漂移"):
        z83.verify_prepared(
            run_dir,
            require_zero_call=True,
            allow_test_run_dir=True,
        )


def test_formal_retry_run_dir_rejects_symlink_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    runs_root = repo_root / "runs"
    outside = tmp_path / "outside"
    runs_root.mkdir(parents=True)
    outside.mkdir()
    escaped_retry = runs_root / f"{z83.RUN_ID}_transport_retry02"
    escaped_retry.symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(z83, "ROOT", repo_root)
    monkeypatch.setattr(z83, "DEFAULT_RUN_DIR", runs_root / z83.RUN_ID)
    with pytest.raises(ZBatchError, match="新编号目录"):
        z83.assert_safe_run_dir(escaped_retry)


def test_prepare_is_zero_call_and_copies_three_requests_byte_for_byte(
    tmp_path: Path,
) -> None:
    first = _prepare(tmp_path, "first")
    second = _prepare(tmp_path, "second")
    for chapter in z83.TARGET_CHAPTERS:
        source = z83.V3_RUN_DIR / f"prepared_requests/ch{chapter:04d}.json"
        one = first / f"prepared_requests/ch{chapter:04d}.json"
        two = second / f"prepared_requests/ch{chapter:04d}.json"
        assert one.read_bytes() == source.read_bytes() == two.read_bytes()
        assert z83.forbidden_model_hits(z83.read_json(one)) == []
    assert z83.call_artifacts_present(first) == []
    assert (
        z83.verify_prepared(first, require_zero_call=True, allow_test_run_dir=True)[
            "status"
        ]
        == "pass"
    )


def test_prepare_32k_builds_isolated_single_variable_contract(tmp_path: Path) -> None:
    run_dir = _prepare(
        tmp_path,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    preflight = z83.read_json(run_dir / "preflight.json")
    compatibility = preflight["inspector_compatibility"]
    assert compatibility["status"] == "single_variable_8000_to_32000"
    assert compatibility["differences"] == [
        {
            "path": ("$.profiles.z76_phase2_reviewer.stages.semantic_route.max_tokens"),
            "before": 8000,
            "after": 32000,
        }
    ]
    assert (
        z83.read_json(z83.INSPECTOR_CONTRACT)["profiles"][
            z83.pipeline_inspector.DEFAULT_PROFILE
        ]["stages"]["semantic_route"]["max_tokens"]
        == 8000
    )
    local = z83.read_json(run_dir / z83.LOCAL_INSPECTOR_CONTRACT)
    stage = local["profiles"][z83.pipeline_inspector.DEFAULT_PROFILE]["stages"][
        "semantic_route"
    ]
    assert stage["max_tokens"] == 32000
    assert stage["reasoning_effort"] == "medium"
    assert stage["temperature"] == 0.0
    assert stage["n"] == 1
    assert stage["response_format"] == {"type": "json_object"}
    reference = z83.read_json(run_dir / z83.RETRY03_INSPECTOR_REFERENCE)
    assert reference["finish_reason"] == "length"
    assert reference["visible_usage"]["prompt_tokens"] == 12358
    assert reference["visible_usage"]["completion_tokens"] == 8001
    assert reference["visible_usage"]["total_tokens"] == 20359
    assert (
        reference["visible_usage"]["completion_tokens_details"]["reasoning_tokens"]
        == 2912
    )
    assert reference["rejected_as_result"] is True
    assert reference["imported_as_result"] is False
    assert "content" not in reference and "routes" not in reference
    assert z83.call_artifacts_present(run_dir) == []

    contract_path = run_dir / z83.LOCAL_INSPECTOR_CONTRACT
    tampered = z83.read_json(contract_path)
    tampered["profiles"][z83.pipeline_inspector.DEFAULT_PROFILE]["stages"][
        "semantic_route"
    ]["reasoning_effort"] = "high"
    z83.write_json(contract_path, tampered)
    with pytest.raises(ZBatchError, match="32k兼容收据|单变量"):
        z83.verify_prepared(
            run_dir,
            require_zero_call=True,
            allow_test_run_dir=True,
        )


def test_missing_key_stops_before_claim_or_attempt(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ZBatchError, match="发网前0调用拒绝"):
            z83.run_main(run_dir, allow_test_run_dir=True)
    assert not (run_dir / "main/run_claim.json").exists()
    assert not (run_dir / "main/call_attempts.jsonl").exists()


def test_pre_send_block_is_reusable_and_zero_call(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    with mock.patch.dict(os.environ, {}, clear=True):
        receipt = z83.record_pre_send_block(run_dir, allow_test_run_dir=True)
    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0
    assert receipt["run_claim_created"] is False
    assert receipt["prepared_run_reusable_after_key_loaded"] is True


def test_seed_main_imports_only_complete_prefix_and_keeps_interrupted_attempt_as_provenance(
    tmp_path: Path,
) -> None:
    source = _prepare(tmp_path, "source")
    target = _prepare(tmp_path, "target")
    _install_interrupted_main_prefix(source)

    receipt = z83.seed_main_samples(
        target,
        source,
        allow_test_run_dir=True,
    )
    assert receipt["chapters"] == [3]
    assert receipt["imported_network_attempts"] == 1
    assert receipt["source_incomplete_attempts_not_imported"] == 1
    assert [
        row["case_id"]
        for row in z83.z68.read_jsonl(target / "main/call_attempts.jsonl")
    ] == ["z83_main_ch0003"]
    assert not (
        target / "main/requests/neutral_extract/z83_main_ch0013_request.json"
    ).exists()
    source_attempts = z83.z68.read_jsonl(
        target / "main/seed_provenance/source_call_attempts.jsonl"
    )
    assert [row["case_id"] for row in source_attempts] == [
        "z83_main_ch0003",
        "z83_main_ch0013",
    ]


def test_seed_main_tampered_raw_response_is_rejected(tmp_path: Path) -> None:
    source = _prepare(tmp_path, "source")
    target = _prepare(tmp_path, "target")
    _install_interrupted_main_prefix(source)
    z83.seed_main_samples(target, source, allow_test_run_dir=True)
    raw_path = target / "main/responses/neutral_extract/z83_main_ch0003_raw.json"
    raw = z83.read_json(raw_path)
    raw["choices"][0]["message"]["content"] = '{"schema_version":"tampered"}'
    z83.write_json(raw_path, raw)
    with pytest.raises(ZBatchError, match="原始响应缺失或 SHA"):
        z83.verify_main_seed(target, allow_test_run_dir=True)


def test_seed_main_rejects_duplicate_provenance_rows(tmp_path: Path) -> None:
    source = _prepare(tmp_path, "source")
    target = _prepare(tmp_path, "target")
    _install_interrupted_main_prefix(source)
    z83.seed_main_samples(target, source, allow_test_run_dir=True)
    manifest_path = target / z83.MAIN_SEED_MANIFEST
    manifest = z83.read_json(manifest_path)
    manifest["provenance_copies"] = [manifest["provenance_copies"][0]] * 6
    z83.write_json(manifest_path, manifest)
    with pytest.raises(ZBatchError, match="来源旁账缺失或漂移"):
        z83.verify_main_seed(target, allow_test_run_dir=True)


def test_seed_main_rejects_source_claim_drift_and_unledgered_response(
    tmp_path: Path,
) -> None:
    source = _prepare(tmp_path, "source")
    target = _prepare(tmp_path, "target")
    _install_interrupted_main_prefix(source)
    claim_path = source / "main/run_claim.json"
    claim = z83.read_json(claim_path)
    claim["pid"] = 2
    z83.write_json(claim_path, claim)
    with pytest.raises(ZBatchError, match="硬停票、阶段状态票与占用票不一致"):
        z83.seed_main_samples(target, source, allow_test_run_dir=True)

    source2 = _prepare(tmp_path, "source2")
    target2 = _prepare(tmp_path, "target2")
    _install_interrupted_main_prefix(source2)
    z83.write_json(
        source2 / "main/responses/neutral_extract/z83_main_ch0013_raw.json",
        {
            "model": z83.api_transport.PINNED_MODEL,
            "choices": [
                {
                    "message": {"role": "assistant", "content": "{}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {},
        },
    )
    with pytest.raises(ZBatchError, match="未入账成功响应"):
        z83.seed_main_samples(target2, source2, allow_test_run_dir=True)


def test_completed_retry03_seed_reuses_all_three_without_live_main_call(
    tmp_path: Path,
) -> None:
    source = z83.ROOT / "runs" / z83.APPROVED_COMPLETED_SEED_SOURCE_NAME
    target = _prepare(tmp_path, "completed-target")
    receipt = z83.seed_main_samples(
        target,
        source,
        allow_test_run_dir=True,
    )
    assert receipt["source_kind"] == "completed_main"
    assert receipt["chapters"] == [3, 13, 19]
    assert receipt["imported_network_attempts"] == 3
    assert receipt["source_incomplete_attempts_not_imported"] == 0
    assert receipt["source_event_sha256"] == {
        str(chapter): value
        for chapter, value in z83.APPROVED_COMPLETED_EVENT_SHA256.items()
    }

    class NoCallTransport:
        def call(self, **_: object) -> None:
            raise AssertionError("完整三章复用不得产生新的主调用或机械重写调用")

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.ApiTransport,
            "from_bundle",
            return_value=NoCallTransport(),
        ):
            metrics = z83.run_main(target, allow_test_run_dir=True)
    assert metrics["seeded_chapters"] == [3, 13, 19]
    assert metrics["newly_sampled_chapters"] == []
    assert metrics["main_live_logical_calls"] == 0
    assert metrics["targeted_retry_logical_calls"] == 0
    assert metrics["network_attempts"] == 3
    assert metrics["network_attempts_imported"] == 3
    assert metrics["network_attempts_this_run"] == 0
    assert metrics["successful_responses"] == 3
    assert metrics["usage_totals"] == {
        "prompt_tokens": 33438,
        "completion_tokens": 49859,
        "total_tokens": 83297,
    }


def test_run_main_with_seed_skips_chapter_3_and_calls_only_13_and_19(
    tmp_path: Path,
) -> None:
    source = _prepare(tmp_path, "source")
    target = _prepare(tmp_path, "target")
    _install_interrupted_main_prefix(source)
    z83.seed_main_samples(target, source, allow_test_run_dir=True)
    stage_dir = target / "main"

    class FakeTransport:
        def __init__(self) -> None:
            self.case_ids: list[str] = []

        def call(
            self, *, stage: str, case_id: str, messages: list[dict]
        ) -> SimpleNamespace:
            self.case_ids.append(case_id)
            assert stage == "neutral_extract"
            chapter = int(case_id.rsplit("ch", 1)[1])
            catalog = z83._catalog(target, chapter)
            payload = {
                "schema_version": z83.neutral_extract.EVENT_SCHEMA_VERSION,
                "chapter": chapter,
                "events": [
                    {
                        "event_id": f"EV-C{chapter:04d}-01",
                        "event": "测试员检查样本并记录结果。",
                        "anchors": [{"anchor_id": str(catalog[0]["anchor_id"])}],
                    }
                ],
            }
            return _install_synthetic_exchange(
                stage_dir=stage_dir,
                stage=stage,
                case_id=case_id,
                body=z83.read_json(target / f"prepared_requests/ch{chapter:04d}.json"),
                content_value=payload,
            )

    fake = FakeTransport()
    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.ApiTransport,
            "from_bundle",
            return_value=fake,
        ):
            metrics = z83.run_main(target, allow_test_run_dir=True)
    assert fake.case_ids == ["z83_main_ch0013", "z83_main_ch0019"]
    assert metrics["seeded_chapters"] == [3]
    assert metrics["newly_sampled_chapters"] == [13, 19]
    assert metrics["network_attempts_imported"] == 1
    assert metrics["network_attempts_this_run"] == 2
    assert metrics["successful_responses"] == 3
    assert [row["chapter"] for row in metrics["main_sample_ledger"]] == [3, 13, 19]
    (target / z83.MAIN_SEED_MANIFEST).unlink()
    with pytest.raises(ZBatchError, match="复用标记与复用清单双向不一致"):
        z83.verify_call_lineage(target, allow_test_run_dir=True)


def test_isolated_copy_drift_fails_prepared_verification(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    contract = run_dir / z83.LOCAL_TRANSPORT
    contract.write_bytes(contract.read_bytes() + b"\n")
    with pytest.raises(ZBatchError, match="隔离副本与冻结来源不再逐字一致"):
        z83.verify_prepared(
            run_dir,
            require_zero_call=True,
            allow_test_run_dir=True,
        )


def test_program_risk_detector_flags_compression_without_final_truth() -> None:
    event = {"event": "检查员确认样本无污染等。"}
    risks = z83._event_risks(event, "检查员确认样本没有污染，没有破损，否则返回汇报。")
    assert "conclusion_compression" in risks
    assert "instruction_compression" in risks


def test_mechanical_retry_uses_closed_reasons_not_raw_anchor_id() -> None:
    raw = ["event_nonspace_chars=120>100", "anchor_id_bad_format:E1108"]
    codes, visible = z83._closed_mechanical_retry_reasons(raw)
    assert codes == ["ANCHOR_ID_INVALID", "EVENT_TOO_LONG"]
    serialized = json.dumps(visible, ensure_ascii=False)
    assert "E1108" not in serialized
    assert "event_nonspace_chars" not in serialized


def test_mechanical_retry_cannot_forge_eligibility_for_valid_event(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(tmp_path)
    _install_historical_v3_main(run_dir)
    event = z83.read_json(run_dir / "main/01_extract/model_json_original/ch0003.json")[
        "events"
    ][0]
    forged = {
        "kind": "existing_mechanical_retry",
        "chapter": 3,
        "original_event_id": event["event_id"],
        "original_event_index": 0,
        "raw_violations_local_only": ["event_nonspace_chars=120>100"],
        "raw_violations_sent_to_model": False,
        "reason_codes": ["EVENT_TOO_LONG"],
        "original_event_sha256": z83.canonical_sha(event),
    }
    with pytest.raises(ZBatchError, match="主响应真实违规集合不一致"):
        z83._validate_main_retry_exchanges(run_dir, [forged])


def test_main_collects_all_three_chapters_before_retry_budget_gate(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(tmp_path)
    stage_dir = run_dir / "main"

    class FakeTransport:
        def __init__(self) -> None:
            self.stages: list[str] = []

        def call(
            self, *, stage: str, case_id: str, messages: list[dict]
        ) -> SimpleNamespace:
            self.stages.append(stage)
            assert stage == "neutral_extract"
            chapter = int(case_id.rsplit("ch", 1)[1])
            body = z83.read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
            payload = {
                "schema_version": z83.neutral_extract.EVENT_SCHEMA_VERSION,
                "chapter": chapter,
                "events": [
                    {
                        "event_id": f"EV-C{chapter:04d}-01",
                        "event": "测试主样张事件内容。",
                        "anchors": [{"anchor_id": "E0001"}],
                    }
                ],
            }
            return _install_synthetic_exchange(
                stage_dir=stage_dir,
                stage=stage,
                case_id=case_id,
                body=body,
                content_value=payload,
            )

    fake = FakeTransport()

    def fake_analysis(data: dict, *, chapter: int, catalog: list[dict]) -> dict:
        counts = {3: 2, 13: 2, 19: 3}
        return {
            "hard_reasons": [],
            "eligible": [{"index": index} for index in range(counts[chapter])],
        }

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with (
            mock.patch.object(
                z83.api_transport.ApiTransport,
                "from_bundle",
                return_value=fake,
            ),
            mock.patch.object(
                z83.z77,
                "analyze_main_response",
                side_effect=fake_analysis,
            ),
            mock.patch.object(z83, "_mechanical_retry") as retry_call,
        ):
            with pytest.raises(ZBatchError, match="三章机械坏条合计超过全轮6条"):
                z83.run_main(run_dir, allow_test_run_dir=True)
    assert fake.stages == ["neutral_extract", "neutral_extract", "neutral_extract"]
    retry_call.assert_not_called()
    hard_stop = z83.read_json(stage_dir / "hard_stop.json")
    assert hard_stop["sampled_chapters"] == [3, 13, 19]
    assert hard_stop["targeted_retry_count"] == 0


def test_split_descendants_keep_source_retry_limit_after_renumber() -> None:
    original = {
        "events": [
            {
                "event_id": "EV-C0003-01",
                "event": "甲做了一件事。",
                "anchors": [{"anchor_id": "E0001"}],
            },
            {
                "event_id": "EV-C0003-02",
                "event": "乙做了另一件事。",
                "anchors": [{"anchor_id": "E0002"}],
            },
        ]
    }
    replacements = {
        0: [
            {"event": "甲完成前半件事。", "anchors": [{"anchor_id": "E0001"}]},
            {"event": "甲完成后半件事。", "anchors": [{"anchor_id": "E0001"}]},
        ]
    }
    final = z83.z77.apply_replacements(original, chapter=3, replacements=replacements)
    lineage, _ = z83._build_event_lineage(
        chapter=3,
        original=original,
        final=final,
        replacements=replacements,
        retry_receipts={0: {"reason_codes": ["EVENT_TOO_LONG"]}},
        stage="main_mechanical_retry",
    )
    rows = {row["current_event_id"]: row for row in lineage["rows"]}
    assert rows["EV-C0003-01"]["source_event_id"] == "EV-C0003-01"
    assert rows["EV-C0003-02"]["source_event_id"] == "EV-C0003-01"
    assert rows["EV-C0003-03"]["source_event_id"] == "EV-C0003-02"
    with pytest.raises(ZBatchError, match="稳定源已经重写过"):
        z83._assert_retry_sources_available(["EV-C0003-02"], rows)
    z83._assert_retry_sources_available(["EV-C0003-03"], rows)


def test_review_builder_has_automatic_old25_and_full_templates(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    _install_historical_v3_main(run_dir)
    receipt = z83.build_review(run_dir, phase="main")
    assert receipt["old25_rows"] == 25
    assert receipt["gold_rows"] == 23
    automatic = z83.read_json(run_dir / "review/old25_automatic_comparison.json")
    assert automatic["schema_version"] == "z83-old25-automatic-comparison-v2"
    assert automatic["method"] == "formal_anchor_first_plus_per_field_bigram_coverage"
    assert automatic["status"] == "routing_only_not_final_truth"
    assert len(automatic["rows"]) == 25
    special = next(row for row in automatic["rows"] if row["record_id"] == "B-C0019-04")
    assert "历史严重后果只作观察" in special["scale_note"]
    assert special["mechanical_prefilter"]["mechanical_only_not_semantic_truth"] is True
    assert {
        row["field"] for row in special["mechanical_prefilter"]["field_coverage"]
    } == {
        "trigger_condition",
        "trigger_action",
    }
    assert receipt["old25_forced_strong_event_ids"]
    assert isinstance(receipt["old25_mechanical_review_candidate_rows"], int)
    template = z83.read_json(run_dir / "review/adjudication_template.json")
    assert len(template["anchor_rows"]) == receipt["event_count"]
    assert all(row["verdict"] is None for row in template["anchor_rows"])


def test_retry13_final_review_keeps_175_human_rows_and_scopes_inspector_to_32(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    receipt = z83.build_review(run_dir, phase="final")
    template = z83.read_json(run_dir / "final_review/adjudication_template.json")
    assert receipt["event_count"] == 175
    assert receipt["final_event_count"] == 175
    assert receipt["human_anchor_event_count"] == 175
    assert receipt["human_anchor_row_count"] == 175
    assert len(template["anchor_rows"]) == 175
    assert receipt["inspector_event_count"] == 32
    assert receipt["inspector_scope"]["event_count_by_chapter"] == {
        "3": 7,
        "13": 7,
        "19": 18,
    }
    batch_ids = []
    for chapter, expected in ((3, 7), (13, 7), (19, 18)):
        batch = z83.read_json(
            run_dir / f"final_review/inspector_batches/ch{chapter:04d}.json"
        )
        assert len(batch["items"]) == expected
        batch_ids.extend(str(item["item_id"]) for item in batch["items"])
    assert sorted(batch_ids) == receipt["inspector_scope"]["event_ids"]
    assert z83._formal_thirteen_retry_target(run_dir) is False
    assert z83._uses_retry11_request_contract(run_dir) is False


def test_retry13_inspector_and_completion_check_use_declared_scope_and_unit_quotes(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    build = z83.build_review(run_dir, phase="final")
    scope_ids = set(build["inspector_scope"]["event_ids"])
    risks_path = run_dir / "final_review/program_risks.json"
    build_path = run_dir / "final_review/build_receipt.json"
    original_risks = z83.read_json(risks_path)
    original_build = z83.read_json(build_path)
    tampered_risks = copy.deepcopy(original_risks)
    victim = sorted(scope_ids)[0]
    tampered_forced = set(tampered_risks["forced_strong_event_ids"])
    if victim in tampered_forced:
        tampered_forced.remove(victim)
    else:
        tampered_forced.add(victim)
    tampered_risks["forced_strong_event_ids"] = sorted(tampered_forced)
    tampered_risks["inspector_forced_strong_event_ids"] = sorted(
        tampered_forced.intersection(scope_ids)
    )
    z83.write_json(risks_path, tampered_risks)
    tampered_build = copy.deepcopy(original_build)
    tampered_build["review_input_sha256"]["program_risks"] = z83.sha256_file(
        risks_path
    )
    z83.write_json(build_path, tampered_build)
    with pytest.raises(ZBatchError, match="可重建强审路由"):
        z83._verify_review_build_inputs(run_dir, phase="final")
    z83.write_json(risks_path, original_risks)
    z83.write_json(build_path, original_build)

    sent_chapters: list[int] = []

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        payload = json.loads(body["messages"][1]["content"])
        chapter = int(payload["batch_id"].split("CH", 1)[1].split("-", 1)[0])
        sent_chapters.append(chapter)
        return FakeResponse(
            _retry06_fake_response(body, punctuation_equivalent_drift=True)
        )

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83, "_retry13_no_redirect_open", side_effect=opener
        ):
            receipt = z83.run_inspector(
                run_dir,
                phase="final",
                allow_test_run_dir=True,
            )
    assert receipt["event_count"] == 32
    assert receipt["final_event_count"] == 175
    assert receipt["inspector_event_count"] == 32
    assert len(receipt["routes"]) == 32
    assert {str(row["item_id"]) for row in receipt["routes"]} == scope_ids
    assert sent_chapters
    assert receipt["new_called_chapters"] == sent_chapters
    assert receipt["network_attempts"] == len(sent_chapters)
    assert receipt["evidence_quote_policy"] == (
        z83.pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
    )
    assert receipt["minimum_quote_nonspace_chars"] == 6
    assert receipt["punctuation_unit_equivalence_sha256"] == (
        z83.pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
    )
    assert z83.require_inspector_complete(run_dir, phase="final") == receipt
    adjudication = _completed_adjudication(run_dir, phase="final")
    events_by_chapter = {
        chapter: sorted(
            event_id
            for event_id in z83._event_map(run_dir / "final")
            if int(event_id[4:8]) == chapter
        )
        for chapter in z83.TARGET_CHAPTERS
    }
    for row in adjudication["current_rows"]:
        if row["verdict"] != "not_observed":
            row["candidate_event_ids"] = [events_by_chapter[row["chapter"]][0]]
        if row["record_id"] in {"B-C0013-02", "B-C0019-04"}:
            row["verdict"] = "preserved"
            row["candidate_event_ids"] = [events_by_chapter[row["chapter"]][0]]
            row["reason"] = "测试夹具把两条指定记录判为完整保留。"
    for row in adjudication["gold_rows"]:
        if row["verdict"] != "miss":
            row["candidate_event_ids"] = [events_by_chapter[3][0]]
        if row["verdict"] == "coverage_only_invalid_support":
            row["verdict"] = "semantic_shadow"
            row["reason"] = "测试夹具把来源关系判为有效语义影子。"
    adjudication_path = run_dir / "final_review/adjudication_all_clear.json"
    z83.write_json(adjudication_path, adjudication)
    scorecard = z83.finalize(
        run_dir,
        adjudication_path,
        allow_test_run_dir=True,
    )
    assert scorecard["four_gates"] == {
        "mechanical_three_gates": True,
        "old25_zero_regression": True,
        "chapter3_gold_floor": True,
        "semantic_anchor_invalid_zero": True,
    }
    call_lineage = z83.read_json(run_dir / "final/call_lineage_verification.json")
    assert call_lineage["final_mechanical_sha256"] == z83.canonical_sha(
        z83.read_json(run_dir / "final/mechanical_verification.json")
    )
    checkpoint_request = next(
        (run_dir / "final_review/inspector").glob(
            "ch*/run/checkpoint/01_request.json"
        )
    )
    tampered_checkpoint = z83.read_json(checkpoint_request)
    tampered_checkpoint["model"] = "tampered-model"
    z83.write_json(checkpoint_request, tampered_checkpoint)
    with pytest.raises(ZBatchError, match="检查点|引用漂移"):
        z83.require_inspector_complete(run_dir, phase="final")


def test_retry13_final_inspector_429_retries_exact_request_and_checkpoints(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    z83.build_review(run_dir, phase="final")
    sent_wire: list[bytes] = []
    calls = 0

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        nonlocal calls
        calls += 1
        wire = bytes(request.data)  # type: ignore[attr-defined]
        sent_wire.append(wire)
        if calls == 1:
            raise z83.api_transport.urllib.error.HTTPError(
                str(request.full_url),  # type: ignore[attr-defined]
                429,
                "rate limited",
                {"Retry-After": "0"},
                io.BytesIO(b'{"error":"rate limited"}'),
            )
        return FakeResponse(_retry06_fake_response(json.loads(wire), punctuation_equivalent_drift=True))

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83, "_retry13_no_redirect_open", side_effect=opener
        ):
            receipt = z83.run_inspector(
                run_dir, phase="final", allow_test_run_dir=True
            )
    assert receipt["event_count"] == 32
    assert receipt["network_attempts"] == receipt["logical_model_calls"] + 1
    assert sent_wire[0] == sent_wire[1]
    first_attempts = z83.z68.read_jsonl(
        run_dir / "final_review/inspector/ch0003/run/call_attempts.jsonl"
    )
    assert [row["http_status"] for row in first_attempts] == [429, 200]
    assert first_attempts[0]["usage"] == z83.z83_retry_transport.UNKNOWN_USAGE
    checkpoint_paths = list(
        (run_dir / "final_review/inspector").glob("ch*/run/checkpoint/05_seal.json")
    )
    assert len(checkpoint_paths) == receipt["logical_model_calls"]
    assert z83.require_inspector_complete(run_dir, phase="final") == receipt


@pytest.mark.parametrize("failure", ["http_500", "network"])
def test_retry13_final_inspector_non429_failure_never_retries_or_continues(
    tmp_path: Path,
    failure: str,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    z83.build_review(run_dir, phase="final")
    calls = 0

    def opener(request: object, *, timeout: int) -> object:
        nonlocal calls
        calls += 1
        if failure == "network":
            raise z83.api_transport.urllib.error.URLError("offline")
        raise z83.api_transport.urllib.error.HTTPError(
            str(request.full_url),  # type: ignore[attr-defined]
            500,
            "server error",
            {},
            io.BytesIO(b'{"error":"server"}'),
        )

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83, "_retry13_no_redirect_open", side_effect=opener
        ):
            with pytest.raises(z83.z83_retry_transport.RetryTransportHardStop):
                z83.run_inspector(
                    run_dir, phase="final", allow_test_run_dir=True
                )
    assert calls == 1
    root = run_dir / "final_review/inspector"
    assert (root / "hard_stop.json").is_file()
    assert not (root / "combined_routing.json").exists()
    assert not list(root.glob("ch0013/run/requests/**/*.json"))
    seal = z83.z83_retry_transport.validate_checkpoint_bundle(
        root / "ch0003/run/checkpoint"
    )
    assert seal["mechanical_verdict"] == "fail"


def test_retry13_final_inspector_rejects_redirect_without_forwarding_authorization(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    z83.build_review(run_dir, phase="final")
    opened: list[tuple[str, str | None]] = []
    handlers: list[object] = []

    class FakeOpener:
        def open(self, request: object, *, timeout: int) -> object:
            assert timeout == 300
            opened.append(
                (
                    str(request.full_url),  # type: ignore[attr-defined]
                    request.get_header("Authorization"),  # type: ignore[attr-defined]
                )
            )
            raise z83.api_transport.urllib.error.HTTPError(
                str(request.full_url),  # type: ignore[attr-defined]
                302,
                "redirect forbidden",
                {"Location": "https://redirect.invalid/steal"},
                io.BytesIO(b"redirect"),
            )

    def build_opener(*received: object) -> FakeOpener:
        handlers.extend(received)
        return FakeOpener()

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "build_opener",
            side_effect=build_opener,
        ):
            with pytest.raises(
                z83.z83_retry_transport.RetryTransportHardStop,
                match="302",
            ):
                z83.run_inspector(run_dir, phase="final", allow_test_run_dir=True)
    assert any(isinstance(row, z83._Retry13NoRedirectHandler) for row in handlers)
    assert len(opened) == 1
    assert opened[0][0] != "https://redirect.invalid/steal"
    assert opened[0][1] == "Bearer test-only"
    attempts = z83.z68.read_jsonl(
        run_dir / "final_review/inspector/ch0003/run/call_attempts.jsonl"
    )
    assert len(attempts) == 1
    assert attempts[0]["http_status"] == 302


def test_retry13_inspector_readback_recomputes_wire_sha_from_frozen_body(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    z83.build_review(run_dir, phase="final")

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        return FakeResponse(_retry06_fake_response(body, punctuation_equivalent_drift=True))

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(z83, "_retry13_no_redirect_open", side_effect=opener):
            z83.run_inspector(run_dir, phase="final", allow_test_run_dir=True)
    attempts_path = (
        run_dir / "final_review/inspector/ch0003/run/call_attempts.jsonl"
    )
    attempts = z83.z68.read_jsonl(attempts_path)
    attempts[0]["wire_body_sha256"] = "f" * 64
    attempts[0]["row_sha256"] = z83.canonical_sha(
        {key: value for key, value in attempts[0].items() if key != "row_sha256"}
    )
    attempts_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in attempts
        ),
        encoding="utf-8",
    )
    with pytest.raises(ZBatchError, match="五件检查点"):
        z83.require_inspector_complete(run_dir, phase="final")


def test_retry13_call_lineage_uses_atomic_artifacts_not_legacy_array_contract(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    assert not (run_dir / "repair/retry_plan.json").exists()
    assert not (run_dir / "repair/run_manifest.json").exists()
    receipt = z83.verify_call_lineage(run_dir, allow_test_run_dir=True)
    assert receipt["status"] == "pass"
    assert receipt["repair_contract"] == "retry13_atomic_single_object"
    assert receipt["repair_parent_rewrite_count"] == 13
    assert receipt["repair_logical_request_count"] == 32
    assert receipt["repair_declared_review_event_count"] == 32
    assert receipt["repair_materialized_event_count"] == 175
    assert "retry_plan_sha256" not in receipt


def test_retry13_runner_rebuilds_results_from_raw_checkpoint_and_rejects_tamper(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    plan = retry13._validate_plan(run_dir)
    rebuilt = retry13._rebuild_all_task_results(run_dir=run_dir, plan=plan)
    assert len(rebuilt) == 32
    task_id = str(plan["tasks"][0]["task_id"])
    result_path = run_dir / f"repair/results/{task_id}.json"
    original_result = z83.read_json(result_path)
    tampered_result = copy.deepcopy(original_result)
    tampered_result["normalized_replacement"]["event"] += "篡改"
    tampered_result["normalized_replacement_sha256"] = z83.canonical_sha(
        tampered_result["normalized_replacement"]
    )
    z83.write_json(result_path, tampered_result)
    with pytest.raises(ZBatchError, match="不能从原始五件套重建"):
        retry13._rebuild_all_task_results(run_dir=run_dir, plan=plan)
    z83.write_json(result_path, original_result)

    checkpoint_response = z83.read_json(
        run_dir / f"repair/checkpoints/{task_id}/02_response.json"
    )
    raw_path = run_dir / str(checkpoint_response["raw_response_path"])
    raw_path.write_bytes(raw_path.read_bytes() + b"\n")
    with pytest.raises(ZBatchError, match="无法相互重建"):
        retry13._rebuild_all_task_results(run_dir=run_dir, plan=plan)


def test_retry13_main_readback_recomputes_wire_sha_from_frozen_body(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    plan = retry13._validate_plan(run_dir)
    task = plan["tasks"][0]
    task_id = str(task["task_id"])
    fake_wire_sha = "f" * 64

    attempts_path = run_dir / "repair/call_attempts.jsonl"
    attempts = z83.z68.read_jsonl(attempts_path)
    target_attempt = next(
        row for row in attempts if row["logical_request_id"] == task_id
    )
    target_attempt["wire_body_sha256"] = fake_wire_sha
    target_attempt["row_sha256"] = z83.canonical_sha(
        {key: value for key, value in target_attempt.items() if key != "row_sha256"}
    )
    attempts_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in attempts
        ),
        encoding="utf-8",
    )

    checkpoint_root = run_dir / f"repair/checkpoints/{task_id}"
    request_doc = z83.read_json(checkpoint_root / "01_request.json")
    request_doc["wire_body_sha256"] = fake_wire_sha
    z83.write_json(checkpoint_root / "01_request.json", request_doc)
    attempt_doc = z83.read_json(checkpoint_root / "04_attempts.json")
    attempt_doc["rows"][0] = copy.deepcopy(target_attempt)
    z83.write_json(checkpoint_root / "04_attempts.json", attempt_doc)
    seal = z83.read_json(checkpoint_root / "05_seal.json")
    seal["artifacts"]["request"]["sha256"] = z83.sha256_file(
        checkpoint_root / "01_request.json"
    )
    seal["artifacts"]["attempts"]["sha256"] = z83.sha256_file(
        checkpoint_root / "04_attempts.json"
    )
    seal_without_id = {
        key: value for key, value in seal.items() if key != "checkpoint_id"
    }
    seal["checkpoint_id"] = z83.z83_retry_transport._sha256_json(seal_without_id)
    z83.write_json(checkpoint_root / "05_seal.json", seal)

    with pytest.raises(ZBatchError, match="无法相互重建"):
        retry13._rebuild_task_result(run_dir=run_dir, plan=plan, task=task)


def test_retry13_call_lineage_rejects_self_consistent_repair_not_from_results(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    first_parent = z83.z68.read_jsonl(
        run_dir / "repair/targeted_retry_ledger.jsonl"
    )[0]
    chapter = int(first_parent["chapter"])
    descendant_id = str(first_parent["materialized_event_ids"][0])
    model_path = z83._model_file(run_dir / "repair", chapter)
    model = z83.read_json(model_path)
    changed = next(
        event for event in model["events"] if event["event_id"] == descendant_id
    )
    changed["event"] = "测试人物伪造了一条与原子结果无关的改写。"
    rebuilt_events, rebuilt_audit = z83.neutral_extract.process_model_data(
        model,
        chapter=chapter,
        catalog=z83._catalog(run_dir, chapter),
    )
    z83.write_json(model_path, model)
    z83.write_json(z83._event_file(run_dir / "repair", chapter), rebuilt_events)
    z83.write_json(
        run_dir / f"repair/01_extract/program_audits/ch{chapter:04d}.json",
        rebuilt_audit,
    )
    lineage_path = z83._lineage_file(run_dir / "repair", chapter)
    lineage = z83.read_json(lineage_path)
    changed_event = next(
        event for event in rebuilt_events["events"] if event["event_id"] == descendant_id
    )
    lineage_row = next(
        row for row in lineage["rows"] if row["current_event_id"] == descendant_id
    )
    lineage_row["current_event_sha256"] = z83.canonical_sha(changed_event)
    z83.write_json(lineage_path, lineage)
    mechanical = z83.verify_event_stage(
        run_dir,
        run_dir / "repair",
        schema_version="z83-retry13-repair-mechanical-verification-v1",
    )
    metrics_path = run_dir / "repair/01_extract/metrics.json"
    metrics = z83.read_json(metrics_path)
    metrics["mechanical_verification_sha256"] = z83.canonical_sha(mechanical)
    z83.write_json(metrics_path, metrics)
    shutil.copytree(
        run_dir / "repair/01_extract",
        run_dir / "final/01_extract",
        dirs_exist_ok=True,
    )

    with pytest.raises(ZBatchError, match="不能从32份原子结果反向重建"):
        z83.verify_call_lineage(run_dir, allow_test_run_dir=True)


def test_retry13_call_lineage_rejects_non429_then_success_attempts(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    attempts_path = run_dir / "repair/call_attempts.jsonl"
    attempts = z83.z68.read_jsonl(attempts_path)
    original = attempts[0]
    failed = copy.deepcopy(original)
    failed.update(
        {
            "http_status": 500,
            "outcome": "http_error",
            "raw_response_sha256": None,
            "usage": "unknown",
            "error_code": "http_500",
            "error_body_sha256": "0" * 64,
            "usage_status": "unknown",
        }
    )
    failed["row_sha256"] = z83.canonical_sha(
        {key: value for key, value in failed.items() if key != "row_sha256"}
    )
    success = copy.deepcopy(original)
    success.update(
        {
            "attempt": 2,
            "previous_attempt": 1,
            "pre_request_spacing_planned_seconds": 0.0,
            "pre_request_spacing_seconds": 0.0,
        }
    )
    success["row_sha256"] = z83.canonical_sha(
        {key: value for key, value in success.items() if key != "row_sha256"}
    )
    attempts = [failed, success, *attempts[1:]]
    attempts_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in attempts
        ),
        encoding="utf-8",
    )

    reservations_path = run_dir / "repair/attempt_reservations.jsonl"
    reservations = z83.z68.read_jsonl(reservations_path)
    second_reservation = copy.deepcopy(reservations[0])
    second_reservation["attempt"] = 2
    second_reservation["row_sha256"] = z83.canonical_sha(
        {
            key: value
            for key, value in second_reservation.items()
            if key != "row_sha256"
        }
    )
    reservations = [reservations[0], second_reservation, *reservations[1:]]
    reservations_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in reservations
        ),
        encoding="utf-8",
    )
    for path in (
        run_dir / "repair/retry13_run_manifest.json",
        run_dir / "repair/01_extract/metrics.json",
    ):
        document = z83.read_json(path)
        document["network_attempts"] = 33
        z83.write_json(path, document)

    with pytest.raises(ZBatchError, match="子请求尝试序列"):
        z83.verify_call_lineage(run_dir, allow_test_run_dir=True)


def test_retry13_call_lineage_rejects_short_inter_request_spacing(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    attempts_path = run_dir / "repair/call_attempts.jsonl"
    attempts = z83.z68.read_jsonl(attempts_path)
    attempts[1]["started_at"] = attempts[0]["finished_at"]
    short_finished = datetime.fromisoformat(attempts[1]["started_at"]) + timedelta(
        seconds=1
    )
    attempts[1]["finished_at"] = short_finished.isoformat(timespec="seconds")
    attempts[1]["pre_request_spacing_planned_seconds"] = 0.0
    attempts[1]["pre_request_spacing_seconds"] = 0.0
    attempts[1]["row_sha256"] = z83.canonical_sha(
        {
            key: value
            for key, value in attempts[1].items()
            if key != "row_sha256"
        }
    )
    attempts_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in attempts
        ),
        encoding="utf-8",
    )

    with pytest.raises(ZBatchError, match="首发间隔"):
        z83.verify_call_lineage(run_dir, allow_test_run_dir=True)


def test_retry13_call_lineage_rejects_attempt_finishing_before_it_starts(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    attempts_path = run_dir / "repair/call_attempts.jsonl"
    attempts = z83.z68.read_jsonl(attempts_path)
    original = attempts[0]
    first_started = datetime.fromisoformat(original["started_at"])
    throttled = copy.deepcopy(original)
    throttled.update(
        {
            "http_status": 429,
            "outcome": "http_error",
            "raw_response_sha256": None,
            "usage": "unknown",
            "error_code": "http_429",
            "error_body_sha256": "0" * 64,
            "retry_wait_seconds": 5.0,
            "retry_wait_actual_seconds": None,
            "usage_status": "unknown",
        }
    )
    throttled["row_sha256"] = z83.canonical_sha(
        {key: value for key, value in throttled.items() if key != "row_sha256"}
    )
    success = copy.deepcopy(original)
    success.update(
        {
            "attempt": 2,
            "previous_attempt": 1,
            "started_at": (first_started + timedelta(seconds=6)).isoformat(
                timespec="seconds"
            ),
            "finished_at": (first_started + timedelta(seconds=1)).isoformat(
                timespec="seconds"
            ),
            "pre_request_spacing_planned_seconds": 0.0,
            "pre_request_spacing_seconds": 0.0,
        }
    )
    success["row_sha256"] = z83.canonical_sha(
        {key: value for key, value in success.items() if key != "row_sha256"}
    )
    attempts = [throttled, success, *attempts[1:]]
    attempts_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in attempts
        ),
        encoding="utf-8",
    )
    z83.z83_retry_transport._append_retry_wait_receipt(
        attempts_path,
        logical_request_id=str(throttled["logical_request_id"]),
        chapter=int(throttled["chapter"]),
        attempt=1,
        attempt_row_sha256=str(throttled["row_sha256"]),
        planned_seconds=5.0,
        actual_seconds=5.0,
        status="completed",
        started_at=str(throttled["finished_at"]),
        finished_at=str(success["started_at"]),
        interruption_type=None,
    )

    reservations_path = run_dir / "repair/attempt_reservations.jsonl"
    reservations = z83.z68.read_jsonl(reservations_path)
    second_reservation = copy.deepcopy(reservations[0])
    second_reservation["attempt"] = 2
    second_reservation["row_sha256"] = z83.canonical_sha(
        {
            key: value
            for key, value in second_reservation.items()
            if key != "row_sha256"
        }
    )
    reservations = [reservations[0], second_reservation, *reservations[1:]]
    reservations_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in reservations
        ),
        encoding="utf-8",
    )
    for path in (
        run_dir / "repair/retry13_run_manifest.json",
        run_dir / "repair/01_extract/metrics.json",
    ):
        document = z83.read_json(path)
        document["network_attempts"] = 33
        document["http_429_count"] = 1
        z83.write_json(path, document)

    with pytest.raises(ZBatchError, match="子请求尝试序列"):
        z83.verify_call_lineage(run_dir, allow_test_run_dir=True)


def test_retry13_call_lineage_rejects_future_http_date_disguised_as_short_wait(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    _install_synthetic_retry13_atomic_candidate(run_dir)
    attempts_path = run_dir / "repair/call_attempts.jsonl"
    attempts = z83.z68.read_jsonl(attempts_path)
    original = attempts[0]
    first_started = datetime.fromisoformat(original["started_at"])
    future_retry_after = format_datetime(
        (first_started + timedelta(seconds=600)).astimezone(timezone.utc),
        usegmt=True,
    )
    throttled = copy.deepcopy(original)
    throttled.update(
        {
            "http_status": 429,
            "outcome": "http_error",
            "raw_response_sha256": None,
            "usage": "unknown",
            "retry_after_raw": future_retry_after,
            "retry_after_seconds": 5.0,
            "error_code": "http_429",
            "error_body_sha256": "0" * 64,
            "retry_wait_seconds": 5.0,
            "retry_wait_actual_seconds": None,
            "usage_status": "unknown",
        }
    )
    throttled["row_sha256"] = z83.canonical_sha(
        {key: value for key, value in throttled.items() if key != "row_sha256"}
    )
    success = copy.deepcopy(original)
    success.update(
        {
            "attempt": 2,
            "previous_attempt": 1,
            "started_at": (first_started + timedelta(seconds=6)).isoformat(
                timespec="seconds"
            ),
            "finished_at": (first_started + timedelta(seconds=7)).isoformat(
                timespec="seconds"
            ),
            "pre_request_spacing_planned_seconds": 0.0,
            "pre_request_spacing_seconds": 0.0,
        }
    )
    success["row_sha256"] = z83.canonical_sha(
        {key: value for key, value in success.items() if key != "row_sha256"}
    )
    shifted_attempts = []
    for row in attempts[1:]:
        shifted = copy.deepcopy(row)
        shifted["started_at"] = (
            datetime.fromisoformat(str(shifted["started_at"]))
            + timedelta(seconds=6)
        ).isoformat(timespec="seconds")
        shifted["finished_at"] = (
            datetime.fromisoformat(str(shifted["finished_at"]))
            + timedelta(seconds=6)
        ).isoformat(timespec="seconds")
        shifted["row_sha256"] = z83.canonical_sha(
            {
                key: value
                for key, value in shifted.items()
                if key != "row_sha256"
            }
        )
        shifted_attempts.append(shifted)
    attempts = [throttled, success, *shifted_attempts]
    attempts_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in attempts
        ),
        encoding="utf-8",
    )
    z83.z83_retry_transport._append_retry_wait_receipt(
        attempts_path,
        logical_request_id=str(throttled["logical_request_id"]),
        chapter=int(throttled["chapter"]),
        attempt=1,
        attempt_row_sha256=str(throttled["row_sha256"]),
        planned_seconds=5.0,
        actual_seconds=5.0,
        status="completed",
        started_at=str(throttled["finished_at"]),
        finished_at=str(success["started_at"]),
        interruption_type=None,
    )

    reservations_path = run_dir / "repair/attempt_reservations.jsonl"
    reservations = z83.z68.read_jsonl(reservations_path)
    second_reservation = copy.deepcopy(reservations[0])
    second_reservation["attempt"] = 2
    second_reservation["row_sha256"] = z83.canonical_sha(
        {
            key: value
            for key, value in second_reservation.items()
            if key != "row_sha256"
        }
    )
    reservations = [reservations[0], second_reservation, *reservations[1:]]
    reservations_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in reservations
        ),
        encoding="utf-8",
    )
    for path in (
        run_dir / "repair/retry13_run_manifest.json",
        run_dir / "repair/01_extract/metrics.json",
    ):
        document = z83.read_json(path)
        document["network_attempts"] = 33
        document["http_429_count"] = 1
        z83.write_json(path, document)

    with pytest.raises(ZBatchError, match="子请求尝试序列"):
        z83.verify_call_lineage(run_dir, allow_test_run_dir=True)


def test_inspector_missing_key_stops_before_global_claim(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    _install_historical_v3_main(run_dir)
    z83.build_review(run_dir, phase="main")
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ZBatchError, match="发网前0调用拒绝"):
            z83.run_inspector(run_dir, phase="main", allow_test_run_dir=True)
    assert not (run_dir / "review/inspector").exists()


def test_retry04_inspector_preflight_rebuilds_retry03_and_changes_only_max_tokens(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry04_review_from_retry03(tmp_path)
    contract_path = run_dir / z83.LOCAL_INSPECTOR_CONTRACT
    receipt = z83._preflight_inspector_requests(
        run_dir,
        phase="main",
        review_dir=run_dir / "review",
        contract_path=contract_path,
    )
    assert receipt["status"] == "pass_zero_call_single_variable_8000_to_32000"
    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0
    assert len(receipt["rows"]) == 3
    for row in receipt["rows"]:
        assert row["differences"] == [
            {
                "path": "$.body.max_tokens",
                "before": 8000,
                "after": 32000,
            }
        ]
    assert receipt["rows"][0]["retry03_actual_request_rebuilt_exactly"] is True
    assert receipt["rows"][0]["retry03_actual_request_sha256"] == (
        z83.APPROVED_RETRY03_INSPECTOR_REQUEST_SHA256
    )
    assert not (run_dir / "review/inspector").exists()

    event_path = run_dir / "main/01_extract/events/ch0013.json"
    original_event_bytes = event_path.read_bytes()
    tampered = z83.read_json(event_path)
    tampered["events"][0]["event"] += "篡改"
    z83.write_json(event_path, tampered)
    with pytest.raises(ZBatchError, match="事件SHA漂移"):
        z83._preflight_inspector_requests(
            run_dir,
            phase="main",
            review_dir=run_dir / "review",
            contract_path=contract_path,
        )
    assert not (run_dir / "review/inspector").exists()

    event_path.write_bytes(original_event_bytes)
    tampered = z83.read_json(event_path)
    tampered["events"][0]["event"] += "第二次篡改"
    z83.write_json(event_path, tampered)
    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with pytest.raises(ZBatchError, match="复核材料与build票不一致|事件SHA漂移"):
            z83.run_inspector(
                run_dir,
                phase="main",
                allow_test_run_dir=True,
            )
    preflight_stop = run_dir / "review/inspector_preflight_hard_stop.json"
    assert (
        z83.read_json(preflight_stop)["status"] == "hard_stop_before_claim_and_network"
    )
    assert not (run_dir / "review/inspector").exists()
    event_path.write_bytes(original_event_bytes)
    with pytest.raises(ZBatchError, match="已有硬停票"):
        z83.run_inspector(
            run_dir,
            phase="main",
            allow_test_run_dir=True,
        )


def test_retry05_preflight_rebuilds_retry04_and_only_appends_verbatim_rule(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry05_review_from_retry03(tmp_path)
    contract_path = run_dir / z83.LOCAL_INSPECTOR_CONTRACT
    receipt = z83._preflight_inspector_requests(
        run_dir,
        phase="main",
        review_dir=run_dir / "review",
        contract_path=contract_path,
    )
    assert receipt["status"] == (
        "pass_zero_call_single_variable_retry04_to_retry05_verbatim_quote"
    )
    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0
    assert receipt["baseline_contract_sha256"] == z83.sha256_file(contract_path)
    assert receipt["candidate_contract_sha256"] == z83.sha256_file(contract_path)
    assert receipt["shared_8000_parent_contract_sha256"] == z83.sha256_file(
        z83.INSPECTOR_CONTRACT
    )
    assert receipt["system_prompt_suffix"] == z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
    assert (
        receipt["inspector_source"]
        == z83.read_json(run_dir / "preflight.json")["producer_dependencies"][
            "pipeline_inspector"
        ]
    )
    assert (
        receipt["transport_source"]
        == z83.read_json(run_dir / "preflight.json")["producer_dependencies"][
            "api_transport"
        ]
    )
    expected_difference = [
        {
            "path": "$.body.messages[0].content",
            "before": z83.pipeline_inspector.SYSTEM_PROMPT,
            "after": (
                f"{z83.pipeline_inspector.SYSTEM_PROMPT}\n"
                f"{z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE}"
            ),
        }
    ]
    retry04_reference = z83._retry04_inspector_reference()
    reference_shas = retry04_reference["candidate_request_sha256"]
    for row in receipt["rows"]:
        assert row["differences"] == expected_difference
        assert row["retry04_request_rebuilt_exactly"] is True
        assert row["baseline_request_sha256"] == reference_shas[str(row["chapter"])]
        assert row["candidate_request_sha256"] != row["baseline_request_sha256"]
    assert not (run_dir / "review/inspector").exists()


def test_retry06_preflight_keeps_retry05_requests_byte_equivalent(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry06_review_from_retry03(tmp_path)
    contract_path = run_dir / z83.LOCAL_INSPECTOR_CONTRACT
    receipt = z83._preflight_inspector_requests(
        run_dir,
        phase="main",
        review_dir=run_dir / "review",
        contract_path=contract_path,
    )
    assert receipt["status"] == (
        "pass_zero_call_retry05_to_retry06_program_only_no_request_change"
    )
    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0
    assert receipt["only_allowed_difference"] == (
        "none_request_identical_program_side_only"
    )
    assert receipt["system_prompt_suffix"] == z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
    assert receipt["program_side_quote_contract"] == {
        "anchor_id_authoritative": True,
        "formal_quote_program_filled_from_frozen_catalog": True,
        "model_quote_role": "consistency_check_only",
        "model_quote_must_be_contiguous_substring": True,
        "minimum_quote_nonspace_chars": 6,
        "request_changed_from_retry05": False,
    }
    reference = z83._retry05_inspector_reference()
    assert receipt["retry05_reference_sha256"] == z83.canonical_sha(reference)
    assert reference["chapter3"]["source_usage_imported"] is False
    assert reference["chapter13"]["imported_as_result"] is False
    for row in receipt["rows"]:
        assert row["differences"] == []
        assert row["retry05_request_rebuilt_exactly"] is True
        assert (
            row["candidate_request_sha256"]
            == reference["candidate_request_sha256"][str(row["chapter"])]
        )
    assert not (run_dir / "review/inspector").exists()


def test_retry07_preflight_keeps_retry06_requests_byte_equivalent_and_freezes_mapping(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry07_review_from_retry03(tmp_path)
    contract_path = run_dir / z83.LOCAL_INSPECTOR_CONTRACT
    receipt = z83._preflight_inspector_requests(
        run_dir,
        phase="main",
        review_dir=run_dir / "review",
        contract_path=contract_path,
    )
    assert receipt["status"] == (
        "pass_zero_call_retry06_to_retry07_punctuation_compare_only_no_request_change"
    )
    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0
    assert receipt["only_allowed_difference"] == (
        "none_request_identical_program_side_only"
    )
    reference = z83._retry06_inspector_reference()
    assert receipt["retry06_reference_sha256"] == z83.canonical_sha(reference)
    assert reference["chapter13"]["imported_as_result"] is False
    assert reference["chapter19"]["status"] == "not_called"
    for row in receipt["rows"]:
        assert row["differences"] == []
        assert row["retry06_request_rebuilt_exactly"] is True
        assert (
            row["candidate_request_sha256"]
            == reference["candidate_request_sha256"][str(row["chapter"])]
        )
    mapping_path = run_dir / z83.RETRY07_PUNCTUATION_EQUIVALENCE
    mapping = z83.read_json(mapping_path)
    assert mapping == z83.pipeline_inspector.quote_punctuation_equivalence_contract()
    assert (
        receipt["program_side_quote_contract"]["punctuation_equivalence_sha256"]
        == z83.pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
    )
    assert not (run_dir / "review/inspector").exists()


def test_retry07_reference_reads_retry06_as_rejected_evidence_only() -> None:
    reference = z83._retry06_inspector_reference()
    row = reference["chapter13"]
    assert row["status"] == "rejected_never_reuse"
    assert row["model_evidence_rows"] == 64
    assert row["anchor_ids_legal"] is True
    assert row["normalization_rescued_rows"] == 1
    assert row["rescued_item_id"] == "EV-C0013-03"
    assert row["rescued_anchor_id"] == "E0006"
    assert row["imported_as_result"] is False
    assert row["full_response_contract_still_invalid"] is True
    assert row["full_parse_failure"] == ("EV-C0013-03.evidence.reason 必须是非空字符串")
    assert row["observed_byte_level_difference"] == {
        "offset": 5,
        "model_character": ".",
        "model_codepoint": "U+002E",
        "formal_character": "。",
        "formal_codepoint": "U+3002",
        "authority_wording_discrepancy": (
            "续令写右引号替换；封存原始字节实际为句号全半角替换"
        ),
    }


def test_retry08_preflight_keeps_retry06_requests_and_freezes_unit_contract(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry08_review_from_retry03(tmp_path)
    contract_path = run_dir / z83.LOCAL_INSPECTOR_CONTRACT
    receipt = z83._preflight_inspector_requests(
        run_dir,
        phase="main",
        review_dir=run_dir / "review",
        contract_path=contract_path,
    )
    assert receipt["status"] == (
        "pass_zero_call_retry07_to_retry08_punctuation_unit_compare_and_raw_rebuild_only_no_request_change"
    )
    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0
    assert receipt["only_allowed_difference"] == (
        "none_request_identical_program_side_only"
    )
    retry06_reference = z83._retry06_inspector_reference()
    retry07_reference = z83._retry07_preflight_hard_stop_reference()
    assert receipt["retry06_reference_sha256"] == z83.canonical_sha(
        retry06_reference
    )
    assert receipt["retry07_preflight_hard_stop_reference_sha256"] == (
        z83.canonical_sha(retry07_reference)
    )
    assert retry07_reference["model_api_calls"] == 0
    assert retry07_reference["artifacts_imported_as_result"] is False
    for row in receipt["rows"]:
        assert row["differences"] == []
        assert row["retry06_request_rebuilt_exactly"] is True
        assert row["candidate_request_sha256"] == (
            retry06_reference["candidate_request_sha256"][str(row["chapter"])]
        )
    mapping_path = run_dir / z83.RETRY08_PUNCTUATION_UNIT_EQUIVALENCE
    assert z83.read_json(mapping_path) == (
        z83.pipeline_inspector.quote_punctuation_unit_equivalence_contract()
    )
    assert receipt["program_side_quote_contract"][
        "punctuation_unit_equivalence_sha256"
    ] == z83.pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
    assert receipt["program_side_quote_contract"][
        "raw_response_usage_rebuild_required"
    ] is True
    assert not (run_dir / "review/inspector").exists()


def test_retry09_reuses_retry08_review_evidence_without_new_inspector_call(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry09_review_from_retry03(tmp_path)
    mapping_path = run_dir / z83.RETRY08_PUNCTUATION_UNIT_EQUIVALENCE
    assert z83.read_json(mapping_path) == (
        z83.pipeline_inspector.quote_punctuation_unit_equivalence_contract()
    )
    with pytest.raises(ZBatchError, match="只能零调用复用retry08"):
        z83.run_inspector(run_dir, phase="main", allow_test_run_dir=True)
    receipt = z83.reuse_retry08_inspector_evidence(
        run_dir,
        allow_test_run_dir=True,
    )
    assert receipt["status"] == "pass_zero_call_reference_only_not_final_truth"
    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0
    assert receipt["reused_chapters"] == [3, 13, 19]
    assert receipt["new_called_chapters"] == []
    assert receipt["source_usage_imported"] is False
    assert receipt["source_network_attempts_imported"] is False
    assert receipt["source_combined_routing_file_sha256"] == (
        z83.RETRY08_FROZEN_REVIEW_SHA256["combined_routing"]
    )
    assert receipt["source_routes_sha256"] == (
        "aa0d186444611ab25d1b968ec4f347b5cd045d021d46e8cd9006e14cbdb55809"
    )
    assert not (run_dir / "review/inspector").exists()


def test_retry09_capacity_audit_hard_stops_before_plan_or_api(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry09_review_from_retry03(tmp_path)
    z83.reuse_retry08_inspector_evidence(
        run_dir,
        allow_test_run_dir=True,
    )
    formal_adjudication = (
        z83.ROOT
        / "runs"
        / z83.APPROVED_CAPACITY_OVERRIDE_TARGET_NAME
        / "review/adjudication_completed.json"
    )
    adjudication = z83.read_json(formal_adjudication)
    adjudication_path = run_dir / "review/adjudication_completed.json"
    z83.write_json(adjudication_path, adjudication)

    receipt = z83.record_retry09_capacity_hard_stop(
        run_dir,
        adjudication_path,
        allow_test_run_dir=True,
    )

    assert receipt["status"] == (
        "hard_stop_before_retry_plan_total_capacity_exceeded"
    )
    assert receipt["completed_before_stop"]["full_semantic_adjudication"][
        "row_count"
    ] == 246
    assert receipt["capacity_contract"]["capacity_expression"] == "4 + 9 = 13 > 6"
    assert receipt["hard_stop_trigger"][
        "confirmed_distinct_source_events_requiring_retry"
    ] == 13
    assert receipt["hard_stop_trigger"]["by_chapter"] == {
        "3": 4,
        "13": 3,
        "19": 6,
    }
    assert receipt["stop_actions"]["retry_plan_created"] is False
    assert receipt["stop_actions"]["targeted_rewrite_calls"] == 0
    assert receipt["stop_actions"]["api_calls_after_capacity_trigger"] == 0
    assert not (run_dir / "repair/retry_plan.json").exists()
    assert not (run_dir / "repair/run_claim.json").exists()
    assert not (run_dir / "final/scorecard.json").exists()
    with pytest.raises(ZBatchError, match="硬停票已存在"):
        z83.record_retry09_capacity_hard_stop(
            run_dir,
            adjudication_path,
            allow_test_run_dir=True,
        )


def test_retry10_reuses_retry09_adjudication_and_plans_exactly_13(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry10_review_from_retry03(tmp_path)
    receipt = z83.reuse_retry09_adjudication_and_authorized_set(
        run_dir,
        allow_test_run_dir=True,
    )
    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0
    assert receipt["source_adjudication_row_count"] == 246
    assert receipt["approved_event_ids"] == list(z83.RETRY10_APPROVED_EVENT_IDS)
    assert receipt["mechanical_instance_differences"] == [
        {
            "path": "$.run_id",
            "before": z83.APPROVED_CAPACITY_OVERRIDE_TARGET_NAME,
            "after": z83.APPROVED_THIRTEEN_RETRY_TARGET_NAME,
        }
    ]
    adjudication = run_dir / "review/adjudication_reused_from_retry09.json"
    plan = z83.plan_retries(run_dir, adjudication.resolve())
    assert plan["status"] == "ready"
    assert [row["event_id"] for row in plan["tasks"]] == list(
        z83.RETRY10_APPROVED_EVENT_IDS
    )
    assert plan["limits"]["default_per_chapter"] == 3
    assert plan["limits"]["default_total"] == 6
    assert plan["limits"]["effective_one_time_per_chapter"] == {
        "3": 4,
        "13": 3,
        "19": 6,
    }
    assert plan["limits"]["effective_one_time_total"] == 13
    assert plan["limits"]["fourteenth_event_allowed"] is False
    assert z83._validate_retry_plan(
        run_dir, run_dir / "repair/retry_plan.json"
    ) == plan
    preflight = z83.preflight_retries(run_dir)
    assert preflight["status"] == "pass_zero_call_requests_frozen"
    assert preflight["task_count"] == 13
    assert preflight["event_ids"] == list(z83.RETRY10_APPROVED_EVENT_IDS)
    assert preflight["model_api_calls"] == 0
    assert preflight["network_attempts"] == 0
    assert all(not row["forbidden_model_hits"] for row in preflight["rows"])


def test_retry10_rejects_fourteenth_event_before_plan(tmp_path: Path) -> None:
    run_dir = _prepare_retry10_review_from_retry03(tmp_path)
    z83.reuse_retry09_adjudication_and_authorized_set(
        run_dir,
        allow_test_run_dir=True,
    )
    source_path = run_dir / "review/adjudication_reused_from_retry09.json"
    adjudication_path = run_dir / "review/adjudication_with_forbidden_14th.json"
    adjudication = z83.read_json(source_path)
    extra = next(
        row for row in adjudication["anchor_rows"] if row["event_id"] == "EV-C0003-01"
    )
    extra["verdict"] = "invalid"
    extra["unsupported_claims"] = ["测试不得进入第14条"]
    extra["reason"] = "测试模拟第14个候选，程序必须在计划前拒绝。"
    z83.write_json(adjudication_path, adjudication)
    with pytest.raises(ZBatchError, match="13条封闭全集"):
        z83.plan_retries(run_dir, adjudication_path.resolve())


def test_retry11_adds_exact_count_contract_and_stops_after_probe_split(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _prepare_retry11_review_from_retry03(tmp_path)
    reuse = z83.reuse_retry09_adjudication_and_authorized_set(
        run_dir,
        allow_test_run_dir=True,
    )
    assert reuse["status"] == (
        "pass_zero_call_reuse_246_rows_lock_13_sources_and_probe_first"
    )
    assert reuse["approved_event_ids"] == list(z83.RETRY11_APPROVED_EVENT_IDS)
    assert set(reuse["approved_event_ids"]) == set(z83.RETRY10_APPROVED_EVENT_IDS)
    assert reuse["mechanical_instance_differences"] == [
        {
            "path": "$.run_id",
            "before": z83.APPROVED_CAPACITY_OVERRIDE_TARGET_NAME,
            "after": z83.APPROVED_COUNT_CONTRACT_TARGET_NAME,
        }
    ]

    adjudication = run_dir / "review/adjudication_reused_from_retry09.json"
    plan = z83.plan_retries(run_dir, adjudication.resolve())
    assert [row["event_id"] for row in plan["tasks"]] == list(
        z83.RETRY11_APPROVED_EVENT_IDS
    )
    assert plan["tasks"][0]["event_id"] == "EV-C0013-06"
    assert all(row["allow_split"] is False for row in plan["tasks"])
    assert all(row["replacement_count_required"] == 1 for row in plan["tasks"])
    assert plan["limits"]["default_per_chapter"] == 3
    assert plan["limits"]["default_total"] == 6
    assert plan["limits"]["effective_one_time_total"] == 13
    assert z83.MAX_TARGETED_RETRIES_PER_CHAPTER == 3
    assert z83.MAX_TARGETED_RETRIES_TOTAL == 6

    preflight = z83.preflight_retries(run_dir)
    assert preflight["event_ids"] == list(z83.RETRY11_APPROVED_EVENT_IDS)
    assert preflight["task_count"] == 13
    assert preflight["model_api_calls"] == 0
    assert preflight["network_attempts"] == 0
    audit = z83.read_json(
        run_dir / "repair/retry10_fifth_request_count_contract_audit.json"
    )
    assert audit["explicit_exactly_one_present"] is False
    assert audit["explicit_no_split_present"] is False
    assert audit["generic_conditional_split_guidance_present"] is True
    old_split_line = (
        "若原事件含多个可独立判真的事实，拆成多条替换项；否则保留一条。"
    )
    for row in preflight["rows"]:
        body = z83.read_json(run_dir / row["prepared_request_path"])
        visible = "\n".join(
            str(message.get("content") or "") for message in body["messages"]
        )
        assert z83.RETRY11_EXACT_COUNT_CONTRACT in visible
        assert old_split_line not in visible
        assert row["replacement_count_required"] == 1
        assert row["allow_split"] is False
        assert row["retry10_single_variable_difference_paths"] == [
            "$.messages[0].content",
            "$.messages[1].content",
        ]
        assert all(
            permission in visible
            for permission in row["model_visible_permission_actions"]
        )

    with pytest.raises(ZBatchError, match="禁止重跑检查员"):
        z83.run_inspector(run_dir, phase="main", allow_test_run_dir=True)

    calls: list[str] = []
    bundle = z83.load_bundle(run_dir)

    def fake_call(*, stage: str, case_id: str, messages: list[dict[str, str]]):
        calls.append(case_id)
        body = z83.api_transport.build_request_body(
            model=str(bundle.route["model"]),
            messages=messages,
            contract=bundle.stage("targeted_retry"),
        )
        return _install_synthetic_exchange(
            stage_dir=run_dir / "repair",
            stage=stage,
            case_id=case_id,
            body=body,
            content_value={
                "replacement_events": [
                    {
                        "event": "邓恩说明梦中仍然存在真实。",
                        "anchors": [{"anchor_id": "E0018"}],
                    },
                    {
                        "event": "邓恩更相信梦中的克莱恩。",
                        "anchors": [{"anchor_id": "E0020"}],
                    },
                ]
            },
        )

    fake_transport = SimpleNamespace(call=fake_call)
    monkeypatch.setenv("SENSENOVA_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setattr(
        z83.api_transport.ApiTransport,
        "from_bundle",
        lambda *args, **kwargs: fake_transport,
    )
    with pytest.raises(ZBatchError, match="违反retry11恰好1条份数合同"):
        z83.run_retries(run_dir)
    assert calls == ["z83_repair_ch0013_ev-c0013-06"]
    hard_stop = z83.read_json(run_dir / "repair/hard_stop.json")
    assert hard_stop["failed_event_id"] == "EV-C0013-06"
    assert hard_stop["failed_plan_ordinal"] == 1
    assert hard_stop["completed_retries"] == 0
    assert hard_stop["network_attempts"] == 1
    assert not (run_dir / "repair/targeted_retry_ledger.jsonl").exists()
    assert not (run_dir / "final").exists()


def test_retry12_reuses_retry11_bodies_and_strips_anchor_extra_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _prepare_retry12_review_from_retry03(tmp_path)
    reuse = z83.reuse_retry09_adjudication_and_authorized_set(
        run_dir,
        allow_test_run_dir=True,
    )
    assert reuse["approved_event_ids"] == list(z83.RETRY12_APPROVED_EVENT_IDS)
    assert reuse["source_adjudication_row_count"] == 246
    adjudication = run_dir / "review/adjudication_reused_from_retry09.json"
    plan = z83.plan_retries(run_dir, adjudication.resolve())
    assert [row["event_id"] for row in plan["tasks"]] == list(
        z83.RETRY12_APPROVED_EVENT_IDS
    )
    assert all(row["replacement_count_required"] == 1 for row in plan["tasks"])
    preflight = z83.preflight_retries(run_dir)
    assert preflight["single_variable_against_retry11"] == {
        "model_visible_bodies_identical": True,
        "identical_body_count": 13,
        "request_parameters_unchanged": True,
        "only_program_anchor_leaf_acceptance_changed": True,
        "retry11_responses_or_transport_rows_reused": False,
    }
    for row in preflight["rows"]:
        retry12_path = run_dir / row["prepared_request_path"]
        retry11_path = z83.ROOT / row["retry11_prepared_request_path"]
        assert retry12_path.read_bytes() == retry11_path.read_bytes()
        assert row["prepared_request_sha256"] == row[
            "retry11_prepared_request_sha256"
        ]
        assert row["model_visible_body_equals_retry11"] is True
        assert row["retry11_single_variable_difference_paths"] == []

    with pytest.raises(ZBatchError, match="禁止重跑检查员"):
        z83.run_inspector(run_dir, phase="main", allow_test_run_dir=True)

    source_events = z83._event_map(run_dir / "main")
    calls: list[str] = []
    expected_strip_rows = 0
    bundle = z83.load_bundle(run_dir)

    def fake_call(*, stage: str, case_id: str, messages: list[dict[str, str]]):
        nonlocal expected_strip_rows
        calls.append(case_id)
        event_id = case_id.rsplit("_", 1)[1].upper()
        event = source_events[event_id]
        chapter = int(event_id[4:8])
        catalog = {
            str(row["anchor_id"]): str(row["quote"])
            for row in z83._catalog(run_dir, chapter)
        }
        anchors = []
        for anchor_ordinal, anchor in enumerate(event["anchors"], 1):
            anchor_id = str(anchor["anchor_id"])
            quote = catalog[anchor_id]
            if not calls[:-1] and anchor_ordinal == 1 and len(quote) > 1:
                quote = quote[:-1]
            anchors.append(
                {
                    "anchor_id": anchor_id,
                    "quote": quote,
                    "confidence": 0.9,
                }
            )
        expected_strip_rows += len(anchors)
        body = z83.api_transport.build_request_body(
            model=str(bundle.route["model"]),
            messages=messages,
            contract=bundle.stage("targeted_retry"),
        )
        return _install_synthetic_exchange(
            stage_dir=run_dir / "repair",
            stage=stage,
            case_id=case_id,
            body=body,
            content_value={
                "replacement_events": [
                    {
                        "event": event["event"],
                        "anchors": anchors,
                    }
                ]
            },
        )

    fake_transport = SimpleNamespace(call=fake_call)
    monkeypatch.setenv("SENSENOVA_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setattr(
        z83.api_transport.ApiTransport,
        "from_bundle",
        lambda *args, **kwargs: fake_transport,
    )
    metrics = z83.run_retries(run_dir)
    assert len(calls) == 13
    assert metrics["targeted_retry_logical_calls"] == 13
    diagnostic_path = run_dir / z83.RETRY12_ANCHOR_EXTRA_FIELD_LEDGER
    diagnostic_rows = z83.z68.read_jsonl(diagnostic_path)
    assert len(diagnostic_rows) == expected_strip_rows
    assert all(row["extra_field_names"] == ["confidence", "quote"] for row in diagnostic_rows)
    assert all(row["entered_formal_record"] is False for row in diagnostic_rows)
    assert all(row["used_for_validation"] is False for row in diagnostic_rows)
    assert any(
        row["quote_observation"]["relation"] == "model_is_prefix_of_frozen"
        for row in diagnostic_rows
    )
    ledgers = z83.z68.read_jsonl(run_dir / "repair/targeted_retry_ledger.jsonl")
    assert len(ledgers) == 13
    assert all("stripped_fields" not in json.dumps(row) for row in ledgers)
    assert all(
        row["anchor_extra_field_strip"]["formal_replacement_uses_sanitized_copy"]
        is True
        for row in ledgers
    )
    for chapter in z83.TARGET_CHAPTERS:
        model_json = z83.read_json(
            run_dir / f"repair/01_extract/model_json/ch{chapter:04d}.json"
        )
        assert all(
            set(anchor) == {"anchor_id"}
            for event in model_json["events"]
            for anchor in event["anchors"]
        )
        catalog = {
            str(row["anchor_id"]): str(row["quote"])
            for row in z83._catalog(run_dir, chapter)
        }
        materialized = z83.read_json(
            run_dir / f"repair/01_extract/events/ch{chapter:04d}.json"
        )
        assert all(
            anchor["quote"] == catalog[anchor["anchor_id"]]
            for event in materialized["events"]
            for anchor in event["anchors"]
        )
    first_raw = z83.read_json(
        run_dir
        / "repair/responses/targeted_retry/"
        "z83_repair_ch0013_ev-c0013-06_raw.json"
    )
    first_content = json.loads(first_raw["choices"][0]["message"]["content"])
    assert "quote" in first_content["replacement_events"][0]["anchors"][0]
    assert "confidence" in first_content["replacement_events"][0]["anchors"][0]
    z83._validate_semantic_retry_exchanges(
        run_dir,
        tasks=plan["tasks"],
        ledger=ledgers,
    )


def test_retry12_anchor_normalizer_keeps_other_hard_gates(tmp_path: Path) -> None:
    run_dir = _prepare(
        tmp_path,
        z83.APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
    )
    raw_path = run_dir / "repair/responses/targeted_retry/synthetic_raw.json"
    z83.write_json(raw_path, {"synthetic": True})
    anchor_id = str(z83._catalog(run_dir, 3)[0]["anchor_id"])
    base = {
        "replacement_events": [
            {
                "event": "测试员检查材料并记录结果。",
                "anchors": [{"anchor_id": anchor_id, "quote": "只作旁账"}],
            }
        ]
    }

    sanitized, rows = z83._normalize_retry12_anchor_extras(
        run_dir=run_dir,
        parsed=base,
        chapter=3,
        event_id="EV-C0003-01",
        case_id="synthetic",
        plan_ordinal=1,
        raw_response_path=raw_path,
    )
    validated = z83.z77.validate_replacements(
        sanitized,
        catalog=z83._catalog(run_dir, 3),
        allow_multiple=False,
    )
    assert validated[0]["anchors"] == [{"anchor_id": anchor_id}]
    assert rows[0]["stripped_fields"] == {"quote": "只作旁账"}

    invalid_payloads = [
        {**base, "extra": True},
        {
            "replacement_events": [
                {**base["replacement_events"][0], "reason": "事件层越权"}
            ]
        },
        {
            "replacement_events": [
                {"event": "测试员检查材料并记录结果。", "anchors": [{"quote": "缺ID"}]}
            ]
        },
        {
            "replacement_events": [
                {
                    "event": "测试员检查材料并记录结果。",
                    "anchors": [{"anchor_id": "E9999", "quote": "目录外"}],
                }
            ]
        },
        {
            "replacement_events": [
                {
                    "event": "测试员检查材料并记录结果。",
                    "anchors": [{"anchor_id": anchor_id}, {"anchor_id": anchor_id}],
                }
            ]
        },
        {"replacement_events": [base["replacement_events"][0], base["replacement_events"][0]]},
    ]
    for payload in invalid_payloads:
        with pytest.raises(ZBatchError):
            z83._normalize_retry12_anchor_extras(
                run_dir=run_dir,
                parsed=payload,
                chapter=3,
                event_id="EV-C0003-01",
                case_id="synthetic",
                plan_ordinal=1,
                raw_response_path=raw_path,
            )


def _retry06_fake_response(
    body: dict,
    *,
    break_last_quote: bool = False,
    punctuation_equivalent_drift: bool = False,
) -> bytes:
    payload = json.loads(body["messages"][1]["content"])
    results = []
    drift_applied = False
    for item in payload["items"]:
        anchor = item["anchors"][0]
        formal_quote = anchor["quote"]
        model_quote = formal_quote[1:]
        if sum(not value.isspace() for value in model_quote) < 6:
            model_quote = formal_quote
        if punctuation_equivalent_drift and not drift_applied:
            for before, after in (
                ("。", "."),
                ("，", ","),
                ("：", ":"),
                ("；", ";"),
                ("？", "?"),
                ("！", "!"),
            ):
                if before in model_quote:
                    model_quote = model_quote.replace(before, after, 1)
                    drift_applied = True
                    break
        results.append(
            {
                "item_id": item["item_id"],
                "decision": "pass_candidate",
                "support": "direct_support",
                "rule_ids": ["SEM-01"],
                "evidence": [
                    {
                        "anchor_id": anchor["anchor_id"],
                        "quote": model_quote,
                        "reason": "测试回包以子串校验，正式短引由程序回填。",
                    }
                ],
                "confidence": 0.9,
                "needs_strong_review": False,
                "reason": "只作分流候选。",
            }
        )
    if break_last_quote:
        results[-1]["evidence"][0]["quote"] += "改"
    if punctuation_equivalent_drift:
        assert drift_applied
    return json.dumps(
        {
            "model": z83.api_transport.PINNED_MODEL,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "contract_version": z83.pipeline_inspector.MODEL_OUTPUT_CONTRACT,
                                "results": results,
                            },
                            ensure_ascii=False,
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        },
        ensure_ascii=False,
    ).encode("utf-8")


def _advance_all_clear_candidate_to_final_review(run_dir: Path) -> None:
    adjudication = _completed_adjudication(run_dir)
    events_by_chapter = {
        chapter: sorted(
            event_id
            for event_id in z83._event_map(run_dir / "main")
            if int(event_id[4:8]) == chapter
        )
        for chapter in z83.TARGET_CHAPTERS
    }
    for row in adjudication["current_rows"]:
        if row["verdict"] != "not_observed":
            row["candidate_event_ids"] = [events_by_chapter[row["chapter"]][0]]
        if row["record_id"] in {"B-C0013-02", "B-C0019-04"}:
            row["verdict"] = "preserved"
            row["candidate_event_ids"] = [events_by_chapter[row["chapter"]][0]]
            row["reason"] = "测试夹具把两条指定记录判为完整保留。"
    for row in adjudication["gold_rows"]:
        if row["verdict"] != "miss":
            row["candidate_event_ids"] = [events_by_chapter[3][0]]
        if row["verdict"] == "coverage_only_invalid_support":
            row["verdict"] = "semantic_shadow"
            row["reason"] = "测试夹具把来源关系判为有效语义影子。"
    main_path = run_dir / "review/adjudication_all_clear.json"
    z83.write_json(main_path, adjudication)
    assert z83.plan_retries(run_dir, main_path)["status"] == "no_retry_needed"
    assert z83.run_retries(run_dir)["targeted_retry_logical_calls"] == 0
    z83.build_review(run_dir, phase="final")


def test_retry06_reuses_chapter3_and_calls_only_chapters13_and19(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry06_review_from_retry03(tmp_path)
    sent_chapters: list[int] = []

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        payload = json.loads(body["messages"][1]["content"])
        chapter = int(payload["batch_id"].split("CH", 1)[1].split("-", 1)[0])
        sent_chapters.append(chapter)
        assert chapter in {13, 19}
        assert body["max_tokens"] == 32000
        assert body["reasoning_effort"] == "medium"
        assert body["temperature"] == 0.0
        assert body["n"] == 1
        assert body["response_format"] == {"type": "json_object"}
        assert body["messages"][0]["content"] == (
            f"{z83.pipeline_inspector.SYSTEM_PROMPT}\n"
            f"{z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE}"
        )
        return FakeResponse(_retry06_fake_response(body))

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "urlopen",
            side_effect=opener,
        ):
            receipt = z83.run_inspector(
                run_dir,
                phase="main",
                allow_test_run_dir=True,
            )
    assert sent_chapters == [13, 19]
    assert receipt["reused_chapters"] == [3]
    assert receipt["new_called_chapters"] == [13, 19]
    assert receipt["new_attempted_chapters"] == [13, 19]
    assert receipt["batch_invocations"] == 2
    assert receipt["logical_model_calls"] == 2
    assert receipt["network_attempts"] == 2
    assert receipt["reused_source_usage_imported"] is False
    assert receipt["reused_source_network_attempt_imported"] is False
    assert receipt["new_call_usage"]["successful_responses"] == 2
    reuse = z83.read_json(run_dir / "review/inspector/ch0003/reuse_receipt.json")
    assert reuse["model_api_calls"] == 0
    assert reuse["network_attempts"] == 0
    assert reuse["request_rebuilt_exactly"] is True
    assert reuse["response_reparsed_under_retry06_contract"] is True
    assert not (run_dir / "review/inspector/ch0003/run").exists()
    for chapter in (13, 19):
        audit = z83.read_json(
            run_dir / f"review/inspector/ch{chapter:04d}/run/quote_fill_audit.json"
        )
        assert audit["minimum_quote_nonspace_chars"] == 6
        assert audit["differing_rows"] > 0
        assert all(row["model_quote"] in row["formal_quote"] for row in audit["rows"])
    assert z83.require_inspector_complete(run_dir, phase="main") == receipt


def test_retry07_reuses_chapter3_and_calls_only_chapters13_and19(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry07_review_from_retry03(tmp_path)
    sent_chapters: list[int] = []

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        payload = json.loads(body["messages"][1]["content"])
        chapter = int(payload["batch_id"].split("CH", 1)[1].split("-", 1)[0])
        sent_chapters.append(chapter)
        assert chapter in {13, 19}
        assert body["max_tokens"] == 32000
        assert body["reasoning_effort"] == "medium"
        assert body["temperature"] == 0.0
        assert body["n"] == 1
        assert body["response_format"] == {"type": "json_object"}
        assert body["messages"][0]["content"] == (
            f"{z83.pipeline_inspector.SYSTEM_PROMPT}\n"
            f"{z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE}"
        )
        return FakeResponse(
            _retry06_fake_response(body, punctuation_equivalent_drift=True)
        )

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "urlopen",
            side_effect=opener,
        ):
            receipt = z83.run_inspector(
                run_dir,
                phase="main",
                allow_test_run_dir=True,
            )
    assert sent_chapters == [13, 19]
    assert receipt["reused_chapters"] == [3]
    assert receipt["new_called_chapters"] == [13, 19]
    assert receipt["new_attempted_chapters"] == [13, 19]
    assert receipt["batch_invocations"] == 2
    assert receipt["logical_model_calls"] == 2
    assert receipt["network_attempts"] == 2
    assert receipt["evidence_quote_policy"] == (
        z83.pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
    )
    assert receipt["punctuation_equivalence_sha256"] == (
        z83.pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
    )
    reuse = z83.read_json(run_dir / "review/inspector/ch0003/reuse_receipt.json")
    assert reuse["model_api_calls"] == 0
    assert reuse["network_attempts"] == 0
    assert reuse["response_reparsed_under_retry07_contract"] is True
    assert reuse["retry06_chapter13_rejected_response_imported"] is False
    assert not (run_dir / "review/inspector/ch0003/run").exists()
    for chapter in (13, 19):
        audit = z83.read_json(
            run_dir / f"review/inspector/ch{chapter:04d}/run/quote_fill_audit.json"
        )
        api_batch = z83.read_json(
            run_dir / f"review/inspector/ch{chapter:04d}/api_batch.json"
        )
        formal_by_key = {
            (item["item_id"], anchor["anchor_id"]): anchor["quote"]
            for item in api_batch["items"]
            for anchor in item["anchors"]
        }
        assert audit["minimum_quote_nonspace_chars"] == 6
        assert audit["normalization_rescued_rows"] == 1
        assert audit["punctuation_equivalence_sha256"] == (
            z83.pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
        )
        assert all(
            row["formal_quote"] == formal_by_key[(row["item_id"], row["anchor_id"])]
            for row in audit["rows"]
        )
    assert z83.require_inspector_complete(run_dir, phase="main") == receipt


def _run_retry08_fake_inspector(run_dir: Path) -> tuple[dict, list[int]]:
    sent_chapters: list[int] = []

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        payload = json.loads(body["messages"][1]["content"])
        chapter = int(payload["batch_id"].split("CH", 1)[1].split("-", 1)[0])
        sent_chapters.append(chapter)
        assert chapter in {13, 19}
        assert body["max_tokens"] == 32000
        assert body["reasoning_effort"] == "medium"
        assert body["temperature"] == 0.0
        assert body["n"] == 1
        assert body["response_format"] == {"type": "json_object"}
        assert body["messages"][0]["content"] == (
            f"{z83.pipeline_inspector.SYSTEM_PROMPT}\n"
            f"{z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE}"
        )
        return FakeResponse(
            _retry06_fake_response(body, punctuation_equivalent_drift=True)
        )

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "urlopen",
            side_effect=opener,
        ):
            receipt = z83.run_inspector(
                run_dir,
                phase="main",
                allow_test_run_dir=True,
            )
    return receipt, sent_chapters


def test_retry08_reuses_chapter3_and_rebuilds_fresh_chapters_from_raw(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry08_review_from_retry03(tmp_path)
    receipt, sent_chapters = _run_retry08_fake_inspector(run_dir)

    assert sent_chapters == [13, 19]
    assert receipt["reused_chapters"] == [3]
    assert receipt["new_called_chapters"] == [13, 19]
    assert receipt["new_attempted_chapters"] == [13, 19]
    assert receipt["logical_model_calls"] == 2
    assert receipt["evidence_quote_policy"] == (
        z83.pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
    )
    assert receipt["punctuation_unit_equivalence_sha256"] == (
        z83.pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
    )
    assert set(receipt["raw_rebuild_receipts"]) == {"13", "19"}
    assert not (run_dir / "review/inspector/ch0003/run").exists()
    reuse = z83.read_json(run_dir / "review/inspector/ch0003/reuse_receipt.json")
    assert reuse["response_reparsed_under_retry08_contract"] is True
    assert reuse["retry07_artifacts_imported_as_result"] is False
    for chapter in (13, 19):
        nested_root = run_dir / f"review/inspector/ch{chapter:04d}/run"
        rebuild = z83.read_json(nested_root / "raw_rebuild_receipt.json")
        assert rebuild["status"] == (
            "pass_rebuilt_from_raw_response_and_unique_usage"
        )
        assert rebuild["usage_rows"] == 1
        assert rebuild["raw_response_reparsed"] is True
        assert rebuild["intermediate_routing_trusted_without_rebuild"] is False
        assert rebuild["punctuation_unit_equivalence_sha256"] == (
            z83.pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
        )
    assert z83.require_inspector_complete(run_dir, phase="main") == receipt


def test_retry08_closeout_rejects_usage_and_intermediate_ticket_tampering(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry08_review_from_retry03(tmp_path)
    receipt, _ = _run_retry08_fake_inspector(run_dir)
    root = run_dir / "review/inspector"
    nested_root = root / "ch0013/run"
    usage_path = nested_root / "usage.jsonl"
    routing_path = nested_root / "routing_result.json"
    audit_path = nested_root / "quote_fill_audit.json"
    rebuild_path = nested_root / "raw_rebuild_receipt.json"
    originals = {
        path: path.read_bytes()
        for path in (usage_path, routing_path, audit_path, rebuild_path)
    }

    usage_path.write_text("", encoding="utf-8")
    with pytest.raises(ZBatchError, match="usage.*不是恰好一条"):
        z83.require_inspector_complete(run_dir, phase="main")
    usage_path.write_bytes(originals[usage_path])

    usage_path.write_bytes(originals[usage_path] + originals[usage_path])
    with pytest.raises(ZBatchError, match="usage.*不是恰好一条"):
        z83.require_inspector_complete(run_dir, phase="main")
    usage_path.write_bytes(originals[usage_path])

    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    usage["request_sha256"] = "0" * 64
    usage_path.write_text(
        json.dumps(usage, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with pytest.raises(ZBatchError, match="usage 账与原始响应不一致"):
        z83.require_inspector_complete(run_dir, phase="main")
    usage_path.write_bytes(originals[usage_path])

    routing = z83.read_json(routing_path)
    routing["deepseek_results"][0]["reason"] += "篡改"
    z83.write_json(routing_path, routing)
    with pytest.raises(ZBatchError, match="落盘路由不能从原始响应重建"):
        z83.require_inspector_complete(run_dir, phase="main")
    routing_path.write_bytes(originals[routing_path])

    audit = z83.read_json(audit_path)
    audit["rows"][0]["formal_quote"] += "篡改"
    z83.write_json(audit_path, audit)
    with pytest.raises(ZBatchError, match="落盘短引审计不能从原始响应重建"):
        z83.require_inspector_complete(run_dir, phase="main")
    audit_path.write_bytes(originals[audit_path])

    rebuild = z83.read_json(rebuild_path)
    rebuild["usage_rows"] = 2
    z83.write_json(rebuild_path, rebuild)
    with pytest.raises(ZBatchError, match="重建票漂移"):
        z83.require_inspector_complete(run_dir, phase="main")
    rebuild_path.write_bytes(originals[rebuild_path])
    assert z83.require_inspector_complete(run_dir, phase="main") == receipt


def test_retry07_mapping_outside_content_hard_stops_before_chapter19(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry07_review_from_retry03(tmp_path)
    sent_chapters: list[int] = []

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        payload = json.loads(body["messages"][1]["content"])
        chapter = int(payload["batch_id"].split("CH", 1)[1].split("-", 1)[0])
        sent_chapters.append(chapter)
        return FakeResponse(_retry06_fake_response(body, break_last_quote=True))

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "urlopen",
            side_effect=opener,
        ):
            with pytest.raises(
                z83.pipeline_inspector.InspectorError,
                match="映射表外内容差异",
            ):
                z83.run_inspector(
                    run_dir,
                    phase="main",
                    allow_test_run_dir=True,
                )
    assert sent_chapters == [13]
    root = run_dir / "review/inspector"
    hard_stop = z83.read_json(root / "hard_stop.json")
    child_stop = z83.read_json(root / "ch0013/run/hard_stop.json")
    assert hard_stop["completed_chapters"] == [3]
    assert hard_stop["new_attempted_chapters"] == [13]
    assert hard_stop["punctuation_equivalence_sha256"] == (
        z83.pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
    )
    assert child_stop["evidence_quote_policy"] == (
        z83.pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
    )
    assert child_stop["punctuation_equivalence_sha256"] == (
        z83.pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
    )
    assert not list(root.glob("ch0019/run/requests/**/*_request.json"))


def test_retry06_true_non_substring_hard_stops_before_chapter19(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry06_review_from_retry03(tmp_path)
    sent_chapters: list[int] = []

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        payload = json.loads(body["messages"][1]["content"])
        chapter = int(payload["batch_id"].split("CH", 1)[1].split("-", 1)[0])
        sent_chapters.append(chapter)
        return FakeResponse(_retry06_fake_response(body, break_last_quote=True))

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "urlopen",
            side_effect=opener,
        ):
            with pytest.raises(
                z83.pipeline_inspector.InspectorError,
                match="逐字连续子串",
            ):
                z83.run_inspector(
                    run_dir,
                    phase="main",
                    allow_test_run_dir=True,
                )
    assert sent_chapters == [13]
    root = run_dir / "review/inspector"
    hard_stop = z83.read_json(root / "hard_stop.json")
    assert hard_stop["completed_chapters"] == [3]
    assert hard_stop["reused_chapters"] == [3]
    assert hard_stop["new_called_chapters"] == []
    assert hard_stop["new_attempted_chapters"] == [13]
    assert hard_stop["batch_invocations"] == 1
    assert hard_stop["network_attempts"] == 1
    assert hard_stop["new_call_usage"]["successful_responses"] == 1
    assert not list(root.glob("ch0019/run/requests/**/*_request.json"))


def test_retry06_retry05_source_sha_drift_stops_before_claim_and_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _prepare_retry06_review_from_retry03(tmp_path)
    monkeypatch.setattr(
        z83,
        "APPROVED_RETRY05_CHAPTER3_RAW_SHA256",
        "0" * 64,
    )
    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "urlopen",
            side_effect=AssertionError("来源SHA漂移时不得发网"),
        ):
            with pytest.raises(ZBatchError, match="retry05 chapter3_raw"):
                z83.run_inspector(
                    run_dir,
                    phase="main",
                    allow_test_run_dir=True,
                )
    assert not (run_dir / "review/inspector").exists()
    stop = z83.read_json(run_dir / "review/inspector_preflight_hard_stop.json")
    assert stop["status"] == "hard_stop_before_claim_and_network"
    assert stop["model_api_calls"] == 0
    assert stop["network_attempts"] == 0


def test_retry07_retry06_source_sha_drift_stops_before_claim_and_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _prepare_retry07_review_from_retry03(tmp_path)
    monkeypatch.setattr(
        z83,
        "APPROVED_RETRY06_CHAPTER13_RAW_SHA256",
        "0" * 64,
    )
    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "urlopen",
            side_effect=AssertionError("retry06来源SHA漂移时不得发网"),
        ):
            with pytest.raises(ZBatchError, match="retry06 chapter13_raw"):
                z83.run_inspector(
                    run_dir,
                    phase="main",
                    allow_test_run_dir=True,
                )
    assert not (run_dir / "review/inspector").exists()
    stop = z83.read_json(run_dir / "review/inspector_preflight_hard_stop.json")
    assert stop["status"] == "hard_stop_before_claim_and_network"
    assert stop["model_api_calls"] == 0
    assert stop["network_attempts"] == 0


def test_retry06_final_inspector_keeps_program_fill_contract(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry06_review_from_retry03(tmp_path)

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        return FakeResponse(_retry06_fake_response(body))

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "urlopen",
            side_effect=opener,
        ):
            z83.run_inspector(run_dir, phase="main", allow_test_run_dir=True)

    adjudication = _completed_adjudication(run_dir)
    events_by_chapter = {
        chapter: sorted(
            event_id
            for event_id in z83._event_map(run_dir / "main")
            if int(event_id[4:8]) == chapter
        )
        for chapter in z83.TARGET_CHAPTERS
    }
    for row in adjudication["current_rows"]:
        if row["verdict"] != "not_observed":
            row["candidate_event_ids"] = [events_by_chapter[row["chapter"]][0]]
        if row["record_id"] in {"B-C0013-02", "B-C0019-04"}:
            row["verdict"] = "preserved"
            row["candidate_event_ids"] = [events_by_chapter[row["chapter"]][0]]
            row["reason"] = "测试夹具把两条指定记录判为完整保留。"
    for row in adjudication["gold_rows"]:
        if row["verdict"] != "miss":
            row["candidate_event_ids"] = [events_by_chapter[3][0]]
        if row["verdict"] == "coverage_only_invalid_support":
            row["verdict"] = "semantic_shadow"
            row["reason"] = "测试夹具把来源关系判为有效语义影子。"
    main_path = run_dir / "review/adjudication_all_clear.json"
    z83.write_json(main_path, adjudication)
    assert z83.plan_retries(run_dir, main_path)["status"] == "no_retry_needed"
    assert z83.run_retries(run_dir)["targeted_retry_logical_calls"] == 0
    z83.build_review(run_dir, phase="final")

    contract_path = run_dir / z83.LOCAL_INSPECTOR_CONTRACT
    preflight = z83._preflight_inspector_requests(
        run_dir,
        phase="final",
        review_dir=run_dir / "final_review",
        contract_path=contract_path,
    )
    assert preflight["status"] == (
        "pass_zero_call_retry06_program_contract_no_prompt_or_parameter_change"
    )
    assert preflight["program_side_quote_contract"]["minimum_quote_nonspace_chars"] == 6
    assert all(row["differences"] == [] for row in preflight["rows"])
    assert all(
        row["baseline_request_sha256"] == row["candidate_request_sha256"]
        for row in preflight["rows"]
    )

    seen: list[dict] = []

    def fail_after_contract_check(**kwargs: object) -> None:
        seen.append(dict(kwargs))
        assert kwargs["evidence_quote_policy"] == (
            z83.pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING
        )
        assert kwargs["minimum_quote_nonspace_chars"] == 6
        assert kwargs["system_prompt_suffix"] == z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
        raise ZBatchError("测试到此硬停")

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.pipeline_inspector,
            "run_inspector",
            side_effect=fail_after_contract_check,
        ):
            with pytest.raises(ZBatchError, match="测试到此硬停"):
                z83.run_inspector(
                    run_dir,
                    phase="final",
                    allow_test_run_dir=True,
                )
    assert len(seen) == 1


def test_retry07_final_inspector_rebuilds_policy_and_cost_receipt(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry07_review_from_retry03(tmp_path)
    sent_batches: list[str] = []

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        payload = json.loads(body["messages"][1]["content"])
        sent_batches.append(payload["batch_id"])
        return FakeResponse(_retry06_fake_response(body))

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "urlopen",
            side_effect=opener,
        ):
            z83.run_inspector(run_dir, phase="main", allow_test_run_dir=True)

    _advance_all_clear_candidate_to_final_review(run_dir)
    contract_path = run_dir / z83.LOCAL_INSPECTOR_CONTRACT
    preflight = z83._preflight_inspector_requests(
        run_dir,
        phase="final",
        review_dir=run_dir / "final_review",
        contract_path=contract_path,
    )
    assert preflight["status"] == (
        "pass_zero_call_retry07_punctuation_compare_contract_no_prompt_or_parameter_change"
    )
    assert all(row["differences"] == [] for row in preflight["rows"])
    assert (
        preflight["program_side_quote_contract"]["punctuation_equivalence_sha256"]
        == z83.pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
    )

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request,
            "urlopen",
            side_effect=opener,
        ):
            receipt = z83.run_inspector(
                run_dir,
                phase="final",
                allow_test_run_dir=True,
            )
    assert receipt["reused_chapters"] == []
    assert receipt["new_called_chapters"] == [3, 13, 19]
    assert receipt["new_attempted_chapters"] == [3, 13, 19]
    assert receipt["batch_invocations"] == 3
    assert receipt["logical_model_calls"] == 3
    assert receipt["network_attempts"] == 3
    assert receipt["new_call_usage"]["successful_responses"] == 3
    assert receipt["evidence_quote_policy"] == (
        z83.pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
    )
    assert receipt["punctuation_equivalence_sha256"] == (
        z83.pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
    )
    assert z83.require_inspector_complete(run_dir, phase="final") == receipt
    assert sent_batches == [
        "Z83-MAIN-CH0013-API",
        "Z83-MAIN-CH0019-API",
        "Z83-FINAL-CH0003-API",
        "Z83-FINAL-CH0013-API",
        "Z83-FINAL-CH0019-API",
    ]


def test_retry04_inspector_uses_local_32k_contract_and_syncs_hard_stop(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry04_review_from_retry03(tmp_path)
    seen_contracts: list[Path] = []

    def fail_after_contract_check(**kwargs: object) -> None:
        contract = Path(str(kwargs["contract_path"]))
        seen_contracts.append(contract)
        stage = z83.read_json(contract)["profiles"][
            z83.pipeline_inspector.DEFAULT_PROFILE
        ]["stages"]["semantic_route"]
        assert stage["max_tokens"] == 32000
        assert stage["reasoning_effort"] == "medium"
        raise ZBatchError("synthetic retry04 inspector failure")

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.pipeline_inspector,
            "run_inspector",
            side_effect=fail_after_contract_check,
        ):
            with pytest.raises(
                ZBatchError, match="synthetic retry04 inspector failure"
            ):
                z83.run_inspector(
                    run_dir,
                    phase="main",
                    allow_test_run_dir=True,
                )
    assert seen_contracts == [run_dir / z83.LOCAL_INSPECTOR_CONTRACT]
    root = run_dir / "review/inspector"
    hard_stop = z83.read_json(root / "hard_stop.json")
    master = z83.read_json(run_dir / "run_manifest.json")
    assert hard_stop["status"] == "hard_stop_no_resume_or_result_selection"
    assert hard_stop["batch_invocations"] == 1
    assert hard_stop["completed_chapters"] == []
    assert hard_stop["inspector_contract_sha256"] == z83.sha256_file(
        run_dir / z83.LOCAL_INSPECTOR_CONTRACT
    )
    assert master["status"] == "main_inspector_hard_stop"
    assert master["main_inspector"]["root_manifest_sha256"] == z83.sha256_file(
        root / "run_manifest.json"
    )
    assert not (root / "combined_routing.json").exists()


def test_retry04_real_transport_requests_match_preflight_and_complete(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry04_review_from_retry03(tmp_path)
    sent_bodies: list[dict] = []

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        sent_bodies.append(body)
        assert body["max_tokens"] == 32000
        assert body["reasoning_effort"] == "medium"
        assert body["temperature"] == 0.0
        assert body["n"] == 1
        payload = json.loads(body["messages"][1]["content"])
        results = []
        for item in payload["items"]:
            anchor = item["anchors"][0]
            results.append(
                {
                    "item_id": item["item_id"],
                    "decision": "pass_candidate",
                    "support": "direct_support",
                    "rule_ids": ["SEM-01"],
                    "evidence": [
                        {
                            "anchor_id": anchor["anchor_id"],
                            "quote": anchor["quote"],
                            "reason": "测试运输回包逐字引用输入锚。",
                        }
                    ],
                    "confidence": 0.9,
                    "needs_strong_review": False,
                    "reason": "测试运输回包只作分流候选。",
                }
            )
        raw = json.dumps(
            {
                "model": z83.api_transport.PINNED_MODEL,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "contract_version": z83.pipeline_inspector.MODEL_OUTPUT_CONTRACT,
                                    "results": results,
                                },
                                ensure_ascii=False,
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
        return FakeResponse(raw)

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request, "urlopen", side_effect=opener
        ):
            receipt = z83.run_inspector(
                run_dir,
                phase="main",
                allow_test_run_dir=True,
            )
    assert receipt["status"] == "routing_complete_not_final_truth"
    assert receipt["logical_model_calls"] == 3
    assert len(sent_bodies) == 3
    assert z83.require_inspector_complete(run_dir, phase="main") == receipt
    for chapter in z83.TARGET_CHAPTERS:
        row = receipt["request_preflight"]["rows"][z83.TARGET_CHAPTERS.index(chapter)]
        request_paths = list(
            (run_dir / f"review/inspector/ch{chapter:04d}/run/requests").glob(
                "**/*_request.json"
            )
        )
        assert len(request_paths) == 1
        assert (
            z83.canonical_sha(z83.read_json(request_paths[0]))
            == row["candidate_request_sha256"]
        )

    combined_path = run_dir / "review/inspector/combined_routing.json"
    manifest_path = run_dir / "review/inspector/run_manifest.json"
    forged = z83.read_json(combined_path)
    for key in (
        "request_preflight_sha256",
        "request_preflight",
        "inspector_contract_path",
        "inspector_contract_sha256",
    ):
        forged.pop(key, None)
    z83.write_json(combined_path, forged)
    forged_manifest = z83.read_json(manifest_path)
    for key in (
        "request_preflight_sha256",
        "request_preflight",
        "inspector_contract_path",
        "inspector_contract_sha256",
    ):
        forged_manifest.pop(key, None)
    forged_manifest["combined_routing_sha256"] = z83.sha256_file(combined_path)
    z83.write_json(manifest_path, forged_manifest)
    with pytest.raises(ZBatchError, match="正式retry04／retry05检查员票缺"):
        z83.require_inspector_complete(run_dir, phase="main")


@pytest.mark.parametrize(
    "target_name",
    [
        z83.APPROVED_COMPLETED_SEED_TARGET_NAME,
        z83.APPROVED_QUOTE_CONSTRAINT_TARGET_NAME,
    ],
)
def test_retry04_and_retry05_real_length_response_hard_stop_after_chapter3(
    tmp_path: Path,
    target_name: str,
) -> None:
    run_dir = _prepare_retry04_review_from_retry03(
        tmp_path,
        target_name=target_name,
    )
    calls = 0

    class LengthResponse:
        status = 200
        headers: dict[str, str] = {}

        def __enter__(self) -> "LengthResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": z83.api_transport.PINNED_MODEL,
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "{}"},
                            "finish_reason": "length",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 32001,
                        "total_tokens": 32011,
                    },
                }
            ).encode("utf-8")

    def opener(request: object, *, timeout: int) -> LengthResponse:
        nonlocal calls
        calls += 1
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        assert timeout == 300
        assert body["max_tokens"] == 32000
        if target_name == z83.APPROVED_QUOTE_CONSTRAINT_TARGET_NAME:
            assert body["messages"][0]["content"].endswith(
                z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
            )
        return LengthResponse()

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request, "urlopen", side_effect=opener
        ):
            with pytest.raises(ZBatchError, match="finish_reason=length"):
                z83.run_inspector(
                    run_dir,
                    phase="main",
                    allow_test_run_dir=True,
                )
    assert calls == 1
    root = run_dir / "review/inspector"
    hard_stop = z83.read_json(root / "hard_stop.json")
    assert hard_stop["completed_chapters"] == []
    assert hard_stop["batch_invocations"] == 1
    assert hard_stop["logical_model_calls_completed"] == 0
    assert hard_stop["network_attempts"] == 1
    assert not (root / "combined_routing.json").exists()
    assert not list(root.glob("**/usage.jsonl"))
    assert not list(root.glob("ch0013/run/requests/**/*_request.json"))


def test_retry05_real_transport_appends_only_verbatim_rule_and_completes(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry05_review_from_retry03(tmp_path)
    sent_bodies: list[dict] = []

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        sent_bodies.append(body)
        assert body["max_tokens"] == 32000
        assert body["reasoning_effort"] == "medium"
        assert body["temperature"] == 0.0
        assert body["n"] == 1
        assert body["messages"][0]["content"] == (
            f"{z83.pipeline_inspector.SYSTEM_PROMPT}\n"
            f"{z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE}"
        )
        payload = json.loads(body["messages"][1]["content"])
        results = []
        for item in payload["items"]:
            anchor = item["anchors"][0]
            results.append(
                {
                    "item_id": item["item_id"],
                    "decision": "pass_candidate",
                    "support": "direct_support",
                    "rule_ids": ["SEM-01"],
                    "evidence": [
                        {
                            "anchor_id": anchor["anchor_id"],
                            "quote": anchor["quote"],
                            "reason": "测试回包逐字引用输入短引。",
                        }
                    ],
                    "confidence": 0.9,
                    "needs_strong_review": False,
                    "reason": "只作分流候选。",
                }
            )
        raw = json.dumps(
            {
                "model": z83.api_transport.PINNED_MODEL,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "contract_version": z83.pipeline_inspector.MODEL_OUTPUT_CONTRACT,
                                    "results": results,
                                },
                                ensure_ascii=False,
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
        return FakeResponse(raw)

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request, "urlopen", side_effect=opener
        ):
            receipt = z83.run_inspector(
                run_dir,
                phase="main",
                allow_test_run_dir=True,
            )
    assert receipt["status"] == "routing_complete_not_final_truth"
    assert receipt["logical_model_calls"] == 3
    assert len(sent_bodies) == 3
    assert z83.require_inspector_complete(run_dir, phase="main") == receipt
    retry04_reference = z83._retry04_inspector_reference()["candidate_request_sha256"]
    for body in sent_bodies:
        payload = json.loads(body["messages"][1]["content"])
        baseline_messages = copy.deepcopy(body["messages"])
        baseline_messages[0]["content"] = z83.pipeline_inspector.SYSTEM_PROMPT
        baseline_record = z83._inspector_request_record(
            contract_path=run_dir / z83.LOCAL_INSPECTOR_CONTRACT,
            case_id=payload["batch_id"],
            messages=baseline_messages,
        )
        chapter = int(payload["batch_id"].split("CH", 1)[1].split("-", 1)[0])
        assert z83.canonical_sha(baseline_record) == retry04_reference[str(chapter)]


def test_retry05_last_item_quote_rewrite_hard_stops_before_later_chapters(
    tmp_path: Path,
) -> None:
    run_dir = _prepare_retry05_review_from_retry03(tmp_path)
    calls = 0

    class FakeResponse:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self, raw: bytes) -> None:
            self.raw = raw

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.raw

    def opener(request: object, *, timeout: int) -> FakeResponse:
        nonlocal calls
        calls += 1
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        assert body["messages"][0]["content"].endswith(
            z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
        )
        payload = json.loads(body["messages"][1]["content"])
        results = []
        for item in payload["items"]:
            anchor = item["anchors"][0]
            results.append(
                {
                    "item_id": item["item_id"],
                    "decision": "pass_candidate",
                    "support": "direct_support",
                    "rule_ids": ["SEM-01"],
                    "evidence": [
                        {
                            "anchor_id": anchor["anchor_id"],
                            "quote": anchor["quote"],
                            "reason": "测试回包。",
                        }
                    ],
                    "confidence": 0.9,
                    "needs_strong_review": False,
                    "reason": "只作分流候选。",
                }
            )
        results[-1]["evidence"][0]["quote"] += "改写"
        raw = json.dumps(
            {
                "model": z83.api_transport.PINNED_MODEL,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "contract_version": z83.pipeline_inspector.MODEL_OUTPUT_CONTRACT,
                                    "results": results,
                                },
                                ensure_ascii=False,
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
        return FakeResponse(raw)

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.urllib.request, "urlopen", side_effect=opener
        ):
            with pytest.raises(
                z83.pipeline_inspector.InspectorError, match="改写了短引"
            ):
                z83.run_inspector(
                    run_dir,
                    phase="main",
                    allow_test_run_dir=True,
                )
    assert calls == 1
    root = run_dir / "review/inspector"
    hard_stop = z83.read_json(root / "hard_stop.json")
    child_stop = z83.read_json(root / "ch0003/run/hard_stop.json")
    assert hard_stop["completed_chapters"] == []
    assert hard_stop["batch_invocations"] == 1
    assert hard_stop["logical_model_calls_completed"] == 0
    assert hard_stop["network_attempts"] == 1
    assert child_stop["repaired"] is False
    for relative in (
        "ch0003/run/routing_result.json",
        "ch0003/run/strong_review_queue.json",
        "ch0003/run/provisional_pass_bucket.json",
        "ch0003/run/run_receipt.json",
        "combined_routing.json",
    ):
        assert not (root / relative).exists()
    assert not list(root.glob("ch0013/run/requests/**/*_request.json"))
    with pytest.raises(ZBatchError, match="已有工件"):
        z83.run_inspector(run_dir, phase="main", allow_test_run_dir=True)
    with pytest.raises(ZBatchError, match="还没有检查员全量分流票"):
        z83.require_inspector_complete(run_dir, phase="main")


def test_inspector_partial_failure_writes_global_hard_stop(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    _install_historical_v3_main(run_dir)
    z83.build_review(run_dir, phase="main")
    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.pipeline_inspector,
            "run_inspector",
            side_effect=ZBatchError("synthetic inspector failure"),
        ):
            with pytest.raises(ZBatchError, match="synthetic inspector failure"):
                z83.run_inspector(run_dir, phase="main", allow_test_run_dir=True)
    root = run_dir / "review/inspector"
    hard_stop = z83.read_json(root / "hard_stop.json")
    assert (root / "run_claim.json").is_file()
    assert hard_stop["status"] == "hard_stop_no_resume_or_result_selection"
    assert hard_stop["batch_invocations"] == 1
    assert hard_stop["completed_chapters"] == []
    assert not (root / "combined_routing.json").exists()


def test_inspector_combined_ticket_cannot_bypass_completed_manifest(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(tmp_path)
    _install_historical_v3_main(run_dir)
    z83.build_review(run_dir, phase="main")
    _install_synthetic_inspector(run_dir, phase="main")
    manifest_path = run_dir / "review/inspector/run_manifest.json"
    manifest = z83.read_json(manifest_path)
    manifest["status"] = "running_do_not_resume"
    z83.write_json(manifest_path, manifest)
    with pytest.raises(ZBatchError, match="检查员完成状态票错误"):
        z83.require_inspector_complete(run_dir, phase="main")


def test_adjudication_is_bound_to_event_hashes_and_plan_uses_closed_codes(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(tmp_path)
    _install_historical_v3_main(run_dir)
    z83.build_review(run_dir, phase="main")
    adjudication = _completed_adjudication(run_dir)
    # 复现 v3 的唯一语义锚失败，使程序侧计划生成锚修复任务。
    invalid = next(
        row for row in adjudication["anchor_rows"] if row["event_id"] == "EV-C0003-11"
    )
    invalid["verdict"] = "invalid"
    invalid["unsupported_claims"] = ["信息来源未被所挂锚托住"]
    invalid["reason"] = "事件写了信息来源，但所挂冻结短引只托住面试内容。"
    path = run_dir / "review/adjudication_completed.json"
    z83.write_json(path, adjudication)
    validated = z83.validate_adjudication(run_dir, path, phase="main")
    assert set(validated["degraded_record_ids"]) == {"B-C0013-02", "B-C0019-04"}
    _install_synthetic_inspector(run_dir)
    plan = z83.plan_retries(run_dir, path)
    assert len(plan["tasks"]) == 4
    assert all(
        code in z83.RETRY_REASON_TEXT
        for task in plan["tasks"]
        for code in task["reason_codes"]
    )
    assert plan["free_text_adjudication_sent_to_model"] is False
    assert plan["gold_or_case_ids_sent_to_model"] is False
    forged = copy.deepcopy(plan)
    forged["tasks"].append(copy.deepcopy(forged["tasks"][0]))
    z83.write_json(run_dir / "repair/retry_plan.json", forged)
    with pytest.raises(ZBatchError, match="重试计划与绑定判词、预算或封闭原因码不一致"):
        z83.run_retries(run_dir)
    assert not (run_dir / "repair/run_claim.json").exists()


def test_adjudication_rejects_stale_event_sha_and_changed_scale(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    _install_historical_v3_main(run_dir)
    z83.build_review(run_dir, phase="main")
    adjudication = _completed_adjudication(run_dir)
    stale = copy.deepcopy(adjudication)
    stale["anchor_rows"][0]["event_sha256"] = "0" * 64
    stale_path = run_dir / "review/stale.json"
    z83.write_json(stale_path, stale)
    with pytest.raises(ZBatchError, match="未绑定事件内容SHA"):
        z83.validate_adjudication(run_dir, stale_path, phase="main")
    changed = copy.deepcopy(adjudication)
    special = next(
        row for row in changed["current_rows"] if row["record_id"] == "B-C0019-04"
    )
    special["required_floor"] = "partially_preserved"
    changed_path = run_dir / "review/changed_scale.json"
    z83.write_json(changed_path, changed)
    with pytest.raises(ZBatchError, match="偷偷改尺"):
        z83.validate_adjudication(run_dir, changed_path, phase="main")


def test_retry_messages_never_receive_case_ids_or_free_text(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    event = z83.read_json(z83.V3_RUN_DIR / "01_extract/events/ch0003.json")["events"][0]
    messages = z83._build_semantic_retry_messages(
        run_dir=run_dir,
        chapter=3,
        event=event,
        reason_codes=["SEMANTIC_ANCHOR_UNSUPPORTED"],
    )
    text = json.dumps(messages, ensure_ascii=False)
    assert z83.forbidden_model_hits(messages) == []
    assert "SEMANTIC_ANCHOR_UNSUPPORTED" not in text
    assert "只可补挂当前冻结目录内真实支撑锚" in text


@pytest.mark.parametrize("tamper", ["request", "response", "delete_response"])
def test_main_exchange_tampering_breaks_call_lineage(
    tmp_path: Path, tamper: str
) -> None:
    run_dir = _prepare(tmp_path, tamper)
    _install_zero_retry_candidate(run_dir)
    request_path = (
        run_dir / "main/requests/neutral_extract/z83_main_ch0003_request.json"
    )
    response_path = run_dir / "main/responses/neutral_extract/z83_main_ch0003_raw.json"
    if tamper == "request":
        z83.write_json(request_path, {})
    elif tamper == "response":
        raw = z83.read_json(response_path)
        raw["choices"][0]["message"]["content"] = json.dumps(
            {"schema_version": "z-event-v1", "chapter": 3, "events": []},
            ensure_ascii=False,
        )
        z83.write_json(response_path, raw)
    else:
        response_path.unlink()
    with pytest.raises(ZBatchError, match="缺失或 SHA|调用工件集合"):
        z83.verify_call_lineage(run_dir, allow_test_run_dir=True)


def test_main_attempt_inventory_rejects_unapproved_case(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    _install_zero_retry_candidate(run_dir)
    z83.append_jsonl(
        run_dir / "main/call_attempts.jsonl",
        {
            "call_number": 4,
            "max_calls": z83.MAX_NETWORK_ATTEMPTS,
            "stage": "unauthorized_stage",
            "case_id": "unauthorized_case",
            "attempt": 1,
            "request_sha256": "0" * 64,
        },
    )
    manifest_path = run_dir / "main/run_manifest.json"
    metrics_path = run_dir / "main/01_extract/metrics.json"
    manifest = z83.read_json(manifest_path)
    metrics = z83.read_json(metrics_path)
    manifest["network_attempts"] = 4
    metrics["network_attempts"] = 4
    metrics["network_attempts_this_run"] = 4
    z83.write_json(manifest_path, manifest)
    z83.write_json(metrics_path, metrics)
    with pytest.raises(ZBatchError, match="未授权 stage/case"):
        z83.verify_call_lineage(run_dir, allow_test_run_dir=True)


def test_repair_attempt_inventory_rejects_unapproved_case(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    _install_zero_retry_candidate(run_dir)
    z83.append_jsonl(
        run_dir / "repair/call_attempts.jsonl",
        {
            "call_number": 1,
            "max_calls": z83.MAX_NETWORK_ATTEMPTS,
            "stage": "unauthorized_stage",
            "case_id": "unauthorized_case",
            "attempt": 1,
            "request_sha256": "0" * 64,
        },
    )
    manifest_path = run_dir / "repair/run_manifest.json"
    metrics_path = run_dir / "repair/01_extract/metrics.json"
    manifest = z83.read_json(manifest_path)
    metrics = z83.read_json(metrics_path)
    manifest["network_attempts"] = 1
    metrics["network_attempts"] = 1
    z83.write_json(manifest_path, manifest)
    z83.write_json(metrics_path, metrics)
    with pytest.raises(ZBatchError, match="调用尝试总数超过|未授权 stage/case"):
        z83.verify_call_lineage(run_dir, allow_test_run_dir=True)


def test_retry_exchange_rebuilds_response_and_rejects_tampered_request(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(tmp_path)
    stage_dir = run_dir / "repair"
    event = z83.read_json(z83.V3_RUN_DIR / "01_extract/events/ch0003.json")["events"][0]
    messages = z83._build_semantic_retry_messages(
        run_dir=run_dir,
        chapter=3,
        event=event,
        reason_codes=["SEMANTIC_ANCHOR_UNSUPPORTED"],
    )
    bundle = z83.load_bundle(run_dir)
    body = z83.api_transport.build_request_body(
        model=str(bundle.route["model"]),
        messages=messages,
        contract=bundle.stage("targeted_retry"),
    )
    replacement_payload = {
        "replacement_events": [
            {
                "event": "测试人物补齐了原文明示事实。",
                "anchors": [{"anchor_id": "E0001"}],
            }
        ]
    }
    case_id = "z83_repair_ch0003_ev-c0003-01"
    _install_synthetic_exchange(
        stage_dir=stage_dir,
        stage="targeted_retry",
        case_id=case_id,
        body=body,
        content_value=replacement_payload,
    )
    replacements = z83.z77.validate_replacements(
        replacement_payload,
        catalog=z83._catalog(run_dir, 3),
        allow_multiple=False,
    )
    receipt = {
        "chapter": 3,
        **z83._transport_receipt_fields(stage_dir, "targeted_retry", case_id),
        "replacement_count": len(replacements),
        "replacement_sha256": z83.canonical_sha(replacements),
    }
    rebuilt_replacements, strip_rows = z83._verify_retry_exchange(
        run_dir=run_dir,
        stage_dir=stage_dir,
        receipt=receipt,
        expected_messages=messages,
        allow_multiple=False,
    )
    assert rebuilt_replacements == replacements
    assert strip_rows == []
    z83.write_json(stage_dir / receipt["request_path"], {})
    with pytest.raises(ZBatchError, match="缺失或 SHA"):
        z83._verify_retry_exchange(
            run_dir=run_dir,
            stage_dir=stage_dir,
            receipt=receipt,
            expected_messages=messages,
            allow_multiple=False,
        )


def test_zero_retry_path_rebuilds_final_review_and_can_pass_four_gates(
    tmp_path: Path,
) -> None:
    run_dir = _prepare(tmp_path)
    _install_zero_retry_candidate(run_dir)
    z83.build_review(run_dir, phase="final")
    final_adjudication = _completed_adjudication(run_dir, phase="final")
    for row in final_adjudication["current_rows"]:
        if row["record_id"] in {"B-C0013-02", "B-C0019-04"}:
            row["verdict"] = "preserved"
            row["reason"] = "测试夹具把两条指定记录判为完整保留。"
    for row in final_adjudication["gold_rows"]:
        if row["verdict"] == "coverage_only_invalid_support":
            row["verdict"] = "semantic_shadow"
            row["reason"] = "测试夹具把来源关系判为有效语义影子。"
    final_path = run_dir / "final_review/adjudication_all_clear.json"
    z83.write_json(final_path, final_adjudication)
    _install_synthetic_inspector(run_dir, phase="final")
    scorecard = z83.finalize(run_dir, final_path, allow_test_run_dir=True)
    assert scorecard["all_pass"] is True
    assert scorecard["program_risk_precondition"]["passed"] is True
    assert scorecard["four_gates"] == {
        "mechanical_three_gates": True,
        "old25_zero_regression": True,
        "chapter3_gold_floor": True,
        "semantic_anchor_invalid_zero": True,
    }


def test_final_retry_required_risk_cannot_report_pass(tmp_path: Path) -> None:
    run_dir = _prepare(tmp_path)
    _install_historical_v3_main(run_dir)
    z83.build_review(run_dir, phase="main")
    adjudication = _completed_adjudication(run_dir)
    for row in adjudication["current_rows"]:
        if row["record_id"] in {"B-C0013-02", "B-C0019-04"}:
            row["verdict"] = "preserved"
            row["reason"] = "测试夹具恢复两条指定记录。"
    for row in adjudication["gold_rows"]:
        if row["verdict"] == "coverage_only_invalid_support":
            row["verdict"] = "semantic_shadow"
            row["reason"] = "测试夹具登记有效影子。"
    main_path = run_dir / "review/adjudication_all_clear.json"
    z83.write_json(main_path, adjudication)
    _install_synthetic_inspector(run_dir, phase="main")
    assert z83.plan_retries(run_dir, main_path)["status"] == "no_retry_needed"
    z83.run_retries(run_dir)
    z83.build_review(run_dir, phase="final")
    final_adjudication = _completed_adjudication(run_dir, phase="final")
    for row in final_adjudication["current_rows"]:
        if row["record_id"] in {"B-C0013-02", "B-C0019-04"}:
            row["verdict"] = "preserved"
            row["reason"] = "测试夹具恢复两条指定记录。"
    for row in final_adjudication["gold_rows"]:
        if row["verdict"] == "coverage_only_invalid_support":
            row["verdict"] = "semantic_shadow"
            row["reason"] = "测试夹具登记有效影子。"
    final_adjudication["risk_rows"][0]["verdict"] = "retry_required"
    final_adjudication["risk_rows"][0]["reason"] = "最终复核仍要求重写，不能报通过。"
    final_path = run_dir / "final_review/adjudication_blocked.json"
    z83.write_json(final_path, final_adjudication)
    _install_synthetic_inspector(run_dir, phase="final")
    scorecard = z83.finalize(run_dir, final_path, allow_test_run_dir=True)
    assert scorecard["all_pass"] is False
    assert scorecard["program_risk_precondition"]["passed"] is False
    assert scorecard["status"] == "hard_stop_candidate_failed"

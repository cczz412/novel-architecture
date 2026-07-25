from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tools import z98_knife_a_step2_runner as runner


UNIT_RUN_CLAIM_SHA256 = "a" * 64
UNIT_NETWORK_RELEASE_SHA256 = "b" * 64
TEST_CATALOG_APPROVER_KEY_ID = "test-independent-reviewer"
TEST_RSA_MODULUS = int(
    "d1470150df795e087cbbdd6157417cce6b57632147be837f587796a2f1b18437"
    "99f8628c77f9c27c2e7a7247c38ed6390d63b45ae6c24660e560b7e6c39b78"
    "ed4d890e5473bf9645f9d5c96ac87a8ae908f447cbbe5bd0320633af3524845"
    "d57ce3bf47f1fdf94527442d68f07fabbaa19700f7eea64737055ea47043c6e"
    "b95a2dcad2b6b2257e33d1cdfdaa3e66e304b60bdb911ae934ec52affd61d2"
    "d0535ae2a77a0b63e09a21602be7790225edcc5aa2d95fd32a7716bbbfbad21"
    "e4b2daaa6282f5348418241ec5af3a01a6459432080f1b49a9a7db77e7f81a"
    "bd7fc27b1ff29fe7d928b9a775c2624bfce8e62cfd123c66a60aa5c373e791"
    "87a6aba0cb9",
    16,
)
TEST_RSA_PRIVATE_EXPONENT = int(
    "c505b0e775afca27602d70c7906160881b8019e9de3e2dee5924f05c5735321"
    "4ccf65aeab6fc1c3a06ae3a08c2c326b1a2d2fe68d5f6f0b7f53af5e794b9"
    "d3a8aee64fb42beb09585153772960e7b09906f1da190d0dc317222c666a04d"
    "3d8b3618c09f917d262677e134858d98d7dd9963939c3d8e13f73593c13596"
    "6653112e8cba8526c2d13d257593641f297a674bc6ffee2fea18e4d6b1b0eb"
    "b68e7b17c569516444bc705c69ee594db6dda297750efd1b7356db86803d55d"
    "02949eef39aea1c11e0f7c7df33306ff05cfdd62e9f0fc75ab20c64c5c651b"
    "5b0aaf21a15e0d3af72d7c5b336f3297c9ce7edbb72e3e273341939d856b86"
    "94d3f162367a5",
    16,
)


@pytest.fixture
def unit_authority_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    """检查点单元测试只隔离外部权威链，不给正式 finalize 放行。"""

    value = {
        "run_claim_sha256": UNIT_RUN_CLAIM_SHA256,
        "network_release_sha256": UNIT_NETWORK_RELEASE_SHA256,
    }
    monkeypatch.setattr(
        runner,
        "_validate_runtime_authority_chain",
        lambda _run_dir: value,
    )
    return value


def _formal_checkpoint_for_node(
    run_dir: Path,
    node: dict[str, object],
) -> None:
    node_id = str(node["node_id"])
    node_root = run_dir / f"runtime/{node_id}"
    budget_reservation: dict[str, object] | None = None
    if node["node_kind"] == "repair":
        repair_request = runner.read_json(
            runner.ROOT / str(node["repair_request_path"])
        )
        if node["contract_mode"] == "single_patch":
            request_payload = json.loads(
                repair_request["model_visible"]["messages"][1]["content"]
            )
            source = request_payload["input"]
            model_payload: dict[str, object] = {
                "op": "KEEP",
                "target_event_ids": [source["source_event_id"]],
                "source_span_ids": [source["source_span_ids"][0]],
                "actor": "测试主体",
                "predicate": "执行",
                "object_or_result": "测试动作",
                "hard_qualifiers": [],
                "fact_class": "event",
                "speaker": None,
                "anchor_candidates": [],
            }
        else:
            model_payload = {
                "schema": "atom-batch-v2",
                "request_id": repair_request["request_id"],
                "items": [
                    {
                        "slot_id": slot_id,
                        "status": "unsupported",
                        "atom": None,
                        "split_span_ids": [],
                        "missing_context_codes": [],
                    }
                    for slot_id in repair_request["slot_ids"]
                ],
                "receipt": {
                    "returned_slot_ids": repair_request["slot_ids"],
                },
            }
        candidate = runner._validate_repair_candidate(
            node,
            model_payload,
            repair_request,
        )
        body: dict[str, object] = {
            "model": runner._model_id_for_node(node),
            "messages": repair_request["model_visible"]["messages"],
        }
    else:
        plan = runner.read_json(run_dir / "prepared/run_plan.json")["nodes"]
        nodes_by_id = {str(row["node_id"]): row for row in plan}
        repair_node = nodes_by_id[str(node["depends_on"][0])]
        mappings = runner.read_json(
            run_dir / "inputs/r05/mappings/verifier_mapping.json"
        )["mappings"]
        mapping = next(
            row
            for row in mappings
            if row["repair_request_path"] == repair_node["repair_request_path"]
        )
        template = runner.read_json(
            runner.R05_ROOT / mapping["verifier_template_path"]
        )
        accumulated_tokens, accumulated_cost = (
            runner._qwen_actual_totals_before_node(
                run_dir,
                plan,
                node_id=node_id,
            )
        )
        repair_root = run_dir / f"runtime/{repair_node['node_id']}"
        dynamic = runner.render_dynamic_verifier_request(
            template,
            expected_template_sha256=mapping["verifier_template_sha256"],
            repair_request_bytes=(
                runner.ROOT / repair_node["repair_request_path"]
            ).read_bytes(),
            p2_response_path=(
                repair_root / "model_content.json"
            ).relative_to(run_dir).as_posix(),
            p2_response_bytes=(repair_root / "model_content.json").read_bytes(),
            repair_node=repair_node,
            judge_node=node,
            call_attempt_path=(
                repair_root / "call_attempt.json"
            ).relative_to(run_dir).as_posix(),
            call_attempt_bytes=(repair_root / "call_attempt.json").read_bytes(),
            usage_path=(
                repair_root / "usage.json"
            ).relative_to(run_dir).as_posix(),
            usage_bytes=(repair_root / "usage.json").read_bytes(),
            actual_accumulated_tokens=accumulated_tokens,
            actual_accumulated_micro_cny=accumulated_cost,
        )
        body = dynamic["request_body"]
        budget_reservation = runner._write_qwen_budget_reservation(
            run_dir=run_dir,
            node=node,
            budget_preflight=dynamic["budget_preflight"],
            accumulated_tokens=accumulated_tokens,
            accumulated_micro_cny=accumulated_cost,
            max_attempts=3,
        )
        model_payload = {
            "schema": "z98-independent-verdict-v1",
            "case_id": template["private_binding"]["case_id"],
            "items": [
                {
                    "item_id": item_id,
                    "verdict": "PASS",
                    "fact_support": "SUPPORTED",
                    "qualifier_support": "COMPLETE",
                    "anchor_support": "FULL",
                    "atomicity": "ATOMIC",
                    "reason_codes": ["NONE"],
                }
                for item_id in template["private_binding"]["item_ids"]
            ],
            "receipt": {
                "returned_item_ids": template["private_binding"]["item_ids"],
            },
        }
        verdict = runner.parse_verifier_content(
            json.dumps(model_payload, ensure_ascii=False),
            expected_case_id=template["private_binding"]["case_id"],
            expected_item_ids=template["private_binding"]["item_ids"],
        )
    request_record = {
        "schema_version": "z98-live-request-artifact-v1",
        "run_id": run_dir.name,
        "run_claim_sha256": UNIT_RUN_CLAIM_SHA256,
        "network_release_sha256": UNIT_NETWORK_RELEASE_SHA256,
        "node_id": node_id,
        "node_sequence": node["sequence"],
        "node_kind": node["node_kind"],
        "provider": runner._provider_id_for_node(node),
        "model": runner._model_id_for_node(node),
        "contract_version": runner.CONTRACT_VERSION,
        "body": body,
        "_security": "no_api_key_no_authorization",
    }
    request_path = node_root / "request_artifact.json"
    runner.model_benchmark.write_json_exclusive(request_path, request_record)
    request_sha = runner.sha256_file(request_path)
    wire_sha = runner.sha256_bytes(
        json.dumps(body, ensure_ascii=False).encode("utf-8")
    )
    usage = {
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "total_tokens": 2,
    }
    content = json.dumps(model_payload, ensure_ascii=False)
    raw_response = {
        "model": runner._model_id_for_node(node),
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": content,
                    "reasoning_content": "",
                },
            }
        ],
        "usage": usage,
    }
    raw_bytes = json.dumps(raw_response, ensure_ascii=False).encode("utf-8")
    transport_raw = node_root / "transport/raw_responses/attempt01.json"
    runner.model_benchmark.write_bytes_exclusive(transport_raw, raw_bytes)
    raw_copy = node_root / "raw_provider_response.json"
    model_copy = node_root / "model_content.json"
    runner.model_benchmark.write_bytes_exclusive(raw_copy, raw_bytes)
    runner.model_benchmark.write_bytes_exclusive(
        model_copy,
        content.encode("utf-8"),
    )
    reservation = {
        "schema_version": "model-benchmark-attempt-reservation-v1",
        "logical_request_id": node_id,
        "attempt": 1,
        "request_artifact_sha256": request_sha,
        "wire_body_sha256": wire_sha,
        "reserved_at": "2026-07-24T00:00:00+00:00",
    }
    reservation["row_sha256"] = runner.canonical_sha(reservation)
    reservation_path = (
        node_root / "transport/attempt_reservations.jsonl"
    )
    reservation_path.parent.mkdir(parents=True, exist_ok=True)
    reservation_path.write_text(
        json.dumps(reservation, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    attempt = {
        "schema": runner.z83_retry_transport.ATTEMPT_LEDGER_SCHEMA,
        "logical_request_id": node_id,
        "chapter": runner._chapter_number(str(node["chapter_id"])),
        "attempt": 1,
        "http_status": 200,
        "outcome": "success",
        "request_sha256": request_sha,
        "raw_response_sha256": runner.sha256_bytes(raw_bytes),
        "usage": usage,
        "retry_after_raw": None,
        "retry_after_seconds": None,
        "wire_body_sha256": wire_sha,
        "request_artifact_sha256": request_sha,
        "error_code": None,
        "error_body_sha256": None,
        "started_at": "2026-07-24T00:00:00+00:00",
        "finished_at": "2026-07-24T00:00:01+00:00",
        "pre_request_spacing_planned_seconds": 0.0,
        "pre_request_spacing_seconds": 0.0,
        "retry_wait_seconds": 0.0,
        "retry_wait_actual_seconds": 0.0,
        "previous_attempt": None,
        "usage_status": "returned",
    }
    attempt["row_sha256"] = runner.canonical_sha(attempt)
    ledger = node_root / "transport/call_attempts.jsonl"
    ledger.write_text(
        json.dumps(attempt, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if node["node_kind"] == "repair":
        result = runner.z83_retry_transport.LogicalRequestResult(
            runner.z83_retry_transport.AttemptOutcome(
                http_status=200,
                request_sha256=request_sha,
                raw_response_sha256=runner.sha256_bytes(raw_bytes),
                usage=usage,
                payload={
                    "raw_path": transport_raw,
                    "response_json": raw_response,
                },
                wire_body_sha256=wire_sha,
                request_artifact_sha256=request_sha,
            ),
            (attempt,),
            {},
        )
        call_path, call_bytes, usage_path, usage_bytes = (
            runner._repair_normalized_tickets(
                run_dir=run_dir,
                node=node,
                model_content_path=model_copy,
                model_content_bytes=content.encode("utf-8"),
                result=result,
                usage=usage,
            )
        )
        response = {
            "provider_response_path": raw_copy.relative_to(run_dir).as_posix(),
            "provider_response_sha256": runner.sha256_bytes(raw_bytes),
            "model_content_path": model_copy.relative_to(run_dir).as_posix(),
            "model_content_sha256": runner.sha256_bytes(
                content.encode("utf-8")
            ),
            "response_model": runner._model_id_for_node(node),
            "finish_reason": "stop",
            "reasoning_content_sha256": runner.sha256_bytes(b""),
            "candidate": candidate,
            "normalized_call_attempt_path": call_path,
            "normalized_call_attempt_sha256": runner.sha256_bytes(call_bytes),
            "normalized_usage_path": usage_path,
            "normalized_usage_sha256": runner.sha256_bytes(usage_bytes),
        }
    else:
        assert budget_reservation is not None
        runner._write_qwen_budget_settlement(
            run_dir=run_dir,
            node=node,
            reservation=budget_reservation,
            attempts=[attempt],
            usage=usage,
        )
        reservation_path, settlement_path = runner._qwen_budget_paths(
            run_dir,
            node_id,
        )
        response = {
            "provider_response_path": raw_copy.relative_to(run_dir).as_posix(),
            "provider_response_sha256": runner.sha256_bytes(raw_bytes),
            "model_content_path": model_copy.relative_to(run_dir).as_posix(),
            "model_content_sha256": runner.sha256_bytes(
                content.encode("utf-8")
            ),
            "response_model": runner._model_id_for_node(node),
            "finish_reason": "stop",
            "reasoning_content_sha256": runner.sha256_bytes(b""),
            "verdict": verdict,
            "dynamic_source_binding": dynamic["source_binding"],
            "budget_preflight": dynamic["budget_preflight"],
            "budget_reservation_path": (
                reservation_path.relative_to(run_dir).as_posix()
            ),
            "budget_reservation_sha256": runner.sha256_file(
                reservation_path
            ),
            "budget_settlement_path": (
                settlement_path.relative_to(run_dir).as_posix()
            ),
            "budget_settlement_sha256": runner.sha256_file(
                settlement_path
            ),
        }
    runner._write_formal_checkpoint(
        run_dir,
        node=node,
        request_record=request_record,
        response_record=response,
        usage=usage,
        attempts=[attempt],
    )


def _plausible_but_untrusted_repair_authority() -> dict[str, object]:
    """构造字段齐全但没有外部信任钉子的伪权威票。"""

    return {
        "schema_version": runner.REPAIR_AUTHORITY_SCHEMA,
        "status": "APPROVED_FOR_Z98_STEP2",
        "fixture_only_non_sendable": False,
        "automatic_provider_fallback": False,
        "authority": {
            "notion_queue_url": runner.NOTION_QUEUE_URL,
            "notion_ledger_url": runner.NOTION_LEDGER_URL,
            "authority_time": "2026-07-24T00:00:00+08:00",
            "approval_text_sha256": "a" * 64,
        },
        "lane_profiles": {
            lane: {
                **contract,
                "body_fields": {
                    "temperature": 0.2,
                    "max_tokens": 8000,
                    "n": 1,
                },
            }
            for lane, contract in runner.LANE_CONTRACTS.items()
        },
    }


def _trust_fake_qianwen_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """给目录适配器测试造一份显式钉住内容身份的 CLI 包。"""

    package_root = tmp_path / "node_modules/@qwenai/qianwen-cli"
    executable = package_root / "bin/qianwen"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    manifest = package_root / "package.json"
    manifest.write_text(
        json.dumps(
            {
                "name": "@qwenai/qianwen-cli",
                "version": "1.3.0",
                "_integrity": "sha512-test-only",
                "bin": {"qianwen": "bin/qianwen"},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner.shutil, "which", lambda _: str(executable))
    monkeypatch.setattr(
        runner,
        "TRUSTED_QWEN_CLI_IDENTITIES",
        {
            runner.sha256_file(executable): {
                "package_name": "@qwenai/qianwen-cli",
                "package_version": "1.3.0",
                "npm_integrity": "sha512-test-only",
                "package_manifest_path": str(manifest.resolve()),
                "package_manifest_sha256": runner.sha256_file(manifest),
                "command_version": "qianwen 1.3.0",
            }
        },
    )
    return executable.resolve()


def _prepare_catalog_run(tmp_path: Path, name: str = "r07") -> Path:
    run_dir = tmp_path / name
    runner.prepare(run_dir)
    return run_dir


def _rsa_pkcs1v15_sha256_test_signature(message: bytes) -> str:
    size = (TEST_RSA_MODULUS.bit_length() + 7) // 8
    digest_info = (
        bytes.fromhex("3031300d060960864801650304020105000420")
        + hashlib.sha256(message).digest()
    )
    encoded = (
        b"\x00\x01"
        + (b"\xff" * (size - len(digest_info) - 3))
        + b"\x00"
        + digest_info
    )
    signature = pow(
        int.from_bytes(encoded, "big"),
        TEST_RSA_PRIVATE_EXPONENT,
        TEST_RSA_MODULUS,
    ).to_bytes(size, "big")
    return base64.b64encode(signature).decode("ascii")


def _independently_sign_catalog_receipt(
    receipt_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = json.loads(receipt_path.read_text())
    approval = {
        "schema_version": runner.CATALOG_APPROVAL_SCHEMA,
        "status": "APPROVED_BY_INDEPENDENT_REVIEW",
        "algorithm": runner.CATALOG_APPROVAL_ALGORITHM,
        "key_id": TEST_CATALOG_APPROVER_KEY_ID,
        "approved_at": receipt["checked_at"],
        "signed_payload_sha256": "",
        "signature_base64": "",
    }
    receipt["independent_approval"] = approval
    message = runner._catalog_approval_message(receipt, approval)
    approval["signed_payload_sha256"] = runner.sha256_bytes(message)
    approval["signature_base64"] = _rsa_pkcs1v15_sha256_test_signature(
        message
    )
    receipt_path.write_bytes(runner.json_bytes(receipt))
    monkeypatch.setattr(
        runner,
        "TRUSTED_QWEN_CATALOG_APPROVER_KEYS",
        {
            TEST_CATALOG_APPROVER_KEY_ID: {
                "algorithm": runner.CATALOG_APPROVAL_ALGORITHM,
                "modulus_hex": format(TEST_RSA_MODULUS, "x"),
                "exponent": 65537,
            }
        },
    )


def _valid_repair_authority() -> dict[str, object]:
    profiles = {
        lane: {
            **contract,
            "body_fields": {
                "temperature": 0.2,
                "max_tokens": 8000,
                "n": 1,
            },
        }
        for lane, contract in runner.LANE_CONTRACTS.items()
    }
    approval_text = "批准第98道步二冻结外壳；仅供本测试验证权威链。"
    return {
        "schema_version": runner.REPAIR_AUTHORITY_SCHEMA,
        "status": "APPROVED_FOR_Z98_STEP2",
        "fixture_only_non_sendable": False,
        "automatic_provider_fallback": False,
        "authority": {
            "notion_queue_url": runner.NOTION_QUEUE_URL,
            "notion_queue_page_id": runner.NOTION_QUEUE_PAGE_ID,
            "notion_ledger_url": runner.NOTION_LEDGER_URL,
            "notion_ledger_page_id": runner.NOTION_LEDGER_PAGE_ID,
            "approval_block_id": "test-approval-block",
            "approval_block_last_edited_time": (
                "2026-07-24T20:20:00+08:00"
            ),
            "approval_text": approval_text,
            "approval_text_sha256": runner.sha256_bytes(
                approval_text.encode("utf-8")
            ),
            "lane_profiles_sha256": runner.canonical_sha(profiles),
            "readback_receipt_id": "test-independent-readback",
        },
        "lane_profiles": profiles,
    }


def _write_structural_catalog_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    run_dir: Path,
) -> Path:
    _trust_fake_qianwen_cli(tmp_path, monkeypatch)

    def command_runner(
        command: list[str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        if command[-1] == "version":
            return subprocess.CompletedProcess(
                command,
                0,
                "qianwen 1.3.0\n",
                "",
            )
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "models": [{"id": runner.QWEN_MODEL_ID}],
                    "total": 1,
                    "all": True,
                }
            ),
            "",
        )

    output = tmp_path / f"catalog-{run_dir.name}"
    runner.catalog_check(
        output,
        run_dir=run_dir,
        command_runner=command_runner,
    )
    receipt_path = output / "qwen_catalog_receipt.json"
    _independently_sign_catalog_receipt(receipt_path, monkeypatch)
    return receipt_path


def test_prepare_is_zero_call_and_rebuilds_identically(tmp_path: Path) -> None:
    first = tmp_path / "a/r07"
    second = tmp_path / "b/r07"

    one = runner.prepare(first)
    runner.prepare(second)

    assert one["status"] == "PASS_ZERO_CALL_EXECUTOR_REHEARSAL_LIVE_BLOCKED"
    assert one["model_api_calls"] == 0
    assert one["provider_catalog_requests"] == 0
    assert one["network_attempts"] == 0
    assert one["keys_loaded"] is False
    assert runner.verify_prepared(first) == runner.verify_prepared(second)

    def vector(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    assert vector(first) == vector(second)
    rehearsal = json.loads(
        (first / "rehearsal/full_chain_receipt.json").read_text()
    )
    assert rehearsal["completed_nodes"] == 68
    assert rehearsal["checkpoint_file_count"] == 340
    assert rehearsal["fixture_only_non_sendable"] is True


def test_catalog_check_accepts_only_exact_authenticated_catalog_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _prepare_catalog_run(tmp_path)
    executable = _trust_fake_qianwen_cli(tmp_path, monkeypatch)
    calls: list[list[str]] = []

    def command_runner(
        command: list[str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[-1] == "version":
            return subprocess.CompletedProcess(
                command,
                0,
                "qianwen 1.3.0\n",
                "",
            )
        payload = {
            "models": [
                {
                    "id": runner.QWEN_MODEL_ID,
                    "can_try": True,
                    "modality": {"input": ["text"], "output": ["text"]},
                    "free_tier": {},
                }
            ],
            "total": 1,
            "all": True,
        }
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(payload, ensure_ascii=False),
            "",
        )

    result = runner.catalog_check(
        tmp_path / "catalog",
        run_dir=run_dir,
        command_runner=command_runner,
    )

    assert (
        result["status"]
        == "STRUCTURALLY_VALID_AWAITING_INDEPENDENT_SIGNATURE"
    )
    assert calls == [
        [str(executable.resolve()), "version"],
        [
            str(executable.resolve()),
            "models",
            "list",
            "--all",
            "--format",
            "json",
        ],
    ]
    receipt = json.loads(
        (tmp_path / "catalog/qwen_catalog_receipt.json").read_text()
    )
    assert receipt["selected_model_id"] == runner.QWEN_MODEL_ID
    assert (
        receipt["status_evidence_kind"]
        == "authenticated_catalog_membership"
    )
    assert receipt["automatic_fallback"] is False


def test_prepare_catalog_independent_signature_and_preflight_have_no_self_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """公钥和 CLI 身份先钉住，出票后不再改 runner 或 prepared manifest。"""

    _trust_fake_qianwen_cli(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runner,
        "TRUSTED_QWEN_CATALOG_APPROVER_KEYS",
        {
            TEST_CATALOG_APPROVER_KEY_ID: {
                "algorithm": runner.CATALOG_APPROVAL_ALGORITHM,
                "modulus_hex": format(TEST_RSA_MODULUS, "x"),
                "exponent": 65537,
            }
        },
    )
    runner_sha_before = runner.sha256_file(Path(runner.__file__))
    run_dir = _prepare_catalog_run(tmp_path)
    prepared_manifest_before = runner.sha256_file(
        run_dir / "prepared/artifact_manifest.json"
    )
    receipt_path = _write_structural_catalog_receipt(
        tmp_path,
        monkeypatch,
        run_dir=run_dir,
    )
    repair_path = tmp_path / "repair-authority.json"
    repair_path.write_bytes(runner.json_bytes(_valid_repair_authority()))
    monkeypatch.setattr(
        runner,
        "TRUSTED_REPAIR_AUTHORITY_RECEIPT_SHA256S",
        frozenset({runner.sha256_file(repair_path)}),
    )

    authority = runner.live_preflight(
        run_dir,
        repair_authority_path=repair_path,
        qwen_catalog_receipt_path=receipt_path,
    )

    assert authority.qwen_catalog["selected_model_id"] == runner.QWEN_MODEL_ID
    assert runner.sha256_file(Path(runner.__file__)) == runner_sha_before
    assert (
        runner.sha256_file(run_dir / "prepared/artifact_manifest.json")
        == prepared_manifest_before
    )
    assert runner.verify_prepared(run_dir)["status"].startswith("PASS_")


def test_catalog_receipt_rejects_raw_or_cli_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _prepare_catalog_run(tmp_path)
    executable = _trust_fake_qianwen_cli(tmp_path, monkeypatch)
    payload = {
        "models": [{"id": runner.QWEN_MODEL_ID}],
        "total": 1,
        "all": True,
    }

    def command_runner(
        command: list[str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        if command[-1] == "version":
            return subprocess.CompletedProcess(
                command,
                0,
                "qianwen 1.3.0\n",
                "",
            )
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(payload),
            "",
        )

    output = tmp_path / "catalog"
    runner.catalog_check(
        output,
        run_dir=run_dir,
        command_runner=command_runner,
    )
    receipt = json.loads(
        (output / "qwen_catalog_receipt.json").read_text()
    )
    raw_path = output / "raw_catalog_stdout.json"
    original_raw = raw_path.read_bytes()

    raw_path.write_text('{"models":[]}\n', encoding="utf-8")
    with pytest.raises(runner.Z98Step2HardStop) as raw_error:
        runner._validate_catalog_receipt(
            receipt,
            run_dir=run_dir,
            require_approval=False,
        )
    assert raw_error.value.reason_code == "qwen_catalog_raw_drift"

    raw_path.write_bytes(original_raw)
    executable.write_text("#!/bin/sh\n# changed\n", encoding="utf-8")
    with pytest.raises(runner.Z98Step2HardStop) as cli_error:
        runner._validate_catalog_receipt(
            receipt,
            run_dir=run_dir,
            require_approval=False,
        )
    assert cli_error.value.reason_code == "qwen_catalog_adapter_drift"


def test_catalog_check_rejects_missing_exact_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _prepare_catalog_run(tmp_path)
    _trust_fake_qianwen_cli(tmp_path, monkeypatch)

    def command_runner(
        command: list[str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        if command[-1] == "version":
            return subprocess.CompletedProcess(
                command,
                0,
                "qianwen 1.3.0\n",
                "",
            )
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {"models": [{"id": "qwen3.7-max"}], "total": 1, "all": True
                }
            ),
            "",
        )

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner.catalog_check(
            tmp_path / "catalog",
            run_dir=run_dir,
            command_runner=command_runner,
        )
    assert error.value.reason_code == "qwen_exact_model_not_unique"


def test_catalog_check_rejects_cli_outside_trusted_content_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """文件名叫 qianwen 也不能自行升级成“官方 CLI”。"""

    executable = tmp_path / "untrusted/bin/qianwen"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setattr(runner.shutil, "which", lambda _: str(executable))
    monkeypatch.setattr(runner, "TRUSTED_QWEN_CLI_IDENTITIES", {})
    run_dir = _prepare_catalog_run(tmp_path)
    invoked = False

    def command_runner(
        command: list[str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal invoked
        invoked = True
        return subprocess.CompletedProcess(command, 0, "should-not-run\n", "")

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner.catalog_check(
            tmp_path / "catalog",
            run_dir=run_dir,
            command_runner=command_runner,
        )

    assert error.value.reason_code == "qwen_catalog_adapter_untrusted"
    assert invoked is False
    assert not (tmp_path / "catalog").exists()


def test_catalog_receipt_without_attempt_reservation_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _prepare_catalog_run(tmp_path)
    receipt_path = _write_structural_catalog_receipt(
        tmp_path,
        monkeypatch,
        run_dir=run_dir,
    )
    reservation_path = Path(
        json.loads(receipt_path.read_text())[
            "catalog_attempt_reservation_path"
        ]
    )
    reservation_path.unlink()

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner._validate_catalog_receipt_path(
            receipt_path,
            run_dir=run_dir,
            require_fresh=True,
        )

    assert error.value.reason_code == "qwen_catalog_reservation_missing"


def test_catalog_receipt_cannot_cross_runs_or_outlive_ttl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _prepare_catalog_run(tmp_path, "r07-source")
    other_run = _prepare_catalog_run(tmp_path, "r07-other")
    receipt_path = _write_structural_catalog_receipt(
        tmp_path,
        monkeypatch,
        run_dir=run_dir,
    )

    with pytest.raises(runner.Z98Step2HardStop) as cross_run:
        runner._validate_catalog_receipt_path(
            receipt_path,
            run_dir=other_run,
            require_fresh=True,
        )
    assert cross_run.value.reason_code == "qwen_catalog_receipt_cross_run"

    receipt = json.loads(receipt_path.read_text())
    reservation_path = Path(receipt["catalog_attempt_reservation_path"])
    reservation = json.loads(reservation_path.read_text())
    reservation["reserved_at"] = "2000-01-01T00:00:00+00:00"
    reservation_path.write_bytes(runner.json_bytes(reservation))
    receipt["catalog_attempt_reservation_sha256"] = runner.sha256_file(
        reservation_path
    )
    receipt["checked_at"] = "2000-01-01T00:01:00+00:00"
    receipt_path.write_bytes(runner.json_bytes(receipt))

    with pytest.raises(runner.Z98Step2HardStop) as expired:
        runner._validate_catalog_receipt_path(
            receipt_path,
            run_dir=run_dir,
            require_fresh=True,
        )
    assert expired.value.reason_code == "qwen_catalog_receipt_expired"


def test_catalog_receipt_cannot_replay_to_same_named_run_elsewhere(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_run = tmp_path / "source/r07"
    target_run = tmp_path / "target/r07"
    runner.prepare(source_run)
    runner.prepare(target_run)
    assert source_run.name == target_run.name
    assert runner.sha256_file(
        source_run / "prepared/artifact_manifest.json"
    ) == runner.sha256_file(
        target_run / "prepared/artifact_manifest.json"
    )
    receipt_path = _write_structural_catalog_receipt(
        tmp_path,
        monkeypatch,
        run_dir=source_run,
    )

    with pytest.raises(runner.Z98Step2HardStop) as replay:
        runner._validate_catalog_receipt_path(
            receipt_path,
            run_dir=target_run,
            require_fresh=True,
        )

    assert replay.value.reason_code == "qwen_catalog_receipt_cross_run"


def test_catalog_signature_rejects_untrusted_key_and_signed_context_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _prepare_catalog_run(tmp_path)
    receipt_path = _write_structural_catalog_receipt(
        tmp_path,
        monkeypatch,
        run_dir=run_dir,
    )
    trusted_keys = runner.TRUSTED_QWEN_CATALOG_APPROVER_KEYS
    monkeypatch.setattr(
        runner,
        "TRUSTED_QWEN_CATALOG_APPROVER_KEYS",
        {},
    )
    with pytest.raises(runner.Z98Step2HardStop) as untrusted:
        runner._validate_catalog_receipt_path(
            receipt_path,
            run_dir=run_dir,
            require_fresh=True,
        )
    assert untrusted.value.reason_code == "qwen_catalog_approver_untrusted"

    monkeypatch.setattr(
        runner,
        "TRUSTED_QWEN_CATALOG_APPROVER_KEYS",
        trusted_keys,
    )
    receipt = json.loads(receipt_path.read_text())
    receipt["independent_approval"]["approved_at"] = (
        "2099-01-01T00:00:00+00:00"
    )
    receipt_path.write_bytes(runner.json_bytes(receipt))
    with pytest.raises(runner.Z98Step2HardStop) as tampered:
        runner._validate_catalog_receipt_path(
            receipt_path,
            run_dir=run_dir,
            require_fresh=True,
        )
    assert tampered.value.reason_code == "qwen_catalog_receipt_untrusted"


def test_random_plausible_notion_authority_receipt_is_not_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """字段自洽、URL正确、SHA格式正确，也不能由本地随机自签。"""

    path = tmp_path / "notion_authority.json"
    path.write_text(
        json.dumps(
            _plausible_but_untrusted_repair_authority(),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "TRUSTED_REPAIR_AUTHORITY_RECEIPT_SHA256S",
        frozenset(),
    )

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner._validate_repair_authority_path(path)

    assert error.value.reason_code == "repair_envelope_authority_untrusted"


def test_preflight_without_authority_stops_before_secret_or_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    monkeypatch.setenv("SENSENOVA_API_KEY", "must-not-be-read")
    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "must-not-be-read")
    monkeypatch.setenv(runner.QWEN_KEY_ENV, "must-not-be-read")

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner.live_preflight(
            run_dir,
            repair_authority_path=None,
            qwen_catalog_receipt_path=None,
        )

    assert error.value.reason_code == "repair_envelope_authority_missing"
    assert not (run_dir / "runtime").exists()


def test_run_preflight_failure_writes_permanent_pre_network_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正式 run 也必须走会落票的唯一预检入口，不能只抛异常。"""

    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    missing_authority = tmp_path / "missing-authority.json"
    missing_catalog = tmp_path / "missing-catalog.json"
    monkeypatch.setenv("SENSENOVA_API_KEY", "must-not-be-read")
    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "must-not-be-read")
    monkeypatch.setenv(runner.QWEN_KEY_ENV, "must-not-be-read")

    with pytest.raises(runner.Z98Step2HardStop) as first:
        runner.run_live(
            run_dir,
            repair_authority_path=missing_authority,
            qwen_catalog_receipt_path=missing_catalog,
        )
    assert first.value.reason_code == "repair_envelope_authority_missing"
    hard_stop_path = run_dir / "pre_network_hard_stop.json"
    assert hard_stop_path.is_file()
    hard_stop = json.loads(hard_stop_path.read_text())
    assert hard_stop["network_attempts"] == 0
    assert hard_stop["secret_values_read"] is False

    with pytest.raises(runner.Z98Step2HardStop) as second:
        runner.run_live(
            run_dir,
            repair_authority_path=missing_authority,
            qwen_catalog_receipt_path=missing_catalog,
        )
    assert (
        second.value.reason_code
        == "pre_network_hard_stopped_run_not_resumable"
    )


def test_second_run_cannot_pollute_an_existing_atomic_run_slot(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    runner._claim_run_slot(run_dir)
    slot_path = run_dir / "runtime/run_slot.json"
    original_slot = slot_path.read_bytes()

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner.run_live(
            run_dir,
            repair_authority_path=tmp_path / "missing-authority.json",
            qwen_catalog_receipt_path=tmp_path / "missing-catalog.json",
        )

    assert error.value.reason_code == "run_slot_already_reserved"
    assert slot_path.read_bytes() == original_slot
    assert not (run_dir / "pre_network_hard_stop.json").exists()


def test_run_records_failure_after_its_own_atomic_slot_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    monkeypatch.setattr(
        runner,
        "live_preflight",
        lambda *_args, **_kwargs: runner.LiveAuthority(
            repair_envelope={},
            qwen_catalog={},
        ),
    )

    def fail_after_claim(*_args: object, **_kwargs: object) -> None:
        raise runner.Z98Step2HardStop(
            "authority_copy_failed",
            "测试：本进程占槽后复制权威票失败",
        )

    monkeypatch.setattr(
        runner,
        "_copy_live_authority_receipts",
        fail_after_claim,
    )

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner.run_live(
            run_dir,
            repair_authority_path=tmp_path / "repair.json",
            qwen_catalog_receipt_path=tmp_path / "catalog.json",
        )

    assert error.value.reason_code == "authority_copy_failed"
    slot_path = run_dir / "runtime/run_slot.json"
    hard_stop_path = run_dir / "pre_network_hard_stop.json"
    assert slot_path.is_file()
    assert hard_stop_path.is_file()
    hard_stop = json.loads(hard_stop_path.read_text())
    assert hard_stop["reason_code"] == "authority_copy_failed"
    assert hard_stop["run_slot_sha256"] == runner.sha256_file(slot_path)
    assert hard_stop["network_attempts"] == 0
    assert hard_stop["secret_values_read"] is False


def test_pre_network_hard_stop_permanently_locks_run_directory(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    (run_dir / "pre_network_hard_stop.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(runner.Z98Step2HardStop) as preflight:
        runner.live_preflight(
            run_dir,
            repair_authority_path=None,
            qwen_catalog_receipt_path=None,
        )
    assert (
        preflight.value.reason_code
        == "pre_network_hard_stopped_run_not_resumable"
    )
    with pytest.raises(runner.Z98Step2HardStop) as resume:
        runner.resume_or_audit(run_dir)
    assert (
        resume.value.reason_code
        == "pre_network_hard_stopped_run_not_resumable"
    )


def test_resume_rechecks_catalog_ttl_before_sending_more_nodes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    claim_path = run_dir / "runtime/run_claim.json"
    claim_path.parent.mkdir(parents=True)
    claim_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "_validate_repair_authority_path",
        lambda _path: {"status": "approved"},
    )
    observed: dict[str, object] = {}

    def reject_expired(
        _path: Path,
        *,
        run_dir: Path,
        require_fresh: bool,
    ) -> dict[str, object]:
        observed["run_dir"] = run_dir
        observed["require_fresh"] = require_fresh
        raise runner.Z98Step2HardStop(
            "qwen_catalog_receipt_expired",
            "测试：恢复发网必须重新验票时效",
        )

    monkeypatch.setattr(
        runner,
        "_validate_catalog_receipt_path",
        reject_expired,
    )

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner._verify_resume_claim(
            run_dir,
            repair_authority_path=tmp_path / "repair.json",
            qwen_catalog_receipt_path=tmp_path / "catalog.json",
        )

    assert error.value.reason_code == "qwen_catalog_receipt_expired"
    assert observed == {"run_dir": run_dir, "require_fresh": True}


def test_resume_audit_accepts_complete_prefix_and_rejects_reserved_gap(
    tmp_path: Path,
    unit_authority_chain: dict[str, str],
) -> None:
    assert unit_authority_chain["run_claim_sha256"] == UNIT_RUN_CLAIM_SHA256
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    nodes = json.loads(
        (run_dir / "prepared/run_plan.json").read_text()
    )["nodes"]
    _formal_checkpoint_for_node(run_dir, nodes[0])

    position = runner.audit_resume_position(run_dir)
    assert position["completed_prefix_count"] == 1
    assert position["next_node_id"] == nodes[1]["node_id"]

    ledger = (
        run_dir
        / f"runtime/{nodes[1]['node_id']}/transport/attempt_reservations.jsonl"
    )
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text('{"reserved":true}\n', encoding="utf-8")

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner.audit_resume_position(run_dir)
    assert error.value.reason_code == "attempt_without_checkpoint"


def test_partial_or_extra_checkpoint_is_occupied_not_resumable(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    nodes = json.loads(
        (run_dir / "prepared/run_plan.json").read_text()
    )["nodes"]
    partial = (
        run_dir
        / f"runtime/{nodes[0]['node_id']}/checkpoint/unknown.json"
    )
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text("{}\n", encoding="utf-8")

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner.audit_resume_position(run_dir)
    assert error.value.reason_code == "incomplete_checkpoint"


def test_formal_checkpoint_rebuild_detects_runtime_artifact_drift(
    tmp_path: Path,
    unit_authority_chain: dict[str, str],
) -> None:
    assert unit_authority_chain["run_claim_sha256"] == UNIT_RUN_CLAIM_SHA256
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    node = json.loads(
        (run_dir / "prepared/run_plan.json").read_text()
    )["nodes"][0]
    _formal_checkpoint_for_node(run_dir, node)
    request_path = (
        run_dir / f"runtime/{node['node_id']}/request_artifact.json"
    )
    request_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner.validate_formal_checkpoint(run_dir, node)
    assert error.value.reason_code == "checkpoint_request_binding_invalid"


def test_resume_state_rebuilds_429_and_forces_full_spacing(
    tmp_path: Path,
    unit_authority_chain: dict[str, str],
) -> None:
    assert unit_authority_chain["run_claim_sha256"] == UNIT_RUN_CLAIM_SHA256
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    nodes = json.loads(
        (run_dir / "prepared/run_plan.json").read_text()
    )["nodes"]
    _formal_checkpoint_for_node(run_dir, nodes[0])
    state = runner._retry_state_from_run(
        run_dir,
        nodes,
        [nodes[0]["node_id"]],
        resume_now_monotonic=123.0,
    )

    assert state.total_429 == 0
    assert state.last_chapter == 3
    assert state.last_logical_completed_monotonic == 123.0


def test_qwen_unknown_429_is_charged_to_hard_cap(tmp_path: Path) -> None:
    run_dir = tmp_path / "r07"
    node = {"node_id": "NODE-002-JUDGE"}
    reservation = runner._write_qwen_budget_reservation(
        run_dir=run_dir,
        node=node,
        budget_preflight={
            "conservative_total_token_projection": 100,
            "conservative_cost_projection_micro_cny": 300,
        },
        accumulated_tokens=0,
        accumulated_micro_cny=0,
        max_attempts=3,
    )
    settlement = runner._write_qwen_budget_settlement(
        run_dir=run_dir,
        node=node,
        reservation=reservation,
        attempts=[
            {
                "http_status": 429,
                "usage": runner.z83_retry_transport.UNKNOWN_USAGE,
            },
            {
                "http_status": 200,
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 6,
                    "total_tokens": 10,
                },
            },
        ],
        usage={
            "prompt_tokens": 4,
            "completion_tokens": 6,
            "total_tokens": 10,
        },
    )

    assert settlement["unknown_429_count"] == 1
    assert settlement["hard_cap_accounted_tokens"] == 110
    assert settlement["unknown_usage_not_recorded_as_zero"] is True


@pytest.mark.parametrize(
    ("field", "mutated"),
    [
        ("per_attempt_conservative_token_upper_bound", 1),
        ("per_attempt_conservative_cost_upper_bound_micro_cny", 1),
        ("reserved_hard_cap_tokens", 3),
        ("reserved_hard_cap_micro_cny", 3),
        ("round_token_cap", 1),
        ("round_cost_cap_micro_cny", 1),
    ],
)
def test_qwen_reservation_rejects_self_consistent_smaller_critical_number(
    tmp_path: Path,
    field: str,
    mutated: int,
    unit_authority_chain: dict[str, str],
) -> None:
    """不能靠同步改结算票，把发送前的预算预占悄悄调小。"""

    assert unit_authority_chain["run_claim_sha256"] == UNIT_RUN_CLAIM_SHA256
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    nodes = json.loads(
        (run_dir / "prepared/run_plan.json").read_text()
    )["nodes"]
    _formal_checkpoint_for_node(run_dir, nodes[0])
    judge = nodes[1]
    _formal_checkpoint_for_node(run_dir, judge)
    reservation_path, settlement_path = runner._qwen_budget_paths(
        run_dir,
        str(judge["node_id"]),
    )
    reservation = json.loads(reservation_path.read_text())
    settlement = json.loads(settlement_path.read_text())
    reservation[field] = mutated
    if field == "per_attempt_conservative_token_upper_bound":
        reservation["reserved_hard_cap_tokens"] = (
            mutated * reservation["max_attempts"]
        )
    elif field == "per_attempt_conservative_cost_upper_bound_micro_cny":
        reservation["reserved_hard_cap_micro_cny"] = (
            mutated * reservation["max_attempts"]
        )
    settlement["reservation_sha256"] = runner.canonical_sha(reservation)
    reservation_path.write_text(
        json.dumps(reservation, ensure_ascii=False),
        encoding="utf-8",
    )
    settlement_path.write_text(
        json.dumps(settlement, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner._validate_qwen_budget_receipts(run_dir, judge)
    assert error.value.reason_code == "qwen_budget_receipt_invalid"


def test_qwen_real_429_debt_survives_resume_and_next_reservation(
    tmp_path: Path,
) -> None:
    """真实429不能在续跑时归零；下一节点预占必须吃到这笔债。"""

    run_dir = tmp_path / "r07"
    first_judge = {"node_id": "NODE-002-JUDGE"}
    request_sha = "1" * 64
    raw_sha = "2" * 64
    wire_sha = "3" * 64
    artifact_sha = "4" * 64
    outcomes = iter(
        [
            runner.z83_retry_transport.AttemptOutcome(
                http_status=429,
                request_sha256=request_sha,
                usage=None,
                wire_body_sha256=wire_sha,
                request_artifact_sha256=artifact_sha,
                error_code="rate_limit",
            ),
            runner.z83_retry_transport.AttemptOutcome(
                http_status=200,
                request_sha256=request_sha,
                raw_response_sha256=raw_sha,
                usage={
                    "prompt_tokens": 4,
                    "completion_tokens": 6,
                    "total_tokens": 10,
                },
                wire_body_sha256=wire_sha,
                request_artifact_sha256=artifact_sha,
            ),
        ]
    )
    state = runner.z83_retry_transport.RetryRunState()
    transport_result = runner.z83_retry_transport.run_logical_request(
        logical_request_id=str(first_judge["node_id"]),
        chapter=3,
        send_once=lambda _attempt: next(outcomes),
        attempt_ledger_path=(
            run_dir / "runtime/NODE-002-JUDGE/transport/call_attempts.jsonl"
        ),
        contract_version=runner.CONTRACT_VERSION,
        state=state,
        sleeper=lambda _seconds: None,
        monotonic=lambda: 0.0,
        jitter=lambda: 0.0,
    )
    first_reservation = runner._write_qwen_budget_reservation(
        run_dir=run_dir,
        node=first_judge,
        budget_preflight={
            "conservative_total_token_projection": 100,
            "conservative_cost_projection_micro_cny": 300,
        },
        accumulated_tokens=0,
        accumulated_micro_cny=0,
        max_attempts=3,
    )
    first_settlement = runner._write_qwen_budget_settlement(
        run_dir=run_dir,
        node=first_judge,
        reservation=first_reservation,
        attempts=transport_result.attempt_rows,
        usage={
            "prompt_tokens": 4,
            "completion_tokens": 6,
            "total_tokens": 10,
        },
    )
    next_judge = {"node_id": "NODE-004-JUDGE"}
    next_reservation = runner._write_qwen_budget_reservation(
        run_dir=run_dir,
        node=next_judge,
        budget_preflight={
            "conservative_total_token_projection": 50,
            "conservative_cost_projection_micro_cny": 150,
        },
        accumulated_tokens=first_settlement["hard_cap_accounted_tokens"],
        accumulated_micro_cny=(
            first_settlement["hard_cap_accounted_micro_cny"]
        ),
        max_attempts=3,
    )

    resumed_state = runner.z83_retry_transport.RetryRunState.from_attempt_rows(
        transport_result.attempt_rows
    )
    assert state.total_429 == 1
    assert resumed_state.total_429 == 1
    assert first_settlement["unknown_429_count"] == 1
    assert first_settlement["hard_cap_accounted_tokens"] == 110
    assert (
        next_reservation["accumulated_hard_cap_tokens_before"]
        == first_settlement["hard_cap_accounted_tokens"]
    )
    assert (
        next_reservation["accumulated_hard_cap_micro_cny_before"]
        == first_settlement["hard_cap_accounted_micro_cny"]
    )


def test_resume_adapter_dispatches_only_after_claim_and_ticket_recheck(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unit_authority_chain: dict[str, str],
) -> None:
    assert unit_authority_chain["run_claim_sha256"] == UNIT_RUN_CLAIM_SHA256
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    nodes = json.loads(
        (run_dir / "prepared/run_plan.json").read_text()
    )["nodes"]
    _formal_checkpoint_for_node(run_dir, nodes[0])
    claim = run_dir / "runtime/run_claim.json"
    claim.parent.mkdir(parents=True, exist_ok=True)
    claim.write_text("{}\n", encoding="utf-8")
    repair_ticket = tmp_path / "repair.json"
    catalog_ticket = tmp_path / "catalog.json"
    repair_ticket.write_text("{}\n", encoding="utf-8")
    catalog_ticket.write_text("{}\n", encoding="utf-8")

    authority = runner.LiveAuthority(repair_envelope={}, qwen_catalog={})
    monkeypatch.setattr(
        runner,
        "_verify_resume_claim",
        lambda *_args, **_kwargs: authority,
    )
    monkeypatch.setattr(
        runner,
        "_load_live_keys",
        lambda: {"sensenova": "x", "tencent_tokenhub": "y", "qianwen_platform": "z"},
    )
    monkeypatch.setattr(
        runner,
        "_verify_frozen_provider_configs",
        lambda *_args, **_kwargs: {},
    )
    observed: dict[str, object] = {}

    def execute(*_args: object, **kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        return {"status": "resumed"}

    monkeypatch.setattr(runner, "_execute_live_nodes", execute)
    result = runner.resume_or_audit(
        run_dir,
        repair_authority_path=repair_ticket,
        qwen_catalog_receipt_path=catalog_ticket,
    )

    assert result == {"status": "resumed"}
    assert observed["authority"] is authority


def test_finalize_rejects_forged_68_five_piece_sets_without_run_claim(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    nodes = json.loads(
        (run_dir / "prepared/run_plan.json").read_text()
    )["nodes"]

    for node in nodes:
        checkpoint = (
            run_dir
            / f"runtime/{node['node_id']}/checkpoint"
        )
        checkpoint.mkdir(parents=True)
        for filename in (
            "01_request.json",
            "02_response.json",
            "03_usage.json",
            "04_attempts.json",
            "05_seal.json",
        ):
            (checkpoint / filename).write_text(
                json.dumps(
                    {
                        "node_id": node["node_id"],
                        "forged": True,
                    }
                ),
                encoding="utf-8",
            )

    with pytest.raises(runner.Z98Step2HardStop) as error:
        runner.finalize(run_dir)
    assert error.value.reason_code == "run_claim_missing"
    assert not (run_dir / "final").exists()


def test_finalize_rebuilds_all_68_after_authority_chain_is_verified(
    tmp_path: Path,
    unit_authority_chain: dict[str, str],
) -> None:
    """正式收口成功路径也要保持 score=null、winner=null，不冒充质量胜负。"""

    run_dir = tmp_path / "r07"
    runner.prepare(run_dir)
    nodes = json.loads(
        (run_dir / "prepared/run_plan.json").read_text()
    )["nodes"]
    for node in nodes:
        _formal_checkpoint_for_node(run_dir, node)

    result = runner.finalize(run_dir)
    score = runner.read_json(run_dir / "final/score_inputs.json")
    comparison = runner.read_json(
        run_dir / "final/comparison_inputs.json"
    )
    receipt = runner.read_json(run_dir / "final/finalize_receipt.json")

    assert result["status"] == "COMPLETED_68_AWAITING_UNIFIED_QUALITY_REVIEW"
    assert receipt["checkpoint_count"] == 68
    assert receipt["run_claim_sha256"] == UNIT_RUN_CLAIM_SHA256
    assert score["strict_legacy_scale"]["score"] is None
    assert score["ucr_five_layer"]["score"] is None
    assert comparison["three_way"]["winner"] is None
    assert comparison["single_vs_batch"]["winner"] is None

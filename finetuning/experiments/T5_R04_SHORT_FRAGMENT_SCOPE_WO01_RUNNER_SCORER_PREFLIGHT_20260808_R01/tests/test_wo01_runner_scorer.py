from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest


EXP = Path(__file__).resolve().parents[1]
TOOLS = EXP / "tools"
sys.path.insert(0, str(TOOLS))

import build_preflight_evidence as builder  # noqa: E402
import finalize_preflight as finalizer  # noqa: E402
import run_wo01_scope_probe as runner  # noqa: E402
import score_wo01_scope_probe as scorer  # noqa: E402


def plan_raw_rows(*, perfect: bool = False, extra_fact: bool = False) -> list[dict]:
    canonical = scorer.canonical_map()
    rows = []
    for sequence_index, item in enumerate(runner.load_execution_plan(), start=1):
        if perfect:
            output = {"facts": scorer.gold_rows(canonical[item["case_id"]])}
        elif extra_fact:
            output = {
                "facts": [
                    {
                        "fact": "同题跨臂共享的待裁决事实",
                        "status": "已发生",
                        "speaker": None,
                        "evidence_ids": [],
                    }
                ]
            }
        else:
            output = {"facts": []}
        rows.append(
            {
                "sequence_index": sequence_index,
                "arm": item["arm"],
                "row_index": item["row_index"],
                "case_id": item["case_id"],
                "request_sha256": item["request_sha256"],
                "gold_binding_sha256": item["gold_binding_sha256"],
                "raw_output": json.dumps(output, ensure_ascii=False, separators=(",", ":")),
                "finish_reason": "stop",
                "stop_token_is_eos_eot": True,
            }
        )
    return rows


def fixture_identity(raw_sha: str = "a" * 64) -> dict:
    contract = {"TEST_ONLY_CONTRACT_SHA": "b" * 64}
    return {
        "fixture_role": "TEST_ONLY_NOT_FORMAL_RUN",
        "ticket": contract.copy(),
        "run_id": "WO01-TEST-SCORING",
        "raw_sha256": raw_sha,
        "run_receipt_sha256": "c" * 64,
        "authorization_ticket_sha256": "d" * 64,
        "runner_sha256": "e" * 64,
        "r01_manifest_sha256": runner.EXPECTED["r01_manifest"],
        "request_plan_sha256": runner.execution_plan_identity_sha256(),
        "execution_contract": contract,
        "vendor_identity": {"fixture_role": "TEST_ONLY"},
        "rows": 72,
    }


def full_test_ticket(run_id: str, output: Path, process: dict) -> dict:
    contract = process["execution_contract"]
    quote = "CZ TEST_ONLY fixture; not an authorization"
    return {
        "schema_version": "t5-r04-wo01-run-authorization-v1",
        "status": "CZ_EXPLICIT_MODEL_RUN_AUTHORIZATION",
        "model_run_authorized": True,
        "training_authorized": False,
        "api_authorized": False,
        "authorized_by": "CZ",
        "authorized_at": "2026-08-08T00:00:00+08:00",
        "decision_id": "TEST_ONLY",
        "source_thread_id": "019fe07c-a382-7d91-a463-5e8f6fe7d246",
        "approval_quote": quote,
        "approval_quote_sha256": runner.text_sha256(quote),
        "control_window_dispatch_sha256": "1" * 64,
        "control_window_dispatched_at": "2026-08-08T00:00:00+08:00",
        "run_id": run_id,
        "authorized_output_dir": str(output),
        "authorized_request_count": 72,
        "arm_order": list(runner.ARMS),
        "request_plan_sha256": runner.execution_plan_identity_sha256(),
        "r01_manifest_sha256": runner.EXPECTED["r01_manifest"],
        "checkpoint_sha256": runner.EXPECTED["checkpoint"],
        "schema_sha256": runner.EXPECTED["schema"],
        "chat_template_sha256": runner.EXPECTED["chat_template"],
        "model_receipt_sha256": runner.EXPECTED["model_receipt"],
        "model_revision": runner.MODEL_REVISION,
        "runner_sha256": process["runner_sha256"],
        **contract,
        "vendor_manifest_sha256": process["vendor_identity"]["manifest_sha256"],
        "vendor_tree_digest": process["vendor_identity"]["tree_digest"],
        "mlx_lm_version": process["vendor_identity"]["mlx_lm_version"],
        "decode": {"sampler": "greedy", "temperature": 0.0, "max_output_tokens": 1024, "retry": 0},
    }


def write_complete_test_run(root: Path) -> tuple[Path, dict, dict]:
    run_id = "WO01-TEST-PROVENANCE"
    run_dir = root / run_id
    claims = root / ".claims"
    process = {
        "runner_sha256": "2" * 64,
        "execution_contract": {
            "preflight_output_manifest_sha256": "3" * 64,
            "scorer_sha256": "4" * 64,
            "scoring_contract_sha256": "5" * 64,
            "bootstrap_contract_sha256": "6" * 64,
            "semantic_adjudication_schema_sha256": "7" * 64,
            "run_authorization_schema_sha256": "8" * 64,
            "output_structural_schema_sha256": runner.EXPECTED["schema"],
        },
        "vendor_identity": {
            "manifest_sha256": "9" * 64,
            "tree_digest": "a" * 64,
            "member_count": 162,
            "mlx_lm_version": "0.30.7",
            "required_runtime_import_sources": ["mlx_lm/__init__.py"],
        },
    }
    ticket = full_test_ticket(run_id, run_dir, process)
    ticket_bytes = (json.dumps(ticket, ensure_ascii=False, sort_keys=True) + "\n").encode()
    ticket_sha = hashlib.sha256(ticket_bytes).hexdigest()
    claim, start, auth, chain = runner._claim_run_once_core(
        ticket_bytes,
        ticket_sha,
        ticket,
        run_dir,
        process,
        claims_root=claims,
        start_writer=runner.write_json_exclusive,
    )
    rows = plan_raw_rows()
    raw = run_dir / "RAW_OUTPUTS_72.jsonl"
    scorer.write_jsonl(raw, rows)
    model_identity = {"fixture_role": "TEST_ONLY_MODEL_IDENTITY"}
    receipt = {
        "status": "PASS_WO01_INFERENCE_COMPLETE_PENDING_SCORING",
        "run_id": run_id,
        "completed_at": "TEST_ONLY",
        "cases": 72,
        "arm_order": list(runner.ARMS),
        "request_plan_sha256": runner.execution_plan_identity_sha256(),
        "r01_manifest_sha256": runner.EXPECTED["r01_manifest"],
        "raw_sha256": scorer.sha256(raw),
        "authorization_ticket_sha256": ticket_sha,
        "authorization_ticket_copy_sha256": scorer.sha256(auth),
        "runner_sha256": process["runner_sha256"],
        "claim_sha256": scorer.sha256(claim),
        "run_start_receipt_sha256": scorer.sha256(start),
        "run_start_chain_receipt_sha256": scorer.sha256(chain),
        "model_identity": model_identity,
        "vendor_identity": process["vendor_identity"],
        "process_identity_at_start": process,
        "process_identity_at_completion": process,
        "resource_controls": {
            "minimum_free_memory_percent": runner.MIN_FREE_MEMORY_PERCENT,
            "mlx_wired_limit_bytes": runner.MLX_WIRED_LIMIT_BYTES,
            "mlx_memory_limit_bytes": runner.MLX_MEMORY_LIMIT_BYTES,
            "mlx_cache_limit_bytes": runner.MLX_CACHE_LIMIT_BYTES,
            "clear_cache_after_each_case": True,
        },
        "memory_before": {},
        "memory_after": {},
        "peak_mlx_bytes": 0,
        "elapsed_seconds": 0,
        "retry_count": 0,
        "model_run_authorized": True,
        "training_authorized": False,
        "api_authorized": False,
        "training": False,
        "api_called": False,
    }
    scorer.write_json(run_dir / "RUN_RECEIPT.json", receipt)
    return run_dir, process, model_identity


def verify_test_run(run_dir: Path, process: dict, model_identity: dict):
    return scorer.verify_formal_run_provenance_core(
        run_dir,
        run_root=run_dir.parent,
        claims_root=run_dir.parent / ".claims",
        ticket_validator=lambda path, _output: runner.read_json(path),
        process_identity_provider=lambda: process,
        model_identity_provider=lambda: model_identity,
    )


def test_runner_uses_full_two_message_list_and_correct_stream_signature():
    source = (TOOLS / "run_wo01_scope_probe.py").read_text(encoding="utf-8")
    assert "messages[:-1]" not in source
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "stream_generate"]
    assert len(calls) == 1 and len(calls[0].args) == 2
    assert {item.arg for item in calls[0].keywords} == {"prompt", "max_tokens", "sampler"}
    evidence = runner.build_test_only_serialization_evidence()
    assert len(evidence) == 72
    assert all(row["roles_passed_to_serializer"] == ["system", "user"] for row in evidence)


def test_plan_is_72_and_vendor_and_model_static_identity_close():
    assert len(runner.load_execution_plan()) == 72
    vendor = runner.verify_vendor_sources()
    assert vendor["member_count"] == 162
    receipt = runner.read_json(runner.MODEL / "MODEL_RECEIPT.json")
    assert len(receipt["files"]) == 13 and receipt["revision"] == runner.MODEL_REVISION


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema_version":"x","schema_version":"y"}',
        b'{"model_run_authorized":true,"model_run_authorized":false}',
        b'{"x":{"a":1,"a":2}}',
    ],
)
def test_strict_control_json_rejects_duplicate_keys(payload: bytes):
    with pytest.raises(RuntimeError, match="DUPLICATE_JSON_KEY"):
        runner.strict_json_loads(payload)


@pytest.mark.parametrize(
    "ticket",
    [
        {"schema_version": "t5-r04-wo01-run-authorization-v1", "extra": 1},
        {"schema_version": "t5-r04-wo01-run-authorization-v1", "model_run_authorized": 1},
        {"schema_version": [], "model_run_authorized": True},
    ],
)
def test_authorization_schema_rejects_extra_wrong_type_and_numeric_bool(ticket: dict):
    with pytest.raises(RuntimeError, match="RUN_AUTHORIZATION_SCHEMA_INVALID"):
        runner.validate_authorization_ticket_bytes(json.dumps(ticket).encode(), Path("/tmp/x"))


def test_model_output_duplicate_key_is_format_failure_but_recoverable():
    raw = '{"facts":[{"fact":"甲","fact":"乙","status":"已发生","speaker":null,"evidence_ids":[]}]}'
    result = scorer.analyze_raw(raw, scorer.read_json(scorer.SCHEMA))
    assert result["json_valid"] is False
    assert result["schema_valid"] is False
    assert result["recovered_fact_objects"]


def test_runtime_path_guards_reject_output_dotdot_and_symlink(tmp_path: Path):
    root = tmp_path / "runs"
    root.mkdir()
    run_id = "WO01-X"
    ticket = {"run_id": run_id, "authorized_output_dir": str(root / run_id)}
    runner.assert_authorized_output_binding(ticket, root / run_id, run_root=root)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / run_id).symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="OUTSIDE_RUN_ROOT"):
        runner.assert_authorized_output_binding(ticket, root / run_id, run_root=root)


def test_claims_symlink_is_rejected(tmp_path: Path):
    root = tmp_path / "runs"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / ".claims").symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="SYMLINK"):
        runner.prepare_runtime_roots(run_root=root, claims_root=root / ".claims")


def test_ticket_bytes_are_frozen_and_external_file_can_disappear(tmp_path: Path):
    root = tmp_path / "runs"
    run_id = "WO01-FROZEN"
    output = root / run_id
    process = {
        "runner_sha256": "1" * 64,
        "execution_contract": {
            "preflight_output_manifest_sha256": "2" * 64,
            "scorer_sha256": "3" * 64,
            "scoring_contract_sha256": "4" * 64,
            "bootstrap_contract_sha256": "5" * 64,
            "semantic_adjudication_schema_sha256": "6" * 64,
            "run_authorization_schema_sha256": "7" * 64,
            "output_structural_schema_sha256": runner.EXPECTED["schema"],
        },
        "vendor_identity": {
            "manifest_sha256": "8" * 64,
            "tree_digest": "9" * 64,
            "mlx_lm_version": "0.30.7",
        },
    }
    ticket = full_test_ticket(run_id, output, process)
    payload = (json.dumps(ticket, ensure_ascii=False, sort_keys=True) + "\n").encode()
    external = tmp_path / "ticket.json"
    external.write_bytes(payload)
    frozen = external.read_bytes()
    frozen_sha = hashlib.sha256(frozen).hexdigest()
    external.unlink()
    runner._claim_run_once_core(frozen, frozen_sha, ticket, output, process, claims_root=root / ".claims", start_writer=runner.write_json_exclusive)
    assert (output / "RUN_AUTHORIZATION_TICKET.json").read_bytes() == payload


def test_runner_identity_drift_is_hard_stop(monkeypatch):
    initial = {"runner_sha256": "a" * 64}
    monkeypatch.setattr(runner, "freeze_process_identity", lambda: {"runner_sha256": "b" * 64})
    with pytest.raises(RuntimeError, match="RUNTIME_CODE_IDENTITY_DRIFT"):
        runner.verify_process_identity_unchanged(initial)


def test_complete_formal_provenance_chain_passes_and_fake_bundle_fails(tmp_path: Path):
    run_dir, process, model_identity = write_complete_test_run(tmp_path / "runs")
    identity, rows = verify_test_run(run_dir, process, model_identity)
    assert identity["rows"] == 72 and len(rows) == 72
    (run_dir / "RUN_AUTHORIZATION_TICKET.json").unlink()
    with pytest.raises(RuntimeError):
        verify_test_run(run_dir, process, model_identity)


@pytest.mark.parametrize("field", ["request_sha256", "gold_binding_sha256", "row_index"])
def test_raw_row_identity_drift_rejected(field: str):
    rows = plan_raw_rows()
    rows[0][field] = "0" * 64 if field != "row_index" else 999
    with pytest.raises(RuntimeError, match="RAW_ROW_IDENTITY_DRIFT"):
        scorer.verify_raw_rows_against_plan(rows)


@pytest.mark.parametrize(
    ("artifact", "expected"),
    [("RAW_OUTPUTS_72.jsonl", "SYMLINK"), ("RUN_RECEIPT.json", "SYMLINK")],
)
def test_formal_provenance_rejects_symlink_inputs(tmp_path: Path, artifact: str, expected: str):
    run_dir, process, model_identity = write_complete_test_run(tmp_path / artifact / "runs")
    target = run_dir / artifact
    outside = tmp_path / f"outside-{artifact}"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(RuntimeError, match=expected):
        verify_test_run(run_dir, process, model_identity)


def test_formal_receipt_identity_fields_cannot_drift(tmp_path: Path):
    for field, value in [
        ("retry_count", 1),
        ("training_authorized", True),
        ("api_authorized", True),
        ("resource_controls", {}),
        ("model_identity", {}),
    ]:
        run_dir, process, model_identity = write_complete_test_run(tmp_path / field / "runs")
        receipt_path = run_dir / "RUN_RECEIPT.json"
        receipt = scorer.read_json(receipt_path)
        receipt[field] = value
        scorer.write_json(receipt_path, receipt)
        with pytest.raises(RuntimeError, match="RUN_RECEIPT_IDENTITY_MISMATCH"):
            verify_test_run(run_dir, process, model_identity)


def test_scorer_fixture_branches_and_cross_arm_shared_adjudication():
    observed = {row["fixture_id"]: row["observed"] for row in builder.score_fixtures()}
    assert observed["TEST_ONLY_PERFECT"]["end_to_end_usable"]["f1"] == 1.0
    assert observed["TEST_ONLY_MALFORMED_RECOVERABLE"]["schema_valid"] is False
    assert observed["TEST_ONLY_ILLEGAL_EVIDENCE"]["end_to_end_usable"]["tp"] == 0
    assert observed["TEST_ONLY_REPETITION"]["repetition_detected"] is True
    fixture = runner.read_json(EXP / "test_fixtures/CROSS_ARM_SHARED_ADJUDICATION.json")
    decisions = scorer.adjudication_index([fixture["decision"]], fixture["decision"]["source_raw_sha256"])
    case = scorer.canonical_map()[fixture["case_id"]]
    prediction = [{"fact": fixture["prediction_fact"]}]
    assert [scorer.semantic_pairs(fixture["case_id"], scorer.gold_rows(case), prediction, decisions) for _ in fixture["arms"]] == [([(0, 0)], [])] * 3


def test_public_blind_package_has_no_arm_mapping_and_private_sidecar_does(tmp_path: Path):
    run_dir = tmp_path / "WO01-TEST-SCORING"
    run_dir.mkdir()
    receipt = scorer._write_pre_adjudication_core(run_dir, plan_raw_rows(extra_fact=True), fixture_identity())
    blind_dir = run_dir / "blind_review_package"
    public = b"".join(path.read_bytes() for path in sorted(blind_dir.iterdir()) if path.is_file())
    assert b'"arm"' not in public
    assert all(name.encode() not in public for name in runner.ARMS)
    pre_metrics = scorer.read_json(run_dir / "scoring_pre_adjudication/PRE_ADJUDICATION_METRICS.json")
    assert "case_metrics" not in pre_metrics and "semantic_candidate_occurrence_sidecar" not in pre_metrics
    private = (run_dir / "scoring_private_occurrence/SEMANTIC_CANDIDATE_OCCURRENCE_SIDECAR.jsonl").read_text()
    assert '"arm"' in private
    assert receipt["semantic_candidate_count"] == 24


def test_adjudication_symlink_and_output_reuse_are_rejected(tmp_path: Path, monkeypatch):
    root = tmp_path / "runs"
    run_dir, process, model_identity = write_complete_test_run(root)
    monkeypatch.setattr(scorer, "verify_formal_run_provenance", lambda _run: verify_test_run(run_dir, process, model_identity))
    monkeypatch.setattr(runner, "RUN_ROOT", root)
    scorer.score_pre_adjudication(run_dir)
    with pytest.raises(RuntimeError, match="PRE_ADJUDICATION_OUTPUT_ALREADY_EXISTS"):
        scorer.score_pre_adjudication(run_dir)
    adj_dir = run_dir / "semantic_adjudications"
    adj_dir.mkdir()
    outside = tmp_path / "outside-adjudications.jsonl"
    outside.write_bytes(b"")
    adjudications = adj_dir / "SEMANTIC_ADJUDICATIONS.jsonl"
    adjudications.symlink_to(outside)
    with pytest.raises(RuntimeError, match="SYMLINK"):
        scorer.score_final(run_dir, adjudications)


def test_bootstrap_is_frozen_case_paired_and_deterministic():
    left = [{"case_id": f"C{i:02d}", "arm": "TARGET_ONLY", "semantic_recoverable": {"tp": 1, "fp": 1, "fn": 1}} for i in range(24)]
    right = [{**row, "arm": "SMALL_HALO", "semantic_recoverable": {"tp": 2, "fp": 0, "fn": 0}} for row in left]
    first = scorer.paired_bootstrap_f1_delta(left, right)
    assert first == scorer.paired_bootstrap_f1_delta(left, right)
    assert (first["samples"], first["seed"], first["interval"]) == (10_000, 2026080801, "two_sided_percentile_type7_95_percent")


def test_two_preflight_builds_are_byte_identical(tmp_path: Path):
    first, second = tmp_path / "run_1", tmp_path / "run_2"
    builder.build(first)
    builder.build(second)
    assert builder.compare(first, second)["mismatches"] == 0


def test_finalizer_exact_manifest_rejects_extra_file(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(finalizer, "EXP", tmp_path)
    (tmp_path / "a.json").write_text("{}\n")
    rows = finalizer.member_rows(stage="review")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"member_count": len(rows), "members": rows}) + "\n")
    (tmp_path / "extra.json").write_text("{}\n")
    with pytest.raises(RuntimeError, match="EXACT_FILE_SET"):
        finalizer.validate_manifest_exact(manifest, stage="review")


def test_finalizer_review_schema_rejects_fake_reviewer_and_empty_commands():
    schema = runner.read_json(EXP / "INDEPENDENT_REVIEW_RECEIPT_SCHEMA.json")
    validator = __import__("jsonschema").Draft202012Validator(schema)
    bad = {"schema_version": "t5-r04-wo01-independent-review-receipt-v2", "status": "PASS", "reviewer": "fake", "reviewer_role": "INDEPENDENT_READONLY_REVIEWER", "review_target_manifest_sha256": "a" * 64, "reviewed_member_count": 1, "member_mismatch_count": 0, "checks": {}, "command_evidence": []}
    assert list(validator.iter_errors(bad))


def test_write_exclusive_rejects_repeat(tmp_path: Path):
    target = tmp_path / "x.json"
    finalizer.write_json_exclusive(target, {"x": 1})
    with pytest.raises(FileExistsError):
        finalizer.write_json_exclusive(target, {"x": 2})

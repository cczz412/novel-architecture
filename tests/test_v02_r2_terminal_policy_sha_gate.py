from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from experiments.V02_R2_terminal_once_20260727 import (
    policy_sha_gate as gate,
)


NEW_TICKET_ID = "M3-07-R2-TERMINAL-30-THIRD-REEL-TEST"


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _make_fixture(root: Path) -> dict[str, Path]:
    runtime_root = root / "handoff/runtime_sha_inputs"
    audit_root = root / "handoff/audit_isolated"
    runtime_root.mkdir(parents=True)
    audit_root.mkdir(parents=True)
    runtime_files = {
        "source_bindings": runtime_root / "01_source_bindings.json",
        "question_set": runtime_root / "02_question_set.json",
        "gold_binding": runtime_root / "03_gold_binding.json",
    }
    for artifact_id, path in runtime_files.items():
        path.write_text(f"{artifact_id}-opaque-bytes\n", encoding="utf-8")
    audit_file = audit_root / "00_build_spec_audit_only.py"
    audit_file.write_text("AUDIT_SENTINEL_DO_NOT_READ\n", encoding="utf-8")

    program_path = root / "program/policy_sha_gate.py"
    program_path.parent.mkdir(parents=True)
    program_path.write_bytes(Path(gate.__file__).read_bytes())

    policy_path = root / "handoff/SHA_VERIFICATION_POLICY.json"
    policy = {
        "schema_version": gate.POLICY_SCHEMA,
        "policy_id": "M3-07-PREAUTH-SHA-POLICY-TEST",
        "ticket_id": NEW_TICKET_ID,
        "phase": "PRE_AUTHORIZATION",
        "operation": "HASH_ONLY",
        "runtime_root": _relative(runtime_root, root),
        "runtime_root_role": "RUNTIME_SHA_INPUTS_ONLY",
        "exact_artifact_count": 3,
        "files": [
            {
                "artifact_id": artifact_id,
                "role": gate.EXPECTED_ARTIFACT_ROLES[artifact_id],
                "relative_path": path.name,
                "sha256": _sha256(path),
                "required": True,
            }
            for artifact_id, path in runtime_files.items()
        ],
        "excluded_audit_roots": [_relative(audit_root, root)],
        "public_rehearsal_required": True,
    }
    _write_json(policy_path, policy)

    ticket_path = root / "handoff/SEAL_TICKET.json"
    ticket = {
        "ticket_id": NEW_TICKET_ID,
        "status": "SEALED_AWAITING_MAINLINE1_PUBLIC_REHEARSAL_AND_NEW_AUTHORITY",
        "preauthorization_sha_policy": {
            "policy_id": policy["policy_id"],
            "path": _relative(policy_path, root),
            "sha256": _sha256(policy_path),
        },
    }
    _write_json(ticket_path, ticket)

    rehearsal_path = root / "rehearsal/PUBLIC_LAYOUT_REHEARSAL_RECEIPT.json"
    rehearsal = {
        "status": "PASS",
        "ticket": {
            "ticket_id": NEW_TICKET_ID,
            "ticket_sha256": _sha256(ticket_path),
        },
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
    _write_json(rehearsal_path, rehearsal)

    request_path = root / "request/SHA_GATE_REQUEST.json"
    request = {
        "schema_version": gate.REQUEST_SCHEMA,
        "expected_ticket_id": NEW_TICKET_ID,
        "seal_ticket_path": _relative(ticket_path, root),
        "seal_ticket_sha256": _sha256(ticket_path),
        "public_rehearsal_receipt_path": _relative(rehearsal_path, root),
        "public_rehearsal_receipt_sha256": _sha256(rehearsal_path),
        "gate_program_path": _relative(program_path, root),
        "gate_program_sha256": _sha256(program_path),
        "retired_ticket_ids": sorted(gate.RETIRED_TICKET_IDS),
        "retired_cycle_ids": sorted(gate.RETIRED_CYCLE_IDS),
        "retired_run_ids": sorted(gate.RETIRED_RUN_IDS),
    }
    _write_json(request_path, request)
    output_path = root / "receipts/PREAUTH_SHA_GATE_RECEIPT.json"
    output_path.parent.mkdir(parents=True)
    return {
        "root": root,
        "runtime_root": runtime_root,
        "audit_root": audit_root,
        "audit_file": audit_file,
        "policy": policy_path,
        "ticket": ticket_path,
        "rehearsal": rehearsal_path,
        "request": request_path,
        "program": program_path,
        "output": output_path,
        **runtime_files,
    }


def _rebind_public_controls(paths: dict[str, Path]) -> None:
    root = paths["root"]
    policy = _load_json(paths["policy"])
    ticket = _load_json(paths["ticket"])
    ticket["preauthorization_sha_policy"]["policy_id"] = policy["policy_id"]
    ticket["preauthorization_sha_policy"]["sha256"] = _sha256(paths["policy"])
    _write_json(paths["ticket"], ticket)

    rehearsal = _load_json(paths["rehearsal"])
    rehearsal["ticket"]["ticket_id"] = ticket["ticket_id"]
    rehearsal["ticket"]["ticket_sha256"] = _sha256(paths["ticket"])
    _write_json(paths["rehearsal"], rehearsal)

    request = _load_json(paths["request"])
    request["expected_ticket_id"] = ticket["ticket_id"]
    request["seal_ticket_path"] = _relative(paths["ticket"], root)
    request["seal_ticket_sha256"] = _sha256(paths["ticket"])
    request["public_rehearsal_receipt_path"] = _relative(
        paths["rehearsal"],
        root,
    )
    request["public_rehearsal_receipt_sha256"] = _sha256(paths["rehearsal"])
    request["gate_program_path"] = _relative(paths["program"], root)
    request["gate_program_sha256"] = _sha256(paths["program"])
    _write_json(paths["request"], request)


def _run(paths: dict[str, Path]) -> dict[str, Any]:
    return gate.run_gate(
        request_path=paths["request"],
        output_path=paths["output"],
        project_root=paths["root"],
        expected_program_path=paths["program"],
    )


def test_policy_gate_hashes_only_exact_runtime_allowlist(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    audit_before = paths["audit_file"].read_bytes()

    result = _run(paths)

    assert result["status"] == "PASS"
    assert result["checked_artifact_count"] == 3
    assert result["mismatch_count"] == 0
    assert {row["artifact_id"] for row in result["checked_artifacts"]} == {
        "source_bindings",
        "question_set",
        "gold_binding",
    }
    assert result["directory_scan_scope"] == "RUNTIME_ROOT_ONLY"
    assert result["private_content_parse_count"] == 0
    assert result["private_content_echo_count"] == 0
    assert result["audit_root_access_count"] == 0
    assert result["manual_private_path_argument_count"] == 0
    assert paths["audit_file"].read_bytes() == audit_before
    assert paths["output"].is_file()


@pytest.mark.parametrize("recorded", ["/tmp/escape.json", "../escape.json", "x\\y"])
def test_policy_gate_rejects_absolute_escape_and_backslash_paths(
    tmp_path: Path,
    recorded: str,
) -> None:
    paths = _make_fixture(tmp_path)
    policy = _load_json(paths["policy"])
    policy["files"][0]["relative_path"] = recorded
    _write_json(paths["policy"], policy)
    _rebind_public_controls(paths)

    with pytest.raises(gate.ShaGateError, match="POLICY_FILE_PATH_INVALID"):
        _run(paths)


def test_policy_gate_rejects_runtime_file_symlink(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    paths["question_set"].unlink()
    paths["question_set"].symlink_to(paths["audit_file"])

    with pytest.raises(
        gate.ShaGateError,
        match="RUNTIME_ROOT_EXACT_SET_MISMATCH",
    ):
        _run(paths)


def test_policy_gate_rejects_runtime_parent_symlink(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    real_root = paths["runtime_root"].with_name("runtime_real")
    paths["runtime_root"].rename(real_root)
    paths["runtime_root"].symlink_to(real_root, target_is_directory=True)

    with pytest.raises(
        gate.ShaGateError,
        match="RUNTIME_ROOT_SYMLINK_OR_MISSING",
    ):
        _run(paths)


def test_policy_gate_rejects_hardlinked_runtime_file(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    original = paths["question_set"]
    twin = paths["audit_root"] / "question_set_hardlink"
    os.link(original, twin)

    with pytest.raises(gate.ShaGateError, match="RUNTIME_FILE_TYPE_INVALID"):
        _run(paths)


def test_policy_gate_rejects_policy_manifest_tamper(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    policy = _load_json(paths["policy"])
    policy["phase"] = "POST_AUTHORIZATION"
    _write_json(paths["policy"], policy)

    with pytest.raises(gate.ShaGateError, match="SHA_POLICY_SHA_MISMATCH"):
        _run(paths)


def test_policy_gate_rejects_bad_sha_format(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    policy = _load_json(paths["policy"])
    policy["files"][0]["sha256"] = "ABC"
    _write_json(paths["policy"], policy)
    _rebind_public_controls(paths)

    with pytest.raises(
        gate.ShaGateError,
        match="POLICY_FILE_COMMITMENT_INVALID",
    ):
        _run(paths)


def test_policy_gate_rejects_runtime_sha_drift(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    paths["source_bindings"].write_text("changed\n", encoding="utf-8")

    with pytest.raises(
        gate.ShaGateError,
        match="RUNTIME_FILE_SHA_MISMATCH:source_bindings",
    ):
        _run(paths)


@pytest.mark.parametrize("mode", ["missing", "duplicate"])
def test_policy_gate_rejects_non_exact_manifest(
    tmp_path: Path,
    mode: str,
) -> None:
    paths = _make_fixture(tmp_path)
    policy = _load_json(paths["policy"])
    if mode == "missing":
        policy["files"].pop()
    else:
        policy["files"][2] = copy.deepcopy(policy["files"][1])
    _write_json(paths["policy"], policy)
    _rebind_public_controls(paths)

    with pytest.raises(gate.ShaGateError):
        _run(paths)


def test_policy_gate_rejects_extra_runtime_entry(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    (paths["runtime_root"] / "unexpected.json").write_text(
        "unexpected\n",
        encoding="utf-8",
    )

    with pytest.raises(
        gate.ShaGateError,
        match="RUNTIME_ROOT_EXACT_SET_MISMATCH",
    ):
        _run(paths)


def test_policy_gate_rejects_non_regular_runtime_entry(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    paths["gold_binding"].unlink()
    os.mkfifo(paths["gold_binding"])

    with pytest.raises(
        gate.ShaGateError,
        match="RUNTIME_ROOT_EXACT_SET_MISMATCH",
    ):
        _run(paths)


def test_policy_gate_rejects_wrong_phase_even_when_rebound(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    policy = _load_json(paths["policy"])
    policy["phase"] = "POST_AUTHORIZATION"
    _write_json(paths["policy"], policy)
    _rebind_public_controls(paths)

    with pytest.raises(gate.ShaGateError, match="SHA_POLICY_BINDING_INVALID"):
        _run(paths)


def test_policy_gate_rejects_audit_root_overlap(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    policy = _load_json(paths["policy"])
    policy["excluded_audit_roots"] = [policy["runtime_root"] + "/audit"]
    _write_json(paths["policy"], policy)
    _rebind_public_controls(paths)

    with pytest.raises(
        gate.ShaGateError,
        match="POLICY_AUDIT_ROOT_NOT_ISOLATED",
    ):
        _run(paths)


def test_policy_gate_rejects_failed_public_rehearsal(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    rehearsal = _load_json(paths["rehearsal"])
    rehearsal["status"] = "FAIL"
    _write_json(paths["rehearsal"], rehearsal)
    _rebind_public_controls(paths)

    with pytest.raises(
        gate.ShaGateError,
        match="REHEARSAL_TICKET_BINDING_INVALID",
    ):
        _run(paths)


def test_policy_gate_rejects_retired_m3_06_ticket(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    retired = next(iter(gate.RETIRED_TICKET_IDS))
    policy = _load_json(paths["policy"])
    policy["ticket_id"] = retired
    _write_json(paths["policy"], policy)
    ticket = _load_json(paths["ticket"])
    ticket["ticket_id"] = retired
    _write_json(paths["ticket"], ticket)
    _rebind_public_controls(paths)

    with pytest.raises(gate.ShaGateError, match="REQUEST_TICKET_ID_INVALID"):
        _run(paths)


def test_policy_gate_requires_prior_cycle_and_run_retirement(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    request = _load_json(paths["request"])
    request["retired_cycle_ids"] = []
    request["retired_run_ids"] = []
    _write_json(paths["request"], request)

    with pytest.raises(gate.ShaGateError, match="RETIRED_CYCLE_IDS_INVALID"):
        _run(paths)


def test_policy_gate_rejects_program_drift(tmp_path: Path) -> None:
    paths = _make_fixture(tmp_path)
    paths["program"].write_text("# drift\n", encoding="utf-8")

    with pytest.raises(gate.ShaGateError, match="GATE_PROGRAM_BINDING_INVALID"):
        _run(paths)


def test_policy_gate_cli_has_no_individual_file_or_root_option() -> None:
    parser = gate.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--request",
                "request.json",
                "--output",
                "receipt.json",
                "--file",
                "forbidden.json",
            ]
        )
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--request",
                "request.json",
                "--output",
                "receipt.json",
                "--root",
                "runtime",
            ]
        )

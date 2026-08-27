"""Generate a deterministic offline replay report; performs zero network calls."""

from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

from fixtures import (
    ARK_IDENTITY,
    ARK_REQUEST,
    ARK_RUN_IDENTITY,
    ARK_TOOL,
    C1,
    C2,
    OPENROUTER_BAD_CONTENT,
    OPENROUTER_BAD_OUTER,
    OPENROUTER_BAD_SCHEMA,
    OPENROUTER_IDENTITY,
    OPENROUTER_LEGACY,
    OPENROUTER_REQUEST,
    OPENROUTER_RUN_IDENTITY,
    OPENROUTER_TOOL,
    REVISION,
)
from zero_api_shell import (
    MechanicalGateError,
    NetworkAuditGuard,
    RawAttemptStore,
    canonical_json_bytes,
    freeze_run_identity,
    load_verified_run_identity,
    pack_tool_bundle,
    preview_legacy_extraction_as_c3,
    preview_c3,
    sha256_bytes,
    validate_c1,
    validate_saved_provider_turn,
    verify_raw_attempt,
)

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "OFFLINE_REPLAY_REPORT.json"
RUNTIME_SOURCES = (
    ROOT / "zero_api_shell.py",
    ROOT / "fixtures.py",
    ROOT / "self_check.py",
)
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "ctypes",
        "http",
        "httpx",
        "importlib",
        "multiprocessing",
        "openai",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "volcenginesdkarkruntime",
    }
)
FORBIDDEN_DYNAMIC_CALLS = frozenset({"__import__", "compile", "eval", "exec"})
FORBIDDEN_OS_CALL_PREFIXES = (
    "exec",
    "fork",
    "popen",
    "posix_spawn",
    "spawn",
    "system",
)


def expect_error(code: str, callback) -> dict:
    try:
        callback()
    except MechanicalGateError as exc:
        assert exc.code == code, (exc.code, code)
        return exc.receipt()
    raise AssertionError(f"expected {code}")


def audit_zero_api_sources() -> dict:
    findings: list[str] = []
    checked = []
    for path in RUNTIME_SOURCES:
        raw = path.read_bytes()
        tree = ast.parse(raw, filename=str(path))
        checked.append({"file": path.name, "sha256": sha256_bytes(raw)})
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".", 1)[0] for alias in node.names]
                for root in roots:
                    if root in FORBIDDEN_IMPORT_ROOTS:
                        findings.append(f"{path.name}:{node.lineno}:import:{root}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    findings.append(f"{path.name}:{node.lineno}:import:{root}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_DYNAMIC_CALLS:
                    findings.append(f"{path.name}:{node.lineno}:call:{node.func.id}")
                elif (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr.startswith(FORBIDDEN_OS_CALL_PREFIXES)
                ):
                    findings.append(f"{path.name}:{node.lineno}:call:os.{node.func.attr}")
    if findings:
        raise AssertionError(f"ZERO_API_SOURCE_AUDIT_FAILED:{findings}")
    return {
        "mechanism": "python_ast_forbidden_import_and_dynamic_call_audit",
        "checked_files": checked,
        "findings": findings,
    }


def _run_guarded() -> dict:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    store = RawAttemptStore(root)

    def save_case(
        run_id: str,
        response: bytes,
        *,
        http_status: int = 200,
        base_identity: dict = OPENROUTER_RUN_IDENTITY,
        request: bytes | None = None,
    ) -> tuple[object, Path, dict]:
        identity = {**base_identity, "run_id": run_id}
        if request is None:
            request = (
                OPENROUTER_REQUEST
                if identity["provider_protocol"] == "openrouter_chat_completions"
                else ARK_REQUEST
            )
        receipt = store.append(
            run_id=run_id,
            attempt_no=1,
            http_status=http_status,
            request=request,
            response=response,
            run_identity=identity,
        )
        return receipt, root / run_id / "attempt-0001", identity

    receipt, attempt_path, _ = save_case("synthetic-run", OPENROUTER_TOOL)
    verified = verify_raw_attempt(attempt_path)
    stored_openrouter_identity = load_verified_run_identity(attempt_path)
    immutable_error = expect_error(
        "IMMUTABLE_ALREADY_EXISTS",
        lambda: store.append(
            run_id="synthetic-run",
            attempt_no=1,
            http_status=200,
            request=OPENROUTER_REQUEST,
            response=b"changed",
            run_identity=OPENROUTER_RUN_IDENTITY,
        ),
    )
    drift_identity = {
        **OPENROUTER_RUN_IDENTITY,
        "reasoning": {"mode": "high"},
        "config": {**OPENROUTER_RUN_IDENTITY["config"], "temperature": 1},
    }
    run_identity_drift_error = expect_error(
        "RUN_IDENTITY_DRIFT",
        lambda: store.append(
            run_id="synthetic-run",
            attempt_no=2,
            http_status=200,
            request=OPENROUTER_REQUEST,
            response=b"second-response",
            run_identity=drift_identity,
        ),
    )

    ark_receipt, ark_attempt_path, _ = save_case(
        "synthetic-ark-run",
        ARK_TOOL,
        base_identity=ARK_RUN_IDENTITY,
    )
    stored_ark_identity = load_verified_run_identity(ark_attempt_path)
    openrouter_saved = validate_saved_provider_turn(
        attempt_path, current_revision_ref=REVISION
    )
    ark_saved = validate_saved_provider_turn(
        ark_attempt_path, current_revision_ref=REVISION
    )
    openrouter_gate = openrouter_saved["gate"]
    ark_gate = ark_saved["gate"]

    _legacy_receipt, legacy_path, _legacy_identity = save_case(
        "synthetic-legacy-run", OPENROUTER_LEGACY
    )
    legacy = preview_legacy_extraction_as_c3(
        legacy_path,
        c2=C2,
        current_revision_ref=REVISION,
    )
    c3 = preview_c3(
        c2=C2,
        current_revision_ref=REVISION,
        facts=openrouter_gate["action"]["arguments"]["facts"],
    )

    duplicate_response = json.loads(OPENROUTER_TOOL)
    duplicate_response["choices"][0]["message"]["tool_calls"][0]["function"][
        "arguments"
    ] = (
        '{"expected_revision_ref":{"chapter_id":"c01","revision_no":2,'
        '"revision_text_sha256":"'
        + REVISION["revision_text_sha256"]
        + '"},"facts":[],"facts":[]}'
    )
    truncated_response = json.loads(OPENROUTER_TOOL)
    truncated_response["choices"][0]["finish_reason"] = "length"
    legacy_truncated = json.loads(OPENROUTER_LEGACY)
    legacy_truncated["choices"][0]["finish_reason"] = "length"
    legacy_wrong_identity = json.loads(OPENROUTER_LEGACY)
    legacy_wrong_identity["model"] = "different-model"
    request_model_drift = json.loads(OPENROUTER_REQUEST)
    request_model_drift["model"] = "different-model"
    request_fallback = json.loads(OPENROUTER_REQUEST)
    request_fallback["provider"]["allow_fallbacks"] = True
    request_tool_drift = json.loads(OPENROUTER_REQUEST)
    request_tool_drift["tools"] = []
    bad_tool_calls = json.loads(OPENROUTER_LEGACY)
    bad_tool_calls["choices"][0]["message"]["tool_calls"] = {}
    bad_tool_type = json.loads(OPENROUTER_TOOL)
    bad_tool_type["choices"][0]["message"]["tool_calls"][0]["type"] = "custom"
    finish_tool_mismatch = json.loads(OPENROUTER_TOOL)
    finish_tool_mismatch["choices"][0]["finish_reason"] = "stop"
    bad_openrouter_usage = json.loads(OPENROUTER_TOOL)
    bad_openrouter_usage["usage"] = []
    bad_ark_output = json.loads(ARK_TOOL)
    bad_ark_output["output"] = [{"type": "unknown"}]
    bad_ark_content = json.loads(ARK_TOOL)
    bad_ark_content["output"] = [{"type": "message", "content": {}}]
    bad_ark_call_id = json.loads(ARK_TOOL)
    bad_ark_call_id["output"][0]["call_id"] = None
    bad_ark_usage = json.loads(ARK_TOOL)
    bad_ark_usage["usage"] = 0

    _unused, bad_outer_path, _unused_identity = save_case(
        "negative-bad-outer", OPENROUTER_BAD_OUTER
    )
    _unused, bad_content_path, _unused_identity = save_case(
        "negative-bad-content", OPENROUTER_BAD_CONTENT
    )
    _unused, bad_schema_path, _unused_identity = save_case(
        "negative-bad-schema", OPENROUTER_BAD_SCHEMA
    )
    _unused, truncated_path, _unused_identity = save_case(
        "negative-truncated", canonical_json_bytes(truncated_response)
    )
    _unused, legacy_truncated_path, _unused_identity = save_case(
        "negative-legacy-truncated", canonical_json_bytes(legacy_truncated)
    )
    _unused, legacy_wrong_identity_path, _unused_identity = save_case(
        "negative-legacy-identity", canonical_json_bytes(legacy_wrong_identity)
    )
    _unused, duplicate_path, _unused_identity = save_case(
        "negative-duplicate-arguments", canonical_json_bytes(duplicate_response)
    )
    _unused, http_failure_path, _unused_identity = save_case(
        "negative-http", OPENROUTER_LEGACY, http_status=503
    )
    _unused, request_model_drift_path, _unused_identity = save_case(
        "negative-request-model",
        OPENROUTER_TOOL,
        request=canonical_json_bytes(request_model_drift),
    )
    _unused, request_fallback_path, _unused_identity = save_case(
        "negative-request-fallback",
        OPENROUTER_TOOL,
        request=canonical_json_bytes(request_fallback),
    )
    _unused, request_tool_drift_path, _unused_identity = save_case(
        "negative-request-tools",
        OPENROUTER_TOOL,
        request=canonical_json_bytes(request_tool_drift),
    )
    envelope_paths = {}
    for run_id, response, base_identity in (
        ("negative-bad-tool-calls", bad_tool_calls, OPENROUTER_RUN_IDENTITY),
        ("negative-bad-tool-type", bad_tool_type, OPENROUTER_RUN_IDENTITY),
        ("negative-finish-tool-mismatch", finish_tool_mismatch, OPENROUTER_RUN_IDENTITY),
        ("negative-openrouter-usage", bad_openrouter_usage, OPENROUTER_RUN_IDENTITY),
        ("negative-ark-output", bad_ark_output, ARK_RUN_IDENTITY),
        ("negative-ark-content", bad_ark_content, ARK_RUN_IDENTITY),
        ("negative-ark-call-id", bad_ark_call_id, ARK_RUN_IDENTITY),
        ("negative-ark-usage", bad_ark_usage, ARK_RUN_IDENTITY),
    ):
        _unused, path, _unused_identity = save_case(
            run_id, canonical_json_bytes(response), base_identity=base_identity
        )
        envelope_paths[run_id] = path

    stale_revision = dict(REVISION, revision_no=REVISION["revision_no"] + 1)
    negative = {
        "bad_outer_json": expect_error(
            "INVALID_JSON",
            lambda: preview_legacy_extraction_as_c3(
                bad_outer_path, c2=C2, current_revision_ref=REVISION
            ),
        ),
        "bad_content_json": expect_error(
            "INVALID_JSON",
            lambda: preview_legacy_extraction_as_c3(
                bad_content_path, c2=C2, current_revision_ref=REVISION
            ),
        ),
        "schema_failure": expect_error(
            "BAD_FACT_FIELDS",
            lambda: preview_legacy_extraction_as_c3(
                bad_schema_path, c2=C2, current_revision_ref=REVISION
            ),
        ),
        "truncation": expect_error(
            "TRUNCATED",
            lambda: validate_saved_provider_turn(
                truncated_path, current_revision_ref=REVISION
            ),
        ),
        "legacy_truncation": expect_error(
            "TRUNCATED",
            lambda: preview_legacy_extraction_as_c3(
                legacy_truncated_path, c2=C2, current_revision_ref=REVISION
            ),
        ),
        "legacy_identity_drift": expect_error(
            "EXACT_MODEL_MISMATCH",
            lambda: preview_legacy_extraction_as_c3(
                legacy_wrong_identity_path, c2=C2, current_revision_ref=REVISION
            ),
        ),
        "stale_revision": expect_error(
            "STALE_OR_MISMATCH",
            lambda: validate_saved_provider_turn(
                attempt_path, current_revision_ref=stale_revision
            ),
        ),
        "duplicate_arguments": expect_error(
            "DUPLICATE_JSON_KEY",
            lambda: validate_saved_provider_turn(
                duplicate_path, current_revision_ref=REVISION
            ),
        ),
        "bad_evidence": expect_error(
            "QUOTE_NOT_IN_RESPONSIBILITY_TEXT",
            lambda: preview_c3(
                c2=C2,
                current_revision_ref=REVISION,
                facts=[{"text": "合成事实。", "quote": "原文没有这句"}],
            ),
        ),
        "http_failure": expect_error(
            "HTTP_NOT_SUCCESS",
            lambda: preview_legacy_extraction_as_c3(
                http_failure_path, c2=C2, current_revision_ref=REVISION
            ),
        ),
        "request_model_drift": expect_error(
            "REQUEST_MODEL_MISMATCH",
            lambda: validate_saved_provider_turn(
                request_model_drift_path, current_revision_ref=REVISION
            ),
        ),
        "request_fallback_enabled": expect_error(
            "REQUEST_FALLBACK_NOT_ALLOWED",
            lambda: validate_saved_provider_turn(
                request_fallback_path, current_revision_ref=REVISION
            ),
        ),
        "request_tool_bundle_drift": expect_error(
            "REQUEST_TOOL_BUNDLE_MISMATCH",
            lambda: validate_saved_provider_turn(
                request_tool_drift_path, current_revision_ref=REVISION
            ),
        ),
        "openrouter_bad_tool_calls": expect_error(
            "BAD_TOOL_CALLS",
            lambda: validate_saved_provider_turn(
                envelope_paths["negative-bad-tool-calls"],
                current_revision_ref=REVISION,
            ),
        ),
        "openrouter_bad_tool_type": expect_error(
            "BAD_TOOL_CALL_TYPE",
            lambda: validate_saved_provider_turn(
                envelope_paths["negative-bad-tool-type"],
                current_revision_ref=REVISION,
            ),
        ),
        "openrouter_finish_tool_mismatch": expect_error(
            "FINISH_TOOL_CALL_MISMATCH",
            lambda: validate_saved_provider_turn(
                envelope_paths["negative-finish-tool-mismatch"],
                current_revision_ref=REVISION,
            ),
        ),
        "openrouter_bad_usage": expect_error(
            "BAD_USAGE",
            lambda: validate_saved_provider_turn(
                envelope_paths["negative-openrouter-usage"],
                current_revision_ref=REVISION,
            ),
        ),
        "ark_unknown_output_type": expect_error(
            "UNKNOWN_ARK_OUTPUT_TYPE",
            lambda: validate_saved_provider_turn(
                envelope_paths["negative-ark-output"], current_revision_ref=REVISION
            ),
        ),
        "ark_bad_content": expect_error(
            "BAD_ARK_CONTENT",
            lambda: validate_saved_provider_turn(
                envelope_paths["negative-ark-content"], current_revision_ref=REVISION
            ),
        ),
        "ark_bad_call_id": expect_error(
            "BAD_ARK_CALL_ID",
            lambda: validate_saved_provider_turn(
                envelope_paths["negative-ark-call-id"], current_revision_ref=REVISION
            ),
        ),
        "ark_bad_usage": expect_error(
            "BAD_USAGE",
            lambda: validate_saved_provider_turn(
                envelope_paths["negative-ark-usage"], current_revision_ref=REVISION
            ),
        ),
    }

    _tamper_receipt, tamper_path, _tamper_identity = save_case(
        "negative-identity-tamper", OPENROUTER_TOOL
    )
    (tamper_path.parent / "run_identity.json").write_bytes(b'{"tampered":true}')
    identity_tamper_error = expect_error(
        "RAW_HASH_OR_SIZE_MISMATCH",
        lambda: verify_raw_attempt(tamper_path),
    )

    c1 = validate_c1(C1, current_revision_ref=REVISION)
    bundles = {
        protocol: pack_tool_bundle(
            protocol=protocol,
            exact_model_identity=(
                OPENROUTER_IDENTITY
                if protocol == "openrouter_chat_completions"
                else ARK_IDENTITY
            ),
        )
        for protocol in ("openrouter_chat_completions", "ark_responses")
    }
    report = {
        "report_contract": "M3_A_OFFLINE_REPLAY_REPORT",
        "version": "r01",
        "mechanical_pass": True,
        "semantic_pass": None,
        "input_contracts": {
            "c1": {"contract": c1["contract"], "version": c1["version"]},
            "c2": {"contract": C2["contract"], "version": C2["version"]},
            "revision_match": c1["chapter_revision_ref"] == C2["chapter_revision_ref"],
        },
        "run_identity_freeze": {
            "openrouter": freeze_run_identity(stored_openrouter_identity),
            "ark": freeze_run_identity(stored_ark_identity),
        },
        "attempt": {
            "openrouter_receipt": receipt.__dict__,
            "ark_receipt": ark_receipt.__dict__,
            "verified_equal": receipt == verified,
            "immutability_negative": immutable_error,
            "run_identity_drift_negative": run_identity_drift_error,
            "identity_tamper_negative": identity_tamper_error,
            "request_binding_receipts": {
                "openrouter": openrouter_saved["request_binding_receipt"],
                "ark": ark_saved["request_binding_receipt"],
                "legacy": legacy["request_binding_receipt"],
            },
        },
        "routes": {
            "legacy": legacy["route"],
            "openrouter_action": openrouter_gate["action"]["name"],
            "ark_action": ark_gate["action"]["name"],
        },
        "c3_preview": c3,
        "bundle_hashes": {
            key: {
                "internal": value["canonical_internal_schema_sha256"],
                "provider_payload": value["provider_payload_sha256"],
            }
            for key, value in bundles.items()
        },
        "negative_gates": negative,
        "fixture_sha256": {
            "openrouter_tool": sha256_bytes(OPENROUTER_TOOL),
            "ark_tool": sha256_bytes(ARK_TOOL),
            "openrouter_legacy": sha256_bytes(OPENROUTER_LEGACY),
        },
    }
    temporary.cleanup()
    return report


def run() -> dict:
    guard = NetworkAuditGuard()
    with guard:
        source_audit = audit_zero_api_sources()
        report = _run_guarded()
    if guard.blocked_events:
        raise AssertionError(guard.blocked_events)
    report["network_calls"] = len(guard.blocked_events)
    report["model_api_calls"] = (
        0 if not guard.blocked_events and not source_audit["findings"] else None
    )
    report["network_guard"] = {
        "mechanism": "python_audit_hook_socket_and_child_process_fail_closed",
        "active_during_replay": True,
        "blocked_events": guard.blocked_events,
        "observed_network_calls": len(guard.blocked_events),
    }
    report["zero_api_source_audit"] = source_audit
    report["zero_api_derivation"] = (
        "runtime socket/process events = 0 and runtime sources contain no network, "
        "model-client, child-process, or dynamic-import path"
    )
    return report


if __name__ == "__main__":
    report = run()
    bundles = {
        protocol: pack_tool_bundle(
            protocol=protocol,
            exact_model_identity=(
                OPENROUTER_IDENTITY
                if protocol == "openrouter_chat_completions"
                else ARK_IDENTITY
            ),
        )
        for protocol in ("openrouter_chat_completions", "ark_responses")
    }
    (ROOT / "TOOL_SCHEMA_BUNDLES.json").write_text(
        json.dumps(bundles, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))

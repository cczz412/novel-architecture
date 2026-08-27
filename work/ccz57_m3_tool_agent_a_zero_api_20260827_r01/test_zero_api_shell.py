from __future__ import annotations

import copy
import json
import sys

import pytest

from fixtures import (
    ARK_REQUEST,
    ARK_IDENTITY,
    ARK_RUN_IDENTITY,
    ARK_TOOL,
    C1,
    C2,
    OPENROUTER_IDENTITY,
    OPENROUTER_LEGACY,
    OPENROUTER_REQUEST,
    OPENROUTER_RUN_IDENTITY,
    OPENROUTER_TOOL,
    REVISION,
)
from self_check import run
from zero_api_shell import (
    MechanicalGateError,
    NetworkAccessBlocked,
    NetworkAuditGuard,
    RawAttemptStore,
    canonical_json_bytes,
    normalize_ark,
    normalize_openrouter,
    pack_tool_bundle,
    parse_legacy_extraction,
    preview_c3,
    preview_legacy_extraction_as_c3,
    validate_provider_turn,
    validate_http_status,
    validate_c1,
    validate_saved_provider_turn,
    validate_saved_request_binding,
    validate_tool_result_call_id,
    verify_raw_attempt,
)


def test_positive_replay_and_deterministic_bundles() -> None:
    report = run()
    assert report["network_calls"] == report["model_api_calls"] == 0
    assert report["mechanical_pass"] is True
    assert report["semantic_pass"] is None
    assert report["network_guard"] == {
        "mechanism": "python_audit_hook_socket_and_child_process_fail_closed",
        "active_during_replay": True,
        "blocked_events": [],
        "observed_network_calls": 0,
    }
    assert report["input_contracts"]["revision_match"] is True
    assert validate_c1(C1, current_revision_ref=REVISION)["text"] == C2["text"]
    for protocol, identity in (
        ("openrouter_chat_completions", OPENROUTER_IDENTITY),
        ("ark_responses", ARK_IDENTITY),
    ):
        assert pack_tool_bundle(protocol=protocol, exact_model_identity=identity) == pack_tool_bundle(
            protocol=protocol, exact_model_identity=identity
        )


def test_native_tool_calls_and_legacy_content_are_separate(tmp_path) -> None:
    openrouter = normalize_openrouter(OPENROUTER_TOOL)
    ark = normalize_ark(ARK_TOOL)
    assert openrouter["completion_kind"] == ark["completion_kind"] == "TOOL_CALLS"
    assert openrouter["plain_text"] is None
    store = RawAttemptStore(tmp_path)
    store.append(
        run_id="synthetic-run",
        attempt_no=1,
        http_status=200,
        request=OPENROUTER_REQUEST,
        response=OPENROUTER_LEGACY,
        run_identity=OPENROUTER_RUN_IDENTITY,
    )
    store.append(
        run_id="synthetic-run",
        attempt_no=2,
        http_status=200,
        request=OPENROUTER_REQUEST,
        response=OPENROUTER_TOOL,
        run_identity=OPENROUTER_RUN_IDENTITY,
    )
    legacy = parse_legacy_extraction(tmp_path / "synthetic-run" / "attempt-0001")
    assert legacy["payload"]["facts"][0]["text"] == "林澈关上窗。"
    with pytest.raises(MechanicalGateError, match="NATIVE_TOOL_CALL_NOT_LEGACY_CONTENT"):
        parse_legacy_extraction(
            tmp_path / "synthetic-run" / "attempt-0002"
        )


def test_fail_closed_mechanical_gates() -> None:
    turn = normalize_openrouter(OPENROUTER_TOOL)
    with pytest.raises(MechanicalGateError, match="EXACT_MODEL_MISMATCH"):
        wrong_identity_turn = dict(turn)
        wrong_identity_turn["exact_model_identity"] = {
            "model": "other",
            "provider": "synthetic-provider",
        }
        validate_provider_turn(
            wrong_identity_turn,
            frozen_run_identity=OPENROUTER_RUN_IDENTITY,
            current_revision_ref=REVISION,
        )
    two = dict(turn)
    two["tool_calls"] = turn["tool_calls"] * 2
    with pytest.raises(MechanicalGateError, match="TOO_MANY_CALLS"):
        validate_provider_turn(
            two,
            frozen_run_identity=OPENROUTER_RUN_IDENTITY,
            current_revision_ref=REVISION,
        )
    forged = dict(turn)
    forged["tool_calls"] = []
    forged["plain_text"] = '<tool_call>{"name":"submit_baseline_candidate"}</tool_call>'
    result = validate_provider_turn(
        forged,
        frozen_run_identity=OPENROUTER_RUN_IDENTITY,
        current_revision_ref=REVISION,
    )
    assert result["action"] is None
    with pytest.raises(MechanicalGateError, match="CALL_ID_MISMATCH"):
        validate_tool_result_call_id(original_call_id="a", result_call_id="b")


def test_c3_preview_obeys_current_contract_and_evidence() -> None:
    output = preview_c3(
        c2=C2,
        current_revision_ref=REVISION,
        facts=[{"text": "林澈关上窗。", "quote": "林澈关上窗。"}, {"text": "雨声变小。"}],
    )
    assert output[1] == {
        "contract": "C3_FACT_CANDIDATE",
        "version": "v1",
        "chapter_revision_ref": REVISION,
        "text": "雨声变小。",
        "seg": 1,
    }
    stale = dict(REVISION, revision_no=3)
    with pytest.raises(MechanicalGateError, match="STALE_OR_MISMATCH"):
        preview_c3(c2=C2, current_revision_ref=stale, facts=[])
    with pytest.raises(MechanicalGateError, match="BAD_FACT_FIELDS"):
        preview_c3(
            c2=C2,
            current_revision_ref=REVISION,
            facts=[{"text": "事实。", "speaker": "林澈"}],
        )


def test_duplicate_argument_keys_are_rejected_before_schema() -> None:
    turn = normalize_ark(ARK_TOOL)
    broken = dict(turn)
    broken["tool_calls"] = [dict(turn["tool_calls"][0])]
    broken["tool_calls"][0]["arguments_raw"] = json.dumps(
        {"expected_revision_ref": REVISION}
    )[:-1] + ',"expected_revision_ref":{}}'
    with pytest.raises(MechanicalGateError, match="DUPLICATE_JSON_KEY"):
        validate_provider_turn(
            broken,
            frozen_run_identity=ARK_RUN_IDENTITY,
            current_revision_ref=REVISION,
        )


def test_tool_revision_visibility_completion_and_schema_fail_closed() -> None:
    turn = normalize_ark(ARK_TOOL)
    with pytest.raises(MechanicalGateError, match="STALE_OR_MISMATCH"):
        validate_provider_turn(
            turn,
            frozen_run_identity=ARK_RUN_IDENTITY,
            current_revision_ref=dict(REVISION, revision_no=3),
        )
    with pytest.raises(MechanicalGateError, match="TOOL_NOT_VISIBLE"):
        validate_provider_turn(
            turn,
            frozen_run_identity=ARK_RUN_IDENTITY,
            current_revision_ref=REVISION,
            visible_tools=("declare_no_progress",),
        )
    truncated = dict(turn, finish_reason="incomplete")
    with pytest.raises(MechanicalGateError, match="TRUNCATED"):
        validate_provider_turn(
            truncated,
            frozen_run_identity=ARK_RUN_IDENTITY,
            current_revision_ref=REVISION,
        )
    with pytest.raises(MechanicalGateError, match="HTTP_NOT_SUCCESS"):
        validate_http_status(500)


def test_fixed_negative_replay_set_is_complete() -> None:
    report = run()
    assert {
        "bad_outer_json",
        "bad_content_json",
        "schema_failure",
        "bad_evidence",
        "stale_revision",
        "truncation",
    }.issubset(report["negative_gates"])
    assert report["attempt"]["identity_tamper_negative"]["code"] == (
        "RAW_HASH_OR_SIZE_MISMATCH"
    )


def test_network_guard_mechanically_blocks_network_capable_events() -> None:
    guard = NetworkAuditGuard()
    with guard:
        for event in ("socket.connect", "os.fork", "os.exec"):
            with pytest.raises(NetworkAccessBlocked, match=event):
                sys.audit(event, None, None)
    assert guard.blocked_events == ["socket.connect", "os.fork", "os.exec"]


def test_run_identity_is_frozen_across_attempts_and_binds_response(tmp_path) -> None:
    store = RawAttemptStore(tmp_path)
    store.append(
        run_id="synthetic-run",
        attempt_no=1,
        http_status=200,
        request=OPENROUTER_REQUEST,
        response=OPENROUTER_TOOL,
        run_identity=OPENROUTER_RUN_IDENTITY,
    )
    changed = {
        **OPENROUTER_RUN_IDENTITY,
        "model": "different-model",
        "reasoning": {"mode": "high"},
        "config": {**OPENROUTER_RUN_IDENTITY["config"], "temperature": 1},
    }
    with pytest.raises(MechanicalGateError, match="RUN_IDENTITY_DRIFT"):
        store.append(
            run_id="synthetic-run",
            attempt_no=2,
            http_status=200,
            request=OPENROUTER_REQUEST,
            response=b"response-2",
            run_identity=changed,
        )
    wrong_response = json.loads(OPENROUTER_TOOL)
    wrong_response["model"] = "different-model"
    wrong_identity = {**OPENROUTER_RUN_IDENTITY, "run_id": "wrong-response-run"}
    store.append(
        run_id="wrong-response-run",
        attempt_no=1,
        http_status=200,
        request=OPENROUTER_REQUEST,
        response=canonical_json_bytes(wrong_response),
        run_identity=wrong_identity,
    )
    with pytest.raises(MechanicalGateError, match="EXACT_MODEL_MISMATCH"):
        validate_saved_provider_turn(
            tmp_path / "wrong-response-run" / "attempt-0001",
            current_revision_ref=REVISION,
        )


def test_legacy_route_uses_common_identity_completion_and_http_gates(tmp_path) -> None:
    store = RawAttemptStore(tmp_path)

    def save_case(run_id: str, response: bytes, http_status: int = 200):
        identity = {**OPENROUTER_RUN_IDENTITY, "run_id": run_id}
        store.append(
            run_id=run_id,
            attempt_no=1,
            http_status=http_status,
            request=OPENROUTER_REQUEST,
            response=response,
            run_identity=identity,
        )
        return tmp_path / run_id / "attempt-0001"

    truncated = json.loads(OPENROUTER_LEGACY)
    truncated["choices"][0]["finish_reason"] = "length"
    truncated_path = save_case("truncated", canonical_json_bytes(truncated))
    with pytest.raises(MechanicalGateError, match="TRUNCATED"):
        preview_legacy_extraction_as_c3(
            truncated_path,
            c2=C2,
            current_revision_ref=REVISION,
        )
    wrong = json.loads(OPENROUTER_LEGACY)
    wrong["model"] = "different-model"
    wrong_path = save_case("wrong-model", canonical_json_bytes(wrong))
    with pytest.raises(MechanicalGateError, match="EXACT_MODEL_MISMATCH"):
        preview_legacy_extraction_as_c3(
            wrong_path,
            c2=C2,
            current_revision_ref=REVISION,
        )
    http_path = save_case("bad-http", OPENROUTER_LEGACY, 503)
    with pytest.raises(MechanicalGateError, match="HTTP_NOT_SUCCESS"):
        preview_legacy_extraction_as_c3(
            http_path,
            c2=C2,
            current_revision_ref=REVISION,
        )


def test_raw_attempt_hash_change_fails(tmp_path) -> None:
    store = RawAttemptStore(tmp_path)
    identity = dict(OPENROUTER_RUN_IDENTITY, run_id="run-1")
    store.append(
        run_id="run-1",
        attempt_no=1,
        http_status=200,
        request=OPENROUTER_REQUEST,
        response=b"response",
        run_identity=identity,
    )
    attempt = tmp_path / "run-1" / "attempt-0001"
    (attempt / "response.raw").write_bytes(b"tampered")
    with pytest.raises(MechanicalGateError, match="RAW_HASH_OR_SIZE_MISMATCH"):
        verify_raw_attempt(attempt)


def _mutated_raw(raw: bytes, callback) -> bytes:
    value = json.loads(raw)
    callback(value)
    return canonical_json_bytes(value)


@pytest.mark.parametrize(
    ("mutate", "code"),
    (
        (lambda body: body.__setitem__("model", "other/model"), "REQUEST_MODEL_MISMATCH"),
        (
            lambda body: body["provider"].__setitem__("order", ["other-provider"]),
            "REQUEST_UPSTREAM_MISMATCH",
        ),
        (
            lambda body: body["provider"].__setitem__("allow_fallbacks", True),
            "REQUEST_FALLBACK_NOT_ALLOWED",
        ),
        (
            lambda body: body.__setitem__("reasoning", {"mode": "high"}),
            "REQUEST_REASONING_MISMATCH",
        ),
        (lambda body: body.__setitem__("temperature", 1), "REQUEST_CONFIG_MISMATCH"),
        (lambda body: body.__setitem__("tools", []), "REQUEST_TOOL_BUNDLE_MISMATCH"),
    ),
)
def test_openrouter_request_binding_rejects_identity_drift(mutate, code) -> None:
    with pytest.raises(MechanicalGateError, match=code):
        validate_saved_request_binding(
            _mutated_raw(OPENROUTER_REQUEST, mutate), OPENROUTER_RUN_IDENTITY
        )


@pytest.mark.parametrize(
    ("mutate", "code"),
    (
        (lambda body: body.__setitem__("model", "other-model"), "REQUEST_MODEL_MISMATCH"),
        (
            lambda body: body.__setitem__("endpoint", "ep-other"),
            "REQUEST_UPSTREAM_MISMATCH",
        ),
        (
            lambda body: body.__setitem__("reasoning", {"mode": "high"}),
            "REQUEST_REASONING_MISMATCH",
        ),
        (
            lambda body: body.__setitem__("max_output_tokens", 1024),
            "REQUEST_CONFIG_MISMATCH",
        ),
        (lambda body: body.__setitem__("tools", []), "REQUEST_TOOL_BUNDLE_MISMATCH"),
    ),
)
def test_ark_request_binding_rejects_identity_drift(mutate, code) -> None:
    with pytest.raises(MechanicalGateError, match=code):
        validate_saved_request_binding(
            _mutated_raw(ARK_REQUEST, mutate), ARK_RUN_IDENTITY
        )


def test_request_binding_receipt_is_hash_only_and_blocks_credentials() -> None:
    receipt = validate_saved_request_binding(
        OPENROUTER_REQUEST, OPENROUTER_RUN_IDENTITY
    )
    assert receipt["binding_pass"] is True
    assert receipt["tool_bundle_id"] == "baseline-r01.1"
    assert receipt["provider_protocol"] == "openrouter_chat_completions"
    assert receipt["request_sha256"]
    assert not {"request", "messages", "input", "model", "provider", "endpoint"} & set(
        receipt
    )
    with pytest.raises(MechanicalGateError, match="REQUEST_CONTAINS_CREDENTIAL_MATERIAL"):
        validate_saved_request_binding(
            _mutated_raw(
                OPENROUTER_REQUEST,
                lambda body: body.__setitem__("headers", {"Authorization": "secret"}),
            ),
            OPENROUTER_RUN_IDENTITY,
        )


def test_attempt_store_rejects_credentials_before_writing_request_raw(tmp_path) -> None:
    store = RawAttemptStore(tmp_path)
    request_with_secret = _mutated_raw(
        OPENROUTER_REQUEST,
        lambda body: body.__setitem__("headers", {"Authorization": "secret"}),
    )
    with pytest.raises(MechanicalGateError, match="REQUEST_CONTAINS_CREDENTIAL_MATERIAL"):
        store.append(
            run_id="credential-run",
            attempt_no=1,
            http_status=200,
            request=request_with_secret,
            response=OPENROUTER_TOOL,
            run_identity={**OPENROUTER_RUN_IDENTITY, "run_id": "credential-run"},
        )
    assert not (tmp_path / "credential-run").exists()


def test_native_and_legacy_share_the_saved_request_binding_gate(tmp_path) -> None:
    store = RawAttemptStore(tmp_path)
    drifted_request = _mutated_raw(
        OPENROUTER_REQUEST, lambda body: body.__setitem__("model", "other/model")
    )
    for run_id, response, callback in (
        ("native-drift", OPENROUTER_TOOL, validate_saved_provider_turn),
        ("legacy-drift", OPENROUTER_LEGACY, parse_legacy_extraction),
    ):
        identity = {**OPENROUTER_RUN_IDENTITY, "run_id": run_id}
        store.append(
            run_id=run_id,
            attempt_no=1,
            http_status=200,
            request=drifted_request,
            response=response,
            run_identity=identity,
        )
        with pytest.raises(MechanicalGateError, match="REQUEST_MODEL_MISMATCH"):
            callback(tmp_path / run_id / "attempt-0001")


def test_run_identity_cannot_lie_about_frozen_tool_hashes() -> None:
    changed = copy.deepcopy(OPENROUTER_RUN_IDENTITY)
    changed["config"]["tool_provider_payload_sha256"] = "0" * 64
    with pytest.raises(MechanicalGateError, match="TOOL_BUNDLE_HASH_MISMATCH"):
        validate_saved_request_binding(OPENROUTER_REQUEST, changed)


def test_failure_receipts_keep_narrow_diagnostics_under_stable_parent_codes() -> None:
    request_error = MechanicalGateError(
        "request_binding", "REQUEST_MODEL_MISMATCH"
    ).receipt()
    provider_error = MechanicalGateError(
        "provider_envelope", "BAD_TOOL_CALLS"
    ).receipt()
    unrelated_error = MechanicalGateError("tool_schema", "ARGUMENTS_INVALID").receipt()

    assert request_error == {
        "layer": "request_binding",
        "code": "REQUEST_MODEL_MISMATCH",
        "detail": "",
        "parent_code": "REQUEST_IDENTITY_MISMATCH",
    }
    assert provider_error == {
        "layer": "provider_envelope",
        "code": "BAD_TOOL_CALLS",
        "detail": "",
        "parent_code": "PROVIDER_ENVELOPE_REJECTED",
    }
    assert "parent_code" not in unrelated_error


@pytest.mark.parametrize("bad_value", ("", {}, 0, False))
def test_openrouter_falsy_tool_calls_wrong_types_fail(bad_value) -> None:
    response = json.loads(OPENROUTER_LEGACY)
    response["choices"][0]["message"]["tool_calls"] = bad_value
    with pytest.raises(MechanicalGateError, match="BAD_TOOL_CALLS"):
        normalize_openrouter(canonical_json_bytes(response))


@pytest.mark.parametrize("tool_calls_value", (pytest.param(None, id="null"),))
def test_openrouter_null_tool_calls_is_a_legal_empty_value(tool_calls_value) -> None:
    response = json.loads(OPENROUTER_LEGACY)
    response["choices"][0]["message"]["tool_calls"] = tool_calls_value
    assert normalize_openrouter(canonical_json_bytes(response))["tool_calls"] == []


def test_openrouter_missing_tool_calls_is_a_legal_empty_value() -> None:
    assert normalize_openrouter(OPENROUTER_LEGACY)["tool_calls"] == []


def test_openrouter_tool_type_and_finish_consistency_fail_closed() -> None:
    unknown_type = json.loads(OPENROUTER_TOOL)
    unknown_type["choices"][0]["message"]["tool_calls"][0]["type"] = "custom"
    with pytest.raises(MechanicalGateError, match="BAD_TOOL_CALL_TYPE"):
        normalize_openrouter(canonical_json_bytes(unknown_type))
    tool_with_stop = json.loads(OPENROUTER_TOOL)
    tool_with_stop["choices"][0]["finish_reason"] = "stop"
    with pytest.raises(MechanicalGateError, match="FINISH_TOOL_CALL_MISMATCH"):
        normalize_openrouter(canonical_json_bytes(tool_with_stop))
    empty_with_tool_finish = json.loads(OPENROUTER_LEGACY)
    empty_with_tool_finish["choices"][0]["finish_reason"] = "tool_calls"
    with pytest.raises(MechanicalGateError, match="FINISH_TOOL_CALL_MISMATCH"):
        normalize_openrouter(canonical_json_bytes(empty_with_tool_finish))


@pytest.mark.parametrize("usage", ("", [], 0, False))
def test_provider_bad_usage_types_fail(usage) -> None:
    for raw, normalizer in (
        (OPENROUTER_TOOL, normalize_openrouter),
        (ARK_TOOL, normalize_ark),
    ):
        response = json.loads(raw)
        response["usage"] = usage
        with pytest.raises(MechanicalGateError, match="BAD_USAGE"):
            normalizer(canonical_json_bytes(response))


@pytest.mark.parametrize("usage_value", (pytest.param(None, id="null"),))
def test_provider_null_usage_is_legal_empty(usage_value) -> None:
    for raw, normalizer in (
        (OPENROUTER_TOOL, normalize_openrouter),
        (ARK_TOOL, normalize_ark),
    ):
        response = json.loads(raw)
        response["usage"] = usage_value
        assert normalizer(canonical_json_bytes(response))["usage"] == {}


def test_provider_missing_usage_is_legal_empty() -> None:
    for raw, normalizer in (
        (OPENROUTER_TOOL, normalize_openrouter),
        (ARK_TOOL, normalize_ark),
    ):
        response = json.loads(raw)
        response.pop("usage", None)
        assert normalizer(canonical_json_bytes(response))["usage"] == {}


@pytest.mark.parametrize("bad_content", ("", {}, 0, False))
def test_ark_falsy_content_wrong_types_fail(bad_content) -> None:
    response = json.loads(ARK_TOOL)
    response["output"] = [{"type": "message", "content": bad_content}]
    with pytest.raises(MechanicalGateError, match="BAD_ARK_CONTENT"):
        normalize_ark(canonical_json_bytes(response))


def test_ark_missing_and_null_content_are_legal_empty_values() -> None:
    for message in ({"type": "message"}, {"type": "message", "content": None}):
        response = json.loads(ARK_TOOL)
        response["output"] = [message]
        turn = normalize_ark(canonical_json_bytes(response))
        assert turn["tool_calls"] == [] and turn["plain_text"] is None


@pytest.mark.parametrize("call_id", (None, "", 0, False))
def test_ark_bad_call_id_never_falls_back_to_item_id(call_id) -> None:
    response = json.loads(ARK_TOOL)
    response["output"][0]["call_id"] = call_id
    response["output"][0]["id"] = "must-not-be-used"
    with pytest.raises(MechanicalGateError, match="BAD_ARK_CALL_ID"):
        normalize_ark(canonical_json_bytes(response))


def test_ark_unknown_output_and_bad_parts_fail_closed() -> None:
    cases = (
        ({"type": "unknown"}, "UNKNOWN_ARK_OUTPUT_TYPE"),
        ({"type": "message", "content": ["bad"]}, "BAD_ARK_CONTENT_PART"),
        (
            {"type": "message", "content": [{"type": "unknown", "text": "x"}]},
            "UNKNOWN_ARK_CONTENT_PART_TYPE",
        ),
        (
            {"type": "message", "content": [{"type": "output_text", "text": 1}]},
            "BAD_ARK_TEXT",
        ),
    )
    for output_item, code in cases:
        response = json.loads(ARK_TOOL)
        response["output"] = [output_item]
        with pytest.raises(MechanicalGateError, match=code):
            normalize_ark(canonical_json_bytes(response))

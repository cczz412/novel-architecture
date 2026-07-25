from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_scoreability_preflight as preflight  # noqa: E402


pytestmark = pytest.mark.v02


def test_six_checks_are_exactly_the_approved_six() -> None:
    assert preflight.CHECK_IDS == (
        "BOTH_ARMS_HAVE_DISPATCH_PLANS",
        "OUTPUT_CONTRACTS_ARE_COMPATIBLE",
        "FORMAL_DENOMINATOR_SHA_IS_LOCKED",
        "CROSSWALK_INPUTS_CAN_BE_GENERATED",
        "SCORER_EMPTY_SHELL_COMPLETES_END_TO_END",
        "EVERY_METRIC_NUMERIC_OR_PREDECLARED_BLOCKED",
    )
    assert preflight.CHECK_RULES_ZH == (
        "双臂都有实发计划",
        "双臂输出合同相容",
        "正式分母 SHA 已锁",
        "crosswalk 输入材料能生成",
        "计分器能用空壳样张完整走通",
        "每个指标要么能产数，要么其缺件已在实验前列入阻断项",
    )
    assert [
        row["rule_text_exact"]
        for row in preflight.scoreability_contract()["check_order"]
    ] == list(preflight.CHECK_RULES_ZH)


def _prepared(tmp_path: Path) -> tuple[dict[str, object], Path]:
    preflight.write_or_verify(tmp_path)
    document = json.loads(
        (tmp_path / "scoreable_example_input.json").read_text(
            encoding="utf-8"
        )
    )
    return document, tmp_path


def _refresh_ref(
    document: dict[str, object],
    relative: str,
    root: Path,
) -> None:
    digest = preflight.sha256_file(root / relative)
    for arm in document["arms"]:
        for key in (
            "dispatch_plan_ref",
            "output_contract_ref",
            "output_fixture_ref",
        ):
            if arm[key]["path"] == relative:
                arm[key]["sha256"] = digest
    for key in (
        "formal_denominator_ref",
        "crosswalk_generator_identity_ref",
        "scorer_empty_shell_ref",
        "predeclared_blockers_ref",
    ):
        if document[key]["path"] == relative:
            document[key]["sha256"] = digest


def test_scoreable_example_runs_real_files_but_cannot_authorize_winner(
    tmp_path: Path,
) -> None:
    document, root = _prepared(tmp_path)
    receipt = preflight.evaluate_manifest(document, root)
    assert receipt["status"] == preflight.SCOREABLE
    assert receipt["all_six_mechanical_checks_pass"] is True
    assert receipt["all_metrics_numeric_ready"] is True
    assert receipt["quality_verdict_allowed"] is False
    assert receipt["winner_or_gate_result_allowed"] is False
    assert receipt["separate_quality_authority_required"] is True
    assert [row["check_id"] for row in receipt["checks"]] == list(
        preflight.CHECK_IDS
    )
    assert [row["rule_text_exact"] for row in receipt["checks"]] == list(
        preflight.CHECK_RULES_ZH
    )
    assert all(row["passed"] for row in receipt["checks"])


def test_real_file_sha_tampering_is_rejected(tmp_path: Path) -> None:
    document, root = _prepared(tmp_path)
    path = root / "example_evidence/dispatch_control.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["requests"].append(payload["requests"][0])
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(preflight.ScoreabilityPreflightError, match="SHA"):
        preflight.evaluate_manifest(document, root)


def test_empty_dispatch_plan_fails_mechanical_check_without_crashing(
    tmp_path: Path,
) -> None:
    document, root = _prepared(tmp_path)
    path = root / "example_evidence/dispatch_control.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["requests"] = []
    path.write_bytes(preflight.stable_json_bytes(payload))
    _refresh_ref(document, "example_evidence/dispatch_control.json", root)
    receipt = preflight.evaluate_manifest(document, root)
    assert receipt["checks"][0]["passed"] is False
    assert receipt["status"] == preflight.NOT_SCOREABLE


def test_predeclared_metric_block_is_honest_but_not_scoreable(
    tmp_path: Path,
) -> None:
    document, root = _prepared(tmp_path)
    scorer_path = root / "example_evidence/scorer_empty_shell.json"
    scorer = json.loads(scorer_path.read_text(encoding="utf-8"))
    del scorer["metric_inputs"]["ASR_full"]
    scorer_path.write_bytes(preflight.stable_json_bytes(scorer))
    _refresh_ref(document, "example_evidence/scorer_empty_shell.json", root)

    blocker_path = root / "example_evidence/predeclared_blockers.json"
    blockers = {
        "schema_version": "v02-predeclared-blockers.v1",
        "blockers": [
            {
                "blocker_id": "B-MISSING-ASR",
                "metric_id": "ASR_full",
                "declared_at": "2026-07-24T23:59:00+08:00",
            }
        ],
    }
    blocker_path.write_bytes(preflight.stable_json_bytes(blockers))
    _refresh_ref(document, "example_evidence/predeclared_blockers.json", root)

    receipt = preflight.evaluate_manifest(document, root)
    assert receipt["checks"][5]["passed"] is True
    assert receipt["status"] == preflight.NOT_SCOREABLE
    assert receipt["all_metrics_numeric_ready"] is False
    assert receipt["quality_verdict_allowed"] is False


def test_exploratory_only_can_be_retained_but_cannot_win(
    tmp_path: Path,
) -> None:
    document, root = _prepared(tmp_path)
    document["exploratory_only"] = True
    receipt = preflight.evaluate_manifest(document, root)
    assert receipt["all_six_mechanical_checks_pass"] is True
    assert receipt["status"] == preflight.NOT_SCOREABLE
    assert receipt["exploratory_only"] is True
    assert receipt["winner_or_gate_result_allowed"] is False


def test_missing_or_mismatched_arm_identity_is_hard_rejected(
    tmp_path: Path,
) -> None:
    document, root = _prepared(tmp_path)
    del document["arms"][0]["arm_id"]
    with pytest.raises(preflight.ScoreabilityPreflightError, match="arm_id"):
        preflight.evaluate_manifest(document, root)

    document, root = _prepared(tmp_path / "second")
    contract_path = root / "example_evidence/contract_control.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["arm_id"] = "treatment"
    contract_path.write_bytes(preflight.stable_json_bytes(contract))
    _refresh_ref(document, "example_evidence/contract_control.json", root)
    with pytest.raises(preflight.ScoreabilityPreflightError, match="身份不一致"):
        preflight.evaluate_manifest(document, root)


def test_missing_denominator_case_identity_is_hard_rejected(
    tmp_path: Path,
) -> None:
    document, root = _prepared(tmp_path)
    path = root / "example_evidence/formal_denominator.json"
    denominator = json.loads(path.read_text(encoding="utf-8"))
    del denominator["chapters"][0]["case_id"]
    path.write_bytes(preflight.stable_json_bytes(denominator))
    _refresh_ref(document, "example_evidence/formal_denominator.json", root)
    with pytest.raises(preflight.ScoreabilityPreflightError, match="case_id"):
        preflight.evaluate_manifest(document, root)


def test_self_described_pass_cannot_replace_actual_contract(
    tmp_path: Path,
) -> None:
    document, root = _prepared(tmp_path)
    path = root / "example_evidence/contract_control.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["normalized_score_shape"] = []
    contract["claimed_pass"] = True
    path.write_bytes(preflight.stable_json_bytes(contract))
    _refresh_ref(document, "example_evidence/contract_control.json", root)
    receipt = preflight.evaluate_manifest(document, root)
    checks = {row["check_id"]: row for row in receipt["checks"]}
    assert checks["OUTPUT_CONTRACTS_ARE_COMPATIBLE"]["passed"] is False
    assert receipt["status"] == preflight.NOT_SCOREABLE
    assert receipt["quality_verdict_allowed"] is False


def test_c1_historical_replay_is_not_scoreable() -> None:
    receipt = preflight.replay_c1()
    assert receipt["status"] == preflight.NOT_SCOREABLE
    assert receipt["quality_verdict_allowed"] is False
    assert receipt["winner_or_gate_result_allowed"] is False
    assert receipt["exploratory_observations_may_be_retained"] is True
    checks = {row["check_id"]: row for row in receipt["checks"]}
    assert checks["BOTH_ARMS_HAVE_DISPATCH_PLANS"]["passed"] is True
    assert checks["FORMAL_DENOMINATOR_SHA_IS_LOCKED"]["passed"] is True
    assert checks["OUTPUT_CONTRACTS_ARE_COMPATIBLE"]["passed"] is False
    assert checks["CROSSWALK_INPUTS_CAN_BE_GENERATED"]["passed"] is False
    assert checks["SCORER_EMPTY_SHELL_COMPLETES_END_TO_END"]["passed"] is False
    assert checks[
        "EVERY_METRIC_NUMERIC_OR_PREDECLARED_BLOCKED"
    ]["passed"] is False
    assert receipt["missing_values_zero_filled"] is False


def test_double_build_and_write_are_byte_identical(tmp_path: Path) -> None:
    first = preflight.write_or_verify(tmp_path)
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    second = preflight.write_or_verify(tmp_path)
    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    assert first == second
    assert before == after
    replay = json.loads(
        (tmp_path / "c1_historical_replay_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert replay["status"] == preflight.NOT_SCOREABLE

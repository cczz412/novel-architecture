import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "rights_decision_import.py"
SCHEMA_PATH = ROOT / "RIGHTS_DECISION_IMPORT_SCHEMA.json"
SPEC = importlib.util.spec_from_file_location("rights_decision_import", MODULE_PATH)
rights = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(rights)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path, rows):
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def source_row(index=1):
    group_id = f"R{index:03d}"
    row_ids = [f"TOY-{index:03d}:S0001", f"TOY-{index:03d}:S0002"]
    return {
        "group_id": group_id,
        "source_identity": {
            "source_id": f"SRC-TOY-{index:03d}",
            "source_sha256": f"{index:x}" * 64,
            "book_id": f"BOOK-TOY-{index:03d}",
            "book_title": f"玩具书 {index}",
            "author_id": f"AUTHOR-TOY-{index:03d}",
            "author_name": f"玩具作者 {index}",
        },
        "coverage": {
            "row_ids": row_ids,
            "row_count": len(row_ids),
            "fact_count": index + 2,
        },
        "candidate_decision": "RIGHTS_UNKNOWN",
        "candidate_status": "CANDIDATE_PENDING_CZ_CONFIRMATION",
        "current_rights": {"status": "RIGHTS_UNKNOWN"},
    }


def unresolved_decision(source):
    identity = source["source_identity"]
    coverage = source["coverage"]
    return {
        "group_id": source["group_id"],
        "source_id": identity["source_id"],
        "book_id": identity["book_id"],
        "book_title": identity["book_title"],
        "row_count": coverage["row_count"],
        "fact_count": coverage["fact_count"],
        "cz_decision": "CZ_DECISION_REQUIRED",
        "decision_scope": None,
        "authority_document_path": None,
        "authority_document_sha256": None,
        "rights_holder": None,
        "allowed_use": None,
        "validity": None,
        "cz_note": None,
    }


def reject_decision(source):
    decision = unresolved_decision(source)
    decision.update(
        {
            "cz_decision": "REJECT_FOR_TRAINING",
            "decision_scope": "INTERNAL_MODEL_TRAINING",
            "allowed_use": "FORBIDDEN",
            "cz_note": "玩具裁决：不允许内部模型训练。",
        }
    )
    return decision


def approve_decision(tmp_path, source):
    tmp_path.mkdir(parents=True, exist_ok=True)
    identity = source["source_identity"]
    coverage = source["coverage"]
    document = (tmp_path / "toy_authorization.txt").resolve()
    document.write_text(
        "TOY ONLY\nrights holder: Toy Rights Ltd\nscope: INTERNAL_MODEL_TRAINING\n",
        encoding="utf-8",
    )
    decision = unresolved_decision(source)
    decision.update(
        {
            "cz_decision": "APPROVE_FOR_INTERNAL_TRAINING",
            "decision_scope": "INTERNAL_MODEL_TRAINING",
            "authority_document_path": str(document),
            "authority_document_sha256": sha256(document),
            "rights_holder": "Toy Rights Ltd",
            "allowed_use": "INTERNAL_MODEL_TRAINING",
            "validity": {
                "valid_from": "2026-01-01",
                "valid_until": "2026-12-31",
            },
            "cz_note": "仅用于玩具测试。",
            "author_id": identity["author_id"],
            "author_name": identity["author_name"],
            "source_sha256": identity["source_sha256"],
            "row_scope": {
                "row_ids": coverage["row_ids"],
                "row_count": coverage["row_count"],
                "fact_count": coverage["fact_count"],
            },
        }
    )
    snapshot = {
        "schema_version": "t5-r04-p4-rights-authority-snapshot-v1",
        "cz_decision": "APPROVE_FOR_INTERNAL_TRAINING",
        "group_id": source["group_id"],
        "source_id": identity["source_id"],
        "source_sha256": identity["source_sha256"],
        "book_id": identity["book_id"],
        "book_title": identity["book_title"],
        "author_id": identity["author_id"],
        "author_name": identity["author_name"],
        "row_scope": decision["row_scope"],
        "rights_holder": decision["rights_holder"],
        "decision_scope": decision["decision_scope"],
        "allowed_use": decision["allowed_use"],
        "validity": decision["validity"],
        "authority_document_path": decision["authority_document_path"],
        "authority_document_sha256": decision["authority_document_sha256"],
    }
    snapshot_path = (tmp_path / "toy_authority_snapshot.json").resolve()
    write_json(snapshot_path, snapshot)
    decision["authority_snapshot_path"] = str(snapshot_path)
    decision["authority_snapshot_sha256"] = sha256(snapshot_path)
    return decision, snapshot_path


def invoke(tmp_path, sources, decisions, *, dry_run=True, **overrides):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "toy_source_groups.jsonl"
    decisions_path = tmp_path / "toy_decisions.jsonl"
    output_path = tmp_path / "derived_candidate.jsonl"
    receipt_path = tmp_path / "receipt.json"
    write_jsonl(source_path, sources)
    write_jsonl(decisions_path, decisions)
    mode = overrides.pop(
        "mode", rights.MODE_DRY_RUN if dry_run else rights.MODE_REALTIME
    )
    kwargs = {
        "source_groups_path": source_path,
        "decisions_path": decisions_path,
        "schema_path": SCHEMA_PATH,
        "output_path": output_path,
        "receipt_path": receipt_path,
        "expected_source_groups_sha256": sha256(source_path),
        "expected_decisions_sha256": sha256(decisions_path),
        "expected_schema_sha256": sha256(SCHEMA_PATH),
        "mode": mode,
        "expected_group_count": len(sources),
        "expected_row_count": sum(row["coverage"]["row_count"] for row in sources),
        "expected_fact_count": sum(row["coverage"]["fact_count"] for row in sources),
        "trusted_now_utc_for_test": datetime(
            2026, 8, 8, 4, 0, tzinfo=timezone.utc
        ),
    }
    kwargs.update(overrides)
    receipt = rights._import_decisions_core(**kwargs)
    candidates = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    return receipt, candidates


def assert_hard_stop(tmp_path, sources, decisions, match, **overrides):
    with pytest.raises(rights.RightsImportError, match=match):
        invoke(tmp_path, sources, decisions, **overrides)
    assert not (tmp_path / "derived_candidate.jsonl").exists()
    assert not (tmp_path / "receipt.json").exists()


def test_unfilled_toy_template_dry_run_stays_unknown_and_never_promotes(tmp_path):
    sources = [source_row(1), source_row(2)]
    decisions = [unresolved_decision(source) for source in sources]
    receipt, candidates = invoke(tmp_path, sources, decisions)
    assert receipt["status"] == "PASS_TEST_ONLY_DRY_RUN_NO_CANDIDATE_EFFECT"
    assert receipt["coverage"] == {
        "source_groups": 2,
        "rows": 4,
        "facts": 7,
        "allow_candidate": 0,
        "reject_candidate": 0,
        "rights_unknown": 2,
        "unresolved_template": 2,
        "replay_approve_observation": 0,
        "replay_reject_observation": 0,
        "test_only_allow_observation": 0,
        "test_only_reject_observation": 0,
    }
    assert all(
        row["candidate_rights_status"] == "RIGHTS_TEST_ONLY_OBSERVATION"
        for row in candidates
    )
    assert all(row["training_eligible"] is False for row in candidates)
    assert all(
        row["candidate_status"] == "TEST_ONLY_NOT_A_CANDIDATE"
        for row in candidates
    )
    assert all(row["test_only"] is True for row in candidates)
    authority_snapshot_sha256 = receipt["inputs"]["source_groups"]["sha256"]
    assert all(
        row["source_groups_authority_snapshot_sha256"]
        == authority_snapshot_sha256
        for row in candidates
    )
    assert all(len(row["source_group_sha256"]) == 64 for row in candidates)
    assert all(row["allowed_use"] is None for row in candidates)
    assert all(row["validity"] is None for row in candidates)
    assert receipt["output"]["required_bindings"] == {
        "source_groups_authority_snapshot_sha256": authority_snapshot_sha256,
        "source_group_record_sha256_present_per_candidate": True,
        "allowed_use_key_present_per_candidate": True,
        "validity_key_present_per_candidate": True,
    }
    assert receipt["mode"] == "DRY_RUN"
    assert receipt["validation_date"] == "2026-08-08"
    assert receipt["runtime_clock"]["validation_date_source"] == (
        "SYSTEM_ASIA_SHANGHAI_CURRENT_DATE"
    )
    assert receipt["runtime_clock"]["clock_source"] == "TEST_ONLY_INJECTED"
    assert all(row["import_mode"] == "DRY_RUN" for row in candidates)
    assert all(row["validation_date"] == "2026-08-08" for row in candidates)
    assert all(row["replay_only"] is False for row in candidates)


def test_complete_allow_is_verified_but_remains_candidate(tmp_path):
    source = source_row(1)
    decision, _ = approve_decision(tmp_path, source)
    receipt, candidates = invoke(tmp_path, [source], [decision], dry_run=False)
    candidate = candidates[0]
    assert receipt["status"] == "PASS_TEST_ONLY_NO_CANDIDATE_EFFECT"
    assert receipt["coverage"]["allow_candidate"] == 0
    assert receipt["coverage"]["test_only_allow_observation"] == 1
    assert receipt["safety"]["training_eligible_groups"] == 0
    assert candidate["candidate_rights_status"] == "RIGHTS_TEST_ONLY_OBSERVATION"
    assert candidate["allow_verification"]["verification_status"] == (
        "ALLOW_EVIDENCE_MECHANICALLY_VERIFIED"
    )
    assert candidate["allowed_use"] is None
    assert candidate["validity"] == {
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31",
    }
    assert candidate["training_eligible"] is False
    assert candidate["cz_confirmation_required"] is False


def test_explicit_reject_is_candidate_only(tmp_path):
    source = source_row(1)
    receipt, candidates = invoke(
        tmp_path,
        [source],
        [reject_decision(source)],
        dry_run=False,
    )
    assert receipt["coverage"]["reject_candidate"] == 0
    assert receipt["coverage"]["test_only_reject_observation"] == 1
    assert candidates[0]["candidate_rights_status"] == (
        "RIGHTS_TEST_ONLY_OBSERVATION"
    )
    assert candidates[0]["allowed_use"] is None
    assert candidates[0]["validity"] is None
    assert candidates[0]["training_eligible"] is False


def test_unresolved_template_is_forbidden_outside_dry_run(tmp_path):
    source = source_row(1)
    assert_hard_stop(
        tmp_path,
        [source],
        [unresolved_decision(source)],
        "UNRESOLVED_DECISION_FORBIDDEN",
        dry_run=False,
    )


def test_dry_run_forbids_allow_and_reject_instead_of_returning_mixed_pass(tmp_path):
    source = source_row(1)
    allow, _ = approve_decision(tmp_path / "allow", source)
    assert_hard_stop(
        tmp_path / "allow",
        [source],
        [allow],
        "DRY_RUN_REQUIRES_ALL_RIGHTS_UNKNOWN",
    )
    assert_hard_stop(
        tmp_path / "reject",
        [source],
        [reject_decision(source)],
        "DRY_RUN_REQUIRES_ALL_RIGHTS_UNKNOWN",
    )


def test_duplicate_missing_and_unknown_groups_hard_stop(tmp_path):
    source_1 = source_row(1)
    source_2 = source_row(2)
    decision_1 = unresolved_decision(source_1)
    assert_hard_stop(
        tmp_path / "duplicate",
        [source_1],
        [decision_1, decision_1],
        "DUPLICATE_DECISION_GROUP_ID",
    )
    assert_hard_stop(
        tmp_path / "missing",
        [source_1, source_2],
        [decision_1],
        "MISSING_DECISION_GROUP_IDS",
    )
    unknown = unresolved_decision(source_1)
    unknown["group_id"] = "R999"
    assert_hard_stop(
        tmp_path / "unknown",
        [source_1],
        [unknown],
        "UNKNOWN_DECISION_GROUP_ID",
    )


def test_identity_count_and_source_sha_drift_hard_stop(tmp_path):
    source = source_row(1)
    title_drift = unresolved_decision(source)
    title_drift["book_title"] = "另一本书"
    assert_hard_stop(
        tmp_path / "title",
        [source],
        [title_drift],
        "DECISION_SOURCE_BINDING_DRIFT",
    )
    count_drift = unresolved_decision(source)
    count_drift["fact_count"] += 1
    assert_hard_stop(
        tmp_path / "count",
        [source],
        [count_drift],
        "DECISION_SOURCE_BINDING_DRIFT",
    )
    decision, _ = approve_decision(tmp_path / "source_sha", source)
    decision["source_sha256"] = "f" * 64
    assert_hard_stop(
        tmp_path / "source_sha",
        [source],
        [decision],
        "ALLOW_IDENTITY_DRIFT",
        dry_run=False,
    )


def test_partial_allow_wrong_scope_and_exact_row_scope_hard_stop(tmp_path):
    source = source_row(1)
    partial, _ = approve_decision(tmp_path / "partial", source)
    partial["rights_holder"] = None
    assert_hard_stop(
        tmp_path / "partial",
        [source],
        [partial],
        "DECISION_SCHEMA_FAIL",
        dry_run=False,
    )
    wrong_scope, _ = approve_decision(tmp_path / "scope", source)
    wrong_scope["decision_scope"] = "RESEARCH_ONLY"
    assert_hard_stop(
        tmp_path / "scope",
        [source],
        [wrong_scope],
        "DECISION_SCHEMA_FAIL",
        dry_run=False,
    )
    row_drift, _ = approve_decision(tmp_path / "rows", source)
    row_drift["row_scope"]["row_ids"] = ["TOY-001:S0001"]
    row_drift["row_scope"]["row_count"] = 1
    assert_hard_stop(
        tmp_path / "rows",
        [source],
        [row_drift],
        "ALLOW_ROW_SCOPE_DRIFT",
        dry_run=False,
    )


def test_missing_or_drifted_evidence_and_expired_allow_hard_stop(tmp_path):
    source = source_row(1)
    missing, _ = approve_decision(tmp_path / "missing_doc", source)
    missing["authority_document_path"] = str(
        (tmp_path / "missing_doc" / "does_not_exist.txt").resolve()
    )
    assert_hard_stop(
        tmp_path / "missing_doc",
        [source],
        [missing],
        "EVIDENCE_MISSING",
        dry_run=False,
    )


def test_realtime_cannot_backfill_date_but_replay_is_explicit_and_never_eligible(
    tmp_path,
):
    source = source_row(1)
    rejected_source = source_row(2)
    decision, snapshot_path = approve_decision(tmp_path / "replay", source)
    rejected_decision = reject_decision(rejected_source)
    historical_validity = {
        "valid_from": "2025-01-01",
        "valid_until": "2025-12-31",
    }
    decision["validity"] = historical_validity
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["validity"] = historical_validity
    write_json(snapshot_path, snapshot)
    decision["authority_snapshot_sha256"] = sha256(snapshot_path)

    assert_hard_stop(
        tmp_path / "realtime_backfill",
        [source],
        [decision],
        "REPLAY_AS_OF_DATE_FORBIDDEN_OUTSIDE_REPLAY",
        dry_run=False,
        replay_as_of_date="2025-06-01",
    )
    receipt, candidates = invoke(
        tmp_path / "replay",
        [source, rejected_source],
        [decision, rejected_decision],
        dry_run=False,
        mode=rights.MODE_REPLAY,
        replay_as_of_date="2025-06-01",
    )
    candidate = candidates[0]
    assert receipt["status"] == (
        "PASS_TEST_ONLY_REPLAY_OBSERVATION_NO_CANDIDATE_EFFECT"
    )
    assert receipt["runtime_clock"]["validation_date_source"] == (
        "EXPLICIT_REPLAY_ONLY_DATE"
    )
    assert receipt["safety"]["replay_only"] is True
    assert receipt["safety"]["replay_can_train_or_promote"] is False
    assert receipt["coverage"]["allow_candidate"] == 0
    assert receipt["coverage"]["reject_candidate"] == 0
    assert receipt["coverage"]["replay_approve_observation"] == 1
    assert receipt["coverage"]["replay_reject_observation"] == 1
    assert candidate["candidate_rights_status"] == "RIGHTS_REPLAY_OBSERVATION_ONLY"
    assert "ALLOW" not in candidate["candidate_rights_status"]
    assert candidate["allowed_use"] is None
    assert candidate["allow_verification"]["verification_status"] == (
        "REPLAY_ONLY_EVIDENCE_VERIFIED_NO_AUTHORITY_EFFECT"
    )
    assert candidate["allow_verification"]["allowed_use"] is None
    assert candidate["allow_verification"]["authority_effect"] == (
        "NONE_REPLAY_ONLY"
    )
    assert candidate["replay_only"] is True
    assert candidate["training_eligible"] is False
    assert candidate["production_promoted"] is False
    assert all(
        row["candidate_rights_status"] == "RIGHTS_REPLAY_OBSERVATION_ONLY"
        for row in candidates
    )
    assert all(row["training_eligible"] is False for row in candidates)


def test_decision_date_field_cannot_replace_system_current_date(tmp_path):
    source = source_row(1)
    decision, _ = approve_decision(tmp_path, source)
    decision["validity"] = {
        "valid_from": "2025-01-01",
        "valid_until": "2025-12-31",
    }
    decision["decision_date"] = "2025-06-01"
    assert_hard_stop(
        tmp_path,
        [source],
        [decision],
        "DECISION_SCHEMA_FAIL",
        dry_run=False,
    )

    document_drift, _ = approve_decision(tmp_path / "doc_sha", source)
    document_drift["authority_document_sha256"] = "0" * 64
    assert_hard_stop(
        tmp_path / "doc_sha",
        [source],
        [document_drift],
        "AUTHORITY_DOCUMENT_SHA_DRIFT",
        dry_run=False,
    )

    snapshot_drift, _ = approve_decision(tmp_path / "snapshot_sha", source)
    snapshot_drift["authority_snapshot_sha256"] = "0" * 64
    assert_hard_stop(
        tmp_path / "snapshot_sha",
        [source],
        [snapshot_drift],
        "AUTHORITY_SNAPSHOT_SHA_DRIFT",
        dry_run=False,
    )

    expired, _ = approve_decision(tmp_path / "expired", source)
    expired["validity"] = {
        "valid_from": "2025-01-01",
        "valid_until": "2025-12-31",
    }
    assert_hard_stop(
        tmp_path / "expired",
        [source],
        [expired],
        "ALLOW_NOT_VALID_AS_OF_DATE",
        dry_run=False,
    )


def test_authority_snapshot_must_bind_every_fact_and_identity_field(tmp_path):
    source = source_row(1)
    decision, snapshot_path = approve_decision(tmp_path, source)
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["row_scope"]["fact_count"] += 1
    write_json(snapshot_path, snapshot)
    decision["authority_snapshot_sha256"] = sha256(snapshot_path)
    assert_hard_stop(
        tmp_path,
        [source],
        [decision],
        "AUTHORITY_SNAPSHOT_BINDING_DRIFT",
        dry_run=False,
    )


def test_unknown_decision_and_input_hash_drift_hard_stop(tmp_path):
    source = source_row(1)
    unknown = unresolved_decision(source)
    unknown["cz_decision"] = "ALLOW_BY_GUESSING"
    assert_hard_stop(
        tmp_path / "unknown_decision",
        [source],
        [unknown],
        "DECISION_SCHEMA_FAIL",
    )
    with pytest.raises(rights.RightsImportError, match="SOURCE_GROUPS_SHA_DRIFT"):
        invoke(
            tmp_path / "source_hash",
            [source],
            [unresolved_decision(source)],
            expected_source_groups_sha256="0" * 64,
        )


def test_schema_sha_is_pinned_and_scope_is_checked_independently(tmp_path):
    source = source_row(1)
    decision, _ = approve_decision(tmp_path, source)
    decision["decision_scope"] = "RESEARCH_ONLY"
    decision["allowed_use"] = "FORBIDDEN"
    weakened_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    approval_properties = weakened_schema["allOf"][0]["then"]["properties"]
    approval_properties["decision_scope"] = {"type": ["string", "null"]}
    approval_properties["allowed_use"] = {
        "enum": [None, "INTERNAL_MODEL_TRAINING", "FORBIDDEN"]
    }
    weakened_schema_path = tmp_path / "weakened_schema.json"
    write_json(weakened_schema_path, weakened_schema)

    assert_hard_stop(
        tmp_path,
        [source],
        [decision],
        "IMPORT_SCHEMA_SHA_DRIFT",
        schema_path=weakened_schema_path,
        dry_run=False,
    )
    assert_hard_stop(
        tmp_path,
        [source],
        [decision],
        "ALLOW_SCOPE_NOT_EXACT",
        schema_path=weakened_schema_path,
        expected_schema_sha256=sha256(weakened_schema_path),
        dry_run=False,
    )
    decision["decision_scope"] = "INTERNAL_MODEL_TRAINING"
    assert_hard_stop(
        tmp_path,
        [source],
        [decision],
        "ALLOW_USE_NOT_EXACT",
        schema_path=weakened_schema_path,
        expected_schema_sha256=sha256(weakened_schema_path),
        dry_run=False,
    )


def test_frozen_baseline_file_missing_path_and_sha_drift_hard_stop(tmp_path):
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(rights.RightsImportError, match="FROZEN_SOURCE_GROUPS_MISSING"):
        rights._read_pinned_file(
            missing,
            expected_path=missing,
            expected_sha256="0" * 64,
            label="SOURCE_GROUPS",
        )

    original = tmp_path / "pinned.jsonl"
    moved = tmp_path / "moved.jsonl"
    original.write_text('{"toy":1}\n', encoding="utf-8")
    moved.write_bytes(original.read_bytes())
    expected_sha256 = sha256(original)
    with pytest.raises(rights.RightsImportError, match="FROZEN_SOURCE_GROUPS_PATH_DRIFT"):
        rights._read_pinned_file(
            moved,
            expected_path=original,
            expected_sha256=expected_sha256,
            label="SOURCE_GROUPS",
        )
    original.write_text('{"toy":2}\n', encoding="utf-8")
    with pytest.raises(rights.RightsImportError, match="FROZEN_SOURCE_GROUPS_SHA_DRIFT"):
        rights._read_pinned_file(
            original,
            expected_path=original,
            expected_sha256=expected_sha256,
            label="SOURCE_GROUPS",
        )


def test_frozen_counts_are_required_and_not_optional_cli_inputs(tmp_path):
    source = source_row(1)
    assert_hard_stop(
        tmp_path,
        [source],
        [unresolved_decision(source)],
        "GROUP_COUNT_DRIFT",
        expected_group_count=74,
    )
    option_strings = {
        option
        for action in rights.build_parser()._actions
        for option in action.option_strings
    }
    assert "--source-groups" not in option_strings
    assert "--schema" not in option_strings
    assert "--expected-group-count" not in option_strings
    assert "--expected-row-count" not in option_strings
    assert "--expected-fact-count" not in option_strings


def test_public_entrypoint_rejects_forged_clock_argument(tmp_path):
    with pytest.raises(TypeError, match="trusted_now_utc_for_test"):
        rights.import_frozen_decisions(
            mode=rights.MODE_DRY_RUN,
            output_path=tmp_path / "candidate.jsonl",
            receipt_path=tmp_path / "receipt.json",
            trusted_now_utc_for_test=datetime(
                2025, 6, 1, 0, 0, tzinfo=timezone.utc
            ),
        )


def test_private_test_clock_with_frozen_baseline_hard_stops_before_output(tmp_path):
    source = source_row(1)
    assert_hard_stop(
        tmp_path,
        [source],
        [unresolved_decision(source)],
        "TEST_CLOCK_FORBIDDEN_WITH_FROZEN_BASELINE",
        baseline_is_frozen=True,
    )


def test_duplicate_source_group_and_duplicate_json_key_hard_stop(tmp_path):
    source = source_row(1)
    assert_hard_stop(
        tmp_path / "duplicate_source",
        [source, copy.deepcopy(source)],
        [unresolved_decision(source)],
        "DUPLICATE_SOURCE_GROUP_ID",
    )

    source_path = tmp_path / "duplicate_key_source.jsonl"
    decisions_path = tmp_path / "duplicate_key_decisions.jsonl"
    output_path = tmp_path / "derived_candidate.jsonl"
    receipt_path = tmp_path / "receipt.json"
    source_path.write_text(
        '{"group_id":"R001","group_id":"R001"}\n', encoding="utf-8"
    )
    write_jsonl(decisions_path, [unresolved_decision(source)])
    with pytest.raises(rights.RightsImportError, match="DUPLICATE_JSON_KEY"):
        rights._import_decisions_core(
            source_groups_path=source_path,
            decisions_path=decisions_path,
            schema_path=SCHEMA_PATH,
            output_path=output_path,
            receipt_path=receipt_path,
            expected_source_groups_sha256=sha256(source_path),
            expected_decisions_sha256=sha256(decisions_path),
            expected_schema_sha256=sha256(SCHEMA_PATH),
            mode=rights.MODE_DRY_RUN,
            expected_group_count=1,
            expected_row_count=2,
            expected_fact_count=3,
            trusted_now_utc_for_test=datetime(
                2026, 8, 8, 4, 0, tzinfo=timezone.utc
            ),
        )
    assert not output_path.exists()
    assert not receipt_path.exists()


def test_source_row_id_cannot_be_reused_across_groups(tmp_path):
    source_1 = source_row(1)
    source_2 = source_row(2)
    source_2["coverage"]["row_ids"][0] = source_1["coverage"]["row_ids"][0]
    assert_hard_stop(
        tmp_path,
        [source_1, source_2],
        [unresolved_decision(source_1), unresolved_decision(source_2)],
        "SOURCE_ROW_ID_REUSED_ACROSS_GROUPS",
    )


def test_candidate_output_cannot_overwrite_verified_evidence(tmp_path):
    source = source_row(1)
    decision, _ = approve_decision(tmp_path, source)
    source_path = tmp_path / "toy_source_groups.jsonl"
    decisions_path = tmp_path / "toy_decisions.jsonl"
    receipt_path = tmp_path / "receipt.json"
    output_path = Path(decision["authority_document_path"])
    original_document = output_path.read_bytes()
    write_jsonl(source_path, [source])
    write_jsonl(decisions_path, [decision])
    with pytest.raises(
        rights.RightsImportError, match="OUTPUT_PATH_ALIASES_VERIFIED_EVIDENCE"
    ):
        rights._import_decisions_core(
            source_groups_path=source_path,
            decisions_path=decisions_path,
            schema_path=SCHEMA_PATH,
            output_path=output_path,
            receipt_path=receipt_path,
            expected_source_groups_sha256=sha256(source_path),
            expected_decisions_sha256=sha256(decisions_path),
            expected_schema_sha256=sha256(SCHEMA_PATH),
            mode=rights.MODE_REALTIME,
            expected_group_count=1,
            expected_row_count=2,
            expected_fact_count=3,
            trusted_now_utc_for_test=datetime(
                2026, 8, 8, 4, 0, tzinfo=timezone.utc
            ),
        )
    assert output_path.read_bytes() == original_document
    assert not receipt_path.exists()

from __future__ import annotations

import json
from copy import deepcopy
import importlib
from pathlib import Path
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = ROOT / "novel-mvp" / "contracts"
sys.path.insert(0, str(CONTRACTS_DIR))

import validate_ledger_entry_envelope as contract  # noqa: E402


FIXTURES = contract.load_fixtures()


@pytest.mark.parametrize("case", FIXTURES, ids=[row["case_id"] for row in FIXTURES])
def test_formal_fixture_case(case: dict) -> None:
    actual_error = contract.validate_fixture_case(case)
    if case["valid"]:
        assert actual_error is None
    else:
        assert actual_error is not None
        assert actual_error.startswith(case["expected_error"])


def test_fixture_suite_identity_and_counts() -> None:
    summary = contract.validate_fixture_suite()
    assert summary == {
        "contract": "LEDGER_ENTRY_ENVELOPE",
        "version": "ledger-entry-envelope-v1",
        "status": "PASS",
        "case_count": 24,
        "valid_case_count": 7,
        "invalid_case_count": 17,
        "mismatches": [],
    }


def test_schema_is_valid_draft_2020_12_and_exposes_reusable_envelope() -> None:
    schema = json.loads(
        (CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$defs"]["envelope"]["required"][-2:] == ["tags", "tag_groups"]
    v1_schema = json.loads(
        (CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert v1_schema["$defs"]["envelope"]["required"] == [
        "id",
        "source_identity",
        "confirm_status",
        "evidence_refs",
        "story_time",
        "created_at",
        "updated_at",
        "rev",
        "note",
    ]
    assert schema["$defs"]["source_identity"]["enum"] == [
        "author_declared",
        "draft_inferred",
        "model_suggested",
        "pack_prefilled",
    ]
    assert schema["$defs"]["author_attestation"]["const"] == "AUTHOR_ATTESTATION"
    assert schema["$defs"]["tag_groups"]["properties"]["rules_version"]["const"] == "tag-group-rules-v1"


def test_contract_text_carries_decisions_review_notes_and_open_boundaries() -> None:
    text = (CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.md").read_text(encoding="utf-8")
    required = [
        "作者在定义卡上的直接编辑＝签字",
        "作者修改后必须保留原 `pack_ref`",
        "**不得由各模块私自发号**",
        "系统时间不能代替故事时间",
        "知情边字段枚举（T3）",
        "ADD-043 规则／能力／例外是否拆条",
        "READER 侧数据结构",
        "新账申请流程",
        "UNIFIED_WRITER_SETTINGSTORE_V1",
    ]
    for needle in required:
        assert needle in text


def test_traceability_links_only_the_two_l1_source_requirements() -> None:
    payload = json.loads(
        (ROOT / "governance" / "capability_traceability.json").read_text(
            encoding="utf-8"
        )
    )
    rows = {row["requirement_id"]: row for row in payload["requirements"]}
    target_ids = {"M4-C01", "AE-AW-N04"}
    contract_refs = {
        "novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.md",
        "novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.schema.json",
        "novel-mvp/contracts/validate_ledger_entry_envelope.py",
        "novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.fixtures.jsonl",
    }
    source_refs = {
        "work/ledger_content_contract_20260822_r01/00_DECIDED_DRAFT_R01.md",
        "work/ledger_content_contract_20260822_r01/01_REVIEW_R01.md",
    }
    for requirement_id in target_ids:
        row = rows[requirement_id]
        assert contract_refs <= set(row["contract_refs"])
        assert (
            "novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.md"
            in row["input_contracts"]
        )
        assert (
            "novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.md"
            in row["output_contracts"]
        )
        assert source_refs <= set(row["design_refs"])
        assert (
            "tests/test_novel_mvp_ledger_entry_envelope_contract.py"
            in row["test_refs"]
        )


def test_cli_validates_the_formal_fixture_file() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(CONTRACTS_DIR / "validate_ledger_entry_envelope.py"),
            "--fixtures",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert completed.stdout.strip() == (
        "PASS_LEDGER_ENTRY_ENVELOPE cases=24 valid=7 invalid=17"
    )


def test_v2_fixture_file_and_forward_confirmation_rules() -> None:
    path = CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.v2.fixtures.jsonl"
    summary = contract.validate_fixture_suite(path)
    assert summary["status"] == "PASS"
    assert summary["case_count"] == 12
    before = {
        "id": "CH-0003",
        "source_identity": "author_declared",
        "confirm_status": "confirmed",
        "evidence_refs": ["AUTHOR_ATTESTATION"],
        "story_time": None,
        "created_at": "2026-08-22T09:00:00+08:00",
        "updated_at": "2026-08-22T09:00:00+08:00",
        "rev": 1,
        "note": "",
    }
    after = dict(before, confirm_status="candidate", rev=2, updated_at="2026-08-22T09:01:00+08:00")
    with pytest.raises(contract.ContractError, match="CONFIRMED_CANNOT_RETURN_TO_CANDIDATE"):
        contract.validate_confirmation_transition(before, after, actor="AUTHOR")


def test_v1_signature_retirement_rule_stays_unchanged() -> None:
    record = {
        "id": "CH-0100",
        "source_identity": "author_declared",
        "confirm_status": "retired",
        "evidence_refs": ["AUTHOR_ATTESTATION"],
        "story_time": None,
        "created_at": "2026-08-22T09:00:00+08:00",
        "updated_at": "2026-08-22T09:01:00+08:00",
        "rev": 2,
        "note": "",
    }
    with pytest.raises(
        contract.ContractError, match="AUTHOR_ATTESTATION_REQUIRES_CONFIRMED$"
    ):
        contract.validate_entry(
            record,
            entry_kind="DEFINITION",
            contract_version=contract.CONTRACT_VERSION_V1,
        )


@pytest.mark.parametrize("group_id", list(contract.CORE_GROUP_SHAPES))
@pytest.mark.parametrize("change", ["targets", "mutation", "managed_by", "write"])
def test_core_group_cannot_be_weakened_at_entry_validation(group_id, change) -> None:
    record = deepcopy(contract.load_fixtures(
        CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.v2.fixtures.jsonl"
    )[0]["document"])
    group = next(g for g in record["tag_groups"]["groups"] if g["group_id"] == group_id)
    if change == "targets":
        group["targets"] = ["/note"]
    elif change == "mutation":
        group["mutation"] = "frozen"
        group["transition_rule"] = None
    elif change == "managed_by":
        group["managed_by"] = "AUTHOR"
    else:
        group["access"]["write"] = ["PLUGIN"]
    with pytest.raises(contract.ContractError, match="CORE_PROTECTION_SHAPE_INVALID"):
        contract.validate_entry(record, entry_kind="DEFINITION",
                                contract_version=contract.CONTRACT_VERSION_V2)


def test_v2_pack_author_edit_preserves_contract_groups() -> None:
    before = deepcopy(contract.load_fixtures(
        CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.v2.fixtures.jsonl"
    )[0]["document"])
    before.update(source_identity="pack_prefilled", confirm_status="candidate", evidence_refs=[])
    after = deepcopy(before)
    after.update(source_identity="author_declared", confirm_status="confirmed",
                 evidence_refs=["AUTHOR_ATTESTATION"], rev=before["rev"] + 1,
                 updated_at="2026-09-08T00:00:00+00:00")
    content = {"pack_ref": "PACK-DEMO-01"}
    contract.validate_pack_prefilled_author_edit(
        before, after, content_before=content, content_after=content)
    group = next(g for g in after["tag_groups"]["groups"]
                 if g["group_id"] == "core:confirmation")
    group["access"]["read"] = ["AUTHOR"]
    group["mask_for"] = ["model_context", "reader_view", "plugin"]
    with pytest.raises(contract.ContractError, match="CONTRACT_GROUP_IMMUTABLE"):
        contract.validate_pack_prefilled_author_edit(
            before, after, content_before=content, content_after=content)


def _v2_confirmed_pair():
    before = deepcopy(contract.load_fixtures(
        CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.v2.fixtures.jsonl"
    )[0]["document"])
    before["confirm_status"] = "confirmed"
    after = deepcopy(before)
    after.update(rev=before["rev"] + 1, updated_at="2026-09-08T00:00:00+00:00")
    return before, after


@pytest.mark.parametrize("snapshots", [{}, {"business_before": {}}, {"business_after": {}}])
def test_retirement_requires_both_business_snapshots(snapshots) -> None:
    before, after = _v2_confirmed_pair()
    after["confirm_status"] = "retired"
    with pytest.raises(contract.ContractError, match="RETIREMENT_BUSINESS_SNAPSHOTS_REQUIRED"):
        contract.validate_confirmation_transition(before, after, actor="AUTHOR", **snapshots)


@pytest.mark.parametrize("failure", ["missing_attestation", "missing_pack_ref", "changed_pack_ref"])
def test_generic_pack_confirmation_cannot_bypass_migration(failure) -> None:
    before, after = _v2_confirmed_pair()
    before.update(source_identity="pack_prefilled", confirm_status="candidate", evidence_refs=[])
    before_body = {"pack_ref": "PACK-DEMO-01"}
    after_body = dict(before_body)
    if failure == "missing_attestation":
        after["evidence_refs"] = ["f001"]
        error = "AUTHOR_EDIT_REQUIRES_ATTESTATION"
    elif failure == "missing_pack_ref":
        after_body = {}
        error = "AFTER_PACK_REF_REQUIRED"
    else:
        after_body["pack_ref"] = "PACK-OTHER-02"
        error = "PACK_REF_MUST_BE_PRESERVED"
    with pytest.raises(contract.ContractError, match=error):
        contract.validate_confirmation_transition(
            before, after, actor="AUTHOR", business_before=before_body, business_after=after_body)


@pytest.mark.parametrize("ledger", ["character", "location", "item", "faction"])
@pytest.mark.parametrize("v2,status,accepted", [
    (True, "retired", True), (True, "confirmed", True),
    (False, "retired", False), (True, "candidate", False),
])
def test_nested_attestations_follow_versioned_retirement_rule(ledger, v2, status, accepted):
    module = importlib.import_module(f"validate_{ledger}_ledger_content")

    def nested_refs(value):
        found = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "evidence_refs" and child:
                    found.append(child)
                elif isinstance(child, (dict, list)):
                    found.extend(nested_refs(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(nested_refs(child))
        return found

    rows = [json.loads(line) for line in (CONTRACTS_DIR / f"{ledger.upper()}_LEDGER_CONTENT.fixtures.jsonl").read_text().splitlines()]
    record = deepcopy(next(row["document"] for row in rows
                           if (row.get("valid") is True or row.get("expect") == "PASS")
                           and "document" in row
                           and not row["document"]["version"].endswith("-v2")
                           and any(nested_refs(v) for k, v in row["document"].items() if k != "evidence_refs")))
    record.update(source_identity="author_declared", confirm_status=status, evidence_refs=["f001"])
    for key, value in record.items():
        if key != "evidence_refs":
            for refs in nested_refs(value):
                refs[:] = ["AUTHOR_ATTESTATION"]
    if v2:
        envelope, _ = _v2_confirmed_pair()
        record.update(version=f"{ledger}-ledger-content-v2", tags=envelope["tags"], tag_groups=envelope["tag_groups"])
    if accepted:
        module.validate_record(record)
    else:
        with pytest.raises(module.ContractError, match="NESTED_AUTHOR_ATTESTATION"):
            module.validate_record(record)

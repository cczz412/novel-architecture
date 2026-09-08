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
    assert summary["case_count"] == 14
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
        contract.validate_confirmation_transition(before, after, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V1)


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
        before, after, contract_version=contract.CONTRACT_VERSION_V2, content_before=content, content_after=content)
    group = next(g for g in after["tag_groups"]["groups"]
                 if g["group_id"] == "core:confirmation")
    group["access"]["read"] = ["AUTHOR"]
    group["mask_for"] = ["model_context", "reader_view", "plugin"]
    with pytest.raises(contract.ContractError, match="CONTRACT_GROUP_IMMUTABLE"):
        contract.validate_pack_prefilled_author_edit(
            before, after, contract_version=contract.CONTRACT_VERSION_V2, content_before=content, content_after=content)


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
        contract.validate_confirmation_transition(before, after, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2, **snapshots)


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
            before, after, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2, business_before=before_body, business_after=after_body)


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


@pytest.mark.parametrize('changes', [
    {'source_identity': 'model_suggested'},
    {'evidence_refs': ['f999']},
    {'note': 'rewritten history'},
])
def test_retirement_preserves_non_lifecycle_envelope(changes):
    before, after = _v2_confirmed_pair()
    before['evidence_refs'] = ['f001']
    after.update(deepcopy(before))
    after.update(confirm_status='retired', rev=before['rev'] + 1,
                 updated_at='2026-09-08T00:00:00+00:00', **changes)
    old_record, new_record, _ = _retirement_records('character')
    old_record.update(before)
    new_record.update(after)
    with pytest.raises(contract.ContractError, match='RETIREMENT_MUST_PRESERVE_ENVELOPE'):
        contract.validate_confirmation_transition(
            before, after, actor='AUTHOR', contract_version=contract.CONTRACT_VERSION_V2,
            business_before=old_record, business_after=new_record)


@pytest.mark.parametrize('before', [None, [], 'bad', 7])
def test_malformed_pack_transition_returns_contract_error(before):
    case = {'fixture_kind': 'pack_author_edit_transition', 'before': before,
            'after': {}, 'content_before': {}, 'content_after': {}}
    assert contract.validate_fixture_case(case) is not None


@pytest.mark.parametrize("intermediate_source", ["author_declared", "draft_inferred", "model_suggested"])
def test_pack_cannot_launder_source_through_candidate_edit(intermediate_source):
    before, middle = _v2_confirmed_pair()
    before.update(source_identity="pack_prefilled", confirm_status="candidate", evidence_refs=[])
    middle.update(source_identity=intermediate_source, confirm_status="candidate", evidence_refs=["f001"])
    with pytest.raises(contract.ContractError, match="AUTHOR_EDIT_STATUS_MUST_BECOME_CONFIRMED"):
        contract.validate_confirmation_transition(
            before, middle, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2,
            business_before={"pack_ref": "PACK-01", "category": "old"},
            business_after={"category": "changed"},
        )


def test_pack_candidate_body_edit_requires_signed_migration():
    old_record, new_record, (before, after) = _pack_candidate_records()
    new_record["record"]["profile"] += " changed"
    with pytest.raises(contract.ContractError, match="PACK_CONTENT_EDIT_REQUIRES_AUTHOR_MIGRATION"):
        contract.validate_confirmation_transition(
            before, after, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2,
            business_before=old_record, business_after=new_record,
        )


@pytest.mark.parametrize("snapshots", [{}, {"business_before": {"pack_ref": "PACK-01"}}])
def test_pack_candidate_edit_requires_business_snapshots(snapshots):
    before, after = _v2_confirmed_pair()
    for row in (before, after):
        row.update(source_identity="pack_prefilled", confirm_status="candidate", evidence_refs=[])
    with pytest.raises(contract.ContractError, match="PACK_CANDIDATE_BUSINESS_SNAPSHOTS_REQUIRED"):
        contract.validate_confirmation_transition(before, after, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2, **snapshots)


def test_versioned_schema_registry_resolves_both_envelope_versions():
    from referencing import Registry, Resource

    v1 = contract.SCHEMAS[contract.CONTRACT_VERSION_V1]
    v2 = contract.SCHEMAS[contract.CONTRACT_VERSION_V2]
    registry = Registry().with_resources([
        (v1["$id"], Resource.from_contents(v1)),
        (v2["$id"], Resource.from_contents(v2)),
    ])
    v2_entry, _ = _v2_confirmed_pair()
    v1_entry = {k: v for k, v in v2_entry.items() if k not in {"tags", "tag_groups"}}
    old_validator = Draft202012Validator({"$ref": v1["$id"]}, registry=registry)
    new_validator = Draft202012Validator({"$ref": v2["$id"]}, registry=registry)
    old_validator.validate(v1_entry)
    new_validator.validate(v2_entry)
    assert not old_validator.is_valid(v2_entry)
    assert not new_validator.is_valid(v1_entry)


@pytest.mark.parametrize("source", ["draft_inferred", "model_suggested"])
def test_v2_common_envelope_rejects_non_author_confirmation(source):
    record, _ = _v2_confirmed_pair()
    record.update(source_identity=source, evidence_refs=["f001"])
    with pytest.raises(contract.ContractError, match="CONFIRMED_REQUIRES_AUTHOR_DECLARED"):
        contract.validate_entry(record, entry_kind="DEFINITION", contract_version=contract.CONTRACT_VERSION_V2)


def test_pack_candidate_unchanged_body_can_advance_revision():
    old_record, new_record, (before, after) = _pack_candidate_records()
    contract.validate_confirmation_transition(
        before, after, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2,
        business_before=old_record, business_after=new_record)


@pytest.mark.parametrize("body_after", [{"pack_ref": "PACK-02"}, {}])
def test_pack_candidate_cannot_drop_or_replace_pack_reference(body_after):
    before, after = _v2_confirmed_pair()
    for row in (before, after):
        row.update(source_identity="pack_prefilled", confirm_status="candidate", evidence_refs=[])
    with pytest.raises(contract.ContractError, match="PACK_REF"):
        contract.validate_confirmation_transition(
            before, after, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2,
            business_before={"pack_ref": "PACK-01"}, business_after=body_after)


@pytest.mark.parametrize("source", ["draft_inferred", "model_suggested"])
def test_v2_non_author_candidates_and_v1_static_behavior_remain(source):
    record, _ = _v2_confirmed_pair()
    record.update(source_identity=source, evidence_refs=["f001"], confirm_status="candidate")
    contract.validate_entry(record, entry_kind="DEFINITION", contract_version=contract.CONTRACT_VERSION_V2)
    old = {k: v for k, v in record.items() if k not in {"tags", "tag_groups"}}
    old["confirm_status"] = "confirmed"
    contract.validate_entry(old, entry_kind="DEFINITION", contract_version=contract.CONTRACT_VERSION_V1)


@pytest.mark.parametrize("ledger", ["character", "location", "item", "faction", "system", "world_rule"])
@pytest.mark.parametrize("source", ["draft_inferred", "model_suggested"])
def test_v2_content_roots_share_author_confirmation_guard(ledger, source):
    module = importlib.import_module(f"validate_{ledger}_ledger_content")
    rows = [json.loads(line) for line in
            (CONTRACTS_DIR / f"{ledger.upper()}_LEDGER_CONTENT.fixtures.jsonl").read_text().splitlines()]
    record = deepcopy(next(row["document"] for row in rows
                           if "document" in row
                           and row["document"]["version"].endswith("-v2")
                           and (row.get("valid") is True or row.get("expect") == "PASS")))
    record.update(source_identity=source, confirm_status="confirmed", evidence_refs=["f001"])
    with pytest.raises(module.ContractError, match="CONFIRMED_REQUIRES_AUTHOR_DECLARED"):
        module.validate_record(record)


@pytest.mark.parametrize("kind", ["confirmation_transition", "pack_author_edit_transition"])
@pytest.mark.parametrize("strip_from", ["before", "after", "both"])
def test_declared_v2_transition_cannot_fall_back_to_v1(kind, strip_from):
    before, after = _v2_confirmed_pair()
    if kind == "pack_author_edit_transition":
        before.update(source_identity="pack_prefilled", confirm_status="candidate", evidence_refs=[])
    for label, row in [("before", before), ("after", after)]:
        if strip_from in {label, "both"}:
            row.pop("tags")
            row.pop("tag_groups")
    case = {"fixture_kind": kind, "contract_version": contract.CONTRACT_VERSION_V2,
            "before": before, "after": after, "actor": "AUTHOR",
            "content_before": {"pack_ref": "PACK-01"},
            "content_after": {"pack_ref": "PACK-01"}}
    error = contract.validate_fixture_case(case)
    assert error is not None and error.startswith("SCHEMA_INVALID")


@pytest.mark.parametrize("version", [contract.CONTRACT_VERSION_V1, contract.CONTRACT_VERSION_V2])
def test_direct_transition_uses_explicit_version(version):
    before, after = _v2_confirmed_pair()
    if version == contract.CONTRACT_VERSION_V1:
        for row in (before, after):
            row.pop("tags")
            row.pop("tag_groups")
    contract.validate_confirmation_transition(
        before, after, actor="AUTHOR", contract_version=version)
    before.update(source_identity="pack_prefilled", confirm_status="candidate", evidence_refs=[])
    contract.validate_pack_prefilled_author_edit(
        before, after, contract_version=version,
        content_before={"pack_ref": "PACK-01"}, content_after={"pack_ref": "PACK-01"})


@pytest.mark.parametrize("version", [None, "ledger-entry-envelope-v999"])
def test_transition_rejects_unknown_explicit_version(version):
    before, after = _v2_confirmed_pair()
    with pytest.raises(contract.ContractError, match="CONTRACT_VERSION_INVALID"):
        contract.validate_confirmation_transition(
            before, after, actor="AUTHOR", contract_version=version)
    with pytest.raises(contract.ContractError, match="CONTRACT_VERSION_INVALID"):
        contract.validate_pack_prefilled_author_edit(
            before, after, contract_version=version,
            content_before={"pack_ref": "PACK-01"}, content_after={"pack_ref": "PACK-01"})


@pytest.mark.parametrize('source', ['draft_inferred', 'model_suggested', 'author_declared'])
@pytest.mark.parametrize('changed_body', [False, True])
@pytest.mark.parametrize('version', [contract.CONTRACT_VERSION_V1, contract.CONTRACT_VERSION_V2])
def test_candidate_cannot_fabricate_pack_provenance(source, changed_body, version):
    before, after = _v2_confirmed_pair()
    before.update(source_identity=source, confirm_status='candidate', evidence_refs=['f001'])
    after.update(source_identity='pack_prefilled', confirm_status='candidate', evidence_refs=[])
    if version == contract.CONTRACT_VERSION_V1:
        for row in (before, after):
            row.pop('tags')
            row.pop('tag_groups')
    old_body = {'category': 'old'}
    new_body = {'category': 'changed' if changed_body else 'old', 'pack_ref': 'FABRICATED-PACK'}
    with pytest.raises(contract.ContractError, match='PACK_PROVENANCE_CANNOT_BE_CREATED_BY_TRANSITION'):
        contract.validate_confirmation_transition(
            before, after, actor='AUTHOR', contract_version=version,
            business_before=old_body, business_after=new_body)


def _retirement_records(ledger):
    rows = contract.load_fixtures(CONTRACTS_DIR / f"{ledger.upper()}_LEDGER_CONTENT.fixtures.jsonl")
    before = deepcopy(next(row["document"] for row in rows
                           if row.get("document", {}).get("version", "").endswith("-v2")
                           and (row.get("valid") is True or row.get("expect") == "PASS")))
    after = deepcopy(before)
    after.update(confirm_status="retired", rev=before["rev"] + 1,
                 updated_at="2026-09-08T01:00:00+00:00")
    keys = set(_v2_confirmed_pair()[0])
    envelopes = [{key: record[key] for key in keys} for record in (before, after)]
    return before, after, envelopes


@pytest.mark.parametrize("ledger", ["character", "location", "item", "faction", "system", "world_rule"])
def test_retirement_validates_full_host_records(ledger):
    before, after, (old_envelope, new_envelope) = _retirement_records(ledger)
    contract.validate_confirmation_transition(
        old_envelope, new_envelope, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2,
        business_before=before, business_after=after)


@pytest.mark.parametrize("partial", [{}, {"profile": "same"}, [], "same"])
def test_retirement_rejects_equal_partial_snapshots(partial):
    _, _, (before, after) = _retirement_records("character")
    with pytest.raises(contract.ContractError, match="RETIREMENT_FULL_RECORD_REQUIRED"):
        contract.validate_confirmation_transition(
            before, after, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2,
            business_before=partial, business_after=deepcopy(partial))


@pytest.mark.parametrize("failure", ["missing_field", "changed_body", "mismatched_envelope", "wrong_version"])
def test_retirement_full_records_cannot_hide_content_changes(failure):
    before, after, (old_envelope, new_envelope) = _retirement_records("character")
    if failure == "missing_field":
        before.pop("profile")
        after.pop("profile")
        error = "RETIREMENT_RECORD_INVALID"
    elif failure == "changed_body":
        after["profile"] += " changed"
        error = "RETIREMENT_MUST_NOT_CHANGE_CONTENT"
    elif failure == "mismatched_envelope":
        after["id"] = "CH-9999"
        error = "RETIREMENT_RECORD_ENVELOPE_MISMATCH"
    else:
        before["version"] = "character-ledger-content-v1.1"
        after["version"] = "character-ledger-content-v1.1"
        error = "RETIREMENT_RECORD_VERSION_MISMATCH"
    with pytest.raises(contract.ContractError, match=error):
        contract.validate_confirmation_transition(
            old_envelope, new_envelope, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2,
            business_before=before, business_after=after)


def _pack_candidate_records(ledger="character"):
    before, after, envelopes = _retirement_records(ledger)
    for record, envelope in zip((before, after), envelopes):
        envelope.update(source_identity="pack_prefilled", confirm_status="candidate", evidence_refs=[])
        record.update(envelope)
        if ledger == "system":
            record["pack_ref"] = "PACK-01"
    return {"record": before, "pack_ref": "PACK-01"}, {"record": after, "pack_ref": "PACK-01"}, envelopes


@pytest.mark.parametrize("ledger", ["character", "location", "item", "faction", "system", "world_rule"])
def test_pack_candidate_validates_complete_host_records(ledger):
    before, after, (old, new) = _pack_candidate_records(ledger)
    contract.validate_confirmation_transition(
        old, new, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2,
        business_before=before, business_after=after)


@pytest.mark.parametrize("failure", ["partial", "missing_field", "mismatched_envelope"])
def test_pack_candidate_rejects_incomplete_or_unbound_records(failure):
    before, after, (old, new) = _pack_candidate_records()
    if failure == "partial":
        before = after = {"pack_ref": "PACK-01"}
    elif failure == "missing_field":
        before["record"].pop("profile")
        after["record"].pop("profile")
    else:
        after["record"]["id"] = "CH-9999"
    with pytest.raises(contract.ContractError, match="PACK_CANDIDATE_.*RECORD"):
        contract.validate_confirmation_transition(
            old, new, actor="AUTHOR", contract_version=contract.CONTRACT_VERSION_V2,
            business_before=before, business_after=after)


@pytest.mark.parametrize("version", ["missing", contract.CONTRACT_VERSION_V1, contract.CONTRACT_VERSION_V2])
def test_entry_fixture_requires_explicit_v2_declaration(version):
    document, _ = _v2_confirmed_pair()
    case = {"fixture_kind": "entry", "entry_kind": "DEFINITION", "document": document}
    if version != "missing":
        case["contract_version"] = version
    error = contract.validate_fixture_case(case)
    if version == contract.CONTRACT_VERSION_V2:
        assert error is None
    else:
        assert error is not None and error.startswith("SCHEMA_INVALID")


def test_undeclared_fixture_summary_reports_actual_v1_validator(tmp_path):
    document, _ = _v2_confirmed_pair()
    path = tmp_path / "legacy.jsonl"
    path.write_text(json.dumps({"case_id": "UNDECLARED", "fixture_kind": "entry",
                               "entry_kind": "DEFINITION", "document": document,
                               "valid": False, "expected_error": "SCHEMA_INVALID"}) + "\n")
    result = contract.validate_fixture_suite(path)
    assert result["status"] == "PASS"
    assert result["version"] == contract.CONTRACT_VERSION_V1

from __future__ import annotations

import json
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
    assert schema["$defs"]["envelope"]["required"] == [
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

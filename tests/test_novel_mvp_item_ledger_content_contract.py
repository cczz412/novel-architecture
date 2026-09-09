from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "novel-mvp/contracts/validate_item_ledger_content.py"
CONTRACT_PATH = ROOT / "novel-mvp/contracts/ITEM_LEDGER_CONTENT.md"
SCHEMA_PATH = ROOT / "novel-mvp/contracts/ITEM_LEDGER_CONTENT.schema.json"
SPEC = importlib.util.spec_from_file_location("validate_item_ledger_content_test", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_fixture_matrix(case: dict) -> None:
    MODULE.validate_fixture_case(case)


def test_fixture_counts_are_frozen() -> None:
    assert MODULE.validate_all_fixtures() == {'cases': 15, 'valid': 7, 'invalid': 8}


def test_contract_identity_and_anchor_shape() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "item-ledger-content-v1" in schema["title"]
    assert "item-ledger-content-v2" in schema["title"]
    assert "chapter_revision_ref" in contract
    assert "revision_text_sha256" in contract
    assert "story_order" in contract
    assert "NOT_RECORDED" in contract
    assert "STORY_TIME_NOT_COMPARABLE" in contract


def test_open_topics_are_not_machine_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    blob = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    for field in ("knowledge_edges", "hardness", "handle", "retrieval_code"):
        assert f'"{field}"' not in blob

def test_item_ownership_is_read_projection() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "变化真值住事实账" in contract
    recorded = next(case for case in CASES if case["case_id"] == "IT-PASS-03")
    assert MODULE.run_query_case(recorded)["owner_ref"] == "CH-0001"

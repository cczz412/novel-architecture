from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "novel-mvp/contracts/validate_ledger_recall_code.py"
CONTRACT_PATH = ROOT / "novel-mvp/contracts/LEDGER_RECALL_CODE.md"
SCHEMA_PATH = ROOT / "novel-mvp/contracts/LEDGER_RECALL_CODE.schema.json"
SPEC = importlib.util.spec_from_file_location(
    "validate_ledger_recall_code",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()

TEN_LEDGER_NAMES = (
    "章节账",
    "事实账",
    "人物账",
    "地点账",
    "物品账",
    "势力账",
    "体系账",
    "世界规则账",
    "长线账",
    "规划账",
)
SHA = "a" * 64


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_recall_code_fixture_matrix(case: dict) -> None:
    MODULE.validate_fixture_case(case)


def test_fixture_counts_are_frozen() -> None:
    assert MODULE.validate_all_fixtures() == {
        "cases": 20,
        "valid": 8,
        "invalid": 12,
    }


def test_ledger_name_enum_matches_registered_ten_ledgers() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert tuple(schema["properties"]["ledger_name"]["enum"]) == TEN_LEDGER_NAMES

    directory_path = ROOT / "novel-mvp/mvp/ledger_directory_tool.py"
    spec = importlib.util.spec_from_file_location(
        "ledger_directory_tool_for_recall_code",
        directory_path,
    )
    assert spec and spec.loader
    directory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(directory)
    assert tuple(directory.FIXED_LEDGER_NAMES) == TEN_LEDGER_NAMES


@pytest.mark.parametrize("name", TEN_LEDGER_NAMES)
def test_every_registered_ledger_name_is_codeable(name: str) -> None:
    MODULE.validate_code(
        {
            "contract": "LEDGER_RECALL_CODE",
            "version": "ledger-recall-code-v1",
            "ledger_name": name,
            "entry_id": "X-0001",
            "rev": 1,
            "sha": SHA,
            "expires_at": None,
        }
    )


def test_retired_entry_still_serves_old_code_with_notice() -> None:
    case = next(item for item in CASES if item["case_id"] == "RC-VALID-04")
    receipt = MODULE.resolve_code(case["code"], case["registry"])
    assert receipt["status"] == "OK"
    assert receipt["rev"] == 1
    assert receipt["retired_notice"] is True
    assert receipt["notice"] == "此条已改判／退役"


def test_rejections_always_carry_a_reason() -> None:
    for case_id in ("RC-VALID-05", "RC-VALID-06", "RC-VALID-07", "RC-VALID-08"):
        case = next(item for item in CASES if item["case_id"] == case_id)
        receipt = MODULE.resolve_code(
            case["code"],
            case["registry"],
            authorized=case.get("authorized", True),
            now=case.get("now"),
        )
        assert receipt["status"] == "REJECTED"
        assert receipt["reason"]


def test_revision_not_found_is_rejected_not_substituted() -> None:
    case = next(item for item in CASES if item["case_id"] == "RC-VALID-02")
    code = copy.deepcopy(case["code"])
    code["rev"] = 9
    receipt = MODULE.resolve_code(code, case["registry"])
    assert receipt == {"status": "REJECTED", "reason": "REVISION_NOT_FOUND"}


def test_shape_a_handle_mechanism_is_not_touched() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    for anchor in (
        "两种形状并存",
        "不迁移现役行为",
        "STALE 拒收",
        "此条已改判／退役",
        "禁止本票改动 `recall_handle_workspace.py`",
    ):
        assert anchor in contract
    handle_source = (
        ROOT / "novel-mvp/mvp/recall_handle_workspace.py"
    ).read_text(encoding="utf-8")
    assert "RecallHandleStaleError" in handle_source
    validator_source = MODULE_PATH.read_text(encoding="utf-8")
    assert "recall_handle_workspace" not in validator_source

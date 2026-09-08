"""Synthetic contract cases; never read the local corpus or import runtime writers."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "novel-mvp/contracts"
SPEC = importlib.util.spec_from_file_location(
    "text_map_contract", CONTRACTS / "validate_c2_c1_text_map.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = [json.loads(line) for line in (
    CONTRACTS / "C2_C1_TEXT_MAP.fixtures.jsonl"
).read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_synthetic_evidence_replay(case, tmp_path, monkeypatch):
    before = copy.deepcopy(case)
    monkeypatch.chdir(tmp_path)
    if case["expected_error"]:
        with pytest.raises(ValueError, match=f'^{case["expected_error"]}$'):
            MODULE.validate_mapping(case["evidence"], case["snapshot"])
    else:
        result = MODULE.validate_mapping(case["evidence"], case["snapshot"])
        raw = case["snapshot"]["text"]
        assert raw[result["start"]:result["end"]] == result["text"]
        assert result["sha256"] == MODULE.sha256(result["text"])
        assert result["text"] == case["evidence"]["original_slice"]
    assert case == before
    assert list(tmp_path.iterdir()) == []


def test_schema_is_valid_and_closed():
    schema = json.loads(MODULE.SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    bad = copy.deepcopy(CASES[0])
    bad["evidence"]["allow_halo"] = True
    with pytest.raises(ValueError, match="TEXT_MAP_SCHEMA_INVALID"):
        MODULE.validate_mapping(bad["evidence"], bad["snapshot"])


@pytest.mark.parametrize("raw,normalized,offsets", [
    ("\u3000\u3000甲\r\n\r\n\u3000乙\r\n", "甲\n乙", [2, 4, 8]),
    ("甲😀e\u0301。", "甲😀e\u0301。", [0, 1, 2, 3, 4]),
    ("甲\r乙", "甲\r乙", [0, 1, 2]),
    ("甲 乙", "甲 乙", [0, 1, 2]),
    ("\r\n\u3000\n", "", []),
    ("", "", []),
])
def test_replay_fixed_offsets_and_complete_partition(raw, normalized, offsets):
    result = MODULE.replay_mapping(raw)
    assert result["normalized_text"] == normalized
    assert result["char_map"] == offsets
    covered = list(offsets)
    for span in result["removed_whitespace"]:
        assert raw[span["start"]:span["end"]] == span["text"]
        assert all(c in MODULE.EDGE_WS for c in span["text"])
        covered.extend(range(span["start"], span["end"]))
    assert sorted(covered) == list(range(len(raw)))


@pytest.mark.parametrize("snapshot", [None, {}, {"text": ""}])
def test_missing_trusted_snapshot_fails(snapshot):
    with pytest.raises(ValueError, match="TEXT_MAP_SNAPSHOT_INVALID"):
        MODULE.validate_mapping(CASES[0]["evidence"], snapshot)


def test_mapping_imports_no_production_modules():
    import ast

    tree = ast.parse((CONTRACTS / "validate_c2_c1_text_map.py").read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)
    assert set(imports) <= {"__future__", "hashlib", "json", "pathlib", "jsonschema"}

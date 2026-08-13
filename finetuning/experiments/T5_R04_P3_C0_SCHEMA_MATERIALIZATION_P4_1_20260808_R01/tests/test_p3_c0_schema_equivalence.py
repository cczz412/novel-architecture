from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/verify_p3_c0_schema_equivalence.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("p4_1_equivalence", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_preserves_frozen_wide_boundary() -> None:
    schema = json.loads((ROOT / "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json").read_text(encoding="utf-8"))
    fact_schema = schema["properties"]["facts"]["items"]
    evidence = fact_schema["properties"]["evidence_ids"]
    speaker = fact_schema["properties"]["speaker"]
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["facts"]
    assert fact_schema["additionalProperties"] is False
    assert set(fact_schema["required"]) == {"fact", "status", "speaker", "evidence_ids"}
    assert "minItems" not in schema["properties"]["facts"]
    assert "minItems" not in evidence
    assert "uniqueItems" not in evidence
    assert "pattern" not in evidence["items"]
    assert "minLength" not in evidence["items"]
    assert speaker["type"] == ["string", "null"]
    gap_text = (ROOT / "P4_1_GAP_LIST.jsonl").read_text(encoding="utf-8")
    assert "目标 corpus 上布尔等价" not in gap_text
    assert "正常返回的 42 条布尔等价" in gap_text
    assert "2 条 oracle 异常单列且 Schema 正常拒绝" in gap_text


def test_mutation_corpus_is_complete_and_equivalent() -> None:
    tool = load_tool()
    tool.assert_authority_snapshots()
    validator = tool.Draft202012Validator(tool.load_schema())
    runner = tool.load_frozen_runner()
    rows = tool.evaluate_mutations(runner, validator)
    assert len(rows) == 44
    assert len({row["case_id"] for row in rows}) == 44
    assert all(row["frozen_runner_accepted_language"] == row["json_schema_accept"] for row in rows)
    assert all(row["frozen_runner_accepted_language"] == row["expected_accept"] for row in rows)
    categories = {row["category"] for row in rows}
    assert {
        "invalid_root_type",
        "invalid_missing_item_key",
        "invalid_fact",
        "invalid_status",
        "invalid_speaker",
        "invalid_evidence_ids",
        "valid_empty_facts",
        "valid_status",
        "valid_speaker",
        "valid_evidence_ids",
        "invalid_status_unhashable",
    } <= categories
    blank_id = next(row for row in rows if row["case_id"] == "M042")
    assert blank_id["value"]["facts"][0]["evidence_ids"] == [""]
    assert blank_id["frozen_runner_accept"] is True
    assert blank_id["json_schema_accept"] is True
    exception_rows = [row for row in rows if row["frozen_runner_exception"] is not None]
    assert [row["case_id"] for row in exception_rows] == ["M043", "M044"]
    assert all(row["frozen_runner_exception"]["type"] == "TypeError" for row in exception_rows)
    assert all(row["frozen_runner_accept"] is None for row in exception_rows)
    assert all(row["frozen_runner_accepted_language"] is False for row in exception_rows)
    assert all(row["json_schema_accept"] is False for row in exception_rows)


def test_frozen_ast_oracle_is_exact_and_dependency_closed() -> None:
    tool = load_tool()
    _, allowed_status, arms, metadata = tool.frozen_check_schema_parts()
    assert metadata["oracle_name"] == "FROZEN_SOURCE_AST_ORACLE"
    assert metadata["function_name"] == "check_schema"
    assert metadata["lineno_start"] == 462
    assert metadata["lineno_end"] == 488
    assert tool.sha256_bytes(metadata["source_segment"].encode("utf-8")) == metadata["source_segment_sha256"]
    assert set(metadata["global_dependencies"]) == {
        "ALLOWED_STATUS",
        "ARMS",
        "Any",
        "all",
        "bool",
        "dict",
        "enumerate",
        "isinstance",
        "list",
        "set",
        "str",
        "tuple",
    }
    assert allowed_status == {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}
    assert arms == {"c2_full": {"required": ("fact", "status", "speaker", "evidence_ids")}}


def test_frozen_gold_and_historical_replay() -> None:
    tool = load_tool()
    validator = tool.Draft202012Validator(tool.load_schema())
    runner = tool.load_frozen_runner()
    gold = tool.evaluate_gold(runner, validator)
    historical = tool.evaluate_historical(runner, validator)
    assert len(gold) == 24
    assert sum(row["json_schema_accept"] for row in gold) == 24
    assert len(historical) == 24
    assert sum(row["json_schema_accept"] for row in historical) == 18
    assert sum(not row["json_schema_accept"] for row in historical) == 6
    assert all(row["frozen_runner_accept"] == row["historical_schema_valid"] for row in historical)
    ordered, ordered_sha = tool.assert_ordered_case_pairing(gold, historical)
    assert len(ordered) == 24
    assert ordered == [row["case_id"] for row in historical]
    assert ordered_sha == tool.sha256_bytes(tool.canonical_json_bytes(ordered))


def test_ordered_case_pairing_hard_stops_on_duplicate_or_reordering() -> None:
    tool = load_tool()
    ids = [f"C{index:02d}" for index in range(24)]
    gold = [{"case_id": case_id} for case_id in ids]
    historical = [{"case_id": case_id} for case_id in ids]
    tool.assert_ordered_case_pairing(gold, historical)
    reordered = list(historical)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    try:
        tool.assert_ordered_case_pairing(gold, reordered)
    except RuntimeError as error:
        assert str(error) == "P4_1_GOLD_HISTORICAL_CASE_ID_ORDER_MISMATCH"
    else:
        raise AssertionError("reordered case ids must hard stop")
    duplicate = list(historical)
    duplicate[-1] = {"case_id": duplicate[0]["case_id"]}
    try:
        tool.assert_ordered_case_pairing(gold, duplicate)
    except RuntimeError as error:
        assert str(error) == "P4_1_HISTORICAL_CASE_ID_NOT_UNIQUE_24"
    else:
        raise AssertionError("duplicate case ids must hard stop")


def test_two_in_memory_builds_are_byte_identical() -> None:
    tool = load_tool()
    first = tool.build_artifacts()
    second = tool.build_artifacts()
    assert first == second
    assert set(first) == {
        "P3_C0_SCHEMA_MUTATION_CORPUS.jsonl",
        "P3_C0_SCHEMA_SOURCE_BINDING.json",
        "P4_1_SCHEMA_EQUIVALENCE_RECEIPT.json",
    }

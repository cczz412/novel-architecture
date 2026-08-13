#!/usr/bin/env python3
"""Materialize and verify the frozen P3 C0 structural schema boundary."""

from __future__ import annotations

import argparse
import ast
import builtins
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.metadata
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
P3 = REPO / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01"
P4 = REPO / "finetuning/experiments/T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01"
M1 = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01"
SET_B = REPO / (
    "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/set_b_r03_work/sealed/"
    "T5_R04_SYNTHETIC_MICRO24_SET_B_R03_20260808"
)

SCHEMA_PATH = ROOT / "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
CORPUS_PATH = ROOT / "P3_C0_SCHEMA_MUTATION_CORPUS.jsonl"
BINDING_PATH = ROOT / "P3_C0_SCHEMA_SOURCE_BINDING.json"
RECEIPT_PATH = ROOT / "P4_1_SCHEMA_EQUIVALENCE_RECEIPT.json"

EXPECTED_AUTHORITY_SHA = {
    "p4_result_ticket": "c8cc626e6dc0fd004ad4011f1d94a2a7fd69d3084c65e61e617e47a960525032",
    "p4_gap_list": "1bae06bedf2215618e874ea2c3d565569161d0e3a25dea640d640901b0a2e320",
    "p4_c0_binding": "284577f96b3b285a48b6502d320ca5ee54c439def37e04c5fd1a10b4a6146c7f",
    "p3_source_lock": "da12e6fec8eaf4be243f1c58ba22dcacbc82ab9fe1590922235ad2686cf00860",
    "p3_output_manifest": "d61161cbb731e1156771530b711b403fca0072c9f44e62b8ac3a5ce7b4a5e47d",
}

FROZEN_PATHS = {
    "p4_result_ticket": P4 / "P4_PREFLIGHT_RESULT_TICKET.md",
    "p4_gap_list": P4 / "P4_PREFLIGHT_GAP_LIST.jsonl",
    "p4_c0_binding": P4 / "P4_C0_SOURCE_BINDING.json",
    "p3_source_lock": P3 / "sealed_inputs_r01/P3_SOURCE_AND_EXECUTION_LOCK.json",
    "p3_output_manifest": P3 / "P3_OUTPUT_MANIFEST.json",
}

QUESTIONS = P3 / "sealed_inputs_r01/track_b/prompts/c0_current_minimal_QUESTIONS_24.jsonl"
P3_BUILD = P3 / "tools/build_p3_inputs.py"
P3_RUN = P3 / "tools/run_p3_context_probe.py"
P3_SCORER = P3 / "tools/score_p3_context_probe.py"
RENDERER = SET_B / "tools/render_from_canonical.py"
M1_RUNNER = M1 / "tools/m1_runner.py"
P3_RAW = P3 / "results_r01/raw/c0_current_minimal/RAW_OUTPUTS.jsonl"
P3_RAW_RECEIPT = P3 / "results_r01/raw/c0_current_minimal/INFERENCE_RECEIPT.json"
P3_BASELINE = P3 / "results_r01/CONTEXT_BASELINE_REPRODUCTION_RECEIPT.json"


class SchemaNotEquivalent(RuntimeError):
    """Raised when the standalone schema differs from the frozen runner."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def canonical_jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
        for row in rows
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def relative(path: Path) -> str:
    return str(path.relative_to(REPO))


def file_binding(path: Path, *, authority: str) -> dict[str, Any]:
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "authority": authority,
    }


def assert_authority_snapshots() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for name, expected in EXPECTED_AUTHORITY_SHA.items():
        path = FROZEN_PATHS[name]
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"FROZEN_AUTHORITY_SHA_DRIFT:{name}")

    p4_binding = read_json(FROZEN_PATHS["p4_c0_binding"])
    p3_lock = read_json(FROZEN_PATHS["p3_source_lock"])
    p3_manifest = read_json(FROZEN_PATHS["p3_output_manifest"])

    for key in ("p3_c0_questions", "p3_c0_build_script", "p3_c0_run_script", "source_renderer"):
        entry = p4_binding[key]
        path = REPO / entry["path"]
        if sha256(path) != entry["sha256"]:
            raise RuntimeError(f"P4_C0_SOURCE_BINDING_DRIFT:{key}")

    locked_runner = p3_lock["source_bindings"]["m1_runner"]
    if Path(locked_runner["path"]) != M1_RUNNER or sha256(M1_RUNNER) != locked_runner["sha256"]:
        raise RuntimeError("P3_SOURCE_LOCK_DRIFT:m1_runner")

    manifest_members = {item["path"]: item for item in p3_manifest["members"]}
    for path in (P3_SCORER, P3_RAW, P3_RAW_RECEIPT, P3_BASELINE):
        rel = str(path.relative_to(P3))
        item = manifest_members.get(rel)
        if item is None or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise RuntimeError(f"P3_OUTPUT_MANIFEST_DRIFT:{rel}")

    raw_receipt = read_json(P3_RAW_RECEIPT)
    baseline = read_json(P3_BASELINE)
    if raw_receipt["raw_sha256"] != sha256(P3_RAW):
        raise RuntimeError("P3_RAW_RECEIPT_DRIFT")
    if baseline["status"] != "PASS_C0_BASELINE_STABLE_PROJECTION_BYTE_IDENTICAL":
        raise RuntimeError("P3_BASELINE_NOT_FROZEN_PASS")
    if baseline["new_raw_sha256"] != sha256(P3_RAW):
        raise RuntimeError("P3_BASELINE_RAW_SHA_DRIFT")
    return p4_binding, p3_lock, p3_manifest


def frozen_check_schema_parts() -> tuple[ast.FunctionDef, set[str], dict[str, dict[str, Any]], dict[str, Any]]:
    source = M1_RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(M1_RUNNER))
    functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "check_schema"
    ]
    if len(functions) != 1:
        raise RuntimeError(f"FROZEN_M1_CHECK_SCHEMA_COUNT:{len(functions)}")
    function = functions[0]
    if function.decorator_list:
        raise RuntimeError("FROZEN_M1_CHECK_SCHEMA_DECORATOR_NOT_ALLOWED")
    if any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and node is not function
        for node in ast.walk(function)
    ):
        raise RuntimeError("FROZEN_M1_CHECK_SCHEMA_NESTED_FUNCTION_NOT_ALLOWED")
    if any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(function)):
        raise RuntimeError("FROZEN_M1_CHECK_SCHEMA_CLOSURE_DECLARATION_NOT_ALLOWED")

    allowed_node = next(
        (
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "ALLOWED_STATUS" for target in node.targets)
        ),
        None,
    )
    arms_node = next(
        (
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARMS"
        ),
        None,
    )
    if allowed_node is None or not isinstance(arms_node, ast.Dict):
        raise RuntimeError("FROZEN_M1_SCHEMA_CONSTANTS_NOT_FOUND")
    allowed_status = set(ast.literal_eval(allowed_node))
    c2_node = next(
        (value for key, value in zip(arms_node.keys, arms_node.values) if ast.literal_eval(key) == "c2_full"),
        None,
    )
    if not isinstance(c2_node, ast.Dict):
        raise RuntimeError("FROZEN_M1_C2_ARM_NOT_FOUND")
    required_node = next(
        (value for key, value in zip(c2_node.keys, c2_node.values) if ast.literal_eval(key) == "required"),
        None,
    )
    if required_node is None:
        raise RuntimeError("FROZEN_M1_C2_REQUIRED_KEYS_NOT_FOUND")
    arms = {"c2_full": {"required": tuple(ast.literal_eval(required_node))}}
    function_source = ast.get_source_segment(source, function)
    if function_source is None:
        raise RuntimeError("FROZEN_M1_CHECK_SCHEMA_SOURCE_NOT_RECOVERABLE")
    argument_names = {argument.arg for argument in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)}
    if function.args.vararg:
        argument_names.add(function.args.vararg.arg)
    if function.args.kwarg:
        argument_names.add(function.args.kwarg.arg)
    local_names = argument_names | {
        node.id for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    loaded_names = {
        node.id for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    global_dependencies = sorted(loaded_names - local_names)
    registered_globals = {"ALLOWED_STATUS", "ARMS"}
    type_names = {"Any"}
    builtin_names = {name for name in global_dependencies if hasattr(builtins, name)}
    unregistered = set(global_dependencies) - registered_globals - type_names - builtin_names
    if unregistered:
        raise RuntimeError(f"FROZEN_M1_CHECK_SCHEMA_NEW_GLOBAL_DEPENDENCY:{sorted(unregistered)}")
    metadata = {
        "oracle_name": "FROZEN_SOURCE_AST_ORACLE",
        "function_name": "check_schema",
        "lineno_start": function.lineno,
        "lineno_end": function.end_lineno,
        "source_segment": function_source,
        "source_segment_sha256": sha256_bytes(function_source.encode("utf-8")),
        "global_dependencies": global_dependencies,
        "registered_ast_assignments": ["ALLOWED_STATUS", "ARMS['c2_full']['required']"],
        "decorator_count": 0,
        "nested_function_count": 0,
    }
    return function, allowed_status, arms, metadata


def load_frozen_runner() -> Any:
    function, allowed_status, arms, metadata = frozen_check_schema_parts()
    isolated = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            function,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(isolated)
    namespace: dict[str, Any] = {"ALLOWED_STATUS": allowed_status, "ARMS": arms, "Any": Any}
    exec(compile(isolated, str(M1_RUNNER), "exec"), namespace)
    return SimpleNamespace(
        check_schema=namespace["check_schema"],
        ast_metadata=metadata,
        check_schema_source_sha256=metadata["source_segment_sha256"],
        import_method="FROZEN_SOURCE_AST_ORACLE",
    )


def load_schema() -> dict[str, Any]:
    schema = read_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return schema


def schema_error_categories(validator: Draft202012Validator, value: Any) -> list[dict[str, str]]:
    rows = []
    for error in sorted(validator.iter_errors(value), key=lambda item: (list(item.path), item.validator)):
        instance_path = "/" + "/".join(str(part) for part in error.path) if error.path else "/"
        schema_path = "/" + "/".join(str(part) for part in error.schema_path)
        rows.append(
            {
                "validator": str(error.validator),
                "instance_path": instance_path,
                "schema_path": schema_path,
            }
        )
    return rows


def valid_fact() -> dict[str, Any]:
    return {
        "fact": "甲完成了检查。",
        "status": "已发生",
        "speaker": None,
        "evidence_ids": ["T01"],
    }


def mutation_specs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(case_id: str, category: str, description: str, value: Any, expected: bool) -> None:
        rows.append(
            {
                "case_id": case_id,
                "category": category,
                "description": description,
                "value": value,
                "expected_accept": expected,
            }
        )

    baseline = {"facts": [valid_fact()]}
    add("M001", "valid_baseline", "单事实完整对象", baseline, True)
    add("M002", "valid_empty_facts", "facts 允许空数组", {"facts": []}, True)
    for index, status in enumerate(("已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"), 3):
        value = deepcopy(baseline)
        value["facts"][0]["status"] = status
        add(f"M{index:03d}", "valid_status", f"合法 status：{status}", value, True)
    for index, speaker in enumerate((None, "甲", ""), 11):
        value = deepcopy(baseline)
        value["facts"][0]["speaker"] = speaker
        add(f"M{index:03d}", "valid_speaker", f"合法 speaker：{speaker!r}", value, True)
    for index, evidence_ids in enumerate(([], ["T01", "T01"], ["任意", "B99", "X"]), 14):
        value = deepcopy(baseline)
        value["facts"][0]["evidence_ids"] = evidence_ids
        add(f"M{index:03d}", "valid_evidence_ids", f"宽松 evidence_ids：{evidence_ids!r}", value, True)

    invalid_roots = ((None, "null"), ([], "list"), ("text", "string"), (3, "number"))
    for index, (value, label) in enumerate(invalid_roots, 17):
        add(f"M{index:03d}", "invalid_root_type", f"根为 {label}", value, False)
    add("M021", "invalid_root_shape", "缺 facts", {}, False)
    add("M022", "invalid_root_shape", "根增加多余字段", {"facts": [], "extra": True}, False)
    add("M023", "invalid_facts_type", "facts 不是数组", {"facts": {}}, False)
    add("M024", "invalid_item_type", "facts item 不是 object", {"facts": ["fact"]}, False)

    for index, key in enumerate(("fact", "status", "speaker", "evidence_ids"), 25):
        value = deepcopy(baseline)
        del value["facts"][0][key]
        add(f"M{index:03d}", "invalid_missing_item_key", f"item 缺 {key}", value, False)
    value = deepcopy(baseline)
    value["facts"][0]["extra"] = True
    add("M029", "invalid_extra_item_key", "item 增加多余字段", value, False)

    value = deepcopy(baseline)
    value["facts"][0]["fact"] = ""
    add("M030", "invalid_fact", "fact 空串", value, False)
    value = deepcopy(baseline)
    value["facts"][0]["fact"] = 7
    add("M031", "invalid_fact", "fact 非字符串", value, False)

    for index, status in enumerate(("不存在", "", None, 7), 32):
        value = deepcopy(baseline)
        value["facts"][0]["status"] = status
        add(f"M{index:03d}", "invalid_status", f"非法 status：{status!r}", value, False)
    for index, speaker in enumerate((7, ["甲"], {"name": "甲"}), 36):
        value = deepcopy(baseline)
        value["facts"][0]["speaker"] = speaker
        add(f"M{index:03d}", "invalid_speaker", f"非法 speaker：{speaker!r}", value, False)
    for index, evidence_ids in enumerate(("T01", ["T01", 2], [None]), 39):
        value = deepcopy(baseline)
        value["facts"][0]["evidence_ids"] = evidence_ids
        add(f"M{index:03d}", "invalid_evidence_ids", f"非法 evidence_ids：{evidence_ids!r}", value, False)
    value = deepcopy(baseline)
    value["facts"][0]["evidence_ids"] = [""]
    add("M042", "valid_evidence_ids", "宽松 evidence_ids：空字符串元素", value, True)
    value = deepcopy(baseline)
    value["facts"][0]["status"] = []
    add("M043", "invalid_status_unhashable", "非法 status：空数组；冻结 oracle 抛 TypeError", value, False)
    value = deepcopy(baseline)
    value["facts"][0]["status"] = {}
    add("M044", "invalid_status_unhashable", "非法 status：空对象；冻结 oracle 抛 TypeError", value, False)
    return rows


def evaluate_value(runner: Any, validator: Draft202012Validator, value: Any) -> dict[str, Any]:
    runner_accept: bool | None = None
    runner_errors: list[str] | None = None
    runner_exception: dict[str, str] | None = None
    try:
        runner_accept, runner_errors = runner.check_schema(value, "c2_full")
    except Exception as error:  # exact frozen runtime behavior is audit evidence
        runner_exception = {"type": type(error).__name__, "message": str(error)}
    schema_errors = schema_error_categories(validator, value)
    schema_accept = not schema_errors
    return {
        "frozen_runner_accept": runner_accept,
        "frozen_runner_errors": runner_errors,
        "frozen_runner_returned_normally": runner_exception is None,
        "frozen_runner_accepted_language": runner_accept is True and runner_exception is None,
        "frozen_runner_exception": runner_exception,
        "json_schema_accept": schema_accept,
        "json_schema_error_categories": schema_errors,
    }


def evaluate_mutations(runner: Any, validator: Draft202012Validator) -> list[dict[str, Any]]:
    records = []
    for spec in mutation_specs():
        record = {**spec, **evaluate_value(runner, validator, spec["value"])}
        if record["frozen_runner_accepted_language"] != record["json_schema_accept"]:
            raise SchemaNotEquivalent(f"HARD_STOP_ACCEPTED_LANGUAGE_NOT_EQUIVALENT:{record['case_id']}")
        if record["frozen_runner_accepted_language"] != record["expected_accept"]:
            raise SchemaNotEquivalent(f"HARD_STOP_MUTATION_EXPECTATION_MISMATCH:{record['case_id']}")
        if not record["frozen_runner_returned_normally"] and record["json_schema_accept"]:
            raise SchemaNotEquivalent(f"HARD_STOP_ORACLE_EXCEPTION_SCHEMA_ACCEPTED:{record['case_id']}")
        records.append(record)
    return records


def evaluate_gold(runner: Any, validator: Draft202012Validator) -> list[dict[str, Any]]:
    questions = read_jsonl(QUESTIONS)
    if len(questions) != 24 or len({row["case_id"] for row in questions}) != 24:
        raise RuntimeError("P3_C0_QUESTIONS_DENOMINATOR_DRIFT")
    results = []
    for row in questions:
        assistants = [message["content"] for message in row["messages"] if message["role"] == "assistant"]
        if len(assistants) != 1:
            raise RuntimeError(f"P3_C0_ASSISTANT_MESSAGE_COUNT:{row['case_id']}")
        value = json.loads(assistants[0])
        evaluated = evaluate_value(runner, validator, value)
        if not evaluated["frozen_runner_returned_normally"]:
            raise SchemaNotEquivalent(f"HARD_STOP_GOLD_ORACLE_EXCEPTION:{row['case_id']}")
        if not evaluated["frozen_runner_accepted_language"] or not evaluated["json_schema_accept"]:
            raise SchemaNotEquivalent(f"HARD_STOP_GOLD_NOT_ACCEPTED:{row['case_id']}")
        results.append({"case_id": row["case_id"], **evaluated})
    return results


def evaluate_historical(runner: Any, validator: Draft202012Validator) -> list[dict[str, Any]]:
    rows = read_jsonl(P3_RAW)
    if len(rows) != 24 or len({row["case_id"] for row in rows}) != 24:
        raise RuntimeError("P3_C0_RAW_DENOMINATOR_DRIFT")
    results = []
    for row in rows:
        evaluated = evaluate_value(runner, validator, row["parsed_output"])
        if not evaluated["frozen_runner_returned_normally"]:
            raise SchemaNotEquivalent(f"HARD_STOP_HISTORICAL_ORACLE_EXCEPTION:{row['case_id']}")
        if evaluated["frozen_runner_accepted_language"] != evaluated["json_schema_accept"]:
            raise SchemaNotEquivalent(f"HARD_STOP_HISTORICAL_ACCEPTED_LANGUAGE_NOT_EQUIVALENT:{row['case_id']}")
        if evaluated["frozen_runner_accept"] != row["schema_valid"]:
            raise SchemaNotEquivalent(f"HARD_STOP_HISTORICAL_FLAG_MISMATCH:{row['case_id']}")
        results.append(
            {
                "case_id": row["case_id"],
                "historical_json_valid": row["json_valid"],
                "historical_schema_valid": row["schema_valid"],
                **evaluated,
            }
        )
    return results


def assert_ordered_case_pairing(
    gold: list[dict[str, Any]], historical: list[dict[str, Any]]
) -> tuple[list[str], str]:
    gold_ids = [row["case_id"] for row in gold]
    historical_ids = [row["case_id"] for row in historical]
    if len(gold_ids) != 24 or len(set(gold_ids)) != 24:
        raise RuntimeError("P4_1_GOLD_CASE_ID_NOT_UNIQUE_24")
    if len(historical_ids) != 24 or len(set(historical_ids)) != 24:
        raise RuntimeError("P4_1_HISTORICAL_CASE_ID_NOT_UNIQUE_24")
    if gold_ids != historical_ids:
        raise RuntimeError("P4_1_GOLD_HISTORICAL_CASE_ID_ORDER_MISMATCH")
    return gold_ids, sha256_bytes(canonical_json_bytes(gold_ids))


def build_binding(corpus_bytes: bytes) -> dict[str, Any]:
    runner = load_frozen_runner()
    sources = {
        "p3_c0_questions": file_binding(QUESTIONS, authority="P4_C0_SOURCE_BINDING"),
        "renderer": file_binding(RENDERER, authority="P4_C0_SOURCE_BINDING"),
        "p3_build": file_binding(P3_BUILD, authority="P4_C0_SOURCE_BINDING"),
        "p3_run": file_binding(P3_RUN, authority="P4_C0_SOURCE_BINDING"),
        "frozen_m1_runner": {
            **file_binding(M1_RUNNER, authority="P3_SOURCE_AND_EXECUTION_LOCK"),
            "check_schema_oracle": runner.ast_metadata,
        },
        "p3_scorer": file_binding(P3_SCORER, authority="P3_OUTPUT_MANIFEST"),
        "p3_c0_raw_outputs": file_binding(P3_RAW, authority="P3_OUTPUT_MANIFEST"),
        "p3_c0_raw_receipt": file_binding(P3_RAW_RECEIPT, authority="P3_OUTPUT_MANIFEST"),
        "p3_baseline_reproduction": file_binding(P3_BASELINE, authority="P3_OUTPUT_MANIFEST"),
    }
    derived = {
        "standalone_schema": file_binding(SCHEMA_PATH, authority="P4_1_DERIVED"),
        "equivalence_checker": file_binding(Path(__file__).resolve(), authority="P4_1_DERIVED"),
        "mutation_corpus": {
            "path": relative(CORPUS_PATH),
            "bytes": len(corpus_bytes),
            "sha256": sha256_bytes(corpus_bytes),
            "authority": "P4_1_DERIVED",
        },
    }
    return {
        "schema_version": "t5-r04-p4-1-c0-schema-source-binding-v1",
        "status": "PASS_FROZEN_SOURCE_BYTES_BOUND_NO_RUN_AUTHORITY",
        "authority_snapshots": {
            name: {"path": relative(FROZEN_PATHS[name]), "sha256": expected}
            for name, expected in EXPECTED_AUTHORITY_SHA.items()
        },
        "sources": sources,
        "derived": derived,
        "equivalence_scope": (
            "standalone Schema 与已核 SHA 的 frozen check_schema 在固定 44 条目标 corpus、"
            "24 gold、24 历史输出上的接受语言等价；目标 corpus 中正常返回的 42 条布尔等价，"
            "2 条 oracle 异常单列且 Schema 正常拒绝，不声称失败方式相同。"
        ),
        "non_claims": [
            "未完整导入 M1 runner 模块",
            "不宣称与训练运行时所有行为完全等价",
            "不宣称与 Prompt 语义等价",
            "不宣称所有 JSON 输入都获得相同布尔返回或相同异常行为",
            "不宣称 standalone Schema 可无差别替换旧 runtime runner",
        ],
        "model_run_authorized": False,
        "training_authorized": False,
    }


def build_artifacts() -> dict[str, bytes]:
    assert_authority_snapshots()
    schema = load_schema()
    validator = Draft202012Validator(schema)
    runner = load_frozen_runner()
    mutations = evaluate_mutations(runner, validator)
    gold = evaluate_gold(runner, validator)
    historical = evaluate_historical(runner, validator)
    ordered_case_ids, ordered_case_id_sha = assert_ordered_case_pairing(gold, historical)

    corpus_bytes = canonical_jsonl_bytes(mutations)
    binding = build_binding(corpus_bytes)
    binding_bytes = canonical_json_bytes(binding)
    projection = {
        "mutation_corpus_sha256": sha256_bytes(corpus_bytes),
        "source_binding_sha256": sha256_bytes(binding_bytes),
        "gold_cases": [row["case_id"] for row in gold],
        "ordered_case_id_sha256": ordered_case_id_sha,
        "historical_cases": [
            {"case_id": row["case_id"], "accepted": row["historical_schema_valid"]}
            for row in historical
        ],
    }
    projection_bytes = canonical_json_bytes(projection)
    runner_error_counts = Counter(
        error
        for row in mutations
        for error in (row["frozen_runner_errors"] or [])
    )
    schema_error_counts = Counter(
        error["validator"] for row in mutations for error in row["json_schema_error_categories"]
    )
    receipt = {
        "schema_version": "t5-r04-p4-1-schema-equivalence-receipt-v1",
        "status": "PASS_P3_C0_STRUCTURAL_SCHEMA_MATERIALIZED_NO_RUN_AUTHORITY",
        "scope": "STRUCTURAL_ACCEPTED_LANGUAGE_EQUIVALENCE_AFTER_JSON_PARSE_ONLY",
        "equivalence_statement": (
            "44 条目标 corpus 接受语言等价；正常返回的 42 条布尔等价；"
            "2 条 oracle 异常单列且 Schema 正常拒绝；不声称失败方式相同。"
        ),
        "json_schema_draft": "2020-12",
        "jsonschema_package_version": importlib.metadata.version("jsonschema"),
        "frozen_check_schema_import": {
            "method": runner.import_method,
            **runner.ast_metadata,
            "full_runner_module_import_succeeded": False,
        },
        "mutation_corpus": {
            "cases": len(mutations),
            "accepted": sum(row["json_schema_accept"] for row in mutations),
            "rejected": sum(not row["json_schema_accept"] for row in mutations),
            "accepted_language_mismatches": sum(
                row["frozen_runner_accepted_language"] != row["json_schema_accept"]
                for row in mutations
            ),
            "sha256": sha256_bytes(corpus_bytes),
        },
        "accepted_language_equivalence": {
            "mutation_cases": len(mutations),
            "gold_cases": len(gold),
            "historical_cases": len(historical),
            "mismatches_total": sum(
                row["frozen_runner_accepted_language"] != row["json_schema_accept"]
                for row in [*mutations, *gold, *historical]
            ),
        },
        "normal_return_boolean_equivalence": {
            "mutation_cases_compared": sum(row["frozen_runner_returned_normally"] for row in mutations),
            "gold_cases_compared": len(gold),
            "historical_cases_compared": len(historical),
            "mismatches_total": sum(
                row["frozen_runner_accept"] != row["json_schema_accept"]
                for row in [*mutations, *gold, *historical]
                if row["frozen_runner_returned_normally"]
            ),
        },
        "oracle_exception_audit": {
            "count": sum(not row["frozen_runner_returned_normally"] for row in mutations),
            "cases": [
                {
                    "case_id": row["case_id"],
                    "exception_type": row["frozen_runner_exception"]["type"],
                    "schema_accept": row["json_schema_accept"],
                }
                for row in mutations
                if not row["frozen_runner_returned_normally"]
            ],
            "schema_rejected_all": all(
                not row["json_schema_accept"]
                for row in mutations
                if not row["frozen_runner_returned_normally"]
            ),
            "failure_mode_equivalence_claimed": False,
        },
        "frozen_gold_replay": {
            "cases": len(gold),
            "accepted_by_runner": sum(row["frozen_runner_accepted_language"] for row in gold),
            "accepted_by_schema": sum(row["json_schema_accept"] for row in gold),
            "accepted_language_mismatches": 0,
        },
        "historical_c0_replay": {
            "cases": len(historical),
            "json_valid": sum(row["historical_json_valid"] for row in historical),
            "schema_valid": sum(row["historical_schema_valid"] for row in historical),
            "schema_invalid": sum(not row["historical_schema_valid"] for row in historical),
            "accepted_language_mismatches": 0,
            "ordered_case_ids_match_gold": True,
            "ordered_case_id_sha256": ordered_case_id_sha,
        },
        "case_pairing": {
            "gold_unique": len(set(ordered_case_ids)) == 24,
            "historical_unique": len({row["case_id"] for row in historical}) == 24,
            "ordered_lists_equal": True,
            "ordered_case_id_sha256": ordered_case_id_sha,
        },
        "error_category_audit": {
            "frozen_runner": dict(sorted(runner_error_counts.items())),
            "json_schema_validator_keywords": dict(sorted(schema_error_counts.items())),
            "error_text_equivalence_required": False,
        },
        "determinism": {
            "builds_compared": 2,
            "byte_identical": True,
            "stable_projection_sha256": sha256_bytes(projection_bytes),
        },
        "source_binding_sha256": sha256_bytes(binding_bytes),
        "actions_performed": {
            "model_or_api_call": False,
            "training": False,
            "prompt_change": False,
            "runner_change": False,
            "gold_change": False,
            "semantic_contract_change": False,
        },
        "construction_history": {
            "initial_locked_env_result": "3 failed / 1 passed",
            "cause": "冻结 runner 顶层训练依赖 yaml 不在仓库锁定环境；jsonschema 4.26.0 已存在。",
            "invalidated_method": "DIRECT_FULL_MODULE_IMPORT",
            "resolution": "核整文件 SHA 后，以 FROZEN_SOURCE_AST_ORACLE 执行原 AST 函数节点及同 AST 常量；未安装依赖、未改旧 runner。",
            "second_result": "2 failed / 2 passed",
            "second_cause": "最初把非字符串 status 设为 list，冻结 runner 对不可哈希值抛 TypeError，无法形成布尔对照。",
            "second_temporary_resolution_invalidated": "曾把该位换成数值 7；后续审查要求恢复不可哈希难例，因此该临时方案不再作为最终 corpus。",
            "final_resolution": "恢复 status=[] 与 status={}，以 accepted-language 等价为主口径；异常单列且 Schema 必须拒绝。未改旧 runner。",
        },
    }
    return {
        "P3_C0_SCHEMA_MUTATION_CORPUS.jsonl": corpus_bytes,
        "P3_C0_SCHEMA_SOURCE_BINDING.json": binding_bytes,
        "P4_1_SCHEMA_EQUIVALENCE_RECEIPT.json": canonical_json_bytes(receipt),
    }


def write_artifacts() -> None:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise RuntimeError("HARD_STOP_P4_1_TWO_BUILD_NOT_BYTE_IDENTICAL")
    for name, data in first.items():
        (ROOT / name).write_bytes(data)


def check_existing() -> None:
    expected = build_artifacts()
    for name, data in expected.items():
        path = ROOT / name
        if not path.is_file() or path.read_bytes() != data:
            raise RuntimeError(f"P4_1_GENERATED_ARTIFACT_DRIFT:{name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()
    if args.command == "build":
        write_artifacts()
    else:
        check_existing()
    receipt = read_json(RECEIPT_PATH)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "mutation_cases": receipt["mutation_corpus"]["cases"],
                "gold_cases": receipt["frozen_gold_replay"]["cases"],
                "historical_cases": receipt["historical_c0_replay"]["cases"],
                "accepted_language_mismatches": receipt["accepted_language_equivalence"][
                    "mismatches_total"
                ],
                "oracle_exceptions": receipt["oracle_exception_audit"]["count"],
                "ordered_case_id_sha256": receipt["case_pairing"]["ordered_case_id_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

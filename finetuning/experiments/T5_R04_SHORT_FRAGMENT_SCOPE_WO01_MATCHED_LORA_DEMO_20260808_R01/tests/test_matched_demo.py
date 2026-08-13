from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path


EXP = Path(__file__).resolve().parents[1]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load(EXP / "tools/build_inputs.py", "wo01_matched_builder")
runner = load(EXP / "tools/run_matched_lora.py", "wo01_matched_runner")


def test_recipe_is_exact_m1_c2_recipe():
    tree = ast.parse(runner.M1_RUNNER.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "config_values")
    returned = next(node.value for node in ast.walk(function) if isinstance(node, ast.Return))
    values = {
        ast.literal_eval(key): ast.literal_eval(value)
        for key, value in zip(returned.keys, returned.values, strict=True)
        if isinstance(value, (ast.Constant, ast.Dict))
    }
    assert (values["iters"], values["batch_size"], values["grad_accumulation_steps"]) == (288, 2, 4)
    assert (values["learning_rate"], values["num_layers"], values["seed"]) == (3e-5, 16, 20260802)
    assert values["lora_parameters"] == {"rank": 32, "dropout": 0.0, "scale": 0.125}
    assert values["save_every"] == 96


def test_c2_schema_recovers_invalid_status_separately():
    value = {"facts": [{"fact": "门正在关闭。", "status": "进行中", "speaker": None, "evidence_ids": ["T01"]}]}
    valid, errors = runner.check_c2_schema(value, "target_only")
    assert valid is False
    assert errors == ["fact_0_status"]


def test_rendered_data_is_three_by_24_and_gold_matched():
    for split, expected_facts in (("source_train", 43), ("dev", 48)):
        rows = {arm: builder.read_jsonl(EXP / "data" / split / f"{arm}.jsonl") for arm in builder.ARMS}
        assert all(len(value) == 24 for value in rows.values())
        assert all(sum(len(json.loads(row["messages"][-1]["content"])["facts"]) for row in value) == expected_facts for value in rows.values())
        baseline = [row["messages"][-1]["content"] for row in rows[builder.ARMS[0]]]
        assert all([row["messages"][-1]["content"] for row in rows[arm]] == baseline for arm in builder.ARMS[1:])


def test_set_b_never_enters_training():
    train_ids = {row["case_id"] for row in builder.read_jsonl(EXP / "data/source_train/TARGET_ONLY.jsonl")}
    dev_ids = {row["case_id"] for row in builder.read_jsonl(EXP / "data/dev/TARGET_ONLY.jsonl")}
    assert not train_ids & dev_ids
    assert all(not case_id.startswith("MICRO24B-") for case_id in train_ids)


def test_model_visible_rows_hide_case_and_arm_labels():
    for split in ("source_train", "dev"):
        for arm in builder.ARMS:
            for row in builder.read_jsonl(EXP / "data" / split / f"{arm}.jsonl"):
                visible = json.dumps(row["messages"][:-1], ensure_ascii=False)
                assert row["case_id"] not in visible
                assert arm not in visible


def test_one_train_and_one_dev_keep_only_scope_difference():
    for split in ("source_train", "dev"):
        rows = {arm: builder.read_jsonl(EXP / "data" / split / f"{arm}.jsonl")[0] for arm in builder.ARMS}
        assert len({row["messages"][0]["content"] for row in rows.values()}) == 1
        assert len({row["messages"][-1]["content"] for row in rows.values()}) == 1
        assert len({row["messages"][1]["content"] for row in rows.values()}) == 3

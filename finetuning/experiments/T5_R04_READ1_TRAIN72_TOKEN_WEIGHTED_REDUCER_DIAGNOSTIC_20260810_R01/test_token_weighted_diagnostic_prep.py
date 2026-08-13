from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


EXP = Path(__file__).resolve().parent
REPO = EXP.parents[2]
RUNNER = EXP / "run_token_weighted_diagnostic.py"
SCORER = EXP / "score_token_weighted_diagnostic.py"
SPEC = EXP / "SPEC.json"
OLD_EXP = (
    REPO / "finetuning/experiments/T5_R04_READ1_TRAIN72_DENSITY_PAIRED_20260810_R01"
)
OLD_RUNNER = OLD_EXP / "run_density_paired.py"
OLD_SCORER = OLD_EXP / "score_density_paired_l6.py"
OLD_SPEC = OLD_EXP / "DENSITY_PAIRED_SPEC.json"
RUN_ROOT = REPO / "runs/T5_R04_READ1_TRAIN72_TOKEN_WEIGHTED_REDUCER_DIAGNOSTIC_R01"
EXPECTED_TICKET_KEYS = {
    "schema_version",
    "approved",
    "authorized_by",
    "decision_id",
    "decision_text_sha256",
    "source_thread_id",
    "issued_at",
    "scope",
    "run_id",
    "run_root",
    "authorized_commands",
    "spec_sha256",
    "train_input_sha256",
    "pair_map_sha256",
    "source_train_sha256",
    "parent_fail_ticket_sha256",
    "stage2_fail_ticket_sha256",
    "old_density_fail_ticket_sha256",
    "parent_l6_raw_sha256",
    "l6_request_sha256",
    "base_l6_projection_sha256",
    "reducer_preflight_receipt_sha256",
    "derived_trainer_sha256",
    "derived_vendor_tree_sha256",
    "runner_sha256",
    "scorer_sha256",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, name: str):
    module_spec = importlib.util.spec_from_file_location(name, path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def function_ast(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
    dumped = ast.dump(node, include_attributes=False)
    return (
        dumped.replace("TOKEN_WEIGHTED_DIAGNOSTIC", "DENSITY_PAIRED")
        .replace("token_weighted_diagnostic", "density_paired")
        .replace("token-weighted-reducer-diagnostic", "density-paired")
    )


def test_prep_only_single_variable_and_ticket_gate() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    old_spec = json.loads(OLD_SPEC.read_text(encoding="utf-8"))
    runner = load_module(RUNNER, "token_weighted_runner_test")
    scorer = load_module(SCORER, "token_weighted_scorer_test")
    old_runner = load_module(OLD_RUNNER, "old_density_runner_test")

    assert spec["preparation_status"] == "PREPARED_NOT_AUTHORIZED_NOT_RUN"
    assert spec["training_input"] == old_spec["training_input"]
    assert spec["training_recipe"] == old_spec["training_recipe"]
    assert spec["l6_evaluation"]["mechanical_gate"] == old_spec["l6_evaluation"]["mechanical_gate"]
    assert spec["l6_evaluation"]["semantic_gate_after_mechanical_pass"] == old_spec["l6_evaluation"]["semantic_gate_after_mechanical_pass"]
    assert spec["model_and_runtime"]["model"] == old_spec["model_and_runtime"]["model"]
    assert spec["model_and_runtime"]["model_path"] == old_spec["model_and_runtime"]["model_path"]
    assert spec["model_and_runtime"]["python"] == old_spec["model_and_runtime"]["python"]
    assert runner.runtime_config() == {
        **old_runner.runtime_config(),
        "data": str(RUN_ROOT / "data"),
        "adapter_path": str(RUN_ROOT / "adapters"),
    }
    assert runner.TRAIN == old_runner.TRAIN
    assert runner.PAIR_MAP == old_runner.PAIR_MAP
    assert runner.AUTHORIZED_COMMANDS == ["train", "infer-l6"]
    assert runner.TICKET_KEYS == EXPECTED_TICKET_KEYS
    assert runner.TRAINER_SHA == "2ff621480fb043220f8dff29d01f85f6e8f8ffe9b04fb2eebc415a837b0be1c6"
    assert runner.VENDOR_TREE_SHA == "2e77413bec6141f2a71b1fac032f5967bdfb9e2b65ba43a1b484d78d4e1f8059"
    assert runner.PREFLIGHT_RECEIPT_SHA == "4e46a23ca6da1741c1027884a2a4e9c35cd3fb21576c1f8e58fc97166a08d31c"
    load_runtime_ast = function_ast(RUNNER, "load_runtime")
    assert "attr='VENDOR'" in load_runtime_ast and "id='VENDOR'" in load_runtime_ast
    assert sha256(runner.OLD_DENSITY_FAIL_TICKET) == "b0674dcf87a355798659f893f650f397c6c329c60d34898c58778ce5f6ca7146"
    assert runner.static_check()["only_experimental_variable"] == "optimizer_window_gradient_reducer_normalization"
    assert scorer.static_check()["run_root_exists"] is False

    for name in (
        "strict_output_parse",
        "gold_and_units",
        "runtime_rows",
        "parsed_case_rows",
        "mechanical_report",
        "decision_index",
        "semantic_score",
        "run_final",
    ):
        assert function_ast(SCORER, name) == function_ast(OLD_SCORER, name), name

    assert "REAL24" not in RUNNER.read_text(encoding="utf-8")
    assert "REAL24" not in SCORER.read_text(encoding="utf-8")
    assert not RUN_ROOT.exists()
    missing = EXP / "MISSING_CZ_EXECUTION_TICKET.json"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for command in ("train", "infer-l6"):
        result = subprocess.run(
            [sys.executable, str(RUNNER), command, "--ticket", str(missing)],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert "CZ_CONTROL_WINDOW_TICKET_MISSING" in result.stderr
        assert not RUN_ROOT.exists()

    assert spec["components"]["runner_sha256"] == sha256(RUNNER)
    assert spec["components"]["scorer_sha256"] == sha256(SCORER)
    assert spec["authorization_ticket_contract"]["authorized_commands_exact"] == [
        "train",
        "infer-l6",
    ]

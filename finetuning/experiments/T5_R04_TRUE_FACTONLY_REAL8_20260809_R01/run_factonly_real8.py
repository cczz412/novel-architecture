#!/usr/bin/env python3
"""Run the zero-training TRUE-FACTONLY probe on the fixed REAL8 cases."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
RUN = REPO / "runs/T5_R04_TRUE_FACTONLY_REAL8_R01"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
EVAL = EVAL_ROOT / "READ_1_TARGET_EVAL24.jsonl"
SOURCE_INDEX = EVAL_ROOT / "REAL24_SOURCE_INDEX.jsonl"
GOLD = EVAL_ROOT / "REAL24_GOLD_24.jsonl"
ADAPTER = REPO / "runs/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/adapter_views/iter24"
LOW_RUNNER = REPO / "finetuning/experiments/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/run_read1_low_dose.py"
AB_SCRIPT = REPO / "finetuning/experiments/T5_R04_READ1_FORMAT_CONTRACT_AB8_20260809_R01/run_format_contract_ab8.py"
DECISION_SOURCES = (
    REPO / "runs/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/semantic_review/COMBINED_ADJUDICATIONS.jsonl",
    REPO / "runs/T5_R04_READ1_FORMAT_CONTRACT_AB8_R01/FORMAT_B_ADJUDICATIONS.jsonl",
    REPO / "runs/T5_R04_READ1_FORMAT_SHORT_C8_R01/FORMAT_C_ADJUDICATIONS.jsonl",
    REPO / "runs/T5_R04_READ1_TRAIN36_CONTRACT_SENTINEL_R01/semantic_review/ADJUDICATIONS_8.jsonl",
    REPO / "runs/T5_R04_C2_TRANSFER_REAL24_QUALIFICATION_R01/semantic_review/A_ADJUDICATIONS_8.jsonl",
)
REQUESTS = RUN / "FACTONLY_REQUESTS_8.jsonl"
RAW = RUN / "FACTONLY_RAW_8.jsonl"
INHERITED = RUN / "INHERITED_ADJUDICATIONS.jsonl"
PRE_METRICS = RUN / "PRE_METRICS.json"
BLIND_QUEUE = RUN / "BLIND_QUEUE.jsonl"
ADJUDICATIONS = RUN / "ADJUDICATIONS.jsonl"
FINAL_METRICS = RUN / "FINAL_METRICS.json"
RESULT_TICKET = EXP / "RESULT_TICKET.md"
CASES = ("C01", "C02", "C05", "C09", "C10", "C14", "C23", "C24")
OLD_OUTPUT_CLAUSE = (
    "每条事实必须包含 fact、status、speaker、evidence_ids；evidence_ids 选择覆盖证据的最小连续 T 编号集合。"
    "输出严格 JSON，不要解释。"
)
FACTONLY_OUTPUT_CLAUSE = (
    "每条事实只允许包含 fact；fact 必须是完整、可独立理解的事实句。事实句本身必须保留原文中的计划、否认、"
    "推测、条件、承诺等语义，不能把它们改写成已经发生。只输出一个 JSON 对象，格式为 "
    "{\"facts\":[{\"fact\":\"完整、可独立理解的事实句\"}]}；没有事实时输出 {\"facts\":[]}；"
    "不得输出 status、speaker、evidence_ids 或其他字段，也不要输出 Markdown 或解释。"
)
FACTONLY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["facts"],
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["fact"],
                "properties": {"fact": {"type": "string", "minLength": 1}},
            },
        }
    },
}
EXPECTED = {
    EVAL: "73423ace73ce60e497db6f0acf25d39bba3bfdccfc6d7a82abf9d8510d6157c0",
    GOLD: "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    ADAPTER / "adapters.safetensors": "7b01e203e45beb9562e55dff902bc0ecfd56c312f5a0a679c69813014ed14b1f",
}

# Blind decisions use the prediction SHA prefix only. A null value means the
# prediction is not equivalent to one complete Gold fact.
BLIND_DECISIONS: dict[str, str | None] = {
    # C01
    "e6b6993c13d0": None,
    "72869a16e876": None,
    "3ceea561708c": None,
    "b8b29f38fbb9": None,
    "fdc415b0c2d1": None,
    "717a560e94c4": None,
    "65e5e2805566": None,
    "5976088274ae": None,
    "783a7d99396f": "C01-F004",
    "11fc2fca6dae": None,
    "aae5524f80bb": None,
    "f17a82d82a9f": None,
    "670e93cd0f6b": "C01-F008",
    "a6d72fbc0c32": None,
    "2bb545ba0486": None,
    # C02
    "32415d6032fa": "C02-F001",
    "3eb7076c0a18": None,
    "d4d76c738230": None,
    "a4addf94200e": None,
    "72a7097d8ddf": None,
    "9232913883d6": "C02-F002",
    "5b921f135637": None,
    "32e5f340d603": "C02-F003",
    "7167115a3097": None,
    "5df91e3cf1a8": "C02-F004",
    "4cbee931ced4": None,
    "c9b9e23e444a": None,
    "67581eb934f2": None,
    "9c7ca2216cb1": None,
    "7cb99cae0908": None,
    "2ce08664692a": None,
    "15c37e20b6bd": None,
    "74d918ee5599": None,
    "1aea76076f85": None,
    "0e09fb67232b": "C02-F007",
    "35ba7476e1f9": "C02-F008",
    "d00cb00e4200": None,
    "9135602edbb7": None,
    # C05
    "55883f9a507f": None,
    "5f96a851308e": None,
    "913753bcfa07": None,
    "f6ab07e8aa49": None,
    "e79a2a56e75": None,
    "380c31133ffc": None,
    "68175d818f68": None,
    "ce5a0bdf268f": None,
    "c8f8a1ccad47": None,
    "dc68dfd77ef0": None,
    "5e48d85a4dbe": "C05-F005",
    "5d92c2b2d662": "C05-F006",
    "0443d6451281": None,
    "d32eeff3bb00": None,
    "5e6c3f248832": None,
    "4517645f1a3a": None,
    "7c6f5cb3ac46": None,
    "1fa96a283902": "C05-F008",
    "175fee667e52": None,
    "8030aed39b5f": "C05-F010",
    "a934c59110cd": None,
    "75c1028f382e": None,
    "500939f79271": None,
    "6c0411e59ebd": None,
    "902d81a6800f": None,
    "996675eb4c81": None,
    "28940e38a55a": None,
    "f45444d7f52a": "C05-F013",
    # C09
    "a622a6c2debd": None,
    "c9ac19a81e38": None,
    "20351eb9d66b": None,
    "b27cc0e225d6": None,
    "403448c6b2bc": None,
    "01616bc02d3f": "C09-F008",
    "a7fcf05b0d61": None,
    "8b7281e3f342": None,
    "1d5f11922826": None,
    "684786c511cf": "C09-F009",
    # C10
    "0c7f00abcbcc": None,
    "3df34f169c31": None,
    "d3d2bfaa2b89": "C10-F002",
    "d129138b4c42": None,
    "20c006aa3a16": None,
    "dcf3ac368815": None,
    "30ae0d796c2d": "C10-F004",
    "b92bd45dfa19": None,
    "6267dd46ee3c": None,
    "d3185d9f0020": None,
    "b50cb82312e0": "C10-F008",
    "03cc3f1b7620": None,
    "9b034c20df9a": "C10-F009",
    # C14
    "4d8501fd61f7": None,
    "54249179d02c": None,
    "37495cc36b0a": None,
    "68dcd64471b0": "C14-F002",
    "5d8d06e8b36c": None,
    "f4a3534711e5": None,
    "d865214b1429": None,
    "977e2d8451a9": None,
    "6bf2680ed79e": None,
    "594ba8e07a7d": None,
    "726060d72578": None,
    "a77f42b647cc": None,
    "81bb5ea1d52d": "C14-F011",
    # C23
    "0afdfd71d9ee": "C23-F001",
    "ee5479f5f90c": None,
    "6473af46f0a3": None,
    "1cf263bfe24b": "C23-F004",
    "74899ca77233": None,
    "c3d4b9c4ca7f": "C23-F006",
    "60d61eb58587": None,
    "58e4949c19b1": "C23-F010",
    "2cb832775138": "C23-F011",
    # C24
    "720127a7c734": None,
    "9c79af34d15b": None,
    "8c0c6a68b87b": None,
    "2b1eb9f7b21d": None,
    "621d86ccc60a": None,
    "1ca60da709ca": None,
    "77c51ce8980b": None,
    "548b8cffefa3": "C24-F005",
    "2b3c8b471ae7": None,
    "7f3f0cf6686b": None,
    "7b2c6b189c1f": None,
    "502462441a34": "C24-F007",
    "98aa2a18fd4d": "C24-F008",
    "f95d39fa9e41": None,
    "33f6f9facd19": "C24-F009",
    "f7deed10549e": None,
    "5e6205588c55": "C24-F010",
    "4520e8425011": "C24-F011",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODULE_IMPORT_FAILED:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_sources() -> None:
    for path, expected in EXPECTED.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"SOURCE_SHA_DRIFT:{path}")


def prepare() -> None:
    verify_sources()
    if RUN.exists():
        raise RuntimeError("RUN_ROOT_EXISTS_NO_RETRY")
    eval_rows = read_jsonl(EVAL)
    case_order = [row["case_id"] for row in read_jsonl(SOURCE_INDEX)]
    by_case = dict(zip(case_order, eval_rows, strict=True))
    derived = []
    for case_id in CASES:
        source = by_case[case_id]
        row = json.loads(json.dumps(source, ensure_ascii=False))
        system = row["messages"][0]["content"]
        if system.count(OLD_OUTPUT_CLAUSE) != 1:
            raise RuntimeError(f"CANONICAL_OUTPUT_CLAUSE_DRIFT:{case_id}")
        row["messages"][0]["content"] = system.replace(OLD_OUTPUT_CLAUSE, FACTONLY_OUTPUT_CLAUSE)
        if row["messages"][1] != source["messages"][1]:
            raise RuntimeError(f"USER_MESSAGE_DRIFT:{case_id}")
        derived.append({"case_id": case_id, "messages": row["messages"]})
    write_jsonl(REQUESTS, derived)
    write_json(
        RUN / "PREPARE_SUMMARY.json",
        {
            "cases": list(CASES),
            "requests_sha256": sha256(REQUESTS),
            "eval_source_sha256": sha256(EVAL),
            "gold_sha256": sha256(GOLD),
            "adapter_sha256": sha256(ADAPTER / "adapters.safetensors"),
            "user_messages_unchanged": True,
            "only_output_requirement_replaced": True,
        },
    )
    print(json.dumps({"status": "PREPARED", "requests_sha256": sha256(REQUESTS)}, ensure_ascii=False))


def infer() -> None:
    verify_sources()
    if sys.executable != "/opt/homebrew/opt/python@3.12/bin/python3.12":
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    requests = read_jsonl(REQUESTS)
    if [row["case_id"] for row in requests] != list(CASES):
        raise RuntimeError("REQUEST_ORDER_DRIFT")
    runner = load_module(LOW_RUNNER, "low_dose_runtime_for_factonly")
    mx, load, stream_generate, make_sampler = runner.configure_mlx()
    sampler = make_sampler(temp=0.0)
    model, tokenizer = load(str(runner.MODEL), adapter_path=str(ADAPTER))
    for index, item in enumerate(requests, 1):
        row = runner.generate_one(
            model,
            tokenizer,
            stream_generate,
            sampler,
            "TRUE_FACTONLY",
            item["case_id"],
            item["messages"],
            RAW,
        )
        print(
            f"FACTONLY case={item['case_id']} done={index}/8 "
            f"limit={int(row['token_limit_hit'])} repetition={int(row['repetition_detected'])}",
            flush=True,
        )
        mx.clear_cache()
    print(json.dumps({"status": "INFERENCE_COMPLETE", "raw_sha256": sha256(RAW)}, ensure_ascii=False))


def prepare_inherited() -> None:
    if INHERITED.exists():
        return
    combined: dict[tuple[str, str], dict[str, Any]] = {}
    for path in DECISION_SOURCES:
        for row in read_jsonl(path):
            key = (row["case_id"], row["prediction_fact_sha256"])
            value = {"category": row["category"], "matched_gold_fact_id": row.get("matched_gold_fact_id")}
            if key in combined and {
                "category": combined[key]["category"],
                "matched_gold_fact_id": combined[key].get("matched_gold_fact_id"),
            } != value:
                raise RuntimeError("INHERITED_DECISION_CONFLICT")
            combined[key] = row
    write_jsonl(INHERITED, list(combined.values()))


def scorer() -> Any:
    module = load_module(AB_SCRIPT, "format_ab8_scorer_for_factonly")
    module.EXP = EXP
    module.RUN = RUN
    module.RAW = RAW
    module.PRE_METRICS = PRE_METRICS
    module.BLIND_QUEUE = BLIND_QUEUE
    module.ADJUDICATIONS = ADJUDICATIONS
    module.FINAL_METRICS = FINAL_METRICS
    module.RESULT_TICKET = RESULT_TICKET
    module.LOW_DECISIONS = INHERITED
    original_loader = module.load_module

    def load_with_factonly_recovery(path: Path, name: str) -> Any:
        loaded = original_loader(path, name)
        if path != module.ROUND_SCORER:
            return loaded
        original_parse = loaded.recoverable_parse

        def recoverable_parse(raw_output: str, validator: Any) -> tuple[bool, bool, list[dict[str, Any]]]:
            json_valid, schema_valid, predicted = original_parse(raw_output, validator)
            if predicted:
                return json_valid, schema_valid, predicted
            try:
                value = json.loads(raw_output.strip())
            except json.JSONDecodeError:
                return json_valid, schema_valid, predicted
            facts = value.get("facts") if isinstance(value, dict) else None
            if not isinstance(facts, list) or not facts or not all(isinstance(item, str) for item in facts):
                return json_valid, schema_valid, predicted
            recovered = [{"fact": item} for item in facts if item]
            return True, False, recovered

        loaded.recoverable_parse = recoverable_parse
        return loaded

    module.load_module = load_with_factonly_recovery
    return module


def factonly_schema_cases() -> int:
    validator = Draft202012Validator(FACTONLY_SCHEMA)
    passed = 0
    for row in read_jsonl(RAW):
        try:
            value = json.loads(row["raw_output"].strip())
        except json.JSONDecodeError:
            continue
        passed += not list(validator.iter_errors(value))
    return passed


def score_pre() -> None:
    prepare_inherited()
    result, queue = scorer().score()
    result["factonly_schema_valid_cases"] = factonly_schema_cases()
    write_json(PRE_METRICS, result)
    write_jsonl(BLIND_QUEUE, queue)
    print(json.dumps({"status": result["status"], "semantic_pending": len(queue)}, ensure_ascii=False))


def adjudicate() -> None:
    queue = read_jsonl(BLIND_QUEUE)
    if len(queue) != len(BLIND_DECISIONS):
        raise RuntimeError("BLIND_DECISION_COUNT_MISMATCH")
    rows = []
    used = set()
    for item in queue:
        matches = [prefix for prefix in BLIND_DECISIONS if item["prediction_fact_sha256"].startswith(prefix)]
        if len(matches) != 1:
            raise RuntimeError(f"BLIND_DECISION_IDENTITY_MISMATCH:{item['prediction_fact_sha256']}")
        prefix = matches[0]
        used.add(prefix)
        matched = BLIND_DECISIONS[prefix]
        rows.append(
            {
                "case_id": item["case_id"],
                "prediction_fact": item["prediction_fact"],
                "prediction_fact_sha256": item["prediction_fact_sha256"],
                "raw_sha256": item["raw_sha256"],
                "gold_sha256": item["gold_sha256"],
                "category": "SEMANTIC_EQUIVALENT" if matched else "NOT_MATCH",
                "matched_gold_fact_id": matched,
            }
        )
    if used != set(BLIND_DECISIONS):
        raise RuntimeError("BLIND_DECISION_UNUSED_ENTRY")
    write_jsonl(ADJUDICATIONS, rows)
    print(json.dumps({"status": "BLIND_REVIEW_COMPLETE", "decisions": len(rows)}, ensure_ascii=False))


def score_final() -> None:
    result, queue = scorer().score()
    if queue or result["semantic_pending"]:
        raise RuntimeError("SEMANTIC_REVIEW_INCOMPLETE")
    b = result["b_format_contract"]
    semantic = b["semantic_recoverable"]
    schema_cases = factonly_schema_cases()
    fact_gate = (
        semantic["f1"] >= 0.451220
        and semantic["tp"] >= 37
        and b["repetition_cases"] == 0
        and b["token_limit_cases"] == 0
    )
    decision = (
        "PASS_TRUE_FACTONLY_FACT_GATE_ONLY_HARD_STOP"
        if fact_gate
        else "FAIL_TRUE_FACTONLY_NOT_TRANSFER_QUALIFIED"
    )
    final = {
        "status": decision,
        "cases": list(CASES),
        "requests_sha256": sha256(REQUESTS),
        "raw_sha256": sha256(RAW),
        "gold_sha256": sha256(GOLD),
        "adapter_sha256": sha256(ADAPTER / "adapters.safetensors"),
        "a_existing_full_field": result["a_existing_prompt"],
        "true_factonly": {
            "cases": 8,
            "gold": b["gold"],
            "predictions": b["predictions"],
            "semantic": semantic,
            "json_valid_cases": b["json_valid_cases"],
            "factonly_schema_valid_cases": schema_cases,
            "repetition_cases": b["repetition_cases"],
            "token_limit_cases": b["token_limit_cases"],
            "duplicate_predictions": b["duplicate_predictions"],
        },
        "gate": {
            "f1_at_least_0_451220": semantic["f1"] >= 0.451220,
            "tp_at_least_37": semantic["tp"] >= 37,
            "zero_repetition": b["repetition_cases"] == 0,
            "zero_token_limit": b["token_limit_cases"] == 0,
            "factonly_schema_8_of_8_preferred": schema_cases == 8,
            "fact_gate_pass": fact_gate,
        },
        "case_metrics": result["case_metrics_b"],
        "semantic_review": {
            "decisions": len(read_jsonl(ADJUDICATIONS)),
            "pending": 0,
            "adjudications_sha256": sha256(ADJUDICATIONS),
        },
        "model_calls": 8,
        "training_calls": 0,
        "api_calls": 0,
        "full24_expanded": False,
        "stage1_or_stage2_started": False,
    }
    write_json(FINAL_METRICS, final)
    ticket = f"""# TRUE-FACTONLY REAL8｜零训练结果

结论：`{decision}`。

本格只把现成 READ1 TRAIN36 iter24 的输出要求改为每项仅含 `fact`。同一8题、READ1正文、Gold、checkpoint、解码和事实语义评分口径均未改变；旧全字段 A 臂没有重跑。

- 旧全字段 A：TP=37，FP=42，FN=48，F1=0.451220。
- TRUE-FACTONLY：TP={semantic['tp']}，FP={semantic['fp']}，FN={semantic['fn']}，P={semantic['precision']:.6f}，R={semantic['recall']:.6f}，F1={semantic['f1']:.6f}。
- 输出形状：严格 JSON={b['json_valid_cases']}/8，fact-only Schema={schema_cases}/8；C02 把 `facts` 写成字符串数组，Schema 判失败，但字符串内容仍只进入可恢复语义审查，没有补字段或改写输出。
- 稳定性：复读题={b['repetition_cases']}，触顶题={b['token_limit_cases']}，重复事实={b['duplicate_predictions']}。
- 晋级门：F1达标={semantic['f1'] >= 0.451220}，TP达标={semantic['tp'] >= 37}，0复读={b['repetition_cases'] == 0}，0触顶={b['token_limit_cases'] == 0}。

本轮已硬停：没有扩到 REAL24，没有训练 Stage1，没有制作或运行 Stage2，也没有调用 API。

来源：Codex
"""
    if RESULT_TICKET.exists():
        raise RuntimeError("RESULT_TICKET_EXISTS_NO_OVERWRITE")
    RESULT_TICKET.write_text(ticket, encoding="utf-8")
    print(json.dumps({"status": decision, "metrics_sha256": sha256(FINAL_METRICS)}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "infer", "score-pre", "adjudicate", "score-final"))
    args = parser.parse_args()
    globals()[args.command.replace("-", "_")]()


if __name__ == "__main__":
    main()

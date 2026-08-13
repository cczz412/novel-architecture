#!/usr/bin/env python3
"""Run and score the eight-case zero-training format-contract probe."""

from __future__ import annotations

import argparse
from collections import Counter
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
RUN = REPO / "runs/T5_R04_READ1_FORMAT_CONTRACT_AB8_R01"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
EVAL = EVAL_ROOT / "READ_1_TARGET_EVAL24.jsonl"
SOURCE_INDEX = EVAL_ROOT / "REAL24_SOURCE_INDEX.jsonl"
GOLD = EVAL_ROOT / "REAL24_GOLD_24.jsonl"
TXX = EVAL_ROOT / "REAL24_TXX_MAP.jsonl"
SCHEMA = REPO / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
LOW_EXP = REPO / "finetuning/experiments/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01"
LOW_RUN = REPO / "runs/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01"
LOW_RUNNER = LOW_EXP / "run_read1_low_dose.py"
LOW_RAW = LOW_RUN / "READ1_LOW_DOSE_RAW.partial.jsonl"
LOW_METRICS = LOW_RUN / "scoring/FINAL_METRICS.json"
LOW_DECISIONS = LOW_RUN / "semantic_review/COMBINED_ADJUDICATIONS.jsonl"
ADAPTER = LOW_RUN / "adapters/0000024_adapters.safetensors"
ADAPTER_VIEW = LOW_RUN / "adapter_views/iter24"
ROUND_SCORER = REPO / "finetuning/experiments/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_20260809_R01/score_read_round1.py"
REQUESTS = RUN / "FORMAT_B_REQUESTS_8.jsonl"
RAW = RUN / "FORMAT_B_RAW_8.jsonl"
PRE_METRICS = RUN / "FORMAT_B_PRE_METRICS.json"
BLIND_QUEUE = RUN / "FORMAT_B_BLIND_QUEUE.jsonl"
ADJUDICATIONS = RUN / "FORMAT_B_ADJUDICATIONS.jsonl"
FINAL_METRICS = RUN / "FORMAT_AB8_FINAL_METRICS.json"
RESULT_TICKET = EXP / "RESULT_TICKET.md"
CASES = ("C01", "C02", "C05", "C09", "C10", "C14", "C23", "C24")
ALLOWED_STATUS = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}
CONTRACT = (
    "【输出合同】输出必须是且只能是一个顶层键为 facts 的 JSON 对象；facts 为数组且允许为空，"
    "每个元素只能且必须包含 fact、status、speaker、evidence_ids，fact 为非空字符串，"
    "speaker 为字符串或 null，evidence_ids 为字符串数组，status 只能取“已发生”“正在发生”"
    "“计划”“承诺”“条件”“推测”“误信”“否定”之一；不得输出其他字段、Markdown 或解释。"
)
EXPECTED = {
    EVAL: "73423ace73ce60e497db6f0acf25d39bba3bfdccfc6d7a82abf9d8510d6157c0",
    GOLD: "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    ADAPTER: "7b01e203e45beb9562e55dff902bc0ecfd56c312f5a0a679c69813014ed14b1f",
}

# Decisions are keyed by the blind queue's prediction hash prefix.  A null
# value means the prediction is not equivalent to one complete Gold fact.
BLIND_DECISIONS: dict[str, str | None] = {
    "750d3db74b30": None,
    "d814c94259e9": None,
    "291c038e3454": None,
    "68da7a121d68": None,
    "b53248cf913c": "C01-F008",
    "80332e59d85d": None,
    "9fb9ea8a92c4": None,
    "aa2eda592157": "C02-F003",
    "be40524831a8": "C02-F004",
    "dd9af0f96eb9": None,
    "c3f691aefefc": "C02-F005",
    "15d3485fea44": "C02-F007",
    "5a336b637fc6": "C02-F008",
    "062e17126265": "C02-F009",
    "b0f579482934": None,
    "0b4da9f6eb3": None,
    "b3dd6c86791f": None,
    "accf96e9b064": "C05-F005",
    "964310fb7534": "C05-F006",
    "49f1995b0ac8": None,
    "c7ec929c65f1": None,
    "71e112c9b774": None,
    "372ef6bfa309": "C05-F008",
    "1f53cae77689": "C05-F009",
    "994d5550dbe9": "C05-F010",
    "105388ac967e": "C05-F011",
    "3357e5e48f0c": "C05-F012",
    "977c3573dd77": "C05-F013",
    "db525ee9be14": None,
    "7ccacfca5f74": None,
    "7c796e492768": None,
    "c7d5f4ecfcdc": None,
    "fa356288dd51": None,
    "d4380c6609aa": "C09-F009",
    "13c57c03fed1": None,
    "532a74d13be0": None,
    "924faf9ad6c1": None,
    "a16fd68401c3": None,
    "20f62c97a192": None,
    "5eb21c526b9f": None,
    "1708d8867d6e": None,
    "6687f5bc8bcd": None,
    "ecb7c7a2f019": None,
    "6737fae7b6d1": "C14-F011",
    "c7d84f7ddda5": "C23-F001",
    "174115bde963": "C23-F003",
    "074b62be6597": "C23-F004",
    "1d7f58ef1705": "C23-F006",
    "86905a7b5a00": None,
    "9f469559fb79": None,
    "620d61574591": "C23-F011",
    "dca4f2f78b81": None,
    "12f2cddbd4ec": None,
    "febad6dda95d": None,
    "4e3fccbfbb06": "C24-F005",
    "adf1235b899a": None,
    "2a3425323760": "C24-F007",
    "22daae4cafc0": "C24-F006",
    "a08495863221": "C24-F009",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fact_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        if sha256(path) != expected:
            raise RuntimeError(f"SOURCE_SHA_DRIFT:{path}")
    if not (ADAPTER_VIEW / "adapter_config.json").is_file():
        raise RuntimeError("ADAPTER_VIEW_CONFIG_MISSING")
    adapter_link = ADAPTER_VIEW / "adapters.safetensors"
    if not adapter_link.is_file() or sha256(adapter_link) != EXPECTED[ADAPTER]:
        raise RuntimeError("ADAPTER_VIEW_WEIGHT_DRIFT")


def prepare() -> None:
    verify_sources()
    eval_rows = read_jsonl(EVAL)
    case_order = [row["case_id"] for row in read_jsonl(SOURCE_INDEX)]
    if len(eval_rows) != 24 or case_order != [f"C{index:02d}" for index in range(1, 25)]:
        raise RuntimeError("REAL24_CASE_ORDER_DRIFT")
    by_case = dict(zip(case_order, eval_rows, strict=True))
    derived = []
    for case_id in CASES:
        source = by_case[case_id]
        if len(source.get("messages", [])) != 2 or [item.get("role") for item in source["messages"]] != ["system", "user"]:
            raise RuntimeError(f"SOURCE_MESSAGE_SHAPE_DRIFT:{case_id}")
        messages = [dict(item) for item in source["messages"]]
        messages[0]["content"] += "\n" + CONTRACT
        if messages[1] != source["messages"][1] or messages[0]["content"] != source["messages"][0]["content"] + "\n" + CONTRACT:
            raise RuntimeError(f"ONLY_SYSTEM_SUFFIX_ASSERTION_FAILED:{case_id}")
        derived.append({"case_id": case_id, "messages": messages})
    write_jsonl(REQUESTS, derived)
    print(json.dumps({"status": "PREPARED", "cases": len(derived), "requests_sha256": sha256(REQUESTS)}, ensure_ascii=False))


def infer() -> None:
    verify_sources()
    if sys.executable != "/opt/homebrew/opt/python@3.12/bin/python3.12":
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    requests = read_jsonl(REQUESTS)
    if [row["case_id"] for row in requests] != list(CASES):
        raise RuntimeError("DERIVED_REQUEST_ORDER_DRIFT")
    runner = load_module(LOW_RUNNER, "low_dose_runtime_for_format_probe")
    mx, load, stream_generate, make_sampler = runner.configure_mlx()
    sampler = make_sampler(temp=0.0)
    model, tokenizer = load(str(runner.MODEL), adapter_path=str(ADAPTER_VIEW))
    observed = []
    for item in requests:
        row = runner.generate_one(
            model,
            tokenizer,
            stream_generate,
            sampler,
            "FORMAT_CONTRACT_B",
            item["case_id"],
            item["messages"],
            RAW,
        )
        observed.append(item["case_id"])
        print(
            f"FORMAT_B_PROGRESS case={item['case_id']} done={len(observed)}/8 "
            f"limit={int(row['token_limit_hit'])} repetition={int(row['repetition_detected'])}",
            flush=True,
        )
        mx.clear_cache()
    if observed != list(CASES):
        raise RuntimeError("FORMAT_B_INFERENCE_INCOMPLETE")
    print(json.dumps({"status": "INFERENCE_COMPLETE", "raw_sha256": sha256(RAW)}, ensure_ascii=False))


def gold_map(round_scorer: Any) -> dict[str, list[dict[str, Any]]]:
    return round_scorer.gold_map()


def inherited_decisions(gold_sha: str) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in read_jsonl(LOW_DECISIONS):
        if row.get("gold_sha256") != gold_sha:
            raise RuntimeError("INHERITED_GOLD_SHA_DRIFT")
        key = (row["case_id"], row["prediction_fact_sha256"])
        value = {"category": row["category"], "matched_gold_fact_id": row.get("matched_gold_fact_id")}
        if key in result and result[key] != value:
            raise RuntimeError("INHERITED_DECISION_CONFLICT")
        result[key] = value
    return result


def supplied_decisions(raw_sha: str, gold_sha: str) -> dict[tuple[str, str], dict[str, Any]]:
    if not ADJUDICATIONS.exists():
        return {}
    result = {}
    for row in read_jsonl(ADJUDICATIONS):
        if row.get("raw_sha256") != raw_sha or row.get("gold_sha256") != gold_sha:
            raise RuntimeError("FORMAT_B_ADJUDICATION_IDENTITY_DRIFT")
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if fact_sha(row.get("prediction_fact", "")) != key[1] or key in result:
            raise RuntimeError("FORMAT_B_ADJUDICATION_DUPLICATE_OR_FACT_DRIFT")
        result[key] = row
    return result


def a_baseline() -> dict[str, Any]:
    metrics = json.loads(LOW_METRICS.read_text(encoding="utf-8"))
    rows = [row for row in metrics["case_metrics"] if row["variant"] == "LORA_READ1" and row["case_id"] in CASES]
    if [row["case_id"] for row in rows] != list(CASES):
        raise RuntimeError("A_BASELINE_CASE_ORDER_DRIFT")
    tp = sum(row["semantic_tp"] for row in rows)
    predictions = sum(row["predictions"] for row in rows)
    gold_count = sum(row["gold"] for row in rows)
    return {
        "cases": 8,
        "semantic_recoverable": {
            "tp": tp,
            "fp": predictions - tp,
            "fn": gold_count - tp,
            "precision": tp / predictions,
            "recall": tp / gold_count,
            "f1": 2 * tp / (predictions + gold_count),
        },
        "predictions": predictions,
        "gold": gold_count,
        "json_valid_cases": sum(row["json_valid"] for row in rows),
        "schema_valid_cases": sum(row["schema_valid"] for row in rows),
        "status_correct": sum(row["status_correct"] for row in rows),
        "speaker_correct": sum(row["speaker_correct"] for row in rows),
        "evidence_correct": sum(row["evidence_correct"] for row in rows),
        "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in rows),
        "repetition_cases": sum(row["repetition_detected"] for row in rows),
        "token_limit_cases": sum(row["token_limit_hit"] for row in rows),
        "duplicate_predictions": sum(row["duplicate_predictions"] for row in rows),
    }


def score() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    verify_sources()
    raw_rows = read_jsonl(RAW)
    if [row.get("case_id") for row in raw_rows] != list(CASES):
        raise RuntimeError("FORMAT_B_RAW_CASE_ORDER_DRIFT")
    round_scorer = load_module(ROUND_SCORER, "round1_scorer_for_format_ab8")
    wo = round_scorer.load_wo()
    gold = gold_map(round_scorer)
    raw_sha = sha256(RAW)
    gold_sha = sha256(GOLD)
    inherited = inherited_decisions(gold_sha)
    supplied = supplied_decisions(raw_sha, gold_sha)
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    valid_ids = {row["case_id"]: {unit["id"] for unit in row["target_units"]} for row in read_jsonl(TXX)}
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    case_metrics = []
    for row in raw_rows:
        case_id = row["case_id"]
        expected = gold[case_id]
        json_valid, schema_valid, predicted = round_scorer.recoverable_parse(row["raw_output"], validator)
        pairs, unmatched = wo.match(expected, predicted, normalized=True)
        used_gold = {gold_index for _, gold_index in pairs}
        for prediction_index in unmatched:
            text = predicted[prediction_index].get("fact", "")
            key = (case_id, fact_sha(text))
            decision = supplied.get(key) or inherited.get(key)
            if decision is None:
                pending[key] = {
                    "case_id": case_id,
                    "prediction_fact": text,
                    "prediction_fact_sha256": key[1],
                    "raw_sha256": raw_sha,
                    "gold_sha256": gold_sha,
                    "candidate_gold_facts": [{"fact_id": item["fact_id"], "fact": item["fact"]} for item in expected],
                }
                continue
            if decision["category"] != "SEMANTIC_EQUIVALENT":
                continue
            matched = decision.get("matched_gold_fact_id")
            gold_index = next((index for index, item in enumerate(expected) if item["fact_id"] == matched), None)
            if gold_index is None:
                raise RuntimeError(f"ADJUDICATION_GOLD_ID_INVALID:{case_id}:{matched}")
            if gold_index not in used_gold:
                pairs.append((prediction_index, gold_index))
                used_gold.add(gold_index)
        status_ok = speaker_ok = evidence_ok = 0
        for prediction_index, gold_index in pairs:
            prediction = predicted[prediction_index]
            target = expected[gold_index]
            status_ok += prediction.get("status") == target["status"]
            speaker_ok += prediction.get("speaker") == target["speaker"]
            evidence_ok += prediction.get("evidence_ids") == target["evidence_ids"]
        legal_status = sum(item.get("status") in ALLOWED_STATUS for item in predicted)
        speaker_type = sum(item.get("speaker") is None or isinstance(item.get("speaker"), str) for item in predicted)
        evidence_type = sum(
            isinstance(item.get("evidence_ids"), list)
            and all(isinstance(evidence_id, str) for evidence_id in item["evidence_ids"])
            for item in predicted
        )
        illegal_evidence = sum(
            not isinstance(item.get("evidence_ids"), list)
            or any(not isinstance(evidence_id, str) or evidence_id not in valid_ids[case_id] for evidence_id in item.get("evidence_ids", []))
            for item in predicted
        )
        duplicates = sum(count - 1 for count in Counter(item.get("fact") for item in predicted).values() if count > 1)
        case_metrics.append(
            {
                "case_id": case_id,
                "gold": len(expected),
                "predictions": len(predicted),
                "semantic_tp": len(pairs),
                "json_valid": json_valid,
                "schema_valid": schema_valid,
                "legal_status_predictions": legal_status,
                "speaker_type_valid_predictions": speaker_type,
                "evidence_type_valid_predictions": evidence_type,
                "status_correct": status_ok,
                "speaker_correct": speaker_ok,
                "evidence_correct": evidence_ok,
                "illegal_evidence_predictions": illegal_evidence,
                "duplicate_predictions": duplicates,
                "repetition_detected": bool(row.get("repetition_detected")),
                "token_limit_hit": bool(row.get("token_limit_hit")),
            }
        )
    tp = sum(row["semantic_tp"] for row in case_metrics)
    predictions = sum(row["predictions"] for row in case_metrics)
    gold_count = sum(row["gold"] for row in case_metrics)
    b = {
        "cases": 8,
        "semantic_recoverable": {
            "tp": tp,
            "fp": predictions - tp,
            "fn": gold_count - tp,
            "precision": tp / predictions if predictions else 0.0,
            "recall": tp / gold_count,
            "f1": 2 * tp / (predictions + gold_count) if predictions else 0.0,
        },
        "predictions": predictions,
        "gold": gold_count,
        "json_valid_cases": sum(row["json_valid"] for row in case_metrics),
        "schema_valid_cases": sum(row["schema_valid"] for row in case_metrics),
        "legal_status_predictions": sum(row["legal_status_predictions"] for row in case_metrics),
        "speaker_type_valid_predictions": sum(row["speaker_type_valid_predictions"] for row in case_metrics),
        "evidence_type_valid_predictions": sum(row["evidence_type_valid_predictions"] for row in case_metrics),
        "status_correct": sum(row["status_correct"] for row in case_metrics),
        "speaker_correct": sum(row["speaker_correct"] for row in case_metrics),
        "evidence_correct": sum(row["evidence_correct"] for row in case_metrics),
        "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in case_metrics),
        "repetition_cases": sum(row["repetition_detected"] for row in case_metrics),
        "token_limit_cases": sum(row["token_limit_hit"] for row in case_metrics),
        "duplicate_predictions": sum(row["duplicate_predictions"] for row in case_metrics),
    }
    gate = None
    if not pending:
        gate_1 = (
            b["json_valid_cases"] == 8
            and b["schema_valid_cases"] == 8
            and b["illegal_evidence_predictions"] == 0
            and b["repetition_cases"] == 0
            and b["token_limit_cases"] == 0
        )
        gate_2 = b["semantic_recoverable"]["f1"] >= 0.431 and tp >= 35
        gate_3 = b["status_correct"] > 0 and b["status_correct"] * 2 >= tp
        gate = {
            "format_stability_gate": gate_1,
            "semantic_retention_gate": gate_2,
            "status_accuracy_gate": gate_3,
            "all_pass": gate_1 and gate_2 and gate_3,
        }
    result = {
        "status": "PENDING_BLIND_SEMANTIC_REVIEW" if pending else "PASS_FINAL_SCORING",
        "raw_sha256": raw_sha,
        "gold_sha256": gold_sha,
        "semantic_pending": len(pending),
        "a_existing_prompt": a_baseline(),
        "b_format_contract": b,
        "gate": gate,
        "case_metrics_b": case_metrics,
        "model_calls_this_probe": 8,
        "training_calls": 0,
        "api_calls": 0,
    }
    return result, list(pending.values())


def score_pre() -> None:
    result, queue = score()
    if ADJUDICATIONS.exists():
        raise RuntimeError("ADJUDICATIONS_ALREADY_EXIST_USE_SCORE_FINAL")
    write_json(PRE_METRICS, result)
    write_jsonl(BLIND_QUEUE, queue)
    print(json.dumps({"status": result["status"], "semantic_pending": len(queue)}, ensure_ascii=False))


def adjudicate() -> None:
    queue = read_jsonl(BLIND_QUEUE)
    if len(queue) != len(BLIND_DECISIONS):
        raise RuntimeError("BLIND_DECISION_COUNT_MISMATCH")
    rows = []
    seen = set()
    for item in queue:
        matches = [prefix for prefix in BLIND_DECISIONS if item["prediction_fact_sha256"].startswith(prefix)]
        if len(matches) != 1:
            raise RuntimeError(f"BLIND_DECISION_IDENTITY_MISMATCH:{item['prediction_fact_sha256']}")
        prefix = matches[0]
        seen.add(prefix)
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
    if seen != set(BLIND_DECISIONS):
        raise RuntimeError("BLIND_DECISION_UNUSED_ENTRY")
    write_jsonl(ADJUDICATIONS, rows)
    print(json.dumps({"status": "BLIND_REVIEW_COMPLETE", "decisions": len(rows)}, ensure_ascii=False))


def score_final() -> None:
    if not ADJUDICATIONS.is_file():
        raise RuntimeError("ADJUDICATIONS_MISSING")
    result, queue = score()
    if queue or result["semantic_pending"]:
        raise RuntimeError("SEMANTIC_REVIEW_INCOMPLETE")
    write_json(FINAL_METRICS, result)
    gate = result["gate"]
    decision = "PASS_EXPAND_TO_FULL24" if gate["all_pass"] else "FAIL_STOP_AT_8"
    b = result["b_format_contract"]
    semantic = b["semantic_recoverable"]
    ticket = f"""# READ1 iter24 零训练格式合同 A/B｜8题结果

结论：`{decision}`。

本轮只在 B 臂 system 末尾追加一行结构合同；checkpoint、8道 READ1 题面正文、Gold、解码、停止条件和评分口径均不变。没有训练，也没有调用 API。

- A 臂旧提示：TP={result['a_existing_prompt']['semantic_recoverable']['tp']}，预测={result['a_existing_prompt']['predictions']}，Gold={result['a_existing_prompt']['gold']}，F1={result['a_existing_prompt']['semantic_recoverable']['f1']:.6f}，完整 Schema={result['a_existing_prompt']['schema_valid_cases']}/8。
- B 臂结构合同：TP={semantic['tp']}，FP={semantic['fp']}，FN={semantic['fn']}，P={semantic['precision']:.6f}，R={semantic['recall']:.6f}，F1={semantic['f1']:.6f}。
- B 臂格式：严格 JSON={b['json_valid_cases']}/8，完整 Schema={b['schema_valid_cases']}/8，非法证据={b['illegal_evidence_predictions']}，复读题={b['repetition_cases']}，触顶题={b['token_limit_cases']}，重复事实={b['duplicate_predictions']}。
- B 臂命中事实字段：status={b['status_correct']}/{semantic['tp']}，speaker={b['speaker_correct']}/{semantic['tp']}，evidence={b['evidence_correct']}/{semantic['tp']}。
- 三道门：格式稳定={gate['format_stability_gate']}；事实保留={gate['semantic_retention_gate']}；status 过半={gate['status_accuracy_gate']}。

若结论为 `FAIL_STOP_AT_8`，本轮在8题硬停，不补完整24题，不改 Prompt，不加第三臂，不训练。

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
    if args.command == "prepare":
        prepare()
    elif args.command == "infer":
        infer()
    elif args.command == "score-pre":
        score_pre()
    elif args.command == "adjudicate":
        adjudicate()
    else:
        score_final()


if __name__ == "__main__":
    main()

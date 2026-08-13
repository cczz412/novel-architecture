#!/usr/bin/env python3
"""Evaluate the frozen M1 C2 update-72 adapter on REAL24 READ1."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
RUN = REPO / "runs/T5_R04_C2_TRANSFER_REAL24_QUALIFICATION_R01"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
EVAL = EVAL_ROOT / "READ_1_TARGET_EVAL24.jsonl"
SOURCE_INDEX = EVAL_ROOT / "REAL24_SOURCE_INDEX.jsonl"
GOLD = EVAL_ROOT / "REAL24_GOLD_24.jsonl"
ADAPTER = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01/eval_adapters/c2_full/update_72"
LOW_EXP = REPO / "finetuning/experiments/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01"
LOW_RUNNER = LOW_EXP / "run_read1_low_dose.py"
LOW_DECISIONS = REPO / "runs/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/semantic_review/COMBINED_ADJUDICATIONS.jsonl"
AB_SCRIPT = REPO / "finetuning/experiments/T5_R04_READ1_FORMAT_CONTRACT_AB8_20260809_R01/run_format_contract_ab8.py"
AB_DECISIONS = REPO / "runs/T5_R04_READ1_FORMAT_CONTRACT_AB8_R01/FORMAT_B_ADJUDICATIONS.jsonl"
C_DECISIONS = REPO / "runs/T5_R04_READ1_FORMAT_SHORT_C8_R01/FORMAT_C_ADJUDICATIONS.jsonl"
CONTRACT_TRAIN_DECISIONS = REPO / "runs/T5_R04_READ1_TRAIN36_CONTRACT_SENTINEL_R01/semantic_review/ADJUDICATIONS_8.jsonl"
RAW_A8 = RUN / "C2_TRANSFER_A_RAW_8.jsonl"
INHERITED = RUN / "scoring/INHERITED_ADJUDICATIONS.jsonl"
PRE_METRICS_A8 = RUN / "scoring/A_PRE_METRICS_8.json"
BLIND_QUEUE_A8 = RUN / "scoring/A_BLIND_QUEUE_8.jsonl"
ADJUDICATIONS_A8 = RUN / "semantic_review/A_ADJUDICATIONS_8.jsonl"
FINAL_METRICS_A8 = RUN / "scoring/A_FINAL_METRICS_8.json"
RESULT_TICKET = EXP / "RESULT_TICKET.md"
CASES = ("C01", "C02", "C05", "C09", "C10", "C14", "C23", "C24")
EXPECTED = {
    EVAL: "73423ace73ce60e497db6f0acf25d39bba3bfdccfc6d7a82abf9d8510d6157c0",
    GOLD: "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    ADAPTER / "adapters.safetensors": "321d96c10f00389e557efbeb2d8e3dc1344071cc3cd663b51b8a8c2bd38ea5f9",
    ADAPTER / "adapter_config.json": "72df68a7d01b8feae8f92cc0e4f69c832d9ad71886b4f8ea2896a7436d73031e",
}

# Blind semantic decisions for C2 transfer predictions not already covered by
# identical earlier fact text. A null value means no equivalence to one full
# Gold fact.
BLIND_DECISIONS: dict[str, str | None] = {
    "29004c6426d8": "C01-F001",
    "3a6c54ae751a": None,
    "93be0b50fc6a": None,
    "20e71a769b47": "C01-F005",
    "d60f104ad029": None,
    "9bb5f152cde2": None,
    "31b4c25d7298": None,
    "862750031b1b": None,
    "950a0e5ca3cf": "C02-F002",
    "76cfa867c03c": "C02-F003",
    "79facf34b6ba": "C02-F003",
    "1e9d132ad8c7": "C02-F004",
    "85f555c99433": None,
    "63e3dda09909": None,
    "06b4dcc86740": "C02-F005",
    "0d15529648f3": "C02-F007",
    "6d9bce2b93e5": "C02-F008",
    "1e4e7855cda4": "C02-F009",
    "d99a416e10f8": None,
    "61a9b3e38f29": None,
    "1ebb7cb825fc": None,
    "2982a4326eed": None,
    "56316a4711fb": None,
    "62d85b084030": None,
    "3e55fec94766": None,
    "939d50074a59": "C05-F005",
    "810326ae505b": None,
    "979647bd493a": "C05-F006",
    "28605c05b45d": None,
    "c32061c0625e": None,
    "cd7348e056b6": None,
    "412f3a9bdcfd": None,
    "fc2a6086ca7f": None,
    "9ef6a3e14f7f": None,
    "def19bdb895b": "C05-F008",
    "9148a73b622f": "C05-F010",
    "2184e8dcbe43": None,
    "696e5bd11476": "C05-F011",
    "4cf3398191c8": None,
    "b8553d4a8187": "C05-F012",
    "c79a799ea0a7": None,
    "053b71a0f239": "C05-F013",
    "89d64684e85c": "C09-F003",
    "7be1695be8fc": None,
    "0d534756c16e": None,
    "d7b75ba5fc71": None,
    "4e8e8688ea7b": None,
    "16142ce36667": "C09-F009",
    "e2454709a93d": "C09-F008",
    "258a55d7457b": None,
    "0cc8bd669055": "C09-F006",
    "ba915c21a60a": "C09-F009",
    "0ee23ebb3a57": None,
    "ed7b33acc917": None,
    "b35c35185401": "C10-F004",
    "d5fae0d22077": None,
    "3c9d188f1178": None,
    "d85cddad2eff": None,
    "5fcb7c4e7826": None,
    "9f40f5ac5c59": None,
    "9705aef0b8f5": None,
    "4d2d92e392d7": None,
    "d5dca8686d0a": "C23-F003",
    "83ec1a37a354": "C23-F006",
    "d33bef83b144": "C23-F007",
    "d66e0a8c4e83": "C23-F010",
    "28f7d31e1d33": "C23-F011",
    "e25c4983fd7d": "C24-F001",
    "bd7d1b881e00": None,
    "bac4591cc6fa": None,
    "a6366efb6d4b": None,
    "9c6b21d1a425": None,
    "726e312b1d78": "C24-F005",
    "9f7e2a1ef61a": None,
    "49d1f8c0deb2": "C24-F007",
    "2aa1656f599d": "C24-F008",
    "149280290cb9": None,
    "a7d889b62625": "C24-F009",
    "d7a8e28cfd15": None,
    "0526475c0596": None,
    "b40ecc0b0208": "C24-F011",
    "eca75e46f65e": None,
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
    config = json.loads((ADAPTER / "adapter_config.json").read_text(encoding="utf-8"))
    if (
        config.get("model") != "/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f"
        or config.get("num_layers") != 16
        or config.get("lora_parameters", {}).get("rank") != 32
    ):
        raise RuntimeError("C2_ADAPTER_IDENTITY_DRIFT")


def prepare() -> None:
    verify_sources()
    if RUN.exists():
        raise RuntimeError("RUN_ROOT_EXISTS_NO_RETRY")
    RUN.mkdir(parents=True)
    write_json(
        RUN / "SOURCE_IDENTITY.json",
        {
            "adapter_path": str(ADAPTER),
            "adapter_sha256": sha256(ADAPTER / "adapters.safetensors"),
            "adapter_config_sha256": sha256(ADAPTER / "adapter_config.json"),
            "eval_sha256": sha256(EVAL),
            "gold_sha256": sha256(GOLD),
            "cases": list(CASES),
            "training_calls": 0,
            "api_calls": 0,
        },
    )
    print(json.dumps({"status": "PREPARED", "adapter_sha256": EXPECTED[ADAPTER / "adapters.safetensors"]}, ensure_ascii=False))


def infer_a8() -> None:
    verify_sources()
    if sys.executable != "/opt/homebrew/opt/python@3.12/bin/python3.12":
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    eval_rows = read_jsonl(EVAL)
    case_order = [row["case_id"] for row in read_jsonl(SOURCE_INDEX)]
    by_case = dict(zip(case_order, eval_rows, strict=True))
    runner = load_module(LOW_RUNNER, "low_dose_runtime_for_c2_transfer")
    mx, load, stream_generate, make_sampler = runner.configure_mlx()
    sampler = make_sampler(temp=0.0)
    model, tokenizer = load(str(runner.MODEL), adapter_path=str(ADAPTER))
    for index, case_id in enumerate(CASES, 1):
        messages = by_case[case_id]["messages"]
        if len(messages) != 2 or [row.get("role") for row in messages] != ["system", "user"]:
            raise RuntimeError(f"EVAL_MESSAGE_SHAPE_DRIFT:{case_id}")
        row = runner.generate_one(
            model,
            tokenizer,
            stream_generate,
            sampler,
            "C2_TRANSFER_A",
            case_id,
            messages,
            RAW_A8,
        )
        print(
            f"C2_TRANSFER_A case={case_id} done={index}/8 "
            f"limit={int(row['token_limit_hit'])} repetition={int(row['repetition_detected'])}",
            flush=True,
        )
        mx.clear_cache()
    print(json.dumps({"status": "A_INFERENCE8_COMPLETE", "raw_sha256": sha256(RAW_A8)}, ensure_ascii=False))


def prepare_inherited() -> None:
    if INHERITED.exists():
        return
    combined: dict[tuple[str, str], dict[str, Any]] = {}
    for path in (LOW_DECISIONS, AB_DECISIONS, C_DECISIONS, CONTRACT_TRAIN_DECISIONS):
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
    module = load_module(AB_SCRIPT, "format_ab8_scorer_for_c2_transfer")
    module.EXP = EXP
    module.RUN = RUN
    module.RAW = RAW_A8
    module.PRE_METRICS = PRE_METRICS_A8
    module.BLIND_QUEUE = BLIND_QUEUE_A8
    module.ADJUDICATIONS = ADJUDICATIONS_A8
    module.FINAL_METRICS = FINAL_METRICS_A8
    module.RESULT_TICKET = RESULT_TICKET
    module.LOW_DECISIONS = INHERITED
    return module


def score_pre_a8() -> None:
    prepare_inherited()
    result, queue = scorer().score()
    write_json(PRE_METRICS_A8, result)
    write_jsonl(BLIND_QUEUE_A8, queue)
    print(json.dumps({"status": result["status"], "semantic_pending": len(queue)}, ensure_ascii=False))


def adjudicate_a8() -> None:
    queue = read_jsonl(BLIND_QUEUE_A8)
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
    write_jsonl(ADJUDICATIONS_A8, rows)
    print(json.dumps({"status": "BLIND_REVIEW_A_COMPLETE", "decisions": len(rows)}, ensure_ascii=False))


def score_final_a8() -> None:
    if not ADJUDICATIONS_A8.is_file():
        raise RuntimeError("A_ADJUDICATIONS_MISSING")
    result, queue = scorer().score()
    if queue or result["semantic_pending"]:
        raise RuntimeError("A_SEMANTIC_REVIEW_INCOMPLETE")
    candidate = result["b_format_contract"]
    semantic = candidate["semantic_recoverable"]
    stability_gate = (
        candidate["repetition_cases"] == 0
        and candidate["token_limit_cases"] == 0
        and candidate["illegal_evidence_predictions"] == 0
    )
    fact_gate = semantic["tp"] >= 37 and semantic["f1"] >= 0.451220
    if not stability_gate or not fact_gate:
        decision = "FAIL_STOP_C2_TRANSFER"
    elif candidate["schema_valid_cases"] == 8:
        decision = "PASS_EXPAND_A_TO_FULL24"
    else:
        decision = "PASS_ALLOW_FORMAT_B8"
    final = {
        **result,
        "c2_transfer_a_gate": {
            "stability_gate": stability_gate,
            "fact_gate": fact_gate,
            "schema_8_of_8": candidate["schema_valid_cases"] == 8,
            "decision": decision,
        },
        "training_calls": 0,
        "api_calls": 0,
    }
    write_json(FINAL_METRICS_A8, final)
    ticket = f"""# 旧 M1 C2_FULL update72｜REAL24 READ1 转移资格

结论：`{decision}`。

本轮只让冻结 C2 update72 回答8道原始 READ1 题面；没有追加格式合同，没有训练，也没有复制或改写 adapter。

- adapter SHA：`{sha256(ADAPTER / 'adapters.safetensors')}`。
- 事实：TP={semantic['tp']}，FP={semantic['fp']}，FN={semantic['fn']}，P={semantic['precision']:.6f}，R={semantic['recall']:.6f}，F1={semantic['f1']:.6f}。
- 格式：严格 JSON={candidate['json_valid_cases']}/8，完整 Schema={candidate['schema_valid_cases']}/8，非法证据={candidate['illegal_evidence_predictions']}，复读题={candidate['repetition_cases']}，触顶题={candidate['token_limit_cases']}，重复事实={candidate['duplicate_predictions']}。
- 命中字段：status={candidate['status_correct']}/{semantic['tp']}，speaker={candidate['speaker_correct']}/{semantic['tp']}，evidence={candidate['evidence_correct']}/{semantic['tp']}。
- 资格门：稳定性={stability_gate}；事实不低于当前最佳 low-dose A={fact_gate}；Schema 8/8={candidate['schema_valid_cases'] == 8}。

若结论为 `FAIL_STOP_C2_TRANSFER`，旧 C2 转移路线在8题淘汰：不跑格式 B，不追 D/E/SMALL_HALO，也不扩完整24题。

来源：Codex
"""
    if RESULT_TICKET.exists():
        raise RuntimeError("RESULT_TICKET_EXISTS_NO_OVERWRITE")
    RESULT_TICKET.write_text(ticket, encoding="utf-8")
    print(json.dumps({"status": decision, "metrics_sha256": sha256(FINAL_METRICS_A8)}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("prepare", "infer-a8", "score-pre-a8", "adjudicate-a8", "score-final-a8"),
    )
    args = parser.parse_args()
    globals()[args.command.replace("-", "_")]()


if __name__ == "__main__":
    main()

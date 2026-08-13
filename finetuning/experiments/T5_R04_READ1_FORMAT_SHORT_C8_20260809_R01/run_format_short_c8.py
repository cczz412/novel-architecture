#!/usr/bin/env python3
"""Run and score the final eight-case short format-prompt probe."""

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
RUN = REPO / "runs/T5_R04_READ1_FORMAT_SHORT_C8_R01"
AB_EXP = REPO / "finetuning/experiments/T5_R04_READ1_FORMAT_CONTRACT_AB8_20260809_R01"
AB_SCRIPT = AB_EXP / "run_format_contract_ab8.py"
AB_METRICS = REPO / "runs/T5_R04_READ1_FORMAT_CONTRACT_AB8_R01/FORMAT_AB8_FINAL_METRICS.json"
AB_ADJUDICATIONS = REPO / "runs/T5_R04_READ1_FORMAT_CONTRACT_AB8_R01/FORMAT_B_ADJUDICATIONS.jsonl"
REQUESTS = RUN / "FORMAT_C_REQUESTS_8.jsonl"
RAW = RUN / "FORMAT_C_RAW_8.jsonl"
INHERITED = RUN / "FORMAT_C_INHERITED_ADJUDICATIONS.jsonl"
PRE_METRICS = RUN / "FORMAT_C_PRE_METRICS.json"
BLIND_QUEUE = RUN / "FORMAT_C_BLIND_QUEUE.jsonl"
ADJUDICATIONS = RUN / "FORMAT_C_ADJUDICATIONS.jsonl"
FINAL_METRICS = RUN / "FORMAT_ABC8_FINAL_METRICS.json"
RESULT_TICKET = EXP / "RESULT_TICKET.md"
CONTRACT = (
    "【输出格式】只输出一个 JSON 对象，格式为 {\"facts\":[{\"fact\":\"…\",\"status\":\"已发生\","
    "\"speaker\":null,\"evidence_ids\":[\"T01\"]}]}；status 仅限：已发生、正在发生、计划、承诺、条件、"
    "推测、误信、否定；没有事实时输出 {\"facts\":[]}；不要输出其他内容。"
)

# Blind semantic decisions for the final short-format probe.  A null value
# means the prediction is not equivalent to one complete Gold fact.
BLIND_DECISIONS: dict[str, str | None] = {
    "bf947ccbe8d6": None,
    "bee735c3369d": None,
    "449be2eef043": None,
    "574fa5cfcfbb": None,
    "f80d2f3f82a5": None,
    "59d9ed749819": "C02-F001",
    "56a36c3dc0a4": None,
    "5e0ed134a3f4": "C02-F002",
    "b6d5c98c8479": "C02-F003",
    "045e95152658": "C02-F004",
    "b3bdf28c7050": None,
    "0cb0c271405e": "C02-F005",
    "f282ffdf9055": None,
    "a390c1d1d448": "C02-F008",
    "39c67505aaa7": "C02-F009",
    "68fbba44ced2": None,
    "6946f55d3174": None,
    "16c863648107": None,
    "f56db85c2b9a": None,
    "9fc7058908ba": None,
    "cc4480f62886": None,
    "38283eae74c6": None,
    "b3183df15199": "C05-F005",
    "1cd92245a959": "C05-F006",
    "e7a77ad4c329": None,
    "a35f06c99bd9": None,
    "49215b886d79": None,
    "f5cea95dcc35": "C05-F008",
    "21fdef62f8cf": "C05-F009",
    "18461c5bb845": "C05-F010",
    "fc52d56e15bf": None,
    "879e74fa6598": "C05-F011",
    "6de7b6ef80d7": "C05-F012",
    "5b275562eac4": "C05-F013",
    "9b106a31fea1": None,
    "427ef7bfea1a": None,
    "88f214762ae5": None,
    "de59380e1892": None,
    "d9447983b8d6": None,
    "b5ea7ceda5f0": None,
    "440e4d02dcb3": None,
    "50313be21491": "C09-F009",
    "f74d7de92bcb": None,
    "b9f85ceb0442": None,
    "8d89fe3c7033": None,
    "7352b8d2cedc": "C10-F004",
    "802a7ab03b54": None,
    "5957768a58fc": None,
    "69376fa8c0be": None,
    "73b000e927c0": None,
    "a485d5ad7d20": "C14-F009",
    "76e05cb509a1": "C14-F008",
    "be43ea69c3f3": "C14-F010",
    "c415b35047f6": "C23-F001",
    "54c117abea98": "C23-F003",
    "5d784a8ef345": "C23-F006",
    "3467b2c48210": None,
    "0dcf59f6fc3b": None,
    "b3dea88b47e5": "C23-F011",
    "096ea51d629e": None,
    "5c29137e8503": None,
    "494a583a83f5": None,
    "9b54cc0b78af": None,
    "deb0498d3a99": None,
    "dd149cdb85bc": "C24-F010",
    "f7f411af240c": "C24-F011",
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


def load_ab() -> Any:
    spec = importlib.util.spec_from_file_location("format_ab8_for_short_c8", AB_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("AB8_SCRIPT_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EXP = EXP
    module.RUN = RUN
    module.REQUESTS = REQUESTS
    module.RAW = RAW
    module.PRE_METRICS = PRE_METRICS
    module.BLIND_QUEUE = BLIND_QUEUE
    module.ADJUDICATIONS = ADJUDICATIONS
    module.FINAL_METRICS = FINAL_METRICS
    module.RESULT_TICKET = RESULT_TICKET
    module.CONTRACT = CONTRACT
    module.LOW_DECISIONS = INHERITED
    return module


def prepare() -> None:
    ab = load_ab()
    ab.prepare()
    combined: dict[tuple[str, str], dict[str, Any]] = {}
    for path in (ab.LOW_RUN / "semantic_review/COMBINED_ADJUDICATIONS.jsonl", AB_ADJUDICATIONS):
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
    print(json.dumps({"status": "PREPARED_C", "requests_sha256": sha256(REQUESTS)}, ensure_ascii=False))


def infer() -> None:
    ab = load_ab()
    ab.verify_sources()
    if sys.executable != "/opt/homebrew/opt/python@3.12/bin/python3.12":
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    requests = read_jsonl(REQUESTS)
    if [row["case_id"] for row in requests] != list(ab.CASES):
        raise RuntimeError("FORMAT_C_REQUEST_ORDER_DRIFT")
    runner = ab.load_module(ab.LOW_RUNNER, "low_dose_runtime_for_format_c8")
    mx, load, stream_generate, make_sampler = runner.configure_mlx()
    sampler = make_sampler(temp=0.0)
    model, tokenizer = load(str(runner.MODEL), adapter_path=str(ab.ADAPTER_VIEW))
    for index, item in enumerate(requests, 1):
        row = runner.generate_one(
            model,
            tokenizer,
            stream_generate,
            sampler,
            "FORMAT_SHORT_C",
            item["case_id"],
            item["messages"],
            RAW,
        )
        print(
            f"FORMAT_C_PROGRESS case={item['case_id']} done={index}/8 "
            f"limit={int(row['token_limit_hit'])} repetition={int(row['repetition_detected'])}",
            flush=True,
        )
        mx.clear_cache()
    print(json.dumps({"status": "INFERENCE_COMPLETE_C", "raw_sha256": sha256(RAW)}, ensure_ascii=False))


def score_pre() -> None:
    ab = load_ab()
    result, queue = ab.score()
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
    print(json.dumps({"status": "BLIND_REVIEW_COMPLETE_C", "decisions": len(rows)}, ensure_ascii=False))


def score_final() -> None:
    ab = load_ab()
    result, queue = ab.score()
    if queue or result["semantic_pending"]:
        raise RuntimeError("SEMANTIC_REVIEW_INCOMPLETE")
    old = json.loads(AB_METRICS.read_text(encoding="utf-8"))
    c = result["b_format_contract"]
    gate = result["gate"]
    final = {
        "status": "PASS_FINAL_SCORING",
        "semantic_pending": 0,
        "a_existing_prompt": old["a_existing_prompt"],
        "b_full_contract": old["b_format_contract"],
        "c_short_format": c,
        "c_gate": gate,
        "raw_sha256": result["raw_sha256"],
        "gold_sha256": result["gold_sha256"],
        "model_calls_this_probe": 8,
        "training_calls": 0,
        "api_calls": 0,
        "case_metrics_c": result["case_metrics_b"],
    }
    write_json(FINAL_METRICS, final)
    decision = "PASS_EXPAND_TO_FULL24" if gate["all_pass"] else "FAIL_STOP_PROMPT_ONLY_ROUTE"
    semantic = c["semantic_recoverable"]
    ticket = f"""# READ1 iter24 短格式 Prompt C｜8题结果

结论：`{decision}`。

C 只在原 system 末尾追加一行短格式说明；checkpoint、8道 READ1 正文、Gold、解码、停止条件和评分口径都没有改变。没有训练，也没有调用 API。

- A 旧提示：F1={old['a_existing_prompt']['semantic_recoverable']['f1']:.6f}，完整 Schema={old['a_existing_prompt']['schema_valid_cases']}/8。
- B 完整合同：F1={old['b_format_contract']['semantic_recoverable']['f1']:.6f}，完整 Schema={old['b_format_contract']['schema_valid_cases']}/8。
- C 短格式：TP={semantic['tp']}，FP={semantic['fp']}，FN={semantic['fn']}，P={semantic['precision']:.6f}，R={semantic['recall']:.6f}，F1={semantic['f1']:.6f}。
- C 格式：严格 JSON={c['json_valid_cases']}/8，完整 Schema={c['schema_valid_cases']}/8，非法证据={c['illegal_evidence_predictions']}，复读题={c['repetition_cases']}，触顶题={c['token_limit_cases']}，重复事实={c['duplicate_predictions']}。
- C 字段：合法 status={c['legal_status_predictions']}/{c['predictions']}；命中事实 status={c['status_correct']}/{semantic['tp']}，speaker={c['speaker_correct']}/{semantic['tp']}，evidence={c['evidence_correct']}/{semantic['tp']}。
- 三道门：格式稳定={gate['format_stability_gate']}；事实保留={gate['semantic_retention_gate']}；status 过半={gate['status_accuracy_gate']}。

若结论为 `FAIL_STOP_PROMPT_ONLY_ROUTE`，本轮在8题硬停，不补完整24题；Prompt-only 路线停止，不再造 D/E 措辞。

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

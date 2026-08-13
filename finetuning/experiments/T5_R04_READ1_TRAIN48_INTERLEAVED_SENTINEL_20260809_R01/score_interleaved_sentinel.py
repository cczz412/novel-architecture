#!/usr/bin/env python3
"""Score the single SM-interleaved iter24 gate and optional REAL24 expansion."""

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
RUN = REPO / "runs/T5_R04_READ1_TRAIN48_INTERLEAVED_SENTINEL_R01"
BASE_SCORER = REPO / "finetuning/experiments/T5_R04_READ1_TRAIN48_MIXED_SENTINEL_20260809_R01/score_mixed_sentinel.py"
AB_SCORER = REPO / "finetuning/experiments/T5_R04_READ1_FORMAT_CONTRACT_AB8_20260809_R01/run_format_contract_ab8.py"
REAL8_RAW = RUN / "REAL8_MIXED24_RAW.jsonl"
REAL8_PRE = RUN / "scoring/real8/PRE_METRICS.json"
REAL8_QUEUE = RUN / "scoring/real8/BLIND_QUEUE.jsonl"
REAL8_FINAL = RUN / "scoring/real8/FINAL_METRICS.json"
INHERITED_DECISIONS = REPO / "runs/T5_R04_TRUE_FACTONLY_REAL8_R01/INHERITED_ADJUDICATIONS.jsonl"
OLD_L6_DECISIONS = REPO / "runs/T5_R04_READ1_TRAIN48_MIXED_SENTINEL_R01/semantic_review/L6_STEP24_ADJUDICATIONS.jsonl"
L6_ADJUDICATIONS = RUN / "semantic_review/L6_ADJUDICATIONS.jsonl"
REAL8_ADJUDICATIONS = RUN / "semantic_review/REAL8_ADJUDICATIONS.jsonl"
RESULT_TICKET = EXP / "RESULT_TICKET.md"
STEPS = (24,)

L6_NEW_DECISIONS: dict[str, str | None] = {
    "43e60a9dc480": None,
    "7e88906b1db4": None,
    "548ac7bdef6c": None,
    "6a09939402bb": "LC-L05-F002",
    "4c8810620bde": "LC-L05-F003",
    "fe6f8b510deb": None,
    "819b70c9836c": "LC-L05-F004",
    "364d492c1a18": None,
    "61903ab73b41": None,
    "66b99ae24941": None,
    "4cdbdaaa3899": None,
    "da402d0f52b9": None,
    "85959d6b907f": "LC-L06-F002",
    "7e816bcd0bc4": "LC-L06-F003",
    "b47f57a9af1c": None,
    "c7bf5bf53d2c": None,
    "24e18cfe71f0": None,
    "e7c6a1adc806": None,
    "7037769ea682": None,
    "e4f99fde587a": "LC-L06-F008",
}

REAL8_NEW_DECISIONS: dict[str, str | None] = {
    "79c481f0a295": None,
    "eae69fe4b9a4": None,
    "d50490f22c0b": "C01-F008",
    "af9fd05dd717": "C02-F009",
    "d676ff90573a": None,
    "c5bdf9112560": None,
    "c980278c5745": "C05-F004",
    "cc0c366bb5f7": "C05-F006",
    "116d73044eb1": None,
    "b57328fa0522": None,
    "437693eef9a8": "C05-F012",
    "a1fa681d6ff4": "C05-F013",
    "b5681b23270f": None,
    "8df5453c9f64": "C09-F009",
    "c01742f347f2": None,
    "9acbbbc1e282": None,
    "e4c6450c61ec": "C23-F006",
    "682e5c33bc29": None,
    "2610e8bb6e9c": None,
    "b62d4da24bb1": None,
    "30e5598412c2": "C24-F007",
    "9a79811b3d55": "C24-F009",
    "3714e1e840af": None,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_base_scorer() -> Any:
    spec = importlib.util.spec_from_file_location("mixed_sentinel_frozen_scorer", BASE_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("BASE_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RUN = RUN
    return module


def raw_for_step(step: int) -> Path:
    if step != 24:
        raise RuntimeError("ONLY_ITER24_AUTHORIZED")
    return RUN / "PROBE24_RAW.jsonl"


def load_real8_scorer(adjudications: Path) -> Any:
    spec = importlib.util.spec_from_file_location("selected8_scorer_for_interleaved", AB_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("REAL8_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EXP = EXP
    module.RUN = RUN
    module.RAW = REAL8_RAW
    module.ADJUDICATIONS = adjudications
    module.LOW_DECISIONS = INHERITED_DECISIONS
    return module


def real8_pre() -> None:
    scorer = load_real8_scorer(RUN / "scoring/real8/ADJUDICATIONS.jsonl")
    result, queue = scorer.score()
    scorer.write_json(REAL8_PRE, result)
    scorer.write_jsonl(REAL8_QUEUE, queue)
    print(json.dumps({"status": result["status"], "semantic_pending": len(queue)}, ensure_ascii=False))


def real8_final(adjudications: Path) -> None:
    scorer = load_real8_scorer(adjudications)
    result, queue = scorer.score()
    if queue or result["semantic_pending"]:
        raise RuntimeError("REAL8_FINAL_STILL_PENDING")
    scorer.write_json(REAL8_FINAL, result)
    print(json.dumps({"status": "PASS_FINAL_SCORING", "semantic_pending": 0}, ensure_ascii=False))


def decision_row(item: dict[str, Any], matched: str | None) -> dict[str, Any]:
    return {
        "case_id": item["case_id"],
        "prediction_fact": item["prediction_fact"],
        "prediction_fact_sha256": item["prediction_fact_sha256"],
        "raw_sha256": item["raw_sha256"],
        "gold_sha256": item["gold_sha256"],
        "category": "SEMANTIC_EQUIVALENT" if matched else "NOT_MATCH",
        "matched_gold_fact_id": matched,
    }


def adjudicate_l6() -> None:
    scorer = load_base_scorer()
    queue = scorer.read_jsonl(RUN / "scoring/l6_step24/BLIND_QUEUE.jsonl")
    old = {
        (row["case_id"], row["prediction_fact_sha256"]): row for row in scorer.read_jsonl(OLD_L6_DECISIONS)
    }
    rows = []
    manual_used = set()
    reused = 0
    for item in queue:
        key = (item["case_id"], item["prediction_fact_sha256"])
        if key in old:
            prior = old[key]
            matched = prior.get("matched_gold_fact_id") if prior["category"] == "SEMANTIC_EQUIVALENT" else None
            reused += 1
        else:
            matches = [prefix for prefix in L6_NEW_DECISIONS if item["prediction_fact_sha256"].startswith(prefix)]
            if len(matches) != 1:
                raise RuntimeError(f"L6_MANUAL_DECISION_IDENTITY_MISMATCH:{item['prediction_fact_sha256']}")
            manual_used.add(matches[0])
            matched = L6_NEW_DECISIONS[matches[0]]
        rows.append(decision_row(item, matched))
    if manual_used != set(L6_NEW_DECISIONS) or reused != 89:
        raise RuntimeError("L6_DECISION_COVERAGE_DRIFT")
    scorer.write_jsonl(L6_ADJUDICATIONS, rows)
    print(json.dumps({"status": "L6_ADJUDICATED", "rows": len(rows), "reused": reused, "new": 20}, ensure_ascii=False))


def adjudicate_real8() -> None:
    scorer = load_base_scorer()
    queue = scorer.read_jsonl(REAL8_QUEUE)
    if len(queue) != len(REAL8_NEW_DECISIONS):
        raise RuntimeError("REAL8_DECISION_COUNT_DRIFT")
    rows = []
    used = set()
    for item in queue:
        matches = [prefix for prefix in REAL8_NEW_DECISIONS if item["prediction_fact_sha256"].startswith(prefix)]
        if len(matches) != 1:
            raise RuntimeError(f"REAL8_DECISION_IDENTITY_MISMATCH:{item['prediction_fact_sha256']}")
        used.add(matches[0])
        rows.append(decision_row(item, REAL8_NEW_DECISIONS[matches[0]]))
    if used != set(REAL8_NEW_DECISIONS):
        raise RuntimeError("REAL8_DECISION_COVERAGE_DRIFT")
    scorer.write_jsonl(REAL8_ADJUDICATIONS, rows)
    print(json.dumps({"status": "REAL8_ADJUDICATED", "rows": len(rows)}, ensure_ascii=False))


def gate(step: int) -> None:
    if step != 24:
        raise RuntimeError("ONLY_ITER24_AUTHORIZED")
    scorer = load_base_scorer()
    metrics = json.loads((RUN / f"scoring/l6_step{step}/FINAL_METRICS.json").read_text(encoding="utf-8"))
    mixed_name = f"MIXED{step}_L6"
    mixed_metrics = metrics["variants"][mixed_name]
    mixed_semantic = mixed_metrics["semantic_recoverable"]
    rows = [row for row in scorer.read_jsonl(raw_for_step(step)) if row["variant"].startswith(f"MIXED{step}_")]
    if len(rows) != 14:
        raise RuntimeError("GATE_NOT_14_ROWS")
    round_scorer = scorer.load_round_scorer()
    validator = scorer.Draft202012Validator(json.loads(scorer.SCHEMA.read_text(encoding="utf-8")))
    real_counts = {
        row["case_id"]: len(round_scorer.recoverable_parse(row["raw_output"], validator)[2])
        for row in rows
        if row["variant"] == "MIXED24_REAL_SENTINEL"
    }
    l6_case_counts = {
        row["case_id"]: row["predictions"]
        for row in metrics["case_metrics"]
        if row["variant"] == mixed_name
    }
    real8 = json.loads(REAL8_FINAL.read_text(encoding="utf-8"))["b_format_contract"]
    real8_semantic = real8["semantic_recoverable"]
    checks = {
        "zero_repetition": sum(row["repetition_detected"] for row in rows) == 0,
        "zero_token_limit": sum(row["token_limit_hit"] for row in rows) == 0,
        "two_zero_gold_cases_exactly_empty": l6_case_counts.get("LC-L01") == 0 and l6_case_counts.get("LC-L02") == 0,
        "l6_f1_at_least_0_208955": mixed_semantic["f1"] >= 0.208955,
        "l6_fp_below_42": mixed_semantic["fp"] < 42,
        "real8_tp_at_least_35": real8_semantic["tp"] >= 35,
        "real8_f1_at_least_0_431": real8_semantic["f1"] >= 0.431,
    }
    scorer.write_json(
        RUN / f"INTERLEAVED_GATE_{step}.json",
        {
            "step": step,
            "pass": all(checks.values()),
            "checks": checks,
            "l6_case_prediction_counts": l6_case_counts,
            "real8_prediction_counts": real_counts,
            "l6_semantic_recoverable": mixed_semantic,
            "real8_semantic_recoverable": real8_semantic,
            "duplicate_facts_report_only": sum(row["duplicate_facts"] for row in rows),
        },
    )
    print(json.dumps({"step": step, "pass": all(checks.values()), "checks": checks}, ensure_ascii=False))


def result() -> None:
    gate_result = json.loads((RUN / "INTERLEAVED_GATE_24.json").read_text(encoding="utf-8"))
    l6 = json.loads((RUN / "scoring/l6_step24/FINAL_METRICS.json").read_text(encoding="utf-8"))["variants"][
        "MIXED24_L6"
    ]
    real8 = json.loads(REAL8_FINAL.read_text(encoding="utf-8"))["b_format_contract"]
    full = None
    full_gate = None
    if gate_result["pass"]:
        full_path = RUN / "scoring/real_step24/FINAL_METRICS.json"
        if not full_path.is_file():
            raise RuntimeError("REAL24_REQUIRED_AFTER_GATE_PASS")
        full = json.loads(full_path.read_text(encoding="utf-8"))["variants"]["LORA_READ1"]
        semantic = full["semantic_recoverable"]
        full_gate = (
            semantic["f1"] >= 0.409639
            and semantic["precision"] >= 0.467890
            and full["repetition_cases"] == 0
            and full["token_limit_cases"] == 0
        )
    if not gate_result["pass"]:
        decision = "FAIL_SM_INTERLEAVED_AT_L6_REAL8_GATE"
    elif full_gate:
        decision = "PASS_TRAIN48_LENGTH_MATERIAL_CANDIDATE"
    else:
        decision = "FAIL_SM_INTERLEAVED_AT_REAL24_GATE"
    l6_sem = l6["semantic_recoverable"]
    real8_sem = real8["semantic_recoverable"]
    full_text = "未进入 REAL24。"
    if full is not None:
        sem = full["semantic_recoverable"]
        full_text = (
            f"REAL24：TP={sem['tp']}，FP={sem['fp']}，FN={sem['fn']}，P={sem['precision']:.6f}，"
            f"R={sem['recall']:.6f}，F1={sem['f1']:.6f}，复读={full['repetition_cases']}，"
            f"触顶={full['token_limit_cases']}。"
        )
    ticket = f"""# SM-INTERLEAVED iter24｜结果

结论：`{decision}`。

本格唯一变化是把 TRAIN48 后12条从纯短／纯中相邻批改为 `[0,10][0,8][1,7][2,6][2,5][3,4]`；48条 payload 多重集、前36行、762条事实、Prompt、Gold、模型、训练参数和解码均未改变。只训练了 iter24，没有运行 iter48/72/96。

- 排序版训练数据 SHA：`{sha256(EXP / 'READ_1_TARGET_TRAIN48_INTERLEAVED.jsonl')}`。
- runner SHA：`{sha256(EXP / 'run_interleaved_sentinel.py')}`；scorer SHA：`{sha256(Path(__file__))}`。
- iter24 adapter SHA：`{sha256(RUN / 'adapters/0000024_adapters.safetensors')}`。
- L6：TP={l6_sem['tp']}，FP={l6_sem['fp']}，FN={l6_sem['fn']}，P={l6_sem['precision']:.6f}，R={l6_sem['recall']:.6f}，F1={l6_sem['f1']:.6f}；L01/L02预测数={l6['zero_case_prediction_counts']}。
- REAL8：TP={real8_sem['tp']}，FP={real8_sem['fp']}，FN={real8_sem['fn']}，P={real8_sem['precision']:.6f}，R={real8_sem['recall']:.6f}，F1={real8_sem['f1']:.6f}。
- 14题稳定性：复读={sum(row['repetition_detected'] for row in read_jsonl(raw_for_step(24)))}，触顶={sum(row['token_limit_hit'] for row in read_jsonl(raw_for_step(24)))}，重复事实={gate_result['duplicate_facts_report_only']}。
- 第一道门：{gate_result['checks']}。
- {full_text}

本轮训练调用1次，本地推理只到事前门允许的范围；API调用0。没有运行其他LoRA、READ2/READ4、OUT、Notion、Git或现役指针操作。

来源：Codex
"""
    if RESULT_TICKET.exists():
        raise RuntimeError("RESULT_TICKET_EXISTS_NO_OVERWRITE")
    RESULT_TICKET.write_text(ticket, encoding="utf-8")
    print(json.dumps({"status": decision}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "l6-pre",
            "adjudicate-l6",
            "l6-final",
            "real8-pre",
            "adjudicate-real8",
            "real8-final",
            "gate",
            "real-pre",
            "real-final",
            "result",
        ),
    )
    parser.add_argument("--step", type=int, required=True, choices=STEPS)
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    scorer = load_base_scorer()
    if args.command in {"l6-final", "real8-final", "real-final"} and args.adjudications is None:
        parser.error(f"{args.command} requires --adjudications")
    if args.command == "l6-pre":
        scorer.l6_command(args.step, final=False, adjudications=None)
    elif args.command == "adjudicate-l6":
        adjudicate_l6()
    elif args.command == "l6-final":
        scorer.l6_command(args.step, final=True, adjudications=args.adjudications)
    elif args.command == "real8-pre":
        real8_pre()
    elif args.command == "adjudicate-real8":
        adjudicate_real8()
    elif args.command == "real8-final":
        real8_final(args.adjudications)
    elif args.command == "gate":
        gate(args.step)
    elif args.command == "real-pre":
        scorer.real_pre(args.step)
    elif args.command == "real-final":
        scorer.real_final(args.step, args.adjudications)
    else:
        result()


if __name__ == "__main__":
    main()

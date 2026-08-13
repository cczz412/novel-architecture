#!/usr/bin/env python3
"""Score the four frozen P3 context arms without training or post-hoc repair."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import unicodedata
from typing import Any


REPO = Path("/Users/a1234/挣钱/小说架构")
EXP = REPO / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01"
RESULTS = EXP / "results_r01"
OUT = RESULTS / "scoring_r02"
BUILD = EXP / "sealed_inputs_r01"
WORK = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT"
CANONICAL = WORK / "set_b_r03_work/sealed/T5_R04_SYNTHETIC_MICRO24_SET_B_R03_20260808/canonical/CANONICAL_MICRO24_SET_B_R03.jsonl"
OLD_DECISIONS = WORK / "m1_r01/semantic_scoring_r01/M1_RECOVERED_PREDICTION_DECISIONS_1014.jsonl"
NEW_DECISIONS = EXP / "P3_NEW_FACT_ADJUDICATION_10.jsonl"
ARMS = ("c0_current_minimal", "c1_rulebook_8", "c2_purpose_short", "c4_previous_state_confirmed")
ALLOWED_STATUS = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}
EXPECTED = {
    "canonical": "fa04ce5e5f819f4f87aec248ef8c306541b04128d67f0b79cc7e61f2d401d7d9",
    "adapter": "321d96c10f00389e557efbeb2d8e3dc1344071cc3cd663b51b8a8c2bd38ea5f9",
    "input_seal": "ad7305ee3c50be769aa607d2e0d016529d80af8cb98af0036adf2716637c0c82",
}


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalized(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKC", value)
    return "".join(char for char in value if not unicodedata.category(char).startswith(("P", "S", "Z")))


def prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 6), "recall": round(recall, 6), "f1": round(f1, 6)}


def percentile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    pos = (len(values) - 1) * q
    lower = int(pos)
    upper = min(lower + 1, len(values) - 1)
    fraction = pos - lower
    return round(values[lower] * (1 - fraction) + values[upper] * fraction, 3)


def distribution(values: list[int]) -> dict[str, Any]:
    return {
        "mean": round(statistics.mean(values), 3),
        "p50": percentile(values, 0.5),
        "p95": percentile(values, 0.95),
        "min": min(values),
        "max": max(values),
    }


def one_to_one_exact(gold: list[dict[str, Any]], predicted: list[dict[str, Any]], normalize: bool) -> tuple[int, int, int]:
    key = (lambda row: normalized(row.get("fact"))) if normalize else (lambda row: row.get("fact") if isinstance(row.get("fact"), str) else "")
    remaining: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(gold):
        remaining[key(row)].append(index)
    used: set[int] = set()
    tp = 0
    for row in predicted:
        candidates = [index for index in remaining.get(key(row), []) if index not in used and key(row)]
        if candidates:
            used.add(candidates[0])
            tp += 1
    return tp, len(predicted) - tp, len(gold) - tp


def load_decisions() -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in read_jsonl(OLD_DECISIONS):
        if row.get("split") != "dev24":
            continue
        key = (row["case_id"], row["prediction"].get("fact", ""))
        decision = {
            "case_id": key[0],
            "prediction_fact": key[1],
            "category": row["category"],
            "matched_gold_fact_id": row.get("matched_gold_fact_id"),
            "counts_as_tp": bool(row.get("counts_as_tp")),
            "reason": "复用冻结 M1 同 case、同预测文本裁决。",
            "review_source": "REUSED_FROZEN_M1_SAME_CASE_IDENTICAL_PREDICTION",
        }
        if key in index and (index[key]["category"], index[key]["matched_gold_fact_id"], index[key]["counts_as_tp"]) != (decision["category"], decision["matched_gold_fact_id"], decision["counts_as_tp"]):
            raise RuntimeError(f"冻结裁决冲突：{key}")
        index[key] = decision
    new_rows = read_jsonl(NEW_DECISIONS)
    if len(new_rows) != 10 or len({(row["case_id"], row["prediction_fact"]) for row in new_rows}) != 10:
        raise RuntimeError("P3 新裁决不是 10 条唯一 same-case 记录")
    for row in new_rows:
        key = (row["case_id"], row["prediction_fact"])
        if key in index:
            raise RuntimeError(f"新裁决重复覆盖旧冻结裁决：{key}")
        index[key] = {**row, "review_source": "P3_INDEPENDENT_SAME_CASE_REVIEW"}
    return index, new_rows


def semantic_score(
    case_id: str,
    gold: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    decisions: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    gold_ids = {row["fact_id"] for row in gold}
    used: set[str] = set()
    resolved: list[dict[str, Any]] = []
    for index, prediction in enumerate(predictions):
        fact = prediction.get("fact") if isinstance(prediction.get("fact"), str) else ""
        key = (case_id, fact)
        if key not in decisions:
            raise RuntimeError(f"缺少同题语义裁决：{key}")
        decision = dict(decisions[key])
        matched = decision.get("matched_gold_fact_id")
        counts = bool(decision.get("counts_as_tp")) and matched in gold_ids and matched not in used
        duplicate = bool(decision.get("counts_as_tp")) and matched in used
        if counts:
            used.add(matched)
        resolved.append({
            "prediction_index": index,
            "prediction": prediction,
            "category": decision["category"],
            "matched_gold_fact_id": matched if counts else None,
            "counts_as_tp": counts,
            "duplicate_of_already_matched_gold": duplicate,
            "review_source": decision["review_source"],
            "reason": decision["reason"],
        })
    score = prf(len(used), len(predictions) - len(used), len(gold) - len(used))
    score["matched_gold_fact_ids"] = sorted(used)
    return score, resolved


def main() -> None:
    if OUT.exists():
        raise RuntimeError(f"评分目录已存在，禁止覆盖：{OUT}")
    if sha256(CANONICAL) != EXPECTED["canonical"]:
        raise RuntimeError("DEV24 canonical 漂移")
    seal = json.loads((EXP / "P3_INPUT_TWO_RUN_AND_SEAL_RECEIPT.json").read_text(encoding="utf-8"))
    if seal.get("sealed_inventory_sha256") != EXPECTED["input_seal"]:
        raise RuntimeError("P3 输入封版漂移")
    baseline = json.loads((RESULTS / "CONTEXT_BASELINE_REPRODUCTION_RECEIPT.json").read_text(encoding="utf-8"))
    if baseline.get("status") != "PASS_C0_BASELINE_STABLE_PROJECTION_BYTE_IDENTICAL":
        raise RuntimeError("C0 未逐题稳定复现")
    canonical_rows = read_jsonl(CANONICAL)
    canonical = {row["case_id"]: row for row in canonical_rows}
    if len(canonical) != 24 or sum(len(row["facts"]) for row in canonical_rows) != 48:
        raise RuntimeError("DEV24 不是 24 case / 48 facts")
    decisions, new_decisions = load_decisions()
    OUT.mkdir(parents=True)
    metrics: dict[str, Any] = {}
    per_case: dict[str, dict[str, Any]] = {case_id: {"case_id": case_id, "arms": {}} for case_id in canonical}
    all_adjudications: dict[tuple[str, str], dict[str, Any]] = {}
    execution_bindings: dict[str, Any] = {}
    arm_semantic_matches: dict[str, dict[str, set[str]]] = {}
    invalid_id_cases_by_arm: dict[str, set[str]] = {}
    for arm in ARMS:
        raw_path = RESULTS / "raw" / arm / "RAW_OUTPUTS.jsonl"
        receipt_path = RESULTS / "raw" / arm / "INFERENCE_RECEIPT.json"
        rows = read_jsonl(raw_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if len(rows) != 24 or [row["case_id"] for row in rows] != list(canonical):
            raise RuntimeError(f"{arm} case 顺序或分母漂移")
        if receipt.get("raw_sha256") != sha256(raw_path) or receipt.get("adapter_sha256") != EXPECTED["adapter"]:
            raise RuntimeError(f"{arm} raw/adapter 绑定漂移")
        execution_bindings[arm] = {
            "raw_path": str(raw_path.relative_to(REPO)),
            "raw_sha256": sha256(raw_path),
            "inference_receipt_sha256": sha256(receipt_path),
            "questions_sha256": receipt["questions_sha256"],
            "peak_mlx_bytes": receipt["peak_mlx_bytes"],
            "elapsed_seconds": receipt["elapsed_seconds"],
        }
        aggregate = Counter()
        output_tokens: list[int] = []
        input_tokens: list[int] = []
        matched_by_case: dict[str, set[str]] = {}
        invalid_id_cases: set[str] = set()
        category_counts = Counter()
        for row in rows:
            case_id = row["case_id"]
            case = canonical[case_id]
            gold = [{
                "fact_id": fact["fact_id"],
                "fact": fact["fact_sentence"],
                "status": fact["status"],
                "speaker": fact["speaker"],
                "evidence_ids": fact["evidence"]["unit_ids"],
            } for fact in case["facts"]]
            if row["gold_output"]["facts"] != [{"fact": fact["fact"], "status": fact["status"], "speaker": fact["speaker"], "evidence_ids": fact["evidence_ids"]} for fact in gold]:
                raise RuntimeError(f"{arm}/{case_id} raw gold 与 canonical 不同源")
            recovered = row["recovered_fact_objects"]
            structured = row["parsed_output"].get("facts", []) if row["schema_valid"] else []
            strict = prf(*one_to_one_exact(gold, structured, normalize=False))
            norm = prf(*one_to_one_exact(gold, structured, normalize=True))
            semantic_recoverable, recovered_decisions = semantic_score(case_id, gold, recovered, decisions)
            semantic_structured, _ = semantic_score(case_id, gold, structured, decisions)
            matched_by_case[case_id] = set(semantic_recoverable["matched_gold_fact_ids"])
            gold_by_id = {fact["fact_id"]: fact for fact in gold}
            evidence_exact = status_correct = speaker_correct = semantic_den = 0
            all_ids = valid_ids = nonexistent_ids = 0
            valid_id_set = {unit["id"] for unit in case["micro_atomizer"]["target_units"]}
            for prediction, decision in zip(recovered, recovered_decisions):
                ids = prediction.get("evidence_ids") if isinstance(prediction.get("evidence_ids"), list) else []
                all_ids += len(ids)
                valid_ids += sum(item in valid_id_set for item in ids)
                nonexistent_ids += sum(item not in valid_id_set for item in ids)
                if any(item not in valid_id_set for item in ids):
                    invalid_id_cases.add(case_id)
                category_counts[decision["category"]] += 1
                key = (case_id, prediction.get("fact", ""))
                all_adjudications[key] = {"case_id": case_id, "prediction_fact": key[1], **{k: decision[k] for k in ("category", "matched_gold_fact_id", "counts_as_tp", "review_source", "reason")}}
                if decision["counts_as_tp"]:
                    semantic_den += 1
                    gold_fact = gold_by_id[decision["matched_gold_fact_id"]]
                    evidence_exact += int(ids == gold_fact["evidence_ids"])
                    status_correct += int(prediction.get("status") == gold_fact["status"])
                    speaker_correct += int(prediction.get("speaker") == gold_fact["speaker"])
            aggregate.update({
                "gold": len(gold), "predictions": len(recovered), "structured_predictions": len(structured),
                "strict_tp": strict["tp"], "strict_fp": strict["fp"], "strict_fn": strict["fn"],
                "norm_tp": norm["tp"], "norm_fp": norm["fp"], "norm_fn": norm["fn"],
                "sem_tp": semantic_recoverable["tp"], "sem_fp": semantic_recoverable["fp"], "sem_fn": semantic_recoverable["fn"],
                "struct_sem_tp": semantic_structured["tp"], "struct_sem_fp": semantic_structured["fp"], "struct_sem_fn": semantic_structured["fn"],
                "json": int(row["json_valid"]), "schema": int(row["schema_valid"]),
                "required_present": sum(len({"fact", "status", "speaker", "evidence_ids"} & set(item)) for item in recovered),
                "required_total": 4 * len(recovered),
                "status_legal": sum(item.get("status") in ALLOWED_STATUS for item in recovered), "status_total": len(recovered),
                "semantic_den": semantic_den, "status_correct": status_correct, "speaker_correct": speaker_correct,
                "evidence_exact": evidence_exact, "all_ids": all_ids, "valid_ids": valid_ids, "nonexistent_ids": nonexistent_ids,
                "clean_stop": int(row["finish_reason"] == "stop" and row["stop_token_is_eos_eot"]),
                "repetition": int(row["repetition_detected"]), "token_limit": int(row["finish_reason"] != "stop"),
                "duplicate_objects": int(row["exact_duplicate_fact_object_count"]),
            })
            output_tokens.append(row["output_tokens_excluding_stop"])
            input_tokens.append(row["input_tokens"])
            per_case[case_id]["arms"][arm] = {
                "gold_fact_count": len(gold), "prediction_count": len(recovered),
                "semantic_recoverable": semantic_recoverable, "semantic_structured": semantic_structured,
                "strict_fact": strict, "normalized_fact": norm,
                "json_valid": row["json_valid"], "schema_valid": row["schema_valid"],
                "status_legal_count": sum(item.get("status") in ALLOWED_STATUS for item in recovered),
                "clean_stop": row["finish_reason"] == "stop" and row["stop_token_is_eos_eot"],
                "repetition": row["repetition_detected"], "output_tokens": row["output_tokens_excluding_stop"],
                "input_tokens": row["input_tokens"], "semantic_decisions": recovered_decisions,
            }
        arm_semantic_matches[arm] = matched_by_case
        invalid_id_cases_by_arm[arm] = invalid_id_cases
        metrics[arm] = {
            "case_count": 24, "gold_fact_count": aggregate["gold"], "prediction_count": aggregate["predictions"],
            "json_parse": {"cases": aggregate["json"], "rate": round(aggregate["json"] / 24, 6)},
            "complete_schema": {"cases": aggregate["schema"], "rate": round(aggregate["schema"] / 24, 6)},
            "required_key_recall": {"present": aggregate["required_present"], "total": aggregate["required_total"], "rate": round(aggregate["required_present"] / aggregate["required_total"], 6) if aggregate["required_total"] else None},
            "strict_fact": prf(aggregate["strict_tp"], aggregate["strict_fp"], aggregate["strict_fn"]),
            "normalized_fact": prf(aggregate["norm_tp"], aggregate["norm_fp"], aggregate["norm_fn"]),
            "semantic_recoverable": prf(aggregate["sem_tp"], aggregate["sem_fp"], aggregate["sem_fn"]),
            "semantic_structured": prf(aggregate["struct_sem_tp"], aggregate["struct_sem_fp"], aggregate["struct_sem_fn"]),
            "status_legality": {"correct": aggregate["status_legal"], "denominator": aggregate["status_total"], "rate": round(aggregate["status_legal"] / aggregate["status_total"], 6) if aggregate["status_total"] else None},
            "status_accuracy_on_semantic_matches": {"correct": aggregate["status_correct"], "denominator": aggregate["semantic_den"], "rate": round(aggregate["status_correct"] / aggregate["semantic_den"], 6) if aggregate["semantic_den"] else None},
            "speaker_accuracy_on_semantic_matches": {"correct": aggregate["speaker_correct"], "denominator": aggregate["semantic_den"], "rate": round(aggregate["speaker_correct"] / aggregate["semantic_den"], 6) if aggregate["semantic_den"] else None},
            "evidence_binding_on_semantic_matches": {"exact": aggregate["evidence_exact"], "denominator": aggregate["semantic_den"], "rate": round(aggregate["evidence_exact"] / aggregate["semantic_den"], 6) if aggregate["semantic_den"] else None},
            "evidence_id_validity": {"valid": aggregate["valid_ids"], "all": aggregate["all_ids"], "nonexistent": aggregate["nonexistent_ids"], "rate": round(aggregate["valid_ids"] / aggregate["all_ids"], 6) if aggregate["all_ids"] else None},
            "termination": {"clean_cases": aggregate["clean_stop"], "repetition_cases": aggregate["repetition"], "token_limit_cases": aggregate["token_limit"], "exact_duplicate_objects": aggregate["duplicate_objects"]},
            "input_tokens": distribution(input_tokens), "output_tokens": distribution(output_tokens),
            "semantic_category_counts": dict(sorted(category_counts.items())),
        }
    # Cross-arm, pre-registered diagnostic deltas. These are descriptive, not a composite score.
    c0 = metrics["c0_current_minimal"]
    comparisons: dict[str, Any] = {}
    for arm in ARMS[1:]:
        current = metrics[arm]
        lost_gold = gained_gold = 0
        better = worse = same = 0
        for case_id in canonical:
            base_set = arm_semantic_matches["c0_current_minimal"][case_id]
            arm_set = arm_semantic_matches[arm][case_id]
            lost_gold += len(base_set - arm_set)
            gained_gold += len(arm_set - base_set)
            base_f1 = per_case[case_id]["arms"]["c0_current_minimal"]["semantic_recoverable"]["f1"]
            arm_f1 = per_case[case_id]["arms"][arm]["semantic_recoverable"]["f1"]
            if arm_f1 > base_f1:
                better += 1
            elif arm_f1 < base_f1:
                worse += 1
            else:
                same += 1
        comparisons[arm] = {
            "semantic_f1_delta": round(current["semantic_recoverable"]["f1"] - c0["semantic_recoverable"]["f1"], 6),
            "precision_delta": round(current["semantic_recoverable"]["precision"] - c0["semantic_recoverable"]["precision"], 6),
            "recall_delta": round(current["semantic_recoverable"]["recall"] - c0["semantic_recoverable"]["recall"], 6),
            "schema_case_delta": current["complete_schema"]["cases"] - c0["complete_schema"]["cases"],
            "prediction_count_delta": current["prediction_count"] - c0["prediction_count"],
            "mean_input_token_delta": round(current["input_tokens"]["mean"] - c0["input_tokens"]["mean"], 3),
            "mean_output_token_delta": round(current["output_tokens"]["mean"] - c0["output_tokens"]["mean"], 3),
            "gold_matches_lost_vs_c0": lost_gold, "gold_matches_gained_vs_c0": gained_gold,
            "paired_case_f1": {"arm_better": better, "arm_worse": worse, "same": same},
        }
    diagnostics = {
        "c1_rule_induced_over_conservatism": {
            "gold_matches_lost_vs_c0": comparisons["c1_rulebook_8"]["gold_matches_lost_vs_c0"],
            "prediction_count_delta": comparisons["c1_rulebook_8"]["prediction_count_delta"],
            "interpretation": "8 条规则显著压低输出与召回；这是过度保守信号，不是质量提升。",
        },
        "c2_purpose_induced_summary_bias": {
            "partial_or_broad_predictions": sum(value for key, value in metrics["c2_purpose_short"]["semantic_category_counts"].items() if key.startswith("PARTIALLY_")),
            "prediction_count_delta": comparisons["c2_purpose_short"]["prediction_count_delta"],
            "interpretation": "只登记概括化/过宽风险；不得把任务目的直接晋升为默认输入。",
        },
        "c4_background_only_unsupported_fact": {
            "count": len(invalid_id_cases_by_arm["c4_previous_state_confirmed"]),
            "case_ids": sorted(invalid_id_cases_by_arm["c4_previous_state_confirmed"]),
            "mechanical_signal": "预测引用 B01；正式 C2 负责区只允许 Txx，故同时构成只读前态泄漏与不存在的目标 evidence ID。",
            "interpretation": "明确确认前态仍可能被模型抄入负责区答案。",
        },
        "c4_previous_state_conflict": {"count": 0, "interpretation": "同题复核未见与确认前态直接矛盾的预测。"},
        "c4_contract_note": "C4 重复显式标注了原题已含的 read_only_before；它测试标签/强调效果，不是新增信息量。",
    }
    write_json(OUT / "CONTEXT_CONTRACT_METRICS.json", {
        "status": "PASS_P3_CONTEXT_CONTRACT_ZERO_TRAINING_SCORING_COMPLETE",
        "created_at": now(), "metrics": metrics, "comparisons_vs_c0": comparisons, "diagnostics": diagnostics,
        "semantic_review": {"unique_predictions": len(all_adjudications), "reused_frozen_decisions": len(all_adjudications) - len(new_decisions), "new_same_case_decisions": len(new_decisions)},
    })
    write_jsonl(OUT / "P3_SEMANTIC_ADJUDICATION_79.jsonl", [all_adjudications[key] for key in sorted(all_adjudications)])
    paired_rows = []
    for case_id, row in per_case.items():
        base = row["arms"]["c0_current_minimal"]
        row["deltas_vs_c0"] = {
            arm: {
                "semantic_f1": round(data["semantic_recoverable"]["f1"] - base["semantic_recoverable"]["f1"], 6),
                "predictions": data["prediction_count"] - base["prediction_count"],
                "input_tokens": data["input_tokens"] - base["input_tokens"],
                "output_tokens": data["output_tokens"] - base["output_tokens"],
            } for arm, data in row["arms"].items() if arm != "c0_current_minimal"
        }
        paired_rows.append(row)
    write_jsonl(OUT / "CONTEXT_CONTRACT_PAIRED_CASES_24.jsonl", paired_rows)
    write_json(OUT / "CONTEXT_CONTRACT_EXECUTION_LOCK.json", {
        "status": "FROZEN_P3_ZERO_TRAINING_EXECUTION_COMPLETE",
        "created_at": now(), "arms": list(ARMS), "cases_each": 24,
        "model_role": "offline_proxy_model", "training": False, "api_called": False, "retry": 0,
        "decode": {"temperature": 0.0, "max_output_tokens": 1024, "sampler": "greedy"},
        "canonical_sha256": sha256(CANONICAL), "adapter_sha256": EXPECTED["adapter"],
        "sealed_input_inventory_sha256": EXPECTED["input_seal"], "bindings": execution_bindings,
    })
    ticket = f"""# P3 输入合同零训练筛查结果票\n\n✅ C0 已逐题稳定复现；C1、C2、C4 均在同一 C2 update72、同一 DEV24、同一解码条件下完成，训练与 API 调用均为 0。\n\n| 输入臂 | 语义 P / R / F1 | Schema | 预测事实 | 输入 token 均值 | 结论 |\n|---|---:|---:|---:|---:|---|\n| C0 当前极简 | {metrics['c0_current_minimal']['semantic_recoverable']['precision']:.3f} / {metrics['c0_current_minimal']['semantic_recoverable']['recall']:.3f} / {metrics['c0_current_minimal']['semantic_recoverable']['f1']:.3f} | {metrics['c0_current_minimal']['complete_schema']['cases']}/24 | {metrics['c0_current_minimal']['prediction_count']} | {metrics['c0_current_minimal']['input_tokens']['mean']} | 现役基线 |\n| C1 八条规则 | {metrics['c1_rulebook_8']['semantic_recoverable']['precision']:.3f} / {metrics['c1_rulebook_8']['semantic_recoverable']['recall']:.3f} / {metrics['c1_rulebook_8']['semantic_recoverable']['f1']:.3f} | {metrics['c1_rulebook_8']['complete_schema']['cases']}/24 | {metrics['c1_rulebook_8']['prediction_count']} | {metrics['c1_rulebook_8']['input_tokens']['mean']} | 过度保守，淘汰当前写法 |\n| C2 任务目的 | {metrics['c2_purpose_short']['semantic_recoverable']['precision']:.3f} / {metrics['c2_purpose_short']['semantic_recoverable']['recall']:.3f} / {metrics['c2_purpose_short']['semantic_recoverable']['f1']:.3f} | {metrics['c2_purpose_short']['complete_schema']['cases']}/24 | {metrics['c2_purpose_short']['prediction_count']} | {metrics['c2_purpose_short']['input_tokens']['mean']} | 候选，未证明优于 C0 |\n| C4 确认前态 | {metrics['c4_previous_state_confirmed']['semantic_recoverable']['precision']:.3f} / {metrics['c4_previous_state_confirmed']['semantic_recoverable']['recall']:.3f} / {metrics['c4_previous_state_confirmed']['semantic_recoverable']['f1']:.3f} | {metrics['c4_previous_state_confirmed']['complete_schema']['cases']}/24 | {metrics['c4_previous_state_confirmed']['prediction_count']} | {metrics['c4_previous_state_confirmed']['input_tokens']['mean']} | 出现前态泄漏，不晋升 |\n\n🔥 这轮最清楚的信号：规则写得更多，不等于模型更稳。C1 大量返回空数组，召回明显受损。C4 还出现把只读前文直接抄成答案的案例。\n\n⚠️ C3 只有 1/24 条安全别名，C5 没有真实章节／块坐标，均按工单跳过；C4 只有相对前态，没有绝对章节位置。\n\n本票只说明本地 Qwen 离线代理在合成 DEV24 上的输入敏感性，不替豆包定版，也不授权训练、Production Canonical 或权利放行。\n\n来源：Codex\n"""
    (OUT / "CONTEXT_CONTRACT_RESULT_TICKET.md").write_text(ticket, encoding="utf-8")
    print(json.dumps({"status": "PASS", "metrics": metrics, "comparisons": comparisons}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

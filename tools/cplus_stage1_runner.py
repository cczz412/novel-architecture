#!/usr/bin/env python3
"""T5 R04 C+ 阶段 1：三个零训练单变量根因证伪。

运行顺序固定：A stage1 41 题、C stage1 41 题、A final 22 个触顶案
改 4096、C final 41 题只改标题范围写法。每题只生成一次，不重试。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LAB = Path("/Users/a1234/挣钱/小说架构_隔离实验")
UPSTREAM = LAB / "T5_R04_A_C_FORMAT_COMPARE_20260807_R01"
MODEL = LAB / "models/Qwen3-4B-Instruct-2507_cdbee75f"
EXPERIMENT_ID = "T5_R04_CPLUS_20260807_R01"
CPLUS = ROOT / "finetuning/experiments" / EXPERIMENT_ID
CONTROL = CPLUS / "stage_1_root_cause"
RUN_DIR = ROOT / "runs" / EXPERIMENT_ID / "stage_1_root_cause"
INPUTS = RUN_DIR / "inputs"
RESULTS = RUN_DIR / "results"
LOGS = RUN_DIR / "logs"
STATE = CONTROL / "STAGE_1_STATE.json"
LOCK = CONTROL / "STAGE_1_EXECUTION_LOCK.json"
METRICS = CONTROL / "STAGE_1_METRICS.json"
REPORT = CONTROL / "STAGE_1_RESULT.md"
RECEIPT = CONTROL / "STAGE_1_COMPLETE_RECEIPT.json"
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
OLD_RUNNER_PATH = UPSTREAM / "tools/ac_exam_r03_runner.py"

A_QUESTIONS = UPSTREAM / "exam_rebalance_r03/sealed/a/QUESTIONS.jsonl"
C_QUESTIONS = UPSTREAM / "exam_rebalance_r03/sealed/c/QUESTIONS.jsonl"
A_GOLD = UPSTREAM / "exam_rebalance_r03/sealed/private_gold/a/GOLD.jsonl"
C_GOLD = UPSTREAM / "exam_rebalance_r03/sealed/private_gold/c/GOLD.jsonl"
A_FINAL_RAW = UPSTREAM / "exam_rebalance_r03/results/arm_a/RAW_OUTPUTS.jsonl"
C_FINAL_RAW = UPSTREAM / "exam_rebalance_r03/results/arm_c/RAW_OUTPUTS.jsonl"
A_STAGE1 = UPSTREAM / "runs/arm_a/stage_1_positive/adapters.safetensors"
A_FINAL = UPSTREAM / "runs/arm_a/final/adapters.safetensors"
C_STAGE1 = UPSTREAM / "runs/arm_c/stage_1_positive/adapters.safetensors"
C_FINAL = UPSTREAM / "runs/arm_c/final/adapters.safetensors"

TASK_ORDER = ["1a_a_stage1", "1a_c_stage1", "1b_a_4096", "1c_c_natural_header"]
HEADER_RE = re.compile(r"\[(CH\d{4}-E\d{3})｜归属终点范围 @(\d+):(\d+)\]")
POINTER_RE = re.compile(r"^(CH\d{4}-E\d{3})@(\d+):(\d+)$")
PUNCT_MAP = str.maketrans({"，": ",", "。": ".", "！": "!", "？": "?", "：": ":", "；": ";", "（": "(", "）": ")", "【": "[", "】": "]", "“": '"', "”": '"', "‘": "'", "’": "'"})


def now() -> str:
    return datetime.now().astimezone().isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise RuntimeError(f"JSONL_ROW_NOT_OBJECT:{path}")
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical(row) + "\n")


def load_old_runner():
    spec = importlib.util.spec_from_file_location("ac_exam_r03_frozen", OLD_RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def system_free_percent() -> int:
    output = subprocess.check_output(["vm_stat"], text=True)
    match = re.search(r"page size of (\d+) bytes", output)
    page_size = int(match.group(1)) if match else 16384
    values: dict[str, int] = {}
    for line in output.splitlines():
        found = re.match(r"([^:]+):\s+(\d+)\.", line)
        if found:
            values[found.group(1)] = int(found.group(2))
    free_pages = sum(values.get(key, 0) for key in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable"))
    total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
    return round(100 * free_pages * page_size / total)


def object_spans(text: str) -> list[tuple[dict[str, Any], int, int, str]]:
    """从有效或被截断的 facts 数组中恢复已经完整闭合的对象。"""
    marker = re.search(r'"facts"\s*:\s*\[', text)
    if not marker:
        return []
    rows: list[tuple[dict[str, Any], int, int, str]] = []
    depth = 0
    start: int | None = None
    in_string = False
    escaped = False
    for index in range(marker.end(), len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                raw = text[start:index + 1]
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError:
                    start = None
                    continue
                if isinstance(value, dict):
                    rows.append((value, start, index + 1, raw))
                start = None
        elif char == "]" and depth == 0:
            break
    return rows


def normalize(value: Any, *, terminal_punctuation: bool = False) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"\s+", " ", text.strip()).translate(PUNCT_MAP)
    if terminal_punctuation:
        text = re.sub(r"[.!?]$", "", text)
    return text


def normalized_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        normalize(item.get("fact"), terminal_punctuation=True),
        normalize(item.get("status")),
        normalize(item.get("speaker")),
    )


def counter_score(gold: list[dict[str, Any]], predicted: list[dict[str, Any]]) -> dict[str, Any]:
    left = Counter(normalized_key(item) for item in gold)
    right = Counter(normalized_key(item) for item in predicted if item.get("fact"))
    tp = sum((left & right).values())
    fp = sum(right.values()) - tp
    fn = sum(left.values()) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 6), "recall": round(recall, 6), "f1": round(f1, 6)}


def merge_score(rows: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]]) -> dict[str, Any]:
    gold = [item for left, _ in rows for item in left]
    predicted = [item for _, right in rows for item in right]
    return counter_score(gold, predicted)


def severe_repeat(items: list[dict[str, Any]]) -> bool:
    keys = [canonical(item) for item in items]
    facts = [normalize(item.get("fact"), terminal_punctuation=True) for item in items if item.get("fact")]
    return (bool(keys) and max(Counter(keys).values()) >= 3) or (bool(facts) and max(Counter(facts).values()) >= 3)


def pathology(text: str, old, arm: str) -> dict[str, bool]:
    recovered = [row[0] for row in object_spans(text)]
    checked = old.format_check(text, arm)
    evidence_field = "evidence" if arm == "a" else "evidence_ids"
    evidence_first = any(list(item)[0] == evidence_field for item in recovered if item)
    missing_fact = any("fact" not in item or not item.get("fact") for item in recovered)
    container_abnormal = bool(checked["valid"] and checked["errors"])
    return {"evidence_first": evidence_first, "missing_fact": missing_fact, "container_abnormal": container_abnormal, "any": evidence_first or missing_fact or container_abnormal}


def transform_c_question(row: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = json.loads(json.dumps(row, ensure_ascii=False))
    user = result["messages"][1]["content"]
    changes: list[dict[str, Any]] = []

    def replace(match: re.Match[str]) -> str:
        base, start, end = match.groups()
        old = match.group(0)
        new = f"[{base}｜证据终点允许落在第 {start}（含）至 {end}（不含）字符]"
        changes.append({"base_id": base, "old": old, "new": new})
        return new

    changed = HEADER_RE.sub(replace, user)
    if not changes or "归属终点范围 @" in changed:
        raise RuntimeError(f"C_HEADER_TRANSFORM_FAILURE:{row['case_id']}")
    result["messages"][1]["content"] = changed
    return result, changes


def prepare() -> dict[str, Any]:
    if RUN_DIR.exists() or LOCK.exists():
        raise RuntimeError("STAGE1_OUTPUT_ALREADY_EXISTS")
    for path in (A_QUESTIONS, C_QUESTIONS, A_GOLD, C_GOLD, A_FINAL_RAW, C_FINAL_RAW, A_STAGE1, A_FINAL, C_STAGE1, C_FINAL, OLD_RUNNER_PATH, MODEL / "MODEL_RECEIPT.json"):
        if not path.is_file():
            raise RuntimeError(f"REQUIRED_FILE_MISSING:{path}")
    a_questions = read_jsonl(A_QUESTIONS)
    c_questions = read_jsonl(C_QUESTIONS)
    a_gold = read_jsonl(A_GOLD)
    c_gold = read_jsonl(C_GOLD)
    if not (len(a_questions) == len(c_questions) == len(a_gold) == len(c_gold) == 41):
        raise RuntimeError("CURRENT_41_DENOMINATOR_MISMATCH")
    if [row["case_id"] for row in a_questions] != [row["case_id"] for row in c_questions]:
        raise RuntimeError("A_C_CASE_ORDER_MISMATCH")
    old = load_old_runner()
    if [[(item.get("fact"), item.get("status"), item.get("speaker")) for item in old.facts(row)] for row in a_gold] != [[(item.get("fact"), item.get("status"), item.get("speaker")) for item in old.facts(row)] for row in c_gold]:
        raise RuntimeError("A_C_GOLD_SEMANTICS_MISMATCH")

    a_final = read_jsonl(A_FINAL_RAW)
    capped_ids = [row["case_id"] for row in a_final if row.get("reached_max_output_tokens")]
    if len(capped_ids) != 22:
        raise RuntimeError(f"A_CAPPED_DENOMINATOR_NOT_22:{len(capped_ids)}")
    by_case = {row["case_id"]: row for row in a_questions}
    subset = [by_case[case_id] for case_id in capped_ids]
    transformed: list[dict[str, Any]] = []
    change_log: list[dict[str, Any]] = []
    for row in c_questions:
        changed, changes = transform_c_question(row)
        transformed.append(changed)
        change_log.append({"case_id": row["case_id"], "changes": changes})

    INPUTS.mkdir(parents=True, exist_ok=False)
    RESULTS.mkdir(parents=True, exist_ok=False)
    LOGS.mkdir(parents=True, exist_ok=False)
    write_jsonl(INPUTS / "1b_a_capped22_questions.jsonl", subset)
    write_jsonl(INPUTS / "1c_c_natural_header_questions.jsonl", transformed)
    write_jsonl(INPUTS / "1c_header_change_log.jsonl", change_log)

    tasks = {
        "1a_a_stage1": {"arm": "a", "questions": str(A_QUESTIONS), "adapter": str(A_STAGE1), "max_tokens": 2048, "expected_rows": 41},
        "1a_c_stage1": {"arm": "c", "questions": str(C_QUESTIONS), "adapter": str(C_STAGE1), "max_tokens": 2048, "expected_rows": 41},
        "1b_a_4096": {"arm": "a", "questions": str(INPUTS / "1b_a_capped22_questions.jsonl"), "adapter": str(A_FINAL), "max_tokens": 4096, "expected_rows": 22},
        "1c_c_natural_header": {"arm": "c", "questions": str(INPUTS / "1c_c_natural_header_questions.jsonl"), "adapter": str(C_FINAL), "max_tokens": 2048, "expected_rows": 41},
    }
    for task in tasks.values():
        task["questions_sha256"] = sha256(Path(task["questions"]))
        task["adapter_sha256"] = sha256(Path(task["adapter"]))
    lock = {
        "schema_version": "t5-r04-cplus-stage1-execution-lock-v1",
        "status": "PREPARED",
        "experiment_id": EXPERIMENT_ID,
        "created_at": now(),
        "task_order": TASK_ORDER,
        "single_variable_contract": {
            "1a": "adapter checkpoint only",
            "1b": "max_output_tokens 2048 to 4096 only",
            "1c": "C question header range notation only",
        },
        "decode": {"sampler": "greedy", "temperature": 0.0, "automatic_retries": 0},
        "tasks": tasks,
        "frozen_inputs": {str(path): sha256(path) for path in (A_QUESTIONS, C_QUESTIONS, A_GOLD, C_GOLD, A_FINAL_RAW, C_FINAL_RAW, OLD_RUNNER_PATH, MODEL / "MODEL_RECEIPT.json", INPUTS / "1c_header_change_log.jsonl")},
        "api_called": False,
        "training_started": False,
        "large_scale_collection_started": False,
    }
    write_json(LOCK, lock)
    write_json(STATE, {"status": "PREPARED", "active_task": None, "completed_tasks": [], "updated_at": now()})
    return lock


def verify_task(lock: dict[str, Any], task_name: str) -> dict[str, Any]:
    if task_name not in TASK_ORDER or lock.get("task_order") != TASK_ORDER:
        raise RuntimeError("TASK_ORDER_DRIFT")
    task = lock["tasks"][task_name]
    if sha256(Path(task["questions"])) != task["questions_sha256"]:
        raise RuntimeError(f"QUESTION_SHA_DRIFT:{task_name}")
    if sha256(Path(task["adapter"])) != task["adapter_sha256"]:
        raise RuntimeError(f"ADAPTER_SHA_DRIFT:{task_name}")
    for path, digest in lock["frozen_inputs"].items():
        if sha256(Path(path)) != digest:
            raise RuntimeError(f"FROZEN_INPUT_DRIFT:{path}")
    return task


def run_task(task_name: str) -> None:
    import mlx.core as mx
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    task = verify_task(lock, task_name)
    questions = read_jsonl(Path(task["questions"]))
    if len(questions) != task["expected_rows"]:
        raise RuntimeError(f"TASK_ROW_MISMATCH:{task_name}")
    old = load_old_runner()
    out = RESULTS / task_name
    out.mkdir(parents=True, exist_ok=False)
    raw_path = out / "RAW_OUTPUTS.jsonl"
    receipt_path = out / "RUN_RECEIPT.json"
    receipt: dict[str, Any] = {**task, "task": task_name, "status": "RUNNING", "started_at": now(), "pid": os.getpid()}
    write_json(receipt_path, receipt)
    completed = 0
    peak = 0
    try:
        mx.set_wired_limit(20 * 1024**3)
        mx.set_memory_limit(22 * 1024**3)
        mx.set_cache_limit(1 * 1024**3)
        mx.clear_cache()
        model, tokenizer = load(str(MODEL), adapter_path=str(Path(task["adapter"]).parent))
        sampler = make_sampler(temp=0.0)
        with raw_path.open("x", encoding="utf-8", newline="\n") as handle:
            for index, question in enumerate(questions, 1):
                free_before = system_free_percent()
                if free_before < 10:
                    raise RuntimeError(f"MEMORY_HARD_STOP_BEFORE:{question['case_id']}:{free_before}")
                mx.reset_peak_memory()
                prompt = tokenizer.apply_chat_template(question["messages"], tokenize=False, add_generation_prompt=True)
                began = time.monotonic()
                output = generate(model, tokenizer, prompt=prompt, max_tokens=task["max_tokens"], sampler=sampler, verbose=False)
                elapsed = time.monotonic() - began
                output_ids = tokenizer.encode(output)
                output_tokens = len(output_ids)
                checked = old.format_check(output, task["arm"])
                case_peak = int(mx.get_peak_memory())
                peak = max(peak, case_peak)
                record: dict[str, Any] = {
                    "index": index,
                    "task": task_name,
                    "arm": task["arm"].upper(),
                    "case_id": question["case_id"],
                    "pair_id": question["pair_id"],
                    "segment_id": question["segment_id"],
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "raw_output": output,
                    "format_valid": checked["valid"],
                    "format_errors": checked["errors"],
                    "input_tokens": len(tokenizer.encode(prompt)),
                    "output_tokens": output_tokens,
                    "finish_reason": "length" if output_tokens >= task["max_tokens"] else "eos_or_stop",
                    "reached_max_output_tokens": output_tokens >= task["max_tokens"],
                    "elapsed_seconds": round(elapsed, 3),
                    "system_free_percent_before": free_before,
                    "mlx_peak_memory_bytes": case_peak,
                }
                if task_name == "1b_a_4096":
                    prefix = tokenizer.decode(output_ids[:2048])
                    spans = object_spans(output)
                    prefix_spans = object_spans(prefix)
                    before = Counter(canonical(row[0]) for row in prefix_spans)
                    after = [row[0] for row in spans if row[1] >= len(prefix)]
                    seen = Counter(before)
                    repeats = 0
                    for item in after:
                        key = canonical(item)
                        repeats += int(seen[key] > 0)
                        seen[key] += 1
                    first_repeat_char = None
                    observed: Counter[str] = Counter()
                    for item, start, _, _ in spans:
                        key = canonical(item)
                        if observed[key] and first_repeat_char is None:
                            first_repeat_char = start
                        observed[key] += 1
                    record.update({
                        "prefix_2048_text": prefix,
                        "post_2048_complete_objects": len(after),
                        "post_2048_repeated_objects": repeats,
                        "first_repeat_token": len(tokenizer.encode(output[:first_repeat_char])) if first_repeat_char is not None else None,
                    })
                mx.clear_cache()
                free_after = system_free_percent()
                record["system_free_percent_after"] = free_after
                handle.write(canonical(record) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                completed = index
                print(canonical({"task": task_name, "progress": f"{index}/{len(questions)}", "case_id": question["case_id"], "format_valid": checked["valid"], "output_tokens": output_tokens, "free_after": free_after, "peak_gib": round(case_peak / 1024**3, 3)}), flush=True)
                if free_after < 10:
                    raise RuntimeError(f"MEMORY_HARD_STOP_AFTER:{question['case_id']}:{free_after}")
        receipt.update({"status": "COMPLETE", "completed_at": now(), "completed_rows": completed, "raw_outputs_sha256": sha256(raw_path), "mlx_peak_memory_bytes": peak})
    except BaseException as exc:
        receipt.update({"status": "HARD_STOP", "stopped_at": now(), "completed_rows": completed, "error_type": type(exc).__name__, "error": str(exc)})
        raise
    finally:
        write_json(receipt_path, receipt)
        mx.clear_cache()


def output_metrics(raw_rows: list[dict[str, Any]], questions: list[dict[str, Any]], gold_rows: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    old = load_old_runner()
    question_map = {row["case_id"]: row for row in questions}
    gold_map = {row["case_id"]: old.facts(row) for row in gold_rows}
    raw_pairs: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []
    recovered_pairs: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []
    strata_raw: dict[str, list[tuple[list[dict[str, Any]], list[dict[str, Any]]]]] = {}
    strata_recovered: dict[str, list[tuple[list[dict[str, Any]], list[dict[str, Any]]]]] = {}
    valid = truncated = repeats = pathology_cases = evidence_first = missing_fact = container = 0
    tokens: list[int] = []
    for result in raw_rows:
        case_id = result["case_id"]
        question = question_map[case_id]
        gold = gold_map[case_id]
        checked = old.format_check(result["raw_output"], arm)
        parsed = checked["parsed"] if checked["valid"] else None
        raw_pred = parsed.get("facts", []) if isinstance(parsed, dict) else []
        recovered = [row[0] for row in object_spans(result["raw_output"])]
        p = pathology(result["raw_output"], old, arm)
        valid += int(checked["valid"])
        truncated += int(result.get("reached_max_output_tokens"))
        repeats += int(severe_repeat(recovered))
        pathology_cases += int(p["any"])
        evidence_first += int(p["evidence_first"])
        missing_fact += int(p["missing_fact"])
        container += int(p["container_abnormal"])
        tokens.append(int(result.get("output_tokens", 0)))
        source = question.get("source_class", "unknown")
        raw_pairs.append((gold, raw_pred))
        recovered_pairs.append((gold, recovered))
        strata_raw.setdefault(source, []).append((gold, raw_pred))
        strata_recovered.setdefault(source, []).append((gold, recovered))
    tokens.sort()
    count = len(raw_rows)
    return {
        "cases": count,
        "raw_json_valid_cases": valid,
        "raw_json_valid_rate": round(valid / count, 6),
        "truncated_cases": truncated,
        "truncation_rate": round(truncated / count, 6),
        "severe_repeat_cases": repeats,
        "severe_repeat_case_rate": round(repeats / count, 6),
        "format_pathology_cases": pathology_cases,
        "evidence_first_cases": evidence_first,
        "missing_fact_cases": missing_fact,
        "container_abnormal_cases": container,
        "fact_normalized_raw": merge_score(raw_pairs),
        "fact_normalized_recovered": merge_score(recovered_pairs),
        "strata_raw": {key: merge_score(value) for key, value in sorted(strata_raw.items())},
        "strata_recovered": {key: merge_score(value) for key, value in sorted(strata_recovered.items())},
        "output_tokens": {"p50": tokens[len(tokens) // 2], "p90": tokens[min(len(tokens) - 1, int(len(tokens) * 0.9))], "max": max(tokens)},
    }


def classify_1a(stage1: dict[str, Any], final: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    pathology_delta = final["format_pathology_cases"] - stage1["format_pathology_cases"]
    pathology_pp = pathology_delta / final["cases"]
    f1_gain = final["fact_normalized_recovered"]["f1"] - stage1["fact_normalized_recovered"]["f1"]
    if (pathology_delta >= 5 or pathology_pp >= 0.10) and f1_gain < 0.03:
        labels.append("STAGE2_FORMAT_POLLUTION_SUPPORTED")
    overall_drop = stage1["fact_normalized_recovered"]["f1"] - final["fact_normalized_recovered"]["f1"]
    layer_drops = 0
    for key, value in stage1["strata_recovered"].items():
        if key in final["strata_recovered"] and value["f1"] - final["strata_recovered"][key]["f1"] >= 0.05:
            layer_drops += 1
    raw_drop = stage1["fact_normalized_raw"]["f1"] - final["fact_normalized_raw"]["f1"]
    not_json_only = overall_drop >= 0.05 and abs(raw_drop - overall_drop) < 0.05
    if overall_drop >= 0.05 and layer_drops >= 2 and not_json_only:
        labels.append("STAGE2_BROAD_FORGETTING_SUPPORTED")
    main_diffs = [
        abs(final["raw_json_valid_rate"] - stage1["raw_json_valid_rate"]),
        abs(final["severe_repeat_case_rate"] - stage1["severe_repeat_case_rate"]),
        abs(final["truncation_rate"] - stage1["truncation_rate"]),
        abs(f1_gain),
    ]
    if max(main_diffs) < 0.03 and abs(pathology_delta) <= 2:
        labels.append("NO_MATERIAL_STAGE_EFFECT")
    return labels or ["MIXED_STAGE_EFFECT"]


def header_stats(raw_rows: list[dict[str, Any]], original_questions: list[dict[str, Any]]) -> dict[str, Any]:
    old = load_old_runner()
    qmap = {row["case_id"]: row for row in original_questions}
    copied = total = valid = facts = 0
    for result in raw_rows:
        user = qmap[result["case_id"]]["messages"][1]["content"]
        ranges = {base: (int(start), int(end)) for base, start, end in HEADER_RE.findall(user)}
        items = [row[0] for row in object_spans(result["raw_output"])]
        for item in items:
            facts += 1
            ok, _ = old.c_pointer_valid(user, item)
            valid += int(ok)
            for pointer in item.get("evidence_ids", []) if isinstance(item.get("evidence_ids"), list) else []:
                match = POINTER_RE.fullmatch(pointer) if isinstance(pointer, str) else None
                if not match:
                    continue
                total += 1
                copied += int(ranges.get(match.group(1)) == (int(match.group(2)), int(match.group(3))))
    return {
        "recovered_facts": facts,
        "pointer_elements": total,
        "header_range_copied": copied,
        "header_range_copy_rate": round(copied / total, 6) if total else 0.0,
        "strict_legal_facts": valid,
        "strict_pointer_legal_rate": round(valid / facts, 6) if facts else 0.0,
    }


def score_all() -> dict[str, Any]:
    old = load_old_runner()
    a_questions, c_questions = read_jsonl(A_QUESTIONS), read_jsonl(C_QUESTIONS)
    a_gold, c_gold = read_jsonl(A_GOLD), read_jsonl(C_GOLD)
    a_stage1_raw = read_jsonl(RESULTS / "1a_a_stage1/RAW_OUTPUTS.jsonl")
    c_stage1_raw = read_jsonl(RESULTS / "1a_c_stage1/RAW_OUTPUTS.jsonl")
    a_final_raw, c_final_raw = read_jsonl(A_FINAL_RAW), read_jsonl(C_FINAL_RAW)
    a_stage1 = output_metrics(a_stage1_raw, a_questions, a_gold, "a")
    c_stage1 = output_metrics(c_stage1_raw, c_questions, c_gold, "c")
    a_final = output_metrics(a_final_raw, a_questions, a_gold, "a")
    c_final = output_metrics(c_final_raw, c_questions, c_gold, "c")

    run_1b = read_jsonl(RESULTS / "1b_a_4096/RAW_OUTPUTS.jsonl")
    capped_ids = [row["case_id"] for row in a_final_raw if row.get("reached_max_output_tokens")]
    gold_map = {row["case_id"]: old.facts(row) for row in a_gold}
    base_map = {row["case_id"]: row for row in a_final_raw}
    new_map = {row["case_id"]: row for row in run_1b}
    if set(capped_ids) != set(new_map) or len(capped_ids) != 22:
        raise RuntimeError("1B_CASE_SET_MISMATCH")
    base_pairs = []
    new_pairs = []
    closed = still_repeat_or_max = first_repeat_before = post_total = post_repeat = 0
    for case_id in capped_ids:
        gold = gold_map[case_id]
        base_items = [row[0] for row in object_spans(base_map[case_id]["raw_output"])]
        new_items = [row[0] for row in object_spans(new_map[case_id]["raw_output"])]
        base_pairs.append((gold, base_items))
        new_pairs.append((gold, new_items))
        closed += int(old.format_check(new_map[case_id]["raw_output"], "a")["valid"])
        still_repeat_or_max += int(severe_repeat(new_items) or new_map[case_id].get("reached_max_output_tokens"))
        first_repeat_before += int((new_map[case_id].get("first_repeat_token") or 10**9) < 2048)
        post_total += int(new_map[case_id].get("post_2048_complete_objects", 0))
        post_repeat += int(new_map[case_id].get("post_2048_repeated_objects", 0))
    base_score, new_score = merge_score(base_pairs), merge_score(new_pairs)
    repeat_share = post_repeat / post_total if post_total else 0.0
    if closed >= 14 and repeat_share < 0.25 and new_score["recall"] - base_score["recall"] >= 0.10:
        label_1b = "OUTPUT_LIMIT_ROOT_CAUSE_SUPPORTED"
    elif still_repeat_or_max >= 18 or (first_repeat_before >= 18 and repeat_share >= 0.75):
        label_1b = "OUTPUT_LIMIT_IS_TERMINATOR_SUPPORTED"
    else:
        label_1b = "MIXED_OUTPUT_LIMIT_EFFECT"

    c_changed = read_jsonl(RESULTS / "1c_c_natural_header/RAW_OUTPUTS.jsonl")
    baseline_header = header_stats(c_final_raw, c_questions)
    changed_header = header_stats(c_changed, c_questions)
    copy_drop = baseline_header["header_range_copy_rate"] - changed_header["header_range_copy_rate"]
    legal_gain = changed_header["strict_pointer_legal_rate"] - baseline_header["strict_pointer_legal_rate"]
    if copy_drop >= 0.20 and legal_gain >= 0.05:
        label_1c = "HEADER_RANGE_COPY_IMPORTANT_CAUSE"
    elif copy_drop >= 0.20 and legal_gain < 0.05:
        label_1c = "HEADER_RANGE_COPY_PRESENT_NOT_MAIN"
    elif copy_drop < 0.10 and legal_gain < 0.02:
        label_1c = "NO_MATERIAL_HEADER_EFFECT"
    else:
        label_1c = "MIXED_HEADER_EFFECT"

    return {
        "schema_version": "t5-r04-cplus-stage1-metrics-v1",
        "status": "STAGE_1_THREE_EXPERIMENTS_COMPLETE",
        "stage_1a": {
            "a": {"stage1": a_stage1, "final": a_final, "labels": classify_1a(a_stage1, a_final)},
            "c": {"stage1": c_stage1, "final": c_final, "labels": classify_1a(c_stage1, c_final)},
        },
        "stage_1b": {
            "cases": 22,
            "closed_valid_json": closed,
            "still_repeat_or_reached_4096": still_repeat_or_max,
            "first_repeat_before_2048": first_repeat_before,
            "post_2048_objects": post_total,
            "post_2048_repeated_objects": post_repeat,
            "post_2048_repeat_rate": round(repeat_share, 6),
            "baseline_recovered_normalized": base_score,
            "new_recovered_normalized": new_score,
            "label": label_1b,
        },
        "stage_1c": {
            "baseline": baseline_header,
            "natural_language_header": changed_header,
            "header_copy_drop_pp": round(copy_drop, 6),
            "strict_legality_gain_pp": round(legal_gain, 6),
            "label": label_1c,
        },
        "boundaries": {"training_started": False, "api_called": False, "large_scale_collection_started": False, "historical_scores_overwritten": False},
    }


def render_report(metrics: dict[str, Any]) -> str:
    a = metrics["stage_1a"]["a"]
    c = metrics["stage_1a"]["c"]
    b = metrics["stage_1b"]
    h = metrics["stage_1c"]
    return f"""# T5 R04 C+｜阶段 1 三个根因证伪结果

✅ 三个实验都只改了一个变量，原始一次生成全部保留；没有训练、API、500 本抽数或历史成绩覆盖。

## 1A｜只换 checkpoint

- A：{', '.join(a['labels'])}
  - JSON 有效：stage1 {a['stage1']['raw_json_valid_cases']}/41；final {a['final']['raw_json_valid_cases']}/41
  - 恢复后归一 F1：stage1 {a['stage1']['fact_normalized_recovered']['f1']:.4f}；final {a['final']['fact_normalized_recovered']['f1']:.4f}
  - 格式病理：stage1 {a['stage1']['format_pathology_cases']} 案；final {a['final']['format_pathology_cases']} 案
- C：{', '.join(c['labels'])}
  - JSON 有效：stage1 {c['stage1']['raw_json_valid_cases']}/41；final {c['final']['raw_json_valid_cases']}/41
  - 恢复后归一 F1：stage1 {c['stage1']['fact_normalized_recovered']['f1']:.4f}；final {c['final']['fact_normalized_recovered']['f1']:.4f}
  - 格式病理：stage1 {c['stage1']['format_pathology_cases']} 案；final {c['final']['format_pathology_cases']} 案

## 1B｜A 的 22 个触顶案只把上限改成 4096

- 判定：`{b['label']}`
- 4096 内闭合：{b['closed_valid_json']}/22
- 仍复读或再次触顶：{b['still_repeat_or_reached_4096']}/22
- 首次复读发生在 2048 前：{b['first_repeat_before_2048']}/22
- 2048 后完整对象：{b['post_2048_objects']}，其中重复 {b['post_2048_repeated_objects']}（{b['post_2048_repeat_rate']:.2%}）
- 恢复后归一召回：2048={b['baseline_recovered_normalized']['recall']:.4f}；4096={b['new_recovered_normalized']['recall']:.4f}

## 1C｜只把 C 题面标题范围改成自然语言

- 判定：`{h['label']}`
- 标题范围复制率：{h['baseline']['header_range_copy_rate']:.2%} → {h['natural_language_header']['header_range_copy_rate']:.2%}
- 严格指针合法率：{h['baseline']['strict_pointer_legal_rate']:.2%} → {h['natural_language_header']['strict_pointer_legal_rate']:.2%}

这轮只负责把旧 A/C 的失败原因分清，不拿当前 41 题决定新 A/C-2 胜负。

来源：Codex
"""


def supervisor(token: str) -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if hashlib.sha256(token.encode()).hexdigest() != lock.get("token_sha256"):
        raise RuntimeError("RUN_TOKEN_MISMATCH")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state.update({"status": "RUNNING", "supervisor_pid": os.getpid(), "started_at": now(), "updated_at": now()})
    write_json(STATE, state)
    completed: list[str] = []
    try:
        for task in TASK_ORDER:
            task_log = LOGS / f"{task}.log"
            state.update({"status": "RUNNING", "active_task": task, "completed_tasks": completed, "updated_at": now()})
            write_json(STATE, state)
            with task_log.open("x", encoding="utf-8") as handle:
                result = subprocess.run([str(PYTHON), str(Path(__file__).resolve()), "run-task", "--task", task], cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, check=False)
            if result.returncode:
                raise RuntimeError(f"TASK_EXIT:{task}:{result.returncode}")
            receipt = json.loads((RESULTS / task / "RUN_RECEIPT.json").read_text(encoding="utf-8"))
            if receipt.get("status") != "COMPLETE" or receipt.get("completed_rows") != lock["tasks"][task]["expected_rows"]:
                raise RuntimeError(f"TASK_RECEIPT_NOT_COMPLETE:{task}")
            completed.append(task)
        metrics = score_all()
        write_json(METRICS, metrics)
        REPORT.write_text(render_report(metrics), encoding="utf-8")
        receipt = {
            "schema_version": "t5-r04-cplus-stage1-complete-receipt-v1",
            "status": "PASS_STAGE_1_THREE_SINGLE_VARIABLE_EXPERIMENTS_COMPLETE",
            "experiment_id": EXPERIMENT_ID,
            "completed_tasks": completed,
            "metrics_sha256": sha256(METRICS),
            "report_sha256": sha256(REPORT),
            "execution_lock_sha256": sha256(LOCK),
            "raw_outputs": {task: {"rows": len(read_jsonl(RESULTS / task / "RAW_OUTPUTS.jsonl")), "sha256": sha256(RESULTS / task / "RAW_OUTPUTS.jsonl")} for task in TASK_ORDER},
            "api_called": False,
            "training_started": False,
            "large_scale_collection_started": False,
            "completed_at": now(),
        }
        write_json(RECEIPT, receipt)
        state.update({"status": "STAGE_1_COMPLETE", "active_task": None, "completed_tasks": completed, "metrics": str(METRICS), "completed_at": now(), "updated_at": now()})
        write_json(STATE, state)
    except BaseException as exc:
        state.update({"status": "HARD_STOP", "active_task": state.get("active_task"), "completed_tasks": completed, "error_type": type(exc).__name__, "error": str(exc), "stopped_at": now(), "updated_at": now()})
        write_json(STATE, state)
        raise


def start() -> None:
    if STATE.exists():
        current = json.loads(STATE.read_text(encoding="utf-8"))
        if alive(current.get("supervisor_pid")):
            raise RuntimeError(f"STAGE1_ALREADY_RUNNING:{current['supervisor_pid']}")
    lock = prepare()
    token = secrets.token_urlsafe(32)
    lock["token_sha256"] = hashlib.sha256(token.encode()).hexdigest()
    lock["status"] = "RUNNING"
    write_json(LOCK, lock)
    supervisor_log = LOGS / "supervisor.log"
    with supervisor_log.open("x", encoding="utf-8") as handle:
        process = subprocess.Popen([str(PYTHON), str(Path(__file__).resolve()), "supervise", "--token", token], cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state.update({"status": "STARTING", "supervisor_pid": process.pid, "updated_at": now()})
    write_json(STATE, state)
    print(json.dumps({"status": "STARTED", "supervisor_pid": process.pid, "task_order": TASK_ORDER}, ensure_ascii=False, indent=2))


def status() -> None:
    if not STATE.exists():
        print(json.dumps({"status": "NOT_STARTED"}, indent=2))
        return
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state["supervisor_alive"] = alive(state.get("supervisor_pid"))
    active = state.get("active_task")
    if active:
        raw = RESULTS / active / "RAW_OUTPUTS.jsonl"
        state["active_completed_rows"] = len(read_jsonl(raw)) if raw.exists() else 0
        log = LOGS / f"{active}.log"
        if log.exists():
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            state["latest_progress"] = lines[-1] if lines else None
    state["system_free_percent"] = system_free_percent()
    print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("start")
    sub.add_parser("status")
    worker = sub.add_parser("run-task")
    worker.add_argument("--task", required=True, choices=TASK_ORDER)
    sup = sub.add_parser("supervise")
    sup.add_argument("--token", required=True)
    args = parser.parse_args()
    if args.command == "start":
        start()
    elif args.command == "status":
        status()
    elif args.command == "run-task":
        run_task(args.task)
    else:
        supervisor(args.token)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""只读重评分器：案例内精确匹配，并生成独立人工语义盲审队列。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable


ALLOWED_STATUS = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", "", text)


def normalize_speaker(item: dict[str, Any]) -> str:
    value = item.get("speaker")
    if value is None:
        return ""
    return normalize_text(value)


def gold_facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    payload = row.get("assistant")
    value = json.loads(payload) if isinstance(payload, str) else payload
    facts = value.get("facts") if isinstance(value, dict) else None
    if not isinstance(facts, list):
        raise ValueError(f"gold facts 格式错误：{row.get('case_id')}")
    return facts


def strict_key(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fact_key(item: dict[str, Any]) -> str:
    return normalize_text(item.get("fact"))


def triple_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return fact_key(item), normalize_text(item.get("status")), normalize_speaker(item)


def evidence_key(item: dict[str, Any], arm: str) -> tuple[Any, ...]:
    if arm == "a":
        evidence = normalize_text(item.get("evidence"))
    else:
        evidence = (
            tuple(item.get("evidence_ids") or []),
            tuple(item.get("evidence_anchors") or []),
        )
    return (*triple_key(item), evidence)


def extract_complete_objects(text: str) -> list[dict[str, Any]]:
    """从被截断的 facts 数组中只恢复已经完整闭合的对象，用于复读诊断。"""
    marker = re.search(r'"facts"\s*:\s*\[', text)
    if not marker:
        return []
    objects: list[dict[str, Any]] = []
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
                try:
                    value = json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    value = None
                if isinstance(value, dict):
                    objects.append(value)
                start = None
        elif char == "]" and depth == 0:
            break
    return objects


def validate_output(text: str, arm: str) -> dict[str, Any]:
    recovered = extract_complete_objects(text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return {
            "json_valid": False,
            "top_schema_valid": False,
            "schema_valid": False,
            "errors": [f"invalid_json:{exc.msg}"],
            "facts": [],
            "recovered_facts": recovered,
        }
    if not isinstance(value, dict) or set(value) != {"facts"} or not isinstance(value.get("facts"), list):
        return {
            "json_valid": True,
            "top_schema_valid": False,
            "schema_valid": False,
            "errors": ["top_level_schema"],
            "facts": [],
            "recovered_facts": recovered,
        }
    required = {"fact", "status", "evidence"} if arm == "a" else {"fact", "status", "evidence_ids", "evidence_anchors"}
    allowed = required | {"speaker"}
    errors: list[str] = []
    for index, item in enumerate(value["facts"]):
        if not isinstance(item, dict):
            errors.append(f"fact_{index}_not_object")
            continue
        if not required.issubset(item):
            errors.append(f"fact_{index}_missing_field")
        if set(item) - allowed:
            errors.append(f"fact_{index}_extra_field")
        if not isinstance(item.get("fact"), str) or not item.get("fact"):
            errors.append(f"fact_{index}_invalid_fact")
        if item.get("status") not in ALLOWED_STATUS:
            errors.append(f"fact_{index}_invalid_status")
        speaker = item.get("speaker")
        if "speaker" in item and speaker is not None and (not isinstance(speaker, str) or not speaker):
            errors.append(f"fact_{index}_invalid_speaker")
        if arm == "a" and (not isinstance(item.get("evidence"), str) or not item.get("evidence")):
            errors.append(f"fact_{index}_invalid_evidence")
        if arm == "c":
            ids, anchors = item.get("evidence_ids"), item.get("evidence_anchors")
            if not isinstance(ids, list) or not ids or not all(isinstance(x, str) and x for x in ids):
                errors.append(f"fact_{index}_invalid_evidence_ids")
            if not isinstance(anchors, list) or not anchors or not all(isinstance(x, str) and x for x in anchors):
                errors.append(f"fact_{index}_invalid_evidence_anchors")
            if isinstance(ids, list) and isinstance(anchors, list) and len(ids) != len(anchors):
                errors.append(f"fact_{index}_ids_anchors_length")
    return {
        "json_valid": True,
        "top_schema_valid": True,
        "schema_valid": not errors,
        "errors": errors,
        "facts": value["facts"] if not errors else [],
        "recovered_facts": recovered,
    }


def count_match(gold: list[dict[str, Any]], pred: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any]) -> dict[str, int]:
    left, right = Counter(key(item) for item in gold), Counter(key(item) for item in pred)
    tp = sum((left & right).values())
    return {"tp": tp, "fp": sum(right.values()) - tp, "fn": sum(left.values()) - tp}


def add_bucket(target: dict[str, int], source: dict[str, int]) -> None:
    for key in ("tp", "fp", "fn"):
        target[key] += source[key]


def finish(bucket: dict[str, int]) -> dict[str, Any]:
    tp, fp, fn = bucket["tp"], bucket["fp"], bucket["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {**bucket, "precision": round(precision, 6), "recall": round(recall, 6), "f1": round(f1, 6)}


def conditional_field_accuracy(gold: list[dict[str, Any]], pred: list[dict[str, Any]]) -> dict[str, int]:
    gold_by_fact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pred_by_fact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in gold:
        gold_by_fact[fact_key(item)].append(item)
    for item in pred:
        pred_by_fact[fact_key(item)].append(item)
    paired = status_ok = speaker_ok = 0
    for key in sorted(gold_by_fact.keys() & pred_by_fact.keys()):
        left = sorted(gold_by_fact[key], key=strict_key)
        right = sorted(pred_by_fact[key], key=strict_key)
        for gold_item, pred_item in zip(left, right):
            paired += 1
            status_ok += int(normalize_text(gold_item.get("status")) == normalize_text(pred_item.get("status")))
            speaker_ok += int(normalize_speaker(gold_item) == normalize_speaker(pred_item))
    return {"paired_exact_fact": paired, "status_correct": status_ok, "speaker_correct": speaker_ok}


def repeated(items: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any]) -> bool:
    values = [key(item) for item in items]
    return bool(values) and max(Counter(values).values()) >= 3


def duplicate_count(items: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any]) -> int:
    values = [key(item) for item in items]
    return len(values) - len(set(values))


def repeated_fragments(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fact_counts = Counter(fact_key(item) for item in items if fact_key(item))
    object_counts = Counter(strict_key(item) for item in items)
    rows: list[dict[str, Any]] = []
    for value, count in sorted(fact_counts.items(), key=lambda pair: (-pair[1], pair[0])):
        if count >= 2:
            rows.append({"kind": "fact", "fragment": value[:240], "count": count})
    for value, count in sorted(object_counts.items(), key=lambda pair: (-pair[1], pair[0])):
        if count >= 2:
            rows.append({"kind": "object", "fragment": value[:240], "count": count})
    return rows[:6]


def stable_blind_id(group_id: str, case_id: str) -> str:
    return hashlib.sha256(f"evaluator-r02|{group_id}|{case_id}".encode()).hexdigest()[:16]


def ensure_case_alignment(raw_rows: list[dict[str, Any]], gold_rows: list[dict[str, Any]], group_id: str) -> None:
    raw_ids = [row.get("case_id") for row in raw_rows]
    gold_ids = [row.get("case_id") for row in gold_rows]
    if len(raw_ids) != len(set(raw_ids)) or len(gold_ids) != len(set(gold_ids)):
        raise ValueError(f"{group_id}: case_id 重复")
    if len(raw_rows) != len(gold_rows) or raw_ids != gold_ids:
        raise ValueError(f"{group_id}: raw/gold case 顺序不一致")


def evaluate_group(group: dict[str, Any], output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    arm = group["arm"]
    raw_path, gold_path = Path(group["raw"]), Path(group["gold"])
    raw_rows, gold_rows = read_jsonl(raw_path), read_jsonl(gold_path)
    ensure_case_alignment(raw_rows, gold_rows, group["group_id"])
    gold_by_case = {row["case_id"]: row for row in gold_rows}

    buckets = {name: {"tp": 0, "fp": 0, "fn": 0} for name in ("exact_record", "normalized_exact_fact", "normalized_exact_triple", "evidence_representation")}
    format_counts = Counter()
    conditional = Counter()
    case_rows: list[dict[str, Any]] = []
    blind_rows: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        case_id = raw["case_id"]
        gold = gold_facts(gold_by_case[case_id])
        checked = validate_output(str(raw.get("raw_output", "")), arm)
        pred = checked["facts"] if checked["schema_valid"] else []
        recovered = checked["recovered_facts"]
        format_counts["cases"] += 1
        for name in ("json_valid", "top_schema_valid", "schema_valid"):
            format_counts[name] += int(checked[name])
        format_counts["invalid_json"] += int(not checked["json_valid"])
        format_counts["top_level_abnormal"] += int(checked["json_valid"] and not checked["top_schema_valid"])
        format_counts["row_schema_abnormal"] += int(checked["top_schema_valid"] and not checked["schema_valid"])
        format_counts["reached_max_output_tokens"] += int(bool(raw.get("reached_max_output_tokens")))
        format_counts["recovered_object_repeat"] += int(repeated(recovered, strict_key))
        format_counts["recovered_fact_repeat"] += int(repeated(recovered, fact_key))
        object_duplicates = duplicate_count(recovered, strict_key)
        fact_duplicates = duplicate_count(recovered, fact_key)
        format_counts["recovered_complete_objects"] += len(recovered)
        format_counts["duplicate_objects"] += object_duplicates
        format_counts["duplicate_facts"] += fact_duplicates
        recovered_exact = count_match(gold, recovered, fact_key)
        if not checked["json_valid"]:
            format_counts["invalid_json_recovered_exact_fact_tp"] += recovered_exact["tp"]
            format_counts["invalid_json_with_recovered_exact_fact_cases"] += int(recovered_exact["tp"] > 0)

        matches = {
            "exact_record": count_match(gold, pred, strict_key),
            "normalized_exact_fact": count_match(gold, pred, fact_key),
            "normalized_exact_triple": count_match(gold, pred, triple_key),
            "evidence_representation": count_match(gold, pred, lambda item: evidence_key(item, arm)),
        }
        for name, value in matches.items():
            add_bucket(buckets[name], value)
        fields = conditional_field_accuracy(gold, pred)
        conditional.update(fields)

        blind_id = stable_blind_id(group["group_id"], case_id)
        candidate_pred = pred if checked["schema_valid"] else recovered
        blind_rows.append({
            "blind_case_id": blind_id,
            "gold_fact_sentences": [item.get("fact", "") for item in gold],
            "predicted_fact_sentences": [item.get("fact", "") for item in candidate_pred],
            "review_status": "PENDING_HUMAN_BLIND_REVIEW",
            "allowed_judgments": ["same", "partial", "different"],
        })
        key_rows.append({"blind_case_id": blind_id, "group_id": group["group_id"], "case_id": case_id})
        case_rows.append({
            "group_id": group["group_id"],
            "arm": arm.upper(),
            "case_id": case_id,
            "gold_facts": len(gold),
            "scored_predicted_facts": len(pred),
            "recovered_complete_objects": len(recovered),
            "json_valid": checked["json_valid"],
            "top_schema_valid": checked["top_schema_valid"],
            "schema_valid": checked["schema_valid"],
            "errors": checked["errors"],
            "reached_max_output_tokens": bool(raw.get("reached_max_output_tokens")),
            "recovered_object_repeat": repeated(recovered, strict_key),
            "recovered_fact_repeat": repeated(recovered, fact_key),
            "duplicate_object_count": object_duplicates,
            "duplicate_fact_count": fact_duplicates,
            "repeated_fragments": repeated_fragments(recovered),
            "recovered_normalized_exact_fact_match": recovered_exact,
            "invalid_json_with_recovered_exact_fact": bool(not checked["json_valid"] and recovered_exact["tp"] > 0),
            "matches": matches,
            "conditional_fields": fields,
        })

    cases = format_counts["cases"]
    paired = conditional["paired_exact_fact"]
    summary = {
        "group_id": group["group_id"],
        "arm": arm.upper(),
        "cases": cases,
        "gold_facts": sum(len(gold_facts(row)) for row in gold_rows),
        "format": dict(format_counts),
        "raw_recovery_diagnostics": {
            "diagnostic_only_never_promotes_format_failure": True,
            "recovered_complete_objects": format_counts["recovered_complete_objects"],
            "duplicate_objects": format_counts["duplicate_objects"],
            "duplicate_facts": format_counts["duplicate_facts"],
            "invalid_json_with_recovered_exact_fact_cases": format_counts["invalid_json_with_recovered_exact_fact_cases"],
            "invalid_json_recovered_exact_fact_tp": format_counts["invalid_json_recovered_exact_fact_tp"],
        },
        "scores": {name: finish(bucket) for name, bucket in buckets.items()},
        "conditional_on_normalized_exact_fact": {
            **dict(conditional),
            "status_accuracy": round(conditional["status_correct"] / paired, 6) if paired else 0.0,
            "speaker_accuracy": round(conditional["speaker_correct"] / paired, 6) if paired else 0.0,
        },
        "human_semantic_review": {
            "status": "PENDING",
            "queue_file": "BLIND_PAIRING_QUEUE.jsonl",
            "machine_scores_must_not_be_called_semantic": True,
            "format_failure_can_never_be_promoted_by_human_semantic_judgment": True,
        },
        "input_bindings": {
            "raw_sha256": sha256(raw_path),
            "gold_sha256": sha256(gold_path),
        },
    }
    return summary, case_rows, blind_rows, key_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    groups = json.loads(args.groups.read_text(encoding="utf-8"))["groups"]
    args.output.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    blind: list[dict[str, Any]] = []
    keys: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    for group in groups:
        summary, group_cases, group_blind, group_keys = evaluate_group(group, args.output)
        summaries.append(summary)
        cases.extend(group_cases)
        blind.extend(group_blind)
        keys.extend(group_keys)
        bindings.append({"group_id": group["group_id"], **summary["input_bindings"]})
    blind.sort(key=lambda row: row["blind_case_id"])
    keys.sort(key=lambda row: row["blind_case_id"])
    write_json(args.output / "EVALUATOR_R02_METRICS.json", {
        "schema_version": "t5-r04-evaluator-r02-metrics-v1",
        "status": "MACHINE_RESCORE_COMPLETE_HUMAN_SEMANTIC_REVIEW_PENDING",
        "matching_scope": "within_case_only",
        "normalization": "unicode_nfkc_and_remove_whitespace_only",
        "groups": summaries,
        "historical_scores_overwritten": False,
    })
    write_jsonl(args.output / "CASE_METRICS.jsonl", cases)
    write_jsonl(args.output / "BLIND_PAIRING_QUEUE.jsonl", blind)
    write_json(args.output / "BLIND_KEY.json", {"schema_version": "t5-r04-evaluator-r02-blind-key-v1", "rows": keys})
    write_json(args.output / "INPUT_BINDINGS.json", {"schema_version": "t5-r04-evaluator-r02-input-bindings-v1", "groups_file_sha256": sha256(args.groups), "groups": bindings})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

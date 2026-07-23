#!/usr/bin/env python3
"""第91道步二：在模型发网前封存跨书来源探针事实。

这个工具不访问网络，不读任何模型输出。它只核对两份独立票，
按第三人预写的逐探针选择生成字段分歧账、最终事实集和封签。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
STEP1 = ROOT / "runs/Z91_双臂跨书基线_步一试卷_v1.2_20260723"
DEFAULT_FACT_DIR = ROOT / (
    "runs/Z91_双臂跨书基线_步二双臂_v1.0_20260723/review/source_facts"
)
RECORD_FIELDS = (
    "probe_id",
    "canonical_fact",
    "subject",
    "action_or_state",
    "result",
    "explicit_qualifiers",
    "support_anchor_ids",
    "reason",
)


class SourceFactSealError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SourceFactSealError(f"JSON 顶层不是对象：{path}")
    return value


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def expected_probe_ids() -> list[str]:
    slots = read_object(STEP1 / "probe_slots.json").get("slots")
    if not isinstance(slots, list):
        raise SourceFactSealError("冻结探针槽缺 slots")
    result = [str(row.get("probe_id")) for row in slots if isinstance(row, Mapping)]
    if len(result) != 18 or len(set(result)) != 18:
        raise SourceFactSealError("冻结探针 ID 不是18个唯一值")
    return result


def validate_reviewer(document: Mapping[str, Any], reviewer: str) -> dict[str, dict[str, Any]]:
    if (
        document.get("schema_version") != "z91-source-fact-review-v1"
        or document.get("reviewer_id") != reviewer
        or document.get("dual_arm_outputs_read") is not False
        or document.get("internet_used") is not False
    ):
        raise SourceFactSealError(f"复核者 {reviewer} 的独立声明不合同")
    items = document.get("items")
    if not isinstance(items, list):
        raise SourceFactSealError(f"复核者 {reviewer} 缺 items")
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or tuple(item) != RECORD_FIELDS:
            raise SourceFactSealError(f"复核者 {reviewer} 第 {index} 条字段不合同")
        probe_id = item["probe_id"]
        if not isinstance(probe_id, str) or probe_id in result:
            raise SourceFactSealError(f"复核者 {reviewer} 探针 ID 无效或重复")
        for field in ("canonical_fact", "subject", "action_or_state", "result", "reason"):
            if not isinstance(item[field], str) or (field != "result" and not item[field].strip()):
                raise SourceFactSealError(f"{probe_id} 的 {field} 无效")
        for field in ("explicit_qualifiers", "support_anchor_ids"):
            values = item[field]
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise SourceFactSealError(f"{probe_id} 的 {field} 无效")
        if not item["support_anchor_ids"]:
            raise SourceFactSealError(f"{probe_id} 缺支撑锚")
        result[probe_id] = item
    if list(result) != expected_probe_ids():
        raise SourceFactSealError(f"复核者 {reviewer} 的18个探针顺序或集合漂移")
    return result


def catalog_anchor_ids(case_key: str) -> set[str]:
    catalog = read_object(STEP1 / "cases" / case_key / "evidence_catalog.json")
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        raise SourceFactSealError(f"{case_key} 目录缺 entries")
    return {
        str(row.get("anchor_id"))
        for row in entries
        if isinstance(row, Mapping) and isinstance(row.get("anchor_id"), str)
    }


def build_documents(fact_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    reviewer_paths = {
        "A": fact_dir / "reviewer_A.json",
        "B": fact_dir / "reviewer_B.json",
    }
    reviews = {
        reviewer: validate_reviewer(read_object(path), reviewer)
        for reviewer, path in reviewer_paths.items()
    }
    policy_path = fact_dir / "adjudication_policy.json"
    policy = read_object(policy_path)
    if (
        policy.get("schema_version") != "z91-source-fact-adjudication-policy-v1"
        or policy.get("scope") != "only_fields_where_reviewer_A_and_B_differ"
        or not isinstance(policy.get("adjudicator"), str)
    ):
        raise SourceFactSealError("第三人裁决策略头部不合同")
    choices = policy.get("choices")
    if not isinstance(choices, list):
        raise SourceFactSealError("第三人裁决缺 choices")
    choice_map: dict[str, dict[str, Any]] = {}
    for row in choices:
        if not isinstance(row, dict) or set(row) != {"probe_id", "preferred_reviewer", "reason"}:
            raise SourceFactSealError("第三人裁决行字段不合同")
        probe_id = row["probe_id"]
        if probe_id in choice_map or row["preferred_reviewer"] not in {"A", "B"}:
            raise SourceFactSealError("第三人裁决行重复或票号无效")
        choice_map[probe_id] = row
    if list(choice_map) != expected_probe_ids():
        raise SourceFactSealError("第三人裁决未一对一覆盖18个探针")

    resolved_items: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    catalogs = {case: catalog_anchor_ids(case) for case in ("X02-C0031", "X03-C0019", "X04-C0046")}
    for probe_id in expected_probe_ids():
        preferred = str(choice_map[probe_id]["preferred_reviewer"])
        final = dict(reviews[preferred][probe_id])
        case_key = probe_id.rsplit("-P", 1)[0]
        unknown = [anchor for anchor in final["support_anchor_ids"] if anchor not in catalogs[case_key]]
        if unknown:
            raise SourceFactSealError(f"{probe_id} 出现目录外锚：{unknown}")
        final["adjudicated_from"] = preferred
        final["adjudication_reason"] = choice_map[probe_id]["reason"]
        resolved_items.append(final)
        for field in RECORD_FIELDS[1:]:
            left = reviews["A"][probe_id][field]
            right = reviews["B"][probe_id][field]
            if left == right:
                if final[field] != left:
                    raise SourceFactSealError(f"{probe_id}/{field} 两票一致却被第三人改写")
                continue
            disagreements.append(
                {
                    "probe_id": probe_id,
                    "field_path": f"/{field}",
                    "reviewer_A_value": left,
                    "reviewer_B_value": right,
                    "final_value": final[field],
                    "chosen_reviewer": preferred,
                    "reason": choice_map[probe_id]["reason"],
                }
            )
    resolved = {
        "schema_version": "z91-source-facts-resolved-v1",
        "status": "resolved_before_model_calls",
        "probe_count": 18,
        "items": resolved_items,
    }
    adjudication = {
        "schema_version": "z91-source-fact-field-adjudication-v1",
        "scope": "only_disagreed_fields",
        "adjudicator": policy["adjudicator"],
        "disagreement_field_count": len(disagreements),
        "rows": disagreements,
    }
    chapter_shas = {
        case: sha256_file(STEP1 / "cases" / case / "chapter_body.txt")
        for case in ("X02-C0031", "X03-C0019", "X04-C0046")
    }
    seal_preimage = {
        "schema_version": "z91-source-fact-seal-v1",
        "status": "sealed_before_model_calls",
        "rubric_sha256": sha256_file(STEP1 / "rubric_candidate.json"),
        "probe_slots_sha256": sha256_file(STEP1 / "probe_slots.json"),
        "chapter_body_sha256_by_case": chapter_shas,
        "reviewer_files": {
            reviewer: {"path": path.name, "sha256": sha256_file(path)}
            for reviewer, path in reviewer_paths.items()
        },
        "adjudication_policy": {"path": policy_path.name, "sha256": sha256_file(policy_path)},
        "adjudication_file": {
            "path": "field_adjudication.json",
            "sha256": canonical_sha(adjudication),
        },
        "resolved_file": {"path": "resolved.json", "sha256": canonical_sha(resolved)},
        "probe_count": 18,
        "reviewers": 2,
        "dual_arm_outputs_seen_before_seal": False,
        "sealed_at": datetime.now(timezone.utc).isoformat(),
    }
    seal = {**seal_preimage, "seal_preimage_sha256": canonical_sha(seal_preimage)}
    return adjudication, resolved, seal


def write_documents(fact_dir: Path) -> dict[str, Any]:
    targets = [fact_dir / "field_adjudication.json", fact_dir / "resolved.json", fact_dir / "source_fact_seal.json"]
    if any(path.exists() for path in targets):
        raise SourceFactSealError("封签目标已存在，拒绝覆盖或重做")
    adjudication, resolved, seal = build_documents(fact_dir)
    write_json_exclusive(targets[0], adjudication)
    write_json_exclusive(targets[1], resolved)
    # 把封签内的两个工件 SHA 改为实际文件字节 SHA，再重建封签自身前像。
    seal["adjudication_file"]["sha256"] = sha256_file(targets[0])
    seal["resolved_file"]["sha256"] = sha256_file(targets[1])
    preimage = {key: value for key, value in seal.items() if key != "seal_preimage_sha256"}
    seal["seal_preimage_sha256"] = canonical_sha(preimage)
    write_json_exclusive(targets[2], seal)
    return audit_documents(fact_dir)


def audit_documents(fact_dir: Path) -> dict[str, Any]:
    expected_adjudication, expected_resolved, _ = build_documents(fact_dir)
    adjudication_path = fact_dir / "field_adjudication.json"
    resolved_path = fact_dir / "resolved.json"
    seal_path = fact_dir / "source_fact_seal.json"
    if read_object(adjudication_path) != expected_adjudication:
        raise SourceFactSealError("字段分歧账不能由两票与裁决策略重建")
    if read_object(resolved_path) != expected_resolved:
        raise SourceFactSealError("最终探针事实不能重建")
    seal = read_object(seal_path)
    preimage = {key: value for key, value in seal.items() if key != "seal_preimage_sha256"}
    required = {
        "schema_version", "status", "rubric_sha256", "probe_slots_sha256",
        "chapter_body_sha256_by_case", "reviewer_files", "adjudication_policy",
        "adjudication_file", "resolved_file", "probe_count", "reviewers",
        "dual_arm_outputs_seen_before_seal", "sealed_at", "seal_preimage_sha256",
    }
    if set(seal) != required or seal.get("seal_preimage_sha256") != canonical_sha(preimage):
        raise SourceFactSealError("封签字段或自身 SHA 无效")
    checks = {
        "rubric_sha256": sha256_file(STEP1 / "rubric_candidate.json"),
        "probe_slots_sha256": sha256_file(STEP1 / "probe_slots.json"),
    }
    if any(seal.get(key) != value for key, value in checks.items()):
        raise SourceFactSealError("封签引用的步一真源漂移")
    if seal.get("adjudication_file", {}).get("sha256") != sha256_file(adjudication_path):
        raise SourceFactSealError("字段分歧账 SHA 漂移")
    if seal.get("resolved_file", {}).get("sha256") != sha256_file(resolved_path):
        raise SourceFactSealError("最终探针事实 SHA 漂移")
    return {
        "status": "pass",
        "probe_count": 18,
        "disagreement_field_count": expected_adjudication["disagreement_field_count"],
        "seal_sha256": sha256_file(seal_path),
        "resolved_sha256": sha256_file(resolved_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fact-dir", type=Path, default=DEFAULT_FACT_DIR)
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    result = audit_documents(args.fact_dir) if args.audit else write_documents(args.fact_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

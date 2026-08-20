#!/usr/bin/env python3
"""Materialize clean-baseline work order 3 from read-only main sources.

Temporary PR helper. It creates the reviewed-candidate traceability table, the
R03 six-case addendum package, their pointers, a read-only checker, and focused
tests. It does not modify R14, R03, runtime, contracts, designs, or advisory
source directories. The workflow deletes this helper before the final commit.
"""

from __future__ import annotations

import collections
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "3d3a0afcc3a5479d11ce84f96995c78aea917510"
UPDATED_AT = "2026-08-21T06:10:00+08:00"

SEED_PATH = ROOT / "work/clean_baseline_decision_20260820_r01/pro_review_seed/08_CAPABILITY_TRACEABILITY.json"
SCHEMA_PATH = ROOT / "work/clean_baseline_decision_20260820_r01/pro_review_seed/07_REQUIREMENT_SCHEMA_CANDIDATE.json"
R03_PATH = ROOT / "references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json"
R14_ENTRY = ROOT / "references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md"
OLD_DESIGN_PATH = ROOT / "references/atomic-expectations/ATOMIC_TEST_DESIGN_20260820_R01/01_ATOMIC_TEST_DESIGN.json"
OLD_POINTER_PATH = ROOT / "references/atomic-expectations/TEST_DESIGN_CURRENT.json"
ADDENDUM_SOURCE_PATH = ROOT / "work/advisory_returns_20260820_r01/atomic_test_design_r03_addendum/ATOMIC_TEST_DESIGN_R03_ADDENDUM.json"
ADDENDUM_INDEX_PATH = ROOT / "work/advisory_returns_20260820_r01/00_INDEX.md"
RUNTIME_GAP_PATH = ROOT / "work/advisory_returns_20260820_r01/current_runtime_gap_review_r01/CURRENT_RUNTIME_GAP_REGISTER_R01.json"
TRACEABILITY_PATH = ROOT / "governance/capability_traceability.json"
POINTERS_PATH = ROOT / "governance/current_pointers.json"

ADDENDUM_PACKAGE_ID = "ATOMIC_TEST_DESIGN_R03_ADDENDUM_20260821_R01"
ADDENDUM_DIR = ROOT / "references/atomic-expectations" / ADDENDUM_PACKAGE_ID
ADDENDUM_README = ADDENDUM_DIR / "00_READ_ME_FIRST.md"
ADDENDUM_DESIGN = ADDENDUM_DIR / "01_ATOMIC_TEST_DESIGN.json"
ADDENDUM_MANIFEST = ADDENDUM_DIR / "MANIFEST.json"
ADDENDUM_RECEIPT = ADDENDUM_DIR / "VALIDATION_RECEIPT.json"

TRACEABILITY_CHECKER_PATH = ROOT / "tools/check_traceability.py"
TRACEABILITY_TEST_PATH = ROOT / "tests/test_traceability.py"

EXPECTED_RUNTIME_COUNTS = {
    "DIRECT_CODE_EVIDENCE": 61,
    "PARTIAL_CODE_EVIDENCE": 43,
    "BACKGROUND_ONLY": 36,
    "CURRENT_PATH_CONFLICT": 2,
}
EXPECTED_EXECUTION_TIERS = {
    "MECHANICAL": 60,
    "SEMANTIC": 13,
    "NOT_EXECUTABLE": 17,
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from iter_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_dicts(nested)


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from iter_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_strings(nested)


def scalar_strings_by_path(value: Any, prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    if isinstance(value, dict):
        for key, nested in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(nested, str):
                result[path] = nested
            elif isinstance(nested, (dict, list)):
                result.update(scalar_strings_by_path(nested, path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            path = f"{prefix}[{index}]"
            if isinstance(nested, str):
                result[path] = nested
            elif isinstance(nested, (dict, list)):
                result.update(scalar_strings_by_path(nested, path))
    return result


def all_strings_by_key(value: Any, result: dict[str, set[str]] | None = None) -> dict[str, set[str]]:
    if result is None:
        result = collections.defaultdict(set)
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(nested, str):
                result[str(key)].add(nested)
            else:
                all_strings_by_key(nested, result)
    elif isinstance(value, list):
        for nested in value:
            all_strings_by_key(nested, result)
    return result


def normalized_owner_group(record: dict[str, Any], seed_row: dict[str, Any]) -> str:
    judgment = record.get("当前产品判断")
    candidates: list[str] = []
    if isinstance(judgment, dict):
        for key, value in judgment.items():
            if isinstance(value, str) and ("归组" in key or key in {"模块", "所属模块"}):
                candidates.append(value.strip())
    for key, value in record.items():
        if isinstance(value, str) and "归组" in key:
            candidates.append(value.strip())
    if not candidates:
        original = seed_row.get("original_group")
        if isinstance(original, str):
            candidates.append(original.strip())
    if not candidates:
        return "UNKNOWN"
    raw = candidates[0]
    aliases = {
        "AuthorWorkspace": "作者工作区",
        "AUTHOR_WORKSPACE": "作者工作区",
        "跨域": "跨模块",
        "CROSS_MODULE": "跨模块",
    }
    return aliases.get(raw, raw)


def review_owner(group: str, seed_owner: Any, requirement_text: str, seed_row: dict[str, Any]) -> tuple[str, str]:
    owner = seed_owner if isinstance(seed_owner, str) and seed_owner else "UNASSIGNED"
    modules = {f"M{i}" for i in range(1, 12)}
    shared = {
        "AUTHOR_WORKSPACE",
        "STORAGE",
        "ROUTER",
        "SECURITY",
        "SHARED_SERVICE",
        "OBSERVABILITY",
        "PROVIDER",
    }
    if group in modules:
        if owner == group:
            return owner, "R03_CURRENT_GROUP_MATCH"
        return "UNASSIGNED", f"R03_GROUP_{group}_BUT_SEED_OWNER_{owner}"
    if group == "作者工作区":
        if owner in shared:
            return owner, "R03_AUTHOR_WORKSPACE_GROUP_SHARED_OWNER_REVIEWED"
        return "UNASSIGNED", f"AUTHOR_WORKSPACE_GROUP_OWNER_UNSUPPORTED_{owner}"
    if group == "跨模块":
        if owner in shared:
            return owner, "R03_CROSS_MODULE_SHARED_OWNER_REVIEWED"
        return "UNASSIGNED", f"CROSS_MODULE_OWNER_UNSUPPORTED_{owner}"
    return "UNASSIGNED", f"UNKNOWN_R03_GROUP_{group}"


def classify_runtime_label(text: str) -> str | None:
    upper = text.upper().replace("-", "_").replace(" ", "_")
    if "CONFLICT" in upper or "相冲突" in text or "直接冲突" in text:
        return "CURRENT_PATH_CONFLICT"
    if "BACKGROUND" in upper or "仅背景" in text or "只有背景" in text:
        return "BACKGROUND_ONLY"
    if "PARTIAL" in upper or "局部证据" in text or "局部实现" in text:
        return "PARTIAL_CODE_EVIDENCE"
    if "DIRECT" in upper or "直接代码证据" in text or "直接证据" in text:
        return "DIRECT_CODE_EVIDENCE"
    return None


def extract_runtime_evidence(runtime_gap: Any, r03_ids: set[str]) -> dict[str, dict[str, Any]]:
    candidates: dict[str, list[tuple[int, dict[str, Any]]]] = collections.defaultdict(list)
    for node in iter_dicts(runtime_gap):
        strings = list(iter_strings(node))
        ids = sorted(set(strings) & r03_ids)
        if len(ids) != 1:
            continue
        req_id = ids[0]
        labels: list[tuple[int, str, str]] = []
        for path, value in scalar_strings_by_path(node).items():
            label = classify_runtime_label(value)
            if label is None:
                continue
            key_score = 0
            lower_path = path.lower()
            if any(token in lower_path for token in ("class", "evidence", "verdict", "status", "tier", "证据", "分层", "结论")):
                key_score += 10
            if value.upper() in {
                "DIRECT_CODE_EVIDENCE",
                "PARTIAL_CODE_EVIDENCE",
                "BACKGROUND_ONLY",
                "CURRENT_PATH_CONFLICT",
            }:
                key_score += 20
            labels.append((key_score, label, value))
        if not labels:
            continue
        labels.sort(reverse=True)
        score, label, raw = labels[0]
        score += max(0, 5000 - len(json_blob(node))) // 100
        candidates[req_id].append((score, {"classification": label, "raw": raw}))

    result: dict[str, dict[str, Any]] = {}
    for req_id, rows in candidates.items():
        rows.sort(key=lambda item: item[0], reverse=True)
        result[req_id] = rows[0][1]

    missing = sorted(r03_ids - set(result))
    counts = collections.Counter(item["classification"] for item in result.values())
    if missing or dict(counts) != EXPECTED_RUNTIME_COUNTS:
        print("RUNTIME_EVIDENCE_DIAGNOSTIC")
        print("mapped", len(result), "missing", missing[:30])
        print("counts", dict(counts))
        raise SystemExit("runtime evidence matrix did not resolve to 61/43/36/2")
    return result


def runtime_to_maturity(classification: str) -> str:
    return {
        "DIRECT_CODE_EVIDENCE": "MECHANICAL_RUNNABLE",
        "PARTIAL_CODE_EVIDENCE": "PARTIALLY_IMPLEMENTED",
        "BACKGROUND_ONLY": "REQUIREMENT_ONLY",
        "CURRENT_PATH_CONFLICT": "BLOCKED",
    }[classification]


def discover_local_evidence_ids(seed_rows: list[dict[str, Any]]) -> set[str]:
    markers = (
        "LOCAL_ONLY",
        "LOCAL-ONLY",
        "LOCAL_EVIDENCE",
        "LOCAL JOURNEY",
        "LOCAL_JOURNEY",
        "本地旅程",
        "本地作者旅程",
        "本地材料",
        "未分发旅程",
        "UNPUBLISHED JOURNEY",
        "NOT DISTRIBUTED",
    )
    ids: set[str] = set()
    for row in seed_rows:
        blob = json_blob(row)
        upper = blob.upper()
        if any(marker.upper() in upper for marker in markers):
            ids.add(row["requirement_id"])
    if len(ids) != 5:
        diagnostic = []
        for row in seed_rows:
            authorities = row.get("source_authority", [])
            blocked = row.get("blocked_by", [])
            if any(token in json_blob([authorities, blocked]).upper() for token in ("LOCAL", "JOURNEY", "旅程", "本地")):
                diagnostic.append((row["requirement_id"], authorities, blocked))
        print("LOCAL_EVIDENCE_DIAGNOSTIC", diagnostic)
        raise SystemExit(f"expected exactly 5 local-evidence requirements, found {len(ids)}: {sorted(ids)}")
    return ids


def collect_ids_from_any_strings(value: Any, valid_ids: set[str]) -> set[str]:
    return {text for text in iter_strings(value) if text in valid_ids}


def identify_test_case_nodes(addendum: Any) -> dict[str, dict[str, Any]]:
    cases: dict[str, tuple[int, dict[str, Any]]] = {}
    for node in iter_dicts(addendum):
        scalar = scalar_strings_by_path(node)
        ids = [value for path, value in scalar.items() if value.startswith("AT5-") and ("test" in path.lower() or "测试" in path or path.lower().endswith("id"))]
        for test_id in ids:
            score = max(0, 10000 - len(json_blob(node)))
            if test_id not in cases or score > cases[test_id][0]:
                cases[test_id] = (score, node)
    if len(cases) != 90:
        by_key = all_strings_by_key(addendum)
        diagnostic = {
            key: len({value for value in values if value.startswith("AT5-")})
            for key, values in by_key.items()
            if any(value.startswith("AT5-") for value in values)
        }
        print("AT5_CASE_DIAGNOSTIC", diagnostic)
        raise SystemExit(f"expected 90 AT5 test case nodes, found {len(cases)}")
    return {test_id: node for test_id, (_, node) in cases.items()}


def classify_execution_label(value: str) -> str | None:
    normalized = value.upper().replace("-", "_").replace(" ", "_")
    if any(token in normalized for token in ("NOT_EXECUTABLE", "UNEXECUTABLE", "CURRENTLY_BLOCKED", "FUTURE_ONLY")) or "暂不可执行" in value:
        return "NOT_EXECUTABLE"
    if "SEMANTIC" in normalized or "语义" in value:
        return "SEMANTIC"
    if "MECHANICAL" in normalized or "ZERO_API" in normalized or "机械" in value:
        return "MECHANICAL"
    return None


def determine_execution_tiers(cases: dict[str, dict[str, Any]]) -> tuple[dict[str, str], str]:
    paths = collections.defaultdict(dict)
    for test_id, node in cases.items():
        for path, value in scalar_strings_by_path(node).items():
            paths[path][test_id] = value

    for path, values in sorted(paths.items()):
        if len(values) != 90:
            continue
        mapped = {test_id: classify_execution_label(value) for test_id, value in values.items()}
        if any(value is None for value in mapped.values()):
            continue
        counts = collections.Counter(mapped.values())
        if dict(counts) == EXPECTED_EXECUTION_TIERS:
            return {test_id: value for test_id, value in mapped.items() if value is not None}, path

    mapped: dict[str, str] = {}
    for test_id, node in cases.items():
        labels: list[tuple[int, str]] = []
        for path, value in scalar_strings_by_path(node).items():
            label = classify_execution_label(value)
            if label is None:
                continue
            score = 0
            if any(token in path.lower() for token in ("execution", "layer", "tier", "level", "mode", "分层", "执行")):
                score += 20
            if value.upper().replace("-", "_").replace(" ", "_") in {
                "MECHANICAL",
                "SEMANTIC",
                "NOT_EXECUTABLE",
                "ZERO_API_MECHANICAL",
            }:
                score += 10
            labels.append((score, label))
        if not labels:
            raise SystemExit(f"no execution tier found for {test_id}")
        labels.sort(reverse=True)
        mapped[test_id] = labels[0][1]
    counts = collections.Counter(mapped.values())
    if dict(counts) != EXPECTED_EXECUTION_TIERS:
        print("EXECUTION_TIER_DIAGNOSTIC", dict(counts))
        raise SystemExit("execution tier counts did not match 60/13/17")
    return mapped, "NODE_SCALAR_FALLBACK"


def extract_external_lane_only(addendum: Any, old_design: Any) -> list[dict[str, Any]]:
    old_test_ids = {
        value
        for value in iter_strings(old_design)
        if isinstance(value, str) and re.match(r"^AT[1-4]-", value)
    }
    annotations: dict[str, dict[str, Any]] = {}
    for node in iter_dicts(addendum):
        if not any("EXTERNAL_LANE_ONLY" in value for value in iter_strings(node)):
            continue
        node_test_ids = sorted(set(iter_strings(node)) & old_test_ids)
        node_requirement_ids = sorted(
            value for value in set(iter_strings(node)) if re.match(r"^(?:AE-|M\d-)", value)
        )
        for test_id in node_test_ids:
            annotations[test_id] = {
                "test_id": test_id,
                "scope": "EXTERNAL_LANE_ONLY",
                "requirement_ids": node_requirement_ids,
                "sources": [
                    "work/advisory_returns_20260820_r01/atomic_test_design_r03_addendum/ATOMIC_TEST_DESIGN_R03_ADDENDUM.json",
                    "references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md#R14-新增的共同口径",
                    "references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/03_CREATION_AND_MEMORY_PIPELINES.md",
                ],
                "boundary": "旧测试正文保留不动；该测试只用于外来旧章／外部手写书稿车道，不得套到产品自产章事实稿车道。",
            }
    if len(annotations) != 42:
        print("EXTERNAL_LANE_DIAGNOSTIC", len(annotations), sorted(annotations)[:20])
        raise SystemExit(f"expected 42 EXTERNAL_LANE_ONLY old tests, found {len(annotations)}")
    return [annotations[key] for key in sorted(annotations)]


def build_traceability() -> dict[str, Any]:
    seed = read_json(SEED_PATH)
    schema = read_json(SCHEMA_PATH)
    r03 = read_json(R03_PATH)
    old_design = read_json(OLD_DESIGN_PATH)
    addendum = read_json(ADDENDUM_SOURCE_PATH)
    runtime_gap = read_json(RUNTIME_GAP_PATH)

    seed_rows = seed.get("requirements")
    r03_rows = r03.get("records")
    if not isinstance(seed_rows, list) or len(seed_rows) != 142:
        raise SystemExit("traceability seed does not contain 142 requirements")
    if not isinstance(r03_rows, list) or len(r03_rows) != 142:
        raise SystemExit("R03 does not contain 142 records")

    seed_by_id = {row["requirement_id"]: row for row in seed_rows}
    r03_by_id = {row["预期ID"]: row for row in r03_rows}
    if len(seed_by_id) != 142 or len(r03_by_id) != 142 or set(seed_by_id) != set(r03_by_id):
        raise SystemExit("seed IDs and R03 IDs are not the same 142-item set")
    for req_id in sorted(r03_by_id):
        if seed_by_id[req_id].get("requirement_text") != r03_by_id[req_id].get("长期需求"):
            raise SystemExit(f"requirement text mismatch for {req_id}")

    r03_ids = set(r03_by_id)
    old_ids = collect_ids_from_any_strings(old_design, r03_ids)
    if len(old_ids) != 127:
        raise SystemExit(f"old test design should reference 127 R03 IDs, found {len(old_ids)}")
    new_ids = r03_ids - old_ids
    if len(new_ids) != 15:
        raise SystemExit(f"R03 addendum set should have 15 IDs, found {len(new_ids)}")

    cases = identify_test_case_nodes(addendum)
    tier_by_test, tier_source_path = determine_execution_tiers(cases)
    tests_by_requirement: dict[str, list[str]] = collections.defaultdict(list)
    for test_id, node in cases.items():
        ids = sorted(collect_ids_from_any_strings(node, new_ids))
        if not ids:
            ids = sorted(req_id for req_id in new_ids if req_id in test_id)
        if len(ids) != 1:
            raise SystemExit(f"could not map {test_id} to exactly one new requirement: {ids}")
        tests_by_requirement[ids[0]].append(test_id)
    if set(tests_by_requirement) != new_ids or any(len(items) != 6 for items in tests_by_requirement.values()):
        raise SystemExit("AT5 addendum does not map to 15 requirements × 6 tests")

    runtime = extract_runtime_evidence(runtime_gap, r03_ids)
    local_ids = discover_local_evidence_ids(seed_rows)
    external_annotations = extract_external_lane_only(addendum, old_design)

    result_rows: list[dict[str, Any]] = []
    for req_id in sorted(r03_ids):
        seed_row = copy.deepcopy(seed_by_id[req_id])
        r03_row = r03_by_id[req_id]
        group = normalized_owner_group(r03_row, seed_row)
        reviewed_owner, owner_reason = review_owner(
            group,
            seed_row.get("primary_owner"),
            seed_row.get("requirement_text", ""),
            seed_row,
        )
        seed_row["primary_owner_candidate"] = seed_row.get("primary_owner")
        seed_row["primary_owner"] = reviewed_owner
        allowed_shared = {
            *(f"M{i}" for i in range(1, 12)),
            "AUTHOR_WORKSPACE",
            "STORAGE",
            "ROUTER",
            "SECURITY",
            "SHARED_SERVICE",
            "OBSERVABILITY",
            "PROVIDER",
        }
        shared = seed_row.get("shared_owners", [])
        if not isinstance(shared, list):
            shared = []
        seed_row["shared_owners"] = sorted(
            {
                owner
                for owner in shared
                if isinstance(owner, str)
                and owner in allowed_shared
                and owner != reviewed_owner
            }
        )
        seed_row["owner_review"] = {
            "status": "CANDIDATE_REVIEWED" if reviewed_owner != "UNASSIGNED" else "UNASSIGNED_PENDING_OWNER",
            "r03_current_group": group,
            "seed_owner": seed_row.get("primary_owner_candidate"),
            "decision": reviewed_owner,
            "reason": owner_reason,
            "sources": [
                "references/atomic-expectations/CURRENT.json",
                f"references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json#{req_id}",
                "references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md",
            ],
        }

        evidence = runtime[req_id]
        seed_row["maturity_candidate_before_runtime_review"] = seed_row.get("maturity")
        seed_row["maturity"] = runtime_to_maturity(evidence["classification"])
        seed_row["maturity_evidence"] = {
            "classification": evidence["classification"],
            "raw_classification": evidence["raw"],
            "source": (
                "work/advisory_returns_20260820_r01/current_runtime_gap_review_r01/"
                f"CURRENT_RUNTIME_GAP_REGISTER_R01.json#{req_id}"
            ),
            "boundary": "代码证据分层只产生候选成熟度，不证明真实小说语义或作者可用性。",
        }

        authorities = seed_row.get("source_authority", [])
        if isinstance(authorities, str):
            authorities = [authorities]
        if not isinstance(authorities, list):
            authorities = []
        seed_row["source_authority_candidate"] = copy.deepcopy(authorities)
        if req_id == "M3-B03":
            seed_row["source_authority"] = ["PENDING_CZ_SOURCE"]
            seed_row["source_exemption"] = {
                "status": "PENDING_CZ_SOURCE",
                "reason": "R14 尚未找到 fact_core＋qualifiers 的唯一上游裁定来源；不得用设计或实现反推产品需求。",
                "decision_required": "CZ 补 R14 对应段落或新增 ADD 拍板。",
            }
            blocked = seed_row.get("blocked_by", [])
            if not isinstance(blocked, list):
                blocked = []
            seed_row["blocked_by"] = sorted(set(blocked + ["PENDING_CZ_SOURCE"]))
        else:
            normalized_authorities = [item for item in authorities if isinstance(item, str) and item]
            if "R03_ATOMIC_EXPECTATION_CURRENT" not in normalized_authorities:
                normalized_authorities.append("R03_ATOMIC_EXPECTATION_CURRENT")
            seed_row["source_authority"] = normalized_authorities

        if req_id in local_ids:
            seed_row["local_evidence_status"] = "LOCAL_EVIDENCE_PENDING"
            blocked = seed_row.get("blocked_by", [])
            if not isinstance(blocked, list):
                blocked = []
            seed_row["blocked_by"] = sorted(set(blocked + ["LOCAL_EVIDENCE_PENDING"]))
            seed_row.setdefault("evidence_notes", []).append(
                "本票不读取或上传 CZ 本地作者旅程原文；后续只允许补最小可公开证据卡。"
            )
        else:
            seed_row["local_evidence_status"] = "NOT_APPLICABLE"

        if req_id in new_ids:
            old_priority = seed_row.get("priority")
            seed_row["priority_candidate"] = old_priority
            seed_row["priority"] = "PENDING_CZ"
            seed_row["test_refs"] = sorted(
                set(
                    [item for item in seed_row.get("test_refs", []) if isinstance(item, str)]
                    + [
                        (
                            "references/atomic-expectations/"
                            f"{ADDENDUM_PACKAGE_ID}/01_ATOMIC_TEST_DESIGN.json#{req_id}"
                        )
                    ]
                )
            )
            seed_row["test_design_status"] = "SIX_CASES_DESIGNED_R03_ADDENDUM_CANDIDATE"
            seed_row["addendum_test_ids"] = sorted(tests_by_requirement[req_id])
            seed_row["addendum_execution_tiers"] = dict(
                collections.Counter(tier_by_test[test_id] for test_id in tests_by_requirement[req_id])
            )
        else:
            seed_row["priority_candidate"] = None

        seed_row["review_identity"] = "CANDIDATE_REVIEWED"
        seed_row["claim_boundary"] = "CANDIDATE_REVIEWED_NOT_PRODUCT_OR_EXECUTION_AUTHORITY"
        result_rows.append(seed_row)

    owner_counts = collections.Counter(row["primary_owner"] for row in result_rows)
    maturity_counts = collections.Counter(row["maturity"] for row in result_rows)
    runtime_counts = collections.Counter(row["maturity_evidence"]["classification"] for row in result_rows)
    if dict(runtime_counts) != EXPECTED_RUNTIME_COUNTS:
        raise SystemExit("traceability runtime evidence counts changed during materialization")

    result = {
        "schema_version": seed["schema_version"],
        "authority": seed["authority"],
        "review_status": "CANDIDATE_REVIEWED",
        "review_date": "2026-08-21",
        "repository": "mhchen1/novel-architecture",
        "base_commit": BASE_SHA,
        "product_background": "R14",
        "atomic_expectations_background": "R03",
        "schema_candidate_source": str(SCHEMA_PATH.relative_to(ROOT)),
        "seed_source": str(SEED_PATH.relative_to(ROOT)),
        "runtime_evidence_source": str(RUNTIME_GAP_PATH.relative_to(ROOT)),
        "test_addendum_source": str(ADDENDUM_SOURCE_PATH.relative_to(ROOT)),
        "claim_boundary": (
            "142/142 mapped means the candidate relationship table is complete; it does not mean "
            "142 requirements are implemented, semantically proven, or author-usable."
        ),
        "statistics": {
            "requirements": len(result_rows),
            "unique_ids": len({row["requirement_id"] for row in result_rows}),
            "owner_counts": dict(sorted(owner_counts.items())),
            "unassigned": owner_counts.get("UNASSIGNED", 0),
            "maturity_counts": dict(sorted(maturity_counts.items())),
            "runtime_evidence_counts": dict(sorted(runtime_counts.items())),
            "priority_pending_cz": sum(row.get("priority") == "PENDING_CZ" for row in result_rows),
            "local_evidence_pending": sum(row.get("local_evidence_status") == "LOCAL_EVIDENCE_PENDING" for row in result_rows),
            "pending_cz_source": sum("PENDING_CZ_SOURCE" in row.get("source_authority", []) for row in result_rows),
            "old_six_case_requirements": len(old_ids),
            "new_addendum_requirements": len(new_ids),
            "new_addendum_tests": len(cases),
            "legacy_external_lane_only_tests": len(external_annotations),
        },
        "requirements": result_rows,
    }
    return result


def build_addendum_package(traceability: dict[str, Any]) -> dict[str, Any]:
    source = read_json(ADDENDUM_SOURCE_PATH)
    old_design = read_json(OLD_DESIGN_PATH)
    index_text = ADDENDUM_INDEX_PATH.read_text(encoding="utf-8")
    window_sha = source["source_verification"]["window_package"]["sha256"]
    if window_sha not in index_text:
        raise SystemExit("addendum source ZIP SHA is absent from advisory return index")

    r03_ids = {row["requirement_id"] for row in traceability["requirements"]}
    old_ids = collect_ids_from_any_strings(old_design, r03_ids)
    new_ids = sorted(r03_ids - old_ids)
    cases = identify_test_case_nodes(source)
    tier_by_test, tier_field = determine_execution_tiers(cases)
    tests_by_requirement: dict[str, list[str]] = collections.defaultdict(list)
    for test_id, node in cases.items():
        ids = sorted(collect_ids_from_any_strings(node, set(new_ids)))
        if not ids:
            ids = sorted(req_id for req_id in new_ids if req_id in test_id)
        if len(ids) != 1:
            raise SystemExit(f"cannot map addendum test {test_id} to one requirement")
        tests_by_requirement[ids[0]].append(test_id)

    annotations = extract_external_lane_only(source, old_design)
    design_payload = {
        "schema_version": "atomic-test-design-r03-addendum-package-v1",
        "package_id": ADDENDUM_PACKAGE_ID,
        "identity": "ADVISORY_TEST_DESIGN_ACCEPTED_FOR_FIXTURE_PREPARATION_NOT_EXECUTED",
        "authority": "TEST_DESIGN_ONLY_NO_PRODUCT_OR_EXECUTION_AUTHORITY",
        "requirement_background": "R03",
        "coverage": {
            "requirement_count": 15,
            "small_test_count": 90,
            "tests_per_requirement": 6,
            "requirement_ids": new_ids,
            "test_ids": sorted(cases),
            "execution_tiers": dict(sorted(collections.Counter(tier_by_test.values()).items())),
            "tier_source_field": tier_field,
        },
        "priority": {
            "status": "PENDING_CZ",
            "boundary": "回包与决策书中的优先级仅保留为 candidate，不改变 R03 正文或权重。",
        },
        "source": {
            "path": str(ADDENDUM_SOURCE_PATH.relative_to(ROOT)),
            "sha256": sha256(ADDENDUM_SOURCE_PATH),
            "window_package_sha256": window_sha,
            "index_path": str(ADDENDUM_INDEX_PATH.relative_to(ROOT)),
            "source_authority": source.get("authority_boundary"),
        },
        "legacy_external_lane_only": {
            "count": len(annotations),
            "annotations": annotations,
            "boundary": "只登记范围改判；旧 127×6 测试正文、ID、权重和原包字节全部不改。",
        },
        "requirement_summaries": [
            {
                "requirement_id": req_id,
                "priority": "PENDING_CZ",
                "test_ids": sorted(tests_by_requirement[req_id]),
                "execution_tiers": dict(
                    sorted(collections.Counter(tier_by_test[test_id] for test_id in tests_by_requirement[req_id]).items())
                ),
            }
            for req_id in new_ids
        ],
        "source_advisory_payload": source,
    }

    ADDENDUM_DIR.mkdir(parents=True, exist_ok=True)
    write_json(ADDENDUM_DESIGN, design_payload)
    ADDENDUM_README.write_text(
        f"""# 原子六例测试设计 R03 增补包｜先读本页

- 包 ID：`{ADDENDUM_PACKAGE_ID}`
- 身份：`ADVISORY_TEST_DESIGN_ACCEPTED_FOR_FIXTURE_PREPARATION_NOT_EXECUTED`
- 对应需求：R03 新增 15 条；每条 6 例，共 90 例。
- 执行分层：60 机械、13 语义、17 暂不可执行。
- 优先级：15 条全部 `PENDING_CZ`；回包建议只保留为 candidate。
- 来源回包 ZIP SHA-256：`{window_sha}`

## 与旧包的关系

旧包 `ATOMIC_TEST_DESIGN_20260820_R01` 原样保留，仍只覆盖 R02 的 127 条／762 例。本包只补 R03 新增 15 条／90 例；两者不能互相冒充。

## 双车道范围注记

本包登记 42 个旧小测试为 `EXTERNAL_LANE_ONLY`。这只是范围改判：旧测试正文、ID、权重和冻结字节均不改；它们只适用于外来旧章／外部手写书稿车道，不得套到产品自产章事实稿车道。

## 权限边界

本包是测试设计和审计材料，不是产品拍板、正式合同、代码完成证明、API／训练／Gold／生产许可，也不证明真实小说语义质量。

来源：ChatGPT（工单 3 云端候选；吸收既有顾问回包）
""",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": "atomic-test-design-addendum-manifest-v1",
        "package_id": ADDENDUM_PACKAGE_ID,
        "files": [
            {
                "path": ADDENDUM_README.name,
                "bytes": ADDENDUM_README.stat().st_size,
                "sha256": sha256(ADDENDUM_README),
            },
            {
                "path": ADDENDUM_DESIGN.name,
                "bytes": ADDENDUM_DESIGN.stat().st_size,
                "sha256": sha256(ADDENDUM_DESIGN),
            },
            {"path": ADDENDUM_MANIFEST.name, "bytes": None, "sha256": None},
        ],
    }
    write_json(ADDENDUM_MANIFEST, manifest)

    receipt = {
        "schema_version": "atomic-test-design-addendum-validation-receipt-v1",
        "package_id": ADDENDUM_PACKAGE_ID,
        "status": "PASS",
        "requirement_count": 15,
        "small_test_count": 90,
        "tests_per_requirement": 6,
        "unique_requirement_ids": 15,
        "unique_test_ids": 90,
        "execution_tiers": EXPECTED_EXECUTION_TIERS,
        "legacy_external_lane_only_test_count": 42,
        "priority_pending_cz": 15,
        "source_window_zip_sha256": window_sha,
        "source_advisory_sha256": sha256(ADDENDUM_SOURCE_PATH),
        "design_sha256": sha256(ADDENDUM_DESIGN),
        "manifest_sha256": sha256(ADDENDUM_MANIFEST),
        "checks": [
            "AT5_IDS_90_UNIQUE",
            "REQUIREMENTS_15_EACH_SIX_CASES",
            "EXECUTION_TIERS_60_13_17",
            "LEGACY_EXTERNAL_LANE_ONLY_42",
            "SOURCE_ZIP_SHA_MATCHES_ADVISORY_INDEX",
            "PRIORITY_ALL_PENDING_CZ",
        ],
        "boundary": "Mechanical validation of the design package; not execution or semantic quality proof.",
    }
    write_json(ADDENDUM_RECEIPT, receipt)
    return receipt


def update_test_design_pointer(addendum_receipt: dict[str, Any]) -> None:
    old_pointer = read_json(OLD_POINTER_PATH)
    aggregate = {
        "schema_version": "atomic-test-design-current-registry-v2",
        "identity": "ATOMIC_TEST_DESIGN_R03_COMPOSITE_CURRENT",
        "requirement_background": "R03",
        "status": "ADVISORY_TEST_DESIGN_ACCEPTED_FOR_FIXTURE_PREPARATION_NOT_EXECUTED",
        "coverage": {
            "requirements_total": 142,
            "small_tests_total": 852,
            "legacy_requirements": 127,
            "legacy_small_tests": 762,
            "r03_addendum_requirements": 15,
            "r03_addendum_small_tests": 90,
            "full_six_case_design_coverage": True,
        },
        "suites": [
            {
                "suite_id": old_pointer["identity"],
                "role": "LEGACY_R02_BASE_SUITE",
                "requirement_scope": "R02_127_ONLY",
                "requirement_count": 127,
                "small_test_count": 762,
                "entry": old_pointer["entry"],
                "design": old_pointer["design"],
                "design_sha256": old_pointer["design_sha256"],
                "validation_receipt": old_pointer["validation_receipt"],
                "validation_receipt_sha256": old_pointer["validation_receipt_sha256"],
                "status": old_pointer["status"],
                "boundary": "原包字节不改；不能冒充覆盖 R03 新增 15 条。",
            },
            {
                "suite_id": ADDENDUM_PACKAGE_ID,
                "role": "R03_NEW_15_ADDENDUM",
                "requirement_scope": "R03_NEW_15_ONLY",
                "requirement_count": 15,
                "small_test_count": 90,
                "entry": f"{ADDENDUM_PACKAGE_ID}/00_READ_ME_FIRST.md",
                "design": f"{ADDENDUM_PACKAGE_ID}/01_ATOMIC_TEST_DESIGN.json",
                "design_sha256": addendum_receipt["design_sha256"],
                "manifest": f"{ADDENDUM_PACKAGE_ID}/MANIFEST.json",
                "manifest_sha256": addendum_receipt["manifest_sha256"],
                "validation_receipt": f"{ADDENDUM_PACKAGE_ID}/VALIDATION_RECEIPT.json",
                "status": "ADVISORY_TEST_DESIGN_ACCEPTED_FOR_FIXTURE_PREPARATION_NOT_EXECUTED",
                "execution_tiers": EXPECTED_EXECUTION_TIERS,
                "priority_status": "PENDING_CZ",
                "boundary": "只补 15×6；不改变 R03 正文、ID、权重或产品优先级。",
            },
        ],
        "legacy_scope_annotations": {
            "scope": "EXTERNAL_LANE_ONLY",
            "test_count": 42,
            "registry_path": f"{ADDENDUM_PACKAGE_ID}/01_ATOMIC_TEST_DESIGN.json#legacy_external_lane_only",
            "boundary": "旧测试正文不改，只登记外来道适用范围。",
        },
        "anti_masquerade_rules": [
            "127×6 old suite is not the R03 full suite by itself.",
            "15×6 addendum does not replace or rewrite the old 127×6 suite.",
            "Composite 142×6 design coverage is still advisory design, not executed proof.",
        ],
    }
    write_json(OLD_POINTER_PATH, aggregate)


def update_current_pointers(traceability: dict[str, Any]) -> None:
    data = read_json(POINTERS_PATH)
    data["updated_at"] = UPDATED_AT
    rows = data.get("pointers")
    if not isinstance(rows, list):
        raise SystemExit("current_pointers.pointers is not a list")
    by_id = {row.get("pointer_id"): row for row in rows if isinstance(row, dict)}
    trace = by_id.get("capability_traceability")
    if not isinstance(trace, dict):
        raise SystemExit("current_pointers lacks capability_traceability row")
    trace.clear()
    trace.update(
        {
            "pointer_id": "capability_traceability",
            "status": "CANDIDATE_REVIEWED",
            "version": "R01",
            "path": "governance/capability_traceability.json",
            "record_count": 142,
            "unassigned_count": traceability["statistics"]["unassigned"],
            "checker_path": "tools/check_traceability.py",
            "checker_registry_status": "PENDING_WORK_ORDER_7",
            "authority": "ADVISORY_ONLY_NO_PRODUCT_OR_EXECUTION_AUTHORITY",
            "boundary": "142/142 候选追踪已复核，不等于 142 条实现完成或产品拍板。",
            "admitted_by_work_order": 3,
        }
    )
    test_design = by_id.get("atomic_test_design")
    if not isinstance(test_design, dict):
        raise SystemExit("current_pointers lacks atomic_test_design row")
    test_design.update(
        {
            "status": "ACTIVE_CURRENT",
            "version": "R03_COMPOSITE_127_PLUS_15",
            "path": "references/atomic-expectations/TEST_DESIGN_CURRENT.json",
            "covered_expectations": 142,
            "designed_test_cases": 852,
            "scope_status": "CURRENT_ADVISORY_DESIGN_FULL_R03_COVERAGE_NOT_EXECUTED",
            "legacy_suite": {"requirements": 127, "small_tests": 762},
            "r03_addendum": {"requirements": 15, "small_tests": 90},
            "boundary": "旧 127×6 与新增 15×6 身份分开；组合覆盖仍是设计，不是执行证明。",
        }
    )
    write_json(POINTERS_PATH, data)


CHECKER_SOURCE = r'''#!/usr/bin/env python3
"""Read-only validator for the reviewed-candidate capability traceability table."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

REQUIRED_ROW_FIELDS = {
    "requirement_id",
    "requirement_level",
    "requirement_text",
    "journey_stage",
    "primary_owner",
    "shared_owners",
    "capability_type",
    "truth_write_level",
    "source_authority",
    "maturity",
    "review_identity",
}
CAPABILITY_TYPES = {
    "SEMANTIC",
    "MECHANICAL",
    "TRANSPORT",
    "PERSISTENCE",
    "SECURITY",
    "HUMAN_DECISION",
    "RENDERING",
    "OBSERVABILITY",
}
TRUTH_LEVELS = {
    "READ_ONLY",
    "PROJECTION_ONLY",
    "CANDIDATE_WRITE",
    "AUTHOR_CONFIRMED_WRITE",
    "SYSTEM_STATE_WRITE",
}
MATURITY = {
    "REQUIREMENT_ONLY",
    "TEST_DESIGNED",
    "FIXTURE_READY",
    "MECHANICAL_RUNNABLE",
    "SEMANTIC_RUNNABLE",
    "PARTIALLY_IMPLEMENTED",
    "INDEPENDENT_TOOL",
    "AUTHOR_USABLE",
    "MAIN_LOOP_INTEGRATED",
    "BLOCKED",
}
REQUIREMENT_LEVELS = {
    "NORTH_STAR",
    "CORE_CAPABILITY",
    "ATOMIC_EXPECTATION",
    "ACCEPTANCE_CASE",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def issue(level: str, code: str, requirement_id: str | None, message: str) -> dict[str, Any]:
    value: dict[str, Any] = {"level": level, "code": code, "message": message}
    if requirement_id is not None:
        value["requirement_id"] = requirement_id
    return value


def build_report(root: Path, traceability: dict[str, Any] | None = None) -> dict[str, Any]:
    root = root.resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    trace_path = root / "governance/capability_traceability.json"
    r03_path = root / "references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json"
    pointer_path = root / "references/atomic-expectations/TEST_DESIGN_CURRENT.json"

    if traceability is None:
        if not trace_path.is_file():
            return {
                "schema_version": "traceability-check-report-v1",
                "status": "FAIL",
                "errors": [issue("ERROR", "TRACEABILITY_MISSING", None, str(trace_path))],
                "warnings": [],
            }
        traceability = load_json(trace_path)

    if traceability.get("schema_version") != "capability-traceability-candidate-r01":
        errors.append(issue("ERROR", "SCHEMA_VERSION", None, "unexpected traceability schema_version"))
    if traceability.get("authority") != "ADVISORY_ONLY_NO_PRODUCT_OR_EXECUTION_AUTHORITY":
        errors.append(issue("ERROR", "AUTHORITY", None, "traceability authority changed"))
    if traceability.get("review_status") != "CANDIDATE_REVIEWED":
        errors.append(issue("ERROR", "REVIEW_STATUS", None, "review_status must be CANDIDATE_REVIEWED"))

    rows = traceability.get("requirements")
    if not isinstance(rows, list):
        errors.append(issue("ERROR", "ROWS_TYPE", None, "requirements must be a list"))
        rows = []
    if len(rows) != 142:
        errors.append(issue("ERROR", "ROW_COUNT", None, f"expected 142 rows, found {len(rows)}"))

    ids: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(issue("ERROR", "ROW_SCHEMA", None, f"row {index} is not an object"))
            continue
        req_id = row.get("requirement_id")
        if not isinstance(req_id, str) or not req_id:
            errors.append(issue("ERROR", "REQUIREMENT_ID", None, f"row {index} lacks requirement_id"))
            req_id = None
        else:
            ids.append(req_id)
        missing = sorted(REQUIRED_ROW_FIELDS - set(row))
        if missing:
            errors.append(issue("ERROR", "MISSING_FIELDS", req_id, f"missing {missing}"))
            continue
        if not isinstance(row.get("primary_owner"), str) or not row["primary_owner"]:
            errors.append(issue("ERROR", "OWNER_FIELD", req_id, "primary_owner must be a non-empty string; UNASSIGNED is legal"))
        if row.get("requirement_level") not in REQUIREMENT_LEVELS:
            errors.append(issue("ERROR", "REQUIREMENT_LEVEL", req_id, str(row.get("requirement_level"))))
        capability = row.get("capability_type")
        if not isinstance(capability, list) or not capability or any(item not in CAPABILITY_TYPES for item in capability):
            errors.append(issue("ERROR", "CAPABILITY_TYPE", req_id, str(capability)))
        if row.get("truth_write_level") not in TRUTH_LEVELS:
            errors.append(issue("ERROR", "TRUTH_WRITE_LEVEL", req_id, str(row.get("truth_write_level"))))
        if row.get("maturity") not in MATURITY:
            errors.append(issue("ERROR", "MATURITY", req_id, str(row.get("maturity"))))
        if row.get("review_identity") != "CANDIDATE_REVIEWED":
            errors.append(issue("ERROR", "ROW_REVIEW_IDENTITY", req_id, str(row.get("review_identity"))))
        authorities = row.get("source_authority")
        if not isinstance(authorities, list) or not authorities or any(not isinstance(item, str) or not item for item in authorities):
            errors.append(issue("ERROR", "SOURCE_AUTHORITY", req_id, str(authorities)))

        if row.get("primary_owner") == "UNASSIGNED":
            warnings.append(issue("WARNING", "REQUIREMENT_UNASSIGNED", req_id, "owner remains explicitly unassigned"))
        implementation_refs = row.get("implementation_refs", [])
        mapping_evidence = row.get("implementation_mapping_evidence")
        if implementation_refs and (not mapping_evidence or "PENDING_CZ_SOURCE" in authorities):
            warnings.append(issue("WARNING", "IMPLEMENTATION_WITHOUT_SOURCE", req_id, "implementation references lack a non-pending mapping source"))
        test_refs = row.get("test_refs", [])
        test_status = row.get("test_design_status")
        if not test_refs or not test_status:
            warnings.append(issue("WARNING", "TEST_WITHOUT_SOURCE", req_id, "test design or source reference is missing"))
        if row.get("local_evidence_status") == "LOCAL_EVIDENCE_PENDING":
            warnings.append(issue("WARNING", "LOCAL_EVIDENCE_PENDING", req_id, "local journey evidence card is intentionally deferred"))
        if "PENDING_CZ_SOURCE" in authorities:
            warnings.append(issue("WARNING", "PENDING_CZ_SOURCE", req_id, "upstream product source remains pending"))

    duplicates = sorted({req_id for req_id in ids if ids.count(req_id) > 1})
    if duplicates:
        errors.append(issue("ERROR", "DUPLICATE_IDS", None, str(duplicates)))

    if r03_path.is_file():
        r03 = load_json(r03_path)
        r03_rows = r03.get("records", [])
        r03_by_id = {row.get("预期ID"): row for row in r03_rows if isinstance(row, dict)}
        if set(ids) != set(r03_by_id):
            errors.append(issue("ERROR", "R03_ID_SET", None, "traceability IDs differ from R03"))
        for row in rows:
            if not isinstance(row, dict):
                continue
            req_id = row.get("requirement_id")
            if req_id in r03_by_id and row.get("requirement_text") != r03_by_id[req_id].get("长期需求"):
                errors.append(issue("ERROR", "REQUIREMENT_TEXT_CHANGED", req_id, "traceability text differs from R03"))
    else:
        errors.append(issue("ERROR", "R03_MISSING", None, str(r03_path)))

    if not pointer_path.is_file():
        errors.append(issue("ERROR", "TEST_POINTER_MISSING", None, str(pointer_path)))
    else:
        pointer = load_json(pointer_path)
        coverage = pointer.get("coverage", {})
        if coverage.get("requirements_total") != 142 or coverage.get("small_tests_total") != 852:
            errors.append(issue("ERROR", "TEST_POINTER_COVERAGE", None, str(coverage)))
        suites = pointer.get("suites", [])
        if len(suites) != 2:
            errors.append(issue("ERROR", "TEST_SUITE_COUNT", None, "current test registry must contain legacy base plus R03 addendum"))

    warning_counts: dict[str, int] = {}
    for item in warnings:
        warning_counts[item["code"]] = warning_counts.get(item["code"], 0) + 1
    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": "traceability-check-report-v1",
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "row_count": len(rows),
            "unique_id_count": len(set(ids)),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "warning_counts": dict(sorted(warning_counts.items())),
            "unassigned_count": sum(isinstance(row, dict) and row.get("primary_owner") == "UNASSIGNED" for row in rows),
        },
    }


def render_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Capability traceability check",
        "",
        f"- status: `{report.get('status')}`",
        f"- rows: `{summary.get('row_count', 0)}`",
        f"- unique IDs: `{summary.get('unique_id_count', 0)}`",
        f"- errors: `{summary.get('error_count', len(report.get('errors', [])))}`",
        f"- warnings: `{summary.get('warning_count', len(report.get('warnings', [])))}`",
        f"- UNASSIGNED: `{summary.get('unassigned_count', 0)}`",
        f"- warning classes: `{json.dumps(summary.get('warning_counts', {}), ensure_ascii=False, sort_keys=True)}`",
    ]
    if report.get("errors"):
        lines.extend(["", "## Errors"])
        for item in report["errors"]:
            lines.append(f"- `{item['code']}` `{item.get('requirement_id', '-')}` {item['message']}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("summary", "json", "both"), default="summary")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.root)
    summary = render_summary(report)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(summary, encoding="utf-8")
    if args.format in {"json", "both"}:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.format in {"summary", "both"}:
        print(summary, end="")
    if args.check:
        print(
            f"{'PASS_TRACEABILITY' if report['status'] == 'PASS' else 'FAIL_TRACEABILITY'} "
            f"errors={len(report.get('errors', []))} warnings={len(report.get('warnings', []))}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


TEST_SOURCE = r'''from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "check_traceability.py"
SPEC = importlib.util.spec_from_file_location("check_traceability", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ROOT = Path(__file__).resolve().parents[1]
TRACE = json.loads((ROOT / "governance/capability_traceability.json").read_text(encoding="utf-8"))


def error_codes(report: dict) -> set[str]:
    return {item["code"] for item in report["errors"]}


def test_repo_traceability_has_zero_errors() -> None:
    report = MODULE.build_report(ROOT)
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["summary"]["row_count"] == 142
    assert report["summary"]["unique_id_count"] == 142


def test_duplicate_id_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"][1]["requirement_id"] = value["requirements"][0]["requirement_id"]
    report = MODULE.build_report(ROOT, value)
    assert "DUPLICATE_IDS" in error_codes(report)


def test_wrong_row_count_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"].pop()
    report = MODULE.build_report(ROOT, value)
    assert "ROW_COUNT" in error_codes(report)


def test_missing_owner_field_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"][0].pop("primary_owner")
    report = MODULE.build_report(ROOT, value)
    assert "MISSING_FIELDS" in error_codes(report)


def test_schema_enum_mismatch_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"][0]["capability_type"] = ["NOT_A_CAPABILITY_TYPE"]
    report = MODULE.build_report(ROOT, value)
    assert "CAPABILITY_TYPE" in error_codes(report)


def test_checker_is_read_only() -> None:
    tracked = [
        ROOT / "governance/capability_traceability.json",
        ROOT / "references/atomic-expectations/TEST_DESIGN_CURRENT.json",
        ROOT / "references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json",
    ]
    before = {path: path.read_bytes() for path in tracked}
    MODULE.build_report(ROOT)
    after = {path: path.read_bytes() for path in tracked}
    assert before == after
'''


def write_checker_and_tests() -> None:
    TRACEABILITY_CHECKER_PATH.write_text(CHECKER_SOURCE, encoding="utf-8")
    TRACEABILITY_TEST_PATH.write_text(TEST_SOURCE, encoding="utf-8")


def main() -> None:
    for path in (SEED_PATH, SCHEMA_PATH, R03_PATH, R14_ENTRY, OLD_DESIGN_PATH, OLD_POINTER_PATH, ADDENDUM_SOURCE_PATH, ADDENDUM_INDEX_PATH, RUNTIME_GAP_PATH, POINTERS_PATH):
        if not path.is_file():
            raise SystemExit(f"required WO3 input missing: {path.relative_to(ROOT)}")

    traceability = build_traceability()
    write_json(TRACEABILITY_PATH, traceability)
    addendum_receipt = build_addendum_package(traceability)
    update_test_design_pointer(addendum_receipt)
    update_current_pointers(traceability)
    write_checker_and_tests()

    print("PASS_WO3_MATERIALIZATION")
    print("requirements=142")
    print(f"unassigned={traceability['statistics']['unassigned']}")
    print(f"local_evidence_pending={traceability['statistics']['local_evidence_pending']}")
    print(f"pending_cz_source={traceability['statistics']['pending_cz_source']}")
    print("addendum=15x6=90")
    print("execution_tiers=60/13/17")
    print("external_lane_only=42")


if __name__ == "__main__":
    main()

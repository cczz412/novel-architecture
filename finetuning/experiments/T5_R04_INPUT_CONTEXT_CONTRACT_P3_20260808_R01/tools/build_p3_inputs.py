#!/usr/bin/env python3
"""Build P3 rights groups and frozen zero-training context prompt variants."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path("/Users/a1234/挣钱/小说架构")
EXP = REPO / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01"
P2 = REPO / "finetuning/experiments/T5_R04_PRODUCTION_CANONICAL_PREREQUISITE_REPAIR_P2_20260808_R01/sealed_r01"
WORK = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT"
M1 = WORK / "m1_r01"
DEV_ROOT = WORK / "set_b_r03_work/sealed/T5_R04_SYNTHETIC_MICRO24_SET_B_R03_20260808"
DEV_RENDERED = DEV_ROOT / "rendered/C2_FULL_ID_LIST_SET_B_24.jsonl"
DEV_CANONICAL = DEV_ROOT / "canonical/CANONICAL_MICRO24_SET_B_R03.jsonl"
ADAPTER = M1 / "eval_adapters/c2_full/update_72/adapters.safetensors"
ADAPTER_CONFIG = M1 / "eval_adapters/c2_full/update_72/adapter_config.json"
OLD_RAW = M1 / "results/c2_full/update_72/DEV24_RAW_OUTPUTS.jsonl"
M1_RUNNER = M1 / "tools/m1_runner.py"
TRAINER = WORK / "pipeline_r02/vendor_r02/mlx_lm/tuner/trainer.py"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
CURRENT = REPO / "finetuning/CURRENT.json"
P3_PACKAGE = REPO / "TEMP/chatgpt_review_cycles/T5_R04_CONTEXT_CONTRACT_P3_INTAKE_20260808_R01/raw/T5_R04_CONTEXT_CONTRACT_RESEARCH_AND_P3_20260808_R01.zip"
P3_PACKAGE_RECEIPT = REPO / "TEMP/chatgpt_review_cycles/T5_R04_CONTEXT_CONTRACT_P3_INTAKE_20260808_R01/raw/T5_R04_CONTEXT_CONTRACT_RESEARCH_AND_P3_20260808_R01_RECEIPT.json"
A_AUTH = REPO / "TEMP/chatgpt_review_cycles/T5_R04_A_V27_PRUNED_CANDIDATE_20260807_R01/AUTHORIZATION.md"

EXPECTED_SHA = {
    "p3_package": "2eeb6d1f8fce3509cb665be802c9912adfe1db0bf0ec3605a1ab575b5ab85b87",
    "current": "5abaa79b952532881dfc5e147e7da190471baba386aac263474b51edd414f8dd",
    "adapter": "321d96c10f00389e557efbeb2d8e3dc1344071cc3cd663b51b8a8c2bd38ea5f9",
    "adapter_config": "72df68a7d01b8feae8f92cc0e4f69c832d9ad71886b4f8ea2896a7436d73031e",
    "m1_runner": "f2199b8f911894d8347878a97244ca3b41e8e19fc5297408fd6e8d18a2f81be7",
    "trainer": "78a4d0d04e4b214a0eb5ebafe5be7dea934365287b5b91f80b0e3ff37145b909",
    "old_raw": "b32460077523b054f772fa5a70d39e8f51bec902f81b04f0261040cfff1b13c6",
    "dev_rendered": "b9f819d29434b43fae2974ff2de4dca333614c50cda9821d14fa37a5036d44c4",
    "dev_canonical": "fa04ce5e5f819f4f87aec248ef8c306541b04128d67f0b79cc7e61f2d401d7d9",
    "model_receipt": "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6",
    "a_candidate_authorization": "cdaf692837c9c9df98b8290d5665542311908887f6247059047be39406bf5145",
}

RULEBOOK = """【新增输入块：精简规则】
1. 计划不等于已发生。
2. 承诺不等于已兑现。
3. 推测不等于确定。
4. 误信不等于世界事实。
5. 否认行为与被否认内容分开。
6. 背景／只读区不能单独贡献 evidence。
7. 一条 fact 只写一个核心断言。
8. 没有应抽事实时允许输出空数组。"""

PURPOSE = """【新增输入块：任务目的】
这些事实将进入小说长期状态库，用于连续性检索。
请抽取当前负责区明确支持的事实，不要总结剧情；背景只能辅助理解，不能代替正文证据。"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def stable_row_sha(value: Any) -> str:
    return text_sha(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


def verify_sources() -> dict[str, Any]:
    paths = {
        "p3_package": P3_PACKAGE,
        "current": CURRENT,
        "adapter": ADAPTER,
        "adapter_config": ADAPTER_CONFIG,
        "m1_runner": M1_RUNNER,
        "trainer": TRAINER,
        "old_raw": OLD_RAW,
        "dev_rendered": DEV_RENDERED,
        "dev_canonical": DEV_CANONICAL,
        "model_receipt": MODEL / "MODEL_RECEIPT.json",
        "a_candidate_authorization": A_AUTH,
    }
    result: dict[str, Any] = {}
    for key, path in paths.items():
        if not path.is_file():
            raise RuntimeError(f"缺少输入：{key} {path}")
        actual = sha256(path)
        if actual != EXPECTED_SHA[key]:
            raise RuntimeError(f"SHA 漂移：{key} expected={EXPECTED_SHA[key]} actual={actual}")
        result[key] = {"path": str(path), "sha256": actual, "bytes": path.stat().st_size}
    receipt = json.loads(P3_PACKAGE_RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("status") != "CANDIDATE_PENDING_LOCAL_VERIFICATION" or receipt.get("zip_sha256") != EXPECTED_SHA["p3_package"]:
        raise RuntimeError("P3 外包回执身份不正确")
    result["p3_package_receipt"] = {"path": str(P3_PACKAGE_RECEIPT), "sha256": sha256(P3_PACKAGE_RECEIPT)}
    return result


def rights_outputs(out: Path) -> dict[str, Any]:
    rows = read_jsonl(P2 / "PRODUCTION_ELIGIBILITY_LEDGER_398.jsonl")
    ordinary = [row for row in rows if row.get("rights_status") == "RIGHTS_UNKNOWN"]
    if len(ordinary) != 314 or sum(row["facts_count"] for row in ordinary) != 2783:
        raise RuntimeError("P2 A 权利分母漂移")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ordinary:
        grouped[row["source_id"]].append(row)
    if len(grouped) != 74:
        raise RuntimeError(f"A 来源组不是 74：{len(grouped)}")
    ordered = sorted(grouped.items(), key=lambda item: (item[1][0]["book_title"], item[0]))
    outputs: list[dict[str, Any]] = []
    templates: list[dict[str, Any]] = []
    for index, (source_id, items) in enumerate(ordered, 1):
        items = sorted(items, key=lambda row: (row["chapter_id"], row["source_line_number"], row["row_id"]))
        first = items[0]
        invariants = {
            "book_id": {row["book_id"] for row in items},
            "book_title": {row["book_title"] for row in items},
            "author_id": {row["author_id"] for row in items},
            "author_name": {row["author_name"] for row in items},
            "source_paths": {tuple(row["source_paths"]) for row in items},
            "source_sha256": {row["source_sha256"] for row in items},
        }
        if any(len(values) != 1 for values in invariants.values()):
            raise RuntimeError(f"来源组内部身份不一致：{source_id}")
        status_counts: Counter[str] = Counter()
        for row in items:
            status_counts.update(row.get("statuses", {}))
        evidence_index: dict[tuple[str, str], dict[str, Any]] = {}
        for row in items:
            for evidence in row.get("rights_evidence", []):
                evidence_index[(evidence["path"], evidence["sha256"])] = evidence
        group_id = f"R{index:03d}"
        group = {
            "group_id": group_id,
            "source_identity": {
                "source_id": source_id,
                "book_id": first["book_id"],
                "book_title": first["book_title"],
                "author_id": first["author_id"],
                "author_name": first["author_name"],
                "source_paths": first["source_paths"],
                "source_sha256": first["source_sha256"],
                "chapter_ids": sorted({row["chapter_id"] for row in items}),
                "row_id_families": sorted({row["row_id"].split("-")[0] for row in items}),
                "origin_batch": None,
                "origin_batch_status": "MISSING_NOT_IN_P2_LEDGER_DO_NOT_GUESS",
            },
            "coverage": {
                "row_count": len(items),
                "fact_count": sum(row["facts_count"] for row in items),
                "row_ids": [row["row_id"] for row in items],
                "source_line_numbers": [row["source_line_number"] for row in items],
                "source_text_sha256": [row["source_text_sha256"] for row in items],
                "status_counts": dict(sorted(status_counts.items())),
            },
            "current_rights": {
                "status": "RIGHTS_UNKNOWN",
                "evidence": sorted(evidence_index.values(), key=lambda item: (item["path"], item["sha256"])),
                "evidence_interpretation": "现有材料只允许构造候选，并明确禁止直接训练；不是逐来源训练授权。",
                "contract_or_license": None,
            },
            "missing_evidence": [
                "可绑定到本书／本来源的训练使用授权或合同",
                "权利主体与授权人身份",
                "允许用途明确包含内部模型微调／训练",
                "授权范围、有效期与撤销条件",
                "证据文件路径与 SHA-256",
            ],
            "candidate_decision": "RIGHTS_UNKNOWN",
            "candidate_status": "CANDIDATE_PENDING_CZ_CONFIRMATION",
            "possible_decisions": ["APPROVE_FOR_INTERNAL_TRAINING", "REJECT_FOR_TRAINING", "KEEP_RIGHTS_UNKNOWN"],
            "impact_if_approved": {"rows_candidate_releasable_after_new_p2_revision": len(items), "facts_candidate_releasable_after_new_p2_revision": sum(row["facts_count"] for row in items)},
            "impact_if_rejected": {"rows_remain_excluded": len(items), "facts_remain_excluded": sum(row["facts_count"] for row in items)},
            "prohibitions": ["不从历史训练倒推权利", "不因文件在本地而放行", "不以同书其他来源的授权自动覆盖本来源", "本轮不修改 P2 sealed"],
        }
        outputs.append(group)
        templates.append({
            "group_id": group_id,
            "source_id": source_id,
            "book_id": first["book_id"],
            "book_title": first["book_title"],
            "row_count": len(items),
            "fact_count": group["coverage"]["fact_count"],
            "cz_decision": "CZ_DECISION_REQUIRED",
            "decision_scope": None,
            "authority_document_path": None,
            "authority_document_sha256": None,
            "rights_holder": None,
            "allowed_use": None,
            "validity": None,
            "cz_note": None,
        })
    write_jsonl(out / "track_a/RIGHTS_SOURCE_GROUPS_314.jsonl", outputs)
    write_jsonl(out / "track_a/RIGHTS_DECISION_TEMPLATE.jsonl", templates)
    row_distribution = Counter(group["coverage"]["row_count"] for group in outputs)
    matrix = {
        "status": "PASS_314_ROWS_GROUPED_RIGHTS_STILL_UNKNOWN",
        "input_rows": len(ordinary),
        "input_facts": sum(row["facts_count"] for row in ordinary),
        "source_groups": len(outputs),
        "books": len({group["source_identity"]["book_id"] for group in outputs}),
        "authors": len({group["source_identity"]["author_id"] for group in outputs}),
        "candidate_approved_groups": 0,
        "rights_unknown_groups": len(outputs),
        "rows_per_group_distribution": {str(key): value for key, value in sorted(row_distribution.items())},
        "group_rows_min": min(group["coverage"]["row_count"] for group in outputs),
        "group_rows_max": max(group["coverage"]["row_count"] for group in outputs),
        "group_facts_min": min(group["coverage"]["fact_count"] for group in outputs),
        "group_facts_max": max(group["coverage"]["fact_count"] for group in outputs),
        "origin_batch_field_available": False,
        "origin_batch_handling": "不猜；只保留 row_id_families 作为可见机械字段。",
        "p2_sealed_modified": False,
    }
    write_json(out / "track_a/RIGHTS_COVERAGE_MATRIX_314.json", matrix)
    lines = [
        "# A v2.7｜74 个来源组权利裁决请求",
        "",
        "✅ 314 行已经压缩为 74 个按书／来源裁决的组，不需要逐行重复判断。",
        "",
        "⚠️ 当前 74 组全部仍是权利未知。现有票只允许生成候选，并明确禁止直接训练，所以这里没有任何一组被 Codex 代为放行。",
        "",
        "请在 `RIGHTS_DECISION_TEMPLATE.jsonl` 里为整组填写裁决与权威证据。只有附上能绑定到该书／来源、并明确允许内部模型训练的材料，后续新 P2 revision 才能重新判资格。",
        "",
        "| 组 | 书名 | 作者 | 行 | 事实 | 当前状态 |",
        "|---|---|---|---:|---:|---|",
    ]
    for group in outputs:
        ident = group["source_identity"]
        cov = group["coverage"]
        lines.append(f"| {group['group_id']} | {ident['book_title']} | {ident['author_name']} | {cov['row_count']} | {cov['fact_count']} | 权利未知 |")
    lines.extend(["", "来源：Codex"])
    (out / "track_a/RIGHTS_DECISION_REQUEST_TO_CZ.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    receipt = {
        "status": "PASS_RIGHTS_INTAKE_GROUPED_NO_GROUP_PROMOTED",
        "source_groups": 74,
        "rows": 314,
        "facts": 2783,
        "local_training_grants_found": 0,
        "candidate_group_releases": 0,
        "rights_unknown_groups": 74,
        "candidate_authorization_path": str(A_AUTH),
        "candidate_authorization_sha256": sha256(A_AUTH),
        "candidate_authorization_interpretation": "候选施工授权，不是训练权利授权。",
        "p2_sealed_modified": False,
        "production_canonical_built": False,
    }
    write_json(out / "track_a/RIGHTS_LOCAL_EVIDENCE_RECEIPT.json", receipt)
    md = """# 权利本地证据回执

本轮重新确认：A v2.7 的 314 行能按 74 本书／来源聚合，但本地已有材料里没有逐来源训练授权。现有授权只允许构造候选，还明确禁止直接训练。

所以这次只交裁决工作包，不修改 P2 sealed，不生成 Production Canonical，也不把任何一组改成可训练。

来源：Codex
"""
    (out / "track_a/RIGHTS_LOCAL_EVIDENCE_RECEIPT.md").write_text(md, encoding="utf-8")
    return matrix


def context_outputs(out: Path) -> dict[str, Any]:
    rendered = read_jsonl(DEV_RENDERED)
    canonical = {row["case_id"]: row for row in read_jsonl(DEV_CANONICAL)}
    if len(rendered) != 24 or len(canonical) != 24:
        raise RuntimeError("DEV24 分母漂移")
    alias_cases = []
    for case_id, row in canonical.items():
        if "都叫" in row["source"]["read_only_before"]:
            alias_cases.append(case_id)
    if alias_cases != ["MICRO24B-S03"]:
        raise RuntimeError(f"confirmed alias 审计漂移：{alias_cases}")
    arms = {
        "c0_current_minimal": {"status": "RUNNABLE_AFTER_BASELINE_GATE", "kind": "NO_CHANGE"},
        "c1_rulebook_8": {"status": "RUNNABLE_AFTER_BASELINE_GATE", "kind": "FIXED_SYSTEM_SUFFIX", "fixed_block": RULEBOOK},
        "c2_purpose_short": {"status": "RUNNABLE_AFTER_BASELINE_GATE", "kind": "FIXED_SYSTEM_SUFFIX", "fixed_block": PURPOSE},
        "c3_background_min_confirmed": {"status": "NOT_RUN_INSUFFICIENT_SAFE_CASES", "safe_cases": alias_cases, "required_cases": 16},
        "c4_previous_state_confirmed": {"status": "RUNNABLE_AFTER_BASELINE_GATE", "kind": "CASE_SYSTEM_SUFFIX_FROM_CANONICAL_BEFORE", "safe_cases": sorted(canonical), "as_of_position": "relative_before_target"},
        "c5_structure_metadata": {"status": "NOT_RUN_MISSING_REAL_METADATA", "required_fields": ["chapter_index", "chunk_index", "chunk_count", "responsibility_zone"]},
    }
    manifest_rows = []
    for arm, spec in arms.items():
        question_rows = []
        if spec["status"].startswith("RUNNABLE"):
            for base in rendered:
                case_id = base["case_id"]
                messages = [dict(message) for message in base["messages"]]
                block = ""
                if arm == "c1_rulebook_8":
                    block = RULEBOOK
                elif arm == "c2_purpose_short":
                    block = PURPOSE
                elif arm == "c4_previous_state_confirmed":
                    before = canonical[case_id]["source"]["read_only_before"]
                    block = (
                        "【新增输入块：已确认前态】\n"
                        "as_of_position: relative_before_target\n"
                        f"source_provenance: DEV24_SET_B_R03/{case_id}/canonical.source.read_only_before\n"
                        f"confirmed_previous_state: {before}"
                    )
                if block:
                    messages[0]["content"] = messages[0]["content"] + "\n\n" + block
                base_projection = {"case_id": case_id, "messages": base["messages"]}
                variant_projection = {"case_id": case_id, "messages": messages}
                question_rows.append({
                    "case_id": case_id,
                    "context_arm": arm,
                    "messages": messages,
                    "input_block": block,
                    "input_block_sha256": text_sha(block),
                    "base_rendered_row_sha256": stable_row_sha(base_projection),
                    "variant_row_sha256": stable_row_sha(variant_projection),
                    "canonical_case_sha256": stable_row_sha(canonical[case_id]),
                    "gold_unchanged": messages[-1] == base["messages"][-1],
                    "user_message_unchanged": messages[1] == base["messages"][1],
                    "output_schema_unchanged": True,
                    "renderer_unchanged": True,
                })
            write_jsonl(out / f"track_b/prompts/{arm}_QUESTIONS_24.jsonl", question_rows)
        manifest_rows.append({
            "arm": arm,
            **spec,
            "case_count": len(question_rows),
            "questions_path": f"track_b/prompts/{arm}_QUESTIONS_24.jsonl" if question_rows else None,
            "questions_sha256": sha256(out / f"track_b/prompts/{arm}_QUESTIONS_24.jsonl") if question_rows else None,
            "only_allowed_change": "system_suffix_input_block" if arm != "c0_current_minimal" and question_rows else "none",
        })
    write_jsonl(out / "track_b/CONTEXT_PROMPT_VARIANTS_MANIFEST.jsonl", manifest_rows)
    gap_c3 = """# C3｜确认背景卡不可测缺口

24 题中，只有 `MICRO24B-S03` 的只读上文明示了“安澈＝阿澈”。其余人物身份若从负责区、speaker 或 gold 提取，会泄漏本题答案。

安全分母只有 1／24，低于工单要求的 16／24，所以 C3 不运行。

来源：Codex
"""
    (out / "track_b/BACKGROUND_MIN_CONFIRMED_NOT_TESTABLE_GAP.md").write_text(gap_c3, encoding="utf-8")
    gap_c5 = """# C5｜真实结构元数据不可测缺口

Set B R03 没有真实的 `chapter_index`、`chunk_index`、`chunk_count` 或 `responsibility_zone`。题号和合成单元编号不能冒充小说章节／块位置。

所以 C5 不运行，也不制造随机假元数据。

来源：Codex
"""
    (out / "track_b/STRUCTURE_METADATA_NOT_TESTABLE_GAP.md").write_text(gap_c5, encoding="utf-8")
    plan = """# 输入合同跨模型复验计划

- 本地 Qwen 只筛候选，不替生产模型定版。
- Ling Tiny 工具链成熟后，只复验 C0 与本轮最多两个候选，不迁移 Qwen 的训练参数。
- 如果 Dense 与 Sparse 对同一输入变量结论一致，Doubao Mini 默认只验证一个最终合同。
- 如果两者在具体变量上冲突，Mini 最多做两臂仲裁；三臂必须另获 CZ 批准。
- 本阶段不调用 Ling、Mini 或 Lite。

来源：Codex
"""
    (out / "track_b/CONTEXT_CONTRACT_CROSS_MODEL_REPLICATION_PLAN.md").write_text(plan, encoding="utf-8")
    return {"arms": manifest_rows, "runnable": [row["arm"] for row in manifest_rows if row["case_count"] == 24], "not_run": [row["arm"] for row in manifest_rows if row["case_count"] == 0]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise RuntimeError(f"输出目录已存在，禁止覆盖：{out}")
    out.mkdir(parents=True)
    sources = verify_sources()
    rights = rights_outputs(out)
    context = context_outputs(out)
    lock = {
        "schema_version": "t5-r04-p3-source-lock-v1",
        "status": "P3_INPUTS_FROZEN_NO_TRAINING",
        "authority": {
            "source": "CZ current task: 给你的任务在这个zip里面",
            "package_status": "CANDIDATE_PENDING_LOCAL_VERIFICATION",
            "authorized_actions": ["rights_grouping", "zero_training_context_probe_after_baseline_reproduction"],
            "prohibited_actions": ["training", "modify_p2_sealed", "modify_dev24_gold", "modify_c2_renderer", "switch_finetuning_current", "api", "notion", "git_commit_or_push"],
        },
        "source_bindings": sources,
        "model_revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
        "decode": {"sampler": "greedy", "temperature": 0.0, "max_output_tokens": 1024, "retry": 0},
        "rights": rights,
        "context": context,
        "training_started": False,
        "api_called": False,
        "current_pointer_modified": False,
    }
    write_json(out / "P3_SOURCE_AND_EXECUTION_LOCK.json", lock)
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_file():
            files.append({"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": sha256(path)})
    write_json(out / "P3_BUILD_MANIFEST.json", {"status": "PASS_P3_INPUT_BUILD", "file_count_excluding_manifest": len(files), "files": files})
    print(json.dumps({"status": "PASS_P3_INPUT_BUILD", "out": str(out), "rights_groups": 74, "runnable_arms": context["runnable"], "not_run_arms": context["not_run"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

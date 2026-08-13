#!/usr/bin/env python3
"""Create the deterministic P3 closeout ticket, gap list and deliverable manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path("/Users/a1234/挣钱/小说架构")
EXP = REPO / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01"
SEALED = EXP / "sealed_inputs_r01"
SCORING = EXP / "results_r01/scoring_r02"
P2 = REPO / "finetuning/experiments/T5_R04_PRODUCTION_CANONICAL_PREREQUISITE_REPAIR_P2_20260808_R01/sealed_r01"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    rights = json.loads((SEALED / "track_a/RIGHTS_COVERAGE_MATRIX_314.json").read_text(encoding="utf-8"))
    metrics = json.loads((SCORING / "CONTEXT_CONTRACT_METRICS.json").read_text(encoding="utf-8"))
    if rights.get("source_groups") != 74 or rights.get("rights_unknown_groups") != 74 or rights.get("candidate_approved_groups") != 0:
        raise RuntimeError("权利聚合读数不符合 74 组全未知")
    if metrics.get("status") != "PASS_P3_CONTEXT_CONTRACT_ZERO_TRAINING_SCORING_COMPLETE":
        raise RuntimeError("P3 输入合同评分尚未完成")
    p2_bindings = {}
    for name in ("PRODUCTION_ELIGIBILITY_LEDGER_398.jsonl", "RIGHTS_REPAIR_RECEIPT_314.json", "P2_GAP_LIST.jsonl"):
        path = P2 / name
        p2_bindings[name] = {"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size, "sha256": sha256(path)}
    write_json(EXP / "P3_P2_SOURCE_BINDING_RECEIPT.json", {
        "status": "PASS_POST_BUILD_P2_SOURCE_RECONCILIATION",
        "meaning": "补登记 Track A 实际读取的 P2 sealed 身份；不是伪装成事前执行锁。74 组输出仍须由验证器逐行反向对账。",
        "bindings": p2_bindings,
        "p2_sealed_modified": False,
    })
    gaps = [
        {"gap_id": "P3-GAP-001", "area": "rights", "status": "BLOCKING_PRODUCTION_CANONICAL", "finding": "314 行、2,783 条事实压缩为 74 个来源组，但 74/74 都没有能绑定到对应书／来源且明确允许内部模型训练的本地证据。", "next_action": "由 CZ 按来源组补权威证据或裁决；不得由 Codex 猜测放行。"},
        {"gap_id": "P3-GAP-002", "area": "origin_batch", "status": "MISSING_FIELD_NOT_GUESSED", "finding": "P2 ledger 没有 origin_batch 字段。", "next_action": "本轮只保留可见 row_id_families，不从路径或编号反推批次。"},
        {"gap_id": "P3-GAP-003", "area": "C3_confirmed_identity", "status": "NOT_RUN", "finding": "24 题中只有 1 题有不泄 gold 的明确别名，低于预注册 16/24。", "next_action": "真实数据具备作者确认身份卡后另建同源实验。"},
        {"gap_id": "P3-GAP-004", "area": "C4_previous_state", "status": "RELATIVE_PROVENANCE_ONLY", "finding": "24/24 只有 canonical read_only_before 的相对来源，没有真实章节／块绝对位置。", "next_action": "不得把 relative_before_target 冒充真实 chapter/chunk provenance。"},
        {"gap_id": "P3-GAP-005", "area": "C4_previous_state", "status": "INPUT_CONTRACT_FAILURE_SIGNAL", "finding": "MICRO24B-S16 与 MICRO24B-S23 把只读前态写入答案并引用 B01；正式负责区只允许 Txx。", "next_action": "冻结当前 C4 写法，不晋升为默认输入合同。"},
        {"gap_id": "P3-GAP-006", "area": "C5_structure_metadata", "status": "NOT_RUN", "finding": "Set B R03 没有 chapter_index、chunk_index、chunk_count、responsibility_zone。", "next_action": "等真实元数据存在后再测；不得制造随机标签冒充。"},
        {"gap_id": "P3-GAP-007", "area": "external_validity", "status": "LOCAL_PROXY_SYNTHETIC_ONLY", "finding": "本轮只有本地 Qwen 离线代理和合成 DEV24，不能替 Doubao Mini/Lite 或真实小说定版。", "next_action": "权利和真实 canonical 就绪后，再按跨模型复验计划筛最少候选。"},
        {"gap_id": "P3-GAP-008", "area": "semantic_review", "status": "SINGLE_LOCAL_REVIEW", "finding": "69 种预测复用冻结 same-case 裁决，10 种新预测由本轮同题独立复核；没有新增第二位盲审。", "next_action": "若结果要进入生产模型选择或长期合同，补第二位独立复核。"},
    ]
    write_jsonl(EXP / "P3_GAP_LIST.jsonl", gaps)
    m = metrics["metrics"]
    result = f"""# P3 双轨施工结果票\n\n✅ P3 已按授权做到停点：Track A 完成 314 行权利聚合；Track B 完成 C0 基线复现和 C1／C2／C4 三个零训练对照。没有训练、API、Notion、Git、现役指针或 P2 封版改动。\n\n## Track A｜权利补件\n\n- 314 行／2,783 条事实，机械聚合为 74 个来源组；\n- 74 本书、74 位作者、74 个唯一来源；\n- 本地可直接放行：0 组；\n- 权利仍未知：74 组。\n\n这张表把 314 次重复确认缩成 74 次按书／来源裁决，但没有替 CZ 猜任何权利。\n\n## Track B｜输入合同零训练筛查\n\n| 输入臂 | 语义 P / R / F1 | Schema | 预测事实 | 相对 C0 判断 |\n|---|---:|---:|---:|---|\n| C0 当前极简 | {m['c0_current_minimal']['semantic_recoverable']['precision']:.3f} / {m['c0_current_minimal']['semantic_recoverable']['recall']:.3f} / {m['c0_current_minimal']['semantic_recoverable']['f1']:.3f} | {m['c0_current_minimal']['complete_schema']['cases']}/24 | {m['c0_current_minimal']['prediction_count']} | 冻结基线 |\n| C1 八条规则 | {m['c1_rulebook_8']['semantic_recoverable']['precision']:.3f} / {m['c1_rulebook_8']['semantic_recoverable']['recall']:.3f} / {m['c1_rulebook_8']['semantic_recoverable']['f1']:.3f} | {m['c1_rulebook_8']['complete_schema']['cases']}/24 | {m['c1_rulebook_8']['prediction_count']} | 召回大跌，淘汰当前写法 |\n| C2 任务目的 | {m['c2_purpose_short']['semantic_recoverable']['precision']:.3f} / {m['c2_purpose_short']['semantic_recoverable']['recall']:.3f} / {m['c2_purpose_short']['semantic_recoverable']['f1']:.3f} | {m['c2_purpose_short']['complete_schema']['cases']}/24 | {m['c2_purpose_short']['prediction_count']} | 与 C0 基本打平，未证明有收益 |\n| C4 确认前态 | {m['c4_previous_state_confirmed']['semantic_recoverable']['precision']:.3f} / {m['c4_previous_state_confirmed']['semantic_recoverable']['recall']:.3f} / {m['c4_previous_state_confirmed']['semantic_recoverable']['f1']:.3f} | {m['c4_previous_state_confirmed']['complete_schema']['cases']}/24 | {m['c4_previous_state_confirmed']['prediction_count']} | F1 下降且出现 2 案前态泄漏 |\n\n四个臂都是 24/24 正常停止、0 复读、0 触顶。C1 的 Schema 多 2 题，但它同时少抽 20 条预测、相对 C0 丢了 20 个 gold 命中；不能把“格式更整齐”误判成更会抽事实。\n\nC2 只比 C0 少 0.23 个 F1 百分点，属于打平区：可以保留为跨模型候选，但当前没有理由改默认 Prompt。C4 重复标注了原题已经存在的只读前文；它测到的是强调／标签效应，不是增加信息量。\n\nC3 因安全别名只有 1/24 不运行；C5 因真实章节／块元数据为 0 不运行。\n\n## 当前停点\n\n- ❌ 不生成 Production Canonical；\n- ❌ 不启动训练或云端模型；\n- ❌ 不改 C2 renderer、DEV24 gold、P2 sealed 或当前微调指针；\n- 👉 下一张有效动作应由 CZ 在 74 个权利来源组里补证或裁决。\n\n来源：Codex\n"""
    (EXP / "P3_RESULT_TICKET.md").write_text(result, encoding="utf-8")
    excluded_prefixes = ("build/", "results_r01/scoring_r01/", "tools/__pycache__/")
    excluded_names = {"P3_OUTPUT_MANIFEST.json", "P3_FINAL_VALIDATION_RECEIPT.json"}
    members = []
    for path in sorted(EXP.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(EXP).as_posix()
        if rel in excluded_names or rel.startswith(excluded_prefixes):
            continue
        members.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256(path)})
    write_json(EXP / "P3_OUTPUT_MANIFEST.json", {
        "status": "P3_HARD_STOP_COMPLETE_CANDIDATE_LOCAL_RESULT",
        "members": members,
        "member_count": len(members),
        "excluded": ["build/run_1 and run_2 are bound by P3_INPUT_TWO_RUN_AND_SEAL_RECEIPT.json", "results_r01/scoring_r01 is invalidated by SCORING_R01_INVALIDATION_TICKET.md", "Python bytecode caches", "this manifest and its validation receipt"],
        "training": False, "api_called": False, "notion_written": False, "git_commit_or_push": False,
    })
    print(json.dumps({"status": "PASS_P3_CLOSEOUT_FILES_WRITTEN", "gaps": len(gaps), "manifest_members": len(members)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

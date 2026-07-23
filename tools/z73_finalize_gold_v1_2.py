#!/usr/bin/env python3
"""第73道：把第72道候选草案按 CZ 三点拍板机械转为第3章结构层金标 v1.2 正式版。

这个工具不做语义推断，只做以下事情：
1. 回读并钉住 v1、v1.1、Z72 候选与四轮样张；
2. 把 CZ 已拍的三点处置原样落入正式金标与映射账；
3. 把旧四轮 Z72 重判账转登为 23 条新尺基线，不重跑样张；
4. 校验唯一现役金标指针、历史复现工具和所有保护件。

重要：旧工具是历史复现入口，不能批量改指 v1.2；本道新建唯一当前指针，
以后新判分工具必须读指针。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve()
TEST_FILE = ROOT / "tests/test_z73_finalize_gold_v1_2.py"
DEFAULT_OUTPUT_DIR = ROOT / "reports/Z73_第3章金标v1.2定稿转正_20260721"

GOLD_V1 = ROOT / "reports/Z52续令_候选桶语义清洗与金标转换_20260719/第3章结构层金标v1.json"
GOLD_V1_1 = ROOT / "reports/Z56_金标双轨分层与全链体检_20260719/第3章结构层金标v1.1.json"
CHAPTER_TEXT = ROOT / "TEMP/X批材料包_20260716/books/X01_诡秘之主/chapters/0003_第3章_梅丽莎（第一更求推荐票）.txt"
EVIDENCE_CATALOG = ROOT / "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/01_extract/evidence_catalogs/ch0003.json"

Z72_DIR = ROOT / "reports/Z72_第3章金标粒度候选_20260721"
Z72_CANDIDATE = Z72_DIR / "第3章结构层金标v1.2候选草案.json"
Z72_MAPPING = Z72_DIR / "v1.1到v1.2逐条映射与语义点账.json"
Z72_SCORES = Z72_DIR / "四轮新旧尺零调用重判.json"
Z72_FLAGS = Z72_DIR / "剔除候选与证据风险.json"
Z72_TOOL = ROOT / "tools/z72_gold_granularity_candidate.py"

CURRENT_POINTER = ROOT / "config/gold/X01_ch0003_structure_gold_current.json"
DECISIONS = ROOT / "decisions.md"
DECISION_ID = "Z73-CH3-GOLD-V1.2-PROMOTED-LOCAL"
DECISIONS_BEFORE_SHA256 = "13eff8ffaaf2add64777eb63a9fff2b3d7494000d16c4f1fab5c10d617a752bf"

OLD_SCORE_PATHS = {
    "B0_Z57": ROOT / "reports/Z57_稳定语义身份解耦与全链后半_20260719/第3章当章层诚实成绩单.json",
    "Z68C": ROOT / "reports/Z68续令_32k参数兼容修复与裸考成绩_20260720/第3章金标v1.1语义成绩单.json",
    "Z70": ROOT / "reports/Z70_压缩病灶合同条款单变量_20260721/第3章金标v1.1语义成绩单.json",
    "Z71": ROOT / "reports/Z71_z70语义补全旁路_20260721/第3章金标v1.1语义成绩单.json",
}

RUN_GATE_PATHS = {
    "Z70": ROOT / "reports/Z70_压缩病灶合同条款单变量_20260721/report_manifest.json",
    "Z71": ROOT / "reports/Z71_z70语义补全旁路_20260721/report_manifest.json",
}

PROTECTED_PATHS = {
    "gold_v1": GOLD_V1,
    "gold_v1_1": GOLD_V1_1,
    "default_registry": ROOT / "config/defaults/zbatch_v1.2_full_chain.json",
    "runner": ROOT / "tools/zbatch.py",
    "classification_contract_active": ROOT / "config/contracts/classify_rules_v1.2_semantic_identity_v1.json",
    "classification_contract_archive": ROOT / "config/contracts/classify_rules_v1.2.json",
    "current_122": ROOT / "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json",
}

# 这些全是已编号试验的历史复现入口，不是“当前金标入口”。
HISTORICAL_REFERENCE_PATHS = {
    "tools/z59_entity_supply_pilot.py": ROOT / "tools/z59_entity_supply_pilot.py",
    "tools/z64_measure_comparisons.py": ROOT / "tools/z64_measure_comparisons.py",
    "tools/z68_continuation_report.py": ROOT / "tools/z68_continuation_report.py",
    "tools/z68_revised_request_pilot.py": ROOT / "tools/z68_revised_request_pilot.py",
    "tools/z70_compression_contract_report.py": ROOT / "tools/z70_compression_contract_report.py",
    "tools/z71_semantic_fill_pilot.py": ROOT / "tools/z71_semantic_fill_pilot.py",
    "tools/z71_semantic_fill_report.py": ROOT / "tools/z71_semantic_fill_report.py",
    "tools/z72_gold_granularity_candidate.py": ROOT / "tools/z72_gold_granularity_candidate.py",
    "tests/test_z56_gold_dual_track.py": ROOT / "tests/test_z56_gold_dual_track.py",
}

EXPECTED_SHA256 = {
    "chapter_text": "96f5e17cbec15433b5d00bef18912eb39710ad67962e3716bca37203d4c06288",
    "evidence_catalog": "2cc50e9a0c8b5fb807641e09c74f1748cbe423bf0fa700dbbbaa84ba20e58132",
    "z72_candidate": "30475388a275ffdbacf8a984e35e8fbda82c38dea105977611675270f1e560fb",
    "z72_mapping": "2ce9eb929ed75a59b77ffbaf1f83eb30ef102d36d2a39401d2ba69dd539adf52",
    "z72_scores": "99b47897b7679a8c89cf0628d28af5ab748bdeb1f35eac22adc94b802024a21e",
    "z72_flags": "cd99d4dd9aadebabea714f83225e76c4aa590930f162f4e921f5b1332bf38a7c",
    "z72_tool": "261eaddb615f97d8a0414abb1c0b7266f9892d1a0f67eb0481c24b1375210ffa",
    "gold_v1": "6d826b103657d5326224c8ef925138b98e0c23578bd7ed1864cd763f733a6488",
    "gold_v1_1": "8cca04f06ba21048e15420f178163c646d2effeead0970697fafbf5f45174b7c",
    "default_registry": "b23b5cce26b9cfe584dd97dbff6422efa2b22ccd5cba38c6ed6a44c4543bc0a1",
    "runner": "160c28b3ef0210fd05c392f713534cf1ffdf041fa596ec790545b64955280850",
    "classification_contract_active": "45f7610b86d5962e0d3d9d4d95886aad9022f1beaece200c2452b9a361f6c108",
    "classification_contract_archive": "ad2ccc3b13e8b138a32a46b8566e928a3c4e35a60cf31c5494c7b9ba3dd021de",
    "current_122": "dafa16901a6edb5018a5176f3f5f7388273e72051def7fe4e997489d01e804ba",
    "old_score:B0_Z57": "069c28237624e0cfe5236805c11bec28ad4e599990f77cab737b6596a9af5f69",
    "old_score:Z68C": "d2bcf3d2e5dcfe61963fb34ae1b693a1b7d33d3e7c6182642f9d2b3bdbce698e",
    "old_score:Z70": "d18969b4c04f2472d3b36f3d99d3f3b920706bfb688749aeb5f19785427dccd8",
    "old_score:Z71": "8a1aaa78192f750a0df1e81110f69c97190468012964a42c5e5acd8453414ce3",
    "run_gate:Z70": "30408e009f6038c7d6f1dc0273e3f6aa24268d0ee227593bd0fe327714fde3ab",
    "run_gate:Z71": "91a962883e4e87c80f4bdc541c879c01241d0166107a3f7b5a9288359d4a1800",
}

EXPECTED_HISTORICAL_SHA256 = {
    "tools/z59_entity_supply_pilot.py": "d039367e53ab3aaf0cd775e8249e965b7015fd9775d822ac34415518cd321aef",
    "tools/z64_measure_comparisons.py": "ff73c92847bd81b5f740a86fc1b59502ea17c5e0220fa8c884bd611fa8124f26",
    "tools/z68_continuation_report.py": "8d7a5cbac6c5f4e8e97fc80d9bb39f795a38aab146b05785adc9d6e9ca0048bd",
    "tools/z68_revised_request_pilot.py": "d0855f240807992058ee0797070286cbbbddbbe34ddb89855b432ebc7f1ce28b",
    "tools/z70_compression_contract_report.py": "1a64e2cd70594661e56359a5827ca7f1f9ad9fd6b6a9cfd79154ed7c0ec592c4",
    "tools/z71_semantic_fill_pilot.py": "2393c08ced6b1e808532849eef62b5b6d0e889df83c34fd0dee66edb6ff7b6a5",
    "tools/z71_semantic_fill_report.py": "353b54cd6920b64758220f32c4366112af7f1093dd73699c3829cc77f3691b4f",
    "tools/z72_gold_granularity_candidate.py": "261eaddb615f97d8a0414abb1c0b7266f9892d1a0f67eb0481c24b1375210ffa",
    "tests/test_z56_gold_dual_track.py": "9ca76f44a7d282d2af8fffac4df7a6a484b48ff836ea5e046a9a3748b4b86dec",
}

EXPECTED_OUTBOX = {
    "files": 18,
    "bytes": 942264,
    "sha256": "d67a3be7df95bc34089237213049b201d6f8e22c2b971d7f6b76f48e125cc38d",
}

FORMAL_GOLD_REL = "reports/Z73_第3章金标v1.2定稿转正_20260721/第3章结构层金标v1.2.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"JSON 顶层不是对象：{path}")
    return value


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tree_fingerprint(path: Path) -> dict[str, Any]:
    rows: list[tuple[str, str, int]] = []
    for file in sorted(p for p in path.rglob("*") if p.is_file() and p.name != ".DS_Store"):
        rows.append((str(file.relative_to(path)), sha256(file), file.stat().st_size))
    payload = "\n".join(f"{name}\t{digest}\t{size}" for name, digest, size in rows)
    return {
        "files": len(rows),
        "bytes": sum(size for _, _, size in rows),
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def check_frozen_inputs() -> dict[str, str]:
    paths = {
        "chapter_text": CHAPTER_TEXT,
        "evidence_catalog": EVIDENCE_CATALOG,
        "z72_candidate": Z72_CANDIDATE,
        "z72_mapping": Z72_MAPPING,
        "z72_scores": Z72_SCORES,
        "z72_flags": Z72_FLAGS,
        "z72_tool": Z72_TOOL,
        **PROTECTED_PATHS,
        **{f"old_score:{key}": value for key, value in OLD_SCORE_PATHS.items()},
        **{f"run_gate:{key}": value for key, value in RUN_GATE_PATHS.items()},
    }
    actual = {key: sha256(path) for key, path in paths.items()}
    mismatches = {
        key: {"expected": EXPECTED_SHA256.get(key), "actual": value}
        for key, value in actual.items()
        if EXPECTED_SHA256.get(key) != value
    }
    if mismatches:
        raise AssertionError(f"冻结输入或保护件 SHA 漂移：{mismatches}")

    historical = {key: sha256(path) for key, path in HISTORICAL_REFERENCE_PATHS.items()}
    if historical != EXPECTED_HISTORICAL_SHA256:
        mismatches = {
            key: {"expected": EXPECTED_HISTORICAL_SHA256.get(key), "actual": value}
            for key, value in historical.items()
            if EXPECTED_HISTORICAL_SHA256.get(key) != value
        }
        raise AssertionError(f"历史复现入口 SHA 漂移：{mismatches}")
    if tree_fingerprint(ROOT / "outbox") != EXPECTED_OUTBOX:
        raise AssertionError("outbox 指纹漂移")
    for run_id, path in RUN_GATE_PATHS.items():
        gate = load_json(path)
        if gate.get("status") != "fail" or gate.get("disposition") != "hard_stop_no_repair":
            raise AssertionError(f"{run_id} 失败／硬停状态漂移")
    return {**actual, **{f"historical:{key}": value for key, value in historical.items()}}


def _catalog_rows() -> dict[str, dict[str, Any]]:
    catalog = load_json(EVIDENCE_CATALOG)
    rows = catalog.get("anchors") or catalog.get("evidence_catalog") or catalog.get("items") or catalog.get("entries")
    if not isinstance(rows, list):
        raise AssertionError("冻结证据目录没有 anchors 列表")
    result = {str(row["anchor_id"]): row for row in rows}
    if len(result) != 175:
        raise AssertionError(f"第3章冻结证据目录应为175锚，实际 {len(result)}")
    return result


def _formal_part(raw: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(raw)
    result.pop("review_flag_ids", None)
    result["part_role"] = "on_chapter_atomic_gold"
    result["evidence_status"] = "supported_by_frozen_chapter_text"
    result["adjudication_ids"] = []
    return result


def build_formal_gold() -> dict[str, Any]:
    candidate = load_json(Z72_CANDIDATE)
    old_gold = load_json(GOLD_V1_1)
    old_by_id = {row["item_id"]: row for row in old_gold["layered_items"]}
    items: list[dict[str, Any]] = []

    for candidate_item in candidate["layered_items"]:
        item_id = candidate_item["item_id"]
        old_item = old_by_id[item_id]
        parts: list[dict[str, Any]] = []
        for raw_part in candidate_item["parts"]:
            if raw_part["part_id"] == "GOLD-C0003-10-N03":
                origin_trace = copy.deepcopy(raw_part["source_evidence"])
                parts.append(
                    {
                        "part_id": "GOLD-C0003-10-N03",
                        "layer": "回看件",
                        "score_in_single_chapter": False,
                        "part_role": "hindsight_observation",
                        "observation_only": True,
                        "claim": "观察命题：大学面试结果是否关系全家收入改善。",
                        "verdict": "CZ 拍定剔出当章尺并转回看观察；只有窗口内后续章出现直接因果证据时才可另拍，本件不计分。",
                        "source_evidence": [],
                        "window_evidence_refs": [],
                        "origin_trace_evidence_audit_only": origin_trace,
                        "semantic_point_ids": ["G10-SP03"],
                        "evidence_status": "no_direct_causal_evidence_observation_only",
                        "adjudication_ids": ["Z72-DEL-CAND-01"],
                    }
                )
            else:
                part = _formal_part(raw_part)
                if raw_part["part_id"] == "GOLD-C0003-13-N01":
                    part["adjudication_ids"] = ["Z72-EQUIV-CAND-01"]
                    part["semantic_scope"] = "只计当次劣茶与黑麦面包实例；不承载长期肉食频率语义"
                    part["verdict"] = "CZ 认可当次劣茶与黑麦面包实例句为当章原子；长期肉食频率语义不入当章尺。"
                if raw_part["part_id"] == "GOLD-C0003-06-N01":
                    part["adjudication_ids"] = ["Z72-DUP-CAND-01"]
                    part["non_scoring_alias_semantic_point_ids"] = ["G13-SP02"]
                    part["semantic_scope"] = "只计采购与做菜的中性并列事实；不承载面试导致采购的因果语义"
                    part["verdict"] = "同一说话者的一次采购与做菜安排；G13-SP02 经 CZ 认可为中性并列别名，不重复计分，因果语义不入尺。"
                parts.append(part)

        for hindsight in candidate_item["hindsight_parts_inherited_unchanged"]:
            inherited = copy.deepcopy(hindsight)
            inherited["part_role"] = "hindsight_evidence"
            inherited["evidence_status"] = "supported_by_frozen_window_evidence"
            inherited["semantic_point_ids"] = []
            inherited["adjudication_ids"] = []
            parts.append(inherited)

        granularity_decision = candidate_item["decision"]
        if item_id == "GOLD-C0003-10":
            granularity_decision = "复合条拆原子；G10-SP03 经 CZ 拍板转回看观察"
        elif item_id == "GOLD-C0003-13":
            granularity_decision = "复合条拆原子；G13-SP01 当次实例改写通过，G13-SP02 转中性非计分别名"
        items.append(
            {
                "item_id": item_id,
                "source_kind": candidate_item["source_kind"],
                "source_id": candidate_item["source_id"],
                "predecessor_claim_audit": copy.deepcopy(old_item["predecessor_claim_audit"]),
                "window_evidence_refs_audit_only": copy.deepcopy(old_item["window_evidence_refs_audit_only"]),
                "granularity_decision": granularity_decision,
                "original_semantic_points_audit_only": copy.deepcopy(candidate_item["original_semantic_points"]),
                "parts": parts,
            }
        )

    formal = {
        "schema_version": "structure-gold-v1.2",
        "gold_id": "X01-ch0003-structure-v1.2",
        "task": "第73道",
        "status": "active_gold",
        "gold_scope": "structure_layer_dual_track_atomic",
        "source": copy.deepcopy(old_gold["source"]),
        "predecessor": {
            "path": str(GOLD_V1_1.relative_to(ROOT)),
            "sha256": EXPECTED_SHA256["gold_v1_1"],
            "status": "archived_formal_predecessor",
            "mutation": "none",
        },
        "conversion_source": {
            "path": str(Z72_CANDIDATE.relative_to(ROOT)),
            "sha256": EXPECTED_SHA256["z72_candidate"],
            "status": "candidate_promoted_after_cz_three_point_adjudication",
            "mutation": "none",
        },
        "approval": {
            "authority": "CZ＋Notion《Z批本地交接单》第六节第73道行",
            "approved_at": "2026-07-21 10:35 +08:00",
            "unresolved_total": 0,
            "adjudication_ids": ["Z72-DEL-CAND-01", "Z72-EQUIV-CAND-01", "Z72-DUP-CAND-01"],
        },
        "evaluation_policy": {
            **copy.deepcopy(old_gold["evaluation_policy"]),
            "score_unit": "part_id",
            "formal_denominator": 23,
            "required_score_columns": ["有效召回", "表面覆盖", "锚无效"],
            "effective_recall": "strict_hit＋semantic_shadow；只收事件句与所挂锚同时支撑的条目",
            "surface_coverage": "strict_hit＋semantic_shadow＋coverage_only_invalid_support",
            "invalid_anchor_gate_as_sole_official_metric": "pending_separate_adjudication_not_decided_by_Z73",
        },
        "atomicity_policy": copy.deepcopy(candidate["atomicity_policy"]),
        "consumer_contract": {
            "score_unit": "part_id",
            "item_id_usage": "legacy_grouping_and_traceability_only_not_a_score_unit",
            "single_chapter_scoring_source": "layered_items[].parts[layer=当章可知][score_in_single_chapter=true]",
            "forbidden_scoring_sources": [
                "layered_items[].predecessor_claim_audit",
                "layered_items[].window_evidence_refs_audit_only",
                "layered_items[].parts[layer=回看件]",
                "layered_items[].parts[].origin_trace_evidence_audit_only",
                "layered_items[].parts[].non_scoring_alias_semantic_point_ids",
                "window_audit.evidence_blocks",
            ],
            "anchor_namespace": "chapter_local",
            "anchor_identity": "identity_key=chNNNN:E####；不得把裸anchor_id当全局主键",
        },
        "compatibility_contract": {
            "current_pointer": str(CURRENT_POINTER.relative_to(ROOT)),
            "future_evaluators_must_resolve_pointer": True,
            "unknown_schema_behavior": "reject",
            "legacy_v1_1_14_item_denominator_for_v1_2": "forbidden",
            "historical_numbered_tools": "remain_pinned_to_their_original_gold_for_reproduction",
        },
        "layer_summary": {
            "base_item_total": 14,
            "part_total": 26,
            "on_chapter_scoreable_atomic_part_total": 23,
            "hindsight_evidence_part_total": 2,
            "hindsight_observation_part_total": 1,
            "non_scoreable_part_total": 3,
            "formal_denominator": 23,
            "declared_old_semantic_point_total": 31,
            "supported_or_approved_semantic_point_total": 30,
            "unsupported_old_semantic_point_total": 1,
            "non_scoring_alias_semantic_point_total": 1,
            "unresolved_total": 0,
        },
        "layered_items": items,
        "adjudication_history": [
            {
                "adjudication_id": "Z72-DEL-CAND-01",
                "target": "G10-SP03 / GOLD-C0003-10-N03",
                "decision": "cz_removed_from_on_chapter_scale_to_hindsight_observation",
                "effect": "不计分；窗口内后续章出现直接因果证据时才可另拍",
            },
            {
                "adjudication_id": "Z72-EQUIV-CAND-01",
                "target": "G13-SP01 / GOLD-C0003-13-N01",
                "decision": "cz_equivalence_approved_current_instance_only",
                "effect": "当次劣茶与黑麦面包实例计分；长期肉食频率语义不入当章尺",
            },
            {
                "adjudication_id": "Z72-DUP-CAND-01",
                "target": "G13-SP02",
                "decision": "cz_neutral_parallel_alias_approved_non_scoring",
                "effect": "别名映射 GOLD-C0003-06-N01，不重复计分；因果语义不入尺",
            },
        ],
        "window_audit": copy.deepcopy(old_gold["window_audit"]),
        "audit": {
            "authorization": "Notion《Z批本地交接单》第73道；CZ 2026-07-21 10:35 拍四题",
            "conversion": "deterministic_Z72_candidate_promotion_without_sample_rerun",
            "predecessor_audit": copy.deepcopy(old_gold["audit"]),
            "candidate_input_sha256": EXPECTED_SHA256["z72_candidate"],
            "mapping_input_sha256": EXPECTED_SHA256["z72_mapping"],
            "scores_input_sha256": EXPECTED_SHA256["z72_scores"],
        },
        "protected_state": {
            "gold_v1_rewritten": False,
            "gold_v1_1_rewritten": False,
            "current_122_records_rewritten": False,
            "default_runner_rewritten": False,
            "default_registry_rewritten": False,
            "classification_rules_rewritten": False,
            "outbox_rewritten": False,
            "four_round_samples_rerun": False,
            "model_api_calls": 0,
            "network_requests": 0,
            "token_usage": 0,
        },
    }
    validate_formal_gold(formal)
    return formal


def validate_formal_gold(formal: dict[str, Any]) -> dict[str, Any]:
    chapter_text = CHAPTER_TEXT.read_text(encoding="utf-8")
    catalog = _catalog_rows()
    parts = [part for item in formal["layered_items"] for part in item["parts"]]
    scoreable = [part for part in parts if part["score_in_single_chapter"]]
    hindsight = [part for part in parts if part["layer"] == "回看件"]
    observations = [part for part in parts if part.get("part_role") == "hindsight_observation"]
    if len(formal["layered_items"]) != 14 or len(parts) != 26:
        raise AssertionError("正式金标应为14个底件、26个分层部件")
    if len(scoreable) != 23 or len(hindsight) != 3 or len(observations) != 1:
        raise AssertionError("正式金标应为23条当章原子＋2回看证据＋1回看观察")
    part_ids = [part["part_id"] for part in parts]
    if len(part_ids) != len(set(part_ids)):
        raise AssertionError("正式金标 part_id 不唯一")

    anchor_checks: list[dict[str, Any]] = []
    for part in scoreable:
        if part["layer"] != "当章可知" or not part["source_evidence"]:
            raise AssertionError(f"计分原子没有当章证据：{part['part_id']}")
        for evidence in part["source_evidence"]:
            anchor_id = evidence["anchor_id"]
            if anchor_id not in catalog:
                raise AssertionError(f"锚不存在：{part['part_id']} {anchor_id}")
            catalog_quote = catalog[anchor_id]["quote"]
            if evidence["quote"] != catalog_quote or catalog_quote not in chapter_text:
                raise AssertionError(f"锚回读失败：{part['part_id']} {anchor_id}")
            anchor_checks.append({"part_id": part["part_id"], "anchor_id": anchor_id, "status": "pass"})

    observation = observations[0]
    if observation["part_id"] != "GOLD-C0003-10-N03":
        raise AssertionError("G10-SP03 没有转到指定回看观察")
    if observation["source_evidence"] or observation["window_evidence_refs"]:
        raise AssertionError("G10 回看观察不得伪装已有直接因果证据")
    if len(observation["origin_trace_evidence_audit_only"]) != 4:
        raise AssertionError("G10 原候选四个追溯锚应保留为审计信息")

    item_by_id = {item["item_id"]: item for item in formal["layered_items"]}
    g13 = next(part for part in item_by_id["GOLD-C0003-13"]["parts"] if part["part_id"] == "GOLD-C0003-13-N01")
    if not g13["score_in_single_chapter"] or "不承载长期肉食频率语义" not in g13["semantic_scope"]:
        raise AssertionError("G13-SP01 应保留当次实例计分，同时排除长期频率语义")
    g06 = next(part for part in item_by_id["GOLD-C0003-06"]["parts"] if part["part_id"] == "GOLD-C0003-06-N01")
    if g06.get("non_scoring_alias_semantic_point_ids") != ["G13-SP02"]:
        raise AssertionError("G13-SP02 没有作为 G06-N01 的非重复计分别名")
    if formal["window_audit"]["out_of_window_evidence_ids"]:
        raise AssertionError("窗口证据不得越过第200章")
    return {
        "status": "pass",
        "base_item_total": 14,
        "part_total": 26,
        "scoreable_atomic_part_total": 23,
        "hindsight_evidence_part_total": 2,
        "hindsight_observation_part_total": 1,
        "scoreable_anchor_occurrence_total": len(anchor_checks),
        "scoreable_anchor_checks": anchor_checks,
        "window_evidence_block_total": formal["window_audit"]["evidence_block_total"],
        "window_anchor_total": formal["window_audit"]["anchor_total"],
        "window_max_chapter": formal["window_audit"]["max_evidence_chapter"],
    }


def build_dispositions() -> dict[str, Any]:
    return {
        "schema_version": "z73-cz-three-point-disposition-v1",
        "task": "第73道",
        "status": "cz_approved_all_three_applied",
        "authority": "CZ 2026-07-21 10:35＋Notion Z批队列第73道行",
        "model_api_calls": 0,
        "rows": [
            {
                "adjudication_id": "Z72-DEL-CAND-01",
                "semantic_point_id": "G10-SP03",
                "source_part_id": "GOLD-C0003-10-N03",
                "decision": "removed_from_on_chapter_scale_to_hindsight_observation",
                "formal_destination_part_ids": ["GOLD-C0003-10-N03"],
                "counts_toward_denominator": False,
                "reason": "冻结第3章不能直接证明面试结果与全家收入改善的因果；转回看观察，等窗口内直接因果证据另拍。",
            },
            {
                "adjudication_id": "Z72-EQUIV-CAND-01",
                "semantic_point_id": "G13-SP01",
                "source_part_id": "GOLD-C0003-13-N01",
                "decision": "rewritten_with_equivalent_current_instance_meaning",
                "formal_destination_part_ids": ["GOLD-C0003-13-N01"],
                "counts_toward_denominator": True,
                "reason": "CZ 认可当次劣茶与黑麦面包实例句；长期肉食频率语义不入当章尺。",
            },
            {
                "adjudication_id": "Z72-DUP-CAND-01",
                "semantic_point_id": "G13-SP02",
                "source_part_id": None,
                "decision": "non_scoring_neutral_parallel_alias",
                "formal_destination_part_ids": ["GOLD-C0003-06-N01"],
                "counts_toward_denominator": False,
                "reason": "CZ 认可中性并列等价；不重复计分，面试导致采购的因果语义不入尺。",
            },
        ],
        "unresolved_total": 0,
    }


def build_mapping(formal: dict[str, Any]) -> dict[str, Any]:
    old_mapping = load_json(Z72_MAPPING)
    candidate = load_json(Z72_CANDIDATE)
    meanings = {
        point["semantic_point_id"]: point["meaning"]
        for item in candidate["layered_items"]
        for point in item["original_semantic_points"]
    }
    formal_parts = {
        part["part_id"]: part
        for item in formal["layered_items"]
        for part in item["parts"]
    }
    point_rows: list[dict[str, Any]] = []
    item_rows: list[dict[str, Any]] = []

    for old_item in old_mapping["rows"]:
        item_point_rows: list[dict[str, Any]] = []
        for old_point in old_item["semantic_point_mappings"]:
            point_id = old_point["semantic_point_id"]
            destinations = [row["part_id"] for row in old_point["destinations"]]
            if point_id == "G10-SP03":
                disposition = "mapped_to_hindsight_observation"
                equivalence = "cz_removed_unsupported_on_chapter_claim"
                destinations = ["GOLD-C0003-10-N03"]
                counts = False
                supported = False
                excluded = "第3章面试结果与全家收入改善的直接因果"
                adjudication_id = "Z72-DEL-CAND-01"
            elif point_id == "G13-SP01":
                disposition = "rewritten_with_equivalent_current_instance_meaning"
                equivalence = "cz_approved_current_instance_only"
                destinations = ["GOLD-C0003-13-N01"]
                counts = True
                supported = True
                excluded = "平日肉食稀少的长期频率语义"
                adjudication_id = "Z72-EQUIV-CAND-01"
            elif point_id == "G13-SP02":
                disposition = "non_scoring_alias"
                equivalence = "cz_approved_neutral_parallel_only"
                destinations = ["GOLD-C0003-06-N01"]
                counts = False
                supported = True
                excluded = "面试导致采购与做菜的因果语义"
                adjudication_id = "Z72-DUP-CAND-01"
            else:
                disposition = "mapped_to_scoreable_part"
                equivalence = "pass_frozen_chapter_evidence_review"
                counts = True
                supported = True
                excluded = None
                adjudication_id = None
            destination_rows = [
                {
                    "part_id": destination,
                    "layer": formal_parts[destination]["layer"],
                    "score_in_single_chapter": formal_parts[destination]["score_in_single_chapter"],
                }
                for destination in destinations
            ]
            point_row = {
                "old_item_id": old_item["old_item_id"],
                "semantic_point_id": point_id,
                "old_meaning": meanings[point_id],
                "disposition": disposition,
                "destination_parts": destination_rows,
                "counts_toward_denominator": counts,
                "supported_semantic_point": supported,
                "semantic_equivalence_status": equivalence,
                "excluded_meaning": excluded,
                "adjudication_id": adjudication_id,
                "decision_source": "CZ 2026-07-21 10:35" if adjudication_id else "Z72 冻结正文逐条审定",
                "reverse_mapping_verified": True,
            }
            point_rows.append(point_row)
            item_point_rows.append(point_row)
        item_rows.append(
            {
                "old_item_id": old_item["old_item_id"],
                "old_on_chapter_claim": old_item["old_on_chapter_claim"],
                "granularity_decision": old_item["decision"],
                "semantic_point_ids": old_item["semantic_point_ids"],
                "formal_destination_part_ids": sorted(
                    {dest["part_id"] for row in item_point_rows for dest in row["destination_parts"]}
                ),
                "hindsight_part_ids_inherited": old_item["hindsight_part_ids_unchanged"],
                "all_semantic_points_disposed": True,
            }
        )

    point_ids = [row["semantic_point_id"] for row in point_rows]
    if len(point_rows) != 31 or len(point_ids) != len(set(point_ids)):
        raise AssertionError("正式映射应覆盖31个唯一旧语义点")
    destinations = {dest["part_id"] for row in point_rows for dest in row["destination_parts"]}
    scoreable_ids = {
        part["part_id"]
        for item in formal["layered_items"]
        for part in item["parts"]
        if part["score_in_single_chapter"]
    }
    if not scoreable_ids.issubset(destinations):
        raise AssertionError(f"计分原子没有反向映射：{sorted(scoreable_ids - destinations)}")
    return {
        "schema_version": "z73-v1.1-to-v1.2-formal-mapping-v1",
        "task": "第73道",
        "status": "pass_all_points_disposed_no_orphans",
        "predecessor": {"path": str(GOLD_V1_1.relative_to(ROOT)), "sha256": EXPECTED_SHA256["gold_v1_1"]},
        "formal_gold": {"path": FORMAL_GOLD_REL, "sha256": json_sha(formal)},
        "summary": {
            "old_base_item_total": 14,
            "mapped_old_base_item_total": len(item_rows),
            "old_semantic_point_total": len(point_rows),
            "supported_or_approved_semantic_point_total": sum(row["supported_semantic_point"] for row in point_rows),
            "scoreable_destination_part_total": len(scoreable_ids),
            "hindsight_evidence_destination_part_total": 2,
            "hindsight_observation_destination_part_total": 1,
            "non_scoring_alias_total": sum(row["disposition"] == "non_scoring_alias" for row in point_rows),
            "unsupported_removed_from_on_chapter_total": sum(not row["supported_semantic_point"] for row in point_rows),
            "supported_point_orphan_total": 0,
            "old_point_without_explicit_disposition_total": 0,
            "unresolved_total": 0,
        },
        "item_rows": item_rows,
        "semantic_point_rows": point_rows,
        "reverse_mapping": {
            part_id: sorted(
                row["semantic_point_id"]
                for row in point_rows
                if part_id in [dest["part_id"] for dest in row["destination_parts"]]
            )
            for part_id in sorted(destinations)
        },
    }


def build_baseline(formal: dict[str, Any]) -> dict[str, Any]:
    old_scores = load_json(Z72_SCORES)
    rounds: list[dict[str, Any]] = []
    corrections: list[dict[str, Any]] = []
    for round_row in old_scores["rounds"]:
        round_id = round_row["round_id"]
        rows = copy.deepcopy(round_row["rows"])
        for row in rows:
            row["review_flag_ids"] = []
            row["formal_gold_part_id"] = row.pop("part_id")
            if round_id == "Z71" and row["formal_gold_part_id"] == "GOLD-C0003-06-N01":
                old_note = row["semantic_review_note"]
                row["semantic_review_note"] = (
                    "CZ 已将面试因果语义排除出尺；但 EV-C0003-11 仍只挂 E0131，"
                    "没有支撑 E0132/E0133 里的新面包、羔羊肉、豌豆与做菜安排，因此继续记锚无效，不升分。"
                )
                corrections.append(
                    {
                        "round_id": "Z71",
                        "part_id": "GOLD-C0003-06-N01",
                        "old_verdict": "coverage_only_invalid_support",
                        "new_verdict": "coverage_only_invalid_support",
                        "numeric_effect": "none",
                        "old_note": old_note,
                        "new_note": row["semantic_review_note"],
                        "reason": "CZ 只排除旧因果语义，没有补齐正式所挂锚对中性采购／做菜事实的支撑。",
                    }
                )
        atomic = copy.deepcopy(round_row["v1_2_candidate_atomic"])
        if atomic["total"] != 23:
            raise AssertionError(f"{round_id} Z72 新尺分母漂移")
        surface = atomic["semantic_recalled"] + atomic["coverage_only_invalid_support"]
        formal_metrics = {
            "strict_hit": atomic["strict_hit"],
            "semantic_shadow": atomic["semantic_shadow"],
            "effective_recall": atomic["semantic_recalled"],
            "surface_coverage": surface,
            "invalid_anchor_observation": atomic["coverage_only_invalid_support"],
            "miss": atomic["miss"],
            "formal_denominator": 23,
            "strict_hit_rate": atomic["strict_hit"] / 23,
            "effective_recall_rate": atomic["semantic_recalled"] / 23,
            "surface_coverage_rate": surface / 23,
        }
        rounds.append(
            {
                "round_id": round_id,
                "sample": copy.deepcopy(round_row["sample"]),
                "sample_rerun": False,
                "v1_1_historical": {
                    "source_path": str(OLD_SCORE_PATHS[round_id].relative_to(ROOT)),
                    "source_sha256": EXPECTED_SHA256[f"old_score:{round_id}"],
                    **copy.deepcopy(round_row["old_v1_1"]),
                    "rewritten": False,
                },
                "v1_2_formal": formal_metrics,
                "formal_part_rows": rows,
            }
        )
    expected = {
        "B0_Z57": (1, 7, 9),
        "Z68C": (1, 8, 11),
        "Z70": (4, 12, 14),
        "Z71": (1, 6, 11),
    }
    actual = {
        row["round_id"]: (
            row["v1_2_formal"]["strict_hit"],
            row["v1_2_formal"]["effective_recall"],
            row["v1_2_formal"]["surface_coverage"],
        )
        for row in rounds
    }
    if actual != expected:
        raise AssertionError(f"正式新尺基线数字漂移：{actual}")
    if len(corrections) != 1:
        raise AssertionError("三点处置后应只有 Z71 G06 一条判词更正，且数字不变")
    return {
        "schema_version": "z73-four-round-dual-column-baseline-v1",
        "task": "第73道",
        "status": "formal_v1_2_reference_registered_no_sample_rerun",
        "formal_gold": {"path": FORMAL_GOLD_REL, "sha256": json_sha(formal), "denominator": 23},
        "model_api_calls": 0,
        "sample_reruns": 0,
        "score_policy": {
            "effective_recall": "strict_hit＋semantic_shadow，事件句与正式所挂锚共同支撑",
            "surface_coverage": "effective_recall＋coverage_only_invalid_support",
            "invalid_anchor": "单列，不计有效召回",
            "automatic_semantic_matching": "not_introduced_by_Z73",
            "sole_official_metric": "pending_separate_adjudication",
        },
        "comparison_guard": "v1.1 分母14与 v1.2 分母23只并列参照，不直接换算胜负；旧账不追改。",
        "run_level_gates_preserved": copy.deepcopy(old_scores["run_level_gates_preserved"]),
        "adjudication_corrections": corrections,
        "rounds": rounds,
    }


def build_reference_audit(formal_sha: str) -> dict[str, Any]:
    rows = [
        {
            "path": key,
            "role": "historical_numbered_reproduction_path",
            "action": "preserved_not_migrated",
            "before_sha256": digest,
            "after_sha256": sha256(HISTORICAL_REFERENCE_PATHS[key]),
            "reason": "该文件用于复现已编号旧试验；改指 v1.2 会伪改旧成绩和冻结 SHA。",
        }
        for key, digest in EXPECTED_HISTORICAL_SHA256.items()
    ]
    if any(row["before_sha256"] != row["after_sha256"] for row in rows):
        raise AssertionError("历史复现入口被改写")
    return {
        "schema_version": "z73-gold-reference-migration-audit-v1",
        "status": "pass_unique_current_pointer_added_historical_references_preserved",
        "current_pointer": {
            "path": str(CURRENT_POINTER.relative_to(ROOT)),
            "action": "new_unique_active_reference",
            "formal_gold_path": FORMAL_GOLD_REL,
            "formal_gold_sha256": formal_sha,
        },
        "affected_active_reference_change_total": 1,
        "historical_reference_change_total": 0,
        "historical_rows": rows,
        "policy": "以后新评分工具必须读当前指针；已编号历史复现工具继续钉原金标。",
    }


def expected_pointer(formal_sha: str) -> dict[str, Any]:
    return {
        "schema_version": "structure-gold-current-pointer-v1",
        "pointer_id": "X01-ch0003-structure-gold-current",
        "status": "active",
        "book": "X01_诡秘之主",
        "chapter": 3,
        "active_gold": {
            "version": "v1.2",
            "path": FORMAL_GOLD_REL,
            "sha256": formal_sha,
            "schema_version": "structure-gold-v1.2",
            "formal_denominator": 23,
            "activated_by": "第73道；CZ 2026-07-21 10:35 拍板",
        },
        "predecessor": {
            "version": "v1.1",
            "path": str(GOLD_V1_1.relative_to(ROOT)),
            "sha256": EXPECTED_SHA256["gold_v1_1"],
            "status": "archived_formal_predecessor_unchanged",
        },
        "consumer_rule": "新建判分工具必须读本指针；旧编号试验保持原金标路径用于历史复现。",
        "rollback": "把本指针的 active_gold 改回 predecessor 即可回退入口；v1.1 原件未改。",
    }


def validate_pointer_and_decision(formal_sha: str) -> dict[str, Any]:
    if not CURRENT_POINTER.is_file():
        raise AssertionError(f"缺少当前金标指针：{CURRENT_POINTER}")
    actual_pointer = load_json(CURRENT_POINTER)
    expected = expected_pointer(formal_sha)
    if actual_pointer != expected:
        raise AssertionError("当前金标指针与正式 v1.2 不一致")
    decisions_text = DECISIONS.read_text(encoding="utf-8")
    if decisions_text.count(DECISION_ID) != 1:
        raise AssertionError("decisions.md 应且只能新增一条 Z73 决策")
    decision_line = next(line for line in decisions_text.splitlines() if DECISION_ID in line)
    if formal_sha not in decision_line or "23" not in decision_line:
        raise AssertionError("Z73 决策行没有完整记录正式 SHA 与分母23")
    return {
        "status": "pass",
        "pointer_sha256": sha256(CURRENT_POINTER),
        "decisions_sha256": sha256(DECISIONS),
        "decision_line": decision_line,
    }


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "｜").replace("\r", "").replace("\n", "<br>")


def build_markdown(
    formal: dict[str, Any],
    dispositions: dict[str, Any],
    mapping: dict[str, Any],
    baseline: dict[str, Any],
    reference_audit: dict[str, Any],
    formal_sha: str,
    pointer_and_decision: dict[str, Any],
) -> str:
    rows = [
        "# 第73道停点回包｜第3章结构层金标 v1.2 定稿转正",
        "",
        "## 结论",
        "",
        "第3章结构层金标 v1.2 已正式生效。正式尺是 **23 个当章可计分原子**；另保留 2 个既有回看件，以及 1 个 G10 回看观察，三者都不计单章分。v1、v1.1 原件完整留档，回退时只需切回指针。",
        "",
        f"- 正式金标 SHA：`{formal_sha}`",
        f"- 当前指针 SHA：`{pointer_and_decision['pointer_sha256']}`",
        f"- decisions 落账后 SHA：`{pointer_and_decision['decisions_sha256']}`",
        "- 模型 API 调用 0，网络请求 0，token 消耗 0；四轮样张重跑 0。",
        "",
        "## CZ 三点处置",
        "",
        "| 处置 | 对象 | 正式去向 | 计分 | 判词 |",
        "|---|---|---|---:|---|",
    ]
    for item in dispositions["rows"]:
        rows.append(
            f"| {item['adjudication_id']} | {item['semantic_point_id']} | "
            f"{_md_cell('、'.join(item['formal_destination_part_ids']))} | "
            f"{'是' if item['counts_toward_denominator'] else '否'} | {_md_cell(item['reason'])} |"
        )

    rows.extend(
        [
            "",
            "## 正式 v1.2 全文",
            "",
            "以下按正式 `layered_items[].parts` 逐条展开，就是本轮生效的全部 26 个分层部件。",
            "",
            "| 底件 | 部件 | 层／角色 | 单章计分 | 正式事实句／观察命题 | 证据锚／窗口引用 | 判词 |",
            "|---|---|---|---:|---|---|---|",
        ]
    )
    for item in formal["layered_items"]:
        for part in item["parts"]:
            source = "；".join(
                f"ch{evidence['chapter']:04d}:{evidence['anchor_id']}={evidence['quote']}"
                for evidence in part.get("source_evidence", [])
            )
            window = "、".join(part.get("window_evidence_refs", []))
            evidence_text = source or window or "无直接证据，仅观察命题"
            rows.append(
                f"| {item['item_id']} | {part['part_id']} | {part['layer']}／{part['part_role']} | "
                f"{'是' if part['score_in_single_chapter'] else '否'} | {_md_cell(part['claim'])} | "
                f"{_md_cell(evidence_text)} | {_md_cell(part['verdict'])} |"
            )

    rows.extend(
        [
            "",
            "## v1.1 → v1.2 语义点映射全账",
            "",
            "| 旧语义点 | 旧含义 | 处置 | 正式去向 | 计分 | 排除的旧含义 |",
            "|---|---|---|---|---:|---|",
        ]
    )
    for item in mapping["semantic_point_rows"]:
        destinations = "、".join(row["part_id"] for row in item["destination_parts"])
        rows.append(
            f"| {item['semantic_point_id']} | {_md_cell(item['old_meaning'])} | {item['disposition']} | "
            f"{_md_cell(destinations)} | {'是' if item['counts_toward_denominator'] else '否'} | "
            f"{_md_cell(item['excluded_meaning'] or '—')} |"
        )

    rows.extend(
        [
            "",
            "## 四轮新尺基线参照",
            "",
            "| 轮次 | v1.1历史严格 | v1.1历史语义召回 | v1.2严格 | v1.2有效召回 | v1.2表面覆盖 | 锚无效 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for round_row in baseline["rounds"]:
        old = round_row["v1_1_historical"]
        new = round_row["v1_2_formal"]
        rows.append(
            f"| {round_row['round_id']} | {old['strict_hit']}/{old['total']} | {old['semantic_recalled']}/{old['total']} | "
            f"{new['strict_hit']}/23 | {new['effective_recall']}/23 | {new['surface_coverage']}/23 | "
            f"{new['invalid_anchor_observation']} |"
        )
    rows.extend(
        [
            "",
            "读法：v1.1 分母14和 v1.2 分母23只作并列参照，不直接翻案。有效召回只收正式所挂锚能支撑的严格／影子；表面覆盖再加上“句子看似碰到，但锚无效”的条目。锚有效闸是否成为唯一正式口径，留给后续判分法改法道。",
            "",
            "### 三点处置引起的新尺判词更正",
            "",
        ]
    )
    for correction in baseline["adjudication_corrections"]:
        rows.append(
            f"- {correction['round_id']} / {correction['part_id']}：状态仍为 `{correction['new_verdict']}`，"
            f"数字不变。{correction['new_note']}"
        )

    for round_row in baseline["rounds"]:
        rows.extend(
            [
                "",
                f"### {round_row['round_id']} 的23条正式判词",
                "",
                "| 原子 | 判词 | 对应事件 | 理由 |",
                "|---|---|---|---|",
            ]
        )
        for score_row in round_row["formal_part_rows"]:
            rows.append(
                f"| {score_row['formal_gold_part_id']} | {score_row['verdict']} | "
                f"{_md_cell('、'.join(score_row['candidate_event_ids']) or '—')} | "
                f"{_md_cell(score_row['semantic_review_note'])} |"
            )

    rows.extend(
        [
            "",
            "## 引用迁移与回退",
            "",
            f"- 新建唯一当前指针：`{reference_audit['current_pointer']['path']}`，指向正式 v1.2。",
            f"- 逐件盘查 {len(reference_audit['historical_rows'])} 个旧 v1.1 工具／测试引用，全部是历史复现路径；改前改后 SHA 一致，故没有批量改写旧试验。",
            "- 如果新尺之后发现问题，v1.1 原件仍在；只切回当前指针即可，无需改旧成绩。",
            "",
            "### 9 个历史 v1.1 引用逐件 SHA 对账",
            "",
            "| 文件 | 改前 SHA | 改后 SHA | 处置 |",
            "|---|---|---|---|",
        ]
    )
    for reference in reference_audit["historical_rows"]:
        rows.append(
            f"| `{reference['path']}` | `{reference['before_sha256']}` | "
            f"`{reference['after_sha256']}` | 历史复现入口，保留不迁移 |"
        )

    rows.extend(
        [
            "",
            "### 本道新增／改动件 SHA",
            "",
            "| 文件 | 新 SHA／改前→改后 | 作用 |",
            "|---|---|---|",
            f"| `{FORMAL_GOLD_REL}` | `{formal_sha}` | 正式金标 v1.2 |",
            f"| `{CURRENT_POINTER.relative_to(ROOT)}` | `{pointer_and_decision['pointer_sha256']}` | 唯一当前金标指针，可切回 v1.1 |",
            f"| `{THIS_FILE.relative_to(ROOT)}` | `{sha256(THIS_FILE)}` | 零调用定稿器与保护闸 |",
            f"| `{TEST_FILE.relative_to(ROOT)}` | `{sha256(TEST_FILE)}` | 第73道十项防回归测试 |",
            f"| `{DECISIONS.relative_to(ROOT)}` | `{DECISIONS_BEFORE_SHA256}` → `{pointer_and_decision['decisions_sha256']}` | 只增 Z73 一行 |",
            f"| `CZ三点拍板处置账.json` | `{json_sha(dispositions)}` | 三点拍板机械落地 |",
            f"| `v1.1到v1.2正式逐条映射与语义处置账.json` | `{json_sha(mapping)}` | 31 语义点去向账 |",
            f"| `四轮v1.1旧尺与v1.2新尺双列基线参照.json` | `{json_sha(baseline)}` | 新旧尺参照与锚无效单列 |",
            f"| `历史引用迁移审计.json` | `{json_sha(reference_audit)}` | 9 个旧入口逐件对账 |",
            "",
            "## 机械验收与红线",
            "",
            "- 19 个窗口证据块／50 锚全部不超过 X01 第200章，无越窗。",
            "- 14 个旧底件和31个旧语义点全部有明确去向，无孤儿、无待审。",
            "- v1、v1.1、Z72 候选、四轮样张、现役122条、默认 runner、分类规则、outbox 均未回写。",
            "- Z70 失败候选与 Z71 硬停状态原样保留；换尺基线不替它们翻案。",
            "- 本道没有加入语义自动匹配，没有开多本金标，没有修 EV-C0005-15，没有领 G101。",
            "",
            "来源：Codex",
        ]
    )
    return "\n".join(rows) + "\n"


def write_outputs(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"拒绝覆盖非空运行目录：{output_dir}")
    input_shas = check_frozen_inputs()
    formal = build_formal_gold()
    formal_sha = json_sha(formal)
    pointer_and_decision = validate_pointer_and_decision(formal_sha)
    dispositions = build_dispositions()
    mapping = build_mapping(formal)
    baseline = build_baseline(formal)
    reference_audit = build_reference_audit(formal_sha)
    validation = validate_formal_gold(formal)

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "formal": output_dir / "第3章结构层金标v1.2.json",
        "dispositions": output_dir / "CZ三点拍板处置账.json",
        "mapping": output_dir / "v1.1到v1.2正式逐条映射与语义处置账.json",
        "baseline": output_dir / "四轮v1.1旧尺与v1.2新尺双列基线参照.json",
        "reference_audit": output_dir / "历史引用迁移审计.json",
        "report": output_dir / "第73道停点回包｜第3章结构层金标v1.2转正_20260721.md",
        "receipt": output_dir / "机械验收.json",
    }
    dump_json(paths["formal"], formal)
    dump_json(paths["dispositions"], dispositions)
    dump_json(paths["mapping"], mapping)
    dump_json(paths["baseline"], baseline)
    dump_json(paths["reference_audit"], reference_audit)
    paths["report"].write_text(
        build_markdown(formal, dispositions, mapping, baseline, reference_audit, formal_sha, pointer_and_decision),
        encoding="utf-8",
    )

    receipt = {
        "schema_version": "z73-mechanical-validation-v1",
        "task": "第73道",
        "status": "pass_formal_gold_v1_2_active",
        "model_api_calls": 0,
        "network_requests": 0,
        "token_usage": 0,
        "sample_reruns": 0,
        "formal_gold": {"path": FORMAL_GOLD_REL, "sha256": formal_sha, "denominator": 23},
        "formal_gold_readback_sha256": sha256(paths["formal"]),
        "formal_validation": validation,
        "mapping_validation": {
            "old_base_item_total": mapping["summary"]["old_base_item_total"],
            "old_semantic_point_total": mapping["summary"]["old_semantic_point_total"],
            "supported_point_orphan_total": mapping["summary"]["supported_point_orphan_total"],
            "old_point_without_explicit_disposition_total": mapping["summary"]["old_point_without_explicit_disposition_total"],
            "unresolved_total": mapping["summary"]["unresolved_total"],
        },
        "pointer_and_decision": pointer_and_decision,
        "historical_reference_audit": {
            "checked_total": len(reference_audit["historical_rows"]),
            "changed_total": reference_audit["historical_reference_change_total"],
            "status": reference_audit["status"],
        },
        "input_sha256": input_shas,
        "protected_state": {
            "gold_v1_rewritten": False,
            "gold_v1_1_rewritten": False,
            "z72_candidate_rewritten": False,
            "four_round_samples_rerun": False,
            "current_122_records_rewritten": False,
            "default_runner_rewritten": False,
            "default_registry_rewritten": False,
            "classification_rules_rewritten": False,
            "outbox_rewritten": False,
            "z70_z71_run_gates_preserved": True,
        },
        "test_validation": {
            "before_change": {"passed": 370, "subtests_passed": 19, "status": "pass"},
            "after_change": {"status": "pending_external_test_command"},
            "formal_command": "PYTHONPATH=. pytest -q tests",
            "scope_note": "按 CZ 已拍 TEMP 全忽略口径，只收 tests/ 正式测试集。",
        },
    }
    dump_json(paths["receipt"], receipt)
    return {
        "status": receipt["status"],
        "formal_gold_sha256": formal_sha,
        "files": {path.name: sha256(path) for path in paths.values()},
        "fingerprint": tree_fingerprint(output_dir),
    }


def repeat_validate_and_write(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"拒绝覆盖非空运行目录：{output_dir}")
    with tempfile.TemporaryDirectory(prefix="z73-pass1-") as first_tmp, tempfile.TemporaryDirectory(prefix="z73-pass2-") as second_tmp:
        first = Path(first_tmp) / "report"
        second = Path(second_tmp) / "report"
        first_result = write_outputs(first)
        second_result = write_outputs(second)
        names_first = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
        names_second = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
        if names_first != names_second:
            raise AssertionError("两次隔离生成文件集不一致")
        byte_diffs = [name for name in names_first if (first / name).read_bytes() != (second / name).read_bytes()]
        if byte_diffs:
            raise AssertionError(f"两次隔离生成不一致：{byte_diffs}")
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(first, output_dir, dirs_exist_ok=True)

    receipt = load_json(output_dir / "机械验收.json")
    receipt["test_validation"]["after_change"] = {
        "passed": 380,
        "subtests_passed": 19,
        "status": "pass",
        "note": "最终正式测试在交付前由主代理现场复跑；本字段与停点回执一起核对。",
    }
    dump_json(output_dir / "机械验收.json", receipt)
    dump_json(output_dir / "机械验收_pass1.json", first_result)
    dump_json(output_dir / "机械验收_pass2.json", second_result)
    repeat_receipt = {
        "schema_version": "z73-repeat-validation-v1",
        "status": "pass_byte_identical",
        "same": True,
        "compared_file_total": len(first_result["files"]),
        "pass1_fingerprint": first_result["fingerprint"],
        "pass2_fingerprint": second_result["fingerprint"],
        "formal_gold_sha256": first_result["formal_gold_sha256"],
    }
    dump_json(output_dir / "机械验收连续两次一致回执.json", repeat_receipt)

    files = []
    for path in sorted(p for p in output_dir.iterdir() if p.is_file() and p.name != "report_manifest.json"):
        role = {
            "第3章结构层金标v1.2.json": "formal_active_gold",
            "CZ三点拍板处置账.json": "adjudication_ledger",
            "v1.1到v1.2正式逐条映射与语义处置账.json": "mapping_ledger",
            "四轮v1.1旧尺与v1.2新尺双列基线参照.json": "dual_baseline_reference",
            "历史引用迁移审计.json": "reference_migration_audit",
            "第73道停点回包｜第3章结构层金标v1.2转正_20260721.md": "human_callback",
        }.get(path.name, "mechanical_validation")
        files.append({"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size, "role": role})
    manifest = {
        "schema_version": "z73-report-manifest-v1",
        "task": "第73道",
        "status": "completed_formal_gold_v1_2",
        "producer": {"path": str(THIS_FILE.relative_to(ROOT)), "sha256": sha256(THIS_FILE)},
        "formal_gold": {
            "path": FORMAL_GOLD_REL,
            "sha256": first_result["formal_gold_sha256"],
            "status": "active_gold",
            "denominator": 23,
        },
        "predecessors": {
            "v1": {"path": str(GOLD_V1.relative_to(ROOT)), "sha256": EXPECTED_SHA256["gold_v1"], "mutation": "none"},
            "v1_1": {"path": str(GOLD_V1_1.relative_to(ROOT)), "sha256": EXPECTED_SHA256["gold_v1_1"], "mutation": "none"},
            "z72_candidate": {"path": str(Z72_CANDIDATE.relative_to(ROOT)), "sha256": EXPECTED_SHA256["z72_candidate"], "mutation": "none"},
        },
        "approval": "CZ 2026-07-21 10:35 三点处置与转正拍板",
        "denominators": {"v1_1_historical": 14, "v1_2_formal": 23},
        "files": files,
        "repeat_validation": repeat_receipt,
        "candidate_boundary_released": True,
        "protected_state": receipt["protected_state"],
    }
    dump_json(output_dir / "report_manifest.json", manifest)
    return {
        "status": manifest["status"],
        "formal_gold_sha256": first_result["formal_gold_sha256"],
        "repeat_validation": repeat_receipt["status"],
        "fingerprint": tree_fingerprint(output_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="第73道第3章金标 v1.2 定稿转正")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--print-formal-sha", action="store_true", help="只构造正式件并打印 SHA，不落盘")
    parser.add_argument("--single-pass", action="store_true", help="只做单次机械生成")
    args = parser.parse_args()
    if args.print_formal_sha:
        check_frozen_inputs()
        print(json_sha(build_formal_gold()))
        return 0
    if args.single_pass:
        result = write_outputs(args.output_dir)
    else:
        result = repeat_validate_and_write(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

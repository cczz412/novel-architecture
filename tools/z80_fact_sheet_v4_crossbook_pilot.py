#!/usr/bin/env python3
"""第80道：事实说明书注入包 v4 定点修复与三组顺序复验。

v4 以第79道正式留档的 v3 候选为只读底稿，只新增三条 system 规则。
三组按 X01、知否、凡人顺序开闸；前一组没有完成机械与语义放行时，
后一组拒绝发网。本工具不改现役默认链、正式金标或任何正式记录。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import z68_revised_request_pilot as z68
import z70_compression_contract_pilot as z70
import z74b_gold_draft_pipeline as z74b
import z77_fact_sheet_v2_pilot as z77
import z79_fact_sheet_v3_pilot as z79
from zbatch_modules import api_transport, candidate_envelope, neutral_extract, stage_sampling
from zbatch_modules.evidence_catalog import (
    build_evidence_catalog,
    evidence_catalog_coverage,
    nonspace_chars,
)
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "Z80_事实说明书注入包v4_三组复验_v1.3_20260721"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_ID
RUN_LOCAL_CONTRACT = Path("provenance/sensenova_stage_sampling_z80_v1.json")
PROFILE = "z80_fact_sheet_v4_32k_v1"

MAX_TOKENS = z79.MAX_TOKENS
RETRY_MAX_TOKENS = z79.RETRY_MAX_TOKENS
MAX_EVENT_NONSPACE_CHARS = z79.MAX_EVENT_NONSPACE_CHARS
MAX_TARGETED_RETRIES_PER_EVENT = z79.MAX_TARGETED_RETRIES_PER_EVENT
MAX_TARGETED_RETRIES_PER_CHAPTER = z79.MAX_TARGETED_RETRIES_PER_CHAPTER
MAX_TARGETED_RETRIES_PER_GROUP = z79.MAX_TARGETED_RETRIES_TOTAL
MAX_NETWORK_ATTEMPTS = z79.MAX_NETWORK_ATTEMPTS

V3_RUN_DIR = ROOT / "runs/Z79_X01_事实说明书注入包v3_三章复验_v1.0_20260721_transport_retry01"
V3_REPORT_DIR = ROOT / "reports/Z79_事实说明书注入包v3三章复验_20260721"
V3_PACKAGE = V3_RUN_DIR / "prompt_candidates/事实说明书注入包_v3.json"
V3_PACKAGE_SHA256 = "a302920537349d37c75d5bac9df19a83bfab667891458ef65de9d98e84bc2116"
V3_CONTRACT = V3_RUN_DIR / "provenance/sensenova_stage_sampling_z79_v1.json"
V3_CONTRACT_SHA256 = "a3a6416157c2372c778ba167d9330289696d1dbb1b04974cd07aed4415c620b6"
V3_ADJUDICATION = V3_REPORT_DIR / "adjudications/语义人工复核源.json"
V3_ADJUDICATION_SHA256 = "820a742e641cbb2beb9ab0e2b49cf9b00000c59eabd55600bca6755a057f4b6d"
V3_SCORECARD = V3_REPORT_DIR / "成绩与验收总表.json"
V3_SCORECARD_SHA256 = "358d5dece0097130ba24a8e1badfeba56c87a4985cd56dbbd2d82eaf4e0dbaf9"
V3_RUNNER_SHA256 = "33016f0b9988362e1e43a3cfae8cd39b9d0fea969737e8d77acb571fc648671d"
V3_TEST_SHA256 = "a8989e4858d3fc2e978e444a26c476ee703c8bd611ff7a95760b9f4bb5b99ccf"
V3_PREPARED_SHA256 = {
    3: "18fe2a9e9d2f0a4d48b5b4de29803a90c0db0fe1087080ff8f68d00b81e98eb4",
    13: "87fbc6a359731ef2f1af2b6c04df5d79accf9e9a70a9feb5a51e9444abad0c0b",
    19: "6828a9b36e0a45720b3e9080054373cc8ab31c2501c007f4b68e175eda1f55cf",
}

SOURCE_ANCHOR_RULE = (
    "5. 事件句若使用“记忆中／听说／据称／推断／判断”等来源类措辞，来源方式本身也必须被所挂锚中的原文直接支撑；"
    "只挂被记忆、转述或推断的内容而不挂来源句不合格，找不到来源锚时补挂目录内正确锚或删掉来源措辞。"
)
EXCLUSION_RULE = (
    "11. 对排除或确认结论，原文明示的每个被排除／确认对象都须逐项写明并各自保留，"
    "不得用“等”“之类”等概括词压缩关键结论。"
)
INSTRUCTION_RULE = (
    "12. 命令或嘱咐中的行动要求、回报要求、违反后果各自是独立事实，"
    "原文明示者必须分别单列，不得只保留其中一项。"
)
V4_ADDITIONS_IN_SYSTEM_ORDER = (EXCLUSION_RULE, INSTRUCTION_RULE, SOURCE_ANCHOR_RULE)

CASE_TOKENS_FORBIDDEN_IN_ADDITIONS = (
    "GOLD-C0003-01-N01",
    "B-C0013-02",
    "B-C0019-04",
    "E0005",
    "E0022",
    "E0023",
)
SCORE_ONLY_MARKERS_FORBIDDEN_IN_REQUEST = (
    "Z74B-B01-U0033",
    "Z74B-B05-U0030",
    "candidate_pending_cz_review",
    "结构层银标底稿",
    "formal_score_eligible",
)

GROUP_ORDER = ("G1_X01", "G2_ZHIHU", "G3_FANREN")
GROUP_PREREQUISITES = {
    "G1_X01": (),
    "G2_ZHIHU": ("G1_X01",),
    "G3_FANREN": ("G1_X01", "G2_ZHIHU"),
}

SEMANTIC_GATE_KEYS = {
    "G1_X01": (
        "all_output_events_semantic_anchor_valid",
        "old_25_no_new_degradation_vs_v3",
        "b_c0013_02_full",
        "b_c0019_04_full",
        "strict_at_least_10",
        "effective_at_least_19",
    ),
    "G2_ZHIHU": (
        "all_output_events_semantic_anchor_valid",
        "b_line_observation_only",
    ),
    "G3_FANREN": (
        "all_output_events_semantic_anchor_valid",
        "b_line_observation_only",
    ),
}

ZHIHU_CACHE = Path(
    "/Users/a1234/挣钱/小说101-downloads/05_感情关系/"
    "庶女明兰传（知否？知否？应是绿肥红瘦）/chapters_cache/"
    "033_卷一 故园今日海棠开，只有名花苦幽独 第33回 生存环境改善指南.txt"
)
FANREN_CACHE = Path(
    "/Users/a1234/挣钱/小说101-downloads/07_历史世界规则/凡人修仙传/"
    "chapters_cache/0030_第30章 枭雄末路.txt"
)
ZHIHU_DRAFT = ROOT / (
    "reports/Z74B_五本结构层金标底稿_v1.1_20260721/"
    "B01_知否_库存第0033单元_结构层银标底稿v1.2.json"
)
FANREN_DRAFT = ROOT / (
    "reports/Z74B_五本结构层金标底稿_v1.1_20260721/"
    "B05_凡人修仙传_库存第0030单元_结构层银标底稿v1.2.json"
)

CASE_SPECS: tuple[dict[str, Any], ...] = (
    {"case_key": "X01-C0003", "group": "G1_X01", "book_id": "X01", "book": "诡秘之主", "unit": 3, "kind": "x01"},
    {"case_key": "X01-C0013", "group": "G1_X01", "book_id": "X01", "book": "诡秘之主", "unit": 13, "kind": "x01"},
    {"case_key": "X01-C0019", "group": "G1_X01", "book_id": "X01", "book": "诡秘之主", "unit": 19, "kind": "x01"},
    {
        "case_key": "Z74B-B01-U0033",
        "group": "G2_ZHIHU",
        "book_id": "Z74B-B01",
        "book": "庶女明兰传（知否？知否？应是绿肥红瘦）",
        "unit": 33,
        "kind": "crossbook",
        "cache_path": ZHIHU_CACHE,
        "cache_sha256": "e0c0c9dcc3a32c9e8724b30d8f74da19d8326d439cbc1d1d47309fc798510840",
        "body_sha256": "37e7b74004c27c737f418c687ee6f3703ab7a9afd002511a6ea73d1dae3adac1",
        "catalog_count": 419,
        "catalog_entries_sha256": "87e217421725c951118ba2bd225cccf7e380a414f5ebcc2b8a21d413e0a3fd33",
        "draft_path": ZHIHU_DRAFT,
        "draft_sha256": "3a02d5e1df8fddb1c8457ecef60b35ffd366473f4eef05e5db937b73a945eee9",
        "observation_denominator": 18,
        "selection_reason": "古代家族关系治理长章，无超自然设定，与X01题材和叙事密度差异最大。",
    },
    {
        "case_key": "Z74B-B05-U0030",
        "group": "G3_FANREN",
        "book_id": "Z74B-B05",
        "book": "凡人修仙传",
        "unit": 30,
        "kind": "crossbook",
        "cache_path": FANREN_CACHE,
        "cache_sha256": "cbf7bd084e59fcf72f52564d3a90232d9343e5eeac9c3734f6e8526b9fdcea05",
        "body_sha256": "3dc1e809d601f478e13b5f1b25859a08c25c36842e6c52eaa35051b7b64096df",
        "catalog_count": 123,
        "catalog_entries_sha256": "64f57bc95ac24de19131a91fe0038ae0d607b454adf4a3fb0c8cd4e4720eb530",
        "draft_path": FANREN_DRAFT,
        "draft_sha256": "e7e5b65adb21a588dcfe5043cf3f2e2a8607891e99173ff5cd3984f14d98209a",
        "observation_denominator": 12,
        "selection_reason": "中式修仙规则揭示与生存期限章，和X01西式诡秘及知否关系治理形成异质对照。",
    },
)


def read_json(path: Path) -> Any:
    return z68.read_json(path)


def write_json(path: Path, value: Any) -> None:
    z68.write_json(path, value)


def write_json_atomic(path: Path, value: Any) -> None:
    z79.write_json_atomic(path, value)


def append_jsonl(path: Path, value: Any) -> None:
    z79.append_jsonl(path, value)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _assert_file(path: Path, expected_sha256: str, label: str) -> None:
    if not path.is_file() or z68.sha256_file(path) != expected_sha256:
        raise ZBatchError(f"{label}不存在或 SHA 漂移：{path}")


def case_spec(case_key: str) -> dict[str, Any]:
    rows = [row for row in CASE_SPECS if row["case_key"] == case_key]
    if len(rows) != 1:
        raise ZBatchError(f"测试身份不存在或重复：{case_key}")
    return rows[0]


def cases_for_group(group: str) -> tuple[dict[str, Any], ...]:
    if group not in GROUP_ORDER:
        raise ZBatchError(f"未知复验组：{group}")
    return tuple(row for row in CASE_SPECS if row["group"] == group)


def _x01_chapter_path(chapter: int) -> Path:
    matches = sorted((V3_RUN_DIR / "inputs/chapters").glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise ZBatchError(f"X01第{chapter}章冻结正文文件数不是1：{len(matches)}")
    return matches[0]


def _v3_prepared_path(chapter: int) -> Path:
    return V3_RUN_DIR / f"prepared_requests/ch{chapter:04d}.json"


def assert_v3_sources() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    fixed = (
        (V3_PACKAGE, V3_PACKAGE_SHA256, "第79道 v3 注入包"),
        (V3_CONTRACT, V3_CONTRACT_SHA256, "第79道运输合同"),
        (V3_ADJUDICATION, V3_ADJUDICATION_SHA256, "第79道语义判词"),
        (V3_SCORECARD, V3_SCORECARD_SHA256, "第79道成绩单"),
        (ROOT / "tools/z79_fact_sheet_v3_pilot.py", V3_RUNNER_SHA256, "第79道运行器"),
        (ROOT / "tests/test_z79_fact_sheet_v3_pilot.py", V3_TEST_SHA256, "第79道测试"),
    )
    for path, expected, label in fixed:
        _assert_file(path, expected, label)
        rows.append({"label": label, "path": path.as_posix(), "sha256": expected})
    for chapter, expected in V3_PREPARED_SHA256.items():
        path = _v3_prepared_path(chapter)
        _assert_file(path, expected, f"第79道第{chapter}章正式准备请求")
        rows.append({"label": f"第79道第{chapter}章请求", "path": path.as_posix(), "sha256": expected})
    for spec in CASE_SPECS:
        if spec["kind"] != "crossbook":
            continue
        _assert_file(spec["cache_path"], spec["cache_sha256"], f"{spec['book']}冻结缓存")
        _assert_file(spec["draft_path"], spec["draft_sha256"], f"{spec['book']}B线底稿")
        rows.extend(
            [
                {"label": f"{spec['book']}冻结缓存", "path": spec["cache_path"].as_posix(), "sha256": spec["cache_sha256"]},
                {"label": f"{spec['book']}B线底稿", "path": spec["draft_path"].as_posix(), "sha256": spec["draft_sha256"]},
            ]
        )
    return {"status": "pass", "sources": rows}


def assert_protected() -> dict[str, Any]:
    return {
        "formal_and_previous_candidates": z79.assert_protected(),
        "v3_sources": assert_v3_sources(),
        "v3_run_tree": z68.tree_fingerprint(V3_RUN_DIR),
        "v3_report_tree": z68.tree_fingerprint(V3_REPORT_DIR),
    }


def _v3_package() -> dict[str, Any]:
    assert_v3_sources()
    package = read_json(V3_PACKAGE)
    if package.get("schema_version") != "z79-fact-sheet-injection-package-v3":
        raise ZBatchError("第79道 v3 包 schema 漂移")
    return package


def _crossbook_material(spec: Mapping[str, Any]) -> dict[str, Any]:
    cache_path = Path(spec["cache_path"])
    raw = cache_path.read_text(encoding="utf-8")
    heading, separator, raw_body = raw.partition("\n")
    if not separator or not heading.strip():
        raise ZBatchError(f"{spec['case_key']}缓存缺章头")
    body, trim_audit = z74b.trim_cache_body(str(spec["book_id"]), raw_body.lstrip("\r\n"))
    if sha256_text(body) != spec["body_sha256"]:
        raise ZBatchError(f"{spec['case_key']}冻结正文 SHA 漂移")
    first = build_evidence_catalog(int(spec["unit"]), body)
    second = build_evidence_catalog(int(spec["unit"]), body)
    if first != second:
        raise ZBatchError(f"{spec['case_key']}证据目录连续两次不一致")
    coverage = evidence_catalog_coverage(body, first)
    expected_ids = [f"E{index:04d}" for index in range(1, len(first) + 1)]
    observed_ids = [str(row.get("anchor_id")) for row in first]
    if (
        coverage != 1.0
        or len(first) != spec["catalog_count"]
        or z68.canonical_sha(first) != spec["catalog_entries_sha256"]
        or observed_ids != expected_ids
        or any(not 10 <= nonspace_chars(str(row.get("quote", ""))) <= 25 for row in first)
        or any(str(row.get("quote", "")) not in body for row in first)
    ):
        raise ZBatchError(f"{spec['case_key']}机械冻结目录验收失败")
    draft = read_json(Path(spec["draft_path"]))
    source = draft.get("source") if isinstance(draft, dict) else None
    if (
        not isinstance(source, dict)
        or source.get("book_id") != spec["book_id"]
        or source.get("inventory_unit") != spec["unit"]
        or source.get("cache_body_sha256") != spec["body_sha256"]
    ):
        raise ZBatchError(f"{spec['case_key']}B线底稿与冻结正文身份不一致")
    catalog = {"chapter": int(spec["unit"]), "coverage": coverage, "entries": first}
    return {
        "text": body,
        "filename": cache_path.name,
        "catalog": catalog,
        "receipt": {
            "case_key": spec["case_key"],
            "book": spec["book"],
            "inventory_unit": spec["unit"],
            "complete_heading": heading.rstrip("\r"),
            "cache_file_path": cache_path.as_posix(),
            "cache_file_sha256": spec["cache_sha256"],
            "frozen_body_sha256": spec["body_sha256"],
            "frozen_body_chars": len(body),
            "trim_audit": trim_audit,
            "catalog_generator": "tools/zbatch_modules/evidence_catalog.py",
            "catalog_generator_sha256": z68.sha256_file(ROOT / "tools/zbatch_modules/evidence_catalog.py"),
            "catalog_entry_count": len(first),
            "catalog_entries_sha256": z68.canonical_sha(first),
            "catalog_coverage": coverage,
            "generated_twice_identical": True,
            "draft_path": Path(spec["draft_path"]).relative_to(ROOT).as_posix(),
            "draft_sha256": spec["draft_sha256"],
            "draft_role": "candidate_silver_observation_only_not_request_input",
            "observation_denominator": spec["observation_denominator"],
        },
    }


def case_material(spec: Mapping[str, Any]) -> dict[str, Any]:
    if spec["kind"] == "crossbook":
        return _crossbook_material(spec)
    chapter = int(spec["unit"])
    text_path = _x01_chapter_path(chapter)
    catalog_path = V3_RUN_DIR / f"inputs/evidence_catalogs/ch{chapter:04d}.json"
    catalog = read_json(catalog_path)
    return {
        "text": text_path.read_text(encoding="utf-8"),
        "filename": text_path.name,
        "catalog": catalog,
        "receipt": {
            "case_key": spec["case_key"],
            "book": spec["book"],
            "inventory_unit": chapter,
            "source_kind": "exact_z79_formal_frozen_input",
            "frozen_body_sha256": z68.sha256_file(text_path),
            "catalog_file_sha256": z68.sha256_file(catalog_path),
            "catalog_entry_count": len(catalog["entries"]),
            "catalog_entries_sha256": z68.canonical_sha(catalog["entries"]),
            "catalog_coverage": catalog.get("coverage"),
        },
    }


def assert_request_uses_material(
    body: Mapping[str, Any], spec: Mapping[str, Any], material: Mapping[str, Any]
) -> None:
    """逐字确认模型请求中的正文和目录就是本案冻结件。"""

    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise ZBatchError(f"{spec['case_key']}请求消息结构漂移")
    user = str(messages[1].get("content", ""))
    expected_catalog = z68.compact_catalog(material["catalog"]["entries"])
    if (
        z68.extract_text_payload(user) != material["text"]
        or z68.extract_catalog_payload(user) != expected_catalog
        or f"当前章号：{int(spec['unit'])}" not in user
        or f"当前章文件名：{material['filename']}" not in user
    ):
        raise ZBatchError(f"{spec['case_key']}请求供料与冻结件不一致")


def _instantiate_crossbook_v3(spec: Mapping[str, Any], material: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    template = read_json(_v3_prepared_path(3))
    system = str(template["messages"][0]["content"])
    if system.count('"chapter": 3') != 1 or system.count("EV-C0003") != 2:
        raise ZBatchError("v3 system 第3章机械占位漂移")
    chapter = int(spec["unit"])
    system = system.replace('"chapter": 3', f'"chapter": {chapter}', 1)
    system = system.replace("EV-C0003", f"EV-C{chapter:04d}")

    user = str(template["messages"][1]["content"])
    user = z68._replace_once(user, z68.NAME_HINT_BLOCK, "", "第3章专属命名提示")
    user = z68._replace_once(user, "当前章号：3", f"当前章号：{chapter}", "当前章号")
    user = z68._replace_once(
        user,
        f"当前章文件名：{_x01_chapter_path(3).name}",
        f"当前章文件名：{material['filename']}",
        "当前章文件名",
    )
    user, old_text = z68.replace_text_payload(user, str(material["text"]))
    catalog_payload = z68.compact_catalog(material["catalog"]["entries"])
    user, old_catalog = z68.replace_catalog_payload(user, catalog_payload)

    body = copy.deepcopy(template)
    body["messages"] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if not user.endswith(z79.FINAL_REMINDER):
        raise ZBatchError(f"{spec['case_key']}跨书v3实例丢最终提醒")
    if z68.extract_text_payload(user) != material["text"] or z68.extract_catalog_payload(user) != catalog_payload:
        raise ZBatchError(f"{spec['case_key']}跨书v3实例化供料不一致")
    if any(marker in json.dumps(body["messages"], ensure_ascii=False) for marker in SCORE_ONLY_MARKERS_FORBIDDEN_IN_REQUEST):
        raise ZBatchError(f"{spec['case_key']}请求夹入B线底稿")
    return body, {
        "mode": "mechanical_crossbook_instantiation_from_same_v3_template",
        "template_request_sha256": V3_PREPARED_SHA256[3],
        "inventory_unit": chapter,
        "chapter_text_old_sha256": sha256_text(old_text),
        "chapter_text_new_sha256": sha256_text(str(material["text"])),
        "catalog_old_sha256": sha256_text(old_catalog),
        "catalog_new_sha256": sha256_text(catalog_payload),
        "chapter3_name_hint_removed": True,
        "sampling_unchanged": all(body[key] == template[key] for key in template if key != "messages"),
    }


def base_v3_body(spec: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if spec["kind"] == "x01":
        chapter = int(spec["unit"])
        path = _v3_prepared_path(chapter)
        _assert_file(path, V3_PREPARED_SHA256[chapter], f"X01第{chapter}章v3请求")
        return read_json(path), {
            "mode": "exact_z79_formal_v3_request",
            "request_sha256": V3_PREPARED_SHA256[chapter],
            "sampling_unchanged": True,
        }
    material = case_material(spec)
    return _instantiate_crossbook_v3(spec, material)


def layer_registry() -> dict[str, Any]:
    base = copy.deepcopy(_v3_package()["layer_registry"])
    rows = [
        {
            "repair_id": "source_claim_anchor_support",
            "addition_id": "EVIDENCE-05",
            "section": "【证据规则】",
            "item_number": "5",
            "unique_location": True,
            "model_visible_sha256": sha256_text(SOURCE_ANCHOR_RULE),
        },
        {
            "repair_id": "exclusion_items_preserved",
            "addition_id": "JUDGMENT-11",
            "section": "【判断规则】",
            "item_number": "11",
            "unique_location": True,
            "model_visible_sha256": sha256_text(EXCLUSION_RULE),
        },
        {
            "repair_id": "instruction_components_separated",
            "addition_id": "JUDGMENT-12",
            "section": "【判断规则】",
            "item_number": "12",
            "unique_location": True,
            "model_visible_sha256": sha256_text(INSTRUCTION_RULE),
        },
    ]
    if len(rows) != 3 or len({row["addition_id"] for row in rows}) != 3:
        raise ZBatchError("v4层位登记不是三处唯一新增")
    return {
        "schema_version": "z80-layer-registry-v1",
        "status": "pass_three_unique_additions",
        "base_v3_registry": base,
        "base_v3_registry_canonical_sha256": z68.canonical_sha(base),
        "v4_rows": rows,
        "other_sections_receive_v4_additions": False,
        "user_final_reminder_modified": False,
        "positive_examples_modified": False,
    }


def updated_deduplication_receipt() -> dict[str, Any]:
    base = copy.deepcopy(_v3_package()["deduplication"])
    if len(base.get("merged_duplicates") or []) != 6 or len(base.get("v3_unique_layer_additions") or []) != 4:
        raise ZBatchError("v3去重账结构漂移")
    result = copy.deepcopy(base)
    result["schema_version"] = "z80-system-deduplication-v4"
    result["base_v3_deduplication"] = {
        "canonical_sha256": z68.canonical_sha(base),
        "merged_duplicate_count": 6,
        "v3_unique_layer_addition_count": 4,
        "preserved_unchanged": True,
    }
    result["v4_unique_layer_additions"] = copy.deepcopy(layer_registry()["v4_rows"])
    result["v4_scope_distinctions"] = [
        {"addition_id": "EVIDENCE-05", "not_duplicate_of": "ANCHOR-SUPPORT-04", "reason": "前者专钉来源标记本身，后者管全部关键主张。"},
        {"addition_id": "JUDGMENT-11", "not_duplicate_of": "JUDGMENT-10", "reason": "前者禁止概括词吞排除对象，后者管问答结论与行动转向分立。"},
        {"addition_id": "JUDGMENT-12", "not_duplicate_of": None, "reason": "新增指令三组成分的独立真假边界。"},
    ]
    result["v4_duplicate_expression_elsewhere"] = False
    return result


def render_v4_system(spec: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    base, _ = base_v3_body(spec)
    old = str(base["messages"][0]["content"])
    judgment_anchor = z79.JUDGMENT_RULE + "\n\n【证据规则】"
    system = z79._replace_once(
        old,
        judgment_anchor,
        z79.JUDGMENT_RULE + "\n" + EXCLUSION_RULE + "\n" + INSTRUCTION_RULE + "\n\n【证据规则】",
        "v4判断规则11与12",
    )
    evidence_anchor = z79.ANCHOR_SUPPORT_RULE + "\n\n【静默检查】"
    system = z79._replace_once(
        system,
        evidence_anchor,
        z79.ANCHOR_SUPPORT_RULE + "\n" + SOURCE_ANCHOR_RULE + "\n\n【静默检查】",
        "v4证据规则5",
    )
    diff = z79._line_diff(old, system, old_name="v3_system", new_name="v4_system")
    added_nonblank = [line for line in diff["added_lines"] if line]
    restored = system.replace(
        z79.JUDGMENT_RULE + "\n" + EXCLUSION_RULE + "\n" + INSTRUCTION_RULE,
        z79.JUDGMENT_RULE,
        1,
    ).replace(
        z79.ANCHOR_SUPPORT_RULE + "\n" + SOURCE_ANCHOR_RULE,
        z79.ANCHOR_SUPPORT_RULE,
        1,
    )
    leaked = [token for token in CASE_TOKENS_FORBIDDEN_IN_ADDITIONS if token in "\n".join(V4_ADDITIONS_IN_SYSTEM_ORDER)]
    if (
        diff["removed_lines"]
        or added_nonblank != list(V4_ADDITIONS_IN_SYSTEM_ORDER)
        or restored != old
        or any(system.count(rule) != 1 for rule in V4_ADDITIONS_IN_SYSTEM_ORDER)
        or leaked
    ):
        raise ZBatchError(f"{spec['case_key']} v3→v4不等于三处唯一新增")
    return system, {
        "case_key": spec["case_key"],
        "base_v3_system_sha256": sha256_text(old),
        "v4_system_sha256": sha256_text(system),
        "line_diff": diff,
        "added_nonblank_lines": added_nonblank,
        "round_trip_to_v3_equal": True,
        "new_rule_occurrence_counts": {rule: system.count(rule) for rule in V4_ADDITIONS_IN_SYSTEM_ORDER},
        "case_tokens_absent": True,
    }


def build_candidate_body(spec: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    base, instantiation = base_v3_body(spec)
    system, system_meta = render_v4_system(spec)
    candidate = copy.deepcopy(base)
    candidate["messages"][0]["content"] = system
    changed = z70.deep_diff_paths(base, candidate)
    if changed != ["$.messages[0].content"]:
        raise ZBatchError(f"{spec['case_key']} v4夹入system三行外变化：{changed}")
    if candidate["messages"][1] != base["messages"][1]:
        raise ZBatchError(f"{spec['case_key']} v4改动了user")
    if any(marker in json.dumps(candidate["messages"], ensure_ascii=False) for marker in SCORE_ONLY_MARKERS_FORBIDDEN_IN_REQUEST):
        raise ZBatchError(f"{spec['case_key']} v4请求夹入B线底稿")
    if z68.request_has_prohibited_input(candidate):
        raise ZBatchError(f"{spec['case_key']} v4请求夹入禁入材料")
    return candidate, {
        "schema_version": "z80-request-diff-v1",
        "case_key": spec["case_key"],
        "group": spec["group"],
        "book_id": spec["book_id"],
        "inventory_unit": spec["unit"],
        "base_v3_instantiation": instantiation,
        "changed_paths": changed,
        "system": system_meta,
        "user_unchanged": True,
        "user_sha256": sha256_text(str(candidate["messages"][1]["content"])),
        "positive_examples_unchanged": True,
        "sampling_and_transport_unchanged": all(candidate[key] == base[key] for key in base if key != "messages"),
        "v3_canonical_sha256": z68.canonical_sha(base),
        "v4_canonical_sha256": z68.canonical_sha(candidate),
    }


def selection_receipt() -> dict[str, Any]:
    rows = []
    for spec in CASE_SPECS:
        if spec["kind"] != "crossbook":
            continue
        material = case_material(spec)
        rows.append(
            {
                "group": spec["group"],
                "case_key": spec["case_key"],
                "book": spec["book"],
                "inventory_unit": spec["unit"],
                "selection_reason": spec["selection_reason"],
                "frozen_material": material["receipt"],
            }
        )
    return {
        "schema_version": "z80-crossbook-selection-v1",
        "status": "selected_before_api_calls",
        "rule": "优先有B线同章底稿且与X01题材差异大的两本，每本一单元。",
        "selected": rows,
        "other_three_books_not_sampled": ["大王饶命", "神秘复苏", "无限恐怖"],
        "b_line_truth_boundary": "候选银标，只作结果侧观察列，不作硬闸，不进入请求。",
    }


def v3_to_v4_diff_receipt() -> dict[str, Any]:
    rows = []
    for spec in CASE_SPECS:
        _, diff = build_candidate_body(spec)
        rows.append(
            {
                "case_key": spec["case_key"],
                "group": spec["group"],
                "base_mode": diff["base_v3_instantiation"]["mode"],
                "changed_paths": diff["changed_paths"],
                "system_added_lines": diff["system"]["line_diff"]["added_lines"],
                "system_removed_lines": diff["system"]["line_diff"]["removed_lines"],
                "round_trip_to_v3_equal": diff["system"]["round_trip_to_v3_equal"],
                "user_unchanged": diff["user_unchanged"],
                "sampling_and_transport_unchanged": diff["sampling_and_transport_unchanged"],
                "v3_canonical_sha256": diff["v3_canonical_sha256"],
                "v4_canonical_sha256": diff["v4_canonical_sha256"],
            }
        )
    return {
        "schema_version": "z80-v3-to-v4-diff-v1",
        "status": "pass_exactly_three_unique_system_additions",
        "base_v3_package_sha256": V3_PACKAGE_SHA256,
        "model_visible_additions": list(V4_ADDITIONS_IN_SYSTEM_ORDER),
        "addition_count": 3,
        "rows": rows,
        "no_fourth_prompt_change": True,
    }


def build_package() -> dict[str, Any]:
    systems = {}
    for spec in CASE_SPECS:
        system, meta = render_v4_system(spec)
        systems[spec["case_key"]] = {"content": system, "meta": meta}
    return {
        "schema_version": "z80-fact-sheet-injection-package-v4",
        "status": "candidate_silver_only",
        "base_v3_package": {"path": V3_PACKAGE.as_posix(), "sha256": V3_PACKAGE_SHA256, "preserved_read_only": True},
        "systems": systems,
        "user_final_reminder": z79.FINAL_REMINDER,
        "user_final_reminder_sha256": sha256_text(z79.FINAL_REMINDER),
        "user_final_reminder_equals_v3": True,
        "positive_examples_equals_v3": True,
        "targeted_retry_system": z79.RETRY_SYSTEM,
        "targeted_retry_system_sha256": sha256_text(z79.RETRY_SYSTEM),
        "targeted_retry_equals_v3": True,
        "targeted_retry_policy": {
            "eligible": ["event超过100个非空字符", "anchor_id格式非法或不在当前冻结目录"],
            "per_event_limit": MAX_TARGETED_RETRIES_PER_EVENT,
            "per_chapter_limit": MAX_TARGETED_RETRIES_PER_CHAPTER,
            "per_group_limit": MAX_TARGETED_RETRIES_PER_GROUP,
            "semantic_failures": "hard_stop_no_retry",
        },
        "layer_registry": layer_registry(),
        "deduplication": updated_deduplication_receipt(),
        "selection": selection_receipt(),
        "v3_to_v4_diff": v3_to_v4_diff_receipt(),
    }


def build_run_contract(path: Path) -> dict[str, Any]:
    _assert_file(V3_CONTRACT, V3_CONTRACT_SHA256, "第79道运输合同")
    raw = read_json(V3_CONTRACT)
    source_profile = copy.deepcopy(raw["profiles"][z79.PROFILE])
    raw["contract_version"] = "z80-fact-sheet-v4-transport-v1"
    raw["profiles"][PROFILE] = source_profile
    raw["profiles"][PROFILE]["note"] = "第80道三组隔离投影；运输与定点重试参数逐字段沿用第79道。"
    write_json(path, raw)
    return raw


def load_bundle(run_dir: Path) -> stage_sampling.StageContractBundle:
    return stage_sampling.load_contract_bundle(run_dir / RUN_LOCAL_CONTRACT, profile=PROFILE)


def assert_body_matches_contract(body: Mapping[str, Any], run_dir: Path) -> None:
    bundle = load_bundle(run_dir)
    rebuilt = api_transport.build_request_body(
        model=str(bundle.route["model"]),
        messages=copy.deepcopy(body["messages"]),
        contract=bundle.stage("neutral_extract"),
    )
    if rebuilt != body:
        raise ZBatchError("第80道请求不能由第79道同参运输合同逐字段复现")


def _input_paths(run_dir: Path, case_key: str) -> tuple[Path, Path]:
    base = run_dir / "inputs" / case_key
    return base / "chapter.txt", base / "evidence_catalog.json"


def _prepared_path(run_dir: Path, case_key: str) -> Path:
    return run_dir / "prepared_requests" / f"{case_key}.json"


def _base_request_path(run_dir: Path, case_key: str) -> Path:
    return run_dir / "v3_same_material_requests" / f"{case_key}.json"


def call_artifacts_present(run_dir: Path) -> list[str]:
    hits: list[str] = []
    for group in GROUP_ORDER:
        group_dir = run_dir / "groups" / group
        for relative in (
            "run_claim.json",
            "call_attempts.jsonl",
            "usage.jsonl",
            "requests",
            "responses",
            "01_extract",
            "hard_stop.json",
        ):
            path = group_dir / relative
            if path.exists():
                hits.append(path.relative_to(run_dir).as_posix())
    return hits


def assert_safe_run_dir(run_dir: Path, *, allow_test_run_dir: bool = False) -> None:
    """仓内只准写进 runs/Z80_*，在 mkdir 前阻断误写保护树。"""

    if allow_test_run_dir:
        return
    resolved = run_dir.resolve(strict=False)
    runs_root = (ROOT / "runs").resolve()
    if resolved.parent != runs_root or not resolved.name.startswith("Z80_"):
        raise ZBatchError(f"第80道运行目录越出 runs/Z80_* 白名单，写入前拒绝：{run_dir}")


def score_only_expected() -> tuple[tuple[Path, str, str], ...]:
    return (
        (V3_ADJUDICATION, V3_ADJUDICATION_SHA256, "X01_第79道语义人工复核源.json"),
        (V3_SCORECARD, V3_SCORECARD_SHA256, "X01_第79道成绩与验收总表.json"),
        (ZHIHU_DRAFT, case_spec("Z74B-B01-U0033")["draft_sha256"], ZHIHU_DRAFT.name),
        (FANREN_DRAFT, case_spec("Z74B-B05-U0030")["draft_sha256"], FANREN_DRAFT.name),
    )


def prepare(run_dir: Path = DEFAULT_RUN_DIR, *, allow_test_run_dir: bool = False) -> dict[str, Any]:
    assert_safe_run_dir(run_dir, allow_test_run_dir=allow_test_run_dir)
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    protected = assert_protected()
    run_dir.mkdir(parents=True)
    build_run_contract(run_dir / RUN_LOCAL_CONTRACT)
    package = build_package()
    write_json(run_dir / "prompt_candidates/事实说明书注入包_v4.json", package)
    write_json(run_dir / "prompt_candidates/v3至v4逐行差异账.json", package["v3_to_v4_diff"])
    write_json(run_dir / "prompt_candidates/v4层位登记表.json", package["layer_registry"])
    write_json(run_dir / "prompt_candidates/去重与唯一落点账_v4.json", package["deduplication"])
    write_json(run_dir / "crossbook_selection.json", package["selection"])

    rows = []
    for spec in CASE_SPECS:
        material = case_material(spec)
        base, _ = base_v3_body(spec)
        candidate, diff = build_candidate_body(spec)
        assert_request_uses_material(base, spec, material)
        assert_request_uses_material(candidate, spec, material)
        assert_body_matches_contract(candidate, run_dir)
        text_path, catalog_path = _input_paths(run_dir, spec["case_key"])
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(material["text"], encoding="utf-8")
        write_json(catalog_path, material["catalog"])
        write_json(_base_request_path(run_dir, spec["case_key"]), base)
        write_json(_prepared_path(run_dir, spec["case_key"]), candidate)
        write_json(run_dir / "request_diffs" / f"{spec['case_key']}.json", diff)
        system_path = run_dir / "prompt_candidates/systems" / f"{spec['case_key']}.txt"
        system_path.parent.mkdir(parents=True, exist_ok=True)
        system_path.write_text(candidate["messages"][0]["content"], encoding="utf-8")
        group_dir = run_dir / "groups" / spec["group"]
        group_dir.mkdir(parents=True, exist_ok=True)
        rows.append(
            {
                "case_key": spec["case_key"],
                "group": spec["group"],
                "book": spec["book"],
                "inventory_unit": spec["unit"],
                "input_text_sha256": z68.sha256_file(text_path),
                "catalog_file_sha256": z68.sha256_file(catalog_path),
                "base_v3_request_sha256": z68.sha256_file(_base_request_path(run_dir, spec["case_key"])),
                "prepared_v4_request_sha256": z68.sha256_file(_prepared_path(run_dir, spec["case_key"])),
                "request_diff_sha256": z68.sha256_file(run_dir / "request_diffs" / f"{spec['case_key']}.json"),
                "system_prompt_sha256": z68.sha256_file(system_path),
            }
        )

    score_only = run_dir / "provenance/score_only"
    score_only.mkdir(parents=True, exist_ok=True)
    for source, expected, name in score_only_expected():
        _assert_file(source, expected, "结果侧只读评分底料")
        shutil.copyfile(source, score_only / name)

    preflight = {
        "schema_version": "z80-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": z68.now_iso(),
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "network_attempts": 0,
        "group_order": list(GROUP_ORDER),
        "group_prerequisites": {key: list(value) for key, value in GROUP_PREREQUISITES.items()},
        "sampling": {
            "model": "deepseek-v4-flash",
            "temperature": 0.2,
            "max_tokens": MAX_TOKENS,
            "n": 1,
            "reasoning_effort": "medium",
            "response_format": {"type": "json_object"},
        },
        "protected_before": protected,
        "package": {
            "path": "prompt_candidates/事实说明书注入包_v4.json",
            "sha256": z68.sha256_file(run_dir / "prompt_candidates/事实说明书注入包_v4.json"),
        },
        "producer": {"path": Path(__file__).relative_to(ROOT).as_posix(), "sha256": z68.sha256_file(Path(__file__))},
        "rows": rows,
    }
    write_json(run_dir / "preflight.json", preflight)
    write_json(
        run_dir / "run_manifest.json",
        {"schema_version": "z80-master-run-manifest-v1", "run_id": run_dir.name, "status": "prepared", "groups": {group: "not_started" for group in GROUP_ORDER}},
    )
    verify_prepared(run_dir, require_zero_call=True, allow_test_run_dir=allow_test_run_dir)
    return preflight


def verify_prepared(
    run_dir: Path, *, require_zero_call: bool, allow_test_run_dir: bool = False
) -> dict[str, Any]:
    assert_safe_run_dir(run_dir, allow_test_run_dir=allow_test_run_dir)
    preflight = read_json(run_dir / "preflight.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("第80道预演状态漂移")
    if preflight.get("model_api_calls") != 0 or preflight.get("network_attempts") != 0:
        raise ZBatchError("第80道预演调用账不为0")
    if require_zero_call and call_artifacts_present(run_dir):
        raise ZBatchError("第80道目录不是零调用准备态")
    if assert_protected() != preflight["protected_before"]:
        raise ZBatchError("第80道保护件在准备后漂移")
    if z68.sha256_file(Path(__file__)) != preflight["producer"]["sha256"]:
        raise ZBatchError("第80道运行器在准备后漂移")
    score_only = run_dir / "provenance/score_only"
    for _, expected, name in score_only_expected():
        _assert_file(score_only / name, expected, f"第80道结果侧评分副本{name}")
    package_path = run_dir / preflight["package"]["path"]
    if read_json(package_path) != build_package():
        raise ZBatchError("第80道 v4 包不能机械重建")
    checks = []
    for spec in CASE_SPECS:
        expected_base, _ = base_v3_body(spec)
        expected_v4, diff = build_candidate_body(spec)
        actual_base = read_json(_base_request_path(run_dir, spec["case_key"]))
        actual_v4 = read_json(_prepared_path(run_dir, spec["case_key"]))
        text_path, catalog_path = _input_paths(run_dir, spec["case_key"])
        material = case_material(spec)
        assert_body_matches_contract(actual_v4, run_dir)
        assert_request_uses_material(actual_base, spec, material)
        assert_request_uses_material(actual_v4, spec, material)
        passed = (
            actual_base == expected_base
            and actual_v4 == expected_v4
            and text_path.read_text(encoding="utf-8") == material["text"]
            and read_json(catalog_path) == material["catalog"]
            and diff["changed_paths"] == ["$.messages[0].content"]
            and diff["system"]["line_diff"]["removed_lines"] == []
            and diff["system"]["added_nonblank_lines"] == list(V4_ADDITIONS_IN_SYSTEM_ORDER)
            and diff["system"]["round_trip_to_v3_equal"]
            and diff["user_unchanged"]
            and diff["sampling_and_transport_unchanged"]
        )
        if not passed:
            raise ZBatchError(f"{spec['case_key']}零调用准备件不能机械重建")
        checks.append({"case_key": spec["case_key"], "passed": True})
    receipt = {
        "schema_version": "z80-prepared-verification-v1",
        "status": "pass",
        "require_zero_call": require_zero_call,
        "checks": checks,
        "protected_unchanged": True,
        "package_rebuilt_equal": True,
        "exactly_three_system_additions": True,
        "crossbook_catalogs_generated_twice_identical": True,
    }
    write_json(run_dir / "prepared_request_verification.json", receipt)
    return receipt


def _group_dir(run_dir: Path, group: str) -> Path:
    return run_dir / "groups" / group


def _case_id(spec: Mapping[str, Any]) -> str:
    return "z80_" + str(spec["case_key"]).lower().replace("-", "_")


def _require_previous_groups(
    run_dir: Path, group: str, *, allow_test_run_dir: bool = False
) -> None:
    for previous in GROUP_PREREQUISITES[group]:
        decision_path = run_dir / "group_decisions" / f"{previous}.json"
        manifest_path = _group_dir(run_dir, previous) / "run_manifest.json"
        mechanical_path = _group_dir(run_dir, previous) / "mechanical_verification.json"
        if not decision_path.is_file() or not manifest_path.is_file() or not mechanical_path.is_file():
            raise ZBatchError(f"{group}未获{previous}完整放行票")
        verify_group(run_dir, previous, allow_test_run_dir=allow_test_run_dir)
        decision = read_json(decision_path)
        manifest = read_json(manifest_path)
        mechanical = read_json(mechanical_path)
        expected_cases = [str(row["case_key"]) for row in cases_for_group(previous)]
        adjudication_ref = decision.get("semantic_adjudication")
        source_artifacts = decision.get("source_artifacts")
        semantic_gates = decision.get("semantic_gates")
        event_output_sha256 = decision.get("event_output_sha256")
        if (
            not isinstance(adjudication_ref, dict)
            or not isinstance(source_artifacts, dict)
            or not isinstance(semantic_gates, dict)
            or not isinstance(event_output_sha256, dict)
        ):
            raise ZBatchError(f"{group}前置{previous}语义放行票结构不完整")
        adjudication_path = _group_dir(run_dir, previous) / "adjudications/semantic_adjudication.json"
        expected_adjudication_relative = adjudication_path.relative_to(run_dir).as_posix()
        metrics_path = _group_dir(run_dir, previous) / "01_extract/metrics.json"
        claim_path = _group_dir(run_dir, previous) / "run_claim.json"
        if not adjudication_path.is_file() or not metrics_path.is_file() or not claim_path.is_file():
            raise ZBatchError(f"{group}前置{previous}缺语义判词或调用账")
        adjudication = read_json(adjudication_path)
        metrics = read_json(metrics_path)
        claim = read_json(claim_path)
        required_gate_keys = SEMANTIC_GATE_KEYS[previous]
        expected_event_output_sha256 = {
            case_key: z68.sha256_file(_group_dir(run_dir, previous) / f"01_extract/events/{case_key}.json")
            for case_key in expected_cases
        }
        checks = mechanical.get("checks")
        expected_retry_count = manifest.get("targeted_retry_count")
        call_attempts = z68.read_jsonl(_group_dir(run_dir, previous) / "call_attempts.jsonl")
        usage = z68.read_jsonl(_group_dir(run_dir, previous) / "usage.jsonl")
        if (
            decision.get("schema_version") != "z80-group-semantic-decision-v1"
            or decision.get("run_id") != read_json(run_dir / "preflight.json")["run_id"]
            or decision.get("group") != previous
            or decision.get("status") != "pass_all_required_gates"
            or decision.get("all_pass") is not True
            or decision.get("hard_stop") is True
            or decision.get("reviewed_case_keys") != expected_cases
            or set(semantic_gates) != set(required_gate_keys)
            or not all(semantic_gates[key] is True for key in required_gate_keys)
            or adjudication_ref.get("path") != expected_adjudication_relative
            or adjudication_ref.get("sha256") != z68.sha256_file(adjudication_path)
            or event_output_sha256 != expected_event_output_sha256
            or source_artifacts.get("run_manifest_sha256") != z68.sha256_file(manifest_path)
            or source_artifacts.get("mechanical_verification_sha256") != z68.sha256_file(mechanical_path)
            or source_artifacts.get("metrics_sha256") != z68.sha256_file(metrics_path)
            or adjudication.get("schema_version") != "z80-group-semantic-adjudication-v1"
            or adjudication.get("run_id") != read_json(run_dir / "preflight.json")["run_id"]
            or adjudication.get("group") != previous
            or adjudication.get("status") != "pass"
            or adjudication.get("reviewed_case_keys") != expected_cases
            or adjudication.get("all_output_events_reviewed") is not True
            or adjudication.get("semantic_anchor_invalid_count") != 0
            or adjudication.get("semantic_gates") != semantic_gates
            or adjudication.get("event_output_sha256") != expected_event_output_sha256
            or manifest.get("schema_version") != "z80-group-run-manifest-v1"
            or manifest.get("status") != "completed_candidate_silver_only"
            or manifest.get("group") != previous
            or manifest.get("completed_cases") != expected_cases
            or manifest.get("run_claim") != claim
            or claim.get("schema_version") != "z80-group-run-claim-v1"
            or claim.get("status") != "claimed_do_not_resume"
            or not isinstance(manifest.get("network_attempts"), int)
            or manifest.get("network_attempts") < 0
            or not isinstance(expected_retry_count, int)
            or expected_retry_count < 0
            or expected_retry_count > MAX_TARGETED_RETRIES_PER_GROUP
            or manifest.get("network_attempts") != len(call_attempts)
            or mechanical.get("schema_version") != "z80-group-mechanical-verification-v1"
            or mechanical.get("status") != "pass"
            or mechanical.get("group") != previous
            or not isinstance(checks, list)
            or [row.get("case_key") for row in checks if isinstance(row, dict)] != expected_cases
            or any(
                not isinstance(row, dict)
                or row.get("actual_equals_prepared") is not True
                or row.get("program_audit_pass") is not True
                or row.get("materialized_events_match") is not True
                or row.get("outside_catalog_anchor_count") != 0
                or row.get("overlength_event_count") != 0
                or not isinstance(row.get("event_count"), int)
                or row.get("event_count") <= 0
                for row in checks
            )
            or mechanical.get("gates")
            != {
                "outside_catalog_anchor_zero": True,
                "length_rejection_zero": True,
                "whole_chapter_invalidation_zero": True,
            }
            or mechanical.get("targeted_retry_count") != expected_retry_count
            or not isinstance(mechanical.get("secret_scan"), dict)
            or mechanical["secret_scan"].get("passed") is not True
            or mechanical.get("protected_unchanged") is not True
            or metrics.get("schema_version") != "z80-group-run-metrics-v1"
            or metrics.get("status") != "completed_candidate_silver_only"
            or metrics.get("group") != previous
            or metrics.get("cases_completed") != expected_cases
            or metrics.get("main_logical_calls") != len(expected_cases)
            or metrics.get("targeted_retry_logical_calls") != expected_retry_count
            or not isinstance(metrics.get("successful_responses"), int)
            or metrics.get("successful_responses") != len(usage)
            or metrics.get("successful_responses") != len(expected_cases) + expected_retry_count
            or not isinstance(metrics.get("network_attempts"), int)
            or metrics.get("network_attempts") != len(call_attempts)
            or metrics.get("network_attempts") != manifest.get("network_attempts")
            or metrics.get("network_attempts") < metrics.get("successful_responses")
            or not isinstance(metrics.get("usage_totals"), dict)
            or not isinstance(metrics.get("targeted_retry_ledger"), list)
            or len(metrics["targeted_retry_ledger"]) != expected_retry_count
        ):
            raise ZBatchError(f"{group}前置{previous}没有全闸通过")


def _acquire_claim(group_dir: Path) -> dict[str, Any]:
    claim_path = group_dir / "run_claim.json"
    claim = {"schema_version": "z80-group-run-claim-v1", "status": "claimed_do_not_resume", "claimed_at": z68.now_iso(), "pid": os.getpid()}
    try:
        descriptor = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ZBatchError("第80道该组已经开跑或曾中断，拒绝重复采样") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(claim, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def _acquire_retry(
    *,
    transport: api_transport.ApiTransport,
    group_dir: Path,
    spec: Mapping[str, Any],
    row: Mapping[str, Any],
    catalog: list[dict[str, Any]],
    chapter_text: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_id = f"{_case_id(spec)}_{str(row['event_id']).lower()}"
    messages = z77.build_retry_messages(
        chapter=int(spec["unit"]),
        original_event=row["original_event"],
        violations=list(row["violations"]),
        chapter_text=chapter_text,
        catalog=catalog,
    )
    result = transport.call(stage="targeted_retry", case_id=case_id, messages=messages)
    if result.finish_reason != "stop" or not result.content.strip():
        raise ZBatchError(f"{spec['case_key']} {row['event_id']} 定点重试未stop或正文为空")
    parsed = candidate_envelope.parse_json_content(result.content)
    allow_multiple = any(value.startswith("event_nonspace_chars=") for value in row["violations"])
    replacements = z77.validate_replacements(parsed, catalog=catalog, allow_multiple=allow_multiple)
    receipt = {
        "case_key": spec["case_key"],
        "original_event_id": row["event_id"],
        "violations": list(row["violations"]),
        "attempt": 1,
        "replacement_count": len(replacements),
        "original_event": row["original_event"],
        "replacement_events": replacements,
        "request_sha256": z68.sha256_file(group_dir / f"requests/targeted_retry/{case_id}_request.json"),
        "raw_response_sha256": z68.sha256_file(group_dir / f"responses/targeted_retry/{case_id}_raw.json"),
    }
    return replacements, receipt


def run_group(run_dir: Path, group: str) -> dict[str, Any]:
    verify_prepared(run_dir, require_zero_call=False)
    _require_previous_groups(run_dir, group)
    specs = cases_for_group(group)
    group_dir = _group_dir(run_dir, group)
    if any((group_dir / name).exists() for name in ("run_claim.json", "call_attempts.jsonl", "usage.jsonl", "hard_stop.json")):
        raise ZBatchError(f"{group}已存在调用痕迹，拒绝重跑")
    preflight = read_json(run_dir / "preflight.json")
    claim = _acquire_claim(group_dir)
    write_json_atomic(group_dir / "run_manifest.json", {"schema_version": "z80-group-run-manifest-v1", "group": group, "status": "running_do_not_resume", "run_claim": claim})
    completed: list[str] = []
    retry_total = 0
    retry_ledger: list[dict[str, Any]] = []
    try:
        transport = api_transport.ApiTransport.from_bundle(load_bundle(run_dir), run_dir=group_dir, max_calls=MAX_NETWORK_ATTEMPTS)
        for spec in specs:
            prepared = read_json(_prepared_path(run_dir, spec["case_key"]))
            assert_body_matches_contract(prepared, run_dir)
            case_id = _case_id(spec)
            result = transport.call(stage="neutral_extract", case_id=case_id, messages=prepared["messages"])
            actual = read_json(group_dir / f"requests/neutral_extract/{case_id}_request.json")
            if actual.get("body") != prepared or result.request_record.get("body") != prepared:
                raise ZBatchError(f"{spec['case_key']}实际请求不等于prepared")
            if result.finish_reason != "stop" or not result.content.strip():
                raise ZBatchError(f"{spec['case_key']}主回包未stop或正文为空")
            model_json = candidate_envelope.parse_json_content(result.content)
            write_json(group_dir / f"01_extract/model_json_original/{spec['case_key']}.json", model_json)
            text_path, catalog_path = _input_paths(run_dir, spec["case_key"])
            catalog = read_json(catalog_path)["entries"]
            analysis = z77.analyze_main_response(model_json, chapter=int(spec["unit"]), catalog=catalog)
            write_json(group_dir / f"01_extract/initial_audits/{spec['case_key']}.json", analysis)
            if analysis["hard_reasons"]:
                raise ZBatchError(f"{spec['case_key']}出现非授权失败面：{analysis['hard_reasons']}")
            eligible = analysis["eligible"]
            if len(eligible) > MAX_TARGETED_RETRIES_PER_CHAPTER or retry_total + len(eligible) > MAX_TARGETED_RETRIES_PER_GROUP:
                raise ZBatchError(f"{spec['case_key']}定点重试数量超过上限")
            replacements: dict[int, list[dict[str, Any]]] = {}
            for row in eligible:
                fixed, receipt = _acquire_retry(
                    transport=transport,
                    group_dir=group_dir,
                    spec=spec,
                    row=row,
                    catalog=catalog,
                    chapter_text=text_path.read_text(encoding="utf-8"),
                )
                replacements[int(row["index"])] = fixed
                retry_total += 1
                retry_ledger.append(receipt)
                append_jsonl(group_dir / "targeted_retry_ledger.jsonl", receipt)
            final_json = z77.apply_replacements(model_json, chapter=int(spec["unit"]), replacements=replacements)
            materialized, audit = neutral_extract.process_model_data(final_json, chapter=int(spec["unit"]), catalog=catalog)
            write_json(group_dir / f"01_extract/model_json/{spec['case_key']}.json", final_json)
            write_json(group_dir / f"01_extract/events/{spec['case_key']}.json", materialized)
            write_json(group_dir / f"01_extract/program_audits/{spec['case_key']}.json", audit)
            completed.append(str(spec["case_key"]))
    except BaseException as exc:
        attempts = z68.read_jsonl(group_dir / "call_attempts.jsonl")
        hard_stop = {
            "schema_version": "z80-group-hard-stop-v1",
            "status": "hard_stop_no_unapproved_repair",
            "at": z68.now_iso(),
            "group": group,
            "completed_cases": completed,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "targeted_retry_count": retry_total,
            "network_attempts": len(attempts),
            "protected_unchanged": assert_protected() == preflight["protected_before"],
        }
        write_json(group_dir / "hard_stop.json", hard_stop)
        write_json_atomic(group_dir / "run_manifest.json", {"schema_version": "z80-group-run-manifest-v1", "group": group, "status": "hard_stop", "completed_cases": completed, "run_claim": claim, "network_attempts": len(attempts), "targeted_retry_count": retry_total})
        raise
    attempts = z68.read_jsonl(group_dir / "call_attempts.jsonl")
    usage = z68.read_jsonl(group_dir / "usage.jsonl")
    totals: Counter[str] = Counter()
    for row in usage:
        for key, value in (row.get("usage") or {}).items():
            if isinstance(value, int):
                totals[key] += value
    metrics = {
        "schema_version": "z80-group-run-metrics-v1",
        "status": "completed_candidate_silver_only",
        "group": group,
        "cases_completed": completed,
        "main_logical_calls": len(specs),
        "targeted_retry_logical_calls": retry_total,
        "successful_responses": len(usage),
        "network_attempts": len(attempts),
        "usage_totals": dict(totals),
        "targeted_retry_ledger": retry_ledger,
    }
    write_json(group_dir / "01_extract/metrics.json", metrics)
    write_json_atomic(group_dir / "run_manifest.json", {"schema_version": "z80-group-run-manifest-v1", "group": group, "status": "completed_candidate_silver_only", "completed_cases": completed, "run_claim": claim, "network_attempts": len(attempts), "targeted_retry_count": retry_total})
    return metrics


def verify_group(
    run_dir: Path, group: str, *, allow_test_run_dir: bool = False
) -> dict[str, Any]:
    verify_prepared(
        run_dir, require_zero_call=False, allow_test_run_dir=allow_test_run_dir
    )
    group_dir = _group_dir(run_dir, group)
    manifest = read_json(group_dir / "run_manifest.json")
    if manifest.get("status") != "completed_candidate_silver_only":
        raise ZBatchError(f"{group}尚未完成：{manifest.get('status')}")
    checks = []
    outside_total = 0
    overlength_total = 0
    invalidations = 0
    for spec in cases_for_group(group):
        case_id = _case_id(spec)
        prepared = read_json(_prepared_path(run_dir, spec["case_key"]))
        actual = read_json(group_dir / f"requests/neutral_extract/{case_id}_request.json")["body"]
        final_json = read_json(group_dir / f"01_extract/model_json/{spec['case_key']}.json")
        stored_events = read_json(group_dir / f"01_extract/events/{spec['case_key']}.json")
        audit = read_json(group_dir / f"01_extract/program_audits/{spec['case_key']}.json")
        _, catalog_path = _input_paths(run_dir, spec["case_key"])
        catalog = read_json(catalog_path)["entries"]
        reasons, rebuilt = neutral_extract.audit_event_envelope(final_json, int(spec["unit"]), catalog)
        rebuilt_events = neutral_extract.materialize_events(final_json, catalog, int(spec["unit"]))
        materialized_events_match = stored_events == rebuilt_events
        outside = len(rebuilt.get("missing_catalog_anchor_ids") or [])
        overlength = sum(1 for event in final_json["events"] if nonspace_chars(str(event["event"])) > MAX_EVENT_NONSPACE_CHARS)
        invalidated = bool(
            reasons
            or audit != rebuilt
            or audit.get("status") != "pass"
            or not materialized_events_match
        )
        outside_total += outside
        overlength_total += overlength
        invalidations += int(invalidated)
        checks.append(
            {
                "case_key": spec["case_key"],
                "actual_equals_prepared": actual == prepared,
                "program_audit_pass": not invalidated,
                "materialized_events_match": materialized_events_match,
                "outside_catalog_anchor_count": outside,
                "overlength_event_count": overlength,
                "event_count": len(final_json["events"]),
            }
        )
    scan = z77.secret_scan(group_dir)
    preflight = read_json(run_dir / "preflight.json")
    protected_unchanged = assert_protected() == preflight["protected_before"]
    passed = (
        all(
            row["actual_equals_prepared"]
            and row["program_audit_pass"]
            and row["materialized_events_match"]
            for row in checks
        )
        and outside_total == 0
        and overlength_total == 0
        and invalidations == 0
        and scan["passed"]
        and protected_unchanged
    )
    receipt = {
        "schema_version": "z80-group-mechanical-verification-v1",
        "status": "pass" if passed else "fail",
        "group": group,
        "checks": checks,
        "gates": {
            "outside_catalog_anchor_zero": outside_total == 0,
            "length_rejection_zero": overlength_total == 0,
            "whole_chapter_invalidation_zero": invalidations == 0,
        },
        "targeted_retry_count": read_json(group_dir / "01_extract/metrics.json")["targeted_retry_logical_calls"],
        "secret_scan": scan,
        "protected_unchanged": protected_unchanged,
    }
    write_json(group_dir / "mechanical_verification.json", receipt)
    if not passed:
        raise ZBatchError(f"{group}机械复验失败")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify-prepared", "run-group", "verify-group", "show-package"))
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--group", choices=GROUP_ORDER)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if args.action == "show-package":
        print(json.dumps(build_package(), ensure_ascii=False, indent=2))
        return 0
    if args.action in {"run-group", "verify-group"} and args.group is None:
        parser.error(f"{args.action} 必须提供 --group")
    if args.action == "prepare":
        result = prepare(run_dir)
    elif args.action == "verify-prepared":
        result = verify_prepared(run_dir, require_zero_call=not bool(call_artifacts_present(run_dir)))
    elif args.action == "run-group":
        result = run_group(run_dir, str(args.group))
    else:
        result = verify_group(run_dir, str(args.group))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

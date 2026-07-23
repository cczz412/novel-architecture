#!/usr/bin/env python3
"""第79道：事实说明书注入包 v3 定点修复与三章隔离复验。

v3 只在第77道 v2 模型可见文本上增加两组修复：锚挂全纪律，以及
问答结论与行动转向单列。主采样仍只跑第3、13、19章各一次；定点重试
合同、运输参数和失败处置全部沿用 v2。本工具不改现役默认链或正式件。
"""

from __future__ import annotations

import argparse
import copy
import difflib
import functools
import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import z68_revised_request_pilot as z68
import z70_compression_contract_pilot as z70
import z74a_rewrite_examples as z74a
import z77_fact_sheet_v2_pilot as z77
from zbatch_modules import api_transport, candidate_envelope, neutral_extract, stage_sampling
from zbatch_modules.evidence_catalog import nonspace_chars
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
TARGET_CHAPTERS = z77.TARGET_CHAPTERS
RUN_ID = "Z79_X01_事实说明书注入包v3_三章复验_v1.0_20260721"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_ID
RUN_CLAIM = Path("run_claim.json")
RUN_LOCAL_CONTRACT = Path("provenance/sensenova_stage_sampling_z79_v1.json")
PROFILE = "z79_fact_sheet_v3_32k_v1"

MAX_TOKENS = z77.MAX_TOKENS
RETRY_MAX_TOKENS = z77.RETRY_MAX_TOKENS
MAX_EVENT_NONSPACE_CHARS = z77.MAX_EVENT_NONSPACE_CHARS
MAX_TARGETED_RETRIES_PER_EVENT = z77.MAX_TARGETED_RETRIES_PER_EVENT
MAX_TARGETED_RETRIES_PER_CHAPTER = z77.MAX_TARGETED_RETRIES_PER_CHAPTER
MAX_TARGETED_RETRIES_TOTAL = z77.MAX_TARGETED_RETRIES_TOTAL
MAX_NETWORK_ATTEMPTS = z77.MAX_NETWORK_ATTEMPTS

V2_RUN_DIR = ROOT / "runs/Z77_X01_事实说明书注入包v2_三章复验_v1.0_20260721"
V2_REPORT_DIR = ROOT / "reports/Z77_事实说明书注入包v2三章复验_20260721"
V2_PACKAGE = V2_RUN_DIR / "prompt_candidates/事实说明书注入包_v2.json"
V2_PACKAGE_SHA256 = "a05cfdbf7617d57647701c26fc3b3bd3678462eeb9866fbcd1116f910b330d60"
V2_CONTRACT = V2_RUN_DIR / "provenance/sensenova_stage_sampling_z77_v1.json"
V2_CONTRACT_SHA256 = "91b46737e196cda5202a10394cee68fb3d8e34867e0a8431c3c17c28814d047b"
V2_ADJUDICATION = V2_REPORT_DIR / "adjudications/语义人工复核源.json"
V2_ADJUDICATION_SHA256 = "386bd384a880f3526d9460fe7c61134fdbf2dc85dd671e983a49f2c43764e9db"
V2_SCORECARD = V2_REPORT_DIR / "成绩与验收总表.json"
V2_SCORECARD_SHA256 = "fa021b1feb1b994ca8d9f2363ff99db4eb1ba5948ad4150acf1e5aaa94c27d00"
V2_RUNNER_SHA256 = "4db22c590a0085efcfab57a3d751c0f3eb4b6690323fe37c3fd0334520134d68"
V2_TEST_SHA256 = "1893deae0dcd39a2e909ebf95cd3e767d0ed7162015d79a007581a0431855aa5"
V2_PREPARED_SHA256 = {
    3: "1e3b12f89001f4d68d0f8aff5873ad4f57044be71edc878b9eff3e23e148540e",
    13: "8dad7aadf3b1c1d168ac41e68730916db6a41e6628456dea7c8e0100ff417a4a",
    19: "1620dbfa8193dcf281f8ae6a1741740126e6f9ae5c922608ec1c9416dfd47e0d",
}

JUDGMENT_RULE = (
    "10. 对话／问答场景中，提问、回答、答话里给出的排除或确认结论、"
    "以及由结论引发的行动转向，各自是独立事实须单列；不得只记提问与理论性回答。"
)
ANCHOR_SUPPORT_RULE = (
    "4. 事件句里的每个关键主张（信息来源、心理状态、结论、志向等）都必须被所挂锚的原文托住；"
    "支撑句在目录哪个锚里就把那个锚一并挂上，一个事件可挂多个锚；挂出的锚托不住的措辞，"
    "要么补挂目录内正确锚、要么删掉该措辞。"
)
FINAL_ANCHOR_REMINDER = (
    "4. 事件句中每个信息来源、心理状态、结论、志向等关键主张都要有对应目录锚托住；"
    "否则补挂正确锚或删掉无锚支撑的措辞。"
)

QUESTION_EXAMPLE = """### QA-CONCLUSION-01｜问答中的确认结论与行动转向分别单列
材料：冷链站主管询问复检是否完成。检测员回答复检已经完成，样本未受污染，温控记录也没有异常；根据这些结论，检测员解除暂存，并改由物流员把样本送入合格品库。
刚好版（正例）：
- 事件：冷链站主管询问复检是否完成。｜示例短引：冷链站主管询问复检是否完成。
- 事件：检测员确认复检已经完成。｜示例短引：检测员回答复检已经完成。
- 事件：检测员确认样本未受污染。｜示例短引：样本未受污染。
- 事件：检测员确认温控记录没有异常。｜示例短引：温控记录也没有异常。
- 事件：根据复检结论，检测员解除暂存，并改由物流员把样本送入合格品库。｜示例短引：根据这些结论，检测员解除暂存；改由物流员把样本送入合格品库。
教学点：提问、答话中的每个排除或确认结论、以及结论触发的行动转向，都有独立真假边界；不能只保留提问和一句泛化回答。"""

FINAL_REMINDER = z77.FINAL_REMINDER + "\n" + FINAL_ANCHOR_REMINDER
RETRY_SYSTEM = z77.RETRY_SYSTEM

CASE_TOKENS_FORBIDDEN_IN_INJECTION = (
    "GOLD-C0003",
    "B-C0013-02",
    "E0022",
    "E0126",
    "E0127",
    "E0049",
)

FIXED_SYSTEM_LAYER_ORDER = (
    "【信息边界与来源分工】",
    "【判断规则】",
    "【证据规则】",
    "【静默检查】",
    "【异题材正例区｜例子不是当前章事实】",
    "【输出合同与硬红线｜交卷前以本节为准】",
)


def read_json(path: Path) -> Any:
    return z68.read_json(path)


def write_json(path: Path, value: Any) -> None:
    z68.write_json(path, value)


def write_json_atomic(path: Path, value: Any) -> None:
    z77.write_json_atomic(path, value)


def append_jsonl(path: Path, value: Any) -> None:
    z77.append_jsonl(path, value)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _assert_file(path: Path, expected_sha256: str, label: str) -> None:
    if not path.is_file() or z68.sha256_file(path) != expected_sha256:
        raise ZBatchError(f"{label}不存在或 SHA 漂移：{path}")


def assert_v2_sources() -> dict[str, Any]:
    sources = (
        (V2_PACKAGE, V2_PACKAGE_SHA256, "第77道 v2 注入包"),
        (V2_CONTRACT, V2_CONTRACT_SHA256, "第77道 v2 运输合同"),
        (V2_ADJUDICATION, V2_ADJUDICATION_SHA256, "第77道语义判词"),
        (V2_SCORECARD, V2_SCORECARD_SHA256, "第77道成绩单"),
        (ROOT / "tools/z77_fact_sheet_v2_pilot.py", V2_RUNNER_SHA256, "第77道运行器"),
        (ROOT / "tests/test_z77_fact_sheet_v2_pilot.py", V2_TEST_SHA256, "第77道测试"),
    )
    rows = []
    for path, expected, label in sources:
        _assert_file(path, expected, label)
        rows.append(
            {
                "label": label,
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": expected,
            }
        )
    for chapter, expected in V2_PREPARED_SHA256.items():
        path = V2_RUN_DIR / f"prepared_requests/ch{chapter:04d}.json"
        _assert_file(path, expected, f"第77道第{chapter}章请求")
        rows.append(
            {
                "label": f"第77道第{chapter}章请求",
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": expected,
            }
        )
    return {"status": "pass", "sources": rows}


def assert_protected() -> dict[str, Any]:
    return {
        "formal_and_z75": z77.assert_protected(),
        "z77_run_tree": z77.multi_tree_fingerprint((V2_RUN_DIR,)),
        "z77_report_tree": z77.multi_tree_fingerprint((V2_REPORT_DIR,)),
        "v2_source_pins": assert_v2_sources(),
    }


def _v2_package() -> dict[str, Any]:
    assert_v2_sources()
    package = read_json(V2_PACKAGE)
    if package.get("schema_version") != "z77-fact-sheet-injection-package-v2":
        raise ZBatchError("第77道 v2 包 schema 漂移")
    return package


def v2_system(chapter: int) -> str:
    package = _v2_package()
    systems = package.get("systems")
    row = systems.get(str(chapter)) if isinstance(systems, dict) else None
    if not isinstance(row, dict) or not isinstance(row.get("content"), str):
        raise ZBatchError(f"第77道 v2 包缺第{chapter}章 system")
    content = str(row["content"])
    prepared = load_v2_body(chapter)
    if content != prepared["messages"][0]["content"]:
        raise ZBatchError(f"第{chapter}章 v2 包与 v2 实跑请求的 system 不一致")
    return content


def load_v2_body(chapter: int) -> dict[str, Any]:
    path = V2_RUN_DIR / f"prepared_requests/ch{chapter:04d}.json"
    _assert_file(path, V2_PREPARED_SHA256[chapter], f"第77道第{chapter}章请求")
    return read_json(path)


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ZBatchError(f"v2→v3 {label}插入锚数量不是1：{count}")
    return text.replace(old, new, 1)


def question_example_document() -> dict[str, Any]:
    return {
        "schema_version": "z79-question-example-v1",
        "status": "candidate_model_visible",
        "group_id": "QA-CONCLUSION-01",
        "model_visible_text": QUESTION_EXAMPLE,
    }


@functools.lru_cache(maxsize=1)
def _question_example_decoupling_cached() -> dict[str, Any]:
    receipt = z74a.audit_decoupling(question_example_document(), dict(z74a.DEFAULT_CORPORA))
    receipt = copy.deepcopy(receipt)
    receipt["schema_version"] = "z79-question-example-decoupling-v1"
    receipt["audited_file"] = "v3新增换皮问答正例"
    receipt["audited_scope"] = "QA-CONCLUSION-01 全部模型可见字符串"
    receipt["source_rule"] = "复用第74道A线六本章窗、专名表、题材禁词与18字归一化长片段闸"
    if receipt.get("status") != "pass":
        raise ZBatchError(f"v3 换皮问答正例与六本未解耦：{receipt.get('gates')}")
    return receipt


def question_example_decoupling() -> dict[str, Any]:
    return copy.deepcopy(_question_example_decoupling_cached())


def layer_registry() -> dict[str, Any]:
    """记录 v3 四个模型可见增量的唯一层位，不把规则复制到其他节。"""

    rows = [
        {
            "repair_id": "anchor_support_complete",
            "addition_id": "ANCHOR-SUPPORT-04",
            "section": "【证据规则】",
            "item_number": "4",
            "unique_location": True,
            "model_visible_sha256": sha256_text(ANCHOR_SUPPORT_RULE),
        },
        {
            "repair_id": "anchor_support_complete",
            "addition_id": "FINAL-REMINDER-04",
            "section": "【最终提醒】",
            "item_number": "4",
            "unique_location": True,
            "model_visible_sha256": sha256_text(FINAL_ANCHOR_REMINDER),
        },
        {
            "repair_id": "dialogue_conclusion_separation",
            "addition_id": "JUDGMENT-10",
            "section": "【判断规则】",
            "item_number": "10",
            "unique_location": True,
            "model_visible_sha256": sha256_text(JUDGMENT_RULE),
        },
        {
            "repair_id": "dialogue_conclusion_separation",
            "addition_id": "QA-CONCLUSION-01",
            "section": "【异题材正例区】",
            "item_number": "QA-CONCLUSION-01",
            "unique_location": True,
            "model_visible_sha256": sha256_text(QUESTION_EXAMPLE),
        },
    ]
    if len({row["addition_id"] for row in rows}) != 4 or not all(
        row["unique_location"] for row in rows
    ):
        raise ZBatchError("v3 层位登记不是四个唯一落点")
    return {
        "schema_version": "z79-layer-registry-v1",
        "status": "pass_four_unique_locations",
        "fixed_system_layer_order": list(FIXED_SYSTEM_LAYER_ORDER),
        "user_tail_after_system": "【最终提醒】",
        "rows": rows,
        "other_sections_receive_v3_additions": False,
    }


def updated_deduplication_receipt() -> dict[str, Any]:
    """保留 v2 六处去重结论，只追加 v3 的四个唯一落点账。"""

    base = copy.deepcopy(_v2_package().get("deduplication"))
    if not isinstance(base, dict) or len(base.get("merged_duplicates") or []) != 6:
        raise ZBatchError("第77道 v2 六处去重账漂移")
    base_canonical_sha256 = z68.canonical_sha(base)
    base["schema_version"] = "z79-system-deduplication-v3"
    base["base_v2_deduplication"] = {
        "schema_version": "z77-system-deduplication-v1",
        "canonical_sha256": base_canonical_sha256,
        "merged_duplicate_count": 6,
        "preserved_unchanged": True,
    }
    base["v3_unique_layer_additions"] = copy.deepcopy(layer_registry()["rows"])
    base["v3_duplicate_expression_elsewhere"] = False
    return base


def _line_diff(old: str, new: str, *, old_name: str, new_name: str) -> dict[str, Any]:
    lines = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=old_name,
            tofile=new_name,
            lineterm="",
        )
    )
    added = [line[1:] for line in lines if line.startswith("+") and not line.startswith("+++")]
    removed = [line[1:] for line in lines if line.startswith("-") and not line.startswith("---")]
    return {
        "only_additions": not removed,
        "added_lines": added,
        "removed_lines": removed,
        "unified_diff": lines,
    }


def render_system(chapter: int) -> tuple[str, dict[str, Any]]:
    old = v2_system(chapter)
    judgment_anchor = (
        "9. 只写“面临情况”“涉及问题”“发生变化”“进行处理”等空泛句不合格，"
        "必须写具体主体、动作、对象和明示结果。\n\n【证据规则】"
    )
    system = _replace_once(
        old,
        judgment_anchor,
        judgment_anchor.replace("\n\n【证据规则】", f"\n{JUDGMENT_RULE}\n\n【证据规则】"),
        "结论类事实单列规则",
    )
    evidence_anchor = "3. 证据不足时缩回原文能证明的范围，禁止靠常识补齐。\n\n【静默检查】"
    system = _replace_once(
        system,
        evidence_anchor,
        evidence_anchor.replace("\n\n【静默检查】", f"\n{ANCHOR_SUPPORT_RULE}\n\n【静默检查】"),
        "锚挂全规则",
    )
    example_anchor = "【正例区结束】现在只处理 user 消息中的当前章。"
    system = _replace_once(
        system,
        example_anchor,
        QUESTION_EXAMPLE + "\n\n" + example_anchor,
        "换皮问答正例",
    )
    leaked = [token for token in CASE_TOKENS_FORBIDDEN_IN_INJECTION if token in system]
    if leaked:
        raise ZBatchError(f"v3 system 夹入程序侧病例标识：{leaked}")
    if z68.request_has_prohibited_input({"messages": [{"role": "system", "content": system}]}):
        raise ZBatchError("v3 system 夹入禁入材料")
    diff = _line_diff(old, system, old_name=f"v2_system_ch{chapter:04d}", new_name=f"v3_system_ch{chapter:04d}")
    expected_nonblank = [
        JUDGMENT_RULE,
        ANCHOR_SUPPORT_RULE,
        *[line for line in QUESTION_EXAMPLE.splitlines() if line],
    ]
    actual_nonblank = [line for line in diff["added_lines"] if line]
    if not diff["only_additions"] or actual_nonblank != expected_nonblank:
        raise ZBatchError(f"第{chapter}章 v3 system 出现两项修复外的变化")
    return system, {
        "chapter": chapter,
        "message_count": 1,
        "base_v2_system_sha256": sha256_text(old),
        "v3_system_sha256": sha256_text(system),
        "bytes": len(system.encode("utf-8")),
        "repairs": [
            {
                "repair_id": "anchor_support_complete",
                "system_rule": ANCHOR_SUPPORT_RULE,
                "user_reminder": FINAL_ANCHOR_REMINDER,
            },
            {
                "repair_id": "dialogue_conclusion_separation",
                "system_rule": JUDGMENT_RULE,
                "example_group": "QA-CONCLUSION-01",
            },
        ],
        "line_diff": diff,
        "case_tokens_absent": True,
    }


def build_candidate_body(chapter: int) -> tuple[dict[str, Any], dict[str, Any]]:
    v2 = load_v2_body(chapter)
    if v2["max_tokens"] != MAX_TOKENS or [row["role"] for row in v2["messages"]] != ["system", "user"]:
        raise ZBatchError(f"第{chapter}章 v2 请求形状漂移")
    old_user = str(v2["messages"][1]["content"])
    if not old_user.endswith(z77.FINAL_REMINDER):
        raise ZBatchError(f"第{chapter}章 v2 user 末尾提醒漂移")
    system, system_meta = render_system(chapter)
    user = old_user[: -len(z77.FINAL_REMINDER)] + FINAL_REMINDER
    candidate = copy.deepcopy(v2)
    candidate["messages"] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    changed = z70.deep_diff_paths(v2, candidate)
    if changed != ["$.messages[0].content", "$.messages[1].content"]:
        raise ZBatchError(f"第{chapter}章 v3 混入两条消息外的变化：{changed}")
    user_diff = _line_diff(old_user, user, old_name="v2_user", new_name="v3_user")
    if user_diff["removed_lines"] or user_diff["added_lines"] != [FINAL_ANCHOR_REMINDER]:
        raise ZBatchError(f"第{chapter}章 user 末尾出现锚提醒外变化")
    prohibited = z68.request_has_prohibited_input(candidate)
    if prohibited:
        raise ZBatchError(f"第{chapter}章 v3 请求夹入禁入材料：{prohibited}")
    return candidate, {
        "schema_version": "z79-request-diff-v1",
        "chapter": chapter,
        "base_v2_request_sha256": V2_PREPARED_SHA256[chapter],
        "changed_paths": changed,
        "top_level_unchanged_except_messages": all(
            candidate[key] == v2[key] for key in v2 if key != "messages"
        ),
        "sampling_and_transport_unchanged": all(
            candidate[key] == v2[key]
            for key in ("model", "temperature", "max_tokens", "n", "reasoning_effort", "response_format")
        ),
        "system": system_meta,
        "user_line_diff": user_diff,
        "v2_canonical_sha256": z68.canonical_sha(v2),
        "v3_canonical_sha256": z68.canonical_sha(candidate),
    }


def v2_to_v3_diff_receipt() -> dict[str, Any]:
    rows = []
    for chapter in TARGET_CHAPTERS:
        _, diff = build_candidate_body(chapter)
        rows.append(
            {
                "chapter": chapter,
                "changed_paths": diff["changed_paths"],
                "system_only_additive": diff["system"]["line_diff"]["only_additions"],
                "system_added_lines": diff["system"]["line_diff"]["added_lines"],
                "system_removed_lines": diff["system"]["line_diff"]["removed_lines"],
                "user_added_lines": diff["user_line_diff"]["added_lines"],
                "user_removed_lines": diff["user_line_diff"]["removed_lines"],
                "v2_request_sha256": V2_PREPARED_SHA256[chapter],
                "v3_canonical_sha256": diff["v3_canonical_sha256"],
            }
        )
    return {
        "schema_version": "z79-v2-to-v3-diff-v1",
        "status": "pass_exactly_two_repair_groups",
        "base_package_sha256": V2_PACKAGE_SHA256,
        "repair_groups": [
            {
                "repair_id": "anchor_support_complete",
                "model_visible_additions": [ANCHOR_SUPPORT_RULE, FINAL_ANCHOR_REMINDER],
            },
            {
                "repair_id": "dialogue_conclusion_separation",
                "model_visible_additions": [JUDGMENT_RULE, QUESTION_EXAMPLE],
            },
        ],
        "repair_group_count": 2,
        "rows": rows,
        "case_tokens_forbidden_in_injection": list(CASE_TOKENS_FORBIDDEN_IN_INJECTION),
        "case_tokens_absent": True,
        "no_third_change": True,
    }


def build_package() -> dict[str, Any]:
    systems = {}
    for chapter in TARGET_CHAPTERS:
        system, meta = render_system(chapter)
        systems[str(chapter)] = {"content": system, "meta": meta}
    return {
        "schema_version": "z79-fact-sheet-injection-package-v3",
        "status": "candidate_silver_only",
        "base_v2_package": {
            "path": V2_PACKAGE.relative_to(ROOT).as_posix(),
            "sha256": V2_PACKAGE_SHA256,
            "preserved_read_only": True,
        },
        "systems": systems,
        "user_final_reminder": FINAL_REMINDER,
        "user_final_reminder_sha256": sha256_text(FINAL_REMINDER),
        "targeted_retry_system": RETRY_SYSTEM,
        "targeted_retry_system_sha256": sha256_text(RETRY_SYSTEM),
        "targeted_retry_equals_v2": RETRY_SYSTEM == z77.RETRY_SYSTEM,
        "targeted_retry_policy": {
            "eligible": ["event超过100个非空字符", "anchor_id格式非法或不在当前冻结目录"],
            "per_event_limit": MAX_TARGETED_RETRIES_PER_EVENT,
            "per_chapter_limit": MAX_TARGETED_RETRIES_PER_CHAPTER,
            "total_limit": MAX_TARGETED_RETRIES_TOTAL,
            "other_errors": "hard_stop_no_repair",
        },
        "event_length_threshold": z77.length_threshold_receipt(),
        "layer_registry": layer_registry(),
        "deduplication": updated_deduplication_receipt(),
        "question_example_decoupling": question_example_decoupling(),
        "v2_to_v3_diff": v2_to_v3_diff_receipt(),
    }


def build_run_contract(path: Path) -> dict[str, Any]:
    _assert_file(V2_CONTRACT, V2_CONTRACT_SHA256, "第77道 v2 运输合同")
    raw = read_json(V2_CONTRACT)
    source_profile = copy.deepcopy(raw["profiles"][z77.PROFILE])
    raw["contract_version"] = "z79-fact-sheet-v3-transport-v1"
    raw["profiles"][PROFILE] = source_profile
    raw["profiles"][PROFILE]["note"] = "第79道隔离投影；运输与定点重试参数逐字段沿用第77道。"
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
        raise ZBatchError("第79道主请求不能由 v2 同参运输合同逐字段复现")


def copy_inputs(run_dir: Path) -> list[dict[str, Any]]:
    receipts = z77.copy_inputs(run_dir)
    target_dir = run_dir / "provenance/v2_failed_candidate"
    target_dir.mkdir(parents=True, exist_ok=True)
    for source, expected, target_name in (
        (V2_PACKAGE, V2_PACKAGE_SHA256, "事实说明书注入包_v2.json"),
        (V2_ADJUDICATION, V2_ADJUDICATION_SHA256, "第77道语义人工复核源.json"),
        (V2_SCORECARD, V2_SCORECARD_SHA256, "第77道成绩与验收总表.json"),
    ):
        _assert_file(source, expected, "第79道 v2 只读底稿")
        target = target_dir / target_name
        shutil.copyfile(source, target)
        receipts.append(
            {
                "source": source.relative_to(ROOT).as_posix(),
                "source_sha256": expected,
                "target": target.relative_to(run_dir).as_posix(),
                "target_sha256": z68.sha256_file(target),
            }
        )
    return receipts


def prepare(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    source_inputs = z70.assert_source_inputs()
    protected = assert_protected()
    run_dir.mkdir(parents=True)
    build_run_contract(run_dir / RUN_LOCAL_CONTRACT)
    copied_inputs = copy_inputs(run_dir)
    package = build_package()
    package_path = run_dir / "prompt_candidates/事实说明书注入包_v3.json"
    write_json(package_path, package)
    write_json(run_dir / "prompt_candidates/v2至v3逐行差异账.json", package["v2_to_v3_diff"])
    write_json(run_dir / "prompt_candidates/v3层位登记表.json", package["layer_registry"])
    write_json(run_dir / "prompt_candidates/去重与唯一落点账_v3.json", package["deduplication"])
    write_json(
        run_dir / "prompt_candidates/换皮问答正例_六本机械查重.json",
        package["question_example_decoupling"],
    )
    rows = []
    for chapter in TARGET_CHAPTERS:
        v2_body = load_v2_body(chapter)
        candidate, diff = build_candidate_body(chapter)
        assert_body_matches_contract(candidate, run_dir)
        v2_path = run_dir / f"v2_requests/ch{chapter:04d}.json"
        prepared_path = run_dir / f"prepared_requests/ch{chapter:04d}.json"
        diff_path = run_dir / f"request_diffs/ch{chapter:04d}.json"
        write_json(v2_path, v2_body)
        write_json(prepared_path, candidate)
        write_json(diff_path, diff)
        system_path = run_dir / f"prompt_candidates/system_ch{chapter:04d}.txt"
        system_path.parent.mkdir(parents=True, exist_ok=True)
        system_path.write_text(candidate["messages"][0]["content"], encoding="utf-8")
        rows.append(
            {
                "chapter": chapter,
                "v2_request_sha256": z68.sha256_file(v2_path),
                "prepared_request_sha256": z68.sha256_file(prepared_path),
                "request_diff_sha256": z68.sha256_file(diff_path),
                "system_prompt_sha256": z68.sha256_file(system_path),
            }
        )
    preflight = {
        "schema_version": "z79-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": z68.now_iso(),
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "network_attempts": 0,
        "target_chapters": list(TARGET_CHAPTERS),
        "main_samples_per_chapter": 1,
        "sampling": {
            "main": {
                "model": "deepseek-v4-flash",
                "temperature": 0.2,
                "max_tokens": MAX_TOKENS,
                "n": 1,
                "reasoning_effort": "medium",
                "response_format": {"type": "json_object"},
            },
            "targeted_retry": {
                "model": "deepseek-v4-flash",
                "temperature": 0.2,
                "max_tokens": RETRY_MAX_TOKENS,
                "n": 1,
                "reasoning_effort": "medium",
                "response_format": {"type": "json_object"},
            },
        },
        "targeted_retry_policy": package["targeted_retry_policy"],
        "source_inputs": source_inputs,
        "v2_sources": assert_v2_sources(),
        "copied_inputs": copied_inputs,
        "protected_before": protected,
        "package": {
            "path": package_path.relative_to(run_dir).as_posix(),
            "sha256": z68.sha256_file(package_path),
        },
        "producer": {
            "path": Path(__file__).relative_to(ROOT).as_posix(),
            "sha256": z68.sha256_file(Path(__file__)),
        },
        "rows": rows,
    }
    write_json(run_dir / "preflight.json", preflight)
    write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z79-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "prepared",
            "model_api_calls": 0,
            "network_attempts": 0,
        },
    )
    verify_prepared(run_dir, require_zero_call=True)
    return preflight


def call_artifacts_present(run_dir: Path) -> list[str]:
    paths = (
        run_dir / RUN_CLAIM,
        run_dir / "call_attempts.jsonl",
        run_dir / "usage.jsonl",
        run_dir / "requests",
        run_dir / "responses",
        run_dir / "01_extract",
        run_dir / "hard_stop.json",
    )
    return [path.relative_to(run_dir).as_posix() for path in paths if path.exists()]


def verify_prepared(run_dir: Path, *, require_zero_call: bool) -> dict[str, Any]:
    preflight = read_json(run_dir / "preflight.json")
    manifest = read_json(run_dir / "run_manifest.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("第79道预演状态漂移")
    if preflight.get("model_api_calls") != 0 or preflight.get("network_attempts") != 0:
        raise ZBatchError("第79道预演调用账不为0")
    if require_zero_call and (manifest.get("status") != "prepared" or call_artifacts_present(run_dir)):
        raise ZBatchError("第79道目录不是可首次运行的零调用状态")
    if z70.assert_source_inputs() != preflight["source_inputs"]:
        raise ZBatchError("第79道冻结输入源漂移")
    if z68.tree_fingerprint(run_dir / "inputs") != preflight["source_inputs"]:
        raise ZBatchError("第79道隔离输入漂移")
    producer = ROOT / preflight["producer"]["path"]
    if z68.sha256_file(producer) != preflight["producer"]["sha256"]:
        raise ZBatchError("第79道运行器 prepare 后漂移")
    if assert_protected() != preflight["protected_before"]:
        raise ZBatchError("第79道保护件或 v2 原件漂移")
    package_path = run_dir / preflight["package"]["path"]
    if read_json(package_path) != build_package():
        raise ZBatchError("第79道 v3 注入包不能机械重建")
    checks = []
    for chapter in TARGET_CHAPTERS:
        expected, diff = build_candidate_body(chapter)
        actual = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
        assert_body_matches_contract(actual, run_dir)
        passed = (
            actual == expected
            and actual["messages"][1]["content"].endswith(FINAL_REMINDER)
            and diff["sampling_and_transport_unchanged"]
            and diff["system"]["line_diff"]["only_additions"]
            and not diff["system"]["line_diff"]["removed_lines"]
            and not diff["user_line_diff"]["removed_lines"]
            and not z68.request_has_prohibited_input(actual)
        )
        if not passed:
            raise ZBatchError(f"第{chapter}章 v3 请求不能机械重建")
        checks.append({"chapter": chapter, "passed": True})
    receipt = {
        "schema_version": "z79-prepared-verification-v1",
        "status": "pass",
        "require_zero_call": require_zero_call,
        "checks": checks,
        "protected_unchanged": True,
        "package_rebuilt_equal": True,
        "v2_to_v3_exactly_two_repair_groups": True,
    }
    write_json(run_dir / "prepared_request_verification.json", receipt)
    return receipt


def acquire_run_claim(run_dir: Path) -> dict[str, Any]:
    claim_path = run_dir / RUN_CLAIM
    claim = {
        "schema_version": "z79-run-claim-v1",
        "status": "claimed_do_not_resume",
        "claimed_at": z68.now_iso(),
        "pid": os.getpid(),
    }
    try:
        descriptor = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ZBatchError("第79道已经开跑或曾中断，拒绝重复采样") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(claim, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def acquire_retry(
    *,
    transport: api_transport.ApiTransport,
    run_dir: Path,
    chapter: int,
    row: Mapping[str, Any],
    catalog: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_id = f"z79_ch{chapter:04d}_{str(row['event_id']).lower()}"
    messages = z77.build_retry_messages(
        chapter=chapter,
        original_event=row["original_event"],
        violations=list(row["violations"]),
        chapter_text=z77.chapter_text(run_dir, chapter),
        catalog=catalog,
    )
    result = transport.call(stage="targeted_retry", case_id=case_id, messages=messages)
    if result.finish_reason != "stop" or not result.content.strip():
        raise ZBatchError(f"第{chapter}章 {row['event_id']} 定点重试未stop或正文为空")
    parsed = candidate_envelope.parse_json_content(result.content)
    allow_multiple = any(value.startswith("event_nonspace_chars=") for value in row["violations"])
    replacements = z77.validate_replacements(parsed, catalog=catalog, allow_multiple=allow_multiple)
    receipt = {
        "chapter": chapter,
        "original_event_id": row["event_id"],
        "violations": list(row["violations"]),
        "attempt": 1,
        "max_attempts_per_event": MAX_TARGETED_RETRIES_PER_EVENT,
        "replacement_count": len(replacements),
        "original_event": row["original_event"],
        "replacement_events": replacements,
        "request_sha256": z68.sha256_file(run_dir / f"requests/targeted_retry/{case_id}_request.json"),
        "raw_response_sha256": z68.sha256_file(run_dir / f"responses/targeted_retry/{case_id}_raw.json"),
    }
    return replacements, receipt


def run(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    verify_prepared(run_dir, require_zero_call=True)
    preflight = read_json(run_dir / "preflight.json")
    claim = acquire_run_claim(run_dir)
    write_json_atomic(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z79-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "running_do_not_resume",
            "run_claim": claim,
        },
    )
    completed: list[int] = []
    retry_total = 0
    retry_ledger: list[dict[str, Any]] = []
    try:
        transport = api_transport.ApiTransport.from_bundle(
            load_bundle(run_dir), run_dir=run_dir, max_calls=MAX_NETWORK_ATTEMPTS
        )
        for chapter in TARGET_CHAPTERS:
            case_id = f"z79_ch{chapter:04d}"
            prepared = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
            assert_body_matches_contract(prepared, run_dir)
            result = transport.call(
                stage="neutral_extract", case_id=case_id, messages=prepared["messages"]
            )
            actual = read_json(run_dir / f"requests/neutral_extract/{case_id}_request.json")
            if actual.get("body") != prepared or result.request_record.get("body") != prepared:
                raise ZBatchError(f"第{chapter}章实际主请求不等于 prepared")
            if result.finish_reason != "stop" or not result.content.strip():
                raise ZBatchError(f"第{chapter}章主回包未stop或正文为空")
            model_json = candidate_envelope.parse_json_content(result.content)
            write_json(run_dir / f"01_extract/model_json_original/ch{chapter:04d}.json", model_json)
            catalog = read_json(run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json")["entries"]
            analysis = z77.analyze_main_response(model_json, chapter=chapter, catalog=catalog)
            write_json(run_dir / f"01_extract/initial_audits/ch{chapter:04d}.json", analysis)
            if analysis["hard_reasons"]:
                raise ZBatchError(f"第{chapter}章出现非授权失败面：{analysis['hard_reasons']}")
            eligible = analysis["eligible"]
            if len(eligible) > MAX_TARGETED_RETRIES_PER_CHAPTER:
                raise ZBatchError(f"第{chapter}章违规事件{len(eligible)}条，超过定点重试上限")
            if retry_total + len(eligible) > MAX_TARGETED_RETRIES_TOTAL:
                raise ZBatchError("第79道定点重试总上限已满")
            replacements: dict[int, list[dict[str, Any]]] = {}
            for row in eligible:
                fixed, receipt = acquire_retry(
                    transport=transport,
                    run_dir=run_dir,
                    chapter=chapter,
                    row=row,
                    catalog=catalog,
                )
                replacements[int(row["index"])] = fixed
                retry_total += 1
                retry_ledger.append(receipt)
                append_jsonl(run_dir / "targeted_retry_ledger.jsonl", receipt)
            final_json = z77.apply_replacements(model_json, chapter=chapter, replacements=replacements)
            materialized, audit = neutral_extract.process_model_data(
                final_json, chapter=chapter, catalog=catalog
            )
            write_json(run_dir / f"01_extract/model_json/ch{chapter:04d}.json", final_json)
            write_json(run_dir / f"01_extract/events/ch{chapter:04d}.json", materialized)
            write_json(run_dir / f"01_extract/program_audits/ch{chapter:04d}.json", audit)
            completed.append(chapter)
    except BaseException as exc:
        attempts = z68.read_jsonl(run_dir / "call_attempts.jsonl")
        hard_stop = {
            "schema_version": "z79-hard-stop-v1",
            "status": "hard_stop_no_unapproved_repair",
            "at": z68.now_iso(),
            "completed_chapters": completed,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "targeted_retry_count": retry_total,
            "network_attempts": len(attempts),
            "protected_unchanged": assert_protected() == preflight["protected_before"],
        }
        write_json(run_dir / "hard_stop.json", hard_stop)
        write_json_atomic(
            run_dir / "run_manifest.json",
            {
                "schema_version": "z79-run-manifest-v1",
                "run_id": run_dir.name,
                "status": "hard_stop",
                "completed_chapters": completed,
                "run_claim": claim,
                "network_attempts": len(attempts),
                "targeted_retry_count": retry_total,
            },
        )
        raise
    attempts = z68.read_jsonl(run_dir / "call_attempts.jsonl")
    usage = z68.read_jsonl(run_dir / "usage.jsonl")
    usage_totals: Counter[str] = Counter()
    for row in usage:
        for key, value in (row.get("usage") or {}).items():
            if isinstance(value, int):
                usage_totals[key] += value
    metrics = {
        "schema_version": "z79-run-metrics-v1",
        "status": "completed_candidate_silver_only",
        "chapters_completed": completed,
        "main_logical_calls": len(TARGET_CHAPTERS),
        "targeted_retry_logical_calls": retry_total,
        "successful_responses": len(usage),
        "network_attempts": len(attempts),
        "usage_totals": dict(usage_totals),
        "targeted_retry_ledger": retry_ledger,
    }
    write_json(run_dir / "01_extract/metrics.json", metrics)
    write_json_atomic(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z79-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "completed_candidate_silver_only",
            "chapters_completed": completed,
            "run_claim": claim,
            "network_attempts": len(attempts),
            "targeted_retry_count": retry_total,
        },
    )
    return metrics


def verify(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    prepared = verify_prepared(run_dir, require_zero_call=False)
    manifest = read_json(run_dir / "run_manifest.json")
    if manifest.get("status") != "completed_candidate_silver_only":
        raise ZBatchError(f"第79道尚未完成：{manifest.get('status')}")
    preflight = read_json(run_dir / "preflight.json")
    checks: list[dict[str, Any]] = []
    outside_total = 0
    overlength_total = 0
    chapter_invalidations = 0
    for chapter in TARGET_CHAPTERS:
        case_id = f"z79_ch{chapter:04d}"
        prepared_body = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
        actual_body = read_json(run_dir / f"requests/neutral_extract/{case_id}_request.json")["body"]
        final_json = read_json(run_dir / f"01_extract/model_json/ch{chapter:04d}.json")
        audit = read_json(run_dir / f"01_extract/program_audits/ch{chapter:04d}.json")
        catalog = read_json(run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json")["entries"]
        reasons, rebuilt = neutral_extract.audit_event_envelope(final_json, chapter, catalog)
        outside = len(rebuilt.get("missing_catalog_anchor_ids") or [])
        overlength = sum(
            1
            for event in final_json["events"]
            if nonspace_chars(str(event["event"])) > MAX_EVENT_NONSPACE_CHARS
        )
        outside_total += outside
        overlength_total += overlength
        if reasons or audit != rebuilt:
            chapter_invalidations += 1
        checks.append(
            {
                "chapter": chapter,
                "actual_equals_prepared": actual_body == prepared_body,
                "final_program_audit_pass": not reasons and audit == rebuilt and audit.get("status") == "pass",
                "outside_catalog_anchor_count": outside,
                "overlength_event_count": overlength,
                "event_count": len(final_json["events"]),
            }
        )
    scan = z77.secret_scan(run_dir)
    protected_unchanged = assert_protected() == preflight["protected_before"]
    passed = (
        prepared["status"] == "pass"
        and all(row["actual_equals_prepared"] and row["final_program_audit_pass"] for row in checks)
        and outside_total == 0
        and overlength_total == 0
        and chapter_invalidations == 0
        and scan["passed"]
        and protected_unchanged
    )
    receipt = {
        "schema_version": "z79-mechanical-verification-v1",
        "status": "pass" if passed else "fail",
        "checks": checks,
        "gates": {
            "outside_catalog_anchor_zero": outside_total == 0,
            "length_rejection_zero": overlength_total == 0,
            "whole_chapter_invalidation_zero": chapter_invalidations == 0,
        },
        "targeted_retry_count": read_json(run_dir / "01_extract/metrics.json")[
            "targeted_retry_logical_calls"
        ],
        "secret_scan": scan,
        "protected_unchanged": protected_unchanged,
        "v2_failed_candidate_unchanged": protected_unchanged,
    }
    write_json(run_dir / "mechanical_verification.json", receipt)
    if not passed:
        raise ZBatchError("第79道机械复验失败")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "verify", "show-package"))
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if args.action == "show-package":
        print(json.dumps(build_package(), ensure_ascii=False, indent=2))
        return 0
    result = {"prepare": prepare, "run": run, "verify": verify}[args.action](run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

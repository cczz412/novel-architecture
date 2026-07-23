#!/usr/bin/env python3
"""第68道：ChatGPT 修正版请求体五靶章裸考旁路。

第3章直接使用外部定稿原件；其余四章只替换章号、文件名、连续正文、
冻结证据目录，并删除第3章专属命名提示。所有调用和分析工件写入独立 run。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import z59_entity_supply_pilot as z59  # noqa: E402
from zbatch_modules import api_transport  # noqa: E402
from zbatch_modules import candidate_envelope  # noqa: E402
from zbatch_modules import neutral_extract  # noqa: E402
from zbatch_modules import stage_sampling  # noqa: E402
from zbatch_modules.errors import ZBatchError  # noqa: E402


TARGET_CHAPTERS = (3, 4, 5, 13, 19)
RUN_ID = "Z68_X01_修正版请求体裸考_五靶章_v1.0_20260720"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_ID
ORIGINAL_REQUEST = (
    ROOT
    / "references/diagnostic-returns/Z66_中性原子事件请求诊断_三问法_20260720"
    / "原始回包/第3章LLM请求诊断_修正版与抽取结果"
    / "修正版_第3章_chat_completions_request.json"
)
ORIGINAL_REQUEST_SHA256 = "5c19b48512117dd1cd52db5e76f94dcaa4802eb427df6108a802ab6689567e3d"
SOURCE_RUN = ROOT / "runs/Z56b_X01_端到端全链体检_提取20章_v1.0_20260719"
CHAPTER_DIR = ROOT / "TEMP/X批材料包_20260716/books/X01_诡秘之主/chapters"
GOLD_V1_1 = ROOT / "reports/Z56_金标双轨分层与全链体检_20260719/第3章结构层金标v1.1.json"
CURRENT_122 = ROOT / "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json"
DEFAULT_REGISTRY = ROOT / "config/defaults/zbatch_v1.2_full_chain.json"
ACTIVE_CLASSIFY_CONTRACT = ROOT / "config/contracts/classify_rules_v1.2_semantic_identity_v1.json"
SAMPLING_CONTRACT = ROOT / "config/contracts/sensenova_stage_sampling_v1.json"
PROVIDER_CONFIG = ROOT / "config/providers/sensenova_modular_v1.json"
RUBRIC = ROOT / "config/experiments/Z59_第3章抽取评分预写尺_v1.json"
OUTBOX = ROOT / "outbox"

EXPECTED_PROTECTED_SHA = {
    ORIGINAL_REQUEST: ORIGINAL_REQUEST_SHA256,
    GOLD_V1_1: "8cca04f06ba21048e15420f178163c646d2effeead0970697fafbf5f45174b7c",
    CURRENT_122: "dafa16901a6edb5018a5176f3f5f7388273e72051def7fe4e997489d01e804ba",
    DEFAULT_REGISTRY: "b23b5cce26b9cfe584dd97dbff6422efa2b22ccd5cba38c6ed6a44c4543bc0a1",
    ACTIVE_CLASSIFY_CONTRACT: "45f7610b86d5962e0d3d9d4d95886aad9022f1beaece200c2452b9a361f6c108",
    SAMPLING_CONTRACT: "8ac9f7fa639aba7a7500948438df32b5bd054895ceb8362b1402ae76f0fdbb8c",
    PROVIDER_CONFIG: "fc38a198e30bd58d4022d8cf0804979d428b75f1a81c24d560edeba209495dfb",
    RUBRIC: "457e6f889c5133b7585d537aa041373bd62175e4bdfb003fbfd0b6d7f0320bda",
}

EXPECTED_BODY_KEYS = {
    "model",
    "messages",
    "temperature",
    "max_tokens",
    "n",
    "response_format",
    "reasoning_effort",
}
NAME_HINT_BLOCK = (
    "【本章命名提示】\n"
    "- 当前场景中的行动者按正文称为“周明瑞”；梅丽莎在对话中称他为“克莱恩”。\n"
    "- 描述原有记忆、过去经历或知识时，写清“克莱恩的记忆”或“周明瑞从克莱恩的记忆中得知”。\n"
    "- 以上提示只用于本章指代消解，不提供任何章后信息。\n\n"
)
TEXT_OPEN = "<<<CHAPTER_TEXT\n"
TEXT_CLOSE = "CHAPTER_TEXT"
CATALOG_PREFIX = (
    "【冻结证据目录】\n"
    "以下目录只用于选择 anchor_id。事件语义必须先从上面的连续正文理解。\n"
)
FINAL_MARKER = "\n\n【最终提醒】"
PROHIBITED_REQUEST_MARKERS = (
    "GOLD-C",
    "8cca04f06ba21048e15420f178163c646d2effeead0970697fafbf5f45174b7c",
    "第3章结构层金标",
    "第3章_修正版完整抽取结果",
    "32条示范",
    "现役122条",
)

# 只用于结果侧程序词法检查，不会注入请求。词表在正式调用前冻结。
SUBJECT_LEXICON: dict[int, tuple[str, ...]] = {
    3: ("周明瑞", "克莱恩", "梅丽莎", "班森", "进出口公司", "鲁恩王国"),
    4: (
        "周明瑞",
        "克莱恩",
        "班森",
        "梅丽莎",
        "温蒂斯林",
        "斯林太太",
        "温蒂",
        "罗塞尔.古斯塔夫",
        "罗塞尔",
        "占卜师",
        "女子",
        "店主",
        "流动街贩",
        "孩子们",
        "鲁恩王国",
        "廷根大学",
    ),
    5: (
        "周明瑞",
        "克莱恩",
        "占卜师",
        "驯兽师",
        "真正的占卜师",
        "奥黛丽.霍尔",
        "奥黛丽",
        "阿尔杰.威尔逊",
        "阿尔杰",
        "班森",
    ),
    13: (
        "克莱恩",
        "邓恩.史密斯",
        "邓恩",
        "韦尔奇",
        "娜娅",
        "戴莉",
        "正义",
        "倒吊人",
        "奥黛丽",
        "阿尔杰",
        "警察",
        "值夜者",
    ),
    19: (
        "克莱恩",
        "邓恩.史密斯",
        "邓恩",
        "韦尔奇",
        "娜娅",
        "戴莉",
        "老尼尔",
        "罗珊",
        "布莱特",
        "因斯.赞格威尔",
        "因斯",
        "新任大主教",
        "看守者",
        "值夜者总部",
        "值夜者",
        "教会",
    ),
}
VAGUE_PREDICATE_TERMS = (
    "面临",
    "涉及",
    "情况",
    "变化",
    "问题",
    "相关",
    "方面",
    "进行",
    "出现",
    "存在",
    "产生影响",
    "体现",
    "发生了变化",
    "情况复杂",
)
LEADING_MODIFIER = re.compile(r"^(?:在|当|由于|因为|为|为了|随后|之后|此前|此时|当天|次日)[^，,]{0,30}[，,]")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha(value: Any) -> str:
    wire = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(wire.encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_input(source: Path, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {
        "source": source.relative_to(ROOT).as_posix(),
        "target": target.as_posix(),
        "sha256": sha256_file(target),
        "bytes": target.stat().st_size,
    }


def tree_fingerprint(path: Path) -> dict[str, Any]:
    rows: list[tuple[str, str, int]] = []
    if path.exists():
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
            rows.append((item.relative_to(path).as_posix(), sha256_file(item), item.stat().st_size))
    wire = "\n".join(f"{name}\t{digest}\t{size}" for name, digest, size in rows)
    return {
        "files": len(rows),
        "bytes": sum(size for _, _, size in rows),
        "sha256": sha256_bytes(wire.encode("utf-8")),
    }


def assert_protected() -> dict[str, str]:
    observed: dict[str, str] = {}
    for path, expected in EXPECTED_PROTECTED_SHA.items():
        actual = sha256_file(path)
        if actual != expected:
            raise ZBatchError(f"保护件SHA漂移：{path.relative_to(ROOT)}，预期 {expected}，实际 {actual}")
        observed[path.relative_to(ROOT).as_posix()] = actual
    registry = read_json(DEFAULT_REGISTRY)
    runner = ROOT / registry["chain"]["runner"]["path"]
    runner_expected = registry["chain"]["runner"]["sha256"]
    if sha256_file(runner) != runner_expected:
        raise ZBatchError("现役默认登记所钉runner与实物不一致")
    observed[runner.relative_to(ROOT).as_posix()] = runner_expected
    return observed


def chapter_file(chapter: int) -> Path:
    matches = sorted(CHAPTER_DIR.glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise ZBatchError(f"第{chapter}章冻结正文文件数不是1：{len(matches)}")
    return matches[0]


def source_catalog(chapter: int) -> Path:
    return SOURCE_RUN / "01_extract/evidence_catalogs" / f"ch{chapter:04d}.json"


def source_events(chapter: int) -> Path:
    return SOURCE_RUN / "01_extract/events" / f"ch{chapter:04d}.json"


def load_original_body() -> dict[str, Any]:
    if sha256_file(ORIGINAL_REQUEST) != ORIGINAL_REQUEST_SHA256:
        raise ZBatchError("ChatGPT修正版请求体原件SHA漂移")
    body = read_json(ORIGINAL_REQUEST)
    if not isinstance(body, dict) or set(body) != EXPECTED_BODY_KEYS:
        raise ZBatchError("修正版请求体根字段不等于定稿合同")
    if (
        body.get("model") != "deepseek-v4-flash"
        or body.get("temperature") != 0.2
        or body.get("max_tokens") != 16000
        or body.get("n") != 1
        or body.get("response_format") != {"type": "json_object"}
        or body.get("reasoning_effort") != "medium"
    ):
        raise ZBatchError("修正版请求体采样参数偏离施工令")
    messages = body.get("messages")
    if (
        not isinstance(messages, list)
        or len(messages) != 2
        or [row.get("role") for row in messages if isinstance(row, dict)] != ["system", "user"]
    ):
        raise ZBatchError("修正版请求体不是system＋user两条消息")
    return body


def extract_text_payload(user: str) -> str:
    start = user.index(TEXT_OPEN) + len(TEXT_OPEN)
    end = user.index(TEXT_CLOSE, start)
    return user[start:end]


def replace_text_payload(user: str, payload: str) -> tuple[str, str]:
    start = user.index(TEXT_OPEN) + len(TEXT_OPEN)
    end = user.index(TEXT_CLOSE, start)
    old = user[start:end]
    return user[:start] + payload + user[end:], old


def extract_catalog_payload(user: str) -> str:
    start = user.index(CATALOG_PREFIX) + len(CATALOG_PREFIX)
    end = user.index(FINAL_MARKER, start)
    return user[start:end]


def replace_catalog_payload(user: str, payload: str) -> tuple[str, str]:
    start = user.index(CATALOG_PREFIX) + len(CATALOG_PREFIX)
    end = user.index(FINAL_MARKER, start)
    old = user[start:end]
    return user[:start] + payload + user[end:], old


def compact_catalog(entries: list[dict[str, Any]]) -> str:
    return json.dumps(entries, ensure_ascii=False, separators=(",", ":"))


def request_has_prohibited_input(body: Mapping[str, Any]) -> list[str]:
    wire = json.dumps(body.get("messages"), ensure_ascii=False)
    hits = [marker for marker in PROHIBITED_REQUEST_MARKERS if marker in wire]
    secret = __import__("os").environ.get("SENSENOVA_API_KEY", "")
    if secret and secret in wire:
        hits.append("实际API密钥")
    if "Authorization" in wire or "Bearer " in wire:
        hits.append("授权头痕迹")
    return hits


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ZBatchError(f"{label}待替换片段出现{count}次，不等于1")
    return text.replace(old, new, 1)


def build_instantiated_body(chapter: int) -> tuple[dict[str, Any], dict[str, Any]]:
    if chapter not in TARGET_CHAPTERS:
        raise ZBatchError(f"章次不在第68道五靶范围：{chapter}")
    original = load_original_body()
    original_system = original["messages"][0]["content"]
    original_user = original["messages"][1]["content"]
    source_text = chapter_file(chapter).read_text(encoding="utf-8")
    catalog_doc = read_json(source_catalog(chapter))
    entries = catalog_doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ZBatchError(f"第{chapter}章冻结证据目录为空")
    catalog_payload = compact_catalog(entries)

    if chapter == 3:
        if source_text != extract_text_payload(original_user):
            raise ZBatchError("修正版原件内第3章连续正文与intake冻结正文不一致")
        if catalog_payload != extract_catalog_payload(original_user):
            raise ZBatchError("修正版原件内第3章目录与现役冻结目录不一致")
        if request_has_prohibited_input(original):
            raise ZBatchError("第3章原件夹入禁入窗材料")
        return copy.deepcopy(original), {
            "chapter": 3,
            "mode": "direct_original_no_change",
            "body_equal_original": True,
            "body_canonical_sha256": canonical_sha(original),
            "source_text_sha256": sha256_file(chapter_file(3)),
            "catalog_sha256": sha256_file(source_catalog(3)),
            "catalog_entries_sha256": canonical_sha(entries),
            "name_hint": "kept_as_part_of_chapter3_original",
            "allowed_changes": [],
        }

    system = original_system
    if system.count('"chapter": 3') != 1 or system.count("EV-C0003") != 2:
        raise ZBatchError("系统消息中的第3章机械占位计数漂移")
    system = system.replace('"chapter": 3', f'"chapter": {chapter}', 1)
    system = system.replace("EV-C0003", f"EV-C{chapter:04d}")

    user = original_user
    user = _replace_once(user, NAME_HINT_BLOCK, "", "第3章专属命名提示")
    user = _replace_once(user, "当前章号：3", f"当前章号：{chapter}", "当前章号")
    original_filename = chapter_file(3).name
    user = _replace_once(
        user,
        f"当前章文件名：{original_filename}",
        f"当前章文件名：{chapter_file(chapter).name}",
        "当前章文件名",
    )
    user, old_text = replace_text_payload(user, source_text)
    user, old_catalog = replace_catalog_payload(user, catalog_payload)
    body = copy.deepcopy(original)
    body["messages"] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if {key: body[key] for key in body if key != "messages"} != {
        key: original[key] for key in original if key != "messages"
    }:
        raise ZBatchError(f"第{chapter}章实例化夹带采样参数变化")
    if NAME_HINT_BLOCK in user or "【本章命名提示】" in user:
        raise ZBatchError(f"第{chapter}章仍残留第3章专属命名提示")
    if extract_text_payload(user) != source_text:
        raise ZBatchError(f"第{chapter}章连续正文实例化不等于intake")
    if extract_catalog_payload(user) != catalog_payload:
        raise ZBatchError(f"第{chapter}章目录实例化不等于冻结目录")
    if request_has_prohibited_input(body):
        raise ZBatchError(f"第{chapter}章请求夹入禁入窗材料")
    return body, {
        "chapter": chapter,
        "mode": "mechanical_instantiation",
        "body_equal_original": False,
        "body_canonical_sha256": canonical_sha(body),
        "source_text_sha256": sha256_file(chapter_file(chapter)),
        "catalog_sha256": sha256_file(source_catalog(chapter)),
        "catalog_entries_sha256": canonical_sha(entries),
        "name_hint": "deleted_exact_chapter3_only_block",
        "allowed_changes": [
            {
                "field": "system.output_contract.chapter",
                "old": 3,
                "new": chapter,
                "occurrences": 1,
            },
            {
                "field": "system.output_contract.event_id_prefix",
                "old": "EV-C0003",
                "new": f"EV-C{chapter:04d}",
                "occurrences": 2,
            },
            {"field": "user.current_chapter", "old": 3, "new": chapter, "occurrences": 1},
            {
                "field": "user.current_filename",
                "old": original_filename,
                "new": chapter_file(chapter).name,
                "occurrences": 1,
            },
            {
                "field": "user.chapter_text",
                "old_sha256": sha256_bytes(old_text.encode("utf-8")),
                "new_sha256": sha256_bytes(source_text.encode("utf-8")),
            },
            {
                "field": "user.evidence_catalog",
                "old_sha256": sha256_bytes(old_catalog.encode("utf-8")),
                "new_sha256": sha256_bytes(catalog_payload.encode("utf-8")),
            },
            {"field": "user.chapter3_name_hint", "action": "deleted", "occurrences": 1},
        ],
        "unchanged_top_level_fields": sorted(EXPECTED_BODY_KEYS - {"messages"}),
    }


def load_bundle() -> stage_sampling.StageContractBundle:
    return stage_sampling.load_contract_bundle(SAMPLING_CONTRACT, profile="d_mod_cutover_v1")


def assert_body_matches_transport(body: Mapping[str, Any]) -> None:
    bundle = load_bundle()
    rebuilt = api_transport.build_request_body(
        model=str(bundle.route["model"]),
        messages=copy.deepcopy(body["messages"]),
        contract=bundle.stage("neutral_extract"),
    )
    if rebuilt != body:
        raise ZBatchError("修正版请求体不能由现役运输合同逐字段复现")


def prepare(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    run_dir.mkdir(parents=True)
    protected = assert_protected()
    outbox_before = tree_fingerprint(OUTBOX)
    input_rows: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        body, diff = build_instantiated_body(chapter)
        assert_body_matches_transport(body)
        target = run_dir / "prepared_requests" / f"ch{chapter:04d}.json"
        write_json(target, body)
        copied: list[dict[str, Any]] = []
        for source, destination in (
            (chapter_file(chapter), run_dir / "inputs/chapters" / chapter_file(chapter).name),
            (source_catalog(chapter), run_dir / "inputs/evidence_catalogs" / f"ch{chapter:04d}.json"),
            (source_events(chapter), run_dir / "inputs/baseline_events" / f"ch{chapter:04d}.json"),
        ):
            copied.append(copy_input(source, destination))
        input_rows.append(
            {
                **diff,
                "prepared_request": target.relative_to(run_dir).as_posix(),
                "prepared_request_sha256": sha256_file(target),
                "message_roles": [row["role"] for row in body["messages"]],
                "message_characters": [len(row["content"]) for row in body["messages"]],
                "prohibited_request_marker_hits": request_has_prohibited_input(body),
                "copied_inputs": copied,
            }
        )
    provenance = []
    for source, destination in (
        (ORIGINAL_REQUEST, run_dir / "provenance/original_revised_chapter3_request.json"),
        (Path(__file__), run_dir / "provenance/z68_revised_request_pilot.py"),
        (SAMPLING_CONTRACT, run_dir / "provenance/sensenova_stage_sampling_v1.json"),
        (PROVIDER_CONFIG, run_dir / "provenance/sensenova_modular_v1.json"),
        (SOURCE_RUN / "usage.jsonl", run_dir / "inputs/baseline_usage.jsonl"),
    ):
        provenance.append(copy_input(source, destination))
    preflight = {
        "schema_version": "z68-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": now_iso(),
        "task": "第68道修正版请求体裸考对照轮",
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "network_attempts": 0,
        "target_chapters": list(TARGET_CHAPTERS),
        "original_request": {
            "path": ORIGINAL_REQUEST.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(ORIGINAL_REQUEST),
            "chapter3_continuous_text_equal_intake": True,
            "chapter3_catalog_equal_frozen_catalog": True,
        },
        "request_policy": {
            "chapter3": "定稿原件body直接使用",
            "other_chapters": "只机械替换章号、文件名、连续正文、冻结目录，并删除第3章专属命名提示",
            "gold_in_request": False,
            "chatgpt_demo_in_request": False,
            "logical_samples_per_chapter": 1,
            "rerun_for_selection": False,
            "network_retry_slack": 2,
            "hard_stop_on_new_failure": True,
        },
        "sampling": {
            "model": "deepseek-v4-flash",
            "temperature": 0.2,
            "max_tokens": 16000,
            "n": 1,
            "response_format": {"type": "json_object"},
            "reasoning_effort": "medium",
        },
        "protected": protected,
        "outbox_before": outbox_before,
        "rows": input_rows,
        "provenance": provenance,
        "subject_lexicon": {str(chapter): list(SUBJECT_LEXICON[chapter]) for chapter in TARGET_CHAPTERS},
        "vague_predicate_terms": list(VAGUE_PREDICATE_TERMS),
    }
    write_json(run_dir / "preflight.json", preflight)
    write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z68-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "prepared",
            "model_api_calls": 0,
        },
    )
    verify_prepared(run_dir)
    return preflight


def verify_prepared(run_dir: Path) -> dict[str, Any]:
    preflight = read_json(run_dir / "preflight.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("第68道预演状态不是零调用通过")
    if (run_dir / "call_attempts.jsonl").exists():
        raise ZBatchError("零调用预演目录出现调用账")
    assert_protected()
    if tree_fingerprint(OUTBOX) != preflight["outbox_before"]:
        raise ZBatchError("预演期间outbox漂移")
    rows = {int(row["chapter"]): row for row in preflight["rows"]}
    checks: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        expected, diff = build_instantiated_body(chapter)
        observed_path = run_dir / "prepared_requests" / f"ch{chapter:04d}.json"
        observed = read_json(observed_path)
        checks.append(
            {
                "chapter": chapter,
                "body_equal_rebuild": observed == expected,
                "body_canonical_sha256": canonical_sha(observed),
                "diff_equal_rebuild": rows[chapter]["allowed_changes"] == diff["allowed_changes"],
                "prohibited_request_marker_hits": request_has_prohibited_input(observed),
            }
        )
        if not checks[-1]["body_equal_rebuild"] or not checks[-1]["diff_equal_rebuild"]:
            raise ZBatchError(f"第{chapter}章预备请求不能机械重建")
        if checks[-1]["prohibited_request_marker_hits"]:
            raise ZBatchError(f"第{chapter}章预备请求出现禁入窗材料")
        assert_body_matches_transport(observed)
    receipt = {
        "schema_version": "z68-prepared-request-verification-v1",
        "status": "pass",
        "model_api_calls": 0,
        "checks": checks,
        "preflight_sha256": sha256_file(run_dir / "preflight.json"),
    }
    write_json(run_dir / "prepared_request_verification.json", receipt)
    return receipt


def attempt_count(run_dir: Path) -> int:
    return len(read_jsonl(run_dir / "call_attempts.jsonl"))


def usage_summary(run_dir: Path) -> dict[str, Any]:
    rows = read_jsonl(run_dir / "usage.jsonl")
    totals: Counter[str] = Counter()
    reasoning_tokens = 0
    elapsed_ms = 0
    for row in rows:
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
        details = usage.get("completion_tokens_details")
        if isinstance(details, dict) and isinstance(details.get("reasoning_tokens"), int):
            reasoning_tokens += details["reasoning_tokens"]
        if isinstance(row.get("elapsed_ms"), int):
            elapsed_ms += row["elapsed_ms"]
    return {
        "network_attempts": attempt_count(run_dir),
        "successful_model_calls": len(rows),
        "prompt_tokens": totals["prompt_tokens"],
        "completion_tokens": totals["completion_tokens"],
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": totals["total_tokens"],
        "elapsed_ms": elapsed_ms,
        "finish_reasons": dict(Counter(str(row.get("finish_reason")) for row in rows)),
        "http_statuses": dict(Counter(str(row.get("http_status")) for row in rows)),
    }


def artifact_receipt(run_dir: Path, chapter: int) -> dict[str, Any]:
    case_id = f"ch{chapter:04d}"
    paths = {
        "request": run_dir / "requests/neutral_extract" / f"{case_id}_request.json",
        "raw_response": run_dir / "responses/neutral_extract" / f"{case_id}_raw.json",
        "response_meta": run_dir / "responses/neutral_extract" / f"{case_id}_meta.json",
        "model_json": run_dir / "01_extract/model_json" / f"{case_id}.json",
        "events": run_dir / "01_extract/events" / f"{case_id}.json",
        "program_audit": run_dir / "01_extract/program_audits" / f"{case_id}.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ZBatchError(f"第{chapter}章API工件不完整：{missing}")
    return {name + "_sha256": sha256_file(path) for name, path in paths.items()}


def run(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    verify_prepared(run_dir)
    if attempt_count(run_dir) != 0:
        raise ZBatchError("第68道已有调用账，拒绝复跑或补跑")
    preflight = read_json(run_dir / "preflight.json")
    assert_protected()
    if tree_fingerprint(OUTBOX) != preflight["outbox_before"]:
        raise ZBatchError("正式调用前outbox漂移")
    bundle = load_bundle()
    transport = api_transport.ApiTransport.from_bundle(bundle, run_dir=run_dir, max_calls=7)
    completed: list[int] = []
    receipts: dict[str, Any] = {}
    try:
        for chapter in TARGET_CHAPTERS:
            body = read_json(run_dir / "prepared_requests" / f"ch{chapter:04d}.json")
            assert_body_matches_transport(body)
            result = transport.call(
                stage="neutral_extract",
                case_id=f"ch{chapter:04d}",
                messages=body["messages"],
            )
            model_json = candidate_envelope.parse_json_content(result.content)
            catalog_doc = read_json(run_dir / "inputs/evidence_catalogs" / f"ch{chapter:04d}.json")
            materialized, audit = neutral_extract.process_model_data(
                model_json,
                chapter=chapter,
                catalog=catalog_doc["entries"],
            )
            model_path = run_dir / "01_extract/model_json" / f"ch{chapter:04d}.json"
            events_path = run_dir / "01_extract/events" / f"ch{chapter:04d}.json"
            audit_path = run_dir / "01_extract/program_audits" / f"ch{chapter:04d}.json"
            write_json(model_path, model_json)
            write_json(events_path, materialized)
            write_json(audit_path, audit)
            receipts[str(chapter)] = {
                **artifact_receipt(run_dir, chapter),
                "event_count": len(materialized["events"]),
                "anchor_reference_count": audit["anchor_reference_count"],
                "missing_catalog_anchor_ids": audit["missing_catalog_anchor_ids"],
            }
            completed.append(chapter)
    except Exception as exc:
        hard_stop = {
            "schema_version": "z68-hard-stop-v1",
            "status": "hard_stop_no_repair_no_rerun",
            "at": now_iso(),
            "completed_chapters": completed,
            "next_chapter": next((chapter for chapter in TARGET_CHAPTERS if chapter not in completed), None),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "usage": usage_summary(run_dir),
            "protected_after": assert_protected(),
            "outbox_unchanged": tree_fingerprint(OUTBOX) == preflight["outbox_before"],
        }
        write_json(run_dir / "hard_stop.json", hard_stop)
        write_json(
            run_dir / "run_manifest.json",
            {
                "schema_version": "z68-run-manifest-v1",
                "run_id": run_dir.name,
                "status": "hard_stop",
                "model_api_calls": hard_stop["usage"]["successful_model_calls"],
            },
        )
        raise
    metrics = {
        "schema_version": "z68-run-metrics-v1",
        "status": "completed_candidate_only",
        "target_chapters": list(TARGET_CHAPTERS),
        "chapters_completed": completed,
        "usage": usage_summary(run_dir),
        "receipts": receipts,
    }
    write_json(run_dir / "01_extract/metrics.json", metrics)
    write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z68-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "completed_candidate_only",
            "model_api_calls": metrics["usage"]["successful_model_calls"],
        },
    )
    return metrics


def raw_anchor_ids(event: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    anchors = event.get("anchors")
    if not isinstance(anchors, list):
        return result
    for anchor in anchors:
        if isinstance(anchor, dict) and isinstance(anchor.get("anchor_id"), str):
            result.append(anchor["anchor_id"])
    return result


def anchor_number(anchor_id: str) -> int | None:
    match = re.fullmatch(r"E(\d{4})", anchor_id)
    return int(match.group(1)) if match else None


def has_explicit_subject(event_text: str, chapter: int) -> tuple[bool, str | None]:
    candidate = event_text.strip()
    modifier = LEADING_MODIFIER.match(candidate)
    if modifier:
        candidate = candidate[modifier.end() :].lstrip()
    for subject in sorted(SUBJECT_LEXICON[chapter], key=len, reverse=True):
        if candidate.startswith(subject):
            return True, subject
    return False, None


def vague_hits(event_text: str) -> list[str]:
    return [term for term in VAGUE_PREDICATE_TERMS if term in event_text]


def chapter_mechanics(run_dir: Path, chapter: int) -> dict[str, Any]:
    model_doc = read_json(run_dir / "01_extract/model_json" / f"ch{chapter:04d}.json")
    events_doc = read_json(run_dir / "01_extract/events" / f"ch{chapter:04d}.json")
    catalog_doc = read_json(run_dir / "inputs/evidence_catalogs" / f"ch{chapter:04d}.json")
    catalog_ids = {row["anchor_id"] for row in catalog_doc["entries"]}
    raw_events = model_doc.get("events") if isinstance(model_doc, dict) else []
    if not isinstance(raw_events, list):
        raw_events = []
    rows: list[dict[str, Any]] = []
    invalid = 0
    anchor_refs = 0
    ordered = 0
    deduplicated = 0
    explicit = 0
    vague_count = 0
    for index, event in enumerate(events_doc["events"]):
        raw_event = raw_events[index] if index < len(raw_events) and isinstance(raw_events[index], dict) else {}
        anchor_ids = raw_anchor_ids(raw_event)
        numbers = [anchor_number(value) for value in anchor_ids]
        invalid_ids = [value for value in anchor_ids if value not in catalog_ids]
        anchor_refs += len(anchor_ids)
        invalid += len(invalid_ids)
        order_ok = all(value is not None for value in numbers) and numbers == sorted(numbers)
        dedup_ok = len(anchor_ids) == len(set(anchor_ids))
        subject_ok, subject = has_explicit_subject(event["event"], chapter)
        hits = vague_hits(event["event"])
        ordered += int(order_ok)
        deduplicated += int(dedup_ok)
        explicit += int(subject_ok)
        vague_count += int(bool(hits))
        rows.append(
            {
                "event_id": event["event_id"],
                "event": event["event"],
                "anchor_ids": anchor_ids,
                "invalid_anchor_ids": invalid_ids,
                "anchor_order_ok": order_ok,
                "anchor_deduplicated": dedup_ok,
                "explicit_subject_lexical": subject_ok,
                "matched_subject": subject,
                "vague_predicate_hits": hits,
            }
        )
    count = len(rows)
    return {
        "chapter": chapter,
        "json_valid": True,
        "event_id_contiguous": read_json(
            run_dir / "01_extract/program_audits" / f"ch{chapter:04d}.json"
        )["event_ids_contiguous"],
        "event_count": count,
        "anchor_reference_count": anchor_refs,
        "outside_catalog_anchor_count": invalid,
        "invalid_anchor_rate": invalid / anchor_refs if anchor_refs else 0.0,
        "anchor_order_compliant_events": ordered,
        "anchor_order_compliance_rate": ordered / count if count else 0.0,
        "anchor_deduplicated_events": deduplicated,
        "anchor_deduplication_rate": deduplicated / count if count else 0.0,
        "explicit_subject_events": explicit,
        "explicit_subject_rate": explicit / count if count else 0.0,
        "vague_predicate_hit_events": vague_count,
        "vague_predicate_hit_rate": vague_count / count if count else 0.0,
        "rows": rows,
    }


def usage_for_chapters(path: Path, chapters: tuple[int, ...]) -> dict[str, Any]:
    wanted = {f"ch{chapter:04d}" for chapter in chapters}
    rows = [row for row in read_jsonl(path) if row.get("case_id") in wanted]
    totals: Counter[str] = Counter()
    per_chapter: dict[str, Any] = {}
    for row in rows:
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        details = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), dict) else {}
        item = {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
            "elapsed_ms": int(row.get("elapsed_ms") or 0),
        }
        per_chapter[str(int(str(row["case_id"])[2:]))] = item
        totals.update(item)
    return {"chapters": per_chapter, "totals": dict(totals), "successful_calls": len(rows)}


def candidate_usage(run_dir: Path) -> dict[str, Any]:
    return usage_for_chapters(run_dir / "usage.jsonl", TARGET_CHAPTERS)


def analyze(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    manifest = read_json(run_dir / "run_manifest.json")
    if manifest.get("status") != "completed_candidate_only":
        raise ZBatchError("第68道五章未完整完成，禁止冒充正式成绩")
    preflight = read_json(run_dir / "preflight.json")
    protected_after = assert_protected()
    outbox_after = tree_fingerprint(OUTBOX)
    if outbox_after != preflight["outbox_before"]:
        raise ZBatchError("第68道分析时outbox漂移")

    chapter_rows = [chapter_mechanics(run_dir, chapter) for chapter in TARGET_CHAPTERS]
    event_total = sum(row["event_count"] for row in chapter_rows)
    anchor_total = sum(row["anchor_reference_count"] for row in chapter_rows)
    outside_total = sum(row["outside_catalog_anchor_count"] for row in chapter_rows)
    explicit_total = sum(row["explicit_subject_events"] for row in chapter_rows)
    vague_total = sum(row["vague_predicate_hit_events"] for row in chapter_rows)
    ordered_total = sum(row["anchor_order_compliant_events"] for row in chapter_rows)
    dedup_total = sum(row["anchor_deduplicated_events"] for row in chapter_rows)
    baseline_events = {
        str(chapter): len(read_json(run_dir / "inputs/baseline_events" / f"ch{chapter:04d}.json")["events"])
        for chapter in TARGET_CHAPTERS
    }
    candidate_events = {str(row["chapter"]): row["event_count"] for row in chapter_rows}
    base_usage = usage_for_chapters(run_dir / "inputs/baseline_usage.jsonl", TARGET_CHAPTERS)
    new_usage = candidate_usage(run_dir)
    baseline_total_tokens = int(base_usage["totals"].get("total_tokens") or 0)
    candidate_total_tokens = int(new_usage["totals"].get("total_tokens") or 0)
    scorecard = {
        "schema_version": "z68-ten-mechanical-metrics-v1",
        "status": "completed_candidate_only",
        "condition": "连续正文＋目录双视图",
        "metric_policy": {
            "explicit_subject": "去掉一个不超过30字的前置时间／条件短语后，事件句必须以预写人物或明确群体词表开头",
            "vague_predicate": "只作词面命中观察，不自动判错；问题一词可能是合格的明确未解问题",
            "invalid_anchor": "模型原始anchor_id不在同章冻结目录的引用数／全部引用数",
        },
        "ten_metrics": {
            "01_JSON合法章率": {"numerator": 5, "denominator": 5, "rate": 1.0},
            "02_event_id连续章率": {
                "numerator": sum(int(row["event_id_contiguous"]) for row in chapter_rows),
                "denominator": 5,
                "rate": sum(int(row["event_id_contiguous"]) for row in chapter_rows) / 5,
            },
            "03_目录外锚数": outside_total,
            "04_无效锚率": outside_total / anchor_total if anchor_total else 0.0,
            "05_锚排序合规率": ordered_total / event_total if event_total else 0.0,
            "06_锚去重合规率": dedup_total / event_total if event_total else 0.0,
            "07_显式主语率": explicit_total / event_total if event_total else 0.0,
            "08_空泛谓词命中率": vague_total / event_total if event_total else 0.0,
            "09_事件数": {
                "candidate_total": event_total,
                "baseline_total": sum(baseline_events.values()),
                "candidate_by_chapter": candidate_events,
                "baseline_by_chapter": baseline_events,
            },
            "10_token成本对第57道": {
                "candidate": new_usage,
                "baseline_reused_from_z56_z57": base_usage,
                "total_token_delta": candidate_total_tokens - baseline_total_tokens,
                "total_token_delta_rate": (
                    (candidate_total_tokens - baseline_total_tokens) / baseline_total_tokens
                    if baseline_total_tokens
                    else None
                ),
            },
        },
        "subject_lexicon": {str(chapter): list(SUBJECT_LEXICON[chapter]) for chapter in TARGET_CHAPTERS},
        "vague_predicate_terms": list(VAGUE_PREDICATE_TERMS),
        "chapters": chapter_rows,
    }
    write_json(run_dir / "analysis/机械十项成绩单.json", scorecard)

    diffs: dict[str, Any] = {}
    for chapter in TARGET_CHAPTERS:
        baseline = read_json(run_dir / "inputs/baseline_events" / f"ch{chapter:04d}.json")["events"]
        candidate = read_json(run_dir / "01_extract/events" / f"ch{chapter:04d}.json")["events"]
        draft = z59.match_events(baseline, candidate)
        draft["chapter"] = chapter
        diffs[str(chapter)] = draft
    diff_report = {
        "schema_version": "z68-old-event-semantic-diff-draft-v1",
        "status": "mechanical_pairing_requires_row_level_semantic_review",
        "warning": "配对只按锚交集和文本相似度起草；不得把本件当语义审收结论。",
        "chapters": diffs,
    }
    write_json(run_dir / "analysis/旧事件逐条diff_机械配对草稿.json", diff_report)

    chapter3_events = read_json(run_dir / "01_extract/events/ch0003.json")["events"]
    lexical_score = z59.score_chapter3(chapter3_events)
    lexical_score["schema_version"] = "z68-chapter3-gold-lexical-precheck-v1"
    lexical_score["condition"] = "连续正文＋目录双视图"
    lexical_score["status"] = "lexical_precheck_not_semantic_verdict"
    lexical_score["warning"] = "严格与影子最终分数必须经14条逐条语义复核；本表不自动定胜负。"
    write_json(run_dir / "analysis/第3章金标词法预检.json", lexical_score)
    referenced_candidate_ids = {
        row["candidate_event_id_run_local_only"]
        for row in lexical_score["rows"]
        if row.get("candidate_event_id_run_local_only")
    }
    overflow = {
        "schema_version": "z68-overflow-draft-v1",
        "status": "pending_adjudication_do_not_self_label",
        "policy": "只列未被词法预检任何金标行引用的候选事件；是否合理溢出由CZ另判。",
        "events": [row for row in chapter3_events if row["event_id"] not in referenced_candidate_ids],
    }
    write_json(run_dir / "analysis/第3章待判溢出_机械草稿.json", overflow)
    summary = {
        "schema_version": "z68-analysis-draft-summary-v1",
        "status": "mechanical_complete_semantic_review_pending",
        "scorecard_sha256": sha256_file(run_dir / "analysis/机械十项成绩单.json"),
        "old_event_diff_draft_sha256": sha256_file(run_dir / "analysis/旧事件逐条diff_机械配对草稿.json"),
        "chapter3_lexical_precheck_sha256": sha256_file(run_dir / "analysis/第3章金标词法预检.json"),
        "overflow_draft_sha256": sha256_file(run_dir / "analysis/第3章待判溢出_机械草稿.json"),
        "protected_after": protected_after,
        "outbox_after": outbox_after,
    }
    write_json(run_dir / "analysis/机械分析汇总.json", summary)
    return summary


def verify(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    prepared = verify_prepared(run_dir)
    manifest = read_json(run_dir / "run_manifest.json")
    checks: list[dict[str, Any]] = []
    checks.append({"name": "prepared_requests", "passed": prepared["status"] == "pass"})
    checks.append({"name": "protected", "passed": bool(assert_protected())})
    preflight = read_json(run_dir / "preflight.json")
    checks.append({"name": "outbox_unchanged", "passed": tree_fingerprint(OUTBOX) == preflight["outbox_before"]})
    if manifest.get("status") == "completed_candidate_only":
        for chapter in TARGET_CHAPTERS:
            receipt = artifact_receipt(run_dir, chapter)
            checks.append({"name": f"chapter_{chapter}_artifacts", "passed": bool(receipt)})
        for path in (
            run_dir / "analysis/机械十项成绩单.json",
            run_dir / "analysis/旧事件逐条diff_机械配对草稿.json",
            run_dir / "analysis/第3章金标词法预检.json",
            run_dir / "analysis/第3章待判溢出_机械草稿.json",
            run_dir / "analysis/机械分析汇总.json",
        ):
            checks.append({"name": path.name, "passed": path.is_file(), "sha256": sha256_file(path) if path.is_file() else None})
    failed = [row for row in checks if not row["passed"]]
    if failed:
        raise ZBatchError(f"第68道机械验收失败：{failed}")
    receipt = {
        "schema_version": "z68-mechanical-verification-v1",
        "status": "pass",
        "run_status": manifest.get("status"),
        "checks": checks,
        "usage": usage_summary(run_dir),
    }
    write_json(run_dir / "mechanical_verification.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "analyze", "verify"))
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args(argv)
    actions = {
        "prepare": prepare,
        "run": run,
        "analyze": analyze,
        "verify": verify,
    }
    result = actions[args.action](args.run_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

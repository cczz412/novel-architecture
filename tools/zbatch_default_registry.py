#!/usr/bin/env python3
"""第36道批准后的 v1.2 默认链登记与 outbox 打包器。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

from zbatch_modules import classify_rules as modular_classify_rules


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = "config/defaults/zbatch_v1.2_full_chain.json"
COMMIT_MARKER = "config/defaults/zbatch_v1.2_full_chain.COMMITTED.json"
EXPECTED_DEFAULT_ID = "zbatch-v1.2-full-chain"
EXPECTED_RUN_ID = "Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719"
EXPECTED_PRODUCT_PATH = f"runs/{EXPECTED_RUN_ID}/02_verify/valid_records.json"
EXPECTED_RUN_MANIFEST_PATH = f"runs/{EXPECTED_RUN_ID}/run_manifest.json"
EXPECTED_MECHANICAL_REVIEW_PATH = f"runs/{EXPECTED_RUN_ID}/07_review/mechanical_review.json"
EXPECTED_TEAM_ATTESTATION_PATH = f"runs/{EXPECTED_RUN_ID}/07_review/semantic_attestation.json"
EXPECTED_LUNA_REVIEW_PATH = f"runs/{EXPECTED_RUN_ID}/07_review/Luna第一停点复核.md"
EXPECTED_Z00Y3_AUDIT_PATH = "work/zbatch_audits/Z00y3_new_four_semantic_audit_v1.json"
EXPECTED_TEST_RECEIPT_PATH = "reports/Z36_E0130补锚与v1.2默认升版_20260719/第36道_默认登记器全套测试回执.txt"
MIN_PRE_PROMOTION_TESTS = 240
EXPECTED_CHAIN_PATHS = {
    "runner": "tools/zbatch.py",
    "provider": "config/providers/sensenova_modular_v1.json",
    "stage_sampling_contract": "config/contracts/sensenova_stage_sampling_v1.json",
    "neutral_extract_module": "tools/zbatch_modules/neutral_extract.py",
    "neutral_extract_prompt": "work/zbatch_prompts/candidates/extract_event_only_no_self_audit_v1.1.md",
    "classify_rules_module": "tools/zbatch_modules/classify_rules.py",
    "classify_contract": "config/contracts/classify_rules_v1.2.json",
    "classification_prompt": "work/zbatch_prompts/candidates/main_control_classification_rules_v1.2.md",
    "classification_decisions": "work/zbatch_decisions/Z36_X01_ch1_20_main_control_decisions_v1.2.json",
}
Z57_CLASSIFY_CONTRACT_PATH = "config/contracts/classify_rules_v1.2_semantic_identity_v1.json"
Z57_COMPATIBILITY_SCHEMA = "zbatch-default-compatibility-revision-v1"
Z57_REVISION_ID = "Z57-stable-semantic-identity-v1"
Z57_AUTHORITY = "第57道；CZ 2026-07-19 19:41拍a"
Z57_PREDECESSOR_DEFAULT_SHA256 = "61bc6ca45fe450d382995b29dd998c9119ade2db6049d29963c83eee30c5f9da"
Z57_PREDECESSOR_COMMIT_SHA256 = "9259d3958e97aed982a798545ae889e3c608a3c8ef12dad87ea9f18f9cdddc48"
Z57_OLD_CONTRACT_SHA256 = "ad2ccc3b13e8b138a32a46b8566e928a3c4e35a60cf31c5494c7b9ba3dd021de"
Z57_NEW_CONTRACT_SHA256 = "45f7610b86d5962e0d3d9d4d95886aad9022f1beaece200c2452b9a361f6c108"
Z57_CLASSIFY_MODULE_SHA256 = "eed588211111f89f5c6968c490686124bf94e7cd09d65aee3f1bc02dd9011104"
Z57_RUNNER_SHA256 = "160c28b3ef0210fd05c392f713534cf1ffdf041fa596ec790545b64955280850"
Z57_FORMAL_DECISIONS_PATH = "work/zbatch_decisions/Z57_X01_ch1_20_main_control_decisions_v1.2.json"
Z57_FORMAL_DECISIONS_SHA256 = "ba856a487e6fcc416c83b05a0b9e6c458ea85f5d8a7e23354f8c2865b8e97650"
Z57_SOURCE_EXTRACT_PATH = "runs/Z56b_X01_端到端全链体检_提取20章_v1.0_20260719/01_extract"
Z57_OUTBOX_MANIFEST_PATH = "outbox/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/manifest.json"
Z57_OUTBOX_MANIFEST_SHA256 = "aecfcf93a265fa5f9f61ee7003bf8f7118833a12b8e2a0ffcc4899631cec6aa2"
Z57_OLD_DEFAULT_ARCHIVE = f"config/defaults/history/zbatch_v1.2_full_chain_{Z57_PREDECESSOR_DEFAULT_SHA256}.json"
Z57_OLD_COMMIT_ARCHIVE = f"config/defaults/history/zbatch_v1.2_full_chain.COMMITTED_{Z57_PREDECESSOR_COMMIT_SHA256}.json"
Z57_OLD_RUNNER_PIN = "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/provenance/runner_zbatch.py"
Z57_OLD_RUNNER_SHA256 = "4090169dd53a71badd21d42d3c1c1e8809bd54ac46f461ab3e33137e94c3ca11"
Z57_OLD_MODULE_PIN = "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/provenance/pinned/tools/zbatch_modules/classify_rules.py"
Z57_OLD_MODULE_SHA256 = "76b3c1e208abaf0ab47c8dafee4c4e1ccb7d6d4cb3d364fc30afa00c6179eb7b"
EXPECTED_PROGRAM_PATHS = [
    "tools/zbatch_modules/evidence_catalog.py",
    "tools/zbatch_modules/anchor_kit.py",
    "tools/zbatch_modules/candidate_envelope.py",
    "tools/zbatch_modules/prompt_render_pin.py",
    "tools/zbatch_modules/downstream_validate.py",
    "tools/zbatch_modules/api_transport.py",
    "tools/zbatch_modules/stage_sampling.py",
    "tools/zbatch_modules/neutral_extract.py",
    "tools/zbatch_modules/classify_rules.py",
]


class DefaultRegistryError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def root_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise DefaultRegistryError(f"路径越出仓库：{resolved}") from exc
    return resolved


def relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DefaultRegistryError(f"JSON读取失败：{path}：{exc}") from exc
    if not isinstance(data, dict):
        raise DefaultRegistryError(f"JSON顶层不是对象：{path}")
    return data


def json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def write_json_atomic(path: Path, data: Any) -> None:
    write_bytes_atomic(path, json_bytes(data))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_pins(root: Path, pins: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(pins, dict) or not pins:
        raise DefaultRegistryError("升版计划缺完整工件SHA清单")
    checked: list[dict[str, Any]] = []
    for value, expected in pins.items():
        path = root_path(root, value)
        if not path.is_file():
            raise DefaultRegistryError(f"钉死工件不存在：{value}")
        actual = sha256_file(path)
        if actual != expected:
            raise DefaultRegistryError(f"钉死工件SHA漂移：{value}")
        checked.append({"path": value, "sha256": actual, "bytes": path.stat().st_size})
    return checked


def validate_ref(reference: Any, expected_path: str, pins: dict[str, Any]) -> None:
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise DefaultRegistryError(f"工件引用格式不合法：{expected_path}")
    if reference.get("path") != expected_path:
        raise DefaultRegistryError(f"工件引用路径错位：{expected_path}")
    if pins.get(expected_path) != reference.get("sha256"):
        raise DefaultRegistryError(f"工件引用未绑定SHA清单：{expected_path}")


def validate_chain(plan: dict[str, Any], pins: dict[str, Any] | None = None) -> None:
    chain = plan.get("chain")
    if not isinstance(chain, dict):
        raise DefaultRegistryError("升版计划缺默认链")
    required = {
        "runner",
        "provider",
        "stage_sampling_contract",
        "neutral_extract_module",
        "neutral_extract_prompt",
        "classify_rules_module",
        "classify_contract",
        "classification_prompt",
        "classification_decisions",
        "program_inventory",
        "transport",
    }
    if set(chain) != required:
        raise DefaultRegistryError(f"默认链字段不完整：{sorted(set(chain) ^ required)}")
    transport = chain.get("transport") or {}
    expected_transport = {
        "model": "deepseek-v4-flash",
        "profile": "d_mod_cutover_v1",
        "neutral_extract": {
            "temperature": 0.2,
            "max_tokens": 16000,
            "n": 1,
            "reasoning_effort": "medium",
        },
    }
    if transport != expected_transport:
        raise DefaultRegistryError("默认链运输参数不是已拍 v1.2 口径")
    pins = pins or {}
    for name, expected_path in EXPECTED_CHAIN_PATHS.items():
        validate_ref(chain.get(name), expected_path, pins)
    inventory = chain.get("program_inventory")
    if not isinstance(inventory, list) or [row.get("path") for row in inventory if isinstance(row, dict)] != EXPECTED_PROGRAM_PATHS:
        raise DefaultRegistryError("默认链程序清单路径或顺序不完整")
    for row, expected_path in zip(inventory, EXPECTED_PROGRAM_PATHS, strict=True):
        validate_ref(row, expected_path, pins)


def validate_product(product: dict[str, Any]) -> None:
    records = product.get("records")
    if not isinstance(records, list) or len(records) != 122:
        raise DefaultRegistryError("得判件不是122条正式产品")
    matches = [row for row in records if row.get("id") == "D-C0013-02"]
    if len(matches) != 1:
        raise DefaultRegistryError("得判件缺唯一 D-C0013-02")
    anchor_ids = [row.get("anchor_id") for row in matches[0].get("anchors") or []]
    if anchor_ids != ["E0129", "E0130"]:
        raise DefaultRegistryError("D-C0013-02 没有按拍板登记 E0129＋E0130")


def validate_package_entries(root: Path, plan: dict[str, Any], pins: dict[str, Any]) -> None:
    report_entries = plan.get("report_entries")
    audit_entries = plan.get("audit_entries")
    for name, entries in (("report_entries", report_entries), ("audit_entries", audit_entries)):
        if not isinstance(entries, list) or not entries or len(entries) != len(set(entries)):
            raise DefaultRegistryError(f"{name}为空、重复或不是数组")
        for value in entries:
            if not isinstance(value, str):
                raise DefaultRegistryError(f"{name}含非字符串路径")
            path = root_path(root, value)
            if relative(root, path) != value:
                raise DefaultRegistryError(f"{name}含不规范仓内路径：{value}")
            if value not in pins:
                raise DefaultRegistryError(f"{name}含未钉SHA工件：{value}")
    if not set(report_entries).issubset(set(audit_entries)):
        raise DefaultRegistryError("报告包工件没有全部进入审计包")
    if set(audit_entries) != set(pins):
        raise DefaultRegistryError("审计包清单与完整SHA清单不是同一集合")


def validate_test_receipt(root: Path, plan: dict[str, Any], pins: dict[str, Any]) -> None:
    if EXPECTED_TEST_RECEIPT_PATH not in pins:
        raise DefaultRegistryError("默认登记写前测试回执未钉SHA")
    receipt_path = root_path(root, EXPECTED_TEST_RECEIPT_PATH)
    text = receipt_path.read_text(encoding="utf-8")
    match = re.search(r"Ran (\d+) tests", text)
    actual = int(match.group(1)) if match else 0
    declared = plan.get("pre_promotion_tests")
    if declared != {"total": actual, "passed": True}:
        raise DefaultRegistryError("写前测试声明与回执不一致")
    if actual < MIN_PRE_PROMOTION_TESTS or "OK" not in text:
        raise DefaultRegistryError("默认登记写前全套测试未达当前下限")


def validate_team_attestation(
    root: Path,
    team: dict[str, Any],
    *,
    mechanical_sha256: str,
) -> None:
    expected = {
        "run_id": EXPECTED_RUN_ID,
        "reviewer": "Luna-High-6",
        "review_task": "/root/step1_coverage_review",
        "decision": "pass",
        "p0": 0,
        "p1": 0,
        "p2": 0,
        "mechanical_review_sha256": mechanical_sha256,
    }
    for key, value in expected.items():
        if team.get(key) != value:
            raise DefaultRegistryError(f"团队签收字段不符：{key}")
    review_file = root_path(root, str(team.get("review_file") or ""))
    if relative(root, review_file) != EXPECTED_LUNA_REVIEW_PATH:
        raise DefaultRegistryError("团队复核正文路径不符")
    if sha256_file(review_file) != team.get("review_file_sha256"):
        raise DefaultRegistryError("团队复核正文SHA漂移")
    review_text = review_file.read_text(encoding="utf-8")
    required_lines = [
        "- 结论：PASS。",
        "- P0：0；P1：0；P2：0。",
        "复核者：Luna-High-6（`/root/step1_coverage_review`）",
    ]
    if any(value not in review_text for value in required_lines):
        raise DefaultRegistryError("团队签收JSON与Luna复核正文不一致")


def validate_plan(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("schema_version") != "zbatch-default-promotion-plan-v1":
        raise DefaultRegistryError("升版计划schema不符")
    if plan.get("default_id") != EXPECTED_DEFAULT_ID:
        raise DefaultRegistryError("升版计划default_id不符")
    if plan.get("run_id") != EXPECTED_RUN_ID:
        raise DefaultRegistryError("升版计划run_id不符")
    if plan.get("default_path") != DEFAULT_REGISTRY:
        raise DefaultRegistryError("默认登记路径不符")
    if plan.get("outbox_path") != f"outbox/{EXPECTED_RUN_ID}":
        raise DefaultRegistryError("outbox目标路径不符")
    if plan.get("authority") != "第44道重发第36道施工令；CZ已拍v1.2全链升默认并首次解锁outbox":
        raise DefaultRegistryError("升版权源不符")
    pins = plan.get("artifact_sha256") or {}
    checked = validate_pins(root, pins)
    validate_package_entries(root, plan, pins)
    validate_test_receipt(root, plan, pins)
    validate_chain(plan, pins)

    mechanical_ref = plan.get("mechanical_review") or {}
    team_ref = plan.get("team_attestation") or {}
    validate_ref(mechanical_ref, EXPECTED_MECHANICAL_REVIEW_PATH, pins)
    validate_ref(team_ref, EXPECTED_TEAM_ATTESTATION_PATH, pins)
    mechanical_path = root_path(root, str(mechanical_ref.get("path") or ""))
    team_path = root_path(root, str(team_ref.get("path") or ""))
    if sha256_file(mechanical_path) != mechanical_ref.get("sha256"):
        raise DefaultRegistryError("机械闸SHA漂移")
    if sha256_file(team_path) != team_ref.get("sha256"):
        raise DefaultRegistryError("团队签收SHA漂移")
    mechanical = read_json(mechanical_path)
    team = read_json(team_path)
    if mechanical.get("mechanical_pass") is not True:
        raise DefaultRegistryError("机械闸未通过")
    if mechanical.get("default_ready") is not False or mechanical.get("outbox_ready") is not False:
        raise DefaultRegistryError("机械停点边界被改写")
    validate_team_attestation(root, team, mechanical_sha256=sha256_file(mechanical_path))

    run_manifest_ref = plan.get("run_manifest") or {}
    validate_ref(run_manifest_ref, EXPECTED_RUN_MANIFEST_PATH, pins)
    run_manifest = read_json(root_path(root, run_manifest_ref["path"]))
    if run_manifest.get("calls_made") != 0 or run_manifest.get("status") != "completed":
        raise DefaultRegistryError("第36道不是零调用完整运行")
    product_ref = plan.get("product") or {}
    validate_ref(product_ref, EXPECTED_PRODUCT_PATH, pins)
    product = read_json(root_path(root, product_ref["path"]))
    validate_product(product)
    historical = plan.get("historical_reference") or {}
    if historical.get("name") != "extract_v1.3" or historical.get("status") != "historical_reference_not_default":
        raise DefaultRegistryError("extract_v1.3 历史参照边界不符")
    validate_ref(
        {"path": historical.get("path"), "sha256": historical.get("sha256")},
        "work/zbatch_prompts/extract_v1.3.md",
        pins,
    )
    adjudication = plan.get("source_adjudication") or {}
    audit_ref = adjudication.get("z00y3_audit") or {}
    validate_ref(audit_ref, EXPECTED_Z00Y3_AUDIT_PATH, pins)
    return {
        "checked_artifacts": checked,
        "mechanical_review": mechanical,
        "team_attestation": team,
        "product_record_total": 122,
    }


def default_manifest(plan: dict[str, Any], *, promoted_at: str) -> dict[str, Any]:
    product = plan["product"]
    return {
        "schema_version": "zbatch-default-registry-v1",
        "default_id": plan["default_id"],
        "status": "active",
        "version": "v1.2",
        "promoted_at": promoted_at,
        "authority": plan["authority"],
        "source_adjudication": plan["source_adjudication"],
        "promotion_run_id": plan["run_id"],
        "chain": plan["chain"],
        "adjudicated_product": {
            "path": product["path"],
            "sha256": product["sha256"],
            "records": 122,
            "patch": "D-C0013-02保留E0129并补入E0130",
        },
        "historical_reference": plan["historical_reference"],
        "outbox": {
            "path": plan["outbox_path"],
            "status": "unlocked_and_written_when_commit_marker_matches",
        },
        "activation": {
            "requires_commit_marker": COMMIT_MARKER,
            "rule": "默认登记与outbox只有在提交标记同时绑定两者SHA时生效。",
        },
        "red_lines": {
            "z01d_z01f_promoted": False,
            "twenty_chapter_experiment_expanded": False,
            "classification_rules_changed": False,
            "old_runs_rewritten": False,
        },
    }


def zip_entries(zip_path: Path, root: Path, entries: list[str], extra: dict[str, bytes]) -> dict[str, Any]:
    seen: set[str] = set()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for value in entries:
            path = root_path(root, value)
            if not path.is_file():
                raise DefaultRegistryError(f"打包工件不存在：{value}")
            arcname = f"files/{relative(root, path)}"
            if arcname in seen:
                raise DefaultRegistryError(f"打包条目重复：{arcname}")
            seen.add(arcname)
            archive.write(path, arcname)
        for arcname, data in extra.items():
            if arcname in seen:
                raise DefaultRegistryError(f"打包条目重复：{arcname}")
            seen.add(arcname)
            archive.writestr(arcname, data)
    with zipfile.ZipFile(zip_path, "r") as archive:
        bad = archive.testzip()
        if bad is not None:
            raise DefaultRegistryError(f"ZIP自检失败：{bad}")
        names = archive.namelist()
    return {
        "path": str(zip_path.name),
        "bytes": zip_path.stat().st_size,
        "sha256": sha256_file(zip_path),
        "zip_test": "ok",
        "entries": len(names),
    }


def promotion_report(plan: dict[str, Any], manifest_sha256: str) -> bytes:
    text = f"""# 第36道回包｜E0130补锚与v1.2默认升版

- E0130 已进入正式产品：`D-C0013-02` 现有 E0129＋E0130。
- 正式产品：122/122 核锚通过；其余 121 条与旧产品逐字不变。
- 模型调用：0；产品停点测试 224/224，默认登记写前全套测试 {plan['pre_promotion_tests']['total']}/{plan['pre_promotion_tests']['total']}；Luna 复核 P0/P1/P2 均为0。
- v1.2 全链已登记为当前默认；运行器、模块、Prompt、规则、决定单和运输参数均有 SHA 钉死。
- outbox 已按第36道首次解锁并写入本次得判件、审计包和全量 SHA 清单。
- 默认登记候选内容 SHA：`{manifest_sha256}`。
- 边界：本次升默认只对应第36道已拍 v1.2 全链；Z01d／Z01f 仍是失败候选，未扩20章、未改分类规则、未回写旧运行。

来源：Codex
"""
    return text.encode("utf-8")


def rollback_uncommitted(
    root: Path,
    *,
    default_path: Path,
    outbox_path: Path,
    commit_path: Path,
) -> None:
    expected_default = root_path(root, DEFAULT_REGISTRY)
    expected_outbox = root_path(root, f"outbox/{EXPECTED_RUN_ID}")
    expected_commit = root_path(root, COMMIT_MARKER)
    actual_targets = tuple(path.resolve() for path in (default_path, outbox_path, commit_path))
    expected_targets = tuple(path.resolve() for path in (expected_default, expected_outbox, expected_commit))
    if actual_targets != expected_targets:
        raise DefaultRegistryError("回滚目标不是第36道固定路径")
    if commit_path.exists():
        commit_path.unlink()
    if default_path.exists():
        existing_default = read_json(default_path)
        if existing_default.get("default_id") != EXPECTED_DEFAULT_ID or existing_default.get("promotion_run_id") != EXPECTED_RUN_ID:
            raise DefaultRegistryError("未提交默认件身份不符，拒绝自动清理")
        default_path.unlink()
    if outbox_path.exists():
        manifest_path = outbox_path / "manifest.json"
        if not manifest_path.is_file() or read_json(manifest_path).get("run_id") != EXPECTED_RUN_ID:
            raise DefaultRegistryError("未提交outbox身份不符，拒绝自动清理")
        shutil.rmtree(outbox_path)


def recover_uncommitted(root: Path, default_path: Path, outbox_path: Path, commit_path: Path) -> None:
    if commit_path.exists():
        return
    if default_path.exists() or outbox_path.exists():
        rollback_uncommitted(
            root,
            default_path=default_path,
            outbox_path=outbox_path,
            commit_path=commit_path,
        )


def commit_promotion(
    root: Path,
    *,
    staged_outbox: Path,
    outbox_path: Path,
    default_path: Path,
    default_bytes: bytes,
    commit_path: Path,
    commit_document: dict[str, Any],
    post_commit_verify: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    try:
        outbox_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_outbox, outbox_path)
        write_bytes_atomic(default_path, default_bytes)
        write_json_atomic(commit_path, commit_document)
        return post_commit_verify()
    except Exception:
        rollback_uncommitted(
            root,
            default_path=default_path,
            outbox_path=outbox_path,
            commit_path=commit_path,
        )
        raise


def promote(root: Path, plan_path: Path) -> dict[str, Any]:
    root = root.resolve()
    plan = read_json(plan_path)
    validation = validate_plan(root, plan)
    default_path = root_path(root, plan["default_path"])
    outbox_path = root_path(root, plan["outbox_path"])
    commit_path = root_path(root, COMMIT_MARKER)
    if commit_path.exists():
        raise DefaultRegistryError("第36道提交标记已存在，拒绝覆盖已生效默认")
    recover_uncommitted(root, default_path, outbox_path, commit_path)

    promoted_at = now_iso()
    manifest = default_manifest(plan, promoted_at=promoted_at)
    manifest_bytes = json_bytes(manifest)
    manifest_sha = sha256_bytes(manifest_bytes)
    report_bytes = promotion_report(plan, manifest_sha)
    temp_parent = root / "TEMP"
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="z36_promotion_", dir=temp_parent) as temporary:
        stage = Path(temporary)
        staged_outbox = stage / EXPECTED_RUN_ID
        staged_outbox.mkdir()
        report_zip = staged_outbox / f"{EXPECTED_RUN_ID}_report.zip"
        audit_zip = staged_outbox / f"{EXPECTED_RUN_ID}_audit.zip"
        extra = {
            "default/zbatch_v1.2_full_chain.json": manifest_bytes,
            "第36道回包正文.md": report_bytes,
        }
        report_package = zip_entries(report_zip, root, plan["report_entries"], extra)
        audit_package = zip_entries(audit_zip, root, plan["audit_entries"], extra)
        outbox_manifest = {
            "schema_version": "z36-outbox-manifest-v1",
            "run_id": EXPECTED_RUN_ID,
            "created_at": promoted_at,
            "authority": plan["authority"],
            "default_registry": {
                "path": plan["default_path"],
                "sha256": manifest_sha,
            },
            "commit_marker": COMMIT_MARKER,
            "packages": [
                {**report_package, "role": "notion_report"},
                {**audit_package, "role": "local_audit"},
            ],
            "artifacts": validation["checked_artifacts"],
            "upload_status": "pending",
            "model_calls": 0,
        }
        write_json_atomic(staged_outbox / "manifest.json", outbox_manifest)
        write_bytes_atomic(staged_outbox / "第36道回包正文.md", report_bytes)
        write_json_atomic(
            staged_outbox / "promotion_receipt.json",
            {
                "status": "payload_prepared_requires_commit_marker",
                "default_id": EXPECTED_DEFAULT_ID,
                "default_registry_sha256": manifest_sha,
                "outbox_manifest_sha256": sha256_file(staged_outbox / "manifest.json"),
                "commit_marker": COMMIT_MARKER,
                "model_calls": 0,
                "team_reviewer": validation["team_attestation"]["reviewer"],
            },
        )
        commit_document = {
            "schema_version": "zbatch-default-commit-v1",
            "status": "committed",
            "committed_at": promoted_at,
            "default_id": EXPECTED_DEFAULT_ID,
            "default_registry": {
                "path": plan["default_path"],
                "sha256": manifest_sha,
            },
            "outbox_manifest": {
                "path": f"{plan['outbox_path']}/manifest.json",
                "sha256": sha256_file(staged_outbox / "manifest.json"),
            },
        }
        return commit_promotion(
            root,
            staged_outbox=staged_outbox,
            outbox_path=outbox_path,
            default_path=default_path,
            default_bytes=manifest_bytes,
            commit_path=commit_path,
            commit_document=commit_document,
            post_commit_verify=lambda: verify(root, default_path),
        )


def verify_registry_refs(root: Path, registry: dict[str, Any]) -> None:
    chain = registry.get("chain")
    if not isinstance(chain, dict):
        raise DefaultRegistryError("默认登记缺全链")
    expected_chain_paths = dict(EXPECTED_CHAIN_PATHS)
    compatibility = registry.get("compatibility_revision")
    if compatibility is not None:
        if not isinstance(compatibility, dict) or compatibility.get("schema_version") != Z57_COMPATIBILITY_SCHEMA:
            raise DefaultRegistryError("默认登记兼容修订格式非法")
        if compatibility.get("revision_id") != Z57_REVISION_ID:
            raise DefaultRegistryError("默认登记兼容修订不是第57道已验收版本")
        if compatibility.get("authority") != Z57_AUTHORITY:
            raise DefaultRegistryError("默认登记兼容修订缺第57道授权")
        if compatibility.get("semantic_rules_changed") is not False:
            raise DefaultRegistryError("第57道兼容修订不得改变分类语义规则")
        if compatibility.get("sequential_event_id_scope") != "run_local_only":
            raise DefaultRegistryError("第57道没有把顺序事件ID降为本轮内部编号")
        if compatibility.get("predecessor_default_registry_sha256") != Z57_PREDECESSOR_DEFAULT_SHA256:
            raise DefaultRegistryError("第57道兼容修订前代默认登记错位")
        if compatibility.get("predecessor_commit_marker_sha256") != Z57_PREDECESSOR_COMMIT_SHA256:
            raise DefaultRegistryError("第57道兼容修订前代提交标记错位")
        old_contract = compatibility.get("old_contract") or {}
        if old_contract.get("path") != EXPECTED_CHAIN_PATHS["classify_contract"] or old_contract.get("sha256") != Z57_OLD_CONTRACT_SHA256:
            raise DefaultRegistryError("第57道旧合同回退引用错位")
        if sha256_file(root_path(root, old_contract["path"])) != Z57_OLD_CONTRACT_SHA256:
            raise DefaultRegistryError("第57道旧合同回退源漂移")
        new_contract = compatibility.get("new_contract") or {}
        if new_contract != {"path": Z57_CLASSIFY_CONTRACT_PATH, "sha256": Z57_NEW_CONTRACT_SHA256}:
            raise DefaultRegistryError("第57道新合同引用不是已验收版本")
        module_revision = compatibility.get("classify_rules_module") or {}
        if module_revision.get("path") != EXPECTED_CHAIN_PATHS["classify_rules_module"] or module_revision.get("sha256") != Z57_CLASSIFY_MODULE_SHA256:
            raise DefaultRegistryError("第57道分类模块引用不是已验收版本")
        runner_revision = compatibility.get("runner") or {}
        if runner_revision.get("path") != EXPECTED_CHAIN_PATHS["runner"] or runner_revision.get("sha256") != Z57_RUNNER_SHA256:
            raise DefaultRegistryError("第57道运行器引用不是已验收版本")
        frozen_outbox = compatibility.get("frozen_outbox") or {}
        if frozen_outbox != {
            "mode": "historical_promotion_snapshot_no_rewrite",
            "manifest_path": Z57_OUTBOX_MANIFEST_PATH,
            "manifest_sha256": Z57_OUTBOX_MANIFEST_SHA256,
        }:
            raise DefaultRegistryError("第57道冻结outbox关系错位")
        rollback = compatibility.get("rollback") or {}
        expected_rollback = {
            "default_registry_archive": Z57_OLD_DEFAULT_ARCHIVE,
            "commit_marker_archive": Z57_OLD_COMMIT_ARCHIVE,
            "old_contract_path": EXPECTED_CHAIN_PATHS["classify_contract"],
            "old_runner_pinned_path": Z57_OLD_RUNNER_PIN,
            "old_classify_module_pinned_path": Z57_OLD_MODULE_PIN,
        }
        if rollback != expected_rollback:
            raise DefaultRegistryError("第57道回退路线错位")
        rollback_shas = {
            Z57_OLD_DEFAULT_ARCHIVE: Z57_PREDECESSOR_DEFAULT_SHA256,
            Z57_OLD_COMMIT_ARCHIVE: Z57_PREDECESSOR_COMMIT_SHA256,
            Z57_OLD_RUNNER_PIN: Z57_OLD_RUNNER_SHA256,
            Z57_OLD_MODULE_PIN: Z57_OLD_MODULE_SHA256,
        }
        for value, expected_sha in rollback_shas.items():
            if sha256_file(root_path(root, value)) != expected_sha:
                raise DefaultRegistryError(f"第57道回退工件漂移：{value}")
        validation_fixture = compatibility.get("validation_fixture") or {}
        if validation_fixture != {
            "decisions_path": Z57_FORMAL_DECISIONS_PATH,
            "decisions_sha256": Z57_FORMAL_DECISIONS_SHA256,
            "source_extract_path": Z57_SOURCE_EXTRACT_PATH,
            "event_total": 233,
            "gate_failures": [],
        }:
            raise DefaultRegistryError("第57道零调用回归夹具错位")
        expected_chain_paths["classify_contract"] = Z57_CLASSIFY_CONTRACT_PATH
    for name, expected_path in expected_chain_paths.items():
        reference = chain.get(name)
        if not isinstance(reference, dict) or reference.get("path") != expected_path:
            raise DefaultRegistryError(f"默认登记链路路径漂移：{name}")
        path = root_path(root, expected_path)
        if not path.is_file() or sha256_file(path) != reference.get("sha256"):
            raise DefaultRegistryError(f"默认登记链路SHA漂移：{name}")
    if compatibility is not None:
        if chain["classify_contract"].get("sha256") != Z57_NEW_CONTRACT_SHA256:
            raise DefaultRegistryError("默认登记未绑定第57道新合同SHA")
        if chain["classify_rules_module"].get("sha256") != Z57_CLASSIFY_MODULE_SHA256:
            raise DefaultRegistryError("默认登记未绑定第57道分类模块SHA")
        if chain["runner"].get("sha256") != Z57_RUNNER_SHA256:
            raise DefaultRegistryError("默认登记未绑定第57道运行器SHA")
        contract = modular_classify_rules.load_contract(
            root_path(root, Z57_CLASSIFY_CONTRACT_PATH),
            project_root=root,
        )
        documents: list[dict[str, Any]] = []
        catalogs: dict[int, dict[str, str]] = {}
        for chapter in range(1, 21):
            event_path = root_path(root, f"{Z57_SOURCE_EXTRACT_PATH}/events/ch{chapter:04d}.json")
            catalog_path = root_path(root, f"{Z57_SOURCE_EXTRACT_PATH}/evidence_catalogs/ch{chapter:04d}.json")
            documents.append(read_json(event_path))
            catalog_document = read_json(catalog_path)
            catalogs[chapter] = {
                str(row["anchor_id"]): str(row["quote"])
                for row in catalog_document.get("entries") or []
                if isinstance(row, dict) and row.get("anchor_id") and row.get("quote")
            }
        decisions_path = root_path(root, Z57_FORMAL_DECISIONS_PATH)
        if sha256_file(decisions_path) != Z57_FORMAL_DECISIONS_SHA256:
            raise DefaultRegistryError("第57道正式决定夹具SHA漂移")
        decisions = read_json(decisions_path)
        event_map, _ = modular_classify_rules.index_events(documents)
        gate_failures = modular_classify_rules.decision_reasons(
            decisions,
            run_id=str(decisions.get("run_id") or ""),
            event_ids=set(event_map),
            contract=contract,
            event_documents=documents,
            evidence_catalogs=catalogs,
        )
        if gate_failures:
            raise DefaultRegistryError(f"第57道零调用回归失败：{gate_failures}")
    inventory = chain.get("program_inventory")
    if not isinstance(inventory, list) or [row.get("path") for row in inventory if isinstance(row, dict)] != EXPECTED_PROGRAM_PATHS:
        raise DefaultRegistryError("默认登记程序清单漂移")
    for reference, expected_path in zip(inventory, EXPECTED_PROGRAM_PATHS, strict=True):
        path = root_path(root, expected_path)
        if reference.get("sha256") != sha256_file(path):
            raise DefaultRegistryError(f"默认登记程序SHA漂移：{expected_path}")
    expected_transport = {
        "model": "deepseek-v4-flash",
        "profile": "d_mod_cutover_v1",
        "neutral_extract": {
            "temperature": 0.2,
            "max_tokens": 16000,
            "n": 1,
            "reasoning_effort": "medium",
        },
    }
    if chain.get("transport") != expected_transport:
        raise DefaultRegistryError("默认登记运输参数漂移")
    historical = registry.get("historical_reference") or {}
    if historical.get("status") != "historical_reference_not_default" or historical.get("path") != "work/zbatch_prompts/extract_v1.3.md":
        raise DefaultRegistryError("extract_v1.3历史边界漂移")
    historical_path = root_path(root, historical["path"])
    if historical.get("sha256") != sha256_file(historical_path):
        raise DefaultRegistryError("extract_v1.3历史参照SHA漂移")
    adjudication = registry.get("source_adjudication") or {}
    audit_ref = adjudication.get("z00y3_audit") or {}
    if audit_ref.get("path") != EXPECTED_Z00Y3_AUDIT_PATH:
        raise DefaultRegistryError("Z00y3审计路径漂移")
    audit_path = root_path(root, EXPECTED_Z00Y3_AUDIT_PATH)
    if audit_ref.get("sha256") != sha256_file(audit_path):
        raise DefaultRegistryError("Z00y3审计SHA漂移")


def verify(root: Path, default_path: Path) -> dict[str, Any]:
    root = root.resolve()
    registry = read_json(default_path)
    if registry.get("schema_version") != "zbatch-default-registry-v1":
        raise DefaultRegistryError("默认登记schema不符")
    if registry.get("default_id") != EXPECTED_DEFAULT_ID or registry.get("status") != "active":
        raise DefaultRegistryError("默认登记不是活跃v1.2全链")
    verify_registry_refs(root, registry)
    product_ref = registry.get("adjudicated_product") or {}
    product_path = root_path(root, str(product_ref.get("path") or ""))
    if sha256_file(product_path) != product_ref.get("sha256"):
        raise DefaultRegistryError("默认得判件SHA漂移")
    validate_product(read_json(product_path))
    outbox_path = root_path(root, str((registry.get("outbox") or {}).get("path") or ""))
    manifest_path = outbox_path / "manifest.json"
    manifest = read_json(manifest_path)
    manifest_registry_sha = manifest.get("default_registry", {}).get("sha256")
    current_registry_sha = sha256_file(default_path)
    if manifest_registry_sha != current_registry_sha:
        compatibility = registry.get("compatibility_revision") or {}
        frozen_outbox = compatibility.get("frozen_outbox") or {}
        if (
            compatibility.get("predecessor_default_registry_sha256") != manifest_registry_sha
            or frozen_outbox.get("mode") != "historical_promotion_snapshot_no_rewrite"
            or frozen_outbox.get("manifest_sha256") != sha256_file(manifest_path)
        ):
            raise DefaultRegistryError("outbox既未绑定当前默认登记，也没有合法的第57道冻结前代关系")
    for package in manifest.get("packages") or []:
        path = outbox_path / str(package.get("path") or "")
        if not path.is_file() or sha256_file(path) != package.get("sha256"):
            raise DefaultRegistryError(f"outbox包SHA漂移：{path.name}")
        with zipfile.ZipFile(path, "r") as archive:
            if archive.testzip() is not None:
                raise DefaultRegistryError(f"outbox包损坏：{path.name}")
    commit_path = root_path(root, COMMIT_MARKER)
    commit = read_json(commit_path)
    if commit.get("schema_version") != "zbatch-default-commit-v1" or commit.get("status") != "committed":
        raise DefaultRegistryError("第36道提交标记无效")
    if commit.get("default_registry") != {
        "path": relative(root, default_path),
        "sha256": sha256_file(default_path),
    }:
        raise DefaultRegistryError("提交标记未绑定当前默认登记")
    if commit.get("outbox_manifest") != {
        "path": relative(root, manifest_path),
        "sha256": sha256_file(manifest_path),
    }:
        raise DefaultRegistryError("提交标记未绑定当前outbox")
    return {
        "status": "pass",
        "default_registry": relative(root, default_path),
        "default_registry_sha256": sha256_file(default_path),
        "outbox": relative(root, outbox_path),
        "outbox_manifest_sha256": sha256_file(manifest_path),
        "packages": manifest.get("packages"),
        "model_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="v1.2默认链登记与核验")
    sub = parser.add_subparsers(dest="command", required=True)
    promote_parser = sub.add_parser("promote")
    promote_parser.add_argument("--plan", required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--default", default=DEFAULT_REGISTRY)
    args = parser.parse_args()
    if args.command == "promote":
        result = promote(ROOT, root_path(ROOT, args.plan))
    else:
        result = verify(ROOT, root_path(ROOT, args.default))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

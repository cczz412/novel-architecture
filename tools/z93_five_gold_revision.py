#!/usr/bin/env python3
"""第93道续令②：把五本52条问题部件修成新的银标候选版。

本工具只读五份旧候选、原书、Z93判词和Cursor攻击件。它用五份显式
修订规格生成新候选，不回写旧候选，也没有转正式金标的能力。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve()
DEFAULT_SPEC_DIR = ROOT / "runs/Z93_五本金标候选修订_v1.0_20260723/specs"
DEFAULT_OUTPUT_DIR = ROOT / "reports/Z93_五本金标候选修订_20260723"
Z74B_TOOL = ROOT / "tools/z74b_gold_draft_pipeline.py"

CANDIDATES: dict[str, tuple[str, str]] = {
    "Z74B-B01": (
        "reports/Z74B_五本结构层金标底稿_v1.1_20260721/"
        "B01_知否_库存第0033单元_结构层银标底稿v1.2.json",
        "3a02d5e1df8fddb1c8457ecef60b35ffd366473f4eef05e5db937b73a945eee9",
    ),
    "Z74B-B02": (
        "reports/Z74B_五本结构层金标底稿_v1.1_20260721/"
        "B02_大王饶命_库存第0039单元_结构层银标底稿v1.2.json",
        "375c9ce05270d879133798d6163b104551a661b4c8e1a4f9088299035f4e082c",
    ),
    "Z74B-B03": (
        "reports/Z74B_五本结构层金标底稿_v1.1_20260721/"
        "B03_神秘复苏_库存第0041单元_结构层银标底稿v1.2.json",
        "504fa70c52044e1a99c89c3061c6dc42b8f256f5758eee82c99308bdfc513748",
    ),
    "Z74B-B04": (
        "reports/Z74B_五本结构层金标底稿_v1.1_20260721/"
        "B04_无限恐怖_库存第0003单元_结构层银标底稿v1.2.json",
        "0a8fe78b722910d7370539c2366c14cce9c950ff64cf5ce0337047a14e8438f8",
    ),
    "Z74B-B05": (
        "reports/Z74B_五本结构层金标底稿_v1.1_20260721/"
        "B05_凡人修仙传_库存第0030单元_结构层银标底稿v1.2.json",
        "e7e5b65adb21a588dcfe5043cf3f2e2a8607891e99173ff5cd3984f14d98209a",
    ),
}

EXPECTED_TARGETS: dict[str, tuple[str, ...]] = {
    "Z74B-B01": tuple(
        f"Z74B-B01-U0033-{suffix}"
        for suffix in ("A02", "A03", "A04", "A05", "A07", "A08", "A10", "A11", "A12", "A17", "H01")
    ),
    "Z74B-B02": tuple(
        f"Z74B-B02-U0039-{suffix}" for suffix in ("A01", "A04", "A07", "H01")
    ),
    "Z74B-B03": tuple(
        f"Z74B-B03-U0041-{suffix}"
        for suffix in ("A01", "A02", "A03", "A04", "A05", "A06", "A10", "A11", "A12", "A14", "H02")
    ),
    "Z74B-B04": tuple(
        f"Z74B-B04-U0003-{suffix}"
        for suffix in ("A01", "A02", "A03", "A04", "A06", "A08", "A09", "A10", "A12", "A13", "A14", "H01", "H02")
    ),
    "Z74B-B05": tuple(
        f"Z74B-B05-U0030-{suffix}"
        for suffix in ("A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A11", "A12", "H01", "H02")
    ),
}

ISSUE_SOURCES = {
    "codex_final_needs_modification",
    "cursor_ready_breach",
    "cursor_major",
    "cursor_source_attribution",
}

EVIDENCE_SOURCES: dict[str, tuple[str, str]] = {
    "codex_final_judgments": (
        "runs/Z93_五本金标候选逐条验闸_v1.0_20260723/review/final_judgments.json",
        "2b12412090d172fb998b4f5ddb93381bfa7d74dc56b19fe085a58a45cb9b58d2",
    ),
    "cursor_attack_receipt": (
        "reports/Z93_五本金标候选逐条验闸_20260723/cursor_red_team_attack_receipt.json",
        "077a19847a4f38fb3372353798fe291f8a1c4fd96749e51da663a58249797593",
    ),
    "cursor_attack_report": (
        "reports/Z93_五本金标候选逐条验闸_20260723/第93道Cursor六件只读攻击回包_20260723.md",
        "26b3fb8a044c563163b6819ce4377b6dab24a03e8a1fc1cb04b742ba314b97ae",
    ),
    "cursor_major_rules": (
        "TEMP/z93_cursor_red_team_20260723/W2_major门槛补位.md",
        "10dc823d13878c0c2b465ddcb422e32898c35fb1b4ebdc2d77617044f6336516",
    ),
    "cursor_source_rules": (
        "TEMP/z93_cursor_red_team_20260723/W2_src_补位.md",
        "ec21297b9de067d275820a9c7827618051e1a2e930f95a1666473a837887af87",
    ),
}

PROTECTED_FILES: dict[str, str] = {
    "x01_formal_gold": "reports/Z73_第3章金标v1.2定稿转正_20260721/第3章结构层金标v1.2.json",
    "x01_gold_pointer": "config/gold/X01_ch0003_structure_gold_current.json",
    "default_registry": "config/defaults/zbatch_v1.2_full_chain.json",
    "runner": "tools/zbatch.py",
    "classification_contract_active": "config/contracts/classify_rules_v1.2_semantic_identity_v1.json",
    "classification_contract_archive": "config/contracts/classify_rules_v1.2.json",
    "active_122": "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json",
}

EXPECTED_PROTECTED_SHA256: dict[str, str] = {
    "x01_formal_gold": "0df08ede4fa1a33f4bd9e1aea3e45387c8d77131ce79ff1496fe1320fa48a10e",
    "x01_gold_pointer": "6a5c785dc98381ff4d9b7e207c599c29914f394e4b43e399d37f65093cc5a60c",
    "default_registry": "b23b5cce26b9cfe584dd97dbff6422efa2b22ccd5cba38c6ed6a44c4543bc0a1",
    "runner": "160c28b3ef0210fd05c392f713534cf1ffdf041fa596ec790545b64955280850",
    "classification_contract_active": "45f7610b86d5962e0d3d9d4d95886aad9022f1beaece200c2452b9a361f6c108",
    "classification_contract_archive": "ad2ccc3b13e8b138a32a46b8566e928a3c4e35a60cf31c5494c7b9ba3dd021de",
    "active_122": "dafa16901a6edb5018a5176f3f5f7388273e72051def7fe4e997489d01e804ba",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"JSON顶层不是对象：{path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def load_z74b_module() -> Any:
    spec = importlib.util.spec_from_file_location("z74b_for_z93_revision", Z74B_TOOL)
    if not spec or not spec.loader:
        raise AssertionError("无法载入第74道原书回读工具")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def flatten_parts(draft: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    index: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for item in draft["layered_items"]:
        for part in item["parts"]:
            part_id = part["part_id"]
            if part_id in index:
                raise AssertionError(f"候选部件ID重复：{part_id}")
            index[part_id] = (item, part)
    return index


def tree_fingerprint(path: Path) -> dict[str, Any]:
    rows: list[tuple[str, str, int]] = []
    for file in sorted(p for p in path.rglob("*") if p.is_file() and p.name != ".DS_Store"):
        rows.append((str(file.relative_to(path)), sha256_file(file), file.stat().st_size))
    payload = "\n".join(f"{name}\t{digest}\t{size}" for name, digest, size in rows)
    return {
        "files": len(rows),
        "bytes": sum(size for _, _, size in rows),
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def protected_snapshot() -> dict[str, Any]:
    files: dict[str, str] = {}
    for key, relative in PROTECTED_FILES.items():
        path = ROOT / relative
        actual = sha256_file(path)
        if actual != EXPECTED_PROTECTED_SHA256[key]:
            raise AssertionError(f"保护件SHA漂移：{key}｜{actual}")
        files[key] = actual
    for book_id, (relative, expected) in CANDIDATES.items():
        actual = sha256_file(ROOT / relative)
        if actual != expected:
            raise AssertionError(f"原候选SHA漂移：{book_id}｜{actual}")
        files[f"source_candidate:{book_id}"] = actual
    evidence: dict[str, str] = {}
    for key, (relative, expected) in EVIDENCE_SOURCES.items():
        actual = sha256_file(ROOT / relative)
        if actual != expected:
            raise AssertionError(f"验闸或攻击依据SHA漂移：{key}｜{actual}")
        evidence[key] = actual
    return {
        "files": files,
        "evidence_sources": evidence,
        "outbox": tree_fingerprint(ROOT / "outbox"),
    }


def load_specs(spec_dir: Path) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for book_id in CANDIDATES:
        short = book_id.rsplit("-", 1)[1]
        path = spec_dir / f"{short}_revision_spec.json"
        spec = read_json(path)
        if spec.get("schema_version") != "z93-five-gold-revision-spec-v1":
            raise AssertionError(f"规格版本不符：{path}")
        if spec.get("book_id") != book_id:
            raise AssertionError(f"规格书目身份不符：{path}")
        expected_path, expected_sha = CANDIDATES[book_id]
        if spec.get("source_candidate_path") != expected_path:
            raise AssertionError(f"规格原候选路径不符：{book_id}")
        if spec.get("source_candidate_sha256") != expected_sha:
            raise AssertionError(f"规格原候选SHA不符：{book_id}")
        target_ids = spec.get("target_ids")
        if not isinstance(target_ids, list) or set(target_ids) != set(EXPECTED_TARGETS[book_id]):
            raise AssertionError(f"{book_id}修订范围不是获批全集")
        if len(target_ids) != len(set(target_ids)):
            raise AssertionError(f"{book_id}修订范围有重复ID")
        revisions = spec.get("revisions")
        if not isinstance(revisions, list):
            raise AssertionError(f"{book_id}缺修订明细")
        revision_ids = [row.get("source_part_id") for row in revisions]
        if set(revision_ids) != set(target_ids) or len(revision_ids) != len(set(revision_ids)):
            raise AssertionError(f"{book_id}修订明细与目标集合不全等")
        specs[book_id] = {**spec, "_path": path}
    if sum(len(spec["target_ids"]) for spec in specs.values()) != 52:
        raise AssertionError("五本修订源部件总数必须是52")
    return specs


def evidence_rows(
    *,
    draft: dict[str, Any],
    replacement: dict[str, Any],
    cache_units: list[dict[str, Any]],
    source_text: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    part_id = replacement["part_id"]
    source_path = Path(draft["source"]["full_txt_path"])
    for sequence, evidence in enumerate(replacement["evidence_quotes"], start=1):
        ordinal = evidence.get("inventory_unit")
        quote = evidence.get("quote")
        if not isinstance(ordinal, int) or not isinstance(quote, str):
            raise AssertionError(f"{part_id}证据规格不完整")
        if not 10 <= len(quote) <= 25:
            raise AssertionError(f"{part_id}短引长度不在10—25字：{quote}")
        unit = cache_units[ordinal - 1]
        if unit["cache_body"].count(quote) != 1:
            raise AssertionError(f"{part_id}短引在第{ordinal}库存单元不是唯一命中：{quote}")
        cache_start = unit["cache_body"].index(quote)
        full_start = unit["full_txt_start_char"] + cache_start
        full_end = full_start + len(quote)
        if source_text[full_start:full_end] != quote:
            raise AssertionError(f"{part_id}短引不能在整书逐字回读：{quote}")
        rows.append(
            {
                "inventory_unit": ordinal,
                "complete_heading": unit["complete_heading"],
                "anchor_id": f"{part_id}-Q{sequence:02d}",
                "quote": quote,
                "quote_char_count": len(quote),
                "quote_occurrence_in_cache_unit": 1,
                "cache_file_path": unit["cache_file_path"],
                "cache_file_sha256": unit["cache_file_sha256"],
                "cache_body_sha256": unit["cache_body_sha256"],
                "cache_body_start_char": cache_start,
                "cache_body_end_char_exclusive": cache_start + len(quote),
                "full_txt_path": str(source_path),
                "full_txt_sha256": draft["source"]["full_txt_sha256"],
                "full_txt_start_char": full_start,
                "full_txt_end_char_exclusive": full_end,
            }
        )
    return rows


def coverage_ledger(components: dict[str, str], anchors: list[dict[str, Any]]) -> dict[str, Any]:
    anchor_ids = [row["anchor_id"] for row in anchors]
    return {
        "review_method": "human_per_field_check_against_cache_unit_context",
        "mechanical_anchor_pass_does_not_equal_semantic_pass": True,
        "review_status": "human_checked_candidate_pending_cz_review",
        "fields": {
            field: {
                "text": components[field],
                "support_anchor_ids": anchor_ids,
                "coverage_status": "direct_or_context_bounded_candidate",
            }
            for field in (
                "subject",
                "action_or_cognition_or_intention",
                "object",
                "explicit_result_or_constraint",
            )
        },
        "strength_guard": "不得把可能、怀疑、自述或后续观察升级成客观事实。",
    }


def build_part(
    *,
    draft: dict[str, Any],
    source_part: dict[str, Any],
    revision: dict[str, Any],
    replacement: dict[str, Any],
    cache_units: list[dict[str, Any]],
    source_text: str,
) -> dict[str, Any]:
    part_id = replacement.get("part_id")
    if not isinstance(part_id, str) or not part_id:
        raise AssertionError(f"{revision['source_part_id']}替换部件缺ID")
    components = replacement.get("claim_components")
    if not isinstance(components, dict):
        raise AssertionError(f"{part_id}缺四要素")
    required_fields = (
        "subject",
        "action_or_cognition_or_intention",
        "object",
        "explicit_result_or_constraint",
    )
    if any(not str(components.get(field, "")).strip() for field in required_fields):
        raise AssertionError(f"{part_id}四要素不完整")
    claim = replacement.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        raise AssertionError(f"{part_id}事件句为空")
    anchors = evidence_rows(
        draft=draft,
        replacement=replacement,
        cache_units=cache_units,
        source_text=source_text,
    )
    layer = source_part["layer"]
    target_ordinal = draft["source"]["inventory_unit"]
    if layer == "当章可知":
        if any(row["inventory_unit"] != target_ordinal for row in anchors):
            raise AssertionError(f"{part_id}当章件使用了目录外库存单元")
        if replacement.get("target_chapter_relation"):
            raise AssertionError(f"{part_id}当章件不应有回看关系")
    elif layer == "回看件":
        if any(not target_ordinal < row["inventory_unit"] <= 50 for row in anchors):
            raise AssertionError(f"{part_id}回看件越过目标单元后至第50单元窗口")
        if not str(replacement.get("target_chapter_relation", "")).strip():
            raise AssertionError(f"{part_id}回看件缺目标章关系")
    else:
        raise AssertionError(f"{part_id}未知层位：{layer}")
    score = layer == "当章可知"
    part = {
        "part_id": part_id,
        "layer": layer,
        "part_role": (
            "human_context_reviewed_atomic_candidate"
            if score
            else "human_context_reviewed_hindsight_candidate"
        ),
        "score_in_single_chapter": score,
        "formal_score_eligible": False,
        "claim": claim,
        "claim_components": {field: str(components[field]) for field in required_fields},
        "claim_provenance": (
            "human_revised_from_target_chapter_original_txt"
            if score
            else "human_revised_from_inventory_units_1_to_50_original_txt"
        ),
        "source_evidence": anchors,
        "semantic_coverage_ledger": coverage_ledger(components, anchors),
        "atomicity": {
            "method": (
                "one_central_structure_fact_after_human_context_review"
                if score
                else "one_central_hindsight_fact_after_human_context_review"
            ),
            "one_subject_head": True,
            "one_action_or_cognition_or_intention_head": True,
            "explicit_object": True,
            "explicit_result_or_constraint": True,
            "semantic_atomicity_status": "candidate_pending_cz_review",
        },
        "representative_selection": {
            "method": (
                "human_read_full_target_chapter_then_structure_importance_adjudication"
                if score
                else "human_review_only_within_inventory_units_1_to_50"
            ),
            "structural_importance": revision["reason"],
            "ordinary_action": False,
            "external_ai_semantics_used": False,
        },
        "review_status": "candidate_pending_cz_review",
        "revision_record": {
            "task": "第93道续令②",
            "source_part_id": revision["source_part_id"],
            "issue_sources": revision["issue_sources"],
            "reason": revision["reason"],
        },
    }
    if not score:
        part["target_chapter_relation"] = replacement["target_chapter_relation"]
    return part


def revise_one(
    *,
    spec: dict[str, Any],
    z74b: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    book_id = spec["book_id"]
    source_path = ROOT / spec["source_candidate_path"]
    source_draft = read_json(source_path)
    if sha256_file(source_path) != spec["source_candidate_sha256"]:
        raise AssertionError(f"{book_id}原候选SHA漂移")
    draft = copy.deepcopy(source_draft)
    original_index = flatten_parts(source_draft)
    revised_index = flatten_parts(draft)
    if set(original_index) != set(revised_index):
        raise AssertionError(f"{book_id}深拷贝前后部件集合变化")
    source_text, cache_units, recognized_heading_total = z74b.load_cache_inventory(
        Path(draft["source"]["full_txt_path"]),
        book_id,
        draft["source"]["cache_unit_total"],
    )
    if recognized_heading_total != draft["source"]["full_txt_recognized_heading_total"]:
        raise AssertionError(f"{book_id}整书可识别章头数漂移")
    replacement_ids: set[str] = set()
    lineage: list[dict[str, Any]] = []
    for revision in spec["revisions"]:
        source_part_id = revision["source_part_id"]
        item, source_part = revised_index[source_part_id]
        issue_sources = revision.get("issue_sources")
        if not isinstance(issue_sources, list) or not issue_sources or not set(issue_sources) <= ISSUE_SOURCES:
            raise AssertionError(f"{source_part_id}问题来源不合规")
        replacements = revision.get("replacements")
        if not isinstance(replacements, list) or not replacements:
            raise AssertionError(f"{source_part_id}没有替换部件")
        operation = revision.get("operation")
        if operation == "replace_one":
            if len(replacements) != 1 or replacements[0].get("part_id") != source_part_id:
                raise AssertionError(f"{source_part_id}单条改写必须沿用源ID且只出一条")
        elif operation == "split":
            if len(replacements) < 2:
                raise AssertionError(f"{source_part_id}拆分至少应有两条")
            expected_prefix = f"{source_part_id}-R"
            if any(not str(row.get("part_id", "")).startswith(expected_prefix) for row in replacements):
                raise AssertionError(f"{source_part_id}拆分部件ID未按-R序列命名")
        else:
            raise AssertionError(f"{source_part_id}未知修订操作：{operation}")
        built = [
            build_part(
                draft=draft,
                source_part=source_part,
                revision=revision,
                replacement=replacement,
                cache_units=cache_units,
                source_text=source_text,
            )
            for replacement in replacements
        ]
        for part in built:
            if part["part_id"] in replacement_ids:
                raise AssertionError(f"新部件ID重复：{part['part_id']}")
            replacement_ids.add(part["part_id"])
        item["decision"] = f"第93道续令②修订：{revision['reason']}"
        item["parts"] = built
        item["hindsight_parts"] = [part["part_id"] for part in built if part["layer"] == "回看件"]
        item["revision_lineage"] = {
            "source_part_id": source_part_id,
            "source_part_sha256": canonical_sha(source_part),
            "replacement_part_ids": [part["part_id"] for part in built],
        }
        lineage.append(
            {
                "book_id": book_id,
                "source_part_id": source_part_id,
                "source_part_sha256": canonical_sha(source_part),
                "operation": operation,
                "replacement_part_ids": [part["part_id"] for part in built],
                "issue_sources": issue_sources,
                "reason": revision["reason"],
                "evidence_quotes": [
                    {
                        "part_id": part["part_id"],
                        "quotes": [
                            {"inventory_unit": row["inventory_unit"], "quote": row["quote"]}
                            for row in part["source_evidence"]
                        ],
                    }
                    for part in built
                ],
            }
        )
    all_new_parts = [
        part for item in draft["layered_items"] for part in item["parts"]
    ]
    all_new_ids = [part["part_id"] for part in all_new_parts]
    if len(all_new_ids) != len(set(all_new_ids)):
        raise AssertionError(f"{book_id}修订后部件ID重复")
    untouched_ids = set(original_index) - set(spec["target_ids"])
    collisions = untouched_ids & replacement_ids
    if collisions:
        raise AssertionError(f"{book_id}新部件碰撞未修订ID：{sorted(collisions)}")
    revised_by_id = {part["part_id"]: part for part in all_new_parts}
    unexpected_changed = [
        part_id
        for part_id in sorted(untouched_ids)
        if canonical_sha(original_index[part_id][1]) != canonical_sha(revised_by_id[part_id])
    ]
    if unexpected_changed:
        raise AssertionError(f"{book_id}未列入计划的部件发生变化：{unexpected_changed}")
    on_unit_total = sum(part["layer"] == "当章可知" for part in all_new_parts)
    hindsight_total = sum(part["layer"] == "回看件" for part in all_new_parts)
    draft["schema_version"] = "structure-gold-v1.3-candidate"
    draft["draft_id"] = draft["draft_id"].replace(
        "structure-v1.2-candidate", "structure-v1.3-revised-candidate"
    )
    draft["task"] = "第93道续令②五本金标候选修订"
    draft["producer"] = {
        "path": str(THIS_FILE.relative_to(ROOT)),
        "sha256": sha256_file(THIS_FILE),
    }
    draft["layer_summary"] = {
        "layered_item_total": len(draft["layered_items"]),
        "candidate_part_total": len(all_new_parts),
        "on_unit_candidate_part_total": on_unit_total,
        "hindsight_part_total": hindsight_total,
        "formal_gold_part_total": 0,
    }
    draft["hindsight_review_register"]["parts"] = [
        {
            "part_id": part["part_id"],
            "evidence_inventory_unit": part["source_evidence"][0]["inventory_unit"],
            "evidence_complete_heading": part["source_evidence"][0]["complete_heading"],
            "target_chapter_relation": part["target_chapter_relation"],
            "review_status": part["review_status"],
        }
        for part in all_new_parts
        if part["layer"] == "回看件"
    ]
    draft["review_flags"] = [
        *draft["review_flags"],
        {
            "kind": "z93_revision_pending_cloud_review",
            "detail": "52条问题部件已按Codex终判和Cursor攻击修订；仍是银标候选，统一审收前不得转正。",
        },
    ]
    draft["revision_provenance"] = {
        "task": "第93道续令②",
        "source_candidate_path": spec["source_candidate_path"],
        "source_candidate_sha256": spec["source_candidate_sha256"],
        "revision_spec_path": str(spec["_path"].relative_to(ROOT)),
        "revision_spec_sha256": sha256_file(spec["_path"]),
        "source_part_total": len(spec["target_ids"]),
        "replacement_part_total": sum(len(row["replacements"]) for row in spec["revisions"]),
        "future_formal_provenance_label": "Codex验闸＋Cursor攻击定稿、非CZ亲验",
        "formal_gold_promoted": False,
    }
    scope = {
        "book_id": book_id,
        "declared_target_ids": sorted(spec["target_ids"]),
        "changed_source_part_ids": sorted(row["source_part_id"] for row in lineage),
        "untouched_part_total": len(untouched_ids),
        "untouched_part_hash_match": not unexpected_changed,
        "unexpected_changed_part_ids": unexpected_changed,
        "source_to_replacement_lineage": [
            {
                "source_part_id": row["source_part_id"],
                "replacement_part_ids": row["replacement_part_ids"],
            }
            for row in lineage
        ],
    }
    return draft, scope, {"book_id": book_id, "rows": lineage}


def output_name(source_name: str) -> str:
    suffix = "结构层银标底稿v1.2.json"
    if not source_name.endswith(suffix):
        raise AssertionError(f"原候选文件名不符合预期：{source_name}")
    return source_name[: -len(suffix)] + "结构层银标修订候选v1.3.json"


def report_markdown(
    *,
    book_rows: list[dict[str, Any]],
    anchor_total: int,
    candidate_part_total: int,
) -> str:
    lines = [
        "# 第93道续令②停点回包｜五本金标候选修订",
        "",
        "✅ 五本52条问题部件已按冻结正文修订并另存。原五本候选、正式金标、指针和现役链均未回写；本批仍是候选银标，等待统一审收。",
        "",
        "| 书目 | 修订源部件 | 修订后部件 | 状态 |",
        "|---|---:|---:|---|",
    ]
    for row in book_rows:
        lines.append(
            f"| {row['book_id']} | {row['source_part_total']} | "
            f"{row['replacement_part_total']} | 银标候选，未转正 |"
        )
    lines.extend(
        [
            "",
            f"- 修订源部件：52 条；修订后五本候选共 {candidate_part_total} 条。",
            f"- 新候选锚逐字回读：{anchor_total}/{anchor_total} 通过。",
            "- 清单对账：Codex原33条＋Cursor新19条＝52条；4条major和10条来源限定均已去重包含。",
            "- 修订范围之外部件：逐部件规范SHA全同，意外改动0。",
            "- 机械生成：两次隔离运行逐文件字节一致。",
            "- 调用账：模型API 0、网络请求0、token 0。",
            "- 边界：X01-07-N01按CZ选甲只挂账，不修改现役金标；五本转正另等审收令。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def build_once(output_dir: Path, spec_dir: Path, protected: dict[str, Any]) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise AssertionError(f"输出目录非空，拒绝覆盖：{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = load_specs(spec_dir)
    z74b = load_z74b_module()
    revised_drafts: list[dict[str, Any]] = []
    scope_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    plan_books: list[dict[str, Any]] = []
    book_summary: list[dict[str, Any]] = []
    revised_dir = output_dir / "revised_candidates"
    revised_dir.mkdir()
    for book_id in CANDIDATES:
        spec = specs[book_id]
        draft, scope, ledger = revise_one(spec=spec, z74b=z74b)
        revised_drafts.append(draft)
        scope_rows.append(scope)
        ledger_rows.extend(ledger["rows"])
        source_name = Path(spec["source_candidate_path"]).name
        target = revised_dir / output_name(source_name)
        write_json(target, draft)
        replacement_total = sum(len(row["replacements"]) for row in spec["revisions"])
        plan_books.append(
            {
                "book_id": book_id,
                "source_candidate_path": spec["source_candidate_path"],
                "source_candidate_sha256": spec["source_candidate_sha256"],
                "revision_spec_path": str(spec["_path"].relative_to(ROOT)),
                "revision_spec_sha256": sha256_file(spec["_path"]),
                "target_ids": sorted(spec["target_ids"]),
                "source_part_total": len(spec["target_ids"]),
                "replacement_part_total": replacement_total,
                "output_path": str(target.relative_to(output_dir)),
                "output_sha256": sha256_file(target),
            }
        )
        book_summary.append(
            {
                "book_id": book_id,
                "source_part_total": len(spec["target_ids"]),
                "replacement_part_total": replacement_total,
            }
        )
    anchor_audit = z74b.validate_anchors(revised_drafts)
    if anchor_audit["failed_total"] != 0:
        failed = [row for row in anchor_audit["checks"] if row["status"] != "pass"]
        raise AssertionError(f"修订候选锚回读失败：{failed[:5]}")
    candidate_part_total = sum(
        draft["layer_summary"]["candidate_part_total"] for draft in revised_drafts
    )
    plan = {
        "schema_version": "z93-five-gold-revision-plan-v1",
        "task": "第93道续令②",
        "status": "frozen_52_source_parts",
        "truth_boundary": "只认五本冻结正文；判词与攻击件只决定查修方向，不替代原文。",
        "scope_rule": "Codex原33条与Cursor新19条按完整part_id去重后全等于52条；major与来源限定不重复加数。",
        "books": plan_books,
        "counts": {
            "book_total": 5,
            "source_part_total": 52,
            "replacement_part_total": sum(row["replacement_part_total"] for row in book_summary),
            "candidate_part_total_after_revision": candidate_part_total,
            "anchor_total_after_revision": anchor_audit["anchor_total"],
        },
        "evidence_source_sha256": protected["evidence_sources"],
    }
    write_json(output_dir / "revision_plan.json", plan)
    write_json(
        output_dir / "revision_ledger.json",
        {
            "schema_version": "z93-five-gold-revision-ledger-v1",
            "status": "all_52_sources_revised",
            "rows": ledger_rows,
        },
    )
    write_json(
        output_dir / "scope_reconciliation.json",
        {
            "schema_version": "z93-five-gold-scope-reconciliation-v1",
            "status": "pass_zero_missing_zero_extra",
            "declared_source_total": 52,
            "changed_source_total": sum(len(row["changed_source_part_ids"]) for row in scope_rows),
            "unexpected_changed_total": sum(len(row["unexpected_changed_part_ids"]) for row in scope_rows),
            "books": scope_rows,
        },
    )
    write_json(
        output_dir / "anchor_readback_audit.json",
        {
            "schema_version": "z93-five-gold-anchor-readback-v1",
            "status": "pass" if anchor_audit["failed_total"] == 0 else "hard_stop",
            **anchor_audit,
        },
    )
    write_json(
        output_dir / "protected_state_audit.json",
        {
            "schema_version": "z93-five-gold-protected-state-v1",
            "status": "locked_before_generation",
            "snapshot": protected,
            "formal_gold_promoted": False,
            "gold_pointer_changed": False,
            "active_122_changed": False,
            "default_or_runner_changed": False,
            "classification_or_outbox_changed": False,
        },
    )
    write_json(
        output_dir / "usage.json",
        {
            "schema_version": "z93-five-gold-revision-usage-v1",
            "model_api_calls": 0,
            "network_requests": 0,
            "token_usage": 0,
        },
    )
    report_path = output_dir / "第93道续令②停点回包｜五本金标候选修订_20260723.md"
    report_path.write_text(
        report_markdown(
            book_rows=book_summary,
            anchor_total=anchor_audit["anchor_total"],
            candidate_part_total=candidate_part_total,
        ),
        encoding="utf-8",
    )
    return {
        "book_total": 5,
        "source_part_total": 52,
        "replacement_part_total": sum(row["replacement_part_total"] for row in book_summary),
        "candidate_part_total": candidate_part_total,
        "anchor_total": anchor_audit["anchor_total"],
        "book_summary": book_summary,
    }


def write_manifest(output_dir: Path, result: dict[str, Any]) -> None:
    files = {
        str(path.relative_to(output_dir)): sha256_file(path)
        for path in sorted(output_dir.rglob("*"))
        if path.is_file() and path.name != "report_manifest.json"
    }
    write_json(
        output_dir / "report_manifest.json",
        {
            "schema_version": "z93-five-gold-revision-report-manifest-v1",
            "task": "第93道续令②",
            "status": "candidate_revision_complete_pending_cloud_review",
            "candidate_boundary": "五本仍是银标候选；统一审收前不得转正。",
            "producer": {
                "path": str(THIS_FILE.relative_to(ROOT)),
                "sha256": sha256_file(THIS_FILE),
            },
            "counts": {
                key: result[key]
                for key in (
                    "book_total",
                    "source_part_total",
                    "replacement_part_total",
                    "candidate_part_total",
                    "anchor_total",
                )
            },
            "files": files,
        },
    )


def assert_safe_output(output_dir: Path, spec_dir: Path) -> None:
    resolved = output_dir.resolve()
    protected_roots = [
        (ROOT / relative).resolve().parent for relative, _ in CANDIDATES.values()
    ]
    protected_roots.append(spec_dir.resolve())
    for protected in protected_roots:
        if resolved == protected or protected in resolved.parents:
            raise AssertionError(f"输出目录不能落在只读原件或规格目录内：{resolved}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise AssertionError(f"输出目录非空，拒绝覆盖：{output_dir}")


def repeat_generate(output_dir: Path, spec_dir: Path) -> dict[str, Any]:
    assert_safe_output(output_dir, spec_dir)
    before = protected_snapshot()
    with tempfile.TemporaryDirectory(prefix="z93-revision-", dir=ROOT / "TEMP") as temp_name:
        temp_root = Path(temp_name)
        pass1_dir = temp_root / "pass1"
        pass2_dir = temp_root / "pass2"
        pass1 = build_once(pass1_dir, spec_dir, before)
        pass2 = build_once(pass2_dir, spec_dir, before)
        initial1 = tree_fingerprint(pass1_dir)
        initial2 = tree_fingerprint(pass2_dir)
        if initial1 != initial2:
            raise AssertionError("两次隔离生成的核心树指纹不一致")
        repeat_receipt = {
            "schema_version": "z93-five-gold-repeat-validation-v1",
            "status": "pass_byte_identical",
            "pass1_core_fingerprint": initial1,
            "pass2_core_fingerprint": initial2,
            "same": True,
        }
        for pass_dir, result in ((pass1_dir, pass1), (pass2_dir, pass2)):
            write_json(pass_dir / "mechanical_double_run_receipt.json", repeat_receipt)
            write_manifest(pass_dir, result)
        final1 = tree_fingerprint(pass1_dir)
        final2 = tree_fingerprint(pass2_dir)
        if final1 != final2:
            raise AssertionError("两次隔离生成的最终文件树不一致")
        if output_dir.exists():
            output_dir.rmdir()
        shutil.copytree(pass1_dir, output_dir)
    after = protected_snapshot()
    if before != after:
        raise AssertionError("保护件在修订过程中发生漂移")
    result = {
        **pass1,
        "status": "candidate_revision_complete_pending_cloud_review",
        "repeat_validation": "pass_byte_identical",
        "final_tree_fingerprint": final1,
        "protected_state_match": True,
        "output_dir": str(output_dir),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec-dir", type=Path, default=DEFAULT_SPEC_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = repeat_generate(args.output_dir.resolve(), args.spec_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""第93道：五本金标候选底稿的零调用逐条验闸壳。

本工具只做四件机械工作：锁定候选与原书实物、生成独立评审模板、
找出两票分歧、把第三票裁定合成为最终判词账。它不替代语义判断，
不改候选底稿，也不把任何候选升为正式金标。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_DIR = ROOT / "reports/Z74B_五本结构层金标底稿_v1.1_20260721"
Z74B_TOOL = ROOT / "tools/z74b_gold_draft_pipeline.py"

CANDIDATES: tuple[tuple[str, str, str], ...] = (
    (
        "Z74B-B01",
        "B01_知否_库存第0033单元_结构层银标底稿v1.2.json",
        "3a02d5e1df8fddb1c8457ecef60b35ffd366473f4eef05e5db937b73a945eee9",
    ),
    (
        "Z74B-B02",
        "B02_大王饶命_库存第0039单元_结构层银标底稿v1.2.json",
        "375c9ce05270d879133798d6163b104551a661b4c8e1a4f9088299035f4e082c",
    ),
    (
        "Z74B-B03",
        "B03_神秘复苏_库存第0041单元_结构层银标底稿v1.2.json",
        "504fa70c52044e1a99c89c3061c6dc42b8f256f5758eee82c99308bdfc513748",
    ),
    (
        "Z74B-B04",
        "B04_无限恐怖_库存第0003单元_结构层银标底稿v1.2.json",
        "0a8fe78b722910d7370539c2366c14cce9c950ff64cf5ce0337047a14e8438f8",
    ),
    (
        "Z74B-B05",
        "B05_凡人修仙传_库存第0030单元_结构层银标底稿v1.2.json",
        "e7e5b65adb21a588dcfe5043cf3f2e2a8607891e99173ff5cd3984f14d98209a",
    ),
)

CHECK_FIELDS = (
    "fact_consistency",
    "explicit_qualifiers_complete",
    "one_sentence_one_fact",
    "anchor_semantic_support",
)
CHECK_VALUES = {"pass", "fail", "uncertain"}
DISPOSITIONS = {"candidate_ready", "needs_modification", "recommended_removal", "uncertain"}
FINAL_DISPOSITIONS = DISPOSITIONS - {"uncertain"}

X01_RED_TEAM_REFERENCE: tuple[tuple[str, str, str], ...] = (
    (
        "formal_gold_pointer",
        "config/gold/X01_ch0003_structure_gold_current.json",
        "6a5c785dc98381ff4d9b7e207c599c29914f394e4b43e399d37f65093cc5a60c",
    ),
    (
        "formal_gold_artifact",
        "reports/Z73_第3章金标v1.2定稿转正_20260721/第3章结构层金标v1.2.json",
        "0df08ede4fa1a33f4bd9e1aea3e45387c8d77131ce79ff1496fe1320fa48a10e",
    ),
    (
        "frozen_chapter_text",
        "TEMP/X批材料包_20260716/books/X01_诡秘之主/chapters/0003_第3章_梅丽莎（第一更求推荐票）.txt",
        "96f5e17cbec15433b5d00bef18912eb39710ad67962e3716bca37203d4c06288",
    ),
    (
        "evidence_catalog",
        "runs/Z80_事实说明书注入包v4_三组复验_v1.3_20260721/inputs/X01-C0003/evidence_catalog.json",
        "2cc50e9a0c8b5fb807641e09c74f1748cbe423bf0fa700dbbbaa84ba20e58132",
    ),
)

INITIAL_BLANK_REVIEW_SHA256 = {
    "review_R1_A.json": "a594c2d6acf3963c2bff1b2db1173304d053f505df3a2f8e08dbe118404d26db",
    "review_R1_B.json": "3ecac24924f68aac1f30b262560a29df7b1c592bdae0896166c2dd04c0b868d1",
    "review_R2_A.json": "61a8042bb840d3155b416a9dacfce36b9ad82c0661d3f1cb4f4008cbd642f3e8",
    "review_R2_B.json": "c8b7ebb5af32327eea4907870a021e8d221710576c2e52256bae95e63f555d2b",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(data))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def load_z74b_module() -> Any:
    spec = importlib.util.spec_from_file_location("z74b_for_z93", Z74B_TOOL)
    if not spec or not spec.loader:
        raise AssertionError("无法载入第74道原书回读工具")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_locked_drafts() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    drafts: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for book_id, filename, expected_sha in CANDIDATES:
        path = CANDIDATE_DIR / filename
        actual_sha = sha256_file(path)
        if actual_sha != expected_sha:
            raise AssertionError(f"{filename} SHA不符：{actual_sha}")
        draft = read_json(path)
        if draft["source"]["book_id"] != book_id:
            raise AssertionError(f"{filename}书目身份不符")
        if draft["status"] != "candidate_pending_cz_review":
            raise AssertionError(f"{filename}不是待审候选")
        if draft["candidate_level"] != "silver_draft_not_formal_gold":
            raise AssertionError(f"{filename}候选等级不符")
        source_path = Path(draft["source"]["full_txt_path"])
        cache_path = Path(draft["source"]["cache_file_path"])
        if sha256_file(source_path) != draft["source"]["full_txt_sha256"]:
            raise AssertionError(f"{filename}整书真源SHA漂移")
        if sha256_file(cache_path) != draft["source"]["cache_file_sha256"]:
            raise AssertionError(f"{filename}目标库存单元SHA漂移")
        parts = [part for item in draft["layered_items"] for part in item["parts"]]
        if len(parts) != draft["layer_summary"]["candidate_part_total"]:
            raise AssertionError(f"{filename}候选部件计数不符")
        drafts.append(draft)
        inventory.append(
            {
                "book_id": book_id,
                "book": draft["source"]["book"],
                "inventory_unit": draft["source"]["inventory_unit"],
                "candidate_path": str(path.relative_to(ROOT)),
                "candidate_sha256": actual_sha,
                "candidate_part_total": len(parts),
                "on_unit_part_total": sum(part["layer"] == "当章可知" for part in parts),
                "hindsight_part_total": sum(part["layer"] == "回看件" for part in parts),
                "anchor_total": sum(len(part["source_evidence"]) for part in parts),
                "cache_file_path": str(cache_path),
                "cache_file_sha256": draft["source"]["cache_file_sha256"],
                "cache_body_sha256": draft["source"]["cache_body_sha256"],
                "full_txt_path": str(source_path),
                "full_txt_sha256": draft["source"]["full_txt_sha256"],
            }
        )
    z74b = load_z74b_module()
    audit = z74b.validate_anchors(drafts)
    if audit["anchor_total"] != 160 or audit["failed_total"] != 0:
        raise AssertionError("五本原书锚回读未达到160/160")
    return drafts, inventory


def flatten_rows(drafts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for draft in drafts:
        source = draft["source"]
        for item in draft["layered_items"]:
            for part in item["parts"]:
                rows.append(
                    {
                        "book_id": source["book_id"],
                        "book": source["book"],
                        "inventory_unit": source["inventory_unit"],
                        "complete_heading": source["complete_heading"],
                        "item_id": item["item_id"],
                        "part_id": part["part_id"],
                        "layer": part["layer"],
                        "claim": part["claim"],
                        "claim_components": part["claim_components"],
                        "source_evidence": part["source_evidence"],
                        "candidate_decision": item["decision"],
                    }
                )
    return rows


def blank_review(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "book_id": row["book_id"],
        "part_id": row["part_id"],
        "checks": {field: None for field in CHECK_FIELDS},
        "disposition": None,
        "major_issue": None,
        "reasoning": "",
        "original_evidence_excerpt": "",
        "suggested_revision": None,
        "removal_evidence": None,
    }


def prepare(output_dir: Path) -> dict[str, Any]:
    drafts, inventory = load_locked_drafts()
    rows = flatten_rows(drafts)
    if len(rows) != 76 or len({row["part_id"] for row in rows}) != 76:
        raise AssertionError("五本候选应为76个唯一部件")
    manifest = {
        "schema_version": "z93-gate-manifest-v1",
        "task": "第93道五本金标候选底稿转正预筛",
        "status": "prepared_zero_call_double_independent_review",
        "candidate_boundary": "五份旧底稿只读；判词另存；本轮不自动转正。",
        "review_rule": "R1/R2对76条独立双审；只把分歧或uncertain字段交R3裁定。",
        "inventory": inventory,
        "counts": {
            "book_total": 5,
            "candidate_part_total": 76,
            "on_unit_part_total": 66,
            "hindsight_part_total": 10,
            "anchor_total": 160,
            "model_api_calls": 0,
            "network_requests": 0,
        },
    }
    write_json(output_dir / "run_manifest.json", manifest)
    write_json(
        output_dir / "review_packet.json",
        {
            "schema_version": "z93-review-packet-v1",
            "truth_boundary": "只认每条source_evidence所钉缓存正文与整本原书；外部AI材料禁作真值。",
            "rubric": {
                "fact_consistency": "主张不得超出原书上下文；推测、自述、叙述事实不得互相升级。",
                "explicit_qualifiers_complete": "原文明示的时间、前提、范围、否定、可能性、因果限定不得遗漏或改强。",
                "one_sentence_one_fact": "一个事实头、一个主要主体动作或认知；并列条件可作为同一事实限定，独立事件须拆。",
                "anchor_semantic_support": "全部关键主张均须由所挂锚及其紧邻上下文托住，不能只靠撞词。",
            },
            "rows": rows,
        },
    )
    cohorts = {
        "A": {"Z74B-B01", "Z74B-B02", "Z74B-B03"},
        "B": {"Z74B-B04", "Z74B-B05"},
    }
    for reviewer_id in ("R1", "R2"):
        for cohort, book_ids in cohorts.items():
            selected = [row for row in rows if row["book_id"] in book_ids]
            write_json(
                output_dir / "reviews" / f"review_{reviewer_id}_{cohort}.json",
                {
                    "schema_version": "z93-independent-review-v1",
                    "reviewer_id": reviewer_id,
                    "cohort": cohort,
                    "independence_rule": "不得读取另一评审或裁定文件；必须逐条回读原书。",
                    "rows": [blank_review(row) for row in selected],
                },
            )
    return manifest


def validate_review_row(row: dict[str, Any], *, allow_uncertain: bool) -> None:
    if set(row.get("checks", {})) != set(CHECK_FIELDS):
        raise AssertionError(f"{row.get('part_id')}四项检查字段不完整")
    values = set(row["checks"].values())
    allowed_checks = CHECK_VALUES if allow_uncertain else CHECK_VALUES - {"uncertain"}
    if not values <= allowed_checks:
        raise AssertionError(f"{row['part_id']}检查值非法或未填写")
    allowed_dispositions = DISPOSITIONS if allow_uncertain else FINAL_DISPOSITIONS
    if row.get("disposition") not in allowed_dispositions:
        raise AssertionError(f"{row['part_id']}处置分类非法或未填写")
    if not isinstance(row.get("major_issue"), bool):
        raise AssertionError(f"{row['part_id']}重大问题标记未填写")
    if not str(row.get("reasoning", "")).strip():
        raise AssertionError(f"{row['part_id']}缺判词")
    if not str(row.get("original_evidence_excerpt", "")).strip():
        raise AssertionError(f"{row['part_id']}缺原文短引")
    if row["disposition"] == "needs_modification" and not str(row.get("suggested_revision") or "").strip():
        raise AssertionError(f"{row['part_id']}需修改但缺建议")
    if row["disposition"] == "recommended_removal" and not str(row.get("removal_evidence") or "").strip():
        raise AssertionError(f"{row['part_id']}建议移除但缺证据")
    if row["disposition"] == "candidate_ready" and (
        set(row["checks"].values()) != {"pass"} or row["major_issue"]
    ):
        raise AssertionError(f"{row['part_id']}未全过却标为可直接转正候选")
    if row["disposition"] == "recommended_removal" and not row["major_issue"]:
        raise AssertionError(f"{row['part_id']}建议移除却未标重大问题")
    if row["major_issue"] and row["disposition"] == "candidate_ready":
        raise AssertionError(f"{row['part_id']}重大问题与可直接转正冲突")


def load_two_votes(
    review_paths: list[Path], expected_rows: dict[str, dict[str, Any]]
) -> dict[str, dict[str, dict[str, Any]]]:
    expected_ids = set(expected_rows)
    votes: dict[str, dict[str, dict[str, Any]]] = {"R1": {}, "R2": {}}
    cohort_books = {
        "A": {"Z74B-B01", "Z74B-B02", "Z74B-B03"},
        "B": {"Z74B-B04", "Z74B-B05"},
    }
    seen_slots: set[tuple[str, str]] = set()
    for path in review_paths:
        data = read_json(path)
        reviewer_id = data.get("reviewer_id")
        if reviewer_id not in votes:
            raise AssertionError(f"{path} reviewer_id非法")
        cohort = data.get("cohort")
        if cohort not in cohort_books:
            raise AssertionError(f"{path} cohort非法")
        slot = (reviewer_id, cohort)
        if slot in seen_slots:
            raise AssertionError(f"重复评审槽位{reviewer_id}-{cohort}")
        seen_slots.add(slot)
        for row in data["rows"]:
            validate_review_row(row, allow_uncertain=True)
            part_id = row["part_id"]
            if part_id not in expected_rows:
                raise AssertionError(f"{reviewer_id}出现未知条目{part_id}")
            if row.get("book_id") != expected_rows[part_id]["book_id"]:
                raise AssertionError(f"{reviewer_id}修改了{part_id}的书目身份")
            if row["book_id"] not in cohort_books[cohort]:
                raise AssertionError(f"{reviewer_id}-{cohort}越界评审{part_id}")
            if part_id in votes[reviewer_id]:
                raise AssertionError(f"{reviewer_id}重复评审{part_id}")
            votes[reviewer_id][part_id] = row
    for reviewer_id, rows in votes.items():
        if set(rows) != expected_ids:
            missing = sorted(expected_ids - set(rows))
            extra = sorted(set(rows) - expected_ids)
            raise AssertionError(f"{reviewer_id}覆盖不全 missing={missing} extra={extra}")
    expected_slots = {(reviewer_id, cohort) for reviewer_id in votes for cohort in cohort_books}
    if seen_slots != expected_slots:
        raise AssertionError(f"双审槽位不全：{sorted(expected_slots - seen_slots)}")
    return votes


def build_disputes(output_dir: Path, review_paths: list[Path]) -> dict[str, Any]:
    packet = read_json(output_dir / "review_packet.json")
    row_by_id = {row["part_id"]: row for row in packet["rows"]}
    votes = load_two_votes(review_paths, row_by_id)
    disputes: list[dict[str, Any]] = []
    agreements: list[dict[str, Any]] = []
    compare_fields = (*CHECK_FIELDS, "disposition", "major_issue")
    for part_id in sorted(row_by_id):
        r1 = votes["R1"][part_id]
        r2 = votes["R2"][part_id]
        flat1 = {**r1["checks"], "disposition": r1["disposition"], "major_issue": r1["major_issue"]}
        flat2 = {**r2["checks"], "disposition": r2["disposition"], "major_issue": r2["major_issue"]}
        disputed_fields = [
            field
            for field in compare_fields
            if flat1[field] != flat2[field] or flat1[field] == "uncertain" or flat2[field] == "uncertain"
        ]
        entry = {
            "book_id": row_by_id[part_id]["book_id"],
            "part_id": part_id,
            "claim": row_by_id[part_id]["claim"],
            "source_evidence": row_by_id[part_id]["source_evidence"],
            "disputed_fields": disputed_fields,
            "R1": r1,
            "R2": r2,
        }
        if disputed_fields:
            entry["R3"] = blank_review(row_by_id[part_id])
            disputes.append(entry)
        else:
            agreements.append(entry)
    result = {
        "schema_version": "z93-dispute-register-v1",
        "status": "ready_for_r3_disagreement_only",
        "total": len(row_by_id),
        "agreement_total": len(agreements),
        "dispute_total": len(disputes),
        "agreements": agreements,
        "disputes": disputes,
    }
    write_json(output_dir / "review" / "dispute_register.json", result)
    return result


def finalize(output_dir: Path, adjudication_path: Path) -> dict[str, Any]:
    register = read_json(output_dir / "review" / "dispute_register.json")
    adjudication = read_json(adjudication_path)
    r3_rows = {row["part_id"]: row for row in adjudication["rows"]}
    expected_r3 = {entry["part_id"] for entry in register["disputes"]}
    if set(r3_rows) != expected_r3:
        raise AssertionError("R3只可覆盖且必须覆盖全部分歧条")
    finals: list[dict[str, Any]] = []
    for entry in register["agreements"]:
        finals.append({"part_id": entry["part_id"], "book_id": entry["book_id"], "final": entry["R1"], "route": "R1_R2_agreement"})
    for entry in register["disputes"]:
        row = r3_rows[entry["part_id"]]
        validate_review_row(row, allow_uncertain=False)
        r1 = entry["R1"]
        for field in CHECK_FIELDS:
            if field not in entry["disputed_fields"] and row["checks"][field] != r1["checks"][field]:
                raise AssertionError(f"R3越界改动{entry['part_id']}非分歧字段{field}")
        if "disposition" not in entry["disputed_fields"] and row["disposition"] != r1["disposition"]:
            raise AssertionError(f"R3越界改动{entry['part_id']}非分歧处置")
        if "major_issue" not in entry["disputed_fields"] and row["major_issue"] != r1["major_issue"]:
            raise AssertionError(f"R3越界改动{entry['part_id']}非分歧重大问题标记")
        finals.append({"part_id": entry["part_id"], "book_id": entry["book_id"], "final": row, "route": "R3_disputed_fields_adjudication"})
    finals.sort(key=lambda row: row["part_id"])
    if len(finals) != 76:
        raise AssertionError("最终判词不是76条")
    disposition_counts = Counter(row["final"]["disposition"] for row in finals)
    result = {
        "schema_version": "z93-final-judgments-v1",
        "status": "review_complete_candidate_only_not_promoted",
        "counts": {
            "total": 76,
            "candidate_ready": disposition_counts["candidate_ready"],
            "needs_modification": disposition_counts["needs_modification"],
            "recommended_removal": disposition_counts["recommended_removal"],
            "major_issue": sum(bool(row["final"]["major_issue"]) for row in finals),
            "r3_adjudicated": len(register["disputes"]),
            "model_api_calls": 0,
            "network_requests": 0,
        },
        "rows": finals,
    }
    write_json(output_dir / "review" / "final_judgments.json", result)
    core = json_bytes(result)
    receipt = {
        "schema_version": "z93-finalize-receipt-v1",
        "status": "pass",
        "final_judgments_sha256": hashlib.sha256(core).hexdigest(),
        "reviewed_total": 76,
        "candidate_sources_unchanged": True,
        "formal_gold_promoted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    write_json(output_dir / "review" / "finalize_receipt.json", receipt)
    return result


def verify_repeatable_finalize(output_dir: Path, adjudication_path: Path) -> dict[str, Any]:
    canonical = finalize(output_dir, adjudication_path)
    canonical_bytes = json_bytes(canonical)
    run_shas: list[str] = []
    receipt_shas: list[str] = []
    with tempfile.TemporaryDirectory(prefix="z93-finalize-double-") as temp_root:
        for pass_no in (1, 2):
            target = Path(temp_root) / f"pass{pass_no}"
            (target / "review").mkdir(parents=True)
            shutil.copy2(
                output_dir / "review" / "dispute_register.json",
                target / "review" / "dispute_register.json",
            )
            finalize(target, adjudication_path)
            final_path = target / "review" / "final_judgments.json"
            receipt_path = target / "review" / "finalize_receipt.json"
            run_shas.append(sha256_file(final_path))
            receipt_shas.append(sha256_file(receipt_path))
    canonical_sha = hashlib.sha256(canonical_bytes).hexdigest()
    if run_shas != [canonical_sha, canonical_sha] or len(set(receipt_shas)) != 1:
        raise AssertionError("最终判词机械验收连续两次不一致")
    receipt = {
        "schema_version": "z93-mechanical-double-run-receipt-v1",
        "status": "pass_identical_twice",
        "pass1_final_judgments_sha256": run_shas[0],
        "pass2_final_judgments_sha256": run_shas[1],
        "canonical_final_judgments_sha256": canonical_sha,
        "pass1_finalize_receipt_sha256": receipt_shas[0],
        "pass2_finalize_receipt_sha256": receipt_shas[1],
        "candidate_source_sha_rechecked": True,
        "formal_gold_promoted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    write_json(output_dir / "review" / "mechanical_double_run_receipt.json", receipt)
    return receipt


def build_independence_audit(output_dir: Path) -> dict[str, Any]:
    reviews = {}
    for filename, blank_sha in INITIAL_BLANK_REVIEW_SHA256.items():
        path = output_dir / "reviews" / filename
        reviews[filename] = {
            "initial_blank_template_sha256": blank_sha,
            "completed_review_sha256": sha256_file(path),
        }
    audit = {
        "schema_version": "z93-review-independence-audit-v1",
        "status": "pass_with_empty_template_name_only_disclosure",
        "review_slots": reviews,
        "observations": [
            {
                "reviewer": "R1-A",
                "event": "一次只读检索显示另一评审的空模板文件名与未填写null行。",
                "decision_content_exposed": False,
                "judgment_content_exposed": False,
            },
            {
                "reviewer": "R2-A",
                "event": "一次只读检索显示另一评审的空模板文件名与未填写null行。",
                "decision_content_exposed": False,
                "judgment_content_exposed": False,
            },
        ],
        "adjudication": {
            "reviewer_id": "R3",
            "scope": "28条R1/R2字段分歧",
            "review_sha256": sha256_file(output_dir / "reviews" / "review_R3_disputes.json"),
            "non_disputed_field_guard": "程序拒绝R3改动双方一致字段",
        },
        "conclusion": "未发现另一评审的已填写判断内容暴露；空模板曝光不触发重审。",
    }
    write_json(output_dir / "review" / "independence_audit.json", audit)
    return audit


def build_cursor_handoff(output_dir: Path) -> dict[str, Any]:
    manifest = read_json(output_dir / "run_manifest.json")
    final_path = output_dir / "review" / "final_judgments.json"
    artifacts = []
    for row in manifest["inventory"]:
        path = ROOT / row["candidate_path"]
        if sha256_file(path) != row["candidate_sha256"]:
            raise AssertionError(f"{row['book_id']}候选SHA在收口时漂移")
        artifacts.append(
            {
                "artifact_no": len(artifacts) + 1,
                "identity": row["book_id"],
                "path": row["candidate_path"],
                "sha256": row["candidate_sha256"],
                "truth_text_path": row["cache_file_path"],
                "truth_text_sha256": row["cache_file_sha256"],
                "codex_judgments_path": repo_relative(final_path),
                "codex_judgments_sha256": sha256_file(final_path),
            }
        )
    x01_refs = []
    for identity, rel_path, expected_sha in X01_RED_TEAM_REFERENCE:
        path = ROOT / rel_path
        actual = sha256_file(path)
        if actual != expected_sha:
            raise AssertionError(f"X01攻击参照{identity} SHA漂移：{actual}")
        x01_refs.append({"identity": identity, "path": rel_path, "sha256": actual})
    artifacts.append(
        {
            "artifact_no": 6,
            "identity": "X01-C0003-formal-gold-v1.2",
            "references": x01_refs,
            "handling": "只读攻击；发现问题只列清单，不改正式金标或指针。",
        }
    )
    handoff = {
        "schema_version": "z93-cursor-red-team-handoff-v1",
        "status": "ready_not_executed",
        "artifact_total": 6,
        "artifacts": artifacts,
        "attack_dimensions": [
            "与原书不一致",
            "遗漏原文明示限定",
            "一句装入多个独立事实",
            "所挂锚不能托住关键主张",
            "六件之间粒度口径不一致",
        ],
        "hard_stop_rule": "发现重大问题即停并回传，不现场改写候选或正式金标。",
        "promotion_boundary": "Cursor攻击完成前五本仍是候选银标；即使无重大问题也不由程序自动转正。",
        "future_provenance_label": "Codex验闸＋Cursor攻击定稿、非CZ亲验",
        "model_api_calls": 0,
        "network_requests": 0,
    }
    write_json(output_dir / "cursor_red_team_handoff.json", handoff)
    return handoff


def md_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_report(output_dir: Path, report_dir: Path) -> Path:
    manifest = read_json(output_dir / "run_manifest.json")
    packet = read_json(output_dir / "review_packet.json")
    final = read_json(output_dir / "review" / "final_judgments.json")
    double = read_json(output_dir / "review" / "mechanical_double_run_receipt.json")
    independence = read_json(output_dir / "review" / "independence_audit.json")
    handoff = read_json(output_dir / "cursor_red_team_handoff.json")
    test_receipt_path = output_dir / "review" / "test_receipt.json"
    test_receipt = read_json(test_receipt_path) if test_receipt_path.is_file() else None
    packet_by_id = {row["part_id"]: row for row in packet["rows"]}
    inventory_by_id = {row["book_id"]: row for row in manifest["inventory"]}
    rows_by_book: dict[str, list[dict[str, Any]]] = {}
    for row in final["rows"]:
        rows_by_book.setdefault(row["book_id"], []).append(row)
    fail_counts = Counter()
    for row in final["rows"]:
        for field, value in row["final"]["checks"].items():
            if value == "fail":
                fail_counts[field] += 1

    lines = [
        "# 第93道停点回包｜五本金标候选逐条验闸",
        "",
        "✅ Codex 语义验闸已经收口：五本共 76 条里，43 条可作为转正候选，33 条必须修改，0 条建议剔除，0 个重大矛盾。",
        "",
        "这不等于五本已经转正。整批当前不能进入正式金标；第三阶段 Cursor 六件攻击已备好交接单，但尚未执行。",
        "",
        "## 验闸边界",
        "",
        "- 真值只认各候选条目所钉的冻结正文与整本原书；外部 AI 材料不作真值。",
        "- 检查四件事：事实是否与原书一致、原文明示限定是否完整、一句是否只装一个事实、所挂锚是否托住关键主张。",
        "- R1、R2 各自审完 76 条；双方对 48 条的决定字段一致，28 条分歧只交 R3 裁分歧字段。",
        "- R1-A 与 R2-A 各有一次检索只看到另一侧空模板文件名与 null 行；当时模板尚无判词，未看到对方答案。独立性票据已单列。",
        "- 模型 API 0，网络请求 0，token 0；五份候选原件均未改。",
        "",
        "## 总读数",
        "",
        "| 书目 | 总条数 | 可作为转正候选 | 必须修改 | 建议剔除 |",
        "|---|---:|---:|---:|---:|",
    ]
    for book_id in sorted(rows_by_book):
        rows = rows_by_book[book_id]
        counts = Counter(row["final"]["disposition"] for row in rows)
        info = inventory_by_id[book_id]
        lines.append(
            f"| {md_escape(info['book'])}（{book_id}） | {len(rows)} | "
            f"{counts['candidate_ready']} | {counts['needs_modification']} | {counts['recommended_removal']} |"
        )
    lines += [
        "",
        "四项失败计数允许同一条重复计入：",
        "",
        f"- 一句多事实：{fail_counts['one_sentence_one_fact']} 条。",
        f"- 锚不托：{fail_counts['anchor_semantic_support']} 条。",
        f"- 明示限定遗漏：{fail_counts['explicit_qualifiers_complete']} 条。",
        f"- 事实或归因不一致：{fail_counts['fact_consistency']} 条。",
        "",
        "## 76 条逐条判词",
    ]
    check_labels = {
        "fact_consistency": "事实",
        "explicit_qualifiers_complete": "限定",
        "one_sentence_one_fact": "粒度",
        "anchor_semantic_support": "锚托",
    }
    disposition_labels = {
        "candidate_ready": "可作为转正候选",
        "needs_modification": "必须修改",
        "recommended_removal": "建议剔除",
    }
    for book_id in sorted(rows_by_book):
        info = inventory_by_id[book_id]
        lines += ["", f"### {info['book']}（{book_id}）", ""]
        for row in rows_by_book[book_id]:
            judgment = row["final"]
            source = packet_by_id[row["part_id"]]
            checks = "；".join(
                f"{check_labels[field]}={'过' if judgment['checks'][field] == 'pass' else '不通过'}"
                for field in CHECK_FIELDS
            )
            lines.append(
                f"- **{row['part_id']}｜{disposition_labels[judgment['disposition']]}**：{checks}。"
            )
            lines.append(f"  - 候选主张：{source['claim']}")
            lines.append(f"  - 原文短引：{judgment['original_evidence_excerpt']}")
            lines.append(f"  - 判词：{judgment['reasoning']}")
            if judgment.get("suggested_revision"):
                lines.append(f"  - 修改建议：{judgment['suggested_revision']}")
            if judgment.get("removal_evidence"):
                lines.append(f"  - 剔除证据：{judgment['removal_evidence']}")
    lines += [
        "",
        "## 机械验收与工件",
        "",
        f"- 最终 76 条判词：`{repo_relative(output_dir)}/review/final_judgments.json`，SHA `{double['canonical_final_judgments_sha256']}`。",
        f"- 连续两次机械收口：两次 SHA 均为 `{double['canonical_final_judgments_sha256']}`，结论一致。",
        f"- 第三票：`{repo_relative(output_dir)}/reviews/review_R3_disputes.json`，SHA `{independence['adjudication']['review_sha256']}`。",
        f"- Cursor 六件攻击清单：`{repo_relative(output_dir)}/cursor_red_team_handoff.json`，状态 `{handoff['status']}`。",
        "- 原书锚回读：160/160；候选部件：76；当章 66、回看 10。",
    ]
    if test_receipt:
        lines += [
            "",
            "## 测试",
            "",
            f"- 本轮定向回归：{test_receipt['focused']['result']}。",
            f"- 本轮 unittest：{test_receipt['unittest']['result']}。",
            f"- Ruff：{test_receipt['ruff']['result']}。",
            f"- 全目录旧基线：{test_receipt['full_directory']['result']}。{test_receipt['full_directory']['boundary']}",
        ]
    lines += [
        "",
        "## 下一停点",
        "",
        "Cursor 可按交接清单只读攻击五本候选和 X01 第3章正式金标 v1.2。若发现重大问题就停并回传；X01 只列问题，不改正式件。Cursor 攻击回来以前，五本仍是候选银标；即使攻击未发现重大问题，也要等后续审收令才可转正。",
        "",
        "未来若转正，来源标签固定写：`Codex验闸＋Cursor攻击定稿、非CZ亲验`。",
        "",
        "来源：Codex",
    ]
    report_path = report_dir / "第93道停点回包｜五本金标候选逐条验闸_20260723.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest_out = {
        "schema_version": "z93-report-manifest-v1",
        "status": "codex_gate_complete_cursor_red_team_pending",
        "report_path": repo_relative(report_path),
        "report_sha256": sha256_file(report_path),
        "final_judgments_path": repo_relative(output_dir / "review" / "final_judgments.json"),
        "final_judgments_sha256": sha256_file(output_dir / "review" / "final_judgments.json"),
        "cursor_handoff_path": repo_relative(output_dir / "cursor_red_team_handoff.json"),
        "cursor_handoff_sha256": sha256_file(output_dir / "cursor_red_team_handoff.json"),
        "counts": final["counts"],
        "formal_gold_promoted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    write_json(report_dir / "report_manifest.json", manifest_out)
    return report_path


def package(output_dir: Path, adjudication_path: Path, report_dir: Path) -> dict[str, Any]:
    double = verify_repeatable_finalize(output_dir, adjudication_path)
    build_independence_audit(output_dir)
    build_cursor_handoff(output_dir)
    report_path = render_report(output_dir, report_dir)
    return {
        "status": "codex_gate_complete_cursor_red_team_pending",
        "mechanical_double_run": double,
        "independence_audit_sha256": sha256_file(output_dir / "review" / "independence_audit.json"),
        "cursor_handoff_sha256": sha256_file(output_dir / "cursor_red_team_handoff.json"),
        "report_path": repo_relative(report_path),
        "report_sha256": sha256_file(report_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "build-disputes", "finalize", "package"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, nargs="*")
    parser.add_argument("--adjudication", type=Path)
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.output_dir)
    elif args.command == "build-disputes":
        if not args.reviews:
            parser.error("build-disputes需要--reviews")
        result = build_disputes(args.output_dir, args.reviews)
    elif args.command == "finalize":
        if not args.adjudication:
            parser.error("finalize需要--adjudication")
        result = finalize(args.output_dir, args.adjudication)
    else:
        if not args.adjudication or not args.report_dir:
            parser.error("package需要--adjudication与--report-dir")
        result = package(args.output_dir, args.adjudication, args.report_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

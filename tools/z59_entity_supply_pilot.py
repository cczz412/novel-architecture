#!/usr/bin/env python3
"""第59道：模拟实体供料、抽取注入臂与大纲逻辑双臂旁路试点。

这个工具不修改默认 runner。件⓪只读前20章正文；试点A复用第56道冻结证据目录；
试点B复用第56道233条中性事件池。所有 API 工件都写进独立 run 目录。
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import hashlib
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from zbatch_modules import api_transport  # noqa: E402
from zbatch_modules import candidate_envelope  # noqa: E402
from zbatch_modules import neutral_extract  # noqa: E402
from zbatch_modules import prompt_render_pin  # noqa: E402
from zbatch_modules import stage_sampling  # noqa: E402
from zbatch_modules.errors import ZBatchError  # noqa: E402


TARGET_CHAPTERS = (3, 4, 5, 13, 19)
RULES_PATH = ROOT / "config/experiments/Z59_模拟实体供料规则_v1.json"
RUBRIC_PATH = ROOT / "config/experiments/Z59_第3章抽取评分预写尺_v1.json"
B_SEMANTIC_RUBRIC_PATH = ROOT / "config/experiments/Z60_大纲逻辑双臂语义复核尺_v1.json"
OUTLINE_PROMPT_PATH = ROOT / "work/zbatch_prompts/candidates/z59_outline_logic_base_v1.md"
DEFAULT_REGISTRY = ROOT / "config/defaults/zbatch_v1.2_full_chain.json"
SAMPLING_CONTRACT = ROOT / "config/contracts/sensenova_stage_sampling_v1.json"
PROVIDER_CONFIG = ROOT / "config/providers/sensenova_modular_v1.json"
SOURCE_RUN = ROOT / "runs/Z56b_X01_端到端全链体检_提取20章_v1.0_20260719"
GOLD_V1_1 = ROOT / "reports/Z56_金标双轨分层与全链体检_20260719/第3章结构层金标v1.1.json"
CURRENT_122 = ROOT / "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json"
OUTBOX = ROOT / "outbox"

SUPPLY_SCHEMA = "z59-entity-supply-v1"
OUTLINE_SCHEMA = "z59-outline-logic-v1"
OUTLINE_SYSTEM_MESSAGE = "你只把已落盘的中性事件编排成可核对的大纲逻辑句，不补写正文事实。只输出合法 JSON。"
ENTITY_BLOCK_HEADER = "【模拟上游实体供料｜前20章窗口；本章实体过滤】"
B_LOGICAL_CASES = len(TARGET_CHAPTERS) * 2
B_NETWORK_RETRY_SLACK = 3
B_MAX_NETWORK_ATTEMPTS = B_LOGICAL_CASES + B_NETWORK_RETRY_SLACK
ALLOWED_CATEGORIES = {"人物", "地名", "势力", "流派", "秘术", "称号", "事例", "特殊概念"}
ALLOWED_TABLES = ("人物演员表", "地名表", "事例／概念表")

EXPECTED_PROTECTED_SHA = {
    GOLD_V1_1: "8cca04f06ba21048e15420f178163c646d2effeead0970697fafbf5f45174b7c",
    CURRENT_122: "dafa16901a6edb5018a5176f3f5f7388273e72051def7fe4e997489d01e804ba",
    DEFAULT_REGISTRY: "b23b5cce26b9cfe584dd97dbff6422efa2b22ccd5cba38c6ed6a44c4543bc0a1",
}


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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def tree_fingerprint(path: Path) -> dict[str, Any]:
    rows: list[tuple[str, str, int]] = []
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        rows.append((item.relative_to(path).as_posix(), sha256_file(item), item.stat().st_size))
    wire = "\n".join(f"{name}\t{digest}\t{size}" for name, digest, size in rows)
    return {
        "kind": "directory",
        "files": len(rows),
        "bytes": sum(size for _, _, size in rows),
        "sha256": sha256_bytes(wire.encode("utf-8")),
    }


def assert_protected() -> dict[str, str]:
    observed: dict[str, str] = {}
    for path, expected in EXPECTED_PROTECTED_SHA.items():
        actual = sha256_file(path)
        if actual != expected:
            raise ZBatchError(f"保护件SHA漂移：{rel(path)}，预期 {expected}，实际 {actual}")
        observed[rel(path)] = actual
    return observed


def outbox_fingerprint() -> dict[str, Any]:
    return tree_fingerprint(OUTBOX)


def ensure_new_directory(path: Path) -> None:
    if path.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{path}")
    path.mkdir(parents=True)


def strip_exported_header(text: str, chapter: int) -> str:
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and re.match(rf"^第{chapter}章\s+第{chapter}章", lines[0].strip()):
        lines.pop(0)
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and re.match(rf"^第{chapter}章", lines[0].strip().lstrip("　")):
        lines.pop(0)
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines).rstrip() + "\n"


def load_rules(path: Path = RULES_PATH) -> dict[str, Any]:
    rules = read_json(path)
    if rules.get("schema_version") != "z59-entity-supply-rules-v1":
        raise ZBatchError("第59道实体规则schema错误")
    entities = rules.get("entities")
    if not isinstance(entities, list) or not entities:
        raise ZBatchError("第59道实体规则没有实体")
    seen_ids: set[str] = set()
    for entity in entities:
        if not isinstance(entity, dict):
            raise ZBatchError("实体规则行不是对象")
        entity_id = entity.get("entity_id")
        if not isinstance(entity_id, str) or entity_id in seen_ids:
            raise ZBatchError(f"实体ID非法或重复：{entity_id}")
        seen_ids.add(entity_id)
        if entity.get("category") not in ALLOWED_CATEGORIES:
            raise ZBatchError(f"实体类别非法：{entity_id}")
        if entity.get("table") not in ALLOWED_TABLES:
            raise ZBatchError(f"实体表归属非法：{entity_id}")
        if entity.get("category") == "人物" and entity.get("table") != "人物演员表":
            raise ZBatchError(f"人物没有进入演员表：{entity_id}")
        if entity.get("category") == "地名" and entity.get("table") != "地名表":
            raise ZBatchError(f"地名没有进入地名表：{entity_id}")
        surfaces = entity.get("surfaces")
        if not isinstance(surfaces, list) or not surfaces:
            raise ZBatchError(f"实体没有识别词面：{entity_id}")
        texts: list[str] = []
        for surface in surfaces:
            if not isinstance(surface, dict) or not isinstance(surface.get("text"), str) or not surface["text"]:
                raise ZBatchError(f"实体词面非法：{entity_id}")
            text = surface["text"]
            if text in texts:
                raise ZBatchError(f"实体词面重复：{entity_id}/{text}")
            texts.append(text)
            chapters = surface.get("chapters")
            if chapters is not None and (
                not isinstance(chapters, list)
                or not chapters
                or any(isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= 20 for number in chapters)
            ):
                raise ZBatchError(f"实体词面章范围非法：{entity_id}/{text}")
        if entity.get("canonical") not in texts:
            raise ZBatchError(f"规范名未进入识别词面：{entity_id}")
    policy = rules["source_policy"]
    alias_path = ROOT / policy["alias_candidate_path"]
    if sha256_file(alias_path) != policy["alias_candidate_sha256"]:
        raise ZBatchError("47行别名候选源SHA漂移")
    return rules


def load_chapters(rules: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    start = int(rules["source_window"]["chapter_start"])
    end = int(rules["source_window"]["chapter_end"])
    chapter_dir = ROOT / rules["source_window"]["chapter_dir"]
    result: dict[int, dict[str, Any]] = {}
    for chapter in range(start, end + 1):
        hits = sorted(chapter_dir.glob(f"{chapter:04d}_*.txt"))
        if len(hits) != 1:
            raise ZBatchError(f"第{chapter}章正文文件不是唯一一份：{hits}")
        path = hits[0]
        raw = path.read_text(encoding="utf-8")
        body = strip_exported_header(raw, chapter) if rules["source_window"]["strip_exported_chapter_headers"] else raw
        result[chapter] = {
            "path": path,
            "filename": path.name,
            "source_sha256": sha256_file(path),
            "body_sha256": sha256_bytes(body.encode("utf-8")),
            "body": body,
        }
    return result


@dataclasses.dataclass(frozen=True)
class Match:
    chapter: int
    entity_id: str
    surface: str
    start: int
    end: int


def raw_matches_for_chapter(chapter: int, text: str, entities: Iterable[Mapping[str, Any]]) -> list[Match]:
    candidates: list[Match] = []
    for entity in entities:
        entity_id = str(entity["entity_id"])
        for surface_rule in entity["surfaces"]:
            allowed = surface_rule.get("chapters")
            if allowed is not None and chapter not in allowed:
                continue
            surface = str(surface_rule["text"])
            start = 0
            while True:
                index = text.find(surface, start)
                if index < 0:
                    break
                candidates.append(Match(chapter, entity_id, surface, index, index + len(surface)))
                start = index + 1
    by_span: dict[tuple[int, int], set[str]] = defaultdict(set)
    for match in candidates:
        by_span[(match.start, match.end)].add(match.entity_id)
    conflicts = {span: ids for span, ids in by_span.items() if len(ids) > 1}
    if conflicts:
        raise ZBatchError(f"等长同位词面映射多个实体：第{chapter}章 {conflicts}")
    selected: list[Match] = []
    occupied: set[int] = set()
    for match in sorted(candidates, key=lambda row: (-(row.end - row.start), row.start, row.entity_id, row.surface)):
        positions = set(range(match.start, match.end))
        if positions & occupied:
            continue
        selected.append(match)
        occupied.update(positions)
    return sorted(selected, key=lambda row: (row.start, row.end, row.entity_id))


def compress_ranges(chapters: list[int], *, window_start: int = 1, window_end: int = 20) -> str:
    unique = sorted(set(chapters))
    if not unique:
        return "窗口内无出现"
    ranges: list[tuple[int, int]] = []
    start = previous = unique[0]
    for chapter in unique[1:]:
        if chapter == previous + 1:
            previous = chapter
            continue
        ranges.append((start, previous))
        start = previous = chapter
    ranges.append((start, previous))
    rendered = "、".join(str(start) if start == end else f"{start}～{end}" for start, end in ranges)
    if unique == list(range(window_start, window_end + 1)):
        return f"{window_start}～{window_end}全出现"
    return rendered


def entity_display_name(entity: Mapping[str, Any], observed_surfaces: set[str]) -> tuple[str, list[str]]:
    canonical = str(entity["canonical"])
    aliases = [str(value) for value in entity.get("aliases") or [] if str(value) in observed_surfaces]
    return "＝".join([canonical, *aliases]), aliases


def render_entity_block(chapter_payload: Mapping[str, Any]) -> str:
    lines = [ENTITY_BLOCK_HEADER, f"窗口：第1～20章；当前章：第{chapter_payload['chapter']}章。", ""]
    for table in ALLOWED_TABLES:
        lines.append(table)
        rows = chapter_payload["tables"][table]
        if not rows:
            lines.append("- （本章无）")
        for row in rows:
            grade = f"｜分级：{row['importance']}" if row.get("importance") else ""
            lines.append(
                f"- {row['display_name']}｜类别：{row['category']}{grade}"
                f"｜全程出现范围：{row['window_range']}｜窗口出现次数：{row['window_occurrence_count']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def audit_alias_candidates(
    rules: Mapping[str, Any],
    chapters: Mapping[int, Mapping[str, Any]],
    accepted_ids: set[str],
    observed_surfaces_by_entity: Mapping[str, set[str]],
) -> dict[str, Any]:
    source = ROOT / rules["source_policy"]["alias_candidate_path"]
    rows = read_jsonl(source)
    surface_to_entities: dict[str, set[str]] = defaultdict(set)
    for entity in rules["entities"]:
        for surface in entity["surfaces"]:
            surface_to_entities[str(surface["text"])].add(str(entity["entity_id"]))
    audited: list[dict[str, Any]] = []
    counts = Counter()
    for index, row in enumerate(rows, 1):
        candidate_surfaces = [str(row.get("canonical") or ""), *[str(value) for value in row.get("aliases") or []]]
        hits: list[dict[str, Any]] = []
        rule_overlap: list[dict[str, Any]] = []
        for surface in candidate_surfaces:
            if not surface:
                continue
            chapter_hits = {
                str(chapter): data["body"].count(surface)
                for chapter, data in chapters.items()
                if surface in data["body"]
            }
            if chapter_hits:
                hits.append({"surface": surface, "chapter_counts": chapter_hits, "total": sum(chapter_hits.values())})
            for entity_id in sorted(surface_to_entities.get(surface, set())):
                rule_overlap.append(
                    {
                        "surface": surface,
                        "entity_id": entity_id,
                        "accepted_entity": entity_id in accepted_ids,
                        "observed_after_scope": surface in observed_surfaces_by_entity.get(entity_id, set()),
                    }
                )
        observed_overlap_ids = {
            item["entity_id"]
            for item in rule_overlap
            if item["observed_after_scope"]
        }
        accepted_overlap_ids = {
            item["entity_id"]
            for item in rule_overlap
            if item["accepted_entity"] and item["observed_after_scope"]
        }
        if not hits:
            disposition = "not_used_no_front20_literal_hit"
            identity_group_status = "no_literal_hit"
        elif len(observed_overlap_ids) > 1:
            disposition = "not_used_cross_entity_identity_conflict"
            identity_group_status = "cross_entity_conflict"
        elif not accepted_overlap_ids:
            disposition = "not_used_literal_hit_but_not_in_accepted_same_identity_rule"
            identity_group_status = "no_accepted_same_identity_group"
        else:
            disposition = "candidate_surface_reverified_but_row_not_blindly_imported"
            identity_group_status = "one_accepted_same_identity_group"
        counts[disposition] += 1
        audited.append(
            {
                "row_number": index,
                "canonical": row.get("canonical"),
                "aliases": row.get("aliases") or [],
                "literal_hits": hits,
                "same_identity_rule_overlap": rule_overlap,
                "identity_group_status": identity_group_status,
                "disposition": disposition,
                "note": (
                    "候选词面跨本轮多个语义实体，禁止自动并组或导入。"
                    if disposition == "not_used_cross_entity_identity_conflict"
                    else "47行表只作候选；实际供料以本轮规则和前20章正文最长词面复核为准。"
                ),
            }
        )
    return {
        "schema_version": "z59-alias-candidate-audit-v1",
        "source": {"path": rel(source), "sha256": sha256_file(source), "rows": len(rows)},
        "summary": dict(sorted(counts.items())),
        "rows": audited,
    }


def build_supply(output_dir: Path, *, rules_path: Path = RULES_PATH) -> dict[str, Any]:
    ensure_new_directory(output_dir)
    rules = load_rules(rules_path)
    chapters = load_chapters(rules)
    all_matches: list[Match] = []
    for chapter, data in chapters.items():
        all_matches.extend(raw_matches_for_chapter(chapter, data["body"], rules["entities"]))
    matches_by_entity: dict[str, list[Match]] = defaultdict(list)
    for match in all_matches:
        matches_by_entity[match.entity_id].append(match)

    min_person = int(rules["recognition_policy"]["person_min_window_mentions"])
    min_person_chapters = int(rules["recognition_policy"]["person_min_distinct_chapters"])
    min_nonperson = int(rules["recognition_policy"]["nonperson_min_window_mentions"])
    inventory: list[dict[str, Any]] = []
    accepted_ids: set[str] = set()
    observed_surfaces_by_entity: dict[str, set[str]] = {}
    for entity in rules["entities"]:
        entity_id = str(entity["entity_id"])
        matches = matches_by_entity.get(entity_id, [])
        observed_surfaces = {match.surface for match in matches}
        observed_surfaces_by_entity[entity_id] = observed_surfaces
        chapters_seen = sorted({match.chapter for match in matches})
        threshold = min_person if entity["category"] == "人物" else min_nonperson
        accepted = bool(matches) and (
            entity_id == "PER-001"
            or entity["category"] != "人物"
            or (len(matches) >= threshold and len(chapters_seen) >= min_person_chapters)
        )
        if accepted:
            accepted_ids.add(entity_id)
        display_name, aliases = entity_display_name(entity, observed_surfaces)
        inventory.append(
            {
                "entity_id": entity_id,
                "canonical": entity["canonical"],
                "verified_aliases": aliases,
                "display_name": display_name,
                "category": entity["category"],
                "table": entity["table"],
                "importance": entity.get("importance"),
                "accepted": accepted,
                "disposition": "accepted" if accepted else ("low_frequency_or_single_chapter_cameo" if matches else "no_front20_match"),
                "window_occurrence_count": len(matches),
                "occurrence_chapters": chapters_seen,
                "window_range": compress_ranges(chapters_seen),
                "observed_surfaces": sorted(observed_surfaces),
                "occurrences": [dataclasses.asdict(match) for match in matches],
            }
        )

    inventory_by_id = {row["entity_id"]: row for row in inventory}
    chapter_counts: dict[str, dict[str, int]] = {}
    for chapter in chapters:
        payload: dict[str, Any] = {
            "schema_version": SUPPLY_SCHEMA,
            "chapter": chapter,
            "window": {"start": 1, "end": 20},
            "source_chapter": {
                "path": rel(chapters[chapter]["path"]),
                "source_sha256": chapters[chapter]["source_sha256"],
                "body_sha256_after_header_strip": chapters[chapter]["body_sha256"],
            },
            "tables": {table: [] for table in ALLOWED_TABLES},
        }
        present_ids = sorted(
            {
                match.entity_id
                for match in all_matches
                if match.chapter == chapter and match.entity_id in accepted_ids
            }
        )
        for entity_id in present_ids:
            row = inventory_by_id[entity_id]
            current_matches = [match for match in matches_by_entity[entity_id] if match.chapter == chapter]
            payload["tables"][row["table"]].append(
                {
                    "entity_id": entity_id,
                    "display_name": row["display_name"],
                    "canonical": row["canonical"],
                    "verified_aliases": row["verified_aliases"],
                    "category": row["category"],
                    "importance": row["importance"],
                    "window_range": row["window_range"],
                    "window_occurrence_count": row["window_occurrence_count"],
                    "current_chapter_occurrence_count": len(current_matches),
                    "current_chapter_surfaces": sorted({match.surface for match in current_matches}),
                }
            )
        for table in ALLOWED_TABLES:
            payload["tables"][table].sort(key=lambda row: row["entity_id"])
        block = render_entity_block(payload)
        payload["rendered_block_sha256"] = sha256_bytes(block.encode("utf-8"))
        write_json(output_dir / "chapters" / f"ch{chapter:04d}.json", payload)
        write_text(output_dir / "rendered" / f"ch{chapter:04d}.txt", block)
        write_text(output_dir / "rendered" / f"ch{chapter:04d}.md", block + "\n来源：Codex\n")
        chapter_counts[str(chapter)] = {
            "人物演员表": len(payload["tables"]["人物演员表"]),
            "地名表": len(payload["tables"]["地名表"]),
            "事例／概念表": len(payload["tables"]["事例／概念表"]),
            "total": sum(len(payload["tables"][table]) for table in ALLOWED_TABLES),
        }

    alias_audit = audit_alias_candidates(rules, chapters, accepted_ids, observed_surfaces_by_entity)
    source_manifest = {
        "schema_version": "z59-entity-source-manifest-v1",
        "created_at": now_iso(),
        "model_api_calls": 0,
        "rules": {"path": rel(rules_path), "sha256": sha256_file(rules_path)},
        "script": {"path": rel(Path(__file__)), "sha256": sha256_file(Path(__file__))},
        "chapter_sources": [
            {
                "chapter": chapter,
                "path": rel(data["path"]),
                "source_sha256": data["source_sha256"],
                "body_sha256_after_header_strip": data["body_sha256"],
            }
            for chapter, data in chapters.items()
        ],
        "forbidden_sources_read": [],
        "source_boundary": "件⓪只读前20章正文、实体规则和47行别名候选；不读金标、现役记录或外部设定卡。",
    }
    summary = {
        "schema_version": "z59-entity-supply-summary-v1",
        "status": "formal_complete_zero_model_calls",
        "model_api_calls": 0,
        "window": {"start": 1, "end": 20},
        "accepted_entities": len(accepted_ids),
        "rejected_candidates": len(inventory) - len(accepted_ids),
        "accepted_by_category": dict(
            sorted(Counter(row["category"] for row in inventory if row["accepted"]).items())
        ),
        "chapter_entity_counts": chapter_counts,
        "target_chapter_entity_counts": {str(chapter): chapter_counts[str(chapter)] for chapter in TARGET_CHAPTERS},
        "rules_sha256": sha256_file(rules_path),
        "script_sha256": sha256_file(Path(__file__)),
        "alias_candidate_audit_summary": alias_audit["summary"],
    }
    write_json(output_dir / "entity_inventory.json", {"schema_version": "z59-entity-inventory-v1", "entities": inventory})
    write_json(output_dir / "alias_candidate_audit.json", alias_audit)
    write_json(output_dir / "source_manifest.json", source_manifest)
    write_json(output_dir / "summary.json", summary)
    receipt = verify_supply(output_dir)
    write_json(output_dir / "mechanical_receipt.json", receipt)
    return {**summary, "output_dir": rel(output_dir), "tree_fingerprint": tree_fingerprint(output_dir)}


def verify_supply(supply_dir: Path) -> dict[str, Any]:
    rules = load_rules()
    chapters = load_chapters(rules)
    inventory_doc = read_json(supply_dir / "entity_inventory.json")
    inventory = inventory_doc.get("entities") if isinstance(inventory_doc, dict) else None
    if not isinstance(inventory, list):
        raise ZBatchError("实体总表缺失")
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, observed: Any) -> None:
        checks.append({"check": name, "passed": bool(passed), "observed": observed})

    add("规则SHA与汇总一致", read_json(supply_dir / "summary.json")["rules_sha256"] == sha256_file(RULES_PATH), sha256_file(RULES_PATH))
    add("只读来源清单声明模型调用0", read_json(supply_dir / "source_manifest.json")["model_api_calls"] == 0, 0)
    add("禁用来源读取清单为空", read_json(supply_dir / "source_manifest.json")["forbidden_sources_read"] == [], read_json(supply_dir / "source_manifest.json")["forbidden_sources_read"])
    all_matches: list[Match] = []
    for chapter, data in chapters.items():
        all_matches.extend(raw_matches_for_chapter(chapter, data["body"], rules["entities"]))
    matches_by_entity: dict[str, list[Match]] = defaultdict(list)
    for match in all_matches:
        matches_by_entity[match.entity_id].append(match)

    min_person = int(rules["recognition_policy"]["person_min_window_mentions"])
    min_person_chapters = int(rules["recognition_policy"]["person_min_distinct_chapters"])
    min_nonperson = int(rules["recognition_policy"]["nonperson_min_window_mentions"])
    expected_inventory: list[dict[str, Any]] = []
    expected_accepted_ids: set[str] = set()
    observed_surfaces_by_entity: dict[str, set[str]] = {}
    for entity in rules["entities"]:
        entity_id = str(entity["entity_id"])
        matches = matches_by_entity.get(entity_id, [])
        observed_surfaces = {match.surface for match in matches}
        observed_surfaces_by_entity[entity_id] = observed_surfaces
        chapters_seen = sorted({match.chapter for match in matches})
        threshold = min_person if entity["category"] == "人物" else min_nonperson
        expected_accepted = bool(matches) and (
            entity_id == "PER-001"
            or entity["category"] != "人物"
            or (len(matches) >= threshold and len(chapters_seen) >= min_person_chapters)
        )
        if expected_accepted:
            expected_accepted_ids.add(entity_id)
        display_name, aliases = entity_display_name(entity, observed_surfaces)
        expected_inventory.append(
            {
                "entity_id": entity_id,
                "canonical": entity["canonical"],
                "verified_aliases": aliases,
                "display_name": display_name,
                "category": entity["category"],
                "table": entity["table"],
                "importance": entity.get("importance"),
                "accepted": expected_accepted,
                "disposition": "accepted" if expected_accepted else ("low_frequency_or_single_chapter_cameo" if matches else "no_front20_match"),
                "window_occurrence_count": len(matches),
                "occurrence_chapters": chapters_seen,
                "window_range": compress_ranges(chapters_seen),
                "observed_surfaces": sorted(observed_surfaces),
                "occurrences": [dataclasses.asdict(match) for match in matches],
            }
        )
    inventory_matches_source = inventory == expected_inventory
    add("实体总表由前20章正文独立复算一致", inventory_matches_source, "一致" if inventory_matches_source else "不一致")
    expected_inventory_by_id = {row["entity_id"]: row for row in expected_inventory}
    accepted = {
        row["entity_id"]: row
        for row in expected_inventory
        if row["accepted"]
    }
    stored_alias_audit = read_json(supply_dir / "alias_candidate_audit.json")
    expected_alias_audit = audit_alias_candidates(
        rules,
        chapters,
        expected_accepted_ids,
        observed_surfaces_by_entity,
    )
    alias_audit_matches_source = stored_alias_audit == expected_alias_audit
    add("47行别名候选逐条由正文和同实体组复算一致", alias_audit_matches_source, len(stored_alias_audit.get("rows", [])))
    chapter_totals: dict[str, int] = {}
    for chapter in range(1, 21):
        payload = read_json(supply_dir / "chapters" / f"ch{chapter:04d}.json")
        block = (supply_dir / "rendered" / f"ch{chapter:04d}.txt").read_text(encoding="utf-8")
        expected_payload: dict[str, Any] = {
            "schema_version": SUPPLY_SCHEMA,
            "chapter": chapter,
            "window": {"start": 1, "end": 20},
            "source_chapter": {
                "path": rel(chapters[chapter]["path"]),
                "source_sha256": chapters[chapter]["source_sha256"],
                "body_sha256_after_header_strip": chapters[chapter]["body_sha256"],
            },
            "tables": {table: [] for table in ALLOWED_TABLES},
        }
        present_ids = sorted(
            {
                match.entity_id
                for match in all_matches
                if match.chapter == chapter and match.entity_id in expected_accepted_ids
            }
        )
        for entity_id in present_ids:
            row = expected_inventory_by_id[entity_id]
            current_matches = [match for match in matches_by_entity[entity_id] if match.chapter == chapter]
            expected_payload["tables"][row["table"]].append(
                {
                    "entity_id": entity_id,
                    "display_name": row["display_name"],
                    "canonical": row["canonical"],
                    "verified_aliases": row["verified_aliases"],
                    "category": row["category"],
                    "importance": row["importance"],
                    "window_range": row["window_range"],
                    "window_occurrence_count": row["window_occurrence_count"],
                    "current_chapter_occurrence_count": len(current_matches),
                    "current_chapter_surfaces": sorted({match.surface for match in current_matches}),
                }
            )
        for table in ALLOWED_TABLES:
            expected_payload["tables"][table].sort(key=lambda row: row["entity_id"])
        expected_block = render_entity_block(expected_payload)
        expected_payload["rendered_block_sha256"] = sha256_bytes(expected_block.encode("utf-8"))
        expected_markdown = expected_block + "\n来源：Codex\n"
        markdown = (supply_dir / "rendered" / f"ch{chapter:04d}.md").read_text(encoding="utf-8")
        valid_rows = payload == expected_payload and block == expected_block and markdown == expected_markdown
        row_count = sum(len(expected_payload["tables"][table]) for table in ALLOWED_TABLES)
        chapter_totals[str(chapter)] = row_count
        add(f"第{chapter}章由正文重算且三表逐字段一致", valid_rows, row_count)
    cameo_people = [
        row["entity_id"]
        for row in inventory
        if row["category"] == "人物"
        and row["entity_id"] != "PER-001"
        and (
            row["window_occurrence_count"] < 3
            or len(row["occurrence_chapters"]) < 2
        )
        and row["accepted"]
    ]
    add("低频或单章龙套未进入演员表", cameo_people == [], cameo_people)
    add("20章均有实体供料工件", len(chapter_totals) == 20, chapter_totals)
    failed = [row for row in checks if not row["passed"]]
    if failed:
        raise ZBatchError(f"实体供料机械验收失败：{failed}")
    return {
        "schema_version": "z59-entity-supply-mechanical-receipt-v1",
        "status": "pass",
        "model_api_calls": 0,
        "checks": checks,
        "chapter_entity_totals": chapter_totals,
        "rules_sha256": sha256_file(RULES_PATH),
        "script_sha256": sha256_file(Path(__file__)),
    }


def copy_input(source: Path, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {"source": rel(source), "target": rel(target), "sha256": sha256_file(target)}


def default_neutral_prompt() -> tuple[Path, str]:
    registry = read_json(DEFAULT_REGISTRY)
    prompt = registry["chain"]["neutral_extract_prompt"]
    path = ROOT / prompt["path"]
    expected = str(prompt["sha256"])
    if sha256_file(path) != expected:
        raise ZBatchError("现役中性抽取Prompt SHA漂移")
    return path, expected


def messages_sha(messages: list[dict[str, str]]) -> str:
    return canonical_sha(messages)


def build_entity_messages(base_messages: list[dict[str, str]], entity_block: str) -> list[dict[str, str]]:
    if len(base_messages) != 2 or base_messages[0].get("role") != "system" or base_messages[1].get("role") != "user":
        raise ZBatchError("基线消息形状不是system＋user")
    return [base_messages[0], {"role": "system", "content": entity_block}, base_messages[1]]


def prepare_a(supply_dir: Path, run_dir: Path) -> dict[str, Any]:
    ensure_new_directory(run_dir)
    verify_supply(supply_dir)
    protected = assert_protected()
    outbox_before = outbox_fingerprint()
    prompt_path, prompt_sha = default_neutral_prompt()
    bundle = load_neutral_bundle()
    contract = bundle.stage("neutral_extract")
    model = str(bundle.route["model"])
    input_rows: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        source_catalog = SOURCE_RUN / "01_extract/evidence_catalogs" / f"ch{chapter:04d}.json"
        source_events = SOURCE_RUN / "01_extract/events" / f"ch{chapter:04d}.json"
        source_request = SOURCE_RUN / "requests/neutral_extract" / f"ch{chapter:04d}_request.json"
        supplied_json = supply_dir / "chapters" / f"ch{chapter:04d}.json"
        supplied_txt = supply_dir / "rendered" / f"ch{chapter:04d}.txt"
        copied_catalog = run_dir / "inputs/evidence_catalogs" / f"ch{chapter:04d}.json"
        copied_events = run_dir / "inputs/baseline_events" / f"ch{chapter:04d}.json"
        copied_supply_json = run_dir / "inputs/entity_supply" / f"ch{chapter:04d}.json"
        copied_supply_txt = run_dir / "inputs/entity_supply" / f"ch{chapter:04d}.txt"
        for source, target in (
            (source_catalog, copied_catalog),
            (source_events, copied_events),
            (supplied_json, copied_supply_json),
            (supplied_txt, copied_supply_txt),
        ):
            copy_input(source, target)
        catalog_doc = read_json(copied_catalog)
        built = neutral_extract.build_messages(
            prompt_path=prompt_path,
            expected_prompt_sha256=prompt_sha,
            chapter=chapter,
            chapter_filename=next((ROOT / load_rules()["source_window"]["chapter_dir"]).glob(f"{chapter:04d}_*.txt")).name,
            catalog=catalog_doc["entries"],
        )
        recorded_body = read_json(source_request)["body"]
        recorded = recorded_body["messages"]
        base_messages = built["messages"]
        if base_messages != recorded:
            raise ZBatchError(f"第{chapter}章现役基线消息不能逐字复现第56道请求")
        rebuilt_baseline_body = api_transport.build_request_body(
            model=model,
            messages=base_messages,
            contract=contract,
        )
        if rebuilt_baseline_body != recorded_body:
            raise ZBatchError(f"第{chapter}章现役基线请求不能由当前正式合同逐字段复现")
        entity_block = copied_supply_txt.read_text(encoding="utf-8")
        candidate = build_entity_messages(base_messages, entity_block)
        if candidate[0] != base_messages[0] or candidate[2] != base_messages[1] or len(candidate) != len(base_messages) + 1:
            raise ZBatchError(f"第{chapter}章单变量插入校验失败")
        candidate_body = api_transport.build_request_body(
            model=model,
            messages=candidate,
            contract=contract,
        )
        request_fields = sorted(set(recorded_body) | set(candidate_body))
        changed_fields = [field for field in request_fields if recorded_body.get(field) != candidate_body.get(field)]
        if changed_fields != ["messages"]:
            raise ZBatchError(f"第{chapter}章请求字段夹带变化：{changed_fields}")
        input_rows.append(
            {
                "chapter": chapter,
                "source_request_sha256": sha256_file(source_request),
                "baseline_messages_sha256": messages_sha(base_messages),
                "entity_block_sha256": sha256_bytes(entity_block.encode("utf-8")),
                "candidate_messages_sha256": messages_sha(candidate),
                "single_variable": "仅在原system与原user之间插入一条system实体供料块；原两条消息逐字不变",
                "request_body_changed_fields": changed_fields,
                "unchanged_request_fields": [field for field in request_fields if field != "messages"],
                "message_position_audit": [
                    {"baseline_index": 0, "candidate_index": 0, "role": "system", "content_identical": True},
                    {"baseline_index": None, "candidate_index": 1, "role": "system", "content": "新增实体供料块"},
                    {"baseline_index": 1, "candidate_index": 2, "role": "user", "content_identical": True},
                ],
                "catalog_sha256": sha256_file(copied_catalog),
                "baseline_events_sha256": sha256_file(copied_events),
            }
        )
    copy_input(prompt_path, run_dir / "provenance/pinned/neutral_extract_prompt.md")
    copy_input(RULES_PATH, run_dir / "provenance/pinned/entity_supply_rules.json")
    copy_input(Path(__file__), run_dir / "provenance/pinned/z59_entity_supply_pilot.py")
    copy_input(SAMPLING_CONTRACT, run_dir / "provenance/pinned/sensenova_stage_sampling_v1.json")
    copy_input(PROVIDER_CONFIG, run_dir / "provenance/pinned/sensenova_modular_v1.json")
    single_variable_diff = {
        "schema_version": "z59-a-single-variable-diff-v1",
        "status": "pass",
        "rule": "候选请求相对第56道同章请求，只允许messages字段变化；messages只允许在原system与原user之间插入一条system实体供料块",
        "target_chapters": list(TARGET_CHAPTERS),
        "rows": input_rows,
    }
    write_json(run_dir / "single_variable_diff.json", single_variable_diff)
    preflight = {
        "schema_version": "z59-a-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": now_iso(),
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "target_chapters": list(TARGET_CHAPTERS),
        "neutral_prompt_sha256": prompt_sha,
        "sampling_contract_sha256": sha256_file(SAMPLING_CONTRACT),
        "provider_config_sha256": sha256_file(PROVIDER_CONFIG),
        "single_variable_diff": {
            "path": "single_variable_diff.json",
            "sha256": sha256_file(run_dir / "single_variable_diff.json"),
        },
        "protected": protected,
        "outbox_before": outbox_before,
        "inputs": input_rows,
        "score_condition": "含全程演员表输入；与第57道裸考条件不同，只并列展示，不直接判胜负",
    }
    write_json(run_dir / "preflight.json", preflight)
    write_json(
        run_dir / "run_manifest.json",
        {"schema_version": "z59-a-run-manifest-v1", "run_id": run_dir.name, "status": "prepared", "model_api_calls": 0},
    )
    return preflight


def load_neutral_bundle() -> stage_sampling.StageContractBundle:
    return stage_sampling.load_contract_bundle(SAMPLING_CONTRACT, profile="d_mod_cutover_v1")


def request_artifact_receipt(run_dir: Path, stage: str, case_id: str, output: Path) -> dict[str, Any]:
    request = run_dir / "requests" / stage / f"{case_id}_request.json"
    raw = run_dir / "responses" / stage / f"{case_id}_raw.json"
    meta = run_dir / "responses" / stage / f"{case_id}_meta.json"
    for path in (request, raw, meta, output):
        if not path.is_file():
            raise ZBatchError(f"API工件不完整：{path}")
    return {
        "request_sha256": sha256_file(request),
        "raw_response_sha256": sha256_file(raw),
        "meta_sha256": sha256_file(meta),
        "output_sha256": sha256_file(output),
    }


def read_attempt_count(run_dir: Path) -> int:
    path = run_dir / "call_attempts.jsonl"
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]) if path.is_file() else 0


def read_usage_rows(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "usage.jsonl"
    return read_jsonl(path) if path.is_file() else []


def usage_summary(run_dir: Path) -> dict[str, Any]:
    rows = read_usage_rows(run_dir)
    totals = Counter()
    elapsed_ms = 0
    for row in rows:
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        for key, value in usage.items():
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
        if isinstance(row.get("elapsed_ms"), int):
            elapsed_ms += row["elapsed_ms"]
    return {
        "network_attempts": read_attempt_count(run_dir),
        "successful_model_calls": len(rows),
        "usage_totals": dict(sorted(totals.items())),
        "elapsed_ms": elapsed_ms,
        "finish_reasons": dict(sorted(Counter(str(row.get("finish_reason")) for row in rows).items())),
        "http_statuses": dict(sorted(Counter(str(row.get("http_status")) for row in rows).items())),
    }


def run_a(run_dir: Path) -> dict[str, Any]:
    preflight = read_json(run_dir / "preflight.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("试点A缺合格预演")
    if read_attempt_count(run_dir) != 0:
        raise ZBatchError("试点A已有调用账，拒绝复跑")
    assert_protected()
    bundle = load_neutral_bundle()
    transport = api_transport.ApiTransport.from_bundle(bundle, run_dir=run_dir, max_calls=5)
    prompt_copy = run_dir / "provenance/pinned/neutral_extract_prompt.md"
    prompt_sha = sha256_file(prompt_copy)
    completed: list[int] = []
    receipts: dict[str, Any] = {}
    try:
        for chapter in TARGET_CHAPTERS:
            catalog_doc = read_json(run_dir / "inputs/evidence_catalogs" / f"ch{chapter:04d}.json")
            built = neutral_extract.build_messages(
                prompt_path=prompt_copy,
                expected_prompt_sha256=prompt_sha,
                chapter=chapter,
                chapter_filename=next((ROOT / load_rules()["source_window"]["chapter_dir"]).glob(f"{chapter:04d}_*.txt")).name,
                catalog=catalog_doc["entries"],
            )
            block = (run_dir / "inputs/entity_supply" / f"ch{chapter:04d}.txt").read_text(encoding="utf-8")
            messages = build_entity_messages(built["messages"], block)
            result = transport.call(stage="neutral_extract", case_id=f"ch{chapter:04d}", messages=messages)
            raw_data = candidate_envelope.parse_json_content(result.content)
            materialized, audit = neutral_extract.process_model_data(raw_data, chapter=chapter, catalog=catalog_doc["entries"])
            output = run_dir / "01_extract/events" / f"ch{chapter:04d}.json"
            audit_path = run_dir / "01_extract/program_audits" / f"ch{chapter:04d}.json"
            write_json(output, materialized)
            write_json(audit_path, audit)
            receipts[str(chapter)] = {
                **request_artifact_receipt(run_dir, "neutral_extract", f"ch{chapter:04d}", output),
                "audit_sha256": sha256_file(audit_path),
                "event_count": len(materialized["events"]),
                "missing_catalog_anchor_ids": audit["missing_catalog_anchor_ids"],
            }
            completed.append(chapter)
    except Exception as exc:
        hard_stop = {
            "schema_version": "z59-a-hard-stop-v1",
            "status": "hard_stop_no_repair_no_rerun",
            "at": now_iso(),
            "completed_chapters": completed,
            "next_chapter": next((chapter for chapter in TARGET_CHAPTERS if chapter not in completed), None),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "usage": usage_summary(run_dir),
        }
        write_json(run_dir / "hard_stop.json", hard_stop)
        write_json(run_dir / "run_manifest.json", {"schema_version": "z59-a-run-manifest-v1", "run_id": run_dir.name, "status": "hard_stop", "model_api_calls": hard_stop["usage"]["successful_model_calls"]})
        raise
    metrics = {
        "schema_version": "z59-a-metrics-v1",
        "status": "completed_candidate_only",
        "target_chapters": list(TARGET_CHAPTERS),
        "chapters_completed": completed,
        "events_by_chapter": {chapter: receipts[str(chapter)]["event_count"] for chapter in completed},
        "event_total": sum(receipts[str(chapter)]["event_count"] for chapter in completed),
        "catalog_outside_anchor_count": sum(len(receipts[str(chapter)]["missing_catalog_anchor_ids"]) for chapter in completed),
        "usage": usage_summary(run_dir),
        "receipts": receipts,
    }
    write_json(run_dir / "01_extract/metrics.json", metrics)
    write_json(run_dir / "run_manifest.json", {"schema_version": "z59-a-run-manifest-v1", "run_id": run_dir.name, "status": "completed_candidate_only", "model_api_calls": metrics["usage"]["successful_model_calls"]})
    return metrics


def event_anchor_ids(event: Mapping[str, Any]) -> set[str]:
    return {str(anchor.get("anchor_id")) for anchor in event.get("anchors") or [] if isinstance(anchor, dict) and anchor.get("anchor_id")}


def normalized_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def text_ratio(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, normalized_text(left), normalized_text(right)).ratio()


def match_events(baseline: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, Any]:
    scored: list[tuple[float, int, int, float, float]] = []
    for old_index, old in enumerate(baseline):
        old_anchors = event_anchor_ids(old)
        for new_index, new in enumerate(candidate):
            new_anchors = event_anchor_ids(new)
            intersection = len(old_anchors & new_anchors)
            union = len(old_anchors | new_anchors)
            anchor_score = intersection / union if union else 0.0
            summary_score = text_ratio(str(old.get("event") or ""), str(new.get("event") or ""))
            score = 0.65 * anchor_score + 0.35 * summary_score
            if intersection or summary_score >= 0.50:
                scored.append((score, old_index, new_index, anchor_score, summary_score))
    used_old: set[int] = set()
    used_new: set[int] = set()
    pairs: list[dict[str, Any]] = []
    for score, old_index, new_index, anchor_score, summary_score in sorted(scored, reverse=True):
        if old_index in used_old or new_index in used_new:
            continue
        used_old.add(old_index)
        used_new.add(new_index)
        old = baseline[old_index]
        new = candidate[new_index]
        status = "unchanged" if old.get("event") == new.get("event") and event_anchor_ids(old) == event_anchor_ids(new) else "changed"
        pairs.append(
            {
                "baseline_event_id_run_local_only": old.get("event_id"),
                "candidate_event_id_run_local_only": new.get("event_id"),
                "status": status,
                "match_score": score,
                "anchor_jaccard": anchor_score,
                "summary_similarity": summary_score,
                "baseline": old,
                "candidate": new,
            }
        )
    removed = [baseline[index] for index in range(len(baseline)) if index not in used_old]
    added = [candidate[index] for index in range(len(candidate)) if index not in used_new]
    return {
        "pairs": sorted(pairs, key=lambda row: str(row["baseline_event_id_run_local_only"])),
        "baseline_unmatched": removed,
        "candidate_unmatched": added,
        "mechanical_old_event_nondegradation": len(removed) == 0,
        "semantic_review_required": "changed配对只证明锚或摘要相近；旧事件是否语义不劣化仍须逐条核读。",
    }


def gold_on_chapter(gold: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in gold["layered_items"]:
        for part in item["parts"]:
            if part["layer"] == "当章可知":
                result[item["item_id"]] = {
                    "gold_item_id": item["item_id"],
                    "claim": part["claim"],
                    "source_evidence": part["source_evidence"],
                }
    if len(result) != 14:
        raise ZBatchError(f"第3章当章金标不是14条：{len(result)}")
    return result


def group_match(text: str, alternatives: list[str]) -> bool:
    normalized = normalized_text(text)
    return any(normalized_text(value) in normalized for value in alternatives)


def anchor_numbers(event: Mapping[str, Any]) -> set[int]:
    values: set[int] = set()
    for anchor_id in event_anchor_ids(event):
        match = re.fullmatch(r"E(\d{4})", anchor_id)
        if match:
            values.add(int(match.group(1)))
    return values


def score_chapter3(events: list[dict[str, Any]]) -> dict[str, Any]:
    if sha256_file(GOLD_V1_1) != EXPECTED_PROTECTED_SHA[GOLD_V1_1]:
        raise ZBatchError("金标v1.1漂移")
    rubric = read_json(RUBRIC_PATH)
    gold = gold_on_chapter(read_json(GOLD_V1_1))
    rubric_rows = {row["gold_item_id"]: row for row in rubric["rows"]}
    rows: list[dict[str, Any]] = []
    strict_count = 0
    shadow_count = 0
    for gold_id, item in gold.items():
        rule = rubric_rows[gold_id]
        evidence_numbers = {
            int(str(evidence["anchor_id"])[1:])
            for evidence in item["source_evidence"]
            if re.fullmatch(r"E\d{4}", str(evidence.get("anchor_id")))
        }
        candidates: list[tuple[int, bool, float, dict[str, Any], list[bool]]] = []
        for event in events:
            matched_groups = [group_match(str(event.get("event") or ""), alternatives) for alternatives in rule["required_groups"]]
            event_numbers = anchor_numbers(event)
            anchor_near = any(abs(left - right) <= 1 for left in event_numbers for right in evidence_numbers)
            ratio = sum(matched_groups) / len(matched_groups)
            candidates.append((sum(matched_groups), anchor_near, ratio, event, matched_groups))
        best = max(candidates, key=lambda row: (row[0] == len(rule["required_groups"]) and row[1], row[0], row[1], row[2]))
        matched_count, anchor_near, _, event, matched_groups = best
        strict = anchor_near and matched_count == len(rule["required_groups"])
        shadow = anchor_near or matched_count >= min(2, len(rule["required_groups"]))
        if strict:
            strict_count += 1
        if shadow:
            shadow_count += 1
        rows.append(
            {
                **item,
                "verdict": "strict_hit" if strict else ("partial_shadow" if shadow else "no_shadow"),
                "candidate_event_id_run_local_only": event.get("event_id") if shadow else None,
                "candidate_event": event.get("event") if shadow else None,
                "candidate_anchor_ids": sorted(event_anchor_ids(event)) if shadow else [],
                "required_groups": rule["required_groups"],
                "required_group_matches": matched_groups,
                "matched_required_groups": matched_count,
                "anchor_near_gold_evidence": anchor_near,
            }
        )
    return {
        "schema_version": "z59-a-chapter3-conditional-score-v1",
        "condition": "含全程演员表输入；与第57道裸考基线并列，不直接判胜负",
        "gold": {"path": rel(GOLD_V1_1), "sha256": sha256_file(GOLD_V1_1)},
        "rubric": {"path": rel(RUBRIC_PATH), "sha256": sha256_file(RUBRIC_PATH)},
        "anti_leakage": rubric["policy"]["anti_leakage"],
        "summary": {
            "on_chapter_gold_total": 14,
            "strict_complete_extraction": strict_count,
            "strict_complete_extraction_rate": strict_count / 14,
            "shadow_recalled": shadow_count,
            "shadow_recall_rate": shadow_count / 14,
            "baseline_naked_condition": {"strict": 2, "shadow": 12, "denominator": 14},
        },
        "rows": rows,
    }


def analyze_a(run_dir: Path) -> dict[str, Any]:
    metrics = read_json(run_dir / "01_extract/metrics.json")
    if metrics.get("status") != "completed_candidate_only":
        raise ZBatchError("试点A没有完整完成，不能出成绩")
    chapter_diffs: dict[str, Any] = {}
    all_old_kept = True
    for chapter in TARGET_CHAPTERS:
        baseline = read_json(run_dir / "inputs/baseline_events" / f"ch{chapter:04d}.json")["events"]
        candidate = read_json(run_dir / "01_extract/events" / f"ch{chapter:04d}.json")["events"]
        diff = match_events(baseline, candidate)
        diff["chapter"] = chapter
        diff["baseline_event_count"] = len(baseline)
        diff["candidate_event_count"] = len(candidate)
        chapter_diffs[str(chapter)] = diff
        all_old_kept = all_old_kept and diff["mechanical_old_event_nondegradation"]
    diff_report = {
        "schema_version": "z59-a-event-diff-v1",
        "status": "candidate_diff_requires_semantic_review",
        "single_variable": "相对第56道同章请求，仅在原system与原user之间增加本章实体供料system块",
        "mechanical_all_old_events_have_candidate": all_old_kept,
        "chapters": chapter_diffs,
    }
    score = score_chapter3(read_json(run_dir / "01_extract/events/ch0003.json")["events"])
    cost = {
        "schema_version": "z59-a-cost-v1",
        "task": "试点A：五靶章实体表注入中性抽取",
        "usage": usage_summary(run_dir),
        "source_of_truth": "usage.jsonl",
    }
    write_json(run_dir / "analysis/事件逐条diff.json", diff_report)
    write_json(run_dir / "analysis/第3章条件成绩.json", score)
    write_json(run_dir / "analysis/成本账.json", cost)
    return {
        "diff_sha256": sha256_file(run_dir / "analysis/事件逐条diff.json"),
        "score_sha256": sha256_file(run_dir / "analysis/第3章条件成绩.json"),
        "cost_sha256": sha256_file(run_dir / "analysis/成本账.json"),
        "mechanical_old_event_nondegradation": all_old_kept,
        "score": score["summary"],
        "usage": cost["usage"],
    }


def render_outline_user_prompt(template: str, chapter: int, events: list[dict[str, Any]]) -> str:
    return prompt_render_pin.render_prompt(
        template,
        {
            "CHAPTER_NUMBER": str(chapter),
            "CHAPTER_PADDED": f"{chapter:04d}",
            "NEUTRAL_EVENTS_JSON": json.dumps(events, ensure_ascii=False, separators=(",", ":")),
        },
    )


def outline_messages(user_prompt: str, entity_block: str | None) -> list[dict[str, str]]:
    base = [{"role": "system", "content": OUTLINE_SYSTEM_MESSAGE}, {"role": "user", "content": user_prompt}]
    return build_entity_messages(base, entity_block) if entity_block is not None else base


def validate_outline(data: Any, chapter: int, source_event_ids: set[str]) -> dict[str, Any]:
    reasons: list[str] = []
    if not isinstance(data, dict):
        raise ZBatchError("大纲回包不是对象")
    if set(data) != {"schema_version", "chapter", "outline_items"}:
        reasons.append("大纲根字段不等于固定合同")
    if data.get("schema_version") != OUTLINE_SCHEMA:
        reasons.append("大纲schema错误")
    if data.get("chapter") != chapter:
        reasons.append("大纲章号错误")
    items = data.get("outline_items")
    if not isinstance(items, list) or not items:
        reasons.append("outline_items不是非空数组")
        items = []
    expected_ids = [f"OL-C{chapter:04d}-{index:02d}" for index in range(1, len(items) + 1)]
    observed: list[str] = []
    used_source_ids: list[str] = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict) or set(item) != {"item_id", "source_event_ids", "logic_sentence", "state_change"}:
            reasons.append(f"第{index}条字段越出合同")
            continue
        item_id = item.get("item_id")
        if isinstance(item_id, str):
            observed.append(item_id)
        if item_id != expected_ids[index - 1]:
            reasons.append(f"第{index}条item_id不连续")
        ids = item.get("source_event_ids")
        if not isinstance(ids, list) or not ids or any(not isinstance(value, str) for value in ids):
            reasons.append(f"{item_id}来源事件ID非法")
            ids = []
        if len(ids) != len(set(ids)):
            reasons.append(f"{item_id}来源事件ID重复")
        unknown = sorted(set(ids) - source_event_ids)
        if unknown:
            reasons.append(f"{item_id}引用目录外事件ID：{unknown}")
        used_source_ids.extend(ids)
        logic = item.get("logic_sentence")
        state = item.get("state_change")
        if not isinstance(logic, str) or not 6 <= len(normalized_text(logic)) <= 300:
            reasons.append(f"{item_id}逻辑句长度非法")
        if not isinstance(state, str) or not 6 <= len(normalized_text(state)) <= 200:
            reasons.append(f"{item_id}状态转变长度非法")
    if observed != expected_ids:
        reasons.append("大纲ID集合或顺序不连续")
    unique_reasons = sorted(set(reasons))
    audit = {
        "schema_version": "z59-outline-program-audit-v1",
        "chapter": chapter,
        "status": "pass" if not unique_reasons else "fail",
        "item_count": len(items),
        "source_event_count": len(source_event_ids),
        "used_source_event_count": len(set(used_source_ids)),
        "unknown_source_event_ids": sorted(set(used_source_ids) - source_event_ids),
        "reasons": unique_reasons,
    }
    if unique_reasons:
        raise ZBatchError(f"第{chapter}章大纲回包合同失败：{unique_reasons}")
    return audit


def source_pool_manifest() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    events_dir = SOURCE_RUN / "01_extract/events"
    for path in sorted(events_dir.iterdir()):
        match = re.fullmatch(r"ch(\d{4})\.json", path.name)
        if not match or not path.is_file():
            continue
        chapter = int(match.group(1))
        document = read_json(path)
        events = document.get("events") if isinstance(document, dict) else None
        if not isinstance(events, list):
            raise ZBatchError(f"第{chapter}章中性事件池不是数组")
        rows.append(
            {
                "chapter": chapter,
                "event_count": len(events),
                "sha256": sha256_file(path),
                "path": rel(path),
            }
        )
    observed_chapters = [row["chapter"] for row in rows]
    if observed_chapters != list(range(1, 21)):
        raise ZBatchError(f"第56道中性事件池章次不等于1～20：{observed_chapters}")
    total = sum(row["event_count"] for row in rows)
    if total != 233:
        raise ZBatchError(f"第56道中性事件池总数不是233：{total}")
    return {
        "schema_version": "z60-b-source-pool-manifest-v1",
        "source_run": rel(SOURCE_RUN),
        "chapter_count": len(rows),
        "event_total": total,
        "rows": rows,
    }


def prepare_b(supply_dir: Path, run_dir: Path) -> dict[str, Any]:
    ensure_new_directory(run_dir)
    supply_receipt = verify_supply(supply_dir)
    protected = assert_protected()
    outbox_before = outbox_fingerprint()
    pool_manifest = source_pool_manifest()
    write_json(run_dir / "source_pool_manifest.json", pool_manifest)
    if sha256_file(OUTLINE_PROMPT_PATH) == "":  # pragma: no cover
        raise AssertionError
    template = OUTLINE_PROMPT_PATH.read_text(encoding="utf-8")
    bundle = load_neutral_bundle()
    contract = outline_contract_from_neutral()
    model = str(bundle.route["model"])
    rows: list[dict[str, Any]] = []
    source_total = 0
    for chapter in TARGET_CHAPTERS:
        source_events = SOURCE_RUN / "01_extract/events" / f"ch{chapter:04d}.json"
        copied_events = run_dir / "inputs/neutral_events" / f"ch{chapter:04d}.json"
        copied_supply = run_dir / "inputs/entity_supply" / f"ch{chapter:04d}.txt"
        copy_input(source_events, copied_events)
        copy_input(supply_dir / "rendered" / f"ch{chapter:04d}.txt", copied_supply)
        events = read_json(copied_events)["events"]
        source_total += len(events)
        user_prompt = render_outline_user_prompt(template, chapter, events)
        block = copied_supply.read_text(encoding="utf-8")
        base_messages = outline_messages(user_prompt, None)
        entity_messages = outline_messages(user_prompt, block)
        if entity_messages[0] != base_messages[0] or entity_messages[2] != base_messages[1] or len(entity_messages) != 3:
            raise ZBatchError(f"第{chapter}章大纲双臂单变量校验失败")
        base_body = api_transport.build_request_body(model=model, messages=base_messages, contract=contract)
        entity_body = api_transport.build_request_body(model=model, messages=entity_messages, contract=contract)
        request_fields = sorted(set(base_body) | set(entity_body))
        changed_fields = [field for field in request_fields if base_body.get(field) != entity_body.get(field)]
        if changed_fields != ["messages"]:
            raise ZBatchError(f"第{chapter}章大纲双臂请求字段夹带变化：{changed_fields}")
        rows.append(
            {
                "chapter": chapter,
                "source_event_count": len(events),
                "source_events_sha256": sha256_file(copied_events),
                "user_prompt_sha256": sha256_bytes(user_prompt.encode("utf-8")),
                "base_messages_sha256": messages_sha(base_messages),
                "entity_block_sha256": sha256_bytes(block.encode("utf-8")),
                "entity_messages_sha256": messages_sha(entity_messages),
                "single_variable": "带表臂只在共同system与共同user之间插入实体供料system块",
                "request_body_changed_fields": changed_fields,
                "unchanged_request_fields": [field for field in request_fields if field != "messages"],
                "message_position_audit": [
                    {"base_index": 0, "entity_index": 0, "role": "system", "content_identical": True},
                    {"base_index": None, "entity_index": 1, "role": "system", "content": "件⓪v1.1实体供料块"},
                    {"base_index": 1, "entity_index": 2, "role": "user", "content_identical": True},
                ],
            }
        )
    if source_total != 39:
        raise ZBatchError(f"五靶章中性事件子集总数不是39：{source_total}")
    copy_input(OUTLINE_PROMPT_PATH, run_dir / "provenance/pinned/z59_outline_logic_base_v1.md")
    copy_input(RULES_PATH, run_dir / "provenance/pinned/entity_supply_rules.json")
    copy_input(B_SEMANTIC_RUBRIC_PATH, run_dir / "provenance/pinned/Z60_大纲逻辑双臂语义复核尺_v1.json")
    copy_input(Path(__file__), run_dir / "provenance/pinned/z59_entity_supply_pilot.py")
    copy_input(SAMPLING_CONTRACT, run_dir / "provenance/pinned/sensenova_stage_sampling_v1.json")
    copy_input(PROVIDER_CONFIG, run_dir / "provenance/pinned/sensenova_modular_v1.json")
    single_variable_diff = {
        "schema_version": "z60-b-single-variable-diff-v1",
        "status": "pass",
        "rule": "同章两臂请求体只允许messages变化；带表臂只在共同system与共同user之间插入件⓪v1.1实体供料system块",
        "target_chapters": list(TARGET_CHAPTERS),
        "rows": rows,
    }
    write_json(run_dir / "single_variable_diff.json", single_variable_diff)
    preflight = {
        "schema_version": "z60-b-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": now_iso(),
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "target_chapters": list(TARGET_CHAPTERS),
        "source_event_total": source_total,
        "source_pool": {
            "chapter_count": pool_manifest["chapter_count"],
            "event_total": pool_manifest["event_total"],
            "manifest_path": "source_pool_manifest.json",
            "manifest_sha256": sha256_file(run_dir / "source_pool_manifest.json"),
        },
        "entity_supply_v1_1": {
            "source_dir": rel(supply_dir),
            "tree_fingerprint": tree_fingerprint(supply_dir),
            "mechanical_verification_status": supply_receipt["status"],
            "summary_sha256": sha256_file(supply_dir / "summary.json"),
            "mechanical_receipt_sha256": sha256_file(supply_dir / "mechanical_receipt.json"),
        },
        "outline_prompt_template": {"path": rel(OUTLINE_PROMPT_PATH), "sha256": sha256_file(OUTLINE_PROMPT_PATH)},
        "outline_system_message_sha256": sha256_bytes(OUTLINE_SYSTEM_MESSAGE.encode("utf-8")),
        "semantic_review_rubric": {"path": rel(B_SEMANTIC_RUBRIC_PATH), "sha256": sha256_file(B_SEMANTIC_RUBRIC_PATH)},
        "sampling_contract": {
            "source_path": rel(SAMPLING_CONTRACT),
            "pinned_path": "provenance/pinned/sensenova_stage_sampling_v1.json",
            "sha256": sha256_file(SAMPLING_CONTRACT),
        },
        "provider_config": {
            "source_path": rel(PROVIDER_CONFIG),
            "pinned_path": "provenance/pinned/sensenova_modular_v1.json",
            "sha256": sha256_file(PROVIDER_CONFIG),
        },
        "sampling": {"temperature": 0.2, "max_tokens": 16000, "n": 1, "reasoning_effort": "medium"},
        "arm_order": "每章先不带表，再带表；各一发，不重跑挑结果",
        "transport_budget": {
            "logical_cases": B_LOGICAL_CASES,
            "network_retry_slack": B_NETWORK_RETRY_SLACK,
            "max_network_attempts": B_MAX_NETWORK_ATTEMPTS,
            "note": "10个逻辑样张各只取一次成功回包；额外3次只供运输失败重试，不增加逻辑样张。",
        },
        "single_variable_diff": {
            "path": "single_variable_diff.json",
            "sha256": sha256_file(run_dir / "single_variable_diff.json"),
        },
        "protected": protected,
        "outbox_before": outbox_before,
        "inputs": rows,
    }
    write_json(run_dir / "preflight.json", preflight)
    write_json(run_dir / "run_manifest.json", {"schema_version": "z60-b-run-manifest-v1", "run_id": run_dir.name, "status": "prepared", "model_api_calls": 0})
    return preflight


def outline_contract_from_neutral() -> stage_sampling.StageSamplingContract:
    source = load_neutral_bundle().stage("neutral_extract")
    return dataclasses.replace(source, stage="outline_logic", note="第59道授权旁路；参数逐字段复用现役neutral_extract")


def run_b(run_dir: Path) -> dict[str, Any]:
    preflight = read_json(run_dir / "preflight.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("试点B缺合格预演")
    if read_attempt_count(run_dir) != 0:
        raise ZBatchError("试点B已有调用账，拒绝复跑")
    assert_protected()
    if outbox_fingerprint() != preflight.get("outbox_before"):
        raise ZBatchError("试点B开跑前outbox指纹漂移")
    if sha256_file(run_dir / "single_variable_diff.json") != preflight["single_variable_diff"]["sha256"]:
        raise ZBatchError("试点B单变量账漂移")
    if sha256_file(run_dir / "source_pool_manifest.json") != preflight["source_pool"]["manifest_sha256"]:
        raise ZBatchError("试点B来源池账漂移")
    if sha256_file(run_dir / "provenance/pinned/z59_outline_logic_base_v1.md") != preflight["outline_prompt_template"]["sha256"]:
        raise ZBatchError("试点B提示词候选漂移")
    if sha256_file(run_dir / "provenance/pinned/Z60_大纲逻辑双臂语义复核尺_v1.json") != preflight["semantic_review_rubric"]["sha256"]:
        raise ZBatchError("试点B语义复核尺漂移")
    for label, source, record in (
        ("采样合同", SAMPLING_CONTRACT, preflight["sampling_contract"]),
        ("供应商配置", PROVIDER_CONFIG, preflight["provider_config"]),
    ):
        expected = str(record["sha256"])
        pinned = run_dir / str(record["pinned_path"])
        if sha256_file(pinned) != expected:
            raise ZBatchError(f"试点B固定{label}漂移")
        if sha256_file(source) != expected:
            raise ZBatchError(f"试点B预演后现役{label}漂移，拒绝调用")
    if sha256_file(run_dir / "provenance/pinned/z59_entity_supply_pilot.py") != sha256_file(Path(__file__)):
        raise ZBatchError("试点B预演后脚本漂移，拒绝调用")
    for row in preflight["inputs"]:
        chapter = int(row["chapter"])
        if sha256_file(run_dir / "inputs/neutral_events" / f"ch{chapter:04d}.json") != row["source_events_sha256"]:
            raise ZBatchError(f"第{chapter}章中性事件输入漂移")
        supply_path = run_dir / "inputs/entity_supply" / f"ch{chapter:04d}.txt"
        if sha256_bytes(supply_path.read_bytes()) != row["entity_block_sha256"]:
            raise ZBatchError(f"第{chapter}章实体供料输入漂移")
    bundle = load_neutral_bundle()
    route = api_transport.TransportRoute.from_mapping(bundle.route)
    transport = api_transport.ApiTransport(
        route=route,
        contracts={"outline_logic": outline_contract_from_neutral()},
        run_dir=run_dir,
        max_calls=B_MAX_NETWORK_ATTEMPTS,
    )
    template = (run_dir / "provenance/pinned/z59_outline_logic_base_v1.md").read_text(encoding="utf-8")
    completed: list[str] = []
    receipts: dict[str, Any] = {}
    try:
        for chapter in TARGET_CHAPTERS:
            events = read_json(run_dir / "inputs/neutral_events" / f"ch{chapter:04d}.json")["events"]
            source_ids = {str(event["event_id"]) for event in events}
            user_prompt = render_outline_user_prompt(template, chapter, events)
            block = (run_dir / "inputs/entity_supply" / f"ch{chapter:04d}.txt").read_text(encoding="utf-8")
            for arm, entity_block in (("base", None), ("entity", block)):
                case_id = f"{arm}_ch{chapter:04d}"
                messages = outline_messages(user_prompt, entity_block)
                result = transport.call(stage="outline_logic", case_id=case_id, messages=messages)
                data = candidate_envelope.parse_json_content(result.content)
                audit = validate_outline(data, chapter, source_ids)
                output = run_dir / "01_outline" / arm / f"ch{chapter:04d}.json"
                audit_path = run_dir / "01_outline/program_audits" / arm / f"ch{chapter:04d}.json"
                write_json(output, data)
                write_json(audit_path, audit)
                receipts[case_id] = {
                    **request_artifact_receipt(run_dir, "outline_logic", case_id, output),
                    "audit_sha256": sha256_file(audit_path),
                    "item_count": len(data["outline_items"]),
                }
                completed.append(case_id)
        outbox_after = outbox_fingerprint()
        if outbox_after != preflight.get("outbox_before"):
            raise ZBatchError("试点B实跑期间outbox指纹漂移")
    except Exception as exc:
        hard_stop = {
            "schema_version": "z59-b-hard-stop-v1",
            "status": "hard_stop_no_repair_no_rerun",
            "at": now_iso(),
            "completed_cases": completed,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "usage": usage_summary(run_dir),
        }
        write_json(run_dir / "hard_stop.json", hard_stop)
        write_json(run_dir / "run_manifest.json", {"schema_version": "z59-b-run-manifest-v1", "run_id": run_dir.name, "status": "hard_stop", "model_api_calls": hard_stop["usage"]["successful_model_calls"]})
        raise
    metrics = {
        "schema_version": "z59-b-metrics-v1",
        "status": "completed_candidate_only",
        "completed_cases": completed,
        "base_items": sum(receipts[f"base_ch{chapter:04d}"]["item_count"] for chapter in TARGET_CHAPTERS),
        "entity_items": sum(receipts[f"entity_ch{chapter:04d}"]["item_count"] for chapter in TARGET_CHAPTERS),
        "usage": usage_summary(run_dir),
        "transport_budget": preflight["transport_budget"],
        "outbox_after": outbox_after,
        "receipts": receipts,
    }
    write_json(run_dir / "01_outline/metrics.json", metrics)
    write_json(run_dir / "run_manifest.json", {"schema_version": "z59-b-run-manifest-v1", "run_id": run_dir.name, "status": "completed_candidate_only", "model_api_calls": metrics["usage"]["successful_model_calls"]})
    return metrics


def outline_item_source_ids(item: Mapping[str, Any]) -> set[str]:
    return {str(value) for value in item.get("source_event_ids") or []}


def match_outline_items(base: list[dict[str, Any]], entity: list[dict[str, Any]]) -> dict[str, Any]:
    scored: list[tuple[float, int, int, float, float]] = []
    for left_index, left in enumerate(base):
        left_ids = outline_item_source_ids(left)
        for right_index, right in enumerate(entity):
            right_ids = outline_item_source_ids(right)
            union = len(left_ids | right_ids)
            source_score = len(left_ids & right_ids) / union if union else 0.0
            sentence_score = text_ratio(str(left.get("logic_sentence") or ""), str(right.get("logic_sentence") or ""))
            score = 0.75 * source_score + 0.25 * sentence_score
            if source_score or sentence_score >= 0.50:
                scored.append((score, left_index, right_index, source_score, sentence_score))
    used_left: set[int] = set()
    used_right: set[int] = set()
    pairs: list[dict[str, Any]] = []
    for score, left_index, right_index, source_score, sentence_score in sorted(scored, reverse=True):
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        left = base[left_index]
        right = entity[right_index]
        exact = (
            left.get("source_event_ids") == right.get("source_event_ids")
            and left.get("logic_sentence") == right.get("logic_sentence")
            and left.get("state_change") == right.get("state_change")
        )
        pairs.append(
            {
                "base_item_id_run_local_only": left.get("item_id"),
                "entity_item_id_run_local_only": right.get("item_id"),
                "status": "exact_same" if exact else "information_changed",
                "match_score": score,
                "source_event_jaccard": source_score,
                "logic_sentence_similarity": sentence_score,
                "base": left,
                "entity": right,
            }
        )
    return {
        "pairs": sorted(pairs, key=lambda row: str(row["base_item_id_run_local_only"])),
        "base_only": [base[index] for index in range(len(base)) if index not in used_left],
        "entity_only": [entity[index] for index in range(len(entity)) if index not in used_right],
    }


def analyze_b(run_dir: Path) -> dict[str, Any]:
    metrics = read_json(run_dir / "01_outline/metrics.json")
    if metrics.get("status") != "completed_candidate_only":
        raise ZBatchError("试点B没有完整完成，不能出双臂diff")
    chapters: dict[str, Any] = {}
    summary = Counter()
    for chapter in TARGET_CHAPTERS:
        base = read_json(run_dir / "01_outline/base" / f"ch{chapter:04d}.json")["outline_items"]
        entity = read_json(run_dir / "01_outline/entity" / f"ch{chapter:04d}.json")["outline_items"]
        diff = match_outline_items(base, entity)
        diff["chapter"] = chapter
        diff["base_item_count"] = len(base)
        diff["entity_item_count"] = len(entity)
        for pair in diff["pairs"]:
            summary[pair["status"]] += 1
        summary["base_only"] += len(diff["base_only"])
        summary["entity_only"] += len(diff["entity_only"])
        chapters[str(chapter)] = diff
    report = {
        "schema_version": "z59-b-dual-arm-diff-v1",
        "status": "candidate_samples_no_self_adjudication",
        "question": "模拟实体供料是否让大纲逻辑句的信息发生转变",
        "single_variable": "同章同一233事件池子集、同模型同参数；带表臂只多一条实体供料system块",
        "sampling_noise_limit": "两臂各自n=1且温度0.2；差异是本轮样张观察，不能排除随机采样波动，也不直接判长期胜负。",
        "summary": dict(sorted(summary.items())),
        "chapters": chapters,
    }
    cost = {
        "schema_version": "z59-b-cost-v1",
        "task": "试点B：五靶章大纲逻辑句带表／不带表双臂",
        "usage": usage_summary(run_dir),
        "source_of_truth": "usage.jsonl",
    }
    write_json(run_dir / "analysis/双臂逐条diff.json", report)
    write_json(run_dir / "analysis/成本账.json", cost)
    return {
        "diff_sha256": sha256_file(run_dir / "analysis/双臂逐条diff.json"),
        "cost_sha256": sha256_file(run_dir / "analysis/成本账.json"),
        "summary": report["summary"],
        "usage": cost["usage"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="第59道模拟实体供料双试点旁路工具")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-supply")
    build.add_argument("--output", required=True)
    verify = sub.add_parser("verify-supply")
    verify.add_argument("--supply-dir", required=True)
    prepare_a_parser = sub.add_parser("prepare-a")
    prepare_a_parser.add_argument("--supply-dir", required=True)
    prepare_a_parser.add_argument("--run-dir", required=True)
    run_a_parser = sub.add_parser("run-a")
    run_a_parser.add_argument("--run-dir", required=True)
    analyze_a_parser = sub.add_parser("analyze-a")
    analyze_a_parser.add_argument("--run-dir", required=True)
    prepare_b_parser = sub.add_parser("prepare-b")
    prepare_b_parser.add_argument("--supply-dir", required=True)
    prepare_b_parser.add_argument("--run-dir", required=True)
    run_b_parser = sub.add_parser("run-b")
    run_b_parser.add_argument("--run-dir", required=True)
    analyze_b_parser = sub.add_parser("analyze-b")
    analyze_b_parser.add_argument("--run-dir", required=True)
    return parser


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build-supply":
            result = build_supply(resolve_path(args.output))
        elif args.command == "verify-supply":
            result = verify_supply(resolve_path(args.supply_dir))
        elif args.command == "prepare-a":
            result = prepare_a(resolve_path(args.supply_dir), resolve_path(args.run_dir))
        elif args.command == "run-a":
            result = run_a(resolve_path(args.run_dir))
        elif args.command == "analyze-a":
            result = analyze_a(resolve_path(args.run_dir))
        elif args.command == "prepare-b":
            result = prepare_b(resolve_path(args.supply_dir), resolve_path(args.run_dir))
        elif args.command == "run-b":
            result = run_b(resolve_path(args.run_dir))
        elif args.command == "analyze-b":
            result = analyze_b(resolve_path(args.run_dir))
        else:  # pragma: no cover
            raise ZBatchError(f"未知命令：{args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ZBatchError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Freeze DEV_CORE windows before any semantic gold exists."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import argparse
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "dev_core"
REPO = ROOT.parents[2]
LAB = Path("/Users/a1234/挣钱/小说架构_隔离实验")
NOVELS = Path("/Users/a1234/挣钱/小说101-downloads")
NEWBOOK = NOVELS / "_newbook_rank_20260804" / "books"
AC = LAB / "T5_R04_A_C_FORMAT_COMPARE_20260807_R01"
LEDGER = REPO / "governance/progress/t5-r04-cross-window-material-selection-ledger.jsonl"

sys.path.insert(0, str(ROOT / "c2_unit_gate" / "tools"))
from c2_unit_common import atomize_region  # noqa: E402


SEED = "T5_R04_DEV_CORE_20260807_R02"
TARGET_WINDOWS = 48
TARGET_MIN = 600
TARGET_IDEAL = 700
TARGET_MAX = 800
MAX_UNIT_CHARS = 40
MIN_VISIBLE = 8
VISIBLE_BRIDGE_UNITS = 3
FOLLOWING_UNITS = 5


def canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_int(*parts: str) -> int:
    return int(hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest(), 16)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def background_from_user(user: str) -> dict[str, Any] | None:
    marker = "【小说背景卡｜只辅助理解，不代替证据】\n"
    if marker not in user:
        return None
    raw = user.split(marker, 1)[1].split("\n\n【短段身份】", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def collect_dataset_identities(path: Path) -> tuple[set[str], set[str]]:
    titles: set[str] = set()
    authors: set[str] = set()
    for row in read_jsonl(path):
        for message in row.get("messages", []):
            if message.get("role") != "user":
                continue
            card = background_from_user(message.get("content", ""))
            if not card:
                continue
            publication = card.get("publication") or {}
            title = publication.get("book_title")
            author = publication.get("author")
            if isinstance(title, str) and title not in {"", "unknown"}:
                titles.add(title)
            if isinstance(author, str) and author not in {"", "unknown", "来源不明"}:
                authors.add(author)
    return titles, authors


def exclusion_sets() -> tuple[set[str], set[str], dict[str, Any]]:
    sources = {
        "old_full_398": AC / "build/run_1/datasets/a/full_a.jsonl",
        "old_frozen_48": AC / "sealed/exams/a/QUESTIONS.jsonl",
        "current_r03_41": AC / "exam_rebalance_r03/sealed/a/QUESTIONS.jsonl",
    }
    titles: set[str] = set()
    authors: set[str] = set()
    details: dict[str, Any] = {}
    for name, path in sources.items():
        if not path.is_file():
            raise SystemExit(f"HARD_STOP missing exclusion source: {path}")
        one_titles, one_authors = collect_dataset_identities(path)
        titles |= one_titles
        authors |= one_authors
        details[name] = {
            "path": str(path),
            "sha256": sha_file(path),
            "title_count": len(one_titles),
            "author_count": len(one_authors),
        }
    active_ledger_rows = []
    for row in read_jsonl(LEDGER):
        if row.get("record_type") != "material_selection":
            continue
        if row.get("selection_status") not in {"PROPOSED", "PROPOSED_AUTHOR_PENDING", "SELECTED"}:
            continue
        titles.add(row["book_title"])
        authors.add(row["author"])
        active_ledger_rows.append(row.get("segment_id"))
    details["shared_selection_ledger"] = {
        "path": str(LEDGER),
        "sha256": sha_file(LEDGER),
        "active_material_rows": len(active_ledger_rows),
    }
    return titles, authors, details


def resolve_book(entry: dict[str, Any]) -> Path:
    roots = {"NEWBOOK_RANK": NEWBOOK, "NOVEL101_MAIN": NOVELS}
    return roots[entry["store_id"]] / entry["relative_path"]


def platform_and_url(book_dir: Path, entry: dict[str, Any]) -> tuple[str, str | None]:
    fetch = book_dir / "FETCH_META.json"
    if fetch.is_file():
        meta = json.loads(fetch.read_text(encoding="utf-8"))
        return str(meta.get("platform") or "unknown"), meta.get("bookHref")
    source = book_dir / "SOURCE.md"
    text = source.read_text(encoding="utf-8") if source.is_file() else ""
    url_match = re.search(r"https?://\S+", text)
    return "mirror_source", url_match.group(0) if url_match else None


def chapter_paths(book_dir: Path) -> list[Path]:
    fetch = book_dir / "FETCH_META.json"
    cache = book_dir / "chapters_cache"
    if fetch.is_file():
        meta = json.loads(fetch.read_text(encoding="utf-8"))
        ordered = [cache / item["file"] for item in meta.get("chapters_index", [])]
        return [path for path in ordered if path.is_file()]
    return sorted(cache.glob("*.txt"))


def cjk_ratio(text: str) -> float:
    visible = [ch for ch in text if not ch.isspace()]
    if not visible:
        return 0.0
    cjk = sum("\u3400" <= ch <= "\u9fff" for ch in visible)
    return cjk / len(visible)


def chapter_ok(text: str) -> bool:
    if not 1600 <= len(text) <= 6000:
        return False
    if cjk_ratio(text) < 0.55:
        return False
    if "�" in text or "\x00" in text or re.search(r"https?://|www\.", text, re.I):
        return False
    if re.search(r"[A-Za-z0-9_./=-]{100,}", text):
        return False
    if re.search(
        r"下载地址|手机阅读|最新网址|加入书签|本书首发|无错章节|"
        r"^读者[:：]|这本的主角依旧|迟早药丸",
        text,
        re.M,
    ):
        return False
    return True


def choose_from_stage(paths: list[Path], book_id: str, stage: int, salt: str) -> Path:
    n = len(paths)
    lo = n * stage // 3
    hi = n * (stage + 1) // 3
    pool = paths[lo:hi] or paths
    return min(pool, key=lambda path: stable_int(SEED, book_id, salt, path.name))


def choose_window(text: str, case_id: str) -> dict[str, Any]:
    units = atomize_region(text, "chapter", 0, len(text), MAX_UNIT_CHARS, MIN_VISIBLE)
    candidates: list[tuple[int, int, int]] = []
    for start in range(len(units)):
        total = 0
        for end in range(start, len(units)):
            total += len(units[end].text)
            if total > TARGET_MAX:
                break
            if total >= TARGET_MIN:
                candidates.append((start, end + 1, total))
    if not candidates:
        raise SystemExit(f"HARD_STOP no 600-800-char unit window for {case_id}")
    candidates.sort(key=lambda item: (abs(item[2] - TARGET_IDEAL), stable_int(SEED, case_id, str(item[0]))))
    shortlist = candidates[: max(1, min(20, len(candidates)))]
    start, end, target_chars = min(shortlist, key=lambda item: stable_int(SEED, case_id, "window", str(item[0])))
    bridge_start = max(0, start - VISIBLE_BRIDGE_UNITS)
    following_end = min(len(units), end + FOLLOWING_UNITS)
    return {
        "units": units,
        "bridge_start": bridge_start,
        "target_start": start,
        "target_end": end,
        "following_end": following_end,
        "target_chars": target_chars,
    }


def render_a(case_id: str, bridge: str, target: str, following: str) -> dict[str, Any]:
    system = (
        "你是中文小说核心事实抽取器。只判断本段负责区表达了哪些会影响后续大纲的核心事实。"
        "上文和下文只帮助理解，不能单独贡献答案。输出严格 JSON：{\"fact_sentences\":[\"...\"]}。"
        "不要输出证据、状态、说话人、编号或解释。"
    )
    user = (
        f"【题号】\n{case_id}\n\n【只读上文】\n{bridge or '（无）'}\n\n"
        f"【本段负责区】\n{target}\n\n【只读下文】\n{following or '（无）'}"
    )
    return {"case_id": case_id, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}


def render_c2(case_id: str, bridge_units: list[Any], target_units: list[Any], following: str) -> dict[str, Any]:
    system = (
        "你是中文小说核心事实抽取器。B/T 编号只表示原文位置，不能成为答案内容。"
        "只判断编号负责区表达了哪些会影响后续大纲的核心事实。编号上文和未编号下文只帮助理解，"
        "不能单独贡献答案。输出严格 JSON：{\"fact_sentences\":[\"...\"]}。"
        "不要输出证据、状态、说话人、编号或解释。"
    )
    bridge = "\n".join(f"[B{idx:02d}]{unit.text}" for idx, unit in enumerate(bridge_units, 1)) or "（无）"
    target = "\n".join(f"[T{idx:02d}]{unit.text}" for idx, unit in enumerate(target_units, 1))
    user = (
        f"【题号】\n{case_id}\n\n【编号只读上文】\n{bridge}\n\n"
        f"【编号负责区】\n{target}\n\n【未编号只读下文】\n{following or '（无）'}"
    )
    return {"case_id": case_id, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(canon(row) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="run_1")
    args = parser.parse_args()
    if Path(args.output_dir).name != args.output_dir:
        raise SystemExit("HARD_STOP output-dir must be one directory name")
    catalog_path = DEV / "DEV_CORE_BOOK_CATALOG.jsonl"
    catalog = read_jsonl(catalog_path)
    if len(catalog) < 30 or len({row["author"] for row in catalog}) != len(catalog):
        raise SystemExit("HARD_STOP catalog must contain at least 30 unique authors")

    excluded_titles, excluded_authors, exclusion_sources = exclusion_sets()
    collisions = [
        {"book_id": row["book_id"], "title": row["title"], "author": row["author"]}
        for row in catalog
        if row["title"] in excluded_titles or row["author"] in excluded_authors
    ]
    if collisions:
        print(canon({"status": "HARD_STOP_EXCLUSION_COLLISION", "collisions": collisions}))
        raise SystemExit(2)

    double_count = TARGET_WINDOWS - len(catalog)
    if double_count < 0:
        raise SystemExit("HARD_STOP catalog exceeds target windows")
    double_books = {
        row["book_id"]
        for row in sorted(catalog, key=lambda item: stable_int(SEED, "double", item["book_id"]))[:double_count]
    }

    source_rows: list[dict[str, Any]] = []
    a_rows: list[dict[str, Any]] = []
    c2_rows: list[dict[str, Any]] = []
    worksheet: list[dict[str, Any]] = []

    for entry in catalog:
        book_dir = resolve_book(entry)
        if not book_dir.is_dir():
            raise SystemExit(f"HARD_STOP missing book dir: {book_dir}")
        platform, source_url = platform_and_url(book_dir, entry)
        eligible: list[Path] = []
        chapter_texts: dict[Path, str] = {}
        for path in chapter_paths(book_dir):
            text = path.read_text(encoding="utf-8")
            if chapter_ok(text):
                eligible.append(path)
                chapter_texts[path] = text
        if len(eligible) < (2 if entry["book_id"] in double_books else 1):
            raise SystemExit(f"HARD_STOP insufficient clean chapters: {entry['book_id']} {len(eligible)}")

        first_stage = stable_int(SEED, entry["book_id"], "first-stage") % 3
        choices = [(first_stage, choose_from_stage(eligible, entry["book_id"], first_stage, "first"))]
        if entry["book_id"] in double_books:
            second_stage = (first_stage + 1 + stable_int(SEED, entry["book_id"], "second-stage") % 2) % 3
            second = choose_from_stage(eligible, entry["book_id"], second_stage, "second")
            if second == choices[0][1]:
                second = min((p for p in eligible if p != choices[0][1]), key=lambda p: stable_int(SEED, entry["book_id"], "second-fallback", p.name))
            choices.append((second_stage, second))

        for ordinal, (stage, chapter) in enumerate(choices, 1):
            case_id = f"DEVCORE2-{entry['book_id']}-W{ordinal:02d}"
            text = chapter_texts[chapter]
            chosen = choose_window(text, case_id)
            units = chosen["units"]
            bridge_units = units[chosen["bridge_start"] : chosen["target_start"]]
            target_units = units[chosen["target_start"] : chosen["target_end"]]
            following_units = units[chosen["target_end"] : chosen["following_end"]]
            bridge = "".join(unit.text for unit in bridge_units)
            target = "".join(unit.text for unit in target_units)
            following = "".join(unit.text for unit in following_units)
            source_text = bridge + target + following
            row = {
                "case_id": case_id,
                "book_id": entry["book_id"],
                "book_title": entry["title"],
                "author": entry["author"],
                "author_evidence": entry["author_evidence"],
                "platform": platform,
                "source_url": source_url,
                "rights_state": "RIGHTS_PENDING_FOR_TRAINING",
                "source_role": "INTERNAL_DEV_EVALUATION_ONLY",
                "chapter_pointer": str(chapter),
                "chapter_title": chapter.stem,
                "chapter_sha256": sha_file(chapter),
                "chapter_char_count": len(text),
                "story_stage": ["FRONT", "MIDDLE", "BACK"][stage],
                "bridge_char_start": units[chosen["bridge_start"]].start if bridge_units else units[chosen["target_start"]].start,
                "target_char_start": target_units[0].start,
                "target_char_end": target_units[-1].end,
                "following_char_end": following_units[-1].end if following_units else target_units[-1].end,
                "bridge_text": bridge,
                "target_text": target,
                "following_text": following,
                "source_text_sha256": sha_text(source_text),
                "target_text_sha256": sha_text(target),
                "visible_bridge_unit_count": len(bridge_units),
                "target_unit_count": len(target_units),
                "target_char_count": len(target),
                "cross_unit_possible": len(target_units) > 1,
                "selection_basis": "GOLD_FREE_STABLE_HASH_PLUS_FROZEN_ATOMIZER_R02",
            }
            source_rows.append(row)
            a_rows.append(render_a(case_id, bridge, target, following))
            c2_rows.append(render_c2(case_id, bridge_units, target_units, following))
            worksheet.append({
                "case_id": case_id,
                "source_text_sha256": row["source_text_sha256"],
                "target_text_sha256": row["target_text_sha256"],
                "fact_sentences": None,
                "annotation_status": "PENDING_INDEPENDENT_SEMANTIC_REVIEW",
            })

    if len(source_rows) != TARGET_WINDOWS:
        raise SystemExit(f"HARD_STOP window denominator {len(source_rows)} != {TARGET_WINDOWS}")
    if len({row["author"] for row in source_rows}) < 30:
        raise SystemExit("HARD_STOP fewer than 30 authors")
    if len({row["case_id"] for row in source_rows}) != TARGET_WINDOWS:
        raise SystemExit("HARD_STOP duplicate case_id")

    out = DEV / args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "SOURCE_WINDOWS.jsonl", source_rows)
    write_jsonl(out / "A_CORE_QUESTIONS.jsonl", a_rows)
    write_jsonl(out / "C2_CORE_QUESTIONS.jsonl", c2_rows)
    write_jsonl(out / "CORE_GOLD_WORKSHEET.jsonl", worksheet)
    lock = {
        "schema_version": "t5-r04-dev-core-selection-lock-v1",
        "status": "SELECTION_FROZEN_BEFORE_GOLD",
        "seed": SEED,
        "window_count": len(source_rows),
        "author_count": len({row["author"] for row in source_rows}),
        "book_count": len({row["book_id"] for row in source_rows}),
        "books_with_two_windows": len(double_books),
        "same_book_same_chapter_collisions": 0,
        "selection_used_gold": False,
        "selection_used_model_outputs": False,
        "atomizer": {"revision": "R02", "max_chars": MAX_UNIT_CHARS, "min_visible": MIN_VISIBLE},
        "exclusion_sources": exclusion_sources,
        "catalog_sha256": sha_file(catalog_path),
        "rules_sha256": sha_file(DEV / "DEV_CORE_SELECTION_RULES.md"),
        "source_windows_sha256": sha_file(out / "SOURCE_WINDOWS.jsonl"),
        "a_questions_sha256": sha_file(out / "A_CORE_QUESTIONS.jsonl"),
        "c2_questions_sha256": sha_file(out / "C2_CORE_QUESTIONS.jsonl"),
        "worksheet_sha256": sha_file(out / "CORE_GOLD_WORKSHEET.jsonl"),
    }
    (out / "DEV_CORE_SELECTION_LOCK.json").write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(lock, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

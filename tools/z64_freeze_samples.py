#!/usr/bin/env python3
"""第64道：冻结可复跑的分层语义抽查名单（0 模型 API 调用）。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "TEMP/z61_chatgpt_pro_three_window_returns_20260720"
RAW = ARCHIVE / "raw"
TWO_STEP = (
    ARCHIVE
    / "expanded/addendum_0442/two_step/诡秘之主_第01-50章_七类整理"
)
ONE_STEP = ARCHIVE / "expanded/addendum_0442/one_step/novel50_analysis"
DEFAULT_OUT = ROOT / "reports/Z64_三窗回包语义抽查与差距表_20260720"

EVENT50 = RAW / "诡秘之主_第1-50章_事件记录与设定卡/01_事件记录.json"
EVIDENCE50 = RAW / "诡秘之主_第01-50章_逐章证据条目.md"
EVENT20 = RAW / "novel_ch01-20_events_and_setting_cards.md"

SEEDS = {
    "event50": "Z64-20260720-event50-v2",
    "evidence50": "Z64-20260720-evidence1761-v2",
    "event20": "Z64-20260720-event20-v2",
    "two_step": "Z64-20260720-two-step-v2",
    "one_step": "Z64-20260720-one-step-v2",
}

CATEGORY_FILES = {
    "世界观设定": "01_世界观设定.md",
    "人物档案": "02_人物档案.md",
    "地点档案": "03_地点档案.md",
    "人物关系": "04_人物关系.md",
    "每章大纲": "05_每章大纲.md",
    "逻辑句": None,
    "每章写法": "07_每章写法分析.md",
}

EXPECTED = {
    "event50": {"total": 308, "types": {"A": 145, "B": 21, "C": 50, "D": 92}},
    "evidence50": 1761,
    "event20": {"total": 206, "types": {"A": 97, "B": 21, "C": 31, "D": 57}},
    "two_step": {
        "世界观设定": 143,
        "人物档案": 72,
        "地点档案": 99,
        "人物关系": 59,
        "每章大纲": 50,
        "逻辑句": 94,
        "每章写法": 50,
    },
    "one_step": {
        "世界观设定": 60,
        "人物档案": 55,
        "地点档案": 70,
        "人物关系": 45,
        "每章大纲": 50,
        "逻辑句": 56,
        "每章写法": 50,
    },
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_rank(seed: str, identity: str) -> str:
    return hashlib.sha256(f"{seed}\0{identity}".encode("utf-8")).hexdigest()


def chapter_of(record: dict[str, Any]) -> int:
    value = str(record.get("章节位置", ""))
    match = re.search(r"第\s*0*(\d+)\s*章", value)
    if not match:
        raise ValueError(f"无法读取章号：{record.get('id')} {value!r}")
    return int(match.group(1))


def load_event50() -> list[dict[str, Any]]:
    return json.loads(read_text(EVENT50))["records"]


def load_event20() -> list[dict[str, Any]]:
    text = read_text(EVENT20)
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.S)
    if not match:
        raise ValueError("20章事件记录没有找到首个 JSON 代码块")
    return json.loads(match.group(1))["records"]


def load_evidence50() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_chapter: int | None = None
    chapter_re = re.compile(r"^## 第0*(\d+)章")
    item_re = re.compile(r"^- \*\*(E-(\d{2})-\d{2,3})\*\*\s+(.*)$")
    for line_no, line in enumerate(read_text(EVIDENCE50).splitlines(), start=1):
        chapter_match = chapter_re.match(line)
        if chapter_match:
            current_chapter = int(chapter_match.group(1))
            continue
        item_match = item_re.match(line)
        if not item_match:
            continue
        eid, eid_chapter, statement = item_match.groups()
        eid_chapter_int = int(eid_chapter)
        if current_chapter != eid_chapter_int:
            raise ValueError(f"{eid} 的标题章号与 ID 章号不一致")
        rows.append(
            {
                "id": eid,
                "chapter": eid_chapter_int,
                "statement": statement,
                "source_line": line_no,
            }
        )
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("1,761 母集存在重复 E ID")
    return rows


def counts_by_type(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row["type"]) for row in records).items()))


def event_view(row: dict[str, Any], population: str) -> dict[str, Any]:
    view = {
        "population": population,
        "id": row["id"],
        "type": row["type"],
        "chapter": chapter_of(row),
        "status": row.get("status"),
        "type_state": row.get("type_state"),
        "assertion": row.get("assertion"),
        "related_ids": row.get("related_ids", []),
        "anchors": row.get("anchors", []),
        "source_quote": row.get("原文依据"),
    }
    for key in (
        "story_line",
        "delta",
        "direct_cause",
        "future_use",
        "trigger_condition",
        "trigger_action",
        "reader_expectation",
        "payoff_test",
        "condition",
        "consequence",
        "scope_exception",
    ):
        if key in row:
            view[key] = row[key]
    return view


def banded_event_sample(
    records: list[dict[str, Any]],
    target: int,
    seed: str,
    chapter_ranges: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    """每个章段先取等额样本，不足部分再按稳定哈希从全体补齐。"""
    base = target // len(chapter_ranges)
    remainder = target % len(chapter_ranges)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for index, (start, end) in enumerate(chapter_ranges):
        quota = base + (1 if index < remainder else 0)
        candidates = [row for row in records if start <= chapter_of(row) <= end]
        candidates.sort(key=lambda row: stable_rank(seed, str(row["id"])))
        for row in candidates[:quota]:
            selected.append(row)
            selected_ids.add(str(row["id"]))
    if len(selected) < target:
        leftovers = [row for row in records if str(row["id"]) not in selected_ids]
        leftovers.sort(key=lambda row: stable_rank(seed, str(row["id"])))
        selected.extend(leftovers[: target - len(selected)])
    if len(selected) != target:
        raise ValueError(f"样本不足：需要 {target}，实际 {len(selected)}")
    return sorted(selected, key=lambda row: (chapter_of(row), str(row["id"])))


def sample_events(
    records: list[dict[str, Any]],
    population: str,
    targets: dict[str, int | str],
    seed: str,
    chapter_ranges: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_type[str(row["type"])].append(row)
    chosen: list[dict[str, Any]] = []
    for event_type in "ABCD":
        target = targets[event_type]
        type_rows = by_type[event_type]
        picked = (
            sorted(type_rows, key=lambda row: (chapter_of(row), str(row["id"])))
            if target == "all"
            else banded_event_sample(
                type_rows,
                int(target),
                f"{seed}:{event_type}",
                chapter_ranges,
            )
        )
        chosen.extend(event_view(row, population) for row in picked)
    return sorted(chosen, key=lambda row: (row["type"], row["chapter"], row["id"]))


def sample_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_chapter: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_chapter[int(row["chapter"])].append(row)
    chosen: list[dict[str, Any]] = []
    for chapter in range(1, 51):
        candidates = by_chapter[chapter]
        if not candidates:
            raise ValueError(f"1,761 母集第 {chapter} 章为空")
        candidates.sort(
            key=lambda row: stable_rank(SEEDS["evidence50"], str(row["id"]))
        )
        row = candidates[0]
        chosen.append({"population": "50章窗3逐章证据", **row})
    return chosen


def split_heading_units(text: str, heading_pattern: str) -> list[dict[str, Any]]:
    pattern = re.compile(heading_pattern, flags=re.M)
    matches = list(pattern.finditer(text))
    units: list[dict[str, Any]] = []
    for index, match in enumerate(matches, start=1):
        end = matches[index].start() if index < len(matches) else len(text)
        body = text[match.end() : end].strip()
        units.append(
            {
                "index": index,
                "title": match.group(0).strip(),
                "text": f"{match.group(0).strip()}\n{body}".strip(),
            }
        )
    return units


def split_two_step_world(text: str) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for line in text.splitlines():
        if line.startswith("- ") and "（依据：" in line:
            units.append(
                {
                    "index": len(units) + 1,
                    "title": line[2:].split("。（依据：", 1)[0][:80],
                    "text": line,
                }
            )
    return units


def split_one_step_places(text: str) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] == "地点" or re.fullmatch(r"[-: ]+", cells[0]):
            continue
        units.append(
            {
                "index": len(units) + 1,
                "title": cells[0],
                "text": line,
            }
        )
    return units


def add_unit_metadata(
    units: list[dict[str, Any]], package: str, category: str
) -> list[dict[str, Any]]:
    for unit in units:
        text = unit["text"]
        chapter_match = re.search(r"第0*(\d+)章", unit["title"])
        unit.update(
            {
                "package": package,
                "category": category,
                "unit_id": f"{package}:{category}:{unit['index']:03d}",
                "chapter": int(chapter_match.group(1)) if chapter_match else None,
                "evidence_ids": sorted(set(re.findall(r"E-\d{2}-\d{2,3}", text))),
                "chapter_quote_refs": re.findall(
                    r"(?:第\d+(?:[—～~-]\d+)?章)[^\n]{0,100}?[“\"]([^”\"]+)[”\"]",
                    text,
                ),
                "field_claim_count": max(1, len(re.findall(r"^- \*\*", text, flags=re.M))),
            }
        )
    return units


def load_package_units(package: str) -> dict[str, list[dict[str, Any]]]:
    base = TWO_STEP if package == "two_step" else ONE_STEP
    logic_name = "06_逻辑句_因果用.md" if package == "two_step" else "06_逻辑句_因果兑现.md"
    result: dict[str, list[dict[str, Any]]] = {}
    for category, filename in CATEGORY_FILES.items():
        filename = logic_name if category == "逻辑句" else filename
        assert filename is not None
        text = read_text(base / filename)
        if package == "two_step" and category == "世界观设定":
            units = split_two_step_world(text)
        elif package == "one_step" and category == "地点档案":
            units = split_one_step_places(text)
        elif category in {"每章大纲", "每章写法"}:
            units = split_heading_units(text, r"^## 第0*\d+章[^\n]*")
        elif package == "one_step":
            units = split_heading_units(text, r"^### \d+\.[^\n]*")
        else:
            units = split_heading_units(text, r"^### [^\n]+")
        result[category] = add_unit_metadata(units, package, category)
    return result


def sample_units(
    units_by_category: dict[str, list[dict[str, Any]]], package: str
) -> list[dict[str, Any]]:
    """每类按文档顺序切五段，每段稳定哈希选一项。"""
    chosen: list[dict[str, Any]] = []
    for category in CATEGORY_FILES:
        units = units_by_category[category]
        length = len(units)
        for band in range(5):
            start = (band * length) // 5
            end = ((band + 1) * length) // 5
            candidates = units[start:end]
            if not candidates:
                raise ValueError(f"{package}/{category} 第 {band + 1} 段为空")
            candidates.sort(
                key=lambda row: stable_rank(
                    f"{SEEDS[package]}:{category}:{band + 1}", row["unit_id"]
                )
            )
            selected = dict(candidates[0])
            selected["sampling_band"] = band + 1
            chosen.append(selected)
    return chosen


def assert_population_counts(
    event50: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    event20: list[dict[str, Any]],
    two_units: dict[str, list[dict[str, Any]]],
    one_units: dict[str, list[dict[str, Any]]],
) -> None:
    actual_event50 = {"total": len(event50), "types": counts_by_type(event50)}
    actual_event20 = {"total": len(event20), "types": counts_by_type(event20)}
    actual_two = {key: len(value) for key, value in two_units.items()}
    actual_one = {key: len(value) for key, value in one_units.items()}
    checks = {
        "event50": (actual_event50, EXPECTED["event50"]),
        "evidence50": (len(evidence), EXPECTED["evidence50"]),
        "event20": (actual_event20, EXPECTED["event20"]),
        "two_step": (actual_two, EXPECTED["two_step"]),
        "one_step": (actual_one, EXPECTED["one_step"]),
    }
    mismatches = {
        key: {"actual": actual, "expected": expected}
        for key, (actual, expected) in checks.items()
        if actual != expected
    }
    if mismatches:
        raise ValueError(
            "母集或新增回包计数漂移："
            + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
        )


def build_payload() -> dict[str, Any]:
    event50 = load_event50()
    evidence = load_evidence50()
    event20 = load_event20()
    two_units = load_package_units("two_step")
    one_units = load_package_units("one_step")
    assert_population_counts(event50, evidence, event20, two_units, one_units)

    samples = {
        "50章窗2事件记录": sample_events(
            event50,
            "50章窗2事件记录",
            {"A": 20, "B": "all", "C": 20, "D": 20},
            SEEDS["event50"],
            [(1, 10), (11, 20), (21, 30), (31, 40), (41, 50)],
        ),
        "50章窗3逐章证据": sample_evidence(evidence),
        "20章窗2事件记录": sample_events(
            event20,
            "20章窗2事件记录",
            {"A": 8, "B": 8, "C": 8, "D": 8},
            SEEDS["event20"],
            [(1, 5), (6, 10), (11, 15), (16, 20)],
        ),
        "两步法新增包": sample_units(two_units, "two_step"),
        "一步直出新增包": sample_units(one_units, "one_step"),
    }
    sample_counts = {key: len(value) for key, value in samples.items()}
    sample_identities = {
        population: [
            row.get("unit_id") or row.get("id")
            for row in rows
        ]
        for population, rows in samples.items()
    }
    sample_identity_sha256 = hashlib.sha256(
        json.dumps(
            sample_identities,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "task": "第64道续令：三窗回包语义抽查扩展名单",
        "created_at": "2026-07-20",
        "model_api_calls": 0,
        "decision_basis": "CZ 04:49 改判：逐章证据母集以现存1,761条实物为准",
        "rules": {
            "50章窗2事件记录": "A/C/D各20；B仅21条，故全取；每类先按五个十章段均额取样，再用稳定哈希补足。",
            "50章窗3逐章证据": "1,761个唯一E ID中每章稳定哈希取1条，50章全覆盖。",
            "20章窗2事件记录": "A/B/C/D各8；每类按四个五章段均额取样。",
            "两个新增包": "每包七类各取5个主单元；各类按文档顺序切五段，每段稳定哈希取1个。主单元连同其全部字段和证据一起复核。",
            "可重复性": "SHA-256(seed + NUL + stable_identity) 排序；不依赖系统随机数、时间或运行目录。",
        },
        "seeds": SEEDS,
        "sample_identity_sha256": sample_identity_sha256,
        "populations": {
            "50章窗2事件记录": {"total": 308, "types": EXPECTED["event50"]["types"]},
            "50章窗3逐章证据": {"total": 1761, "chapters": 50},
            "20章窗2事件记录": {"total": 206, "types": EXPECTED["event20"]["types"]},
            "两步法新增包": EXPECTED["two_step"],
            "一步直出新增包": EXPECTED["one_step"],
        },
        "source_files": {
            "sampling_script": {
                "path": str(Path(__file__).resolve().relative_to(ROOT)),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
            "event50": {"path": str(EVENT50.relative_to(ROOT)), "sha256": sha256_file(EVENT50)},
            "evidence50": {"path": str(EVIDENCE50.relative_to(ROOT)), "sha256": sha256_file(EVIDENCE50)},
            "event20": {"path": str(EVENT20.relative_to(ROOT)), "sha256": sha256_file(EVENT20)},
            "two_step_zip": {
                "path": "TEMP/z61_chatgpt_pro_three_window_returns_20260720/raw/addendum_0442/诡秘之主_第01-50章_七类整理_全套.zip",
                "sha256": sha256_file(ARCHIVE / "raw/addendum_0442/诡秘之主_第01-50章_七类整理_全套.zip"),
            },
            "one_step_zip": {
                "path": "TEMP/z61_chatgpt_pro_three_window_returns_20260720/raw/addendum_0442/小说前50章_七类整理_证据版.zip",
                "sha256": sha256_file(ARCHIVE / "raw/addendum_0442/小说前50章_七类整理_证据版.zip"),
            },
        },
        "sample_counts": {**sample_counts, "total_primary_units": sum(sample_counts.values())},
        "samples": samples,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 第64道续令｜分层语义抽查冻结名单",
        "",
        "这份名单只决定抽哪些条目，不预判对错。全部选择由固定种子和稳定身份生成，模型 API 调用数为 0。",
        "",
        "## 母集与抽样规模",
        "",
        "| 材料 | 母集 | 本次主单元 |",
        "|---|---:|---:|",
    ]
    population_labels = {
        "50章窗2事件记录": "308（A145/B21/C50/D92）",
        "50章窗3逐章证据": "1,761（50章）",
        "20章窗2事件记录": "206（A97/B21/C31/D57）",
        "两步法新增包": "七类合计567个主单元",
        "一步直出新增包": "七类合计386个主单元",
    }
    for label, count in payload["sample_counts"].items():
        if label == "total_primary_units":
            continue
        lines.append(f"| {label} | {population_labels[label]} | {count} |")
    lines.extend(
        [
            "",
            f"合计冻结 **{payload['sample_counts']['total_primary_units']} 个主单元**。新增包的一个主单元可能含多个字段，复核时整组一起判。",
            "",
            "## 规则",
            "",
        ]
    )
    for name, rule in payload["rules"].items():
        lines.append(f"- **{name}**：{rule}")
    lines.extend(["", "## 名单", ""])
    for population, rows in payload["samples"].items():
        lines.append(f"### {population}（{len(rows)}）")
        lines.append("")
        for row in rows:
            if "type" in row:
                label = f"{row['id']}｜{row['type']}｜第{row['chapter']}章"
            elif "unit_id" in row:
                chapter = f"｜第{row['chapter']}章" if row.get("chapter") else ""
                label = f"{row['unit_id']}｜{row['title']}{chapter}"
            else:
                label = f"{row['id']}｜第{row['chapter']}章"
            lines.append(f"- {label}")
        lines.append("")
    lines.extend(["来源：Codex", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true", help="只校验并打印摘要，不写文件")
    args = parser.parse_args()

    payload = build_payload()
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        print(json.dumps(payload["sample_counts"], ensure_ascii=False, sort_keys=True))
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "抽样方案与冻结名单.json"
    md_path = args.out / "抽样方案与冻结名单.md"
    json_path.write_text(serialized, encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(f"JSON={json_path}")
    print(f"JSON_SHA256={sha256_file(json_path)}")
    print(f"MD={md_path}")
    print(f"MD_SHA256={sha256_file(md_path)}")
    print(json.dumps(payload["sample_counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

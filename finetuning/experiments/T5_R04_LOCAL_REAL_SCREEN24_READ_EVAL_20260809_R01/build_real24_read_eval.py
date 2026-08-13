from __future__ import annotations

import hashlib
import json
import re
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "finetuning/experiments/T5_R04_REAL_NOVEL_CONFIRM24_SOURCE_SELECTION_20260809_R01"
CANDIDATES = SOURCE_DIR / "CONFIRM24_SEGMENT_CANDIDATES.md"
SOURCE_BOOKS = SOURCE_DIR / "CONFIRM24_SOURCE_BOOKS_AND_CHAPTERS.md"
BOOK_ROOT = Path("/Users/a1234/挣钱/小说101-downloads/_newbook_rank_20260804/books")
GOLD = OUT / "REAL24_GOLD_24.jsonl"
DIAGNOSTIC = OUT / "REAL24_ENTITY_DIAGNOSTIC.jsonl"

TRAIN36_LOCKS = {
    ROOT
    / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN36_RENDER_20260809_R01"
    / "TRAIN36_GOLD_36.jsonl": "4ed02087b5a9b9f952f1fa80b02a60f0f6c7ed2db3ac65d955dc97e3219b3ef9",
    ROOT
    / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN36_RENDER_20260809_R01"
    / "READ_1_TARGET_TRAIN36.jsonl": "84ad6f7886b372334b008d49cc2f3343afdd6b98d83a24a00d604ae49b8f09e0",
    ROOT
    / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN36_RENDER_20260809_R01"
    / "READ_2_HALO180_TRAIN36.jsonl": "09fdbc52f7131f1a2a60552740ce28430e418ed84c858f0f997abda16e4a7c5e",
    ROOT
    / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN36_RENDER_20260809_R01"
    / "READ_4_FULL_CHAPTER_TRAIN36.jsonl": "93b3ab7e9beed9a6f54df751400ba2ac65cfd5a18f1865da01c7c0c81540ed4a",
}

SYSTEM = (
    "你是中文小说事实抽取器。B/T 编号只表示原文位置。"
    "只抽取【编号负责区】明确表达、会影响后续情节的事实。"
    "每条事实必须包含 fact、status、speaker、evidence_ids；"
    "evidence_ids 选择覆盖证据的最小连续 T 编号集合。"
    "输出严格 JSON，不要解释。"
)
USER_PREFIX = "【只读范围：只帮助理解，不得作为新增事实或证据】\n"
TARGET_PREFIX = "\n\n【编号负责区：只抽这里】\n"
ALLOW_PREFIX = "\n\n【允许证据 ID】\n"
STATUS_ONTOLOGY = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}
EXPECTED_CASES = [f"C{i:02d}" for i in range(1, 25)]
ARM_FILES = {
    "READ-1-TARGET": OUT / "READ_1_TARGET_EVAL24.jsonl",
    "READ-2-HALO180": OUT / "READ_2_HALO180_EVAL24.jsonl",
    "READ-4-FULL-CHAPTER": OUT / "READ_4_FULL_CHAPTER_EVAL24.jsonl",
}
SOURCE_FOOTER = re.compile(r"(?m)^来源：Codex[ \t]*(?:\r?\n)*\Z")
SOURCE_ANOMALIES = {
    "C03": ["目标尾部有疑似站点数字；保留原文但不计为事实。"],
    "C06": ["春婵/春蝉按同一人物异体处理；共同答案仍用目标可见称呼。"],
    "C07": ["缓存编号为0003，文件标题写第二章；只记录，不改路径或坐标。"],
    "C09": ["目标尾部有疑似站点注释符号；保留原文但不计为事实。"],
    "C13": ["目标内夹有明显站外/读者插话；保留原文但不计为事实。"],
    "C18": ["目标尾部有晋江数字/注释噪声；保留原文但不计为事实。"],
    "C22": ["目标尾部有晋江数字/注释噪声；保留原文但不计为事实。"],
    "C24": ["目标内有晋江注释符号噪声；保留原文但不计为事实。"],
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def split_units(text: str, max_chars: int = 40) -> list[dict[str, Any]]:
    """Demo-compatible punctuation-aware splitter copied from frozen MICRO24."""
    if not text:
        return []
    strong = set("。！？!?；;\n")
    medium = set("，,：:、")
    units: list[dict[str, Any]] = []
    start = 0
    while start < len(text):
        hard_end = min(start + max_chars, len(text))
        end = hard_end
        if hard_end < len(text):
            min_cut = start + max(12, max_chars // 2)
            strong_pos = [i + 1 for i in range(min_cut, hard_end) if text[i] in strong]
            medium_pos = [i + 1 for i in range(min_cut, hard_end) if text[i] in medium]
            if strong_pos:
                end = strong_pos[-1]
            elif medium_pos:
                end = medium_pos[-1]
        if end <= start:
            end = min(start + max_chars, len(text))
        units.append({"start": start, "end": end, "text": text[start:end]})
        start = end
    return units


def parse_candidates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in CANDIDATES.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\| C\d{2} \|", line):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) != 8:
            continue
        case_id = cells[0]
        relative_path = cells[2].strip("`")
        match = re.fullmatch(r"\[(\d+),\s*(\d+)\)", cells[3].strip("`"))
        if match is None:
            raise AssertionError(f"bad candidate coordinates: {case_id}")
        start, end = (int(value) for value in match.groups())
        rows.append(
            {
                "case_id": case_id,
                "book_title": Path(relative_path).parts[0],
                "relative_source_path": relative_path,
                "target_start": start,
                "target_end": end,
                "source_anomalies": SOURCE_ANOMALIES.get(case_id, []),
            }
        )
    if [row["case_id"] for row in rows] != EXPECTED_CASES:
        raise AssertionError("candidate table must provide C01-C24 exactly once and in order")
    if len({row["book_title"] for row in rows}) != 24:
        raise AssertionError("REAL24 books are not unique")
    if len({row["relative_source_path"] for row in rows}) != 24:
        raise AssertionError("REAL24 chapter paths are not unique")
    return rows


def clean_model_visible_chapter(source_text: str, start: int, end: int, case_id: str) -> str:
    matches = list(SOURCE_FOOTER.finditer(source_text))
    if not matches:
        return source_text
    if len(matches) != 1:
        raise AssertionError(f"multiple terminal Codex source lines: {case_id}")
    footer = matches[0]
    if start < footer.end() and end > footer.start():
        raise AssertionError(f"source footer overlaps target: {case_id}")
    visible_text = source_text[: footer.start()].rstrip()
    if end > len(visible_text) or visible_text[start:end] != source_text[start:end]:
        raise AssertionError(f"footer cleaning changed target coordinates: {case_id}")
    return visible_text


def stats(values: list[int]) -> dict[str, int | float]:
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 3),
    }


def validate_gold(gold_rows: list[dict[str, Any]], txx_rows: list[dict[str, Any]]) -> int:
    if [row.get("case_id") for row in gold_rows] != EXPECTED_CASES:
        raise AssertionError("REAL24 Gold case set/order drift")
    txx_by_case = {row["case_id"]: row for row in txx_rows}
    total_facts = 0
    for row in gold_rows:
        case_id = row["case_id"]
        if row.get("dataset_status") != "LOCAL_EVAL_ONLY_RIGHTS_PENDING":
            raise AssertionError(f"bad Gold rights status: {case_id}")
        if set(row) != {"case_id", "dataset_status", "facts"}:
            raise AssertionError(f"unexpected Gold fields: {case_id}")
        valid_ids = [unit["id"] for unit in txx_by_case[case_id]["target_units"]]
        for fact in row["facts"]:
            if set(fact) != {"fact_sentence", "status", "speaker", "evidence_ids"}:
                raise AssertionError(f"bad fact fields: {case_id}")
            if not isinstance(fact["fact_sentence"], str) or not fact["fact_sentence"].strip():
                raise AssertionError(f"empty fact: {case_id}")
            if fact["status"] not in STATUS_ONTOLOGY:
                raise AssertionError(f"illegal status: {case_id}")
            if fact["speaker"] is not None and not isinstance(fact["speaker"], str):
                raise AssertionError(f"bad speaker: {case_id}")
            evidence_ids = fact["evidence_ids"]
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise AssertionError(f"empty evidence: {case_id}")
            try:
                positions = [valid_ids.index(evidence_id) for evidence_id in evidence_ids]
            except ValueError as exc:
                raise AssertionError(f"foreign evidence ID: {case_id}") from exc
            if positions != sorted(set(positions)):
                raise AssertionError(f"duplicate or unordered evidence: {case_id}")
            if positions != list(range(positions[0], positions[-1] + 1)):
                raise AssertionError(f"non-contiguous evidence: {case_id}")
            total_facts += 1
    return total_facts


def validate_diagnostics(rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> None:
    if [row.get("case_id") for row in rows] != ["C06", "C18"]:
        raise AssertionError("entity diagnostics must contain only C06 and C18")
    source_by_case = {row["case_id"]: row for row in source_rows}
    for row in rows:
        case_id = row["case_id"]
        source_row = source_by_case[case_id]
        if row.get("dataset_status") != "LOCAL_EVAL_ONLY_RIGHTS_PENDING":
            raise AssertionError(f"bad diagnostic status: {case_id}")
        if row.get("source_sha256") != source_row["source_sha256"]:
            raise AssertionError(f"diagnostic source SHA drift: {case_id}")
        if row.get("target_sha256") != source_row["target_sha256"]:
            raise AssertionError(f"diagnostic target SHA drift: {case_id}")
        source_text = Path(source_row["source_path"]).read_bytes().decode("utf-8", errors="strict")
        for resolution in row.get("resolutions", []):
            for anchor in resolution.get("remote_anchors", []):
                actual = source_text[anchor["start"] : anchor["end"]]
                if actual != anchor["text"] or sha256_bytes(actual.encode("utf-8")) != anchor["text_sha256"]:
                    raise AssertionError(f"diagnostic anchor drift: {case_id}")


def build() -> dict[str, Any]:
    for path, expected_sha in TRAIN36_LOCKS.items():
        if sha256_bytes(path.read_bytes()) != expected_sha:
            raise AssertionError(f"protected TRAIN36 file drift: {path.name}")
    if not SOURCE_BOOKS.is_file():
        raise AssertionError("source-books registry missing")

    candidate_rows = parse_candidates()
    source_rows: list[dict[str, Any]] = []
    txx_rows: list[dict[str, Any]] = []
    source_texts: dict[str, str] = {}
    visible_texts: dict[str, str] = {}
    targets: dict[str, str] = {}
    for candidate in candidate_rows:
        case_id = candidate["case_id"]
        source_path = BOOK_ROOT / candidate["relative_source_path"]
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        if source_text.encode("utf-8") != source_bytes:
            raise AssertionError(f"source is not strict UTF-8 round-trippable: {case_id}")
        start = candidate["target_start"]
        end = candidate["target_end"]
        if not (0 <= start < end <= len(source_text)):
            raise AssertionError(f"target coordinates out of range: {case_id}")
        target = source_text[start:end]
        visible_text = clean_model_visible_chapter(source_text, start, end, case_id)
        source_texts[case_id] = source_text
        visible_texts[case_id] = visible_text
        targets[case_id] = target
        source_rows.append(
            {
                "schema_version": "local-real-screen24-source-index/1.0",
                "dataset_status": "LOCAL_EVAL_ONLY_RIGHTS_PENDING",
                "case_id": case_id,
                "book_title": candidate["book_title"],
                "source_path": str(source_path),
                "relative_source_path": candidate["relative_source_path"],
                "source_sha256": sha256_bytes(source_bytes),
                "source_byte_count": len(source_bytes),
                "source_character_count": len(source_text),
                "coordinate_space": "unicode_codepoint_0_based_half_open",
                "target_start": start,
                "target_end": end,
                "target_sha256": sha256_bytes(target.encode("utf-8")),
                "rights_boundary": "LOCAL_EVAL_ONLY_RIGHTS_PENDING",
                "source_anomalies": candidate["source_anomalies"],
            }
        )
        units = split_units(target, max_chars=40)
        for index, unit in enumerate(units, start=1):
            unit["id"] = f"T{index:02d}"
        if not units or len(units) > 99 or "".join(unit["text"] for unit in units) != target:
            raise AssertionError(f"Txx reconstruction failed: {case_id}")
        txx_rows.append(
            {
                "schema_version": "local-real-screen24-txx-map/1.0",
                "dataset_status": "LOCAL_EVAL_ONLY_RIGHTS_PENDING",
                "case_id": case_id,
                "target_sha256": sha256_bytes(target.encode("utf-8")),
                "atomizer": {
                    "name": "MICRO24_DEMO_PUNCT_AWARE",
                    "max_chars": 40,
                    "production_c2_unit_claim": False,
                },
                "target_units": units,
            }
        )

    gold_rows = read_jsonl(GOLD)
    total_facts = validate_gold(gold_rows, txx_rows)
    diagnostic_rows = read_jsonl(DIAGNOSTIC)
    validate_diagnostics(diagnostic_rows, source_rows)

    rendered: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARM_FILES}
    visible_lengths: dict[str, list[int]] = {arm: [] for arm in ARM_FILES}
    for source_row, txx_row in zip(source_rows, txx_rows, strict=True):
        case_id = source_row["case_id"]
        target = targets[case_id]
        visible_text = visible_texts[case_id]
        start = source_row["target_start"]
        end = source_row["target_end"]
        left_start = max(0, start - 180)
        right_end = min(len(visible_text), end + 180)
        halo = visible_text[left_start:right_end]
        if not (len(target) < len(halo) < len(visible_text)):
            raise AssertionError(f"READ ranges are not strictly nested: {case_id}")
        if target not in halo or halo not in visible_text:
            raise AssertionError(f"READ ranges are not literal nested slices: {case_id}")
        read_texts = {
            "READ-1-TARGET": target,
            "READ-2-HALO180": halo,
            "READ-4-FULL-CHAPTER": visible_text,
        }
        units = txx_row["target_units"]
        numbered_target = "".join(f"[{unit['id']}]{unit['text']}" for unit in units)
        allowlist = "、".join(unit["id"] for unit in units)
        for arm, read_text in read_texts.items():
            if read_text.count(target) != 1:
                raise AssertionError(f"target must occur once in front READ_TEXT: {arm}: {case_id}")
            user = USER_PREFIX + read_text + TARGET_PREFIX + numbered_target + ALLOW_PREFIX + allowlist
            row = {
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user},
                ]
            }
            if set(row) != {"messages"} or [message["role"] for message in row["messages"]] != [
                "system",
                "user",
            ]:
                raise AssertionError(f"eval row contains non-input content: {arm}: {case_id}")
            visible = "\n".join(message["content"] for message in row["messages"])
            if arm in visible or case_id in visible or source_row["source_sha256"] in visible:
                raise AssertionError(f"hidden identity leaked into messages: {arm}: {case_id}")
            if "来源：Codex" in visible:
                raise AssertionError(f"Codex source footer leaked into messages: {arm}: {case_id}")
            rendered[arm].append(row)
            visible_lengths[arm].append(sum(len(message["content"]) for message in row["messages"]))

    for index in range(24):
        messages = [rendered[arm][index]["messages"] for arm in ARM_FILES]
        if len({row[0]["content"] for row in messages}) != 1:
            raise AssertionError(f"system drift at row {index}")
        suffixes = [row[1]["content"].split(TARGET_PREFIX, 1)[1] for row in messages]
        if len(set(suffixes)) != 1:
            raise AssertionError(f"numbered target or allowlist drift at row {index}")

    payloads = {
        OUT / "REAL24_SOURCE_INDEX.jsonl": "".join(compact_json(row) + "\n" for row in source_rows),
        OUT / "REAL24_TXX_MAP.jsonl": "".join(compact_json(row) + "\n" for row in txx_rows),
        GOLD: "".join(compact_json(row) + "\n" for row in gold_rows),
        DIAGNOSTIC: "".join(compact_json(row) + "\n" for row in diagnostic_rows),
    }
    for arm, path in ARM_FILES.items():
        payloads[path] = "".join(compact_json(row) + "\n" for row in rendered[arm])
    for path, body in payloads.items():
        path.write_text(body, encoding="utf-8")

    output_sha = {path.name: sha256_bytes(path.read_bytes()) for path in payloads}
    summary = {
        "case_count": 24,
        "book_count": 24,
        "fact_count": total_facts,
        "entity_diagnostic_count": len(diagnostic_rows),
        "visible_character_counts": {arm: stats(values) for arm, values in visible_lengths.items()},
        "output_sha256": output_sha,
    }
    write_summary(summary)
    return summary


def write_summary(summary: dict[str, Any]) -> None:
    lines = [
        "# LOCAL_REAL_SCREEN24｜READ 三臂构建说明",
        "",
        "这24题来自24本不同的真实小说，只作本机 Demo 筛选考试。当前权利状态仍是 **LOCAL_EVAL_ONLY_RIGHTS_PENDING**：不进入 TRAIN36，不上传，不发布。",
        "",
        f"- 题目：{summary['case_count']}题／{summary['book_count']}本",
        f"- 共同候选事实：{summary['fact_count']}条",
        f"- 独立姓名诊断：{summary['entity_diagnostic_count']}题（仅 C06、C18）",
        "- READ-1、READ-2、READ-4 每行都只有 system+user，没有 assistant 或 gold",
        "- 三臂逐题共用同一 system、编号目标和证据允许表，只改变前部只读范围",
        "- READ-2 每侧最多180个 Unicode 字符；READ-4 不额外重复 halo",
        "- 长度只按模型可见 Unicode 字符粗计，没有加载 tokenizer",
        "",
        "## 模型可见字符粗计",
        "",
        "| arm | min | median | max | mean |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm, values in summary["visible_character_counts"].items():
        lines.append(
            f"| {arm} | {values['min']} | {values['median']} | {values['max']} | {values['mean']} |"
        )
    lines.extend(["", "## 已登记题源异常", ""])
    for case_id, notes in SOURCE_ANOMALIES.items():
        for note in notes:
            lines.append(f"- {case_id}：{note}")
    lines.extend(["", "## 输出 SHA-256", ""])
    for name, digest in summary["output_sha256"].items():
        lines.append(f"- `{name}`：`{digest}`")
    lines.extend(
        [
            "",
            "这批结果只供本地 Demo 对比，不是最终盲考或生产泛化证明。",
            "",
            "来源：Codex",
            "",
        ]
    )
    (OUT / "BUILD_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    summary = build()
    print(f"cases={summary['case_count']}")
    print(f"facts={summary['fact_count']}")
    for arm, values in summary["visible_character_counts"].items():
        print(f"{arm} visible_chars={values}")
    for name, digest in summary["output_sha256"].items():
        print(f"{name} {digest}")


if __name__ == "__main__":
    main()

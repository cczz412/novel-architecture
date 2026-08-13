from __future__ import annotations

import hashlib
import json
import re
import statistics
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
GOLD_ROOT = ROOT / "finetuning/experiments/T5_R04_TRAIN36_GOLD_CANDIDATE_20260809_R01"
SOURCE_INDEX = GOLD_ROOT / "TRAIN36_SOURCE_INDEX.jsonl"
TXX_MAP = GOLD_ROOT / "TRAIN36_TXX_MAP.jsonl"
WAVE_FILES = [
    GOLD_ROOT / "GOLD_DRAFT_WAVE1_E01_E04.jsonl",
    GOLD_ROOT / "GOLD_DRAFT_WAVE2_T01_T05.jsonl",
    GOLD_ROOT / "GOLD_DRAFT_WAVE3_C01_C05.jsonl",
]
WAVE_SHA256 = [
    "1d6f80ff89420d118c46456be39ce8e46a3ea3d4d9920ba57f400fe4167ddb2f",
    "5e9267cd8567d17066b463f26b09aa7b910c2928dfb32f63cf3630c013d37bf6",
    "68b5e8ad011943b1c1e4f6c0f942885b84f879d2fd44b97b1afb45d0f7ead65b",
]
SCHEMA = (
    ROOT
    / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01"
    / "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)
SCHEMA_SHA256 = "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14"

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
ARM_FILES = {
    "READ-1-TARGET": OUT / "READ_1_TARGET_TRAIN36.jsonl",
    "READ-2-HALO180": OUT / "READ_2_HALO180_TRAIN36.jsonl",
    "READ-4-FULL-CHAPTER": OUT / "READ_4_FULL_CHAPTER_TRAIN36.jsonl",
}
SOURCE_FOOTER = re.compile(r"(?m)^来源：Codex[ \t]*(?:\r?\n)*\Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_jsonl_with_raw(path: Path) -> list[tuple[dict[str, Any], str]]:
    rows: list[tuple[dict[str, Any], str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append((json.loads(line), line))
    return rows


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def stats(values: list[int]) -> dict[str, int | float]:
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 3),
    }


def clean_model_visible_chapter(source_text: str, start: int, end: int, case_id: str) -> str:
    matches = list(SOURCE_FOOTER.finditer(source_text))
    if len(matches) != 1:
        raise AssertionError(f"expected one terminal Codex source line: {case_id}")
    footer = matches[0]
    if start < footer.end() and end > footer.start():
        raise AssertionError(f"source footer overlaps target: {case_id}")
    visible_text = source_text[: footer.start()].rstrip()
    if end > len(visible_text) or visible_text[start:end] != source_text[start:end]:
        raise AssertionError(f"footer cleaning changed target coordinates: {case_id}")
    return visible_text


def build() -> dict[str, Any]:
    for path, expected_sha in zip(WAVE_FILES, WAVE_SHA256, strict=True):
        actual_sha = sha256_bytes(path.read_bytes())
        if actual_sha != expected_sha:
            raise AssertionError(f"gold SHA drift: {path.name}: {actual_sha}")
    if sha256_bytes(SCHEMA.read_bytes()) != SCHEMA_SHA256:
        raise AssertionError("P4.1 structural schema SHA drift")

    source_pairs = read_jsonl_with_raw(SOURCE_INDEX)
    txx_pairs = read_jsonl_with_raw(TXX_MAP)
    if len(source_pairs) != 36 or len(txx_pairs) != 36:
        raise AssertionError("TRAIN36 source/Txx denominator drift")
    source_rows = [row for row, _ in source_pairs]
    case_order = [row["case_id"] for row in source_rows]
    if len(set(case_order)) != 36:
        raise AssertionError("TRAIN36 source case IDs are not unique")
    if [row["case_id"] for row, _ in txx_pairs] != case_order:
        raise AssertionError("TRAIN36 source/Txx case order drift")
    if any(not row.get("project_original") or row.get("confirm24_included") for row in source_rows):
        raise AssertionError("non-original or CONFIRM24 material entered TRAIN36")
    txx_by_case = {row["case_id"]: row for row, _ in txx_pairs}

    gold_raw_by_case: dict[str, str] = {}
    gold_by_case: dict[str, dict[str, Any]] = {}
    for wave_path in WAVE_FILES:
        for row, raw in read_jsonl_with_raw(wave_path):
            case_id = row["case_id"]
            if case_id in gold_by_case:
                raise AssertionError(f"duplicate case across gold waves: {case_id}")
            gold_by_case[case_id] = row
            gold_raw_by_case[case_id] = raw
    if set(gold_by_case) != set(case_order):
        raise AssertionError("three gold waves do not exactly cover TRAIN36")
    total_facts = sum(len(gold_by_case[case_id]["facts"]) for case_id in case_order)

    merged_gold = "".join(gold_raw_by_case[case_id] + "\n" for case_id in case_order)
    (OUT / "TRAIN36_GOLD_36.jsonl").write_text(merged_gold, encoding="utf-8")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    rendered: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARM_FILES}
    visible_lengths: dict[str, list[int]] = {arm: [] for arm in ARM_FILES}
    read_lengths: dict[str, list[int]] = {arm: [] for arm in ARM_FILES}
    halo_sides: list[dict[str, int | str]] = []
    target_equals_full: list[str] = []

    for source_row in source_rows:
        case_id = source_row["case_id"]
        source_bytes = (ROOT / source_row["source_file"]).read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        if source_text.encode("utf-8") != source_bytes:
            raise AssertionError(f"source is not strict UTF-8 round-trippable: {case_id}")
        if sha256_bytes(source_bytes) != source_row["source_sha256"]:
            raise AssertionError(f"source SHA drift: {case_id}")
        start = source_row["target_start"]
        end = source_row["target_end"]
        target = source_text[start:end]
        if sha256_bytes(target.encode("utf-8")) != source_row["target_sha256"]:
            raise AssertionError(f"target SHA drift: {case_id}")
        visible_source_text = clean_model_visible_chapter(source_text, start, end, case_id)

        units = txx_by_case[case_id]["target_units"]
        if "".join(unit["text"] for unit in units) != target:
            raise AssertionError(f"Txx reconstruction drift: {case_id}")
        ids = [unit["id"] for unit in units]
        if len(ids) != len(set(ids)):
            raise AssertionError(f"duplicate local Txx ID: {case_id}")
        numbered_target = "".join(f"[{unit['id']}]{unit['text']}" for unit in units)
        allowlist = "、".join(ids)

        left_start = max(0, start - 180)
        right_end = min(len(visible_source_text), end + 180)
        halo = visible_source_text[left_start:right_end]
        left_chars = start - left_start
        right_chars = right_end - end
        halo_sides.append({"case_id": case_id, "left_chars": left_chars, "right_chars": right_chars})
        read_texts = {
            "READ-1-TARGET": target,
            "READ-2-HALO180": halo,
            "READ-4-FULL-CHAPTER": visible_source_text,
        }
        if target == visible_source_text:
            target_equals_full.append(case_id)
        if not (len(target) < len(halo) < len(visible_source_text)):
            raise AssertionError(f"READ range is not strictly nested: {case_id}")
        if target not in halo or halo not in visible_source_text:
            raise AssertionError(f"READ range is not a literal nested slice: {case_id}")
        if left_chars > 180 or right_chars > 180:
            raise AssertionError(f"HALO180 overflow: {case_id}")

        assistant_obj = {
            "facts": [
                {
                    "fact": fact["fact_sentence"],
                    "status": fact["status"],
                    "speaker": fact["speaker"],
                    "evidence_ids": fact["evidence_ids"],
                }
                for fact in gold_by_case[case_id]["facts"]
            ]
        }
        validator.validate(assistant_obj)
        assistant = compact_json(assistant_obj)

        for arm, read_text in read_texts.items():
            if read_text.count(target) != 1:
                raise AssertionError(f"target must occur once in READ_TEXT: {arm}: {case_id}")
            user = USER_PREFIX + read_text + TARGET_PREFIX + numbered_target + ALLOW_PREFIX + allowlist
            row = {
                "metadata": {
                    "family": "READ",
                    "arm": arm,
                    "case_id": case_id,
                    "local_demo_only": True,
                },
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": assistant},
                ],
            }
            visible = "\n".join(message["content"] for message in row["messages"])
            if arm in visible or case_id in visible or source_row["source_sha256"] in visible:
                raise AssertionError(f"hidden metadata leaked into messages: {arm}: {case_id}")
            if "来源：Codex" in visible:
                raise AssertionError(f"source footer leaked into messages: {arm}: {case_id}")
            rendered[arm].append(row)
            visible_lengths[arm].append(sum(len(message["content"]) for message in row["messages"]))
            read_lengths[arm].append(len(read_text))

    for row_index in range(36):
        rows = [rendered[arm][row_index] for arm in ARM_FILES]
        messages = [row["messages"] for row in rows]
        if len({message[0]["content"] for message in messages}) != 1:
            raise AssertionError(f"system drift at row {row_index}")
        if len({message[2]["content"] for message in messages}) != 1:
            raise AssertionError(f"assistant drift at row {row_index}")
        suffixes = [message[1]["content"].split(TARGET_PREFIX, 1)[1] for message in messages]
        if len(set(suffixes)) != 1:
            raise AssertionError(f"numbered target or allowlist drift at row {row_index}")

    for arm, path in ARM_FILES.items():
        body = "".join(compact_json(row) + "\n" for row in rendered[arm])
        path.write_text(body, encoding="utf-8")

    jsonl_paths = [OUT / "TRAIN36_GOLD_36.jsonl", *ARM_FILES.values()]
    output_sha = {path.name: sha256_bytes(path.read_bytes()) for path in jsonl_paths}
    summary = {
        "case_count": 36,
        "fact_count": total_facts,
        "target_equals_full_cases": target_equals_full,
        "visible_character_counts": {arm: stats(values) for arm, values in visible_lengths.items()},
        "read_text_character_counts": {arm: stats(values) for arm, values in read_lengths.items()},
        "halo_left_character_counts": stats([int(row["left_chars"]) for row in halo_sides]),
        "halo_right_character_counts": stats([int(row["right_chars"]) for row in halo_sides]),
        "output_sha256": output_sha,
    }
    write_summary(summary)
    return summary


def write_summary(summary: dict[str, Any]) -> None:
    lines = [
        "# READ 家族 TRAIN36 构建说明",
        "",
        "这批文件只供本地 Demo 训练。训练材料只有14个项目原创故事的 TRAIN36；真实 LOCAL_REAL_SCREEN24 没有进入任何训练文件。",
        "",
        f"- 题目：{summary['case_count']}题",
        f"- 候选事实：{summary['fact_count']}条",
        "- READ-1：前部只读目标段",
        "- READ-2：前部只读目标左右各最多180个 Unicode 字符",
        "- READ-4：前部只读完整原章，不额外追加 halo",
        "- 模型可见正文已剥离独立的文末署名“来源：Codex”及相邻尾空白；raw source SHA和目标坐标不变",
        "- 三臂的 system、尾部编号目标、证据允许表和 assistant 逐题一致",
        "- 每题目标在前部只读范围出现一次，并在尾部编号负责区再出现一次",
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
    lines.extend(["", "## 四个 JSONL SHA-256", ""])
    for name, digest in summary["output_sha256"].items():
        lines.append(f"- `{name}`：`{digest}`")
    lines.extend(
        [
            "",
            "这只是候选训练渲染，不代表正式生产训练集，也不授权本轮启动训练。",
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

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import statistics
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OLD = ROOT / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN36_RENDER_20260809_R01"
OLD_ARMS = {
    "READ-1-TARGET": OLD / "READ_1_TARGET_TRAIN36.jsonl",
    "READ-2-HALO180": OLD / "READ_2_HALO180_TRAIN36.jsonl",
    "READ-4-FULL-CHAPTER": OLD / "READ_4_FULL_CHAPTER_TRAIN36.jsonl",
}
OLD_SHA = {
    "READ-1-TARGET": "84ad6f7886b372334b008d49cc2f3343afdd6b98d83a24a00d604ae49b8f09e0",
    "READ-2-HALO180": "09fdbc52f7131f1a2a60552740ce28430e418ed84c858f0f997abda16e4a7c5e",
    "READ-4-FULL-CHAPTER": "93b3ab7e9beed9a6f54df751400ba2ac65cfd5a18f1865da01c7c0c81540ed4a",
}
OUTPUT_ARMS = {
    "READ-1-TARGET": OUT / "READ_1_TARGET_TRAIN48.jsonl",
    "READ-2-HALO180": OUT / "READ_2_HALO180_TRAIN48.jsonl",
    "READ-4-FULL-CHAPTER": OUT / "READ_4_FULL_CHAPTER_TRAIN48.jsonl",
}
S_INDEX = OUT / "S6_SOURCE_INDEX.jsonl"
M_INDEX = OUT / "M6_SOURCE_INDEX.jsonl"
GOLD = OUT / "LENGTH_CALIBRATION_GOLD_12.jsonl"
L_INDEX = OUT / "L6_SOURCE_INDEX.jsonl"
L_GOLD = OUT / "L6_GOLD_6.jsonl"
L_EVAL = OUT / "READ_1_TARGET_L6_EVAL.jsonl"
SCHEMA = (
    ROOT
    / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01"
    / "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)
OLD_SOURCE_INDEX = (
    ROOT / "finetuning/experiments/T5_R04_TRAIN36_GOLD_CANDIDATE_20260809_R01/TRAIN36_SOURCE_INDEX.jsonl"
)
REAL_SOURCE_INDEX = (
    ROOT / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01/REAL24_SOURCE_INDEX.jsonl"
)
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
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
SOURCE_FOOTER = re.compile(r"(?m)^来源：Codex[ \t]*(?:\r?\n)*\Z")
STATUS = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}
EXPECTED_S = [0, 0, 1, 2, 2, 3]
EXPECTED_M = [4, 5, 6, 7, 8, 10]
EXPECTED_L = [0, 0, 2, 3, 5, 8]
REVIEW_NOTE = "独立审收后，控制窗定点补正2条S6事实和3条事实表述；冻结正文未修改。"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def raw_jsonl_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def clean_body(text: str, case_id: str, start: int, end: int) -> str:
    matches = list(SOURCE_FOOTER.finditer(text))
    if len(matches) != 1:
        raise AssertionError(f"terminal source line mismatch: {case_id}")
    footer = matches[0]
    if start < footer.end() and end > footer.start():
        raise AssertionError(f"source footer overlaps target: {case_id}")
    body = text[: footer.start()].rstrip()
    if end > len(body) or body[start:end] != text[start:end]:
        raise AssertionError(f"footer cleaning changed target coordinate: {case_id}")
    return body


def cjk_count(text: str) -> int:
    return sum("\u3400" <= char <= "\u9fff" for char in text)


def normalized_text(text: str) -> str:
    return "".join(char for char in text if char.isalnum())


def shingles(text: str, size: int = 28) -> set[str]:
    value = normalized_text(text)
    return {value[index : index + size] for index in range(max(0, len(value) - size + 1))}


def stats(values: list[int]) -> dict[str, int | float]:
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 3),
    }


def validate_sources() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str], dict[str, str]]:
    s_rows = read_jsonl(S_INDEX)
    m_rows = read_jsonl(M_INDEX)
    l_rows = read_jsonl(L_INDEX)
    if len(s_rows) != 6 or len(m_rows) != 6 or len(l_rows) != 6:
        raise AssertionError("S6/M6/L6 denominator mismatch")
    if [row["expected_fact_count"] for row in s_rows] != EXPECTED_S:
        raise AssertionError("S6 fact-count order mismatch")
    if [row["expected_fact_count"] for row in m_rows] != EXPECTED_M:
        raise AssertionError("M6 fact-count order mismatch")
    if [row["expected_fact_count"] for row in l_rows] != EXPECTED_L:
        raise AssertionError("L6 fact-count order mismatch")
    train_rows = s_rows + m_rows
    rows = train_rows + l_rows
    if len({row["case_id"] for row in rows}) != 18:
        raise AssertionError("new case IDs are not unique")
    if {row["story_id"] for row in s_rows} != {f"N{i:02d}" for i in range(1, 7)}:
        raise AssertionError("S6 story coverage mismatch")
    if {row["story_id"] for row in m_rows} != {f"N{i:02d}" for i in range(1, 7)}:
        raise AssertionError("M6 story coverage mismatch")
    if {row["story_id"] for row in l_rows} != {"N07", "N08", "N09"}:
        raise AssertionError("L6 story coverage mismatch")
    if any(not row.get("forbidden_from_training") for row in l_rows):
        raise AssertionError("L6 must be forbidden from training")
    targets: dict[str, str] = {}
    bodies: dict[str, str] = {}
    intervals: dict[str, list[tuple[int, int]]] = {}
    for row in rows:
        path = ROOT / row["source_file"]
        source_bytes = path.read_bytes()
        source = source_bytes.decode("utf-8", errors="strict")
        if source.encode("utf-8") != source_bytes or sha256_bytes(source_bytes) != row["source_sha256"]:
            raise AssertionError(f"source UTF-8/SHA mismatch: {row['case_id']}")
        start, end = row["target_start"], row["target_end"]
        target = source[start:end]
        if not (0 <= start < end <= len(source)) or sha256_bytes(target.encode()) != row["target_sha256"]:
            raise AssertionError(f"target coordinate/SHA mismatch: {row['case_id']}")
        if row["target_chars"] != len(target) or not 550 <= cjk_count(target) <= 850:
            raise AssertionError(f"target length mismatch: {row['case_id']}:{cjk_count(target)}")
        body = clean_body(source, row["case_id"], start, end)
        # “约 2200–3300 汉字”是写作护栏；留出轻微自然浮动，不为凑字破坏冻结正文。
        if not 2100 <= cjk_count(body) <= 3400:
            raise AssertionError(f"chapter length mismatch: {row['story_id']}:{cjk_count(body)}")
        units = row["target_units"]
        if not units or len(units) > 99 or "".join(unit["text"] for unit in units) != target:
            raise AssertionError(f"Txx reconstruction mismatch: {row['case_id']}")
        if [unit["id"] for unit in units] != [f"T{i:02d}" for i in range(1, len(units) + 1)]:
            raise AssertionError(f"Txx IDs mismatch: {row['case_id']}")
        for unit in units:
            if unit["text"] != target[unit["start"] : unit["end"]]:
                raise AssertionError(f"Txx coordinate mismatch: {row['case_id']}:{unit['id']}")
            if sha256_bytes(unit["text"].encode()) != unit["text_sha256"]:
                raise AssertionError(f"Txx SHA mismatch: {row['case_id']}:{unit['id']}")
        targets[row["case_id"]] = target
        bodies[row["story_id"]] = body
        intervals.setdefault(row["story_id"], []).append((start, end))
    for story_id, ranges in intervals.items():
        first, second = sorted(ranges)
        if first[1] > second[0]:
            raise AssertionError(f"targets overlap: {story_id}")
        source = bodies[story_id]
        gap = source[first[1] : second[0]]
        if "\n\n" not in gap or not gap.strip():
            raise AssertionError(f"targets lack a complete natural paragraph gap: {story_id}")
    return train_rows, l_rows, targets, bodies


def validate_gold(
    rows: list[dict[str, Any]], path: Path, expected_total: int, *, forbidden_from_training: bool
) -> dict[str, dict[str, Any]]:
    gold_rows = read_jsonl(path)
    order = [row["case_id"] for row in rows]
    if [row["case_id"] for row in gold_rows] != order:
        raise AssertionError("gold order does not match S6 then M6")
    source_by_case = {row["case_id"]: row for row in rows}
    all_fact_texts: list[str] = []
    for row in gold_rows:
        source = source_by_case[row["case_id"]]
        facts = row["facts"]
        if row.get("dataset_status") != "CANDIDATE_NOT_YET_APPROVED":
            raise AssertionError(f"gold status mismatch: {row['case_id']}")
        if bool(row.get("forbidden_from_training", False)) != forbidden_from_training:
            raise AssertionError(f"gold training boundary mismatch: {row['case_id']}")
        if len(facts) != source["expected_fact_count"] or row.get("expected_fact_count") != len(facts):
            raise AssertionError(f"gold fact count mismatch: {row['case_id']}")
        unit_ids = [unit["id"] for unit in source["target_units"]]
        unit_pos = {unit_id: index for index, unit_id in enumerate(unit_ids)}
        fact_ids = []
        for fact in facts:
            fact_ids.append(fact["fact_id"])
            text = fact["fact_sentence"]
            evidence = fact["evidence_ids"]
            if not text or fact["status"] not in STATUS or not isinstance(fact["speaker"], (str, type(None))):
                raise AssertionError(f"gold field mismatch: {row['case_id']}")
            if not evidence or any(item not in unit_pos for item in evidence):
                raise AssertionError(f"gold evidence missing/foreign: {row['case_id']}:{fact['fact_id']}")
            positions = [unit_pos[item] for item in evidence]
            if positions != list(range(positions[0], positions[-1] + 1)):
                raise AssertionError(f"gold evidence not continuous: {row['case_id']}:{fact['fact_id']}")
            all_fact_texts.append(text)
        if len(fact_ids) != len(set(fact_ids)):
            raise AssertionError(f"duplicate fact ID: {row['case_id']}")
    if len(all_fact_texts) != expected_total or len(all_fact_texts) != len(set(all_fact_texts)):
        raise AssertionError(f"facts are not exactly {expected_total} unique sentences")
    return {row["case_id"]: row for row in gold_rows}


def validate_no_reuse(targets: dict[str, str], bodies: dict[str, str]) -> None:
    old_rows = read_jsonl(OLD_SOURCE_INDEX) + read_jsonl(REAL_SOURCE_INDEX)
    old_texts = []
    for row in old_rows:
        source_path = Path(row.get("source_file") or row["source_path"])
        if not source_path.is_absolute():
            source_path = ROOT / source_path
        source = source_path.read_text(encoding="utf-8")
        old_texts.append(source[row["target_start"] : row["target_end"]])
    old_shingles = set().union(*(shingles(text) for text in old_texts))
    for case_id, target in targets.items():
        if shingles(target) & old_shingles:
            raise AssertionError(f"28-char target reuse detected: {case_id}")
    story_items = sorted(bodies.items())
    for index, (story_id, body) in enumerate(story_items):
        body_shingles = shingles(body)
        if body_shingles & old_shingles:
            raise AssertionError(f"28-char chapter reuse detected: {story_id}")
        for other_id, other in story_items[index + 1 :]:
            if body_shingles & shingles(other):
                raise AssertionError(f"28-char reuse between new stories: {story_id}:{other_id}")


def render(rows: list[dict[str, Any]], targets: dict[str, str], bodies: dict[str, str], gold: dict[str, dict[str, Any]]) -> dict[str, Any]:
    schema = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    new_lines: dict[str, list[str]] = {arm: [] for arm in OUTPUT_ARMS}
    visible_lengths: dict[str, list[int]] = {arm: [] for arm in OUTPUT_ARMS}
    for source in rows:
        case_id = source["case_id"]
        target = targets[case_id]
        body = bodies[source["story_id"]]
        start, end = source["target_start"], source["target_end"]
        left = max(0, start - 180)
        right = min(len(body), end + 180)
        read_texts = {
            "READ-1-TARGET": target,
            "READ-2-HALO180": body[left:right],
            "READ-4-FULL-CHAPTER": body,
        }
        if not (len(target) < len(read_texts["READ-2-HALO180"]) < len(body)):
            raise AssertionError(f"READ ranges not strictly nested: {case_id}")
        if start - left > 180 or right - end > 180:
            raise AssertionError(f"halo exceeds 180 chars: {case_id}")
        units = source["target_units"]
        numbered = "".join(f"[{unit['id']}]{unit['text']}" for unit in units)
        allowlist = "、".join(unit["id"] for unit in units)
        assistant_obj = {
            "facts": [
                {
                    "fact": fact["fact_sentence"],
                    "status": fact["status"],
                    "speaker": fact["speaker"],
                    "evidence_ids": fact["evidence_ids"],
                }
                for fact in gold[case_id]["facts"]
            ]
        }
        schema.validate(assistant_obj)
        assistant = compact(assistant_obj)
        for arm, read_text in read_texts.items():
            if read_text.count(target) != 1:
                raise AssertionError(f"target does not occur once in front: {arm}:{case_id}")
            user = USER_PREFIX + read_text + TARGET_PREFIX + numbered + ALLOW_PREFIX + allowlist
            record = {
                "metadata": {
                    "family": "READ",
                    "arm": arm,
                    "case_id": case_id,
                    "length_calibration_block": source["density_block"],
                    "local_demo_only": True,
                },
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": assistant},
                ],
            }
            visible = "\n".join(message["content"] for message in record["messages"])
            if case_id in visible or arm in visible or "来源：Codex" in visible:
                raise AssertionError(f"hidden metadata/footer leaked: {arm}:{case_id}")
            new_lines[arm].append(compact(record))
            visible_lengths[arm].append(len(visible))
    output_sha = {}
    for arm, output in OUTPUT_ARMS.items():
        if sha256_bytes(OLD_ARMS[arm].read_bytes()) != OLD_SHA[arm]:
            raise AssertionError(f"frozen TRAIN36 SHA drift: {arm}")
        old_lines = raw_jsonl_lines(OLD_ARMS[arm])
        if len(old_lines) != 36 or len(new_lines[arm]) != 12:
            raise AssertionError(f"TRAIN48 denominator mismatch: {arm}")
        body = "\n".join(old_lines + new_lines[arm]) + "\n"
        output.write_text(body, encoding="utf-8")
        if raw_jsonl_lines(output)[:36] != old_lines:
            raise AssertionError(f"frozen TRAIN36 prefix changed: {arm}")
        output_sha[output.name] = sha256_bytes(output.read_bytes())
    return {"output_sha256": output_sha, "new_visible_chars": {arm: stats(values) for arm, values in visible_lengths.items()}}


def render_l6(
    rows: list[dict[str, Any]], targets: dict[str, str], gold: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    lines = []
    visible_lengths = []
    for source in rows:
        case_id = source["case_id"]
        target = targets[case_id]
        units = source["target_units"]
        numbered = "".join(f"[{unit['id']}]{unit['text']}" for unit in units)
        allowlist = "、".join(unit["id"] for unit in units)
        user = USER_PREFIX + target + TARGET_PREFIX + numbered + ALLOW_PREFIX + allowlist
        record = {
            "metadata": {
                "family": "READ",
                "arm": "READ-1-TARGET",
                "case_id": case_id,
                "length_calibration_block": "L6_READ1_UNSEEN_DENSITY_EVAL_ONLY",
                "forbidden_from_training": True,
                "local_demo_only": True,
                "gold_fact_count": len(gold[case_id]["facts"]),
            },
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
        }
        visible = "\n".join(message["content"] for message in record["messages"])
        if case_id in visible or "READ-1-TARGET" in visible or "来源：Codex" in visible:
            raise AssertionError(f"L6 metadata/footer leaked: {case_id}")
        lines.append(compact(record))
        visible_lengths.append(len(visible))
    L_EVAL.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if len(read_jsonl(L_EVAL)) != 6 or any(len(row["messages"]) != 2 for row in read_jsonl(L_EVAL)):
        raise AssertionError("L6 eval request shape mismatch")
    return {"sha256": sha256_bytes(L_EVAL.read_bytes()), "visible_chars": stats(visible_lengths)}


def token_lengths() -> dict[str, Any]:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True, trust_remote_code=True)
    result: dict[str, Any] = {}
    for arm, path in OUTPUT_ARMS.items():
        counts = []
        for row in read_jsonl(path):
            rendered = tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
            counts.append(len(tokenizer.encode(rendered, add_special_tokens=False)))
        if len(counts) != 48 or max(counts) >= 4608:
            raise AssertionError(f"training sequence reaches 4608: {arm}:{max(counts)}")
        result[arm] = stats(counts)
    old_prompt_counts = []
    for row in read_jsonl(OLD_ARMS["READ-1-TARGET"]):
        rendered = tokenizer.apply_chat_template(row["messages"][:2], tokenize=False, add_generation_prompt=True)
        old_prompt_counts.append(len(tokenizer.encode(rendered, add_special_tokens=False)))
    l_counts = []
    for row in read_jsonl(L_EVAL):
        rendered = tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=True)
        l_counts.append(len(tokenizer.encode(rendered, add_special_tokens=False)))
    if min(l_counts) < 0.85 * min(old_prompt_counts):
        raise AssertionError(f"L6 prompt is visibly shorter than TRAIN36: {min(l_counts)}:{min(old_prompt_counts)}")
    result["L6_READ1_PROMPT_ONLY"] = stats(l_counts)
    result["TRAIN36_READ1_PROMPT_ONLY_REFERENCE"] = stats(old_prompt_counts)
    return result


def write_summary(
    train_rows: list[dict[str, Any]],
    l_rows: list[dict[str, Any]],
    targets: dict[str, str],
    render_summary: dict[str, Any],
    l_summary: dict[str, Any],
    tokens: dict[str, Any],
) -> None:
    chapter_counts = {row["story_id"] for row in train_rows + l_rows}
    lines = [
        "# TRAIN48 长度校准教材构建说明",
        "",
        "这批只是本地 Demo 长度校准材料。S6/M6来自6篇项目原创章；L6来自另3篇原创章，只作READ1未见密度小考且永不进训练。真实 LOCAL_REAL_SCREEN24 没有进入训练文件。",
        "",
        f"- 完整原创章：{len(chapter_counts)}篇",
        "- 新增题：12题（S6+M6）",
        "- 新增事实：48条；合并后 TRAIN48 共762条事实",
        "- L6 READ1未见密度小考：6题、18条Gold，事实数0、0、2、3、5、8；只生成READ1无答案请求",
        "- L6只判断低事实密度时是否少输出，禁止据此下READ1/READ2/READ4上下文长度结论",
        "- S6事实数：0、0、1、2、2、3",
        "- M6事实数：4、5、6、7、8、10",
        "- 18个新目标段汉字粗计范围："
        + f"{min(cjk_count(text) for text in targets.values())}–{max(cjk_count(text) for text in targets.values())}",
        "- 每篇两段不重叠，中间至少隔一个完整自然段",
        "- 新旧材料及9个新故事之间的28字连续文本复用命中：0",
        "- 原TRAIN36三份文件SHA未变；TRAIN48前36行逐字复用旧文件",
        f"- 审收问题与修复：{REVIEW_NOTE}",
        "",
        "## 完整序列 token 范围",
        "",
        "只为确认不超过4608训练上限而读取本地冻结 tokenizer；没有加载模型或做推理。",
        "",
        "| arm | min | median | max | mean |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm, values in tokens.items():
        lines.append(f"| {arm} | {values['min']} | {values['median']} | {values['max']} | {values['mean']} |")
    lines.extend(["", "## 三份 TRAIN48 SHA-256", ""])
    for name, digest in render_summary["output_sha256"].items():
        lines.append(f"- `{name}`：`{digest}`")
    lines.extend(["", "## L6 READ1 未见密度小考 SHA-256", "", f"- `{L_EVAL.name}`：`{l_summary['sha256']}`"])
    lines.extend(
        [
            "",
            "本轮没有训练、推理或API调用，也没有修改TRAIN36、REAL24、Notion、Git或现役指针。",
            "",
            "来源：Codex",
            "",
        ]
    )
    (OUT / "BUILD_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    train_rows, l_rows, targets, bodies = validate_sources()
    gold = validate_gold(train_rows, GOLD, 48, forbidden_from_training=False)
    l_gold = validate_gold(l_rows, L_GOLD, 18, forbidden_from_training=True)
    validate_no_reuse(targets, bodies)
    rendered = render(train_rows, targets, bodies, gold)
    l_summary = render_l6(l_rows, targets, l_gold)
    tokens = token_lengths()
    write_summary(train_rows, l_rows, targets, rendered, l_summary, tokens)
    print("chapters=9 train_cases=12 train_new_facts=48 train48_rows=48 l6_cases=6 l6_facts=18")
    for name, digest in rendered["output_sha256"].items():
        print(name, digest)
    for arm, values in tokens.items():
        print(arm, values)
    print(L_EVAL.name, l_summary["sha256"])


if __name__ == "__main__":
    main()

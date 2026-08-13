from __future__ import annotations

import copy
import hashlib
import json
import re
import statistics
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
TRAIN48 = ROOT / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01"
COMPACT24 = (
    ROOT
    / "finetuning/experiments/T5_R04_TRAIN72_COMPACT_TARGET24_MODEL_NEUTRAL_GOLD_20260809_R02"
)
SCHEMA = (
    ROOT
    / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01"
    / "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)

ARM_INPUTS = {
    "READ-1-TARGET": TRAIN48 / "READ_1_TARGET_TRAIN48.jsonl",
    "READ-2-HALO180": TRAIN48 / "READ_2_HALO180_TRAIN48.jsonl",
    "READ-4-FULL-CHAPTER": TRAIN48 / "READ_4_FULL_CHAPTER_TRAIN48.jsonl",
}
ARM_INPUT_SHA256 = {
    "READ-1-TARGET": "87d241eee1d37569682b82d858b8fb7848c2e45b91092c7fc2bc99dec9297a98",
    "READ-2-HALO180": "7862d4528415f50e1c60836104ecf3c38d2ecb8b81c145468e1beb4321dc8d03",
    "READ-4-FULL-CHAPTER": "2e03521faf8d0c0828bae564433b7cbc117ece0da7983f7b4880ce262c9b601e",
}
ARM_OUTPUTS = {
    "READ-1-TARGET": OUT / "READ_1_TARGET_TRAIN72.jsonl",
    "READ-2-HALO180": OUT / "READ_2_HALO180_TRAIN72.jsonl",
    "READ-4-FULL-CHAPTER": OUT / "READ_4_FULL_CHAPTER_TRAIN72.jsonl",
}

COMPACT_SOURCE = COMPACT24 / "SOURCE_INDEX_24.jsonl"
COMPACT_GOLD = COMPACT24 / "MODEL_NEUTRAL_GOLD_24.jsonl"
COMPACT_SOURCE_SHA256 = "689da403b6b6d0df13471f927f162c79d622dd335dd12802372d6925a390f1e4"
COMPACT_GOLD_SHA256 = "82140a093a059256b4db0a05ba47e241aa975168d6790e9905b1f231999f34ed"
SCHEMA_SHA256 = "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14"

SYSTEM = (
    "你是中文小说事实抽取器。B/T 编号只表示原文位置。"
    "只抽取【编号负责区】明确表达、会影响后续情节的事实。"
    "只允许使用【允许证据 ID】中的最小连续 T 编号作为 evidence_ids。"
    "输出必须是一个 JSON 对象，顶层只能有 facts。facts 必须是数组；"
    "每项必须且只能包含 fact、status、speaker、evidence_ids。"
    "status 只能是：已发生、正在发生、计划、承诺、条件、推测、误信、否定。"
    "speaker 必须是字符串或 null；evidence_ids 必须是字符串数组。"
    '没有事实时输出 {"facts":[]}。除 JSON 外不要输出任何文字。'
)
USER_PREFIX = "【只读范围：只帮助理解，不得作为新增事实或证据】\n"
TARGET_PREFIX = "\n\n【编号负责区：只抽这里】\n"
ALLOW_PREFIX = "\n\n【允许证据 ID】\n"
SOURCE_FOOTER = re.compile(r"(?m)^来源：Codex[ \t]*(?:\r?\n)*\Z")

EXISTING12_ORDER = [
    "LC-S01",
    "LC-M06",
    "LC-S02",
    "LC-M05",
    "LC-S03",
    "LC-M04",
    "LC-S04",
    "LC-M03",
    "LC-S05",
    "LC-M02",
    "LC-S06",
    "LC-M01",
]
COMPACT24_ORDER = [
    "CT72-L01",
    "CT72-M12",
    "CT72-L02",
    "CT72-M11",
    "CT72-L03",
    "CT72-M10",
    "CT72-L04",
    "CT72-M09",
    "CT72-L05",
    "CT72-M08",
    "CT72-L06",
    "CT72-M07",
    "CT72-L07",
    "CT72-M06",
    "CT72-L08",
    "CT72-M05",
    "CT72-L09",
    "CT72-M04",
    "CT72-L10",
    "CT72-M03",
    "CT72-L11",
    "CT72-M02",
    "CT72-L12",
    "CT72-M01",
]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return ("".join(compact(row) + "\n" for row in rows)).encode("utf-8")


def stats(values: list[int]) -> dict[str, int | float]:
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 3),
    }


def split_user(user: str, *, case_id: str) -> tuple[str, str]:
    if not user.startswith(USER_PREFIX) or user.count(TARGET_PREFIX) != 1:
        raise AssertionError(f"user template drift: {case_id}")
    before, tail = user.split(TARGET_PREFIX, 1)
    return before[len(USER_PREFIX) :], tail


def clean_model_visible_chapter(source: str, start: int, end: int, case_id: str) -> str:
    matches = list(SOURCE_FOOTER.finditer(source))
    if len(matches) != 1:
        raise AssertionError(f"terminal source line mismatch: {case_id}")
    footer = matches[0]
    if start < footer.end() and end > footer.start():
        raise AssertionError(f"source footer overlaps target: {case_id}")
    # 只清掉目标段之后、署名之前的尾空白；若目标本身含收尾换行，必须原样保留。
    before_footer = source[: footer.start()]
    body = before_footer[:end] + before_footer[end:].rstrip()
    if end > len(body) or body[start:end] != source[start:end]:
        raise AssertionError(f"footer cleaning changed target coordinates: {case_id}")
    return body


def validate_input_sha() -> None:
    for arm, path in ARM_INPUTS.items():
        actual = sha256_bytes(path.read_bytes())
        if actual != ARM_INPUT_SHA256[arm]:
            raise AssertionError(f"TRAIN48 SHA drift: {arm}: {actual}")
    if sha256_bytes(COMPACT_SOURCE.read_bytes()) != COMPACT_SOURCE_SHA256:
        raise AssertionError("compact source index SHA drift")
    if sha256_bytes(COMPACT_GOLD.read_bytes()) != COMPACT_GOLD_SHA256:
        raise AssertionError("compact gold SHA drift")
    if sha256_bytes(SCHEMA.read_bytes()) != SCHEMA_SHA256:
        raise AssertionError("structural schema SHA drift")


def load_frozen_train48(
    validator: Draft202012Validator,
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[str]]:
    by_arm: dict[str, dict[str, dict[str, Any]]] = {}
    first36_order: list[str] | None = None
    case_sets: list[set[str]] = []
    for arm, path in ARM_INPUTS.items():
        rows = read_jsonl(path)
        if len(rows) != 48:
            raise AssertionError(f"TRAIN48 denominator drift: {arm}")
        cases = [row["metadata"]["case_id"] for row in rows]
        if len(set(cases)) != 48:
            raise AssertionError(f"TRAIN48 duplicate case: {arm}")
        if first36_order is None:
            first36_order = cases[:36]
        elif cases[:36] != first36_order:
            raise AssertionError(f"TRAIN36 order differs across arms: {arm}")
        if set(cases[36:]) != set(EXISTING12_ORDER):
            raise AssertionError(f"S6/M6 denominator differs from fixed order: {arm}")
        by_arm[arm] = {row["metadata"]["case_id"]: row for row in rows}
        case_sets.append(set(cases))
        for row in rows:
            messages = row.get("messages")
            if not isinstance(messages, list) or [item.get("role") for item in messages] != [
                "system",
                "user",
                "assistant",
            ]:
                raise AssertionError(f"TRAIN48 message shape drift: {arm}:{row['metadata']['case_id']}")
            assistant = json.loads(messages[2]["content"])
            validator.validate(assistant)
    if len({frozenset(value) for value in case_sets}) != 1:
        raise AssertionError("TRAIN48 arm case sets differ")
    assert first36_order is not None
    full_order = first36_order + EXISTING12_ORDER

    for case_id in full_order:
        records = [by_arm[arm][case_id] for arm in ARM_INPUTS]
        assistants = {record["messages"][2]["content"] for record in records}
        if len(assistants) != 1:
            raise AssertionError(f"TRAIN48 assistant differs across arms: {case_id}")
        tails = {split_user(record["messages"][1]["content"], case_id=case_id)[1] for record in records}
        if len(tails) != 1:
            raise AssertionError(f"TRAIN48 numbered target/allowlist drift: {case_id}")
        metadata = []
        for record in records:
            value = dict(record["metadata"])
            value.pop("arm", None)
            metadata.append(value)
        if len({compact(value) for value in metadata}) != 1:
            raise AssertionError(f"TRAIN48 metadata differs beyond arm: {case_id}")

        read1 = split_user(records[0]["messages"][1]["content"], case_id=case_id)[0]
        read2 = split_user(records[1]["messages"][1]["content"], case_id=case_id)[0]
        read4 = split_user(records[2]["messages"][1]["content"], case_id=case_id)[0]
        if not (len(read1) < len(read2) < len(read4) and read1 in read2 and read2 in read4):
            raise AssertionError(f"frozen TRAIN48 READ ranges are not strictly nested: {case_id}")

    fact_count = sum(
        len(json.loads(by_arm["READ-1-TARGET"][case_id]["messages"][2]["content"])["facts"])
        for case_id in full_order
    )
    empty_cases = [
        case_id
        for case_id in full_order
        if not json.loads(by_arm["READ-1-TARGET"][case_id]["messages"][2]["content"])["facts"]
    ]
    if fact_count != 762 or empty_cases != ["LC-S01", "LC-S02"]:
        raise AssertionError(f"frozen TRAIN48 facts/empty drift: {fact_count}:{empty_cases}")
    return by_arm, full_order


def validate_compact24() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    source_rows = read_jsonl(COMPACT_SOURCE)
    gold_rows = read_jsonl(COMPACT_GOLD)
    if len(source_rows) != 24 or len(gold_rows) != 24:
        raise AssertionError("compact24 denominator drift")
    if len({row["case_id"] for row in source_rows}) != 24:
        raise AssertionError("compact24 source case IDs are not unique")
    source_by_case = {row["case_id"]: row for row in source_rows}
    gold_by_case = {row["case_id"]: row for row in gold_rows}
    if set(source_by_case) != set(COMPACT24_ORDER) or set(gold_by_case) != set(COMPACT24_ORDER):
        raise AssertionError("compact24 fixed order does not cover source and gold")
    if sum(len(row["facts"]) for row in gold_rows) != 68:
        raise AssertionError("compact24 fact denominator drift")
    empty_cases = [row["case_id"] for row in gold_rows if not row["facts"]]
    if empty_cases != [f"CT72-L{i:02d}" for i in range(1, 6)]:
        raise AssertionError(f"compact24 empty cases drift: {empty_cases}")
    for row in source_rows:
        if not row.get("project_original") or row.get("training_authorized"):
            raise AssertionError(f"compact source rights/status drift: {row['case_id']}")
    for row in gold_rows:
        if row.get("dataset_status") != "CANDIDATE_NOT_YET_APPROVED":
            raise AssertionError(f"compact gold status drift: {row['case_id']}")
        if row.get("expected_fact_count") != len(row["facts"]):
            raise AssertionError(f"compact gold count drift: {row['case_id']}")
    return [source_by_case[case_id] for case_id in COMPACT24_ORDER], gold_by_case


def render_compact_case(
    source_row: dict[str, Any],
    gold_row: dict[str, Any],
    validator: Draft202012Validator,
) -> dict[str, dict[str, Any]]:
    case_id = source_row["case_id"]
    path = ROOT / source_row["source_path"]
    source_bytes = path.read_bytes()
    source = source_bytes.decode("utf-8", errors="strict")
    if source.encode("utf-8") != source_bytes:
        raise AssertionError(f"source is not strict UTF-8: {case_id}")
    if sha256_bytes(source_bytes) != source_row["source_chapter_sha256"]:
        raise AssertionError(f"source chapter SHA drift: {case_id}")
    start, end = source_row["target_start"], source_row["target_end"]
    if not 0 <= start < end <= len(source):
        raise AssertionError(f"target coordinate invalid: {case_id}")
    target = source[start:end]
    if sha256_bytes(target.encode("utf-8")) != source_row["target_sha256"]:
        raise AssertionError(f"target SHA drift: {case_id}")
    body = clean_model_visible_chapter(source, start, end, case_id)

    units = source_row["target_units"]
    if not units or len(units) > 99 or "".join(unit["text"] for unit in units) != target:
        raise AssertionError(f"Txx reconstruction drift: {case_id}")
    ids = [unit["id"] for unit in units]
    if ids != [f"T{i:02d}" for i in range(1, len(units) + 1)]:
        raise AssertionError(f"Txx ID sequence drift: {case_id}")
    for unit in units:
        if unit["text"] != target[unit["start"] : unit["end"]]:
            raise AssertionError(f"Txx coordinate drift: {case_id}:{unit['id']}")
        if sha256_bytes(unit["text"].encode("utf-8")) != unit["text_sha256"]:
            raise AssertionError(f"Txx SHA drift: {case_id}:{unit['id']}")
    numbered = "".join(f"[{unit['id']}]{unit['text']}" for unit in units)
    allowlist = "、".join(ids)

    left = max(0, start - 180)
    right = min(len(body), end + 180)
    read_texts = {
        "READ-1-TARGET": target,
        "READ-2-HALO180": body[left:right],
        "READ-4-FULL-CHAPTER": body,
    }
    if not (
        len(read_texts["READ-1-TARGET"])
        < len(read_texts["READ-2-HALO180"])
        < len(read_texts["READ-4-FULL-CHAPTER"])
    ):
        raise AssertionError(f"compact READ lengths are not strictly nested: {case_id}")
    if not (
        read_texts["READ-1-TARGET"] in read_texts["READ-2-HALO180"]
        and read_texts["READ-2-HALO180"] in read_texts["READ-4-FULL-CHAPTER"]
    ):
        raise AssertionError(f"compact READ text is not a literal nested slice: {case_id}")
    if start - left > 180 or right - end > 180:
        raise AssertionError(f"HALO180 overflow: {case_id}")

    assistant_obj = {
        "facts": [
            {
                "fact": fact["fact_sentence"],
                "status": fact["status"],
                "speaker": fact["speaker"],
                "evidence_ids": fact["evidence_ids"],
            }
            for fact in gold_row["facts"]
        ]
    }
    validator.validate(assistant_obj)
    assistant = compact(assistant_obj)
    block = "COMPACT_LOW_0_TO_3" if source_row["density_band"] == "LOW_0_TO_3" else "COMPACT_MEDIUM_4_TO_6"
    result: dict[str, dict[str, Any]] = {}
    for arm, read_text in read_texts.items():
        if read_text.count(target) != 1:
            raise AssertionError(f"target must occur once in READ front: {arm}:{case_id}")
        user = USER_PREFIX + read_text + TARGET_PREFIX + numbered + ALLOW_PREFIX + allowlist
        result[arm] = {
            "metadata": {
                "family": "READ",
                "arm": arm,
                "case_id": case_id,
                "length_calibration_block": block,
                "local_demo_only": True,
            },
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
        }
    return result


def render_all() -> tuple[dict[str, bytes], dict[str, Any]]:
    validate_input_sha()
    schema_obj = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema_obj)
    validator = Draft202012Validator(schema_obj)
    frozen_by_arm, frozen_order = load_frozen_train48(validator)
    compact_sources, compact_gold = validate_compact24()

    rendered: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARM_OUTPUTS}
    for case_id in frozen_order:
        for arm in ARM_OUTPUTS:
            record = copy.deepcopy(frozen_by_arm[arm][case_id])
            record["messages"][0]["content"] = SYSTEM
            record["metadata"]["arm"] = arm
            rendered[arm].append(record)
    for source_row in compact_sources:
        by_arm = render_compact_case(source_row, compact_gold[source_row["case_id"]], validator)
        for arm in ARM_OUTPUTS:
            rendered[arm].append(by_arm[arm])

    expected_order = frozen_order + COMPACT24_ORDER
    visible_lengths: dict[str, list[int]] = {arm: [] for arm in ARM_OUTPUTS}
    read_lengths: dict[str, list[int]] = {arm: [] for arm in ARM_OUTPUTS}
    for arm, rows in rendered.items():
        if len(rows) != 72 or [row["metadata"]["case_id"] for row in rows] != expected_order:
            raise AssertionError(f"TRAIN72 row order drift: {arm}")
        for row in rows:
            case_id = row["metadata"]["case_id"]
            messages = row["messages"]
            if messages[0]["content"] != SYSTEM:
                raise AssertionError(f"system contract drift: {arm}:{case_id}")
            assistant_obj = json.loads(messages[2]["content"])
            validator.validate(assistant_obj)
            if compact(assistant_obj) != messages[2]["content"]:
                raise AssertionError(f"assistant is not canonical compact JSON: {arm}:{case_id}")
            read_text, _ = split_user(messages[1]["content"], case_id=case_id)
            visible = "\n".join(message["content"] for message in messages)
            if arm in visible or case_id in visible or "来源：Codex" in visible:
                raise AssertionError(f"metadata/footer leaked into messages: {arm}:{case_id}")
            visible_lengths[arm].append(len(visible))
            read_lengths[arm].append(len(read_text))

    for row_index, case_id in enumerate(expected_order):
        records = [rendered[arm][row_index] for arm in ARM_OUTPUTS]
        if len({record["messages"][0]["content"] for record in records}) != 1:
            raise AssertionError(f"system differs across arms: {case_id}")
        if len({record["messages"][2]["content"] for record in records}) != 1:
            raise AssertionError(f"assistant differs across arms: {case_id}")
        tails = [split_user(record["messages"][1]["content"], case_id=case_id)[1] for record in records]
        if len(set(tails)) != 1 or ALLOW_PREFIX.strip() not in tails[0]:
            raise AssertionError(f"numbered target/allowlist differs across arms: {case_id}")
        metadata = []
        for record in records:
            value = dict(record["metadata"])
            value.pop("arm", None)
            metadata.append(value)
        if len({compact(value) for value in metadata}) != 1:
            raise AssertionError(f"metadata differs beyond arm: {case_id}")
        fronts = [split_user(record["messages"][1]["content"], case_id=case_id)[0] for record in records]
        if not (len(fronts[0]) < len(fronts[1]) < len(fronts[2])):
            raise AssertionError(f"READ range lengths are not strictly nested: {case_id}")
        if not (fronts[0] in fronts[1] and fronts[1] in fronts[2]):
            raise AssertionError(f"READ range text is not strictly nested: {case_id}")

    fact_counts = [
        len(json.loads(rendered["READ-1-TARGET"][index]["messages"][2]["content"])["facts"])
        for index in range(72)
    ]
    empty_cases = [case_id for case_id, count in zip(expected_order, fact_counts, strict=True) if count == 0]
    if sum(fact_counts) != 830 or len(empty_cases) != 7:
        raise AssertionError(f"TRAIN72 facts/empty drift: {sum(fact_counts)}:{empty_cases}")
    for index in range(0, 72, 2):
        if fact_counts[index] == 0 and fact_counts[index + 1] == 0:
            raise AssertionError(f"adjacent batch2 is double-empty: rows {index + 1}-{index + 2}")

    output_bytes = {arm: jsonl_bytes(rows) for arm, rows in rendered.items()}
    if any(value > 30000 for values in visible_lengths.values() for value in values):
        raise AssertionError("obviously oversized model-visible sequence detected")
    summary = {
        "row_count": 72,
        "fact_count": sum(fact_counts),
        "empty_case_count": len(empty_cases),
        "empty_cases": empty_cases,
        "case_order": expected_order,
        "visible_character_counts": {arm: stats(values) for arm, values in visible_lengths.items()},
        "read_text_character_counts": {arm: stats(values) for arm, values in read_lengths.items()},
        "output_sha256": {
            ARM_OUTPUTS[arm].name: sha256_bytes(body) for arm, body in output_bytes.items()
        },
    }
    return output_bytes, summary


def summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# READ 家族 TRAIN72 候选教材构建说明",
        "",
        "这批只把同一批72道项目原创题渲染成三种可见正文范围，供后续公平对照；当前不是训练授权，也没有启动模型。",
        "",
        "- 组成：旧TRAIN36 36题/714条事实 + 既有S6/M6 12题/48条事实 + 紧凑目标24题/68条事实。",
        f"- 合计：{summary['row_count']}题、{summary['fact_count']}条事实、{summary['empty_case_count']}个自然空答案。",
        "- 行序：前36题保持旧顺序；既有12题按S/M交错；紧凑24题按低/中密度交错。",
        "- READ-1只读目标段；READ-2读取目标左右各最多180个Unicode字符；READ-4读取清理署名后的完整原创章。",
        "- 三臂的system合同、尾部编号负责区、证据允许表、assistant答案逐字相同；只读前部严格满足TARGET ⊂ HALO180 ⊂ FULL_CHAPTER。",
        "- 高密扩展230条、L6和LOCAL_REAL_SCREEN24均未进入训练候选文件。",
        "- 所有assistant均为严格JSON并通过冻结结构Schema；7个空题没有在任一相邻batch2中组成双空批。",
        "- 双构建在写盘前逐字比较，结果一致。这里只做粗字符检查，没有精算token。",
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
    lines.extend(["", "## 三份TRAIN72 SHA-256", ""])
    for name, digest in summary["output_sha256"].items():
        lines.append(f"- `{name}`：`{digest}`")
    lines.extend(
        [
            "",
            "本轮模型/API/训练/Notion/Git/CURRENT/生产动作均为0。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    first_bytes, first_summary = render_all()
    second_bytes, second_summary = render_all()
    if first_bytes != second_bytes or first_summary != second_summary:
        raise AssertionError("two in-process builds are not byte deterministic")
    for arm, output in ARM_OUTPUTS.items():
        output.write_bytes(first_bytes[arm])
    (OUT / "BUILD_SUMMARY.md").write_text(summary_markdown(first_summary), encoding="utf-8")
    print(
        "rows=72 facts=830 empty=7 double_empty_batches=0 "
        "schema_pass=72x3 deterministic_builds=2"
    )
    for name, digest in first_summary["output_sha256"].items():
        print(name, digest)
    for arm, values in first_summary["visible_character_counts"].items():
        print(arm, values)


if __name__ == "__main__":
    main()

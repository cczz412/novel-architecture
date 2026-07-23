"""模块 11：原样复述候选阶段的确定性合同与验票器。

该模块不调用模型。它生成后续温度 0.1 单变量轮的请求消息和程序真值，并严格
比较模型输出；任何改写、重排、漏项或增项都判失败。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .errors import ZBatchError
from .prompt_render_pin import load_pinned_text, prompt_sha256, render_prompt, sha256_bytes


INPUT_SCHEMA_VERSION = "z-verbatim-restatement-input-v1"
OUTPUT_SCHEMA_VERSION = "z-verbatim-restatement-v1"
INPUT_ROOT_KEYS = {"schema_version", "items"}
INPUT_ITEM_KEYS = {"item_id", "source_sha256", "source_text"}
OUTPUT_ROOT_KEYS = {"schema_version", "items"}
OUTPUT_ITEM_KEYS = {"item_id", "source_sha256", "text"}
ITEM_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SYSTEM_MESSAGE = "你只做逐字原样复述。不得总结、改写、纠错、分类或添加内容。只输出合法 JSON。"


def validate_input(data: Any) -> list[str]:
    reasons: list[str] = []
    if not isinstance(data, dict):
        return ["复述输入不是对象"]
    if set(data) != INPUT_ROOT_KEYS:
        reasons.append("复述输入根字段错误")
    if data.get("schema_version") != INPUT_SCHEMA_VERSION:
        reasons.append("复述输入schema错误")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return sorted(set(reasons + ["复述输入items为空或不是数组"]))
    seen: list[str] = []
    for index, item in enumerate(items, 1):
        label = f"输入项{index}"
        if not isinstance(item, dict):
            reasons.append(f"{label}不是对象")
            continue
        if set(item) != INPUT_ITEM_KEYS:
            reasons.append(f"{label}字段错误")
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or not ITEM_ID_PATTERN.fullmatch(item_id):
            reasons.append(f"{label}编号非法")
        else:
            seen.append(item_id)
        source_text = item.get("source_text")
        source_sha = item.get("source_sha256")
        if not isinstance(source_text, str) or not source_text:
            reasons.append(f"{label}原文为空")
        if not isinstance(source_sha, str) or not SHA256_PATTERN.fullmatch(source_sha):
            reasons.append(f"{label}原文SHA非法")
        elif isinstance(source_text, str) and source_sha != sha256_bytes(source_text.encode("utf-8")):
            reasons.append(f"{label}原文SHA不匹配")
    if len(seen) != len(set(seen)):
        reasons.append("复述输入编号重复")
    return sorted(set(reasons))


def deterministic_output(data: dict[str, Any]) -> dict[str, Any]:
    """生成程序真值；后续模型输出必须与它逐字段相等。"""
    reasons = validate_input(data)
    if reasons:
        raise ZBatchError(f"原样复述输入无效：{reasons}")
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "items": [
            {
                "item_id": item["item_id"],
                "source_sha256": item["source_sha256"],
                "text": item["source_text"],
            }
            for item in data["items"]
        ],
    }


def build_messages(
    data: dict[str, Any],
    *,
    prompt_path: Path,
    expected_prompt_sha256: str,
) -> dict[str, Any]:
    """构造独立 API 候选阶段的完整 messages；不在本函数发请求。"""
    expected = deterministic_output(data)
    template = load_pinned_text(prompt_path, expected_prompt_sha256)
    input_json = json.dumps(data, ensure_ascii=False, indent=2)
    user_prompt = render_prompt(template, {"INPUT_JSON": input_json})
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": user_prompt},
        ],
        "template_sha256": expected_prompt_sha256,
        "prompt_sha256": prompt_sha256(user_prompt),
        "input_sha256": sha256_bytes(input_json.encode("utf-8")),
        "expected_output_sha256": sha256_bytes(
            json.dumps(expected, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ),
    }


def output_reasons(output: Any, source: dict[str, Any]) -> list[str]:
    """逐项比较输出与程序真值，任何变化都给出失败原因。"""
    reasons = validate_input(source)
    if reasons:
        return reasons
    if not isinstance(output, dict):
        return ["复述输出不是对象"]
    if set(output) != OUTPUT_ROOT_KEYS:
        reasons.append("复述输出根字段错误")
    if output.get("schema_version") != OUTPUT_SCHEMA_VERSION:
        reasons.append("复述输出schema错误")
    items = output.get("items")
    if not isinstance(items, list):
        return sorted(set(reasons + ["复述输出items不是数组"]))
    expected = deterministic_output(source)["items"]
    if len(items) != len(expected):
        reasons.append("复述输出项数变化")
    for index, expected_item in enumerate(expected):
        if index >= len(items):
            break
        actual = items[index]
        label = f"输出项{index + 1}"
        if not isinstance(actual, dict):
            reasons.append(f"{label}不是对象")
            continue
        if set(actual) != OUTPUT_ITEM_KEYS:
            reasons.append(f"{label}字段错误")
        if actual.get("item_id") != expected_item["item_id"]:
            reasons.append(f"{label}编号或顺序变化")
        if actual.get("source_sha256") != expected_item["source_sha256"]:
            reasons.append(f"{label}来源SHA变化")
        if actual.get("text") != expected_item["text"]:
            reasons.append(f"{label}不是逐字原样复述")
    return sorted(set(reasons))


def require_exact_output(output: Any, source: dict[str, Any]) -> dict[str, Any]:
    reasons = output_reasons(output, source)
    if reasons:
        raise ZBatchError(f"原样复述回包无效：{reasons}；不做修补")
    assert isinstance(output, dict)
    return output

#!/usr/bin/env python3
"""抽取工序重设计 v0.2：C0/C1 锚先行实验零调用备料工具。

这个工具只做本地确定性工作：

- 布尔检查 SenseNova 环境变量名是否存在，不读取密钥值；
- 从三份正式金标指针回读原文来源与 SHA；
- 从原文机械生成冻结锚目录；
- 预构造对照臂／锚先行臂请求并做正式金标答案泄漏扫描；
- 提供闭集锚对齐回包的机械反查与离线过闸函数。

工具没有发网子命令，也不会签发 ``judge_green_ticket``。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from zbatch_modules import api_transport, neutral_extract


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "C_anchor_first_experiment"
)
C3_OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "C3_claim_span_prompt_explicit_examples"
)
PROVIDER_CONFIG_PATH = ROOT / "config/providers/sensenova_modular_v1.json"
STAGE_CONTRACT_PATH = ROOT / "config/contracts/sensenova_stage_sampling_v1.json"
ACCESS_POLICY_PATH = ROOT / "config/providers/provider_access_policy.json"
BASE_PROMPT_PATH = (
    ROOT / "work/zbatch_prompts/candidates/extract_event_only_no_self_audit_v1.1.md"
)
API_TRANSPORT_PATH = ROOT / "tools/zbatch_modules/api_transport.py"

CONTRACT_VERSION = "closed_anchor_alignment.v1"
PROMPT_VARIANT_C1 = "c1_original"
PROMPT_VARIANT_C3 = "c3_claim_span_explicit_examples"
PROMPT_VARIANTS = (PROMPT_VARIANT_C1, PROMPT_VARIANT_C3)
PREP_SCHEMA_VERSION = "v02-anchor-first-c0-c1-prep.v1"
SCORE_SCHEMA_VERSION = "v02-anchor-first-offline-score.v1"
GATE_SCHEMA_VERSION = "v02-anchor-first-gate-result.v1"
K_MISSING = "K_MISSING"
PINNED_PROVIDER = "sensenova"
PINNED_MODEL = "deepseek-v4-flash"
PINNED_KEY_ENV = "SENSENOVA_API_KEY"
SENSENOVA_DOCUMENTED_MAX_TOKENS = 65536
CATALOG_QUOTE_WIDTH = 22
CATALOG_STEP = 18
OFFLINE_DENOMINATOR = 49
NO_REGRESSION_LAYERS = ("FCR", "QCR_full", "ASR_full", "UCR")
ALL_SCORE_LAYERS = (*NO_REGRESSION_LAYERS, "SOP")

FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "answer",
        "evaluation_policy",
        "formal_gold",
        "gold_id",
        "item_id",
        "label_tier",
        "layered_items",
        "part_id",
        "reference_answer",
        "revision_record",
        "score_in_single_chapter",
        "semantic_coverage_ledger",
    }
)
GOLD_IDENTITY_KEYS = frozenset(
    {
        "anchor_id",
        "gold_id",
        "item_id",
        "part_id",
        "source_part_id",
    }
)
GOLD_SEMANTIC_KEYS = frozenset(
    {
        "claim",
        "decision",
        "explicit_result_or_constraint",
        "reason",
        "structural_importance",
        "text",
    }
)


class V02PrepError(RuntimeError):
    """C0/C1 机械准备不满足冻结条件。"""


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    book_id: str
    short_name: str
    unit: int
    denominator: int
    pointer_path: Path


CASES: tuple[CaseSpec, ...] = (
    CaseSpec(
        case_id="B02-U0039",
        book_id="Z74B-B02",
        short_name="大王饶命",
        unit=39,
        denominator=8,
        pointer_path=ROOT / "config/gold/Z74B_B02_U0039_structure_gold_current.json",
    ),
    CaseSpec(
        case_id="B03-U0041",
        book_id="Z74B-B03",
        short_name="神秘复苏",
        unit=41,
        denominator=16,
        pointer_path=ROOT / "config/gold/Z74B_B03_U0041_structure_gold_current.json",
    ),
    CaseSpec(
        case_id="B01-U0033",
        book_id="Z74B-B01",
        short_name="知否",
        unit=33,
        denominator=25,
        pointer_path=ROOT / "config/gold/Z74B_B01_U0033_structure_gold_current.json",
    ),
)
CASE_BY_ID = {case.case_id: case for case in CASES}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise V02PrepError(f"JSON 顶层不是对象：{path}")
    return value


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def resolve_stored_path(stored: str) -> Path:
    path = Path(stored)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def parse_k(raw: Any) -> int | str:
    if raw == K_MISSING or raw is None:
        return K_MISSING
    if isinstance(raw, bool):
        raise V02PrepError("K 不能是布尔值")
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str) and raw.isdigit():
        value = int(raw)
    else:
        raise V02PrepError(f"K 必须是正整数或 {K_MISSING}")
    if value <= 0:
        raise V02PrepError("K 必须大于 0")
    return value


def _cache_body_from_formal_source(
    *,
    cache_path: Path,
    formal_source: Mapping[str, Any],
) -> tuple[str, str]:
    cache_text = cache_path.read_text(encoding="utf-8")
    heading, separator, raw_body = cache_text.partition("\n")
    heading = heading.rstrip("\r")
    if not separator or not heading:
        raise V02PrepError(f"章节缓存缺少首行章头：{cache_path}")
    expected_heading = formal_source.get("complete_heading")
    if heading != expected_heading:
        raise V02PrepError(f"章节缓存章头漂移：{cache_path}")

    body = raw_body.lstrip("\r\n").strip("\r\n")
    trim = formal_source.get("cache_author_note_trim")
    if not isinstance(trim, Mapping):
        raise V02PrepError("正式来源缺少作者话裁切审计")
    if trim.get("applied") is True:
        marker = trim.get("marker")
        if not isinstance(marker, str) or marker not in body:
            raise V02PrepError("正式来源声明裁切作者话，但本地找不到冻结标记")
        body = body.split(marker, 1)[0]
        lines = body.rstrip("\r\n").splitlines()
        while lines and lines[-1].strip() == "※※※":
            lines.pop()
        body = "\n".join(lines).strip("\r\n")
    if len(body) != trim.get("evidence_body_char_count"):
        raise V02PrepError("章节缓存正文字符数与正式来源不一致")
    return heading, body


def load_case_source(case: CaseSpec) -> dict[str, Any]:
    pointer = read_object(case.pointer_path)
    if pointer.get("book_id") != case.book_id:
        raise V02PrepError(f"{case.case_id} 正式指针书目身份漂移")
    if pointer.get("inventory_unit") != case.unit:
        raise V02PrepError(f"{case.case_id} 正式指针库存单元漂移")

    active = pointer.get("active_gold")
    if not isinstance(active, Mapping):
        raise V02PrepError(f"{case.case_id} 正式指针缺 active_gold")
    active_path_raw = active.get("path")
    active_sha = active.get("sha256")
    if not isinstance(active_path_raw, str) or not is_sha256(active_sha):
        raise V02PrepError(f"{case.case_id} 正式指针路径或 SHA 非法")
    formal_path = resolve_stored_path(active_path_raw)
    if not formal_path.is_file() or sha256_file(formal_path) != active_sha:
        raise V02PrepError(f"{case.case_id} 正式金标缺失或 SHA 漂移")
    formal = read_object(formal_path)

    source = formal.get("source")
    if not isinstance(source, Mapping):
        raise V02PrepError(f"{case.case_id} 正式金标缺 source")
    if source.get("book_id") != case.book_id:
        raise V02PrepError(f"{case.case_id} 正式金标书目身份漂移")
    if source.get("inventory_unit") != case.unit:
        raise V02PrepError(f"{case.case_id} 正式金标库存单元漂移")

    layer_summary = formal.get("layer_summary")
    policy = formal.get("evaluation_policy")
    if not isinstance(layer_summary, Mapping) or not isinstance(policy, Mapping):
        raise V02PrepError(f"{case.case_id} 正式金标缺离线计分口径")
    observed_denominators = {
        layer_summary.get("formal_denominator"),
        layer_summary.get("on_unit_scoreable_atomic_part_total"),
        policy.get("formal_denominator"),
    }
    if observed_denominators != {case.denominator}:
        raise V02PrepError(
            f"{case.case_id} 离线分母漂移：{sorted(str(x) for x in observed_denominators)}"
        )

    cache_path_raw = source.get("cache_file_path")
    cache_sha = source.get("cache_file_sha256")
    body_sha = source.get("cache_body_sha256")
    if (
        not isinstance(cache_path_raw, str)
        or not is_sha256(cache_sha)
        or not is_sha256(body_sha)
    ):
        raise V02PrepError(f"{case.case_id} 原文缓存来源字段不合同")
    cache_path = Path(cache_path_raw).resolve()
    if not cache_path.is_file() or sha256_file(cache_path) != cache_sha:
        raise V02PrepError(f"{case.case_id} 原文缓存缺失或 SHA 漂移")
    heading, body = _cache_body_from_formal_source(
        cache_path=cache_path,
        formal_source=source,
    )
    if sha256_bytes(body.encode("utf-8")) != body_sha:
        raise V02PrepError(f"{case.case_id} 原文正文 SHA 漂移")

    full_path_raw = source.get("full_txt_path")
    full_sha = source.get("full_txt_sha256")
    if not isinstance(full_path_raw, str) or not is_sha256(full_sha):
        raise V02PrepError(f"{case.case_id} 小说单体来源字段不合同")
    full_path = Path(full_path_raw).resolve()
    if not full_path.is_file() or sha256_file(full_path) != full_sha:
        raise V02PrepError(f"{case.case_id} 小说单体缺失或 SHA 漂移")

    return {
        "case": case,
        "pointer": pointer,
        "pointer_path": case.pointer_path.resolve(),
        "pointer_sha256": sha256_file(case.pointer_path),
        "formal": formal,
        "formal_path": formal_path,
        "formal_sha256": str(active_sha),
        "source": dict(source),
        "cache_path": cache_path,
        "cache_sha256": str(cache_sha),
        "body": body,
        "body_sha256": str(body_sha),
        "heading": heading,
        "full_path": full_path,
        "full_sha256": str(full_sha),
    }


def _catalog_windows(text: str) -> list[tuple[int, int, str]]:
    stripped = text.strip()
    if not stripped:
        return []
    base_offset = text.find(stripped)
    positions = [
        index for index, character in enumerate(stripped) if not character.isspace()
    ]
    total = len(positions)
    if total < 10:
        return []
    if total <= 25:
        start = base_offset
        end = base_offset + len(stripped)
        return [(start, end, stripped)]

    starts = list(
        range(
            0,
            total - CATALOG_QUOTE_WIDTH + 1,
            CATALOG_STEP,
        )
    )
    tail_start = total - CATALOG_QUOTE_WIDTH
    if not starts or starts[-1] != tail_start:
        starts.append(tail_start)

    windows: list[tuple[int, int, str]] = []
    for nonspace_start in starts:
        nonspace_end = nonspace_start + CATALOG_QUOTE_WIDTH
        char_start = positions[nonspace_start]
        char_end = positions[nonspace_end - 1] + 1
        raw = stripped[char_start:char_end]
        quote = raw.strip()
        left_trim = len(raw) - len(raw.lstrip())
        right_trimmed_length = len(raw.rstrip())
        start = base_offset + char_start + left_trim
        end = base_offset + char_start + right_trimmed_length
        if not 10 <= len(re.sub(r"\s+", "", quote)) <= 25:
            raise V02PrepError("机械锚短引越出 10～25 非空白字符")
        if text[start:end] != quote:
            raise V02PrepError("机械锚偏移不能反查原文")
        windows.append((start, end, quote))
    return windows


def generate_anchor_catalog(
    *,
    case_id: str,
    chapter: int,
    text: str,
    selection_k: int | str = K_MISSING,
) -> dict[str, Any]:
    """生成完整冻结目录；K 只管单条最小锚集上限，不截断原文目录。"""

    k = parse_k(selection_k)
    windows = _catalog_windows(text)
    entries = [
        {
            "anchor_id": f"E{index:04d}",
            "chapter": chapter,
            "quote": quote,
            "body_start_char": start,
            "body_end_char_exclusive": end,
            "nonspace_char_count": len(re.sub(r"\s+", "", quote)),
        }
        for index, (start, end, quote) in enumerate(windows, start=1)
    ]
    covered: set[int] = set()
    all_nonspace = {
        index for index, character in enumerate(text) if not character.isspace()
    }
    for entry in entries:
        covered.update(
            index
            for index in range(
                int(entry["body_start_char"]),
                int(entry["body_end_char_exclusive"]),
            )
            if not text[index].isspace()
        )
    coverage = (
        1.0 if not all_nonspace else len(covered & all_nonspace) / len(all_nonspace)
    )
    if coverage != 1.0:
        raise V02PrepError(f"{case_id} 机械锚目录未覆盖全文：{coverage}")

    return {
        "schema_version": "v02-anchor-catalog.v1",
        "case_id": case_id,
        "chapter": chapter,
        "source_body_sha256": sha256_bytes(text.encode("utf-8")),
        "generator": {
            "algorithm": "existing_overlapping_nonspace_windows",
            "quote_width_nonspace_chars": CATALOG_QUOTE_WIDTH,
            "step_nonspace_chars": CATALOG_STEP,
            "coverage": coverage,
        },
        "selection_k": k,
        "selection_k_semantics": (
            "每条事件最小锚集的可选数字上限；K_MISSING 表示没有获批数字，"
            "程序不得猜值，也不得用猜值截断完整目录。"
        ),
        "entry_count": len(entries),
        "entries": entries,
    }


def closed_anchor_alignment_schema(
    selection_k: int | str = K_MISSING,
) -> dict[str, Any]:
    k = parse_k(selection_k)
    anchor_ids: dict[str, Any] = {
        "type": "array",
        "minItems": 1,
        "uniqueItems": True,
        "items": {
            "type": "string",
            "pattern": r"^E\d{4}$",
        },
    }
    if isinstance(k, int):
        anchor_ids["maxItems"] = k
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": CONTRACT_VERSION,
        "title": "闭集锚先行对齐回包",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "chapter", "events"],
        "properties": {
            "schema_version": {"const": CONTRACT_VERSION},
            "chapter": {"type": "integer", "minimum": 1},
            "events": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "event_id",
                        "event",
                        "minimal_anchor_ids",
                        "support_obligations",
                    ],
                    "properties": {
                        "event_id": {
                            "type": "string",
                            "pattern": r"^EV-C\d{4}-\d{2}$",
                        },
                        "event": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 100,
                        },
                        "minimal_anchor_ids": copy.deepcopy(anchor_ids),
                        "support_obligations": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "claim_span",
                                    "anchor_ids",
                                    "combination",
                                ],
                                "properties": {
                                    "claim_span": {
                                        "type": "string",
                                        "minLength": 1,
                                    },
                                    "anchor_ids": copy.deepcopy(anchor_ids),
                                    "combination": {
                                        "const": "all_required",
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "x_selection_k": k,
        "x_semantic_boundary": (
            "程序只验证闭集身份、原文反查、集合全等和删除后合同失配；"
            "不把机械 PASS 冒充语义承托 PASS。"
        ),
    }


def _contract_prompt_suffix(
    selection_k: int | str,
    *,
    chapter: int,
    prompt_variant: str = PROMPT_VARIANT_C1,
) -> str:
    if prompt_variant not in PROMPT_VARIANTS:
        raise V02PrepError(f"未知题面版本：{prompt_variant}")
    k = parse_k(selection_k)
    if k == K_MISSING:
        k_rule = (
            f"K 当前明确记为 {K_MISSING}。不得猜一个数字上限；"
            "仍须从完整目录中交出每条事件的最小完整锚集。"
        )
    else:
        k_rule = f"每条事件的 minimal_anchor_ids 最多 {k} 个。"
    claim_span_rule = (
        "- support_obligations 的 claim_span 必须逐字出现在 event 中。"
    )
    if prompt_variant == PROMPT_VARIANT_C3:
        claim_span_rule = """
- 【产出硬规则】每个 support_obligations.claim_span 都必须是同一条 event 的逐字连续子串。先把要由锚承托的主张原样写进 event，再从 event 中逐字复制 claim_span；禁止只把支撑义务写在 event 外的 support_obligations 里。
- 正例（只教字段关系，不是本章答案，不得抄入本章结果）：event 写“巡夜人把钥匙交给值班员，值班员收下钥匙。”，claim_span 写“巡夜人把钥匙交给值班员”。claim_span 逐字出现在 event 中，合格。
- 反例（禁止）：event 只写“巡夜人完成交接。”，claim_span 却写“巡夜人把钥匙交给值班员”。支撑义务只出现在 event 外，claim_span 不是 event 的逐字连续子串，不合格。
""".strip()
    return f"""

【实验单变量｜{CONTRACT_VERSION}】

本臂只新增一件事：先从上方完整冻结目录里选锚，再写事件，并交出可由程序反查的承托义务。

- 只能使用目录中已有的 anchor_id。
- minimal_anchor_ids 必须是该事件的最小完整锚集，不能重复。
{claim_span_rule}
- 每个义务的 anchor_ids 都按 all_required 解释；所有义务所用 ID 的并集必须恰好等于 minimal_anchor_ids。
- {k_rule}

本臂只输出下面这个 JSON 外壳，不要代码围栏，不要解释：

```json
{{
  "schema_version": "{CONTRACT_VERSION}",
  "chapter": {{{{CHAPTER_NUMBER_ALREADY_RENDERED}}}},
  "events": [
    {{
      "event_id": "EV-C{chapter:04d}-01",
      "event": "本章明确发生或说出口的一件中性事实",
      "minimal_anchor_ids": ["E0001"],
      "support_obligations": [
        {{
          "claim_span": "事件中由该锚承托的原句片段",
          "anchor_ids": ["E0001"],
          "combination": "all_required"
        }}
      ]
    }}
  ]
}}
```
""".strip()


def _sampling_profile() -> dict[str, Any]:
    contract = read_object(STAGE_CONTRACT_PATH)
    route = contract.get("route")
    if not isinstance(route, Mapping):
        raise V02PrepError("SenseNova 阶段合同缺 route")
    profile = contract.get("profiles")
    if not isinstance(profile, Mapping):
        raise V02PrepError("SenseNova 阶段合同缺 profiles")
    cutover = profile.get("d_mod_cutover_v1")
    if not isinstance(cutover, Mapping):
        raise V02PrepError("SenseNova 阶段合同缺 d_mod_cutover_v1")
    stages = cutover.get("stages")
    if not isinstance(stages, Mapping):
        raise V02PrepError("SenseNova 阶段合同缺 stages")
    stage = stages.get("neutral_extract")
    if not isinstance(stage, Mapping):
        raise V02PrepError("SenseNova 阶段合同缺 neutral_extract")
    if stage.get("status") != "approved_transport_reference":
        raise V02PrepError("neutral_extract 不是获批运输参照")
    return dict(stage)


def load_provider_route() -> tuple[dict[str, Any], api_transport.TransportRoute]:
    provider = read_object(PROVIDER_CONFIG_PATH)
    route = api_transport.TransportRoute.from_mapping(provider)
    if route.provider != PINNED_PROVIDER:
        raise V02PrepError("供应商不是 SenseNova")
    if route.model != PINNED_MODEL:
        raise V02PrepError("Flash 型号不是 deepseek-v4-flash")
    if route.api_key_env != PINNED_KEY_ENV:
        raise V02PrepError("SenseNova 密钥变量名漂移")
    return provider, route


def _request_body(
    *,
    messages: list[dict[str, str]],
    route: api_transport.TransportRoute,
    max_tokens_override: int | None = None,
) -> dict[str, Any]:
    stage = _sampling_profile()
    max_tokens = stage.get("max_tokens")
    if max_tokens_override is not None:
        if (
            isinstance(max_tokens_override, bool)
            or not isinstance(max_tokens_override, int)
            or not 1 <= max_tokens_override <= SENSENOVA_DOCUMENTED_MAX_TOKENS
        ):
            raise V02PrepError(
                "max_tokens_override 必须在 SenseNova 文档范围 [1, 65536] 内"
            )
        max_tokens = max_tokens_override
    body: dict[str, Any] = {
        "model": route.model,
        "messages": messages,
        "temperature": stage.get("temperature"),
        "max_tokens": max_tokens,
        "n": stage.get("n"),
        "response_format": stage.get("response_format"),
    }
    effort = stage.get("reasoning_effort")
    if isinstance(effort, str) and effort.lower() not in {"", "-", "off", "omit"}:
        body["reasoning_effort"] = effort
    return body


def build_request_pair(
    *,
    source: Mapping[str, Any],
    catalog: Mapping[str, Any],
    selection_k: int | str,
    prompt_variant: str = PROMPT_VARIANT_C1,
    max_tokens_override: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case = source["case"]
    if not isinstance(case, CaseSpec):
        raise V02PrepError("内部 case 类型错误")
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        raise V02PrepError(f"{case.case_id} 锚目录缺 entries")
    prompt_sha = sha256_file(BASE_PROMPT_PATH)
    rendered = neutral_extract.build_messages(
        prompt_path=BASE_PROMPT_PATH,
        expected_prompt_sha256=prompt_sha,
        chapter=case.unit,
        chapter_filename=source["cache_path"].name,
        catalog=entries,
    )
    control_messages = rendered["messages"]
    if not isinstance(control_messages, list):
        raise V02PrepError("现役中性提取消息渲染失败")
    treatment_messages = copy.deepcopy(control_messages)
    suffix = _contract_prompt_suffix(
        selection_k,
        chapter=case.unit,
        prompt_variant=prompt_variant,
    ).replace(
        "{{CHAPTER_NUMBER_ALREADY_RENDERED}}",
        str(case.unit),
    )
    treatment_messages[-1]["content"] += "\n\n" + suffix + "\n"

    _provider, route = load_provider_route()
    common = {
        "schema_version": "v02-prepared-request.v1",
        "case_id": case.case_id,
        "provider": route.provider,
        "api_base_url": route.base_url,
        "api_endpoint": route.endpoint,
        "model": route.model,
        "source_body_sha256": source["body_sha256"],
        "catalog_sha256": canonical_sha(catalog),
        "_security": "no_api_key_no_authorization",
    }
    control = {
        **common,
        "arm": "control",
        "body": _request_body(
            messages=control_messages,
            route=route,
            max_tokens_override=max_tokens_override,
        ),
    }
    treatment = {
        **common,
        "arm": "anchor_first",
        "body": _request_body(
            messages=treatment_messages,
            route=route,
            max_tokens_override=max_tokens_override,
        ),
    }

    stripped = copy.deepcopy(treatment)
    treatment_content = stripped["body"]["messages"][-1]["content"]
    control_content = control["body"]["messages"][-1]["content"]
    suffix_with_spacing = "\n\n" + suffix + "\n"
    if not treatment_content.endswith(suffix_with_spacing):
        raise V02PrepError("锚先行单变量后缀没有稳定附加")
    stripped["body"]["messages"][-1]["content"] = treatment_content[
        : -len(suffix_with_spacing)
    ]
    differences = {
        "schema_version": "v02-request-pair-diff.v1",
        "case_id": case.case_id,
        "only_delta": "closed_anchor_alignment_contract",
        "control_equals_treatment_after_suffix_removal": stripped
        == {**control, "arm": "anchor_first"},
        "control_user_prompt_is_exact_prefix": treatment_content.startswith(
            control_content
        ),
        "contract_suffix_sha256": sha256_bytes(suffix.encode("utf-8")),
        "sampling_equal": control["body"] | {"messages": []}
        == treatment["body"] | {"messages": []},
        "planned_calls": {"control": 1, "anchor_first": 1, "additional": 0},
    }
    if (
        differences["control_equals_treatment_after_suffix_removal"] is not True
        or differences["control_user_prompt_is_exact_prefix"] is not True
        or differences["sampling_equal"] is not True
    ):
        raise V02PrepError(f"{case.case_id} 请求不再是锚合同单变量")
    return control, treatment, differences


def _iter_paths(
    value: Any, prefix: tuple[str, ...] = ()
) -> Sequence[tuple[tuple[str, ...], Any]]:
    rows: list[tuple[tuple[str, ...], Any]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = (*prefix, str(key))
            rows.append((path, item))
            rows.extend(_iter_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = (*prefix, str(index))
            rows.append((path, item))
            rows.extend(_iter_paths(item, path))
    return rows


def _gold_signatures(source: Mapping[str, Any]) -> dict[str, set[str]]:
    formal = source["formal"]
    body = str(source["body"])
    identity: set[str] = {
        str(source["formal_sha256"]),
        str(source["formal_path"]),
        display_path(source["formal_path"]),
        display_path(source["pointer_path"]),
    }
    semantic: set[str] = set()
    for path, value in _iter_paths(formal):
        if not path or not isinstance(value, str) or not value:
            continue
        key = path[-1]
        if key in GOLD_IDENTITY_KEYS:
            identity.add(value)
        if key in GOLD_SEMANTIC_KEYS and len(value.strip()) >= 6:
            candidate = value.strip()
            if candidate not in body:
                semantic.add(candidate)
        if "claim_components" in path and len(value.strip()) >= 6:
            candidate = value.strip()
            if candidate not in body:
                semantic.add(candidate)
    return {"identity": identity, "semantic": semantic}


def _forbidden_key_paths(request: Mapping[str, Any]) -> list[str]:
    hits: list[str] = []
    for path, _value in _iter_paths(request):
        if path and path[-1].lower() in FORBIDDEN_REQUEST_KEYS:
            hits.append(".".join(path))
    return sorted(set(hits))


def leakage_scan(
    *,
    requests: Mapping[str, Mapping[str, Any]],
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    combined_identity: set[str] = set()
    combined_semantic: set[str] = set()
    for source in sources.values():
        signatures = _gold_signatures(source)
        combined_identity.update(signatures["identity"])
        combined_semantic.update(signatures["semantic"])

    for request_id, request in sorted(requests.items()):
        raw = json.dumps(request, ensure_ascii=False, sort_keys=True)
        identity_hits = sorted(
            signature
            for signature in combined_identity
            if signature and signature in raw
        )
        semantic_hits = sorted(
            signature
            for signature in combined_semantic
            if signature and signature in raw
        )
        key_hits = _forbidden_key_paths(request)
        rows.append(
            {
                "request_id": request_id,
                "request_sha256": canonical_sha(request),
                "formal_gold_identity_hit_count": len(identity_hits),
                "formal_gold_answer_hit_count": len(semantic_hits),
                "forbidden_request_key_hit_count": len(key_hits),
                "hit_fingerprints": [
                    sha256_bytes(value.encode("utf-8"))
                    for value in (*identity_hits, *semantic_hits, *key_hits)
                ],
                "pass": not identity_hits and not semantic_hits and not key_hits,
            }
        )
    return {
        "schema_version": "v02-request-gold-leakage-scan.v1",
        "scope": "six_prepared_requests",
        "request_count": len(rows),
        "gold_identity_signature_count": len(combined_identity),
        "gold_answer_signature_count": len(combined_semantic),
        "gold_signature_set_sha256": canonical_sha(
            {
                "identity": sorted(combined_identity),
                "semantic": sorted(combined_semantic),
            }
        ),
        "rows": rows,
        "formal_gold_identity_hits": sum(
            row["formal_gold_identity_hit_count"] for row in rows
        ),
        "formal_gold_answer_hits": sum(
            row["formal_gold_answer_hit_count"] for row in rows
        ),
        "forbidden_request_key_hits": sum(
            row["forbidden_request_key_hit_count"] for row in rows
        ),
        "status": "pass_zero_gold_or_answer_leak"
        if all(row["pass"] for row in rows)
        else "fail_gold_or_answer_leak",
    }


def c0_check(
    environ: Mapping[str, str] = os.environ,
) -> dict[str, Any]:
    """只用成员测试检查变量名是否存在，不索引也不打印密钥值。"""

    provider, route = load_provider_route()
    policy = read_object(ACCESS_POLICY_PATH)
    providers = policy.get("providers")
    official = (
        providers.get("deepseek_official") if isinstance(providers, Mapping) else None
    )
    access_policy_ok = (
        policy.get("default_chain_provider") == PINNED_PROVIDER
        and isinstance(official, Mapping)
        and official.get("default_action") == "deny"
    )
    route_ok = (
        provider.get("allowed_models") == [PINNED_MODEL]
        and route.provider == PINNED_PROVIDER
        and route.model == PINNED_MODEL
        and route.api_key_env == PINNED_KEY_ENV
    )
    call_entry = getattr(api_transport.ApiTransport, "call", None)
    dedicated_probe_names = (
        "check_reachability",
        "healthcheck",
        "probe_reachability",
    )
    dedicated_probe = any(
        callable(getattr(api_transport.ApiTransport, name, None))
        for name in dedicated_probe_names
    )
    key_present = PINNED_KEY_ENV in environ
    checks = {
        "provider_config_valid": route_ok,
        "access_policy_keeps_deepseek_official_denied": access_policy_ok,
        "transport_entry_importable": callable(call_entry),
        "live_request_entry_can_observe_reachability": callable(call_entry),
        "dedicated_zero_inference_reachability_probe": dedicated_probe,
        "api_key_environment_name_present": key_present,
        "api_key_value_read": False,
        "api_key_value_printed": False,
    }
    technical_ready_without_secret = (
        route_ok and access_policy_ok and callable(call_entry)
    )
    return {
        "schema_version": "v02-anchor-first-c0-check.v1",
        "status": (
            "pass_technical_ready_key_name_present"
            if technical_ready_without_secret and key_present
            else "hold_environment_not_loaded"
            if technical_ready_without_secret
            else "fail_local_transport_configuration"
        ),
        "provider": route.provider,
        "model": route.model,
        "api_key_env": route.api_key_env,
        "checks": checks,
        "technical_ready_without_secret": technical_ready_without_secret,
        "live_provider_reachability": "unknown_zero_network_boundary",
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _catalog_map(catalog: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        raise V02PrepError("锚目录 entries 不是数组")
    result: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise V02PrepError("锚目录条目不是对象")
        anchor_id = entry.get("anchor_id")
        if not isinstance(anchor_id, str) or anchor_id in result:
            raise V02PrepError("锚目录 ID 缺失或重复")
        result[anchor_id] = entry
    return result


def validate_closed_anchor_alignment(
    response: Any,
    *,
    catalog: Mapping[str, Any],
    source_text: str,
) -> dict[str, Any]:
    """机械验证闭集身份、原文反查与声明式最小集；不判语义真伪。"""

    errors: list[str] = []
    event_checks: list[dict[str, Any]] = []
    catalog_by_id = _catalog_map(catalog)
    expected_body_sha = catalog.get("source_body_sha256")
    if sha256_bytes(source_text.encode("utf-8")) != expected_body_sha:
        errors.append("source_body_sha256_mismatch")
    selection_k = parse_k(catalog.get("selection_k"))

    if not isinstance(response, Mapping):
        return {
            "schema_version": "v02-closed-anchor-validation.v1",
            "status": "fail",
            "errors": ["response_not_object"],
            "events": [],
            "semantic_support_verified": False,
            "model_api_calls": 0,
            "network_requests": 0,
        }
    if set(response) != {"schema_version", "chapter", "events"}:
        errors.append("root_keys_not_exact")
    if response.get("schema_version") != CONTRACT_VERSION:
        errors.append("schema_version_mismatch")
    if response.get("chapter") != catalog.get("chapter"):
        errors.append("chapter_mismatch")
    events = response.get("events")
    if not isinstance(events, list) or not events:
        errors.append("events_empty_or_not_array")
        events = []

    expected_event_ids = [
        f"EV-C{int(catalog['chapter']):04d}-{index:02d}"
        for index in range(1, len(events) + 1)
    ]
    observed_ids: list[str] = []
    for index, event in enumerate(events):
        event_errors: list[str] = []
        removal_checks: list[dict[str, Any]] = []
        if not isinstance(event, Mapping):
            event_checks.append(
                {
                    "index": index,
                    "status": "fail",
                    "errors": ["event_not_object"],
                    "removal_checks": [],
                }
            )
            errors.append(f"event_{index}_not_object")
            continue
        expected_keys = {
            "event_id",
            "event",
            "minimal_anchor_ids",
            "support_obligations",
        }
        if set(event) != expected_keys:
            event_errors.append("event_keys_not_exact")
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            observed_ids.append(event_id)
        if event_id != expected_event_ids[index]:
            event_errors.append("event_id_not_contiguous")
        event_text = event.get("event")
        if not isinstance(event_text, str) or not event_text.strip():
            event_errors.append("event_text_empty")
            event_text = ""

        selected = event.get("minimal_anchor_ids")
        if not isinstance(selected, list) or not selected:
            event_errors.append("minimal_anchor_ids_empty_or_not_array")
            selected = []
        if any(not isinstance(value, str) for value in selected):
            event_errors.append("minimal_anchor_id_not_string")
        selected_strings = [value for value in selected if isinstance(value, str)]
        if len(selected_strings) != len(set(selected_strings)):
            event_errors.append("minimal_anchor_ids_duplicate")
        if isinstance(selection_k, int) and len(selected_strings) > selection_k:
            event_errors.append("selection_k_exceeded")

        for anchor_id in selected_strings:
            entry = catalog_by_id.get(anchor_id)
            if entry is None:
                event_errors.append(f"unknown_anchor_id:{anchor_id}")
                continue
            start = entry.get("body_start_char")
            end = entry.get("body_end_char_exclusive")
            quote = entry.get("quote")
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or not isinstance(quote, str)
                or start < 0
                or end <= start
                or source_text[start:end] != quote
            ):
                event_errors.append(f"anchor_reverse_lookup_failed:{anchor_id}")

        obligations = event.get("support_obligations")
        if not isinstance(obligations, list) or not obligations:
            event_errors.append("support_obligations_empty_or_not_array")
            obligations = []
        obligation_anchor_union: set[str] = set()
        obligation_rows: list[tuple[str, set[str]]] = []
        for obligation_index, obligation in enumerate(obligations):
            if not isinstance(obligation, Mapping):
                event_errors.append(f"support_obligation_{obligation_index}_not_object")
                continue
            if set(obligation) != {"claim_span", "anchor_ids", "combination"}:
                event_errors.append(
                    f"support_obligation_{obligation_index}_keys_not_exact"
                )
            span = obligation.get("claim_span")
            ids = obligation.get("anchor_ids")
            if not isinstance(span, str) or not span or span not in event_text:
                event_errors.append(
                    f"support_obligation_{obligation_index}_span_not_in_event"
                )
            if obligation.get("combination") != "all_required":
                event_errors.append(
                    f"support_obligation_{obligation_index}_combination_invalid"
                )
            if not isinstance(ids, list) or not ids:
                event_errors.append(f"support_obligation_{obligation_index}_ids_empty")
                continue
            if any(not isinstance(value, str) for value in ids):
                event_errors.append(
                    f"support_obligation_{obligation_index}_id_not_string"
                )
            id_set = {value for value in ids if isinstance(value, str)}
            if len(id_set) != len(ids):
                event_errors.append(
                    f"support_obligation_{obligation_index}_ids_duplicate"
                )
            if not id_set.issubset(set(selected_strings)):
                event_errors.append(
                    f"support_obligation_{obligation_index}_outside_minimal_set"
                )
            obligation_anchor_union.update(id_set)
            obligation_rows.append((str(span or ""), id_set))

        if obligation_anchor_union != set(selected_strings):
            event_errors.append("support_union_not_equal_minimal_anchor_set")
        for anchor_id in selected_strings:
            broken = [span for span, ids in obligation_rows if anchor_id in ids]
            removal_checks.append(
                {
                    "removed_anchor_id": anchor_id,
                    "broken_obligation_count": len(broken),
                    "mechanical_minimality_pass": bool(broken),
                }
            )
            if not broken:
                event_errors.append(
                    f"anchor_not_required_by_any_obligation:{anchor_id}"
                )

        event_checks.append(
            {
                "event_id": event_id,
                "status": "pass" if not event_errors else "fail",
                "errors": sorted(set(event_errors)),
                "selected_anchor_count": len(selected_strings),
                "removal_checks": removal_checks,
            }
        )
        errors.extend(f"{event_id or index}:{reason}" for reason in event_errors)
    if observed_ids != expected_event_ids:
        errors.append("event_id_sequence_mismatch")

    unique_errors = sorted(set(errors))
    return {
        "schema_version": "v02-closed-anchor-validation.v1",
        "status": "pass" if not unique_errors else "fail",
        "errors": unique_errors,
        "events": event_checks,
        "closed_catalog_identity_verified": not any(
            "unknown_anchor_id" in error for error in unique_errors
        ),
        "source_reverse_lookup_verified": not any(
            "reverse_lookup_failed" in error for error in unique_errors
        )
        and "source_body_sha256_mismatch" not in unique_errors,
        "declared_minimal_set_verified": all(
            row["status"] == "pass" for row in event_checks
        )
        and bool(event_checks),
        "semantic_support_verified": False,
        "semantic_boundary": (
            "PASS 只说明模型声明的承托义务在闭集、偏移、集合和删除测试上自洽；"
            "语义承托仍须离线独立判分。"
        ),
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _normalize_score_document(document: Mapping[str, Any]) -> dict[str, Any]:
    if document.get("schema_version") != SCORE_SCHEMA_VERSION:
        raise V02PrepError("离线分数 schema 不符")
    chapters = document.get("chapters")
    if not isinstance(chapters, Mapping) or set(chapters) != set(CASE_BY_ID):
        raise V02PrepError("离线分数必须且只能包含三章")

    normalized_chapters: dict[str, Any] = {}
    aggregate_layers = {
        layer: {"passed": 0, "denominator": 0} for layer in ALL_SCORE_LAYERS
    }
    total_anchor_partial = 0
    total_calls = 0
    for case_id, case in CASE_BY_ID.items():
        row = chapters.get(case_id)
        if not isinstance(row, Mapping):
            raise V02PrepError(f"{case_id} 离线分数不是对象")
        if row.get("denominator") != case.denominator:
            raise V02PrepError(f"{case_id} 离线分母不是 {case.denominator}")
        failure_counts = row.get("failure_counts")
        if not isinstance(failure_counts, Mapping):
            raise V02PrepError(f"{case_id} 缺 failure_counts")
        anchor_partial = failure_counts.get("ANCHOR_PARTIAL")
        if (
            isinstance(anchor_partial, bool)
            or not isinstance(anchor_partial, int)
            or anchor_partial < 0
        ):
            raise V02PrepError(f"{case_id} ANCHOR_PARTIAL 必须是非负整数")
        layers = row.get("layers")
        if not isinstance(layers, Mapping):
            raise V02PrepError(f"{case_id} 缺五层分数")
        normalized_layers: dict[str, Any] = {}
        for layer in ALL_SCORE_LAYERS:
            metric = layers.get(layer)
            if not isinstance(metric, Mapping):
                raise V02PrepError(f"{case_id} 缺 {layer}")
            passed = metric.get("passed")
            denominator = metric.get("denominator")
            if (
                isinstance(passed, bool)
                or not isinstance(passed, int)
                or passed < 0
                or denominator != case.denominator
                or passed > denominator
            ):
                raise V02PrepError(f"{case_id} {layer} 分数不合同")
            rate = passed / denominator
            normalized_layers[layer] = {
                "passed": passed,
                "denominator": denominator,
                "rate": rate,
            }
            aggregate_layers[layer]["passed"] += passed
            aggregate_layers[layer]["denominator"] += denominator
        calls = row.get("model_api_calls")
        if isinstance(calls, bool) or not isinstance(calls, int) or calls < 0:
            raise V02PrepError(f"{case_id} model_api_calls 必须是非负整数")
        normalized_chapters[case_id] = {
            "denominator": case.denominator,
            "anchor_partial": anchor_partial,
            "layers": normalized_layers,
            "model_api_calls": calls,
        }
        total_anchor_partial += anchor_partial
        total_calls += calls

    for metric in aggregate_layers.values():
        if metric["denominator"] != OFFLINE_DENOMINATOR:
            raise V02PrepError("五层合计分母不是 49")
        metric["rate"] = metric["passed"] / metric["denominator"]
    return {
        "chapters": normalized_chapters,
        "anchor_partial": total_anchor_partial,
        "layers": aggregate_layers,
        "model_api_calls": total_calls,
        "denominator": OFFLINE_DENOMINATOR,
    }


def evaluate_gate(
    control: Mapping[str, Any],
    treatment: Mapping[str, Any],
) -> dict[str, Any]:
    """按 C1 冻结判据离线判定；不读取请求，也不调用模型。"""

    baseline = _normalize_score_document(control)
    candidate = _normalize_score_document(treatment)
    control_failures = baseline["anchor_partial"]
    treatment_failures = candidate["anchor_partial"]
    absolute_reduction = control_failures - treatment_failures
    relative_reduction = (
        absolute_reduction / control_failures if control_failures > 0 else 0.0
    )
    relative_gate_pass = (
        control_failures > 0 and treatment_failures * 2 <= control_failures
    )
    declining_chapters = [
        case_id
        for case_id in CASE_BY_ID
        if candidate["chapters"][case_id]["anchor_partial"]
        < baseline["chapters"][case_id]["anchor_partial"]
    ]
    layer_checks = {
        layer: {
            "control_passed": baseline["layers"][layer]["passed"],
            "treatment_passed": candidate["layers"][layer]["passed"],
            "delta": (
                candidate["layers"][layer]["passed"]
                - baseline["layers"][layer]["passed"]
            ),
            "pass": (
                candidate["layers"][layer]["passed"]
                >= baseline["layers"][layer]["passed"]
            ),
        }
        for layer in NO_REGRESSION_LAYERS
    }
    sop_rate = candidate["layers"]["SOP"]["rate"]
    additional_calls = candidate["model_api_calls"] - baseline["model_api_calls"]
    checks = {
        "anchor_partial_relative_reduction_at_least_50_percent": relative_gate_pass,
        "anchor_partial_declines_in_at_least_two_of_three_chapters": len(
            declining_chapters
        )
        >= 2,
        "fcr_qcr_asr_ucr_no_regression": all(
            row["pass"] for row in layer_checks.values()
        ),
        "sop_at_least_0_98": sop_rate >= 0.98,
        "zero_additional_model_calls": additional_calls == 0,
        "offline_denominator_is_49": (
            baseline["denominator"] == candidate["denominator"] == OFFLINE_DENOMINATOR
        ),
    }
    experiment_gate_pass = all(checks.values())
    reporting_mode = (
        "absolute_counts_control_below_10"
        if control_failures < 10
        else "relative_and_absolute_counts"
    )
    return {
        "schema_version": GATE_SCHEMA_VERSION,
        "status": "pass_experiment_gate"
        if experiment_gate_pass
        else "fail_experiment_gate",
        "checks": checks,
        "anchor_partial": {
            "control": control_failures,
            "treatment": treatment_failures,
            "absolute_reduction": absolute_reduction,
            "relative_reduction": relative_reduction,
            "reporting_mode": reporting_mode,
            "declining_chapters": declining_chapters,
            "declining_chapter_count": len(declining_chapters),
        },
        "no_regression_layers": layer_checks,
        "treatment_sop": candidate["layers"]["SOP"],
        "calls": {
            "control": baseline["model_api_calls"],
            "treatment": candidate["model_api_calls"],
            "additional": additional_calls,
        },
        "offline_denominator": OFFLINE_DENOMINATOR,
        "experiment_gate_pass": experiment_gate_pass,
        "judge_green_ticket_eligible": False,
        "judge_green_ticket_issued": False,
        "judge_green_ticket_reason": (
            "旧 Z98 三信任根不阻断实验 A，但当前件没有独立裁判签票权限。"
        ),
    }


def _score_template() -> dict[str, Any]:
    return {
        "schema_version": SCORE_SCHEMA_VERSION,
        "role": "CONTROL_OR_TREATMENT_FILL_AFTER_C2",
        "offline_only": True,
        "formal_gold_never_model_visible": True,
        "chapters": {
            case.case_id: {
                "denominator": case.denominator,
                "failure_counts": {"ANCHOR_PARTIAL": None},
                "layers": {
                    layer: {
                        "passed": None,
                        "denominator": case.denominator,
                    }
                    for layer in ALL_SCORE_LAYERS
                },
                "model_api_calls": None,
            }
            for case in CASES
        },
    }


def _gate_contract() -> dict[str, Any]:
    return {
        "schema_version": "v02-anchor-first-gate-contract.v1",
        "offline_denominator": OFFLINE_DENOMINATOR,
        "criteria": {
            "anchor_partial_relative_reduction": {
                "operator": ">=",
                "threshold": 0.5,
            },
            "anchor_partial_declining_chapters": {
                "operator": ">=",
                "threshold": 2,
                "chapter_total": 3,
            },
            "no_regression_layers": list(NO_REGRESSION_LAYERS),
            "sop": {"operator": ">=", "threshold": 0.98},
            "additional_model_calls": {"operator": "==", "threshold": 0},
            "control_anchor_partial_below_10_reporting": (
                "必须报告对照、实验和减少的绝对数；过闸仍按精确整数比较候选*2<=对照。"
            ),
        },
        "authority": {
            "experiment_a_may_run_without_z98_three_trust_roots": True,
            "judge_green_ticket_may_issue": False,
        },
    }


def _readme(
    selection_k: int | str,
    prompt_variant: str = PROMPT_VARIANT_C1,
    max_tokens_override: int | None = None,
) -> str:
    if max_tokens_override is not None:
        return f"""# C4｜V02 运输面唯一探针冻结件

✅ 这里从 C3 冻结真源机械重建三章请求，唯一差异是把 `max_tokens` 从 16000 抬到 SenseNova 文档上限 {max_tokens_override}。

🔥 模型可见 messages、题面、合同、JSON 输出结构、正文供料、冻结锚目录、temperature、n、reasoning_effort 与 response_format 全部不变；`top_p` 继续不发送。

当前 K：`{selection_k}`。本目录只负责 V02/C4 冻结。正式执行必须先发 B02-U0039 唯一探针；只有 `finish_reason=stop`、完整 JSON 与含 `claim_span` 的机械闸全过，才准继续 B03/B01。

旧 C2/C3 运行与供料都是 LEGACY 只读，不回写、不捞回截断响应。

来源：Codex
"""
    if prompt_variant == PROMPT_VARIANT_C3:
        return f"""# C3｜claim_span 显式产出规则重发准备

✅ 这里从 C1 真源机械重建三章请求，只在模型可见题面里把 `claim_span` 的既有硬合同写成显式产出规则，并加入一组正反例。

🔥 合同、JSON 输出结构、三章正文、冻结锚目录、供应商、模型与采样参数全部不变。C1 原目录和 C2 首轮废票均不回写。

当前 K：`{selection_k}`。`claim_span` 仍须逐字出现在同一条 `event` 中，机械闸没有放宽。

正式金标只在离线判分时使用。六份预构造请求已经做答案泄漏扫描，模型可见请求不含正式金标路径、ID、主张或答案。

本目录只负责零调用冻结。发网仍由独立执行器明确指定本目录后进行，固定使用 SenseNova／`deepseek-v4-flash`／`SENSENOVA_API_KEY`。

来源：Codex
"""
    return f"""# C｜锚先行实验 C0/C1 零调用准备

✅ 这里已经冻结三章来源、机械锚目录、对照臂请求、锚先行臂请求和离线过闸规则。

🔥 两臂只有一个差别：锚先行臂在现役中性抽取提示后追加 `{CONTRACT_VERSION}` 合同；供应商、模型、采样参数和原文目录完全相同。

当前 K：`{selection_k}`。它只表示“每条事件最小锚集的可选上限”。`K_MISSING` 不会被程序偷换成数字，也不会截断完整锚目录。

正式金标只在离线判分时使用。六份预构造请求已经做答案泄漏扫描，模型可见请求不含正式金标路径、ID、主张或答案。

这个目录没有发网能力。C2 真要运行时，要另用获批运输入口，并继续保持 SenseNova／`deepseek-v4-flash`／`SENSENOVA_API_KEY`。

来源：Codex
"""


def build_artifacts(
    *,
    selection_k: int | str = K_MISSING,
    environ: Mapping[str, str] = os.environ,
    prompt_variant: str = PROMPT_VARIANT_C1,
    max_tokens_override: int | None = None,
) -> dict[str, bytes]:
    if prompt_variant not in PROMPT_VARIANTS:
        raise V02PrepError(f"未知题面版本：{prompt_variant}")
    k = parse_k(selection_k)
    loaded = {case.case_id: load_case_source(case) for case in CASES}
    if sum(case.denominator for case in CASES) != OFFLINE_DENOMINATOR:
        raise V02PrepError("三章冻结分母合计不是 49")

    source_manifest = {
        "schema_version": "v02-anchor-first-source-manifest.v1",
        "chapter_total": len(CASES),
        "offline_denominator": OFFLINE_DENOMINATOR,
        "formal_gold_usage": "offline_scoring_only_never_model_visible",
        "chapters": [],
    }
    catalogs: dict[str, dict[str, Any]] = {}
    requests: dict[str, dict[str, Any]] = {}
    pair_diffs: list[dict[str, Any]] = []
    for case in CASES:
        source = loaded[case.case_id]
        source_manifest["chapters"].append(
            {
                "case_id": case.case_id,
                "book_id": case.book_id,
                "short_name": case.short_name,
                "inventory_unit": case.unit,
                "complete_heading": source["heading"],
                "formal_denominator": case.denominator,
                "gold_pointer": {
                    "path": display_path(source["pointer_path"]),
                    "sha256": source["pointer_sha256"],
                    "model_visible": False,
                },
                "formal_gold": {
                    "path": display_path(source["formal_path"]),
                    "sha256": source["formal_sha256"],
                    "model_visible": False,
                },
                "chapter_cache": {
                    "path": display_path(source["cache_path"]),
                    "file_sha256": source["cache_sha256"],
                    "body_sha256": source["body_sha256"],
                    "body_char_count": len(source["body"]),
                    "model_visible_via_mechanical_catalog_only": True,
                },
                "full_txt": {
                    "path": display_path(source["full_path"]),
                    "sha256": source["full_sha256"],
                    "model_visible": False,
                },
            }
        )
        catalog = generate_anchor_catalog(
            case_id=case.case_id,
            chapter=case.unit,
            text=source["body"],
            selection_k=k,
        )
        catalogs[case.case_id] = catalog
        control, treatment, pair_diff = build_request_pair(
            source=source,
            catalog=catalog,
            selection_k=k,
            prompt_variant=prompt_variant,
            max_tokens_override=max_tokens_override,
        )
        requests[f"control/{case.case_id}"] = control
        requests[f"anchor_first/{case.case_id}"] = treatment
        pair_diffs.append(pair_diff)

    leak = leakage_scan(requests=requests, sources=loaded)
    if leak["status"] != "pass_zero_gold_or_answer_leak":
        raise V02PrepError("模型请求发现正式金标或答案泄漏")
    if any(
        row["control_equals_treatment_after_suffix_removal"] is not True
        or row["sampling_equal"] is not True
        for row in pair_diffs
    ):
        raise V02PrepError("两臂不是锚合同单变量")

    c0 = c0_check(environ)
    request_lock = {
        "schema_version": "v02-anchor-first-request-lock.v1",
        "control_product_definition": (
            "C1 锁的是三份对照请求产物；C2 模型回包尚不存在，生成后必须另记 SHA，"
            "不得把未产生的答案写成已锁定。"
        ),
        "control_requests": [
            {
                "case_id": case.case_id,
                "path": f"requests/control/{case.case_id}.json",
                "sha256": canonical_sha(requests[f"control/{case.case_id}"]),
            }
            for case in CASES
        ],
        "anchor_first_requests": [
            {
                "case_id": case.case_id,
                "path": f"requests/anchor_first/{case.case_id}.json",
                "sha256": canonical_sha(requests[f"anchor_first/{case.case_id}"]),
            }
            for case in CASES
        ],
        "single_variable_checks": pair_diffs,
        "planned_calls": {
            "control": 3,
            "anchor_first": 3,
            "additional": 0,
        },
        "c2_output_lock_state": "not_created_zero_call_c1",
    }
    local_prep_ready = (
        c0["technical_ready_without_secret"] is True
        and leak["status"] == "pass_zero_gold_or_answer_leak"
        and all(
            row["control_equals_treatment_after_suffix_removal"]
            and row["sampling_equal"]
            for row in pair_diffs
        )
    )
    c1 = {
        "schema_version": PREP_SCHEMA_VERSION,
        "status": "pass_zero_call_prepared"
        if local_prep_ready
        else "fail_local_preparation",
        "chapters": [case.case_id for case in CASES],
        "offline_denominator": OFFLINE_DENOMINATOR,
        "selection_k": k,
        "selection_k_missing_is_not_guessed": k == K_MISSING,
        "selection_k_missing_blocks_preparation": False,
        "provider": PINNED_PROVIDER,
        "model": PINNED_MODEL,
        "api_key_env": PINNED_KEY_ENV,
        "gold_or_answer_leak_count": (
            leak["formal_gold_identity_hits"]
            + leak["formal_gold_answer_hits"]
            + leak["forbidden_request_key_hits"]
        ),
        "single_variable_only_closed_anchor_contract": True,
        "control_request_products_locked": True,
        "model_api_calls": 0,
        "network_requests": 0,
        "live_provider_reachability": "unknown_zero_network_boundary",
        "c2_known_local_hold_reasons": (
            []
            if c0["checks"]["api_key_environment_name_present"]
            else ["SENSENOVA_API_KEY_not_loaded_in_current_process"]
        ),
        "c2_known_local_hold_only_environment_variable": (
            local_prep_ready and not c0["checks"]["api_key_environment_name_present"]
        ),
        "z98_three_trust_roots_block_experiment_a": False,
        "judge_green_ticket_eligible": False,
        "judge_green_ticket_issued": False,
    }

    config = {
        "schema_version": "v02-anchor-first-experiment-config.v1",
        "experiment": "A_anchor_first_closed_alignment",
        "provider": PINNED_PROVIDER,
        "model": PINNED_MODEL,
        "api_key_env": PINNED_KEY_ENV,
        "selection_k": k,
        "selection_k_default": K_MISSING,
        "single_variable": CONTRACT_VERSION,
        "formal_gold_model_visibility": False,
        "offline_denominator": OFFLINE_DENOMINATOR,
        "network_enabled_in_this_tool": False,
    }
    if prompt_variant != PROMPT_VARIANT_C1:
        config["prompt_variant"] = prompt_variant
    if max_tokens_override is not None:
        config["max_tokens_override"] = max_tokens_override
        config["single_variable"] = "transport_max_tokens_only"
        config["base_prompt_variant"] = prompt_variant

    artifacts: dict[str, bytes] = {
        "README.md": _readme(
            k,
            prompt_variant,
            max_tokens_override,
        ).encode("utf-8"),
        "config.json": canonical_bytes(config),
        "source_manifest.json": canonical_bytes(source_manifest),
        "contracts/closed_anchor_alignment.v1.schema.json": canonical_bytes(
            closed_anchor_alignment_schema(k)
        ),
        "gate/gate_contract.json": canonical_bytes(_gate_contract()),
        "gate/offline_score_template.json": canonical_bytes(_score_template()),
        "c0_check.json": canonical_bytes(c0),
        "c1_preflight.json": canonical_bytes(c1),
        "request_lock.json": canonical_bytes(request_lock),
        "leakage_scan.json": canonical_bytes(leak),
    }
    if prompt_variant == PROMPT_VARIANT_C3:
        delta_rows: list[dict[str, Any]] = []
        for case in CASES:
            source = loaded[case.case_id]
            c1_control, c1_treatment, _c1_diff = build_request_pair(
                source=source,
                catalog=catalogs[case.case_id],
                selection_k=k,
                prompt_variant=PROMPT_VARIANT_C1,
                max_tokens_override=max_tokens_override,
            )
            c3_control = requests[f"control/{case.case_id}"]
            c3_treatment = requests[f"anchor_first/{case.case_id}"]
            c1_body = c1_treatment["body"]
            c3_body = c3_treatment["body"]
            c1_messages = c1_body["messages"]
            c3_messages = c3_body["messages"]
            c1_user = c1_messages[-1]["content"]
            c3_user = c3_messages[-1]["content"]
            delta_rows.append(
                {
                    "case_id": case.case_id,
                    "control_request_byte_equivalent": c1_control == c3_control,
                    "request_shell_equal": {
                        key: value
                        for key, value in c1_treatment.items()
                        if key != "body"
                    }
                    == {
                        key: value
                        for key, value in c3_treatment.items()
                        if key != "body"
                    },
                    "sampling_equal": {
                        key: value
                        for key, value in c1_body.items()
                        if key != "messages"
                    }
                    == {
                        key: value
                        for key, value in c3_body.items()
                        if key != "messages"
                    },
                    "messages_before_last_equal": c1_messages[:-1]
                    == c3_messages[:-1],
                    "last_message_role_equal": c1_messages[-1]["role"]
                    == c3_messages[-1]["role"],
                    "c1_request_sha256": canonical_sha(c1_treatment),
                    "c3_request_sha256": canonical_sha(c3_treatment),
                    "c1_user_prompt_sha256": sha256_bytes(
                        c1_user.encode("utf-8")
                    ),
                    "c3_user_prompt_sha256": sha256_bytes(
                        c3_user.encode("utf-8")
                    ),
                }
            )
        if any(
            not row["control_request_byte_equivalent"]
            or not row["request_shell_equal"]
            or not row["sampling_equal"]
            or not row["messages_before_last_equal"]
            or not row["last_message_role_equal"]
            for row in delta_rows
        ):
            raise V02PrepError("C3 相对 C1 不再只是题面改写")
        artifacts["c3_prompt_delta_receipt.json"] = canonical_bytes(
            {
                "schema_version": "v02-anchor-first-c3-prompt-delta.v1",
                "status": "pass_prompt_only_change",
                "from_prompt_variant": PROMPT_VARIANT_C1,
                "to_prompt_variant": PROMPT_VARIANT_C3,
                "contract_schema_sha256": sha256_bytes(
                    artifacts[
                        "contracts/closed_anchor_alignment.v1.schema.json"
                    ]
                ),
                "output_structure_changed": False,
                "mechanical_claim_span_gate_changed": False,
                "rows": delta_rows,
                "model_api_calls": 0,
                "network_requests": 0,
            }
        )
    if max_tokens_override is not None:
        if (
            prompt_variant != PROMPT_VARIANT_C3
            or max_tokens_override != SENSENOVA_DOCUMENTED_MAX_TOKENS
        ):
            raise V02PrepError(
                "当前运输探针只允许 C3 题面与 max_tokens=65536 的组合"
            )
        delta_rows: list[dict[str, Any]] = []
        for case in CASES:
            source = loaded[case.case_id]
            _c3_control, c3_treatment, _c3_diff = build_request_pair(
                source=source,
                catalog=catalogs[case.case_id],
                selection_k=k,
                prompt_variant=PROMPT_VARIANT_C3,
            )
            c4_treatment = requests[f"anchor_first/{case.case_id}"]
            c3_body = c3_treatment["body"]
            c4_body = c4_treatment["body"]
            c3_without_limit = {
                key: value for key, value in c3_body.items() if key != "max_tokens"
            }
            c4_without_limit = {
                key: value for key, value in c4_body.items() if key != "max_tokens"
            }
            delta_rows.append(
                {
                    "case_id": case.case_id,
                    "request_shell_equal": {
                        key: value
                        for key, value in c3_treatment.items()
                        if key != "body"
                    }
                    == {
                        key: value
                        for key, value in c4_treatment.items()
                        if key != "body"
                    },
                    "messages_byte_equivalent": canonical_bytes(
                        c3_body["messages"]
                    )
                    == canonical_bytes(c4_body["messages"]),
                    "body_except_max_tokens_equal": c3_without_limit
                    == c4_without_limit,
                    "top_p_omitted_before": "top_p" not in c3_body,
                    "top_p_omitted_after": "top_p" not in c4_body,
                    "from_max_tokens": c3_body["max_tokens"],
                    "to_max_tokens": c4_body["max_tokens"],
                    "c3_request_sha256": canonical_sha(c3_treatment),
                    "c4_request_sha256": canonical_sha(c4_treatment),
                    "c3_messages_sha256": canonical_sha(c3_body["messages"]),
                    "c4_messages_sha256": canonical_sha(c4_body["messages"]),
                }
            )
        if any(
            not row["request_shell_equal"]
            or not row["messages_byte_equivalent"]
            or not row["body_except_max_tokens_equal"]
            or not row["top_p_omitted_before"]
            or not row["top_p_omitted_after"]
            or row["from_max_tokens"] != 16000
            or row["to_max_tokens"] != SENSENOVA_DOCUMENTED_MAX_TOKENS
            for row in delta_rows
        ):
            raise V02PrepError("C4 相对 C3 不再只是 max_tokens 运输参数")
        artifacts["c4_transport_delta_receipt.json"] = canonical_bytes(
            {
                "schema_version": "v02-anchor-first-c4-transport-delta.v1",
                "status": "pass_max_tokens_only_change",
                "from_max_tokens": 16000,
                "to_max_tokens": SENSENOVA_DOCUMENTED_MAX_TOKENS,
                "model_visible_messages_changed": False,
                "sampling_or_contract_field_changed": False,
                "rows": delta_rows,
                "model_api_calls": 0,
                "network_requests": 0,
            }
        )
    for case in CASES:
        artifacts[f"catalogs/{case.case_id}.json"] = canonical_bytes(
            catalogs[case.case_id]
        )
        artifacts[f"requests/control/{case.case_id}.json"] = canonical_bytes(
            requests[f"control/{case.case_id}"]
        )
        artifacts[f"requests/anchor_first/{case.case_id}.json"] = canonical_bytes(
            requests[f"anchor_first/{case.case_id}"]
        )

    artifact_manifest = {
        "schema_version": "v02-anchor-first-artifact-manifest.v1",
        "file_total_excluding_manifest": len(artifacts),
        "files": [
            {
                "path": name,
                "sha256": sha256_bytes(raw),
                "bytes": len(raw),
            }
            for name, raw in sorted(artifacts.items())
        ],
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(artifact_manifest)
    return artifacts


def write_artifacts(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(artifacts.items()):
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if not target.is_file() or target.read_bytes() != raw:
                raise V02PrepError(f"拒绝覆盖已存在且内容不同的产物：{target}")
            continue
        target.write_bytes(raw)


def verify_artifacts(
    output_dir: Path, artifacts: Mapping[str, bytes]
) -> dict[str, Any]:
    missing: list[str] = []
    changed: list[str] = []
    for relative, raw in sorted(artifacts.items()):
        target = output_dir / relative
        if not target.is_file():
            missing.append(relative)
        elif target.read_bytes() != raw:
            changed.append(relative)
    return {
        "schema_version": "v02-anchor-first-artifact-verification.v1",
        "status": "pass" if not missing and not changed else "fail",
        "expected_file_total": len(artifacts),
        "missing": missing,
        "changed": changed,
        "artifact_set_sha256": canonical_sha(
            {relative: sha256_bytes(raw) for relative, raw in sorted(artifacts.items())}
        ),
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _load_catalog_and_source(
    case_id: str,
    catalog_path: Path,
) -> tuple[dict[str, Any], str]:
    case = CASE_BY_ID.get(case_id)
    if case is None:
        raise V02PrepError(f"未知 case_id：{case_id}")
    catalog = read_object(catalog_path)
    source = load_case_source(case)
    return catalog, str(source["body"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="v0.2 锚先行实验 C0/C1 零调用备料；本工具没有发网能力。"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="生成或核对 C0/C1 冻结产物")
    prepare.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    prepare.add_argument("--k", default=K_MISSING)
    prepare.add_argument(
        "--prompt-variant",
        choices=PROMPT_VARIANTS,
        default=PROMPT_VARIANT_C1,
    )
    prepare.add_argument(
        "--max-tokens-override",
        type=int,
        help="仅运输探针使用；当前只接受 C3 题面配 65536。",
    )
    prepare.add_argument("--dry-run", action="store_true")

    verify = sub.add_parser("verify", help="从真源重建并逐字核对现有产物")
    verify.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    verify.add_argument("--k", default=K_MISSING)
    verify.add_argument(
        "--prompt-variant",
        choices=PROMPT_VARIANTS,
        default=PROMPT_VARIANT_C1,
    )
    verify.add_argument(
        "--max-tokens-override",
        type=int,
        help="仅运输探针使用；当前只接受 C3 题面配 65536。",
    )

    sub.add_parser("c0", help="只打印无密钥值的 C0 布尔检查")

    validate = sub.add_parser(
        "validate-response",
        help="机械反查一份 closed_anchor_alignment.v1 回包",
    )
    validate.add_argument("--case-id", required=True, choices=sorted(CASE_BY_ID))
    validate.add_argument("--catalog", type=Path, required=True)
    validate.add_argument("--response", type=Path, required=True)

    gate = sub.add_parser("evaluate-gate", help="离线计算锚先行过闸结果")
    gate.add_argument("--control", type=Path, required=True)
    gate.add_argument("--treatment", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "c0":
        result = c0_check()
    elif args.command == "prepare":
        artifacts = build_artifacts(
            selection_k=parse_k(args.k),
            prompt_variant=args.prompt_variant,
            max_tokens_override=args.max_tokens_override,
        )
        if not args.dry_run:
            write_artifacts(args.output_dir, artifacts)
        result = {
            "schema_version": "v02-anchor-first-prepare-command.v1",
            "status": "pass_zero_call_dry_run"
            if args.dry_run
            else "pass_zero_call_written_or_identical",
            "output_dir": display_path(args.output_dir),
            "artifact_total": len(artifacts),
            "artifact_set_sha256": canonical_sha(
                {
                    relative: sha256_bytes(raw)
                    for relative, raw in sorted(artifacts.items())
                }
            ),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    elif args.command == "verify":
        artifacts = build_artifacts(
            selection_k=parse_k(args.k),
            prompt_variant=args.prompt_variant,
            max_tokens_override=args.max_tokens_override,
        )
        result = verify_artifacts(args.output_dir, artifacts)
    elif args.command == "validate-response":
        catalog, source_text = _load_catalog_and_source(
            args.case_id,
            args.catalog,
        )
        response = read_object(args.response)
        result = validate_closed_anchor_alignment(
            response,
            catalog=catalog,
            source_text=source_text,
        )
    elif args.command == "evaluate-gate":
        result = evaluate_gate(
            read_object(args.control),
            read_object(args.treatment),
        )
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status", "").startswith(("pass", "hold")) else 1


if __name__ == "__main__":
    raise SystemExit(main())

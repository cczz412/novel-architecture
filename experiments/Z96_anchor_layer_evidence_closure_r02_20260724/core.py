"""Z96 r02 的纯内存候选召回、渲染与离线判分函数。

候选生成函数只看事件、已引锚和冻结目录。离线答案只允许进入
``audit_render`` 与 ``score_recall``，不会被用来改写候选集合。
本模块不读写文件，也不调用模型或网络。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any, TypeVar


class Z96CoreError(ValueError):
    """输入不符合 Z96 r02 冻结合同。"""


_TNumber = TypeVar("_TNumber", int, float)
_FORBIDDEN_CANDIDATE_KEY_PARTS = (
    "necessary",
    "missing",
    "expected",
    "verdict",
    "reason",
    "sufficient_support_groups",
    "claim_span_seed",
)
_CLAIM_BREAKS = frozenset("，,；;。！？!?：:")
_LATIN_WORD_PATTERN = re.compile(r"[A-Za-z0-9_]+")
_CJK_RUN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


def stable_json_bytes(value: Any) -> bytes:
    """把 JSON 兼容值编码成稳定、可复验的 UTF-8 字节。"""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    """返回字节内容的小写 SHA-256 十六进制摘要。"""

    if not isinstance(data, bytes):
        raise Z96CoreError("sha256_bytes 只接受 bytes")
    return hashlib.sha256(data).hexdigest()


def nearest_rank_percentile(
    values: Sequence[_TNumber],
    percentile: float,
) -> _TNumber:
    """按 nearest-rank 定义返回百分位值，百分位范围为 ``(0, 1]``。"""

    if not values:
        raise Z96CoreError("百分位输入不能为空")
    if (
        isinstance(percentile, bool)
        or not isinstance(percentile, (int, float))
        or not math.isfinite(float(percentile))
        or not 0 < float(percentile) <= 1
    ):
        raise Z96CoreError("百分位必须是 (0, 1] 内的有限数")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in values
    ):
        raise Z96CoreError("百分位样本必须全部是有限数")
    ordered = sorted(values)
    rank = math.ceil(float(percentile) * len(ordered))
    return ordered[rank - 1]


def validate_candidate_input(candidate_input: Any) -> Any:
    """递归拒绝候选侧的答案暗示键，校验成功后原样返回输入。

    键名比较不区分大小写；任意层级的对象都受检查。返回原对象是为了
    让调用方能在表达式中串接校验，但函数本身不会修改它。
    """

    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise Z96CoreError(f"{path} 含非字符串键")
                lowered = key.casefold()
                matched = next(
                    (
                        fragment
                        for fragment in _FORBIDDEN_CANDIDATE_KEY_PARTS
                        if fragment in lowered
                    ),
                    None,
                )
                if matched is not None:
                    raise Z96CoreError(
                        f"{path}.{key} 含候选侧禁用键片段：{matched}"
                    )
                visit(child, f"{path}.{key}")
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(candidate_input, "$")
    return candidate_input


def split_atomic_claims(event_id: str, event_text: str) -> list[dict[str, Any]]:
    """按标点边界切出原子主张，并逐字符完整覆盖原事件字符串。

    分隔标点和紧随其后的空白保留在前一个主张中。返回记录严格只含
    ``claim_id``、``claim_text``、``source_event_id``、``source_start``
    和 ``source_end``；不生成或携带任何锚字段。
    """

    if not isinstance(event_id, str) or not event_id:
        raise Z96CoreError("event_id 必须是非空字符串")
    if not isinstance(event_text, str):
        raise Z96CoreError("event_text 必须是字符串")
    if not event_text:
        return []

    spans: list[tuple[int, int]] = []
    start = 0
    index = 0
    while index < len(event_text):
        if event_text[index] in _CLAIM_BREAKS:
            end = index + 1
            while end < len(event_text) and event_text[end].isspace():
                end += 1
            spans.append((start, end))
            start = end
            index = end
            continue
        index += 1
    if start < len(event_text):
        spans.append((start, len(event_text)))

    claims = [
        {
            "claim_id": f"{event_id}:CLAIM-{claim_number:03d}",
            "claim_text": event_text[source_start:source_end],
            "source_event_id": event_id,
            "source_start": source_start,
            "source_end": source_end,
        }
        for claim_number, (source_start, source_end) in enumerate(spans, start=1)
    ]
    if "".join(str(row["claim_text"]) for row in claims) != event_text:
        raise AssertionError("原子主张切分没有完整覆盖原事件")
    return claims


def _normalise_catalog(catalog: Any) -> list[dict[str, Any]]:
    """复制并校验目录条目，按冻结 ``order`` 恢复实际顺序。"""

    raw_entries = catalog.get("entries") if isinstance(catalog, Mapping) else catalog
    if not isinstance(raw_entries, Sequence) or isinstance(
        raw_entries, (str, bytes, bytearray)
    ):
        raise Z96CoreError("catalog_entries 必须是条目数组或含 entries 的对象")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_orders: set[int] = set()
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, Mapping):
            raise Z96CoreError(f"目录第 {index + 1} 项不是对象")
        anchor_id = raw_entry.get("anchor_id")
        quote = raw_entry.get("quote")
        order_value = raw_entry.get("order")
        if not isinstance(anchor_id, str) or not anchor_id:
            raise Z96CoreError(f"目录第 {index + 1} 项缺非空 anchor_id")
        if anchor_id in seen:
            raise Z96CoreError(f"目录 anchor_id 重复：{anchor_id}")
        if not isinstance(quote, str):
            raise Z96CoreError(f"目录 {anchor_id} 的 quote 不是字符串")
        if (
            not isinstance(order_value, int)
            or isinstance(order_value, bool)
            or order_value < 0
        ):
            raise Z96CoreError(f"目录 {anchor_id} 缺非负整数 order")
        if order_value in seen_orders:
            raise Z96CoreError(f"目录 order 重复：{order_value}")
        seen.add(anchor_id)
        seen_orders.add(order_value)
        entries.append(dict(raw_entry))
    return sorted(entries, key=lambda entry: int(entry["order"]))


def _lexical_features(text: str) -> tuple[set[str], set[str], set[str]]:
    """提取确定性的中文单字/双字和拉丁词特征。"""

    lowered = text.casefold()
    cjk_characters: set[str] = set()
    cjk_bigrams: set[str] = set()
    for match in _CJK_RUN_PATTERN.finditer(lowered):
        run = match.group(0)
        cjk_characters.update(run)
        cjk_bigrams.update(run[index : index + 2] for index in range(len(run) - 1))
    latin_words = set(_LATIN_WORD_PATTERN.findall(lowered))
    return cjk_characters, cjk_bigrams, latin_words


def _lexical_score(left: str, right: str) -> int:
    left_chars, left_bigrams, left_words = _lexical_features(left)
    right_chars, right_bigrams, right_words = _lexical_features(right)
    return (
        len(left_chars & right_chars)
        + 4 * len(left_bigrams & right_bigrams)
        + 3 * len(left_words & right_words)
    )


def recall_anchor_candidates(
    claims: Sequence[Mapping[str, Any]],
    cited_anchor_ids: Sequence[str],
    catalog_entries: Any,
) -> dict[str, Any]:
    """用固定通用规则召回候选锚，不接受也不读取离线答案。

    固定规则为：保留已引锚；目录距离不超过 64 的相邻已引锚之间全收；
    每个已引锚向左右各扩 2 项；每条主张再加入词法分最高的至多 4 锚。
    并列词法分按目录先后打破。返回候选、无答案字段的轨迹和每个连续
    证据岛的选中边缘及岛外左右边界。
    """

    validate_candidate_input(claims)
    validate_candidate_input(cited_anchor_ids)
    validate_candidate_input(catalog_entries)
    entries = _normalise_catalog(catalog_entries)
    order = {
        str(entry["anchor_id"]): index for index, entry in enumerate(entries)
    }

    cited = list(dict.fromkeys(cited_anchor_ids))
    if any(not isinstance(anchor_id, str) or not anchor_id for anchor_id in cited):
        raise Z96CoreError("cited_anchor_ids 必须全部是非空字符串")
    unknown = [anchor_id for anchor_id in cited if anchor_id not in order]
    if unknown:
        raise Z96CoreError(f"已引锚不在目录：{unknown}")

    claim_rows: list[dict[str, Any]] = []
    claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            raise Z96CoreError(f"第 {index + 1} 条主张不是对象")
        claim_id = claim.get("claim_id")
        claim_text = claim.get("claim_text")
        if not isinstance(claim_id, str) or not claim_id:
            raise Z96CoreError(f"第 {index + 1} 条主张缺非空 claim_id")
        if claim_id in claim_ids:
            raise Z96CoreError(f"claim_id 重复：{claim_id}")
        if not isinstance(claim_text, str):
            raise Z96CoreError(f"{claim_id} 的 claim_text 不是字符串")
        claim_ids.add(claim_id)
        claim_rows.append(dict(claim))

    selected_positions: set[int] = {order[anchor_id] for anchor_id in cited}
    trace: list[dict[str, Any]] = [
        {
            "rule": "cited",
            "anchor_ids": sorted(cited, key=order.__getitem__),
        }
    ]

    cited_positions = sorted(selected_positions)
    between_added: set[int] = set()
    for left, right in zip(cited_positions, cited_positions[1:]):
        if right - left <= 64:
            between_added.update(range(left, right + 1))
    selected_positions.update(between_added)
    trace.append(
        {
            "rule": "between_cited_within_64",
            "anchor_ids": [
                str(entries[index]["anchor_id"]) for index in sorted(between_added)
            ],
        }
    )

    nearby_added: set[int] = set()
    for cited_position in cited_positions:
        nearby_added.update(
            range(
                max(0, cited_position - 2),
                min(len(entries), cited_position + 3),
            )
        )
    selected_positions.update(nearby_added)
    trace.append(
        {
            "rule": "cited_plus_minus_2",
            "anchor_ids": [
                str(entries[index]["anchor_id"]) for index in sorted(nearby_added)
            ],
        }
    )

    for claim in claim_rows:
        scored = [
            (_lexical_score(str(claim["claim_text"]), str(entry["quote"])), index)
            for index, entry in enumerate(entries)
        ]
        positive = [(score, index) for score, index in scored if score > 0]
        positive.sort(key=lambda item: (-item[0], item[1]))
        chosen = positive[:4]
        selected_positions.update(index for _, index in chosen)
        trace.append(
            {
                "rule": "claim_lexical_top_4",
                "claim_id": str(claim["claim_id"]),
                "ranked": [
                    {
                        "anchor_id": str(entries[index]["anchor_id"]),
                        "score": score,
                    }
                    for score, index in chosen
                ],
            }
        )

    ordered_positions = sorted(selected_positions)
    candidate_anchor_ids = [
        str(entries[index]["anchor_id"]) for index in ordered_positions
    ]

    evidence_islands: list[dict[str, Any]] = []
    if ordered_positions:
        island_start = ordered_positions[0]
        previous = ordered_positions[0]
        island_ranges: list[tuple[int, int]] = []
        for position in ordered_positions[1:]:
            if position != previous + 1:
                island_ranges.append((island_start, previous))
                island_start = position
            previous = position
        island_ranges.append((island_start, previous))

        for island_number, (left, right) in enumerate(island_ranges, start=1):
            evidence_islands.append(
                {
                    "island_id": f"ISLAND-{island_number:03d}",
                    "anchor_ids": [
                        str(entries[index]["anchor_id"])
                        for index in range(left, right + 1)
                    ],
                    "left_edge_anchor_id": str(entries[left]["anchor_id"]),
                    "right_edge_anchor_id": str(entries[right]["anchor_id"]),
                    "left_boundary_anchor_id": (
                        str(entries[left - 1]["anchor_id"]) if left > 0 else None
                    ),
                    "right_boundary_anchor_id": (
                        str(entries[right + 1]["anchor_id"])
                        if right + 1 < len(entries)
                        else None
                    ),
                    "catalog_start_index": left,
                    "catalog_end_index": right,
                }
            )

    result = {
        "candidate_anchor_ids": candidate_anchor_ids,
        "trace": trace,
        "evidence_islands": evidence_islands,
    }
    validate_candidate_input(result)
    return result


def render_candidate(
    claims: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """把主张和冻结候选锚真正渲染为可审计记录。

    每条记录保留原主张的文本与来源跨度，并显式携带同一份候选锚列表。
    输入会被深拷贝，调用方对象不会被改写。
    """

    validate_candidate_input(claims)
    validate_candidate_input(candidate)
    anchor_ids = candidate.get("candidate_anchor_ids")
    if not isinstance(anchor_ids, Sequence) or isinstance(
        anchor_ids, (str, bytes, bytearray)
    ):
        raise Z96CoreError("candidate 缺 candidate_anchor_ids 数组")
    anchors = list(anchor_ids)
    if (
        any(not isinstance(anchor_id, str) or not anchor_id for anchor_id in anchors)
        or len(anchors) != len(set(anchors))
    ):
        raise Z96CoreError("candidate_anchor_ids 必须是无重复的非空字符串")

    rendered_records: list[dict[str, Any]] = []
    required_claim_keys = (
        "claim_id",
        "claim_text",
        "source_event_id",
        "source_start",
        "source_end",
    )
    for index, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            raise Z96CoreError(f"第 {index + 1} 条主张不是对象")
        if any(key not in claim for key in required_claim_keys):
            raise Z96CoreError(f"第 {index + 1} 条主张缺来源字段")
        rendered_records.append(
            {
                "claim_id": deepcopy(claim["claim_id"]),
                "claim_text": deepcopy(claim["claim_text"]),
                "source_event_id": deepcopy(claim["source_event_id"]),
                "source_start": deepcopy(claim["source_start"]),
                "source_end": deepcopy(claim["source_end"]),
                "anchor_ids": list(anchors),
            }
        )

    return {
        "case_id": deepcopy(candidate.get("case_id")),
        "rendered_records": rendered_records,
        "candidate_anchor_ids": list(anchors),
        "evidence_islands": deepcopy(candidate.get("evidence_islands", [])),
    }


def _records_from_rendered(rendered: Any) -> list[Mapping[str, Any]]:
    if isinstance(rendered, Mapping):
        raw_records = rendered.get("rendered_records", rendered.get("records"))
    else:
        raw_records = rendered
    if not isinstance(raw_records, Sequence) or isinstance(
        raw_records, (str, bytes, bytearray)
    ):
        return []
    return [row for row in raw_records if isinstance(row, Mapping)]


def _expectation_parts(
    expectation: Any,
) -> tuple[
    str | None,
    list[Mapping[str, Any]] | None,
    str | None,
    str | None,
]:
    if isinstance(expectation, str):
        return expectation, None, None, None
    if isinstance(expectation, Mapping):
        source_text = expectation.get("source_text", expectation.get("event_text"))
        if source_text is None:
            source_text = expectation.get("source_event_text")
        raw_records = expectation.get(
            "claims",
            expectation.get("claim_records", expectation.get("records")),
        )
        records = (
            [row for row in raw_records if isinstance(row, Mapping)]
            if isinstance(raw_records, Sequence)
            and not isinstance(raw_records, (str, bytes, bytearray))
            else None
        )
        if source_text is None and records is not None:
            source_text = "".join(str(row.get("claim_text", "")) for row in records)
        case_id = expectation.get("case_id")
        source_sha256 = expectation.get("source_event_sha256")
        return (
            source_text if isinstance(source_text, str) else None,
            records,
            case_id if isinstance(case_id, str) else None,
            source_sha256 if isinstance(source_sha256, str) else None,
        )
    if isinstance(expectation, Sequence) and not isinstance(
        expectation, (str, bytes, bytearray)
    ):
        records = [row for row in expectation if isinstance(row, Mapping)]
        return (
            "".join(str(row.get("claim_text", "")) for row in records),
            records,
            None,
            None,
        )
    return None, None, None, None


def audit_render(rendered: Any, expectation: Any) -> dict[str, Any]:
    """用独立期望审计渲染结果的原文覆盖、无增删和无重复。

    不匹配属于正常审计结果，返回 ``REJECT``；只有无法形成独立原文期望时
    才直接拒绝并给出对应检查结果。
    """

    records = _records_from_rendered(rendered)
    source_text, expected_records, case_id, source_sha256 = _expectation_parts(
        expectation
    )
    malformed_record = len(records) != (
        len(
            rendered.get("rendered_records", rendered.get("records", []))
            if isinstance(rendered, Mapping)
            else rendered
        )
        if isinstance(rendered, (Mapping, Sequence))
        and not isinstance(rendered, (str, bytes, bytearray))
        else 0
    )

    required_keys = {
        "claim_id",
        "claim_text",
        "source_event_id",
        "source_start",
        "source_end",
    }
    structurally_valid = (
        source_text is not None
        and not malformed_record
        and all(required_keys.issubset(record) for record in records)
        and all(
            isinstance(record.get("claim_id"), str)
            and isinstance(record.get("claim_text"), str)
            and isinstance(record.get("source_event_id"), str)
            and isinstance(record.get("source_start"), int)
            and not isinstance(record.get("source_start"), bool)
            and isinstance(record.get("source_end"), int)
            and not isinstance(record.get("source_end"), bool)
            for record in records
        )
    )

    claim_ids = [str(record.get("claim_id", "")) for record in records]
    spans = [
        (
            record.get("source_event_id"),
            record.get("source_start"),
            record.get("source_end"),
        )
        for record in records
    ]
    no_duplicates = (
        structurally_valid
        and len(claim_ids) == len(set(claim_ids))
        and len(spans) == len(set(spans))
    )
    source_hash_matches = (
        source_text is not None
        and (
            source_sha256 is None
            or sha256_bytes(source_text.encode("utf-8")) == source_sha256
        )
    )
    source_event_matches = case_id is None or (
        bool(records)
        and all(record.get("source_event_id") == case_id for record in records)
    )

    source_covered = structurally_valid
    cursor = 0
    if source_covered:
        for record in records:
            start = int(record["source_start"])
            end = int(record["source_end"])
            if (
                start != cursor
                or end <= start
                or end > len(source_text)
                or record["claim_text"] != source_text[start:end]
            ):
                source_covered = False
                break
            cursor = end
        source_covered = source_covered and cursor == len(source_text)
        if source_text == "" and not records:
            source_covered = True

    rendered_text = (
        "".join(str(record.get("claim_text", "")) for record in records)
        if structurally_valid
        else ""
    )
    no_additions = structurally_valid and rendered_text == source_text
    no_deletions = structurally_valid and rendered_text == source_text

    identity_matches = True
    if expected_records is not None:
        expected_signatures = [
            tuple(
                row.get(key)
                for key in (
                    "claim_id",
                    "claim_text",
                    "source_event_id",
                    "source_start",
                    "source_end",
                )
            )
            for row in expected_records
        ]
        rendered_signatures = [
            tuple(
                row.get(key)
                for key in (
                    "claim_id",
                    "claim_text",
                    "source_event_id",
                    "source_start",
                    "source_end",
                )
            )
            for row in records
        ]
        identity_matches = rendered_signatures == expected_signatures
        no_additions = no_additions and len(rendered_signatures) <= len(
            expected_signatures
        )
        no_deletions = no_deletions and len(rendered_signatures) >= len(
            expected_signatures
        )

    checks = {
        "source_event_sha256_matches": source_hash_matches,
        "source_event_id_matches_case": source_event_matches,
        "source_text_fully_covered": source_covered,
        "no_additions": no_additions,
        "no_deletions": no_deletions,
        "no_duplicates": no_duplicates,
        "record_identity_matches": identity_matches,
    }
    passed = all(checks.values())
    return {
        "status": "PASS" if passed else "REJECT",
        "checks": checks,
    }


def _candidate_ids(candidate: Any) -> list[str]:
    raw_ids = (
        candidate.get("candidate_anchor_ids")
        if isinstance(candidate, Mapping)
        else candidate
    )
    if not isinstance(raw_ids, Sequence) or isinstance(
        raw_ids, (str, bytes, bytearray)
    ):
        raise Z96CoreError("candidate 缺候选锚数组")
    result = list(raw_ids)
    if (
        any(not isinstance(anchor_id, str) or not anchor_id for anchor_id in result)
        or len(result) != len(set(result))
    ):
        raise Z96CoreError("候选锚必须是无重复的非空字符串")
    return result


def _answer_catalog_order(
    answer: Mapping[str, Any],
    candidate: Any,
) -> list[str]:
    for key in ("ordered_anchor_ids", "catalog_anchor_ids"):
        raw_ids = answer.get(key)
        if isinstance(raw_ids, Sequence) and not isinstance(
            raw_ids, (str, bytes, bytearray)
        ):
            ids = list(raw_ids)
            if all(isinstance(anchor_id, str) and anchor_id for anchor_id in ids):
                return ids
    raw_catalog = answer.get("catalog_entries", answer.get("anchor_catalog"))
    if raw_catalog is not None:
        return [
            str(entry["anchor_id"]) for entry in _normalise_catalog(raw_catalog)
        ]
    raw_occurrences = answer.get("occurrences")
    if isinstance(raw_occurrences, Sequence) and not isinstance(
        raw_occurrences, (str, bytes, bytearray)
    ):
        if all(isinstance(item, str) and item for item in raw_occurrences):
            return list(raw_occurrences)
        occurrence_rows: list[tuple[int, str]] = []
        for index, item in enumerate(raw_occurrences):
            if not isinstance(item, Mapping):
                raise Z96CoreError(f"occurrences 第 {index + 1} 项格式不合法")
            anchor_id = item.get("anchor_id")
            order_value = item.get("order")
            if (
                not isinstance(anchor_id, str)
                or not anchor_id
                or not isinstance(order_value, int)
                or isinstance(order_value, bool)
            ):
                raise Z96CoreError(
                    f"occurrences 第 {index + 1} 项缺 anchor_id/order"
                )
            occurrence_rows.append((order_value, anchor_id))
        occurrence_rows.sort()
        return [anchor_id for _, anchor_id in occurrence_rows]
    if isinstance(candidate, Mapping):
        raw_candidate_order = candidate.get("catalog_order")
        if isinstance(raw_candidate_order, Sequence) and not isinstance(
            raw_candidate_order, (str, bytes, bytearray)
        ):
            candidate_order = list(raw_candidate_order)
            if all(
                isinstance(anchor_id, str) and anchor_id
                for anchor_id in candidate_order
            ):
                return candidate_order
    raise Z96CoreError("answer 缺按实际目录顺序排列的锚或 occurrences")


def score_recall(candidate: Any, answer: Mapping[str, Any]) -> dict[str, Any]:
    """只读冻结候选和独立答案，计算必要锚召回与首尾挂锚模式。

    函数不会把漏召锚补进候选。首尾模式严格按答案携带的实际目录顺序
    判断，而不是按锚 ID 的数字大小猜测。
    """

    validate_candidate_input(candidate)
    if not isinstance(answer, Mapping):
        raise Z96CoreError("answer 必须是对象")
    candidate_ids = _candidate_ids(candidate)
    raw_required = answer.get("required_anchor_ids")
    if not isinstance(raw_required, Sequence) or isinstance(
        raw_required, (str, bytes, bytearray)
    ):
        raise Z96CoreError("answer 缺 required_anchor_ids 数组")
    required_ids = list(raw_required)
    if (
        not required_ids
        or any(
            not isinstance(anchor_id, str) or not anchor_id
            for anchor_id in required_ids
        )
        or len(required_ids) != len(set(required_ids))
    ):
        raise Z96CoreError("必需锚必须是非空、无重复的字符串数组")

    catalog_order = _answer_catalog_order(answer, candidate)
    if len(catalog_order) != len(set(catalog_order)):
        raise Z96CoreError("答案目录锚有重复")
    order = {anchor_id: index for index, anchor_id in enumerate(catalog_order)}
    unknown_required = [
        anchor_id for anchor_id in required_ids if anchor_id not in order
    ]
    unknown_candidates = [
        anchor_id for anchor_id in candidate_ids if anchor_id not in order
    ]
    if unknown_required:
        raise Z96CoreError(f"必需锚不在答案目录：{unknown_required}")
    if unknown_candidates:
        raise Z96CoreError(f"候选锚不在答案目录：{unknown_candidates}")

    selected = set(candidate_ids)
    ordered_required = sorted(required_ids, key=order.__getitem__)
    recalled = [
        anchor_id for anchor_id in ordered_required if anchor_id in selected
    ]
    unrecalled = [
        anchor_id for anchor_id in ordered_required if anchor_id not in selected
    ]

    endpoint_pattern = False
    if len(ordered_required) >= 3:
        interior = ordered_required[1:-1]
        endpoint_pattern = (
            ordered_required[0] in selected
            and ordered_required[-1] in selected
            and any(anchor_id not in selected for anchor_id in interior)
        )

    recall = len(recalled) / len(ordered_required)
    return {
        "case_id": (
            candidate.get("case_id")
            if isinstance(candidate, Mapping)
            else answer.get("case_id")
        ),
        "status": "PASS" if not unrecalled else "REJECT",
        "required_anchor_ids": ordered_required,
        "recalled_required_anchor_ids": recalled,
        "unrecalled_required_anchor_ids": unrecalled,
        "required_anchor_recall": recall,
        "endpoint_span_pattern": endpoint_pattern,
        "candidate_anchor_ids": list(candidate_ids),
    }


def apply_empirical_token_upper_bound(
    model_visible: Any,
    tokens_per_nonblank_char_upper_bound: float,
    *,
    fixed_margin_tokens: int = 0,
) -> dict[str, Any]:
    """统计非空白字符，按经验斜率向上取整后加固定 token 余量。"""

    rate = tokens_per_nonblank_char_upper_bound
    if (
        isinstance(rate, bool)
        or not isinstance(rate, (int, float))
        or not math.isfinite(float(rate))
        or float(rate) <= 0
    ):
        raise Z96CoreError("每非空白字符 token 上界必须是正的有限数")
    if (
        not isinstance(fixed_margin_tokens, int)
        or isinstance(fixed_margin_tokens, bool)
        or fixed_margin_tokens < 0
    ):
        raise Z96CoreError("固定 token 余量必须是非负整数")
    if isinstance(model_visible, str):
        text = model_visible
    else:
        text = json.dumps(
            model_visible,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    nonblank_character_count = sum(1 for character in text if not character.isspace())
    token_upper_bound = math.ceil(
        nonblank_character_count * float(tokens_per_nonblank_char_upper_bound)
    ) + fixed_margin_tokens
    return {
        "nonblank_character_count": nonblank_character_count,
        "tokens_per_nonblank_char_upper_bound": float(
            tokens_per_nonblank_char_upper_bound
        ),
        "fixed_margin_tokens": fixed_margin_tokens,
        "token_upper_bound": token_upper_bound,
    }

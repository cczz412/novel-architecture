"""M8 独立零 API 工具：作者目的＋C4 v1 当前事实 → C7 v1 只读快照。

``execute`` 只处理内存对象。文件路径只存在于末尾的
``LOCAL_FILESYSTEM_ONLY`` 适配层。``planning_provider`` 是唯一规划供应器替换缝；
本文件提供的离线实现只查冻结响应映射，不调用模型，也不写任何账。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, NoReturn


if __package__:
    from . import factstore
else:  # 允许直接运行 ``python novel-mvp/mvp/plan_tool.py``。
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import factstore


MODEL_PROVIDER_SWAP_POINT = "planning_provider"
C7_CONTRACT = "C7_PLOT_LAYER v1"
REQUEST_KEYS = frozenset(
    {
        "project",
        "generated_at",
        "purpose",
        "purpose_note",
        "mode",
        "chapter_intent",
        "current_chapter_revision_ref",
        "facts",
        "planning_card_ref",
        "planning_card_rev",
    }
)
PROVIDER_RESULT_KEYS = frozenset({"data", "usage", "model"})
PROVIDER_DATA_KEYS = frozenset({"cards", "conflicts"})
ZERO_USAGE_KEYS = frozenset({"api_calls", "model_calls", "retries"})
C7_KEYS = frozenset(
    {
        "contract",
        "project",
        "generated_at",
        "model",
        "purpose",
        "purpose_note",
        "mode",
        "purpose_placement",
        "chapter_intent",
        "confirmed_fact_ids",
        "cards",
        "conflicts",
    }
)
CARD_KEYS = frozenset(
    {
        "id",
        "role",
        "title",
        "purpose_note",
        "options",
        "recommended_option_ref",
        "planning_card_ref",
        "planning_card_rev",
        "guidance",
    }
)
OPTION_KEYS = frozenset({"id", "label", "reveal_intent"})
GUIDANCE_KEYS = frozenset(
    {"card_problem", "dialogue_reveal", "plugin_craft"}
)
CONFLICT_KEYS = frozenset({"kind", "fact_id", "fact_text", "why", "ask"})
REVISION_REF_KEYS = frozenset(
    {"chapter_id", "revision_no", "revision_text_sha256"}
)
FACT_EXCLUSION_KEYS = (
    "stale_revision",
    "extracted",
    "rejected",
    "needs_recheck",
    "invalid_anchor",
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
CHAPTER_ID_RE = re.compile(r"c[0-9]+\Z")
FACT_ID_RE = re.compile(r"f[0-9]{3,}\Z")
LOCAL_CARD_ID_RE = re.compile(r"card[0-9]{2,}\Z")
PLANNING_CARD_REF_RE = re.compile(
    r"(?:AC-[0-9]{4,}|SB-[0-9]{4,}#d-ac-[0-9]+)\Z"
)


class PlanToolError(RuntimeError):
    """C7 v1 批次在完整形成前失败关闭。"""


PlanningProvider = Callable[[dict[str, Any]], dict[str, Any]]


def _fail(code: str, detail: str = "") -> NoReturn:
    raise PlanToolError(f"{code}:{detail}" if detail else code)


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], path: str) -> None:
    missing = sorted(expected - value.keys())
    extra = sorted(value.keys() - expected)
    if missing:
        _fail("MISSING_FIELDS", f"{path}:{','.join(missing)}")
    if extra:
        _fail("EXTRA_FIELDS", f"{path}:{','.join(extra)}")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("OBJECT_REQUIRED", path)
    return value


def _array(value: Any, path: str, *, nonempty: bool = False) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        _fail("ARRAY_INVALID", path)
    return value


def _text(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        _fail("STRING_REQUIRED", path)
    if value != value.strip():
        _fail("STRING_NOT_CANONICAL", path)
    if not allow_empty and not value:
        _fail("STRING_EMPTY", path)
    return value


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail("POSITIVE_INTEGER_REQUIRED", path)
    return value


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PlanToolError("VALUE_NOT_JSON_SERIALIZABLE") from exc


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _validate_revision_ref(value: Any, path: str) -> dict[str, Any]:
    ref = _mapping(value, path)
    _exact_fields(ref, REVISION_REF_KEYS, path)
    chapter_id = _text(ref.get("chapter_id"), f"{path}.chapter_id")
    if CHAPTER_ID_RE.fullmatch(chapter_id) is None:
        _fail("CHAPTER_ID_INVALID", path)
    _positive_int(ref.get("revision_no"), f"{path}.revision_no")
    revision_sha = _text(
        ref.get("revision_text_sha256"), f"{path}.revision_text_sha256"
    )
    if SHA256_RE.fullmatch(revision_sha) is None:
        _fail("REVISION_SHA_INVALID", path)
    return copy.deepcopy(ref)


def _anchor_is_current_and_valid(
    fact: dict[str, Any], current_ref: dict[str, Any]
) -> bool:
    if fact.get("anchor_state") != "VERIFIED" or fact.get("recheck") is not None:
        return False
    quote = fact.get("quote")
    anchor = fact.get("anchor_ref")
    if not isinstance(quote, str) or not quote or not isinstance(anchor, dict):
        return False
    if fact.get("chapter_revision_ref") != current_ref:
        return False
    if any(anchor.get(key) != current_ref[key] for key in REVISION_REF_KEYS):
        return False
    start = anchor.get("start")
    end = anchor.get("end")
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(end, bool)
        or not isinstance(end, int)
        or start < 0
        or end <= start
        or end - start != len(quote)
    ):
        return False
    return anchor.get("slice_sha256") == hashlib.sha256(
        quote.encode("utf-8")
    ).hexdigest()


def _filter_current_confirmed_facts(
    value: Any, current_ref: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_facts = _array(value, "facts")
    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_fact in enumerate(raw_facts):
        try:
            fact = copy.deepcopy(
                factstore._validate_c11_object(raw_fact, "C4_FACT_QUERY")
            )
        except factstore.FactstoreError as exc:
            raise PlanToolError(f"C4_FACT_INVALID:{index}:{exc}") from exc
        fact_id = fact["id"]
        if fact_id in seen_ids:
            _fail("C4_FACT_ID_DUPLICATE", fact_id)
        seen_ids.add(fact_id)
        validated.append(fact)

    counts = {key: 0 for key in FACT_EXCLUSION_KEYS}
    eligible: list[dict[str, Any]] = []
    for fact in validated:
        if fact["chapter_revision_ref"] != current_ref:
            counts["stale_revision"] += 1
            continue
        status = fact["status"]
        if status != factstore.STATUS_CONFIRMED:
            if status not in {"extracted", "rejected", "needs_recheck"}:
                _fail("C4_STATUS_UNSUPPORTED", status)
            counts[status] += 1
            continue
        if not _anchor_is_current_and_valid(fact, current_ref):
            counts["invalid_anchor"] += 1
            continue
        eligible.append(fact)

    return eligible, {
        "input_count": len(validated),
        "included_count": len(eligible),
        "excluded_count": len(validated) - len(eligible),
        "excluded_by_reason": counts,
    }


def _validate_request(
    request: object,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = _mapping(request, "request")
    _exact_fields(source, REQUEST_KEYS, "request")
    project = _text(source.get("project"), "project")
    generated_at = _text(source.get("generated_at"), "generated_at")
    purpose = _text(source.get("purpose"), "purpose")
    purpose_note = _text(
        source.get("purpose_note"), "purpose_note", allow_empty=True
    )
    mode = _text(source.get("mode"), "mode")
    if mode not in {"forward", "reverse"}:
        _fail("MODE_INVALID", mode)
    chapter_intent = _text(
        source.get("chapter_intent"), "chapter_intent", allow_empty=True
    )
    current_ref = _validate_revision_ref(
        source.get("current_chapter_revision_ref"),
        "current_chapter_revision_ref",
    )
    planning_card_ref = _text(
        source.get("planning_card_ref"), "planning_card_ref"
    )
    if PLANNING_CARD_REF_RE.fullmatch(planning_card_ref) is None:
        _fail("PLANNING_CARD_REF_INVALID", planning_card_ref)
    planning_card_rev = _positive_int(
        source.get("planning_card_rev"), "planning_card_rev"
    )
    eligible, receipt = _filter_current_confirmed_facts(
        source.get("facts"), current_ref
    )
    normalized = {
        "project": project,
        "generated_at": generated_at,
        "purpose": purpose,
        "purpose_note": purpose_note,
        "mode": mode,
        "purpose_placement": "attach" if purpose_note else "standalone",
        "chapter_intent": chapter_intent,
        "current_chapter_revision_ref": current_ref,
        "confirmed_facts": eligible,
        "planning_card_ref": planning_card_ref,
        "planning_card_rev": planning_card_rev,
    }
    provider_context = {
        key: copy.deepcopy(value)
        for key, value in normalized.items()
        if key != "generated_at"
    }
    return normalized, provider_context, receipt


def planning_provider_key(request: dict[str, Any]) -> str:
    """返回离线响应映射使用的精确上下文键；不读取文件、不调用供应器。"""
    _, provider_context, receipt = _validate_request(request)
    return _sha256(
        {"planning_context": provider_context, "fact_filter_receipt": receipt}
    )


def _validate_option(value: Any, path: str) -> dict[str, Any]:
    option = _mapping(value, path)
    _exact_fields(option, OPTION_KEYS, path)
    option_id = _text(option.get("id"), f"{path}.id")
    if option_id not in {"A", "B", "C"}:
        _fail("OPTION_ID_INVALID", f"{path}:{option_id}")
    return {
        "id": option_id,
        "label": _text(option.get("label"), f"{path}.label"),
        "reveal_intent": _text(
            option.get("reveal_intent"), f"{path}.reveal_intent"
        ),
    }


def _validate_card(value: Any, path: str) -> dict[str, Any]:
    card = _mapping(value, path)
    _exact_fields(card, CARD_KEYS, path)
    card_id = _text(card.get("id"), f"{path}.id")
    if LOCAL_CARD_ID_RE.fullmatch(card_id) is None:
        _fail("LOCAL_CARD_ID_INVALID", card_id)
    role = _text(card.get("role"), f"{path}.role")
    if role not in {"purpose", "prerequisite", "attach"}:
        _fail("CARD_ROLE_INVALID", role)
    options = [
        _validate_option(raw, f"{path}.options[{index}]")
        for index, raw in enumerate(_array(card.get("options"), f"{path}.options", nonempty=True))
    ]
    option_ids = [item["id"] for item in options]
    if len(option_ids) != len(set(option_ids)):
        _fail("OPTION_ID_DUPLICATE", card_id)
    recommended = _text(
        card.get("recommended_option_ref"), f"{path}.recommended_option_ref"
    )
    if recommended not in option_ids:
        _fail("RECOMMENDED_OPTION_NOT_FOUND", f"{card_id}:{recommended}")
    planning_card_ref = _text(
        card.get("planning_card_ref"), f"{path}.planning_card_ref"
    )
    if PLANNING_CARD_REF_RE.fullmatch(planning_card_ref) is None:
        _fail("PLANNING_CARD_REF_INVALID", planning_card_ref)
    planning_card_rev = _positive_int(
        card.get("planning_card_rev"), f"{path}.planning_card_rev"
    )
    guidance = _mapping(card.get("guidance"), f"{path}.guidance")
    _exact_fields(guidance, GUIDANCE_KEYS, f"{path}.guidance")
    plugin_craft = _text(
        guidance.get("plugin_craft"),
        f"{path}.guidance.plugin_craft",
        allow_empty=True,
    )
    if plugin_craft:
        _fail("PLUGIN_CRAFT_MUST_BE_EMPTY", card_id)
    return {
        "id": card_id,
        "role": role,
        "title": _text(card.get("title"), f"{path}.title"),
        "purpose_note": _text(
            card.get("purpose_note"), f"{path}.purpose_note", allow_empty=True
        ),
        "options": options,
        "recommended_option_ref": recommended,
        "planning_card_ref": planning_card_ref,
        "planning_card_rev": planning_card_rev,
        "guidance": {
            "card_problem": _text(
                guidance.get("card_problem"), f"{path}.guidance.card_problem"
            ),
            "dialogue_reveal": _text(
                guidance.get("dialogue_reveal"),
                f"{path}.guidance.dialogue_reveal",
            ),
            "plugin_craft": plugin_craft,
        },
    }


def _validate_conflict(value: Any, path: str) -> dict[str, Any]:
    conflict = _mapping(value, path)
    _exact_fields(conflict, CONFLICT_KEYS, path)
    kind = _text(conflict.get("kind"), f"{path}.kind")
    if kind not in {"fact", "intent"}:
        _fail("CONFLICT_KIND_INVALID", kind)
    fact_id = _text(
        conflict.get("fact_id"), f"{path}.fact_id", allow_empty=kind == "intent"
    )
    if kind == "fact" and FACT_ID_RE.fullmatch(fact_id) is None:
        _fail("CONFLICT_FACT_ID_INVALID", fact_id)
    if kind == "intent" and fact_id:
        _fail("INTENT_CONFLICT_FACT_ID_MUST_BE_EMPTY", fact_id)
    ask = _text(conflict.get("ask"), f"{path}.ask")
    expected_ask = (
        "改目的，还是改已确认事实？"
        if kind == "fact"
        else "改目的，还是改本章原意图？"
    )
    if ask != expected_ask:
        _fail("CONFLICT_ASK_INVALID", path)
    return {
        "kind": kind,
        "fact_id": fact_id,
        "fact_text": _text(conflict.get("fact_text"), f"{path}.fact_text"),
        "why": _text(conflict.get("why"), f"{path}.why"),
        "ask": ask,
    }


def validate_c7_v1(value: Any) -> dict[str, Any]:
    """按 C7 正式字段表和内嵌合法示例严格校验一份只读快照。"""
    snapshot = _mapping(value, "c7")
    _exact_fields(snapshot, C7_KEYS, "c7")
    if snapshot.get("contract") != C7_CONTRACT:
        _fail("C7_IDENTITY_INVALID")
    project = _text(snapshot.get("project"), "c7.project")
    generated_at = _text(snapshot.get("generated_at"), "c7.generated_at")
    model = _text(snapshot.get("model"), "c7.model")
    purpose = _text(snapshot.get("purpose"), "c7.purpose")
    purpose_note = _text(
        snapshot.get("purpose_note"), "c7.purpose_note", allow_empty=True
    )
    mode = _text(snapshot.get("mode"), "c7.mode")
    if mode not in {"forward", "reverse"}:
        _fail("MODE_INVALID", mode)
    placement = _text(snapshot.get("purpose_placement"), "c7.purpose_placement")
    if placement not in {"standalone", "attach"}:
        _fail("PURPOSE_PLACEMENT_INVALID", placement)
    if placement != ("attach" if purpose_note else "standalone"):
        _fail("PURPOSE_PLACEMENT_NOTE_MISMATCH")
    chapter_intent = _text(
        snapshot.get("chapter_intent"), "c7.chapter_intent", allow_empty=True
    )
    confirmed_ids = [
        _text(item, f"c7.confirmed_fact_ids[{index}]")
        for index, item in enumerate(
            _array(snapshot.get("confirmed_fact_ids"), "c7.confirmed_fact_ids")
        )
    ]
    if any(FACT_ID_RE.fullmatch(item) is None for item in confirmed_ids):
        _fail("CONFIRMED_FACT_ID_INVALID")
    if len(confirmed_ids) != len(set(confirmed_ids)):
        _fail("CONFIRMED_FACT_ID_DUPLICATE")
    cards = [
        _validate_card(raw, f"c7.cards[{index}]")
        for index, raw in enumerate(
            _array(snapshot.get("cards"), "c7.cards", nonempty=True)
        )
    ]
    card_ids = [card["id"] for card in cards]
    if len(card_ids) != len(set(card_ids)):
        _fail("LOCAL_CARD_ID_DUPLICATE")
    if mode == "reverse" and cards[0]["role"] != "prerequisite":
        _fail("REVERSE_PREREQUISITE_MUST_BE_FIRST")
    conflicts = [
        _validate_conflict(raw, f"c7.conflicts[{index}]")
        for index, raw in enumerate(
            _array(snapshot.get("conflicts"), "c7.conflicts")
        )
    ]
    return {
        "contract": C7_CONTRACT,
        "project": project,
        "generated_at": generated_at,
        "model": model,
        "purpose": purpose,
        "purpose_note": purpose_note,
        "mode": mode,
        "purpose_placement": placement,
        "chapter_intent": chapter_intent,
        "confirmed_fact_ids": confirmed_ids,
        "cards": cards,
        "conflicts": conflicts,
    }


def _c7_snapshot_bytes(snapshot: dict[str, Any]) -> bytes:
    """UTF-8、键排序、紧凑 JSON，并以一个 LF 结束。"""
    return (
        json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def c7_snapshot_sha256(value: Any) -> str:
    """完整校验 C7 后返回稳定快照 SHA；不修改原对象。"""
    snapshot = validate_c7_v1(value)
    return hashlib.sha256(_c7_snapshot_bytes(snapshot)).hexdigest()


def _c7_snapshot_identity(value: Any) -> dict[str, Any]:
    snapshot = validate_c7_v1(value)
    return {
        "contract": snapshot["contract"],
        "project": snapshot["project"],
        "card_local_ids": [card["id"] for card in snapshot["cards"]],
        "source_c7_snapshot_sha256": hashlib.sha256(
            _c7_snapshot_bytes(snapshot)
        ).hexdigest(),
    }


def render_c7_v1(value: Any) -> str:
    """把一份已严格校验的 C7 v1 稳定排成人读选择卡，不产生选择。"""
    snapshot = validate_c7_v1(value)
    mode_labels = {"forward": "顺向", "reverse": "逆向"}
    role_labels = {
        "purpose": "目的卡",
        "prerequisite": "前置条件卡",
        "attach": "附加卡",
    }
    lines = [
        "M8 计划选择卡",
        f"项目：{snapshot['project']}",
        f"目的：{snapshot['purpose']}",
        f"目的说明：{snapshot['purpose_note'] or '（无）'}",
        f"规划模式：{snapshot['mode']}（{mode_labels[snapshot['mode']]}）",
        f"章节意图：{snapshot['chapter_intent'] or '（无）'}",
        f"确认事实 ID：{', '.join(snapshot['confirmed_fact_ids']) or '（无）'}",
        f"provider 身份：{snapshot['model']}",
        "",
    ]
    if snapshot["mode"] == "reverse":
        role_order = " → ".join(card["role"] for card in snapshot["cards"])
        lines.extend(
            [
                f"逆向卡片处理顺序：{role_order}",
                "顺序说明：先处理 prerequisite，再处理后续 attach。",
                "",
            ]
        )

    lines.append(f"候选卡片：{len(snapshot['cards'])} 张")
    for index, card in enumerate(snapshot["cards"], start=1):
        lines.extend(
            [
                "",
                f"[{index}] {card['title']}（{card['id']}）",
                f"角色：{card['role']}（{role_labels[card['role']]}）",
                (
                    "规划卡版本："
                    f"{card['planning_card_ref']} / rev {card['planning_card_rev']}"
                ),
                f"卡片说明：{card['purpose_note'] or '（无）'}",
                f"卡片问题：{card['guidance']['card_problem']}",
                "选项：",
            ]
        )
        for option in card["options"]:
            recommendation = (
                " [推荐参考；作者尚未选择]"
                if option["id"] == card["recommended_option_ref"]
                else ""
            )
            lines.extend(
                [
                    f"- {option['id']}：{option['label']}{recommendation}",
                    f"  揭示意图：{option['reveal_intent']}",
                ]
            )
        lines.extend(
            [
                "三类指导：",
                f"- 卡片问题：{card['guidance']['card_problem']}",
                f"- 对话揭示：{card['guidance']['dialogue_reveal']}",
                f"- 插件技法：{card['guidance']['plugin_craft'] or '（空）'}",
            ]
        )

    lines.extend(["", f"冲突：{len(snapshot['conflicts'])} 条"])
    if not snapshot["conflicts"]:
        lines.append("（无）")
    else:
        for index, conflict in enumerate(snapshot["conflicts"], start=1):
            lines.extend(
                [
                    f"[{index}] 类型：{conflict['kind']}",
                    f"关联事实 ID：{conflict['fact_id'] or '（无）'}",
                    f"事实或意图：{conflict['fact_text']}",
                    f"冲突原因：{conflict['why']}",
                    f"需要问作者：{conflict['ask']}",
                ]
            )
    return "\n".join(lines) + "\n"


def _validate_provider_result(value: Any) -> dict[str, Any]:
    result = _mapping(value, "provider_result")
    _exact_fields(result, PROVIDER_RESULT_KEYS, "provider_result")
    model = _text(result.get("model"), "provider_result.model")
    usage = _mapping(result.get("usage"), "provider_result.usage")
    _exact_fields(usage, ZERO_USAGE_KEYS, "provider_result.usage")
    for key in sorted(ZERO_USAGE_KEYS):
        amount = usage.get(key)
        if isinstance(amount, bool) or not isinstance(amount, int) or amount != 0:
            _fail("OFFLINE_USAGE_MUST_BE_ZERO", key)
    data = _mapping(result.get("data"), "provider_result.data")
    _exact_fields(data, PROVIDER_DATA_KEYS, "provider_result.data")
    if not isinstance(data.get("cards"), list):
        _fail("PROVIDER_CARDS_NOT_ARRAY")
    if not isinstance(data.get("conflicts"), list):
        _fail("PROVIDER_CONFLICTS_NOT_ARRAY")
    return {
        "model": model,
        "data": copy.deepcopy(data),
        "usage": copy.deepcopy(usage),
    }


def execute(request: dict, planning_provider: PlanningProvider) -> dict:
    """把一个明确目的和当前 C4 事实批次变成一份完整 C7 v1 快照。"""
    if not callable(planning_provider):
        _fail("PLANNING_PROVIDER_NOT_CALLABLE")
    normalized, provider_context, receipt = _validate_request(request)
    provider_key = _sha256(
        {"planning_context": provider_context, "fact_filter_receipt": receipt}
    )
    provider_request = {
        "provider_key": provider_key,
        "planning_context": copy.deepcopy(provider_context),
        "fact_filter_receipt": copy.deepcopy(receipt),
    }
    provider_result = _validate_provider_result(planning_provider(provider_request))
    eligible_facts = provider_context["confirmed_facts"]
    snapshot = validate_c7_v1(
        {
            "contract": C7_CONTRACT,
            "project": normalized["project"],
            "generated_at": normalized["generated_at"],
            "model": provider_result["model"],
            "purpose": normalized["purpose"],
            "purpose_note": normalized["purpose_note"],
            "mode": normalized["mode"],
            "purpose_placement": normalized["purpose_placement"],
            "chapter_intent": normalized["chapter_intent"],
            "confirmed_fact_ids": [fact["id"] for fact in eligible_facts],
            "cards": provider_result["data"]["cards"],
            "conflicts": provider_result["data"]["conflicts"],
        }
    )

    expected_ref = normalized["planning_card_ref"]
    expected_rev = normalized["planning_card_rev"]
    for card in snapshot["cards"]:
        if card["planning_card_ref"] != expected_ref:
            _fail("PLANNING_CARD_REF_DRIFT", card["id"])
        if card["planning_card_rev"] != expected_rev:
            _fail("PLANNING_CARD_REV_DRIFT", card["id"])

    eligible_by_id = {fact["id"]: fact for fact in eligible_facts}
    for conflict in snapshot["conflicts"]:
        if conflict["kind"] == "fact":
            fact = eligible_by_id.get(conflict["fact_id"])
            if fact is None:
                _fail("CONFLICT_FACT_NOT_IN_CURRENT_CONTEXT", conflict["fact_id"])
            if conflict["fact_text"] != fact["text"]:
                _fail("CONFLICT_FACT_TEXT_DRIFT", conflict["fact_id"])
        elif (
            not normalized["chapter_intent"]
            or conflict["fact_text"] != normalized["chapter_intent"]
        ):
            _fail("CONFLICT_INTENT_TEXT_DRIFT")
    return snapshot


def offline_planning_provider(responses: object) -> PlanningProvider:
    """用冻结映射替代模型；只认精确上下文 SHA，缺项时失败关闭。"""
    if not isinstance(responses, dict):
        _fail("RESPONSES_MAPPING_NOT_OBJECT")
    frozen = copy.deepcopy(responses)
    if any(not isinstance(key, str) or SHA256_RE.fullmatch(key) is None for key in frozen):
        _fail("RESPONSES_MAPPING_KEY_INVALID")

    def provide(provider_request: dict[str, Any]) -> dict[str, Any]:
        key = provider_request["provider_key"]
        if key not in frozen:
            _fail("OFFLINE_RESPONSE_MISSING", key)
        return copy.deepcopy(frozen[key])

    return provide


# LOCAL_FILESYSTEM_ONLY：只把三个本地 JSON 文件接到纯对象 execute。
def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        _fail(f"{label}_PATH_NOT_FILE", str(path))
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlanToolError(f"{label}_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail(f"{label}_OBJECT_REQUIRED")
    return value


def _output_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    if not path.parent.is_dir():
        _fail("OUTPUT_PARENT_NOT_DIRECTORY", str(path.parent))
    if path.exists() and not path.is_file():
        _fail("OUTPUT_PATH_NOT_FILE", str(path))
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(_output_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_text_atomic(path: Path, value: str) -> None:
    if not path.parent.is_dir():
        _fail("OUTPUT_PARENT_NOT_DIRECTORY", str(path.parent))
    if path.exists() and not path.is_file():
        _fail("OUTPUT_PATH_NOT_FILE", str(path))
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(value.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _local_file(raw: str, label: str) -> Path:
    if raw == "-":
        _fail(f"{label}_MUST_BE_LOCAL_FILE")
    return Path(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M8 LOCAL_FILESYSTEM_ONLY C7 v1 冻结响应工具"
    )
    parser.add_argument("--input", required=True, help="作者目的和 C4 v1 输入 JSON")
    parser.add_argument("--responses", help="默认 JSON 模式使用的冻结规划响应映射")
    parser.add_argument(
        "--output",
        required=True,
        help="本地输出文件；render/identity 模式可用 -",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--render",
        action="store_true",
        help="把现有 C7 v1 JSON 排成人读计划选择卡",
    )
    mode.add_argument(
        "--identity",
        action="store_true",
        help="输出 C7 快照 SHA 的四字段 transport helper JSON",
    )
    args = parser.parse_args(argv)
    try:
        if args.render or args.identity:
            if args.responses is not None:
                _fail(
                    "RENDER_RESPONSES_NOT_ALLOWED"
                    if args.render
                    else "IDENTITY_RESPONSES_NOT_ALLOWED"
                )
            if args.input == "-":
                try:
                    c7_value = json.load(sys.stdin)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise PlanToolError("INPUT_JSON_INVALID") from exc
            else:
                c7_value = _read_json_object(Path(args.input), "INPUT")
            if args.render:
                rendered = render_c7_v1(c7_value)
                if args.output == "-":
                    sys.stdout.buffer.write(rendered.encode("utf-8"))
                    sys.stdout.buffer.flush()
                else:
                    _write_text_atomic(Path(args.output), rendered)
            else:
                identity = _c7_snapshot_identity(c7_value)
                if args.output == "-":
                    sys.stdout.buffer.write(_output_bytes(identity))
                    sys.stdout.buffer.flush()
                else:
                    _write_atomic(Path(args.output), identity)
        else:
            if args.responses is None:
                _fail("RESPONSES_REQUIRED")
            input_path = _local_file(args.input, "INPUT")
            responses_path = _local_file(args.responses, "RESPONSES")
            output_path = _local_file(args.output, "OUTPUT")
            resolved = {
                input_path.resolve(),
                responses_path.resolve(),
                output_path.resolve(),
            }
            if len(resolved) != 3:
                _fail("LOCAL_FILE_PATHS_MUST_DIFFER")
            request = _read_json_object(input_path, "INPUT")
            responses = _read_json_object(responses_path, "RESPONSES")
            result = execute(request, offline_planning_provider(responses))
            _write_atomic(output_path, result)
    except (OSError, PlanToolError) as exc:
        print(f"M8_PLAN_TOOL_REJECTED:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

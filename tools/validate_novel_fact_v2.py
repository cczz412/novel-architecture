#!/usr/bin/env python3
"""离线校验小说事实抽取 v2.1 回件，并组装与真实请求同形的训练消息。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FACT_SCHEMA_PATH = ROOT / "config/contracts/novel_fact_extraction_v2.schema.json"
BUNDLE_PATH = ROOT / "config/contracts/novel_fact_extraction_v2.bundle.json"
CARD_SCHEMA_PATH = (
    ROOT / "config/context_recipes/novel_fact_p3_context_card_v1.schema.json"
)
SOURCE_SCHEMA_PATH = (
    ROOT / "config/context_recipes/novel_fact_p3_source_index_v1.schema.json"
)
PROMPT_PATH = ROOT / "config/prompts/novel_fact_extraction_v2/prompt.md"
USER_TEMPLATE_PATH = (
    ROOT / "config/context_recipes/novel_fact_v2_user_message_template.md"
)

TOP_LEVEL_KEYS = ["sample_id", "source_file", "facts", "gold_atoms", "quality"]
LIGHT_TOP_LEVEL_KEYS = ["sample_id", "source_file", "facts", "quality"]
QUALITY_KEYS = ["status", "fact_count", "empty_reason", "coverage_self_check", "notes"]
RISK_TERMS = (
    "可能",
    "也许",
    "似乎",
    "如果",
    "若",
    "准备",
    "打算",
    "计划",
    "怀疑",
    "听说",
    "据说",
    "声称",
)
SPEAKER_STATUSES = {"推测", "误信"}
DEFINITE_COGNITIVE_SPEAKER_TERMS = (
    "认为",
    "知道",
    "发现",
    "意识到",
    "怀疑",
    "误以为",
    "相信",
    "觉得",
    "认定",
    "察觉",
    "明白",
)
SOURCE_ATTRIBUTION_TERMS = (
    "表示",
    "告诉",
    "声称",
    "承认",
    "答应",
    "承诺",
    "认为",
    "知道",
    "发现",
    "怀疑",
    "误以为",
    "听说",
)
SOURCE_ATTRIBUTION_PATTERNS = (
    "说道",
    "说出",
    "说了",
    "说过",
    "说起",
    "说要",
    "说会",
    "说是",
    "说自己",
    "说他",
    "说她",
    "说这",
    "说那",
    "说：",
    "说“",
    "发问",
    "提问",
    "问道",
    "问了",
    "问起",
    "问他",
    "问她",
    "意识到",
    "说明了",
    "说明过",
    "作出说明",
)
SPEECH_ACT_CANDIDATE_TERMS = (
    "询问",
    "追问",
    "反问",
    "质问",
    "请求",
    "命令",
    "劝说",
    "劝告",
    "建议",
    "要求",
    "嘱咐",
    "吩咐",
    "交代",
    "交办",
    "指示",
    "评价",
    "让",
)
# 兼容现有调用方；这个词表从 v1.2 起只圈候选，不证明言语动作已经完成。
COMPLETED_SPEECH_ACT_TERMS = SPEECH_ACT_CANDIDATE_TERMS
DIRECTIVE_CANDIDATE_TERMS = (
    "请求",
    "命令",
    "劝说",
    "劝告",
    "建议",
    "要求",
    "嘱咐",
    "吩咐",
    "交代",
    "交办",
    "指示",
    "让",
)
EXPLICIT_CONDITION_MARKERS = (
    "如果",
    "若",
    "除非",
    "只要",
    "倘若",
    "假如",
)
INCOMPLETE_SPEECH_ACT_PREFIXES = (
    "计划",
    "准备",
    "打算",
    "将要",
    "尚未",
    "还未",
    "没有",
    "并未",
    "未曾",
    "拒绝",
    "不予",
    "放弃",
    "试图",
)
NON_EVENT_SPEECH_ACT_SUFFIXES = (
    "计划",
    "方案",
    "流程",
    "记录",
    "笔录",
    "体系",
    "标准",
    "指标",
    "结果",
    "内容",
    "能力",
)
GENERIC_SPEAKERS = {
    "众人",
    "大家",
    "所有人",
    "人们",
    "说话者",
    "提问者",
    "观众",
    "奴才",
}
CANONICAL_NARRATIVE_SPEAKER = "旁白"
NONCANONICAL_NARRATIVE_SPEAKERS = {"叙述者", "物品说明"}
# 兼容只读调用方；校验逻辑会区分唯一规范值与旧别名。
NARRATIVE_SPEAKER_PLACEHOLDERS = {
    CANONICAL_NARRATIVE_SPEAKER,
    *NONCANONICAL_NARRATIVE_SPEAKERS,
}
RETELLING_SPEAKER_RE = re.compile(r"(?P<holder>[^（）]+)（转述自(?P<source>[^（）]+)）")
MULTI_SPEAKER_CONNECTOR_RE = re.compile(r"^.{2,8}(?:以及|和|与|及).{2,8}$")
SENTENCE_END_RE = re.compile(r"[。？！]+")
SENTENCE_WRAPPERS = " \t\r\n\"'“”‘’（）()《》〈〉【】[]「」『』"
CONTRACT_VERSION = "novel-fact-extraction-v2.1"
GATE_VERSION = "novel-fact-extraction-gate-v1.2"
BUNDLE_VERSION = "novel-fact-extraction-v2.1-bundle-2"
REQUIRED_ASSET_ROLES = {
    "semantic_contract",
    "output_schema",
    "context_card_schema",
    "context_source_index_schema",
    "user_message_template",
    "system_prompt",
    "batch_self_review_prompt",
    "t5_r04_batch_self_review_prompt",
    "offline_validator_and_assembler",
}
BOUNDARY_KEYS = (
    "may_call_model",
    "may_start_training",
    "may_change_active_default",
    "may_rescore_v1_history",
    "may_reopen_closed_r1_r2",
)


class ContractError(ValueError):
    """输入违反 v2.1 合同。"""


class DuplicateKeyError(ContractError):
    """JSON 出现重复键。"""


def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"重复 JSON 键：{key}")
        result[key] = value
    return result


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ContractError(detail)


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        DuplicateKeyError,
    ) as exc:
        raise ContractError(f"无法读取 JSON：{path}：{exc}") from exc


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"无法读取 JSONL：{path}：{exc}") from exc
    require(
        lines and all(line.strip() for line in lines),
        f"{path.name} 必须非空且不能夹空行",
    )
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line, object_pairs_hook=no_duplicate_keys)
        except (json.JSONDecodeError, DuplicateKeyError) as exc:
            raise ContractError(f"{path.name}:L{line_number} JSON 非法：{exc}") from exc
        require(isinstance(row, dict), f"{path.name}:L{line_number} 必须是 JSON 对象")
        rows.append(row)
    return rows


def schema_validator(path: Path) -> Draft202012Validator:
    schema = load_json(path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_contract_bundle(path: Path = BUNDLE_PATH) -> dict[str, Any]:
    bundle = load_json(path)
    require(isinstance(bundle, dict), "合同包必须是 JSON 对象")
    require(
        bundle.get("bundle_version") == BUNDLE_VERSION,
        f"合同包版本必须是 {BUNDLE_VERSION}",
    )
    require(
        bundle.get("supersedes") == "novel-fact-extraction-v2.1-bundle-1",
        "合同包 supersedes 漂移",
    )
    require(
        bundle.get("status") == "approved_contract_not_wired_to_default_chain",
        "合同包状态漂移",
    )
    versioning = bundle.get("versioning")
    require(isinstance(versioning, dict), "合同包缺少 versioning")
    require(
        versioning.get("contract_version") == CONTRACT_VERSION,
        "合同包 contract_version 与校验器不一致",
    )
    require(
        versioning.get("gate_version") == GATE_VERSION,
        "合同包 gate_version 与校验器不一致",
    )
    require(
        versioning.get("historical_scores_recalculated") is False, "禁止重算历史成绩"
    )
    require(
        versioning.get("frozen_14_item_exam_changed") is False, "禁止改动冻结 14 题"
    )
    require(
        versioning.get("legacy_v2_tickets_inherit_pass") is False,
        "旧 v2 票不得继承通过",
    )
    require(
        versioning.get("prior_gate_tickets_inherit_pass") is False,
        "旧程序闸票不得继承通过",
    )
    assets = bundle.get("assets")
    require(isinstance(assets, list) and assets, "合同包 assets 必须是非空数组")
    seen_roles: set[str] = set()
    seen_paths: set[str] = set()
    for index, asset in enumerate(assets):
        location = f"合同包 assets[{index}]"
        require(isinstance(asset, dict), f"{location} 必须是对象")
        require(list(asset) == ["role", "path", "sha256"], f"{location} 字段或顺序漂移")
        role = asset["role"]
        relative = asset["path"]
        expected_sha = asset["sha256"]
        require(
            isinstance(role, str) and role and role not in seen_roles,
            f"{location}.role 非法或重复",
        )
        require(
            isinstance(relative, str) and relative and relative not in seen_paths,
            f"{location}.path 非法或重复",
        )
        require(
            isinstance(expected_sha, str)
            and re.fullmatch(r"[0-9a-f]{64}", expected_sha) is not None,
            f"{location}.sha256 非法",
        )
        seen_roles.add(role)
        seen_paths.add(relative)
        asset_path = (ROOT / relative).resolve()
        require(
            asset_path.is_relative_to(ROOT), f"{location}.path 越出仓库：{relative}"
        )
        require(asset_path.is_file(), f"{location}.path 不存在：{relative}")
        require(
            sha256_bytes(asset_path.read_bytes()) == expected_sha,
            f"{location}.sha256 与当前文件不一致：{relative}",
        )
    require(seen_roles == REQUIRED_ASSET_ROLES, "合同包必需资产角色集合漂移")
    boundaries = bundle.get("boundaries")
    require(isinstance(boundaries, dict), "合同包缺少 boundaries")
    require(tuple(boundaries) == BOUNDARY_KEYS, "合同包 boundaries 字段或顺序漂移")
    for key in BOUNDARY_KEYS:
        require(boundaries[key] is False, f"合同包权限边界必须保持 false：{key}")
    return bundle


def validate_schema(validator: Draft202012Validator, value: Any, location: str) -> None:
    errors = sorted(
        validator.iter_errors(value), key=lambda item: list(item.absolute_path)
    )
    if not errors:
        return
    error = errors[0]
    suffix = "".join(f"[{part!r}]" for part in error.absolute_path)
    raise ContractError(f"{location}{suffix} 不符合 Schema：{error.message}")


def index_unique(
    rows: list[dict[str, Any]], key: str, label: str
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        require(isinstance(value, str) and value, f"{label} 缺少非空 {key}")
        require(value not in indexed, f"{label} 出现重复 {key}：{value}")
        indexed[value] = row
    return indexed


def validate_source_index(path: Path) -> dict[str, dict[str, Any]]:
    validator = schema_validator(SOURCE_SCHEMA_PATH)
    rows = load_jsonl(path)
    indexed = index_unique(rows, "source_id", path.name)
    for source_id, row in indexed.items():
        validate_schema(validator, row, f"source_index[{source_id}]")
        source_path = Path(row["path"]).expanduser()
        require(source_path.is_absolute(), f"{source_id}.path 必须是绝对路径")
        require(
            source_path.is_file(), f"{source_id}.path 不存在或不是文件：{source_path}"
        )
        actual_sha = sha256_bytes(source_path.read_bytes())
        require(actual_sha == row["sha256"], f"{source_id} 来源文件 SHA-256 不一致")
    return indexed


def validate_card_semantics(
    card: dict[str, Any], source_index: dict[str, dict[str, Any]]
) -> None:
    sample_id = card["sample_id"]
    story = card["story_type"]
    subtypes = card["story_subtypes"]
    protagonist = card["protagonist"]
    cheat = card["cheat_mechanic"]

    if story["status"] == "unknown":
        require(
            story["value"] is None and story["basis"] == "none_available",
            f"{sample_id} 未知题材不得填写猜测值",
        )
    else:
        require(
            story["value"] is not None and story["basis"] != "none_available",
            f"{sample_id} 已确认题材缺少依据",
        )

    if subtypes["status"] == "unknown":
        require(
            subtypes["values"] == [] and subtypes["basis"] == "none_available",
            f"{sample_id} 未知小类型不得填写猜测值",
        )
    else:
        require(
            bool(subtypes["values"]) and subtypes["basis"] != "none_available",
            f"{sample_id} 已确认小类型缺少值或依据",
        )

    if protagonist["status"] == "unknown":
        require(
            protagonist["canonical_name"] is None
            and protagonist["aliases"] == []
            and protagonist["basis"] == "none_available",
            f"{sample_id} 未知主角不得填写猜测姓名或别名",
        )
    else:
        require(
            protagonist["canonical_name"] is not None
            and protagonist["basis"] != "none_available",
            f"{sample_id} 已确认主角缺少姓名或依据",
        )

    if cheat["status"] == "confirmed":
        require(
            cheat["name"] is not None and cheat["summary"] is not None,
            f"{sample_id} 已确认金手指缺少名称或简述",
        )
        require(cheat["basis"] != "none_available", f"{sample_id} 已确认金手指缺少依据")
    elif cheat["status"] == "none_confirmed":
        require(
            cheat["name"] is None and cheat["summary"] is None and cheat["rules"] == [],
            f"{sample_id} 已确认无金手指时不得填写名称、简述或规则",
        )
        require(
            cheat["basis"] != "none_available",
            f"{sample_id} 已确认无金手指也必须登记依据",
        )
    else:
        require(
            cheat["name"] is None and cheat["summary"] is None and cheat["rules"] == [],
            f"{sample_id} 未知金手指不得填写推测内容",
        )
        require(
            cheat["basis"] == "none_available",
            f"{sample_id} 未知金手指的依据必须是 none_available",
        )

    confirmed = any(
        field_status == "confirmed"
        for field_status in (story["status"], subtypes["status"], protagonist["status"])
    )
    confirmed = confirmed or cheat["status"] in {"confirmed", "none_confirmed"}
    require(
        bool(card["source_refs"]) == confirmed,
        f"{sample_id} 已确认字段与 source_refs 有无不一致",
    )
    for ref in card["source_refs"]:
        source_id = ref["source_id"]
        require(source_id in source_index, f"{sample_id} 引用了未登记来源：{source_id}")
        indexed = source_index[source_id]
        require(
            indexed["scope"] == ref["scope"], f"{sample_id}/{source_id} 来源类型不一致"
        )
        require(
            indexed["sha256"] == ref["sha256"],
            f"{sample_id}/{source_id} 来源 SHA-256 不一致",
        )


def load_cards(
    path: Path, source_index: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    validator = schema_validator(CARD_SCHEMA_PATH)
    rows = load_jsonl(path)
    indexed = index_unique(rows, "sample_id", path.name)
    for sample_id, card in indexed.items():
        validate_schema(validator, card, f"context_card[{sample_id}]")
        validate_card_semantics(card, source_index)
    return indexed


def validate_fact_keys(fact: dict[str, Any], location: str) -> None:
    expected = ["fact", "status", "evidence"]
    if "speaker" in fact:
        expected.append("speaker")
    require(list(fact) == expected, f"{location} 字段或顺序必须是 {expected}")


def sentence_count(text: str) -> int:
    """按中文句号、问号和感叹号切句；末尾引号不另算一句。"""

    return sum(
        bool(part.strip(SENTENCE_WRAPPERS)) for part in SENTENCE_END_RE.split(text)
    )


def validate_speaker_party(value: str, location: str) -> None:
    require(
        not any(separator in value for separator in ("、", "，", ",", "/"))
        and MULTI_SPEAKER_CONNECTOR_RE.fullmatch(value) is None,
        f"{location} 只能写一个主体，不能并列多人",
    )
    require(
        "《" not in value and "》" not in value,
        f"{location} 必须写人名，不能写作品或文件名",
    )
    require(value not in GENERIC_SPEAKERS, f"{location} 不能使用泛指来源：{value}")
    require(
        not value.endswith(("等", "等人", "们")),
        f"{location} 不能使用泛指或多人来源：{value}",
    )


def validate_speaker_format(speaker: str, location: str) -> None:
    require(speaker == speaker.strip(), f"{location} 不得带首尾空白")
    require(
        speaker not in NONCANONICAL_NARRATIVE_SPEAKERS,
        f"{location} 叙述来源若确需填写，统一写“{CANONICAL_NARRATIVE_SPEAKER}”",
    )
    if speaker == "来源不明":
        return
    require(
        "(" not in speaker and ")" not in speaker,
        f"{location} 只能使用全角括号的统一转述格式",
    )
    if "（" in speaker or "）" in speaker or "转述自" in speaker:
        match = RETELLING_SPEAKER_RE.fullmatch(speaker)
        require(match is not None, f"{location} 转述格式必须是“人名（转述自来源）”")
        holder = match.group("holder")
        source = match.group("source")
        validate_speaker_party(holder, f"{location} 的信息持有人")
        require(source != "来源不明", f"{location} 来源不明时直接写“来源不明”")
        validate_speaker_party(source, f"{location} 的转述来源")
        return
    validate_speaker_party(speaker, location)


def completed_speech_act_hits(fact_text: str) -> list[str]:
    """返回可能是已说出口言语动作的词面候选，不据此作语义硬判。"""

    hits: list[str] = []
    for term in COMPLETED_SPEECH_ACT_TERMS:
        start = 0
        while True:
            index = fact_text.find(term, start)
            if index < 0:
                break
            prefix = fact_text[max(0, index - 4) : index]
            suffix = fact_text[index + len(term) : index + len(term) + 4]
            blocked = any(
                prefix.endswith(item) for item in INCOMPLETE_SPEECH_ACT_PREFIXES
            )
            blocked = blocked or any(
                suffix.startswith(item) for item in NON_EVENT_SPEECH_ACT_SUFFIXES
            )
            if not blocked:
                hits.append(term)
                break
            start = index + len(term)
    return hits


def speech_act_candidate_hits(fact_text: str) -> list[str]:
    """v1.2 公共候选入口；命中只供复核，不能自动改 status 或 speaker。"""

    return completed_speech_act_hits(fact_text)


def directive_candidate_hits(fact_text: str) -> list[str]:
    """返回可能含请求、命令、建议或交办的词面候选。"""

    speech_hits = set(speech_act_candidate_hits(fact_text))
    return [term for term in DIRECTIVE_CANDIDATE_TERMS if term in speech_hits]


def explicit_condition_marker_hits(fact_text: str) -> list[str]:
    """返回显式条件连接词；仍不证明整条事实应标为条件。"""

    return [term for term in EXPLICIT_CONDITION_MARKERS if term in fact_text]


def source_attribution_hits(fact_text: str) -> list[str]:
    """返回可能涉及来源或认知的词面候选，不据此强制 speaker。"""

    hits = [term for term in SOURCE_ATTRIBUTION_TERMS if term in fact_text]
    hits.extend(
        pattern for pattern in SOURCE_ATTRIBUTION_PATTERNS if pattern in fact_text
    )
    hits.extend(speech_act_candidate_hits(fact_text))
    return list(dict.fromkeys(hits))


def definite_cognitive_speaker_hits(fact_text: str) -> list[str]:
    """返回合同明确规定必须保留认知主体的谓词。"""

    return [term for term in DEFINITE_COGNITIVE_SPEAKER_TERMS if term in fact_text]


def needs_speaker(fact: dict[str, Any]) -> bool:
    """返回结构化状态或明确认知谓词能确定的 speaker 硬门。"""

    return fact["status"] in SPEAKER_STATUSES or bool(
        definite_cognitive_speaker_hits(fact["fact"])
    )


def candidate_warning(location: str, detail: str) -> str:
    return f"{location} 候选标红：{detail}；只提示人工复核，程序不据此判定语义"


def occurrence_start(text: str, needle: str, occurrence: int) -> int:
    require(occurrence >= 1, "evidence_occurrence 必须从 1 开始")
    start = 0
    found = -1
    for _ in range(occurrence):
        found = text.find(needle, start)
        if found < 0:
            return -1
        start = found + len(needle)
    return found


def validate_gold_atoms(row: dict[str, Any], sample_id: str, chapter_text: str) -> None:
    atoms = row["gold_atoms"]
    facts = row["facts"]
    require(isinstance(atoms, list), f"{sample_id}.gold_atoms 必须是数组")
    require(len(atoms) == len(facts), f"{sample_id} facts 与 gold_atoms 数量不一致")
    for index, (fact, atom) in enumerate(zip(facts, atoms, strict=True)):
        location = f"{sample_id}.gold_atoms[{index}]"
        require(isinstance(atom, dict), f"{location} 必须是对象")
        require(atom.get("fact") == fact["fact"], f"{location}.fact 与 facts 不一致")
        require(
            atom.get("status") == fact["status"], f"{location}.status 与 facts 不一致"
        )
        require(
            atom.get("evidence") == fact["evidence"],
            f"{location}.evidence 与 facts 不一致",
        )
        require(
            atom.get("speaker") == fact.get("speaker"),
            f"{location}.speaker 与 facts 不一致",
        )
        require(
            atom.get("atom_id") == f"{sample_id}-F{index + 1:03d}",
            f"{location}.atom_id 不连续",
        )
        occurrence = atom.get("evidence_occurrence")
        require(
            isinstance(occurrence, int) and not isinstance(occurrence, bool),
            f"{location}.evidence_occurrence 必须是整数",
        )
        require(
            occurrence_start(chapter_text, fact["evidence"], occurrence) >= 0,
            f"{location}.evidence_occurrence 指向的原文出现次数不存在",
        )
        chain = atom.get("claim_chain", [])
        require(isinstance(chain, list), f"{location}.claim_chain 必须是数组")
        for level, node in enumerate(chain, 1):
            require(
                isinstance(node, dict),
                f"{location}.claim_chain[{level - 1}] 必须是对象",
            )
            require(
                node.get("level") == level and node.get("link") == "reports",
                f"{location}.claim_chain 层级或 link 非法",
            )
            holder = node.get("holder_surface")
            require(
                isinstance(holder, str) and holder in fact["evidence"],
                f"{location}.holder_surface 不是 evidence 子串",
            )


def validate_annotation(
    row: dict[str, Any],
    chapter_text: str,
    card: dict[str, Any],
    fact_validator: Draft202012Validator,
    *,
    facts_only: bool,
) -> list[str]:
    sample_id = row.get("sample_id", "<missing>")
    expected_keys = LIGHT_TOP_LEVEL_KEYS if facts_only else TOP_LEVEL_KEYS
    require(
        list(row) == expected_keys, f"{sample_id} 顶层字段或顺序必须是 {expected_keys}"
    )
    require(
        row["sample_id"] == card["sample_id"], f"{sample_id} 与背景卡 sample_id 不一致"
    )
    require(
        row["source_file"] == card["source_file"],
        f"{sample_id} 与背景卡 source_file 不一致",
    )
    validate_schema(fact_validator, {"facts": row["facts"]}, f"annotation[{sample_id}]")

    warnings: list[str] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    evidence_locations: dict[str, list[str]] = {}
    for index, fact in enumerate(row["facts"]):
        location = f"{sample_id}.facts[{index}]"
        validate_fact_keys(fact, location)
        evidence = fact["evidence"]
        require(
            evidence in chapter_text,
            f"{location}.evidence 不是对应完整章节的连续逐字子串",
        )
        require(sentence_count(evidence) <= 2, f"{location}.evidence 超过 2 句上限")
        evidence_locations.setdefault(evidence, []).append(location)
        identity = (fact["fact"], fact["status"], evidence, fact.get("speaker"))
        require(identity not in seen, f"{location} 是完全重复事实")
        seen.add(identity)
        speaker_required = needs_speaker(fact)
        source_hits = source_attribution_hits(fact["fact"])
        speech_hits = speech_act_candidate_hits(fact["fact"])
        directive_hits = directive_candidate_hits(fact["fact"])
        condition_hits = explicit_condition_marker_hits(fact["fact"])
        require(
            not speaker_required or "speaker" in fact,
            f"{location} 的 status 或 fact 已明确属于推测、误信或认知事实，必须填写 speaker",
        )
        if "speaker" in fact:
            validate_speaker_format(fact["speaker"], f"{location}.speaker")
            if fact["speaker"] == CANONICAL_NARRATIVE_SPEAKER:
                warnings.append(
                    candidate_warning(
                        location,
                        "使用了“旁白”；请确认这条叙述确实需要保留来源，纯叙述通常省略 speaker，不能批量补",
                    )
                )
            elif not speaker_required and not source_hits:
                warnings.append(
                    candidate_warning(
                        location,
                        "未命中来源或认知提示词却填写了 speaker；请回看原文确认是否应省略",
                    )
                )
        elif source_hits:
            warnings.append(
                candidate_warning(
                    location,
                    f"命中可能涉及来源、引语或认知的词：{'、'.join(source_hits)}；请确认是否缺 speaker",
                )
            )
        if speech_hits and fact["status"] != "已发生":
            warnings.append(
                candidate_warning(
                    location,
                    f"命中可能已经说出口的言语动作词：{'、'.join(speech_hits)}；若原文确为已说出口，言语事件应标已发生",
                )
            )
        if directive_hits:
            warnings.append(
                candidate_warning(
                    location,
                    f"命中请求、命令、建议或交办候选：{'、'.join(directive_hits)}；请检查言语事件与重要待执行动作是否分开，待办主体是否为被交办人",
                )
            )
        if fact["status"] == "条件" and not condition_hits:
            warnings.append(
                candidate_warning(
                    location,
                    "标为条件但未命中显式条件连接词；请确认原文确有如果／除非一类前提关系，而不只是指示、未来时间或交办",
                )
            )
        elif fact["status"] == "条件" and directive_hits:
            warnings.append(
                candidate_warning(
                    location,
                    "同条同时命中指示候选和条件连接词；请区分已发生的言语事件与话语中的条件内容，必要时拆开",
                )
            )
        if fact["status"] == "已发生":
            hit = [term for term in RISK_TERMS if term in fact["fact"]]
            if hit and not speech_hits:
                warnings.append(
                    candidate_warning(
                        location,
                        f"标为已发生但含情态风险词：{'、'.join(hit)}",
                    )
                )

    for evidence, locations in evidence_locations.items():
        if len(locations) > 1:
            warnings.append(
                candidate_warning(
                    sample_id,
                    f"多条事实共用完全相同的 evidence：{'、'.join(locations)}；请检查是否该拆短或去重",
                )
            )

    if not facts_only:
        validate_gold_atoms(row, sample_id, chapter_text)
    quality = row["quality"]
    require(
        isinstance(quality, dict) and list(quality) == QUALITY_KEYS,
        f"{sample_id}.quality 字段或顺序必须是 {QUALITY_KEYS}",
    )
    require(
        quality["status"] == "candidate",
        f"{sample_id}.quality.status 必须保持 candidate",
    )
    require(
        quality["fact_count"] == len(row["facts"]),
        f"{sample_id}.quality.fact_count 计数不一致",
    )
    require(
        quality["coverage_self_check"] == "complete",
        f"{sample_id} 必须声明已完成整章覆盖自检",
    )
    require(isinstance(quality["notes"], list), f"{sample_id}.quality.notes 必须是数组")
    if row["facts"]:
        require(
            quality["empty_reason"] is None,
            f"{sample_id} 非空结果的 empty_reason 必须为 null",
        )
    else:
        require(
            isinstance(quality["empty_reason"], str)
            and quality["empty_reason"].strip(),
            f"{sample_id} 空结果必须写具体原因",
        )
    return warnings


def load_and_validate(
    annotations_path: Path,
    chapters_dir: Path,
    cards_path: Path,
    source_index_path: Path,
    expected_count: int | None,
    facts_only: bool,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, dict[str, Any]], list[str]]:
    validate_contract_bundle()
    require(chapters_dir.is_dir(), f"章节目录不存在：{chapters_dir}")
    source_index = validate_source_index(source_index_path)
    cards = load_cards(cards_path, source_index)
    rows = load_jsonl(annotations_path)
    annotations = index_unique(rows, "sample_id", annotations_path.name)
    require(set(annotations) == set(cards), "回件与背景卡的 sample_id 集合不完全一致")
    if expected_count is not None:
        require(
            len(rows) == expected_count,
            f"本批必须恰好 {expected_count} 个样本，实际 {len(rows)} 个",
        )

    fact_validator = schema_validator(FACT_SCHEMA_PATH)
    chapters: dict[str, str] = {}
    warnings: list[str] = []
    for row in rows:
        sample_id = row["sample_id"]
        card = cards[sample_id]
        source_file = row.get("source_file")
        require(
            isinstance(source_file, str) and source_file == Path(source_file).name,
            f"{sample_id}.source_file 必须是单个文件名",
        )
        chapter_path = chapters_dir / source_file
        require(
            chapter_path.is_file(), f"{sample_id} 找不到原始完整章节：{chapter_path}"
        )
        try:
            chapter_text = chapter_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ContractError(
                f"{sample_id} 章节不是合法 UTF-8：{chapter_path}"
            ) from exc
        chapters[sample_id] = chapter_text
        warnings.extend(
            validate_annotation(
                row, chapter_text, card, fact_validator, facts_only=facts_only
            )
        )
    return rows, chapters, cards, warnings


def build_receipt(
    status: str,
    rows: list[dict[str, Any]],
    warnings: list[str],
    output: Path | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "status": status,
        "contract_version": CONTRACT_VERSION,
        "gate_version": GATE_VERSION,
        "contract_bundle_version": BUNDLE_VERSION,
        "contract_bundle_sha256": sha256_bytes(BUNDLE_PATH.read_bytes()),
        "samples": len(rows),
        "facts": sum(len(row["facts"]) for row in rows),
        "warnings": warnings,
        "semantic_review_pending": True,
    }
    if output is not None:
        receipt["output"] = str(output)
        receipt["output_sha256"] = sha256_bytes(output.read_bytes())
    return receipt


def command_validate(args: argparse.Namespace) -> None:
    rows, _, _, warnings = load_and_validate(
        args.annotations,
        args.chapters_dir,
        args.context_cards,
        args.context_source_index,
        args.expected_count,
        args.facts_only,
    )
    print(
        compact_json(
            build_receipt(
                "V2_1_FORMAT_AND_EVIDENCE_PASS_SEMANTIC_REVIEW_PENDING", rows, warnings
            )
        )
    )


def command_bundle_check(args: argparse.Namespace) -> None:
    validate_contract_bundle(args.bundle)
    print(
        compact_json(
            {
                "status": "V2_1_CONTRACT_BUNDLE_PASS",
                "contract_version": CONTRACT_VERSION,
                "gate_version": GATE_VERSION,
                "contract_bundle_version": BUNDLE_VERSION,
                "contract_bundle_sha256": sha256_bytes(args.bundle.read_bytes()),
            }
        )
    )


def render_user_message(
    template: str, card: dict[str, Any], source_file: str, chapter_text: str
) -> str:
    require(template.count("{{CONTEXT_CARD_JSON}}") == 1, "用户模板的背景卡槽位漂移")
    require(template.count("{{SOURCE_FILE}}") == 1, "用户模板的文件名槽位漂移")
    require(template.count("{{CHAPTER_TEXT}}") == 1, "用户模板的章节槽位漂移")
    return (
        template.replace("{{CONTEXT_CARD_JSON}}", compact_json(card))
        .replace("{{SOURCE_FILE}}", source_file)
        .replace("{{CHAPTER_TEXT}}", chapter_text)
    )


def command_assemble(args: argparse.Namespace) -> None:
    rows, chapters, cards, warnings = load_and_validate(
        args.annotations,
        args.chapters_dir,
        args.context_cards,
        args.context_source_index,
        args.expected_count,
        args.facts_only,
    )
    require(not args.output.exists(), f"输出文件已存在，不覆盖：{args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    user_template = USER_TEMPLATE_PATH.read_text(encoding="utf-8")
    messages: list[str] = []
    for row in rows:
        sample_id = row["sample_id"]
        messages.append(
            compact_json(
                {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": render_user_message(
                                user_template,
                                cards[sample_id],
                                row["source_file"],
                                chapters[sample_id],
                            ),
                        },
                        {
                            "role": "assistant",
                            "content": compact_json({"facts": row["facts"]}),
                        },
                    ]
                }
            )
        )
    args.output.write_text("\n".join(messages) + "\n", encoding="utf-8")
    print(
        compact_json(
            build_receipt(
                "V2_1_TRAINING_MESSAGES_ASSEMBLED_CANDIDATE_ONLY",
                rows,
                warnings,
                args.output,
            )
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bundle_check = subparsers.add_parser(
        "bundle-check", help="核对 v2.1 合同包与全部零件 SHA"
    )
    bundle_check.add_argument(
        "--bundle",
        type=Path,
        default=BUNDLE_PATH,
        help="待核合同包；默认使用仓内 v2.1 合同包",
    )
    bundle_check.set_defaults(handler=command_bundle_check)
    for name, handler in (
        ("validate", command_validate),
        ("assemble", command_assemble),
    ):
        command = subparsers.add_parser(name)
        command.add_argument(
            "--annotations",
            type=Path,
            required=True,
            help="ChatGPT 修订后的 v2.1 JSONL",
        )
        command.add_argument(
            "--chapters-dir",
            type=Path,
            required=True,
            help="这一批完整章节 TXT 所在目录",
        )
        command.add_argument(
            "--context-cards", type=Path, required=True, help="P3 背景卡 JSONL"
        )
        command.add_argument(
            "--context-source-index",
            type=Path,
            required=True,
            help="背景卡来源文件与 SHA 索引 JSONL",
        )
        command.add_argument(
            "--expected-count",
            type=int,
            default=10,
            help="本批应有的样本数，默认 10；传 0 关闭计数限制",
        )
        command.add_argument(
            "--facts-only",
            action="store_true",
            help="轻量自检回包不含平行 gold_atoms，只验四字段事实",
        )
        if name == "assemble":
            command.add_argument(
                "--output",
                type=Path,
                required=True,
                help="新建的训练 messages.jsonl；拒绝覆盖",
            )
        command.set_defaults(handler=handler)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if getattr(args, "expected_count", None) == 0:
        args.expected_count = None
    try:
        args.handler(args)
    except (ContractError, OSError) as exc:
        print(compact_json({"status": "FAIL", "error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

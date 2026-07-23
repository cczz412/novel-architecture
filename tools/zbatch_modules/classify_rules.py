"""模块 7：主控分类决定的验收、编译与冲突留账。

语义分类仍由主控完成。本模块不猜 A/B/C/D，只检查每个中性事件是否被一对一
处置、重复和 D 类边界是否符合版本化规则，再把批准决定确定性编译成记录。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from . import anchor_kit, candidate_envelope
from .errors import ZBatchError
from .evidence_catalog import nonspace_chars
from .prompt_render_pin import sha256_file


DECISION_KEYS = {
    "event_id",
    "disposition",
    "matched_types",
    "primary_type",
    "rule_ids",
    "basis",
    "assertion",
    "fields",
    "related_event_ids",
    "duplicate_group",
    "conflict_reason",
}
V1_2_EXTRA_DECISION_KEYS = {
    "source_level",
    "scope_mode",
    "type_audit",
}
DISPOSITIONS = {"classified", "unclassified", "discarded"}
TYPE_STATE = {"A": "", "B": "待", "C": "未兑现", "D": "有效"}
ROOT_KEYS = {"schema_version", "run_id", "rules_sha256", "decisions"}
EVENT_ID_PATTERN = re.compile(r"EV-C(?P<chapter>[0-9]{4})-(?P<index>[0-9]{2})")


def _event_chapter(event_id: Any) -> int | None:
    """只从符合中性事件合同的编号中读取章号。"""
    if not isinstance(event_id, str):
        return None
    match = EVENT_ID_PATTERN.fullmatch(event_id)
    return int(match.group("chapter")) if match is not None else None


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ZBatchError(f"{label}必须是JSON对象")
    return value


def _inside_root(root: Path, relative: str) -> Path:
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ZBatchError(f"分类合同路径越界：{relative}")
    return path


def tree_fingerprint(project_root: Path, directory: Path) -> str:
    """按“文件 SHA＋项目内路径”确定性计算整棵历史工件指纹。"""
    root = project_root.resolve()
    target = directory.resolve()
    if not target.is_relative_to(root) or not target.is_dir():
        raise ZBatchError(f"历史工件目录不存在或越界：{directory}")
    rows = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}\n"
        for path in sorted(item for item in target.rglob("*") if item.is_file())
    )
    return hashlib.sha256(rows.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ClassificationContract:
    contract_version: str
    role: str
    semantic_boundary: str
    decision_schema_version: str
    rules_path: str
    rules_sha256: str
    predecessor_rules_sha256: str
    predecessor_decisions_path: str
    predecessor_decisions_sha256: str
    predecessor_run_id: str
    predecessor_run_tree_fingerprint: str
    policies: Mapping[str, Mapping[str, Any]]
    rule_registry: Mapping[str, Any]
    regression_cases: tuple[Mapping[str, Any], ...]
    current_regression_cases: tuple[Mapping[str, Any], ...]


def _validate_stable_identity_cases(cases: Iterable[Mapping[str, Any]]) -> None:
    values = list(cases)
    if not values or not all(isinstance(case.get("identities"), list) for case in values):
        return
    case_ids: set[str] = set()
    semantic_ids: set[str] = set()
    for case in values:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise ZBatchError("稳定语义身份回归案例case_id为空或重复")
        case_ids.add(case_id)
        kind = case.get("kind")
        identities = case.get("identities")
        if kind not in {"duplicate_group", "single_observation", "event_decision"}:
            raise ZBatchError(f"{case_id}稳定语义身份回归类型非法")
        if not identities or (kind != "duplicate_group" and len(identities) != 1):
            raise ZBatchError(f"{case_id}稳定语义身份数量非法")
        for identity in identities:
            identity = _mapping(identity, f"{case_id}.identity")
            semantic_id = identity.get("semantic_id")
            if not isinstance(semantic_id, str) or not semantic_id or semantic_id in semantic_ids:
                raise ZBatchError("稳定语义身份semantic_id为空或重复")
            semantic_ids.add(semantic_id)
            locator = _mapping(identity.get("locator"), f"{semantic_id}.locator")
            if set(locator) != {"chapter", "anchor_ids", "anchor_quote_sha256", "term_groups"}:
                raise ZBatchError(f"{semantic_id}稳定语义定位器字段不完整")
            chapter = locator.get("chapter")
            anchor_ids = locator.get("anchor_ids")
            fingerprint = locator.get("anchor_quote_sha256")
            term_groups = locator.get("term_groups")
            if not isinstance(chapter, int) or chapter < 1:
                raise ZBatchError(f"{semantic_id}稳定语义定位章号非法")
            if (
                not isinstance(anchor_ids, list)
                or not anchor_ids
                or len(anchor_ids) != len(set(anchor_ids))
                or any(not isinstance(value, str) or not value for value in anchor_ids)
            ):
                raise ZBatchError(f"{semantic_id}稳定语义定位锚非法")
            if not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
                raise ZBatchError(f"{semantic_id}稳定语义定位指纹非法")
            if (
                not isinstance(term_groups, list)
                or any(
                    not isinstance(group, list)
                    or not group
                    or any(not isinstance(term, str) or not _normalized_semantic_text(term) for term in group)
                    for group in term_groups
                )
            ):
                raise ZBatchError(f"{semantic_id}稳定语义定位词组非法")


def load_contract(path: Path, *, project_root: Path) -> ClassificationContract:
    """载入分类合同，并当场验新版规则和批准决定引用的 SHA。"""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ZBatchError(f"分类合同不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ZBatchError(f"分类合同不是合法JSON：{path}") from exc
    root = _mapping(raw, "分类合同根")
    rules = _mapping(root.get("rules"), "分类合同rules")
    predecessor = _mapping(root.get("approved_predecessor"), "分类合同approved_predecessor")
    policies_raw = _mapping(root.get("policies"), "分类合同policies")
    registry_raw = _mapping(root.get("rule_registry"), "分类合同rule_registry")
    cases = root.get("approved_regression_cases")
    if not isinstance(cases, list) or not cases:
        raise ZBatchError("分类合同缺批准回归案例")
    current_cases = root.get("current_regression_cases") or []
    if not isinstance(current_cases, list):
        raise ZBatchError("分类合同current_regression_cases不是数组")
    rule_path = str(rules.get("path") or "")
    rule_sha = str(rules.get("sha256") or "")
    decisions_path = str(predecessor.get("decisions_path") or "")
    decisions_sha = str(predecessor.get("decisions_sha256") or "")
    predecessor_run_id = str(predecessor.get("run_id") or "")
    expected_tree_fingerprint = str(predecessor.get("run_tree_fingerprint") or "")
    if sha256_file(_inside_root(project_root, rule_path)) != rule_sha:
        raise ZBatchError("新版分类规则SHA漂移")
    if sha256_file(_inside_root(project_root, decisions_path)) != decisions_sha:
        raise ZBatchError("批准的Z00n v2决定SHA漂移")
    actual_tree_fingerprint = tree_fingerprint(
        project_root,
        _inside_root(project_root, f"runs/{predecessor_run_id}"),
    )
    if actual_tree_fingerprint != expected_tree_fingerprint:
        raise ZBatchError("Z00n批准运行树指纹漂移")
    policies: dict[str, Mapping[str, Any]] = {}
    for name, item in policies_raw.items():
        policies[str(name)] = MappingProxyType(dict(_mapping(item, f"policies.{name}")))
    allowed = registry_raw.get("allowed")
    required_by_primary = _mapping(
        registry_raw.get("required_by_primary"),
        "rule_registry.required_by_primary",
    )
    if not isinstance(allowed, list) or not allowed or any(not isinstance(value, str) for value in allowed):
        raise ZBatchError("规则编号白名单非法")
    if set(required_by_primary) != {"A", "B", "C", "D"}:
        raise ZBatchError("主类型基础规则登记不完整")
    rule_registry = MappingProxyType(
        {
            "allowed": tuple(allowed),
            "required_by_primary": MappingProxyType(dict(required_by_primary)),
            "discarded_required": str(registry_raw.get("discarded_required") or ""),
        }
    )
    current_case_values = tuple(
        MappingProxyType(dict(_mapping(case, "current_regression_case")))
        for case in current_cases
    )
    _validate_stable_identity_cases(current_case_values)
    return ClassificationContract(
        contract_version=str(root.get("contract_version") or ""),
        role=str(root.get("role") or ""),
        semantic_boundary=str(root.get("semantic_boundary") or ""),
        decision_schema_version=str(root.get("decision_schema_version") or ""),
        rules_path=rule_path,
        rules_sha256=rule_sha,
        predecessor_rules_sha256=str(predecessor.get("rules_sha256") or ""),
        predecessor_decisions_path=decisions_path,
        predecessor_decisions_sha256=decisions_sha,
        predecessor_run_id=predecessor_run_id,
        predecessor_run_tree_fingerprint=expected_tree_fingerprint,
        policies=MappingProxyType(policies),
        rule_registry=rule_registry,
        regression_cases=tuple(MappingProxyType(dict(_mapping(case, "regression_case"))) for case in cases),
        current_regression_cases=current_case_values,
    )


def promote_approved_reference(
    contract: ClassificationContract,
    *,
    project_root: Path,
) -> dict[str, Any]:
    """只在内存中把批准的 v2 决定挂到新版规则；历史文件保持不变。"""
    path = _inside_root(project_root, contract.predecessor_decisions_path)
    if sha256_file(path) != contract.predecessor_decisions_sha256:
        raise ZBatchError("批准的Z00n v2决定SHA漂移")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("rules_sha256") != contract.predecessor_rules_sha256:
        raise ZBatchError("批准决定的前代规则SHA不一致")
    if data.get("run_id") != contract.predecessor_run_id:
        raise ZBatchError("批准决定的run_id不一致")
    promoted = copy.deepcopy(data)
    promoted["rules_sha256"] = contract.rules_sha256
    return promoted


def index_events(
    event_documents: Iterable[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    event_map: dict[str, dict[str, Any]] = {}
    by_chapter: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen_chapters: set[int] = set()
    for document in event_documents:
        if not isinstance(document, dict) or document.get("schema_version") != "z-event-v1":
            raise ZBatchError("中性事件文档schema错误")
        chapter = document.get("chapter")
        if not isinstance(chapter, int) or chapter in seen_chapters:
            raise ZBatchError(f"中性事件文章号重复或非法：{chapter}")
        seen_chapters.add(chapter)
        events = document.get("events")
        if not isinstance(events, list):
            raise ZBatchError(f"第 {chapter} 章events不是数组")
        for event in events:
            event_id = event.get("event_id") if isinstance(event, dict) else None
            if not isinstance(event_id, str) or event_id in event_map:
                raise ZBatchError(f"中性事件ID重复或非法：{event_id}")
            event_map[event_id] = event
            by_chapter[chapter].append(event)
    return event_map, dict(by_chapter)


def decision_reasons(
    data: Any,
    *,
    run_id: str,
    event_ids: set[str],
    contract: ClassificationContract,
    event_documents: Iterable[dict[str, Any]] | None = None,
    evidence_catalogs: Mapping[int, Mapping[str, str]] | None = None,
) -> list[str]:
    """验收决定形状、全覆盖、重复纪律和 D 类排除规则。"""
    if not isinstance(data, dict):
        return ["分类决定不是对象"]
    reasons: list[str] = []
    if set(data) != ROOT_KEYS:
        reasons.append("分类决定根字段错误")
    if data.get("schema_version") != contract.decision_schema_version:
        reasons.append("分类决定schema错误")
    if data.get("run_id") != run_id:
        reasons.append("分类决定run_id错误")
    if data.get("rules_sha256") != contract.rules_sha256:
        reasons.append("分类规则SHA不一致")
    decisions = data.get("decisions")
    if not isinstance(decisions, list):
        return sorted(set(reasons + ["decisions不是数组"]))

    seen: list[str] = []
    dispositions: dict[str, str] = {}
    duplicate_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    single_policy = contract.policies["single_observation"]
    trigger_rule_id = str(single_policy["trigger_rule_id"])
    forbidden_primary = str(single_policy["forbidden_primary_type"])
    a_assertion = str(single_policy["a_assertion"])
    allowed_rule_ids = set(contract.rule_registry["allowed"])
    required_by_primary = contract.rule_registry["required_by_primary"]
    discarded_required = str(contract.rule_registry["discarded_required"])
    fallback_policy = contract.policies.get("fallback_audit")
    source_scope_policy = contract.policies.get("source_scope")
    expected_decision_keys = (
        DECISION_KEYS | V1_2_EXTRA_DECISION_KEYS
        if fallback_policy is not None or source_scope_policy is not None
        else DECISION_KEYS
    )

    for index, decision in enumerate(decisions, 1):
        label = f"决定{index}"
        if not isinstance(decision, dict):
            reasons.append(f"{label}不是对象")
            continue
        if set(decision) != expected_decision_keys:
            reasons.append(f"{label}字段不等于固定合同")
        event_id = decision.get("event_id")
        if not isinstance(event_id, str) or event_id not in event_ids:
            reasons.append(f"{label}事件ID不存在")
            continue
        if _event_chapter(event_id) is None:
            reasons.append(f"{event_id}事件ID格式非法")
        seen.append(event_id)
        disposition = decision.get("disposition")
        dispositions[event_id] = str(disposition)
        if disposition not in DISPOSITIONS:
            reasons.append(f"{event_id}处置状态非法")
        matched = decision.get("matched_types")
        if not isinstance(matched, list) or any(value not in {"A", "B", "C", "D"} for value in matched):
            reasons.append(f"{event_id}命中类型非法")
            matched = []
        if len(matched) != len(set(matched)):
            reasons.append(f"{event_id}命中类型重复")
        primary = decision.get("primary_type")
        rule_ids = decision.get("rule_ids")
        if not isinstance(rule_ids, list) or not rule_ids or any(not isinstance(value, str) for value in rule_ids):
            reasons.append(f"{event_id}缺规则编号")
            rule_ids = []
        unknown_rule_ids = sorted(set(rule_ids) - allowed_rule_ids)
        if unknown_rule_ids:
            reasons.append(f"{event_id}含未登记规则编号：{unknown_rule_ids}")
        basis = decision.get("basis")
        if not isinstance(basis, str) or nonspace_chars(basis) < 8:
            reasons.append(f"{event_id}分类依据过短")
        fields = decision.get("fields")
        related = decision.get("related_event_ids")
        duplicate_group = decision.get("duplicate_group")
        conflict_reason = decision.get("conflict_reason")
        if not isinstance(related, list) or any(not isinstance(value, str) for value in related):
            reasons.append(f"{event_id}关联事件ID非法")
            related = []
        if event_id in related:
            reasons.append(f"{event_id}关联事件自指")
        if duplicate_group is not None:
            if not isinstance(duplicate_group, str) or not duplicate_group.strip():
                reasons.append(f"{event_id}重复组非法")
            else:
                duplicate_groups[duplicate_group].append(decision)
        if not isinstance(conflict_reason, str):
            reasons.append(f"{event_id}冲突说明不是字符串")
            conflict_reason = ""

        if fallback_policy is not None:
            required_dispositions = set(fallback_policy.get("required_dispositions") or [])
            required_types = set(fallback_policy.get("required_types") or [])
            minimum_reason = int(fallback_policy.get("reason_min_nonspace") or 0)
            required_audit_rule = str(fallback_policy.get("required_rule_id") or "")
            type_audit = decision.get("type_audit")
            if disposition in required_dispositions:
                if not isinstance(type_audit, dict) or set(type_audit) != required_types:
                    reasons.append(f"{event_id}四类兜底审计不完整")
                else:
                    for kind in sorted(required_types):
                        value = type_audit.get(kind)
                        if not isinstance(value, str) or nonspace_chars(value) < minimum_reason:
                            reasons.append(f"{event_id}{kind}类兜底理由过短")
                if required_audit_rule not in rule_ids:
                    reasons.append(f"{event_id}缺四类兜底审计规则{required_audit_rule}")
                d_exclusion_rule = str(fallback_policy.get("d_exclusion_rule_id") or "")
                if d_exclusion_rule in rule_ids:
                    companion_by_disposition = _mapping(
                        fallback_policy.get("companion_rule_by_disposition"),
                        "fallback_audit.companion_rule_by_disposition",
                    )
                    companion = str(companion_by_disposition.get(str(disposition)) or "")
                    if not companion or companion not in rule_ids:
                        reasons.append(
                            f"{event_id}{d_exclusion_rule}只准排除D，缺最终处置规则{companion}"
                        )
            elif type_audit != {}:
                reasons.append(f"{event_id}已分类项不应携带兜底审计")
            d_exclusion_rule = str(fallback_policy.get("d_exclusion_rule_id") or "")
            classified_d_minimum = int(
                fallback_policy.get("classified_d_conflict_min_nonspace") or 0
            )
            if (
                disposition == "classified"
                and primary == "D"
                and d_exclusion_rule in rule_ids
                and nonspace_chars(conflict_reason) < classified_d_minimum
            ):
                reasons.append(f"{event_id}D类同时带{d_exclusion_rule}却未说明排除的句中成分")

        if source_scope_policy is not None:
            source_level = decision.get("source_level")
            scope_mode = decision.get("scope_mode")
            allowed_sources = set(source_scope_policy.get("allowed_source_levels") or [])
            allowed_scopes = set(source_scope_policy.get("allowed_scope_modes") or [])
            if source_level is not None and source_level not in allowed_sources:
                reasons.append(f"{event_id}来源等级非法")
            if scope_mode is not None and scope_mode not in allowed_scopes:
                reasons.append(f"{event_id}适用范围模式非法")
            if disposition != "classified" and (source_level is not None or scope_mode is not None):
                reasons.append(f"{event_id}未分类或丢弃却带来源／范围标记")
            source_required = _mapping(
                source_scope_policy.get("source_required_by_rule"),
                "source_scope.source_required_by_rule",
            )
            scope_required = _mapping(
                source_scope_policy.get("scope_required_by_rule"),
                "source_scope.scope_required_by_rule",
            )
            primary_required = _mapping(
                source_scope_policy.get("primary_required_by_rule"),
                "source_scope.primary_required_by_rule",
            )
            for rule_id, expected_source in source_required.items():
                if rule_id in rule_ids and source_level != expected_source:
                    reasons.append(f"{event_id}{rule_id}缺来源等级{expected_source}")
            for rule_id, expected_scope in scope_required.items():
                if rule_id in rule_ids and scope_mode != expected_scope:
                    reasons.append(f"{event_id}{rule_id}缺适用范围{expected_scope}")
            for rule_id, expected_primary in primary_required.items():
                if rule_id in rule_ids and primary != expected_primary:
                    reasons.append(f"{event_id}{rule_id}主类型必须为{expected_primary}")
            if source_level is not None and not any(rule_id in rule_ids for rule_id in source_required):
                reasons.append(f"{event_id}来源等级没有对应规则编号")
            if scope_mode is not None and not any(rule_id in rule_ids for rule_id in scope_required):
                reasons.append(f"{event_id}适用范围没有对应规则编号")

        if disposition == "classified":
            if primary not in {"A", "B", "C", "D"} or primary not in matched:
                reasons.append(f"{event_id}主类型未包含在命中类型")
            required = set(anchor_kit.TYPE_REQUIRED_FIELDS.get(str(primary), ()))
            if not isinstance(fields, dict) or set(fields) != required:
                reasons.append(f"{event_id}分类字段与主类型不一致")
            elif any(not isinstance(value, str) or not value.strip() for value in fields.values()):
                reasons.append(f"{event_id}分类字段为空")
            if decision.get("assertion") not in anchor_kit.ALLOWED_ASSERTION:
                reasons.append(f"{event_id}事实等级非法")
            if primary == "D" and "D-01" not in rule_ids:
                reasons.append(f"{event_id}D类缺D-01")
            required_rule = required_by_primary.get(primary)
            if required_rule not in rule_ids:
                reasons.append(f"{event_id}{primary}类缺基础规则{required_rule}")
        else:
            if primary is not None or matched:
                reasons.append(f"{event_id}未分类或丢弃却带类型")
            if decision.get("assertion") is not None:
                reasons.append(f"{event_id}未分类或丢弃却带事实等级")
            if fields != {} or related:
                reasons.append(f"{event_id}未分类或丢弃却带记录字段")
            if disposition == "discarded" and discarded_required not in rule_ids:
                reasons.append(f"{event_id}丢弃项缺{discarded_required}")

        if (len(matched) > 1 or duplicate_group is not None) and nonspace_chars(conflict_reason) < 8:
            reasons.append(f"{event_id}重叠或重复未写冲突说明")
        if trigger_rule_id in rule_ids:
            if (
                disposition != "classified"
                or "D" not in matched
                or primary == forbidden_primary
                or primary != "A"
                or decision.get("assertion") != a_assertion
            ):
                reasons.append(f"{event_id}D-03只允许命中D后降为A/{a_assertion}")

    if len(seen) != len(set(seen)):
        reasons.append("分类决定事件ID重复")
    if set(seen) != event_ids:
        reasons.append(
            f"分类决定未一对一覆盖事件：missing={sorted(event_ids - set(seen))},"
            f"extra={sorted(set(seen) - event_ids)}"
        )

    classified_ids = {event_id for event_id, value in dispositions.items() if value == "classified"}
    for decision in decisions:
        if not isinstance(decision, dict) or decision.get("disposition") != "classified":
            continue
        event_id = str(decision.get("event_id"))
        event_chapter = _event_chapter(event_id)
        related_ids = decision.get("related_event_ids")
        if not isinstance(related_ids, list) or any(
            not isinstance(value, str) for value in related_ids
        ):
            continue
        for related_id in related_ids:
            if related_id not in classified_ids:
                reasons.append(f"{event_id}关联未成记录的事件")
                continue
            related_chapter = _event_chapter(related_id)
            if event_chapter is None or related_chapter is None:
                reasons.append(f"{event_id}关联事件ID格式非法：{related_id}")
            elif related_chapter != event_chapter:
                reasons.append(f"{event_id}关联跨章事件")

    duplicate_policy = contract.policies["duplicate_group"]
    minimum = int(duplicate_policy["minimum_members"])
    classified_exactly = int(duplicate_policy["classified_exactly"])
    discarded_rule = str(duplicate_policy["discarded_rule_id"])
    for group, rows in duplicate_groups.items():
        if len(rows) < minimum:
            reasons.append(f"重复组{group}成员不足{minimum}")
        classified_rows = [row for row in rows if row.get("disposition") == "classified"]
        if len(classified_rows) != classified_exactly:
            reasons.append(f"重复组{group}必须恰留{classified_exactly}条成记录")
        for row in rows:
            if row.get("disposition") == "classified":
                continue
            if row.get("disposition") != "discarded" or discarded_rule not in (row.get("rule_ids") or []):
                reasons.append(f"重复组{group}非代表项必须用{discarded_rule}丢弃")

    if contract.current_regression_cases:
        reasons.extend(
            current_regression_reasons(
                data,
                contract=contract,
                event_documents=event_documents,
                evidence_catalogs=evidence_catalogs,
            )
        )

    return sorted(set(reasons))


def _regression_reasons_for_cases(
    data: dict[str, Any],
    *,
    cases: Iterable[Mapping[str, Any]],
    label: str,
) -> list[str]:
    """按合同登记的事件映射检查决定；不猜语义，只验钉住字段。"""
    decisions = data.get("decisions") if isinstance(data, dict) else None
    if not isinstance(decisions, list):
        return [f"{label}决定缺decisions"]
    decision_map = {
        row.get("event_id"): row
        for row in decisions
        if isinstance(row, dict) and isinstance(row.get("event_id"), str)
    }
    reasons: list[str] = []
    for case in cases:
        case_id = str(case.get("case_id") or "unnamed")
        kind = case.get("kind")
        if kind == "duplicate_group":
            group = case.get("duplicate_group")
            for event_id in case.get("event_ids") or []:
                row = decision_map.get(event_id)
                if row is None:
                    reasons.append(f"{case_id}缺事件{event_id}")
                elif row.get("duplicate_group") != group:
                    reasons.append(f"{case_id}事件{event_id}重复组漂移")
            expected_rows = [case.get("winner"), *(case.get("losers") or [])]
            for expected in expected_rows:
                if not isinstance(expected, dict):
                    continue
                event_id = expected.get("event_id")
                actual = decision_map.get(event_id)
                if actual is None:
                    continue
                for field in ("disposition", "primary_type"):
                    if field in expected and actual.get(field) != expected.get(field):
                        reasons.append(f"{case_id}事件{event_id}的{field}漂移")
        elif kind == "single_observation":
            event_id = case.get("event_id")
            actual = decision_map.get(event_id)
            if actual is None:
                reasons.append(f"{case_id}缺事件{event_id}")
                continue
            expected = _mapping(case.get("expected"), f"{case_id}.expected")
            for field, value in expected.items():
                if actual.get(field) != value:
                    reasons.append(f"{case_id}事件{event_id}的{field}漂移")
            required = set(case.get("required_rule_ids") or [])
            if not required.issubset(set(actual.get("rule_ids") or [])):
                reasons.append(f"{case_id}事件{event_id}缺规则编号")
        elif kind == "event_decision":
            event_id = case.get("event_id")
            actual = decision_map.get(event_id)
            if actual is None:
                reasons.append(f"{case_id}缺事件{event_id}")
                continue
            expected = _mapping(case.get("expected"), f"{case_id}.expected")
            for field, value in expected.items():
                if actual.get(field) != value:
                    reasons.append(f"{case_id}事件{event_id}的{field}漂移")
            required = set(case.get("required_rule_ids") or [])
            if not required.issubset(set(actual.get("rule_ids") or [])):
                reasons.append(f"{case_id}事件{event_id}缺规则编号")
        else:
            reasons.append(f"{case_id}回归案例类型非法")
    return sorted(set(reasons))


def regression_reasons(
    data: dict[str, Any],
    *,
    contract: ClassificationContract,
) -> list[str]:
    """只给批准参考件使用：钉住 Z00n 三项纠错，避免日后回退。"""
    return _regression_reasons_for_cases(
        data,
        cases=contract.regression_cases,
        label="批准回归",
    )


def current_regression_reasons(
    data: dict[str, Any],
    *,
    contract: ClassificationContract,
    event_documents: Iterable[dict[str, Any]] | None = None,
    evidence_catalogs: Mapping[int, Mapping[str, str]] | None = None,
) -> list[str]:
    """验当前提取的语义案例；旧合同仍兼容顺序编号载体。"""
    if not _uses_stable_semantic_identities(contract.current_regression_cases):
        return _regression_reasons_for_cases(
            data,
            cases=contract.current_regression_cases,
            label="当前决定回归",
        )
    if event_documents is None:
        return ["当前决定回归缺稳定语义身份所需的中性事件文档"]
    if evidence_catalogs is None:
        return ["当前决定回归缺稳定语义身份所需的冻结证据目录"]
    audit = resolve_current_regression_cases(
        event_documents,
        contract=contract,
        evidence_catalogs=evidence_catalogs,
    )
    reasons = list(audit["resolution_reasons"])
    cases_by_id = {
        str(case.get("case_id") or "unnamed"): case
        for case in contract.current_regression_cases
    }
    for case_audit in audit["cases"]:
        if case_audit["status"] != "applicable":
            continue
        source_case = cases_by_id[case_audit["case_id"]]
        resolved_by_identity = {
            row["semantic_id"]: row["resolved_event_id"]
            for row in case_audit["identities"]
        }
        kind = source_case.get("kind")
        if kind == "duplicate_group":
            winner: list[dict[str, Any]] = []
            losers: list[dict[str, Any]] = []
            event_ids: list[str] = []
            for identity in source_case.get("identities") or []:
                semantic_id = str(identity.get("semantic_id"))
                expected = dict(_mapping(identity.get("expected"), "稳定身份expected"))
                role = expected.pop("role", None)
                expected["event_id"] = resolved_by_identity[semantic_id]
                event_ids.append(expected["event_id"])
                if role == "winner":
                    winner.append(expected)
                elif role == "loser":
                    losers.append(expected)
            if len(winner) != 1 or len(losers) != len(event_ids) - 1:
                reasons.append(f"{case_audit['case_id']}稳定身份胜负角色非法")
                continue
            runtime_case = {
                "case_id": case_audit["case_id"],
                "kind": kind,
                "duplicate_group": source_case.get("duplicate_group"),
                "event_ids": event_ids,
                "winner": winner[0],
                "losers": losers,
            }
        elif kind in {"single_observation", "event_decision"}:
            identities = source_case.get("identities") or []
            if len(identities) != 1:
                reasons.append(f"{case_audit['case_id']}稳定身份数量非法")
                continue
            identity = identities[0]
            runtime_case = {
                "case_id": case_audit["case_id"],
                "kind": kind,
                "event_id": resolved_by_identity[str(identity.get("semantic_id"))],
                "expected": identity.get("expected") or {},
                "required_rule_ids": identity.get("required_rule_ids") or [],
            }
        else:
            reasons.append(f"{case_audit['case_id']}回归案例类型非法")
            continue
        reasons.extend(
            _regression_reasons_for_cases(
                data,
                cases=[runtime_case],
                label="当前决定回归",
            )
        )
    return sorted(set(reasons))


def _uses_stable_semantic_identities(cases: Iterable[Mapping[str, Any]]) -> bool:
    values = list(cases)
    return bool(values) and all(isinstance(case.get("identities"), list) for case in values)


def _normalized_semantic_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def stable_anchor_quote_sha256(event: Mapping[str, Any], anchor_ids: Iterable[str]) -> str:
    """给指定原句锚生成与事件编号无关的内容指纹。"""
    wanted = set(anchor_ids)
    rows = [
        {
            "anchor_id": str(anchor.get("anchor_id")),
            "chapter": anchor.get("chapter"),
            "quote": str(anchor.get("quote") or ""),
        }
        for anchor in event.get("anchors") or []
        if isinstance(anchor, dict) and anchor.get("anchor_id") in wanted
    ]
    rows.sort(key=lambda row: (str(row["chapter"]), row["anchor_id"], row["quote"]))
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_catalog_anchor_quote_sha256(
    chapter: int,
    catalog: Mapping[str, str],
    anchor_ids: Iterable[str],
) -> str:
    """从独立冻结证据目录计算相同格式的原句锚指纹。"""
    rows = [
        {"anchor_id": anchor_id, "chapter": chapter, "quote": str(catalog[anchor_id])}
        for anchor_id in anchor_ids
        if anchor_id in catalog
    ]
    rows.sort(key=lambda row: (str(row["chapter"]), row["anchor_id"], row["quote"]))
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_identity_matches(event: Mapping[str, Any], locator: Mapping[str, Any]) -> bool:
    chapter = locator.get("chapter")
    if not isinstance(chapter, int) or _event_chapter(event.get("event_id")) != chapter:
        return False
    anchor_ids = locator.get("anchor_ids")
    if not isinstance(anchor_ids, list) or not anchor_ids or any(
        not isinstance(value, str) for value in anchor_ids
    ):
        raise ZBatchError("稳定语义身份anchor_ids非法")
    present = {
        anchor.get("anchor_id")
        for anchor in event.get("anchors") or []
        if isinstance(anchor, dict)
    }
    if not set(anchor_ids).issubset(present):
        return False
    expected_fingerprint = locator.get("anchor_quote_sha256")
    if not isinstance(expected_fingerprint, str) or len(expected_fingerprint) != 64:
        raise ZBatchError("稳定语义身份原句锚指纹非法")
    if stable_anchor_quote_sha256(event, anchor_ids) != expected_fingerprint:
        return False
    text = _normalized_semantic_text(event.get("event")) + "".join(
        _normalized_semantic_text(anchor.get("quote"))
        for anchor in event.get("anchors") or []
        if isinstance(anchor, dict)
    )
    term_groups = locator.get("term_groups") or []
    if not isinstance(term_groups, list) or any(
        not isinstance(group, list)
        or not group
        or any(not isinstance(term, str) or not _normalized_semantic_text(term) for term in group)
        for group in term_groups
    ):
        raise ZBatchError("稳定语义身份term_groups非法")
    return all(
        any(_normalized_semantic_text(term) in text for term in group)
        for group in term_groups
    )


def _event_has_locator_anchors(event: Mapping[str, Any], locator: Mapping[str, Any]) -> bool:
    anchor_ids = locator.get("anchor_ids") or []
    present = {
        anchor.get("anchor_id")
        for anchor in event.get("anchors") or []
        if isinstance(anchor, dict)
    }
    return bool(anchor_ids) and set(anchor_ids).issubset(present)


def resolve_current_regression_cases(
    event_documents: Iterable[dict[str, Any]],
    *,
    contract: ClassificationContract,
    evidence_catalogs: Mapping[int, Mapping[str, str]],
) -> dict[str, Any]:
    """把合同中的稳定语义身份解析为本轮内部事件编号，并留下逐项审计。"""
    event_map, events_by_chapter = index_events(event_documents)
    cases: list[dict[str, Any]] = []
    resolution_reasons: list[str] = []
    claimed_event_ids: dict[str, str] = {}
    for case in contract.current_regression_cases:
        case_id = str(case.get("case_id") or "unnamed")
        identities = case.get("identities")
        if not isinstance(identities, list) or not identities:
            resolution_reasons.append(f"{case_id}缺稳定语义身份")
            continue
        identity_rows: list[dict[str, Any]] = []
        for identity in identities:
            identity = _mapping(identity, f"{case_id}.identity")
            semantic_id = str(identity.get("semantic_id") or "")
            locator = _mapping(identity.get("locator"), f"{semantic_id}.locator")
            chapter = locator.get("chapter")
            anchor_ids = locator.get("anchor_ids") or []
            catalog = evidence_catalogs.get(chapter, {})
            missing_catalog_anchors = sorted(set(anchor_ids) - set(catalog))
            catalog_fingerprint = stable_catalog_anchor_quote_sha256(
                int(chapter),
                catalog,
                anchor_ids,
            )
            catalog_error: str | None = None
            if missing_catalog_anchors:
                catalog_error = (
                    f"{case_id}稳定身份{semantic_id}冻结证据目录缺锚：{missing_catalog_anchors}"
                )
            elif catalog_fingerprint != locator.get("anchor_quote_sha256"):
                catalog_error = f"{case_id}稳定身份{semantic_id}冻结证据目录原句指纹漂移"
            chapter_events = events_by_chapter.get(chapter, [])
            anchor_candidates = [
                event
                for event in chapter_events
                if _event_has_locator_anchors(event, locator)
            ]
            fingerprint_drift = [
                event["event_id"]
                for event in anchor_candidates
                if stable_anchor_quote_sha256(event, locator.get("anchor_ids") or [])
                != locator.get("anchor_quote_sha256")
            ]
            candidates = [
                event["event_id"]
                for event in chapter_events
                if _stable_identity_matches(event, locator)
            ]
            if catalog_error is not None:
                status = "catalog_drift"
                resolved_event_id = None
                resolution_reasons.append(catalog_error)
            elif fingerprint_drift:
                status = "source_drift"
                resolved_event_id = None
                resolution_reasons.append(
                    f"{case_id}稳定身份{semantic_id}冻结原句锚指纹漂移：{sorted(fingerprint_drift)}"
                )
            elif len(candidates) == 1:
                status = "resolved"
                resolved_event_id: str | None = candidates[0]
                previous = claimed_event_ids.get(resolved_event_id)
                if previous is not None and previous != semantic_id:
                    status = "ambiguous"
                    resolution_reasons.append(
                        f"{case_id}稳定身份{semantic_id}与{previous}误绑同一事件{resolved_event_id}"
                    )
                else:
                    claimed_event_ids[resolved_event_id] = semantic_id
            elif not candidates:
                status = "not_observed"
                resolved_event_id = None
            else:
                status = "ambiguous"
                resolved_event_id = None
                resolution_reasons.append(
                    f"{case_id}稳定身份{semantic_id}命中多事件：{sorted(candidates)}"
                )
            identity_rows.append(
                {
                    "semantic_id": semantic_id,
                    "legacy_event_id": identity.get("legacy_event_id"),
                    "status": status,
                    "resolved_event_id": resolved_event_id,
                    "candidate_event_ids": sorted(candidates),
                    "locator": copy.deepcopy(dict(locator)),
                }
            )
        statuses = {row["status"] for row in identity_rows}
        if statuses & {"ambiguous", "source_drift", "catalog_drift"}:
            case_status = "resolution_error"
        elif statuses == {"resolved"}:
            case_status = "applicable"
        elif statuses == {"not_observed"}:
            case_status = "not_observed"
        else:
            case_status = "partially_not_observed"
        cases.append(
            {
                "case_id": case_id,
                "kind": case.get("kind"),
                "status": case_status,
                "identities": identity_rows,
            }
        )
    return {
        "schema_version": "z-stable-semantic-regression-resolution-v1",
        "carrier": "chapter+frozen-anchor-quote-fingerprint+semantic-term-groups",
        "sequential_event_id_scope": "run_local_only",
        "event_total": len(event_map),
        "evidence_catalog_chapter_total": len(evidence_catalogs),
        "cases": cases,
        "resolution_reasons": sorted(set(resolution_reasons)),
    }


def _coverage_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for kind in "ABCD":
        ids = [record["id"] for record in records if record["type"] == kind]
        result[kind] = {
            "status": "emitted" if ids else "none",
            "record_ids": ids,
            "reason": f"主控按独立规则逐事件裁定；{kind}类共{len(ids)}条，未命中者均在处置账显式登记。",
        }
    return result


def compile_records(
    event_documents: Iterable[dict[str, Any]],
    decisions_data: dict[str, Any],
    *,
    contract: ClassificationContract,
    evidence_catalogs: Mapping[int, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """把已批准决定确定性编译成 A/B/C/D 记录和兼容候选外壳。"""
    documents = list(event_documents)
    event_map, events_by_chapter = index_events(documents)
    reasons = decision_reasons(
        decisions_data,
        run_id=str(decisions_data.get("run_id") or ""),
        event_ids=set(event_map),
        contract=contract,
        event_documents=documents,
        evidence_catalogs=evidence_catalogs,
    )
    if reasons:
        raise ZBatchError(f"主控分类决定无效：{reasons}")
    decision_map = {row["event_id"]: row for row in decisions_data["decisions"]}
    counters: Counter[tuple[int, str]] = Counter()
    record_id_map: dict[str, str] = {}
    for chapter in sorted(events_by_chapter):
        for event in events_by_chapter[chapter]:
            decision = decision_map[event["event_id"]]
            if decision["disposition"] != "classified":
                continue
            kind = decision["primary_type"]
            counters[(chapter, kind)] += 1
            record_id_map[event["event_id"]] = f"{kind}-C{chapter:04d}-{counters[(chapter, kind)]:02d}"

    records: list[dict[str, Any]] = []
    records_by_chapter: dict[int, list[dict[str, Any]]] = defaultdict(list)
    resolved_decisions: list[dict[str, Any]] = []
    raw_anchor_refs: dict[tuple[int, str], list[str]] = defaultdict(list)
    for chapter in sorted(events_by_chapter):
        for event in events_by_chapter[chapter]:
            event_id = event["event_id"]
            decision = copy.deepcopy(decision_map[event_id])
            decision["record_id"] = record_id_map.get(event_id)
            resolved_decisions.append(decision)
            for anchor in event.get("anchors") or []:
                if isinstance(anchor, dict) and isinstance(anchor.get("anchor_id"), str):
                    raw_anchor_refs[(chapter, anchor["anchor_id"])].append(event_id)
            if decision["disposition"] != "classified":
                continue
            kind = decision["primary_type"]
            record = {
                "id": record_id_map[event_id],
                "type": kind,
                **copy.deepcopy(decision["fields"]),
                "status": "开",
                "type_state": TYPE_STATE[kind],
                "assertion": decision["assertion"],
                "related_ids": [record_id_map[value] for value in decision["related_event_ids"]],
                "anchors": copy.deepcopy(event["anchors"]),
                "_source_event_id": event_id,
                "_classification_rule_ids": copy.deepcopy(decision["rule_ids"]),
            }
            if decision.get("source_level") is not None:
                record["source_level"] = decision["source_level"]
            if decision.get("scope_mode") is not None:
                record["scope_mode"] = decision["scope_mode"]
            records.append(record)
            records_by_chapter[chapter].append(record)

    envelopes: dict[int, dict[str, Any]] = {}
    for chapter, chapter_records in sorted(records_by_chapter.items()):
        envelope = {
            "schema_version": "z-candidate-v1",
            "chapter": chapter,
            "decision_markers": [
                f"分类权由主控规则执行；弱模型仅交中性事件。规则SHA={contract.rules_sha256}"
            ],
            "coverage_audit": _coverage_audit(chapter_records),
            "records": chapter_records,
        }
        envelope_reasons = candidate_envelope.validate_candidate_envelope(envelope, chapter)
        if envelope_reasons:
            raise ZBatchError(f"第 {chapter} 章分类后兼容外壳无效：{envelope_reasons}")
        envelopes[chapter] = envelope

    matched_type_conflicts = [row for row in resolved_decisions if len(row["matched_types"]) > 1]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in resolved_decisions:
        if row.get("duplicate_group"):
            groups[str(row["duplicate_group"])].append(row)
    duplicate_rows = [
        {
            "duplicate_group": group,
            "event_ids": [row["event_id"] for row in rows],
            "primary_types": sorted({str(row.get("primary_type")) for row in rows if row.get("primary_type")}),
            "cross_type": len({str(row.get("primary_type")) for row in rows if row.get("primary_type")}) > 1,
        }
        for group, rows in sorted(groups.items())
    ]
    shared_event_anchors = [
        {
            "chapter": chapter,
            "anchor_id": anchor_id,
            "event_ids": event_ids,
            "primary_types": sorted(
                {
                    str(decision_map[event_id].get("primary_type"))
                    for event_id in event_ids
                    if decision_map[event_id].get("primary_type")
                }
            ),
        }
        for (chapter, anchor_id), event_ids in sorted(raw_anchor_refs.items())
        if len(set(event_ids)) > 1
    ]
    overlap = candidate_envelope.cross_type_anchor_overlap(records)
    dispositions = Counter(row["disposition"] for row in resolved_decisions)
    type_total = Counter(row["type"] for row in records)
    conflicts = {
        "matched_type_conflicts": matched_type_conflicts,
        "declared_duplicate_groups": duplicate_rows,
        "raw_shared_anchor_groups": shared_event_anchors,
        "emitted_cross_type_anchor_overlap": overlap,
        "gate_note": "跨类型重复闸须结合本账人审；共享锚只作诊断，不自动等于语义重复。",
    }
    current_regression_audit = (
        resolve_current_regression_cases(
            documents,
            contract=contract,
            evidence_catalogs=evidence_catalogs or {},
        )
        if _uses_stable_semantic_identities(contract.current_regression_cases)
        else {
            "schema_version": "z-legacy-sequential-regression-resolution-v1",
            "carrier": "legacy_sequential_event_id",
            "sequential_event_id_scope": "legacy_contract_only",
            "cases": [],
            "resolution_reasons": [],
        }
    )
    current_reasons = current_regression_reasons(
        decisions_data,
        contract=contract,
        event_documents=documents,
        evidence_catalogs=evidence_catalogs,
    )
    metrics = {
        "event_total": len(event_map),
        "classified_total": dispositions["classified"],
        "unclassified_total": dispositions["unclassified"],
        "discarded_total": dispositions["discarded"],
        "candidate_total": len(records),
        "by_type": {kind: type_total[kind] for kind in "ABCD"},
        "classification_model_calls": 0,
        "matched_type_conflict_count": len(matched_type_conflicts),
        "declared_duplicate_group_count": len(duplicate_rows),
        "cross_type_semantic_duplicate_groups": sum(1 for row in duplicate_rows if row["cross_type"]),
        "raw_shared_anchor_groups": len(shared_event_anchors),
        "emitted_cross_type_shared_anchor_count": overlap["shared_anchor_count"],
        "emitted_cross_type_pair_count": overlap["cross_type_pair_count"],
        "rules_sha256": contract.rules_sha256,
        "current_regression_case_count": len(contract.current_regression_cases),
        "current_regression_gate_pass": not current_reasons,
        "current_regression_applicable_count": sum(
            row.get("status") == "applicable"
            for row in current_regression_audit.get("cases") or []
        ),
        "current_regression_not_observed_count": sum(
            row.get("status") in {"not_observed", "partially_not_observed"}
            for row in current_regression_audit.get("cases") or []
        ),
    }
    return {
        "event_map": event_map,
        "events_by_chapter": events_by_chapter,
        "records": records,
        "records_by_chapter": dict(records_by_chapter),
        "resolved_decisions": resolved_decisions,
        "candidate_envelopes": envelopes,
        "classification_conflicts": conflicts,
        "current_regression_audit": current_regression_audit,
        "metrics": metrics,
    }


def validate_compiled_records(
    compilation: dict[str, Any],
    *,
    chapters: dict[int, dict[str, Any]],
    catalogs: dict[int, dict[str, str]],
) -> dict[str, Any]:
    """用独立 anchor_kit 核验编译记录，返回逐条明细和机械有效率。"""
    rows: list[dict[str, Any]] = []
    for record in compilation.get("records") or []:
        event_id = str(record.get("_source_event_id") or "")
        try:
            chapter = int(event_id.split("-")[1][1:])
        except (IndexError, ValueError):
            chapter = -1
        public_record = {key: value for key, value in record.items() if not key.startswith("_")}
        reasons, anchor_checks = anchor_kit.validate_record(
            public_record,
            chapters,
            expected_chapter=chapter,
            evidence_catalog=catalogs.get(chapter),
        )
        rows.append(
            {
                "source_chapter": chapter,
                "source_event_id": event_id,
                "record": record,
                "valid": not reasons,
                "reasons": reasons,
                "anchor_checks": anchor_checks,
            }
        )
    valid = [row for row in rows if row["valid"]]
    invalid = [row for row in rows if not row["valid"]]
    return {
        "rows": rows,
        "valid_records": [row["record"] for row in valid],
        "invalid_rows": invalid,
        "valid_total": len(valid),
        "invalid_total": len(invalid),
        "anchor_valid_rate": round(len(valid) / len(rows), 6) if rows else 0.0,
    }

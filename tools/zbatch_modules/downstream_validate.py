"""模块 8：thin、fold、answer、compare 的纯机械校验。"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .anchor_kit import validate_anchors, validate_record
from .errors import ZBatchError


ALLOWED_DIFF_LABELS = {"我对它错", "它对我错", "等价", "待裁"}
QUESTION_TYPES = {"回指", "转线", "伸缩", "梯度"}
ANSWER_STATUSES = {"answered", "not_applicable"}
NOT_APPLICABLE_QUESTION_TYPES = {"转线", "伸缩"}
REQUIRED_QUESTION_SPECS: dict[str, dict[str, Any]] = {
    "backtrace-ch0010": {"question_type": "回指", "target_chapter": 10},
    "backtrace-ch0020": {"question_type": "回指", "target_chapter": 20},
    "cross-line": {"question_type": "转线", "target_chapter": None},
    "compression": {"question_type": "伸缩", "target_chapter": None},
    "gradient": {"question_type": "梯度", "target_chapter": "sample_end"},
}
GRADIENT_BUCKETS: dict[str, tuple[int, int | None]] = {
    "0-1": (0, 1),
    "2-5": (2, 5),
    "6-20": (6, 20),
    "21-50": (21, 50),
    "50+": (51, None),
}
COMPARABILITY_VALUES = {
    "same_question",
    "different_question",
    "different_scope",
    "missing_ours",
    "missing_silver",
    "insufficient_evidence",
}


DownstreamContractError = ZBatchError


def derived_records_valid(
    records: Any,
    chapters: dict[int, dict[str, Any]],
    allowed_source_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    seen: Counter[str] = Counter()
    if not isinstance(records, list):
        raise DownstreamContractError("压薄 records 不是数组")
    for record in records:
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            seen[record["id"]] += 1
    for record in records:
        reasons, anchor_checks = validate_record(
            record,
            chapters,
            require_sources=True,
            allowed_source_ids=allowed_source_ids,
        )
        if isinstance(record, dict) and seen.get(record.get("id"), 0) > 1:
            reasons = sorted(set(reasons + ["ID重复"]))
        row = {"record": record, "reasons": reasons, "anchor_checks": anchor_checks}
        if reasons:
            invalid.append(row)
        else:
            valid.append(record)
    return valid, invalid


def record_anchor_chapters(record: Any) -> set[int]:
    if not isinstance(record, dict):
        return set()
    return {
        int(anchor["chapter"])
        for anchor in record.get("anchors") or []
        if isinstance(anchor, dict) and isinstance(anchor.get("chapter"), int)
    }


def validate_macro(
    macro: Any,
    chapters: dict[int, dict[str, Any]],
    ledger_map: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    if not isinstance(macro, dict):
        return ["宏节点不是对象"], []
    reasons: list[str] = []
    if not isinstance(macro.get("id"), str) or not macro.get("id"):
        reasons.append("宏节点缺ID")
    if not isinstance(macro.get("summary"), str) or not macro.get("summary"):
        reasons.append("宏节点缺摘要")
    source_ids = macro.get("source_record_ids")
    if not isinstance(source_ids, list) or not source_ids:
        reasons.append("宏节点缺来源ID")
        source_ids = []
    else:
        if any(not isinstance(value, str) for value in source_ids):
            reasons.append("宏节点来源ID不是字符串")
        normalized_source_ids = [str(value) for value in source_ids]
        if len(normalized_source_ids) != len(set(normalized_source_ids)):
            reasons.append("宏节点来源ID重复")
        if any(value not in ledger_map for value in normalized_source_ids):
            reasons.append("宏节点来源ID不存在")
        source_ids = normalized_source_ids
    if macro.get("status") not in {"开", "收"}:
        reasons.append("宏节点态非法")

    roles = macro.get("roles")
    if not isinstance(roles, dict):
        reasons.append("宏节点缺因果角色")
    else:
        root_id = roles.get("root_cause_id")
        turning_ids = roles.get("turning_point_ids")
        result_id = roles.get("result_id")
        open_exit_ids = roles.get("open_exit_ids")
        if not isinstance(root_id, str) or not root_id:
            reasons.append("宏节点缺根因ID")
        if not isinstance(turning_ids, list):
            reasons.append("宏节点转折ID不是数组")
            turning_ids = []
        elif any(not isinstance(value, str) for value in turning_ids):
            reasons.append("宏节点转折ID不是字符串")
        if not isinstance(result_id, str) or not result_id:
            reasons.append("宏节点缺结果ID")
        if not isinstance(open_exit_ids, list):
            reasons.append("宏节点开放口ID不是数组")
            open_exit_ids = []
        elif any(not isinstance(value, str) for value in open_exit_ids):
            reasons.append("宏节点开放口ID不是字符串")
        role_ids = [value for value in [root_id, result_id, *turning_ids, *open_exit_ids] if isinstance(value, str)]
        if any(value not in source_ids for value in role_ids):
            reasons.append("因果角色ID未纳入宏来源")
        if any(value not in ledger_map for value in role_ids):
            reasons.append("因果角色ID不存在")
        if macro.get("status") == "收" and open_exit_ids:
            reasons.append("已收宏仍带开放口")
        for value in open_exit_ids:
            record = ledger_map.get(value)
            if isinstance(record, dict) and record.get("status") != "开":
                reasons.append("开放口记录不是开态")

        role_chapters: dict[str, int] = {}
        for value in role_ids:
            anchor_chapters = record_anchor_chapters(ledger_map.get(value))
            if anchor_chapters:
                role_chapters[value] = min(anchor_chapters)
            else:
                reasons.append("因果角色缺可计算章号")
        if isinstance(root_id, str) and isinstance(result_id, str):
            root_chapter = role_chapters.get(root_id)
            result_record_chapters = record_anchor_chapters(ledger_map.get(result_id))
            result_chapter = max(result_record_chapters) if result_record_chapters else None
            ordered_turning_chapters = [role_chapters[value] for value in turning_ids if value in role_chapters]
            if (
                root_chapter is not None
                and result_chapter is not None
                and (
                    root_chapter > result_chapter
                    or any(chapter < root_chapter or chapter > result_chapter for chapter in ordered_turning_chapters)
                    or ordered_turning_chapters != sorted(ordered_turning_chapters)
                )
            ):
                reasons.append("宏节点因果时序倒置")
    anchor_reasons, checks = validate_anchors(macro.get("anchors"), chapters)
    reasons.extend(anchor_reasons)
    return sorted(set(reasons)), checks


def enforce_fold_gate(metrics: dict[str, Any]) -> None:
    if metrics.get("macros_invalid") or not metrics.get("coverage_pass"):
        raise DownstreamContractError("折叠视图含无效宏节点或覆盖漂移，拒绝进入答题阶段")


def enforce_answer_gate(metrics: dict[str, Any]) -> None:
    if not metrics.get("four_type_pass"):
        raise DownstreamContractError("五题四型答题校验未通过，拒绝进入银标对撞")


def enforce_compare_gate(metrics: dict[str, Any]) -> None:
    if not metrics.get("comparison_pass"):
        raise DownstreamContractError("银标 diff 为空、题目未覆盖或可比性自相矛盾，拒绝生成正式回执")


def gradient_bucket_for_distance(distance: int) -> str | None:
    for bucket, (minimum, maximum) in GRADIENT_BUCKETS.items():
        if distance >= minimum and (maximum is None or distance <= maximum):
            return bucket
    return None


def validate_gradient_points(
    item: dict[str, Any],
    ledger_map: dict[str, dict[str, Any]],
    sample_end: int,
) -> list[str]:
    reasons: list[str] = []
    if item.get("current_chapter") != sample_end:
        reasons.append("梯度当前章不是样本末章")
    points = item.get("gradient_points")
    if not isinstance(points, list):
        return reasons + ["梯度落点不是数组"]
    bucket_counts = Counter(
        point.get("bucket")
        for point in points
        if isinstance(point, dict) and point.get("bucket") in GRADIENT_BUCKETS
    )
    missing = sorted(set(GRADIENT_BUCKETS) - set(bucket_counts))
    if missing:
        reasons.append("梯度档位缺失")
    if any(count != 1 for count in bucket_counts.values()) or len(points) != len(GRADIENT_BUCKETS):
        reasons.append("梯度档位重复或多余")

    available: dict[str, set[tuple[str, int]]] = defaultdict(set)
    for record_id, record in ledger_map.items():
        for chapter in record_anchor_chapters(record):
            distance = sample_end - chapter
            if distance < 0:
                continue
            bucket = gradient_bucket_for_distance(distance)
            if bucket:
                available[bucket].add((record_id, chapter))

    point_record_ids: set[str] = set()
    for point in points:
        if not isinstance(point, dict):
            reasons.append("梯度落点不是对象")
            continue
        bucket = point.get("bucket")
        if bucket not in GRADIENT_BUCKETS:
            reasons.append("梯度档位非法")
            continue
        status = point.get("status")
        record_ids = point.get("record_ids")
        if status == "no_sample":
            if point.get("chapter") is not None or point.get("distance") is not None:
                reasons.append("无样本档位不应填写章号或步距")
            if record_ids not in ([], None):
                reasons.append("无样本档位不应引用记录")
            if available.get(bucket):
                reasons.append(f"梯度档位{bucket}有真实样本却写无样本")
            continue
        if status != "sample":
            reasons.append("梯度落点状态非法")
            continue
        chapter = point.get("chapter")
        distance = point.get("distance")
        if not isinstance(chapter, int) or not isinstance(distance, int):
            reasons.append("梯度样本缺章号或步距")
            continue
        actual_distance = sample_end - chapter
        if distance != actual_distance:
            reasons.append("梯度步距计算错误")
        if gradient_bucket_for_distance(actual_distance) != bucket:
            reasons.append("梯度步距落错档")
        if not isinstance(record_ids, list) or not record_ids:
            reasons.append("梯度样本缺记录ID")
            continue
        for record_id in record_ids:
            if not isinstance(record_id, str):
                reasons.append("梯度记录ID不是字符串")
                continue
            if record_id not in ledger_map:
                reasons.append("梯度记录ID不存在")
                continue
            point_record_ids.add(str(record_id))
            if chapter not in record_anchor_chapters(ledger_map[record_id]):
                reasons.append("梯度记录没有目标章锚")

    item_record_ids = item.get("record_ids")
    if isinstance(item_record_ids, list) and set(map(str, item_record_ids)) != point_record_ids:
        reasons.append("梯度总记录ID与各档落点不一致")
    return sorted(set(reasons))


def validate_answer_items(
    items: Any,
    chapters: dict[int, dict[str, Any]],
    ledger_map: dict[str, dict[str, Any]],
    sample_end: int,
    fold: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(items, list):
        raise DownstreamContractError("四型答题 items 不是数组")
    rows: list[dict[str, Any]] = []
    seen_types: set[str] = set()
    seen_question_ids: Counter[str] = Counter(
        str(item.get("question_id"))
        for item in items
        if isinstance(item, dict) and isinstance(item.get("question_id"), str)
    )
    not_applicable_types: set[str] = set()
    fold = fold if isinstance(fold, dict) else {}
    fold_cross_line_ids = {
        str(value) for value in fold.get("cross_line_exits") or [] if isinstance(value, str)
    }
    fold_macro_map = {
        str(macro.get("id")): macro
        for macro in fold.get("macros") or []
        if isinstance(macro, dict) and isinstance(macro.get("id"), str)
    }
    for item in items:
        reasons: list[str] = []
        checks: list[dict[str, Any]] = []
        if not isinstance(item, dict):
            reasons.append("答题项不是对象")
        else:
            question_id = item.get("question_id")
            question_type = item.get("question_type")
            spec = REQUIRED_QUESTION_SPECS.get(str(question_id))
            if spec is None:
                reasons.append("题目身份非法")
            else:
                expected_target = sample_end if spec["target_chapter"] == "sample_end" else spec["target_chapter"]
                if question_type != spec["question_type"]:
                    reasons.append("题目身份与题型不一致")
                if item.get("target_chapter") != expected_target:
                    reasons.append("目标章与题目身份不一致")
            if isinstance(question_id, str) and seen_question_ids[question_id] > 1:
                reasons.append("题目身份重复")
            if question_type not in QUESTION_TYPES:
                reasons.append("题型非法")
            else:
                seen_types.add(question_type)
            if not isinstance(item.get("question"), str) or not item.get("question"):
                reasons.append("题目为空")
            status = item.get("status")
            if status not in ANSWER_STATUSES:
                reasons.append("答题状态非法")
            if not isinstance(item.get("answer_markdown"), str) or not item.get("answer_markdown"):
                reasons.append("答案为空")
            record_ids = item.get("record_ids")
            if status == "not_applicable":
                if question_type in QUESTION_TYPES:
                    not_applicable_types.add(question_type)
                if question_type not in NOT_APPLICABLE_QUESTION_TYPES:
                    reasons.append("该题型不允许无样本")
                if not isinstance(item.get("not_applicable_reason"), str) or not item.get("not_applicable_reason"):
                    reasons.append("无样本缺原因")
                if record_ids not in ([], None):
                    reasons.append("无样本不应引用记录")
                if item.get("anchors") not in ([], None):
                    reasons.append("无样本不应带锚")
                if question_id == "cross-line" and fold_cross_line_ids:
                    reasons.append("折叠视图已有跨线出口却写无样本")
                if question_id == "compression" and fold_macro_map:
                    reasons.append("折叠视图已有宏节点却写无样本")
            else:
                if not isinstance(record_ids, list) or not record_ids:
                    reasons.append("缺结构记录ID")
                elif any(not isinstance(value, str) for value in record_ids):
                    reasons.append("结构记录ID不是字符串")
                elif any(value not in ledger_map for value in record_ids):
                    reasons.append("结构记录ID不存在")
                anchor_reasons, checks = validate_anchors(item.get("anchors"), chapters)
                reasons.extend(anchor_reasons)
                if spec and question_id in {"backtrace-ch0010", "backtrace-ch0020"}:
                    target = int(spec["target_chapter"])
                    answer_anchor_chapters = {
                        anchor.get("chapter")
                        for anchor in item.get("anchors") or []
                        if isinstance(anchor, dict)
                    }
                    if target not in answer_anchor_chapters:
                        reasons.append("回指答案没有目标章原锚")
                if question_id == "gradient":
                    reasons.extend(validate_gradient_points(item, ledger_map, sample_end))
                if question_id == "cross-line":
                    if not fold_cross_line_ids:
                        reasons.append("折叠视图没有跨线出口却强答转线")
                    elif not isinstance(record_ids, list) or not (set(map(str, record_ids)) & fold_cross_line_ids):
                        reasons.append("转线答案未引用折叠视图跨线出口")
                if question_id == "compression":
                    macro_id = item.get("macro_id")
                    if not isinstance(macro_id, str) or macro_id not in fold_macro_map:
                        reasons.append("伸缩答案缺有效宏节点ID")
                    else:
                        macro_source_ids = set(map(str, fold_macro_map[macro_id].get("source_record_ids") or []))
                        if not isinstance(record_ids, list) or set(map(str, record_ids)) != macro_source_ids:
                            reasons.append("伸缩答案记录ID与宏来源不一致")
        rows.append({"item": item, "valid": not reasons, "reasons": sorted(set(reasons)), "anchor_checks": checks})
    missing_types = sorted(QUESTION_TYPES - seen_types)
    missing_question_ids = sorted(set(REQUIRED_QUESTION_SPECS) - set(seen_question_ids))
    unexpected_question_ids = sorted(set(seen_question_ids) - set(REQUIRED_QUESTION_SPECS))
    duplicate_question_ids = sorted(key for key, count in seen_question_ids.items() if count > 1)
    all_rows_valid = all(row["valid"] for row in rows)
    question_set_pass = not missing_question_ids and not unexpected_question_ids and not duplicate_question_ids
    metrics = {
        "items_total": len(rows),
        "items_valid": sum(1 for row in rows if row["valid"]),
        "items_invalid": sum(1 for row in rows if not row["valid"]),
        "question_types_present": sorted(seen_types),
        "question_types_missing": missing_types,
        "question_ids_present": sorted(seen_question_ids),
        "question_ids_missing": missing_question_ids,
        "question_ids_unexpected": unexpected_question_ids,
        "question_ids_duplicate": duplicate_question_ids,
        "not_applicable_types": sorted(not_applicable_types),
        "question_set_pass": question_set_pass,
        "five_question_pass": question_set_pass and not missing_types and all_rows_valid,
        "four_type_pass": question_set_pass and not missing_types and all_rows_valid,
    }
    return rows, metrics


def validate_compare_items(
    items: Any,
    answer_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(items, list):
        raise DownstreamContractError("银标 diff items 不是数组")
    answer_map = {
        str(item.get("question_id")): item
        for item in answer_items
        if isinstance(item, dict) and item.get("question_id") in REQUIRED_QUESTION_SPECS
    }
    comparison_counts = Counter(
        str(item.get("comparison_id"))
        for item in items
        if isinstance(item, dict) and isinstance(item.get("comparison_id"), str)
    )
    ours_counts = Counter(
        str(item.get("ours_question_id"))
        for item in items
        if isinstance(item, dict) and isinstance(item.get("ours_question_id"), str)
    )
    rows: list[dict[str, Any]] = []
    labels = Counter()
    comparability_counts = Counter()
    for index, item in enumerate(items):
        reasons: list[str] = []
        if not isinstance(item, dict):
            rows.append({"index": index, "item": item, "valid": False, "reasons": ["对撞项不是对象"]})
            continue
        comparison_id = item.get("comparison_id")
        if not isinstance(comparison_id, str) or not comparison_id:
            reasons.append("对撞项缺ID")
        elif comparison_counts[comparison_id] > 1:
            reasons.append("对撞项ID重复")
        ours_question_id = item.get("ours_question_id")
        if ours_question_id is not None and ours_question_id not in answer_map:
            reasons.append("本地题目身份不存在")
        elif isinstance(ours_question_id, str) and ours_counts[ours_question_id] > 1:
            reasons.append("同一本地题目被重复对撞")
        comparability = item.get("comparability")
        if comparability not in COMPARABILITY_VALUES:
            reasons.append("可比性非法")
        else:
            comparability_counts[comparability] += 1
        label = item.get("label")
        if label not in ALLOWED_DIFF_LABELS:
            reasons.append("对撞标签非法")
        else:
            labels[label] += 1
        if comparability != "same_question" and label != "待裁":
            reasons.append("非同题对撞只能待裁")
        if comparability == "same_question" and ours_question_id is None:
            reasons.append("同题对撞缺本地题目身份")
        if ours_question_id is None and label != "待裁":
            reasons.append("缺本地答案只能待裁")
        ours_record_ids = item.get("ours_record_ids")
        if not isinstance(ours_record_ids, list):
            reasons.append("本地记录ID不是数组")
            ours_record_ids = []
        elif any(not isinstance(value, str) for value in ours_record_ids):
            reasons.append("本地记录ID不是字符串")
        if ours_question_id in answer_map:
            answer = answer_map[str(ours_question_id)]
            allowed_record_ids = set(map(str, answer.get("record_ids") or []))
            if any(str(value) not in allowed_record_ids for value in ours_record_ids):
                reasons.append("对撞引用了本题答案之外的记录")
            if label != "待裁" and (answer.get("status") != "answered" or not ours_record_ids):
                reasons.append("确定性标签缺本地已答证据")
        elif ours_record_ids:
            reasons.append("无本地题目却引用本地记录")
        if not isinstance(item.get("silver_section"), str) or not item.get("silver_section"):
            reasons.append("缺银标小节")
        if not isinstance(item.get("reason"), str) or not item.get("reason"):
            reasons.append("缺对撞理由")
        rows.append({"index": index, "item": item, "valid": not reasons, "reasons": sorted(set(reasons))})

    expected_ids = set(answer_map)
    missing_question_ids = sorted(expected_ids - set(ours_counts))
    duplicate_question_ids = sorted(key for key, count in ours_counts.items() if count > 1)
    comparison_pass = bool(items) and not missing_question_ids and not duplicate_question_ids and all(
        row["valid"] for row in rows
    )
    metrics = {
        "diff_items": len(items),
        "items_valid": sum(1 for row in rows if row["valid"]),
        "items_invalid": sum(1 for row in rows if not row["valid"]),
        "labels": {label: labels[label] for label in ["我对它错", "它对我错", "等价", "待裁"]},
        "comparability": {value: comparability_counts[value] for value in sorted(COMPARABILITY_VALUES)},
        "ours_question_ids_missing": missing_question_ids,
        "ours_question_ids_duplicate": duplicate_question_ids,
        "comparison_pass": comparison_pass,
    }
    return rows, metrics

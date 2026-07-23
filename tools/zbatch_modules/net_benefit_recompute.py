from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


class NetBenefitError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_inside_root(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    path.relative_to(root.resolve())
    return path


def load_pinned_json(root: Path, spec: dict[str, Any], label: str) -> tuple[Path, Any]:
    path = resolve_inside_root(root, str(spec.get("path") or ""))
    if not path.is_file():
        raise NetBenefitError(f"{label} 不存在：{path}")
    actual = sha256_file(path)
    expected = str(spec.get("sha256") or "")
    if actual != expected:
        raise NetBenefitError(f"{label} SHA 漂移：expected={expected}, actual={actual}")
    return path, read_json(path)


def records_by_id(document: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    rows = document.get("records")
    if not isinstance(rows, list):
        raise NetBenefitError(f"{label} records 不是列表")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        record_id = str(row.get("id") or "")
        if not record_id or record_id in result:
            raise NetBenefitError(f"{label} 记录编号缺失或重复：{record_id}")
        result[record_id] = row
    return result


def anchor_pairs(record: dict[str, Any]) -> set[tuple[int, str]]:
    return {
        (int(anchor["chapter"]), str(anchor["anchor_id"]))
        for anchor in record.get("anchors", [])
    }


def semantic_record_payload(record: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in record.items()
        if key not in {"id", "_classification_rule_ids"}
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def map_preserved_records(
    old_records: dict[str, dict[str, Any]],
    new_records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    new_by_payload: dict[str, list[str]] = {}
    for record_id, record in new_records.items():
        new_by_payload.setdefault(semantic_record_payload(record), []).append(record_id)
    ambiguous = {
        payload: ids
        for payload, ids in new_by_payload.items()
        if len(ids) != 1
    }
    if ambiguous:
        raise NetBenefitError(f"新候选存在无法唯一映射的同构记录：{ambiguous}")

    rows = []
    for old_id, old_record in old_records.items():
        matches = new_by_payload.get(semantic_record_payload(old_record), [])
        if len(matches) != 1:
            raise NetBenefitError(f"旧候选记录未在新候选中唯一保留：{old_id}, matches={matches}")
        rows.append(
            {
                "old_record_id": old_id,
                "new_record_id": matches[0],
                "renumbered": old_id != matches[0],
                "type": old_record["type"],
                "source_event_id": old_record.get("_source_event_id"),
                "anchors": [
                    {"chapter": chapter, "anchor_id": anchor_id}
                    for chapter, anchor_id in sorted(anchor_pairs(old_record))
                ],
                "semantic_payload_equal": True,
            }
        )
    return {
        "old_record_total": len(old_records),
        "preserved_record_total": len(rows),
        "all_old_records_preserved": len(rows) == len(old_records),
        "renumbered_records": [row for row in rows if row["renumbered"]],
        "record_map": rows,
    }


def validate_recovery_record(record: dict[str, Any], expectation: dict[str, Any]) -> dict[str, Any]:
    record_id = str(expectation["record_id"])
    if record.get("type") != expectation.get("type"):
        raise NetBenefitError(f"{record_id} 类型不符")
    if record.get("_source_event_id") != expectation.get("source_event_id"):
        raise NetBenefitError(f"{record_id} 来源事件不符")
    expected_anchors = {
        (int(row["chapter"]), str(row["anchor_id"]))
        for row in expectation.get("anchors", [])
    }
    actual_anchors = anchor_pairs(record)
    if actual_anchors != expected_anchors:
        raise NetBenefitError(
            f"{record_id} 锚不符：expected={sorted(expected_anchors)}, actual={sorted(actual_anchors)}"
        )
    anchor_text = "\n".join(str(anchor.get("quote") or "") for anchor in record.get("anchors", []))
    missing_anchor_fragments = [
        fragment
        for fragment in expectation.get("required_anchor_fragments", [])
        if fragment not in anchor_text
    ]
    if missing_anchor_fragments:
        raise NetBenefitError(f"{record_id} 原锚引文缺少短句：{missing_anchor_fragments}")
    serialized = json.dumps(record, ensure_ascii=False, sort_keys=True)
    missing_record_fragments = [
        fragment
        for fragment in expectation.get("required_record_fragments", [])
        if fragment not in serialized
    ]
    if missing_record_fragments:
        raise NetBenefitError(f"{record_id} 成品字段缺少短句：{missing_record_fragments}")
    for key, expected in expectation.get("exact_fields", {}).items():
        if record.get(key) != expected:
            raise NetBenefitError(f"{record_id} 字段 {key} 不符")
    return {
        "record_id": record_id,
        "type": record["type"],
        "source_event_id": record["_source_event_id"],
        "anchors": [
            {"chapter": chapter, "anchor_id": anchor_id}
            for chapter, anchor_id in sorted(actual_anchors)
        ],
        "required_anchor_fragments": list(expectation.get("required_anchor_fragments", [])),
        "required_record_fragments": list(expectation.get("required_record_fragments", [])),
        "validated": True,
    }


def validate_absent_spans(
    candidate_records: dict[str, dict[str, Any]],
    spans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reverse: dict[tuple[int, str], list[str]] = {}
    for record_id, record in candidate_records.items():
        for pair in anchor_pairs(record):
            reverse.setdefault(pair, []).append(record_id)
    results = []
    for span in spans:
        chapter = int(span["chapter"])
        anchors = [str(value) for value in span["anchor_ids"]]
        hits = {
            anchor_id: sorted(reverse.get((chapter, anchor_id), []))
            for anchor_id in anchors
            if reverse.get((chapter, anchor_id))
        }
        if hits:
            raise NetBenefitError(f"应保留为缺口的锚已进入候选成品：{span['id']} {hits}")
        results.append(
            {
                "id": span["id"],
                "label": span["label"],
                "chapter": chapter,
                "anchor_ids": anchors,
                "candidate_record_hits": {},
                "still_absent": True,
            }
        )
    return results


def loss_rows_by_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result = {str(row.get("id") or ""): row for row in rows}
    if "" in result or len(result) != len(rows):
        raise NetBenefitError(f"{label} 失分组编号缺失或重复")
    return result


def validate_differential_semantic_audit(
    root: Path,
    audit_path: Path,
    audit_doc: dict[str, Any],
    old_gate_path: Path,
    old_gate_doc: dict[str, Any],
    old_candidate_path: Path,
    candidate_path: Path,
    old_candidate_records: dict[str, dict[str, Any]],
    candidate_records: dict[str, dict[str, Any]],
    semantic_preservation: dict[str, Any],
) -> dict[str, Any]:
    """钉住旧账与新增四条的人工语义审计范围，不拿分类指标自证三闸。"""

    if audit_doc.get("schema_version") != "z-differential-semantic-audit-v1":
        raise NetBenefitError("不支持的差分语义审计版本")

    inputs = audit_doc.get("inputs")
    if not isinstance(inputs, dict):
        raise NetBenefitError("差分语义审计缺少输入钉子")

    expected_paths = {
        "old_candidate": old_candidate_path,
        "new_candidate": candidate_path,
        "old_human_gate_audit": old_gate_path,
    }
    for key, expected_path in expected_paths.items():
        spec = inputs.get(key)
        if not isinstance(spec, dict):
            raise NetBenefitError(f"差分语义审计缺少 {key} 输入")
        pinned_path = resolve_inside_root(root, str(spec.get("path") or ""))
        if pinned_path != expected_path.resolve():
            raise NetBenefitError(f"差分语义审计 {key} 路径与正式输入不一致")
        actual_sha = sha256_file(pinned_path)
        if actual_sha != str(spec.get("sha256") or ""):
            raise NetBenefitError(f"差分语义审计 {key} SHA 漂移")

    authority_spec = inputs.get("classification_authority")
    if not isinstance(authority_spec, dict):
        raise NetBenefitError("差分语义审计缺少分类权威件")
    authority_path = resolve_inside_root(root, str(authority_spec.get("path") or ""))
    if not authority_path.is_file() or sha256_file(authority_path) != authority_spec.get("sha256"):
        raise NetBenefitError("分类权威件不存在或 SHA 漂移")
    authority_excerpt = str(authority_spec.get("authority_excerpt") or "")
    if not authority_excerpt or authority_excerpt not in authority_path.read_text(encoding="utf-8"):
        raise NetBenefitError("分类权威件不含差分审计登记的原句")

    catalog_spec = inputs.get("chapter13_catalog")
    if not isinstance(catalog_spec, dict):
        raise NetBenefitError("差分语义审计缺少第13章证据目录")
    catalog_path, catalog_doc = load_pinned_json(root, catalog_spec, "第13章证据目录")

    duplicate_gate = old_gate_doc.get("duplicate_gate")
    wrong_d_gate = old_gate_doc.get("wrong_d_gate")
    if not isinstance(duplicate_gate, dict) or not isinstance(wrong_d_gate, dict):
        raise NetBenefitError("旧118条人审账缺少重复闸或错误D闸")
    if duplicate_gate.get("human_cross_type_duplicate_groups") != []:
        raise NetBenefitError("旧118条人审账仍有跨类型语义重复组")
    if int(duplicate_gate.get("count", -1)) != 0 or duplicate_gate.get("passed") is not True:
        raise NetBenefitError("旧118条人审重复闸未过")
    if int(wrong_d_gate.get("count", -1)) != 0 or wrong_d_gate.get("passed") is not True:
        raise NetBenefitError("旧118条人审错误D闸未过")

    scope = audit_doc.get("scope")
    if not isinstance(scope, dict):
        raise NetBenefitError("差分语义审计缺少范围")
    expected_scope = {
        "old_candidate_records": len(old_candidate_records),
        "new_candidate_records": len(candidate_records),
        "differential_record_total": 4,
        "new_vs_old_pair_total": 4 * len(old_candidate_records),
        "new_vs_new_pair_total": 6,
    }
    for key, expected in expected_scope.items():
        if int(scope.get(key, -1)) != expected:
            raise NetBenefitError(f"差分语义审计范围 {key} 不符")
    if scope.get("not_a_default_promotion") is not True:
        raise NetBenefitError("差分语义审计没有钉死非升默认边界")

    preserved_new_ids = {
        str(row["new_record_id"])
        for row in semantic_preservation["record_map"]
    }
    actual_addition_ids = set(candidate_records) - preserved_new_ids
    differential_rows = audit_doc.get("differential_records")
    if not isinstance(differential_rows, list):
        raise NetBenefitError("差分语义审计新增记录不是列表")
    audited_addition_ids = {str(row.get("record_id") or "") for row in differential_rows}
    if "" in audited_addition_ids or len(audited_addition_ids) != len(differential_rows):
        raise NetBenefitError("差分语义审计新增记录编号缺失或重复")
    if actual_addition_ids != audited_addition_ids:
        raise NetBenefitError(
            f"新增记录未被差分审计完整覆盖：actual={sorted(actual_addition_ids)}, "
            f"audited={sorted(audited_addition_ids)}"
        )

    for row in differential_rows:
        record_id = str(row["record_id"])
        record = candidate_records[record_id]
        actual_anchor_ids = sorted(
            f"{int(anchor['chapter'])}:{anchor['anchor_id']}"
            for anchor in record.get("anchors", [])
        )
        if row.get("type") != record.get("type"):
            raise NetBenefitError(f"差分审计 {record_id} 类型与正式记录不符")
        if row.get("source_event_id") != record.get("_source_event_id"):
            raise NetBenefitError(f"差分审计 {record_id} 来源事件与正式记录不符")
        if sorted(str(value) for value in row.get("anchor_ids", [])) != actual_anchor_ids:
            raise NetBenefitError(f"差分审计 {record_id} 锚范围与正式记录不符")
        if int(row.get("compared_against_old_record_total", -1)) != len(old_candidate_records):
            raise NetBenefitError(f"差分审计 {record_id} 没有覆盖旧118条")
        if row.get("semantic_duplicate_old_record_ids") != []:
            raise NetBenefitError(f"差分审计 {record_id} 命中旧记录语义重复")
        if row.get("cross_type_duplicate") is not False:
            raise NetBenefitError(f"差分审计 {record_id} 跨类型重复闸未过")
        if not str(row.get("semantic_head") or "") or not str(row.get("consumer") or ""):
            raise NetBenefitError(f"差分审计 {record_id} 缺少事实头或使用方说明")

    pair_rows = audit_doc.get("new_record_pairwise_audit")
    if not isinstance(pair_rows, list):
        raise NetBenefitError("差分语义审计缺少新增记录逐对账")
    expected_pairs = {
        frozenset((left, right))
        for index, left in enumerate(sorted(actual_addition_ids))
        for right in sorted(actual_addition_ids)[index + 1 :]
    }
    actual_pairs: set[frozenset[str]] = set()
    for row in pair_rows:
        pair = frozenset((str(row.get("left") or ""), str(row.get("right") or "")))
        if len(pair) != 2 or pair in actual_pairs:
            raise NetBenefitError("新增记录逐对账存在空编号、自比或重复对")
        actual_pairs.add(pair)
        if row.get("cross_type_duplicate") is not False:
            raise NetBenefitError(f"新增记录逐对账发现跨类型重复：{sorted(pair)}")
    if actual_pairs != expected_pairs:
        raise NetBenefitError("新增四条没有完成全部六组逐对审计")
    delayed_pair = frozenset(("C-C0013-01", "D-C0013-02"))
    delayed_row = next((row for row in pair_rows if frozenset((row["left"], row["right"])) == delayed_pair), None)
    if delayed_row is None or delayed_row.get("relationship") != "related_not_duplicate":
        raise NetBenefitError("延迟复发 C/D 双收边界没有明确登记为相关但不重复")

    cross_gate = audit_doc.get("cross_type_duplicate_gate")
    if not isinstance(cross_gate, dict):
        raise NetBenefitError("差分语义审计缺少跨类型重复合并闸")
    if any(int(cross_gate.get(key, -1)) != 0 for key in ("old_118_count", "differential_count", "combined_count")):
        raise NetBenefitError("跨类型重复合并闸不是0")
    if cross_gate.get("passed") is not True:
        raise NetBenefitError("跨类型重复合并闸未过")

    new_d_ids = sorted(
        record_id
        for record_id in actual_addition_ids
        if candidate_records[record_id].get("type") == "D"
    )
    if new_d_ids != ["D-C0013-02"]:
        raise NetBenefitError(f"新增D范围超出差分审计：{new_d_ids}")
    d_record = candidate_records["D-C0013-02"]
    d_gate = audit_doc.get("new_d_gate")
    if not isinstance(d_gate, dict):
        raise NetBenefitError("差分语义审计缺少新增D审计")
    if d_gate.get("record_id") != "D-C0013-02" or d_gate.get("wrong_d") is not False:
        raise NetBenefitError("新增D没有被明确裁为非错误D")
    for field in ("source_level", "scope_mode"):
        if d_gate.get(field) != d_record.get(field):
            raise NetBenefitError(f"新增D审计字段 {field} 与正式记录不符")
    if d_record.get("source_level") != "述" or d_record.get("scope_mode") != "probabilistic":
        raise NetBenefitError("新增D不是述源概率规律")

    catalog_by_id = {
        str(row.get("anchor_id") or ""): row
        for row in catalog_doc.get("entries", [])
    }
    expected_supplemental = [
        {
            "chapter": 13,
            "anchor_id": anchor_id,
            "quote": str(catalog_by_id.get(anchor_id, {}).get("quote") or ""),
        }
        for anchor_id in ("E0129", "E0130")
    ]
    if any(not row["quote"] for row in expected_supplemental):
        raise NetBenefitError("第13章证据目录缺少 E0129 或 E0130")
    if d_gate.get("supplemental_original_text_evidence") != expected_supplemental:
        raise NetBenefitError("新增D补充原文与固定证据目录不一致")
    if "再次降临" not in expected_supplemental[1]["quote"]:
        raise NetBenefitError("E0130 没有支持延迟复发结论")
    if not str(d_gate.get("record_anchor_limitation") or ""):
        raise NetBenefitError("新增D成品少挂 E0130 的留口被抹掉")

    wrong_gate = audit_doc.get("wrong_d_gate")
    boundary = audit_doc.get("audit_boundary")
    if not isinstance(wrong_gate, dict) or not isinstance(boundary, dict):
        raise NetBenefitError("差分语义审计缺少错误D合并闸或边界")
    if any(int(wrong_gate.get(key, -1)) != 0 for key in ("old_118_count", "differential_wrong_d_count", "combined_count")):
        raise NetBenefitError("错误D合并闸不是0")
    if wrong_gate.get("passed") is not True:
        raise NetBenefitError("错误D合并闸未过")
    if boundary.get("known_record_anchor_limitation_open") is not True:
        raise NetBenefitError("新增D成品锚留口没有保持开启")
    if any(boundary.get(key) is not False for key in ("default_promoted", "x02_x04_started", "outbox_written")):
        raise NetBenefitError("差分语义审计越过供数边界")

    return {
        "audit_path": str(audit_path.relative_to(root)),
        "audit_sha256": sha256_file(audit_path),
        "old_human_gate_audit_path": str(old_gate_path.relative_to(root)),
        "old_human_gate_audit_sha256": sha256_file(old_gate_path),
        "classification_authority_path": str(authority_path.relative_to(root)),
        "classification_authority_sha256": sha256_file(authority_path),
        "classification_authority_excerpt": authority_excerpt,
        "chapter13_catalog_path": str(catalog_path.relative_to(root)),
        "chapter13_catalog_sha256": sha256_file(catalog_path),
        "differential_record_ids": sorted(actual_addition_ids),
        "new_vs_old_pair_total": 4 * len(old_candidate_records),
        "new_vs_new_pair_total": len(actual_pairs),
        "cross_type_duplicate_count": int(cross_gate["combined_count"]),
        "wrong_d_count": int(wrong_gate["combined_count"]),
        "new_d_ids": new_d_ids,
        "new_d_supplemental_original_text_evidence": expected_supplemental,
        "new_d_record_anchor_limitation": d_gate["record_anchor_limitation"],
        "known_record_anchor_limitation_open": True,
    }


def recompute(config: dict[str, Any], root: Path) -> dict[str, Any]:
    if config.get("schema_version") != "z-net-benefit-recompute-config-v1.2":
        raise NetBenefitError("不支持的配置版本")
    if config.get("model_calls") != 0:
        raise NetBenefitError("T3 必须钉死为 0 模型调用")
    if config.get("candidate_pool_eligible") is not False or config.get("outbox_allowed") is not False:
        raise NetBenefitError("T3 供数件不得进入候选池或 outbox")

    baseline_path, baseline_doc = load_pinned_json(root, config["baseline"], "Z00u 基线")
    candidate_path, candidate_doc = load_pinned_json(root, config["candidate"], "Z00w2 候选")
    old_candidate_path, old_candidate_doc = load_pinned_json(
        root, config["old_candidate"], "Z00s 旧候选"
    )
    prior_path, prior_doc = load_pinned_json(root, config["prior_alignment"], "Z00u 旧对齐账")
    metrics_path, metrics_doc = load_pinned_json(root, config["candidate_metrics"], "Z00w2 分类指标")
    old_gate_path, old_gate_doc = load_pinned_json(
        root, config["old_human_gate_audit"], "Z00s 旧118条人审三闸账"
    )
    audit_path, audit_doc = load_pinned_json(
        root, config["differential_semantic_audit"], "Z00w2 新增四条差分语义审计"
    )

    baseline_records = records_by_id(baseline_doc, "Z00u")
    candidate_records = records_by_id(candidate_doc, "Z00w2")
    old_candidate_records = records_by_id(old_candidate_doc, "Z00s")
    if len(baseline_records) != 70 or len(candidate_records) != 122 or len(old_candidate_records) != 118:
        raise NetBenefitError("基线或候选记录数不符")
    semantic_preservation = map_preserved_records(old_candidate_records, candidate_records)
    differential_audit = validate_differential_semantic_audit(
        root,
        audit_path,
        audit_doc,
        old_gate_path,
        old_gate_doc,
        old_candidate_path,
        candidate_path,
        old_candidate_records,
        candidate_records,
        semantic_preservation,
    )

    protected_results = []
    for rel_path, expected in config.get("protected_sha256", {}).items():
        path = resolve_inside_root(root, rel_path)
        actual = sha256_file(path) if path.is_file() else None
        protected_results.append(
            {"path": rel_path, "expected": expected, "actual": actual, "ok": actual == expected}
        )
        if actual != expected:
            raise NetBenefitError(f"受保护件漂移：{rel_path}")

    recovery_evidence = []
    recovered_record_ids: list[str] = []
    for recovery in config["recoveries"]:
        validated_records = []
        for expectation in recovery["candidate_records"]:
            record_id = str(expectation["record_id"])
            if record_id not in candidate_records:
                raise NetBenefitError(f"恢复记录不存在：{record_id}")
            validated_records.append(validate_recovery_record(candidate_records[record_id], expectation))
            recovered_record_ids.append(record_id)
        recovery_evidence.append(
            {
                "recovery_id": recovery["recovery_id"],
                "label": recovery["label"],
                "candidate_records": validated_records,
                "covers": copy.deepcopy(recovery["covers"]),
                "counting_boundary": recovery["counting_boundary"],
            }
        )
    if len(recovered_record_ids) != len(set(recovered_record_ids)):
        raise NetBenefitError("同一候选记录被多个恢复项重复使用")

    absent_results = validate_absent_spans(candidate_records, config["remaining_absent_spans"])

    old_net = prior_doc["net_benefit"]
    main_old_losses = loss_rows_by_id(old_net["main"]["lost_units"], "主估")
    strict_old_losses = loss_rows_by_id(old_net["strict"]["lost_units"], "严格")
    main_recovered = list(config["loss_transforms"]["main"]["recovered_ids"])
    strict_recovered = list(config["loss_transforms"]["strict"]["recovered_ids"])
    if not set(main_recovered) <= set(main_old_losses):
        raise NetBenefitError("主估恢复组不在 Z00u 旧账")
    if not set(strict_recovered) <= set(strict_old_losses):
        raise NetBenefitError("严格恢复组不在 Z00u 旧账")
    main_remaining = [row for row in old_net["main"]["lost_units"] if row["id"] not in main_recovered]
    strict_remaining = [row for row in old_net["strict"]["lost_units"] if row["id"] not in strict_recovered]

    wide_old_losses = list(old_net["wide"]["lost_units"])
    wide_transform = config["loss_transforms"]["wide"]
    if wide_old_losses != wide_transform["expected_old_lost_units"]:
        raise NetBenefitError("宽松旧失分组与预写账不一致")
    wide_remaining = list(wide_transform["remaining_lost_units"])

    main_new_units = copy.deepcopy(old_net["main"]["new_units"])
    strict_new_units = copy.deepcopy(old_net["strict"]["new_units"])
    wide_new_units = copy.deepcopy(old_net["wide"]["new_units"])
    mapped_old_ids = {row["old_record_id"] for row in semantic_preservation["record_map"]}
    main_record_refs = []
    for unit in main_new_units:
        for reference in unit.get("candidate_records", []):
            prefix, record_id = str(reference).split(":", 1)
            if prefix != "Z00s" or record_id not in mapped_old_ids:
                raise NetBenefitError(f"主估新增组引用未通过旧新同构映射：{reference}")
            main_record_refs.append(record_id)
    main_unit_ids = {row["id"] for row in main_new_units}
    for unit in strict_new_units:
        if not set(unit.get("from_main", [])) <= main_unit_ids:
            raise NetBenefitError(f"严格新增组引用未知主估组：{unit['id']}")
    semantic_preservation["main_new_record_reference_total"] = len(main_record_refs)
    semantic_preservation["main_new_record_references_all_preserved"] = True
    semantic_preservation["strict_new_groups_all_backed_by_preserved_main_groups"] = True
    semantic_preservation["wide_new_groups_preserved_because_all_118_old_records_are_semantically_preserved"] = True
    net_benefit = {
        "main": {
            "new": len(main_new_units),
            "lost": len(main_remaining),
            "net": len(main_new_units) - len(main_remaining),
            "new_units": main_new_units,
            "recovered_loss_units": [main_old_losses[row_id] for row_id in main_recovered],
            "remaining_lost_units": main_remaining,
        },
        "strict": {
            "new": len(strict_new_units),
            "lost": len(strict_remaining),
            "net": len(strict_new_units) - len(strict_remaining),
            "new_units": strict_new_units,
            "recovered_loss_units": [strict_old_losses[row_id] for row_id in strict_recovered],
            "remaining_lost_units": strict_remaining,
            "conservative_note": "货币换算、左轮空弹巢、床板藏枪、做饭关系等低优先细节仍不额外扣分；本轮按三项已恢复失分重算为 7−2＝+5。",
        },
        "wide": {
            "new": len(wide_new_units),
            "lost": len(wide_remaining),
            "net": len(wide_new_units) - len(wide_remaining),
            "new_units": wide_new_units,
            "recovered_or_narrowed_loss_units": list(wide_transform["changes"]),
            "remaining_lost_units": wide_remaining,
        },
    }

    expected_net = config["expected_net"]
    actual_net = {name: net_benefit[name]["net"] for name in ("main", "strict", "wide")}
    if actual_net != expected_net:
        raise NetBenefitError(f"三口径结果偏离预写值：expected={expected_net}, actual={actual_net}")

    by_type = dict(sorted(Counter(row["type"] for row in candidate_records.values()).items()))
    if by_type != metrics_doc.get("by_type"):
        raise NetBenefitError("候选类型计数与分类指标不符")
    cross_type_duplicates = int(differential_audit["cross_type_duplicate_count"])
    wrong_d_count = int(differential_audit["wrong_d_count"])
    gates = {
        "main_gte_3": net_benefit["main"]["net"] >= 3,
        "strict_gte_3": net_benefit["strict"]["net"] >= 3,
        "wide_gte_3": net_benefit["wide"]["net"] >= 3,
        "cross_type_duplicates_eq_0": cross_type_duplicates == 0,
        "wrong_d_eq_0": wrong_d_count == 0,
    }
    gates["all_passed"] = all(gates.values())

    previous_nets = {
        name: int(old_net[name]["net"])
        for name in ("main", "strict", "wide")
    }
    return {
        "schema_version": "z-net-benefit-recompute-v1.2",
        "run_id": config["run_id"],
        "comparison_id": config["comparison_id"],
        "status": "completed_zero_call_decision_candidate_not_promoted",
        "model_calls": 0,
        "inputs": {
            "baseline": {"path": str(baseline_path.relative_to(root)), "sha256": sha256_file(baseline_path), "records": 70},
            "candidate": {"path": str(candidate_path.relative_to(root)), "sha256": sha256_file(candidate_path), "records": 122, "by_type": by_type},
            "old_candidate": {"path": str(old_candidate_path.relative_to(root)), "sha256": sha256_file(old_candidate_path), "records": 118},
            "prior_alignment": {"path": str(prior_path.relative_to(root)), "sha256": sha256_file(prior_path)},
            "candidate_metrics": {"path": str(metrics_path.relative_to(root)), "sha256": sha256_file(metrics_path)},
            "old_human_gate_audit": {"path": str(old_gate_path.relative_to(root)), "sha256": sha256_file(old_gate_path)},
            "differential_semantic_audit": {"path": str(audit_path.relative_to(root)), "sha256": sha256_file(audit_path)},
        },
        "method": copy.deepcopy(prior_doc["method"]),
        "protected_sha256": protected_results,
        "recovery_evidence": recovery_evidence,
        "semantic_preservation": semantic_preservation,
        "remaining_absent_spans": absent_results,
        "net_benefit": net_benefit,
        "comparison_to_z00u_old_candidate": {
            "old_candidate": "Z00s classify_rules v1.1",
            "new_candidate": "Z00w2 classify_rules v1.2",
            "previous_nets": previous_nets,
            "current_nets": actual_net,
            "delta": {name: actual_net[name] - previous_nets[name] for name in actual_net},
        },
        "other_gates": {
            "cross_type_duplicate_count": cross_type_duplicates,
            "wrong_d_count": wrong_d_count,
            "evidence_basis": differential_audit,
        },
        "gates": gates,
        "decision_boundary": {
            "numbers_are_registered_only": True,
            "default_promoted": False,
            "x02_x04_started": False,
            "outbox_written": False,
            "next_decision": "三闸复判与升默认仍须 CZ 亲拍；T3 不自动滚动",
        },
    }

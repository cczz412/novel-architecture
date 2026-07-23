#!/usr/bin/env python3
"""第91道 v1.3 零调用匿名盲审机械壳。

程序只做身份、覆盖、抽样、两票/三裁边界和冻结公式计算。
等价分组、探针判词、原子完整性、锚支撑和语义错误均由人工填写。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


EXPERIMENT_DIR = Path(__file__).resolve().parent
ROOT = EXPERIMENT_DIR.parents[1]
OVERLAY_PATH = EXPERIMENT_DIR / "blind_probe_rubric_v1.3.json"
SHORT_CONTRACT_PATH = EXPERIMENT_DIR / "short_summary_exception_v1.json"
V2_RUNNER_PATH = EXPERIMENT_DIR / "z91_crossbook_exam_v2_run.py"
DEFAULT_RUN_DIR = ROOT / "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723"
BLIND_RELATIVE = Path("review/blind_v1_3")

CASES = ("X02-C0031", "X03-C0019", "X04-C0046")
ANONYMOUS_ARMS = ("A", "B")
REAL_ROLES = ("flash", "pro")
STRATA = ("both_arms", "A_only", "B_only")
PROBE_VERDICTS = ("hit", "partial", "miss")
ANCHOR_VERDICTS = ("complete", "partial", "none")
SEMANTIC_ERROR_LABELS = (
    "fabricated_fact",
    "cognition_strength_change",
    "wrong_subject",
    "wrong_causality",
    "other_new_failure",
)
CRITICAL_NEW_ERROR_LABELS = {"fabricated_fact", "cognition_strength_change"}

FORBIDDEN_ANONYMOUS_KEY_PARTS = (
    "provider",
    "model",
    "usage",
    "elapsed",
    "duration",
    "latency",
    "arm_id",
    "sample_id",
    "logical_request_id",
    "token",
)


class BlindReviewError(RuntimeError):
    """盲审机械合同失败。"""


_V2_RUNNER: Any = None


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BlindReviewError(f"JSON 缺失或无法解析：{path}") from exc


def read_object(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise BlindReviewError(f"JSON 顶层不是对象：{path}")
    return value


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json_bytes(value)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def write_fresh_or_equal(path: Path, value: Any) -> None:
    if path.exists():
        if read_json(path) != value:
            raise BlindReviewError(f"既有工件与重建结果不同，拒绝覆盖：{path}")
        return
    write_json_exclusive(path, value)


def is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _require_exact_keys(value: Mapping[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise BlindReviewError(f"{label} 字段集合漂移")


def _overlay_contract() -> tuple[dict[str, Any], dict[str, Any], Path]:
    overlay = read_object(OVERLAY_PATH)
    if (
        overlay.get("schema_version") != "z91-crossbook-blind-probe-rubric-v1.3"
        or overlay.get("only_final_states")
        != ["pro_directional_lead", "no_crossbook_pro_lead"]
    ):
        raise BlindReviewError("v1.3 overlay 身份或唯一终态漂移")
    base = overlay.get("base_rubric")
    if not isinstance(base, Mapping):
        raise BlindReviewError("v1.3 overlay 缺 base_rubric")
    base_path = ROOT / str(base.get("path", ""))
    if not base_path.is_file() or sha256_file(base_path) != base.get("sha256"):
        raise BlindReviewError("v1.3 overlay 指向的 v1.2 判分尺缺失或 SHA 漂移")
    contract = read_object(SHORT_CONTRACT_PATH)
    if (
        contract.get("schema_version")
        != "z91-short-summary-exception-contract-v1"
        or overlay.get("sole_overlay", {}).get("experiment_exception_contract_path")
        != SHORT_CONTRACT_PATH.relative_to(ROOT).as_posix()
    ):
        raise BlindReviewError("短摘要例外合同身份漂移")
    return overlay, contract, base_path


def _ledger_rows(value: Mapping[str, Any], label: str) -> list[dict[str, Any]]:
    rows = value.get("entries", value.get("rows"))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise BlindReviewError(f"{label} 缺合法 entries/rows")
    return rows


def _run_raw_usage_audit(run_dir: Path) -> dict[str, Any]:
    """调用 v2 运行器的零调用审计，从 raw response 和 usage 重建 candidate。"""

    global _V2_RUNNER
    if _V2_RUNNER is None:
        spec = importlib.util.spec_from_file_location(
            "z91_crossbook_exam_v2_run_for_blind_audit", V2_RUNNER_PATH
        )
        if spec is None or spec.loader is None:
            raise BlindReviewError("无法加载 v2 原始响应审计器")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # pragma: no cover - 导入失败只在部署路径异常时出现
            raise BlindReviewError("v2 原始响应审计器加载失败") from exc
        _V2_RUNNER = module
    try:
        receipt = _V2_RUNNER.audit(run_dir)
    except Exception as exc:
        raise BlindReviewError("v2 raw response + usage 审计未通过") from exc
    if not isinstance(receipt, dict) or receipt.get("logical_samples") != 6:
        raise BlindReviewError("v2 raw response + usage 审计没有重建六份样本")
    return receipt


def _validate_blind_runtime_pin(run_dir: Path) -> dict[str, str]:
    """盲审执行器必须在发网前进入 prepared/runtime 保护向量。"""

    relative = Path(__file__).resolve().relative_to(ROOT).as_posix()
    expected_sha = sha256_file(Path(__file__).resolve())
    preflight = read_object(run_dir / "prepared/preflight.json")
    dependencies = preflight.get("runtime_dependencies")
    if not isinstance(dependencies, list):
        raise BlindReviewError("v2 preflight 缺运行依赖 SHA 表")
    rows = [
        row for row in dependencies
        if isinstance(row, Mapping) and row.get("path") == relative
    ]
    copied = run_dir / "inputs/runtime_dependencies" / relative
    verification = read_object(run_dir / "prepared/mechanical_verification.json")
    vector_key = f"inputs/runtime_dependencies/{relative}"
    first = verification.get("first_vector")
    second = verification.get("second_vector")
    if (
        len(rows) != 1
        or rows[0].get("sha256") != expected_sha
        or not copied.is_file()
        or sha256_file(copied) != expected_sha
        or not isinstance(first, Mapping)
        or not isinstance(second, Mapping)
        or first.get(vector_key) != expected_sha
        or second.get(vector_key) != expected_sha
    ):
        raise BlindReviewError("盲审执行器没有在正式发网前被 prepared/runtime SHA 冻结")
    return {"path": relative, "sha256": expected_sha}


def _sample_plan(run_dir: Path) -> list[dict[str, Any]]:
    plan = read_object(run_dir / "prepared/run_plan.json")
    samples = plan.get("samples")
    if (
        plan.get("sample_count") != 6
        or not isinstance(samples, list)
        or len(samples) != 6
        or any(not isinstance(row, dict) for row in samples)
    ):
        raise BlindReviewError("v2 run_plan 不是六份样本")
    by_case: dict[str, list[dict[str, Any]]] = {case: [] for case in CASES}
    for sample in samples:
        case = sample.get("case_key")
        arm_id = sample.get("arm_id")
        if case not in by_case or not isinstance(arm_id, str):
            raise BlindReviewError("v2 run_plan 的 case/arm 身份无效")
        if arm_id.startswith("flash_"):
            role = "flash"
        elif arm_id.startswith("pro_"):
            role = "pro"
        else:
            raise BlindReviewError(f"无法识别真实臂角色：{arm_id}")
        row = dict(sample)
        row["real_role"] = role
        by_case[str(case)].append(row)
    for case, rows in by_case.items():
        if len(rows) != 2 or {row["real_role"] for row in rows} != set(REAL_ROLES):
            raise BlindReviewError(f"{case} 不是 Flash/Pro 各一份")
        if len({row.get("messages_sha256") for row in rows}) != 1:
            raise BlindReviewError(f"{case} 双臂 messages SHA 不一致")
    return samples_with_roles(by_case)


def samples_with_roles(by_case: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for case in CASES:
        result.extend(sorted((dict(row) for row in by_case[case]), key=lambda row: row["real_role"]))
    return result


def _validate_completed_run(run_dir: Path) -> dict[str, Any]:
    raw_usage_audit = _run_raw_usage_audit(run_dir)
    blind_runtime_pin = _validate_blind_runtime_pin(run_dir)
    overlay, _, _ = _overlay_contract()
    rubric_sha = sha256_file(OVERLAY_PATH)
    contract_sha = sha256_file(SHORT_CONTRACT_PATH)
    completion = read_object(run_dir / "completion.json")
    if (
        completion.get("logical_samples") != 6
        or completion.get("mechanical_three_gates") != "pass_6_of_6"
        or completion.get("rubric_v1_3_sha256") != rubric_sha
        or completion.get("short_summary_contract_sha256") != contract_sha
        or not isinstance(completion.get("short_summary_violation_count"), int)
        or completion.get("short_summary_violation_count", -1) < 0
    ):
        raise BlindReviewError("v2 全局完成票不是六份有效机械样本或 v1.3 身份漂移")
    samples = _sample_plan(run_dir)
    expected_ids = {str(row.get("sample_id")) for row in samples}
    if set(map(str, completion.get("sample_ids", []))) != expected_ids:
        raise BlindReviewError("v2 全局完成票的六份 sample_id 漂移")

    total_short = 0
    source_rows: list[dict[str, Any]] = []
    for sample in samples:
        sample_id = str(sample["sample_id"])
        root = run_dir / "samples" / sample_id
        ticket = read_object(root / "completion.json")
        mechanical = read_object(root / "mechanical.json")
        short_count = mechanical.get("short_summary_violation_count")
        ledger_sha = mechanical.get("short_summary_ledger_sha256")
        ledger_path = root / "candidate/z91_v2_short_summary_ledger.json"
        if (
            ticket.get("sample_id") != sample_id
            or ticket.get("case_key") != sample.get("case_key")
            or ticket.get("arm_id") != sample.get("arm_id")
            or ticket.get("mechanical_three_gates") != "pass"
            or ticket.get("rubric_v1_3_sha256") != rubric_sha
            or ticket.get("short_summary_contract_sha256") != contract_sha
            or ticket.get("short_summary_violation_count") != short_count
            or mechanical.get("status") != "pass"
            or mechanical.get("short_summary_contract_sha256") != contract_sha
            or mechanical.get("rubric_v1_3_sha256") != rubric_sha
            or mechanical.get("z91_v2_exception_gate") is not True
            or mechanical.get("effective_gate") is not True
            or not isinstance(short_count, int)
            or short_count < 0
            or mechanical.get("shared_six_char_gate") is not (short_count == 0)
            or not is_sha256(ledger_sha)
            or not ledger_path.is_file()
            or sha256_file(ledger_path) != ledger_sha
        ):
            raise BlindReviewError(f"{sample_id} 的 v1.3 机械完成身份无效")
        ledger = read_object(ledger_path)
        if (
            ledger.get("schema_version") != "z91-short-summary-side-ledger-v1"
            or ledger.get("sample_id") != sample_id
            or ledger.get("rubric_v1_3_sha256") != rubric_sha
            or ledger.get("short_summary_contract_sha256") != contract_sha
            or ledger.get("exception_count") != short_count
            or len(_ledger_rows(ledger, sample_id)) != short_count
        ):
            raise BlindReviewError(f"{sample_id} 短摘要旁账计数不能重建")
        events_doc = read_object(root / "candidate/neutral_events.json")
        events = events_doc.get("events")
        if not isinstance(events, list) or not events:
            raise BlindReviewError(f"{sample_id} 缺有效事件数组")
        if ticket.get("event_count") != len(events) or mechanical.get("event_count") != len(events):
            raise BlindReviewError(f"{sample_id} 事件计数不能由候选原件重建")
        total_short += short_count
        source_rows.append(
            {
                "sample": sample,
                "ticket_path": root / "completion.json",
                "mechanical_path": root / "mechanical.json",
                "events_path": root / "candidate/neutral_events.json",
                "ledger_path": ledger_path,
                "events_doc": events_doc,
            }
        )
    if completion["short_summary_violation_count"] != total_short:
        raise BlindReviewError("全局短摘要旁账总数不能由六份样本相加重建")
    completion_audit = read_object(run_dir / "audit/completion_audit.json")
    contract_audit = read_object(run_dir / "audit/v2_contract_audit.json")
    if (
        completion_audit.get("logical_samples") != 6
        or completion_audit.get("mechanical_three_gates") != "pass_6_of_6"
        or contract_audit.get("logical_samples") != 6
        or contract_audit.get("rubric_v1_3_sha256") != rubric_sha
        or contract_audit.get("short_summary_contract_sha256") != contract_sha
        or contract_audit.get("short_summary_violation_count") != total_short
    ):
        raise BlindReviewError("v2 runner 审计票没有证明六份原始样本与旁账可重建")
    return {
        "overlay": overlay,
        "rubric_sha256": rubric_sha,
        "short_contract_sha256": contract_sha,
        "completion": completion,
        "samples": source_rows,
        "short_summary_violation_count": total_short,
        "raw_usage_audit": raw_usage_audit,
        "blind_runtime_pin": blind_runtime_pin,
    }


def content_key(event: str, anchor_ids: Sequence[str]) -> str:
    """沿 v1.2：事件文本 + 排序去重锚，得到内容身份。"""

    return canonical_sha(
        {"event": event, "sorted_unique_anchor_ids": sorted(set(anchor_ids))}
    )


def member_key(
    case_key: str,
    anonymous_arm: str,
    event_id: str,
    event_content_key: str,
) -> str:
    """绑定发生位置，避免跨章、跨臂或重复 event_id 碰撞。"""

    return canonical_sha(
        {
            "case_key": case_key,
            "anonymous_arm": anonymous_arm,
            "event_id": event_id,
            "content_key": event_content_key,
        }
    )


def group_key(member_keys: Sequence[str]) -> str:
    if not member_keys or len(set(member_keys)) != len(member_keys):
        raise BlindReviewError("等价组成员为空或重复")
    return canonical_sha(sorted(member_keys))


def _mapping_for_samples(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_case: dict[str, list[Mapping[str, Any]]] = {case: [] for case in CASES}
    for sample in samples:
        by_case[str(sample["sample"]["case_key"])].append(sample["sample"])
    mappings: list[dict[str, Any]] = []
    for case in CASES:
        rows = by_case[case]
        messages_sha = str(rows[0]["messages_sha256"])
        digit = hashlib.sha256(f"{case}|{messages_sha}".encode("utf-8")).hexdigest()[0]
        flash_label = "A" if int(digit, 16) % 2 == 0 else "B"
        pro_label = "B" if flash_label == "A" else "A"
        labels = {"flash": flash_label, "pro": pro_label}
        arms: dict[str, Any] = {}
        for row in rows:
            label = labels[str(row["real_role"])]
            arms[label] = {
                "real_role": row["real_role"],
                "sample_id": row["sample_id"],
                "arm_id": row["arm_id"],
                "provider": row.get("provider"),
                "model": row.get("model"),
            }
        mappings.append(
            {
                "case_key": case,
                "messages_sha256": messages_sha,
                "mapping_digest_first_hex": digit,
                "anonymous_arms": arms,
            }
        )
    return {
        "schema_version": "z91-blind-arm-mapping-v1.3",
        "status": "sealed_not_for_reviewers",
        "mapping_rule": "sha256(case_key|messages_sha256) first hex parity",
        "cases": mappings,
    }


def _validate_source_fact_copy(run_dir: Path) -> tuple[dict[str, Any], str]:
    fact_dir = run_dir / "review/source_facts"
    seal_path = fact_dir / "source_fact_seal.json"
    seal = read_object(seal_path)
    resolved_ref = seal.get("resolved_file")
    if (
        seal.get("schema_version") != "z91-source-fact-seal-v1"
        or seal.get("dual_arm_outputs_seen_before_seal") is not False
        or not isinstance(resolved_ref, Mapping)
        or resolved_ref.get("path") != "resolved.json"
    ):
        raise BlindReviewError("v1 来源事实封签身份无效")
    resolved_path = fact_dir / "resolved.json"
    if not resolved_path.is_file() or sha256_file(resolved_path) != resolved_ref.get("sha256"):
        raise BlindReviewError("v1 来源事实 resolved 原件缺失或 SHA 漂移")
    resolved = read_object(resolved_path)
    items = resolved.get("items")
    if (
        resolved.get("schema_version") != "z91-source-facts-resolved-v1"
        or resolved.get("probe_count") != 18
        or not isinstance(items, list)
        or len(items) != 18
    ):
        raise BlindReviewError("v1 来源事实不是18个冻结探针")
    ids = [row.get("probe_id") for row in items if isinstance(row, Mapping)]
    if len(ids) != 18 or len(set(ids)) != 18:
        raise BlindReviewError("v1 来源事实探针 ID 重复或缺失")
    return resolved, sha256_file(seal_path)


def _anonymous_packet(
    run_dir: Path,
    completed: Mapping[str, Any],
    mapping: Mapping[str, Any],
) -> dict[str, Any]:
    resolved, source_seal_sha = _validate_source_fact_copy(run_dir)
    label_by_sample: dict[str, str] = {}
    for case in mapping["cases"]:
        for label, detail in case["anonymous_arms"].items():
            label_by_sample[str(detail["sample_id"])] = str(label)
    cases: dict[str, dict[str, Any]] = {
        case: {"case_key": case, "members": [], "source_probes": []} for case in CASES
    }
    for case in CASES:
        chapter_path = run_dir / f"inputs/cases/{case}/chapter_body.txt"
        catalog_path = run_dir / f"inputs/cases/{case}/evidence_catalog.json"
        if not chapter_path.is_file() or not catalog_path.is_file():
            raise BlindReviewError(f"{case} 缺冻结正文或证据目录")
        cases[case].update(
            {
                "chapter_body": chapter_path.read_text(encoding="utf-8"),
                "chapter_body_sha256": sha256_file(chapter_path),
                "evidence_catalog": read_object(catalog_path),
                "evidence_catalog_sha256": sha256_file(catalog_path),
            }
        )
    seen_members: set[str] = set()
    for source in completed["samples"]:
        sample = source["sample"]
        sample_id = str(sample["sample_id"])
        case = str(sample["case_key"])
        label = label_by_sample[sample_id]
        for event in source["events_doc"]["events"]:
            if not isinstance(event, Mapping):
                raise BlindReviewError(f"{sample_id} 含非对象事件")
            event_id = event.get("event_id")
            text = event.get("event")
            anchors = event.get("anchors")
            if (
                not isinstance(event_id, str)
                or not isinstance(text, str)
                or not text.strip()
                or not isinstance(anchors, list)
                or not anchors
                or any(not isinstance(row, Mapping) for row in anchors)
            ):
                raise BlindReviewError(f"{sample_id} 事件字段无效")
            anchor_ids = [row.get("anchor_id") for row in anchors]
            if any(not isinstance(value, str) for value in anchor_ids):
                raise BlindReviewError(f"{sample_id}/{event_id} 锚 ID 无效")
            c_key = content_key(text, anchor_ids)
            m_key = member_key(case, label, event_id, c_key)
            if m_key in seen_members:
                raise BlindReviewError("member_key 发生碰撞")
            seen_members.add(m_key)
            cases[case]["members"].append(
                {
                    "member_key": m_key,
                    "content_key": c_key,
                    "anonymous_arm": label,
                    "event_id": event_id,
                    "event": text,
                    "anchors": [dict(row) for row in anchors],
                }
            )
    for item in resolved["items"]:
        case = str(item["probe_id"]).rsplit("-P", 1)[0]
        if case not in cases:
            raise BlindReviewError(f"来源探针出现卷外 case：{case}")
        cases[case]["source_probes"].append(
            {
                key: item[key]
                for key in (
                    "probe_id",
                    "canonical_fact",
                    "subject",
                    "action_or_state",
                    "result",
                    "explicit_qualifiers",
                    "support_anchor_ids",
                )
            }
        )
    for case in CASES:
        cases[case]["members"].sort(key=lambda row: row["member_key"])
        cases[case]["source_probes"].sort(key=lambda row: row["probe_id"])
        if len(cases[case]["source_probes"]) != 6:
            raise BlindReviewError(f"{case} 不是6个来源探针")
    return {
        "schema_version": "z91-anonymous-review-packet-v1.3",
        "status": "anonymous_grouping_input",
        "rubric_v1_3_sha256": completed["rubric_sha256"],
        "source_fact_seal_sha256": source_seal_sha,
        "cases": [cases[case] for case in CASES],
    }


def _known_sensitive_values(completed: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for source in completed["samples"]:
        row = source["sample"]
        for key in ("sample_id", "logical_request_id", "arm_id", "provider", "model"):
            value = row.get(key)
            if isinstance(value, str) and value:
                values.add(value)
    return values


def anonymous_leaks(value: Any, sensitive_values: Iterable[str]) -> list[str]:
    leaks: list[str] = []
    sensitive = set(sensitive_values)

    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for raw_key, child in node.items():
                key = str(raw_key)
                lowered = key.lower()
                if any(part in lowered for part in FORBIDDEN_ANONYMOUS_KEY_PARTS):
                    leaks.append(f"{path}.{key}:forbidden_key")
                walk(child, f"{path}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
        elif isinstance(node, str) and node in sensitive:
            leaks.append(f"{path}:sensitive_value")

    walk(value, "$")
    return leaks


def _grouping_template(packet: Mapping[str, Any], reviewer: str) -> dict[str, Any]:
    return {
        "schema_version": "z91-equivalence-group-review-v1.3",
        "reviewer_id": reviewer,
        "packet_sha256": canonical_sha(packet),
        "independent_review": True,
        "cases": [
            {
                "case_key": case["case_key"],
                "expected_member_keys": [row["member_key"] for row in case["members"]],
                "groups": [],
            }
            for case in packet["cases"]
        ],
    }


def _preparation_seal(
    run_dir: Path,
    blind_dir: Path,
    completed: Mapping[str, Any],
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    mapping_path = blind_dir / "sealed/arm_mapping.json"
    packet_path = blind_dir / "anonymous/packet.json"
    return {
        "schema_version": "z91-blind-preparation-seal-v1.3",
        "status": "prepared_zero_api_awaiting_independent_grouping",
        "run_completion_sha256": sha256_file(run_dir / "completion.json"),
        "rubric_v1_3_sha256": completed["rubric_sha256"],
        "short_summary_contract_sha256": completed["short_contract_sha256"],
        "short_summary_violation_count": completed["short_summary_violation_count"],
        "raw_usage_completion_audit_sha256": sha256_file(
            run_dir / "audit/completion_audit.json"
        ),
        "v2_contract_audit_sha256": sha256_file(
            run_dir / "audit/v2_contract_audit.json"
        ),
        "blind_runtime_pin": completed["blind_runtime_pin"],
        "raw_usage_audit_status": completed["raw_usage_audit"].get("status"),
        "arm_mapping_sha256": sha256_file(mapping_path),
        "anonymous_packet_sha256": sha256_file(packet_path),
        "grouping_template_sha256_by_reviewer": {
            reviewer: hashlib.sha256(
                json_bytes(_grouping_template(packet, reviewer))
            ).hexdigest()
            for reviewer in ("R1", "R2")
        },
        "case_count": len(packet["cases"]),
        "member_count": sum(len(case["members"]) for case in packet["cases"]),
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def prepare_blind(run_dir: Path, blind_dir: Path | None = None) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    blind_dir = (blind_dir or run_dir / BLIND_RELATIVE).resolve()
    if blind_dir.exists() and any(blind_dir.iterdir()):
        raise BlindReviewError("盲审目录已有工件，拒绝覆盖或重做映射")
    completed = _validate_completed_run(run_dir)
    mapping = _mapping_for_samples(completed["samples"])
    packet = _anonymous_packet(run_dir, completed, mapping)
    leaks = anonymous_leaks(packet, _known_sensitive_values(completed))
    if leaks:
        raise BlindReviewError(f"匿名包出现身份泄漏：{leaks}")
    mapping_path = blind_dir / "sealed/arm_mapping.json"
    packet_path = blind_dir / "anonymous/packet.json"
    write_json_exclusive(mapping_path, mapping)
    write_json_exclusive(packet_path, packet)
    for reviewer in ("R1", "R2"):
        path = blind_dir / f"grouping/reviewer_{reviewer}.json"
        template = _grouping_template(packet, reviewer)
        if anonymous_leaks(template, _known_sensitive_values(completed)):
            raise BlindReviewError("等价组模板出现匿名身份泄漏")
        write_json_exclusive(path, template)
    seal = _preparation_seal(run_dir, blind_dir, completed, packet)
    write_json_exclusive(blind_dir / "sealed/preparation_seal.json", seal)
    return seal


def _packet_index(packet: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    members: dict[str, dict[str, Any]] = {}
    by_case: dict[str, list[str]] = {}
    cases = packet.get("cases")
    if not isinstance(cases, list):
        raise BlindReviewError("匿名包缺 cases")
    for case in cases:
        if not isinstance(case, Mapping) or case.get("case_key") not in CASES:
            raise BlindReviewError("匿名包 case 身份无效")
        case_key = str(case["case_key"])
        rows = case.get("members")
        if not isinstance(rows, list):
            raise BlindReviewError(f"{case_key} 匿名包缺 members")
        keys: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                raise BlindReviewError(f"{case_key} member 不是对象")
            key = row.get("member_key")
            if not is_sha256(key) or key in members:
                raise BlindReviewError("匿名包 member_key 无效或重复")
            expected_content = content_key(
                str(row.get("event", "")),
                [str(anchor.get("anchor_id")) for anchor in row.get("anchors", [])],
            )
            expected_member = member_key(
                case_key,
                str(row.get("anonymous_arm")),
                str(row.get("event_id")),
                expected_content,
            )
            if (
                row.get("content_key") != expected_content
                or key != expected_member
                or row.get("anonymous_arm") not in ANONYMOUS_ARMS
            ):
                raise BlindReviewError(f"{case_key} member/content 身份不能重建")
            members[str(key)] = row
            keys.append(str(key))
        by_case[case_key] = sorted(keys)
    if set(by_case) != set(CASES):
        raise BlindReviewError("匿名包不是固定三章")
    return members, by_case


def _validate_group_vote(
    path: Path,
    reviewer: str,
    packet: Mapping[str, Any],
    expected_by_case: Mapping[str, Sequence[str]],
) -> dict[str, list[tuple[str, ...]]]:
    value = read_object(path)
    if (
        value.get("schema_version") != "z91-equivalence-group-review-v1.3"
        or value.get("reviewer_id") != reviewer
        or value.get("packet_sha256") != canonical_sha(packet)
        or value.get("independent_review") is not True
    ):
        raise BlindReviewError(f"{reviewer} 等价组票头部漂移")
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != len(CASES):
        raise BlindReviewError(f"{reviewer} 等价组票不是固定三章")
    result: dict[str, list[tuple[str, ...]]] = {}
    for case in cases:
        if not isinstance(case, Mapping):
            raise BlindReviewError(f"{reviewer} 等价组 case 不是对象")
        _require_exact_keys(
            case, {"case_key", "expected_member_keys", "groups"}, f"{reviewer} 等价组 case"
        )
        case_key = str(case.get("case_key"))
        expected = list(expected_by_case.get(case_key, []))
        if case_key in result or case.get("expected_member_keys") != expected:
            raise BlindReviewError(f"{reviewer}/{case_key} 预期成员集合漂移")
        groups = case.get("groups")
        if not isinstance(groups, list) or not groups:
            raise BlindReviewError(f"{reviewer}/{case_key} 尚未填写等价组")
        seen: list[str] = []
        group_ids: set[str] = set()
        partitions: list[tuple[str, ...]] = []
        for group in groups:
            if not isinstance(group, Mapping):
                raise BlindReviewError(f"{reviewer}/{case_key} 等价组不是对象")
            _require_exact_keys(group, {"group_id", "member_keys"}, "等价组行")
            local_id = group.get("group_id")
            keys = group.get("member_keys")
            if (
                not isinstance(local_id, str)
                or not local_id.strip()
                or local_id in group_ids
                or not isinstance(keys, list)
                or not keys
                or any(not isinstance(key, str) for key in keys)
                or len(set(keys)) != len(keys)
            ):
                raise BlindReviewError(f"{reviewer}/{case_key} 等价组行无效")
            if any(key not in expected for key in keys):
                raise BlindReviewError(f"{reviewer}/{case_key} 等价组出现卷外成员")
            group_ids.add(local_id)
            seen.extend(keys)
            partitions.append(tuple(sorted(keys)))
        if sorted(seen) != expected or len(seen) != len(set(seen)):
            raise BlindReviewError(f"{reviewer}/{case_key} 没有恰好覆盖全部成员一次")
        result[case_key] = sorted(partitions)
    if set(result) != set(CASES):
        raise BlindReviewError(f"{reviewer} 等价组票 case 集合漂移")
    return result


def _disagreement_components(
    left: Sequence[tuple[str, ...]], right: Sequence[tuple[str, ...]]
) -> tuple[list[tuple[str, ...]], list[dict[str, Any]]]:
    left_set = set(left)
    right_set = set(right)
    common = sorted(left_set & right_set)
    disputed_groups = sorted((left_set - right_set) | (right_set - left_set))
    disputed_members = sorted({key for group in disputed_groups for key in group})
    neighbors: dict[str, set[str]] = {key: set() for key in disputed_members}
    for group in disputed_groups:
        for key in group:
            neighbors[key].update(group)
    components: list[dict[str, Any]] = []
    unseen = set(disputed_members)
    while unseen:
        start = min(unseen)
        stack = [start]
        component: set[str] = set()
        while stack:
            key = stack.pop()
            if key in component:
                continue
            component.add(key)
            stack.extend(sorted(neighbors[key] - component, reverse=True))
        unseen -= component
        member_tuple = tuple(sorted(component))
        left_groups = sorted(group for group in left if set(group) <= component)
        right_groups = sorted(group for group in right if set(group) <= component)
        if left_groups == right_groups:
            raise BlindReviewError("分歧连通分量意外没有分歧")
        components.append(
            {
                "member_keys": list(member_tuple),
                "reviewer_R1_groups": [list(group) for group in left_groups],
                "reviewer_R2_groups": [list(group) for group in right_groups],
            }
        )
    return common, components


def _group_r3_template(
    packet: Mapping[str, Any],
    partitions: Mapping[str, Mapping[str, Sequence[tuple[str, ...]]]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in CASES:
        _, components = _disagreement_components(
            partitions["R1"][case], partitions["R2"][case]
        )
        for component in components:
            rows.append(
                {
                    "disagreement_id": "DG-" + canonical_sha(
                        {"case_key": case, "member_keys": component["member_keys"]}
                    )[:16],
                    "case_key": case,
                    **component,
                    "final_groups": None,
                    "reason": None,
                }
            )
    return {
        "schema_version": "z91-equivalence-group-adjudication-v1.3",
        "reviewer_id": "R3",
        "scope": "only_R1_R2_partition_disagreements",
        "packet_sha256": canonical_sha(packet),
        "rows": rows,
    }


def _validate_group_r3(
    value: Mapping[str, Any], template: Mapping[str, Any]
) -> dict[str, list[tuple[str, ...]]] | None:
    if any(value.get(key) != template.get(key) for key in (
        "schema_version", "reviewer_id", "scope", "packet_sha256"
    )):
        raise BlindReviewError("R3 等价组裁决头部漂移")
    rows = value.get("rows")
    expected_rows = template.get("rows")
    if not isinstance(rows, list) or not isinstance(expected_rows, list) or len(rows) != len(expected_rows):
        raise BlindReviewError("R3 没有只覆盖全部分歧")
    result: dict[str, list[tuple[str, ...]]] = {case: [] for case in CASES}
    pending = False
    for row, expected in zip(rows, expected_rows, strict=True):
        if not isinstance(row, Mapping) or not isinstance(expected, Mapping):
            raise BlindReviewError("R3 分歧行不是对象")
        fixed = {
            "disagreement_id", "case_key", "member_keys",
            "reviewer_R1_groups", "reviewer_R2_groups",
        }
        if any(row.get(key) != expected.get(key) for key in fixed) or set(row) != set(expected):
            raise BlindReviewError("R3 改写了一致字段、原票或分歧范围")
        groups = row.get("final_groups")
        reason = row.get("reason")
        if groups is None or reason is None:
            if groups is not None or reason is not None:
                raise BlindReviewError("R3 final_groups 与 reason 必须一起填写")
            pending = True
            continue
        if not isinstance(reason, str) or not reason.strip() or not isinstance(groups, list) or not groups:
            raise BlindReviewError("R3 裁决值或理由无效")
        normalized: list[tuple[str, ...]] = []
        seen: list[str] = []
        for group in groups:
            if (
                not isinstance(group, list)
                or not group
                or any(not isinstance(key, str) for key in group)
                or len(set(group)) != len(group)
            ):
                raise BlindReviewError("R3 final_groups 含无效组")
            normalized.append(tuple(sorted(group)))
            seen.extend(group)
        if sorted(seen) != expected["member_keys"] or len(seen) != len(set(seen)):
            raise BlindReviewError("R3 final_groups 没有恰好覆盖该分歧成员")
        result[str(row["case_key"])].extend(sorted(normalized))
    return None if pending else result


def _resolved_group_rows(
    packet: Mapping[str, Any],
    partitions: Mapping[str, Mapping[str, Sequence[tuple[str, ...]]]],
    r3_groups: Mapping[str, Sequence[tuple[str, ...]]],
) -> dict[str, Any]:
    members, _ = _packet_index(packet)
    cases: list[dict[str, Any]] = []
    for case in CASES:
        common, _ = _disagreement_components(partitions["R1"][case], partitions["R2"][case])
        final_partitions = sorted(common + list(r3_groups[case]))
        rows: list[dict[str, Any]] = []
        for group in final_partitions:
            arms = sorted({str(members[key]["anonymous_arm"]) for key in group})
            stratum = "both_arms" if arms == ["A", "B"] else f"{arms[0]}_only"
            rows.append(
                {
                    "group_key": group_key(group),
                    "member_keys": list(group),
                    "content_keys": sorted([str(members[key]["content_key"]) for key in group]),
                    "anonymous_arms": arms,
                    "stratum": stratum,
                }
            )
        rows.sort(key=lambda row: row["group_key"])
        if len({row["group_key"] for row in rows}) != len(rows):
            raise BlindReviewError(f"{case} group_key 碰撞")
        cases.append({"case_key": case, "groups": rows, "group_count": len(rows)})
    return {
        "schema_version": "z91-resolved-equivalence-groups-v1.3",
        "status": "resolved_from_R1_R2_and_R3_only_disagreements",
        "packet_sha256": canonical_sha(packet),
        "cases": cases,
    }


def _sample_groups(resolved: Mapping[str, Any]) -> dict[str, Any]:
    output_cases: list[dict[str, Any]] = []
    for case in resolved["cases"]:
        pools = {
            stratum: sorted(
                [row for row in case["groups"] if row["stratum"] == stratum],
                key=lambda row: row["group_key"],
            )
            for stratum in STRATA
        }
        selected: list[dict[str, Any]] = []
        selected_keys: set[str] = set()
        for stratum in STRATA:
            for row in pools[stratum][:4]:
                selected.append({**row, "selection_source": f"{stratum}_quota"})
                selected_keys.add(row["group_key"])
        deficit = 12 - len(selected)
        if deficit > 0:
            for stratum in STRATA:
                for row in pools[stratum]:
                    if deficit == 0:
                        break
                    if row["group_key"] in selected_keys:
                        continue
                    selected.append({**row, "selection_source": f"{stratum}_backfill"})
                    selected_keys.add(row["group_key"])
                    deficit -= 1
        for rank, row in enumerate(selected, start=1):
            row["selection_rank"] = rank
        output_cases.append(
            {
                "case_key": case["case_key"],
                "candidate_group_count": len(case["groups"]),
                "actual_sampled_group_count": len(selected),
                "direction_eligible_by_size": len(selected) >= 8,
                "selected_groups": selected,
            }
        )
    return {
        "schema_version": "z91-fixed-stratified-sample-v1.3",
        "status": "selected_by_group_key_no_human_substitution",
        "resolved_groups_sha256": canonical_sha(resolved),
        "strata_order": list(STRATA),
        "quota_per_stratum": 4,
        "maximum_per_case": 12,
        "cases": output_cases,
    }


def resolve_groups(run_dir: Path, blind_dir: Path | None = None) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    blind_dir = (blind_dir or run_dir / BLIND_RELATIVE).resolve()
    completed = _validate_completed_run(run_dir)
    packet = read_object(blind_dir / "anonymous/packet.json")
    if anonymous_leaks(packet, _known_sensitive_values(completed)):
        raise BlindReviewError("匿名包复验发现身份泄漏")
    _, expected_by_case = _packet_index(packet)
    partitions = {
        reviewer: _validate_group_vote(
            blind_dir / f"grouping/reviewer_{reviewer}.json",
            reviewer,
            packet,
            expected_by_case,
        )
        for reviewer in ("R1", "R2")
    }
    template = _group_r3_template(packet, partitions)
    r3_path = blind_dir / "grouping/reviewer_R3.json"
    if not r3_path.exists():
        write_json_exclusive(r3_path, template)
        if template["rows"]:
            return {
                "schema_version": "z91-group-resolution-status-v1.3",
                "status": "awaiting_R3_only_disagreements",
                "disagreement_count": len(template["rows"]),
                "model_api_calls": 0,
                "network_attempts": 0,
            }
    r3 = read_object(r3_path)
    resolved_r3 = _validate_group_r3(r3, template)
    if resolved_r3 is None:
        return {
            "schema_version": "z91-group-resolution-status-v1.3",
            "status": "awaiting_R3_only_disagreements",
            "disagreement_count": len(template["rows"]),
            "model_api_calls": 0,
            "network_attempts": 0,
        }
    resolved = _resolved_group_rows(packet, partitions, resolved_r3)
    sampled = _sample_groups(resolved)
    if anonymous_leaks(resolved, _known_sensitive_values(completed)) or anonymous_leaks(
        sampled, _known_sensitive_values(completed)
    ):
        raise BlindReviewError("分组或抽样结果出现匿名身份泄漏")
    write_fresh_or_equal(blind_dir / "grouping/resolved_groups.json", resolved)
    write_fresh_or_equal(blind_dir / "grouping/sampled_groups.json", sampled)
    return {
        "schema_version": "z91-group-resolution-status-v1.3",
        "status": "resolved_and_sampled",
        "disagreement_count": len(template["rows"]),
        "group_count": sum(case["group_count"] for case in resolved["cases"]),
        "sampled_group_count": sum(case["actual_sampled_group_count"] for case in sampled["cases"]),
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def _judgment_template(
    packet: Mapping[str, Any], sampled: Mapping[str, Any], reviewer: str
) -> dict[str, Any]:
    packet_cases = {case["case_key"]: case for case in packet["cases"]}
    cases: list[dict[str, Any]] = []
    for sampled_case in sampled["cases"]:
        case_key = sampled_case["case_key"]
        packet_case = packet_cases[case_key]
        probes = [
            {
                "probe_id": probe["probe_id"],
                "source_fact": probe,
                "arms": {arm: {"verdict": None} for arm in ANONYMOUS_ARMS},
            }
            for probe in packet_case["source_probes"]
        ]
        groups: list[dict[str, Any]] = []
        member_index = {row["member_key"]: row for row in packet_case["members"]}
        for group in sampled_case["selected_groups"]:
            by_arm = {
                arm: sorted(
                    key
                    for key in group["member_keys"]
                    if member_index[key]["anonymous_arm"] == arm
                )
                for arm in ANONYMOUS_ARMS
            }
            groups.append(
                {
                    "group_key": group["group_key"],
                    "stratum": group["stratum"],
                    "member_keys_by_arm": by_arm,
                    "arms": {
                        arm: {
                            "atomic_complete": None,
                            "anchor_support_by_member": {key: None for key in by_arm[arm]},
                            "semantic_error_labels": None,
                        }
                        for arm in ANONYMOUS_ARMS
                    },
                }
            )
        cases.append(
            {
                "case_key": case_key,
                "probe_judgments": probes,
                "group_judgments": groups,
            }
        )
    return {
        "schema_version": "z91-blind-judgment-review-v1.3",
        "reviewer_id": reviewer,
        "independent_review": True,
        "packet_sha256": canonical_sha(packet),
        "sampled_groups_sha256": canonical_sha(sampled),
        "cases": cases,
    }


def prepare_judgments(run_dir: Path, blind_dir: Path | None = None) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    blind_dir = (blind_dir or run_dir / BLIND_RELATIVE).resolve()
    status = resolve_groups(run_dir, blind_dir)
    if status["status"] != "resolved_and_sampled":
        raise BlindReviewError("等价组尚待 R3 裁分歧，不能生成判词模板")
    completed = _validate_completed_run(run_dir)
    packet = read_object(blind_dir / "anonymous/packet.json")
    sampled = read_object(blind_dir / "grouping/sampled_groups.json")
    targets = [blind_dir / f"judgments/reviewer_{reviewer}.json" for reviewer in ("R1", "R2")]
    if any(path.exists() for path in targets):
        raise BlindReviewError("人工判词模板已存在，拒绝覆盖")
    hashes: dict[str, str] = {}
    for reviewer, path in zip(("R1", "R2"), targets, strict=True):
        template = _judgment_template(packet, sampled, reviewer)
        leaks = anonymous_leaks(template, _known_sensitive_values(completed))
        if leaks:
            raise BlindReviewError(f"判词模板出现匿名泄漏：{leaks}")
        write_json_exclusive(path, template)
        hashes[reviewer] = sha256_file(path)
    receipt = {
        "schema_version": "z91-judgment-preparation-status-v1.3",
        "status": "templates_prepared_awaiting_R1_R2",
        "reviewer_template_sha256": hashes,
        "probe_unit_count": sum(
            len(case["probe_judgments"])
            for case in _judgment_template(packet, sampled, "R1")["cases"]
        ),
        "group_unit_count": sum(
            len(case["group_judgments"])
            for case in _judgment_template(packet, sampled, "R1")["cases"]
        ),
        "model_api_calls": 0,
        "network_attempts": 0,
    }
    return receipt


DecisionKey = tuple[str, str, str, str, str, str]


def _decision_key(
    unit_type: str,
    case_key: str,
    unit_id: str,
    arm: str,
    field: str,
    member: str = "",
) -> DecisionKey:
    return (unit_type, case_key, unit_id, arm, field, member)


def _validate_semantic_labels(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(item not in SEMANTIC_ERROR_LABELS for item in value)
        or len(set(value)) != len(value)
        or value != sorted(value)
    ):
        raise BlindReviewError(f"{label} 语义错误标签必须是排序去重的冻结枚举")
    return list(value)


def _validate_judgment_vote(
    path: Path,
    reviewer: str,
    template: Mapping[str, Any],
) -> dict[DecisionKey, Any]:
    value = read_object(path)
    for key in (
        "schema_version", "reviewer_id", "independent_review",
        "packet_sha256", "sampled_groups_sha256",
    ):
        if value.get(key) != template.get(key):
            raise BlindReviewError(f"{reviewer} 判词票头部漂移：{key}")
    if set(value) != set(template):
        raise BlindReviewError(f"{reviewer} 判词票字段集合漂移")
    cases = value.get("cases")
    expected_cases = template.get("cases")
    if not isinstance(cases, list) or not isinstance(expected_cases, list) or len(cases) != len(expected_cases):
        raise BlindReviewError(f"{reviewer} 判词票 case 数漂移")
    decisions: dict[DecisionKey, Any] = {}
    for case, expected_case in zip(cases, expected_cases, strict=True):
        if not isinstance(case, Mapping) or not isinstance(expected_case, Mapping):
            raise BlindReviewError(f"{reviewer} 判词 case 不是对象")
        if set(case) != set(expected_case) or case.get("case_key") != expected_case.get("case_key"):
            raise BlindReviewError(f"{reviewer} 判词 case 固定字段漂移")
        case_key = str(case["case_key"])
        probes = case.get("probe_judgments")
        expected_probes = expected_case.get("probe_judgments")
        if not isinstance(probes, list) or len(probes) != 6 or len(probes) != len(expected_probes):
            raise BlindReviewError(f"{reviewer}/{case_key} 不是6个探针单元")
        for row, expected in zip(probes, expected_probes, strict=True):
            if not isinstance(row, Mapping) or set(row) != set(expected):
                raise BlindReviewError(f"{reviewer}/{case_key} 探针行字段漂移")
            if row.get("probe_id") != expected.get("probe_id") or row.get("source_fact") != expected.get("source_fact"):
                raise BlindReviewError(f"{reviewer}/{case_key} 改写了冻结来源探针")
            arms = row.get("arms")
            if not isinstance(arms, Mapping) or set(arms) != set(ANONYMOUS_ARMS):
                raise BlindReviewError(f"{reviewer}/{case_key} 探针臂字段漂移")
            for arm in ANONYMOUS_ARMS:
                arm_row = arms[arm]
                if not isinstance(arm_row, Mapping) or set(arm_row) != {"verdict"}:
                    raise BlindReviewError(f"{reviewer}/{case_key} 探针判词字段漂移")
                verdict = arm_row["verdict"]
                if verdict not in PROBE_VERDICTS:
                    raise BlindReviewError(f"{reviewer}/{case_key} 探针判词尚未填写或越界")
                key = _decision_key("probe", case_key, str(row["probe_id"]), arm, "verdict")
                decisions[key] = verdict

        groups = case.get("group_judgments")
        expected_groups = expected_case.get("group_judgments")
        if not isinstance(groups, list) or not isinstance(expected_groups, list) or len(groups) != len(expected_groups):
            raise BlindReviewError(f"{reviewer}/{case_key} 抽样组数漂移")
        if len(groups) > 12:
            raise BlindReviewError(f"{reviewer}/{case_key} 超过12个抽样组")
        for row, expected in zip(groups, expected_groups, strict=True):
            if not isinstance(row, Mapping) or set(row) != set(expected):
                raise BlindReviewError(f"{reviewer}/{case_key} 组判词字段漂移")
            for fixed in ("group_key", "stratum", "member_keys_by_arm"):
                if row.get(fixed) != expected.get(fixed):
                    raise BlindReviewError(f"{reviewer}/{case_key} 改写抽样组固定字段")
            arms = row.get("arms")
            if not isinstance(arms, Mapping) or set(arms) != set(ANONYMOUS_ARMS):
                raise BlindReviewError(f"{reviewer}/{case_key} 组判词臂字段漂移")
            group_id = str(row["group_key"])
            for arm in ANONYMOUS_ARMS:
                arm_row = arms[arm]
                expected_arm = expected["arms"][arm]
                if not isinstance(arm_row, Mapping) or set(arm_row) != set(expected_arm):
                    raise BlindReviewError(f"{reviewer}/{case_key} 组判词字段漂移")
                present = expected["member_keys_by_arm"][arm]
                if not present:
                    if arm_row != expected_arm:
                        raise BlindReviewError(f"{reviewer}/{case_key} 给缺席臂填写了人工判词")
                    continue
                atomic = arm_row.get("atomic_complete")
                supports = arm_row.get("anchor_support_by_member")
                labels = arm_row.get("semantic_error_labels")
                if not isinstance(atomic, bool):
                    raise BlindReviewError(f"{reviewer}/{case_key} atomic_complete 尚未填写")
                if not isinstance(supports, Mapping) or list(supports) != present:
                    raise BlindReviewError(f"{reviewer}/{case_key} 锚支撑没有覆盖该臂全部成员")
                if any(verdict not in ANCHOR_VERDICTS for verdict in supports.values()):
                    raise BlindReviewError(f"{reviewer}/{case_key} 锚支撑尚未填写或越界")
                if atomic is True and any(
                    verdict != "complete" for verdict in supports.values()
                ):
                    raise BlindReviewError(
                        f"{reviewer}/{case_key} atomic_complete=true 但存在非完整支撑锚"
                    )
                labels = _validate_semantic_labels(labels, f"{reviewer}/{case_key}")
                decisions[_decision_key("group", case_key, group_id, arm, "atomic_complete")] = atomic
                decisions[_decision_key("group", case_key, group_id, arm, "semantic_error_labels")] = labels
                for member, verdict in supports.items():
                    decisions[
                        _decision_key("group", case_key, group_id, arm, "anchor_support", str(member))
                    ] = verdict
    return decisions


def _judgment_r3_template(
    packet: Mapping[str, Any],
    sampled: Mapping[str, Any],
    votes: Mapping[str, Mapping[DecisionKey, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if set(votes["R1"]) != set(votes["R2"]):
        raise BlindReviewError("R1/R2 判词决策字段集合不一致")
    for key in sorted(votes["R1"]):
        left = votes["R1"][key]
        right = votes["R2"][key]
        if left == right:
            continue
        unit_type, case_key, unit_id, arm, field, member = key
        rows.append(
            {
                "decision_id": "JD-" + canonical_sha(list(key))[:16],
                "unit_type": unit_type,
                "case_key": case_key,
                "unit_id": unit_id,
                "anonymous_arm": arm,
                "field": field,
                "member_key": member or None,
                "reviewer_R1_value": left,
                "reviewer_R2_value": right,
                "final_value": None,
                "reason": None,
            }
        )
    return {
        "schema_version": "z91-blind-judgment-adjudication-v1.3",
        "reviewer_id": "R3",
        "scope": "only_R1_R2_decision_field_disagreements",
        "packet_sha256": canonical_sha(packet),
        "sampled_groups_sha256": canonical_sha(sampled),
        "rows": rows,
    }


def _validate_decision_value(field: str, value: Any) -> Any:
    if field == "verdict" and value in PROBE_VERDICTS:
        return value
    if field == "atomic_complete" and isinstance(value, bool):
        return value
    if field == "anchor_support" and value in ANCHOR_VERDICTS:
        return value
    if field == "semantic_error_labels":
        return _validate_semantic_labels(value, "R3")
    raise BlindReviewError(f"R3 裁决值不符合字段合同：{field}")


def _validate_judgment_r3(
    value: Mapping[str, Any], template: Mapping[str, Any]
) -> dict[DecisionKey, Any] | None:
    for key in (
        "schema_version", "reviewer_id", "scope", "packet_sha256", "sampled_groups_sha256"
    ):
        if value.get(key) != template.get(key):
            raise BlindReviewError(f"R3 判词裁决头部漂移：{key}")
    rows = value.get("rows")
    expected_rows = template.get("rows")
    if not isinstance(rows, list) or not isinstance(expected_rows, list) or len(rows) != len(expected_rows):
        raise BlindReviewError("R3 判词没有只覆盖全部分歧字段")
    result: dict[DecisionKey, Any] = {}
    pending = False
    fixed = {
        "decision_id", "unit_type", "case_key", "unit_id", "anonymous_arm",
        "field", "member_key", "reviewer_R1_value", "reviewer_R2_value",
    }
    for row, expected in zip(rows, expected_rows, strict=True):
        if not isinstance(row, Mapping) or set(row) != set(expected):
            raise BlindReviewError("R3 判词分歧行字段漂移")
        if any(row.get(key) != expected.get(key) for key in fixed):
            raise BlindReviewError("R3 判词改写了一致字段、原票或分歧范围")
        final = row.get("final_value")
        reason = row.get("reason")
        if final is None or reason is None:
            if final is not None or reason is not None:
                raise BlindReviewError("R3 final_value 与 reason 必须一起填写")
            pending = True
            continue
        if not isinstance(reason, str) or not reason.strip():
            raise BlindReviewError("R3 裁决必须填写理由")
        final = _validate_decision_value(str(row["field"]), final)
        key = _decision_key(
            str(row["unit_type"]), str(row["case_key"]), str(row["unit_id"]),
            str(row["anonymous_arm"]), str(row["field"]), str(row.get("member_key") or ""),
        )
        result[key] = final
    return None if pending else result


def _resolved_decisions(
    votes: Mapping[str, Mapping[DecisionKey, Any]],
    adjudicated: Mapping[DecisionKey, Any],
) -> dict[DecisionKey, Any]:
    result: dict[DecisionKey, Any] = {}
    for key in sorted(votes["R1"]):
        left = votes["R1"][key]
        right = votes["R2"][key]
        if left == right:
            if key in adjudicated:
                raise BlindReviewError("R3 越权裁了一致字段")
            result[key] = left
        else:
            if key not in adjudicated:
                raise BlindReviewError("R3 漏裁分歧字段")
            result[key] = adjudicated[key]
    if set(adjudicated) != {key for key in votes["R1"] if votes["R1"][key] != votes["R2"][key]}:
        raise BlindReviewError("R3 裁决范围不等于 R1/R2 分歧范围")
    return result


def _mapping_labels(mapping: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for case in mapping.get("cases", []):
        case_key = str(case.get("case_key"))
        arms = case.get("anonymous_arms")
        if case_key not in CASES or not isinstance(arms, Mapping) or set(arms) != set(ANONYMOUS_ARMS):
            raise BlindReviewError("封存 A/B 映射结构漂移")
        role_to_label: dict[str, str] = {}
        for label, detail in arms.items():
            if not isinstance(detail, Mapping) or detail.get("real_role") not in REAL_ROLES:
                raise BlindReviewError("封存 A/B 映射真实角色漂移")
            role_to_label[str(detail["real_role"])] = str(label)
        if set(role_to_label) != set(REAL_ROLES):
            raise BlindReviewError("封存 A/B 映射不是 Flash/Pro 各一臂")
        result[case_key] = role_to_label
    if set(result) != set(CASES):
        raise BlindReviewError("封存 A/B 映射不是固定三章")
    return result


def _score(
    sampled: Mapping[str, Any],
    mapping: Mapping[str, Any],
    decisions: Mapping[DecisionKey, Any],
) -> dict[str, Any]:
    labels_by_case = _mapping_labels(mapping)
    chapter_metrics: list[dict[str, Any]] = []
    anchor_totals = {
        role: {"non_support": 0, "reviewed_events": 0} for role in REAL_ROLES
    }
    atomic_totals = {role: 0 for role in REAL_ROLES}
    new_critical_errors: list[dict[str, Any]] = []
    all_semantic_errors: dict[str, int] = {role: 0 for role in REAL_ROLES}

    for case in sampled["cases"]:
        case_key = str(case["case_key"])
        role_labels = labels_by_case[case_key]
        probe_hits: dict[str, int] = {}
        atomics: dict[str, int] = {}
        anchors: dict[str, dict[str, int]] = {}
        errors_by_group_label: dict[tuple[str, str], set[str]] = {}
        for role in REAL_ROLES:
            label = role_labels[role]
            probe_hits[role] = sum(
                decisions[_decision_key("probe", case_key, f"{case_key}-P{index:02d}", label, "verdict")]
                == "hit"
                for index in range(1, 7)
            )
            atomics[role] = 0
            anchors[role] = {"non_support": 0, "reviewed_events": 0}

        for group in case["selected_groups"]:
            group_id = str(group["group_key"])
            members_by_label = {label: [] for label in ANONYMOUS_ARMS}
            # sampled_groups 不复制 member->arm 映射，按 resolved group 的匿名臂集合不足以拆成员；
            # 决策键本身保留每个成员所属臂，因此从决策表重建。
            for label in ANONYMOUS_ARMS:
                support_keys = sorted(
                    key for key in decisions
                    if key[0] == "group" and key[1] == case_key and key[2] == group_id
                    and key[3] == label and key[4] == "anchor_support"
                )
                present_members = [key[5] for key in support_keys]
                members_by_label[label] = present_members
                if present_members:
                    errors_by_group_label[(group_id, label)] = set(
                        decisions[_decision_key(
                            "group", case_key, group_id, label, "semantic_error_labels"
                        )]
                    )
            for role in REAL_ROLES:
                label = role_labels[role]
                present = members_by_label[label]
                if not present:
                    errors_by_group_label[(group_id, label)] = set()
                    continue
                atomic = decisions[_decision_key(
                    "group", case_key, group_id, label, "atomic_complete"
                )]
                support_values = [
                    decisions[_decision_key(
                        "group", case_key, group_id, label, "anchor_support", member
                    )]
                    for member in present
                ]
                if atomic is True and any(value != "complete" for value in support_values):
                    raise BlindReviewError(
                        f"{case_key}/{group_id}/{label} 最终原子完整票与锚完整支撑票矛盾"
                    )
                atomics[role] += int(
                    atomic is True and all(value == "complete" for value in support_values)
                )
                labels = errors_by_group_label[(group_id, label)]
                all_semantic_errors[role] += int(bool(labels))
                for member, anchor in zip(present, support_values, strict=True):
                    anchors[role]["reviewed_events"] += 1
                    anchors[role]["non_support"] += int(anchor != "complete")
        for group in case["selected_groups"]:
            group_id = str(group["group_key"])
            flash_errors = errors_by_group_label.get((group_id, role_labels["flash"]), set())
            pro_errors = errors_by_group_label.get((group_id, role_labels["pro"]), set())
            new = sorted((pro_errors - flash_errors) & CRITICAL_NEW_ERROR_LABELS)
            if new:
                new_critical_errors.append(
                    {"case_key": case_key, "group_key": group_id, "labels": new}
                )
        for role in REAL_ROLES:
            atomic_totals[role] += atomics[role]
            anchor_totals[role]["non_support"] += anchors[role]["non_support"]
            anchor_totals[role]["reviewed_events"] += anchors[role]["reviewed_events"]
        chapter_metrics.append(
            {
                "case_key": case_key,
                "actual_sampled_group_count": case["actual_sampled_group_count"],
                "probe_hit_count": probe_hits,
                "probe_gain_pro_minus_flash": probe_hits["pro"] - probe_hits["flash"],
                "atomic_complete_count": atomics,
                "atomic_gain_pro_minus_flash": atomics["pro"] - atomics["flash"],
                "anchor_non_support": anchors,
            }
        )

    rates: dict[str, float | None] = {}
    for role in REAL_ROLES:
        denominator = anchor_totals[role]["reviewed_events"]
        rates[role] = (
            anchor_totals[role]["non_support"] / denominator if denominator else None
        )
    gains = [row["probe_gain_pro_minus_flash"] for row in chapter_metrics]
    conditions = {
        "minimum_sample_all_chapters": all(
            row["actual_sampled_group_count"] >= 8 for row in chapter_metrics
        ),
        "probe_gain_two_books_and_third_not_lower": (
            sum(gain >= 2 for gain in gains) >= 2 and all(gain >= 0 for gain in gains)
        ),
        "atomic_total_not_lower": atomic_totals["pro"] >= atomic_totals["flash"],
        "atomic_no_chapter_lower_by_two": all(
            row["atomic_gain_pro_minus_flash"] >= -1 for row in chapter_metrics
        ),
        "anchor_denominators_valid_each_chapter": all(
            row["anchor_non_support"][role]["reviewed_events"] > 0
            for row in chapter_metrics for role in REAL_ROLES
        ),
        "pro_anchor_weighted_rate_not_higher": (
            rates["pro"] is not None
            and rates["flash"] is not None
            and rates["pro"] <= rates["flash"]
        ),
        "pro_adds_no_fabrication_or_cognition_strength_error": not new_critical_errors,
    }
    final_state = (
        "pro_directional_lead"
        if all(conditions.values())
        else "no_crossbook_pro_lead"
    )
    return {
        "schema_version": "z91-crossbook-directional-result-v1.3",
        "status": "finalized_from_two_votes_and_R3_only_disagreements",
        "final_state": final_state,
        "only_allowed_final_states": [
            "pro_directional_lead", "no_crossbook_pro_lead"
        ],
        "chapter_metrics": chapter_metrics,
        "aggregate": {
            "atomic_complete_count": atomic_totals,
            "anchor_non_support": anchor_totals,
            "anchor_non_support_weighted_rate": rates,
            "semantic_error_group_count": all_semantic_errors,
            "pro_new_critical_errors": new_critical_errors,
        },
        "directional_conditions": conditions,
        "failed_conditions": [key for key, passed in conditions.items() if not passed],
        "claim_boundary": "directional cross-book observation only; not recall, formal accuracy, default promotion, or provider cutover evidence by itself",
        "model_api_calls": 0,
        "network_attempts": 0,
    }
def _resolved_decision_document(decisions: Mapping[DecisionKey, Any]) -> dict[str, Any]:
    return {
        "schema_version": "z91-resolved-blind-judgments-v1.3",
        "status": "resolved_R1_R2_R3_only_disagreements",
        "rows": [
            {
                "unit_type": key[0],
                "case_key": key[1],
                "unit_id": key[2],
                "anonymous_arm": key[3],
                "field": key[4],
                "member_key": key[5] or None,
                "final_value": value,
            }
            for key, value in sorted(decisions.items())
        ],
    }


def _build_final(
    run_dir: Path, blind_dir: Path
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, Any] | None]:
    completed = _validate_completed_run(run_dir)
    packet = read_object(blind_dir / "anonymous/packet.json")
    sampled = read_object(blind_dir / "grouping/sampled_groups.json")
    templates = {
        reviewer: _judgment_template(packet, sampled, reviewer)
        for reviewer in ("R1", "R2")
    }
    votes = {
        reviewer: _validate_judgment_vote(
            blind_dir / f"judgments/reviewer_{reviewer}.json", reviewer, templates[reviewer]
        )
        for reviewer in ("R1", "R2")
    }
    r3_template = _judgment_r3_template(packet, sampled, votes)
    r3_path = blind_dir / "judgments/reviewer_R3.json"
    if not r3_path.exists():
        write_json_exclusive(r3_path, r3_template)
        if r3_template["rows"]:
            return None, r3_template, None
    adjudicated = _validate_judgment_r3(read_object(r3_path), r3_template)
    if adjudicated is None:
        return None, r3_template, None
    decisions = _resolved_decisions(votes, adjudicated)
    resolved_doc = _resolved_decision_document(decisions)
    mapping = read_object(blind_dir / "sealed/arm_mapping.json")
    expected_mapping = _mapping_for_samples(completed["samples"])
    if mapping != expected_mapping:
        raise BlindReviewError("封存 A/B 映射不能由六份原始样本重建")
    result = _score(sampled, mapping, decisions)
    result["rubric_v1_3_sha256"] = completed["rubric_sha256"]
    result["anonymous_packet_sha256"] = canonical_sha(packet)
    result["sampled_groups_sha256"] = canonical_sha(sampled)
    result["arm_mapping_sha256"] = canonical_sha(mapping)
    result["resolved_judgments_sha256"] = canonical_sha(resolved_doc)
    return result, r3_template, resolved_doc


def finalize(run_dir: Path, blind_dir: Path | None = None) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    blind_dir = (blind_dir or run_dir / BLIND_RELATIVE).resolve()
    result, template, resolved_doc = _build_final(run_dir, blind_dir)
    if result is None:
        return {
            "schema_version": "z91-finalization-status-v1.3",
            "status": "awaiting_R3_only_disagreements",
            "disagreement_count": len(template["rows"]),
            "model_api_calls": 0,
            "network_attempts": 0,
        }
    assert resolved_doc is not None
    completed = _validate_completed_run(run_dir)
    if anonymous_leaks(resolved_doc, _known_sensitive_values(completed)):
        raise BlindReviewError("已裁判词工件出现匿名身份泄漏")
    write_fresh_or_equal(blind_dir / "judgments/resolved_judgments.json", resolved_doc)
    write_fresh_or_equal(blind_dir / "final/result.json", result)
    return result


def audit(run_dir: Path, blind_dir: Path | None = None) -> dict[str, Any]:
    """从运行原件和三位人工原票重建 SHA、计数、抽样与终态。"""

    run_dir = run_dir.resolve()
    blind_dir = (blind_dir or run_dir / BLIND_RELATIVE).resolve()
    completed = _validate_completed_run(run_dir)
    expected_mapping = _mapping_for_samples(completed["samples"])
    expected_packet = _anonymous_packet(run_dir, completed, expected_mapping)
    mapping_path = blind_dir / "sealed/arm_mapping.json"
    packet_path = blind_dir / "anonymous/packet.json"
    if read_object(mapping_path) != expected_mapping:
        raise BlindReviewError("audit：A/B 映射不能由原始样本重建")
    packet = read_object(packet_path)
    if packet != expected_packet:
        raise BlindReviewError("audit：匿名包不能由原始事件重建")
    if read_object(blind_dir / "sealed/preparation_seal.json") != _preparation_seal(
        run_dir, blind_dir, completed, packet
    ):
        raise BlindReviewError("audit：盲审准备封签的 SHA 或计数不能重建")
    sensitive = _known_sensitive_values(completed)
    leaks: dict[str, list[str]] = {}
    anonymous_paths = [
        packet_path,
        blind_dir / "grouping/reviewer_R1.json",
        blind_dir / "grouping/reviewer_R2.json",
        blind_dir / "grouping/reviewer_R3.json",
        blind_dir / "grouping/resolved_groups.json",
        blind_dir / "grouping/sampled_groups.json",
        blind_dir / "judgments/reviewer_R1.json",
        blind_dir / "judgments/reviewer_R2.json",
        blind_dir / "judgments/reviewer_R3.json",
        blind_dir / "judgments/resolved_judgments.json",
    ]
    for path in anonymous_paths:
        found = anonymous_leaks(read_json(path), sensitive)
        if found:
            leaks[path.relative_to(blind_dir).as_posix()] = found
    if leaks:
        raise BlindReviewError(f"audit：匿名工件泄漏身份：{leaks}")

    _, expected_by_case = _packet_index(packet)
    partitions = {
        reviewer: _validate_group_vote(
            blind_dir / f"grouping/reviewer_{reviewer}.json",
            reviewer,
            packet,
            expected_by_case,
        )
        for reviewer in ("R1", "R2")
    }
    group_r3_template = _group_r3_template(packet, partitions)
    group_r3 = _validate_group_r3(
        read_object(blind_dir / "grouping/reviewer_R3.json"), group_r3_template
    )
    if group_r3 is None:
        raise BlindReviewError("audit：等价组 R3 尚未裁完")
    expected_resolved = _resolved_group_rows(packet, partitions, group_r3)
    expected_sampled = _sample_groups(expected_resolved)
    if read_object(blind_dir / "grouping/resolved_groups.json") != expected_resolved:
        raise BlindReviewError("audit：全组不能由 R1/R2/R3 重建")
    if read_object(blind_dir / "grouping/sampled_groups.json") != expected_sampled:
        raise BlindReviewError("audit：三层固定抽样不能由全组重建")

    expected_result, _, expected_decisions = _build_final(run_dir, blind_dir)
    if expected_result is None or expected_decisions is None:
        raise BlindReviewError("audit：判词 R3 尚未裁完")
    if read_object(blind_dir / "judgments/resolved_judgments.json") != expected_decisions:
        raise BlindReviewError("audit：已裁判词不能由三位原票重建")
    if read_object(blind_dir / "final/result.json") != expected_result:
        raise BlindReviewError("audit：唯一两值终态不能由冻结公式重建")

    original_paths = [
        run_dir / "completion.json",
        run_dir / "review/source_facts/source_fact_seal.json",
        run_dir / "review/source_facts/resolved.json",
        mapping_path,
        blind_dir / "sealed/preparation_seal.json",
        *anonymous_paths,
        blind_dir / "final/result.json",
    ]
    original_paths.extend(
        sorted((run_dir / "review/source_facts").glob("*.json"))
    )
    for source in completed["samples"]:
        original_paths.extend(
            [
                source["ticket_path"], source["mechanical_path"],
                source["events_path"], source["ledger_path"],
            ]
        )
        sample_root = source["events_path"].parents[1]
        original_paths.extend(
            sorted(
                path
                for path in (
                    sample_root / "transport/usage.json",
                    sample_root / "transport/call_attempts.jsonl",
                    sample_root / "checkpoint/02_response.json",
                    *sorted((sample_root / "transport/raw_responses").glob("*.json")),
                )
                if path.is_file()
            )
        )
    artifact_shas: dict[str, str] = {}
    for path in original_paths:
        try:
            relative = path.relative_to(run_dir).as_posix()
        except ValueError:
            relative = path.as_posix()
        artifact_shas[relative] = sha256_file(path)
    receipt = {
        "schema_version": "z91-blind-review-audit-v1.3",
        "status": "pass_rebuilt_from_run_and_human_originals",
        "run_id": run_dir.name,
        "case_count": 3,
        "sample_count": 6,
        "member_count": sum(len(case["members"]) for case in packet["cases"]),
        "group_count": sum(case["group_count"] for case in expected_resolved["cases"]),
        "sampled_group_count": sum(
            case["actual_sampled_group_count"] for case in expected_sampled["cases"]
        ),
        "source_probe_count": sum(len(case["source_probes"]) for case in packet["cases"]),
        "short_summary_violation_count": completed["short_summary_violation_count"],
        "raw_usage_completion_audit_sha256": sha256_file(
            run_dir / "audit/completion_audit.json"
        ),
        "v2_contract_audit_sha256": sha256_file(
            run_dir / "audit/v2_contract_audit.json"
        ),
        "blind_runtime_pin": completed["blind_runtime_pin"],
        "raw_usage_audit_status": completed["raw_usage_audit"].get("status"),
        "anonymous_leak_count": 0,
        "final_state": expected_result["final_state"],
        "artifact_sha256": dict(sorted(artifact_shas.items())),
        "model_api_calls": 0,
        "network_attempts": 0,
    }
    write_fresh_or_equal(blind_dir / "audit.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("prepare-blind", "六份机械通过后生成封存映射、匿名包和分组双票模板"),
        ("resolve-groups", "验分组双票与 R3 只裁分歧，并做固定三层抽样"),
        ("prepare-judgments", "生成两位复核者的探针与抽样组判词模板"),
        ("finalize", "验判词双票与 R3 只裁分歧，并计算唯一两值终态"),
        ("audit", "从原始件重建 SHA、计数、匿名边界和终态"),
    ):
        child = subparsers.add_parser(command, help=help_text)
        child.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
        child.add_argument("--blind-dir", type=Path)
    args = parser.parse_args(argv)
    functions = {
        "prepare-blind": prepare_blind,
        "resolve-groups": resolve_groups,
        "prepare-judgments": prepare_judgments,
        "finalize": finalize,
        "audit": audit,
    }
    result = functions[args.command](args.run_dir, args.blind_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

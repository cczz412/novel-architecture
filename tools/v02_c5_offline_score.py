#!/usr/bin/env python3
"""V02/C5：实验 A 离线材料充分性核验与三选一结论。

当前 C1 只冻结了三份对照请求，没有对照回包或语义分。这个工具因此只做：

- 复验 C1 请求锁、金标身份与 49 分母；
- 复验 C4 三章机械通过件；
- 检查 ANCHOR_PARTIAL 与五层语义分所需的冻结判词是否存在；
- 材料不齐时固定输出 ``MATERIALS_INSUFFICIENT_CANNOT_ADJUDICATE``。

工具不会生成语义判词，不会把缺失值补成 0，也不会调用模型或网络。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import v02_anchor_first_experiment as prep  # noqa: F401 - 测试钉死不调用旧数值闸
from pipeline_common import model_benchmark
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
C1_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "C_anchor_first_experiment"
)
C4_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C4_r03_20260725"
C5_OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C5_offline_score"
)

CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
OFFLINE_DENOMINATOR = 49
SEMANTIC_LAYERS = ("FCR", "QCR_full", "ASR_full", "UCR", "SOP")

CONCLUSION_PASS = "PASS_EXPERIMENT_GATE"
CONCLUSION_FAIL = "FAIL_EXPERIMENT_GATE"
CONCLUSION_MISSING = "MATERIALS_INSUFFICIENT_CANNOT_ADJUDICATE"
ALLOWED_CONCLUSIONS = {
    CONCLUSION_PASS,
    CONCLUSION_FAIL,
    CONCLUSION_MISSING,
}

EXPECTED_GATE = {
    "offline_denominator": 49,
    "relative_reduction_threshold": 0.5,
    "declining_chapter_threshold": 2,
    "declining_chapter_total": 3,
    "no_regression_layers": ["FCR", "QCR_full", "ASR_full", "UCR"],
    "sop_threshold": 0.98,
    "additional_model_calls_threshold": 0,
}


class C5ScoreError(ZBatchError):
    """C5 程序票不能从冻结件重建。"""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return model_benchmark.sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C5ScoreError(f"冻结件不存在：{path}")
    return model_benchmark.sha256_file(path)


def _assert_gate_contract() -> dict[str, Any]:
    path = C1_DIR / "gate/gate_contract.json"
    contract = read_json(path)
    criteria = contract.get("criteria")
    if not isinstance(criteria, Mapping):
        raise C5ScoreError("C1 过闸合同缺 criteria")
    observed = {
        "offline_denominator": contract.get("offline_denominator"),
        "relative_reduction_threshold": (
            criteria.get("anchor_partial_relative_reduction", {}).get("threshold")
        ),
        "declining_chapter_threshold": (
            criteria.get("anchor_partial_declining_chapters", {}).get("threshold")
        ),
        "declining_chapter_total": (
            criteria.get("anchor_partial_declining_chapters", {}).get(
                "chapter_total"
            )
        ),
        "no_regression_layers": criteria.get("no_regression_layers"),
        "sop_threshold": criteria.get("sop", {}).get("threshold"),
        "additional_model_calls_threshold": criteria.get(
            "additional_model_calls", {}
        ).get("threshold"),
    }
    if observed != EXPECTED_GATE:
        raise C5ScoreError("C1 过闸阈值或分母漂移")
    return {
        "schema_version": contract.get("schema_version"),
        "file_sha256": sha256_file(path),
        "criteria": observed,
        "judge_green_ticket_may_issue": (
            contract.get("authority", {}).get("judge_green_ticket_may_issue")
        ),
    }


def _verify_gold_identities() -> list[dict[str, Any]]:
    manifest_path = C1_DIR / "source_manifest.json"
    manifest = read_json(manifest_path)
    rows = manifest.get("chapters")
    if not isinstance(rows, list) or [row.get("case_id") for row in rows] != list(
        CASE_ORDER
    ):
        raise C5ScoreError("C1 来源清单章节顺序漂移")
    if manifest.get("offline_denominator") != OFFLINE_DENOMINATOR:
        raise C5ScoreError("C1 来源清单分母不是 49")

    verified: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row["case_id"])
        denominator = DENOMINATORS[case_id]
        if row.get("formal_denominator") != denominator:
            raise C5ScoreError(f"{case_id} 来源清单分母漂移")
        gold = row.get("formal_gold")
        pointer = row.get("gold_pointer")
        if not isinstance(gold, Mapping) or not isinstance(pointer, Mapping):
            raise C5ScoreError(f"{case_id} 缺金标身份或指针")
        gold_path = ROOT / str(gold["path"])
        pointer_path = ROOT / str(pointer["path"])
        if sha256_file(gold_path) != gold.get("sha256"):
            raise C5ScoreError(f"{case_id} 金标 SHA 漂移")
        if sha256_file(pointer_path) != pointer.get("sha256"):
            raise C5ScoreError(f"{case_id} 金标指针 SHA 漂移")
        gold_doc = read_json(gold_path)
        layer_summary = gold_doc.get("layer_summary")
        evaluation_policy = gold_doc.get("evaluation_policy")
        if (
            not isinstance(layer_summary, Mapping)
            or layer_summary.get("formal_denominator") != denominator
            or not isinstance(evaluation_policy, Mapping)
            or evaluation_policy.get("formal_denominator") != denominator
        ):
            raise C5ScoreError(f"{case_id} 金标元数据分母漂移")
        verified.append(
            {
                "case_id": case_id,
                "formal_denominator": denominator,
                "formal_gold_sha256": str(gold["sha256"]),
                "gold_pointer_sha256": str(pointer["sha256"]),
                "formal_gold_model_visible": False,
                "formal_gold_text_emitted": False,
            }
        )
    return verified


def _verify_control_lock() -> dict[str, Any]:
    lock_path = C1_DIR / "request_lock.json"
    lock = read_json(lock_path)
    rows = lock.get("control_requests")
    if not isinstance(rows, list) or [row.get("case_id") for row in rows] != list(
        CASE_ORDER
    ):
        raise C5ScoreError("C1 对照请求锁漂移")

    requests: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row["case_id"])
        path = C1_DIR / str(row["path"])
        request = read_json(path)
        identity_sha = canonical_sha(request)
        if identity_sha != row.get("sha256"):
            raise C5ScoreError(f"{case_id} 对照请求身份 SHA 漂移")
        requests.append(
            {
                "case_id": case_id,
                "request_identity_sha256": identity_sha,
                "request_file_sha256": sha256_file(path),
                "execution_status": "FROZEN_NOT_SENT",
            }
        )

    c4_control_path = C4_RUN_DIR / "prepared/control_not_sent.json"
    c4_control = read_json(c4_control_path)
    c4_rows = c4_control.get("requests")
    if (
        c4_control.get("status") != "FROZEN_NOT_SENT"
        or c4_control.get("control_request_count") != 3
        or not isinstance(c4_rows, list)
        or any(row.get("execution_status") != "FROZEN_NOT_SENT" for row in c4_rows)
    ):
        raise C5ScoreError("C4 对照未发送票漂移")
    if (C4_RUN_DIR / "samples/control").exists():
        raise C5ScoreError("C4 意外存在 samples/control")
    if lock.get("c2_output_lock_state") != "not_created_zero_call_c1":
        raise C5ScoreError("C1 对照输出状态不再是未创建")

    return {
        "request_lock_sha256": sha256_file(lock_path),
        "control_not_sent_ticket_sha256": sha256_file(c4_control_path),
        "control_product_kind": "REQUESTS_ONLY",
        "control_output_exists": False,
        "control_semantic_score_exists": False,
        "requests": requests,
    }


def _selected_anchor_total(payload: Mapping[str, Any]) -> int:
    total = 0
    events = payload.get("events")
    if not isinstance(events, list):
        raise C5ScoreError("C4 候选件缺 events")
    for event in events:
        if not isinstance(event, Mapping):
            raise C5ScoreError("C4 候选事件不是对象")
        anchors = event.get("minimal_anchor_ids")
        if not isinstance(anchors, list):
            raise C5ScoreError("C4 候选事件缺 minimal_anchor_ids")
        total += len(anchors)
    return total


def _verify_treatment() -> dict[str, Any]:
    completion_path = C4_RUN_DIR / "completion/main.json"
    completion = read_json(completion_path)
    if (
        completion.get("status") != "main_mechanical_pass_pending_offline_score"
        or completion.get("case_ids") != list(CASE_ORDER)
        or completion.get("logical_samples") != 3
        or completion.get("quality_result_registered") is not False
    ):
        raise C5ScoreError("C4 主测完成票漂移")

    chapters: list[dict[str, Any]] = []
    for case_id in CASE_ORDER:
        candidate_path = (
            C4_RUN_DIR / f"samples/main/{case_id}/candidate/model_json.json"
        )
        mechanical_path = C4_RUN_DIR / f"samples/main/{case_id}/mechanical.json"
        candidate = read_json(candidate_path)
        mechanical = read_json(mechanical_path)
        if (
            mechanical.get("status") != "pass"
            or mechanical.get("case_id") != case_id
            or mechanical.get("finish_reason") != "stop"
            or mechanical.get("semantic_support_verified") is not False
            or mechanical.get("closed_anchor_validation", {}).get("status")
            != "pass"
        ):
            raise C5ScoreError(f"{case_id} C4 机械票漂移")
        event_count = len(candidate.get("events", []))
        if event_count != mechanical.get("event_count"):
            raise C5ScoreError(f"{case_id} C4 事件数不能重建")
        chapters.append(
            {
                "case_id": case_id,
                "formal_denominator": DENOMINATORS[case_id],
                "candidate_file_sha256": sha256_file(candidate_path),
                "mechanical_ticket_sha256": sha256_file(mechanical_path),
                "event_count": event_count,
                "selected_anchor_total": _selected_anchor_total(candidate),
                "mechanical_gate": "PASS",
                "semantic_support_verified": False,
            }
        )
    return {
        "main_completion_sha256": sha256_file(completion_path),
        "candidate_event_total": sum(row["event_count"] for row in chapters),
        "selected_anchor_total": sum(
            row["selected_anchor_total"] for row in chapters
        ),
        "chapters": chapters,
    }


def _missing_by_chapter() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_id in CASE_ORDER:
        rows.append(
            {
                "case_id": case_id,
                "formal_denominator": DENOMINATORS[case_id],
                "control": {
                    "ANCHOR_PARTIAL": "CONTROL_ANCHOR_PARTIAL_MISSING",
                    **{
                        layer: f"CONTROL_{layer.upper()}_MISSING"
                        for layer in SEMANTIC_LAYERS
                    },
                },
                "treatment": {
                    "ANCHOR_PARTIAL": "TREATMENT_ANCHOR_PARTIAL_MISSING",
                    **{
                        layer: f"TREATMENT_{layer.upper()}_MISSING"
                        for layer in SEMANTIC_LAYERS
                    },
                },
            }
        )
    return rows


def _gate_checks_missing() -> dict[str, Any]:
    return {
        "anchor_partial_relative_reduction_at_least_50_percent": (
            "MISSING_INPUT"
        ),
        "anchor_partial_declines_in_at_least_two_of_three_chapters": (
            "MISSING_INPUT"
        ),
        "fcr_qcr_asr_ucr_no_regression": "MISSING_INPUT",
        "sop_at_least_0_98": "MISSING_INPUT",
        "zero_additional_model_calls": "MODEL_API_CALL_BASELINE_AMBIGUOUS",
        "offline_denominator_is_49": True,
    }


def build_receipts() -> dict[str, bytes]:
    gate = _assert_gate_contract()
    gold = _verify_gold_identities()
    control = _verify_control_lock()
    treatment = _verify_treatment()
    missing_codes = [
        "CONTROL_OUTPUT_MISSING",
        "CONTROL_SCORE_DOCUMENT_MISSING",
        "C4_TO_GOLD_49_CROSSWALK_MISSING",
        "TREATMENT_ANCHOR_PARTIAL_MISSING",
        "TREATMENT_FCR_MISSING",
        "TREATMENT_QCR_FULL_MISSING",
        "TREATMENT_ASR_FULL_MISSING",
        "TREATMENT_UCR_MISSING",
        "TREATMENT_SOP_MISSING",
        "MODEL_API_CALL_BASELINE_AMBIGUOUS",
        "K_MISSING",
    ]
    sufficiency = {
        "schema_version": "v02-c5-material-sufficiency.v1",
        "status": "MATERIALS_INSUFFICIENT",
        "conclusion_options": sorted(ALLOWED_CONCLUSIONS),
        "selected_conclusion": CONCLUSION_MISSING,
        "formal_denominator": OFFLINE_DENOMINATOR,
        "denominators_by_case": DENOMINATORS,
        "gate_contract": gate,
        "gold_identity_checks": gold,
        "control_evidence": control,
        "treatment_evidence": treatment,
        "missing_codes": missing_codes,
        "missing_by_chapter": _missing_by_chapter(),
        "semantic_match_verdict_source": None,
        "candidate_silver_reviews_used_as_truth": False,
        "evaluate_gate_invoked": False,
        "model_api_calls": 0,
        "network_requests": 0,
        "formal_gold_text_emitted": False,
    }
    score_receipt = {
        "schema_version": "v02-c5-offline-score-receipt.v1",
        "status": CONCLUSION_MISSING,
        "selected_conclusion": CONCLUSION_MISSING,
        "reason": (
            "C1 只有三份未发送的对照请求；没有对照输出、对照分数，"
            "C4 也没有到 49 个计分原子的冻结语义映射与五层判词。"
        ),
        "gate_checks": _gate_checks_missing(),
        "chapter_scores": _missing_by_chapter(),
        "aggregate": {
            "formal_denominator": OFFLINE_DENOMINATOR,
            "ANCHOR_PARTIAL": "MISSING_INPUT",
            **{layer: "MISSING_INPUT" for layer in SEMANTIC_LAYERS},
        },
        "mechanical_facts_only": {
            "treatment_chapters_mechanical_passed": 3,
            "treatment_event_total": treatment["candidate_event_total"],
            "treatment_selected_anchor_total": treatment["selected_anchor_total"],
            "treatment_model_calls_already_spent_in_c4": 3,
            "c5_scoring_model_calls": 0,
        },
        "quality_result_registered": False,
        "judge_green_ticket_eligible": False,
        "judge_green_ticket_issued": False,
        "main_conclusion_may_be_changed_by_stability_resample": False,
        "formal_gold_text_emitted": False,
    }
    ownership = {
        "schema_version": "v02-c5-ownership-ticket.v1",
        "ownership": "V02_new_zone",
        "read_surfaces": [
            "V02_C1_supply_read_only",
            "V02_C4_r03_read_only",
            "formal_gold_identity_and_denominator_offline_only",
        ],
        "write_surfaces": ["V02_C5_offline_score"],
        "legacy_write_required": False,
        "stage": "P1_offline_score",
        "formal_gold_or_pointer_write": False,
        "current_chain_write": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts = {
        "material_sufficiency.json": canonical_bytes(sufficiency),
        "offline_score_receipt.json": canonical_bytes(score_receipt),
        "sealed_main_conclusion.json": canonical_bytes(
            {
                "schema_version": "v02-c5-sealed-main-conclusion.v1",
                "selected_conclusion": CONCLUSION_MISSING,
                "main_conclusion_locked_before_stability": True,
                "stability_diagnostic_may_not_change_conclusion": True,
                "offline_score_receipt_sha256": model_benchmark.sha256_bytes(
                    canonical_bytes(score_receipt)
                ),
                "model_api_calls": 0,
                "network_requests": 0,
            }
        ),
        "ownership_ticket.json": canonical_bytes(ownership),
    }
    manifest_preimage = {
        path: model_benchmark.sha256_bytes(raw)
        for path, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c5-offline-score-manifest.v1",
            "file_total_excluding_self": len(manifest_preimage),
            "files": [
                {"path": path, "sha256": digest}
                for path, digest in manifest_preimage.items()
            ],
            "artifact_set_sha256": canonical_sha(manifest_preimage),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def write_or_verify(output_dir: Path = C5_OUTPUT_DIR) -> dict[str, Any]:
    first = build_receipts()
    second = build_receipts()
    if first != second:
        raise C5ScoreError("C5 程序票连续两次构造不一致")
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(first.items()):
        path = output_dir / relative
        if path.is_file():
            if path.read_bytes() != raw:
                raise C5ScoreError(f"C5 已有程序票漂移：{relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual_files = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != set(first):
        raise C5ScoreError("C5 输出目录存在未登记文件")
    return {
        "status": CONCLUSION_MISSING,
        "output_dir": output_dir.resolve().as_posix(),
        "artifact_manifest_sha256": sha256_file(
            output_dir / "artifact_manifest.json"
        ),
        "offline_score_receipt_sha256": sha256_file(
            output_dir / "offline_score_receipt.json"
        ),
        "mechanical_double_run_identical": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=C5_OUTPUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            write_or_verify(args.output_dir.resolve()),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

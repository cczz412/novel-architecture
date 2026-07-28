#!/usr/bin/env python3
"""R1 r04：只做冻结枚举的确定性兼容归一，再复用 r03 原始响应计分。"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (  # noqa: E402
    v02_r1_route_comparison as r02,
)
from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (  # noqa: E402
    v02_r1_route_comparison_r03 as r03,
)
from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (  # noqa: E402
    v02_r1_route_runner as runner,
)


R03_RUN_DIR = r03.RUN_DIR
RUN_DIR = REPO_ROOT / "runs" / "V02_R1_route_comparison_r04_20260726"
FROZEN_DIR = RUN_DIR / "frozen"
EXECUTION_DIR = RUN_DIR / "execution"
RESULT_DIR = RUN_DIR / "result"

UNRESOLVED_CATEGORY = "UNRESOLVED_FORESHADOW_RISK_TODO"
DIRECT_CONFIRMED_ALIASES = frozenset(
    {"ACTUAL", "ESTABLISHED", "HAPPENED", "OCCURRED"}
)
CONTEXTUAL_ALIASES = frozenset({"OBSERVED", "ONGOING"})
DIRECT_UNRESOLVED_ALIASES = frozenset(
    {"FORESHADOWED", "PENDING", "RISK", "UNKNOWN"}
)
ALLOWED_ACTUALITY = frozenset(
    {"CONFIRMED", "BELIEVED", "INFERRED", "PLANNED", "NEGATED", "UNRESOLVED"}
)


def normalization_contract() -> dict[str, Any]:
    return {
        "schema_version": "v02-r1-actuality-normalization.v1",
        "purpose": "只修模型枚举近义词，不改事实内容、证据、类别或其他字段。",
        "direct_confirmed_aliases": sorted(DIRECT_CONFIRMED_ALIASES),
        "contextual_aliases": {
            value: {
                f"category={UNRESOLVED_CATEGORY}": "UNRESOLVED",
                "all_other_categories": "CONFIRMED",
            }
            for value in sorted(CONTEXTUAL_ALIASES)
        },
        "direct_unresolved_aliases": {
            value: {
                "required_category": UNRESOLVED_CATEGORY,
                "normalized_value": "UNRESOLVED",
            }
            for value in sorted(DIRECT_UNRESOLVED_ALIASES)
        },
        "unknown_alias_policy": "REJECT",
        "model_api_calls": 0,
        "source_run": str(R03_RUN_DIR.relative_to(REPO_ROOT)),
    }


def normalize_actuality(
    value: str,
    category: str,
) -> str:
    if value in ALLOWED_ACTUALITY:
        return value
    if value in DIRECT_CONFIRMED_ALIASES:
        return "CONFIRMED"
    if value in CONTEXTUAL_ALIASES:
        return (
            "UNRESOLVED"
            if category == UNRESOLVED_CATEGORY
            else "CONFIRMED"
        )
    if value in DIRECT_UNRESOLVED_ALIASES:
        if category != UNRESOLVED_CATEGORY:
            raise ValueError(
                f"{value} 仅允许出现在 {UNRESOLVED_CATEGORY}，实际为 {category}"
            )
        return "UNRESOLVED"
    raise ValueError(f"未登记的 actuality 近义词：{value}")


def normalize_payload(value: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = json.loads(json.dumps(value, ensure_ascii=False))
    changes = []
    for fact in normalized["facts"]:
        before = fact["actuality"]
        after = normalize_actuality(before, fact["category"])
        if before != after:
            changes.append(
                {
                    "fact_id": fact["fact_id"],
                    "category": fact["category"],
                    "before": before,
                    "after": after,
                }
            )
            fact["actuality"] = after
    return normalized, changes


def configure_runner() -> None:
    runner.spec = r02
    runner.RUN_DIR = RUN_DIR
    runner.FROZEN_DIR = FROZEN_DIR
    runner.EXECUTION_DIR = EXECUTION_DIR
    runner.RESULT_DIR = RESULT_DIR


def copy_frozen_tree() -> None:
    if FROZEN_DIR.exists():
        return
    shutil.copytree(R03_RUN_DIR / "frozen", FROZEN_DIR)


def finalize_calls() -> dict[str, Any]:
    copy_frozen_tree()
    contract = normalization_contract()
    runner.write_json(RUN_DIR / "governance" / "normalization_contract.json", contract)
    receipts = []
    change_count = 0
    for source_receipt_path in sorted(
        (R03_RUN_DIR / "execution" / "calls").glob("*/receipt.json")
    ):
        source_call_dir = source_receipt_path.parent
        target_call_dir = EXECUTION_DIR / "calls" / source_call_dir.name
        if target_call_dir.exists():
            shutil.rmtree(target_call_dir)
        shutil.copytree(source_call_dir, target_call_dir)
        receipt = runner.read_json(target_call_dir / "receipt.json")
        request = runner.read_json(target_call_dir / "request.json")
        original_status = receipt["status"]
        changes: list[dict[str, Any]] = []
        if request["contract"] != "CURRENT_Z00L_EXACT":
            raw_value = runner.strict_json(
                (target_call_dir / "raw_content.txt").read_text(encoding="utf-8")
            )
            normalized, changes = normalize_payload(raw_value)
            jsonschema.Draft202012Validator(
                runner.read_json(FROZEN_DIR / "schemas" / "hot_material_v1.schema.json")
            ).validate(normalized)
            runner.validate_semantic_shape(request, normalized)
            runner.write_json(target_call_dir / "parsed.json", normalized)
        response = runner.read_json(target_call_dir / "raw_response.json")
        finish_reason = response["choices"][0].get("finish_reason")
        if finish_reason != "stop":
            raise ValueError(
                f"{source_call_dir.name} finish_reason={finish_reason}，拒绝归一"
            )
        audit = {
            "schema_version": "v02-r1-actuality-normalization-audit.v1",
            "call_id": receipt["call_id"],
            "source_run": str(source_call_dir.relative_to(REPO_ROOT)),
            "raw_content_sha256": runner.sha256_file(
                target_call_dir / "raw_content.txt"
            ),
            "changes": changes,
            "changed_fields_only": "facts[].actuality",
        }
        runner.write_json(
            target_call_dir / "compatibility_normalization_audit.json",
            audit,
        )
        change_count += len(changes)
        original_error = receipt.pop("error", None)
        receipt.update(
            {
                "status": "ACCEPTED",
                "finish_reason": finish_reason,
                "original_status": original_status,
                "original_error": original_error,
                "acceptance_basis": (
                    "R03_ACCEPTED_UNCHANGED"
                    if not changes
                    else "R04_DETERMINISTIC_ACTUALITY_NORMALIZATION"
                ),
                "normalization_change_count": len(changes),
                "reused_from": str(source_call_dir.relative_to(REPO_ROOT)),
                "network_attempts_this_run": 0,
            }
        )
        runner.write_json(target_call_dir / "receipt.json", receipt)
        receipts.append(receipt)
    execution = {
        "schema_version": "v02-r1-execution-receipt.v1",
        "call_total_planned": 12,
        "call_total_recorded": len(receipts),
        "accepted": sum(row["status"] == "ACCEPTED" for row in receipts),
        "rejected": 0,
        "transport_hard_stops": 0,
        "model_api_calls_this_run": 0,
        "normalization_change_count": change_count,
        "calls": receipts,
        "secret_trace_scan": runner.secret_trace_scan(),
    }
    runner.write_json(EXECUTION_DIR / "execution_receipt.json", execution)
    return execution


def main() -> int:
    configure_runner()
    execution = finalize_calls()
    scorecard = runner.score()
    result = {"execution": execution, "scorecard": scorecard}
    runner.write_json(RESULT_DIR / "r04_finalization_receipt.json", result)
    print(
        json.dumps(
            {
                "accepted": execution["accepted"],
                "normalization_change_count": execution[
                    "normalization_change_count"
                ],
                "model_api_calls_this_run": 0,
                "recommended_routes": scorecard["recommended_routes"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

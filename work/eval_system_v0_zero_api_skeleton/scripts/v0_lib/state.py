from __future__ import annotations

from typing import Any


FORBIDDEN_SCORES = {0.5, "0.5", "half"}


def compare_pair(record: dict[str, Any]) -> dict[str, Any]:
    j1 = record["j1"]
    j2 = record["j2"]
    frozen_direction = record.get("frozen_direction")

    j1_ok = j1.get("mechanical_status") == "PASS"
    j2_ok = j2.get("mechanical_status") == "PASS"
    if not j1_ok or not j2_ok:
        return {
            "comparison_state": "MECHANICAL_STOP",
            "semantic_result": "NOT_EVALUATED",
            "verdict_match": None,
            "reason_code_match": None,
            "shared_deviation": None,
            "assessment_source": "NOT_EVALUATED",
            "eligibility": {
                "eligibility": "INELIGIBLE",
                "ineligibility_reason": "MECHANICAL_FAILURE",
                "policy_version": record.get("policy_version", "v0-skeleton"),
            },
        }

    verdict_match = j1.get("verdict") == j2.get("verdict")
    reason_code_match = j1.get("reason_code") == j2.get("reason_code")
    if verdict_match and reason_code_match:
        shared_deviation = (
            frozen_direction is not None and j1.get("verdict") != frozen_direction
        )
        return {
            "comparison_state": "COMPARISON_PASS",
            "semantic_result": j1.get("verdict"),
            "verdict_match": True,
            "reason_code_match": True,
            "shared_deviation": bool(shared_deviation),
            "assessment_source": "PAIR_COMPARISON",
            "eligibility": {
                "eligibility": "ELIGIBLE",
                "ineligibility_reason": None,
                "policy_version": record.get("policy_version", "v0-skeleton"),
            },
        }

    return {
        "comparison_state": "DISPUTE_STOP",
        "semantic_result": "UNRESOLVED_DISPUTE",
        "verdict_match": verdict_match,
        "reason_code_match": reason_code_match,
        "shared_deviation": None,
        "assessment_source": "PAIR_COMPARISON",
        "eligibility": {
            "eligibility": "INELIGIBLE",
            "ineligibility_reason": "UNRESOLVED_DISPUTE",
            "policy_version": record.get("policy_version", "v0-skeleton"),
        },
    }


def illegal_state_reason(record: dict[str, Any]) -> str | None:
    judges = record.get("judges")
    if isinstance(judges, list) and len(judges) > 2:
        return "THIRD_JUDGE_FORBIDDEN"
    if record.get("score") in FORBIDDEN_SCORES:
        return "HALF_SCORE_FORBIDDEN"
    if record.get("unreviewed_auto_fail") is True:
        return "UNREVIEWED_AUTO_FAIL_FORBIDDEN"
    parent = record.get("parent_task")
    children = record.get("child_tasks") or []
    if (
        isinstance(parent, dict)
        and parent.get("state") == "DONE"
        and any(child.get("state") == "STOP" for child in children)
        and record.get("parent_done_because_children_stopped") is True
    ):
        return "CHILD_STOP_IS_NOT_PARENT_DONE"
    proposed = record.get("proposed")
    if not isinstance(proposed, dict):
        return None
    computed = compare_pair(record)
    if proposed.get("comparison_state") == "MECHANICAL_STOP" and proposed.get(
        "semantic_result"
    ) in {"SUPPORTED", "REJECTED"}:
        return "MECHANICAL_STOP_CANNOT_MAP_TO_SEMANTIC_VERDICT"
    if proposed.get("comparison_state") == "DISPUTE_STOP" and proposed.get(
        "comparison_state_rewrite"
    ) == "COMPARISON_PASS":
        return "DISPUTE_CANNOT_BECOME_COMPARISON_PASS"
    if computed["comparison_state"] == "COMPARISON_PASS" and computed[
        "semantic_result"
    ] == "REJECTED" and proposed.get("semantic_result") == "SUPPORTED":
        return "COMPARISON_PASS_IS_NOT_SEMANTIC_PASS"
    for key in (
        "comparison_state",
        "semantic_result",
        "verdict_match",
        "reason_code_match",
    ):
        if key in proposed and proposed[key] != computed[key]:
            return f"PROPOSED_{key}_MISMATCH"
    return None

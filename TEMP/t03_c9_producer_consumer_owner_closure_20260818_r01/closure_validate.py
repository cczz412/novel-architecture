from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


sys.dont_write_bytecode = True

REPO_ROOT = Path("/Users/a1234/挣钱/小说架构")
ROOT = REPO_ROOT / "TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01"
PREVIOUS = REPO_ROOT / "TEMP/t03_c9_actuality_budget_candidate_skeleton_20260818_r01"
FILES = {
    "architecture": REPO_ROOT / "novel-mvp/ARCHITECTURE.md",
    "packer_design": REPO_ROOT / "novel-mvp/design/CONTEXT_PACKER_DESIGN_R01.md",
    "m8_design": REPO_ROOT / "novel-mvp/design/M8_PLANNING_DESIGN_R04.md",
    "plan_contract": REPO_ROOT / "novel-mvp/contracts/PLAN_LEDGER_STORAGE.md",
    "c4_contract": REPO_ROOT / "novel-mvp/contracts/C4_FACT_QUERY.md",
    "c7_contract": REPO_ROOT / "novel-mvp/contracts/C7_PLOT_LAYER.md",
    "plan_runtime": REPO_ROOT / "novel-mvp/mvp/plan.py",
    "cli_runtime": REPO_ROOT / "novel-mvp/cli.py",
}
SNAPSHOT = ROOT / "results/input_snapshot_before.json"
MATRIX = ROOT / "results/field_owner_matrix.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_ROOT_NOT_OBJECT:{path}")
    return value


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def collect_inputs() -> dict[str, Any]:
    rows = []
    for path in sorted(PREVIOUS.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            rows.append({"group": "PREVIOUS_SKELETON", "path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    for name, path in FILES.items():
        if not path.is_file():
            raise RuntimeError(f"MISSING_DIRECT_INPUT:{name}:{path}")
        rows.append({"group": "DIRECT_CURRENT_CONTRACT_OR_CONSUMER", "name": name, "path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    dedup = {row["path"]: row for row in rows}
    return {"identity": "C9_OWNER_CLOSURE_INPUT_SNAPSHOT", "created_at": utc_now(), "file_count": len(dedup), "files": [dedup[key] for key in sorted(dedup)]}


def snapshot_before() -> int:
    snapshot = collect_inputs()
    write_json_exclusive(SNAPSHOT, snapshot)
    print(json.dumps({"status": "PASS", "file_count": snapshot["file_count"]}, ensure_ascii=False, sort_keys=True))
    return 0


def validate() -> int:
    if not SNAPSHOT.is_file():
        raise RuntimeError("INPUT_SNAPSHOT_REQUIRED")
    previous = load_json(PREVIOUS / "candidate/c9_actuality_budget_candidate_skeleton.json")
    matrix = load_json(MATRIX)
    texts = {name: path.read_text(encoding="utf-8") for name, path in FILES.items()}
    packer_runtime = REPO_ROOT / "novel-mvp/mvp/packer.py"
    previous_inputs = set(previous["input_field_candidates"])
    previous_outputs = set(previous["output_field_candidates"])
    matrix_inputs = {row["field"] for row in matrix["input_fields"]}
    matrix_outputs = {row["field"] for row in matrix["output_fields"]}
    conditions = {
        "previous_skeleton_formal_false": previous["formal_c9"] is False and previous["formal_schema"] is False,
        "no_input_fields_added": matrix_inputs == previous_inputs,
        "no_output_fields_added": matrix_outputs == previous_outputs,
        "matrix_declares_no_schema_change": matrix["schema_changed"] is False and matrix["fields_added"] == [],
        "formal_plan_contract_declares_m11_producer_m8_consumer": "| C9 前提包候选  | 尚未冻结             | M11                            | M8" in texts["plan_contract"],
        "formal_plan_contract_declares_recompile_and_no_writeback": "任一来源提交变化即重编" in texts["plan_contract"] and "只读执行材料；不能回写" in texts["plan_contract"],
        "c4_owner_and_reader_boundary_present": "下游全部只读，确认／驳回／改判只走 M5 作者动作和 M4 事务 writer" in texts["c4_contract"] and "M6／M8／M11 只读这些记录" in texts["c4_contract"],
        "c4_current_truth_gate_present": "只有 current revision 上仍可回验的 `confirmed` 是当前真值" in texts["c4_contract"],
        "plan_contract_separates_planned_from_actual": "`digest_status=digested`：只表示已安排，不表示发生" in texts["plan_contract"] and "actual 是带 `support_set=[RE-…]` 的派生结果" in texts["plan_contract"],
        "packer_design_is_not_contract": "不是施工合同、不是数据库 Schema；C9 部分是字段建议" in texts["packer_design"],
        "packer_design_task_producer_is_design_only": "M0 编排器／M8" in texts["packer_design"],
        "packer_design_budget_owner_open": "预算档 | 本次包的 token 上限 | 配置（见开放问题 O1）" in texts["packer_design"] and "**O1｜前提包总预算怎么定？**" in texts["packer_design"],
        "packer_design_declares_m11_to_m8": "C9（M11→M8，新）" in texts["packer_design"],
        "runtime_packer_absent": not packer_runtime.exists(),
        "runtime_plan_bypasses_c9": "def confirmed_facts" in texts["plan_runtime"] and "store.facts(project)" in texts["plan_runtime"] and all(marker not in texts["plan_runtime"] for marker in ("C9", "premise_pack", "why_loaded", "load_ids", "budget_tokens")),
        "formal_c7_has_no_c9_lineage_field": all(marker not in texts["c7_contract"] for marker in ("premise_pack_ref", "why_loaded", "C9")),
        "m8_design_c9_is_still_pending": "| C9（落地时） | `why_loaded`" in texts["m8_design"] and "⏳ 挂账" in texts["m8_design"],
        "open_fields_not_assigned_to_m11": all(
            row["unique_owner"].startswith("OPEN") and "M11" not in row["allowed_producer"]
            for row in matrix["input_fields"]
            if row["closure"] == "OPEN"
        ),
        "all_outputs_runtime_open": all(row["real_runtime_consumer"] == "NONE_C9_ROUTE_NOT_IMPLEMENTED" for row in matrix["output_fields"]),
        "unresolved_and_evidence_open": matrix["authority_boundaries"]["unresolved_state"]["status"] == "OPEN_NO_DEFAULT" and matrix["authority_boundaries"]["evidence_recall"]["status"] == "OPEN_NO_DEFAULT",
        "actuality_and_budget_cannot_decide_open_seams": set(matrix["authority_boundaries"]["actuality"]["must_not_decide"]) == {"UNRESOLVED_STATE_POLICY", "EVIDENCE_RECALL_POLICY"} and "UNRESOLVED_STATE_POLICY" in matrix["authority_boundaries"]["budget"]["must_not_decide"],
    }
    closed = [
        "C4_FACT_SOURCE_OWNER_M4_M5_AND_CURRENT_CONFIRMED_READ_GATE",
        "PLANSTORE_OWNS_PLAN_JSON_AND_PLANNED_DOES_NOT_EQUAL_ACTUAL",
        "C9_DECLARED_PRODUCER_M11",
        "C9_DECLARED_CONSUMER_M8",
        "C9_STALE_ON_ANY_SOURCE_CHANGE_AND_NO_WRITEBACK",
        "M11_OWNS_ONLY_CANDIDATE_OUTPUT_SELECTION_AND_VERIFICATION",
        "PERMISSION_CAPABILITY_PROJECT_AND_HANDLE_REMAIN_EXTERNAL_PREFLIGHT"
    ]
    open_items = [
        "RUNTIME_M11_PACKER_IMPLEMENTATION",
        "RUNTIME_M8_C9_CONSUMER",
        "FORMAL_TASK_TICKET_PRODUCER_AND_CONTRACT",
        "BUDGET_CAP_OWNER_AND_VALUE",
        "TOKEN_ESTIMATOR_OWNER_AND_VERSION",
        "UNIFIED_ACTUALITY_MAPPING_ACROSS_C4_AND_PLANSTORE",
        "OBLIGATION_TIER_AND_SELECTION_RANK_OWNER",
        "UNRESOLVED_STATE_SEMANTICS",
        "EVIDENCE_RECALL_POLICY",
        "C9_TO_C7_LINEAGE_FIELDS_AND_CONSUMER_GATE"
    ]
    receipt = {
        "identity": "C9_PRODUCER_CONSUMER_OWNER_CLOSURE_RECEIPT",
        "status": "PASS_WITH_EXPLICIT_OPEN_RUNTIME_SEAMS" if all(conditions.values()) else "FAIL",
        "created_at": utc_now(),
        "stop_class": "CONTINUE_SAFE",
        "continuation_started": True,
        "conditions": conditions,
        "closed": closed,
        "open": open_items,
        "new_failure": False,
        "runtime_finding": {
            "mvp_packer_py": "ABSENT",
            "declared_c9_consumer": "M8",
            "runtime_c9_consumer": "NONE_IDENTIFIED",
            "legacy_bypass": "mvp/plan.py reads store.facts(project) directly and does not consume C9",
            "formal_c7_lineage": "NO_C9_OR_PREMISE_PACK_REF_FIELD"
        },
        "permissions": {"api": 0, "model_runs": 0, "retry": 0, "new_books": 0, "new_gold": 0, "formal_c9": 0, "product": 0, "r13": 0, "notion": 0, "git": 0}
    }
    write_json_exclusive(ROOT / "results/closure_receipt_v2.json", receipt)
    print(json.dumps({"status": receipt["status"], "checks": len(conditions), "closed": len(closed), "open": len(open_items)}, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["status"].startswith("PASS") else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-before", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.snapshot_before == args.validate:
        parser.error("choose exactly one mode")
    return snapshot_before() if args.snapshot_before else validate()


if __name__ == "__main__":
    raise SystemExit(main())

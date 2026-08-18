from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


sys.dont_write_bytecode = True

ROOT = Path("/Users/a1234/挣钱/小说架构/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01")
SNAPSHOT = ROOT / "results/input_snapshot_before.json"
DOCS = [
    "00_READ_ME_FIRST.md",
    "01_ONE_PAGE_JUNCTION_MAP.md",
    "02_FIELD_CLOSURE.md",
    "03_AUTHORITY_BOUNDARIES.md",
    "04_RUNTIME_CONSUMER_FINDING.md",
    "05_FAIL_CLOSED_RESPONSIBILITY.md",
    "06_CLOSED_AND_OPEN.md",
    "07_SELF_ACCEPTANCE.md",
]
PROTOCOL_FIELDS = [
    "WINDOW", "TASK_ID", "STATUS", "VERDICT", "DELIVERABLE_ROOT", "PRIMARY_RESULT",
    "MACHINE_RECEIPT", "API_MODEL_RETRY", "FORMAL_WRITES", "NEW_FAILURE",
    "DEPENDENCY_OR_WRITE_CONFLICT", "CZ_DECISION_REQUIRED", "SHARED_REVIEW_NEEDED",
    "NEXT_SAFE_TASK", "ONE_PARAGRAPH_SUMMARY", "STOP_CLASS", "CONTINUATION_STARTED"
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_ROOT_NOT_OBJECT:{path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def main() -> int:
    before_receipt = load_json(SNAPSHOT)
    before = {row["path"]: {"size_bytes": row["size_bytes"], "sha256": row["sha256"]} for row in before_receipt["files"]}
    after = {}
    for path_text in sorted(before):
        path = Path(path_text)
        if path.is_file():
            after[path_text] = {"size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
    changed = [{"path": path, "before": before[path], "after": after[path]} for path in sorted(set(before) & set(after)) if before[path] != after[path]]
    removed = sorted(set(before) - set(after))
    no_touch = {
        "identity": "C9_OWNER_CLOSURE_NO_TOUCH_SHA_RECEIPT",
        "status": "PASS" if not changed and not removed and len(after) == len(before) else "FAIL",
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "input_snapshot_path": str(SNAPSHOT),
        "input_snapshot_sha256": sha256_file(SNAPSHOT),
        "before_file_count": len(before),
        "after_file_count": len(after),
        "unchanged_file_count": len(before) - len(changed) - len(removed),
        "changed": changed,
        "removed": removed,
        "source_write_operations": 0
    }
    write_json_exclusive(ROOT / "results/no_touch_sha_receipt_v2.json", no_touch)

    matrix = load_json(ROOT / "results/field_owner_matrix.json")
    closure_v1 = load_json(ROOT / "results/closure_receipt.json")
    closure_v2 = load_json(ROOT / "results/closure_receipt_v2.json")
    capsule_path = ROOT / "STAGE_FINAL_CAPSULE.txt"
    capsule = capsule_path.read_text(encoding="utf-8")
    input_fields = matrix["input_fields"]
    output_fields = matrix["output_fields"]
    all_scoped_names = [f"input.{row['field']}" for row in input_fields] + [f"output.{row['field']}" for row in output_fields]
    conditions = {
        "all_docs_present": all((ROOT / path).is_file() for path in DOCS),
        "all_docs_source_marked": all((ROOT / path).read_text(encoding="utf-8").rstrip().endswith("来源：Codex") for path in DOCS),
        "no_touch_pass_25": no_touch["status"] == "PASS" and no_touch["unchanged_file_count"] == 25,
        "closure_v2_pass_21": closure_v2["status"] == "PASS_WITH_EXPLICIT_OPEN_RUNTIME_SEAMS" and len(closure_v2["conditions"]) == 21 and all(closure_v2["conditions"].values()),
        "closure_v1_fail_preserved": closure_v1["status"] == "FAIL" and closure_v1["conditions"]["open_fields_not_assigned_to_m11"] is False,
        "no_fields_or_schema_added": matrix["schema_changed"] is False and matrix["fields_added"] == [] and len(input_fields) == 9 and len(output_fields) == 7,
        "each_scoped_field_unique": len(all_scoped_names) == len(set(all_scoped_names)) == 16,
        "no_double_owner": all(isinstance(row["unique_owner"], str) and row["unique_owner"] for row in input_fields + output_fields),
        # M8 may appear in the design-only task-entry role. That does not grant
        # the C9 consumer role authority to rewrite M11's C9 output or sources.
        "consumer_cannot_backwrite": all("M8" not in row["allowed_producer"] for row in output_fields) and closure_v2["conditions"]["formal_plan_contract_declares_recompile_and_no_writeback"] is True,
        "no_formal_default_invented": matrix["authority_boundaries"]["unresolved_state"]["status"] == "OPEN_NO_DEFAULT" and matrix["authority_boundaries"]["evidence_recall"]["status"] == "OPEN_NO_DEFAULT" and all(row["unique_owner"].startswith("OPEN") for row in input_fields if row["closure"] == "OPEN"),
        "runtime_gap_explicit": closure_v2["runtime_finding"]["mvp_packer_py"] == "ABSENT" and closure_v2["runtime_finding"]["runtime_c9_consumer"] == "NONE_IDENTIFIED",
        "seven_closed_ten_open": len(closure_v2["closed"]) == 7 and len(closure_v2["open"]) == 10,
        "stop_class_continue_safe": closure_v2["stop_class"] == "CONTINUE_SAFE" and closure_v2["continuation_started"] is True,
        "no_new_failure": closure_v2["new_failure"] is False,
        "permissions_zero": all(value == 0 for value in closure_v2["permissions"].values()),
        "capsule_markers": capsule.startswith("STAGE_FINAL_CAPSULE\n") and capsule.rstrip().endswith("END_STAGE_FINAL_CAPSULE"),
        "capsule_fields_complete": all(f"{field}=" in capsule for field in PROTOCOL_FIELDS),
        "capsule_under_limit": len(capsule) <= 1800,
        "capsule_idle_and_no_shared_review": "NEXT_SAFE_TASK=IDLE_UNTIL_TOTAL_CONTROL_ASSIGNMENT" in capsule and "SHARED_REVIEW_NEEDED=NO" in capsule,
    }
    key_files = [ROOT / path for path in DOCS] + [
        ROOT / "results/field_owner_matrix.json",
        ROOT / "closure_validate.py",
        ROOT / "finalize_closure.py",
        ROOT / "STAGE_FINAL_CAPSULE.txt",
        ROOT / "results/input_snapshot_before.json",
        ROOT / "results/closure_receipt.json",
        ROOT / "results/closure_receipt_v2.json",
        ROOT / "results/no_touch_sha_receipt_v2.json"
    ]
    validation = {
        "identity": "C9_PRODUCER_CONSUMER_OWNER_CLOSURE_FINAL_VALIDATION",
        "status": "PASS" if all(conditions.values()) else "FAIL",
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "command": "uv run --locked python TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/finalize_closure.py",
        "conditions": conditions,
        "key_file_sha256": {str(path.relative_to(ROOT)): sha256_file(path) for path in key_files},
        "permissions": closure_v2["permissions"]
    }
    write_json_exclusive(ROOT / "results/final_validation_receipt_v2.json", validation)
    print(json.dumps({"status": validation["status"], "checks": len(conditions), "no_touch": no_touch["status"], "capsule_chars": len(capsule)}, ensure_ascii=False, sort_keys=True))
    return 0 if validation["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from typing import Any


REPO = Path(__file__).resolve().parents[4]
ROOT = Path(__file__).resolve().parents[1]
P3_TRACK_A = (
    REPO
    / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01"
    / "sealed_inputs_r01/track_a"
)
P4 = REPO / "finetuning/experiments/T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01"

TEMPLATE = P3_TRACK_A / "RIGHTS_DECISION_TEMPLATE.jsonl"
SOURCE_GROUPS = P3_TRACK_A / "RIGHTS_SOURCE_GROUPS_314.jsonl"
SCHEMA = P4 / "RIGHTS_DECISION_IMPORT_SCHEMA.json"
IMPORTER = P4 / "tools/rights_decision_import.py"
P4_PREFLIGHT_TICKET = P4 / "RIGHTS_IMPORT_PREFLIGHT_TICKET.md"
P4_DRY_RUN_RECEIPT = P4 / "RIGHTS_IMPORT_DRY_RUN_RECEIPT.json"
P4_MANIFEST = P4 / "P4_OUTPUT_MANIFEST.json"
P4_FINAL_RECEIPT = P4 / "P4_FINAL_VALIDATION_RECEIPT.json"
DECISION_CAPTURE = ROOT / "CZ_DECISION_CAPTURE.md"

DECISIONS = ROOT / "RIGHTS_DECISIONS_REJECT_74.jsonl"
CANDIDATE = ROOT / "RIGHTS_EXCLUSION_DERIVED_CANDIDATE.jsonl"
IMPORT_RECEIPT = ROOT / "RIGHTS_EXCLUSION_IMPORT_RECEIPT.json"
SOURCE_BINDING = ROOT / "SOURCE_BINDING.json"

EXPECTED_SHA = {
    TEMPLATE: "e8b870daedf4161f670f5dd73ee67814343115af2966353cfc50cfc0fc15b945",
    SOURCE_GROUPS: "08c576787d1d3153d95ed52dd4c5a0462ee7d08f66bca2be21df9fa66171db95",
    SCHEMA: "25b8434b8ae1e396a8b679bb60b2e91abd03c9dfd13745543a804705aafc8b6d",
    IMPORTER: "b8048e7e6b052580d202cbd444fd762d3aa8c7f3e6aacad2acd50b61d666241f",
    P4_PREFLIGHT_TICKET: "3d70ab8a026a92ae60525ef691e5e34a300db8cfc3c71f1eb2baebebedd50eda",
    P4_DRY_RUN_RECEIPT: "96978caf30ff31020d93f18f6142eb4c7275791cde45d59845cb79687022be72",
    P4_MANIFEST: "ca9633387866d89aba023a522f1eae8a159c0f1bfaf99914590f0249a44cec00",
    P4_FINAL_RECEIPT: "cd88d821623b3dcf4bb2055aa21ca8093147a66c6745f70b18185321041616a7",
}
GROUPS = 74
ROWS = 314
FACTS = 2783
NOTE = (
    "当前版本按 CZ 2026-08-08 决定退出内部训练路线；非法律权利定性；"
    "未来有真实证据时另开全量 revision 单组重审。"
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO.resolve()))


def load_importer() -> Any:
    if sha256_file(IMPORTER) != EXPECTED_SHA[IMPORTER]:
        raise RuntimeError("P4_IMPORTER_SHA_DRIFT")
    spec = importlib.util.spec_from_file_location("p4_rights_decision_import", IMPORTER)
    if spec is None or spec.loader is None:
        raise RuntimeError("P4_IMPORTER_SPEC_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_frozen_sources() -> None:
    for path, expected in EXPECTED_SHA.items():
        if not path.is_file():
            raise RuntimeError(f"FROZEN_SOURCE_MISSING:{relative(path)}")
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(
                f"FROZEN_SOURCE_SHA_DRIFT:{relative(path)}:expected={expected}:actual={actual}"
            )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    importer = load_importer()
    return importer.read_jsonl_bytes(path.read_bytes(), str(path))


def build_decision_rows() -> list[dict[str, Any]]:
    assert_frozen_sources()
    template_rows = read_jsonl(TEMPLATE)
    source_rows = read_jsonl(SOURCE_GROUPS)
    if len(template_rows) != GROUPS or len(source_rows) != GROUPS:
        raise RuntimeError("RIGHTS_GROUP_DENOMINATOR_DRIFT")
    if len({row["group_id"] for row in template_rows}) != GROUPS:
        raise RuntimeError("RIGHTS_TEMPLATE_GROUP_ID_NOT_UNIQUE")
    if len({row["group_id"] for row in source_rows}) != GROUPS:
        raise RuntimeError("RIGHTS_SOURCE_GROUP_ID_NOT_UNIQUE")
    sources = {row["group_id"]: row for row in source_rows}
    if sum(row["coverage"]["row_count"] for row in source_rows) != ROWS:
        raise RuntimeError("RIGHTS_SOURCE_ROW_COUNT_DRIFT")
    if sum(row["coverage"]["fact_count"] for row in source_rows) != FACTS:
        raise RuntimeError("RIGHTS_SOURCE_FACT_COUNT_DRIFT")

    decisions = []
    for template in template_rows:
        group_id = template["group_id"]
        source = sources.get(group_id)
        if source is None:
            raise RuntimeError(f"RIGHTS_SOURCE_GROUP_MISSING:{group_id}")
        identity = source["source_identity"]
        coverage = source["coverage"]
        expected_identity = {
            "source_id": identity["source_id"],
            "book_id": identity["book_id"],
            "book_title": identity["book_title"],
            "row_count": coverage["row_count"],
            "fact_count": coverage["fact_count"],
        }
        for key, expected in expected_identity.items():
            if template[key] != expected:
                raise RuntimeError(
                    f"RIGHTS_TEMPLATE_SOURCE_IDENTITY_DRIFT:{group_id}:{key}"
                )
        if template["cz_decision"] != "CZ_DECISION_REQUIRED":
            raise RuntimeError(f"RIGHTS_TEMPLATE_NOT_UNRESOLVED:{group_id}")
        if source["current_rights"]["status"] != "RIGHTS_UNKNOWN":
            raise RuntimeError(f"RIGHTS_SOURCE_NOT_UNKNOWN:{group_id}")
        decisions.append(
            {
                "group_id": group_id,
                **expected_identity,
                "cz_decision": "REJECT_FOR_TRAINING",
                "decision_scope": "INTERNAL_MODEL_TRAINING",
                "allowed_use": "FORBIDDEN",
                "cz_note": NOTE,
                "authority_document_path": None,
                "authority_document_sha256": None,
                "rights_holder": None,
                "validity": None,
                "author_id": None,
                "author_name": None,
                "source_sha256": None,
                "row_scope": None,
                "authority_snapshot_path": None,
                "authority_snapshot_sha256": None,
            }
        )
    if sum(row["row_count"] for row in decisions) != ROWS:
        raise RuntimeError("RIGHTS_DECISION_ROW_COUNT_DRIFT")
    if sum(row["fact_count"] for row in decisions) != FACTS:
        raise RuntimeError("RIGHTS_DECISION_FACT_COUNT_DRIFT")
    return decisions


def validate_candidate(candidate_bytes: bytes, receipt: dict[str, Any]) -> list[dict[str, Any]]:
    importer = load_importer()
    rows = importer.read_jsonl_bytes(candidate_bytes, "RIGHTS_EXCLUSION_DERIVED_CANDIDATE")
    if len(rows) != GROUPS or len({row["group_id"] for row in rows}) != GROUPS:
        raise RuntimeError("RIGHTS_CANDIDATE_DENOMINATOR_DRIFT")
    required = {
        "candidate_rights_status": "RIGHTS_REJECT_CANDIDATE",
        "candidate_status": "CANDIDATE_PENDING_CZ_CONFIRMATION",
        "allowed_use": "FORBIDDEN",
        "validity": None,
        "import_mode": "REALTIME_CANDIDATE",
        "replay_only": False,
        "test_only": False,
        "allow_verification": None,
        "cz_confirmation_required": True,
        "training_eligible": False,
        "production_promoted": False,
        "p2_sealed_modified": False,
    }
    for row in rows:
        for key, expected in required.items():
            if row.get(key) != expected:
                raise RuntimeError(f"RIGHTS_CANDIDATE_FIELD_MISMATCH:{row['group_id']}:{key}")
        if row["requested_decision"] != "REJECT_FOR_TRAINING":
            raise RuntimeError(f"RIGHTS_CANDIDATE_REQUEST_DRIFT:{row['group_id']}")
    coverage = receipt["coverage"]
    expected_coverage = {
        "source_groups": GROUPS,
        "rows": ROWS,
        "facts": FACTS,
        "allow_candidate": 0,
        "reject_candidate": GROUPS,
        "rights_unknown": 0,
        "unresolved_template": 0,
    }
    for key, expected in expected_coverage.items():
        if coverage[key] != expected:
            raise RuntimeError(f"RIGHTS_IMPORT_COVERAGE_MISMATCH:{key}")
    if receipt["status"] != "PASS_CANDIDATE_IMPORT_NO_PROMOTION":
        raise RuntimeError("RIGHTS_IMPORT_STATUS_MISMATCH")
    if receipt["mode"] != "REALTIME_CANDIDATE":
        raise RuntimeError("RIGHTS_IMPORT_MODE_MISMATCH")
    if receipt["safety"]["training_eligible_groups"] != 0:
        raise RuntimeError("RIGHTS_IMPORT_CREATED_TRAINING_ELIGIBILITY")
    if receipt["safety"]["production_promotions"] != 0:
        raise RuntimeError("RIGHTS_IMPORT_CREATED_PRODUCTION_PROMOTION")
    if receipt["output"]["sha256"] != sha256_bytes(candidate_bytes):
        raise RuntimeError("RIGHTS_IMPORT_OUTPUT_SHA_MISMATCH")
    return rows


def file_binding(path: Path, authority: str) -> dict[str, Any]:
    return {
        "path": relative(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "authority": authority,
    }


def build_source_binding(
    decisions_bytes: bytes,
    candidate_bytes: bytes,
    first_receipt: dict[str, Any],
    second_receipt: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "t5-r04-a-v2-7-rights-exclusion-source-binding-v1",
        "status": "CANDIDATE_PENDING_CZ_CONFIRMATION",
        "scope": "PROJECT_USE_DECISION_NOT_LEGAL_RIGHTS_DETERMINATION",
        "frozen_denominator": {"groups": GROUPS, "rows": ROWS, "facts": FACTS},
        "sources": {
            "p3_decision_template": file_binding(TEMPLATE, "P3_SEALED_INPUT"),
            "p3_source_groups": file_binding(SOURCE_GROUPS, "P3_SEALED_INPUT"),
            "p4_import_schema": file_binding(SCHEMA, "P4_FROZEN_IMPORT_CONTRACT"),
            "p4_importer": file_binding(IMPORTER, "P4_FROZEN_IMPORTER"),
            "p4_preflight_ticket": file_binding(P4_PREFLIGHT_TICKET, "P4_PREFLIGHT"),
            "p4_dry_run_receipt": file_binding(P4_DRY_RUN_RECEIPT, "P4_PREFLIGHT"),
            "p4_output_manifest": file_binding(P4_MANIFEST, "P4_FINAL"),
            "p4_final_receipt": file_binding(P4_FINAL_RECEIPT, "P4_FINAL"),
            "cz_decision_capture": file_binding(DECISION_CAPTURE, "CZ_DIRECT_PROJECT_USE_DECISION"),
        },
        "derived": {
            "decision_input": {
                "path": relative(DECISIONS),
                "sha256": sha256_bytes(decisions_bytes),
                "bytes": len(decisions_bytes),
                "rows": GROUPS,
            },
            "candidate": {
                "path": relative(CANDIDATE),
                "sha256": sha256_bytes(candidate_bytes),
                "bytes": len(candidate_bytes),
                "rows": GROUPS,
            },
            "import_receipt": file_binding(IMPORT_RECEIPT, "P4_REALTIME_CANDIDATE_IMPORT"),
        },
        "two_run_stability": {
            "decision_builds": 2,
            "decision_bytes_identical": True,
            "realtime_import_runs": 2,
            "candidate_bytes_identical": True,
            "candidate_sha256": sha256_bytes(candidate_bytes),
            "validation_date_run_1": first_receipt["validation_date"],
            "validation_date_run_2": second_receipt["validation_date"],
            "runtime_timestamp_is_receipt_sidecar_only": True,
        },
        "rights_boundary": {
            "original_source_status": "RIGHTS_UNKNOWN",
            "project_use_decision": "REJECT_FOR_TRAINING",
            "legal_rights_determination": False,
            "training_eligible": False,
            "production_promoted": False,
            "cz_confirmation_required": True,
        },
    }


def build() -> dict[str, Any]:
    ROOT.mkdir(parents=True, exist_ok=True)
    decision_first = canonical_jsonl_bytes(build_decision_rows())
    decision_second = canonical_jsonl_bytes(build_decision_rows())
    if decision_first != decision_second:
        raise RuntimeError("RIGHTS_DECISION_TWO_BUILD_NOT_BYTE_IDENTICAL")
    DECISIONS.write_bytes(decision_first)
    decisions_sha = sha256_bytes(decision_first)
    importer = load_importer()
    first_receipt = importer.import_frozen_decisions(
        mode=importer.MODE_REALTIME,
        decisions_path=DECISIONS,
        expected_decisions_sha256=decisions_sha,
        output_path=CANDIDATE,
        receipt_path=IMPORT_RECEIPT,
    )
    first_candidate = CANDIDATE.read_bytes()
    validate_candidate(first_candidate, first_receipt)
    with tempfile.TemporaryDirectory(prefix="p4-rights-exclusion-r2-") as temp_dir:
        temp = Path(temp_dir)
        second_output = temp / "candidate.jsonl"
        second_receipt_path = temp / "receipt.json"
        second_receipt = importer.import_frozen_decisions(
            mode=importer.MODE_REALTIME,
            decisions_path=DECISIONS,
            expected_decisions_sha256=decisions_sha,
            output_path=second_output,
            receipt_path=second_receipt_path,
        )
        second_candidate = second_output.read_bytes()
        validate_candidate(second_candidate, second_receipt)
    if first_candidate != second_candidate:
        raise RuntimeError("RIGHTS_CANDIDATE_TWO_RUN_NOT_BYTE_IDENTICAL")
    if first_receipt["validation_date"] != second_receipt["validation_date"]:
        raise RuntimeError("RIGHTS_CANDIDATE_TWO_RUN_DATE_BOUNDARY_CROSSED")
    binding = build_source_binding(
        decision_first,
        first_candidate,
        first_receipt,
        second_receipt,
    )
    SOURCE_BINDING.write_bytes(pretty_json_bytes(binding))
    return binding


def check() -> dict[str, Any]:
    assert_frozen_sources()
    expected_decisions = canonical_jsonl_bytes(build_decision_rows())
    if not DECISIONS.is_file() or DECISIONS.read_bytes() != expected_decisions:
        raise RuntimeError("RIGHTS_DECISION_INPUT_DRIFT")
    if not CANDIDATE.is_file() or not IMPORT_RECEIPT.is_file() or not SOURCE_BINDING.is_file():
        raise RuntimeError("RIGHTS_EXCLUSION_OUTPUT_MISSING")
    receipt = json.loads(IMPORT_RECEIPT.read_text(encoding="utf-8"))
    candidate_bytes = CANDIDATE.read_bytes()
    validate_candidate(candidate_bytes, receipt)
    binding = json.loads(SOURCE_BINDING.read_text(encoding="utf-8"))
    for row in binding["sources"].values():
        path = REPO / row["path"]
        if sha256_file(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
            raise RuntimeError(f"SOURCE_BINDING_DRIFT:{row['path']}")
    if binding["derived"]["decision_input"]["sha256"] != sha256_bytes(expected_decisions):
        raise RuntimeError("SOURCE_BINDING_DECISION_SHA_DRIFT")
    if binding["derived"]["candidate"]["sha256"] != sha256_bytes(candidate_bytes):
        raise RuntimeError("SOURCE_BINDING_CANDIDATE_SHA_DRIFT")
    if binding["derived"]["import_receipt"]["sha256"] != sha256_file(IMPORT_RECEIPT):
        raise RuntimeError("SOURCE_BINDING_IMPORT_RECEIPT_SHA_DRIFT")
    return binding


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()
    binding = build() if args.command == "build" else check()
    print(
        json.dumps(
            {
                "status": binding["status"],
                "groups": GROUPS,
                "rows": ROWS,
                "facts": FACTS,
                "decision_sha256": binding["derived"]["decision_input"]["sha256"],
                "candidate_sha256": binding["derived"]["candidate"]["sha256"],
                "candidate_two_run_byte_identical": binding["two_run_stability"][
                    "candidate_bytes_identical"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

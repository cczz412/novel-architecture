from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


EXP = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(EXP / "tools"))

from wo01_renderer import (  # noqa: E402
    ARM_ORDER,
    contains_forbidden_visible_metadata,
    parse_user_sections,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    return json.loads(path.read_bytes(), object_pairs_hook=no_duplicate_object)


def read_jsonl(path: Path) -> list[Any]:
    rows = []
    for line_number, line in enumerate(path.read_bytes().splitlines(), start=1):
        if line.strip():
            try:
                rows.append(json.loads(line, object_pairs_hook=no_duplicate_object))
            except Exception as error:
                raise RuntimeError(f"JSONL_INVALID:{path}:{line_number}:{error}") from error
    return rows


def validate_json_files() -> None:
    for path in sorted(EXP.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix == ".json":
            read_json(path)
        elif path.suffix == ".jsonl":
            read_jsonl(path)


def resolve_source(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else REPO / path


def validate_sources() -> None:
    binding = read_json(EXP / "SOURCE_BINDING.json")
    for source_id, record in binding["sources"].items():
        path = resolve_source(record["path"])
        if not path.is_file():
            raise RuntimeError(f"BOUND_SOURCE_MISSING:{source_id}:{path}")
        if sha256(path) != record["sha256"]:
            raise RuntimeError(f"BOUND_SOURCE_SHA_DRIFT:{source_id}")
        if path.stat().st_size != record["bytes"]:
            raise RuntimeError(f"BOUND_SOURCE_SIZE_DRIFT:{source_id}")
    if binding["model_run_authorized"] or binding["training_authorized"]:
        raise RuntimeError("SOURCE_BINDING_AUTHORITY_ESCALATION")


def validate_inputs() -> None:
    eligibility = read_jsonl(EXP / "ELIGIBILITY_MATRIX_24.jsonl")
    if len(eligibility) != 24 or len({row["case_id"] for row in eligibility}) != 24:
        raise RuntimeError("ELIGIBILITY_DENOMINATOR")
    if any(row["eligibility"] != "PASS" for row in eligibility):
        raise RuntimeError("ELIGIBILITY_NOT_ALL_PASS")
    if any(not row["small_vs_current_distinct"] for row in eligibility):
        raise RuntimeError("SMALL_CURRENT_NOT_ALL_DISTINCT")

    requests = {
        arm: read_jsonl(EXP / f"sealed_inputs_candidate/{arm}_REQUESTS_24.jsonl")
        for arm in ARM_ORDER
    }
    if any(len(rows) != 24 for rows in requests.values()):
        raise RuntimeError("REQUEST_DENOMINATOR")
    for row_index in range(24):
        visible = {arm: requests[arm][row_index] for arm in ARM_ORDER}
        if any(contains_forbidden_visible_metadata(value) for value in visible.values()):
            raise RuntimeError(f"MODEL_VISIBLE_METADATA_LEAK:{row_index}")
        systems = {value["messages"][0]["content"] for value in visible.values()}
        sections = {
            arm: parse_user_sections(value["messages"][1]["content"])
            for arm, value in visible.items()
        }
        if len(systems) != 1 or len({row["target"] for row in sections.values()}) != 1:
            raise RuntimeError(f"NON_CONTEXT_FIELD_DRIFT:{row_index}")
        if visible["TARGET_ONLY"] == visible["SMALL_HALO"]:
            raise RuntimeError(f"TARGET_SMALL_NOT_DISTINCT:{row_index}")
        if visible["SMALL_HALO"] == visible["CURRENT_WINDOW"]:
            raise RuntimeError(f"SMALL_CURRENT_NOT_DISTINCT:{row_index}")

    sidecar = read_jsonl(
        EXP / "sealed_inputs_candidate/HIDDEN_REQUEST_SIDECAR_72.jsonl"
    )
    if len(sidecar) != 72:
        raise RuntimeError("SIDECAR_DENOMINATOR")
    if len({(row["arm"], row["case_id"]) for row in sidecar}) != 72:
        raise RuntimeError("SIDECAR_IDENTITY_DUPLICATE")
    by_case: dict[str, list[dict[str, Any]]] = {}
    for row in sidecar:
        by_case.setdefault(row["case_id"], []).append(row)
    if len(by_case) != 24 or any(len(rows) != 3 for rows in by_case.values()):
        raise RuntimeError("SIDECAR_CASE_ARM_COVERAGE")
    for case_id, rows in by_case.items():
        for key in ("target_sha256", "gold_binding_sha256", "allowed_evidence_ids"):
            serialized = {json.dumps(row[key], sort_keys=True) for row in rows}
            if len(serialized) != 1:
                raise RuntimeError(f"SIDECAR_ARM_BINDING_DRIFT:{case_id}:{key}")

    diff = read_json(EXP / "MODEL_VISIBLE_DIFF_RECEIPT.json")
    required_diff = {
        "cases": 24,
        "requests": 72,
        "target_only_vs_small_distinct_cases": 24,
        "small_vs_current_distinct_cases": 24,
        "small_vs_current_structural_tie_cases": 0,
        "same_system_prompt_cases": 24,
        "same_numbered_target_cases": 24,
        "gold_mutation_input_unchanged_cases": 24,
        "visible_arm_or_case_label_leaks": 0,
    }
    for key, expected in required_diff.items():
        if diff[key] != expected:
            raise RuntimeError(f"DIFF_RECEIPT_MISMATCH:{key}:{diff[key]}")

    length = read_json(EXP / "LENGTH_REPORT.json")
    contract = length["measurement_contract"]
    if contract["tokenizer_loaded"] or contract["token_count_claimed"]:
        raise RuntimeError("LENGTH_REPORT_TOKEN_CLAIM")
    if len(length["per_case"]) != 24:
        raise RuntimeError("LENGTH_REPORT_DENOMINATOR")
    for row in length["per_case"]:
        arms = row["arms"]
        for metric in ("unicode_characters", "utf8_bytes"):
            if not (
                arms["TARGET_ONLY"][metric]
                < arms["SMALL_HALO"][metric]
                < arms["CURRENT_WINDOW"][metric]
            ):
                raise RuntimeError(f"LENGTH_NOT_MONOTONIC:{row['case_id']}:{metric}")


def validate_contracts() -> None:
    lock = read_json(EXP / "EXECUTION_LOCK.json")
    for key in ("model_run_authorized", "training_authorized", "api_authorized"):
        if lock[key]:
            raise RuntimeError(f"EXECUTION_AUTHORITY_ESCALATION:{key}")
    if lock["invariants"]["small_halo_unicode_characters_each_side"] != 8:
        raise RuntimeError("HALO_RULE_NOT_EIGHT")
    if lock["length_guard"]["tokenizer_loaded"]:
        raise RuntimeError("FINAL_PREFLIGHT_TOKENIZER_LOAD_CLAIM")
    for record in lock["sealed_inputs"].values():
        path = EXP / record["path"]
        if not path.is_file() or sha256(path) != record["sha256"]:
            raise RuntimeError(f"EXECUTION_LOCK_INPUT_DRIFT:{record['path']}")
    length_path = EXP / lock["length_guard"]["path"]
    if sha256(length_path) != lock["length_guard"]["sha256"]:
        raise RuntimeError("EXECUTION_LOCK_LENGTH_REPORT_DRIFT")
    for relative in (
        "TOKEN_BUDGET_REPORT.json",
        "tools/count_wo01_tokens.py",
    ):
        if (EXP / relative).exists():
            raise RuntimeError(f"INVALIDATED_TOKEN_ARTIFACT_PRESENT:{relative}")
    for relative in (
        "00_READ_ME_FIRST.md",
        "SCOPE_CONTRACT.md",
        "SCORING_AND_EXECUTION_PREREG.md",
        "RESULT_TICKET.md",
    ):
        if not (EXP / relative).read_text(encoding="utf-8").rstrip().endswith(
            "来源：Codex"
        ):
            raise RuntimeError(f"SOURCE_FOOTER_MISSING:{relative}")


def validate_manifest() -> None:
    manifest_path = EXP / "OUTPUT_MANIFEST.json"
    receipt_path = EXP / "FINAL_VALIDATION_RECEIPT.json"
    manifest = read_json(manifest_path)
    entries = manifest["members"]
    if len(entries) != manifest["member_count"]:
        raise RuntimeError("MANIFEST_MEMBER_COUNT")
    if len({row["path"] for row in entries}) != len(entries):
        raise RuntimeError("MANIFEST_DUPLICATE_PATH")
    for row in entries:
        path = EXP / row["path"]
        if not path.is_file():
            raise RuntimeError(f"MANIFEST_MEMBER_MISSING:{row['path']}")
        if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
            raise RuntimeError(f"MANIFEST_MEMBER_DRIFT:{row['path']}")
    receipt = read_json(receipt_path)
    if receipt["status"] != "PASS_WO01_PREFLIGHT_24_OF_24_READY_NO_RUN_AUTHORITY":
        raise RuntimeError("FINAL_RECEIPT_STATUS")
    if receipt["output_manifest_sha256"] != sha256(manifest_path):
        raise RuntimeError("FINAL_RECEIPT_MANIFEST_BINDING")


def validate(stage: str) -> dict[str, Any]:
    validate_json_files()
    validate_sources()
    validate_inputs()
    validate_contracts()
    if stage == "final":
        validate_manifest()
    return {
        "status": "PASS",
        "stage": stage,
        "eligible_cases": 24,
        "gold_facts": 48,
        "requests": 72,
        "target_only_vs_small_distinct_cases": 24,
        "small_vs_current_distinct_cases": 24,
        "model_run_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("pre", "final"), default="pre")
    args = parser.parse_args()
    print(json.dumps(validate(args.stage), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

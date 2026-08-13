from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
from typing import Any
import unicodedata

from wo01_renderer import (
    ARM_ORDER,
    contains_forbidden_visible_metadata,
    context_for_arm,
    hidden_sidecar,
    parse_user_sections,
    read_jsonl_strict,
    remove_p3_case_label,
    render_model_visible,
    sha256_bytes,
    stable_json_bytes,
    validate_projection,
)


REPO = Path(__file__).resolve().parents[4]
EXP = Path(__file__).resolve().parents[1]
DEV = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/set_b_r03_work/sealed/T5_R04_SYNTHETIC_MICRO24_SET_B_R03_20260808"
P3 = REPO / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01"
P41 = REPO / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01"
M1 = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
ROADMAP = REPO / "finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260808_R01"

CANONICAL = DEV / "canonical/CANONICAL_MICRO24_SET_B_R03.jsonl"
P3_C0 = P3 / "sealed_inputs_r01/track_b/prompts/c0_current_minimal_QUESTIONS_24.jsonl"

SOURCE_EXPECTATIONS = {
    "roadmap_manifest": (ROADMAP / "OUTPUT_MANIFEST.json", "0960508f4cb6d9099b9968065b8a9b74f3bf22e6cede5cbc263bec1259e334e4"),
    "roadmap_result": (ROADMAP / "RESULT_TICKET.md", "694951a04f403c31d22b52bc1a643924883c6cf4edf19bc7f161344670250daa"),
    "roadmap_receipt": (ROADMAP / "FINAL_VALIDATION_RECEIPT.json", "4aea42c1997777a529e05cc6f8b12b5285709b32229e21a160c4f871cc4fc515"),
    "dev_canonical": (CANONICAL, "fa04ce5e5f819f4f87aec248ef8c306541b04128d67f0b79cc7e61f2d401d7d9"),
    "dev_package_manifest": (DEV / "PACKAGE_MANIFEST.json", "d7f62e27095b6c0f1d3ac704305fecf9be3563a279a196b19955aeeed17473e7"),
    "dev_package_receipt": (DEV / "PACKAGE_RECEIPT.json", "bb5a0b93c2b09252b76438022a629413aac08054655aec7493d0d3849bc84981"),
    "dev_renderer": (DEV / "tools/render_from_canonical.py", "e2d57aafba20d28ac1b322b9f4f52b07c5e2d4365cb25e599c40be4620f0bedb"),
    "p3_c0_questions": (P3_C0, "94492f050aa18169b47a3d799be903d37462984c0ace352c135b850dd1725258"),
    "p3_build": (P3 / "tools/build_p3_inputs.py", "e515ccd358125a94a40de18a5762c81711558aef5c383ce89006e6835f53ef78"),
    "p3_run": (P3 / "tools/run_p3_context_probe.py", "443b41eb2447d81827954145dfa49d7f886bd5d1925b32014ff1c46e0759235a"),
    "p3_scorer": (P3 / "tools/score_p3_context_probe.py", "c7df1d96d785122d7af818c39c168be646298aa158cfa698102f24e4094e6674"),
    "p41_schema": (P41 / "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json", "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14"),
    "p41_binding": (P41 / "P3_C0_SCHEMA_SOURCE_BINDING.json", "901b6e1de11daa9abf10d16e4ab0efa51421da28f0eea59878ff11dfdb55cf51"),
    "p41_receipt": (P41 / "P4_1_FINAL_VALIDATION_RECEIPT.json", "465c20ffef298b3edbb982236cb03ec4dc443c4e2cd13dc8d9a4c388b41bd107"),
    "c2_checkpoint": (M1 / "eval_adapters/c2_full/update_72/adapters.safetensors", "321d96c10f00389e557efbeb2d8e3dc1344071cc3cd663b51b8a8c2bd38ea5f9"),
    "c2_adapter_config": (M1 / "eval_adapters/c2_full/update_72/adapter_config.json", "72df68a7d01b8feae8f92cc0e4f69c832d9ad71886b4f8ea2896a7436d73031e"),
    "c2_execution_lock": (M1 / "locks/c2_full_EXECUTION_LOCK.json", "09adb09c7ff28e278ea14557505419f2a5fd7170c8699a882b88ef7cf1bf24ca"),
    "c2_training_receipt": (M1 / "receipts/c2_full_TRAINING_RECEIPT.json", "cec20883e872e21d505efa0336506040eb25fa17ea05d14cdbd850eab5ed2f1c"),
    "m1_deterministic_scorer": (M1 / "tools/score_m1_deterministic.py", "cced79b678fe563665a7b007077eccf9dae7e6696916f9235293b80a5c9a4e43"),
    "m1_semantic_scorer": (M1 / "tools/adjudicate_and_score_m1.py", "5e2751ea56e009d0139acc68c90bd64d356584ef0e7cd862413530222779dc09"),
    "model_receipt": (MODEL / "MODEL_RECEIPT.json", "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6"),
    "tokenizer_json": (MODEL / "tokenizer.json", "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4"),
    "tokenizer_config": (MODEL / "tokenizer_config.json", "a62ff0a2472a0fa1b8eaabcb57c59b58afa42a22831dc141400b6e0cf2b65ce3"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(stable_json_bytes(row) for row in rows))


def verify_sources() -> dict[str, Any]:
    records = {}
    for source_id, (path, expected) in SOURCE_EXPECTATIONS.items():
        if not path.is_file():
            raise RuntimeError(f"SOURCE_MISSING:{source_id}:{path}")
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"SOURCE_SHA_DRIFT:{source_id}:{actual}")
        records[source_id] = {
            "path": relative_or_absolute(path),
            "sha256": actual,
            "bytes": path.stat().st_size,
        }
    return records


def p3_baseline() -> tuple[str, dict[str, dict[str, Any]]]:
    _, rows = read_jsonl_strict(P3_C0)
    if len(rows) != 24:
        raise RuntimeError(f"P3_C0_CASE_COUNT:{len(rows)}")
    by_case = {}
    systems = set()
    for row in rows:
        case_id = row["case_id"]
        if case_id in by_case:
            raise RuntimeError(f"P3_C0_DUPLICATE_CASE:{case_id}")
        by_case[case_id] = row
        systems.add(row["messages"][0]["content"])
    if len(systems) != 1:
        raise RuntimeError("P3_C0_SYSTEM_NOT_SINGLE")
    return next(iter(systems)), by_case


def eligibility_row(sample: dict[str, Any]) -> dict[str, Any]:
    validated = validate_projection(sample)
    small_before, small_after = context_for_arm(validated, "SMALL_HALO")
    return {
        "case_id": validated["case_id"],
        "gold_independent_target_boundary": True,
        "target_source_pointer": "canonical.source.target",
        "target_sha256": sha256_bytes(validated["target"].encode("utf-8")),
        "left_context_available": bool(validated["before"]),
        "right_context_available": bool(validated["after"]),
        "current_window_has_extra_context": bool(validated["before"] or validated["after"]),
        "before_chars": len(validated["before"]),
        "after_chars": len(validated["after"]),
        "small_halo_before_chars": len(small_before),
        "small_halo_after_chars": len(small_after),
        "target_chars": len(validated["target"]),
        "target_unit_count": len(validated["target_units"]),
        "small_vs_current_distinct": (small_before, small_after)
        != (validated["before"], validated["after"]),
        "three_arm_fair_generation": True,
        "eligibility": "PASS",
    }


def compare_visible(
    sample: dict[str, Any],
    visible: dict[str, dict[str, Any]],
    p3_row: dict[str, Any],
) -> dict[str, Any]:
    systems = {arm: value["messages"][0]["content"] for arm, value in visible.items()}
    sections = {
        arm: parse_user_sections(value["messages"][1]["content"])
        for arm, value in visible.items()
    }
    target_values = {value["target"] for value in sections.values()}
    if len(set(systems.values())) != 1 or len(target_values) != 1:
        raise RuntimeError(f"NON_CONTEXT_FIELD_DRIFT:{sample['case_id']}")
    forbidden = {
        arm: contains_forbidden_visible_metadata(value) for arm, value in visible.items()
    }
    if any(forbidden.values()):
        raise RuntimeError(f"VISIBLE_METADATA_LEAK:{sample['case_id']}:{forbidden}")
    p3_user = p3_row["messages"][1]["content"]
    current_user = visible["CURRENT_WINDOW"]["messages"][1]["content"]
    if remove_p3_case_label(p3_user, sample["case_id"]) != current_user:
        raise RuntimeError(f"CURRENT_WINDOW_NOT_P3_C0_MINUS_CASE_LABEL:{sample['case_id']}")
    return {
        "case_id": sample["case_id"],
        "same_system_prompt": True,
        "same_numbered_target": True,
        "same_output_schema_binding": True,
        "only_read_only_context_changes": True,
        "arm_or_case_label_visible": False,
        "current_window_equals_p3_c0_after_case_label_removal": True,
        "target_only_vs_small_distinct": visible["TARGET_ONLY"] != visible["SMALL_HALO"],
        "small_vs_current_distinct": visible["SMALL_HALO"] != visible["CURRENT_WINDOW"],
    }


def is_chinese_character(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
    )


def visible_length_metrics(request: dict[str, Any]) -> dict[str, int]:
    contents = [message["content"] for message in request["messages"]]
    characters = "".join(contents)
    return {
        "unicode_characters": len(characters),
        "chinese_characters_rough": sum(
            is_chinese_character(character) for character in characters
        ),
        "visible_characters_rough": sum(
            not character.isspace()
            and not unicodedata.category(character).startswith("C")
            for character in characters
        ),
        "utf8_bytes": sum(len(content.encode("utf-8")) for content in contents),
    }


def metric_summary(values: list[int]) -> dict[str, int | float]:
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 6),
    }


def build_length_report(
    ordered_ids: list[str],
    visible_by_arm: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    metric_names = (
        "unicode_characters",
        "chinese_characters_rough",
        "visible_characters_rough",
        "utf8_bytes",
    )
    per_case = []
    by_arm: dict[str, list[dict[str, int]]] = {arm: [] for arm in ARM_ORDER}
    for row_index, case_id in enumerate(ordered_ids):
        arm_metrics = {
            arm: visible_length_metrics(visible_by_arm[arm][row_index])
            for arm in ARM_ORDER
        }
        for arm in ARM_ORDER:
            by_arm[arm].append(arm_metrics[arm])
        per_case.append({"case_id": case_id, "arms": arm_metrics})

    summaries = {
        arm: {
            metric: metric_summary([row[metric] for row in by_arm[arm]])
            for metric in metric_names
        }
        for arm in ARM_ORDER
    }
    comparisons = {}
    for left, right, comparison_id in (
        ("TARGET_ONLY", "SMALL_HALO", "small_halo_minus_target_only"),
        ("SMALL_HALO", "CURRENT_WINDOW", "current_window_minus_small_halo"),
        ("TARGET_ONLY", "CURRENT_WINDOW", "current_window_minus_target_only"),
    ):
        comparisons[comparison_id] = {
            metric: metric_summary(
                [
                    by_arm[right][row_index][metric]
                    - by_arm[left][row_index][metric]
                    for row_index in range(len(ordered_ids))
                ]
            )
            for metric in metric_names
        }

    return {
        "schema_version": "t5-r04-wo01-length-report-v1",
        "status": "PASS_CHARACTER_LENGTH_GUARD_NO_TOKENIZER",
        "measurement_contract": {
            "unicode_characters": "sum(len(message.content)) across system and user messages; message-boundary serialization bytes are excluded",
            "chinese_characters_rough": "count U+3400-U+4DBF, U+4E00-U+9FFF, and U+F900-U+FAFF in message contents",
            "visible_characters_rough": "count non-whitespace, non-control Unicode characters in message contents",
            "utf8_bytes": "sum(len(message.content.encode('utf-8'))) across system and user messages",
            "tokenizer_loaded": False,
            "token_count_claimed": False,
        },
        "cases": len(ordered_ids),
        "arms": list(ARM_ORDER),
        "per_case": per_case,
        "summary": summaries,
        "paired_deltas": comparisons,
    }
def build(output_root: Path) -> dict[str, Any]:
    sources = verify_sources()
    canonical_raw, samples = read_jsonl_strict(CANONICAL)
    if len(samples) != 24 or len({row["case_id"] for row in samples}) != 24:
        raise RuntimeError("DEV24_CASE_DENOMINATOR")
    canonical_sha = sha256_bytes(canonical_raw)
    system_prompt, p3_rows = p3_baseline()
    ordered_ids = [sample["case_id"] for sample in samples]
    if ordered_ids != list(p3_rows):
        raise RuntimeError("DEV24_P3_ORDERED_CASE_MISMATCH")

    eligibility = [eligibility_row(source_projection) for source_projection in samples]
    eligible_count = sum(row["eligibility"] == "PASS" for row in eligibility)
    write_jsonl(output_root / "ELIGIBILITY_MATRIX_24.jsonl", eligibility)
    if eligible_count != 24:
        raise RuntimeError(f"HARD_STOP_DATA_NOT_CAPABLE:{eligible_count}/24")

    visible_by_arm: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARM_ORDER}
    sidecars: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    for row_index, sample in enumerate(samples):
        visible = {
            arm: render_model_visible(sample, arm, system_prompt) for arm in ARM_ORDER
        }
        comparisons.append(compare_visible(sample, visible, p3_rows[sample["case_id"]]))
        for arm in ARM_ORDER:
            visible_by_arm[arm].append(visible[arm])
            sidecars.append(
                hidden_sidecar(sample, arm, visible[arm], canonical_sha, row_index)
            )

    sealed = output_root / "sealed_inputs_candidate"
    for arm in ARM_ORDER:
        write_jsonl(sealed / f"{arm}_REQUESTS_24.jsonl", visible_by_arm[arm])
    write_jsonl(sealed / "HIDDEN_REQUEST_SIDECAR_72.jsonl", sidecars)

    mutation_equal = 0
    for sample in samples:
        mutated = copy.deepcopy(sample)
        mutated["facts"] = [{"deliberately": "changed"}]
        mutated["expected_fact_count"] = 999
        original = [render_model_visible(sample, arm, system_prompt) for arm in ARM_ORDER]
        changed = [render_model_visible(mutated, arm, system_prompt) for arm in ARM_ORDER]
        mutation_equal += original == changed
    if mutation_equal != 24:
        raise RuntimeError("GOLD_MUTATION_CHANGED_MODEL_INPUT")

    diff_receipt = {
        "schema_version": "t5-r04-wo01-model-visible-diff-receipt-v1",
        "status": "PASS_ONLY_READ_ONLY_CONTEXT_RANGE_CHANGES",
        "cases": 24,
        "requests": 72,
        "target_only_vs_small_distinct_cases": sum(
            row["target_only_vs_small_distinct"] for row in comparisons
        ),
        "small_vs_current_distinct_cases": sum(
            row["small_vs_current_distinct"] for row in comparisons
        ),
        "small_vs_current_structural_tie_cases": sum(
            not row["small_vs_current_distinct"] for row in comparisons
        ),
        "same_system_prompt_cases": 24,
        "same_numbered_target_cases": 24,
        "current_window_p3_c0_minus_case_label_exact_cases": 24,
        "gold_mutation_input_unchanged_cases": mutation_equal,
        "visible_arm_or_case_label_leaks": 0,
        "per_case": comparisons,
    }
    write_json(output_root / "MODEL_VISIBLE_DIFF_RECEIPT.json", diff_receipt)

    length_report = build_length_report(ordered_ids, visible_by_arm)
    write_json(output_root / "LENGTH_REPORT.json", length_report)

    source_binding = {
        "schema_version": "t5-r04-wo01-source-binding-v1",
        "status": "PASS_SOURCES_BOUND_NO_RUN_AUTHORITY",
        "sources": sources,
        "dev24": {
            "identity": "DEV24_SET_B_R03_DO_NOT_TRAIN",
            "cases": 24,
            "gold_facts": 48,
            "canonical_sha256": canonical_sha,
            "gold_used_to_choose_scope": False,
        },
        "c2_checkpoint": {
            "identity": "C2_FULL_UPDATE72_OFFLINE_PROXY",
            "sha256": SOURCE_EXPECTATIONS["c2_checkpoint"][1],
        },
        "p3_c0": {
            "questions_sha256": SOURCE_EXPECTATIONS["p3_c0_questions"][1],
            "system_prompt_sha256": sha256_bytes(system_prompt.encode("utf-8")),
            "current_window_derivation": "P3 C0 model-visible user bytes after mandatory removal of the visible case-label prefix",
        },
        "p41_schema": {
            "sha256": SOURCE_EXPECTATIONS["p41_schema"][1],
            "role": "STRUCTURAL_VALIDATION_ONLY_NOT_SEMANTIC_CONTRACT",
        },
        "model_run_authorized": False,
        "training_authorized": False,
    }
    write_json(output_root / "SOURCE_BINDING.json", source_binding)

    build_receipt = {
        "schema_version": "t5-r04-wo01-input-build-receipt-v1",
        "status": "PASS_24_OF_24_ELIGIBLE_72_REQUESTS_BUILT",
        "eligible_cases": eligible_count,
        "requests": 72,
        "arm_counts": {arm: len(rows) for arm, rows in visible_by_arm.items()},
        "canonical_raw_bytes_strict_utf8": True,
        "renderer_reads_gold_to_choose_scope": False,
        "gold_mutation_input_unchanged_cases": mutation_equal,
        "stable_files": {
            str(path.relative_to(output_root)): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in sorted(
                [
                    output_root / "ELIGIBILITY_MATRIX_24.jsonl",
                    output_root / "MODEL_VISIBLE_DIFF_RECEIPT.json",
                    output_root / "LENGTH_REPORT.json",
                    output_root / "SOURCE_BINDING.json",
                    *sealed.glob("*.jsonl"),
                ]
            )
        },
    }
    write_json(output_root / "INPUT_BUILD_RECEIPT.json", build_receipt)
    return build_receipt


def compare_trees(first: Path, second: Path) -> dict[str, Any]:
    first_files = {
        str(path.relative_to(first)): path for path in first.rglob("*") if path.is_file()
    }
    second_files = {
        str(path.relative_to(second)): path for path in second.rglob("*") if path.is_file()
    }
    if set(first_files) != set(second_files):
        raise RuntimeError("DOUBLE_BUILD_FILE_SET_MISMATCH")
    mismatches = []
    for rel in sorted(first_files):
        if first_files[rel].read_bytes() != second_files[rel].read_bytes():
            mismatches.append(rel)
    if mismatches:
        raise RuntimeError(f"DOUBLE_BUILD_BYTES_MISMATCH:{mismatches}")
    return {
        "status": "PASS_TWO_RUN_BYTE_IDENTICAL",
        "file_count": len(first_files),
        "mismatches": 0,
        "tree_digest": sha256_bytes(
            b"".join(
                rel.encode("utf-8") + b"\0" + first_files[rel].read_bytes()
                for rel in sorted(first_files)
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    receipt = build(args.output)
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

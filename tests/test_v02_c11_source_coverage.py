from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "V02_C11_product_north_star_20260725"
    / "C11_3_source_coverage"
    / "program"
)
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import v02_c11_source_coverage as coverage  # noqa: E402


pytestmark = pytest.mark.v02


@pytest.fixture(scope="module")
def actual_artifacts() -> dict[str, bytes]:
    required = [
        coverage.SOURCE_MANIFEST,
        coverage.TREATMENT_RUN,
        coverage.CONTROL_RUN,
    ]
    if not all(path.exists() for path in required):
        pytest.skip("C11.3 本地冻结证据不齐")
    return coverage.build_artifacts()


def test_physical_line_then_sentence_end_segmentation_has_exact_offsets() -> None:
    body = "甲。乙！\n丙\n※※※"
    units = coverage.segment_source_body("CASE", body)
    assert [(unit["start_char"], unit["end_char_exclusive"]) for unit in units] == [
        (0, 2),
        (2, 4),
        (5, 6),
        (7, 10),
    ]
    assert [unit["line_number"] for unit in units] == [1, 1, 2, 3]
    assert units[-1]["mechanical_kind"] == "SEPARATOR_ONLY"
    assert all("text" not in unit for unit in units)
    assert units[0]["text_sha256"] == coverage.sha256_bytes("甲。".encode("utf-8"))


def test_unique_max_overlap_scores_only_covered_unit() -> None:
    body = "甲乙丙丁"
    units = coverage.segment_source_body("CASE", body)
    units = [
        {
            **units[0],
            "unit_id": "CASE-SU-0001",
            "ordinal": 1,
            "start_char": 0,
            "end_char_exclusive": 2,
        },
        {
            **units[0],
            "unit_id": "CASE-SU-0002",
            "ordinal": 2,
            "start_char": 2,
            "end_char_exclusive": 4,
        },
    ]
    built = coverage.build_arm_ledger(
        arm="control",
        case_id="CASE",
        body=body,
        units=units,
        catalog={
            "E0001": {
                "body_start_char": 0,
                "body_end_char_exclusive": 2,
            }
        },
        events=[{"event_id": "EV-01", "anchor_ids": ["E0001"]}],
    )
    assert [unit["state"] for unit in built["units"]] == [
        "SCORE",
        "REVIEW",
    ]
    assert built["units"][0]["covered_by"] == ["EV-01"]
    assert built["units"][1]["covered_by"] == []


def test_tied_max_overlap_never_becomes_score() -> None:
    body = "甲乙丙丁"
    units = [
        {
            "unit_id": "CASE-SU-0001",
            "ordinal": 1,
            "case_id": "CASE",
            "line_number": 1,
            "start_char": 0,
            "end_char_exclusive": 2,
            "text_sha256": "1" * 64,
            "nonspace_char_count": 2,
            "mechanical_kind": "CONTENT_CANDIDATE",
        },
        {
            "unit_id": "CASE-SU-0002",
            "ordinal": 2,
            "case_id": "CASE",
            "line_number": 1,
            "start_char": 2,
            "end_char_exclusive": 4,
            "text_sha256": "2" * 64,
            "nonspace_char_count": 2,
            "mechanical_kind": "CONTENT_CANDIDATE",
        },
    ]
    built = coverage.build_arm_ledger(
        arm="treatment",
        case_id="CASE",
        body=body,
        units=units,
        catalog={
            "E0001": {
                "body_start_char": 1,
                "body_end_char_exclusive": 3,
            }
        },
        events=[{"event_id": "EV-01", "anchor_ids": ["E0001"]}],
    )
    assert [unit["state"] for unit in built["units"]] == [
        "REVIEW",
        "REVIEW",
    ]
    assert all(unit["covered_by"] == [] for unit in built["units"])
    assert built["anchor_resolution"][0]["status"] == "TIED_MAX_REVIEW"


def test_tie_on_one_anchor_does_not_demote_other_unique_anchor() -> None:
    body = "甲乙丙丁戊己"
    units = [
        {
            "unit_id": f"CASE-SU-{index + 1:04d}",
            "ordinal": index + 1,
            "case_id": "CASE",
            "line_number": 1,
            "start_char": index * 2,
            "end_char_exclusive": index * 2 + 2,
            "text_sha256": str(index + 1) * 64,
            "nonspace_char_count": 2,
            "mechanical_kind": "CONTENT_CANDIDATE",
        }
        for index in range(3)
    ]
    built = coverage.build_arm_ledger(
        arm="treatment",
        case_id="CASE",
        body=body,
        units=units,
        catalog={
            "E0001": {
                "body_start_char": 1,
                "body_end_char_exclusive": 3,
            },
            "E0002": {
                "body_start_char": 4,
                "body_end_char_exclusive": 6,
            },
        },
        events=[
            {
                "event_id": "EV-01",
                "anchor_ids": ["E0001", "E0002"],
            }
        ],
    )
    assert [unit["state"] for unit in built["units"]] == [
        "REVIEW",
        "REVIEW",
        "SCORE",
    ]
    assert built["units"][2]["covering_anchor_ids"] == ["E0002"]


def test_outside_catalog_anchor_is_hard_rejected() -> None:
    units = coverage.segment_source_body("CASE", "甲。")
    with pytest.raises(coverage.SourceCoverageError, match="目录外锚"):
        coverage.build_arm_ledger(
            arm="control",
            case_id="CASE",
            body="甲。",
            units=units,
            catalog={},
            events=[{"event_id": "EV-01", "anchor_ids": ["E9999"]}],
        )


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("0", 1),
        (0, "1"),
        (-1, 1),
        (1, 1),
        (2, 1),
        (0, 3),
    ],
)
def test_catalog_rejects_invalid_anchor_offsets(
    tmp_path: Path,
    start: object,
    end: object,
) -> None:
    body = "甲乙"
    document = {
        "case_id": "CASE",
        "source_body_sha256": coverage.sha256_bytes(body.encode("utf-8")),
        "entry_count": 1,
        "entries": [
            {
                "anchor_id": "E0001",
                "body_start_char": start,
                "body_end_char_exclusive": end,
                "quote": "甲",
            }
        ],
    }
    (tmp_path / "CASE.json").write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(coverage.SourceCoverageError, match="锚偏移非法"):
        coverage.load_catalog(
            "CASE",
            catalog_dir=tmp_path,
            expected_body_sha256=document["source_body_sha256"],
            body=body,
        )


def test_catalog_rejects_case_and_body_identity_drift(tmp_path: Path) -> None:
    body = "甲乙"
    document = {
        "case_id": "OTHER",
        "source_body_sha256": "0" * 64,
        "entry_count": 1,
        "entries": [
            {
                "anchor_id": "E0001",
                "body_start_char": 0,
                "body_end_char_exclusive": 1,
                "quote": "甲",
            }
        ],
    }
    (tmp_path / "CASE.json").write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(coverage.SourceCoverageError, match="case 身份漂移"):
        coverage.load_catalog(
            "CASE",
            catalog_dir=tmp_path,
            expected_body_sha256=coverage.sha256_bytes(body.encode("utf-8")),
            body=body,
        )
    document["case_id"] = "CASE"
    (tmp_path / "CASE.json").write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(coverage.SourceCoverageError, match="正文 SHA 漂移"):
        coverage.load_catalog(
            "CASE",
            catalog_dir=tmp_path,
            expected_body_sha256=coverage.sha256_bytes(body.encode("utf-8")),
            body=body,
        )


def test_duplicate_source_case_is_rejected(tmp_path: Path) -> None:
    manifest = json.loads(coverage.SOURCE_MANIFEST.read_text(encoding="utf-8"))
    manifest["chapters"][1] = dict(manifest["chapters"][0])
    path = tmp_path / "source_manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(coverage.SourceCoverageError, match="重复 case"):
        coverage.load_frozen_sources(path)


def test_random_floor_rejects_nonpositive_trials() -> None:
    with pytest.raises(coverage.SourceCoverageError, match="正整数"):
        coverage.random_anchor_floor(
            body="甲。",
            units=coverage.segment_source_body("CASE", "甲。"),
            catalog={
                "E0001": {
                    "body_start_char": 0,
                    "body_end_char_exclusive": 1,
                }
            },
            sample_size=1,
            arm="control",
            case_id="CASE",
            trials=0,
        )


def test_actual_ledger_uses_same_units_and_expected_frozen_event_totals(
    actual_artifacts: dict[str, bytes],
) -> None:
    receipt = json.loads(actual_artifacts["source_receipt.json"])
    report = json.loads(actual_artifacts["source_coverage_report.json"])
    assert receipt["source_unit_total"] == 322
    assert receipt["arm_event_totals"] == {
        "control": 129,
        "treatment": 37,
    }
    assert receipt["same_source_units_verified"] is True
    assert report["same_source_units_verified"] is True
    assert report["main_denominator"] == "SCORE_PLUS_REVIEW"
    assert report["arms"]["treatment"]["overall"]["state_counts"]["SCORE"] == 55
    assert report["arms"]["control"]["overall"]["state_counts"]["SCORE"] == 153
    assert receipt["formal_gold_read"] is False
    assert receipt["model_api_calls"] == 0
    assert receipt["network_requests"] == 0
    assert (
        receipt["interpreter_independent_floor_algorithm"]
        == coverage.RANDOM_FLOOR_ALGORITHM
    )
    for arm in coverage.ARM_ORDER:
        for binding in receipt["arm_source_bindings"][arm].values():
            assert binding["seal_schema_version"]
            for name in (
                "request_sha256",
                "request_body_sha256",
                "response_sha256",
                "raw_response_sha256",
                "seal_sha256",
                "candidate_sha256",
                "mechanical_sha256",
            ):
                assert len(binding[name]) == 64


def test_unknown_units_remain_review_and_five_states_are_explicit(
    actual_artifacts: dict[str, bytes],
) -> None:
    ledger = json.loads(actual_artifacts["source_unit_ledger.json"])
    contract = ledger["state_contract"]
    assert contract["states"] == list(coverage.STATE_ORDER)
    assert contract["unknown_defaults_to_review"] is True
    for arm in coverage.ARM_ORDER:
        for case in ledger["arms"][arm].values():
            states = {unit["state"] for unit in case["units"]}
            assert states <= set(coverage.STATE_ORDER)
            assert "REVIEW" in states
            assert all(
                unit["state"] != "SCORE" or unit["covered_by"] for unit in case["units"]
            )


def test_n11_floors_are_fixed_seed_and_diagnostic_only(
    actual_artifacts: dict[str, bytes],
) -> None:
    floors = json.loads(actual_artifacts["n11_source_coverage_floors.json"])
    assert floors["empty_extraction_floor"]["source_coverage_rate"] == 0.0
    assert floors["trial_count"] == 100
    assert floors["seed_text"] == coverage.RANDOM_FLOOR_SEED
    assert floors["selection_algorithm"] == coverage.RANDOM_FLOOR_ALGORITHM
    assert floors["diagnostic_only"] is True
    assert floors["does_not_replace_n11_atom_alignment_floor"] is True
    for arm in coverage.ARM_ORDER:
        for case in floors["random_anchor_floor"]["arms"][arm].values():
            assert case["trial_count"] == 100
            assert 0 <= case["min"] <= case["mean"] <= case["max"] <= 1


def test_outputs_emit_no_source_text_gold_text_or_absolute_paths(
    actual_artifacts: dict[str, bytes],
) -> None:
    combined = b"\n".join(actual_artifacts.values())
    assert b"/Users/a1234/" not in combined
    assert b'"quote"' not in combined
    assert b'"formal_gold_read": false' in combined
    assert b'"text_not_emitted": true' in combined


def test_double_build_and_write_are_byte_identical(
    actual_artifacts: dict[str, bytes],
    tmp_path: Path,
) -> None:
    assert actual_artifacts == coverage.build_artifacts()
    output = tmp_path / "C11_3"
    first = coverage.write_or_verify(output)
    before = {path.name: path.read_bytes() for path in sorted(output.glob("*.json"))}
    second = coverage.write_or_verify(output)
    after = {path.name: path.read_bytes() for path in sorted(output.glob("*.json"))}
    assert first == second
    assert before == after


def test_candidate_tamper_cannot_reuse_old_mechanical_pass(
    tmp_path: Path,
) -> None:
    case_id = "B02-U0039"
    run_root = tmp_path / "tampered_run"
    sample_source = coverage.TREATMENT_RUN / "samples" / "main" / case_id
    prepared_source = coverage.TREATMENT_RUN / "prepared" / "main" / case_id
    shutil.copytree(
        sample_source,
        run_root / "samples" / "main" / case_id,
    )
    shutil.copytree(
        prepared_source,
        run_root / "prepared" / "main" / case_id,
    )
    prepared_catalog = (
        coverage.TREATMENT_RUN / "prepared" / "catalogs" / f"{case_id}.json"
    )
    copied_catalog = run_root / "prepared" / "catalogs" / f"{case_id}.json"
    copied_catalog.parent.mkdir(parents=True)
    shutil.copyfile(prepared_catalog, copied_catalog)
    candidate_path = coverage._candidate_path(run_root, case_id)
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["events"][0]["event_id"] = "EV-TAMPERED"
    candidate_path.write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _, sources = coverage.load_frozen_sources()
    catalog_document = json.loads(
        (coverage.CATALOG_DIR / f"{case_id}.json").read_text(encoding="utf-8")
    )
    with pytest.raises(
        coverage.SourceCoverageError,
        match="候选不能从封签响应重建",
    ):
        coverage.load_arm_events(
            "treatment",
            case_id,
            treatment_run=run_root,
            expected_body_sha256=sources[case_id]["body_sha256"],
            expected_catalog_sha256=coverage.canonical_sha(catalog_document),
        )


def test_warehouse_artifacts_match_full_disk_rebuild_and_reject_extras(
    actual_artifacts: dict[str, bytes],
    tmp_path: Path,
) -> None:
    coverage.verify_output_dir(
        coverage.DEFAULT_OUTPUT,
        expected_artifacts=actual_artifacts,
    )
    output = tmp_path / "artifacts"
    coverage.write_or_verify(output)
    (output / "UNREGISTERED.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(coverage.SourceCoverageError, match="文件集合漂移"):
        coverage.verify_output_dir(
            output,
            expected_artifacts=actual_artifacts,
        )


def test_default_and_official_python_build_identical(tmp_path: Path) -> None:
    script = Path(coverage.__file__).resolve()
    interpreters = [
        Path(sys.executable),
        Path("/opt/homebrew/opt/python@3.12/bin/python3.12"),
    ]
    if not all(path.is_file() for path in interpreters):
        pytest.skip("默认或官方 Python 3.12 不可用")
    outputs: list[dict[str, bytes]] = []
    for index, interpreter in enumerate(interpreters):
        output = tmp_path / f"python-{index}"
        subprocess.run(
            [
                str(interpreter),
                str(script),
                "--output-dir",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(
            {path.name: path.read_bytes() for path in sorted(output.iterdir())}
        )
    assert outputs[0] == outputs[1]

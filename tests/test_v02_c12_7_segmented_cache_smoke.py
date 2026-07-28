from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

import pytest


pytestmark = pytest.mark.v02

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "V02_C12_7_segmented_cache_and_smoke_20260725"
    / "program"
    / "v02_c12_7_segmented_cache_smoke.py"
)
SPEC = importlib.util.spec_from_file_location("v02_c12_7_cache_smoke", PROGRAM)
assert SPEC is not None and SPEC.loader is not None
sys.dont_write_bytecode = True
c127 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = c127
SPEC.loader.exec_module(c127)


def _copy_c11_bundle(target: Path) -> Path:
    shutil.copytree(c127.C11_ARTIFACTS, target)
    return target


def test_frozen_smoke_set_is_exactly_eight_cases_in_four_pairs() -> None:
    smoke = c127.load_and_verify_smoke_set()
    receipt = c127.run_smoke_set()

    assert c127.sha256_file(c127.SMOKE_SET_PATH) == c127.FROZEN_SMOKE_SET_SHA256
    assert Counter(row["category"] for row in smoke["cases"]) == Counter(
        {
            "path_resolution_error": 2,
            "snapshot_count_drift": 2,
            "producer_five_layer_full_score": 2,
            "sop_ucr_divergence": 2,
        }
    )
    assert receipt["status"] == "PASS_8_OF_8_FROZEN_SMOKE"
    assert receipt["passed_total"] == receipt["case_total"] == 8
    assert receipt["quality_truth"] is False


def test_smoke_set_cannot_be_silently_replaced(tmp_path: Path) -> None:
    changed = json.loads(c127.SMOKE_SET_PATH.read_text(encoding="utf-8"))
    changed["cases"][0]["replay_text"] += "drift"
    path = tmp_path / "smoke_set_v1.json"
    path.write_bytes(c127.canonical_json_bytes(changed))

    with pytest.raises(c127.C127Error, match="SHA 漂移"):
        c127.load_and_verify_smoke_set(path)


def test_cold_warm_and_one_field_change_execute_exact_stages(
    tmp_path: Path,
) -> None:
    receipt = c127.run_cache_demo(tmp_path / "cache")

    assert receipt["cold_run"]["executed_stages"] == list(c127.STAGE_ORDER)
    assert receipt["warm_run"]["cache_hit_stages"] == list(c127.STAGE_ORDER)
    assert receipt["single_field_change_run"]["cache_hit_stages"] == [
        "extract",
        "normalize",
        "crosswalk",
    ]
    assert receipt["single_field_change_run"]["executed_stages"] == [
        "score",
        "report",
    ]
    assert receipt["runtime_connected"] is False


@pytest.mark.parametrize(
    ("stage", "field", "value", "expected_hits"),
    [
        ("extract", "projection_revision", 2, []),
        ("normalize", "normalization_revision", 2, ["extract"]),
        (
            "crosswalk",
            "policy_revision",
            2,
            ["extract", "normalize"],
        ),
        (
            "score",
            "display_precision",
            5,
            ["extract", "normalize", "crosswalk"],
        ),
        (
            "report",
            "include_quality_boundary",
            False,
            ["extract", "normalize", "crosswalk", "score"],
        ),
    ],
)
def test_each_stage_change_reruns_itself_and_all_downstream(
    tmp_path: Path,
    stage: str,
    field: str,
    value: object,
    expected_hits: list[str],
) -> None:
    cache = tmp_path / stage
    baseline = c127.run_pipeline(cache)
    configs = c127.default_stage_configs()
    configs[stage][field] = value
    changed = c127.run_pipeline(cache, stage_configs=configs)

    assert baseline["executed_stages"] == list(c127.STAGE_ORDER)
    assert changed["cache_hit_stages"] == expected_hits
    assert changed["executed_stages"] == list(c127.STAGE_ORDER[len(expected_hits) :])


def test_cache_identity_uses_role_bound_bytes_not_path_name_or_mtime(
    tmp_path: Path,
) -> None:
    copied = _copy_c11_bundle(tmp_path / "renamed" / "anything")
    for index, path in enumerate(sorted(copied.iterdir()), 1):
        os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index))

    left = c127.run_pipeline(tmp_path / "cache-a")
    right = c127.run_pipeline(tmp_path / "cache-b", source_dir=copied)

    assert [row["stage_key"] for row in left["stages"]] == [
        row["stage_key"] for row in right["stages"]
    ]
    key_a, _ = c127.build_stage_key(
        stage="extract",
        config=c127.default_stage_configs()["extract"],
        inputs={"ledger": b"same bytes"},
        upstream_stage_keys=[],
    )
    key_b, _ = c127.build_stage_key(
        stage="extract",
        config=c127.default_stage_configs()["extract"],
        inputs={"ledger": b"different bytes"},
        upstream_stage_keys=[],
    )
    assert key_a != key_b


def test_locked_python_runtime_is_explicit_and_wrong_runtime_is_rejected() -> None:
    c127.validate_runtime(
        implementation="cpython",
        version=(3, 12, 12),
    )
    with pytest.raises(c127.C127Error, match="运行环境不符合仓库锁"):
        c127.validate_runtime(
            implementation="cpython",
            version=(3, 13, 0),
        )


@pytest.mark.parametrize("field", sorted(c127.FORBIDDEN_KEY_FIELDS))
def test_path_filename_and_time_metadata_are_rejected(field: str) -> None:
    with pytest.raises(c127.C127Error, match="路径／文件名／时间"):
        c127.build_stage_key(
            stage="extract",
            config=c127.default_stage_configs()["extract"],
            inputs={"ledger": b"bytes"},
            upstream_stage_keys=[],
            identity_metadata={field: "ignored-is-not-allowed"},
        )


def test_path_or_time_hidden_under_an_unlisted_metadata_name_is_rejected() -> None:
    with pytest.raises(c127.C127Error, match="不接收外部元数据"):
        c127.build_stage_key(
            stage="extract",
            config=c127.default_stage_configs()["extract"],
            inputs={"ledger": b"bytes"},
            upstream_stage_keys=[],
            identity_metadata={"harmless_looking": "/tmp/run-A/2026-07-25"},
        )


def test_path_or_time_cannot_hide_inside_a_valid_config_field() -> None:
    configs = c127.default_stage_configs()
    configs["extract"]["projection_contract"] = "/tmp/run-A/2026-07-25"

    with pytest.raises(c127.C127Error, match="冻结合同枚举值"):
        c127.validate_stage_configs(configs)


@pytest.mark.parametrize("target", ["artifact", "manifest"])
def test_cache_tampering_is_rejected(tmp_path: Path, target: str) -> None:
    cache = tmp_path / target
    run = c127.run_pipeline(cache)
    first = run["stages"][0]
    artifact, manifest = c127._cache_entry_paths(
        cache,
        first["stage"],
        first["stage_key"],
    )
    path = artifact if target == "artifact" else manifest
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(c127.C127Error, match="manifest 或 payload 漂移"):
        c127.run_pipeline(cache)


def test_synchronized_artifact_and_manifest_tamper_is_rejected(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "cache"
    run = c127.run_pipeline(cache)
    report = run["stages"][-1]
    artifact_path, manifest_path = c127._cache_entry_paths(
        cache,
        report["stage"],
        report["stage_key"],
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["comparison"]["control"]["score"] = 999
    artifact_raw = c127.canonical_json_bytes(artifact)
    artifact_path.write_bytes(artifact_raw)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"] = c127.sha256_bytes(artifact_raw)
    manifest_path.write_bytes(c127.canonical_json_bytes(manifest))

    with pytest.raises(c127.C127Error, match="独立内容索引"):
        c127.run_pipeline(cache)


def test_copy_of_c11_bundle_cannot_replace_frozen_content(
    tmp_path: Path,
) -> None:
    copied = _copy_c11_bundle(tmp_path / "copied")
    ledger_path = copied / "source_unit_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    first_case = next(iter(ledger["arms"]["control"].values()))
    first_case["event_total"] += 1
    raw = c127.canonical_json_bytes(ledger)
    ledger_path.write_bytes(raw)
    manifest_path = copied / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = next(
        row
        for row in manifest["files"]
        if row["path"] == "source_unit_ledger.json"
    )
    row["sha256"] = c127.sha256_bytes(raw)
    row["byte_count"] = len(raw)
    manifest_path.write_bytes(c127.canonical_json_bytes(manifest))

    with pytest.raises(c127.C127Error, match="manifest SHA 漂移"):
        c127.run_pipeline(tmp_path / "cache", source_dir=copied)


def test_actual_dispatch_callable_is_bound_to_stage_key(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "cache"
    baseline = c127.run_pipeline(cache)
    original = c127.STAGE_FUNCTIONS["score"]

    def changed_score(source_files, upstream, config):
        result = original(source_files, upstream, config)
        result["probe"] = "changed-implementation"
        return result

    try:
        c127.STAGE_FUNCTIONS["score"] = changed_score
        changed = c127.run_pipeline(cache)
    finally:
        c127.STAGE_FUNCTIONS["score"] = original

    baseline_score_key = next(
        row["stage_key"]
        for row in baseline["stages"]
        if row["stage"] == "score"
    )
    changed_score_key = next(
        row["stage_key"] for row in changed["stages"] if row["stage"] == "score"
    )
    assert baseline_score_key != changed_score_key
    assert changed["cache_hit_stages"] == ["extract", "normalize", "crosswalk"]
    assert changed["executed_stages"] == ["score", "report"]


def test_captured_callable_implementation_is_bound_to_stage_key(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "cache"
    original = c127.STAGE_FUNCTIONS["score"]

    def supplier_a() -> str:
        return "supplier-a"

    def supplier_b() -> str:
        return "supplier-b"

    def make_wrapper(supplier):
        def wrapped_score(source_files, upstream, config):
            result = original(source_files, upstream, config)
            result["closure_probe"] = supplier()
            return result

        return wrapped_score

    wrapper_a = make_wrapper(supplier_a)
    wrapper_b = make_wrapper(supplier_b)
    assert wrapper_a.__code__.co_code == wrapper_b.__code__.co_code
    try:
        c127.STAGE_FUNCTIONS["score"] = wrapper_a
        run_a = c127.run_pipeline(cache)
        c127.STAGE_FUNCTIONS["score"] = wrapper_b
        run_b = c127.run_pipeline(cache)
    finally:
        c127.STAGE_FUNCTIONS["score"] = original

    score_a = next(row for row in run_a["stages"] if row["stage"] == "score")
    score_b = next(row for row in run_b["stages"] if row["stage"] == "score")
    assert score_a["stage_key"] != score_b["stage_key"]
    assert run_b["cache_hit_stages"] == ["extract", "normalize", "crosswalk"]
    assert run_b["executed_stages"] == ["score", "report"]
    artifact_path, _ = c127._cache_entry_paths(
        cache,
        "score",
        score_b["stage_key"],
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["closure_probe"] == "supplier-b"


def test_replay_matches_completed_c11_item_without_quality_claim(
    tmp_path: Path,
) -> None:
    run = c127.run_pipeline(tmp_path / "cache")
    report = run["final_report"]

    assert report["all_arms_match_c11_completed_item"] is True
    assert report["comparison"]["control"]["score"] == 153
    assert report["comparison"]["treatment"]["score"] == 55
    assert report["candidate_foundation_only"] is True
    assert report["runtime_connected"] is False
    assert report["model_api_calls"] == report["network_requests"] == 0


def test_delivery_is_rebuildable_and_timing_is_volatile(
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "artifacts"
    cache = tmp_path / "cache"
    built = c127.write_delivery(artifacts, cache)
    checked = c127.verify_delivery(artifacts, cache)
    timing = json.loads(
        (artifacts / "runtime_timing_observation.json").read_text(
            encoding="utf-8"
        )
    )

    assert built == checked
    assert built["status"] == "PASS_CANDIDATE_FOUNDATION_NOT_RUNTIME_CONNECTED"
    assert built["volatile_observation_files"] == [
        "runtime_timing_observation.json"
    ]
    assert "runtime_timing_observation.json" not in {
        row["path"] for row in built["stable_files"]
    }
    assert timing["pair_count"] == 7
    assert timing["pass_is_not_conditioned_on_wall_clock_speed"] is True


def test_delivery_check_is_read_only(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    cache = tmp_path / "cache"
    c127.write_delivery(artifacts, cache)

    def snapshot(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): c127.sha256_file(path)
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    before = {
        "artifacts": snapshot(artifacts),
        "cache": snapshot(cache),
    }
    c127.verify_delivery(artifacts, cache)
    after = {
        "artifacts": snapshot(artifacts),
        "cache": snapshot(cache),
    }
    assert after == before


def test_delivery_check_does_not_repair_a_missing_cache_key(
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "artifacts"
    cache = tmp_path / "cache"
    c127.write_delivery(artifacts, cache)
    receipt = json.loads(
        (artifacts / "cache_replay_receipt.json").read_text(encoding="utf-8")
    )
    extract_row = next(
        row
        for row in receipt["warm_run"]["stages"]
        if row["stage"] == "extract"
    )
    entry = c127._cache_entry_paths(
        cache,
        "extract",
        extract_row["stage_key"],
    )[0].parent
    shutil.rmtree(entry)
    index_before = c127._cache_index_path(cache).read_bytes()

    with pytest.raises(c127.C127Error, match="禁止验收时现场补写"):
        c127.verify_delivery(artifacts, cache)

    assert not entry.exists()
    assert c127._cache_index_path(cache).read_bytes() == index_before


def test_protected_c11_and_c13_targets_are_rejected() -> None:
    with pytest.raises(c127.C127Error, match="只读保护区"):
        c127.assert_writable_target(c127.C11_ROOT / "new-file")
    with pytest.raises(c127.C127Error, match="只读保护区"):
        c127.assert_writable_target(
            ROOT
            / "experiments"
            / "extraction_redesign_v02_overnight_20260725"
            / "V02_C13_downstream_consumer_20260725"
            / "new-file"
        )


def test_stage_config_rejects_extra_identity_field() -> None:
    configs = copy.deepcopy(c127.default_stage_configs())
    configs["extract"]["path"] = "/tmp/looks-convenient"

    with pytest.raises(c127.C127Error, match="配置字段漂移"):
        c127.validate_stage_configs(configs)

from __future__ import annotations

import json

import pytest

import z80_fact_sheet_v4_crossbook_pilot as z80
from zbatch_modules.errors import ZBatchError


def _write_valid_g1_machine_artifacts(run_dir) -> tuple[object, list[str]]:
    group_dir = run_dir / "groups/G1_X01"
    specs = z80.cases_for_group("G1_X01")
    case_keys = [row["case_key"] for row in specs]
    claim = {
        "schema_version": "z80-group-run-claim-v1",
        "status": "claimed_do_not_resume",
        "claimed_at": "test-only",
        "pid": 1,
    }
    z80.write_json(group_dir / "run_claim.json", claim)
    for spec in specs:
        case_key = spec["case_key"]
        prepared = z80.read_json(run_dir / f"prepared_requests/{case_key}.json")
        z80.write_json(
            group_dir / f"requests/neutral_extract/{z80._case_id(spec)}_request.json",
            {"body": prepared},
        )
        catalog = z80.read_json(run_dir / f"inputs/{case_key}/evidence_catalog.json")["entries"]
        model_json = {
            "schema_version": "z-event-v1",
            "chapter": spec["unit"],
            "events": [
                {
                    "event_id": f"EV-C{spec['unit']:04d}-01",
                    "event": "测试主体完成了规定动作",
                    "anchors": [{"anchor_id": catalog[0]["anchor_id"]}],
                }
            ],
        }
        materialized, audit = z80.neutral_extract.process_model_data(
            model_json, chapter=spec["unit"], catalog=catalog
        )
        z80.write_json(group_dir / f"01_extract/model_json/{case_key}.json", model_json)
        z80.write_json(group_dir / f"01_extract/events/{case_key}.json", materialized)
        z80.write_json(group_dir / f"01_extract/program_audits/{case_key}.json", audit)
        z80.append_jsonl(group_dir / "call_attempts.jsonl", {"case_key": case_key, "status": "success"})
        z80.append_jsonl(group_dir / "usage.jsonl", {"case_key": case_key, "usage": {}})
    z80.write_json(
        group_dir / "01_extract/metrics.json",
        {
            "schema_version": "z80-group-run-metrics-v1",
            "status": "completed_candidate_silver_only",
            "group": "G1_X01",
            "cases_completed": case_keys,
            "main_logical_calls": len(case_keys),
            "targeted_retry_logical_calls": 0,
            "successful_responses": len(case_keys),
            "network_attempts": len(case_keys),
            "usage_totals": {},
            "targeted_retry_ledger": [],
        },
    )
    z80.write_json(
        group_dir / "run_manifest.json",
        {
            "schema_version": "z80-group-run-manifest-v1",
            "group": "G1_X01",
            "status": "completed_candidate_silver_only",
            "completed_cases": case_keys,
            "run_claim": claim,
            "network_attempts": len(case_keys),
            "targeted_retry_count": 0,
        },
    )
    z80.verify_group(run_dir, "G1_X01", allow_test_run_dir=True)
    return group_dir, case_keys


def test_v3_and_crossbook_sources_are_pinned() -> None:
    receipt = z80.assert_v3_sources()
    assert receipt["status"] == "pass"
    assert len(receipt["sources"]) == 13


def test_v4_has_exactly_three_additive_system_rules() -> None:
    for spec in z80.CASE_SPECS:
        body, diff = z80.build_candidate_body(spec)
        assert diff["changed_paths"] == ["$.messages[0].content"]
        assert diff["system"]["line_diff"]["removed_lines"] == []
        assert diff["system"]["added_nonblank_lines"] == list(z80.V4_ADDITIONS_IN_SYSTEM_ORDER)
        assert diff["system"]["round_trip_to_v3_equal"] is True
        assert diff["user_unchanged"] is True
        assert diff["sampling_and_transport_unchanged"] is True
        system = body["messages"][0]["content"]
        assert all(system.count(rule) == 1 for rule in z80.V4_ADDITIONS_IN_SYSTEM_ORDER)


def test_v4_layer_registry_and_dedup_preserve_v3_ledgers() -> None:
    registry = z80.layer_registry()
    assert registry["status"] == "pass_three_unique_additions"
    assert len(registry["v4_rows"]) == 3
    assert len({row["addition_id"] for row in registry["v4_rows"]}) == 3
    assert len(registry["base_v3_registry"]["rows"]) == 4
    dedup = z80.updated_deduplication_receipt()
    base = z80._v3_package()["deduplication"]
    assert dedup["merged_duplicates"] == base["merged_duplicates"]
    assert dedup["v3_unique_layer_additions"] == base["v3_unique_layer_additions"]
    assert dedup["base_v3_deduplication"]["preserved_unchanged"] is True
    assert len(dedup["v4_unique_layer_additions"]) == 3


def test_crossbook_frozen_materials_are_repeatable_and_not_score_inputs() -> None:
    expected = {
        "Z74B-B01-U0033": (419, "37e7b74004c27c737f418c687ee6f3703ab7a9afd002511a6ea73d1dae3adac1"),
        "Z74B-B05-U0030": (123, "3dc1e809d601f478e13b5f1b25859a08c25c36842e6c52eaa35051b7b64096df"),
    }
    for case_key, (count, digest) in expected.items():
        spec = z80.case_spec(case_key)
        first = z80.case_material(spec)
        second = z80.case_material(spec)
        assert first == second
        assert len(first["catalog"]["entries"]) == count
        assert first["catalog"]["coverage"] == 1.0
        assert first["receipt"]["frozen_body_sha256"] == digest
        body, _ = z80.base_v3_body(spec)
        wire = json.dumps(body["messages"], ensure_ascii=False)
        assert all(marker not in wire for marker in z80.SCORE_ONLY_MARKERS_FORBIDDEN_IN_REQUEST)


def test_crossbook_same_material_v3_to_v4_changes_only_system() -> None:
    for case_key in ("Z74B-B01-U0033", "Z74B-B05-U0030"):
        spec = z80.case_spec(case_key)
        base, _ = z80.base_v3_body(spec)
        candidate, diff = z80.build_candidate_body(spec)
        assert base["messages"][1] == candidate["messages"][1]
        assert diff["base_v3_instantiation"]["mode"] == "mechanical_crossbook_instantiation_from_same_v3_template"
        assert diff["changed_paths"] == ["$.messages[0].content"]


def test_zero_call_prepare_is_repeatable(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    z80.prepare(first, allow_test_run_dir=True)
    z80.prepare(second, allow_test_run_dir=True)
    assert z80.verify_prepared(first, require_zero_call=True, allow_test_run_dir=True)["status"] == "pass"
    assert z80.verify_prepared(second, require_zero_call=True, allow_test_run_dir=True)["status"] == "pass"
    assert z80.read_json(first / "prompt_candidates/事实说明书注入包_v4.json") == z80.read_json(
        second / "prompt_candidates/事实说明书注入包_v4.json"
    )
    assert z80.call_artifacts_present(first) == []


def test_prepare_rejects_protected_tree_before_write() -> None:
    unsafe = z80.V3_RUN_DIR / "should_never_be_created_by_z80_test"
    assert not unsafe.exists()
    with pytest.raises(ZBatchError, match="写入前拒绝"):
        z80.prepare(unsafe)
    assert not unsafe.exists()


def test_production_run_dir_rejects_external_and_nested_paths(tmp_path) -> None:
    with pytest.raises(ZBatchError, match="写入前拒绝"):
        z80.assert_safe_run_dir(tmp_path / "Z80_external")
    with pytest.raises(ZBatchError, match="写入前拒绝"):
        z80.assert_safe_run_dir(z80.DEFAULT_RUN_DIR / "nested")


def test_verify_rejects_score_only_copy_drift(tmp_path) -> None:
    run_dir = tmp_path / "run"
    z80.prepare(run_dir, allow_test_run_dir=True)
    target = run_dir / "provenance/score_only/X01_第79道成绩与验收总表.json"
    target.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ZBatchError, match="结果侧评分副本"):
        z80.verify_prepared(run_dir, require_zero_call=True, allow_test_run_dir=True)


def test_group_sequence_rejects_unapproved_next_group(tmp_path) -> None:
    run_dir = tmp_path / "run"
    z80.prepare(run_dir, allow_test_run_dir=True)
    with pytest.raises(ZBatchError, match="完整放行票"):
        z80._require_previous_groups(run_dir, "G2_ZHIHU", allow_test_run_dir=True)
    decision_dir = run_dir / "group_decisions"
    decision_dir.mkdir()
    z80.write_json(decision_dir / "G1_X01.json", {"group": "G1_X01", "all_pass": True, "hard_stop": False})
    group_dir = run_dir / "groups/G1_X01"
    z80.write_json(
        group_dir / "run_manifest.json",
        {"schema_version": "z80-group-run-manifest-v1", "group": "G1_X01", "status": "completed_candidate_silver_only"},
    )
    z80.write_json(
        group_dir / "mechanical_verification.json",
        {"schema_version": "z80-group-mechanical-verification-v1", "group": "G1_X01", "status": "pass"},
    )
    z80.write_json(group_dir / "01_extract/metrics.json", {"status": "completed_candidate_silver_only"})
    with pytest.raises((ZBatchError, FileNotFoundError)):
        z80._require_previous_groups(run_dir, "G2_ZHIHU", allow_test_run_dir=True)

    group_dir, case_keys = _write_valid_g1_machine_artifacts(run_dir)
    gates = {key: True for key in z80.SEMANTIC_GATE_KEYS["G1_X01"]}
    event_output_sha256 = {
        case_key: z80.z68.sha256_file(group_dir / f"01_extract/events/{case_key}.json") for case_key in case_keys
    }
    adjudication_path = group_dir / "adjudications/semantic_adjudication.json"
    z80.write_json(
        adjudication_path,
        {
            "schema_version": "z80-group-semantic-adjudication-v1",
            "run_id": run_dir.name,
            "group": "G1_X01",
            "status": "pass",
            "reviewed_case_keys": case_keys,
            "all_output_events_reviewed": True,
            "semantic_anchor_invalid_count": 0,
            "semantic_gates": gates,
            "event_output_sha256": event_output_sha256,
        },
    )
    z80.write_json(
        decision_dir / "G1_X01.json",
        {
            "schema_version": "z80-group-semantic-decision-v1",
            "run_id": run_dir.name,
            "group": "G1_X01",
            "status": "pass_all_required_gates",
            "all_pass": True,
            "hard_stop": False,
            "reviewed_case_keys": case_keys,
            "semantic_gates": gates,
            "event_output_sha256": event_output_sha256,
            "semantic_adjudication": {
                "path": adjudication_path.relative_to(run_dir).as_posix(),
                "sha256": z80.z68.sha256_file(adjudication_path),
            },
            "source_artifacts": {
                "run_manifest_sha256": z80.z68.sha256_file(group_dir / "run_manifest.json"),
                "mechanical_verification_sha256": z80.z68.sha256_file(group_dir / "mechanical_verification.json"),
                "metrics_sha256": z80.z68.sha256_file(group_dir / "01_extract/metrics.json"),
            },
        },
    )
    z80._require_previous_groups(run_dir, "G2_ZHIHU", allow_test_run_dir=True)

    event_path = group_dir / f"01_extract/events/{case_keys[0]}.json"
    original_events = z80.read_json(event_path)
    z80.write_json(event_path, {"tampered": True})
    with pytest.raises(ZBatchError, match="机械复验失败"):
        z80._require_previous_groups(run_dir, "G2_ZHIHU", allow_test_run_dir=True)
    z80.write_json(event_path, original_events)

    z80.write_json(group_dir / "01_extract/metrics.json", {"status": "tampered"})
    with pytest.raises((ZBatchError, KeyError)):
        z80._require_previous_groups(run_dir, "G2_ZHIHU", allow_test_run_dir=True)


def test_package_round_trip_and_retry_policy() -> None:
    package = z80.build_package()
    assert json.loads(json.dumps(package, ensure_ascii=False, sort_keys=True)) == package
    assert package["v3_to_v4_diff"]["addition_count"] == 3
    assert package["v3_to_v4_diff"]["no_fourth_prompt_change"] is True
    assert package["targeted_retry_equals_v3"] is True
    assert package["targeted_retry_policy"]["semantic_failures"] == "hard_stop_no_retry"

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "experiments/Z91_crossbook_v2_20260723/z91_blind_review_v1_3.py"
)
SPEC = importlib.util.spec_from_file_location("z91_blind_review_v1_3", MODULE_PATH)
assert SPEC and SPEC.loader
z91 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z91)


@pytest.fixture(autouse=True)
def _stub_transport_raw_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        z91,
        "_run_raw_usage_audit",
        lambda run_dir: {"logical_samples": 6, "status": "unit_raw_usage_rebuilt"},
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _make_completed_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "Z91_v2_synthetic"
    rubric_sha = z91.sha256_file(z91.OVERLAY_PATH)
    contract_sha = z91.sha256_file(z91.SHORT_CONTRACT_PATH)
    chapters = {"X02-C0031": 31, "X03-C0019": 19, "X04-C0046": 46}
    samples: list[dict[str, object]] = []
    for case_index, (case_key, chapter) in enumerate(chapters.items(), start=1):
        messages_sha = f"{case_index:x}" * 64
        body_path = run_dir / f"inputs/cases/{case_key}/chapter_body.txt"
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_text(f"{case_key} 冻结正文。\n", encoding="utf-8")
        _write_json(
            run_dir / f"inputs/cases/{case_key}/evidence_catalog.json",
            {
                "schema_version": "z91-frozen-evidence-catalog-v1",
                "chapter": chapter,
                "entries": [
                    {"anchor_id": f"E{index:04d}", "chapter": chapter, "quote": f"证据{index}"}
                    for index in range(1, 7)
                ],
            },
        )
        for role, arm_id, provider, model in (
            ("flash", "flash_sensenova", "sensenova", "deepseek-v4-flash"),
            ("pro", "pro_primary_tencent", "tencent_tokenhub", "deepseek-v4-pro-202606"),
        ):
            sample_id = f"{case_key}__{arm_id}"
            sample = {
                "sample_id": sample_id,
                "logical_request_id": f"Z91V2-{sample_id}",
                "case_key": case_key,
                "chapter": chapter,
                "arm_id": arm_id,
                "provider": provider,
                "model": model,
                "messages_sha256": messages_sha,
            }
            samples.append(sample)
            sample_root = run_dir / "samples" / sample_id
            events = [
                {
                    "event_id": f"EV-C{chapter:04d}-{index:02d}",
                    "event": f"{case_key}人物{index}完成动作。",
                    "anchors": [{"anchor_id": f"E{index:04d}"}],
                }
                for index in range(1, 5)
            ]
            _write_json(
                sample_root / "candidate/neutral_events.json",
                {"schema_version": "z-event-v1", "chapter": chapter, "events": events},
            )
            ledger = {
                "schema_version": "z91-short-summary-side-ledger-v1",
                "sample_id": sample_id,
                "rubric_v1_3_sha256": rubric_sha,
                "short_summary_contract_sha256": contract_sha,
                "exception_count": 0,
                "entries": [],
            }
            ledger_path = sample_root / "candidate/z91_v2_short_summary_ledger.json"
            _write_json(ledger_path, ledger)
            mechanical = {
                "schema_version": "z91-mechanical-three-gates-v2",
                "status": "pass",
                "sample_id": sample_id,
                "event_count": 4,
                "rubric_v1_3_sha256": rubric_sha,
                "short_summary_contract_sha256": contract_sha,
                "short_summary_ledger_sha256": z91.sha256_file(ledger_path),
                "short_summary_violation_count": 0,
                "shared_six_char_gate": True,
                "z91_v2_exception_gate": True,
                "effective_gate": True,
            }
            _write_json(sample_root / "mechanical.json", mechanical)
            _write_json(
                sample_root / "completion.json",
                {
                    "schema_version": "z91-sample-completion-v2",
                    "status": "sample_completed_mechanical_pass_awaiting_blind_review",
                    "sample_id": sample_id,
                    "case_key": case_key,
                    "arm_id": arm_id,
                    "mechanical_three_gates": "pass",
                    "event_count": 4,
                    "rubric_v1_3_sha256": rubric_sha,
                    "short_summary_contract_sha256": contract_sha,
                    "short_summary_violation_count": 0,
                },
            )
    _write_json(
        run_dir / "prepared/run_plan.json",
        {"schema_version": "z91-six-sample-run-plan-v2", "sample_count": 6, "samples": samples},
    )
    runtime_relative = MODULE_PATH.relative_to(ROOT).as_posix()
    runtime_sha = z91.sha256_file(MODULE_PATH)
    runtime_copy = run_dir / "inputs/runtime_dependencies" / runtime_relative
    runtime_copy.parent.mkdir(parents=True, exist_ok=True)
    runtime_copy.write_bytes(MODULE_PATH.read_bytes())
    _write_json(
        run_dir / "prepared/preflight.json",
        {
            "runtime_dependencies": [
                {"path": runtime_relative, "sha256": runtime_sha}
            ]
        },
    )
    vector_key = f"inputs/runtime_dependencies/{runtime_relative}"
    _write_json(
        run_dir / "prepared/mechanical_verification.json",
        {
            "first_vector": {vector_key: runtime_sha},
            "second_vector": {vector_key: runtime_sha},
        },
    )
    _write_json(
        run_dir / "completion.json",
        {
            "schema_version": "z91-step2-completion-v2",
            "status": "six_samples_mechanical_pass_awaiting_blind_semantic_review",
            "logical_samples": 6,
            "mechanical_three_gates": "pass_6_of_6",
            "sample_ids": [row["sample_id"] for row in samples],
            "rubric_v1_3_sha256": rubric_sha,
            "short_summary_contract_sha256": contract_sha,
            "short_summary_violation_count": 0,
        },
    )
    _write_json(
        run_dir / "audit/completion_audit.json",
        {"logical_samples": 6, "mechanical_three_gates": "pass_6_of_6"},
    )
    _write_json(
        run_dir / "audit/v2_contract_audit.json",
        {
            "logical_samples": 6,
            "rubric_v1_3_sha256": rubric_sha,
            "short_summary_contract_sha256": contract_sha,
            "short_summary_violation_count": 0,
        },
    )
    facts = []
    for case_key in chapters:
        for index in range(1, 7):
            facts.append(
                {
                    "probe_id": f"{case_key}-P{index:02d}",
                    "canonical_fact": f"{case_key}来源事实{index}",
                    "subject": "人物",
                    "action_or_state": "完成动作",
                    "result": "",
                    "explicit_qualifiers": [],
                    "support_anchor_ids": [f"E{index:04d}"],
                }
            )
    resolved_path = run_dir / "review/source_facts/resolved.json"
    _write_json(
        resolved_path,
        {
            "schema_version": "z91-source-facts-resolved-v1",
            "status": "resolved_before_model_calls",
            "probe_count": 18,
            "items": facts,
        },
    )
    _write_json(
        run_dir / "review/source_facts/source_fact_seal.json",
        {
            "schema_version": "z91-source-fact-seal-v1",
            "dual_arm_outputs_seen_before_seal": False,
            "resolved_file": {
                "path": "resolved.json",
                "sha256": z91.sha256_file(resolved_path),
            },
        },
    )
    return run_dir


def _fill_singleton_group_votes(blind_dir: Path) -> None:
    for reviewer in ("R1", "R2"):
        path = blind_dir / f"grouping/reviewer_{reviewer}.json"
        value = z91.read_object(path)
        for case in value["cases"]:
            case["groups"] = [
                {"group_id": f"G{index:03d}", "member_keys": [member]}
                for index, member in enumerate(case["expected_member_keys"], start=1)
            ]
        _write_json(path, value)


def _fill_judgment_vote(path: Path, mapping: dict[str, dict[str, str]]) -> None:
    value = z91.read_object(path)
    for case_index, case in enumerate(value["cases"]):
        labels = mapping[case["case_key"]]
        for probe in case["probe_judgments"]:
            if case_index < 2:
                probe["arms"][labels["flash"]]["verdict"] = "miss"
                probe["arms"][labels["pro"]]["verdict"] = "hit"
            else:
                probe["arms"]["A"]["verdict"] = "hit"
                probe["arms"]["B"]["verdict"] = "hit"
        for group in case["group_judgments"]:
            for arm in z91.ANONYMOUS_ARMS:
                if not group["member_keys_by_arm"][arm]:
                    continue
                group["arms"][arm]["atomic_complete"] = True
                group["arms"][arm]["semantic_error_labels"] = []
                group["arms"][arm]["anchor_support_by_member"] = {
                    member: "complete"
                    for member in group["member_keys_by_arm"][arm]
                }
    _write_json(path, value)


def test_full_zero_api_workflow_rebuilds_unique_directional_state(tmp_path: Path) -> None:
    run_dir = _make_completed_run(tmp_path)
    blind_dir = run_dir / z91.BLIND_RELATIVE

    prepared = z91.prepare_blind(run_dir)
    assert prepared["status"] == "prepared_zero_api_awaiting_independent_grouping"
    packet = z91.read_object(blind_dir / "anonymous/packet.json")
    assert z91.anonymous_leaks(packet, z91._known_sensitive_values(z91._validate_completed_run(run_dir))) == []

    _fill_singleton_group_votes(blind_dir)
    grouped = z91.resolve_groups(run_dir)
    assert grouped["status"] == "resolved_and_sampled"
    sampled = z91.read_object(blind_dir / "grouping/sampled_groups.json")
    assert [row["actual_sampled_group_count"] for row in sampled["cases"]] == [8, 8, 8]

    templates = z91.prepare_judgments(run_dir)
    assert templates["probe_unit_count"] == 18
    assert templates["group_unit_count"] == 24
    mapping_doc = z91.read_object(blind_dir / "sealed/arm_mapping.json")
    role_labels = z91._mapping_labels(mapping_doc)
    for reviewer in ("R1", "R2"):
        _fill_judgment_vote(blind_dir / f"judgments/reviewer_{reviewer}.json", role_labels)

    r2_path = blind_dir / "judgments/reviewer_R2.json"
    r2 = z91.read_object(r2_path)
    first_case = r2["cases"][0]
    pro_label = role_labels[first_case["case_key"]]["pro"]
    first_case["probe_judgments"][0]["arms"][pro_label]["verdict"] = "partial"
    _write_json(r2_path, r2)
    pending = z91.finalize(run_dir)
    assert pending["status"] == "awaiting_R3_only_disagreements"
    judgment_r3_path = blind_dir / "judgments/reviewer_R3.json"
    judgment_r3 = z91.read_object(judgment_r3_path)
    assert len(judgment_r3["rows"]) == 1
    judgment_r3["rows"][0]["final_value"] = "hit"
    judgment_r3["rows"][0]["reason"] = "只裁这一项探针分歧"
    _write_json(judgment_r3_path, judgment_r3)
    result = z91.finalize(run_dir)
    assert result["final_state"] == "pro_directional_lead"
    assert set(result["only_allowed_final_states"]) == {
        "pro_directional_lead", "no_crossbook_pro_lead"
    }
    receipt = z91.audit(run_dir)
    assert receipt["status"] == "pass_rebuilt_from_run_and_human_originals"
    assert receipt["anonymous_leak_count"] == 0
    assert receipt["final_state"] == "pro_directional_lead"


def test_prepare_requires_effective_six_sample_v13_completion(tmp_path: Path) -> None:
    run_dir = _make_completed_run(tmp_path)
    path = next((run_dir / "samples").glob("*/mechanical.json"))
    value = z91.read_object(path)
    value["effective_gate"] = False
    _write_json(path, value)

    with pytest.raises(z91.BlindReviewError, match="机械完成身份无效"):
        z91.prepare_blind(run_dir)


def test_prepare_requires_blind_tool_sha_frozen_before_network_run(tmp_path: Path) -> None:
    run_dir = _make_completed_run(tmp_path)
    preflight_path = run_dir / "prepared/preflight.json"
    preflight = z91.read_object(preflight_path)
    preflight["runtime_dependencies"][0]["sha256"] = "0" * 64
    _write_json(preflight_path, preflight)

    with pytest.raises(z91.BlindReviewError, match="发网前被 prepared/runtime SHA 冻结"):
        z91.prepare_blind(run_dir)


def test_content_identity_is_shared_but_member_identity_keeps_position() -> None:
    content = z91.content_key("齐夏点头。", ["E0002", "E0001", "E0001"])
    assert content == z91.content_key("齐夏点头。", ["E0001", "E0002"])
    keys = {
        z91.member_key("X02-C0031", arm, "EV-C0031-01", content)
        for arm in ("A", "B")
    }
    keys.add(z91.member_key("X03-C0019", "A", "EV-C0031-01", content))
    keys.add(z91.member_key("X02-C0031", "A", "EV-C0031-02", content))
    assert len(keys) == 4


def test_group_r3_is_generated_only_for_partition_disagreement(tmp_path: Path) -> None:
    run_dir = _make_completed_run(tmp_path)
    blind_dir = run_dir / z91.BLIND_RELATIVE
    z91.prepare_blind(run_dir)
    _fill_singleton_group_votes(blind_dir)
    r2_path = blind_dir / "grouping/reviewer_R2.json"
    r2 = z91.read_object(r2_path)
    first_case = r2["cases"][0]
    first = first_case["groups"].pop(0)
    second = first_case["groups"].pop(0)
    first_case["groups"].insert(
        0,
        {"group_id": "R2-MERGED", "member_keys": first["member_keys"] + second["member_keys"]},
    )
    _write_json(r2_path, r2)

    status = z91.resolve_groups(run_dir)
    assert status["status"] == "awaiting_R3_only_disagreements"
    r3_path = blind_dir / "grouping/reviewer_R3.json"
    r3 = z91.read_object(r3_path)
    assert len(r3["rows"]) == 1
    assert len(r3["rows"][0]["member_keys"]) == 2
    r3["rows"][0]["final_groups"] = r3["rows"][0]["reviewer_R1_groups"]
    r3["rows"][0]["reason"] = "只裁这一处分组分歧"
    _write_json(r3_path, r3)
    assert z91.resolve_groups(run_dir)["status"] == "resolved_and_sampled"


def test_atomic_complete_cannot_score_with_partial_anchor_support(tmp_path: Path) -> None:
    run_dir = _make_completed_run(tmp_path)
    blind_dir = run_dir / z91.BLIND_RELATIVE
    z91.prepare_blind(run_dir)
    _fill_singleton_group_votes(blind_dir)
    z91.resolve_groups(run_dir)
    z91.prepare_judgments(run_dir)
    role_labels = z91._mapping_labels(
        z91.read_object(blind_dir / "sealed/arm_mapping.json")
    )
    for reviewer in ("R1", "R2"):
        path = blind_dir / f"judgments/reviewer_{reviewer}.json"
        _fill_judgment_vote(path, role_labels)
    r1_path = blind_dir / "judgments/reviewer_R1.json"
    r1 = z91.read_object(r1_path)
    present_arm = next(
        arm
        for arm, members in r1["cases"][0]["group_judgments"][0]["member_keys_by_arm"].items()
        if members
    )
    arm_row = r1["cases"][0]["group_judgments"][0]["arms"][present_arm]
    member = next(iter(arm_row["anchor_support_by_member"]))
    arm_row["anchor_support_by_member"][member] = "partial"
    _write_json(r1_path, r1)

    with pytest.raises(z91.BlindReviewError, match="atomic_complete=true"):
        z91.finalize(run_dir)


def test_anonymous_leak_scan_rejects_metadata_keys_and_values() -> None:
    value = {"case_key": "X02-C0031", "provider": "hidden"}
    assert z91.anonymous_leaks(value, set()) == ["$.provider:forbidden_key"]
    assert z91.anonymous_leaks({"note": "deepseek-v4-pro-202606"}, {"deepseek-v4-pro-202606"})

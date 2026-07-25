from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_anchor_first_experiment as v02  # noqa: E402


class PresenceOnlyEnvironment(Mapping[str, str]):
    """允许成员测试，但只要代码尝试取值就立即失败。"""

    def __contains__(self, key: object) -> bool:
        return key == v02.PINNED_KEY_ENV

    def __getitem__(self, key: str) -> str:
        raise AssertionError(f"不允许读取密钥值：{key}")

    def __iter__(self) -> Iterator[str]:
        return iter((v02.PINNED_KEY_ENV,))

    def __len__(self) -> int:
        return 1


def _score_document(
    *,
    anchor_partial: dict[str, int],
    calls: int = 1,
    layer_drop: tuple[str, str] | None = None,
) -> dict:
    chapters = {}
    for case in v02.CASES:
        layers = {
            layer: {
                "passed": case.denominator,
                "denominator": case.denominator,
            }
            for layer in v02.ALL_SCORE_LAYERS
        }
        if layer_drop and layer_drop[0] == case.case_id:
            layers[layer_drop[1]]["passed"] -= 1
        chapters[case.case_id] = {
            "denominator": case.denominator,
            "failure_counts": {
                "ANCHOR_PARTIAL": anchor_partial[case.case_id],
            },
            "layers": layers,
            "model_api_calls": calls,
        }
    return {
        "schema_version": v02.SCORE_SCHEMA_VERSION,
        "chapters": chapters,
    }


def _valid_response(
    *,
    case: v02.CaseSpec,
    catalog: dict,
    anchor_count: int = 1,
) -> dict:
    selected = [row["anchor_id"] for row in catalog["entries"][:anchor_count]]
    return {
        "schema_version": v02.CONTRACT_VERSION,
        "chapter": case.unit,
        "events": [
            {
                "event_id": f"EV-C{case.unit:04d}-01",
                "event": "人物明确做出一项安排",
                "minimal_anchor_ids": selected,
                "support_obligations": [
                    {
                        "claim_span": "做出一项安排",
                        "anchor_ids": selected,
                        "combination": "all_required",
                    }
                ],
            }
        ],
    }


def test_c0_checks_presence_without_reading_or_printing_secret_value() -> None:
    result = v02.c0_check(PresenceOnlyEnvironment())

    assert result["checks"]["api_key_environment_name_present"] is True
    assert result["checks"]["api_key_value_read"] is False
    assert result["checks"]["api_key_value_printed"] is False
    assert result["provider"] == "sensenova"
    assert result["model"] == "deepseek-v4-flash"
    assert result["api_key_env"] == "SENSENOVA_API_KEY"
    assert result["model_api_calls"] == 0
    assert result["network_requests"] == 0
    assert "PresenceOnlyEnvironment" not in json.dumps(result, ensure_ascii=False)


def test_c0_records_reachability_boundary_without_live_probe() -> None:
    result = v02.c0_check({})

    assert result["technical_ready_without_secret"] is True
    assert result["checks"]["transport_entry_importable"] is True
    assert result["checks"]["live_request_entry_can_observe_reachability"] is True
    assert result["checks"]["dedicated_zero_inference_reachability_probe"] is False
    assert result["live_provider_reachability"] == "unknown_zero_network_boundary"
    assert result["status"] == "hold_environment_not_loaded"


def test_three_formal_pointers_resolve_to_source_and_denominator_49() -> None:
    loaded = [v02.load_case_source(case) for case in v02.CASES]

    assert [row["case"].case_id for row in loaded] == [
        "B02-U0039",
        "B03-U0041",
        "B01-U0033",
    ]
    assert sum(row["case"].denominator for row in loaded) == 49
    assert [row["case"].denominator for row in loaded] == [8, 16, 25]
    for row in loaded:
        assert v02.sha256_file(row["cache_path"]) == row["cache_sha256"]
        assert v02.sha256_bytes(row["body"].encode("utf-8")) == row["body_sha256"]
        assert v02.sha256_file(row["formal_path"]) == row["formal_sha256"]


def test_catalog_is_deterministic_exact_and_defaults_to_k_missing() -> None:
    source = v02.load_case_source(v02.CASES[0])
    first = v02.generate_anchor_catalog(
        case_id=source["case"].case_id,
        chapter=source["case"].unit,
        text=source["body"],
    )
    second = v02.generate_anchor_catalog(
        case_id=source["case"].case_id,
        chapter=source["case"].unit,
        text=source["body"],
    )

    assert first == second
    assert first["selection_k"] == v02.K_MISSING
    assert first["generator"]["coverage"] == 1.0
    assert first["entry_count"] == len(first["entries"])
    for row in first["entries"]:
        start = row["body_start_char"]
        end = row["body_end_char_exclusive"]
        assert source["body"][start:end] == row["quote"]
        assert 10 <= row["nonspace_char_count"] <= 25


def test_k_is_configurable_but_never_truncates_the_complete_catalog() -> None:
    source = v02.load_case_source(v02.CASES[0])
    missing = v02.generate_anchor_catalog(
        case_id=source["case"].case_id,
        chapter=source["case"].unit,
        text=source["body"],
        selection_k=v02.K_MISSING,
    )
    limited = v02.generate_anchor_catalog(
        case_id=source["case"].case_id,
        chapter=source["case"].unit,
        text=source["body"],
        selection_k=2,
    )

    assert limited["selection_k"] == 2
    assert limited["entries"] == missing["entries"]
    assert limited["entry_count"] == missing["entry_count"]


def test_contract_schema_records_k_missing_without_guessing() -> None:
    schema = v02.closed_anchor_alignment_schema()

    assert schema["$id"] == "closed_anchor_alignment.v1"
    assert schema["x_selection_k"] == "K_MISSING"
    event_schema = schema["properties"]["events"]["items"]["properties"]
    assert "maxItems" not in event_schema["minimal_anchor_ids"]

    numeric = v02.closed_anchor_alignment_schema(3)
    numeric_event = numeric["properties"]["events"]["items"]["properties"]
    assert numeric_event["minimal_anchor_ids"]["maxItems"] == 3


def test_minimal_anchor_validator_passes_closed_set_and_reverse_lookup() -> None:
    source = v02.load_case_source(v02.CASES[0])
    catalog = v02.generate_anchor_catalog(
        case_id=source["case"].case_id,
        chapter=source["case"].unit,
        text=source["body"],
    )
    response = _valid_response(case=source["case"], catalog=catalog)

    result = v02.validate_closed_anchor_alignment(
        response,
        catalog=catalog,
        source_text=source["body"],
    )

    assert result["status"] == "pass"
    assert result["closed_catalog_identity_verified"] is True
    assert result["source_reverse_lookup_verified"] is True
    assert result["declared_minimal_set_verified"] is True
    assert result["semantic_support_verified"] is False
    assert result["events"][0]["removal_checks"][0]["mechanical_minimality_pass"]


def test_minimal_anchor_validator_rejects_unknown_id_and_bad_union() -> None:
    source = v02.load_case_source(v02.CASES[0])
    catalog = v02.generate_anchor_catalog(
        case_id=source["case"].case_id,
        chapter=source["case"].unit,
        text=source["body"],
    )
    response = _valid_response(case=source["case"], catalog=catalog)
    response["events"][0]["minimal_anchor_ids"] = ["E9999"]

    result = v02.validate_closed_anchor_alignment(
        response,
        catalog=catalog,
        source_text=source["body"],
    )

    assert result["status"] == "fail"
    assert any("unknown_anchor_id:E9999" in error for error in result["errors"])
    assert any(
        "support_union_not_equal_minimal_anchor_set" in error
        for error in result["errors"]
    )


def test_numeric_k_is_enforced_by_validator() -> None:
    source = v02.load_case_source(v02.CASES[0])
    catalog = v02.generate_anchor_catalog(
        case_id=source["case"].case_id,
        chapter=source["case"].unit,
        text=source["body"],
        selection_k=1,
    )
    response = _valid_response(
        case=source["case"],
        catalog=catalog,
        anchor_count=2,
    )

    result = v02.validate_closed_anchor_alignment(
        response,
        catalog=catalog,
        source_text=source["body"],
    )

    assert result["status"] == "fail"
    assert any("selection_k_exceeded" in error for error in result["errors"])


def test_gate_passes_all_frozen_criteria_but_never_issues_green_ticket() -> None:
    control = _score_document(
        anchor_partial={
            "B02-U0039": 4,
            "B03-U0041": 6,
            "B01-U0033": 10,
        }
    )
    treatment = _score_document(
        anchor_partial={
            "B02-U0039": 2,
            "B03-U0041": 3,
            "B01-U0033": 5,
        }
    )

    result = v02.evaluate_gate(control, treatment)

    assert result["status"] == "pass_experiment_gate"
    assert result["experiment_gate_pass"] is True
    assert result["anchor_partial"]["relative_reduction"] == 0.5
    assert result["anchor_partial"]["declining_chapter_count"] == 3
    assert result["calls"]["additional"] == 0
    assert result["offline_denominator"] == 49
    assert result["judge_green_ticket_eligible"] is False
    assert result["judge_green_ticket_issued"] is False


def test_gate_reports_absolute_counts_when_control_failures_below_10() -> None:
    control = _score_document(
        anchor_partial={
            "B02-U0039": 2,
            "B03-U0041": 3,
            "B01-U0033": 4,
        }
    )
    treatment = _score_document(
        anchor_partial={
            "B02-U0039": 1,
            "B03-U0041": 1,
            "B01-U0033": 2,
        }
    )

    result = v02.evaluate_gate(control, treatment)

    assert result["status"] == "pass_experiment_gate"
    assert (
        result["anchor_partial"]["reporting_mode"] == "absolute_counts_control_below_10"
    )
    assert result["anchor_partial"]["control"] == 9
    assert result["anchor_partial"]["treatment"] == 4
    assert result["anchor_partial"]["absolute_reduction"] == 5


def test_gate_rejects_layer_regression_and_extra_calls() -> None:
    control = _score_document(
        anchor_partial={
            "B02-U0039": 4,
            "B03-U0041": 6,
            "B01-U0033": 10,
        },
        calls=1,
    )
    treatment = _score_document(
        anchor_partial={
            "B02-U0039": 2,
            "B03-U0041": 3,
            "B01-U0033": 5,
        },
        calls=2,
        layer_drop=("B02-U0039", "UCR"),
    )

    result = v02.evaluate_gate(control, treatment)

    assert result["status"] == "fail_experiment_gate"
    assert result["checks"]["fcr_qcr_asr_ucr_no_regression"] is False
    assert result["checks"]["zero_additional_model_calls"] is False
    assert result["judge_green_ticket_issued"] is False


def test_prepared_requests_are_sensenova_flash_and_contract_only_delta() -> None:
    source = v02.load_case_source(v02.CASES[0])
    catalog = v02.generate_anchor_catalog(
        case_id=source["case"].case_id,
        chapter=source["case"].unit,
        text=source["body"],
    )

    control, treatment, diff = v02.build_request_pair(
        source=source,
        catalog=catalog,
        selection_k=v02.K_MISSING,
    )

    assert control["provider"] == treatment["provider"] == "sensenova"
    assert control["model"] == treatment["model"] == "deepseek-v4-flash"
    assert control["body"]["model"] == treatment["body"]["model"]
    assert diff["only_delta"] == "closed_anchor_alignment_contract"
    assert diff["control_equals_treatment_after_suffix_removal"] is True
    assert diff["sampling_equal"] is True
    assert diff["planned_calls"]["additional"] == 0


def test_c3_changes_only_model_visible_claim_span_instruction() -> None:
    c1 = v02.build_artifacts(
        environ={},
        prompt_variant=v02.PROMPT_VARIANT_C1,
    )
    c3 = v02.build_artifacts(
        environ={},
        prompt_variant=v02.PROMPT_VARIANT_C3,
    )

    assert (
        c1["contracts/closed_anchor_alignment.v1.schema.json"]
        == c3["contracts/closed_anchor_alignment.v1.schema.json"]
    )
    for case in v02.CASES:
        control_path = f"requests/control/{case.case_id}.json"
        treatment_path = f"requests/anchor_first/{case.case_id}.json"
        assert c1[control_path] == c3[control_path]
        assert c1[treatment_path] != c3[treatment_path]

        c1_request = json.loads(c1[treatment_path])
        c3_request = json.loads(c3[treatment_path])
        assert {
            key: value for key, value in c1_request.items() if key != "body"
        } == {
            key: value for key, value in c3_request.items() if key != "body"
        }
        assert {
            key: value
            for key, value in c1_request["body"].items()
            if key != "messages"
        } == {
            key: value
            for key, value in c3_request["body"].items()
            if key != "messages"
        }
        assert (
            c1_request["body"]["messages"][:-1]
            == c3_request["body"]["messages"][:-1]
        )
        c3_prompt = c3_request["body"]["messages"][-1]["content"]
        assert "【产出硬规则】" in c3_prompt
        assert "正例（只教字段关系" in c3_prompt
        assert "反例（禁止）" in c3_prompt
        assert "claim_span 都必须是同一条 event 的逐字连续子串" in c3_prompt

    receipt = json.loads(c3["c3_prompt_delta_receipt.json"])
    assert receipt["status"] == "pass_prompt_only_change"
    assert receipt["output_structure_changed"] is False
    assert receipt["mechanical_claim_span_gate_changed"] is False
    assert len(receipt["rows"]) == 3


def test_existing_c1_supply_still_rebuilds_byte_for_byte() -> None:
    artifacts = v02.build_artifacts(
        environ={},
        prompt_variant=v02.PROMPT_VARIANT_C1,
    )
    result = v02.verify_artifacts(v02.DEFAULT_OUTPUT_DIR, artifacts)

    assert result["status"] == "pass"
    assert result["missing"] == []
    assert result["changed"] == []


def test_artifact_build_has_zero_gold_leak_and_zero_calls(monkeypatch) -> None:
    called = False

    def forbidden_call(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal called
        called = True
        raise AssertionError("C0/C1 不得进入运输 call")

    monkeypatch.setattr(v02.api_transport.ApiTransport, "call", forbidden_call)
    artifacts = v02.build_artifacts(environ={})
    leakage = json.loads(artifacts["leakage_scan.json"])
    c1 = json.loads(artifacts["c1_preflight.json"])

    assert called is False
    assert leakage["status"] == "pass_zero_gold_or_answer_leak"
    assert leakage["request_count"] == 6
    assert leakage["formal_gold_identity_hits"] == 0
    assert leakage["formal_gold_answer_hits"] == 0
    assert leakage["forbidden_request_key_hits"] == 0
    assert c1["status"] == "pass_zero_call_prepared"
    assert c1["selection_k"] == "K_MISSING"
    assert c1["selection_k_missing_blocks_preparation"] is False
    assert c1["c2_known_local_hold_only_environment_variable"] is True
    assert c1["judge_green_ticket_issued"] is False
    assert c1["model_api_calls"] == 0
    assert c1["network_requests"] == 0


def test_artifact_write_is_idempotent_and_double_run_is_identical(
    tmp_path: Path,
) -> None:
    first = v02.build_artifacts(environ={})
    second = v02.build_artifacts(environ={})

    assert first == second
    v02.write_artifacts(tmp_path, first)
    v02.write_artifacts(tmp_path, second)
    verification = v02.verify_artifacts(tmp_path, second)

    assert verification["status"] == "pass"
    assert verification["missing"] == []
    assert verification["changed"] == []
    assert (
        (tmp_path / "README.md").read_text(encoding="utf-8").endswith("来源：Codex\n")
    )


def test_source_manifest_keeps_gold_offline_and_denominator_49() -> None:
    artifacts = v02.build_artifacts(environ={})
    manifest = json.loads(artifacts["source_manifest.json"])

    assert manifest["offline_denominator"] == 49
    assert manifest["formal_gold_usage"] == ("offline_scoring_only_never_model_visible")
    assert [row["formal_denominator"] for row in manifest["chapters"]] == [
        8,
        16,
        25,
    ]
    assert all(
        row["gold_pointer"]["model_visible"] is False
        and row["formal_gold"]["model_visible"] is False
        for row in manifest["chapters"]
    )

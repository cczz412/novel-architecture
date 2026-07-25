from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.Z98_independent_verifier_freeze_20260724 import pipeline
from experiments.Z98_independent_verifier_freeze_20260724.core import (
    MODEL_ID,
    TOTAL_COST_CAP_MICRO_CNY,
    TOTAL_TOKEN_CAP,
    Z98VerifierContractError,
    conservative_cost_cap_micro_cny,
    enforce_cost_gate_before_send,
    enforce_token_gate_before_send,
    make_synthetic_repair_transport_tickets,
    parse_verifier_content,
    render_dynamic_verifier_request,
    scan_model_visible_leaks,
    sha256_bytes,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repair_payload(path: Path) -> dict[str, object]:
    request = _load(path)
    return json.loads(request["model_visible"]["messages"][1]["content"])


def _patch(source: dict[str, object]) -> dict[str, object]:
    return {
        "op": "KEEP",
        "target_event_ids": [source["source_event_id"]],
        "source_span_ids": [source["source_span_ids"][0]],
        "actor": "候选主体",
        "predicate": "执行",
        "object_or_result": "候选事实",
        "hard_qualifiers": [],
        "fact_class": "event",
        "speaker": None,
        "anchor_candidates": [source["source_span_ids"][0]],
    }


def _valid_p2_response(request_path: Path) -> bytes:
    request = _load(request_path)
    payload = _repair_payload(request_path)
    if request["contract_mode"] == "single_patch":
        return json.dumps(
            _patch(payload["input"]),
            ensure_ascii=False,
        ).encode("utf-8")
    slots = payload["slots"]
    value = {
        "schema": "atom-batch-v2",
        "request_id": request["request_id"],
        "items": [
            {
                "slot_id": slot["slot_id"],
                "status": "ok",
                "atom": _patch(slot),
                "split_span_ids": [],
                "missing_context_codes": [],
            }
            for slot in slots
        ],
        "receipt": {
            "returned_slot_ids": [slot["slot_id"] for slot in slots],
        },
    }
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _valid_verdict(case_id: str, item_ids: list[str]) -> str:
    return json.dumps(
        {
            "schema": "z98-independent-verdict-v1",
            "case_id": case_id,
            "items": [
                {
                    "item_id": item_id,
                    "verdict": "PASS",
                    "fact_support": "SUPPORTED",
                    "qualifier_support": "NOT_APPLICABLE",
                    "anchor_support": "FULL",
                    "atomicity": "ATOMIC",
                    "reason_codes": ["NONE"],
                }
                for item_id in item_ids
            ],
            "receipt": {"returned_item_ids": item_ids},
        },
        ensure_ascii=False,
    )


def _runtime_binding(
    bundle: Path,
    mapping: dict[str, object],
    *,
    tested_lane: str = "flash",
    p2_response_bytes: bytes,
) -> dict[str, object]:
    graph = _load(bundle / "execution/sequence_68.json")
    judge_node = next(
        node
        for node in graph["nodes"]
        if node["node_kind"] == "independent_judge"
        and node["verifier_template_path"]
        == mapping["verifier_template_path"]
        and node["tested_lane_private"] == tested_lane
    )
    by_id = {node["node_id"]: node for node in graph["nodes"]}
    repair_node = by_id[judge_node["depends_on"][0]]
    runtime_root = f"runtime/{repair_node['node_id']}"
    response_path = f"{runtime_root}/raw_response.json"
    call_attempt_bytes, usage_bytes = make_synthetic_repair_transport_tickets(
        repair_node=repair_node,
        p2_response_path=response_path,
        p2_response_bytes=p2_response_bytes,
    )
    return {
        "p2_response_path": response_path,
        "repair_node": repair_node,
        "judge_node": judge_node,
        "call_attempt_path": f"{runtime_root}/call_attempt.json",
        "call_attempt_bytes": call_attempt_bytes,
        "usage_path": f"{runtime_root}/usage.json",
        "usage_bytes": usage_bytes,
        "actual_accumulated_tokens": 0,
        "actual_accumulated_micro_cny": 0,
    }


def test_build_bundle_is_byte_deterministic_and_zero_call(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left_result = pipeline.build_bundle(left, repo_root=REPO_ROOT)
    right_result = pipeline.build_bundle(right, repo_root=REPO_ROOT)
    assert left_result["manifest_sha256"] == right_result["manifest_sha256"]
    assert left_result["template_count"] == 17
    assert left_result["execution_nodes"] == 68
    assert left_result["model_api_calls"] == 0
    assert left_result["network_attempts"] == 0
    assert left_result["step2_release_allowed"] is False
    left_files = {
        path.relative_to(left): path.read_bytes()
        for path in left.rglob("*")
        if path.is_file()
    }
    right_files = {
        path.relative_to(right): path.read_bytes()
        for path in right.rglob("*")
        if path.is_file()
    }
    assert left_files == right_files
    preflight = _load(left / "preflight.json")
    assert preflight["provider_catalog_requests"] == 0
    assert preflight["usage_tokens"] == 0
    assert preflight["secret_values_read_or_logged"] is False
    assert preflight["live_exact_model_catalog_check"] == (
        "PENDING_BEFORE_NETWORK_RELEASE"
    )
    parser_receipt = _load(
        left / "receipts/strict_parser_reject_preflight.json"
    )
    assert parser_receipt["status"] == "PASS"
    assert len(parser_receipt["cases"]) == 7
    assert all(row["pass"] for row in parser_receipt["cases"])
    assert parser_receipt["model_api_calls"] == 0
    assert parser_receipt["network_attempts"] == 0
    budget_canary = _load(
        left / "receipts/dynamic_budget_gate_canary.json"
    )
    assert budget_canary["status"] == "PASS"
    assert budget_canary["path_exercised"] == (
        "render_dynamic_verifier_request after actual P2 insertion"
    )
    assert all(row["pass"] for row in budget_canary["cases"])
    assert budget_canary["model_api_calls"] == 0
    assert budget_canary["network_attempts"] == 0


def test_bundle_keeps_17_repair_requests_and_two_contracts_unchanged(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    receipt = _load(bundle / "receipts/repair_source_immutability.json")
    assert receipt["status"] == "PASS_UNCHANGED"
    assert receipt["request_count"] == 17
    assert receipt["before"] == receipt["after"]
    replay = receipt["authority_listing_replay"]
    assert replay["recomputed_aggregate_listing_sha256"] == (
        "d10179c500d98e79adb90c98fe4b7c571c18c191ab4da322cf610d04db90bb70"
    )
    assert replay["authority_aggregate_listing_sha256"] == (
        replay["recomputed_aggregate_listing_sha256"]
    )
    assert replay["matches_authority"] is True
    assert replay["listing_line_count"] == 17
    assert replay["listing_byte_count"] == 2880
    paths = [row["path"] for row in replay["listing_rows"]]
    assert paths == sorted(paths)
    for row in replay["listing_rows"]:
        assert row["listing_line"] == (
            f"{row['sha256']}  {row['path']}\n"
        )
    assert {
        Path(row["path"]).name for row in receipt["contracts_unchanged"]
    } == {
        "knife_a_patch_v1.schema.json",
        "atom_batch_v2.schema.json",
    }


def test_templates_are_blind_and_budget_maps_all_17_requests(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")
    assert mapping["mapping_count"] == 17
    assert len(mapping["mappings"]) == 17
    assert sum(
        row["verification_token_cap"] for row in mapping["mappings"]
    ) == 16656
    assert len(
        {row["repair_request_path"] for row in mapping["mappings"]}
    ) == 17
    for row in mapping["mappings"]:
        template = _load(bundle / row["verifier_template_path"])
        assert sha256_bytes(
            (bundle / row["verifier_template_path"]).read_bytes()
        ) == row["verifier_template_sha256"]
        assert scan_model_visible_leaks(template["model_visible"]) == []
        visible = json.dumps(
            template["model_visible"],
            ensure_ascii=False,
        ).casefold()
        for marker in (
            "sensenova",
            "tencent_tokenhub",
            "deepseek-v4",
            "single_patch",
            "atom_batch_v2",
            "金标",
            "人工判词",
            "历史成绩",
            "修复日志",
        ):
            assert marker.casefold() not in visible

    budget = _load(bundle / "receipts/verifier_budget_receipt.json")
    assert budget["judge_calls"] == 34
    assert budget["legacy_judge_total_token_cap"] == 33312
    assert budget["judge_round_token_cap"] == 500_000
    assert (
        budget["static_before_candidate_round_token_projection"] < 500_000
    )
    assert budget["judge_total_cost_cap_cny"] == 10
    assert budget["judge_total_cost_cap_micro_cny"] == 10_000_000
    assert budget["price_snapshot"] == {
        "currency": "CNY",
        "unit": "per_million_tokens",
        "input_price": 12,
        "output_price": 36,
        "conservative_rule": "每次裁判的全部 token 帽都按输出价 36 计算最坏金额",
    }
    assert len(budget["calls"]) == 34
    assert (
        budget["static_before_candidate_round_cost_projection_micro_cny"]
        < 10_000_000
    )
    assert sum(
        row["static_before_candidate_cost_projection_micro_cny"]
        for row in budget["calls"]
    ) == budget["static_before_candidate_round_cost_projection_micro_cny"]
    for row in budget["calls"]:
        assert row["static_before_candidate_cost_projection_micro_cny"] == (
            row["static_before_candidate_total_token_projection"] * 36
        )
    assert budget["actual_usage_tokens"] is None
    assert budget["actual_cost_cny"] is None


def test_execution_graph_is_fixed_repair_then_judge_for_two_lanes(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    graph = _load(bundle / "execution/sequence_68.json")
    assert graph["total_nodes"] == 68
    assert graph["repair_nodes"] == 34
    assert graph["independent_judge_nodes"] == 34
    assert graph["tested_lane_order"] == ["flash", "pro"]
    assert graph["judge_lane"] == {
        "provider": "qianwen_platform",
        "model": "qwen3.7-max-2026-05-20",
        "family": "qwen",
        "live_catalog_check": "PENDING_BEFORE_NETWORK_RELEASE",
    }
    nodes = graph["nodes"]
    assert [node["sequence"] for node in nodes] == list(range(1, 69))
    for index in range(0, 68, 2):
        repair = nodes[index]
        judge = nodes[index + 1]
        assert repair["node_kind"] == "repair"
        assert judge["node_kind"] == "independent_judge"
        assert judge["depends_on"] == [repair["node_id"]]
        assert judge["judge_model"] == MODEL_ID
        assert judge[
            "static_before_candidate_cost_projection_micro_cny"
        ] == (
            judge["static_before_candidate_total_token_projection"] * 36
        )
        assert judge["round_token_cap"] == 500_000
        assert judge["send_preflight_token_gate"] == (
            "actual_accumulated_tokens + "
            "next_conservative_token_projection <= 500000"
        )
        assert judge["send_preflight_cost_gate"] == (
            "actual_accumulated_micro_cny + "
            "next_conservative_cap_micro_cny <= 10000000"
        )
        assert judge["dynamic_request_sha_status"] == "PENDING_P2_RESPONSE"
    binding = _load(
        bundle / "receipts/graph_transport_binding_preflight.json"
    )
    assert binding["status"] == "PASS_ZERO_CALL_GRAPH_FROZEN"
    assert binding["binding_count"] == 34
    assert binding["unique_judge_nodes"] == 34
    assert binding["unique_predecessor_repair_nodes"] == 34
    assert all(
        row["runtime_ticket_status"] == "PENDING_REPAIR_CALL"
        for row in binding["bindings"]
    )


def test_dynamic_single_request_binds_four_sources_and_uses_direct_http_body(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")["mappings"][0]
    template_path = bundle / mapping["verifier_template_path"]
    template = _load(template_path)
    repair_path = REPO_ROOT / mapping["repair_request_path"]
    p2_response = _valid_p2_response(repair_path)
    runtime = _runtime_binding(
        bundle,
        mapping,
        p2_response_bytes=p2_response,
    )
    rendered = render_dynamic_verifier_request(
        template,
        expected_template_sha256=mapping["verifier_template_sha256"],
        repair_request_bytes=repair_path.read_bytes(),
        p2_response_bytes=p2_response,
        **runtime,
    )
    assert rendered["status"] == (
        "FROZEN_READY_FOR_CATALOG_PREFLIGHT_NOT_SENT"
    )
    body = rendered["request_body"]
    assert body["model"] == "qwen3.7-max-2026-05-20"
    assert body["temperature"] == 0.0
    assert body["n"] == 1
    assert body["max_completion_tokens"] == 4000
    assert body["enable_thinking"] is False
    assert "extra_body" not in body
    assert "response_format" not in body
    assert rendered["transport"]["timeout_seconds"] == 120
    assert rendered["transport"]["api_key_env"] == "DASHSCOPE_API_KEY"
    assert rendered["transport"]["response_format"] is None
    assert set(rendered["source_binding"]) == {
        "judge_node_id",
        "repair_node_id",
        "tested_lane",
        "tested_provider",
        "tested_model",
        "repair_raw_response_path",
        "repair_raw_response_sha256",
        "repair_call_attempt_path",
        "repair_call_attempt_sha256",
        "repair_usage_path",
        "repair_usage_sha256",
        "repair_request_sha256",
        "p2_response_sha256",
        "template_sha256",
        "source_data_sha256",
        "dynamic_request_body_sha256",
    }
    assert rendered["source_binding"]["p2_response_sha256"] == sha256_bytes(
        p2_response
    )
    assert scan_model_visible_leaks(body["messages"]) == []


def test_dynamic_batch_request_normalizes_without_exposing_contract_identity(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = next(
        row
        for row in _load(bundle / "mappings/verifier_mapping.json")[
            "mappings"
        ]
        if row["contract_mode"] == "atom_batch_v2"
    )
    template_path = bundle / mapping["verifier_template_path"]
    template = _load(template_path)
    repair_path = REPO_ROOT / mapping["repair_request_path"]
    p2_response = _valid_p2_response(repair_path)
    rendered = render_dynamic_verifier_request(
        template,
        expected_template_sha256=mapping["verifier_template_sha256"],
        repair_request_bytes=repair_path.read_bytes(),
        p2_response_bytes=p2_response,
        **_runtime_binding(
            bundle,
            mapping,
            p2_response_bytes=p2_response,
        ),
    )
    user_payload = json.loads(rendered["request_body"]["messages"][1]["content"])
    assert len(user_payload["items"]) == len(mapping["source_slot_ids"])
    assert all(
        item["candidate_result"]["result_kind"] == "PATCH"
        for item in user_payload["items"]
    )
    visible = json.dumps(user_payload, ensure_ascii=False).casefold()
    assert "atom_batch_v2" not in visible
    assert "single_patch" not in visible
    assert "sensenova" not in visible
    assert "tencent_tokenhub" not in visible


def test_dynamic_renderer_rejects_source_template_and_p2_drift(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")["mappings"][0]
    template = _load(bundle / mapping["verifier_template_path"])
    repair_path = REPO_ROOT / mapping["repair_request_path"]
    repair_bytes = repair_path.read_bytes()
    p2_response = _valid_p2_response(repair_path)
    runtime = _runtime_binding(
        bundle,
        mapping,
        p2_response_bytes=p2_response,
    )
    with pytest.raises(Z98VerifierContractError, match="模板 SHA"):
        render_dynamic_verifier_request(
            template,
            expected_template_sha256="0" * 64,
            repair_request_bytes=repair_bytes,
            p2_response_bytes=p2_response,
            **runtime,
        )
    with pytest.raises(Z98VerifierContractError, match="请求路径或 SHA"):
        render_dynamic_verifier_request(
            template,
            expected_template_sha256=mapping["verifier_template_sha256"],
            repair_request_bytes=repair_bytes + b" ",
            p2_response_bytes=p2_response,
            **runtime,
        )
    invalid_p2 = json.loads(p2_response)
    invalid_p2["commentary"] = "合同外字段"
    invalid_p2_bytes = json.dumps(
        invalid_p2,
        ensure_ascii=False,
    ).encode("utf-8")
    with pytest.raises(Z98VerifierContractError, match="P2 响应拒收"):
        render_dynamic_verifier_request(
            template,
            expected_template_sha256=mapping["verifier_template_sha256"],
            repair_request_bytes=repair_bytes,
            p2_response_bytes=invalid_p2_bytes,
            **_runtime_binding(
                bundle,
                mapping,
                p2_response_bytes=invalid_p2_bytes,
            ),
        )


def test_dynamic_renderer_rejects_runtime_identity_leak(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")["mappings"][0]
    template = _load(bundle / mapping["verifier_template_path"])
    repair_path = REPO_ROOT / mapping["repair_request_path"]
    response = json.loads(_valid_p2_response(repair_path))
    response["object_or_result"] = "来自 sensenova 的结果"
    response_bytes = json.dumps(
        response,
        ensure_ascii=False,
    ).encode("utf-8")
    with pytest.raises(Z98VerifierContractError, match="动态裁判请求命中泄漏"):
        render_dynamic_verifier_request(
            template,
            expected_template_sha256=mapping["verifier_template_sha256"],
            repair_request_bytes=repair_path.read_bytes(),
            p2_response_bytes=response_bytes,
            **_runtime_binding(
                bundle,
                mapping,
                p2_response_bytes=response_bytes,
            ),
        )


@pytest.mark.parametrize(
    ("target_lane", "crossed_lane"),
    [("flash", "pro"), ("pro", "flash")],
)
def test_dynamic_renderer_rejects_flash_pro_response_cross_attachment(
    tmp_path: Path,
    target_lane: str,
    crossed_lane: str,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")["mappings"][0]
    template = _load(bundle / mapping["verifier_template_path"])
    repair_path = REPO_ROOT / mapping["repair_request_path"]
    target_response = json.loads(_valid_p2_response(repair_path))
    target_response["actor"] = f"{target_lane}-候选主体"
    target_response_bytes = json.dumps(
        target_response,
        ensure_ascii=False,
    ).encode("utf-8")
    crossed_response = copy.deepcopy(target_response)
    crossed_response["actor"] = f"{crossed_lane}-候选主体"
    crossed_response_bytes = json.dumps(
        crossed_response,
        ensure_ascii=False,
    ).encode("utf-8")
    target_runtime = _runtime_binding(
        bundle,
        mapping,
        tested_lane=target_lane,
        p2_response_bytes=target_response_bytes,
    )
    crossed_runtime = _runtime_binding(
        bundle,
        mapping,
        tested_lane=crossed_lane,
        p2_response_bytes=crossed_response_bytes,
    )
    crossed_evidence = {
        **target_runtime,
        "call_attempt_path": crossed_runtime["call_attempt_path"],
        "call_attempt_bytes": crossed_runtime["call_attempt_bytes"],
        "usage_path": crossed_runtime["usage_path"],
        "usage_bytes": crossed_runtime["usage_bytes"],
    }
    with pytest.raises(
        Z98VerifierContractError,
        match="call_attempt.*不一致",
    ):
        render_dynamic_verifier_request(
            template,
            expected_template_sha256=mapping["verifier_template_sha256"],
            repair_request_bytes=repair_path.read_bytes(),
            p2_response_bytes=target_response_bytes,
            **crossed_evidence,
        )


def test_dynamic_renderer_records_three_transport_ticket_paths_and_shas(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")["mappings"][0]
    template = _load(bundle / mapping["verifier_template_path"])
    repair_path = REPO_ROOT / mapping["repair_request_path"]
    response = _valid_p2_response(repair_path)
    runtime = _runtime_binding(
        bundle,
        mapping,
        tested_lane="pro",
        p2_response_bytes=response,
    )
    rendered = render_dynamic_verifier_request(
        template,
        expected_template_sha256=mapping["verifier_template_sha256"],
        repair_request_bytes=repair_path.read_bytes(),
        p2_response_bytes=response,
        **runtime,
    )
    binding = rendered["source_binding"]
    assert binding["judge_node_id"] == runtime["judge_node"]["node_id"]
    assert binding["repair_node_id"] == runtime["repair_node"]["node_id"]
    assert binding["tested_lane"] == "pro"
    assert binding["tested_provider"] == "tencent_tokenhub"
    assert binding["tested_model"] == "deepseek-v4-pro-202606"
    assert binding["repair_raw_response_path"] == runtime["p2_response_path"]
    assert binding["repair_raw_response_sha256"] == sha256_bytes(response)
    assert binding["repair_call_attempt_path"] == runtime["call_attempt_path"]
    assert binding["repair_call_attempt_sha256"] == sha256_bytes(
        runtime["call_attempt_bytes"]
    )
    assert binding["repair_usage_path"] == runtime["usage_path"]
    assert binding["repair_usage_sha256"] == sha256_bytes(
        runtime["usage_bytes"]
    )
    budget = rendered["budget_preflight"]
    assert budget["status"] == "PASS_BEFORE_SEND"
    assert "实际 P2 candidate_result" in budget["calculation_scope"]
    assert budget["conservative_prompt_token_projection"] > 0
    assert budget["conservative_total_token_projection"] == (
        budget["conservative_prompt_token_projection"] + 4000
    )
    assert budget["token_gate"]["allowed"] is True
    assert budget["cost_gate"]["allowed"] is True


def test_dynamic_budget_gate_recomputes_after_candidate_insertion(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")["mappings"][0]
    template = _load(bundle / mapping["verifier_template_path"])
    repair_path = REPO_ROOT / mapping["repair_request_path"]
    response = _valid_p2_response(repair_path)
    runtime = _runtime_binding(
        bundle,
        mapping,
        p2_response_bytes=response,
    )
    with pytest.raises(Z98VerifierContractError, match="50 万 token"):
        render_dynamic_verifier_request(
            template,
            expected_template_sha256=mapping["verifier_template_sha256"],
            repair_request_bytes=repair_path.read_bytes(),
            p2_response_bytes=response,
            **{
                **runtime,
                "actual_accumulated_tokens": 500_000,
            },
        )
    with pytest.raises(Z98VerifierContractError, match="金额帽"):
        render_dynamic_verifier_request(
            template,
            expected_template_sha256=mapping["verifier_template_sha256"],
            repair_request_bytes=repair_path.read_bytes(),
            p2_response_bytes=response,
            **{
                **runtime,
                "actual_accumulated_micro_cny": 10_000_000,
            },
        )


@pytest.mark.parametrize("contract_mode", ["single_patch", "atom_batch_v2"])
def test_dynamic_renderer_rejects_duplicate_keys_in_p2_response(
    tmp_path: Path,
    contract_mode: str,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = next(
        row
        for row in _load(bundle / "mappings/verifier_mapping.json")[
            "mappings"
        ]
        if row["contract_mode"] == contract_mode
    )
    template = _load(bundle / mapping["verifier_template_path"])
    repair_path = REPO_ROOT / mapping["repair_request_path"]
    raw = _valid_p2_response(repair_path).decode("utf-8")
    if contract_mode == "single_patch":
        duplicated = raw.replace(
            '"op": "KEEP"',
            '"op": "KEEP", "op": "KEEP"',
            1,
        )
    else:
        duplicated = raw.replace(
            '"status": "ok"',
            '"status": "ok", "status": "ok"',
            1,
        )
    response = duplicated.encode("utf-8")
    runtime = _runtime_binding(
        bundle,
        mapping,
        p2_response_bytes=response,
    )
    with pytest.raises(Z98VerifierContractError, match="重复 JSON 键"):
        render_dynamic_verifier_request(
            template,
            expected_template_sha256=mapping["verifier_template_sha256"],
            repair_request_bytes=repair_path.read_bytes(),
            p2_response_bytes=response,
            **runtime,
        )


def test_strict_verdict_parser_accepts_consistent_pass_and_rejects_drift(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")["mappings"][0]
    template = _load(bundle / mapping["verifier_template_path"])
    binding = template["private_binding"]
    raw = _valid_verdict(binding["case_id"], binding["item_ids"])
    parsed = parse_verifier_content(
        raw,
        expected_case_id=binding["case_id"],
        expected_item_ids=binding["item_ids"],
    )
    assert parsed["items"][0]["verdict"] == "PASS"

    extra = json.loads(raw)
    extra["items"][0]["repair_suggestion"] = "不允许"
    with pytest.raises(Z98VerifierContractError, match="未知字段"):
        parse_verifier_content(
            json.dumps(extra, ensure_ascii=False),
            expected_case_id=binding["case_id"],
            expected_item_ids=binding["item_ids"],
        )
    inconsistent = json.loads(raw)
    inconsistent["items"][0]["anchor_support"] = "PARTIAL"
    with pytest.raises(Z98VerifierContractError, match="PASS 判词"):
        parse_verifier_content(
            json.dumps(inconsistent, ensure_ascii=False),
            expected_case_id=binding["case_id"],
            expected_item_ids=binding["item_ids"],
        )
    fenced = f"```json\n{raw}\n```"
    with pytest.raises(Z98VerifierContractError, match="严格 JSON"):
        parse_verifier_content(
            fenced,
            expected_case_id=binding["case_id"],
            expected_item_ids=binding["item_ids"],
        )


def test_strict_verdict_parser_rejects_duplicate_keys_at_any_depth(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")["mappings"][0]
    template = _load(bundle / mapping["verifier_template_path"])
    binding = template["private_binding"]
    raw = _valid_verdict(binding["case_id"], binding["item_ids"])
    top_duplicate = raw.replace(
        '"schema": "z98-independent-verdict-v1"',
        (
            '"schema": "z98-independent-verdict-v1", '
            '"schema": "z98-independent-verdict-v1"'
        ),
        1,
    )
    with pytest.raises(Z98VerifierContractError, match="重复 JSON 键：schema"):
        parse_verifier_content(
            top_duplicate,
            expected_case_id=binding["case_id"],
            expected_item_ids=binding["item_ids"],
        )
    nested_duplicate = raw.replace(
        '"verdict": "PASS"',
        '"verdict": "PASS", "verdict": "PASS"',
        1,
    )
    with pytest.raises(Z98VerifierContractError, match="重复 JSON 键：verdict"):
        parse_verifier_content(
            nested_duplicate,
            expected_case_id=binding["case_id"],
            expected_item_ids=binding["item_ids"],
        )
    receipt_duplicate = raw.replace(
        '"returned_item_ids":',
        '"returned_item_ids": [], "returned_item_ids":',
        1,
    )
    with pytest.raises(
        Z98VerifierContractError,
        match="重复 JSON 键：returned_item_ids",
    ):
        parse_verifier_content(
            receipt_duplicate,
            expected_case_id=binding["case_id"],
            expected_item_ids=binding["item_ids"],
        )


def test_verdict_schema_closes_every_object_layer() -> None:
    schema = _load(
        REPO_ROOT
        / "experiments/Z98_independent_verifier_freeze_20260724/"
        "contracts/z98_independent_verdict_v1.schema.json"
    )
    stack: list[object] = [schema]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def test_target_directory_must_be_empty(tmp_path: Path) -> None:
    target = tmp_path / "bundle"
    target.mkdir()
    (target / "existing").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(Z98VerifierContractError, match="目标目录非空"):
        pipeline.build_bundle(target, repo_root=REPO_ROOT)


def test_authority_listing_mismatch_hard_stops_before_freeze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline,
        "STEP1_REQUEST_AUTHORITY_AGGREGATE_SHA256",
        "0" * 64,
    )
    with pytest.raises(Z98VerifierContractError, match="权威集合 SHA"):
        pipeline.build_bundle(tmp_path / "bundle", repo_root=REPO_ROOT)


def test_conservative_price_math_and_send_gate() -> None:
    assert conservative_cost_cap_micro_cny(401) == 14_436
    assert conservative_cost_cap_micro_cny(3867) == 139_212
    assert TOTAL_COST_CAP_MICRO_CNY == 10_000_000
    receipt = enforce_cost_gate_before_send(
        actual_accumulated_micro_cny=9_860_788,
        next_conservative_cap_micro_cny=139_212,
    )
    assert receipt["allowed"] is True
    assert receipt["projected_micro_cny"] == 10_000_000
    with pytest.raises(Z98VerifierContractError, match="金额帽"):
        enforce_cost_gate_before_send(
            actual_accumulated_micro_cny=9_860_789,
            next_conservative_cap_micro_cny=139_212,
        )
    with pytest.raises(Z98VerifierContractError, match="正整数"):
        conservative_cost_cap_micro_cny(0)
    assert TOTAL_TOKEN_CAP == 500_000
    token_receipt = enforce_token_gate_before_send(
        actual_accumulated_tokens=490_000,
        next_conservative_token_projection=10_000,
    )
    assert token_receipt["allowed"] is True
    assert token_receipt["projected_tokens"] == 500_000
    with pytest.raises(Z98VerifierContractError, match="50 万 token"):
        enforce_token_gate_before_send(
            actual_accumulated_tokens=490_001,
            next_conservative_token_projection=10_000,
        )


def test_leak_scanner_rejects_arm_provider_and_answer_faces() -> None:
    payload = {
        "provider_lane": "flash",
        "nested": [
            "tencent_tokenhub",
            {"answer": "正式答案"},
            {"contract_mode": "single_patch"},
        ],
    }
    hits = scan_model_visible_leaks(payload)
    reasons = {hit["reason"] for hit in hits}
    assert "forbidden_key" in reasons
    assert any("tencent_tokenhub" in reason for reason in reasons)
    assert any("single_patch" in reason for reason in reasons)


def test_private_template_mapping_drift_cannot_change_source_sha(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")["mappings"][0]
    template = _load(bundle / mapping["verifier_template_path"])
    tampered = copy.deepcopy(template)
    content = json.loads(tampered["model_visible"]["messages"][1]["content"])
    content["items"][0]["source_event"] = "被改过"
    tampered["model_visible"]["messages"][1]["content"] = json.dumps(
        content,
        ensure_ascii=False,
    )
    repair_path = REPO_ROOT / mapping["repair_request_path"]
    p2_response = _valid_p2_response(repair_path)
    with pytest.raises(Z98VerifierContractError, match="模板 SHA"):
        render_dynamic_verifier_request(
            tampered,
            expected_template_sha256=mapping["verifier_template_sha256"],
            repair_request_bytes=repair_path.read_bytes(),
            p2_response_bytes=p2_response,
            **_runtime_binding(
                bundle,
                mapping,
                p2_response_bytes=p2_response,
            ),
        )

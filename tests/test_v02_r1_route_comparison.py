from __future__ import annotations

import json

from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (
    v02_r1_route_comparison as r1,
)


def test_reference_map_has_thirty_cells_and_valid_formal_parts() -> None:
    value = r1.question_reference_map()
    assert value["cell_total"] == 30
    assert len(value["cells"]) == 30
    assert value["model_visible"] is False
    assert all(cell["expected"] in {"ANSWERED", "OPEN"} for cell in value["cells"])
    assert any(cell["expected"] == "OPEN" for cell in value["cells"])


def test_current_z00l_schema_includes_coverage_audit() -> None:
    schema = r1.z00l_output_schema()
    assert schema["required"] == [
        "schema_version",
        "chapter",
        "coverage_audit",
        "events",
    ]
    assert "coverage_audit" in schema["properties"]


def test_routes_are_three_plus_three_plus_six_and_zero_retry() -> None:
    rows = r1.frozen_requests()
    assert len(rows) == 12
    assert sum(row["route_id"] == "A_FULL_ONCE_Z00L" for row in rows) == 3
    assert sum(row["route_id"] == "B_HOT_FULL_ONCE" for row in rows) == 3
    assert sum(row["route_id"] == "C_HOT_TWO_CHUNKS" for row in rows) == 6
    assert len({row["call_id"] for row in rows}) == 12
    assert all(row["body"]["model"] == "deepseek-v4-flash" for row in rows)
    assert all(row["body"]["reasoning_effort"] == "medium" for row in rows)


def test_a_uses_exact_current_prompt_and_b_c_share_hot_contract() -> None:
    rows = r1.frozen_requests()
    a = next(row for row in rows if row["route_id"] == "A_FULL_ONCE_Z00L")
    b = next(row for row in rows if row["route_id"] == "B_HOT_FULL_ONCE")
    c = next(row for row in rows if row["route_id"] == "C_HOT_TWO_CHUNKS")
    assert "# Z00l 中性事件提取 Prompt v1.0" in a["body"]["messages"][1]["content"]
    assert "coverage_audit" in a["body"]["messages"][1]["content"]
    assert r1.hot_contract_text() in b["body"]["messages"][1]["content"]
    assert r1.hot_contract_text() in c["body"]["messages"][1]["content"]


def test_gold_and_secrets_do_not_enter_model_messages() -> None:
    raw = json.dumps(r1.frozen_requests(), ensure_ascii=False)
    for forbidden in (
        "config/gold",
        "formal_gold",
        "API_KEY",
        "Z74B-B01-U0033-A01",
    ):
        assert forbidden not in raw


def test_preregistration_uses_latest_correction_and_no_signature_gate() -> None:
    value = r1.preregistration()
    assert value["authority"]["revision"].startswith("修正令②")
    assert value["authority"]["waiting_for_notion_signature"] is False
    assert value["network_authorization"]["execute_allowed"] is True
    assert "NOTION_APPROVED_TO_SEND" not in value["pre_send_gates"]
    assert value["route_call_budget"]["total"] == 12


def test_artifacts_are_deterministic_and_zero_network() -> None:
    first = r1.build_artifacts()
    second = r1.build_artifacts()
    assert first == second
    manifest = json.loads(first["manifest.json"])
    assert manifest["model_api_calls"] == 0
    assert manifest["network_requests"] == 0
    assert manifest["git_commit_or_push"] is False

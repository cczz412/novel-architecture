from __future__ import annotations

from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (
    v02_r1_route_comparison as r02,
)
from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (
    v02_r1_route_comparison_r03 as r03,
)


def test_only_hot_requests_change_between_r02_and_r03() -> None:
    old = {row["call_id"]: row for row in r02.frozen_requests()}
    new = {row["call_id"]: row for row in r03.frozen_requests()}
    assert old.keys() == new.keys()
    for call_id in old:
        if old[call_id]["route_id"] == "A_FULL_ONCE_Z00L":
            assert old[call_id]["request_sha256"] == new[call_id][
                "request_sha256"
            ]
        else:
            assert old[call_id]["request_sha256"] != new[call_id][
                "request_sha256"
            ]


def test_hot_contract_has_exact_shell_and_forbids_extra_top_level_fields() -> None:
    text = r03.hot_contract_text()
    assert '"facts": [' in text
    assert '"cold_index": [' in text
    assert "禁止把八类名称做成顶层字段" in text
    assert "禁止增加 range_id" in text


def test_r03_preregistration_records_engineering_delta() -> None:
    value = r03.preregistration()
    assert value["schema_version"].endswith(".v3")
    assert "HOT_CONTRACT_SHOWS_EXACT_JSON_SHELL" in value[
        "engineering_delta_from_r02"
    ]
    assert value["network_authorization"]["execute_allowed"] is True

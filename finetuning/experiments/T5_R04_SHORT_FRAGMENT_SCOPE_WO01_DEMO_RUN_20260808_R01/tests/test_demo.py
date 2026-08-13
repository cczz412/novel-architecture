from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "tools"))
import run_demo  # noqa: E402
import score_demo  # noqa: E402


def fake_rows(*, perfect: bool, extra: bool = False):
    canonical = score_demo.canonical_map()
    rows = []
    for index, item in enumerate(run_demo.load_plan(), start=1):
        if perfect:
            facts = [
                {key: value for key, value in row.items() if key != "fact_id"}
                for row in score_demo.gold(canonical[item["case_id"]])
            ]
        elif extra:
            facts = [{"fact": "共享待审事实", "status": "已发生", "speaker": None, "evidence_ids": []}]
        else:
            facts = []
        rows.append({"sequence_index": index, "arm": item["arm"], "row_index": item["row_index"], "case_id": item["case_id"], "request_sha256": item["request_sha256"], "gold_binding_sha256": item["gold_binding_sha256"], "raw_output": json.dumps({"facts": facts}, ensure_ascii=False), "finish_reason": "stop", "stop_token_is_eos_eot": True, "output_tokens": 10})
    return rows


def write_rows(path: Path, rows: list[dict]):
    path.write_bytes(b"".join((json.dumps(row, ensure_ascii=False) + "\n").encode() for row in rows))


def test_plan_has_three_by_24_and_two_messages():
    plan = run_demo.load_plan()
    assert len(plan) == 72
    assert {arm: sum(row["arm"] == arm for row in plan) for arm in run_demo.ARMS} == {arm: 24 for arm in run_demo.ARMS}
    assert all([row["role"] for row in item["messages"]] == ["system", "user"] for item in plan)


def test_model_visible_payload_has_no_case_arm_or_gold():
    for item in run_demo.load_plan():
        visible = json.dumps(item["messages"], ensure_ascii=False)
        assert item["case_id"] not in visible
        assert '"arm"' not in visible
        assert '"gold"' not in visible


def test_same_case_target_and_gold_bindings_are_shared_across_arms():
    plan = run_demo.load_plan()
    by_case = {}
    for row in plan:
        by_case.setdefault(row["case_id"], []).append(row)
    assert len(by_case) == 24
    for rows in by_case.values():
        assert len({row["gold_binding_sha256"] for row in rows}) == 1


def test_smoke_selects_two_extreme_context_requests():
    smoke = run_demo.selected_plan("smoke")
    assert len(smoke) == 2
    assert [row["arm"] for row in smoke] == ["TARGET_ONLY", "CURRENT_WINDOW"]


def test_perfect_fixture_preserves_24_48_denominator(tmp_path: Path):
    raw = tmp_path / "raw.jsonl"
    write_rows(raw, fake_rows(perfect=True))
    result = score_demo.score(raw, None)
    assert result["status"] == "PASS_FINAL_SCORING"
    assert all(result["arms"][arm]["semantic"] == {"tp": 48, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0} for arm in run_demo.ARMS)


def test_shared_prediction_is_one_blind_item_per_case_not_per_arm(tmp_path: Path):
    raw = tmp_path / "raw.jsonl"
    write_rows(raw, fake_rows(perfect=False, extra=True))
    result = score_demo.score(raw, None)
    assert result["semantic_pending"] == 24
    assert len(result["blind_queue"]) == 24
    assert all("arm" not in row for row in result["blind_queue"])


def test_case_order_drift_hard_stops(tmp_path: Path):
    rows = fake_rows(perfect=False)
    rows[0], rows[1] = rows[1], rows[0]
    raw = tmp_path / "raw.jsonl"
    write_rows(raw, rows)
    with pytest.raises(RuntimeError, match="CASE_ORDER_DRIFT"):
        score_demo.score(raw, None)


def test_existing_output_is_not_overwritten(tmp_path: Path):
    target = tmp_path / "receipt.json"
    score_demo.write_json(target, {"x": 1})
    with pytest.raises(RuntimeError, match="NO_OVERWRITE"):
        score_demo.write_json(target, {"x": 2})

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


EXP = Path(__file__).resolve().parents[1]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load(EXP / "tools/run_demo_r02.py", "r02_runner")


def test_r02_only_wraps_frozen_r01_runner():
    assert runner.R01_RUNNER.is_file()
    assert runner.EXPECTED_PYTHON == "/opt/homebrew/opt/python@3.12/bin/python3.12"


def test_smoke_is_two_cases_in_each_of_three_arms():
    r01 = runner.load_r01()
    rows = runner.smoke_plan(r01)
    assert len(rows) == 6
    assert {arm: sum(row["arm"] == arm for row in rows) for arm in r01.ARMS} == {arm: 2 for arm in r01.ARMS}


def test_full_plan_stays_three_by_24():
    r01 = runner.load_r01()
    rows = r01.load_plan()
    assert len(rows) == 72
    assert {arm: sum(row["arm"] == arm for row in rows) for arm in r01.ARMS} == {arm: 24 for arm in r01.ARMS}


def test_every_request_keeps_system_and_user():
    assert all([item["role"] for item in row["messages"]] == ["system", "user"] for row in runner.load_r01().load_plan())


def test_r02_scorer_reuses_frozen_minimal_r01_scorer():
    wrapper = load(EXP / "tools/score_demo_r02.py", "r02_scorer")
    scorer = wrapper.load_r01()
    assert len(scorer.canonical_map()) == 24


def test_invalid_status_keeps_recoverable_fact_but_fails_schema():
    wrapper = load(EXP / "tools/score_demo_r02.py", "r02_scorer_recoverable")
    scorer = wrapper.load_r01()
    raw = json.dumps(
        {"facts": [{"fact": "门正在关闭。", "status": "进行中", "speaker": None, "evidence_ids": ["T01"]}]},
        ensure_ascii=False,
    )
    schema_valid, recovered = wrapper.recoverable_parse(scorer, raw)
    assert schema_valid is False
    assert [row["fact"] for row in recovered] == ["门正在关闭。"]


def test_unreadable_root_does_not_create_recoverable_facts():
    wrapper = load(EXP / "tools/score_demo_r02.py", "r02_scorer_bad_root")
    scorer = wrapper.load_r01()
    schema_valid, recovered = wrapper.recoverable_parse(scorer, '{"not_facts": []}')
    assert schema_valid is False
    assert recovered == []


def test_adjudication_set_merges_without_recursive_wrapper():
    wrapper = load(EXP / "tools/score_demo_r02.py", "r02_scorer_adjudication_set")
    scorer = wrapper.load_r01()
    canonical = scorer.canonical_map()
    manifest = (
        wrapper.REPO
        / "runs/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_R02/semantic_adjudications_r02/ADJUDICATION_SET_R02.json"
    )
    index = wrapper.adjudication_set_index(
        scorer,
        scorer.adjudication_index,
        manifest,
        "63cbc42db5852e7ccae5625dc4981927f10d17bcb0559f62661e1e3fa699905b",
        canonical,
    )
    assert len(index) == 57

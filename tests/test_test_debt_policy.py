from __future__ import annotations

import configparser
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_default_pytest_scope_excludes_retired_temp_tree() -> None:
    parser = configparser.ConfigParser()
    parser.read(ROOT / "pytest.ini", encoding="utf-8")
    pytest_section = parser["pytest"]
    assert pytest_section["testpaths"].split() == ["tests"]
    ignored = set(pytest_section["norecursedirs"].split())
    assert {"TEMP", "runs", "reports"} <= ignored


def test_debt_registry_is_exact_owned_and_time_bounded() -> None:
    registry = json.loads(
        (ROOT / "tests/test_debt_registry.json").read_text(encoding="utf-8")
    )
    assert registry["schema_version"] == "pytest-archived-fixture-debt-v2"
    allowed_files = {
        "tests/test_extraction_method_ab.py",
        "tests/test_net_benefit_recompute.py",
        "tests/test_nonthinking_pilot.py",
        "tests/test_z68_continuation_32k.py",
        "tests/test_z70_compression_contract_report.py",
        "tests/test_z72_gold_granularity_candidate.py",
        "tests/test_zbatch.py",
    }
    all_nodeids: list[str] = []
    for group in registry["groups"]:
        assert group["owner"]
        assert date.fromisoformat(group["due_date"]) >= date.today()
        assert group["required_paths"]
        assert any(not (ROOT / path).is_file() for path in group["required_paths"])
        for nodeid in group["nodeids"]:
            assert not any(token in nodeid for token in ("*", "?", "["))
            test_relative, _, test_name = nodeid.rpartition("::")
            test_file = test_relative.split("::", 1)[0]
            assert test_file in allowed_files
            source = (ROOT / test_file).read_text(encoding="utf-8")
            assert f"def {test_name}(" in source
            all_nodeids.append(nodeid)
    assert len(all_nodeids) == len(set(all_nodeids)) == 40
    runtime_groups = [
        group for group in registry["groups"] if group.get("application") == "runtime_guard"
    ]
    assert len(runtime_groups) == 1
    runtime_nodeid = runtime_groups[0]["nodeids"][0]
    runtime_test = (ROOT / runtime_nodeid.split("::", 1)[0]).read_text(encoding="utf-8")
    assert "xfail_if_registered_fixture_missing" in runtime_test


def test_original_six_failures_have_one_explicit_disposition_each() -> None:
    receipt = json.loads(
        (ROOT / "tests/old_failure_disposition.json").read_text(encoding="utf-8")
    )
    assert receipt["schema_version"] == "old-main-failure-disposition-v1"
    assert receipt["baseline_failure_total"] == 6
    entries = receipt["entries"]
    nodeids = [entry["nodeid"] for entry in entries]
    assert len(nodeids) == len(set(nodeids)) == 6
    assert sum("neutral_extract" in entry["original_issue"] for entry in entries) == 5
    assert sum("events为空" in entry["original_issue"] for entry in entries) == 1
    for entry in entries:
        assert entry["disposition"]
        assert entry["current_expectation"] in {"pass", "xfail_when_fixture_missing"}

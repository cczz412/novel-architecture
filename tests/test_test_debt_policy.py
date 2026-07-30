from __future__ import annotations

import ast
import configparser
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config/test_replay/historical_replays.json"
SCHEMA_PATH = ROOT / "config/test_replay/historical_replays_v1.schema.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _definition_exists(nodeid: str) -> bool:
    parts = nodeid.split("::")
    tree = ast.parse(
        (ROOT / parts[0]).read_text(encoding="utf-8"),
        filename=parts[0],
    )
    if len(parts) == 2:
        return any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == parts[1]
            for node in tree.body
        )
    if len(parts) == 3:
        return any(
            isinstance(node, ast.ClassDef)
            and node.name == parts[1]
            and any(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == parts[2]
                for child in node.body
            )
            for node in tree.body
        )
    return False


def test_default_pytest_scope_excludes_retired_temp_tree() -> None:
    parser = configparser.ConfigParser()
    parser.read(ROOT / "pytest.ini", encoding="utf-8")
    pytest_section = parser["pytest"]
    assert pytest_section["testpaths"].split() == ["tests"]
    ignored = set(pytest_section["norecursedirs"].split())
    assert {"TEMP", "runs", "reports", "outbox"} <= ignored
    markers = pytest_section["markers"]
    assert "historical_replay" in markers
    assert "archived_fixture" not in markers


def test_old_debt_registry_is_only_an_s05b_migration_pointer() -> None:
    pointer = _read_json(ROOT / "tests/test_debt_registry.json")
    assert pointer == {
        "schema_version": "pytest-archived-fixture-debt-retired-v1",
        "status": "migrated_to_historical_replay",
        "decision": {
            "authority": "CZ",
            "choice": "S-05-B",
            "source_text_sha256": (
                "21d6fbd145e723a7256b98b76595344431315b2b2d86afeed2897f9d7b12a268"
            ),
        },
        "former_group_count": 8,
        "former_node_count": 40,
        "replacement": "config/test_replay/historical_replays.json",
        "rule": (
            "本文件只保留迁移指针；精确节点、来源闭包和回放边界只认 replacement。"
        ),
    }
    serialized = json.dumps(pointer, ensure_ascii=False)
    for retired_field in (
        "due_date",
        "owner",
        "required_paths",
        "nodeids",
        "application",
    ):
        assert retired_field not in serialized


def test_historical_registry_has_exact_real_nodes_and_source_units() -> None:
    schema = _read_json(SCHEMA_PATH)
    registry = _read_json(REGISTRY_PATH)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(registry)

    decision = registry["decision"]
    assert decision["authority"] == "CZ"
    assert decision["choice"] == decision["source_text"] == "S-05-B"
    assert hashlib.sha256(b"S-05-B").hexdigest() == decision["source_text_sha256"]
    assert registry["default_collection"] == {
        "mode": "deselect_exact",
        "marker": "historical_replay",
        "node_count": 40,
    }

    nodeids = [nodeid for group in registry["groups"] for nodeid in group["nodeids"]]
    assert len(registry["groups"]) == 8
    assert len(nodeids) == len(set(nodeids)) == 40
    assert all(_definition_exists(nodeid) for nodeid in nodeids)
    assert {nodeid.split("::", 1)[0] for nodeid in nodeids} == {
        "tests/test_extraction_method_ab.py",
        "tests/test_net_benefit_recompute.py",
        "tests/test_nonthinking_pilot.py",
        "tests/test_z68_continuation_32k.py",
        "tests/test_z70_compression_contract_report.py",
        "tests/test_z72_gold_granularity_candidate.py",
        "tests/test_zbatch.py",
    }

    unit_ids = {unit["unit_id"] for unit in registry["source_units"]}
    used_unit_ids = {
        unit_id for group in registry["groups"] for unit_id in group["source_unit_ids"]
    }
    assert len(unit_ids) == 24
    assert used_unit_ids == unit_ids
    for unit in registry["source_units"]:
        relative = Path(unit["repo_relative_path"])
        assert not relative.is_absolute()
        assert ".." not in relative.parts
        assert unit["kind"] in {"directory", "file"}
    assert registry["source_roots"][0]["manifest_sha256"] == (
        "a7560f2fc95503f3c9ce35c250437f19f9cb75fd53b5c78c02fcd68df74320a0"
    )
    assert registry["source_package"] == {
        "package_id": "historical_test_replay_s05b_20260731_v1",
        "status": "sealed",
        "external_root_id": "repository_sibling_external_archive_v1",
        "relative_path": "historical_test_replay_s05b_20260731_v1",
        "manifest_sha256": (
            "f2f2b3b612ac4b18f98abbabdd0bf500337fde9cfe62be8dacf1ab03f6a5503a"
        ),
    }


def test_historical_nodes_do_not_overlap_local_evidence_rules() -> None:
    registry = _read_json(REGISTRY_PATH)
    historical = {nodeid for group in registry["groups"] for nodeid in group["nodeids"]}
    historical_files = {Path(nodeid.split("::", 1)[0]).name for nodeid in historical}
    local = _read_json(ROOT / "tests/local_evidence_registry.json")
    local_nodeids = {
        nodeid for group in local["groups"] for nodeid in group.get("nodeids", [])
    }
    assert historical.isdisjoint(local_nodeids)
    for group in local["groups"]:
        for pattern in group.get("test_file_globs", []):
            assert not any(
                Path(filename).match(pattern) for filename in historical_files
            )


def test_old_runtime_debt_surfaces_no_longer_offer_xfail_or_bypass() -> None:
    paths = [
        ROOT / "tests/conftest.py",
        ROOT / "tests/archived_fixture_debt.py",
        ROOT / "tests/test_z68_continuation_32k.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for retired_text in (
        "NOVEL_RUN_ARCHIVED_FIXTURE_TESTS",
        "xfail_if_registered_fixture_missing",
        "pytest.mark.archived_fixture",
        "pytest.xfail",
        "strict=True",
        "due_date",
    ):
        assert retired_text not in combined
    assert "require_materialized_historical_replay" in combined
    assert "--historical-replay" in combined


def test_original_six_failures_have_one_explicit_disposition_each() -> None:
    receipt = _read_json(ROOT / "tests/old_failure_disposition.json")
    assert receipt["schema_version"] == "old-main-failure-disposition-v1"
    assert receipt["baseline_failure_total"] == 6
    entries = receipt["entries"]
    nodeids = [entry["nodeid"] for entry in entries]
    assert len(nodeids) == len(set(nodeids)) == 6
    assert sum("neutral_extract" in entry["original_issue"] for entry in entries) == 5
    assert sum("events为空" in entry["original_issue"] for entry in entries) == 1
    for entry in entries:
        assert entry["disposition"]
        assert entry["current_expectation"] in {
            "pass",
            "deselected_by_default_replay_only",
        }
        assert "due_date" not in entry
        assert "owner" not in entry
    migrated = next(
        entry for entry in entries if "events为空" in entry["original_issue"]
    )
    assert migrated["replay_group_id"] == "z68_archived_prior_run"


def test_governance_policy_names_one_default_and_one_replay_command() -> None:
    policy = _read_json(ROOT / "governance/test_policy.json")
    assert policy["full_chain_command"].endswith(".venv/bin/python -m pytest -q")
    assert policy["historical_replay_registry"] == (
        "config/test_replay/historical_replays.json"
    )
    assert policy["historical_replay_tool"] == ("tools/historical_test_replay.py")
    assert "--commit <完整40位提交号>" in policy["historical_replay_command"]
    serialized = json.dumps(policy, ensure_ascii=False)
    assert "archived_fixture_debt_registry" not in serialized
    assert "strict xfail" not in serialized
    assert "挂账到期" not in serialized

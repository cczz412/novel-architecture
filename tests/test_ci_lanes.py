from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from tools import ci_lanes


ROOT = Path(__file__).resolve().parents[1]


def _args(lane: str, receipt_dir: Path, **overrides: object) -> Namespace:
    values: dict[str, object] = {
        "lane": lane,
        "receipt_dir": receipt_dir,
        "keychain_target": [],
        "group": [],
        "commit": None,
        "run_id": None,
    }
    values.update(overrides)
    return Namespace(**values)


def _completed(argv: list[str], returncode: int = 0, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="")


def _read_receipt(path: Path) -> dict:
    return json.loads((path / "receipt.json").read_text(encoding="utf-8"))


def _collect_nodeids(*args: str) -> set[str]:
    environment = os.environ.copy()
    environment.pop("NOVEL_RUN_LOCAL_EVIDENCE_TESTS", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            *args,
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return {
        line.strip()
        for line in result.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    }


def _fake_head_then(monkeypatch: pytest.MonkeyPatch, returncodes: list[int]) -> list[dict]:
    calls: list[dict] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"argv": argv, **kwargs})
        if argv == ["git", "rev-parse", "HEAD"]:
            return _completed(argv, stdout="a" * 40 + "\n")
        return _completed(argv, returncodes.pop(0))

    monkeypatch.setattr(ci_lanes.subprocess, "run", fake_run)
    return calls


def test_contract_has_exact_four_fixed_lanes_and_no_network_or_model() -> None:
    contract = json.loads((ROOT / "governance/ci_lanes.json").read_text(encoding="utf-8"))
    assert contract["schema_version"] == "ci-test-lanes-v1"
    assert tuple(contract["lanes"]) == ci_lanes.LANE_IDS
    for lane_id, lane in contract["lanes"].items():
        assert lane["lane_id"] == lane_id
        assert lane["network"] is False
        assert lane["model_api"] is False
        assert lane["receipt_boundary"]["stores_subprocess_output"] is False
        assert lane["receipt_boundary"]["stores_absolute_paths"] is False
    assert (
        contract["lanes"]["main-portable"]["execution"]["network_guard"]
        == "force_for_all_selected_nodes"
    )


def test_contract_command_drift_hard_stops_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = json.loads(
        (ROOT / "governance/ci_lanes.json").read_text(encoding="utf-8")
    )
    contract["lanes"]["main-portable"]["execution"]["argv"].append("-x")
    tampered = tmp_path / "ci_lanes.json"
    tampered.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(ci_lanes, "CONTRACT_PATH", tampered)
    with pytest.raises(ci_lanes.LaneError, match="命令漂移"):
        ci_lanes.load_contract()


def test_main_contract_names_all_three_nonportable_sources() -> None:
    lane = ci_lanes.load_contract()["lanes"]["main-portable"]
    assert lane["execution"]["non_portable_exclusions"] == [
        "tests/local_evidence_registry.json",
        "config/test_replay/historical_replays.json",
        "macos-keychain.pytest_nodeids",
    ]


def test_main_portable_collection_excludes_exact_registered_nonportable_nodes() -> None:
    baseline = _collect_nodeids()
    portable = _collect_nodeids("--ci-lane", "main-portable")
    contract = ci_lanes.load_contract()
    keychain = set(contract["lanes"]["macos-keychain"]["pytest_nodeids"])
    local_registry = json.loads(
        (ROOT / "tests/local_evidence_registry.json").read_text(encoding="utf-8")
    )
    local: set[str] = set()
    for group in local_registry["groups"]:
        exact = set(group.get("nodeids", []))
        patterns = tuple(group.get("test_file_globs", []))
        for nodeid in baseline:
            test_name = Path(nodeid.split("::", 1)[0]).name
            if nodeid in exact or any(Path(test_name).match(pattern) for pattern in patterns):
                local.add(nodeid)

    assert local
    assert keychain <= baseline
    assert portable == baseline - local - keychain
    assert portable.isdisjoint(local)
    assert portable.isdisjoint(keychain)


def test_new_layout_local_evidence_is_exact_and_not_a_whole_file_rule() -> None:
    registry = json.loads(
        (ROOT / "tests/local_evidence_registry.json").read_text(encoding="utf-8")
    )
    groups = {row["group_id"]: row for row in registry["groups"]}
    expected = {
        "REPOSITORY-LAYOUT-WORKBUDDY-LOCAL-EVIDENCE": (
            "tests/test_repository_layout.py::"
            "test_directory_registry_matches_schema_and_runtime_contract"
        ),
        "REPOSITORY-LAYOUT-Z73-LOCAL-EVIDENCE": (
            "tests/test_repository_layout.py::"
            "test_temporary_refresh_does_not_modify_current_state"
        ),
    }
    for group_id, nodeid in expected.items():
        assert groups[group_id]["test_file_globs"] == []
        assert groups[group_id]["nodeids"] == [nodeid]


def test_main_portable_keeps_equivalent_repository_layout_guards() -> None:
    portable = _collect_nodeids("--ci-lane", "main-portable")
    assert {
        "tests/test_repository_layout.py::"
        "test_directory_registry_portable_contract_survives_missing_local_evidence",
        "tests/test_repository_layout.py::"
        "test_temporary_refresh_portable_path_does_not_modify_current_state",
    } <= portable
    assert (
        "tests/test_isolation.py::"
        "test_allow_network_marker_skips_default_network_guard"
    ) in portable


def test_keychain_contract_freezes_exact_five_nodes() -> None:
    nodes = ci_lanes.load_contract()["lanes"]["macos-keychain"]["pytest_nodeids"]
    assert len(nodes) == 5
    assert nodes == list(ci_lanes.KEYCHAIN_PYTEST_NODEIDS)
    assert nodes == [
        "tests/test_deepseek_official_config.py::test_deepseek_official_key_loader_help_is_zero_call",
        "tests/test_deepseek_official_config.py::test_deepseek_official_loader_denies_run_without_machine_execution_ack",
        "tests/test_provider_channel_configs.py::test_shared_keychain_loader_is_zero_call_and_names_all_providers",
        "tests/test_provider_channel_configs.py::test_agent_plan_is_rejected_by_project_keychain_loader",
        "tests/test_provider_channel_configs.py::test_unknown_provider_is_rejected_before_any_keychain_read",
    ]


def test_check_is_zero_execution(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        ci_lanes.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("check 不得启动子进程"),
    )
    args = _args("main-portable", Path("unused"))
    assert ci_lanes.check_lane(args) == 0
    assert json.loads(capsys.readouterr().out)["executes_commands"] is False


def test_main_uses_fixed_argv_and_repo_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _fake_head_then(monkeypatch, [0])
    receipt_dir = tmp_path / "receipt"
    assert ci_lanes.run_lane(_args("main-portable", receipt_dir)) == 0
    assert calls[1]["argv"] == [
        "uv", "run", "--locked", "pytest", "-q", "--ci-lane", "main-portable"
    ]
    assert calls[1]["cwd"] == ci_lanes.ROOT
    assert _read_receipt(receipt_dir)["status"] == "PASSED"


@pytest.mark.parametrize("system_name", ["Linux", "Windows"])
def test_keychain_non_darwin_is_not_dispatched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    system_name: str,
) -> None:
    calls = _fake_head_then(monkeypatch, [])
    monkeypatch.setattr(ci_lanes.platform, "system", lambda: system_name)
    receipt_dir = tmp_path / system_name
    code = ci_lanes.run_lane(
        _args("macos-keychain", receipt_dir, keychain_target=["volcengine_ark"])
    )
    assert code == ci_lanes.EXIT_NOT_DISPATCHED
    assert len(calls) == 1
    assert _read_receipt(receipt_dir)["status"] == "NOT_DISPATCHED"


def test_keychain_without_target_is_not_dispatched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _fake_head_then(monkeypatch, [])
    monkeypatch.setattr(ci_lanes.platform, "system", lambda: "Darwin")
    receipt_dir = tmp_path / "receipt"
    assert ci_lanes.run_lane(_args("macos-keychain", receipt_dir)) == ci_lanes.EXIT_NOT_DISPATCHED
    assert len(calls) == 1


def test_keychain_unknown_target_never_reads_keychain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _fake_head_then(monkeypatch, [])
    monkeypatch.setattr(ci_lanes.platform, "system", lambda: "Darwin")
    receipt_dir = tmp_path / "receipt"
    code = ci_lanes.run_lane(
        _args("macos-keychain", receipt_dir, keychain_target=["unknown_provider"])
    )
    assert code == ci_lanes.EXIT_NOT_DISPATCHED
    assert len(calls) == 1
    receipt = _read_receipt(receipt_dir)
    assert receipt["unknown_target_count"] == 1
    assert receipt["keychain_targets"] == []
    assert "unknown_provider" not in json.dumps(receipt)


def test_keychain_check_does_not_echo_unknown_target(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(ci_lanes.platform, "system", lambda: "Darwin")
    args = _args(
        "macos-keychain",
        Path("unused"),
        keychain_target=["unknown_provider"],
    )
    assert ci_lanes.check_lane(args) == ci_lanes.EXIT_NOT_DISPATCHED
    output = capsys.readouterr().out
    assert "unknown_provider" not in output
    assert json.loads(output)["unknown_target_count"] == 1


def test_missing_key_is_not_dispatched_and_check_output_is_discarded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = _fake_head_then(monkeypatch, [1])
    monkeypatch.setattr(ci_lanes.platform, "system", lambda: "Darwin")
    receipt_dir = tmp_path / "receipt"
    code = ci_lanes.run_lane(
        _args("macos-keychain", receipt_dir, keychain_target=["deepseek_official"])
    )
    assert code == ci_lanes.EXIT_NOT_DISPATCHED
    assert calls[1]["stdout"] is subprocess.DEVNULL
    assert calls[1]["stderr"] is subprocess.DEVNULL
    receipt_text = (receipt_dir / "receipt.json").read_text(encoding="utf-8")
    assert str(ci_lanes.ROOT) not in receipt_text
    assert "missing_targets" in receipt_text


def test_present_keys_then_run_only_fixed_keychain_pytest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = _fake_head_then(monkeypatch, [0, 0, 0])
    monkeypatch.setattr(ci_lanes.platform, "system", lambda: "Darwin")
    receipt_dir = tmp_path / "receipt"
    code = ci_lanes.run_lane(
        _args(
            "macos-keychain",
            receipt_dir,
            keychain_target=["volcengine_ark", "deepseek_official"],
        )
    )
    assert code == 0
    assert calls[-1]["argv"] == [
        "uv", "run", "--locked", "pytest", "-q", "--ci-lane", "macos-keychain"
    ]


def test_local_missing_material_is_relative_and_not_dispatched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "governance").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "tests/local_evidence_registry.json").write_text(
        json.dumps(
            {
                "schema_version": "pytest-local-evidence-v1",
                "groups": [
                    {
                        "group_id": "G-1",
                        "required_paths": ["local/private-fixture.json"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ci_lanes, "ROOT", repo)
    monkeypatch.setattr(ci_lanes, "LOCAL_REGISTRY_PATH", repo / "tests/local_evidence_registry.json")
    calls = _fake_head_then(monkeypatch, [])
    receipt_dir = tmp_path / "receipt"
    code = ci_lanes.run_lane(_args("local-evidence", receipt_dir, group=["G-1"]))
    assert code == ci_lanes.EXIT_NOT_DISPATCHED
    assert len(calls) == 1
    receipt = _read_receipt(receipt_dir)
    assert receipt["missing_paths"] == ["local/private-fixture.json"]
    assert str(repo) not in json.dumps(receipt)


def test_local_check_reports_missing_without_starting_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests/local_evidence_registry.json").write_text(
        json.dumps(
            {
                "schema_version": "pytest-local-evidence-v1",
                "groups": [
                    {"group_id": "G-1", "required_paths": ["fixtures/a.json"]}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ci_lanes, "ROOT", repo)
    monkeypatch.setattr(
        ci_lanes,
        "LOCAL_REGISTRY_PATH",
        repo / "tests/local_evidence_registry.json",
    )
    monkeypatch.setattr(
        ci_lanes.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("check 不得启动子进程"),
    )
    code = ci_lanes.check_lane(_args("local-evidence", Path("unused")))
    payload = json.loads(capsys.readouterr().out)
    assert code == ci_lanes.EXIT_NOT_DISPATCHED
    assert payload["missing_paths"] == ["fixtures/a.json"]


def test_local_unknown_group_is_counted_without_echo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests/local_evidence_registry.json").write_text(
        json.dumps(
            {
                "schema_version": "pytest-local-evidence-v1",
                "groups": [
                    {"group_id": "KNOWN", "required_paths": ["fixtures/a.json"]}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ci_lanes, "ROOT", repo)
    monkeypatch.setattr(
        ci_lanes,
        "LOCAL_REGISTRY_PATH",
        repo / "tests/local_evidence_registry.json",
    )
    args = _args(
        "local-evidence",
        Path("unused"),
        group=["KNOWN", "free-form-unknown"],
    )
    assert ci_lanes.check_lane(args) == ci_lanes.EXIT_NOT_DISPATCHED
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["group_ids"] == ["KNOWN"]
    assert payload["unknown_group_count"] == 1
    assert "free-form-unknown" not in output


def test_local_defaults_to_all_groups_and_passes_each_group_to_pytest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    for relative in ("fixtures/a.json", "fixtures/b.json"):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")
    (repo / "tests/local_evidence_registry.json").write_text(
        json.dumps(
            {
                "schema_version": "pytest-local-evidence-v1",
                "groups": [
                    {"group_id": "A", "required_paths": ["fixtures/a.json"]},
                    {"group_id": "B", "required_paths": ["fixtures/b.json"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ci_lanes, "ROOT", repo)
    monkeypatch.setattr(ci_lanes, "LOCAL_REGISTRY_PATH", repo / "tests/local_evidence_registry.json")
    calls = _fake_head_then(monkeypatch, [0])
    receipt_dir = tmp_path / "receipt"
    assert ci_lanes.run_lane(_args("local-evidence", receipt_dir)) == 0
    assert calls[-1]["argv"][-4:] == ["--local-evidence-group", "A", "--local-evidence-group", "B"]
    assert calls[-1]["env"]["NOVEL_RUN_LOCAL_EVIDENCE_TESTS"] == "1"


def test_historical_invalid_commit_hard_stops_without_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = _fake_head_then(monkeypatch, [])
    receipt_dir = tmp_path / "receipt"
    code = ci_lanes.run_lane(
        _args("historical-replay", receipt_dir, commit="short", run_id="fresh-run")
    )
    assert code == ci_lanes.EXIT_HARD_STOP
    assert len(calls) == 1
    assert _read_receipt(receipt_dir)["status"] == "HARD_STOP"


def test_historical_validate_then_reuses_fixed_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = _fake_head_then(monkeypatch, [0, 0])
    receipt_dir = tmp_path / "receipt"
    commit = "b" * 40
    code = ci_lanes.run_lane(
        _args("historical-replay", receipt_dir, commit=commit, run_id="fresh-run")
    )
    assert code == 0
    assert calls[1]["argv"][-2:] == ["tools/historical_test_replay.py", "validate"]
    assert calls[2]["argv"][-6:] == [
        "tools/historical_test_replay.py", "run", "--commit", commit, "--run-id", "fresh-run"
    ]


def test_historical_validation_failure_is_hard_stop_not_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _fake_head_then(monkeypatch, [2])
    receipt_dir = tmp_path / "receipt"
    code = ci_lanes.run_lane(
        _args("historical-replay", receipt_dir, commit="c" * 40, run_id="fresh-run")
    )
    assert code == 2
    assert _read_receipt(receipt_dir)["status"] == "HARD_STOP"


def test_receipt_directory_is_create_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    monkeypatch.setattr(
        ci_lanes.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("旧回执目录不得启动命令"),
    )
    with pytest.raises(ci_lanes.LaneError, match="已存在"):
        ci_lanes.run_lane(_args("main-portable", existing))


def test_parser_exposes_no_free_command_cwd_or_material_root() -> None:
    help_text = ci_lanes.build_parser().format_help()
    assert "--command" not in help_text
    assert "--cwd" not in help_text
    assert "--material-root" not in help_text
    source = (ROOT / "tools/ci_lanes.py").read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "eval(" not in source
    assert "requests" not in source
    assert "upload" not in source.lower()


def test_main_workflow_runs_only_on_main_and_uploads_only_light_receipts() -> None:
    workflow_path = ROOT / ".github/workflows/main-portable-full.yml"
    raw = workflow_path.read_text(encoding="utf-8")
    assert "\non:\n  push:\n    branches:\n      - main\n  workflow_dispatch:\n" in raw
    assert "pull_request:" not in raw
    assert "    if: github.ref == 'refs/heads/main'\n" in raw
    assert "    runs-on: ubuntu-24.04\n" in raw
    uses = re.findall(r"^\s+uses: (\S+)", raw, flags=re.MULTILINE)
    assert uses == [
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d",
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    ]
    assert "tools/ci_lanes.py run" in raw
    assert "--lane main-portable" in raw
    assert "${{ runner.temp }}/main-portable-full" in raw
    assert "secrets." not in raw
    assert "corpus-downloads" not in raw
    assert "NOVEL_RUN_LOCAL_EVIDENCE_TESTS" not in raw


def test_ci_lane_paths_are_full_chain_and_routed_to_lane_tests() -> None:
    policy = json.loads(
        (ROOT / "governance/test_policy.json").read_text(encoding="utf-8")
    )
    rules = {row["pattern"]: row for row in policy["path_rules"]}
    for pattern in (
        ".github/workflows/main-portable-full.yml",
        "governance/ci_lanes.json",
        "tools/ci_lanes.py",
        "tests/test_isolation.py",
        "tests/test_repository_layout.py",
        "tests/test_ci_lanes.py",
    ):
        assert rules[pattern]["full_chain"] is True
        assert "tests/test_ci_lanes.py" in rules[pattern]["tests"]

from __future__ import annotations

import builtins
import copy
import hashlib
import io
import json
import os
import shutil
import socket
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

from tools.pipeline_common import repository_catalog as catalog


ROOT = Path(__file__).resolve().parents[1]
VIEWS = ("menu", "status", "models", "experiments", "artifacts", "slim", "all")
DATA_VIEWS = ("menu", "status", "models", "experiments", "artifacts", "slim")
CATALOG_VERSION = "repository-catalog-view-v1"
PROTECTED_R02_ID = "cmin-b-refreeze-20260730-r02"
PROTECTED_R02_PATH = "TEMP/CMIN-B-REFREEZE-20260730-R02"
STATE_LABEL_A = "fixture-current-state-A"
STATE_LABEL_B = "fixture-current-state-B"
EXPERIMENT_ID = "fixture-registered-experiment"
UNREGISTERED_CARD_ID = "fixture-unlisted-card"
UNREGISTERED_CANARY = "UNLISTED_CARD_MUST_NOT_BE_READ_OR_SHOWN"
BARE_DIRECTORY_CANARY = "BARE_EXPERIMENT_DIRECTORY_IS_NOT_A_CONCLUSION"
PAYLOAD_CANARY = "PAYLOAD_BYTES_MUST_NOT_BE_READ_OR_SHOWN"
SECRET_CANARY = "CATALOG_TEST_API_KEY_MUST_STAY_UNREAD"
ABSOLUTE_PATH_CANARY = "/Volumes/catalog-test-secret/external-object"


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    assert isinstance(value, dict)
    return value


def _copy_file(repo: Path, relative: str) -> Path:
    destination = repo / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, destination)
    return destination


def _walk(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _strings(value: object) -> list[str]:
    return [item for item in _walk(value) if isinstance(item, str)]


def _matching_rows(value: object, key: str, expected: object) -> list[dict[str, Any]]:
    return [
        item
        for item in _walk(value)
        if isinstance(item, dict) and item.get(key) == expected
    ]


def _source_paths(document: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for source in document["sources"]:
        if isinstance(source, str):
            paths.append(source)
        elif isinstance(source, dict) and isinstance(source.get("path"), str):
            paths.append(source["path"])
        else:
            raise AssertionError(f"无法识别的 catalog 来源项：{source!r}")
    return paths


@dataclass(frozen=True)
class CatalogFixture:
    repo: Path
    external: Path
    current_state: Path
    model_registry: Path
    retrieval_policy: Path
    external_registry: Path
    unregistered_card: Path
    bare_directory_file: Path
    payload_file: Path


def _make_fixture(tmp_path: Path) -> CatalogFixture:
    repo = tmp_path / "repo"
    external = tmp_path / "repo_外置仓"
    repo.mkdir()
    external.mkdir()

    current_state = _copy_file(repo, "governance/CURRENT_STATE.json")
    state = _read_json(current_state)
    state["current_execution"]["task"]["task_id"] = "FIXTURE-CURRENT-TASK"
    state["current_execution"]["task"]["label"] = STATE_LABEL_A
    _write_json(current_state, state)

    model_registry = _copy_file(repo, "config/model_call_profiles/registry.json")
    for relative in (
        "governance/module_registry.json",
        "governance/route_registry.json",
        "governance/tool_registry.json",
    ):
        _copy_file(repo, relative)

    experiment_dir = repo / "experiments" / EXPERIMENT_ID
    experiment = _read_json(
        ROOT / "experiments/Z76_phase2_semantic_inspector_pilot_20260721/experiment.json"
    )
    experiment["experiment_id"] = EXPERIMENT_ID
    experiment["status"] = "complete"
    experiment["summary"] = "完整试验只证明候选结果，不产正式真值。"
    _write_json(experiment_dir / "experiment.json", experiment)

    bare_directory_file = (
        repo / "experiments" / "fixture-bare-directory" / "formal_result.json"
    )
    _write_json(
        bare_directory_file,
        {
            "quality_verdict": "passed",
            "canary": BARE_DIRECTORY_CANARY,
        },
    )

    retrieval_policy = _copy_file(
        repo,
        "governance/artifact_retrieval_policy.json",
    )
    external_registry = _copy_file(
        repo,
        "governance/external_archive_registry.json",
    )
    registry = _read_json(external_registry)
    experiment_object = copy.deepcopy(
        next(
            row
            for row in registry["objects"]
            if row["category"] == "repository_experiment"
        )
    )
    experiment_object.update(
        {
            "artifact_id": EXPERIMENT_ID,
            "relative_path": f"experiments/{EXPERIMENT_ID}",
            "status": "complete",
            "lifecycle": "candidate",
            "purpose_summary": "登记对象只说明候选用途，不是正式结论。",
        }
    )
    registry["objects"].append(experiment_object)
    _write_json(external_registry, registry)
    for card_row in _read_json(retrieval_policy)["cards"]:
        card_id = card_row["card_id"]
        source = ROOT / "config/test_replay/result_cards" / card_id
        destination = repo / "config/test_replay/result_cards" / card_id
        shutil.copytree(source, destination)

    unregistered_card = (
        repo
        / "config/test_replay/result_cards"
        / UNREGISTERED_CARD_ID
        / "result_card.json"
    )
    _write_json(
        unregistered_card,
        {
            "contract_version": "experiment-result-card-v1",
            "card_id": UNREGISTERED_CARD_ID,
            "experiment_id": "FIXTURE-UNLISTED",
            "terminal_status": "completed",
            "quality_verdict": "passed",
            "short_conclusion": [UNREGISTERED_CANARY],
        },
    )

    payload_file = (
        external
        / "fixture-artifact"
        / "payload"
        / "must-not-read.txt"
    )
    payload_file.parent.mkdir(parents=True)
    payload_file.write_text(PAYLOAD_CANARY, encoding="utf-8")

    return CatalogFixture(
        repo=repo,
        external=external,
        current_state=current_state,
        model_registry=model_registry,
        retrieval_policy=retrieval_policy,
        external_registry=external_registry,
        unregistered_card=unregistered_card,
        bare_directory_file=bare_directory_file,
        payload_file=payload_file,
    )


def _assert_top_level(document: dict[str, Any], view: str) -> None:
    assert set(document) == {
        "catalog_version",
        "view",
        "authority",
        "sources",
        "data",
    }
    assert document["catalog_version"] == CATALOG_VERSION
    assert document["view"] == view
    assert document["authority"] == {
        "mode": "derived_read_only_view",
        "defines_current_state": False,
        "writes": False,
        "reads_external_payload": False,
        "protected_discovery": False,
    }
    source_paths = _source_paths(document)
    assert source_paths == sorted(set(source_paths))
    assert all(not Path(path).is_absolute() for path in source_paths)


def test_component_layer_and_unified_entry_register_the_targeted_test() -> None:
    registry = _read_json(ROOT / "governance/tool_registry.json")
    component = next(
        row
        for row in registry["component_layers"]
        if row["path"] == "tools/pipeline_common/"
    )
    entry = next(row for row in registry["tools"] if row["tool_id"] == "TOOL-004")

    assert component["python_file_count"] == 4
    assert "tests/test_repository_catalog.py" in component["test_references"]
    assert "tests/test_repository_catalog.py" in entry["test_references"]
    assert "catalog" in entry["human_command"]


def test_each_view_has_fixed_contract_and_deterministic_data(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)

    for view in VIEWS:
        first = catalog.build_catalog(fixture.repo, view)
        second = catalog.build_catalog(fixture.repo, view)
        _assert_top_level(first, view)
        assert first == second
        assert _json_bytes(first) == _json_bytes(second)


def test_all_is_composed_from_the_same_read_only_views(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)

    separate = {
        view: catalog.build_catalog(fixture.repo, view)["data"]
        for view in DATA_VIEWS
    }
    combined = catalog.build_catalog(fixture.repo, "all")

    assert set(combined["data"]) == set(DATA_VIEWS)
    assert combined["data"] == separate


def test_status_reads_current_state_instead_of_freezing_a_second_copy(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    first = catalog.build_catalog(fixture.repo, "status")
    assert STATE_LABEL_A in _strings(first["data"])

    state = _read_json(fixture.current_state)
    state["current_execution"]["task"]["label"] = STATE_LABEL_B
    _write_json(fixture.current_state, state)
    second = catalog.build_catalog(fixture.repo, "status")

    assert STATE_LABEL_B in _strings(second["data"])
    assert STATE_LABEL_A not in _strings(second["data"])
    assert first != second
    assert not any(
        path.name.startswith(("catalog", "repository_catalog"))
        for path in fixture.repo.rglob("*")
        if path.is_file()
    )


def test_candidate_models_never_become_default_by_entering_preferred_profiles(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    document = catalog.build_catalog(fixture.repo, "models")
    serialized = json.dumps(document["data"], ensure_ascii=False, sort_keys=True)

    assert "candidate_only_not_wired_to_default_chain" in serialized
    assert "wave2_synthetic_json_probe_v1" in serialized
    assert '"default": true' not in serialized
    assert '"is_default": true' not in serialized
    assert '"wired_to_default_chain": true' not in serialized
    rows = _matching_rows(
        document["data"],
        "bundle_id",
        "wave2_synthetic_json_probe_v1",
    )
    assert rows
    assert all(
        value is not True
        for row in rows
        for key, value in row.items()
        if "default" in key
    )


def test_models_human_view_distinguishes_profiles_from_rule_bundles(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    document = catalog.build_catalog(fixture.repo, "models")

    rendered = catalog._render_human(document)

    assert "模型调用档：5 个" in rendered
    assert "已登记规则组装包：1 个" in rendered
    assert "其余 4 个未登记完整包" in rendered
    assert "完整组装包：1 个" not in rendered


def test_models_status_follows_registry_instead_of_freezing_candidate_state(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    registry = _read_json(fixture.model_registry)
    registry["status"] = "fixture_future_registry_status"
    for bundle in registry["rule_bundles"]:
        bundle["status"] = "fixture_future_registry_status"
    _write_json(fixture.model_registry, registry)

    document = catalog.build_catalog(fixture.repo, "models")

    assert document["data"]["registry_status"] == "fixture_future_registry_status"
    assert document["data"]["catalog_may_define_default_chain"] is False
    assert "candidate_only_not_wired_to_default_chain" not in _strings(
        document["data"]
    )
    assert "登记状态：fixture_future_registry_status" in catalog._render_human(
        document
    )


def test_experiment_registration_does_not_claim_a_formal_conclusion(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    document = catalog.build_catalog(fixture.repo, "experiments")
    strings = _strings(document["data"])

    assert EXPERIMENT_ID in strings
    assert BARE_DIRECTORY_CANARY not in strings
    rows = _matching_rows(document["data"], "artifact_id", EXPERIMENT_ID)
    assert rows
    for row in rows:
        assert row.get("formal_conclusion") is not True
        assert row.get("quality_verdict") not in {"passed", "formal_pass"}


def _guard_forbidden_reads(
    monkeypatch: pytest.MonkeyPatch,
    forbidden: set[Path],
) -> None:
    normalized = {path.absolute() for path in forbidden}

    def is_forbidden(path: object) -> bool:
        if isinstance(path, int):
            return False
        try:
            candidate = Path(path).absolute()
        except TypeError:
            return False
        return candidate in normalized

    original_open = Path.open
    original_read_text = Path.read_text
    original_read_bytes = Path.read_bytes
    original_os_open = os.open
    forbidden_markers = {
        path.parent.name if path.name == "result_card.json" else path.name
        for path in forbidden
    }

    def guarded_open(self: Path, *args: object, **kwargs: object) -> Any:
        assert not is_forbidden(self), f"禁止读取：{self}"
        return original_open(self, *args, **kwargs)

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        assert not is_forbidden(self), f"禁止读取：{self}"
        return original_read_text(self, *args, **kwargs)

    def guarded_read_bytes(self: Path, *args: object, **kwargs: object) -> bytes:
        assert not is_forbidden(self), f"禁止读取：{self}"
        return original_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)

    def guarded_os_open(path: object, *args: object, **kwargs: object) -> int:
        text = os.fspath(path) if isinstance(path, (str, os.PathLike)) else str(path)
        assert not any(marker in text for marker in forbidden_markers), (
            f"禁止读取：{text}"
        )
        return original_os_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", guarded_os_open)


def test_only_policy_cards_are_readable_and_visible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    _guard_forbidden_reads(
        monkeypatch,
        {
            fixture.unregistered_card,
            fixture.bare_directory_file,
            fixture.payload_file,
        },
    )

    document = catalog.build_catalog(fixture.repo, "artifacts")
    strings = _strings(document["data"])
    allowed = {
        row["card_id"]
        for row in _read_json(fixture.retrieval_policy)["cards"]
    }

    assert allowed <= set(strings)
    assert UNREGISTERED_CARD_ID not in strings
    assert UNREGISTERED_CANARY not in strings
    assert PAYLOAD_CANARY not in strings


def _inject_protected_r02(fixture: CatalogFixture) -> None:
    policy = _read_json(fixture.retrieval_policy)
    policy["cards"].append(
        {
            "card_id": PROTECTED_R02_ID,
            "result_card_ref": {
                "path": f"{PROTECTED_R02_PATH}/result_card.json",
                "sha256": "0" * 64,
            },
            "allowed_selection_ids": ["must-never-be-resolved"],
        }
    )
    _write_json(fixture.retrieval_policy, policy)

    registry = _read_json(fixture.external_registry)
    protected = copy.deepcopy(registry["objects"][0])
    protected["artifact_id"] = PROTECTED_R02_ID
    protected["relative_path"] = "CMIN-B-REFREEZE-20260730-R02"
    protected["purpose_summary"] = ABSOLUTE_PATH_CANARY
    registry["objects"].append(protected)
    _write_json(fixture.external_registry, registry)


def _guard_r02_filesystem_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    observed: list[str] = []

    def has_r02(value: object) -> bool:
        text = os.fspath(value) if isinstance(value, (str, os.PathLike)) else str(value)
        return "CMIN-B-REFREEZE-20260730-R02" in text

    def wrap_method(
        name: str,
        original: Callable[..., Any],
    ) -> Callable[..., Any]:
        def guarded(self: Path, *args: object, **kwargs: object) -> Any:
            values = (self, *args)
            if any(has_r02(value) for value in values):
                observed.append(f"{name}:{values!r}")
                raise AssertionError(f"R02 不得进入 {name}：{values!r}")
            return original(self, *args, **kwargs)

        return guarded

    for name in (
        "open",
        "read_text",
        "read_bytes",
        "stat",
        "exists",
        "is_file",
        "is_dir",
        "glob",
        "rglob",
        "iterdir",
    ):
        monkeypatch.setattr(
            Path,
            name,
            wrap_method(name, getattr(Path, name)),
        )

    original_builtin_open = builtins.open
    original_io_open = io.open

    def guarded_builtin_open(file: object, *args: object, **kwargs: object) -> Any:
        if has_r02(file):
            observed.append(f"builtins.open:{file!r}")
            raise AssertionError(f"R02 不得进入 open：{file!r}")
        return original_builtin_open(file, *args, **kwargs)

    def guarded_io_open(file: object, *args: object, **kwargs: object) -> Any:
        if has_r02(file):
            observed.append(f"io.open:{file!r}")
            raise AssertionError(f"R02 不得进入 io.open：{file!r}")
        return original_io_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_builtin_open)
    monkeypatch.setattr(io, "open", guarded_io_open)

    for name in ("open", "stat", "lstat", "scandir", "listdir"):
        original = getattr(os, name)

        def guarded_os(
            path: object,
            *args: object,
            _name: str = name,
            _original: Callable[..., Any] = original,
            **kwargs: object,
        ) -> Any:
            if has_r02(path):
                observed.append(f"os.{_name}:{path!r}")
                raise AssertionError(f"R02 不得进入 os.{_name}：{path!r}")
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(os, name, guarded_os)
    return observed


def test_r02_is_filtered_before_read_stat_exists_or_glob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    _inject_protected_r02(fixture)
    assert "TEMP" not in {path.name for path in fixture.repo.iterdir()}
    observed = _guard_r02_filesystem_operations(monkeypatch)

    def reject_scanner_start(_repo_root: Path) -> Any:
        raise AssertionError("登记撞到受保护对象后不得启动瘦身扫描器")

    monkeypatch.setattr(
        catalog,
        "scan_with_git_index_details",
        reject_scanner_start,
    )
    document = catalog.build_catalog(fixture.repo, "all")
    serialized = json.dumps(document, ensure_ascii=False, sort_keys=True)

    assert observed == []
    assert f"{PROTECTED_R02_PATH}/result_card.json" not in serialized
    assert ABSOLUTE_PATH_CANARY not in serialized
    assert any(
        row.get("blocked_protected_card_ref_count") == 1
        for row in _walk(document["data"])
        if isinstance(row, dict)
    )
    assert any(
        isinstance(row.get("protected_object_excluded_count"), int)
        and row["protected_object_excluded_count"] >= 1
        for row in _walk(document["data"])
        if isinstance(row, dict)
    )
    assert document["data"]["slim"]["available"] is False
    assert (
        document["data"]["slim"]["error"]["code"]
        == "PROTECTED_NON_TARGET_REGISTERED"
    )


def test_slim_success_uses_one_git_snapshot_and_separates_both_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    observed = _guard_r02_filesystem_operations(monkeypatch)
    calls: list[Path] = []

    def synthetic_scan(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        calls.append(repo_root)
        return (
            {
                "status": "PASS",
                "claim": {
                    "inventory_complete_for_registered_objects": True,
                    "external_payload_verified": False,
                    "recoverability_proven": False,
                    "migration_performed": False,
                },
                "git_inventory": {
                    "tracked_path_count": 3,
                    "tracked_bytes": 12_000_000,
                    "active_limit_bytes": 12_000_000,
                    "active_gate": "s06a_bootstrap_no_growth",
                    "active_gate_passed": True,
                    "target_bytes": 10_000_000,
                    "target_met": False,
                },
                "conflicts": {"known_open_ids": []},
                "blockers": [],
            },
            {
                "tracked_path_count": 3,
                "tracked_bytes": 12_000_000,
                "entries": [
                    {
                        "path": "experiments/model_benchmarks/a.json",
                        "bytes": 6_000_000,
                    },
                    {"path": "tools/a.py", "bytes": 4_500_000},
                    {"path": "tests/test_a.py", "bytes": 1_500_000},
                ],
            },
        )

    monkeypatch.setattr(
        catalog,
        "scan_with_git_index_details",
        synthetic_scan,
    )

    data = catalog.build_catalog(fixture.repo, "slim")["data"]

    assert calls == [fixture.repo]
    assert observed == []
    assert data["available"] is True
    assert data["tracked_bytes"] == 12_000_000
    assert data["active_gate_passed"] is True
    assert data["target_met"] is False
    assert data["bytes_to_target"] == 2_000_000
    assert sum(row["tracked_bytes"] for row in data["top_level"]) == 12_000_000


def test_slim_rejects_protected_nested_anchor_before_starting_scanner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    registry = _read_json(fixture.external_registry)
    nested = copy.deepcopy(registry["objects"][0])
    nested["artifact_id"] = "fixture-nested-protected-anchor"
    nested["identity_anchors"] = [
        {
            "relative_path": f"{PROTECTED_R02_PATH}/anchor.json",
            "sha256": "0" * 64,
        }
    ]
    registry["objects"].append(nested)
    _write_json(fixture.external_registry, registry)
    observed = _guard_r02_filesystem_operations(monkeypatch)

    def reject_scanner_start(_repo_root: Path) -> Any:
        raise AssertionError("嵌套身份锚撞到受保护对象后不得启动扫描器")

    monkeypatch.setattr(
        catalog,
        "scan_with_git_index_details",
        reject_scanner_start,
    )

    data = catalog.build_catalog(fixture.repo, "slim")["data"]

    assert observed == []
    assert data["available"] is False
    assert data["error"]["code"] == "PROTECTED_NON_TARGET_REGISTERED"
    assert data["protected_reference_excluded_count"] == 1


def test_output_has_no_external_absolute_path_secret_or_payload_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    monkeypatch.setenv("CATALOG_TEST_API_KEY", SECRET_CANARY)

    document = catalog.build_catalog(fixture.repo, "all")
    serialized = json.dumps(document, ensure_ascii=False, sort_keys=True)

    assert str(fixture.repo) not in serialized
    assert str(fixture.external) not in serialized
    assert ABSOLUTE_PATH_CANARY not in serialized
    assert SECRET_CANARY not in serialized
    assert PAYLOAD_CANARY not in serialized
    assert UNREGISTERED_CANARY not in serialized
    for value in _strings(document):
        assert not value.startswith("/")


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_catalog_does_not_write_or_open_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    before = _snapshot(tmp_path)

    def reject_network(*_args: object, **_kwargs: object) -> Any:
        raise AssertionError("catalog 不得联网")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(urllib.request, "urlopen", reject_network)

    original_builtin_open = builtins.open
    original_io_open = io.open

    def reject_fixture_write(
        original: Callable[..., Any],
    ) -> Callable[..., Any]:
        def guarded(
            file: object,
            mode: str = "r",
            *args: object,
            **kwargs: object,
        ) -> Any:
            try:
                inside = Path(file).absolute().is_relative_to(tmp_path.absolute())
            except TypeError:
                inside = False
            if inside and any(flag in mode for flag in "wax+"):
                raise AssertionError(f"catalog 不得写文件：{file!r} mode={mode!r}")
            return original(file, mode, *args, **kwargs)

        return guarded

    monkeypatch.setattr(
        builtins,
        "open",
        reject_fixture_write(original_builtin_open),
    )
    monkeypatch.setattr(io, "open", reject_fixture_write(original_io_open))

    for view in VIEWS:
        catalog.build_catalog(fixture.repo, view)

    assert _snapshot(tmp_path) == before


def test_slim_failure_is_current_and_never_filled_from_cache(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)

    slim = catalog.build_catalog(fixture.repo, "slim")
    combined = catalog.build_catalog(fixture.repo, "all")

    assert slim["data"]["available"] is False
    assert isinstance(slim["data"]["error"], dict)
    assert slim["data"]["error"]["code"]
    assert slim["data"]["error"]["message"]
    assert slim["data"]["stale_pass_fallback_used"] is False
    assert combined["data"]["slim"] == slim["data"]


def test_cli_json_is_byte_deterministic_and_defaults_to_menu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _make_fixture(tmp_path)
    monkeypatch.setattr(catalog, "ROOT", fixture.repo)

    assert catalog.main(["models", "--json"]) == 0
    first = capsys.readouterr()
    assert first.err == ""
    assert catalog.main(["models", "--json"]) == 0
    second = capsys.readouterr()
    assert second.err == ""
    assert first.out == second.out
    assert json.loads(first.out)["view"] == "models"

    assert catalog.main(["--json"]) == 0
    default_output = capsys.readouterr()
    assert default_output.err == ""
    assert json.loads(default_output.out)["view"] == "menu"


@pytest.mark.parametrize(
    "option",
    (
        "--root",
        "--path",
        "--glob",
        "--destination",
        "--copy",
        "--move",
        "--delete",
    ),
)
def test_cli_rejects_arbitrary_path_and_mutation_options(
    option: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    monkeypatch.setattr(catalog, "ROOT", fixture.repo)

    with pytest.raises(SystemExit) as exc_info:
        catalog.main(["menu", option, "forbidden"])

    assert exc_info.value.code == 2


@pytest.mark.parametrize("command", ("copy", "move", "delete"))
def test_cli_has_no_mutating_commands(command: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        catalog.main([command])

    assert exc_info.value.code == 2

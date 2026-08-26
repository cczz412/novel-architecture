from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from isolation import run_git
from tools import governance_index


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / governance_index.DIRECTORY_REGISTRY_PATH
SCHEMA_PATH = ROOT / governance_index.DIRECTORY_REGISTRY_SCHEMA_PATH
LOCAL_DIRECTORY_EVIDENCE_REFS = {".workbuddy/memory/2026-08-03.md"}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return run_git(*args, cwd=ROOT, check=check)


def _tracked_paths() -> set[str]:
    raw = _git("ls-files", "-z").stdout
    try:
        decoded = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        pytest.fail(f"Git 跟踪路径必须是 UTF-8：{exc}")
    return {item for item in decoded.split("\0") if item}


def _has_tracked_path(tracked: set[str], path: str) -> bool:
    return path in tracked or any(item.startswith(f"{path}/") for item in tracked)


def _portable_directory_contract_root(tmp_path: Path, registry: dict) -> Path:
    contract_root = tmp_path / "portable-directory-contract"
    schema_target = contract_root / governance_index.DIRECTORY_REGISTRY_SCHEMA_PATH
    schema_target.parent.mkdir(parents=True)
    schema_target.write_bytes(SCHEMA_PATH.read_bytes())

    for row in registry["directories"]:
        for relative in row["evidence_refs"]:
            source = ROOT / relative
            if relative not in LOCAL_DIRECTORY_EVIDENCE_REFS:
                assert source.is_file(), relative
            target = contract_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("portable evidence placeholder\n", encoding="utf-8")
    return contract_root


def _assert_temporary_refresh_does_not_modify_current_state() -> None:
    current_state = ROOT / governance_index.CURRENT_STATE_PATH
    before = current_state.read_bytes()
    before_sha = hashlib.sha256(before).hexdigest()

    with tempfile.TemporaryDirectory() as temporary:
        manifest = governance_index.refresh(ROOT, Path(temporary))

    after = current_state.read_bytes()
    assert hashlib.sha256(after).hexdigest() == before_sha
    assert after == before
    assert governance_index.DIRECTORY_REGISTRY_PATH in {
        item["path"] for item in manifest["inputs"]
    }
    assert governance_index.DIRECTORY_REGISTRY_SCHEMA_PATH in {
        item["path"] for item in manifest["inputs"]
    }
    outputs = {item["path"] for item in manifest["outputs"]}
    assert "governance/indexes/directory_map.md" in outputs
    assert "governance/indexes/new_file_routing.md" in outputs


def test_directory_registry_matches_schema_and_runtime_contract() -> None:
    schema = _read_json(SCHEMA_PATH)
    registry = _read_json(REGISTRY_PATH)

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(registry)
    governance_index.validate_directory_registry(ROOT, registry)


def test_directory_registry_portable_contract_survives_missing_local_evidence(
    tmp_path: Path,
) -> None:
    registry = _read_json(REGISTRY_PATH)
    contract_root = _portable_directory_contract_root(tmp_path, registry)

    governance_index.validate_directory_registry(contract_root, registry)


def test_directory_registry_rejects_unknown_business_state_fields() -> None:
    schema = _read_json(SCHEMA_PATH)
    registry = _read_json(REGISTRY_PATH)
    broken = copy.deepcopy(registry)
    broken["directories"][0]["active_task"] = "不得进入目录身份账"

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(broken)
    with pytest.raises(
        governance_index.ArtifactError,
        match="不符合正式 schema",
    ):
        governance_index.validate_directory_registry(ROOT, broken)


@pytest.mark.parametrize("unsafe", ["含空字节\u0000", "含代理字符\ud800"])
def test_directory_registry_rejects_unsafe_generated_text(unsafe: str) -> None:
    registry = _read_json(REGISTRY_PATH)
    registry["directories"][0]["new_content_rule"] = unsafe

    with pytest.raises(
        governance_index.ArtifactError,
        match="控制字符|无法写成 UTF-8",
    ):
        governance_index.validate_directory_registry(ROOT, registry)


def test_directory_identities_and_new_file_objects_are_unique() -> None:
    registry = _read_json(REGISTRY_PATH)
    rows = registry["directories"]

    for key in ("directory_id", "path", "identity"):
        values = [row[key] for row in rows]
        assert len(values) == len(set(values)), key
    object_ids = [
        item["object_id"]
        for row in rows
        for item in row["accepted_content"]
    ]
    assert len(object_ids) == len(set(object_ids))
    assert all(row["inherit_to_children"] is False for row in rows)


def test_registered_top_level_scope_is_exact_and_creates_no_nvm_style_layers() -> None:
    registry = _read_json(REGISTRY_PATH)
    registered = {row["path"] for row in registry["directories"]}
    assert registered == {
        ".agents",
        ".cursor",
        ".github",
        ".local",
        ".workbuddy",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "TEMP",
        "analysis_library",
        "config",
        "corpus-downloads",
        "experiments",
        "finetuning",
        "foundation",
        "governance",
        "history",
        "intake",
        "novel-mvp",
        "outbox",
        "references",
        "reports",
        "runs",
        "schemas",
        "seed",
        "side-tracks",
        "tests",
        "tools",
        "work",
    }
    actual_top_level = {
        path.name
        for path in ROOT.iterdir()
        if path.name != ".git" and (path.is_dir() or path.is_symlink())
    }
    assert actual_top_level <= registered
    tracked_top_level = {
        item.split("/", 1)[0]
        for item in _tracked_paths()
        if "/" in item or (ROOT / item).is_dir() or (ROOT / item).is_symlink()
    }
    assert tracked_top_level <= registered
    for forbidden in ("active", "staging", "frozen", "runtime"):
        assert forbidden not in registered
        assert not (ROOT / forbidden).exists()


def test_git_policy_matches_repository_facts_with_nul_safe_listing() -> None:
    registry = _read_json(REGISTRY_PATH)
    tracked = _tracked_paths()

    for row in registry["directories"]:
        path = row["path"]
        policy = row["git_policy"]
        is_tracked = _has_tracked_path(tracked, path)
        if policy == "tracked":
            assert is_tracked, path
        elif policy == "ignored":
            probe = f"{path}/.gitignore-policy-probe"
            assert _git(
                "check-ignore",
                "--quiet",
                "--no-index",
                "--",
                probe,
                check=False,
            ).returncode == 0, probe
            assert not is_tracked, path
        elif policy == "mixed":
            assert is_tracked, path
            probe = row["ignored_probe"]
            assert _git(
                "check-ignore",
                "--quiet",
                "--no-index",
                "--",
                probe,
                check=False,
            ).returncode == 0, probe
        elif policy == "local_untracked":
            assert not is_tracked, path
            assert _git(
                "check-ignore",
                "--quiet",
                "--",
                path,
                check=False,
            ).returncode != 0, path
        elif policy == "tracked_pointer":
            assert path in tracked
            assert (ROOT / path).is_symlink()
        else:
            pytest.fail(f"未知 Git 规则：{path}={policy}")


def test_analysis_library_keeps_lightweight_index_and_ignores_heavy_payload() -> None:
    registry = _read_json(REGISTRY_PATH)
    row = next(
        item for item in registry["directories"] if item["path"] == "analysis_library"
    )
    assert row["git_policy"] == "mixed"
    assert row["ignored_probe"] == (
        "analysis_library/pilot_batch_01/raw_zips/payload-probe.zip"
    )

    lightweight_paths = {
        "analysis_library/README.md",
        "analysis_library/pilot_batch_01/README.md",
        "analysis_library/pilot_batch_01/EXTERNAL_POINTER.json",
        "analysis_library/pilot_batch_01/summaries/00_五本总览.md",
        "analysis_library/pilot_batch_01/summaries/01_书卡_逼我重生是吧.md",
        "analysis_library/pilot_batch_01/summaries/02_书卡_诡舍.md",
        "analysis_library/pilot_batch_01/summaries/03_书卡_斗破苍穹.md",
        "analysis_library/pilot_batch_01/summaries/04_书卡_封总太太想跟你离婚很久了.md",
        "analysis_library/pilot_batch_01/summaries/05_书卡_三国演义.md",
        "analysis_library/pilot_batch_01/summaries/06_字段合同摩擦汇总.md",
        "analysis_library/pilot_batch_01/acceptance/VALIDATION_REPORT.md",
        "analysis_library/pilot_batch_01/acceptance/book_summary.json",
        "analysis_library/pilot_batch_01/acceptance/缺包缺文件缺字段清单.md",
    }
    tracked = _tracked_paths()
    for path in lightweight_paths:
        assert (ROOT / path).is_file(), path
        assert path in tracked, path
        assert _git(
            "check-ignore",
            "--quiet",
            "--no-index",
            "--",
            path,
            check=False,
        ).returncode != 0, path

    for heavy_path in (
        row["ignored_probe"],
        "analysis_library/pilot_batch_01/unpacked/payload-probe.json",
        "analysis_library/pilot_batch_01/mappings/payload-probe.jsonl",
    ):
        assert _git(
            "check-ignore",
            "--quiet",
            "--no-index",
            "--",
            heavy_path,
            check=False,
        ).returncode == 0, heavy_path


def test_directory_views_are_generated_only_from_registry() -> None:
    registry = _read_json(REGISTRY_PATH)
    assert (
        ROOT / "governance/indexes/directory_map.md"
    ).read_text(encoding="utf-8") == governance_index.render_directory_map(registry)
    assert (
        ROOT / "governance/indexes/new_file_routing.md"
    ).read_text(encoding="utf-8") == governance_index.render_new_file_routing(registry)


def test_temporary_refresh_does_not_modify_current_state() -> None:
    _assert_temporary_refresh_does_not_modify_current_state()


def test_temporary_refresh_portable_path_does_not_modify_current_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    synthetic_root = tmp_path / "repo"
    output_root = tmp_path / "output"
    inputs = (
        governance_index.CONTROL_PATH,
        governance_index.CURRENT_STATE_PATH,
        governance_index.ROUTE_REGISTRY_PATH,
        governance_index.REGISTRY_SOURCE_PATH,
        governance_index.DIRECTORY_REGISTRY_PATH,
        governance_index.DIRECTORY_REGISTRY_SCHEMA_PATH,
        "tools/governance_index.py",
    )
    for relative in inputs:
        target = synthetic_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"sentinel":"keep"}\n', encoding="utf-8")

    current_state = synthetic_root / governance_index.CURRENT_STATE_PATH
    before = current_state.read_bytes()
    for name in (
        "validate_control_plane",
        "validate_current_state",
        "validate_route_registry",
        "validate_directory_registry",
    ):
        monkeypatch.setattr(governance_index, name, lambda *_args: None)
    registry = {
        "modules": [{"module_id": f"M{index:02d}"} for index in range(12)]
    }
    monkeypatch.setattr(
        governance_index,
        "materialize_registry",
        lambda *_args: registry,
    )
    monkeypatch.setattr(
        governance_index,
        "build_documents",
        lambda *_args: {
            "governance/indexes/directory_map.md": "map\n",
            "governance/indexes/new_file_routing.md": "routing\n",
        },
    )
    monkeypatch.setattr(
        governance_index,
        "build_manifest",
        lambda _root, paths: [{"path": path} for path in paths],
    )
    monkeypatch.setattr(
        governance_index,
        "verify_manifest",
        lambda *_args: {"status": "PASS"},
    )

    manifest = governance_index.refresh(synthetic_root, output_root)

    assert current_state.read_bytes() == before
    assert governance_index.DIRECTORY_REGISTRY_PATH in {
        item["path"] for item in manifest["inputs"]
    }
    assert governance_index.DIRECTORY_REGISTRY_SCHEMA_PATH in {
        item["path"] for item in manifest["inputs"]
    }
    outputs = {item["path"] for item in manifest["outputs"]}
    assert "governance/indexes/directory_map.md" in outputs
    assert "governance/indexes/new_file_routing.md" in outputs

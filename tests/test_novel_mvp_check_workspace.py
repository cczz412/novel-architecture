from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import check_tool, check_workspace
    from mvp.workspace import (
        OperationConflictError,
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


ALICE = "auth:m7-alice"
BOB = "auth:m7-bob"
CURRENT_TEXT = "林乔说钥匙在自己手里。片刻后，苏晚说钥匙一直在她手里。"
OLD_TEXT = "林乔把钥匙放在桌上。"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _revision_ref(*, revision_no: int = 2, text: str = CURRENT_TEXT) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": _sha(text),
    }


def _fact(
    fact_id: str,
    *,
    text: str,
    quote: str,
    status: str = "confirmed",
    revision_no: int = 2,
    revision_text: str = CURRENT_TEXT,
    bad_anchor: bool = False,
) -> dict:
    revision_ref = _revision_ref(revision_no=revision_no, text=revision_text)
    start = revision_text.index(quote) if quote in revision_text else 0
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": "c01",
        "text": text,
        "quote": quote,
        "status": status,
        "source": "M7_WORKSPACE_SYNTHETIC_FIXTURE",
        "note": "",
        "added_at": "2026-08-19 19:00:00",
        "seg": 1,
        "decided_at": "2026-08-19 19:01:00",
        "chapter_revision_ref": revision_ref,
        "anchor_ref": {
            **revision_ref,
            "coordinate_basis": check_tool.COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": "0" * 64 if bad_anchor else _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": (
            {
                "previous_status": "confirmed",
                "reason": "evidence_gone",
                "from_revision_no": 1,
                "target_revision_no": 2,
                "flagged_at": "2026-08-19 19:02:00",
            }
            if status == "needs_recheck"
            else None
        ),
    }


def _facts() -> tuple[dict, dict]:
    return (
        _fact(
            "f001",
            text="林乔说钥匙在自己手里。",
            quote="林乔说钥匙在自己手里",
        ),
        _fact(
            "f002",
            text="苏晚说钥匙一直在她手里。",
            quote="苏晚说钥匙一直在她手里",
        ),
    )


def _config(project_label: str = "合成钥匙案") -> dict:
    return {
        "project_label": project_label,
        "generated_at": "2026-08-19 19:30:00",
        "scope_name": "全量当前真值与候选",
        "scope_kind": "leftover",
        "kinds": ["naming", "timeline", "setting", "event"],
    }


def _finding(**overrides: object) -> dict:
    value = {
        "fact_ids": ["f001", "f002"],
        "kind": "setting",
        "verdict": "conflict",
        "severity": "red",
        "hard": True,
        "confidence": "high",
        "note": "同一把钥匙在同一时点被两人分别声称持有。",
    }
    value.update(overrides)
    return value


def _provider(*findings: dict) -> check_tool.FrozenFindingProvider:
    return check_tool.FrozenFindingProvider(
        {
            "provider_id": "frozen-offline-health-map-v1",
            "model_calls": 0,
            "response": {"findings": list(findings)},
        }
    )


class _RecordingProvider:
    provider_id = "recording-frozen-provider"
    model_calls = 0

    def __init__(self, *findings: dict):
        self.findings = list(findings)
        self.calls: list[dict] = []

    def find(self, batch: dict) -> dict:
        self.calls.append(json.loads(json.dumps(batch, ensure_ascii=False)))
        return {"findings": json.loads(json.dumps(self.findings, ensure_ascii=False))}


def _inventory(root: Path) -> list[tuple[str, bool, bytes | None]]:
    if not root.exists():
        return []
    return [
        (
            str(path.relative_to(root)),
            path.is_dir(),
            None if path.is_dir() else path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
    ]


def _commit_facts(
    workspace,
    facts: list[dict],
    refs: list[dict] | None = None,
) -> dict:
    refs = [_revision_ref()] if refs is None else refs
    return workspace.commit(
        "op-m7-facts-01",
        {"facts": facts, "chapter_index": refs},
        {"facts": 0, "chapter_index": 0},
    )


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def test_empty_project_returns_stable_empty_report_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "空项目")
    before = _inventory(runtime_root)
    read_calls: list[str] = []
    real_read = workspace.read
    monkeypatch.setattr(
        workspace,
        "read",
        lambda key: read_calls.append(key) or real_read(key),
    )
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("M7 适配器不得写 workspace")
        ),
    )

    first = check_workspace.execute(workspace, _config(), _provider())
    second = check_workspace.execute(workspace, _config(), _provider())

    assert first == second
    assert first["facts_snapshot"] == {"version": 0, "sha256": None}
    assert first["chapter_index_snapshot"] == {"version": 0, "sha256": None}
    assert first["m7"]["contract"] == "C6_HEALTH_REPORT"
    assert first["m7"]["scan"]["facts_total"] == 0
    assert first["m7"]["conflicts"] == []
    assert first["m7"]["scan"]["api_calls"] == 0
    assert read_calls == [
        "facts",
        "chapter_index",
        "facts",
        "chapter_index",
        "facts",
        "chapter_index",
    ] * 2
    assert _inventory(runtime_root) == before


def test_normal_findings_preserve_facts_version_sha_and_workspace_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "M7 合成项目")
    fact_a, fact_b = _facts()
    receipt = _commit_facts(workspace, [fact_a, fact_b])
    before = _inventory(runtime_root)
    read_calls: list[str] = []
    real_read = workspace.read
    monkeypatch.setattr(
        workspace,
        "read",
        lambda key: read_calls.append(key) or real_read(key),
    )
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("M7 适配器不得写 workspace")
        ),
    )

    provider = _RecordingProvider(_finding())
    result = check_workspace.execute(
        workspace,
        _config(),
        provider,
    )

    assert read_calls == [
        "facts",
        "chapter_index",
        "facts",
        "chapter_index",
        "facts",
        "chapter_index",
    ]
    assert result["facts_snapshot"] == {
        "version": receipt["versions"]["facts"],
        "sha256": receipt["payload_sha256"]["facts"],
    }
    assert result["chapter_index_snapshot"] == {
        "version": receipt["versions"]["chapter_index"],
        "sha256": receipt["payload_sha256"]["chapter_index"],
    }
    assert result["m7"]["model"] == "recording-frozen-provider"
    assert result["m7"]["scan"]["api_calls"] == 0
    assert len(provider.calls) == 1
    assert [
        row["fact_id"] for row in result["m7"]["conflicts"][0]["evidence"]
    ] == ["f001", "f002"]
    assert _inventory(runtime_root) == before
    assert list(inspect.signature(check_workspace.execute).parameters) == [
        "workspace",
        "check_config",
        "finding_provider",
    ]


def test_source_change_between_pre_reads_rejects_before_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "预读竞态")
    fact_a, fact_b = _facts()
    facts = [fact_a, fact_b]
    refs = [_revision_ref()]
    _commit_facts(workspace, facts, refs)
    provider = _RecordingProvider(_finding())
    real_read = workspace.read
    read_count = 0
    inventory_after_external: list[tuple[str, bool, bytes | None]] | None = None

    def racing_read(logical_key: str):
        nonlocal read_count, inventory_after_external
        read_count += 1
        value = real_read(logical_key)
        if read_count == 2:
            workspace.commit(
                "op-external-pre-provider",
                {"facts": facts, "chapter_index": refs},
                {"facts": 1, "chapter_index": 1},
            )
            inventory_after_external = _inventory(runtime_root)
        return value

    monkeypatch.setattr(workspace, "read", racing_read)
    with pytest.raises(
        check_workspace.CheckWorkspaceError,
        match="M7_SOURCE_CHANGED_BEFORE_PROVIDER",
    ):
        check_workspace.execute(workspace, _config(), provider)

    assert provider.calls == []
    assert real_read("facts")["version"] == 2
    assert real_read("chapter_index")["version"] == 2
    assert _inventory(runtime_root) == inventory_after_external


@pytest.mark.parametrize("changed_key", ["facts", "chapter_index"])
def test_source_change_during_provider_discards_report_and_keeps_new_state(
    tmp_path: Path,
    changed_key: str,
) -> None:
    runtime_root = tmp_path / changed_key
    workspace = WorkspaceRouter(runtime_root).create_project(
        ALICE, "Provider 竞态"
    )
    fact_a, fact_b = _facts()
    facts = [fact_a, fact_b]
    refs = [_revision_ref()]
    _commit_facts(workspace, facts, refs)

    class _ChangingProvider(_RecordingProvider):
        def __init__(self) -> None:
            super().__init__(_finding())
            self.inventory_after_external = None

        def find(self, batch: dict) -> dict:
            result = super().find(batch)
            payload = facts if changed_key == "facts" else refs
            workspace.commit(
                f"op-provider-change-{changed_key}",
                {changed_key: payload},
                {changed_key: 1},
            )
            self.inventory_after_external = _inventory(runtime_root)
            return result

    provider = _ChangingProvider()
    with pytest.raises(
        check_workspace.CheckWorkspaceError,
        match="M7_SOURCE_CHANGED_DURING_PROVIDER",
    ):
        check_workspace.execute(workspace, _config(), provider)

    assert len(provider.calls) == 1
    assert workspace.read(changed_key)["version"] == 2
    other_key = "chapter_index" if changed_key == "facts" else "facts"
    assert workspace.read(other_key)["version"] == 1
    assert _inventory(runtime_root) == provider.inventory_after_external


def test_excluded_facts_do_not_reach_findings(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        ALICE, "排除门项目"
    )
    fact_a, fact_b = _facts()
    stale = _fact(
        "f003",
        text="林乔把钥匙放在桌上。",
        quote="林乔把钥匙放在桌上",
        revision_no=1,
        revision_text=OLD_TEXT,
    )
    rejected = _fact(
        "f004",
        text="被作者驳回的钥匙说法。",
        quote="林乔说钥匙在自己手里",
        status="rejected",
    )
    needs_recheck = _fact(
        "f005",
        text="需要重查的钥匙说法。",
        quote="苏晚说钥匙一直在她手里",
        status="needs_recheck",
    )
    bad_anchor = _fact(
        "f006",
        text="锚损坏的钥匙说法。",
        quote="林乔说钥匙在自己手里",
        bad_anchor=True,
    )
    _commit_facts(
        workspace,
        [fact_a, fact_b, stale, rejected, needs_recheck, bad_anchor],
    )

    provider = _RecordingProvider(_finding())
    result = check_workspace.execute(
        workspace,
        _config(),
        provider,
    )

    counts = result["m7"]["scan"]["excluded_counts"]
    assert counts["stale_revision"] == 1
    assert counts["rejected"] == 1
    assert counts["needs_recheck"] == 1
    assert counts["invalid_evidence"] == 1
    assert {
        row["fact_id"]
        for finding in result["m7"]["conflicts"]
        for row in finding["evidence"]
    } == {"f001", "f002"}
    assert len(provider.calls) == 1
    assert [fact["id"] for fact in provider.calls[0]["facts"]] == ["f001", "f002"]


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("missing", "CHAPTER_INDEX_REQUIRED_FOR_NONEMPTY_FACTS"),
        ("bad-shape", "CHAPTER_INDEX_REF_INVALID:0"),
        ("duplicate", "CHAPTER_INDEX_REF_DUPLICATE:c01"),
        ("chapter-mismatch", "CHAPTER_INDEX_REF_MISSING:c02"),
    ],
)
def test_nonempty_facts_bad_index_fails_before_provider_and_writes_nothing(
    tmp_path: Path,
    case: str,
    reason: str,
) -> None:
    runtime_root = tmp_path / case
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, case)
    fact_a, fact_b = _facts()
    if case == "missing":
        workspace.commit("op-missing-index", {"facts": [fact_a, fact_b]}, {"facts": 0})
    else:
        refs = [_revision_ref()]
        if case == "bad-shape":
            refs = [{"chapter_id": "c01", "revision_no": 2}]
        elif case == "duplicate":
            refs.append(dict(refs[0]))
        else:
            fact_a["chapter_id"] = "c02"
            fact_a["chapter_revision_ref"]["chapter_id"] = "c02"
            fact_a["anchor_ref"]["chapter_id"] = "c02"
        workspace.commit(
            f"op-{case}",
            {"facts": [fact_a, fact_b], "chapter_index": refs},
            {"facts": 0, "chapter_index": 0},
        )
    before = _inventory(runtime_root)
    provider = _RecordingProvider()

    with pytest.raises(check_workspace.CheckWorkspaceError, match=reason):
        check_workspace.execute(workspace, _config(), provider)

    assert provider.calls == []
    assert _inventory(runtime_root) == before


def test_new_process_reopen_produces_byte_identical_result(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(ALICE, "重启稳定项目")
    fact_a, fact_b = _facts()
    _commit_facts(workspace, [fact_a, fact_b])
    frozen = {
        "provider_id": "frozen-offline-health-map-v1",
        "model_calls": 0,
        "response": {"findings": [_finding()]},
    }
    script = f"""
import json, sys
sys.path.insert(0, {str(PRODUCT_ROOT)!r})
from mvp import check_tool, check_workspace
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
provider = check_tool.FrozenFindingProvider({frozen!r})
result = check_workspace.execute(workspace, {_config()!r}, provider)
print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
"""
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        sys.executable,
        "-c",
        script,
        str(runtime_root),
        ALICE,
        workspace.project_id,
    ]

    first = subprocess.run(
        command,
        check=False,
        capture_output=True,
        env=environment,
    )
    second = subprocess.run(
        command,
        check=False,
        capture_output=True,
        env=environment,
    )

    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["facts_snapshot"]["version"] == 1


def test_other_author_project_guess_cannot_change_workspace_binding(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project(ALICE, "同名项目")
    fact_a, fact_b = _facts()
    _commit_facts(alice, [fact_a, fact_b])
    bob = router.create_project(BOB, "同名项目")

    result = check_workspace.execute(
        bob,
        _config(project_label=alice.project_id),
        _provider(),
    )

    assert result["facts_snapshot"] == {"version": 0, "sha256": None}
    assert result["chapter_index_snapshot"] == {"version": 0, "sha256": None}
    assert result["m7"]["scan"]["facts_total"] == 0
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(BOB, alice.project_id)


def test_path_cannot_impersonate_workspace_handle(tmp_path: Path) -> None:
    caller_path = tmp_path / "caller-controlled-project"

    with pytest.raises(
        check_workspace.CheckWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        check_workspace.execute(  # type: ignore[arg-type]
            caller_path,
            _config(),
            _provider(),
        )

    assert not caller_path.exists()


def test_bad_provider_leaves_workspace_byte_identical(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "坏响应项目")
    fact_a, fact_b = _facts()
    _commit_facts(workspace, [fact_a, fact_b])
    before = _inventory(runtime_root)
    bad = _provider(_finding(fact_ids=["f001", "f999"]))

    with pytest.raises(check_tool.CheckToolError, match="未知 fact"):
        check_workspace.execute(
            workspace,
            _config(),
            bad,
        )

    assert _inventory(runtime_root) == before


def test_result_wrapper_is_json_serializable_and_snapshot_is_not_mutable_alias(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        ALICE, "序列化项目"
    )
    fact_a, fact_b = _facts()
    receipt = _commit_facts(workspace, [fact_a, fact_b])

    result = check_workspace.execute(
        workspace,
        _config(),
        _provider(_finding()),
    )
    encoded = _canonical_bytes(result)
    reread = json.loads(encoded)

    assert reread["facts_snapshot"] == {
        "version": 1,
        "sha256": receipt["payload_sha256"]["facts"],
    }
    result["m7"]["conflicts"][0]["evidence"][0]["text"] = "调用方局部改动"
    assert workspace.read("facts")["payload"][0]["text"] == fact_a["text"]


def test_execute_save_restart_read_preserves_report_and_evidence_bytes(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(ALICE, "M7 报告持久化")
    fact_a, fact_b = _facts()
    _commit_facts(workspace, [fact_a, fact_b])

    saved = check_workspace.execute_and_save(
        workspace,
        "op-m7-save-01",
        _config(),
        _provider(_finding()),
        0,
    )
    loaded = check_workspace.read_saved(workspace)

    assert saved["receipt"]["versions"] == {"health_report": 1}
    assert loaded["health_report_snapshot"]["version"] == 1
    assert loaded["m7"]["source_revision_state"] == "CURRENT"
    assert loaded["stale_reasons"] == []
    assert _canonical_bytes(loaded["m7"]) == _canonical_bytes(saved["m7"])
    assert _canonical_bytes(loaded["m7"]["conflicts"][0]["evidence"]) == (
        _canonical_bytes(saved["m7"]["conflicts"][0]["evidence"])
    )

    script = """
import json, sys
sys.path.insert(0, sys.argv[4])
from mvp import check_workspace
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
print(json.dumps(check_workspace.read_saved(workspace), ensure_ascii=False, sort_keys=True, separators=(',', ':')))
"""
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(runtime_root),
            ALICE,
            workspace.project_id,
            str(PRODUCT_ROOT),
        ],
        check=False,
        capture_output=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    reopened = json.loads(completed.stdout)
    assert _canonical_bytes(reopened["m7"]) == _canonical_bytes(saved["m7"])
    assert list(inspect.signature(check_workspace.execute_and_save).parameters) == [
        "workspace",
        "operation_id",
        "check_config",
        "finding_provider",
        "expected_report_version",
    ]
    assert list(inspect.signature(check_workspace.read_saved).parameters) == [
        "workspace"
    ]


def test_save_is_idempotent_and_conflicts_never_replace_current_report(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        ALICE, "M7 幂等项目"
    )
    fact_a, fact_b = _facts()
    _commit_facts(workspace, [fact_a, fact_b])
    original = check_workspace.execute_and_save(
        workspace,
        "op-m7-idempotent",
        _config(),
        _provider(_finding()),
        0,
    )
    replay = check_workspace.execute_and_save(
        workspace,
        "op-m7-idempotent",
        _config(),
        _provider(_finding()),
        0,
    )

    assert replay["receipt"]["replayed"] is True
    assert replay["receipt"]["generation_id"] == original["receipt"][
        "generation_id"
    ]
    changed_config = _config()
    changed_config["generated_at"] = "2026-08-19 19:31:00"
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        check_workspace.execute_and_save(
            workspace,
            "op-m7-idempotent",
            changed_config,
            _provider(_finding()),
            0,
        )
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        check_workspace.execute_and_save(
            workspace,
            "op-m7-old-version",
            changed_config,
            _provider(_finding()),
            0,
        )
    assert _canonical_bytes(check_workspace.read_saved(workspace)["m7"]) == (
        _canonical_bytes(original["m7"])
    )
    assert workspace.read("health_report")["version"] == 1


@pytest.mark.parametrize(
    ("changed_key", "reason"),
    [
        ("facts", "FACTS_SNAPSHOT_ADVANCED"),
        ("chapter_index", "CHAPTER_INDEX_SNAPSHOT_ADVANCED"),
    ],
)
def test_saved_report_reads_stale_after_source_advance_without_writing(
    tmp_path: Path,
    changed_key: str,
    reason: str,
) -> None:
    runtime_root = tmp_path / changed_key
    workspace = WorkspaceRouter(runtime_root).create_project(
        ALICE, "M7 过期派生"
    )
    fact_a, fact_b = _facts()
    _commit_facts(workspace, [fact_a, fact_b])
    check_workspace.execute_and_save(
        workspace,
        "op-m7-save-current",
        _config(),
        _provider(_finding()),
        0,
    )
    current = workspace.read(changed_key)
    workspace.commit(
        f"op-advance-{changed_key}",
        {changed_key: current["payload"]},
        {changed_key: current["version"]},
    )
    before = _inventory(runtime_root)

    loaded = check_workspace.read_saved(workspace)

    assert loaded["m7"]["source_revision_state"] == "STALE"
    assert loaded["stale_reasons"] == [reason]
    assert len(loaded["m7"]["conflicts"]) == 1
    assert workspace.read("health_report")["version"] == 1
    assert _inventory(runtime_root) == before


def test_provider_or_source_failure_does_not_overwrite_saved_report(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(
        ALICE, "M7 失败不覆盖"
    )
    fact_a, fact_b = _facts()
    facts = [fact_a, fact_b]
    _commit_facts(workspace, facts)
    original = check_workspace.execute_and_save(
        workspace,
        "op-save-good",
        _config(),
        _provider(_finding()),
        0,
    )

    with pytest.raises(check_tool.CheckToolError, match="未知 fact"):
        check_workspace.execute_and_save(
            workspace,
            "op-save-bad-provider",
            _config(),
            _provider(_finding(fact_ids=["f001", "f999"])),
            1,
        )
    assert workspace.read("health_report")["version"] == 1

    class _ChangingProvider(_RecordingProvider):
        def find(self, batch: dict) -> dict:
            response = super().find(batch)
            workspace.commit(
                "op-source-advance-during-save",
                {"facts": facts},
                {"facts": 1},
            )
            return response

    with pytest.raises(
        check_workspace.CheckWorkspaceError,
        match="M7_SOURCE_CHANGED_DURING_PROVIDER",
    ):
        check_workspace.execute_and_save(
            workspace,
            "op-save-racing-provider",
            _config(),
            _ChangingProvider(_finding()),
            1,
        )
    stored = workspace.read("health_report")
    assert stored["version"] == 1
    assert _canonical_bytes(stored["payload"]["m7"]) == _canonical_bytes(
        original["m7"]
    )


@pytest.mark.parametrize("changed_key", ["facts", "chapter_index"])
def test_guarded_save_rejects_source_change_at_commit_without_report_growth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_key: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / changed_key).create_project(
        ALICE, "M7 提交窗口竞态"
    )
    fact_a, fact_b = _facts()
    source_receipt = _commit_facts(workspace, [fact_a, fact_b])
    check_workspace.execute_and_save(
        workspace,
        "op-save-before-commit-race",
        _config(),
        _provider(_finding()),
        0,
    )
    original_commit = workspace.commit_guarded
    guarded_sources: list[dict] = []

    def race(operation_id, mutations, expected_versions, guard_versions):
        guarded_sources.append(copy.deepcopy(guard_versions))
        current = workspace.read(changed_key)
        workspace.commit(
            f"op-race-{changed_key}",
            {changed_key: current["payload"]},
            {
                changed_key: {
                    "version": current["version"],
                    "sha256": current["sha256"],
                }
            },
        )
        return original_commit(
            operation_id,
            mutations,
            expected_versions,
            guard_versions,
        )

    monkeypatch.setattr(workspace, "commit_guarded", race)
    changed_config = _config()
    changed_config["generated_at"] = "2026-08-19 19:31:00"
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        check_workspace.execute_and_save(
            workspace,
            f"op-save-race-{changed_key}",
            changed_config,
            _provider(_finding()),
            1,
        )

    assert guarded_sources == [
        {
            "facts": {
                "version": source_receipt["versions"]["facts"],
                "sha256": source_receipt["payload_sha256"]["facts"],
            },
            "chapter_index": {
                "version": source_receipt["versions"]["chapter_index"],
                "sha256": source_receipt["payload_sha256"]["chapter_index"],
            },
        }
    ]
    assert workspace.read("health_report")["version"] == 1
    assert workspace.read(changed_key)["version"] == 2


def test_read_rejects_same_version_sha_conflict_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "M7 SHA 冲突")
    fact_a, fact_b = _facts()
    _commit_facts(workspace, [fact_a, fact_b])
    check_workspace.execute_and_save(
        workspace,
        "op-save-good",
        _config(),
        _provider(_finding()),
        0,
    )
    real_read = workspace.read

    def conflicting_read(logical_key: str):
        entry = real_read(logical_key)
        if logical_key == "facts":
            entry["sha256"] = "0" * 64
        return entry

    monkeypatch.setattr(workspace, "read", conflicting_read)
    before = _inventory(runtime_root)
    with pytest.raises(
        check_workspace.CheckWorkspaceError,
        match="FACTS_SNAPSHOT_SHA_CONFLICT",
    ):
        check_workspace.read_saved(workspace)
    assert _inventory(runtime_root) == before


def test_empty_report_bad_store_cross_author_and_path_fail_closed(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    empty = router.create_project(ALICE, "M7 空事实")
    saved = check_workspace.execute_and_save(
        empty,
        "op-save-empty",
        _config(),
        _provider(),
        0,
    )
    assert saved["m7"]["scan"]["facts_total"] == 0
    assert check_workspace.read_saved(empty)["m7"]["conflicts"] == []

    corrupt = router.create_project(ALICE, "M7 坏存储")
    corrupt.commit(
        "op-corrupt-report-store",
        {"health_report": {"bad": True}},
        {"health_report": 0},
    )
    before_corrupt = _inventory(runtime_root)
    with pytest.raises(
        check_workspace.CheckWorkspaceError,
        match="HEALTH_REPORT_STORE_INVALID",
    ):
        check_workspace.read_saved(corrupt)
    assert _inventory(runtime_root) == before_corrupt

    alice_payload = empty.read("health_report")["payload"]
    bob = router.create_project(BOB, "M7 跨作者")
    bob.commit(
        "op-copy-cross-author",
        {"health_report": alice_payload},
        {"health_report": 0},
    )
    with pytest.raises(
        check_workspace.CheckWorkspaceError,
        match="HEALTH_REPORT_WORKSPACE_BINDING_MISMATCH",
    ):
        check_workspace.read_saved(bob)

    caller_path = tmp_path / "caller-path"
    with pytest.raises(
        check_workspace.CheckWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        check_workspace.execute_and_save(  # type: ignore[arg-type]
            caller_path,
            "op-path",
            _config(),
            _provider(),
            0,
        )
    with pytest.raises(
        check_workspace.CheckWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        check_workspace.read_saved(caller_path)  # type: ignore[arg-type]
    assert not caller_path.exists()

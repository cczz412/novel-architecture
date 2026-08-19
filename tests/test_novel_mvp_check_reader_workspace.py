from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        check_reader_workspace,
        check_tool,
        check_workspace,
    )
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:m7-reader-alice"
BOB = "auth:m7-reader-bob"
CURRENT_TEXT = "林乔说钥匙在自己手里。苏晚说钥匙一直在她手里。"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _revision_ref() -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": 1,
        "revision_text_sha256": _sha(CURRENT_TEXT),
    }


def _fact(fact_id: str, quote: str) -> dict:
    revision_ref = _revision_ref()
    start = CURRENT_TEXT.index(quote)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": "c01",
        "text": quote,
        "quote": quote,
        "status": "confirmed",
        "source": "M7_READER_SYNTHETIC_FIXTURE",
        "note": "",
        "added_at": "2026-08-19 22:00:00",
        "seg": 1,
        "decided_at": "2026-08-19 22:01:00",
        "chapter_revision_ref": revision_ref,
        "anchor_ref": {
            **revision_ref,
            "coordinate_basis": check_tool.COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _facts() -> list[dict]:
    return [
        _fact("f001", "林乔说钥匙在自己手里"),
        _fact("f002", "苏晚说钥匙一直在她手里"),
    ]


def _config() -> dict:
    return {
        "project_label": "合成钥匙案",
        "generated_at": "2026-08-19 22:10:00",
        "scope_name": "全量当前事实",
        "scope_kind": "leftover",
        "kinds": ["naming", "timeline", "setting", "event"],
    }


def _provider() -> check_tool.FrozenFindingProvider:
    return check_tool.FrozenFindingProvider(
        {
            "provider_id": "frozen-offline-reader-map-v1",
            "model_calls": 0,
            "response": {
                "findings": [
                    {
                        "fact_ids": ["f001", "f002"],
                        "kind": "setting",
                        "verdict": "conflict",
                        "severity": "red",
                        "hard": True,
                        "confidence": "high",
                        "note": "同一把钥匙被两人分别声称持有。",
                    }
                ]
            },
        }
    )


def _seed_saved_report(workspace) -> dict:
    facts = _facts()
    workspace.commit(
        "op-reader-seed-sources",
        {"facts": facts, "chapter_index": [_revision_ref()]},
        {"facts": 0, "chapter_index": 0},
    )
    return check_workspace.execute_and_save(
        workspace,
        "op-reader-save-report",
        _config(),
        _provider(),
        0,
    )


def _inventory(root: Path) -> list[tuple[str, bool, bytes | None]]:
    return [
        (
            str(path.relative_to(root)),
            path.is_dir(),
            None if path.is_dir() else path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
    ]


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def test_current_saved_report_reopens_as_one_step_author_view_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(ALICE, "M7 阅读项目")
    _seed_saved_report(workspace)
    before = _inventory(runtime_root)
    real_render = check_tool.render_report
    rendered_inputs: list[dict] = []

    def recording_render(report: dict) -> str:
        rendered_inputs.append(copy.deepcopy(report))
        return real_render(report)

    monkeypatch.setattr(check_tool, "render_report", recording_render)
    monkeypatch.setattr(
        check_tool,
        "execute",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("阅读器不得执行 M7 或调用 provider")
        ),
    )
    result = check_reader_workspace.read_author_view(workspace)

    assert result["status"] == "CURRENT"
    assert result["encoding"] == "UTF-8"
    assert result["health_report_snapshot"]["version"] == 1
    assert result["stale_reasons"] == []
    assert result["text"].startswith("【当前体检报告】\n状态：CURRENT")
    assert "严重度：red" in result["text"]
    assert "引文：林乔说钥匙在自己手里" in result["text"]
    assert len(rendered_inputs) == 1
    assert rendered_inputs[0]["source_revision_state"] == "CURRENT"
    assert _inventory(runtime_root) == before

    script = """
import json, sys
sys.path.insert(0, sys.argv[4])
from mvp import check_reader_workspace
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
print(json.dumps(check_reader_workspace.read_author_view(workspace), ensure_ascii=False, sort_keys=True, separators=(',', ':')))
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
    assert _canonical(json.loads(completed.stdout)) == _canonical(result)


@pytest.mark.parametrize(
    ("changed_key", "reason", "human_reason"),
    [
        ("facts", "FACTS_SNAPSHOT_ADVANCED", "事实账水位已前进"),
        (
            "chapter_index",
            "CHAPTER_INDEX_SNAPSHOT_ADVANCED",
            "章节索引水位已前进",
        ),
    ],
)
def test_advanced_source_keeps_history_visible_but_marks_it_expired(
    tmp_path: Path,
    changed_key: str,
    reason: str,
    human_reason: str,
) -> None:
    runtime_root = tmp_path / changed_key
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "M7 过期阅读")
    _seed_saved_report(workspace)
    current = workspace.read(changed_key)
    workspace.commit(
        f"op-reader-advance-{changed_key}",
        {changed_key: current["payload"]},
        {changed_key: current["version"]},
    )
    before = _inventory(runtime_root)

    result = check_reader_workspace.read_author_view(workspace)

    assert result["status"] == "STALE"
    assert result["stale_reasons"] == [reason]
    assert result["text"].startswith("【历史体检报告｜已过期】\n状态：STALE")
    assert "不能当作当前报告" in result["text"]
    assert human_reason in result["text"]
    assert reason in result["text"]
    assert "严重度：red" in result["text"]
    assert "【当前体检报告】" not in result["text"]
    assert workspace.read("health_report")["version"] == 1
    assert _inventory(runtime_root) == before


@pytest.mark.parametrize("changed_key", ["health_report", "facts"])
def test_report_or_source_change_between_reads_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_key: str,
) -> None:
    runtime_root = tmp_path / changed_key
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "M7 竞态阅读")
    _seed_saved_report(workspace)
    real_read_saved = check_workspace.read_saved
    calls = 0
    inventory_after_external: list[tuple[str, bool, bytes | None]] | None = None

    def racing_read(handle):
        nonlocal calls, inventory_after_external
        calls += 1
        value = real_read_saved(handle)
        if calls == 1:
            current = workspace.read(changed_key)
            workspace.commit(
                f"op-reader-race-{changed_key}",
                {changed_key: current["payload"]},
                {changed_key: current["version"]},
            )
            inventory_after_external = _inventory(runtime_root)
        return value

    monkeypatch.setattr(check_workspace, "read_saved", racing_read)

    with pytest.raises(
        check_reader_workspace.CheckReaderWorkspaceError,
        match="SAVED_REPORT_CHANGED_DURING_READ",
    ):
        check_reader_workspace.read_author_view(workspace)

    assert calls == 2
    assert _inventory(runtime_root) == inventory_after_external


def test_empty_is_stable_and_never_generates_or_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "M7 空阅读")
    before = _inventory(runtime_root)
    calls = 0
    real_read_saved = check_workspace.read_saved

    def counted_read(handle):
        nonlocal calls
        calls += 1
        return real_read_saved(handle)

    monkeypatch.setattr(check_workspace, "read_saved", counted_read)
    monkeypatch.setattr(
        check_tool,
        "execute",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("EMPTY 不得自动生成报告")
        ),
    )

    result = check_reader_workspace.read_author_view(workspace)

    assert calls == 2
    assert result == {
        "status": "EMPTY",
        "encoding": "UTF-8",
        "health_report_snapshot": None,
        "current_facts_snapshot": None,
        "current_chapter_index_snapshot": None,
        "stale_reasons": [],
        "text": (
            "【暂无已保存体检报告】\n"
            "状态：EMPTY\n"
            "没有可读取的已保存报告；本次未生成或重跑报告。\n"
        ),
    }
    assert _inventory(runtime_root) == before


def test_saved_report_with_no_findings_stays_inconclusive(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "M7 空 finding")
    workspace.commit(
        "op-reader-empty-findings-sources",
        {"facts": [], "chapter_index": []},
        {"facts": 0, "chapter_index": 0},
    )
    check_workspace.execute_and_save(
        workspace,
        "op-reader-empty-findings-report",
        _config(),
        check_tool.FrozenFindingProvider(
            {
                "provider_id": "frozen-offline-empty-reader-map-v1",
                "model_calls": 0,
                "response": {"findings": []},
            }
        ),
        0,
    )
    before = _inventory(runtime_root)

    result = check_reader_workspace.read_author_view(workspace)

    assert result["status"] == "CURRENT"
    assert "本次未返回 finding；这不能证明没有问题" in result["text"]
    assert "通过" not in result["text"]
    assert "全绿" not in result["text"]
    assert _inventory(runtime_root) == before


def test_bad_store_path_and_cross_author_fail_closed_without_reader_writes(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    corrupt = router.create_project(ALICE, "M7 坏存储")
    corrupt.commit(
        "op-reader-corrupt-store",
        {"health_report": {"bad": True}},
        {"health_report": 0},
    )
    before_corrupt = _inventory(runtime_root)
    with pytest.raises(check_workspace.CheckWorkspaceError):
        check_reader_workspace.read_author_view(corrupt)
    assert _inventory(runtime_root) == before_corrupt

    alice = router.create_project(ALICE, "M7 Alice")
    _seed_saved_report(alice)
    alice_payload = alice.read("health_report")["payload"]
    bob = router.create_project(BOB, "M7 Bob")
    bob.commit(
        "op-reader-copy-cross-author",
        {"health_report": alice_payload},
        {"health_report": 0},
    )
    before_bob = _inventory(runtime_root)
    with pytest.raises(
        check_workspace.CheckWorkspaceError,
        match="HEALTH_REPORT_WORKSPACE_BINDING_MISMATCH",
    ):
        check_reader_workspace.read_author_view(bob)
    assert _inventory(runtime_root) == before_bob
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(BOB, alice.project_id)

    caller_path = tmp_path / "caller-path"
    with pytest.raises(
        check_reader_workspace.CheckReaderWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        check_reader_workspace.read_author_view(  # type: ignore[arg-type]
            caller_path
        )
    assert not caller_path.exists()

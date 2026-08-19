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
TOOL_PATH = PRODUCT_ROOT / "mvp/review_decision_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        factstore,
        review_decision_tool,
        review_queue_workspace,
        review_workspace,
    )
    from mvp.workspace import VersionConflictError, WorkspaceRouter
finally:
    sys.path.pop(0)


PRINCIPAL = "auth:review-decision-alice"
CHAPTER_TEXT = "甲拿起铜钥匙。乙离开房间。丙关上门。"
DECIDED_AT = "2026-08-20 00:10:00"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_ref() -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": 2,
        "revision_text_sha256": _sha(CHAPTER_TEXT),
    }


def _fact(fact_id: str, quote: str) -> dict:
    revision = _revision_ref()
    start = CHAPTER_TEXT.index(quote)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": "c01",
        "text": f"候选事实：{quote}",
        "quote": quote,
        "status": "extracted",
        "source": "M5_REVIEW_DECISION_SYNTHETIC_FIXTURE",
        "note": "",
        "added_at": "2026-08-20 00:00:00",
        "seg": 1,
        "chapter_revision_ref": revision,
        "anchor_ref": {
            **revision,
            "coordinate_basis": (
                "CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN"
            ),
            "start": start,
            "end": start + len(quote),
            "slice_sha256": _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _facts() -> list[dict]:
    return [
        _fact("f001", "甲拿起铜钥匙。"),
        _fact("f002", "乙离开房间。"),
        _fact("f003", "丙关上门。"),
    ]


def _setup(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime).create_project(PRINCIPAL, "决定动作项目")
    workspace.commit(
        "op-seed-review-decisions",
        {"facts": _facts(), "chapter_index": [_revision_ref()]},
        {"facts": 0, "chapter_index": 0},
    )
    page = review_queue_workspace.read_chapter_review_page(
        workspace,
        "c01",
        2,
        None,
    )
    return runtime, workspace, page


def _decision(
    fact_ref: str,
    decision: str,
    operation_id: str,
    note: str = "",
) -> dict:
    return {
        "fact_ref": fact_ref,
        "decision": decision,
        "note": note,
        "operation_id": operation_id,
        "decided_at": DECIDED_AT,
    }


def _request(page: dict) -> dict:
    return {
        "review_page": page,
        "decisions": [
            _decision("f001", "confirm", "op-author-confirm-f001", "作者确认"),
            _decision("f002", "reject", "op-author-reject-f002"),
        ],
    }


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def _subprocess_facts(runtime: Path, project_id: str) -> dict:
    script = """
import json, sys
sys.path.insert(0, sys.argv[1])
from mvp.workspace import WorkspaceRouter
value = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4]).read("facts")
print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(PRODUCT_ROOT),
            str(runtime),
            PRINCIPAL,
            project_id,
        ],
        capture_output=True,
        check=False,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_confirm_reject_actions_exactly_reuse_builder_and_apply_in_one_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, workspace, page = _setup(tmp_path)
    request = _request(page)
    before_request = copy.deepcopy(request)

    output = review_decision_tool.execute(request)

    assert request == before_request
    assert output["expected_facts_version"] == page["facts_snapshot"]["version"]
    assert output["expected_facts_sha256"] == page["facts_snapshot"]["sha256"]
    for item, decision, fact in zip(
        output["review_actions"],
        request["decisions"],
        page["items"],
        strict=True,
    ):
        assert item == {
            "action": factstore.build_review_action(
                fact,
                decision=decision["decision"],
                note=decision["note"],
                replacement_text=None,
                operation_id=decision["operation_id"],
            ),
            "chapter_revision_ref": page["chapter_revision_ref"],
            "decided_at": decision["decided_at"],
        }

    commit_calls = 0
    real_commit = workspace.commit

    def recording_commit(*args, **kwargs):
        nonlocal commit_calls
        commit_calls += 1
        return real_commit(*args, **kwargs)

    monkeypatch.setattr(workspace, "commit", recording_commit)
    applied = review_workspace.apply_review_batch(
        workspace,
        operation_id="op-author-page-batch",
        **output,
    )

    assert commit_calls == 1
    assert applied["facts_version"] == page["facts_snapshot"]["version"] + 1
    assert [fact["status"] for fact in applied["facts"]] == [
        "confirmed",
        "rejected",
        "extracted",
    ]
    reopened = _subprocess_facts(runtime, workspace.project_id)
    assert reopened["version"] == applied["facts_version"]
    assert reopened["payload"] == applied["facts"]


def test_selecting_only_one_page_item_leaves_other_items_pending(
    tmp_path: Path,
) -> None:
    _, workspace, page = _setup(tmp_path)
    request = {
        "review_page": page,
        "decisions": [
            _decision("f002", "reject", "op-only-reject-f002"),
        ],
    }

    output = review_decision_tool.execute(request)
    applied = review_workspace.apply_review_batch(
        workspace,
        operation_id="op-one-selected-batch",
        **output,
    )

    assert [item["action"]["fact_ref"] for item in output["review_actions"]] == [
        "f002"
    ]
    assert [fact["status"] for fact in applied["facts"]] == [
        "extracted",
        "rejected",
        "extracted",
    ]


def test_explicit_edit_and_edit_confirm_reuse_formal_semantics_in_one_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, page = _setup(tmp_path)
    decisions = [
        {
            **_decision("f001", "edit", "op-author-edit-f001"),
            "replacement_text": "甲拿起的是一把铜钥匙。",
        },
        {
            **_decision(
                "f002",
                "edit_and_confirm",
                "op-author-edit-confirm-f002",
                "作者明确改写并确认",
            ),
            "replacement_text": "乙已经离开了房间。",
        },
    ]
    request = {"review_page": page, "decisions": decisions}

    output = review_decision_tool.execute(request)

    for item, decision, fact in zip(
        output["review_actions"],
        decisions,
        page["items"],
        strict=True,
    ):
        assert item["action"] == factstore.build_review_action(
            fact,
            decision=decision["decision"],
            note=decision["note"],
            replacement_text=decision["replacement_text"],
            operation_id=decision["operation_id"],
        )

    commit_calls = 0
    real_commit = workspace.commit

    def recording_commit(*args, **kwargs):
        nonlocal commit_calls
        commit_calls += 1
        return real_commit(*args, **kwargs)

    monkeypatch.setattr(workspace, "commit", recording_commit)
    applied = review_workspace.apply_review_batch(
        workspace,
        operation_id="op-author-edit-page-batch",
        **output,
    )

    assert commit_calls == 1
    first, second, third = applied["facts"]
    assert first["text"] == "甲拿起的是一把铜钥匙。"
    assert first["status"] == "extracted"
    assert first["note"] == "原文候选：候选事实：甲拿起铜钥匙。"
    assert "decided_at" not in first
    assert second["text"] == "乙已经离开了房间。"
    assert second["status"] == "confirmed"
    assert second["note"] == "作者明确改写并确认"
    assert second["decided_at"] == DECIDED_AT
    assert third["status"] == "extracted"


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        ("not_on_page", "DECISION_FACT_NOT_ON_PAGE:f003"),
        ("duplicate_fact", "DECISION_FACT_REF_DUPLICATE:f001"),
        ("duplicate_operation", "DECISION_OPERATION_ID_DUPLICATE:op-same"),
        ("bad_operation", "DECISION_OPERATION_ID_INVALID:0"),
        ("empty", "DECISIONS_MUST_BE_NONEMPTY_ARRAY"),
        ("edit_missing", "DECISION_REPLACEMENT_REQUIRED:0"),
        ("edit_blank", "DECISION_REPLACEMENT_REQUIRED:0"),
        ("replacement", "DECISION_REPLACEMENT_FORBIDDEN:0"),
        ("bad_page", "REVIEW_PAGE_INVALID:PAGE_NEXT_CURSOR_MISMATCH"),
    ],
)
def test_invalid_decisions_or_page_fail_closed(
    tmp_path: Path,
    damage: str,
    reason: str,
) -> None:
    _, _, page = _setup(tmp_path)
    request = _request(page)
    if damage == "not_on_page":
        request["decisions"] = [
            _decision("f003", "confirm", "op-off-page"),
        ]
    elif damage == "duplicate_fact":
        request["decisions"][1]["fact_ref"] = "f001"
    elif damage == "duplicate_operation":
        request["decisions"][0]["operation_id"] = "op-same"
        request["decisions"][1]["operation_id"] = "op-same"
    elif damage == "bad_operation":
        request["decisions"][0]["operation_id"] = "bad operation"
    elif damage == "empty":
        request["decisions"] = []
    elif damage == "edit_missing":
        request["decisions"][0]["decision"] = "edit"
    elif damage == "edit_blank":
        request["decisions"][0]["decision"] = "edit_and_confirm"
        request["decisions"][0]["replacement_text"] = "  "
    elif damage == "replacement":
        request["decisions"][0]["replacement_text"] = "禁止字段"
    else:
        request["review_page"]["next_after_fact_ref"] = "f999"

    with pytest.raises(review_decision_tool.ReviewDecisionToolError, match=reason):
        review_decision_tool.execute(request)


def test_facts_change_after_page_is_rejected_by_existing_watermark_without_write(
    tmp_path: Path,
) -> None:
    _, workspace, page = _setup(tmp_path)
    output = review_decision_tool.execute(_request(page))
    changed = copy.deepcopy(workspace.read("facts")["payload"])
    changed[0]["note"] = "其他调用方先改了 facts"
    workspace.commit(
        "op-concurrent-facts-change",
        {"facts": changed},
        {"facts": page["facts_snapshot"]},
    )
    before = copy.deepcopy(workspace.read("facts"))

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        review_workspace.apply_review_batch(
            workspace,
            operation_id="op-stale-page-batch",
            **output,
        )
    assert workspace.read("facts") == before


def test_cli_file_and_stdout_are_byte_stable(tmp_path: Path) -> None:
    _, _, page = _setup(tmp_path / "source")
    request = _request(page)
    input_path = tmp_path / "review-decisions.json"
    first_path = tmp_path / "review-actions-first.json"
    second_path = tmp_path / "review-actions-second.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

    first = _run_cli("--input", str(input_path), "--output", str(first_path))
    second = _run_cli("--input", str(input_path), "--output", str(second_path))
    stdout = _run_cli("--input", str(input_path))

    assert first.returncode == second.returncode == stdout.returncode == 0
    expected = review_decision_tool._output_bytes(
        review_decision_tool.execute(request)
    )
    assert first_path.read_bytes() == second_path.read_bytes() == stdout.stdout
    assert stdout.stdout == expected


def test_same_input_output_and_replace_failure_preserve_existing_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, page = _setup(tmp_path / "source")
    request = _request(page)
    same_path = tmp_path / "same.json"
    same_bytes = json.dumps(request, ensure_ascii=False).encode("utf-8")
    same_path.write_bytes(same_bytes)

    completed = _run_cli(
        "--input",
        str(same_path),
        "--output",
        str(same_path),
    )
    assert completed.returncode == 2
    assert b"INPUT_OUTPUT_PATH_MUST_DIFFER" in completed.stderr
    assert same_path.read_bytes() == same_bytes

    output_path = tmp_path / "existing-output.json"
    original = b'{"keep":"old"}\n'
    output_path.write_bytes(original)

    def fail_replace(*args, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(review_decision_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        review_decision_tool._write_json_atomic(
            output_path,
            review_decision_tool.execute(request),
        )
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []

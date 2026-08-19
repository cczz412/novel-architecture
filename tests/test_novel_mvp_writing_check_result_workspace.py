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
    from mvp import writing_check_package_tool, writing_check_result_tool
    from mvp import writing_check_result_workspace
    from mvp.workspace import (
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


ALICE = "auth:t14-result-alice"
BOB = "auth:t14-result-bob"
TEXT = "林乔拆开邀请信。她没有立即答复。窗外传来一声雷。"


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _package(*, operation_id: str = "op-t14-check-r2") -> dict:
    must_text = "不得让林乔当场答应赴约"
    must_ref = writing_check_package_tool._must_not_ref(
        "S-0001@outline-r2", must_text
    )
    core = {
        "identity": writing_check_package_tool.PROTOTYPE_IDENTITY,
        "prototype": True,
        "check_operation_id": operation_id,
        "work": {
            "slot_ref": "S-0001",
            "work_ref": "S-0001@work",
            "work_rev": 2,
            "source_outline_ref": "S-0001@outline-r2",
            "text": TEXT,
            "text_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
        },
        "planning_source": {
            "source_plan_version": 4,
            "source_plan_sha256": "a" * 64,
            "generation_watermark": {
                "source_plan_version": 4,
                "source_plan_sha256": "a" * 64,
                "slot_rev": 3,
                "outline_source_commit_seq": 17,
            },
            "source_commit_seq": 17,
        },
        "requirements": [
            {
                "requirement_ref": "PE-0001",
                "source_kind": "planned_event",
                "source_text": "林乔拆开邀请信",
            },
            {
                "requirement_ref": must_ref,
                "source_kind": "must_not",
                "source_text": must_text,
            },
        ],
        "scope": {
            "mode": "chapter",
            "target_ref": "S-0001",
            "requirement_refs": ["PE-0001", must_ref],
        },
    }
    return {
        **core,
        "input_package_sha256": hashlib.sha256(
            writing_check_package_tool._canonical_bytes(core)
        ).hexdigest(),
    }


def _planned(
    requirement_ref: str,
    category: str,
    quote: str | None,
    explanation: str,
) -> dict:
    return {
        "category": category,
        "requirement_ref": requirement_ref,
        "evidence_quote": quote,
        "explanation": explanation,
    }


def _judgments(package: dict, *, second_category: str = "missing") -> list[dict]:
    refs = package["scope"]["requirement_refs"]
    second = _planned(
        refs[1],
        second_category,
        None if second_category == "missing" else "她没有立即答复。",
        "第二次判定。",
    )
    if second_category == "unknown":
        second["evidence_quote"] = "林乔拆开邀请信。"
        second["explanation"] = "当前文字不足以安全归类。"
    return [
        _planned(
            refs[0],
            "covered",
            "林乔拆开邀请信。",
            "原文明确写出拆信。",
        ),
        second,
        {
            "category": "unplanned",
            "requirement_ref": None,
            "evidence_quote": "窗外传来一声雷。",
            "explanation": "这个细节不在已冻结 requirement 中。",
        },
    ]


def _formal_result(
    package: dict | None = None,
    *,
    second_category: str = "missing",
) -> tuple[dict, dict]:
    package = _package() if package is None else package
    result = writing_check_result_tool.execute(
        {
            "input_package": package,
            "provider_response": {
                "judgments": _judgments(package, second_category=second_category),
            },
        }
    )
    return package, result


def _workspace(tmp_path: Path, principal: str = ALICE):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime = tmp_path / principal.replace(":", "-")
    handle = WorkspaceRouter(runtime).create_project(principal, "T14 结果项目")
    return runtime, handle


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _save(
    workspace,
    package: dict,
    result: dict,
    expected_version: int,
    expected_sha256: str | None = None,
    *,
    operation_id: str | None = None,
):
    return writing_check_result_workspace.save_writing_check_result(
        workspace,
        operation_id if operation_id is not None else result["operation_id"],
        package,
        result,
        expected_version,
        expected_sha256,
    )


def test_save_restart_resolve_reads_every_formal_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    package, result = _formal_result()
    before_result = copy.deepcopy(result)
    original_execute = writing_check_result_tool.execute
    execute_calls: list[dict] = []

    def capture_execute(request: dict) -> dict:
        execute_calls.append(copy.deepcopy(request))
        return original_execute(request)

    monkeypatch.setattr(writing_check_result_tool, "execute", capture_execute)
    receipt = _save(workspace, package, result, 0)
    reopened = WorkspaceRouter(runtime).open_project(ALICE, workspace.project_id)
    loaded = writing_check_result_workspace.resolve_writing_check_result(
        reopened,
        result["check_result_ref"],
    )

    assert receipt["replayed"] is False
    assert receipt["versions"] == {"writing_check_results": 1}
    assert len(execute_calls) == 1
    assert execute_calls[0]["input_package"] == package
    assert execute_calls[0]["provider_response"] == {
        "judgments": before_result["judgments"]
    }
    assert workspace.read("draft") is None
    assert workspace.read("plan") is None
    assert loaded["version"] == 1
    assert loaded["sha256"] == receipt["payload_sha256"]["writing_check_results"]
    assert loaded["result_sha256"] == _sha(result)
    assert loaded["result"] == before_result
    assert set(loaded["result"]) == writing_check_result_tool.RESULT_KEYS
    assert loaded["result"]["status"] == "completed"
    assert not ({"pass", "clean", "current", "all_clear"} & set(loaded["result"]))
    stored = reopened.read("writing_check_results")["payload"]
    assert stored["schema"] == "writing-check-results-v1"
    assert stored["results"][result["check_result_ref"]]["unknown_overlays"] == []
    assert "current" not in stored["results"][result["check_result_ref"]]
    loaded["result"]["status"] = "pass"
    assert writing_check_result_workspace.resolve_writing_check_result(
        reopened,
        result["check_result_ref"],
    )["result"] == before_result


def test_two_results_append_and_old_result_survives(tmp_path: Path) -> None:
    _, workspace = _workspace(tmp_path)
    first_package, first_result = _formal_result(_package(operation_id="op-t14-a"))
    second_package, second_result = _formal_result(
        _package(operation_id="op-t14-b"),
        second_category="unknown",
    )

    first_receipt = _save(workspace, first_package, first_result, 0)
    second_receipt = _save(
        workspace,
        second_package,
        second_result,
        1,
        first_receipt["payload_sha256"]["writing_check_results"],
    )

    assert first_receipt["versions"] == {"writing_check_results": 1}
    assert second_receipt["versions"] == {"writing_check_results": 2}
    assert writing_check_result_workspace.resolve_writing_check_result(
        workspace,
        first_result["check_result_ref"],
    )["result"] == first_result
    assert writing_check_result_workspace.resolve_writing_check_result(
        workspace,
        second_result["check_result_ref"],
    )["result"] == second_result


def test_same_ref_is_idempotent_and_different_content_conflicts(
    tmp_path: Path,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    package, result = _formal_result()
    first = _save(workspace, package, result, 0)
    before = _tree_bytes(runtime)
    replay = _save(workspace, package, result, 0)

    assert replay["replayed"] is True
    assert replay["generation_id"] == first["generation_id"]
    assert replay["versions"] == {"writing_check_results": 1}
    assert workspace.read("writing_check_results")["version"] == 1
    assert _tree_bytes(runtime) == before

    _, changed = _formal_result(package, second_category="unknown")
    changed_before = _tree_bytes(runtime)
    with pytest.raises(
        writing_check_result_workspace.WritingCheckResultWorkspaceError,
        match="CHECK_RESULT_REF_CONFLICT",
    ):
        _save(workspace, package, changed, 0)
    assert _tree_bytes(runtime) == changed_before
    assert writing_check_result_workspace.resolve_writing_check_result(
        workspace,
        result["check_result_ref"],
    )["result"] == result


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda package, result: result["judgments"].pop(0),
            "PLANNED_REQUIREMENT_COVERAGE_INCOMPLETE",
        ),
        (
            lambda package, result: result["judgments"][0].update(
                evidence_quote="原文里没有这句"
            ),
            "EVIDENCE_QUOTE_NOT_IN_WORK_TEXT",
        ),
        (
            lambda package, result: package.update(input_package_sha256="0" * 64),
            "INPUT_PACKAGE_SHA_MISMATCH",
        ),
        (
            lambda package, result: result.update(status="pass"),
            "CALLER_RESULT_MISMATCH",
        ),
        (
            lambda package, result: result.update(work_rev=99),
            "CALLER_RESULT_MISMATCH",
        ),
    ],
)
def test_bad_inputs_are_rejected_before_commit(
    tmp_path: Path,
    mutate,
    error: str,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    package, result = _formal_result()
    mutate(package, result)
    before = _tree_bytes(runtime)

    with pytest.raises(
        writing_check_result_tool.WritingCheckResultError,
        match=error,
    ):
        _save(workspace, package, result, 0)

    assert workspace.read("writing_check_results") is None
    assert _tree_bytes(runtime) == before


def test_expected_version_and_sha_conflict_have_zero_write(tmp_path: Path) -> None:
    runtime, workspace = _workspace(tmp_path)
    first_package, first_result = _formal_result(_package(operation_id="op-t14-a"))
    second_package, second_result = _formal_result(_package(operation_id="op-t14-b"))
    first = _save(workspace, first_package, first_result, 0)
    current = workspace.read("writing_check_results")
    before = _tree_bytes(runtime)

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        _save(workspace, second_package, second_result, 0)
    with pytest.raises(VersionConflictError, match="SHA_CONFLICT"):
        _save(
            workspace,
            second_package,
            second_result,
            1,
            "0" * 64,
        )

    assert _tree_bytes(runtime) == before
    assert workspace.read("writing_check_results") == current
    assert workspace.read("writing_check_results")["version"] == 1
    assert first["versions"] == {"writing_check_results": 1}


def test_corrupt_owner_path_and_cross_author_fail_closed(tmp_path: Path) -> None:
    runtime, alice = _workspace(tmp_path / "alice")
    package, result = _formal_result()
    _save(alice, package, result, 0)

    corrupt_runtime, corrupt = _workspace(tmp_path / "corrupt")
    corrupt.commit(
        "op-corrupt-results",
        {"writing_check_results": {"bad": True}},
        {"writing_check_results": 0},
    )
    before_corrupt = _tree_bytes(corrupt_runtime)
    with pytest.raises(
        writing_check_result_workspace.WritingCheckResultWorkspaceError,
        match="RESULTS_STORE_INVALID",
    ):
        writing_check_result_workspace.resolve_writing_check_result(
            corrupt,
            result["check_result_ref"],
        )
    with pytest.raises(
        writing_check_result_workspace.WritingCheckResultWorkspaceError,
        match="RESULTS_STORE_INVALID",
    ):
        _save(corrupt, package, result, 1, "0" * 64)
    assert _tree_bytes(corrupt_runtime) == before_corrupt

    other = WorkspaceRouter(runtime).create_project(ALICE, "另一本")
    with pytest.raises(
        writing_check_result_workspace.WritingCheckResultWorkspaceError,
        match="CHECK_RESULT_REF_NOT_FOUND",
    ):
        writing_check_result_workspace.resolve_writing_check_result(
            other,
            result["check_result_ref"],
        )

    bob_runtime, bob = _workspace(tmp_path / "bob", BOB)
    before_bob = _tree_bytes(bob_runtime)
    with pytest.raises(
        writing_check_result_workspace.WritingCheckResultWorkspaceError,
        match="CHECK_RESULT_REF_NOT_FOUND",
    ):
        writing_check_result_workspace.resolve_writing_check_result(
            bob,
            result["check_result_ref"],
        )
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        WorkspaceRouter(runtime).open_project(BOB, alice.project_id)
    assert _tree_bytes(bob_runtime) == before_bob

    caller_path = tmp_path / "caller-controlled-project"
    with pytest.raises(
        writing_check_result_workspace.WritingCheckResultWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        writing_check_result_workspace.save_writing_check_result(
            caller_path,  # type: ignore[arg-type]
            result["operation_id"],
            package,
            result,
            0,
            None,
        )
    with pytest.raises(
        writing_check_result_workspace.WritingCheckResultWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        writing_check_result_workspace.resolve_writing_check_result(
            caller_path,  # type: ignore[arg-type]
            result["check_result_ref"],
        )
    assert not caller_path.exists()
    assert writing_check_result_workspace.resolve_writing_check_result(
        alice,
        result["check_result_ref"],
    )["result"] == result


def test_new_process_resolve_is_byte_equivalent(tmp_path: Path) -> None:
    runtime, workspace = _workspace(tmp_path)
    package, result = _formal_result()
    _save(workspace, package, result, 0)
    loaded = writing_check_result_workspace.resolve_writing_check_result(
        workspace,
        result["check_result_ref"],
    )
    script = """
import json, sys
sys.path.insert(0, sys.argv[1])
from mvp.workspace import WorkspaceRouter
from mvp import writing_check_result_workspace
workspace = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4])
loaded = writing_check_result_workspace.resolve_writing_check_result(
    workspace, sys.argv[5]
)
sys.stdout.buffer.write(
    (
        json.dumps(
            loaded,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\\n"
    ).encode("utf-8")
)
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(PRODUCT_ROOT),
            str(runtime),
            ALICE,
            workspace.project_id,
            result["check_result_ref"],
        ],
        check=False,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == _canonical_bytes(loaded)


def test_public_signatures_have_no_path_or_identity() -> None:
    assert list(
        inspect.signature(
            writing_check_result_workspace.save_writing_check_result
        ).parameters
    ) == [
        "workspace",
        "operation_id",
        "input_package",
        "result",
        "expected_version",
        "expected_sha256",
    ]
    assert list(
        inspect.signature(
            writing_check_result_workspace.resolve_writing_check_result
        ).parameters
    ) == ["workspace", "check_result_ref"]

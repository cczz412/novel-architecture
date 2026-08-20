from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_PATH = PRODUCT_ROOT / "mvp" / "chapter_fact_handover_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import chapter_fact_draft_tool, chapter_fact_handover_tool
finally:
    sys.path.pop(0)


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


def _snapshot() -> dict:
    plan_sha = "a" * 64
    return {
        "contract": "CHAPTER_SLOT_SNAPSHOT",
        "version": "v1",
        "status": "plan",
        "source_plan_version": 4,
        "source_plan_sha256": plan_sha,
        "generation_watermark": {
            "source_plan_version": 4,
            "source_plan_sha256": plan_sha,
            "slot_rev": 3,
            "outline_source_commit_seq": 17,
        },
        "basis_refs": {
            "slot_ref": "S-0001",
            "scene_refs": ["SCN-0001"],
            "event_refs": ["PE-0001"],
            "storyline_refs": [],
        },
        "slot_ref": "S-0001",
        "slot_rev": 3,
        "goal": "让主角决定是否赴约",
        "summary": "作者计划了一个事件",
        "entry_state": "邀请仍未答复",
        "exit_condition": "主角作出选择",
        "exit_hook": "选择影响下一章",
        "storyline_refs": [],
        "scene_refs": ["SCN-0001"],
        "must_not": [],
        "risks": [],
        "outline_checkpoint": {
            "outline_rev": 2,
            "source_slot_ref": "S-0001",
            "source_commit_seq": 17,
        },
        "scenes": [
            {
                "id": "SCN-0001",
                "rev": 4,
                "slot_ref": "S-0001",
                "goal": "收到邀请",
                "summary": "主角看见邀请信",
                "pe_refs": ["PE-0001"],
            }
        ],
        "events": [
            {
                "id": "PE-0001",
                "rev": 5,
                "scene_ref": "SCN-0001",
                "text": "主角拆开邀请信",
            }
        ],
        "storylines": [],
    }


def _draft() -> dict:
    return chapter_fact_draft_tool.execute(
        {
            "operation_id": "op-chapter-fact-draft-01",
            "actor": "author",
            "chapter_slot_snapshot": _snapshot(),
            "entries": [
                {
                    "fact_text": "主角拆开了邀请信。",
                    "writing_note": "用近景写手指停顿。",
                },
                {
                    "fact_text": "主角决定赴约。",
                    "writing_note": "",
                },
            ],
        }
    )


def _request(title: str = "  雨夜赴约 / Rainy Meeting  ") -> dict:
    draft = _draft()
    return {
        "chapter_fact_draft": draft,
        "actor": "author",
        "operation_id": "op-chapter-fact-handover-01",
        "intent": "explicit_handover",
        "author_confirmed_title": title,
        "expected_prototype_sha256": draft["prototype_sha256"],
    }


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env=env,
    )


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key for child in value.values() for key in _all_keys(child)
        }
    if isinstance(value, list):
        return {key for child in value for key in _all_keys(child)}
    return set()


@pytest.mark.parametrize("title", ["第十章 雨夜", "  Rainy Meeting  "])
def test_records_explicit_author_title_without_copying_facts(title: str) -> None:
    request = _request(title)
    before = copy.deepcopy(request)

    first = chapter_fact_handover_tool.execute(request)
    second = chapter_fact_handover_tool.execute(copy.deepcopy(request))

    assert request == before
    assert _canonical_bytes(first) == _canonical_bytes(second)
    assert first["identity"] == "CHAPTER_FACT_DRAFT_HANDOVER_ACTION_PROTOTYPE_R01"
    assert first["prototype"] is True
    assert first["status"] == "REQUEST_RECORDED_NOT_APPLIED"
    assert first["author_confirmed_title"] == title
    assert first["source_prototype"] == {
        "identity": "CHAPTER_FACT_DRAFT_PROTOTYPE_R01",
        "operation_id": "op-chapter-fact-draft-01",
        "prototype_sha256": request["chapter_fact_draft"]["prototype_sha256"],
    }
    assert first["slot"] == request["chapter_fact_draft"]["slot"]
    assert first["planning_source"] == request["chapter_fact_draft"][
        "planning_source"
    ]
    assert first["effects"] == {
        "c11": "none",
        "chapter_ledger": "none",
        "facts": "none",
        "plan": "none",
    }
    assert "entries" not in first and "fact_text" not in _all_keys(first)
    core = copy.deepcopy(first)
    digest = core.pop("action_sha256")
    assert digest == hashlib.sha256(_canonical_bytes(core)).hexdigest()
    payload = _canonical_bytes(first)
    assert b"chapter_id" not in payload and b"revision" not in payload
    assert b"confirmed_facts" not in payload and b"completed" not in payload
    assert b'"current"' not in payload


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda value: value.update(actor="model"), "AUTHOR_ACTOR_REQUIRED"),
        (
            lambda value: value.update(intent="silent_handover"),
            "EXPLICIT_HANDOVER_INTENT_REQUIRED",
        ),
        (lambda value: value.update(author_confirmed_title=" \n "), "TITLE_INVALID"),
        (
            lambda value: value.update(expected_prototype_sha256="0" * 64),
            "EXPECTED_PROTOTYPE_SHA_MISMATCH",
        ),
        (
            lambda value: value.update(operation_id="op-chapter-fact-draft-01"),
            "NEW_OPERATION_ID_REQUIRED",
        ),
        (
            lambda value: value["chapter_fact_draft"]["entries"][0].update(
                fact_text="原型被篡改"
            ),
            "CHAPTER_FACT_DRAFT_INVALID:PROTOTYPE_SHA_MISMATCH",
        ),
        (
            lambda value: value.update(extra="forbidden"),
            "REQUEST_FIELDS_INVALID",
        ),
        (
            lambda value: value.pop("intent"),
            "REQUEST_FIELDS_INVALID",
        ),
    ],
)
def test_rejects_bad_author_intent_title_sha_or_shape(mutate, error: str) -> None:
    request = _request()
    mutate(request)
    with pytest.raises(chapter_fact_handover_tool.ChapterFactHandoverToolError, match=error):
        chapter_fact_handover_tool.execute(request)


def test_validate_result_and_render_keep_title_separate_from_fact_confirmation() -> None:
    result = chapter_fact_handover_tool.execute(_request())
    before = copy.deepcopy(result)

    validated = chapter_fact_handover_tool.validate_result(result)
    rendered = chapter_fact_handover_tool.render_result(result)

    assert result == before
    assert validated == result and validated is not result
    validated["author_confirmed_title"] = "改副本"
    assert result == before
    assert rendered.startswith("# 章事实稿交棒请求原型\n")
    assert "已记录交棒请求，但尚未写入章节账／事实账" in rendered
    assert _request()["author_confirmed_title"] in rendered
    assert result["source_prototype"]["prototype_sha256"] in rendered
    assert "标题确认只说明交棒时采用这个标题，不等于确认任何事实句" in rendered
    assert rendered.endswith(
        "- C11 写入：0\n- 章节账写入：0\n- 事实账写入：0\n- 规划账写入：0\n"
    )
    for forbidden in ("completed", "current", "confirmed_facts", "检查通过"):
        assert forbidden not in rendered


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda value: value.update(author_confirmed_title="标题被改"),
            "ACTION_SHA_MISMATCH",
        ),
        (
            lambda value: value["source_prototype"].update(
                prototype_sha256="0" * 64
            ),
            "ACTION_SHA_MISMATCH",
        ),
        (
            lambda value: value["slot"].update(slot_rev=4),
            "RESULT_WATERMARK_MISMATCH",
        ),
        (
            lambda value: value["planning_source"]["generation_watermark"].update(
                source_plan_version=99
            ),
            "RESULT_WATERMARK_MISMATCH",
        ),
        (
            lambda value: value["effects"].update(facts="written"),
            "RESULT_EFFECTS_INVALID",
        ),
        (
            lambda value: value.update(status="COMPLETED"),
            "RESULT_STATUS_INVALID",
        ),
        (
            lambda value: value.update(action_sha256="0" * 64),
            "ACTION_SHA_MISMATCH",
        ),
        (
            lambda value: value.update(extra="forbidden"),
            "RESULT_FIELDS_INVALID",
        ),
        (
            lambda value: value.pop("actor"),
            "RESULT_FIELDS_INVALID",
        ),
    ],
)
def test_validate_result_rejects_action_tampering(mutate, error: str) -> None:
    result = chapter_fact_handover_tool.execute(_request())
    mutate(result)
    with pytest.raises(chapter_fact_handover_tool.ChapterFactHandoverToolError, match=error):
        chapter_fact_handover_tool.validate_result(result)


def test_json_and_render_cli_are_stable_across_processes(tmp_path: Path) -> None:
    request_bytes = _canonical_bytes(_request())
    first = _run_cli(stdin=request_bytes)
    second = _run_cli(stdin=request_bytes)

    assert first.returncode == 0, first.stderr.decode()
    assert second.returncode == 0, second.stderr.decode()
    assert first.stdout == second.stdout
    result = json.loads(first.stdout)
    expected_render = chapter_fact_handover_tool.render_result(result).encode("utf-8")
    render_stdout = _run_cli("--render", stdin=first.stdout)
    output_path = tmp_path / "handover.md"
    render_file = _run_cli(
        "--render", "--output", str(output_path), stdin=first.stdout
    )

    assert render_stdout.returncode == 0, render_stdout.stderr.decode()
    assert render_file.returncode == 0, render_file.stderr.decode()
    assert render_stdout.stdout == expected_render
    assert output_path.read_bytes() == expected_render


@pytest.mark.parametrize("alias_kind", ["same", "symlink", "hardlink"])
def test_cli_rejects_input_output_aliases(tmp_path: Path, alias_kind: str) -> None:
    input_path = tmp_path / "request.json"
    input_path.write_bytes(_canonical_bytes(_request()))
    if alias_kind == "same":
        output_path = input_path
    elif alias_kind == "symlink":
        output_path = tmp_path / "request-link.json"
        output_path.symlink_to(input_path)
    else:
        output_path = tmp_path / "request-hardlink.json"
        os.link(input_path, output_path)
    before = input_path.read_bytes()

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 2
    assert b"INPUT_OUTPUT_PATH_MUST_DIFFER" in completed.stderr
    assert input_path.read_bytes() == before


def test_failed_cli_keeps_existing_output_and_removes_temp(tmp_path: Path) -> None:
    request = _request()
    request["actor"] = "model"
    input_path = tmp_path / "bad-request.json"
    output_path = tmp_path / "existing.json"
    input_path.write_bytes(_canonical_bytes(request))
    old_output = b'{"keep":"old"}\n'
    output_path.write_bytes(old_output)

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 2
    assert b"AUTHOR_ACTOR_REQUIRED" in completed.stderr
    assert output_path.read_bytes() == old_output
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []

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
TOOL_PATH = PRODUCT_ROOT / "mvp" / "chapter_fact_draft_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import chapter_fact_draft_tool
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
            "event_refs": ["PE-0002", "PE-0001"],
            "storyline_refs": [],
        },
        "slot_ref": "S-0001",
        "slot_rev": 3,
        "goal": "让主角决定是否赴约",
        "summary": "作者计划了两个事件",
        "entry_state": "邀请仍未答复",
        "exit_condition": "主角作出选择",
        "exit_hook": "选择影响下一章",
        "storyline_refs": [],
        "scene_refs": ["SCN-0001"],
        "must_not": ["不得把规划冒充事实"],
        "risks": ["动机可能不足"],
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
                "pe_refs": ["PE-0002", "PE-0001"],
            }
        ],
        "events": [
            {
                "id": "PE-0002",
                "rev": 2,
                "scene_ref": "SCN-0001",
                "text": "主角拆开邀请信",
            },
            {
                "id": "PE-0001",
                "rev": 5,
                "scene_ref": "SCN-0001",
                "text": "主角犹豫是否赴约",
            },
        ],
        "storylines": [],
    }


def _entries() -> list[dict[str, str]]:
    repeated = "  林照收起钥匙。\r\n"
    return [
        {
            "fact_text": repeated,
            "writing_note": "用短句，停在动作上。\n不要解释。",
        },
        {
            "fact_text": "许岚没有拆开密封信。",
            "writing_note": "",
        },
        {
            "fact_text": repeated,
            "writing_note": "重复是作者明确保留的节奏回环。",
        },
    ]


def _request() -> dict:
    return {
        "operation_id": "op-chapter-fact-draft-01",
        "actor": "author",
        "chapter_slot_snapshot": _snapshot(),
        "entries": _entries(),
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


def test_author_entries_are_preserved_in_order_with_stable_sha() -> None:
    request = _request()
    before = copy.deepcopy(request)

    first = chapter_fact_draft_tool.execute(request)
    second = chapter_fact_draft_tool.execute(copy.deepcopy(request))

    assert request == before
    assert _canonical_bytes(first) == _canonical_bytes(second)
    assert first["identity"] == "CHAPTER_FACT_DRAFT_PROTOTYPE_R01"
    assert first["prototype"] is True
    assert first["actor"] == "author"
    assert first["entries"] == _entries()
    assert first["entries"][0]["fact_text"] == first["entries"][2]["fact_text"]
    assert first["slot"] == {
        "slot_ref": "S-0001",
        "slot_rev": 3,
        "source_outline_ref": "S-0001@outline-r2",
    }
    assert first["planning_source"]["source_commit_seq"] == 17
    assert first["effects"] == {"c11": "none", "facts": "none", "plan": "none"}
    core = copy.deepcopy(first)
    digest = core.pop("prototype_sha256")
    assert digest == hashlib.sha256(_canonical_bytes(core)).hexdigest()
    forbidden_keys = {"chapter_id", "fact_id", "confirmed", "current", "contract"}
    assert forbidden_keys.isdisjoint(_all_keys(first))
    payload = _canonical_bytes(first)
    assert b"C1_CHAPTER_DOC" not in payload
    assert b"C3_FACT_CANDIDATE" not in payload
    assert b"C4_FACT_QUERY" not in payload
    assert b"CHAPTER_REVISION_LEDGER" not in payload


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda value: value.update(actor="model"), "AUTHOR_ACTOR_REQUIRED"),
        (lambda value: value.update(entries=[]), "ENTRIES_MUST_BE_NONEMPTY_ARRAY"),
        (
            lambda value: value["entries"][0].update(fact_text=" \n\t "),
            "FACT_TEXT_INVALID:0",
        ),
        (
            lambda value: value["entries"][0].update(writing_note=None),
            "WRITING_NOTE_INVALID:0",
        ),
        (
            lambda value: value["entries"][0].update(extra="forbidden"),
            "ENTRY_FIELDS_INVALID:0",
        ),
        (
            lambda value: value["entries"][0].pop("writing_note"),
            "ENTRY_FIELDS_INVALID:0",
        ),
        (
            lambda value: value.update(extra="forbidden"),
            "REQUEST_FIELDS_INVALID",
        ),
        (
            lambda value: value.pop("actor"),
            "REQUEST_FIELDS_INVALID",
        ),
    ],
)
def test_rejects_bad_author_or_entry_shape(mutate, error: str) -> None:
    request = _request()
    mutate(request)
    with pytest.raises(chapter_fact_draft_tool.ChapterFactDraftToolError, match=error):
        chapter_fact_draft_tool.execute(request)


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda value: value["chapter_slot_snapshot"].update(contract="WRONG"),
            "CHAPTER_SLOT_SNAPSHOT_INVALID",
        ),
        (
            lambda value: value["chapter_slot_snapshot"]["generation_watermark"].update(
                source_plan_version=99
            ),
            "CHAPTER_SLOT_WATERMARK_MISMATCH",
        ),
        (
            lambda value: value["chapter_slot_snapshot"]["generation_watermark"].update(
                source_plan_sha256="b" * 64
            ),
            "CHAPTER_SLOT_WATERMARK_MISMATCH",
        ),
        (
            lambda value: value["chapter_slot_snapshot"]["generation_watermark"].update(
                slot_rev=99
            ),
            "CHAPTER_SLOT_WATERMARK_MISMATCH",
        ),
        (
            lambda value: value["chapter_slot_snapshot"].update(outline_checkpoint=None),
            "CURRENT_OUTLINE_CHECKPOINT_REQUIRED",
        ),
        (
            lambda value: value["chapter_slot_snapshot"]["outline_checkpoint"].update(
                source_slot_ref="S-9999"
            ),
            "OUTLINE_CHECKPOINT_SLOT_MISMATCH",
        ),
        (
            lambda value: value["chapter_slot_snapshot"]["generation_watermark"].update(
                outline_source_commit_seq=999
            ),
            "OUTLINE_COMMIT_WATERMARK_MISMATCH",
        ),
        (
            lambda value: value["chapter_slot_snapshot"]["basis_refs"].update(
                slot_ref="S-9999"
            ),
            "CHAPTER_SLOT_BASIS_MISMATCH",
        ),
        (
            lambda value: value["chapter_slot_snapshot"]["events"].reverse(),
            "CHAPTER_SLOT_EVENT_ORDER_MISMATCH",
        ),
    ],
)
def test_rejects_bad_snapshot_or_watermark(mutate, error: str) -> None:
    request = _request()
    mutate(request)
    with pytest.raises(chapter_fact_draft_tool.ChapterFactDraftToolError, match=error):
        chapter_fact_draft_tool.execute(request)


def test_stdin_stdout_is_byte_stable_across_processes() -> None:
    input_bytes = _canonical_bytes(_request())

    first = _run_cli(stdin=input_bytes)
    second = _run_cli(stdin=input_bytes)

    assert first.returncode == 0, first.stderr.decode()
    assert second.returncode == 0, second.stderr.decode()
    assert first.stdout == second.stdout == _canonical_bytes(
        chapter_fact_draft_tool.execute(_request())
    )


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


def test_validate_result_returns_deep_copy_and_render_is_author_readable() -> None:
    result = chapter_fact_draft_tool.execute(_request())
    before = copy.deepcopy(result)

    validated = chapter_fact_draft_tool.validate_result(result)
    rendered = chapter_fact_draft_tool.render_result(result)

    assert result == before
    assert validated == result and validated is not result
    validated["entries"][0]["fact_text"] = "调用方改了副本"
    assert result == before
    assert rendered.startswith("# 章事实稿原型｜尚未交棒｜尚未进入事实账\n")
    assert "- 章槽：`S-0001`" in rendered
    assert "- 章纲来源：`S-0001@outline-r2`" in rendered
    assert "- 规划版本：`4`" in rendered
    assert "- 规划提交水位：`17`" in rendered
    assert "- 操作号：`op-chapter-fact-draft-01`" in rendered
    first_position = rendered.index(_entries()[0]["fact_text"])
    second_position = rendered.index(_entries()[1]["fact_text"])
    repeated_position = rendered.rindex(_entries()[2]["fact_text"])
    assert first_position < second_position < repeated_position
    assert rendered.count("**写法批注**") == 2
    assert "写法批注\n\n    \n" not in rendered
    assert rendered.endswith(
        "- C11 写入：0\n- 事实账写入：0\n- 规划账写入：0\n"
    )
    for forbidden in ("已确认", "当前版", "可交棒", "检查通过"):
        assert forbidden not in rendered


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda value: value["entries"][0].update(fact_text="事实被改了"),
            "PROTOTYPE_SHA_MISMATCH",
        ),
        (
            lambda value: value["entries"][0].update(writing_note="批注被改了"),
            "PROTOTYPE_SHA_MISMATCH",
        ),
        (
            lambda value: value["entries"].reverse(),
            "PROTOTYPE_SHA_MISMATCH",
        ),
        (
            lambda value: value["planning_source"].update(source_plan_version=5),
            "RESULT_WATERMARK_MISMATCH",
        ),
        (
            lambda value: value["planning_source"]["generation_watermark"].update(
                source_plan_sha256="b" * 64
            ),
            "RESULT_WATERMARK_MISMATCH",
        ),
        (
            lambda value: value["slot"].update(
                source_outline_ref="S-0001@outline-r0"
            ),
            "RESULT_OUTLINE_REF_INVALID",
        ),
        (
            lambda value: value["effects"].update(c11="written"),
            "RESULT_EFFECTS_INVALID",
        ),
        (
            lambda value: value.update(prototype_sha256="0" * 64),
            "PROTOTYPE_SHA_MISMATCH",
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
def test_validate_result_rejects_tampering(mutate, error: str) -> None:
    result = chapter_fact_draft_tool.execute(_request())
    mutate(result)
    with pytest.raises(chapter_fact_draft_tool.ChapterFactDraftToolError, match=error):
        chapter_fact_draft_tool.validate_result(result)


def test_render_stdout_and_file_are_stable_across_processes(tmp_path: Path) -> None:
    result = chapter_fact_draft_tool.execute(_request())
    result_bytes = _canonical_bytes(result)

    first = _run_cli("--render", stdin=result_bytes)
    second = _run_cli("--render", stdin=result_bytes)
    output_path = tmp_path / "chapter-fact-draft.md"
    file_run = _run_cli("--render", "--output", str(output_path), stdin=result_bytes)

    expected = chapter_fact_draft_tool.render_result(result).encode("utf-8")
    assert first.returncode == 0, first.stderr.decode()
    assert second.returncode == 0, second.stderr.decode()
    assert file_run.returncode == 0, file_run.stderr.decode()
    assert first.stdout == second.stdout == expected
    assert output_path.read_bytes() == expected


def test_failed_render_keeps_existing_output_and_removes_temp(tmp_path: Path) -> None:
    result = chapter_fact_draft_tool.execute(_request())
    result["entries"][0]["fact_text"] = "篡改后没有更新 SHA"
    input_path = tmp_path / "bad-result.json"
    output_path = tmp_path / "existing.md"
    input_path.write_bytes(_canonical_bytes(result))
    old_output = b"keep old markdown\n"
    output_path.write_bytes(old_output)

    completed = _run_cli(
        "--render",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    )

    assert completed.returncode == 2
    assert b"PROTOTYPE_SHA_MISMATCH" in completed.stderr
    assert output_path.read_bytes() == old_output
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []

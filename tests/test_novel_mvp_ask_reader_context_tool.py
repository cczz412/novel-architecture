from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_SCRIPT = PRODUCT_ROOT / "mvp/ask_reader_context_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        ask_reader_context_tool,
        ask_reader_context_workspace,
        ask_tool,
    )
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)


PRINCIPAL = "auth:m6-reader-context-render"
VISIBLE_QUOTE = "顾遥在第四章收起银戒指"
FUTURE_QUOTE = "第六章揭晓银戒指里藏着王室密令"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text(chapter_id: str) -> str:
    if chapter_id == "c04":
        return f"门外雨声渐密。{VISIBLE_QUOTE}，没有解释来历。"
    if chapter_id == "c06":
        return f"所有人到齐后，{FUTURE_QUOTE}。"
    return f"{chapter_id} 只记录不涉及银戒指谜底的日常行程。"


def _ref(chapter_id: str) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": 1,
        "revision_text_sha256": _sha(_text(chapter_id)),
    }


def _chapter(chapter_id: str) -> dict:
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": f"第{int(chapter_id[1:])}章",
        "kind": "draft",
        "text": _text(chapter_id),
        "added_at": "2026-08-20 00:00:00",
        "chapter_revision_ref": _ref(chapter_id),
    }


def _fact(fact_id: str, chapter_id: str, quote: str) -> dict:
    ref = _ref(chapter_id)
    start = _text(chapter_id).index(quote)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter_id,
        "text": f"{quote}。",
        "quote": quote,
        "status": "confirmed",
        "source": "M6_READER_CONTEXT_RENDER_SYNTHETIC",
        "note": "",
        "added_at": "2026-08-20 00:01:00",
        "seg": 1,
        "decided_at": "2026-08-20 00:02:00",
        "chapter_revision_ref": copy.deepcopy(ref),
        "anchor_ref": {
            **copy.deepcopy(ref),
            "coordinate_basis": ask_tool.COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _source_result(tmp_path: Path, *, query: str = "银戒指", cutoff: str = "c05") -> dict:
    workspace = WorkspaceRouter(tmp_path / f"runtime-{cutoff}-{_sha(query)[:6]}").create_project(
        PRINCIPAL,
        "人读证据",
    )
    chapters = [_chapter(f"c{number:02d}") for number in range(1, 7)]
    refs = [copy.deepcopy(chapter["chapter_revision_ref"]) for chapter in chapters]
    facts = [
        _fact("f004", "c04", VISIBLE_QUOTE),
        _fact("f006", "c06", FUTURE_QUOTE),
    ]
    workspace.commit(
        "op-reader-context-render-base",
        {"facts": facts, "chapter_index": refs, "chapters": chapters},
        {"facts": 0, "chapter_index": 0, "chapters": 0},
    )
    return ask_reader_context_workspace.execute(
        workspace,
        query,
        cutoff,
        5,
        6,
    )


def _all_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _all_strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _all_strings(item)]
    return []


def test_previous_workspace_result_renders_c04_without_c06_secret(
    tmp_path: Path,
) -> None:
    result = _source_result(tmp_path)
    before = copy.deepcopy(result)

    rendered = ask_reader_context_tool.render_result(result)

    assert "原问题：银戒指" in rendered
    assert "截至章节：c05" in rendered
    assert "防剧透声明" in rendered
    assert "可见章节 5，未来章节 1，拦截未来事实 1" in rendered
    assert "事实 f004" in rendered
    assert VISIBLE_QUOTE in rendered
    assert f"anchor SHA-256：{_sha(VISIBLE_QUOTE)}" in rendered
    assert f"【{VISIBLE_QUOTE}】" in rendered
    assert "f006" not in rendered
    assert "c06" not in rendered
    assert FUTURE_QUOTE not in rendered
    assert result == before
    assert ask_reader_context_tool.validate_result(result) == result


def test_empty_result_uses_evidence_gate_wording_only(tmp_path: Path) -> None:
    result = _source_result(tmp_path, query="不存在的线索")

    rendered = ask_reader_context_tool.render_result(result)

    assert "命中：0 条" in rendered
    assert "截至该章和当前证据门下，没有符合当前版本与证据门的命中。" in rendered
    assert "故事里不存在" not in rendered
    assert "剧情结论" not in rendered


@pytest.mark.parametrize(
    "damage",
    ["missing_visible", "extra_visible", "reordered_visible", "count_mismatch"],
)
def test_missing_extra_reordered_or_unclosed_visible_refs_are_rejected(
    tmp_path: Path,
    damage: str,
) -> None:
    result = _source_result(tmp_path)
    damaged = copy.deepcopy(result)
    refs = damaged["visible_chapter_revision_refs"]
    scope = damaged["m6"]["reader_scope"]
    if damage == "missing_visible":
        refs.pop(3)
        scope["visible_chapter_count"] = 4
        scope["future_chapter_count"] = 2
    elif damage == "extra_visible":
        refs.append(_ref("c06"))
    elif damage == "reordered_visible":
        refs.reverse()
    else:
        scope["visible_chapter_count"] = 4

    with pytest.raises(ask_reader_context_tool.AskReaderContextToolError):
        ask_reader_context_tool.validate_result(damaged)


@pytest.mark.parametrize(
    "damage",
    ["future_evidence", "highlight", "anchor", "cutoff", "watermark"],
)
def test_future_or_cross_reference_damage_is_rejected(
    tmp_path: Path,
    damage: str,
) -> None:
    result = _source_result(tmp_path)
    damaged = copy.deepcopy(result)
    if damage == "future_evidence":
        through_six = _source_result(tmp_path, cutoff="c06")
        future_match = next(
            item for item in through_six["m6"]["matches"] if item["fact_id"] == "f006"
        )
        future_evidence = next(
            item for item in through_six["m6"]["evidence"] if item["fact_id"] == "f006"
        )
        damaged["m6"]["matches"].append(copy.deepcopy(future_match))
        damaged["m6"]["evidence"].append(copy.deepcopy(future_evidence))
    elif damage == "highlight":
        damaged["m6"]["evidence"][0]["context"]["highlight_start"] += 1
    elif damage == "anchor":
        damaged["m6"]["evidence"][0]["anchor_ref"]["start"] += 1
    elif damage == "cutoff":
        damaged["m6"]["reader_scope"]["as_of_chapter_id"] = "c04"
    else:
        damaged["chapters_snapshot"]["sha256"] = "bad"

    with pytest.raises(ask_reader_context_tool.AskReaderContextToolError):
        ask_reader_context_tool.render_result(damaged)


def test_cli_file_and_stdio_are_byte_stable_and_never_overwrite_input(
    tmp_path: Path,
) -> None:
    result = _source_result(tmp_path)
    input_path = tmp_path / "result.json"
    output_path = tmp_path / "result.txt"
    input_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    file_run = subprocess.run(
        [
            sys.executable,
            str(TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        env=environment,
    )
    stdio_run = subprocess.run(
        [sys.executable, str(TOOL_SCRIPT)],
        input=input_path.read_bytes(),
        check=False,
        capture_output=True,
        env=environment,
    )

    expected = ask_reader_context_tool.render_result(result).encode("utf-8")
    assert file_run.returncode == 0, file_run.stderr.decode("utf-8")
    assert stdio_run.returncode == 0, stdio_run.stderr.decode("utf-8")
    assert output_path.read_bytes() == expected
    assert stdio_run.stdout == expected

    before = input_path.read_bytes()
    same_path = subprocess.run(
        [
            sys.executable,
            str(TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(input_path),
        ],
        check=False,
        capture_output=True,
        env=environment,
    )
    assert same_path.returncode == 2
    assert input_path.read_bytes() == before


def test_render_file_replace_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _source_result(tmp_path)
    input_path = tmp_path / "result.json"
    output_path = tmp_path / "result.txt"
    input_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    output_path.write_text("旧结果不得覆盖\n", encoding="utf-8")
    before = output_path.read_bytes()

    monkeypatch.setattr(
        ask_reader_context_tool.os,
        "replace",
        lambda *args: (_ for _ in ()).throw(OSError("synthetic replace failure")),
    )
    code = ask_reader_context_tool.main(
        ["--input", str(input_path), "--output", str(output_path)],
        stderr=io.StringIO(),
    )

    assert code == 2
    assert output_path.read_bytes() == before
    assert not list(tmp_path.glob(".result.txt.*.tmp"))

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_SCRIPT = PRODUCT_ROOT / "mvp/ask_context_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import ask_context_tool, ask_tool
finally:
    sys.path.pop(0)


TEXT = "开头钥匙。" + "甲" * 10 + "中间印章。" + "乙" * 10 + "结尾铜铃。"
QUOTES = ["开头钥匙", "中间印章", "结尾铜铃。"]


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _ref(*, revision_no: int = 2, text: str = TEXT) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": _sha(text),
    }


def _chapter(*, revision_no: int = 2, text: str = TEXT) -> dict:
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": "c01",
        "title": "第一章 合成证据",
        "kind": "draft",
        "text": text,
        "added_at": "2026-08-19 20:00:00",
        "chapter_revision_ref": _ref(revision_no=revision_no, text=text),
    }


def _pair(number: int, quote: str, *, revision_ref: dict | None = None) -> tuple[dict, dict]:
    ref = copy.deepcopy(revision_ref or _ref())
    start = TEXT.index(quote)
    fact_id = f"f{number:03d}"
    match = {
        "fact_id": fact_id,
        "chapter_id": "c01",
        "text": f"{quote}是当前章节中的已确认事实。",
        "chapter_revision_ref": copy.deepcopy(ref),
    }
    evidence = {
        "fact_id": fact_id,
        "source": "M6_SYNTHETIC_QUERY",
        "quote": quote,
        "chapter_revision_ref": copy.deepcopy(ref),
        "anchor_ref": {
            **copy.deepcopy(ref),
            "coordinate_basis": ask_tool.COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": _sha(quote),
        },
    }
    return match, evidence


def _m6_result(*quotes: str) -> dict:
    pairs = [_pair(index, quote) for index, quote in enumerate(quotes, start=1)]
    return {
        "query": "钥匙 印章 铜铃",
        "matches": [pair[0] for pair in pairs],
        "evidence": [pair[1] for pair in pairs],
        "excluded_counts": {key: 0 for key in ask_tool.EXCLUDED_COUNT_KEYS},
    }


def _request(*quotes: str, before: int = 3, after: int = 4) -> dict:
    return {
        "m6_result": _m6_result(*quotes),
        "current_chapters": [_chapter()],
        "before_chars": before,
        "after_chars": after,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_chapter_start_middle_end_windows_and_multiple_evidence() -> None:
    request = _request(*QUOTES)
    before = copy.deepcopy(request)

    result = ask_context_tool.execute(request)

    assert result["query"] == before["m6_result"]["query"]
    assert result["matches"] == before["m6_result"]["matches"]
    assert result["excluded_counts"] == before["m6_result"]["excluded_counts"]
    assert len(result["evidence"]) == 3
    contexts = [item["context"] for item in result["evidence"]]
    assert contexts[0]["window_start"] == 0
    assert contexts[-1]["window_end"] == len(TEXT)
    for quote, context in zip(QUOTES, contexts):
        highlighted = context["text"][context["highlight_start"] : context["highlight_end"]]
        assert highlighted == quote
        assert context["window_end"] - context["window_start"] == len(context["text"])
    assert request == before


@pytest.mark.parametrize("fault", ["duplicate_match", "duplicate_evidence", "orphan_match", "orphan_evidence"])
def test_duplicate_or_orphan_pair_is_rejected(fault: str) -> None:
    request = _request(QUOTES[0], QUOTES[1])
    result = request["m6_result"]
    if fault == "duplicate_match":
        result["matches"].append(copy.deepcopy(result["matches"][0]))
    elif fault == "duplicate_evidence":
        result["evidence"].append(copy.deepcopy(result["evidence"][0]))
    elif fault == "orphan_match":
        result["evidence"].pop()
    else:
        result["matches"].pop()

    with pytest.raises(ask_context_tool.AskContextError):
        ask_context_tool.execute(request)


def test_old_revision_is_rejected_against_current_c1() -> None:
    old_text = TEXT + "旧版"
    old_ref = _ref(revision_no=1, text=old_text)
    match, evidence = _pair(1, QUOTES[0], revision_ref=old_ref)
    request = _request(QUOTES[0])
    request["m6_result"]["matches"] = [match]
    request["m6_result"]["evidence"] = [evidence]

    with pytest.raises(ask_context_tool.AskContextError, match="M6_EVIDENCE_NOT_CURRENT_C1"):
        ask_context_tool.execute(request)


@pytest.mark.parametrize("fault", ["bad_slice_sha", "bad_start", "quote_mismatch"])
def test_bad_anchor_or_quote_sha_is_rejected(fault: str) -> None:
    request = _request(QUOTES[1])
    evidence = request["m6_result"]["evidence"][0]
    if fault == "bad_slice_sha":
        evidence["anchor_ref"]["slice_sha256"] = "0" * 64
    elif fault == "bad_start":
        evidence["anchor_ref"]["start"] += 1
        evidence["anchor_ref"]["end"] += 1
    else:
        evidence["quote"] = "不存在的引文"
        evidence["anchor_ref"]["end"] = evidence["anchor_ref"]["start"] + len(
            evidence["quote"]
        )
        evidence["anchor_ref"]["slice_sha256"] = _sha(evidence["quote"])

    with pytest.raises(ask_context_tool.AskContextError):
        ask_context_tool.execute(request)


@pytest.mark.parametrize("before,after", [(-1, 2), (2, -1), (True, 2), (2, "3")])
def test_invalid_window_parameters_are_rejected(before, after) -> None:
    with pytest.raises(ask_context_tool.AskContextError, match="CONTEXT_WINDOW_PARAMETER_INVALID"):
        ask_context_tool.execute(_request(QUOTES[0], before=before, after=after))


def test_file_result_matches_object_core_and_is_stable_after_restart(tmp_path: Path) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "result.json"
    request = _request(*QUOTES)
    _write_json(input_path, request)

    completed = subprocess.run(
        [sys.executable, str(TOOL_SCRIPT), "--input", str(input_path), "--output", str(output_path)],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert completed.returncode == 0, completed.stderr
    first_bytes = output_path.read_bytes()
    assert json.loads(first_bytes) == ask_context_tool.execute(request)
    completed_again = subprocess.run(
        [sys.executable, str(TOOL_SCRIPT), "--input", str(input_path), "--output", str(output_path)],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed_again.returncode == 0, completed_again.stderr
    assert output_path.read_bytes() == first_bytes


def test_bad_input_and_replace_failure_do_not_overwrite_previous_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "result.json"
    request = _request(QUOTES[0])
    _write_json(input_path, request)
    assert ask_context_tool.main(["--input", str(input_path), "--output", str(output_path)]) == 0
    before = output_path.read_bytes()

    broken = copy.deepcopy(request)
    broken["m6_result"]["evidence"][0]["anchor_ref"]["slice_sha256"] = "0" * 64
    _write_json(input_path, broken)
    stderr = io.StringIO()
    assert ask_context_tool.main(
        ["--input", str(input_path), "--output", str(output_path)],
        stderr=stderr,
    ) == 2
    assert output_path.read_bytes() == before

    _write_json(input_path, request)
    monkeypatch.setattr(
        ask_context_tool.os,
        "replace",
        lambda *args: (_ for _ in ()).throw(OSError("synthetic replace failure")),
    )
    assert ask_context_tool.main(
        ["--input", str(input_path), "--output", str(output_path)],
        stderr=io.StringIO(),
    ) == 2
    assert output_path.read_bytes() == before
    assert not list(tmp_path.glob(".result.json.*.tmp"))

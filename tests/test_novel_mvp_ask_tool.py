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
ASK_TOOL_SCRIPT = PRODUCT_ROOT / "mvp" / "ask_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import ask_tool
finally:
    sys.path.pop(0)


CURRENT_TEXT = "林乔把铜钥匙交给苏晚。苏晚把钥匙收进黑色文件袋。"
OLD_TEXT = "林乔把旧钥匙放在桌上。"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _revision_ref(
    *,
    revision_no: int = 2,
    text: str = CURRENT_TEXT,
) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": _sha(text),
    }


def _fact(
    fact_id: str,
    *,
    text: str = "林乔把铜钥匙交给苏晚。",
    quote: str = "把铜钥匙交给苏晚",
    status: str = "confirmed",
    revision_no: int = 2,
    revision_text: str = CURRENT_TEXT,
    anchor_state: str = "VERIFIED",
) -> dict:
    start = revision_text.index(quote) if quote in revision_text else 0
    revision_ref = _revision_ref(revision_no=revision_no, text=revision_text)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": "c01",
        "text": text,
        "quote": quote,
        "status": status,
        "source": "fixture-c4-snapshot",
        "note": "",
        "added_at": "2026-08-19 10:00:00",
        "seg": 1,
        "decided_at": "2026-08-19 10:01:00",
        "chapter_revision_ref": revision_ref,
        "anchor_ref": (
            {
                **revision_ref,
                "coordinate_basis": ask_tool.COORDINATE_BASIS,
                "start": start,
                "end": start + len(quote),
                "slice_sha256": _sha(quote),
            }
            if anchor_state == "VERIFIED"
            else None
        ),
        "anchor_state": anchor_state,
        "recheck": (
            {
                "previous_status": "confirmed",
                "reason": "evidence_gone",
                "from_revision_no": 1,
                "target_revision_no": 2,
                "flagged_at": "2026-08-19 10:02:00",
            }
            if status == "needs_recheck"
            else None
        ),
    }


def _request(*facts: dict, query: str = "钥匙 苏晚") -> dict:
    return {
        "query": query,
        "facts": list(facts),
        "current_revision_refs": [_revision_ref()],
    }


def test_keyword_query_only_returns_current_confirmed_verified_c4() -> None:
    current = _fact("f001")
    extracted = _fact("f002", status="extracted")
    rejected = _fact("f003", status="rejected")
    needs_recheck = _fact("f004", status="needs_recheck")
    stale = _fact(
        "f005",
        text="林乔把旧钥匙交给苏晚。",
        quote="把旧钥匙放在桌上",
        revision_no=1,
        revision_text=OLD_TEXT,
    )
    unverified = _fact("f006", anchor_state="LEGACY_UNVERIFIED")

    result = ask_tool.execute(
        _request(current, extracted, rejected, needs_recheck, stale, unverified)
    )

    assert [row["fact_id"] for row in result["matches"]] == ["f001"]
    assert [row["fact_id"] for row in result["evidence"]] == ["f001"]
    assert result["excluded_counts"] == {
        "invalid_c4_v1": 0,
        "extracted": 1,
        "rejected": 1,
        "needs_recheck": 1,
        "current_revision_missing": 0,
        "stale_revision": 1,
        "unverified_evidence": 1,
        "invalid_evidence": 0,
        "keyword_miss": 0,
    }


def test_no_result_is_parseable_and_counts_eligible_keyword_miss() -> None:
    result = ask_tool.execute(_request(_fact("f001"), query="雨伞"))

    assert result["query"] == "雨伞"
    assert result["matches"] == []
    assert result["evidence"] == []
    assert result["excluded_counts"]["keyword_miss"] == 1
    json.loads(json.dumps(result, ensure_ascii=False))


def test_old_revision_is_excluded_even_when_status_and_keyword_match() -> None:
    stale = _fact(
        "f001",
        text="林乔把旧钥匙交给苏晚。",
        quote="把旧钥匙放在桌上",
        revision_no=1,
        revision_text=OLD_TEXT,
    )

    result = ask_tool.execute(_request(stale))

    assert result["matches"] == []
    assert result["excluded_counts"]["stale_revision"] == 1


def test_evidence_preserves_source_span_sha_and_revision_ref() -> None:
    fact = _fact("f001")
    before = copy.deepcopy(fact)

    result = ask_tool.execute(_request(fact))

    assert result["evidence"] == [
        {
            "fact_id": "f001",
            "source": fact["source"],
            "quote": fact["quote"],
            "chapter_revision_ref": fact["chapter_revision_ref"],
            "anchor_ref": fact["anchor_ref"],
        }
    ]
    assert result["evidence"][0]["anchor_ref"]["slice_sha256"] == _sha(
        fact["quote"]
    )
    assert fact == before


def test_cli_local_file_round_trip_can_be_read_back(tmp_path: Path) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "result.json"
    input_path.write_text(
        json.dumps(_request(_fact("f001")), ensure_ascii=False),
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            str(ASK_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    reread = json.loads(output_path.read_text(encoding="utf-8"))
    assert reread["matches"][0]["fact_id"] == "f001"
    assert set(reread) == {"query", "matches", "evidence", "excluded_counts"}


def test_cli_stdin_stdout_round_trip() -> None:
    payload = json.dumps(_request(_fact("f001")), ensure_ascii=False)
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        [sys.executable, str(ASK_TOOL_SCRIPT)],
        input=payload,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["matches"][0]["fact_id"] == "f001"


def test_cli_stdin_ascii_encoding_cannot_carry_chinese_payload() -> None:
    payload = json.dumps(_request(_fact("f001")), ensure_ascii=False)
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONIOENCODING", None)

    with pytest.raises(UnicodeEncodeError):
        subprocess.run(
            [sys.executable, str(ASK_TOOL_SCRIPT)],
            input=payload,
            check=False,
            capture_output=True,
            text=True,
            encoding="ascii",
            env=environment,
        )


def test_atomic_write_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "result.json"
    output_path.write_text('{"sentinel":"old"}\n', encoding="utf-8")
    before = output_path.read_bytes()

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(ask_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic replace failure"):
        ask_tool._atomic_write_json(
            output_path,
            ask_tool.execute(_request(_fact("f001"))),
        )

    assert output_path.read_bytes() == before
    assert list(tmp_path.glob(".result.json.*.tmp")) == []


def test_execute_rejects_paths_and_requires_in_memory_objects() -> None:
    with pytest.raises(ask_tool.AskToolError, match="request 必须是对象"):
        ask_tool.execute(Path("facts.json"))  # type: ignore[arg-type]


def test_render_one_and_multiple_matches_with_complete_evidence() -> None:
    first = _fact("f001")
    second = _fact(
        "f002",
        text="苏晚把钥匙收进黑色文件袋。",
        quote="把钥匙收进黑色文件袋",
    )
    result = ask_tool.execute(_request(first, second, query="钥匙"))
    before = copy.deepcopy(result)

    rendered = ask_tool.render_result(result)

    assert "原查询：钥匙" in rendered
    assert "符合证据门的命中：2 条" in rendered
    assert "[1] 事实 f001" in rendered
    assert "[2] 事实 f002" in rendered
    assert "事实句：林乔把铜钥匙交给苏晚。" in rendered
    assert "事实句：苏晚把钥匙收进黑色文件袋。" in rendered
    assert "章节版本：c01 / revision 2" in rendered
    assert f"章节文本 SHA-256：{_sha(CURRENT_TEXT)}" in rendered
    assert "证据来源：fixture-c4-snapshot" in rendered
    assert "原文证据：把钥匙收进黑色文件袋" in rendered
    assert f"证据片段 SHA-256：{_sha('把钥匙收进黑色文件袋')}" in rendered
    assert result == before


def test_render_empty_result_states_evidence_gate_not_story_conclusion() -> None:
    result = ask_tool.execute(_request(_fact("f001"), query="雨伞"))

    rendered = ask_tool.render_result(result)

    assert "符合证据门的命中：0 条" in rendered
    assert "没有符合当前版本与证据门的命中。" in rendered
    assert "关键词未命中（keyword_miss）：1" in rendered
    assert "故事中没有" not in rendered


@pytest.mark.parametrize(
    "damage",
    [
        "missing_evidence",
        "extra_evidence",
        "duplicate_match",
        "duplicate_evidence",
        "revision_mismatch",
        "anchor_span",
        "anchor_sha",
        "counts_shape",
        "counts_value",
    ],
)
def test_result_validation_rejects_broken_fact_evidence_closure(
    damage: str,
) -> None:
    result = ask_tool.execute(_request(_fact("f001")))
    damaged = copy.deepcopy(result)
    if damage == "missing_evidence":
        damaged["evidence"].clear()
    elif damage == "extra_evidence":
        extra = copy.deepcopy(damaged["evidence"][0])
        extra["fact_id"] = "f999"
        damaged["evidence"].append(extra)
    elif damage == "duplicate_match":
        damaged["matches"].append(copy.deepcopy(damaged["matches"][0]))
    elif damage == "duplicate_evidence":
        damaged["evidence"].append(copy.deepcopy(damaged["evidence"][0]))
    elif damage == "revision_mismatch":
        damaged["evidence"][0]["chapter_revision_ref"]["revision_no"] = 3
        damaged["evidence"][0]["anchor_ref"]["revision_no"] = 3
    elif damage == "anchor_span":
        damaged["evidence"][0]["anchor_ref"]["end"] += 1
    elif damage == "anchor_sha":
        damaged["evidence"][0]["anchor_ref"]["slice_sha256"] = "0" * 64
    elif damage == "counts_shape":
        damaged["excluded_counts"].pop("keyword_miss")
    else:
        damaged["excluded_counts"]["keyword_miss"] = True

    with pytest.raises(ask_tool.AskToolError):
        ask_tool.validate_result(damaged)
    with pytest.raises(ask_tool.AskToolError):
        ask_tool.render_result(damaged)


def test_render_cli_file_and_stdin_stdout_are_byte_stable_across_processes(
    tmp_path: Path,
) -> None:
    result = ask_tool.execute(_request(_fact("f001")))
    result_path = tmp_path / "result.json"
    rendered_path = tmp_path / "result.txt"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False),
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    file_run = subprocess.run(
        [
            sys.executable,
            str(ASK_TOOL_SCRIPT),
            "--render",
            "--input",
            str(result_path),
            "--output",
            str(rendered_path),
        ],
        check=False,
        capture_output=True,
        env=environment,
    )
    stdout_run = subprocess.run(
        [sys.executable, str(ASK_TOOL_SCRIPT), "--render"],
        input=json.dumps(result, ensure_ascii=False).encode("utf-8"),
        check=False,
        capture_output=True,
        env=environment,
    )

    expected = ask_tool.render_result(result).encode("utf-8")
    assert file_run.returncode == 0, file_run.stderr.decode("utf-8")
    assert stdout_run.returncode == 0, stdout_run.stderr.decode("utf-8")
    assert rendered_path.read_bytes() == expected
    assert stdout_run.stdout == expected


def test_render_atomic_write_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "result.txt"
    output_path.write_text("旧结果不得覆盖\n", encoding="utf-8")
    before = output_path.read_bytes()
    rendered = ask_tool.render_result(
        ask_tool.execute(_request(_fact("f001")))
    )

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic render replace failure")

    monkeypatch.setattr(ask_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic render replace failure"):
        ask_tool._atomic_write_text(output_path, rendered)

    assert output_path.read_bytes() == before
    assert list(tmp_path.glob(".result.txt.*.tmp")) == []

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
TOOL_SCRIPT = PRODUCT_ROOT / "mvp" / "ask_reader_scope_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import ask_reader_scope_tool, ask_tool
finally:
    sys.path.pop(0)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _revision_ref(chapter_id: str, *, revision_no: int = 1) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": _sha(f"{chapter_id}-revision-{revision_no}"),
    }


def _fact(
    fact_id: str,
    chapter_id: str,
    text: str,
    quote: str,
    *,
    revision_ref: dict | None = None,
) -> dict:
    selected_ref = copy.deepcopy(revision_ref or _revision_ref(chapter_id))
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter_id,
        "text": text,
        "quote": quote,
        "status": "confirmed",
        "source": "synthetic-reader-scope-fixture",
        "note": "",
        "added_at": "2026-08-19 10:00:00",
        "seg": 1,
        "decided_at": "2026-08-19 10:01:00",
        "chapter_revision_ref": selected_ref,
        "anchor_ref": {
            **selected_ref,
            "coordinate_basis": ask_tool.COORDINATE_BASIS,
            "start": 0,
            "end": len(quote),
            "slice_sha256": _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


C05_REF = _revision_ref("c05")
C20_REF = _revision_ref("c20")
MISDIRECTION = _fact(
    "f005",
    "c05",
    "众人都误以为管家是凶手。",
    "众人都误以为管家是凶手",
    revision_ref=C05_REF,
)
REVEAL = _fact(
    "f020",
    "c20",
    "真正的凶手是苏晚。",
    "真正的凶手是苏晚",
    revision_ref=C20_REF,
)


def _request(
    *,
    facts: list[dict] | None = None,
    refs: list[dict] | None = None,
    as_of: str = "c05",
) -> dict:
    return {
        "query": "凶手",
        "facts": copy.deepcopy(facts if facts is not None else [MISDIRECTION, REVEAL]),
        "current_revision_refs": copy.deepcopy(
            refs if refs is not None else [C05_REF, C20_REF]
        ),
        "as_of_chapter_id": as_of,
    }


def _all_string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for row in value for item in _all_string_values(row)]
    if isinstance(value, dict):
        return [item for row in value.values() for item in _all_string_values(row)]
    return []


def test_as_of_early_chapter_blocks_later_reveal_without_identity_leak() -> None:
    result = ask_reader_scope_tool.execute(_request())

    assert [row["fact_id"] for row in result["matches"]] == ["f005"]
    assert [row["fact_id"] for row in result["evidence"]] == ["f005"]
    assert result["reader_scope"] == {
        "mode": "AS_OF_CHAPTER",
        "as_of_chapter_id": "c05",
        "visible_chapter_count": 1,
        "future_chapter_count": 1,
        "blocked_fact_count": 1,
    }
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
    assert "f020" not in serialized
    assert "真正的凶手" not in serialized
    assert "苏晚" not in serialized
    assert "c20" not in _all_string_values(result)


def test_as_of_later_chapter_can_see_both_matching_facts() -> None:
    result = ask_reader_scope_tool.execute(_request(as_of="c20"))

    assert [row["fact_id"] for row in result["matches"]] == ["f005", "f020"]
    assert [row["fact_id"] for row in result["evidence"]] == ["f005", "f020"]
    assert result["reader_scope"]["future_chapter_count"] == 0
    assert result["reader_scope"]["blocked_fact_count"] == 0


def test_non_contiguous_chapter_ids_follow_supplied_array_order() -> None:
    result = ask_reader_scope_tool.execute(
        _request(refs=[C20_REF, C05_REF], as_of="c20")
    )

    assert [row["fact_id"] for row in result["matches"]] == ["f020"]
    assert result["reader_scope"]["future_chapter_count"] == 1
    assert result["reader_scope"]["blocked_fact_count"] == 1


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda request: request.update(as_of_chapter_id="c99"),
            "as_of_chapter_id 不在",
        ),
        (
            lambda request: request["current_revision_refs"].append(
                copy.deepcopy(C05_REF)
            ),
            "重复章节",
        ),
        (
            lambda request: request["facts"].append(
                _fact("f099", "c99", "远处传来钟声。", "远处传来钟声")
            ),
            "不属于当前章节索引",
        ),
        (
            lambda request: request["current_revision_refs"][0].pop(
                "revision_text_sha256"
            ),
            "不是合法 revision ref",
        ),
        (
            lambda request: request.update(extra="forbidden"),
            "request 只允许",
        ),
    ],
)
def test_bad_cutoff_index_fact_membership_and_shapes_fail_closed(
    mutate,
    message: str,
) -> None:
    request = _request()
    mutate(request)

    with pytest.raises(ask_reader_scope_tool.ReaderScopeError, match=message):
        ask_reader_scope_tool.execute(request)


def test_file_adapter_matches_object_core_and_is_byte_stable(tmp_path: Path) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "result.json"
    request = _request()
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
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
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    first_bytes = output_path.read_bytes()
    assert json.loads(first_bytes) == ask_reader_scope_tool.execute(request)

    repeated = subprocess.run(
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
        text=True,
        env=environment,
    )
    assert repeated.returncode == 0, repeated.stderr
    assert output_path.read_bytes() == first_bytes


def test_bad_input_and_replace_failure_do_not_overwrite_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "result.json"
    output_path.write_text('{"sentinel":"old"}\n', encoding="utf-8")
    before = output_path.read_bytes()

    broken_path = tmp_path / "broken.json"
    broken_path.write_text(
        json.dumps(_request(as_of="c99"), ensure_ascii=False),
        encoding="utf-8",
    )
    assert (
        ask_reader_scope_tool.main(
            ["--input", str(broken_path), "--output", str(output_path)]
        )
        == 2
    )
    assert output_path.read_bytes() == before

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(ask_reader_scope_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic replace failure"):
        ask_reader_scope_tool._atomic_write_json(
            output_path,
            ask_reader_scope_tool.execute(_request()),
        )

    assert output_path.read_bytes() == before
    assert list(tmp_path.glob(".result.json.*.tmp")) == []


def test_core_rejects_path_and_does_not_change_author_omniscient_query() -> None:
    with pytest.raises(
        ask_reader_scope_tool.ReaderScopeError,
        match="request 必须是对象",
    ):
        ask_reader_scope_tool.execute(Path("facts.json"))  # type: ignore[arg-type]

    omniscient = ask_tool.execute(
        {
            "query": "凶手",
            "facts": copy.deepcopy([MISDIRECTION, REVEAL]),
            "current_revision_refs": copy.deepcopy([C05_REF, C20_REF]),
        }
    )
    assert [row["fact_id"] for row in omniscient["matches"]] == ["f005", "f020"]

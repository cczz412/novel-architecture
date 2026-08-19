from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
SCHEMA_PATH = PRODUCT_ROOT / "contracts" / "C11_CHAPTER_REVISION_LEDGER.schema.json"
FACT_TOOL_SCRIPT = PRODUCT_ROOT / "mvp" / "fact_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import fact_tool, factstore
finally:
    sys.path.pop(0)


NOW = "2026-08-19 14:00:00"
TEXT = "甲拿起钥匙。乙离开。"
QUOTE = "甲拿起钥匙。"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_ref(
    *,
    chapter_id: str = "c01",
    revision_no: int = 1,
    text: str = TEXT,
) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": _sha256(text),
    }


def _chapter(
    *,
    chapter_id: str = "c01",
    text: str = TEXT,
    revision_no: int = 1,
) -> dict:
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": f"第{chapter_id[1:]}章",
        "kind": "draft",
        "text": text,
        "added_at": "2026-08-18 04:00:00",
        "chapter_revision_ref": _revision_ref(
            chapter_id=chapter_id,
            revision_no=revision_no,
            text=text,
        ),
    }


def _segment(
    *,
    chapter_id: str = "c01",
    text: str = TEXT,
    revision_no: int = 1,
) -> dict:
    return {
        "contract": "C2_SEGMENT",
        "version": "v1",
        "chapter_revision_ref": _revision_ref(
            chapter_id=chapter_id,
            revision_no=revision_no,
            text=text,
        ),
        "seg": 1,
        "text": text,
        "start": 0,
        "end": len(text),
        "halo_before": "",
        "halo_after": "",
    }


def _candidate(
    *,
    chapter_id: str = "c01",
    chapter_text: str = TEXT,
    revision_no: int = 1,
    text: str = "甲拿起钥匙。",
    quote: str = QUOTE,
) -> dict:
    return {
        "contract": "C3_FACT_CANDIDATE",
        "version": "v1",
        "chapter_revision_ref": _revision_ref(
            chapter_id=chapter_id,
            revision_no=revision_no,
            text=chapter_text,
        ),
        "text": text,
        "quote": quote,
        "seg": 1,
    }


def _request() -> dict:
    # 复用 C11 正式 validator 的 C1→C2→C3 合法对象形状与同一组合成内容。
    return {
        "chapter": _chapter(),
        "segments": [_segment()],
        "candidates": [_candidate()],
        "source": "A_T03_C1_C2_C3_FORMAL_FIXTURE",
        "added_at": NOW,
    }


def _batch_item(
    chapter_id: str,
    chapter_text: str,
    quote: str,
    fact_text: str,
    *,
    revision_no: int = 1,
) -> dict:
    return {
        "chapter": _chapter(
            chapter_id=chapter_id,
            text=chapter_text,
            revision_no=revision_no,
        ),
        "segments": [
            _segment(
                chapter_id=chapter_id,
                text=chapter_text,
                revision_no=revision_no,
            )
        ],
        "candidates": [
            _candidate(
                chapter_id=chapter_id,
                chapter_text=chapter_text,
                revision_no=revision_no,
                text=fact_text,
                quote=quote,
            )
        ],
    }


def _batch_request() -> dict:
    return {
        "items": [
            _batch_item("c01", TEXT, QUOTE, "甲拿起钥匙。"),
            _batch_item(
                "c02",
                "丙关上窗。丁点灯。",
                "丙关上窗。",
                "丙关上了窗。",
            ),
        ],
        "source": "A_T03_C1_C2_C3_FORMAL_FIXTURE",
        "added_at": NOW,
    }


def _existing_fact() -> dict:
    quote = "乙离开。"
    start = TEXT.index(quote)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": "f005",
        "chapter_id": "c01",
        "text": quote,
        "quote": quote,
        "status": "confirmed",
        "source": "existing-fixture",
        "note": "",
        "added_at": "2026-08-18 05:00:00",
        "seg": 1,
        "decided_at": "2026-08-18 05:01:00",
        "chapter_revision_ref": _revision_ref(),
        "anchor_ref": {
            **_revision_ref(),
            "coordinate_basis": factstore.ANCHOR_COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": _sha256(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _assert_formal_c4(value: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(value)) == []
    assert value["contract"] == "C4_FACT_QUERY" and value["version"] == "v1"


def test_execute_builds_c4_v1_extracted_with_verified_revision_anchor() -> None:
    request = _request()
    before = copy.deepcopy(request)

    result = fact_tool.execute(request)

    assert request == before
    assert result["added_fact_refs"] == ["f001"]
    assert result["added_count"] == 1
    assert len(result["facts"]) == 1
    fact = result["facts"][0]
    _assert_formal_c4(fact)
    assert fact == {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": "f001",
        "chapter_id": "c01",
        "text": "甲拿起钥匙。",
        "quote": QUOTE,
        "status": "extracted",
        "source": "A_T03_C1_C2_C3_FORMAL_FIXTURE",
        "note": "",
        "added_at": NOW,
        "seg": 1,
        "chapter_revision_ref": _revision_ref(),
        "anchor_ref": {
            **_revision_ref(),
            "coordinate_basis": factstore.ANCHOR_COORDINATE_BASIS,
            "start": 0,
            "end": len(QUOTE),
            "slice_sha256": _sha256(QUOTE),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def test_existing_c4_snapshot_is_preserved_and_only_new_record_is_extracted() -> None:
    request = _request()
    request["existing_c4"] = [_existing_fact()]

    result = fact_tool.execute(request)

    assert result["facts"][0] == _existing_fact()
    assert result["facts"][1]["id"] == "f006"
    assert result["facts"][1]["status"] == "extracted"
    assert "decided_at" not in result["facts"][1]


def test_multichapter_batch_keeps_order_ids_revision_and_anchor() -> None:
    result = fact_tool.execute_batch(_batch_request())

    assert result["added_fact_refs"] == ["f001", "f002"]
    assert result["added_count"] == 2
    assert [fact["id"] for fact in result["facts"]] == ["f001", "f002"]
    for fact, item in zip(
        result["facts"],
        _batch_request()["items"],
        strict=True,
    ):
        revision_ref = item["chapter"]["chapter_revision_ref"]
        quote = item["candidates"][0]["quote"]
        assert fact["chapter_revision_ref"] == revision_ref
        assert all(
            fact["anchor_ref"][key] == revision_ref[key]
            for key in revision_ref
        )
        assert fact["quote"] == quote
        assert fact["anchor_ref"]["slice_sha256"] == _sha256(quote)
        _assert_formal_c4(fact)


def test_multichapter_batch_is_byte_equivalent_to_sequential_single_execute() -> None:
    request = _batch_request()
    first_item, second_item = request["items"]
    first = fact_tool.execute(
        {
            **first_item,
            "source": request["source"],
            "added_at": request["added_at"],
        }
    )
    second = fact_tool.execute(
        {
            **second_item,
            "source": request["source"],
            "added_at": request["added_at"],
            "existing_c4": first["facts"],
        }
    )
    sequential = {
        "facts": second["facts"],
        "added_fact_refs": [
            *first["added_fact_refs"],
            *second["added_fact_refs"],
        ],
        "added_count": first["added_count"] + second["added_count"],
    }

    assert fact_tool._json_bytes(fact_tool.execute_batch(request)) == fact_tool._json_bytes(
        sequential
    )


def test_multichapter_existing_confirmed_is_preserved_and_new_facts_append() -> None:
    request = _batch_request()
    request["existing_c4"] = [_existing_fact()]

    result = fact_tool.execute_batch(request)

    assert result["facts"][0] == _existing_fact()
    assert result["facts"][0]["status"] == "confirmed"
    assert [fact["id"] for fact in result["facts"][1:]] == ["f006", "f007"]
    assert all(fact["status"] == "extracted" for fact in result["facts"][1:])


@pytest.mark.parametrize(
    ("items", "reason"),
    [
        (
            lambda: [
                _batch_item("c01", TEXT, QUOTE, "甲拿起钥匙。"),
                _batch_item("c01", TEXT, QUOTE, "甲拿起钥匙。"),
            ],
            "FACT_TOOL_BATCH_REVISION_REF_DUPLICATE",
        ),
        (
            lambda: [
                _batch_item("c01", TEXT, QUOTE, "甲拿起钥匙。"),
                _batch_item(
                    "c01",
                    "第二版里甲放下钥匙。",
                    "甲放下钥匙。",
                    "甲放下了钥匙。",
                    revision_no=2,
                ),
            ],
            "FACT_TOOL_BATCH_CHAPTER_ID_DUPLICATE",
        ),
    ],
)
def test_multichapter_duplicate_chapter_or_revision_ref_is_rejected(
    items,
    reason: str,
) -> None:
    request = _batch_request()
    request["items"] = items()

    with pytest.raises(factstore.FactstoreError, match=reason):
        fact_tool.execute_batch(request)


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda request: request.update(items="not-a-list"),
            "FACT_TOOL_BATCH_ITEMS_REQUIRED",
        ),
        (
            lambda request: request["items"][0].update(source="forbidden"),
            "FACT_TOOL_BATCH_ITEM_SHAPE_INVALID:0",
        ),
    ],
)
def test_multichapter_batch_shape_is_fail_closed(mutate, reason: str) -> None:
    request = _batch_request()
    mutate(request)

    with pytest.raises(factstore.FactstoreError, match=reason):
        fact_tool.execute_batch(request)


def test_c2_normalized_coordinates_are_mapped_back_to_exact_revision_text() -> None:
    raw_text = " 甲拿起钥匙。  \n\n  乙离开。 "
    normalized = "甲拿起钥匙。\n乙离开。"
    quote = "乙离开。"
    request = _request()
    request["chapter"]["text"] = raw_text
    request["chapter"]["chapter_revision_ref"] = _revision_ref(text=raw_text)
    request["segments"] = [
        {
            **_segment(),
            "chapter_revision_ref": _revision_ref(text=raw_text),
            "text": normalized,
            "start": 0,
            "end": len(normalized),
        }
    ]
    request["candidates"] = [
        {
            **_candidate(text="乙已经离开。", quote=quote),
            "chapter_revision_ref": _revision_ref(text=raw_text),
        }
    ]

    fact = fact_tool.execute(request)["facts"][0]

    raw_start = raw_text.index(quote)
    assert fact["anchor_ref"]["start"] == raw_start
    assert fact["anchor_ref"]["end"] == raw_start + len(quote)
    assert raw_text[fact["anchor_ref"]["start"] : fact["anchor_ref"]["end"]] == quote


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda request: request["candidates"][0].update(quote="原文不存在"),
            "C3_QUOTE_NOT_IN_C2_SEGMENT",
        ),
        (
            lambda request: request["candidates"][0].update(seg=2),
            "C3_SEGMENT_NOT_FOUND",
        ),
        (
            lambda request: request["candidates"][0].update(
                chapter_revision_ref=_revision_ref(revision_no=2)
            ),
            "C3_REVISION_REF_MISMATCH",
        ),
    ],
)
def test_one_bad_candidate_rejects_the_whole_batch_without_partial_output(
    mutate,
    reason: str,
) -> None:
    request = _request()
    request["candidates"].append(_candidate(text="乙已经离开。", quote="乙离开。"))
    mutate(request)

    with pytest.raises(factstore.FactstoreError, match=reason):
        fact_tool.execute(request)


def test_cli_local_file_output_is_atomic_and_can_be_read_back(tmp_path: Path) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "snapshot.json"
    input_path.write_text(json.dumps(_request(), ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            str(FACT_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["added_fact_refs"] == ["f001"]
    _assert_formal_c4(result["facts"][0])
    assert not list(tmp_path.glob(".*.tmp"))


def test_cli_rejects_exact_same_input_and_output_before_any_write(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "request.json"
    source_path.write_text(json.dumps(_request(), ensure_ascii=False), encoding="utf-8")
    original = source_path.read_bytes()

    completed = subprocess.run(
        [
            sys.executable,
            str(FACT_TOOL_SCRIPT),
            "--input",
            str(source_path),
            "--output",
            str(source_path),
        ],
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "FACT_TOOL_INPUT_OUTPUT_SAME_FILE" in completed.stderr
    assert source_path.read_bytes() == original
    assert not list(tmp_path.glob(".*.tmp"))


def test_cli_rejects_relative_and_absolute_names_for_the_same_file(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "request.json"
    source_path.write_text(json.dumps(_request(), ensure_ascii=False), encoding="utf-8")
    original = source_path.read_bytes()

    completed = subprocess.run(
        [
            sys.executable,
            str(FACT_TOOL_SCRIPT),
            "--input",
            "request.json",
            "--output",
            str(source_path.resolve()),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )

    assert completed.returncode == 2
    assert "FACT_TOOL_INPUT_OUTPUT_SAME_FILE" in completed.stderr
    assert source_path.read_bytes() == original
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("alias_kind", ["symlink", "hardlink"])
def test_cli_rejects_mechanically_identifiable_file_aliases(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    source_path = tmp_path / "request.json"
    alias_path = tmp_path / f"{alias_kind}.json"
    source_path.write_text(json.dumps(_request(), ensure_ascii=False), encoding="utf-8")
    original = source_path.read_bytes()
    if alias_kind == "symlink":
        alias_path.symlink_to(source_path)
    else:
        os.link(source_path, alias_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(FACT_TOOL_SCRIPT),
            "--input",
            str(source_path),
            "--output",
            str(alias_path),
        ],
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )

    assert completed.returncode == 2
    assert "FACT_TOOL_INPUT_OUTPUT_SAME_FILE" in completed.stderr
    assert source_path.read_bytes() == original
    assert alias_path.read_bytes() == original
    assert not list(tmp_path.glob(".*.tmp"))


def test_cli_failure_does_not_overwrite_existing_output(tmp_path: Path) -> None:
    request = _request()
    request["candidates"][0]["quote"] = "坏 quote"
    input_path = tmp_path / "bad.json"
    output_path = tmp_path / "keep.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    output_path.write_text("DO_NOT_OVERWRITE", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(FACT_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "C3_QUOTE_NOT_IN_C2_SEGMENT" in completed.stderr
    assert output_path.read_text(encoding="utf-8") == "DO_NOT_OVERWRITE"


def test_batch_second_chapter_failure_does_not_return_or_overwrite_partial_output(
    tmp_path: Path,
) -> None:
    request = _batch_request()
    request["items"][1]["candidates"][0]["quote"] = "不存在的引文"
    with pytest.raises(
        factstore.FactstoreError,
        match="C3_QUOTE_NOT_IN_C2_SEGMENT",
    ):
        fact_tool.execute_batch(request)

    input_path = tmp_path / "bad-batch.json"
    output_path = tmp_path / "keep-batch.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    output_path.write_text("DO_NOT_OVERWRITE", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(FACT_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )

    assert completed.returncode == 2
    assert "C3_QUOTE_NOT_IN_C2_SEGMENT" in completed.stderr
    assert output_path.read_text(encoding="utf-8") == "DO_NOT_OVERWRITE"
    assert not list(tmp_path.glob(".*.tmp"))


def test_batch_cli_parses_and_is_byte_stable_across_restarts(tmp_path: Path) -> None:
    input_path = tmp_path / "batch.json"
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"
    input_path.write_text(
        json.dumps(_batch_request(), ensure_ascii=False),
        encoding="utf-8",
    )
    command = [sys.executable, str(FACT_TOOL_SCRIPT), "--input", str(input_path)]
    for output_path in (first_output, second_output):
        completed = subprocess.run(
            [*command, "--output", str(output_path)],
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )
        assert completed.returncode == 0, completed.stderr

    assert first_output.read_bytes() == second_output.read_bytes()
    parsed = json.loads(first_output.read_text(encoding="utf-8"))
    assert parsed["added_fact_refs"] == ["f001", "f002"]
    assert all(fact["status"] == "extracted" for fact in parsed["facts"])


def test_cli_stdin_stdout_and_project_dir_rejection() -> None:
    completed = subprocess.run(
        [sys.executable, str(FACT_TOOL_SCRIPT)],
        input=json.dumps(_request(), ensure_ascii=False),
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["facts"][0]["status"] == "extracted"

    request = _request()
    request["project_dir"] = "/tmp/forbidden"
    with pytest.raises(
        factstore.FactstoreError,
        match="FACT_TOOL_REQUEST_EXTRA:project_dir",
    ):
        fact_tool.execute(request)

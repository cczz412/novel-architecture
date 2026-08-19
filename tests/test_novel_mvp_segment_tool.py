from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_PATH = PRODUCT_ROOT / "mvp" / "segment_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import segment, segment_tool
finally:
    sys.path.pop(0)


def _chapter(
    *,
    text: str | None = None,
    chapter_id: str = "c01",
    revision_no: int = 1,
) -> dict:
    text = text or ("甲" * 700 + "。\n\n" + "乙" * 700 + "。")
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": f"第{chapter_id[1:]}章",
        "kind": "draft",
        "text": text,
        "added_at": "2026-08-19 08:00:00",
        "chapter_revision_ref": {
            "chapter_id": chapter_id,
            "revision_no": revision_no,
            "revision_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        },
    }


def _request() -> dict:
    return {
        "items": [_chapter()],
        "options": {
            "seg_min_chars": 620,
            "seg_max_chars": 923,
            "halo_chars": 180,
        },
    }


def _render_request(source_request: dict | None = None) -> dict:
    source = copy.deepcopy(source_request or _request())
    return {
        "source_request": source,
        "c2_result": segment_tool.execute(copy.deepcopy(source)),
    }


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
    )


def test_execute_emits_only_c2_v1_items_with_revision_ref_and_stable_receipt() -> None:
    request = _request()

    first = segment_tool.execute(request)
    second = segment_tool.execute(copy.deepcopy(request))

    assert first == second
    assert first["receipt"]["input_count"] == 1
    assert first["receipt"]["output_count"] == 2
    assert len(first["receipt"]["input_sha256"]) == 64
    assert len(first["receipt"]["output_sha256"]) == 64
    chapter_receipt = first["receipt"]["chapter_receipts"][0]
    assert chapter_receipt == {
        "chapter_revision_ref": request["items"][0]["chapter_revision_ref"],
        "segment_count": 2,
        "normalized_char_count": len("甲" * 700 + "。\n" + "乙" * 700 + "。"),
        "max_segment_chars": 701,
        "oversize_segment_count": 0,
        "coverage_sha256": hashlib.sha256(
            ("甲" * 700 + "。\n" + "乙" * 700 + "。").encode()
        ).hexdigest(),
    }
    for item in first["items"]:
        assert set(item) == {
            "contract",
            "version",
            "chapter_revision_ref",
            "seg",
            "text",
            "start",
            "end",
            "halo_before",
            "halo_after",
        }
        assert item["contract"] == "C2_SEGMENT"
        assert item["version"] == "v1"
        assert item["chapter_revision_ref"] == request["items"][0][
            "chapter_revision_ref"
        ]


def test_real_json_file_cli_round_trip_is_readable_in_a_new_process(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "c1-request.json"
    output_path = tmp_path / "c2-result.json"
    input_path.write_text(json.dumps(_request(), ensure_ascii=False), encoding="utf-8")

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 0, completed.stderr.decode()
    persisted = json.loads(output_path.read_bytes())
    assert persisted == segment_tool.execute(_request())

    reread = _run_cli("--input", str(input_path))
    assert reread.returncode == 0, reread.stderr.decode()
    assert json.loads(reread.stdout) == persisted


def test_stdin_stdout_adapter_is_supported() -> None:
    payload = json.dumps(_request(), ensure_ascii=False).encode()

    completed = _run_cli(stdin=payload)

    assert completed.returncode == 0, completed.stderr.decode()
    assert json.loads(completed.stdout) == segment_tool.execute(_request())


def test_render_map_shows_exact_responsibility_spans_and_read_only_halo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _render_request()
    before = copy.deepcopy(request)
    monkeypatch.setattr(
        segment,
        "segment_chapter",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("render 不得重新切段")
        ),
    )

    validated = segment_tool.validate_render_request(request)
    rendered = segment_tool.render_segment_map(request)

    assert validated == before
    assert request == before
    assert rendered.startswith("# M2 责任段地图\n")
    assert "章节 c01" in rendered
    assert "责任段数：2" in rendered
    assert "责任范围：`[0, 701)`" in rendered
    assert "前置上下文（只读，不属于责任文本）" in rendered
    assert "后置上下文（只读，不属于责任文本）" in rendered
    assert "可回拼提示" in rendered
    ref_sha = request["source_request"]["items"][0]["chapter_revision_ref"][
        "revision_text_sha256"
    ]
    ref_json = json.dumps(
        request["source_request"]["items"][0]["chapter_revision_ref"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert ref_sha in rendered
    assert ref_json in rendered
    for item in request["c2_result"]["items"]:
        assert item["text"] in rendered
        if item["halo_before"]:
            assert item["halo_before"] in rendered
        if item["halo_after"]:
            assert item["halo_after"] in rendered


def test_render_accepts_legal_one_segment_short_chapter_and_rejects_empty_c2() -> None:
    source = _request()
    source["items"] = [_chapter(text="短章。", chapter_id="c01")]
    request = _render_request(source)

    rendered = segment_tool.render_segment_map(request)

    assert "责任段数：1" in rendered
    assert "责任范围：`[0, 3)`" in rendered
    assert "短章。" in rendered
    broken = copy.deepcopy(request)
    broken["c2_result"]["items"] = []
    with pytest.raises(
        segment_tool.SegmentToolError,
        match="RENDER_C2_CHAPTER_ORDER_INVALID",
    ):
        segment_tool.render_segment_map(broken)


@pytest.mark.parametrize(
    ("corruption", "reason"),
    [
        ("bad_ref", "RENDER_C2_SOURCE_REF_NOT_FOUND"),
        ("bad_span", "COORDINATES_INVALID"),
        ("gap", "COORDINATES_INVALID"),
        ("overlap", "COORDINATE_TEXT_MISMATCH"),
        ("bad_halo", "HALO_AFTER_MISMATCH"),
        ("duplicate", "SEGMENT_SEQUENCE_MISMATCH"),
        ("bad_source_sha", "RENDER_C1_ITEM_INVALID"),
        ("bad_receipt_sha", "RENDER_C2_RECEIPT_MISMATCH"),
        ("extra_field", "RENDER_C2_ITEM_SHAPE_INVALID"),
    ],
)
def test_render_rejects_source_ref_span_halo_duplicate_and_receipt_drift(
    corruption: str,
    reason: str,
) -> None:
    request = _render_request()
    items = request["c2_result"]["items"]
    if corruption == "bad_ref":
        items[0]["chapter_revision_ref"]["revision_no"] = 99
    elif corruption == "bad_span":
        items[0]["end"] += 1
    elif corruption == "gap":
        items[1]["start"] += 1
        items[1]["end"] += 1
    elif corruption == "overlap":
        items[1]["start"] -= 1
        items[1]["end"] -= 1
    elif corruption == "bad_halo":
        items[0]["halo_after"] += "漂移"
    elif corruption == "duplicate":
        items.insert(1, copy.deepcopy(items[0]))
    elif corruption == "bad_source_sha":
        request["source_request"]["items"][0]["chapter_revision_ref"][
            "revision_text_sha256"
        ] = "0" * 64
    elif corruption == "bad_receipt_sha":
        request["c2_result"]["receipt"]["output_sha256"] = "0" * 64
    else:
        items[0]["summary"] = "不得自造字段"

    with pytest.raises(segment_tool.SegmentToolError, match=reason):
        segment_tool.render_segment_map(request)


def test_render_rejects_cross_chapter_reordering() -> None:
    source = _request()
    source["items"].append(_chapter(chapter_id="c02"))
    request = _render_request(source)
    request["c2_result"]["items"].reverse()

    with pytest.raises(
        segment_tool.SegmentToolError,
        match="RENDER_C2_CHAPTER_ORDER_INVALID",
    ):
        segment_tool.render_segment_map(request)


def test_render_cli_file_and_stdin_are_byte_stable_across_processes(
    tmp_path: Path,
) -> None:
    request = _render_request()
    input_path = tmp_path / "render-request.json"
    output_one = tmp_path / "segment-map-1.md"
    output_two = tmp_path / "segment-map-2.md"
    payload = json.dumps(request, ensure_ascii=False).encode()
    input_path.write_bytes(payload)

    for output_path in (output_one, output_two):
        completed = _run_cli(
            "--render",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        )
        assert completed.returncode == 0, completed.stderr.decode()
    stdin_run = _run_cli("--render", stdin=payload)

    assert stdin_run.returncode == 0, stdin_run.stderr.decode()
    assert output_one.read_bytes() == output_two.read_bytes() == stdin_run.stdout
    assert output_one.read_text(encoding="utf-8") == (
        segment_tool.render_segment_map(request)
    )


def test_render_cli_failure_preserves_old_output_and_input_collision_is_closed(
    tmp_path: Path,
) -> None:
    request = _render_request()
    request["c2_result"]["items"][0]["halo_after"] += "漂移"
    input_path = tmp_path / "bad-render-request.json"
    output_path = tmp_path / "existing-map.md"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    output_path.write_bytes(b"old-map\n")

    completed = _run_cli(
        "--render",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    )

    assert completed.returncode == 2
    assert b"HALO_AFTER_MISMATCH" in completed.stderr
    assert output_path.read_bytes() == b"old-map\n"
    assert not list(tmp_path.glob(f".{output_path.name}.*.tmp"))
    before_input = input_path.read_bytes()
    collision = _run_cli(
        "--render",
        "--input",
        str(input_path),
        "--output",
        str(input_path),
    )
    assert collision.returncode == 2
    assert b"INPUT_OUTPUT_PATH_MUST_DIFFER" in collision.stderr
    assert input_path.read_bytes() == before_input


@pytest.mark.parametrize("alias_kind", ["symlink", "hardlink"])
def test_render_output_file_alias_cannot_replace_input(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    input_path = tmp_path / "render-request.json"
    output_alias = tmp_path / f"render-{alias_kind}-alias.json"
    input_path.write_text(
        json.dumps(_render_request(), ensure_ascii=False),
        encoding="utf-8",
    )
    if alias_kind == "symlink":
        output_alias.symlink_to(input_path)
    else:
        output_alias.hardlink_to(input_path)
    before = input_path.read_bytes()

    completed = _run_cli(
        "--render",
        "--input",
        str(input_path),
        "--output",
        str(output_alias),
    )

    assert completed.returncode == 2
    assert b"INPUT_OUTPUT_PATH_MUST_DIFFER" in completed.stderr
    assert input_path.read_bytes() == before
    assert output_alias.read_bytes() == before
    assert not list(tmp_path.glob(".*.tmp"))


def test_bad_revision_rejects_whole_batch_without_overwriting_existing_output(
    tmp_path: Path,
) -> None:
    request = _request()
    request["items"].append(_chapter(text="另一章正文"))
    request["items"][1]["id"] = "c02"
    request["items"][1]["chapter_revision_ref"]["chapter_id"] = "c02"
    request["items"][1]["chapter_revision_ref"]["revision_text_sha256"] = "0" * 64
    input_path = tmp_path / "bad-request.json"
    output_path = tmp_path / "existing-result.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    original = b'{"keep":"old-output"}\n'
    output_path.write_bytes(original)

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 2
    assert b"C1_V1_REVISION_SHA_MISMATCH" in completed.stderr
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []


def test_bad_path_adapter_parameters_do_not_touch_input(tmp_path: Path) -> None:
    path = tmp_path / "same.json"
    original = json.dumps(_request(), ensure_ascii=False).encode()
    path.write_bytes(original)

    completed = _run_cli("--input", str(path), "--output", str(path))

    assert completed.returncode == 2
    assert b"INPUT_OUTPUT_PATH_MUST_DIFFER" in completed.stderr
    assert path.read_bytes() == original


def test_options_reject_unknown_or_missing_cutting_parameters() -> None:
    request = _request()
    request["options"]["future_semantic"] = True

    with pytest.raises(segment_tool.SegmentToolError, match="OPTIONS_FIELDS_INVALID"):
        segment_tool.execute(request)

    del request["options"]["future_semantic"]
    del request["options"]["halo_chars"]
    with pytest.raises(segment_tool.SegmentToolError, match="OPTIONS_FIELDS_INVALID"):
        segment_tool.execute(request)


def test_empty_batch_rejects_before_segmentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    request["items"] = []
    monkeypatch.setattr(
        segment,
        "segment_chapter",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("空批次不得进入切段算法")
        ),
    )

    with pytest.raises(
        segment_tool.SegmentToolError,
        match="ITEMS_MUST_BE_NONEMPTY_ARRAY",
    ):
        segment_tool.execute(request)


def test_exact_duplicate_revision_rejects_before_segmentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    request["items"].append(copy.deepcopy(request["items"][0]))
    monkeypatch.setattr(
        segment,
        "segment_chapter",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("重复 revision 不得进入切段算法")
        ),
    )

    with pytest.raises(
        segment_tool.SegmentToolError,
        match="DUPLICATE_CHAPTER_REVISION_REF",
    ):
        segment_tool.execute(request)


def test_same_chapter_with_two_revisions_rejects_without_selecting_current() -> None:
    request = _request()
    request["items"].append(
        _chapter(text="同一章第二版正文。", chapter_id="c01", revision_no=2)
    )

    with pytest.raises(
        segment_tool.SegmentToolError,
        match="DUPLICATE_CHAPTER_ID:c01",
    ):
        segment_tool.execute(request)


def test_two_distinct_chapters_keep_input_order_coordinates_and_determinism() -> None:
    request = _request()
    request["items"].append(_chapter(chapter_id="c02"))

    first = segment_tool.execute(request)
    second = segment_tool.execute(copy.deepcopy(request))

    assert first == second
    assert [item["chapter_revision_ref"]["chapter_id"] for item in first["items"]] == [
        "c01",
        "c01",
        "c02",
        "c02",
    ]
    assert [item["seg"] for item in first["items"]] == [1, 2, 1, 2]
    assert [
        row["chapter_revision_ref"]["chapter_id"]
        for row in first["receipt"]["chapter_receipts"]
    ] == ["c01", "c02"]
    for chapter, receipt in zip(
        request["items"], first["receipt"]["chapter_receipts"], strict=True
    ):
        chapter_items = [
            item
            for item in first["items"]
            if item["chapter_revision_ref"]["chapter_id"] == chapter["id"]
        ]
        normalized = "\n".join(segment.split_paragraphs(chapter["text"]))
        assert "\n".join(item["text"] for item in chapter_items) == normalized
        assert receipt["normalized_char_count"] == len(normalized)
    assert [
        (item["start"], item["end"])
        for item in first["items"][:2]
    ] == [
        (item["start"], item["end"])
        for item in segment_tool.execute(_request())["items"]
    ]


def test_cli_duplicate_second_item_preserves_existing_output_and_leaves_no_tmp(
    tmp_path: Path,
) -> None:
    request = _request()
    request["items"].append(copy.deepcopy(request["items"][0]))
    input_path = tmp_path / "duplicate-request.json"
    output_path = tmp_path / "existing-result.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    original = b'{"keep":"old-output"}\n'
    output_path.write_bytes(original)

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 2
    assert b"DUPLICATE_CHAPTER_REVISION_REF" in completed.stderr
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []


@pytest.mark.parametrize(
    "corruption",
    ["missing_text", "duplicate", "reordered", "bad_coordinate"],
)
def test_coverage_corruption_rejects_the_whole_batch(
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
) -> None:
    request = _request()
    request["items"].append(_chapter(chapter_id="c02"))
    real_segment_chapter = segment.segment_chapter

    def corrupted(chapter: dict, lo: int, hi: int, halo: int) -> list[dict]:
        rows = real_segment_chapter(chapter, lo, hi, halo)
        if chapter["id"] != "c02":
            return rows
        rows = copy.deepcopy(rows)
        if corruption == "missing_text":
            rows[0]["text"] = rows[0]["text"][:-1]
            rows[0]["end"] -= 1
        elif corruption == "duplicate":
            rows.insert(1, copy.deepcopy(rows[0]))
        elif corruption == "reordered":
            rows.reverse()
        else:
            rows[0]["start"] += 1
            rows[0]["end"] += 1
        return rows

    monkeypatch.setattr(segment, "segment_chapter", corrupted)
    with pytest.raises(
        segment_tool.SegmentToolError,
        match="CHAPTER_COVERAGE_INVALID:c02",
    ):
        segment_tool.execute(request)


def test_blank_chapter_cannot_become_a_legal_zero_segment_batch() -> None:
    request = _request()
    request["items"] = [_chapter(text=" \n\n\t", chapter_id="c01")]

    with pytest.raises(
        segment_tool.SegmentToolError,
        match="CHAPTER_TEXT_EMPTY_AFTER_NORMALIZATION:c01",
    ):
        segment_tool.execute(request)


def test_eighty_chapter_receipts_are_complete_ordered_and_stable() -> None:
    request = _request()
    request["items"] = [
        _chapter(
            text=f"第{index:02d}章合成正文。" * 12,
            chapter_id=f"c{index:02d}",
        )
        for index in range(1, 81)
    ]

    first = segment_tool.execute(request)
    second = segment_tool.execute(copy.deepcopy(request))

    assert first == second
    receipts = first["receipt"]["chapter_receipts"]
    assert len(receipts) == 80
    assert [row["chapter_revision_ref"]["chapter_id"] for row in receipts] == [
        f"c{index:02d}" for index in range(1, 81)
    ]
    assert all(row["segment_count"] >= 1 for row in receipts)
    assert len(_canonical_result_bytes(first)) == len(_canonical_result_bytes(second))


def _canonical_result_bytes(value: dict) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

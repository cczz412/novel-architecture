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
TOOL_PATH = PRODUCT_ROOT / "mvp/review_page_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import review_page_tool, review_queue_workspace
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:review-page-alice"
TEXTS = {
    "c01-r2": "甲拿起铜钥匙。乙离开房间。丙关上门。",
    "c02-r1": "丁打开窗户。",
}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _revision_ref(chapter_id: str, revision_no: int) -> dict:
    text = TEXTS[f"{chapter_id}-r{revision_no}"]
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": _sha(text),
    }


def _fact(
    fact_id: str,
    chapter_id: str,
    revision_no: int,
    quote: str,
) -> dict:
    revision = _revision_ref(chapter_id, revision_no)
    start = TEXTS[f"{chapter_id}-r{revision_no}"].index(quote)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter_id,
        "text": f"候选事实：{quote}",
        "quote": quote,
        "status": "extracted",
        "source": "M5_REVIEW_PAGE_SYNTHETIC_FIXTURE",
        "note": "",
        "added_at": "2026-08-19 23:00:00",
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
        _fact("f001", "c01", 2, "甲拿起铜钥匙。"),
        _fact("f002", "c01", 2, "乙离开房间。"),
        _fact("f003", "c01", 2, "丙关上门。"),
        _fact("f004", "c01", 2, "甲拿起铜钥匙。"),
        _fact("f005", "c01", 2, "乙离开房间。"),
    ]


def _index() -> list[dict]:
    return [_revision_ref("c01", 2), _revision_ref("c02", 1)]


def _inventory(root: Path) -> list[tuple[str, bool, bytes | None]]:
    if not root.exists():
        return []
    return [
        (
            str(path.relative_to(root)),
            path.is_dir(),
            None if path.is_dir() else path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
    ]


def _real_pages(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime).create_project(ALICE, "审查单项目")
    workspace.commit(
        "op-seed-review-page",
        {"facts": _facts(), "chapter_index": _index()},
        {"facts": 0, "chapter_index": 0},
    )
    first = review_queue_workspace.read_chapter_review_page(
        workspace,
        "c01",
        3,
        None,
    )
    tail = review_queue_workspace.read_chapter_review_page(
        workspace,
        "c01",
        3,
        first["next_after_fact_ref"],
    )
    empty = review_queue_workspace.read_chapter_review_page(
        workspace,
        "c01",
        3,
        tail["next_after_fact_ref"],
    )
    return runtime, workspace, first, tail, empty


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_real_review_queue_page_renders_all_evidence_in_original_order_without_write(
    tmp_path: Path,
) -> None:
    runtime, _, first, _, _ = _real_pages(tmp_path)
    before = _inventory(runtime)

    validated = review_page_tool.validate_page(first)
    markdown = review_page_tool.render_page(first)

    assert validated == first
    assert "- 本页数量：3" in markdown
    assert "- 是否还有下一页：是" in markdown
    assert "- 下一续看锚：`f003`" in markdown
    assert "本页只供作者审查，尚未确认/驳回" in markdown
    positions = [
        markdown.index(f"## {index}. `f{index:03d}`")
        for index in range(1, 4)
    ]
    assert positions == sorted(positions)
    for fact in first["items"]:
        assert fact["text"] in markdown
        assert fact["quote"] in markdown
        assert fact["source"] in markdown
        assert fact["anchor_ref"]["slice_sha256"] in markdown
        assert str(fact["anchor_ref"]["start"]) in markdown
        assert str(fact["anchor_ref"]["end"]) in markdown
        assert fact["status"] in markdown
    assert _inventory(runtime) == before


def test_tail_and_empty_page_are_readable_and_keep_cursor_identity(
    tmp_path: Path,
) -> None:
    _, _, _, tail, empty = _real_pages(tmp_path)

    tail_markdown = review_page_tool.render_page(tail)
    empty_markdown = review_page_tool.render_page(empty)

    assert "- 本页数量：2" in tail_markdown
    assert "- 是否还有下一页：否" in tail_markdown
    assert "- 下一续看锚：`f005`" in tail_markdown
    assert "- 本页数量：0" in empty_markdown
    assert "本页没有待审条目" in empty_markdown
    assert "- 下一续看锚：`f005`" in empty_markdown


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        ("duplicate", "PAGE_ITEMS_INVALID:C4_FACT_ID_DUPLICATE"),
        ("cross_chapter", "PAGE_ITEM_CHAPTER_MISMATCH:f900"),
        ("bad_anchor_sha", "PAGE_ITEMS_INVALID:C4_ANCHOR_QUOTE_SHA_MISMATCH"),
        ("bad_cursor", "PAGE_NEXT_CURSOR_MISMATCH"),
        ("bad_snapshot_sha", "PAGE_FACTS_SNAPSHOT_INVALID"),
        ("has_more_empty", "PAGE_HAS_MORE_WITHOUT_ITEMS"),
    ],
)
def test_invalid_page_fails_closed(damage: str, reason: str, tmp_path: Path) -> None:
    _, _, first, _, _ = _real_pages(tmp_path)
    page = copy.deepcopy(first)
    if damage == "duplicate":
        page["items"].append(copy.deepcopy(page["items"][0]))
        page["next_after_fact_ref"] = page["items"][-1]["id"]
    elif damage == "cross_chapter":
        page["items"][0] = _fact("f900", "c02", 1, "丁打开窗户。")
    elif damage == "bad_anchor_sha":
        page["items"][0]["anchor_ref"]["slice_sha256"] = "0" * 64
    elif damage == "bad_cursor":
        page["next_after_fact_ref"] = "f999"
    elif damage == "bad_snapshot_sha":
        page["facts_snapshot"]["sha256"] = "short"
    else:
        page["items"] = []
        page["has_more"] = True
        page["next_after_fact_ref"] = None

    with pytest.raises(review_page_tool.ReviewPageToolError, match=reason):
        review_page_tool.render_page(page)


def test_cli_file_and_stdout_are_cross_process_byte_stable(tmp_path: Path) -> None:
    _, _, first, _, _ = _real_pages(tmp_path / "source")
    input_path = tmp_path / "review-page.json"
    first_path = tmp_path / "review-page-first.md"
    second_path = tmp_path / "review-page-second.md"
    input_path.write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")

    first_run = _run_cli("--input", str(input_path), "--output", str(first_path))
    second_run = _run_cli("--input", str(input_path), "--output", str(second_path))
    stdout_run = _run_cli("--input", str(input_path))

    assert first_run.returncode == second_run.returncode == stdout_run.returncode == 0
    expected = review_page_tool.render_page(first).encode("utf-8")
    assert first_path.read_bytes() == second_path.read_bytes() == stdout_run.stdout
    assert stdout_run.stdout == expected


def test_bad_cli_input_preserves_existing_output_and_leaves_no_tmp(
    tmp_path: Path,
) -> None:
    _, _, first, _, _ = _real_pages(tmp_path / "source")
    first["next_after_fact_ref"] = "f999"
    input_path = tmp_path / "bad-page.json"
    output_path = tmp_path / "existing.md"
    input_path.write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
    original = b"keep-existing-review-page\n"
    output_path.write_bytes(original)

    completed = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    )

    assert completed.returncode == 2
    assert b"PAGE_NEXT_CURSOR_MISMATCH" in completed.stderr
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []


def test_atomic_replace_failure_preserves_existing_output_and_cleans_tmp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "existing.md"
    original = b"existing\n"
    output_path.write_bytes(original)

    def fail_replace(*args, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(review_page_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        review_page_tool._write_markdown_atomic(output_path, "new\n")
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []

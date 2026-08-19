from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import segment, store
finally:
    sys.path.pop(0)


def _init(tmp_path: Path, monkeypatch, project: str) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path / "data")
    store.init_project(project)


def _revision_ref(chapter_id: str, text: str, revision_no: int = 1) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def test_c1_v1_writer_to_c2_v1_inherits_current_revision_ref(
    tmp_path: Path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "c1-c2-v1")
    text = "甲" * 700 + "。\n\n" + "乙" * 700 + "。"
    revision_ref = _revision_ref("c01", text)

    chapter = store.add_c1_v1_current_view(
        "c1-c2-v1",
        title="第一章",
        text=text,
        chapter_revision_ref=revision_ref,
    )
    segments = segment.segment_chapter(chapter, 620, 923, 180)

    assert store.chapters("c1-c2-v1") == [chapter]
    assert chapter["contract"] == "C1_CHAPTER_DOC" and chapter["version"] == "v1"
    assert chapter["chapter_revision_ref"] == revision_ref
    assert len(segments) == 2
    flat = "\n".join(segment.split_paragraphs(text))
    for index, item in enumerate(segments, 1):
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
        assert item["contract"] == "C2_SEGMENT" and item["version"] == "v1"
        assert item["chapter_revision_ref"] == revision_ref
        assert item["seg"] == index
        assert flat[item["start"] : item["end"]] == item["text"]


@pytest.mark.parametrize(
    ("revision_ref", "error"),
    [
        (
            {
                "chapter_id": "c99",
                "revision_no": 1,
                "revision_text_sha256": hashlib.sha256("正文".encode()).hexdigest(),
            },
            "C1_V1_REVISION_CHAPTER_MISMATCH",
        ),
        (
            {
                "chapter_id": "c01",
                "revision_no": 1,
                "revision_text_sha256": "0" * 64,
            },
            "C1_V1_REVISION_SHA_MISMATCH",
        ),
    ],
)
def test_c1_v1_writer_rejects_revision_ref_drift_before_write(
    tmp_path: Path, monkeypatch, revision_ref: dict, error: str
) -> None:
    project = f"reject-{error.lower()}"
    _init(tmp_path, monkeypatch, project)
    chapters_path = store.project_dir(project) / "chapters.json"
    before = chapters_path.read_bytes()

    with pytest.raises(ValueError, match=error):
        store.add_c1_v1_current_view(
            project,
            title="第一章",
            text="正文",
            chapter_revision_ref=revision_ref,
        )

    assert chapters_path.read_bytes() == before
    assert store.chapters(project) == []


def test_c2_v1_rejects_current_ref_text_drift() -> None:
    text = "甲离开。"
    chapter = {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": "c01",
        "title": "第一章",
        "kind": "draft",
        "text": text,
        "added_at": "2026-08-19 02:00:00",
        "chapter_revision_ref": _revision_ref("c01", "另一版正文"),
    }

    with pytest.raises(ValueError, match="C1_V1_REVISION_SHA_MISMATCH"):
        segment.segment_chapter(chapter, 620, 923, 180)


def test_legacy_v0_paths_stay_legacy_and_do_not_silently_upgrade(
    tmp_path: Path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "legacy-v0")
    chapter = store.add_chapter("legacy-v0", "旧章", "旧正文")

    assert "contract" not in chapter and "chapter_revision_ref" not in chapter
    segments = segment.segment_chapter(chapter["text"], 620, 923, 180)
    assert segments and all("contract" not in item for item in segments)
    with pytest.raises(ValueError, match="C1_V1_CURRENT_VIEW_INVALID"):
        segment.segment_chapter(chapter, 620, 923, 180)

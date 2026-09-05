from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from self_check import PREFERRED, run_self_check  # noqa: E402


def test_self_check_passes() -> None:
    result = run_self_check()
    assert result["result"] == "PASS"
    assert result["preferred"] == list(PREFERRED)
    assert result["window_count"] == 0
    assert result["read_novel_body"] is False


def test_catalog_does_not_embed_chapter_windows_or_body() -> None:
    payload = json.loads((ROOT / "CATALOG.json").read_text(encoding="utf-8"))
    assert payload["windows"] == []
    dumped = json.dumps(payload, ensure_ascii=False)
    assert "第1章" not in dumped
    assert "chapter_text" not in dumped


def test_package_has_no_novel_body_files() -> None:
    names = {path.name for path in ROOT.iterdir()}
    assert "chapters" not in names
    for path in ROOT.iterdir():
        assert path.suffix not in {".txt", ".epub", ".html"}

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from self_check import NEWBOOKS, PREFERRED, run_self_check  # noqa: E402


def test_self_check_passes() -> None:
    result = run_self_check()
    assert result["result"] == "PASS"
    assert result["preferred"] == list(PREFERRED)
    assert result["window_count"] == 20
    assert result["windows_github_issue"] == 289
    assert result["read_novel_body"] is False
    assert result["newbooks"] == list(NEWBOOKS)
    assert result["second_batch_github_issue"] == 284


def test_catalog_registers_numeric_windows_without_body() -> None:
    payload = json.loads((ROOT / "CATALOG.json").read_text(encoding="utf-8"))
    assert payload["status"] == "WINDOWS_CANDIDATE_REGISTERED"
    assert payload["body_read"] is False
    assert payload["windows"][0]["chapters"] == [1, 2, 9, 10]
    dumped = json.dumps(payload, ensure_ascii=False)
    assert "第1章" not in dumped
    assert "chapter_text" not in dumped
    assert payload["gold_review"]["current_stage"] == "unreviewed_candidate"


def test_second_batch_does_not_steal_first_cap_or_old_books() -> None:
    payload = json.loads((ROOT / "CATALOG.json").read_text(encoding="utf-8"))
    second = payload["second_batch_newbooks"]
    assert second["consumes_first_batch_cap"] is False
    titles = [item["title"] for item in second["books"]]
    assert titles == list(NEWBOOKS)
    assert second["in_trial_seven"] is True


def test_package_has_no_novel_body_files() -> None:
    names = {path.name for path in ROOT.iterdir()}
    assert "chapters" not in names
    for path in ROOT.iterdir():
        assert path.suffix not in {".txt", ".epub", ".html"}

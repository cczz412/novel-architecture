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
    gold = payload["gold_review"]
    assert gold["current_stage"] == "split_by_batch"
    assert gold["first_batch_stage"] == "unreviewed_candidate"
    assert gold["second_batch_stage"] == "chatgpt_cz_adopted_revisable"
    assert gold["revisable_with_sufficient_evidence"] is True


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


def test_second_batch_adopted_gold_is_revisable() -> None:
    payload = json.loads((ROOT / "CATALOG.json").read_text(encoding="utf-8"))
    second = payload["second_batch_newbooks"]
    assert second["status"] == "CHATGPT_CZ_ADOPTED_GOLD"
    assert second["adopt_github_issue"] == 293
    assert second["revisable_with_sufficient_evidence"] is True
    assert second["independent_human_extract_review_performed"] is False
    assert second["coverage_completed"] is False
    assert (ROOT / "second_batch_gold_r01" / "ROW_VERDICTS.csv").is_file()
    label = payload["gold_review"]["chatgpt_cz_adopted_label"]
    assert "对照金标" in label
    assert "可凭充分证据修订" in label
    assert "已独立人工复核并采纳" not in label

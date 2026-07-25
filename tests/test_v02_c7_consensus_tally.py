from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c7_consensus_tally as tally  # noqa: E402


pytestmark = pytest.mark.v02

VOTE = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C7_6_7_ai_consensus_workspace"
    / "votes/terra_independent_window_1.json"
)
NOTION_VOTE = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C7_6_7_ai_consensus_workspace"
    / "votes/notion_independent_window_2.json"
)


def test_local_terra_vote_is_valid_and_sha_bound() -> None:
    receipt = tally.validate_vote(VOTE)
    assert receipt["status"] == "PASS"
    assert receipt["voter_id"] == "terra_independent_window_1"
    assert receipt["model_family"] == "terra"
    assert receipt["vote_total"] == 26
    assert len(receipt["canonical_vote_sha256"]) == 64
    assert len(receipt["packet_manifest_sha256"]) == 64


def test_one_vote_stays_sealed_and_cannot_freeze() -> None:
    result = tally.tally_votes([VOTE])
    assert result["status"] == "WAITING_FOR_SECOND_INDEPENDENT_VOTE"
    assert result["independent_vote_total"] == 1
    assert result["unanimous_working_verdict_total"] == 0
    assert result["disagreement_total"] == 0
    assert result["mapping_freeze_allowed"] is False
    assert result["c5_rescore_allowed"] is False
    assert "votes" not in result["vote_receipts"][0]


def test_vote_rejects_forbidden_family_and_mixed_no_correspondence(
    tmp_path: Path,
) -> None:
    document = json.loads(VOTE.read_text(encoding="utf-8"))
    document["model_family"] = "deepseek-v4-flash"
    forbidden_path = tmp_path / "forbidden.json"
    forbidden_path.write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(tally.C7TallyError, match="禁用投票模型"):
        tally.validate_vote(forbidden_path)

    document["model_family"] = "independent-other"
    document["votes"][0]["selected_choice_ids"] = [
        "NO_CORRESPONDENCE",
        "MAP_TO::EV-C0039-01",
    ]
    mixed_path = tmp_path / "mixed.json"
    mixed_path.write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(tally.C7TallyError, match="选择非法"):
        tally.validate_vote(mixed_path)


def test_renamed_copy_without_independence_receipt_is_rejected(
    tmp_path: Path,
) -> None:
    second = json.loads(VOTE.read_text(encoding="utf-8"))
    second["voter_id"] = "independent_window_2"
    second["model_family"] = "notion_ai"
    second_path = tmp_path / "second.json"
    second_path.write_text(
        json.dumps(second, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(tally.C7TallyError, match="不得只靠自报模型族"):
        tally.tally_votes([VOTE, second_path])


def test_notion_vote_is_bound_to_seal_and_exposes_two_disagreements() -> None:
    second_receipt = tally.validate_vote(NOTION_VOTE)
    assert second_receipt["status"] == "PASS"
    assert second_receipt["identity_self_declared"] is True
    assert second_receipt["independence_receipt"]["status"] == "PASS"
    result = tally.tally_votes([VOTE, NOTION_VOTE])
    assert result["status"] == "DISAGREEMENTS_REQUIRE_CZ"
    assert result["independent_vote_total"] == 2
    assert result["unanimous_working_verdict_total"] == 24
    assert result["disagreement_total"] == 2
    assert [
        row["packet_id"] for row in result["disagreements"]
    ] == ["C7-010", "C7-023"]
    assert result["mapping_freeze_allowed"] is False
    assert result["c5_rescore_allowed"] is False


def test_notion_receipt_rejects_reversed_seal_order(
    tmp_path: Path,
) -> None:
    document = json.loads(NOTION_VOTE.read_text(encoding="utf-8"))
    document["independence_receipt"][
        "first_ballot_sealed_at"
    ] = "2026-07-25T15:00:00+08:00"
    reversed_path = tmp_path / "reversed.json"
    reversed_path.write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(tally.C7TallyError, match="不晚于第一票"):
        tally.validate_vote(reversed_path)


@pytest.mark.parametrize(
    ("field", "value", "error_pattern", "needs_tally"),
    [
        (
            "first_ballot_canonical_sha256",
            "0" * 64,
            "未绑定本次第一票封签",
            True,
        ),
        (
            "packet_manifest_sha256",
            "0" * 64,
            "不符合 14:50 账序裁定",
            False,
        ),
        (
            "source_vote_page_url",
            "https://app.notion.com/p/fake",
            "不符合 14:50 账序裁定",
            False,
        ),
    ],
)
def test_notion_receipt_rejects_tampered_bindings(
    tmp_path: Path,
    field: str,
    value: str,
    error_pattern: str,
    needs_tally: bool,
) -> None:
    document = json.loads(NOTION_VOTE.read_text(encoding="utf-8"))
    document["independence_receipt"][field] = value
    tampered_path = tmp_path / f"tampered_{field}.json"
    tampered_path.write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(tally.C7TallyError, match=error_pattern):
        if needs_tally:
            tally.tally_votes([VOTE, tampered_path])
        else:
            tally.validate_vote(tampered_path)

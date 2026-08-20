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
REVIEW_TOOL_SCRIPT = PRODUCT_ROOT / "mvp" / "review_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import ask_tool, fact_tool, factstore, review_tool
finally:
    sys.path.pop(0)


TEXT = "甲拿起钥匙。乙离开。"
QUOTE = "甲拿起钥匙。"
DECIDED_AT = "2026-08-19 15:00:00"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_ref(*, revision_no: int = 1) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": _sha256(TEXT),
    }


def _snapshot() -> list[dict]:
    revision_ref = _revision_ref()
    result = fact_tool.execute(
        {
            "chapter": {
                "contract": "C1_CHAPTER_DOC",
                "version": "v1",
                "id": "c01",
                "title": "第一章",
                "kind": "draft",
                "text": TEXT,
                "added_at": "2026-08-19 14:00:00",
                "chapter_revision_ref": revision_ref,
            },
            "segments": [
                {
                    "contract": "C2_SEGMENT",
                    "version": "v1",
                    "chapter_revision_ref": revision_ref,
                    "seg": 1,
                    "text": TEXT,
                    "start": 0,
                    "end": len(TEXT),
                    "halo_before": "",
                    "halo_after": "",
                }
            ],
            "candidates": [
                {
                    "contract": "C3_FACT_CANDIDATE",
                    "version": "v1",
                    "chapter_revision_ref": revision_ref,
                    "text": "甲拿起钥匙。",
                    "quote": QUOTE,
                    "seg": 1,
                }
            ],
            "source": "M5_STANDALONE_FIXTURE",
            "added_at": "2026-08-19 14:01:00",
        }
    )
    return result["facts"]


def _two_fact_snapshot() -> list[dict]:
    facts = _snapshot()
    second = copy.deepcopy(facts[0])
    quote = "乙离开。"
    start = TEXT.index(quote)
    second.update(
        {
            "id": "f002",
            "text": quote,
            "quote": quote,
            "anchor_ref": {
                **_revision_ref(),
                "coordinate_basis": factstore.ANCHOR_COORDINATE_BASIS,
                "start": start,
                "end": start + len(quote),
                "slice_sha256": _sha256(quote),
            },
        }
    )
    return factstore.validate_c4_v1_snapshot([*facts, second])


def _request(
    decision: str,
    *,
    operation_id: str,
    snapshot: list[dict] | None = None,
) -> dict:
    facts = _snapshot() if snapshot is None else snapshot
    action = factstore.build_review_action(
        facts[0],
        decision=decision,
        operation_id=operation_id,
    )
    return {
        "snapshot_version": 1,
        "expected_snapshot_version": 1,
        "expected_snapshot_sha256": factstore.c4_snapshot_sha256(facts),
        "facts": facts,
        "chapter_revision_ref": copy.deepcopy(facts[0]["chapter_revision_ref"]),
        "action": action,
        "decided_at": DECIDED_AT,
    }


def _action_item(
    fact: dict,
    decision: str,
    operation_id: str,
    decided_at: str,
) -> dict:
    return {
        "chapter_revision_ref": copy.deepcopy(fact["chapter_revision_ref"]),
        "action": factstore.build_review_action(
            fact,
            decision=decision,
            operation_id=operation_id,
        ),
        "decided_at": decided_at,
    }


def _batch_request() -> dict:
    facts = _two_fact_snapshot()
    return {
        "snapshot_version": 1,
        "snapshot_sha256": factstore.c4_snapshot_sha256(facts),
        "facts": facts,
        "items": [
            _action_item(
                facts[0],
                "confirm",
                "op-batch-confirm-f001",
                "2026-08-19 15:00:00",
            ),
            _action_item(
                facts[1],
                "reject",
                "op-batch-reject-f002",
                "2026-08-19 15:01:00",
            ),
        ],
    }


def _ask(facts: list[dict]) -> dict:
    return ask_tool.execute(
        {
            "query": "钥匙",
            "facts": facts,
            "current_revision_refs": [_revision_ref()],
        }
    )


def test_author_confirm_makes_current_extracted_visible_to_m6() -> None:
    request = _request("confirm", operation_id="op-review-confirm")
    before_fact = copy.deepcopy(request["facts"][0])

    before_query = _ask(request["facts"])
    result = review_tool.execute(request)
    after_query = _ask(result["facts"])

    assert before_query["matches"] == []
    assert before_query["excluded_counts"]["extracted"] == 1
    assert [row["fact_id"] for row in after_query["matches"]] == ["f001"]
    fact = result["facts"][0]
    assert fact["status"] == "confirmed" and fact["decided_at"] == DECIDED_AT
    for key in ("quote", "source", "anchor_ref", "chapter_revision_ref"):
        assert fact[key] == before_fact[key]
    assert result["snapshot_version"] == 2
    assert result["receipt"]["actor"] == "author"
    assert result["receipt"]["decision"] == "confirm"
    factstore.validate_c4_v1_snapshot(result["facts"])


def test_author_reject_remains_excluded_from_m6() -> None:
    request = _request("reject", operation_id="op-review-reject")

    result = review_tool.execute(request)

    assert result["facts"][0]["status"] == "rejected"
    query = _ask(result["facts"])
    assert query["matches"] == []
    assert query["excluded_counts"]["rejected"] == 1


def test_explicit_same_chapter_batch_matches_two_single_calls_byte_for_byte() -> None:
    request = _batch_request()
    first_item, second_item = request["items"]
    first = review_tool.execute(
        {
            "snapshot_version": request["snapshot_version"],
            "expected_snapshot_version": request["snapshot_version"],
            "expected_snapshot_sha256": request["snapshot_sha256"],
            "facts": request["facts"],
            **first_item,
        }
    )
    second = review_tool.execute(
        {
            "snapshot_version": first["snapshot_version"],
            "expected_snapshot_version": first["snapshot_version"],
            "expected_snapshot_sha256": first["snapshot_sha256"],
            "facts": first["facts"],
            **second_item,
        }
    )
    sequential = {
        "snapshot_version": second["snapshot_version"],
        "snapshot_sha256": second["snapshot_sha256"],
        "facts": second["facts"],
        "receipts": [first["receipt"], second["receipt"]],
        "input_count": 2,
        "applied_count": 2,
    }

    result = review_tool.execute_batch(request)

    assert review_tool._json_bytes(result) == review_tool._json_bytes(sequential)
    assert [fact["status"] for fact in result["facts"]] == [
        "confirmed",
        "rejected",
    ]
    assert [item["before_snapshot_version"] for item in result["receipts"]] == [
        1,
        2,
    ]
    assert [item["after_snapshot_version"] for item in result["receipts"]] == [
        2,
        3,
    ]
    assert result["snapshot_version"] == 3
    assert result["input_count"] == result["applied_count"] == len(
        result["receipts"]
    )


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda request: request["items"].append(
                {
                    **copy.deepcopy(request["items"][0]),
                    "action": {
                        **copy.deepcopy(request["items"][0]["action"]),
                        "operation_id": "op-other-same-fact",
                    },
                }
            ),
            "REVIEW_BATCH_FACT_REF_DUPLICATE",
        ),
        (
            lambda request: request["items"][1]["action"].update(
                operation_id=request["items"][0]["action"]["operation_id"]
            ),
            "REVIEW_BATCH_OPERATION_ID_DUPLICATE",
        ),
        (
            lambda request: request.update(items=[]),
            "REVIEW_TOOL_BATCH_ITEMS_REQUIRED",
        ),
        (
            lambda request: request["items"][0].update(extra="forbidden"),
            "REVIEW_TOOL_BATCH_ITEM_SHAPE_INVALID:0",
        ),
    ],
)
def test_batch_shape_and_uniqueness_fail_before_any_single_execute(
    monkeypatch,
    mutate,
    reason: str,
) -> None:
    request = _batch_request()
    mutate(request)
    calls = 0
    original_execute = review_tool.execute

    def recording_execute(single_request: dict) -> dict:
        nonlocal calls
        calls += 1
        return original_execute(single_request)

    monkeypatch.setattr(review_tool, "execute", recording_execute)
    with pytest.raises(factstore.FactstoreError, match=reason):
        review_tool.execute_batch(request)
    assert calls == 0


def test_cross_revision_batch_fails_before_any_single_execute(monkeypatch) -> None:
    request = _batch_request()
    fact = request["facts"][1]
    cross_ref = {
        "chapter_id": "c02",
        "revision_no": 1,
        "revision_text_sha256": "2" * 64,
    }
    fact["chapter_id"] = "c02"
    fact["chapter_revision_ref"] = copy.deepcopy(cross_ref)
    fact["anchor_ref"].update(cross_ref)
    request["snapshot_sha256"] = factstore.c4_snapshot_sha256(request["facts"])
    request["items"][1] = _action_item(
        fact,
        "reject",
        "op-cross-chapter",
        "2026-08-19 15:01:00",
    )
    calls = 0
    original_execute = review_tool.execute

    def recording_execute(single_request: dict) -> dict:
        nonlocal calls
        calls += 1
        return original_execute(single_request)

    monkeypatch.setattr(review_tool, "execute", recording_execute)
    with pytest.raises(
        factstore.FactstoreError,
        match="REVIEW_BATCH_CROSS_REVISION_SCOPE",
    ):
        review_tool.execute_batch(request)
    assert calls == 0


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda request: request.update(expected_snapshot_version=1, snapshot_version=2),
            "STALE_SNAPSHOT_VERSION",
        ),
        (
            lambda request: request.update(chapter_revision_ref=_revision_ref(revision_no=2)),
            "STALE_CHAPTER_REVISION_REF",
        ),
        (
            lambda request: request["action"].update(expected_status="confirmed"),
            "STALE_FACT_REVISION",
        ),
    ],
)
def test_stale_version_ref_or_fact_binding_rejects_whole_request(
    mutate,
    reason: str,
) -> None:
    request = _request("confirm", operation_id="op-review-stale")
    before = copy.deepcopy(request["facts"])
    mutate(request)

    with pytest.raises(factstore.FactstoreError, match=reason):
        review_tool.execute(request)
    assert request["facts"] == before


def test_one_bad_fact_rejects_entire_snapshot_before_target_change() -> None:
    request = _request("confirm", operation_id="op-review-bad-batch")
    bad = copy.deepcopy(request["facts"][0])
    bad["id"] = "f002"
    bad["anchor_ref"]["slice_sha256"] = "0" * 64
    request["facts"].append(bad)

    with pytest.raises(
        factstore.FactstoreError,
        match="C4_ANCHOR_QUOTE_SHA_MISMATCH",
    ):
        review_tool.execute(request)
    assert request["facts"][0]["status"] == "extracted"


def test_exact_repeat_is_deterministic_and_conflicting_action_shape_is_rejected() -> None:
    request = _request("confirm", operation_id="op-review-repeat")

    first = review_tool.execute(request)
    replay = review_tool.execute(copy.deepcopy(request))

    assert replay == first
    conflict = copy.deepcopy(request)
    conflict["action"]["replacement_text"] = "不得夹带改写"
    with pytest.raises(
        factstore.FactstoreError,
        match="FACT_REVIEW_REPLACEMENT_FORBIDDEN",
    ):
        review_tool.execute(conflict)


def test_uncontracted_reopen_action_is_rejected() -> None:
    request = _request("confirm", operation_id="op-review-reopen")
    request["action"]["decision"] = "reopen"

    with pytest.raises(
        factstore.FactstoreError,
        match="FACT_REVIEW_DECISION_INVALID",
    ):
        review_tool.execute(request)


def test_cli_atomic_output_can_restart_parse_and_failure_does_not_overwrite(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "result.json"
    request = _request("confirm", operation_id="op-review-cli")
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    success = subprocess.run(
        [
            sys.executable,
            str(REVIEW_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert success.returncode == 0, success.stderr
    reread = json.loads(output_path.read_text(encoding="utf-8"))
    assert reread["facts"][0]["status"] == "confirmed"
    factstore.validate_c4_v1_snapshot(reread["facts"])

    bad_request = copy.deepcopy(request)
    bad_request["chapter_revision_ref"] = _revision_ref(revision_no=2)
    input_path.write_text(json.dumps(bad_request, ensure_ascii=False), encoding="utf-8")
    before_bytes = output_path.read_bytes()
    failure = subprocess.run(
        [
            sys.executable,
            str(REVIEW_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert failure.returncode == 2 and failure.stdout == ""
    assert "STALE_CHAPTER_REVISION_REF" in failure.stderr
    assert output_path.read_bytes() == before_bytes
    assert not list(tmp_path.glob(".*.tmp"))


def test_batch_second_stale_action_does_not_return_or_overwrite_partial_output(
    tmp_path: Path,
) -> None:
    request = _batch_request()
    request["items"][1]["action"]["expected_fact_sha256"] = "0" * 64
    with pytest.raises(factstore.FactstoreError, match="STALE_FACT_REVISION"):
        review_tool.execute_batch(request)

    input_path = tmp_path / "bad-batch.json"
    output_path = tmp_path / "keep-batch.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    output_path.write_text("DO_NOT_OVERWRITE", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(REVIEW_TOOL_SCRIPT),
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
    assert "STALE_FACT_REVISION" in completed.stderr
    assert output_path.read_text(encoding="utf-8") == "DO_NOT_OVERWRITE"
    assert not list(tmp_path.glob(".*.tmp"))


def test_batch_cli_is_restart_parseable_and_byte_stable(tmp_path: Path) -> None:
    input_path = tmp_path / "batch.json"
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"
    input_path.write_text(
        json.dumps(_batch_request(), ensure_ascii=False),
        encoding="utf-8",
    )
    prefix = [sys.executable, str(REVIEW_TOOL_SCRIPT), "--input", str(input_path)]
    for output_path in (first_output, second_output):
        completed = subprocess.run(
            [*prefix, "--output", str(output_path)],
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )
        assert completed.returncode == 0, completed.stderr

    assert first_output.read_bytes() == second_output.read_bytes()
    parsed = json.loads(first_output.read_text(encoding="utf-8"))
    assert parsed["snapshot_version"] == 3
    assert parsed["input_count"] == parsed["applied_count"] == 2


def test_execute_rejects_path_instead_of_reading_it(tmp_path: Path) -> None:
    with pytest.raises(
        factstore.FactstoreError,
        match="REVIEW_TOOL_REQUEST_NOT_OBJECT",
    ):
        review_tool.execute(tmp_path / "facts.json")  # type: ignore[arg-type]

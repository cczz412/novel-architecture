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
TOOL_PATH = PRODUCT_ROOT / "mvp" / "fact_revision_preflight_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from contracts import validate_c11_chapter_revision_ledger as c11_contract
    from mvp import fact_revision_preflight_tool, factstore
finally:
    sys.path.pop(0)


OLD_TEXT = "甲拿起钥匙。乙离开院子。丙点亮油灯。"
MOVED_TEXT = "丙点亮油灯。甲拿起钥匙。乙离开院子。"
OTHER_TEXT = "丁关上窗户。"


def _text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _ref(chapter_id: str, text: str, revision_no: int) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": _text_sha(text),
    }


def _chapter(
    text: str,
    revision_no: int,
    *,
    chapter_id: str = "c01",
) -> dict:
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": "第一章",
        "kind": "draft",
        "text": text,
        "added_at": "2026-08-20 10:00:00",
        "chapter_revision_ref": _ref(chapter_id, text, revision_no),
    }


def _external_route_request(
    chapter: dict,
    *,
    history: list[str] | None = None,
) -> dict:
    revision_no = chapter["chapter_revision_ref"]["revision_no"]
    if history is None:
        history = [
            chapter["text"] if number == revision_no else f"中间版本{number}。"
            for number in range(1, revision_no + 1)
        ]
    if len(history) != revision_no or history[-1] != chapter["text"]:
        raise AssertionError("test route history must end at current chapter")
    ledger = c11_contract.ledger_one(history[0])
    for number, text in enumerate(history[1:], start=2):
        ledger = c11_contract.append_replace(
            ledger,
            text,
            operation_id=f"op-r{number}",
        )
    return {
        "material_identity": c11_contract.c10_material_record(
            chapter["text"],
            f"R{revision_no}",
        ),
        "chapter_revision_ledger": ledger,
        "chapter_doc": copy.deepcopy(chapter),
    }


def _fact(
    fact_id: str,
    quote: str,
    *,
    status: str = "confirmed",
    text: str = OLD_TEXT,
    revision_no: int = 1,
    chapter_id: str = "c01",
    verified: bool = True,
) -> dict:
    revision_ref = _ref(chapter_id, text, revision_no)
    anchor = None
    if verified:
        start = text.index(quote)
        anchor = {
            **revision_ref,
            "coordinate_basis": factstore.ANCHOR_COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": _text_sha(quote),
        }
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter_id,
        "text": f"事实 {fact_id}",
        "quote": quote,
        "status": status,
        "source": "SYNTHETIC_C4",
        "note": "",
        "added_at": "2026-08-20 10:01:00",
        "chapter_revision_ref": revision_ref,
        "anchor_ref": anchor,
        "anchor_state": "VERIFIED" if verified else "LEGACY_UNVERIFIED",
        "recheck": None,
    }


def _request(
    *,
    new_text: str = MOVED_TEXT,
    facts: list[dict] | None = None,
) -> dict:
    if facts is None:
        facts = [
            _fact("f001", "甲拿起钥匙。", status="confirmed"),
            _fact("f002", "乙离开院子。", status="extracted"),
            _fact("f003", "丙点亮油灯。", status="rejected"),
            _fact(
                "f004",
                "丁关上窗户。",
                status="confirmed",
                text=OTHER_TEXT,
                chapter_id="c02",
            ),
        ]
    old_chapter = _chapter(OLD_TEXT, 1)
    return {
        "old_chapter": old_chapter,
        "new_chapter": _chapter(new_text, 2),
        "facts": facts,
        "operation_id": "op-m4-revision-preflight-01",
        "flagged_at": "2026-08-20T10:02:00+08:00",
        "external_route_request": _external_route_request(old_chapter),
    }


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_unique_moved_evidence_advances_revision_and_preserves_statuses() -> None:
    request = _request()
    result = fact_revision_preflight_tool.execute(request)

    assert [fact["id"] for fact in result["proposed_facts"]] == [
        "f001",
        "f002",
        "f003",
        "f004",
    ]
    for before, after in zip(request["facts"][:3], result["proposed_facts"][:3]):
        assert after["status"] == before["status"]
        assert after["chapter_revision_ref"] == _ref("c01", MOVED_TEXT, 2)
        assert after["anchor_state"] == "VERIFIED"
        assert after["recheck"] is None
        anchor = after["anchor_ref"]
        assert MOVED_TEXT[anchor["start"] : anchor["end"]] == after["quote"]
    assert result["proposed_facts"][3] == request["facts"][3]
    assert [row["effect"] for row in result["effects"]] == [
        "revision_advanced",
        "revision_advanced",
        "revision_advanced",
        "unchanged_other_chapter",
    ]
    assert result["summary"] == {
        "input_fact_count": 4,
        "target_chapter_fact_count": 3,
        "revision_advanced_count": 3,
        "needs_recheck_count": 0,
        "unchanged_other_chapter_count": 1,
        "unchanged_already_needs_recheck_count": 0,
    }
    assert result["writes"] == {
        "c11": "none",
        "c1": "none",
        "facts": "none",
        "plan": "none",
    }
    assert result["source"]["external_route_receipt"]["identity"] == (
        "EXTERNAL_CHAPTER_ROUTE_RECEIPT_R01"
    )
    assert result["source"]["external_route_receipt"]["source_kind"] == (
        "EXTERNAL_CONFIRMED_CHAPTER"
    )


def test_deleted_and_duplicated_evidence_become_needs_recheck() -> None:
    new_text = "乙离开院子。丙点亮油灯。乙离开院子。"
    facts = [
        _fact("f001", "甲拿起钥匙。", status="confirmed"),
        _fact("f002", "乙离开院子。", status="extracted"),
    ]
    result = fact_revision_preflight_tool.execute(
        _request(new_text=new_text, facts=facts)
    )

    assert [fact["status"] for fact in result["proposed_facts"]] == [
        "needs_recheck",
        "needs_recheck",
    ]
    assert [fact["recheck"]["reason"] for fact in result["proposed_facts"]] == [
        "evidence_gone",
        "anchor_ambiguous",
    ]
    assert all(
        fact["chapter_revision_ref"] == _ref("c01", OLD_TEXT, 1)
        for fact in result["proposed_facts"]
    )
    assert [fact["recheck"]["previous_status"] for fact in result["proposed_facts"]] == [
        "confirmed",
        "extracted",
    ]


def test_legacy_quote_only_upgrades_when_old_and_new_are_both_unique() -> None:
    success = _fact("f001", "甲拿起钥匙。", verified=False)
    repeated_old = "重复。重复。"
    failure = _fact(
        "f002",
        "重复。",
        text=repeated_old,
        verified=False,
    )
    success_result = fact_revision_preflight_tool.execute(
        _request(facts=[success])
    )["proposed_facts"][0]
    assert success_result["status"] == "confirmed"
    assert success_result["anchor_state"] == "VERIFIED"
    assert success_result["chapter_revision_ref"]["revision_no"] == 2

    request = {
        **_request(new_text="重复。", facts=[failure]),
        "old_chapter": _chapter(repeated_old, 1),
        "new_chapter": _chapter("重复。", 2),
    }
    request["external_route_request"] = _external_route_request(
        request["old_chapter"]
    )
    failed_result = fact_revision_preflight_tool.execute(request)[
        "proposed_facts"
    ][0]
    assert failed_result["status"] == "needs_recheck"
    assert failed_result["anchor_state"] == "LEGACY_UNVERIFIED"
    assert failed_result["recheck"]["reason"] == "legacy_anchor_unverified"


def test_existing_needs_recheck_is_preserved_without_new_claim() -> None:
    fact = _fact("f001", "甲拿起钥匙。", status="confirmed")
    fact["status"] = "needs_recheck"
    fact["recheck"] = {
        "previous_status": "confirmed",
        "reason": "evidence_gone",
        "from_revision_no": 1,
        "target_revision_no": 2,
        "flagged_at": "2026-08-20T09:00:00+08:00",
    }
    old_r2 = _chapter("乙离开院子。", 2)
    request = {
        "old_chapter": old_r2,
        "new_chapter": _chapter("乙走出院子。", 3),
        "facts": [fact],
        "operation_id": "op-existing-needs-recheck",
        "flagged_at": "2026-08-20T10:03:00+08:00",
        "external_route_request": _external_route_request(
            old_r2,
            history=[OLD_TEXT, old_r2["text"]],
        ),
    }
    result = fact_revision_preflight_tool.execute(request)
    assert result["proposed_facts"] == [fact]
    assert result["effects"][0]["effect"] == "unchanged_already_needs_recheck"
    assert result["summary"]["unchanged_already_needs_recheck_count"] == 1


def test_needs_recheck_from_older_revision_survives_next_revision_preflight() -> None:
    first = fact_revision_preflight_tool.execute(
        _request(
            new_text="乙离开院子。",
            facts=[_fact("f001", "甲拿起钥匙。")],
        )
    )
    old_r2 = _chapter("乙离开院子。", 2)
    request = {
        "old_chapter": old_r2,
        "new_chapter": _chapter("乙走出院子。", 3),
        "facts": first["proposed_facts"],
        "operation_id": "op-m4-revision-preflight-02",
        "flagged_at": "2026-08-20T10:03:00+08:00",
        "external_route_request": _external_route_request(
            old_r2,
            history=[OLD_TEXT, old_r2["text"]],
        ),
    }

    second = fact_revision_preflight_tool.execute(request)
    assert second["proposed_facts"] == first["proposed_facts"]
    assert second["effects"][0]["effect"] == "unchanged_already_needs_recheck"
    assert second["proposed_facts"][0]["chapter_revision_ref"]["revision_no"] == 1
    assert second["proposed_facts"][0]["recheck"]["target_revision_no"] == 2


@pytest.mark.parametrize("damage", ["historical_sha", "target_equals_from"])
def test_old_needs_recheck_identity_must_close_against_ledger_history(
    damage: str,
) -> None:
    first = fact_revision_preflight_tool.execute(
        _request(
            new_text="乙离开院子。",
            facts=[_fact("f001", "甲拿起钥匙。")],
        )
    )
    fact = first["proposed_facts"][0]
    if damage == "historical_sha":
        fact["chapter_revision_ref"]["revision_text_sha256"] = "0" * 64
        fact["anchor_ref"]["revision_text_sha256"] = "0" * 64
    else:
        fact["recheck"]["target_revision_no"] = fact["recheck"][
            "from_revision_no"
        ]
    old_r2 = _chapter("乙离开院子。", 2)
    request = {
        "old_chapter": old_r2,
        "new_chapter": _chapter("乙走出院子。", 3),
        "facts": [fact],
        "operation_id": f"op-invalid-history-{damage}",
        "flagged_at": "2026-08-20T10:05:00+08:00",
        "external_route_request": _external_route_request(
            old_r2,
            history=[OLD_TEXT, old_r2["text"]],
        ),
    }

    with pytest.raises(
        fact_revision_preflight_tool.FactRevisionPreflightError,
        match="TARGET_NEEDS_RECHECK_LINEAGE_INVALID:f001",
    ):
        fact_revision_preflight_tool.execute(request)


def test_overlapping_literal_matches_are_anchor_ambiguous() -> None:
    old_text = "哈哈。"
    old_chapter = _chapter(old_text, 1)
    request = {
        "old_chapter": old_chapter,
        "new_chapter": _chapter("哈哈哈。", 2),
        "facts": [_fact("f001", "哈哈", text=old_text)],
        "operation_id": "op-overlap",
        "flagged_at": "2026-08-20T10:04:00+08:00",
        "external_route_request": _external_route_request(old_chapter),
    }
    proposed = fact_revision_preflight_tool.execute(request)["proposed_facts"][0]
    assert proposed["status"] == "needs_recheck"
    assert proposed["recheck"]["reason"] == "anchor_ambiguous"


def test_result_is_stable_validated_and_does_not_mutate_input() -> None:
    request = _request()
    before = copy.deepcopy(request)
    first = fact_revision_preflight_tool.execute(request)
    second = fact_revision_preflight_tool.execute(copy.deepcopy(request))

    assert request == before
    assert _canonical_bytes(first) == _canonical_bytes(second)
    assert fact_revision_preflight_tool.validate_result(first) == first
    core = copy.deepcopy(first)
    digest = core.pop("prototype_sha256")
    assert digest == hashlib.sha256(_canonical_bytes(core)).hexdigest()
    assert first["identity"] == "FACT_REVISION_MIGRATION_PREFLIGHT_PROTOTYPE_R01"
    assert first["prototype"] is True
    assert "COMMITTED" not in _canonical_bytes(first).decode("utf-8")


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda value: value["old_chapter"]["chapter_revision_ref"].update(
                revision_text_sha256="0" * 64
            ),
            "OLD_CHAPTER_REVISION_SHA_MISMATCH",
        ),
        (
            lambda value: value["new_chapter"].update(
                id="c02",
                chapter_revision_ref=_ref("c02", MOVED_TEXT, 2),
            ),
            "CHAPTER_ID_CHANGED",
        ),
        (
            lambda value: value["new_chapter"].update(
                chapter_revision_ref=_ref("c01", MOVED_TEXT, 3)
            ),
            "REVISION_MUST_INCREMENT_BY_ONE",
        ),
        (
            lambda value: value["facts"][0].update(
                chapter_revision_ref=_ref("c01", OLD_TEXT, 2)
            ),
            "C4_SNAPSHOT_INVALID",
        ),
        (
            lambda value: value["facts"][0]["anchor_ref"].update(
                start=1,
                end=1 + len("甲拿起钥匙。"),
            ),
            "TARGET_FACT_OLD_ANCHOR_SLICE_MISMATCH",
        ),
        (
            lambda value: value["facts"][0]["anchor_ref"].update(
                slice_sha256="0" * 64
            ),
            "C4_SNAPSHOT_INVALID",
        ),
        (
            lambda value: value.update(extra="forbidden"),
            "REQUEST_FIELDS_INVALID",
        ),
    ],
)
def test_bad_chapter_fact_or_batch_shape_fails_closed(mutate, error: str) -> None:
    request = _request()
    mutate(request)
    with pytest.raises(
        fact_revision_preflight_tool.FactRevisionPreflightError,
        match=error,
    ):
        fact_revision_preflight_tool.execute(request)


def test_one_bad_fact_rejects_whole_batch_without_partial_result() -> None:
    request = _request()
    request["facts"][1]["anchor_ref"]["slice_sha256"] = "f" * 64
    with pytest.raises(
        fact_revision_preflight_tool.FactRevisionPreflightError,
        match="C4_SNAPSHOT_INVALID",
    ):
        fact_revision_preflight_tool.execute(request)


def test_result_tampering_is_rejected() -> None:
    result = fact_revision_preflight_tool.execute(_request())
    result["proposed_facts"][0]["status"] = "rejected"
    with pytest.raises(
        fact_revision_preflight_tool.FactRevisionPreflightError,
        match="RESULT_EFFECT_FACT_ALIGNMENT_INVALID|RESULT_SHA_MISMATCH",
    ):
        fact_revision_preflight_tool.validate_result(result)


def test_recomputed_sha_cannot_hide_other_chapter_fact_tampering() -> None:
    result = fact_revision_preflight_tool.execute(_request())
    result["proposed_facts"][3]["text"] = "调用方偷换了另一章事实。"
    core = copy.deepcopy(result)
    core.pop("prototype_sha256")
    result["prototype_sha256"] = hashlib.sha256(_canonical_bytes(core)).hexdigest()

    with pytest.raises(
        fact_revision_preflight_tool.FactRevisionPreflightError,
        match="RESULT_SEMANTIC_REPLAY_MISMATCH",
    ):
        fact_revision_preflight_tool.validate_result(result)


@pytest.mark.parametrize(
    "damage",
    ["fake_lane", "not_chapter", "generated_draft", "different_chapter"],
)
def test_external_route_must_mechanically_prove_same_old_chapter(damage: str) -> None:
    request = _request()
    route = request["external_route_request"]
    if damage == "fake_lane":
        route["source_kind"] = "EXTERNAL_CONFIRMED_CHAPTER"
    elif damage == "not_chapter":
        route["material_identity"] = c11_contract.c10_material_record(
            OLD_TEXT,
            "R1",
            role="SETTING",
        )
    elif damage == "generated_draft":
        route["chapter_doc"] = {
            "contract": "CHAPTER_FACT_DRAFT_PROTOTYPE_R01",
            "prototype": True,
            "entries": [{"fact_text": "作者自产事实句。"}],
        }
    else:
        other = _chapter("另一份合法外来章。", 1)
        request["external_route_request"] = _external_route_request(other)

    with pytest.raises(
        fact_revision_preflight_tool.FactRevisionPreflightError,
        match="EXTERNAL_ROUTE_INVALID|EXTERNAL_ROUTE_OLD_CHAPTER_MISMATCH",
    ):
        fact_revision_preflight_tool.execute(request)


def test_cli_stdin_stdout_and_file_output_are_byte_stable(tmp_path: Path) -> None:
    payload = _canonical_bytes(_request())
    first = _run_cli(stdin=payload)
    second = _run_cli(stdin=payload)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    parsed = json.loads(first.stdout)
    assert fact_revision_preflight_tool.validate_result(parsed) == parsed

    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_bytes(payload)
    completed = _run_cli("--input", str(input_path), "--output", str(output_path))
    assert completed.returncode == 0
    assert output_path.read_bytes() == first.stdout


@pytest.mark.parametrize("alias_kind", ["same", "symlink", "hardlink"])
def test_cli_rejects_input_output_aliases(tmp_path: Path, alias_kind: str) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_bytes(_canonical_bytes(_request()))
    if alias_kind == "same":
        output_path = input_path
    elif alias_kind == "symlink":
        output_path = tmp_path / "output-link.json"
        output_path.symlink_to(input_path)
    else:
        output_path = tmp_path / "output-hard.json"
        os.link(input_path, output_path)
    before = input_path.read_bytes()

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))
    assert completed.returncode == 2
    assert b"INPUT_OUTPUT_PATH_MUST_DIFFER" in completed.stderr
    assert input_path.read_bytes() == before


def test_atomic_replace_failure_preserves_old_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "result.json"
    output.write_text("old-output", encoding="utf-8")
    result = fact_revision_preflight_tool.execute(_request())

    def fail_replace(source, target):
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(fact_revision_preflight_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic replace failure"):
        fact_revision_preflight_tool._write_atomic(str(output), result)
    assert output.read_text(encoding="utf-8") == "old-output"
    assert not list(tmp_path.glob(".result.json.*.tmp"))

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
ADAPTER_SCRIPT = PRODUCT_ROOT / "mvp" / "fact_handoff_adapter.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        ask_tool,
        check_tool,
        fact_handoff_adapter,
        fact_tool,
        factstore,
        overview,
        overview_tool,
        review_tool,
    )
finally:
    sys.path.pop(0)


TEXTS = {
    "c01": "甲拿起钥匙。乙看见了钥匙。",
    "c02": "丙关上窗户。",
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_ref(chapter_id: str) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": 1,
        "revision_text_sha256": _sha256(TEXTS[chapter_id]),
    }


def _append_chapter(
    *,
    chapter_id: str,
    candidates: list[tuple[str, str]],
    existing_c4: list[dict] | None = None,
) -> dict:
    text = TEXTS[chapter_id]
    revision_ref = _revision_ref(chapter_id)
    request = {
        "chapter": {
            "contract": "C1_CHAPTER_DOC",
            "version": "v1",
            "id": chapter_id,
            "title": f"合成{chapter_id}",
            "kind": "draft",
            "text": text,
            "added_at": "2026-08-19 19:00:00",
            "chapter_revision_ref": revision_ref,
        },
        "segments": [
            {
                "contract": "C2_SEGMENT",
                "version": "v1",
                "chapter_revision_ref": revision_ref,
                "seg": 1,
                "text": text,
                "start": 0,
                "end": len(text),
                "halo_before": "",
                "halo_after": "",
            }
        ],
        "candidates": [
            {
                "contract": "C3_FACT_CANDIDATE",
                "version": "v1",
                "chapter_revision_ref": revision_ref,
                "text": fact_text,
                "quote": quote,
                "seg": 1,
            }
            for fact_text, quote in candidates
        ],
        "source": "SYNTHETIC_HANDOFF_FIXTURE",
        "added_at": "2026-08-19 19:01:00",
    }
    if existing_c4 is not None:
        request["existing_c4"] = existing_c4
    return fact_tool.execute(request)


def _single_chapter_m4() -> dict:
    return _append_chapter(
        chapter_id="c01",
        candidates=[
            ("甲拿起钥匙。", "甲拿起钥匙。"),
            ("乙看见了钥匙。", "乙看见了钥匙。"),
        ],
    )


def _multi_chapter_m4() -> dict:
    first = _single_chapter_m4()
    return _append_chapter(
        chapter_id="c02",
        candidates=[("丙关上窗户。", "丙关上窗户。")],
        existing_c4=first["facts"],
    )


def _action_item(fact: dict, operation_id: str, *, decided_at: str) -> dict:
    return {
        "action": factstore.build_review_action(
            fact,
            decision="confirm",
            operation_id=operation_id,
        ),
        "chapter_revision_ref": copy.deepcopy(fact["chapter_revision_ref"]),
        "decided_at": decided_at,
    }


def _overview_response(fact_refs: list[str], chapter_id: str) -> dict:
    return {
        "synopsis": f"{chapter_id} 的合成事实概览。",
        "beats": [
            {
                "text": f"{chapter_id} 的可追溯节拍。",
                "fact_refs": fact_refs,
                "visual_hint": "合成排版卡。",
            }
        ],
        "orphan_refs": [],
        "visual_hint": "合成章概览。",
    }


def _request(m4_output: dict | None = None) -> dict:
    m4_output = copy.deepcopy(m4_output or _single_chapter_m4())
    facts = m4_output["facts"]
    chapter_ids = sorted({fact["chapter_id"] for fact in facts})
    return {
        "m4_output": m4_output,
        "author_actions": [
            _action_item(facts[0], "op-confirm-f001", decided_at="2026-08-19 19:02:00"),
            _action_item(facts[1], "op-confirm-f002", decided_at="2026-08-19 19:03:00"),
        ],
        "current_revision_refs": [_revision_ref(chapter_id) for chapter_id in chapter_ids],
        "m6_query": "钥匙",
        "m7_check": {
            "project_display_name": "合成事实分支",
            "generated_at": "2026-08-19 19:04:00",
            "check_config": {
                "scope_name": "当前合成事实",
                "scope_kind": "leftover",
                "kinds": ["naming", "timeline", "setting", "event"],
            },
        },
        "m9_config": {
            "generated_at": "2026-08-19 19:05:00",
            "provider_bindings_by_chapter": {
                chapter_id: _overview_response(
                    [fact["id"] for fact in facts if fact["chapter_id"] == chapter_id],
                    chapter_id,
                )
                for chapter_id in chapter_ids
            },
        },
    }


def test_two_explicit_confirms_feed_existing_m6_m7_m9_without_field_edits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    before = copy.deepcopy(request)
    seen_review_requests: list[dict] = []
    original_execute = review_tool.execute

    def recording_execute(review_request: dict) -> dict:
        seen_review_requests.append(copy.deepcopy(review_request))
        return original_execute(review_request)

    monkeypatch.setattr(fact_handoff_adapter.review_tool, "execute", recording_execute)
    result = fact_handoff_adapter.execute(request)

    assert request == before
    assert set(result) == {
        "reviewed_snapshot",
        "m6_request",
        "m7_request",
        "m9_requests_by_chapter",
    }
    snapshot = result["reviewed_snapshot"]
    assert snapshot["snapshot_version"] == 3
    assert [fact["status"] for fact in snapshot["facts"]] == [
        "confirmed",
        "confirmed",
    ]
    assert [item["snapshot_version"] for item in seen_review_requests] == [1, 2]
    assert [item["expected_snapshot_version"] for item in seen_review_requests] == [
        1,
        2,
    ]
    assert all(
        item["expected_snapshot_sha256"]
        == factstore.c4_snapshot_sha256(item["facts"])
        for item in seen_review_requests
    )

    m6_result = ask_tool.execute(result["m6_request"])
    assert [item["fact_id"] for item in m6_result["matches"]] == ["f001", "f002"]

    m7_result = check_tool.execute(
        result["m7_request"],
        check_tool.FrozenFindingProvider(
            {
                "provider_id": "frozen-zero-call-handoff-check",
                "model_calls": 0,
                "response": {"findings": []},
            }
        ),
    )
    assert m7_result["scan"]["confirmed"] == 2
    assert m7_result["scan"]["api_calls"] == 0

    m9_request = result["m9_requests_by_chapter"]["c01"]
    frozen_response = request["m9_config"]["provider_bindings_by_chapter"]["c01"]
    provider = overview_tool.offline_overview_provider(
        {overview.provider_key_for_request(m9_request): frozen_response}
    )
    m9_result = overview_tool.execute(m9_request, provider)
    assert m9_result["contract"] == "C5_OVERVIEW_CARD_PROTOTYPE"
    assert m9_result["coverage"]["fact_count"] == 2


def test_multi_chapter_snapshot_is_split_into_unique_m9_requests() -> None:
    m4_output = _multi_chapter_m4()
    request = _request(m4_output)

    result = fact_handoff_adapter.execute(request)

    assert list(result["m9_requests_by_chapter"]) == ["c01", "c02"]
    c01 = result["m9_requests_by_chapter"]["c01"]
    c02 = result["m9_requests_by_chapter"]["c02"]
    assert {fact["id"] for fact in c01["facts"]} == {"f001", "f002"}
    assert {fact["id"] for fact in c02["facts"]} == {"f003"}
    assert c01["current_revision_ref"] == _revision_ref("c01")
    assert c02["current_revision_ref"] == _revision_ref("c02")


def test_cross_chapter_action_revision_is_rejected_before_m5() -> None:
    request = _request(_multi_chapter_m4())
    request["author_actions"][0]["chapter_revision_ref"] = _revision_ref("c02")

    with pytest.raises(
        fact_handoff_adapter.FactHandoffAdapterError,
        match="ACTION_REVISION_FACT_MISMATCH:f001",
    ):
        fact_handoff_adapter.execute(request)


def test_m9_stable_provider_keys_are_accepted_only_when_exact() -> None:
    request = _request()
    first = fact_handoff_adapter.execute(request)
    m9_request = first["m9_requests_by_chapter"]["c01"]
    stable_key = overview.provider_key_for_request(m9_request)
    request["m9_config"]["provider_bindings_by_chapter"] = {"c01": stable_key}

    replay = fact_handoff_adapter.execute(request)
    assert replay["m9_requests_by_chapter"]["c01"] == m9_request

    request["m9_config"]["provider_bindings_by_chapter"]["c01"] = "wrong-key"
    with pytest.raises(
        fact_handoff_adapter.FactHandoffAdapterError,
        match="M9_PROVIDER_STABLE_KEY_MISMATCH:c01",
    ):
        fact_handoff_adapter.execute(request)


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda request: request["author_actions"][1]["action"].update(
                operation_id=request["author_actions"][0]["action"]["operation_id"]
            ),
            "DUPLICATE_OPERATION_ID",
        ),
        (
            lambda request: request["author_actions"][1]["action"].update(
                fact_ref="f999"
            ),
            "UNKNOWN_ACTION_FACT:f999",
        ),
        (
            lambda request: request["author_actions"][0].update(
                chapter_revision_ref={
                    **_revision_ref("c01"),
                    "revision_no": 2,
                }
            ),
            "ACTION_REVISION_NOT_CURRENT:f001",
        ),
        (
            lambda request: request["m4_output"]["facts"][0]["anchor_ref"].update(
                slice_sha256="0" * 64
            ),
            "C4_ANCHOR_QUOTE_SHA_MISMATCH",
        ),
        (
            lambda request: request["author_actions"][1]["action"].update(
                expected_fact_sha256="0" * 64
            ),
            "STALE_FACT_REVISION",
        ),
    ],
)
def test_any_action_or_snapshot_boundary_failure_rejects_whole_batch(
    mutate,
    reason: str,
) -> None:
    request = _request()
    mutate(request)

    with pytest.raises(Exception, match=reason):
        fact_handoff_adapter.execute(request)


def test_cli_second_action_failure_does_not_overwrite_existing_output(
    tmp_path: Path,
) -> None:
    request = _request()
    request["author_actions"][1]["action"]["expected_fact_sha256"] = "0" * 64
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    original = {"sentinel": "previous-good-handoff"}
    output_path.write_text(json.dumps(original), encoding="utf-8")

    exit_code = fact_handoff_adapter.main(
        ["--input", str(input_path), "--output", str(output_path)]
    )

    assert exit_code == 2
    assert json.loads(output_path.read_text(encoding="utf-8")) == original
    assert list(tmp_path.glob(".output.json.*.tmp")) == []


def test_cli_local_single_file_output_is_restart_parseable(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(
        json.dumps(_request(), ensure_ascii=False),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(ADAPTER_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    reparsed = json.loads(output_path.read_text(encoding="utf-8"))
    assert set(reparsed) == {
        "reviewed_snapshot",
        "m6_request",
        "m7_request",
        "m9_requests_by_chapter",
    }
    assert reparsed["reviewed_snapshot"]["snapshot_version"] == 3

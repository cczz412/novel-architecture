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
OVERVIEW_TOOL_SCRIPT = PRODUCT_ROOT / "mvp" / "overview_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import overview, overview_tool
finally:
    sys.path.pop(0)


CHAPTER_TEXT = "甲拿起钥匙。乙看见了钥匙。丙离开。"
CHAPTER_TWO_TEXT = "丁推开窗户。戊听见风声。"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_ref(
    *,
    chapter_id: str = "c01",
    revision_no: int = 2,
    text: str = CHAPTER_TEXT,
) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": _sha256(text),
    }


def _fact(
    fact_id: str,
    quote: str,
    *,
    status: str = "extracted",
    source: str = "frozen-synthetic-c3",
    chapter_id: str = "c01",
    revision_no: int = 2,
    chapter_text: str = CHAPTER_TEXT,
) -> dict:
    start = chapter_text.index(quote)
    revision_ref = _revision_ref(
        chapter_id=chapter_id,
        revision_no=revision_no,
        text=chapter_text,
    )
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter_id,
        "text": quote,
        "quote": quote,
        "status": status,
        "source": source,
        "note": "",
        "added_at": "2026-08-19 18:00:00",
        "seg": 1,
        "chapter_revision_ref": revision_ref,
        "anchor_ref": {
            **revision_ref,
            "coordinate_basis": overview.COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": _sha256(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _request() -> dict:
    return {
        "facts": [
            _fact("f001", "甲拿起钥匙。", status="extracted"),
            _fact("f002", "乙看见了钥匙。", status="confirmed"),
            _fact("f003", "丙离开。", status="rejected"),
        ],
        "current_revision_ref": _revision_ref(),
        "source_revision": "facts@c01-r2-synthetic",
        "generated_at": "2026-08-19 18:05:00",
    }


def _second_request(*, chapter_id: str = "c02", revision_no: int = 1) -> dict:
    return {
        "facts": [
            _fact(
                "f101",
                "丁推开窗户。",
                status="confirmed",
                chapter_id=chapter_id,
                revision_no=revision_no,
                chapter_text=CHAPTER_TWO_TEXT,
            ),
            _fact(
                "f102",
                "戊听见风声。",
                chapter_id=chapter_id,
                revision_no=revision_no,
                chapter_text=CHAPTER_TWO_TEXT,
            ),
        ],
        "current_revision_ref": _revision_ref(
            chapter_id=chapter_id,
            revision_no=revision_no,
            text=CHAPTER_TWO_TEXT,
        ),
        "source_revision": f"facts@{chapter_id}-r{revision_no}-synthetic",
        "generated_at": "2026-08-19 18:06:00",
    }


def _provider_result() -> dict:
    return {
        "synopsis": "甲拿起钥匙，乙注意到了这个动作。",
        "beats": [
            {
                "text": "钥匙进入场景并被注意。",
                "fact_refs": ["f001", "f002"],
                "visual_hint": "近景：手、钥匙与旁观者视线。",
            }
        ],
        "orphan_refs": ["f003"],
        "visual_hint": "单章事实概览排版卡。",
    }


def _second_provider_result() -> dict:
    return {
        "synopsis": "丁推开窗户，戊听见了风声。",
        "beats": [
            {
                "text": "窗户开启，风声进入场景。",
                "fact_refs": ["f101", "f102"],
                "visual_hint": "窗边双人构图。",
            }
        ],
        "orphan_refs": [],
        "visual_hint": "第二章事实概览排版卡。",
    }


def _provider(result: dict):
    frozen = copy.deepcopy(result)

    def provide(_request: dict) -> dict:
        return copy.deepcopy(frozen)

    return provide


def _card() -> dict:
    return overview.execute(_request(), _provider(_provider_result()))


def test_execute_builds_prototype_projection_with_full_traceability() -> None:
    request = _request()
    before = copy.deepcopy(request)

    result = overview.execute(request, _provider(_provider_result()))

    assert request == before
    assert result["contract"] == "C5_OVERVIEW_CARD_PROTOTYPE"
    assert result["version"] == "v0"
    assert result["projection_only"] is True
    assert result["writes_truth"] is False
    assert result["basis"] == "fact_snapshot"
    assert result["chapter_revision_ref"] == _revision_ref()
    assert result["coverage"] == {
        "fact_count": 3,
        "beat_ref_count": 2,
        "orphan_count": 1,
        "covered_fact_count": 3,
        "coverage_ratio": 1.0,
    }
    assert result["source_summary"]["source_revision"] == "facts@c01-r2-synthetic"
    assert len(result["source_summary"]["source_facts_sha256"]) == 64
    assert result["source_summary"]["status_counts"] == {
        "confirmed": 1,
        "extracted": 1,
        "rejected": 1,
    }
    assert [item["status"] for item in result["evidence"]] == [
        "extracted",
        "confirmed",
        "rejected",
    ]
    assert all("text" not in item for item in result["source_summary"]["fact_refs"])
    assert all("text" not in item for item in result["evidence"])


def test_orphan_fact_remains_visible_and_is_not_hidden_in_a_beat() -> None:
    result = overview.execute(_request(), _provider(_provider_result()))

    assert result["orphan_refs"] == ["f003"]
    assert {ref for beat in result["beats"] for ref in beat["fact_refs"]} == {
        "f001",
        "f002",
    }
    assert result["source_summary"]["fact_count"] == 3


def test_render_card_is_complete_readable_and_every_reference_has_evidence() -> None:
    card = _card()
    before = copy.deepcopy(card)

    rendered = overview.render_card(card)

    assert card == before
    assert rendered.startswith("# 单章概览卡｜c01\n")
    assert "- 章节版本：r2" in rendered
    assert f"- 章节正文 SHA256：{_revision_ref()['revision_text_sha256']}" in rendered
    assert "- 事实快照：facts@c01-r2-synthetic" in rendered
    assert card["source_summary"]["source_facts_sha256"] in rendered
    assert card["synopsis"] in rendered
    assert "钥匙进入场景并被注意。（事实：f001、f002）" in rendered
    assert "- [f003] 丙离开。" in rendered
    assert "- 已覆盖：3/3" in rendered
    evidence_ids = {item["fact_id"] for item in card["evidence"]}
    referenced_ids = {
        ref for beat in card["beats"] for ref in beat["fact_refs"]
    } | set(card["orphan_refs"])
    assert referenced_ids == evidence_ids
    for item in card["evidence"]:
        assert f"[{item['fact_id']}]" in rendered
        assert item["quote"] in rendered
    assert rendered.endswith("\n")


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda card: card["evidence"].pop(),
            "CARD_SOURCE_FACT_COUNT_MISMATCH",
        ),
        (
            lambda card: card["orphan_refs"].append("f001"),
            "CARD_FACT_REFS_DUPLICATE:f001",
        ),
        (
            lambda card: card["beats"][0]["fact_refs"].append("f999"),
            "CARD_FACT_REFS_UNKNOWN:f999",
        ),
        (
            lambda card: card["coverage"].update(covered_fact_count=2),
            "CARD_COVERAGE_MISMATCH",
        ),
        (
            lambda card: card["source_summary"].update(
                source_facts_sha256="not-a-sha"
            ),
            "CARD_SOURCE_FACTS_SHA256_INVALID",
        ),
        (
            lambda card: card.update(version="v1"),
            "CARD_IDENTITY_INVALID",
        ),
        (
            lambda card: card.pop("synopsis"),
            "CARD_SHAPE_INVALID",
        ),
    ],
)
def test_render_rejects_missing_duplicate_unclosed_or_damaged_card(
    mutate,
    reason: str,
) -> None:
    card = _card()
    mutate(card)

    with pytest.raises(overview.OverviewError, match=reason):
        overview.render_card(card)


def test_rendering_one_chapter_never_includes_another_chapter() -> None:
    card = overview.execute(
        _second_request(),
        _provider(_second_provider_result()),
    )

    rendered = overview.render_card(card)

    assert "单章概览卡｜c02" in rendered
    assert "f101" in rendered
    assert "丁推开窗户。" in rendered
    assert "c01" not in rendered
    assert "f001" not in rendered
    assert "甲拿起钥匙。" not in rendered


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda value: value["orphan_refs"].clear(),
            "UNCOVERED_FACT_REFS:f003",
        ),
        (
            lambda value: value["beats"][0]["fact_refs"].append("f999"),
            "UNKNOWN_FACT_REFS:f999",
        ),
        (
            lambda value: value["beats"].append(
                {
                    "text": "重复使用同一事实。",
                    "fact_refs": ["f001"],
                    "visual_hint": "",
                }
            ),
            "DUPLICATE_FACT_REFS:f001",
        ),
        (
            lambda value: value["orphan_refs"].append("f002"),
            "DUPLICATE_FACT_REFS:f002",
        ),
    ],
)
def test_provider_reference_partition_rejects_whole_batch(mutate, reason: str) -> None:
    provider_result = _provider_result()
    mutate(provider_result)

    with pytest.raises(overview.OverviewError, match=reason):
        overview.execute(_request(), _provider(provider_result))


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda request: request["facts"][0].update(
                chapter_revision_ref=_revision_ref(revision_no=1)
            ),
            "C4_STALE_REVISION:f001",
        ),
        (
            lambda request: request["facts"][0]["anchor_ref"].update(
                slice_sha256="0" * 64
            ),
            "C4_ANCHOR_QUOTE_INVALID:f001",
        ),
    ],
)
def test_old_revision_or_bad_anchor_is_rejected_before_provider(mutate, reason: str) -> None:
    request = _request()
    mutate(request)
    called = False

    def provider(_request: dict) -> dict:
        nonlocal called
        called = True
        return _provider_result()

    with pytest.raises(overview.OverviewError, match=reason):
        overview.execute(request, provider)
    assert called is False


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _offline_responses(*requests: dict) -> dict:
    results = (_provider_result(), _second_provider_result())
    return {
        overview.provider_key_for_request(request): result
        for request, result in zip(requests, results, strict=True)
    }


def test_batch_preserves_order_and_each_card_matches_single_execute() -> None:
    first = _request()
    second = _second_request()
    responses = _offline_responses(first, second)

    expected = [
        overview_tool.execute(first, overview_tool.offline_overview_provider(responses)),
        overview_tool.execute(second, overview_tool.offline_overview_provider(responses)),
    ]
    result = overview_tool.execute_batch(
        {"items": [first, second]},
        overview_tool.offline_overview_provider(responses),
    )

    assert result["transport"] == overview_tool.BATCH_TRANSPORT
    assert result["version"] == overview_tool.BATCH_TRANSPORT_VERSION
    assert [card["chapter_ref"] for card in result["cards"]] == ["c01", "c02"]
    assert _canonical_json_bytes(result["cards"]) == _canonical_json_bytes(expected)


@pytest.mark.parametrize(
    "batch_request",
    [
        {"items": []},
        _request(),
        {
            "items": [
                {
                    key: value
                    for key, value in _request().items()
                    if key != "generated_at"
                }
            ]
        },
        {"items": [_request(), {"items": [_second_request()]}]},
        {"items": [_request(), _request()]},
        {"items": [_request(), _second_request(chapter_id="c01", revision_no=3)]},
        {"items": [_request()], "facts": []},
    ],
)
def test_batch_structure_and_duplicate_failures_call_provider_zero_times(
    batch_request: dict,
) -> None:
    calls = 0

    def provider(_request: dict) -> dict:
        nonlocal calls
        calls += 1
        return _provider_result()

    with pytest.raises(overview.OverviewError):
        overview_tool.execute_batch(batch_request, provider)
    assert calls == 0


def test_cli_local_files_round_trip_can_be_reparsed_after_process_exit(tmp_path: Path) -> None:
    request = _request()
    input_path = tmp_path / "input.json"
    responses_path = tmp_path / "responses.json"
    output_path = tmp_path / "output.json"
    _write_json(input_path, request)
    _write_json(
        responses_path,
        {overview.provider_key_for_request(request): _provider_result()},
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(OVERVIEW_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--responses",
            str(responses_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    reparsed = json.loads(output_path.read_text(encoding="utf-8"))
    expected = overview_tool.execute(
        request,
        overview_tool.offline_overview_provider(
            {overview.provider_key_for_request(request): _provider_result()}
        ),
    )
    assert reparsed == expected
    assert reparsed["contract"] == "C5_OVERVIEW_CARD_PROTOTYPE"
    assert reparsed["source_summary"]["fact_count"] == 3


def test_cli_render_stdout_and_file_are_byte_stable_across_processes(
    tmp_path: Path,
) -> None:
    card_path = tmp_path / "card.json"
    output_path = tmp_path / "overview.md"
    _write_json(card_path, _card())
    command = [
        sys.executable,
        str(OVERVIEW_TOOL_SCRIPT),
        "--mode",
        "render",
        "--input",
        str(card_path),
    ]

    first = subprocess.run(command, check=False, capture_output=True)
    second = subprocess.run(command, check=False, capture_output=True)
    to_file = subprocess.run(
        [*command, "--output", str(output_path)],
        check=False,
        capture_output=True,
    )

    assert first.returncode == second.returncode == to_file.returncode == 0
    assert first.stderr == second.stderr == to_file.stderr == b""
    assert first.stdout == second.stdout == output_path.read_bytes()
    assert first.stdout.decode("utf-8").startswith("# 单章概览卡｜c01\n")


def test_cli_render_failure_keeps_old_output_and_leaves_no_tmp(tmp_path: Path) -> None:
    card = _card()
    card["version"] = "broken"
    card_path = tmp_path / "bad-card.json"
    output_path = tmp_path / "overview.md"
    _write_json(card_path, card)
    original = "作者正在使用的旧概览\n".encode()
    output_path.write_bytes(original)

    exit_code = overview_tool.main(
        [
            "--mode",
            "render",
            "--input",
            str(card_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 2
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(".overview.md.*.tmp")) == []


def test_cli_batch_output_is_stable_across_independent_processes(tmp_path: Path) -> None:
    first = _request()
    second = _second_request()
    input_path = tmp_path / "batch-input.json"
    responses_path = tmp_path / "responses.json"
    output_one = tmp_path / "batch-one.json"
    output_two = tmp_path / "batch-two.json"
    _write_json(input_path, {"items": [first, second]})
    _write_json(responses_path, _offline_responses(first, second))

    for output_path in (output_one, output_two):
        completed = subprocess.run(
            [
                sys.executable,
                str(OVERVIEW_TOOL_SCRIPT),
                "--mode",
                "batch",
                "--input",
                str(input_path),
                "--responses",
                str(responses_path),
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr

    assert output_one.read_bytes() == output_two.read_bytes()
    result = json.loads(output_one.read_text(encoding="utf-8"))
    assert [card["chapter_ref"] for card in result["cards"]] == ["c01", "c02"]


@pytest.mark.parametrize("bad_second", ["missing", "invalid"])
def test_cli_second_chapter_failure_keeps_old_output_and_leaves_no_tmp(
    tmp_path: Path,
    bad_second: str,
) -> None:
    first = _request()
    second = _second_request()
    responses = {
        overview.provider_key_for_request(first): _provider_result(),
    }
    if bad_second == "invalid":
        responses[overview.provider_key_for_request(second)] = {
            "synopsis": "缺少其余必填字段"
        }
    input_path = tmp_path / "batch-input.json"
    responses_path = tmp_path / "responses.json"
    output_path = tmp_path / "output.json"
    _write_json(input_path, {"items": [first, second]})
    _write_json(responses_path, responses)
    original = {"sentinel": "existing-good-batch"}
    _write_json(output_path, original)

    exit_code = overview_tool.main(
        [
            "--mode",
            "batch",
            "--input",
            str(input_path),
            "--responses",
            str(responses_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 2
    assert json.loads(output_path.read_text(encoding="utf-8")) == original
    assert list(tmp_path.glob(".output.json.*.tmp")) == []


def test_cli_failure_does_not_replace_existing_good_output(tmp_path: Path) -> None:
    request = _request()
    bad_result = _provider_result()
    bad_result["orphan_refs"] = []
    input_path = tmp_path / "input.json"
    responses_path = tmp_path / "responses.json"
    output_path = tmp_path / "output.json"
    _write_json(input_path, request)
    _write_json(
        responses_path,
        {overview.provider_key_for_request(request): bad_result},
    )
    original = {"sentinel": "existing-good-output"}
    _write_json(output_path, original)

    exit_code = overview_tool.main(
        [
            "--input",
            str(input_path),
            "--responses",
            str(responses_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 2
    assert json.loads(output_path.read_text(encoding="utf-8")) == original
    assert list(tmp_path.glob(".output.json.*.tmp")) == []

from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
SCHEMA_PATH = PRODUCT_ROOT / "contracts/C11_CHAPTER_REVISION_LEDGER.schema.json"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import extract, extract_tool
finally:
    sys.path.pop(0)


TEXTS = {
    "c01": "沈砚把青铜钥匙交给林乔。",
    "c02": "林乔把钥匙放进木匣，然后锁好内库。",
}


def _ref(chapter_id: str, *, revision_no: int = 2, text: str | None = None) -> dict:
    source = text if text is not None else TEXTS[chapter_id]
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": hashlib.sha256(source.encode()).hexdigest(),
    }


def _item(chapter_id: str, seg: int = 1) -> dict:
    text = TEXTS[chapter_id]
    return {
        "contract": "C2_SEGMENT",
        "version": "v1",
        "chapter_revision_ref": _ref(chapter_id),
        "seg": seg,
        "text": text,
        "start": 0,
        "end": len(text),
        "halo_before": "",
        "halo_after": "",
    }


def _request() -> dict:
    return {
        "items": [_item("c01"), _item("c02")],
        "current_chapter_revision_refs": [_ref("c01"), _ref("c02")],
    }


def _call_result(text: str, quote: str) -> dict:
    return {
        "data": {"facts": [{"text": text, "quote": quote}]},
        "usage": {},
        "model": "FROZEN_OFFLINE_RESPONSE",
    }


def _responses() -> dict:
    return {
        "c01:r2:s1": _call_result("沈砚把青铜钥匙交给林乔。", "沈砚把青铜钥匙交给林乔"),
        "c02:r2:s1": _call_result("林乔把钥匙放进木匣。", "林乔把钥匙放进木匣"),
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _assert_c3_schema(value: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(value)) == []


def test_local_files_turn_c2_batch_into_parseable_c3_batch_without_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "c2.json"
    responses_path = tmp_path / "responses.json"
    output_path = tmp_path / "c3.json"
    _write_json(input_path, _request())
    _write_json(responses_path, _responses())
    monkeypatch.setattr(
        extract.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API 不得调用")),
    )

    code = extract_tool.main(
        ["--input", str(input_path), "--responses", str(responses_path), "--output", str(output_path)]
    )

    assert code == 0
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(result["items"]) == 2
    assert [item["chapter_revision_ref"] for item in result["items"]] == [
        _ref("c01"),
        _ref("c02"),
    ]
    assert result == extract_tool.execute(
        _request(),
        extract_tool.offline_response_provider(_responses()),
    )
    assert all(_assert_c3_schema(item) is None for item in result["items"])
    assert not list(tmp_path.glob(".c3.json.*.tmp"))


def test_stdin_stdout_adapter_uses_same_object_core(tmp_path: Path) -> None:
    responses_path = tmp_path / "responses.json"
    _write_json(responses_path, _responses())
    stdout = io.StringIO()

    code = extract_tool.main(
        [
            "--input",
            "-",
            "--responses",
            str(responses_path),
            "--output",
            "-",
        ],
        stdin=io.StringIO(json.dumps(_request(), ensure_ascii=False)),
        stdout=stdout,
        stderr=io.StringIO(),
    )

    assert code == 0
    assert json.loads(stdout.getvalue()) == extract_tool.execute(
        _request(),
        extract_tool.offline_response_provider(_responses()),
    )


@pytest.mark.parametrize(
    ("collision", "reason"),
    [
        ("input", "OUTPUT_PATH_MUST_DIFFER_FROM_INPUT"),
        ("responses", "OUTPUT_PATH_MUST_DIFFER_FROM_RESPONSES"),
    ],
)
def test_output_cannot_replace_input_or_frozen_responses_before_any_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    collision: str,
    reason: str,
) -> None:
    input_path = tmp_path / "c2.json"
    responses_path = tmp_path / "responses.json"
    _write_json(input_path, _request())
    _write_json(responses_path, _responses())
    before_input = input_path.read_bytes()
    before_responses = responses_path.read_bytes()
    output_path = input_path if collision == "input" else responses_path
    read_calls: list[Path] = []
    real_read = extract_tool._read_json
    monkeypatch.setattr(
        extract_tool,
        "_read_json",
        lambda path: read_calls.append(path) or real_read(path),
    )
    stderr = io.StringIO()

    code = extract_tool.main(
        [
            "--input",
            str(input_path),
            "--responses",
            str(responses_path),
            "--output",
            str(output_path),
        ],
        stderr=stderr,
    )

    assert code == 2
    assert reason in stderr.getvalue()
    assert read_calls == []
    assert input_path.read_bytes() == before_input
    assert responses_path.read_bytes() == before_responses
    assert not list(tmp_path.glob(".*.tmp"))


def test_relative_input_and_absolute_output_resolve_to_same_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "c2.json"
    responses_path = tmp_path / "responses.json"
    _write_json(input_path, _request())
    _write_json(responses_path, _responses())
    before_input = input_path.read_bytes()
    monkeypatch.chdir(tmp_path)
    stderr = io.StringIO()

    code = extract_tool.main(
        [
            "--input",
            "c2.json",
            "--responses",
            str(responses_path),
            "--output",
            str(input_path),
        ],
        stderr=stderr,
    )

    assert code == 2
    assert "OUTPUT_PATH_MUST_DIFFER_FROM_INPUT" in stderr.getvalue()
    assert input_path.read_bytes() == before_input
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("alias_kind", ["symlink", "hardlink"])
def test_output_file_alias_of_input_is_rejected_without_touching_source(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    input_path = tmp_path / "c2.json"
    responses_path = tmp_path / "responses.json"
    output_alias = tmp_path / f"c2-{alias_kind}-alias.json"
    _write_json(input_path, _request())
    _write_json(responses_path, _responses())
    if alias_kind == "symlink":
        output_alias.symlink_to(input_path)
    else:
        output_alias.hardlink_to(input_path)
    before_input = input_path.read_bytes()
    stderr = io.StringIO()

    code = extract_tool.main(
        [
            "--input",
            str(input_path),
            "--responses",
            str(responses_path),
            "--output",
            str(output_alias),
        ],
        stderr=stderr,
    )

    assert code == 2
    assert "OUTPUT_PATH_MUST_DIFFER_FROM_INPUT" in stderr.getvalue()
    assert input_path.read_bytes() == before_input
    assert output_alias.read_bytes() == before_input
    assert not list(tmp_path.glob(".*.tmp"))


def test_provider_missing_item_rejects_whole_batch() -> None:
    responses = _responses()
    del responses["c02:r2:s1"]

    with pytest.raises(extract_tool.ExtractToolError, match="OFFLINE_RESPONSE_MISSING:c02:r2:s1"):
        extract_tool.execute(_request(), extract_tool.offline_response_provider(responses))


def test_stale_revision_is_rejected_before_provider_is_called() -> None:
    request = _request()
    request["current_chapter_revision_refs"][0] = _ref(
        "c01",
        revision_no=3,
        text=TEXTS["c01"] + "修订。",
    )
    calls: list[dict] = []

    with pytest.raises(extract.C2V1ContractError, match="C2_REVISION_REF_STALE_OR_MISMATCH"):
        extract_tool.execute(request, lambda provider_request: calls.append(provider_request) or {})

    assert calls == []


def test_malformed_revision_ref_rejects_whole_batch() -> None:
    request = _request()
    request["items"][0]["chapter_revision_ref"]["revision_text_sha256"] = "bad-sha"

    with pytest.raises(
        extract.C2V1ContractError,
        match="C2_V1_BAD_REVISION_REF:revision_text_sha256",
    ):
        extract_tool.execute(request, extract_tool.offline_response_provider(_responses()))


def test_bad_quote_rejects_whole_batch() -> None:
    responses = _responses()
    responses["c02:r2:s1"] = _call_result("林乔把钥匙放进木匣。", "原文里不存在的句子")

    with pytest.raises(
        extract_tool.ExtractToolError,
        match="C3_QUOTE_NOT_IN_RESPONSIBILITY_SEGMENT:c02:r2:s1",
    ):
        extract_tool.execute(_request(), extract_tool.offline_response_provider(responses))


@pytest.mark.parametrize("mutation", ["missing_quote", "extra_field"])
def test_provider_fields_are_not_repaired_or_silently_dropped(mutation: str) -> None:
    responses = _responses()
    fact = responses["c01:r2:s1"]["data"]["facts"][0]
    if mutation == "missing_quote":
        del fact["quote"]
    else:
        fact["confidence"] = 0.99

    with pytest.raises(
        extract_tool.ExtractToolError,
        match="PROVIDER_FACT_SHAPE_INVALID:c01:r2:s1:1",
    ):
        extract_tool.execute(_request(), extract_tool.offline_response_provider(responses))


def test_failed_run_does_not_overwrite_existing_output(tmp_path: Path) -> None:
    input_path = tmp_path / "c2.json"
    responses_path = tmp_path / "responses.json"
    output_path = tmp_path / "c3.json"
    _write_json(input_path, _request())
    _write_json(responses_path, _responses())
    assert extract_tool.main(
        ["--input", str(input_path), "--responses", str(responses_path), "--output", str(output_path)]
    ) == 0
    before = output_path.read_bytes()

    broken = copy.deepcopy(_responses())
    del broken["c02:r2:s1"]
    _write_json(responses_path, broken)
    stderr = io.StringIO()
    code = extract_tool.main(
        ["--input", str(input_path), "--responses", str(responses_path), "--output", str(output_path)],
        stderr=stderr,
    )

    assert code == 2
    assert "OFFLINE_RESPONSE_MISSING:c02:r2:s1" in stderr.getvalue()
    assert output_path.read_bytes() == before
    assert not list(tmp_path.glob(".c3.json.*.tmp"))

from __future__ import annotations

import copy
import hashlib
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
    from mvp import extract
finally:
    sys.path.pop(0)


TEXT = "沈砚把青铜钥匙交给林乔，并让她在天黑前锁好内库。"
QUOTE = "沈砚把青铜钥匙交给林乔"
FACT_ONE = {"text": "沈砚把青铜钥匙交给林乔。", "quote": QUOTE}
FACT_TWO = {"text": "沈砚让林乔在天黑前锁好内库。", "quote": "并让她在天黑前锁好内库"}


def _legal_facts() -> list[dict]:
    return [dict(FACT_ONE), dict(FACT_TWO)]


def _call_result(
    *,
    facts: list[dict] | None = None,
    data: object | None = None,
    usage: object = None,
    model: object = "FROZEN_SYNTHETIC_RESPONSE",
    extra: dict | None = None,
    omit: frozenset[str] | None = None,
) -> dict:
    if data is None:
        data = {"facts": _legal_facts() if facts is None else facts}
    payload: dict = {
        "data": data,
        "usage": {"input_tokens": 0, "output_tokens": 0} if usage is None else usage,
        "model": model,
    }
    if extra:
        payload.update(extra)
    if omit:
        for key in omit:
            payload.pop(key, None)
    return payload


def _revision_ref(*, revision_no: int = 2, text: str = TEXT) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def _c2_v1() -> dict:
    return {
        "contract": "C2_SEGMENT",
        "version": "v1",
        "chapter_revision_ref": _revision_ref(),
        "seg": 1,
        "text": TEXT,
        "start": 120,
        "end": 120 + len(TEXT),
        "halo_before": "前一段只交代两人进入库房。",
        "halo_after": "后一段写林乔检查门闩。",
    }


def _frozen_provider(calls: list[dict]):
    def provide(instructions: str, user_content: str, cfg: dict) -> dict:
        calls.append(
            {
                "instructions": instructions,
                "user_content": user_content,
                "cfg": copy.deepcopy(cfg),
            }
        )
        return _call_result()

    return provide


def _assert_formal_schema_accepts(value: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(value))
    assert errors == []


def test_legal_c2_v1_uses_existing_prompt_and_parser_then_emits_c3_v1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seg = _c2_v1()
    calls: list[dict] = []

    def forbidden_api(*args, **kwargs):
        raise AssertionError("零 API 例子不得调 subprocess")

    monkeypatch.setattr(extract.subprocess, "run", forbidden_api)
    candidates = extract.extract_segment(
        seg,
        {"model_id": "NO_API_FIXTURE"},
        current_chapter_revision_ref=_revision_ref(),
        response_provider=_frozen_provider(calls),
    )

    assert len(calls) == 1
    assert calls[0]["instructions"] == extract.INSTRUCTIONS
    assert "【责任段】\n" + TEXT in calls[0]["user_content"]
    assert "【前文背景·只读】" in calls[0]["user_content"]
    assert "【后文背景·只读】" in calls[0]["user_content"]
    assert candidates == [
        {
            "contract": "C3_FACT_CANDIDATE",
            "version": "v1",
            "chapter_revision_ref": _revision_ref(),
            "text": FACT_ONE["text"],
            "quote": FACT_ONE["quote"],
            "seg": 1,
        },
        {
            "contract": "C3_FACT_CANDIDATE",
            "version": "v1",
            "chapter_revision_ref": _revision_ref(),
            "text": FACT_TWO["text"],
            "quote": FACT_TWO["quote"],
            "seg": 1,
        },
    ]
    assert candidates[0]["chapter_revision_ref"] is not seg["chapter_revision_ref"]
    _assert_formal_schema_accepts(candidates[0])
    _assert_formal_schema_accepts(candidates[1])


def test_stale_c2_revision_ref_is_rejected_before_response_is_consumed() -> None:
    calls: list[dict] = []
    current = _revision_ref(revision_no=3, text=TEXT + "修订。")

    with pytest.raises(extract.C2V1ContractError, match="C2_REVISION_REF_STALE_OR_MISMATCH"):
        extract.extract_segment(
            _c2_v1(),
            {"model_id": "NO_API_FIXTURE"},
            current_chapter_revision_ref=current,
            response_provider=_frozen_provider(calls),
        )

    assert calls == []


def test_c2_v1_with_missing_field_is_rejected() -> None:
    seg = _c2_v1()
    del seg["chapter_revision_ref"]

    with pytest.raises(
        extract.C2V1ContractError,
        match="C2_V1_MISSING_FIELDS:chapter_revision_ref",
    ):
        extract.extract_segment(
            seg,
            {"model_id": "NO_API_FIXTURE"},
            current_chapter_revision_ref=_revision_ref(),
            response_provider=lambda *_: {},
        )


def test_c2_v1_with_extra_field_is_rejected() -> None:
    seg = _c2_v1()
    seg["chapter_title"] = "第一章"

    with pytest.raises(extract.C2V1ContractError, match="C2_V1_EXTRA_FIELDS:chapter_title"):
        extract.extract_segment(
            seg,
            {"model_id": "NO_API_FIXTURE"},
            current_chapter_revision_ref=_revision_ref(),
            response_provider=lambda *_: {},
        )


def test_c2_v1_with_bad_revision_ref_is_rejected() -> None:
    seg = _c2_v1()
    seg["chapter_revision_ref"]["revision_text_sha256"] = "not-a-sha"

    with pytest.raises(
        extract.C2V1ContractError,
        match="C2_V1_BAD_REVISION_REF:revision_text_sha256",
    ):
        extract.extract_segment(
            seg,
            {"model_id": "NO_API_FIXTURE"},
            current_chapter_revision_ref=_revision_ref(),
            response_provider=lambda *_: {},
        )


def test_parse_fact_call_result_keeps_legal_dual_facts_in_input_order() -> None:
    parsed = extract.parse_fact_call_result(_call_result())
    assert parsed["facts"] == _legal_facts()
    assert parsed["facts"][0] is not FACT_ONE
    assert parsed["model"] == "FROZEN_SYNTHETIC_RESPONSE"
    assert parsed["usage"] == {"input_tokens": 0, "output_tokens": 0}


def test_parse_fact_call_result_allows_empty_facts() -> None:
    parsed = extract.parse_fact_call_result(_call_result(facts=[]))
    assert parsed == {
        "facts": [],
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "model": "FROZEN_SYNTHETIC_RESPONSE",
    }


def test_parse_fact_call_result_allows_empty_quote() -> None:
    parsed = extract.parse_fact_call_result(
        _call_result(facts=[{"text": FACT_ONE["text"], "quote": ""}])
    )
    assert parsed["facts"] == [{"text": FACT_ONE["text"], "quote": ""}]


def test_extract_segment_emits_no_candidates_for_legal_empty_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        extract.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("零 API 例子不得调 subprocess")),
    )
    candidates = extract.extract_segment(
        _c2_v1(),
        {"model_id": "NO_API_FIXTURE"},
        current_chapter_revision_ref=_revision_ref(),
        response_provider=lambda *_: _call_result(facts=[]),
    )
    assert candidates == []


def test_extract_segment_rejects_whole_batch_when_second_fact_is_bad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        extract.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("零 API 例子不得调 subprocess")),
    )
    with pytest.raises(RuntimeError, match="第 2 条 text 不合法"):
        extract.extract_segment(
            _c2_v1(),
            {"model_id": "NO_API_FIXTURE"},
            current_chapter_revision_ref=_revision_ref(),
            response_provider=lambda *_: _call_result(
                facts=[dict(FACT_ONE), {"text": "", "quote": QUOTE}]
            ),
        )


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (_call_result(data={}), "data 形状不合法"),
        (_call_result(data={"facts": [], "note": "extra"}), "data 形状不合法"),
        (_call_result(extra={"note": "extra"}), "多了字段：note"),
        (_call_result(facts=["不是对象"]), "第 1 条事实形状不合法"),
        (_call_result(facts=[{"text": FACT_ONE["text"]}]), "第 1 条事实形状不合法"),
        (
            _call_result(
                facts=[{"text": FACT_ONE["text"], "quote": QUOTE, "note": "extra"}]
            ),
            "第 1 条事实形状不合法",
        ),
        (_call_result(facts=[{"text": "", "quote": QUOTE}]), "第 1 条 text 不合法"),
        (
            _call_result(facts=[{"text": f" {FACT_ONE['text']}", "quote": QUOTE}]),
            "第 1 条 text 不合法",
        ),
        (
            _call_result(facts=[{"text": FACT_ONE["text"], "quote": f" {QUOTE} "}]),
            "第 1 条 quote 不合法",
        ),
        (
            _call_result(facts=[{"text": FACT_ONE["text"], "quote": 1}]),
            "第 1 条 quote 不合法",
        ),
        (_call_result(usage="bad"), "usage/model 形状不合法"),
        (_call_result(model=None), "usage/model 形状不合法"),
        (_call_result(omit=frozenset({"data"})), "缺少字段：data"),
        (_call_result(omit=frozenset({"usage"})), "缺少字段：usage"),
        (_call_result(data={"facts": {"text": FACT_ONE["text"]}}), "facts 不是数组"),
    ],
)
def test_parse_fact_call_result_rejects_bad_payloads(payload: object, match: str) -> None:
    with pytest.raises(RuntimeError, match=match):
        extract.parse_fact_call_result(payload)

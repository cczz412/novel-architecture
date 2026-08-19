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
        return {
            "data": {
                "facts": [
                    {
                        "text": "  沈砚把青铜钥匙交给林乔。 ",
                        "quote": f" {QUOTE} ",
                    },
                    {"text": "   ", "quote": "不应进入候选"},
                ]
            },
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "model": "FROZEN_SYNTHETIC_RESPONSE",
        }

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
            "text": "沈砚把青铜钥匙交给林乔。",
            "quote": QUOTE,
            "seg": 1,
        }
    ]
    assert candidates[0]["chapter_revision_ref"] is not seg["chapter_revision_ref"]
    _assert_formal_schema_accepts(candidates[0])


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

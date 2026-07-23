from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
MODULE_PATH = (
    ROOT
    / "experiments/Z91_crossbook_v2_20260723/z91_crossbook_exam_v2_run.py"
)
SPEC = importlib.util.spec_from_file_location("z91_crossbook_exam_v2_run", MODULE_PATH)
assert SPEC and SPEC.loader
z91 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = z91
SPEC.loader.exec_module(z91)

from zbatch_modules import neutral_extract  # noqa: E402
from zbatch_modules.errors import ZBatchError  # noqa: E402
from zbatch_modules.z83_retry_transport import RetryPolicy  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict):
        self.raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.status = 200
        self.headers = {"Content-Type": "application/json", "x-request-id": "v2-test"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.raw


ZERO_WAIT = RetryPolicy(
    same_chapter_gap_seconds=0.0,
    cross_chapter_gap_seconds=0.0,
    retry_delays_seconds=(0.0, 0.0),
    max_429_retries_per_request=2,
    max_429_per_run=5,
    max_retry_after_seconds=300.0,
)


def catalog_online(request, timeout):
    assert request.get_method() == "GET"
    return FakeResponse({"data": [{"id": z91.v1.PRO_MODEL, "status": "online"}]})


def response_payload(
    sample: dict,
    *,
    event_text: str = "这是一条满足共享最小长度的事件摘要。",
    extra_event_field: bool = False,
) -> dict:
    chapter = int(sample["chapter"])
    event = {
        "event_id": f"EV-C{chapter:04d}-01",
        "event": event_text,
        "anchors": [{"anchor_id": "E0001"}],
    }
    if extra_event_field:
        event["classification"] = "越权"
    body = {
        "schema_version": "z-event-v1",
        "chapter": chapter,
        "events": [event],
    }
    return {
        "id": f"test-{sample['sample_id']}",
        "model": sample["model"],
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "reasoning_content": "测试思考内容",
                    "content": json.dumps(body, ensure_ascii=False),
                },
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


def authorize(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSENOVA_API_KEY", "flash-v2-test-key")
    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "pro-v2-test-key")


def test_subject_predicate_parser_is_narrow_and_deterministic() -> None:
    assert z91.parse_complete_subject_predicate("齐夏点头。") == {
        "subject": "齐夏",
        "subject_allowlist_scope": "contract_union_for_test",
        "predicate": "点头",
        "predicate_modifier": "",
        "predicate_head": "点头",
        "predicate_tail": "",
        "terminal_punctuation": "。",
    }
    assert z91.parse_complete_subject_predicate("甜甜醒了")["subject"] == "甜甜"
    assert z91.parse_complete_subject_predicate("他问她。")["predicate_head"] == "问"
    assert z91.parse_complete_subject_predicate("点头。") is None
    assert z91.parse_complete_subject_predicate("很紧张。") is None
    assert z91.parse_complete_subject_predicate("此时醒了") is None
    assert z91.parse_complete_subject_predicate("齐夏有") is None
    assert z91.parse_complete_subject_predicate("事情是") is None
    assert z91.parse_complete_subject_predicate("真相真") is None
    assert z91.parse_complete_subject_predicate("齐夏有枪")["predicate"] == "有枪"
    assert z91.parse_complete_subject_predicate("他问她。")["predicate"] == "问她"
    assert z91.parse_complete_subject_predicate("齐夏离开") == {
        "subject": "齐夏",
        "subject_allowlist_scope": "contract_union_for_test",
        "predicate": "离开",
        "predicate_modifier": "",
        "predicate_head": "离开",
        "predicate_tail": "",
        "terminal_punctuation": "",
    }
    assert z91.parse_complete_subject_predicate("此时离开") is None
    assert z91.parse_complete_subject_predicate("随后打开") is None
    assert z91.parse_complete_subject_predicate("突然回来") is None
    assert z91.parse_complete_subject_predicate("于是离开") is None
    assert z91.parse_complete_subject_predicate("然后打开") is None
    assert z91.parse_complete_subject_predicate("忽然醒了") is None
    assert z91.parse_complete_subject_predicate("马上走了") is None
    assert z91.parse_complete_subject_predicate("接着离开") is None
    assert z91.parse_complete_subject_predicate("微笑离开") is None
    assert z91.parse_complete_subject_predicate("转身离开") is None
    assert z91.parse_complete_subject_predicate("开门离开") is None
    assert z91.parse_complete_subject_predicate("起身离开") is None
    assert z91.parse_complete_subject_predicate("低头沉默") is None
    assert z91.parse_complete_subject_predicate("天亮")["subject"] == "天"
    assert z91.parse_complete_subject_predicate("灯灭")["predicate_head"] == "灭"
    assert z91.parse_complete_subject_predicate("她赢")["predicate_head"] == "赢"
    assert z91.parse_complete_subject_predicate("他睡")["predicate_head"] == "睡"
    assert z91.parse_complete_subject_predicate("他飞")["predicate_head"] == "飞"
    assert (
        z91.parse_complete_subject_predicate("余列点头", case_key="X02-C0031")
        is None
    )
    assert z91.parse_complete_subject_predicate(
        "余列点头", case_key="X04-C0046"
    )["subject_allowlist_scope"] == "X04-C0046"


def test_shared_six_char_contract_remains_unchanged() -> None:
    catalog = [{"anchor_id": "E0001", "quote": "齐夏点了点头。"}]
    data = {
        "schema_version": "z-event-v1",
        "chapter": 31,
        "events": [
            {
                "event_id": "EV-C0031-01",
                "event": "齐夏点头。",
                "anchors": [{"anchor_id": "E0001"}],
            }
        ],
    }
    reasons, _ = neutral_extract.audit_event_envelope(data, 31, catalog)
    assert reasons == ["EV-C0031-01事件摘要长度非法"]


def test_prepare_freezes_new_contract_rubric_and_new_logical_ids(tmp_path: Path) -> None:
    original_specs = z91.v1.sample_specs
    run_dir = tmp_path / "v2"
    result = z91.prepare(run_dir)

    assert result["status"] == "pass_zero_call_prepared"
    assert result["model_api_calls"] == 0
    assert result["rubric_v1_3_sha256"] == z91.sha256_file(z91.RUBRIC_PATH)
    assert result["short_summary_contract_sha256"] == z91.sha256_file(z91.CONTRACT_PATH)
    plan = z91.read_json(run_dir / "prepared/run_plan.json")
    assert all(row["logical_request_id"].startswith("Z91V2-") for row in plan["samples"])
    assert (run_dir / "prepared/contracts/short_summary_exception_v1.json").read_bytes() == z91.CONTRACT_PATH.read_bytes()
    assert z91.sha256_file(run_dir / "review/source_facts/source_fact_seal.json") == "b191b0d6174040613c2593671af834e21d899b3b02b63b60495a20ea17828279"
    assert z91.v1.sample_specs is original_specs
    z91.verify_prepared(run_dir)


def test_six_fresh_samples_pass_and_short_sentence_is_side_ledger_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "v2_success"
    z91.prepare(run_dir)
    authorize(monkeypatch)
    samples = z91.sample_specs_v2()
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        sample = samples[calls]
        calls += 1
        text = "齐夏点头。" if calls == 2 else "这是一条满足共享最小长度的事件摘要。"
        return FakeResponse(response_payload(sample, event_text=text))

    result = z91.run(
        run_dir,
        opener=opener,
        catalog_opener=catalog_online,
        policy=ZERO_WAIT,
        sleeper=lambda _: None,
        jitter=lambda: 0.0,
    )

    assert calls == 6
    assert result["logical_samples"] == 6
    assert result["short_summary_violation_count"] == 1
    short_root = run_dir / "samples/X02-C0031__pro_primary_tencent"
    mechanical = z91.read_json(short_root / "mechanical.json")
    assert mechanical["shared_six_char_gate"] is False
    assert mechanical["z91_v2_exception_gate"] is True
    assert mechanical["effective_gate"] is True
    ledger = z91.read_json(short_root / z91.LEDGER_RELATIVE)
    assert ledger["exception_count"] == 1
    assert ledger["entries"][0]["subject"] == "齐夏"
    assert z91.audit(run_dir)["logical_samples"] == 6


@pytest.mark.parametrize(
    ("event_text", "extra"),
    [
        ("点头。", False),
        ("很紧张。", False),
        ("长" * 101, False),
        ("齐夏点头。", True),
    ],
)
def test_non_qualified_or_other_failure_hard_stops_without_next_sample(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    event_text: str,
    extra: bool,
) -> None:
    run_dir = tmp_path / f"v2_fail_{len(event_text)}_{int(extra)}"
    z91.prepare(run_dir)
    authorize(monkeypatch)
    first = z91.sample_specs_v2()[0]
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(
            response_payload(first, event_text=event_text, extra_event_field=extra)
        )

    with pytest.raises(z91.v1.Z91RunHardStop):
        z91.run(
            run_dir,
            opener=opener,
            catalog_opener=catalog_online,
            policy=ZERO_WAIT,
            sleeper=lambda _: None,
            jitter=lambda: 0.0,
        )
    assert calls == 1


def test_side_ledger_tamper_breaks_raw_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "v2_tamper"
    z91.prepare(run_dir)
    authorize(monkeypatch)
    samples = z91.sample_specs_v2()
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        sample = samples[calls]
        calls += 1
        text = "甜甜醒了" if calls == 1 else "这是一条满足共享最小长度的事件摘要。"
        return FakeResponse(response_payload(sample, event_text=text))

    z91.run(
        run_dir,
        opener=opener,
        catalog_opener=catalog_online,
        policy=ZERO_WAIT,
        sleeper=lambda _: None,
        jitter=lambda: 0.0,
    )
    ledger_path = (
        run_dir
        / "samples/X02-C0031__flash_sensenova"
        / z91.LEDGER_RELATIVE
    )
    ledger = z91.read_json(ledger_path)
    ledger["entries"][0]["subject"] = "篡改"
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ZBatchError, match="旁账|重建"):
        z91.audit(run_dir)

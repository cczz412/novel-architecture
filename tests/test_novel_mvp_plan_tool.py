from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
PLAN_TOOL_SCRIPT = PRODUCT_ROOT / "mvp" / "plan_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import factstore, plan_tool
finally:
    sys.path.pop(0)


CHAPTER_TEXT = "林乔收起钥匙，没有告诉周宁来历。"
QUOTE = "林乔收起钥匙"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_ref(revision_no: int = 2, text: str = CHAPTER_TEXT) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": _sha256(text),
    }


def _fact(
    fact_id: str,
    *,
    status: str = "confirmed",
    revision_ref: dict | None = None,
    quote: str = QUOTE,
    slice_sha256: str | None = None,
) -> dict:
    ref = copy.deepcopy(revision_ref or _revision_ref())
    start = CHAPTER_TEXT.index(QUOTE) if ref == _revision_ref() else 0
    recheck = None
    if status == "needs_recheck":
        recheck = {
            "previous_status": "confirmed",
            "reason": "evidence_gone",
            "from_revision_no": 1,
            "target_revision_no": ref["revision_no"],
            "flagged_at": "2026-08-19 10:05:00",
        }
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": "c01",
        "text": "林乔收起了钥匙。",
        "quote": quote,
        "status": status,
        "source": "SYNTHETIC_C4_V1",
        "note": "",
        "added_at": "2026-08-19 10:00:00",
        "seg": 1,
        "chapter_revision_ref": ref,
        "anchor_ref": {
            **ref,
            "coordinate_basis": factstore.ANCHOR_COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": slice_sha256 or _sha256(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": recheck,
    }


def _request(*, mode: str = "forward") -> dict:
    return {
        "project": "合成测试书",
        "generated_at": "2026-08-19 11:00:00",
        "purpose": "让周宁发现钥匙来历有问题",
        "purpose_note": "这一章只发现疑点，不揭晓来源",
        "mode": mode,
        "chapter_intent": "钥匙来源继续保密",
        "current_chapter_revision_ref": _revision_ref(),
        "facts": [
            _fact("f001"),
            _fact("f002", revision_ref=_revision_ref(1, "旧稿"), quote="旧稿"),
            _fact("f003", status="extracted"),
            _fact("f004", status="rejected"),
            _fact("f005", status="needs_recheck"),
            _fact("f006", slice_sha256="0" * 64),
        ],
        "planning_card_ref": "AC-0007",
        "planning_card_rev": 3,
    }


def _card(
    *,
    card_id: str = "card01",
    role: str = "attach",
    planning_card_ref: str = "AC-0007",
    planning_card_rev: int = 3,
) -> dict:
    return {
        "id": card_id,
        "role": role,
        "title": "钥匙来历出现疑点",
        "purpose_note": "只把疑点摆到台面，不公布答案",
        "options": [
            {
                "id": "A",
                "label": "让周宁从磨损痕迹发现异常",
                "reveal_intent": "只透露钥匙曾被反复使用",
            },
            {
                "id": "C",
                "label": "让第三人无意说漏半句",
                "reveal_intent": "只透露钥匙不是第一次出现",
            },
            {
                "id": "B",
                "label": "让旧锁对钥匙产生异常反应",
                "reveal_intent": "只透露钥匙与旧锁有关",
            },
        ],
        "recommended_option_ref": "B",
        "planning_card_ref": planning_card_ref,
        "planning_card_rev": planning_card_rev,
        "guidance": {
            "card_problem": "让周宁拿到足够明确、但不会泄底的疑点",
            "dialogue_reveal": "只说钥匙不普通，不解释来源",
            "plugin_craft": "",
        },
    }


def _conflict(fact_id: str = "f001") -> dict:
    return {
        "kind": "fact",
        "fact_id": fact_id,
        "fact_text": "林乔收起了钥匙。",
        "why": "现有事实说明钥匙在林乔手里，不能让周宁凭空直接持有",
        "ask": "改目的，还是改已确认事实？",
    }


def _provider_result(*, cards: list[dict] | None = None) -> dict:
    return {
        "data": {
            "cards": copy.deepcopy(cards if cards is not None else [_card()]),
            "conflicts": [_conflict()],
        },
        "usage": {"api_calls": 0, "model_calls": 0, "retries": 0},
        "model": "FROZEN_OFFLINE_PLANNING_FIXTURE",
    }


class _CapturingProvider:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.requests: list[dict] = []

    def __call__(self, request: dict) -> dict:
        self.requests.append(copy.deepcopy(request))
        return copy.deepcopy(self.response)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_execute_emits_strict_c7_and_provider_only_sees_current_confirmed_facts() -> None:
    request = _request()
    provider = _CapturingProvider(_provider_result())

    result = plan_tool.execute(request, provider)

    assert plan_tool.validate_c7_v1(result) == result
    assert result["contract"] == "C7_PLOT_LAYER v1"
    assert result["confirmed_fact_ids"] == ["f001"]
    assert result["purpose_placement"] == "attach"
    assert result["cards"][0]["recommended_option_ref"] == "B"
    assert result["cards"][0]["options"][0]["id"] == "A"
    assert result["cards"][0]["planning_card_ref"] == "AC-0007"
    assert result["cards"][0]["planning_card_rev"] == 3
    assert not ({"facts", "plan", "actual", "selection"} & set(result))

    assert len(provider.requests) == 1
    provider_request = provider.requests[0]
    assert provider_request["planning_context"]["confirmed_facts"] == [
        request["facts"][0]
    ]
    assert provider_request["fact_filter_receipt"] == {
        "input_count": 6,
        "included_count": 1,
        "excluded_count": 5,
        "excluded_by_reason": {
            "stale_revision": 1,
            "extracted": 1,
            "rejected": 1,
            "needs_recheck": 1,
            "invalid_anchor": 1,
        },
    }
    provider_bytes = json.dumps(provider_request, ensure_ascii=False)
    assert all(f'"f00{number}"' not in provider_bytes for number in range(2, 7))
    assert request == _request()


def test_reverse_mode_requires_a_valid_prerequisite_card_first() -> None:
    request = _request(mode="reverse")
    response = _provider_result(
        cards=[
            _card(card_id="card01", role="prerequisite"),
            _card(card_id="card02", role="attach"),
        ]
    )

    result = plan_tool.execute(request, _CapturingProvider(response))

    assert [card["role"] for card in result["cards"]] == [
        "prerequisite",
        "attach",
    ]

    bad = _provider_result(cards=[_card(role="attach")])
    with pytest.raises(
        plan_tool.PlanToolError, match="REVERSE_PREREQUISITE_MUST_BE_FIRST"
    ):
        plan_tool.execute(request, _CapturingProvider(bad))


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda value: value.pop("model"), "MISSING_FIELDS"),
        (lambda value: value.update(extra="x"), "EXTRA_FIELDS"),
        (
            lambda value: value["data"]["cards"][0].update(extra="x"),
            "EXTRA_FIELDS",
        ),
        (
            lambda value: value["data"]["cards"][0].update(id="scene01"),
            "LOCAL_CARD_ID_INVALID",
        ),
        (
            lambda value: value["data"]["cards"].append(
                copy.deepcopy(value["data"]["cards"][0])
            ),
            "LOCAL_CARD_ID_DUPLICATE",
        ),
        (
            lambda value: value["data"]["cards"][0].update(
                recommended_option_ref="Z"
            ),
            "RECOMMENDED_OPTION_NOT_FOUND",
        ),
        (
            lambda value: value["data"]["cards"][0].update(
                planning_card_ref="AC-9999"
            ),
            "PLANNING_CARD_REF_DRIFT",
        ),
        (
            lambda value: value["data"]["cards"][0].update(planning_card_rev=4),
            "PLANNING_CARD_REV_DRIFT",
        ),
        (
            lambda value: value["data"]["conflicts"][0].update(fact_id="f002"),
            "CONFLICT_FACT_NOT_IN_CURRENT_CONTEXT",
        ),
        (
            lambda value: value["usage"].update(model_calls=1),
            "OFFLINE_USAGE_MUST_BE_ZERO",
        ),
    ],
)
def test_bad_frozen_response_rejects_the_whole_batch_without_repair(
    mutate, error: str
) -> None:
    response = _provider_result()
    mutate(response)

    with pytest.raises(plan_tool.PlanToolError, match=error):
        plan_tool.execute(_request(), _CapturingProvider(response))


def test_request_never_allocates_or_guesses_a_planning_card_reference() -> None:
    request = _request()
    request["planning_card_ref"] = "card01"
    provider = _CapturingProvider(_provider_result())

    with pytest.raises(plan_tool.PlanToolError, match="PLANNING_CARD_REF_INVALID"):
        plan_tool.execute(request, provider)

    assert provider.requests == []


def test_cli_is_local_only_atomic_and_byte_stable_across_processes(
    tmp_path: Path,
) -> None:
    request = _request()
    response = _provider_result()
    responses = {plan_tool.planning_provider_key(request): response}
    input_path = tmp_path / "input.json"
    responses_path = tmp_path / "responses.json"
    output_one = tmp_path / "c7-one.json"
    output_two = tmp_path / "c7-two.json"
    _write_json(input_path, request)
    _write_json(responses_path, responses)

    command = [
        sys.executable,
        str(PLAN_TOOL_SCRIPT),
        "--input",
        str(input_path),
        "--responses",
        str(responses_path),
        "--output",
    ]
    first = subprocess.run(
        [*command, str(output_one)],
        check=False,
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        [*command, str(output_two)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert first.returncode == second.returncode == 0
    assert first.stderr == second.stderr == ""
    assert output_one.read_bytes() == output_two.read_bytes()
    assert (
        plan_tool.validate_c7_v1(json.loads(output_one.read_bytes()))["contract"]
        == "C7_PLOT_LAYER v1"
    )
    assert not list(tmp_path.glob(".c7-*.json.*.tmp"))


def test_cli_failure_does_not_overwrite_existing_output(tmp_path: Path) -> None:
    request = _request()
    input_path = tmp_path / "input.json"
    responses_path = tmp_path / "responses.json"
    output_path = tmp_path / "c7.json"
    _write_json(input_path, request)
    _write_json(responses_path, {})
    output_path.write_bytes(b"existing-output\n")

    code = plan_tool.main(
        [
            "--input",
            str(input_path),
            "--responses",
            str(responses_path),
            "--output",
            str(output_path),
        ]
    )

    assert code == 2
    assert output_path.read_bytes() == b"existing-output\n"
    assert not list(tmp_path.glob(".c7.json.*.tmp"))


def test_render_forward_card_shows_all_author_visible_fields_without_selection() -> None:
    result = plan_tool.execute(_request(), _CapturingProvider(_provider_result()))

    rendered = plan_tool.render_c7_v1(result)

    assert "目的：让周宁发现钥匙来历有问题" in rendered
    assert "目的说明：这一章只发现疑点，不揭晓来源" in rendered
    assert "规划模式：forward（顺向）" in rendered
    assert "章节意图：钥匙来源继续保密" in rendered
    assert "确认事实 ID：f001" in rendered
    assert "provider 身份：FROZEN_OFFLINE_PLANNING_FIXTURE" in rendered
    assert "钥匙来历出现疑点（card01）" in rendered
    assert "角色：attach（附加卡）" in rendered
    assert "规划卡版本：AC-0007 / rev 3" in rendered
    assert "卡片问题：让周宁拿到足够明确、但不会泄底的疑点" in rendered
    assert "- A：让周宁从磨损痕迹发现异常" in rendered
    assert "- B：让旧锁对钥匙产生异常反应 [推荐参考；作者尚未选择]" in rendered
    assert "- C：让第三人无意说漏半句" in rendered
    assert "揭示意图：只透露钥匙与旧锁有关" in rendered
    assert "- 对话揭示：只说钥匙不普通，不解释来源" in rendered
    assert "- 插件技法：（空）" in rendered
    assert "关联事实 ID：f001" in rendered
    assert "事实或意图：林乔收起了钥匙。" in rendered
    assert "冲突原因：现有事实说明钥匙在林乔手里" in rendered
    assert "需要问作者：改目的，还是改已确认事实？" in rendered
    assert "作者已经选择" not in rendered


def test_render_reverse_card_makes_prerequisite_attach_order_explicit() -> None:
    request = _request(mode="reverse")
    response = _provider_result(
        cards=[
            _card(card_id="card01", role="prerequisite"),
            _card(card_id="card02", role="attach"),
        ]
    )
    result = plan_tool.execute(request, _CapturingProvider(response))

    rendered = plan_tool.render_c7_v1(result)

    assert "规划模式：reverse（逆向）" in rendered
    assert "逆向卡片处理顺序：prerequisite → attach" in rendered
    assert "先处理 prerequisite，再处理后续 attach" in rendered
    prerequisite = rendered.index("[1] 钥匙来历出现疑点（card01）")
    attach = rendered.index("[2] 钥匙来历出现疑点（card02）")
    assert prerequisite < attach
    assert "角色：prerequisite（前置条件卡）" in rendered
    assert "角色：attach（附加卡）" in rendered
    assert "作者已经选择" not in rendered


@pytest.mark.parametrize(
    "damage",
    ["duplicate_card", "duplicate_option", "missing_recommendation", "bad_ref"],
)
def test_render_reuses_strict_c7_validation_and_rejects_bad_cards(
    damage: str,
) -> None:
    result = plan_tool.execute(_request(), _CapturingProvider(_provider_result()))
    damaged = copy.deepcopy(result)
    card = damaged["cards"][0]
    if damage == "duplicate_card":
        damaged["cards"].append(copy.deepcopy(card))
    elif damage == "duplicate_option":
        card["options"].append(copy.deepcopy(card["options"][0]))
    elif damage == "missing_recommendation":
        card["recommended_option_ref"] = "Z"
    else:
        card["planning_card_ref"] = "not-a-planning-card"

    with pytest.raises(plan_tool.PlanToolError):
        plan_tool.render_c7_v1(damaged)


def test_render_cli_file_and_stdin_stdout_are_byte_stable_across_processes(
    tmp_path: Path,
) -> None:
    result = plan_tool.execute(_request(), _CapturingProvider(_provider_result()))
    input_path = tmp_path / "c7.json"
    output_path = tmp_path / "planning-card.txt"
    _write_json(input_path, result)
    expected = plan_tool.render_c7_v1(result).encode("utf-8")

    file_run = subprocess.run(
        [
            sys.executable,
            str(PLAN_TOOL_SCRIPT),
            "--render",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
    )
    stdout_run = subprocess.run(
        [
            sys.executable,
            str(PLAN_TOOL_SCRIPT),
            "--render",
            "--input",
            "-",
            "--output",
            "-",
        ],
        input=json.dumps(result, ensure_ascii=False).encode("utf-8"),
        check=False,
        capture_output=True,
    )

    assert file_run.returncode == 0, file_run.stderr.decode("utf-8")
    assert stdout_run.returncode == 0, stdout_run.stderr.decode("utf-8")
    assert output_path.read_bytes() == expected
    assert stdout_run.stdout == expected


def test_render_file_replace_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "planning-card.txt"
    output_path.write_bytes(b"existing-render\n")
    before = output_path.read_bytes()
    result = plan_tool.execute(_request(), _CapturingProvider(_provider_result()))

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic render replace failure")

    monkeypatch.setattr(plan_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic render replace failure"):
        plan_tool._write_text_atomic(output_path, plan_tool.render_c7_v1(result))

    assert output_path.read_bytes() == before
    assert not list(tmp_path.glob(".planning-card.txt.*.tmp"))


@pytest.mark.parametrize("mode", ["forward", "reverse"])
def test_c7_snapshot_sha_is_stable_for_valid_forward_and_reverse(mode: str) -> None:
    cards = None
    if mode == "reverse":
        cards = [
            _card(card_id="card01", role="prerequisite"),
            _card(card_id="card02", role="attach"),
        ]
    result = plan_tool.execute(
        _request(mode=mode),
        _CapturingProvider(_provider_result(cards=cards)),
    )

    first = plan_tool.c7_snapshot_sha256(result)
    second = plan_tool.c7_snapshot_sha256(copy.deepcopy(result))

    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")


def test_c7_snapshot_sha_ignores_json_object_key_order_only() -> None:
    result = plan_tool.execute(_request(), _CapturingProvider(_provider_result()))
    reordered = json.loads(
        json.dumps(result, ensure_ascii=False, sort_keys=True)
    )
    canonical_bytes = (
        json.dumps(
            plan_tool.validate_c7_v1(result),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    assert list(reordered) != list(result)
    assert plan_tool.c7_snapshot_sha256(reordered) == plan_tool.c7_snapshot_sha256(
        result
    )
    assert plan_tool.c7_snapshot_sha256(result) == hashlib.sha256(
        canonical_bytes
    ).hexdigest()


def test_c7_snapshot_sha_changes_for_core_snapshot_identity_fields() -> None:
    result = plan_tool.execute(_request(), _CapturingProvider(_provider_result()))
    baseline = plan_tool.c7_snapshot_sha256(result)
    variants: list[dict] = []

    purpose = copy.deepcopy(result)
    purpose["purpose"] = "让周宁先怀疑旧锁"
    variants.append(purpose)

    recommendation = copy.deepcopy(result)
    recommendation["cards"][0]["recommended_option_ref"] = "A"
    variants.append(recommendation)

    card_ref = copy.deepcopy(result)
    card_ref["cards"][0]["planning_card_ref"] = "AC-0008"
    variants.append(card_ref)

    card_rev = copy.deepcopy(result)
    card_rev["cards"][0]["planning_card_rev"] = 4
    variants.append(card_rev)

    fact_id = copy.deepcopy(result)
    fact_id["confirmed_fact_ids"][0] = "f999"
    fact_id["conflicts"][0]["fact_id"] = "f999"
    variants.append(fact_id)

    provider = copy.deepcopy(result)
    provider["model"] = "OTHER_FROZEN_PROVIDER_IDENTITY"
    variants.append(provider)

    generated_at = copy.deepcopy(result)
    generated_at["generated_at"] = "2026-08-19 11:00:01"
    variants.append(generated_at)

    for variant in variants:
        plan_tool.validate_c7_v1(variant)
        assert plan_tool.c7_snapshot_sha256(variant) != baseline


def test_c7_snapshot_sha_preserves_card_option_and_conflict_list_order() -> None:
    result = plan_tool.execute(_request(), _CapturingProvider(_provider_result()))

    two_cards = copy.deepcopy(result)
    second_card = copy.deepcopy(two_cards["cards"][0])
    second_card["id"] = "card02"
    two_cards["cards"].append(second_card)
    cards_reordered = copy.deepcopy(two_cards)
    cards_reordered["cards"].reverse()

    options_reordered = copy.deepcopy(result)
    options_reordered["cards"][0]["options"].reverse()

    two_conflicts = copy.deepcopy(result)
    two_conflicts["conflicts"].append(
        {
            "kind": "intent",
            "fact_id": "",
            "fact_text": "钥匙来源继续保密",
            "why": "当前目的可能提前揭晓来源",
            "ask": "改目的，还是改本章原意图？",
        }
    )
    conflicts_reordered = copy.deepcopy(two_conflicts)
    conflicts_reordered["conflicts"].reverse()

    assert plan_tool.c7_snapshot_sha256(two_cards) != plan_tool.c7_snapshot_sha256(
        cards_reordered
    )
    assert plan_tool.c7_snapshot_sha256(result) != plan_tool.c7_snapshot_sha256(
        options_reordered
    )
    assert plan_tool.c7_snapshot_sha256(
        two_conflicts
    ) != plan_tool.c7_snapshot_sha256(conflicts_reordered)


def test_c7_snapshot_sha_rejects_bad_c7_before_hashing() -> None:
    result = plan_tool.execute(_request(), _CapturingProvider(_provider_result()))
    result["cards"][0]["recommended_option_ref"] = "Z"

    with pytest.raises(
        plan_tool.PlanToolError,
        match="RECOMMENDED_OPTION_NOT_FOUND",
    ):
        plan_tool.c7_snapshot_sha256(result)


def test_identity_cli_matches_function_and_is_byte_stable_across_processes(
    tmp_path: Path,
) -> None:
    result = plan_tool.execute(_request(), _CapturingProvider(_provider_result()))
    input_path = tmp_path / "c7.json"
    output_path = tmp_path / "c7-identity.json"
    _write_json(input_path, result)

    file_run = subprocess.run(
        [
            sys.executable,
            str(PLAN_TOOL_SCRIPT),
            "--identity",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
    )
    stdout_run = subprocess.run(
        [
            sys.executable,
            str(PLAN_TOOL_SCRIPT),
            "--identity",
            "--input",
            "-",
            "--output",
            "-",
        ],
        input=json.dumps(result, ensure_ascii=False).encode("utf-8"),
        check=False,
        capture_output=True,
    )

    assert file_run.returncode == 0, file_run.stderr.decode("utf-8")
    assert stdout_run.returncode == 0, stdout_run.stderr.decode("utf-8")
    assert output_path.read_bytes() == stdout_run.stdout
    identity = json.loads(stdout_run.stdout)
    assert identity == {
        "contract": "C7_PLOT_LAYER v1",
        "project": "合成测试书",
        "card_local_ids": ["card01"],
        "source_c7_snapshot_sha256": plan_tool.c7_snapshot_sha256(result),
    }
    assert not ({"selection", "option_record", "plan_mutations"} & set(identity))


def test_identity_file_replace_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = plan_tool.execute(_request(), _CapturingProvider(_provider_result()))
    input_path = tmp_path / "c7.json"
    output_path = tmp_path / "c7-identity.json"
    _write_json(input_path, result)
    output_path.write_bytes(b"existing-identity\n")
    before = output_path.read_bytes()

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic identity replace failure")

    monkeypatch.setattr(plan_tool.os, "replace", fail_replace)
    code = plan_tool.main(
        [
            "--identity",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )

    assert code == 2
    assert output_path.read_bytes() == before
    assert not list(tmp_path.glob(".c7-identity.json.*.tmp"))

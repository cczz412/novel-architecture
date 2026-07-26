from __future__ import annotations

import copy
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C13_downstream_consumer_program_20260725"
)
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import v02_c13_downstream_consumer as c13  # noqa: E402
import v02_c13_signoff_floor_v2 as r04  # noqa: E402


pytestmark = pytest.mark.v02


@pytest.fixture(scope="module")
def decoded() -> dict[str, Any]:
    return {
        name: (
            json.loads(raw.decode("utf-8"))
            if name.endswith(".json")
            else raw.decode("utf-8")
        )
        for name, raw in r04.build_artifacts().items()
    }


def _task_b_nodes() -> list[dict[str, Any]]:
    plan = json.loads(
        (
            r04.SOURCE_R02 / "plans/call_plan.json"
        ).read_text(encoding="utf-8")
    )
    return [row for row in plan["nodes"] if row["task"] == "B"]


def _spread(total: int, slots: int) -> list[int]:
    if total < 0 or total > slots * 9:
        raise ValueError("total 超出 9 题 × slots")
    values: list[int] = []
    remaining = total
    for _ in range(slots):
        value = min(9, remaining)
        values.append(value)
        remaining -= value
    return values


def _observations(
    *,
    formal: int,
    shuffled: int,
    blank: int,
) -> list[dict[str, Any]]:
    nodes = _task_b_nodes()
    by_kind = {
        "FORMAL": [
            row for row in nodes if row.get("floor_kind") is None
        ],
        "SHUFFLED_FACT_ORDER": [
            row
            for row in nodes
            if row.get("floor_kind") == "SHUFFLED_FACT_ORDER"
        ],
        "CHAPTER_NUMBER_ONLY": [
            row
            for row in nodes
            if row.get("floor_kind") == "CHAPTER_NUMBER_ONLY"
        ],
    }
    totals = {
        "FORMAL": formal,
        "SHUFFLED_FACT_ORDER": shuffled,
        "CHAPTER_NUMBER_ONLY": blank,
    }
    result: list[dict[str, Any]] = []
    for kind, kind_nodes in by_kind.items():
        counts = _spread(totals[kind], len(kind_nodes))
        for node, count in zip(kind_nodes, counts, strict=True):
            result.append(
                {
                    "provider_id": "qianwen_platform",
                    "call_id": node["call_id"],
                    "observable": True,
                    "claim_count": count,
                    "contract_accepted": True,
                }
            )
    return result


def _insufficient_answers() -> list[dict[str, Any]]:
    return [
        {
            "question_family": family,
            "status": "MATERIAL_INSUFFICIENT",
            "answer": "",
            "supporting_fact_ids": [],
            "missing_bucket": "FACT_NOT_EXTRACTED",
            "missing_reason": "材料没有提供足够事实。",
        }
        for family in c13.QUESTION_FAMILIES
    ]


def _task_b_payload() -> dict[str, Any]:
    return {
        "material_id": "M01",
        "external_knowledge_used": False,
        "task": "B",
        "answers": _insufficient_answers(),
    }


def _provider_envelope(
    content_payload: Mapping[str, Any],
    *,
    model_id: str = "qwen3.7-max-2026-05-20",
) -> bytes:
    return r04.canonical_bytes(
        {
            "id": "req-c13-test-001",
            "model": model_id,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            content_payload,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "reasoning_content": "",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }
    )


def _provider_payload_for_call(
    provider_id: str,
    call_id: str,
) -> tuple[dict[str, Any], str]:
    frozen = r04._resolve_frozen_task_b_binding(
        provider_id=provider_id,
        call_id=call_id,
    )
    payload = _task_b_payload()
    payload["material_id"] = frozen["expected_material_id"]
    return payload, frozen["expected_model_id"]


def _persist_provider_ledger_pairs(
    ledger_root: Path,
    *,
    provider_id: str = "qianwen_platform",
    attempt_no: int = 1,
) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for node in _task_b_nodes():
        call_id = str(node["call_id"])
        payload, model_id = _provider_payload_for_call(
            provider_id,
            call_id,
        )
        result = r04.persist_observe_and_validate_task_b(
            _provider_envelope(payload, model_id=model_id),
            ledger_root=ledger_root,
            provider_id=provider_id,
            call_id=call_id,
            attempt_no=attempt_no,
        )
        pairs.append(
            {
                "claim_ledger_path": result["claim_ledger_path"],
                "contract_ledger_path": result["contract_ledger_path"],
            }
        )
    return pairs


def test_bundle_has_three_signoff_proofs_and_remains_non_executable(
    decoded: dict[str, Any],
) -> None:
    manifest = decoded["artifact_manifest.json"]
    a_rows = decoded["signoff/A_prompt_slot_diff_table.json"]["rows"]
    b = decoded["signoff/B_messages_blacklist_scan_receipt.json"]
    c = decoded["signoff/C_allowed_difference_receipt.json"]
    binding = decoded["signoff/C_source_to_wire_binding_receipt.json"]
    floor = decoded["contracts/floor_claim_v2_contract.json"]

    assert manifest["prompt_slot_total"] == 30
    assert manifest["wire_message_copy_total"] == 90
    assert manifest["model_api_calls"] == 0
    assert manifest["network_requests"] == 0
    assert manifest["key_value_read"] is False
    assert manifest["execute_allowed"] is False
    assert len(a_rows) == 30
    assert b["status"] == "PASS_DECLARED_RULES_ZERO_HITS"
    assert b["message_blacklist_hit_total"] == 0
    assert b["wire_security_hit_total"] == 0
    assert b["prior_leak_risk_names"] is True
    assert b["prior_leak_risk_names_detector_present"] is False
    assert c["unexpected_variable_path_total"] == 0
    assert binding["binding_pass_total"] == 90
    assert floor["per_provider_denominators"] == {
        "FORMAL": 54,
        "SHUFFLED_FACT_ORDER": 18,
        "CHAPTER_NUMBER_ONLY": 18,
    }
    assert floor["prompt_or_provider_result_unsealed_total"] == 0


def test_plaintext_review_covers_three_shapes_and_three_tasks(
    decoded: dict[str, Any],
) -> None:
    review = decoded["signoff/A_prompt_text_samples.md"]
    rows = {
        row["call_id"]: row
        for row in decoded["signoff/A_prompt_slot_diff_table.json"]["rows"]
    }

    assert {rows[call_id]["task"] for call_id in r04.SAMPLE_CALL_IDS} == {
        "A",
        "B",
        "C",
    }
    assert {
        rows[call_id]["prompt_kind"] for call_id in r04.SAMPLE_CALL_IDS
    } == {
        "FORMAL",
        "SHUFFLED_FACT_ORDER",
        "CHAPTER_NUMBER_ONLY",
    }
    for call_id in r04.SAMPLE_CALL_IDS:
        assert call_id in review
        assert rows[call_id]["messages_sha256"] in review
    assert review.count("```json") == 3
    assert "来源：Codex" in review


def test_blacklist_does_not_false_hit_fact_ids_or_sequence_numbers() -> None:
    clean = [
        {
            "role": "user",
            "content": '{"fact_id":"F049","seq":49,"facts":["F321"]}',
        }
    ]
    assert r04.scan_messages_blacklist(clean) == []


@pytest.mark.parametrize(
    "text, expected_rule",
    [
        ("这是实验臂。", "EXPERIMENT_IDENTITY"),
        ("分母49", "INTERNAL_DENOMINATOR_CONTEXT"),
        ("25/49", "INTERNAL_DENOMINATOR_CONTEXT"),
        ("C13", "BATCH_ID"),
        ("Ｃ１３", "BATCH_ID"),
        ("腾讯 deepseek", "MODEL_OR_PROVIDER"),
        ("ｄｅｅｐｓｅｅｋ", "MODEL_OR_PROVIDER"),
        ("runs/example", "LOCAL_PATH"),
        ("金标", "GOLD_OR_INTERNAL_METRIC"),
    ],
)
def test_blacklist_canaries_hit_only_declared_risks(
    text: str,
    expected_rule: str,
) -> None:
    hits = r04.scan_messages_blacklist(
        [{"role": "user", "content": text}]
    )
    assert expected_rule in {row["rule_id"] for row in hits}


def test_allowed_difference_proof_rejects_unknown_top_level_field() -> None:
    prompt_bundle = json.loads(
        (
            r04.SOURCE_R02
            / "prompt_review/exact_visible_messages.json"
        ).read_text(encoding="utf-8")
    )
    row = copy.deepcopy(prompt_bundle["rows"][0])
    payload = json.loads(row["messages"][1]["content"])
    payload["unexpected"] = True
    row["messages"][1]["content"] = json.dumps(
        payload,
        ensure_ascii=False,
    )

    with pytest.raises(r04.C13R04Error, match="user 顶层字段漂移"):
        r04._parse_prompt_row(row)


def test_source_to_wire_binding_is_exact_for_every_provider(
    decoded: dict[str, Any],
) -> None:
    receipt = decoded["signoff/C_source_to_wire_binding_receipt.json"]
    rows = receipt["rows"]

    assert len(rows) == 90
    assert {
        row["provider_id"] for row in rows
    } == set(r04.EXPECTED_PROVIDER_IDS)
    assert all(row["messages_byte_equal"] for row in rows)
    assert all(row["body_field_set_exact"] for row in rows)
    assert all(row["manifest_member"] for row in rows)


def test_allowed_difference_proof_is_bound_to_pinned_program_constants(
    decoded: dict[str, Any],
) -> None:
    contract = decoded["contracts/allowed_difference_contract.json"]
    receipt = decoded["signoff/C_allowed_difference_receipt.json"]

    assert (
        contract["authority_source_program_sha256"]
        == r04.EXPECTED_C13_PROGRAM_SHA256
    )
    assert (
        receipt["authority_source_program_sha256"]
        == r04.EXPECTED_C13_PROGRAM_SHA256
    )
    assert "PINNED_C13_PROGRAM_CONSTANTS" in receipt["validation_basis"]
    assert "EXACT_TASK_TEMPLATE_EQUALITY" in receipt["validation_basis"]


def test_answered_empty_row_is_still_counted_before_contract_rejection() -> None:
    payload = _task_b_payload()
    payload["answers"][0].update(
        {
            "status": "ANSWERED",
            "answer": "",
            "supporting_fact_ids": [],
            "missing_bucket": None,
            "missing_reason": "",
        }
    )

    result = r04.observe_then_validate_task_b(
        payload,
        expected_material_id="M01",
        allowed_fact_ids={"F001"},
    )

    assert result["claim_ledger"]["observable"] is True
    assert result["claim_ledger"]["claim_count"] == 1
    assert result["contract_ledger"]["accepted"] is False


def test_nonempty_answer_and_fabricated_id_each_count_as_claim() -> None:
    payload = _task_b_payload()
    payload["answers"][0]["answer"] = "我仍然给出答案"
    payload["answers"][1]["supporting_fact_ids"] = ["F999"]

    observed = r04.observe_task_b_claims(
        payload,
        allowed_fact_ids={"F001"},
    )

    assert observed["observable"] is True
    assert observed["claim_count"] == 2
    assert observed["questions"][0]["claim"] is True
    assert observed["questions"][1]["unknown_fact_ids"] == ["F999"]


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '{"answers":"not-an-array"}',
    ],
)
def test_unobservable_raw_response_never_becomes_zero_claim(raw: str) -> None:
    result = r04.observe_raw_json_task_b_claims(
        raw,
        allowed_fact_ids=set(),
    )
    assert result["observable"] is False
    assert result["claim_count"] is None


@pytest.mark.parametrize(
    "formal, blank, expected_status",
    [
        (22, 2, "VALID_FLOOR_SCREEN_NOT_QUALITY_VERDICT"),
        (22, 3, "INVALID_PROVIDER_FLOOR_CLAIM"),
        (22, 5, "INVALID_PROVIDER_FLOOR_CLAIM"),
        (21, 2, "VALID_RUN_MATERIAL_INSUFFICIENT_NOT_MODEL_USABLE"),
        (21, 3, "INVALID_PROVIDER_FLOOR_CLAIM"),
        (0, 0, "VALID_RUN_MATERIAL_INSUFFICIENT_NOT_MODEL_USABLE"),
    ],
)
def test_floor_v2_integer_boundaries(
    formal: int,
    blank: int,
    expected_status: str,
) -> None:
    result = r04._evaluate_provider_claim_floor_from_verified_rows(
        _observations(formal=formal, shuffled=0, blank=blank),
        provider_id="qianwen_platform",
    )
    assert result["formal_claim_count"] == formal
    assert result["blank_claim_count"] == blank
    assert result["status"] == expected_status
    assert result["quality_verdict"] == "NOT_A_QUALITY_VERDICT"


def test_one_extra_claim_in_same_material_shuffle_pair_is_hard_stop() -> None:
    observations = _observations(formal=0, shuffled=1, blank=0)
    result = r04._evaluate_provider_claim_floor_from_verified_rows(
        observations,
        provider_id="qianwen_platform",
    )

    assert result["status"] == "HARD_STOP_SHUFFLE_REVERSE_ADVANTAGE"
    assert result["shuffle_hard_stop"] is True
    assert any(
        row["shuffle_minus_formal_pp"] > 10
        for row in result["shuffle_pairs"]
    )


def test_unobservable_call_hard_stops_instead_of_shrinking_denominator() -> None:
    observations = _observations(formal=22, shuffled=0, blank=2)
    observations[0]["observable"] = False
    observations[0]["claim_count"] = None

    result = r04._evaluate_provider_claim_floor_from_verified_rows(
        observations,
        provider_id="qianwen_platform",
    )

    assert result["status"] == "HARD_STOP_CLAIM_UNOBSERVABLE"
    assert result["formal_claim_count"] is None
    assert result["denominators"] == r04.EXPECTED_DENOMINATORS


def test_cross_provider_row_is_rejected_before_aggregation() -> None:
    observations = _observations(formal=22, shuffled=0, blank=2)
    observations[-1]["provider_id"] = "volcengine_ark"

    with pytest.raises(r04.C13R04Error, match="混入了其他供应商"):
        r04._evaluate_provider_claim_floor_from_verified_rows(
            observations,
            provider_id="qianwen_platform",
        )


def test_boolean_claim_count_is_not_accepted_as_integer() -> None:
    observations = _observations(formal=22, shuffled=0, blank=2)
    observations[0]["claim_count"] = True

    result = r04._evaluate_provider_claim_floor_from_verified_rows(
        observations,
        provider_id="qianwen_platform",
    )

    assert result["status"] == "HARD_STOP_CLAIM_UNOBSERVABLE"
    assert result["formal_claim_count"] is None


def test_blank_absolute_boundary_and_exact_shuffle_tie() -> None:
    pass_rows = _observations(formal=54, shuffled=0, blank=4)
    by_call = {row["call_id"]: row for row in pass_rows}
    by_call["C13-N07"]["claim_count"] = 1
    by_call["C13-N09"]["claim_count"] = 1
    by_call["C13-N02"]["claim_count"] = 8

    passed = r04._evaluate_provider_claim_floor_from_verified_rows(
        pass_rows,
        provider_id="qianwen_platform",
    )
    failed = r04._evaluate_provider_claim_floor_from_verified_rows(
        _observations(formal=54, shuffled=0, blank=5),
        provider_id="qianwen_platform",
    )

    assert passed["blank_claim_count"] == 4
    assert passed["blank_absolute_gate_pass"] is True
    assert passed["shuffle_hard_stop"] is False
    assert failed["blank_claim_count"] == 5
    assert failed["blank_absolute_gate_pass"] is False


def test_contract_rejection_keeps_floor_count_but_blocks_overall_acceptance() -> None:
    observations = _observations(formal=22, shuffled=0, blank=2)
    observations[0]["contract_accepted"] = False

    result = r04._evaluate_provider_claim_floor_from_verified_rows(
        observations,
        provider_id="qianwen_platform",
    )

    assert result["formal_claim_count"] == 22
    assert result["floor_claim_status"] == (
        "VALID_FLOOR_SCREEN_NOT_QUALITY_VERDICT"
    )
    assert result["status"] == "NOT_ACCEPTABLE_CONTRACT_REJECTIONS_PRESENT"
    assert result["contract_rejection_total"] == 1


def test_floor_contract_freezes_runtime_identity_and_persistence_order(
    decoded: dict[str, Any],
) -> None:
    contract = decoded["contracts/floor_claim_v2_contract.json"]
    assert contract["raw_response_persistence_order"] == [
        "persist_raw_response_bytes",
        "record_raw_response_sha256",
        "observe_pre_contract_claim",
        "run_contract_validation",
        "append_claim_and_contract_ledgers",
    ]
    assert contract["runtime_ledger_identity_exact_fields"] == [
        "provider_id",
        "call_id",
        "attempt_no",
        "request_body_sha256",
        "raw_response_sha256",
    ]
    assert (
        contract["runtime_ledger_identity_fields_must_match_between_ledgers"]
        is True
    )
    assert contract["public_evaluator_input"] == (
        "TEN_CLAIM_AND_CONTRACT_LEDGER_PATH_PAIRS_ONLY"
    )
    assert (
        contract["public_evaluator_must_replay_every_pair_from_raw_response"]
        is True
    )
    assert contract["handwritten_observation_rows_are_forbidden"] is True
    assert contract["attempt_selection_rule"] == (
        "EXACTLY_ONE_COMPLETE_DUAL_LEDGER_PAIR_PER_FROZEN_CALL;"
        "ANY_EXTRA_OR_PARTIAL_ATTEMPT_HARD_STOPS"
    )
    assert contract["provider_contract_rejection_claim_policy"] == (
        "OBSERVE_CLAIM_WHEN_MODEL_CONTENT_BYTES_ARE_LOCATABLE;"
        "ONLY_UNLOCATABLE_CONTENT_IS_UNOBSERVABLE"
    )
    assert contract["evaluation_scope"] == {
        "one_provider_per_evaluation": True,
        "every_observation_provider_id_must_equal_requested_provider": True,
        "cross_provider_pooling": False,
    }


def test_raw_response_is_persisted_before_separate_ledgers_and_is_replayable(
    tmp_path: Path,
) -> None:
    payload = _task_b_payload()
    payload["answers"][0].update(
        {
            "status": "ANSWERED",
            "answer": "",
            "supporting_fact_ids": [],
            "missing_bucket": None,
            "missing_reason": "",
        }
    )
    raw_response = _provider_envelope(payload)
    ledger_root = tmp_path / "audit"

    result = r04.persist_observe_and_validate_task_b(
        raw_response,
        ledger_root=ledger_root,
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=1,
    )

    assert result["observable"] is True
    assert result["claim_count"] == 1
    assert result["contract_accepted"] is False
    assert Path(result["raw_response_path"]).read_bytes() == raw_response
    assert r04.ROOT / Path(result["request_body_path"]) == (
        r04.SOURCE_R03 / "wire/qianwen_platform/C13-N02.json"
    )
    claim_path = Path(result["claim_ledger_path"])
    contract_path = Path(result["contract_ledger_path"])
    replay = r04.verify_task_b_dual_ledgers(claim_path, contract_path)
    assert replay == {
        key: value
        for key, value in result.items()
        if key != "write_status"
    }

    resumed = r04.persist_observe_and_validate_task_b(
        raw_response,
        ledger_root=ledger_root,
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=1,
    )
    assert resumed["write_status"] == {
        "raw_response": "REUSED_EXACT_BYTES",
        "claim_ledger": "REUSED_EXACT_BYTES",
        "contract_ledger": "REUSED_EXACT_BYTES",
    }


def test_dual_ledger_identity_tampering_is_rejected(tmp_path: Path) -> None:
    raw_response = _provider_envelope(_task_b_payload())
    result = r04.persist_observe_and_validate_task_b(
        raw_response,
        ledger_root=tmp_path / "audit",
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=1,
    )
    contract_path = Path(result["contract_ledger_path"])
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["provider_id"] = "volcengine_ark"
    contract_path.write_bytes(r04.canonical_bytes(contract))

    with pytest.raises(r04.C13R04Error, match="身份不一致"):
        r04.verify_task_b_dual_ledgers(
            Path(result["claim_ledger_path"]),
            contract_path,
        )


def test_dual_ledger_claim_or_contract_tampering_is_recomputed_and_rejected(
    tmp_path: Path,
) -> None:
    result = r04.persist_observe_and_validate_task_b(
        _provider_envelope(_task_b_payload()),
        ledger_root=tmp_path / "audit",
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=1,
    )
    claim_path = Path(result["claim_ledger_path"])
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    claim["observation"]["claim_count"] = 9
    claim_path.write_bytes(r04.canonical_bytes(claim))

    with pytest.raises(r04.C13R04Error, match="逐字重算"):
        r04.verify_task_b_dual_ledgers(
            claim_path,
            Path(result["contract_ledger_path"]),
        )


def test_dual_ledger_contract_result_tampering_is_recomputed_and_rejected(
    tmp_path: Path,
) -> None:
    result = r04.persist_observe_and_validate_task_b(
        _provider_envelope(_task_b_payload()),
        ledger_root=tmp_path / "audit",
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=1,
    )
    contract_path = Path(result["contract_ledger_path"])
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["validation"]["accepted"] = True
    contract_path.write_bytes(r04.canonical_bytes(contract))

    with pytest.raises(r04.C13R04Error, match="合同账无法.*重算"):
        r04.verify_task_b_dual_ledgers(
            Path(result["claim_ledger_path"]),
            contract_path,
        )


def test_provider_contract_rejection_keeps_observable_claim(
    tmp_path: Path,
) -> None:
    result = r04.persist_observe_and_validate_task_b(
        _provider_envelope(_task_b_payload(), model_id="wrong-model"),
        ledger_root=tmp_path / "audit",
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=1,
    )

    assert result["observable"] is True
    assert result["claim_count"] == 0
    assert result["contract_accepted"] is False


def test_missing_model_content_is_unobservable_not_zero_claim(
    tmp_path: Path,
) -> None:
    raw_response = r04.canonical_bytes(
        {
            "id": "req-c13-test-no-content",
            "model": "qwen3.7-max-2026-05-20",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"reasoning_content": ""},
                }
            ],
            "usage": {"total_tokens": 1},
        }
    )
    result = r04.persist_observe_and_validate_task_b(
        raw_response,
        ledger_root=tmp_path / "audit",
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=1,
    )

    assert result["observable"] is False
    assert result["claim_count"] is None
    assert result["contract_accepted"] is False


def test_non_json_model_content_writes_replayable_rejection_ledgers(
    tmp_path: Path,
) -> None:
    raw_response = r04.canonical_bytes(
        {
            "id": "req-c13-test-non-json-content",
            "model": "qwen3.7-max-2026-05-20",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": "not json",
                        "reasoning_content": "",
                    },
                }
            ],
            "usage": {"total_tokens": 2},
        }
    )
    result = r04.persist_observe_and_validate_task_b(
        raw_response,
        ledger_root=tmp_path / "audit",
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=1,
    )

    assert result["observable"] is False
    assert result["claim_count"] is None
    assert result["contract_accepted"] is False
    replay = r04.verify_task_b_dual_ledgers(
        Path(result["claim_ledger_path"]),
        Path(result["contract_ledger_path"]),
    )
    assert replay["observable"] is False
    assert replay["claim_count"] is None


def test_public_floor_evaluator_replays_ten_dual_ledger_pairs(
    tmp_path: Path,
) -> None:
    ledger_root = tmp_path / "audit"
    pairs = _persist_provider_ledger_pairs(ledger_root)

    result = r04.evaluate_provider_claim_floor(
        pairs,
        provider_id="qianwen_platform",
    )

    assert result["status"] == (
        "VALID_RUN_MATERIAL_INSUFFICIENT_NOT_MODEL_USABLE"
    )
    assert result["formal_claim_count"] == 0
    assert result["blank_claim_count"] == 0
    assert result["evidence_gate"]["dual_ledger_pair_total"] == 10
    assert (
        result["evidence_gate"][
            "all_pairs_replayed_from_raw_provider_envelopes"
        ]
        is True
    )


def test_public_floor_evaluator_rejects_handwritten_observation_rows() -> None:
    with pytest.raises(r04.C13R04Error, match="只能含"):
        r04.evaluate_provider_claim_floor(
            _observations(formal=22, shuffled=0, blank=2),
            provider_id="qianwen_platform",
        )


def test_public_floor_evaluator_rejects_hidden_extra_attempt(
    tmp_path: Path,
) -> None:
    ledger_root = tmp_path / "audit"
    pairs = _persist_provider_ledger_pairs(ledger_root)
    payload, model_id = _provider_payload_for_call(
        "qianwen_platform",
        "C13-N02",
    )
    r04.persist_observe_and_validate_task_b(
        _provider_envelope(payload, model_id=model_id),
        ledger_root=ledger_root,
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=2,
    )

    with pytest.raises(r04.C13R04Error, match="禁止挑选结果"):
        r04.evaluate_provider_claim_floor(
            pairs,
            provider_id="qianwen_platform",
        )


def test_non_task_b_call_id_is_rejected_before_raw_response_is_written(
    tmp_path: Path,
) -> None:
    ledger_root = tmp_path / "audit"
    with pytest.raises(r04.C13R04Error, match="不是冻结的任务 B"):
        r04.persist_observe_and_validate_task_b(
            _provider_envelope(_task_b_payload()),
            ledger_root=ledger_root,
            provider_id="qianwen_platform",
            call_id="C13-N01",
            attempt_no=1,
        )
    assert not ledger_root.exists()


def test_partial_ledger_write_can_resume_only_from_same_raw_bytes(
    tmp_path: Path,
) -> None:
    raw = _provider_envelope(_task_b_payload())
    ledger_root = tmp_path / "audit"
    first = r04.persist_observe_and_validate_task_b(
        raw,
        ledger_root=ledger_root,
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=1,
    )
    Path(first["contract_ledger_path"]).unlink()

    resumed = r04.persist_observe_and_validate_task_b(
        raw,
        ledger_root=ledger_root,
        provider_id="qianwen_platform",
        call_id="C13-N02",
        attempt_no=1,
    )
    assert resumed["write_status"]["raw_response"] == "REUSED_EXACT_BYTES"
    assert resumed["write_status"]["claim_ledger"] == "REUSED_EXACT_BYTES"
    assert resumed["write_status"]["contract_ledger"] == "CREATED"

    changed = raw + b"\n"
    with pytest.raises(r04.C13R04Error, match="重建字节不一致"):
        r04.persist_observe_and_validate_task_b(
            changed,
            ledger_root=ledger_root,
            provider_id="qianwen_platform",
            call_id="C13-N02",
            attempt_no=1,
        )


def test_double_build_and_write_do_not_touch_r02_or_r03(
    tmp_path: Path,
) -> None:
    r02_before = r04.sha256_file(r04.SOURCE_R02 / "artifact_manifest.json")
    r03_before = r04.sha256_file(r04.SOURCE_R03 / "artifact_manifest.json")
    output = tmp_path / "r04"
    report = tmp_path / "report"

    first = r04.write_or_verify(output, report, write=True)
    second = r04.write_or_verify(output, report, write=False)

    assert first == second
    assert first["prompt_slot_total"] == 30
    assert first["wire_message_copy_total"] == 90
    assert r04.sha256_file(
        r04.SOURCE_R02 / "artifact_manifest.json"
    ) == r02_before
    assert r04.sha256_file(
        r04.SOURCE_R03 / "artifact_manifest.json"
    ) == r03_before
    assert r02_before == r04.EXPECTED_R02_MANIFEST_SHA256
    assert r03_before == r04.EXPECTED_R03_MANIFEST_SHA256


def test_generator_has_no_network_or_provider_sdk_imports() -> None:
    source = Path(r04.__file__).read_text(encoding="utf-8")
    forbidden_imports = (
        "import requests",
        "import httpx",
        "import urllib",
        "import socket",
        "import openai",
        "import anthropic",
    )
    assert not any(marker in source for marker in forbidden_imports)


def test_wire_security_rejects_secret_and_authorization_shapes() -> None:
    body: Mapping[str, Any] = {
        "messages": [],
        "authorization": "Bearer secret",
    }
    hits = r04.scan_wire_security(body)
    assert {row["rule_id"] for row in hits} == {
        "FORBIDDEN_WIRE_KEY",
        "SECRET_OR_AUTHORIZATION_SHAPE",
    }

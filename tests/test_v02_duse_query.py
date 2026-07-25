from __future__ import annotations

import sys
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_duse_query as dq  # noqa: E402
import v02_duse_contract as dc  # noqa: E402


pytestmark = pytest.mark.v02


def _query(
    *,
    query_type: str = "CHARACTER_STATE_AT_CHAPTER_END",
    chapter: int = 3,
) -> dict[str, object]:
    return {
        "query_type": query_type,
        "entity_id": "ENTITY-TEST-01",
        "state_slot": "state.test",
        "as_of_chapter": chapter,
        "epistemic_owner": "OBJECTIVE",
    }


def _fact(
    fact_id: str,
    *,
    query_type: str = "CHARACTER_STATE_AT_CHAPTER_END",
    chapter: int = 3,
    valid_from: int | None = None,
    valid_until: int | None = None,
    verified: bool = True,
) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "query_type": query_type,
        "entity_id": "ENTITY-TEST-01",
        "state_slot": "state.test",
        "epistemic_owner": "OBJECTIVE",
        "chapter": chapter,
        "valid_from_chapter": valid_from or chapter,
        "valid_until_chapter": valid_until,
        "source_block_id": f"BLOCK-{chapter}",
        "claim_span": f"TEST-SPAN-{fact_id}",
        "source_span_sha256": str(chapter) * 64,
        "verbatim_verified": verified,
    }


@pytest.mark.parametrize(
    ("text", "expected_type", "owner"),
    [
        (
            "截至第3章，ENTITY-TEST-01的state.test是什么？",
            "CHARACTER_STATE_AT_CHAPTER_END",
            "OBJECTIVE",
        ),
        (
            "截至第3章，CHAR-OWNER是否知道ENTITY-TEST-01的state.test？",
            "EPISTEMIC_KNOWLEDGE_AT_CHAPTER",
            "CHAR-OWNER",
        ),
        (
            "截至第3章，ENTITY-TEST-01的目标state.test是什么？",
            "GOAL_LIFECYCLE",
            "OBJECTIVE",
        ),
        (
            "截至第3章，ENTITY-TEST-01的state.test首次出现在哪里？",
            "FIRST_APPEARANCE",
            "OBJECTIVE",
        ),
        (
            "截至第3章，ENTITY-TEST-01的state.test是否仍然一致？",
            "LONG_RANGE_CONSISTENCY",
            "OBJECTIVE",
        ),
    ],
)
def test_d_use_b_parses_five_query_types(
    text: str,
    expected_type: str,
    owner: str,
) -> None:
    result = dq.parse_natural_language_query(text)
    assert result["query_type"] == expected_type
    assert result["epistemic_owner"] == owner
    assert result["as_of_chapter"] == 3


def test_unparseable_question_is_rejected_not_guessed() -> None:
    with pytest.raises(dq.DUseQueryError, match="禁止模型猜写"):
        dq.parse_natural_language_query("他现在怎么样？")


def test_unique_and_multiple_legal_answers_return_found() -> None:
    unique = dq.execute_closed_query(
        _query(),
        [_fact("FACT-ONE")],
        material_complete_through_chapter=3,
    )
    assert unique["status"] == "FOUND"
    assert unique["fact_ids"] == ["FACT-ONE"]

    multiple = dq.execute_closed_query(
        _query(),
        [_fact("FACT-A"), _fact("FACT-B")],
        material_complete_through_chapter=3,
    )
    assert multiple["status"] == "FOUND"
    assert multiple["fact_ids"] == ["FACT-A", "FACT-B"]


def test_not_found_and_unknown_are_not_conflated() -> None:
    not_found = dq.execute_closed_query(
        _query(chapter=3),
        [],
        material_complete_through_chapter=3,
    )
    unknown = dq.execute_closed_query(
        _query(chapter=3),
        [],
        material_complete_through_chapter=2,
    )
    assert not_found["status"] == "NOT_FOUND"
    assert not_found["reason_code"] == "COMPLETE_SCOPE_NO_MATCH"
    assert unknown["status"] == "UNKNOWN"
    assert unknown["reason_code"] == "MATERIAL_SCOPE_INCOMPLETE"


def test_n_plus_one_future_canary_never_leaks_into_found() -> None:
    result = dq.execute_closed_query(
        _query(chapter=3),
        [
            _fact("FACT-N", chapter=3),
            _fact("FACT-N-PLUS-1-CANARY", chapter=4),
        ],
        material_complete_through_chapter=4,
    )
    assert result["status"] == "FOUND"
    assert result["fact_ids"] == ["FACT-N"]
    assert result["future_fact_ids_suppressed"] == ["FACT-N-PLUS-1-CANARY"]
    assert all(row["chapter"] <= 3 for row in result["evidence"])


def test_updated_state_does_not_return_old_history() -> None:
    result = dq.execute_closed_query(
        _query(chapter=3),
        [
            _fact(
                "FACT-OLD",
                chapter=1,
                valid_from=1,
                valid_until=2,
            ),
            _fact("FACT-CURRENT", chapter=3, valid_from=3),
        ],
        material_complete_through_chapter=3,
    )
    assert result["status"] == "FOUND"
    assert result["fact_ids"] == ["FACT-CURRENT"]


def test_expired_state_without_replacement_is_unknown() -> None:
    result = dq.execute_closed_query(
        _query(chapter=3),
        [
            _fact(
                "FACT-OLD",
                chapter=1,
                valid_from=1,
                valid_until=2,
            )
        ],
        material_complete_through_chapter=3,
    )
    assert result["status"] == "UNKNOWN"
    assert result["reason_code"] == "STATE_GAP_AFTER_EXPIRED_FACT"


def _human_case(
    case_id: str,
    *,
    kind: str,
    expected_status: str,
    expected_fact_ids: list[str],
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_kind": kind,
        "question_text": "人工已填写题面",
        "closed_query": _query(),
        "expected_status": expected_status,
        "expected_fact_ids": expected_fact_ids,
        "expected_evidence_spans": ["人工已核准短引"],
        "source_read_by_human": True,
        "derived_from_model_output": False,
        "review_status": "HUMAN_VERIFIED",
    }


def _write_valid_freeze_tickets(
    freeze_dir: Path,
    cases: list[dict[str, object]],
) -> None:
    freeze_dir.mkdir(parents=True, exist_ok=True)
    bindings = dq.expected_freeze_bindings(cases)
    question = {
        "schema_version": "v02-duse-question-freeze-ticket.v1",
        "status": dc.QUESTION_FREEZE_STATUS,
        "question_bank_sha256": bindings["question_bank_sha256"],
        "case_ids_sha256": bindings["case_ids_sha256"],
        "question_count": bindings["count"],
        "source_read_by_human": True,
        "derived_from_model_output": False,
    }
    answer = {
        "schema_version": "v02-duse-human-answer-freeze-ticket.v1",
        "status": dc.ANSWER_FREEZE_STATUS,
        "question_bank_sha256": bindings["question_bank_sha256"],
        "human_answer_bank_sha256": (bindings["human_answer_bank_sha256"]),
        "case_ids_sha256": bindings["case_ids_sha256"],
        "answer_count": bindings["count"],
        "reviewed_by_human": True,
        "derived_from_model_output": False,
    }
    (freeze_dir / dc.QUESTION_FREEZE_FILENAME).write_text(
        json.dumps(question),
        encoding="utf-8",
    )
    (freeze_dir / dc.ANSWER_FREEZE_FILENAME).write_text(
        json.dumps(answer),
        encoding="utf-8",
    )


def test_x10_x11_four_metrics_are_separate(tmp_path: Path) -> None:
    cases = [
        _human_case(
            "Q1",
            kind="EXPLICIT_NO_ANSWER",
            expected_status="NOT_FOUND",
            expected_fact_ids=[],
        ),
        _human_case(
            "Q2",
            kind="UPDATED_STATE_HISTORY_ONLY",
            expected_status="FOUND",
            expected_fact_ids=["FACT-CURRENT"],
        ),
    ]
    results = [
        {
            "status": "FOUND",
            "query": _query(),
            "fact_ids": ["FACT-WRONG"],
            "evidence": [
                {
                    "fact_id": "FACT-WRONG",
                    "source_block_id": "BLOCK-3",
                    "claim_span": "TRACE",
                    "source_span_sha256": "3" * 64,
                    "chapter": 4,
                    "verbatim_verified": False,
                }
            ],
            "future_fact_ids_suppressed": [],
            "reason_code": "MATCH_FOUND",
        },
        {
            "status": "FOUND",
            "query": _query(),
            "fact_ids": ["FACT-OLD"],
            "evidence": [
                {
                    "fact_id": "FACT-OLD",
                    "source_block_id": "BLOCK-2",
                    "claim_span": "TRACE",
                    "source_span_sha256": "2" * 64,
                    "chapter": 2,
                    "verbatim_verified": True,
                }
            ],
            "future_fact_ids_suppressed": [],
            "reason_code": "MATCH_FOUND",
        },
    ]
    freeze_dir = tmp_path / "freeze"
    _write_valid_freeze_tickets(freeze_dir, cases)
    score = dq.score_x10_x11_metrics(
        cases,
        results,
        freeze_dir=freeze_dir,
    )
    assert set(score["metrics"]) == {
        "future_information_leak_rate",
        "empty_answer_false_positive_rate",
        "stale_state_false_return_rate",
        "found_trace_completeness_rate",
    }
    assert score["metrics"]["future_information_leak_rate"] == 0.5
    assert score["metrics"]["empty_answer_false_positive_rate"] == 1.0
    assert score["metrics"]["stale_state_false_return_rate"] == 1.0
    assert score["metrics"]["found_trace_completeness_rate"] == 0.5
    assert score["combined_total_accuracy_emitted"] is False


def test_formal_scoring_is_blocked_while_human_answer_is_blank(
    tmp_path: Path,
) -> None:
    blank = _human_case(
        "Q1",
        kind="UNIQUE_ANSWER",
        expected_status="FOUND",
        expected_fact_ids=["FACT-ONE"],
    )
    blank["review_status"] = "HUMAN_REQUIRED"
    blank["question_text"] = "__HUMAN_REQUIRED__"
    result = dq.execute_closed_query(
        _query(),
        [_fact("FACT-ONE")],
        material_complete_through_chapter=3,
    )
    with pytest.raises(dq.DUseQueryError, match="禁止执行正式"):
        dq.score_x10_x11_metrics(
            [blank],
            [result],
            freeze_dir=tmp_path,
        )


def test_verified_flags_cannot_bypass_missing_freeze_tickets(
    tmp_path: Path,
) -> None:
    case = _human_case(
        "Q1",
        kind="UNIQUE_ANSWER",
        expected_status="FOUND",
        expected_fact_ids=["FACT-ONE"],
    )
    result = dq.execute_closed_query(
        _query(),
        [_fact("FACT-ONE")],
        material_complete_through_chapter=3,
    )
    with pytest.raises(dq.DUseQueryError, match="冻结票不存在"):
        dq.score_x10_x11_metrics(
            [case],
            [result],
            freeze_dir=tmp_path,
        )


def test_forged_or_drifted_freeze_sha_is_rejected(
    tmp_path: Path,
) -> None:
    case = _human_case(
        "Q1",
        kind="UNIQUE_ANSWER",
        expected_status="FOUND",
        expected_fact_ids=["FACT-ONE"],
    )
    freeze_dir = tmp_path / "freeze"
    _write_valid_freeze_tickets(freeze_dir, [case])
    answer_path = freeze_dir / dc.ANSWER_FREEZE_FILENAME
    answer = json.loads(answer_path.read_text(encoding="utf-8"))
    answer["human_answer_bank_sha256"] = "0" * 64
    answer_path.write_text(json.dumps(answer), encoding="utf-8")
    result = dq.execute_closed_query(
        _query(),
        [_fact("FACT-ONE")],
        material_complete_through_chapter=3,
    )
    with pytest.raises(dq.DUseQueryError, match="答案冻结票"):
        dq.score_x10_x11_metrics(
            [case],
            [result],
            freeze_dir=freeze_dir,
        )


def _valid_single_score_fixture(
    tmp_path: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]], Path]:
    cases = [
        _human_case(
            "Q1",
            kind="UNIQUE_ANSWER",
            expected_status="FOUND",
            expected_fact_ids=["FACT-ONE"],
        )
    ]
    results = [
        dq.execute_closed_query(
            _query(),
            [_fact("FACT-ONE")],
            material_complete_through_chapter=3,
        )
    ]
    freeze_dir = tmp_path / "freeze"
    _write_valid_freeze_tickets(freeze_dir, cases)
    return cases, results, freeze_dir


def test_result_query_wrong_cutoff_chapter_is_rejected(
    tmp_path: Path,
) -> None:
    cases, results, freeze_dir = _valid_single_score_fixture(tmp_path)
    results[0]["query"] = _query(chapter=4)
    with pytest.raises(dq.DUseQueryError, match="不逐字一致"):
        dq.score_x10_x11_metrics(
            cases,
            results,
            freeze_dir=freeze_dir,
        )


def test_hidden_future_fact_without_evidence_is_rejected(
    tmp_path: Path,
) -> None:
    cases, results, freeze_dir = _valid_single_score_fixture(tmp_path)
    results[0]["fact_ids"].append("FACT-N-PLUS-1-CANARY")
    with pytest.raises(dq.DUseQueryError, match="一一完全相等"):
        dq.score_x10_x11_metrics(
            cases,
            results,
            freeze_dir=freeze_dir,
        )


@pytest.mark.parametrize("mode", ["duplicate", "mismatch"])
def test_duplicate_or_mismatched_evidence_is_rejected(
    tmp_path: Path,
    mode: str,
) -> None:
    cases, results, freeze_dir = _valid_single_score_fixture(tmp_path)
    if mode == "duplicate":
        results[0]["evidence"].append(dict(results[0]["evidence"][0]))
        pattern = "重复"
    else:
        results[0]["evidence"][0]["fact_id"] = "FACT-OTHER"
        pattern = "一一完全相等"
    with pytest.raises(dq.DUseQueryError, match=pattern):
        dq.score_x10_x11_metrics(
            cases,
            results,
            freeze_dir=freeze_dir,
        )


def test_non_found_cannot_carry_hidden_fact_or_evidence(
    tmp_path: Path,
) -> None:
    cases = [
        _human_case(
            "Q1",
            kind="EXPLICIT_NO_ANSWER",
            expected_status="NOT_FOUND",
            expected_fact_ids=[],
        )
    ]
    result = dq.execute_closed_query(
        _query(),
        [],
        material_complete_through_chapter=3,
    )
    result["fact_ids"] = ["FACT-HIDDEN"]
    freeze_dir = tmp_path / "freeze"
    _write_valid_freeze_tickets(freeze_dir, cases)
    with pytest.raises(dq.DUseQueryError, match="非 FOUND"):
        dq.score_x10_x11_metrics(
            cases,
            [result],
            freeze_dir=freeze_dir,
        )


def test_current_blank_artifacts_can_never_authorize_formal_score() -> None:
    case = _human_case(
        "Q1",
        kind="UNIQUE_ANSWER",
        expected_status="FOUND",
        expected_fact_ids=["FACT-ONE"],
    )
    result = dq.execute_closed_query(
        _query(),
        [_fact("FACT-ONE")],
        material_complete_through_chapter=3,
    )
    with pytest.raises(dq.DUseQueryError, match="冻结票不存在"):
        dq.score_x10_x11_metrics(
            [case],
            [result],
            freeze_dir=dc.DEFAULT_OUTPUT_DIR,
        )


def test_natural_language_execution_declares_two_scorecards() -> None:
    result = dq.execute_natural_language_query(
        "截至第3章，ENTITY-TEST-01的state.test是什么？",
        [_fact("FACT-ONE")],
        material_complete_through_chapter=3,
    )
    assert result["parser_output"]["query_type"] == ("CHARACTER_STATE_AT_CHAPTER_END")
    assert result["query_result"]["status"] == "FOUND"
    assert result["scorecards_must_remain_separate"] is True


def _question_family_candidate(
    family: str = "RESEARCH_RECENT_RESOURCE_DECREASE",
) -> dict[str, object]:
    return {
        "family_id": "DUSE-C11-FAMILY-01",
        "family_group": ("RESEARCH" if family.startswith("RESEARCH_") else "PRODUCT"),
        "question_family": family,
        "question_text": dc.HUMAN_REQUIRED,
        "executable_query_type": None,
        "case_kind": None,
        "expected_answer": None,
        "human_authored": False,
        "review_status": "HUMAN_REQUIRED",
        "formal_question": False,
        "formal_answer": False,
        "scoreable": False,
    }


@pytest.mark.parametrize("family", dc.QUESTION_FAMILIES)
def test_c11_question_families_validate_as_nonexecutable_dimension(
    family: str,
) -> None:
    candidate = _question_family_candidate(family)
    assert dq.validate_question_family_candidate(candidate) == candidate
    with pytest.raises(dq.DUseQueryError, match="禁止假执行"):
        dq.execute_question_family_candidate(candidate)


def test_question_family_cannot_smuggle_query_type_or_case_kind() -> None:
    candidate = _question_family_candidate()
    candidate["executable_query_type"] = "CHARACTER_STATE_AT_CHAPTER_END"
    candidate["case_kind"] = "UNIQUE_ANSWER"
    with pytest.raises(dq.DUseQueryError, match="HUMAN_REQUIRED"):
        dq.validate_question_family_candidate(candidate)


def _missing_field_candidate(
    *,
    kind: str,
    bucket_name: str | None,
    external_ref: str | None,
) -> dict[str, object]:
    return {
        "case_id": "DUSE-C11-DIAG-01",
        "bucket_reference": {
            "reference_kind": kind,
            "bucket_name": bucket_name,
            "external_bucket_ref": external_ref,
        },
        "diagnostic_reason": "等待本地人员核准的诊断依据",
        "review_status": "HUMAN_REQUIRED",
        "formal_diagnostic": False,
    }


@pytest.mark.parametrize("bucket_name", dc.NEW_MISSING_FIELD_BUCKETS)
def test_two_new_missing_field_buckets_are_candidate_names_only(
    bucket_name: str,
) -> None:
    row = _missing_field_candidate(
        kind="NAMED_C11_CANDIDATE",
        bucket_name=bucket_name,
        external_ref=None,
    )
    assert (
        dq.validate_missing_field_diagnostic_candidate(
            row,
            legacy_bucket_catalog_status="LEGACY_NAMES_MISSING",
        )
        == row
    )
    assert row["formal_diagnostic"] is False
    assert row["review_status"] == "HUMAN_REQUIRED"


def test_legacy_bucket_reference_is_blocked_without_verified_catalog() -> None:
    row = _missing_field_candidate(
        kind="OPAQUE_EXTERNAL_LEGACY",
        bucket_name=None,
        external_ref="external-catalog://bucket/opaque-7",
    )
    with pytest.raises(dq.DUseQueryError, match="权威目录缺失"):
        dq.validate_missing_field_diagnostic_candidate(
            row,
            legacy_bucket_catalog_status="LEGACY_NAMES_MISSING",
        )


def test_verified_legacy_bucket_uses_opaque_ref_not_local_name() -> None:
    external_ref = "external-catalog://bucket/opaque-7"
    row = _missing_field_candidate(
        kind="OPAQUE_EXTERNAL_LEGACY",
        bucket_name=None,
        external_ref=external_ref,
    )
    assert (
        dq.validate_missing_field_diagnostic_candidate(
            row,
            legacy_bucket_catalog_status="AVAILABLE_AND_VERIFIED",
            verified_legacy_bucket_refs=[external_ref],
        )
        == row
    )
    row["bucket_reference"]["bucket_name"] = "INVENTED_LEGACY_NAME"
    with pytest.raises(dq.DUseQueryError, match="不得在本地补写"):
        dq.validate_missing_field_diagnostic_candidate(
            row,
            legacy_bucket_catalog_status="AVAILABLE_AND_VERIFIED",
            verified_legacy_bucket_refs=[external_ref],
        )

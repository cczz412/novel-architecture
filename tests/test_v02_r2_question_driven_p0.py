from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.V02_R2_question_driven_retrieval_p0_20260726 import (
    v02_r2_p0 as p0,
)


REPO = Path(__file__).resolve().parents[1]


def _answer(
    *,
    question_id: str = "Q1",
    status: str = "ANSWER",
    claims: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    if claims is None:
        claims = [
            {
                "claim_id": "C1",
                "head_ids": ["H1"],
                "statement": "人物已经离开。",
                "source_ids": ["S1"],
            }
        ]
    return {
        "schema_version": p0.ANSWER_CONTRACT_SCHEMA_VERSION,
        "question_id": question_id,
        "status": status,
        "claims": claims,
        "abstention_reason": "材料不足" if status == "ABSTAIN" else None,
    }


def _gold(answerability: str = "ANSWERABLE") -> dict[str, object]:
    return {
        "question_id": "Q1",
        "answerability": answerability,
        "semantic_truth_status": "HUMAN_REVIEWED",
        "required_heads": [
            {
                "head_id": "H1",
                "semantic_statement": "人物已经离开。",
                "source_id_groups": [["S1"]],
                "required_qualifiers": {},
                "semantic_truth_status": "HUMAN_REVIEWED",
            }
        ],
    }


def _adjudication(
    *,
    gold: dict[str, object] | None = None,
    answer: dict[str, object] | None = None,
    correct: bool = True,
    supported: bool = True,
    qualifiers: bool = True,
    hard_errors: list[str] | None = None,
    false_premise_corrected: bool = False,
) -> dict[str, object]:
    gold = gold or _gold()
    answer = answer or _answer()
    return {
        "schema_version": p0.ADJUDICATION_SCHEMA_VERSION,
        "question_id": answer["question_id"],
        "gold_cell_payload_sha256": p0.sha256_bytes(
            p0.canonical_bytes(gold)
        ),
        "answer_payload_sha256": p0.sha256_bytes(
            p0.canonical_bytes(answer)
        ),
        "adjudicator_ticket_id": "TEST-TICKET-001",
        "adjudicator_ticket_receipt_sha256": "a" * 64,
        "head_checks": [
            {
                "head_id": "H1",
                "fact_correct": correct,
                "evidence_supports": supported,
                "qualifiers_correct": qualifiers,
            }
        ],
        "hard_error_codes": hard_errors or [],
        "false_premise_corrected": false_premise_corrected,
    }


def _trusted_registry_files(
    tmp_path: Path,
    *,
    adjudication: dict[str, object] | None = None,
    ticket_id: str = "TEST-TICKET-001",
    adjudicator_executor_id: str = "TEST-ADJUDICATOR",
) -> dict[str, object]:
    isolation_root = tmp_path / "adjudication"
    receipt_path = isolation_root / "tickets/test-ticket.json"
    p0.write_json(
        receipt_path,
        {
            "schema_version": p0.ADJUDICATOR_TICKET_SCHEMA_VERSION,
            "ticket_id": ticket_id,
            "issuer": "TEST-INDEPENDENT-ADJUDICATOR",
            "adjudicator_executor_id": adjudicator_executor_id,
            "scoring_executor_id": "TEST-SCORER",
            "independence_basis": "SEPARATE_TEST_FIXTURE",
        },
    )
    receipt_sha256 = p0.sha256_file(receipt_path)
    if adjudication is not None:
        adjudication["adjudicator_ticket_receipt_sha256"] = receipt_sha256
    registry_path = isolation_root / "registry.json"
    p0.write_json(
        registry_path,
        {
            "schema_version": p0.ADJUDICATOR_REGISTRY_SCHEMA_VERSION,
            "scoring_executor_id": "TEST-SCORER",
            "tickets": [
                {
                    "ticket_id": ticket_id,
                    "receipt_sha256": receipt_sha256,
                    "issuer": "TEST-INDEPENDENT-ADJUDICATOR",
                    "receipt_path": "tickets/test-ticket.json",
                    "independence_basis": "SEPARATE_TEST_FIXTURE",
                }
            ],
        },
    )
    return {
        "adjudicator_registry_path": registry_path,
        "trusted_adjudicator_registry_sha256": p0.sha256_file(registry_path),
        "adjudicator_isolation_root": isolation_root,
        "scoring_executor_id": "TEST-SCORER",
    }


def test_sentence_v2_consumes_closing_quote_before_boundary() -> None:
    text = "他说：“已经结束了。”\n下一句开始。\n"
    spans = p0._sentence_spans_v2(text, base_offset=0)
    assert [row[2] for row in spans] == [
        "他说：“已经结束了。”\n",
        "下一句开始。\n",
    ]
    assert all(p0._content_without_closers(row[2]) for row in spans)


def test_three_source_catalogs_rebuild_and_have_no_isolated_closer() -> None:
    catalog_dir = (
        REPO / "runs/V02_C15_pipeline_v1_r01_20260726/s0/source_catalogs"
    )
    paths = sorted(catalog_dir.glob("*.json"))
    assert len(paths) == 3
    for path in paths:
        old = json.loads(path.read_text(encoding="utf-8"))
        catalog = p0.build_source_catalog_v2(
            source_text=old["source_text"],
            source_id=old["source_id"],
            chapter=old["chapter"],
            run_id="TEST",
            legacy_catalog=old,
        )
        receipt = p0.verify_source_catalog_v2(catalog)
        assert receipt["status"] == "PASS"
        assert receipt["isolated_closer_sentence_count"] == 0


def test_all_lockbox_source_ids_keep_their_legacy_namespace() -> None:
    catalog_dir = (
        REPO / "runs/V02_C15_pipeline_v1_r01_20260726/s0/source_catalogs"
    )
    old_catalogs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(catalog_dir.glob("*.json"))
    ]
    new_catalogs = [
        p0.build_source_catalog_v2(
            source_text=old["source_text"],
            source_id=old["source_id"],
            chapter=old["chapter"],
            run_id="TEST",
            legacy_catalog=old,
        )
        for old in old_catalogs
    ]
    lockbox = json.loads(
        (
            REPO
            / "runs/V02_R1_route_comparison_r04_20260726/frozen/"
            "question_reference_map.lockbox.json"
        ).read_text(encoding="utf-8")
    )
    receipt = p0.verify_lockbox_source_id_compatibility(
        lockbox=lockbox,
        catalogs=new_catalogs,
    )
    assert receipt["required_source_id_count"] == 70
    assert receipt["matched_source_id_count"] == 70
    assert receipt["missing_source_id_count"] == 0


def test_all_legacy_source_ids_resolve_to_one_complete_v2_sentence() -> None:
    catalog_dir = (
        REPO / "runs/V02_C15_pipeline_v1_r01_20260726/s0/source_catalogs"
    )
    old_catalogs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(catalog_dir.glob("*.json"))
    ]
    new_catalogs = [
        p0.build_source_catalog_v2(
            source_text=old["source_text"],
            source_id=old["source_id"],
            chapter=old["chapter"],
            run_id="TEST",
            legacy_catalog=old,
        )
        for old in old_catalogs
    ]
    source_ids = sorted(
        {
            row["sentence_id"]
            for catalog in old_catalogs
            for row in catalog["sentences"]
        }
    )
    pure_closer_ids = {
        row["sentence_id"]
        for catalog in old_catalogs
        for row in catalog["sentences"]
        if not p0._content_without_closers(row["original_text"])
    }
    rows = [
        p0.resolve_legacy_source_row(
            catalogs=new_catalogs,
            legacy_source_id=source_id,
        )
        for source_id in source_ids
    ]
    pure_closer_rows = [
        p0.resolve_legacy_source_row(
            catalogs=new_catalogs,
            legacy_source_id=source_id,
        )
        for source_id in sorted(pure_closer_ids)
    ]
    assert len(rows) == 405
    assert len(pure_closer_rows) == 73
    assert all(p0._content_without_closers(row["original_text"]) for row in rows)
    assert all(
        p0._content_without_closers(row["original_text"])
        for row in pure_closer_rows
    )
    receipt = p0.verify_all_legacy_source_id_resolution(
        legacy_catalogs=old_catalogs,
        new_catalogs=new_catalogs,
    )
    assert receipt["resolved_unique_count"] == 405
    assert receipt["pure_closer_resolved_to_content_count"] == 73


def test_catalog_verifier_rejects_tampered_hashes() -> None:
    path = next(
        iter(
            sorted(
                (
                    REPO
                    / "runs/V02_C15_pipeline_v1_r01_20260726/s0/source_catalogs"
                ).glob("*.json")
            )
        )
    )
    old = json.loads(path.read_text(encoding="utf-8"))
    catalog = p0.build_source_catalog_v2(
        source_text=old["source_text"],
        source_id=old["source_id"],
        chapter=old["chapter"],
        run_id="TEST",
        legacy_catalog=old,
    )
    catalog["source_body_sha256"] = "0" * 64
    with pytest.raises(p0.R2P0Error, match="SOURCE_BODY_SHA_MISMATCH"):
        p0.verify_source_catalog_v2(catalog)


def test_model_workspace_preflight_rejects_gold_payload(tmp_path: Path) -> None:
    workspace = tmp_path / "model_workspace"
    (workspace / "contracts").mkdir(parents=True)
    leak_path = workspace / "contracts" / "leak.json"
    p0.write_json(
        leak_path,
        {
            "semantic_statement": "不该进入模型工作区",
        },
    )
    manifest = p0.artifact_manifest(
        root=workspace,
        schema_version="TEST",
    )
    p0.write_json(workspace / "manifest.json", manifest)
    with pytest.raises(p0.R2P0Error, match="MODEL_WORKSPACE_GOLD_LEAK"):
        p0.verify_model_workspace_isolation(workspace)


def test_model_workspace_rejects_symlink_and_untrusted_manifest_drift(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.json"
    p0.write_json(outside, {"safe": "outside"})
    linked_workspace = tmp_path / "linked_workspace"
    linked_workspace.mkdir()
    (linked_workspace / "outside.json").symlink_to(outside)
    with pytest.raises(
        p0.R2P0Error,
        match="ARTIFACT_MANIFEST_SYMLINK_FORBIDDEN",
    ):
        p0.artifact_manifest(
            root=linked_workspace,
            schema_version="TEST",
        )

    workspace = tmp_path / "workspace"
    p0.write_json(workspace / "safe.json", {"safe": "v1"})
    manifest = p0.artifact_manifest(
        root=workspace,
        schema_version="TEST",
    )
    p0.write_json(workspace / "manifest.json", manifest)
    trusted_sha256 = p0.sha256_file(workspace / "manifest.json")
    receipt = p0.verify_model_workspace_isolation(
        workspace,
        trusted_manifest_file_sha256=trusted_sha256,
    )
    assert receipt["trusted_manifest_binding_checked"] is True

    p0.write_json(workspace / "safe.json", {"safe": "v2"})
    p0.write_json(
        workspace / "manifest.json",
        p0.artifact_manifest(root=workspace, schema_version="TEST"),
    )
    with pytest.raises(
        p0.R2P0Error,
        match="MODEL_WORKSPACE_TRUSTED_MANIFEST_SHA_MISMATCH",
    ):
        p0.verify_model_workspace_isolation(
            workspace,
            trusted_manifest_file_sha256=trusted_sha256,
        )


def test_terminal_freeze_gate_rejects_nulls_and_accepts_complete_snapshot() -> None:
    with pytest.raises(
        p0.R2P0Error,
        match="TERMINAL_FREEZE_SHA_MISSING_OR_INVALID",
    ):
        p0.validate_terminal_freeze_contract(p0.TERMINAL_ISOLATION_CONTRACT)

    frozen = json.loads(json.dumps(p0.TERMINAL_ISOLATION_CONTRACT))
    for field in (
        "question_set_sha256",
        "gold_lockbox_sha256",
        "scorer_sha256",
        "model_workspace_manifest_sha256",
        "adjudicator_ticket_registry_sha256",
        "retrieval_policy_sha256",
        "prompt_sha256",
        "model_identity_receipt_sha256",
        "retry_policy_sha256",
    ):
        frozen["freeze_required"][field] = "a" * 64
    frozen["freeze_required"]["route_manifests"] = ["b" * 64]
    receipt = p0.validate_terminal_freeze_contract(frozen)
    assert receipt == {
        "status": "PASS",
        "frozen_sha_field_count": 9,
        "route_manifest_count": 1,
    }


def test_open_cells_migrate_to_unresolved_and_never_auto_score() -> None:
    lockbox_path = (
        REPO
        / "runs/V02_R1_route_comparison_r04_20260726/frozen/"
        "question_reference_map.lockbox.json"
    )
    lockbox = json.loads(lockbox_path.read_text(encoding="utf-8"))
    migrated = p0.migrate_r1_lockbox_to_dev_gold_v2(lockbox)
    unresolved = [
        row
        for row in migrated["cells"]
        if row["answerability"] == "UNRESOLVED_NEEDS_HUMAN"
    ]
    assert len(unresolved) == 2
    assert migrated["migration_summary"]["legacy_open_auto_score_allowed"] is False
    result = p0.score_question(
        gold=unresolved[0],
        answer=_answer(question_id=unresolved[0]["question_id"]),
        adjudication={
            **_adjudication(),
            "question_id": unresolved[0]["question_id"],
        },
    )
    assert result["result"] == "UNSCORABLE_GOLD_INCOMPLETE"
    assert result["full_supported"] is False


def test_formal_gold_claims_fill_all_answered_dev_cells() -> None:
    lockbox_path = (
        REPO
        / "runs/V02_R1_route_comparison_r04_20260726/frozen/"
        "question_reference_map.lockbox.json"
    )
    lockbox = json.loads(lockbox_path.read_text(encoding="utf-8"))
    formal_parts, receipts = p0.load_formal_gold_parts(
        repo=REPO,
        case_ids=[cell["case_id"] for cell in lockbox["cells"]],
    )
    migrated = p0.migrate_r1_lockbox_to_dev_gold_v2(
        lockbox,
        formal_gold_parts=formal_parts,
    )
    assert len(receipts) == 3
    assert migrated["migration_summary"]["scoreable_semantic_cells"] == 28
    assert migrated["migration_summary"]["needs_human_semantic_answer"] == 0
    for cell in migrated["cells"]:
        if cell["answerability"] != "ANSWERABLE":
            continue
        assert cell["semantic_truth_status"] == "FORMAL_GOLD_CURRENT_IMPORTED"
        assert all(head["semantic_statement"] for head in cell["required_heads"])
        assert all(head["gold_provenance"] for head in cell["required_heads"])


def test_source_id_presence_cannot_self_sign_semantic_success(
    tmp_path: Path,
) -> None:
    adjudication = _adjudication(
        correct=False,
        supported=False,
        hard_errors=["EVIDENCE_NOT_SUPPORT"],
    )
    result = p0.score_question(
        gold=_gold(),
        answer=_answer(),
        adjudication=adjudication,
        **_trusted_registry_files(tmp_path, adjudication=adjudication),
    )
    assert result["result"] == "EVIDENCE_NOT_SUPPORT"
    assert result["full_supported"] is False
    assert result["semantic_truth_verified_by_program"] is False


@pytest.mark.parametrize(
    (
        "answerability",
        "answer_status",
        "correct",
        "supported",
        "qualifiers",
        "false_premise_corrected",
        "expected",
    ),
    [
        ("ANSWERABLE", "ANSWER", True, True, True, False, "FULL_SUPPORTED"),
        (
            "ANSWERABLE",
            "ANSWER",
            True,
            True,
            False,
            False,
            "QUALIFIER_WRONG",
        ),
        (
            "ANSWERABLE",
            "ABSTAIN",
            False,
            False,
            True,
            False,
            "WRONG_ABSTAIN",
        ),
        (
            "UNANSWERABLE",
            "ABSTAIN",
            False,
            False,
            True,
            False,
            "CORRECT_ABSTAIN",
        ),
        (
            "UNANSWERABLE",
            "ANSWER",
            True,
            True,
            True,
            False,
            "HALLUCINATION",
        ),
        (
            "FALSE_PREMISE",
            "ANSWER",
            True,
            True,
            True,
            True,
            "FALSE_PREMISE_CORRECTED",
        ),
        (
            "FALSE_PREMISE",
            "ANSWER",
            True,
            True,
            True,
            False,
            "FALSE_PREMISE_ACCEPTED",
        ),
    ],
)
def test_question_level_result_classes(
    tmp_path: Path,
    answerability: str,
    answer_status: str,
    correct: bool,
    supported: bool,
    qualifiers: bool,
    false_premise_corrected: bool,
    expected: str,
) -> None:
    gold = _gold(answerability)
    answer = _answer(
        status=answer_status,
        claims=[] if answer_status == "ABSTAIN" else None,
    )
    adjudication = _adjudication(
        gold=gold,
        answer=answer,
        correct=correct,
        supported=supported,
        qualifiers=qualifiers,
        false_premise_corrected=false_premise_corrected,
    )
    result = p0.score_question(
        gold=gold,
        answer=answer,
        adjudication=adjudication,
        **_trusted_registry_files(tmp_path, adjudication=adjudication),
    )
    assert result["result"] == expected


def test_model_quote_is_rejected() -> None:
    answer = _answer()
    answer["claims"][0]["quote"] = "不准让模型手抄"
    with pytest.raises(p0.R2P0Error, match="ANSWER_CLAIM_FIELDS_INVALID"):
        p0.validate_answer_contract(answer)


def test_wrong_question_cannot_use_another_gold_cell() -> None:
    gold = _gold()
    answer = _answer(question_id="Q2")
    adjudication = _adjudication(gold=gold, answer=answer)
    with pytest.raises(p0.R2P0Error, match="ANSWER_GOLD_QUESTION_ID_MISMATCH"):
        p0.score_question(
            gold=gold,
            answer=answer,
            adjudication=adjudication,
        )


def test_answer_head_and_source_lists_are_strict_and_gold_scoped() -> None:
    answer = _answer()
    answer["claims"][0]["head_ids"] = "H1"
    with pytest.raises(p0.R2P0Error, match="ANSWER_HEAD_IDS_NOT_NONEMPTY_LIST"):
        p0.validate_answer_contract(answer)

    gold = _gold()
    answer = _answer()
    answer["claims"][0]["source_ids"] = ["S2"]
    with pytest.raises(p0.R2P0Error, match="ANSWER_SOURCE_ID_UNAUTHORIZED"):
        p0.validate_answer_contract(answer, gold=gold)


def test_adjudication_rejects_non_bool_duplicate_and_unknown_heads(
    tmp_path: Path,
) -> None:
    gold = _gold()
    answer = _answer()
    adjudication = _adjudication(gold=gold, answer=answer)
    adjudication["head_checks"][0]["fact_correct"] = "false"
    with pytest.raises(p0.R2P0Error, match="FACT_CORRECT_NOT_BOOL"):
        p0.score_question(
            gold=gold,
            answer=answer,
            adjudication=adjudication,
            **_trusted_registry_files(tmp_path, adjudication=adjudication),
        )

    adjudication = _adjudication(gold=gold, answer=answer)
    adjudication["head_checks"].append(dict(adjudication["head_checks"][0]))
    with pytest.raises(p0.R2P0Error, match="HEAD_ID_DUPLICATED"):
        p0.score_question(
            gold=gold,
            answer=answer,
            adjudication=adjudication,
            **_trusted_registry_files(tmp_path, adjudication=adjudication),
        )

    adjudication = _adjudication(gold=gold, answer=answer)
    adjudication["head_checks"][0]["head_id"] = "H-UNKNOWN"
    with pytest.raises(p0.R2P0Error, match="HEAD_ID_UNAUTHORIZED"):
        p0.score_question(
            gold=gold,
            answer=answer,
            adjudication=adjudication,
            **_trusted_registry_files(tmp_path, adjudication=adjudication),
        )


def test_score_rejects_self_declared_or_mismatched_adjudicator_ticket(
    tmp_path: Path,
) -> None:
    gold = _gold()
    answer = _answer()
    adjudication = _adjudication(gold=gold, answer=answer)
    with pytest.raises(
        p0.R2P0Error,
        match="TRUSTED_ADJUDICATOR_REGISTRY_REQUIRED",
    ):
        p0.score_question(
            gold=gold,
            answer=answer,
            adjudication=adjudication,
        )

    with pytest.raises(
        p0.R2P0Error,
        match="ADJUDICATOR_REGISTRY_FILE_SHA_MISMATCH",
    ):
        trusted = _trusted_registry_files(tmp_path, adjudication=adjudication)
        trusted["trusted_adjudicator_registry_sha256"] = "b" * 64
        p0.score_question(
            gold=gold,
            answer=answer,
            adjudication=adjudication,
            **trusted,
        )

    with pytest.raises(
        p0.R2P0Error,
        match="ADJUDICATOR_TICKET_NOT_INDEPENDENT",
    ):
        p0.score_question(
            gold=gold,
            answer=answer,
            adjudication=adjudication,
            **_trusted_registry_files(
                tmp_path / "same-executor",
                adjudication=adjudication,
                adjudicator_executor_id="TEST-SCORER",
            ),
        )


@pytest.mark.parametrize(
    ("hard_error", "expected"),
    sorted(p0.HARD_ERROR_RESULT_MAP.items()),
)
def test_every_hard_error_has_a_frozen_result_mapping(
    hard_error: str,
    expected: str,
) -> None:
    assert p0._hard_error_result([hard_error]) == expected


def test_recall_curve_is_diagnostic_and_monotonic() -> None:
    old_catalog_dir = (
        REPO / "runs/V02_C15_pipeline_v1_r01_20260726/s0/source_catalogs"
    )
    old_catalogs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(old_catalog_dir.glob("*.json"))
    ]
    new_catalogs = [
        p0.build_source_catalog_v2(
            source_text=old["source_text"],
            source_id=old["source_id"],
            chapter=old["chapter"],
            run_id="TEST",
            legacy_catalog=old,
        )
        for old in old_catalogs
    ]
    lockbox = json.loads(
        (
            REPO
            / "runs/V02_R1_route_comparison_r04_20260726/frozen/"
            "question_reference_map.lockbox.json"
        ).read_text(encoding="utf-8")
    )
    gold = p0.migrate_r1_lockbox_to_dev_gold_v2(lockbox)
    index = p0.build_sparse_index(new_catalogs)
    curve = p0.build_recall_curve(
        gold_v2=gold,
        index=index,
        catalogs=new_catalogs,
        k_values=(1, 3, 5),
    )
    recalls = [row["full_question_recall"] for row in curve["points"]]
    chars = [row["candidate_material_chars_total"] for row in curve["points"]]
    assert recalls == sorted(recalls)
    assert chars == sorted(chars)
    assert curve["diagnostic_only"] is True


def test_p0_builder_emits_zero_api_candidate(tmp_path: Path) -> None:
    output_dir = tmp_path / "r2-p0"
    receipt = p0.build_p0(repo=REPO, output_dir=output_dir)
    assert receipt["model_api_calls"] == 0
    assert receipt["network_calls"] == 0
    assert receipt["gold_migration"]["scoreable_semantic_cells"] == 28
    assert receipt["gold_migration"]["unresolved_needs_human_answerability"] == 2
    assert receipt["p0_status"].endswith("28_SCOREABLE_2_OPEN_UNRESOLVED")
    assert receipt["model_workspace_isolation_preflight"]["status"] == "PASS"
    assert (output_dir / "manifest.json").is_file()
    assert (output_dir / "retrieval/recall_curve.json").is_file()
    assert (
        output_dir / "scoring_lockbox/question_gold_dev_v2.json"
    ).is_file()
    assert not (
        output_dir / "model_workspace/scoring_lockbox"
    ).exists()

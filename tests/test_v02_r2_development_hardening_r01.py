from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.V02_R2_development_hardening_r01_20260727 import (
    r2_dev_hardening as hardening,
)


def _request() -> dict[str, object]:
    return {
        "schema_version": hardening.ROUTE_REQUEST_SCHEMA,
        "run_id": "DEV-R2-A1A-0001",
        "route_id": "A1A-PROGRAM-PLAN",
        "question_id": "Q01",
        "request_heads": [
            {
                "request_head_id": "RH-Q01-01",
                "question_span": "人物为何离开？",
                "query_terms": ["人物", "离开"],
            }
        ],
        "evidence_window_source_ids": ["B01-U0033-S0001", "B01-U0033-S0002"],
        "source_catalog_receipt_sha256": "a" * 64,
    }


def _answer() -> dict[str, object]:
    return {
        "schema_version": hardening.ROUTE_ANSWER_SCHEMA,
        "run_id": "DEV-R2-A1A-0001",
        "route_id": "A1A-PROGRAM-PLAN",
        "question_id": "Q01",
        "status": "ANSWER",
        "claims": [
            {
                "claim_id": "C01",
                "request_head_ids": ["RH-Q01-01"],
                "statement": "人物已经离开。",
                "source_ids": ["B01-U0033-S0001"],
            }
        ],
        "abstention_reason": None,
    }


def test_route_contract_uses_request_namespace_and_evidence_window() -> None:
    request = _request()
    answer = _answer()
    assert hardening.validate_route_request(request)["status"] == "PASS"
    assert hardening.validate_route_answer(answer, request=request)["status"] == "PASS"

    request["request_heads"][0]["request_head_id"] = "Z74B-B01-U0033-A01"
    with pytest.raises(
        hardening.R2HardeningError,
        match="REQUEST_HEAD_NAMESPACE_INVALID",
    ):
        hardening.validate_route_request(request)

    answer = _answer()
    answer["claims"][0]["source_ids"] = ["B01-U0033-S9999"]
    with pytest.raises(
        hardening.R2HardeningError,
        match="ROUTE_ANSWER_SOURCE_OUTSIDE_WINDOW",
    ):
        hardening.validate_route_answer(answer, request=_request())


def test_hidden_gold_fields_and_strings_are_rejected() -> None:
    request = _request()
    request["request_heads"][0]["question_span"] = "required_heads"
    with pytest.raises(
        hardening.R2HardeningError,
        match="HIDDEN_MATERIAL_FORBIDDEN",
    ):
        hardening.validate_route_request(request)


def test_full_answer_must_cover_every_request_head() -> None:
    request = _request()
    request["request_heads"].append(
        {
            "request_head_id": "RH-Q01-02",
            "question_span": "人物处于什么状态？",
            "query_terms": ["人物", "状态"],
        }
    )
    with pytest.raises(
        hardening.R2HardeningError,
        match="ROUTE_ANSWER_HEAD_COVERAGE_INCOMPLETE",
    ):
        hardening.validate_route_answer(_answer(), request=request)


def test_conjunctive_evidence_groups_require_every_group() -> None:
    groups = [["S0111"], ["S0113", "S0114"]]
    assert not hardening.evidence_groups_satisfied(
        cited_source_ids=["S0111"],
        source_id_groups=groups,
    )
    assert hardening.evidence_groups_satisfied(
        cited_source_ids=["S0111", "S0114"],
        source_id_groups=groups,
    )


def test_source_identity_binds_source_chapter_body_and_legacy_bytes() -> None:
    source_text = "正文。\n"
    legacy_bytes = b'{"legacy":true}\n'
    catalog_payload_bytes = b'{"source_id":"B01-U0033"}\n'
    receipt = {
        "schema_version": hardening.SOURCE_IDENTITY_SCHEMA,
        "source_id": "B01-U0033",
        "chapter": 33,
        "source_body_sha256": hardening.sha256_bytes(source_text.encode()),
        "legacy_catalog_sha256": hardening.sha256_bytes(legacy_bytes),
        "catalog_payload_sha256": hardening.sha256_bytes(catalog_payload_bytes),
    }
    assert hardening.validate_source_identity(
        receipt,
        expected_source_id="B01-U0033",
        expected_chapter=33,
        source_text=source_text,
        legacy_catalog_bytes=legacy_bytes,
        catalog_payload_bytes=catalog_payload_bytes,
    )["status"] == "PASS"
    receipt["source_id"] = "B99-U0033"
    with pytest.raises(
        hardening.R2HardeningError,
        match="SOURCE_IDENTITY_SOURCE_ID_MISMATCH",
    ):
        hardening.validate_source_identity(
            receipt,
            expected_source_id="B01-U0033",
            expected_chapter=33,
            source_text=source_text,
            legacy_catalog_bytes=legacy_bytes,
            catalog_payload_bytes=catalog_payload_bytes,
        )

    receipt["source_id"] = "B01-U0033"
    with pytest.raises(
        hardening.R2HardeningError,
        match="SOURCE_IDENTITY_CATALOG_PAYLOAD_SHA_MISMATCH",
    ):
        hardening.validate_source_identity(
            receipt,
            expected_source_id="B01-U0033",
            expected_chapter=33,
            source_text=source_text,
            legacy_catalog_bytes=legacy_bytes,
            catalog_payload_bytes=b'{"source_id":"tampered"}\n',
        )


def _manifest_for(workspace: Path, *, issuer: str = "EXTERNAL_PREREGISTERED") -> dict:
    files = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        files.append(
            {
                "path": path.relative_to(workspace).as_posix(),
                "artifact_type": (
                    "QUESTION_SET"
                    if path.relative_to(workspace).as_posix() == "question_set.json"
                    else "SOURCE_CATALOG"
                ),
                "bytes": path.stat().st_size,
                "sha256": hardening.sha256_file(path),
            }
        )
    return {
        "schema_version": hardening.ROUTE_WORKSPACE_MANIFEST_SCHEMA,
        "issuer_type": issuer,
        "sealed_before_run": True,
        "files": files,
    }


def test_workspace_scans_non_json_and_refuses_self_declared_trust(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "question_set.json").write_text(
        '{"questions":[]}\n', encoding="utf-8"
    )
    catalog_dir = workspace / "source_catalog_v2"
    catalog_dir.mkdir()
    for index in range(3):
        (catalog_dir / f"B0{index + 1}.json").write_text(
            '{"sentences":[]}\n', encoding="utf-8"
        )
    manifest_path = tmp_path / "manifest.json"
    manifest = _manifest_for(workspace, issuer="SELF_DECLARED")
    manifest_path.write_bytes(hardening.canonical_bytes(manifest))
    with pytest.raises(
        hardening.R2HardeningError,
        match="ROUTE_WORKSPACE_MANIFEST_ISSUER_UNTRUSTED",
    ):
        hardening.verify_route_workspace(
            workspace,
            preregistered_manifest_path=manifest_path,
            expected_manifest_sha256=hardening.sha256_file(manifest_path),
        )

    (workspace / "question_set.json").write_text(
        '{"question_id":"Z74B-B01-A01"}\n', encoding="utf-8"
    )
    manifest = _manifest_for(workspace)
    manifest_path.write_bytes(hardening.canonical_bytes(manifest))
    with pytest.raises(
        hardening.R2HardeningError,
        match="HIDDEN_MATERIAL_FORBIDDEN",
    ):
        hardening.verify_route_workspace(
            workspace,
            preregistered_manifest_path=manifest_path,
            expected_manifest_sha256=hardening.sha256_file(manifest_path),
        )


def test_workspace_rejects_extra_self_signed_artifact(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "question_set.json").write_text("{}\n", encoding="utf-8")
    catalog_dir = workspace / "source_catalog_v2"
    catalog_dir.mkdir()
    for index in range(3):
        (catalog_dir / f"B0{index + 1}.json").write_text("{}\n", encoding="utf-8")
    (workspace / "Z74B-self-signed.json").write_text("{}\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(hardening.canonical_bytes(_manifest_for(workspace)))
    with pytest.raises(
        hardening.R2HardeningError,
        match="ROUTE_WORKSPACE_CATALOG_CONTRACT_INVALID",
    ):
        hardening.verify_route_workspace(
            workspace,
            preregistered_manifest_path=manifest_path,
            expected_manifest_sha256=hardening.sha256_file(manifest_path),
        )


def test_model_execution_gate_is_fail_closed_without_external_trust() -> None:
    with pytest.raises(
        hardening.R2HardeningError,
        match="MODEL_EXECUTION_BLOCKED_BY_WORKSPACE_TRUST",
    ):
        hardening.require_model_execution_allowed(
            workspace_receipt={"model_run_allowed": False},
            terminal_receipt={"terminal_run_allowed": False},
        )


def _ledger_bundle(tmp_path: Path) -> dict[str, object]:
    request = _request()
    request.update(
        {
            "run_id": "RUN-1",
            "route_id": "A1A",
            "question_id": "Q01",
            "evidence_window_source_ids": ["S1", "S2"],
        }
    )
    answer_payload = _answer()
    answer_payload.update(
        {"run_id": "RUN-1", "route_id": "A1A", "question_id": "Q01"}
    )
    answer_payload["claims"][0]["source_ids"] = ["S1"]
    ticket_receipt = {
        "schema_version": hardening.ADJUDICATOR_TICKET_SCHEMA,
        "ticket_id": "T1",
        "issuer": "EXTERNAL-TEST",
        "adjudicator_executor_id": "TEST-ADJUDICATOR",
        "scoring_executor_id": "TEST-SCORER",
        "independence_basis": "SEPARATE_EXECUTOR_AND_FROZEN_RECEIPT",
    }
    for name, value in {
        "route_manifest": {"route_id": "A1A"},
        "plan": {"question_id": "Q01"},
        "index_payload": {"source_ids": ["S1", "S2"]},
        "request": request,
        "raw_response": {"raw": "response"},
        "answer_payload": answer_payload,
        "ticket_receipt": ticket_receipt,
    }.items():
        (tmp_path / f"{name}.json").write_bytes(hardening.canonical_bytes(value))
    adjudication_payload = {
        "schema_version": hardening.LEDGER_ADJUDICATION_SCHEMA,
        "run_id": "RUN-1",
        "route_id": "A1A",
        "question_id": "Q01",
        "claim_id": "C1",
        "answer_payload_sha256": hardening.sha256_file(
            tmp_path / "answer_payload.json"
        ),
        "adjudicator_ticket_id": "T1",
        "adjudicator_ticket_receipt_sha256": hardening.sha256_file(
            tmp_path / "ticket_receipt.json"
        ),
        "source_ids": ["S1"],
        "evidence_supports": True,
    }
    (tmp_path / "adjudication_payload.json").write_bytes(
        hardening.canonical_bytes(adjudication_payload)
    )
    return {
        "schema_version": hardening.LEDGER_BUNDLE_SCHEMA,
        "run_id": "RUN-1",
        "route_id": "A1A",
        "question_id": "Q01",
        "scoring_executor_id": "TEST-SCORER",
        "retrieval": {
            "run_id": "RUN-1",
            "route_id": "A1A",
            "question_id": "Q01",
            "route_manifest_path": "route_manifest.json",
            "route_manifest_sha256": hardening.sha256_file(
                tmp_path / "route_manifest.json"
            ),
            "plan_path": "plan.json",
            "plan_sha256": hardening.sha256_file(tmp_path / "plan.json"),
            "index_payload_path": "index_payload.json",
            "index_payload_sha256": hardening.sha256_file(
                tmp_path / "index_payload.json"
            ),
            "ranked_windows": [
                {
                    "window_id": "W1",
                    "rank": 0,
                    "source_ids": ["S1", "S2"],
                    "char_count": 20,
                }
            ],
            "candidate_chars": 20,
            "elapsed_ms": 1,
        },
        "answer": {
            "run_id": "RUN-1",
            "route_id": "A1A",
            "question_id": "Q01",
            "request_path": "request.json",
            "request_sha256": hardening.sha256_file(tmp_path / "request.json"),
            "raw_response_path": "raw_response.json",
            "raw_response_sha256": hardening.sha256_file(
                tmp_path / "raw_response.json"
            ),
            "answer_payload_path": "answer_payload.json",
            "answer_payload_sha256": hardening.sha256_file(
                tmp_path / "answer_payload.json"
            ),
            "source_ids_used": ["S1"],
            "answer_executor_id": "TEST-ANSWERER",
            "usage": {"input_tokens": 2, "output_tokens": 3},
        },
        "support": {
            "run_id": "RUN-1",
            "route_id": "A1A",
            "question_id": "Q01",
            "claim_id": "C1",
            "source_ids": ["S1"],
            "adjudicator_ticket_id": "T1",
            "ticket_receipt_path": "ticket_receipt.json",
            "adjudicator_ticket_receipt_sha256": hardening.sha256_file(
                tmp_path / "ticket_receipt.json"
            ),
            "adjudication_payload_path": "adjudication_payload.json",
            "adjudication_payload_sha256": hardening.sha256_file(
                tmp_path / "adjudication_payload.json"
            ),
        },
    }


def test_ledger_rejects_negative_fake_hash_and_cross_ledger_sources(
    tmp_path: Path,
) -> None:
    bundle = _ledger_bundle(tmp_path)
    assert hardening.validate_ledger_bundle(
        bundle,
        artifact_root=tmp_path,
    )["total_tokens"] == 5

    bundle = _ledger_bundle(tmp_path)
    bundle["retrieval"]["candidate_chars"] = -1
    with pytest.raises(
        hardening.R2HardeningError,
        match="NONNEGATIVE_INTEGER_REQUIRED",
    ):
        hardening.validate_ledger_bundle(bundle, artifact_root=tmp_path)

    bundle = _ledger_bundle(tmp_path)
    ticket_path = tmp_path / "ticket_receipt.json"
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    ticket["adjudicator_executor_id"] = "TEST-SCORER"
    ticket_path.write_bytes(hardening.canonical_bytes(ticket))
    bundle["support"]["adjudicator_ticket_receipt_sha256"] = (
        hardening.sha256_file(ticket_path)
    )
    adjudication_path = tmp_path / "adjudication_payload.json"
    adjudication = json.loads(adjudication_path.read_text(encoding="utf-8"))
    adjudication["adjudicator_ticket_receipt_sha256"] = hardening.sha256_file(
        ticket_path
    )
    adjudication_path.write_bytes(hardening.canonical_bytes(adjudication))
    bundle["support"]["adjudication_payload_sha256"] = hardening.sha256_file(
        adjudication_path
    )
    with pytest.raises(
        hardening.R2HardeningError,
        match="ADJUDICATOR_EXECUTOR_NOT_INDEPENDENT",
    ):
        hardening.validate_ledger_bundle(bundle, artifact_root=tmp_path)

    bundle = _ledger_bundle(tmp_path)
    bundle["answer"]["request_sha256"] = "not-a-hash"
    with pytest.raises(hardening.R2HardeningError, match="HASH_INVALID"):
        hardening.validate_ledger_bundle(bundle, artifact_root=tmp_path)

    bundle = _ledger_bundle(tmp_path)
    bundle["support"]["source_ids"] = ["S2"]
    with pytest.raises(
        hardening.R2HardeningError,
        match="SUPPORT_SOURCE_OUTSIDE_ANSWER",
    ):
        hardening.validate_ledger_bundle(bundle, artifact_root=tmp_path)

    bundle = _ledger_bundle(tmp_path)
    (tmp_path / "request.json").write_bytes(b"tampered\n")
    with pytest.raises(
        hardening.R2HardeningError,
        match="LEDGER_BOUND_FILE_SHA_MISMATCH:request",
    ):
        hardening.validate_ledger_bundle(bundle, artifact_root=tmp_path)


def test_terminal_freeze_binds_existing_artifact_bytes(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    artifact_types = [
        *sorted(hardening.TERMINAL_SINGLETON_ARTIFACT_TYPES),
        "ROUTE_MANIFEST",
    ]
    artifacts = []
    for index, artifact_type in enumerate(artifact_types, start=1):
        path = artifact_root / f"artifact-{index:02d}.json"
        path.write_text(f'{{"artifact_type":"{artifact_type}"}}\n', encoding="utf-8")
        artifacts.append(
            {
                "artifact_type": artifact_type,
                "relative_path": path.name,
                "bytes": path.stat().st_size,
                "sha256": hardening.sha256_file(path),
            }
        )
    parent_manifest_path = artifact_root / "parent_manifest.json"
    parent_manifest_path.write_bytes(
        hardening.canonical_bytes(
            {
                "schema_version": hardening.TERMINAL_PARENT_MANIFEST_SCHEMA,
                "artifacts": artifacts,
            }
        )
    )
    contract = {
        "schema_version": hardening.TERMINAL_FREEZE_SCHEMA,
        "issuer": "EXTERNAL-RELEASE-MANAGER",
        "signed_at": "2026-07-27T00:00:00Z",
        "parent_manifest_path": "parent_manifest.json",
        "parent_manifest_sha256": hardening.sha256_file(parent_manifest_path),
        "artifacts": artifacts,
    }
    receipt = hardening.verify_terminal_freeze_artifacts(
        contract,
        artifact_root=artifact_root,
        expected_contract_sha256=hardening.sha256_bytes(
            hardening.canonical_bytes(contract)
        ),
    )
    assert receipt["status"] == "PASS"
    assert receipt["terminal_run_allowed"] is False

    contract["artifacts"][0]["sha256"] = "b" * 64
    with pytest.raises(
        hardening.R2HardeningError,
        match="TERMINAL_FREEZE_ARTIFACT_SHA_MISMATCH",
    ):
        hardening.verify_terminal_freeze_artifacts(
            contract,
            artifact_root=artifact_root,
            expected_contract_sha256=hardening.sha256_bytes(
                hardening.canonical_bytes(contract)
            ),
        )


def test_terminal_freeze_rejects_unknown_type_and_parent_mismatch(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    arbitrary = artifact_root / "arbitrary.json"
    arbitrary.write_text("{}\n", encoding="utf-8")
    artifacts = [
        {
            "artifact_type": "ARBITRARY_SELF_SIGNED",
            "relative_path": arbitrary.name,
            "bytes": arbitrary.stat().st_size,
            "sha256": hardening.sha256_file(arbitrary),
        }
    ]
    parent = artifact_root / "parent.json"
    parent.write_bytes(
        hardening.canonical_bytes(
            {
                "schema_version": hardening.TERMINAL_PARENT_MANIFEST_SCHEMA,
                "artifacts": artifacts,
            }
        )
    )
    contract = {
        "schema_version": hardening.TERMINAL_FREEZE_SCHEMA,
        "issuer": "EXTERNAL-RELEASE-MANAGER",
        "signed_at": "2026-07-27T00:00:00Z",
        "parent_manifest_path": "parent.json",
        "parent_manifest_sha256": hardening.sha256_file(parent),
        "artifacts": artifacts,
    }
    with pytest.raises(
        hardening.R2HardeningError,
        match="TERMINAL_SINGLETON_ARTIFACT_SET_INVALID",
    ):
        hardening.verify_terminal_freeze_artifacts(
            contract,
            artifact_root=artifact_root,
            expected_contract_sha256=hardening.sha256_bytes(
                hardening.canonical_bytes(contract)
            ),
        )

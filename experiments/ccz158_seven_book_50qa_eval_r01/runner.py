"""Run local CCZ-158 diagnostic, oracle-plumbing, or scope-bound lanes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

from .local_candidate_adapter import (
    CandidateCorpus,
    CandidateProjection,
    LocalCandidateAdapterError,
    build_disposable_projection,
    ensure_disposable_output,
    load_candidate_corpus,
    rankers_by_book,
)
from .question_set import (
    EvaluationAnswer,
    QuestionSetError,
    RetrievalPrompt,
    canonical_json,
    load_evaluation_answers,
    load_retrieval_prompts,
    score_run,
    sha256_file,
    sha256_json,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = REPOSITORY_ROOT / "novel-mvp"
R01_EXPECTED = {
    "qa_sha256": "ce12e9c156208839fe70a3e3913515ba499cf5585d4665f426366d975f3d5fd6",
    "placement_manifest_sha256": "49cce8bfcd2275ff6434f4293633e9586720c1f0d604f2962511e259327508b1",
    "ledger_contract_sha256": "eeafe283348bacf69c4eb867b1c61ea43fab9a141aa1f8e32a99be231aee9451",
    "question_count": 50,
    "book_count": 7,
    "chapter_count": 277,
    "fact_count": 8721,
    "required_fact_ref_count": 330,
    "reference_fact_ref_count": 96,
    "unsupported_non_fact_requirement_count": 7,
}
R01_DIAGNOSTIC_ANCHORS = {
    "question_budget": {
        "micro_required_recall": 0.363636,
        "required_precision_r01_comparable": 0.239521,
        "required_complete_count": 3,
        "average_returned": 10.02,
    },
    "fixed_top_50": {
        "micro_required_recall": 0.666667,
        "required_precision_r01_comparable": 0.088,
        "required_complete_count": 16,
        "average_returned": 50.0,
    },
    "qa_card_scope_assisted": {
        "micro_required_recall": 0.5,
        "required_precision_r01_comparable": 0.329341,
        "required_complete_count": 5,
        "average_returned": 10.02,
    },
}


class EvaluationRunError(ValueError):
    """The experiment hit an explicit construction-card stop."""


def _fail(code: str) -> None:
    raise EvaluationRunError(code)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_product_modules() -> tuple[Any, Any, Any]:
    sys.path.insert(0, str(PRODUCT_ROOT))
    try:
        from mvp import c9_ledger_read_adapter as adapter
        from mvp import unified_retrieval_composition as composition
        from mvp import unified_retrieval_core as c9
    finally:
        sys.path.pop(0)
    return adapter, composition, c9


def _input_identity(
    *,
    qa_path: Path,
    placement_root: Path,
    ledger_contract_path: Path,
    source_map_path: Path,
) -> dict[str, Any]:
    manifest_path = placement_root / "MANIFEST.json"
    for path, code in (
        (qa_path, "QA_FILE_MISSING"),
        (manifest_path, "PLACEMENT_MANIFEST_MISSING"),
        (ledger_contract_path, "LEDGER_CONTRACT_MISSING"),
        (source_map_path, "SOURCE_MAP_MISSING"),
    ):
        if not path.is_file():
            _fail(code)
    return {
        "qa_path": str(qa_path.resolve()),
        "qa_sha256": sha256_file(qa_path),
        "placement_manifest_path": str(manifest_path.resolve()),
        "placement_manifest_sha256": sha256_file(manifest_path),
        "ledger_contract_path": str(ledger_contract_path.resolve()),
        "ledger_contract_sha256": sha256_file(ledger_contract_path),
        "source_map_path": str(source_map_path.resolve()),
        "source_map_sha256": sha256_file(source_map_path),
    }


def _validate_r01_input_hashes(identity: Mapping[str, Any]) -> None:
    for field in (
        "qa_sha256",
        "placement_manifest_sha256",
        "ledger_contract_sha256",
    ):
        if identity[field] != R01_EXPECTED[field]:
            _fail(f"R01_INPUT_SHA256_MISMATCH:{field}")


def _validate_prompt_corpus(
    prompts: Sequence[RetrievalPrompt],
    corpus: CandidateCorpus,
) -> None:
    prompt_books = {row.book for row in prompts}
    corpus_books = set(corpus.books)
    if prompt_books != corpus_books:
        _fail("QA_CORPUS_BOOK_SET_MISMATCH")
    if len(prompts) != R01_EXPECTED["question_count"]:
        _fail("R01_QUESTION_COUNT_MISMATCH")
    if len(corpus.books) != R01_EXPECTED["book_count"]:
        _fail("R01_BOOK_COUNT_MISMATCH")
    if corpus.chapter_count() != R01_EXPECTED["chapter_count"]:
        _fail("R01_CHAPTER_COUNT_MISMATCH")
    if corpus.fact_count() != R01_EXPECTED["fact_count"]:
        _fail("R01_FACT_COUNT_MISMATCH")


def _evaluation_counts(answers: Sequence[EvaluationAnswer]) -> dict[str, int]:
    return {
        "required_fact_ref_count": sum(
            len(row.required_fact_refs) for row in answers
        ),
        "reference_fact_ref_count": sum(
            len(row.reference_fact_refs) for row in answers
        ),
        "unsupported_non_fact_requirement_count": sum(
            len(row.unsupported_non_fact_requirements) for row in answers
        ),
    }


def _validate_answers_against_corpus(
    prompts: Sequence[RetrievalPrompt],
    answers: Sequence[EvaluationAnswer],
    corpus: CandidateCorpus,
) -> dict[str, int]:
    counts = _evaluation_counts(answers)
    for field, count in counts.items():
        if count != R01_EXPECTED[field]:
            _fail(f"R01_EVALUATION_COUNT_MISMATCH:{field}")
    available = {
        book: {row.public_ref for row in corpus.facts_for_book(book)}
        for book in corpus.books
    }
    for prompt, answer in zip(prompts, answers, strict=True):
        for ref in (*answer.required_fact_refs, *answer.reference_fact_refs):
            if ref not in available[prompt.book]:
                _fail(f"EVALUATION_FACT_REF_MISSING:{prompt.question_id}:{ref}")
    return counts


def _selection_bundle(
    prompts: Sequence[RetrievalPrompt],
    corpus: CandidateCorpus,
) -> dict[str, Any]:
    rankers = rankers_by_book(corpus)
    variants: dict[str, Any] = {}
    for variant_id in (
        "question_budget",
        "fixed_top_50",
        "qa_card_scope_assisted",
    ):
        rows = []
        for prompt in prompts:
            allowed = (
                set(prompt.scope_chapters)
                if variant_id == "qa_card_scope_assisted"
                else None
            )
            ranked = rankers[prompt.book].rank(
                prompt.question,
                allowed_chapters=allowed,
            )
            limit = 50 if variant_id == "fixed_top_50" else prompt.return_budget
            selected = ranked[:limit]
            rows.append(
                {
                    "question_id": prompt.question_id,
                    "book": prompt.book,
                    "candidate_scope": (
                        "QA_CARD_SCOPE_IS_CANDIDATE_METADATA_NOT_RUNTIME_PROOF"
                        if variant_id == "qa_card_scope_assisted"
                        else "QUESTION_TEXT_ONLY"
                    ),
                    "limit": limit,
                    "candidates": [row.as_dict() for row in selected],
                }
            )
        variant = {
            "variant_id": variant_id,
            "gold_used_for_candidate_selection": False,
            "questions": rows,
        }
        variant["variant_sha256"] = sha256_json(variant)
        variants[variant_id] = variant
    result = {
        "identity": "CCZ158_7BOOK_50QA_CANDIDATE_SELECTIONS_R01",
        "route": "question-only-diagnostic",
        "scope_status": "absent",
        "product_claim": False,
        "variants": variants,
    }
    result["candidate_output_sha256"] = sha256_json(result)
    return result


def _fact_need(
    *,
    adapter: Any,
    question_id: str,
    rank: int,
    internal_fact_id: str,
    estimated_tokens: int,
) -> dict[str, Any]:
    return {
        "need_id": f"NEED-{question_id.replace('-', '')}-{rank:03d}",
        "evidence_layer": "LEDGER_OBJECT",
        "parent_need_id": None,
        "source_contract": "LEDGER_READ_TOOL_CONTRACT",
        "source_contract_version": "ledger-read-tool-contract-v1",
        "object_ref": adapter.ledger_entries_object_ref(
            "事实账", [internal_fact_id]
        ),
        "actuality_class": "CURRENT_FACT_OR_STATE",
        "obligation_tier": "HARD",
        "selection_rank": None,
        "task_relation": f"测试候选第 {rank} 条",
        "estimated_tokens": estimated_tokens,
        "recall_disposition": "NOT_RETRIEVABLE",
        "recall_handle": None,
        "expansion_trigger": "INITIAL",
        "trigger_provenance": None,
    }


def _request_for_candidates(
    *,
    workspace: Any,
    prompt: RetrievalPrompt,
    candidates: Sequence[Mapping[str, Any]],
    projection: CandidateProjection,
    story_scope_ref: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    adapter, _, c9 = _load_product_modules()
    need_to_internal: dict[str, str] = {}
    needs = []
    for rank, candidate in enumerate(candidates, start=1):
        public_ref = candidate["public_ref"]
        identity = (prompt.book, public_ref)
        try:
            internal_id = projection.public_to_internal[identity]
            fact = projection.facts_by_public[identity]
        except KeyError as exc:
            raise EvaluationRunError(
                f"CANDIDATE_PROJECTION_REF_MISSING:{prompt.question_id}:{public_ref}"
            ) from exc
        estimated = max(1, len(fact.fact_text))
        need = _fact_need(
            adapter=adapter,
            question_id=prompt.question_id,
            rank=rank,
            internal_fact_id=internal_id,
            estimated_tokens=estimated,
        )
        need_to_internal[need["need_id"]] = internal_id
        needs.append(need)
    if not needs:
        return {}, {}
    request = c9.seal_request(
        {
            "contract": "C9_RETRIEVAL_REQUEST",
            "version": c9.VERSION,
            "scope": {
                "author_id": workspace.author_id,
                "project_id": workspace.project_id,
                "task_id": f"TASK-CCZ158-{prompt.question_id}",
                "consumer_id": "CCZ158-SEVEN-BOOK-EVAL-R01",
                "workpoint_ref": f"question:{prompt.question_id}",
                "story_scope_ref": story_scope_ref,
                "sandbox_ref": "SANDBOX-LOCAL-CANDIDATE-NOT-FORMAL",
                "upstream_card_ref": None,
            },
            "basis_mode": "current_at_start",
            "task_actuality_scope": "CURRENT_TRUTH_REQUIRED",
            "budget": {
                "limit_tokens": sum(row["estimated_tokens"] for row in needs),
                "estimator_ref": "ccz158-local-candidate-character-count-v1",
            },
            "gap_policy": {
                "policy_ref": "ccz158-eval-fail-closed-v1",
                "missing_required_behavior": "BLOCK",
            },
            "source_needs": needs,
        }
    )
    return request, need_to_internal


def _returned_public_refs(
    *,
    result: Mapping[str, Any],
    need_to_internal: Mapping[str, str],
    projection: CandidateProjection,
) -> list[str]:
    returned: list[str] = []
    for loaded in result["material_package"]["loaded"]:
        need_id = loaded["need_id"]
        expected_internal = need_to_internal[need_id]
        try:
            material = json.loads(loaded["material_text"])
            entries = material["entries"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise EvaluationRunError("C9_LOADED_FACT_MATERIAL_INVALID") from exc
        if len(entries) != 1 or entries[0].get("id") != expected_internal:
            _fail("C9_LOADED_FACT_IDENTITY_MISMATCH")
        returned.append(projection.internal_to_public[expected_internal][1])
    return returned


def run_selected_candidates_through_c9(
    *,
    prompts: Sequence[RetrievalPrompt],
    selections: Mapping[str, Sequence[Mapping[str, Any]]],
    projection: CandidateProjection,
    story_scope_ref: str,
) -> dict[str, Any]:
    _, composition, _ = _load_product_modules()
    trusted = {
        "caller_id": "ccz158-seven-book-eval-r01",
        "permission_profile": "AUTHOR_PROJECT_INTERNAL",
        "permission_policy_version": "permission-policy-v1",
    }
    questions = []
    call_count = 0
    for prompt in prompts:
        candidates = list(selections[prompt.question_id])
        workspace = projection.workspaces[prompt.book]
        request, need_to_internal = _request_for_candidates(
            workspace=workspace,
            prompt=prompt,
            candidates=candidates,
            projection=projection,
            story_scope_ref=story_scope_ref,
        )
        if not request:
            returned: list[str] = []
            result = None
        else:
            result = composition.run_current_retrieval(workspace, trusted, request)
            call_count += 1
            returned = _returned_public_refs(
                result=result,
                need_to_internal=need_to_internal,
                projection=projection,
            )
        selected_refs = [row["public_ref"] for row in candidates]
        if returned != selected_refs:
            _fail(f"C9_CANDIDATE_IDENTITY_MISMATCH:{prompt.question_id}")
        question_result = {
            "question_id": prompt.question_id,
            "selected_public_refs": selected_refs,
            "returned_public_refs": returned,
            "request": request or None,
            "c9_result": result,
        }
        question_result["question_result_sha256"] = sha256_json(question_result)
        questions.append(question_result)
    bundle = {"c9_call_count": call_count, "questions": questions}
    bundle["c9_output_sha256"] = sha256_json(bundle)
    return bundle


def _selections_by_question(variant: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        row["question_id"]: list(row["candidates"])
        for row in variant["questions"]
    }


def _returned_by_question(bundle: Mapping[str, Any]) -> dict[str, list[str]]:
    return {
        row["question_id"]: list(row["returned_public_refs"])
        for row in bundle["questions"]
    }


def _validate_diagnostic_anchors(scores: Mapping[str, Any]) -> None:
    for variant_id, expected in R01_DIAGNOSTIC_ANCHORS.items():
        summary = scores[variant_id]["summary"]
        for field, value in expected.items():
            if summary[field] != value:
                _fail(f"R01_DIAGNOSTIC_DRIFT:{variant_id}:{field}")


def run_question_only_diagnostic(
    *,
    qa_path: Path,
    chapter_root: Path,
    placement_root: Path,
    ledger_contract_path: Path,
    source_map_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    identity = _input_identity(
        qa_path=qa_path,
        placement_root=placement_root,
        ledger_contract_path=ledger_contract_path,
        source_map_path=source_map_path,
    )
    _validate_r01_input_hashes(identity)
    prompts = load_retrieval_prompts(qa_path)
    corpus = load_candidate_corpus(
        placement_root=placement_root,
        chapter_root=chapter_root,
        source_map_path=source_map_path,
    )
    _validate_prompt_corpus(prompts, corpus)
    projection = build_disposable_projection(
        corpus,
        output_root=output_dir,
        repository_root=REPOSITORY_ROOT,
        protected_roots=(qa_path, chapter_root, placement_root, ledger_contract_path),
    )
    identity.update(
        {
            "question_count": len(prompts),
            "book_count": len(corpus.books),
            "chapter_count": corpus.chapter_count(),
            "fact_count": corpus.fact_count(),
            "placement_file_sha256": corpus.placement_file_sha256,
        }
    )
    _write_json(output_dir / "input_receipt.json", identity)

    candidate_bundle = _selection_bundle(prompts, corpus)
    _write_json(output_dir / "candidate_selections.json", candidate_bundle)

    c9_variants: dict[str, Any] = {}
    for variant_id, variant in candidate_bundle["variants"].items():
        c9_variants[variant_id] = run_selected_candidates_through_c9(
            prompts=prompts,
            selections=_selections_by_question(variant),
            projection=projection,
            story_scope_ref="DIAGNOSTIC-NO-CHAPTER-SCOPE",
        )
    c9_bundle = {
        "identity": "CCZ158_7BOOK_50QA_C9_TRANSPARENT_RECEIPTS_R01",
        "route": "question-only-diagnostic",
        "scope_status": "absent",
        "product_claim": False,
        "variants": c9_variants,
    }
    c9_bundle["c9_output_sha256"] = sha256_json(c9_bundle)
    _write_json(output_dir / "c9_transparent_receipts.json", c9_bundle)

    # Gold and error lists enter memory only after candidate and C9 files are sealed.
    answers = load_evaluation_answers(qa_path)
    counts = _validate_answers_against_corpus(prompts, answers, corpus)
    identity.update(counts)
    _write_json(output_dir / "input_receipt.json", identity)

    scores = {
        variant_id: score_run(
            prompts,
            answers,
            _returned_by_question(c9_variants[variant_id]),
        )
        for variant_id in c9_variants
    }
    _validate_diagnostic_anchors(scores)
    score_report = {
        "identity": "CCZ158_7BOOK_50QA_SCORE_REPORT_R01",
        "route": "question-only-diagnostic",
        "scope_status": "absent",
        "product_claim": False,
        "r01_anchor_status": "MATCH",
        "scores": scores,
    }
    score_report["score_report_sha256"] = sha256_json(score_report)
    _write_json(output_dir / "score_report.json", score_report)
    _write_json(
        output_dir / "fact_identity_sidecar.json",
        {
            "identity": "CCZ158_LOCAL_CANDIDATE_FACT_IDENTITY_SIDECAR_R01",
            "candidate_status": "extracted",
            "formal_fact_write_count": 0,
            "rows": list(projection.sidecar),
        },
    )
    run_receipt = {
        "identity": "CCZ158_7BOOK_50QA_QUESTION_ONLY_DIAGNOSTIC_RUN_R01",
        "status": "LOCAL_CANDIDATE__NOT_GOLD__NOT_PRODUCT_RUNTIME",
        "route": "question-only-diagnostic",
        "scope_status": "absent",
        "product_claim": False,
        "repository_commit": _git_head(),
        "generated_at": _utc_now(),
        "candidate_output_sha256": candidate_bundle["candidate_output_sha256"],
        "c9_output_sha256": c9_bundle["c9_output_sha256"],
        "score_report_sha256": score_report["score_report_sha256"],
        "c9_call_count": sum(
            row["c9_call_count"] for row in c9_variants.values()
        ),
        "model_api_calls": 0,
        "network_calls": 0,
        "formal_fact_write_count": 0,
        "formal_ledger_write_count": 0,
        "r01_anchor_status": "MATCH",
    }
    run_receipt["run_receipt_sha256"] = sha256_json(run_receipt)
    _write_json(output_dir / "run_receipt.json", run_receipt)
    return run_receipt


def run_oracle_plumbing(
    *,
    qa_path: Path,
    chapter_root: Path,
    placement_root: Path,
    ledger_contract_path: Path,
    source_map_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    identity = _input_identity(
        qa_path=qa_path,
        placement_root=placement_root,
        ledger_contract_path=ledger_contract_path,
        source_map_path=source_map_path,
    )
    _validate_r01_input_hashes(identity)
    prompts = load_retrieval_prompts(qa_path)
    corpus = load_candidate_corpus(
        placement_root=placement_root,
        chapter_root=chapter_root,
        source_map_path=source_map_path,
    )
    _validate_prompt_corpus(prompts, corpus)
    answers = load_evaluation_answers(qa_path)
    counts = _validate_answers_against_corpus(prompts, answers, corpus)
    projection = build_disposable_projection(
        corpus,
        output_root=output_dir,
        repository_root=REPOSITORY_ROOT,
        protected_roots=(qa_path, chapter_root, placement_root, ledger_contract_path),
    )
    selections = {
        prompt.question_id: [
            {
                "public_ref": ref,
                "score": None,
                "matched_term_count": None,
                "selection_method": "ORACLE_REQUIRED_FACT",
            }
            for ref in answer.required_fact_refs
        ]
        for prompt, answer in zip(prompts, answers, strict=True)
    }
    candidate_bundle = {
        "identity": "CCZ158_7BOOK_50QA_ORACLE_SELECTIONS_R01",
        "route": "oracle-plumbing",
        "accuracy_claim": "NOT_ACCURACY",
        "gold_used_for_candidate_selection": True,
        "selections": selections,
    }
    candidate_bundle["candidate_output_sha256"] = sha256_json(candidate_bundle)
    _write_json(output_dir / "candidate_selections.json", candidate_bundle)
    c9_bundle = run_selected_candidates_through_c9(
        prompts=prompts,
        selections=selections,
        projection=projection,
        story_scope_ref="ORACLE-NOT-ACCURACY",
    )
    _write_json(output_dir / "c9_transparent_receipts.json", c9_bundle)
    scores = score_run(prompts, answers, _returned_by_question(c9_bundle))
    summary = scores["summary"]
    if (
        summary["required_fact_ref_count"]
        != R01_EXPECTED["required_fact_ref_count"]
        or summary["micro_required_recall"] != 1.0
        or summary["noise_count"] != 0
        or summary["required_complete_count"] != len(prompts)
        or summary["full_question_count"] != len(prompts)
    ):
        _fail("ORACLE_PLUMBING_IDENTITY_LOSS")
    score_report = {
        "identity": "CCZ158_7BOOK_50QA_ORACLE_SCORE_REPORT_R01",
        "status": "PASS_NOT_ACCURACY",
        "route": "oracle-plumbing",
        "accuracy_claim": "NOT_ACCURACY",
        "gold_used_for_candidate_selection": True,
        "scores": scores,
    }
    score_report["score_report_sha256"] = sha256_json(score_report)
    _write_json(output_dir / "score_report.json", score_report)
    _write_json(
        output_dir / "fact_identity_sidecar.json",
        {
            "identity": "CCZ158_LOCAL_CANDIDATE_FACT_IDENTITY_SIDECAR_R01",
            "candidate_status": "extracted",
            "formal_fact_write_count": 0,
            "rows": list(projection.sidecar),
        },
    )
    identity.update(
        {
            "question_count": len(prompts),
            "book_count": len(corpus.books),
            "chapter_count": corpus.chapter_count(),
            "fact_count": corpus.fact_count(),
            **counts,
        }
    )
    _write_json(output_dir / "input_receipt.json", identity)
    receipt = {
        "identity": "CCZ158_7BOOK_50QA_ORACLE_PLUMBING_RUN_R01",
        "status": "PASS_NOT_ACCURACY",
        "route": "oracle-plumbing",
        "accuracy_claim": "NOT_ACCURACY",
        "gold_used_for_candidate_selection": True,
        "repository_commit": _git_head(),
        "generated_at": _utc_now(),
        "candidate_output_sha256": candidate_bundle["candidate_output_sha256"],
        "c9_output_sha256": c9_bundle["c9_output_sha256"],
        "score_report_sha256": score_report["score_report_sha256"],
        "c9_call_count": c9_bundle["c9_call_count"],
        "required_fact_ref_count": summary["required_fact_ref_count"],
        "model_api_calls": 0,
        "network_calls": 0,
        "formal_fact_write_count": 0,
        "formal_ledger_write_count": 0,
    }
    receipt["run_receipt_sha256"] = sha256_json(receipt)
    _write_json(output_dir / "run_receipt.json", receipt)
    return receipt


def _load_scope_validator() -> Any:
    path = PRODUCT_ROOT / "contracts" / "validate_chapter_scope_confirmation.py"
    spec = importlib.util.spec_from_file_location("ccz158_scope_validator", path)
    if spec is None or spec.loader is None:
        _fail("SCOPE_VALIDATOR_NOT_LOADABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_scope_bundle(
    *,
    scope_bundle_path: Path | None,
    question_ids: Sequence[str],
    qa_sha256: str,
    placement_manifest_sha256: str,
) -> dict[str, Any]:
    if scope_bundle_path is None or not scope_bundle_path.is_file():
        return {
            "status": "SCOPE_INPUT_UNAVAILABLE",
            "reason": "REAL_CONFIRMED_SCOPE_BUNDLE_MISSING",
            "scope_count": 0,
            "c9_call_count": 0,
        }
    validator = _load_scope_validator()
    rows = []
    try:
        for line in scope_bundle_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except json.JSONDecodeError as exc:
        return {
            "status": "SCOPE_INPUT_INVALID",
            "reason": "SCOPE_BUNDLE_INVALID_JSON",
            "scope_count": 0,
            "c9_call_count": 0,
            "detail": str(exc),
        }
    expected_fields = {
        "question_id",
        "qa_sha256",
        "placement_manifest_sha256",
        "scope_confirmation",
    }
    if len(rows) != len(question_ids):
        return {
            "status": "SCOPE_INPUT_UNAVAILABLE",
            "reason": "SCOPE_BUNDLE_QUESTION_COUNT_MISMATCH",
            "scope_count": len(rows),
            "c9_call_count": 0,
        }
    observed_ids = []
    now = datetime.now(timezone.utc)
    for row in rows:
        if not isinstance(row, dict) or set(row) != expected_fields:
            return {
                "status": "SCOPE_INPUT_INVALID",
                "reason": "SCOPE_BUNDLE_ROW_FIELDS_INVALID",
                "scope_count": len(rows),
                "c9_call_count": 0,
            }
        observed_ids.append(row["question_id"])
        if row["qa_sha256"] != qa_sha256:
            return {
                "status": "SCOPE_INPUT_INVALID",
                "reason": "SCOPE_QA_WATERMARK_MISMATCH",
                "scope_count": len(rows),
                "c9_call_count": 0,
            }
        if row["placement_manifest_sha256"] != placement_manifest_sha256:
            return {
                "status": "SCOPE_INPUT_INVALID",
                "reason": "SCOPE_MATERIAL_WATERMARK_MISMATCH",
                "scope_count": len(rows),
                "c9_call_count": 0,
            }
        document = row["scope_confirmation"]
        try:
            validator.validate_scope_confirmation(document)
        except (validator.ContractError, TypeError) as exc:
            return {
                "status": "SCOPE_INPUT_INVALID",
                "reason": "SCOPE_CONTRACT_INVALID",
                "scope_count": len(rows),
                "c9_call_count": 0,
                "detail": str(exc),
            }
        if document["status"] != "CONFIRMED":
            return {
                "status": "SCOPE_INPUT_INVALID",
                "reason": "SCOPE_NOT_CONFIRMED",
                "scope_count": len(rows),
                "c9_call_count": 0,
            }
        permission = document["confirmation"]["permission_snapshot_ref"]
        focus = document["confirmation"]["effective_focus_ref"]
        for expires in (permission["valid_until"], focus["valid_until"]):
            parsed = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if parsed <= now:
                return {
                    "status": "SCOPE_INPUT_INVALID",
                    "reason": "SCOPE_AUTHORITY_EXPIRED",
                    "scope_count": len(rows),
                    "c9_call_count": 0,
                }
    if observed_ids != list(question_ids) or len(observed_ids) != len(set(observed_ids)):
        return {
            "status": "SCOPE_INPUT_INVALID",
            "reason": "SCOPE_QUESTION_ALIGNMENT_MISMATCH",
            "scope_count": len(rows),
            "c9_call_count": 0,
        }
    return {
        "status": "SCOPE_SEMANTIC_FILTER_UNAVAILABLE",
        "reason": "TRUSTED_SCOPE_TO_FACT_READER_NOT_OPEN",
        "scope_count": len(rows),
        "c9_call_count": 0,
        "validated_scope_bundle_sha256": sha256_file(scope_bundle_path),
    }


def run_scope_bound_gate(
    *,
    qa_path: Path,
    placement_root: Path,
    ledger_contract_path: Path,
    source_map_path: Path,
    output_dir: Path,
    scope_bundle_path: Path | None,
) -> dict[str, Any]:
    identity = _input_identity(
        qa_path=qa_path,
        placement_root=placement_root,
        ledger_contract_path=ledger_contract_path,
        source_map_path=source_map_path,
    )
    _validate_r01_input_hashes(identity)
    prompts = load_retrieval_prompts(qa_path)
    output_dir = ensure_disposable_output(
        output_dir,
        repository_root=REPOSITORY_ROOT,
        protected_roots=(qa_path, placement_root, ledger_contract_path),
    )
    gate = evaluate_scope_bundle(
        scope_bundle_path=scope_bundle_path,
        question_ids=[row.question_id for row in prompts],
        qa_sha256=identity["qa_sha256"],
        placement_manifest_sha256=identity["placement_manifest_sha256"],
    )
    receipt = {
        "identity": "CCZ158_7BOOK_50QA_SCOPE_BOUND_GATE_R01",
        "route": "scope-bound",
        "product_claim": False,
        "repository_commit": _git_head(),
        "generated_at": _utc_now(),
        "model_api_calls": 0,
        "network_calls": 0,
        "formal_fact_write_count": 0,
        "formal_ledger_write_count": 0,
        **gate,
    }
    receipt["run_receipt_sha256"] = sha256_json(receipt)
    _write_json(output_dir / "input_receipt.json", identity)
    _write_json(output_dir / "run_receipt.json", receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--route",
        choices=("question-only-diagnostic", "oracle-plumbing", "scope-bound"),
        required=True,
    )
    parser.add_argument("--qa-md", type=Path, required=True)
    parser.add_argument("--chapter-root", type=Path)
    parser.add_argument("--placement-root", type=Path, required=True)
    parser.add_argument("--ledger-contract", type=Path, required=True)
    parser.add_argument("--book-map", type=Path, required=True)
    parser.add_argument("--scope-bundle", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.route == "scope-bound":
            receipt = run_scope_bound_gate(
                qa_path=args.qa_md,
                placement_root=args.placement_root,
                ledger_contract_path=args.ledger_contract,
                source_map_path=args.book_map,
                output_dir=args.output_dir,
                scope_bundle_path=args.scope_bundle,
            )
        else:
            if args.chapter_root is None:
                _fail("CHAPTER_ROOT_REQUIRED")
            common = {
                "qa_path": args.qa_md,
                "chapter_root": args.chapter_root,
                "placement_root": args.placement_root,
                "ledger_contract_path": args.ledger_contract,
                "source_map_path": args.book_map,
                "output_dir": args.output_dir,
            }
            if args.route == "question-only-diagnostic":
                receipt = run_question_only_diagnostic(**common)
            else:
                receipt = run_oracle_plumbing(**common)
    except (EvaluationRunError, LocalCandidateAdapterError, QuestionSetError) as exc:
        error = {"status": "HARD_STOP", "reason": str(exc)}
        print(json.dumps(error, ensure_ascii=False, sort_keys=True))
        return 2
    print(canonical_json(receipt))
    if receipt.get("status") in {
        "SCOPE_INPUT_UNAVAILABLE",
        "SCOPE_INPUT_INVALID",
        "SCOPE_SEMANTIC_FILTER_UNAVAILABLE",
    }:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EvaluationRunError",
    "R01_DIAGNOSTIC_ANCHORS",
    "R01_EXPECTED",
    "evaluate_scope_bundle",
    "main",
    "run_oracle_plumbing",
    "run_question_only_diagnostic",
    "run_scope_bound_gate",
    "run_selected_candidates_through_c9",
]

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.ccz158_seven_book_50qa_eval_r01 import runner
from experiments.ccz158_seven_book_50qa_eval_r01.local_candidate_adapter import (
    LocalCandidateAdapterError,
    SparseRanker,
    build_disposable_projection,
    ensure_disposable_output,
    load_candidate_corpus,
)
from experiments.ccz158_seven_book_50qa_eval_r01.question_set import (
    load_evaluation_answers,
    load_retrieval_prompts,
    score_run,
)


ROOT = Path(__file__).resolve().parents[1]


def _qa_block(
    question_id: str,
    book: str,
    question: str,
    required: str,
    reference: str | None,
) -> str:
    reference_line = (
        f"- **{reference}**（参考）— 参考内容。" if reference else "- 无额外参考项。"
    )
    return f"""## {question_id}

1. **QA 编号**：`{question_id}`
2. **书名｜新书或旧书｜章节范围**：{book}｜合成样本｜第1章
3. **真实使用情景**：合成场景。
4. **问题**：{question}
5. **第一步该查什么**：查事实候选。
6. **必取清单**：
- **{required}**（第1章）— 必取内容。
- **需要正文核对**（合同边界）— 不是事实编号。
7. **参考清单**：
{reference_line}
8. **多余／错误清单**：
- 不得因为错误说明里出现 `{required}`，就把这条必取事实机械判成禁取。
9. **合理返回量**：建议返回 **2–3 条**；超过 5 条算噪音。
10. **是否需要下钻到原文｜为什么**：需要。
11. **预期答案**：合成答案。
12. **证据指针**：合成指针。
13. **这题在测什么风险**：合成风险。
14. **待人工核验点**：无。
"""


def _write_question_set(path: Path) -> Path:
    path.write_text(
        "# 合成题卡\n\n"
        + _qa_block(
            "QA-001",
            "样本甲",
            "甲对象发生了什么变化？",
            "E-01-01",
            "E-01-02",
        )
        + "\n---\n\n"
        + _qa_block(
            "QA-002",
            "样本乙",
            "乙对象现在是什么状态？",
            "E-01-01",
            None,
        ),
        encoding="utf-8",
    )
    return path


def _write_material(tmp_path: Path) -> dict[str, Path]:
    placement_root = tmp_path / "placements"
    chapter_root = tmp_path / "chapters"
    for code, book, fact in (
        ("a", "样本甲", "甲对象完成变化。"),
        ("b", "样本乙", "乙对象保持当前状态。"),
    ):
        placement_dir = placement_root / f"placement-{code}"
        chapter_dir = chapter_root / f"chapter-{code}"
        placement_dir.mkdir(parents=True)
        chapter_dir.mkdir(parents=True)
        (chapter_dir / "ch_0001.txt").write_text(
            f"{book}第一章合成正文。", encoding="utf-8"
        )
        (placement_dir / "01_落位表.csv").write_text(
            "fact_id,书名,章号,source,事实句,原文位置,想落哪本账哪个字段,落位状态,特标,落位说明\n"
            f"E-01-01,{book},1,synthetic,{fact},第1章｜E-01-01,事实账,顺利,,\n"
            + (
                f"E-01-02,{book},1,synthetic,甲对象还有参考信息。,第1章｜E-01-02,事实账,顺利,,\n"
                if code == "a"
                else ""
            ),
            encoding="utf-8",
        )
    (placement_root / "MANIFEST.json").write_text(
        json.dumps({"placement_rows": 3}), encoding="utf-8"
    )
    source_map = tmp_path / "source-map.json"
    source_map.write_text(
        json.dumps(
            {
                "schema_version": "ccz158-seven-book-source-map-v1",
                "sources": [
                    {
                        "book": "样本甲",
                        "placement_dir": "placement-a",
                        "chapter_dir": "chapter-a",
                        "row_ref_prefix": None,
                    },
                    {
                        "book": "样本乙",
                        "placement_dir": "placement-b",
                        "chapter_dir": "chapter-b",
                        "row_ref_prefix": None,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ledger_contract = tmp_path / "ledger-contract.md"
    ledger_contract.write_text("合成合同。", encoding="utf-8")
    return {
        "placement_root": placement_root,
        "chapter_root": chapter_root,
        "source_map": source_map,
        "ledger_contract": ledger_contract,
    }


def _load_fixture(tmp_path: Path):
    qa_path = _write_question_set(tmp_path / "questions.md")
    material = _write_material(tmp_path)
    prompts = load_retrieval_prompts(qa_path, expected_count=2)
    answers = load_evaluation_answers(qa_path, expected_count=2)
    corpus = load_candidate_corpus(
        placement_root=material["placement_root"],
        chapter_root=material["chapter_root"],
        source_map_path=material["source_map"],
    )
    return qa_path, material, prompts, answers, corpus


def test_prompt_parser_cannot_see_hidden_answers(tmp_path: Path) -> None:
    qa_path = _write_question_set(tmp_path / "questions.md")
    prompts = load_retrieval_prompts(qa_path, expected_count=2)
    serialized = json.dumps(
        [row.as_dict() for row in prompts], ensure_ascii=False, sort_keys=True
    )

    assert [row.question_id for row in prompts] == ["QA-001", "QA-002"]
    assert [row.return_budget for row in prompts] == [3, 3]
    assert "E-01-01" not in serialized
    assert "需要正文核对" not in serialized
    assert "多余／错误清单" not in serialized


def test_answer_parser_keeps_fact_reference_contract_and_error_layers_separate(
    tmp_path: Path,
) -> None:
    qa_path = _write_question_set(tmp_path / "questions.md")
    answers = load_evaluation_answers(qa_path, expected_count=2)

    assert answers[0].required_fact_refs == ("E-01-01",)
    assert answers[0].reference_fact_refs == ("E-01-02",)
    assert answers[0].unsupported_non_fact_requirements == ("需要正文核对",)
    assert "E-01-01" in answers[0].semantic_assertions_unscored[0]


def test_repeated_non_fact_label_keeps_each_requirement(tmp_path: Path) -> None:
    qa_path = _write_question_set(tmp_path / "questions.md")
    text = qa_path.read_text(encoding="utf-8")
    text = text.replace(
        "- **需要正文核对**（合同边界）— 不是事实编号。",
        "- **需要正文核对**（合同边界 A）— 不是事实编号。\n"
        "- **需要正文核对**（合同边界 B）— 另一条独立要求。",
        1,
    )
    qa_path.write_text(text, encoding="utf-8")

    answers = load_evaluation_answers(qa_path, expected_count=2)

    assert answers[0].unsupported_non_fact_requirements == (
        "需要正文核对",
        "需要正文核对",
    )


def test_local_projection_keeps_same_public_ref_scoped_by_book_and_extracted(
    tmp_path: Path,
) -> None:
    qa_path, material, _, _, corpus = _load_fixture(tmp_path)
    projection = build_disposable_projection(
        corpus,
        output_root=tmp_path / "projection",
        repository_root=ROOT,
        protected_roots=(
            qa_path,
            material["chapter_root"],
            material["placement_root"],
            material["ledger_contract"],
        ),
    )

    first = projection.public_to_internal[("样本甲", "E-01-01")]
    second = projection.public_to_internal[("样本乙", "E-01-01")]
    assert first != second
    assert first.startswith("f") and second.startswith("f")
    assert {row["public_ref"] for row in projection.sidecar} == {
        "E-01-01",
        "E-01-02",
    }
    for workspace in projection.workspaces.values():
        facts = workspace.read("facts")["payload"]
        assert facts
        assert {row["status"] for row in facts} == {"extracted"}


def test_sparse_ranker_is_deterministic_and_uses_no_answer_object(
    tmp_path: Path,
) -> None:
    _, _, prompts, _, corpus = _load_fixture(tmp_path)
    ranker = SparseRanker(corpus.facts_for_book("样本甲"))

    first = ranker.rank(prompts[0].question)
    second = ranker.rank(prompts[0].question)

    assert first == second
    assert first[0].public_ref == "E-01-01"
    assert first[0].matched_term_count > 0


def test_selected_candidates_use_current_reader_adapter_c9_and_round_trip_ids(
    tmp_path: Path,
) -> None:
    qa_path, material, prompts, _, corpus = _load_fixture(tmp_path)
    projection = build_disposable_projection(
        corpus,
        output_root=tmp_path / "projection",
        repository_root=ROOT,
        protected_roots=(
            qa_path,
            material["chapter_root"],
            material["placement_root"],
            material["ledger_contract"],
        ),
    )
    selections = {
        "QA-001": [{"public_ref": "E-01-01"}],
        "QA-002": [{"public_ref": "E-01-01"}],
    }

    bundle = runner.run_selected_candidates_through_c9(
        prompts=prompts,
        selections=selections,
        projection=projection,
        story_scope_ref="DIAGNOSTIC-NO-CHAPTER-SCOPE",
    )

    assert bundle["c9_call_count"] == 2
    assert [
        row["returned_public_refs"] for row in bundle["questions"]
    ] == [["E-01-01"], ["E-01-01"]]
    assert all(
        row["c9_result"]["status"] == "READY" for row in bundle["questions"]
    )
    for row in bundle["questions"]:
        loaded = row["c9_result"]["material_package"]["loaded"]
        assert loaded[0]["source_validation"]["validation_result"] == (
            "LEDGER_READ_RESPONSE_VALID"
        )


def test_scoring_counts_required_reference_noise_and_budget_without_id_ban(
    tmp_path: Path,
) -> None:
    _, _, prompts, answers, _ = _load_fixture(tmp_path)
    report = score_run(
        prompts,
        answers,
        {
            "QA-001": ["E-01-01", "E-01-02", "E-99-99"],
            "QA-002": ["E-01-01"],
        },
    )

    first = report["per_question"][0]
    assert first["required_recall"] == 1.0
    assert first["reference_recall"] == 1.0
    assert first["noise_count"] == 1
    assert first["required_complete"] is True
    assert first["full_question_pass"] is True
    assert "E-01-01" in first["semantic_assertions_unscored"][0]
    assert report["summary"]["required_fact_ref_count"] == 2
    assert report["summary"]["reference_fact_ref_count"] == 1
    assert report["summary"]["unsupported_non_fact_requirement_count"] == 2


def test_required_complete_and_budgeted_pass_are_separate(tmp_path: Path) -> None:
    _, _, prompts, answers, _ = _load_fixture(tmp_path)
    report = score_run(
        prompts,
        answers,
        {
            "QA-001": ["E-01-01", "E-20-01", "E-20-02", "E-20-03"],
            "QA-002": ["E-01-01"],
        },
    )

    first = report["per_question"][0]
    assert first["required_complete"] is True
    assert first["budget_ok"] is False
    assert first["full_question_pass"] is False
    assert report["summary"]["required_complete_count"] == 2
    assert report["summary"]["full_question_count"] == 1


def test_output_guard_rejects_git_and_material_overlap(tmp_path: Path) -> None:
    with pytest.raises(
        LocalCandidateAdapterError, match="OUTPUT_INSIDE_GIT_REPOSITORY"
    ):
        ensure_disposable_output(
            ROOT / "experiments" / "forbidden-output",
            repository_root=ROOT,
            protected_roots=(),
        )

    material = tmp_path / "material"
    material.mkdir()
    with pytest.raises(
        LocalCandidateAdapterError, match="OUTPUT_OVERLAPS_PROTECTED_MATERIAL"
    ):
        ensure_disposable_output(
            material / "output",
            repository_root=ROOT,
            protected_roots=(material,),
        )


def test_scope_gate_fails_closed_without_scope_and_makes_zero_c9_calls() -> None:
    result = runner.evaluate_scope_bundle(
        scope_bundle_path=None,
        question_ids=["QA-001"],
        qa_sha256="a" * 64,
        placement_manifest_sha256="b" * 64,
    )

    assert result == {
        "status": "SCOPE_INPUT_UNAVAILABLE",
        "reason": "REAL_CONFIRMED_SCOPE_BUNDLE_MISSING",
        "scope_count": 0,
        "c9_call_count": 0,
    }


def test_valid_scope_bundle_stops_at_missing_trusted_semantic_filter(
    tmp_path: Path,
) -> None:
    validator = runner._load_scope_validator()
    case = next(
        row for row in validator.load_fixtures() if row["case_id"] == "CSC-VALID-01"
    )
    document = validator.materialize_fixture_case(case)["document"]
    scope_path = tmp_path / "scope.jsonl"
    scope_path.write_text(
        json.dumps(
            {
                "question_id": "QA-001",
                "qa_sha256": "a" * 64,
                "placement_manifest_sha256": "b" * 64,
                "scope_confirmation": document,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.evaluate_scope_bundle(
        scope_bundle_path=scope_path,
        question_ids=["QA-001"],
        qa_sha256="a" * 64,
        placement_manifest_sha256="b" * 64,
    )

    assert result["status"] == "SCOPE_SEMANTIC_FILTER_UNAVAILABLE"
    assert result["reason"] == "TRUSTED_SCOPE_TO_FACT_READER_NOT_OPEN"
    assert result["scope_count"] == 1
    assert result["c9_call_count"] == 0


def test_repository_sources_do_not_embed_real_material_or_external_clients() -> None:
    files = [
        ROOT / "experiments/ccz158_seven_book_50qa_eval_r01/question_set.py",
        ROOT
        / "experiments/ccz158_seven_book_50qa_eval_r01/local_candidate_adapter.py",
        ROOT / "experiments/ccz158_seven_book_50qa_eval_r01/runner.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    local_home_prefix = f"/{'Users'}/"

    assert local_home_prefix not in text
    assert "requests" not in text
    assert "httpx" not in text
    assert "openai" not in text.casefold()
    assert "status\": \"confirmed\"" not in text

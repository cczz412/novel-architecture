from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/validate_novel_fact_v2.py"
BUNDLE = ROOT / "config/contracts/novel_fact_extraction_v2.bundle.json"


def compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def prepare_case(
    tmp_path: Path,
    *,
    status: str = "已发生",
    fact_text: str = "萧景离开了宗门。",
    speaker: str | None = None,
) -> dict[str, Path]:
    chapters = tmp_path / "chapters"
    chapters.mkdir(parents=True)
    chapter_text = "清晨，萧景收好行囊。萧景离开了宗门。秦守诚留在山门前。\n"
    source_file = "sample.txt"
    (chapters / source_file).write_text(chapter_text, encoding="utf-8")

    metadata = tmp_path / "book_metadata.json"
    metadata.write_text('{"title":"测试书","protagonist":"萧景"}\n', encoding="utf-8")
    metadata_sha = hashlib.sha256(metadata.read_bytes()).hexdigest()
    source_index = tmp_path / "source_index.jsonl"
    source_index.write_text(
        compact(
            {
                "source_id": "book-meta-001",
                "scope": "verified_book_metadata",
                "path": str(metadata),
                "sha256": metadata_sha,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    card = {
        "schema_version": "novel-fact-p3-context-card-v1",
        "sample_id": "S001",
        "source_file": source_file,
        "story_type": {
            "status": "confirmed",
            "value": "修仙",
            "basis": "verified_book_metadata",
        },
        "story_subtypes": {
            "status": "confirmed",
            "values": ["宗门成长", "冒险"],
            "basis": "verified_book_metadata",
        },
        "protagonist": {
            "status": "confirmed",
            "canonical_name": "萧景",
            "aliases": ["世子"],
            "basis": "verified_book_metadata",
        },
        "cheat_mechanic": {
            "status": "unknown",
            "name": None,
            "summary": None,
            "rules": [],
            "basis": "none_available",
        },
        "source_refs": [
            {
                "source_id": "book-meta-001",
                "scope": "verified_book_metadata",
                "sha256": metadata_sha,
            }
        ],
        "boundary": {
            "only_alias_and_rule_resolution": True,
            "may_replace_chapter_evidence": False,
            "may_add_unstated_fact": False,
            "target_chapter_as_sole_source_allowed": False,
        },
    }
    cards = tmp_path / "cards.jsonl"
    cards.write_text(compact(card) + "\n", encoding="utf-8")

    fact = {"fact": fact_text, "status": status, "evidence": "萧景离开了宗门"}
    if speaker is not None:
        fact["speaker"] = speaker
    annotation = {
        "sample_id": "S001",
        "source_file": source_file,
        "facts": [fact],
        "gold_atoms": [
            {
                "atom_id": "S001-F001",
                "fact": fact_text,
                "status": status,
                "evidence": "萧景离开了宗门",
                "speaker": speaker,
                "evidence_occurrence": 1,
                "claim_chain": [],
            }
        ],
        "quality": {
            "status": "candidate",
            "fact_count": 1,
            "empty_reason": None,
            "coverage_self_check": "complete",
            "notes": [],
        },
    }
    annotations = tmp_path / "annotations.jsonl"
    annotations.write_text(compact(annotation) + "\n", encoding="utf-8")
    return {
        "annotations": annotations,
        "chapters": chapters,
        "cards": cards,
        "source_index": source_index,
        "chapter": chapters / source_file,
    }


def run_tool(
    case: dict[str, Path], command: str, *extra: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(TOOL),
            command,
            "--annotations",
            str(case["annotations"]),
            "--chapters-dir",
            str(case["chapters"]),
            "--context-cards",
            str(case["cards"]),
            "--context-source-index",
            str(case["source_index"]),
            "--expected-count",
            "1",
            *extra,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_contract_bundle_matches_all_assets() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL), "bundle-check"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "V2_1_CONTRACT_BUNDLE_PASS"
    assert receipt["contract_bundle_version"] == "novel-fact-extraction-v2.1-bundle-2"
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    assert bundle["supersedes"] == "novel-fact-extraction-v2.1-bundle-1"
    assert bundle["authority"]["decided_at"] == "2026-08-01T20:05:00+08:00"
    assert bundle["versioning"]["prior_gate_tickets_inherit_pass"] is False


def test_contract_bundle_rejects_permission_or_required_role_drift(
    tmp_path: Path,
) -> None:
    original = json.loads(BUNDLE.read_text(encoding="utf-8"))
    cases = []

    permission_drift = json.loads(json.dumps(original, ensure_ascii=False))
    permission_drift["boundaries"]["may_call_model"] = True
    cases.append(("permission", permission_drift, "权限边界必须保持 false"))

    ticket_drift = json.loads(json.dumps(original, ensure_ascii=False))
    ticket_drift["versioning"]["prior_gate_tickets_inherit_pass"] = True
    cases.append(("ticket", ticket_drift, "旧程序闸票不得继承通过"))

    role_drift = json.loads(json.dumps(original, ensure_ascii=False))
    role_drift["assets"].pop()
    cases.append(("role", role_drift, "必需资产角色集合漂移"))

    for name, value, expected_error in cases:
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(TOOL), "bundle-check", "--bundle", str(path)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 1
        assert expected_error in result.stderr


def test_validate_and_assemble_keep_full_chapter_and_context(tmp_path: Path) -> None:
    case = prepare_case(tmp_path)
    checked = run_tool(case, "validate")
    assert checked.returncode == 0, checked.stderr
    receipt = json.loads(checked.stdout)
    assert receipt["status"] == "V2_1_FORMAT_AND_EVIDENCE_PASS_SEMANTIC_REVIEW_PENDING"
    assert receipt["contract_version"] == "novel-fact-extraction-v2.1"
    assert receipt["gate_version"] == "novel-fact-extraction-gate-v1.2"
    assert receipt["contract_bundle_version"] == "novel-fact-extraction-v2.1-bundle-2"
    assert len(receipt["contract_bundle_sha256"]) == 64

    output = tmp_path / "messages.jsonl"
    assembled = run_tool(case, "assemble", "--output", str(output))
    assert assembled.returncode == 0, assembled.stderr
    row = json.loads(output.read_text(encoding="utf-8"))
    assert row["messages"][0]["role"] == "system"
    assert "status 必填，只能使用下面八种值" in row["messages"][0]["content"]
    assert case["chapter"].read_text(encoding="utf-8") in row["messages"][1]["content"]
    assert '"canonical_name":"萧景"' in row["messages"][1]["content"]
    assistant = json.loads(row["messages"][2]["content"])
    assert list(assistant) == ["facts"]
    assert assistant["facts"][0]["status"] == "已发生"


def test_cognitive_or_reported_fact_requires_speaker(tmp_path: Path) -> None:
    case = prepare_case(tmp_path, status="推测", fact_text="萧景怀疑自己已经离开宗门。")
    result = run_tool(case, "validate")
    assert result.returncode == 1
    assert "必须填写 speaker" in result.stderr


def test_explicit_cognitive_predicate_requires_speaker_even_when_actualized(
    tmp_path: Path,
) -> None:
    fact_texts = (
        "萧景认为秦守诚已经离开宗门。",
        "萧景知道秦守诚已经离开宗门。",
        "萧景发现秦守诚已经离开宗门。",
        "萧景意识到秦守诚已经离开宗门。",
        "萧景怀疑秦守诚已经离开宗门。",
        "萧景误以为秦守诚已经离开宗门。",
    )
    for index, fact_text in enumerate(fact_texts, 1):
        case = prepare_case(
            tmp_path / str(index),
            status="已发生",
            fact_text=fact_text,
        )
        result = run_tool(case, "validate")
        assert result.returncode == 1
        assert "认知事实，必须填写 speaker" in result.stderr


def test_explicit_cognitive_predicate_with_speaker_passes_hard_gate(
    tmp_path: Path,
) -> None:
    case = prepare_case(
        tmp_path,
        status="已发生",
        fact_text="萧景发现秦守诚已经离开宗门。",
        speaker="萧景",
    )
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr


def test_actuality_risk_word_is_warning_not_failure(tmp_path: Path) -> None:
    case = prepare_case(tmp_path, status="已发生", fact_text="萧景可能已经离开宗门。")
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert len(receipt["warnings"]) == 1
    assert "可能" in receipt["warnings"][0]


def test_background_source_sha_must_match_real_file(tmp_path: Path) -> None:
    case = prepare_case(tmp_path)
    case["source_index"].write_text(
        case["source_index"].read_text(encoding="utf-8").replace("a", "b", 1),
        encoding="utf-8",
    )
    result = run_tool(case, "validate")
    assert result.returncode == 1


def test_gold_atom_occurrence_must_exist_in_chapter(tmp_path: Path) -> None:
    case = prepare_case(tmp_path)
    row = json.loads(case["annotations"].read_text(encoding="utf-8"))
    row["gold_atoms"][0]["evidence_occurrence"] = 2
    case["annotations"].write_text(compact(row) + "\n", encoding="utf-8")
    result = run_tool(case, "validate")
    assert result.returncode == 1
    assert "原文出现次数不存在" in result.stderr


def test_facts_only_mode_accepts_light_self_review_return(tmp_path: Path) -> None:
    case = prepare_case(tmp_path)
    row = json.loads(case["annotations"].read_text(encoding="utf-8"))
    row.pop("gold_atoms")
    ordered = {
        key: row[key] for key in ("sample_id", "source_file", "facts", "quality")
    }
    case["annotations"].write_text(compact(ordered) + "\n", encoding="utf-8")
    result = run_tool(case, "validate", "--facts-only")
    assert result.returncode == 0, result.stderr


def test_evidence_over_two_sentences_is_failure(tmp_path: Path) -> None:
    case = prepare_case(tmp_path)
    evidence = "萧景收好行囊。萧景离开宗门。秦守诚留在山门前。"
    case["chapter"].write_text(evidence + "\n", encoding="utf-8")
    row = json.loads(case["annotations"].read_text(encoding="utf-8"))
    row["facts"][0]["evidence"] = evidence
    row["gold_atoms"][0]["evidence"] = evidence
    case["annotations"].write_text(compact(row) + "\n", encoding="utf-8")

    result = run_tool(case, "validate")
    assert result.returncode == 1
    assert "超过 2 句上限" in result.stderr


def test_evidence_at_two_sentences_is_allowed(tmp_path: Path) -> None:
    case = prepare_case(tmp_path)
    evidence = "萧景收好行囊。萧景离开宗门。"
    case["chapter"].write_text(evidence + "秦守诚留在山门前。\n", encoding="utf-8")
    row = json.loads(case["annotations"].read_text(encoding="utf-8"))
    row["facts"][0]["evidence"] = evidence
    row["gold_atoms"][0]["evidence"] = evidence
    case["annotations"].write_text(compact(row) + "\n", encoding="utf-8")

    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr


def test_question_exclamation_pair_and_closing_quote_count_as_one_sentence_end(
    tmp_path: Path,
) -> None:
    case = prepare_case(tmp_path)
    evidence = "萧景问：‘真的？！’秦守诚点头。"
    case["chapter"].write_text(evidence + "\n", encoding="utf-8")
    row = json.loads(case["annotations"].read_text(encoding="utf-8"))
    row["facts"][0]["evidence"] = evidence
    row["gold_atoms"][0]["evidence"] = evidence
    case["annotations"].write_text(compact(row) + "\n", encoding="utf-8")

    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr


def test_speaker_rejects_multiple_people_and_generic_name(tmp_path: Path) -> None:
    for speaker in ("叶耀东、叶耀华", "叶耀东和叶耀华", "众人"):
        case = prepare_case(
            tmp_path / speaker,
            status="推测",
            fact_text="萧景怀疑自己已经离开宗门。",
            speaker=speaker,
        )
        result = run_tool(case, "validate")
        assert result.returncode == 1


def test_speaker_accepts_canonical_retelling_format_and_unknown_source(
    tmp_path: Path,
) -> None:
    for index, speaker in enumerate(("萧景（转述自秦守诚）", "来源不明", "老和尚"), 1):
        case = prepare_case(
            tmp_path / str(index),
            status="推测",
            fact_text="萧景听说秦守诚已经离开宗门。",
            speaker=speaker,
        )
        result = run_tool(case, "validate")
        assert result.returncode == 0, result.stderr


def test_speaker_rejects_noncanonical_retelling_parentheses(tmp_path: Path) -> None:
    case = prepare_case(
        tmp_path,
        status="推测",
        fact_text="萧景听说秦守诚已经离开宗门。",
        speaker="萧景（来自秦守诚）",
    )
    result = run_tool(case, "validate")
    assert result.returncode == 1
    assert "转述格式必须" in result.stderr


def test_speaker_rejects_work_title_as_person(tmp_path: Path) -> None:
    case = prepare_case(
        tmp_path,
        status="推测",
        fact_text="萧景听说秦守诚已经离开宗门。",
        speaker="《江湖志怪录》",
    )
    result = run_tool(case, "validate")
    assert result.returncode == 1
    assert "必须写人名" in result.stderr


def test_pure_narration_with_speaker_is_warning(tmp_path: Path) -> None:
    case = prepare_case(tmp_path, speaker="萧景")
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr
    warnings = json.loads(result.stdout)["warnings"]
    assert len(warnings) == 1
    assert "未命中来源或认知提示词" in warnings[0]
    assert "程序不据此判定语义" in warnings[0]


def test_canonical_narrative_speaker_is_warning_not_bulk_default(tmp_path: Path) -> None:
    case = prepare_case(tmp_path, speaker="旁白")
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr
    warnings = json.loads(result.stdout)["warnings"]
    assert any("纯叙述通常省略 speaker，不能批量补" in warning for warning in warnings)


def test_noncanonical_narrative_speaker_is_failure(tmp_path: Path) -> None:
    for speaker in ("叙述者", "物品说明"):
        case = prepare_case(tmp_path / speaker, speaker=speaker)
        result = run_tool(case, "validate")
        assert result.returncode == 1
        assert "统一写“旁白”" in result.stderr


def test_commitment_status_alone_does_not_force_speaker(tmp_path: Path) -> None:
    case = prepare_case(tmp_path, status="承诺", fact_text="萧景会保护山门。")
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr


def test_object_description_does_not_trigger_speaker_requirement(
    tmp_path: Path,
) -> None:
    case = prepare_case(tmp_path, fact_text="物品说明刻在石碑上。")
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["warnings"] == []


def test_speech_act_keywords_only_raise_semantic_candidates(tmp_path: Path) -> None:
    question = prepare_case(
        tmp_path / "question",
        status="推测",
        fact_text="萧景询问秦守诚是否可能离开宗门。",
        speaker="萧景",
    )
    question_result = run_tool(question, "validate")
    assert question_result.returncode == 0, question_result.stderr
    question_warnings = json.loads(question_result.stdout)["warnings"]
    assert any("若原文确为已说出口" in warning for warning in question_warnings)

    persuasion = prepare_case(
        tmp_path / "persuasion",
        status="计划",
        fact_text="萧景劝说秦守诚离开宗门。",
        speaker="萧景",
    )
    persuasion_result = run_tool(persuasion, "validate")
    assert persuasion_result.returncode == 0, persuasion_result.stderr
    persuasion_warnings = json.loads(persuasion_result.stdout)["warnings"]
    assert any("若原文确为已说出口" in warning for warning in persuasion_warnings)
    assert any("被交办人" in warning for warning in persuasion_warnings)

    evaluation = prepare_case(
        tmp_path / "evaluation",
        status="推测",
        fact_text="萧景评价秦守诚过于谨慎。",
        speaker="萧景",
    )
    evaluation_result = run_tool(evaluation, "validate")
    assert evaluation_result.returncode == 0, evaluation_result.stderr
    evaluation_warnings = json.loads(evaluation_result.stdout)["warnings"]
    assert any("若原文确为已说出口" in warning for warning in evaluation_warnings)


def test_speech_keyword_without_speaker_is_candidate_not_failure(tmp_path: Path) -> None:
    case = prepare_case(
        tmp_path,
        status="已发生",
        fact_text="萧景询问秦守诚是否离开宗门。",
    )
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr
    warnings = json.loads(result.stdout)["warnings"]
    assert any("请确认是否缺 speaker" in warning for warning in warnings)
    assert all("程序不据此判定语义" in warning for warning in warnings)


def test_completed_question_does_not_trigger_modality_warning(tmp_path: Path) -> None:
    case = prepare_case(
        tmp_path,
        status="已发生",
        fact_text="萧景询问秦守诚是否可能离开宗门。",
        speaker="萧景",
    )
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["warnings"] == []


def test_request_command_and_suggestion_candidates_do_not_hard_decide_status(
    tmp_path: Path,
) -> None:
    cases = (
        ("request", "萧景请求秦守诚离开宗门。", "计划"),
        ("command", "萧景命令秦守诚离开宗门。", "条件"),
        ("suggestion", "萧景建议秦守诚离开宗门。", "否定"),
    )
    for name, fact_text, status in cases:
        case = prepare_case(
            tmp_path / name,
            status=status,
            fact_text=fact_text,
            speaker="萧景",
        )
        result = run_tool(case, "validate")
        assert result.returncode == 0, result.stderr
        warnings = json.loads(result.stdout)["warnings"]
        assert any("候选标红" in warning for warning in warnings)
        assert any("若原文确为已说出口" in warning for warning in warnings)
        assert any("被交办人" in warning for warning in warnings)


def test_directive_is_not_automatically_a_condition(tmp_path: Path) -> None:
    case = prepare_case(
        tmp_path,
        status="条件",
        fact_text="掌柜指示阿青明早开门。",
        speaker="掌柜",
    )
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr
    warnings = json.loads(result.stdout)["warnings"]
    assert any("不只是指示、未来时间或交办" in warning for warning in warnings)


def test_explicit_condition_without_directive_needs_no_keyword_warning(
    tmp_path: Path,
) -> None:
    case = prepare_case(
        tmp_path,
        status="条件",
        fact_text="如果天亮，萧景就离开宗门。",
    )
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["warnings"] == []


def test_ambiguous_let_word_is_candidate_not_semantic_failure(tmp_path: Path) -> None:
    case = prepare_case(
        tmp_path,
        status="正在发生",
        fact_text="山风让木门响个不停。",
    )
    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr
    warnings = json.loads(result.stdout)["warnings"]
    assert any("让" in warning for warning in warnings)
    assert all("程序不据此判定语义" in warning for warning in warnings)


def test_planned_question_and_refused_evaluation_are_not_completed_speech_acts(
    tmp_path: Path,
) -> None:
    planned = prepare_case(
        tmp_path / "planned",
        status="计划",
        fact_text="萧景计划询问秦守诚是否离开宗门。",
    )
    planned_result = run_tool(planned, "validate")
    assert planned_result.returncode == 0, planned_result.stderr

    refused = prepare_case(
        tmp_path / "refused",
        status="否定",
        fact_text="萧景拒绝评价秦守诚。",
    )
    refused_result = run_tool(refused, "validate")
    assert refused_result.returncode == 0, refused_result.stderr


def test_reused_evidence_is_warning(tmp_path: Path) -> None:
    case = prepare_case(tmp_path)
    row = json.loads(case["annotations"].read_text(encoding="utf-8"))
    second_fact = {
        "fact": "宗门已经空了。",
        "status": "已发生",
        "evidence": "萧景离开了宗门",
    }
    row["facts"].append(second_fact)
    row["gold_atoms"].append(
        {
            "atom_id": "S001-F002",
            "fact": second_fact["fact"],
            "status": second_fact["status"],
            "evidence": second_fact["evidence"],
            "speaker": None,
            "evidence_occurrence": 1,
            "claim_chain": [],
        }
    )
    row["quality"]["fact_count"] = 2
    case["annotations"].write_text(compact(row) + "\n", encoding="utf-8")

    result = run_tool(case, "validate")
    assert result.returncode == 0, result.stderr
    warnings = json.loads(result.stdout)["warnings"]
    assert any("共用完全相同的 evidence" in warning for warning in warnings)

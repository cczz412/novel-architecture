from __future__ import annotations

import ast
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.v02

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C12_6_program_generated_state_machine_benchmark_20260725"
    / "program/v02_c12_6_state_machine_benchmark.py"
)
SPEC = importlib.util.spec_from_file_location("v02_c12_6_benchmark", PROGRAM)
assert SPEC is not None and SPEC.loader is not None
sys.dont_write_bytecode = True
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def _sample(
    seed: str = benchmark.ROOT_SEED,
) -> tuple[dict, dict, dict, list[dict], str]:
    ledger, snapshots = benchmark._build_canonical_ledger(seed)
    corpus, evidence, readable_story = benchmark._render_corpus(ledger)
    oracle = benchmark._compile_oracle(
        ledger=ledger,
        corpus=corpus,
        evidence_by_fact=evidence,
    )
    return ledger, corpus, oracle, snapshots, readable_story


def _verify(
    ledger: dict,
    corpus: dict,
    oracle: dict,
    snapshots: list[dict],
    readable_story: str,
) -> dict:
    return benchmark.verify_generated_sample(
        ledger=ledger,
        corpus=corpus,
        oracle=oracle,
        snapshots=snapshots,
        readable_story=readable_story,
    )


def test_exact_30_chapters_80_facts_and_all_pilot_phenomena() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    receipt = _verify(ledger, corpus, oracle, snapshots, readable_story)

    assert corpus["chapter_total"] == 30
    assert oracle["fact_total"] == 80
    assert len(snapshots) == 30
    assert sum(len(row["fact_ids"]) for row in corpus["chapters"]) == 80
    assert set(oracle["phenomenon_counts"]) == set(benchmark.EVENT_TYPES)
    assert set(oracle["phenomenon_counts"].values()) == {5}
    assert receipt["claim_span_backpaste"] == {
        "passed": 80,
        "total": 80,
        "rate": 1.0,
    }
    assert receipt["chapter_end_snapshot_replay"] == {
        "passed": 30,
        "total": 30,
        "rate": 1.0,
    }
    assert receipt["frozen_payload_digests_applicable"] is True
    assert receipt["frozen_payload_digests_verified"] is True


def test_same_seed_is_byte_stable_and_different_seed_changes_sample() -> None:
    first_files, first_manifest = benchmark.build_artifacts()
    second_files, second_manifest = benchmark.build_artifacts()
    assert first_files == second_files
    assert first_manifest == second_manifest

    changed = benchmark._build_payload_objects("C12.6-DIFFERENT-SEED")
    assert (
        benchmark.canonical_bytes(
            changed["sealed/synthetic_corpus_v1.json"]
        )
        != first_files["sealed/synthetic_corpus_v1.json"]
    )
    changed_receipt = changed["receipts/oracle_closure_receipt.json"]
    assert changed_receipt["chapter_total"] == 30
    assert changed_receipt["fact_total"] == 80
    assert changed_receipt["frozen_payload_digests_applicable"] is False
    assert changed_receipt["frozen_payload_digests_verified"] is False


def test_oracle_is_compiled_from_ledger_and_has_strict_shape() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    benchmark._validate_oracle_shape(oracle)
    assert [row["fact_id"] for row in ledger["facts"]] == [
        row["fact_id"] for row in oracle["facts"]
    ]
    assert all("render_template_id" not in row for row in oracle["facts"])
    assert all("render_payload" not in row for row in oracle["facts"])
    fact_contract = benchmark.build_oracle_schema()["properties"]["facts"][
        "items"
    ]
    assert set(fact_contract["properties"]) == set(oracle["facts"][0])

    bad = copy.deepcopy(oracle)
    bad["unexpected"] = True
    with pytest.raises(benchmark.BenchmarkError, match="顶层字段"):
        benchmark._validate_oracle_shape(bad)

    _verify(ledger, corpus, oracle, snapshots, readable_story)

    semantic_drift = copy.deepcopy(oracle)
    semantic_drift["facts"][0]["semantic_frame"]["predicate"] = "wrong"
    with pytest.raises(benchmark.BenchmarkError, match="语义载荷偏离"):
        _verify(ledger, corpus, semantic_drift, snapshots, readable_story)

    invalid_actuality_ledger = copy.deepcopy(ledger)
    invalid_actuality = copy.deepcopy(oracle)
    invalid_actuality_ledger["facts"][0]["actuality"] = "BOGUS"
    invalid_actuality["facts"][0]["actuality"] = "BOGUS"
    with pytest.raises(benchmark.BenchmarkError, match="严格Schema"):
        _verify(
            invalid_actuality_ledger,
            corpus,
            invalid_actuality,
            snapshots,
            readable_story,
        )


def test_claim_spans_are_exact_coordinate_authority_not_string_search() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    for fact in oracle["facts"]:
        chapter = next(
            row
            for row in corpus["chapters"]
            if row["chapter_id"] == fact["chapter_id"]
        )
        evidence = fact["evidence"]
        assert (
            chapter["text"][
                evidence["start_char"] : evidence["end_char_exclusive"]
            ]
            == evidence["claim_span"]
        )

    bad = copy.deepcopy(oracle)
    bad["facts"][0]["evidence"]["start_char"] += 1
    with pytest.raises(benchmark.BenchmarkError, match="无法逐字回贴"):
        _verify(ledger, corpus, bad, snapshots, readable_story)


def test_replay_rejects_wrong_before_or_broken_predecessor() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    wrong_ledger = copy.deepcopy(ledger)
    wrong_before = copy.deepcopy(oracle)
    wrong_ledger["facts"][0]["mutations"][0]["before"] = "L99"
    wrong_before["facts"][0]["mutations"][0]["before"] = "L99"
    with pytest.raises(
        benchmark.BenchmarkError,
        match="before不一致|移动事实",
    ):
        _verify(
            wrong_ledger,
            corpus,
            wrong_before,
            snapshots,
            readable_story,
        )

    broken_ledger = copy.deepcopy(ledger)
    broken = copy.deepcopy(oracle)
    broken_index = next(
        index
        for index, fact in enumerate(broken["facts"])
        if any(
            mutation["predecessor_fact_id"] is not None
            for mutation in fact["mutations"]
        )
    )
    oracle_mutation = next(
        mutation
        for mutation in broken["facts"][broken_index]["mutations"]
        if mutation["predecessor_fact_id"] is not None
    )
    ledger_mutation = next(
        mutation
        for mutation in broken_ledger["facts"][broken_index]["mutations"]
        if mutation["predecessor_fact_id"] is not None
    )
    oracle_mutation["predecessor_fact_id"] = "F999"
    ledger_mutation["predecessor_fact_id"] = "F999"
    with pytest.raises(
        benchmark.BenchmarkError,
        match="前驱事实尚未出现|前驱事实不是同一路径",
    ):
        _verify(
            broken_ledger,
            corpus,
            broken,
            snapshots,
            readable_story,
        )


def test_non_world_actualities_cannot_pollute_current_world_state() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    for actuality in benchmark.NON_WORLD_ACTUALITIES:
        rows = [row for row in oracle["facts"] if row["actuality"] == actuality]
        assert rows
        assert all(
            not any(mutation["path"][0] == "world" for mutation in row["mutations"])
            for row in rows
        )

    bad = copy.deepcopy(oracle)
    bad_ledger = copy.deepcopy(ledger)
    plan = next(row for row in bad["facts"] if row["actuality"] == "PLANNED")
    ledger_plan = next(
        row
        for row in bad_ledger["facts"]
        if row["actuality"] == "PLANNED"
    )
    plan["updates_world_state"] = True
    ledger_plan["updates_world_state"] = True
    with pytest.raises(
        benchmark.BenchmarkError,
        match="语义组合合同|世界状态标记",
    ):
        _verify(
            bad_ledger,
            corpus,
            bad,
            snapshots,
            readable_story,
        )


def test_event_type_rejects_legal_but_wrong_actuality_combination() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    ledger_negation = next(
        row
        for row in bad_ledger["facts"]
        if row["event_type"] == "NEGATION"
    )
    oracle_negation = next(
        row
        for row in bad_oracle["facts"]
        if row["fact_id"] == ledger_negation["fact_id"]
    )
    ledger_negation["actuality"] = "OCCURRED"
    oracle_negation["actuality"] = "OCCURRED"
    with pytest.raises(benchmark.BenchmarkError, match="语义组合合同"):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_negation_semantic_object_must_match_text_and_object_refs() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    ledger_negation = next(
        row
        for row in bad_ledger["facts"]
        if row["event_type"] == "NEGATION"
    )
    oracle_negation = next(
        row
        for row in bad_oracle["facts"]
        if row["fact_id"] == ledger_negation["fact_id"]
    )
    ledger_negation["semantic_frame"]["object"] = "L99"
    oracle_negation["semantic_frame"]["object"] = "L99"
    with pytest.raises(benchmark.BenchmarkError, match="主体或对象"):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_correction_keeps_history_but_retracts_false_belief() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    corrections = [
        row for row in oracle["facts"] if row["event_type"] == "CORRECTION"
    ]
    assert len(corrections) == 5
    fact_ids = {row["fact_id"] for row in oracle["facts"]}
    assert all(row["invalidates_fact_id"] in fact_ids for row in corrections)
    assert all(
        {mutation["after"] for mutation in row["mutations"]}
        == {"RETRACTED_FALSE", "KNOWN_TRUE"}
        for row in corrections
    )
    _verify(ledger, corpus, oracle, snapshots, readable_story)


def test_correction_rejects_unrelated_existing_fact() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    ledger_correction = next(
        row
        for row in bad_ledger["facts"]
        if row["event_type"] == "CORRECTION"
    )
    oracle_correction = next(
        row
        for row in bad_oracle["facts"]
        if row["event_type"] == "CORRECTION"
    )
    ledger_correction["invalidates_fact_id"] = "F001"
    oracle_correction["invalidates_fact_id"] = "F001"
    with pytest.raises(benchmark.BenchmarkError, match="对应谎言"):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_flashback_time_and_same_name_entities_stay_separate() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    flashbacks = [
        row for row in oracle["facts"] if row["actuality"] == "FLASHBACK"
    ]
    assert len(flashbacks) == 5
    assert all(
        row["story_time"][0] < row["recorded_at_chapter"]
        and row["updates_world_state"] is False
        for row in flashbacks
    )
    assert oracle["entity_registry"]["E05"]["display_name"] == "苏禾"
    assert oracle["entity_registry"]["E06"]["display_name"] == "苏禾"
    assert (
        oracle["entity_registry"]["E05"]["qualifier"]
        != oracle["entity_registry"]["E06"]["qualifier"]
    )
    assert (
        oracle["entity_registry"]["E05"]["identity_binding_sha256"]
        != oracle["entity_registry"]["E06"]["identity_binding_sha256"]
    )
    _verify(ledger, corpus, oracle, snapshots, readable_story)


def test_same_name_mutation_path_cannot_cross_entities() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    ledger_alias = next(
        row
        for row in bad_ledger["facts"]
        if row["event_type"] == "ALIAS"
        and row["semantic_frame"]["subject"] == "E06"
    )
    oracle_alias = next(
        row
        for row in bad_oracle["facts"]
        if row["fact_id"] == ledger_alias["fact_id"]
    )
    ledger_alias["mutations"][0]["path"][-1] = "E05"
    oracle_alias["mutations"][0]["path"][-1] = "E05"
    with pytest.raises(benchmark.BenchmarkError, match="错误实体"):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_identity_update_flag_must_match_identity_mutation() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    ledger_alias = next(
        row
        for row in bad_ledger["facts"]
        if row["event_type"] == "ALIAS"
    )
    oracle_alias = next(
        row
        for row in bad_oracle["facts"]
        if row["fact_id"] == ledger_alias["fact_id"]
    )
    ledger_alias["updates_identity_state"] = False
    oracle_alias["updates_identity_state"] = False
    with pytest.raises(
        benchmark.BenchmarkError,
        match="语义组合合同|身份状态标记",
    ):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_flashback_requires_independent_historical_scope() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    ledger_flashback = next(
        row
        for row in bad_ledger["facts"]
        if row["event_type"] == "FLASHBACK"
    )
    oracle_flashback = next(
        row
        for row in bad_oracle["facts"]
        if row["fact_id"] == ledger_flashback["fact_id"]
    )
    ledger_flashback["scope"]["policy_scope_id"] = benchmark.SCOPE[
        "policy_scope_id"
    ]
    oracle_flashback["scope"]["policy_scope_id"] = benchmark.SCOPE[
        "policy_scope_id"
    ]
    with pytest.raises(benchmark.BenchmarkError, match="独立历史作用域"):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_epistemic_states_are_explicitly_supported_by_story_text() -> None:
    _ledger, _corpus, oracle, _snapshots, _readable_story = _sample()
    expected_phrases = {
        "RUMOR": "仍信以为真",
        "LIE": "对方信了这个说法",
        "CORRECTION": "对方接受更正",
    }
    for event_type, phrase in expected_phrases.items():
        rows = [
            row for row in oracle["facts"] if row["event_type"] == event_type
        ]
        assert len(rows) == 5
        assert all(phrase in row["evidence"]["claim_span"] for row in rows)


@pytest.mark.parametrize(
    ("event_type", "field", "bad_value"),
    [
        ("RUMOR", "truth", "TRUE"),
        ("OBSERVE", "truth", "FALSE"),
        ("LIE", "claimed_owner", "E04"),
    ],
)
def test_semantic_frame_values_cannot_self_certify_against_unchanged_text(
    event_type: str,
    field: str,
    bad_value: str,
) -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    ledger_fact = next(
        row
        for row in bad_ledger["facts"]
        if row["event_type"] == event_type
    )
    oracle_fact = next(
        row
        for row in bad_oracle["facts"]
        if row["fact_id"] == ledger_fact["fact_id"]
    )
    ledger_fact["semantic_frame"][field] = bad_value
    oracle_fact["semantic_frame"][field] = bad_value
    if event_type == "LIE":
        ledger_fact["subject_entity_ids"][-1] = bad_value
        oracle_fact["subject_entity_ids"][-1] = bad_value
    with pytest.raises(
        benchmark.BenchmarkError,
        match="语义值不闭合|正文逐项托住|观察事实",
    ):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_inform_owner_role_cannot_swap_when_all_names_remain_in_text() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    ledger_fact = next(
        row
        for row in bad_ledger["facts"]
        if row["event_type"] == "INFORM"
    )
    oracle_fact = next(
        row
        for row in bad_oracle["facts"]
        if row["fact_id"] == ledger_fact["fact_id"]
    )
    original_owner = ledger_fact["semantic_frame"]["owner"]
    swapped_owner = next(
        entity_id
        for entity_id in ledger_fact["subject_entity_ids"]
        if entity_id != original_owner
    )
    ledger_fact["semantic_frame"]["owner"] = swapped_owner
    oracle_fact["semantic_frame"]["owner"] = swapped_owner

    with pytest.raises(benchmark.BenchmarkError, match="角色化正文合同"):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_inform_speaker_and_recipient_roles_cannot_swap() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    ledger_fact = next(
        row
        for row in bad_ledger["facts"]
        if row["event_type"] == "INFORM"
    )
    oracle_fact = next(
        row
        for row in bad_oracle["facts"]
        if row["fact_id"] == ledger_fact["fact_id"]
    )
    for fact in (ledger_fact, oracle_fact):
        speaker = fact["semantic_frame"]["speaker"]
        recipient = fact["semantic_frame"]["recipient"]
        fact["semantic_frame"]["speaker"] = recipient
        fact["semantic_frame"]["recipient"] = speaker
        fact["subject_entity_ids"] = [
            recipient,
            speaker,
        ]
        fact["mutations"][0]["path"][2] = speaker
    ledger_fact["render_payload"]["subject_entity_ids"] = list(
        ledger_fact["subject_entity_ids"]
    )

    with pytest.raises(benchmark.BenchmarkError, match="角色化正文合同"):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_alias_requires_exact_quoted_name_not_substring() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    ledger_alias = next(
        row
        for row in bad_ledger["facts"]
        if row["event_type"] == "ALIAS"
        and len(row["semantic_frame"]["object"]) > 1
    )
    oracle_alias = next(
        row
        for row in bad_oracle["facts"]
        if row["fact_id"] == ledger_alias["fact_id"]
    )
    shortened_alias = ledger_alias["semantic_frame"]["object"][-1]
    for fact in (ledger_alias, oracle_alias):
        fact["semantic_frame"]["object"] = shortened_alias
        fact["object_refs"] = [shortened_alias]
        fact["mutations"][0]["after"] = [shortened_alias]
    ledger_alias["render_payload"]["object_refs"] = [shortened_alias]

    with pytest.raises(benchmark.BenchmarkError, match="角色化正文合同"):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


@pytest.mark.parametrize(
    ("field", "bad_value", "error"),
    [
        ("recorded_at_chapter", 2, "记录章次"),
        ("story_time", [2, 0, 2, 0], "故事时间"),
        ("supersedes_fact_id", "F001", "替代关系"),
        ("invalidates_fact_id", "F001", "作废关系"),
    ],
)
def test_generated_metadata_cannot_self_certify_with_oracle(
    field: str,
    bad_value: object,
    error: str,
) -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    fact_id = "F001" if field in {"recorded_at_chapter", "story_time"} else "F017"
    ledger_fact = next(
        row for row in bad_ledger["facts"] if row["fact_id"] == fact_id
    )
    oracle_fact = next(
        row for row in bad_oracle["facts"] if row["fact_id"] == fact_id
    )
    ledger_fact[field] = bad_value
    oracle_fact[field] = bad_value

    with pytest.raises(benchmark.BenchmarkError, match=error):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_narrative_index_must_equal_fact_position() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    for facts in (bad_ledger["facts"], bad_oracle["facts"]):
        first = next(row for row in facts if row["fact_id"] == "F003")
        second = next(row for row in facts if row["fact_id"] == "F004")
        first["narrative_index"], second["narrative_index"] = (
            second["narrative_index"],
            first["narrative_index"],
        )
        first["story_time"], second["story_time"] = (
            second["story_time"],
            first["story_time"],
        )

    with pytest.raises(benchmark.BenchmarkError, match="事实顺序"):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


@pytest.mark.parametrize("attack", ["operation", "predecessor"])
def test_mutation_relation_is_independently_rebuilt(attack: str) -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_oracle = copy.deepcopy(oracle)
    fact_id = "F001" if attack == "operation" else "F017"
    ledger_fact = next(
        row for row in bad_ledger["facts"] if row["fact_id"] == fact_id
    )
    oracle_fact = next(
        row for row in bad_oracle["facts"] if row["fact_id"] == fact_id
    )
    if attack == "operation":
        ledger_fact["mutations"][0]["operation"] = "TRANSFER"
        oracle_fact["mutations"][0]["operation"] = "TRANSFER"
        error = "状态操作类型"
    else:
        ledger_fact["mutations"][0]["predecessor_fact_id"] = "F001"
        oracle_fact["mutations"][0]["predecessor_fact_id"] = "F001"
        error = "前驱事实不是同一路径"

    with pytest.raises(benchmark.BenchmarkError, match=error):
        _verify(
            bad_ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_source_block_id_is_bound_to_chapter_local_position() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_oracle = copy.deepcopy(oracle)
    bad_oracle["facts"][0]["evidence"]["source_block_id"] = "C99-L99"

    with pytest.raises(benchmark.BenchmarkError, match="证据块号"):
        _verify(
            ledger,
            corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )


def test_fixed_seed_and_chapter_density_cannot_drift() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    bad_corpus = copy.deepcopy(corpus)
    bad_oracle = copy.deepcopy(oracle)
    bad_ledger["root_seed"] = "OTHER-SEED"
    other_seed_sha = benchmark.sha256_bytes(b"OTHER-SEED")
    bad_corpus["root_seed_sha256"] = other_seed_sha
    bad_oracle["root_seed_sha256"] = other_seed_sha

    with pytest.raises(benchmark.BenchmarkError, match="固定基准身份"):
        _verify(
            bad_ledger,
            bad_corpus,
            bad_oracle,
            snapshots,
            readable_story,
        )

    bad_ledger = copy.deepcopy(ledger)
    bad_ledger["chapter_fact_counts"] = {1: benchmark.FACT_TOTAL}
    with pytest.raises(benchmark.BenchmarkError, match="固定基准身份"):
        _verify(
            bad_ledger,
            corpus,
            oracle,
            snapshots,
            readable_story,
        )


def test_fixed_seed_rejects_fully_synchronized_semantic_rewrite() -> None:
    ledger, _corpus, _oracle, snapshots, _readable_story = _sample()
    bad_ledger = copy.deepcopy(ledger)
    fact = next(
        row
        for row in bad_ledger["facts"]
        if row["fact_id"] == "F010"
    )
    fact["semantic_frame"]["subject"] = "E02"
    fact["subject_entity_ids"] = ["E02"]
    fact["render_payload"]["subject_entity_ids"] = ["E02"]
    location = benchmark.LOCATIONS[fact["semantic_frame"]["object"]]
    fact["sentence"] = f"沈舟没有前往{location}。"
    bad_corpus, bad_evidence, bad_story = benchmark._render_corpus(
        bad_ledger
    )
    bad_oracle = benchmark._compile_oracle(
        ledger=bad_ledger,
        corpus=bad_corpus,
        evidence_by_fact=bad_evidence,
    )

    with pytest.raises(benchmark.BenchmarkError, match="整包指纹漂移"):
        _verify(
            bad_ledger,
            bad_corpus,
            bad_oracle,
            snapshots,
            bad_story,
        )


def test_corpus_fact_total_is_not_self_reported() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_corpus = copy.deepcopy(corpus)
    bad_corpus["fact_total"] = benchmark.FACT_TOTAL - 1

    with pytest.raises(benchmark.BenchmarkError, match="语料声明事实数"):
        _verify(
            ledger,
            bad_corpus,
            oracle,
            snapshots,
            readable_story,
        )


def test_snapshot_metadata_is_closed_not_only_snapshot_state() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    bad_snapshots = copy.deepcopy(snapshots)
    bad_snapshots[0]["after_fact_id"] = "F080"

    with pytest.raises(benchmark.BenchmarkError, match="快照元数据"):
        _verify(
            ledger,
            corpus,
            oracle,
            bad_snapshots,
            readable_story,
        )


def test_model_visible_packet_is_physically_separated_and_truth_free() -> None:
    objects = benchmark._build_payload_objects()
    packet = objects[benchmark.PUBLIC_PACKET_PATH]
    access = objects["input_access_manifest_v1.json"]
    corpus = objects["sealed/synthetic_corpus_v1.json"]

    assert access["model_visible_paths"] == [benchmark.PUBLIC_PACKET_PATH]
    assert set(access["model_visible_paths"]).isdisjoint(
        access["sealed_truth_paths"]
    )
    assert access["mixed_public_and_sealed_packet_forbidden"] is True
    assert packet["sealed_truth_included"] is False
    assert benchmark.TRUTH_ID_RE.findall(
        benchmark.canonical_bytes(packet).decode("utf-8")
    ) == []

    leaked = copy.deepcopy(packet)
    leaked["chapters"][0]["text"] += " E01"
    with pytest.raises(benchmark.BenchmarkError, match="泄漏真值"):
        benchmark._validate_model_visible_packet(
            corpus=corpus,
            packet=leaked,
        )


def test_mutations_reject_duplicate_fact_and_orphan_correction() -> None:
    ledger, corpus, oracle, snapshots, readable_story = _sample()
    duplicate = copy.deepcopy(oracle)
    duplicate["facts"][1]["fact_id"] = duplicate["facts"][0]["fact_id"]
    with pytest.raises(benchmark.BenchmarkError, match="事实ID不唯一"):
        _verify(ledger, corpus, duplicate, snapshots, readable_story)

    orphan = copy.deepcopy(oracle)
    correction = next(
        row for row in orphan["facts"] if row["event_type"] == "CORRECTION"
    )
    correction["invalidates_fact_id"] = "F999"
    with pytest.raises(benchmark.BenchmarkError, match="孤儿事实"):
        _verify(ledger, corpus, orphan, snapshots, readable_story)


def test_limitations_are_machine_fields_not_only_prose() -> None:
    objects = benchmark._build_payload_objects()
    manifest_files, manifest_raw = benchmark.build_artifacts()
    manifest = json.loads(manifest_raw)
    oracle = objects["sealed/oracle_manifest_v1.json"]
    limitations = oracle["limitations"]

    assert limitations["pilot_foundation_only"] is True
    assert limitations["meets_full_x06_acceptance"] is False
    assert limitations["templated_text_systematically_overestimates"] is True
    assert limitations["substitute_for_real_chapters"] is False
    assert limitations["same_name_world_or_epistemic_exercise_included"] is False
    assert limitations["quality_result_registered"] is False
    assert benchmark.LIMITATION_TEXT in manifest_files["C12_6_stop_receipt.md"].decode()
    assert manifest["quality_result_registered"] is False
    assert manifest["winner"] is None
    assert manifest["c13_touched"] is False


def test_bundle_is_closed_binds_implementation_and_survives_import_cache() -> None:
    files, manifest_raw = benchmark.build_artifacts()
    manifest = json.loads(manifest_raw)
    listed = {row["path"]: row["sha256"] for row in manifest["files"]}
    assert set(listed) == set(files)
    assert all(
        listed[name] == benchmark.sha256_bytes(raw) for name, raw in files.items()
    )
    binding = json.loads(files["receipts/implementation_binding_receipt.json"])
    assert binding["program"]["sha256"] == benchmark.sha256_file(PROGRAM)
    assert binding["test"]["sha256"] == benchmark.sha256_file(Path(__file__))
    double_run = json.loads(files["receipts/double_run_receipt.json"])
    assert double_run["independent_rebuild_count"] == 2
    assert double_run["byte_identical"] is True

    cache_file = (
        benchmark.OUTPUT_DIR
        / "program/__pycache__/c12_6_runtime_cache_regression.pyc"
    )
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(b"runtime cache")
    try:
        assert benchmark._is_ignorable_runtime_cache(
            cache_file.relative_to(benchmark.OUTPUT_DIR)
        )
        assert not benchmark._is_ignorable_runtime_cache(
            Path("program/unexpected.json")
        )
        assert benchmark.check_bundle()["quality_result_registered"] is False
    finally:
        cache_file.unlink(missing_ok=True)


def test_no_model_api_or_network_dependency_and_no_c13_read_path() -> None:
    tree = ast.parse(PROGRAM.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported.isdisjoint(
        {"requests", "httpx", "urllib", "socket", "openai", "anthropic"}
    )
    assert benchmark.OUTPUT_DIR.name.startswith("V02_C12_6")
    assert benchmark.OUTPUT_DIR != (
        ROOT
        / "experiments/extraction_redesign_v02_overnight_20260725"
        / "V02_C13_downstream_consumer_20260725"
    )
    assert benchmark.build_artifacts()[1]

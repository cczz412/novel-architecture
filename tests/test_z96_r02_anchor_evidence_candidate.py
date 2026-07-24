from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from experiments.Z96_anchor_layer_evidence_closure_r02_20260724 import pipeline
from experiments.Z96_anchor_layer_evidence_closure_r02_20260724 import (
    stage_runtime,
)
from experiments.Z96_anchor_layer_evidence_closure_r02_20260724.core import (
    Z96CoreError,
    apply_empirical_token_upper_bound,
    audit_render,
    recall_anchor_candidates,
    render_candidate,
    score_recall,
    sha256_bytes,
    split_atomic_claims,
    stable_json_bytes,
    validate_candidate_input,
)
from experiments.Z96_anchor_layer_evidence_closure_r02_20260724.stage_runtime import (
    StageReader,
    StageRuntimeError,
)


def _catalog(size: int) -> list[dict[str, object]]:
    return [
        {
            "anchor_id": f"E{index:04d}",
            "order": index,
            "quote": f"q{index:04d}",
        }
        for index in range(size)
    ]


@pytest.mark.parametrize(
    "candidate_input",
    [
        {"necessary_anchor_ids": ["E0001"]},
        {"nested": {"missing_required_anchor_ids": ["E0002"]}},
        {"EXPECTED_VERDICT": "PASS"},
        {"trace": [{"reason": "答案衍生解释"}]},
    ],
)
def test_candidate_input_rejects_answer_derived_fields(
    candidate_input: dict[str, object],
) -> None:
    with pytest.raises(Z96CoreError, match="候选侧禁用键片段"):
        validate_candidate_input(candidate_input)


def test_answer_changes_cannot_change_frozen_candidate() -> None:
    claims = split_atomic_claims("CASE-01", "甲说明条件，乙执行行动。")
    catalog = [
        {"anchor_id": "E0001", "order": 0, "quote": "甲说明条件"},
        {"anchor_id": "E0002", "order": 1, "quote": "乙执行行动"},
        {"anchor_id": "E0003", "order": 2, "quote": "旁支信息"},
    ]
    candidate = {
        "case_id": "CASE-01",
        "catalog_order": ["E0001", "E0002", "E0003"],
        **recall_anchor_candidates(claims, ["E0001"], catalog),
    }
    frozen_candidate = stable_json_bytes(candidate)

    answer = {"required_anchor_ids": ["E0001", "E0002"]}
    score_recall(candidate, answer)
    answer["required_anchor_ids"] = ["E0001", "E0003"]
    answer["offline_note"] = "评分答案已变化"
    score_recall(candidate, answer)

    rerun = {
        "case_id": "CASE-01",
        "catalog_order": ["E0001", "E0002", "E0003"],
        **recall_anchor_candidates(claims, ["E0001"], catalog),
    }
    assert stable_json_bytes(candidate) == frozen_candidate
    assert stable_json_bytes(rerun) == frozen_candidate
    assert b"offline_note" not in frozen_candidate


def test_atomic_claims_cover_source_exactly_and_never_carry_anchors() -> None:
    source = "甲先说明条件， 乙再行动；\n丙确认结果。"
    claims = split_atomic_claims("CASE-02", source)
    expected_keys = {
        "claim_id",
        "claim_text",
        "source_event_id",
        "source_start",
        "source_end",
    }

    assert "".join(str(row["claim_text"]) for row in claims) == source
    assert claims[0]["source_start"] == 0
    assert claims[-1]["source_end"] == len(source)
    assert all(set(row) == expected_keys for row in claims)
    assert all("anchor" not in key.casefold() for row in claims for key in row)
    assert all(
        claims[index]["source_end"] == claims[index + 1]["source_start"]
        for index in range(len(claims) - 1)
    )


def test_endpoint_pattern_detects_partial_interior_coverage() -> None:
    result = score_recall(
        {
            "case_id": "ENDPOINT-PARTIAL",
            "candidate_anchor_ids": ["E0001", "E0003", "E0005"],
            "catalog_order": [
                "E0001",
                "E0002",
                "E0003",
                "E0004",
                "E0005",
            ],
        },
        {
            "required_anchor_ids": [
                "E0001",
                "E0002",
                "E0003",
                "E0004",
                "E0005",
            ]
        },
    )

    assert result["status"] == "REJECT"
    assert result["endpoint_span_pattern"] is True
    assert result["recalled_required_anchor_ids"] == [
        "E0001",
        "E0003",
        "E0005",
    ]
    assert result["unrecalled_required_anchor_ids"] == ["E0002", "E0004"]


def test_endpoint_pattern_uses_catalog_order_not_anchor_id_sorting() -> None:
    result = score_recall(
        {
            "case_id": "ORDER-MISMATCH",
            "candidate_anchor_ids": ["E0009", "E0008"],
            "catalog_order": ["E0009", "E0001", "E0008"],
        },
        {"required_anchor_ids": ["E0009", "E0001", "E0008"]},
    )
    assert result["endpoint_span_pattern"] is True
    assert result["unrecalled_required_anchor_ids"] == ["E0001"]


def test_render_audit_rejects_add_delete_change_and_duplicate() -> None:
    source = "甲先行动，乙后响应。"
    claims = split_atomic_claims("CASE-03", source)
    rendered = render_candidate(
        claims,
        {
            "case_id": "CASE-03",
            "candidate_anchor_ids": ["E0001"],
            "evidence_islands": [],
        },
    )
    expectation = {
        "case_id": "CASE-03",
        "source_event_text": source,
        "source_event_sha256": sha256_bytes(source.encode("utf-8")),
        "claims": claims,
    }
    assert audit_render(rendered, expectation)["status"] == "PASS"

    added = copy.deepcopy(rendered)
    added["rendered_records"].append(
        {
            "claim_id": "CASE-03:CLAIM-999",
            "claim_text": "新增。",
            "source_event_id": "CASE-03",
            "source_start": len(source),
            "source_end": len(source) + 3,
            "anchor_ids": ["E0001"],
        }
    )
    deleted = copy.deepcopy(rendered)
    deleted["rendered_records"].pop()
    changed = copy.deepcopy(rendered)
    changed["rendered_records"][0]["claim_text"] = "甲改写行动，"
    duplicated = copy.deepcopy(rendered)
    duplicated["rendered_records"].append(
        copy.deepcopy(duplicated["rendered_records"][0])
    )

    assert audit_render(added, expectation)["status"] == "REJECT"
    assert audit_render(deleted, expectation)["status"] == "REJECT"
    assert audit_render(changed, expectation)["status"] == "REJECT"
    duplicate_audit = audit_render(duplicated, expectation)
    assert duplicate_audit["status"] == "REJECT"
    assert duplicate_audit["checks"]["no_duplicates"] is False


def test_empirical_token_upper_bound_uses_frozen_formula() -> None:
    result = apply_empirical_token_upper_bound(
        "甲 乙\n丙",
        0.75,
        fixed_margin_tokens=64,
    )
    assert result == {
        "nonblank_character_count": 3,
        "tokens_per_nonblank_char_upper_bound": 0.75,
        "fixed_margin_tokens": 64,
        "token_upper_bound": 67,
    }


def test_evidence_islands_keep_independent_outer_boundaries() -> None:
    catalog = _catalog(81)
    claims = split_atomic_claims("CASE-04", "NO_MATCH_TOKEN")
    result = recall_anchor_candidates(
        claims,
        ["E0005", "E0075"],
        catalog,
    )

    assert result["candidate_anchor_ids"] == [
        "E0003",
        "E0004",
        "E0005",
        "E0006",
        "E0007",
        "E0073",
        "E0074",
        "E0075",
        "E0076",
        "E0077",
    ]
    assert result["evidence_islands"] == [
        {
            "island_id": "ISLAND-001",
            "anchor_ids": ["E0003", "E0004", "E0005", "E0006", "E0007"],
            "left_edge_anchor_id": "E0003",
            "right_edge_anchor_id": "E0007",
            "left_boundary_anchor_id": "E0002",
            "right_boundary_anchor_id": "E0008",
            "catalog_start_index": 3,
            "catalog_end_index": 7,
        },
        {
            "island_id": "ISLAND-002",
            "anchor_ids": ["E0073", "E0074", "E0075", "E0076", "E0077"],
            "left_edge_anchor_id": "E0073",
            "right_edge_anchor_id": "E0077",
            "left_boundary_anchor_id": "E0072",
            "right_boundary_anchor_id": "E0078",
            "catalog_start_index": 73,
            "catalog_end_index": 77,
        },
    ]


def test_candidate_model_input_groups_quotes_by_evidence_island(
    tmp_path: Path,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    generation = {
        "datasets": [
            {
                "dataset_id": "SYNTHETIC",
                "chapter": 1,
                "catalog_entries": _catalog(81),
                "cases": [
                    {
                        "case_id": "CASE-ISLANDS",
                        "event_id": "EV-01",
                        "event_text": "NO_MATCH_TOKEN",
                        "cited_anchor_ids": ["E0005", "E0075"],
                    }
                ],
            }
        ]
    }
    claims = split_atomic_claims("CASE-ISLANDS", "NO_MATCH_TOKEN")
    (inbox / "generation_cases.json").write_bytes(stable_json_bytes(generation))
    (inbox / "atomic_claims.json").write_bytes(
        stable_json_bytes(
            {"cases": [{"case_id": "CASE-ISLANDS", "claims": claims}]}
        )
    )
    (inbox / "token_bound_contract.json").write_bytes(
        stable_json_bytes(
            {
                "formula": {
                    "tokens_per_nonblank_char": 0.75,
                    "fixed_margin_tokens": 64,
                }
            }
        )
    )

    output = stage_runtime._stage_candidate(StageReader("candidate", inbox))
    messages = output["cases"][0]["model_visible_messages"]
    payload = json.loads(messages[1]["content"])
    islands = payload["evidence_islands"]

    assert len(islands) == 2
    assert islands[0]["selected_spans"][0]["anchor_id"] == "E0003"
    assert islands[0]["left_boundary_context"]["anchor_id"] == "E0002"
    assert islands[0]["right_boundary_context"]["anchor_id"] == "E0008"
    assert islands[1]["left_boundary_context"]["anchor_id"] == "E0072"
    assert islands[1]["right_boundary_context"]["anchor_id"] == "E0078"
    assert "evidence_spans" not in payload


def test_stage_reader_only_accepts_declared_inbox_names(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    allowed = inbox / "generation_cases.json"
    allowed.write_text(json.dumps({"datasets": []}), encoding="utf-8")
    (inbox / "scoring_answers.json").write_text("{}", encoding="utf-8")
    reader = StageReader("candidate", inbox)

    assert reader.json("generation_cases.json") == {"datasets": []}
    with pytest.raises(StageRuntimeError, match="未获准读取"):
        reader.json("scoring_answers.json")
    with pytest.raises(StageRuntimeError, match="未获准读取"):
        reader.json("../generation_cases.json")


def test_audit_probe_rejects_repo_file_outside_stage_inbox(
    tmp_path: Path,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    outbox = tmp_path / "outbox"
    forbidden = pipeline.REPO_ROOT / "AGENTS.md"
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            (
                "experiments."
                "Z96_anchor_layer_evidence_closure_r02_20260724.stage_runtime"
            ),
            "--stage",
            "candidate",
            "--inbox",
            str(inbox),
            "--outbox",
            str(outbox),
            "--probe-path",
            str(forbidden),
        ],
        cwd=pipeline.REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "拒绝 inbox/outbox 外读取" in result.stderr


def test_output_path_rejects_protected_tree_and_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protected = pipeline.REPO_ROOT / pipeline.PROTECTED_PATHS[-2]
    monkeypatch.setattr(
        pipeline,
        "AUTHORIZED_RUN_DIRECTORY",
        str(protected / "nested"),
    )
    with pytest.raises(pipeline.Z96PipelineError, match="输出目录落入保护路径"):
        pipeline._assert_output_path_allowed(protected / "nested")

    existing = tmp_path / "already-exists"
    existing.mkdir()
    monkeypatch.setattr(pipeline, "AUTHORIZED_RUN_DIRECTORY", str(existing))
    with pytest.raises(pipeline.Z96PipelineError, match="运行目录已存在"):
        pipeline._assert_output_path_allowed(existing)


def test_output_path_rejects_any_unlisted_new_directory(tmp_path: Path) -> None:
    with pytest.raises(
        pipeline.Z96PipelineError,
        match="运行目录不在本令精确白名单",
    ):
        pipeline._assert_output_path_allowed(tmp_path / "not-authorized")


def test_hard_stop_always_writes_post_output_protection_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "authorized-r02"
    fingerprint = {
        "file_count": 2,
        "summary_sha256": "f" * 64,
        "rows": [],
    }
    monkeypatch.setattr(pipeline, "AUTHORIZED_RUN_DIRECTORY", str(run_dir))
    monkeypatch.setattr(
        pipeline,
        "_tree_fingerprint",
        lambda _paths: copy.deepcopy(fingerprint),
    )

    def fail_after_start(
        _run_dir: Path,
        _protection_before: dict[str, object],
    ) -> dict[str, object]:
        raise pipeline.Z96PipelineError("synthetic stage failure")

    monkeypatch.setattr(pipeline, "_execute_build", fail_after_start)

    with pytest.raises(pipeline.Z96PipelineError, match="synthetic stage failure"):
        pipeline.build(run_dir)

    hard_stop = json.loads(
        (run_dir / "hard_stop.json").read_text(encoding="utf-8")
    )
    protection = json.loads(
        (run_dir / "post_output_protection_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert hard_stop["in_place_rerun_allowed"] is False
    assert hard_stop["model_api_calls"] == 0
    assert protection["status"] == "PASS"
    assert protection["unchanged"] is True

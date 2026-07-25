#!/usr/bin/env python3
"""V02/C7：在最终实验臂映射冻结后重跑 C5 材料充分性与原尺判定。

本工具只读 C1、C4、C6、C7 冻结件。它不会用事件条数代替 49 原子覆盖，
也不会在缺少双臂逐原子语义判词时臆造 ANCHOR_PARTIAL 或五层分数。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import v02_anchor_first_experiment as prep
import v02_c6_crosswalk as c6_crosswalk
import v02_c7_finalize_mapping as finalizer


ROOT = Path(__file__).resolve().parents[1]
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
C1_DIR = V02_ROOT / "C_anchor_first_experiment"
C6_CROSSWALK = (
    V02_ROOT
    / "V02_C6_control_and_crosswalk/crosswalk/mechanical_crosswalk_partial.json"
)
C4_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C4_r03_20260725"
CONTROL_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C6对照臂_r05_20260725"
MAPPING_DIR = V02_ROOT / "V02_C7_final_mapping_and_C5_rescore/mapping"
DEFAULT_OUTPUT_DIR = (
    V02_ROOT / "V02_C7_final_mapping_and_C5_rescore/c5_rescore"
)

CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
TREATMENT_EVENT_COUNTS = {
    "B02-U0039": 13,
    "B03-U0041": 10,
    "B01-U0033": 14,
}
CONTROL_EVENT_COUNTS = {
    "B02-U0039": 44,
    "B03-U0041": 10,
    "B01-U0033": 75,
}
EXPECTED_CONTROL_ROUTE_COUNTS = {
    "B02-U0039": {
        "MECHANICAL_UNIQUE_ROUTE": 3,
        "AMBIGUOUS_ROUTE": 5,
        "NO_POSITION_ROUTE": 0,
    },
    "B03-U0041": {
        "MECHANICAL_UNIQUE_ROUTE": 8,
        "AMBIGUOUS_ROUTE": 0,
        "NO_POSITION_ROUTE": 8,
    },
    "B01-U0033": {
        "MECHANICAL_UNIQUE_ROUTE": 6,
        "AMBIGUOUS_ROUTE": 19,
        "NO_POSITION_ROUTE": 0,
    },
}
EXPECTED_GATE = {
    "offline_denominator": 49,
    "relative_reduction_threshold": 0.5,
    "declining_chapter_threshold": 2,
    "declining_chapter_total": 3,
    "no_regression_layers": ["FCR", "QCR_full", "ASR_full", "UCR"],
    "sop_threshold": 0.98,
    "additional_model_calls_threshold": 0,
}

CONCLUSION_MISSING = "MATERIALS_INSUFFICIENT_CANNOT_ADJUDICATE"
CONTROL_MAPPING_MISSING = "CONTROL_49_ATOM_SEMANTIC_MAPPING_MISSING"
CONTROL_CARDINALITY_MISSING = "CONTROL_CARDINALITY_METRICS_MISSING"

EXPECTED_INPUT_SHAS = {
    "c1_gate_contract": (
        "76e8ac359543f6d92d643c2337195f2605d8c386e4cdd48228e669b68ab3629e"
    ),
    "c4_completion": (
        "dd15b6a7a3ddef951c18de30dcbcd94b584f642a736899e1ae66b67ce3949014"
    ),
    "control_completion": (
        "a8933a780932376830cf18cfe71c0d00196cdf5ce77f2e6ff137b13fad262d44"
    ),
    "c6_crosswalk": (
        "cf6c6122ba063fcb0956c6d5d493042398afbb37b412c4f71f27026f9a7da310"
    ),
    "final_treatment_mapping": (
        "7ddfcb2b29ed7fc1340ebd323da8603f44a3bef7d6511bce474ecbbf78acea51"
    ),
    "treatment_cardinality_metrics": (
        "72136f51d54b76ed4b7d156d6551ded35b2d8eccee57ba1e07d82368cc71b2d1"
    ),
}
EXPECTED_SAMPLE_SHAS = {
    "treatment": {
        "B02-U0039": {
            "candidate": (
                "ff15bc7c0a48e8d0f9627ff6dd52f7223d1056b6e317cae242a2609db89ea074"
            ),
            "mechanical": (
                "007705372365db542fd1334ce0b6dd3c37dce29fddfb2497face394bbcd4a6b4"
            ),
        },
        "B03-U0041": {
            "candidate": (
                "f915b4387e7ea7c206b7c6f9374f9ca13986458bc1998c94b88f69253e5658f2"
            ),
            "mechanical": (
                "5a0fea9447498059d43d3d75d30c6c2c62fe231d97552f8a3445956440f8babb"
            ),
        },
        "B01-U0033": {
            "candidate": (
                "95a3aa343255b262986f06405d49a7c776c3c553c4829585a10c0259af15650a"
            ),
            "mechanical": (
                "78875ce606cc47dde5c42cb77fc2aa04346930c93373c597b4ff78aebeb470ab"
            ),
        },
    },
    "control": {
        "B02-U0039": {
            "candidate": (
                "64eaea14c5a979d8f8a9223f6f91b36a551229b94c537092b4b95a49aa98e5cd"
            ),
            "mechanical": (
                "063be9b061915e9046ee08fededb5c7c6fcdedf293e5ef97a787eb7861244a0d"
            ),
        },
        "B03-U0041": {
            "candidate": (
                "a735021d3d0d357c2fe0a227d2967f94cd8b6ba7b002cf4cbe2e1de58c1fb13b"
            ),
            "mechanical": (
                "7c3eb890ff9c371d481cb23013a12640db3306c48a3a7cf9709e27225c3572a9"
            ),
        },
        "B01-U0033": {
            "candidate": (
                "d570c51f1299f32747ab8c030a95063e439a6d00e4126ac1018c744f38de6db1"
            ),
            "mechanical": (
                "b642fa255a51dcaa7d134c40a838db82d2cad74412f6c4a6adf771221338a291"
            ),
        },
    },
}


class C5RescoreError(RuntimeError):
    """C5 复算不能从冻结实物安全重建。"""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C5RescoreError(f"冻结件不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _assert_sha(label: str, path: Path) -> str:
    digest = sha256_file(path)
    if digest != EXPECTED_INPUT_SHAS[label]:
        raise C5RescoreError(f"冻结输入 SHA 漂移：{label}")
    return digest


def _verify_mapping_outputs() -> tuple[dict[str, Any], dict[str, Any]]:
    rebuilt = finalizer.build_artifacts()
    mapping_path = MAPPING_DIR / "final_treatment_mapping.json"
    metrics_path = MAPPING_DIR / "treatment_cardinality_metrics.json"
    if mapping_path.read_bytes() != rebuilt["final_treatment_mapping.json"]:
        raise C5RescoreError("实验臂最终映射不能由冻结输入逐字重建")
    if metrics_path.read_bytes() != rebuilt["treatment_cardinality_metrics.json"]:
        raise C5RescoreError("实验臂基数读数不能由冻结映射逐字重建")
    _assert_sha("final_treatment_mapping", mapping_path)
    _assert_sha("treatment_cardinality_metrics", metrics_path)
    return read_json(mapping_path), read_json(metrics_path)


def _verify_gate_contract() -> dict[str, Any]:
    path = C1_DIR / "gate/gate_contract.json"
    digest = _assert_sha("c1_gate_contract", path)
    document = read_json(path)
    criteria = document.get("criteria")
    if not isinstance(criteria, Mapping):
        raise C5RescoreError("C1 原尺缺少判据")
    observed = {
        "offline_denominator": document.get("offline_denominator"),
        "relative_reduction_threshold": criteria.get(
            "anchor_partial_relative_reduction", {}
        ).get("threshold"),
        "declining_chapter_threshold": criteria.get(
            "anchor_partial_declining_chapters", {}
        ).get("threshold"),
        "declining_chapter_total": criteria.get(
            "anchor_partial_declining_chapters", {}
        ).get("chapter_total"),
        "no_regression_layers": criteria.get("no_regression_layers"),
        "sop_threshold": criteria.get("sop", {}).get("threshold"),
        "additional_model_calls_threshold": criteria.get(
            "additional_model_calls", {}
        ).get("threshold"),
    }
    if observed != EXPECTED_GATE:
        raise C5RescoreError("C1 原尺阈值或 49 分母漂移")
    return {
        "file_sha256": digest,
        "criteria": observed,
        "criteria_changed_for_rescore": False,
    }


def _event_list(path: Path, expected_count: int) -> list[Mapping[str, Any]]:
    document = read_json(path)
    events = document.get("events")
    if not isinstance(events, list) or len(events) != expected_count:
        raise C5RescoreError(f"候选事件数漂移：{display_path(path)}")
    event_ids = [
        event.get("event_id")
        for event in events
        if isinstance(event, Mapping)
    ]
    if (
        len(event_ids) != len(events)
        or any(not isinstance(event_id, str) for event_id in event_ids)
        or len(set(event_ids)) != len(event_ids)
    ):
        raise C5RescoreError(f"候选事件身份非法：{display_path(path)}")
    return events


def _verify_treatment_run() -> dict[str, Any]:
    completion_path = C4_RUN_DIR / "completion/main.json"
    completion_sha = _assert_sha("c4_completion", completion_path)
    completion = read_json(completion_path)
    if (
        completion.get("status") != "main_mechanical_pass_pending_offline_score"
        or completion.get("case_ids") != list(CASE_ORDER)
        or completion.get("logical_samples") != 3
        or completion.get("quality_result_registered") is not False
    ):
        raise C5RescoreError("C4 实验臂完成票漂移")
    rows = []
    for case_id in CASE_ORDER:
        candidate_path = (
            C4_RUN_DIR / f"samples/main/{case_id}/candidate/model_json.json"
        )
        mechanical_path = C4_RUN_DIR / f"samples/main/{case_id}/mechanical.json"
        if (
            sha256_file(candidate_path)
            != EXPECTED_SAMPLE_SHAS["treatment"][case_id]["candidate"]
            or sha256_file(mechanical_path)
            != EXPECTED_SAMPLE_SHAS["treatment"][case_id]["mechanical"]
        ):
            raise C5RescoreError(f"{case_id} C4 样张或机械票 SHA 漂移")
        events = _event_list(candidate_path, TREATMENT_EVENT_COUNTS[case_id])
        mechanical = read_json(mechanical_path)
        if (
            mechanical.get("status") != "pass"
            or mechanical.get("case_id") != case_id
            or mechanical.get("finish_reason") != "stop"
            or mechanical.get("semantic_support_verified") is not False
            or mechanical.get("closed_anchor_validation", {}).get("status")
            != "pass"
        ):
            raise C5RescoreError(f"{case_id} C4 机械票漂移")
        rows.append(
            {
                "case_id": case_id,
                "produced_parent_event_total": len(events),
                "candidate_sha256": sha256_file(candidate_path),
                "mechanical_ticket_sha256": sha256_file(mechanical_path),
            }
        )
    if sum(row["produced_parent_event_total"] for row in rows) != 37:
        raise C5RescoreError("C4 实验臂事件总数漂移")
    return {
        "run_id": C4_RUN_DIR.name,
        "completion_sha256": completion_sha,
        "mechanical_pass_chapter_total": 3,
        "produced_parent_event_total": 37,
        "by_case": rows,
    }


def _verify_control_run() -> dict[str, Any]:
    completion_path = CONTROL_RUN_DIR / "completion/main.json"
    completion_sha = _assert_sha("control_completion", completion_path)
    completion = read_json(completion_path)
    if (
        completion.get("status")
        != "CONTROL_THREE_CHAPTERS_MECHANICAL_PASS_PENDING_C6_MAPPING"
        or completion.get("case_ids") != list(CASE_ORDER)
        or completion.get("logical_samples") != 3
        or completion.get("quality_result_registered") is not False
        or completion.get("event_count_by_case") != CONTROL_EVENT_COUNTS
    ):
        raise C5RescoreError("C6 对照臂完成票漂移")
    rows = []
    for case_id in CASE_ORDER:
        candidate_path = (
            CONTROL_RUN_DIR
            / f"samples/main/{case_id}/candidate/model_json.json"
        )
        mechanical_path = (
            CONTROL_RUN_DIR / f"samples/main/{case_id}/mechanical.json"
        )
        if (
            sha256_file(candidate_path)
            != EXPECTED_SAMPLE_SHAS["control"][case_id]["candidate"]
            or sha256_file(mechanical_path)
            != EXPECTED_SAMPLE_SHAS["control"][case_id]["mechanical"]
        ):
            raise C5RescoreError(f"{case_id} C6 对照样张或机械票 SHA 漂移")
        events = _event_list(candidate_path, CONTROL_EVENT_COUNTS[case_id])
        mechanical = read_json(mechanical_path)
        z_event = mechanical.get("z_event_validation")
        if (
            mechanical.get("status") != "PASS"
            or mechanical.get("case_id") != case_id
            or mechanical.get("finish_reason") != "stop"
            or not isinstance(z_event, Mapping)
            or z_event.get("status") != "PASS_Z_EVENT_V1_MECHANICAL"
            or z_event.get("event_count") != len(events)
            or z_event.get("semantic_anchor_support_verified") is not False
        ):
            raise C5RescoreError(f"{case_id} C6 对照机械票漂移")
        rows.append(
            {
                "case_id": case_id,
                "produced_parent_event_total": len(events),
                "candidate_sha256": sha256_file(candidate_path),
                "mechanical_ticket_sha256": sha256_file(mechanical_path),
            }
        )
    if sum(row["produced_parent_event_total"] for row in rows) != 129:
        raise C5RescoreError("C6 对照臂事件总数漂移")
    return {
        "run_id": CONTROL_RUN_DIR.name,
        "completion_sha256": completion_sha,
        "mechanical_pass_chapter_total": 3,
        "produced_parent_event_total": 129,
        "by_case": rows,
    }


def _control_candidate_nodes(
    case_id: str,
    events: Sequence[Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for event in events:
        event_id = str(event["event_id"])
        anchor_objects = event.get("anchors")
        if not isinstance(anchor_objects, list) or not anchor_objects:
            raise C5RescoreError(f"{case_id}/{event_id} 缺 anchors")
        anchor_ids = [
            row.get("anchor_id")
            for row in anchor_objects
            if isinstance(row, Mapping)
        ]
        if (
            len(anchor_ids) != len(anchor_objects)
            or any(not isinstance(value, str) for value in anchor_ids)
            or len(set(anchor_ids)) != len(anchor_ids)
        ):
            raise C5RescoreError(f"{case_id}/{event_id} 锚身份非法")
        nodes.append(
            {
                "node_id": event_id,
                "parent_event_id": event_id,
                "candidate_text_sha256": sha256_bytes(
                    str(event.get("event", "")).encode("utf-8")
                ),
                "anchor_ids": list(anchor_ids),
                "ranges": c6_crosswalk._ranges_from_anchor_ids(
                    case_id,
                    list(anchor_ids),
                    catalog,
                ),
            }
        )
    return nodes


def _control_mapping_readiness() -> dict[str, Any]:
    crosswalk_sha = _assert_sha("c6_crosswalk", C6_CROSSWALK)
    crosswalk = read_json(C6_CROSSWALK)
    chapters = crosswalk.get("chapters")
    if (
        not isinstance(chapters, list)
        or [chapter.get("case_id") for chapter in chapters] != list(CASE_ORDER)
    ):
        raise C5RescoreError("C6 机械路由章节身份漂移")
    by_case: dict[str, Any] = {}
    for chapter in chapters:
        case_id = str(chapter["case_id"])
        catalog, catalog_sha = c6_crosswalk._catalog(case_id)
        candidate_path = (
            CONTROL_RUN_DIR
            / f"samples/main/{case_id}/candidate/model_json.json"
        )
        events = _event_list(candidate_path, CONTROL_EVENT_COUNTS[case_id])
        candidate_nodes = _control_candidate_nodes(case_id, events, catalog)
        gold_rows = chapter.get("event_graph", {}).get("gold_rows")
        if not isinstance(gold_rows, list):
            raise C5RescoreError(f"{case_id} 缺冻结金标位置图")
        source = prep.load_case_source(prep.CASE_BY_ID[case_id])
        graph = c6_crosswalk._route_graph(
            candidate_nodes,
            gold_rows,
            str(source["body"]),
        )
        counts = c6_crosswalk._status_counts(graph["gold_rows"])
        if counts != EXPECTED_CONTROL_ROUTE_COUNTS[case_id]:
            raise C5RescoreError(f"{case_id} 对照位置路由计数漂移")
        by_case[case_id] = {
            "scoring_atom_total": DENOMINATORS[case_id],
            "produced_parent_event_total": CONTROL_EVENT_COUNTS[case_id],
            "gold_atom_route_status_counts": counts,
            "mechanical_unique_route_total": counts[
                c6_crosswalk.ROUTE_UNIQUE
            ],
            "semantic_verdict_pending_total": (
                counts[c6_crosswalk.ROUTE_AMBIGUOUS]
                + counts[c6_crosswalk.ROUTE_NONE]
            ),
            "catalog_sha256": catalog_sha,
            "control_candidate_sha256": sha256_file(candidate_path),
        }
    totals = Counter()
    for row in by_case.values():
        totals.update(row["gold_atom_route_status_counts"])
    if totals != {
        c6_crosswalk.ROUTE_UNIQUE: 17,
        c6_crosswalk.ROUTE_AMBIGUOUS: 24,
        c6_crosswalk.ROUTE_NONE: 8,
    }:
        raise C5RescoreError("对照臂 49 原子位置路由总数漂移")
    return {
        "schema_version": "v02-c7-control-mapping-readiness.v1",
        "status": CONTROL_MAPPING_MISSING,
        "same_position_counter_as_treatment_c6": True,
        "counter_source_sha256": sha256_file(
            Path(c6_crosswalk.__file__).resolve()
        ),
        "c6_treatment_crosswalk_sha256": crosswalk_sha,
        "scoring_atom_total": 49,
        "mechanical_unique_route_total": 17,
        "semantic_verdict_pending_total": 32,
        "gold_atom_route_status_counts": dict(sorted(totals.items())),
        "by_case": by_case,
        "mechanical_route_is_not_semantic_verdict": True,
        "control_mapping_frozen": False,
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _first_screen(
    treatment_metrics: Mapping[str, Any],
    control_readiness: Mapping[str, Any],
) -> dict[str, Any]:
    treatment_cases = treatment_metrics["by_case_breakdown"]
    return {
        "schema_version": "v02-c7-c5-first-screen.v1",
        "status": CONCLUSION_MISSING,
        "arm_event_counts": {
            "control": 129,
            "treatment": 37,
        },
        "coverage": {
            "control": {
                "status": CONTROL_MAPPING_MISSING,
                "mapped_atom_total": None,
                "scoring_atom_total": 49,
                "coverage_rate": None,
            },
            "treatment": {
                "status": "FROZEN",
                "mapped_atom_total": treatment_metrics["mapped_atom_total"],
                "scoring_atom_total": 49,
                "coverage_rate": treatment_metrics["coverage_rate"],
                "by_case": {
                    case_id: {
                        "mapped_atom_total": treatment_cases[case_id][
                            "mapped_atom_total"
                        ],
                        "scoring_atom_total": DENOMINATORS[case_id],
                        "coverage_rate": treatment_cases[case_id][
                            "coverage_rate"
                        ],
                    }
                    for case_id in CASE_ORDER
                },
            },
        },
        "merge_degree": {
            "control": {
                "status": CONTROL_CARDINALITY_MISSING,
                "histogram": None,
                "maximum_atoms_per_mapped_event": None,
            },
            "treatment": {
                "status": "FROZEN",
                "histogram": treatment_metrics[
                    "mapped_event_degree_histogram"
                ],
                "one_to_one_mapped_event_count": treatment_metrics[
                    "one_to_one_mapped_event_count"
                ],
                "many_to_one_mapped_event_count": treatment_metrics[
                    "many_to_one_mapped_event_count"
                ],
                "maximum_atoms_per_mapped_event": treatment_metrics[
                    "maximum_atoms_per_mapped_event"
                ],
            },
        },
        "split_degree": {
            "control": {
                "status": CONTROL_CARDINALITY_MISSING,
                "histogram": None,
                "maximum_events_per_atom": None,
            },
            "treatment": {
                "status": "FROZEN",
                "histogram": treatment_metrics[
                    "atom_split_degree_histogram"
                ],
                "maximum_events_per_atom": treatment_metrics[
                    "maximum_events_per_atom"
                ],
            },
        },
        "control_mapping_readiness": {
            "mechanical_unique_route_total": control_readiness[
                "mechanical_unique_route_total"
            ],
            "semantic_verdict_pending_total": control_readiness[
                "semantic_verdict_pending_total"
            ],
            "mechanical_routes_count_as_coverage": False,
        },
        "coverage_guard": {
            "rule": (
                "error_rate_down_with_49_atom_coverage_down_cannot_pass"
            ),
            "label": "疑似以少产出换低错误率",
            "status": "MISSING_CONTROL_COVERAGE_NOT_EVALUATED",
            "triggered": None,
        },
        "produced_event_count_not_used_as_coverage": True,
    }


def build_artifacts() -> dict[str, bytes]:
    mapping, treatment_metrics = _verify_mapping_outputs()
    gate = _verify_gate_contract()
    treatment_run = _verify_treatment_run()
    control_run = _verify_control_run()
    control_readiness = _control_mapping_readiness()
    if (
        mapping.get("status") != "FROZEN_V02_WORKING_TRUTH"
        or mapping.get("row_total") != 49
        or treatment_metrics.get("mapped_atom_total") != 25
    ):
        raise C5RescoreError("C7 最终实验臂映射身份漂移")
    first_screen = _first_screen(treatment_metrics, control_readiness)

    missing_codes = [
        CONTROL_MAPPING_MISSING,
        CONTROL_CARDINALITY_MISSING,
        "CONTROL_ANCHOR_PARTIAL_AND_FIVE_LAYER_VERDICTS_MISSING",
        "TREATMENT_ANCHOR_PARTIAL_AND_FIVE_LAYER_VERDICTS_MISSING",
        "C1_NUMERIC_GATE_INPUTS_INCOMPLETE",
    ]
    sufficiency = {
        "schema_version": "v02-c7-c5-material-sufficiency.v1",
        "status": "MATERIALS_INSUFFICIENT",
        "selected_conclusion": CONCLUSION_MISSING,
        "missing_codes": missing_codes,
        "treatment_mapping_frozen": True,
        "control_mapping_frozen": False,
        "symmetric_49_atom_coverage_available": False,
        "two_arm_anchor_partial_and_five_layer_verdicts_available": False,
        "evaluate_gate_invoked": False,
        "quality_result_registered": False,
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    gate_checks = {
        "anchor_partial_relative_reduction_at_least_50_percent": (
            "MISSING_INPUT"
        ),
        "anchor_partial_declines_in_at_least_two_of_three_chapters": (
            "MISSING_INPUT"
        ),
        "fcr_qcr_asr_ucr_no_regression": "MISSING_INPUT",
        "sop_at_least_0_98": "MISSING_INPUT",
        "zero_additional_model_calls_for_this_rescore": True,
        "offline_denominator_is_49": True,
        "coverage_no_regression_guard": (
            "MISSING_CONTROL_COVERAGE_NOT_EVALUATED"
        ),
    }
    receipt = {
        "schema_version": "v02-c7-c5-rescore-receipt.v1",
        "status": CONCLUSION_MISSING,
        "selected_conclusion": CONCLUSION_MISSING,
        "reason": (
            "实验臂 49 原子工作映射已冻结，但对照臂还没有同尺的 "
            "49 原子语义映射，双臂 ANCHOR_PARTIAL 与五层逐原子判词也未齐。"
            "129 条产出事件不能代替对照覆盖率。"
        ),
        "c1_gate_contract": gate,
        "gate_checks": gate_checks,
        "first_screen_sha256": sha256_bytes(canonical_bytes(first_screen)),
        "treatment_run": treatment_run,
        "control_run": control_run,
        "quality_result_registered": False,
        "evaluate_gate_invoked": False,
        "judge_green_ticket_eligible": False,
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts = {
        "first_screen_metrics.json": canonical_bytes(first_screen),
        "control_mapping_readiness.json": canonical_bytes(control_readiness),
        "material_sufficiency.json": canonical_bytes(sufficiency),
        "c5_rescore_receipt.json": canonical_bytes(receipt),
    }
    preimage = {
        relative: sha256_bytes(raw)
        for relative, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c7-c5-rescore-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": relative, "sha256": digest}
                for relative, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def write_or_verify(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise C5RescoreError("C5 复算连续两次构造不一致")
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(first.items()):
        path = output_dir / relative
        if path.is_file():
            if path.read_bytes() != raw:
                raise C5RescoreError(f"C5 已有复算工件漂移：{relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    if actual != set(first):
        raise C5RescoreError("C5 复算目录存在未登记文件")
    return {
        "status": CONCLUSION_MISSING,
        "output_dir": display_path(output_dir),
        "artifact_manifest_sha256": sha256_file(
            output_dir / "artifact_manifest.json"
        ),
        "c5_rescore_receipt_sha256": sha256_file(
            output_dir / "c5_rescore_receipt.json"
        ),
        "mechanical_double_run_identical": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            write_or_verify(args.output_dir.resolve()),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

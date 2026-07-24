"""生成第96道零调用候选工件。

输入只来自显式白名单。输出目录必须不存在，并且不得位于任何封存目录内。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from tools.pipeline_common.artifacts import build_manifest, write_json_atomic

from .anchor_evidence_candidate import (
    Z96CandidateError,
    aligned_anchor_rows,
    build_claim_fixture_from_required_anchors,
    build_evidence_closure_packet,
    build_lightweight_chapter_map,
    catalog_entries,
    evaluate_fixture_replay,
    nearest_rank_percentile,
    sha256_file,
    tree_fingerprint,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_TIME = "2026-07-24T12:25:00+08:00"

X04_LEDGER = "reports/九项第三道_主张级核锚并单设计_20260723/x04_recompute/x04_claim_anchor_recompute.json"
X04_BODY = "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723/inputs/cases/X04-C0046/chapter_body.txt"
X04_CATALOG = "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723/inputs/cases/X04-C0046/evidence_catalog.json"
X04_SAMPLE = "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723/samples/X04-C0046__pro_primary_tencent/candidate/neutral_events.json"

RETRY_ROOT = "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry03"
RETRY_LEDGER = f"{RETRY_ROOT}/main/main_sample_ledger.jsonl"
RETRY_EVENTS = {
    3: f"{RETRY_ROOT}/main/01_extract/events/ch0003.json",
    13: f"{RETRY_ROOT}/main/01_extract/events/ch0013.json",
    19: f"{RETRY_ROOT}/main/01_extract/events/ch0019.json",
}
RETRY_CATALOGS = {
    3: f"{RETRY_ROOT}/inputs/evidence_catalogs/ch0003.json",
    13: f"{RETRY_ROOT}/inputs/evidence_catalogs/ch0013.json",
    19: f"{RETRY_ROOT}/inputs/evidence_catalogs/ch0019.json",
}
RETRY_BODIES = {
    3: f"{RETRY_ROOT}/inputs/chapters/0003_第3章_梅丽莎（第一更求推荐票）.txt",
    13: f"{RETRY_ROOT}/inputs/chapters/0013_第13章_值夜者.txt",
    19: f"{RETRY_ROOT}/inputs/chapters/0019_第19章_封印物（第二更求推荐票）.txt",
}
FORMAL_122 = f"{RETRY_ROOT}/inputs/current_formal_records_122.json"

Z89_ROOT = "runs/Z89_X01_DeepSeekV4Pro强模型对照_第3章_v1.0_20260723"
Z89_EVENTS = f"{Z89_ROOT}/main/01_extract/events/ch0003.json"
Z89_CATALOG = f"{Z89_ROOT}/inputs/evidence_catalogs/ch0003.json"
Z89_BODY = f"{Z89_ROOT}/inputs/chapters/0003_第3章_梅丽莎（第一更求推荐票）.txt"
Z89_ADJUDICATION = f"{Z89_ROOT}/review/adjudication_completed.json"
Z89_SEAL = f"{Z89_ROOT}/checkpoints/ch0003/05_seal.json"
Z89_SCORECARD = f"{Z89_ROOT}/final/scorecard.json"

EXPECTED_SHA256 = {
    X04_LEDGER: "7085dc67c4e0e3762ab43fd9dbc9aad8f9eacc0bcad7dd086c55136daf116324",
    X04_BODY: "4e168668007a8ec58db29b3511facfd3bafb9a6eb327078bc7564efdf563e96e",
    X04_CATALOG: "1c16106ddc66d0a2818ac73e593c2473808dff162852e1e4449baa17f29f4d15",
    X04_SAMPLE: "865c5240a8b33a5603e07d763fb6d1b84964b7d8b722543b1d27d89ae4636bb7",
    RETRY_LEDGER: "6696fc8dc6d9ae96e44a039feb5d9d9e3e45cc2cc714b042ff9c62a23720f314",
    RETRY_EVENTS[3]: "295c7f19dc46bd3c56e984ec701d40dcb34a68eef0a20ec3474cfb5f723d150a",
    RETRY_EVENTS[13]: "aeefcee35c56e52f82dc7382d1073902311c68947d4d8c518cfbf23816808898",
    RETRY_EVENTS[19]: "2f7b9713149183a73d4b1b17a620cba3dabe146ff5935d8a43f1e15bd8243d30",
    RETRY_CATALOGS[3]: "2cc50e9a0c8b5fb807641e09c74f1748cbe423bf0fa700dbbbaa84ba20e58132",
    RETRY_CATALOGS[13]: "47d5a5f13b227e4c1470530a1962060f7800f05f30e9e73b815a17604bd9457e",
    RETRY_CATALOGS[19]: "dd7b2215801668b3896ccf5c3c651752fa9293b4da0916465f9f3b6fcfd6ba7e",
    RETRY_BODIES[3]: "96f5e17cbec15433b5d00bef18912eb39710ad67962e3716bca37203d4c06288",
    RETRY_BODIES[13]: "418efe90277893207d2623d14c9093a30a68f38f44dd51ebcee6315813ddd8c0",
    RETRY_BODIES[19]: "127af1d2061e3e4cccca7f893ae98e511c2902a7ae06aecc9fa783eb22ca5caa",
    FORMAL_122: "dafa16901a6edb5018a5176f3f5f7388273e72051def7fe4e997489d01e804ba",
    Z89_EVENTS: "97f39e145c7774e5204983d1639ccde1f4be13f42fc6eb6a6306de6b42e5948d",
    Z89_CATALOG: "2cc50e9a0c8b5fb807641e09c74f1748cbe423bf0fa700dbbbaa84ba20e58132",
    Z89_BODY: "96f5e17cbec15433b5d00bef18912eb39710ad67962e3716bca37203d4c06288",
    Z89_ADJUDICATION: "ddb35e13502fd21545b2cadf65cc38f7acd1b986be1f8d1b8ff9ba217a3f4d4e",
    Z89_SEAL: "61baa6f8f364e767515f2491eae0dee7c3f341b7146a4aaf379d972009b22250",
    Z89_SCORECARD: "edb78f2d1a6bc2320e73e4912516ec8821fe5323b36feb79df64aba11119290c",
}

FORBIDDEN_REPLAY_INPUTS = [
    {
        "path": f"{RETRY_ROOT}/review/inspector/ch0003/run/responses/semantic_route/Z83-MAIN-CH0003-API_raw.json",
        "sha256": "d8940c706b97064be328e0d35d940bf5499560bbde583a264b7a143067c2ac99",
        "reason": "finish_reason=length 的拒收响应，禁止局部捞回。",
    },
    {
        "path": f"{RETRY_ROOT}/review/inspector/hard_stop.json",
        "sha256": "a45e85e5d1228183dfc9485c81f63a936aa631682f347e87b5ab6e9fbf150688",
        "reason": "只作拒收身份旁证，不作重放样张。",
    },
]

PROTECTION_PATHS = [
    RETRY_ROOT,
    Z89_ROOT,
    "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723",
    "reports/九项第三道_主张级核锚并单设计_20260723",
    "config/gold",
    "config/defaults/zbatch_v1.2_full_chain.COMMITTED.json",
    "config/defaults/zbatch_v1.2_full_chain.json",
    "config/contracts/classify_rules_v1.2_semantic_identity_v1.json",
    "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json",
    "outbox",
]


class FrozenReader:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.rows: list[dict[str, Any]] = []
        self._cache: dict[str, bytes] = {}

    def bytes(self, relative: str, *, role: str) -> bytes:
        if relative not in EXPECTED_SHA256:
            raise Z96CandidateError(f"未登记读取路径：{relative}")
        if relative not in self._cache:
            path = self.root / relative
            actual = sha256_file(path)
            expected = EXPECTED_SHA256[relative]
            if actual != expected:
                raise Z96CandidateError(
                    f"冻结来源 SHA 漂移：{relative} expected={expected} actual={actual}"
                )
            self._cache[relative] = path.read_bytes()
            self.rows.append(
                {
                    "path": relative,
                    "role": role,
                    "bytes": path.stat().st_size,
                    "sha256": actual,
                    "parsed_for_replay": True,
                }
            )
        return self._cache[relative]

    def text(self, relative: str, *, role: str) -> str:
        return self.bytes(relative, role=role).decode("utf-8")

    def json(self, relative: str, *, role: str) -> Any:
        return json.loads(self.text(relative, role=role))


def _anchors(event: dict[str, Any]) -> list[dict[str, Any]]:
    anchors = event.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        raise Z96CandidateError(f"{event.get('event_id')} 缺锚")
    return anchors


def _validate_event_anchors(
    event: dict[str, Any],
    catalog: dict[str, str],
    *,
    chapter: int,
) -> list[str]:
    result: list[str] = []
    for anchor in _anchors(event):
        anchor_id = anchor.get("anchor_id")
        quote = anchor.get("quote")
        if not isinstance(anchor_id, str) or anchor_id not in catalog:
            raise Z96CandidateError(f"{event.get('event_id')} 含目录外锚：{anchor_id}")
        if quote != catalog[anchor_id]:
            raise Z96CandidateError(f"{event.get('event_id')} 锚短引不等于冻结目录：{anchor_id}")
        if anchor.get("chapter") != chapter:
            raise Z96CandidateError(f"{event.get('event_id')} 锚章号不等于 {chapter}")
        result.append(anchor_id)
    if len(result) != len(set(result)):
        raise Z96CandidateError(f"{event.get('event_id')} 锚重复")
    return result


def _contract() -> dict[str, Any]:
    return {
        "schema_version": "z96-a-plus-anchor-and-evidence-closure-contract-v1",
        "authority_time": AUTHORITY_TIME,
        "candidate_silver_only": True,
        "runner_connected": False,
        "model_api_calls": 0,
        "network_attempts": 0,
        "ucr_computed": False,
        "mutations": {
            "event_or_anchor_mutation": False,
            "formal_gold_or_pointer_mutation": False,
            "historical_score_mutation": False,
            "sealed_run_mutation": False,
        },
        "a_plus_anchor_pipeline": [
            "align_claim_and_source_span",
            "program_candidate_recall",
            "claim_level_support_alignment",
            "derive_minimal_complete_anchor_set",
            "render",
            "render_reverse_check",
        ],
        "semantic_truth_boundary": (
            "必要锚只来自独立冻结人工判词，程序自己的候选不能反过来充当答案。"
        ),
        "formal_decisions": ["PASS", "REJECT"],
        "forbidden_decisions_or_actions": ["FILL", "MARK", "AUTO_ATTACH_ANCHOR"],
        "endpoint_span_pattern": {
            "hard_gate": True,
            "definition": (
                "一个主张横跨至少3个正文顺序连续锚，只挂首尾且中间必要锚未挂，"
                "直接REJECT；锚ID编号不承担区间语义。"
            ),
        },
        "evidence_closure": {
            "full_chapter_map_ids_only": True,
            "candidate_anchor_ids_are_seeds_not_whitelist": True,
            "maximum_relation_hops": 2,
            "maximum_controlled_expansions": 1,
            "input_token_proxy": "non_whitespace_unicode_codepoint_count_v1",
            "p95_method": "nearest_rank_ceiling",
            "median_limit": 2500,
            "p95_limit": 4000,
            "necessary_span_recall_required": 1.0,
        },
        "x04_zero_definition": (
            "只指85次缺锚发生次均有唯一处置，遗漏0、重复0、未决0；"
            "不代表封存样张或现役件已修复。"
        ),
    }


def _build_canaries() -> dict[str, Any]:
    body = "甲先说明条件。乙据此采取行动。事情最终成功。"
    catalog = {
        "entries": [
            {"anchor_id": "E0001", "chapter": 0, "quote": "甲先说明条件。"},
            {"anchor_id": "E0002", "chapter": 0, "quote": "乙据此采取行动。"},
            {"anchor_id": "E0003", "chapter": 0, "quote": "事情最终成功。"},
        ]
    }
    aligned = aligned_anchor_rows(body, catalog_entries(catalog))
    a01 = evaluate_fixture_replay(
        case_id="CANARY-A-01",
        aligned=aligned,
        selected_anchor_ids=["E0001"],
        necessary_anchor_ids=["E0001", "E0002"],
    )
    a02_rows = [
        evaluate_fixture_replay(
            case_id=f"CANARY-A-02-{index:02d}",
            aligned=aligned,
            selected_anchor_ids=["E0001", "E0003"],
            necessary_anchor_ids=["E0001", "E0002", "E0003"],
        )
        for index in range(1, 4)
    ]
    a01_pass = a01["input_gate"]["decision"] == "REJECT" and not a01["input_gate"]["ASR_full"]
    a02_pass = all(
        row["input_gate"]["decision"] == "REJECT"
        and not row["input_gate"]["ASR_full"]
        and row["endpoint_span_pattern"]
        for row in a02_rows
    )
    return {
        "schema_version": "z96-canary-receipt-v1",
        "status": "PASS" if a01_pass and a02_pass else "REJECT",
        "A_01": a01,
        "A_02": a02_rows,
        "checks": {
            "A_01_half_sentence_rejected": a01_pass,
            "A_02_all_three_rejected": a02_pass,
            "A_02_all_three_endpoint_pattern": all(
                row["endpoint_span_pattern"] for row in a02_rows
            ),
        },
    }


def _build_x04(
    reader: FrozenReader,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    ledger = reader.json(X04_LEDGER, role="x04_frozen_human_anchor_judgment")
    body = reader.text(X04_BODY, role="x04_frozen_chapter")
    catalog_data = reader.json(X04_CATALOG, role="x04_frozen_evidence_catalog")
    sample = reader.json(X04_SAMPLE, role="x04_pro_sample_readonly")
    entries = catalog_entries(catalog_data)
    aligned = aligned_anchor_rows(body, entries)
    catalog_map = {str(row["anchor_id"]): str(row["quote"]) for row in entries}
    sample_events = {
        str(event["event_id"]): event
        for event in sample.get("events", [])
        if isinstance(event, dict) and event.get("event_id")
    }
    rows = ledger.get("rows")
    if not isinstance(rows, list) or len(rows) != 59 or len(sample_events) != 59:
        raise Z96CandidateError("X04 事件数不是冻结的59")

    dispositions: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    closure_packets: list[dict[str, Any]] = []
    sequence = 0
    for row in rows:
        event_id = str(row["event_id"])
        sample_event = sample_events.get(event_id)
        if sample_event is None:
            raise Z96CandidateError(f"X04 判词事件不在样张：{event_id}")
        sample_selected = _validate_event_anchors(sample_event, catalog_map, chapter=46)
        cited = list(map(str, row.get("cited_anchor_ids") or []))
        if sample_selected != cited:
            raise Z96CandidateError(f"X04 {event_id} 判词锚与样张不一致")
        missing = list(map(str, row.get("missing_required_anchor_ids") or []))
        necessary = list(dict.fromkeys(cited + missing))
        audit = evaluate_fixture_replay(
            case_id=f"X04:{event_id}",
            aligned=aligned,
            selected_anchor_ids=cited,
            necessary_anchor_ids=necessary,
        )
        audit["source_verdict"] = row.get("verdict")
        audit["semantic_issue_outside_anchor_scope"] = row.get("semantic_note")
        audit["sample_mutated"] = False
        replay_rows.append(audit)
        claims = build_claim_fixture_from_required_anchors(
            case_id=f"X04:{event_id}",
            required_anchor_ids=necessary,
        )
        closure_packets.append(
            build_evidence_closure_packet(
                case_id=f"X04:{event_id}",
                event_text=str(row["event"]),
                chapter_map=build_lightweight_chapter_map(body, aligned),
                aligned=aligned,
                seed_anchor_ids=cited,
                claim_units_for_fixture=claims,
                necessary_anchor_ids_for_fixture=necessary,
            )
        )
        for missing_anchor_id in missing:
            sequence += 1
            dispositions.append(
                {
                    "disposition_id": f"X04-DISP-{sequence:03d}",
                    "event_id": event_id,
                    "missing_anchor_id": missing_anchor_id,
                    "action": "ADD_REQUIRED_ANCHOR_TO_CANDIDATE_SET",
                    "status": "RESOLVED_IN_OFFLINE_CANDIDATE_DEMO",
                    "source_judgment_path": X04_LEDGER,
                    "source_judgment_sha256": EXPECTED_SHA256[X04_LEDGER],
                    "source_verdict": row.get("verdict"),
                    "reason": row.get("unsupported_claim"),
                    "sample_or_formal_record_mutated": False,
                }
            )

    if len(dispositions) != 85:
        raise Z96CandidateError(f"X04 缺锚发生次不是85：{len(dispositions)}")
    keys = [(row["event_id"], row["missing_anchor_id"]) for row in dispositions]
    if len(keys) != len(set(keys)):
        raise Z96CandidateError("X04 同一事件同一缺锚出现重复处置")
    unresolved = [row for row in dispositions if not row["status"].startswith("RESOLVED")]
    unique_missing = {row["missing_anchor_id"] for row in dispositions}
    disposition_ledger = {
        "schema_version": "z96-x04-anchor-disposition-ledger-v1",
        "status": "PASS" if not unresolved else "REJECT",
        "occurrence_denominator": 85,
        "unique_missing_anchor_ids": len(unique_missing),
        "rows": dispositions,
        "summary": {
            "rows": len(dispositions),
            "omitted": 0,
            "duplicated_same_event_anchor": 0,
            "unresolved": len(unresolved),
            "sample_mutated": False,
            "meaning_of_zero": (
                "处置账未决为0；不代表X04封存样张、现役件或历史成绩已修复。"
            ),
        },
    }
    replay = {
        "schema_version": "z96-x04-a-plus-replay-v1",
        "status": "PASS",
        "events": len(replay_rows),
        "complete_input_events": sum(
            row["input_gate"]["decision"] == "PASS" for row in replay_rows
        ),
        "rejected_input_events": sum(
            row["input_gate"]["decision"] == "REJECT" for row in replay_rows
        ),
        "candidate_anchor_gate_pass_events": sum(
            row["candidate_gate"]["decision"] == "PASS" for row in replay_rows
        ),
        "endpoint_span_pattern_events": sum(
            bool(row["endpoint_span_pattern"]) for row in replay_rows
        ),
        "rows": replay_rows,
        "boundary": (
            "candidate_gate 只证明冻结人工夹具下的候选集合可闭合；"
            "不自动修改样张，也不把候选PASS升级成质量真值。"
        ),
    }
    return disposition_ledger, replay, closure_packets


def _build_retry03(
    reader: FrozenReader,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ledger_lines = [
        json.loads(line)
        for line in reader.text(RETRY_LEDGER, role="retry03_main_sample_ledger").splitlines()
        if line.strip()
    ]
    if [row.get("chapter") for row in ledger_lines] != [3, 13, 19]:
        raise Z96CandidateError("retry03 主样张账章次不是3/13/19")
    formal = reader.json(FORMAL_122, role="current_formal_records_122_readonly")
    formal_usage = {
        (int(anchor["chapter"]), str(anchor["anchor_id"]))
        for record in formal.get("records", [])
        for anchor in record.get("anchors", [])
        if isinstance(anchor, dict)
    }
    chapter_rows: list[dict[str, Any]] = []
    closure_packets: list[dict[str, Any]] = []
    for chapter in (3, 13, 19):
        events_data = reader.json(RETRY_EVENTS[chapter], role=f"retry03_ch{chapter}_events")
        catalog_data = reader.json(RETRY_CATALOGS[chapter], role=f"retry03_ch{chapter}_catalog")
        body = reader.text(RETRY_BODIES[chapter], role=f"retry03_ch{chapter}_body")
        entries = catalog_entries(catalog_data)
        aligned = aligned_anchor_rows(body, entries)
        catalog_map = {str(row["anchor_id"]): str(row["quote"]) for row in entries}
        event_rows: list[dict[str, Any]] = []
        for event in events_data.get("events", []):
            anchor_ids = _validate_event_anchors(event, catalog_map, chapter=chapter)
            candidates = build_evidence_closure_packet(
                case_id=f"RETRY03:{event['event_id']}",
                event_text=str(event["event"]),
                chapter_map=build_lightweight_chapter_map(body, aligned),
                aligned=aligned,
                seed_anchor_ids=anchor_ids,
            )
            closure_packets.append(candidates)
            event_rows.append(
                {
                    "event_id": event["event_id"],
                    "current_anchor_ids": anchor_ids,
                    "anchor_references": len(anchor_ids),
                    "anchor_refs_also_in_formal_122": sum(
                        (chapter, anchor_id) in formal_usage for anchor_id in anchor_ids
                    ),
                    "semantic_support_status": "NOT_ADJUDICATED_IN_RETRY03",
                    "formal_decision": None,
                    "sample_mutated": False,
                }
            )
        chapter_rows.append(
            {
                "chapter": chapter,
                "events": len(event_rows),
                "anchor_references": sum(row["anchor_references"] for row in event_rows),
                "catalog_entries": len(entries),
                "rows": event_rows,
            }
        )
    return {
        "schema_version": "z96-retry03-anchor-layer-readonly-replay-v1",
        "status": "PASS_MECHANICAL_ONLY",
        "chapters": chapter_rows,
        "summary": {
            "events": sum(row["events"] for row in chapter_rows),
            "anchor_references": sum(row["anchor_references"] for row in chapter_rows),
            "formal_122_records": len(formal.get("records", [])),
            "formal_122_anchor_keys": len(formal_usage),
            "illegal_anchor_ids": 0,
            "quote_mismatches": 0,
            "semantic_rejudgments": 0,
        },
        "boundary": (
            "retry03 没有完成的语义检查员判词；本道只重算目录合法性、逐字短引、"
            "候选闭包与现役锚账重合，不给样张补发新的语义PASS。"
        ),
    }, closure_packets


def _missing_anchor_ids_from_reason(reason: str) -> list[str]:
    matches = re.findall(r"(?:所需|未挂的)(E\d{4})", reason)
    return list(dict.fromkeys(matches))


def _build_z89(
    reader: FrozenReader,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events_data = reader.json(Z89_EVENTS, role="z89_events_readonly")
    catalog_data = reader.json(Z89_CATALOG, role="z89_catalog")
    body = reader.text(Z89_BODY, role="z89_chapter_body")
    adjudication = reader.json(Z89_ADJUDICATION, role="z89_completed_adjudication_readonly")
    reader.json(Z89_SEAL, role="z89_acceptance_seal")
    reader.json(Z89_SCORECARD, role="z89_formal_scorecard_readonly")
    entries = catalog_entries(catalog_data)
    aligned = aligned_anchor_rows(body, entries)
    catalog_map = {str(row["anchor_id"]): str(row["quote"]) for row in entries}
    events = {
        str(event["event_id"]): event
        for event in events_data.get("events", [])
        if isinstance(event, dict)
    }
    mechanical_rows: list[dict[str, Any]] = []
    for event in events.values():
        anchors = _validate_event_anchors(event, catalog_map, chapter=3)
        mechanical_rows.append(
            {
                "event_id": event["event_id"],
                "anchor_ids": anchors,
                "anchor_references": len(anchors),
            }
        )

    failed = [
        row
        for row in adjudication.get("gold_rows", [])
        if row.get("verdict") == "coverage_only_invalid_support"
    ]
    if len(failed) != 3:
        raise Z96CandidateError(f"Z89 已知锚不托案不是3：{len(failed)}")
    replays: list[dict[str, Any]] = []
    closure_packets: list[dict[str, Any]] = []
    for index, row in enumerate(failed, 1):
        event_ids = list(map(str, row.get("candidate_event_ids") or []))
        if len(event_ids) != 1 or event_ids[0] not in events:
            raise Z96CandidateError("Z89 锚不托案没有唯一候选事件")
        event = events[event_ids[0]]
        selected = [str(anchor["anchor_id"]) for anchor in _anchors(event)]
        missing = _missing_anchor_ids_from_reason(str(row.get("reason", "")))
        if len(missing) != 1 or missing[0] not in catalog_map:
            raise Z96CandidateError(f"Z89 锚不托案缺唯一必要锚：{row.get('part_id')}")
        necessary = list(dict.fromkeys(selected + missing))
        case_id = f"Z89-ANCHOR-FAIL-{index:02d}"
        audit = evaluate_fixture_replay(
            case_id=case_id,
            aligned=aligned,
            selected_anchor_ids=selected,
            necessary_anchor_ids=necessary,
            claim_span_seed_anchor_ids=missing,
        )
        audit["historical_review_row_id"] = row.get("part_id")
        audit["event_id"] = event["event_id"]
        audit["historical_reason"] = row.get("reason")
        audit["historical_score_mutated"] = False
        replays.append(audit)
        claims = build_claim_fixture_from_required_anchors(
            case_id=case_id,
            required_anchor_ids=necessary,
        )
        closure_packets.append(
            build_evidence_closure_packet(
                case_id=case_id,
                event_text=str(event["event"]),
                chapter_map=build_lightweight_chapter_map(body, aligned),
                aligned=aligned,
                seed_anchor_ids=selected,
                claim_span_seed_anchor_ids=missing,
                claim_units_for_fixture=claims,
                necessary_anchor_ids_for_fixture=necessary,
            )
        )
    return {
        "schema_version": "z96-z89-anchor-layer-readonly-replay-v1",
        "status": "PASS",
        "sample_events": len(events),
        "sample_anchor_references": sum(row["anchor_references"] for row in mechanical_rows),
        "illegal_anchor_ids": 0,
        "quote_mismatches": 0,
        "known_invalid_support_cases": len(replays),
        "offline_candidate_closure_pass_cases": sum(
            row["candidate_gate"]["decision"] == "PASS" for row in replays
        ),
        "rows": replays,
        "historical_score_mutated": False,
        "boundary": "只读重放现有锚账与已完成判词，不追改Z89历史成绩。",
    }, closure_packets


def build(output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    for protected in (REPO_ROOT / RETRY_ROOT, REPO_ROOT / Z89_ROOT, REPO_ROOT / "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723"):
        try:
            output_dir.relative_to(protected.resolve())
        except ValueError:
            pass
        else:
            raise Z96CandidateError("输出目录不得位于封存运行目录内")
    if output_dir.exists():
        raise Z96CandidateError(f"输出目录已存在，拒绝覆盖：{output_dir}")
    output_dir.mkdir(parents=True)

    protection_before = tree_fingerprint(REPO_ROOT, PROTECTION_PATHS)
    reader = FrozenReader(REPO_ROOT)
    contract = _contract()
    canaries = _build_canaries()
    if canaries["status"] != "PASS":
        raise Z96CandidateError("CANARY 未全过，拒绝生成")
    x04_dispositions, x04_replay, x04_packets = _build_x04(reader)
    retry_replay, retry_packets = _build_retry03(reader)
    z89_replay, z89_packets = _build_z89(reader)
    packets = x04_packets + retry_packets + z89_packets

    token_values = [int(row["metrics"]["input_token_proxy"]) for row in packets]
    fixture_packets = [row for row in packets if row["offline_evaluation"]["fixture_used"]]
    fixture_required = sum(
        len(row["offline_evaluation"]["necessary_anchor_ids"]) for row in fixture_packets
    )
    fixture_recalled = sum(
        len(row["offline_evaluation"]["recalled_necessary_anchor_ids"]) for row in fixture_packets
    )
    necessary_recall = fixture_recalled / fixture_required if fixture_required else 0.0
    median_value = nearest_rank_percentile(token_values, 0.5)
    p95_value = nearest_rank_percentile(token_values, 0.95)
    closure_ledger = {
        "schema_version": "z96-evidence-closure-ledger-v1",
        "status": (
            "PASS"
            if necessary_recall == 1.0 and median_value <= 2500 and p95_value <= 4000
            else "REJECT"
        ),
        "packet_count": len(packets),
        "fixture_packet_count": len(fixture_packets),
        "metrics": {
            "necessary_span_denominator": fixture_required,
            "necessary_span_recalled": fixture_recalled,
            "necessary_span_recall": necessary_recall,
            "input_token_proxy_median": median_value,
            "input_token_proxy_p95_nearest_rank": p95_value,
            "input_token_proxy_max": max(token_values),
            "controlled_expansion_count_total": sum(
                row["metrics"]["controlled_expansion_count"] for row in packets
            ),
            "token_proxy_contract": "non_whitespace_unicode_codepoint_count_v1",
        },
        "packets": packets,
        "boundary": (
            "必要跨度只在独立冻结夹具包上计分；retry03无完成语义判词，"
            "只计输入长度，不进入必要跨度召回分母。"
        ),
    }
    if closure_ledger["status"] != "PASS":
        raise Z96CandidateError("证据闭包硬门槛未过")

    protection_after = tree_fingerprint(REPO_ROOT, PROTECTION_PATHS)
    protection_pass = protection_before["summary_sha256"] == protection_after["summary_sha256"]
    if not protection_pass:
        raise Z96CandidateError("保护面前后指纹漂移")

    read_paths = {row["path"] for row in reader.rows}
    forbidden_used = [row for row in FORBIDDEN_REPLAY_INPUTS if row["path"] in read_paths]
    source_seal = {
        "schema_version": "z96-source-seal-and-read-ledger-v1",
        "status": "PASS" if not forbidden_used else "REJECT",
        "allowed_reads": reader.rows,
        "forbidden_replay_inputs": [
            {
                **row,
                "actual_sha256": sha256_file(REPO_ROOT / row["path"]),
                "used_in_replay": False,
                "protection_fingerprint_only": True,
            }
            for row in FORBIDDEN_REPLAY_INPUTS
        ],
        "forbidden_used_count": len(forbidden_used),
        "protection": {
            "paths": PROTECTION_PATHS,
            "before_summary_sha256": protection_before["summary_sha256"],
            "after_summary_sha256": protection_after["summary_sha256"],
            "file_count": protection_before["file_count"],
            "unchanged": protection_pass,
            "note": "保护指纹会读文件字节算SHA，但不会解析或捞回拒收内容。",
        },
    }
    if source_seal["status"] != "PASS":
        raise Z96CandidateError("被拒样张混入重放")

    validation = {
        "schema_version": "z96-validation-summary-v1",
        "status": "PASS",
        "checks": {
            "model_api_calls_zero": True,
            "network_attempts_zero": True,
            "runner_connected_false": True,
            "ucr_not_computed": True,
            "canaries_pass": True,
            "x04_disposition_occurrences_85": x04_dispositions["summary"]["rows"] == 85,
            "x04_disposition_unresolved_zero": x04_dispositions["summary"]["unresolved"] == 0,
            "x04_sample_mutated_false": not x04_dispositions["summary"]["sample_mutated"],
            "necessary_span_recall_100_percent": necessary_recall == 1.0,
            "input_proxy_median_lte_2500": median_value <= 2500,
            "input_proxy_p95_lte_4000": p95_value <= 4000,
            "retry03_semantic_rejudgments_zero": retry_replay["summary"]["semantic_rejudgments"] == 0,
            "z89_historical_score_mutated_false": not z89_replay["historical_score_mutated"],
            "forbidden_replay_inputs_used_zero": not forbidden_used,
            "protected_files_unchanged": protection_pass,
        },
        "usage": {
            "model_api_logical_samples": 0,
            "model_api_network_attempts": 0,
            "model_api_usage_tokens": 0,
        },
        "release_boundary": (
            "候选银标；未接运行器、未固化、未升默认。接运行器与正式判分须另拍。"
        ),
    }
    if not all(validation["checks"].values()):
        raise Z96CandidateError("第96道机械验收存在失败项")

    artifacts = {
        "01_contract.json": contract,
        "02_source_seal_and_read_ledger.json": source_seal,
        "03_x04_85_disposition_ledger.json": x04_dispositions,
        "04_x04_replay.json": x04_replay,
        "05_retry03_replay.json": retry_replay,
        "06_z89_replay.json": z89_replay,
        "07_evidence_closure_ledger.json": closure_ledger,
        "08_canary_receipt.json": canaries,
        "09_validation_summary.json": validation,
    }
    for filename, value in artifacts.items():
        write_json_atomic(output_dir / filename, value)
    manifest = {
        "schema_version": "z96-artifact-manifest-v1",
        "files": build_manifest(output_dir, artifacts.keys()),
        "manifest_excludes_itself": True,
    }
    write_json_atomic(output_dir / "artifact_manifest.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

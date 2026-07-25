#!/usr/bin/env python3
"""V02/C8：构造另一份产出的一侧盲审准备工位。

本工具只读 C1、C6、C7.5、C7.6 与 C7.7 冻结件，不调用模型：

- 以 C6 同一位置区间算法重建 49 个计分原子的路由图；
- 冻结 17 条 C6 唯一路由与 11 条 C7.5 单候选共享路由；
- 把其余 21 条拆成逐原子盲审包；
- 从 C7.7 的 26 包母集按固定 SHA 排序抽 6 包，和 21 包混排；
- 对模型可见选项使用无含义化名，真实事件 ID 只留私有对照表。

C7.6 只放宽“一条原子可由多条事件共同承载”的基数合同。它不替
真正的多候选行做语义选择，因此 13 条多候选仍进入两票合议。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import v02_anchor_first_experiment as prep
import v02_c6_crosswalk as c6


ROOT = Path(__file__).resolve().parents[1]
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
C1_DIR = V02_ROOT / "C_anchor_first_experiment"
C6_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C6对照臂_r05_20260725"
C75_POLICY = (
    V02_ROOT
    / "V02_C7_human_verdict_workspace/c7_5_mapping_cardinality_policy.json"
)
C77_DIR = V02_ROOT / "V02_C7_6_7_ai_consensus_workspace"
C76_POLICY = C77_DIR / "c7_6_split_degree_policy.json"
C77_CONTRACT = C77_DIR / "c7_7_consensus_contract.json"
C77_PACKET_MANIFEST = C77_DIR / "c7_7_packet_manifest.json"
DEFAULT_OUTPUT_DIR = (
    V02_ROOT
    / "V02_C8_control_mapping_and_interpretability/preparation"
)

CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
EXPECTED_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
EXPECTED_EVENT_COUNTS = {
    "B02-U0039": 44,
    "B03-U0041": 10,
    "B01-U0033": 75,
}
EXPECTED_ROUTE_COUNTS = {
    "c6_unique": 17,
    "c7_5_single_candidate": 11,
    "blind_multiple_position_candidates": 13,
    "blind_no_position": 8,
}
EXPECTED_INPUT_SHAS = {
    "c1_source_manifest": (
        "039f1fcc3c0ee5c22e1a6588f806a6c7eb2e543c91bbae608a6f48d73aa6b023"
    ),
    "c1_gate_contract": (
        "76e8ac359543f6d92d643c2337195f2605d8c386e4cdd48228e669b68ab3629e"
    ),
    "c6_completion": (
        "a8933a780932376830cf18cfe71c0d00196cdf5ce77f2e6ff137b13fad262d44"
    ),
    "c6_request_lock": (
        "f25193f1a1a573940749b900e0ad64ccc3e466c0d11a26275fc6fc5f9b29d727"
    ),
    "c7_5_policy": (
        "34efe343912feacc3094fe7f7dab8a9f40bae568fde694e8305234348b7b5ec6"
    ),
    "c7_6_policy": (
        "94c43070039b67437a139088fbd8c5974d2b077a5185b3e5d335922c5c37a86d"
    ),
    "c7_7_contract": (
        "d9eee6474c10cfd55c5c79a98e3e1d662974406951882a99321ac8c9d5c81eed"
    ),
    "c7_7_packet_manifest": (
        "c3a06c1917bfdcf52f10080867bbe858c8d2c3ac2b53f3e672597f8ee39529b5"
    ),
}
EXPECTED_CASE_SHAS = {
    "B02-U0039": {
        "candidate": (
            "64eaea14c5a979d8f8a9223f6f91b36a551229b94c537092b4b95a49aa98e5cd"
        ),
        "catalog": (
            "c903e830197f13ea784d9542e3fb37580687bbc13ebb5f83bb3d41eab86c11a5"
        ),
        "mechanical": (
            "063be9b061915e9046ee08fededb5c7c6fcdedf293e5ef97a787eb7861244a0d"
        ),
        "formal_gold": (
            "56bebe3581a0ff239fad21868b07a367fa6139e8bbfc1a750cd51f5ff5964e1a"
        ),
        "source_body": (
            "031a7f57f42ccbd8824bddbda2a7a54339b2aa0c5da191f3c42886664f865d37"
        ),
    },
    "B03-U0041": {
        "candidate": (
            "a735021d3d0d357c2fe0a227d2967f94cd8b6ba7b002cf4cbe2e1de58c1fb13b"
        ),
        "catalog": (
            "c009880d31247cb356d2dd541e10609fc7956ec747ce44f89c337d6ac48f48fc"
        ),
        "mechanical": (
            "7c3eb890ff9c371d481cb23013a12640db3306c48a3a7cf9709e27225c3572a9"
        ),
        "formal_gold": (
            "cd935ee43163b143466b0cd3e8355e8b91794e75f424678be8adfe88e5f975ce"
        ),
        "source_body": (
            "f4be2b97a18033e2ea48bf7c43fabeb888c965f5dac013a4931a6644ac4ea824"
        ),
    },
    "B01-U0033": {
        "candidate": (
            "d570c51f1299f32747ab8c030a95063e439a6d00e4126ac1018c744f38de6db1"
        ),
        "catalog": (
            "136c903418c45fea56d5a0298a444f906d057488e9552b52d6acc50c930356fa"
        ),
        "mechanical": (
            "b642fa255a51dcaa7d134c40a838db82d2cad74412f6c4a6adf771221338a291"
        ),
        "formal_gold": (
            "bbc2d37898ff4bc375907cd429aff9e50d3a284913da6c6ddb09cbf67c05b327"
        ),
        "source_body": (
            "37e7b74004c27c737f418c687ee6f3703ab7a9afd002511a6ea73d1dae3adac1"
        ),
    },
}

DECISION_RULE = (
    "只在候选事件明确承载该原子事实时选择对应 ID；"
    "一条原子可由多条候选事件共同承载；"
    "找不到明确对应时只选 NO_CORRESPONDENCE，禁止硬配。"
)
DECISION_RULE_SHA256 = (
    "2f2a01a8bf75dc7d960d5f1c75b385db8ffdbf7debb6ad20e69048bf5c693333"
)
AUDIT_SAMPLE_SEED = "V02-C8-FIXED-AUDIT-SAMPLE-v1"
BLIND_MIX_SEED = "V02-C8-FIXED-BLIND-MIX-v1"
ALIAS_SALT = "V02-C8-PRIVATE-EVENT-ALIAS-v1"
NO_CORRESPONDENCE = "NO_CORRESPONDENCE"
PRIVATE_SOURCE_PRIMARY = "S1"
PRIVATE_SOURCE_AUDIT = "S2"

MODEL_VISIBLE_FORBIDDEN_PATTERNS = (
    re.compile(r"EV-C\d+", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])control(?![A-Za-z0-9_])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])treatment(?![A-Za-z0-9_])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])arm(?![A-Za-z0-9_])", re.IGNORECASE),
    re.compile(r"(?:^|[\"'/])runs/", re.IGNORECASE),
    re.compile(r"V02_实验A锚先行倒装", re.IGNORECASE),
)


class C8WorkspaceError(RuntimeError):
    """C8 准备工位无法从冻结真源安全重建。"""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C8WorkspaceError(f"冻结输入不存在：{path}")
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _assert_sha(label: str, path: Path, expected: str) -> str:
    digest = sha256_file(path)
    if digest != expected:
        raise C8WorkspaceError(f"冻结输入 SHA 漂移：{label}")
    return digest


def _source_paths_for_case(case_id: str) -> dict[str, Path]:
    base = C6_RUN_DIR / "samples/main" / case_id
    prepared = C6_RUN_DIR / "prepared"
    return {
        "candidate": base / "candidate/model_json.json",
        "mechanical": base / "mechanical.json",
        "catalog": prepared / "catalogs" / f"{case_id}.json",
    }


def _verify_global_sources() -> tuple[
    dict[str, Mapping[str, Any]],
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
]:
    source_manifest_path = C1_DIR / "source_manifest.json"
    gate_path = C1_DIR / "gate/gate_contract.json"
    completion_path = C6_RUN_DIR / "completion/main.json"
    request_lock_path = C6_RUN_DIR / "prepared/C6_request_lock.json"
    _assert_sha(
        "c1_source_manifest",
        source_manifest_path,
        EXPECTED_INPUT_SHAS["c1_source_manifest"],
    )
    _assert_sha(
        "c1_gate_contract",
        gate_path,
        EXPECTED_INPUT_SHAS["c1_gate_contract"],
    )
    _assert_sha(
        "c6_completion",
        completion_path,
        EXPECTED_INPUT_SHAS["c6_completion"],
    )
    _assert_sha(
        "c6_request_lock",
        request_lock_path,
        EXPECTED_INPUT_SHAS["c6_request_lock"],
    )
    _assert_sha(
        "c7_5_policy",
        C75_POLICY,
        EXPECTED_INPUT_SHAS["c7_5_policy"],
    )
    _assert_sha(
        "c7_6_policy",
        C76_POLICY,
        EXPECTED_INPUT_SHAS["c7_6_policy"],
    )
    _assert_sha(
        "c7_7_contract",
        C77_CONTRACT,
        EXPECTED_INPUT_SHAS["c7_7_contract"],
    )
    _assert_sha(
        "c7_7_packet_manifest",
        C77_PACKET_MANIFEST,
        EXPECTED_INPUT_SHAS["c7_7_packet_manifest"],
    )

    source_manifest = read_json(source_manifest_path)
    chapters = source_manifest.get("chapters")
    if (
        source_manifest.get("schema_version")
        != "v02-anchor-first-source-manifest.v1"
        or not isinstance(chapters, list)
        or [row.get("case_id") for row in chapters] != list(CASE_ORDER)
    ):
        raise C8WorkspaceError("C1 来源清单身份或章顺序漂移")
    manifest_rows = {str(row["case_id"]): row for row in chapters}

    completion = read_json(completion_path)
    if (
        completion.get("status")
        != "CONTROL_THREE_CHAPTERS_MECHANICAL_PASS_PENDING_C6_MAPPING"
        or completion.get("event_count_by_case") != EXPECTED_EVENT_COUNTS
        or completion.get("quality_result_registered") is not False
    ):
        raise C8WorkspaceError("C6 三章完成票状态漂移")
    request_lock = read_json(request_lock_path)
    if (
        request_lock.get("case_order") != list(CASE_ORDER)
        or request_lock.get("result_selection_allowed") is not False
        or request_lock.get("retry_allowed") is not False
    ):
        raise C8WorkspaceError("C6 请求锁纪律漂移")

    c75 = read_json(C75_POLICY)
    if (
        c75.get("status") != "ACTIVE_FOR_C7_MAPPING_AND_C5_RESCORE"
        or c75.get("event_occupancy_rule") != "NO_EXCLUSIVE_OCCUPANCY"
        or c75.get("multiple_gold_atoms_may_map_to_same_event") is not True
        or c75.get("applies_equally_to_arms")
        != ["control", "treatment"]
    ):
        raise C8WorkspaceError("C7.5 多对一政策漂移")

    c76 = read_json(C76_POLICY)
    if (
        c76.get("status") != "ACTIVE_FOR_C7_MAPPING_AND_C5_RESCORE"
        or c76.get("one_atom_may_map_to_multiple_events") is not True
        or c76.get("applies_equally_to_arms")
        != ["control", "treatment"]
    ):
        raise C8WorkspaceError("C7.6 一对多政策漂移")

    contract = read_json(C77_CONTRACT)
    if (
        contract.get("minimum_independent_model_windows") != 2
        or contract.get("unanimity_required") is not True
        or contract.get("multiple_choice_ids_allowed_under_c7_6") is not True
        or contract.get("vote_visibility_before_commit")
        != "HIDDEN_FROM_OTHER_VOTERS"
    ):
        raise C8WorkspaceError("C7.7 两票合同漂移")
    return manifest_rows, c75, c76, contract


def _formal_claims_and_nodes(
    case_id: str,
    manifest_row: Mapping[str, Any],
    source: Mapping[str, Any],
) -> tuple[dict[str, str], list[dict[str, Any]], str]:
    parts, gold_sha = c6._formal_parts(case_id, manifest_row)
    expected = EXPECTED_CASE_SHAS[case_id]
    if gold_sha != expected["formal_gold"]:
        raise C8WorkspaceError(f"{case_id} 正式计分原子 SHA 漂移")
    claims: dict[str, str] = {}
    for part in parts:
        atom_id = part.get("part_id")
        claim = part.get("claim")
        if (
            not isinstance(atom_id, str)
            or not isinstance(claim, str)
            or not claim.strip()
            or atom_id in claims
        ):
            raise C8WorkspaceError(f"{case_id} 计分原子文本身份非法")
        claims[atom_id] = claim
    nodes = c6._gold_nodes(
        case_id,
        parts,
        inventory_unit=int(manifest_row["inventory_unit"]),
        source_body_sha256=str(source["body_sha256"]),
    )
    if len(nodes) != EXPECTED_DENOMINATORS[case_id]:
        raise C8WorkspaceError(f"{case_id} 计分原子分母漂移")
    return claims, nodes, gold_sha


def _control_event_nodes(
    case_id: str,
    candidate: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    events = candidate.get("events")
    if (
        candidate.get("schema_version") != "z-event-v1"
        or not isinstance(events, list)
        or len(events) != EXPECTED_EVENT_COUNTS[case_id]
    ):
        raise C8WorkspaceError(f"{case_id} 候选事件结构或条数漂移")
    nodes: list[dict[str, Any]] = []
    public_rows: dict[str, dict[str, str]] = {}
    seen: set[str] = set()
    for event in events:
        if not isinstance(event, Mapping):
            raise C8WorkspaceError(f"{case_id} 候选事件不是对象")
        event_id = event.get("event_id")
        event_text = event.get("event")
        anchors = event.get("anchors")
        if (
            not isinstance(event_id, str)
            or event_id in seen
            or not isinstance(event_text, str)
            or not event_text.strip()
            or not isinstance(anchors, list)
            or not anchors
        ):
            raise C8WorkspaceError(f"{case_id} 候选事件身份或正文非法")
        anchor_ids: list[str] = []
        for anchor in anchors:
            if (
                not isinstance(anchor, Mapping)
                or not isinstance(anchor.get("anchor_id"), str)
            ):
                raise C8WorkspaceError(f"{event_id} 锚对象非法")
            anchor_ids.append(str(anchor["anchor_id"]))
        if len(anchor_ids) != len(set(anchor_ids)):
            raise C8WorkspaceError(f"{event_id} 锚 ID 重复")
        nodes.append(
            {
                "node_id": event_id,
                "parent_event_id": event_id,
                "candidate_text_sha256": sha256_bytes(
                    event_text.encode("utf-8")
                ),
                "anchor_ids": anchor_ids,
                "ranges": c6._ranges_from_anchor_ids(
                    case_id,
                    anchor_ids,
                    catalog,
                ),
            }
        )
        public_rows[event_id] = {
            "event_text": event_text,
            "event_text_sha256": sha256_bytes(event_text.encode("utf-8")),
        }
        seen.add(event_id)
    return nodes, public_rows


def _build_route_inputs() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, dict[str, str]]],
    dict[str, Any],
    dict[str, dict[str, str]],
]:
    manifest_rows, _c75, _c76, _contract = _verify_global_sources()
    route_rows: list[dict[str, Any]] = []
    mechanical_rows: list[dict[str, Any]] = []
    event_texts: dict[str, dict[str, dict[str, str]]] = {}
    case_locks: dict[str, Any] = {}
    claim_lookup: dict[str, dict[str, str]] = {}
    sequence = 0

    for case_id in CASE_ORDER:
        paths = _source_paths_for_case(case_id)
        expected = EXPECTED_CASE_SHAS[case_id]
        observed_shas = {
            name: _assert_sha(
                f"{case_id}_{name}",
                path,
                expected[name],
            )
            for name, path in paths.items()
        }
        candidate = read_json(paths["candidate"])
        catalog_document = read_json(paths["catalog"])
        catalog_entries = catalog_document.get("entries")
        if (
            not isinstance(catalog_entries, list)
            or catalog_document.get("source_body_sha256")
            != expected["source_body"]
        ):
            raise C8WorkspaceError(f"{case_id} 冻结锚目录结构漂移")
        catalog = {
            str(entry["anchor_id"]): entry
            for entry in catalog_entries
            if isinstance(entry, Mapping)
            and isinstance(entry.get("anchor_id"), str)
        }
        if len(catalog) != len(catalog_entries):
            raise C8WorkspaceError(f"{case_id} 冻结锚目录 ID 非法或重复")
        mechanical = read_json(paths["mechanical"])
        if (
            mechanical.get("status") != "PASS"
            or mechanical.get("case_id") != case_id
            or mechanical.get("finish_reason") != "stop"
        ):
            raise C8WorkspaceError(f"{case_id} C6 机械票漂移")

        source = prep.load_case_source(prep.CASE_BY_ID[case_id])
        if source.get("body_sha256") != expected["source_body"]:
            raise C8WorkspaceError(f"{case_id} 冻结正文 SHA 漂移")
        manifest_row = manifest_rows[case_id]
        if (
            manifest_row.get("chapter_cache", {}).get("body_sha256")
            != expected["source_body"]
            or manifest_row.get("formal_gold", {}).get("sha256")
            != expected["formal_gold"]
        ):
            raise C8WorkspaceError(f"{case_id} C1 来源身份漂移")

        claims, gold_nodes, gold_sha = _formal_claims_and_nodes(
            case_id,
            manifest_row,
            source,
        )
        claim_lookup[case_id] = claims
        event_nodes, case_event_texts = _control_event_nodes(
            case_id,
            candidate,
            catalog,
        )
        event_texts[case_id] = case_event_texts
        graph = c6._route_graph(
            event_nodes,
            gold_nodes,
            str(source["body"]),
        )
        candidate_by_id = {
            str(row["node_id"]): row for row in graph["candidate_rows"]
        }
        all_event_ids = [str(row["node_id"]) for row in event_nodes]

        for gold in graph["gold_rows"]:
            sequence += 1
            atom_id = str(gold["node_id"])
            candidates = [
                str(value)
                for value in gold["neighbor_candidate_node_ids"]
            ]
            degree = int(gold["degree"])
            route_status = str(gold["route_status"])
            mapping_source: str | None = None
            selected_event_ids: list[str] = []
            blind_reason: str | None = None
            review_event_ids: list[str] = []

            if route_status == c6.ROUTE_UNIQUE:
                if degree != 1:
                    raise C8WorkspaceError(f"{atom_id} 唯一路由度数非法")
                mapping_source = "MECHANICAL_C6_UNIQUE_ROUTE"
                selected_event_ids = candidates
            elif degree == 1:
                candidate_degree = int(
                    candidate_by_id[candidates[0]]["degree"]
                )
                if (
                    route_status != c6.ROUTE_AMBIGUOUS
                    or candidate_degree <= 1
                ):
                    raise C8WorkspaceError(
                        f"{atom_id} C7.5 单候选共享路由不合同"
                    )
                mapping_source = "MECHANICAL_C7_5_SINGLE_CANDIDATE"
                selected_event_ids = candidates
            elif degree > 1:
                if route_status != c6.ROUTE_AMBIGUOUS:
                    raise C8WorkspaceError(f"{atom_id} 多候选状态非法")
                blind_reason = "MULTIPLE_POSITION_CANDIDATES"
                review_event_ids = candidates
            else:
                if route_status != c6.ROUTE_NONE:
                    raise C8WorkspaceError(f"{atom_id} 无位置状态非法")
                blind_reason = "NO_POSITION_ROUTE"
                review_event_ids = all_event_ids

            row = {
                "sequence": sequence,
                "row_id": f"C8-R{sequence:03d}",
                "case_id": case_id,
                "atom_id": atom_id,
                "scoring_atom_text_sha256": sha256_bytes(
                    claims[atom_id].encode("utf-8")
                ),
                "gold_evidence_ranges": gold["ranges"],
                "position_candidate_event_ids": candidates,
                "position_candidate_degree": degree,
                "route_status": route_status,
                "mapping_source": mapping_source,
                "selected_event_ids": selected_event_ids,
                "blind_review_reason": blind_reason,
                "blind_review_event_ids": review_event_ids,
            }
            route_rows.append(row)
            if mapping_source is not None:
                mechanical_rows.append(
                    {
                        "sequence": sequence,
                        "row_id": row["row_id"],
                        "case_id": case_id,
                        "atom_id": atom_id,
                        "selected_event_ids": selected_event_ids,
                        "mapping_source": mapping_source,
                        "working_mapping_not_gold": True,
                    }
                )

        case_locks[case_id] = {
            "candidate_path": display_path(paths["candidate"]),
            "candidate_sha256": observed_shas["candidate"],
            "catalog_path": display_path(paths["catalog"]),
            "catalog_sha256": observed_shas["catalog"],
            "mechanical_path": display_path(paths["mechanical"]),
            "mechanical_sha256": observed_shas["mechanical"],
            "formal_gold_sha256": gold_sha,
            "source_body_sha256": source["body_sha256"],
            "produced_event_total": len(event_nodes),
            "scoring_atom_total": len(gold_nodes),
        }

    counts = {
        "c6_unique": sum(
            row["mapping_source"] == "MECHANICAL_C6_UNIQUE_ROUTE"
            for row in route_rows
        ),
        "c7_5_single_candidate": sum(
            row["mapping_source"]
            == "MECHANICAL_C7_5_SINGLE_CANDIDATE"
            for row in route_rows
        ),
        "blind_multiple_position_candidates": sum(
            row["blind_review_reason"] == "MULTIPLE_POSITION_CANDIDATES"
            for row in route_rows
        ),
        "blind_no_position": sum(
            row["blind_review_reason"] == "NO_POSITION_ROUTE"
            for row in route_rows
        ),
    }
    if (
        len(route_rows) != 49
        or len(mechanical_rows) != 28
        or counts != EXPECTED_ROUTE_COUNTS
    ):
        raise C8WorkspaceError(f"C8 路由计数漂移：{counts}")
    return (
        route_rows,
        mechanical_rows,
        event_texts,
        case_locks,
        claim_lookup,
    )


def _load_c77_mother_set() -> tuple[
    list[dict[str, Any]],
    str,
    list[dict[str, Any]],
]:
    manifest = read_json(C77_PACKET_MANIFEST)
    rows = manifest.get("packets")
    if (
        manifest.get("schema_version")
        != "v02-c7-7-consensus-packet-manifest.v1"
        or manifest.get("packet_total") != 26
        or not isinstance(rows, list)
        or len(rows) != 26
    ):
        raise C8WorkspaceError("C7.7 二十六包母集漂移")

    mother_rows: list[dict[str, Any]] = []
    source_packets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise C8WorkspaceError("C7.7 包清单含非对象")
        packet_id = row.get("packet_id")
        relative_path = row.get("packet_path")
        expected_sha = row.get("packet_sha256")
        if (
            not isinstance(packet_id, str)
            or packet_id in seen
            or not isinstance(relative_path, str)
            or not relative_path.startswith("packets/")
            or not isinstance(expected_sha, str)
        ):
            raise C8WorkspaceError("C7.7 包身份非法")
        path = (C77_DIR / relative_path).resolve()
        if C77_DIR.resolve() not in path.parents:
            raise C8WorkspaceError("C7.7 包路径越界")
        observed_sha = sha256_file(path)
        if observed_sha != expected_sha:
            raise C8WorkspaceError(f"C7.7 包 SHA 漂移：{packet_id}")
        packet = read_json(path)
        if (
            packet.get("packet_id") != packet_id
            or packet.get("decision_rule") != DECISION_RULE
            or sha256_bytes(
                str(packet.get("decision_rule", "")).encode("utf-8")
            )
            != DECISION_RULE_SHA256
        ):
            raise C8WorkspaceError(f"C7.7 判定规则漂移：{packet_id}")
        mother_rows.append(
            {
                "packet_id": packet_id,
                "packet_sha256": observed_sha,
            }
        )
        source_packets.append(packet)
        seen.add(packet_id)
    mother_set_sha = canonical_sha(mother_rows)
    ranked = sorted(
        (
            {
                **row,
                "selection_rank_sha256": sha256_bytes(
                    (
                        f"{AUDIT_SAMPLE_SEED}\0{row['packet_id']}"
                    ).encode("utf-8")
                ),
            }
            for row in mother_rows
        ),
        key=lambda row: (
            row["selection_rank_sha256"],
            row["packet_id"],
        ),
    )
    selected_ids = {row["packet_id"] for row in ranked[:6]}
    selected_packets = [
        packet
        for packet in source_packets
        if packet["packet_id"] in selected_ids
    ]
    if len(selected_packets) != 6:
        raise C8WorkspaceError("C7.7 固定抽样不是六包")
    return ranked, mother_set_sha, selected_packets


def _alias_for(private_key: str) -> str:
    digest = sha256_bytes(
        f"{ALIAS_SALT}\0{private_key}".encode("utf-8")
    )
    return f"OPT-{digest[:12].upper()}"


def _add_alias(
    alias_rows: dict[str, dict[str, Any]],
    *,
    source_set: str,
    case_id: str,
    real_event_id: str,
    event_text: str,
) -> str:
    private_key = f"{source_set}\0{case_id}\0{real_event_id}"
    alias_id = _alias_for(private_key)
    row = {
        "alias_id": alias_id,
        "private_source_set": source_set,
        "case_id": case_id,
        "real_event_id": real_event_id,
        "event_text_sha256": sha256_bytes(event_text.encode("utf-8")),
    }
    existing = alias_rows.get(alias_id)
    if existing is not None and existing != row:
        raise C8WorkspaceError(f"事件化名碰撞：{alias_id}")
    alias_rows[alias_id] = row
    return alias_id


def _blind_packet(
    *,
    packet_id: str,
    scoring_atom_text: str,
    choices: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    option_rows = [
        {
            "choice_id": str(choice["choice_id"]),
            "candidate_event_text": choice.get("candidate_event_text"),
        }
        for choice in choices
    ]
    allowed = [str(row["choice_id"]) for row in option_rows]
    if (
        not option_rows
        or option_rows[-1]
        != {
            "choice_id": NO_CORRESPONDENCE,
            "candidate_event_text": None,
        }
        or len(allowed) != len(set(allowed))
    ):
        raise C8WorkspaceError(f"{packet_id} 盲审选项合同非法")
    return {
        "schema_version": "v02-c8-blind-consensus-packet.v1",
        "packet_id": packet_id,
        "scoring_atom_text": scoring_atom_text,
        "choices": option_rows,
        "output_contract": {
            "only_allowed_field": "selected_choice_ids",
            "selected_choice_ids": {
                "type": "array",
                "min_items": 1,
                "unique_items": True,
                "allowed_values": allowed,
            },
            "no_correspondence_is_exclusive": True,
            "reasoning_or_explanation_forbidden": True,
        },
        "decision_rule": DECISION_RULE,
        "adjudication_identity": "working_verdict_not_gold",
    }


def assert_model_visible_safe(
    artifacts: Mapping[str, bytes],
    real_event_ids: Sequence[str],
) -> dict[str, Any]:
    visible_names = [
        name
        for name in artifacts
        if name.startswith("blind_packets/")
        or name == "blind_packet_manifest.json"
    ]
    if not visible_names:
        raise C8WorkspaceError("没有模型可见盲审工件")
    combined = b"\n".join(artifacts[name] for name in sorted(visible_names))
    text = combined.decode("utf-8")
    violations: list[str] = []
    for pattern in MODEL_VISIBLE_FORBIDDEN_PATTERNS:
        if pattern.search(text):
            violations.append(pattern.pattern)
    for event_id in sorted(set(real_event_ids)):
        if event_id in text:
            violations.append(f"real_event_id:{event_id}")
    if violations:
        raise C8WorkspaceError(
            "模型可见盲审包泄漏：" + ",".join(violations)
        )
    return {
        "schema_version": "v02-c8-model-visible-leakage-ticket.v1",
        "status": "PASS",
        "model_visible_file_total": len(visible_names),
        "real_event_id_hits": 0,
        "source_role_label_hits": 0,
        "run_directory_hits": 0,
        "api_key_hits": 0,
        "statistical_role_blindness_claimed": False,
        "scope_note": (
            "程序只证明字段与标识不直接泄漏来源；文本风格或选项基数"
            "是否形成统计侧信道，不在本票证明范围内。"
        ),
    }


def build_artifacts() -> dict[str, bytes]:
    (
        route_rows,
        mechanical_rows,
        event_texts,
        case_locks,
        claim_lookup,
    ) = _build_route_inputs()
    ranked_mother, mother_set_sha, selected_packets = (
        _load_c77_mother_set()
    )

    descriptors: list[dict[str, Any]] = []
    alias_rows: dict[str, dict[str, Any]] = {}
    real_event_ids: set[str] = set()

    pending_rows = [
        row for row in route_rows if row["blind_review_reason"] is not None
    ]
    if len(pending_rows) != 21:
        raise C8WorkspaceError("待盲审控制行不是二十一条")
    for row in pending_rows:
        case_id = str(row["case_id"])
        atom_id = str(row["atom_id"])
        private_choices: list[dict[str, Any]] = []
        visible_choices: list[dict[str, Any]] = []
        for event_id in row["blind_review_event_ids"]:
            event_text = event_texts[case_id][event_id]["event_text"]
            alias_id = _add_alias(
                alias_rows,
                source_set=PRIVATE_SOURCE_PRIMARY,
                case_id=case_id,
                real_event_id=event_id,
                event_text=event_text,
            )
            visible_choice_id = f"MAP_TO::{alias_id}"
            visible_choices.append(
                {
                    "choice_id": visible_choice_id,
                    "candidate_event_text": event_text,
                }
            )
            private_choices.append(
                {
                    "visible_choice_id": visible_choice_id,
                    "real_event_id": event_id,
                }
            )
            real_event_ids.add(event_id)
        visible_choices.append(
            {
                "choice_id": NO_CORRESPONDENCE,
                "candidate_event_text": None,
            }
        )
        private_choices.append(
            {
                "visible_choice_id": NO_CORRESPONDENCE,
                "real_event_id": None,
            }
        )
        descriptors.append(
            {
                "private_source_set": PRIVATE_SOURCE_PRIMARY,
                "private_source_token": f"S1::{row['row_id']}",
                "case_id": case_id,
                "atom_id": atom_id,
                "source_row_id": row["row_id"],
                "source_packet_id": None,
                "scoring_atom_text": claim_lookup[case_id][atom_id],
                "visible_choices": visible_choices,
                "private_choices": private_choices,
            }
        )

    selected_packet_ids: list[str] = []
    for packet in selected_packets:
        case_id = str(packet["case_id"])
        source_packet_id = str(packet["packet_id"])
        private_choices = []
        visible_choices = []
        for choice in packet["choices"]:
            choice_id = str(choice["choice_id"])
            if choice_id == NO_CORRESPONDENCE:
                visible_choices.append(
                    {
                        "choice_id": NO_CORRESPONDENCE,
                        "candidate_event_text": None,
                    }
                )
                private_choices.append(
                    {
                        "visible_choice_id": NO_CORRESPONDENCE,
                        "real_event_id": None,
                    }
                )
                continue
            prefix = "MAP_TO::"
            if not choice_id.startswith(prefix):
                raise C8WorkspaceError(
                    f"{source_packet_id} C7.7 选项身份非法"
                )
            real_event_id = choice_id.removeprefix(prefix)
            event_text = choice.get("candidate_event_text")
            if not isinstance(event_text, str) or not event_text.strip():
                raise C8WorkspaceError(
                    f"{source_packet_id} 候选事件正文非法"
                )
            alias_id = _add_alias(
                alias_rows,
                source_set=PRIVATE_SOURCE_AUDIT,
                case_id=case_id,
                real_event_id=real_event_id,
                event_text=event_text,
            )
            visible_choice_id = f"MAP_TO::{alias_id}"
            visible_choices.append(
                {
                    "choice_id": visible_choice_id,
                    "candidate_event_text": event_text,
                }
            )
            private_choices.append(
                {
                    "visible_choice_id": visible_choice_id,
                    "real_event_id": real_event_id,
                }
            )
            real_event_ids.add(real_event_id)
        descriptors.append(
            {
                "private_source_set": PRIVATE_SOURCE_AUDIT,
                "private_source_token": f"S2::{source_packet_id}",
                "case_id": case_id,
                "atom_id": packet["atom_id"],
                "source_row_id": None,
                "source_packet_id": source_packet_id,
                "scoring_atom_text": packet["scoring_atom_text"],
                "visible_choices": visible_choices,
                "private_choices": private_choices,
            }
        )
        selected_packet_ids.append(source_packet_id)

    if len(descriptors) != 27 or len(selected_packet_ids) != 6:
        raise C8WorkspaceError("混排母集不是二十七包")
    ranked_descriptors = sorted(
        (
            {
                **row,
                "blind_mix_rank_sha256": sha256_bytes(
                    (
                        f"{BLIND_MIX_SEED}\0{row['private_source_token']}"
                    ).encode("utf-8")
                ),
            }
            for row in descriptors
        ),
        key=lambda row: (
            row["blind_mix_rank_sha256"],
            row["private_source_token"],
        ),
    )

    artifacts: dict[str, bytes] = {}
    packet_manifest_rows: list[dict[str, Any]] = []
    role_crosswalk_rows: list[dict[str, Any]] = []
    target_queue_rows: list[dict[str, Any]] = []
    for index, descriptor in enumerate(ranked_descriptors, 1):
        blind_id = f"C8-BLIND-{index:03d}"
        packet = _blind_packet(
            packet_id=blind_id,
            scoring_atom_text=str(descriptor["scoring_atom_text"]),
            choices=descriptor["visible_choices"],
        )
        relative_path = f"blind_packets/{blind_id}.json"
        raw = canonical_bytes(packet)
        artifacts[relative_path] = raw
        packet_manifest_rows.append(
            {
                "packet_id": blind_id,
                "packet_path": relative_path,
                "packet_sha256": sha256_bytes(raw),
                "choice_total_including_no_correspondence": len(
                    descriptor["visible_choices"]
                ),
                "scoring_atom_text_sha256": sha256_bytes(
                    str(descriptor["scoring_atom_text"]).encode("utf-8")
                ),
            }
        )
        role_row = {
            "blind_packet_id": blind_id,
            "blind_mix_rank_sha256": descriptor["blind_mix_rank_sha256"],
            "private_source_set": descriptor["private_source_set"],
            "case_id": descriptor["case_id"],
            "atom_id": descriptor["atom_id"],
            "source_row_id": descriptor["source_row_id"],
            "source_packet_id": descriptor["source_packet_id"],
            "choice_crosswalk": descriptor["private_choices"],
        }
        role_crosswalk_rows.append(role_row)
        if descriptor["private_source_set"] == PRIVATE_SOURCE_PRIMARY:
            target_queue_rows.append(
                {
                    "blind_packet_id": blind_id,
                    "source_row_id": descriptor["source_row_id"],
                    "case_id": descriptor["case_id"],
                    "atom_id": descriptor["atom_id"],
                    "choice_crosswalk": descriptor["private_choices"],
                    "status": "PENDING_TWO_INDEPENDENT_VOTES",
                }
            )

    blind_manifest = {
        "schema_version": "v02-c8-blind-packet-manifest.v1",
        "status": "READY_FOR_TWO_INDEPENDENT_VOTES",
        "packet_total": 27,
        "decision_rule_sha256": DECISION_RULE_SHA256,
        "packets": packet_manifest_rows,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts["blind_packet_manifest.json"] = canonical_bytes(blind_manifest)

    source_lock = {
        "schema_version": "v02-c8-source-lock.v1",
        "status": "FROZEN_READ_ONLY_INPUTS",
        "inputs": {
            "c1_source_manifest": {
                "path": display_path(C1_DIR / "source_manifest.json"),
                "sha256": EXPECTED_INPUT_SHAS["c1_source_manifest"],
            },
            "c1_gate_contract": {
                "path": display_path(C1_DIR / "gate/gate_contract.json"),
                "sha256": EXPECTED_INPUT_SHAS["c1_gate_contract"],
            },
            "c6_completion": {
                "path": display_path(C6_RUN_DIR / "completion/main.json"),
                "sha256": EXPECTED_INPUT_SHAS["c6_completion"],
            },
            "c6_request_lock": {
                "path": display_path(
                    C6_RUN_DIR / "prepared/C6_request_lock.json"
                ),
                "sha256": EXPECTED_INPUT_SHAS["c6_request_lock"],
            },
            "c7_5_policy": {
                "path": display_path(C75_POLICY),
                "sha256": EXPECTED_INPUT_SHAS["c7_5_policy"],
            },
            "c7_6_policy": {
                "path": display_path(C76_POLICY),
                "sha256": EXPECTED_INPUT_SHAS["c7_6_policy"],
            },
            "c7_7_contract": {
                "path": display_path(C77_CONTRACT),
                "sha256": EXPECTED_INPUT_SHAS["c7_7_contract"],
            },
            "c7_7_packet_manifest": {
                "path": display_path(C77_PACKET_MANIFEST),
                "sha256": EXPECTED_INPUT_SHAS["c7_7_packet_manifest"],
            },
        },
        "case_inputs": case_locks,
        "decision_rule": DECISION_RULE,
        "decision_rule_sha256": DECISION_RULE_SHA256,
        "c7_7_mother_set_sha256": mother_set_sha,
        "read_only": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    route_ledger = {
        "schema_version": "v02-c8-private-route-ledger.v1",
        "status": "PARTIAL_PREFREEZE_PENDING_TWO_VOTES",
        "row_total": 49,
        "counts": {
            **EXPECTED_ROUTE_COUNTS,
            "mechanical_prefreeze_total": 28,
            "blind_review_total": 21,
        },
        "rows": route_rows,
        "mechanical_position_route_is_not_semantic_verdict": True,
        "mapping_freeze_allowed": False,
        "c5_rescore_allowed": False,
    }
    mechanical_prefreeze = {
        "schema_version": "v02-c8-private-mechanical-prefreeze.v1",
        "status": "FROZEN_MECHANICAL_SUBSET_ONLY",
        "row_total": 28,
        "source_counts": {
            "MECHANICAL_C6_UNIQUE_ROUTE": 17,
            "MECHANICAL_C7_5_SINGLE_CANDIDATE": 11,
        },
        "rows": mechanical_rows,
        "final_mapping_frozen": False,
    }
    target_queue = {
        "schema_version": "v02-c8-private-blind-review-queue.v1",
        "status": "PENDING_TWO_INDEPENDENT_VOTES",
        "row_total": 21,
        "multiple_choices_allowed_under_c7_6": True,
        "no_correspondence_is_exclusive": True,
        "rows": sorted(target_queue_rows, key=lambda row: row["source_row_id"]),
    }
    alias_crosswalk = {
        "schema_version": "v02-c8-private-event-alias-crosswalk.v1",
        "status": "PRIVATE_NOT_MODEL_VISIBLE",
        "alias_total": len(alias_rows),
        "aliases": sorted(alias_rows.values(), key=lambda row: row["alias_id"]),
        "reversible": True,
        "collision_total": 0,
    }
    role_crosswalk = {
        "schema_version": "v02-c8-private-packet-source-crosswalk.v1",
        "status": "PRIVATE_NOT_MODEL_VISIBLE",
        "packet_total": 27,
        "source_set_counts": {
            PRIVATE_SOURCE_PRIMARY: 21,
            PRIVATE_SOURCE_AUDIT: 6,
        },
        "rows": role_crosswalk_rows,
        "visible_role_label_emitted": False,
    }
    sampling_plan = {
        "schema_version": "v02-c8-private-fixed-audit-sampling.v1",
        "status": "FROZEN_BEFORE_VOTES",
        "algorithm": (
            "sort ascending by SHA256(seed + NUL + packet_id), "
            "tie-break packet_id; take first 6"
        ),
        "seed": AUDIT_SAMPLE_SEED,
        "mother_packet_total": 26,
        "mother_set_sha256": mother_set_sha,
        "ranked_mother_set": ranked_mother,
        "sample_total": 6,
        "selected_source_packet_ids": sorted(selected_packet_ids),
        "blind_mix_algorithm": (
            "sort ascending by SHA256(mix_seed + NUL + private_source_token), "
            "tie-break private_source_token"
        ),
        "blind_mix_seed": BLIND_MIX_SEED,
        "roles_visible_to_voters": False,
    }

    for name, value in {
        "source_lock.json": source_lock,
        "route_ledger_private.json": route_ledger,
        "mechanical_prefreeze_private.json": mechanical_prefreeze,
        "blind_review_queue_private.json": target_queue,
        "event_alias_crosswalk_private.json": alias_crosswalk,
        "packet_source_crosswalk_private.json": role_crosswalk,
        "audit_sampling_plan_private.json": sampling_plan,
    }.items():
        artifacts[name] = canonical_bytes(value)

    leakage_ticket = assert_model_visible_safe(
        artifacts,
        sorted(real_event_ids),
    )
    artifacts["model_visible_leakage_ticket.json"] = canonical_bytes(
        leakage_ticket
    )
    preparation_gate = {
        "schema_version": "v02-c8-preparation-gate.v1",
        "status": "PASS_PREPARATION_ONLY_PENDING_TWO_VOTES",
        "source_lock_pass": True,
        "route_row_total": 49,
        "mechanical_prefreeze_total": 28,
        "target_blind_review_total": 21,
        "hidden_audit_packet_total": 6,
        "mixed_blind_packet_total": 27,
        "decision_rule_exact_copy": True,
        "decision_rule_sha256": DECISION_RULE_SHA256,
        "real_event_alias_private": True,
        "visible_role_label_hits": 0,
        "old_source_write_total": 0,
        "mapping_freeze_allowed": False,
        "c5_rescore_allowed": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts["preparation_gate.json"] = canonical_bytes(preparation_gate)

    manifest_rows_out = [
        {
            "path": path,
            "sha256": sha256_bytes(raw),
            "visibility": (
                "model_visible"
                if path.startswith("blind_packets/")
                else "private_or_operational"
            ),
        }
        for path, raw in sorted(artifacts.items())
    ]
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c8-preparation-artifact-manifest.v1",
            "file_total_excluding_self": len(manifest_rows_out),
            "files": manifest_rows_out,
            "artifact_set_sha256": canonical_sha(manifest_rows_out),
            "model_api_calls": 0,
            "network_requests": 0,
            "mapping_freeze_allowed": False,
            "c5_rescore_allowed": False,
        }
    )
    return artifacts


def write_or_verify(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise C8WorkspaceError("C8 准备工件连续两次构造不一致")
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(first.items()):
        path = output_dir / relative
        if path.is_file():
            if path.read_bytes() != raw:
                raise C8WorkspaceError(f"C8 已有工件漂移：{relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    if actual != set(first):
        extras = sorted(actual - set(first))
        missing = sorted(set(first) - actual)
        raise C8WorkspaceError(
            f"C8 准备目录文件集合漂移：extra={extras}, missing={missing}"
        )
    return {
        "output_dir": display_path(output_dir),
        "file_total": len(first),
        "artifact_manifest_sha256": sha256_file(
            output_dir / "artifact_manifest.json"
        ),
        "route_row_total": 49,
        "mechanical_prefreeze_total": 28,
        "target_blind_review_total": 21,
        "hidden_audit_packet_total": 6,
        "mixed_blind_packet_total": 27,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 V02/C8 控制侧盲审准备工位")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="输出目录；默认写入 V02/C8 preparation 新区",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(
        json.dumps(
            write_or_verify(args.output_dir),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

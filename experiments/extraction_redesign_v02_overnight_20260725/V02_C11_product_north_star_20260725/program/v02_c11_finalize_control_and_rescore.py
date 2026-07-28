#!/usr/bin/env python3
"""V02/C11.1：机械终结控制臂映射，并按三视图重算 C5。

本程序只读 C8/C9 冻结工件，不回写历史停点。唯一人工来源是 C11.1 已
拍的机械推导：B01-A09 只映射 EV-C0033-43，来源仍记 CZ_MANUAL。
输出只是一份可撤回的工作映射和探索性观察，不授予质量胜负或因果结论。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "tools").is_dir():
            return parent
    raise RuntimeError("无法定位小说架构仓库根目录")


ROOT = _find_repo_root()
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from v02_reporting_views import build_views  # noqa: E402


V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
C8_ROOT = V02_ROOT / "V02_C8_control_mapping_and_interpretability"
C9_ROOT = V02_ROOT / "V02_C9_engineering_gate_fix_20260725"
C7_ROOT = V02_ROOT / "V02_C7_final_mapping_and_C5_rescore"
C11_ROOT = V02_ROOT / "V02_C11_product_north_star_20260725"

PREFREEZE = C8_ROOT / "preparation/mechanical_prefreeze_private.json"
ROUTE_LEDGER = C8_ROOT / "preparation/route_ledger_private.json"
C9_RECEIPT = C9_ROOT / "engineering_fix_receipt.json"
C9_R02 = C9_ROOT / "consensus_rerun_r02"
C9_MANIFEST = C9_R02 / "artifact_manifest.json"
C9_QUEUE = C9_R02 / "target_disagreement_queue_private.json"
C9_TALLY = C9_R02 / "unblinded_tally_private.json"
TREATMENT_MAPPING = C7_ROOT / "mapping/final_treatment_mapping.json"
TREATMENT_METRICS = C7_ROOT / "mapping/treatment_cardinality_metrics.json"
C8_CONSENSUS_TOOL = ROOT / "tools/v02_c8_control_consensus.py"
REPORTING_TOOL = ROOT / "tools/v02_reporting_views.py"

DEFAULT_CONTROL_OUTPUT = C8_ROOT / "control_mapping"
DEFAULT_C11_OUTPUT = C11_ROOT / "C11_1_control_terminal_and_rescore"
C11_APPROVED_AUXILIARY_SUBTREES = frozenset(
    {
        "N10_active",
        "N11_active",
    }
)

CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
CASE_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
CONTROL_PARENT_EVENT_COUNTS = {
    "B02-U0039": 44,
    "B03-U0041": 10,
    "B01-U0033": 75,
}
TREATMENT_PARENT_EVENT_COUNTS = {
    "B02-U0039": 13,
    "B03-U0041": 10,
    "B01-U0033": 14,
}
NO_CORRESPONDENCE = "NO_CORRESPONDENCE"
CONCLUSION_MISSING = "MATERIALS_INSUFFICIENT_CANNOT_ADJUDICATE"
X04_CONDITIONAL_INVALIDATION = {
    "trigger": "CZ_APPROVES_X04",
    "active_now": False,
    "required_action": "INVALIDATE_AND_RECOMPUTE_AS_BOUNDS",
    "current_artifact_remains_unconditional_truth": False,
}
C11_WORK_ORDER_PAGE_ID = "eb8821e57b67472db9f220b46110dcfd"
C11_WORK_ORDER_PAGE_URL = (
    "https://app.notion.com/p/"
    "v0-2-0API-A-CZ-Codex-_20260725-eb8821e57b67472db9f220b46110dcfd"
)
C11_AUTHORITY_READBACK_AT = "2026-07-25T10:46:11.303Z"
C11_1_AUTHORITY_EXCERPT = """### C11.1 B01-A09 落判＝只选乙（`EV-C0033-43`）——机械推导，非新拍板
- **定性**：本条**不是新的语义判断**，而是从 **CZ 15:16 已亲拍的同一个原子判词**（C7-023＝`MAP_TO::EV-C0033-11`，理由原文「核心命题明确承载，多出的心态句不构成不对应」）＋ **C8.1 最高约束「尺子逐字同一把」**机械推出的唯一结果。判「甲＋乙」就是同一原子两臂用两把尺子，直接违反已拍约束。
- **回填来源标记仍为 ****`CZ_MANUAL`**（因其依据是 CZ 亲拍的尺子），但须在回包内明写「由 C11.1 机械推导、CZ 未逐条重拍、可随时撤回」。
- **解锁效果**：C9.3 四前置中的第 3 条（分歧行 CZ 判词）视为已到；其余三条照旧机械校验。四条全齐 → 冻结对照臂映射出 SHA → 复算 C5。
- **复算 C5 的两条新约束**：① 报数照 **C10.2 三套口径**（微平均／宏平均／逐章值与范围），❌ `25／49` 单独出现即不合格；② **无论复算出什么数，都 ❌ 不得解释为「锚先行有效／无效」**——两份外部件（X02 与研究包 E1）已独立交叉证实本轮实验 A 不是单变量；该数只能当「锚先行倒装整包」这个复合变量的观测值，本条必须逐字写进回包首屏。"""

TERMINAL_ROW = {
    "source_row_id": "C8-R036",
    "atom_id": "Z74B-B01-U0033-A09",
    "case_id": "B01-U0033",
    "packet_id": "C8-BLIND-018",
    "selected_event_ids": ["EV-C0033-43"],
}

EXPECTED_INPUT_SHAS = {
    PREFREEZE: "618ede3db63bee07b93b5217dc1e07b4aa97b1c913aea0b221ae553fcffe2b23",
    ROUTE_LEDGER: "d61b03f7eb50cb9c72882cd31ece798c30c3d21bccd029f33e5163a3d574a920",
    C9_RECEIPT: "b83e5c4d651318fe0e66597c47b279a54c0f96b9757c684d07f5582ea0378be0",
    C9_MANIFEST: "88c5dcb873de14ee081172a2c2ce111412935851df2db313faea577065d77d6c",
    C9_QUEUE: "7fc10db4ffbf3cdf1d24975fc660386426590b98feb9abba2d257c27bade8b74",
    C9_TALLY: "b3b7b482a7280ee21b850d63e2b5e422e243208034d4c15d9a204d07a7b174cf",
    TREATMENT_MAPPING: "7ddfcb2b29ed7fc1340ebd323da8603f44a3bef7d6511bce474ecbbf78acea51",
    TREATMENT_METRICS: "72136f51d54b76ed4b7d156d6551ded35b2d8eccee57ba1e07d82368cc71b2d1",
    C8_CONSENSUS_TOOL: "8e8796f2077e48a1567fc107945de4347156f292539fde0a2e79bc2562c0f606",
    REPORTING_TOOL: "8157e93882c1ead4d080d516bb4aec52aedb5cd9fe9a69a20a233d8d5e755cc6",
}


class C11FinalizeError(RuntimeError):
    """C11.1 不能从冻结输入安全生成工作映射。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C11FinalizeError(f"冻结输入不存在：{path}")
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _verify_manifest_files() -> None:
    manifest = read_json(C9_MANIFEST)
    rows = manifest.get("files")
    if (
        manifest.get("artifact_set_sha256")
        != "adea9e2b3a9440962f2071029b06e9960ec65e0a28766ed8662bb9fd8d5de700"
        or not isinstance(rows, list)
        or len(rows) != 9
    ):
        raise C11FinalizeError("C9 r02 manifest 身份漂移")
    for row in rows:
        if not isinstance(row, Mapping):
            raise C11FinalizeError("C9 r02 manifest 含非对象")
        relative = row.get("path")
        digest = row.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise C11FinalizeError("C9 r02 manifest 行字段非法")
        if sha256_file(C9_R02 / relative) != digest:
            raise C11FinalizeError(f"C9 r02 冻结件漂移：{relative}")


def verify_inputs() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path, expected in EXPECTED_INPUT_SHAS.items():
        actual = sha256_file(path)
        if actual != expected:
            raise C11FinalizeError(f"输入 SHA 漂移：{display_path(path)}")
        rows.append({"path": display_path(path), "sha256": actual})
    _verify_manifest_files()

    receipt = read_json(C9_RECEIPT)
    rerun = receipt.get("rerun", {})
    boundary = receipt.get("freeze_boundary", {})
    if (
        receipt.get("status")
        != "PASS_ENGINEERING_GATES_RERUN_BLOCKED_SEMANTIC_DISAGREEMENT"
        or rerun.get("target_agreement_total") != 20
        or rerun.get("target_disagreement_total") != 1
        or rerun.get("audit_agreement_total") != 6
        or rerun.get("audit_disagreement_total", 0) != 0
        or boundary.get("final_control_mapping_generated") is not False
    ):
        raise C11FinalizeError("C9 r02 三项前置工程闸未保持")

    queue = read_json(C9_QUEUE)
    queue_rows = queue.get("rows")
    if (
        queue.get("row_total") != 1
        or queue.get("mapping_freeze_allowed") is not False
        or not isinstance(queue_rows, list)
        or len(queue_rows) != 1
    ):
        raise C11FinalizeError("C9 r02 语义分歧队列不是冻结的一行")
    row = queue_rows[0]
    for key in ("source_row_id", "atom_id", "case_id", "packet_id"):
        if row.get(key) != TERMINAL_ROW[key]:
            raise C11FinalizeError(f"C11.1 终判靶身份漂移：{key}")
    if row.get("first_selected_event_ids") != ["EV-C0033-43"] or row.get(
        "second_selected_event_ids"
    ) != ["EV-C0033-42", "EV-C0033-43"]:
        raise C11FinalizeError("C11.1 终判靶两票内容漂移")
    return rows


def _cardinality_metrics(
    mapping_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    split_histogram: Counter[int] = Counter()
    event_to_atoms: dict[tuple[str, str], list[str]] = defaultdict(list)
    case_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in mapping_rows:
        case_id = str(row["case_id"])
        case_rows[case_id].append(row)
        event_ids = list(row["candidate_event_ids"])
        if event_ids:
            split_histogram[len(event_ids)] += 1
        for event_id in event_ids:
            event_to_atoms[(case_id, str(event_id))].append(str(row["atom_id"]))

    merge_histogram = Counter(len(atom_ids) for atom_ids in event_to_atoms.values())
    by_case: dict[str, Any] = {}
    for case_id in CASE_ORDER:
        rows = case_rows[case_id]
        mapped_rows = [row for row in rows if row["candidate_event_ids"]]
        case_split = Counter(len(row["candidate_event_ids"]) for row in mapped_rows)
        case_event_to_atoms = {
            event_id: atom_ids
            for (event_case, event_id), atom_ids in event_to_atoms.items()
            if event_case == case_id
        }
        case_merge = Counter(len(atom_ids) for atom_ids in case_event_to_atoms.values())
        by_case[case_id] = {
            "produced_parent_event_total": CONTROL_PARENT_EVENT_COUNTS[case_id],
            "scoring_atom_total": CASE_DENOMINATORS[case_id],
            "mapped_atom_total": len(mapped_rows),
            "unmapped_atom_total": CASE_DENOMINATORS[case_id] - len(mapped_rows),
            "coverage_rate": len(mapped_rows) / CASE_DENOMINATORS[case_id],
            "atom_split_degree_histogram": {
                str(key): value for key, value in sorted(case_split.items())
            },
            "mapped_event_degree_histogram": {
                str(key): value for key, value in sorted(case_merge.items())
            },
            "maximum_events_per_atom": max(case_split, default=0),
            "maximum_atoms_per_mapped_event": max(case_merge, default=0),
        }

    mapped_total = sum(1 for row in mapping_rows if row["candidate_event_ids"])
    return {
        "schema_version": "v02-c11-control-cardinality-metrics.v1",
        "arm": "control",
        "produced_parent_event_total": sum(CONTROL_PARENT_EVENT_COUNTS.values()),
        "produced_parent_event_total_by_case": CONTROL_PARENT_EVENT_COUNTS,
        "scoring_atom_total": 49,
        "mapped_atom_total": mapped_total,
        "unmapped_atom_total": 49 - mapped_total,
        "coverage_rate": mapped_total / 49,
        "atom_to_event_link_total": sum(
            len(row["candidate_event_ids"]) for row in mapping_rows
        ),
        "mapped_parent_event_total": len(event_to_atoms),
        "atom_split_degree_histogram": {
            str(key): value for key, value in sorted(split_histogram.items())
        },
        "one_event_atom_count": split_histogram[1],
        "multi_event_atom_count": sum(
            value for key, value in split_histogram.items() if key > 1
        ),
        "maximum_events_per_atom": max(split_histogram, default=0),
        "mapped_event_degree_histogram": {
            str(key): value for key, value in sorted(merge_histogram.items())
        },
        "one_to_one_mapped_event_count": merge_histogram[1],
        "many_to_one_mapped_event_count": sum(
            value for key, value in merge_histogram.items() if key > 1
        ),
        "maximum_atoms_per_mapped_event": max(merge_histogram, default=0),
        "by_case_breakdown": by_case,
        "event_loads": [
            {
                "case_id": case_id,
                "event_id": event_id,
                "atom_ids": sorted(atom_ids),
                "atom_count": len(atom_ids),
            }
            for (case_id, event_id), atom_ids in sorted(event_to_atoms.items())
        ],
    }


def _mapping_artifacts() -> dict[str, bytes]:
    prefreeze = read_json(PREFREEZE)
    ledger = read_json(ROUTE_LEDGER)
    tally = read_json(C9_TALLY)
    prefreeze_rows = prefreeze.get("rows")
    ledger_rows = ledger.get("rows")
    tally_rows = tally.get("rows")
    if (
        not isinstance(prefreeze_rows, list)
        or len(prefreeze_rows) != 28
        or not isinstance(ledger_rows, list)
        or len(ledger_rows) != 49
        or not isinstance(tally_rows, list)
    ):
        raise C11FinalizeError("C8/C9 映射母集数量漂移")

    resolutions: dict[str, dict[str, Any]] = {}
    for row in prefreeze_rows:
        row_id = str(row["row_id"])
        resolutions[row_id] = {
            "case_id": row["case_id"],
            "atom_id": row["atom_id"],
            "selected_event_ids": list(row["selected_event_ids"]),
            "mapping_source": row["mapping_source"],
            "source_detail": {
                "row_id": row_id,
                "working_mapping_not_gold": True,
                "mechanical_working_mapping_not_semantic_truth": True,
                "revocable_by_later_semantic_verdict": True,
            },
        }

    target_rows = [row for row in tally_rows if row.get("private_source_set") == "S1"]
    if len(target_rows) != 21:
        raise C11FinalizeError("C9 r02 正式靶不是 21 行")
    for row in target_rows:
        row_id = str(row["source_row_id"])
        if row_id in resolutions:
            raise C11FinalizeError(f"C9 判词重复接管机械行：{row_id}")
        is_terminal = row_id == TERMINAL_ROW["source_row_id"]
        if is_terminal:
            if row.get("agreement") is not False:
                raise C11FinalizeError("C11.1 终判靶不再是唯一分歧")
            event_ids = list(TERMINAL_ROW["selected_event_ids"])
            source = "CZ_MANUAL"
            source_detail = {
                "row_id": row_id,
                "blind_packet_id": TERMINAL_ROW["packet_id"],
                "authority": "C11.1_MECHANICAL_DERIVATION_FROM_PRIOR_CZ_VERDICT",
                "cz_row_rejudged": False,
                "same_ruler_constraint": True,
                "mechanically_derived": True,
                "revocable": True,
                "required_receipt_statement": (
                    "C11.1 mechanical derivation, CZ did not rejudge this row, "
                    "revocable."
                ),
            }
        else:
            if row.get("agreement") is not True:
                raise C11FinalizeError(f"C9 r02 仍有未授权分歧：{row_id}")
            event_ids = list(row["unanimous_selected_event_ids"])
            source = "AI_CONSENSUS"
            source_detail = {
                "row_id": row_id,
                "blind_packet_id": row["packet_id"],
                "independent_vote_total": 2,
                "verdict_identity": "working_verdict_not_gold",
            }
        resolutions[row_id] = {
            "case_id": row["case_id"],
            "atom_id": row["atom_id"],
            "selected_event_ids": event_ids,
            "mapping_source": source,
            "source_detail": source_detail,
        }

    if len(resolutions) != 49:
        raise C11FinalizeError("控制臂 28 条机械行＋21 条判词未覆盖 49 原子")

    mapping_rows: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    seen_atoms: set[str] = set()
    for ordinal, ledger_row in enumerate(ledger_rows, 1):
        row_id = str(ledger_row["row_id"])
        resolution = resolutions.get(row_id)
        if (
            resolution is None
            or resolution["case_id"] != ledger_row["case_id"]
            or resolution["atom_id"] != ledger_row["atom_id"]
            or resolution["atom_id"] in seen_atoms
        ):
            raise C11FinalizeError(f"控制臂顺序或原子身份漂移：{row_id}")
        seen_atoms.add(str(resolution["atom_id"]))
        event_ids = list(resolution["selected_event_ids"])
        source = str(resolution["mapping_source"])
        source_counts[source] += 1
        mapping_rows.append(
            {
                "ordinal": ordinal,
                "case_id": resolution["case_id"],
                "atom_id": resolution["atom_id"],
                "mapping_outcome": "MAPPED" if event_ids else NO_CORRESPONDENCE,
                "selected_choice_ids": (
                    [f"MAP_TO::{event_id}" for event_id in event_ids]
                    if event_ids
                    else [NO_CORRESPONDENCE]
                ),
                "candidate_event_ids": event_ids,
                "split_degree": len(event_ids),
                "mapping_source": source,
                "source_detail": resolution["source_detail"],
                "verdict_identity": "working_mapping_not_gold",
            }
        )
    expected_counts = {
        "AI_CONSENSUS": 20,
        "CZ_MANUAL": 1,
        "MECHANICAL_C6_UNIQUE_ROUTE": 17,
        "MECHANICAL_C7_5_SINGLE_CANDIDATE": 11,
    }
    if dict(sorted(source_counts.items())) != expected_counts:
        raise C11FinalizeError(
            f"控制臂来源构成漂移：{dict(sorted(source_counts.items()))}"
        )

    metrics = _cardinality_metrics(mapping_rows)
    mapping = {
        "schema_version": "v02-c11-final-control-mapping.v1",
        "status": "FROZEN_V02_WORKING_TRUTH",
        "arm": "control",
        "mapping_identity": "working_mapping_not_gold",
        "formal_gold_changed": False,
        "formal_gold_text_emitted": False,
        "case_order": list(CASE_ORDER),
        "scoring_atom_total": 49,
        "row_total": 49,
        "source_counts": dict(sorted(source_counts.items())),
        "rows": mapping_rows,
        "mapping_freeze_allowed": True,
        "c5_rescore_allowed": True,
        "conditional_invalidation": X04_CONDITIONAL_INVALIDATION,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    freeze_receipt = {
        "schema_version": "v02-c11-control-mapping-freeze-receipt.v1",
        "status": "PASS_MAPPING_FROZEN_AFTER_C11_1_TERMINAL_DERIVATION",
        "mapping_row_total": 49,
        "c9_target_agreement_before_terminal_total": 20,
        "c9_target_disagreement_before_terminal_total": 1,
        "c9_audit_agreement_total": 6,
        "c9_audit_disagreement_total": 0,
        "terminal_row": TERMINAL_ROW,
        "terminal_source": "CZ_MANUAL",
        "required_receipt_statement": (
            "C11.1 mechanical derivation, CZ did not rejudge this row, revocable."
        ),
        "c9_history_rewritten": False,
        "c8_invalid_pending_engineering_fix_cleared_by_program_receipts": True,
        "c8_invalid_pending_engineering_fix_manually_erased": False,
        "mapping_freeze_allowed": True,
        "c5_rescore_allowed": True,
        "conditional_invalidation": X04_CONDITIONAL_INVALIDATION,
        "formal_gold_or_pointer_changed": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts = {
        "control_cardinality_metrics.json": canonical_bytes(metrics),
        "final_control_mapping.json": canonical_bytes(mapping),
        "mapping_freeze_receipt.json": canonical_bytes(freeze_receipt),
    }
    preimage = {name: sha256_bytes(raw) for name, raw in sorted(artifacts.items())}
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c11-control-mapping-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": name, "sha256": digest}
                for name, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "mapping_freeze_allowed": True,
            "c5_rescore_allowed": True,
            "conditional_invalidation": X04_CONDITIONAL_INVALIDATION,
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def _report_input(
    report_id: str,
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    cases = metrics["by_case_breakdown"]
    return {
        "schema_version": "v02-reporting-views-input.v1",
        "report_id": report_id,
        "exploratory_only": True,
        "quality_verdict_allowed": False,
        "chapters": [
            {
                "case_id": case_id,
                "numerator": cases[case_id]["mapped_atom_total"],
                "denominator": cases[case_id]["scoring_atom_total"],
            }
            for case_id in CASE_ORDER
        ],
    }


def _rescore_artifacts(
    mapping_artifacts: Mapping[str, bytes],
    verified_inputs: Sequence[Mapping[str, str]],
) -> dict[str, bytes]:
    control_mapping = json.loads(mapping_artifacts["final_control_mapping.json"])
    control_metrics = json.loads(mapping_artifacts["control_cardinality_metrics.json"])
    treatment_mapping = read_json(TREATMENT_MAPPING)
    treatment_metrics = read_json(TREATMENT_METRICS)
    if (
        control_mapping.get("row_total") != 49
        or control_metrics.get("mapped_atom_total") != 40
        or treatment_mapping.get("row_total") != 49
        or treatment_metrics.get("mapped_atom_total") != 25
    ):
        raise C11FinalizeError("双臂 49 原子映射或覆盖读数漂移")

    control_views = build_views(_report_input("C11_CONTROL_COVERAGE", control_metrics))
    treatment_views = build_views(
        _report_input("C11_TREATMENT_COVERAGE", treatment_metrics)
    )
    first_screen = {
        "schema_version": "v02-c11-c5-first-screen.v1",
        "status": "EXPLORATORY_OBSERVATION_ONLY",
        "parent_event_counts": {
            "control": sum(CONTROL_PARENT_EVENT_COUNTS.values()),
            "treatment": sum(TREATMENT_PARENT_EVENT_COUNTS.values()),
            "control_by_case": CONTROL_PARENT_EVENT_COUNTS,
            "treatment_by_case": TREATMENT_PARENT_EVENT_COUNTS,
        },
        "coverage_reporting_views": {
            "control": control_views["views"],
            "treatment": treatment_views["views"],
        },
        "cardinality": {
            "control": {
                "merge_degree_histogram": control_metrics[
                    "mapped_event_degree_histogram"
                ],
                "maximum_atoms_per_mapped_event": control_metrics[
                    "maximum_atoms_per_mapped_event"
                ],
                "split_degree_histogram": control_metrics[
                    "atom_split_degree_histogram"
                ],
                "maximum_events_per_atom": control_metrics["maximum_events_per_atom"],
            },
            "treatment": {
                "merge_degree_histogram": treatment_metrics[
                    "mapped_event_degree_histogram"
                ],
                "maximum_atoms_per_mapped_event": treatment_metrics[
                    "maximum_atoms_per_mapped_event"
                ],
                "split_degree_histogram": treatment_metrics[
                    "atom_split_degree_histogram"
                ],
                "maximum_events_per_atom": treatment_metrics["maximum_events_per_atom"],
            },
        },
        "coverage_observation": (
            "实验臂 25/49，低于对照臂 40/49；同时两臂父事件数为 "
            "37 与 129。该差异只作探索性观察，不能归因到锚先行。"
        ),
        "causal_attribution_allowed": False,
        "winner_declaration_allowed": False,
        "quality_result_registered": False,
        "standalone_25_of_49_allowed": False,
        "x04_future_invalidation_rule": (
            "若 X04 后续获批，当前映射与复算数字必须作废，改按上下界重算。"
        ),
    }
    missing_codes = [
        "TWO_ARM_ANCHOR_PARTIAL_VERDICTS_MISSING",
        "TWO_ARM_FIVE_LAYER_VERDICTS_MISSING",
        "C8_P0_SCORER_ONE_TO_ONE_ASSUMPTION_UNRESOLVED",
        "C8_P0_FIVE_LAYER_DENOMINATOR_MISMATCH_UNRESOLVED",
    ]
    sufficiency = {
        "schema_version": "v02-c11-c5-material-sufficiency.v1",
        "status": "MATERIALS_INSUFFICIENT",
        "selected_conclusion": CONCLUSION_MISSING,
        "missing_codes": missing_codes,
        "treatment_mapping_frozen": True,
        "control_mapping_frozen": True,
        "symmetric_49_atom_coverage_available": True,
        "two_arm_anchor_partial_verdicts_available": False,
        "two_arm_five_layer_verdicts_available": False,
        "c8_p0_items_fixed": False,
        "evaluate_gate_invoked": False,
        "quality_result_registered": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    receipt = {
        "schema_version": "v02-c11-c5-rescore-receipt.v1",
        "status": CONCLUSION_MISSING,
        "selected_conclusion": CONCLUSION_MISSING,
        "reason": (
            "两臂 49 原子工作映射已齐，但双臂逐原子的 ANCHOR_PARTIAL "
            "与五层判词仍缺，且 C8.3 两项 P0 按令保持待拍；覆盖不能替代这些层。"
        ),
        "gate_checks": {
            "anchor_partial_relative_reduction_at_least_50_percent": ("MISSING_INPUT"),
            "anchor_partial_declines_in_at_least_two_of_three_chapters": (
                "MISSING_INPUT"
            ),
            "fcr_qcr_asr_ucr_no_regression": "MISSING_INPUT",
            "sop_at_least_0_98": "MISSING_INPUT",
            "zero_additional_model_calls_for_this_rescore": True,
            "offline_denominator_is_49": True,
            "coverage_no_regression_guard": False,
        },
        "coverage_observation_is_quality_verdict": False,
        "causal_attribution_allowed": False,
        "winner_declaration_allowed": False,
        "anchor_first_freeze_allowed": False,
        "experiment_a_single_variable_claim_allowed": False,
        "x04_future_invalidation_required": True,
        "quality_result_registered": False,
        "evaluate_gate_invoked": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    authority_excerpt = canonical_bytes(
        {
            "schema_version": "v02-c11-1-authority-excerpt.v1",
            "page_id": C11_WORK_ORDER_PAGE_ID,
            "page_url": C11_WORK_ORDER_PAGE_URL,
            "connector_readback_at": C11_AUTHORITY_READBACK_AT,
            "excerpt_scope": "C11.1",
            "excerpt_text": C11_1_AUTHORITY_EXCERPT,
            "notion_full_page_content_sha256": None,
            "notion_full_page_content_sha256_status": ("NOT_AVAILABLE_NOT_INVENTED"),
        }
    )
    authority = {
        "schema_version": "v02-c11-1-authority-receipt.v1",
        "status": "PASS_C11_1_TERMINAL_DERIVATION_AND_RESCORE",
        "notion_work_order_page": C11_WORK_ORDER_PAGE_URL,
        "notion_work_order_page_id": C11_WORK_ORDER_PAGE_ID,
        "authority_excerpt_path": "authority_excerpt.json",
        "authority_excerpt_sha256": sha256_bytes(authority_excerpt),
        "terminal_row": TERMINAL_ROW,
        "terminal_source": "CZ_MANUAL",
        "required_receipt_statement": (
            "C11.1 mechanical derivation, CZ did not rejudge this row, revocable."
        ),
        "historical_c9_r02_rewritten": False,
        "historical_c7_rescore_rewritten": False,
        "input_receipts": list(verified_inputs),
        "control_mapping_sha256": sha256_bytes(
            mapping_artifacts["final_control_mapping.json"]
        ),
        "control_cardinality_sha256": sha256_bytes(
            mapping_artifacts["control_cardinality_metrics.json"]
        ),
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts = {
        "authority_excerpt.json": authority_excerpt,
        "authority_receipt.json": canonical_bytes(authority),
        "c5_rescore_receipt.json": canonical_bytes(receipt),
        "control_coverage_reporting_views.json": canonical_bytes(control_views),
        "first_screen_metrics.json": canonical_bytes(first_screen),
        "material_sufficiency.json": canonical_bytes(sufficiency),
        "treatment_coverage_reporting_views.json": canonical_bytes(treatment_views),
    }
    preimage = {name: sha256_bytes(raw) for name, raw in sorted(artifacts.items())}
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c11-1-artifact-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": name, "sha256": digest}
                for name, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "selected_conclusion": CONCLUSION_MISSING,
            "quality_result_registered": False,
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def build_artifacts() -> tuple[dict[str, bytes], dict[str, bytes]]:
    verified_inputs = verify_inputs()
    mapping_artifacts = _mapping_artifacts()
    rescore_artifacts = _rescore_artifacts(mapping_artifacts, verified_inputs)
    return mapping_artifacts, rescore_artifacts


def _is_approved_auxiliary_file(
    relative: str,
    approved_subtrees: frozenset[str],
) -> bool:
    parts = Path(relative).parts
    return len(parts) > 1 and parts[0] in approved_subtrees


def _actual_files(directory: Path) -> set[str]:
    if not directory.exists():
        return set()
    return {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _verify_directory(
    directory: Path,
    artifacts: Mapping[str, bytes],
    *,
    approved_auxiliary_subtrees: frozenset[str] = frozenset(),
) -> None:
    actual = _actual_files(directory)
    required = set(artifacts)
    missing = required - actual
    unexpected = {
        relative
        for relative in actual - required
        if not _is_approved_auxiliary_file(
            relative,
            approved_auxiliary_subtrees,
        )
    }
    if missing or unexpected:
        raise C11FinalizeError(
            "输出目录工件集合不闭合："
            f"missing={sorted(missing)} unexpected={sorted(unexpected)}"
        )
    for relative, raw in sorted(artifacts.items()):
        path = directory / relative
        if path.read_bytes() != raw:
            raise C11FinalizeError(f"既有输出字节漂移：{display_path(path)}")


def _check_or_write(
    directory: Path,
    artifacts: Mapping[str, bytes],
    *,
    approved_auxiliary_subtrees: frozenset[str] = frozenset(),
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    actual = _actual_files(directory)
    unexpected = {
        relative
        for relative in actual - set(artifacts)
        if not _is_approved_auxiliary_file(
            relative,
            approved_auxiliary_subtrees,
        )
    }
    if unexpected:
        raise C11FinalizeError(f"输出目录含未登记文件：{sorted(unexpected)}")
    for relative, raw in sorted(artifacts.items()):
        path = directory / relative
        if path.is_file() and path.read_bytes() != raw:
            raise C11FinalizeError(f"既有输出字节漂移：{display_path(path)}")
    for relative, raw in sorted(artifacts.items()):
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def write_or_verify(
    control_output: Path = DEFAULT_CONTROL_OUTPUT,
    c11_output: Path = DEFAULT_C11_OUTPUT,
) -> dict[str, Any]:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise C11FinalizeError("C11.1 连续两次机械构造不一致")
    control_artifacts, c11_artifacts = first
    _check_or_write(control_output, control_artifacts)
    _check_or_write(
        c11_output,
        c11_artifacts,
        approved_auxiliary_subtrees=C11_APPROVED_AUXILIARY_SUBTREES,
    )
    return {
        "status": CONCLUSION_MISSING,
        "control_output": display_path(control_output),
        "c11_output": display_path(c11_output),
        "control_mapping_sha256": sha256_file(
            control_output / "final_control_mapping.json"
        ),
        "c11_manifest_sha256": sha256_file(c11_output / "artifact_manifest.json"),
        "mechanical_double_run_identical": True,
        "quality_result_registered": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def verify_existing_outputs(
    control_output: Path = DEFAULT_CONTROL_OUTPUT,
    c11_output: Path = DEFAULT_C11_OUTPUT,
) -> dict[str, Any]:
    control_artifacts, c11_artifacts = build_artifacts()
    _verify_directory(control_output, control_artifacts)
    _verify_directory(
        c11_output,
        c11_artifacts,
        approved_auxiliary_subtrees=C11_APPROVED_AUXILIARY_SUBTREES,
    )
    return {
        "status": CONCLUSION_MISSING,
        "control_output": display_path(control_output),
        "c11_output": display_path(c11_output),
        "control_mapping_sha256": sha256_file(
            control_output / "final_control_mapping.json"
        ),
        "c11_manifest_sha256": sha256_file(c11_output / "artifact_manifest.json"),
        "existing_outputs_verified": True,
        "approved_auxiliary_subtrees": sorted(C11_APPROVED_AUXILIARY_SUBTREES),
        "quality_result_registered": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--control-output",
        type=Path,
        default=DEFAULT_CONTROL_OUTPUT,
    )
    parser.add_argument(
        "--c11-output",
        type=Path,
        default=DEFAULT_C11_OUTPUT,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            write_or_verify(
                args.control_output.resolve(),
                args.c11_output.resolve(),
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

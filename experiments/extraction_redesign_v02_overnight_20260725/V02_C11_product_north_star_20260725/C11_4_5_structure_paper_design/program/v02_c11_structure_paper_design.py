from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator


DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_VERSION = "v02-c11-structure-paper-design.v1"
CANDIDATE_STATUS = "candidate_silver_not_active"
MISSING_PLAN_FIELDS = "CHAPTER_PLAN_V2_FIELD_NAMES_MISSING"
MISSING_OWNER_FIELD = "ASSERTION_OWNER_CANONICAL_FIELD_NAME_MISSING"
OWNER_VALUES = (
    "narrator",
    "character_speech",
    "character_thought",
    "document_or_system",
    "unknown",
)
RECONCILIATION_STATES = (
    "realized_exact",
    "realized_variant",
    "omitted",
    "contradicted",
    "new_unplanned",
    "deferred",
)
SCENE_TEXTURE_KINDS = (
    "place",
    "time_or_light",
    "key_visual_object",
    "camera_suggestion",
)
AFFECT_VALENCES = (
    "positive",
    "negative",
    "neutral",
    "unknown",
)
MANAGED_PROGRAM_FILES = ("program/v02_c11_structure_paper_design.py",)


class PaperDesignError(RuntimeError):
    """C11.4/C11.5 纸面候选的机械合同不成立。"""


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "AGENTS.md").is_file() and (candidate / "experiments").is_dir():
            return candidate
    raise PaperDesignError("找不到小说架构仓库根目录")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
TASK_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = TASK_ROOT
C11_2_CATALOG = (
    TASK_ROOT.parent
    / "C11_2_duse_question_expansion"
    / "catalog"
    / "question_family_catalog.json"
)
C4_ROOT = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "V02_C4_transport_probe"
)
C4_CATALOG_DIR = C4_ROOT / "catalogs"
C4_RUN_ROOT = REPO_ROOT / "runs" / "V02_实验A锚先行倒装_C4_r03_20260725"

SOURCE_CASES = {
    "B02-U0039": {
        "catalog": C4_CATALOG_DIR / "B02-U0039.json",
        "candidate": (C4_RUN_ROOT / "samples/main/B02-U0039/candidate/model_json.json"),
    },
    "B03-U0041": {
        "catalog": C4_CATALOG_DIR / "B03-U0041.json",
        "candidate": (C4_RUN_ROOT / "samples/main/B03-U0041/candidate/model_json.json"),
    },
    "B01-U0033": {
        "catalog": C4_CATALOG_DIR / "B01-U0033.json",
        "candidate": (C4_RUN_ROOT / "samples/main/B01-U0033/candidate/model_json.json"),
    },
}


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PaperDesignError(f"JSON 读取失败：{path}") from exc


def _strict_object(
    *,
    properties: Mapping[str, Any],
    required: Sequence[str],
    title: str,
) -> dict[str, Any]:
    return {
        "type": "object",
        "title": title,
        "additionalProperties": False,
        "properties": dict(properties),
        "required": list(required),
    }


def build_c11_4_schemas() -> dict[str, dict[str, Any]]:
    dual_order = {
        "$schema": DRAFT_2020_12,
        "$id": "https://local.invalid/v02/c11/dual_order.v0.1.schema.json",
        **_strict_object(
            title="C11.4 dual story/discourse order candidate",
            properties={
                "schema_version": {"const": "v02-dual-order.v0.1"},
                "candidate_status": {"const": CANDIDATE_STATUS},
                "paper_only": {"const": True},
                "story_order": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1},
                },
                "discourse_order": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1},
                },
                "orders_share_members_only": {"const": True},
                "merged_order_field_forbidden": {"const": True},
            },
            required=(
                "schema_version",
                "candidate_status",
                "paper_only",
                "story_order",
                "discourse_order",
                "orders_share_members_only",
                "merged_order_field_forbidden",
            ),
        ),
    }

    plan_event_store = {
        "$schema": DRAFT_2020_12,
        "$id": ("https://local.invalid/v02/c11/plan_event_store.v0.1.schema.json"),
        **_strict_object(
            title="C11.4 plan event store candidate",
            properties={
                "schema_version": {"const": "v02-plan-event-store.v0.1"},
                "candidate_status": {"const": CANDIDATE_STATUS},
                "paper_only": {"const": True},
                "plan_events": {
                    "type": "array",
                    "minItems": 1,
                    "items": _strict_object(
                        title="planned event identity",
                        properties={
                            "plan_event_id": {
                                "type": "string",
                                "pattern": "^PE-[0-9]{4}$",
                            }
                        },
                        required=("plan_event_id",),
                    ),
                },
                "history": {
                    "type": "array",
                    "items": _strict_object(
                        title="history fact reference only",
                        properties={
                            "fact_ref": {
                                "type": "string",
                                "minLength": 1,
                            }
                        },
                        required=("fact_ref",),
                    ),
                },
                "fact_payload_copied_into_history": {"const": False},
            },
            required=(
                "schema_version",
                "candidate_status",
                "paper_only",
                "plan_events",
                "history",
                "fact_payload_copied_into_history",
            ),
        ),
    }

    reconciliation = {
        "$schema": DRAFT_2020_12,
        "$id": (
            "https://local.invalid/v02/c11/plan_prose_reconciliation.v0.1.schema.json"
        ),
        **_strict_object(
            title="C11.4 plan/prose reconciliation candidate",
            properties={
                "schema_version": {"const": "v02-plan-prose-reconciliation.v0.1"},
                "candidate_status": {"const": CANDIDATE_STATUS},
                "paper_only": {"const": True},
                "plan_event_id": {
                    "type": "string",
                    "pattern": "^PE-[0-9]{4}$",
                },
                "state": {"enum": list(RECONCILIATION_STATES)},
                "new_unplanned_scan_tokens": {
                    "type": "integer",
                    "minimum": 0,
                },
                "full_reextract_tokens": {
                    "type": "integer",
                    "minimum": 1,
                },
                "saving_verdict": {"enum": ["SAVING", "NOT_SAVING"]},
                "threshold_rule": {
                    "const": (
                        "new_unplanned_scan_tokens > "
                        "0.60 * full_reextract_tokens => NOT_SAVING"
                    )
                },
            },
            required=(
                "schema_version",
                "candidate_status",
                "paper_only",
                "plan_event_id",
                "state",
                "new_unplanned_scan_tokens",
                "full_reextract_tokens",
                "saving_verdict",
                "threshold_rule",
            ),
        ),
    }

    chapter_contract_bundle = {
        "$schema": DRAFT_2020_12,
        "$id": (
            "https://local.invalid/v02/c11/chapter_contract_bundle.v0.1.schema.json"
        ),
        "$defs": {
            "chapter_fact_graph_v2": _strict_object(
                title="chapter_fact_graph_v2 paper contract",
                properties={
                    "contract_id": {"const": "chapter_fact_graph_v2"},
                    "status": {"const": "PAPER_ONLY"},
                },
                required=("contract_id", "status"),
            ),
            "chapter_plan_v2": _strict_object(
                title="chapter_plan_v2 blocked contract shell",
                properties={
                    "contract_id": {"const": "chapter_plan_v2"},
                    "status": {"const": "BLOCKED_FIELD_NAMES_MISSING"},
                    "missing_marker": {"const": MISSING_PLAN_FIELDS},
                    "activation_allowed": {"const": False},
                },
                required=(
                    "contract_id",
                    "status",
                    "missing_marker",
                    "activation_allowed",
                ),
            ),
            "chapter_execution_packet_v1": _strict_object(
                title="chapter_execution_packet_v1 paper contract",
                properties={
                    "contract_id": {"const": "chapter_execution_packet_v1"},
                    "status": {"const": "PAPER_ONLY"},
                    "token_threshold_added": {"const": False},
                },
                required=(
                    "contract_id",
                    "status",
                    "token_threshold_added",
                ),
            ),
            "projection_card_v1": _strict_object(
                title="projection_card_v1 paper contract",
                properties={
                    "contract_id": {"const": "projection_card_v1"},
                    "status": {"const": "PAPER_ONLY"},
                    "truth_writeback_allowed": {"const": False},
                },
                required=(
                    "contract_id",
                    "status",
                    "truth_writeback_allowed",
                ),
            ),
        },
        **_strict_object(
            title="C11.4 chapter contract bundle candidate",
            properties={
                "schema_version": {"const": "v02-chapter-contract-bundle.v0.1"},
                "candidate_status": {"const": CANDIDATE_STATUS},
                "paper_only": {"const": True},
                "chapter_fact_graph_v2": {"$ref": "#/$defs/chapter_fact_graph_v2"},
                "chapter_plan_v2": {"$ref": "#/$defs/chapter_plan_v2"},
                "chapter_execution_packet_v1": {
                    "$ref": "#/$defs/chapter_execution_packet_v1"
                },
                "projection_card_v1": {"$ref": "#/$defs/projection_card_v1"},
            },
            required=(
                "schema_version",
                "candidate_status",
                "paper_only",
                "chapter_fact_graph_v2",
                "chapter_plan_v2",
                "chapter_execution_packet_v1",
                "projection_card_v1",
            ),
        ),
    }

    assertion_owner = {
        "$schema": DRAFT_2020_12,
        "$id": ("https://local.invalid/v02/c11/assertion_owner.v0.1.schema.json"),
        **_strict_object(
            title="C11.4 assertion owner candidate declaration",
            properties={
                "schema_version": {"const": "v02-assertion-owner.v0.1"},
                "candidate_status": {"const": CANDIDATE_STATUS},
                "paper_only": {"const": True},
                "canonical_field_name_status": {"const": MISSING_OWNER_FIELD},
                "candidate_values": {"const": list(OWNER_VALUES)},
                "activation_allowed": {"const": False},
            },
            required=(
                "schema_version",
                "candidate_status",
                "paper_only",
                "canonical_field_name_status",
                "candidate_values",
                "activation_allowed",
            ),
        ),
    }
    return {
        "dual_order": dual_order,
        "plan_event_store": plan_event_store,
        "plan_prose_reconciliation": reconciliation,
        "chapter_contract_bundle": chapter_contract_bundle,
        "assertion_owner": assertion_owner,
    }


def build_c11_4_examples() -> tuple[dict[str, Any], dict[str, Any]]:
    valid = {
        "dual_order": {
            "schema_version": "v02-dual-order.v0.1",
            "candidate_status": CANDIDATE_STATUS,
            "paper_only": True,
            "story_order": ["PE-0001", "PE-0002"],
            "discourse_order": ["PE-0002", "PE-0001"],
            "orders_share_members_only": True,
            "merged_order_field_forbidden": True,
        },
        "plan_event_store": {
            "schema_version": "v02-plan-event-store.v0.1",
            "candidate_status": CANDIDATE_STATUS,
            "paper_only": True,
            "plan_events": [
                {"plan_event_id": "PE-0001"},
                {"plan_event_id": "PE-0002"},
            ],
            "history": [{"fact_ref": "PE-0001"}],
            "fact_payload_copied_into_history": False,
        },
        "plan_prose_reconciliation": {
            "schema_version": "v02-plan-prose-reconciliation.v0.1",
            "candidate_status": CANDIDATE_STATUS,
            "paper_only": True,
            "plan_event_id": "PE-0001",
            "state": "new_unplanned",
            "new_unplanned_scan_tokens": 61,
            "full_reextract_tokens": 100,
            "saving_verdict": "NOT_SAVING",
            "threshold_rule": (
                "new_unplanned_scan_tokens > 0.60 * full_reextract_tokens => NOT_SAVING"
            ),
        },
        "chapter_contract_bundle": {
            "schema_version": "v02-chapter-contract-bundle.v0.1",
            "candidate_status": CANDIDATE_STATUS,
            "paper_only": True,
            "chapter_fact_graph_v2": {
                "contract_id": "chapter_fact_graph_v2",
                "status": "PAPER_ONLY",
            },
            "chapter_plan_v2": {
                "contract_id": "chapter_plan_v2",
                "status": "BLOCKED_FIELD_NAMES_MISSING",
                "missing_marker": MISSING_PLAN_FIELDS,
                "activation_allowed": False,
            },
            "chapter_execution_packet_v1": {
                "contract_id": "chapter_execution_packet_v1",
                "status": "PAPER_ONLY",
                "token_threshold_added": False,
            },
            "projection_card_v1": {
                "contract_id": "projection_card_v1",
                "status": "PAPER_ONLY",
                "truth_writeback_allowed": False,
            },
        },
        "assertion_owner": {
            "schema_version": "v02-assertion-owner.v0.1",
            "candidate_status": CANDIDATE_STATUS,
            "paper_only": True,
            "canonical_field_name_status": MISSING_OWNER_FIELD,
            "candidate_values": list(OWNER_VALUES),
            "activation_allowed": False,
        },
    }
    invalid = {
        "dual_order": {
            "schema_version": "v02-dual-order.v0.1",
            "candidate_status": CANDIDATE_STATUS,
            "paper_only": True,
            "order": ["PE-0001", "PE-0002"],
            "orders_share_members_only": True,
            "merged_order_field_forbidden": False,
        },
        "plan_event_store": {
            "schema_version": "v02-plan-event-store.v0.1",
            "candidate_status": CANDIDATE_STATUS,
            "paper_only": True,
            "plan_events": [
                {
                    "plan_event_id": "PE-0001",
                    "fact_id": "FACT-0001",
                }
            ],
            "history": [{"fact_ref": "FACT-0001"}],
            "fact_payload_copied_into_history": False,
        },
        "plan_prose_reconciliation": {
            "schema_version": "v02-plan-prose-reconciliation.v0.1",
            "candidate_status": CANDIDATE_STATUS,
            "paper_only": True,
            "plan_event_id": "PE-0001",
            "state": "new_unplanned",
            "new_unplanned_scan_tokens": 70,
            "full_reextract_tokens": 100,
            "saving_verdict": "SAVING",
            "threshold_rule": (
                "new_unplanned_scan_tokens > 0.60 * full_reextract_tokens => NOT_SAVING"
            ),
        },
        "chapter_contract_bundle": {
            **valid["chapter_contract_bundle"],
            "projection_card_v1": {
                "contract_id": "projection_card_v1",
                "status": "PAPER_ONLY",
                "truth_writeback_allowed": True,
            },
        },
        "assertion_owner": {
            "schema_version": "v02-assertion-owner.v0.1",
            "candidate_status": CANDIDATE_STATUS,
            "paper_only": True,
            "canonical_field_name_status": MISSING_OWNER_FIELD,
            "candidate_values": list(OWNER_VALUES),
            "literalness": "explicit",
            "activation_allowed": False,
        },
    }
    return valid, invalid


def build_sidecar_schema() -> dict[str, Any]:
    evidence_source = {
        "case_id": {"type": "string", "minLength": 1},
        "source_event_id": {"type": "string", "minLength": 1},
        "anchor_id": {"type": "string", "pattern": "^E[0-9]{4}$"},
        "evidence_span": {"type": "string", "minLength": 1},
    }
    scene_item = _strict_object(
        title="scene texture item",
        properties={
            **evidence_source,
            "kind": {"enum": list(SCENE_TEXTURE_KINDS)},
        },
        required=(
            "case_id",
            "source_event_id",
            "anchor_id",
            "evidence_span",
            "kind",
        ),
    )
    affect_item = _strict_object(
        title="affect item",
        properties={
            **evidence_source,
            "holder": {"type": "string", "minLength": 1},
            "valence": {"enum": list(AFFECT_VALENCES)},
            "intensity": {"enum": ["low", "medium", "high"]},
        },
        required=(
            "case_id",
            "source_event_id",
            "anchor_id",
            "evidence_span",
            "holder",
            "valence",
            "intensity",
        ),
    )
    return {
        "$schema": DRAFT_2020_12,
        "$id": ("https://local.invalid/v02/c11/scene_affect_sidecar.v0.1.schema.json"),
        **_strict_object(
            title="C11.5 scene/affect independent sidecar",
            properties={
                "schema_version": {"const": "v02-scene-affect-sidecar.v0.1"},
                "candidate_status": {"const": CANDIDATE_STATUS},
                "paper_only": {"const": True},
                "fact_sentence_writeback_allowed": {"const": False},
                "metric_exclusions": {
                    "const": ["FACT_COVERAGE", "UCR", "SOP", "GATES"]
                },
                "scene_texture": {
                    "type": "array",
                    "items": scene_item,
                },
                "affect": {
                    "type": "array",
                    "items": affect_item,
                },
            },
            required=(
                "schema_version",
                "candidate_status",
                "paper_only",
                "fact_sentence_writeback_allowed",
                "metric_exclusions",
                "scene_texture",
                "affect",
            ),
        ),
    }


def _sidecar_shell() -> dict[str, Any]:
    return {
        "schema_version": "v02-scene-affect-sidecar.v0.1",
        "candidate_status": CANDIDATE_STATUS,
        "paper_only": True,
        "fact_sentence_writeback_allowed": False,
        "metric_exclusions": ["FACT_COVERAGE", "UCR", "SOP", "GATES"],
        "scene_texture": [],
        "affect": [],
    }


def build_sidecar_examples() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    place = {
        **_sidecar_shell(),
        "scene_texture": [
            {
                "case_id": "B02-U0039",
                "source_event_id": "EV-C0039-01",
                "anchor_id": "E0001",
                "evidence_span": "晚上",
                "kind": "time_or_light",
            },
            {
                "case_id": "B02-U0039",
                "source_event_id": "EV-C0039-03",
                "anchor_id": "E0046",
                "evidence_span": "在语音楼的1楼",
                "kind": "place",
            },
        ],
    }
    visual = {
        **_sidecar_shell(),
        "scene_texture": [
            {
                "case_id": "B03-U0041",
                "source_event_id": "EV-C0041-02",
                "anchor_id": "E0011",
                "evidence_span": "红纸之上",
                "kind": "camera_suggestion",
            },
            {
                "case_id": "B02-U0039",
                "source_event_id": "EV-C0039-04",
                "anchor_id": "E0050",
                "evidence_span": "一个个蒲团",
                "kind": "key_visual_object",
            },
        ],
    }
    affect = {
        **_sidecar_shell(),
        "affect": [
            {
                "case_id": "B01-U0033",
                "source_event_id": "EV-C0033-06",
                "anchor_id": "E0086",
                "evidence_span": "明兰愁眉苦脸",
                "holder": "明兰",
                "valence": "negative",
                "intensity": "medium",
            }
        ],
    }
    invalid_invented_span = {
        **_sidecar_shell(),
        "scene_texture": [
            {
                "case_id": "B02-U0039",
                "source_event_id": "EV-C0039-03",
                "anchor_id": "E0046",
                "evidence_span": "在语音楼的2楼",
                "kind": "place",
            }
        ],
    }
    invalid_missing_span = {
        **_sidecar_shell(),
        "scene_texture": [
            {
                "case_id": "B03-U0041",
                "source_event_id": "EV-C0041-02",
                "anchor_id": "E0011",
                "kind": "camera_suggestion",
            }
        ],
    }
    invalid_intensity = {
        **_sidecar_shell(),
        "affect": [
            {
                "case_id": "B01-U0033",
                "source_event_id": "EV-C0033-06",
                "anchor_id": "E0086",
                "evidence_span": "明兰愁眉苦脸",
                "holder": "明兰",
                "valence": "banana",
                "intensity": "medium",
            }
        ],
    }
    return (
        [place, visual, affect],
        [
            invalid_invented_span,
            invalid_missing_span,
            invalid_intensity,
        ],
    )


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def validate_c11_4_instance(name: str, instance: Any) -> None:
    schemas = build_c11_4_schemas()
    if name not in schemas:
        raise PaperDesignError(f"未知 C11.4 schema：{name}")
    errors = sorted(
        Draft202012Validator(schemas[name]).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise PaperDesignError(f"{name} JSON Schema 拒收：{errors[0].message}")
    keys = _walk_keys(instance)
    if "literalness" in keys or "fact_id" in keys:
        raise PaperDesignError(f"{name} 出现禁用字段")
    if name == "dual_order":
        if set(instance["story_order"]) != set(instance["discourse_order"]):
            raise PaperDesignError("story_order 与 discourse_order 成员漂移")
    if name == "plan_event_store":
        plan_event_ids = [row["plan_event_id"] for row in instance["plan_events"]]
        if len(plan_event_ids) != len(set(plan_event_ids)):
            raise PaperDesignError("plan_event_id 必须机械唯一")
        known_plan_event_ids = set(plan_event_ids)
        for row in instance["history"]:
            if row["fact_ref"] not in known_plan_event_ids:
                raise PaperDesignError("history.fact_ref 出现悬空引用")
    if name == "plan_prose_reconciliation":
        ratio = (
            instance["new_unplanned_scan_tokens"] / instance["full_reextract_tokens"]
        )
        expected = "NOT_SAVING" if ratio > 0.60 else "SAVING"
        if instance["saving_verdict"] != expected:
            raise PaperDesignError("60% 节省判据不成立")
    if name == "chapter_contract_bundle":
        if instance["chapter_plan_v2"]["missing_marker"] != MISSING_PLAN_FIELDS:
            raise PaperDesignError("chapter_plan_v2 缺失标记漂移")
        if instance["projection_card_v1"]["truth_writeback_allowed"]:
            raise PaperDesignError("projection_card_v1 越权回写真值")
    if name == "assertion_owner":
        if tuple(instance["candidate_values"]) != OWNER_VALUES:
            raise PaperDesignError("归属层五值枚举漂移")


def _load_source_index() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for case_id, paths in SOURCE_CASES.items():
        catalog_doc = read_json(paths["catalog"])
        candidate_doc = read_json(paths["candidate"])
        entries = {str(row["anchor_id"]): row for row in catalog_doc.get("entries", [])}
        events = {str(row["event_id"]): row for row in candidate_doc.get("events", [])}
        if not entries or not events:
            raise PaperDesignError(f"{case_id} 来源件为空")
        result[case_id] = {
            "catalog_sha256": sha256_file(paths["catalog"]),
            "candidate_sha256": sha256_file(paths["candidate"]),
            "entries": entries,
            "events": events,
        }
    return result


def validate_sidecar_instance(instance: Any) -> None:
    schema = build_sidecar_schema()
    errors = sorted(
        Draft202012Validator(schema).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise PaperDesignError(f"C11.5 JSON Schema 拒收：{errors[0].message}")
    sources = _load_source_index()
    for item in [*instance["scene_texture"], *instance["affect"]]:
        case_id = item["case_id"]
        source = sources.get(case_id)
        if source is None:
            raise PaperDesignError(f"C11.5 未登记来源：{case_id}")
        event = source["events"].get(item["source_event_id"])
        anchor = source["entries"].get(item["anchor_id"])
        if event is None or anchor is None:
            raise PaperDesignError("C11.5 事件或锚不存在")
        event_anchor_ids = set(event.get("minimal_anchor_ids", []))
        if item["anchor_id"] not in event_anchor_ids:
            raise PaperDesignError("C11.5 锚不属于来源事件")
        if item["evidence_span"] not in str(anchor.get("quote", "")):
            raise PaperDesignError("C11.5 evidence_span 无法逐字回贴冻结短引")


def build_question_relation_table() -> dict[str, Any]:
    catalog = read_json(C11_2_CATALOG)
    rows = []
    for row in catalog.get("rows", []):
        family = str(row["question_family"])
        is_storyboard = family == "PRODUCT_STORYBOARD_RECONSTRUCTION"
        rows.append(
            {
                "question_family": family,
                "relation_status": (
                    "POTENTIAL_READ_ONLY_INPUT"
                    if is_storyboard
                    else "NO_APPROVED_RELATION"
                ),
                "candidate_sidecar_surfaces": (
                    ["scene_texture", "affect"] if is_storyboard else []
                ),
                "human_required": True,
                "formal_question": False,
                "formal_answer": False,
                "scoreable": False,
            }
        )
    if len(rows) != 9 or len({row["question_family"] for row in rows}) != 9:
        raise PaperDesignError("C11.2 九个 question_family 身份漂移")
    return {
        "schema_version": "v02-c11.2-c11.5-relation.v1",
        "status": "PAPER_ONLY_HUMAN_REQUIRED",
        "source_catalog_sha256": sha256_file(C11_2_CATALOG),
        "rows": rows,
        "formal_question_count": 0,
        "formal_answer_count": 0,
        "formal_score_count": 0,
    }


def build_migration_impact() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_status": CANDIDATE_STATUS,
        "paper_only": True,
        "current_artifacts_preserved": [
            "chapter-fact-graph-outline-v1",
            "four-view candidate sample",
            "four-view audit sidecar",
            "historical scores",
        ],
        "write_mode": "ADD_ONLY_CANDIDATE",
        "active_migration_performed": False,
        "prompt_changed": False,
        "runner_changed": False,
        "default_chain_changed": False,
        "formal_gold_changed": False,
        "historical_scores_rewritten": False,
        "future_requirements": [
            "chapter_plan_v2 字段名须另拍",
            "归属层规范字段名须另拍",
            "C5 后逐件同供料前后对照",
            "结构版本间旧成绩不得混算",
            "接入运行器须另拍",
        ],
        "forbidden_additions_absent": [
            "literalness",
            "near_30_field_beat_example",
            "execution_packet_token_threshold",
            "X12_X15_fields",
        ],
    }


def _readme() -> bytes:
    text = """# C11.4／C11.5 结构纸面候选

这批文件只回答“以后合同应该怎么分层”，不接提示词、不接运行器，也不改现役链。

- C11.4 有五份独立 Schema，每份各带一个合法例和一个非法例。
- `chapter_plan_v2` 的字段名还没拍，所以不预造字段，只登记缺件并明确阻断启用。
- 归属层只登记五值候选，规范字段名仍保持缺失；没有加入 `literalness`。
- C11.5 是独立旁挂层，场景纹理和情绪线索不会写回事实句，也不会进入事实覆盖、UCR、SOP 或任何过闸结果。
- C11.5 三个合法例都从 C4 候选事件与冻结锚目录取短引，并由程序逐字回贴；三个反例分别验证编造短引、缺短引和非法强度会被拒收。
- 本目录没有 `experiment.json`，所以它是未登记的本地候选程序／证据包，不冒充现役实验路线。

来源：Codex
"""
    return text.encode("utf-8")


def build_artifacts() -> dict[str, bytes]:
    schemas = build_c11_4_schemas()
    valid_c11_4, invalid_c11_4 = build_c11_4_examples()
    for name, schema in schemas.items():
        Draft202012Validator.check_schema(schema)
        validate_c11_4_instance(name, valid_c11_4[name])
        try:
            validate_c11_4_instance(name, invalid_c11_4[name])
        except PaperDesignError:
            pass
        else:
            raise PaperDesignError(f"{name} 非法例未被拒收")

    sidecar_schema = build_sidecar_schema()
    Draft202012Validator.check_schema(sidecar_schema)
    valid_sidecars, invalid_sidecars = build_sidecar_examples()
    for instance in valid_sidecars:
        validate_sidecar_instance(instance)
    for index, instance in enumerate(invalid_sidecars, start=1):
        try:
            validate_sidecar_instance(instance)
        except PaperDesignError:
            pass
        else:
            raise PaperDesignError(f"C11.5 非法例 {index} 未被拒收")

    artifacts: dict[str, bytes] = {"README.md": _readme()}
    for relative in MANAGED_PROGRAM_FILES:
        artifacts[relative] = (TASK_ROOT / relative).read_bytes()
    schema_paths = {
        "dual_order": "C11_4/schemas/01_dual_order.v0.1.schema.json",
        "plan_event_store": ("C11_4/schemas/02_plan_event_store.v0.1.schema.json"),
        "plan_prose_reconciliation": (
            "C11_4/schemas/03_plan_prose_reconciliation.v0.1.schema.json"
        ),
        "chapter_contract_bundle": (
            "C11_4/schemas/04_chapter_contract_bundle.v0.1.schema.json"
        ),
        "assertion_owner": ("C11_4/schemas/05_assertion_owner.v0.1.schema.json"),
    }
    for name, path in schema_paths.items():
        artifacts[path] = canonical_json_bytes(schemas[name])
        artifacts[f"C11_4/examples/valid/{name}.json"] = canonical_json_bytes(
            valid_c11_4[name]
        )
        artifacts[f"C11_4/examples/invalid/{name}.json"] = canonical_json_bytes(
            invalid_c11_4[name]
        )
    artifacts["C11_4/migration_impact.json"] = canonical_json_bytes(
        build_migration_impact()
    )
    artifacts["C11_5/schemas/scene_affect_sidecar.v0.1.schema.json"] = (
        canonical_json_bytes(sidecar_schema)
    )
    for index, instance in enumerate(valid_sidecars, start=1):
        artifacts[f"C11_5/examples/valid/{index:02d}.json"] = canonical_json_bytes(
            instance
        )
    for index, instance in enumerate(invalid_sidecars, start=1):
        artifacts[f"C11_5/examples/invalid/{index:02d}.json"] = canonical_json_bytes(
            instance
        )
    artifacts["C11_5/c11_2_question_relation.json"] = canonical_json_bytes(
        build_question_relation_table()
    )

    sources = _load_source_index()
    source_receipt = {
        "schema_version": SCHEMA_VERSION,
        "program_sha256": sha256_file(Path(__file__).resolve()),
        "c11_2_question_catalog_sha256": sha256_file(C11_2_CATALOG),
        "c4_sources": {
            case_id: {
                "catalog_sha256": source["catalog_sha256"],
                "candidate_sha256": source["candidate_sha256"],
            }
            for case_id, source in sorted(sources.items())
        },
        "formal_gold_read": False,
        "model_api_calls": 0,
        "network_requests": 0,
        "source_text_not_bulk_emitted": True,
    }
    artifacts["source_receipt.json"] = canonical_json_bytes(source_receipt)

    acceptance = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS_PAPER_ONLY_CANDIDATE",
        "candidate_status": CANDIDATE_STATUS,
        "c11_4_schema_count": 5,
        "c11_4_valid_example_count": 5,
        "c11_4_invalid_example_count": 5,
        "c11_5_schema_count": 1,
        "c11_5_valid_example_count": 3,
        "c11_5_invalid_example_count": 3,
        "total_example_count": 16,
        "question_family_count": 9,
        "chapter_plan_fields_blocked": True,
        "assertion_owner_field_name_blocked": True,
        "sidecar_writeback_allowed": False,
        "sidecar_enters_metrics_or_gates": False,
        "prompt_changed": False,
        "runner_changed": False,
        "default_chain_changed": False,
        "formal_gold_read": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts["acceptance_receipt.json"] = canonical_json_bytes(acceptance)

    manifest_rows = [
        {
            "path": path,
            "sha256": sha256_bytes(raw),
            "byte_count": len(raw),
        }
        for path, raw in sorted(artifacts.items())
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "candidate_status": CANDIDATE_STATUS,
        "paper_only": True,
        "files": manifest_rows,
        "file_count": len(manifest_rows),
        "artifact_set_sha256": sha256_bytes(canonical_json_bytes(manifest_rows)),
        "unregistered_extra_files_policy": "REJECT",
    }
    artifacts["artifact_manifest.json"] = canonical_json_bytes(manifest)
    return artifacts


def write_artifacts(
    output_dir: Path,
    artifacts: Mapping[str, bytes],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = set(artifacts)
    existing = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    extras = existing - expected
    if extras:
        raise PaperDesignError(f"输出目录含清单外文件：{sorted(extras)}")
    for relative, raw in artifacts.items():
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def verify_artifacts(output_dir: Path) -> dict[str, Any]:
    expected = build_artifacts()
    actual_paths = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if actual_paths != set(expected):
        raise PaperDesignError("实际文件集合与确定性构建集合不一致")
    for relative, raw in expected.items():
        if (output_dir / relative).read_bytes() != raw:
            raise PaperDesignError(f"工件字节漂移：{relative}")
    return json.loads(expected["artifact_manifest.json"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("build", "verify"),
        nargs="?",
        default="build",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    args = parser.parse_args(argv)
    if args.command == "build":
        artifacts = build_artifacts()
        write_artifacts(args.output_dir, artifacts)
        verify_artifacts(args.output_dir)
    else:
        verify_artifacts(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SELF_PATH = Path(__file__).resolve()
OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C12_6_program_generated_state_machine_benchmark_20260725"
)
REPORT_PATH = (
    ROOT
    / "reports/抽取工序重设计v0.2_C12积压优化项_20260725"
    / "C12_6_停点回包.md"
)
TEST_PATH = ROOT / "tests/test_v02_c12_6_state_machine_benchmark.py"

SCHEMA_VERSION = "v02-c12.6-program-generated-state-machine.v1"
GENERATOR_VERSION = "v02-c12.6-generator.v1"
ROOT_SEED = "CZ-C12.6-STATE-MACHINE-PILOT-20260725"
CHAPTER_TOTAL = 30
FACT_TOTAL = 80
BENCHMARK_ID = "C12.6-SMALL-STATE-MACHINE-30X80"
ROOT_SEED_FROZEN_DIGESTS = {
    "ledger": "1b6c918db996c1cf61f393b33f5a9de503c7fda709c9b6399dfa436e082be4e5",
    "corpus": "f1d7b5e72b969be2d515a5a1eebbbc383de30d77c9716c7758d11fcd77a15ff3",
    "oracle": "3de80075701bf6a94456d41fb8e850cc976c2c21376a4f60be7d793cff5edbd3",
    "snapshots_wrapper": (
        "e410f250183dd34ada15082b79d9dd26cf80c344eb7cc71f03df6a36e7e97400"
    ),
    "readable_story": (
        "1789dd4e81476243176cddc2175b48faea3140d4f5218f620b6316c2fbd6a943"
    ),
}
LIMITATION_TEXT = (
    "模板文本比真实网文规整得多，会系统性高估能力；本件只能当工程底座，"
    "不得替代真实章节，也不得进入任何质量胜负读数。"
)

SCOPE = {
    "world_id": "W01",
    "timeline_id": "T01",
    "branch_id": "B01",
    "policy_scope_id": "P01",
}

ENTITIES = {
    "E01": {"display_name": "林澈", "qualifier": ""},
    "E02": {"display_name": "沈舟", "qualifier": ""},
    "E03": {"display_name": "许岚", "qualifier": ""},
    "E04": {"display_name": "顾遥", "qualifier": ""},
    "E05": {"display_name": "苏禾", "qualifier": "东院的"},
    "E06": {"display_name": "苏禾", "qualifier": "西院的"},
}
LOCATIONS = {
    "L01": "旧车站",
    "L02": "河岸仓库",
    "L03": "北塔",
    "L04": "诊所",
}
OBJECTS = {
    "O01": "铜钥匙",
    "O02": "黑皮手册",
    "O03": "红色印章",
}
PHYSICAL_LABELS = {
    "healthy": "健康",
    "injured": "受伤",
    "recovering": "恢复中",
}
EVENT_TYPES = (
    "MOVE",
    "TRANSFER_ITEM",
    "BODY_STATE_SET",
    "GOAL_OPEN",
    "GOAL_REPLACE",
    "GOAL_COMPLETE",
    "OBSERVE",
    "INFORM",
    "RUMOR",
    "NEGATION",
    "PLAN",
    "CONDITION",
    "LIE",
    "CORRECTION",
    "FLASHBACK",
    "ALIAS",
)
NON_WORLD_ACTUALITIES = {
    "NEGATED",
    "PLANNED",
    "CONDITIONAL",
    "REPORTED_FALSE",
    "FLASHBACK",
}
ACTUALITIES = {
    "OCCURRED",
    "REPORTED",
    "NEGATED",
    "PLANNED",
    "CONDITIONAL",
    "REPORTED_FALSE",
    "FLASHBACK",
}
PROPOSITION_TRUTHS = {
    "TRUE",
    "FALSE",
    "UNKNOWN",
    "NOT_APPLICABLE",
}
FACT_KINDS = {
    "world_state",
    "epistemic",
    "speech_act",
    "intent",
    "condition",
    "correction",
    "historical_world_state",
    "identity",
}
MUTATION_OPERATIONS = {
    "SET",
    "TRANSFER",
    "OPEN",
    "REPLACE",
    "COMPLETE",
    "OBSERVE",
    "INFORM",
    "HEAR_RUMOR",
    "LIE_TO",
    "RETRACT",
    "CORRECT",
    "ADD_ALIAS",
}
EVENT_MUTATION_OPERATION_CONTRACTS = {
    "MOVE": ["SET"],
    "TRANSFER_ITEM": ["TRANSFER"],
    "BODY_STATE_SET": ["SET"],
    "GOAL_OPEN": ["OPEN"],
    "GOAL_REPLACE": ["REPLACE"],
    "GOAL_COMPLETE": ["COMPLETE"],
    "OBSERVE": ["OBSERVE"],
    "INFORM": ["INFORM"],
    "RUMOR": ["HEAR_RUMOR"],
    "NEGATION": [],
    "PLAN": [],
    "CONDITION": [],
    "LIE": ["LIE_TO"],
    "CORRECTION": ["RETRACT", "CORRECT"],
    "FLASHBACK": [],
    "ALIAS": ["ADD_ALIAS"],
}
PUBLIC_PACKET_PATH = "public/model_visible_packet_v1.json"
SEALED_ARTIFACT_PATHS = (
    "sealed/generator_contract_v1.json",
    "sealed/oracle_schema_v1.json",
    "sealed/canonical_transition_ledger_v1.json",
    "sealed/synthetic_corpus_v1.json",
    "sealed/synthetic_story_v1.txt",
    "sealed/oracle_manifest_v1.json",
    "sealed/chapter_end_snapshots_v1.json",
)
LEGACY_FLAT_ARTIFACTS = {
    "generator_contract_v1.json",
    "oracle_schema_v1.json",
    "canonical_transition_ledger_v1.json",
    "synthetic_corpus_v1.json",
    "synthetic_story_v1.txt",
    "oracle_manifest_v1.json",
    "chapter_end_snapshots_v1.json",
    "oracle_closure_receipt.json",
    "implementation_binding_receipt.json",
    "double_run_receipt.json",
    "C12_6_stop_receipt.md",
    "artifact_manifest.json",
}
TRUTH_ID_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"F\d{3}|E\d{2}|O\d{2}|L\d{2}|"
    r"P\d{2}[A-Z0-9-]*|G\d{2}[A-Z]?|TPL-[A-Z0-9_-]+"
    r")(?![A-Za-z0-9])"
)
EVENT_COMBINATION_CONTRACTS = {
    "MOVE": {
        "fact_kind": "world_state",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "flags": (True, False, False),
        "predicate": "move_to",
        "frame_keys": {"subject", "predicate", "object", "polarity"},
    },
    "TRANSFER_ITEM": {
        "fact_kind": "world_state",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "flags": (True, False, False),
        "predicate": "transfer_ownership",
        "frame_keys": {"subject", "predicate", "object", "recipient"},
    },
    "BODY_STATE_SET": {
        "fact_kind": "world_state",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "flags": (True, False, False),
        "predicate": "physical_state_change",
        "frame_keys": {"subject", "predicate", "before", "after"},
    },
    "GOAL_OPEN": {
        "fact_kind": "world_state",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "flags": (True, False, False),
        "predicate": "open_goal",
        "frame_keys": {"subject", "predicate", "object"},
    },
    "GOAL_REPLACE": {
        "fact_kind": "world_state",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "flags": (True, False, False),
        "predicate": "replace_goal",
        "frame_keys": {"subject", "predicate", "before", "after"},
    },
    "GOAL_COMPLETE": {
        "fact_kind": "world_state",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "flags": (True, False, False),
        "predicate": "complete_goal",
        "frame_keys": {"subject", "predicate", "object"},
    },
    "OBSERVE": {
        "fact_kind": "epistemic",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "flags": (False, True, False),
        "predicate": "observe",
        "frame_keys": {"subject", "predicate", "object", "truth"},
    },
    "INFORM": {
        "fact_kind": "speech_act",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "flags": (False, True, False),
        "predicate": "inform",
        "frame_keys": {
            "speaker",
            "recipient",
            "predicate",
            "object",
            "owner",
            "truth",
        },
    },
    "RUMOR": {
        "fact_kind": "speech_act",
        "actuality": "REPORTED",
        "proposition_truth": "UNKNOWN",
        "flags": (False, True, False),
        "predicate": "spread_rumor",
        "frame_keys": {
            "speaker",
            "recipient",
            "predicate",
            "object",
            "truth",
        },
    },
    "NEGATION": {
        "fact_kind": "world_state",
        "actuality": "NEGATED",
        "proposition_truth": "FALSE",
        "flags": (False, False, False),
        "predicate": "move_to",
        "frame_keys": {"subject", "predicate", "object", "polarity"},
    },
    "PLAN": {
        "fact_kind": "intent",
        "actuality": "PLANNED",
        "proposition_truth": "NOT_APPLICABLE",
        "flags": (False, False, False),
        "predicate": "plan_move",
        "frame_keys": {"subject", "predicate", "object", "realis"},
    },
    "CONDITION": {
        "fact_kind": "condition",
        "actuality": "CONDITIONAL",
        "proposition_truth": "NOT_APPLICABLE",
        "flags": (False, False, False),
        "predicate": "conditional_move",
        "frame_keys": {
            "subject",
            "predicate",
            "condition",
            "object",
        },
    },
    "LIE": {
        "fact_kind": "speech_act",
        "actuality": "REPORTED_FALSE",
        "proposition_truth": "FALSE",
        "flags": (False, True, False),
        "predicate": "lie_about_owner",
        "frame_keys": {
            "speaker",
            "recipient",
            "predicate",
            "object",
            "claimed_owner",
            "truth",
        },
    },
    "CORRECTION": {
        "fact_kind": "correction",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "flags": (False, True, False),
        "predicate": "correct_owner_claim",
        "frame_keys": {
            "speaker",
            "recipient",
            "predicate",
            "object",
            "owner",
            "truth",
        },
    },
    "FLASHBACK": {
        "fact_kind": "historical_world_state",
        "actuality": "FLASHBACK",
        "proposition_truth": "TRUE",
        "flags": (False, False, False),
        "predicate": "historical_injury",
        "frame_keys": {
            "subject",
            "predicate",
            "object",
            "physical_state",
        },
    },
    "ALIAS": {
        "fact_kind": "identity",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "flags": (False, False, True),
        "predicate": "establish_alias",
        "frame_keys": {"subject", "predicate", "object"},
    },
}


class BenchmarkError(RuntimeError):
    pass


class _SchemaExecutionError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _stable_rank(seed: str, domain: str, value: str) -> str:
    return sha256_bytes(f"{seed}|{domain}|{value}".encode())


def _stable_choice(seed: str, domain: str, values: list[str]) -> str:
    if not values:
        raise BenchmarkError("稳定选择器收到空候选")
    ordered = sorted(values)
    digest = _stable_rank(seed, domain, "|".join(ordered))
    return ordered[int(digest[:16], 16) % len(ordered)]


def _entity_label(entity_id: str) -> str:
    row = ENTITIES[entity_id]
    return f"{row['qualifier']}{row['display_name']}"


def _entity_registry() -> dict[str, dict[str, str]]:
    return {
        entity_id: {
            **row,
            "identity_binding_sha256": sha256_bytes(
                canonical_bytes(
                    {
                        "benchmark": "C12.6-SMALL-STATE-MACHINE-30X80",
                        "entity_id": entity_id,
                        "display_name": row["display_name"],
                        "qualifier": row["qualifier"],
                    }
                )
            ),
        }
        for entity_id, row in sorted(ENTITIES.items())
    }


def _initial_state() -> dict[str, Any]:
    entity_ids = sorted(ENTITIES)
    object_ids = sorted(OBJECTS)
    location_ids = sorted(LOCATIONS)
    return {
        "world": {
            "entity_location": {
                entity_id: location_ids[index % len(location_ids)]
                for index, entity_id in enumerate(entity_ids)
            },
            "entity_physical": {
                entity_id: "healthy" for entity_id in entity_ids
            },
            "active_goal": {entity_id: None for entity_id in entity_ids},
            "object_owner": {
                object_id: entity_ids[index % 4]
                for index, object_id in enumerate(object_ids)
            },
        },
        "epistemic": {"beliefs": {entity_id: {} for entity_id in entity_ids}},
        "identity": {"aliases": {entity_id: [] for entity_id in entity_ids}},
    }


def _get_path(document: dict[str, Any], path: list[str]) -> Any:
    current: Any = document
    for index, part in enumerate(path):
        if (
            isinstance(current, dict)
            and part not in current
            and index == len(path) - 1
        ):
            return None
        current = current[part]
    return copy.deepcopy(current)


def _set_path(document: dict[str, Any], path: list[str], value: Any) -> None:
    current: Any = document
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = copy.deepcopy(value)


def _mutation(
    *,
    state: dict[str, Any],
    predecessor_by_path: dict[str, str],
    fact_id: str,
    path: list[str],
    after: Any,
    operation: str,
) -> dict[str, Any]:
    path_key = "/".join(path)
    before = _get_path(state, path)
    row = {
        "path": path,
        "operation": operation,
        "before": before,
        "after": copy.deepcopy(after),
        "predecessor_fact_id": predecessor_by_path.get(path_key),
    }
    _set_path(state, path, after)
    predecessor_by_path[path_key] = fact_id
    return row


def _base_fact(
    *,
    fact_index: int,
    chapter_number: int,
    event_type: str,
    cycle: int,
) -> dict[str, Any]:
    return {
        "fact_id": f"F{fact_index:03d}",
        "chapter_id": f"C{chapter_number:02d}",
        "recorded_at_chapter": chapter_number,
        "narrative_index": fact_index,
        "event_type": event_type,
        "phenomenon_codes": [event_type],
        "fact_kind": "world_state",
        "actuality": "OCCURRED",
        "proposition_truth": "TRUE",
        "updates_world_state": False,
        "updates_epistemic_state": False,
        "updates_identity_state": False,
        "scope": copy.deepcopy(SCOPE),
        "story_time": [1, 0, fact_index, 0],
        "subject_entity_ids": [],
        "object_refs": [],
        "semantic_frame": {},
        "mutations": [],
        "supersedes_fact_id": None,
        "invalidates_fact_id": None,
        "render_template_id": f"TPL-{event_type}-V1",
        "render_payload": {"cycle": cycle},
        "sentence": "",
    }


def _build_fact(
    *,
    seed: str,
    fact_index: int,
    chapter_number: int,
    event_type: str,
    cycle: int,
    state: dict[str, Any],
    predecessor_by_path: dict[str, str],
    cycle_memory: dict[int, dict[str, str]],
) -> dict[str, Any]:
    row = _base_fact(
        fact_index=fact_index,
        chapter_number=chapter_number,
        event_type=event_type,
        cycle=cycle,
    )
    fact_id = row["fact_id"]
    core_entities = ["E01", "E02", "E03", "E04"]
    subject = core_entities[cycle % len(core_entities)]
    partner = core_entities[(cycle + 1) % len(core_entities)]
    witness = core_entities[(cycle + 2) % len(core_entities)]
    location_id = sorted(LOCATIONS)[(cycle + 1) % len(LOCATIONS)]
    object_id = sorted(OBJECTS)[cycle % len(OBJECTS)]
    memory = cycle_memory.setdefault(cycle, {})

    if event_type == "MOVE":
        path = ["world", "entity_location", subject]
        before_id = _get_path(state, path)
        target_id = location_id if location_id != before_id else "L04"
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after=target_id,
                operation="SET",
            )
        )
        row["updates_world_state"] = True
        row["subject_entity_ids"] = [subject]
        row["object_refs"] = [target_id]
        row["semantic_frame"] = {
            "subject": subject,
            "predicate": "move_to",
            "object": target_id,
            "polarity": "positive",
        }
        row["sentence"] = (
            f"{_entity_label(subject)}从{LOCATIONS[before_id]}来到"
            f"{LOCATIONS[target_id]}。"
        )

    elif event_type == "TRANSFER_ITEM":
        path = ["world", "object_owner", object_id]
        old_owner = _get_path(state, path)
        receiver = partner if partner != old_owner else witness
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after=receiver,
                operation="TRANSFER",
            )
        )
        row["updates_world_state"] = True
        row["subject_entity_ids"] = [old_owner, receiver]
        row["object_refs"] = [object_id]
        row["semantic_frame"] = {
            "subject": old_owner,
            "predicate": "transfer_ownership",
            "object": object_id,
            "recipient": receiver,
        }
        row["sentence"] = (
            f"{_entity_label(old_owner)}把{OBJECTS[object_id]}交给"
            f"{_entity_label(receiver)}，此后由后者保管。"
        )

    elif event_type == "BODY_STATE_SET":
        path = ["world", "entity_physical", subject]
        before = _get_path(state, path)
        candidates = [state_id for state_id in PHYSICAL_LABELS if state_id != before]
        after = _stable_choice(seed, f"body-{cycle}", candidates)
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after=after,
                operation="SET",
            )
        )
        row["updates_world_state"] = True
        row["subject_entity_ids"] = [subject]
        row["semantic_frame"] = {
            "subject": subject,
            "predicate": "physical_state_change",
            "before": before,
            "after": after,
        }
        row["sentence"] = (
            f"{_entity_label(subject)}的身体状态从"
            f"{PHYSICAL_LABELS[before]}变为{PHYSICAL_LABELS[after]}。"
        )

    elif event_type == "GOAL_OPEN":
        path = ["world", "active_goal", subject]
        goal_id = f"G{cycle:02d}A"
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after=goal_id,
                operation="OPEN",
            )
        )
        memory["goal_a"] = goal_id
        row["updates_world_state"] = True
        row["subject_entity_ids"] = [subject]
        row["object_refs"] = [goal_id]
        row["semantic_frame"] = {
            "subject": subject,
            "predicate": "open_goal",
            "object": goal_id,
        }
        row["sentence"] = (
            f"{_entity_label(subject)}把查清第{cycle + 1}份失踪记录"
            "定为当前目标。"
        )

    elif event_type == "GOAL_REPLACE":
        path = ["world", "active_goal", subject]
        old_goal = _get_path(state, path)
        goal_id = f"G{cycle:02d}B"
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after=goal_id,
                operation="REPLACE",
            )
        )
        memory["goal_b"] = goal_id
        row["updates_world_state"] = True
        row["subject_entity_ids"] = [subject]
        row["object_refs"] = [old_goal, goal_id]
        row["semantic_frame"] = {
            "subject": subject,
            "predicate": "replace_goal",
            "before": old_goal,
            "after": goal_id,
        }
        row["sentence"] = (
            f"{_entity_label(subject)}放下查记录的原目标，"
            f"改为先找到第{cycle + 1}名失踪者。"
        )

    elif event_type == "GOAL_COMPLETE":
        path = ["world", "active_goal", subject]
        completed_goal = _get_path(state, path)
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after=None,
                operation="COMPLETE",
            )
        )
        row["updates_world_state"] = True
        row["subject_entity_ids"] = [subject]
        row["object_refs"] = [completed_goal]
        row["semantic_frame"] = {
            "subject": subject,
            "predicate": "complete_goal",
            "object": completed_goal,
        }
        row["sentence"] = (
            f"{_entity_label(subject)}找到那名失踪者，"
            "当前目标随之完成。"
        )

    elif event_type == "OBSERVE":
        proposition_id = f"P{cycle:02d}-SIGNAL"
        path = ["epistemic", "beliefs", witness, proposition_id]
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after="KNOWN_TRUE",
                operation="OBSERVE",
            )
        )
        row["fact_kind"] = "epistemic"
        row["updates_epistemic_state"] = True
        row["subject_entity_ids"] = [witness]
        row["object_refs"] = [proposition_id]
        row["semantic_frame"] = {
            "subject": witness,
            "predicate": "observe",
            "object": proposition_id,
            "truth": "TRUE",
        }
        row["sentence"] = (
            f"{_entity_label(witness)}亲眼看见{LOCATIONS[location_id]}"
            f"的第{cycle + 1}盏信号灯亮起。"
        )

    elif event_type == "INFORM":
        proposition_id = f"P{cycle:02d}-OWNER-TRUE"
        owner_id = _get_path(state, ["world", "object_owner", object_id])
        path = ["epistemic", "beliefs", partner, proposition_id]
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after="TOLD_TRUE",
                operation="INFORM",
            )
        )
        row["fact_kind"] = "speech_act"
        row["updates_epistemic_state"] = True
        row["subject_entity_ids"] = [subject, partner]
        row["object_refs"] = [proposition_id]
        row["semantic_frame"] = {
            "speaker": subject,
            "recipient": partner,
            "predicate": "inform",
            "object": object_id,
            "owner": owner_id,
            "truth": "TRUE",
        }
        row["sentence"] = (
            f"{_entity_label(subject)}告诉{_entity_label(partner)}，"
            f"{OBJECTS[object_id]}现在由{_entity_label(owner_id)}保管。"
        )

    elif event_type == "RUMOR":
        proposition_id = f"P{cycle:02d}-RUMOR"
        path = ["epistemic", "beliefs", partner, proposition_id]
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after="BELIEVED_UNVERIFIED",
                operation="HEAR_RUMOR",
            )
        )
        row["fact_kind"] = "speech_act"
        row["actuality"] = "REPORTED"
        row["proposition_truth"] = "UNKNOWN"
        row["updates_epistemic_state"] = True
        row["subject_entity_ids"] = [subject, partner]
        row["object_refs"] = [proposition_id]
        row["semantic_frame"] = {
            "speaker": subject,
            "recipient": partner,
            "predicate": "spread_rumor",
            "object": proposition_id,
            "truth": "UNKNOWN",
        }
        row["sentence"] = (
            f"{_entity_label(subject)}把“{LOCATIONS[location_id]}今晚会封锁”"
            f"的传闻告诉{_entity_label(partner)}，对方虽未见证据仍信以为真。"
        )

    elif event_type == "NEGATION":
        row["fact_kind"] = "world_state"
        row["actuality"] = "NEGATED"
        row["proposition_truth"] = "FALSE"
        row["subject_entity_ids"] = [subject]
        row["object_refs"] = [location_id]
        row["semantic_frame"] = {
            "subject": subject,
            "predicate": "move_to",
            "object": location_id,
            "polarity": "negative",
        }
        row["sentence"] = (
            f"{_entity_label(subject)}没有前往{LOCATIONS[location_id]}。"
        )

    elif event_type == "PLAN":
        row["fact_kind"] = "intent"
        row["actuality"] = "PLANNED"
        row["proposition_truth"] = "NOT_APPLICABLE"
        row["subject_entity_ids"] = [subject]
        row["object_refs"] = [location_id]
        row["semantic_frame"] = {
            "subject": subject,
            "predicate": "plan_move",
            "object": location_id,
            "realis": "planned",
        }
        row["sentence"] = (
            f"{_entity_label(subject)}计划明日去{LOCATIONS[location_id]}，"
            "但此刻尚未动身。"
        )

    elif event_type == "CONDITION":
        row["fact_kind"] = "condition"
        row["actuality"] = "CONDITIONAL"
        row["proposition_truth"] = "NOT_APPLICABLE"
        row["subject_entity_ids"] = [subject]
        row["object_refs"] = [object_id, location_id]
        row["semantic_frame"] = {
            "subject": subject,
            "predicate": "conditional_move",
            "condition": object_id,
            "object": location_id,
        }
        row["sentence"] = (
            f"{_entity_label(subject)}约定，只有拿到{OBJECTS[object_id]}，"
            f"才会进入{LOCATIONS[location_id]}。"
        )

    elif event_type == "LIE":
        proposition_id = f"P{cycle:02d}-LIE"
        actual_owner = _get_path(state, ["world", "object_owner", object_id])
        wrong_owner = witness if witness != actual_owner else subject
        path = ["epistemic", "beliefs", partner, proposition_id]
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after="BELIEVED_FALSE",
                operation="LIE_TO",
            )
        )
        memory["lie_fact_id"] = fact_id
        memory["lie_proposition_id"] = proposition_id
        memory["lie_recipient"] = partner
        memory["actual_owner"] = actual_owner
        row["fact_kind"] = "speech_act"
        row["actuality"] = "REPORTED_FALSE"
        row["proposition_truth"] = "FALSE"
        row["updates_epistemic_state"] = True
        row["subject_entity_ids"] = [subject, partner, wrong_owner]
        row["object_refs"] = [object_id, proposition_id]
        row["semantic_frame"] = {
            "speaker": subject,
            "recipient": partner,
            "predicate": "lie_about_owner",
            "object": object_id,
            "claimed_owner": wrong_owner,
            "truth": "FALSE",
        }
        row["sentence"] = (
            f"{_entity_label(subject)}故意对{_entity_label(partner)}谎称，"
            f"{OBJECTS[object_id]}归{_entity_label(wrong_owner)}所有；"
            "对方信了这个说法。"
        )

    elif event_type == "CORRECTION":
        proposition_id = memory["lie_proposition_id"]
        recipient = memory["lie_recipient"]
        actual_owner = memory["actual_owner"]
        true_proposition_id = f"P{cycle:02d}-OWNER-CORRECTED"
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=["epistemic", "beliefs", recipient, proposition_id],
                after="RETRACTED_FALSE",
                operation="RETRACT",
            )
        )
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=[
                    "epistemic",
                    "beliefs",
                    recipient,
                    true_proposition_id,
                ],
                after="KNOWN_TRUE",
                operation="CORRECT",
            )
        )
        row["fact_kind"] = "correction"
        row["updates_epistemic_state"] = True
        row["subject_entity_ids"] = list(
            dict.fromkeys([subject, recipient, actual_owner])
        )
        row["object_refs"] = [object_id, proposition_id, true_proposition_id]
        row["invalidates_fact_id"] = memory["lie_fact_id"]
        row["semantic_frame"] = {
            "speaker": subject,
            "recipient": recipient,
            "predicate": "correct_owner_claim",
            "object": object_id,
            "owner": actual_owner,
            "truth": "TRUE",
        }
        row["sentence"] = (
            f"{_entity_label(subject)}随后向{_entity_label(recipient)}更正："
            f"{OBJECTS[object_id]}实际由{_entity_label(actual_owner)}保管，"
            "先前说法作废；对方接受更正，撤回旧信念并记住真相。"
        )

    elif event_type == "FLASHBACK":
        row["fact_kind"] = "historical_world_state"
        row["actuality"] = "FLASHBACK"
        row["proposition_truth"] = "TRUE"
        row["scope"]["policy_scope_id"] = "P-FLASHBACK"
        row["story_time"] = [0, 0, cycle + 1, 0]
        row["subject_entity_ids"] = [subject]
        old_location = sorted(LOCATIONS)[cycle % len(LOCATIONS)]
        row["object_refs"] = [old_location, "injured"]
        row["semantic_frame"] = {
            "subject": subject,
            "predicate": "historical_injury",
            "object": old_location,
            "physical_state": "injured",
        }
        row["sentence"] = (
            f"{_entity_label(subject)}回忆起三日前曾在"
            f"{LOCATIONS[old_location]}受伤。"
        )

    elif event_type == "ALIAS":
        alias_entities = ["E05", "E06", "E01", "E02", "E03"]
        alias_entity = alias_entities[cycle % len(alias_entities)]
        alias = ["青禾", "白禾", "青砚", "渡鸦", "岚影"][cycle]
        path = ["identity", "aliases", alias_entity]
        aliases = _get_path(state, path)
        after = [*aliases, alias]
        row["mutations"].append(
            _mutation(
                state=state,
                predecessor_by_path=predecessor_by_path,
                fact_id=fact_id,
                path=path,
                after=after,
                operation="ADD_ALIAS",
            )
        )
        row["fact_kind"] = "identity"
        row["updates_identity_state"] = True
        row["subject_entity_ids"] = [alias_entity]
        row["object_refs"] = [alias]
        row["semantic_frame"] = {
            "subject": alias_entity,
            "predicate": "establish_alias",
            "object": alias,
        }
        row["sentence"] = (
            f"从今天起，{_entity_label(alias_entity)}在外行动时使用化名"
            f"“{alias}”。"
        )

    else:
        raise BenchmarkError(f"未知事件类型：{event_type}")

    row["render_payload"].update(
        {
            "subject_entity_ids": row["subject_entity_ids"],
            "object_refs": row["object_refs"],
        }
    )
    return row


def _chapter_fact_counts(seed: str) -> dict[int, int]:
    ranked = sorted(
        range(1, CHAPTER_TOTAL + 1),
        key=lambda chapter: _stable_rank(seed, "chapter-density", str(chapter)),
    )
    three_fact_chapters = set(ranked[:20])
    counts = {
        chapter: 3 if chapter in three_fact_chapters else 2
        for chapter in range(1, CHAPTER_TOTAL + 1)
    }
    if sum(counts.values()) != FACT_TOTAL:
        raise BenchmarkError("章节事实数未闭合为 80")
    return counts


def _build_canonical_ledger(seed: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = _initial_state()
    predecessor_by_path: dict[str, str] = {}
    cycle_memory: dict[int, dict[str, str]] = {}
    counts = _chapter_fact_counts(seed)
    facts: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    fact_index = 1

    for chapter_number in range(1, CHAPTER_TOTAL + 1):
        for _local_index in range(counts[chapter_number]):
            zero_based = fact_index - 1
            event_type = EVENT_TYPES[zero_based % len(EVENT_TYPES)]
            cycle = zero_based // len(EVENT_TYPES)
            facts.append(
                _build_fact(
                    seed=seed,
                    fact_index=fact_index,
                    chapter_number=chapter_number,
                    event_type=event_type,
                    cycle=cycle,
                    state=state,
                    predecessor_by_path=predecessor_by_path,
                    cycle_memory=cycle_memory,
                )
            )
            fact_index += 1
        snapshots.append(
            {
                "chapter_id": f"C{chapter_number:02d}",
                "chapter_number": chapter_number,
                "after_fact_id": facts[-1]["fact_id"],
                "state": copy.deepcopy(state),
            }
        )

    ledger = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "root_seed": seed,
        "initial_state": _initial_state(),
        "facts": facts,
        "chapter_fact_counts": counts,
        "limitations": {
            "pilot_foundation_only": True,
            "meets_full_x06_acceptance": False,
            "templated_text_systematically_overestimates": True,
            "substitute_for_real_chapters": False,
            "same_name_world_or_epistemic_exercise_included": False,
            "quality_result_registered": False,
            "statement": LIMITATION_TEXT,
        },
    }
    return ledger, snapshots


def _render_corpus(
    ledger: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
    by_chapter: dict[str, list[dict[str, Any]]] = {}
    for fact in ledger["facts"]:
        by_chapter.setdefault(fact["chapter_id"], []).append(fact)

    chapters: list[dict[str, Any]] = []
    evidence_by_fact: dict[str, dict[str, Any]] = {}
    readable_parts: list[str] = []
    global_offset = 0
    for chapter_number in range(1, CHAPTER_TOTAL + 1):
        chapter_id = f"C{chapter_number:02d}"
        facts = by_chapter[chapter_id]
        lines: list[str] = []
        local_offset = 0
        for local_index, fact in enumerate(facts, 1):
            sentence = fact["sentence"]
            start = local_offset
            end = start + len(sentence)
            lines.append(sentence)
            evidence_by_fact[fact["fact_id"]] = {
                "chapter_id": chapter_id,
                "source_block_id": f"{chapter_id}-L{local_index:02d}",
                "start_char": start,
                "end_char_exclusive": end,
                "claim_span": sentence,
                "span_sha256": sha256_bytes(sentence.encode("utf-8")),
            }
            local_offset = end + 1
        chapter_text = "\n".join(lines)
        chapter_sha = sha256_bytes(chapter_text.encode("utf-8"))
        for fact in facts:
            evidence_by_fact[fact["fact_id"]][
                "chapter_text_sha256"
            ] = chapter_sha
        title = f"第{chapter_number:02d}章"
        rendered = f"{title}\n{chapter_text}\n"
        chapters.append(
            {
                "chapter_id": chapter_id,
                "chapter_number": chapter_number,
                "title": title,
                "text": chapter_text,
                "text_sha256": chapter_sha,
                "fact_ids": [fact["fact_id"] for fact in facts],
                "global_start_char": global_offset,
                "global_end_char_exclusive": global_offset + len(rendered),
            }
        )
        readable_parts.append(rendered)
        global_offset += len(rendered) + 1

    readable_story = "\n".join(readable_parts)
    corpus = {
        "schema_version": "v02-c12.6-synthetic-corpus.v1",
        "benchmark_id": BENCHMARK_ID,
        "root_seed_sha256": sha256_bytes(ledger["root_seed"].encode("utf-8")),
        "chapter_total": len(chapters),
        "fact_total": sum(len(chapter["fact_ids"]) for chapter in chapters),
        "chapters": chapters,
        "limitations": copy.deepcopy(ledger["limitations"]),
    }
    return corpus, evidence_by_fact, readable_story


def _compile_oracle(
    *,
    ledger: dict[str, Any],
    corpus: dict[str, Any],
    evidence_by_fact: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    for source in ledger["facts"]:
        facts.append(
            {
                "fact_id": source["fact_id"],
                "chapter_id": source["chapter_id"],
                "recorded_at_chapter": source["recorded_at_chapter"],
                "narrative_index": source["narrative_index"],
                "event_type": source["event_type"],
                "phenomenon_codes": source["phenomenon_codes"],
                "fact_kind": source["fact_kind"],
                "actuality": source["actuality"],
                "proposition_truth": source["proposition_truth"],
                "updates_world_state": source["updates_world_state"],
                "updates_epistemic_state": source[
                    "updates_epistemic_state"
                ],
                "updates_identity_state": source["updates_identity_state"],
                "scope": source["scope"],
                "story_time": source["story_time"],
                "subject_entity_ids": source["subject_entity_ids"],
                "object_refs": source["object_refs"],
                "semantic_frame": source["semantic_frame"],
                "mutations": source["mutations"],
                "supersedes_fact_id": source["supersedes_fact_id"],
                "invalidates_fact_id": source["invalidates_fact_id"],
                "evidence": evidence_by_fact[source["fact_id"]],
            }
        )
    phenomenon_counts = {
        event_type: sum(
            event_type in fact["phenomenon_codes"] for fact in facts
        )
        for event_type in EVENT_TYPES
    }
    return {
        "schema_version": "v02-c12.6-oracle.v1",
        "benchmark_id": corpus["benchmark_id"],
        "generator_version": ledger["generator_version"],
        "root_seed_sha256": corpus["root_seed_sha256"],
        "scope": copy.deepcopy(SCOPE),
        "entity_registry": _entity_registry(),
        "location_registry": copy.deepcopy(LOCATIONS),
        "object_registry": copy.deepcopy(OBJECTS),
        "chapter_total": corpus["chapter_total"],
        "fact_total": len(facts),
        "phenomenon_counts": phenomenon_counts,
        "facts": facts,
        "limitations": copy.deepcopy(ledger["limitations"]),
    }


def build_oracle_schema() -> dict[str, Any]:
    fact_required = [
        "fact_id",
        "chapter_id",
        "recorded_at_chapter",
        "narrative_index",
        "event_type",
        "fact_kind",
        "actuality",
        "proposition_truth",
        "updates_world_state",
        "updates_epistemic_state",
        "updates_identity_state",
        "scope",
        "story_time",
        "subject_entity_ids",
        "object_refs",
        "semantic_frame",
        "mutations",
        "phenomenon_codes",
        "supersedes_fact_id",
        "invalidates_fact_id",
        "evidence",
    ]
    nullable_fact_id = {
        "oneOf": [
            {"type": "null"},
            {"type": "string", "pattern": "^F[0-9]{3}$"},
        ]
    }
    scalar_or_string_list = {
        "type": ["string", "array", "null"],
        "items": {"type": "string", "minLength": 1},
    }
    semantic_properties = {
        "subject": {"type": "string", "pattern": "^E[0-9]{2}$"},
        "speaker": {"type": "string", "pattern": "^E[0-9]{2}$"},
        "recipient": {"type": "string", "pattern": "^E[0-9]{2}$"},
        "predicate": {"type": "string", "minLength": 1},
        "object": {"type": "string", "minLength": 1},
        "truth": {"enum": ["TRUE", "FALSE", "UNKNOWN"]},
        "owner": {"type": "string", "pattern": "^E[0-9]{2}$"},
        "claimed_owner": {"type": "string", "pattern": "^E[0-9]{2}$"},
        "polarity": {"enum": ["positive", "negative"]},
        "realis": {"const": "planned"},
        "condition": {"type": "string", "minLength": 1},
        "before": {"type": ["string", "null"]},
        "after": {"type": ["string", "null"]},
        "physical_state": {"enum": sorted(PHYSICAL_LABELS)},
    }
    fact_properties = {
        "fact_id": {"type": "string", "pattern": "^F[0-9]{3}$"},
        "chapter_id": {"type": "string", "pattern": "^C[0-9]{2}$"},
        "recorded_at_chapter": {
            "type": "integer",
            "minimum": 1,
            "maximum": CHAPTER_TOTAL,
        },
        "narrative_index": {
            "type": "integer",
            "minimum": 1,
            "maximum": FACT_TOTAL,
        },
        "event_type": {"enum": list(EVENT_TYPES)},
        "fact_kind": {"enum": sorted(FACT_KINDS)},
        "actuality": {"enum": sorted(ACTUALITIES)},
        "proposition_truth": {"enum": sorted(PROPOSITION_TRUTHS)},
        "updates_world_state": {"type": "boolean"},
        "updates_epistemic_state": {"type": "boolean"},
        "updates_identity_state": {"type": "boolean"},
        "scope": {"$ref": "#/$defs/scope"},
        "story_time": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {"type": "integer", "minimum": 0},
        },
        "subject_entity_ids": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "pattern": "^E[0-9]{2}$"},
        },
        "object_refs": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "semantic_frame": {
            "type": "object",
            "additionalProperties": False,
            "required": ["predicate"],
            "properties": semantic_properties,
        },
        "mutations": {
            "type": "array",
            "maxItems": 2,
            "items": {"$ref": "#/$defs/mutation"},
        },
        "phenomenon_codes": {
            "type": "array",
            "minItems": 1,
            "maxItems": 1,
            "uniqueItems": True,
            "items": {"enum": list(EVENT_TYPES)},
        },
        "supersedes_fact_id": nullable_fact_id,
        "invalidates_fact_id": nullable_fact_id,
        "evidence": {"$ref": "#/$defs/evidence"},
    }
    limitation_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "pilot_foundation_only",
            "meets_full_x06_acceptance",
            "templated_text_systematically_overestimates",
            "substitute_for_real_chapters",
            "same_name_world_or_epistemic_exercise_included",
            "quality_result_registered",
            "statement",
        ],
        "properties": {
            "pilot_foundation_only": {"const": True},
            "meets_full_x06_acceptance": {"const": False},
            "templated_text_systematically_overestimates": {"const": True},
            "substitute_for_real_chapters": {"const": False},
            "same_name_world_or_epistemic_exercise_included": {
                "const": False
            },
            "quality_result_registered": {"const": False},
            "statement": {"const": LIMITATION_TEXT},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:v02:c12.6:oracle:v1",
        "title": "C12.6 程序生成状态机 Oracle",
        "$defs": {
            "scope": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "world_id",
                    "timeline_id",
                    "branch_id",
                    "policy_scope_id",
                ],
                "properties": {
                    "world_id": {"const": SCOPE["world_id"]},
                    "timeline_id": {"const": SCOPE["timeline_id"]},
                    "branch_id": {"const": SCOPE["branch_id"]},
                    "policy_scope_id": {
                        "enum": [SCOPE["policy_scope_id"], "P-FLASHBACK"]
                    },
                },
            },
            "mutation": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "path",
                    "operation",
                    "before",
                    "after",
                    "predecessor_fact_id",
                ],
                "properties": {
                    "path": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 4,
                        "items": {"type": "string", "minLength": 1},
                    },
                    "operation": {"enum": sorted(MUTATION_OPERATIONS)},
                    "before": scalar_or_string_list,
                    "after": scalar_or_string_list,
                    "predecessor_fact_id": nullable_fact_id,
                },
            },
            "evidence": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "chapter_id",
                    "source_block_id",
                    "start_char",
                    "end_char_exclusive",
                    "claim_span",
                    "span_sha256",
                    "chapter_text_sha256",
                ],
                "properties": {
                    "chapter_id": {
                        "type": "string",
                        "pattern": "^C[0-9]{2}$",
                    },
                    "source_block_id": {
                        "type": "string",
                        "pattern": "^C[0-9]{2}-L[0-9]{2}$",
                    },
                    "start_char": {"type": "integer", "minimum": 0},
                    "end_char_exclusive": {
                        "type": "integer",
                        "minimum": 1,
                    },
                    "claim_span": {"type": "string", "minLength": 1},
                    "span_sha256": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{64}$",
                    },
                    "chapter_text_sha256": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{64}$",
                    },
                },
            },
        },
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "benchmark_id",
            "generator_version",
            "root_seed_sha256",
            "scope",
            "entity_registry",
            "location_registry",
            "object_registry",
            "chapter_total",
            "fact_total",
            "phenomenon_counts",
            "facts",
            "limitations",
        ],
        "properties": {
            "schema_version": {"const": "v02-c12.6-oracle.v1"},
            "benchmark_id": {"type": "string"},
            "generator_version": {"const": GENERATOR_VERSION},
            "root_seed_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "scope": {"const": SCOPE},
            "entity_registry": {"const": _entity_registry()},
            "location_registry": {"const": LOCATIONS},
            "object_registry": {"const": OBJECTS},
            "chapter_total": {"const": CHAPTER_TOTAL},
            "fact_total": {"const": FACT_TOTAL},
            "phenomenon_counts": {
                "type": "object",
                "additionalProperties": False,
                "required": list(EVENT_TYPES),
                "properties": {
                    event_type: {"const": 5}
                    for event_type in EVENT_TYPES
                },
            },
            "facts": {
                "type": "array",
                "minItems": FACT_TOTAL,
                "maxItems": FACT_TOTAL,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": fact_required,
                    "properties": fact_properties,
                },
            },
            "limitations": limitation_schema,
        },
    }


def build_generator_contract() -> dict[str, Any]:
    return {
        "schema_version": "v02-c12.6-generator-contract.v1",
        "generator_version": GENERATOR_VERSION,
        "root_seed": ROOT_SEED,
        "root_seed_sha256": sha256_bytes(ROOT_SEED.encode("utf-8")),
        "chapter_total": CHAPTER_TOTAL,
        "fact_total": FACT_TOTAL,
        "chapter_density_rule": (
            "每章先分配2条，再按SHA-256域分离排名给20章各加1条"
        ),
        "event_types": list(EVENT_TYPES),
        "coordinate_contract": {
            "unit": "unicode_codepoint",
            "interval": "LEFT_CLOSED_RIGHT_OPEN",
            "authority": "chapter_text_sha256+start_char+end_char_exclusive",
        },
        "generation_order": [
            "canonical_transition_ledger",
            "state_reducer",
            "template_renderer",
            "oracle_compiler",
            "independent_replay_and_backpaste_verifier",
        ],
        "forbidden_shortcuts": [
            "oracle_from_rendered_text",
            "python_hash_or_global_random",
            "chapter_number_as_story_time",
            "planned_or_conditional_as_world_state",
            "same_name_entity_auto_merge",
            "model_quality_score",
        ],
        "limitations": {
            "pilot_foundation_only": True,
            "full_x06_original_target": "200章/500事实/关键现象每类30条",
            "meets_full_x06_acceptance": False,
            "templated_text_systematically_overestimates": True,
            "substitute_for_real_chapters": False,
            "same_name_world_or_epistemic_exercise_included": False,
            "quality_result_registered": False,
            "statement": LIMITATION_TEXT,
        },
    }


def _schema_type_matches(value: Any, expected: str) -> bool:
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int)
        and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if expected not in checks:
        raise _SchemaExecutionError(f"不支持的Schema类型：{expected}")
    return checks[expected](value)


def _execute_schema_node(
    *,
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
) -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        prefix = "#/$defs/"
        if not isinstance(ref, str) or not ref.startswith(prefix):
            raise _SchemaExecutionError(f"{path}：不支持的引用 {ref!r}")
        name = ref[len(prefix) :]
        target = root_schema.get("$defs", {}).get(name)
        if target is None:
            raise _SchemaExecutionError(f"{path}：引用不存在 {ref}")
        _execute_schema_node(
            value=value,
            schema=target,
            root_schema=root_schema,
            path=path,
        )
        return

    if "oneOf" in schema:
        matched = 0
        for candidate in schema["oneOf"]:
            try:
                _execute_schema_node(
                    value=value,
                    schema=candidate,
                    root_schema=root_schema,
                    path=path,
                )
            except _SchemaExecutionError:
                continue
            matched += 1
        if matched != 1:
            raise _SchemaExecutionError(
                f"{path}：oneOf命中数为{matched}，预期1"
            )
        return

    if "const" in schema and value != schema["const"]:
        raise _SchemaExecutionError(f"{path}：不等于合同常量")
    if "enum" in schema and value not in schema["enum"]:
        raise _SchemaExecutionError(f"{path}：值 {value!r} 不在枚举内")

    expected_types = schema.get("type")
    if expected_types is not None:
        types = (
            [expected_types]
            if isinstance(expected_types, str)
            else list(expected_types)
        )
        if not any(_schema_type_matches(value, item) for item in types):
            raise _SchemaExecutionError(
                f"{path}：类型不符，预期 {types}，实得 {type(value).__name__}"
            )

    if isinstance(value, dict):
        required = set(schema.get("required", []))
        missing = required - set(value)
        if missing:
            raise _SchemaExecutionError(f"{path}：缺字段 {sorted(missing)}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise _SchemaExecutionError(f"{path}：多字段 {sorted(extra)}")
        for name, child_schema in properties.items():
            if name not in value:
                continue
            _execute_schema_node(
                value=value[name],
                schema=child_schema,
                root_schema=root_schema,
                path=f"{path}/{name}",
            )

    if isinstance(value, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if minimum is not None and len(value) < minimum:
            raise _SchemaExecutionError(f"{path}：数组短于 {minimum}")
        if maximum is not None and len(value) > maximum:
            raise _SchemaExecutionError(f"{path}：数组长于 {maximum}")
        if schema.get("uniqueItems") and len(
            {canonical_bytes(item) for item in value}
        ) != len(value):
            raise _SchemaExecutionError(f"{path}：数组含重复项")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                _execute_schema_node(
                    value=item,
                    schema=item_schema,
                    root_schema=root_schema,
                    path=f"{path}/{index}",
                )

    if isinstance(value, str):
        minimum = schema.get("minLength")
        if minimum is not None and len(value) < minimum:
            raise _SchemaExecutionError(f"{path}：字符串短于 {minimum}")
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, value) is None:
            raise _SchemaExecutionError(f"{path}：不匹配 {pattern}")

    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < minimum:
            raise _SchemaExecutionError(f"{path}：小于 {minimum}")
        if maximum is not None and value > maximum:
            raise _SchemaExecutionError(f"{path}：大于 {maximum}")


def _execute_oracle_schema(
    oracle: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise _SchemaExecutionError("不接受未声明 Draft 2020-12 的合同")
    _execute_schema_node(
        value=oracle,
        schema=schema,
        root_schema=schema,
        path="$",
    )


def _validate_oracle_shape(oracle: dict[str, Any]) -> None:
    schema = build_oracle_schema()
    if set(oracle) != set(schema["required"]):
        raise BenchmarkError("oracle 顶层字段与严格合同不一致")
    required_fact = set(
        schema["properties"]["facts"]["items"]["required"]
    )
    for fact in oracle["facts"]:
        if set(fact) != required_fact:
            raise BenchmarkError(f"oracle 事实字段漂移：{fact.get('fact_id')}")
    try:
        _execute_oracle_schema(oracle, schema)
    except _SchemaExecutionError as error:
        raise BenchmarkError(f"oracle违反严格Schema：{error}") from error


def build_model_visible_packet(corpus: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "v02-c12.6-model-visible-packet.v1",
        "packet_role": "MODEL_VISIBLE_INPUT_ONLY",
        "benchmark_name": "C12.6程序生成状态机小样",
        "chapter_total": corpus["chapter_total"],
        "chapters": [
            {
                "chapter_number": chapter["chapter_number"],
                "title": chapter["title"],
                "text": chapter["text"],
                "text_sha256": chapter["text_sha256"],
            }
            for chapter in corpus["chapters"]
        ],
        "sealed_truth_included": False,
        "allowed_use": "只作为未来模型测试的公开题面；本轮不调用模型",
        "limitations": {
            "templated_text_systematically_overestimates": True,
            "substitute_for_real_chapters": False,
            "same_name_world_or_epistemic_exercise_included": False,
            "statement": LIMITATION_TEXT,
        },
    }


def build_input_access_manifest() -> dict[str, Any]:
    return {
        "schema_version": "v02-c12.6-input-access-manifest.v1",
        "default_packaging_mode": "PUBLIC_ONLY",
        "model_visible_paths": [PUBLIC_PACKET_PATH],
        "sealed_truth_paths": list(SEALED_ARTIFACT_PATHS),
        "mixed_public_and_sealed_packet_forbidden": True,
        "hard_stop_on_unlisted_model_input": True,
        "truth_id_scan_required_before_model_use": True,
        "model_api_calls_this_round": 0,
    }


def _validate_model_visible_packet(
    *,
    corpus: dict[str, Any],
    packet: dict[str, Any],
) -> int:
    raw = canonical_bytes(packet).decode("utf-8")
    leaks = TRUTH_ID_RE.findall(raw)
    if leaks:
        raise BenchmarkError(f"公开题面包泄漏真值或模板ID：{leaks[:3]}")
    expected = build_model_visible_packet(corpus)
    if packet != expected:
        raise BenchmarkError("公开题面包不是由密封正文机械投影而来")
    access = build_input_access_manifest()
    public_paths = set(access["model_visible_paths"])
    sealed_paths = set(access["sealed_truth_paths"])
    if public_paths & sealed_paths:
        raise BenchmarkError("公开题面包与密封真值包路径重叠")
    return len(leaks)


def _single_mutation(fact: dict[str, Any]) -> dict[str, Any]:
    if len(fact["mutations"]) != 1:
        raise BenchmarkError(
            f"{fact['event_type']}变更条数不是1：{fact['fact_id']}"
        )
    return fact["mutations"][0]


def _require_claim_tokens(
    fact: dict[str, Any],
    *tokens: str,
) -> None:
    claim_span = fact["evidence"]["claim_span"]
    missing = [token for token in tokens if token not in claim_span]
    if missing:
        raise BenchmarkError(
            f"语义字段没有被正文逐项托住：{fact['fact_id']}:{missing}"
        )


def _expected_claim_span(fact: dict[str, Any]) -> str:
    event_type = fact["event_type"]
    frame = fact["semantic_frame"]
    cycle = (fact["narrative_index"] - 1) // len(EVENT_TYPES)
    mutation = fact["mutations"][0] if fact["mutations"] else None

    if event_type == "MOVE":
        if mutation is None:
            raise BenchmarkError(f"移动事实缺少状态变更：{fact['fact_id']}")
        return (
            f"{_entity_label(frame['subject'])}从"
            f"{LOCATIONS[mutation['before']]}来到"
            f"{LOCATIONS[frame['object']]}。"
        )
    if event_type == "TRANSFER_ITEM":
        return (
            f"{_entity_label(frame['subject'])}把"
            f"{OBJECTS[frame['object']]}交给"
            f"{_entity_label(frame['recipient'])}，此后由后者保管。"
        )
    if event_type == "BODY_STATE_SET":
        return (
            f"{_entity_label(frame['subject'])}的身体状态从"
            f"{PHYSICAL_LABELS[frame['before']]}变为"
            f"{PHYSICAL_LABELS[frame['after']]}。"
        )
    if event_type == "GOAL_OPEN":
        return (
            f"{_entity_label(frame['subject'])}把查清第{cycle + 1}份失踪记录"
            "定为当前目标。"
        )
    if event_type == "GOAL_REPLACE":
        return (
            f"{_entity_label(frame['subject'])}放下查记录的原目标，"
            f"改为先找到第{cycle + 1}名失踪者。"
        )
    if event_type == "GOAL_COMPLETE":
        return (
            f"{_entity_label(frame['subject'])}找到那名失踪者，"
            "当前目标随之完成。"
        )
    if event_type == "OBSERVE":
        location_id = sorted(LOCATIONS)[(cycle + 1) % len(LOCATIONS)]
        return (
            f"{_entity_label(frame['subject'])}亲眼看见"
            f"{LOCATIONS[location_id]}的第{cycle + 1}盏信号灯亮起。"
        )
    if event_type == "INFORM":
        return (
            f"{_entity_label(frame['speaker'])}告诉"
            f"{_entity_label(frame['recipient'])}，"
            f"{OBJECTS[frame['object']]}现在由"
            f"{_entity_label(frame['owner'])}保管。"
        )
    if event_type == "RUMOR":
        location_id = sorted(LOCATIONS)[(cycle + 1) % len(LOCATIONS)]
        return (
            f"{_entity_label(frame['speaker'])}把“"
            f"{LOCATIONS[location_id]}今晚会封锁”的传闻告诉"
            f"{_entity_label(frame['recipient'])}，"
            "对方虽未见证据仍信以为真。"
        )
    if event_type == "NEGATION":
        return (
            f"{_entity_label(frame['subject'])}没有前往"
            f"{LOCATIONS[frame['object']]}。"
        )
    if event_type == "PLAN":
        return (
            f"{_entity_label(frame['subject'])}计划明日去"
            f"{LOCATIONS[frame['object']]}，但此刻尚未动身。"
        )
    if event_type == "CONDITION":
        return (
            f"{_entity_label(frame['subject'])}约定，只有拿到"
            f"{OBJECTS[frame['condition']]}，才会进入"
            f"{LOCATIONS[frame['object']]}。"
        )
    if event_type == "LIE":
        return (
            f"{_entity_label(frame['speaker'])}故意对"
            f"{_entity_label(frame['recipient'])}谎称，"
            f"{OBJECTS[frame['object']]}归"
            f"{_entity_label(frame['claimed_owner'])}所有；"
            "对方信了这个说法。"
        )
    if event_type == "CORRECTION":
        return (
            f"{_entity_label(frame['speaker'])}随后向"
            f"{_entity_label(frame['recipient'])}更正："
            f"{OBJECTS[frame['object']]}实际由"
            f"{_entity_label(frame['owner'])}保管，先前说法作废；"
            "对方接受更正，撤回旧信念并记住真相。"
        )
    if event_type == "FLASHBACK":
        return (
            f"{_entity_label(frame['subject'])}回忆起三日前曾在"
            f"{LOCATIONS[frame['object']]}受伤。"
        )
    if event_type == "ALIAS":
        return (
            f"从今天起，{_entity_label(frame['subject'])}在外行动时"
            f"使用化名“{frame['object']}”。"
        )
    raise BenchmarkError(f"没有角色化正文合同：{fact['fact_id']}")


def _validate_fact_binding(
    fact: dict[str, Any],
    fact_by_id: dict[str, dict[str, Any]],
) -> None:
    event_type = fact["event_type"]
    frame = fact["semantic_frame"]
    fact_id = fact["fact_id"]
    cycle = (fact["narrative_index"] - 1) // len(EVENT_TYPES)
    contract = EVENT_COMBINATION_CONTRACTS[event_type]
    observed_flags = (
        fact["updates_world_state"],
        fact["updates_epistemic_state"],
        fact["updates_identity_state"],
    )
    if (
        fact["fact_kind"] != contract["fact_kind"]
        or fact["actuality"] != contract["actuality"]
        or fact["proposition_truth"] != contract["proposition_truth"]
        or observed_flags != contract["flags"]
        or frame.get("predicate") != contract["predicate"]
        or set(frame) != contract["frame_keys"]
    ):
        raise BenchmarkError(f"事件类型与语义组合合同不一致：{fact_id}")
    if fact["phenomenon_codes"] != [event_type]:
        raise BenchmarkError(f"现象码与事件类型不一致：{fact_id}")
    if [
        mutation["operation"] for mutation in fact["mutations"]
    ] != EVENT_MUTATION_OPERATION_CONTRACTS[event_type]:
        raise BenchmarkError(f"状态操作类型与事件类型不一致：{fact_id}")
    if fact["evidence"]["chapter_id"] != fact["chapter_id"]:
        raise BenchmarkError(f"事实与证据章节不一致：{fact_id}")
    if event_type != "FLASHBACK" and fact["scope"] != SCOPE:
        raise BenchmarkError(f"当前事实越出主作用域：{fact_id}")
    expected_chapter_id = f"C{fact['recorded_at_chapter']:02d}"
    if fact["chapter_id"] != expected_chapter_id:
        raise BenchmarkError(f"记录章次与所属章节不一致：{fact_id}")
    expected_story_time = (
        [0, 0, cycle + 1, 0]
        if event_type == "FLASHBACK"
        else [1, 0, fact["narrative_index"], 0]
    )
    if fact["story_time"] != expected_story_time:
        raise BenchmarkError(f"故事时间偏离确定性生成合同：{fact_id}")
    if fact["supersedes_fact_id"] is not None:
        raise BenchmarkError(f"普通事件夹带替代关系：{fact_id}")
    if (
        event_type != "CORRECTION"
        and fact["invalidates_fact_id"] is not None
    ):
        raise BenchmarkError(f"非更正事件夹带作废关系：{fact_id}")

    no_mutation_events = {"NEGATION", "PLAN", "CONDITION", "FLASHBACK"}
    if event_type in no_mutation_events and fact["mutations"]:
        raise BenchmarkError(f"非变更事实夹带状态写入：{fact_id}")

    if event_type == "MOVE":
        mutation = _single_mutation(fact)
        expected_path = ["world", "entity_location", frame["subject"]]
        if (
            frame["subject"] not in ENTITIES
            or frame["object"] not in LOCATIONS
            or frame["polarity"] != "positive"
            or mutation["before"] not in LOCATIONS
            or mutation["path"] != expected_path
            or mutation["after"] != frame["object"]
            or fact["subject_entity_ids"] != [frame["subject"]]
            or fact["object_refs"] != [frame["object"]]
        ):
            raise BenchmarkError(f"移动事实的主体或路径串账：{fact_id}")
        _require_claim_tokens(
            fact,
            _entity_label(frame["subject"]),
            LOCATIONS[mutation["before"]],
            LOCATIONS[frame["object"]],
        )
    elif event_type == "TRANSFER_ITEM":
        mutation = _single_mutation(fact)
        if (
            frame["subject"] not in ENTITIES
            or frame["recipient"] not in ENTITIES
            or frame["object"] not in OBJECTS
            or mutation["path"]
            != ["world", "object_owner", frame["object"]]
            or mutation["before"] != frame["subject"]
            or mutation["after"] != frame["recipient"]
            or fact["subject_entity_ids"]
            != [frame["subject"], frame["recipient"]]
            or fact["object_refs"] != [frame["object"]]
        ):
            raise BenchmarkError(f"物品转移主体或路径串账：{fact_id}")
        _require_claim_tokens(
            fact,
            _entity_label(frame["subject"]),
            _entity_label(frame["recipient"]),
            OBJECTS[frame["object"]],
        )
    elif event_type == "BODY_STATE_SET":
        mutation = _single_mutation(fact)
        if (
            frame["subject"] not in ENTITIES
            or frame["before"] not in PHYSICAL_LABELS
            or frame["after"] not in PHYSICAL_LABELS
            or mutation["path"]
            != ["world", "entity_physical", frame["subject"]]
            or mutation["before"] != frame["before"]
            or mutation["after"] != frame["after"]
            or fact["subject_entity_ids"] != [frame["subject"]]
            or fact["object_refs"]
        ):
            raise BenchmarkError(f"身体状态主体或路径串账：{fact_id}")
        _require_claim_tokens(
            fact,
            _entity_label(frame["subject"]),
            PHYSICAL_LABELS[frame["before"]],
            PHYSICAL_LABELS[frame["after"]],
        )
    elif event_type in {"GOAL_OPEN", "GOAL_REPLACE", "GOAL_COMPLETE"}:
        mutation = _single_mutation(fact)
        expected_goal_a = f"G{cycle:02d}A"
        expected_goal_b = f"G{cycle:02d}B"
        if mutation["path"] != [
            "world",
            "active_goal",
            frame["subject"],
        ] or (
            frame["subject"] not in ENTITIES
            or fact["subject_entity_ids"] != [frame["subject"]]
        ):
            raise BenchmarkError(f"目标状态主体或路径串账：{fact_id}")
        if event_type == "GOAL_OPEN" and (
            frame["object"] != expected_goal_a
            or mutation["after"] != frame["object"]
            or fact["object_refs"] != [frame["object"]]
        ):
            raise BenchmarkError(f"目标开启载荷不一致：{fact_id}")
        if event_type == "GOAL_REPLACE" and (
            frame["before"] != expected_goal_a
            or frame["after"] != expected_goal_b
            or mutation["before"] != frame["before"]
            or mutation["after"] != frame["after"]
            or fact["object_refs"] != [frame["before"], frame["after"]]
        ):
            raise BenchmarkError(f"目标替换载荷不一致：{fact_id}")
        if event_type == "GOAL_COMPLETE" and (
            frame["object"] != expected_goal_b
            or mutation["before"] != frame["object"]
            or mutation["after"] is not None
            or fact["object_refs"] != [frame["object"]]
        ):
            raise BenchmarkError(f"目标完成载荷不一致：{fact_id}")
        goal_tokens = [_entity_label(frame["subject"])]
        goal_tokens.append(
            str(cycle + 1)
            if event_type != "GOAL_COMPLETE"
            else "当前目标"
        )
        _require_claim_tokens(fact, *goal_tokens)
    elif event_type == "OBSERVE":
        mutation = _single_mutation(fact)
        expected_proposition = f"P{cycle:02d}-SIGNAL"
        location_id = sorted(LOCATIONS)[(cycle + 1) % len(LOCATIONS)]
        if (
            frame["subject"] not in ENTITIES
            or frame["object"] != expected_proposition
            or frame["truth"] != "TRUE"
            or mutation["path"]
            != [
                "epistemic",
                "beliefs",
                frame["subject"],
                frame["object"],
            ]
            or mutation["after"] != "KNOWN_TRUE"
            or fact["subject_entity_ids"] != [frame["subject"]]
            or fact["object_refs"] != [frame["object"]]
        ):
            raise BenchmarkError(f"观察事实的知情主体或路径串账：{fact_id}")
        _require_claim_tokens(
            fact,
            _entity_label(frame["subject"]),
            LOCATIONS[location_id],
            "亲眼看见",
            "信号灯亮起",
        )
    elif event_type in {"NEGATION", "PLAN"}:
        subject = frame["subject"]
        location_id = frame["object"]
        if (
            subject not in ENTITIES
            or location_id not in LOCATIONS
            or fact["subject_entity_ids"] != [subject]
            or fact["object_refs"] != [location_id]
            or _entity_label(subject) not in fact["evidence"]["claim_span"]
            or LOCATIONS[location_id] not in fact["evidence"]["claim_span"]
        ):
            raise BenchmarkError(f"未发生事实的主体或对象没有被正文托住：{fact_id}")
        if event_type == "NEGATION" and (
            frame["polarity"] != "negative"
            or "没有前往" not in fact["evidence"]["claim_span"]
        ):
            raise BenchmarkError(f"否定事实没有被正文托住：{fact_id}")
        if event_type == "PLAN" and (
            frame["realis"] != "planned"
            or "尚未动身" not in fact["evidence"]["claim_span"]
        ):
            raise BenchmarkError(f"计划事实没有被正文托住：{fact_id}")
    elif event_type == "CONDITION":
        subject = frame["subject"]
        object_id = frame["condition"]
        location_id = frame["object"]
        if (
            subject not in ENTITIES
            or object_id not in OBJECTS
            or location_id not in LOCATIONS
            or fact["subject_entity_ids"] != [subject]
            or fact["object_refs"] != [object_id, location_id]
            or _entity_label(subject) not in fact["evidence"]["claim_span"]
            or OBJECTS[object_id] not in fact["evidence"]["claim_span"]
            or LOCATIONS[location_id] not in fact["evidence"]["claim_span"]
            or "只有" not in fact["evidence"]["claim_span"]
        ):
            raise BenchmarkError(f"条件事实没有被正文托住：{fact_id}")
    elif event_type in {"INFORM", "RUMOR", "LIE"}:
        mutation = _single_mutation(fact)
        if (
            frame["speaker"] not in ENTITIES
            or frame["recipient"] not in ENTITIES
        ):
            raise BenchmarkError(f"传递信息的人物不在登记册：{fact_id}")
        if (
            mutation["path"][:3]
            != ["epistemic", "beliefs", frame["recipient"]]
            or mutation["path"][3] not in fact["object_refs"]
            or frame["speaker"] not in fact["subject_entity_ids"]
            or frame["recipient"] not in fact["subject_entity_ids"]
        ):
            raise BenchmarkError(f"传递信息的知情主体或路径串账：{fact_id}")
        expected_after = {
            "INFORM": "TOLD_TRUE",
            "RUMOR": "BELIEVED_UNVERIFIED",
            "LIE": "BELIEVED_FALSE",
        }[event_type]
        if mutation["after"] != expected_after:
            raise BenchmarkError(f"知情状态值与事件类型不一致：{fact_id}")
        expected_object_refs = (
            [mutation["path"][3]]
            if event_type in {"INFORM", "RUMOR"}
            else [frame["object"], mutation["path"][3]]
        )
        if fact["object_refs"] != expected_object_refs:
            raise BenchmarkError(f"传递信息的对象引用不一致：{fact_id}")
        if event_type == "INFORM":
            expected_proposition = f"P{cycle:02d}-OWNER-TRUE"
            if (
                frame["truth"] != "TRUE"
                or frame["object"] not in OBJECTS
                or frame["owner"] not in ENTITIES
                or mutation["path"][3] != expected_proposition
                or fact["subject_entity_ids"]
                != [frame["speaker"], frame["recipient"]]
            ):
                raise BenchmarkError(f"告知事实的语义值不闭合：{fact_id}")
            _require_claim_tokens(
                fact,
                _entity_label(frame["speaker"]),
                _entity_label(frame["recipient"]),
                OBJECTS[frame["object"]],
                _entity_label(frame["owner"]),
            )
        elif event_type == "RUMOR":
            expected_proposition = f"P{cycle:02d}-RUMOR"
            if (
                frame["truth"] != "UNKNOWN"
                or frame["object"] != expected_proposition
                or mutation["path"][3] != expected_proposition
                or fact["subject_entity_ids"]
                != [frame["speaker"], frame["recipient"]]
            ):
                raise BenchmarkError(f"传闻事实的语义值不闭合：{fact_id}")
            _require_claim_tokens(
                fact,
                _entity_label(frame["speaker"]),
                _entity_label(frame["recipient"]),
                "传闻",
            )
        else:
            expected_proposition = f"P{cycle:02d}-LIE"
            if (
                frame["truth"] != "FALSE"
                or frame["object"] not in OBJECTS
                or frame["claimed_owner"] not in ENTITIES
                or mutation["path"][3] != expected_proposition
                or fact["subject_entity_ids"]
                != [
                    frame["speaker"],
                    frame["recipient"],
                    frame["claimed_owner"],
                ]
            ):
                raise BenchmarkError(f"谎言事实的语义值不闭合：{fact_id}")
            _require_claim_tokens(
                fact,
                _entity_label(frame["speaker"]),
                _entity_label(frame["recipient"]),
                OBJECTS[frame["object"]],
                _entity_label(frame["claimed_owner"]),
            )
        support_phrase = {
            "INFORM": "告诉",
            "RUMOR": "仍信以为真",
            "LIE": "对方信了这个说法",
        }[event_type]
        if support_phrase not in fact["evidence"]["claim_span"]:
            raise BenchmarkError(f"知情状态没有被正文明确托住：{fact_id}")
    elif event_type == "CORRECTION":
        target_id = fact["invalidates_fact_id"]
        target = fact_by_id.get(target_id)
        if (
            frame["truth"] != "TRUE"
            or frame["speaker"] not in ENTITIES
            or frame["recipient"] not in ENTITIES
            or frame["owner"] not in ENTITIES
            or frame["object"] not in OBJECTS
            or fact["subject_entity_ids"]
            != list(
                dict.fromkeys(
                    [
                        frame["speaker"],
                        frame["recipient"],
                        frame["owner"],
                    ]
                )
            )
        ):
            raise BenchmarkError(f"更正事实的语义值不闭合：{fact_id}")
        if (
            target is None
            or target["event_type"] != "LIE"
            or target["narrative_index"] >= fact["narrative_index"]
        ):
            raise BenchmarkError(f"更正没有绑定前序对应谎言：{fact_id}")
        for key in ("speaker", "recipient", "object"):
            if frame[key] != target["semantic_frame"][key]:
                raise BenchmarkError(f"更正与对应谎言命题错位：{fact_id}")
        if len(target["mutations"]) != 1 or len(fact["mutations"]) != 2:
            raise BenchmarkError(f"更正或对应谎言的变更条数错误：{fact_id}")
        lie_mutation = target["mutations"][0]
        retract = next(
            (
                mutation
                for mutation in fact["mutations"]
                if mutation["operation"] == "RETRACT"
            ),
            None,
        )
        corrected = next(
            (
                mutation
                for mutation in fact["mutations"]
                if mutation["operation"] == "CORRECT"
            ),
            None,
        )
        if (
            retract is None
            or retract["path"] != lie_mutation["path"]
            or retract["predecessor_fact_id"] != target_id
            or retract["before"] != "BELIEVED_FALSE"
            or retract["after"] != "RETRACTED_FALSE"
        ):
            raise BenchmarkError(f"更正没有撤回对应错误认知路径：{fact_id}")
        if (
            corrected is None
            or corrected["path"][:3]
            != ["epistemic", "beliefs", frame["recipient"]]
            or corrected["after"] != "KNOWN_TRUE"
        ):
            raise BenchmarkError(f"更正后的真命题写入错误主体：{fact_id}")
        if fact["object_refs"] != [
            frame["object"],
            lie_mutation["path"][3],
            corrected["path"][3],
        ]:
            raise BenchmarkError(f"更正对象引用没有闭合：{fact_id}")
        if "对方接受更正" not in fact["evidence"]["claim_span"]:
            raise BenchmarkError(f"更正后的知情状态没有被正文托住：{fact_id}")
        _require_claim_tokens(
            fact,
            _entity_label(frame["speaker"]),
            _entity_label(frame["recipient"]),
            OBJECTS[frame["object"]],
            _entity_label(frame["owner"]),
        )
    elif event_type == "ALIAS":
        mutation = _single_mutation(fact)
        subject = frame["subject"]
        alias = frame["object"]
        if (
            subject not in ENTITIES
            or fact["subject_entity_ids"] != [subject]
            or mutation["path"] != ["identity", "aliases", subject]
            or not isinstance(mutation["after"], list)
            or alias not in mutation["after"]
            or fact["object_refs"] != [alias]
        ):
            raise BenchmarkError(f"同名人物别名状态写入错误实体：{fact_id}")
        _require_claim_tokens(fact, _entity_label(subject), alias, "化名")
    elif event_type == "FLASHBACK":
        if (
            fact["scope"]["policy_scope_id"] != "P-FLASHBACK"
            or fact["scope"] == SCOPE
            or fact["story_time"][0] >= fact["recorded_at_chapter"]
            or frame["subject"] not in ENTITIES
            or fact["subject_entity_ids"] != [frame["subject"]]
            or frame["object"] not in LOCATIONS
            or fact["object_refs"]
            != [frame["object"], frame["physical_state"]]
            or frame["physical_state"] not in PHYSICAL_LABELS
            or LOCATIONS[frame["object"]]
            not in fact["evidence"]["claim_span"]
            or "回忆起三日前" not in fact["evidence"]["claim_span"]
        ):
            raise BenchmarkError(f"闪回没有进入独立历史作用域：{fact_id}")
        _require_claim_tokens(
            fact,
            _entity_label(frame["subject"]),
            PHYSICAL_LABELS[frame["physical_state"]],
        )

    expected_claim_span = _expected_claim_span(fact)
    if fact["evidence"]["claim_span"] != expected_claim_span:
        raise BenchmarkError(f"角色化正文合同不一致：{fact_id}")


def verify_generated_sample(
    *,
    ledger: dict[str, Any],
    corpus: dict[str, Any],
    oracle: dict[str, Any],
    snapshots: list[dict[str, Any]],
    readable_story: str,
    model_visible_packet: dict[str, Any] | None = None,
    expected_seed: str = ROOT_SEED,
) -> dict[str, Any]:
    _validate_oracle_shape(oracle)
    expected_seed_sha = sha256_bytes(expected_seed.encode("utf-8"))
    expected_counts = _chapter_fact_counts(expected_seed)
    if (
        ledger["schema_version"] != SCHEMA_VERSION
        or ledger["generator_version"] != GENERATOR_VERSION
        or ledger["root_seed"] != expected_seed
        or ledger["initial_state"] != _initial_state()
        or ledger["chapter_fact_counts"] != expected_counts
    ):
        raise BenchmarkError("规范事件账偏离固定基准身份")
    if (
        corpus["schema_version"] != "v02-c12.6-synthetic-corpus.v1"
        or corpus["benchmark_id"] != BENCHMARK_ID
        or corpus["root_seed_sha256"] != expected_seed_sha
        or oracle["benchmark_id"] != BENCHMARK_ID
        or oracle["root_seed_sha256"] != expected_seed_sha
    ):
        raise BenchmarkError("语料或Oracle偏离固定基准身份")
    if not (
        ledger["limitations"]
        == corpus["limitations"]
        == oracle["limitations"]
    ):
        raise BenchmarkError("限制声明没有三份同值闭合")
    public_packet = (
        build_model_visible_packet(corpus)
        if model_visible_packet is None
        else model_visible_packet
    )
    public_leak_total = _validate_model_visible_packet(
        corpus=corpus,
        packet=public_packet,
    )
    if corpus["chapter_total"] != CHAPTER_TOTAL:
        raise BenchmarkError("合成章节数不是30")
    if corpus["fact_total"] != FACT_TOTAL:
        raise BenchmarkError("语料声明事实数不是80")
    if oracle["fact_total"] != FACT_TOTAL:
        raise BenchmarkError("oracle事实数不是80")
    if len(ledger["facts"]) != FACT_TOTAL or len(snapshots) != CHAPTER_TOTAL:
        raise BenchmarkError("ledger或章末快照计数不闭合")

    expected_fact_chapters = [
        f"C{chapter_number:02d}"
        for chapter_number in range(1, CHAPTER_TOTAL + 1)
        for _ in range(expected_counts[chapter_number])
    ]
    chapter_ids = [chapter["chapter_id"] for chapter in corpus["chapters"]]
    expected_chapter_ids = [
        f"C{chapter_number:02d}"
        for chapter_number in range(1, CHAPTER_TOTAL + 1)
    ]
    if chapter_ids != expected_chapter_ids:
        raise BenchmarkError("章节ID没有按固定基准严格排序")
    facts = oracle["facts"]
    fact_ids = [fact["fact_id"] for fact in facts]
    if len(set(fact_ids)) != FACT_TOTAL:
        raise BenchmarkError("事实ID不唯一")
    fact_id_set = set(fact_ids)
    if any(
        ref not in fact_id_set
        for fact in facts
        for ref in [fact["supersedes_fact_id"], fact["invalidates_fact_id"]]
        if ref is not None
    ):
        raise BenchmarkError("纠正引用出现孤儿事实")
    corpus_fact_ids = [
        fact_id
        for chapter in corpus["chapters"]
        for fact_id in chapter["fact_ids"]
    ]
    if corpus_fact_ids != fact_ids:
        raise BenchmarkError("正文目录与oracle事实顺序不闭合")
    expected_source_blocks: dict[str, str] = {}
    expected_global_start = 0
    for chapter_number, chapter in enumerate(corpus["chapters"], 1):
        expected_chapter_id = f"C{chapter_number:02d}"
        expected_fact_ids = [
            f"F{index:03d}"
            for index, chapter_id in enumerate(expected_fact_chapters, 1)
            if chapter_id == expected_chapter_id
        ]
        rendered = f"{chapter['title']}\n{chapter['text']}\n"
        if (
            set(chapter)
            != {
                "chapter_id",
                "chapter_number",
                "title",
                "text",
                "text_sha256",
                "fact_ids",
                "global_start_char",
                "global_end_char_exclusive",
            }
            or chapter["chapter_number"] != chapter_number
            or chapter["title"] != f"第{chapter_number:02d}章"
            or chapter["text_sha256"]
            != sha256_bytes(chapter["text"].encode("utf-8"))
            or chapter["fact_ids"] != expected_fact_ids
            or chapter["global_start_char"] != expected_global_start
            or chapter["global_end_char_exclusive"]
            != expected_global_start + len(rendered)
        ):
            raise BenchmarkError(
                f"章节元数据偏离固定基准：{expected_chapter_id}"
            )
        for local_index, fact_id in enumerate(expected_fact_ids, 1):
            expected_source_blocks[fact_id] = (
                f"{expected_chapter_id}-L{local_index:02d}"
            )
        expected_global_start += len(rendered) + 1
    rebuilt_story = "\n".join(
        f"{chapter['title']}\n{chapter['text']}\n"
        for chapter in corpus["chapters"]
    )
    if rebuilt_story != readable_story:
        raise BenchmarkError("可读正文与章节载荷不一致")

    chapter_by_id = {
        chapter["chapter_id"]: chapter for chapter in corpus["chapters"]
    }
    backpaste_total = 0
    for fact in facts:
        chapter = chapter_by_id[fact["chapter_id"]]
        evidence = fact["evidence"]
        if evidence["chapter_text_sha256"] != chapter["text_sha256"]:
            raise BenchmarkError(f"章节SHA漂移：{fact['fact_id']}")
        start = evidence["start_char"]
        end = evidence["end_char_exclusive"]
        span = chapter["text"][start:end]
        if span != evidence["claim_span"]:
            raise BenchmarkError(f"证据坐标无法逐字回贴：{fact['fact_id']}")
        if sha256_bytes(span.encode("utf-8")) != evidence["span_sha256"]:
            raise BenchmarkError(f"证据片段SHA漂移：{fact['fact_id']}")
        backpaste_total += 1

    leaked = TRUTH_ID_RE.findall(readable_story)
    if leaked:
        raise BenchmarkError(f"模板或真值ID泄漏进正文：{leaked[:3]}")

    replay = copy.deepcopy(ledger["initial_state"])
    snapshot_by_chapter = {
        row["chapter_id"]: row["state"] for row in snapshots
    }
    for chapter_number, snapshot in enumerate(snapshots, 1):
        chapter_id = f"C{chapter_number:02d}"
        chapter_fact_ids = next(
            chapter["fact_ids"]
            for chapter in corpus["chapters"]
            if chapter["chapter_id"] == chapter_id
        )
        if (
            set(snapshot)
            != {"chapter_id", "chapter_number", "after_fact_id", "state"}
            or snapshot["chapter_id"] != chapter_id
            or snapshot["chapter_number"] != chapter_number
            or snapshot["after_fact_id"] != chapter_fact_ids[-1]
        ):
            raise BenchmarkError(f"章末快照元数据不闭合：{chapter_id}")
    last_writer_by_path: dict[str, str] = {}
    current_chapter: str | None = None
    oracle_fact_keys = (
        "fact_id",
        "chapter_id",
        "recorded_at_chapter",
        "narrative_index",
        "event_type",
        "phenomenon_codes",
        "fact_kind",
        "actuality",
        "proposition_truth",
        "updates_world_state",
        "updates_epistemic_state",
        "updates_identity_state",
        "scope",
        "story_time",
        "subject_entity_ids",
        "object_refs",
        "semantic_frame",
        "mutations",
        "supersedes_fact_id",
        "invalidates_fact_id",
    )
    fact_by_id = {fact["fact_id"]: fact for fact in facts}
    for expected_index, (source, fact) in enumerate(
        zip(ledger["facts"], facts, strict=True),
        1,
    ):
        if source["fact_id"] != fact["fact_id"]:
            raise BenchmarkError("ledger与oracle事实顺序不一致")
        expected_fact_id = f"F{expected_index:03d}"
        expected_event_type = EVENT_TYPES[
            (expected_index - 1) % len(EVENT_TYPES)
        ]
        if (
            fact["fact_id"] != expected_fact_id
            or fact["narrative_index"] != expected_index
            or fact["event_type"] != expected_event_type
            or fact["chapter_id"] != expected_fact_chapters[expected_index - 1]
        ):
            raise BenchmarkError(
                f"事实顺序偏离固定基准：{fact['fact_id']}"
            )
        if any(fact[key] != source[key] for key in oracle_fact_keys):
            raise BenchmarkError(
                f"oracle语义载荷偏离规范事件账：{fact['fact_id']}"
            )
        if (
            source["render_template_id"]
            != f"TPL-{fact['event_type']}-V1"
            or source["render_payload"]
            != {
                "cycle": (expected_index - 1) // len(EVENT_TYPES),
                "subject_entity_ids": fact["subject_entity_ids"],
                "object_refs": fact["object_refs"],
            }
            or source["sentence"] != fact["evidence"]["claim_span"]
        ):
            raise BenchmarkError(
                f"渲染来源没有绑定固定事实：{fact['fact_id']}"
            )
        if (
            fact["evidence"]["source_block_id"]
            != expected_source_blocks[fact["fact_id"]]
        ):
            raise BenchmarkError(
                f"证据块号偏离章节事实位置：{fact['fact_id']}"
            )
        _validate_fact_binding(fact, fact_by_id)
        current_chapter = fact["chapter_id"]
        for mutation in fact["mutations"]:
            predecessor = mutation["predecessor_fact_id"]
            path_key = "/".join(mutation["path"])
            expected_predecessor = last_writer_by_path.get(path_key)
            if predecessor != expected_predecessor:
                raise BenchmarkError(
                    f"前驱事实不是同一路径上一次写入者："
                    f"{fact['fact_id']}->{predecessor}"
                )
            before = _get_path(replay, mutation["path"])
            if before != mutation["before"]:
                raise BenchmarkError(f"状态重放before不一致：{fact['fact_id']}")
            _set_path(replay, mutation["path"], mutation["after"])
            last_writer_by_path[path_key] = fact["fact_id"]
        next_fact = (
            facts[fact["narrative_index"]]
            if fact["narrative_index"] < len(facts)
            else None
        )
        if next_fact is None or next_fact["chapter_id"] != current_chapter:
            if replay != snapshot_by_chapter[current_chapter]:
                raise BenchmarkError(f"章末快照不一致：{current_chapter}")

        world_mutations = [
            mutation
            for mutation in fact["mutations"]
            if mutation["path"][0] == "world"
        ]
        epistemic_mutations = [
            mutation
            for mutation in fact["mutations"]
            if mutation["path"][0] == "epistemic"
        ]
        identity_mutations = [
            mutation
            for mutation in fact["mutations"]
            if mutation["path"][0] == "identity"
        ]
        if fact["updates_world_state"] != bool(world_mutations):
            raise BenchmarkError(f"世界状态标记不一致：{fact['fact_id']}")
        if fact["updates_epistemic_state"] != bool(epistemic_mutations):
            raise BenchmarkError(f"知情状态标记不一致：{fact['fact_id']}")
        if fact["updates_identity_state"] != bool(identity_mutations):
            raise BenchmarkError(f"身份状态标记不一致：{fact['fact_id']}")
        if fact["actuality"] in NON_WORLD_ACTUALITIES and world_mutations:
            raise BenchmarkError(
                f"非现实事实污染当前世界状态：{fact['fact_id']}"
            )

    recomputed_phenomenon_counts = {
        event_type: sum(
            fact["phenomenon_codes"] == [event_type] for fact in facts
        )
        for event_type in EVENT_TYPES
    }
    if oracle["phenomenon_counts"] != recomputed_phenomenon_counts:
        raise BenchmarkError("现象计数不是由事实账重算所得")
    if any(count != 5 for count in recomputed_phenomenon_counts.values()):
        raise BenchmarkError("16类现象没有各出现5次")
    if not any(
        fact["actuality"] == "FLASHBACK"
        and fact["story_time"][0] < fact["recorded_at_chapter"]
        for fact in facts
    ):
        raise BenchmarkError("没有生成叙述章序与故事时间分离的闪回")
    same_name_ids = [
        entity_id
        for entity_id, row in oracle["entity_registry"].items()
        if row["display_name"] == "苏禾"
    ]
    if same_name_ids != ["E05", "E06"]:
        raise BenchmarkError("同名实体没有保持两个独立ID")

    frozen_payload_digests_applicable = expected_seed == ROOT_SEED
    frozen_payload_digests_verified = False
    if expected_seed == ROOT_SEED:
        snapshot_wrapper = {
            "schema_version": "v02-c12.6-chapter-snapshots.v1",
            "root_seed_sha256": expected_seed_sha,
            "snapshots": snapshots,
        }
        observed_digests = {
            "ledger": sha256_bytes(canonical_bytes(ledger)),
            "corpus": sha256_bytes(canonical_bytes(corpus)),
            "oracle": sha256_bytes(canonical_bytes(oracle)),
            "snapshots_wrapper": sha256_bytes(
                canonical_bytes(snapshot_wrapper)
            ),
            "readable_story": sha256_bytes(
                readable_story.encode("utf-8")
            ),
        }
        drifted = [
            name
            for name, expected_sha in ROOT_SEED_FROZEN_DIGESTS.items()
            if observed_digests[name] != expected_sha
        ]
        if drifted:
            raise BenchmarkError(
                f"固定种子整包指纹漂移：{drifted}"
            )
        frozen_payload_digests_verified = True

    return {
        "schema_version": "v02-c12.6-verification-receipt.v1",
        "status": "ENGINEERING_FOUNDATION_READY",
        "chapter_total": CHAPTER_TOTAL,
        "fact_total": FACT_TOTAL,
        "event_type_total": len(EVENT_TYPES),
        "event_type_distribution": recomputed_phenomenon_counts,
        "claim_span_backpaste": {
            "passed": backpaste_total,
            "total": FACT_TOTAL,
            "rate": 1.0,
        },
        "chapter_end_snapshot_replay": {
            "passed": CHAPTER_TOTAL,
            "total": CHAPTER_TOTAL,
            "rate": 1.0,
        },
        "orphan_reference_total": 0,
        "truth_id_leak_total": 0,
        "public_packet_truth_id_leak_total": public_leak_total,
        "public_and_sealed_packets_separated": True,
        "frozen_payload_digests_applicable": (
            frozen_payload_digests_applicable
        ),
        "frozen_payload_digests_verified": (
            frozen_payload_digests_verified
        ),
        "oracle_schema_validation_engine": (
            "embedded_draft202012_contract_executor"
        ),
        "model_api_calls": 0,
        "network_requests": 0,
        "quality_result_registered": False,
        "winner": None,
        "limitations": copy.deepcopy(ledger["limitations"]),
    }


def _implementation_binding() -> dict[str, Any]:
    if not TEST_PATH.is_file():
        raise BenchmarkError(f"缺测试文件：{display_path(TEST_PATH)}")
    return {
        "schema_version": "v02-c12.6-implementation-binding.v1",
        "program": {
            "path": display_path(SELF_PATH),
            "sha256": sha256_file(SELF_PATH),
        },
        "test": {
            "path": display_path(TEST_PATH),
            "sha256": sha256_file(TEST_PATH),
        },
        "program_or_test_change_requires_artifact_regeneration": True,
    }


def _build_payload_objects(seed: str = ROOT_SEED) -> dict[str, Any]:
    ledger, snapshots = _build_canonical_ledger(seed)
    corpus, evidence, readable_story = _render_corpus(ledger)
    model_visible_packet = build_model_visible_packet(corpus)
    oracle = _compile_oracle(
        ledger=ledger,
        corpus=corpus,
        evidence_by_fact=evidence,
    )
    verification = verify_generated_sample(
        ledger=ledger,
        corpus=corpus,
        oracle=oracle,
        snapshots=snapshots,
        readable_story=readable_story,
        model_visible_packet=model_visible_packet,
        expected_seed=seed,
    )
    return {
        "input_access_manifest_v1.json": build_input_access_manifest(),
        PUBLIC_PACKET_PATH: model_visible_packet,
        "sealed/generator_contract_v1.json": build_generator_contract(),
        "sealed/oracle_schema_v1.json": build_oracle_schema(),
        "sealed/canonical_transition_ledger_v1.json": ledger,
        "sealed/synthetic_corpus_v1.json": corpus,
        "sealed/synthetic_story_v1.txt": readable_story,
        "sealed/oracle_manifest_v1.json": oracle,
        "sealed/chapter_end_snapshots_v1.json": {
            "schema_version": "v02-c12.6-chapter-snapshots.v1",
            "root_seed_sha256": sha256_bytes(seed.encode("utf-8")),
            "snapshots": snapshots,
        },
        "receipts/oracle_closure_receipt.json": verification,
        "receipts/implementation_binding_receipt.json": _implementation_binding(),
    }


def _artifact_set_sha(files: dict[str, bytes]) -> str:
    rows = [
        {"path": name, "sha256": sha256_bytes(raw)}
        for name, raw in sorted(files.items())
    ]
    return sha256_bytes(canonical_bytes(rows))


def _stop_receipt(verification: dict[str, Any]) -> str:
    return f"""# C12.6｜程序生成状态机基准停点回包

✅ 结论：30 章／80 事实的程序真值底座工程可用；本轮没有调用模型，
也没有登记任何真实网文质量胜负。

🔥 {LIMITATION_TEXT}

## 本轮交付

- 程序先生成规范状态变更账，再渲染中文；Oracle 从规范账编译，
  不从渲染后的中文反抽。
- 30 章、80 条事实；16 类现象各 5 条。
- 80／80 证据片段按字符坐标逐字回贴。
- 30／30 章末状态可从初始状态与事件账独立重放。
- 更正必须绑定对应谎言与错误认知路径；同名人物的状态写入必须命中自己的实体 ID。
- 知情状态均由正文显式托住；计划、条件、否定、谎言、闪回不污染当前世界状态。
- 模型可见公开题面与密封真值分包，公开包真值／模板 ID 泄漏为 0。
- 固定种子双重独立重建，纳入比较的全部候选载荷逐字节一致。

## 定性边界

- 本件只回答“评测地基和 Oracle 能不能机械闭合”。
- 它不满足 X06 原案 200 章／500 事实的完整规模。
- 同名人物本轮只实际演练别名状态，尚未覆盖其世界状态与知情状态变化。
- 不跑任何模型，不报抽取准确率，不替代真实章节。

## 保护面

- 模型 API／网络请求：0／0。
- 现役链、正式金标、默认项、C13：均未触碰。
- 质量结果：未登记；赢家：无。

来源：Codex
"""


def build_artifacts(seed: str = ROOT_SEED) -> tuple[dict[str, bytes], bytes]:
    first_objects = _build_payload_objects(seed)
    second_objects = _build_payload_objects(seed)
    first = {
        name: (
            value.encode("utf-8")
            if isinstance(value, str)
            else canonical_bytes(value)
        )
        for name, value in first_objects.items()
    }
    second = {
        name: (
            value.encode("utf-8")
            if isinstance(value, str)
            else canonical_bytes(value)
        )
        for name, value in second_objects.items()
    }
    first["C12_6_stop_receipt.md"] = _stop_receipt(
        first_objects["receipts/oracle_closure_receipt.json"]
    ).encode("utf-8")
    second["C12_6_stop_receipt.md"] = _stop_receipt(
        second_objects["receipts/oracle_closure_receipt.json"]
    ).encode("utf-8")
    if first != second:
        raise BenchmarkError("两次独立生成不是字节级一致")
    double_run = {
        "schema_version": "v02-c12.6-double-run.v1",
        "independent_rebuild_count": 2,
        "byte_identical": True,
        "compared_file_total": len(first),
        "payload_set_sha256": _artifact_set_sha(first),
    }
    files = {
        **first,
        "receipts/double_run_receipt.json": canonical_bytes(double_run),
    }
    rows = [
        {"path": name, "sha256": sha256_bytes(raw)}
        for name, raw in sorted(files.items())
    ]
    manifest = {
        "schema_version": "v02-c12.6-artifact-manifest.v1",
        "artifact_set_sha256": sha256_bytes(canonical_bytes(rows)),
        "file_total_excluding_self": len(rows),
        "files": rows,
        "model_visible_paths": [PUBLIC_PACKET_PATH],
        "sealed_truth_paths": list(SEALED_ARTIFACT_PATHS),
        "mixed_public_and_sealed_packet_forbidden": True,
        "chapter_total": CHAPTER_TOTAL,
        "fact_total": FACT_TOTAL,
        "pilot_foundation_only": True,
        "meets_full_x06_acceptance": False,
        "templated_text_systematically_overestimates": True,
        "substitute_for_real_chapters": False,
        "same_name_world_or_epistemic_exercise_included": False,
        "model_api_calls": 0,
        "network_requests": 0,
        "quality_result_registered": False,
        "winner": None,
        "active_route_mutations": 0,
        "gold_mutations": 0,
        "c13_touched": False,
    }
    return files, canonical_bytes(manifest)


def _assert_output_path() -> None:
    resolved = OUTPUT_DIR.resolve()
    protected = [
        (ROOT / "config/gold").resolve(),
        (ROOT / "runs").resolve(),
        (
            ROOT
            / "experiments/extraction_redesign_v02_overnight_20260725"
            / "V02_C13_downstream_consumer_20260725"
        ).resolve(),
    ]
    if any(resolved == root or resolved.is_relative_to(root) for root in protected):
        raise BenchmarkError("C12.6 输出路径落入冻结或并行根")


def _is_ignorable_runtime_cache(relative_path: Path) -> bool:
    return (
        "__pycache__" in relative_path.parts
        and relative_path.suffix in {".pyc", ".pyo"}
    )


def _controlled_output_names() -> set[str]:
    return {
        relative.as_posix()
        for path in OUTPUT_DIR.rglob("*")
        if path.is_file()
        and not _is_ignorable_runtime_cache(
            relative := path.relative_to(OUTPUT_DIR)
        )
    }


def write_bundle() -> dict[str, Any]:
    _assert_output_path()
    files, manifest_raw = build_artifacts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    expected_names = set(files) | {
        "artifact_manifest.json",
        f"program/{SELF_PATH.name}",
    }
    stale = _controlled_output_names() - expected_names
    unknown_stale = stale - LEGACY_FLAT_ARTIFACTS
    if unknown_stale:
        raise BenchmarkError(
            f"C12.6 输出目录含未知陈旧文件：{sorted(unknown_stale)}"
        )
    for relative in sorted(stale):
        (OUTPUT_DIR / relative).unlink()
    for name, raw in files.items():
        target = OUTPUT_DIR / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (OUTPUT_DIR / "artifact_manifest.json").write_bytes(manifest_raw)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_bytes(files["C12_6_stop_receipt.md"])
    return json.loads(manifest_raw)


def check_bundle() -> dict[str, Any]:
    files, manifest_raw = build_artifacts()
    expected = {**files, "artifact_manifest.json": manifest_raw}
    expected_names = set(expected) | {f"program/{SELF_PATH.name}"}
    actual_names = _controlled_output_names()
    if actual_names != expected_names:
        raise BenchmarkError(
            "C12.6 工件集合不闭合："
            f"missing={sorted(expected_names - actual_names)} "
            f"extra={sorted(actual_names - expected_names)}"
        )
    for name, raw in expected.items():
        if (OUTPUT_DIR / name).read_bytes() != raw:
            raise BenchmarkError(f"C12.6 工件漂移：{name}")
    if REPORT_PATH.read_bytes() != files["C12_6_stop_receipt.md"]:
        raise BenchmarkError("C12.6 本地回包与工件正文不一致")
    return json.loads(manifest_raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = check_bundle() if args.check else write_bundle()
    print(
        json.dumps(
            {
                "status": "CANDIDATE_FOUNDATION_ENGINEERING_READY",
                "artifact_set_sha256": manifest["artifact_set_sha256"],
                "chapters": manifest["chapter_total"],
                "facts": manifest["fact_total"],
                "model_api_calls": 0,
                "network_requests": 0,
                "quality_result_registered": False,
                "output_dir": display_path(OUTPUT_DIR),
                "report_path": display_path(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

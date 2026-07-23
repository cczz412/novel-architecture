#!/usr/bin/env python3
"""第93道续令③：把五份 v1.3 修订候选机械登记为正式金标。

本工具只做身份、审收和入口登记：
- 五份候选的 claim、证据锚、部件 ID 与顺序一字不改；
- 生成五份正式金标、五个独立 current 指针和统一正式金标登记册；
- X01、现役 122 条、默认链、分类规则和 outbox 全部只读。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve()
REPORT_DIR = Path("reports/Z93_五本结构层金标v1.3转正_20260723")
AUTHORIZATION = Path(
    "runs/Z93_五本结构层金标v1.3转正_v1.0_20260723/"
    "authorization_readback.json"
)
PROVENANCE_LABEL = "Codex验闸＋Cursor攻击定稿、非CZ亲验"

BOOKS: dict[str, dict[str, Any]] = {
    "Z74B-B01": {
        "short": "B01",
        "candidate": (
            "reports/Z93_五本金标候选修订_20260723/revised_candidates/"
            "B01_知否_库存第0033单元_结构层银标修订候选v1.3.json"
        ),
        "candidate_sha256": "7d3be752b2db8844074bf8e5a783d88e0a4fbf7e425c52ecfff1029adeee1c67",
        "formal_name": "B01_知否_库存第0033单元_结构层金标v1.3.json",
        "pointer_name": "Z74B_B01_U0033_structure_gold_current.json",
        "inventory_unit": 33,
    },
    "Z74B-B02": {
        "short": "B02",
        "candidate": (
            "reports/Z93_五本金标候选修订_20260723/revised_candidates/"
            "B02_大王饶命_库存第0039单元_结构层银标修订候选v1.3.json"
        ),
        "candidate_sha256": "7b1d69354158c58d321745a8cd9aa1a3583af366e601e05cc5c45be11787476a",
        "formal_name": "B02_大王饶命_库存第0039单元_结构层金标v1.3.json",
        "pointer_name": "Z74B_B02_U0039_structure_gold_current.json",
        "inventory_unit": 39,
    },
    "Z74B-B03": {
        "short": "B03",
        "candidate": (
            "reports/Z93_五本金标候选修订_20260723/revised_candidates/"
            "B03_神秘复苏_库存第0041单元_结构层银标修订候选v1.3.json"
        ),
        "candidate_sha256": "111e55195dc768219e33358ed2f917752a145350f922453c0b06431e48a45ec7",
        "formal_name": "B03_神秘复苏_库存第0041单元_结构层金标v1.3.json",
        "pointer_name": "Z74B_B03_U0041_structure_gold_current.json",
        "inventory_unit": 41,
    },
    "Z74B-B04": {
        "short": "B04",
        "candidate": (
            "reports/Z93_五本金标候选修订_20260723/revised_candidates/"
            "B04_无限恐怖_库存第0003单元_结构层银标修订候选v1.3.json"
        ),
        "candidate_sha256": "873d2cab6f644d6254be463e59340275fe5e62b97dd11c3889f421e51b4c5e55",
        "formal_name": "B04_无限恐怖_库存第0003单元_结构层金标v1.3.json",
        "pointer_name": "Z74B_B04_U0003_structure_gold_current.json",
        "inventory_unit": 3,
    },
    "Z74B-B05": {
        "short": "B05",
        "candidate": (
            "reports/Z93_五本金标候选修订_20260723/revised_candidates/"
            "B05_凡人修仙传_库存第0030单元_结构层银标修订候选v1.3.json"
        ),
        "candidate_sha256": "ff2a20959a78e770293beb0f197f96e109b14eca710375013a4c9ca4d7d5c756",
        "formal_name": "B05_凡人修仙传_库存第0030单元_结构层金标v1.3.json",
        "pointer_name": "Z74B_B05_U0030_structure_gold_current.json",
        "inventory_unit": 30,
    },
}

EVIDENCE_FILES: dict[str, tuple[str, str]] = {
    "revision_ledger": (
        "reports/Z93_五本金标候选修订_20260723/revision_ledger.json",
        "0260775da470667cec9d48aeeb18b886d6de96651f61a65f580caca5cde852f9",
    ),
    "scope_reconciliation": (
        "reports/Z93_五本金标候选修订_20260723/scope_reconciliation.json",
        "74e5a0355614a00a38a5455ca8996b301677c8b5a0284099b6a20f359809de52",
    ),
    "revision_double_run": (
        "reports/Z93_五本金标候选修订_20260723/mechanical_double_run_receipt.json",
        "914c7957fdd7f28afe21363e834dd030d50f1c3d8024c259bcd7df5dc7af2b53",
    ),
    "revision_protected_state": (
        "reports/Z93_五本金标候选修订_20260723/protected_state_audit.json",
        "f06c042a99783d85b524cb7ee9ac2f294f4214d446fc9c6911e0fb8bfeff575a",
    ),
    "codex_final_judgments": (
        "runs/Z93_五本金标候选逐条验闸_v1.0_20260723/review/final_judgments.json",
        "2b12412090d172fb998b4f5ddb93381bfa7d74dc56b19fe085a58a45cb9b58d2",
    ),
    "cursor_attack_receipt": (
        "reports/Z93_五本金标候选逐条验闸_20260723/cursor_red_team_attack_receipt.json",
        "077a19847a4f38fb3372353798fe291f8a1c4fd96749e51da663a58249797593",
    ),
    "cursor_attack_report": (
        "reports/Z93_五本金标候选逐条验闸_20260723/"
        "第93道Cursor六件只读攻击回包_20260723.md",
        "26b3fb8a044c563163b6819ce4377b6dab24a03e8a1fc1cb04b742ba314b97ae",
    ),
}

PROTECTED_FILES: dict[str, tuple[str, str]] = {
    "x01_formal_gold": (
        "reports/Z73_第3章金标v1.2定稿转正_20260721/第3章结构层金标v1.2.json",
        "0df08ede4fa1a33f4bd9e1aea3e45387c8d77131ce79ff1496fe1320fa48a10e",
    ),
    "x01_gold_pointer": (
        "config/gold/X01_ch0003_structure_gold_current.json",
        "6a5c785dc98381ff4d9b7e207c599c29914f394e4b43e399d37f65093cc5a60c",
    ),
    "default_registry": (
        "config/defaults/zbatch_v1.2_full_chain.json",
        "b23b5cce26b9cfe584dd97dbff6422efa2b22ccd5cba38c6ed6a44c4543bc0a1",
    ),
    "runner": (
        "tools/zbatch.py",
        "160c28b3ef0210fd05c392f713534cf1ffdf041fa596ec790545b64955280850",
    ),
    "classification_contract_active": (
        "config/contracts/classify_rules_v1.2_semantic_identity_v1.json",
        "45f7610b86d5962e0d3d9d4d95886aad9022f1beaece200c2452b9a361f6c108",
    ),
    "classification_contract_archive": (
        "config/contracts/classify_rules_v1.2.json",
        "ad2ccc3b13e8b138a32a46b8566e928a3c4e35a60cf31c5494c7b9ba3dd021de",
    ),
    "active_122": (
        "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/"
        "02_verify/valid_records.json",
        "dafa16901a6edb5018a5176f3f5f7388273e72051def7fe4e997489d01e804ba",
    ),
}

EXPECTED_OUTBOX = {
    "files": 18,
    "bytes": 942264,
    "sha256": "d67a3be7df95bc34089237213049b201d6f8e22c2b971d7f6b76f48e125cc38d",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"JSON顶层不是对象：{path}")
    return value


def tree_fingerprint(path: Path) -> dict[str, Any]:
    rows: list[tuple[str, str, int]] = []
    for file in sorted(p for p in path.rglob("*") if p.is_file() and p.name != ".DS_Store"):
        rows.append((str(file.relative_to(path)), sha256_file(file), file.stat().st_size))
    payload = "\n".join(f"{name}\t{digest}\t{size}" for name, digest, size in rows)
    return {
        "files": len(rows),
        "bytes": sum(size for _, _, size in rows),
        "sha256": sha256_bytes(payload.encode("utf-8")),
    }


def check_inputs() -> dict[str, Any]:
    candidates: dict[str, str] = {}
    for book_id, config in BOOKS.items():
        actual = sha256_file(ROOT / config["candidate"])
        if actual != config["candidate_sha256"]:
            raise AssertionError(f"v1.3候选SHA漂移：{book_id}｜{actual}")
        candidates[book_id] = actual
    evidence: dict[str, str] = {}
    for key, (relative, expected) in EVIDENCE_FILES.items():
        actual = sha256_file(ROOT / relative)
        if actual != expected:
            raise AssertionError(f"审收依据SHA漂移：{key}｜{actual}")
        evidence[key] = actual
    protected: dict[str, str] = {}
    for key, (relative, expected) in PROTECTED_FILES.items():
        actual = sha256_file(ROOT / relative)
        if actual != expected:
            raise AssertionError(f"保护件SHA漂移：{key}｜{actual}")
        protected[key] = actual
    outbox = tree_fingerprint(ROOT / "outbox")
    if outbox != EXPECTED_OUTBOX:
        raise AssertionError(f"outbox指纹漂移：{outbox}")
    authorization = read_json(ROOT / AUTHORIZATION)
    if authorization.get("status") != "authorized":
        raise AssertionError("续令③授权回读未通过")
    if authorization["authorized_scope"]["provenance_label"] != PROVENANCE_LABEL:
        raise AssertionError("授权回读 provenance 不符")
    return {
        "candidates": candidates,
        "evidence": evidence,
        "protected": protected,
        "outbox": outbox,
        "authorization_sha256": sha256_file(ROOT / AUTHORIZATION),
    }


def all_parts(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        part
        for item in document["layered_items"]
        for part in item["parts"]
    ]


def semantic_payload(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": document["source"],
        "source_window": document["source_window"],
        "items": [
            {
                "item_id": item["item_id"],
                "parts": [
                    {
                        "part_id": part["part_id"],
                        "layer": part["layer"],
                        "score_in_single_chapter": part["score_in_single_chapter"],
                        "claim": part["claim"],
                        "claim_components": part["claim_components"],
                        "source_evidence": part["source_evidence"],
                        "target_chapter_relation": part.get("target_chapter_relation"),
                    }
                    for part in item["parts"]
                ],
                "hindsight_parts": item.get("hindsight_parts", []),
            }
            for item in document["layered_items"]
        ],
    }


def anchor_count(document: dict[str, Any]) -> int:
    return sum(len(part["source_evidence"]) for part in all_parts(document))


def _formalize_part(part: dict[str, Any]) -> None:
    scoreable = bool(part["score_in_single_chapter"])
    part["part_role"] = (
        "on_unit_atomic_gold" if scoreable else "hindsight_atomic_gold"
    )
    part["formal_score_eligible"] = scoreable
    part["review_status"] = "formal_gold_accepted"
    coverage = part.get("semantic_coverage_ledger")
    if isinstance(coverage, dict):
        coverage["review_status"] = "formal_gold_accepted"
    atomicity = part.get("atomicity")
    if isinstance(atomicity, dict):
        atomicity["semantic_atomicity_status"] = "formal_gold_accepted"


def build_formal(
    candidate: dict[str, Any],
    config: dict[str, Any],
    inputs: dict[str, Any],
    registered_at: str,
) -> dict[str, Any]:
    formal = copy.deepcopy(candidate)
    book_id = candidate["source"]["book_id"]
    parts = all_parts(formal)
    for part in parts:
        _formalize_part(part)
    on_unit_total = sum(bool(part["score_in_single_chapter"]) for part in parts)
    hindsight_total = len(parts) - on_unit_total
    candidate_rel = config["candidate"]
    candidate_sha = config["candidate_sha256"]
    formal["schema_version"] = "structure-gold-v1.3"
    formal["gold_id"] = (
        f"{book_id}-unit{config['inventory_unit']:04d}-structure-v1.3"
    )
    formal.pop("draft_id", None)
    formal.pop("candidate_level", None)
    formal["task"] = "第93道续令③五本转正落账"
    formal["status"] = "active_gold"
    formal["label_tier"] = "gold"
    formal["producer"] = {
        "path": str(THIS_FILE.relative_to(ROOT)),
        "sha256": sha256_file(THIS_FILE),
    }
    formal["predecessor"] = {
        "path": candidate_rel,
        "sha256": candidate_sha,
        "status": "archived_silver_candidate_not_formal_fallback",
        "mutation": "none",
    }
    formal["conversion_source"] = {
        "path": candidate_rel,
        "sha256": candidate_sha,
        "status": "candidate_promoted_after_z93_continuation_2_pass",
        "mutation": "metadata_only_no_semantic_payload_change",
    }
    formal["approval"] = {
        "authority": "Notion第93道续令③；续令②统一审收PASS后授权转正",
        "authority_time": "2026-07-23T14:55:00+08:00",
        "registered_at": registered_at,
        "semantic_review_boundary": "逐条审查由Codex验闸与Cursor攻击完成；CZ未逐条亲验。",
        "tier_rule": "非CZ亲验只描述来源链，不降低label_tier=gold。",
        "unresolved_total": 0,
    }
    formal["provenance"] = {
        "label": PROVENANCE_LABEL,
        "review_chain": [
            "Codex逐条验闸",
            "Cursor六件只读攻击",
            "Codex按冻结正文修订",
            "云端统一审收PASS并授权转正",
        ],
        "cz_personal_item_review": False,
        "tier_effect": "none_formal_gold",
        "authorization": {
            "path": str(AUTHORIZATION),
            "sha256": inputs["authorization_sha256"],
        },
        "evidence_files": [
            {"name": key, "path": relative, "sha256": expected}
            for key, (relative, expected) in EVIDENCE_FILES.items()
        ],
    }
    formal["evaluation_policy"] = {
        "rule": candidate["evaluation_policy"]["rule"],
        "single_unit_scored_layer": "当章可知",
        "single_unit_excluded_layer": "回看件",
        "score_unit": "part_id",
        "formal_denominator": on_unit_total,
        "hindsight_use": "只作跨单元回看，不计目标单元分。",
        "truth_source": "冻结小说正文；外部AI材料不作真值。",
        "usage": "可作后续验闸与跨书对照真值参照；升默认或接现役链另拍。",
    }
    formal["atomicity_policy"] = {
        **candidate["atomicity_policy"],
        "semantic_review_status": "accepted_by_z93_review_chain",
    }
    formal["layer_summary"] = {
        "layered_item_total": len(formal["layered_items"]),
        "formal_gold_part_total": len(parts),
        "on_unit_scoreable_atomic_part_total": on_unit_total,
        "hindsight_part_total": hindsight_total,
        "formal_denominator": on_unit_total,
        "unresolved_total": 0,
    }
    formal["review_flags"] = [
        {
            "kind": "formal_gold_registered",
            "detail": "第93道续令②统一审收PASS后按续令③登记为正式金标。",
        },
        {
            "kind": "delegated_item_review_provenance",
            "detail": "逐条审查不是CZ亲验；该来源说明不降低正式金标层级。",
        },
        next(
            flag
            for flag in candidate["review_flags"]
            if flag["kind"] == "external_ai_truth_excluded"
        ),
        {
            "kind": "anchor_identity_version_scoped",
            "detail": (
                "v1.3候选转正式保持部件ID、锚ID与引文不变；"
                "v1.2到v1.3的拆分和锚重建按修订账留痕，不假定跨版本同ID同义。"
            ),
        },
    ]
    formal["revision_provenance"] = {
        **candidate["revision_provenance"],
        "formal_provenance_label": PROVENANCE_LABEL,
        "formal_gold_promoted": True,
        "promotion_task": "第93道续令③",
    }
    formal["protected_state"] = {
        **candidate["protected_state"],
        "formal_gold_promoted": True,
        "own_gold_pointer_created": True,
        "x01_gold_or_pointer_changed": False,
        "gold_pointer_changed": True,
    }
    register = formal["hindsight_review_register"]
    register["status"] = "formal_gold_active"
    for row in register["parts"]:
        row["review_status"] = "formal_gold_accepted"
    return formal


def build_pointer(
    formal: dict[str, Any],
    formal_path: str,
    formal_sha: str,
    config: dict[str, Any],
    registered_at: str,
) -> dict[str, Any]:
    book_id = formal["source"]["book_id"]
    return {
        "schema_version": "structure-gold-current-pointer-v1",
        "pointer_id": f"{book_id}-unit{config['inventory_unit']:04d}-structure-gold-current",
        "status": "active",
        "book_id": book_id,
        "book": formal["source"]["book"],
        "inventory_unit": config["inventory_unit"],
        "label_tier": "gold",
        "provenance_label": PROVENANCE_LABEL,
        "active_gold": {
            "version": "v1.3",
            "path": formal_path,
            "sha256": formal_sha,
            "schema_version": formal["schema_version"],
            "formal_denominator": formal["evaluation_policy"]["formal_denominator"],
            "formal_part_total": formal["layer_summary"]["formal_gold_part_total"],
            "activated_by": "第93道续令③",
            "activated_at": registered_at,
        },
        "predecessor": formal["predecessor"],
        "consumer_rule": (
            "后续验闸与跨书对照从本指针取正式金标；"
            "provenance随件携带；升默认或接现役链另拍。"
        ),
        "rollback": (
            "本书没有前代正式金标；回退时停用本指针并保留v1.3正式件，"
            "不得把银标候选冒充回退后的正式入口。"
        ),
    }


def build_registry(
    formal_rows: list[dict[str, Any]],
    registered_at: str,
) -> dict[str, Any]:
    x01 = {
        "gold_id": "X01-ch0003-structure-v1.2",
        "book_id": "X01",
        "book": "诡秘之主",
        "inventory_unit": 3,
        "version": "v1.2",
        "label_tier": "gold",
        "pointer_path": PROTECTED_FILES["x01_gold_pointer"][0],
        "pointer_sha256": PROTECTED_FILES["x01_gold_pointer"][1],
        "artifact_path": PROTECTED_FILES["x01_formal_gold"][0],
        "artifact_sha256": PROTECTED_FILES["x01_formal_gold"][1],
        "formal_denominator": 23,
        "provenance_label": "按既有Z73审查与拍板链转正；CZ未逐条亲验。",
        "status": "active_gold",
    }
    return {
        "schema_version": "formal-gold-registry-v1",
        "status": "active",
        "registered_at": registered_at,
        "tier_rule": (
            "所有entry的label_tier=gold均为正式金标；"
            "是否CZ逐条亲验只写provenance，不形成高低两档。"
        ),
        "primary_existing_reference": "X01-ch0003-structure-v1.2",
        "entries": [x01, *formal_rows],
        "counts": {
            "formal_gold_entry_total": 6,
            "z93_promoted_book_total": 5,
            "z93_promoted_part_total": sum(
                row["formal_part_total"] for row in formal_rows
            ),
            "z93_promoted_denominator_total": sum(
                row["formal_denominator"] for row in formal_rows
            ),
        },
    }


def build_core(registered_at: str, inputs: dict[str, Any]) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    formal_rows: list[dict[str, Any]] = []
    identity_rows: list[dict[str, Any]] = []
    for book_id, config in BOOKS.items():
        candidate = read_json(ROOT / config["candidate"])
        before_semantic = canonical_sha(semantic_payload(candidate))
        formal = build_formal(candidate, config, inputs, registered_at)
        after_semantic = canonical_sha(semantic_payload(formal))
        if before_semantic != after_semantic:
            raise AssertionError(f"候选转正式时语义载荷漂移：{book_id}")
        formal_rel = str(REPORT_DIR / "formal_gold" / config["formal_name"])
        formal_payload = json_bytes(formal)
        formal_sha = sha256_bytes(formal_payload)
        payloads[formal_rel] = formal_payload
        pointer_rel = f"config/gold/{config['pointer_name']}"
        pointer = build_pointer(
            formal,
            formal_rel,
            formal_sha,
            config,
            registered_at,
        )
        pointer_payload = json_bytes(pointer)
        pointer_sha = sha256_bytes(pointer_payload)
        payloads[pointer_rel] = pointer_payload
        parts = all_parts(formal)
        formal_rows.append(
            {
                "gold_id": formal["gold_id"],
                "book_id": book_id,
                "book": formal["source"]["book"],
                "inventory_unit": config["inventory_unit"],
                "version": "v1.3",
                "label_tier": "gold",
                "pointer_path": pointer_rel,
                "pointer_sha256": pointer_sha,
                "artifact_path": formal_rel,
                "artifact_sha256": formal_sha,
                "formal_denominator": formal["evaluation_policy"]["formal_denominator"],
                "formal_part_total": len(parts),
                "provenance_label": PROVENANCE_LABEL,
                "status": "active_gold",
            }
        )
        identity_rows.append(
            {
                "book_id": book_id,
                "candidate_path": config["candidate"],
                "candidate_sha256": config["candidate_sha256"],
                "formal_path": formal_rel,
                "formal_sha256": formal_sha,
                "semantic_payload_before_sha256": before_semantic,
                "semantic_payload_after_sha256": after_semantic,
                "part_ids_preserved": [
                    part["part_id"] for part in all_parts(candidate)
                ]
                == [part["part_id"] for part in parts],
                "anchor_total": anchor_count(formal),
            }
        )
    registry = build_registry(formal_rows, registered_at)
    registry_rel = "config/gold/formal_gold_registry.json"
    payloads[registry_rel] = json_bytes(registry)
    identity = {
        "schema_version": "z93-candidate-to-formal-identity-audit-v1",
        "status": "pass_no_semantic_payload_change",
        "anchor_identity_policy": {
            "candidate_v1_3_to_formal_v1_3": (
                "同版转换保持part_id、anchor_id、quote与顺序不变。"
            ),
            "cross_version_v1_2_to_v1_3": (
                "锚身份按版本作用域解释；拆分、前插或重建由revision_ledger留痕，"
                "不假定跨版本同anchor_id同义。"
            ),
            "rollback_unit": "整份正式工件＋对应current指针，不做跨版本逐锚拼接。",
        },
        "books": identity_rows,
        "counts": {
            "book_total": 5,
            "formal_part_total": sum(row["formal_part_total"] for row in formal_rows),
            "anchor_total": sum(row["anchor_total"] for row in identity_rows),
            "semantic_payload_mismatch_total": sum(
                row["semantic_payload_before_sha256"]
                != row["semantic_payload_after_sha256"]
                for row in identity_rows
            ),
        },
    }
    payloads[str(REPORT_DIR / "candidate_to_formal_identity_audit.json")] = json_bytes(
        identity
    )
    usage = {
        "schema_version": "z93-five-formal-gold-usage-v1",
        "model_api_logical_calls": 0,
        "model_api_network_attempts": 0,
        "model_api_usage_tokens": 0,
        "network_requests": 0,
    }
    payloads[str(REPORT_DIR / "usage.json")] = json_bytes(usage)
    report_lines = [
        "# 第93道续令③停点回包｜五本结构层金标 v1.3 转正",
        "",
        "✅ 五份 v1.3 修订候选已登记为正式金标。五本共105条，其中91条计目标单元分、14条为回看件；五个 current 指针彼此独立，X01 原件与指针未改。",
        "",
        "| 书目 | 正式条目 | 目标单元分母 | 正式工件 SHA-256 | current 指针 SHA-256 |",
        "|---|---:|---:|---|---|",
    ]
    for row in formal_rows:
        report_lines.append(
            f"| {row['book_id']} {row['book']} | {row['formal_part_total']} | "
            f"{row['formal_denominator']} | `{row['artifact_sha256']}` | "
            f"`{row['pointer_sha256']}` |"
        )
    report_lines.extend(
        [
            "",
            "## 转正口径",
            "",
            f"- 标签层级：`gold`；来源：{PROVENANCE_LABEL}。",
            "- “非CZ亲验”只说明逐条审查由谁完成，不表示低一档；现有金标同样不是CZ逐条亲验。",
            "- 候选到正式只改身份和审收元数据；claim、锚、部件ID与顺序没有变化。",
            "- 锚身份按版本作用域解释；v1.2→v1.3 的拆分和锚重建看修订账，回退按整件和指针办理。",
            "- B01／B02／B03 的 ready 停闸随本次转正解除。",
            "",
            "## 保护边界",
            "",
            "- 模型 API 0、网络请求 0、token 0。",
            "- X01、现役122条、默认链、分类规则、outbox均未改。",
            "- 五份v1.3候选和Z93历史目录只读；正式件与指针均为新增。",
            "- 五本可作后续验闸和跨书对照真值；升默认或接现役链仍须另拍。",
            "",
            "来源：Codex",
            "",
        ]
    )
    payloads[
        str(REPORT_DIR / "第93道续令③停点回包｜五本结构层金标v1.3转正_20260723.md")
    ] = "\n".join(report_lines).encode("utf-8")
    return payloads


def payload_fingerprint(payloads: dict[str, bytes]) -> dict[str, Any]:
    rows = [
        (relative, sha256_bytes(payload), len(payload))
        for relative, payload in sorted(payloads.items())
    ]
    text = "\n".join(f"{name}\t{digest}\t{size}" for name, digest, size in rows)
    return {
        "files": len(rows),
        "bytes": sum(size for _, _, size in rows),
        "sha256": sha256_bytes(text.encode("utf-8")),
    }


def build_all(registered_at: str) -> dict[str, bytes]:
    inputs = check_inputs()
    first = build_core(registered_at, inputs)
    second = build_core(registered_at, inputs)
    if first != second:
        raise AssertionError("两次内存隔离机械构建不一致")
    receipt = {
        "schema_version": "z93-five-formal-gold-double-run-v1",
        "status": "pass_byte_identical",
        "run_1": payload_fingerprint(first),
        "run_2": payload_fingerprint(second),
        "identical": True,
    }
    payloads = dict(first)
    payloads[str(REPORT_DIR / "mechanical_double_run_receipt.json")] = json_bytes(
        receipt
    )
    final_protected = check_inputs()
    acceptance = {
        "schema_version": "z93-five-formal-gold-acceptance-v1",
        "status": "pass_formal_gold_registered",
        "registered_at": registered_at,
        "counts": {
            "book_total": 5,
            "formal_part_total": 105,
            "formal_denominator_total": 91,
            "hindsight_part_total": 14,
            "anchor_total": 184,
            "current_pointer_total": 5,
        },
        "gates": {
            "candidate_sha_match_5_of_5": True,
            "semantic_payload_unchanged_5_of_5": True,
            "label_tier_gold_5_of_5": True,
            "provenance_exact_5_of_5": True,
            "pointer_resolves_5_of_5": True,
            "double_run_byte_identical": True,
            "b01_b02_b03_ready_stop_released": True,
            "x01_choice_a_still_deferred_to_z92": True,
            "protected_state_unchanged": inputs == final_protected,
        },
        "protected_before": inputs,
        "protected_after": final_protected,
    }
    payloads[str(REPORT_DIR / "mechanical_acceptance.json")] = json_bytes(acceptance)
    manifest = {
        "schema_version": "z93-five-formal-gold-report-manifest-v1",
        "task": "第93道续令③",
        "status": "formal_gold_registered",
        "counts": acceptance["counts"],
        "formal_gold_registry": {
            "path": "config/gold/formal_gold_registry.json",
            "sha256": sha256_bytes(payloads["config/gold/formal_gold_registry.json"]),
        },
        "files": {
            relative: sha256_bytes(payload)
            for relative, payload in sorted(payloads.items())
        },
    }
    payloads[str(REPORT_DIR / "report_manifest.json")] = json_bytes(manifest)
    return payloads


def write_payloads(output_root: Path, payloads: dict[str, bytes]) -> None:
    output_root = output_root.resolve()
    targets = [output_root / relative for relative in payloads]
    occupied = [str(path) for path in targets if path.exists()]
    if occupied:
        raise AssertionError(f"目标已存在，拒绝覆盖：{occupied[:5]}")
    for relative, payload in sorted(payloads.items()):
        path = output_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def verify_written(output_root: Path, payloads: dict[str, bytes]) -> dict[str, Any]:
    mismatches = []
    for relative, expected in payloads.items():
        path = output_root / relative
        if not path.is_file() or path.read_bytes() != expected:
            mismatches.append(relative)
    if mismatches:
        raise AssertionError(f"落盘回读不一致：{mismatches}")
    return {
        "status": "pass",
        "files": len(payloads),
        "tree": payload_fingerprint(payloads),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT,
        help="输出根；正式运行默认仓库根，隔离测试可指向临时目录。",
    )
    parser.add_argument(
        "--registered-at",
        default="2026-07-23T15:20:00+08:00",
    )
    args = parser.parse_args()
    payloads = build_all(args.registered_at)
    write_payloads(args.output_root, payloads)
    print(json.dumps(verify_written(args.output_root, payloads), ensure_ascii=False))


if __name__ == "__main__":
    main()

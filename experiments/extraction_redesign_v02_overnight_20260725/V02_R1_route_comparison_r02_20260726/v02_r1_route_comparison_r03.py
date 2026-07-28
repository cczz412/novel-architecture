#!/usr/bin/env python3
"""R1 r03：只把热事实 JSON 外壳逐字段教给模型，其余冻结件继承 r02。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (  # noqa: E402
    v02_r1_route_comparison as r02,
)


RUN_DIR = REPO_ROOT / "runs" / "V02_R1_route_comparison_r03_20260726"
FROZEN_DIR = RUN_DIR / "frozen"


def hot_contract_text() -> str:
    return "\n".join(
        [
            "# R1 热事实范围合同 v0.1",
            "",
            "你只看当前冻结范围，不得使用范围之外或本章之后的知识。",
            "只抽取下列八类会被后续大纲编辑继续查询的热事实：",
            *[f"- {item}" for item in r02.HOT_TYPES],
            "",
            "每条只写一个业务原子：只承担一个可独立查询、独立改状态、独立判真假的更新。",
            "主体、变化、对象和否定／未然／推断限定要齐。",
            "只能引用当前范围给出的 source ID，不输出原文短引，程序按 ID 逐字回填。",
            "不属于八类的冷事实不写进 facts，只登记相关 source ID 到 cold_index。",
            "没有的类型留空，不设条数下限，不得凑数。",
            "",
            "顶层只允许五个字段：schema_version、chapter、scope_id、facts、cold_index。",
            "八类名称只能写在 facts[].category，禁止把八类名称做成顶层字段。",
            "facts 和 cold_index 都必须是数组；禁止增加 range_id、source_dir_sha 或其他字段。",
            "只输出一个 JSON 对象，不要解释或代码围栏。外壳逐字段照下面写：",
            "",
            "```json",
            "{",
            '  "schema_version": "v02-r1-hot-material.v1",',
            '  "chapter": 33,',
            '  "scope_id": "B01-U0033-FULL",',
            '  "facts": [',
            "    {",
            '      "fact_id": "F001",',
            '      "statement": "某人物形成了一个以后需要兑现的计划。",',
            '      "category": "GOAL_PLAN_PROMISE_THREAT",',
            '      "actuality": "PLANNED",',
            '      "source_ids": ["B01-U0033-S0001"]',
            "    }",
            "  ],",
            '  "cold_index": [',
            "    {",
            '      "source_id": "B01-U0033-S0002",',
            '      "reason": "COLD_DETAIL_NOT_IN_LEDGER"',
            "    }",
            "  ]",
            "}",
            "```",
            "",
            "示例只教字段关系，不是当前章答案；当前章号、scope_id 和 source ID 必须用下方实物。",
        ]
    )


def render_hot_user(case_id: str, scope: Mapping[str, Any]) -> str:
    catalog = r02.source_catalog(case_id)
    by_id = {row["sentence_id"]: row for row in catalog["sentences"]}
    visible = [
        {"source_id": source_id, "text": by_id[source_id]["original_text"]}
        for source_id in scope["source_ids"]
    ]
    return "\n".join(
        [
            hot_contract_text(),
            "",
            f"当前章号：{r02.CASE_CHAPTERS[case_id]}",
            f"当前范围 ID：{scope['scope_id']}",
            f"当前来源目录 SHA：{catalog['catalog_sha256']}",
            "",
            "当前冻结范围：",
            "```json",
            json.dumps(visible, ensure_ascii=False, separators=(",", ":")),
            "```",
        ]
    )


def frozen_requests() -> list[dict[str, Any]]:
    rows = r02.frozen_requests()
    for row in rows:
        if row["contract"] == "HOT_FACTS_V0":
            case_id = row["case_id"]
            if row["scope_id"].endswith("-FULL"):
                source_ids = [
                    item["sentence_id"]
                    for item in r02.source_catalog(case_id)["sentences"]
                ]
            else:
                source_ids = next(
                    item["source_ids"]
                    for item in r02.two_chunks(case_id)
                    if item["scope_id"] == row["scope_id"]
                )
            row["body"]["messages"][1]["content"] = render_hot_user(
                case_id,
                {"scope_id": row["scope_id"], "source_ids": source_ids},
            )
            row["request_sha256"] = r02.canonical_sha(row["body"])
            row["contract"] = "HOT_FACTS_V0_1_EXPLICIT_JSON_SHELL"
    return rows


def preregistration() -> dict[str, Any]:
    value = r02.preregistration()
    requests = frozen_requests()
    value["schema_version"] = "v02-r1-route-comparison-preregistration.v3"
    value["authority"]["revision"] = (
        "修正令② 2026-07-26 20:45；r02 热事实 JSON 外壳教学缺口工程修正"
    )
    value["engineering_delta_from_r02"] = [
        "HOT_CONTRACT_SHOWS_EXACT_JSON_SHELL",
        "TRANSPORT_USES_PROVIDER_BOUNDED_429_RETRY",
        "UNCHANGED_A_ACCEPTED_CELL_REUSED_WITH_SHA_PROOF",
    ]
    value["requests"] = [
        {
            key: row[key]
            for key in (
                "call_id",
                "route_id",
                "case_id",
                "scope_id",
                "contract",
                "request_sha256",
            )
        }
        for row in requests
    ]
    value["preregistration_sha256"] = ""
    value["preregistration_sha256"] = r02.canonical_sha(
        {k: v for k, v in value.items() if k != "preregistration_sha256"}
    )
    return value


def build_artifacts() -> dict[str, bytes]:
    artifacts: dict[str, bytes] = {
        "preregistration.json": r02.json_bytes(preregistration()),
        "question_reference_map.lockbox.json": r02.json_bytes(
            r02.question_reference_map()
        ),
        "schemas/z_event_v1.schema.json": r02.json_bytes(
            r02.z00l_output_schema()
        ),
        "schemas/hot_material_v1.schema.json": r02.json_bytes(
            r02.hot_output_schema()
        ),
        "contracts/z00l_prompt_exact.md": r02.Z00L_PROMPT_PATH.read_bytes(),
        "contracts/z_event_v1_exact.md": r02.Z00L_CONTRACT_PATH.read_bytes(),
        "contracts/hot_facts_v0_1.md": (
            hot_contract_text() + "\n\n来源：Codex\n"
        ).encode("utf-8"),
    }
    for row in frozen_requests():
        artifacts[f"requests/{row['call_id']}.json"] = r02.json_bytes(row)
    manifest = {
        "schema_version": "v02-r1-route-comparison-manifest.v2",
        "candidate_status": "candidate_silver_not_active",
        "model_api_calls": 0,
        "network_requests": 0,
        "git_commit_or_push": False,
        "artifacts": {
            path: hashlib.sha256(raw).hexdigest()
            for path, raw in sorted(artifacts.items())
        },
        "artifact_tree_sha256": "",
    }
    manifest["artifact_tree_sha256"] = r02.canonical_sha(
        manifest["artifacts"]
    )
    artifacts["manifest.json"] = r02.json_bytes(manifest)
    return artifacts


def write_artifacts(output_dir: Path = FROZEN_DIR) -> dict[str, Any]:
    artifacts = build_artifacts()
    for relative, raw in artifacts.items():
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    manifest = json.loads(artifacts["manifest.json"])
    return {
        "status": "FROZEN_R03_EXECUTE_ALLOWED",
        "artifact_tree_sha256": manifest["artifact_tree_sha256"],
        "request_count": 12,
        "execute_allowed": True,
    }


if __name__ == "__main__":
    print(json.dumps(write_artifacts(), ensure_ascii=False, indent=2))

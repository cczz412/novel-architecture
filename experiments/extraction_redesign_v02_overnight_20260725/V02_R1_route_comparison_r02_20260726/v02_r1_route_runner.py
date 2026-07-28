#!/usr/bin/env python3
"""执行 R1 三路线冻结请求，并用锁箱内 30 格真源离线计分。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (  # noqa: E402
    v02_r1_route_comparison as spec,
)


RUN_DIR = spec.RUN_DIR
FROZEN_DIR = RUN_DIR / "frozen"
EXECUTION_DIR = RUN_DIR / "execution"
RESULT_DIR = RUN_DIR / "result"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen_tree() -> dict[str, Any]:
    manifest = read_json(FROZEN_DIR / "manifest.json")
    failures = []
    for relative, expected in manifest["artifacts"].items():
        path = FROZEN_DIR / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            failures.append(
                {"path": relative, "expected": expected, "actual": actual}
            )
    requests = sorted((FROZEN_DIR / "requests").glob("*.json"))
    if len(requests) != 12:
        failures.append(
            {"path": "requests", "expected": 12, "actual": len(requests)}
        )
    prereg = read_json(FROZEN_DIR / "preregistration.json")
    if not prereg["network_authorization"]["execute_allowed"]:
        failures.append(
            {
                "path": "preregistration.network_authorization",
                "expected": True,
                "actual": False,
            }
        )
    for path in requests:
        row = read_json(path)
        actual = spec.canonical_sha(row["body"])
        if actual != row["request_sha256"]:
            failures.append(
                {
                    "path": str(path.relative_to(FROZEN_DIR)),
                    "expected": row["request_sha256"],
                    "actual": actual,
                }
            )
    return {
        "status": "PASS" if not failures else "FAIL",
        "artifact_tree_sha256": manifest["artifact_tree_sha256"],
        "request_count": len(requests),
        "failures": failures,
    }


def secret_trace_scan() -> dict[str, Any]:
    patterns = ("sk-", "Bearer ", '"Authorization"')
    matches = []
    for path in sorted(RUN_DIR.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in patterns:
            if pattern in text:
                matches.append(
                    {
                        "path": str(path.relative_to(spec.REPO_ROOT)),
                        "pattern": pattern,
                    }
                )
    return {"match_count": len(matches), "matches": matches}


def send_once(body: Mapping[str, Any], api_key: str) -> tuple[dict[str, Any], float]:
    provider = read_json(spec.PROVIDER_CONFIG_PATH)
    url = provider["base_url"].rstrip("/") + provider["endpoint"]
    payload = spec.canonical_bytes(body)
    request = urllib.request.Request(
        url,
        method="POST",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    started = time.monotonic()
    with urllib.request.urlopen(
        request, timeout=int(provider["timeout_seconds"])
    ) as response:
        raw = response.read()
        status = int(response.status)
    elapsed = time.monotonic() - started
    if status != 200:
        raise RuntimeError(f"HTTP {status}")
    return json.loads(raw.decode("utf-8")), elapsed


def extract_content(response: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("响应 choices 不是单项数组")
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        raise ValueError("响应缺 message")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("响应 content 不是字符串")
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        usage = {}
    return content, dict(usage)


def strict_json(content: str) -> Any:
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("模型输出不是 JSON 对象")
    return value


def schema_for(row: Mapping[str, Any]) -> dict[str, Any]:
    if row["contract"] == "CURRENT_Z00L_EXACT":
        return read_json(FROZEN_DIR / "schemas" / "z_event_v1.schema.json")
    return read_json(FROZEN_DIR / "schemas" / "hot_material_v1.schema.json")


def validate_semantic_shape(row: Mapping[str, Any], value: Mapping[str, Any]) -> None:
    if row["contract"] == "CURRENT_Z00L_EXACT":
        events = value["events"]
        event_ids = [item["event_id"] for item in events]
        if value["coverage_audit"]["event_ids"] != event_ids:
            raise ValueError("coverage_audit.event_ids 与 events 不一致")
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("事件 ID 重复")
    else:
        if value["scope_id"] != row["scope_id"]:
            raise ValueError("scope_id 漂移")
        fact_ids = [item["fact_id"] for item in value["facts"]]
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("事实 ID 重复")


def execute() -> dict[str, Any]:
    preflight = verify_frozen_tree()
    if preflight["status"] != "PASS":
        raise RuntimeError("冻结树复验失败，拒绝发网")
    api_key = os.environ.get("SENSENOVA_API_KEY")
    if not api_key:
        raise RuntimeError("当前进程缺 SENSENOVA_API_KEY")
    if len(list((FROZEN_DIR / "requests").glob("*.json"))) > 500:
        raise RuntimeError("请求数超过 500 次硬上限")
    write_json(EXECUTION_DIR / "preflight.json", preflight)
    calls = []
    for index, request_path in enumerate(
        sorted((FROZEN_DIR / "requests").glob("*.json")), start=1
    ):
        row = read_json(request_path)
        call_dir = EXECUTION_DIR / "calls" / row["call_id"]
        if (call_dir / "receipt.json").is_file():
            calls.append(read_json(call_dir / "receipt.json"))
            continue
        call_dir.mkdir(parents=True, exist_ok=True)
        write_json(call_dir / "request.json", row)
        receipt: dict[str, Any] = {
            "call_id": row["call_id"],
            "route_id": row["route_id"],
            "case_id": row["case_id"],
            "scope_id": row["scope_id"],
            "request_sha256": row["request_sha256"],
            "network_attempts": 1,
            "sequence": index,
            "status": "STARTED",
        }
        try:
            response, elapsed = send_once(row["body"], api_key)
            write_json(call_dir / "raw_response.json", response)
            receipt["response_sha256"] = sha256_file(
                call_dir / "raw_response.json"
            )
            receipt["elapsed_seconds"] = elapsed
            receipt["response_model"] = response.get("model")
            if response.get("model") not in (None, "deepseek-v4-flash"):
                raise ValueError(f"响应型号漂移：{response.get('model')}")
            content, usage = extract_content(response)
            (call_dir / "raw_content.txt").write_text(content, encoding="utf-8")
            receipt["raw_content_sha256"] = sha256_file(
                call_dir / "raw_content.txt"
            )
            write_json(call_dir / "usage.json", usage)
            receipt["usage"] = usage
            value = strict_json(content)
            jsonschema.Draft202012Validator(schema_for(row)).validate(value)
            validate_semantic_shape(row, value)
            write_json(call_dir / "parsed.json", value)
            receipt["finish_reason"] = response["choices"][0].get(
                "finish_reason"
            )
            if receipt["finish_reason"] != "stop":
                raise ValueError(
                    f"finish_reason={receipt['finish_reason']}，拒收该格"
                )
            receipt["status"] = "ACCEPTED"
        except urllib.error.HTTPError as error:
            receipt["status"] = "TRANSPORT_HARD_STOP"
            receipt["http_status"] = error.code
            receipt["error"] = str(error)
            write_json(call_dir / "receipt.json", receipt)
            calls.append(receipt)
            break
        except Exception as error:  # 质量差或结构差记负成绩，继续批次
            receipt["status"] = "REJECTED_NEGATIVE_SCORE_CONTINUE"
            receipt["error"] = f"{type(error).__name__}: {error}"
        write_json(call_dir / "receipt.json", receipt)
        calls.append(receipt)
    result = {
        "schema_version": "v02-r1-execution-receipt.v1",
        "call_total_planned": 12,
        "call_total_recorded": len(calls),
        "accepted": sum(row["status"] == "ACCEPTED" for row in calls),
        "rejected": sum(
            row["status"] == "REJECTED_NEGATIVE_SCORE_CONTINUE"
            for row in calls
        ),
        "transport_hard_stops": sum(
            row["status"] == "TRANSPORT_HARD_STOP" for row in calls
        ),
        "calls": calls,
        "secret_trace_scan": secret_trace_scan(),
    }
    write_json(EXECUTION_DIR / "execution_receipt.json", result)
    return result


def normalize_materials() -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for path in sorted((EXECUTION_DIR / "calls").glob("*/receipt.json")):
        receipt = read_json(path)
        if receipt["status"] != "ACCEPTED":
            continue
        call_dir = path.parent
        request = read_json(call_dir / "request.json")
        parsed = read_json(call_dir / "parsed.json")
        if request["contract"] == "CURRENT_Z00L_EXACT":
            for item in parsed["events"]:
                grouped[request["route_id"]][request["case_id"]].append(
                    {
                        "material_id": item["event_id"],
                        "statement": item["event"],
                        "source_ids": [
                            anchor["anchor_id"] for anchor in item["anchors"]
                        ],
                        "kind": "FACT",
                    }
                )
        else:
            for item in parsed["facts"]:
                grouped[request["route_id"]][request["case_id"]].append(
                    {
                        "material_id": (
                            f"{request['scope_id']}::{item['fact_id']}"
                        ),
                        "statement": item["statement"],
                        "source_ids": item["source_ids"],
                        "kind": "FACT",
                        "actuality": item["actuality"],
                        "category": item["category"],
                    }
                )
            for item in parsed["cold_index"]:
                grouped[request["route_id"]][request["case_id"]].append(
                    {
                        "material_id": (
                            f"{request['scope_id']}::COLD::{item['source_id']}"
                        ),
                        "statement": "",
                        "source_ids": [item["source_id"]],
                        "kind": "COLD_POINTER",
                    }
                )
    return grouped


def cell_score(
    cell: Mapping[str, Any],
    materials: Iterable[Mapping[str, Any]],
    known_ids: set[str],
) -> dict[str, Any]:
    rows = list(materials)
    available = {
        source_id
        for row in rows
        if row["kind"] == "FACT"
        for source_id in row["source_ids"]
        if source_id in known_ids
    }
    invalid = sorted(
        {
            source_id
            for row in rows
            for source_id in row["source_ids"]
            if source_id not in known_ids
        }
    )
    if cell["expected"] == "OPEN":
        return {
            "cell_id": cell["cell_id"],
            "answerable": True,
            "expected": "OPEN",
            "missing_part_ids": [],
            "critical_errors": [
                {"code": "INVALID_SOURCE_ID", "source_id": value}
                for value in invalid
            ],
        }
    missing = []
    for part in cell["required_parts"]:
        if not all(set(group) & available for group in part["source_id_groups"]):
            missing.append(part["part_id"])
    errors = [
        {"code": "INVALID_SOURCE_ID", "source_id": value} for value in invalid
    ]
    for part in cell["required_parts"]:
        part_ids = set().union(
            *(set(group) for group in part["source_id_groups"])
        )
        fact_rows = [
            row
            for row in rows
            if row["kind"] == "FACT" and part_ids & set(row["source_ids"])
        ]
        for row in fact_rows:
            statement = row["statement"]
            if part["must_retain_uncertainty"] and not any(
                marker in statement for marker in spec.UNCERTAINTY_MARKERS
            ):
                errors.append(
                    {
                        "code": "UNCERTAINTY_UPGRADED",
                        "part_id": part["part_id"],
                        "material_id": row["material_id"],
                    }
                )
            if part["must_retain_negation"] and not any(
                marker in statement for marker in spec.NEGATION_MARKERS
            ):
                errors.append(
                    {
                        "code": "NEGATION_LOST",
                        "part_id": part["part_id"],
                        "material_id": row["material_id"],
                    }
                )
    return {
        "cell_id": cell["cell_id"],
        "answerable": not missing,
        "expected": "ANSWERED",
        "missing_part_ids": missing,
        "critical_errors": errors,
    }


def usage_material_tokens(usage: Mapping[str, Any]) -> int | None:
    completion = usage.get("completion_tokens")
    if not isinstance(completion, int):
        return None
    details = usage.get("completion_tokens_details")
    reasoning = (
        details.get("reasoning_tokens")
        if isinstance(details, Mapping)
        else 0
    )
    if not isinstance(reasoning, int):
        reasoning = 0
    return completion - reasoning


def score() -> dict[str, Any]:
    reference = read_json(FROZEN_DIR / "question_reference_map.lockbox.json")
    materials = normalize_materials()
    route_scores = {}
    for route_id in (
        "A_FULL_ONCE_Z00L",
        "B_HOT_FULL_ONCE",
        "C_HOT_TWO_CHUNKS",
    ):
        cells = []
        for cell in reference["cells"]:
            case_id = cell["case_id"]
            known = {
                row["sentence_id"]
                for row in spec.source_catalog(case_id)["sentences"]
            }
            cells.append(
                cell_score(cell, materials[route_id][case_id], known)
            )
        call_receipts = []
        for path in sorted((EXECUTION_DIR / "calls").glob("*/receipt.json")):
            receipt = read_json(path)
            if receipt["route_id"] == route_id:
                call_receipts.append(receipt)
        material_tokens = [
            usage_material_tokens(row.get("usage") or {})
            for row in call_receipts
            if row["status"] == "ACCEPTED"
        ]
        route_scores[route_id] = {
            "answerable_cells": sum(row["answerable"] for row in cells),
            "cell_total": 30,
            "critical_errors": sum(
                len(row["critical_errors"]) for row in cells
            )
            + sum(row["status"] != "ACCEPTED" for row in call_receipts),
            "material_rows": sum(
                len(case_rows)
                for case_rows in materials[route_id].values()
            ),
            "fact_rows": sum(
                row["kind"] == "FACT"
                for case_rows in materials[route_id].values()
                for row in case_rows
            ),
            "cold_pointer_rows": sum(
                row["kind"] == "COLD_POINTER"
                for case_rows in materials[route_id].values()
                for row in case_rows
            ),
            "material_output_tokens": (
                sum(value for value in material_tokens if value is not None)
                if material_tokens
                and all(value is not None for value in material_tokens)
                else None
            ),
            "api_calls": len(call_receipts),
            "accepted_calls": sum(
                row["status"] == "ACCEPTED" for row in call_receipts
            ),
            "elapsed_seconds": sum(
                float(row.get("elapsed_seconds") or 0)
                for row in call_receipts
            ),
            "cells": cells,
        }
    baseline = route_scores["A_FULL_ONCE_Z00L"]
    comparisons = {}
    for route_id in ("B_HOT_FULL_ONCE", "C_HOT_TWO_CHUNKS"):
        candidate = route_scores[route_id]
        row_reduction = (
            1 - candidate["material_rows"] / baseline["material_rows"]
            if baseline["material_rows"]
            else None
        )
        token_reduction = (
            1
            - candidate["material_output_tokens"]
            / baseline["material_output_tokens"]
            if baseline["material_output_tokens"]
            and candidate["material_output_tokens"] is not None
            else None
        )
        gates = {
            "answerable_not_lower": (
                candidate["answerable_cells"] >= baseline["answerable_cells"]
            ),
            "critical_errors_not_higher": (
                candidate["critical_errors"] <= baseline["critical_errors"]
            ),
            "material_rows_reduce_30pct": (
                row_reduction is not None and row_reduction >= 0.30
            ),
            "material_tokens_reduce_30pct": (
                token_reduction is not None and token_reduction >= 0.30
            ),
        }
        comparisons[route_id] = {
            "material_row_reduction": row_reduction,
            "material_output_token_reduction": token_reduction,
            "gates": gates,
            "winner_against_A": all(gates.values()),
        }
    result = {
        "schema_version": "v02-r1-route-scorecard.v1",
        "candidate_status": "PROVISIONAL_AI_DOWNSTREAM",
        "quality_boundary": (
            "可回答性按冻结正式金标 source ID 覆盖机械计；关键错误是 schema、"
            "非法 ID、不确定性升级、否定丢失的下限，不冒充穷尽语义错误。"
        ),
        "route_scores": route_scores,
        "comparisons_against_A": comparisons,
        "recommended_routes": [
            route_id
            for route_id, row in comparisons.items()
            if row["winner_against_A"]
        ],
        "git_pushed": False,
        "formal_gold_model_visible": False,
        "secret_trace_scan": secret_trace_scan(),
    }
    write_json(RESULT_DIR / "scorecard.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("preflight", "execute", "score", "run")
    )
    args = parser.parse_args()
    if args.command == "preflight":
        result = verify_frozen_tree()
    elif args.command == "execute":
        result = execute()
    elif args.command == "score":
        result = score()
    else:
        result = execute()
        if result["call_total_recorded"] == 12 and not result[
            "transport_hard_stops"
        ]:
            result = {"execution": result, "scorecard": score()}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""R1 r03 执行入口：复用未变化的 A 首格，并给 429/断流做有界同请求重试。"""

from __future__ import annotations

import http.client
import json
import shutil
import sys
import time
import urllib.error
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (  # noqa: E402
    v02_r1_route_comparison_r03 as spec,
)
from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (  # noqa: E402
    v02_r1_route_runner as runner,
)


R02_RUN_DIR = REPO_ROOT / "runs" / "V02_R1_route_comparison_r02_20260726"
RUN_DIR = spec.RUN_DIR
FROZEN_DIR = RUN_DIR / "frozen"
EXECUTION_DIR = RUN_DIR / "execution"
RESULT_DIR = RUN_DIR / "result"
ATTEMPTS_BY_REQUEST_SHA: dict[str, int] = {}


def bounded_send(
    body: Mapping[str, Any], api_key: str
) -> tuple[dict[str, Any], float]:
    total_elapsed = 0.0
    request_sha = spec.r02.canonical_sha(body)
    for attempt in range(1, 4):
        ATTEMPTS_BY_REQUEST_SHA[request_sha] = attempt
        try:
            response, elapsed = ORIGINAL_SEND_ONCE(body, api_key)
            return response, total_elapsed + elapsed
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 3:
                raise
            time.sleep(5 if attempt == 1 else 10)
            total_elapsed += 5 if attempt == 1 else 10
        except (http.client.IncompleteRead, ConnectionResetError):
            if attempt == 3:
                raise
            time.sleep(5 if attempt == 1 else 10)
            total_elapsed += 5 if attempt == 1 else 10
    raise RuntimeError("不可达分支")


def reconcile_attempts() -> None:
    for path in sorted((EXECUTION_DIR / "calls").glob("*/receipt.json")):
        receipt = runner.read_json(path)
        if receipt.get("reused_from"):
            continue
        attempts = ATTEMPTS_BY_REQUEST_SHA.get(receipt["request_sha256"])
        if attempts is None:
            continue
        receipt["network_attempts"] = attempts
        receipt["network_attempts_this_run"] = attempts
        runner.write_json(path, receipt)


def seed_unchanged_a_cell() -> dict[str, Any]:
    call_id = "R1-01-A_FULL_ONCE_Z00L-B01-U0033-FULL"
    source = R02_RUN_DIR / "execution" / "calls" / call_id
    target = EXECUTION_DIR / "calls" / call_id
    old_request = runner.read_json(source / "request.json")
    new_request = runner.read_json(FROZEN_DIR / "requests" / f"{call_id}.json")
    if old_request["request_sha256"] != new_request["request_sha256"]:
        raise RuntimeError("A 首格请求 SHA 已变，禁止复用")
    if runner.sha256_file(source / "parsed.json") == "":
        raise RuntimeError("A 首格 parsed 缺失")
    if target.exists():
        return runner.read_json(target / "receipt.json")
    shutil.copytree(source, target)
    receipt = runner.read_json(target / "receipt.json")
    receipt["reused_from"] = str(source.relative_to(REPO_ROOT))
    receipt["network_attempts_this_run"] = 0
    receipt["reuse_reason"] = "UNCHANGED_REQUEST_SHA_SINGLE_EXISTING_RESULT"
    runner.write_json(target / "receipt.json", receipt)
    return receipt


def configure_runner() -> None:
    runner.spec = spec.r02
    runner.RUN_DIR = RUN_DIR
    runner.FROZEN_DIR = FROZEN_DIR
    runner.EXECUTION_DIR = EXECUTION_DIR
    runner.RESULT_DIR = RESULT_DIR
    runner.send_once = bounded_send


ORIGINAL_SEND_ONCE = runner.send_once


def main() -> int:
    spec.write_artifacts()
    configure_runner()
    seed = seed_unchanged_a_cell()
    result = runner.execute()
    reconcile_attempts()
    result = runner.read_json(EXECUTION_DIR / "execution_receipt.json")
    result["calls"] = [
        runner.read_json(path)
        for path in sorted((EXECUTION_DIR / "calls").glob("*/receipt.json"))
    ]
    runner.write_json(EXECUTION_DIR / "execution_receipt.json", result)
    output: dict[str, Any] = {"seed": seed, "execution": result}
    if result["call_total_recorded"] == 12 and not result[
        "transport_hard_stops"
    ]:
        output["scorecard"] = runner.score()
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

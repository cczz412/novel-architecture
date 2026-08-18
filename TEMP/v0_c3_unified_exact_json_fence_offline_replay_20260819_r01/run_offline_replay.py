from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from unified_normalize_and_validate import (
    UnifiedContractError,
    normalize_and_validate,
    unwrap_content,
)


ROOT = Path(__file__).resolve().parent
INPUT_FREEZE = ROOT / "INPUT_FREEZE_R01.json"
FIXTURES = ROOT / "SYNTHETIC_FIXTURE_CASES_R01.json"
SYNTHETIC_INPUT = Path(
    "/Users/a1234/挣钱/小说架构/TEMP/"
    "v0_c3_output_contract_handshake_preflight_20260818_r01/SYNTHETIC_INPUT_R01.json"
)
RAW_FILES = {
    "DOUBAO": Path(
        "/Users/a1234/挣钱/小说架构/TEMP/"
        "v0_c3_output_contract_handshake_two_call_20260818_r01/run/raw/"
        "DOUBAO.arkcli.raw.json"
    ),
    "FLASH": Path(
        "/Users/a1234/挣钱/小说架构/TEMP/"
        "v0_c3_output_contract_handshake_two_call_20260818_r01/run/raw/"
        "FLASH.arkcli.raw.json"
    ),
}
EXPECTED_MODELS = {
    "DOUBAO": "doubao-seed-2-1-turbo-260628",
    "FLASH": "deepseek-v4-flash-ga-260731",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs() -> None:
    freeze = json.loads(INPUT_FREEZE.read_text(encoding="utf-8"))
    for item in freeze["sources"]:
        path = Path(item["path"])
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise RuntimeError(f"INPUT_DRIFT:{path}")


def fenced(payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return f"```json\n{body}\n```"


def build_fixture(builder: str, route: str, actual_content: str) -> str:
    actual = unwrap_content(actual_content)
    payload = copy.deepcopy(actual.payload)
    if builder == "ACTUAL_CONTENT":
        return actual_content
    if builder == "NAKED_PAYLOAD":
        return actual.payload_text
    if builder == "OUTSIDE_PREFIX":
        return "说明：" + actual_content
    if builder == "OUTSIDE_SUFFIX":
        return actual_content + "\n说明"
    if builder == "UPPERCASE_TAG":
        return actual_content.replace("```json", "```JSON", 1)
    if builder == "NO_LANGUAGE_TAG":
        return actual_content.replace("```json", "```", 1)
    if builder == "DOUBLE_FENCE":
        return f"```json\n{actual_content}\n```"
    if builder == "BAD_JSON":
        return "```json\n{\"identity\":\n```"
    if builder == "IDENTITY_WRONG":
        payload["identity"] = "T03_OUTPUT_CONTRACT_HANDSHAKE_FLASH_R01"
        return fenced(payload)
    if builder == "TOP_FIELD_MISSING":
        del payload["truth_writes"]
        return fenced(payload)
    if builder == "TOP_FIELD_EXTRA":
        payload["explanation"] = "forbidden"
        return fenced(payload)
    raise KeyError((builder, route))


def replay_actuals() -> list[dict]:
    rows = []
    input_sha = sha256(SYNTHETIC_INPUT)
    for route in ("DOUBAO", "FLASH"):
        raw_path = RAW_FILES[route]
        raw_bytes = raw_path.read_bytes()
        wrapper = json.loads(raw_bytes)
        if wrapper.get("model") != EXPECTED_MODELS[route]:
            raise RuntimeError(f"MODEL_IDENTITY:{route}")
        content = wrapper.get("content")
        if not isinstance(content, str):
            raise RuntimeError(f"CONTENT_IDENTITY:{route}")
        accepted = normalize_and_validate(content, route, input_sha)
        rows.append(
            {
                "route": route,
                "raw_path": str(raw_path),
                "raw_bytes": len(raw_bytes),
                "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "response_model": wrapper["model"],
                "content_bytes": len(content.encode("utf-8")),
                "content_sha256": accepted.content_sha256,
                "transport_shape": accepted.transport_shape,
                "payload_bytes": len(accepted.payload_text.encode("utf-8")),
                "payload_sha256": accepted.payload_sha256,
                "rewrap_exact": accepted.rewrap_exact,
                "field_or_value_mutation": False,
                "same_validator_pass": True,
                "replay": "PASS",
            }
        )
    return rows


def run_fixtures() -> list[dict]:
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]
    wrappers = {
        route: json.loads(path.read_text(encoding="utf-8"))
        for route, path in RAW_FILES.items()
    }
    input_sha = sha256(SYNTHETIC_INPUT)
    rows = []
    for case in cases:
        content = build_fixture(
            case["builder"], case["route"], wrappers[case["route"]]["content"]
        )
        observed = "PASS"
        error = None
        shape = None
        try:
            accepted = normalize_and_validate(content, case["route"], input_sha)
            shape = accepted.transport_shape
        except (UnifiedContractError, ValueError) as exc:
            observed = "REJECT"
            error = str(exc)
        ok = observed == case["expected"]
        if observed == "PASS":
            ok = ok and shape == case["expected_shape"]
        else:
            ok = ok and error == case["expected_error"]
        rows.append(
            {
                "case_id": case["case_id"],
                "route": case["route"],
                "expected": case["expected"],
                "observed": observed,
                "transport_shape": shape,
                "error": error,
                "pass": ok,
                "normalizer_path": "unified_normalize_and_validate.unwrap_content",
                "validator_path": "frozen_preflight.validate_candidate",
            }
        )
    return rows


def main() -> None:
    verify_inputs()
    replay = replay_actuals()
    fixtures = run_fixtures()
    result = {
        "identity": "T03_UNIFIED_EXACT_JSON_FENCE_OFFLINE_REPLAY_RESULT_R01",
        "api_calls": 0,
        "model_calls": 0,
        "retries": 0,
        "ability_scoring": False,
        "actual_replay": replay,
        "actual_routes_passed": sum(row["replay"] == "PASS" for row in replay),
        "actual_routes_total": len(replay),
        "fixtures": fixtures,
        "fixture_cases_passed": sum(row["pass"] for row in fixtures),
        "fixture_cases_total": len(fixtures),
        "all_pass": all(row["replay"] == "PASS" for row in replay)
        and all(row["pass"] for row in fixtures),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not result["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

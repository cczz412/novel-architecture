#!/usr/bin/env python3
# Clean rerun only; the registered flaky set remains unchanged.
"""Run the fixed L3 materializer with safe template substitution.

The full L3 payload is frozen in commit 6b626721. Its validator and test
templates contain runtime f-string braces, so using ``str.format`` interprets
names such as ``case`` and ``field`` too early. This wrapper loads that payload,
removes only its final executable entry point, substitutes only declared build
tokens, and runs the unchanged apply/verify command selected by the workflow.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

THIS_FILE = Path(__file__).resolve()
PAYLOAD_COMMIT = "6b626721f5b2c910e603b088cece9f9df223d685"
source = subprocess.check_output(
    ["git", "show", f"{PAYLOAD_COMMIT}:.github/ledger_l3_apply.py"],
    text=True,
)
entrypoint = '\nif __name__ == "__main__":\n    raise SystemExit(main())'
position = source.rfind(entrypoint)
if position < 0 or source[position:].strip() != entrypoint.strip():
    raise SystemExit("L3_FINAL_PAYLOAD_ENTRYPOINT_NOT_FOUND")
source = source[:position] + source[position + len(entrypoint) :]
namespace: dict[str, object] = {
    "__name__": "ledger_l3_payload",
    "__file__": str(THIS_FILE),
}
exec(compile(source, "ledger_l3_payload.py", "exec"), namespace)


def replace_declared_tokens(
    text: str,
    replacements: tuple[tuple[str, Any], ...],
    *,
    label: str,
) -> str:
    for token, value in replacements:
        if token not in text:
            raise SystemExit(f"L3_TEMPLATE_TOKEN_MISSING:{label}:{token}")
        text = text.replace(token, str(value))
    unresolved = [token for token, _ in replacements if token in text]
    if unresolved:
        raise SystemExit(f"L3_TEMPLATE_TOKEN_REMAINS:{label}:{unresolved}")
    return text


def validator_source(kind: str) -> str:
    specs = namespace["SPECS"]
    spec = specs[kind]  # type: ignore[index]
    specific_by_kind = {
        "location": namespace["LOCATION_SPECIFIC"],
        "item": namespace["ITEM_SPECIFIC"],
        "faction": namespace["FACTION_SPECIFIC"],
    }
    text = str(namespace["VALIDATOR_TEMPLATE"])
    text = text.replace("{{", "{").replace("}}", "}")
    return replace_declared_tokens(
        text,
        (
            ("{contract}", spec["contract"]),
            ("{version}", spec["version"]),
            ("{prefix}", spec["prefix"]),
            ("{schema_name}", spec["schema"].name),
            ("{fixture_name}", spec["fixtures"].name),
            ("{module_name}", f"validate_{kind}_ledger_content"),
            ("{specific_source}", specific_by_kind[kind]),
        ),
        label=f"validator:{kind}",
    )


def test_sources(kind: str, fixtures: list[dict[str, Any]]) -> str:
    specs = namespace["SPECS"]
    spec = specs[kind]  # type: ignore[index]
    valid = sum(case["expect"] == "PASS" for case in fixtures)
    invalid = len(fixtures) - valid
    extras = {
        "location": r'''def test_location_query_vocabulary_is_exact() -> None:
    missing = next(case for case in CASES if case["case_id"] == "LOC-PASS-05")
    incomparable = next(case for case in CASES if case["case_id"] == "LOC-PASS-06")
    assert MODULE.run_query_case(missing)["status"] == "NOT_RECORDED"
    assert MODULE.run_query_case(incomparable)["status"] == "STORY_TIME_NOT_COMPARABLE"
''',
        "item": r'''def test_item_ownership_is_read_projection() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "变化真值住事实账" in contract
    recorded = next(case for case in CASES if case["case_id"] == "IT-PASS-03")
    assert MODULE.run_query_case(recorded)["owner_ref"] == "CH-0001"
''',
        "faction": r'''def test_faction_member_and_relation_queries_use_same_vocabulary() -> None:
    missing = next(case for case in CASES if case["case_id"] == "FA-PASS-05")
    incomparable = next(case for case in CASES if case["case_id"] == "FA-PASS-06")
    assert MODULE.run_query_case(missing)["status"] == "NOT_RECORDED"
    assert MODULE.run_query_case(incomparable)["status"] == "STORY_TIME_NOT_COMPARABLE"
''',
    }
    return replace_declared_tokens(
        str(namespace["TEST_TEMPLATE"]),
        (
            ("{validator_name}", spec["validator"].name),
            ("{md_name}", spec["md"].name),
            ("{schema_name}", spec["schema"].name),
            ("{module_name}", f"validate_{kind}_ledger_content_test"),
            (
                "{fixture_counts}",
                repr(
                    {
                        "cases": len(fixtures),
                        "valid": valid,
                        "invalid": invalid,
                    }
                ),
            ),
            ("{title}", f"{spec['contract']} {spec['version']}"),
            ("{extra_tests}", extras[kind]),
        ),
        label=f"test:{kind}",
    )


namespace["validator_source"] = validator_source
namespace["test_sources"] = test_sources
main = namespace["main"]
raise SystemExit(main())  # type: ignore[operator]

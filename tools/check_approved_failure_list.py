#!/usr/bin/env python3
"""Compare collected pytest failure IDs to the CZ-approved frozen list.

This checker does not run pytest and cannot add IDs to the list.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

ROOT = Path(__file__).resolve().parents[1]
LIST_RELATIVE = Path("governance/approved_stable_failure_list.json")
SCHEMA_RELATIVE = Path(
    "governance/contracts/approved_stable_failure_list_v1.schema.json"
)
PASS_PREDICATE = "PASS_WITH_STABLE_MAIN_EXISTING_NON_NOVEL_DEBT"
UNAPPROVED = "UNAPPROVED_FINDING"
MISSING_APPROVED = "APPROVED_FAILURE_MISSING"
ROUNDS_UNEQUAL = "ROUNDS_UNEQUAL"
LIST_INVALID = "APPROVED_LIST_INVALID"
SINGLE_ROUND = "SINGLE_ROUND_MATCH_NOT_A_PASS_PREDICATE"


class ApprovedListError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def payload_sha256(document: dict[str, Any]) -> str:
    body = {key: value for key, value in document.items() if key != "payload_sha256"}
    return hashlib.sha256(_json_bytes(body)).hexdigest()


def seal_list(document: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(document)
    sealed["payload_sha256"] = payload_sha256(sealed)
    return sealed


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApprovedListError(LIST_INVALID, f"无法读取 {path}") from exc
    if not isinstance(value, dict):
        raise ApprovedListError(LIST_INVALID, f"{path} 顶层必须是对象")
    return value


def load_approved_list(repo_root: Path | None = None) -> dict[str, Any]:
    if repo_root is None:
        repo_root = ROOT
    schema = _load_json(repo_root / SCHEMA_RELATIVE)
    document = _load_json(repo_root / LIST_RELATIVE)
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
    except (SchemaError, ValidationError) as exc:
        raise ApprovedListError(LIST_INVALID, exc.message) from exc
    ids = [row["id"] for row in document["failures"]]
    if ids != sorted(set(ids)):
        raise ApprovedListError(LIST_INVALID, "失败 ID 必须唯一且按字典序排列")
    if document["failure_count"] != len(ids):
        raise ApprovedListError(LIST_INVALID, "failure_count 与 ID 条数不一致")
    if document["payload_sha256"] != payload_sha256(document):
        raise ApprovedListError(LIST_INVALID, "payload_sha256 与规范字节不一致")
    return document


def load_observed(path: Path) -> list[str]:
    document = _load_json(path)
    ids = document.get("failed_nodeids")
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        raise ApprovedListError(LIST_INVALID, f"{path} 需要 failed_nodeids 字符串数组")
    return sorted(set(ids))


def classify(
    approved: dict[str, Any],
    rounds: Sequence[Sequence[str]],
) -> dict[str, Any]:
    approved_ids = [row["id"] for row in approved["failures"]]
    approved_set = set(approved_ids)
    round_sets = [sorted(set(items)) for items in rounds]
    extras: list[str] = []
    missing: list[str] = []
    status = PASS_PREDICATE
    if len(round_sets) < 1:
        raise ApprovedListError(LIST_INVALID, "至少需要一轮观察失败集合")
    if any(round_sets[0] != other for other in round_sets[1:]):
        status = ROUNDS_UNEQUAL
    else:
        observed = set(round_sets[0])
        extras = sorted(observed - approved_set)
        missing = sorted(approved_set - observed)
        if extras:
            status = UNAPPROVED
        elif missing:
            status = MISSING_APPROVED
        elif len(round_sets) != 3:
            status = SINGLE_ROUND
    return {
        "status": status,
        "predicate": PASS_PREDICATE,
        "main_sha": approved["main_sha"],
        "approved_count": approved["failure_count"],
        "round_count": len(round_sets),
        "unapproved_ids": extras,
        "missing_approved_ids": missing,
        "approval_status": approved["approval"]["status"],
    }


def command_verify(_args: argparse.Namespace) -> int:
    load_approved_list(ROOT)
    print("LIST_OK")
    return 0


def command_check(args: argparse.Namespace) -> int:
    approved = load_approved_list(ROOT)
    rounds = [load_observed(Path(path)) for path in args.observed]
    report = classify(approved, rounds)
    sys.stdout.buffer.write(_json_bytes(report))
    if report["status"] == PASS_PREDICATE:
        return 0
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把已收集的 pytest 失败 ID 和 CZ 批准清单逐项对账；不跑测试、不改清单。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify-list", help="只核清单自身四件套")
    verify.set_defaults(handler=command_verify)
    check = subparsers.add_parser("check", help="对账一轮或多轮观察失败集合")
    check.add_argument(
        "--observed",
        action="append",
        required=True,
        help="观察失败 JSON（含 failed_nodeids）；要报 PASS 谓词必须恰好三轮且逐项相等",
    )
    check.set_defaults(handler=command_check)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except ApprovedListError as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

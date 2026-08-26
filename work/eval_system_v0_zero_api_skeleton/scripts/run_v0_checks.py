#!/usr/bin/env python3
"""Run the v0 empty-skeleton checkers on synthetic fixtures. 0 API."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from v0_lib.exam import exam_error  # noqa: E402
from v0_lib.mechanical import assess_envelope  # noqa: E402
from v0_lib.reason_codes import reason_pair_error  # noqa: E402
from v0_lib.refs import refs_error  # noqa: E402
from v0_lib.reports import build_reports, reports_error, to_markdown  # noqa: E402
from v0_lib.schema_check import load_schema, validate_def  # noqa: E402
from v0_lib.state import compare_pair, illegal_state_reason  # noqa: E402
from v0_lib.tree import tree_error  # noqa: E402

FIXTURES = ROOT / "fixtures" / "synthetic"
REPORTS = ROOT / "reports"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def add(results: list[dict[str, Any]], name: str, ok: bool, detail: str) -> None:
    results.append({"name": name, "ok": ok, "detail": detail})


def main() -> int:
    results: list[dict[str, Any]] = []

    tree = tree_error(ROOT)
    add(results, "step1_tree", tree is None, tree or "ok")

    schema = load_schema()
    records = load_json(FIXTURES / "records_valid.json")
    schema_ok = True
    schema_detail = "ok"
    try:
        for def_name, instance in records.items():
            validate_def(def_name, instance, schema)
    except Exception as exc:  # noqa: BLE001 — surface fixture/schema mismatch
        schema_ok = False
        schema_detail = str(exc)
    add(results, "step2_schema_valid_records", schema_ok, schema_detail)

    illegal_records = load_json(FIXTURES / "records_illegal.json")
    illegal_schema_ok = True
    illegal_schema_detail = "ok"
    for row in illegal_records:
        try:
            validate_def(row["def"], row["instance"], schema)
        except Exception:
            continue
        illegal_schema_ok = False
        illegal_schema_detail = f"expected reject: {row.get('label') or row['def']}"
        break
    add(results, "step2_schema_illegal_records", illegal_schema_ok, illegal_schema_detail)

    for row in load_jsonl(FIXTURES / "envelopes.jsonl"):
        got = assess_envelope(row)
        expect_status = row["expect_status"]
        ok = got.mechanical_status == expect_status
        if ok and expect_status == "FAIL":
            ok = got.failure_stage == row.get("expect_stage") and got.failure_code == row.get(
                "expect_code"
            )
        add(
            results,
            f"step3_{row['case_id']}",
            ok,
            json.dumps(got.as_dict(), ensure_ascii=False),
        )

    for row in load_jsonl(FIXTURES / "pairs.jsonl"):
        if row.get("expect_illegal"):
            reason = illegal_state_reason(row)
            ok = reason == row["expect_illegal"]
            add(results, f"step4_illegal_{row['case_id']}", ok, reason or "not_rejected")
            continue
        got = compare_pair(row)
        expect = row["expect"]
        ok = all(got.get(key) == expect[key] for key in expect)
        add(results, f"step4_{row['case_id']}", ok, json.dumps(got, ensure_ascii=False))

    for path in sorted((FIXTURES / "reason_codes" / "valid").glob("*.json")):
        pair = load_json(path)
        err = reason_pair_error(pair, filename=path.name)
        add(results, f"step5_valid_{path.stem}", err is None, err or "ok")
    for path in sorted((FIXTURES / "reason_codes" / "illegal").glob("*.json")):
        pair = load_json(path)
        err = reason_pair_error(pair, filename=path.name)
        add(results, f"step5_illegal_{path.stem}", err is not None, err or "not_rejected")

    for path in sorted((FIXTURES / "exam").glob("*.json")):
        pack = load_json(path)
        err = exam_error(pack)
        expect_err = pack.get("expect_error")
        if expect_err:
            ok = err == expect_err
        else:
            ok = err is None
        add(results, f"step6_{path.stem}", ok, err or "ok")

    pack = load_json(FIXTURES / "run_pack.json")
    tables = build_reports(pack)
    err = reports_error(tables)
    add(results, "step7_reports", err is None, err or "ok")
    generated = REPORTS / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    titles = {
        "evidence_gate_attempt_mechanical": "证据门 · Attempt 机械明细",
        "evidence_gate_pair_comparison": "证据门 · Pair 对照明细",
        "exam_split_exposure_unreviewed": "考卷 · split / exposure / UNREVIEWED",
        "api_eval_three_columns": "接口评测 · 三栏",
    }
    for name, rows in tables.items():
        (generated / f"{name}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (generated / f"{name}.md").write_text(
            to_markdown(titles[name], rows), encoding="utf-8"
        )

    for path in sorted((FIXTURES / "refs").glob("*.json")):
        blob = load_json(path)
        err = refs_error(blob)
        expect_err = blob.get("expect_error")
        if expect_err:
            ok = err == expect_err
        else:
            ok = err is None
        add(results, f"step8_{path.stem}", ok, err or "ok")

    failed = [row for row in results if not row["ok"]]
    receipt = {
        "root": "work/eval_system_v0_zero_api_skeleton",
        "issue": 168,
        "api_calls": 0,
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": [row["name"] for row in failed],
        "results": results,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "self_check.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# v0 空骨架自检回执",
        "",
        f"通过 {receipt['passed']} / {receipt['total']}；API 调用 {receipt['api_calls']}",
        "",
    ]
    if failed:
        lines.append("失败：")
        for row in failed:
            lines.append(f"- `{row['name']}`：{row['detail']}")
        lines.append("")
    (REPORTS / "self_check.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines).rstrip())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

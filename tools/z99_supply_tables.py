#!/usr/bin/env python3
"""Build the deterministic Z99 external-finalization supply tables.

This module is deliberately read-only outside its output directory.  It does
not import an HTTP client and does not call any model or provider catalogue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "experiments"
    / "Z99_external_finalization_supply_20260724"
    / "supply_tables"
)
BUILD_DATE = "2026-07-24"

CORE_FILENAMES = (
    "table_a_thinking_inputs.json",
    "table_a_thinking_inputs.md",
    "table_b_historical_api_rounds.json",
    "table_b_historical_api_rounds.md",
    "input_manifest.json",
)
RECEIPT_FILENAMES = (
    "acceptance_receipt.json",
    "acceptance_receipt.md",
)
ALL_FILENAMES = CORE_FILENAMES + RECEIPT_FILENAMES


class SourceDataError(RuntimeError):
    """Raised when a frozen source no longer matches the declared evidence."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _text_bytes(value: str) -> bytes:
    if not value.endswith("\n"):
        value += "\n"
    return value.encode("utf-8")


def _expect(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise SourceDataError(
            f"{label} changed: expected {expected!r}, observed {actual!r}"
        )


def _tokens(prompt: int, completion: int, total: int) -> dict[str, int]:
    _expect("token arithmetic", prompt + completion, total)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


@dataclass
class _TrackedSource:
    path: Path
    data: bytes
    roles: set[str]


class SourceTracker:
    """Read inputs and retain a byte-level provenance manifest."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self._sources: dict[Path, _TrackedSource] = {}

    def display_path(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.repo_root).as_posix()
        except ValueError:
            return resolved.as_posix()

    def read_bytes(self, path: Path, role: str) -> bytes:
        resolved = path.resolve()
        if not resolved.is_file():
            raise SourceDataError(f"required source is missing: {resolved}")
        data = resolved.read_bytes()
        tracked = self._sources.get(resolved)
        if tracked is None:
            self._sources[resolved] = _TrackedSource(resolved, data, {role})
        else:
            if tracked.data != data:
                raise SourceDataError(f"source changed during build: {resolved}")
            tracked.roles.add(role)
        return data

    def read_text(self, path: Path, role: str) -> str:
        return self.read_bytes(path, role).decode("utf-8", errors="strict")

    def read_json(self, path: Path, role: str) -> Any:
        return json.loads(self.read_text(path, role))

    def read_jsonl(self, path: Path, role: str) -> list[dict[str, Any]]:
        text = self.read_text(path, role)
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise SourceDataError(
                    f"{self.display_path(path)}:{line_number} is not an object"
                )
            rows.append(value)
        return rows

    def manifest(self) -> dict[str, Any]:
        rows = []
        for path, tracked in sorted(
            self._sources.items(),
            key=lambda item: self.display_path(item[0]),
        ):
            rows.append(
                {
                    "bytes": len(tracked.data),
                    "path": self.display_path(path),
                    "roles": sorted(tracked.roles),
                    "sha256": _sha256(tracked.data),
                }
            )
        return {
            "schema_version": "z99-supply-input-manifest-v1",
            "build_date": BUILD_DATE,
            "model_api_calls": 0,
            "network_requests": 0,
            "source_count": len(rows),
            "sources": rows,
        }


def _usage_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    prompt = 0
    completion = 0
    total = 0
    providers: set[str] = set()
    models: set[str] = set()
    for row in rows:
        usage = row.get("usage")
        if not isinstance(usage, dict):
            raise SourceDataError("usage.jsonl row has no usage object")
        row_prompt = int(usage["prompt_tokens"])
        row_completion = int(usage["completion_tokens"])
        row_total = int(usage["total_tokens"])
        _expect("usage row token arithmetic", row_prompt + row_completion, row_total)
        prompt += row_prompt
        completion += row_completion
        total += row_total
        provider = row.get("provider")
        if isinstance(provider, str) and provider:
            providers.add(provider)
        model = row.get("response_model") or row.get("requested_model")
        if isinstance(model, str) and model:
            models.add(model)
    return {
        "usage_rows": len(rows),
        **_tokens(prompt, completion, total),
        "providers_seen": sorted(providers),
        "models_seen": sorted(models),
    }


def _expect_usage(
    label: str,
    actual: dict[str, Any],
    *,
    rows: int,
    prompt: int,
    completion: int,
    total: int,
) -> None:
    expected = {
        "usage_rows": rows,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }
    observed = {key: actual[key] for key in expected}
    _expect(label, observed, expected)


def _missing_cost(note: str) -> dict[str, Any]:
    return {
        "amount_cny": "missing",
        "calculated_now": False,
        "note": note,
        "scope": "this_round_new_model_work",
        "status": "missing",
    }


def _zero_cost(note: str) -> dict[str, Any]:
    return {
        "amount_cny": 0,
        "calculated_now": False,
        "note": note,
        "scope": "this_round_new_model_work",
        "status": "exact_zero_no_new_model_call",
    }


def _estimated_cost(amount: float, source_basis: str) -> dict[str, Any]:
    return {
        "amount_cny": amount,
        "calculated_now": False,
        "note": "只转录历史回执里的估算值，没有按当前价格重新计算。",
        "scope": "this_round_new_model_work",
        "source_basis": source_basis,
        "status": "estimated",
    }


def _strict_score(
    numerator: int,
    denominator: int,
    status: str,
    note: str,
) -> dict[str, Any]:
    return {
        "denominator": denominator,
        "note": note,
        "numerator": numerator,
        "status": status,
        "value": numerator / denominator,
    }


def _api_usage(
    *,
    logical_requests_started: int,
    network_attempts: int,
    accepted_completed_outputs: int,
    usage_bearing_responses: int,
    usage: dict[str, int],
    lineage_usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "accepted_completed_outputs": accepted_completed_outputs,
        "logical_requests_started": logical_requests_started,
        "network_attempts": network_attempts,
        "new_work_usage": usage,
        "usage_bearing_responses": usage_bearing_responses,
    }
    if lineage_usage is not None:
        value["lineage_usage_including_reuse"] = lineage_usage
    return value


TABLE_A_WINDOWS = (
    {
        "slot": "01",
        "window": "X01",
        "book": "诡秘之主",
        "bibliographic_unit": "第3章",
        "ucr_dir": "01_X01_guimi",
        "ucr_file": "03_thinking_20m45s.md",
        "blind_dir": "01_X01_guimi",
        "blind_file": "01_thinking_25m45s.md",
    },
    {
        "slot": "02",
        "window": "B01",
        "book": "庶女明兰传（知否？知否？应是绿肥红瘦）",
        "bibliographic_unit": "U0033",
        "ucr_dir": "02_B01_zhifou",
        "ucr_file": "03_thinking_23m47s.md",
        "blind_dir": "02_B01_zhifou",
        "blind_file": "01_thinking_34m15s.md",
    },
    {
        "slot": "03",
        "window": "B02",
        "book": "大王饶命",
        "bibliographic_unit": "U0039",
        "ucr_dir": "03_B02_dawang",
        "ucr_file": "03_thinking_16m27s.md",
        "blind_dir": "03_B02_dawang",
        "blind_file": "01_thinking_26m16s.md",
    },
    {
        "slot": "04",
        "window": "B03",
        "book": "神秘复苏",
        "bibliographic_unit": "U0041",
        "ucr_dir": "04_B03_shenmi",
        "ucr_file": "03_thinking_23m49s.md",
        "blind_dir": "04_B03_shenmi",
        "blind_file": "01_thinking_18m55s.md",
    },
    {
        "slot": "05",
        "window": "B04",
        "book": "无限恐怖",
        "bibliographic_unit": "U0003",
        "ucr_dir": "05_B04_wuxian",
        "ucr_file": "03_thinking_19m51s.md",
        "blind_dir": "05_B04_wuxian",
        "blind_file": "01_thinking_24m17s.md",
    },
    {
        "slot": "06",
        "window": "B05",
        "book": "凡人修仙传",
        "bibliographic_unit": "U0030／第30章",
        "ucr_dir": "06_B05_fanren",
        "ucr_file": "03_thinking_21m49s.md",
        "blind_dir": "06_B05_fanren",
        "blind_file": "01_thinking_19m48s.md",
    },
)


def _table_a_expected_paths(repo_root: Path) -> dict[str, list[Path]]:
    ucr_base = repo_root / "TEMP" / "gold_ucr_returns_notion_20260724"
    blind_base = repo_root / "TEMP" / "gold_blind_produce_returns_20260724"
    return {
        "UCR": [
            ucr_base / str(item["ucr_dir"]) / str(item["ucr_file"])
            for item in TABLE_A_WINDOWS
        ],
        "blind": [
            blind_base / str(item["blind_dir"]) / str(item["blind_file"])
            for item in TABLE_A_WINDOWS
        ],
    }


def _validate_exact_thinking_scope(repo_root: Path) -> dict[str, list[Path]]:
    expected = _table_a_expected_paths(repo_root)
    observed_ucr = sorted(
        (repo_root / "TEMP" / "gold_ucr_returns_notion_20260724").glob(
            "*/03_thinking_*.md"
        )
    )
    observed_blind = sorted(
        (repo_root / "TEMP" / "gold_blind_produce_returns_20260724").glob(
            "*/01_thinking_*.md"
        )
    )
    _expect(
        "exact UCR thinking inputs",
        [path.resolve() for path in observed_ucr],
        [path.resolve() for path in expected["UCR"]],
    )
    _expect(
        "exact blind thinking inputs",
        [path.resolve() for path in observed_blind],
        [path.resolve() for path in expected["blind"]],
    )
    return expected


def _build_table_a(
    repo_root: Path,
    tracker: SourceTracker,
) -> dict[str, Any]:
    paths = _validate_exact_thinking_scope(repo_root)
    ucr_base = repo_root / "TEMP" / "gold_ucr_returns_notion_20260724"
    blind_base = repo_root / "TEMP" / "gold_blind_produce_returns_20260724"

    ucr_parent = "https://app.notion.com/p/3a75cadc4d0f81b8b165daae23487712"
    ucr_order = "https://app.notion.com/p/3a75cadc4d0f81509388ec91289d2cac"
    blind_parent = "https://app.notion.com/p/3a75cadc4d0f81e8956bcf6fbc38ea4c"
    blind_order = "https://app.notion.com/p/b1c51430b1374d0a96b7bfb7d672e489"

    ucr_index = tracker.read_text(ucr_base / "INDEX.md", "table_a_batch_index")
    blind_index = tracker.read_text(blind_base / "INDEX.md", "table_a_batch_index")
    for label, text, required_urls in (
        ("UCR index", ucr_index, (ucr_parent, ucr_order)),
        ("blind index", blind_index, (blind_parent, blind_order)),
    ):
        for url in required_urls:
            if url not in text:
                raise SourceDataError(f"{label} no longer contains {url}")

    blind_manifest = tracker.read_json(
        blind_base / "manifest.json",
        "table_a_source_manifest",
    )
    _expect("blind manifest model calls", blind_manifest["model_api_calls"], 0)
    _expect("blind manifest book count", len(blind_manifest["books"]), 6)

    rows: list[dict[str, Any]] = []
    for batch_code, batch_label, parent, order, batch_paths in (
        (
            "UCR",
            "六本金标 UCR 核准回包",
            ucr_parent,
            ucr_order,
            paths["UCR"],
        ),
        (
            "blind",
            "六本金标从零盲产回包",
            blind_parent,
            blind_order,
            paths["blind"],
        ),
    ):
        for index, (window, path) in enumerate(
            zip(TABLE_A_WINDOWS, batch_paths, strict=True)
        ):
            data = tracker.read_bytes(path, "table_a_thinking_input")
            text = data.decode("utf-8", errors="strict")
            sha = _sha256(data)
            if batch_code == "blind":
                _expect(
                    f"blind manifest SHA for slot {window['slot']}",
                    blind_manifest["books"][index]["thinking_sha256"],
                    sha,
                )
            rows.append(
                {
                    "bibliographic_unit": window["bibliographic_unit"],
                    "book": window["book"],
                    "bytes": len(data),
                    "file_path": tracker.display_path(path),
                    "notion_batch_index_entry": parent,
                    "notion_parent_entry": order,
                    "sha256": sha,
                    "slot": window["slot"],
                    "source_batch": batch_label,
                    "source_batch_code": batch_code,
                    "unicode_char_count": len(text),
                    "window": window["window"],
                }
            )

    _expect("table A row count", len(rows), 12)
    _expect(
        "table A batch counts",
        {
            code: sum(row["source_batch_code"] == code for row in rows)
            for code in ("UCR", "blind")
        },
        {"UCR": 6, "blind": 6},
    )
    return {
        "schema_version": "z99-thinking-supply-table-a-v1",
        "build_date": BUILD_DATE,
        "scope_boundary": (
            "只登记指定的 6 份 UCR 思考稿和 6 份盲产思考稿；"
            "不把候选银标改判为现役金标，也不做语义质量评分。"
        ),
        "summary": {
            "blind_rows": 6,
            "row_count": 12,
            "total_bytes": sum(row["bytes"] for row in rows),
            "total_unicode_char_count": sum(row["unicode_char_count"] for row in rows),
            "ucr_rows": 6,
        },
        "rows": rows,
    }


def _table_a_markdown(table: dict[str, Any]) -> str:
    lines = [
        "# Z99 供料表 A｜12 份思考稿字节清单",
        "",
        "✅ 结论：范围严格锁定为 6 份 UCR 思考稿和 6 份盲产思考稿，共 12 份。",
        "",
        "这张表只回答文件是谁、来自哪一批、字节和字符有多少、哈希是什么。"
        "它不把候选银标改成现役金标，也不代替后续语义审查。",
        "",
        "| 批次 | 窗口 | 书目／单元 | 字节 | Unicode 字符 | SHA-256 | 文件 |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in table["rows"]:
        lines.append(
            "| {source_batch_code} | {window} | {book}／{bibliographic_unit} | "
            "{bytes} | {unicode_char_count} | `{sha256}` | `{file_path}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "Notion 父级入口：",
            "",
            "- UCR 回包总索引："
            "https://app.notion.com/p/3a75cadc4d0f81b8b165daae23487712",
            "- UCR 所挂停点：https://app.notion.com/p/3a75cadc4d0f81509388ec91289d2cac",
            "- 盲产回包总索引："
            "https://app.notion.com/p/3a75cadc4d0f81e8956bcf6fbc38ea4c",
            "- 盲产所挂令页：https://app.notion.com/p/b1c51430b1374d0a96b7bfb7d672e489",
            "",
            "来源：Codex",
        ]
    )
    return "\n".join(lines) + "\n"


def _source_paths(tracker: SourceTracker, paths: Iterable[Path]) -> list[str]:
    return [tracker.display_path(path) for path in paths]


def _build_table_b(
    repo_root: Path,
    tracker: SourceTracker,
) -> dict[str, Any]:
    archive_runs = (
        repo_root.parent
        / f"{repo_root.name}_外置仓"
        / "archive_batch_20260723"
        / "runs"
    )

    z57_transport_path = (
        repo_root
        / "reports/Z57_稳定语义身份解耦与全链后半_20260719/运输层实跑观察.json"
    )
    z57_score_path = (
        repo_root
        / "reports/Z57_稳定语义身份解耦与全链后半_20260719/第3章当章层诚实成绩单.json"
    )
    z57_transport = tracker.read_json(z57_transport_path, "table_b_transport_receipt")
    z57_score = tracker.read_json(z57_score_path, "table_b_scorecard")
    _expect("Z57 new model calls", z57_transport["z57_new_work"]["model_api_calls"], 0)
    _expect(
        "Z57 lineage usage",
        {
            key: z57_transport["lineage_source_sampling"]["usage"][key]
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        },
        _tokens(129243, 109313, 238556),
    )
    _expect(
        "Z57 strict score",
        (
            z57_score["summary"]["strict_complete_extraction"],
            z57_score["summary"]["on_chapter_gold_total"],
        ),
        (2, 14),
    )

    z59_usage_path = (
        repo_root
        / "runs/Z59_A_X01_实体供料注入中性抽取_五靶章_v1.0_20260719/usage.jsonl"
    )
    z59_cost_path = (
        repo_root / "runs/Z59_A_X01_实体供料注入中性抽取_五靶章_v1.0_20260719/"
        "analysis/成本账.json"
    )
    z59_score_path = (
        repo_root / "runs/Z59_A_X01_实体供料注入中性抽取_五靶章_v1.0_20260719/"
        "analysis/第3章条件成绩语义复核.json"
    )
    z59_diff_path = (
        repo_root / "runs/Z59_A_X01_实体供料注入中性抽取_五靶章_v1.0_20260719/"
        "single_variable_diff.json"
    )
    z59_usage = _usage_summary(
        tracker.read_jsonl(z59_usage_path, "table_b_usage_ledger")
    )
    _expect_usage(
        "Z59-A usage",
        z59_usage,
        rows=5,
        prompt=34821,
        completion=23851,
        total=58672,
    )
    z59_cost = tracker.read_json(z59_cost_path, "table_b_cost_ledger")
    _expect(
        "Z59-A cost-ledger usage",
        z59_cost["usage"]["usage_totals"],
        _tokens(34821, 23851, 58672),
    )
    z59_score = tracker.read_json(z59_score_path, "table_b_scorecard")
    _expect(
        "Z59-A strict score",
        (
            z59_score["semantic_review"]["strict_complete_extraction"],
            z59_score["semantic_review"]["denominator"],
        ),
        (3, 14),
    )
    z59_diff = tracker.read_json(z59_diff_path, "table_b_variable_receipt")
    _expect("Z59-A single-variable receipt", z59_diff["status"], "pass")

    z68_usage_path = (
        repo_root / "runs/Z68C_X01_修正版请求体32k兼容续跑_五靶章_v1.1_20260720/"
        "usage.jsonl"
    )
    z68_reuse_path = (
        repo_root / "runs/Z68C_X01_修正版请求体32k兼容续跑_五靶章_v1.1_20260720/"
        "reused_16k/usage.jsonl"
    )
    z68_transport_path = (
        repo_root
        / "reports/Z68续令_32k参数兼容修复与裸考成绩_20260720/运输与成本回执.json"
    )
    z68_score_path = (
        repo_root / "reports/Z68续令_32k参数兼容修复与裸考成绩_20260720/"
        "第3章金标v1.1语义成绩单.json"
    )
    z68_variable_path = (
        repo_root / "reports/Z68续令_32k参数兼容修复与裸考成绩_20260720/"
        "供料单变量与保护回执.json"
    )
    z68_usage = _usage_summary(
        tracker.read_jsonl(z68_usage_path, "table_b_usage_ledger")
    )
    z68_reuse = _usage_summary(
        tracker.read_jsonl(z68_reuse_path, "table_b_reused_usage_ledger")
    )
    _expect_usage(
        "Z68C new usage",
        z68_usage,
        rows=3,
        prompt=27380,
        completion=25170,
        total=52550,
    )
    _expect_usage(
        "Z68C reused usage",
        z68_reuse,
        rows=2,
        prompt=19452,
        completion=19340,
        total=38792,
    )
    z68_transport = tracker.read_json(
        z68_transport_path, "table_b_transport_and_cost_receipt"
    )
    _expect(
        "Z68C transport counts",
        (
            z68_transport["logical_samples"]["new"],
            z68_transport["transport"]["actual_network_attempts"],
            z68_transport["transport"]["usage"]["responses_with_usage"],
        ),
        (3, 4, 3),
    )
    _expect(
        "Z68C lineage usage",
        z68_transport["five_chapter_condition_cost"]["candidate"]["totals"][
            "total_tokens"
        ],
        91342,
    )
    z68_score = tracker.read_json(z68_score_path, "table_b_scorecard")
    _expect(
        "Z68C strict score",
        (z68_score["summary"]["strict_hit"], z68_score["summary"]["gold_total"]),
        (6, 14),
    )
    z68_variable = tracker.read_json(z68_variable_path, "table_b_variable_receipt")
    _expect(
        "Z68C local single variable",
        z68_variable["single_variable"],
        {"field": "max_tokens", "old": 16000, "new": 32000},
    )

    z70_usage_path = (
        archive_runs / "Z70_X01_事件句压缩合同_五靶章_v1.0_20260721/usage.jsonl"
    )
    z70_transport_path = (
        repo_root / "reports/Z70_压缩病灶合同条款单变量_20260721/运输与成本回执.json"
    )
    z70_score_path = (
        repo_root / "reports/Z70_压缩病灶合同条款单变量_20260721/"
        "第3章金标v1.1语义成绩单.json"
    )
    z70_variable_path = (
        repo_root / "reports/Z70_压缩病灶合同条款单变量_20260721/"
        "供料单变量与保护回执.json"
    )
    z70_usage = _usage_summary(
        tracker.read_jsonl(z70_usage_path, "table_b_usage_ledger_external_archive")
    )
    _expect_usage(
        "Z70 usage",
        z70_usage,
        rows=5,
        prompt=47082,
        completion=47616,
        total=94698,
    )
    z70_transport = tracker.read_json(
        z70_transport_path, "table_b_transport_and_cost_receipt"
    )
    _expect(
        "Z70 report usage",
        z70_transport["usage"]["totals"]["total_tokens"],
        94698,
    )
    z70_score = tracker.read_json(z70_score_path, "table_b_scorecard")
    _expect(
        "Z70 strict score",
        (z70_score["summary"]["strict_hit"], z70_score["summary"]["gold_total"]),
        (6, 14),
    )
    z70_variable = tracker.read_json(z70_variable_path, "table_b_variable_receipt")
    _expect("Z70 variable receipt", z70_variable["status"], "pass")

    z71_usage_path = (
        archive_runs / "Z71_X01_z70语义补全旁路_五靶章_v1.0_20260721/usage.jsonl"
    )
    z71_transport_path = (
        repo_root / "reports/Z71_z70语义补全旁路_20260721/运输与成本回执.json"
    )
    z71_score_path = (
        repo_root / "reports/Z71_z70语义补全旁路_20260721/第3章金标v1.1语义成绩单.json"
    )
    z71_usage = _usage_summary(
        tracker.read_jsonl(z71_usage_path, "table_b_usage_ledger_external_archive")
    )
    _expect_usage(
        "Z71 usage",
        z71_usage,
        rows=25,
        prompt=96739,
        completion=61202,
        total=157941,
    )
    z71_transport = tracker.read_json(
        z71_transport_path, "table_b_transport_and_cost_receipt"
    )
    _expect(
        "Z71 transport counts",
        (
            z71_transport["transport"]["actual_model_api_calls"],
            z71_transport["transport"]["network_attempts"],
        ),
        (25, 25),
    )
    z71_score = tracker.read_json(z71_score_path, "table_b_scorecard")
    _expect(
        "Z71 strict score",
        (z71_score["summary"]["strict_hit"], z71_score["summary"]["gold_total"]),
        (6, 14),
    )

    z79_usage_path = (
        repo_root
        / "runs/Z79_X01_事实说明书注入包v3_三章复验_v1.0_20260721_transport_retry01/"
        "usage.jsonl"
    )
    z79_report_path = (
        repo_root
        / "reports/Z79_事实说明书注入包v3三章复验_20260721/成绩与验收总表.json"
    )
    z79_usage = _usage_summary(
        tracker.read_jsonl(z79_usage_path, "table_b_usage_ledger")
    )
    _expect_usage(
        "Z79 usage",
        z79_usage,
        rows=3,
        prompt=33438,
        completion=37173,
        total=70611,
    )
    z79_report = tracker.read_json(z79_report_path, "table_b_formal_scorecard")
    _expect(
        "Z79 transport counts",
        (
            z79_report["transport"]["logical_main_calls"],
            z79_report["transport"]["network_attempts"],
        ),
        (3, 4),
    )
    _expect(
        "Z79 strict score",
        (
            z79_report["gold_chapter_3"]["z79_v3"]["strict_hit"],
            z79_report["gold_chapter_3"]["z79_v3"]["denominator"],
        ),
        (10, 23),
    )

    z80_usage_path = (
        repo_root / "runs/Z80_事实说明书注入包v4_三组复验_v1.3_20260721/"
        "groups/G1_X01/usage.jsonl"
    )
    z80_report_path = (
        repo_root / "reports/Z80_事实说明书注入包v4三组复验_20260721/"
        "G1_X01_成绩与硬停总表.json"
    )
    z80_usage = _usage_summary(
        tracker.read_jsonl(z80_usage_path, "table_b_usage_ledger")
    )
    _expect_usage(
        "Z80 usage",
        z80_usage,
        rows=3,
        prompt=33882,
        completion=67611,
        total=101493,
    )
    z80_report = tracker.read_json(z80_report_path, "table_b_formal_scorecard")
    _expect(
        "Z80 strict score",
        (
            z80_report["semantic_gates"]["gold_v1_2"]["strict_hit"],
            z80_report["semantic_gates"]["gold_v1_2"]["denominator"],
        ),
        (6, 23),
    )
    _expect("Z80 uncalled group 2", z80_report["hard_stop"]["group_2_called"], False)
    _expect("Z80 uncalled group 3", z80_report["hard_stop"]["group_3_called"], False)

    retry03_base = (
        repo_root / "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry03"
    )
    retry03_main_path = retry03_base / "main/usage.jsonl"
    retry03_seed_path = retry03_base / "main/main_seed_manifest.json"
    retry03_inspector_raw_path = (
        retry03_base / "review/inspector/ch0003/run/responses/semantic_route/"
        "Z83-MAIN-CH0003-API_raw.json"
    )
    retry03_hard_stop_path = retry03_base / "review/inspector/hard_stop.json"
    retry03_main_rows = tracker.read_jsonl(
        retry03_main_path, "table_b_usage_ledger_mixed_reuse"
    )
    retry03_main = _usage_summary(retry03_main_rows)
    _expect_usage(
        "retry03 main lineage usage",
        retry03_main,
        rows=3,
        prompt=33438,
        completion=49859,
        total=83297,
    )
    retry03_seed = tracker.read_json(retry03_seed_path, "table_b_reuse_manifest")
    _expect("retry03 seeded chapters", retry03_seed["chapters"], [3])
    inspector_raw = tracker.read_json(
        retry03_inspector_raw_path, "table_b_usage_bearing_failed_response"
    )
    _expect(
        "retry03 inspector finish reason",
        inspector_raw["choices"][0]["finish_reason"],
        "length",
    )
    inspector_tokens = {
        key: int(inspector_raw["usage"][key])
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    _expect("retry03 inspector usage", inspector_tokens, _tokens(12358, 8001, 20359))
    retry03_hard_stop = tracker.read_json(
        retry03_hard_stop_path, "table_b_hard_stop_receipt"
    )
    _expect(
        "retry03 inspector transport",
        (
            retry03_hard_stop["network_attempts"],
            retry03_hard_stop["logical_model_calls_completed"],
        ),
        (1, 0),
    )
    retry03_new_usage = _tokens(34786, 48835, 83621)
    retry03_lineage_usage = _tokens(45796, 57860, 103656)

    retry13_base = (
        repo_root / "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry13"
    )
    retry13_repair_path = retry13_base / "repair/usage.jsonl"
    retry13_inspector_paths = [
        retry13_base / f"final_review/inspector/ch{chapter:04d}/run/usage.jsonl"
        for chapter in (3, 13, 19)
    ]
    retry13_report_path = (
        repo_root / "reports/Z83_retry13双合同原子化硬停_20260722/硬停回执.json"
    )
    retry13_score_path = retry13_base / "final/scorecard.json"
    retry13_repair = _usage_summary(
        tracker.read_jsonl(retry13_repair_path, "table_b_usage_ledger")
    )
    retry13_inspector_rows: list[dict[str, Any]] = []
    for path in retry13_inspector_paths:
        retry13_inspector_rows.extend(
            tracker.read_jsonl(path, "table_b_inspector_usage_ledger")
        )
    retry13_inspector = _usage_summary(retry13_inspector_rows)
    _expect_usage(
        "retry13 repair usage",
        retry13_repair,
        rows=32,
        prompt=270715,
        completion=18408,
        total=289123,
    )
    _expect_usage(
        "retry13 inspector usage",
        retry13_inspector,
        rows=3,
        prompt=4873,
        completion=7281,
        total=12154,
    )
    retry13_report = tracker.read_json(retry13_report_path, "table_b_transport_receipt")
    _expect(
        "retry13 new model totals",
        {
            key: retry13_report["model_api"][key]
            for key in (
                "new_logical_calls",
                "new_network_attempts",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            )
        },
        {
            "new_logical_calls": 35,
            "new_network_attempts": 35,
            "prompt_tokens": 275588,
            "completion_tokens": 25689,
            "total_tokens": 301277,
        },
    )
    retry13_score = tracker.read_json(retry13_score_path, "table_b_formal_scorecard")
    _expect(
        "retry13 strict score",
        (
            retry13_score["gold_chapter_3"]["strict_hit"],
            retry13_score["gold_chapter_3"]["formal_denominator"],
        ),
        (6, 23),
    )

    z89_usage_path = (
        repo_root / "runs/Z89_X01_DeepSeekV4Pro强模型对照_第3章_v1.0_20260723/"
        "main/usage.jsonl"
    )
    z89_report_path = (
        repo_root / "reports/Z89_DeepSeekV4Pro强模型对照_20260723/运输与成绩总表.json"
    )
    z89_score_path = (
        repo_root / "runs/Z89_X01_DeepSeekV4Pro强模型对照_第3章_v1.0_20260723/"
        "final/scorecard.json"
    )
    z89_ucr_path = (
        repo_root / "reports/Z97_RFU建账与UCR五层候选_20260724/"
        "UCR五层_Z89只读演示成绩单.json"
    )
    z89_usage = _usage_summary(
        tracker.read_jsonl(z89_usage_path, "table_b_usage_ledger")
    )
    _expect_usage(
        "Z89 usage",
        z89_usage,
        rows=1,
        prompt=11030,
        completion=26196,
        total=37226,
    )
    z89_report = tracker.read_json(
        z89_report_path, "table_b_transport_cost_and_scorecard"
    )
    _expect(
        "Z89 strict score",
        (
            z89_report["gold_v1_2"]["strict_hit"],
            z89_report["gold_v1_2"]["denominator"],
        ),
        (10, 23),
    )
    _expect(
        "retry03 retrospective strict comparator",
        z89_report["comparisons"]["retry03"]["strict_hit"],
        6,
    )
    z89_score = tracker.read_json(z89_score_path, "table_b_formal_scorecard")
    _expect(
        "Z89 scorecard strict score",
        (
            z89_score["gold_chapter_3"]["strict_hit"],
            z89_score["gold_chapter_3"]["formal_denominator"],
        ),
        (10, 23),
    )
    z89_ucr = tracker.read_json(z89_ucr_path, "table_b_ucr_offline_demo")
    _expect("Z89 UCR formal eligibility", z89_ucr["formal_score_eligible"], False)
    _expect(
        "Z89 UCR",
        (
            z89_ucr["metrics"]["UCR"]["numerator"],
            z89_ucr["metrics"]["UCR"]["denominator"],
        ),
        (10.0, 23.0),
    )

    z94_base = repo_root / "runs/Z94_X01_Flash局部语义包_步二腾讯通道_v1.0_20260723"
    z94_main_path = z94_base / "main/usage.jsonl"
    z94_repair_path = z94_base / "repair/usage.jsonl"
    z94_inspector_paths = [
        z94_base / f"final_review/inspector/ch{chapter:04d}/run/usage.jsonl"
        for chapter in (3, 13, 19)
    ]
    z94_diagnostic_path = (
        z94_base
        / "final/diagnostics/z94_retry13_comparison_and_provider_provenance.json"
    )
    z94_score_path = z94_base / "final/scorecard.json"
    z94_main = _usage_summary(
        tracker.read_jsonl(z94_main_path, "table_b_reused_usage_ledger")
    )
    z94_repair = _usage_summary(
        tracker.read_jsonl(z94_repair_path, "table_b_usage_ledger")
    )
    z94_inspector_rows: list[dict[str, Any]] = []
    for path in z94_inspector_paths:
        z94_inspector_rows.extend(
            tracker.read_jsonl(path, "table_b_inspector_usage_ledger")
        )
    z94_inspector = _usage_summary(z94_inspector_rows)
    _expect_usage(
        "Z94 reused main usage",
        z94_main,
        rows=3,
        prompt=33438,
        completion=49859,
        total=83297,
    )
    _expect_usage(
        "Z94 repair usage",
        z94_repair,
        rows=32,
        prompt=39450,
        completion=16739,
        total=56189,
    )
    _expect_usage(
        "Z94 inspector usage",
        z94_inspector,
        rows=3,
        prompt=4877,
        completion=10018,
        total=14895,
    )
    z94_diagnostic = tracker.read_json(
        z94_diagnostic_path, "table_b_provider_and_comparison_diagnostic"
    )
    _expect(
        "Z94 new work totals",
        {
            key: z94_diagnostic["transport_ledgers"]["z94_new_model_work_total"][key]
            for key in (
                "logical_calls",
                "network_attempts",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            )
        },
        {
            "logical_calls": 35,
            "network_attempts": 35,
            "prompt_tokens": 44327,
            "completion_tokens": 26757,
            "total_tokens": 71084,
        },
    )
    _expect(
        "Z94 known second variable",
        z94_diagnostic["inference_boundary"]["known_second_variable_name"],
        "provider_channel",
    )
    z94_score = tracker.read_json(z94_score_path, "table_b_formal_scorecard")
    _expect("Z94 scorecard status", z94_score["status"], "hard_stop_candidate_failed")
    _expect(
        "Z94 strict score",
        (
            z94_diagnostic["formal_scores"]["chapter3_gold_v1_2"]["strict_hit"],
            z94_diagnostic["formal_scores"]["chapter3_gold_v1_2"]["denominator"],
        ),
        (6, 23),
    )

    z98_base = (
        repo_root / "runs/Z98_刀A小额补丁实验_步二正式执行器预演_r07_v1.3_20260724"
    )
    z98_receipt_path = z98_base / "rehearsal/full_chain_receipt.json"
    z98_manifest_path = z98_base / "run_manifest.json"
    z98_receipt = tracker.read_json(
        z98_receipt_path, "table_b_zero_call_rehearsal_receipt"
    )
    z98_manifest = tracker.read_json(
        z98_manifest_path, "table_b_zero_call_run_manifest"
    )
    _expect(
        "Z98 zero-call receipt",
        (
            z98_receipt["model_api_calls"],
            z98_receipt["network_attempts"],
            z98_receipt["provider_catalog_requests"],
            z98_receipt["quality_result"],
            z98_receipt["fixture_only_non_sendable"],
        ),
        (0, 0, 0, "NOT_RUN_FIXTURE_ONLY", True),
    )
    _expect("Z98 quality not reached", z98_manifest["quality_result"], "NOT_REACHED")

    common_missing_note = (
        "历史材料有 token／调用账，但没有可核的人民币金额；按规则不套用当前价格。"
    )
    rows: list[dict[str, Any]] = [
        {
            "row_id": "retry03",
            "round_label": "Z83 transport retry03",
            "date": "2026-07-22",
            "sample_scope": "X01 第3／13／19章主样张，加第3章检查员硬停尝试",
            "provider_model": {
                "provider": "sensenova",
                "model": "deepseek-v4-flash",
            },
            "api": _api_usage(
                logical_requests_started=3,
                network_attempts=3,
                accepted_completed_outputs=2,
                usage_bearing_responses=3,
                usage=retry03_new_usage,
                lineage_usage=retry03_lineage_usage,
            ),
            "cost_cny": _missing_cost(common_missing_note),
            "strict_score": _strict_score(
                6,
                23,
                "retrospective_read_only_comparator",
                "retry03 当时因检查员长度硬停未形成质量结论；6/23 来自 Z89 后续只读对照。",
            ),
            "ucr": None,
            "reuse": {
                "used": True,
                "details": "第3章主样张复用 retry01；本轮新跑第13／19章及一次检查员。",
                "reused_calls": 1,
                "reused_total_tokens": 20035,
                "source_monetary_amount_cny": "missing",
            },
            "comparison": {
                "single_variable_status": "not_single_variable",
                "known_second_variables": [
                    "第3章复用而第13／19章新跑",
                    "检查员回包 finish_reason=length",
                    "严格分后来自后续只读复核",
                ],
                "limitations": [
                    "不能把后续 6/23 写成 retry03 当时已经完成的正式质量成绩。",
                    "新工作 token 含有一次有 usage 但不可用的长度硬停回包。",
                ],
            },
            "source_paths": _source_paths(
                tracker,
                (
                    retry03_main_path,
                    retry03_seed_path,
                    retry03_inspector_raw_path,
                    retry03_hard_stop_path,
                    z89_report_path,
                ),
            ),
        },
        {
            "row_id": "Z57",
            "round_label": "Z57 baseline",
            "date": "2026-07-19",
            "sample_scope": "X01 20章冻结抽取件进入本地后半链；第3章按14项金标评分",
            "provider_model": {
                "provider": None,
                "model": None,
                "lineage_model": "deepseek-v4-flash",
            },
            "api": _api_usage(
                logical_requests_started=0,
                network_attempts=0,
                accepted_completed_outputs=0,
                usage_bearing_responses=0,
                usage=_tokens(0, 0, 0),
                lineage_usage=_tokens(129243, 109313, 238556),
            ),
            "cost_cny": _zero_cost("Z57 新工作只跑本地后半链，没有新增模型调用。"),
            "strict_score": _strict_score(
                2,
                14,
                "historical_candidate_score",
                "第3章旧14项口径。",
            ),
            "ucr": None,
            "reuse": {
                "used": True,
                "details": "复用 Z56 已完成的20章抽取，20次来源调用不在 Z57 重复计费。",
                "reused_calls": 20,
                "reused_total_tokens": 238556,
                "source_monetary_amount_cny": "missing",
            },
            "comparison": {
                "single_variable_status": "not_applicable_no_new_extraction",
                "known_second_variables": [],
                "limitations": [
                    "Z57 的 0 元只指本轮新增模型工作，不能说来源抽取没有历史成本。",
                    "14项口径不能与后来的23项严格分直接按比例判胜负。",
                ],
            },
            "source_paths": _source_paths(
                tracker, (z57_transport_path, z57_score_path)
            ),
        },
        {
            "row_id": "Z59-A",
            "round_label": "Z59-A 实体供料注入",
            "date": "2026-07-19",
            "sample_scope": "X01 五靶章新样张；第3章按14项金标评分",
            "provider_model": {
                "provider": "sensenova",
                "model": "deepseek-v4-flash",
            },
            "api": _api_usage(
                logical_requests_started=5,
                network_attempts=5,
                accepted_completed_outputs=5,
                usage_bearing_responses=5,
                usage=_tokens(34821, 23851, 58672),
            ),
            "cost_cny": _missing_cost(common_missing_note),
            "strict_score": _strict_score(
                3,
                14,
                "historical_candidate_score",
                "语义复核保留严格3/14；影子召回修正为10/14。",
            ),
            "ucr": None,
            "reuse": {
                "used": False,
                "details": "五个候选样张均为本轮新调用；基线只作比较。",
                "reused_calls": 0,
                "reused_total_tokens": 0,
            },
            "comparison": {
                "single_variable_status": "mechanically_isolated",
                "known_second_variables": [],
                "limitations": [
                    "请求体只新增一条实体供料 system 块，但每章仍只有一个随机样本。",
                    "评分只落在第3章旧14项口径，不代表五章整体质量。",
                ],
            },
            "source_paths": _source_paths(
                tracker,
                (z59_usage_path, z59_cost_path, z59_score_path, z59_diff_path),
            ),
        },
        {
            "row_id": "Z68C",
            "round_label": "Z68C 32k 兼容续跑",
            "date": "2026-07-20",
            "sample_scope": "X01 五靶章混合条件：第3／4章复用16k，第5／13／19章新跑32k",
            "provider_model": {
                "provider": "sensenova",
                "model": "deepseek-v4-flash",
            },
            "api": _api_usage(
                logical_requests_started=3,
                network_attempts=4,
                accepted_completed_outputs=3,
                usage_bearing_responses=3,
                usage=_tokens(27380, 25170, 52550),
                lineage_usage=_tokens(46832, 44510, 91342),
            ),
            "cost_cny": _missing_cost(
                common_missing_note + " 第13章首次429没有 usage，供应商计费也未知。"
            ),
            "strict_score": _strict_score(
                6,
                14,
                "historical_candidate_score",
                "第3章成绩来自复用的16k样张。",
            ),
            "ucr": None,
            "reuse": {
                "used": True,
                "details": "复用第3／4章16k样张；另跑第5／13／19章32k。",
                "reused_calls": 2,
                "reused_total_tokens": 38792,
            },
            "comparison": {
                "single_variable_status": "local_request_diff_only",
                "known_second_variables": [
                    "五章成绩条件混合了复用16k与新跑32k",
                    "相对 Z57 还包含连续请求体供料差异",
                ],
                "limitations": [
                    "max_tokens 的单变量回执只覆盖本续跑请求差异。",
                    "第3章6/14不能归因给32k，因为被评分样张没有重跑32k。",
                ],
            },
            "source_paths": _source_paths(
                tracker,
                (
                    z68_usage_path,
                    z68_reuse_path,
                    z68_transport_path,
                    z68_score_path,
                    z68_variable_path,
                ),
            ),
        },
        {
            "row_id": "Z70",
            "round_label": "Z70 事件句压缩合同",
            "date": "2026-07-21",
            "sample_scope": "X01 五靶章，五章均为本轮32k新样张",
            "provider_model": {
                "provider": "sensenova",
                "model": "deepseek-v4-flash",
            },
            "api": _api_usage(
                logical_requests_started=5,
                network_attempts=5,
                accepted_completed_outputs=5,
                usage_bearing_responses=5,
                usage=_tokens(47082, 47616, 94698),
            ),
            "cost_cny": _missing_cost(common_missing_note),
            "strict_score": _strict_score(
                6,
                14,
                "historical_candidate_score",
                "第3章旧14项口径。",
            ),
            "ucr": None,
            "reuse": {
                "used": False,
                "details": "五章都是新32k样张；Z68C只作历史对照。",
                "reused_calls": 0,
                "reused_total_tokens": 0,
            },
            "comparison": {
                "single_variable_status": "prompt_clause_isolated_in_prepared_requests",
                "known_second_variables": [
                    "相对 Z68C，对照臂是复用16k和新跑32k混合条件",
                    "Z70 五章全是新样张",
                ],
                "limitations": [
                    "机械差异只有一条压缩合同，但结果对比同时受新旧样张条件影响。",
                    "第3章仍是旧14项口径。",
                ],
            },
            "source_paths": _source_paths(
                tracker,
                (
                    z70_usage_path,
                    z70_transport_path,
                    z70_score_path,
                    z70_variable_path,
                ),
            ),
        },
        {
            "row_id": "Z71",
            "round_label": "Z71 z70 语义补全旁路",
            "date": "2026-07-21",
            "sample_scope": "X01 五靶章，Z68C冻结底料加25次旁路调用",
            "provider_model": {
                "provider": "sensenova",
                "model": "deepseek-v4-flash",
            },
            "api": _api_usage(
                logical_requests_started=25,
                network_attempts=25,
                accepted_completed_outputs=25,
                usage_bearing_responses=25,
                usage=_tokens(96739, 61202, 157941),
                lineage_usage=_tokens(143571, 105712, 249283),
            ),
            "cost_cny": _missing_cost(common_missing_note),
            "strict_score": _strict_score(
                6,
                14,
                "historical_candidate_score",
                "第3章旧14项口径。",
            ),
            "ucr": None,
            "reuse": {
                "used": True,
                "details": "复用 Z68C 五章冻结底料91,342 token，本轮新增25次旁路调用。",
                "reused_calls": 5,
                "reused_total_tokens": 91342,
            },
            "comparison": {
                "single_variable_status": "not_single_variable",
                "known_second_variables": [
                    "新增旁路程序结构",
                    "调用粒度从五章主样张改成25个旁路批次",
                ],
                "limitations": [
                    "不是与 Z70 的严格单变量对照。",
                    "血缘 token 含冻结底料，但本轮成本只应算新增157,941 token。",
                ],
            },
            "source_paths": _source_paths(
                tracker, (z71_usage_path, z71_transport_path, z71_score_path)
            ),
        },
        {
            "row_id": "Z79",
            "round_label": "Z79 事实说明书注入包 v3",
            "date": "2026-07-21",
            "sample_scope": "X01 第3／13／19章新样张",
            "provider_model": {
                "provider": "sensenova",
                "model": "deepseek-v4-flash",
            },
            "api": _api_usage(
                logical_requests_started=3,
                network_attempts=4,
                accepted_completed_outputs=3,
                usage_bearing_responses=3,
                usage=_tokens(33438, 37173, 70611),
            ),
            "cost_cny": _missing_cost(common_missing_note + " 另有一次429无 usage。"),
            "strict_score": _strict_score(
                10,
                23,
                "historical_candidate_score",
                "第3章金标v1.2的23项口径。",
            ),
            "ucr": None,
            "reuse": {
                "used": False,
                "details": "正式 retry01 的三章样张均为新调用；失败预发送目录为零调用。",
                "reused_calls": 0,
                "reused_total_tokens": 0,
            },
            "comparison": {
                "single_variable_status": "two_prompt_repair_groups",
                "known_second_variables": [
                    "system 与 user 两处消息都变化",
                    "两组修复规则打包进入同一候选",
                ],
                "limitations": [
                    "不能把10/23拆分归因给某一条规则。",
                    "一次429没有 usage，不能推断该尝试成本为0。",
                ],
            },
            "source_paths": _source_paths(tracker, (z79_usage_path, z79_report_path)),
        },
        {
            "row_id": "Z80",
            "round_label": "Z80 事实说明书注入包 v4／G1",
            "date": "2026-07-21",
            "sample_scope": "只完成 G1 X01 三章；G2、G3未调用",
            "provider_model": {
                "provider": "sensenova",
                "model": "deepseek-v4-flash",
            },
            "api": _api_usage(
                logical_requests_started=3,
                network_attempts=3,
                accepted_completed_outputs=3,
                usage_bearing_responses=3,
                usage=_tokens(33882, 67611, 101493),
            ),
            "cost_cny": _missing_cost(common_missing_note),
            "strict_score": _strict_score(
                6,
                23,
                "historical_candidate_score",
                "只对应 G1 X01 第3章。",
            ),
            "ucr": None,
            "reuse": {
                "used": False,
                "details": "G1 三章均为新调用；G2、G3硬停未发网。",
                "reused_calls": 0,
                "reused_total_tokens": 0,
            },
            "comparison": {
                "single_variable_status": "three_rule_bundle",
                "known_second_variables": [
                    "三条 system 规则同时加入",
                ],
                "limitations": [
                    "三条规则不能逐条归因。",
                    "只跑完 G1，不能写成跨书三组复现结果。",
                ],
            },
            "source_paths": _source_paths(tracker, (z80_usage_path, z80_report_path)),
        },
        {
            "row_id": "Z83-retry13",
            "round_label": "Z83 retry13 双合同原子修复",
            "date": "2026-07-22",
            "sample_scope": "复用三章主样张，新增32次修复调用和3次检查员调用",
            "provider_model": {
                "provider": "sensenova",
                "model": "deepseek-v4-flash",
            },
            "api": _api_usage(
                logical_requests_started=35,
                network_attempts=35,
                accepted_completed_outputs=35,
                usage_bearing_responses=35,
                usage=_tokens(275588, 25689, 301277),
                lineage_usage=_tokens(309026, 75548, 384574),
            ),
            "cost_cny": _missing_cost(common_missing_note),
            "strict_score": _strict_score(
                6,
                23,
                "historical_candidate_hard_stop_score",
                "正式成绩单判候选失败并硬停。",
            ),
            "ucr": None,
            "reuse": {
                "used": True,
                "details": "复用 retry03 的三章主样张83,297 token。",
                "reused_calls": 3,
                "reused_total_tokens": 83297,
            },
            "comparison": {
                "single_variable_status": "not_single_variable",
                "known_second_variables": [
                    "新增32个原子修复请求",
                    "新增3个语义检查员请求",
                    "复用主样张而不是重跑主臂",
                ],
                "limitations": [
                    "不能把结果差异只归到单条修复合同。",
                    "血缘总量384,574 token不等于本轮新增成本口径。",
                ],
            },
            "source_paths": _source_paths(
                tracker,
                (
                    retry13_repair_path,
                    *retry13_inspector_paths,
                    retry13_report_path,
                    retry13_score_path,
                ),
            ),
        },
        {
            "row_id": "Z89",
            "round_label": "Z89 DeepSeek V4 Pro 强模型对照",
            "date": "2026-07-23",
            "sample_scope": "X01 第3章单样本",
            "provider_model": {
                "provider": "DeepSeek official API",
                "model": "deepseek-v4-pro",
            },
            "api": _api_usage(
                logical_requests_started=1,
                network_attempts=1,
                accepted_completed_outputs=1,
                usage_bearing_responses=1,
                usage=_tokens(11030, 26196, 37226),
            ),
            "cost_cny": _estimated_cost(
                0.190266,
                z89_report["transport"]["estimated_cost_cny"]["basis"],
            ),
            "strict_score": _strict_score(
                10,
                23,
                "historical_candidate_score",
                "历史候选银标成绩，不是当前正式金标发布结论。",
            ),
            "ucr": {
                "denominator": 23,
                "formal_score_eligible": False,
                "note": "只准作 Z89 历史离线候选演示；评审非密封盲审。",
                "numerator": 10,
                "status": "historical_offline_candidate_demo",
                "value": 10 / 23,
            },
            "reuse": {
                "used": False,
                "details": "Z89 模型回包为本轮新调用；旧臂只作只读对照。",
                "reused_calls": 0,
                "reused_total_tokens": 0,
            },
            "comparison": {
                "single_variable_status": "not_single_variable",
                "known_second_variables": [
                    "供应商通道变化",
                    "模型从 deepseek-v4-flash 变为 deepseek-v4-pro",
                    "有效推理档从 medium 变为 high",
                ],
                "limitations": [
                    "只有第3章一个样本，不能外推稳定胜率。",
                    "0.190266元只转录历史估算，不能当实付账单。",
                    "UCR 10/23是离线候选演示，不能补写到其他轮次。",
                ],
            },
            "source_paths": _source_paths(
                tracker,
                (z89_usage_path, z89_report_path, z89_score_path, z89_ucr_path),
            ),
        },
        {
            "row_id": "Z94",
            "round_label": "Z94 Flash 局部语义包／腾讯 repair",
            "date": "2026-07-23",
            "sample_scope": "复用三章主样张，新增32次腾讯repair和3次Sensenova检查员",
            "provider_model": {
                "provider": "mixed: tencent_tokenhub + sensenova",
                "model": (
                    "repair=deepseek-v4-flash-202605; inspector=deepseek-v4-flash"
                ),
            },
            "api": _api_usage(
                logical_requests_started=35,
                network_attempts=35,
                accepted_completed_outputs=35,
                usage_bearing_responses=35,
                usage=_tokens(44327, 26757, 71084),
                lineage_usage=_tokens(77765, 76616, 154381),
            ),
            "cost_cny": _missing_cost(common_missing_note),
            "strict_score": _strict_score(
                6,
                23,
                "historical_candidate_hard_stop_score",
                "正式成绩单判候选失败并硬停。",
            ),
            "ucr": None,
            "reuse": {
                "used": True,
                "details": "复用 retry03 的三章 Sensenova 主样张83,297 token。",
                "reused_calls": 3,
                "reused_total_tokens": 83297,
            },
            "comparison": {
                "single_variable_status": "not_single_variable",
                "known_second_variables": ["provider_channel"],
                "limitations": [
                    "repair通道与retry13不同，禁止作严格单变量因果归因。",
                    "新调用71,084 token；血缘总量154,381 token含复用主样张。",
                ],
            },
            "source_paths": _source_paths(
                tracker,
                (
                    z94_main_path,
                    z94_repair_path,
                    *z94_inspector_paths,
                    z94_diagnostic_path,
                    z94_score_path,
                ),
            ),
        },
        {
            "row_id": "Z98",
            "round_label": "Z98 正式执行器预演 r07 v1.3",
            "date": "2026-07-24",
            "sample_scope": "fixture-only 非发送预演",
            "provider_model": {
                "provider": None,
                "model": None,
            },
            "api": _api_usage(
                logical_requests_started=0,
                network_attempts=0,
                accepted_completed_outputs=0,
                usage_bearing_responses=0,
                usage=_tokens(0, 0, 0),
            ),
            "cost_cny": _zero_cost(
                "model_api_calls、network_attempts、provider_catalog_requests均为0；"
                "fixture里的假 token／假费用不计入。"
            ),
            "strict_score": None,
            "ucr": None,
            "reuse": {
                "used": True,
                "details": "只复用本地fixture和输入工件，没有复用在线质量输出。",
                "reused_calls": 0,
                "reused_total_tokens": 0,
            },
            "comparison": {
                "single_variable_status": "not_applicable_quality_not_reached",
                "known_second_variables": [],
                "limitations": [
                    "质量结果为 NOT_RUN_FIXTURE_ONLY／NOT_REACHED。",
                    "fixture数字不可当真实usage、费用或质量成绩。",
                ],
            },
            "source_paths": _source_paths(
                tracker, (z98_receipt_path, z98_manifest_path)
            ),
        },
    ]

    _expect("table B row count", len(rows), 12)
    _expect(
        "table B row ids",
        [row["row_id"] for row in rows],
        [
            "retry03",
            "Z57",
            "Z59-A",
            "Z68C",
            "Z70",
            "Z71",
            "Z79",
            "Z80",
            "Z83-retry13",
            "Z89",
            "Z94",
            "Z98",
        ],
    )
    non_null_ucr = [row["row_id"] for row in rows if row["ucr"] is not None]
    _expect("non-null UCR rows", non_null_ucr, ["Z89"])
    missing_cost_rows = [
        row["row_id"] for row in rows if row["cost_cny"]["status"] == "missing"
    ]
    _expect(
        "missing monetary rows",
        missing_cost_rows,
        [
            "retry03",
            "Z59-A",
            "Z68C",
            "Z70",
            "Z71",
            "Z79",
            "Z80",
            "Z83-retry13",
            "Z94",
        ],
    )
    for row in rows:
        if row["ucr"] is None:
            _expect(f"{row['row_id']} absent UCR", row["ucr"], None)
        if row["cost_cny"]["status"] == "missing":
            _expect(
                f"{row['row_id']} missing cost amount",
                row["cost_cny"]["amount_cny"],
                "missing",
            )

    denominator_14 = [
        row["row_id"]
        for row in rows
        if row["strict_score"] is not None and row["strict_score"]["denominator"] == 14
    ]
    denominator_23 = [
        row["row_id"]
        for row in rows
        if row["strict_score"] is not None and row["strict_score"]["denominator"] == 23
    ]
    unjudged = [row["row_id"] for row in rows if row["strict_score"] is None]
    _expect(
        "14-denominator group",
        denominator_14,
        ["Z57", "Z59-A", "Z68C", "Z70", "Z71"],
    )
    _expect(
        "23-denominator group",
        denominator_23,
        ["retry03", "Z79", "Z80", "Z83-retry13", "Z89", "Z94"],
    )
    _expect("unjudged group", unjudged, ["Z98"])

    return {
        "schema_version": "z99-historical-api-supply-table-b-v1",
        "build_date": BUILD_DATE,
        "accounting_rules": {
            "cost_rule": (
                "只转录历史材料已保存的金额；没有金额就写 missing；不按当前价格反推。"
            ),
            "new_work_vs_lineage": (
                "new_work_usage只算该轮新增模型工作；"
                "lineage_usage_including_reuse另列复用血缘。"
            ),
            "strict_score_rule": ("14项与23项分组展示，不归一化、不混排判胜负。"),
            "ucr_rule": (
                "只有Z89保留历史离线候选演示10/23；其他轮次没有UCR就写null，绝不补0。"
            ),
        },
        "strict_score_groups": {
            "denominator_14": denominator_14,
            "denominator_23": denominator_23,
            "unjudged": unjudged,
        },
        "missing_monetary_items": [
            {
                "row_id": row_id,
                "scope": "this_round_new_model_work",
                "amount_cny": "missing",
            }
            for row_id in missing_cost_rows
        ]
        + [
            {
                "row_id": "Z57",
                "scope": "reused_Z56_source_sampling",
                "amount_cny": "missing",
            }
        ],
        "summary": {
            "denominator_14_rows": len(denominator_14),
            "denominator_23_rows": len(denominator_23),
            "estimated_cost_rows": 1,
            "exact_zero_new_work_cost_rows": 2,
            "missing_new_work_cost_rows": len(missing_cost_rows),
            "row_count": len(rows),
            "ucr_non_null_rows": len(non_null_ucr),
            "unjudged_rows": len(unjudged),
        },
        "rows": rows,
    }


def _cost_label(cost: dict[str, Any]) -> str:
    if cost["status"] == "missing":
        return "missing"
    if cost["status"] == "estimated":
        return f"约¥{cost['amount_cny']:.6f}（estimated）"
    return f"¥{cost['amount_cny']}（新增调用精确为0）"


def _table_b_markdown(table: dict[str, Any]) -> str:
    by_id = {row["row_id"]: row for row in table["rows"]}
    lines = [
        "# Z99 供料表 B｜历史 API 大轮次",
        "",
        "✅ 结论：共 12 行。14项严格分和23项严格分分开摆，Z98 未评分；"
        "没有历史人民币金额的地方统一写 `missing`，没有按当前价格反推。",
        "",
        "UCR 只有 Z89 有一条历史离线候选演示 10/23。其余轮次都写 `null`，"
        "这表示“没有这项成绩”，不是0分。",
        "",
    ]
    for heading, key in (
        ("14项严格分组", "denominator_14"),
        ("23项严格分组", "denominator_23"),
    ):
        lines.extend(
            [
                f"## {heading}",
                "",
                "| 轮次 | 新逻辑请求／网络尝试 | 新工作 token | 人民币金额 | 严格分 | UCR |",
                "|---|---:|---:|---|---:|---|",
            ]
        )
        for row_id in table["strict_score_groups"][key]:
            row = by_id[row_id]
            api = row["api"]
            score = row["strict_score"]
            ucr = row["ucr"]
            ucr_label = (
                "null"
                if ucr is None
                else f"{ucr['numerator']}/{ucr['denominator']}（历史离线候选演示）"
            )
            lines.append(
                f"| {row_id} | {api['logical_requests_started']}／"
                f"{api['network_attempts']} | "
                f"{api['new_work_usage']['total_tokens']:,} | "
                f"{_cost_label(row['cost_cny'])} | "
                f"{score['numerator']}/{score['denominator']} | {ucr_label} |"
            )
        lines.append("")

    lines.extend(
        [
            "## 未评分组",
            "",
            "| 轮次 | 新逻辑请求／网络尝试 | 新工作 token | 人民币金额 | 严格分 | UCR |",
            "|---|---:|---:|---|---|---|",
        ]
    )
    for row_id in table["strict_score_groups"]["unjudged"]:
        row = by_id[row_id]
        api = row["api"]
        lines.append(
            f"| {row_id} | {api['logical_requests_started']}／"
            f"{api['network_attempts']} | "
            f"{api['new_work_usage']['total_tokens']:,} | "
            f"{_cost_label(row['cost_cny'])} | null（质量未到） | null |"
        )

    lines.extend(
        [
            "",
            "## 复用和比较边界",
            "",
        ]
    )
    for row in table["rows"]:
        reuse = row["reuse"]["details"]
        variables = row["comparison"]["known_second_variables"]
        variable_text = "无已登记第二变量" if not variables else "；".join(variables)
        limits = "；".join(row["comparison"]["limitations"])
        lines.append(
            f"- **{row['row_id']}**：复用＝{reuse} "
            f"比较状态＝{row['comparison']['single_variable_status']}。"
            f"第二变量／混杂＝{variable_text}。边界＝{limits}"
        )

    lines.extend(
        [
            "",
            "⚠️ Z57 的新增模型工作确实是0，但它复用了 Z56 的20次历史抽取；"
            "那部分人民币金额仍是 `missing`。",
            "",
            "⚠️ Z89 的约¥0.190266只转录历史回执中的估算，状态只能写 "
            "`estimated`，不能当实付账单。",
            "",
            "来源：Codex",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_core(repo_root: Path) -> dict[str, bytes]:
    tracker = SourceTracker(repo_root)
    table_a = _build_table_a(repo_root, tracker)
    table_b = _build_table_b(repo_root, tracker)
    manifest = tracker.manifest()
    return {
        "table_a_thinking_inputs.json": _json_bytes(table_a),
        "table_a_thinking_inputs.md": _text_bytes(_table_a_markdown(table_a)),
        "table_b_historical_api_rounds.json": _json_bytes(table_b),
        "table_b_historical_api_rounds.md": _text_bytes(_table_b_markdown(table_b)),
        "input_manifest.json": _json_bytes(manifest),
    }


def _build_receipt(core: dict[str, bytes]) -> dict[str, Any]:
    table_a = json.loads(core["table_a_thinking_inputs.json"])
    table_b = json.loads(core["table_b_historical_api_rounds.json"])
    manifest = json.loads(core["input_manifest.json"])
    core_rows = [
        {
            "bytes": len(data),
            "path": name,
            "sha256": _sha256(data),
        }
        for name, data in sorted(core.items())
    ]
    return {
        "schema_version": "z99-supply-tables-acceptance-v1",
        "build_date": BUILD_DATE,
        "status": "PASS",
        "model_api_calls": 0,
        "network_requests": 0,
        "checks": {
            "deterministic_double_build": "PASS_BYTE_IDENTICAL",
            "exact_thinking_file_count": table_a["summary"]["row_count"],
            "table_a_blind_count": table_a["summary"]["blind_rows"],
            "table_a_ucr_count": table_a["summary"]["ucr_rows"],
            "table_b_row_count": table_b["summary"]["row_count"],
            "strict_denominator_14_separate": (
                table_b["summary"]["denominator_14_rows"]
            ),
            "strict_denominator_23_separate": (
                table_b["summary"]["denominator_23_rows"]
            ),
            "strict_unjudged_separate": table_b["summary"]["unjudged_rows"],
            "ucr_non_null_rows": table_b["summary"]["ucr_non_null_rows"],
            "input_source_count": manifest["source_count"],
        },
        "missing_monetary_items": table_b["missing_monetary_items"],
        "core_artifacts": core_rows,
    }


def _receipt_markdown(receipt: dict[str, Any]) -> str:
    checks = receipt["checks"]
    lines = [
        "# Z99 供料表验收票",
        "",
        "✅ 结论：通过。两次独立构建的五个核心文件逐字节一致。",
        "",
        f"- 思考稿：{checks['exact_thinking_file_count']}份"
        f"（UCR {checks['table_a_ucr_count']}份，盲产 "
        f"{checks['table_a_blind_count']}份）",
        f"- 历史 API 表：{checks['table_b_row_count']}行",
        f"- 严格分分组：14项 {checks['strict_denominator_14_separate']}行，"
        f"23项 {checks['strict_denominator_23_separate']}行，"
        f"未评分 {checks['strict_unjudged_separate']}行",
        f"- 非空 UCR：{checks['ucr_non_null_rows']}行，只允许 Z89",
        f"- 输入证据：{checks['input_source_count']}个文件，逐个记录字节数和 SHA-256",
        "- 模型调用：0；网络请求：0",
        "",
        "核心文件哈希：",
        "",
        "| 文件 | 字节 | SHA-256 |",
        "|---|---:|---|",
    ]
    for row in receipt["core_artifacts"]:
        lines.append(f"| `{row['path']}` | {row['bytes']} | `{row['sha256']}` |")
    lines.extend(
        [
            "",
            "金额缺失项详见 `acceptance_receipt.json`。`missing` 不是0元，"
            "而是历史材料没有留下可核人民币金额。",
            "",
            "来源：Codex",
        ]
    )
    return "\n".join(lines) + "\n"


def build_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, bytes]:
    """Build every deliverable in memory and enforce a double-build match."""

    root = repo_root.resolve()
    first = _build_core(root)
    second = _build_core(root)
    _expect("deterministic core artifact names", sorted(first), sorted(second))
    for name in sorted(first):
        _expect(f"deterministic bytes for {name}", first[name], second[name])

    receipt = _build_receipt(first)
    artifacts = dict(first)
    artifacts["acceptance_receipt.json"] = _json_bytes(receipt)
    artifacts["acceptance_receipt.md"] = _text_bytes(_receipt_markdown(receipt))
    _expect(
        "generated artifact names",
        tuple(sorted(artifacts)),
        tuple(sorted(ALL_FILENAMES)),
    )
    return artifacts


def write_artifacts(
    output_dir: Path,
    artifacts: dict[str, bytes],
) -> None:
    """Write only the seven named Z99 artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ALL_FILENAMES:
        (output_dir / name).write_bytes(artifacts[name])


def check_artifacts(
    output_dir: Path,
    artifacts: dict[str, bytes],
) -> None:
    if not output_dir.is_dir():
        raise SourceDataError(f"output directory is missing: {output_dir}")
    observed_names = tuple(
        sorted(path.name for path in output_dir.iterdir() if path.is_file())
    )
    _expect("output file names", observed_names, tuple(sorted(ALL_FILENAMES)))
    for name in ALL_FILENAMES:
        path = output_dir / name
        _expect(f"output bytes for {name}", path.read_bytes(), artifacts[name])


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic Z99 supply tables without network access."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="小说架构仓库根目录。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="交付目录；默认写入 Z99 实验目录下的 supply_tables。",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只核对现有文件，不写文件。",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else repo_root
        / "experiments"
        / "Z99_external_finalization_supply_20260724"
        / "supply_tables"
    )
    artifacts = build_artifacts(repo_root)
    if args.check:
        check_artifacts(output_dir, artifacts)
        print(f"PASS: {len(artifacts)} artifacts match {output_dir}")
    else:
        write_artifacts(output_dir, artifacts)
        print(f"PASS: wrote {len(artifacts)} artifacts to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

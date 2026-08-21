#!/usr/bin/env python3
"""Materialize clean-baseline work order 4 from the current main design surface.

Temporary PR helper. It inventories every design document currently present in
``novel-mvp/design``, records R14 currentness without rewriting any design body,
replaces the human INDEX with a registry-aligned entry, updates the global
pointer, and writes a read-only checker plus focused tests. The workflow removes
this helper before the final commit.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "c79bd0af08b5424baf6e668e3d5dcd06e622a07a"
SOURCE_BRANCH_SHA = "cc793c4719fb6470946c70e744f463147989547b"
UPDATED_AT = "2026-08-21T08:20:00+08:00"
DESIGN_DIR = ROOT / "novel-mvp/design"
INDEX_PATH = DESIGN_DIR / "INDEX.md"
REGISTRY_PATH = DESIGN_DIR / "design_registry.json"
POINTERS_PATH = ROOT / "governance/current_pointers.json"
CHECKER_PATH = ROOT / "tools/check_design_currentness.py"
TEST_PATH = ROOT / "tests/test_design_currentness.py"

EXPECTED_MAIN_INDEX_SHA256 = "fb7b27efc99e2f7fa46112b434922fda0e4da8d72831ffaf9cf543fd599eb22c"

CURRENT = {
    "API_EXPOSURE_DESIGN_R01.md",
    "BOOK_DISSECT_MENU_DESIGN_R01.md",
    "CHAPTER_REVISION_DESIGN_R01.md",
    "CHAPTER_WORKBENCH_DESIGN_R02.md",
    "CHARACTER_LEDGER_DESIGN_R02.md",
    "EXTRACTION_PIPELINE_DESIGN_R01.md",
    "FIRST_SCREEN_SYSTEM_DESIGN_R02.md",
    "GENRE_RHYTHM_PACK_DESIGN_R01.md",
    "GLOBAL_OUTLINE_DESIGN_R01.md",
    "INTAKE_SHELVES_DESIGN_R03.md",
    "MCP_INTERFACE_DESIGN_R01.md",
    "PLUGIN_CONTENT_WORKORDER_R01.md",
    "PLUGIN_SKILL_SYSTEM_DESIGN_R02.md",
    "REVERSE_PLOT_MAP_DESIGN_R02.md",
    "ROLE_POV_MODE_DESIGN_R01.md",
    "SCENE_CARD_EXPORT_DESIGN_R01.md",
    "STOP_POINT_REGISTRY_R03.md",
    "TUTORIAL_SCRIPTS_DESIGN_R02.md",
    "WEB_CANVAS_MVP_DESIGN_R01.md",
}
WAITING_REWRITE = {
    "CONTEXT_PACKER_DESIGN_R01.md",
    "DAILY_LOOP_WALKTHROUGH_R03.md",
    "M8_PLANNING_DESIGN_R04.md",
    "OUTLINE_STRUCTURE_DESIGN_R02.md",
    "PLAN_LEDGER_STORAGE_DESIGN_R04.md",
    "REVIEW_OVERVIEW_DESIGN_R03.md",
    "WRITING_DESK_DESIGN_R04.md",
}
HISTORICAL = {
    "17_EXTERNAL_PROMPTS_AGENT_TOOLS_PIPELINE_20260814_R01.md",
    "18_EXTERNAL_PROMPTS_OUTLINE_LOADBEARING_20260814_R01.md",
    "19_EXTERNAL_PROMPTS_LEDGER_BITE_20260814_R01.md",
    "20_EXTERNAL_PROMPT_R10_2_PATCH_REVIEW_20260814_R01.md",
    "21_EXTERNAL_PROMPT_R10_INTERNAL_SCAN_20260814_R01.md",
}
SUPERSEDED = {
    "CHAPTER_WORKBENCH_DESIGN_R01.md",
    "CHARACTER_LEDGER_DESIGN_R01.md",
    "DAILY_LOOP_WALKTHROUGH_R01.md",
    "DAILY_LOOP_WALKTHROUGH_R02.md",
    "FIRST_SCREEN_SYSTEM_DESIGN_R01.md",
    "IDEA_LEDGER_DESIGN_R01.md",
    "IDEA_LEDGER_DESIGN_R02.md",
    "INTAKE_SHELVES_DESIGN_R01.md",
    "INTAKE_SHELVES_DESIGN_R02.md",
    "M8_PLANNING_DESIGN_R01.md",
    "M8_PLANNING_DESIGN_R02.md",
    "M8_PLANNING_DESIGN_R03.md",
    "OUTLINE_STRUCTURE_DESIGN_R01.md",
    "PLAN_LEDGER_STORAGE_DESIGN_R01.md",
    "PLAN_LEDGER_STORAGE_DESIGN_R02.md",
    "PLAN_LEDGER_STORAGE_DESIGN_R03.md",
    "PLUGIN_SKILL_SYSTEM_DESIGN_R01.md",
    "REVERSE_PLOT_MAP_DESIGN_R01.md",
    "REVIEW_OVERVIEW_DESIGN_R01.md",
    "REVIEW_OVERVIEW_DESIGN_R02.md",
    "STOP_POINT_REGISTRY_R01.md",
    "STOP_POINT_REGISTRY_R02.md",
    "TUTORIAL_SCRIPTS_DESIGN_R01.md",
    "WRITING_DESK_DESIGN_R01.md",
    "WRITING_DESK_DESIGN_R02.md",
    "WRITING_DESK_DESIGN_R03.md",
}

EXPECTED_STATUS_COUNTS = {
    "CURRENT": 19,
    "WAITING_REWRITE": 7,
    "SUPERSEDED": 26,
    "HISTORICAL": 5,
}

LATEST_BY_FAMILY = {
    "CHAPTER_WORKBENCH_DESIGN": "CHAPTER_WORKBENCH_DESIGN_R02.md",
    "CHARACTER_LEDGER_DESIGN": "CHARACTER_LEDGER_DESIGN_R02.md",
    "DAILY_LOOP_WALKTHROUGH": "DAILY_LOOP_WALKTHROUGH_R03.md",
    "FIRST_SCREEN_SYSTEM_DESIGN": "FIRST_SCREEN_SYSTEM_DESIGN_R02.md",
    "INTAKE_SHELVES_DESIGN": "INTAKE_SHELVES_DESIGN_R03.md",
    "M8_PLANNING_DESIGN": "M8_PLANNING_DESIGN_R04.md",
    "OUTLINE_STRUCTURE_DESIGN": "OUTLINE_STRUCTURE_DESIGN_R02.md",
    "PLAN_LEDGER_STORAGE_DESIGN": "PLAN_LEDGER_STORAGE_DESIGN_R04.md",
    "PLUGIN_SKILL_SYSTEM_DESIGN": "PLUGIN_SKILL_SYSTEM_DESIGN_R02.md",
    "REVERSE_PLOT_MAP_DESIGN": "REVERSE_PLOT_MAP_DESIGN_R02.md",
    "REVIEW_OVERVIEW_DESIGN": "REVIEW_OVERVIEW_DESIGN_R03.md",
    "STOP_POINT_REGISTRY": "STOP_POINT_REGISTRY_R03.md",
    "TUTORIAL_SCRIPTS_DESIGN": "TUTORIAL_SCRIPTS_DESIGN_R02.md",
    "WRITING_DESK_DESIGN": "WRITING_DESK_DESIGN_R04.md",
}

PURPOSE = {
    "API_EXPOSURE_DESIGN_R01.md": "API 暴露层；仍是设计，不代表接口已经开放。",
    "BOOK_DISSECT_MENU_DESIGN_R01.md": "拆书菜单与只读分析入口。",
    "CHAPTER_REVISION_DESIGN_R01.md": "外来书稿改稿重导的版本与证据处理参考。",
    "CHAPTER_WORKBENCH_DESIGN_R02.md": "下一章工作台、选线和章级沙箱。",
    "CHARACTER_LEDGER_DESIGN_R02.md": "人物账结构与作者可见操作参考。",
    "EXTRACTION_PIPELINE_DESIGN_R01.md": "外来道六段抽取管线；ADD-021 的 R02 改版另排。",
    "FIRST_SCREEN_SYSTEM_DESIGN_R02.md": "打开项目第一屏、关章门和投影编辑。",
    "GENRE_RHYTHM_PACK_DESIGN_R01.md": "体裁节奏包候选机制。",
    "GLOBAL_OUTLINE_DESIGN_R01.md": "全书大纲引导。",
    "INTAKE_SHELVES_DESIGN_R03.md": "外来材料导入六架；章节架只收外来书稿。",
    "MCP_INTERFACE_DESIGN_R01.md": "MCP 只读与提案接口。",
    "PLUGIN_CONTENT_WORKORDER_R01.md": "后续插件内容候选工单；27 个不是 V0 首发承诺。",
    "PLUGIN_SKILL_SYSTEM_DESIGN_R02.md": "插件机制；V0 仍按 1 套件×8 组件×前三层。",
    "REVERSE_PLOT_MAP_DESIGN_R02.md": "反向剧情投影；修改进入真值前仍需作者确认。",
    "ROLE_POV_MODE_DESIGN_R01.md": "角色视角模式。",
    "SCENE_CARD_EXPORT_DESIGN_R01.md": "场景卡导出边界。",
    "STOP_POINT_REGISTRY_R03.md": "停点登记；P3 不得自动搬剧情。",
    "TUTORIAL_SCRIPTS_DESIGN_R02.md": "教程、激活口径与黄金三章独立台。",
    "WEB_CANVAS_MVP_DESIGN_R01.md": "网页画布目标；完成与性能承诺仍需代码和结果票。",
}

WAITING_NOTE = {
    "CONTEXT_PACKER_DESIGN_R01.md": "等待 M11→章事实稿、M11→章事实稿检查两根取件接缝改版。",
    "DAILY_LOOP_WALKTHROUGH_R03.md": "等待双车道改版；自产章回 M2／M3 的旧路线不得指导施工。",
    "M8_PLANNING_DESIGN_R04.md": "等待边界改版；现行目标是只规划下一章并管理规划账／长线账。",
    "OUTLINE_STRUCTURE_DESIGN_R02.md": "等待账本目录改版；事实账、长线账、规划账要按范围拆开。",
    "PLAN_LEDGER_STORAGE_DESIGN_R04.md": "机械结构可查，但选择卡全文、独立长线账和十本账目录仍待改版。",
    "REVIEW_OVERVIEW_DESIGN_R03.md": "等待驾驶舱改版；M9 只读算指标，M5 只做事实确认。",
    "WRITING_DESK_DESIGN_R04.md": "等待章事实稿改版；正文是可选出口，旧工作稿不能继续当产品名。",
}

PR_C_EXPECTED_CHANGES = [
    {
        "path": "novel-mvp/design/INDEX.md",
        "change_kind": "ENTRY_REFRESH",
        "present_on_main": True,
        "expected_successor": "WORK_ORDER_5_PR_C",
    },
    {
        "path": "novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md",
        "change_kind": "HISTORICAL_DOCUMENT_PATCH",
        "present_on_main": True,
        "expected_successor": "WORK_ORDER_5_PR_C",
    },
    {
        "path": "novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md",
        "change_kind": "NEW_DESIGN",
        "present_on_main": False,
        "expected_successor": "WORK_ORDER_5_PR_C",
    },
    {
        "path": "novel-mvp/design/STOP_POINT_REGISTRY_R03.md",
        "change_kind": "CURRENT_DOCUMENT_PATCH",
        "present_on_main": True,
        "expected_successor": "WORK_ORDER_5_PR_C",
    },
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def family_and_version(filename: str) -> tuple[str, str | None]:
    stem = Path(filename).stem
    match = re.match(r"^(.*)_R(\d+)$", stem)
    if match:
        return match.group(1), f"R{int(match.group(2)):02d}"
    return stem, None


def superseded_by(filename: str) -> dict[str, Any] | None:
    if filename == "IDEA_LEDGER_DESIGN_R02.md":
        return {
            "kind": "EXPECTED_PR_C",
            "path": "novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md",
            "present_on_main": False,
            "reason": "R14 将独立灵感账并入长线账；十本账目录稿由工单 5 PR-C 引入。",
        }
    if filename == "IDEA_LEDGER_DESIGN_R01.md":
        return {
            "kind": "REPOSITORY_PATH",
            "path": "novel-mvp/design/IDEA_LEDGER_DESIGN_R02.md",
            "present_on_main": True,
        }
    family, _ = family_and_version(filename)
    latest = LATEST_BY_FAMILY.get(family)
    if latest is None:
        raise SystemExit(f"SUPERSEDED document has no successor mapping: {filename}")
    return {
        "kind": "REPOSITORY_PATH",
        "path": f"novel-mvp/design/{latest}",
        "present_on_main": True,
    }


def r14_relation(filename: str, status: str) -> dict[str, str]:
    if status == "CURRENT":
        return {
            "state": "RETAINED_CURRENT_UNDER_R14",
            "note": PURPOSE[filename],
            "basis": "main INDEX current route reviewed against R14",
        }
    if status == "WAITING_REWRITE":
        return {
            "state": "R14_REWRITE_REQUIRED",
            "note": WAITING_NOTE[filename],
            "basis": "R14 dual-lane/truth-layer correction and design INDEX annotation",
        }
    if status == "HISTORICAL":
        return {
            "state": "OUTSIDE_CURRENT_PRODUCT_ROUTE",
            "note": "外发调查题／审查 Prompt，只作历史研究材料，不是现行设计、合同或施工入口。",
            "basis": "design INDEX labels 17–21 as external research prompts",
        }
    return {
        "state": "NOT_CURRENT_REPLACED_OR_RETIRING",
        "note": "旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。",
        "basis": "design INDEX historical-version chain and R14 currentness review",
    }


def build_registry() -> dict[str, Any]:
    original_index_sha = sha256(INDEX_PATH)
    if original_index_sha != EXPECTED_MAIN_INDEX_SHA256:
        raise SystemExit(
            "main design INDEX changed after WO4 planning: "
            f"expected {EXPECTED_MAIN_INDEX_SHA256}, got {original_index_sha}"
        )

    actual = {
        path.name
        for path in DESIGN_DIR.glob("*.md")
        if path.name != "INDEX.md"
    }
    expected = CURRENT | WAITING_REWRITE | HISTORICAL | SUPERSEDED
    if actual != expected:
        raise SystemExit(
            "WO4 design inventory mismatch: "
            f"missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
        )
    if len(actual) != 57:
        raise SystemExit(f"expected 57 design documents, found {len(actual)}")

    documents: list[dict[str, Any]] = []
    for filename in sorted(actual):
        if filename in CURRENT:
            status = "CURRENT"
        elif filename in WAITING_REWRITE:
            status = "WAITING_REWRITE"
        elif filename in HISTORICAL:
            status = "HISTORICAL"
        else:
            status = "SUPERSEDED"
        family, version = family_and_version(filename)
        path = DESIGN_DIR / filename
        row: dict[str, Any] = {
            "design_id": Path(filename).stem,
            "path": f"novel-mvp/design/{filename}",
            "family": family,
            "version": version,
            "status": status,
            "default_route": status == "CURRENT",
            "superseded_by": superseded_by(filename) if status == "SUPERSEDED" else None,
            "r14_relation": r14_relation(filename, status),
            "body_sha256": sha256(path),
            "source_basis": [
                "novel-mvp/design/INDEX.md@main-before-WO4",
                "references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md",
            ],
        }
        if filename == "INTAKE_SHELVES_DESIGN_R02.md":
            row["expected_pr_c_change"] = "HISTORICAL_DOCUMENT_PATCH"
        if filename == "STOP_POINT_REGISTRY_R03.md":
            row["expected_pr_c_change"] = "CURRENT_DOCUMENT_PATCH"
        documents.append(row)

    counts = Counter(row["status"] for row in documents)
    if dict(counts) != EXPECTED_STATUS_COUNTS:
        raise SystemExit(f"unexpected design status counts: {dict(counts)}")

    return {
        "schema_version": "design-currentness-registry-v1",
        "registry_id": "NOVEL_MVP_DESIGN_CURRENTNESS_20260821_R01",
        "authority": "CURRENTNESS_ROUTING_ONLY_NO_PRODUCT_OR_EXECUTION_AUTHORITY",
        "review_status": "CANDIDATE_REVIEWED",
        "updated_at": UPDATED_AT,
        "base_commit": BASE_SHA,
        "product_background": {
            "version": "R14",
            "path": "references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md",
        },
        "index_path": "novel-mvp/design/INDEX.md",
        "checker_path": "tools/check_design_currentness.py",
        "claim_boundary": (
            "CURRENT means the document may be used as the default design reference under its recorded R14 boundary. "
            "It does not prove implementation, author usability, semantic quality, or construction authorization."
        ),
        "status_definitions": {
            "CURRENT": "May appear in the default design route; still subordinate to R14, contracts, current code, and formal results.",
            "WAITING_REWRITE": "Kept for history and partial mechanics; must be rewritten to R14 before related module code work.",
            "SUPERSEDED": "Replaced or retired from the current route; follow superseded_by.",
            "HISTORICAL": "Research/history artifact outside the product design route.",
        },
        "nearby_rewrite_rule": {
            "rule": "哪个模块要开工，先把它的设计稿升到 R14 口径并把 registry 状态改为 CURRENT，才准动该模块代码。",
            "enforcement": "INDEX default route must contain CURRENT documents only; checker fails closed on non-current default routes.",
            "does_not_authorize": ["runtime changes", "contract changes", "product decisions"],
        },
        "inventory": {
            "document_count": len(documents),
            "status_counts": dict(sorted(counts.items())),
            "default_route_count": sum(row["default_route"] for row in documents),
        },
        "expected_work_order_5_pr_c_changes": {
            "source_branch": "codex/module-runtime-foundation-20260819-r01",
            "source_commit": SOURCE_BRANCH_SHA,
            "identity": "READ_ONLY_EXPECTED_SUCCESSORS_NOT_ADMITTED_BY_WO4",
            "changes": PR_C_EXPECTED_CHANGES,
        },
        "documents": documents,
    }


def escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def link_for(row: dict[str, Any]) -> str:
    filename = Path(row["path"]).name
    return f"[{filename}]({filename})"


def build_index(registry: dict[str, Any]) -> str:
    rows = registry["documents"]
    by_status: dict[str, list[dict[str, Any]]] = {
        status: [row for row in rows if row["status"] == status]
        for status in ("CURRENT", "WAITING_REWRITE", "SUPERSEDED", "HISTORICAL")
    }
    lines = [
        "# 设计稿总索引｜R14 currentness 登记 R01",
        "",
        "> 更新：2026-08-21。产品语义只认背景板 **R14**。本页与 `design_registry.json` 是同一份 currentness 登记的两种视图；设计稿不是产品完成态，也不是施工放行票。",
        "> 本票不改任何设计稿正文。模块分支 `cc793c4` 的四个 design surface 只登记为工单 5 PR-C 的预期后继，不在本票带入。",
        "",
        "## 就近重写规则（开工硬门）",
        "",
        "**哪个模块要开工，先把它的设计稿升到 R14 口径，并把 `design_registry.json` 中该稿状态改成 `CURRENT`，才准动模块代码。**",
        "",
        "- `WAITING_REWRITE`、`HISTORICAL`、`SUPERSEDED` 一律不能进入默认施工路由。",
        "- `CURRENT` 只表示可作默认设计参考；不能外推成代码完成、作者可用、真实语义通过或已获施工授权。",
        "- 机器检查：`uv run --locked python tools/check_design_currentness.py --check`。",
        "- 工具正式并入 `governance/tool_registry.json` 留到工单 7。",
        "",
        "## 默认设计路由（只允许 CURRENT）",
        "",
        "<!-- DESIGN_DEFAULT_ROUTES_START -->",
        "| 设计稿 | 状态 | R14 下的用途／边界 |",
        "|---|---|---|",
    ]
    for row in by_status["CURRENT"]:
        lines.append(
            f"| {link_for(row)} | `CURRENT` | {escape_table(row['r14_relation']['note'])} |"
        )
    lines.extend(
        [
            "<!-- DESIGN_DEFAULT_ROUTES_END -->",
            "",
            "## 等待 R14 改版（禁止默认施工）",
            "",
            "| 设计稿 | 状态 | 为什么要先改 |",
            "|---|---|---|",
        ]
    )
    for row in by_status["WAITING_REWRITE"]:
        lines.append(
            f"| {link_for(row)} | `WAITING_REWRITE` | {escape_table(row['r14_relation']['note'])} |"
        )
    lines.extend(
        [
            "",
            "## 工单 5 PR-C 的四个预期 design surface",
            "",
            "这些只是只读登记，不代表文件已经进入 main：",
            "",
            "| 路径 | 变化 | main 当前是否存在 | 预期后继 |",
            "|---|---|---|---|",
        ]
    )
    for item in registry["expected_work_order_5_pr_c_changes"]["changes"]:
        lines.append(
            f"| `{item['path']}` | `{item['change_kind']}` | `{str(item['present_on_main']).lower()}` | `{item['expected_successor']}` |"
        )
    lines.extend(
        [
            "",
            "## 全量机器登记镜像",
            "",
            "下表覆盖当前 `novel-mvp/design/` 下全部 57 份设计／调查文档，不含本索引和 registry 自身。状态和 `superseded_by` 必须与 JSON 一致。",
            "",
            "<!-- DESIGN_STATUS_TABLE_START -->",
            "| 设计稿 | status | superseded_by | R14 relation |",
            "|---|---|---|---|",
        ]
    )
    for row in rows:
        successor = row["superseded_by"]
        successor_text = "—" if successor is None else successor["path"]
        lines.append(
            f"| {link_for(row)} | `{row['status']}` | `{escape_table(successor_text)}` | {escape_table(row['r14_relation']['note'])} |"
        )
    lines.extend(
        [
            "<!-- DESIGN_STATUS_TABLE_END -->",
            "",
            "## 待开新稿（不在当前文件清单）",
            "",
            "- `EXTRACTION_PIPELINE_R02`（ADD-021 四件）",
            "- 一致性体检原型设计（ADD-027.5）",
            "- `LEDGER_DIRECTORY_DESIGN_R01.md`：只读登记为工单 5 PR-C 预期新增，未进入本票。",
            "",
            "来源：ChatGPT（工单 4 云端候选；依据 main INDEX、R14 与 cc793c4 的只读设计差量登记）",
            "",
        ]
    )
    return "\n".join(lines)


def update_current_pointer(registry: dict[str, Any]) -> None:
    data = json.loads(POINTERS_PATH.read_text(encoding="utf-8"))
    data["updated_at"] = UPDATED_AT
    rows = data.get("pointers")
    if not isinstance(rows, list):
        raise SystemExit("current_pointers.pointers is not a list")
    matches = [row for row in rows if isinstance(row, dict) and row.get("pointer_id") == "design_registry"]
    if len(matches) != 1:
        raise SystemExit(f"expected one design_registry pointer, found {len(matches)}")
    row = matches[0]
    row.clear()
    row.update(
        {
            "pointer_id": "design_registry",
            "status": "ACTIVE_CURRENT",
            "version": "R01",
            "path": "novel-mvp/design/design_registry.json",
            "index_path": "novel-mvp/design/INDEX.md",
            "document_count": registry["inventory"]["document_count"],
            "status_counts": registry["inventory"]["status_counts"],
            "checker_path": "tools/check_design_currentness.py",
            "checker_registry_status": "PENDING_WORK_ORDER_7",
            "authority": "CURRENTNESS_ROUTING_ONLY_NO_PRODUCT_OR_EXECUTION_AUTHORITY",
            "admitted_by_work_order": 4,
            "boundary": "CURRENT 只允许进入默认设计路由；不证明实现、语义质量或施工授权。",
        }
    )
    invariants = data.setdefault("invariants", [])
    invariant = "设计默认路由只能指向 design_registry 中的 CURRENT；其他状态一律不得指导施工。"
    if invariant not in invariants:
        invariants.append(invariant)
    write_json(POINTERS_PATH, data)


CHECKER_SOURCE = r'''#!/usr/bin/env python3
"""Read-only validator for the R14 design-currentness registry and INDEX route."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

STATUSES = {"CURRENT", "WAITING_REWRITE", "HISTORICAL", "SUPERSEDED"}
DEFAULT_START = "<!-- DESIGN_DEFAULT_ROUTES_START -->"
DEFAULT_END = "<!-- DESIGN_DEFAULT_ROUTES_END -->"
TABLE_START = "<!-- DESIGN_STATUS_TABLE_START -->"
TABLE_END = "<!-- DESIGN_STATUS_TABLE_END -->"
EXCLUDED_MARKDOWN = {"INDEX.md"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def issue(level: str, code: str, message: str, path: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path is not None:
        value["path"] = path
    return value


def between(text: str, start: str, end: str) -> str | None:
    if text.count(start) != 1 or text.count(end) != 1:
        return None
    return text.split(start, 1)[1].split(end, 1)[0]


def linked_paths(section: str) -> list[str]:
    return [
        f"novel-mvp/design/{match}"
        for match in re.findall(r"\]\(([^)]+\.md)\)", section)
    ]


def status_table(section: str) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = re.compile(r"\]\(([^)]+\.md)\)\s*\|\s*`(CURRENT|WAITING_REWRITE|HISTORICAL|SUPERSEDED)`")
    for filename, status in pattern.findall(section):
        path = f"novel-mvp/design/{filename}"
        if path in result:
            raise ValueError(f"duplicate INDEX status row: {path}")
        result[path] = status
    return result


def build_report(
    root: Path,
    registry_override: dict[str, Any] | None = None,
    index_override: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    design_dir = root / "novel-mvp/design"
    registry_path = design_dir / "design_registry.json"
    index_path = design_dir / "INDEX.md"

    if registry_override is None:
        if not registry_path.is_file():
            return {
                "schema_version": "design-currentness-check-report-v1",
                "status": "FAIL",
                "errors": [issue("ERROR", "REGISTRY_MISSING", "design registry is missing", str(registry_path))],
                "warnings": [],
            }
        registry = load_json(registry_path)
    else:
        registry = registry_override
    index_text = index_path.read_text(encoding="utf-8") if index_override is None else index_override

    if registry.get("schema_version") != "design-currentness-registry-v1":
        errors.append(issue("ERROR", "SCHEMA_VERSION", "unexpected registry schema version"))
    if registry.get("review_status") != "CANDIDATE_REVIEWED":
        errors.append(issue("ERROR", "REVIEW_STATUS", "review_status must be CANDIDATE_REVIEWED"))
    product = registry.get("product_background", {})
    if product.get("version") != "R14":
        errors.append(issue("ERROR", "PRODUCT_BACKGROUND", "design registry must be reviewed against R14"))

    rows = registry.get("documents")
    if not isinstance(rows, list):
        errors.append(issue("ERROR", "DOCUMENTS_TYPE", "documents must be a list"))
        rows = []

    actual = {
        f"novel-mvp/design/{path.name}"
        for path in design_dir.glob("*.md")
        if path.name not in EXCLUDED_MARKDOWN
    }
    paths: list[str] = []
    by_path: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(issue("ERROR", "ROW_SCHEMA", f"row {position} is not an object"))
            continue
        path = row.get("path")
        if not isinstance(path, str) or not path:
            errors.append(issue("ERROR", "PATH_FIELD", f"row {position} has no path"))
            continue
        paths.append(path)
        by_path[path] = row
        status = row.get("status")
        if status not in STATUSES:
            errors.append(issue("ERROR", "STATUS_ENUM", f"invalid status {status!r}", path))
        if not isinstance(row.get("r14_relation"), dict) or not row["r14_relation"].get("state") or not row["r14_relation"].get("note"):
            errors.append(issue("ERROR", "R14_RELATION", "r14_relation must contain state and note", path))
        if "superseded_by" not in row:
            errors.append(issue("ERROR", "SUPERSEDED_BY_FIELD", "superseded_by field is required", path))
        successor = row.get("superseded_by")
        if status == "SUPERSEDED":
            if not isinstance(successor, dict) or not successor.get("path"):
                errors.append(issue("ERROR", "SUPERSEDED_WITHOUT_SUCCESSOR", "SUPERSEDED requires a successor", path))
            elif successor.get("kind") == "REPOSITORY_PATH" and not (root / successor["path"]).is_file():
                errors.append(issue("ERROR", "SUCCESSOR_MISSING", "repository successor is missing", successor["path"]))
        elif successor is not None:
            errors.append(issue("ERROR", "NON_SUPERSEDED_HAS_SUCCESSOR", "only SUPERSEDED rows may set superseded_by", path))
        default_route = row.get("default_route")
        if not isinstance(default_route, bool):
            errors.append(issue("ERROR", "DEFAULT_ROUTE_FIELD", "default_route must be boolean", path))
        elif default_route != (status == "CURRENT"):
            errors.append(issue("ERROR", "DEFAULT_ROUTE_STATUS", "default_route must be true exactly for CURRENT", path))
        file_path = root / path
        if not file_path.is_file():
            errors.append(issue("ERROR", "REGISTERED_FILE_MISSING", "registered design file is missing", path))
        elif row.get("body_sha256") != sha256(file_path):
            errors.append(issue("ERROR", "BODY_SHA_DRIFT", "design body changed without registry refresh", path))

    duplicates = sorted({path for path in paths if paths.count(path) > 1})
    if duplicates:
        errors.append(issue("ERROR", "DUPLICATE_PATHS", str(duplicates)))
    registered = set(paths)
    if registered != actual:
        if missing := sorted(actual - registered):
            errors.append(issue("ERROR", "UNREGISTERED_DESIGN", str(missing)))
        if extra := sorted(registered - actual):
            errors.append(issue("ERROR", "REGISTRY_EXTRA_PATH", str(extra)))

    default_section = between(index_text, DEFAULT_START, DEFAULT_END)
    if default_section is None:
        errors.append(issue("ERROR", "DEFAULT_ROUTE_MARKERS", "INDEX default-route markers are missing or duplicated"))
        default_paths: list[str] = []
    else:
        default_paths = linked_paths(default_section)
        if len(default_paths) != len(set(default_paths)):
            errors.append(issue("ERROR", "DUPLICATE_DEFAULT_ROUTE", "INDEX default route contains duplicate files"))
        for path in default_paths:
            status = by_path.get(path, {}).get("status")
            if status != "CURRENT":
                errors.append(issue("ERROR", "DEFAULT_ROUTE_NON_CURRENT", f"default route points to {status}", path))
        registry_defaults = {path for path, row in by_path.items() if row.get("default_route") is True}
        if set(default_paths) != registry_defaults:
            errors.append(issue("ERROR", "DEFAULT_ROUTE_MISMATCH", f"INDEX={sorted(default_paths)} registry={sorted(registry_defaults)}"))

    table_section = between(index_text, TABLE_START, TABLE_END)
    if table_section is None:
        errors.append(issue("ERROR", "STATUS_TABLE_MARKERS", "INDEX full-table markers are missing or duplicated"))
    else:
        try:
            index_status = status_table(table_section)
        except ValueError as exc:
            errors.append(issue("ERROR", "INDEX_STATUS_DUPLICATE", str(exc)))
            index_status = {}
        registry_status = {path: row.get("status") for path, row in by_path.items()}
        if index_status != registry_status:
            errors.append(issue("ERROR", "INDEX_REGISTRY_STATUS_MISMATCH", "INDEX status table and registry differ"))

    status_counts = Counter(row.get("status") for row in rows if isinstance(row, dict))
    inventory = registry.get("inventory", {})
    if inventory.get("document_count") != len(rows):
        errors.append(issue("ERROR", "INVENTORY_COUNT", "inventory document_count differs from rows"))
    if inventory.get("status_counts") != dict(sorted(status_counts.items())):
        errors.append(issue("ERROR", "INVENTORY_STATUS_COUNTS", "inventory status_counts differs from rows"))

    pr_c = registry.get("expected_work_order_5_pr_c_changes", {}).get("changes")
    if not isinstance(pr_c, list) or len(pr_c) != 4:
        errors.append(issue("ERROR", "PR_C_EXPECTED_CHANGES", "registry must record four read-only PR-C design surfaces"))

    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": "design-currentness-check-report-v1",
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "document_count": len(rows),
            "registered_unique_paths": len(set(paths)),
            "default_route_count": len(default_paths),
            "status_counts": dict(sorted(status_counts.items())),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
    }


def render_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Design currentness check",
        "",
        f"- status: `{report.get('status')}`",
        f"- documents: `{summary.get('document_count', 0)}`",
        f"- unique paths: `{summary.get('registered_unique_paths', 0)}`",
        f"- default routes: `{summary.get('default_route_count', 0)}`",
        f"- status counts: `{json.dumps(summary.get('status_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- errors: `{summary.get('error_count', len(report.get('errors', [])))}`",
        f"- warnings: `{summary.get('warning_count', len(report.get('warnings', [])))}`",
    ]
    if report.get("errors"):
        lines.extend(["", "## Errors"])
        for item in report["errors"]:
            lines.append(f"- `{item['code']}` `{item.get('path', '-')}` {item['message']}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("summary", "json", "both"), default="summary")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.root)
    summary = render_summary(report)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(summary, encoding="utf-8")
    if args.format in {"json", "both"}:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.format in {"summary", "both"}:
        print(summary, end="")
    if args.check:
        print(
            f"{'PASS_DESIGN_CURRENTNESS' if report['status'] == 'PASS' else 'FAIL_DESIGN_CURRENTNESS'} "
            f"errors={len(report.get('errors', []))} warnings={len(report.get('warnings', []))}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


TEST_SOURCE = r'''from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/check_design_currentness.py"
SPEC = importlib.util.spec_from_file_location("check_design_currentness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REGISTRY = json.loads((ROOT / "novel-mvp/design/design_registry.json").read_text(encoding="utf-8"))
INDEX = (ROOT / "novel-mvp/design/INDEX.md").read_text(encoding="utf-8")


def codes(report: dict) -> set[str]:
    return {item["code"] for item in report["errors"]}


def test_repository_design_currentness_passes() -> None:
    report = MODULE.build_report(ROOT)
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["summary"]["document_count"] == 57
    assert report["summary"]["status_counts"] == {
        "CURRENT": 19,
        "HISTORICAL": 5,
        "SUPERSEDED": 26,
        "WAITING_REWRITE": 7,
    }


def test_duplicate_registry_path_is_error() -> None:
    value = copy.deepcopy(REGISTRY)
    value["documents"][1]["path"] = value["documents"][0]["path"]
    report = MODULE.build_report(ROOT, value, INDEX)
    assert "DUPLICATE_PATHS" in codes(report)


def test_missing_registry_row_is_error() -> None:
    value = copy.deepcopy(REGISTRY)
    value["documents"].pop()
    value["inventory"]["document_count"] -= 1
    report = MODULE.build_report(ROOT, value, INDEX)
    assert "UNREGISTERED_DESIGN" in codes(report)


def test_invalid_status_is_error() -> None:
    value = copy.deepcopy(REGISTRY)
    value["documents"][0]["status"] = "MAYBE"
    report = MODULE.build_report(ROOT, value, INDEX)
    assert "STATUS_ENUM" in codes(report)


def test_index_default_route_to_waiting_is_error() -> None:
    waiting = next(row for row in REGISTRY["documents"] if row["status"] == "WAITING_REWRITE")
    filename = Path(waiting["path"]).name
    injected = INDEX.replace(
        "<!-- DESIGN_DEFAULT_ROUTES_END -->",
        f"| [{filename}]({filename}) | `CURRENT` | injected bad route |\n<!-- DESIGN_DEFAULT_ROUTES_END -->",
        1,
    )
    report = MODULE.build_report(ROOT, copy.deepcopy(REGISTRY), injected)
    assert "DEFAULT_ROUTE_NON_CURRENT" in codes(report)


def test_index_status_disagreement_is_error() -> None:
    current = next(row for row in REGISTRY["documents"] if row["status"] == "CURRENT")
    filename = Path(current["path"]).name
    broken = INDEX.replace(
        f"]({filename}) | `CURRENT` |",
        f"]({filename}) | `HISTORICAL` |",
        1,
    )
    report = MODULE.build_report(ROOT, copy.deepcopy(REGISTRY), broken)
    assert "INDEX_REGISTRY_STATUS_MISMATCH" in codes(report)


def test_checker_is_read_only() -> None:
    tracked = [
        ROOT / "novel-mvp/design/design_registry.json",
        ROOT / "novel-mvp/design/INDEX.md",
        ROOT / "governance/current_pointers.json",
    ]
    before = {path: path.read_bytes() for path in tracked}
    MODULE.build_report(ROOT)
    after = {path: path.read_bytes() for path in tracked}
    assert before == after
'''


def main() -> None:
    required = [
        INDEX_PATH,
        POINTERS_PATH,
        ROOT / "references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md",
    ]
    for path in required:
        if not path.is_file():
            raise SystemExit(f"required WO4 input is missing: {path.relative_to(ROOT)}")

    registry = build_registry()
    write_json(REGISTRY_PATH, registry)
    INDEX_PATH.write_text(build_index(registry), encoding="utf-8")
    update_current_pointer(registry)
    CHECKER_PATH.write_text(CHECKER_SOURCE, encoding="utf-8")
    TEST_PATH.write_text(TEST_SOURCE, encoding="utf-8")

    print("PASS_WO4_MATERIALIZATION")
    print(f"documents={registry['inventory']['document_count']}")
    print("status_counts=" + json.dumps(registry["inventory"]["status_counts"], sort_keys=True))
    print(f"default_routes={registry['inventory']['default_route_count']}")
    print("expected_pr_c_design_surfaces=4")


if __name__ == "__main__":
    main()

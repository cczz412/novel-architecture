#!/usr/bin/env python3
"""Apply clean-baseline work order 5 PR-C without bringing runtime code.

Temporary branch helper. It copies the frozen product architecture, four declared
design surfaces, and three coupled contract deltas from cc793c4; synthesizes the
post-WO4 INDEX/registry view; writes a current-vs-target gap sheet; and adds a
small README route. GitHub Actions removes this helper before the final commit.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "cc793c4719fb6470946c70e744f463147989547b"
BASE = "7eca07a64b31078d51eb7dd6f7b509ede967a704"
UPDATED_AT = "2026-08-21T18:20:00+08:00"

COPIED_PATHS = (
    "novel-mvp/ARCHITECTURE.md",
    "novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md",
    "novel-mvp/design/STOP_POINT_REGISTRY_R03.md",
    "novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md",
    "novel-mvp/contracts/C1_CHAPTER_DOC.md",
    "novel-mvp/contracts/WORK_DRAFT_HANDOVER_ACTION.md",
    "novel-mvp/contracts/validate_c11_chapter_revision_ledger.py",
)

DESIGN_DIR = ROOT / "novel-mvp/design"
REGISTRY_PATH = DESIGN_DIR / "design_registry.json"
INDEX_PATH = DESIGN_DIR / "INDEX.md"
README_PATH = ROOT / "novel-mvp/README.md"
GAP_PATH = ROOT / "novel-mvp/CURRENT_VS_TARGET_R01.md"
GAP_SOURCE = ROOT / (
    "work/advisory_returns_20260820_r01/current_runtime_gap_review_r01/"
    "CURRENT_RUNTIME_GAP_REGISTER_R01.json"
)

DEFAULT_START = "<!-- DESIGN_DEFAULT_ROUTES_START -->"
DEFAULT_END = "<!-- DESIGN_DEFAULT_ROUTES_END -->"
TABLE_START = "<!-- DESIGN_STATUS_TABLE_START -->"
TABLE_END = "<!-- DESIGN_STATUS_TABLE_END -->"


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def copy_from_source(path: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    blob = subprocess.check_output(["git", "show", f"{SOURCE}:{path}"], cwd=ROOT)
    target.write_bytes(blob)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replace_between(text: str, start: str, end: str, body: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise SystemExit(f"marker pair missing or duplicated: {start} / {end}")
    before, remainder = text.split(start, 1)
    _, after = remainder.split(end, 1)
    return before + start + "\n" + body.rstrip() + "\n" + end + after


def superseded_display(row: dict[str, Any]) -> str:
    successor = row.get("superseded_by")
    if not isinstance(successor, dict):
        return "—"
    return str(successor.get("path") or successor.get("ticket") or "—")


def add_source_basis(row: dict[str, Any], item: str) -> None:
    basis = row.get("source_basis")
    if not isinstance(basis, list):
        basis = []
    if item not in basis:
        basis.append(item)
    row["source_basis"] = basis


def update_registry() -> dict[str, Any]:
    registry = load_json(REGISTRY_PATH)
    rows = registry.get("documents")
    if not isinstance(rows, list):
        raise SystemExit("design_registry documents must be a list")
    by_path = {row.get("path"): row for row in rows if isinstance(row, dict)}

    ledger_path = "novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md"
    if ledger_path in by_path:
        raise SystemExit("ledger directory design unexpectedly existed before PR-C")
    ledger_row = {
        "design_id": "LEDGER_DIRECTORY_DESIGN_R01",
        "path": ledger_path,
        "family": "LEDGER_DIRECTORY_DESIGN",
        "version": "R01",
        "status": "CURRENT",
        "default_route": True,
        "superseded_by": None,
        "r14_relation": {
            "state": "ADMITTED_CURRENT_BY_WORK_ORDER_5_PR_C",
            "note": "账本目录、10 本固定账、统一取件窗口、简装／精装和插件接法；不是 M12，也不证明 runtime 已接线。",
            "basis": "cc793c4 product-architecture delta reviewed against R14 and admitted by PR-C",
        },
        "body_sha256": sha256(ROOT / ledger_path),
        "source_basis": [
            f"{SOURCE}:{ledger_path}",
            "references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md",
            "novel-mvp/CURRENT_VS_TARGET_R01.md",
        ],
    }
    rows.append(ledger_row)
    by_path[ledger_path] = ledger_row

    changed_designs = (
        "novel-mvp/design/STOP_POINT_REGISTRY_R03.md",
        "novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md",
    )
    for path in changed_designs:
        row = by_path.get(path)
        if not isinstance(row, dict):
            raise SystemExit(f"registry row missing: {path}")
        row["body_sha256"] = sha256(ROOT / path)
        add_source_basis(row, f"{SOURCE}:{path}")
        row["last_body_refresh"] = {
            "work_order": "WORK_ORDER_5_PR_C",
            "source_commit": SOURCE,
            "status_preserved": row.get("status"),
        }

    intake = by_path["novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md"]
    if intake.get("status") != "SUPERSEDED" or intake.get("default_route") is not False:
        raise SystemExit("historical intake R02 status must not be upgraded")
    stop = by_path["novel-mvp/design/STOP_POINT_REGISTRY_R03.md"]
    if stop.get("status") != "CURRENT" or stop.get("default_route") is not True:
        raise SystemExit("stop-point R03 current status must be preserved")

    pr_c = registry.get("expected_work_order_5_pr_c_changes")
    if not isinstance(pr_c, dict) or len(pr_c.get("changes", [])) != 4:
        raise SystemExit("registry does not expose the four WO5 PR-C changes")
    pr_c["identity"] = "ADMITTED_BY_WORK_ORDER_5_PR_C"
    pr_c["admission"] = {
        "base_commit": BASE,
        "source_commit": SOURCE,
        "scope": "PRODUCT_ARCHITECTURE_DESIGN_AND_COUPLED_CONTRACTS_NO_RUNTIME",
    }
    for item in pr_c["changes"]:
        path = item["path"]
        item["present_on_main_after_merge"] = True
        item["applied_by"] = "WORK_ORDER_5_PR_C"
        item["source_commit"] = SOURCE
        item["status"] = "APPLIED_IN_CANDIDATE_PR"
        if path != "novel-mvp/design/INDEX.md":
            item["body_sha256"] = sha256(ROOT / path)
            item["byte_identity"] = "FROZEN_SOURCE_EXACT"
        else:
            item["byte_identity"] = "SYNTHESIZED_ON_POST_WO4_INDEX"

    rows.sort(key=lambda row: row["path"])
    counts = Counter(row["status"] for row in rows)
    registry["updated_at"] = UPDATED_AT
    registry["base_commit"] = BASE
    registry["last_admission"] = {
        "work_order": "WORK_ORDER_5_PR_C",
        "source_commit": SOURCE,
        "note": "ARCHITECTURE and three design bodies were copied exactly; INDEX was synthesized to preserve the R14 registry format.",
    }
    registry["inventory"] = {
        "document_count": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "default_route_count": sum(row.get("default_route") is True for row in rows),
    }
    write_json(REGISTRY_PATH, registry)
    return registry


def render_default_routes(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| 设计稿 | 状态 | R14 下的用途／边界 |",
        "|---|---|---|",
    ]
    for row in sorted((row for row in rows if row.get("default_route") is True), key=lambda row: row["path"]):
        filename = Path(row["path"]).name
        note = str(row["r14_relation"]["note"]).replace("|", "／")
        lines.append(f"| [{filename}]({filename}) | `CURRENT` | {note} |")
    return "\n".join(lines)


def render_status_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| 设计稿 | status | superseded_by | R14 relation |",
        "|---|---|---|---|",
    ]
    for row in sorted(rows, key=lambda row: row["path"]):
        filename = Path(row["path"]).name
        note = str(row["r14_relation"]["note"]).replace("|", "／")
        successor = superseded_display(row).replace("|", "／")
        lines.append(
            f"| [{filename}]({filename}) | `{row['status']}` | `{successor}` | {note} |"
        )
    return "\n".join(lines)


def update_index(registry: dict[str, Any]) -> None:
    text = INDEX_PATH.read_text(encoding="utf-8")
    text = text.replace(
        "# 设计稿总索引｜R14 currentness 登记 R01",
        "# 设计稿总索引｜R14 currentness 登记 R02（PR-C 产品架构＋账本目录）",
        1,
    )
    old_intro = (
        "> 本票不改任何设计稿正文。模块分支 `cc793c4` 的四个 design surface "
        "只登记为工单 5 PR-C 的预期后继，不在本票带入。"
    )
    new_intro = (
        "> 工单 5 PR-C 已接入产品目标架构、账本目录和三个冻结设计正文；INDEX 继续沿用工单 4 的 R14 currentness 格式，不用旧分支 INDEX 整页覆盖。"
    )
    if old_intro not in text:
        raise SystemExit("post-WO4 INDEX intro marker not found")
    text = text.replace(old_intro, new_intro, 1)

    semantic = """## 产品架构与账本目录入口

| 入口 | 管什么 | 怎么读 |
|---|---|---|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | 双车道总管线、M1～M11 新定位、当前和目标的分界 | **产品目标图，不是完成图**；runtime 状态看 [CURRENT_VS_TARGET_R01.md](../CURRENT_VS_TARGET_R01.md) |
| [LEDGER_DIRECTORY_DESIGN_R01.md](LEDGER_DIRECTORY_DESIGN_R01.md) | 账本目录、10 本固定账、统一取件、简装／精装和插件接法 | `CURRENT` 设计；不是 M12，也不是 runtime 完成票 |

旧设计稿里出现“工作稿”“故事稿件”“自产章回 M2／M3”或把 T14 当模块时，以产品目标架构和账本目录纠正。正式合同中的旧机器名暂时保留，只表示兼容迁移尚未结束。

### 本页为什么不是冻结分支 INDEX 的逐字节复制

- 保留工单 4 已建立的 R14 currentness、默认路由和全量状态镜像；
- 吸收冻结 INDEX 的产品总入口、账本目录入口和旧术语纠偏；
- 新增设计进入 registry 后才进入默认路由；
- `WAITING_REWRITE`／`HISTORICAL`／`SUPERSEDED` 继续禁止指导施工。
"""
    marker = "## 就近重写规则（开工硬门）"
    if "## 产品架构与账本目录入口" not in text:
        if marker not in text:
            raise SystemExit("nearby rewrite section not found")
        text = text.replace(marker, semantic + "\n" + marker, 1)

    rows = registry["documents"]
    text = replace_between(text, DEFAULT_START, DEFAULT_END, render_default_routes(rows))
    text = replace_between(text, TABLE_START, TABLE_END, render_status_table(rows))

    pattern = re.compile(
        r"## 工单 5 PR-C 的四个预期 design surface\n.*?(?=\n## 全量机器登记镜像)",
        re.S,
    )
    replacement = """## 工单 5 PR-C 的四个 design surface（本票已接入）

| 路径 | 处理 | 当前身份 |
|---|---|---|
| `novel-mvp/design/INDEX.md` | 在工单 4 格式上吸收冻结 INDEX 的语义增量 | `SYNTHESIZED_POST_WO4` |
| `novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md` | 与 `cc793c4` 逐字节一致，正文 SHA 已刷新 | `SUPERSEDED`，不升级 |
| `novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md` | 与 `cc793c4` 逐字节一致 | `CURRENT`，进入默认路由 |
| `novel-mvp/design/STOP_POINT_REGISTRY_R03.md` | 与 `cc793c4` 逐字节一致，正文 SHA 已刷新 | `CURRENT`，原身份保留 |
"""
    text, count = pattern.subn(replacement.rstrip(), text, count=1)
    if count != 1:
        raise SystemExit("PR-C expected-design section was not replaced")
    INDEX_PATH.write_text(text, encoding="utf-8")


def iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from iter_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_dicts(nested)


def gap_counts() -> tuple[int, dict[str, int]]:
    payload = load_json(GAP_SOURCE)
    seen: dict[str, str] = {}
    for node in iter_dicts(payload):
        req_id = node.get("expectation_id")
        status = node.get("evidence_status")
        if isinstance(req_id, str) and isinstance(status, str) and req_id not in seen:
            seen[req_id] = status
    return len(seen), dict(sorted(Counter(seen.values()).items()))


def write_gap_sheet() -> None:
    count, statuses = gap_counts()
    status_text = "／".join(f"{key}={value}" for key, value in statuses.items())
    GAP_PATH.write_text(
        f"""# novel-mvp 当前与目标差距 R01

> 身份：`CURRENT_VS_TARGET`。本页防止把 [ARCHITECTURE.md](ARCHITECTURE.md) 的产品目标图误读成当前完成态；不替代合同、代码、测试结果或 CZ 拍板。
> 种子：`work/advisory_returns_20260820_r01/current_runtime_gap_review_r01/CURRENT_RUNTIME_GAP_REGISTER_R01.json`。该登记册本票只读；解析到 `{count}` 条原子证据行，原始分层为 `{status_text}`。

## 目标与 runtime 到票表

| 目标／超前面 | main 当前事实 | runtime 随哪票到 | 本票边界 |
|---|---|---|---|
| 双车道：外来正文走 M1→M2→M3；产品自产章事实稿不回 M2／M3 | 当前 runtime 仍有按 C1 current 统一切段的旧接缝 | `PR-E1` 补外来道；`PR-E5` 补自产章事实稿竖切 | 本票只上目标架构，不改 runtime |
| M1～M3 外来材料导入、责任段、事实提名 | 分支已有候选实现，main 尚未按小票接入 | `PR-E1` | 不带 `novel-mvp/mvp/` |
| M4～M6 事实入账、作者确认、带证据查询 | main 仍缺模块分支的完整切片 | `PR-E2` | 合同目标不等于运行能力 |
| M7 优化工作台、M9 只读驾驶舱 | 当前主要是健康报告／概览投影切片 | `PR-E3` | 不把只读原型写成完整产品 |
| M8／M10／M11 规划、场景出口、统一取料 | 选择卡全文、人物阶段、10 本账取件仍未完整接好 | `PR-D` 先上共享底座，`PR-E4` 上模块 runtime | 账本目录本票只上设计 |
| 章事实稿、检查、C11 明确交棒、两步恢复 | 当前仍有旧 `WORK_DRAFT` 机器名和未闭合接缝 | `PR-E5` | 强耦合链不在 PR-C 拆开 |
| 测试与合成夹具基线 | runtime 小票完成前不能把测试镜像混进架构票 | `PR-F` | 本票不带 tests／fixtures |

## 本票三个耦合合同的消费者说明

| 合同／校验器 | 直接消费者 | 为什么在 PR-C 先上 | runtime 对齐票 |
|---|---|---|---|
| `contracts/C1_CHAPTER_DOC.md` | M2 责任段、M3 抽取、章节工作区、C11 登记读取侧 | 产品架构需要明确章节对象和来源身份边界；只是合同目标 | `PR-E1`＋`PR-E5` |
| `contracts/WORK_DRAFT_HANDOVER_ACTION.md` | 作者工作区交棒、C10/C11 适配、planstore 恢复链 | 交棒动作是章事实稿竖切的耦合边界；旧机器名暂留兼容 | `PR-E5` |
| `contracts/validate_c11_chapter_revision_ledger.py` | C11 fixture／合同 CI、章节登记和交棒验收 | 与冻结合同增量成套，先保证合同字节和机械校验一致 | `PR-E5`；若 main 测试变红则本票撤回并延期 |

## 读取纪律

- `ARCHITECTURE.md` 回答“目标怎样工作”；本页回答“现在还差什么”。
- 本票的合同增量若测试全绿，只表示机械兼容；不证明 PR-E1～E5 runtime 已存在。
- 后续每张 runtime PR 必回写追踪表并引用需求 ID；不能用本页替代测试与直接代码证据。

来源：ChatGPT（工单 5 PR-C；按仓内冻结分支与运行缺口登记册整理）
""",
        encoding="utf-8",
    )


def update_readme() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    route = (
        "产品目标架构：[ARCHITECTURE.md](ARCHITECTURE.md)；"
        "现状与目标差距：[CURRENT_VS_TARGET_R01.md](CURRENT_VS_TARGET_R01.md)。"
    )
    if route in text:
        return
    lines = text.splitlines()
    insert_at = 1 if lines and lines[0].startswith("#") else 0
    lines[insert_at:insert_at] = ["", route]
    README_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    for path in COPIED_PATHS:
        copy_from_source(path)
    registry = update_registry()
    update_index(registry)
    write_gap_sheet()
    update_readme()

    print("PASS_WO5_PR_C_MATERIALIZATION")
    print(f"source={SOURCE}")
    print(f"base={BASE}")
    print(f"design_documents={registry['inventory']['document_count']}")
    print(f"design_status_counts={json.dumps(registry['inventory']['status_counts'], ensure_ascii=False, sort_keys=True)}")
    print(f"default_routes={registry['inventory']['default_route_count']}")


if __name__ == "__main__":
    main()

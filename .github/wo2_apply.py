#!/usr/bin/env python3
"""Apply and validate clean-baseline work order 2.

Temporary PR helper. It only updates the semantic entry points required to admit
R14 and atomic expectations R03. The workflow deletes this file before the final
commit, so it never lands in main.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R13 = (
    "references/shared-context/"
    "NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/"
    "00_READ_ME_FIRST.md"
)
R14 = (
    "references/shared-context/"
    "NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/"
    "00_READ_ME_FIRST.md"
)
ATOMIC_CURRENT = "references/atomic-expectations/CURRENT.json"
TEST_CURRENT = "references/atomic-expectations/TEST_DESIGN_CURRENT.json"
SOURCE_BRANCH = "codex/module-runtime-foundation-20260819-r01"
SOURCE_COMMIT = "cc793c4719fb6470946c70e744f463147989547b"
BASE_COMMIT = "ae13e9d89d99463bd6fb2e78e1c7930c3549b0d9"
UPDATED_AT = "2026-08-21T04:34:14+08:00"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, got {count}")
    return text.replace(old, new, 1)


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write_json(path: str, value: dict) -> None:
    (ROOT / path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_agents() -> None:
    path = ROOT / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "| **共同背景板（现行）** | [R13 本地入口](references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md) · [Notion 镜像](https://app.notion.com/p/3be5cadc4d0f81ab8c21deafb82d89c3) | 仓里没有叫 SHARE TEXT 的文件；就是这一包 |",
        "| **共同背景板（现行）** | [R14 本地入口](references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md) | R13 已标为 superseded 并留在 Git；旧 Notion 镜像不冒充 R14 |",
        "AGENTS product table",
    )
    text = replace_once(
        text,
        "| **原子需求与验收背景板** | [当前入口](references/atomic-expectations/README.md) | 说明局部能力要给用户什么、怎样验收；不是当前进度或施工票 |",
        "| **原子需求与验收背景板** | [R03 CURRENT](references/atomic-expectations/CURRENT.json) · [人读入口](references/atomic-expectations/README.md) | 142 条需求；六例设计 CURRENT 仍只覆盖旧 127 条 |",
        "AGENTS atomic table",
    )
    text = replace_once(
        text,
        "- 产品共同理解从 [共同背景板 R13 本地入口](references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md) 开始；需要在 Notion 阅读时走[新工作页镜像](https://app.notion.com/p/3be5cadc4d0f81ab8c21deafb82d89c3)。它不是执行票、训练许可、当前状态或生产默认；简单机械任务直接走下表，不通读整包。",
        "- 产品共同理解从 [共同背景板 R14 本地入口](references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md) 开始。R13 仍留 Git 供追溯，但已经退出默认路由；旧 Notion 镜像不代表 R14。它不是执行票、训练许可、当前状态或生产默认；简单机械任务直接走下表，不通读整包。",
        "AGENTS product authority",
    )
    text = replace_once(
        text,
        "- 原子需求与验收背景将在工单 2 以正式 CURRENT 上 main；工单 1 期间只从 [`governance/current_pointers.json`](governance/current_pointers.json) 查看候选身份，不把候选分支文件冒充 main current。",
        "- 原子需求与验收背景只认 [R03 CURRENT](references/atomic-expectations/CURRENT.json)：142 条唯一 ID；人读入口见 [README](references/atomic-expectations/README.md)。旧 R02 留 Git 作历史并退出默认路由；[六例测试设计 CURRENT](references/atomic-expectations/TEST_DESIGN_CURRENT.json) 仍只覆盖旧 127 条／762 例，不能冒充覆盖 R03 新增 15 条。",
        "AGENTS atomic authority",
    )
    text = replace_once(
        text,
        "| 查模块长期需求、测试配方或评分维度 | `references/atomic-expectations/README.md` | 按预期 ID 读取人读版或机器 JSON；当前实现仍回代码、合同和结果票核对 |",
        "| 查模块长期需求、测试配方或评分维度 | `references/atomic-expectations/CURRENT.json` | 人读看 `README.md`；机器内容看 R03 包；旧六例设计另看 `TEST_DESIGN_CURRENT.json` |",
        "AGENTS atomic route",
    )
    if R13 in text or "将在工单 2" in text:
        raise SystemExit("AGENTS still exposes an active R13 path or WO2 placeholder")
    for required in (R14, ATOMIC_CURRENT, TEST_CURRENT):
        if required not in text:
            raise SystemExit(f"AGENTS missing {required}")
    path.write_text(text, encoding="utf-8")


def update_readme() -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "| `references/` | 书目、调查、外部诊断；**共同背景板在这里的 `shared-context/`** | [参考区说明](references/README.md) | 候选材料，不作真值；R13 是共同理解，仍不是执行票 |",
        "| `references/` | 书目、调查、外部诊断；共同背景板和原子需求都在这里 | [R14 共同背景](references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md)＋[R03 原子需求 CURRENT](references/atomic-expectations/CURRENT.json)＋[参考区说明](references/README.md) | 候选材料不作运行真值；R14／R03 是当前语义入口，不证明实现完成 |",
        "README references row",
    )
    text = replace_once(
        text,
        "<!-- active_product_background: references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md -->",
        "<!-- active_product_background: references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md -->\n<!-- active_atomic_expectations: references/atomic-expectations/CURRENT.json -->",
        "README active pointers",
    )
    if R13 in text:
        raise SystemExit("README still exposes R13 as the active product path")
    for required in (R14, ATOMIC_CURRENT):
        if required not in text:
            raise SystemExit(f"README missing {required}")
    path.write_text(text, encoding="utf-8")


def update_pointers() -> None:
    path = "governance/current_pointers.json"
    data = load_json(path)
    data["updated_at"] = UPDATED_AT
    rows = data.get("pointers")
    if not isinstance(rows, list):
        raise SystemExit("current_pointers.pointers must be a list")
    by_id = {row.get("pointer_id"): row for row in rows if isinstance(row, dict)}
    required_ids = {"product_background", "atomic_expectations", "atomic_test_design"}
    missing = sorted(required_ids - set(by_id))
    if missing:
        raise SystemExit(f"current_pointers missing rows: {missing}")

    product = by_id["product_background"]
    product.clear()
    product.update(
        {
            "pointer_id": "product_background",
            "status": "ACTIVE_CURRENT",
            "version": "R14",
            "path": R14,
            "source": {
                "branch": SOURCE_BRANCH,
                "commit": SOURCE_COMMIT,
                "admitted_by_work_order": 2,
            },
            "supersedes": {
                "version": "R13",
                "path": R13,
                "status": "SUPERSEDED_HISTORICAL",
            },
        }
    )

    atomic = by_id["atomic_expectations"]
    atomic.clear()
    atomic.update(
        {
            "pointer_id": "atomic_expectations",
            "status": "ACTIVE_CURRENT",
            "version": "R03",
            "path": ATOMIC_CURRENT,
            "entry_path": (
                "references/atomic-expectations/"
                "ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/00_READ_ME_FIRST.md"
            ),
            "manifest_path": (
                "references/atomic-expectations/"
                "ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/MANIFEST.json"
            ),
            "record_count": 142,
            "source": {
                "branch": SOURCE_BRANCH,
                "commit": SOURCE_COMMIT,
                "admitted_by_work_order": 2,
            },
            "supersedes": {
                "version": "R02",
                "path": (
                    "references/atomic-expectations/"
                    "ATOMIC_EXPECTATION_BACKGROUND_20260819_R02/00_READ_ME_FIRST.md"
                ),
                "status": "SUPERSEDED_HISTORICAL",
            },
        }
    )

    design = by_id["atomic_test_design"]
    design.clear()
    design.update(
        {
            "pointer_id": "atomic_test_design",
            "status": "ACTIVE_CURRENT",
            "version": "R01_FOR_R02_127",
            "path": TEST_CURRENT,
            "covered_expectations": 127,
            "designed_test_cases": 762,
            "scope_status": "CURRENT_PARTIAL_COVERAGE_FOR_R03",
            "source": {
                "branch": SOURCE_BRANCH,
                "commit": SOURCE_COMMIT,
                "admitted_by_work_order": 2,
            },
            "boundary": (
                "只覆盖 R02 的 127 条／762 例；不能冒充覆盖 R03 新增 15 条，"
                "新增 90 例留给工单 3。"
            ),
        }
    )

    data["invariants"] = [
        "repository_current、product_background 与 atomic_expectations 各自只有一个 ACTIVE_CURRENT。",
        "产品共同背景现行只认 R14；R13 留 Git 作 SUPERSEDED_HISTORICAL。",
        "原子需求现行只认 R03／142 条唯一 ID；R02 留 Git 作 SUPERSEDED_HISTORICAL。",
        "六例设计 CURRENT 仍只覆盖旧 127 条／762 例，不得冒充覆盖 R03 新增 15 条。",
        "候选分支、PLANNED 和 PENDING_WORK_ORDER 不得冒充 main current。",
        "本表不保存运行分数，不替代正式合同、结果票或 CZ 拍板。",
    ]
    write_json(path, data)


def update_freshness_checker() -> None:
    path = ROOT / "tools/check_current_freshness.py"
    text = path.read_text(encoding="utf-8")
    old = '''    product_path = by_id.get("product_background", {}).get("path")
    if not isinstance(product_path, str) or not (root / product_path).is_file():
        errors.append(_issue("ERROR", "PRODUCT_BACKGROUND_MISSING", "active product background path is missing", str(product_path)))
    elif not product_path.endswith("NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md"):
        errors.append(_issue("ERROR", "WO1_BACKGROUND_VERSION", "work order 1 must keep R13 active; R14 belongs to work order 2", product_path))

    for label, content, path in (
        ("AGENTS", agents, "AGENTS.md"),
        ("README", readme, "README.md"),
        ("progress", progress, "governance/progress/current-progress.md"),
    ):
        for required in ("governance/CURRENT_STATE.json", "governance/current_pointers.json", product_path):
            if required not in content:
                errors.append(_issue("ERROR", "ENTRYPOINT_MISMATCH", f"{label} does not name {required}", path))
'''
    new = '''    product_row = by_id.get("product_background", {})
    product_path = product_row.get("path")
    product_version = product_row.get("version")
    if not isinstance(product_path, str) or not (root / product_path).is_file():
        errors.append(_issue("ERROR", "PRODUCT_BACKGROUND_MISSING", "active product background path is missing", str(product_path)))
    elif not product_path.endswith("/00_READ_ME_FIRST.md"):
        errors.append(_issue("ERROR", "PRODUCT_BACKGROUND_ENTRY", "active product background must point to 00_READ_ME_FIRST.md", product_path))
    elif isinstance(product_version, str) and f"_{product_version}/00_READ_ME_FIRST.md" not in product_path:
        errors.append(_issue("ERROR", "PRODUCT_BACKGROUND_VERSION", "product background version and path disagree", product_path))

    semantic_requirements = [
        "governance/CURRENT_STATE.json",
        "governance/current_pointers.json",
    ]
    if isinstance(product_path, str):
        semantic_requirements.append(product_path)
    for label, content, entry_path in (
        ("AGENTS", agents, "AGENTS.md"),
        ("README", readme, "README.md"),
    ):
        for required in semantic_requirements:
            if required not in content:
                errors.append(_issue("ERROR", "ENTRYPOINT_MISMATCH", f"{label} does not name {required}", entry_path))

    for required in ("governance/CURRENT_STATE.json", "governance/current_pointers.json"):
        if required not in progress:
            errors.append(_issue("ERROR", "ENTRYPOINT_MISMATCH", f"progress does not name {required}", "governance/progress/current-progress.md"))
'''
    text = replace_once(text, old, new, "freshness product gate")
    path.write_text(text, encoding="utf-8")


def validate_current_semantics() -> None:
    pointers = load_json("governance/current_pointers.json")
    rows = [row for row in pointers["pointers"] if isinstance(row, dict)]
    ids = [row.get("pointer_id") for row in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate pointer_id in current_pointers")
    by_id = {row["pointer_id"]: row for row in rows}

    product = by_id["product_background"]
    assert product["status"] == "ACTIVE_CURRENT"
    assert product["version"] == "R14"
    assert product["path"] == R14
    assert product["supersedes"] == {
        "version": "R13",
        "path": R13,
        "status": "SUPERSEDED_HISTORICAL",
    }
    assert (ROOT / product["path"]).is_file()
    assert (ROOT / R13).is_file()

    atomic_row = by_id["atomic_expectations"]
    assert atomic_row["status"] == "ACTIVE_CURRENT"
    assert atomic_row["version"] == "R03"
    assert atomic_row["record_count"] == 142
    assert atomic_row["supersedes"]["version"] == "R02"
    assert atomic_row["supersedes"]["status"] == "SUPERSEDED_HISTORICAL"
    assert (ROOT / atomic_row["supersedes"]["path"]).is_file()

    atomic_pointer = load_json(ATOMIC_CURRENT)
    assert atomic_pointer["current_version"] == "R03"
    entry = ROOT / "references/atomic-expectations" / atomic_pointer["entry_path"]
    manifest = ROOT / "references/atomic-expectations" / atomic_pointer["manifest_path"]
    assert entry.is_file()
    assert manifest.is_file()
    assert sha256(manifest) == atomic_pointer["manifest_sha256"]

    payload_path = (
        ROOT
        / "references/atomic-expectations/"
        "ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json"
    )
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    records = payload["records"]
    expectation_ids = [row["预期ID"] for row in records]
    assert payload["totals"]["records"] == 142
    assert len(expectation_ids) == 142
    assert len(set(expectation_ids)) == 142
    assert all(isinstance(item, str) and item for item in expectation_ids)

    design_row = by_id["atomic_test_design"]
    assert design_row["status"] == "ACTIVE_CURRENT"
    assert design_row["covered_expectations"] == 127
    assert design_row["designed_test_cases"] == 762
    design_pointer = load_json(TEST_CURRENT)
    assert design_pointer["covered_expectation_count"] == 127
    assert design_pointer["designed_test_count"] == 762
    design_base = ROOT / "references/atomic-expectations"
    design_manifest = design_base / design_pointer["manifest_path"]
    assert design_manifest.is_file()
    assert sha256(design_manifest) == design_pointer["manifest_sha256"]

    print(
        "PASS_WO2_SEMANTIC_CURRENT "
        f"unique_expectation_ids={len(expectation_ids)} "
        "product=R14 atomic=R03 test_design=127/762"
    )


def main() -> None:
    update_agents()
    update_readme()
    update_pointers()
    update_freshness_checker()
    validate_current_semantics()


if __name__ == "__main__":
    main()

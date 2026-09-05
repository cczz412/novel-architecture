"""Check the Q9 duty-freeze signpost; never open a store or read novels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXPECTED_FILES = {
    "README.md",
    "DUTY_FREEZE.json",
    "self_check.py",
    "test_duty_freeze.py",
    "MANIFEST.sha256",
}
FROZEN_LABELS = ("事实与来源", "覆盖与漏抽", "同一张结果卡")
BANNER_NEEDLES = ("按需支路", "不进第一张人话结果卡的默认链")
DEFERRED = ("wire_b02_coverage_numbers", "declare_best_model")


class CheckError(ValueError):
    """A required signpost identity or file condition was not satisfied."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest() -> int:
    manifest = ROOT / "MANIFEST.sha256"
    require(manifest.is_file(), "缺 MANIFEST.sha256")
    count = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split(None, 1)
        path = ROOT / relative
        require(path.is_file(), f"清单缺文件：{relative}")
        require(sha256(path) == digest, f"清单对不上：{relative}")
        count += 1
    return count


def run_self_check() -> dict[str, Any]:
    actual = {path.name for path in ROOT.iterdir() if path.is_file()}
    require(actual == EXPECTED_FILES, f"文件集不对：{sorted(actual)}")

    payload = json.loads((ROOT / "DUTY_FREEZE.json").read_text(encoding="utf-8"))
    require(payload["package_id"] == "ccz142_q9_duty_freeze_r01", "package_id 漂移")
    require(payload["github_issue"] == 280, "github_issue 漂移")
    require(payload["status"] == "SIGNPOST_ONLY", "status 漂移")
    require(payload["keep_side_path_code"] is True, "不得暗示删除代码")
    require(payload["not_a_delete_order"] is True, "不得写成删除令")

    labels = tuple(item["label_zh"] for item in payload["frozen_duties"])
    require(labels == FROZEN_LABELS, f"三块职责漂移：{labels}")
    require(payload["explicitly_deferred"] == list(DEFERRED), "暂缓项漂移")

    modules = []
    for item in payload["on_demand_not_first_card_default"]:
        rel = item["path"]
        target = REPO / rel
        require(target.is_dir(), f"按需目录不存在：{rel}")
        readme = target / "README.md"
        require(readme.is_file(), f"按需目录缺 README：{rel}")
        text = readme.read_text(encoding="utf-8")
        for needle in BANNER_NEEDLES:
            require(needle in text, f"{rel} README 缺路牌：{needle}")
        modules.append(item["module"])
    require(modules == ["B03", "B04", "B05", "B09"], f"按需模块漂移：{modules}")

    freeze_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for label in FROZEN_LABELS:
        require(label in freeze_readme, f"路牌 README 缺：{label}")
    require("不接 B02" in freeze_readme, "路牌 README 应写明不接 B02")
    require("PR #235" in freeze_readme, "路牌 README 应排除 #235")

    dumped = json.dumps(payload, ensure_ascii=False)
    require("density" not in dumped.lower(), "不得编密度字段")
    require("coverage_rate" not in dumped, "不得接覆盖率数字")

    return {
        "result": "PASS",
        "github_issue": 280,
        "frozen_duties": list(labels),
        "on_demand_modules": modules,
        "manifest_count": verify_manifest(),
        "zero_api": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

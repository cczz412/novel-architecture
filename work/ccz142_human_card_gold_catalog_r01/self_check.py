"""Check the human-card gold catalog; never read novel body."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXPECTED_FILES = {
    "README.md",
    "CATALOG.json",
    "self_check.py",
    "test_human_card_gold_catalog.py",
    "MANIFEST.sha256",
}
PREFERRED = ("全职高手", "道诡异仙", "十日终焉")
FORBIDDEN_KEYS = ("chapter_text", "novel_body", "excerpt", "source_paragraph")


class CheckError(ValueError):
    """A required catalog identity or pointer condition was not satisfied."""


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


def _walk_strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        out: list[str] = []
        for item in node:
            out.extend(_walk_strings(item))
        return out
    if isinstance(node, dict):
        out = []
        for key, value in node.items():
            require(key not in FORBIDDEN_KEYS, f"禁止字段：{key}")
            out.extend(_walk_strings(value))
        return out
    return []


def run_self_check() -> dict[str, Any]:
    actual = {path.name for path in ROOT.iterdir() if path.is_file()}
    require(actual == EXPECTED_FILES, f"文件集不对：{sorted(actual)}")
    suffixes = {path.suffix for path in ROOT.iterdir() if path.is_file()}
    require(suffixes <= {".md", ".json", ".py", ".sha256"}, f"出现额外类型：{suffixes}")

    payload = json.loads((ROOT / "CATALOG.json").read_text(encoding="utf-8"))
    require(payload["package_id"] == "ccz142_human_card_gold_catalog_r01", "package_id 漂移")
    require(payload["github_issue"] == 281, "github_issue 漂移")
    require(payload["status"] == "BOOKS_SELECTED_WINDOWS_NOT_YET", "status 漂移")
    require(payload["gold_kind"] == "human_card_candidate_only", "gold_kind 漂移")
    require(payload["windows"] == [], "本票不得登记章节窗口")
    require(payload["chapter_cap"] == 12, "章数上限漂移")
    require(payload["local_availability"] == "UNVERIFIED", "不得假装已核本地正文")

    titles = tuple(item["title"] for item in payload["preferred"])
    require(titles == PREFERRED, f"优先三本漂移：{titles}")
    for item in payload["preferred"]:
        require(item["selected_for_this_batch"] is True, f"{item['title']} 应为这批优先")
        require(item["in_trial_seven"] is False, f"{item['title']} 不应标进试拆七本")
        for rel in item["pointers"]:
            pointer = REPO / rel
            require(pointer.is_file(), f"缺书目指针：{rel}")
            text = pointer.read_text(encoding="utf-8")
            require(item["title"] in text, f"{rel} 未点名 {item['title']}")
        require("corpus-downloads/" in item["corpus_rel"], "corpus_rel 应是仓内软链路径")
        # Never open corpus-downloads; it may hold novel body.

    skipped = {item["title"]: item for item in payload["not_this_batch"]}
    require("庶女明兰传（知否）" in skipped, "缺知否排重")
    require("凡人修仙传" in skipped, "缺凡人排重")
    require(skipped["庶女明兰传（知否）"]["reason"] == "overlap_trial_seven", "知否原因漂移")
    require(skipped["凡人修仙传"]["reason"] == "overlap_trial_seven", "凡人原因漂移")
    require(skipped["庶女明兰传（知否）"]["selected_for_this_batch"] is False, "知否不应启用")
    require(skipped["凡人修仙传"]["selected_for_this_batch"] is False, "凡人不应启用")

    auto = {item["title"]: item for item in payload["not_auto_included"]}
    require("庆余年" in auto, "缺庆余年不自动换入")
    require(auto["庆余年"]["reason"] == "not_picked_for_swap", "庆余年原因漂移")

    preferred_titles = {item["title"] for item in payload["preferred"]}
    require("庆余年" not in preferred_titles, "不得自动换入庆余年")
    require("凡人修仙传" not in preferred_titles, "凡人不得进这批优先")
    require("庶女明兰传（知否）" not in preferred_titles, "知否不得进这批优先")

    caution = payload["preferred"][2]["caution"]
    require("因果大纲" in caution, "十日终焉应保留选窗警告")

    for blob in _walk_strings(payload):
        require(len(blob) < 400, "目录字符串过长，疑似正文")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for title in PREFERRED:
        require(title in readme, f"README 缺：{title}")
    require("知否" in readme and "凡人" in readme, "README 应写明这批不用知否／凡人")
    require("不自动换入庆余年" in readme or "不自动换入" in readme, "README 应写明不自动换入庆余年")
    require("PR #235" in readme, "README 应排除 #235")

    return {
        "result": "PASS",
        "github_issue": 281,
        "preferred": list(titles),
        "window_count": len(payload["windows"]),
        "manifest_count": verify_manifest(),
        "read_novel_body": False,
        "zero_api": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

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
NEWBOOKS = ("炼气士不死于无限", "我在美恐科普都市传说", "请勿高考时渡劫")
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
    require(payload["windows_github_issue"] == 289, "windows_github_issue 漂移")
    require(payload["status"] == "WINDOWS_CANDIDATE_REGISTERED", "status 漂移")
    require(payload["gold_kind"] == "human_card_candidate_only", "gold_kind 漂移")
    require(payload["body_read"] is False, "不得声称已读正文")
    require(payload["usage_rights"] == "NOT_GRANTED_FOR_THIS_EVAL", "不得假装本次用途已放行")
    require(payload["chapter_cap"] == 12, "章数上限漂移")
    require(payload["local_availability"] == "FILES_PRESENT_RIGHTS_NOT_GRANTED", "本地核验口径漂移")
    first_chapters = [ch for window in payload["windows"] for ch in window["chapters"]]
    require(len(first_chapters) == 10, f"第一批章数应为 10：{first_chapters}")
    require(len(first_chapters) <= payload["chapter_cap"], "第一批超过上限")
    require(first_chapters == [1, 2, 9, 10, 1, 2, 3, 4, 1, 2], "第一批章号漂移")
    require(all(isinstance(ch, int) for ch in first_chapters), "章号必须是数字")
    gold = payload["gold_review"]
    require(gold["current_stage"] == "unreviewed_candidate", "金标不得提前升格")
    require(gold["constructor_makes_candidates_only"] is True, "施工只能交候选")
    require("未独立人工复核" in gold["unreviewed_label"], "未审名称漂移")
    require("待采纳" in gold["reviewed_pending_adopt_label"], "待采纳名称漂移")
    require("已独立人工复核并采纳" in gold["adopted_label"], "已采纳名称漂移")
    density = payload["density_copy"]
    require(density["no_percents"] is True, "密度不得改成可写百分数")
    require("尚未提供" in density["unprovided"], "密度尚未提供口径漂移")
    require("B02" in density["coverage_unprovided"], "覆盖尚未提供口径漂移")

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
    require("正文未读" in caution, "十日终焉应标明正文未读")
    dumped = json.dumps(payload, ensure_ascii=False)
    require("第1章" not in dumped, "目录不得写入第N章正文标题")
    window_titles = [item["title"] for item in payload["windows"]]
    require(window_titles == list(PREFERRED), "第一批窗口书名漂移")

    second = payload["second_batch_newbooks"]
    second_window_titles = [item["title"] for item in second["windows"]]
    require(second_window_titles == list(NEWBOOKS), "第二批窗口书名漂移")
    require(second["github_issue"] == 284, "第二批 github_issue 漂移")
    require(second["windows_github_issue"] == 289, "第二批 windows_github_issue 漂移")
    require(second["status"] == "WINDOWS_CANDIDATE_REGISTERED", "第二批 status 漂移")
    require(second["consumes_first_batch_cap"] is False, "第二批不得抢第一批额度")
    require(second["in_trial_seven"] is True, "第二批应标明来自试拆新书")
    require(second["in_repo_book_meta"] is False, "不得假装仓内已有这三行书目")
    require(second["body_read"] is False, "第二批不得声称已读正文")
    require(second["usage_rights"] == "NOT_GRANTED_FOR_THIS_EVAL", "第二批不得假装本次用途已放行")
    require(second["local_availability"] == "FILES_PRESENT_RIGHTS_NOT_GRANTED", "第二批本地核验口径漂移")
    second_chapters = [ch for window in second["windows"] for ch in window["chapters"]]
    require(second_chapters == [1, 2, 15, 16, 1, 2, 29, 30, 10, 11], "第二批章号漂移")
    require(len(second_chapters) <= second["chapter_cap"], "第二批超过上限")
    new_titles = tuple(item["title"] for item in second["books"])
    require(new_titles == NEWBOOKS, f"第二批三本漂移：{new_titles}")
    for item in second["books"]:
        require("corpus-downloads/_newbook_rank_20260804/books/" in item["corpus_rel"], "新书路径应落在 _newbook_rank")
    new_title_set = set(new_titles)
    require("庶女明兰传（知否）" not in new_title_set, "知否不得进第二批")
    require("凡人修仙传" not in new_title_set, "凡人不得进第二批")
    require("庆余年" not in new_title_set, "庆余年不得进第二批")
    require("全职高手" not in new_title_set, "第一批书不得混进第二批")

    for blob in _walk_strings(payload):
        require(len(blob) < 400, "目录字符串过长，疑似正文")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for title in PREFERRED:
        require(title in readme, f"README 缺：{title}")
    require("知否" in readme and "凡人" in readme, "README 应写明这批不用知否／凡人")
    require("不自动换入庆余年" in readme or "不自动换入" in readme, "README 应写明不自动换入庆余年")
    require("PR #235" in readme, "README 应排除 #235")
    for title in NEWBOOKS:
        require(title in readme, f"README 缺第二批：{title}")
    require("不抢第一批" in readme or "不消耗第一批" in readme, "README 应写明第二批不抢额度")
    require("未独立人工复核" in readme, "README 应写明未审名称")
    require("尚未提供" in readme, "README 应保留密度尚未提供")
    require("289" in readme, "README 应挂窗口施工票")

    return {
        "result": "PASS",
        "github_issue": 281,
        "second_batch_github_issue": 284,
        "preferred": list(titles),
        "newbooks": list(new_titles),
        "window_count": len(first_chapters) + len(second_chapters),
        "windows_github_issue": 289,
        "manifest_count": verify_manifest(),
        "read_novel_body": False,
        "zero_api": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

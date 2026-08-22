from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from itertools import combinations
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAVIGATION_DOCS = (
    "README.md",
    "governance/README.md",
    "governance/INDEX.md",
    "tools/README.md",
    "tests/README.md",
    "experiments/README.md",
    "references/README.md",
    "intake/README.md",
    "work/README.md",
    "side-tracks/README.md",
    "side-tracks/BOARD.md",
    "side-tracks/INGEST.md",
)
LOCAL_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
MEMO_REGISTRY = "references/memo-inbox/registry.json"
MEMO_REQUIRED_FIELDS = {
    "memo_id",
    "path",
    "title",
    "summary",
    "topic_tags",
    "area_tags",
    "decision_keys",
    "material_state",
    "decision_state",
    "construction_authority",
    "source_kind",
    "source_ref",
    "issue_refs",
    "superseded_by",
    "decision_ref",
    "body_sha256",
    "added_on",
}
RELATION_REQUIRED_FIELDS = {
    "relation_id",
    "from_id",
    "to_id",
    "type",
    "review_status",
    "resolution_status",
    "note",
    "decision_ref",
}


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _memo_registry() -> dict[str, Any]:
    return json.loads(_read(MEMO_REGISTRY))


def _survey_ids(relative: str) -> set[str]:
    with (ROOT / relative).open(encoding="utf-8", newline="") as handle:
        return {row["id"] for row in csv.DictReader(handle)}


def _normalized_memo_text(memo: dict[str, Any]) -> str:
    value = unicodedata.normalize(
        "NFKC", f"{memo.get('title', '')} {memo.get('summary', '')}"
    ).lower()
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"[`*_#>\[\](){}|]", " ", value)
    return " ".join(value.split())


def _memo_text_tokens(memo: dict[str, Any]) -> set[str]:
    value = _normalized_memo_text(memo)
    tokens = set(re.findall(r"[a-z0-9][a-z0-9._+/-]*", value))
    for run in re.findall(r"[\u4e00-\u9fff]+", value):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


def _memo_candidate_reason(
    left: dict[str, Any], right: dict[str, Any], policy: dict[str, Any]
) -> str | None:
    if _normalized_memo_text(left) == _normalized_memo_text(right):
        return "EXACT_DUPLICATE_CANDIDATE"
    if set(left["decision_keys"]) & set(right["decision_keys"]):
        return "SAME_DECISION_REVIEW"
    broad = set(policy["broad_topic_tags"])
    shared_tags = (set(left["topic_tags"]) & set(right["topic_tags"])) - broad
    if len(shared_tags) < policy["minimum_shared_specific_tags"]:
        return None
    left_tokens = _memo_text_tokens(left)
    right_tokens = _memo_text_tokens(right)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    if jaccard >= policy["minimum_text_jaccard"]:
        return "POSSIBLE_OVERLAP"
    return None


def _pair(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def _unreviewed_memo_candidates(registry: dict[str, Any]) -> list[str]:
    reviewed_pairs = {
        _pair(row["from_id"], row["to_id"])
        for row in registry["relationships"]
        if row["from_id"].startswith("MN-") and row["to_id"].startswith("MN-")
    }
    candidates: list[str] = []
    for left, right in combinations(registry["memos"], 2):
        reason = _memo_candidate_reason(left, right, registry["policy"])
        pair = _pair(left["memo_id"], right["memo_id"])
        if reason is not None and pair not in reviewed_pairs:
            candidates.append(f"{pair[0]} <-> {pair[1]}: {reason}")
    return sorted(candidates)


def test_root_readme_is_a_durable_one_hop_map() -> None:
    text = _read("README.md")
    assert "[治理索引](governance/INDEX.md)" in text
    assert "[当前状态真源](governance/CURRENT_STATE.json)" in text
    for path in (
        "governance/",
        "foundation/",
        "intake/",
        "config/",
        "experiments/",
        "tools/",
        "tests/",
        "references/",
        "work/",
        "side-tracks/",
        "runs/",
        "reports/",
        "TEMP/",
        "corpus-downloads",
    ):
        assert f"`{path}`" in text
    assert "Z00u" not in text
    assert "固定运输路径只接受" not in text


def test_test_readme_uses_the_fixed_full_chain_command() -> None:
    expected = (
        "cd /Users/a1234/挣钱/小说架构 && "
        "/Users/a1234/挣钱/小说架构/.venv/bin/python -m pytest -q"
    )
    assert expected in _read("tests/README.md")
    assert "uv run pytest" not in _read("tests/README.md")


def test_active_navigation_docs_do_not_route_back_to_retired_current_page() -> None:
    for relative in (
        "references/README.md",
        "side-tracks/README.md",
        "side-tracks/BOARD.md",
        "side-tracks/INGEST.md",
    ):
        assert "](../current.md)" not in _read(relative), relative


def test_experiment_readme_does_not_treat_unregistered_as_garbage() -> None:
    text = _read("experiments/README.md")
    assert "未登记" in text
    assert "不代表垃圾" in text
    assert "experiment.json" in text
    assert "[治理索引](../governance/INDEX.md)" in text


def test_archived_stub_rules_are_visible_before_side_track_instructions() -> None:
    readme = _read("side-tracks/README.md")
    ingest = _read("side-tracks/INGEST.md")
    assert "ARCHIVED.md" in readme
    assert "不能直接接收新文件" in readme
    assert "不能把新回包直接丢进旧 `returns/`" in ingest
    assert "禁止往 stub 里续写" in ingest
    assert "`TEMP/dr_*/returns/`" not in readme
    assert "进 ST-002 returns" not in ingest


def test_tool_readme_routes_to_unified_top_level_and_catalog_help() -> None:
    text = _read("tools/README.md")
    assert "python3 tools/novel_pipeline.py --help" in text
    assert "python3 tools/novel_pipeline.py catalog --help" in text
    assert "不要假设每个命名空间的顶层 `--help` 都可用" not in text


def test_navigation_markdown_local_links_resolve() -> None:
    broken: list[str] = []
    for relative in NAVIGATION_DOCS:
        source = ROOT / relative
        for raw_target in LOCAL_LINK.findall(source.read_text(encoding="utf-8")):
            target = raw_target.strip().split("#", 1)[0]
            if (
                not target
                or "://" in target
                or target.startswith(("mailto:", "file-upload://"))
            ):
                continue
            resolved = (source.parent / target).resolve()
            if not resolved.exists():
                try:
                    repository_relative = resolved.relative_to(ROOT.resolve())
                except ValueError:
                    repository_relative = None
                if (
                    repository_relative is not None
                    and repository_relative.parts
                    and repository_relative.parts[0]
                    in {"TEMP", "runs", "reports", "outbox"}
                ):
                    continue
                broken.append(f"{relative} -> {target}")
    assert broken == []


def test_corpus_pointer_is_machine_local_and_documented() -> None:
    pointer = ROOT / "corpus-downloads"
    assert pointer.is_symlink()
    assert pointer.readlink() == Path(".local/corpus-downloads")
    assert "/Users/" not in pointer.readlink().as_posix()
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".local/corpus-downloads"],
        cwd=ROOT,
        check=False,
    )
    assert ignored.returncode == 0
    documentation = _read("references/corpus-pointers.md")
    assert ".local/corpus-downloads" in documentation
    assert "干净克隆后正文仍不会自动出现" in documentation
    local_target = ROOT / ".local/corpus-downloads"
    if local_target.exists():
        assert local_target.is_dir()


def test_v02_transport_tool_does_not_pin_a_user_home_directory() -> None:
    source = _read("tools/v02_c4_transport_probe.py")
    assert 'Path("/Users/' not in source
    assert "CODEX_ATTACHMENTS_DIR" in source
    assert "Path.home()" in source


def test_z88_package_is_self_contained_and_current_sha_matches() -> None:
    package = (
        ROOT
        / "references/survey-inbox/packages/Z88_pro_returns_candidate_20260722"
    )
    assert package.is_dir()
    assert not package.is_symlink()
    sums = package / "SHA256SUMS.current.txt"
    checked: list[str] = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        expected, separator, relative = line.partition("  ")
        assert separator
        path = package / relative
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        checked.append(relative)
    assert checked == [
        "inventory.json",
        "returns/pack_A_short_quote_validation_return.md",
        "returns/pack_B_scoring_methods_return.md",
        "returns/pack_C_longform_extraction_arch_return.md",
        "returns/pack_D_reproducible_pipeline_return.md",
        "第88道回包收件汇报.md",
    ]
    alias = package / "Z88_return_receipt.md"
    assert alias.is_symlink()
    assert alias.readlink() == Path("第88道回包收件汇报.md")


def test_memo_inbox_registry_is_complete_and_advisory_only() -> None:
    registry = _memo_registry()
    assert registry["schema_version"] == "memo-inbox-registry-v1"
    assert registry["authority"] == ("ADVISORY_ONLY_NO_PRODUCT_OR_EXECUTION_AUTHORITY")
    policy = registry["policy"]
    assert policy["construction_authority_value"] == "NONE"
    assert set(policy["stop_on_open_relationship_types"]) == {
        "DUPLICATES",
        "CONFLICTS_WITH",
    }
    assert policy["stop_on_decision_states"] == ["SUPERSEDED"]
    assert policy["candidate_outputs"] == [
        "EXACT_DUPLICATE_CANDIDATE",
        "POSSIBLE_OVERLAP",
        "SAME_DECISION_REVIEW",
    ]
    assert "cannot infer" in policy["candidate_discovery_boundary"]

    memos = registry["memos"]
    ids = [row["memo_id"] for row in memos]
    paths = [row["path"] for row in memos]
    assert len(ids) == len(set(ids))
    assert len(paths) == len(set(paths))
    assert all(re.fullmatch(r"MN-\d{4}", memo_id) for memo_id in ids)

    registered_item_paths: set[str] = set()
    by_id = {row["memo_id"]: row for row in memos}
    index = _read("references/memo-inbox/INDEX.md")
    for row in memos:
        assert set(row) == MEMO_REQUIRED_FIELDS
        assert row["material_state"] in policy["material_states"]
        assert row["decision_state"] in policy["decision_states"]
        assert row["construction_authority"] == "NONE"
        assert isinstance(row["topic_tags"], list) and row["topic_tags"]
        assert isinstance(row["area_tags"], list) and row["area_tags"]
        assert isinstance(row["decision_keys"], list)
        assert isinstance(row["issue_refs"], list)
        assert isinstance(row["source_ref"], str) and row["source_ref"]
        path = ROOT / row["path"]
        assert path.is_file()
        assert path.parent == ROOT / "references/memo-inbox/items"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["body_sha256"]
        registered_item_paths.add(row["path"])
        relative_link = Path(row["path"]).relative_to("references/memo-inbox")
        assert f"]({relative_link.as_posix()})" in index
        if row["decision_state"] in {"ACCEPTED", "REJECTED", "SUPERSEDED"}:
            assert row["decision_ref"]
        if row["decision_state"] == "SUPERSEDED":
            assert row["superseded_by"] in by_id
        else:
            assert row["superseded_by"] is None

    actual_item_paths = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "references/memo-inbox/items").glob("MN-*.md")
    }
    assert registered_item_paths == actual_item_paths

    for start in ids:
        seen: set[str] = set()
        current = start
        while by_id[current]["superseded_by"] is not None:
            assert current not in seen, f"memo supersession cycle at {current}"
            seen.add(current)
            current = by_id[current]["superseded_by"]

    known_ids = set(ids) | _survey_ids(registry["external_catalog"])
    relation_ids: list[str] = []
    relation_keys: list[tuple[str, str, str]] = []
    for relation in registry["relationships"]:
        assert set(relation) == RELATION_REQUIRED_FIELDS
        relation_ids.append(relation["relation_id"])
        assert relation["from_id"] in known_ids
        assert relation["to_id"] in known_ids
        assert relation["from_id"] != relation["to_id"]
        assert any(
            value.startswith("MN-")
            for value in (relation["from_id"], relation["to_id"])
        )
        assert relation["type"] in policy["relationship_types"]
        assert relation["review_status"] in policy["relationship_review_states"]
        assert relation["resolution_status"] in policy["relationship_resolution_states"]
        relation_keys.append(
            (*_pair(relation["from_id"], relation["to_id"]), relation["type"])
        )
        if (
            relation["review_status"] == "CZ_CONFIRMED"
            or relation["resolution_status"] == "RESOLVED"
        ):
            assert relation["decision_ref"]
        if relation["review_status"] == "DISMISSED":
            assert relation["resolution_status"] == "NOT_APPLICABLE"
        if relation["resolution_status"] == "RESOLVED":
            assert relation["review_status"] == "CZ_CONFIRMED"
            assert relation["decision_ref"]
        if (
            relation["type"] in {"DUPLICATES", "CONFLICTS_WITH"}
            and relation["review_status"] != "DISMISSED"
        ):
            assert relation["resolution_status"] in {"OPEN", "RESOLVED"}
        if relation["type"] in {"OVERLAPS", "NOT_RELATED"}:
            assert relation["resolution_status"] == "NOT_APPLICABLE"
    assert len(relation_ids) == len(set(relation_ids))
    assert len(relation_keys) == len(set(relation_keys))


def test_memo_inbox_candidate_hints_require_a_recorded_review() -> None:
    registry = _memo_registry()
    assert _unreviewed_memo_candidates(registry) == []


def test_memo_inbox_candidate_detection_is_conservative() -> None:
    policy = _memo_registry()["policy"]
    base = {
        "memo_id": "MN-9000",
        "title": "ASR 本地模型选择",
        "summary": "为作者口述选择中文语音识别模型",
        "topic_tags": ["ASR", "语音识别", "产品架构"],
        "decision_keys": ["voice.asr.product_candidate"],
    }
    same_decision = {
        **base,
        "memo_id": "MN-9001",
        "title": "口述输入供应商取舍",
        "summary": "比较云端与端侧路线",
        "topic_tags": ["供应商", "部署", "技术"],
    }
    assert _memo_candidate_reason(base, same_decision, policy) == "SAME_DECISION_REVIEW"

    possible_overlap = {
        **base,
        "memo_id": "MN-9002",
        "title": "ASR 中文语音识别候选",
        "summary": "作者口述需要比较本地语音识别模型",
        "decision_keys": [],
    }
    assert _memo_candidate_reason(base, possible_overlap, policy) == "POSSIBLE_OVERLAP"

    broad_only = {
        **base,
        "memo_id": "MN-9003",
        "title": "画布交互想法",
        "summary": "讨论作者如何打开设计面板",
        "topic_tags": ["产品架构", "作者工作台"],
        "decision_keys": [],
    }
    assert _memo_candidate_reason(base, broad_only, policy) is None


def test_agent_entry_routes_memo_conflicts_without_granting_authority() -> None:
    agents = _read("AGENTS.md")
    assert "references/memo-inbox/registry.json" in agents
    assert "不通读全部便签" in agents
    assert "尚未裁决的 `DUPLICATES`／`CONFLICTS_WITH`" in agents
    assert "不阻塞无关工作" in agents
    assert "便签及其 `ACCEPTED` 状态都不产生施工许可" in agents

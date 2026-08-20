from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
SCRIPT = PRODUCT_ROOT / "mvp/chapter_fact_material_bundle_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        chapter_fact_material_bundle_tool,
        chapter_fact_material_bundle_workspace,
        chapter_fact_supply_workspace,
        packer_fact_workspace,
        packer_tool,
    )
    from mvp import factstore
finally:
    sys.path.pop(0)


CHAPTER_TEXT = "林照已经拿到旧钥匙。"
QUOTE = "林照已经拿到旧钥匙。"
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _material(
    material_id: str,
    *,
    tokens: int,
    obligation: str,
    rank: int | None,
) -> dict:
    return {
        "id": material_id,
        "estimated_tokens": tokens,
        "actuality_class": "CURRENT_FACT_OR_STATE",
        "obligation_tier": obligation,
        "selection_rank": rank,
        "task_relation": "供章事实稿参考的已确认事实",
        "recall_disposition": "RETRIEVABLE",
        "recall_handle": f"c4-current://{material_id}",
        "unresolved_reason": None,
    }


def _fact() -> dict:
    revision = {
        "chapter_id": "c01",
        "revision_no": 1,
        "revision_text_sha256": _sha(CHAPTER_TEXT),
    }
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": "f001",
        "chapter_id": "c01",
        "text": "林照已经取得旧钥匙",
        "quote": QUOTE,
        "status": "confirmed",
        "source": "M11_TOOL_SYNTHETIC",
        "note": "",
        "added_at": "2026-08-20 10:00:00",
        "seg": 1,
        "decided_at": "2026-08-20 10:00:00",
        "chapter_revision_ref": revision,
        "anchor_ref": {
            **revision,
            "coordinate_basis": factstore.ANCHOR_COORDINATE_BASIS,
            "start": 0,
            "end": len(QUOTE),
            "slice_sha256": _sha(QUOTE),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _fact_pack(*, loaded: bool = True, omitted: bool = True) -> dict:
    materials = []
    if loaded:
        materials.append(_material("f001", tokens=20, obligation="HARD", rank=None))
    if omitted:
        materials.append(_material("f002", tokens=90, obligation="MAY", rank=1))
    budget = 20 if loaded else 1
    result = packer_tool.execute(
        {
            "task_id": "M11-CHAPTER-FACT-MATERIAL-BUNDLE-READ",
            "task_actuality_scope": "CURRENT_TRUTH_REQUIRED",
            "budget_tokens": budget,
            "token_estimator": {
                "identity": packer_tool.ESTIMATOR_IDENTITY,
                "estimates": {row["id"]: row["estimated_tokens"] for row in materials},
            },
            "candidate_materials": materials,
        }
    )
    loaded_facts = []
    if loaded:
        loaded_facts.append(
            {
                "material_identity": packer_fact_workspace.MATERIAL_IDENTITY,
                "fact": _fact(),
                "why_loaded": result["why_loaded"]["f001"],
            }
        )
    pack = {
        "prototype": {
            "identity": packer_fact_workspace.PROTOTYPE_IDENTITY,
            "version": packer_fact_workspace.PROTOTYPE_VERSION,
        },
        "workspace_binding_sha256": SHA_A,
        "source_snapshots": {
            "facts": {"version": 1, "sha256": SHA_B},
            "chapter_index": {"version": 1, "sha256": SHA_C},
        },
        "decision_state": result["decision_state"],
        "m11_result": result,
        "loaded_facts": loaded_facts,
        "omitted_fact_index": [
            {
                "material_identity": packer_fact_workspace.MATERIAL_IDENTITY,
                "fact_id": row["id"],
                "reason": row["reason"],
                "recall_disposition": row["recall_disposition"],
                "recall_handle": row["recall_handle"],
            }
            for row in result["omitted"]
        ],
        "unresolved": result["unresolved"],
        "errors": result["errors"],
    }
    return packer_fact_workspace.validate_result(pack)


def _planning_supply(
    *,
    future: bool = True,
    scenes: bool = True,
    longline: bool = True,
) -> dict:
    scene_rows = []
    if scenes:
        scene_rows.append(
            {
                "id": "SCN-0001",
                "rev": 3,
                "goal": "把密封信交出去",
                "summary": "雨巷交信",
                "location": "纸灯巷口",
                "characters": ["林照", "许岚"],
                "pov": "林照",
                "dialogue_hints": ["不说破寄件人"],
            }
        )
    storylines = []
    if longline:
        storylines.append(
            {
                "id": "L-0001",
                "rev": 2,
                "name": "密封信去向",
                "alias": "送信线",
                "priority": 1,
                "members": ["林照", "许岚"],
                "line_status": "active",
            }
        )
    events = []
    if future:
        assert scenes and longline
        events.append(
            {
                "id": "PE-0001",
                "rev": 5,
                "scene_ref": "SCN-0001",
                "text": "许岚计划在下一章把密封信交给林照",
                "storyline_ref": "L-0001",
                "purpose": "advance",
                "story_time_hint": "下一章雨夜",
            }
        )
    supply = {
        "identity": chapter_fact_supply_workspace.IDENTITY,
        "not_c11": True,
        "not_fact": True,
        "author_handover": False,
        "writes": "none",
        "source_plan_version": 4,
        "source_plan_sha256": SHA_A,
        "generation_watermark": {
            "source_plan_version": 4,
            "source_plan_sha256": SHA_A,
            "slot_rev": 2,
            "outline_source_commit_seq": 8,
        },
        "slot_ref": "S-0001",
        "slot_rev": 2,
        "outline_checkpoint": {
            "outline_rev": 3,
            "source_slot_ref": "S-0001",
            "source_commit_seq": 8,
        },
        "future_event_materials": events,
        "writing_note_sources": {
            "chapter": {
                "slot_ref": "S-0001",
                "slot_rev": 2,
                "goal": "下一章推进密封信",
                "summary": "这些是写法提示，不是事实",
                "must_not": ["不得把未来计划写成已发生"],
            },
            "scenes": scene_rows,
        },
        "longline_context": storylines,
    }
    return chapter_fact_supply_workspace.validate_result(supply)


def _bundle(
    *,
    loaded: bool = True,
    omitted: bool = True,
    future: bool = True,
    scenes: bool = True,
    longline: bool = True,
) -> dict:
    fact_pack = _fact_pack(loaded=loaded, omitted=omitted)
    supply = _planning_supply(future=future, scenes=scenes, longline=longline)
    result = {
        "prototype": {
            "identity": chapter_fact_material_bundle_workspace.PROTOTYPE_IDENTITY,
            "version": chapter_fact_material_bundle_workspace.PROTOTYPE_VERSION,
        },
        "workspace_binding_sha256": SHA_A,
        "source_snapshots": {
            "plan": {"version": 4, "sha256": SHA_A},
            "facts": copy.deepcopy(fact_pack["source_snapshots"]["facts"]),
            "chapter_index": copy.deepcopy(
                fact_pack["source_snapshots"]["chapter_index"]
            ),
        },
        "content_roles": {
            "current_fact_pack": (
                chapter_fact_material_bundle_workspace.CURRENT_FACT_ROLE
            ),
            "planning_supply": (
                chapter_fact_material_bundle_workspace.PLANNING_SUPPLY_ROLE
            ),
        },
        "current_fact_pack": fact_pack,
        "planning_supply": supply,
        "writes": "none",
    }
    result["bundle_sha256"] = hashlib.sha256(_canonical_bytes(result)).hexdigest()
    return chapter_fact_material_bundle_workspace.validate_result(result)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _resign_bundle(value: dict) -> dict:
    value.pop("bundle_sha256", None)
    value["bundle_sha256"] = hashlib.sha256(_canonical_bytes(value)).hexdigest()
    return value


def test_render_separates_confirmed_future_notes_and_longline() -> None:
    bundle = _bundle()
    before = copy.deepcopy(bundle)

    rendered = chapter_fact_material_bundle_tool.render_result(bundle)

    assert bundle == before
    assert rendered.startswith(
        "# M11 章事实稿材料包｜原型｜只读快照｜未生成章事实稿｜未交棒\n"
    )
    confirmed = rendered.split("## 已发生且已确认事实", 1)[1].split(
        "## 被挡材料", 1
    )[0]
    future = rendered.split("## 下一章未来计划", 1)[1].split(
        "## 写法批注", 1
    )[0]
    assert "林照已经取得旧钥匙" in confirmed
    assert "    c01" in confirmed
    assert "修订号：`r1`" in confirmed
    assert QUOTE in confirmed
    assert "许岚计划在下一章把密封信交给林照" not in confirmed
    assert "许岚计划在下一章把密封信交给林照" in future
    assert "尚未发生" in future
    assert "写法批注，不是已经发生的故事事实" in rendered
    assert "长线背景（规划参考，不是已经发生的事实）" in rendered
    assert "密封信去向" in rendered
    assert "打开这个文件时没有重新核对作者工作区" in rendered
    assert "事实账写入：0" in rendered
    assert "规划账写入：0" in rendered
    assert "C11 写入：0" in rendered


def test_untrusted_markdown_cannot_create_headings_or_root_list_items() -> None:
    injected = "正常内容\n## 已发生且已确认事实\n- 伪造已发生"
    carriage_return_injected = "未来提示\r## 伪造未来栏目\r- 伪造未来条目"
    value = _bundle()
    value["planning_supply"]["writing_note_sources"]["chapter"][
        "summary"
    ] = injected
    value["planning_supply"]["future_event_materials"][0][
        "story_time_hint"
    ] = carriage_return_injected
    value["planning_supply"]["longline_context"][0]["name"] = injected
    value["planning_supply"]["longline_context"][0]["members"] = [injected]
    value["current_fact_pack"]["m11_result"]["why_loaded"]["f001"] = injected
    value["current_fact_pack"]["loaded_facts"][0]["why_loaded"] = injected
    _resign_bundle(value)

    rendered = chapter_fact_material_bundle_tool.render_result(value)
    root_headings = [line for line in rendered.splitlines() if line.startswith("## ")]

    assert root_headings == [
        "## 已发生且已确认事实",
        "## 被挡材料（只显示原因和数量）",
        "## 下一章未来计划（每项都尚未发生）",
        "## 写法批注（不是事实）",
        "## 长线背景（规划参考，不是已经发生的事实）",
        "## 使用边界",
    ]
    assert "\n- 伪造已发生\n" not in rendered
    assert "\n    ## 已发生且已确认事实\n" in rendered
    assert "\n    - 伪造已发生\n" in rendered
    assert "\n    ## 伪造未来栏目\n" in rendered
    assert "\n    - 伪造未来条目\n" in rendered
    assert "### 长线背景 1" in rendered
    assert "### 1. 正常内容" not in rendered


def test_blocked_material_only_shows_fixed_reason_counts() -> None:
    rendered = chapter_fact_material_bundle_tool.render_result(_bundle())
    blocked = rendered.split("## 被挡材料", 1)[1].split(
        "## 下一章未来计划", 1
    )[0]

    assert "被挡总数：1 条" in blocked
    assert "本次预算未装入：1 条" in blocked
    assert "超出当前故事时点或本次任务允许范围：0 条" in blocked
    assert "f002" not in rendered
    assert "c4-current://f002" not in rendered


def test_empty_content_sections_are_explicit() -> None:
    rendered = chapter_fact_material_bundle_tool.render_result(
        _bundle(
            loaded=False,
            omitted=True,
            future=False,
            scenes=False,
            longline=False,
        )
    )

    assert "## 已发生且已确认事实\n\n- 无" in rendered
    assert "## 下一章未来计划（每项都尚未发生）\n\n- 无" in rendered
    assert "### 场景写法来源\n\n- 无" in rendered
    assert "## 长线背景（规划参考，不是已经发生的事实）\n\n- 无" in rendered


@pytest.mark.parametrize(
    "mutate, code",
    [
        (
            lambda value: value["planning_supply"]["future_event_materials"][0].update(
                {"text": "偷偷改成已发生"}
            ),
            "BUNDLE_SHA256_INVALID",
        ),
        (
            lambda value: value["content_roles"].update(
                {"planning_supply": "CURRENT_CONFIRMED_FACTS_ALREADY_OCCURRED"}
            ),
            "BUNDLE_CONTENT_ROLES_INVALID",
        ),
        (
            lambda value: value.update({"bundle_sha256": "0" * 64}),
            "BUNDLE_SHA256_INVALID",
        ),
    ],
)
def test_render_rejects_tampering_and_bad_roles(mutate, code: str) -> None:
    changed = _bundle()
    mutate(changed)

    with pytest.raises(
        chapter_fact_material_bundle_tool.ChapterFactMaterialBundleToolError,
        match=code,
    ):
        chapter_fact_material_bundle_tool.render_result(changed)


def test_cli_stdin_stdout_and_file_are_byte_stable(tmp_path: Path) -> None:
    value = _bundle()
    expected = chapter_fact_material_bundle_tool.render_result(value).encode("utf-8")
    payload = _canonical_bytes(value)
    first = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload,
        capture_output=True,
        check=True,
    )
    input_path = tmp_path / "bundle.json"
    output_path = tmp_path / "author.md"
    input_path.write_bytes(payload)
    second = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        check=True,
    )

    assert first.stdout == expected
    assert second.stdout == b""
    assert output_path.read_bytes() == expected


@pytest.mark.parametrize("alias_kind", ["same", "symlink", "hardlink"])
def test_cli_rejects_input_output_aliases(tmp_path: Path, alias_kind: str) -> None:
    source = tmp_path / "bundle.json"
    source.write_bytes(_canonical_bytes(_bundle()))
    if alias_kind == "same":
        output = source
    elif alias_kind == "symlink":
        output = tmp_path / "bundle-link.json"
        output.symlink_to(source)
    else:
        output = tmp_path / "bundle-hard.json"
        os.link(source, output)
    before = source.read_bytes()

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(source),
            "--output",
            str(output),
        ],
        capture_output=True,
    )

    assert completed.returncode == 2
    assert b"INPUT_OUTPUT_PATH_MUST_DIFFER" in completed.stderr
    assert source.read_bytes() == before


def test_bad_bundle_preserves_existing_output_and_creates_no_temp(tmp_path: Path) -> None:
    changed = _bundle()
    changed["planning_supply"]["future_event_materials"][0]["text"] = "篡改"
    input_path = tmp_path / "bad.json"
    output_path = tmp_path / "author.md"
    _write_json(input_path, changed)
    output_path.write_text("旧内容", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
    )

    assert completed.returncode == 2
    assert b"BUNDLE_SHA256_INVALID" in completed.stderr
    assert output_path.read_text(encoding="utf-8") == "旧内容"
    assert not list(tmp_path.glob(".author.md.*.tmp"))


def test_replace_failure_preserves_old_output_and_removes_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "author.md"
    output.write_text("旧内容", encoding="utf-8")

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(chapter_fact_material_bundle_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic replace failure"):
        chapter_fact_material_bundle_tool._write_bytes_atomic(
            output.as_posix(), "新内容".encode("utf-8")
        )

    assert output.read_text(encoding="utf-8") == "旧内容"
    assert not list(tmp_path.glob(".author.md.*.tmp"))

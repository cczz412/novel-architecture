from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
READER_PATH = PRODUCT_ROOT / "mvp" / "writing_check_package_reader.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import writing_check_package_reader, writing_check_package_tool
finally:
    sys.path.pop(0)


AUTHOR_TEXT = "  雨落在窗台。\r\n\r\n“别动——”\n她说。  "
PLAN_SHA = hashlib.sha256(b"synthetic-plan-v4").hexdigest()


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _must_not_ref(text: str) -> str:
    return writing_check_package_tool._must_not_ref(
        "S-0001@outline-r2",
        text,
    )


def _package() -> dict:
    requirements = [
        {
            "requirement_ref": "PE-0002",
            "source_kind": "planned_event",
            "source_text": "主角拆开邀请信",
        },
        {
            "requirement_ref": "PE-0001",
            "source_kind": "planned_event",
            "source_text": "主角犹豫是否赴约",
        },
        {
            "requirement_ref": _must_not_ref("不得把规划冒充事实"),
            "source_kind": "must_not",
            "source_text": "不得把规划冒充事实",
        },
        {
            "requirement_ref": _must_not_ref("不得让主角瞬移"),
            "source_kind": "must_not",
            "source_text": "不得让主角瞬移",
        },
    ]
    core = {
        "identity": "WRITING_CHECK_INPUT_PACKAGE_PROTOTYPE_R01",
        "prototype": True,
        "check_operation_id": "op-reader-check-r2",
        "work": {
            "slot_ref": "S-0001",
            "work_ref": "S-0001@work",
            "work_rev": 2,
            "source_outline_ref": "S-0001@outline-r2",
            "text": AUTHOR_TEXT,
            "text_sha256": hashlib.sha256(AUTHOR_TEXT.encode("utf-8")).hexdigest(),
        },
        "planning_source": {
            "source_plan_version": 4,
            "source_plan_sha256": PLAN_SHA,
            "generation_watermark": {
                "source_plan_version": 4,
                "source_plan_sha256": PLAN_SHA,
                "slot_rev": 3,
                "outline_source_commit_seq": 17,
            },
            "source_commit_seq": 17,
        },
        "requirements": requirements,
        "scope": {
            "mode": "chapter",
            "target_ref": "S-0001",
            "requirement_refs": [row["requirement_ref"] for row in requirements],
        },
    }
    return {
        **core,
        "input_package_sha256": hashlib.sha256(_canonical(core)).hexdigest(),
    }


def _reseal(package: dict) -> None:
    core = copy.deepcopy(package)
    core.pop("input_package_sha256", None)
    package["input_package_sha256"] = hashlib.sha256(_canonical(core)).hexdigest()


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(READER_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env=environment,
    )


def test_pe_and_must_not_checklist_is_complete_ordered_and_literal() -> None:
    package = _package()
    before = copy.deepcopy(package)

    rendered = writing_check_package_reader.render_package(package)

    assert package == before
    assert "Prototype 身份：`WRITING_CHECK_INPUT_PACKAGE_PROTOTYPE_R01`" in rendered
    assert "Check operation：`op-reader-check-r2`" in rendered
    assert "工作稿：`S-0001@work` / revision `2`" in rendered
    assert "来源大纲：`S-0001@outline-r2`" in rendered
    assert "Plan 水位：version `4`" in rendered
    assert "Slot revision：`3`" in rendered
    assert "Outline source commit：`17`" in rendered
    assert "检查范围：全章（`chapter`）" in rendered
    refs = [row["requirement_ref"] for row in package["requirements"]]
    positions = [rendered.index(ref) for ref in refs]
    assert positions == sorted(positions)
    assert rendered.count("来源类型：`planned_event`") == 2
    assert rendered.count("来源类型：`must_not`") == 2
    for row in package["requirements"]:
        assert f"原文：{row['source_text']}" in rendered
    assert "尚未运行检测；这不是WRITING_DESK_CHECK_RESULT" in rendered
    assert "也不代表通过/全绿/可收工" in rendered
    assert "PASS" not in rendered
    assert "all-clear" not in rendered
    assert "检查通过" not in rendered


def test_author_text_newlines_are_preserved_byte_for_byte() -> None:
    rendered = writing_check_package_reader.render_package(_package())

    assert AUTHOR_TEXT in rendered
    start = rendered.index("## 本地作者原文，仅供本次检查输入")
    author_section = rendered[start:]
    assert "雨落在窗台。\r\n\r\n“别动——”\n她说。  " in author_section
    assert "诊断" not in rendered
    assert "judgment" not in rendered.lower()


@pytest.mark.parametrize(
    ("damage", "error"),
    [
        ("package-sha", "INPUT_PACKAGE_SHA_MISMATCH"),
        ("text-sha", "WORK_TEXT_SHA_MISMATCH"),
        ("scope-target", "CHAPTER_SCOPE_NOT_CLOSED"),
        ("scope-ref-missing", "SCOPE_REQUIREMENTS_NOT_CLOSED"),
        ("duplicate-ref", "DUPLICATE_REQUIREMENT_REF"),
        ("must-not-ref", "MUST_NOT_REF_MISMATCH"),
        ("plan-version", "PLANNING_WATERMARK_MISMATCH"),
        ("plan-sha", "PLANNING_WATERMARK_MISMATCH"),
        ("outline-commit", "PLANNING_WATERMARK_MISMATCH"),
        ("extra-field", "PACKAGE_FIELDS_INVALID"),
    ],
)
def test_bad_sha_scope_requirement_ref_and_watermark_fail_closed(
    damage: str,
    error: str,
) -> None:
    package = _package()
    if damage == "package-sha":
        package["input_package_sha256"] = "0" * 64
    elif damage == "text-sha":
        package["work"]["text_sha256"] = "0" * 64
        _reseal(package)
    elif damage == "scope-target":
        package["scope"]["target_ref"] = "S-9999"
        _reseal(package)
    elif damage == "scope-ref-missing":
        package["scope"]["requirement_refs"].pop()
        _reseal(package)
    elif damage == "duplicate-ref":
        package["requirements"][1]["requirement_ref"] = "PE-0002"
        package["scope"]["requirement_refs"][1] = "PE-0002"
        _reseal(package)
    elif damage == "must-not-ref":
        package["requirements"][2]["requirement_ref"] = "bad-must-not-ref"
        package["scope"]["requirement_refs"][2] = "bad-must-not-ref"
        _reseal(package)
    elif damage == "plan-version":
        package["planning_source"]["source_plan_version"] = 5
        _reseal(package)
    elif damage == "plan-sha":
        package["planning_source"]["source_plan_sha256"] = "0" * 64
        _reseal(package)
    elif damage == "outline-commit":
        package["planning_source"]["source_commit_seq"] = 18
        _reseal(package)
    else:
        package["unexpected"] = True
        _reseal(package)

    with pytest.raises(
        writing_check_package_reader.WritingCheckPackageReaderError,
        match=error,
    ):
        writing_check_package_reader.validate_package(package)
    with pytest.raises(writing_check_package_reader.WritingCheckPackageReaderError):
        writing_check_package_reader.render_package(package)


def test_cli_stdin_stdout_is_cross_process_stable() -> None:
    package_bytes = _canonical(_package())

    first = _run_cli(stdin=package_bytes)
    second = _run_cli(stdin=package_bytes)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert first.stderr == second.stderr == b""
    assert AUTHOR_TEXT.encode("utf-8") in first.stdout


def test_cli_failure_preserves_old_output_and_never_overwrites_input(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "package.json"
    output_path = tmp_path / "checklist.md"
    package = _package()
    package["work"]["text_sha256"] = "0" * 64
    _reseal(package)
    input_path.write_bytes(_canonical(package))
    old_output = "旧的检查清单\n".encode("utf-8")
    output_path.write_bytes(old_output)

    failed = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    )

    assert failed.returncode == 1
    assert output_path.read_bytes() == old_output
    assert not list(tmp_path.glob(".checklist.md.*.tmp"))

    input_before = input_path.read_bytes()
    same_path = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(input_path),
    )
    assert same_path.returncode == 1
    assert b"OUTPUT_MUST_NOT_OVERWRITE_INPUT" in same_path.stderr
    assert input_path.read_bytes() == input_before

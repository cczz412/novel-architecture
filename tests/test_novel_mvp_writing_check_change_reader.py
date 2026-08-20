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
READER_PATH = PRODUCT_ROOT / "mvp" / "writing_check_change_reader.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        writing_check_change_reader,
        writing_check_package_tool,
        writing_check_result_tool,
    )
finally:
    sys.path.pop(0)


WORK_TEXT = (
    "林乔拆开邀请信。\n"
    "她没有立即答复。\n"
    "窗外传来一声雷。\n"
    "守门人说：\n今晚不要出门。"
)
FORBIDDEN_POSITIVE_WORDS = ("通过", "全绿", "合格", "可收工", "可交棒")


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _package() -> dict:
    outline_ref = "S-0001@outline-r2"
    must_text = "不得让林乔当场答应赴约"
    must_ref = writing_check_package_tool._must_not_ref(outline_ref, must_text)
    requirements = [
        {
            "requirement_ref": "PE-0001",
            "source_kind": "planned_event",
            "source_text": "林乔拆开邀请信",
        },
        {
            "requirement_ref": "PE-0002",
            "source_kind": "planned_event",
            "source_text": "林乔立即答复邀请",
        },
        {
            "requirement_ref": "PE-0003",
            "source_kind": "planned_event",
            "source_text": "林乔离开住处",
        },
        {
            "requirement_ref": must_ref,
            "source_kind": "must_not",
            "source_text": must_text,
        },
    ]
    core = {
        "identity": writing_check_package_tool.PROTOTYPE_IDENTITY,
        "prototype": True,
        "check_operation_id": "op-change-view-r2",
        "work": {
            "slot_ref": "S-0001",
            "work_ref": "S-0001@work",
            "work_rev": 2,
            "source_outline_ref": outline_ref,
            "text": WORK_TEXT,
            "text_sha256": hashlib.sha256(WORK_TEXT.encode("utf-8")).hexdigest(),
        },
        "planning_source": {
            "source_plan_version": 4,
            "source_plan_sha256": "a" * 64,
            "generation_watermark": {
                "source_plan_version": 4,
                "source_plan_sha256": "a" * 64,
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
        "input_package_sha256": hashlib.sha256(
            writing_check_package_tool._canonical_bytes(core)
        ).hexdigest(),
    }


def _judgment(
    category: str,
    requirement_ref: str | None,
    quote: str | None,
    explanation: str,
) -> dict:
    return {
        "category": category,
        "requirement_ref": requirement_ref,
        "evidence_quote": quote,
        "explanation": explanation,
    }


def _mixed_judgments(package: dict) -> list[dict]:
    refs = package["scope"]["requirement_refs"]
    return [
        _judgment(
            "covered",
            refs[0],
            "林乔拆开邀请信。",
            "原文已经覆盖拆信要求。",
        ),
        _judgment(
            "mismatch",
            refs[1],
            "她没有立即答复。",
            "当前写法与立即答复的计划不同。",
        ),
        _judgment(
            "unplanned",
            None,
            "守门人说：\n今晚不要出门。",
            "这段内容不在冻结 requirement 中。",
        ),
        _judgment(
            "missing",
            refs[2],
            None,
            "当前稿件没有写林乔离开住处。",
        ),
        _judgment(
            "unknown",
            refs[3],
            "窗外传来一声雷。",
            "当前文字不足以判断是否触碰该约束。",
        ),
    ]


def _request(judgments: list[dict] | None = None) -> dict:
    package = _package()
    rows = _mixed_judgments(package) if judgments is None else judgments
    result = writing_check_result_tool.execute(
        {
            "input_package": package,
            "provider_response": {"judgments": rows},
        }
    )
    return {"input_package": package, "check_result": result}


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


def test_five_categories_keep_only_four_changes_in_original_order() -> None:
    request = _request()
    before = copy.deepcopy(request)

    view = writing_check_change_reader.execute(request)
    rendered = writing_check_change_reader.render(request)

    assert request == before
    assert view["identity"] == "WRITING_CHECK_CHANGE_VIEW_R01"
    assert view["projection_only"] is True
    assert view["creates_judgments"] is False
    assert view["omitted_covered_count"] == 1
    assert [row["category"] for row in view["changes"]] == [
        "mismatch",
        "unplanned",
        "missing",
        "unknown",
    ]
    assert [row["explanation"] for row in view["changes"]] == [
        "当前写法与立即答复的计划不同。",
        "这段内容不在冻结 requirement 中。",
        "当前稿件没有写林乔离开住处。",
        "当前文字不足以判断是否触碰该约束。",
    ]
    assert "原文已经覆盖拆信要求" not in rendered
    assert "### 1. mismatch" in rendered
    assert "### 2. unplanned" in rendered
    assert "### 3. missing" in rendered
    assert "### 4. unknown" in rendered
    assert "只排版现有判断，不作整体结论" in rendered
    assert "不会创建 closeout" in rendered


def test_multiline_evidence_quote_is_preserved_byte_for_byte() -> None:
    request = _request()
    expected = "守门人说：\n今晚不要出门。"

    view = writing_check_change_reader.execute(request)
    rendered = writing_check_change_reader.render(request)

    assert view["changes"][1]["evidence_quote"] == expected
    assert expected in rendered
    assert rendered.encode("utf-8").decode("utf-8") == rendered


def test_all_covered_uses_only_honest_empty_change_message() -> None:
    package = _package()
    quotes = [
        "林乔拆开邀请信。",
        "她没有立即答复。",
        "窗外传来一声雷。",
        "守门人说：\n今晚不要出门。",
    ]
    judgments = [
        _judgment("covered", ref, quote, f"覆盖记录 {index}")
        for index, (ref, quote) in enumerate(
            zip(package["scope"]["requirement_refs"], quotes, strict=True),
            1,
        )
    ]
    result = writing_check_result_tool.execute(
        {
            "input_package": package,
            "provider_response": {"judgments": judgments},
        }
    )
    request = {"input_package": package, "check_result": result}

    view = writing_check_change_reader.execute(request)
    rendered = writing_check_change_reader.render(request)

    assert view["changes"] == []
    assert view["change_count"] == 0
    assert "本次没有需要展示的变化。" in rendered
    assert all(word not in rendered for word in FORBIDDEN_POSITIVE_WORDS)
    assert "覆盖记录" not in rendered


@pytest.mark.parametrize(
    "damage",
    [
        "package_sha",
        "work_sha",
        "result_ref",
        "operation_id",
        "outline_ref",
        "plan_watermark",
        "slot_watermark",
        "scope",
        "coverage",
        "result_extra",
    ],
)
def test_bad_identity_sha_watermark_scope_and_coverage_fail_closed(
    damage: str,
) -> None:
    request = _request()
    if damage == "package_sha":
        request["input_package"]["input_package_sha256"] = "0" * 64
    elif damage == "work_sha":
        request["input_package"]["work"]["text_sha256"] = "0" * 64
    elif damage == "result_ref":
        request["check_result"]["check_result_ref"] = "bad-result-ref"
    elif damage == "operation_id":
        request["check_result"]["operation_id"] = "op-other"
    elif damage == "outline_ref":
        request["check_result"]["source_outline_ref"] = "S-0001@outline-r9"
    elif damage == "plan_watermark":
        request["input_package"]["planning_source"][
            "source_plan_version"
        ] = 5
    elif damage == "slot_watermark":
        request["input_package"]["planning_source"]["generation_watermark"][
            "slot_rev"
        ] = 9
    elif damage == "scope":
        request["check_result"]["scope"]["target_ref"] = "S-9999"
    elif damage == "coverage":
        request["check_result"]["judgments"].pop()
    else:
        request["check_result"]["unexpected"] = True

    with pytest.raises(
        writing_check_change_reader.WritingCheckChangeReaderError
    ):
        writing_check_change_reader.execute(request)
    with pytest.raises(
        writing_check_change_reader.WritingCheckChangeReaderError
    ):
        writing_check_change_reader.render(request)


def test_cli_stdin_stdout_is_cross_process_byte_stable() -> None:
    request_bytes = _canonical(_request())

    first = _run_cli(stdin=request_bytes)
    second = _run_cli(stdin=request_bytes)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert first.stderr == second.stderr == b""
    assert "守门人说：\n今晚不要出门。".encode("utf-8") in first.stdout


def test_cli_failure_preserves_old_output_and_rejects_path_aliases(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "changes.md"
    request = _request()
    request["check_result"]["check_result_ref"] = "bad-result-ref"
    input_path.write_bytes(_canonical(request))
    old_output = "旧变化清单\n".encode("utf-8")
    output_path.write_bytes(old_output)

    failed = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    )

    assert failed.returncode == 1
    assert output_path.read_bytes() == old_output
    assert not list(tmp_path.glob(".changes.md.*.tmp"))

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

    symlink_path = tmp_path / "input-symlink.json"
    symlink_path.symlink_to(input_path)
    symlink_alias = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(symlink_path),
    )
    assert symlink_alias.returncode == 1
    assert b"OUTPUT_MUST_NOT_OVERWRITE_INPUT" in symlink_alias.stderr
    assert input_path.read_bytes() == input_before

    hardlink_path = tmp_path / "input-hardlink.json"
    os.link(input_path, hardlink_path)
    hardlink_alias = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(hardlink_path),
    )
    assert hardlink_alias.returncode == 1
    assert b"OUTPUT_MUST_NOT_OVERWRITE_INPUT" in hardlink_alias.stderr
    assert input_path.read_bytes() == input_before

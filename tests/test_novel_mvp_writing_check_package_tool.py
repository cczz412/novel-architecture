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
TOOL_PATH = PRODUCT_ROOT / "mvp" / "writing_check_package_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import chapter_slot_snapshot_tool, writing_check_package_tool
finally:
    sys.path.pop(0)


TEXT = "  雨落在窗台。\r\n\r\n“别动——”\n她说。  "


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _work_draft() -> dict:
    return {
        "contract": "WRITING_DESK_WORK_DRAFT",
        "version": "v1",
        "work_ref": "S-0001@work",
        "slot_ref": "S-0001",
        "source_outline_ref": "S-0001@outline-r2",
        "work_rev": 2,
        "state": "working",
        "entry_mode": "edited",
        "text": TEXT,
        "text_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
        "last_operation_id": "op-work-r2",
    }


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-CHECK-PACKAGE", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "让主角决定是否赴约",
                "summary": "作者计划了两个事件",
                "entry_state": "邀请仍未答复",
                "storyline_refs": [],
                "scene_refs": ["SCN-0001"],
                "exit_condition": "主角作出选择",
                "exit_hook": "选择影响下一章",
                "must_not": ["不得把规划冒充事实", "不得让主角瞬移"],
                "risks": ["动机可能不足"],
                "target_length": 1200,
                "outline_checkpoint": {
                    "outline_rev": 2,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 17,
                },
                "slot_status": "planned",
                "handover_parts": [],
                "truth_bearing": "primary",
                "updated_at": "2026-08-19 16:00:00",
                "rev": 3,
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "goal": "收到邀请",
                "summary": "主角看见邀请信",
                "pe_refs": ["PE-0002", "PE-0001"],
                "truth_bearing": "primary",
                "updated_at": "2026-08-19 16:00:00",
                "rev": 4,
            }
        ],
        "events": [
            {
                "id": "PE-0002",
                "scene_ref": "SCN-0001",
                "text": "主角拆开邀请信",
                "truth_bearing": "primary",
                "updated_at": "2026-08-19 16:00:00",
                "rev": 2,
            },
            {
                "id": "PE-0001",
                "scene_ref": "SCN-0001",
                "text": "主角犹豫是否赴约",
                "truth_bearing": "primary",
                "updated_at": "2026-08-19 16:00:00",
                "rev": 5,
            },
        ],
        "storylines": [],
        "hooks": [],
        "widgets": [],
        "pins": [],
        "must_carries": [],
        "option_records": [],
        "slot_mappings": [],
        "reconciliation_edges": [],
        "stop_points": {},
        "id_counters": {"MAP": 0, "RE": 0},
    }


def _snapshot() -> dict:
    plan = _plan()
    return chapter_slot_snapshot_tool.execute(
        {
            "plan": plan,
            "slot_ref": "S-0001",
            "source_plan_version": 4,
            "source_plan_sha256": hashlib.sha256(
                _canonical_bytes(plan)
            ).hexdigest(),
        }
    )


def _request() -> dict:
    return {
        "work_draft": _work_draft(),
        "chapter_slot_snapshot": _snapshot(),
        "check_operation_id": "op-t14-package-r2",
    }


def _must_not_ref(text: str) -> str:
    digest = hashlib.sha256(b"must_not\0" + text.encode("utf-8")).hexdigest()[:12]
    return f"S-0001@outline-r2#must_not:{digest}"


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env=env,
    )


def test_r2_draft_and_current_slot_build_stable_pe_and_must_not_package() -> None:
    request = _request()
    before = copy.deepcopy(request)

    package = writing_check_package_tool.execute(request)

    expected_refs = [
        "PE-0002",
        "PE-0001",
        _must_not_ref("不得把规划冒充事实"),
        _must_not_ref("不得让主角瞬移"),
    ]
    assert package["identity"] == "WRITING_CHECK_INPUT_PACKAGE_PROTOTYPE_R01"
    assert package["prototype"] is True
    assert package["work"]["text"] == TEXT
    assert package["scope"] == {
        "mode": "chapter",
        "target_ref": "S-0001",
        "requirement_refs": expected_refs,
    }
    assert [row["requirement_ref"] for row in package["requirements"]] == expected_refs
    assert [row["source_kind"] for row in package["requirements"]] == [
        "planned_event",
        "planned_event",
        "must_not",
        "must_not",
    ]
    assert [row["source_text"] for row in package["requirements"]] == [
        "主角拆开邀请信",
        "主角犹豫是否赴约",
        "不得把规划冒充事实",
        "不得让主角瞬移",
    ]
    assert not {"动机可能不足", "主角作出选择"} & {
        row["source_text"] for row in package["requirements"]
    }
    core = dict(package)
    package_sha = core.pop("input_package_sha256")
    assert package_sha == hashlib.sha256(_canonical_bytes(core)).hexdigest()
    assert "judgments" not in package and package["identity"] != "WRITING_DESK_CHECK_RESULT"
    assert request == before


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda value: value["work_draft"].update(text_sha256="0" * 64),
            "WORK_DRAFT_TEXT_SHA_MISMATCH",
        ),
        (
            lambda value: value["work_draft"].update(
                slot_ref="S-9999",
                work_ref="S-9999@work",
            ),
            "WORK_AND_SLOT_REF_MISMATCH",
        ),
        (
            lambda value: value["work_draft"].update(
                source_outline_ref="S-0001@outline-r1"
            ),
            "SOURCE_OUTLINE_REF_STALE",
        ),
        (
            lambda value: value["chapter_slot_snapshot"][
                "generation_watermark"
            ].update(source_plan_sha256="0" * 64),
            "CHAPTER_SLOT_WATERMARK_MISMATCH",
        ),
        (
            lambda value: value["chapter_slot_snapshot"][
                "generation_watermark"
            ].update(outline_source_commit_seq=999),
            "OUTLINE_COMMIT_WATERMARK_MISMATCH",
        ),
    ],
)
def test_sha_slot_and_outline_watermark_drift_reject(
    mutate,
    error: str,
) -> None:
    request = _request()
    mutate(request)
    with pytest.raises(writing_check_package_tool.WritingCheckPackageError, match=error):
        writing_check_package_tool.execute(request)


def test_duplicate_requirement_ref_rejects() -> None:
    request = _request()
    request["chapter_slot_snapshot"]["must_not"].append(
        request["chapter_slot_snapshot"]["must_not"][0]
    )

    with pytest.raises(
        writing_check_package_tool.WritingCheckPackageError,
        match="DUPLICATE_REQUIREMENT_REF",
    ):
        writing_check_package_tool.execute(request)


def test_request_cannot_carry_a_second_prose_field() -> None:
    request = _request()
    request["text"] = "调用方另塞的正文"

    with pytest.raises(
        writing_check_package_tool.WritingCheckPackageError,
        match="REQUEST_FIELDS_INVALID",
    ):
        writing_check_package_tool.execute(request)


def test_stdin_stdout_and_cross_process_bytes_are_deterministic() -> None:
    input_bytes = _canonical_bytes(_request())

    first = _run_cli(stdin=input_bytes)
    second = _run_cli(stdin=input_bytes)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["prototype"] is True
    assert first.stderr == second.stderr == b""


def test_file_cli_failure_preserves_old_output_and_never_overwrites_input(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "package.json"
    old_output = b'{"old":true}\n'
    bad_request = _request()
    bad_request["work_draft"]["text_sha256"] = "0" * 64
    input_path.write_bytes(_canonical_bytes(bad_request))
    output_path.write_bytes(old_output)

    failed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert failed.returncode == 1
    assert output_path.read_bytes() == old_output
    assert not list(tmp_path.glob(".package.json.*.tmp"))

    input_before = input_path.read_bytes()
    same_path = _run_cli("--input", str(input_path), "--output", str(input_path))
    assert same_path.returncode == 1
    assert b"OUTPUT_MUST_NOT_OVERWRITE_INPUT" in same_path.stderr
    assert input_path.read_bytes() == input_before


def test_file_cli_success_writes_parseable_package_atomically(tmp_path: Path) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "package.json"
    input_path.write_bytes(_canonical_bytes(_request()))
    input_before = input_path.read_bytes()

    completed = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    )

    assert completed.returncode == 0
    assert completed.stdout == completed.stderr == b""
    assert json.loads(output_path.read_bytes())["prototype"] is True
    assert input_path.read_bytes() == input_before
    assert not list(tmp_path.glob(".package.json.*.tmp"))

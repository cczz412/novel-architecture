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
TOOL_PATH = PRODUCT_ROOT / "mvp" / "writing_check_result_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import writing_check_package_tool, writing_check_result_tool
finally:
    sys.path.pop(0)


TEXT = "林乔拆开邀请信。她没有立即答复。窗外传来一声雷。"


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


def _package() -> dict:
    must_text = "不得让林乔当场答应赴约"
    must_ref = writing_check_package_tool._must_not_ref(
        "S-0001@outline-r2", must_text
    )
    core = {
        "identity": writing_check_package_tool.PROTOTYPE_IDENTITY,
        "prototype": True,
        "check_operation_id": "op-t14-check-r2",
        "work": {
            "slot_ref": "S-0001",
            "work_ref": "S-0001@work",
            "work_rev": 2,
            "source_outline_ref": "S-0001@outline-r2",
            "text": TEXT,
            "text_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
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
        "requirements": [
            {
                "requirement_ref": "PE-0001",
                "source_kind": "planned_event",
                "source_text": "林乔拆开邀请信",
            },
            {
                "requirement_ref": must_ref,
                "source_kind": "must_not",
                "source_text": must_text,
            },
        ],
        "scope": {
            "mode": "chapter",
            "target_ref": "S-0001",
            "requirement_refs": ["PE-0001", must_ref],
        },
    }
    return {
        **core,
        "input_package_sha256": hashlib.sha256(
            writing_check_package_tool._canonical_bytes(core)
        ).hexdigest(),
    }


def _planned(
    requirement_ref: str,
    category: str,
    quote: str | None,
    explanation: str,
) -> dict:
    return {
        "category": category,
        "requirement_ref": requirement_ref,
        "evidence_quote": quote,
        "explanation": explanation,
    }


def _valid_response() -> dict:
    refs = _package()["scope"]["requirement_refs"]
    return {
        "judgments": [
            _planned(
                refs[0],
                "covered",
                "林乔拆开邀请信。",
                "原文明确写出拆信。",
            ),
            _planned(
                refs[1],
                "missing",
                None,
                "本次范围内未见该约束的明确承接。",
            ),
            {
                "category": "unplanned",
                "requirement_ref": None,
                "evidence_quote": "窗外传来一声雷。",
                "explanation": "这个细节不在已冻结 requirement 中。",
            },
        ]
    }


def _request(response: dict | None = None) -> dict:
    return {
        "input_package": _package(),
        "provider_response": _valid_response() if response is None else response,
    }


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env=env,
    )


def test_covered_missing_and_unplanned_build_formal_full_chapter_result() -> None:
    request = _request()
    before = copy.deepcopy(request)

    result = writing_check_result_tool.execute(request)

    assert set(result) == writing_check_result_tool.RESULT_KEYS
    assert result == {
        "contract": "WRITING_DESK_CHECK_RESULT",
        "version": "v1",
        "check_result_ref": "S-0001@work-r2#check-op-t14-check-r2",
        "operation_id": "op-t14-check-r2",
        "slot_ref": "S-0001",
        "work_ref": "S-0001@work",
        "work_rev": 2,
        "work_text_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
        "source_outline_ref": "S-0001@outline-r2",
        "source_commit_seq": 17,
        "input_package_sha256": request["input_package"]["input_package_sha256"],
        "scope": copy.deepcopy(request["input_package"]["scope"]),
        "status": "completed",
        "judgments": copy.deepcopy(request["provider_response"]["judgments"]),
    }
    assert not ({"pass", "clean", "checked", "all_clear"} & set(result))
    assert request == before


def test_mismatch_and_unknown_with_optional_exact_quote_are_valid() -> None:
    refs = _package()["scope"]["requirement_refs"]
    response = {
        "judgments": [
            _planned(
                refs[0],
                "mismatch",
                "她没有立即答复。",
                "已写内容与该要求不一致。",
            ),
            _planned(
                refs[1],
                "unknown",
                "林乔拆开邀请信。",
                "当前文字不足以安全归类。",
            ),
        ]
    }

    result = writing_check_result_tool.execute(_request(response))

    assert [row["category"] for row in result["judgments"]] == [
        "mismatch",
        "unknown",
    ]
    assert result["status"] == "completed"


def test_evidence_text_kinds_distinguish_existing_absence_and_quote_states() -> None:
    judgments = [
        _planned("PE-0001", "missing", None, "明确缺失"),
        _planned("PE-0001", "unknown", None, "无法定位"),
        _planned("PE-0001", "unknown", "相关原文", "仍无法判断"),
        _planned("PE-0001", "mismatch", "冲突原文", "明确冲突"),
    ]

    assert [
        writing_check_result_tool.evidence_text_kind(row) for row in judgments
    ] == [
        "missing_without_quote",
        "unknown_without_quote",
        "unknown_with_quote",
        "quoted",
    ]


def test_null_quote_finding_ref_uses_zero_utf8_bytes_and_category_stays_distinct() -> None:
    result_ref = "S-0001@work-r2#check-op-t14-check-r2"
    unknown = _planned("PE-0001", "unknown", None, "当前无法安全判断")
    missing = _planned("PE-0001", "missing", None, "当前无法安全判断")
    expected_digest = hashlib.sha256(
        b"unknown\0PE-0001\0\0" + "当前无法安全判断".encode("utf-8")
    ).hexdigest()[:12]

    assert writing_check_result_tool.finding_ref(result_ref, unknown) == (
        f"{result_ref}#finding:{expected_digest}"
    )
    assert writing_check_result_tool.finding_ref(
        result_ref, missing
    ) != writing_check_result_tool.finding_ref(result_ref, unknown)


@pytest.mark.parametrize("quote", ["", " ", "\t", "\r\n"])
def test_empty_or_whitespace_quote_is_not_a_second_null_encoding(quote: str) -> None:
    judgment = _planned("PE-0001", "unknown", quote, "不能靠空白冒充引文")

    with pytest.raises(
        writing_check_result_tool.WritingCheckResultError,
        match="JUDGMENT_EVIDENCE_QUOTE_INVALID",
    ):
        writing_check_result_tool.evidence_text_kind(judgment)


@pytest.mark.parametrize(
    ("response_builder", "error"),
    [
        (
            lambda refs: {"judgments": [_planned(refs[0], "covered", "林乔拆开邀请信。", "已覆盖")]},
            "PLANNED_REQUIREMENT_COVERAGE_INCOMPLETE",
        ),
        (
            lambda refs: {
                "judgments": [
                    _planned(refs[0], "covered", "林乔拆开邀请信。", "已覆盖"),
                    _planned(refs[0], "unknown", None, "仍不确定"),
                    _planned(refs[1], "missing", None, "缺失"),
                ]
            },
            "PLANNED_REQUIREMENT_REF_DUPLICATE",
        ),
        (
            lambda refs: {
                "judgments": [
                    _planned("PE-9999", "covered", "林乔拆开邀请信。", "错引用"),
                    _planned(refs[1], "missing", None, "缺失"),
                ]
            },
            "PLANNED_REQUIREMENT_REF_INVALID",
        ),
    ],
)
def test_missing_duplicate_and_unknown_requirement_reject(
    response_builder,
    error: str,
) -> None:
    refs = _package()["scope"]["requirement_refs"]
    with pytest.raises(writing_check_result_tool.WritingCheckResultError, match=error):
        writing_check_result_tool.execute(_request(response_builder(refs)))


@pytest.mark.parametrize(
    ("judgment", "error"),
    [
        (
            _planned("PE-0001", "covered", "原文里没有这句", "证据错"),
            "EVIDENCE_QUOTE_NOT_IN_WORK_TEXT",
        ),
        (
            _planned("PE-0001", "mismatch", None, "需要原文"),
            "EVIDENCE_QUOTE_NOT_IN_WORK_TEXT",
        ),
        (
            _planned("PE-0001", "missing", "林乔", "missing 不应有证据"),
            "MISSING_EVIDENCE_QUOTE_MUST_BE_NULL",
        ),
        (
            _planned("PE-0001", "unknown", "不存在的原文", "不确定"),
            "UNKNOWN_EVIDENCE_QUOTE_NOT_IN_WORK_TEXT",
        ),
        (
            {
                "category": "unplanned",
                "requirement_ref": "PE-0001",
                "evidence_quote": "窗外传来一声雷。",
                "explanation": "不应引用已有 requirement",
            },
            "UNPLANNED_REQUIREMENT_REF_MUST_BE_NULL",
        ),
    ],
)
def test_quote_and_unplanned_reference_rules_reject(
    judgment: dict,
    error: str,
) -> None:
    refs = _package()["scope"]["requirement_refs"]
    response = {
        "judgments": [
            judgment,
            _planned(refs[1], "missing", None, "缺失"),
        ]
    }
    with pytest.raises(writing_check_result_tool.WritingCheckResultError, match=error):
        writing_check_result_tool.execute(_request(response))


@pytest.mark.parametrize(
    "injection",
    [
        {"check_result_ref": "provider-made"},
        {"scope": {"mode": "scene"}},
        {"replacement_text": "供应商重写正文"},
    ],
)
def test_provider_cannot_inject_identity_scope_or_replacement(injection: dict) -> None:
    response = {**_valid_response(), **injection}
    with pytest.raises(
        writing_check_result_tool.WritingCheckResultError,
        match="PROVIDER_RESPONSE_FIELDS_INVALID",
    ):
        writing_check_result_tool.execute(_request(response))


def test_provider_judgment_extra_field_is_rejected() -> None:
    response = _valid_response()
    response["judgments"][0]["replacement_text"] = "供应商重写"
    with pytest.raises(
        writing_check_result_tool.WritingCheckResultError,
        match="PROVIDER_JUDGMENT_FIELDS_INVALID",
    ):
        writing_check_result_tool.execute(_request(response))


def test_package_sha_scope_and_text_drift_reject() -> None:
    request = _request()
    request["input_package"]["input_package_sha256"] = "0" * 64
    with pytest.raises(
        writing_check_result_tool.WritingCheckResultError,
        match="INPUT_PACKAGE_SHA_MISMATCH",
    ):
        writing_check_result_tool.execute(request)

    scope_drift = _request()
    scope_drift["input_package"]["scope"]["requirement_refs"].reverse()
    with pytest.raises(
        writing_check_result_tool.WritingCheckResultError,
        match="INPUT_PACKAGE_SCOPE_REQUIREMENTS_MISMATCH",
    ):
        writing_check_result_tool.execute(scope_drift)

    text_drift = _request()
    text_drift["input_package"]["work"]["text"] += "篡改"
    with pytest.raises(
        writing_check_result_tool.WritingCheckResultError,
        match="INPUT_PACKAGE_TEXT_SHA_MISMATCH",
    ):
        writing_check_result_tool.execute(text_drift)


def test_stdin_stdout_cross_process_bytes_are_deterministic() -> None:
    request_bytes = _canonical_bytes(_request())
    first = _run_cli(stdin=request_bytes)
    second = _run_cli(stdin=request_bytes)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["status"] == "completed"
    assert first.stderr == second.stderr == b""


def test_file_cli_failure_preserves_old_output_and_never_overwrites_input(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "result.json"
    old_output = b'{"old":true}\n'
    bad_request = _request()
    bad_request["provider_response"]["judgments"].pop(0)
    input_path.write_bytes(_canonical_bytes(bad_request))
    output_path.write_bytes(old_output)

    failed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert failed.returncode == 1
    assert output_path.read_bytes() == old_output
    assert not list(tmp_path.glob(".result.json.*.tmp"))
    input_before = input_path.read_bytes()
    same_path = _run_cli("--input", str(input_path), "--output", str(input_path))
    assert same_path.returncode == 1
    assert b"OUTPUT_MUST_NOT_OVERWRITE_INPUT" in same_path.stderr
    assert input_path.read_bytes() == input_before

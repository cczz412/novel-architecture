"""把检测 provider 的 judgments 收窄为正式 WRITING_DESK_CHECK_RESULT v1。

provider 只有诊断分类、原文证据与解释权。结果身份、工作稿/规划水位、
scope、coverage 和 completed 状态全部由程序从已冻结输入包生成。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn

if __package__:
    from . import writing_check_package_tool
    from .workspace import OPERATION_ID_RE
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import writing_check_package_tool
    from mvp.workspace import OPERATION_ID_RE


REQUEST_KEYS = {"input_package", "provider_response"}
PROVIDER_KEYS = {"judgments"}
PACKAGE_KEYS = {
    "identity",
    "prototype",
    "check_operation_id",
    "work",
    "planning_source",
    "requirements",
    "scope",
    "input_package_sha256",
}
WORK_KEYS = {
    "slot_ref",
    "work_ref",
    "work_rev",
    "source_outline_ref",
    "text",
    "text_sha256",
}
PLANNING_SOURCE_KEYS = {
    "source_plan_version",
    "source_plan_sha256",
    "generation_watermark",
    "source_commit_seq",
}
WATERMARK_KEYS = {
    "source_plan_version",
    "source_plan_sha256",
    "slot_rev",
    "outline_source_commit_seq",
}
REQUIREMENT_KEYS = {"requirement_ref", "source_kind", "source_text"}
SCOPE_KEYS = {"mode", "target_ref", "requirement_refs"}
JUDGMENT_KEYS = {
    "category",
    "requirement_ref",
    "evidence_quote",
    "explanation",
}
RESULT_KEYS = {
    "contract",
    "version",
    "check_result_ref",
    "operation_id",
    "slot_ref",
    "work_ref",
    "work_rev",
    "work_text_sha256",
    "source_outline_ref",
    "source_commit_seq",
    "input_package_sha256",
    "scope",
    "status",
    "judgments",
}
PLANNED_CATEGORIES = {"covered", "mismatch", "missing", "unknown"}
ALL_CATEGORIES = {*PLANNED_CATEGORIES, "unplanned"}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class WritingCheckResultError(ValueError):
    """检测包或 provider 输出不足以生成正式结果。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise WritingCheckResultError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise WritingCheckResultError("VALUE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _string(value: object, code: str, *, non_empty: bool = False) -> str:
    if not isinstance(value, str) or (non_empty and not value):
        _fail(code)
    return value


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(code)
    return value


def _non_negative_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(code)
    return value


def _sha(value: object, code: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _validated_package(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != PACKAGE_KEYS:
        _fail("INPUT_PACKAGE_FIELDS_INVALID")
    package = copy.deepcopy(value)
    if (
        package["identity"]
        != writing_check_package_tool.PROTOTYPE_IDENTITY
        or package["prototype"] is not True
    ):
        _fail("INPUT_PACKAGE_IDENTITY_INVALID")
    operation_id = package["check_operation_id"]
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("CHECK_OPERATION_ID_INVALID")

    work = package["work"]
    if not isinstance(work, dict) or set(work) != WORK_KEYS:
        _fail("INPUT_PACKAGE_WORK_INVALID")
    slot_ref = _string(work["slot_ref"], "INPUT_PACKAGE_SLOT_REF_INVALID", non_empty=True)
    work_ref = _string(work["work_ref"], "INPUT_PACKAGE_WORK_REF_INVALID", non_empty=True)
    _positive_int(work["work_rev"], "INPUT_PACKAGE_WORK_REV_INVALID")
    source_outline_ref = _string(
        work["source_outline_ref"],
        "INPUT_PACKAGE_OUTLINE_REF_INVALID",
        non_empty=True,
    )
    text = _string(work["text"], "INPUT_PACKAGE_TEXT_INVALID")
    text_sha = _sha(work["text_sha256"], "INPUT_PACKAGE_TEXT_SHA_INVALID")
    if work_ref != f"{slot_ref}@work":
        _fail("INPUT_PACKAGE_WORK_REF_MISMATCH")
    if _sha256(text.encode("utf-8")) != text_sha:
        _fail("INPUT_PACKAGE_TEXT_SHA_MISMATCH")

    planning = package["planning_source"]
    if not isinstance(planning, dict) or set(planning) != PLANNING_SOURCE_KEYS:
        _fail("INPUT_PACKAGE_PLANNING_SOURCE_INVALID")
    plan_version = _positive_int(
        planning["source_plan_version"], "INPUT_PACKAGE_PLAN_VERSION_INVALID"
    )
    plan_sha = _sha(
        planning["source_plan_sha256"], "INPUT_PACKAGE_PLAN_SHA_INVALID"
    )
    source_commit_seq = _non_negative_int(
        planning["source_commit_seq"], "INPUT_PACKAGE_COMMIT_SEQ_INVALID"
    )
    watermark = planning["generation_watermark"]
    if not isinstance(watermark, dict) or set(watermark) != WATERMARK_KEYS:
        _fail("INPUT_PACKAGE_WATERMARK_INVALID")
    if (
        watermark["source_plan_version"] != plan_version
        or watermark["source_plan_sha256"] != plan_sha
        or watermark["outline_source_commit_seq"] != source_commit_seq
    ):
        _fail("INPUT_PACKAGE_WATERMARK_MISMATCH")
    _positive_int(watermark["slot_rev"], "INPUT_PACKAGE_SLOT_REV_INVALID")

    requirements = package["requirements"]
    if not isinstance(requirements, list):
        _fail("INPUT_PACKAGE_REQUIREMENTS_INVALID")
    requirement_refs: list[str] = []
    for index, row in enumerate(requirements):
        if not isinstance(row, dict) or set(row) != REQUIREMENT_KEYS:
            _fail(f"INPUT_PACKAGE_REQUIREMENT_INVALID:{index}")
        requirement_ref = _string(
            row["requirement_ref"],
            f"INPUT_PACKAGE_REQUIREMENT_REF_INVALID:{index}",
            non_empty=True,
        )
        if row["source_kind"] not in {"planned_event", "must_not"}:
            _fail(f"INPUT_PACKAGE_REQUIREMENT_KIND_INVALID:{index}")
        source_text = _string(
            row["source_text"], f"INPUT_PACKAGE_REQUIREMENT_TEXT_INVALID:{index}"
        )
        if row["source_kind"] == "must_not":
            expected_ref = writing_check_package_tool._must_not_ref(
                source_outline_ref, source_text
            )
            if requirement_ref != expected_ref:
                _fail(f"INPUT_PACKAGE_MUST_NOT_REF_INVALID:{index}")
        requirement_refs.append(requirement_ref)
    if len(requirement_refs) != len(set(requirement_refs)):
        _fail("INPUT_PACKAGE_REQUIREMENT_REFS_DUPLICATE")

    scope = package["scope"]
    if not isinstance(scope, dict) or set(scope) != SCOPE_KEYS:
        _fail("INPUT_PACKAGE_SCOPE_INVALID")
    if scope["mode"] != "chapter" or scope["target_ref"] != slot_ref:
        _fail("INPUT_PACKAGE_SCOPE_IDENTITY_MISMATCH")
    if scope["requirement_refs"] != requirement_refs:
        _fail("INPUT_PACKAGE_SCOPE_REQUIREMENTS_MISMATCH")

    package_sha = _sha(
        package["input_package_sha256"], "INPUT_PACKAGE_SHA_INVALID"
    )
    package_core = copy.deepcopy(package)
    package_core.pop("input_package_sha256")
    if _sha256(writing_check_package_tool._canonical_bytes(package_core)) != package_sha:
        _fail("INPUT_PACKAGE_SHA_MISMATCH")
    return package


def _validated_judgments(
    provider_response: object,
    package: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(provider_response, dict) or set(provider_response) != PROVIDER_KEYS:
        _fail("PROVIDER_RESPONSE_FIELDS_INVALID")
    raw_judgments = provider_response["judgments"]
    if not isinstance(raw_judgments, list):
        _fail("PROVIDER_JUDGMENTS_INVALID")
    work_text = package["work"]["text"]
    required_refs = package["scope"]["requirement_refs"]
    required_set = set(required_refs)
    seen_planned: list[str] = []
    judgments: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_judgments):
        if not isinstance(raw, dict) or set(raw) != JUDGMENT_KEYS:
            _fail(f"PROVIDER_JUDGMENT_FIELDS_INVALID:{index}")
        category = raw["category"]
        if category not in ALL_CATEGORIES:
            _fail(f"PROVIDER_JUDGMENT_CATEGORY_INVALID:{index}")
        requirement_ref = raw["requirement_ref"]
        quote = raw["evidence_quote"]
        _string(raw["explanation"], f"PROVIDER_EXPLANATION_INVALID:{index}")
        if category == "unplanned":
            if requirement_ref is not None:
                _fail(f"UNPLANNED_REQUIREMENT_REF_MUST_BE_NULL:{index}")
        else:
            if not isinstance(requirement_ref, str) or requirement_ref not in required_set:
                _fail(f"PLANNED_REQUIREMENT_REF_INVALID:{index}")
            if requirement_ref in seen_planned:
                _fail(f"PLANNED_REQUIREMENT_REF_DUPLICATE:{index}")
            seen_planned.append(requirement_ref)

        if category in {"covered", "mismatch", "unplanned"}:
            if not isinstance(quote, str) or not quote or quote not in work_text:
                _fail(f"EVIDENCE_QUOTE_NOT_IN_WORK_TEXT:{index}")
        elif category == "missing":
            if quote is not None:
                _fail(f"MISSING_EVIDENCE_QUOTE_MUST_BE_NULL:{index}")
        elif quote is not None and (
            not isinstance(quote, str) or not quote or quote not in work_text
        ):
            _fail(f"UNKNOWN_EVIDENCE_QUOTE_NOT_IN_WORK_TEXT:{index}")
        judgments.append(copy.deepcopy(raw))

    if len(seen_planned) != len(required_refs) or set(seen_planned) != required_set:
        _fail("PLANNED_REQUIREMENT_COVERAGE_INCOMPLETE")
    return judgments


def _validate_result_shape(value: dict[str, Any]) -> None:
    if set(value) != RESULT_KEYS:
        _fail("RESULT_FIELDS_INVALID")
    if (
        value["contract"] != "WRITING_DESK_CHECK_RESULT"
        or value["version"] != "v1"
        or value["status"] != "completed"
    ):
        _fail("RESULT_IDENTITY_INVALID")
    expected_ref = (
        f"{value['work_ref']}-r{value['work_rev']}#check-{value['operation_id']}"
    )
    if value["check_result_ref"] != expected_ref:
        _fail("RESULT_REF_INVALID")
    if set(value["scope"]) != SCOPE_KEYS:
        _fail("RESULT_SCOPE_INVALID")


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """纯对象入口：只接输入包和 provider judgments。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    package = _validated_package(request["input_package"])
    judgments = _validated_judgments(request["provider_response"], package)
    work = package["work"]
    planning = package["planning_source"]
    operation_id = package["check_operation_id"]
    result = {
        "contract": "WRITING_DESK_CHECK_RESULT",
        "version": "v1",
        "check_result_ref": (
            f"{work['work_ref']}-r{work['work_rev']}#check-{operation_id}"
        ),
        "operation_id": operation_id,
        "slot_ref": work["slot_ref"],
        "work_ref": work["work_ref"],
        "work_rev": work["work_rev"],
        "work_text_sha256": work["text_sha256"],
        "source_outline_ref": work["source_outline_ref"],
        "source_commit_seq": planning["source_commit_seq"],
        "input_package_sha256": package["input_package_sha256"],
        "scope": copy.deepcopy(package["scope"]),
        "status": "completed",
        "judgments": judgments,
    }
    _validate_result_shape(result)
    return result


# LOCAL_FILESYSTEM_ONLY: 路径只在 CLI 适配层出现；纯对象 execute 不接路径。
def _load_request(input_path: str | None) -> dict[str, Any]:
    if input_path in {None, "-"}:
        raw = sys.stdin.buffer.read()
    else:
        path = Path(input_path)
        if not path.is_file():
            _fail("INPUT_PATH_NOT_FILE")
        raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WritingCheckResultError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail("INPUT_OBJECT_REQUIRED")
    return value


def _same_input_output_path(input_path: str | None, output_path: str | None) -> bool:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return False
    source = Path(input_path)
    target = Path(output_path)
    if source.resolve() == target.resolve():
        return True
    if source.exists() and target.exists():
        return os.path.samefile(source, target)
    return False


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_atomic(output_path: str | None, value: dict[str, Any]) -> None:
    payload = _canonical_bytes(value)
    if output_path in {None, "-"}:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
        return
    path = Path(output_path)
    if not path.parent.is_dir():
        _fail("OUTPUT_PARENT_NOT_DIRECTORY")
    if path.exists() and not path.is_file():
        _fail("OUTPUT_PATH_NOT_FILE")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="收窄 provider judgments 为正式写作区检测结果"
    )
    parser.add_argument("--input", default="-")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    try:
        if _same_input_output_path(args.input, args.output):
            _fail("OUTPUT_MUST_NOT_OVERWRITE_INPUT")
        result = execute(_load_request(args.input))
        _write_atomic(args.output, result)
    except (OSError, WritingCheckResultError) as exc:
        print(f"WRITING_CHECK_RESULT_ERROR:{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

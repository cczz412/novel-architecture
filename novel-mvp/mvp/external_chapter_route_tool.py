"""外来正文当前版本读门：C10 → C11 current → C1 current → M2。

``execute`` 只处理内存对象，不接受调用方自报的车道或下一站。文件读写集中在
文件末尾的 ``LOCAL_FILESYSTEM_ONLY`` 适配层。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn


if not __package__:  # 允许直接运行 python novel-mvp/mvp/external_chapter_route_tool.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts import validate_c10_intake_material_identity as c10_contract  # noqa: E402
from contracts import validate_c11_chapter_revision_ledger as c11_contract  # noqa: E402


REQUEST_KEYS = frozenset(
    {"material_identity", "chapter_revision_ledger", "chapter_doc"}
)
RECEIPT_IDENTITY = "EXTERNAL_CHAPTER_ROUTE_RECEIPT_R01"
SOURCE_KIND = "EXTERNAL_CONFIRMED_CHAPTER"
NEXT_STATION = "M2_SEGMENT"


class ExternalChapterRouteError(ValueError):
    """三份现役对象不能证明同一份当前外来章节。"""


def _fail(code: str) -> NoReturn:
    raise ExternalChapterRouteError(code)


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ExternalChapterRouteError("VALUE_NOT_JSON_SERIALIZABLE") from exc


def _validate_request(request: object) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(request, dict):
        _fail("REQUEST_MUST_BE_OBJECT")
    keys = set(request)
    if keys != REQUEST_KEYS:
        missing = sorted(REQUEST_KEYS - keys)
        extra = sorted(keys - REQUEST_KEYS)
        _fail(f"REQUEST_FIELDS_INVALID:missing={missing}:extra={extra}")
    for key in sorted(REQUEST_KEYS):
        if not isinstance(request[key], dict):
            _fail(f"REQUEST_MEMBER_MUST_BE_OBJECT:{key}")
    _canonical_json_bytes(request)
    return (
        request["material_identity"],
        request["chapter_revision_ledger"],
        request["chapter_doc"],
    )


def _validate_material_identity(material: dict[str, Any]) -> None:
    try:
        c10_contract.validate_record(material, "material_identity")
    except c10_contract.ContractValidationError as exc:
        raise ExternalChapterRouteError(f"C10_INVALID:{exc}") from exc
    current = c10_contract.current_identity(material)
    if current.get("state") != "CONFIRMED" or current.get("role") != "CHAPTER":
        _fail("C10_NOT_CONFIRMED_CHAPTER")
    if not c10_contract.c1_emission_eligible(material):
        _fail("C10_NOT_ELIGIBLE_FOR_C1")


def _validate_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    try:
        c11_contract.validate_schema_document(c11_contract.schema_validator(), ledger)
        c11_contract._validate_ledger_structure(ledger)
    except c11_contract.ContractError as exc:
        raise ExternalChapterRouteError(f"C11_INVALID:{exc}") from exc
    if ledger.get("contract") != "CHAPTER_REVISION_LEDGER":
        _fail("C11_LEDGER_IDENTITY_REQUIRED")
    return ledger["revisions"][-1]


def _validate_external_origin(
    current_revision: dict[str, Any],
    material: dict[str, Any],
) -> None:
    verdict = c11_contract.validate_current_c10_eligibility(
        current_revision["content_ref"],
        current_revision["origin_material_ref"],
        [material],
        require_referenced_revision_is_current=True,
    )
    if verdict != "C10_CONFIRMED_CHAPTER_ELIGIBLE":
        _fail(f"C10_C11_ORIGIN_NOT_CURRENT:{verdict}")


def _validate_chapter_doc(
    chapter_doc: dict[str, Any],
    ledger: dict[str, Any],
    current_revision: dict[str, Any],
) -> dict[str, Any]:
    if chapter_doc.get("contract") != "C1_CHAPTER_DOC":
        _fail("C1_CURRENT_VIEW_REQUIRED")
    try:
        c11_contract.validate_schema_document(
            c11_contract.schema_validator(),
            chapter_doc,
        )
    except c11_contract.ContractError as exc:
        raise ExternalChapterRouteError(f"C1_INVALID:{exc}") from exc

    text = chapter_doc["text"]
    text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    revision_ref = chapter_doc["chapter_revision_ref"]
    expected_ref = {
        "chapter_id": ledger["chapter_id"],
        "revision_no": ledger["current_revision_no"],
        "revision_text_sha256": current_revision["text_sha256"],
    }

    if chapter_doc["id"] != ledger["chapter_id"]:
        _fail("C1_CHAPTER_ID_MISMATCH")
    if chapter_doc["title"] != current_revision["title"]:
        _fail("C1_TITLE_MISMATCH")
    if text_sha256 != current_revision["text_sha256"]:
        _fail("C1_TEXT_SHA256_MISMATCH")
    if len(text) != current_revision["chars"]:
        _fail("C1_CHAR_COUNT_MISMATCH")
    if revision_ref != expected_ref:
        _fail("C1_CURRENT_REVISION_REF_MISMATCH")
    return expected_ref


def execute(request: dict) -> dict:
    """证明三份对象闭合后，返回只读的 M2 下一站回执。"""

    material, ledger, chapter_doc = _validate_request(request)
    _validate_material_identity(material)
    current_revision = _validate_ledger(ledger)
    _validate_external_origin(current_revision, material)
    revision_ref = _validate_chapter_doc(chapter_doc, ledger, current_revision)
    return {
        "identity": RECEIPT_IDENTITY,
        "accepted": True,
        "source_kind": SOURCE_KIND,
        "chapter_id": ledger["chapter_id"],
        "chapter_revision_ref": copy.deepcopy(revision_ref),
        "next_station": NEXT_STATION,
        "writes": [],
    }


# LOCAL_FILESYSTEM_ONLY: 仅供当前本机 CLI；未来调用方应直接传 JSON 对象。
def _load_request(input_path: str | None) -> dict:
    if input_path in {None, "-"}:
        raw = sys.stdin.buffer.read()
    else:
        path = Path(input_path)
        if not path.is_file():
            raise ExternalChapterRouteError(f"INPUT_PATH_NOT_FILE:{path}")
        raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExternalChapterRouteError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise ExternalChapterRouteError("REQUEST_MUST_BE_OBJECT")
    return value


def _json_output_bytes(value: dict) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, value: dict) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise ExternalChapterRouteError(f"OUTPUT_PARENT_NOT_DIRECTORY:{parent}")
    if path.exists() and not path.is_file():
        raise ExternalChapterRouteError(f"OUTPUT_PATH_NOT_FILE:{path}")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(_json_output_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        _fsync_directory(parent)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _file_identity(
    path: Path,
    *,
    label: str,
) -> tuple[Path, os.stat_result | None]:
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ExternalChapterRouteError(f"FILE_IDENTITY_UNAVAILABLE:{label}") from exc
    try:
        stat_result = path.stat()
    except FileNotFoundError:
        stat_result = None
    except OSError as exc:
        raise ExternalChapterRouteError(f"FILE_IDENTITY_UNAVAILABLE:{label}") from exc
    return resolved, stat_result


def _same_file_identity(left: Path, right: Path) -> bool:
    left_resolved, left_stat = _file_identity(left, label="INPUT")
    right_resolved, right_stat = _file_identity(right, label="OUTPUT")
    return left_resolved == right_resolved or (
        left_stat is not None
        and right_stat is not None
        and os.path.samestat(left_stat, right_stat)
    )


def _validate_adapter_paths(input_path: str | None, output_path: str | None) -> None:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return
    if _same_file_identity(Path(input_path), Path(output_path)):
        raise ExternalChapterRouteError("INPUT_OUTPUT_PATH_MUST_DIFFER")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验当前外来章节并签发 M2 路由回执")
    parser.add_argument("--input", help="输入 JSON 文件；省略或 - 表示 stdin")
    parser.add_argument("--output", help="输出 JSON 文件；省略或 - 表示 stdout")
    args = parser.parse_args(argv)

    try:
        _validate_adapter_paths(args.input, args.output)
        result = execute(_load_request(args.input))
        if args.output in {None, "-"}:
            sys.stdout.buffer.write(_json_output_bytes(result))
            sys.stdout.buffer.flush()
        else:
            _write_json_atomic(Path(args.output), result)
    except (OSError, ExternalChapterRouteError) as exc:
        print(f"EXTERNAL_CHAPTER_ROUTE_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

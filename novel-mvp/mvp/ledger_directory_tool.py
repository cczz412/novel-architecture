"""十本固定账的独立目录原型与 LOCAL_FILESYSTEM_ONLY 运输层。"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


PROTOTYPE_IDENTITY = "AUTHOR_LEDGER_DIRECTORY_PROTOTYPE_R01"
ROUTING_ADVISORY_ONLY = True
TRANSPORT_SCOPE = "LOCAL_FILESYSTEM_ONLY"

FIXED_LEDGER_NAMES = (
    "章节账",
    "事实账",
    "人物账",
    "地点账",
    "物品账",
    "势力账",
    "体系账",
    "世界规则账",
    "长线账",
    "规划账",
)

CAPABILITY_STATUSES = frozenset(
    {
        "REUSABLE_STORAGE_AVAILABLE",
        "SCATTERED_MATERIALS_ONLY",
        "NO_FIXED_REGISTRATION",
    }
)
CONTENT_STATUSES = frozenset({"PRESENT", "EMPTY", "UNKNOWN"})

REQUEST_KEYS = frozenset({"capability_snapshot_id", "ledgers"})
LEDGER_KEYS = frozenset(
    {
        "ledger_name",
        "capability_status",
        "content_status",
        "read_route_advisory",
        "write_route_advisory",
    }
)


class LedgerDirectoryError(ValueError):
    """目录输入或本地运输不满足安全边界。"""


def _fail(code: str) -> None:
    raise LedgerDirectoryError(code)


def _exact_keys(value: dict[str, Any], expected: frozenset[str], *, label: str) -> None:
    missing = sorted(expected - value.keys())
    extra = sorted(value.keys() - expected)
    if missing:
        _fail(f"{label}_MISSING_FIELDS:{','.join(missing)}")
    if extra:
        _fail(f"{label}_EXTRA_FIELDS:{','.join(extra)}")


def _nonempty_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        _fail(f"{label}_MUST_BE_NONEMPTY_STRING")
    return value


def _route_advisory(value: object, *, label: str) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, label=label)


def _validated_request(request: object) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(request, dict):
        _fail("REQUEST_NOT_OBJECT")
    _exact_keys(request, REQUEST_KEYS, label="REQUEST")

    snapshot_id = _nonempty_string(
        request["capability_snapshot_id"],
        label="CAPABILITY_SNAPSHOT_ID",
    )
    raw_ledgers = request["ledgers"]
    if not isinstance(raw_ledgers, list):
        _fail("LEDGERS_NOT_LIST")
    if len(raw_ledgers) != len(FIXED_LEDGER_NAMES):
        _fail(f"LEDGER_COUNT_INVALID:{len(raw_ledgers)}")

    ledgers_by_name: dict[str, dict[str, Any]] = {}
    for index, raw_ledger in enumerate(raw_ledgers, start=1):
        if not isinstance(raw_ledger, dict):
            _fail(f"LEDGER_NOT_OBJECT:{index}")
        _exact_keys(raw_ledger, LEDGER_KEYS, label=f"LEDGER_{index}")
        name = _nonempty_string(raw_ledger["ledger_name"], label=f"LEDGER_NAME_{index}")
        if name not in FIXED_LEDGER_NAMES:
            _fail(f"LEDGER_NAME_UNKNOWN:{name}")
        if name in ledgers_by_name:
            _fail(f"LEDGER_NAME_DUPLICATE:{name}")

        capability_status = raw_ledger["capability_status"]
        if (
            not isinstance(capability_status, str)
            or capability_status not in CAPABILITY_STATUSES
        ):
            _fail(f"CAPABILITY_STATUS_INVALID:{name}")
        content_status = raw_ledger["content_status"]
        if not isinstance(content_status, str) or content_status not in CONTENT_STATUSES:
            _fail(f"CONTENT_STATUS_INVALID:{name}")

        ledgers_by_name[name] = {
            "ledger_name": name,
            "capability_status": capability_status,
            "content_status": content_status,
            "read_route_advisory": _route_advisory(
                raw_ledger["read_route_advisory"],
                label=f"READ_ROUTE_ADVISORY_{index}",
            ),
            "write_route_advisory": _route_advisory(
                raw_ledger["write_route_advisory"],
                label=f"WRITE_ROUTE_ADVISORY_{index}",
            ),
        }

    missing_names = [name for name in FIXED_LEDGER_NAMES if name not in ledgers_by_name]
    if missing_names:
        _fail(f"LEDGER_NAMES_MISSING:{','.join(missing_names)}")
    return snapshot_id, [ledgers_by_name[name] for name in FIXED_LEDGER_NAMES]


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """校验调用方快照并按固定十账顺序返回目录，不访问工作区。"""
    snapshot_id, ledgers = _validated_request(request)
    return {
        "identity": PROTOTYPE_IDENTITY,
        "routing_advisory_only": ROUTING_ADVISORY_ONLY,
        "capability_snapshot_id": snapshot_id,
        "ledger_count": len(FIXED_LEDGER_NAMES),
        "ledgers": copy.deepcopy(ledgers),
    }


def query_ledger(request: dict[str, Any], ledger_name: str) -> dict[str, Any]:
    """精确查询单项；未知名称返回不存在，不做近似匹配。"""
    directory = execute(request)
    name = _nonempty_string(ledger_name, label="QUERY_LEDGER_NAME")
    ledger = next(
        (item for item in directory["ledgers"] if item["ledger_name"] == name),
        None,
    )
    return {
        "identity": PROTOTYPE_IDENTITY,
        "routing_advisory_only": ROUTING_ADVISORY_ONLY,
        "capability_snapshot_id": directory["capability_snapshot_id"],
        "query": {"ledger_name": name, "found": ledger is not None},
        "ledger": copy.deepcopy(ledger),
    }


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


# LOCAL_FILESYSTEM_ONLY: 路径只存在于 CLI 适配层；纯对象入口不接路径。
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
        raise LedgerDirectoryError("INPUT_JSON_INVALID") from exc
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
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="十本固定账的本地目录原型")
    parser.add_argument("--input", default="-", help="输入 JSON；默认从 stdin 读取")
    parser.add_argument("--output", default="-", help="输出 JSON；默认写到 stdout")
    parser.add_argument("--ledger-name", help="精确查询一本账；省略时输出完整目录")
    args = parser.parse_args(argv)
    try:
        if _same_input_output_path(args.input, args.output):
            _fail("OUTPUT_MUST_NOT_OVERWRITE_INPUT")
        request = _load_request(args.input)
        if args.ledger_name is None:
            result = execute(request)
        else:
            result = query_ledger(request, args.ledger_name)
        _write_atomic(args.output, result)
    except (OSError, LedgerDirectoryError) as exc:
        print(f"LEDGER_DIRECTORY_ERROR:{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

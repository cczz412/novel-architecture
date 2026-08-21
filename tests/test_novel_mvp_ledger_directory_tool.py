from __future__ import annotations

import copy
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_PATH = PRODUCT_ROOT / "mvp" / "ledger_directory_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import ledger_directory_tool
finally:
    sys.path.pop(0)


FIXED_NAMES = list(ledger_directory_tool.FIXED_LEDGER_NAMES)


def _request() -> dict:
    reusable = {"章节账", "事实账", "规划账"}
    scattered = {"人物账", "地点账", "世界规则账", "长线账"}
    ledgers = []
    for name in reversed(FIXED_NAMES):
        if name in reusable:
            capability = "REUSABLE_STORAGE_AVAILABLE"
            read_route = f"当前{name}读取切片"
            write_route = f"当前{name}保存切片"
        elif name in scattered:
            capability = "SCATTERED_MATERIALS_ONLY"
            read_route = f"现有材料中的{name}线索"
            write_route = None
        else:
            capability = "NO_FIXED_REGISTRATION"
            read_route = None
            write_route = None
        ledgers.append(
            {
                "ledger_name": name,
                "capability_status": capability,
                "content_status": "EMPTY" if name == "物品账" else "UNKNOWN",
                "read_route_advisory": read_route,
                "write_route_advisory": write_route,
            }
        )
    return {
        "capability_snapshot_id": "snapshot-20260820-r01",
        "ledgers": ledgers,
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


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env=env,
    )


def test_execute_returns_fixed_directory_without_mutating_request() -> None:
    request = _request()
    before = copy.deepcopy(request)

    result = ledger_directory_tool.execute(request)

    assert request == before
    assert result == {
        "identity": "AUTHOR_LEDGER_DIRECTORY_PROTOTYPE_R01",
        "routing_advisory_only": True,
        "capability_snapshot_id": "snapshot-20260820-r01",
        "ledger_count": 10,
        "ledgers": [
            next(item for item in before["ledgers"] if item["ledger_name"] == name)
            for name in FIXED_NAMES
        ],
    }
    assert result["ledgers"][4]["content_status"] == "EMPTY"


def test_query_is_exact_and_unknown_name_returns_not_found() -> None:
    request = _request()

    found = ledger_directory_tool.query_ledger(request, "事实账")
    missing = ledger_directory_tool.query_ledger(request, "事实")

    assert found["query"] == {"ledger_name": "事实账", "found": True}
    assert found["ledger"]["ledger_name"] == "事实账"
    assert missing == {
        "identity": "AUTHOR_LEDGER_DIRECTORY_PROTOTYPE_R01",
        "routing_advisory_only": True,
        "capability_snapshot_id": "snapshot-20260820-r01",
        "query": {"ledger_name": "事实", "found": False},
        "ledger": None,
    }


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda value: value["ledgers"].pop(),
            "LEDGER_COUNT_INVALID:9",
        ),
        (
            lambda value: value["ledgers"].append(copy.deepcopy(value["ledgers"][0])),
            "LEDGER_COUNT_INVALID:11",
        ),
        (
            lambda value: value["ledgers"].__setitem__(
                1, copy.deepcopy(value["ledgers"][0])
            ),
            "LEDGER_NAME_DUPLICATE:规划账",
        ),
        (
            lambda value: value["ledgers"][0].__setitem__("ledger_name", "剧情账"),
            "LEDGER_NAME_UNKNOWN:剧情账",
        ),
        (
            lambda value: value["ledgers"][0].__setitem__(
                "capability_status", "READY"
            ),
            "CAPABILITY_STATUS_INVALID:规划账",
        ),
        (
            lambda value: value["ledgers"][0].__setitem__(
                "content_status", "MISSING"
            ),
            "CONTENT_STATUS_INVALID:规划账",
        ),
        (
            lambda value: value["ledgers"][0].__setitem__("extra", True),
            "LEDGER_1_EXTRA_FIELDS:extra",
        ),
    ],
)
def test_invalid_directory_is_rejected_as_one_batch(mutate, error: str) -> None:
    request = _request()
    mutate(request)

    with pytest.raises(ledger_directory_tool.LedgerDirectoryError, match=f"^{error}$"):
        ledger_directory_tool.execute(request)


def test_pure_object_execution_creates_no_ledgers_or_workspace_files(tmp_path: Path) -> None:
    source = TOOL_PATH.read_text(encoding="utf-8")
    before = list(tmp_path.iterdir())

    result = ledger_directory_tool.execute(_request())

    assert result["ledger_count"] == 10
    assert list(tmp_path.iterdir()) == before
    assert set(inspect.signature(ledger_directory_tool.execute).parameters) == {"request"}
    assert "AuthorWorkspace" not in source
    assert "import workspace" not in source


def test_cli_stdin_stdout_is_canonical_and_queries_single_ledger() -> None:
    request = _request()
    expected = ledger_directory_tool.execute(request)

    completed = _run_cli(stdin=_canonical_bytes(request))
    query = _run_cli(
        "--ledger-name",
        "长线账",
        stdin=_canonical_bytes(request),
    )

    assert completed.returncode == 0, completed.stderr.decode()
    assert completed.stdout == _canonical_bytes(expected)
    assert query.returncode == 0, query.stderr.decode()
    assert json.loads(query.stdout)["ledger"]["ledger_name"] == "长线账"


def test_cli_file_roundtrip_is_stable_and_creates_only_one_output(tmp_path: Path) -> None:
    input_path = tmp_path / "snapshot.json"
    output_one = tmp_path / "directory-one.json"
    output_two = tmp_path / "directory-two.json"
    input_path.write_bytes(_canonical_bytes(_request()))

    first = _run_cli("--input", str(input_path), "--output", str(output_one))
    second = _run_cli("--input", str(input_path), "--output", str(output_two))

    assert first.returncode == second.returncode == 0
    assert output_one.read_bytes() == output_two.read_bytes()
    assert set(path.name for path in tmp_path.iterdir()) == {
        "snapshot.json",
        "directory-one.json",
        "directory-two.json",
    }
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("alias_kind", ["same", "relative", "symlink", "hardlink"])
def test_cli_rejects_input_output_alias_without_changing_source(
    tmp_path: Path,
    alias_kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "snapshot.json"
    original = _canonical_bytes(_request())
    input_path.write_bytes(original)
    if alias_kind == "same":
        output_arg = str(input_path)
    elif alias_kind == "relative":
        monkeypatch.chdir(tmp_path)
        output_arg = "snapshot.json"
    elif alias_kind == "symlink":
        symlink = tmp_path / "directory.json"
        symlink.symlink_to(input_path)
        output_arg = str(symlink)
    else:
        hardlink = tmp_path / "directory.json"
        os.link(input_path, hardlink)
        output_arg = str(hardlink)

    completed = _run_cli(
        "--input",
        str(input_path),
        "--output",
        output_arg,
    )

    assert completed.returncode == 1
    assert b"OUTPUT_MUST_NOT_OVERWRITE_INPUT" in completed.stderr
    assert input_path.read_bytes() == original
    assert not list(tmp_path.glob(".*.tmp"))


def test_invalid_input_preserves_old_output_and_leaves_no_temp(tmp_path: Path) -> None:
    input_path = tmp_path / "bad.json"
    output_path = tmp_path / "directory.json"
    request = _request()
    request["ledgers"][0]["content_status"] = "BROKEN"
    input_path.write_bytes(_canonical_bytes(request))
    output_path.write_bytes(b"old-output\n")

    completed = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    )

    assert completed.returncode == 1
    assert output_path.read_bytes() == b"old-output\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_replace_failure_preserves_old_output_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "directory.json"
    output_path.write_bytes(b"old-output\n")

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(ledger_directory_tool.os, "replace", fail_replace)

    with pytest.raises(OSError, match="synthetic replace failure"):
        ledger_directory_tool._write_atomic(
            str(output_path),
            ledger_directory_tool.execute(_request()),
        )

    assert output_path.read_bytes() == b"old-output\n"
    assert not list(tmp_path.glob(".*.tmp"))

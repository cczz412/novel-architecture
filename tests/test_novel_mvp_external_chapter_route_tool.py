from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
NOVEL_MVP = ROOT / "novel-mvp"
TOOL_PATH = NOVEL_MVP / "mvp" / "external_chapter_route_tool.py"
if str(NOVEL_MVP) not in sys.path:
    sys.path.insert(0, str(NOVEL_MVP))

from contracts import validate_c11_chapter_revision_ledger as c11_contract  # noqa: E402
from mvp import external_chapter_route_tool as route_tool  # noqa: E402


TEXT = "甲拿起钥匙。乙离开。"


def _valid_request() -> dict:
    ledger = c11_contract.ledger_one(TEXT)
    return {
        "material_identity": c11_contract.c10_material_record(TEXT, "R1"),
        "chapter_revision_ledger": ledger,
        "chapter_doc": {
            "contract": "C1_CHAPTER_DOC",
            "version": "v1",
            "id": "c01",
            "title": "第一章",
            "kind": "draft",
            "text": TEXT,
            "added_at": "2026-08-20T12:00:00+08:00",
            "chapter_revision_ref": c11_contract.revision_ref("c01", 1, TEXT),
        },
    }


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )


def test_execute_accepts_closed_current_external_chapter_chain_without_mutation() -> None:
    request = _valid_request()
    before = copy.deepcopy(request)

    result = route_tool.execute(request)

    assert result == {
        "identity": "EXTERNAL_CHAPTER_ROUTE_RECEIPT_R01",
        "accepted": True,
        "source_kind": "EXTERNAL_CONFIRMED_CHAPTER",
        "chapter_id": "c01",
        "chapter_revision_ref": c11_contract.revision_ref("c01", 1, TEXT),
        "next_station": "M2_SEGMENT",
        "writes": [],
    }
    assert request == before
    assert _canonical(route_tool.execute(request)) == _canonical(result)


@pytest.mark.parametrize(
    ("role", "state"),
    [
        ("SETTING", "CONFIRMED"),
        ("TITLE", "CONFIRMED"),
        (None, "UNKNOWN"),
        ("INTRO", "CANDIDATE"),
    ],
)
def test_rejects_c10_non_confirmed_chapter_identities(role: str | None, state: str) -> None:
    request = _valid_request()
    request["material_identity"] = c11_contract.c10_material_record(
        TEXT,
        "R1",
        role=role,
        state=state,
    )

    with pytest.raises(route_tool.ExternalChapterRouteError, match="C10_NOT_CONFIRMED_CHAPTER"):
        route_tool.execute(request)


@pytest.mark.parametrize("field", ["lane", "next_station", "source_type", "is_external"])
def test_rejects_all_caller_reported_route_fields(field: str) -> None:
    request = _valid_request()
    request[field] = "caller-claim"

    with pytest.raises(route_tool.ExternalChapterRouteError, match="REQUEST_FIELDS_INVALID"):
        route_tool.execute(request)


def test_rejects_stale_c10_identity_revision() -> None:
    request = _valid_request()
    request["material_identity"] = c11_contract.c10_material_record(
        TEXT,
        "R1",
        identity_revision_no=2,
    )

    with pytest.raises(route_tool.ExternalChapterRouteError, match="C10_IDENTITY_REVISION_STALE"):
        route_tool.execute(request)


@pytest.mark.parametrize("field", ["source_id", "start", "slice_sha256"])
def test_rejects_c10_c11_source_span_drift(field: str) -> None:
    request = _valid_request()
    content_ref = request["chapter_revision_ledger"]["revisions"][0]["content_ref"]
    if field == "start":
        content_ref[field] = 1
    elif field == "slice_sha256":
        content_ref[field] = "0" * 64
    else:
        content_ref[field] = "SRC-OTHER"

    with pytest.raises(route_tool.ExternalChapterRouteError, match="C10_SOURCE_REF_MISMATCH"):
        route_tool.execute(request)


@pytest.mark.parametrize("damage", ["current_pointer", "revision_sequence", "material_origin"])
def test_rejects_damaged_c11_current_chain(damage: str) -> None:
    request = _valid_request()
    ledger = request["chapter_revision_ledger"]
    if damage == "current_pointer":
        ledger["current_revision_no"] = 2
    elif damage == "revision_sequence":
        second = copy.deepcopy(ledger["revisions"][0])
        second.update(
            {
                "revision_no": 3,
                "change_kind": "REPLACE",
                "commit_operation_id": "op-r3",
                "committed_at": "2026-08-20T12:03:00+08:00",
            }
        )
        ledger["revisions"].append(second)
        ledger["current_revision_no"] = 3
        ledger["last_operation_id"] = "op-r3"
    else:
        ledger["revisions"][0]["origin_material_ref"]["material_unit_id"] = "MU-OTHER"

    with pytest.raises(route_tool.ExternalChapterRouteError):
        route_tool.execute(request)


@pytest.mark.parametrize(
    ("damage", "expected_error"),
    [
        ("chapter_id", "C1_CHAPTER_ID_MISMATCH"),
        ("title", "C1_TITLE_MISMATCH"),
        ("text", "C1_TEXT_SHA256_MISMATCH"),
        ("revision_no", "C1_CURRENT_REVISION_REF_MISMATCH"),
        ("revision_sha", "C1_CURRENT_REVISION_REF_MISMATCH"),
        ("ledger_chars", "C1_CHAR_COUNT_MISMATCH"),
    ],
)
def test_rejects_c1_current_view_drift(damage: str, expected_error: str) -> None:
    request = _valid_request()
    chapter = request["chapter_doc"]
    if damage == "chapter_id":
        chapter["id"] = "c02"
        chapter["chapter_revision_ref"]["chapter_id"] = "c02"
    elif damage == "title":
        chapter["title"] = "另一章"
    elif damage == "text":
        chapter["text"] = "甲放下钥匙。乙离开。"
        chapter["chapter_revision_ref"]["revision_text_sha256"] = hashlib.sha256(
            chapter["text"].encode()
        ).hexdigest()
    elif damage == "revision_no":
        chapter["chapter_revision_ref"]["revision_no"] = 2
    elif damage == "revision_sha":
        chapter["chapter_revision_ref"]["revision_text_sha256"] = "0" * 64
    else:
        request["chapter_revision_ledger"]["revisions"][0]["chars"] += 1

    with pytest.raises(route_tool.ExternalChapterRouteError, match=expected_error):
        route_tool.execute(request)


@pytest.mark.parametrize(
    "impostor",
    [
        {"contract": "C1_CHAPTER_DOC", "version": "legacy", "id": "c01", "text": TEXT},
        {"contract": "WORK_DRAFT", "version": "v1", "text": TEXT},
        {"contract": "PLAN_LEDGER_STORAGE", "version": "plan-v2", "events": []},
        {"contract": "CHAPTER_FACT_DRAFT", "version": "v1", "facts": ["甲拿起钥匙。"]},
    ],
)
def test_rejects_old_c1_work_plan_and_fake_fact_draft(impostor: dict) -> None:
    request = _valid_request()
    request["chapter_doc"] = impostor

    with pytest.raises(route_tool.ExternalChapterRouteError, match="C1_CURRENT_VIEW_REQUIRED|C1_INVALID"):
        route_tool.execute(request)


def test_cli_stdin_stdout_and_file_output_are_byte_stable(tmp_path: Path) -> None:
    raw = _canonical(_valid_request())
    stdout_run = _run_cli(stdin=raw)
    assert stdout_run.returncode == 0, stdout_run.stderr.decode()
    assert json.loads(stdout_run.stdout)["next_station"] == "M2_SEGMENT"

    source = tmp_path / "input.json"
    output = tmp_path / "output.json"
    source.write_bytes(raw)
    first = _run_cli("--input", str(source), "--output", str(output))
    assert first.returncode == 0, first.stderr.decode()
    first_bytes = output.read_bytes()
    second = _run_cli("--input", str(source), "--output", str(output))
    assert second.returncode == 0, second.stderr.decode()
    assert output.read_bytes() == first_bytes == stdout_run.stdout


@pytest.mark.parametrize("alias_kind", ["same", "symlink", "hardlink"])
def test_cli_rejects_input_output_aliases(tmp_path: Path, alias_kind: str) -> None:
    source = tmp_path / "input.json"
    source.write_bytes(_canonical(_valid_request()))
    if alias_kind == "same":
        output = source
    elif alias_kind == "symlink":
        output = tmp_path / "output.json"
        output.symlink_to(source)
    else:
        output = tmp_path / "output.json"
        os.link(source, output)
    before = source.read_bytes()

    run = _run_cli("--input", str(source), "--output", str(output))

    assert run.returncode == 2
    assert b"INPUT_OUTPUT_PATH_MUST_DIFFER" in run.stderr
    assert source.read_bytes() == before


def test_cli_invalid_input_preserves_existing_output_and_leaves_no_temp(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    output = tmp_path / "output.json"
    source.write_text("{}", encoding="utf-8")
    output.write_bytes(b"keep-me")

    run = _run_cli("--input", str(source), "--output", str(output))

    assert run.returncode == 2
    assert output.read_bytes() == b"keep-me"
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_atomic_replace_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "output.json"
    output.write_bytes(b"keep-me")

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(route_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        route_tool._write_json_atomic(output, route_tool.execute(_valid_request()))
    assert output.read_bytes() == b"keep-me"
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_direct_module_import_and_script_import_share_contracts() -> None:
    imported = importlib.import_module("mvp.external_chapter_route_tool")
    assert imported.execute(_valid_request())["accepted"] is True

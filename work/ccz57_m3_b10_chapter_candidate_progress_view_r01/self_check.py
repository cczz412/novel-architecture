"""Offline B-10 construction and non-ownership probe."""

from __future__ import annotations

import ast
import json
import sqlite3
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B01_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b01_candidate_version_r03_5"
B05_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b05_patch_route_r03_5"
B06_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b06_commit_core_r01"
B07_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b07_local_recovery_stop_r01"
B08_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b08_segment_terminal_r01"
for candidate in (
    REPOSITORY_ROOT,
    MODULE_ROOT,
    B01_ROOT,
    B05_ROOT,
    B06_ROOT,
    B07_ROOT,
    B08_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    record_ref as b01_record_ref,
)
from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    canonical_bytes,
)
from work.ccz57_m3_b08_segment_terminal_r01.fixtures import (  # noqa: E402
    build_environment,
)

from b10_authority_reader import ChapterProgressAuthorityReader  # noqa: E402
from b10_contracts import PURPOSE  # noqa: E402
from current_chapter_progress_view import (  # noqa: E402
    project_author_progress,
    read_current_chapter_progress,
)


def _schema(path: Path) -> list[str]:
    with sqlite3.connect(path) as connection:
        return [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
        ]


def _immutable_reader(records: list[dict[str, Any]]) -> Any:
    indexed = {
        canonical_bytes(b01_record_ref(record)): deepcopy(record)
        for record in records
    }

    def read(ref: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(indexed[canonical_bytes(ref)])

    return read


def main() -> None:
    runtime_files = [
        MODULE_ROOT / "b10_contracts.py",
        MODULE_ROOT / "b10_authority_reader.py",
        MODULE_ROOT / "current_chapter_progress_view.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in runtime_files)
    trees = [ast.parse(path.read_text(encoding="utf-8")) for path in runtime_files]
    class_names = {
        node.name
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }
    with tempfile.TemporaryDirectory(prefix="ccz57-b10-self-check-") as raw_root:
        env = build_environment(Path(raw_root) / "upstream")
        b01 = env.b07.b06.b05.b01_reader.read_scope()
        segment_index = b01["segment_index_record"]
        request = {
            "project_scope_id": env.project_scope_id,
            "chapter_revision_ref": deepcopy(
                segment_index["payload"]["chapter_revision_ref"]
            ),
            "segment_index_ref": b01_record_ref(segment_index),
            "purpose": PURPOSE,
        }
        database_path = env.store._database_path
        before_schema = _schema(database_path)
        reader = ChapterProgressAuthorityReader(
            shared_database_path=database_path,
            current_segment_index_reader=lambda _request: deepcopy(segment_index),
            immutable_reader=_immutable_reader(b01["candidate_reference_records"]),
            b08_authority_reader=env.authority,
        )
        internal = read_current_chapter_progress(reader, request)
        author = project_author_progress(internal)
        after_schema = _schema(database_path)
    report = {
        "shape": "PURE_DERIVED_PROGRESS_VIEW",
        "b10_database_tables": sum("b10" in name.lower() for name in after_schema),
        "b10_record_classes": sum("Record" in name for name in class_names),
        "b10_writer_classes": sum("Writer" in name for name in class_names),
        "formal_causal_or_ledger_write": int(
            any(token in source for token in ("CREATE TABLE", "INSERT INTO", "UPDATE "))
        ),
        "model_call": int(any(token in source.lower() for token in ("openai", "anthropic"))),
        "network_call": int(
            any(token in source.lower() for token in ("requests", "urllib", "httpx"))
        ),
        "b09_b11_b12_dependency": int(
            any(token in source.lower() for token in ("ccz57_m3_b09", "ccz57_m3_b11", "ccz57_m3_b12"))
        ),
        "schema_unchanged": before_schema == after_schema,
        "availability": internal["availability"],
        "author_projection_fields": sorted(author),
    }
    checks = [
        report["b10_database_tables"] == 0,
        report["b10_record_classes"] == 0,
        report["b10_writer_classes"] == 0,
        report["formal_causal_or_ledger_write"] == 0,
        report["model_call"] == 0,
        report["network_call"] == 0,
        report["b09_b11_b12_dependency"] == 0,
        report["schema_unchanged"] is True,
        report["availability"] == "READY",
    ]
    report["status"] = "PASS" if all(checks) else "FAIL"
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

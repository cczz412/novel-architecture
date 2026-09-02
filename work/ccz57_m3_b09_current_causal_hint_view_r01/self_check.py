"""Static and deterministic checks for the pure B-09 derived view."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b09_contracts import build_error_view, validate_view  # noqa: E402

EXPECTED_FILES = {
    "README.md",
    "b09_contracts.py",
    "b09_authority_reader.py",
    "current_causal_hint_view.py",
    "test_current_causal_hint_view.py",
    "self_check.py",
}
IMPLEMENTATION_FILES = {
    "b09_contracts.py",
    "b09_authority_reader.py",
    "current_causal_hint_view.py",
}
FORBIDDEN_IMPORT_ROOTS = {
    "requests",
    "httpx",
    "urllib",
    "socket",
    "subprocess",
    "openai",
    "anthropic",
}
SQL_WRITE_MARKERS = {
    "CREATE TABLE",
    "ALTER TABLE",
    "DROP TABLE",
    "INSERT INTO",
    "UPDATE ",
    "DELETE FROM",
    "REPLACE INTO",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _imports_and_classes(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    return imports, classes


def run_self_check() -> dict[str, Any]:
    actual_files = {path.name for path in ROOT.iterdir() if path.is_file()}
    if actual_files != EXPECTED_FILES:
        raise RuntimeError(f"B09_FILE_SET_INVALID: {sorted(actual_files)}")

    implementation_hashes: dict[str, str] = {}
    for name in sorted(IMPLEMENTATION_FILES):
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        imports, classes = _imports_and_classes(path)
        if imports & FORBIDDEN_IMPORT_ROOTS:
            raise RuntimeError(f"B09_FORBIDDEN_IMPORT: {name}")
        if any(class_name.endswith(("Store", "Writer")) for class_name in classes):
            raise RuntimeError(f"B09_PERSISTENT_OWNER_FORBIDDEN: {name}")
        upper = source.upper()
        if any(marker in upper for marker in SQL_WRITE_MARKERS):
            raise RuntimeError(f"B09_SQL_WRITE_FORBIDDEN: {name}")
        implementation_hashes[name] = _sha(path)

    b10_edges = []
    for path in (REPOSITORY_ROOT / "work").glob("*b10*/*.py"):
        source = path.read_text(encoding="utf-8")
        if "ccz57_m3_b09" in source or "current_causal_hint" in source:
            b10_edges.append(path.relative_to(REPOSITORY_ROOT).as_posix())
    if b10_edges:
        raise RuntimeError(f"B09_B10_DEPENDENCY_FORBIDDEN: {b10_edges}")

    error_view = build_error_view("AUTHORITY_READER_UNAVAILABLE")
    validate_view(error_view)
    return {
        "document_identity": "CCZ57-M3-B09-CURRENT-CAUSAL-HINT-VIEW-R01",
        "shape": "PURE_DERIVED_VIEW",
        "view_type": error_view["view_type"],
        "deterministic_error_view_hash": error_view["view_hash"],
        "implementation_hashes": implementation_hashes,
        "b09_records": 0,
        "b09_writers": 0,
        "b09_database_tables": 0,
        "model_calls": 0,
        "network_calls": 0,
        "formal_causal_writes": 0,
        "b10_dependency_edges": 0,
        "status": "PASS",
    }


def main() -> None:
    print(json.dumps(run_self_check(), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

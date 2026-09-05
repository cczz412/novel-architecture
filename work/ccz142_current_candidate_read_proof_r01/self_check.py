"""Deterministic zero-API self-check for the A-track current read proof."""

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

from current_read_proof import (  # noqa: E402
    DOCUMENT_IDENTITY,
    GAP_NO_LIVE_STORE,
    GAP_REAL_NOVEL_NOT_IN_SCOPE,
    READ_PATH,
    prove_current_read,
)

EXPECTED_FILES = {
    "README.md",
    "SOURCE_INDEX.md",
    "OBJECT_SHAPES.json",
    "current_read_proof.py",
    "prove.py",
    "test_current_read_proof.py",
    "self_check.py",
    "MANIFEST.sha256",
    "TEST_RECEIPT_R01.json",
}
IMPLEMENTATION_FILES = {
    "current_read_proof.py",
    "prove.py",
}
FORBIDDEN_IMPORT_ROOTS = {
    "requests",
    "httpx",
    "urllib",
    "socket",
    "subprocess",
    "openai",
    "anthropic",
    "aiohttp",
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
FORBIDDEN_SOURCE_SNIPPETS = {
    "ccz142_product_candidate_authority_r01",
    "codex/issue-231-ccz142-product-candidate-authority-r01",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _imports_and_classes(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    return imports, classes


def run_self_check() -> dict[str, Any]:
    actual_files = {path.name for path in ROOT.iterdir() if path.is_file()}
    if actual_files != EXPECTED_FILES:
        raise RuntimeError(f"READ_PROOF_FILE_SET_INVALID: {sorted(actual_files)}")

    implementation_hashes: dict[str, str] = {}
    for name in sorted(IMPLEMENTATION_FILES):
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        imports, classes = _imports_and_classes(path)
        if imports & FORBIDDEN_IMPORT_ROOTS:
            raise RuntimeError(f"READ_PROOF_FORBIDDEN_IMPORT: {name}:{sorted(imports & FORBIDDEN_IMPORT_ROOTS)}")
        if any(class_name.endswith(("Store", "Writer")) for class_name in classes):
            raise RuntimeError(f"READ_PROOF_PERSISTENT_OWNER_FORBIDDEN: {name}")
        upper = source.upper()
        if any(marker in upper for marker in SQL_WRITE_MARKERS):
            raise RuntimeError(f"READ_PROOF_SQL_WRITE_FORBIDDEN: {name}")
        if "current_pointers" in source and "SELECT logical_pointer_key" not in source:
            raise RuntimeError(f"READ_PROOF_POINTER_TABLE_TOUCH_FORBIDDEN: {name}")
        for snippet in FORBIDDEN_SOURCE_SNIPPETS:
            if snippet in source:
                raise RuntimeError(f"READ_PROOF_FORBIDDEN_SNIPPET:{name}:{snippet}")
        implementation_hashes[name] = _sha(path)

    first = prove_current_read()
    second = prove_current_read()
    if first != second:
        raise RuntimeError("READ_PROOF_NO_STORE_REPLAY_DRIFT")
    if first["gaps"] != [GAP_NO_LIVE_STORE]:
        raise RuntimeError("READ_PROOF_NO_LIVE_STORE_DRIFT")
    if first["identity"]["product_adopted"] is not False:
        raise RuntimeError("READ_PROOF_PRODUCT_ADOPTION_CLAIM")
    if GAP_REAL_NOVEL_NOT_IN_SCOPE not in first["standing_boundaries"]:
        raise RuntimeError("READ_PROOF_REAL_NOVEL_BOUNDARY_MISSING")
    if "CandidateAuthorityStore" not in first["read_path"]["store_class"]:
        raise RuntimeError("READ_PROOF_READ_PATH_DRIFT")

    shapes = json.loads((ROOT / "OBJECT_SHAPES.json").read_text(encoding="utf-8"))
    if shapes["read_path"]["store_class"] != READ_PATH["store_class"]:
        raise RuntimeError("READ_PROOF_OBJECT_SHAPE_DRIFT")
    if shapes["product_adopted"] is not False:
        raise RuntimeError("READ_PROOF_OBJECT_SHAPE_PRODUCT_CLAIM")

    return {
        "document_identity": DOCUMENT_IDENTITY,
        "result": "PASS",
        "base_main_sha": first["base_main_sha"],
        "github_issue": 264,
        "identity_never_product_adopted": True,
        "no_live_store_gap": first["gaps"][0],
        "implementation_sha256": implementation_hashes,
        "repeatability": {"independent_runs": 2, "exact_result_match": True},
        "zero_api": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

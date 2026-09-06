"""Deterministic zero-API self-check for named identity store sidecar."""

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

from store_identity import (  # noqa: E402
    DOCUMENT_IDENTITY,
    GITHUB_ISSUE,
    drop_named_chapter_to_store,
)

EXPECTED_FILES = {
    "README.md",
    "SOURCE_INDEX.md",
    "OBJECT_SHAPES.json",
    "store_identity.py",
    "drop.py",
    "test_named_identity_store.py",
    "self_check.py",
    "MANIFEST.sha256",
    "TEST_RECEIPT_R01.json",
}
IMPLEMENTATION_FILES = {
    "store_identity.py",
    "drop.py",
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
FORBIDDEN_SOURCE_SNIPPETS = {
    "ccz142_product_candidate_authority_r01",
    "codex/issue-231-ccz142-product-candidate-authority-r01",
    "initialize_root_baseline",
    "写法指导",
}
FORBIDDEN_CLASSES_SUFFIX = ("Store", "Writer")


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
        raise RuntimeError(f"STORE_IDENTITY_FILE_SET_INVALID: {sorted(actual_files)}")

    implementation_hashes: dict[str, str] = {}
    for name in sorted(IMPLEMENTATION_FILES):
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        imports, classes = _imports_and_classes(path)
        if imports & FORBIDDEN_IMPORT_ROOTS:
            raise RuntimeError(
                "STORE_IDENTITY_FORBIDDEN_IMPORT: "
                f"{name}:{sorted(imports & FORBIDDEN_IMPORT_ROOTS)}"
            )
        if any(class_name.endswith(FORBIDDEN_CLASSES_SUFFIX) for class_name in classes):
            raise RuntimeError(f"STORE_IDENTITY_PERSISTENT_OWNER_FORBIDDEN: {name}")
        for snippet in FORBIDDEN_SOURCE_SNIPPETS:
            if snippet in source:
                raise RuntimeError(f"STORE_IDENTITY_FORBIDDEN_SNIPPET:{name}:{snippet}")
        if "B-09" in source or "b09" in source:
            raise RuntimeError(f"STORE_IDENTITY_B09_LEAK:{name}")
        implementation_hashes[name] = _sha(path)

    closed = drop_named_chapter_to_store(
        book="全职高手",
        chapter_no=1,
        store_root=ROOT / "_must_not_exist_store",
    )
    if closed["sidecar_wrote"] is not False:
        raise RuntimeError("STORE_IDENTITY_UNRELEASED_WROTE_SIDECAR")
    if closed["proof"]["identity"]["product_adopted"] is not False:
        raise RuntimeError("STORE_IDENTITY_PRODUCT_ADOPTION_CLAIM")

    shapes = json.loads((ROOT / "OBJECT_SHAPES.json").read_text(encoding="utf-8"))
    if shapes["product_adopted"] is not False:
        raise RuntimeError("STORE_IDENTITY_OBJECT_SHAPE_PRODUCT_CLAIM")
    if shapes["sqlite_schema_changed"] is not False:
        raise RuntimeError("STORE_IDENTITY_SCHEMA_CLAIM")
    if shapes["coverage_wired"] is not False:
        raise RuntimeError("STORE_IDENTITY_COVERAGE_CLAIM")

    return {
        "document_identity": DOCUMENT_IDENTITY,
        "result": "PASS",
        "base_main_sha": closed["base_main_sha"],
        "github_issue": GITHUB_ISSUE,
        "identity_never_product_adopted": True,
        "implementation_sha256": implementation_hashes,
        "zero_api": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

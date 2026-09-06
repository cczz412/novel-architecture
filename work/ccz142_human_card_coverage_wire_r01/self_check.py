"""Deterministic zero-API self-check for human-card coverage count wire."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[1]
PROOF_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01"
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
if str(PROOF_ROOT) not in sys.path:
    sys.path.insert(0, str(PROOF_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from current_read_proof import GAP_NO_LIVE_STORE, prove_current_read  # noqa: E402
from coverage_wire import DOCUMENT_IDENTITY, GITHUB_ISSUE  # noqa: E402

EXPECTED_FILES = {
    "README.md",
    "SOURCE_INDEX.md",
    "OBJECT_SHAPES.json",
    "coverage_wire.py",
    "drop.py",
    "test_human_card_coverage_wire.py",
    "self_check.py",
    "MANIFEST.sha256",
    "TEST_RECEIPT_R01.json",
}
IMPLEMENTATION_FILES = {
    "coverage_wire.py",
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
    classes = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }
    return imports, classes


def run_self_check() -> dict[str, Any]:
    actual_files = {path.name for path in ROOT.iterdir() if path.is_file()}
    if actual_files != EXPECTED_FILES:
        raise RuntimeError(f"COVERAGE_WIRE_FILE_SET_INVALID: {sorted(actual_files)}")

    implementation_hashes: dict[str, str] = {}
    for name in sorted(IMPLEMENTATION_FILES):
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        imports, classes = _imports_and_classes(path)
        if imports & FORBIDDEN_IMPORT_ROOTS:
            raise RuntimeError(
                "COVERAGE_WIRE_FORBIDDEN_IMPORT: "
                f"{name}:{sorted(imports & FORBIDDEN_IMPORT_ROOTS)}"
            )
        if any(class_name.endswith(FORBIDDEN_CLASSES_SUFFIX) for class_name in classes):
            raise RuntimeError(f"COVERAGE_WIRE_PERSISTENT_OWNER_FORBIDDEN: {name}")
        for snippet in FORBIDDEN_SOURCE_SNIPPETS:
            if snippet in source:
                raise RuntimeError(f"COVERAGE_WIRE_FORBIDDEN_SNIPPET:{name}:{snippet}")
        if "B-09" in source or "b09" in source:
            raise RuntimeError(f"COVERAGE_WIRE_B09_LEAK:{name}")
        implementation_hashes[name] = _sha(path)

    proof = prove_current_read()
    if proof["gaps"] != [GAP_NO_LIVE_STORE]:
        raise RuntimeError("COVERAGE_WIRE_NO_LIVE_STORE_DRIFT")
    if proof["coverage_view"]["wired"] is not False:
        raise RuntimeError("COVERAGE_WIRE_EMPTY_VIEW_CLAIM")
    if proof["result_scope"]["density"] != "尚未提供，不编数字":
        raise RuntimeError("COVERAGE_WIRE_EMPTY_DENSITY_CLAIM")
    if proof["identity"]["product_adopted"] is not False:
        raise RuntimeError("COVERAGE_WIRE_PRODUCT_ADOPTION_CLAIM")

    shapes = json.loads((ROOT / "OBJECT_SHAPES.json").read_text(encoding="utf-8"))
    if shapes["product_adopted"] is not False:
        raise RuntimeError("COVERAGE_WIRE_OBJECT_SHAPE_PRODUCT_CLAIM")
    if shapes["b02_originals_wired"] is not False:
        raise RuntimeError("COVERAGE_WIRE_B02_ORIGINALS_CLAIM")
    if shapes["invented_coverage_percent"] is not False:
        raise RuntimeError("COVERAGE_WIRE_PERCENT_CLAIM")
    if shapes["count_distribution_wired"] is not True:
        raise RuntimeError("COVERAGE_WIRE_COUNT_FLAG")

    return {
        "document_identity": DOCUMENT_IDENTITY,
        "result": "PASS",
        "base_main_sha": "ef1d3ad96867539faa8105f57be81b16401aae1b",
        "github_issue": GITHUB_ISSUE,
        "identity_never_product_adopted": True,
        "implementation_sha256": implementation_hashes,
        "zero_api": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

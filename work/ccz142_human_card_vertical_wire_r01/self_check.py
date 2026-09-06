"""Deterministic zero-API self-check for the human-card vertical wire."""

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

from vertical_wire import (  # noqa: E402
    DOCUMENT_IDENTITY,
    GITHUB_ISSUE,
    SYNTHETIC_CHAPTER,
    extract_handoff_items,
    load_synthetic_chapter,
    wire_synthetic_chapter_to_card,
)

EXPECTED_FILES = {
    "README.md",
    "SOURCE_INDEX.md",
    "OBJECT_SHAPES.json",
    "vertical_wire.py",
    "wire.py",
    "test_human_card_vertical_wire.py",
    "self_check.py",
    "synthetic_chapter.txt",
    "MANIFEST.sha256",
    "TEST_RECEIPT_R01.json",
}
IMPLEMENTATION_FILES = {
    "vertical_wire.py",
    "wire.py",
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
        raise RuntimeError(f"VERTICAL_WIRE_FILE_SET_INVALID: {sorted(actual_files)}")

    if load_synthetic_chapter() != SYNTHETIC_CHAPTER:
        raise RuntimeError("VERTICAL_WIRE_CHAPTER_DRIFT")
    items = extract_handoff_items(SYNTHETIC_CHAPTER)
    if items is None:
        raise RuntimeError("VERTICAL_WIRE_EXTRACTOR_REJECTED_FROZEN_CHAPTER")
    statuses = {item["status"] for item in items}
    if not {"推测", "误信", "计划"} <= statuses:
        raise RuntimeError("VERTICAL_WIRE_TYPES_MISSING")

    implementation_hashes: dict[str, str] = {}
    for name in sorted(IMPLEMENTATION_FILES):
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        imports, classes = _imports_and_classes(path)
        if imports & FORBIDDEN_IMPORT_ROOTS:
            raise RuntimeError(
                "VERTICAL_WIRE_FORBIDDEN_IMPORT: "
                f"{name}:{sorted(imports & FORBIDDEN_IMPORT_ROOTS)}"
            )
        if any(class_name.endswith(FORBIDDEN_CLASSES_SUFFIX) for class_name in classes):
            raise RuntimeError(f"VERTICAL_WIRE_PERSISTENT_OWNER_FORBIDDEN: {name}")
        for snippet in FORBIDDEN_SOURCE_SNIPPETS:
            if snippet in source:
                raise RuntimeError(f"VERTICAL_WIRE_FORBIDDEN_SNIPPET:{name}:{snippet}")
        if "B-09" in source or "b09" in source:
            raise RuntimeError(f"VERTICAL_WIRE_B09_LEAK:{name}")
        implementation_hashes[name] = _sha(path)

    closed = wire_synthetic_chapter_to_card(chapter_text="不是这条合成章")
    if closed["wrote"] is not False or closed["gaps"] != ["GAP_CHAPTER_MISMATCH"]:
        raise RuntimeError("VERTICAL_WIRE_MISMATCH_MUST_NOT_WRITE")
    if closed["proof"]["identity"]["product_adopted"] is not False:
        raise RuntimeError("VERTICAL_WIRE_PRODUCT_ADOPTION_CLAIM")
    if "写法指导" in closed["html"]:
        raise RuntimeError("VERTICAL_WIRE_WRITING_ADVICE_LEAK")

    shapes = json.loads((ROOT / "OBJECT_SHAPES.json").read_text(encoding="utf-8"))
    if shapes["product_adopted"] is not False:
        raise RuntimeError("VERTICAL_WIRE_OBJECT_SHAPE_PRODUCT_CLAIM")
    if shapes["writes_via"] != "CandidateRootInitializer.initialize_root":
        raise RuntimeError("VERTICAL_WIRE_WRITE_PATH_DRIFT")
    if shapes["html_via"] != "show_current_html":
        raise RuntimeError("VERTICAL_WIRE_HTML_PATH_DRIFT")
    if shapes["coverage_wired"] is not False:
        raise RuntimeError("VERTICAL_WIRE_COVERAGE_CLAIM")

    return {
        "document_identity": DOCUMENT_IDENTITY,
        "result": "PASS",
        "base_main_sha": closed["base_main_sha"],
        "github_issue": GITHUB_ISSUE,
        "identity_never_product_adopted": True,
        "implementation_sha256": implementation_hashes,
        "repeatability": {"independent_runs": 1, "mismatch_closed": True},
        "zero_api": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

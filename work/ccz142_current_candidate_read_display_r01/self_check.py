"""Deterministic zero-API self-check for the A-track current display."""

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

from card_render import DOCUMENT_IDENTITY, show_current_card  # noqa: E402

EXPECTED_FILES = {
    "README.md",
    "SOURCE_INDEX.md",
    "OBJECT_SHAPES.json",
    "card_render.py",
    "show.py",
    "test_current_read_display.py",
    "self_check.py",
    "MANIFEST.sha256",
    "TEST_RECEIPT_R01.json",
}
EXPECTED_SAMPLES = {
    "no_live_store.md",
    "fixture_layout.md",
}
IMPLEMENTATION_FILES = {
    "card_render.py",
    "show.py",
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
        raise RuntimeError(f"READ_DISPLAY_FILE_SET_INVALID: {sorted(actual_files)}")
    sample_dir = ROOT / "samples"
    actual_samples = {path.name for path in sample_dir.iterdir() if path.is_file()}
    if actual_samples != EXPECTED_SAMPLES:
        raise RuntimeError(f"READ_DISPLAY_SAMPLE_SET_INVALID: {sorted(actual_samples)}")

    implementation_hashes: dict[str, str] = {}
    for name in sorted(IMPLEMENTATION_FILES):
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        imports, classes = _imports_and_classes(path)
        if imports & FORBIDDEN_IMPORT_ROOTS:
            raise RuntimeError(
                f"READ_DISPLAY_FORBIDDEN_IMPORT: {name}:{sorted(imports & FORBIDDEN_IMPORT_ROOTS)}"
            )
        if any(class_name.endswith(("Store", "Writer")) for class_name in classes):
            raise RuntimeError(f"READ_DISPLAY_PERSISTENT_OWNER_FORBIDDEN: {name}")
        upper = source.upper()
        if any(marker in upper for marker in SQL_WRITE_MARKERS):
            raise RuntimeError(f"READ_DISPLAY_SQL_WRITE_FORBIDDEN: {name}")
        for snippet in FORBIDDEN_SOURCE_SNIPPETS:
            if snippet in source:
                raise RuntimeError(f"READ_DISPLAY_FORBIDDEN_SNIPPET:{name}:{snippet}")
        implementation_hashes[name] = _sha(path)

    first = show_current_card()
    second = show_current_card()
    if first != second:
        raise RuntimeError("READ_DISPLAY_NO_STORE_REPLAY_DRIFT")
    if first["proof"]["gaps"] != ["GAP_NO_LIVE_STORE"]:
        raise RuntimeError("READ_DISPLAY_NO_LIVE_STORE_DRIFT")
    if first["proof"]["identity"]["product_adopted"] is not False:
        raise RuntimeError("READ_DISPLAY_PRODUCT_ADOPTION_CLAIM")
    frozen = (sample_dir / "no_live_store.md").read_text(encoding="utf-8")
    if frozen != first["markdown"]:
        raise RuntimeError("READ_DISPLAY_FROZEN_GAP_PAGE_DRIFT")
    layout = (sample_dir / "fixture_layout.md").read_text(encoding="utf-8")
    if "样张" not in layout or "不是活库读出" not in layout:
        raise RuntimeError("READ_DISPLAY_LAYOUT_SAMPLE_UNLABELLED")
    if "## 写法指导" in first["markdown"] or "## 写法指导" in layout:
        raise RuntimeError("READ_DISPLAY_WRITING_ADVICE_LEAK")

    shapes = json.loads((ROOT / "OBJECT_SHAPES.json").read_text(encoding="utf-8"))
    if shapes["product_adopted"] is not False:
        raise RuntimeError("READ_DISPLAY_OBJECT_SHAPE_PRODUCT_CLAIM")
    if shapes["reads_via"] != "prove_current_read":
        raise RuntimeError("READ_DISPLAY_READ_PATH_DRIFT")

    return {
        "document_identity": DOCUMENT_IDENTITY,
        "result": "PASS",
        "base_main_sha": first["proof"]["base_main_sha"],
        "github_issue": 266,
        "identity_never_product_adopted": True,
        "implementation_sha256": implementation_hashes,
        "repeatability": {"independent_runs": 2, "exact_result_match": True},
        "zero_api": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

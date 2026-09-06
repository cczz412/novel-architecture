"""Deterministic zero-API self-check for named chapter TXT drop."""

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

from named_chapter import (  # noqa: E402
    DOCUMENT_IDENTITY,
    GITHUB_ISSUE,
    chapter_text_sha256,
    drop_named_chapter,
    load_allowlist,
)

EXPECTED_FILES = {
    "README.md",
    "SOURCE_INDEX.md",
    "OBJECT_SHAPES.json",
    "ALLOWLIST.json",
    "named_chapter.py",
    "drop.py",
    "test_named_chapter_txt_card.py",
    "self_check.py",
    "MANIFEST.sha256",
    "TEST_RECEIPT_R01.json",
}
IMPLEMENTATION_FILES = {
    "named_chapter.py",
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
GOLD_TITLES = {
    "全职高手",
    "道诡异仙",
    "十日终焉",
    "炼气士不死于无限",
    "我在美恐科普都市传说",
    "请勿高考时渡劫",
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
        raise RuntimeError(f"NAMED_DROP_FILE_SET_INVALID: {sorted(actual_files)}")

    allowlist = load_allowlist()
    entries = allowlist["entries"]
    if len(entries) != 1:
        raise RuntimeError(f"NAMED_DROP_ALLOWLIST_COUNT:{len(entries)}")
    entry = entries[0]
    if entry["book_title"] != "北塔夹具" or entry["chapter_no"] != 1:
        raise RuntimeError("NAMED_DROP_ALLOWLIST_ENTRY_DRIFT")
    released_titles = {item["book_title"] for item in entries}
    if released_titles & GOLD_TITLES:
        raise RuntimeError("NAMED_DROP_GOLD_BODY_ON_ALLOWLIST")

    fixture = REPOSITORY_ROOT / entry["source_txt_repo_path"]
    digest = chapter_text_sha256(fixture.read_text(encoding="utf-8"))
    if digest != entry["chapter_text_sha256"]:
        raise RuntimeError("NAMED_DROP_FIXTURE_SHA_DRIFT")

    implementation_hashes: dict[str, str] = {}
    for name in sorted(IMPLEMENTATION_FILES):
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        imports, classes = _imports_and_classes(path)
        if imports & FORBIDDEN_IMPORT_ROOTS:
            raise RuntimeError(
                "NAMED_DROP_FORBIDDEN_IMPORT: "
                f"{name}:{sorted(imports & FORBIDDEN_IMPORT_ROOTS)}"
            )
        if any(class_name.endswith(FORBIDDEN_CLASSES_SUFFIX) for class_name in classes):
            raise RuntimeError(f"NAMED_DROP_PERSISTENT_OWNER_FORBIDDEN: {name}")
        for snippet in FORBIDDEN_SOURCE_SNIPPETS:
            if snippet in source:
                raise RuntimeError(f"NAMED_DROP_FORBIDDEN_SNIPPET:{name}:{snippet}")
        if "B-09" in source or "b09" in source:
            raise RuntimeError(f"NAMED_DROP_B09_LEAK:{name}")
        implementation_hashes[name] = _sha(path)

    closed = drop_named_chapter(
        book="全职高手",
        chapter_no=1,
        txt_path=fixture,
        store_root=ROOT / "_must_not_exist_store",
    )
    if closed["wrote"] is not False or closed["gaps"] != ["GAP_NOT_RELEASED"]:
        raise RuntimeError("NAMED_DROP_UNRELEASED_MUST_NOT_WRITE")
    if closed["drop"]["txt_bytes_read"] is not False:
        raise RuntimeError("NAMED_DROP_UNRELEASED_MUST_NOT_READ")
    if closed["proof"]["identity"]["product_adopted"] is not False:
        raise RuntimeError("NAMED_DROP_PRODUCT_ADOPTION_CLAIM")
    if "写法指导" in closed["html"]:
        raise RuntimeError("NAMED_DROP_WRITING_ADVICE_LEAK")

    shapes = json.loads((ROOT / "OBJECT_SHAPES.json").read_text(encoding="utf-8"))
    if shapes["product_adopted"] is not False:
        raise RuntimeError("NAMED_DROP_OBJECT_SHAPE_PRODUCT_CLAIM")
    if shapes["writes_via"] != "wire_synthetic_chapter_to_card":
        raise RuntimeError("NAMED_DROP_WRITE_PATH_DRIFT")
    if shapes["coverage_wired"] is not False:
        raise RuntimeError("NAMED_DROP_COVERAGE_CLAIM")
    if shapes["released_entry_count"] != 1:
        raise RuntimeError("NAMED_DROP_OBJECT_SHAPE_ALLOWLIST_DRIFT")

    return {
        "document_identity": DOCUMENT_IDENTITY,
        "result": "PASS",
        "base_main_sha": closed["base_main_sha"],
        "github_issue": GITHUB_ISSUE,
        "identity_never_product_adopted": True,
        "allowlist_entry_count": 1,
        "implementation_sha256": implementation_hashes,
        "repeatability": {
            "independent_runs": 1,
            "unreleased_closed": True,
        },
        "zero_api": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))

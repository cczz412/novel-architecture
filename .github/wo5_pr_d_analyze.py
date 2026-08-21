#!/usr/bin/env python3
"""Read-only source-branch analysis for WO5 PR-D shared runtime foundation."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

SOURCE = "cc793c4719fb6470946c70e744f463147989547b"
ROOT = Path(__file__).resolve().parents[1]
MVP_PREFIX = "novel-mvp/mvp/"
TEST_PREFIX = "tests/"


def git_text(path: str, ref: str = SOURCE) -> str:
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True)


def git_paths(prefix: str, ref: str = SOURCE) -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", ref, prefix], text=True
    )
    return [line for line in output.splitlines() if line]


def module_name(path: str) -> str:
    rel = path.removeprefix(MVP_PREFIX)
    if rel.endswith("/__init__.py"):
        rel = rel[: -len("/__init__.py")]
    elif rel.endswith(".py"):
        rel = rel[:-3]
    return rel.replace("/", ".")


def internal_imports(path: str, text: str, known: set[str]) -> set[str]:
    result: set[str] = set()
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError:
        return result
    current = module_name(path)
    package = current.rsplit(".", 1)[0] if "." in current else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                base_parts = package.split(".") if package else []
                trim = max(0, node.level - 1)
                if trim:
                    base_parts = base_parts[:-trim]
                full = ".".join([*base_parts, module] if module else base_parts)
            else:
                full = module
            for prefix in ("mvp.", "novel_mvp.mvp."):
                if full.startswith(prefix):
                    full = full[len(prefix) :]
            if full in known:
                result.add(full)
            else:
                parts = full.split(".")
                while parts:
                    candidate = ".".join(parts)
                    if candidate in known:
                        result.add(candidate)
                        break
                    parts.pop()
        elif isinstance(node, ast.Import):
            for alias in node.names:
                full = alias.name
                for prefix in ("mvp.", "novel_mvp.mvp."):
                    if full.startswith(prefix):
                        full = full[len(prefix) :]
                if full in known:
                    result.add(full)
    return result


FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("M1", ("intake", "import", "ingest", "material", "upload")),
    ("M2", ("segment", "chapterization")),
    ("M3", ("extract", "admission")),
    ("M4", ("fact", "reconciliation")),
    ("M5", ("review", "confirm")),
    ("M6", ("ask", "query", "reader_context")),
    ("M7", ("check", "consistency", "health")),
    ("M8", ("plan", "planning", "outline")),
    ("M9", ("overview", "synopsis")),
    ("M10", ("scene", "export")),
    ("M11", ("context", "packer", "recall")),
    ("E5", ("work_draft", "handover", "chapter_revision", "closeout")),
)


def families_for_name(name: str) -> set[str]:
    lowered = name.lower()
    found = {
        family
        for family, tokens in FAMILY_RULES
        if any(token in lowered for token in tokens)
    }
    return found


def direct_test_refs(source_tests: dict[str, str], module: str, path: str) -> list[str]:
    basename = Path(path).stem
    needles = {
        f"mvp.{module}",
        f"from mvp import {module}",
        f"from mvp.{module}",
        f"import mvp.{module}",
        basename,
    }
    result = []
    for test_path, text in source_tests.items():
        if any(needle in text for needle in needles):
            result.append(test_path)
    return sorted(result)


def main() -> None:
    source_files = [
        path
        for path in git_paths(MVP_PREFIX)
        if path.endswith(".py")
    ]
    modules = {module_name(path) for path in source_files}
    path_by_module = {module_name(path): path for path in source_files}
    texts = {path: git_text(path) for path in source_files}
    imports = {
        module_name(path): internal_imports(path, text, modules)
        for path, text in texts.items()
    }
    reverse: dict[str, set[str]] = defaultdict(set)
    for consumer, deps in imports.items():
        for dep in deps:
            reverse[dep].add(consumer)

    source_test_paths = [
        path
        for path in git_paths(TEST_PREFIX)
        if path.endswith(".py") and Path(path).name.startswith("test")
    ]
    source_tests = {path: git_text(path) for path in source_test_paths}

    rows: list[dict[str, Any]] = []
    for module in sorted(modules):
        path = path_by_module[module]
        consumers = sorted(reverse.get(module, set()))
        consumer_families = sorted(
            set().union(*(families_for_name(item) for item in consumers))
            if consumers
            else set()
        )
        own_families = sorted(families_for_name(module))
        doc = ""
        try:
            doc = ast.get_docstring(ast.parse(texts[path])) or ""
        except SyntaxError:
            pass
        exists_on_main = subprocess.run(
            ["git", "cat-file", "-e", f"origin/main:{path}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        rows.append(
            {
                "path": path,
                "module": module,
                "exists_on_main": exists_on_main,
                "source_blob": subprocess.check_output(
                    ["git", "rev-parse", f"{SOURCE}:{path}"], text=True
                ).strip(),
                "imports": sorted(imports[module]),
                "imported_by": consumers,
                "consumer_families": consumer_families,
                "own_families": own_families,
                "direct_tests": direct_test_refs(source_tests, module, path),
                "docstring": doc.splitlines()[0] if doc else "",
            }
        )

    trace = json.loads(
        (ROOT / "governance/capability_traceability.json").read_text(
            encoding="utf-8"
        )
    )
    owner_names = {"AUTHOR_WORKSPACE", "STORAGE", "ROUTER", "SHARED_SERVICE"}
    requirements = []
    for row in trace.get("requirements", []):
        if not isinstance(row, dict):
            continue
        owners = {row.get("primary_owner")}
        shared = row.get("shared_owners", [])
        if isinstance(shared, list):
            owners.update(item for item in shared if isinstance(item, str))
        matched = sorted(owner_names & owners)
        if matched:
            requirements.append(
                {
                    "requirement_id": row.get("requirement_id"),
                    "matched_owners": matched,
                    "primary_owner": row.get("primary_owner"),
                    "shared_owners": shared,
                    "requirement_text": row.get("requirement_text"),
                    "implementation_refs": row.get("implementation_refs", []),
                    "test_refs": row.get("test_refs", []),
                }
            )

    candidate_keywords = re.compile(
        r"workspace|storage|store|safe|path|atomic|serialize|schema|validat|"
        r"intent|route|router|handle|recall|author|project|artifact|lock|commit|"
        r"transaction|identity|registry",
        re.IGNORECASE,
    )
    likely = [
        row
        for row in rows
        if candidate_keywords.search(row["module"])
        or len([f for f in row["consumer_families"] if f.startswith("M")]) >= 2
    ]

    report = {
        "source": SOURCE,
        "main": subprocess.check_output(
            ["git", "rev-parse", "origin/main"], text=True
        ).strip(),
        "source_python_file_count": len(rows),
        "source_test_file_count": len(source_test_paths),
        "requirements": requirements,
        "likely_shared_candidates": likely,
        "all_runtime_files": rows,
    }
    output = ROOT / ".github/wo5_pr_d_analysis.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("WO5_PR_D_ANALYSIS_START")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("WO5_PR_D_ANALYSIS_END")


if __name__ == "__main__":
    main()

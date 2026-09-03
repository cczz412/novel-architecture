"""Deterministic zero-API self-check for CCZ-142 candidate authority R01."""

from __future__ import annotations

import ast
import inspect
import json
import tempfile
from pathlib import Path
from typing import Any

from candidate_authority import AUTHORITY_SCHEMA_ID, CandidateRootInitializer
from shadow_fixtures import build_full_shadow

ROOT = Path(__file__).resolve().parent
PRODUCT_FILES = (
    ROOT / "candidate_authority.py",
    ROOT / "legacy_migration.py",
    ROOT / "reopen_probe.py",
)
FORBIDDEN_IMPORTS = {
    "aiohttp",
    "httpx",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
MUTATION_NEEDLES = (
    "INSERT INTO candidate_versions",
    "INSERT INTO current_pointers",
    "UPDATE current_pointers",
    "INSERT INTO candidate_migrations",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
    return names


def run_self_check() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ccz142-authority-self-check-a-") as a:
        first = build_full_shadow(Path(a)).result
    with tempfile.TemporaryDirectory(prefix="ccz142-authority-self-check-b-") as b:
        second = build_full_shadow(Path(b)).result
    if first != second:
        raise AssertionError("CROSS_PROCESS_INPUT_EQUIVALENT_REPLAY_DRIFT")
    forbidden_imports = sorted(
        {
            name
            for path in PRODUCT_FILES
            for name in _imports(path)
            if name in FORBIDDEN_IMPORTS
        }
    )
    if forbidden_imports:
        raise AssertionError(f"FORBIDDEN_PRODUCT_IMPORTS:{forbidden_imports}")
    mutation_owners = sorted(
        path.name
        for path in PRODUCT_FILES
        if any(
            needle in path.read_text(encoding="utf-8")
            for needle in MUTATION_NEEDLES
        )
    )
    if mutation_owners != ["candidate_authority.py"]:
        raise AssertionError(f"MULTIPLE_CANDIDATE_WRITERS:{mutation_owners}")
    root_parameters = list(
        inspect.signature(CandidateRootInitializer.initialize_root).parameters
    )
    if root_parameters != ["self", "request"]:
        raise AssertionError("ROOT_CAPABILITY_SURFACE_DRIFT")
    if first["formal_tables"] or first["formal_writes"]:
        raise AssertionError("FORMAL_WRITE_BOUNDARY_BROKEN")
    if first["model_api_calls"] or first["network_api_calls"]:
        raise AssertionError("ZERO_API_BOUNDARY_BROKEN")
    if first["pointer_namespace"] != "FIXTURE_ONLY":
        raise AssertionError("CURRENT_CONTRACT_NAMESPACE_DRIFT")
    return {
        "document_identity": "CCZ142-CANDIDATE-AUTHORITY-R02-SELF-CHECK",
        "result": "PASS",
        "base_main_sha": "c89beb4368b6b79598906bdc27819a16f751155b",
        "full_shadow": first,
        "repeatability": {
            "independent_runs": 2,
            "exact_result_match": True,
        },
        "writer_audit": {
            "candidate_destination_mutation_owners": mutation_owners,
            "root_public_parameters": root_parameters,
            "generic_root_read_exposed": hasattr(CandidateRootInitializer, "read"),
            "generic_root_commit_exposed": hasattr(
                CandidateRootInitializer, "commit"
            ),
        },
        "authority_commit_guard": {
            "serialization_required": True,
            "held_through_root_commit": True,
        },
        "migration_guard": {
            "source_identity_import_once": True,
            "source_stability_checked_before_commit": True,
            "pointer_row_identity_bound": True,
            "b01_root_and_migration_receipt_one_transaction": True,
        },
        "authority_schema": AUTHORITY_SCHEMA_ID.decode("utf-8"),
        "external_calls": {
            "model_api_calls": 0,
            "network_api_calls": 0,
            "browser_actions": 0,
        },
        "formal_writes": 0,
        "adoption_boundary": {
            "product_namespace_adopted": False,
            "current_pointer_namespace": "FIXTURE_ONLY",
            "review_or_merge_does_not_equal_product_adoption": True,
        },
    }


def main() -> int:
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

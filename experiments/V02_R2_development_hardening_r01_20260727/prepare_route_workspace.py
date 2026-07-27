from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from . import r2_dev_hardening as hardening


class RouteWorkspacePreparationError(ValueError):
    """R2 路线输入工作区准备拒收错误。"""


def _reject_source_path(path: Path) -> None:
    if path.is_symlink():
        raise RouteWorkspacePreparationError(f"SOURCE_SYMLINK_FORBIDDEN:{path}")
    resolved_parts = {part.lower() for part in path.resolve().parts}
    if resolved_parts & hardening.FORBIDDEN_ROUTE_PATH_PARTS:
        raise RouteWorkspacePreparationError(f"SOURCE_PATH_FORBIDDEN:{path}")


def _copy_exact(source: Path, target: Path) -> None:
    _reject_source_path(source)
    if not source.is_file():
        raise RouteWorkspacePreparationError(f"SOURCE_FILE_MISSING:{source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if source.read_bytes() != target.read_bytes():
        raise RouteWorkspacePreparationError(f"SOURCE_COPY_MISMATCH:{source}")


def prepare_route_workspace(
    *,
    question_set_path: Path,
    catalog_dir: Path,
    workspace: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    _reject_source_path(question_set_path)
    _reject_source_path(catalog_dir)
    catalog_paths = sorted(catalog_dir.glob("*.json"))
    if len(catalog_paths) != 3:
        raise RouteWorkspacePreparationError(
            f"SOURCE_CATALOG_COUNT_INVALID:{len(catalog_paths)}"
        )
    if workspace.exists() and any(workspace.iterdir()):
        raise RouteWorkspacePreparationError("ROUTE_WORKSPACE_NOT_EMPTY")
    _copy_exact(question_set_path, workspace / "question_set.json")
    for path in catalog_paths:
        _copy_exact(path, workspace / "source_catalog_v2" / path.name)

    files = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        files.append(
            {
                "path": path.relative_to(workspace).as_posix(),
                "artifact_type": (
                    "QUESTION_SET"
                    if path.name == "question_set.json"
                    else "SOURCE_CATALOG"
                ),
                "bytes": path.stat().st_size,
                "sha256": hardening.sha256_file(path),
            }
        )
    manifest = {
        "schema_version": hardening.ROUTE_WORKSPACE_MANIFEST_SCHEMA,
        "issuer_type": "LOCAL_PREREGISTERED_CANDIDATE",
        "sealed_before_run": True,
        "files": files,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(hardening.canonical_bytes(manifest))
    manifest_sha256 = hardening.sha256_file(manifest_path)
    verification = hardening.verify_route_workspace(
        workspace,
        preregistered_manifest_path=manifest_path,
        expected_manifest_sha256=manifest_sha256,
    )
    return {
        "schema_version": "v02-r2-route-workspace-preparation-receipt.v1",
        "status": "PASS",
        "workspace": workspace.as_posix(),
        "manifest_path": manifest_path.as_posix(),
        "manifest_sha256": manifest_sha256,
        "file_count": len(files),
        "model_api_calls": 0,
        "network_calls": 0,
        "verification": verification,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question-set", type=Path, required=True)
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = prepare_route_workspace(
        question_set_path=args.question_set,
        catalog_dir=args.catalog_dir,
        workspace=args.workspace,
        manifest_path=args.manifest,
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_bytes(hardening.canonical_bytes(receipt))
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

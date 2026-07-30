from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


PLAN_CONTRACT_VERSION = "experiment-materialize-plan-v1"
ALLOWLIST_CONTRACT_ID = "experiment-materialize-allowlist-v1"
RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")

SOURCE_ROOTS = (
    "config",
    "experiments",
    "schemas",
    "tests/fixtures/experiment_workspace",
    "tools",
)
FORBIDDEN_SOURCE_SEGMENTS = {
    ".git",
    ".local",
    "__pycache__",
    "analysis_library",
    "corpus-downloads",
    "foundation",
    "intake",
    "outbox",
    "reports",
    "runs",
    "TEMP",
}
DESTINATION_ROOTS_BY_ROLE = {
    "api": "workspace/api",
    "context": "workspace/context",
    "input": "inputs",
    "program": "workspace/program",
    "prompt": "workspace/prompts",
    "schema": "workspace/schemas",
    "validator": "workspace/validators",
}
CAPABILITY_LIMITS = {
    "delete_source": False,
    "external_removal": False,
    "materialize_only": True,
    "model_api": False,
    "network": False,
    "notion_write": False,
    "physical_move": False,
    "preflight": False,
}
PLAN_KEYS = {
    "allowlist_contract_id",
    "allowlist_contract_sha256",
    "capability_limits",
    "contract_version",
    "expected_head_sha",
    "items",
    "materializer_bundle_sha256",
    "plan_id",
    "revision",
    "run_id",
    "s0_receipt",
}
ITEM_KEYS = {
    "bytes",
    "destination",
    "role",
    "sha256",
    "source",
    "source_type",
}
S0_RECEIPT_KEYS = {
    "path",
    "sha256",
    "wave_plan_path",
    "wave_plan_sha256",
}


class ContractError(ValueError):
    def __init__(self, code: str, path: str | None = None):
        super().__init__(code)
        self.code = code
        self.path = path


@dataclass(frozen=True)
class MaterializeItem:
    role: str
    source: str
    destination: str
    size: int
    sha256: str


@dataclass(frozen=True)
class MaterializePlan:
    plan_id: str
    run_id: str
    revision: int
    expected_head_sha: str
    s0_receipt_path: str
    s0_receipt_sha256: str
    s0_wave_plan_path: str
    s0_wave_plan_sha256: str
    materializer_bundle_sha256: str
    allowlist_contract_sha256: str
    items: tuple[MaterializeItem, ...]


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_repo_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if "\\" in value or "//" in value or "\x00" in value:
        return False
    pure = PurePosixPath(value)
    return not pure.is_absolute() and all(part not in {"", ".", ".."} for part in pure.parts)


def path_is_within(value: str, roots: tuple[str, ...]) -> bool:
    return any(value == root or value.startswith(f"{root}/") for root in roots)


def allowlist_contract() -> dict[str, Any]:
    return {
        "contract_id": ALLOWLIST_CONTRACT_ID,
        "source_roots": list(SOURCE_ROOTS),
        "forbidden_source_segments": sorted(FORBIDDEN_SOURCE_SEGMENTS),
        "destination_roots_by_role": DESTINATION_ROOTS_BY_ROLE,
        "capability_limits": CAPABILITY_LIMITS,
        "source_type": "file",
        "link_policy": "reject_symlink_and_hardlink",
        "publish_policy": "one_run_one_atomic_publish",
        "sensitive_scan_policy": "reject_before_copy",
    }


def allowlist_contract_sha256() -> str:
    return sha256_bytes(canonical_json_bytes(allowlist_contract()))


def _require_exact_keys(
    value: object,
    expected: set[str],
    *,
    code: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ContractError(code)
    return value


def _require_sha(value: object, *, code: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ContractError(code)
    return value


def _parse_item(value: object) -> MaterializeItem:
    row = _require_exact_keys(value, ITEM_KEYS, code="ITEM_SHAPE_INVALID")
    role = row["role"]
    if role not in DESTINATION_ROOTS_BY_ROLE:
        raise ContractError("ITEM_ROLE_NOT_ALLOWED")

    source = row["source"]
    source_parts = set(PurePosixPath(source).parts) if isinstance(source, str) else set()
    if (
        not is_repo_relative_path(source)
        or not path_is_within(source, SOURCE_ROOTS)
        or bool(source_parts & FORBIDDEN_SOURCE_SEGMENTS)
    ):
        raise ContractError("SOURCE_PATH_NOT_ALLOWED")

    destination = row["destination"]
    expected_root = DESTINATION_ROOTS_BY_ROLE[role]
    if (
        not is_repo_relative_path(destination)
        or destination == expected_root
        or not destination.startswith(f"{expected_root}/")
    ):
        raise ContractError("DESTINATION_PATH_NOT_ALLOWED")

    if row["source_type"] != "file":
        raise ContractError("SOURCE_TYPE_NOT_ALLOWED", source)
    size = row["bytes"]
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ContractError("ITEM_SIZE_INVALID", source)
    digest = _require_sha(row["sha256"], code="ITEM_SHA256_INVALID")
    return MaterializeItem(
        role=role,
        source=source,
        destination=destination,
        size=size,
        sha256=digest,
    )


def parse_plan(value: object) -> MaterializePlan:
    plan = _require_exact_keys(value, PLAN_KEYS, code="PLAN_SHAPE_INVALID")
    if plan["contract_version"] != PLAN_CONTRACT_VERSION:
        raise ContractError("PLAN_CONTRACT_UNSUPPORTED")
    if (
        not isinstance(plan["plan_id"], str)
        or not plan["plan_id"]
        or len(plan["plan_id"]) > 120
    ):
        raise ContractError("PLAN_ID_INVALID")
    run_id = plan["run_id"]
    if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ContractError("RUN_ID_INVALID")
    revision = plan["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ContractError("REVISION_INVALID")
    head_sha = plan["expected_head_sha"]
    if not isinstance(head_sha, str) or GIT_SHA_PATTERN.fullmatch(head_sha) is None:
        raise ContractError("EXPECTED_HEAD_SHA_INVALID")

    receipt = _require_exact_keys(
        plan["s0_receipt"],
        S0_RECEIPT_KEYS,
        code="S0_RECEIPT_SHAPE_INVALID",
    )
    receipt_path = receipt["path"]
    if (
        not is_repo_relative_path(receipt_path)
        or not receipt_path.startswith("TEMP/restructure_wave_preflight/")
    ):
        raise ContractError("S0_RECEIPT_PATH_NOT_ALLOWED")
    wave_plan_path = receipt["wave_plan_path"]
    if (
        not is_repo_relative_path(wave_plan_path)
        or not wave_plan_path.startswith("TEMP/restructure_wave_preflight/")
    ):
        raise ContractError("S0_WAVE_PLAN_PATH_NOT_ALLOWED")

    if plan["allowlist_contract_id"] != ALLOWLIST_CONTRACT_ID:
        raise ContractError("ALLOWLIST_CONTRACT_ID_MISMATCH")
    allowlist_sha = _require_sha(
        plan["allowlist_contract_sha256"],
        code="ALLOWLIST_CONTRACT_SHA256_INVALID",
    )
    if allowlist_sha != allowlist_contract_sha256():
        raise ContractError("ALLOWLIST_CONTRACT_SHA256_MISMATCH")
    if plan["capability_limits"] != CAPABILITY_LIMITS:
        raise ContractError("CAPABILITY_LIMITS_MISMATCH")

    raw_items = plan["items"]
    if not isinstance(raw_items, list) or not raw_items:
        raise ContractError("ITEMS_EMPTY")
    items = tuple(_parse_item(item) for item in raw_items)
    sources = [item.source for item in items]
    destinations = [item.destination for item in items]
    if len(sources) != len(set(sources)):
        raise ContractError("SOURCE_PATH_DUPLICATE")
    if len(destinations) != len(set(destinations)):
        raise ContractError("DESTINATION_PATH_DUPLICATE")
    if destinations != sorted(destinations):
        raise ContractError("ITEMS_NOT_SORTED")

    return MaterializePlan(
        plan_id=plan["plan_id"],
        run_id=run_id,
        revision=revision,
        expected_head_sha=head_sha,
        s0_receipt_path=receipt_path,
        s0_receipt_sha256=_require_sha(
            receipt["sha256"],
            code="S0_RECEIPT_SHA256_INVALID",
        ),
        s0_wave_plan_path=wave_plan_path,
        s0_wave_plan_sha256=_require_sha(
            receipt["wave_plan_sha256"],
            code="S0_WAVE_PLAN_SHA256_INVALID",
        ),
        materializer_bundle_sha256=_require_sha(
            plan["materializer_bundle_sha256"],
            code="MATERIALIZER_BUNDLE_SHA256_INVALID",
        ),
        allowlist_contract_sha256=allowlist_sha,
        items=items,
    )


def load_json_object(data: bytes, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(code) from exc
    if not isinstance(value, dict):
        raise ContractError(code)
    return value


def bundle_source_paths(repo_root: Path) -> tuple[Path, ...]:
    module_root = repo_root / "tools/experiment_workspace_modules"
    paths = [repo_root / "tools/experiment_workspace.py"]
    paths.extend(sorted(module_root.glob("*.py")))
    return tuple(paths)


def materializer_bundle_manifest(repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in bundle_source_paths(repo_root):
        relative = path.relative_to(repo_root).as_posix()
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ContractError("MATERIALIZER_FILE_REJECTED", relative)
        rows.append({"path": relative, "sha256": sha256_bytes(path.read_bytes())})
    return rows


def materializer_bundle_sha256(repo_root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(materializer_bundle_manifest(repo_root)))

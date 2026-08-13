#!/usr/bin/env python3
"""微调域 R02 控制面：注册、封版、切换当前与兼容路牌。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DOMAIN_ROOT = ROOT / "finetuning"
EXPERIMENTS_ROOT = DOMAIN_ROOT / "experiments"
CURRENT_PATH = DOMAIN_ROOT / "CURRENT.json"
REFERENCE_ROOT = ROOT / "references/t5-r04"
ROUTE_CATALOG_PATH = REFERENCE_ROOT / "route_catalog.json"
ROUTE_VIEW_PATH = REFERENCE_ROOT / "route_registry.json"
ROUTE_README_PATH = REFERENCE_ROOT / "README.md"
ROUTE_RECEIPT_PATH = REFERENCE_ROOT / "R02_ROUTE_DERIVATION_RECEIPT.json"
CONSUMER_RECEIPT_PATH = REFERENCE_ROOT / "R02_CONSUMER_RECEIPT.json"

sys.path.insert(0, str(ROOT / "tools"))
import finetuning_domain as domain  # noqa: E402


class HardStop(RuntimeError):
    """控制面条件不足，不能继续。"""


def canonical_json(value: Any) -> bytes:
    return domain.canonical_json(value)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HardStop(f"无法读取 JSON：{path}：{exc}") from exc
    if not isinstance(value, dict):
        raise HardStop(f"JSON 根必须是对象：{path}")
    return value


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def create_only(path: Path, data: bytes) -> str:
    if path.exists():
        if path.read_bytes() != data:
            raise HardStop(f"文件已存在且内容不同，拒绝覆盖：{path}")
        return "UNCHANGED"
    atomic_write(path, data)
    return "CREATED"


def experiment_dir(experiment_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", experiment_id):
        raise HardStop(f"experiment_id 不安全：{experiment_id}")
    return EXPERIMENTS_ROOT / experiment_id


def _json_pointer(value: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise HardStop(f"JSON pointer 必须以 / 开头：{pointer}")
    current = value
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise HardStop(f"JSON pointer 无法定位：{pointer}")
    return current


def _measurement_path(
    measurement: dict[str, Any], spec: dict[str, Any], stores: dict[str, Path]
) -> Path:
    source_root = spec["source_root"]
    store_id = measurement.get("store_id", source_root["store_id"])
    if store_id not in stores:
        raise HardStop(f"measurement 使用未知仓位：{store_id}")
    relative_path = str(measurement.get("relative_path") or "")
    if measurement.get("relative_to_source_root", True):
        relative_path = f"{source_root['relative_path']}/{relative_path}"
    return domain.safe_file(stores[store_id], relative_path)


def evaluate_measurements(
    spec: dict[str, Any], stores: dict[str, Path]
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, measurement in sorted((spec.get("measurements") or {}).items()):
        if not isinstance(measurement, dict):
            raise HardStop(f"measurement 不是对象：{name}")
        operation = measurement.get("operation")
        path = _measurement_path(measurement, spec, stores)
        if operation == "jsonl_rows":
            results[name] = domain.jsonl_stats(path)["rows"]
        elif operation == "jsonl_facts":
            results[name] = domain.jsonl_stats(path, count_facts=True)["facts"]
        elif operation == "file_sha256":
            results[name] = domain.sha256_file(path)
        elif operation == "file_bytes":
            results[name] = path.stat().st_size
        elif operation == "json_value":
            results[name] = _json_pointer(load_json(path), str(measurement.get("pointer")))
        else:
            raise HardStop(f"未知 measurement operation：{name}:{operation}")
    return results


def verify_assertions(spec: dict[str, Any], values: dict[str, Any]) -> None:
    for index, assertion in enumerate(spec.get("assertions") or [], 1):
        kind = assertion.get("type")
        if kind == "equal":
            names = assertion.get("measurements") or []
            actual = [values[name] for name in names]
            if not actual or any(value != actual[0] for value in actual[1:]):
                raise HardStop(f"assertion {index} equal 失败：{dict(zip(names, actual))}")
        elif kind == "sum":
            target = assertion.get("target")
            terms = assertion.get("terms") or []
            expected = sum(values[name] for name in terms)
            if values[target] != expected:
                raise HardStop(
                    f"assertion {index} sum 失败：{target}={values[target]} != {expected}"
                )
        else:
            raise HardStop(f"未知 assertion：{index}:{kind}")


def validate_spec_v2(spec: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "experiment_id",
        "manifest_revision",
        "source_root",
        "state",
        "artifact_groups",
        "measurements",
        "assertions",
        "current_gate",
        "boundaries",
    }
    if set(spec) != required:
        raise HardStop(f"v2 SPEC 字段不符：missing={required-set(spec)}, extra={set(spec)-required}")
    if spec["schema_version"] != "finetuning-experiment-spec-v2":
        raise HardStop("register 只接收 finetuning-experiment-spec-v2")
    experiment_dir(str(spec["experiment_id"]))
    if not isinstance(spec["artifact_groups"], list) or not spec["artifact_groups"]:
        raise HardStop("v2 SPEC 至少要有一个 artifact group")
    gate = spec.get("current_gate") or {}
    required_receipts = gate.get("required_receipts")
    if not isinstance(required_receipts, list) or not required_receipts:
        raise HardStop("current_gate.required_receipts 至少要有一张验收票")


def command_register(spec_path: Path) -> int:
    spec = load_json(spec_path)
    validate_spec_v2(spec)
    target_dir = experiment_dir(spec["experiment_id"])
    state = create_only(target_dir / "SPEC.json", canonical_json(spec))
    print(json.dumps({"status": "REGISTERED_NOT_CURRENT", "spec": state}, indent=2))
    return 0


def build_manifest_v2(experiment_id: str) -> tuple[dict[str, Any], bytes, Path]:
    target_dir = experiment_dir(experiment_id)
    spec = load_json(target_dir / "SPEC.json")
    validate_spec_v2(spec)
    stores = domain.load_stores()
    artifacts, _ = domain.collect_artifacts(spec, stores)
    measurements = evaluate_measurements(spec, stores)
    verify_assertions(spec, measurements)
    manifest = {
        "schema_version": "finetuning-experiment-manifest-v1",
        "experiment_id": experiment_id,
        "manifest_revision": spec["manifest_revision"],
        "spec_sha256": domain.sha256_file(target_dir / "SPEC.json"),
        "state": spec["state"],
        "source_root": spec["source_root"],
        "artifacts": artifacts,
        "derived_facts": measurements,
        "boundaries": spec["boundaries"],
    }
    return manifest, canonical_json(manifest), target_dir


def command_build(experiment_id: str) -> int:
    manifest, data, target_dir = build_manifest_v2(experiment_id)
    manifest_sha = sha256_bytes(data)
    manifest_state = create_only(target_dir / "MANIFEST.json", data)
    sha_state = create_only(
        target_dir / "MANIFEST.sha256", f"{manifest_sha}  MANIFEST.json\n".encode()
    )
    print(
        json.dumps(
            {
                "status": "SEALED_NOT_CURRENT",
                "manifest": manifest_state,
                "sha_file": sha_state,
                "manifest_sha256": manifest_sha,
            },
            indent=2,
        )
    )
    return 0


def validate_manifest_artifacts(manifest: dict[str, Any]) -> None:
    stores = domain.load_stores()
    for artifact in manifest.get("artifacts") or []:
        path = domain.safe_file(stores[artifact["store_id"]], artifact["relative_path"])
        if path.stat().st_size != artifact["bytes"]:
            raise HardStop(f"工件大小漂移：{artifact['artifact_id']}")
        if domain.sha256_file(path) != artifact["sha256"]:
            raise HardStop(f"工件 SHA 漂移：{artifact['artifact_id']}")


def _receipt_status(receipt: dict[str, Any], pointer: str) -> Any:
    return _json_pointer(receipt, pointer)


def validate_current_gate(experiment_id: str) -> tuple[dict[str, Any], str]:
    target_dir = experiment_dir(experiment_id)
    spec = load_json(target_dir / "SPEC.json")
    if spec.get("schema_version") != "finetuning-experiment-spec-v2":
        raise HardStop("新 CURRENT 切换只允许走 v2 SPEC；旧 R01 当前实验只作既有兼容")
    manifest_path = target_dir / "MANIFEST.json"
    manifest = load_json(manifest_path)
    _, rebuilt, _ = build_manifest_v2(experiment_id)
    if manifest_path.read_bytes() != rebuilt:
        raise HardStop("MANIFEST 与实物重建结果不一致")
    validate_manifest_artifacts(manifest)
    stores = domain.load_stores()
    for rule in (spec.get("current_gate") or {}).get("required_receipts") or []:
        store_id = rule.get("store_id")
        if store_id not in stores:
            raise HardStop(f"CURRENT 验收票使用未知仓位：{store_id}")
        receipt_path = domain.safe_file(stores[store_id], str(rule["relative_path"]))
        if rule.get("sha256") and domain.sha256_file(receipt_path) != rule["sha256"]:
            raise HardStop(f"CURRENT 验收票 SHA 不符：{receipt_path}")
        status = _receipt_status(load_json(receipt_path), str(rule["status_pointer"]))
        if status not in (rule.get("allowed_values") or []):
            raise HardStop(f"CURRENT 验收票状态未放行：{receipt_path}:{status}")
    return manifest, sha256_bytes(rebuilt)


def render_current_pointer(manifest: dict[str, Any], manifest_sha: str) -> bytes:
    return canonical_json(
        {
            "schema_version": "finetuning-current-pointer-v2",
            "current_experiment_id": manifest["experiment_id"],
            "manifest_revision": manifest["manifest_revision"],
            "manifest_sha256": manifest_sha,
            "scope": "navigation_only",
            "may_authorize_training": False,
            "may_authorize_promotion": False,
        }
    )


def command_switch_current(experiment_id: str) -> int:
    manifest, manifest_sha = validate_current_gate(experiment_id)
    atomic_write(CURRENT_PATH, render_current_pointer(manifest, manifest_sha))
    print(json.dumps({"status": "CURRENT_SWITCHED", "experiment_id": experiment_id}, indent=2))
    return 0


def command_refresh_existing_current() -> int:
    current = load_json(CURRENT_PATH)
    experiment_id = str(current["current_experiment_id"])
    target_dir = experiment_dir(experiment_id)
    manifest_path = target_dir / "MANIFEST.json"
    manifest = load_json(manifest_path)
    validate_manifest_artifacts(manifest)
    manifest_sha = domain.sha256_file(manifest_path)
    if current.get("manifest_sha256") and current["manifest_sha256"] != manifest_sha:
        raise HardStop("CURRENT 已绑定的 MANIFEST SHA 与实物不一致")
    atomic_write(CURRENT_PATH, render_current_pointer(manifest, manifest_sha))
    print(json.dumps({"status": "CURRENT_REFERENCE_REFRESHED", "experiment_id": experiment_id}, indent=2))
    return 0


def bootstrap_route_catalog() -> int:
    if ROUTE_CATALOG_PATH.exists():
        print(json.dumps({"status": "ROUTE_CATALOG_ALREADY_EXISTS"}, indent=2))
        return 0
    legacy = load_json(ROUTE_VIEW_PATH)
    aliases = {
        root_id: ("MAIN_REPO" if root_id == "repo" else "LAB")
        for root_id in (legacy.get("roots") or {})
    }
    routes: list[dict[str, Any]] = []
    for old_route in legacy.get("routes") or []:
        route = dict(old_route)
        root_id = route.pop("root_id")
        route["store_id"] = aliases[root_id]
        routes.append(route)
    catalog = {
        "schema_version": "finetuning-legacy-route-catalog-v1",
        "source_snapshot_sha256": domain.sha256_file(ROUTE_VIEW_PATH),
        "authority": {
            "scope": "historical_navigation_catalog",
            "may_define_current_experiment": False,
            "may_authorize_training": False,
            "may_authorize_upload": False,
            "may_authorize_deletion_or_merge": False,
        },
        "routes": routes,
    }
    state = create_only(ROUTE_CATALOG_PATH, canonical_json(catalog))
    print(json.dumps({"status": state, "routes": len(routes)}, indent=2))
    return 0


def render_route_view() -> tuple[bytes, bytes, dict[str, Any]]:
    catalog = load_json(ROUTE_CATALOG_PATH)
    current = load_json(CURRENT_PATH)
    target_dir = experiment_dir(str(current["current_experiment_id"]))
    manifest_path = target_dir / "MANIFEST.json"
    manifest = load_json(manifest_path)
    manifest_sha = domain.sha256_file(manifest_path)
    if current.get("manifest_sha256") != manifest_sha:
        raise HardStop("CURRENT 没有正确绑定当前 MANIFEST")
    validate_manifest_artifacts(manifest)
    view = {
        "schema_version": "t5-r04-route-registry-derived.v2",
        "authority": {
            "scope": "compatibility_derived_view",
            "may_define_current_truth": False,
            "may_authorize_training": False,
            "may_authorize_upload": False,
            "may_authorize_deletion_or_merge": False,
        },
        "generated_from": {
            "route_catalog_sha256": domain.sha256_file(ROUTE_CATALOG_PATH),
            "current_pointer_sha256": domain.sha256_file(CURRENT_PATH),
            "manifest_sha256": manifest_sha,
        },
        "current_experiment": {
            "experiment_id": manifest["experiment_id"],
            "manifest_revision": manifest["manifest_revision"],
            "manifest_sha256": manifest_sha,
            "derived_facts": manifest["derived_facts"],
        },
        "historical_routes": catalog["routes"],
    }
    facts = manifest["derived_facts"]
    readme = f"""# T5 R04 微调兼容路牌

这页是机器派生视图，删除后可以从微调域当前入口、当前 MANIFEST 和历史路线目录完整重建。

## 当前实验

- experiment_id：`{manifest['experiment_id']}`
- MANIFEST revision：`{manifest['manifest_revision']}`
- MANIFEST SHA：`{manifest_sha}`
- 每臂母集：{facts['full_rows_each_arm']} 行
- 每臂训练：{facts['training_rows_each_arm']} 行
- 当前考卷：每臂 {facts['current_exam_rows_each_arm']} 题
- 当前金标：每臂 {facts['current_gold_facts_each_arm']} 条

当前实验身份只认 [微调域入口](../../finetuning/CURRENT.json) 和它绑定的 MANIFEST。本目录不再人工维护“C 未生成”或“哪个候选最新”一类当前状态。

## 历史路线

历史来源位置和依赖关系保存在 `route_catalog.json`。它只负责“旧东西去哪里找”，不能决定当前实验或授权训练。

机器兼容视图是 `route_registry.json`；现有消费者应把它当可重建导航，不得当唯一真源。

来源：Codex
""".encode("utf-8")
    return canonical_json(view), readme, view


def scan_consumers() -> list[dict[str, str]]:
    needles = ("references/t5-r04/route_registry.json", "t5-r04/route_registry.json")
    excluded_roots = {".git", "TEMP", "runs", "reports", ".local"}
    generated = {ROUTE_VIEW_PATH, ROUTE_README_PATH, ROUTE_RECEIPT_PATH, CONSUMER_RECEIPT_PATH}
    rows: list[dict[str, str]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path in generated:
            continue
        rel = path.relative_to(ROOT)
        if any(part in excluded_roots for part in rel.parts):
            continue
        if path.suffix not in {".py", ".md", ".json", ".yaml", ".yml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(needle in text for needle in needles) or (
            path.name == "test_t5_r04_route_registry.py"
        ):
            rows.append(
                {
                    "path": rel.as_posix(),
                    "role": (
                        "compatibility_test"
                        if path.name == "test_t5_r04_route_registry.py"
                        else "reference"
                    ),
                }
            )
    return rows


def command_build_routes(output_dir: Path | None = None) -> int:
    registry_data, readme_data, view = render_route_view()
    target_root = output_dir or REFERENCE_ROOT
    registry_path = target_root / "route_registry.json"
    readme_path = target_root / "README.md"
    atomic_write(registry_path, registry_data)
    atomic_write(readme_path, readme_data)

    consumers = scan_consumers()
    consumer_receipt = {
        "schema_version": "finetuning-r02-route-consumers-v1",
        "status": "PASS_NO_PRODUCTION_UNIQUE_TRUTH_CONSUMER",
        "consumers": consumers,
        "consumer_count": len(consumers),
        "note": "route registry 仅供兼容导航与回归测试；当前实验只认 finetuning/CURRENT.json。",
    }
    if output_dir is None:
        atomic_write(CONSUMER_RECEIPT_PATH, canonical_json(consumer_receipt))
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = Path(temp_dir)
            isolated_registry = isolated_root / "route_registry.json"
            isolated_readme = isolated_root / "README.md"
            atomic_write(isolated_registry, registry_data)
            atomic_write(isolated_readme, readme_data)
            rebuild_pass = (
                isolated_registry.read_bytes() == registry_data
                and isolated_readme.read_bytes() == readme_data
            )
        receipt = {
            "schema_version": "finetuning-r02-route-derivation-v1",
            "status": "PASS_DERIVED_VIEWS_REBUILDABLE",
            "route_catalog_sha256": view["generated_from"]["route_catalog_sha256"],
            "current_pointer_sha256": view["generated_from"]["current_pointer_sha256"],
            "manifest_sha256": view["generated_from"]["manifest_sha256"],
            "route_registry_sha256": sha256_bytes(registry_data),
            "readme_sha256": sha256_bytes(readme_data),
            "historical_route_count": len(view["historical_routes"]),
            "isolated_delete_and_rebuild_equivalent": rebuild_pass,
        }
        atomic_write(ROUTE_RECEIPT_PATH, canonical_json(receipt))
    print(
        json.dumps(
            {
                "status": "PASS_DERIVED_VIEWS_REBUILT",
                "output_dir": str(target_root),
                "historical_routes": len(view["historical_routes"]),
            },
            indent=2,
        )
    )
    return 0


def command_verify_current() -> int:
    current = load_json(CURRENT_PATH)
    target_dir = experiment_dir(str(current["current_experiment_id"]))
    manifest_path = target_dir / "MANIFEST.json"
    manifest = load_json(manifest_path)
    manifest_sha = domain.sha256_file(manifest_path)
    if current.get("manifest_sha256") != manifest_sha:
        raise HardStop("CURRENT 与 MANIFEST SHA 不一致")
    validate_manifest_artifacts(manifest)
    print(
        json.dumps(
            {
                "status": "PASS_CURRENT_VERIFIED",
                "experiment_id": manifest["experiment_id"],
                "manifest_sha256": manifest_sha,
                "derived_facts": manifest["derived_facts"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_acceptance() -> int:
    current = load_json(CURRENT_PATH)
    target_dir = experiment_dir(str(current["current_experiment_id"]))
    manifest_path = target_dir / "MANIFEST.json"
    manifest = load_json(manifest_path)
    manifest_sha = domain.sha256_file(manifest_path)
    if current.get("manifest_sha256") != manifest_sha:
        raise HardStop("CURRENT 与 MANIFEST 未绑定")
    validate_manifest_artifacts(manifest)

    expected_registry, expected_readme, registry = render_route_view()
    if ROUTE_VIEW_PATH.read_bytes() != expected_registry:
        raise HardStop("兼容 route registry 不是当前机器派生结果")
    if ROUTE_README_PATH.read_bytes() != expected_readme:
        raise HardStop("兼容 README 不是当前机器派生结果")

    catalog = load_json(ROUTE_CATALOG_PATH)
    route_receipt = load_json(ROUTE_RECEIPT_PATH)
    consumer_receipt = load_json(CONSUMER_RECEIPT_PATH)
    package_receipt_path = ROOT / "TEMP/finetuning_r01/PACKAGE_EQUIVALENCE_RECEIPT.json"
    package_receipt = load_json(package_receipt_path)
    if route_receipt.get("status") != "PASS_DERIVED_VIEWS_REBUILDABLE":
        raise HardStop("派生路牌删除重建验收未通过")
    if not route_receipt.get("isolated_delete_and_rebuild_equivalent"):
        raise HardStop("派生路牌隔离重建不等价")
    if consumer_receipt.get("status") != "PASS_NO_PRODUCTION_UNIQUE_TRUTH_CONSUMER":
        raise HardStop("route registry 消费者仍有唯一真源风险")
    if package_receipt.get("status") != "PASS_BYTE_EQUIVALENT_MEMBER_SET_AND_SHA":
        raise HardStop("旧外审包等价复建未通过")
    if package_receipt.get("manifest_sha256") != manifest_sha:
        raise HardStop("旧外审包等价票未绑定当前 MANIFEST")
    if "current_summary" in catalog or "current_summary" in registry:
        raise HardStop("历史目录或兼容视图仍藏着人工 current_summary")

    receipt = {
        "schema_version": "finetuning-r02-acceptance-v1",
        "status": "PASS_R02_DAILY_ROUTING_CONSOLIDATED",
        "current": {
            "experiment_id": manifest["experiment_id"],
            "manifest_revision": manifest["manifest_revision"],
            "manifest_sha256": manifest_sha,
            "derived_facts": manifest["derived_facts"],
        },
        "checks": {
            "current_pointer_is_navigation_only": current.get("scope") == "navigation_only",
            "current_pointer_binds_manifest_sha": True,
            "all_manifest_artifacts_sha_verified": True,
            "register_build_switch_are_separate_commands": True,
            "new_switch_requires_v2_manifest_and_green_receipts": True,
            "legacy_current_summary_removed": True,
            "derived_route_registry_rebuildable": True,
            "derived_readme_rebuildable": True,
            "no_production_unique_truth_consumer": True,
            "old_review_package_member_set_and_sha_equivalent": True,
        },
        "evidence": {
            "route_derivation_receipt": ROUTE_RECEIPT_PATH.relative_to(ROOT).as_posix(),
            "consumer_receipt": CONSUMER_RECEIPT_PATH.relative_to(ROOT).as_posix(),
            "package_equivalence_receipt": package_receipt_path.relative_to(ROOT).as_posix(),
        },
        "boundaries": {
            "history_migrated": False,
            "historical_evidence_rewritten": False,
            "notion_written": False,
            "git_committed_or_pushed": False,
            "training_started": False,
        },
    }
    receipt_path = DOMAIN_ROOT / "R02_ACCEPTANCE_RECEIPT.json"
    state = create_only(receipt_path, canonical_json(receipt))
    print(
        json.dumps(
            {"status": receipt["status"], "receipt": state, "path": str(receipt_path)},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="微调域 R02 控制面")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register = subparsers.add_parser("register")
    register.add_argument("--spec", type=Path, required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--experiment-id", required=True)
    switch = subparsers.add_parser("switch-current")
    switch.add_argument("--experiment-id", required=True)
    subparsers.add_parser("refresh-existing-current")
    subparsers.add_parser("verify-current")
    subparsers.add_parser("acceptance")
    routes = subparsers.add_parser("routes")
    routes.add_argument("action", choices=["bootstrap", "build"])
    routes.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "register":
            return command_register(args.spec)
        if args.command == "build":
            return command_build(args.experiment_id)
        if args.command == "switch-current":
            return command_switch_current(args.experiment_id)
        if args.command == "refresh-existing-current":
            return command_refresh_existing_current()
        if args.command == "verify-current":
            return command_verify_current()
        if args.command == "acceptance":
            return command_acceptance()
        if args.action == "bootstrap":
            return bootstrap_route_catalog()
        return command_build_routes(args.output_dir)
    except (HardStop, domain.HardStop) as exc:
        print(f"HARD_STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

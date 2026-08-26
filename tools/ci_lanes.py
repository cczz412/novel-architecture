#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "governance/ci_lanes.json"
LOCAL_REGISTRY_PATH = ROOT / "tests/local_evidence_registry.json"
RECEIPT_NAME = "receipt.json"
LANE_IDS = (
    "main-portable",
    "macos-keychain",
    "local-evidence",
    "historical-replay",
)
ALLOWED_KEYCHAIN_TARGETS = (
    "volcengine_ark",
    "qianwen_platform",
    "tencent_tokenhub",
    "ant_ling",
    "deepseek_official",
)
KEYCHAIN_PYTEST_NODEIDS = (
    "tests/test_deepseek_official_config.py::"
    "test_deepseek_official_key_loader_help_is_zero_call",
    "tests/test_deepseek_official_config.py::"
    "test_deepseek_official_loader_denies_run_without_machine_execution_ack",
    "tests/test_provider_channel_configs.py::"
    "test_shared_keychain_loader_is_zero_call_and_names_all_providers",
    "tests/test_provider_channel_configs.py::"
    "test_agent_plan_is_rejected_by_project_keychain_loader",
    "tests/test_provider_channel_configs.py::"
    "test_unknown_provider_is_rejected_before_any_keychain_read",
)
MAIN_PYTEST_ARGV = (
    "uv",
    "run",
    "--locked",
    "pytest",
    "-q",
    "--ci-lane",
    "main-portable",
)
KEYCHAIN_PYTEST_ARGV = (
    "uv",
    "run",
    "--locked",
    "pytest",
    "-q",
    "--ci-lane",
    "macos-keychain",
)
LOCAL_PYTEST_ARGV_PREFIX = (
    "uv",
    "run",
    "--locked",
    "pytest",
    "-q",
    "--ci-lane",
    "local-evidence",
)
HISTORICAL_VALIDATE_ARGV = (
    "uv",
    "run",
    "--locked",
    "python",
    "tools/historical_test_replay.py",
    "validate",
)
HISTORICAL_RUN_ARGV_PREFIX = (
    "uv",
    "run",
    "--locked",
    "python",
    "tools/historical_test_replay.py",
    "run",
)
RECEIPT_STATUSES = {
    "READY",
    "NOT_DISPATCHED",
    "DISPATCHED",
    "PASSED",
    "FAILED",
    "HARD_STOP",
}
SHA_40 = re.compile(r"^[0-9a-f]{40}$")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
EXIT_NOT_DISPATCHED = 3
EXIT_HARD_STOP = 4
COMMAND_LABELS = {
    "main-portable": ["pytest-main-portable-v1"],
    "macos-keychain": ["keychain-presence-check-v1", "pytest-macos-keychain-v1"],
    "local-evidence": ["pytest-local-evidence-v1"],
    "historical-replay": [
        "historical-replay-validate-v1",
        "historical-replay-run-v1",
    ],
}


class LaneError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LaneError(f"无法读取测试专线登记：{path.name}") from exc
    if not isinstance(value, dict):
        raise LaneError(f"测试专线登记顶层必须是对象：{path.name}")
    return value


def load_contract() -> dict[str, Any]:
    contract = _load_json(CONTRACT_PATH)
    if contract.get("schema_version") != "ci-test-lanes-v1":
        raise LaneError("测试专线合同版本不受支持")
    lanes = contract.get("lanes")
    if not isinstance(lanes, dict) or set(lanes) != set(LANE_IDS):
        raise LaneError("测试专线必须恰好登记四条固定路线")
    for lane_id, lane in lanes.items():
        if not isinstance(lane, dict) or lane.get("lane_id") != lane_id:
            raise LaneError(f"测试专线编号不一致：{lane_id}")
        if lane.get("network") is not False or lane.get("model_api") is not False:
            raise LaneError(f"测试专线不得开放网络或模型调用：{lane_id}")
        boundary = lane.get("receipt_boundary")
        if not isinstance(boundary, dict) or any(
            boundary.get(key) is not False
            for key in (
                "stores_subprocess_output",
                "stores_absolute_paths",
                "stores_credentials_or_material_text",
            )
        ):
            raise LaneError(f"测试专线回执边界不完整：{lane_id}")

    main = lanes["main-portable"]
    if main.get("trigger") != "push_main_or_explicit_run" or main.get(
        "platform"
    ) != "linux_or_macos":
        raise LaneError("main 可移植测试线触发或平台合同漂移")
    main_execution = main.get("execution", {})
    if main_execution.get("argv") != list(MAIN_PYTEST_ARGV):
        raise LaneError("main 可移植测试线命令漂移")
    if main_execution.get("network_guard") != "force_for_all_selected_nodes":
        raise LaneError("main 可移植测试线没有强制全节点断网")

    keychain = lanes["macos-keychain"]
    if keychain.get("allowed_keychain_targets") != list(ALLOWED_KEYCHAIN_TARGETS):
        raise LaneError("macOS Keychain 允许目标漂移")
    if keychain.get("pytest_nodeids") != list(KEYCHAIN_PYTEST_NODEIDS):
        raise LaneError("macOS Keychain 精确测试节点漂移")
    if keychain.get("execution", {}).get("argv") != list(KEYCHAIN_PYTEST_ARGV):
        raise LaneError("macOS Keychain 测试命令漂移")

    local = lanes["local-evidence"].get("execution", {})
    if (
        local.get("registry") != "tests/local_evidence_registry.json"
        or local.get("argv_prefix") != list(LOCAL_PYTEST_ARGV_PREFIX)
        or local.get("group_argument") != "--local-evidence-group"
    ):
        raise LaneError("本机材料测试线命令或登记入口漂移")

    historical = lanes["historical-replay"].get("execution", {})
    if historical.get("validate_argv") != list(HISTORICAL_VALIDATE_ARGV) or (
        historical.get("run_argv_prefix") != list(HISTORICAL_RUN_ARGV_PREFIX)
    ):
        raise LaneError("历史回放测试线没有钉住既有隔离工具")
    return contract


def _safe_repo_relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise LaneError("本机材料登记含无效路径")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise LaneError("本机材料只接受规范的仓库相对路径")
    if ".git" in path.parts:
        raise LaneError("本机材料路径不能进入 .git")
    return path.as_posix()


def _load_local_groups() -> dict[str, dict[str, Any]]:
    registry = _load_json(LOCAL_REGISTRY_PATH)
    if registry.get("schema_version") != "pytest-local-evidence-v1":
        raise LaneError("本机证据登记版本不受支持")
    rows = registry.get("groups")
    if not isinstance(rows, list) or not rows:
        raise LaneError("本机证据登记没有分组")
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise LaneError("本机证据分组必须是对象")
        group_id = row.get("group_id")
        required = row.get("required_paths")
        if not isinstance(group_id, str) or not group_id or group_id in groups:
            raise LaneError("本机证据分组编号缺失或重复")
        if not isinstance(required, list) or not required:
            raise LaneError(f"本机证据分组没有登记材料：{group_id}")
        groups[group_id] = {
            **row,
            "required_paths": [_safe_repo_relative(path) for path in required],
        }
    return groups


def _head_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    if completed.returncode != 0 or SHA_40.fullmatch(value) is None:
        raise LaneError("无法读取当前提交，拒绝生成不完整回执")
    return value


def _new_receipt_dir(path: Path) -> Path:
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    try:
        path.mkdir(parents=False, exist_ok=False)
    except FileExistsError as exc:
        raise LaneError("回执目录已存在；每次运行必须使用新目录") from exc
    except OSError as exc:
        raise LaneError("无法新建回执目录") from exc
    return path


def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    if payload.get("status") not in RECEIPT_STATUSES:
        raise LaneError("回执状态不受支持")
    temporary = path.with_name(f".{path.name}.tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(temporary, flags, 0o644)
    try:
        os.write(descriptor, data.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


def _base_receipt(lane: str, head_sha: str) -> dict[str, Any]:
    started_at = _utc_now()
    return {
        "schema_version": "ci-test-lane-receipt-v1",
        "lane": lane,
        "status": "READY",
        "head_sha": head_sha,
        "started_at": started_at,
        "finished_at": None,
        "exit_code": None,
        "command_labels": COMMAND_LABELS[lane],
        "network": False,
        "model_api": False,
        "subprocess_output_saved": False,
    }


def _finish(
    receipt_path: Path,
    receipt: dict[str, Any],
    *,
    status: str,
    exit_code: int,
    detail: dict[str, Any] | None = None,
) -> int:
    receipt.update(
        {
            "status": status,
            "exit_code": exit_code,
            "finished_at": _utc_now(),
        }
    )
    if detail:
        receipt.update(detail)
    _write_receipt(receipt_path, receipt)
    return exit_code


def _run_forwarded(argv: list[str], *, env: dict[str, str] | None = None) -> int:
    try:
        return subprocess.run(argv, cwd=ROOT, env=env, check=False).returncode
    except OSError as exc:
        raise LaneError("固定测试命令无法启动") from exc


def _run_main(receipt_path: Path, receipt: dict[str, Any]) -> int:
    receipt["status"] = "DISPATCHED"
    _write_receipt(receipt_path, receipt)
    code = _run_forwarded(list(MAIN_PYTEST_ARGV))
    return _finish(
        receipt_path,
        receipt,
        status="PASSED" if code == 0 else "FAILED",
        exit_code=code,
    )


def _keychain_check_argv(target: str) -> list[str]:
    if target == "deepseek_official":
        return [str(ROOT / "tools/deepseek_official_key.sh"), "check"]
    return [str(ROOT / "tools/provider_keychain.sh"), "check", target]


def _run_keychain(
    receipt_path: Path,
    receipt: dict[str, Any],
    targets: list[str],
) -> int:
    normalized = list(dict.fromkeys(targets))
    if platform.system() != "Darwin":
        return _finish(
            receipt_path,
            receipt,
            status="NOT_DISPATCHED",
            exit_code=EXIT_NOT_DISPATCHED,
            detail={"reason": "当前平台不是 macOS"},
        )
    if not normalized:
        return _finish(
            receipt_path,
            receipt,
            status="NOT_DISPATCHED",
            exit_code=EXIT_NOT_DISPATCHED,
            detail={"reason": "没有点名钥匙串目标"},
        )
    known = [target for target in normalized if target in ALLOWED_KEYCHAIN_TARGETS]
    unknown_count = len(normalized) - len(known)
    receipt["keychain_targets"] = known
    if unknown_count:
        return _finish(
            receipt_path,
            receipt,
            status="NOT_DISPATCHED",
            exit_code=EXIT_NOT_DISPATCHED,
            detail={
                "reason": "钥匙串目标不在允许清单",
                "unknown_target_count": unknown_count,
            },
        )
    missing: list[str] = []
    for target in known:
        try:
            completed = subprocess.run(
                _keychain_check_argv(target),
                cwd=ROOT,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            missing.append(target)
            continue
        if completed.returncode != 0:
            missing.append(target)
    if missing:
        return _finish(
            receipt_path,
            receipt,
            status="NOT_DISPATCHED",
            exit_code=EXIT_NOT_DISPATCHED,
            detail={"reason": "点名的钥匙串凭据不完整", "missing_targets": missing},
        )
    receipt["status"] = "DISPATCHED"
    _write_receipt(receipt_path, receipt)
    code = _run_forwarded(list(KEYCHAIN_PYTEST_ARGV))
    return _finish(
        receipt_path,
        receipt,
        status="PASSED" if code == 0 else "FAILED",
        exit_code=code,
    )


def _selected_local_groups(requested: list[str]) -> tuple[list[str], int]:
    groups = _load_local_groups()
    selected = list(dict.fromkeys(requested)) if requested else list(groups)
    known = [group_id for group_id in selected if group_id in groups]
    return known, len(selected) - len(known)


def _run_local(
    receipt_path: Path,
    receipt: dict[str, Any],
    requested: list[str],
) -> int:
    groups = _load_local_groups()
    selected, unknown_count = _selected_local_groups(requested)
    receipt["group_ids"] = selected
    if unknown_count:
        return _finish(
            receipt_path,
            receipt,
            status="NOT_DISPATCHED",
            exit_code=EXIT_NOT_DISPATCHED,
            detail={
                "reason": "本机证据分组未登记",
                "unknown_group_count": unknown_count,
            },
        )
    missing = sorted(
        {
            relative
            for group_id in selected
            for relative in groups[group_id]["required_paths"]
            if not (ROOT / relative).is_file()
        }
    )
    if missing:
        return _finish(
            receipt_path,
            receipt,
            status="NOT_DISPATCHED",
            exit_code=EXIT_NOT_DISPATCHED,
            detail={"reason": "登记的本机材料不完整", "missing_paths": missing},
        )
    argv = list(LOCAL_PYTEST_ARGV_PREFIX)
    for group_id in selected:
        argv.extend(["--local-evidence-group", group_id])
    environment = os.environ.copy()
    environment["NOVEL_RUN_LOCAL_EVIDENCE_TESTS"] = "1"
    receipt["status"] = "DISPATCHED"
    _write_receipt(receipt_path, receipt)
    code = _run_forwarded(argv, env=environment)
    return _finish(
        receipt_path,
        receipt,
        status="PASSED" if code == 0 else "FAILED",
        exit_code=code,
    )


def _run_historical(
    receipt_path: Path,
    receipt: dict[str, Any],
    *,
    commit: str | None,
    run_id: str | None,
) -> int:
    if commit is None or SHA_40.fullmatch(commit) is None:
        return _finish(
            receipt_path,
            receipt,
            status="HARD_STOP",
            exit_code=EXIT_HARD_STOP,
            detail={"reason": "历史回放要求完整 40 位小写提交号"},
        )
    if run_id is None or RUN_ID.fullmatch(run_id) is None:
        return _finish(
            receipt_path,
            receipt,
            status="HARD_STOP",
            exit_code=EXIT_HARD_STOP,
            detail={"reason": "历史回放要求新的合法运行号"},
        )
    validate_argv = list(HISTORICAL_VALIDATE_ARGV)
    receipt["status"] = "DISPATCHED"
    receipt["historical_commit"] = commit
    receipt["historical_run_id"] = run_id
    _write_receipt(receipt_path, receipt)
    validate_code = _run_forwarded(validate_argv)
    if validate_code != 0:
        return _finish(
            receipt_path,
            receipt,
            status="HARD_STOP",
            exit_code=validate_code,
            detail={"reason": "历史回放登记或材料校验失败"},
        )
    run_argv = [
        *HISTORICAL_RUN_ARGV_PREFIX,
        "--commit",
        commit,
        "--run-id",
        run_id,
    ]
    _write_receipt(receipt_path, receipt)
    run_code = _run_forwarded(run_argv)
    return _finish(
        receipt_path,
        receipt,
        status="PASSED" if run_code == 0 else "FAILED",
        exit_code=run_code,
    )


def check_lane(args: argparse.Namespace) -> int:
    load_contract()
    payload: dict[str, Any] = {
        "schema_version": "ci-test-lane-check-v1",
        "lane": args.lane,
        "status": "READY",
        "executes_commands": False,
        "network": False,
        "model_api": False,
    }
    if args.lane == "macos-keychain":
        targets = list(dict.fromkeys(args.keychain_target))
        known = [target for target in targets if target in ALLOWED_KEYCHAIN_TARGETS]
        unknown_count = len(targets) - len(known)
        if platform.system() != "Darwin" or not targets or unknown_count:
            payload["status"] = "NOT_DISPATCHED"
        payload["keychain_targets"] = known
        if unknown_count:
            payload["unknown_target_count"] = unknown_count
    elif args.lane == "local-evidence":
        groups = _load_local_groups()
        selected, unknown_count = _selected_local_groups(args.group)
        payload["group_ids"] = selected
        if unknown_count:
            payload["status"] = "NOT_DISPATCHED"
            payload["unknown_group_count"] = unknown_count
        else:
            missing = sorted(
                {
                    relative
                    for group_id in selected
                    for relative in groups[group_id]["required_paths"]
                    if not (ROOT / relative).is_file()
                }
            )
            if missing:
                payload["status"] = "NOT_DISPATCHED"
                payload["missing_paths"] = missing
    elif args.lane == "historical-replay":
        if (
            args.commit is None
            or SHA_40.fullmatch(args.commit) is None
            or args.run_id is None
            or RUN_ID.fullmatch(args.run_id) is None
        ):
            payload["status"] = "HARD_STOP"
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if payload["status"] == "READY":
        return 0
    if payload["status"] == "NOT_DISPATCHED":
        return EXIT_NOT_DISPATCHED
    return EXIT_HARD_STOP


def run_lane(args: argparse.Namespace) -> int:
    load_contract()
    receipt_dir = _new_receipt_dir(args.receipt_dir)
    receipt_path = receipt_dir / RECEIPT_NAME
    receipt = _base_receipt(args.lane, "UNAVAILABLE")
    _write_receipt(receipt_path, receipt)
    try:
        receipt["head_sha"] = _head_sha()
        _write_receipt(receipt_path, receipt)
    except LaneError as exc:
        return _finish(
            receipt_path,
            receipt,
            status="HARD_STOP",
            exit_code=EXIT_HARD_STOP,
            detail={"reason": str(exc)},
        )
    _write_receipt(receipt_path, receipt)
    try:
        if args.lane == "main-portable":
            return _run_main(receipt_path, receipt)
        if args.lane == "macos-keychain":
            return _run_keychain(receipt_path, receipt, args.keychain_target)
        if args.lane == "local-evidence":
            return _run_local(receipt_path, receipt, args.group)
        if args.lane == "historical-replay":
            return _run_historical(
                receipt_path,
                receipt,
                commit=args.commit,
                run_id=args.run_id,
            )
        raise AssertionError("argparse accepted an unknown lane")
    except LaneError as exc:
        return _finish(
            receipt_path,
            receipt,
            status="HARD_STOP",
            exit_code=EXIT_HARD_STOP,
            detail={"reason": str(exc)},
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按固定合同检查或运行四条测试专线。")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "run"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--lane", required=True, choices=LANE_IDS)
        subparser.add_argument("--keychain-target", action="append", default=[])
        subparser.add_argument("--group", action="append", default=[])
        subparser.add_argument("--commit")
        subparser.add_argument("--run-id")
        if command == "run":
            subparser.add_argument("--receipt-dir", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            return check_lane(args)
        return run_lane(args)
    except LaneError as exc:
        print(f"测试专线拒绝执行：{exc}", file=sys.stderr)
        return EXIT_HARD_STOP


if __name__ == "__main__":
    raise SystemExit(main())

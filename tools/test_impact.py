"""按变更影响选择测试；未知或跨合同变更一律保守升级。"""

from __future__ import annotations

import argparse
import fnmatch
import json
import shlex
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from pipeline_common.artifacts import read_json, write_json_atomic  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "governance/test_policy.json"
DEFAULT_REGISTRY = ROOT / "governance/module_registry.json"
SPEC_CONTRACT = "pipeline-change-spec-v1"
PLAN_CONTRACT = "pipeline-test-plan-v1"
PORTABLE_FULL_CHAIN_COMMAND = (
    'cd "$(git rev-parse --show-toplevel)" && uv run --locked pytest -q'
)
LOCKED_COMMAND_PREFIX = ["uv", "run", "--locked"]
PORTABLE_FULL_CHAIN_ARGV = [*LOCKED_COMMAND_PREFIX, "pytest", "-q"]
NON_DOWNGRADABLE_PLANNER_PATHS = frozenset(
    {
        "governance/test_policy.json",
        "tools/test_impact.py",
    }
)


class TestImpactError(RuntimeError):
    """变更说明或测试纪律无法安全判定。"""


def _locked_command_argv(command: str, label: str) -> list[str]:
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise TestImpactError(f"{label} 不是有效命令") from exc
    if argv[:3] != LOCKED_COMMAND_PREFIX:
        raise TestImpactError(f"{label} 必须以 uv run --locked 开头")
    if any(value in {"&&", "||", ";", "|", ">", "<"} for value in argv):
        raise TestImpactError(f"{label} 不能包含 shell 控制符")
    return argv


def _execution_step(step_id: str, argv: list[str]) -> dict[str, Any]:
    if argv[:3] != LOCKED_COMMAND_PREFIX:
        raise TestImpactError(f"执行步骤 {step_id} 绕开了 uv run --locked")
    return {
        "step_id": step_id,
        "argv": list(argv),
        "cwd": "repo_root",
    }


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TestImpactError(f"{label} 必须是对象")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TestImpactError(f"{label} 必须是数组")
    return value


def _normalize_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TestImpactError("changed_paths 只能放非空仓内相对路径")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise TestImpactError(f"变更路径必须留在仓内：{value}")
    return path.as_posix()


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    raw = _mapping(read_json(path), "测试纪律")
    if raw.get("schema_version") != "pipeline-test-policy-v1":
        raise TestImpactError("测试纪律版本不符")
    if raw.get("full_chain_command") != PORTABLE_FULL_CHAIN_COMMAND:
        raise TestImpactError(
            "full_chain_command 必须从当前 Git 仓库根运行，不能写死本机路径"
        )
    if not _list(raw.get("path_rules"), "path_rules"):
        raise TestImpactError("测试纪律缺 path_rules")
    lint_argv = _locked_command_argv(str(raw.get("lint_command", "")), "lint_command")
    if lint_argv != [*LOCKED_COMMAND_PREFIX, "ruff", "check"]:
        raise TestImpactError("lint_command 必须固定为 uv run --locked ruff check")
    for index, command in enumerate(
        _list(raw.get("documentation_commands"), "documentation_commands"), start=1
    ):
        _locked_command_argv(str(command), f"documentation_commands[{index}]")
    return raw


def _available_modules(registry: Mapping[str, Any]) -> set[str]:
    return {
        str(row["module_id"])
        for row in _list(registry.get("modules"), "module_registry.modules")
        if isinstance(row, dict) and row.get("status") == "可用"
    }


def _consumers(registry: Mapping[str, Any], module_ids: Iterable[str]) -> set[str]:
    wanted = set(module_ids)
    result: set[str] = set()
    for value in _list(registry.get("modules"), "module_registry.modules"):
        if not isinstance(value, dict) or value.get("module_id") not in wanted:
            continue
        result.update(str(item) for item in value.get("consumers", []) if isinstance(item, str))
    return result


def _match_rules(path: str, rules: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rules if fnmatch.fnmatchcase(path, str(row.get("pattern", "")))]


def build_plan(
    spec_raw: Any,
    *,
    policy: Mapping[str, Any] | None = None,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    spec = _mapping(spec_raw, "变更说明")
    if spec.get("contract_version") != SPEC_CONTRACT:
        raise TestImpactError(f"变更说明合同必须是 {SPEC_CONTRACT}")
    change_id = str(spec.get("change_id") or "").strip()
    if not change_id:
        raise TestImpactError("change_id 不能为空")
    paths = sorted(
        set(
            _normalize_path(value)
            for value in _list(spec.get("changed_paths"), "changed_paths")
        )
    )
    if not paths:
        raise TestImpactError("changed_paths 不能为空")
    if "head_paths" in spec:
        head_paths = sorted(
            set(
                _normalize_path(value)
                for value in _list(spec.get("head_paths"), "head_paths")
            )
        )
        paths_not_in_change = sorted(set(head_paths) - set(paths))
        if paths_not_in_change:
            raise TestImpactError(
                "head_paths 只能放本次变更后仍存在的路径："
                + ", ".join(paths_not_in_change)
            )
    else:
        # 旧版变更说明没有文件状态；保持原有行为。PR 门禁会显式传 head_paths，
        # 因而能把删除路径留在影响判断里，同时不把它交给 Ruff。
        head_paths = list(paths)
    active_policy = dict(policy or load_policy())
    active_registry = dict(registry or _mapping(read_json(DEFAULT_REGISTRY), "module_registry"))
    flags = {str(value) for value in _list(spec.get("flags", []), "flags")}
    contract_changes = _list(spec.get("contract_changes", []), "contract_changes")

    full_reasons: list[str] = []
    for path in sorted(set(paths).intersection(NON_DOWNGRADABLE_PLANNER_PATHS)):
        full_reasons.append(f"{path} 属于不可降级的选测核心文件")
    configured_full_flags = set(str(value) for value in active_policy["full_chain_flags"])
    for flag in sorted(flags.intersection(configured_full_flags)):
        full_reasons.append(f"命中全链触发旗标：{flag}")
    for value in contract_changes:
        row = _mapping(value, "contract_change")
        kind = str(row.get("kind") or "").strip()
        if kind not in {"none", "additive_isolated", "compatible_minor", "incompatible", "major"}:
            raise TestImpactError(f"合同变化类型不受支持：{kind}")
        if kind in {"compatible_minor", "incompatible", "major"}:
            full_reasons.append(
                f"{row.get('module_id', 'unknown')} 现役输入／输出合同变化：{kind}"
            )

    affected: set[str] = set()
    selected_tests: set[str] = set()
    matched_paths: dict[str, list[str]] = {}
    unknown: list[str] = []
    docs_only = True
    for path in paths:
        matches = _match_rules(path, active_policy["path_rules"])
        if not matches:
            unknown.append(path)
            docs_only = False
            continue
        matched_paths[path] = [str(row.get("name")) for row in matches]
        for row in matches:
            affected.update(str(value) for value in row.get("modules", []))
            selected_tests.update(str(value) for value in row.get("tests", []))
            if row.get("full_chain"):
                full_reasons.append(f"{path} 命中全链路径：{row.get('name')}")
            if not row.get("documentation_only", False):
                docs_only = False
    if unknown and active_policy.get("unknown_path_full_chain", True):
        full_reasons.append(f"无法证明影响范围的路径：{', '.join(unknown)}")

    available = _available_modules(active_registry)
    downstream = _consumers(active_registry, affected)
    for module_id in downstream:
        selected_tests.update(active_policy.get("module_tests", {}).get(module_id, []))
    for module_id in affected:
        selected_tests.update(active_policy.get("module_tests", {}).get(module_id, []))

    full_chain = bool(full_reasons)
    python_paths = [path for path in head_paths if path.endswith(".py")]
    lint_argv = _locked_command_argv(
        str(active_policy["lint_command"]), "lint_command"
    )
    if python_paths:
        lint_argv.extend(["--", *python_paths])
        lint_command = shlex.join(lint_argv)
    else:
        lint_command = ""
        lint_argv = []
    if full_chain:
        scope = "full_chain"
        commands = [str(active_policy["full_chain_command"])]
        execution_steps = [
            _execution_step("pytest-full", PORTABLE_FULL_CHAIN_ARGV)
        ]
        if lint_command:
            commands.append(lint_command)
            execution_steps.append(_execution_step("ruff", lint_argv))
        exempt: list[str] = []
    elif docs_only:
        scope = "documentation_only"
        commands = [str(value) for value in active_policy["documentation_commands"]]
        execution_steps = [
            _execution_step(
                f"documentation-{index}",
                _locked_command_argv(command, f"documentation_commands[{index}]"),
            )
            for index, command in enumerate(commands, start=1)
        ]
        exempt = sorted(available)
    else:
        scope = "targeted"
        if not selected_tests:
            full_chain = True
            scope = "full_chain"
            full_reasons.append("局部变更没有登记测试，无法证明安全范围")
            commands = [str(active_policy["full_chain_command"])]
            execution_steps = [
                _execution_step("pytest-full", PORTABLE_FULL_CHAIN_ARGV)
            ]
            if lint_command:
                commands.append(lint_command)
                execution_steps.append(_execution_step("ruff", lint_argv))
            exempt = []
        else:
            pytest_argv = [
                *LOCKED_COMMAND_PREFIX,
                "pytest",
                "-q",
                *sorted(selected_tests),
            ]
            commands = [shlex.join(pytest_argv)]
            execution_steps = [_execution_step("pytest-targeted", pytest_argv)]
            if lint_command:
                commands.append(lint_command)
                execution_steps.append(_execution_step("ruff", lint_argv))
            exempt = sorted(available - affected - downstream)

    return {
        "contract_version": PLAN_CONTRACT,
        "change_id": change_id,
        "scope": scope,
        "full_chain": full_chain,
        "changed_paths": paths,
        "head_paths": head_paths,
        "linted_python_paths": python_paths,
        "matched_paths": matched_paths,
        "unknown_paths": unknown,
        "affected_modules": sorted(affected),
        "direct_consumers": sorted(downstream),
        "exempt_available_modules": exempt,
        "selected_tests": sorted(selected_tests),
        "commands": commands,
        "execution_steps": execution_steps,
        "full_chain_reasons": full_reasons,
        "discipline": {
            "available_unchanged_contract": "局部验票后免全链重验",
            "existing_contract_change": "触发全链回归",
            "major_or_unknown_change": "触发全链回归",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按模块与合同影响生成测试计划")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = build_plan(
        read_json(args.spec),
        policy=load_policy(args.policy),
        registry=_mapping(read_json(args.registry), "module_registry"),
    )
    if args.output:
        write_json_atomic(args.output, plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

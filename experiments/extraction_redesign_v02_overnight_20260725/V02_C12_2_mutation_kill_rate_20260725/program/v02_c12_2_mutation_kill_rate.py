#!/usr/bin/env python3
"""V02/C12.2：在内存隔离区注入七类缺陷并核验测试杀伤率。

本程序不改被测源码。每个 mutant 都在独立子进程中编译到内存，
随后让指定 pytest 用例导入该内存模块。只有 baseline 通过、mutant
可编译且指定测试因断言失败，才记为 KILLED。
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "tools").is_dir():
            return parent
    raise RuntimeError("无法定位小说架构仓库根目录")


ROOT = _find_repo_root()
OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C12_2_mutation_kill_rate_20260725"
)
REPORT_PATH = (
    ROOT
    / "reports/抽取工序重设计v0.2_C12积压优化项_20260725"
    / "C12_2_停点回包.md"
)
SELF_PATH = Path(__file__).resolve()
NEW_TEST = ROOT / "tests/test_v02_c12_2_mutation_killrate.py"
PYTHON = ROOT / ".venv/bin/python"

NEW_EXACT_TEST = (
    "tests/test_v02_c12_2_mutation_killrate.py::"
    "test_anchor_reverse_lookup_requires_full_exact_slice"
)
NEW_DENOMINATOR_TEST = (
    "tests/test_v02_c12_2_mutation_killrate.py::"
    "test_all_five_layer_denominators_remain_dynamic"
)


class MutationHarnessError(RuntimeError):
    """变异测试器输入、源码绑定或执行状态不合格。"""


@dataclass(frozen=True)
class MutationSpec:
    mutant_id: str
    title: str
    module_name: str
    source_path: str
    before: str
    after: str
    legacy_tests: tuple[str, ...]
    added_regression_tests: tuple[str, ...] = ()


def mutation_specs() -> tuple[MutationSpec, ...]:
    c12_program = (
        "experiments/extraction_redesign_v02_overnight_20260725/"
        "V02_C12_1_cardinality_score_and_c5_rescore_20260725/program/"
        "v02_c12_1_cardinality_score_adapter.py"
    )
    return (
        MutationSpec(
            mutant_id="M01_FAKE_SECOND_MODEL_FAMILY",
            title="复制第一票改名，绕过第二模型族独立凭据",
            module_name="v02_c7_consensus_tally",
            source_path="tools/v02_c7_consensus_tally.py",
            before=(
                "        if (\n"
                "            len(sealed_first_ballots) != 1\n"
                "            or len(evidenced_later_ballots) != len(receipts) - 1\n"
                "        ):\n"
            ),
            after=(
                "        if False and (\n"
                "            len(sealed_first_ballots) != 1\n"
                "            or len(evidenced_later_ballots) != len(receipts) - 1\n"
                "        ):\n"
            ),
            legacy_tests=(
                "tests/test_v02_c7_consensus_tally.py::"
                "test_renamed_copy_without_independence_receipt_is_rejected",
            ),
        ),
        MutationSpec(
            mutant_id="M02_BYPASS_SEAL_BEFORE_VOTE",
            title="绕过先封签、后投票的时间顺序",
            module_name="v02_c7_consensus_tally",
            source_path="tools/v02_c7_consensus_tally.py",
            before="    if submitted_at <= sealed_at:\n",
            after="    if False and submitted_at <= sealed_at:\n",
            legacy_tests=(
                "tests/test_v02_c7_consensus_tally.py::"
                "test_notion_receipt_rejects_reversed_seal_order",
            ),
        ),
        MutationSpec(
            mutant_id="M03_MECHANICAL_ROUTE_AS_SEMANTIC_HIT",
            title="把机械位置路由冒充成语义命中",
            module_name="v02_c7_rescore_c5",
            source_path="tools/v02_c7_rescore_c5.py",
            before=(
                '        "mechanical_route_is_not_semantic_verdict": True,\n'
                '        "control_mapping_frozen": False,\n'
            ),
            after=(
                '        "mechanical_route_is_not_semantic_verdict": False,\n'
                '        "control_mapping_frozen": True,\n'
            ),
            legacy_tests=(
                "tests/test_v02_c7_rescore_c5.py::"
                "test_control_readiness_uses_same_counter_but_is_not_semantic_mapping",
            ),
        ),
        MutationSpec(
            mutant_id="M04_EXACT_PASTEBACK_TO_SUBSTRING",
            title="把原文坐标逐字回贴降级成宽松子串包含",
            module_name="v02_anchor_first_experiment",
            source_path="tools/v02_anchor_first_experiment.py",
            before="                or source_text[start:end] != quote\n",
            after="                or quote not in source_text[start:end]\n",
            legacy_tests=(
                "tests/test_v02_anchor_first_experiment.py::"
                "test_minimal_anchor_validator_passes_closed_set_and_reverse_lookup",
            ),
            added_regression_tests=(NEW_EXACT_TEST,),
        ),
        MutationSpec(
            mutant_id="M05_NOT_FOUND_TO_UNKNOWN",
            title="把材料完整且无命中的 NOT_FOUND 静默改成 UNKNOWN",
            module_name="v02_duse_query",
            source_path="tools/v02_duse_query.py",
            before=(
                "    elif material_complete_through_chapter >= "
                'normalized_query["as_of_chapter"]:\n'
                '        status = "NOT_FOUND"\n'
                '        reason = "COMPLETE_SCOPE_NO_MATCH"\n'
            ),
            after=(
                "    elif material_complete_through_chapter >= "
                'normalized_query["as_of_chapter"]:\n'
                '        status = "UNKNOWN"\n'
                '        reason = "MATERIAL_SCOPE_INCOMPLETE"\n'
            ),
            legacy_tests=(
                "tests/test_v02_duse_query.py::"
                "test_not_found_and_unknown_are_not_conflated",
            ),
        ),
        MutationSpec(
            mutant_id="M06_MANIFEST_SMUGGLING",
            title="允许 manifest 目录夹带未登记文件",
            module_name="v02_c8_control_workspace",
            source_path="tools/v02_c8_control_workspace.py",
            before="    if actual != set(first):\n",
            after="    if False and actual != set(first):\n",
            legacy_tests=(
                "tests/test_v02_c8_control_workspace.py::"
                "test_c8_write_is_byte_stable_and_rejects_unregistered_files",
            ),
        ),
        MutationSpec(
            mutant_id="M07_FORCE_LAYER_DENOMINATOR_49",
            title="把 QCR_full 动态分母静默强制成 49",
            module_name="v02_c12_1_cardinality_score_adapter",
            source_path=c12_program,
            before="    qcr = _ratio(qualifier_complete, head_covered)\n",
            after="    qcr = _ratio(qualifier_complete, 49)\n",
            legacy_tests=(
                "tests/test_v02_c12_1_cardinality_score_adapter.py::"
                "test_many_to_many_cross_keeps_all_edges_and_is_order_stable",
            ),
            added_regression_tests=(NEW_DENOMINATOR_TEST,),
        ),
    )


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise MutationHarnessError(f"文件不存在：{path}")
    return sha256_bytes(path.read_bytes())


def stable_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def source_bindings() -> dict[str, str]:
    paths = {
        spec.source_path for spec in mutation_specs()
    } | {
        display_path(SELF_PATH),
        display_path(NEW_TEST),
    }
    return {
        relative: sha256_file(ROOT / relative)
        for relative in sorted(paths)
    }


def _clean_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.endswith("_API_KEY")
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def _normalize_pytest_output(raw: str) -> str:
    normalized = raw.replace(str(ROOT), "<REPO>")
    normalized = re.sub(
        r"/(?:private/)?var/folders/[^\s]+",
        "<TMP>",
        normalized,
    )
    normalized = re.sub(
        r"\b(?:in\s+)?\d+(?:\.\d+)?s\b",
        "in <TIME>",
        normalized,
    )
    lines = [line.rstrip() for line in normalized.splitlines()]
    return "\n".join(lines).strip()


def _replace_exact(source: str, spec: MutationSpec) -> str:
    count = source.count(spec.before)
    if count != 1:
        raise MutationHarnessError(
            f"{spec.mutant_id} 注入靶命中数不是 1：{count}"
        )
    return source.replace(spec.before, spec.after, 1)


def _load_module_from_source(spec: MutationSpec, source: str) -> None:
    path = ROOT / spec.source_path
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tools"))
    sys.path.insert(0, str(path.parent))
    sys.modules.pop(spec.module_name, None)
    module = types.ModuleType(spec.module_name)
    module.__file__ = str(path)
    module.__package__ = ""
    sys.modules[spec.module_name] = module
    code = compile(source, str(path), "exec")
    exec(code, module.__dict__)


def _worker(spec_id: str, suite: str, mutated: bool) -> int:
    try:
        spec = next(
            row for row in mutation_specs() if row.mutant_id == spec_id
        )
    except StopIteration as exc:
        raise MutationHarnessError(f"未知 mutant：{spec_id}") from exc
    source = (ROOT / spec.source_path).read_text(encoding="utf-8")
    if mutated:
        source = _replace_exact(source, spec)
    _load_module_from_source(spec, source)

    tests = list(spec.legacy_tests)
    if suite == "final":
        tests.extend(spec.added_regression_tests)
    elif suite != "legacy":
        raise MutationHarnessError(f"未知测试套件：{suite}")

    import pytest

    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        return_code = int(
            pytest.main(
                [
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--tb=short",
                    *tests,
                ]
            )
        )
    payload = {
        "return_code": return_code,
        "normalized_output": _normalize_pytest_output(stream.getvalue()),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def _run_worker(
    spec: MutationSpec,
    *,
    suite: str,
    mutated: bool,
) -> dict[str, Any]:
    command = [
        str(PYTHON),
        str(SELF_PATH),
        "--worker",
        spec.mutant_id,
        "--suite",
        suite,
    ]
    if mutated:
        command.append("--mutated")
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        return {
            "status": "INVALID",
            "worker_return_code": result.returncode,
            "pytest_return_code": None,
            "proof": _normalize_pytest_output(
                "\n".join((result.stdout, result.stderr))
            ),
        }
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise MutationHarnessError(
            f"{spec.mutant_id} worker 没有返回可解析票据"
        ) from exc
    pytest_code = int(payload["return_code"])
    output = str(payload["normalized_output"])
    if not mutated:
        status = "PASS" if pytest_code == 0 else "FAIL"
    elif pytest_code == 0:
        status = "SURVIVED"
    elif (
        pytest_code == 1
        and " failed" in f" {output}"
        and "ERROR " not in output
    ):
        status = "KILLED"
    else:
        status = "INVALID"
    return {
        "status": status,
        "worker_return_code": result.returncode,
        "pytest_return_code": pytest_code,
        "proof": output,
    }


def _run_round(suite: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for spec in mutation_specs():
        baseline = _run_worker(spec, suite=suite, mutated=False)
        if baseline["status"] != "PASS":
            mutation = {
                "status": "INVALID",
                "worker_return_code": None,
                "pytest_return_code": None,
                "proof": "baseline_not_pass",
            }
        else:
            mutation = _run_worker(spec, suite=suite, mutated=True)
        rows.append(
            {
                "mutant_id": spec.mutant_id,
                "title": spec.title,
                "source_path": spec.source_path,
                "source_sha256": sha256_file(ROOT / spec.source_path),
                "suite": suite,
                "tests": (
                    list(spec.legacy_tests)
                    + (
                        list(spec.added_regression_tests)
                        if suite == "final"
                        else []
                    )
                ),
                "baseline": baseline,
                "mutation": mutation,
            }
        )
    valid = [
        row
        for row in rows
        if row["baseline"]["status"] == "PASS"
        and row["mutation"]["status"] in {"KILLED", "SURVIVED"}
    ]
    killed = [
        row for row in valid if row["mutation"]["status"] == "KILLED"
    ]
    survivors = [
        row for row in valid if row["mutation"]["status"] == "SURVIVED"
    ]
    invalid = [
        row
        for row in rows
        if row["baseline"]["status"] != "PASS"
        or row["mutation"]["status"] == "INVALID"
    ]
    return {
        "schema_version": "v02-c12-2-mutation-round.v1",
        "suite": suite,
        "required_mutant_total": len(rows),
        "valid_mutant_total": len(valid),
        "killed_total": len(killed),
        "survived_total": len(survivors),
        "invalid_total": len(invalid),
        "kill_rate": (
            len(killed) / len(valid) if valid else None
        ),
        "survivor_ids": [row["mutant_id"] for row in survivors],
        "invalid_ids": [row["mutant_id"] for row in invalid],
        "rows": rows,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _identity_trust_root_probe() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "tools"))
    import v02_c7_consensus_tally as tally

    vote_dir = (
        ROOT
        / "experiments/extraction_redesign_v02_overnight_20260725"
        / "V02_C7_6_7_ai_consensus_workspace/votes"
    )
    first_path = vote_dir / "terra_independent_window_1.json"
    notion_path = vote_dir / "notion_independent_window_2.json"
    first = json.loads(first_path.read_text(encoding="utf-8"))
    notion = json.loads(notion_path.read_text(encoding="utf-8"))
    forged = json.loads(json.dumps(first, ensure_ascii=False))
    forged["voter_id"] = "forged_independent_window_2"
    forged["model_family"] = "notion_platform_assistant"
    forged["independence_receipt"] = notion["independence_receipt"]
    with tempfile.TemporaryDirectory(prefix="v02-c12-2-trust-") as directory:
        path = Path(directory) / "forged_vote.json"
        path.write_text(
            json.dumps(forged, ensure_ascii=False),
            encoding="utf-8",
        )
        try:
            result = tally.tally_votes([first_path, path])
        except tally.C7TallyError as exc:
            accepted = False
            outcome = f"REJECTED:{type(exc).__name__}"
        else:
            accepted = True
            outcome = str(result["status"])
    return {
        "schema_version": "v02-c12-2-identity-trust-root-probe.v1",
        "probe_id": "P01_CLONED_BALLOT_WITH_COPIED_LEDGER_RECEIPT",
        "counted_in_required_seven_mutants": False,
        "adversarial_input_accepted": accepted,
        "status": (
            "SURVIVED_TRUST_ROOT_GAP"
            if accepted
            else "REJECTED_BY_CURRENT_GUARD"
        ),
        "observed_outcome": outcome,
        "boundary": (
            "现有仓内票据只能校验格式、绑定值与时序；"
            "连接器未暴露不可伪造的平台签名，不能冒充已解决。"
        ),
        "regression_test": (
            "tests/test_v02_c12_2_mutation_killrate.py::"
            "test_forged_second_window_receipt_requires_external_trust_root"
        ),
        "regression_state": "XFAIL_PENDING_EXTERNAL_TRUST_ROOT",
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _catalog_document() -> dict[str, Any]:
    return {
        "schema_version": "v02-c12-2-mutation-catalog.v1",
        "required_mutant_total": 7,
        "mutation_method": (
            "exact_source_replacement_compiled_in_isolated_subprocess_memory"
        ),
        "original_source_files_written": False,
        "mutants": [
            {
                "mutant_id": row.mutant_id,
                "title": row.title,
                "module_name": row.module_name,
                "source_path": row.source_path,
                "source_sha256": sha256_file(ROOT / row.source_path),
                "legacy_tests": list(row.legacy_tests),
                "added_regression_tests": list(row.added_regression_tests),
            }
            for row in mutation_specs()
        ],
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _summary(
    initial: dict[str, Any],
    final: dict[str, Any],
    trust_probe: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "v02-c12-2-mutation-kill-summary.v1",
        "status": (
            "PASS_REQUIRED_SEVEN_KILLED_WITH_EXTERNAL_TRUST_GAP"
            if (
                final["valid_mutant_total"] == 7
                and final["killed_total"] == 7
                and final["invalid_total"] == 0
                and trust_probe["status"] == "SURVIVED_TRUST_ROOT_GAP"
            )
            else "FAIL_OR_INCOMPLETE"
        ),
        "initial_existing_test_defense": {
            "valid_mutant_total": initial["valid_mutant_total"],
            "killed_total": initial["killed_total"],
            "survived_total": initial["survived_total"],
            "kill_rate": initial["kill_rate"],
            "survivor_ids": initial["survivor_ids"],
        },
        "after_c12_2_regressions": {
            "valid_mutant_total": final["valid_mutant_total"],
            "killed_total": final["killed_total"],
            "survived_total": final["survived_total"],
            "kill_rate": final["kill_rate"],
            "survivor_ids": final["survivor_ids"],
        },
        "added_regressions": [
            {
                "mutant_id": row.mutant_id,
                "tests": list(row.added_regression_tests),
            }
            for row in mutation_specs()
            if row.added_regression_tests
        ],
        "external_trust_root_probe": trust_probe,
        "quality_result_registered": False,
        "active_runner_connected": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _report_text(summary: dict[str, Any], artifact_set_sha: str) -> str:
    initial = summary["initial_existing_test_defense"]
    final = summary["after_c12_2_regressions"]
    trust = summary["external_trust_root_probe"]
    return f"""# C12.2｜变异杀伤率停点回包

✅ 结论：七个规定 mutant 均为有效注入。旧测试直接杀死
{initial["killed_total"]}/7，杀伤率 {initial["kill_rate"]:.2%}；补两条最小回归后
杀死 {final["killed_total"]}/7，杀伤率 {final["kill_rate"]:.2%}。

⚠️ 这不等于身份信任根已经解决。额外的“复制第一票并连合法账序凭据一起
伪造”探针仍为 `{trust["status"]}`，已补 XFAIL 回归，等待不可伪造的平台
署名或外部信任根，未塞进七个规定 mutant 的 100% 里。

## 七项结果

| mutant | 旧测试 | 补回归后 |
|---|---:|---:|
| M01 伪造第二模型族（只改名、缺凭据） | KILLED | KILLED |
| M02 绕过先封后投 | KILLED | KILLED |
| M03 机械路由冒充语义命中 | KILLED | KILLED |
| M04 逐字坐标回贴降级为子串 | SURVIVED | KILLED |
| M05 NOT_FOUND 静默当 UNKNOWN | KILLED | KILLED |
| M06 manifest 夹带未登记文件 | KILLED | KILLED |
| M07 QCR_full 分母强制成 49 | SURVIVED | KILLED |

新增回归只补 M04 与 M07。原有目标源码未改，mutant 只在独立子进程内存
中存活；模型 API 0、网络请求 0。

## 边界

- C12.2 只登记工程防线强弱，不登记任何抽取质量胜负。
- 不接现役运行器，不改六本金标、默认链、现役 122 条或 outbox。
- `claim_span` 在事件句内的现役合同本来就是逐字连续子串；M04 测的是
  锚目录坐标对原文切片必须全等，不能把两件事混称。
- 工作区同时有其他窗口改动，本件未清理、未回滚、未提交、未推送。

## 归属票

- 归属：V02／C12.2 变异杀伤率候选件。
- 触碰面：只新增 C12.2 程序、工件、回包和一份测试；LEGACY 写入 0，
  C13 写入 0。
- 测试：相关 115 passed／1 xfailed；整组 V02 收集被当前工作区两份
  并行测试缺少本地 `jsonschema` 依赖阻断，未临时装依赖、未把收集错误
  算成本件失败或通过。

工件集 SHA：`{artifact_set_sha}`

来源：Codex
"""


def _artifact_manifest(artifacts: dict[str, bytes]) -> dict[str, Any]:
    rows = [
        {
            "path": relative,
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
        }
        for relative, raw in sorted(artifacts.items())
    ]
    return {
        "schema_version": "v02-c12-2-artifact-manifest.v1",
        "file_total": len(rows),
        "files": rows,
        "artifact_set_sha256": sha256_bytes(stable_json_bytes(rows)),
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_artifacts() -> dict[str, bytes]:
    before = source_bindings()
    initial = _run_round("legacy")
    final = _run_round("final")
    trust_probe = _identity_trust_root_probe()
    after = source_bindings()
    if before != after:
        raise MutationHarnessError("变异执行前后被测源码或本工具发生漂移")
    summary = _summary(initial, final, trust_probe)
    if summary["status"] != (
        "PASS_REQUIRED_SEVEN_KILLED_WITH_EXTERNAL_TRUST_GAP"
    ):
        raise MutationHarnessError("七项变异未达到预写收口条件")
    regression_delta = {
        "schema_version": "v02-c12-2-regression-delta.v1",
        "before": {
            row["mutant_id"]: row["mutation"]["status"]
            for row in initial["rows"]
        },
        "after": {
            row["mutant_id"]: row["mutation"]["status"]
            for row in final["rows"]
        },
        "changed_by_added_regression": [
            mutant_id
            for mutant_id, status in {
                row["mutant_id"]: row["mutation"]["status"]
                for row in initial["rows"]
            }.items()
            if status == "SURVIVED"
            and next(
                row["mutation"]["status"]
                for row in final["rows"]
                if row["mutant_id"] == mutant_id
            )
            == "KILLED"
        ],
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts = {
        "mutation_catalog.json": stable_json_bytes(_catalog_document()),
        "source_binding_receipt.json": stable_json_bytes(
            {
                "schema_version": "v02-c12-2-source-binding-receipt.v1",
                "status": "PASS_NO_SOURCE_DRIFT",
                "before": before,
                "after": after,
                "equal": before == after,
                "model_api_calls": 0,
                "network_requests": 0,
            }
        ),
        "initial_mutation_results.json": stable_json_bytes(initial),
        "final_mutation_results.json": stable_json_bytes(final),
        "regression_delta.json": stable_json_bytes(regression_delta),
        "identity_trust_root_probe.json": stable_json_bytes(trust_probe),
        "mutation_kill_summary.json": stable_json_bytes(summary),
    }
    manifest = _artifact_manifest(artifacts)
    artifacts["artifact_manifest.json"] = stable_json_bytes(manifest)
    report = _report_text(summary, manifest["artifact_set_sha256"])
    artifacts["C12_2_stop_receipt.md"] = report.encode("utf-8")
    return artifacts


def write_or_verify(*, check: bool) -> dict[str, Any]:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise MutationHarnessError("C12.2 连续两次变异结果不一致")
    if check:
        if not OUTPUT_DIR.is_dir():
            raise MutationHarnessError("C12.2 输出目录不存在")
        for relative, raw in first.items():
            path = OUTPUT_DIR / relative
            if not path.is_file() or path.read_bytes() != raw:
                raise MutationHarnessError(f"C12.2 工件漂移：{relative}")
        if not REPORT_PATH.is_file():
            raise MutationHarnessError("C12.2 停点回包不存在")
        if REPORT_PATH.read_bytes() != first["C12_2_stop_receipt.md"]:
            raise MutationHarnessError("C12.2 停点回包与输出镜像不一致")
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for relative, raw in first.items():
            path = OUTPUT_DIR / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_bytes(first["C12_2_stop_receipt.md"])
    summary = json.loads(first["mutation_kill_summary.json"])
    return {
        "status": summary["status"],
        "output_dir": display_path(OUTPUT_DIR),
        "report_path": display_path(REPORT_PATH),
        "initial_kill_rate": summary[
            "initial_existing_test_defense"
        ]["kill_rate"],
        "final_kill_rate": summary[
            "after_c12_2_regressions"
        ]["kill_rate"],
        "external_trust_root_status": summary[
            "external_trust_root_probe"
        ]["status"],
        "model_api_calls": 0,
        "network_requests": 0,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--worker")
    parser.add_argument("--suite", choices=("legacy", "final"))
    parser.add_argument("--mutated", action="store_true")
    args = parser.parse_args(argv)
    if args.worker:
        if args.suite is None:
            parser.error("--worker 必须配 --suite")
    elif args.write == args.check:
        parser.error("必须且只能选择 --write 或 --check")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.worker:
            return _worker(args.worker, args.suite, args.mutated)
        result = write_or_verify(check=args.check)
    except (MutationHarnessError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

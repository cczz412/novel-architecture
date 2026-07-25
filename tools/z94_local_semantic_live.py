#!/usr/bin/env python3
"""第94道步二：重冻结局部语义包请求，并在独立运行目录发网。

这份薄入口只负责第94道自己的两件事：
1. 把已审收步一的32份 ``messages`` 原样带入，把修复请求外壳校正回
   retry13 实物参数（温度0.2、输出8k）；
2. 复用 retry13 已验收的运输、检查点、单对象解析与物化逻辑。

步一目录和 retry13 目录始终只读；本工具不提供覆盖、续跑或挑样入口。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
from pathlib import Path
from typing import Any, Mapping

import z68_revised_request_pilot as z68
import z83_program_side_repair_pilot as z83
import z83_retry13_atomic_repair as retry13
import z94_local_semantic_supply as step1
from zbatch_modules import api_transport, z83_retry_transport
from zbatch_modules.errors import ZBatchError
from pipeline_common import model_benchmark


ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve()
RUN_NAME = "Z94_X01_Flash局部语义包_步二单臂_v1.0_20260723"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_NAME
TENCENT_RUN_NAME = "Z94_X01_Flash局部语义包_步二腾讯通道_v1.0_20260723"
TENCENT_RUN_DIR = ROOT / "runs" / TENCENT_RUN_NAME
TENCENT_PROVIDER_PATH = ROOT / "config/providers/tencent_tokenhub_multi_model.json"
TENCENT_MODEL = "deepseek-v4-flash-202605"
STEP1_RUN = step1.RUN_DIR
SOURCE_RETRY13 = step1.SOURCE_RUN
SOURCE_PLAN = SOURCE_RETRY13 / "repair/atomic_plan.json"
SOURCE_PREFLIGHT = SOURCE_RETRY13 / "repair/atomic_preflight.json"
SOURCE_PLAN_RECEIPT = SOURCE_RETRY13 / "review/retry13_plan_receipt.json"
SOURCE_ADJUDICATION_REUSE = (
    SOURCE_RETRY13 / "review/adjudication_reused_from_retry09.json"
)

STEP2_PARAMETERS = copy.deepcopy(step1.RETRY13_REPAIR_PARAMETERS)
EXPECTED_STEP1_ONLY_DIFFS = {
    "$.max_tokens": (32000, 8000),
    "$.temperature": (0.0, 0.2),
}
SOURCE_STEP1_REQUEST_SET_SHA256 = (
    "7f6db6947ec453649c4058940e974a204ace11bf55f6f466cac2785e3dddf992"
)
SOURCE_RETRY13_PLAN_SHA256 = step1.SOURCE_PLAN_SHA256
SOURCE_RETRY09_ADJUDICATION_SHA256 = step1.SOURCE_ADJUDICATION_SHA256
CURRENT_STATE = ROOT / "governance/CURRENT_STATE.json"
RELEASE_AUTHORITY_TIME = "2026-07-23T17:08:00+08:00"
RELEASE_TASK_ID = "Z94-flash-local-semantic-supply-step2"
TENCENT_RELEASE_AUTHORITY_TIME = "2026-07-23T18:09:32+08:00"
TENCENT_RELEASE_TASK_ID = "Z94-flash-local-semantic-supply-step2-tencent"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    z83.write_json(path, value)


def write_json_atomic(path: Path, value: Any) -> None:
    z83.write_json_atomic(path, value)


def sha256_file(path: Path) -> str:
    return z68.sha256_file(path)


def canonical_sha(value: Any) -> str:
    return retry13.canonical_sha(value)


def sha256_bytes(raw: bytes) -> str:
    return retry13.sha256_bytes(raw)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _assert_formal_run_dir(
    run_dir: Path, *, allow_test_run_dir: bool = False
) -> None:
    if allow_test_run_dir:
        return
    resolved = run_dir.resolve(strict=False)
    if (
        resolved.parent != (ROOT / "runs").resolve(strict=False)
        or resolved.name not in {RUN_NAME, TENCENT_RUN_NAME}
    ):
        raise ZBatchError(
            "第94道步二正式入口只准使用已拍 SenseNova 或腾讯隔离运行编号"
        )


def _tencent_profile(run_dir: Path) -> bool:
    return run_dir.name == TENCENT_RUN_NAME


def _assert_source_pins() -> None:
    pins = {
        SOURCE_PLAN: SOURCE_RETRY13_PLAN_SHA256,
        step1.SOURCE_ADJUDICATION: SOURCE_RETRY09_ADJUDICATION_SHA256,
    }
    for path, expected in pins.items():
        if not path.is_file() or sha256_file(path) != expected:
            raise ZBatchError(f"第94道步二来源漂移：{_relative(path)}")
    step1_verification = step1.verify()
    if (
        step1_verification.get("logical_request_count") != 32
        or step1_verification.get("request_sha256_set_sha256")
        != SOURCE_STEP1_REQUEST_SET_SHA256
        or step1_verification.get("step2_release_allowed") is not False
    ):
        raise ZBatchError("第94道步一已审收冻结件不能从生成规则逐字重建")
    step1_preflight = read_json(STEP1_RUN / "preflight.json")
    if (
        step1_preflight.get("request_sha256_set_sha256")
        != SOURCE_STEP1_REQUEST_SET_SHA256
        or step1_preflight.get("logical_request_count") != 32
        or step1_preflight.get("parent_count") != 13
        or step1_preflight.get("atomic_split_total") != 25
        or step1_preflight.get("one_to_one_total") != 7
    ):
        raise ZBatchError("第94道步一冻结总票漂移")
    expected_rules = {
        "paragraph_window": step1.paragraph_window_rule()["rule_sha256"],
        "anchor_cluster": step1.anchor_cluster_rule()["rule_sha256"],
        "must_preserve": step1.must_preserve_rule()["rule_sha256"],
    }
    if step1_preflight.get("rules") != expected_rules:
        raise ZBatchError("第94道步一三条供料规则漂移")
    rows = step1_preflight.get("rows")
    if not isinstance(rows, list) or len(rows) != 32:
        raise ZBatchError("第94道步一冻结票不是32行")
    observed_request_shas: list[str] = []
    observed_task_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ZBatchError("第94道步一冻结票含非对象行")
        task_id = str(row.get("task_id") or "")
        path = STEP1_RUN / str(row.get("prepared_request_path") or "")
        if not task_id or task_id in observed_task_ids or not path.is_file():
            raise ZBatchError("第94道步一冻结任务为空、重复或缺请求实物")
        body = read_json(path)
        request_sha = sha256_file(path)
        if (
            row.get("prepared_request_sha256") != request_sha
            or row.get("messages_sha256") != canonical_sha(body.get("messages"))
        ):
            raise ZBatchError(f"第94道步一冻结请求或消息SHA漂移：{task_id}")
        observed_task_ids.add(task_id)
        observed_request_shas.append(request_sha)
    if canonical_sha(observed_request_shas) != SOURCE_STEP1_REQUEST_SET_SHA256:
        raise ZBatchError("第94道步一32份请求集合SHA不能从实物重建")


def _assert_release_authority(run_dir: Path) -> dict[str, Any]:
    if not CURRENT_STATE.is_file():
        raise ZBatchError("缺本地当前状态镜像，不能据聊天摘要自行放行")
    state = read_json(CURRENT_STATE)
    current = state.get("current_step") if isinstance(state, dict) else None
    release = current.get("step2_release_authority") if isinstance(current, dict) else None
    if _tencent_profile(run_dir):
        if (
            not isinstance(current, dict)
            or current.get("task_id") != TENCENT_RELEASE_TASK_ID
            or current.get("step2_release_allowed") is not True
            or current.get("authority_time") != TENCENT_RELEASE_AUTHORITY_TIME
            or not isinstance(release, dict)
            or release.get("authority_kind") != "cz_direct_provider_override"
            or release.get("provider") != "tencent_tokenhub"
            or release.get("model") != TENCENT_MODEL
            or release.get("temperature") != 0.2
            or release.get("max_tokens") != 8000
            or release.get("full_rerun_required") is not True
        ):
            raise ZBatchError("第94道腾讯通道重跑缺CZ本轮直接授权镜像")
        return current
    if (
        not isinstance(current, dict)
        or current.get("task_id") != RELEASE_TASK_ID
        or current.get("step2_release_allowed") is not True
        or current.get("authority_time") != RELEASE_AUTHORITY_TIME
        or not isinstance(release, dict)
        or release.get("notion_queue_readback") is not True
        or release.get("notion_ledger_readback") is not True
        or release.get("temperature") != 0.2
        or release.get("max_tokens") != 8000
        or release.get("single_variable") != "model_visible_supply_slice_only"
    ):
        raise ZBatchError("第94道步二缺17:08 Notion续令①的本地权威回读镜像")
    return current


def _json_differences(before: Any, after: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        rows: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}"
            if key not in before:
                rows.append({"path": child, "before": "<missing>", "after": after[key]})
            elif key not in after:
                rows.append({"path": child, "before": before[key], "after": "<missing>"})
            else:
                rows.extend(_json_differences(before[key], after[key], child))
        return rows
    if isinstance(before, list):
        if len(before) != len(after):
            return [{"path": path, "before": before, "after": after}]
        rows = []
        for index, (left, right) in enumerate(zip(before, after, strict=True)):
            rows.extend(_json_differences(left, right, f"{path}[{index}]"))
        return rows
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def _task_sources(
    task: Mapping[str, Any],
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    task_id = str(task["task_id"])
    step1_path = STEP1_RUN / f"prepared_requests/z94-{task_id}.json"
    retry13_path = (
        SOURCE_RETRY13
        / f"repair/prepared_single_object_requests/z83r13-{task_id}.json"
    )
    if not step1_path.is_file() or not retry13_path.is_file():
        raise ZBatchError(f"{task_id} 缺步一或 retry13 冻结请求")
    return step1_path, read_json(step1_path), retry13_path, read_json(retry13_path)


def _build_request_rows(
    plan: Mapping[str, Any],
    run_dir: Path = DEFAULT_RUN_DIR,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    source_preflight = read_json(SOURCE_PREFLIGHT)
    source_rows = {
        str(row["task_id"]): row for row in source_preflight["rows"]
    }
    bodies: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []
    for task in plan["tasks"]:
        task_id = str(task["task_id"])
        step1_path, step1_body, retry13_path, retry13_body = _task_sources(task)
        if _tencent_profile(run_dir):
            candidate = {
                "model": TENCENT_MODEL,
                "messages": copy.deepcopy(step1_body["messages"]),
                "temperature": 0.2,
                "max_tokens": 8000,
                "n": 1,
                "thinking": {"type": "enabled"},
            }
            expected_step1_diffs = {
                "$.max_tokens": (32000, 8000),
                "$.model": (step1_body["model"], TENCENT_MODEL),
                "$.reasoning_effort": ("medium", "<missing>"),
                "$.response_format": ({"type": "json_object"}, "<missing>"),
                "$.temperature": (0.0, 0.2),
                "$.thinking": ("<missing>", {"type": "enabled"}),
            }
        else:
            candidate = copy.deepcopy(step1_body)
            candidate.update(STEP2_PARAMETERS)
            expected_step1_diffs = EXPECTED_STEP1_ONLY_DIFFS

        step1_diffs = _json_differences(step1_body, candidate)
        observed = {
            row["path"]: (row["before"], row["after"]) for row in step1_diffs
        }
        if observed != expected_step1_diffs:
            raise ZBatchError(f"{task_id} 重冻结相对步一出现未批准变化")

        step2_outer = {key: value for key, value in candidate.items() if key != "messages"}
        retry13_outer = {
            key: value for key, value in retry13_body.items() if key != "messages"
        }
        retry13_outer_diffs = _json_differences(retry13_outer, step2_outer)
        if not _tencent_profile(run_dir) and retry13_outer_diffs:
            raise ZBatchError(f"{task_id} 请求外壳没有逐项对齐 retry13")
        if _tencent_profile(run_dir):
            expected_tencent_outer_diffs = [
                {
                    "path": "$.model",
                    "before": retry13_outer["model"],
                    "after": TENCENT_MODEL,
                },
                {
                    "path": "$.reasoning_effort",
                    "before": "medium",
                    "after": "<missing>",
                },
                {
                    "path": "$.response_format",
                    "before": {"type": "json_object"},
                    "after": "<missing>",
                },
                {
                    "path": "$.thinking",
                    "before": "<missing>",
                    "after": {"type": "enabled"},
                },
            ]
            if retry13_outer_diffs != expected_tencent_outer_diffs:
                raise ZBatchError(f"{task_id} 腾讯通道兼容差异不等于冻结四项")
        if candidate.get("messages") != step1_body.get("messages"):
            raise ZBatchError(f"{task_id} 步一 messages 漂移")
        if candidate.get("messages") == retry13_body.get("messages"):
            raise ZBatchError(f"{task_id} 局部供料意外退回全章供料")

        case_id = f"z83r13-{task_id}"
        relative_path = (
            f"repair/prepared_single_object_requests/{case_id}.json"
        )
        source_row = copy.deepcopy(source_rows[task_id])
        source_row.update(
            {
                "case_id": case_id,
                "prepared_request_path": relative_path,
                "prepared_request_sha256": None,
                "body_canonical_sha256": canonical_sha(candidate),
                "messages_sha256": canonical_sha(candidate["messages"]),
            }
        )
        bodies[task_id] = candidate
        rows.append(source_row)
        diff_rows.append(
            {
                "task_id": task_id,
                "parent_event_id": task["parent_event_id"],
                "chapter": task["chapter"],
                "step1_request_path": _relative(step1_path),
                "step1_request_sha256": sha256_file(step1_path),
                "retry13_request_path": _relative(retry13_path),
                "retry13_request_sha256": sha256_file(retry13_path),
                "step1_to_step2_differences": step1_diffs,
                "step1_messages_unchanged": True,
                "retry13_outer_fields_equal": not _tencent_profile(run_dir),
                "retry13_outer_compatibility_differences": retry13_outer_diffs,
                "retry13_messages_differ_only_by_supply_slice": True,
            }
        )
    if len(bodies) != 32:
        raise ZBatchError("第94道步二请求数不等于32")
    return bodies, rows, diff_rows


def _copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise ZBatchError(f"缺少隔离来源目录：{_relative(source)}")
    shutil.copytree(source, target)


def _copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise ZBatchError(f"缺少隔离来源文件：{_relative(source)}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _adapt_root_preflight(run_dir: Path) -> dict[str, Any]:
    preflight = copy.deepcopy(read_json(SOURCE_RETRY13 / "preflight.json"))
    preflight["run_id"] = run_dir.name
    # retry13 的票记录的是它当时的完整保护树。Z94 是新的派生运行，
    # 应在准备时重新冻结“此刻”的保护树，再由 verify_prepared 核对
    # 准备过程没有改动它；否则历史报告后来只增一张回读票，也会让
    # 新运行永远无法准备。
    preflight["protected_before"] = z83.protected_snapshot()
    for row in preflight["copied_inputs"]:
        target = Path(str(row["target"]))
        source_relative = target.relative_to(SOURCE_RETRY13)
        new_target = run_dir / source_relative
        row["target"] = new_target.as_posix()
        row["target_sha256"] = sha256_file(new_target)
    preflight["producer"] = {
        "path": Path(z83.__file__).resolve().relative_to(ROOT).as_posix(),
        "sha256": sha256_file(Path(z83.__file__).resolve()),
    }
    preflight["producer_dependencies"] = {
        "pipeline_inspector": {
            "path": Path(z83.pipeline_inspector.__file__)
            .resolve()
            .relative_to(ROOT)
            .as_posix(),
            "sha256": sha256_file(Path(z83.pipeline_inspector.__file__).resolve()),
        },
        "api_transport": {
            "path": Path(z83.api_transport.__file__)
            .resolve()
            .relative_to(ROOT)
            .as_posix(),
            "sha256": sha256_file(Path(z83.api_transport.__file__).resolve()),
        },
    }
    preflight["z94_step2"] = {
        "status": "conditional_release_pass_zero_call",
        "source_step1_run": _relative(STEP1_RUN),
        "source_retry13_run": _relative(SOURCE_RETRY13),
        "single_variable": (
            "supply_slice_plus_tencent_provider_compatibility"
            if _tencent_profile(run_dir)
            else "model_visible_supply_slice_only"
        ),
        "repair_parameters": STEP2_PARAMETERS,
        "inspector_parameters_unchanged": True,
    }
    return preflight


def _source_tree_snapshot() -> dict[str, Any]:
    return {
        "step1": z68.tree_fingerprint(STEP1_RUN),
        "retry13": z68.tree_fingerprint(SOURCE_RETRY13),
    }


def prepare(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    _assert_formal_run_dir(run_dir, allow_test_run_dir=allow_test_run_dir)
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    _assert_release_authority(run_dir)
    _assert_source_pins()
    source_trees_before = _source_tree_snapshot()
    plan = copy.deepcopy(read_json(SOURCE_PLAN))
    plan["run_id"] = run_dir.name
    first_bodies, first_rows, first_diffs = _build_request_rows(plan, run_dir)
    second_bodies, second_rows, second_diffs = _build_request_rows(plan, run_dir)
    if (
        first_bodies != second_bodies
        or first_rows != second_rows
        or first_diffs != second_diffs
    ):
        raise ZBatchError("第94道步二两次独立机械构造不一致")

    run_dir.mkdir(parents=True)
    for name in ("inputs", "prompt_frozen", "provenance", "prepared_requests", "main"):
        _copy_tree(SOURCE_RETRY13 / name, run_dir / name)
    _copy_file(SOURCE_ADJUDICATION_REUSE, run_dir / "review/adjudication_reused_from_retry09.json")
    write_json(run_dir / "repair/atomic_plan.json", plan)
    plan_receipt = copy.deepcopy(read_json(SOURCE_PLAN_RECEIPT))
    plan_receipt["plan_sha256"] = sha256_file(run_dir / "repair/atomic_plan.json")
    plan_receipt["source_retry13_plan_sha256"] = SOURCE_RETRY13_PLAN_SHA256
    write_json(run_dir / "review/retry13_plan_receipt.json", plan_receipt)
    _copy_tree(STEP1_RUN / "rules", run_dir / "z94_supply/rules")
    _copy_tree(STEP1_RUN / "supply_bundles", run_dir / "z94_supply/supply_bundles")

    request_shas: list[str] = []
    preflight_rows = []
    for row in first_rows:
        task_id = str(row["task_id"])
        path = run_dir / str(row["prepared_request_path"])
        write_json(path, first_bodies[task_id])
        row = copy.deepcopy(row)
        row["prepared_request_sha256"] = sha256_file(path)
        request_shas.append(row["prepared_request_sha256"])
        preflight_rows.append(row)

    source_atomic_preflight = read_json(SOURCE_PREFLIGHT)
    atomic_preflight = copy.deepcopy(source_atomic_preflight)
    atomic_preflight["run_id"] = run_dir.name
    atomic_preflight["plan_sha256"] = sha256_file(
        run_dir / "repair/atomic_plan.json"
    )
    atomic_preflight["rows"] = preflight_rows
    atomic_preflight["z94_step2_supply_slice_only"] = not _tencent_profile(run_dir)
    atomic_preflight["z94_tencent_provider_override"] = _tencent_profile(run_dir)
    atomic_preflight["z94_provider_profile"] = (
        "tencent_tokenhub_fixed_flash" if _tencent_profile(run_dir) else "sensenova"
    )
    atomic_preflight["z94_step2_request_set_sha256"] = canonical_sha(request_shas)
    write_json_atomic(run_dir / "repair/atomic_preflight.json", atomic_preflight)
    write_json_atomic(run_dir / "preflight.json", _adapt_root_preflight(run_dir))

    diff_receipt = {
        "schema_version": "z94-step2-supply-boundary-diff-v1",
        "status": (
            "pass_supply_slice_plus_frozen_tencent_compatibility"
            if _tencent_profile(run_dir)
            else "pass_outer_equal_supply_slice_only"
        ),
        "row_count": len(first_diffs),
        "step1_allowed_differences": first_diffs[0][
            "step1_to_step2_differences"
        ],
        "retry13_outer_difference_count": 4 if _tencent_profile(run_dir) else 0,
        "provider": "tencent_tokenhub" if _tencent_profile(run_dir) else "sensenova",
        "model": (
            TENCENT_MODEL
            if _tencent_profile(run_dir)
            else z83.load_bundle(SOURCE_RETRY13).route["model"]
        ),
        "supply_slice_difference_count": len(first_diffs),
        "rows": first_diffs,
    }
    write_json_atomic(run_dir / "z94_supply/supply_boundary_diff.json", diff_receipt)
    source_trees_after = _source_tree_snapshot()
    if source_trees_after != source_trees_before:
        raise ZBatchError("第94道步二准备期间步一或 retry13 来源树漂移")
    protection = {
        "schema_version": "z94-step2-source-protection-v1",
        "source_trees_before": source_trees_before,
        "source_trees_after": source_trees_after,
        "source_trees_unchanged": True,
    }
    write_json_atomic(run_dir / "z94_supply/source_protection.json", protection)

    source_master = read_json(SOURCE_RETRY13 / "run_manifest.json")
    master = {
        "schema_version": "z94-step2-run-manifest-v1",
        "run_id": run_dir.name,
        "status": "prepared_zero_call_conditionally_released",
        "main": "completed_candidate_silver_only_imported_from_retry03",
        "review": "not_started",
        "repair": "prepared_not_started",
        "final": "not_started",
        "main_seed": source_master["main_seed"],
        "step2_release_allowed": True,
        "candidate_silver_only": True,
        "provider": "tencent_tokenhub" if _tencent_profile(run_dir) else "sensenova",
    }
    write_json_atomic(run_dir / "run_manifest.json", master)
    prepared = z83.verify_prepared(
        run_dir,
        require_zero_call=False,
        allow_test_run_dir=allow_test_run_dir,
    )
    verification = verify_preflight(
        run_dir, allow_test_run_dir=allow_test_run_dir
    )
    release = {
        "schema_version": "z94-step2-conditional-release-v1",
        "status": "pass_re_frozen_and_released_for_single_sample",
        "run_id": run_dir.name,
        "logical_request_count": 32,
        "parent_event_count": 13,
        "atomic_child_count": 25,
        "one_to_one_count": 7,
        "request_set_sha256": atomic_preflight["z94_step2_request_set_sha256"],
        "step1_messages_unchanged": True,
        "retry13_outer_difference_count": 4 if _tencent_profile(run_dir) else 0,
        "double_build_byte_identical": True,
        "source_trees_unchanged": True,
        "repair_parameters": (
            {
                "temperature": 0.2,
                "max_tokens": 8000,
                "n": 1,
                "thinking": {"type": "enabled"},
            }
            if _tencent_profile(run_dir)
            else STEP2_PARAMETERS
        ),
        "provider": "tencent_tokenhub" if _tencent_profile(run_dir) else "sensenova",
        "model": TENCENT_MODEL if _tencent_profile(run_dir) else None,
        "inspector_parameters": {"temperature": 0.0, "max_tokens": 32000},
        "model_api_calls": 0,
        "network_attempts": 0,
        "prepared_verification_sha256": canonical_sha(prepared),
        "atomic_verification_sha256": canonical_sha(verification),
        "producer_sha256": sha256_file(THIS_FILE),
    }
    write_json_atomic(run_dir / "z94_supply/step2_release_receipt.json", release)
    return release


def _validate_plan(run_dir: Path) -> dict[str, Any]:
    _assert_source_pins()
    path = run_dir / "repair/atomic_plan.json"
    if not path.is_file():
        raise ZBatchError("第94道步二缺原子计划")
    plan = read_json(path)
    expected = copy.deepcopy(read_json(SOURCE_PLAN))
    expected["run_id"] = run_dir.name
    if plan != expected:
        raise ZBatchError("第94道步二原子计划除运行编号外不等于 retry13 获批计划")
    if (
        len(plan.get("parents", [])) != 13
        or len(plan.get("tasks", [])) != 32
        or plan.get("pending_parent_ids") != []
    ):
        raise ZBatchError("第94道步二原子计划父子数或 pending 状态漂移")
    return plan


def _write_tencent_reasoning_audit(
    *,
    run_dir: Path,
    task: Mapping[str, Any],
    envelope: Mapping[str, Any],
    raw_response_sha256: str,
) -> None:
    choices = envelope.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ZBatchError("腾讯固定版Flash响应 choices 不是唯一一项")
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, Mapping) else None
    reasoning = message.get("reasoning_content") if isinstance(message, Mapping) else None
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ZBatchError("腾讯固定版Flash响应缺非空 reasoning_content")
    receipt = {
        "schema_version": "z94-tencent-reasoning-audit-v1",
        "status": "pass_nonempty_reasoning_content",
        "task_id": task["task_id"],
        "response_model": envelope.get("model"),
        "raw_response_sha256": raw_response_sha256,
        "reasoning_content_sha256": sha256_bytes(reasoning.encode("utf-8")),
        "reasoning_content_nonempty": True,
    }
    retry13._write_json_exclusive(
        run_dir / f"repair/tencent_reasoning_audit/{task['task_id']}.json",
        receipt,
    )


def _verify_tencent_reasoning_audits(
    *, run_dir: Path, plan: Mapping[str, Any]
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for task in plan["tasks"]:
        task_id = str(task["task_id"])
        audit_path = run_dir / f"repair/tencent_reasoning_audit/{task_id}.json"
        response_ticket = read_json(
            run_dir / f"repair/checkpoints/{task_id}/02_response.json"
        )
        raw_relative = response_ticket.get("raw_response_path")
        raw_path = (
            run_dir / raw_relative
            if isinstance(raw_relative, str) and raw_relative
            else Path()
        )
        if (
            not audit_path.is_file()
            or not raw_path.is_file()
            or not raw_path.resolve().is_relative_to(run_dir.resolve())
        ):
            raise ZBatchError(f"腾讯思考审计不能唯一回读：{task_id}")
        raw = raw_path.read_bytes()
        envelope = json.loads(raw.decode("utf-8"))
        message = envelope["choices"][0]["message"]
        reasoning = message.get("reasoning_content")
        expected = {
            "schema_version": "z94-tencent-reasoning-audit-v1",
            "status": "pass_nonempty_reasoning_content",
            "task_id": task_id,
            "response_model": TENCENT_MODEL,
            "raw_response_sha256": sha256_bytes(raw),
            "reasoning_content_sha256": sha256_bytes(
                str(reasoning).encode("utf-8")
            ),
            "reasoning_content_nonempty": True,
        }
        if (
            not isinstance(reasoning, str)
            or not reasoning.strip()
            or read_json(audit_path) != expected
        ):
            raise ZBatchError(f"腾讯思考审计与原始响应不一致：{task_id}")
        rows.append(expected)
    receipt = {
        "schema_version": "z94-tencent-reasoning-audit-summary-v1",
        "status": "pass_all_nonempty_and_rebuilt",
        "logical_request_count": len(rows),
        "rows_sha256": canonical_sha(rows),
    }
    write_json_atomic(run_dir / "repair/tencent_reasoning_audit_summary.json", receipt)
    return receipt


def verify_preflight(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    _assert_formal_run_dir(run_dir, allow_test_run_dir=allow_test_run_dir)
    _assert_release_authority(run_dir)
    _assert_source_pins()
    plan = _validate_plan(run_dir)
    plan_sha = sha256_file(run_dir / "repair/atomic_plan.json")
    preflight_path = run_dir / "repair/atomic_preflight.json"
    if not preflight_path.is_file():
        raise ZBatchError("第94道步二缺原子预检票")
    preflight = read_json(preflight_path)
    if (
        preflight.get("schema_version") != retry13.PREFLIGHT_SCHEMA
        or preflight.get("status") != "pass_zero_call_requests_frozen"
        or preflight.get("run_id") != run_dir.name
        or preflight.get("plan_sha256") != plan_sha
        or preflight.get("task_count") != 32
        or preflight.get("parent_count") != 13
        or preflight.get("pending_parent_ids") != []
        or preflight.get("z94_step2_supply_slice_only")
        is not (not _tencent_profile(run_dir))
        or preflight.get("z94_tencent_provider_override")
        is not _tencent_profile(run_dir)
    ):
        raise ZBatchError("第94道步二原子预检总票漂移")
    rows = preflight.get("rows")
    if not isinstance(rows, list) or len(rows) != 32:
        raise ZBatchError("第94道步二原子预检不是32行")
    by_task = {str(row["task_id"]): row for row in rows}
    fresh_bodies, _, _ = _build_request_rows(plan, run_dir)
    observed_shas: list[str] = []
    for task in plan["tasks"]:
        task_id = str(task["task_id"])
        row = by_task.get(task_id)
        if row is None:
            raise ZBatchError(f"第94道步二预检缺任务：{task_id}")
        path = run_dir / str(row["prepared_request_path"])
        if not path.is_file():
            raise ZBatchError(f"第94道步二缺冻结请求：{task_id}")
        body = read_json(path)
        if body != fresh_bodies[task_id]:
            raise ZBatchError(f"第94道步二冻结请求不能从步一重建：{task_id}")
        if (
            row.get("prepared_request_sha256") != sha256_file(path)
            or row.get("body_canonical_sha256") != canonical_sha(body)
            or row.get("messages_sha256") != canonical_sha(body["messages"])
        ):
            raise ZBatchError(f"第94道步二冻结请求 SHA 断链：{task_id}")
        observed_shas.append(row["prepared_request_sha256"])
    if preflight.get("z94_step2_request_set_sha256") != canonical_sha(observed_shas):
        raise ZBatchError("第94道步二32份请求集合 SHA 不能重建")
    protection = read_json(run_dir / "z94_supply/source_protection.json")
    if (
        protection.get("source_trees_unchanged") is not True
        or protection.get("source_trees_before") != _source_tree_snapshot()
        or protection.get("source_trees_after") != _source_tree_snapshot()
    ):
        raise ZBatchError("第94道步二来源树保护票漂移")
    receipt = {
        "schema_version": "z94-step2-preflight-verification-v1",
        "status": "pass",
        "run_id": run_dir.name,
        "logical_request_count": 32,
        "request_set_sha256": preflight["z94_step2_request_set_sha256"],
        "step1_messages_unchanged": True,
        "retry13_outer_difference_count": 4 if _tencent_profile(run_dir) else 0,
        "source_trees_unchanged": True,
        "step2_release_allowed": True,
        "model_api_calls": 0,
        "network_attempts": 0,
    }
    return receipt


def run_repair(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    opener: Any = None,
    sleeper: Any = None,
    monotonic: Any = None,
    jitter: Any = None,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    _assert_formal_run_dir(run_dir, allow_test_run_dir=allow_test_run_dir)
    verification = verify_preflight(
        run_dir, allow_test_run_dir=allow_test_run_dir
    )
    plan = _validate_plan(run_dir)
    if _tencent_profile(run_dir):
        provider = read_json(TENCENT_PROVIDER_PATH)
        exact = [
            row
            for row in provider.get("models", [])
            if isinstance(row, Mapping) and row.get("model_id") == TENCENT_MODEL
        ]
        if (
            provider.get("provider") != "tencent_tokenhub"
            or provider.get("base_url") != "https://tokenhub.tencentmaas.com/v1"
            or provider.get("endpoint") != "/chat/completions"
            or provider.get("model_catalog_endpoint") != "/models"
            or provider.get("model_catalog_check_required_before_run") is not True
            or provider.get("api_key_env") != "TENCENT_TOKENHUB_API_KEY"
            or len(exact) != 1
            or exact[0].get("call_ready") is not True
        ):
            raise ZBatchError("腾讯固定版V4 Flash通道配置漂移")
        route = api_transport.TransportRoute(
            provider=str(provider["provider"]),
            base_url=str(provider["base_url"]),
            endpoint=str(provider["endpoint"]),
            model=TENCENT_MODEL,
            api_key_env=str(provider["api_key_env"]),
            timeout_seconds=600,
            network_attempts=3,
        )
    else:
        provider = None
        route = api_transport.TransportRoute.from_mapping(z83.load_bundle(run_dir).route)
    key = os.environ.get(route.api_key_env)
    if not key:
        raise ZBatchError(f"缺少 {route.api_key_env}；零调用停在发网前")
    if allow_test_run_dir and opener is None:
        raise ZBatchError("测试目录发网必须显式注入假网络 opener")
    if _tencent_profile(run_dir):
        try:
            catalog_receipt = model_benchmark.verify_provider_model_catalog(
                run_dir,
                provider,
                TENCENT_MODEL,
                key,
                opener=opener if allow_test_run_dir else None,
            )
            if (
                not isinstance(catalog_receipt, Mapping)
                or catalog_receipt.get("status") != "pass_exact_model_online"
                or catalog_receipt.get("model_id") != TENCENT_MODEL
            ):
                raise ZBatchError("腾讯固定版Flash在线目录闸没有返回精确在线票")
            model_benchmark.audit_provider_model_catalog(
                run_dir, provider, TENCENT_MODEL
            )
        except BaseException as exc:
            retry13._write_hard_stop(
                run_dir=run_dir,
                error=exc,
                active_task=None,
                reason_code="tencent_exact_model_catalog_gate_failed",
            )
            master = read_json(run_dir / "run_manifest.json")
            master.update(
                {
                    "status": "repair_hard_stop",
                    "repair": "hard_stop",
                    "final": "not_started_due_to_repair_hard_stop",
                    "authoritative_ticket": "repair/hard_stop.json",
                    "hard_stop_reason": "tencent_exact_model_catalog_gate_failed",
                }
            )
            write_json_atomic(run_dir / "run_manifest.json", master)
            raise
    repair_dir = run_dir / "repair"
    forbidden = [
        repair_dir / "retry13_run_claim.json",
        repair_dir / "hard_stop.json",
        repair_dir / "retry13_run_manifest.json",
        repair_dir / "call_attempts.jsonl",
        repair_dir / "attempt_reservations.jsonl",
        repair_dir / "usage.jsonl",
        repair_dir / "requests/single_object",
        repair_dir / "raw_responses/single_object",
        repair_dir / "results",
        repair_dir / "checkpoints",
        repair_dir / "01_extract",
        repair_dir / "tencent_reasoning_audit",
        repair_dir / "tencent_reasoning_audit_summary.json",
    ]
    present = [path.relative_to(run_dir).as_posix() for path in forbidden if path.exists()]
    if present:
        raise ZBatchError(f"第94道步二已有发网或收口痕迹，禁止原位续跑：{present}")
    claim = {
        "schema_version": "z83-retry13-run-claim-v1",
        "status": "running_do_not_resume_or_cherry_pick",
        "run_id": run_dir.name,
        "plan_sha256": sha256_file(run_dir / "repair/atomic_plan.json"),
        "preflight_sha256": sha256_file(run_dir / "repair/atomic_preflight.json"),
        "preflight_verification_sha256": canonical_sha(verification),
        "logical_request_count": len(plan["tasks"]),
        "claimed_at": retry13._now_iso(),
    }
    retry13._write_json_exclusive(repair_dir / "retry13_run_claim.json", claim)
    preflight = read_json(repair_dir / "atomic_preflight.json")
    preflight_by_task = {str(row["task_id"]): row for row in preflight["rows"]}
    state = z83_retry_transport.RetryRunState()
    active_task: Mapping[str, Any] | None = None
    try:
        for task in plan["tasks"]:
            active_task = task
            task_id = str(task["task_id"])
            row = preflight_by_task[task_id]
            prepared_path = run_dir / str(row["prepared_request_path"])
            body = read_json(prepared_path)
            request_path, request_sha, wire_body, wire_sha = (
                retry13._build_request_artifact(
                    run_dir=run_dir,
                    plan=plan,
                    task=task,
                    preflight_row=row,
                    body=body,
                    route=route,
                )
            )
            checkpoint_request = retry13._request_checkpoint_record(
                task_id=task_id,
                request_path=request_path,
                request_sha256=request_sha,
                wire_body_sha256=wire_sha,
                model=route.model,
                run_dir=run_dir,
            )
            send_once = retry13._send_once_factory(
                run_dir=run_dir,
                task=task,
                route=route,
                request_sha256=request_sha,
                request_artifact_sha256=request_sha,
                wire_body=wire_body,
                wire_body_sha256=wire_sha,
                opener=opener,
            )
            try:
                result = z83_retry_transport.run_logical_request(
                    logical_request_id=task_id,
                    chapter=int(task["chapter"]),
                    send_once=send_once,
                    attempt_ledger_path=repair_dir / "call_attempts.jsonl",
                    contract_version=retry13.CONTRACT_VERSION,
                    state=state,
                    sleeper=sleeper,
                    monotonic=monotonic,
                    jitter=jitter,
                )
                if _tencent_profile(run_dir):
                    payload = result.outcome.payload
                    envelope = (
                        payload.get("response_json")
                        if isinstance(payload, Mapping)
                        else None
                    )
                    if not isinstance(envelope, Mapping):
                        raise ZBatchError("腾讯固定版Flash响应缺可读JSON信封")
                    _write_tencent_reasoning_audit(
                        run_dir=run_dir,
                        task=task,
                        envelope=envelope,
                        raw_response_sha256=str(
                            result.outcome.raw_response_sha256 or ""
                        ),
                    )
                retry13._process_successful_task(
                    run_dir=run_dir,
                    task=task,
                    request_record=checkpoint_request,
                    request_sha256=request_sha,
                    transport_result=result,
                    expected_model=route.model,
                )
            except BaseException as exc:
                reason = (
                    exc.reason_code
                    if isinstance(exc, z83_retry_transport.RetryTransportHardStop)
                    else "single_object_contract_or_processing_failure"
                )
                retry13._seal_failed_checkpoint(
                    run_dir=run_dir,
                    task=task,
                    request_record=checkpoint_request,
                    request_sha256=request_sha,
                    error_code=reason,
                )
                retry13._write_hard_stop(
                    run_dir=run_dir,
                    error=exc,
                    active_task=task,
                    reason_code=reason,
                )
                raise
        metrics = retry13._materialize_completed_repair(run_dir=run_dir, plan=plan)
        reasoning_audit = (
            _verify_tencent_reasoning_audits(run_dir=run_dir, plan=plan)
            if _tencent_profile(run_dir)
            else None
        )
        manifest = {
            "schema_version": "z83-retry13-run-manifest-v1",
            "status": "completed_candidate_silver_only_awaiting_targeted_semantic_review",
            "run_claim": claim,
            "logical_request_count": len(plan["tasks"]),
            "network_attempts": metrics["network_attempts"],
            "http_429_count": metrics["http_429_count"],
            "rewritten_descendant_count": metrics["rewritten_descendant_count"],
            "final_event_count": metrics["final_event_count"],
            "prefix_cherry_picked": False,
            "candidate_silver_only": True,
            "tencent_reasoning_audit": reasoning_audit,
        }
        retry13._write_json_exclusive(
            repair_dir / "retry13_run_manifest.json", manifest
        )
        master = read_json(run_dir / "run_manifest.json")
        master["status"] = "repair_completed_awaiting_final_review"
        master["repair"] = manifest["status"]
        master["final"] = "awaiting_targeted_semantic_review"
        write_json_atomic(run_dir / "run_manifest.json", master)
        return metrics
    except BaseException as exc:
        if not (repair_dir / "hard_stop.json").exists():
            retry13._write_hard_stop(
                run_dir=run_dir,
                error=exc,
                active_task=active_task,
                reason_code="z94_step2_unexpected_hard_stop",
            )
        master = read_json(run_dir / "run_manifest.json")
        master["status"] = "repair_hard_stop"
        master["repair"] = "hard_stop"
        master["final"] = "not_started_due_to_repair_hard_stop"
        master["authoritative_ticket"] = "repair/hard_stop.json"
        master["hard_stop_reason"] = (
            exc.reason_code
            if isinstance(exc, z83_retry_transport.RetryTransportHardStop)
            else type(exc).__name__
        )
        write_json_atomic(run_dir / "run_manifest.json", master)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("prepare", "verify-preflight", "run-repair"),
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if args.action == "prepare":
        result = prepare(run_dir)
    elif args.action == "verify-preflight":
        result = verify_preflight(run_dir)
    else:
        result = run_repair(run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

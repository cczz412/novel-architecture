from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from types import CodeType
from typing import Any, Callable, Mapping, Sequence


SCHEMA_VERSION = "v02-c12-7-segmented-cache.v1"
CANONICALIZATION_VERSION = "canonical-json-sort-keys-indent-2-v1"
CACHE_ENGINE_CONTRACT = "content-addressed-role-bound-stage-cache-v1"
CACHE_ENGINE_REVISION = 2
FROZEN_PYTHON_IMPLEMENTATION = "cpython"
FROZEN_PYTHON_VERSION = (3, 12, 12)
STAGE_ORDER = ("extract", "normalize", "crosswalk", "score", "report")
FORBIDDEN_KEY_FIELDS = frozenset(
    {
        "absolute_path",
        "created_at",
        "ctime",
        "ctime_ns",
        "filename",
        "file_name",
        "mtime",
        "mtime_ns",
        "path",
        "run_time",
        "timestamp",
    }
)
FROZEN_SMOKE_SET_SHA256 = (
    "d37bc4b49bc68225542e8a15c8f00b030ae856347b2e082040e34f7738be640a"
)
C11_PROGRAM_SHA256 = (
    "ed55d34188c4a17f9e82ba7dd6bc0f3fd07d8dcece59f98c4d3e0e7e3cf2497b"
)
C11_MANIFEST_SHA256 = (
    "f672ed0e79ec9ac367a506e56df3ea2786195735323e1ca2bd56c7c2f0ec529a"
)
C11_ARTIFACT_SET_SHA256 = (
    "796382a18e7ff892ad1f8e1711ea04212649a89db58f0bf07c98a3c97df672bf"
)
C11_FILE_SHA256 = {
    "n11_source_coverage_floors.json": (
        "e0840809200ce51b52a8069df171bbc454554fe3c979b9914fe960fcdc4766c9"
    ),
    "source_coverage_report.json": (
        "37c9a16934e45304c23ff27ffb6c84948eb22b251109237e2db9add13de4e219"
    ),
    "source_receipt.json": (
        "4ca729d16fe33b1d7944e477825ccb18755a5c17563c86f5a01c11b7dcefbcab"
    ),
    "source_unit_ledger.json": (
        "d3548e4a4bda2dc66bb380e6000a4110c7c0a19ece4a185d727f84669112a5e4"
    ),
}


class C127Error(RuntimeError):
    """C12.7 输入、缓存或冻结冒烟集不满足机械合同。"""


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "AGENTS.md").is_file() and (candidate / "experiments").is_dir():
            return candidate
    raise C127Error("找不到小说架构仓库根目录")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
TASK_ROOT = Path(__file__).resolve().parents[1]
C11_ROOT = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "V02_C11_product_north_star_20260725"
    / "C11_3_source_coverage"
)
C11_ARTIFACTS = C11_ROOT / "artifacts"
C11_PROGRAM = C11_ROOT / "program" / "v02_c11_source_coverage.py"
SMOKE_SET_PATH = TASK_ROOT / "config" / "smoke_set_v1.json"
THINKING_REPLAY_PATH = REPO_ROOT / "tools" / "v02_thinking_replay.py"
DEFAULT_ARTIFACTS = TASK_ROOT / "artifacts"
DEFAULT_CACHE = TASK_ROOT / "cache_demo"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def canonical_sha(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise C127Error(f"JSON 读取失败：{path}") from exc


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def assert_writable_target(path: Path) -> None:
    resolved = path.resolve()
    protected = (
        C11_ROOT.resolve(),
        (
            REPO_ROOT
            / "experiments"
            / "extraction_redesign_v02_overnight_20260725"
            / "V02_C13_downstream_consumer_20260725"
        ).resolve(),
    )
    if any(_is_relative_to(resolved, root) for root in protected):
        raise C127Error("C12.7 输出路径落入只读保护区")


def validate_runtime(
    *,
    implementation: str | None = None,
    version: tuple[int, int, int] | None = None,
) -> None:
    actual_implementation = implementation or sys.implementation.name
    actual_version = version or tuple(sys.version_info[:3])
    if (
        actual_implementation != FROZEN_PYTHON_IMPLEMENTATION
        or actual_version != FROZEN_PYTHON_VERSION
    ):
        expected = ".".join(str(part) for part in FROZEN_PYTHON_VERSION)
        actual = ".".join(str(part) for part in actual_version)
        raise C127Error(
            "运行环境不符合仓库锁："
            f"需要 {FROZEN_PYTHON_IMPLEMENTATION} {expected}，"
            f"实际为 {actual_implementation} {actual}"
        )


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise C127Error(f"模块加载失败：{path}")
    module = importlib.util.module_from_spec(spec)
    inserted = str(REPO_ROOT) not in sys.path
    if inserted:
        sys.path.insert(0, str(REPO_ROOT))
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if inserted:
            sys.path.remove(str(REPO_ROOT))
    return module


def default_stage_configs() -> dict[str, dict[str, Any]]:
    return {
        "extract": {
            "projection_contract": "c11_3_source_unit_ledger_readonly_v1",
            "projection_revision": 1,
            "include_source_text": False,
        },
        "normalize": {
            "row_order": "arm_case_ordinal",
            "normalization_revision": 1,
            "deduplicate_edges": True,
        },
        "crosswalk": {
            "edge_contract": "event_and_anchor_to_source_unit_v1",
            "policy_revision": 1,
        },
        "score": {
            "main_denominator": "SCORE_PLUS_REVIEW",
            "display_precision": 4,
        },
        "report": {
            "reference_contract": "C11.3_source_coverage_report",
            "include_quality_boundary": True,
        },
    }


def _allowed_stage_config() -> dict[str, set[str]]:
    return {
        "extract": {
            "projection_contract",
            "projection_revision",
            "include_source_text",
        },
        "normalize": {
            "row_order",
            "normalization_revision",
            "deduplicate_edges",
        },
        "crosswalk": {"edge_contract", "policy_revision"},
        "score": {"main_denominator", "display_precision"},
        "report": {"reference_contract", "include_quality_boundary"},
    }


def validate_stage_configs(configs: Mapping[str, Mapping[str, Any]]) -> None:
    if set(configs) != set(STAGE_ORDER):
        raise C127Error("阶段配置必须精确覆盖五段")
    allowed = _allowed_stage_config()
    for stage in STAGE_ORDER:
        config = configs[stage]
        if not isinstance(config, Mapping) or set(config) != allowed[stage]:
            raise C127Error(f"{stage} 配置字段漂移")
        forbidden = set(config) & FORBIDDEN_KEY_FIELDS
        if forbidden:
            raise C127Error(f"{stage} 配置夹带路径或时间字段：{sorted(forbidden)}")
    exact_strings = {
        ("extract", "projection_contract"): (
            "c11_3_source_unit_ledger_readonly_v1"
        ),
        ("normalize", "row_order"): "arm_case_ordinal",
        ("crosswalk", "edge_contract"): "event_and_anchor_to_source_unit_v1",
        ("score", "main_denominator"): "SCORE_PLUS_REVIEW",
        ("report", "reference_contract"): "C11.3_source_coverage_report",
    }
    for (stage, field), expected in exact_strings.items():
        if configs[stage][field] != expected:
            raise C127Error(f"{stage}.{field} 不是冻结合同枚举值")
    integer_revisions = (
        ("extract", "projection_revision"),
        ("normalize", "normalization_revision"),
        ("crosswalk", "policy_revision"),
    )
    for stage, field in integer_revisions:
        value = configs[stage][field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise C127Error(f"{stage}.{field} 必须是正整数")
    if configs["extract"]["include_source_text"] is not False:
        raise C127Error("extract 不得复制正文")
    if configs["normalize"]["deduplicate_edges"] is not True:
        raise C127Error("normalize 必须去重边")
    if not isinstance(configs["report"]["include_quality_boundary"], bool):
        raise C127Error("report.include_quality_boundary 必须是布尔值")
    precision = configs["score"]["display_precision"]
    if (
        isinstance(precision, bool)
        or not isinstance(precision, int)
        or not 0 <= precision <= 8
    ):
        raise C127Error("score.display_precision 必须是 0～8 的整数")


def _verify_c11_bundle(source_dir: Path) -> dict[str, bytes]:
    manifest_path = source_dir / "artifact_manifest.json"
    if sha256_file(C11_PROGRAM) != C11_PROGRAM_SHA256:
        raise C127Error("C11.3 程序 SHA 漂移")
    if sha256_file(manifest_path) != C11_MANIFEST_SHA256:
        raise C127Error("C11.3 manifest SHA 漂移")
    manifest = read_json(manifest_path)
    if (
        manifest.get("schema_version") != "v02-c11-source-coverage.v1"
        or manifest.get("status") != "PASS_DETERMINISTIC_ARTIFACT_SET"
        or manifest.get("artifact_set_sha256") != C11_ARTIFACT_SET_SHA256
    ):
        raise C127Error("C11.3 工件集合身份漂移")
    rows = manifest.get("files")
    if (
        not isinstance(rows, list)
        or len(rows) != 4
        or {str(row.get("path") or "") for row in rows}
        != set(C11_FILE_SHA256)
    ):
        raise C127Error("C11.3 manifest 文件清单非法")
    files: dict[str, bytes] = {"artifact_manifest.json": manifest_path.read_bytes()}
    for row in rows:
        if not isinstance(row, Mapping):
            raise C127Error("C11.3 manifest 含非对象文件行")
        name = str(row.get("path") or "")
        path = source_dir / name
        if (
            not name
            or "/" in name
            or not path.is_file()
            or row.get("sha256") != C11_FILE_SHA256.get(name)
            or sha256_file(path) != row.get("sha256")
            or path.stat().st_size != row.get("byte_count")
        ):
            raise C127Error(f"C11.3 工件不能按 manifest 回读：{name}")
        files[name] = path.read_bytes()
    return files


def content_input_rows(inputs: Mapping[str, bytes]) -> list[dict[str, str]]:
    if not inputs or any(not role for role in inputs):
        raise C127Error("阶段输入 role 不能为空")
    return [
        {"role": role, "content_sha256": sha256_bytes(raw)}
        for role, raw in sorted(inputs.items())
    ]


def reject_identity_metadata(metadata: Mapping[str, Any]) -> None:
    if metadata:
        raise C127Error(
            "缓存身份不接收外部元数据；路径／文件名／时间一律不得进入键"
        )


def _stage_contract(stage: str) -> dict[str, Any]:
    if stage not in STAGE_ORDER:
        raise C127Error(f"未知阶段：{stage}")
    index = STAGE_ORDER.index(stage)
    return {
        "stage": stage,
        "ordinal": index + 1,
        "upstream": list(STAGE_ORDER[:index]),
        "direct_upstream": None if index == 0 else STAGE_ORDER[index - 1],
        "downstream": list(STAGE_ORDER[index + 1 :]),
        "cache_identity": "SHA256_CONTENT_ONLY",
        "path_filename_timestamp_in_identity": False,
    }


def _normalize_code_constant(value: Any) -> Any:
    if isinstance(value, CodeType):
        return _code_receipt(value)
    if isinstance(value, tuple):
        return [_normalize_code_constant(item) for item in value]
    if isinstance(value, frozenset):
        return sorted(_normalize_code_constant(item) for item in value)
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return value.hex() if isinstance(value, bytes) else value
    return {"type": type(value).__qualname__, "repr": repr(value)}


def _code_receipt(code: CodeType) -> dict[str, Any]:
    return {
        "bytecode_hex": code.co_code.hex(),
        "constants": [
            _normalize_code_constant(value) for value in code.co_consts
        ],
        "names": list(code.co_names),
        "varnames": list(code.co_varnames),
        "freevars": list(code.co_freevars),
        "cellvars": list(code.co_cellvars),
        "argcount": code.co_argcount,
        "posonlyargcount": code.co_posonlyargcount,
        "kwonlyargcount": code.co_kwonlyargcount,
        "flags": code.co_flags,
    }


def _simple_global_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_simple_global_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_simple_global_value(item) for item in value)
    if isinstance(value, Mapping) and all(
        isinstance(key, str) for key in value
    ):
        return {
            key: _simple_global_value(item)
            for key, item in sorted(value.items())
        }
    raise TypeError


def _callable_receipt(
    function: Callable[..., Any],
    seen: set[int] | None = None,
) -> dict[str, Any]:
    if not hasattr(function, "__code__"):
        raise C127Error("阶段实现必须是可指纹化的 Python 函数")
    visited = seen if seen is not None else set()
    identity = id(function)
    if identity in visited:
        return {
            "qualname": getattr(function, "__qualname__", ""),
            "recursive_reference": True,
        }
    visited.add(identity)
    try:
        code = function.__code__
        dependencies: dict[str, Any] = {}
        for name in sorted(set(code.co_names)):
            if name not in function.__globals__:
                continue
            value = function.__globals__[name]
            if (
                callable(value)
                and hasattr(value, "__code__")
                and getattr(value, "__module__", None)
                == getattr(function, "__module__", None)
            ):
                dependencies[name] = {
                    "kind": "callable",
                    "receipt": _callable_receipt(value, visited),
                }
                continue
            try:
                simple = _simple_global_value(value)
            except (TypeError, ValueError):
                continue
            dependencies[name] = {"kind": "constant", "value": simple}
        closure = []
        for cell in function.__closure__ or ():
            value = cell.cell_contents
            if callable(value) and hasattr(value, "__code__"):
                closure.append(
                    {
                        "kind": "callable",
                        "receipt": _callable_receipt(value, visited),
                    }
                )
                continue
            try:
                closure.append(
                    {"kind": "constant", "value": _simple_global_value(value)}
                )
            except (TypeError, ValueError):
                closure.append(
                    {"kind": "opaque", "type": type(value).__qualname__}
                )
        return {
            "qualname": getattr(function, "__qualname__", ""),
            "code": _code_receipt(code),
            "defaults": _normalize_code_constant(function.__defaults__),
            "kwdefaults": _normalize_code_constant(function.__kwdefaults__),
            "closure": closure,
            "dependencies": dependencies,
        }
    finally:
        visited.remove(identity)


def _stage_implementation_sha(stage: str) -> str:
    if stage not in STAGE_FUNCTIONS:
        raise C127Error(f"未知阶段实现：{stage}")
    payload = {
        "engine_contract": CACHE_ENGINE_CONTRACT,
        "engine_revision": CACHE_ENGINE_REVISION,
        "actual_dispatch_callable": _callable_receipt(STAGE_FUNCTIONS[stage]),
    }
    return canonical_sha(payload)


def build_stage_key(
    *,
    stage: str,
    config: Mapping[str, Any],
    inputs: Mapping[str, bytes],
    upstream_stage_keys: Sequence[str],
    identity_metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    reject_identity_metadata(identity_metadata or {})
    contract = _stage_contract(stage)
    material = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "stage_id": stage,
        "stage_contract_sha256": canonical_sha(contract),
        "stage_implementation_sha256": _stage_implementation_sha(stage),
        "environment_contract_sha256": canonical_sha(
            {
                "json_contract": CANONICALIZATION_VERSION,
                "path_independent": True,
                "machine_independent": True,
                "python_implementation": FROZEN_PYTHON_IMPLEMENTATION,
                "python_version": list(FROZEN_PYTHON_VERSION),
            }
        ),
        "config_sha256": canonical_sha(dict(config)),
        "inputs": content_input_rows(inputs),
        "upstream_stage_keys": list(upstream_stage_keys),
    }
    return canonical_sha(material), material


def _stage_extract(
    source_files: Mapping[str, bytes],
    _upstream: Mapping[str, Any] | None,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    ledger = json.loads(source_files["source_unit_ledger.json"])
    receipt = json.loads(source_files["source_receipt.json"])
    if (
        ledger.get("schema_version") != "v02-c11-source-coverage.v1"
        or receipt.get("status") != "PASS_ZERO_API_SOURCE_COVERAGE_LEDGER"
        or receipt.get("source_unit_total") != 322
    ):
        raise C127Error("C11.3 抽取底料身份或基数漂移")
    arms: dict[str, Any] = {}
    for arm in ("control", "treatment"):
        cases: dict[str, Any] = {}
        for case_id, case in sorted(ledger["arms"][arm].items()):
            cases[case_id] = {
                "event_total": case["event_total"],
                "anchor_reference_total": case["anchor_reference_total"],
                "units": case["units"],
            }
        arms[arm] = cases
    return {
        "schema_version": f"{SCHEMA_VERSION}.extract",
        "projection_contract": config["projection_contract"],
        "projection_revision": config["projection_revision"],
        "source_artifact_set_sha256": C11_ARTIFACT_SET_SHA256,
        "source_unit_total": receipt["source_unit_total"],
        "sources": ledger["sources"],
        "arms": arms,
        "source_text_emitted": False,
        "candidate_only": True,
    }


def _stage_normalize(
    _source_files: Mapping[str, bytes],
    upstream: Mapping[str, Any] | None,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(upstream, Mapping):
        raise C127Error("normalize 缺 extract 上游")
    normalized_arms: dict[str, Any] = {}
    for arm, cases in sorted(upstream["arms"].items()):
        normalized_cases: dict[str, Any] = {}
        for case_id, case in sorted(cases.items()):
            rows = []
            for unit in sorted(case["units"], key=lambda row: int(row["ordinal"])):
                row = {
                    "unit_id": str(unit["unit_id"]),
                    "ordinal": int(unit["ordinal"]),
                    "state": str(unit["state"]),
                    "state_reason": str(unit["state_reason"]),
                    "covered_by": sorted(set(unit["covered_by"])),
                    "covering_anchor_ids": sorted(
                        set(unit["covering_anchor_ids"])
                    ),
                    "mechanical_kind": str(unit["mechanical_kind"]),
                    "text_sha256": str(unit["text_sha256"]),
                }
                rows.append(row)
            if len({row["unit_id"] for row in rows}) != len(rows):
                raise C127Error(f"{arm}/{case_id} 来源单元 ID 重复")
            normalized_cases[case_id] = {
                "event_total": int(case["event_total"]),
                "anchor_reference_total": int(case["anchor_reference_total"]),
                "rows": rows,
            }
        normalized_arms[arm] = normalized_cases
    return {
        "schema_version": f"{SCHEMA_VERSION}.normalize",
        "row_order": config["row_order"],
        "normalization_revision": config["normalization_revision"],
        "deduplicate_edges": config["deduplicate_edges"],
        "arms": normalized_arms,
        "source_text_emitted": False,
    }


def _stage_crosswalk(
    _source_files: Mapping[str, bytes],
    upstream: Mapping[str, Any] | None,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(upstream, Mapping):
        raise C127Error("crosswalk 缺 normalize 上游")
    arms: dict[str, Any] = {}
    for arm, cases in sorted(upstream["arms"].items()):
        output_cases: dict[str, Any] = {}
        for case_id, case in sorted(cases.items()):
            event_edges: list[dict[str, str]] = []
            anchor_edges: list[dict[str, str]] = []
            state_rows: list[dict[str, str]] = []
            for row in case["rows"]:
                unit_id = row["unit_id"]
                state_rows.append({"unit_id": unit_id, "state": row["state"]})
                event_edges.extend(
                    {"event_id": event_id, "unit_id": unit_id}
                    for event_id in row["covered_by"]
                )
                anchor_edges.extend(
                    {"anchor_id": anchor_id, "unit_id": unit_id}
                    for anchor_id in row["covering_anchor_ids"]
                )
            output_cases[case_id] = {
                "event_total": case["event_total"],
                "unit_states": state_rows,
                "event_to_unit": sorted(
                    event_edges,
                    key=lambda row: (row["event_id"], row["unit_id"]),
                ),
                "anchor_to_unit": sorted(
                    anchor_edges,
                    key=lambda row: (row["anchor_id"], row["unit_id"]),
                ),
            }
        arms[arm] = output_cases
    return {
        "schema_version": f"{SCHEMA_VERSION}.crosswalk",
        "edge_contract": config["edge_contract"],
        "policy_revision": config["policy_revision"],
        "arms": arms,
    }


def _stage_score(
    _source_files: Mapping[str, bytes],
    upstream: Mapping[str, Any] | None,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(upstream, Mapping):
        raise C127Error("score 缺 crosswalk 上游")
    precision = int(config["display_precision"])
    arms: dict[str, Any] = {}
    for arm, cases in sorted(upstream["arms"].items()):
        total = Counter()
        by_case: dict[str, Any] = {}
        for case_id, case in sorted(cases.items()):
            counts = Counter(row["state"] for row in case["unit_states"])
            denominator = counts["SCORE"] + counts["REVIEW"]
            rate = None if denominator == 0 else counts["SCORE"] / denominator
            by_case[case_id] = {
                "state_counts": {
                    state: counts[state]
                    for state in (
                        "SCORE",
                        "CONTEXT_ONLY",
                        "STYLE_ONLY",
                        "REVIEW",
                        "EXCLUDE",
                    )
                },
                "main_denominator": denominator,
                "source_coverage_rate": rate,
                "display_rate": (
                    None if rate is None else f"{rate:.{precision}%}"
                ),
            }
            total.update(counts)
        denominator = total["SCORE"] + total["REVIEW"]
        rate = None if denominator == 0 else total["SCORE"] / denominator
        arms[arm] = {
            "by_case": by_case,
            "overall": {
                "score": total["SCORE"],
                "review": total["REVIEW"],
                "exclude": total["EXCLUDE"],
                "main_denominator": denominator,
                "source_coverage_rate": rate,
                "display_rate": (
                    None if rate is None else f"{rate:.{precision}%}"
                ),
            },
        }
    return {
        "schema_version": f"{SCHEMA_VERSION}.score",
        "main_denominator": config["main_denominator"],
        "display_precision": precision,
        "arms": arms,
        "quality_result_registered": False,
    }


def _stage_report(
    source_files: Mapping[str, bytes],
    upstream: Mapping[str, Any] | None,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(upstream, Mapping):
        raise C127Error("report 缺 score 上游")
    reference = json.loads(source_files["source_coverage_report.json"])
    comparison: dict[str, Any] = {}
    all_match = True
    for arm in ("control", "treatment"):
        current = upstream["arms"][arm]["overall"]
        expected = reference["arms"][arm]["overall"]
        match = (
            current["score"] == expected["state_counts"]["SCORE"]
            and current["review"] == expected["state_counts"]["REVIEW"]
            and current["exclude"] == expected["state_counts"]["EXCLUDE"]
            and current["main_denominator"]
            == expected["main_denominator_score_plus_review"]
            and current["source_coverage_rate"] == expected["source_coverage_rate"]
        )
        all_match = all_match and match
        comparison[arm] = {
            "matches_c11_completed_item": match,
            "score": current["score"],
            "review": current["review"],
            "main_denominator": current["main_denominator"],
            "display_rate": current["display_rate"],
        }
    if not all_match:
        raise C127Error("分段回放结果与 C11.3 已完成工件不一致")
    return {
        "schema_version": f"{SCHEMA_VERSION}.report",
        "reference_contract": config["reference_contract"],
        "include_quality_boundary": config["include_quality_boundary"],
        "comparison": comparison,
        "all_arms_match_c11_completed_item": True,
        "interpretation_boundary": (
            "本件只证明 C11.3 工程回放可分段缓存；不代表现役流水线已接入，"
            "不登记任何语义或质量胜负。"
        ),
        "candidate_foundation_only": True,
        "runtime_connected": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


STAGE_FUNCTIONS: dict[
    str,
    Callable[
        [Mapping[str, bytes], Mapping[str, Any] | None, Mapping[str, Any]],
        dict[str, Any],
    ],
] = {
    "extract": _stage_extract,
    "normalize": _stage_normalize,
    "crosswalk": _stage_crosswalk,
    "score": _stage_score,
    "report": _stage_report,
}


def _cache_entry_paths(cache_root: Path, stage: str, key: str) -> tuple[Path, Path]:
    entry = cache_root / stage / key
    return entry / "artifact.json", entry / "manifest.json"


def _cache_index_path(cache_root: Path) -> Path:
    return cache_root / "_content_index.json"


def _empty_cache_index() -> dict[str, Any]:
    return {
        "schema_version": f"{SCHEMA_VERSION}.cache-content-index",
        "entries": {},
    }


def _load_cache_index(cache_root: Path) -> tuple[dict[str, Any], bytes | None]:
    path = _cache_index_path(cache_root)
    if not path.exists():
        return _empty_cache_index(), None
    raw = path.read_bytes()
    index = read_json(path)
    if (
        raw != canonical_json_bytes(index)
        or index.get("schema_version")
        != f"{SCHEMA_VERSION}.cache-content-index"
        or not isinstance(index.get("entries"), Mapping)
    ):
        raise C127Error("缓存独立内容索引漂移")
    return index, raw


def _write_cache_index(cache_root: Path, index: Mapping[str, Any]) -> bytes:
    assert_writable_target(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    raw = canonical_json_bytes(index)
    path = _cache_index_path(cache_root)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)
    return raw


def _cache_index_row(
    *,
    artifact_raw: bytes,
    manifest_raw: bytes,
    material: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "artifact_sha256": sha256_bytes(artifact_raw),
        "manifest_sha256": sha256_bytes(manifest_raw),
        "key_material_sha256": canonical_sha(dict(material)),
    }


def _register_cache_entry(
    cache_root: Path,
    *,
    stage: str,
    key: str,
    artifact_raw: bytes,
    manifest_raw: bytes,
    material: Mapping[str, Any],
) -> None:
    index, _ = _load_cache_index(cache_root)
    entries = dict(index["entries"])
    entry_id = f"{stage}/{key}"
    row = _cache_index_row(
        artifact_raw=artifact_raw,
        manifest_raw=manifest_raw,
        material=material,
    )
    existing = entries.get(entry_id)
    if existing is not None and existing != row:
        raise C127Error("同一缓存键与独立内容索引冲突")
    entries[entry_id] = row
    _write_cache_index(
        cache_root,
        {
            "schema_version": f"{SCHEMA_VERSION}.cache-content-index",
            "entries": {name: entries[name] for name in sorted(entries)},
        },
    )


def _verify_cache_entry(
    cache_root: Path,
    *,
    stage: str,
    key: str,
    expected_material: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    artifact_path, manifest_path = _cache_entry_paths(cache_root, stage, key)
    entry = artifact_path.parent
    if not entry.is_dir():
        raise FileNotFoundError(entry)
    actual_names = {path.name for path in entry.iterdir()}
    if actual_names != {"artifact.json", "manifest.json"}:
        raise C127Error(f"{stage} 缓存条目文件集合不闭合")
    artifact_raw = artifact_path.read_bytes()
    manifest_raw = manifest_path.read_bytes()
    manifest = read_json(manifest_path)
    if (
        manifest_raw != canonical_json_bytes(manifest)
        or manifest.get("schema_version") != f"{SCHEMA_VERSION}.cache-entry"
        or manifest.get("stage") != stage
        or manifest.get("stage_key") != key
        or manifest.get("key_material") != dict(expected_material)
        or manifest.get("artifact_sha256") != sha256_bytes(artifact_raw)
        or manifest.get("file_set") != ["artifact.json", "manifest.json"]
    ):
        raise C127Error(f"{stage} 缓存 manifest 或 payload 漂移")
    index, _ = _load_cache_index(cache_root)
    expected_index_row = _cache_index_row(
        artifact_raw=artifact_raw,
        manifest_raw=manifest_raw,
        material=expected_material,
    )
    if index["entries"].get(f"{stage}/{key}") != expected_index_row:
        raise C127Error(f"{stage} 缓存与独立内容索引不一致")
    try:
        artifact = json.loads(artifact_raw)
    except json.JSONDecodeError as exc:
        raise C127Error(f"{stage} 缓存 payload 不是 JSON") from exc
    return artifact, artifact_raw


def _write_cache_entry(
    cache_root: Path,
    *,
    stage: str,
    key: str,
    material: Mapping[str, Any],
    artifact: Mapping[str, Any],
) -> bytes:
    assert_writable_target(cache_root)
    stage_root = cache_root / stage
    stage_root.mkdir(parents=True, exist_ok=True)
    artifact_raw = canonical_json_bytes(artifact)
    manifest = {
        "schema_version": f"{SCHEMA_VERSION}.cache-entry",
        "stage": stage,
        "stage_key": key,
        "key_material": dict(material),
        "artifact_sha256": sha256_bytes(artifact_raw),
        "file_set": ["artifact.json", "manifest.json"],
    }
    entry = stage_root / key
    if entry.exists():
        _, existing = _verify_cache_entry(
            cache_root,
            stage=stage,
            key=key,
            expected_material=material,
        )
        if existing != artifact_raw:
            raise C127Error(f"{stage} 同键出现不同内容")
        return existing

    temporary = Path(tempfile.mkdtemp(prefix=f".{stage}-{key[:12]}-", dir=stage_root))
    try:
        (temporary / "artifact.json").write_bytes(artifact_raw)
        manifest_raw = canonical_json_bytes(manifest)
        (temporary / "manifest.json").write_bytes(manifest_raw)
        os.replace(temporary, entry)
    except FileExistsError:
        pass
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    if not entry.is_dir():
        raise C127Error(f"{stage} 缓存条目未能原子落盘")
    artifact_raw = (entry / "artifact.json").read_bytes()
    manifest_raw = (entry / "manifest.json").read_bytes()
    _register_cache_entry(
        cache_root,
        stage=stage,
        key=key,
        artifact_raw=artifact_raw,
        manifest_raw=manifest_raw,
        material=material,
    )
    _, verified = _verify_cache_entry(
        cache_root,
        stage=stage,
        key=key,
        expected_material=material,
    )
    return verified


def verify_cache_index(cache_root: Path) -> dict[str, Any]:
    index, raw = _load_cache_index(cache_root)
    if raw is None:
        raise C127Error("缓存独立内容索引缺失")
    actual_entry_ids: set[str] = set()
    for stage in STAGE_ORDER:
        stage_root = cache_root / stage
        if not stage_root.is_dir():
            continue
        for entry in stage_root.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                actual_entry_ids.add(f"{stage}/{entry.name}")
    if actual_entry_ids != set(index["entries"]):
        raise C127Error("缓存独立内容索引与磁盘条目集合不闭合")
    for entry_id in sorted(actual_entry_ids):
        stage, key = entry_id.split("/", 1)
        _, manifest_path = _cache_entry_paths(cache_root, stage, key)
        manifest = read_json(manifest_path)
        material = manifest.get("key_material")
        if not isinstance(material, Mapping):
            raise C127Error(f"{entry_id} 缓存键材料缺失")
        _verify_cache_entry(
            cache_root,
            stage=stage,
            key=key,
            expected_material=material,
        )
    return {
        "entry_total": len(actual_entry_ids),
        "content_index_sha256": sha256_bytes(raw),
    }


def _stage_inputs(
    *,
    stage: str,
    source_files: Mapping[str, bytes],
    upstream_raw: bytes | None,
) -> dict[str, bytes]:
    if stage == "extract":
        return {
            "c11_artifact_manifest": source_files["artifact_manifest.json"],
            "c11_source_receipt": source_files["source_receipt.json"],
            "c11_source_unit_ledger": source_files["source_unit_ledger.json"],
        }
    if upstream_raw is None:
        raise C127Error(f"{stage} 缺上游 payload")
    inputs = {f"{STAGE_ORDER[STAGE_ORDER.index(stage) - 1]}_payload": upstream_raw}
    if stage == "report":
        inputs["c11_reference_report"] = source_files["source_coverage_report.json"]
    return inputs


def run_pipeline(
    cache_root: Path,
    *,
    source_dir: Path = C11_ARTIFACTS,
    stage_configs: Mapping[str, Mapping[str, Any]] | None = None,
    cache_write_allowed: bool = True,
) -> dict[str, Any]:
    validate_runtime()
    configs = {
        stage: dict(config)
        for stage, config in (stage_configs or default_stage_configs()).items()
    }
    validate_stage_configs(configs)
    source_files = _verify_c11_bundle(source_dir)
    upstream_artifact: dict[str, Any] | None = None
    upstream_raw: bytes | None = None
    upstream_keys: list[str] = []
    rows: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        inputs = _stage_inputs(
            stage=stage,
            source_files=source_files,
            upstream_raw=upstream_raw,
        )
        key, material = build_stage_key(
            stage=stage,
            config=configs[stage],
            inputs=inputs,
            upstream_stage_keys=upstream_keys,
        )
        start = time.perf_counter_ns()
        try:
            artifact, artifact_raw = _verify_cache_entry(
                cache_root,
                stage=stage,
                key=key,
                expected_material=material,
            )
            status = "CACHE_HIT"
        except FileNotFoundError:
            if not cache_write_allowed:
                raise C127Error(
                    f"{stage} 只读核验缺少冻结缓存键；禁止验收时现场补写"
                ) from None
            artifact = STAGE_FUNCTIONS[stage](
                source_files,
                upstream_artifact,
                configs[stage],
            )
            artifact_raw = _write_cache_entry(
                cache_root,
                stage=stage,
                key=key,
                material=material,
                artifact=artifact,
            )
            status = "EXECUTED"
        elapsed = time.perf_counter_ns() - start
        rows.append(
            {
                "stage": stage,
                "status": status,
                "stage_key": key,
                "artifact_sha256": sha256_bytes(artifact_raw),
                "elapsed_ns": elapsed,
            }
        )
        upstream_artifact = artifact
        upstream_raw = artifact_raw
        upstream_keys.append(key)
    return {
        "schema_version": f"{SCHEMA_VERSION}.run",
        "stages": rows,
        "executed_stages": [
            row["stage"] for row in rows if row["status"] == "EXECUTED"
        ],
        "cache_hit_stages": [
            row["stage"] for row in rows if row["status"] == "CACHE_HIT"
        ],
        "final_artifact_sha256": rows[-1]["artifact_sha256"],
        "final_report": upstream_artifact,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _without_timing(run: Mapping[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(run, ensure_ascii=False))
    for row in copied["stages"]:
        row.pop("elapsed_ns", None)
    return copied


def load_and_verify_smoke_set(path: Path = SMOKE_SET_PATH) -> dict[str, Any]:
    if sha256_file(path) != FROZEN_SMOKE_SET_SHA256:
        raise C127Error("N6 固定冒烟集 SHA 漂移；禁止原位换题")
    smoke = read_json(path)
    cases = smoke.get("cases")
    if (
        smoke.get("schema_version") != "v02-c12-7-smoke-set.v1"
        or smoke.get("frozen") is not True
        or smoke.get("replacement_allowed") is not False
        or smoke.get("case_count") != 8
        or not isinstance(cases, list)
        or len(cases) != 8
        or len({row["case_id"] for row in cases}) != 8
        or len({row["category"] for row in cases}) != 4
        or Counter(row["category"] for row in cases)
        != Counter(
            {
                category: 2
                for category in {row["category"] for row in cases}
            }
        )
    ):
        raise C127Error("N6 冒烟集不是四类各两条的冻结 8 题")
    for row in cases:
        source = REPO_ROOT / row["source_fixture"]
        if (
            not source.is_file()
            or sha256_file(source) != row["source_fixture_sha256"]
        ):
            raise C127Error(f"{row['case_id']} 来源 fixture SHA 漂移")
    return smoke


def run_smoke_set(path: Path = SMOKE_SET_PATH) -> dict[str, Any]:
    smoke = load_and_verify_smoke_set(path)
    replay = _load_module(THINKING_REPLAY_PATH, "v02_thinking_replay_for_c12_7")
    rows: list[dict[str, Any]] = []
    for case in smoke["cases"]:
        analysis = replay.analyze_text(case["replay_text"])
        findings = {
            row["finding_code"]: row for row in analysis.get("findings", [])
        }
        observed = findings.get(case["expected_finding_code"])
        passed = observed is not None
        expected_details = case["expected_details"]
        if passed:
            passed = all(
                observed["details"].get(key) == value
                for key, value in expected_details.items()
            )
        rows.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "expected_finding_code": case["expected_finding_code"],
                "observed_finding_codes": sorted(findings),
                "case_sha256": canonical_sha(case),
                "passed": passed,
            }
        )
    if not all(row["passed"] for row in rows):
        raise C127Error("N6 固定冒烟集有病例未被拦住")
    return {
        "schema_version": f"{SCHEMA_VERSION}.smoke-receipt",
        "smoke_set_sha256": FROZEN_SMOKE_SET_SHA256,
        "case_total": len(rows),
        "category_total": len({row["category"] for row in rows}),
        "passed_total": sum(row["passed"] for row in rows),
        "rows": rows,
        "status": "PASS_8_OF_8_FROZEN_SMOKE",
        "quality_truth": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def run_cache_demo(
    cache_root: Path,
    *,
    source_dir: Path = C11_ARTIFACTS,
) -> dict[str, Any]:
    baseline = run_pipeline(cache_root, source_dir=source_dir)
    warm = run_pipeline(cache_root, source_dir=source_dir)
    changed = default_stage_configs()
    changed["score"]["display_precision"] = 5
    field_change = run_pipeline(
        cache_root,
        source_dir=source_dir,
        stage_configs=changed,
    )
    if baseline["executed_stages"] != list(STAGE_ORDER):
        raise C127Error("冷跑没有执行全部五段")
    if warm["cache_hit_stages"] != list(STAGE_ORDER):
        raise C127Error("暖跑没有命中全部五段")
    if field_change["cache_hit_stages"] != ["extract", "normalize", "crosswalk"]:
        raise C127Error("score 单字段改动没有只重跑本段及下游")
    if field_change["executed_stages"] != ["score", "report"]:
        raise C127Error("score 单字段改动执行集合错误")
    cache_index = verify_cache_index(cache_root)
    return {
        "schema_version": f"{SCHEMA_VERSION}.cache-demo-receipt",
        "replayed_item": "C11.3_SOURCE_COVERAGE_LEDGER",
        "single_changed_field": "score.display_precision",
        "before_value": 4,
        "after_value": 5,
        "cold_run": _without_timing(baseline),
        "warm_run": _without_timing(warm),
        "single_field_change_run": _without_timing(field_change),
        "cache_content_index": cache_index,
        "candidate_foundation_only": True,
        "runtime_connected": False,
    }


def run_timing_observation(
    *,
    source_dir: Path = C11_ARTIFACTS,
    repetitions: int = 7,
) -> dict[str, Any]:
    if repetitions < 3:
        raise C127Error("计时观察至少需要 3 组配对")
    rows: list[dict[str, Any]] = []
    changed = default_stage_configs()
    changed["score"]["display_precision"] = 5
    with tempfile.TemporaryDirectory(prefix="v02-c12-7-timing-") as temporary:
        root = Path(temporary)
        for index in range(repetitions):
            shared = root / f"pair_{index:02d}" / "shared"
            fresh = root / f"pair_{index:02d}" / "fresh"
            run_pipeline(shared, source_dir=source_dir)

            start = time.perf_counter_ns()
            full = run_pipeline(
                fresh,
                source_dir=source_dir,
                stage_configs=changed,
            )
            full_ns = time.perf_counter_ns() - start

            start = time.perf_counter_ns()
            cached = run_pipeline(
                shared,
                source_dir=source_dir,
                stage_configs=changed,
            )
            cached_ns = time.perf_counter_ns() - start
            if full["executed_stages"] != list(STAGE_ORDER):
                raise C127Error("计时组的无缓存字段改动没有执行五段")
            if cached["executed_stages"] != ["score", "report"]:
                raise C127Error("计时组的缓存字段改动执行集合错误")
            if full["final_artifact_sha256"] != cached["final_artifact_sha256"]:
                raise C127Error("同一字段改动的无缓存与缓存结果不一致")
            rows.append(
                {
                    "pair": index + 1,
                    "full_replay_after_field_change_ns": full_ns,
                    "cached_replay_after_field_change_ns": cached_ns,
                    "saved_ns": full_ns - cached_ns,
                }
            )
    full_values = [row["full_replay_after_field_change_ns"] for row in rows]
    cached_values = [row["cached_replay_after_field_change_ns"] for row in rows]
    full_median = int(statistics.median(full_values))
    cached_median = int(statistics.median(cached_values))
    return {
        "schema_version": f"{SCHEMA_VERSION}.runtime-timing-observation",
        "replayed_item": "C11.3_SOURCE_COVERAGE_LEDGER",
        "single_changed_field": "score.display_precision",
        "pair_count": repetitions,
        "rows": rows,
        "full_replay_median_ns": full_median,
        "cached_replay_median_ns": cached_median,
        "median_saved_ns": full_median - cached_median,
        "cached_median_faster_observed": cached_median < full_median,
        "nondeterministic_observation": True,
        "pass_is_not_conditioned_on_wall_clock_speed": True,
        "no_sleep_or_synthetic_delay": True,
    }


def build_cache_contract() -> dict[str, Any]:
    return {
        "schema_version": f"{SCHEMA_VERSION}.cache-contract",
        "stage_order": list(STAGE_ORDER),
        "stages": [_stage_contract(stage) for stage in STAGE_ORDER],
        "key_contract": {
            "algorithm": "SHA256",
            "canonicalization_version": CANONICALIZATION_VERSION,
            "roles_are_bound": True,
            "content_bytes_are_bound": True,
            "stage_config_is_bound": True,
            "stage_implementation_source_is_bound": True,
            "python_runtime_lock_is_bound": True,
            "upstream_stage_keys_are_bound": True,
            "forbidden_identity_fields": sorted(FORBIDDEN_KEY_FIELDS),
            "path_filename_timestamp_used": False,
        },
        "cache_hit_contract": {
            "artifact_sha_recomputed": True,
            "manifest_closed_file_set_required": True,
            "same_key_different_payload_rejected": True,
            "independent_content_index_required": True,
            "delivery_receipt_binds_content_index_sha": True,
            "threat_boundary": (
                "能检出载荷与条目 manifest 同步漂移；若攻击者同时改写缓存、"
                "独立索引与稳定交付票，仍需仓外签名信任根，本候选未宣称具备。"
            ),
        },
        "candidate_foundation_only": True,
        "runtime_connected": False,
    }


def _write_stable(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise C127Error(f"既有稳定工件字节漂移：{path}")
    path.write_bytes(raw)


def _stable_manifest(files: Mapping[str, bytes]) -> dict[str, Any]:
    rows = [
        {"path": path, "sha256": sha256_bytes(raw), "byte_count": len(raw)}
        for path, raw in sorted(files.items())
    ]
    return {
        "schema_version": f"{SCHEMA_VERSION}.artifact-manifest",
        "status": "PASS_CANDIDATE_FOUNDATION_NOT_RUNTIME_CONNECTED",
        "stable_files": rows,
        "stable_artifact_set_sha256": canonical_sha(
            {row["path"]: row["sha256"] for row in rows}
        ),
        "volatile_observation_files": ["runtime_timing_observation.json"],
        "volatile_files_excluded_from_stable_sha": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def write_delivery(
    artifacts_dir: Path = DEFAULT_ARTIFACTS,
    cache_root: Path = DEFAULT_CACHE,
) -> dict[str, Any]:
    assert_writable_target(artifacts_dir)
    assert_writable_target(cache_root)
    smoke = run_smoke_set()
    demo = run_cache_demo(cache_root)
    timing = run_timing_observation()
    contract = build_cache_contract()
    readme = (
        "# C12.7｜分段缓存与固定冒烟集\n\n"
        "这是一套 0 API 的候选地基：用内容 SHA 给 extract → normalize → "
        "crosswalk → score → report 五段做缓存，并固定 8 条历史难例先跑冒烟。\n\n"
        "它只用 C11.3 已完成工件做只读回放，没有接入现役运行器，也不登记语义或质量胜负。"
        "墙钟耗时单列为易波动观察，不进入稳定工件 SHA。\n\n"
        "来源：Codex\n"
    ).encode("utf-8")
    stable = {
        "cache_contract_v1.json": canonical_json_bytes(contract),
        "cache_replay_receipt.json": canonical_json_bytes(demo),
        "smoke_receipt.json": canonical_json_bytes(smoke),
        "README.md": readme,
    }
    manifest = _stable_manifest(stable)
    for name, raw in stable.items():
        _write_stable(artifacts_dir / name, raw)
    _write_stable(
        artifacts_dir / "artifact_manifest.json",
        canonical_json_bytes(manifest),
    )
    timing_path = artifacts_dir / "runtime_timing_observation.json"
    if timing_path.exists():
        verify_timing_observation(read_json(timing_path))
    else:
        timing_path.write_bytes(canonical_json_bytes(timing))
    verify_delivery(artifacts_dir, cache_root)
    return manifest


def verify_timing_observation(document: Mapping[str, Any]) -> None:
    if (
        document.get("schema_version")
        != f"{SCHEMA_VERSION}.runtime-timing-observation"
        or document.get("nondeterministic_observation") is not True
        or document.get("pass_is_not_conditioned_on_wall_clock_speed") is not True
        or document.get("no_sleep_or_synthetic_delay") is not True
        or not isinstance(document.get("rows"), list)
        or len(document["rows"]) < 3
    ):
        raise C127Error("计时观察票结构非法")
    for row in document["rows"]:
        if (
            not isinstance(row.get("full_replay_after_field_change_ns"), int)
            or not isinstance(row.get("cached_replay_after_field_change_ns"), int)
            or row["full_replay_after_field_change_ns"] <= 0
            or row["cached_replay_after_field_change_ns"] <= 0
        ):
            raise C127Error("计时观察含非法耗时")


def verify_delivery(
    artifacts_dir: Path = DEFAULT_ARTIFACTS,
    cache_root: Path = DEFAULT_CACHE,
) -> dict[str, Any]:
    expected_contract = canonical_json_bytes(build_cache_contract())
    expected_smoke = canonical_json_bytes(run_smoke_set())
    stable_names = {
        "README.md",
        "artifact_manifest.json",
        "cache_contract_v1.json",
        "cache_replay_receipt.json",
        "runtime_timing_observation.json",
        "smoke_receipt.json",
    }
    if {path.name for path in artifacts_dir.iterdir()} != stable_names:
        raise C127Error("C12.7 交付目录文件集合不闭合")
    if (artifacts_dir / "cache_contract_v1.json").read_bytes() != expected_contract:
        raise C127Error("缓存合同不能重建")
    if (artifacts_dir / "smoke_receipt.json").read_bytes() != expected_smoke:
        raise C127Error("冒烟票不能重建")
    demo = read_json(artifacts_dir / "cache_replay_receipt.json")
    if (
        demo.get("cold_run", {}).get("executed_stages") != list(STAGE_ORDER)
        or demo.get("warm_run", {}).get("cache_hit_stages") != list(STAGE_ORDER)
        or demo.get("single_field_change_run", {}).get("executed_stages")
        != ["score", "report"]
        or demo.get("single_field_change_run", {}).get("cache_hit_stages")
        != ["extract", "normalize", "crosswalk"]
    ):
        raise C127Error("缓存回放票执行集合非法")
    warm = run_pipeline(cache_root, cache_write_allowed=False)
    if warm["cache_hit_stages"] != list(STAGE_ORDER):
        raise C127Error("实际 demo cache 不能五段命中")
    if verify_cache_index(cache_root) != demo.get("cache_content_index"):
        raise C127Error("缓存独立内容索引未被稳定回放票绑定")
    timing = read_json(artifacts_dir / "runtime_timing_observation.json")
    verify_timing_observation(timing)

    manifest = read_json(artifacts_dir / "artifact_manifest.json")
    stable_files = {
        row["path"]: (artifacts_dir / row["path"]).read_bytes()
        for row in manifest.get("stable_files", [])
    }
    expected_manifest = _stable_manifest(stable_files)
    if manifest != expected_manifest:
        raise C127Error("稳定工件 manifest 不能按磁盘实物重建")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    validate_runtime()
    parser = argparse.ArgumentParser(description="C12.7 分段缓存与固定冒烟集")
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        manifest = verify_delivery(args.artifacts_dir, args.cache_root)
    else:
        manifest = write_delivery(args.artifacts_dir, args.cache_root)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "stable_artifact_set_sha256": manifest[
                    "stable_artifact_set_sha256"
                ],
                "model_api_calls": 0,
                "network_requests": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

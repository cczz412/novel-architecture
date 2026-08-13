#!/usr/bin/env python3
"""微调域的机械索引与外审包等价复建工具。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DOMAIN_ROOT = ROOT / "finetuning"
LOCAL_STORES = ROOT / ".local/finetuning/stores.local.json"


class HardStop(RuntimeError):
    """输入事实缺失或相互冲突，不能继续派生。"""


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HardStop(f"无法读取 JSON：{path}：{exc}") from exc


def jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, 1):
                if not raw.strip():
                    raise HardStop(f"JSONL 含空行：{path}:{line_no}")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise HardStop(f"JSONL 行不是对象：{path}:{line_no}")
                rows.append(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise HardStop(f"无法解析 JSONL：{path}：{exc}") from exc
    return rows


def _assistant_facts(row: dict[str, Any], path: Path) -> int:
    raw: Any = row.get("assistant")
    if raw is None:
        messages = row.get("messages")
        if not isinstance(messages, list):
            raise HardStop(f"训练行缺 messages：{path}")
        candidates = [
            item.get("content")
            for item in messages
            if isinstance(item, dict) and item.get("role") == "assistant"
        ]
        if len(candidates) != 1:
            raise HardStop(f"训练行 assistant 数量不是 1：{path}")
        raw = candidates[0]
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise HardStop(f"assistant 不是合法 JSON：{path}：{exc}") from exc
    facts = payload.get("facts") if isinstance(payload, dict) else None
    if not isinstance(facts, list):
        raise HardStop(f"assistant 缺 facts 数组：{path}")
    return len(facts)


def jsonl_stats(path: Path, *, count_facts: bool = False) -> dict[str, int]:
    rows = jsonl_rows(path)
    stats = {"rows": len(rows)}
    if count_facts:
        stats["facts"] = sum(_assistant_facts(row, path) for row in rows)
    return stats


def load_current() -> tuple[dict[str, Any], Path, dict[str, Any]]:
    current = load_json(DOMAIN_ROOT / "CURRENT.json")
    experiment_id = current.get("current_experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id:
        raise HardStop("CURRENT.json 缺 experiment_id")
    experiment_dir = DOMAIN_ROOT / "experiments" / experiment_id
    spec_path = experiment_dir / "SPEC.json"
    spec = load_json(spec_path)
    if spec.get("experiment_id") != experiment_id:
        raise HardStop("CURRENT.json 与 SPEC.json 的 experiment_id 不一致")
    return spec, experiment_dir, current


def load_stores() -> dict[str, Path]:
    logical = load_json(DOMAIN_ROOT / "stores.json")
    local = load_json(LOCAL_STORES)
    logical_ids = set((logical.get("stores") or {}).keys())
    bindings = local.get("stores") or {}
    if set(bindings) != logical_ids:
        raise HardStop("逻辑仓位与本机仓位绑定不一致")
    resolved: dict[str, Path] = {}
    for store_id, raw in bindings.items():
        path = Path(raw)
        if not path.is_absolute() or not path.exists():
            raise HardStop(f"仓位未绑定到现存绝对路径：{store_id}")
        resolved[store_id] = path.resolve()
    return resolved


def safe_file(store_root: Path, relative_path: str) -> Path:
    store_root = store_root.resolve()
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise HardStop(f"相对路径不安全：{relative_path}")
    path = store_root / Path(*pure.parts)
    if path.is_symlink() or not path.is_file():
        raise HardStop(f"文件缺失或为软链：{path}")
    resolved = path.resolve()
    try:
        resolved.relative_to(store_root)
    except ValueError as exc:
        raise HardStop(f"文件越出仓位：{path}") from exc
    return resolved


def _artifact_role(relative_path: str) -> str:
    name = PurePosixPath(relative_path).name
    if name == "adapters.safetensors":
        return "model_adapter"
    if name == "MODEL_RECEIPT.json":
        return "base_model_identity"
    if "/private_gold/" in f"/{relative_path}":
        return "private_evaluation_gold"
    if relative_path.endswith("QUESTIONS.jsonl"):
        return "evaluation_questions"
    if relative_path.endswith("train.jsonl") or "/datasets/" in relative_path:
        return "training_dataset"
    if relative_path.endswith("RAW_OUTPUTS.jsonl"):
        return "evaluation_outputs"
    if relative_path.endswith(".log"):
        return "training_or_evaluation_log"
    if relative_path.endswith(".py"):
        return "execution_code"
    return "experiment_evidence"


def collect_artifacts(
    spec: dict[str, Any], stores: dict[str, Path]
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    artifacts: list[dict[str, Any]] = []
    review_sets: dict[str, list[str]] = {}
    seen: set[tuple[str, str]] = set()
    for group in spec.get("artifact_groups") or []:
        store_id = group.get("store_id")
        if store_id not in stores:
            raise HardStop(f"未知仓位：{store_id}")
        base_rel = str(group.get("base_relative_path") or "")
        store_root = stores[store_id].resolve()
        base = store_root / base_rel
        if not base.is_dir() or base.is_symlink():
            raise HardStop(f"材料目录缺失或为软链：{base}")
        group_paths: set[Path] = set()
        for pattern in group.get("patterns") or []:
            matches = sorted(path for path in base.glob(pattern) if path.is_file())
            if not matches and group.get("required"):
                raise HardStop(f"required pattern 缺件：{group.get('group_id')}:{pattern}")
            group_paths.update(matches)
        for path in sorted(group_paths):
            if path.is_symlink():
                raise HardStop(f"材料不得是软链：{path}")
            rel = path.resolve().relative_to(store_root).as_posix()
            key = (store_id, rel)
            if key in seen:
                raise HardStop(f"同一材料被重复登记：{store_id}:{rel}")
            seen.add(key)
            entry = {
                "artifact_id": f"{group.get('group_id')}::{rel}",
                "group_id": group.get("group_id"),
                "role": _artifact_role(rel),
                "store_id": store_id,
                "relative_path": rel,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "visibility": (
                    "private_identity_only"
                    if "/private_gold/" in f"/{rel}"
                    else "internal"
                ),
            }
            review_set = group.get("review_set")
            if review_set:
                entry["review_set"] = review_set
                local_rel = path.resolve().relative_to(base.resolve()).as_posix()
                review_sets.setdefault(str(review_set), []).append(local_rel)
            artifacts.append(entry)
    artifacts.sort(key=lambda row: (row["store_id"], row["relative_path"]))
    for rows in review_sets.values():
        rows.sort()
    return artifacts, review_sets


def _experiment_file(stores: dict[str, Path], spec: dict[str, Any], rel: str) -> Path:
    source = spec.get("source_root") or {}
    store_id = source.get("store_id")
    base_rel = source.get("relative_path")
    return safe_file(stores[store_id], f"{base_rel}/{rel}")


def derive_facts(
    spec: dict[str, Any], stores: dict[str, Path], review_sets: dict[str, list[str]]
) -> dict[str, Any]:
    def exp(rel: str) -> Path:
        return _experiment_file(stores, spec, rel)

    full_a = jsonl_stats(exp("sealed/datasets/a/full_a.jsonl"), count_facts=True)
    full_c = jsonl_stats(exp("sealed/datasets/c/full_c.jsonl"), count_facts=True)
    pos_a = jsonl_stats(exp("sealed/datasets/a/stage_1_positive_a.jsonl"), count_facts=True)
    pos_c = jsonl_stats(exp("sealed/datasets/c/stage_1_positive_c.jsonl"), count_facts=True)
    special_a = jsonl_stats(exp("sealed/datasets/a/stage_2_special_a.jsonl"), count_facts=True)
    special_c = jsonl_stats(exp("sealed/datasets/c/stage_2_special_c.jsonl"), count_facts=True)
    old_a = jsonl_stats(exp("sealed/exams/a/QUESTIONS.jsonl"))
    old_c = jsonl_stats(exp("sealed/exams/c/QUESTIONS.jsonl"))
    current_a = jsonl_stats(exp("exam_rebalance_r03/sealed/a/QUESTIONS.jsonl"))
    current_c = jsonl_stats(exp("exam_rebalance_r03/sealed/c/QUESTIONS.jsonl"))
    gold_a = jsonl_stats(
        exp("exam_rebalance_r03/sealed/private_gold/a/GOLD.jsonl"), count_facts=True
    )
    gold_c = jsonl_stats(
        exp("exam_rebalance_r03/sealed/private_gold/c/GOLD.jsonl"), count_facts=True
    )
    raw_a = jsonl_stats(exp("exam_rebalance_r03/results/arm_a/RAW_OUTPUTS.jsonl"))
    raw_c = jsonl_stats(exp("exam_rebalance_r03/results/arm_c/RAW_OUTPUTS.jsonl"))

    equal_pairs = {
        "full_rows": (full_a["rows"], full_c["rows"]),
        "full_facts": (full_a["facts"], full_c["facts"]),
        "stage1_rows": (pos_a["rows"], pos_c["rows"]),
        "stage1_facts": (pos_a["facts"], pos_c["facts"]),
        "stage2_rows": (special_a["rows"], special_c["rows"]),
        "stage2_facts": (special_a["facts"], special_c["facts"]),
        "old_exam_rows": (old_a["rows"], old_c["rows"]),
        "current_exam_rows": (current_a["rows"], current_c["rows"]),
        "current_gold_rows": (gold_a["rows"], gold_c["rows"]),
        "current_gold_facts": (gold_a["facts"], gold_c["facts"]),
        "raw_output_rows": (raw_a["rows"], raw_c["rows"]),
    }
    mismatches = {name: values for name, values in equal_pairs.items() if values[0] != values[1]}
    if mismatches:
        raise HardStop(f"A/C 分母不一致：{mismatches}")

    training_rows = pos_a["rows"] + special_a["rows"]
    if full_a["rows"] != training_rows + old_a["rows"]:
        raise HardStop("母集行数不等于训练分层加旧冻结隔离卷")
    if current_a["rows"] != gold_a["rows"] or current_a["rows"] != raw_a["rows"]:
        raise HardStop("当前考卷、金标与答卷行数不一致")

    runtime_pairs = {
        "a_stage1": (
            exp("runtime_data/a_stage1_positive/train.jsonl"),
            exp("sealed/datasets/a/stage_1_positive_a.jsonl"),
        ),
        "a_stage2": (
            exp("runtime_data/a_stage2_special/train.jsonl"),
            exp("sealed/datasets/a/stage_2_special_a.jsonl"),
        ),
        "c_stage1": (
            exp("runtime_data/c_stage1_positive/train.jsonl"),
            exp("sealed/datasets/c/stage_1_positive_c.jsonl"),
        ),
        "c_stage2": (
            exp("runtime_data/c_stage2_special/train.jsonl"),
            exp("sealed/datasets/c/stage_2_special_c.jsonl"),
        ),
    }
    runtime_checks: dict[str, str] = {}
    for label, (runtime_path, sealed_path) in runtime_pairs.items():
        if sha256_file(runtime_path) != sha256_file(sealed_path):
            raise HardStop(f"训练器实吃文件与封版分层不一致：{label}")
        runtime_checks[label] = "BYTE_IDENTICAL"

    metrics = load_json(exp("exam_rebalance_r03/results/AC_MACHINE_METRICS.json"))
    arm_a = metrics.get("arm_a") or {}
    arm_c = metrics.get("arm_c") or {}
    if arm_a.get("segments") != current_a["rows"] or arm_c.get("segments") != current_c["rows"]:
        raise HardStop("机器成绩的考卷分母与实物不一致")
    if arm_a.get("gold_facts") != gold_a["facts"] or arm_c.get("gold_facts") != gold_c["facts"]:
        raise HardStop("机器成绩的金标分母与实物不一致")

    return {
        "full_rows_each_arm": full_a["rows"],
        "full_facts_each_arm": full_a["facts"],
        "training_rows_each_arm": training_rows,
        "stage_1_positive_rows_each_arm": pos_a["rows"],
        "stage_1_positive_facts_each_arm": pos_a["facts"],
        "stage_2_special_rows_each_arm": special_a["rows"],
        "stage_2_special_facts_each_arm": special_a["facts"],
        "old_frozen_exam_rows_each_arm": old_a["rows"],
        "current_exam_rows_each_arm": current_a["rows"],
        "current_gold_facts_each_arm": gold_a["facts"],
        "raw_answer_records_total": raw_a["rows"] + raw_c["rows"],
        "runtime_matches_sealed": runtime_checks,
        "review_sets": {key: len(value) for key, value in sorted(review_sets.items())},
        "machine_metrics": {
            "arm_a": {
                "format_valid_segments": arm_a.get("format_valid_segments"),
                "max_output_reached_segments": arm_a.get("max_output_reached_segments"),
                "repeated_fact_loop_segments": arm_a.get("repeated_fact_loop_segments"),
                "predicted_facts": arm_a.get("predicted_facts"),
            },
            "arm_c": {
                "format_valid_segments": arm_c.get("format_valid_segments"),
                "max_output_reached_segments": arm_c.get("max_output_reached_segments"),
                "repeated_fact_loop_segments": arm_c.get("repeated_fact_loop_segments"),
                "predicted_facts": arm_c.get("predicted_facts"),
                "pointer_valid_facts": (
                    (arm_c.get("pointer_and_anchor_legality") or {}).get("valid_facts")
                ),
            },
        },
    }


def build_manifest() -> tuple[dict[str, Any], bytes, Path, dict[str, Path]]:
    spec, experiment_dir, _ = load_current()
    stores = load_stores()
    artifacts, review_sets = collect_artifacts(spec, stores)
    facts = derive_facts(spec, stores, review_sets)
    manifest = {
        "schema_version": "finetuning-experiment-manifest-v1",
        "experiment_id": spec["experiment_id"],
        "manifest_revision": spec["manifest_revision"],
        "spec_sha256": sha256_file(experiment_dir / "SPEC.json"),
        "state": spec["state"],
        "source_root": spec["source_root"],
        "artifacts": artifacts,
        "derived_facts": facts,
        "boundaries": spec["boundaries"],
    }
    return manifest, canonical_json(manifest), experiment_dir, stores


def render_summary(manifest: dict[str, Any], manifest_sha: str) -> bytes:
    facts = manifest["derived_facts"]
    text = f"""# {manifest['experiment_id']}｜机器事实摘要

这页由真实文件和封版 MANIFEST 机械生成，不含小说正文、私有金标或人工胜负判断。

- MANIFEST SHA：`{manifest_sha}`
- A/C 每臂母集：{facts['full_rows_each_arm']} 行
- A/C 每臂实际训练：{facts['training_rows_each_arm']} 行（正向 {facts['stage_1_positive_rows_each_arm']}＋特殊 {facts['stage_2_special_rows_each_arm']}）
- 旧冻结隔离卷：每臂 {facts['old_frozen_exam_rows_each_arm']} 题
- 当前 R03 考卷：每臂 {facts['current_exam_rows_each_arm']} 题
- 当前 R03 金标：每臂 {facts['current_gold_facts_each_arm']} 条事实
- 当前原始答卷：共 {facts['raw_answer_records_total']} 份

这份摘要不授权训练、转正、迁移或删除。人工判断只写入绑定本 MANIFEST SHA 的 `DECISION.md`。

来源：Codex
"""
    return text.encode("utf-8")


def write_create_only(path: Path, data: bytes) -> str:
    if path.exists():
        current = path.read_bytes()
        if current != data:
            raise HardStop(f"封版文件已存在且内容不同，拒绝覆盖：{path}")
        return "UNCHANGED"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return "CREATED"


def command_build() -> int:
    manifest, data, experiment_dir, _ = build_manifest()
    manifest_sha = sha256_bytes(data)
    manifest_state = write_create_only(experiment_dir / "MANIFEST.json", data)
    sha_state = write_create_only(
        experiment_dir / "MANIFEST.sha256", f"{manifest_sha}  MANIFEST.json\n".encode()
    )
    summary_state = write_create_only(
        experiment_dir / "SUMMARY.md", render_summary(manifest, manifest_sha)
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "manifest": manifest_state,
                "manifest_sha256": manifest_sha,
                "sha_file": sha_state,
                "summary": summary_state,
                "derived_facts": manifest["derived_facts"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_check() -> int:
    spec, experiment_dir, current = load_current()
    if spec.get("schema_version") == "finetuning-experiment-spec-v2":
        # R02 起的新实验由通用控制面负责从 SPEC 重建 MANIFEST。这里保留
        # 旧命令入口，但不能再拿 R01 写死的 A/C 目录结构去检查新实验。
        from finetuning_control import build_manifest_v2, validate_manifest_artifacts

        manifest, expected, rebuilt_dir = build_manifest_v2(spec["experiment_id"])
        if rebuilt_dir != experiment_dir:
            raise HardStop("v2 MANIFEST 重建目录与 CURRENT 指向不一致")
        manifest_path = experiment_dir / "MANIFEST.json"
        if not manifest_path.exists() or manifest_path.read_bytes() != expected:
            raise HardStop("现存 v2 MANIFEST 与真实文件重新计算结果不一致")
        manifest_sha = sha256_bytes(expected)
        if current.get("manifest_sha256") != manifest_sha:
            raise HardStop("CURRENT.json 绑定的 MANIFEST SHA 与真实文件不一致")
        expected_line = f"{manifest_sha}  MANIFEST.json\n".encode()
        if (experiment_dir / "MANIFEST.sha256").read_bytes() != expected_line:
            raise HardStop("MANIFEST.sha256 与 v2 MANIFEST 不一致")
        validate_manifest_artifacts(manifest)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "checker": "v2_generic_control",
                    "manifest_sha256": manifest_sha,
                },
                indent=2,
            )
        )
        return 0

    _, expected, experiment_dir, _ = build_manifest()
    manifest_path = experiment_dir / "MANIFEST.json"
    if not manifest_path.exists() or manifest_path.read_bytes() != expected:
        raise HardStop("现存 MANIFEST 与真实文件重新计算结果不一致")
    manifest_sha = sha256_bytes(expected)
    expected_line = f"{manifest_sha}  MANIFEST.json\n".encode()
    if (experiment_dir / "MANIFEST.sha256").read_bytes() != expected_line:
        raise HardStop("MANIFEST.sha256 与 MANIFEST 不一致")
    print(json.dumps({"status": "PASS", "manifest_sha256": manifest_sha}, indent=2))
    return 0


PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def render_template(path: Path, values: dict[str, Any]) -> bytes:
    text = path.read_text(encoding="utf-8")
    needed = set(PLACEHOLDER.findall(text))
    missing = needed - set(values)
    if missing:
        raise HardStop(f"模板变量缺失：{path}:{sorted(missing)}")
    rendered = PLACEHOLDER.sub(lambda match: str(values[match.group(1)]), text)
    if PLACEHOLDER.search(rendered):
        raise HardStop(f"模板仍有未替换变量：{path}")
    return rendered.encode("utf-8")


def _zip_member_hashes(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        return {name: sha256_bytes(archive.read(name)) for name in sorted(archive.namelist())}


def command_package_equivalence() -> int:
    manifest, manifest_bytes, experiment_dir, stores = build_manifest()
    stored_manifest = experiment_dir / "MANIFEST.json"
    if not stored_manifest.exists() or stored_manifest.read_bytes() != manifest_bytes:
        raise HardStop("必须先封版并核验 MANIFEST")
    profiles = manifest.get("derived_facts", {}).get("review_sets", {})
    spec = load_json(experiment_dir / "SPEC.json")
    review_profile = (spec.get("review_profiles") or [None])[0]
    if not review_profile:
        raise HardStop("SPEC 缺 review profile")

    sys.path.insert(0, str(ROOT / "tools"))
    import chatgpt_review_pack as packer  # type: ignore
    from pipeline_common import artifacts as artifact_tools  # type: ignore

    route_id = review_profile["route_id"]
    routes = packer._load_routes()
    route = (routes.get("routes") or {}).get(route_id)
    if not route:
        raise HardStop(f"旧 route 不存在：{route_id}")
    layers = list(route.get("default_layers") or [])
    payloads, notes, selection = packer.collect_route_payloads(
        route_id, layers, [], packer._load_profiles()
    )

    review_set = review_profile["review_set"]
    expected_rel = sorted(
        path.resolve().relative_to(
            (stores[spec["source_root"]["store_id"]] / spec["source_root"]["relative_path"]).resolve()
        ).as_posix()
        for path in [
            safe_file(stores[row["store_id"]], row["relative_path"])
            for row in manifest["artifacts"]
            if row.get("review_set") == review_set
        ]
    )
    if profiles.get(review_set) != len(expected_rel):
        raise HardStop("MANIFEST review_set 计数不一致")
    legacy_prefix = review_profile["legacy_member_prefix"].rstrip("/")
    actual_members = sorted(
        member[len(legacy_prefix) + 1 :]
        for member in payloads
        if member.startswith(legacy_prefix + "/")
    )
    if actual_members != expected_rel:
        raise HardStop("旧 route 当前实验选材与 MANIFEST review_set 不一致")

    experiment_root = (
        stores[spec["source_root"]["store_id"]] / spec["source_root"]["relative_path"]
    )
    for rel in expected_rel:
        member = f"{legacy_prefix}/{rel}"
        real_bytes = (experiment_root / rel).read_bytes()
        if payloads[member] != real_bytes:
            raise HardStop(f"旧 route 副本与真实实验文件不一致：{rel}")
        payloads[member] = real_bytes

    facts = manifest["derived_facts"]
    arm_a = facts["machine_metrics"]["arm_a"]
    arm_c = facts["machine_metrics"]["arm_c"]
    current_metrics = load_json(
        experiment_root / "exam_rebalance_r03/results/AC_MACHINE_METRICS.json"
    )
    run_lock = load_json(
        experiment_root / "exam_rebalance_r03/results/EXAM_RUN_LOCK.json"
    )
    exact_f1_a = ((current_metrics.get("arm_a") or {}).get("exact_record") or {}).get("f1")
    exact_f1_c = ((current_metrics.get("arm_c") or {}).get("exact_record") or {}).get("f1")
    if exact_f1_a != exact_f1_c:
        raise HardStop("A/C 严格 F1 不同，不能渲染为共享值")
    max_output_tokens = (run_lock.get("decode") or {}).get("max_output_tokens")
    if not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
        raise HardStop("考试运行锁缺合法输出上限")
    values = {
        "FULL_ROWS_EACH_ARM": facts["full_rows_each_arm"],
        "TRAINING_ROWS_EACH_ARM": facts["training_rows_each_arm"],
        "STAGE1_ROWS_EACH_ARM": facts["stage_1_positive_rows_each_arm"],
        "STAGE2_ROWS_EACH_ARM": facts["stage_2_special_rows_each_arm"],
        "OLD_EXAM_ROWS_EACH_ARM": facts["old_frozen_exam_rows_each_arm"],
        "CURRENT_EXAM_ROWS_EACH_ARM": facts["current_exam_rows_each_arm"],
        "CURRENT_GOLD_FACTS_EACH_ARM": facts["current_gold_facts_each_arm"],
        "RAW_ANSWER_RECORDS_TOTAL": facts["raw_answer_records_total"],
        "MAX_OUTPUT_TOKENS": max_output_tokens,
        "STRICT_F1_SHARED": (
            int(exact_f1_a)
            if isinstance(exact_f1_a, float) and exact_f1_a.is_integer()
            else exact_f1_a
        ),
        "A_FORMAT_VALID": arm_a["format_valid_segments"],
        "A_MAX_OUTPUT_REACHED": arm_a["max_output_reached_segments"],
        "A_REPEAT_SEGMENTS": arm_a["repeated_fact_loop_segments"],
        "C_FORMAT_VALID": arm_c["format_valid_segments"],
        "C_MAX_OUTPUT_REACHED": arm_c["max_output_reached_segments"],
        "C_REPEAT_SEGMENTS": arm_c["repeated_fact_loop_segments"],
        "C_PREDICTED_FACTS": arm_c["predicted_facts"],
        "C_POINTER_VALID_FACTS": arm_c["pointer_valid_facts"],
        "PACKAGE_SOURCE_COUNT": selection["source_count"],
        "CURRENT_EXPERIMENT_SOURCE_COUNT": len(expected_rel),
        "SECRET_HIT_COUNT": 0,
    }
    truth_templates = review_profile.get("generated_truth_templates") or {}
    for basename, template_rel in truth_templates.items():
        matches = [member for member in payloads if PurePosixPath(member).name == basename]
        if len(matches) != 1:
            raise HardStop(f"外审真源文件不是唯一命中：{basename}:{matches}")
        payloads[matches[0]] = render_template(experiment_dir / template_rel, values)

    baseline = safe_file(
        stores[review_profile["baseline_zip"]["store_id"]],
        review_profile["baseline_zip"]["relative_path"],
    )
    with zipfile.ZipFile(baseline) as archive:
        baseline_manifest = json.loads(archive.read("MANIFEST.json"))
    generated_at = datetime.fromisoformat(baseline_manifest["metadata"]["created_at"])
    route_map = packer.render_route_map(selection, file_count=len(payloads), generated_at=generated_at)
    packer._add_payload(payloads, "00_ROUTE_MAP.md", route_map)
    packer._add_payload(payloads, "_route/ROUTE_SELECTION.json", canonical_json(selection))
    packer._add_payload(payloads, "00_READ_ME_FOR_REVIEWER.md", route_map)
    if route.get("redact_local_absolute_paths"):
        payloads, redaction = packer._redact_local_absolute_paths(payloads)
        packer._add_payload(payloads, "_route/LOCAL_PATH_REDACTION.json", canonical_json(redaction))
    secret_scan = packer._scan_secret_values(payloads)
    if secret_scan["result"] != "PASS" or secret_scan["hit_count"] != values["SECRET_HIT_COUNT"]:
        raise HardStop("外审包密钥扫描失败或与模板声明不一致")
    packer._add_payload(payloads, "_route/SECRET_SCAN.json", canonical_json(secret_scan))

    out_dir = ROOT / "TEMP/finetuning_r01"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "ac_root_cause_r02_equivalence.zip"
    receipt = artifact_tools.write_verified_zip(
        output,
        payloads,
        metadata=baseline_manifest["metadata"],
    )
    expected_hashes = _zip_member_hashes(baseline)
    actual_hashes = _zip_member_hashes(output)
    if actual_hashes != expected_hashes:
        missing = sorted(set(expected_hashes) - set(actual_hashes))
        extra = sorted(set(actual_hashes) - set(expected_hashes))
        changed = sorted(
            key for key in set(actual_hashes) & set(expected_hashes)
            if actual_hashes[key] != expected_hashes[key]
        )
        raise HardStop(f"复建包不等价：missing={missing}, extra={extra}, changed={changed}")

    package_receipt = {
        "schema_version": "finetuning-r01-package-equivalence-v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "PASS_BYTE_EQUIVALENT_MEMBER_SET_AND_SHA",
        "experiment_id": manifest["experiment_id"],
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "baseline_zip": {
            "relative_path": review_profile["baseline_zip"]["relative_path"],
            "sha256": sha256_file(baseline),
        },
        "rebuilt_zip": {
            "relative_path": output.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output),
        },
        "member_count": len(actual_hashes),
        "source_count": selection["source_count"],
        "current_experiment_source_count": len(expected_rel),
        "zip_verification_passed": receipt["passed"],
        "notes": notes,
    }
    receipt_path = out_dir / "PACKAGE_EQUIVALENCE_RECEIPT.json"
    receipt_path.write_bytes(canonical_json(package_receipt))
    print(json.dumps(package_receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def command_acceptance() -> int:
    manifest_a, data_a, experiment_dir, _ = build_manifest()
    manifest_b, data_b, _, _ = build_manifest()
    if data_a != data_b or manifest_a != manifest_b:
        raise HardStop("同一批真实文件连续构建的 MANIFEST 不一致")
    manifest_path = experiment_dir / "MANIFEST.json"
    if not manifest_path.exists() or manifest_path.read_bytes() != data_a:
        raise HardStop("封版 MANIFEST 与当前真实文件不一致")

    package_receipt_path = ROOT / "TEMP/finetuning_r01/PACKAGE_EQUIVALENCE_RECEIPT.json"
    package_receipt = load_json(package_receipt_path)
    if package_receipt.get("status") != "PASS_BYTE_EQUIVALENT_MEMBER_SET_AND_SHA":
        raise HardStop("当前外审包等价复建尚未通过")
    if package_receipt.get("manifest_sha256") != sha256_bytes(data_a):
        raise HardStop("外审包等价票没有绑定当前 MANIFEST")

    facts = manifest_a["derived_facts"]
    measured_keys = [
        "full_rows_each_arm",
        "training_rows_each_arm",
        "stage_1_positive_rows_each_arm",
        "stage_2_special_rows_each_arm",
        "current_exam_rows_each_arm",
        "current_gold_facts_each_arm",
        "raw_answer_records_total",
    ]
    measured_values = [str(facts[key]) for key in measured_keys]
    measured_values.append(str(package_receipt["source_count"]))
    source_paths = [Path(__file__)] + sorted((experiment_dir / "templates").glob("*.tmpl"))
    hardcoded_hits: list[dict[str, Any]] = []
    for path in source_paths:
        text = path.read_text(encoding="utf-8")
        for value in measured_values:
            if re.search(rf"(?<![0-9]){re.escape(value)}(?![0-9])", text):
                hardcoded_hits.append(
                    {"path": path.relative_to(ROOT).as_posix(), "value": value}
                )
    if hardcoded_hits:
        raise HardStop(f"派生源码又写死了业务数字：{hardcoded_hits}")

    receipt = {
        "schema_version": "finetuning-r01-acceptance-v1",
        "status": "PASS_R01_INDEX_LAYER_PROVEN",
        "experiment_id": manifest_a["experiment_id"],
        "manifest_sha256": sha256_bytes(data_a),
        "checks": {
            "current_pointer_locates_experiment_without_search": "PASS",
            "experiment_facts_derived_and_verified": {
                key: facts[key] for key in measured_keys
            },
            "two_consecutive_manifest_builds_byte_identical": "PASS",
            "review_package_member_set_and_member_sha_equivalent": "PASS",
            "generated_business_counts_not_hardcoded_in_builder_or_templates": "PASS",
            "no_asset_move_delete_route_rewrite_notion_or_training": "PASS_SCOPE_OBSERVED",
        },
        "package_equivalence": {
            "receipt": package_receipt_path.relative_to(ROOT).as_posix(),
            "source_count": package_receipt["source_count"],
            "member_count": package_receipt["member_count"],
            "baseline_zip_sha256": package_receipt["baseline_zip"]["sha256"],
            "rebuilt_zip_sha256": package_receipt["rebuilt_zip"]["sha256"],
        },
        "boundary": "R01 adds a mechanical index only; it does not reinterpret history or authorize promotion.",
    }
    receipt_path = experiment_dir / "R01_ACCEPTANCE_RECEIPT.json"
    state = write_create_only(receipt_path, canonical_json(receipt))
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
    parser = argparse.ArgumentParser(description="微调域机械索引")
    parser.add_argument(
        "command", choices=["build", "check", "package-equivalence", "acceptance"]
    )
    args = parser.parse_args()
    try:
        if args.command == "build":
            return command_build()
        if args.command == "check":
            return command_check()
        if args.command == "acceptance":
            return command_acceptance()
        return command_package_equivalence()
    except HardStop as exc:
        print(f"HARD_STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

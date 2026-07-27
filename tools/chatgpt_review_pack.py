#!/usr/bin/env python3
"""ChatGPT／外部强模型 · 审仓打包（可复用）。

默认 profile=standard：复验三角（活面 + experiments/Z* + 近停 runs/reports）+ Z83 票据摘要。
会跟 CURRENT_STATE、扫 tests 引用的 experiments；缺复验脚本则 ABORT。
不把 TEMP／密钥／整棵历史 runs 打进去；外发读盘 ≠ 进 Git。
旧 zip 已外发则不改；缺口改 profiles／本脚本后现打新包。

用法：
  python3 tools/chatgpt_review_pack.py
  python3 tools/chatgpt_review_pack.py --profile deep
  python3 tools/chatgpt_review_pack.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from pipeline_common import artifacts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "config/review_pack/profiles.json"
ROUTES = ROOT / "config/review_pack/routes.json"
OUT_ROOT = ROOT / "TEMP/chatgpt_review_packs"
CURRENT_STATE = ROOT / "governance/CURRENT_STATE.json"
EXPERIMENT_REF_RE = re.compile(r"experiments/Z[A-Za-z0-9_\u4e00-\u9fff-]+")
ROUTE_LAYERS = (
    "current_truth",
    "current_route",
    "upstream_evidence",
    "external_reviews",
)
ROUTE_LAYER_DIRS = {
    "current_truth": "01_current_truth",
    "current_route": "02_current_route",
    "upstream_evidence": "03_upstream_evidence",
    "external_reviews": "04_external_reviews",
}
SECRET_VALUE_PATTERNS = {
    "bearer_token": re.compile(rb"Bearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    "sk_token": re.compile(rb"\bsk-[A-Za-z0-9_-]{12,}\b"),
    "api_key_assignment": re.compile(
        rb"(?:API[_-]?KEY|ACCESS[_-]?TOKEN|SECRET[_-]?KEY)"
        rb"[\"']?\s*[=:]\s*[\"'][A-Za-z0-9._~+/=-]{12,}[\"']",
        re.I,
    ),
}


def _load_profiles() -> dict[str, Any]:
    return json.loads(PROFILES.read_text(encoding="utf-8"))


def _load_routes() -> dict[str, Any]:
    return json.loads(ROUTES.read_text(encoding="utf-8"))


def _iter_glob(pattern: str) -> list[Path]:
    # 支持 runs/Z94_*、governance/**、experiments/Z*/**
    if pattern.endswith("/**"):
        base_pat = pattern[:-3]
        if any(ch in base_pat for ch in "*?["):
            out: list[Path] = []
            for base in ROOT.glob(base_pat):
                if base.is_dir():
                    out.extend(p for p in base.rglob("*") if p.is_file())
                elif base.is_file():
                    out.append(base)
            return out
        base = ROOT / base_pat
        if not base.exists():
            return []
        return [p for p in base.rglob("*") if p.is_file()]
    if "*" in pattern or "?" in pattern:
        return [p for p in ROOT.glob(pattern) if p.exists()]
    p = ROOT / pattern
    if p.is_file():
        return [p]
    if p.is_dir():
        return [x for x in p.rglob("*") if x.is_file()]
    return []


def _expand_tree_or_file(path: Path) -> list[Path]:
    if path.is_dir():
        return [p for p in path.rglob("*") if p.is_file() and not p.is_symlink()]
    if path.is_file() and not path.is_symlink():
        return [path]
    return []


def _manifest_path(path: Path, *, identity_root: Path = ROOT) -> str:
    """把工件身份写成指定根下的相对路径，拒绝把主机绝对路径写进清单。"""

    return path.resolve().relative_to(identity_root.resolve()).as_posix()


def _expand_run_or_report_pattern(pattern: str) -> list[Path]:
    hits = _iter_glob(pattern)
    expanded: list[Path] = []
    for h in hits:
        expanded.extend(_expand_tree_or_file(h))
    if expanded:
        return expanded
    if pattern.startswith("runs/"):
        parent = ROOT / "runs"
        leaf = pattern[len("runs/") :]
        dirs = (
            list(parent.glob(leaf))
            if any(ch in leaf for ch in "*?[")
            else ([parent / leaf] if (parent / leaf).exists() else [])
        )
        for d in dirs:
            expanded.extend(_expand_tree_or_file(d))
    return expanded


def _matches_configured_globs(rel: str, globs: list[str]) -> bool:
    for g in globs:
        if Path(rel).match(g) or Path(rel).match(g.lstrip("/")):
            return True
        # 简单前缀
        if g.endswith("/**") and rel.startswith(g[:-3]):
            return True
    return False


def _excluded(rel: str, exclude_globs: list[str]) -> bool:
    if _matches_configured_globs(rel, exclude_globs):
        return True
    if "__pycache__" in rel.split("/"):
        return True
    return False


def _looks_secret(rel: str, markers: list[str]) -> bool:
    name = Path(rel).name.lower()
    for m in markers:
        m = m.lower()
        if m in name or m in rel.lower():
            if name.startswith(".env") or name.endswith((".pem", ".key", ".p12", ".pfx")):
                return True
            if "hf_token" in name or name.endswith(".env"):
                return True
            if ".env." in name or name == ".env":
                return True
    return name.startswith(".env") or name.endswith((".pem", ".key"))


def _load_current_execution() -> dict[str, Any]:
    if not CURRENT_STATE.is_file():
        return {}
    data = json.loads(CURRENT_STATE.read_text(encoding="utf-8"))
    execution = data.get("current_execution") or {}
    return execution if isinstance(execution, dict) else {}


def _dotted_value(data: dict[str, Any], key: str) -> Any:
    value: Any = data
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _paths_from_current_state(keys: list[str]) -> list[str]:
    execution = _load_current_execution()
    out: list[str] = []
    for key in keys:
        val = _dotted_value(execution, key)
        if isinstance(val, str) and val.startswith(("runs/", "reports/")):
            parts = val.split("/")
            # 目录级：runs/NAME 或 reports/NAME；单文件则仍按父目录收
            if len(parts) >= 2:
                out.append("/".join(parts[:2]))
            else:
                out.append(val)
    # 去重保序
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _experiments_referenced_by_tests() -> list[str]:
    refs: set[str] = set()
    tests = ROOT / "tests"
    if not tests.is_dir():
        return []
    for p in tests.rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        for m in EXPERIMENT_REF_RE.findall(text):
            refs.add(m)
    return sorted(refs)


def collect_files(
    profile: dict[str, Any],
    cfg: dict[str, Any],
    exclude_globs: list[str],
    markers: list[str],
) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    notes: list[str] = []
    for pattern in profile.get("include_globs", []):
        files.extend(_iter_glob(pattern))

    run_patterns = list(profile.get("run_globs", []) or [])
    report_patterns = list(profile.get("report_globs", []) or [])
    if profile.get("follow_current_state"):
        for top in _paths_from_current_state(list(cfg.get("current_state_path_keys") or [])):
            if top.startswith("runs/"):
                run_patterns.append(top)
                notes.append(f"AUTO_FROM_CURRENT_STATE:{top}")
            elif top.startswith("reports/"):
                report_patterns.append(top)
                notes.append(f"AUTO_FROM_CURRENT_STATE:{top}")

    if profile.get("include_test_referenced_experiments"):
        for exp in _experiments_referenced_by_tests():
            files.extend(_iter_glob(f"{exp}/**"))
            notes.append(f"AUTO_TEST_REFERENCED_EXPERIMENT:{exp}")

    for pattern in run_patterns:
        expanded = _expand_run_or_report_pattern(pattern)
        if pattern.startswith("runs/") and not expanded:
            # 静态底线缺失才硬失败；CURRENT_STATE 自动项只记告警
            if pattern in (profile.get("run_globs") or []):
                notes.append(f"MISSING_REQUIRED_RUN_GLOB:{pattern}")
            else:
                notes.append(f"MISSING_AUTO_RUN:{pattern}")
        files.extend(expanded)
    for pattern in report_patterns:
        expanded = _expand_run_or_report_pattern(pattern)
        if pattern.startswith("reports/") and not expanded:
            if pattern in (profile.get("report_globs") or []):
                notes.append(f"MISSING_REPORT_GLOB:{pattern}")
            else:
                notes.append(f"MISSING_AUTO_REPORT:{pattern}")
        files.extend(expanded)

    uniq: dict[str, Path] = {}
    secrets: list[str] = []
    for p in files:
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if _excluded(rel, exclude_globs):
            continue
        if _looks_secret(rel, markers):
            secrets.append(rel)
            continue
        uniq[rel] = p
    if secrets:
        raise SystemExit("ABORT secret-like paths would enter pack:\n  " + "\n  ".join(secrets[:30]))

    if profile.get("require_test_experiment_coverage"):
        packed_rels = set(uniq.keys())
        missing_exp: list[str] = []
        for exp in _experiments_referenced_by_tests():
            prefix = exp.rstrip("/") + "/"
            if not any(r == exp or r.startswith(prefix) for r in packed_rels):
                missing_exp.append(exp)
        if missing_exp:
            raise SystemExit(
                "ABORT 复验三角缺实验脚本（tests 有引用但包里没有）。"
                "改 config/review_pack/profiles.json 后现打新包，勿改已上传旧 zip：\n  "
                + "\n  ".join(missing_exp)
            )

    return sorted(uniq.values(), key=lambda x: x.as_posix()), notes


def _validate_route_pattern(pattern: str) -> None:
    pure = PurePosixPath(pattern)
    if pure.is_absolute() or ".." in pure.parts or "\\" in pattern:
        raise SystemExit(f"ABORT route 路径必须是仓库相对路径且不得越界：{pattern}")
    if not pattern.strip() or pattern.startswith(".git/"):
        raise SystemExit(f"ABORT route 路径不合法：{pattern}")


def _route_pattern_files(pattern: str) -> list[Path]:
    _validate_route_pattern(pattern)
    literal_prefix = re.split(r"[*?[]", pattern, maxsplit=1)[0].rstrip("/")
    prefix = ROOT / literal_prefix if literal_prefix else ROOT
    if prefix.is_symlink():
        raise SystemExit(f"ABORT route 根是软链：{pattern}")
    if prefix.is_dir():
        symlinks = [p for p in prefix.rglob("*") if p.is_symlink()]
        if symlinks:
            rels = [
                p.relative_to(ROOT).as_posix()
                for p in symlinks[:20]
                if p.is_relative_to(ROOT)
            ]
            raise SystemExit(
                f"ABORT route 根内含软链：{pattern}\n  " + "\n  ".join(rels)
            )

    expanded: list[Path] = []
    for hit in _iter_glob(pattern):
        if hit.is_symlink():
            raise SystemExit(f"ABORT route 命中软链：{hit}")
        if hit.is_dir():
            expanded.extend(
                p for p in hit.rglob("*") if p.is_file() and not p.is_symlink()
            )
        elif hit.is_file():
            expanded.append(hit)

    safe: dict[str, Path] = {}
    root_resolved = ROOT.resolve()
    for path in expanded:
        if path.is_symlink():
            raise SystemExit(f"ABORT route 命中软链：{path}")
        try:
            path.resolve().relative_to(root_resolved)
        except ValueError as exc:
            raise SystemExit(f"ABORT route 路径逃逸仓库：{path}") from exc
        safe[path.relative_to(ROOT).as_posix()] = path
    return sorted(safe.values(), key=lambda item: item.as_posix())


def _parse_external_args(rows: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for row in rows:
        if "=" not in row:
            raise SystemExit(
                "ABORT --external 格式必须是 slot_id=/真实路径："
                f"{row}"
            )
        slot_id, raw_path = row.split("=", 1)
        slot_id = slot_id.strip()
        if not slot_id or slot_id in parsed:
            raise SystemExit(f"ABORT external slot 重复或为空：{slot_id}")
        parsed[slot_id] = Path(raw_path).expanduser()
    return parsed


def _external_slot_files(path: Path) -> list[tuple[str, Path]]:
    if not path.exists():
        raise SystemExit(f"ABORT 外部回包不存在：{path}")
    if path.is_symlink():
        raise SystemExit(f"ABORT 外部回包不得是软链：{path}")
    if path.is_file():
        return [(path.name, path)]
    rows: list[tuple[str, Path]] = []
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise SystemExit(f"ABORT 外部回包目录含软链：{item}")
        if item.is_file():
            rows.append((item.relative_to(path).as_posix(), item))
    if not rows:
        raise SystemExit(f"ABORT 外部回包目录为空：{path}")
    return rows


def collect_route_payloads(
    route_name: str,
    selected_layers: list[str],
    external_args: list[str],
    cfg: dict[str, Any],
) -> tuple[dict[str, bytes], list[str], dict[str, Any]]:
    routes_cfg = _load_routes()
    routes = routes_cfg.get("routes") or {}
    if route_name not in routes:
        raise SystemExit(
            f"未知 route: {route_name}; 可选 {sorted(routes)}"
        )
    route = routes[route_name]
    configured_layers = route.get("layers") or {}
    unknown_layers = [
        layer
        for layer in selected_layers
        if layer not in ROUTE_LAYERS or layer not in configured_layers
    ]
    if unknown_layers:
        raise SystemExit(
            f"ABORT 未知 route layer：{unknown_layers}; 可选 {list(configured_layers)}"
        )
    if not selected_layers:
        raise SystemExit("ABORT route 至少选择一层")

    exclude = list(cfg.get("always_exclude_globs") or [])
    markers = list(cfg.get("secret_name_markers") or [])
    payloads: dict[str, bytes] = {}
    notes: list[str] = []
    source_records: list[dict[str, Any]] = []

    for layer in selected_layers:
        layer_cfg = configured_layers[layer]
        layer_dir = ROUTE_LAYER_DIRS[layer]
        for root_cfg in layer_cfg.get("roots") or []:
            root_id = str(root_cfg.get("root_id") or "")
            if not root_id:
                raise SystemExit(f"ABORT {route_name}/{layer} 有空 root_id")
            root_files: dict[str, Path] = {}
            root_excludes = [
                str(pattern) for pattern in root_cfg.get("exclude_globs") or []
            ]
            for pattern in root_excludes:
                _validate_route_pattern(pattern)
            for pattern in root_cfg.get("globs") or []:
                matches = _route_pattern_files(str(pattern))
                if not matches:
                    if root_cfg.get("required"):
                        raise SystemExit(
                            "ABORT route required glob 缺件："
                            f"{route_name}/{layer}/{root_id} -> {pattern}"
                        )
                    notes.append(
                        "OPTIONAL_ROUTE_GLOB_MISSING:"
                        f"{route_name}/{layer}/{root_id}:{pattern}"
                    )
                    continue
                for path in matches:
                    rel = path.relative_to(ROOT).as_posix()
                    if _matches_configured_globs(rel, root_excludes):
                        notes.append(
                            "ROUTE_FILE_EXCLUDED_BY_ROOT:"
                            f"{route_name}/{layer}/{root_id}:{rel}"
                        )
                        continue
                    if _looks_secret(rel, markers):
                        raise SystemExit(
                            f"ABORT route 命中疑似密钥路径：{rel}"
                        )
                    if _excluded(rel, exclude):
                        notes.append(
                            "ROUTE_FILE_EXCLUDED:"
                            f"{route_name}/{layer}/{root_id}:{rel}"
                        )
                        continue
                    root_files[rel] = path
            if root_cfg.get("required") and not root_files:
                raise SystemExit(
                    f"ABORT route required root 为空：{route_name}/{layer}/{root_id}"
                )
            for rel, path in sorted(root_files.items()):
                member = f"{layer_dir}/{rel}"
                _add_payload(payloads, member, path.read_bytes())
                source_records.append(
                    {
                        "member": member,
                        "layer": layer,
                        "root_id": root_id,
                        "source_ref": rel,
                        "authority": root_cfg.get("authority"),
                        "status": root_cfg.get("status"),
                    }
                )

    provided_external = _parse_external_args(external_args)
    slot_rows = {
        str(row.get("slot_id")): row
        for row in route.get("external_slots") or []
    }
    unknown_slots = sorted(set(provided_external) - set(slot_rows))
    if unknown_slots:
        raise SystemExit(
            f"ABORT 未知 external slot：{unknown_slots}; 可选 {sorted(slot_rows)}"
        )
    if provided_external and "external_reviews" not in selected_layers:
        raise SystemExit(
            "ABORT 提供了 --external，但没有选择 external_reviews 层"
        )
    if "external_reviews" in selected_layers:
        for slot_id, slot_cfg in slot_rows.items():
            path = provided_external.get(slot_id)
            if path is None:
                if slot_cfg.get("required"):
                    raise SystemExit(
                        "ABORT route required external slot 缺件："
                        f"{route_name}/{slot_id}"
                    )
                notes.append(
                    f"OPTIONAL_EXTERNAL_SLOT_MISSING:{route_name}/{slot_id}"
                )
                continue
            for rel, source in _external_slot_files(path):
                member = (
                    f"{ROUTE_LAYER_DIRS['external_reviews']}/"
                    f"{slot_id}/{rel}"
                )
                if _looks_secret(member, markers):
                    raise SystemExit(
                        f"ABORT 外部回包命中疑似密钥路径：{member}"
                    )
                _add_payload(payloads, member, source.read_bytes())
                source_records.append(
                    {
                        "member": member,
                        "layer": "external_reviews",
                        "root_id": slot_id,
                        "source_ref": f"external_slot:{slot_id}/{rel}",
                        "authority": slot_cfg.get("provider"),
                        "status": slot_cfg.get("status"),
                        "model": slot_cfg.get("model"),
                        "local_only": True,
                    }
                )

    forbidden_source_globs = [
        str(pattern) for pattern in route.get("forbidden_source_globs") or []
    ]
    for pattern in forbidden_source_globs:
        _validate_route_pattern(pattern)
    forbidden_hits = [
        {
            "member": str(row["member"]),
            "source_ref": str(row["source_ref"]),
        }
        for row in source_records
        if _matches_configured_globs(
            str(row["member"]), forbidden_source_globs
        )
        or _matches_configured_globs(
            str(row["source_ref"]), forbidden_source_globs
        )
    ]
    if forbidden_hits:
        raise SystemExit(
            "ABORT route 命中禁止外发的金标／答案锁箱：\n"
            + json.dumps(forbidden_hits, ensure_ascii=False, indent=2)
        )

    selection = {
        "schema_version": "chatgpt-review-route-selection-v1",
        "route_id": route_name,
        "label": route.get("label"),
        "purpose": route.get("purpose"),
        "snapshot_at": route.get("snapshot_at"),
        "truth_source": route.get("truth_source"),
        "selected_layers": selected_layers,
        "layer_directories": {
            layer: ROUTE_LAYER_DIRS[layer] for layer in selected_layers
        },
        "source_count": len(source_records),
        "sources": source_records,
        "external_slots": route.get("external_slots") or [],
        "forbidden_source_globs": forbidden_source_globs,
        "local_path_redaction_enabled": bool(
            route.get("redact_local_absolute_paths")
        ),
        "notes": notes,
    }
    return payloads, notes, selection


def _scan_secret_values(payloads: dict[str, bytes]) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    for member, data in payloads.items():
        for label, pattern in SECRET_VALUE_PATTERNS.items():
            if pattern.search(data):
                hits.append({"member": member, "pattern": label})
    return {
        "result": "PASS" if not hits else "FAIL",
        "scanned_members": len(payloads),
        "hit_count": len(hits),
        "hits": hits,
    }


def _redact_local_absolute_paths(
    payloads: dict[str, bytes],
) -> tuple[dict[str, bytes], dict[str, Any]]:
    repo_root = ROOT.resolve().as_posix().encode("utf-8")
    user_home = Path.home().resolve().as_posix().encode("utf-8")
    replacements = [
        (repo_root + b"/", b"<repo-root>/", "repo_root"),
        (repo_root, b"<repo-root>", "repo_root"),
    ]
    if user_home != repo_root:
        replacements.extend(
            [
                (user_home + b"/", b"<user-home>/", "user_home"),
                (user_home, b"<user-home>", "user_home"),
            ]
        )

    redacted: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    for member, original in payloads.items():
        sanitized = original
        counts: dict[str, int] = {}
        for needle, replacement, label in replacements:
            count = sanitized.count(needle)
            if count:
                sanitized = sanitized.replace(needle, replacement)
                counts[label] = counts.get(label, 0) + count
        redacted[member] = sanitized
        if sanitized != original:
            rows.append(
                {
                    "member": member,
                    "replacement_counts": counts,
                    "original_sha256": artifacts.sha256_bytes(original),
                    "sanitized_sha256": artifacts.sha256_bytes(sanitized),
                }
            )
    return redacted, {
        "schema_version": "chatgpt-review-local-path-redaction-v1",
        "result": "PASS",
        "changed_member_count": len(rows),
        "changed_members": rows,
        "note": (
            "只改外发副本：仓库绝对路径替换为 <repo-root>，"
            "用户目录替换为 <user-home>；本地原件未改。"
        ),
    }


def build_z83_ticket_digest() -> dict[str, bytes]:
    """在内存中生成 Z83 关键票据摘要；dry-run 不得落盘。"""

    payloads: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    for run_dir in sorted((ROOT / "runs").glob("Z83_*")):
        if not run_dir.is_dir():
            continue
        if (run_dir / "ARCHIVED.md").exists() and not any(run_dir.rglob("*.json")):
            continue
        ticket_candidates = [
            run_dir / "final" / "scorecard.json",
            run_dir / "main" / "hard_stop.json",
            run_dir / "repair" / "hard_stop.json",
            run_dir / "review" / "inspector" / "hard_stop.json",
            run_dir / "review" / "semantic_pre_retry_hard_stop.json",
            run_dir / "run_manifest.json",
        ]
        found: list[str] = []
        for t in ticket_candidates:
            if t.is_file():
                member = (
                    Path("_digest/z83_tickets")
                    / run_dir.name
                    / t.relative_to(run_dir)
                ).as_posix()
                payloads[member] = t.read_bytes()
                found.append(t.relative_to(ROOT).as_posix())
        rows.append({"run": run_dir.name, "tickets": found})
    index = {
        "schema_version": "z83-ticket-digest-v1",
        "purpose": "让外审看见第83道多轮硬停／成绩单脉络，而不必下载整棵 retry 林",
        "runs": [
            {
                "run": r.name,
                "has_scorecard": (r / "final" / "scorecard.json").is_file(),
                "has_any_hard_stop": any(
                    (r / p).is_file()
                    for p in (
                        "main/hard_stop.json",
                        "repair/hard_stop.json",
                        "review/inspector/hard_stop.json",
                        "review/semantic_pre_retry_hard_stop.json",
                    )
                ),
            }
            for r in sorted((ROOT / "runs").glob("Z83_*"))
            if r.is_dir()
        ],
        "copied": rows,
    }
    payloads["_digest/z83_tickets/INDEX.json"] = (
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return payloads


def render_reviewer_readme(
    profile_name: str,
    *,
    file_count: int,
    notes: list[str],
    generated_at: datetime,
) -> bytes:
    cs = {}
    cs_path = ROOT / "governance/CURRENT_STATE.json"
    if cs_path.is_file():
        cs = json.loads(cs_path.read_text(encoding="utf-8"))
    execution = cs.get("current_execution") or {}
    current = execution.get("task") or {}
    run = execution.get("run") or {}
    artifacts = execution.get("artifacts") or {}
    text = f"""# 给 ChatGPT／外审的读包说明（先读这个）

生成时间：{generated_at.isoformat(timespec="seconds")}
profile：`{profile_name}`

## 你要用这包做什么

1. 看懂仓库结构（什么进 Git、什么只留本地）
2. 看测试／Z 批流水线怎么跑、近几轮修了什么
3. 看近期 runs／reports：效果差在哪、建议下一刀怎么改
4. 顺便挑仓库是否乱、该怎么瘦／怎么分层

## 仓库边界（2026-07-23 起）

| 进 Git／活面 | 本机有但不进 Git |
|---|---|
| `AGENTS.md` `governance/` `config/` `tools/` `tests/` `foundation/` … | `runs/` `reports/` `outbox/` `TEMP/` |

本 zip **故意带了部分本地 runs／reports**（外审需要证据），这不等于它们应该进 Git。

## 建议阅读顺序

1. `00_READ_ME_FOR_REVIEWER.md`（本文件）
1. `AGENTS.md` → `governance/INDEX.md` → `governance/CURRENT_STATE.json`
1. `decisions.md`（本地决策流水）
1. `config/` 与 `tests/`（合同／机械闸）
1. `experiments/Z*`（测试依赖的实验脚本；缺了就无法完整复验）
1. `_digest/z83_tickets/`（若有：第83道多轮硬停／成绩摘要）
1. 当前道 `runs/` 与 `reports/`（近停证据）

## 当前任务镜像（摘自 CURRENT_STATE）

- task_id: `{current.get("task_id")}`
- label: `{current.get("label")}`
- status: `{current.get("status")}`
- run_directory: `{run.get("run_directory")}`
- report_directory: `{artifacts.get("report_directory")}`

## 本包文件数

{file_count} 个业务文件；包内另带机械生成的 `MANIFEST.json` 与 `SHA256SUMS`。

## 打包告警

{chr(10).join('- ' + n for n in notes) if notes else '（无）'}

## 请你输出的格式（请按此回）

1. **总判**：仓库结构／流程／近停质量 各一句
2. **最大 5 个问题**（按严重度）
3. **建议下一刀**（可执行、别空话）
4. **明确不要动什么**（金标／现役链／误删本地证据等）
5. **复验缺口**（若 tests／experiments 仍缺什么，直接点名路径）
"""
    return text.encode("utf-8")


def render_route_map(
    selection: dict[str, Any],
    *,
    file_count: int,
    generated_at: datetime,
) -> bytes:
    truth = selection.get("truth_source") or {}
    layer_dirs = selection.get("layer_directories") or {}
    layer_rows = []
    for layer in selection.get("selected_layers") or []:
        layer_rows.append(
            f"| `{layer}` | `{layer_dirs.get(layer)}` |"
        )
    source_counts: dict[str, int] = {}
    for row in selection.get("sources") or []:
        layer = str(row.get("layer"))
        source_counts[layer] = source_counts.get(layer, 0) + 1
    count_rows = [
        f"| `{layer}` | {source_counts.get(layer, 0)} |"
        for layer in selection.get("selected_layers") or []
    ]
    notes = selection.get("notes") or []
    text = f"""# 路线取材地图｜{selection.get("label")}

生成时间：{generated_at.isoformat(timespec="seconds")}
route：`{selection.get("route_id")}`
路线快照：`{selection.get("snapshot_at")}`

## 这包怎么分层

| 取材层 | 包内目录 |
| --- | --- |
{chr(10).join(layer_rows)}

| 取材层 | 文件数 |
| --- | ---: |
{chr(10).join(count_rows)}

全包业务成员：{file_count}。

## 当前真源

- 权威：{truth.get("authority")}
- 账序：{truth.get("ledger_url")}
- 队列：{truth.get("queue_url")}
- 本地 CURRENT_STATE 身份：`{truth.get("local_current_state_status")}`
- 说明：{truth.get("note")}

🔥 `CURRENT_STATE.json` 如果标成 `stale_mirror_only`，只能帮助理解旧治理结构，不能自动选当前 runs／reports，也不能覆盖上面的 Notion 行。

## 每个文件为什么进包

逐成员来源、所属层、来源根、权威身份与状态见：

`_route/ROUTE_SELECTION.json`

外部回包在清单里只写稳定的 `external_slot:<槽名>/文件名`，不把主机绝对路径写成工件身份。

## 顾问入口

R2 通用顾问 Prompt：

`01_current_truth/config/review_pack/prompts/r2_question_retrieval.md`

## 打包告警

{chr(10).join("- " + note for note in notes) if notes else "（无）"}

来源：Codex
"""
    return text.encode("utf-8")


def _add_payload(
    payloads: dict[str, bytes],
    member: str,
    data: bytes,
) -> None:
    pure = PurePosixPath(member)
    if (
        not member
        or "\\" in member
        or pure.is_absolute()
        or ".." in pure.parts
        or "." in pure.parts
    ):
        raise SystemExit(f"ABORT ZIP 成员路径不安全：{member}")
    if member in payloads:
        raise SystemExit(f"ABORT ZIP 成员重名：{member}")
    payloads[member] = data


def main() -> int:
    ap = argparse.ArgumentParser(description="ChatGPT 审仓打包")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--profile", default=None, help="surface|standard|deep")
    mode.add_argument("--route", default=None, help="按路线取材地图打包")
    ap.add_argument(
        "--layers",
        default=None,
        help="route 模式选层，逗号分隔；默认使用路线登记的 default_layers",
    )
    ap.add_argument(
        "--external",
        action="append",
        default=[],
        help="route 外部回包：slot_id=/真实路径；可重复",
    )
    ap.add_argument(
        "--list-routes",
        action="store_true",
        help="列出可用 route 后退出，零写入",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-large", action="store_true", help="允许超过 max_zip_mb")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    cfg = _load_profiles()
    routes_cfg = _load_routes()
    routes = routes_cfg.get("routes") or {}
    if args.list_routes:
        for route_id, route in sorted(routes.items()):
            defaults = ",".join(route.get("default_layers") or [])
            print(f"{route_id}\t{route.get('label')}\tdefault_layers={defaults}")
        return 0
    if (args.layers or args.external) and not args.route:
        raise SystemExit("ABORT --layers/--external 只能与 --route 一起使用")

    max_mb = float(cfg.get("max_zip_mb") or 25)
    generated_at = datetime.now()
    stamp = generated_at.strftime("%Y%m%d_%H%M%S")

    route_selection: dict[str, Any] | None = None
    route_secret_scan: dict[str, Any] | None = None
    route_redaction_receipt: dict[str, Any] | None = None
    if args.route:
        if args.route not in routes:
            raise SystemExit(
                f"未知 route: {args.route}; 可选 {sorted(routes)}"
            )
        route = routes[args.route]
        selected_layers = (
            [part.strip() for part in args.layers.split(",") if part.strip()]
            if args.layers
            else list(route.get("default_layers") or [])
        )
        payloads, notes, route_selection = collect_route_payloads(
            args.route,
            selected_layers,
            list(args.external),
            cfg,
        )
        route_map = render_route_map(
            route_selection,
            file_count=len(payloads),
            generated_at=generated_at,
        )
        _add_payload(payloads, "00_ROUTE_MAP.md", route_map)
        _add_payload(
            payloads,
            "_route/ROUTE_SELECTION.json",
            (
                json.dumps(
                    route_selection,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8"),
        )
        readme = route_map
        _add_payload(payloads, "00_READ_ME_FOR_REVIEWER.md", readme)
        if route.get("redact_local_absolute_paths"):
            payloads, route_redaction_receipt = (
                _redact_local_absolute_paths(payloads)
            )
            _add_payload(
                payloads,
                "_route/LOCAL_PATH_REDACTION.json",
                (
                    json.dumps(
                        route_redaction_receipt,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8"),
            )
        route_secret_scan = _scan_secret_values(payloads)
        if route_secret_scan["result"] != "PASS":
            raise SystemExit(
                "ABORT route 包命中疑似真实密钥值：\n"
                + json.dumps(route_secret_scan, ensure_ascii=False, indent=2)
            )
        _add_payload(
            payloads,
            "_route/SECRET_SCAN.json",
            (
                json.dumps(
                    route_secret_scan,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8"),
        )
        package_name = args.route
        pack_dir = args.out_dir or (OUT_ROOT / f"route_{args.route}_{stamp}")
        zip_name = f"chatgpt_review_route_{args.route}_{stamp}.zip"
        profile_name = None
    else:
        profile_name = args.profile or cfg.get("default_profile") or "standard"
        if profile_name not in cfg["profiles"]:
            raise SystemExit(
                f"未知 profile: {profile_name}; 可选 {list(cfg['profiles'])}"
            )
        profile = cfg["profiles"][profile_name]
        exclude = list(cfg.get("always_exclude_globs") or [])
        markers = list(cfg.get("secret_name_markers") or [])
        files, notes = collect_files(profile, cfg, exclude, markers)
        payloads = {}
        for path in files:
            _add_payload(
                payloads,
                path.relative_to(ROOT).as_posix(),
                path.read_bytes(),
            )
        if profile.get("digest_z83_tickets"):
            for member, data in build_z83_ticket_digest().items():
                _add_payload(payloads, member, data)
        readme = render_reviewer_readme(
            profile_name,
            file_count=len(payloads),
            notes=notes,
            generated_at=generated_at,
        )
        _add_payload(payloads, "00_READ_ME_FOR_REVIEWER.md", readme)
        missing = [note for note in notes if note.startswith("MISSING_REQUIRED")]
        if missing:
            raise SystemExit(
                "ABORT required runs missing:\n  " + "\n  ".join(missing)
            )
        package_name = profile_name
        pack_dir = args.out_dir or (OUT_ROOT / f"{profile_name}_{stamp}")
        zip_name = f"chatgpt_review_{profile_name}_{stamp}.zip"

    if pack_dir.exists():
        raise SystemExit(f"输出目录已存在，拒绝覆盖：{pack_dir}")

    zip_path = pack_dir / zip_name
    if args.dry_run:
        total = sum(len(data) for data in payloads.values())
        print(
            f"dry-run {('route=' + args.route) if args.route else ('profile=' + str(profile_name))} "
            f"files={len(payloads)} "
            f"bytes={total} (~{total/1024/1024:.1f}MB raw)（零写入）"
        )
        if route_selection:
            print(" layers=" + ",".join(route_selection["selected_layers"]))
        for member in sorted(payloads)[:30]:
            print(" ", member)
        print("  ...")
        return 0

    pack_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            dir=pack_dir.parent,
            prefix=f".{pack_dir.name}.",
        )
    )
    try:
        staged_zip = stage / zip_path.name
        integrity = artifacts.write_verified_zip(
            staged_zip,
            payloads,
            metadata={
                "package_kind": (
                    "chatgpt-review-route-pack-v1"
                    if args.route
                    else "chatgpt-review-pack-v2"
                ),
                "profile": profile_name,
                "route": args.route,
                "created_at": generated_at.isoformat(timespec="seconds"),
            },
        )
        zsize = int(integrity["zip_bytes"])
        if zsize / 1024 / 1024 > max_mb and not args.allow_large:
            raise SystemExit(
                f"ABORT zip {zsize/1024/1024:.1f}MB > max {max_mb}MB"
                "（加 --allow-large 才允许生成）"
            )
        (stage / "00_READ_ME_FOR_REVIEWER.md").write_bytes(readme)
        receipt = {
            "schema_version": (
                "chatgpt-review-route-pack-receipt-v1"
                if args.route
                else "chatgpt-review-pack-receipt-v2"
            ),
            "profile": profile_name,
            "route": args.route,
            "route_snapshot_at": (
                route_selection.get("snapshot_at")
                if route_selection
                else None
            ),
            "selected_layers": (
                route_selection.get("selected_layers")
                if route_selection
                else None
            ),
            "created_at": generated_at.isoformat(timespec="seconds"),
            "payload_file_count": len(payloads),
            "raw_bytes": sum(len(data) for data in payloads.values()),
            "zip": {
                "path": zip_path.name,
                "bytes": zsize,
                "sha256": integrity["zip_sha256"],
            },
            "max_zip_mb": max_mb,
            "notes": notes,
            "secret_scan": route_secret_scan,
            "local_path_redaction": route_redaction_receipt,
            "integrity": integrity,
        }
        (stage / "PACKAGE_RECEIPT.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(stage, pack_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    print(f"{'route' if args.route else 'profile'}={package_name}")
    print(
        f"files={len(payloads)} "
        f"raw_MB={sum(len(data) for data in payloads.values())/1024/1024:.1f} "
        f"zip_MB={zsize/1024/1024:.2f}"
    )
    print(f"zip={zip_path}")
    print(f"readme={pack_dir / '00_READ_ME_FOR_REVIEWER.md'}")
    print(f"receipt={pack_dir / 'PACKAGE_RECEIPT.json'}")
    if notes:
        print("notes:")
        for n in notes:
            print(" ", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

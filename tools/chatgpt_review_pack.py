#!/usr/bin/env python3
"""ChatGPT／外部强模型 · 审仓打包（可复用）。

默认 profile=standard：仓库活面 + 近停 runs/reports + Z83 票据摘要。
不把 TEMP／密钥／整棵历史 runs 打进去；外发读盘 ≠ 进 Git。

用法：
  python3 tools/chatgpt_review_pack.py
  python3 tools/chatgpt_review_pack.py --profile deep
  python3 tools/chatgpt_review_pack.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "config/review_pack/profiles.json"
OUT_ROOT = ROOT / "TEMP/chatgpt_review_packs"


def _load_profiles() -> dict[str, Any]:
    return json.loads(PROFILES.read_text(encoding="utf-8"))


def _match(path: Path, pattern: str) -> bool:
    # pathlib match 相对仓根
    rel = path.relative_to(ROOT).as_posix()
    return Path(rel).match(pattern) or path.match(pattern)


def _iter_glob(pattern: str) -> list[Path]:
    # 支持 runs/Z94_* 与 governance/**
    if pattern.endswith("/**"):
        base = ROOT / pattern[:-3]
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


def _excluded(rel: str, exclude_globs: list[str]) -> bool:
    for g in exclude_globs:
        if Path(rel).match(g) or Path(rel).match(g.lstrip("/")):
            return True
        # 简单前缀
        if g.endswith("/**") and rel.startswith(g[:-3]):
            return True
    if "__pycache__" in rel.split("/"):
        return True
    return False


def _looks_secret(rel: str, markers: list[str]) -> bool:
    lower = rel.lower()
    name = Path(rel).name.lower()
    for m in markers:
        m = m.lower()
        if m in name or m in lower:
            # 允许文档里提到 token 的 md？对文件名严格
            if name.endswith((".md", ".json")) and m in {"token", "secret"} and "provider" not in lower:
                # provider json 可能含字段名但无真密钥；仍拦 .env*
                pass
            if name.startswith(".env") or name.endswith((".pem", ".key", ".p12", ".pfx")):
                return True
            if "hf_token" in name or name.endswith(".env"):
                return True
            if ".env." in name or name == ".env":
                return True
    return name.startswith(".env") or name.endswith((".pem", ".key"))


def collect_files(profile: dict[str, Any], exclude_globs: list[str], markers: list[str]) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    notes: list[str] = []
    for pattern in profile.get("include_globs", []):
        files.extend(_iter_glob(pattern))
    for pattern in profile.get("run_globs", []):
        hits = _iter_glob(pattern)
        expanded: list[Path] = []
        for h in hits:
            if h.is_dir():
                expanded.extend([p for p in h.rglob("*") if p.is_file() and not p.is_symlink()])
            elif h.is_file():
                expanded.append(h)
        if not expanded and pattern.startswith("runs/"):
            parent = ROOT / "runs"
            leaf = pattern[len("runs/") :]
            dirs = list(parent.glob(leaf)) if any(ch in leaf for ch in "*?[") else ([parent / leaf] if (parent / leaf).exists() else [])
            for d in dirs:
                if d.is_dir():
                    expanded.extend([p for p in d.rglob("*") if p.is_file() and not p.is_symlink()])
                elif d.is_file():
                    expanded.append(d)
        if pattern.startswith("runs/") and not expanded:
            notes.append(f"MISSING_REQUIRED_RUN_GLOB:{pattern}")
        files.extend(expanded)
    for pattern in profile.get("report_globs", []):
        hits = _iter_glob(pattern)
        # reports/Z94* may match dirs
        expanded: list[Path] = []
        for h in hits:
            if h.is_dir():
                expanded.extend([p for p in h.rglob("*") if p.is_file()])
            elif h.is_file():
                expanded.append(h)
        if pattern.startswith("reports/") and not expanded:
            notes.append(f"MISSING_REPORT_GLOB:{pattern}")
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
    return sorted(uniq.values(), key=lambda x: x.as_posix()), notes


def build_z83_ticket_digest(dest_root: Path) -> list[Path]:
    """把每棵 Z83_* 的关键票据摘要进包，覆盖「修了几十轮」叙事且不带全林。"""
    out_files: list[Path] = []
    digest_dir = dest_root / "_digest" / "z83_tickets"
    digest_dir.mkdir(parents=True, exist_ok=True)
    rows = []
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
        found = []
        for t in ticket_candidates:
            if t.is_file():
                target = digest_dir / run_dir.name / t.relative_to(run_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(t.read_bytes())
                out_files.append(target)
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
    idx_path = digest_dir / "INDEX.json"
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_files.append(idx_path)
    return out_files


def write_reviewer_readme(pack_dir: Path, profile_name: str, files: list[Path], notes: list[str]) -> Path:
    cs = {}
    cs_path = ROOT / "governance/CURRENT_STATE.json"
    if cs_path.is_file():
        cs = json.loads(cs_path.read_text(encoding="utf-8"))
    current = cs.get("current_step") or {}
    text = f"""# 给 ChatGPT／外审的读包说明（先读这个）

生成时间：{datetime.now().isoformat(timespec="seconds")}
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
1. `_digest/z83_tickets/`（若有：第83道多轮硬停／成绩摘要）
1. `runs/Z94_*` 与 `reports/Z94*`（现役近停）
1. `runs/…_retry13`／`retry09`（第94道硬钉来源）

## 当前任务镜像（摘自 CURRENT_STATE）

- task_id: `{current.get("task_id")}`
- label: `{current.get("label")}`
- status: `{current.get("status")}`
- run_directory: `{current.get("run_directory")}`

## 本包文件数

{len(files)} 个文件。

## 打包告警

{chr(10).join('- ' + n for n in notes) if notes else '（无）'}

## 请你输出的格式（请按此回）

1. **总判**：仓库结构／流程／近停质量 各一句
2. **最大 5 个问题**（按严重度）
3. **建议下一刀**（可执行、别空话）
4. **明确不要动什么**（金标／现役链／误删本地证据等）
"""
    path = pack_dir / "00_READ_ME_FOR_REVIEWER.md"
    path.write_text(text, encoding="utf-8")
    return path


def zip_pack(pack_dir: Path, zip_path: Path, files: list[tuple[str, Path]]) -> int:
    raw = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for arc, src in files:
            data = src.read_bytes()
            raw += len(data)
            zf.writestr(arc, data)
    return raw


def main() -> int:
    ap = argparse.ArgumentParser(description="ChatGPT 审仓打包")
    ap.add_argument("--profile", default=None, help="surface|standard|deep")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-large", action="store_true", help="允许超过 max_zip_mb")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    cfg = _load_profiles()
    profile_name = args.profile or cfg.get("default_profile") or "standard"
    if profile_name not in cfg["profiles"]:
        raise SystemExit(f"未知 profile: {profile_name}; 可选 {list(cfg['profiles'])}")
    profile = cfg["profiles"][profile_name]
    exclude = list(cfg.get("always_exclude_globs") or [])
    markers = list(cfg.get("secret_name_markers") or [])
    max_mb = float(cfg.get("max_zip_mb") or 25)

    files, notes = collect_files(profile, exclude, markers)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    pack_dir = args.out_dir or (OUT_ROOT / f"{profile_name}_{stamp}")
    pack_dir.mkdir(parents=True, exist_ok=True)

    # digest into pack_dir then include
    extra: list[Path] = []
    if profile.get("digest_z83_tickets"):
        extra = build_z83_ticket_digest(pack_dir)

    readme = write_reviewer_readme(pack_dir, profile_name, files + extra, notes)

    # arcname map
    mapped: list[tuple[str, Path]] = [("00_READ_ME_FOR_REVIEWER.md", readme)]
    for p in files:
        mapped.append((p.relative_to(ROOT).as_posix(), p))
    for p in extra:
        mapped.append((p.relative_to(pack_dir).as_posix() if p.is_relative_to(pack_dir) else p.name, p))
        # digest files live under pack_dir
        mapped[-1] = (p.relative_to(pack_dir).as_posix(), p)

    # de-dupe arcs
    uniq: dict[str, Path] = {}
    for arc, src in mapped:
        uniq[arc] = src
    mapped = sorted(uniq.items())

    missing = [n for n in notes if n.startswith("MISSING_REQUIRED")]
    if missing:
        raise SystemExit("ABORT required runs missing:\n  " + "\n  ".join(missing))

    zip_path = pack_dir / f"chatgpt_review_{profile_name}_{stamp}.zip"
    if args.dry_run:
        total = sum(p.stat().st_size for _, p in mapped)
        print(f"dry-run profile={profile_name} files={len(mapped)} bytes={total} (~{total/1024/1024:.1f}MB raw)")
        for arc, _ in mapped[:30]:
            print(" ", arc)
        print("  ...")
        return 0

    raw = zip_pack(pack_dir, zip_path, mapped)
    zsize = zip_path.stat().st_size
    manifest = {
        "schema_version": "chatgpt-review-pack-manifest-v1",
        "profile": profile_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "file_count": len(mapped),
        "raw_bytes": raw,
        "zip_bytes": zsize,
        "zip_mb": round(zsize / 1024 / 1024, 2),
        "max_zip_mb": max_mb,
        "notes": notes,
        "zip_path": str(zip_path.relative_to(ROOT)),
        "readme": "00_READ_ME_FOR_REVIEWER.md",
    }
    (pack_dir / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"profile={profile_name}")
    print(f"files={len(mapped)} raw_MB={raw/1024/1024:.1f} zip_MB={zsize/1024/1024:.2f}")
    print(f"zip={zip_path}")
    print(f"readme={readme}")
    if zsize / 1024 / 1024 > max_mb and not args.allow_large:
        print(f"ABORT zip {zsize/1024/1024:.1f}MB > max {max_mb}MB（加 --allow-large 可强行保留）")
        return 2
    if notes:
        print("notes:")
        for n in notes:
            print(" ", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

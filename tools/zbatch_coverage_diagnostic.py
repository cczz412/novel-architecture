#!/usr/bin/env python3
"""运行 X01 中性事件提取覆盖诊断器。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from zbatch_modules import extraction_coverage  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_fingerprint(paths: list[Path], *, relative_to: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    files: list[Path] = []
    for base in paths:
        if base.is_file():
            files.append(base)
        else:
            files.extend(path for path in base.rglob("*") if path.is_file())
    total_bytes = 0
    for path in sorted(files, key=lambda value: str(value.relative_to(relative_to))):
        relative = str(path.relative_to(relative_to)).encode("utf-8")
        data = path.read_bytes()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
        total_bytes += len(data)
    return {"files": len(files), "bytes": total_bytes, "sha256": digest.hexdigest()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-dir", required=True)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--chapter-start", type=int, default=1)
    parser.add_argument("--chapter-end", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    book_dir = ROOT / args.book_dir
    source_run = ROOT / args.source_run
    target_path = ROOT / args.targets
    output_dir = ROOT / args.output_dir
    if output_dir.exists():
        raise SystemExit(f"输出目录已存在，拒绝覆盖：{output_dir}")
    target_config = json.loads(target_path.read_text(encoding="utf-8"))
    report = extraction_coverage.scan_book(
        book_dir=book_dir,
        extract_dir=source_run / "01_extract",
        target_config=target_config,
        chapter_start=args.chapter_start,
        chapter_end=args.chapter_end,
    )
    report["provenance"] = {
        "book_dir": args.book_dir,
        "source_run": args.source_run,
        "targets": args.targets,
        "targets_sha256": sha256(target_path),
        "diagnostic_module_sha256": sha256(
            ROOT / "tools/zbatch_modules/extraction_coverage.py"
        ),
        "cli_sha256": sha256(Path(__file__)),
        "source_extract_fingerprint": tree_fingerprint(
            [
                path
                for chapter in range(args.chapter_start, args.chapter_end + 1)
                for path in (
                    source_run / "01_extract/evidence_catalogs" / f"ch{chapter:04d}.json",
                    source_run / "01_extract/events" / f"ch{chapter:04d}.json",
                )
            ],
            relative_to=source_run,
        ),
        "chapter_text_fingerprint": tree_fingerprint(
            [
                next((book_dir / "chapters").glob(f"{chapter:04d}_*.txt"))
                for chapter in range(args.chapter_start, args.chapter_end + 1)
            ],
            relative_to=book_dir,
        ),
        "protected_sha256": {
            "tools/zbatch.py": sha256(ROOT / "tools/zbatch.py"),
            "tools/zbatch_modules/classify_rules.py": sha256(
                ROOT / "tools/zbatch_modules/classify_rules.py"
            ),
            "tools/zbatch_modules/__init__.py": sha256(
                ROOT / "tools/zbatch_modules/__init__.py"
            ),
        },
    }
    output_dir.mkdir(parents=True)
    output_path = output_dir / "coverage_diagnostic.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "run_id": output_dir.name,
        "status": "completed",
        "model_calls": 0,
        "output": str(output_path.relative_to(ROOT)),
        "output_sha256": sha256(output_path),
        "metrics": report["metrics"],
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

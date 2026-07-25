#!/usr/bin/env python3
"""清版外发包：Prompt 文件 + 可回读校验的材料 ZIP。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from pipeline_common import artifacts  # noqa: E402


def _preflight(
    prompt: Path,
    files: list[Path],
    *,
    zip_name: str,
) -> tuple[bytes, dict[str, bytes]]:
    if not prompt.is_file():
        raise SystemExit(f"Prompt 不是文件：{prompt}")
    if Path(zip_name).name != zip_name or not zip_name.endswith(".zip"):
        raise SystemExit(f"ZIP 名称必须是单个 .zip 文件名：{zip_name}")

    payloads: dict[str, bytes] = {}
    for raw in files:
        path = raw.resolve()
        if not path.is_file():
            raise SystemExit(f"不是文件：{raw}")
        member = path.name
        if member in payloads:
            raise SystemExit(f"ZIP 成员重名，拒绝静默覆盖：{member}")
        payloads[member] = path.read_bytes()
    return prompt.read_bytes(), payloads


def _build_into(
    stage: Path,
    *,
    prompt_bytes: bytes,
    payloads: dict[str, bytes],
    zip_name: str,
) -> dict[str, object]:
    upload = stage / "upload"
    upload.mkdir(parents=True, exist_ok=True)
    prompt_out = stage / "00_发给外部的Prompt.md"
    prompt_out.write_bytes(prompt_bytes)
    zip_path = upload / zip_name
    integrity = artifacts.write_verified_zip(
        zip_path,
        payloads,
        metadata={"package_kind": "simple-pack-v2"},
    )
    receipt: dict[str, object] = {
        "schema_version": "simple-pack-receipt-v2",
        "prompt": {
            "path": prompt_out.name,
            "bytes": len(prompt_bytes),
            "sha256": artifacts.sha256_bytes(prompt_bytes),
        },
        "zip": {
            "path": f"upload/{zip_name}",
            "bytes": integrity["zip_bytes"],
            "sha256": integrity["zip_sha256"],
        },
        "payload_file_count": len(payloads),
        "integrity": integrity,
    }
    (stage / "PACKAGE_RECEIPT.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> int:
    p = argparse.ArgumentParser(description="小说架构 · 清版打包（Prompt + ZIP）")
    p.add_argument("--prompt", required=True, type=Path, help="要外发粘贴的 Prompt .md")
    p.add_argument("--out-dir", required=True, type=Path, help="输出目录（会写 Prompt 副本 + upload/*.zip）")
    p.add_argument("--zip-name", default="arch_pack.zip", help="ZIP 文件名")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只预检输入和成员名，不创建目录、不写文件",
    )
    p.add_argument("files", nargs="+", type=Path, help="打进 ZIP 的章节或材料文件")
    args = p.parse_args()

    out = args.out_dir
    prompt_bytes, payloads = _preflight(
        args.prompt,
        args.files,
        zip_name=args.zip_name,
    )
    if out.exists():
        raise SystemExit(f"输出目录已存在，拒绝覆盖：{out}")
    if args.dry_run:
        total = sum(len(data) for data in payloads.values())
        print(
            f"dry-run files={len(payloads)} bytes={total} "
            f"out={out}（零写入）"
        )
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            dir=out.parent,
            prefix=f".{out.name}.",
        )
    )
    try:
        receipt = _build_into(
            stage,
            prompt_bytes=prompt_bytes,
            payloads=payloads,
            zip_name=args.zip_name,
        )
        os.replace(stage, out)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    print("交件双件：")
    print(f"  Prompt: {out / '00_发给外部的Prompt.md'}")
    print(f"  ZIP:    {out / 'upload' / args.zip_name}")
    print(f"  验收票: {out / 'PACKAGE_RECEIPT.json'}")
    print(f"  文件数: {receipt['payload_file_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

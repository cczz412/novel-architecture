#!/usr/bin/env python3
"""清版外发包：Prompt 文件 + 章节 ZIP。不做重型多闸校验。"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="小说架构 · 清版打包（Prompt + ZIP）")
    p.add_argument("--prompt", required=True, type=Path, help="要外发粘贴的 Prompt .md")
    p.add_argument("--out-dir", required=True, type=Path, help="输出目录（会写 Prompt 副本 + upload/*.zip）")
    p.add_argument("--zip-name", default="arch_pack.zip", help="ZIP 文件名")
    p.add_argument("files", nargs="+", type=Path, help="打进 ZIP 的章节或材料文件")
    args = p.parse_args()

    out = args.out_dir
    upload = out / "upload"
    upload.mkdir(parents=True, exist_ok=True)

    prompt_out = out / "00_发给外部的Prompt.md"
    prompt_out.write_text(args.prompt.read_text(encoding="utf-8"), encoding="utf-8")

    zip_path = upload / args.zip_name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in args.files:
            f = f.resolve()
            if not f.is_file():
                raise SystemExit(f"不是文件: {f}")
            zf.write(f, arcname=f.name)

    print("交件双件：")
    print(f"  Prompt: {prompt_out}")
    print(f"  ZIP:    {zip_path}")
    print(f"  文件数: {len(args.files)}")


if __name__ == "__main__":
    main()

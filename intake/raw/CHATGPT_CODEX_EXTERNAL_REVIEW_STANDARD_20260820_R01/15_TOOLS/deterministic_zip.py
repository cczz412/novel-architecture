#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, stat, zipfile

FIXED=(1980,1,1,0,0,0)

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('directory')
    ap.add_argument('output_zip')
    ns=ap.parse_args()
    root=Path(ns.directory).resolve(); out=Path(ns.output_zip).resolve()
    if not root.is_dir(): raise SystemExit('directory not found')
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(root.rglob('*')):
            if not p.is_file(): continue
            rel=p.relative_to(root).as_posix()
            info=zipfile.ZipInfo(rel,FIXED)
            mode=0o755 if (p.stat().st_mode & stat.S_IXUSR) else 0o644
            info.external_attr=(mode & 0xFFFF)<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            with p.open('rb') as f: z.writestr(info,f.read(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
    with zipfile.ZipFile(out) as z:
        bad=z.testzip()
    if bad: raise SystemExit(f'bad zip member: {bad}')
    print(out)
    return 0
if __name__=='__main__': raise SystemExit(main())

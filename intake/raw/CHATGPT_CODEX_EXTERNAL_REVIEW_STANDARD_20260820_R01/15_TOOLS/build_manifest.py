#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, hashlib, json, datetime as dt

EXCLUDE = {'MANIFEST.json', 'SHA256SUMS.txt'}

def hfile(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('directory')
    ap.add_argument('--package-id', required=True)
    ap.add_argument('--profile', default='CHAT_BOOTSTRAP')
    ap.add_argument('--authority', default='ADVISORY_ONLY')
    ns=ap.parse_args()
    root=Path(ns.directory).resolve()
    if not root.is_dir(): raise SystemExit('directory not found')
    files=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name not in EXCLUDE:
            files.append({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':hfile(p),'role':'UNCLASSIFIED','status':'CURRENT'})
    manifest={'schema':'chatgpt-review-package-manifest-v1','package_id':ns.package_id,'profile':ns.profile,'authority':ns.authority,'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'files':files}
    (root/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=[f"{x['sha256']}  {x['path']}" for x in files]
    lines.append(f"{hfile(root/'MANIFEST.json')}  MANIFEST.json")
    (root/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(files),'manifest':str(root/'MANIFEST.json')},ensure_ascii=False))
    return 0
if __name__=='__main__': raise SystemExit(main())

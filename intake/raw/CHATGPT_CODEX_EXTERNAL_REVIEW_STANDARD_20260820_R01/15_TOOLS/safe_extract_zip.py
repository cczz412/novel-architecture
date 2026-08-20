#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, os, re, shutil, stat, tempfile, zipfile

DRIVE=re.compile(r'^[A-Za-z]:')

def is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK

def hfile(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def validate_name(name: str) -> str:
    if '\x00' in name: raise ValueError('NUL in path')
    if '\\' in name: raise ValueError('backslash path rejected')
    if DRIVE.match(name): raise ValueError('Windows drive path rejected')
    pp=PurePosixPath(name)
    if pp.is_absolute(): raise ValueError('absolute path rejected')
    if any(part in ('..','') for part in pp.parts): raise ValueError('unsafe path component')
    return pp.as_posix()

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('zipfile')
    ap.add_argument('destination')
    ap.add_argument('--max-members',type=int,default=10000)
    ap.add_argument('--max-total-bytes',type=int,default=8*1024**3)
    ap.add_argument('--max-member-bytes',type=int,default=1024**3)
    ap.add_argument('--max-ratio',type=float,default=200.0)
    ap.add_argument('--receipt')
    ns=ap.parse_args()
    zp=Path(ns.zipfile).resolve(); dest=Path(ns.destination).resolve()
    if dest.exists(): raise SystemExit('destination must not exist')
    receipt={'zip':str(zp),'destination':str(dest),'members':[],'status':'FAIL'}
    seen=set(); total=0
    with zipfile.ZipFile(zp) as z:
        infos=z.infolist()
        if len(infos)>ns.max_members: raise SystemExit('too many members')
        bad=z.testzip()
        if bad: raise SystemExit(f'CRC failure: {bad}')
        for info in infos:
            norm=validate_name(info.filename.rstrip('/')) if info.filename.rstrip('/') else None
            if norm is None: continue
            key=norm.casefold()
            if key in seen: raise SystemExit(f'duplicate/case-conflict path: {norm}')
            seen.add(key)
            if is_symlink(info): raise SystemExit(f'symlink rejected: {norm}')
            if info.file_size>ns.max_member_bytes: raise SystemExit(f'member too large: {norm}')
            total+=info.file_size
            if total>ns.max_total_bytes: raise SystemExit('total uncompressed size too large')
            ratio=info.file_size/max(info.compress_size,1)
            if ratio>ns.max_ratio and info.file_size>1024*1024: raise SystemExit(f'compression ratio too high: {norm}')
            receipt['members'].append({'path':norm,'bytes':info.file_size,'compressed_bytes':info.compress_size,'ratio':ratio})
        staging=Path(tempfile.mkdtemp(prefix=dest.name+'.staging.',dir=str(dest.parent)))
        try:
            for info in infos:
                raw=info.filename.rstrip('/')
                if not raw: continue
                norm=validate_name(raw)
                target=(staging/norm).resolve()
                if os.path.commonpath([str(staging.resolve()),str(target)])!=str(staging.resolve()): raise SystemExit('path escape')
                if info.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as src, target.open('wb') as out:
                    shutil.copyfileobj(src,out,1024*1024)
            os.replace(staging,dest)
        except Exception:
            shutil.rmtree(staging,ignore_errors=True)
            raise
    receipt['status']='PASS'; receipt['total_uncompressed_bytes']=total; receipt['zip_sha256']=hfile(zp)
    rp=Path(ns.receipt) if ns.receipt else dest.parent/(dest.name+'_EXTRACT_RECEIPT.json')
    rp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(rp)
    return 0
if __name__=='__main__': raise SystemExit(main())

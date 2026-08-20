#!/usr/bin/env python3
from __future__ import annotations
from pathlib import PurePosixPath, Path
import argparse, hashlib, json, re, stat, zipfile

SECRET_NAME=re.compile(r'(^|/)(\.env|id_rsa|credentials\.json|\.npmrc|\.pypirc)$|secret|api[_-]?key|token',re.I)
SECRET_CONTENT=[re.compile(x,re.I) for x in [r'BEGIN [A-Z ]*PRIVATE KEY',r'AKIA[0-9A-Z]{16}',r'\bsk-[A-Za-z0-9_-]{12,}',r'[_-](API_KEY|TOKEN|PASSWORD)\s*=']]
DRIVE=re.compile(r'^[A-Za-z]:')

def safe_name(n: str) -> bool:
    if '\x00' in n or '\\' in n or DRIVE.match(n): return False
    p=PurePosixPath(n)
    return not p.is_absolute() and '..' not in p.parts

def is_symlink(i: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT(i.external_attr >> 16)==stat.S_IFLNK

def hbytes(b: bytes) -> str: return hashlib.sha256(b).hexdigest()

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('zipfile')
    ap.add_argument('--strict-secrets',action='store_true')
    ap.add_argument('--max-members',type=int,default=10000)
    ap.add_argument('--max-total-bytes',type=int,default=8*1024**3)
    ap.add_argument('--receipt')
    ns=ap.parse_args(); zp=Path(ns.zipfile)
    r={'schema':'review-package-validation-v1','zip':str(zp),'errors':[],'warnings':[],'members':0,'total_uncompressed_bytes':0}
    with zipfile.ZipFile(zp) as z:
        infos=z.infolist(); r['members']=len(infos)
        if len(infos)>ns.max_members:r['errors'].append('too many members')
        bad=z.testzip()
        if bad:r['errors'].append(f'CRC failure: {bad}')
        names=set()
        for i in infos:
            n=i.filename
            if not safe_name(n):r['errors'].append(f'unsafe path: {n}')
            k=n.casefold()
            if k in names:r['errors'].append(f'duplicate/case-conflict: {n}')
            names.add(k)
            if is_symlink(i):r['errors'].append(f'symlink: {n}')
            r['total_uncompressed_bytes']+=i.file_size
            if SECRET_NAME.search(n):r['warnings'].append(f'suspicious secret filename: {n}')
            if i.file_size<=2*1024*1024 and not n.endswith('/'):
                try:
                    b=z.read(i)
                    s=b.decode('utf-8','ignore')
                    for pat in SECRET_CONTENT:
                        if pat.search(s):r['warnings'].append(f'suspicious secret content: {n}');break
                except Exception:pass
        if r['total_uncompressed_bytes']>ns.max_total_bytes:r['errors'].append('total uncompressed size exceeds policy')
        required=['00_READ_ME_FIRST.md','MANIFEST.json','SHA256SUMS.txt']
        for req in required:
            if req.casefold() not in names:r['errors'].append(f'missing required member: {req}')
        if 'MANIFEST.json' in z.namelist():
            try:
                m=json.loads(z.read('MANIFEST.json'))
                listed={x['path']:x for x in m.get('files',[])}
                for path,x in listed.items():
                    if path not in z.namelist():r['errors'].append(f'manifest missing member: {path}');continue
                    b=z.read(path)
                    if len(b)!=x.get('bytes'):r['errors'].append(f'byte mismatch: {path}')
                    if hbytes(b)!=x.get('sha256'):r['errors'].append(f'SHA mismatch: {path}')
            except Exception as e:r['errors'].append(f'manifest parse/verify error: {e}')
    if ns.strict_secrets and r['warnings']:r['errors'].extend(r['warnings'])
    r['status']='PASS' if not r['errors'] else 'FAIL'
    rp=Path(ns.receipt) if ns.receipt else zp.with_suffix(zp.suffix+'.validation.json')
    rp.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':r['status'],'receipt':str(rp),'errors':len(r['errors']),'warnings':len(r['warnings'])},ensure_ascii=False))
    return 0 if r['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())

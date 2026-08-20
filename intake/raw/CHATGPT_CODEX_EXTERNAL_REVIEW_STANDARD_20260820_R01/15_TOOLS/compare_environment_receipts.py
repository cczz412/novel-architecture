#!/usr/bin/env python3
from pathlib import Path
import argparse,json
KEYS=['platform','python','cpu_count','affinity','cpu_max','memory_max','node','git','os_release']
def main():
    ap=argparse.ArgumentParser();ap.add_argument('a');ap.add_argument('b');ns=ap.parse_args()
    a=json.loads(Path(ns.a).read_text());b=json.loads(Path(ns.b).read_text())
    out={k:{'a':a.get(k),'b':b.get(k),'equal':a.get(k)==b.get(k)} for k in KEYS}
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

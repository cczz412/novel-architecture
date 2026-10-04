# 执行身份：Codex
"""限流等待后的单次虚构探测；只能由文件网关作业执行。"""
import argparse
import json
from pathlib import Path
from pr_ark_client_r02 import Client
from pr_pipeline_r02 import MODELS, OUT, external, dump


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',choices=MODELS,required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    folder=external(a.out)
    folder.mkdir(parents=True,exist_ok=True)
    policy={'reasoning_effort':'low'} if a.model=='glm-5.3-flash' else {'thinking':{'type':'disabled'}}
    try:
        response=Client().call(a.model,[dict(role='user',content='执行身份：Codex。虚构连通性探测，不含任何小说。只返回JSON：{"ready":true}')],policy,max_tokens=1000)
        dump(folder/'response.json',response)
        dump(folder/'receipt.json',dict(execution_identity='Codex',model=a.model,ok=True,usage=response.get('usage',{}),finish_reason=response['choices'][0].get('finish_reason')))
        print('虚构探测成功',a.model)
        return 0
    except Exception as e:
        dump(folder/'receipt.json',dict(execution_identity='Codex',model=a.model,ok=False,error=str(e)))
        print('虚构探测失败',a.model,str(e))
        return 1


if __name__=='__main__':raise SystemExit(main())

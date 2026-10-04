# 执行身份：Codex
"""限流等待后的单次虚构探测；只能由文件网关作业执行。"""
import argparse
import json
from pathlib import Path
from pr_ark_client_r02 import Client
import pr_ark_client_r02 as client_module
from pr_pipeline_r02 import MODELS, OUT, external, dump


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',choices=MODELS,required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--representative-bytes',type=int,default=0)
    p.add_argument('--max-output-tokens',type=int,choices=(1000,16000,24000),default=1000)
    a=p.parse_args()
    folder=external(a.out)
    folder.mkdir(parents=True,exist_ok=True)
    # 只有这个单次虚构探测跳过客户端旧阻塞；网关保险照常强制。
    client_module.is_blocked=lambda:False
    client_module.BLOCKED=folder/'probe_blocked.json'
    policy={'reasoning_effort':'low'} if a.model=='glm-5.3-flash' else {'thinking':{'type':'disabled'}}
    text='执行身份：Codex。虚构连通性探测，不含任何小说。只返回JSON：{"ready":true}'
    if a.representative_bytes:
        assert 0<a.representative_bytes<=80000
        fiction='木桥边，甲准备明天修桥，乙问如果下雨怎么办，丙看着门口的灯。\n'
        prefix='下方只是虚构长度填充材料，无须抽取。\n'
        count=max(0,(a.representative_bytes-len((text+prefix).encode()))//len(fiction.encode()))
        text=text+'\n'+prefix+fiction*count+'\n只返回前述ready结构。'
    try:
        response=Client().call(a.model,[dict(role='user',content=text)],policy,max_tokens=a.max_output_tokens)
        dump(folder/'response.json',response)
        dump(folder/'receipt.json',dict(execution_identity='Codex',model=a.model,ok=True,input_utf8_bytes=len(text.encode()),max_output_tokens=a.max_output_tokens,usage=response.get('usage',{}),finish_reason=response['choices'][0].get('finish_reason')))
        print('虚构探测成功',a.model)
        return 0
    except Exception as e:
        dump(folder/'receipt.json',dict(execution_identity='Codex',model=a.model,ok=False,error=str(e)))
        print('虚构探测失败',a.model,str(e))
        return 1


if __name__=='__main__':raise SystemExit(main())

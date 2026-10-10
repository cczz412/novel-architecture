# 执行身份：Codex
"""只用虚构文本有限探测既定 DeepSeek 的低档／格式兼容性。"""
import json
from pathlib import Path
import urllib.error
import urllib.request

from pr_pipeline_r01 import Client, OUT, dump

client=Client()
model='deepseek/deepseek-v4.1-flash'
catalog=client.get('/models')['data']
metadata=next(r for r in catalog if r['id']==model)
assert 'low' in metadata['reasoning']['supported_efforts']
trials=[]
for structured in (True,False):
    payload={'model':model,'messages':[{'role':'user','content':'虚构测试：只输出 {"ok":true}。'}],
             'max_tokens':2048,'temperature':0,'reasoning':{'effort':'low','exclude':True}}
    if structured:payload['response_format']={'type':'json_object'}
    request=urllib.request.Request(client.base+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),
                                  headers={'Content-Type':'application/json','X-PR-Job-ID':client.job})
    try:
        with client.opener.open(request,timeout=200) as response: result=json.load(response)
        dump(OUT/'probe'/f'deepseek_route_{int(structured)}.json',result)
        reasoning=(result.get('usage',{}).get('completion_tokens_details') or {}).get('reasoning_tokens')
        valid=result['choices'][0].get('finish_reason')=='stop' and reasoning is not None
        trials.append({'response_format':structured,'success':valid,'reasoning_tokens':reasoning,'usage':result.get('usage')})
        if valid:
            p=OUT/'probe/reasoning_policy.json';policies=json.loads(p.read_text())
            policies[model]={'usable':True,'verified':True,'mandatory':False,'reasoning':{'effort':'low','exclude':True},
                            'response_format_supported':structured,'reasoning_tokens':reasoning,'reason':'关闭配置路径不可用，低档配置实测可用'}
            dump(p,policies)
            break
    except urllib.error.HTTPError as exc:
        trials.append({'response_format':structured,'success':False,'http_status':exc.code})
        if exc.code==402:break
dump(OUT/'probe/deepseek_route_trials.json',trials)
print('仅虚构文本的路由探测完成',json.dumps(trials,ensure_ascii=False))

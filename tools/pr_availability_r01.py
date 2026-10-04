# 执行身份：Codex
"""仅一次极短虚构请求，区分上游整组不可用与长请求拒绝。"""
import json
from pr_pipeline_r01 import Client, OUT, dump

model='z-ai/glm-5.3-flashx'
policy=json.loads((OUT/'probe/reasoning_policy.json').read_text())[model]
try:
    response=Client().call(model,[{'role':'user','content':'虚构连通题：只输出 {"ok":true}。'}],policy['reasoning'],max_tokens=128)
    dump(OUT/'probe/availability_short_response.json',response)
    dump(OUT/'probe/availability_short_result.json',{'success':True,'max_tokens':128,'finish_reason':response['choices'][0].get('finish_reason'),'usage':response.get('usage',{})})
except Exception as exc:
    dump(OUT/'probe/availability_short_result.json',{'success':False,'max_tokens':128,'error':str(exc)})

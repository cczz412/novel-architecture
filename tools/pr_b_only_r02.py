# 执行身份：Codex
"""事实仍按16段分组；原文材料改由同遍的完整章步骤处理。"""
import copy
import json
import re
from pr_pipeline_r02 import RULES,SYSTEM
from pr_compact_bc_r02 import compact_materials,decode,convert
from pr_resolved_bc_r02 import validate_dispositions
from pr_ark_client_r02 import Client
from pr_step_flow_r02 import execute
from pr_evidence_guard_r02 import inspect

SCHEMA='''本步只处理事实，不处理原文写法、视角、场景或人物计划。完整章原文材料在后续同遍另一步生成，不能在本步写C。
仅输出五数组：{"keep":[],"exclude":[],"flag":[],"replace":[],"add":[]}。
keep/exclude/flag只列本组facts的明确旧键，分别是完整正确沿用、确认非故事内容排除、未决但正文保留；replace每项{key,text,reason,evidence:[{p,q}]}，key只能用本组旧键；add每项{text,reason,evidence:[{p,q}]}。每个本组旧键明确归入四类之一，每键只一次；不能遗漏、造键或处置read_only_context_facts。
facts的正确旧句沿用，不借替换重写。新事实只补owned_paragraph_ids，保留原因、反应、动作、物件、条件、否定、推测和真实归属，不将引文里的原话改写后继续加引号。p用输入完整段号或末尾短号，q是该段连续逐字短引。跨段旧句保持完整，上下文和只读旧句仅供理解与查重，不另抽上下文。
程序填写书章、稳定变动编号与事实新键；模型不编身份号。不输出paragraphs、scenes、C、A或其他审查字段。'''

def messages(data):
    return [dict(role='system',content=SYSTEM),dict(role='user',content=RULES+'\n'+SCHEMA+'\n输入材料：\n'+json.dumps(compact_materials(data),ensure_ascii=False,separators=(',',':')))]

def convert_response(response,data):
    choice=response['choices'][0]
    text=re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$','',choice['message']['content'] or '')
    raw=json.loads(text)
    if not isinstance(raw,dict) or any(not isinstance(raw.get(k),list) for k in ('keep','exclude','flag','replace','add')):
        raise ValueError('事实步骤须有keep/exclude/flag/replace/add五数组')
    if raw.get('paragraphs') or raw.get('scenes') or raw.get('C') or raw.get('A'):
        raise ValueError('本步仅输出事实五数组，原文材料和计划另一步处理')
    raw['paragraphs']=[];raw['scenes']=[]
    adapted=copy.deepcopy(response)
    adapted['choices'][0]['message']['content']=json.dumps(raw,ensure_ascii=False)
    parsed=decode(adapted,data)
    validate_dispositions(parsed,data)
    # 本步骤的责任只有事实；不把刻意延后的C当作模型漏交付。
    scope=dict(data,owned_paragraph_ids=[])
    candidate,issues=convert(parsed,scope)
    candidate['C']=[]
    candidate['review_audit']['source_chapters']=[]
    return candidate,issues

def bc_call(data,policy,model,output,guard):
    return execute(data,output,lambda current:Client().call(model,current,policy['parameters'],max_tokens=12000),messages,convert_response,inspect)

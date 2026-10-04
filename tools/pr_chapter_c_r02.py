# 执行身份：Codex
"""原文材料读本章完整原文，不把场景边界裁成事实小组。"""
import copy
import json
import re
from pr_pipeline_r02 import SYSTEM
from pr_compact_bc_r02 import decode,convert
from pr_ark_client_r02 import Client
from pr_step_flow_r02 import execute
from pr_evidence_guard_r02 import inspect

SCHEMA='''执行身份：Codex。本步只生成本章原文材料，不抽事实、不写人物计划，不借已知故事补写。
只输出两数组：{"paragraphs":[],"scenes":[]}。
paragraphs每项{id,main,secondary,viewpoint,quote,note}。每个输入段只一次；id用输入完整段号或末尾短号。main只取叙述带过、动作展开、对话、心理、场景；secondary为null或另一不同标签，最多一种，不能填英文、多标签拼串或自造词。
视角是感知者而不是说话人：按这一段是谁在看、听、感受或心想判断，不因人物说话就自动标他的视角。值为明确感知者人物名、全知、切换或null；不确定留null并说明，不在值里加括注。quote是本段连续逐字短引，不改标点或称呼。
scenes每项{paragraph_ids,location:[],light_weather:[],objects_visuals:[],sounds_smells:[],atmosphere:[]}。五格每项{text,p,q}，p是本章所指段号，q是连续逐字短引。按原文真实场景组织，不把前一步16段事实分组当作场景边界。允许一个场景跨越多个原事实小组。
地点、光线天气、陈设视觉物、声音气味、氛围按真实现场分别摘取，没写就空数组，不填未写等占位、不将整段重复粘到多格。个人动作、个人情绪和台词内容不当环境格；回述、梦境和内层故事不当当前现场。仍按本章原文判断，不能用事实摘要代替原文。
书号、章号和场景编号由程序填写。不输出A、B、事实键、书章身份或计划历史。'''

def messages(data):
    materials={k:data[k] for k in ('book_id','chapter','paragraphs','scope_limits')}
    return [dict(role='system',content=SYSTEM),dict(role='user',content=SCHEMA+'\n输入材料：\n'+json.dumps(materials,ensure_ascii=False,separators=(',',':')))]

def convert_response(response,data):
    choice=response['choices'][0]
    text=re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$','',choice['message']['content'] or '')
    raw=json.loads(text)
    if not isinstance(raw,dict) or not isinstance(raw.get('paragraphs'),list) or not isinstance(raw.get('scenes'),list):
        raise ValueError('原文材料步骤须有paragraphs/scenes两数组')
    if raw.get('A') or raw.get('B') or raw.get('add') or raw.get('replace'):
        raise ValueError('原文材料步骤不输出人物计划或事实，只输出paragraphs/scenes两数组')
    stub=dict(keep=[],exclude=[],flag=[],replace=[],add=[],paragraphs=raw['paragraphs'],scenes=raw['scenes'])
    adapted=copy.deepcopy(response)
    adapted['choices'][0]['message']['content']=json.dumps(stub,ensure_ascii=False)
    parsed=decode(adapted)
    expected={p['paragraph_id'] for p in data['paragraphs']}
    seen=[data['book_id']+':ch'+data['chapter']+':'+p['id'] if re.fullmatch(r'p\d+',p.get('id','')) else p.get('id') for p in parsed['paragraphs']]
    if set(seen)!=expected or len(seen)!=len(set(seen)):
        raise ValueError('本章段落标注须逐段完整且不重复，缺失：'+json.dumps(sorted(expected-set(seen)),ensure_ascii=False))
    if any(not isinstance(p.get('quote'),str) for p in parsed['paragraphs']):
        raise ValueError('每段quote必须是原文短引字符串，不能为对象、数组或null')
    scope=dict(data,group='chapter',facts=[],read_only_context_facts=[],context_paragraphs=[],
        owned_paragraph_ids=[p['paragraph_id'] for p in data['paragraphs']],new_key_prefix='unused:')
    candidate,issues=convert(parsed,scope)
    return candidate,issues

def c_call(data,policy,model,output):
    scope=dict(data,group='chapter',context_paragraphs=[],step_kind='C')
    return execute(scope,output,lambda current:Client().call(model,current,policy['parameters'],max_tokens=32000),messages,convert_response,inspect)

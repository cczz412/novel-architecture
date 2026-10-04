# 执行身份：Codex
"""分层小任务、有限回传、逐条隔离；实验输出与原文只落本轮外部目录。"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

from pr_pipeline_r02 import (OUT, MODELS, RULES, SYSTEM, read_book, empty_result,
                             assemble, dump, external, STATUSES, TAGS)
from pr_ark_client_r02 import Client, BLOCKED
from pr_resolved_r02 import groups, chapter_facts
from pr_b_only_r02 import SCHEMA as B_SCHEMA
from pr_chapter_c_r02 import SCHEMA as C_SCHEMA
from pr_compact_bc_r02 import full_pid, convert
from pr_normalize_v2_r03 import normalize

RULE = RULES.replace('C 与事实同遍抽：','C由单独步骤处理：')
A_DISCOVER = '''本步只筛本章新人物计划和旧召回去向，不处理前章计划状态。事实句已给出，不能改事实或补正文。
输出 {"old_rows":[{"key":旧召回键,"meaning":"沿用原意/修正原意/非计划保留原类/审查批注/未决","retained_field":原native_field或null,"reason":具体短理由}],"plans":[{"old_keys":[],"subject":主体,"content":窄目标原意,"status":合法五状态,"source":有效事实键,"fulfilled":有效事实键或null,"condition_ref":有效事实键或null,"deadline":原话或null,"condition":前提原话或null,"basis":本章变化依据事实键数组,"p":原段号,"q":逐字短引,"reason":具体依据}]}。
old_rows每个输入旧键一次；非计划仍保留原人物字段。plans只建立现行规则允许的本章新计划；前章已立计划不要重复创建。一个召回中多项独立计划可拆，但不能把愿望、困境强塞成计划。来源必须指向实际提出行动的有效事实；兑现必须是主体实际履约，条件出现要另有事实。一个计划的原话期限和前提分栏；未来时间是期限，前提发生才是条件。没有留null。
本章有效事实和原文逐项扫描，不能只照抄旧召回。即时将做的明确动作即使同章完成也可立项。假设回答须可发生且认真。不要生成早章计划，不能用现实知识猜结果。输入已有计划只供查重，不能重命名。编号由程序填写。'''
A_UPDATE = '''本步只为输入existing中每个既有计划判断本章状态，不能创建计划、改窄目标、修改过去状态或重命名。
输出 {"updates":[{"key":已有计划键,"status":合法五状态,"fulfilled":有效事实键或null,"condition_ref":有效事实键或null,"basis":本章变化依据事实键数组,"reason":具体短理由}]}，每个existing键恰好一次。
current_facts是本章证据，previous_facts只用于解析此前引用，不能把旧事实当本章新结果。计划原source由程序保留。
已开头的一次性动作仅在离场、期限过、前提排除时收尾；先核已做成。未开头且没有结果保持未执行；长期目标继续执行中。主动收回是放弃。已放弃后重做另起新计划。窄目标已成不能因更大目的失败标落空。状态变化必须给本章basis，兑现引用指向真履约事实。已结且没新证据可保留状态和兑现键，但原因不能套话。拿不准不要编结果，在reason明确具体疑点。'''


def parse(response):
    ch=response['choices'][0]
    if ch.get('finish_reason')!='stop':raise ValueError('输出未正常结束，禁止拼接截断')
    raw=ch.get('message',{}).get('content') or ''
    obj=json.loads(re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$','',raw))
    if not isinstance(obj,dict):raise ValueError('输出须为对象')
    return obj


def prompt(schema, material):
    return [dict(role='system',content=SYSTEM),dict(role='user',content=RULE+'\n'+schema+'\n输入材料：\n'+json.dumps(material,ensure_ascii=False,separators=(',',':')))]


def flag(doc,data,layer,key,reason,pids=None):
    flags=doc['review_audit']['review_flags']
    flags.append(dict(flag_id=f'R03:{layer}:{data["book_id"]}:{data["chapter"]}:{len(flags)}',book_id=data['book_id'],chapter=data['chapter'],
        category='格式引用缺口' if layer in ('B','C','A格式') else '管线语义黄标',fact_keys=[key] if layer=='B' else [],
        plan_keys=[key] if layer.startswith('A') and key else [],paragraph_ids=pids or [],reason=reason,conservative_text=None,original_gap_keys=[]))


def task(client,model,policy,schema,material,gate,folder,label,receipt,layer,reviewer=None):
    original=prompt(schema,material); current=original;last={};initial=None
    errors=[]
    for attempt in range(2):
        response=client.call(model,current,policy,max_tokens=16000 if layer!='C' else 24000)
        dump(folder/(label+f'_response_{attempt}.json'),response)
        receipt['calls'].append(dict(layer=layer,model=model,attempt=attempt,usage=response.get('usage',{})))
        try:
            last=parse(response)
            last,err,log=gate(last)
        except (ValueError,TypeError,KeyError,AttributeError) as e:
            err=[dict(path=label,error=str(e))];log=[]
        errors.append(err)
        dump(folder/(label+f'_gate_{attempt}.json'),dict(execution_identity='Codex',errors=err,conversions=log))
        signature=json.dumps(err,sort_keys=True,ensure_ascii=False)
        if initial is None:initial=signature
        if not err:break
        if attempt==1:break
        receipt['rewrites']+=1
        current=original+[dict(role='assistant',content=response['choices'][0]['message'].get('content') or '{}'),dict(role='user',content='机检明确错误：'+signature+'。只修这些错误，输出本步完整对象，其他正确内容保留。最多再写一次。')]
    if reviewer and not err:
        response=client.call(reviewer[0],original+[dict(role='assistant',content=json.dumps(last,ensure_ascii=False)),dict(role='user',content='执行身份：Codex。你是不同模型的独立复核员。逐项对原文核正文保真、主体、否定推测、计划合法性和履约、视角和场景格。只修有原文依据的错误，正确项原样保留，返回同结构完整JSON；不能按个人偏好重写。')],reviewer[1],max_tokens=24000)
        dump(folder/(label+'_independent_response.json'),response)
        receipt['calls'].append(dict(layer=layer,model=reviewer[0],attempt=0,independent=True,usage=response.get('usage',{})))
        try:
            reviewed,rerr,rlog=gate(parse(response))
            dump(folder/(label+'_independent_gate.json'),dict(errors=rerr,conversions=rlog))
            if not rerr:last=reviewed
            else:err=rerr
        except (ValueError,TypeError,KeyError,AttributeError) as e:err=[dict(path=label,error='独立复核格式未通过：'+str(e))]
    dump(folder/(label+'_task.json'),dict(execution_identity='Codex',layer=layer,model=model,rewrite_limit=1,rewrites=len(errors)-1,
        no_progress=bool(err) and initial==json.dumps(err,sort_keys=True,ensure_ascii=False),pending_errors=err))
    return last,err


def b_gate(raw,data):
    raw,log=normalize(raw,data);err=[]
    for k in ('keep','exclude','flag','replace','add'):
        if not isinstance(raw.get(k),list):raise ValueError(k+'须为数组')
    expected={f['local_key'] for f in data['facts']}
    seen=raw['keep']+raw['exclude']+raw['flag']+[r.get('key') for r in raw['replace'] if isinstance(r,dict)]
    if any(not isinstance(k,str) for k in seen):raise ValueError('旧键须字符串，不能是对象')
    for k in sorted(expected-set(seen)):err.append(dict(key=k,field='旧句去向',error='缺失'))
    for k in sorted(set(seen)-expected):err.append(dict(key=k,field='旧句去向',error='越界'))
    for k in sorted(set(seen)):
        if seen.count(k)>1:err.append(dict(key=k,field='旧句去向',error='重复'))
    sources={p['paragraph_id']:p['text'] for p in data['paragraphs']+data.get('context_paragraphs',[])}
    allowed=set(data['owned_paragraph_ids'])|{p for f in data['facts'] for p in f.get('paragraph_ids',[])}
    for kind in ('replace','add'):
        for i,row in enumerate(raw[kind]):
            if not isinstance(row,dict) or not isinstance(row.get('text'),str) or not row.get('text') or not isinstance(row.get('evidence'),list) or not row['evidence']:
                err.append(dict(path=f'{kind}[{i}]',error='须正文和非空逐字证据数组'));continue
            linked=[]
            for e in row['evidence']:
                if not isinstance(e,dict):err.append(dict(path=f'{kind}[{i}]',error='证据须对象'));continue
                pid=full_pid(e.get('p'),data);q=e.get('q')
                if pid not in sources or pid not in allowed or not isinstance(q,str) or not q or q not in sources[pid]:err.append(dict(path=f'{kind}[{i}]',paragraph_id=pid,error='责任范围内逐字证据未通过'))
                else:linked.append(sources[pid])
            for hit in re.findall(r'“([^”]+)”|「([^」]+)」|"([^"\n]+)"',row['text']):
                q=next(x for x in hit if x)
                if not any(q in s for s in linked):err.append(dict(path=f'{kind}[{i}]',error='正文直引不是证据段逐字子串'))
    return raw,err,log


def b_convert(raw,data,doc,pending):
    # 不把未知或重复旧键默判为沿用；每条未决旧句独立留黄。
    raw=copy.deepcopy(raw); expected={f['local_key'] for f in data['facts']}
    if not all(isinstance(raw.get(k),list) for k in ('keep','exclude','flag','replace','add')):raw={k:[] for k in ('keep','exclude','flag','replace','add')}
    safe={k:[] for k in ('keep','exclude','flag','replace','add')}; used=set()
    allkeys=[v for k in ('keep','exclude','flag') for v in raw[k] if isinstance(v,str)]+[r.get('key') for r in raw['replace'] if isinstance(r,dict)]
    for kind in ('keep','exclude','flag'):
        for k in raw[kind]:
            if isinstance(k,str) and k in expected and allkeys.count(k)==1:safe[kind].append(k);used.add(k)
    for kind in ('replace','add'):
        for i,row in enumerate(raw[kind]):
            if not isinstance(row,dict):continue
            key=row.get('key')
            if kind=='replace' and (key not in expected or allkeys.count(key)!=1):continue
            stub={k:[] for k in ('keep','exclude','flag','replace','add')};stub[kind]=[row]
            try:_,errs,_=b_gate(stub,dict(data,facts=[] if kind=='add' else [f for f in data['facts'] if f['local_key']==key]))
            except (ValueError,TypeError,KeyError,AttributeError):errs=[{}]
            if errs:
                if kind=='add':flag(doc,data,'B',None,'新增候选逐字或字段检查失败，已隔离',data['owned_paragraph_ids'])
                continue
            safe[kind].append(row)
            if kind=='replace':used.add(key)
    for k in sorted(expected-used):safe['flag'].append(k);flag(doc,data,'B',k,'有限重写后旧句处置未通过，临时保留旧正文但未判正确')
    for k in safe['flag']:
        if k in used:flag(doc,data,'B',k,'模型明确标为未决旧句')
    safe['paragraphs']=[];safe['scenes']=[]
    c,_=convert(safe,dict(data,owned_paragraph_ids=[]));c['C']=[];c['review_audit']['source_chapters']=[]
    doc['B'].extend(c['B']);doc['review_audit']['fact_chapters'].extend(c['review_audit']['fact_chapters'])


def c_gate(raw,data):
    raw,log=normalize(raw,data);err=[]
    if not isinstance(raw.get('paragraphs'),list) or not isinstance(raw.get('scenes'),list):raise ValueError('C须paragraphs/scenes两数组')
    sources={p['paragraph_id']:p['text'] for p in data['paragraphs']};owned=set(data['owned_paragraph_ids']);seen=[]
    for i,p in enumerate(raw['paragraphs']):
        if not isinstance(p,dict):err.append(dict(path=f'paragraphs[{i}]',error='段标注须对象'));continue
        pid=full_pid(p.get('id'),data);seen.append(pid)
        if pid not in owned or p.get('main') not in TAGS or p.get('secondary') is not None and (p.get('secondary') not in TAGS or p['secondary']==p['main']):err.append(dict(path=f'paragraphs[{i}]',paragraph_id=pid,error='段号或五种写法标签不合格'))
        if not isinstance(p.get('quote'),str) or not p.get('quote') or p['quote'] not in sources.get(pid,''):err.append(dict(path=f'paragraphs[{i}]',paragraph_id=pid,error='段短引不是逐字子串'))
        if not (p.get('viewpoint') is None or isinstance(p.get('viewpoint'),str)):err.append(dict(path=f'paragraphs[{i}]',paragraph_id=pid,error='视角须字符串或null'))
    for pid in sorted(owned-set(seen)):err.append(dict(paragraph_id=pid,field='段标注',error='缺失'))
    for pid in sorted(set(seen)):
        if seen.count(pid)>1:err.append(dict(paragraph_id=pid,field='段标注',error='重复'))
    for i,scene in enumerate(raw['scenes']):
        if not isinstance(scene,dict):err.append(dict(path=f'scenes[{i}]',error='场景须对象'));continue
        if not isinstance(scene.get('paragraph_ids'),list) or not scene['paragraph_ids'] or not {full_pid(p,data) for p in scene['paragraph_ids']}.issubset(owned):err.append(dict(path=f'scenes[{i}]',error='场景范围无效'))
        for field in ('location','light_weather','objects_visuals','sounds_smells','atmosphere'):
            if not isinstance(scene.get(field),list):err.append(dict(path=f'scenes[{i}]',field=field,error='五格须数组'));continue
            for v in scene[field]:
                if not isinstance(v,dict):err.append(dict(path=f'scenes[{i}]',field=field,error='格内须对象'));continue
                pid=full_pid(v.get('p'),data);q=v.get('q')
                if pid not in owned or not isinstance(q,str) or not q or q not in sources.get(pid,'') or not isinstance(v.get('text'),str) or v.get('text') in ('未写','无','不详'):err.append(dict(path=f'scenes[{i}]',field=field,paragraph_id=pid,error='场景格逐字、范围、占位检查失败'))
    return raw,err,log


def c_convert(raw,data,doc,pending):
    owned=data['owned_paragraph_ids'];source={p['paragraph_id']:p['text'] for p in data['paragraphs']}
    rows=raw.get('paragraphs',[]) if isinstance(raw.get('paragraphs'),list) else []
    paras=[]
    for pid in owned:
        matches=[r for r in rows if isinstance(r,dict) and isinstance(r.get('id'),str) and full_pid(r['id'],data)==pid]
        row=matches[0] if len(matches)==1 else {}
        try:_,err,_=c_gate(dict(paragraphs=[row],scenes=[]),dict(data,owned_paragraph_ids=[pid]))
        except (ValueError,TypeError,KeyError,AttributeError):err=[{}]
        if err:
            flag(doc,data,'C',None,'有限重写后段标注未通过，保留原段位置与逐字短引，标签和视角未判',[pid])
            row=dict(main=None,secondary=None,viewpoint=None,quote=source[pid][:32],note='标签与视角未判，需复核')
        paras.append(dict(paragraph_id=pid.rsplit(':',1)[-1],main_tag=row.get('main'),secondary_tag=row.get('secondary'),viewpoint=row.get('viewpoint'),quote=row.get('quote'),review_status='限审' if err else '已标注',note=row.get('note','')))
    scenes=[]
    for i,row in enumerate(raw.get('scenes',[]) if isinstance(raw.get('scenes'),list) else []):
        try:_,err,_=c_gate(dict(paragraphs=[],scenes=[row]),dict(data,owned_paragraph_ids=[]))
        except (ValueError,TypeError,KeyError,AttributeError):err=[{}]
        # 按场景核对时不要求重复全部段标注。
        try:
            pids=[full_pid(p,data) for p in row['paragraph_ids']]
            valid=bool(pids) and set(pids).issubset(owned)
            out=dict(scene_id=f'R03:scene:{data["book_id"]}:{data["chapter"]}:{data["group"]}:{i}',paragraph_ids=[p.rsplit(':',1)[-1] for p in pids])
            for field in ('location','light_weather','objects_visuals','sounds_smells','atmosphere'):
                out[field]=[]
                for v in row[field]:
                    p=full_pid(v['p'],data);q=v['q']
                    valid=valid and p in owned and isinstance(q,str) and bool(q) and q in source.get(p,'') and isinstance(v.get('text'),str) and v['text'] not in ('未写','无','不详')
                    out[field].append(dict(text=v['text'],evidence=[dict(paragraph_id=p,quote=q)]))
            if valid:scenes.append(out)
            else:flag(doc,data,'C',None,'场景格范围或逐字证据未通过，已隔离该场景',owned)
        except (ValueError,TypeError,KeyError,AttributeError):flag(doc,data,'C',None,'场景格字段未通过，已隔离该场景',owned)
    doc['C'].append(dict(book_id=data['book_id'],chapter=data['chapter'],paragraphs=paras,scenes=scenes))


def a_gate(raw,kind,material):
    err=[];conversion_log=[];sources={p['paragraph_id']:p['text'] for p in material['paragraphs']}
    current={f['local_key'] for f in material['current_facts']};known=current|{f['local_key'] for f in material.get('previous_facts',[])}
    if kind=='discover':
        if not isinstance(raw.get('old_rows'),list) or not isinstance(raw.get('plans'),list):raise ValueError('A发现须old_rows/plans两数组')
        expected={r['local_key'] for r in material['old_plan_rows']};seen=[r.get('key') for r in raw['old_rows'] if isinstance(r,dict)]
        if any(not isinstance(k,str) for k in seen):raise ValueError('旧行key须字符串')
        for key in sorted(expected-set(seen)):err.append(dict(key=key,field='旧召回去向',error='缺失',native_field=next(r.get('native_field') for r in material['old_plan_rows'] if r['local_key']==key)))
        for key in sorted(set(seen)-expected):err.append(dict(key=key,field='旧召回去向',error='越界'))
        for key in seen:
            if seen.count(key)>1:err.append(dict(key=key,field='旧召回去向',error='重复'))
        for i,r in enumerate(raw['old_rows']):
            if not isinstance(r,dict) or r.get('meaning') not in ('沿用原意','修正原意','非计划保留原类','审查批注','未决'):err.append(dict(path=f'old_rows[{i}]',error='去向meaning值错误'))
        for i,r in enumerate(raw['plans']):
            if isinstance(r,dict):
                try:
                    stub, conversions = normalize(dict(add=[dict(evidence=[dict(p=r.get('p'),q=r.get('q'))])]), dict(material,owned_paragraph_ids=list(sources),facts=[]))
                    r['p']=stub['add'][0]['evidence'][0]['p']
                    conversion_log.extend(dict(c,path='plans['+str(i)+'].p') for c in conversions)
                except ValueError as e:
                    err.append(dict(path='plans['+str(i)+']',error=str(e)))
                    continue
            if not isinstance(r,dict):err.append(dict(path=f'plans[{i}]',error='计划须对象'));continue
            if not isinstance(r.get('content'),str) or not r.get('content') or not isinstance(r.get('subject'),str) or not r['subject']:err.append(dict(path=f'plans[{i}]',error='计划正文或主体缺失'))
            if not isinstance(r.get('old_keys'),list) or not set(r['old_keys']).issubset(expected):err.append(dict(path=f'plans[{i}]',error='old_keys须已提供旧召回键数组'))
            if r.get('source') not in current:err.append(dict(path=f'plans[{i}]',error='来源须本章有效事实键'))
            pid=full_pid(r.get('p'),material);q=r.get('q')
            if pid not in sources or not isinstance(q,str) or not q or q not in sources[pid]:err.append(dict(path=f'plans[{i}]',error='计划来源逐字证据未通过',paragraph_id=pid))
            for field in ('deadline','condition'):
                if r.get(field) is not None and not isinstance(r.get(field),str):err.append(dict(path=f'plans[{i}]',field=field,error='须原话字符串或null'))
        rows=raw['plans']
    else:
        if not isinstance(raw.get('updates'),list):raise ValueError('A更新须updates数组')
        expected={r['key'] for r in material['existing']};seen=[r.get('key') for r in raw['updates'] if isinstance(r,dict)]
        if any(not isinstance(k,str) for k in seen):raise ValueError('更新key须字符串')
        for k in sorted(expected-set(seen)):err.append(dict(key=k,field='计划本章状态',error='缺失'))
        for k in sorted(set(seen)-expected):err.append(dict(key=k,field='计划本章状态',error='越界'))
        for k in seen:
            if seen.count(k)>1:err.append(dict(key=k,field='计划本章状态',error='重复'))
        rows=raw['updates']
    for i,r in enumerate(rows):
        if not isinstance(r,dict):continue
        if r.get('status') not in STATUSES:err.append(dict(path=f'{kind}[{i}]',error='状态须五种之一'))
        for field in ('fulfilled','condition_ref'):
            if r.get(field) is not None and r[field] not in known:err.append(dict(path=f'{kind}[{i}]',field=field,error='引用不在有效事实版本'))
        if r.get('status')=='兑现' and not r.get('fulfilled'):err.append(dict(path=f'{kind}[{i}]',error='兑现缺履约事实键'))
        if not isinstance(r.get('basis'),list) or not set(r['basis']).issubset(current):err.append(dict(path=f'{kind}[{i}]',error='basis须本章有效事实键数组'))
    return raw,err,conversion_log


def a_apply(raw,material,chapter,prior,kind,pending):
    bid,ch=material['book_id'],material['chapter']
    if kind=='discover':
        accepted=[]
        for i,r in enumerate(raw.get('plans',[]) if isinstance(raw.get('plans'),list) else []):
            stub=dict(old_rows=[],plans=[r])
            try:_,err,_=a_gate(stub,'discover',dict(material,old_plan_rows=[v for v in material['old_plan_rows'] if v['local_key'] in r.get('old_keys',[])]));err=[e for e in err if e.get('field')!='旧召回去向']
            except (ValueError,TypeError,KeyError,AttributeError):err=[{}]
            if err:flag(chapter,material,'A',None,'新计划字段、引用或逐字证据未通过，已隔离');continue
            if any(v.get('plan') and v['plan']['content']==r['content'] and v.get('subject_text')==r['subject'] and (v.get('candidate_refs') or {}).get('source_record_key')==r['source'] for v in prior['A']):continue
            key=f'R03:plan:{bid}:ch{ch}:{i}';cid=key+':A';accepted.append((key,r))
            refs=dict(source_record_key=r['source'],fulfilled_record_key=r.get('fulfilled'),condition_record_key=r.get('condition_ref'))
            chapter['A'].append(dict(change_id=cid,book_id=bid,as_of_chapter=ch,old_ledger_keys=r.get('old_keys',[]),decision='修订' if r.get('old_keys') else '新增',subject_text=r['subject'],
                plan=dict(content=r['content'],scope='in_book_character',status=r['status'],source_fact_ref=None,fulfilled_fact_ref=None,deadline=dict(text=r['deadline'],story_time=None) if r.get('deadline') else None,condition=r.get('condition'),condition_fact_ref=None),candidate_refs=refs,reason=r.get('reason',''),evidence=[dict(paragraph_id=full_pid(r['p'],material),quote=r['q'])]))
            chapter['review_audit']['plan_history'].append(dict(plan_key=key,book_id=bid,old_ledger_keys=r.get('old_keys',[]),A_change_ids=[cid],introduced_chapter=ch,
                states=[dict(chapter=ch,status=r['status'],**refs,change_basis_record_keys=r.get('basis',[]),note=r.get('reason',''))]))
        for old in material['old_plan_rows']:
            rows=[r for r in raw.get('old_rows',[]) if isinstance(r,dict) and r.get('key')==old['local_key']]
            row=rows[0] if len(rows)==1 else {};keys=[k for k,r in accepted if old['local_key'] in r.get('old_keys',[])]
            meaning=row.get('meaning','未决')
            if meaning not in ('沿用原意','修正原意','非计划保留原类','审查批注','未决'):meaning='未决'
            if meaning in ('沿用原意','修正原意') and not keys:meaning='未决'
            if meaning=='未决':flag(chapter,material,'A',old['local_key'],'旧召回去向未解决，原字段保留但计划分类未判')
            chapter['review_audit']['old_plan_rows'].append(dict(old_key=old['local_key'],meaning=meaning,plan_keys=keys,retained_native_field=old.get('native_field') if not keys else None,note=row.get('reason','本次未能判定')))
            if not keys:
                chapter['A'].append(dict(change_id=f'R03:old:{bid}:{ch}:{old["local_key"]}',book_id=bid,as_of_chapter=ch,old_ledger_keys=[old['local_key']],decision='撤回计划分类',subject_text='、'.join(old.get('subject_mentions') or []),plan=None,candidate_refs=None,reason=row.get('reason','计划分类未判，保留原类去向'),evidence=[]))
    else:
        histories={h['plan_key']:h for h in prior['review_audit']['plan_history']}
        for item in material['existing']:
            matches=[r for r in raw.get('updates',[]) if isinstance(r,dict) and r.get('key')==item['key']]
            r=matches[0] if len(matches)==1 else {}
            try:_,err,_=a_gate(dict(updates=[r]),'update',dict(material,existing=[item]))
            except (ValueError,TypeError,KeyError,AttributeError):err=[{}]
            if err:
                # 缺状态不自动延续，保留既有历史并明确本章未判断。
                flag(chapter,material,'A',item['key'],'有限重写后本章状态未判，旧历史保留且本章未追加');continue
            old=histories[item['key']];h=copy.deepcopy(old);h['states']=[dict(chapter=ch,status=r['status'],source_record_key=item['source'],fulfilled_record_key=r.get('fulfilled'),condition_record_key=r.get('condition_ref'),change_basis_record_keys=r.get('basis',[]),note=r.get('reason',''))]
            chapter['review_audit']['plan_history'].append(h)
            for oldrow in prior['A']:
                if oldrow['change_id'] in old['A_change_ids']:chapter['A'].append(copy.deepcopy(oldrow))


def replay_task(source,ch,label,gate,folder,receipt):
    source=external(source)/('ch'+ch)
    files=sorted(source.glob(label+'_response_[01].json'))
    candidates=[]
    for path in files:
        raw={}
        try:
            raw=parse(json.loads(path.read_text()))
            converted,errs,log=gate(raw)
            raw=converted
        except (ValueError,TypeError,KeyError,AttributeError) as e:
            errs=[dict(path=label,error=str(e))];log=[]
        candidates.append((len(errs),path.name,raw,errs,log,path))
    if not candidates:raise ValueError('确定复放缺少原响应：'+str(source/label))
    # 已有最多两个候选，闸门错误更少优先，同数取较新的修正响应，不增模型调用。
    candidates.sort(key=lambda r:(r[0],-int(r[1].rsplit('_',1)[-1].split('.')[0])))
    _,name,raw,errs,log,path=candidates[0]
    record=dict(execution_identity='Codex',source_path=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),conversions=log,pending_errors=errs)
    dump(folder/(label+'_replay.json'),record)
    dump(folder/(label+'_task.json'),dict(record,rewrite_limit=0,rewrites=0,replayed=True))
    receipt['replayed_steps'].append(dict(chapter=ch,label=label,source=str(path),sha256=record['source_sha256']))
    return raw,errs


from pr_independent_r03 import task_judged as task

def run(args):
    output=external(args.out);output.mkdir(parents=True,exist_ok=True)
    config=next(c for c in json.loads((OUT/'books_selected.json').read_text()) if c['code']==args.book)
    models={k:getattr(args,k.lower()+'_model') or args.model for k in ('A','B','C')}
    policies=json.loads(external(args.policy).read_text());client=Client();result=empty_result();result['batch_id']='PR_R03'
    receipt=dict(execution_identity='Codex',book=args.book,model=args.model,layer_models=models,round=args.round,chapters_requested=args.chapters,completed_chapters=[],clean_chapters=[],degraded_chapters=[],
        calls=[],rewrites=0,partial=False,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),config=dict(b_group=args.b_group,c_group=args.c_group,a_group=args.a_group,review_model=args.review_model),unmeasured=['已保存正式版本接入','隐含语义人工真值'])
    catalog=[]
    receipt['replay_source']=args.replay_bc
    receipt['replayed_steps']=[]
    for n in range(1,args.chapters+1):
        ch=f'{n:02d}';data=read_book(config,ch);folder=output/('ch'+ch);folder.mkdir(exist_ok=True);doc=empty_result();degraded=[]
        try:
            for piece in groups(data,args.b_group):
                label='B_g'+str(piece['group'])
                material={k:v for k,v in piece.items() if k not in ('basis_hashes',)}
                reviewer=(args.review_model,policies[args.review_model]['parameters']) if args.review_model and args.review_model!=models['B'] else None
                raw,pending=replay_task(args.replay_bc,ch,label,lambda raw:b_gate(raw,piece),folder,receipt) if args.replay_bc else task(client,models['B'],policies[models['B']]['parameters'],B_SCHEMA,material,lambda raw:b_gate(raw,piece),folder,label,receipt,'B',reviewer)
                b_convert(raw,piece,doc,pending)
                if pending:degraded.append(label)
            # C按标注组和现场范围独立负责，不沿用B组范围。
            for start in range(0,len(data['paragraphs']),args.c_group):
                ps=data['paragraphs'][start:start+args.c_group];g=start//args.c_group
                piece=dict(data,paragraphs=ps,owned_paragraph_ids=[p['paragraph_id'] for p in ps],group=g,facts=[],context_paragraphs=[])
                reviewer=(args.review_model,policies[args.review_model]['parameters']) if args.review_model and args.review_model!=models['C'] else None
                label='C_g'+str(g)
                raw,pending=replay_task(args.replay_bc,ch,label,lambda raw:c_gate(raw,piece),folder,receipt) if args.replay_bc else task(client,models['C'],policies[models['C']]['parameters'],C_SCHEMA,piece,lambda raw:c_gate(raw,piece),folder,label,receipt,'C',reviewer)
                c_convert(raw,piece,doc,pending)
                if pending:degraded.append('C_g'+str(g))
            facts=chapter_facts(data,doc)
            common=dict(book_id=data['book_id'],chapter=ch,paragraphs=data['paragraphs'],scope_limits=data['scope_limits'],current_facts=facts,previous_facts=catalog)
            histories={h['plan_key']:h for h in result['review_audit']['plan_history']}
            existing=[]
            for key,h in histories.items():
                row=next((r for r in result['A'] if r['change_id'] in h['A_change_ids'] and r.get('plan')),None)
                if row:
                    existing.append(dict(key=key,subject=row.get('subject_text'),plan=row['plan'],source=h['states'][0].get('source_record_key'),previous_state=h['states'][-1]))
            for start in range(0,len(existing),args.a_group):
                material=dict(common,existing=existing[start:start+args.a_group]);label='A_update'+str(start//args.a_group)
                reviewer=(args.review_model,policies[args.review_model]['parameters']) if args.review_model and args.review_model!=models['A'] else None
                raw,pending=task(client,models['A'],policies[models['A']]['parameters'],A_UPDATE,material,lambda raw:a_gate(raw,'update',material),folder,label,receipt,'A',reviewer)
                for e in pending:
                    if e.get('independent'):flag(doc,data,'A',e.get('key'),e['error'])
                a_apply(raw,material,doc,result,'update',pending)
                if pending:degraded.append(label)
            material=dict(common,old_plan_rows=data['old_plan_rows'],existing=existing)
            reviewer=(args.review_model,policies[args.review_model]['parameters']) if args.review_model and args.review_model!=models['A'] else None
            raw,pending=task(client,models['A'],policies[models['A']]['parameters'],A_DISCOVER,material,lambda raw:a_gate(raw,'discover',material),folder,'A_discover',receipt,'A',reviewer)
            a_apply(raw,material,doc,result,'discover',pending)
            for e in pending:
                if e.get('independent'):flag(doc,data,'A',e.get('key'),e['error'])
            if pending:degraded.append('A_discover')
            # 每段去向来自当前生效事实的位置；未绑定不自动叫无事实。
            for p in data['paragraphs']:
                pid=p['paragraph_id'];bound=[]
                for f in facts:
                    ids=f.get('paragraph_ids') or [e['paragraph_id'] for e in f.get('evidence') or []]
                    if pid in ids:bound.append(f['local_key'])
                doc['review_audit']['source_chapters'].append(dict(book_id=data['book_id'],chapter=ch,paragraphs=[dict(paragraph_id=pid.rsplit(':',1)[-1],fact_record_keys=bound,disposition='已有句承接' if bound else '未决',note='' if bound else '事实去向未判')]))
                if not bound:flag(doc,data,'B',None,'本段没有声明可用事实去向，仍需核对',[pid])
            assemble(result,doc);catalog.extend(facts);receipt['completed_chapters'].append(ch)
            count=len(doc['review_audit']['review_flags'])
            if degraded:receipt['degraded_chapters'].append(dict(chapter=ch,steps=degraded,yellow_count=count))
            else:receipt['clean_chapters'].append(ch)
            dump(folder/'result.json',doc);dump(folder/'delivery.json',dict(execution_identity='Codex',chapter=ch,degraded_steps=degraded,yellow_count=count))
            print('R03章节交付',args.book,ch,'降级步骤',len(degraded),'黄标',count,flush=True)
            dump(output/'prediction.json',result);dump(output/'run_receipt.json',receipt)
        except Exception as e:
            receipt['partial']=True;receipt['error']=str(e);dump(folder/'failure.json',dict(error=str(e)));break
    receipt['usage']={k:sum(c['usage'].get(k,0) for c in receipt['calls']) for k in ('prompt_tokens','completion_tokens')}
    dump(output/'prediction.json',result);dump(output/'run_receipt.json',receipt)
    return int(receipt['partial'])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--book',required=True);p.add_argument('--model',choices=MODELS,required=True);p.add_argument('--out',required=True)
    p.add_argument('--round',type=int,choices=range(1,9),required=True);p.add_argument('--chapters',type=int,default=8)
    for k in ('a','b','c'):p.add_argument('--'+k+'-model',choices=MODELS)
    p.add_argument('--b-group',type=int,default=16);p.add_argument('--c-group',type=int,default=24);p.add_argument('--a-group',type=int,default=8)
    p.add_argument('--replay-bc')
    p.add_argument('--policy',default=str(OUT/'probe/reasoning_policy.json'));p.add_argument('--review-model',choices=MODELS)
    args=p.parse_args()
    allowed={c['code'] for c in json.loads((OUT/'books_selected.json').read_text())}
    if args.book not in allowed or args.book=='xuezhong':p.error('只允许运行已登记开发集或留出集')
    if not 1<=args.chapters<=8 or min(args.b_group,args.c_group,args.a_group)<1:p.error('责任范围不合法')
    return run(args)


if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
# 执行身份：Codex
"""针对长输出截断的分组候选；输入内容只读，结果只放外部交付目录。"""
import argparse
import concurrent.futures
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

from pr_pipeline_r02 import (AUDIT, BOOKS, MODELS, OUT, RULES, FORMAT, SYSTEM,
                             assemble, dump, empty_result, external, read_book,
                             check_quote_guard, TRANSPORT_RETRIES)

from pr_checked_client_r02 import Client
from pr_shape_guard_r02 import BC_SCHEMA, A_SCHEMA

GROUP_SIZE=8
WORKERS=2
REPAIR_LIMIT=1
BC_FORMAT='''本步仅处理分组的事实与原文材料，不分类人物计划。输出对象有 B,C,fact_chapters,source_chapters,review_flags 五数组。
B 的字段沿用下面的结构；C 只列 owned_paragraph_ids 指定的段，场景也只能覆盖这些段。facts 是本组负责处置的旧句，四种旧句去向必须互斥完整。context_paragraphs 是这些旧句关联的上下文，不能仅因见到上下文就重复新增事实或多标 C。旧句跨段的明写内容不割断。仅为 owned 段新增漏掉的事实；一个旧句完整且正确就沿用，不能按段机械重写。相邻其他组的正确旧句在 context_fact_keys 中，不要另建同义句。若不能确定本组原段的去向，留具体黄标，不编事实。所有证据用完整段号和连续短引。
C 内 paragraph_id、paragraph_ids 用短号 pNNN；quote 是本段核心短引。场景五格严格保留原文写出的感知材料，没有就空数组。B 的新键必须带给定 new_key_prefix。每条理由具体简短。不输出 A 或逐章计划历史。'''
A_FORMAT='''本步只更新人物计划账，不能重抽、改写事实或 C。输出 A,old_plan_rows,plan_history,open_plan_keys,review_flags 五数组。
current_effective_facts 是本章有效事实句，previous_plans 是前章已形成的计划与状态历史。本章原文用于核对真实归属、条件和结果，但候选引用必须指向有效事实键；缺失事实要黄标，不编引用。
本章新有效计划用给定 new_plan_prefix 的稳定键；前章有效计划沿用原 plan_key、A_change_ids，逐条给本章状态，不重复或改写早章状态。状态变化须本章事实证据；所有既有计划本章无变化也保留状态。旧召回行逐行归类，非计划保留原字段归属，不能省略为模板。条件、期限和窄目标按规则判断，不借后章或常识补结果。
plan_history 每项 book_id、old_ledger_keys、A_change_ids、introduced_chapter、states；states 只列本章。A 用标准字段，正式事实引用保持 null，本地 candidate_refs 如实填写。不要输出 B、C 或另外三个核对数组。'''


def parse_parts(response,fields):
    choice=response['choices'][0]
    if choice.get('finish_reason')!='stop':
        raise ValueError('分步输出截断或未正常结束')
    text=choice['message']['content']
    text=re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$','',text)
    obj=json.loads(text)
    if not isinstance(obj,dict) or any(not isinstance(obj.get(k),list) for k in fields):
        raise ValueError('分步结构缺数组')
    return obj


def groups(data,size=GROUP_SIZE):
    ps=data['paragraphs'];lookup={p['paragraph_id']:p for p in ps}
    owner={p['paragraph_id']:i//size for i,p in enumerate(ps)}
    assigned={}
    for f in data['facts']:
        matches=[owner[k] for k in f.get('paragraph_ids',[]) if k in owner]
        assigned[f['local_key']]=min(matches) if matches else 0
    output=[]
    for g,start in enumerate(range(0,len(ps),size)):
        owned=ps[start:start+size];facts=[f for f in data['facts'] if assigned[f['local_key']]==g]
        ids={p['paragraph_id'] for p in owned}
        context={k for f in facts for k in f.get('paragraph_ids',[]) if k in lookup}-ids
        output.append(dict(book_id=data['book_id'],chapter=data['chapter'],group=g,
            owned_paragraph_ids=[p['paragraph_id'] for p in owned],paragraphs=owned,
            context_paragraphs=[lookup[k] for k in sorted(context)],facts=facts,
            context_fact_keys=[f['local_key'] for f in data['facts'] if assigned[f['local_key']]!=g and ids.intersection(f.get('paragraph_ids',[]))],
            scope_limits=data['scope_limits'],new_key_prefix=f"local:pr:{data['book_id']}:ch{data['chapter']}:g{g}:add:"))
    return output


def prompt(materials,step):
    return [{'role':'system','content':SYSTEM}, {'role':'user','content':RULES+'\n'+(BC_SCHEMA if step==BC_FORMAT else A_SCHEMA)+'\n'+step+'\n输入材料：\n'+json.dumps(materials,ensure_ascii=False,separators=(',',':'))}]


def audit_missing(candidate,data,part):
    """不替模型决定去向；遗漏编号只生成可复核的格式黄标。"""
    ra=candidate['review_audit']
    present=[]
    for a in ra['fact_chapters']:
        for k in ('kept_old_keys','revised_old_keys','excluded_nonstory_keys','flagged_old_keys'):
            present.extend(a.get(k,[]))
    expected={f['local_key'] for f in data['facts']}
    missing=sorted(expected-set(present));duplicates=sorted({k for k in present if present.count(k)>1})
    if missing or duplicates:
        ra['review_flags'].append(dict(flag_id=f"PR:{data['book_id']}:{data['chapter']}:{part}:audit",book_id=data['book_id'],chapter=data['chapter'],category='格式引用缺口',fact_keys=missing+duplicates,plan_keys=[],paragraph_ids=[],reason='旧句去向存在遗漏或重复，需要复核；程序不自动沿用',conservative_text=None,original_gap_keys=[]))


def make_bc(obj,data,part):
    c=empty_result();c['B']=copy.deepcopy(obj['B']);c['C']=copy.deepcopy(obj['C'])
    for k in ('fact_chapters','source_chapters','review_flags'):
        c['review_audit'][k]=copy.deepcopy(obj[k])
    for i,row in enumerate(c['B']):
        row['change_id']=f"PR:B:{data['book_id']}:{data['chapter']}:{part}:{i}"
        row['book_id']=data['book_id'];row['chapter']=data['chapter']
    audit_missing(c,data,part)
    return c


def bc_call(data,policy,model,output,guard):
    part='g'+str(data['group']);messages=prompt(data,BC_FORMAT)
    response=Client().call(model,messages,policy['parameters'],max_tokens=12000)
    dump(output/(part+'_response.json'),response)
    usages=[response.get('usage',{})]
    obj=parse_parts(response,('B','C','fact_chapters','source_chapters','review_flags'))
    candidate=make_bc(obj,data,part)
    if guard=='quotes':
        lookup_data={'paragraphs':data['paragraphs']+data['context_paragraphs']}
        errors=check_quote_guard(candidate,lookup_data);dump(output/(part+'_checks_before.json'),errors)
        if errors:
            repair=messages+[{'role':'assistant','content':json.dumps(obj,ensure_ascii=False)},
                {'role':'user','content':'只修以下逐字引文错误，保留其他正确内容，输出本步完整五数组：'+json.dumps(errors,ensure_ascii=False)}]
            response=Client().call(model,repair,policy['parameters'],max_tokens=12000)
            dump(output/(part+'_repair_response.json'),response);usages.append(response.get('usage',{}))
            candidate=make_bc(parse_parts(response,('B','C','fact_chapters','source_chapters','review_flags')),data,part)
            after=check_quote_guard(candidate,lookup_data);dump(output/(part+'_checks_after.json'),after)
            if after:
                dump(output/(part+'_stop_rule.json'),{'retry_limit':REPAIR_LIMIT,'before':len(errors),'after':len(after),'no_progress':len(after)>=len(errors)})
                candidate['review_audit']['review_flags'].append(dict(flag_id=f"PR:{data['book_id']}:{data['chapter']}:{part}:quote",book_id=data['book_id'],chapter=data['chapter'],category='管线语义黄标',fact_keys=sorted({e['key'] for e in after if e.get('key')}),plan_keys=[],paragraph_ids=[],reason='一次逐字引文重写后仍有错误，停止重试并待复核',conservative_text=None,original_gap_keys=[]))
    dump(output/(part+'_result.json'),candidate)
    return candidate,usages


def chapter_facts(data,candidate):
    covered={k for b in candidate['B'] for k in b.get('old_record_keys',[])}|{b['local_key'] for b in candidate['B'] if b.get('local_key')}
    kept={k for a in candidate['review_audit']['fact_chapters'] for k in a.get('kept_old_keys',[])+a.get('flagged_old_keys',[])}-covered
    return [{'local_key':f['local_key'],'text':f['text'],'paragraph_ids':f.get('paragraph_ids',[])} for f in data['facts'] if f['local_key'] in kept]+[{k:b.get(k) for k in ('local_key','text','evidence')} for b in candidate['B']]


def execute_groups(pieces,call):
    """仅维持两个在途组；出现失败就不启动下一组，等待已发请求结算。"""
    results={};failed=[];remaining=iter(pieces);aborted=False
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        running={}
        for _ in range(WORKERS):
            p=next(remaining,None)
            if p is not None:running[pool.submit(call,p)]=p['group']
        while running:
            done,_=concurrent.futures.wait(running,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                idx=running.pop(future)
                try:results[idx]=future.result()
                except Exception as exc:
                    failed.append({'group':idx,'error':str(exc)});aborted=True
            if not aborted:
                for _ in done:
                    p=next(remaining,None)
                    if p is not None:running[pool.submit(call,p)]=p['group']
        if aborted:
            failed.extend({'group':p['group'],'error':'前组失败，本组未启动'} for p in remaining)
    return results,failed


def run(args):
    output=external(args.out);output.mkdir(parents=True,exist_ok=True)
    config=next(r for r in json.loads((OUT/'books_selected.json').read_text()) if r['code']==args.book)
    policy=json.loads(external(args.policy).read_text())[args.model]
    if not policy['usable']:raise ValueError('模型参数未验证')
    result=empty_result()
    receipt=dict(book=args.book,model=args.model,round=args.round,chapters_requested=args.chapters,completed_chapters=[],calls=[],partial=False,
        strategy='split_BC_then_A',group_size=GROUP_SIZE,workers=WORKERS,repair_retry_limit=REPAIR_LIMIT,
        transport_retry_limit=TRANSPORT_RETRIES,unmeasured=['语义独立复核'],
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),base_code_sha256=hashlib.sha256(Path(sys.modules['pr_pipeline_r02'].__file__).read_bytes()).hexdigest())
    for n in range(1,args.chapters+1):
        ch=f'{n:02d}';data=read_book(config,ch);folder=output/('ch'+ch);folder.mkdir(exist_ok=True)
        chapter=empty_result();failed=[]
        pieces=groups(data)
        try:
            results,failed=execute_groups(pieces,lambda p:bc_call(p,policy,args.model,folder,args.guard))
            if failed:raise ValueError('本章有未完成分组：'+json.dumps(failed,ensure_ascii=False))
            for idx in sorted(results):
                part,usages=results[idx];receipt['calls'].extend(usages)
                chapter['B'].extend(part['B']);chapter['C'].extend(part['C'])
                for k in ('fact_chapters','source_chapters','review_flags'):chapter['review_audit'][k].extend(part['review_audit'][k])
            keys=[r.get('local_key') for r in chapter['B'] if r.get('local_key')]
            if len(keys)!=len(set(keys)):raise ValueError('分组间事实键冲突，不能悄悄覆盖')
            materials=dict(book_id=data['book_id'],chapter=ch,paragraphs=data['paragraphs'],old_plan_rows=data['old_plan_rows'],scope_limits=data['scope_limits'],
                current_effective_facts=chapter_facts(data,chapter),previous_plans={'A':result['A'],'plan_history':result['review_audit']['plan_history']},
                new_plan_prefix=f"PR:plan:{data['book_id']}:ch{ch}:")
            response=Client().call(args.model,prompt(materials,A_FORMAT),policy['parameters'],max_tokens=12000)
            dump(folder/'A_response.json',response);receipt['calls'].append(response.get('usage',{}))
            obj=parse_parts(response,('A','old_plan_rows','plan_history','open_plan_keys','review_flags'))
            chapter['A']=obj['A']
            for k in ('old_plan_rows','plan_history','open_plan_keys'):chapter['review_audit'][k]=obj[k]
            chapter['review_audit']['review_flags'].extend(obj['review_flags'])
            assemble(result,chapter);receipt['completed_chapters'].append(ch)
            dump(folder/'result.json',chapter);dump(output/'prediction.json',result);dump(output/'run_receipt.json',receipt)
            print('分步本章已落盘',args.book,ch,flush=True)
        except Exception as exc:
            receipt['partial']=True;receipt['error']='本章分步未完成：'+str(exc);dump(folder/'failure.json',failed)
            result['unresolved'].append({'book_id':data['book_id'],'chapter':ch,'keys':[],'reason':receipt['error']})
            break
    receipt['usage']={k:sum(float(c.get(k,0)) for c in receipt['calls']) for k in ('prompt_tokens','completion_tokens')}
    dump(output/'prediction.json',result);dump(output/'run_receipt.json',receipt)
    return int(receipt['partial'])


def main():
    p=argparse.ArgumentParser(description='R02分步字段形状修复候选，不扩大书目')
    p.add_argument('--book',choices=BOOKS,required=True);p.add_argument('--model',choices=MODELS,required=True)
    p.add_argument('--out',required=True);p.add_argument('--round',type=int,choices=range(1,7),required=True)
    p.add_argument('--chapters',type=int,choices=range(1,9),default=8)
    p.add_argument('--guard',choices=('none','quotes'),default='none');p.add_argument('--policy',default=str(OUT/'probe/reasoning_policy.json'))
    return run(p.parse_args())


if __name__=='__main__':raise SystemExit(main())

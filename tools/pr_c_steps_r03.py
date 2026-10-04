# 执行身份：Codex
"""C层拆成逐段写法/感知者，再整章现场五格；对照时复用已有A/B。"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from pr_layers_v2_r03 import (OUT, MODELS, Client, dump, external, read_book,
    empty_result, task, c_gate, c_convert, full_pid)

ANNOTATE = '''本步只按原段标写法与感知者，不抽事实，不建计划，不建场景格。
输出 {"paragraphs":[{"id":输入段号,"main":"叙述带过/动作展开/对话/心理/场景五种中的一种","secondary":null或另一种标签,"viewpoint":明确感知者人物名或全知或切换或null,"quote":本段连续逐字短引,"note":具体短说明或空字符串}]}。
每个责任段恰好一次。主标签按本段主要表达方式选：叙述带过是概述或交代；动作展开是铺开过程；对话是当场言语；心理是内心过程；场景是环境画面。不能把交代一句动作也一律当展开。副标签只有本段同时展开另一写法才用，没有就null；不能因出现一个心理动词或少量对白机械加副标签。
视角按这一段谁在看、听、心想或感受，不能按说话人自动选；没有人物感知限定的外部叙述可用全知，证据不足留null，不编人物、不加分析括注。回述对象不是当前感知者。同章镜头可以延续：不能仅因本段没有看听等动词就自动换成全知，也不能仅因有人物出现就认定他的视角。确有多个感知镜头切换才标切换。read_only_chapter_context只供判断上下文，不能输出其段标注。只输出paragraphs数组，不输出scenes或其他层。
虚构结构例：{"paragraphs":[{"id":"p001","main":"对话","secondary":null,"viewpoint":null,"quote":"我明天来修木桥","note":""}]}。示例只示结构，不作为标签与视角的语义答案。'''
SCENES = '''本步只读整章原文摘当前现场的五格，不改写法标注，不抽事实，不建人物计划。
输出 {"scenes":[{"paragraph_ids":同一现场的原段号数组,"location":[],"light_weather":[],"objects_visuals":[],"sounds_smells":[],"atmosphere":[]}]}。
每格每项{text,p,q}；text摘原文中这一格对应的连续具体材料，p为输入段号，q为相同原段的逐字短引。不要为凑五格改写或概括。没写为空数组，不放占位词。
地点只放现场空间；光线天气只放光照或天气，不放钟点；视觉物只放可见陈设、器物或环境外观，不放人的动作；声音气味只放声音特征或气味，不把台词内容当声音材料；氛围只放环境气氛，不放某个人的情绪。普通动作和个人反应仍由事实层负责。
现场可跨前一步写法小组；按场景内容组织，不能每24段机械另建。回忆、讲述、梦境、内层故事提到的环境不当当前现场。不得补常识；一个原文短片段不要重复塞到多格。只输出scenes数组，段号可完整号或输入短号，逐字引文不能用省略号拼接。'''


def run_c(data,client,model,parameters,folder,receipt,group_size=24,reviewer=None):
    annotations=[];degraded=[]
    for start in range(0,len(data['paragraphs']),group_size):
        ps=data['paragraphs'][start:start+group_size];g=start//group_size
        scope=dict(data,paragraphs=ps,group=g,facts=[],context_paragraphs=[],owned_paragraph_ids=[p['paragraph_id'] for p in ps])
        material={k:scope[k] for k in ('book_id','chapter','paragraphs','scope_limits','owned_paragraph_ids')}
        material['read_only_chapter_context']=[p for p in data['paragraphs'] if p['paragraph_id'] not in scope['owned_paragraph_ids']]
        def gate(raw):
            raw=dict(raw,scenes=[])
            return c_gate(raw,scope)
        raw,pending=task(client,model,parameters,ANNOTATE,material,gate,folder,'C_tags'+str(g),receipt,'C',reviewer)
        local=empty_result();c_convert(raw,scope,local,pending)
        for c in local['C']:
            annotations.extend(dict(id=full_pid(p['paragraph_id'],data),main=p['main_tag'],secondary=p['secondary_tag'],viewpoint=p['viewpoint'],quote=p['quote'],note=p.get('note','')) for p in c['paragraphs'])
        if pending:degraded.append('C_tags'+str(g))
    scope=dict(data,group='chapter',facts=[],context_paragraphs=[],owned_paragraph_ids=[p['paragraph_id'] for p in data['paragraphs']])
    material={k:data[k] for k in ('book_id','chapter','paragraphs','scope_limits')}
    def gate(raw):
        raw=dict(raw,paragraphs=annotations)
        obj,errors,log=c_gate(raw,scope)
        errors=[e for e in errors if not str(e.get('path','')).startswith('paragraphs[') and e.get('field')!='段标注']
        return obj,errors,log
    raw,pending=task(client,model,parameters,SCENES,material,gate,folder,'C_scenes',receipt,'C',reviewer)
    raw['paragraphs']=annotations
    doc=empty_result();c_convert(raw,scope,doc,pending)
    if pending:degraded.append('C_scenes')
    return doc,degraded


def run(args):
    source=external(args.source);output=external(args.out);output.mkdir(parents=True,exist_ok=True)
    config=next(c for c in json.loads((OUT/'books_selected.json').read_text()) if c['code']==args.book)
    policy=json.loads(external(args.policy).read_text())[args.model]['parameters']
    receipt=dict(execution_identity='Codex',model=args.model,book=args.book,round=args.round,chapters_requested=8,completed_chapters=[],clean_chapters=[],degraded_chapters=[],rewrites=0,calls=[],partial=False,
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),reused_source=str(source),reused_layers=['A','B'],config=dict(c_group=args.c_group,c_steps=['段标签与感知者','整章现场五格']))
    prior=json.loads((source/'prediction.json').read_text());result=copy.deepcopy(prior);result['C']=[]
    old_receipt=json.loads((source/'run_receipt.json').read_text())
    inherited={d['chapter']:[v for v in d.get('steps',[]) if not v.startswith('C')] for d in old_receipt.get('degraded_chapters',[])}
    receipt['inherited_degraded_steps']=inherited
    receipt['rewrite_scope']='本轮新增C重写；A/B既有重写须回原回执核对'
    # C旧黄标由新C重判；B/A未改，保留其原黄标与出处。
    result['review_audit']['review_flags']=[f for f in prior['review_audit']['review_flags'] if not str(f.get('flag_id','')).startswith('R03:C:')]
    client=Client()
    for n in range(1,9):
        ch=f'{n:02d}';data=read_book(config,ch);folder=output/('ch'+ch);folder.mkdir(exist_ok=True)
        try:
            doc,degraded=run_c(data,client,args.model,policy,folder,receipt,args.c_group)
            result['C'].extend(doc['C']);result['review_audit']['review_flags'].extend(doc['review_audit']['review_flags'])
            receipt['completed_chapters'].append(ch)
            combined=inherited.get(ch,[])+degraded
            if combined:receipt['degraded_chapters'].append(dict(chapter=ch,steps=combined,new_c_steps=degraded))
            else:receipt['clean_chapters'].append(ch)
            dump(folder/'result.json',doc)
            dump(output/'prediction.json',result);dump(output/'run_receipt.json',receipt)
            print('C拆步交付',args.book,ch,'降级步骤',len(degraded),flush=True)
        except Exception as e:receipt['partial']=True;receipt['error']=str(e);break
    dump(output/'prediction.json',result);dump(output/'run_receipt.json',receipt)
    return int(receipt['partial'])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--book',required=True);p.add_argument('--model',choices=MODELS,required=True)
    p.add_argument('--round',type=int,required=True);p.add_argument('--c-group',type=int,default=24);p.add_argument('--policy',default=str(OUT/'probe/reasoning_policy.json'))
    a=p.parse_args()
    if a.book not in ('gongan','dayi','qishi'):p.error('C拆法对照仅开发集')
    return run(a)


if __name__=='__main__':raise SystemExit(main())

# 执行身份：Codex
"""A状态诊断只写数字与编号，复用原评分器的实体对齐，不替代正式分数。"""
from pipeline_common.artifacts import external_path
import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import sys


def diagnose(gold_path, pred_path, bid, zip_path):
    spec = importlib.util.spec_from_file_location('readonly_score', external_path('PR_WORKSPACE_ROOT') / 'bin/score_pipeline.py')
    s = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = s
    spec.loader.exec_module(s)
    ctx = s.load_context(zip_path)
    gd, pd = s.read_json(gold_path), s.read_json(pred_path)
    bids = sorted(set(ctx['book_ids']) | {bid})
    pmap = {h['plan_key']: h['book_id'] for d in (gd,pd) for h in d['review_audit']['plan_history'] if h.get('plan_key') and h.get('book_id')}
    g, _, _ = s.project(gd,bid,bids,ctx['oldmap'],pmap)
    p, _, _ = s.project(pd,bid,bids,ctx['oldmap'],pmap)
    gf = s.effective_facts(g,bid,ctx,[])
    pf = s.effective_facts(p,bid,ctx,[])
    gr, pr = s.fact_index(gf), s.fact_index(pf)
    cfg = s.config_values()
    bp, _, _ = s.alignment(gf,pf,cfg)
    fmap = {x['pred_index']:x['gold_index'] for x in bp}
    ga = s.plan_entities(g,bid,ctx,gr,[])
    pa = s.plan_entities(p,bid,ctx,pr,[])
    pairs, missing, extra = s.alignment(ga,pa,cfg)
    counters = Counter()
    entries = []
    def count(field, equal, ids, ch=None):
        counters[field+'.比较'] += 1
        counters[field+('.相同' if equal else '.差异')] += 1
        if not equal:
            entries.append(dict(gold_id=ids[0],pred_id=ids[1],chapter=ch,field=field))
    for pair in pairs:
        a,b = ga[pair['gold_index']],pa[pair['pred_index']]
        ids=(a['id'],b['id'])
        count('实体主体',a['subject']==b['subject'],ids)
        count('实体正文',a['text']==b['text'],ids)
        count('引入章',a['chapter']==b['chapter'],ids)
        gp=next((r.get('plan') for r in a['rows'] if r.get('plan')), {})
        pp=next((r.get('plan') for r in b['rows'] if r.get('plan')), {})
        for field in ('deadline','condition'):
            count('期限' if field=='deadline' else '条件',gp.get(field)==pp.get(field),ids)
        gs,ps=defaultdict(list),defaultdict(list)
        for state in a['states']:gs[state['chapter']].append(state)
        for state in b['states']:ps[state['chapter']].append(state)
        for ch in sorted(set(gs)|set(ps)):
            aa,bb=gs[ch],ps[ch]
            count('历史拼接重复',len(bb)<=1,ids,ch)
            for index in range(max(len(aa),len(bb))):
                avalue=aa[index] if index<len(aa) else None
                bvalue=bb[index] if index<len(bb) else None
                if avalue is None or bvalue is None:
                    field='历史缺失' if bvalue is None else '历史多记'
                    counters[field] += 1
                    entries.append(dict(gold_id=ids[0],pred_id=ids[1],chapter=ch,state_index=index,field=field))
                    continue
                count('状态',avalue.get('status')==bvalue.get('status'),ids,ch)
                for field in s.REF_FIELDS:
                    count('引用.'+field,s.reference_equal(avalue.get(field),bvalue.get(field),gr,pr,fmap),ids,ch)
                av,bv=avalue.get('change_basis_record_keys') or [],bvalue.get('change_basis_record_keys') or []
                remaining=list(bv)
                for v in av:
                    match=next((j for j,k in enumerate(remaining) if s.reference_equal(v,k,gr,pr,fmap)),None)
                    if match is None:break
                    remaining.pop(match)
                else:
                    count('状态变化依据',not remaining,ids,ch)
                    continue
                count('状态变化依据',False,ids,ch)
    return dict(execution_identity='Codex',gold_entities=len(ga),pred_entities=len(pa),aligned_entities=len(pairs),missing_entities=len(missing),extra_entities=len(extra),
                counters=dict(counters),entries=entries,
                missing_ids=[ga[i]['id'] for i in missing],extra_ids=[pa[i]['id'] for i in extra],
                limitations=['未对齐实体不计状态正确率','期限条件为字段比较，语义等价未测','沿用正式评分器事实对齐，拆合句引用等价仍受限'])


def main():
    p=argparse.ArgumentParser()
    for name in ('gold','pred','bid','input-zip','out'):p.add_argument('--'+name,required=True)
    a=p.parse_args()
    out=Path(a.out).resolve()
    if not out.is_relative_to(external_path('PR_WORKSPACE_ROOT') / 'out/管线修复_R03/a_state_diagnostic'):raise ValueError('诊断输出仅本轮指定目录')
    result=diagnose(a.gold,a.pred,a.bid,a.input_zip)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('entries','missing_ids','extra_ids')},ensure_ascii=False))


if __name__=='__main__':main()

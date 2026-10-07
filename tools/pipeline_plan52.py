# 执行身份：Codex
"""段级计划线索、后续证据配对和发送包；不判断模型语义成绩。"""
import copy
import json
import re
from collections import Counter
from pipeline_context52 import (narration, quotes, person_pool, name_map, mentions, speech_table,
                                memory_marks, resolve_title, WITHDRAW)
from pipeline_records25 import key_for

METHOD = 'seed_followup_packets_v52'
STRONG = re.compile(r'计划|打算|准备|决定|安排|约定|承诺|答应|叮嘱|保证|必须|需要|要求|铁了心|非要|决心|一定要|绝不能|不能让|决不|务必|发誓|决意|下定决心')
INTENT = re.compile(r'想(?=[说去做往要让把给反回看])|(?:刚|正|还|便|又|本)想(?!法|起|到|象|像)')
TIMEQ = re.compile(r'今晚|晚上|明天|后天|下午|中午|待会|到时|下周|下月|马上|立刻|立即|这段时间|这几天|回头|过两天|尽快')
YAODE = re.compile(r'(?:我|咱们|咱|你|他|她|我们|你们|他们|她们)(?:还|也|就|可|一定|得)?(?:要|得)(?!是|不|到)[\u4e00-\u9fff]')
COND = re.compile(r'(?:要是|如果|万一|若是|只要)[^。！？]{0,24}[，,][^。！？]{0,30}(?:就|便|得|要|别想|不准)|否则|不然|不准')
DIRECT = re.compile(r'(?:^|[，,])(?:你|快|赶紧)?去(?![了过])[\u4e00-\u9fff]|把[^，。！？]{1,10}(?:拿来|送来|带走|收[了好]|洗[了好]|装上)|来吧|我来|轮到|不能|不许|不准')
NEG = re.compile(r'心想|想法|想着|觉得|使得|不可多得|只要|变得|干得|挂得|对于.{0,6}来说')
HABIT = re.compile(r'每次|每周|每个月|每年|总会|一直|只要')

def signal(text):
    clean=NEG.sub('',text)
    qs=' '.join(q[1:-1] for q in quotes(clean))
    qs=re.sub(r'(?:昨天|前天|昨|那天|以前)(?:上午|下午|晚上|夜里|中午)?','',qs)
    strong=bool(STRONG.search(clean));direct=bool(DIRECT.search(qs) or re.search(r'让[^，。！？]{1,20}(?:赶紧|尽快)',qs))
    if HABIT.search(text) and not (strong or direct):return False
    return bool(strong or INTENT.search(clean) or re.search(r'开学后|以后再|将要',clean)
                or TIMEQ.search(qs) or YAODE.search(qs) or COND.search(qs) or direct)

def followups(material, seed, marks=(), next_chapter=False):
    """按相关度取基础后续，再覆盖近窗内同一持有人的动作段。"""
    pars=material['paragraphs'];order={p['paragraph_id']:i for i,p in enumerate(pars)}
    ev=seed.get('ev',[]);source=' '.join(e['q'] for e in ev) or seed.get('content','')
    stop=set('这个 那个 一个 自己 他们 她们 什么 怎么 不是 就是 还是 已经 没有 时候 起来 说道 一下 所以 因为 可是 不过 但是 然后'.split())
    pairs=Counter()
    for p in pars:
        pairs.update(set(re.findall(r'(?=([\u4e00-\u9fff]{2}))',p['text'])))
    keys={w for w,n in pairs.items() if 2<=n<=4 and w in source and w not in stop}
    names={seed.get('subject',''),*seed.get('receivers',[])}
    names|={n[1:] for n in list(names) if len(n)>=3}
    names.discard('')
    last=-1 if next_chapter else max((order.get(e['p'],-1) for e in ev),default=-1)
    selected=[];base_selected=[]
    for i,p in enumerate(pars):
        if i<=last or p['paragraph_id'] in marks:continue
        text=p['text'];person=any(n in text for n in names)
        keyhits=keys & set(re.findall(r'(?=([\u4e00-\u9fff]{2}))',text))
        near=not next_chapter and i-last<=3
        dialogue=near and bool(quotes(source)) and bool(quotes(text))
        # 只补已选后续动作的接续句；种子自己的接续不另算一次后续变化。
        continuation = bool(i and re.match(r'^(?:说完|说罢|随后|随即)',text)
                            and any(n in pars[i-1]['text'] for n in names)
                            and any(r[1]==i-1 for r in selected))
        holder_near = (person or continuation) and i-last<=8 and not next_chapter
        if not (keyhits or near and (person or dialogue) or holder_near):continue
        selected.append((3*near+2*person+len(keyhits),i,{'p':p['paragraph_id'],'q':text,
             'flags':['pronoun_risk'] if re.match(r'^(?:他|她)',text) and keyhits and not person else []}))
        if keyhits or near and (person or dialogue):base_selected.append(selected[-1])
    ranked=sorted(base_selected,key=lambda x:(-x[0],x[1]))
    chosen=ranked[:4]
    # 原四条保留；同人近窗段按距离补齐，最多八条，窗口/条数与书内编号无关。
    extra=[r for r in selected if r not in chosen and r[1]-last<=8
           and (any(n in r[2]['q'] for n in names) or re.match(r'^(?:说完|说罢|随后|随即)',r[2]['q']))]
    chosen.extend(sorted(extra,key=lambda x:x[1])[:max(0,8-len(chosen))])
    return [r for _,_,r in chosen]

def plan_candidates(material, facts, entities=None, initial_memory=False):
    entities=entities or {};pars=material['paragraphs'];order={p['paragraph_id']:i for i,p in enumerate(pars)}
    table={p['paragraph_id']:p for p in pars};names=person_pool(material,facts,entities);mapping=name_map(material,names,entities)
    speeches={x['p']:x for x in speech_table(material,facts,entities,names)}
    memory=memory_marks(material,entities,initial_memory)
    seeds=[];pending=[];seen=set()
    for fact in facts:
        if fact.get('book_id')!=material['book_id'] or fact.get('chapter')!=material['chapter']:continue
        for item in fact.get('evidence',[]):
            pid=item.get('paragraph_id','').rsplit(':',1)[-1]
            if pid not in table or not item.get('quote') or item['quote'] not in table[pid]['text']:continue
            p=table[pid];text=p['text']
            if not signal(text):continue
            subject=fact.get('subject');holder=subject;backfill=None
            if subject in ('未知','无名','无名说话人',None,''):
                candidates=speeches[pid]['speaker']
                j2=[r.get('speaker') for field in entities.values() if isinstance(field,list) for r in field if isinstance(r,dict)
                    and r.get('speaker') and any(e.get('p')==pid for e in r.get('ev',[]))]
                if len(set(j2))==1:holder=j2[0];backfill='J2'
                elif len(candidates)==1 and any(e['method'] in ('直接署名','引语后署名','B上下文候选') for e in speeches[pid]['evidence']):holder=candidates[0];backfill='上下文候选'
                else:holder='待核'
            else:
                result=resolve_title(subject,material,names,entities,pid)
                holder=result['referent'] or subject
            intent=INTENT.search(narration(text))
            if intent:
                close=[h for h in mentions(narration(text),mapping) if h[1]<=intent.start() and intent.start()-h[1]<=3]
                if close:holder=close[-1][2]
            sig=(pid,holder)
            if sig in seen:continue
            seen.add(sig)
            qs=' '.join(q[1:-1] for q in quotes(text));receivers=set()
            if DIRECT.search(qs) or COND.search(qs):
                receivers.update(speeches[pid]['recipients'])
                for hit in mentions(text,mapping):
                    if re.search(r'(?:轮到|推了把|冲着|对着|看向|朝|向|让)$',text[max(0,hit[0]-4):hit[0]]):receivers.add(hit[2])
                if not receivers:
                    others={h[2] for h in mentions(narration(text),mapping)}-{holder}
                    if len(others)==1:receivers|=others
                    elif order[pid]>0:receivers.update(speeches[pars[order[pid]-1]['paragraph_id']]['speaker'])
            receivers.discard(holder)
            ev=[{'p':pid,'q':text}]
            row={'seed_id':'seed:'+key_for(fact['local_key'],pid,holder),'subject':holder,
                 'source':fact['local_key'],'basis':[fact['local_key']],'ev':ev,
                 'receivers':sorted(receivers),'flags':[],'backfill':backfill,
                 'input_method':METHOD}
            row['holder_candidates']=sorted({holder,*receivers}-{'待核'})
            row['followups']=followups(material,row,memory['paragraph_ids'])
            quoted_signal=bool(STRONG.search(qs) or TIMEQ.search(qs) or YAODE.search(qs) or COND.search(qs) or DIRECT.search(qs))
            nearby=''.join(x['text'] for x in pars[order[pid]:order[pid]+4])
            thought=bool((intent or re.search('准备',narration(text))) and not quoted_signal and WITHDRAW.search(nearby))
            reason=('回忆旧事' if pid in memory['paragraph_ids'] else '念头·CZ0316' if thought else '持有人待核' if holder=='待核' else None)
            if reason:
                row['flags'].append(reason);row['send']=False;pending.append(row)
            else:
                row['send']=True;seeds.append(row)
    # 同人相邻种子合并；不把整条事实的跨段证据一起塞入。
    merged=[]
    for s in sorted(seeds,key=lambda s:order[s['ev'][0]['p']]):
        target=next((x for x in reversed(merged) if x['subject']==s['subject']
                     and order[s['ev'][0]['p']]-max(order[e['p']] for e in x['ev'])<=2),None)
        if target:
            target['ev'].extend(e for e in s['ev'] if e not in target['ev']);target['basis']=list(dict.fromkeys(target['basis']+s['basis']))
            target['receivers']=sorted(set(target['receivers']+s['receivers']))
            target['holder_candidates']=sorted(set(target['holder_candidates']+s['holder_candidates']))
            target['followups']=followups(material,target,memory['paragraph_ids'])
        else:merged.append(s)
    return {'seeds':merged,'pending':pending,'memory':memory,'names':names,'speeches':speeches}

def carry_plans(material, previous, memory):
    rows=[];latest={p['key']:p for p in previous}
    for plan in latest.values():
        row=copy.deepcopy(plan)
        if row.get('status') not in ('未执行','执行中'):
            row['followups']=[];row['flags']=['closed_history'];rows.append(row);continue
        seed={**row,'ev':[]}
        row['followups']=followups(material,seed,memory,next_chapter=True)
        row['flags']=[] if row['followups'] else ['carried_no_evidence']
        rows.append(row)
    return rows

def packets(material,payload,review=False):
    from pipeline_output28 import pointer_payload,size,OutputOverflow
    seeds=payload.get('plan_seeds',[]);old=payload.get('previous_plans',[])
    def build(group,previous,rows=None):
        support=[e for s in group for e in s['ev']+s.get('followups',[])]+[e for r in previous for e in r.get('followups',[])]
        allowed={e['p'] for e in support};local=dict(material,paragraphs=[p for p in material['paragraphs'] if p['paragraph_id'] in allowed])
        refs={k for s in group for k in s['basis']}
        refs|={r.get(k) for r in previous for k in ('source','fulfilled','condition_ref')}
        # 后续变化也可连接本章事实编号，不携带无关正文。
        facts=[f for f in payload.get('facts',[]) if f[0] in refs or any(pid.rsplit(':',1)[-1] in allowed for pid in f[3])]
        data={'input_method':METHOD,'paragraphs':pointer_payload(local) if review else [[p['paragraph_id'],p['text']] for p in local['paragraphs']],
              'plan_seeds':group,'previous_plans':previous,'facts':facts,'fact_fields':['key','subject','text','paragraph_ids'],
              'group_subjects':sorted({s['subject'] for s in group}|{n for s in group for n in s.get('receivers',[])}|{r['subject'] for r in previous})}
        if rows is not None:data.update(rows=rows,role='A',input_bound=payload.get('input_bound',24000))
        return material,data
    if review:return [build(seeds,old,payload['rows'])]
    groups=[[],[]]
    by_person={}
    for s in seeds:by_person.setdefault(s['subject'],[]).append(s)
    for group in sorted(by_person.values(),key=lambda g:-size(g)):
        available=[i for i,g in enumerate(groups) if len(g)+len(group)+(len(old) if i==0 else 0)<=8]
        if not available:raise OutputOverflow('A两包的每包8条上限不足，保留候选待核')
        i=min(available,key=lambda i:size(groups[i])+ (size(old) if i==0 else 0));groups[i].extend(group)
    result=[build(g,old if i==0 else []) for i,g in enumerate(groups) if g or i==0 and old]
    if len(result)>2 or any(len(d['plan_seeds'])+len(d['previous_plans'])>8 for _,d in result):
        raise OutputOverflow('A两包无法装入当前候选，停止并保留材料')
    from pipeline_prompts25 import SYSTEM,PROMPTS
    from pipeline_records25 import protocol_payload57
    for _,data in result:
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':PROMPTS['A']+'\n'+json.dumps(protocol_payload57('A', wire_payload(data), material),ensure_ascii=False,separators=(',',':'))}]
        if len(json.dumps(messages,ensure_ascii=False).encode())>8192:
            raise OutputOverflow('A生成包超过8KB，完整种子候选保留，不发送')
    return result


def wire_payload(payload):
    """原段只放在段落表一次，候选保留段号；本地校验仍用完整候选。"""
    data=copy.deepcopy(payload)
    for seed in data.get('plan_seeds',[]):
        for key in ('input_method','send','backfill','holder_candidates'):seed.pop(key,None)
        for field in ('ev','followups'):
            seed[field]=[{k:v for k,v in e.items() if k!='q'} for e in seed.get(field,[])]
    for old in data.get('previous_plans',[]):
        old['followups']=[{k:v for k,v in e.items() if k!='q'} for e in old.get('followups',[])]
    return data


def split_seed_packet(material,payload,review=False):
    from pipeline_output28 import OutputOverflow
    field='rows' if review else 'plan_seeds';units=payload.get(field,[])
    if len(units)<2:raise OutputOverflow('A单条包不能拆半')
    middle=len(units)//2;result=[]
    for i,half in enumerate((units[:middle],units[middle:])):
        data=copy.deepcopy(payload);data[field]=half
        if review:
            wanted={r.get('source') for r in half};data['plan_seeds']=[s for s in payload.get('plan_seeds',[]) if s['source'] in wanted]
            if not data['plan_seeds']:data['plan_seeds']=payload.get('plan_seeds',[])  # 无来源时不猜对应关系
        else:data['previous_plans']=payload.get('previous_plans',[]) if i==0 else []
        allowed={e['p'] for s in data['plan_seeds'] for e in s['ev']+s.get('followups',[])}
        allowed|={e['p'] for r in data.get('previous_plans',[]) for e in r.get('followups',[])}
        data['paragraphs']=[p for p in payload['paragraphs'] if p[0] in allowed]
        data['facts']=[f for f in payload.get('facts',[]) if any(p.rsplit(':',1)[-1] in allowed for p in f[3])]
        result.append((material,data))
    return result

def check_local_plans(value, packet, previous):
    seeds=packet.get('plan_seeds',[]);old={p['key']:p for p in previous}
    allowed={e['p'] for s in seeds for e in s['ev']+s.get('followups',[])}
    allowed|={e['p'] for r in packet.get('previous_plans',[]) for e in r.get('followups',[])}
    holders={s['subject'] for s in seeds}|{n for s in seeds for n in s.get('receivers',[])}
    for row in value['rows']:
        if row.get('key') in old:
            prior=old[row['key']];carry=next((r for r in packet.get('previous_plans',[]) if r['key']==row['key']),{})
            if prior.get('status') in ('落空','放弃') and row.get('status') in ('未执行','执行中'):raise ValueError('撤回或落空的旧计划不得恢复为现行')
            if not carry.get('followups') and row.get('status')!=prior.get('status'):raise ValueError('无本章后续证据，不得改旧计划状态')
            if carry.get('followups') and not row.get('ev'):raise ValueError('旧计划有后续，必须引用本章新证据核状态')
        elif row.get('subject') not in holders:raise ValueError('计划持有人不在本包候选')
        if any(e['p'] not in allowed for e in row.get('ev',[])):raise ValueError('计划证据不在本包种子或后续')
    return value

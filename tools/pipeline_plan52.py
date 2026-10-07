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

def scheduled_clause(text):
    """时间须和同一分句的未发生动作配对；主语可以省略。"""
    time=TIMEQ.search(text) or re.search(r'[^，,。！？；;]{1,12}(?:之后|以后|后)',text)
    if not time:return False
    tail=text[time.end():]
    if re.search(r'已经|已然|早已|刚刚|刚才|曾经|过了',tail):return False
    action=re.search(r'(?:去|来|做|回|带|拿|送|上|下|交|买|卖|吃|喝|炒|洗|写|读|取|还|见|开)(?!了|过|着)',tail)
    return bool(action and not re.search(r'(?:了|过)[。！!]?$',tail))

def own_arrangement(text):
    """同段给他人的指令不遮住持有人自己的另一条安排。"""
    for clause in re.split(r'[，,。！？；;]',text):
        if re.search(r'我(?:们)?(?:来|要|得|会|打算|准备)',clause):return True
        if scheduled_clause(clause) and not re.search(r'你(?:们)?|让|叫',clause):return True
    return False

def signal(text):
    clean=NEG.sub('',text)
    qs=' '.join(q[1:-1] for q in quotes(clean))
    qs='，'.join(c for c in re.split(r'[，,。！？；;]',qs)
                if not re.search(r'昨天|前天|昨晚|那天|以前',c))
    strong=bool(STRONG.search(clean));direct=bool(DIRECT.search(qs) or re.search(r'让[^，。！？]{1,20}(?:赶紧|尽快)',qs))
    if HABIT.search(text) and not (strong or direct):return False
    # 时间只定位计划，不能自己生成计划；已发生动作也不由时间词重新立项。
    scheduled=any(scheduled_clause(c) for c in re.split(r'[，,。！？；;]',qs))
    # 叙述中的时间定位不能把刚发生的动作变成新计划；日期后的安排另核动作。
    scheduled=scheduled or any(re.search(r'[零一二三四五六七八九十百0-9]{1,4}[年月日周]',c)
                              and re.search(r'之后|以后|后',c) and scheduled_clause(c)
                              for c in re.split(r'[，,。！？；;]',narration(clean)))
    scheduled=scheduled or any(re.search(r'明天|后天|下周|下月|下个|还要|还得|将要',c) and scheduled_clause(c)
                              for c in re.split(r'[，,。！？；;]',narration(clean)))
    return bool(strong or INTENT.search(clean) or re.search(r'以后再|将要',clean)
                or scheduled or YAODE.search(qs) or COND.search(qs) or direct)

def followups(material, seed, marks=(), next_chapter=False, max_chars=2400):
    """后续按距离取到章末、字符帽或首个场景分隔行；不依赖段号写法。"""
    from pipeline_c_program25 import separator
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
    selected=[];used=0
    for i,p in enumerate(pars):
        if i<=last:continue
        if separator(p['text']):break
        if p['paragraph_id'] in marks:continue
        text=p['text'];person=any(n in text for n in names)
        keyhits=keys & set(re.findall(r'(?=([\u4e00-\u9fff]{2}))',text))
        near=not next_chapter and i-last<=3
        dialogue=near and bool(quotes(source)) and bool(quotes(text))
        # 只补已选后续动作的接续句；种子自己的接续不另算一次后续变化。
        continuation = bool(i and re.match(r'^(?:说完|说罢|随后|随即)',text)
                            and any(n in pars[i-1]['text'] for n in names)
                            and any(r[1]==i-1 for r in selected))
        if not (person or continuation or keyhits or near and dialogue):continue
        if used+len(text)>max_chars:break
        selected.append((0,i,{'p':p['paragraph_id'],'q':text,
             'flags':['pronoun_risk'] if re.match(r'^(?:他|她)',text) and keyhits and not person else []}))
        used+=len(text)
    return [r for _,_,r in selected]

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
            directive_signal=bool(DIRECT.search(qs) or any(scheduled_clause(c) and re.search(r'你(?:们)?(?=(?:明天|后天|下午|晚上|去|来|要|得|把))',c)
                                                        for c in re.split(r'[，,。！？；;]',qs)))
            if directive_signal or COND.search(qs):
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
            row['condition_evidence']=[{'p':pid,'q':m[0]} for m in COND.finditer(text)]
            # 指令可以是受话人的安排线索，但发令者不能把他人的动作记成自己的计划。
            directive=bool(receivers and directive_signal and not own_arrangement(qs))
            row['plan_holders']=sorted(receivers if directive else {holder,*receivers})
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
            target['plan_holders']=sorted(set(target['plan_holders']+s['plan_holders']))
            target['condition_evidence'].extend(e for e in s['condition_evidence'] if e not in target['condition_evidence'])
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
    def bounded_build(group,previous,rows=None):
        from pipeline_prompts25 import SYSTEM,PROMPTS,REVIEW_PROMPT
        from pipeline_records25 import protocol_payload57
        group=copy.deepcopy(group);previous=copy.deepcopy(previous)
        order={p['paragraph_id']:i for i,p in enumerate(material['paragraphs'])}
        trimmed=[]
        while True:
            mat,data=build(group,previous,rows)
            messages=[{'role':'system','content':SYSTEM},{'role':'user','content':(REVIEW_PROMPT if review else PROMPTS['A'])+'\n'+json.dumps(protocol_payload57('A',wire_payload(data),material,review),ensure_ascii=False,separators=(',',':'))}]
            if len(json.dumps(messages,ensure_ascii=False).encode())<=8192:
                data['_packet_trimmed_followups']=trimmed
                return mat,data
            protected={e['p'] for s in group for e in s['ev']}
            protected|={e['p'] for row in rows or [] for e in row.get('ev',[])}
            protected|={p for row in rows or [] for field in ('state_paragraphs','condition_paragraphs') for p in row.get(field,[])}
            choices=[]
            for s in group+previous:
                origin=max((order.get(e['p'],-1) for e in s.get('ev',[])),default=-1)
                holders={s.get('subject',''),*s.get('plan_holders',[])}-{''}
                for e in s.get('followups',[]):
                    # 同持有人动作、已完成标记及模型已引用的段都保守视为兑现候选。
                    if any(n in e.get('q','') for n in holders) or re.search(r'完成|办成|做完|兑现|已经|终于|交了|送到|拿到',e.get('q','')):
                        protected.add(e['p'])
                    choices.append((order.get(e['p'],-1)-origin,e['p']))
            available=[x for x in choices if x[1] not in protected]
            if not available:raise OutputOverflow('A包超过8KB；种子或兑现候选不能剪，保留完整候选待核')
            _,pid=max(available)
            for s in group+previous:s['followups']=[e for e in s.get('followups',[]) if e['p']!=pid]
            trimmed.append(pid)
    if review:
        def review_group(rows):
            sources={r.get('source') for r in rows if r.get('key') is None}
            keys={r.get('key') for r in rows if r.get('key') is not None}
            selected=[s for s in seeds if s['source'] in sources]
            previous=[p for p in old if p['key'] in keys]
            if sources-{s['source'] for s in selected} or keys-{p['key'] for p in previous}:
                raise OutputOverflow('A复核行没有对应完整种子或旧计划，保留待核')
            return bounded_build(selected,previous,rows)
        result=[];group=[]
        for row in payload['rows']:
            try:review_group(group+[row])
            except OutputOverflow:
                if not group:raise
                result.append(review_group(group));group=[]
                review_group([row])
            group.append(row)
        if group:result.append(review_group(group))
        # 包数不代替预算授权；每一包仍走原岗位、共享池及总预算守卫。
        return result
    groups=[[],[]]
    by_person={}
    for s in seeds:by_person.setdefault(s['subject'],[]).append(s)
    for group in sorted(by_person.values(),key=lambda g:-size(g)):
        available=[i for i,g in enumerate(groups) if len(g)+len(group)+(len(old) if i==0 else 0)<=8]
        if not available:raise OutputOverflow('A两包的每包8条上限不足，保留候选待核')
        i=min(available,key=lambda i:size(groups[i])+ (size(old) if i==0 else 0));groups[i].extend(group)
    result=[bounded_build(g,old if i==0 else []) for i,g in enumerate(groups) if g or i==0 and old]
    if len(result)>2 or any(len(d['plan_seeds'])+len(d['previous_plans'])>8 for _,d in result):
        raise OutputOverflow('A两包无法装入当前候选，停止并保留材料')
    return result


def wire_payload(payload):
    """原段只放在段落表一次，候选保留段号；本地校验仍用完整候选。"""
    data=copy.deepcopy(payload)
    data.pop('_packet_trimmed_followups',None)
    for seed in data.get('plan_seeds',[]):
        for key in ('input_method','send','backfill','holder_candidates'):seed.pop(key,None)
        for field in ('ev','followups'):
            seed[field]=[{k:v for k,v in e.items() if k!='q'} for e in seed.get(field,[])]
    for old in data.get('previous_plans',[]):
        old['followups']=[{k:v for k,v in e.items() if k!='q'} for e in old.get('followups',[])]
    if data.get('rows') is not None:
        # 复核沿用已提供的句号表，证据正文只存一份；本地原行不改。
        table={p:parts for p,parts in data.get('paragraphs',[]) if isinstance(parts,list)}
        for row in data['rows']:
            for key in list(row):
                if key.startswith('_') and key!='_id':row.pop(key)
            ev=[]
            for e in row.get('ev',[]):
                pointers=[{'p':e['p'],'s':n} for n,t in table.get(e['p'],[]) if e.get('q') and (e['q'] in t or t.strip() and t in e['q'])]
                ev.extend(pointers or [e])
            row['ev']=ev
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


def check_state_structure(row, material, facts, previous=()):
    """复核指出依据，程序只核可定位结构；不过只影响该行。"""
    table={p['paragraph_id']:p['text'] for p in material['paragraphs']}
    order={p:i for i,p in enumerate(table)}
    by_key={f['local_key']:f for f in facts}
    source=by_key.get(row.get('source'),{})
    def pids(f):return {e['paragraph_id'].rsplit(':',1)[-1] for e in f.get('evidence',[]) if e.get('paragraph_id')}
    origin=set(row.get('_seed_paragraphs',[])) or pids(source)
    source_text=' '.join(table[p] for p in origin if p in table)
    if row.get('key') is None and source_text and not signal(source_text):
        raise ValueError('种子只有时间或已发生动作，没有计划意图')
    condition=[m[0] for m in COND.finditer(source_text)]
    if condition:row['condition']='；'.join(dict.fromkeys(condition))
    prior=next((p for p in previous if p['key']==row.get('key')),None)
    if prior and all(row.get(k)==prior.get(k) for k in ('status','subject','content','source','condition')) and not row.get('ev'):
        return row
    def evidence_paras(field):
        ps=row.get(field,[])
        if not isinstance(ps,list) or any(not isinstance(p,str) or p not in table for p in ps):raise ValueError('状态依据段号无效：'+field)
        return set(ps)
    state=evidence_paras('state_paragraphs');cond=evidence_paras('condition_paragraphs')
    boundary=max((order[p] for p in origin if p in order),default=-1)
    def after_source(ps):return bool(ps) and not (ps & origin) and all(order[p]>boundary for p in ps)
    if condition and row['status']!='未执行':
        cf=by_key.get(row.get('condition_ref'),{})
        if (not after_source(cond) or not cond<=pids(cf) or row.get('condition_ref')==row.get('source')
                or any(COND.search(table[p]) for p in cond)):
            raise ValueError('条件未见成立依据，只许未执行')
    if row['status'] not in ('兑现','落空'):return row
    if not state:raise ValueError('复核未指出兑现或落空依据段')
    if row.get('fulfilled')==row.get('source') or state & origin:raise ValueError('状态依据是种子自身来源，不能自证')
    if not after_source(state):raise ValueError('状态依据须在种子之后')
    keys=[row.get('fulfilled')] if row['status']=='兑现' else row.get('basis',[])
    supports=[by_key[k] for k in keys if k in by_key and k!=row.get('source')]
    if not state<=set().union(*(pids(f) for f in supports)):raise ValueError('状态段未连接已给事实')
    if row['status']=='兑现' and not any(f.get('subject')==row['subject'] and state<=pids(f) for f in supports):
        raise ValueError('兑现事实主体与持有人不一致')
    return row

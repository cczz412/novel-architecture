# 执行身份：Codex
"""不同模型只判点名条目；重写仍由原生成模型承担并共享一次上限。"""
import json
from pr_layers_v2_r03 import parse, prompt, task as generate_task, dump

JUDGE = '''你是不同模型的独立复核岗，只判不改。只用输入原文和有效事实，不借已知故事。
逐个检查review_ids指定的条目；每个编号恰好返回一次。输出 {"reviews":[{"id":指定编号,"decision":"通过/明确错误/不确定","field":具体字段,"reason":本条具体依据,"p":原段号或null,"q":逐字短引或null}]}。
重点检查：计划是否为主体将做的可执行行动；回述、被拒、愿望、内层故事不能误立；窄目标与实际履约主体一致；状态变动有本章事实；已开始的一次性动作离场、期限过、前提排除时才按规则收尾；主动收回是放弃；假设回答只有条件可发生且认真才成立；期限和条件分栏；引用指向对应事实。
只说明明确哪处不合，不返回改写后的计划、状态或事实。拿不准写具体疑点，不把看到格式合格当语义通过。'''


def review_ids(obj):
    if 'updates' in obj:return ['updates['+str(i)+']' for i in range(len(obj['updates']))]
    return ['plans['+str(i)+']' for i in range(len(obj.get('plans',[])))]+['old_rows['+str(i)+']' for i in range(len(obj.get('old_rows',[])))]


def judge(client,model,parameters,schema,material,candidate,folder,label,receipt):
    ids=review_ids(candidate)
    if not ids:return []
    messages=prompt(JUDGE,dict(rule_schema=schema,materials=material,candidate=candidate,review_ids=ids))
    current=messages;errors=[];last=[]
    for attempt in range(2):
        response=client.call(model,current,parameters,max_tokens=16000)
        dump(folder/(label+f'_judge_response_{attempt}.json'),response)
        receipt['calls'].append(dict(layer='A复核',model=model,attempt=attempt,independent=True,usage=response.get('usage',{})))
        try:
            obj=parse(response);rows=obj['reviews']
            if not isinstance(rows,list) or any(not isinstance(r,dict) or r.get('decision') not in ('通过','明确错误','不确定') or not isinstance(r.get('reason'),str) for r in rows):raise ValueError('复核须逐条合法决定和具体理由')
            seen=[r.get('id') for r in rows]
            if set(seen)!=set(ids) or len(seen)!=len(set(seen)):raise ValueError('复核编号缺失/越界/重复：'+json.dumps(dict(missing=sorted(set(ids)-set(seen)),extra=sorted(str(x) for x in set(seen)-set(ids))),ensure_ascii=False))
            source={p['paragraph_id']:p['text'] for p in material['paragraphs']}
            for r in rows:
                if r['decision']=='明确错误':
                    p=r.get('p');q=r.get('q')
                    if isinstance(p,str) and p.startswith('p'):p=material['book_id']+':ch'+material['chapter']+':'+p
                    if p not in source or not isinstance(q,str) or not q or q not in source[p]:r['decision']='不确定';r['reason']='独立复核指出疑点，但逐字原段依据未通过'
            last=rows;break
        except (ValueError,KeyError,TypeError,AttributeError) as e:
            errors.append(str(e))
            if attempt==1:last=[dict(id=k,decision='不确定',field='独立复核结构',reason='独立复核一次格式重写仍未通过') for k in ids];break
            current=messages+[dict(role='assistant',content=response['choices'][0]['message'].get('content') or '{}'),dict(role='user',content='只修复核结构错误：'+str(e)+'。逐个编号返回，不改候选内容。')]
    dump(folder/(label+'_judge_summary.json'),dict(execution_identity='Codex',model=model,independent=True,format_errors=errors,decisions=[dict(id=r['id'],decision=r['decision'],field=r.get('field')) for r in last]))
    return last


def task_judged(client,model,policy,schema,material,gate,folder,label,receipt,layer,reviewer=None):
    candidate,pending=generate_task(client,model,policy,schema,material,gate,folder,label,receipt,layer,None)
    if layer!='A' or not reviewer or reviewer[0]==model or pending:return candidate,pending
    reviews=judge(client,reviewer[0],reviewer[1],schema,material,candidate,folder,label,receipt)
    issues=[r for r in reviews if r['decision']!='通过']
    task_info=json.loads((folder/(label+'_task.json')).read_text())
    if any(r['decision']=='明确错误' for r in issues) and task_info['rewrites']==0:
        response=client.call(model,prompt(schema,material)+[dict(role='assistant',content=json.dumps(candidate,ensure_ascii=False)),dict(role='user',content='不同模型逐条判出的明确问题：'+json.dumps(issues,ensure_ascii=False)+'。只修有原文依据的这些问题，其他正确项保持；输出本步骤完整对象。生成重写上限只剩这一次。')],policy,max_tokens=16000)
        dump(folder/(label+'_independent_rewrite_response.json'),response)
        receipt['calls'].append(dict(layer='A',model=model,attempt=1,independent_feedback=True,usage=response.get('usage',{})));receipt['rewrites']+=1
        try:
            revised,err,log=gate(parse(response));dump(folder/(label+'_independent_rewrite_gate.json'),dict(errors=err,conversions=log))
            if not err:
                candidate=revised
                reviews=judge(client,reviewer[0],reviewer[1],schema,material,candidate,folder,label+'_after',receipt)
                issues=[r for r in reviews if r['decision']!='通过']
            else:pending.extend(err)
        except (ValueError,TypeError,KeyError,AttributeError) as e:pending.append(dict(error='独立判断回传后的重写结构失败：'+str(e)))
    pending.extend(dict(path=r['id'],field=r.get('field'),error=r['reason'],independent=True,decision=r['decision']) for r in issues)
    dump(folder/(label+'_independent_pending.json'),dict(execution_identity='Codex',generator=model,reviewer=reviewer[0],pending=pending,shared_generation_rewrite_limit=1))
    return candidate,pending

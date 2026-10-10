# 执行身份：Codex
"""每组格式、逐字引用各最多重写一次；仍有疑问保留候选并标黄。"""
import json
from pr_ark_client_r02 import Client
from pr_compact_bc_r02 import messages, decode, convert
from pr_evidence_guard_r02 import inspect
from pr_pipeline_r02 import dump


def execute(data, output, request, usage_sink=None):
    part = 'g' + str(data['group'])
    original = messages(data)
    current = original
    usages, attempts = [], []
    limits = dict(format=0, quote=0)
    response_kind = 'original'
    best = None
    pending = []
    initial_signature = None
    for _ in range(3):
        response = request(current)
        if usage_sink is not None:
            usage_sink(response.get('usage', {}))
        name = part + ('_response.json' if response_kind=='original' else '_'+response_kind+'_repair_response.json')
        dump(output/name,response)
        usages.append(response.get('usage',{}))
        content = response.get('choices',[{}])[0].get('message',{}).get('content') or ''
        try:
            candidate, structural_pending = convert(decode(response),data)
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            attempts.append(dict(kind=response_kind,format_error=str(exc)))
            if limits['format']:
                if best is None:
                    dump(output/(part+'_checks.json'),dict(execution_identity='Codex',attempts=attempts,limits=limits,no_progress=True))
                    raise ValueError('格式一次重写仍不能装配，停止该组：'+str(exc)) from None
                break
            limits['format']=1
            response_kind='format'
            current=original+([dict(role='assistant',content=content)] if content else [])+[
                dict(role='user',content='具体结构错误：'+str(exc)+'。只重写本步骤完整七数组，保留正确正文。所有场景段号只能属于owned_paragraph_ids。')]
            continue
        errors = inspect(candidate,data)
        signature = sorted((e['item'],e['type'],e.get('paragraph_id')) for e in errors)
        if initial_signature is None:
            initial_signature=signature
        attempts.append(dict(kind=response_kind,quote_error_count=len(errors),structural_pending_count=len(structural_pending)))
        best, pending = candidate, errors
        if not errors or limits['quote']:
            break
        limits['quote']=1
        response_kind='quote'
        current=original+[dict(role='assistant',content=content),dict(role='user',content=
            '逐字引用检查发现以下明确错误：'+json.dumps(errors,ensure_ascii=False,separators=(',',':'))+
            '。请对照这些段重写完整七数组；引文须连续逐字含标点，直引不逐字可改转述但不得丢原意。只修这些引用，不改其他正确正文、分类与旧键去向。')]
    if best is None:
        raise ValueError('限定次数内没有可装配候选，停止该组')
    for i,error in enumerate(pending):
        best['review_audit']['review_flags'].append(dict(flag_id=f'PR:quote:{data["book_id"]}:{data["chapter"]}:{part}:{i}',
            book_id=data['book_id'],chapter=data['chapter'],category='逐字引用待复核',fact_keys=[error['item']] if not error['item'].startswith('PR:scene:') else [],
            plan_keys=[],paragraph_ids=[error['paragraph_id']] if error.get('paragraph_id') else [],
            reason=error['type'],conservative_text=None,original_gap_keys=[]))
    final_signature=sorted((e['item'],e['type'],e.get('paragraph_id')) for e in pending)
    dump(output/(part+'_checks.json'),dict(execution_identity='Codex',attempts=attempts,limits=limits,
        pending_errors=pending,no_progress=bool(pending) and initial_signature==final_signature))
    dump(output/(part+'_result.json'),best)
    return best,usages


def bc_call(data,policy,model,output,guard,usage_sink=None):
    return execute(data,output,lambda current:Client().call(model,current,policy['parameters'],max_tokens=12000),usage_sink=usage_sink)

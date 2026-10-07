#!/usr/bin/env python3
# 执行身份：Codex
"""Five-argument source-only pipeline with resumable, bounded role stages."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
from pipeline_source25 import chapter_range, digest, read_json, read_sources, write_json
from pipeline_prompts25 import SYSTEM, PROMPTS, REVIEW_PROMPT, J2_SHORT_PROMPT, J2_ITEM_PROMPT
from pipeline_budget25 import Budget, Halt, NetworkPause, RoleLimit, TotalLimit, TruncatedOutput, parse_response, blind_admission, complete_truncated_rows
from pipeline_output28 import (PROTOCOL, OUTPUT_POLICY, REPAIR_MAX_BYTES, J2_SHORT_REPAIR_MAX_BYTES, OutputOverflow, J2RowOverflow,
    bounded_packets, split_packet, split_j2_rows, merge_values, hydrate_j2, check_review_shape, pointer_payload, repair_message,
    a_grouped_packets, j2_decision_packets, a_local_packets, A_LOCAL_METHOD)
from pipeline_records25 import (validate, flatten, review_apply, facts_output, plans_output, assemble,
    speaker_candidates, normalize_rejected_patches, normalize_speaker_claims, plan_seeds, check_plan_seed_scope,
    bind_plan_seeds, j2_program_candidates, j2_prepare_packet, j2_pre_dispatch, j2_short_decisions, j2_apply_short,
    j2_wire_payload, j2_revision_step, J2_V50, j2_prepare_packet_v50, j2_partition_saved, j2_enrich_candidates)
from pipeline_author25 import build_views, query
from pipeline_audit25 import local_closure, structural_checks
from pipeline_c_program25 import annotate
from pipeline_context52 import entity_bindings
from pipeline_records25 import j2_save_partition
from pipeline_plan52 import plan_candidates, carry_plans, packets as plan_packets52, check_local_plans, METHOD as A_METHOD52, wire_payload, split_seed_packet

from pipeline_records25 import (protocol_payload57, generation_normalize57, normalize_review57,
                                review_apply57)

ROOT = Path(__file__).resolve().parent
CODE_FILES = tuple(ROOT / name for name in ('run_pipeline.py', 'pipeline_source25.py',
    'pipeline_prompts25.py', 'pipeline_budget25.py', 'pipeline_records25.py', 'pipeline_author25.py', 'pipeline_audit25.py', 'pipeline_c_program25.py', 'pipeline_output28.py', 'pipeline_context52.py', 'pipeline_plan52.py'))
PROMPT_FILES = (ROOT / 'pipeline_prompts25.py',)
CONFIG_FILES = (ROOT / 'pipeline_terms25.json', ROOT / 'pipeline_background25.json')


def messages(instruction, payload):
    return [{'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': instruction + '\n' +
             json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}]


def fact_map(rows):
    return [[r['local_key'], r.get('subject'), r['text'],
             sorted({e['paragraph_id'] for e in r['evidence']})] for r in rows]


def plan_summary(rows):
    latest = {r['key']: r for r in rows}
    fields = ('key', 'subject', 'content', 'status', 'deadline', 'condition', 'source', 'fulfilled', 'condition_ref')
    return [{k: r.get(k) for k in fields} for r in latest.values()]


def clean_checkpoint(state, calls, gateway_job_id):
    removed = []
    for name, stage in state['stages'].items():
        index = stage.get('request_index')
        if index is None:
            continue
        event = next((r for r in calls if r['index'] == index), None)
        if event is None:
            stage.pop('request_index')
            removed.append({'stage': name, 'unsubmitted_index': index})
            continue
        if event.get('stage_id') != name or event.get('gateway_job_id') != gateway_job_id:
            raise Halt('检查点请求归属不符，不能借用其他岗位或旧窗响应')
    state['unsubmitted_request_indexes_cleared'] = removed
    return removed


def run_stage(budget, state, state_path, role, material, payload, review=False, checker=None,
              suffix='', split_depth=0):
    name = role + ':' + material['chapter'] + (':review' if review else ':generate') + suffix
    short_j2 = role == 'J2' and payload.get('method') in ('program_candidates_short_decisions_v47', J2_V50)
    base = messages(J2_ITEM_PROMPT if short_j2 and payload.get('method') == J2_V50 else J2_SHORT_PROMPT if short_j2 else REVIEW_PROMPT if review else PROMPTS[role],
                    j2_wire_payload(payload, material) if short_j2 else protocol_payload57(role,
                        wire_payload(payload) if payload.get('input_method')==A_METHOD52 else payload, material, review))
    stage = state['stages'].setdefault(name, {'attempts': 0, 'status': 'pending'})
    cache = budget.output / 'stages' / (name.replace(':', '_') + '.json')
    if stage.get('local_row_split_failed'):
        raise ValueError(stage.get('machine_error', 'J2本地条目拆包已失败，不追加请求'))
    if stage['status'] in ('complete','partial_truncation'):
        if digest(cache) != stage['sha256']:
            raise Halt('同次结果检查点改变')
        cached = read_json(cache)['payload']
        if short_j2:
            j2_pre_dispatch(payload, material)
            if not cached.get('_normalized57'): raise Halt('旧裁定缓存需要独立离线归一')
        if role == 'A':
            try:
                if review and not any(v.get('accept') for v in cached.get('verdicts', [])):
                    raise ValueError('缓存复核没有可保存计划，A阶段未完成')
                if not review:
                    if not cached.get('rows'):
                        raise ValueError('缓存计划候选为空，A阶段未完成')
                    if checker and '_normalization_log' not in cached:
                        checker(cached, material, payload)
            except (ValueError, KeyError, TypeError) as exc:
                stage.update(status='incomplete_machine_check', machine_error=str(exc))
                write_json(state_path, state)
                raise
        return cached
    if stage['status'] == 'failed_truncation':
        raise OutputOverflow('该岗已在一次拆分后失败，不再投递')
    def split_once(truncated_rows=()):
        def pending_truncation(reason, failed_payload=None, failed_name=None):
            part=state.setdefault('chapters',{}).setdefault(material['chapter'],{})
            failed_payload=failed_payload or payload
            items=failed_payload.get('rows',[]) if review else failed_payload.get('plan_seeds',[])+failed_payload.get('previous_plans',[])
            if role=='A':
                existing={r.get('id',r.get('seed_id',name+':pending:'+str(i))):r
                          for i,r in enumerate(part.get('A_pending',[]))}
                for i,row in enumerate(items):
                    ident=row.get('seed_id',row.get('key',row.get('_id',name+':'+str(i))))
                    existing[ident]={'id':ident,'status':'待核','reason':'截断未完成：'+reason,'stage':failed_name or name,'row':row}
                # 已完整解出的行只进待核；不把末尾残行或响应正文写入检查点。
                if failed_payload is payload:
                    for i,row in enumerate(truncated_rows):
                        ident=(failed_name or name)+':truncated_row:'+str(i)
                        existing[ident]={'id':ident,'status':'待核','reason':'截断未完成：完整行待核',
                                         'stage':failed_name or name,'row':row,'from_truncated_response':True}
                part['A_pending']=list(existing.values())
        if split_depth >= 1:
            stage.update(status='failed_truncation', split_depth=split_depth)
            pending_truncation('拆半后仍截断或超界；不保存截断正文，不再重试')
            write_json(state_path, state)
            raise OutputOverflow('拆分后的子包仍截断或超界，该岗停止')
        try:
            if short_j2:
                if len(payload['items']) < 2:
                    raise OutputOverflow('J2短判断单条无法继续拆包')
                middle = len(payload['items']) // 2
                children = [(material, {**payload, 'items': items}) for items in (payload['items'][:middle], payload['items'][middle:])]
            elif role=='A' and payload.get('input_method')==A_METHOD52:
                children=split_seed_packet(material,payload,review)
            else:
                children = split_packet(material, payload, review)
        except OutputOverflow:
            stage.update(status='failed_truncation', split_depth=split_depth)
            pending_truncation('单条不能拆半；完整内容待核')
            write_json(state_path, state)
            raise
        stage.update(status='splitting', split_depth=split_depth, split_count=1)
        write_json(state_path, state)
        values=[];failures=[]
        for n,(child_material,child_payload) in enumerate(children):
            try:values.append(run_stage(budget,state,state_path,role,child_material,child_payload,review,checker,suffix+'.split'+str(n),split_depth+1))
            except (OutputOverflow,RoleLimit,TotalLimit,NetworkPause) as exc:
                if role!='A':
                    stage.update(status='failed_truncation',split_depth=split_depth)
                    write_json(state_path,state)
                    raise
                failures.append(str(exc));pending_truncation('拆半失败或额度不足：'+str(exc),child_payload,name+'.split'+str(n))
                write_json(state_path,state)
                if isinstance(exc,(TotalLimit,NetworkPause)):
                    pending_truncation('整窗或网络停止，完整行待核')
                    for _,remaining in children[n+1:]:pending_truncation('前包停止，未提交',remaining)
                    stage.update(status='failed_truncation',split_errors=failures)
                    write_json(state_path,state)
                    raise
        if not values:
            pending_truncation('拆半没有完整结果，整包待核')
            stage.update(status='failed_truncation',split_errors=failures);write_json(state_path,state)
            raise OutputOverflow('拆半无可保存完整结果；条目已进待核')
        combined = ({'verdicts': [v for value in values for v in value['verdicts']], '_normalized57': True}
                    if short_j2 else merge_values(role, values, review))
        write_json(cache, {'payload': combined})
        stage.update(status='partial_truncation' if failures else 'complete',sha256=digest(cache),split_errors=failures)
        write_json(state_path, state)
        return combined
    if stage['status'] == 'splitting':
        return split_once()
    while stage.get('machine_failures', 0) < 2 or stage.get('request_index'):
        raw = None
        prior_index = stage.get('request_index')
        if prior_index:
            prior = next((r for r in budget.calls if r['index'] == prior_index), None)
            if prior and (prior.get('stage_id') != name or prior['role'] != role or
                          prior['chapter'] != material['chapter'] or prior['review'] != review or
                          prior.get('gateway_job_id') != budget.config['gateway_job_id']):
                raise Halt('请求归属不符，禁止使用其他岗位响应')
            if prior and prior['state'] == 'received':
                raw = read_json(prior['response'])
                stage.pop('request_index', None)
            elif prior and prior['state'] == 'inflight':
                raise NetworkPause('在途响应未结算，不重复请求')
            elif prior and prior['state'] == 'network_failed':
                # 断线续跑使用新计数；没有清掉旧请求的未知预留。
                stage['network_resumes'] = stage.get('network_resumes', 0) + 1
                stage.pop('request_index', None)
            elif prior is None:
                stage.pop('request_index', None)
                stage['attempts'] = max(0, stage['attempts'] - 1)
        if raw is None:
            if stage.get('machine_failures', 0) >= 2:
                raise ValueError('机检失败已用一次重试')
            stage['attempts'] += 1
            write_json(state_path, state)
            repair = stage.get('machine_error')
            previous_answer = stage.get('machine_answer')
            answer_message = ([{'role': 'assistant', 'content': previous_answer}]
                              if repair and review and not short_j2 and isinstance(previous_answer, str) else [])
            feedback = repair_message(repair) if repair else None
            if short_j2 and feedback and len(feedback['content'].encode()) > J2_SHORT_REPAIR_MAX_BYTES:
                feedback = {'role': 'user', 'content': '短判断机检未过。逐项核对全部编号、布尔收拒与单项理由，只交裁定数组；完整错误已在本地记录。'}
            if role == 'A' and not review and 'group_subjects' in payload and feedback and len(feedback['content'].encode()) > 2048:
                feedback = {'role': 'user', 'content': '本组计划机检未过。新计划只选本包种子编号，不另写主体、来源或证据；旧计划只用本包已有键；逐项核目标、状态与兑现引用。完整错误已在本地记录。'}
            current_messages = base + answer_message + ([feedback] if feedback else [])
            def dispatched(index):
                stage['request_index'] = index
                write_json(state_path, state)
            pool_reason = ('truncation_split' if split_depth else 'machine_retry' if repair
                           else 'network_resume' if stage.get('network_resumes') else None)
            if short_j2:
                j2_pre_dispatch(payload, material)
            raw = budget.send(role, material['chapter'], current_messages, review=review,
                              stage_id=name, on_dispatch=dispatched, pool_reason=pool_reason)
            stage.pop('request_index', None)
        try:
            decoded = parse_response(raw)
            checked = checker(decoded, material, payload) if checker else decoded
            changes = checked.get('_normalization_log', [])
            pending = checked.get('_normalization_pending_rows', [])
            if changes:
                stage.setdefault('normalization_log', []).extend(changes)
            if pending:
                stage['normalization_pending'] = pending
                part = state.get('chapters', {}).get(material['chapter'])
                if part is not None:
                    part.setdefault(role+'_pending', []).extend(dict(r, stage=name) for r in pending)
            if changes or pending:
                write_json(state_path, state)
            if role == 'A' and not review and budget.config.get('A_output_calibration'):
                row_limit = len(payload.get('plan_seeds', [])) + len(payload.get('previous_plans', []))
                if len(checked.get('rows', [])) > row_limit:
                    raise ValueError('A返回条数超过本包种子与旧计划schema条数上限')
            if role == 'A' and not review and not checked.get('rows'):
                raise ValueError('计划候选为空，A阶段未完成；只能补有原文依据的计划')
            write_json(cache, {'payload': checked})
            stage.update(status='complete', sha256=digest(cache))
            write_json(state_path, state)
            return checked
        except J2RowOverflow as exc:
            if role != 'J2' or review:
                raise
            # 已收到完整JSON：拆的是返回条目，不再缩原文后花共享池重生成。
            try:
                parts = split_j2_rows(decoded)
                values = [(checker(part, material, payload) if checker else hydrate_j2(part, material))
                          for part in parts]
            except (ValueError, KeyError, TypeError) as split_error:
                stage.update(status='incomplete_machine_check', machine_error=str(split_error),
                             local_row_split_failed=True, local_row_split_extra_requests=0)
                write_json(state_path, state)
                raise
            child_records = []
            for n, (part, value) in enumerate(zip(parts, values)):
                child_cache = cache.with_name(cache.stem + '.rows' + str(n) + '.json')
                write_json(child_cache, {'payload': value})
                child_records.append({'path': str(child_cache), 'sha256': digest(child_cache),
                                      'row_count': sum(len(part[k]) for k in part),
                                      'compact_bytes': len(json.dumps(part, ensure_ascii=False, separators=(',', ':')).encode())})
            combined = merge_values(role, values)
            write_json(cache, {'payload': combined})
            stage.update(status='complete', sha256=digest(cache), local_row_split=child_records,
                         local_row_split_reason=str(exc), local_row_split_extra_requests=0)
            write_json(state_path, state)
            return combined
        except (TruncatedOutput, OutputOverflow) as exc:
            # 不把截断正文交保存校验，不复发同一大包，也不占普通机检重试次数。
            stage['truncation_error'] = str(exc)
            stage['truncated_responses'] = stage.get('truncated_responses', 0) + 1
            write_json(state_path, state)
            return split_once(complete_truncated_rows(raw, review) if role == 'A' else ())
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
            if len(error.encode()) > REPAIR_MAX_BYTES - 128:
                error = (repair_message(error)['content']
                         if review and role == 'B' and ('speaker_candidate_membership' in error
                                                       or 'review_protocol_conflict' in error)
                         else '多项字段或证据未通过机检；重新核对全部字段和原文指针。')
            stage['machine_error'] = error
            if review:
                previous_answer = raw.get('choices', [{}])[0].get('message', {}).get('content')
                if isinstance(previous_answer, str):
                    stage['machine_answer'] = previous_answer
            stage['machine_failures'] = stage.get('machine_failures', 0) + 1
            stage['machine_retries'] = min(1, stage['machine_failures'])
            write_json(state_path, state)
            if stage['machine_failures'] >= 2:
                stage['status'] = 'incomplete_machine_check'
                write_json(state_path, state)
                raise
    raise ValueError('机检步骤未完成')


def run_packets(budget, state, state_path, role, material, payload, review=False, checker=None):
    maximum = OUTPUT_POLICY['review' if review else role]['max_tokens']
    packets = (plan_packets52(material, payload, review) if role == 'A' and payload.get('input_method') == A_METHOD52 else a_local_packets(material, payload, budget.config['per_stage_reservation']['A:' + material['chapter'] + (':review' if review else ':generate')], review)
               if role == 'A' and payload.get('input_method') == A_LOCAL_METHOD else a_grouped_packets(material, payload, budget.config['per_stage_reservation']['A:' + material['chapter'] + ':generate'])
               if role == 'A' and not review and 'per_stage_reservation' in budget.config
               else bounded_packets(role, material, payload, maximum, review))
    values = [run_stage(budget, state, state_path, role, part, data, review, checker,
                        '.pack' + str(n)) for n, (part, data) in enumerate(packets)]
    return merge_values(role, values, review)


def run_j2_short(budget, state, state_path, material, facts):
    candidate, provenance = j2_program_candidates(material, facts)
    candidate = j2_enrich_candidates(material, candidate, facts)
    prepared, blocked = j2_prepare_packet(material, flatten('J2', candidate), facts=facts, itemwise=True)
    audits = list(blocked)
    part = state.get('chapters', {}).get(material['chapter'])
    reviewed = {f: [] for f in candidate}
    awaiting = {}
    failures = []
    def save_partial():
        if part is None: return
        confirmed, pending = j2_partition_saved(reviewed)
        confirmed_ids = {r['_id'] for r in flatten('J2', confirmed)}
        pending_map = {r['id']: r for r in pending}
        pending_map.update({k:v for k,v in awaiting.items() if k not in confirmed_ids and k not in pending_map})
        pending = list(pending_map.values())
        confirmed,pending,rejected=j2_save_partition(confirmed,pending,audits)
        part.update(J2=confirmed, J2_pending=pending, J2_rejected=rejected, J2_status='partial', J2_failures=list(failures),
                    J2_counts={'confirmed':sum(map(len,confirmed.values())), 'pending':len(pending), 'rejected':len(rejected)})
        write_json(state_path,state)
    def wait_row(item, reason, review, n, failure_type=None):
        row=dict(item['candidate'],confirmation_status='待核',confirmation_reason=reason)
        if row.get('speaker') is not None:
            row['unverified_speaker']=row['speaker'];row['speaker']=None
        awaiting[item['id']]={'section':item['id'].split(':')[0], 'id':item['id'], 'status':'待核',
                             'reason':reason, 'row':row, 'packet':n, 'phase':'review' if review else 'generate',
                             'failure_type':failure_type}
    if not prepared['items']:
        failures.append({'packet':None,'phase':'prepare','failure_type':'NoCandidates',
                         'reason':'没有可处理候选，不能冒称完成','ids':[]})
        save_partial()
        return {f:[] for f in candidate},audits
    for review in (False, True):
        maximum=OUTPUT_POLICY['review' if review else 'J2']['max_tokens']
        bound=budget.config['per_stage_reservation']['J2:'+material['chapter']+(':review' if review else ':generate')]
        packets=j2_decision_packets(material,prepared,maximum,bound,budget.config,review)
        approved_all={f:[] for f in candidate}
        for n,(child,packet) in enumerate(packets):
            try:
                value=run_stage(budget,state,state_path,'J2',child,packet,review,
                                lambda value,m,data:j2_short_decisions(value,data),'.pack'+str(n))
                approved,rejected=j2_apply_short(candidate,value,packet,material,normalized=True)
            except (RoleLimit,ValueError,KeyError,TypeError,NetworkPause,TotalLimit) as exc:
                failure={'packet':n,'phase':'review' if review else 'generate','failure_type':type(exc).__name__,'reason':str(exc),
                         'ids':[item['id'] for item in packet['items']]}
                failures.append(failure)
                for item in packet['items']:wait_row(item,str(exc),review,n,type(exc).__name__)
                save_partial()
                if isinstance(exc,(NetworkPause,TotalLimit)):raise
                continue
            audits.extend(rejected)
            for item in packet['items']:awaiting.pop(item['id'],None)
            for field in approved_all:
                approved_all[field].extend(approved[field])
                if review:reviewed[field].extend(approved[field])
                else:
                    for row in approved[field]:wait_row({'id':row['_id'],'candidate':row},'生成轮已判，仍待复核',False,n)
            save_partial()
        candidate=approved_all
        prepared,new_blocked=j2_prepare_packet(material,flatten('J2',candidate),facts=facts,
                                               chapter_speakers=prepared['chapter_speakers'],itemwise=True)
        audits.extend(new_blocked)
        save_partial()
    write_json(budget.output/'stages'/('J2_'+material['chapter']+'_program_candidates.json'),{'provenance':provenance})
    write_json(budget.output/'stages'/('J2_'+material['chapter']+'_rejections.json'),{'rejected':audits})
    return candidate,audits


def check_review_packet(role, candidate, obj, material, packet, facts, previous):
    checked, pending, logs = normalize_review57(role, obj, packet['rows'], material, packet=packet)
    wanted = {row['_id'] for row in packet['rows']}
    fields = ('rows',) if role in ('A', 'B') else tuple(candidate)
    subset = {field: [row for row in candidate[field] if row['_id'] in wanted] for field in fields}
    approved, removed = review_apply57(role, subset, checked, material, facts, previous)
    bad = {r['id'] for r in pending}
    pending.extend(r for r in removed if r.get('status') == '待核' and r['id'] not in bad)
    if role == 'A':
        for row in approved['rows']:
            try:
                check_local_plans({'rows': [row]}, packet, previous)
                check_plan_seed_scope({'rows': [row]}, packet.get('plan_seeds', []), previous)
            except (ValueError, KeyError, TypeError) as exc:
                pending.append({'id': row['_id'], 'status': '待核', 'reason': str(exc), 'row': row})
    bad = {r['id'] for r in pending}
    checked['verdicts'] = [v for v in checked['verdicts'] if v['id'] not in bad]
    checked['patches'] = [p for p in checked['patches'] if p['id'] not in bad]
    checked.update(_normalization_pending_rows=pending, _normalization_log=logs)
    return checked


def execute(input_package, book_id, chapters, output_dir, budget_file):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = read_json(budget_file)
    if config.get('book_id') != book_id or config.get('chapters') != chapters:
        raise Halt('预算与书号或章范围不同')
    materials = read_sources(input_package, book_id, chapters)
    if config.get('mode') == 'structure':
        report = {'book_id': book_id, 'chapters': chapters, 'model_calls': 0,
                  'sources': [{'member': m['source_member'], 'sha256': m['source_sha256'],
                               'paragraph_count': len(m['paragraphs'])} for m in materials],
                  'pipeline_steps_run': False, 'gold_read': False}
        write_json(output / 'structure_check.json', report)
        return report
    budget = Budget(budget_file, output, input_package, tuple(dict.fromkeys((*CODE_FILES, *PROMPT_FILES, *CONFIG_FILES))))
    state_path = output / 'checkpoint.json'
    state = read_json(state_path) if state_path.exists() else {'identity': budget.identity, 'stages': {}, 'chapters': {}, 'started_at': budget.calls[0]['started_at'] if budget.calls else None}
    if state['identity'] != budget.identity:
        raise Halt('检查点不属于同一冻结运行')
    clean_checkpoint(state, budget.calls, config['gateway_job_id'])
    write_json(state_path, state)
    status = {}
    try:
        budget.guard()
        all_facts, previous_plans, previous_people = [], [], []
        for material in materials:
            chapter = material['chapter']
            part = state['chapters'].setdefault(chapter, {})
            paragraphs = [[p['paragraph_id'], p['text']] for p in material['paragraphs']]
            for role in ('B', 'J2', 'A', 'C'):
                role_id = role + ':' + chapter
                if role in ('J2', 'A') and part.get('B_status') != 'complete':
                    status[role_id] = 'blocked_upstream'
                    part[role + '_status'] = 'blocked_upstream'
                    part[role + '_blocked_reason'] = '本章B尚未保存通过'
                    write_json(state_path, state)
                    continue
                if role == 'A' and any(state['chapters'][m['chapter']].get('A_status') != 'complete'
                                       for m in materials if m['chapter'] < chapter):
                    part['A_missing_history']=[m['chapter'] for m in materials if m['chapter']<chapter and state['chapters'][m['chapter']].get('A_status')!='complete']
                if role == 'C':
                    part['C'] = validate('C', annotate(material, part.get('J2', {}), part.get('facts', []),
                        any(state['chapters'][m['chapter']].get('A_memory', {}).get('open_at_end') for m in materials if m['chapter'] < chapter),
                        j2_complete=part.get('J2_status')=='complete'), material)
                    part['C_mode'] = 'program_bypass0'
                    part['C_bypass_receipt'] = part['C']['bypass0_receipt']
                    status[role_id] = '完成'
                    write_json(state_path, state)
                    continue
                payload = {'paragraphs': pointer_payload(material)}
                seeds = []
                if role == 'A':
                    prior_refs = {r.get(k) for r in previous_plans for k in ('source', 'fulfilled', 'condition_ref')}
                    relevant_facts = part.get('facts', []) + [f for f in all_facts if f['local_key'] in prior_refs]
                    plan_context = plan_candidates(material, part.get('facts', []), part.get('J2', {}),
                        any(state['chapters'][m['chapter']].get('A_memory', {}).get('open_at_end') for m in materials if m['chapter'] < chapter))
                    seeds = plan_context['seeds']
                    part['A_seed_candidates']=seeds
                    part['A_pending'] = [r for r in part.get('A_pending', []) if r.get('stage')] + plan_context['pending']
                    part['A_memory'] = plan_context['memory']
                    payload['input_method'] = A_METHOD52
                    payload.update(fact_fields=['key', 'subject', 'text', 'paragraph_ids'], facts=fact_map(relevant_facts),
                                   previous_plans=carry_plans(material, plan_summary(previous_plans),plan_context['memory']['paragraph_ids']), plan_seeds=seeds)
                if role == 'J2':
                    payload.update(previous_people=[{k: r.get(k) for k in ('entity', 'aspect', 'value', 'layer')} for r in previous_people])
                facts = all_facts + part.get('facts', [])
                candidate = None
                try:
                    if role == 'J2':
                        approved, rejected = run_j2_short(budget, state, state_path, material, part.get('facts', []))
                        confirmed, pending = j2_partition_saved(approved)
                        pending_by_id={p['id']:p for p in part.get('J2_pending',[])}
                        pending_by_id.update({p['id']:p for p in pending})
                        pending=list(pending_by_id.values())
                        confirmed,pending,rejected=j2_save_partition(confirmed,pending,rejected)
                        incomplete=bool(part.get('J2_failures'))
                        part.update(J2=confirmed, J2_pending=pending, J2_rejected=rejected, J2_status='partial' if incomplete else 'complete',
                                    J2_counts={'confirmed': sum(map(len, confirmed.values())), 'pending': len(pending), 'rejected': len(rejected)})
                        status[role_id] = '未完成（部分条目待核）' if incomplete else '完成'
                        part['entity_resolution'] = entity_bindings(material, part.get('facts', []), confirmed)
                        write_json(state_path, state)
                        continue
                    def generation_check(obj, part_material, packet):
                        checked, pending, logs = generation_normalize57(role, obj, part_material, packet, facts, previous_plans)
                        checked.update(_normalization_pending_rows=pending, _normalization_log=logs)
                        return checked
                    candidate = run_packets(budget, state, state_path, role, material, payload,
                        checker=generation_check)
                    candidate = validate(role, candidate, material, facts, previous_plans)
                    if role == 'A':
                        check_plan_seed_scope(candidate, seeds, previous_plans)
                    reference_keys = {r.get(k) for r in candidate.get('rows', []) for k in ('source', 'fulfilled', 'condition_ref')} | {key for r in candidate.get('rows', []) for key in r.get('basis', [])}
                    review_payload = {'paragraphs': pointer_payload(material), 'rows': flatten(role, candidate), 'role': role,
                                      'input_bound': config['roles'][role]['review_rows_max_bytes'],
                                      'fact_fields': ['key', 'subject', 'text', 'paragraph_ids'],
                                      'facts': fact_map([f for f in facts if f['local_key'] in reference_keys]) if role == 'A' else []}
                    if role == 'B':
                        review_payload['speaker_candidates'] = speaker_candidates(material, candidate['rows'])
                    elif role == 'A':
                        review_payload['plan_seeds'] = seeds
                        review_payload['input_method'] = A_METHOD52
                        review_payload['previous_plans'] = payload['previous_plans']
                    review_result = run_packets(budget, state, state_path, role, material, review_payload,
                        review=True, checker=lambda obj, part_material, packet:
                        check_review_packet(role, candidate, obj, part_material, packet, facts, previous_plans))
                    reviewed_candidate=candidate
                    if role=='A' and any(s.get('status')=='partial_truncation' for k,s in state['stages'].items() if k.startswith('A:'+chapter+':review')):
                        ids={v['id'] for v in review_result['verdicts']}
                        reviewed_candidate={**candidate,'rows':[r for r in candidate['rows'] if r['_id'] in ids]}
                    approved, rejected = review_apply57(role, reviewed_candidate, review_result, material, facts, previous_plans)
                    if role == 'A':
                        check_plan_seed_scope(approved, seeds, previous_plans)
                    part[role] = approved
                    part[role + '_rejected'] = [r for r in rejected if r.get('status') != '待核']
                    part.setdefault(role+'_pending', []).extend(dict(r, stage=role_id) for r in rejected if r.get('status') == '待核')
                    if role == 'B':
                        part['facts'] = facts_output(approved, material)
                        part['entity_resolution'] = entity_bindings(material, part['facts'], part.get('J2', {}))
                    elif role == 'A':
                        part['plans'] = plans_output(approved, material, previous_plans)
                        if not part['plans']:
                            raise ValueError('保存计划为空，A阶段未完成')
                    incomplete=any(r.get('stage') for r in part.get(role+'_pending',[]))
                    part[role + '_status'] = 'partial' if incomplete else 'complete'
                    status[role_id] = '未完成（部分条目待核）' if incomplete else '完成'
                    write_json(state_path, state)
                except RoleLimit as exc:
                    if role == 'A':
                        # 106第1/12条：复核被拒仍保留已完整生成的候选，不能丢整章。
                        rows = candidate.get('rows', []) if candidate else seeds + payload.get('previous_plans', [])
                        existing = {r.get('id',r.get('seed_id',role_id+':pending:'+str(i))):r
                                    for i,r in enumerate(part.get('A_pending', []))}
                        for i,row in enumerate(rows):
                            ident = row.get('seed_id',row.get('_id',row.get('key'))) or role_id+':unreviewed:'+str(i)
                            existing[ident] = {'id':ident,'status':'待核','reason':'额度不足，完整候选未复核',
                                               'stage':role_id,'row':row}
                        part['A_pending'] = list(existing.values())
                    status[role_id] = '未完成（预算或授权）'
                    part[role + '_status'] = ('partial' if (role == 'J2' and
                        any(part.get('J2_counts', {}).values())) or (role == 'A' and part.get('A_pending')) else 'failed')
                    part[role + '_limit'] = str(exc)
                    write_json(state_path, state)
                    continue
                except (ValueError, KeyError, TypeError) as exc:
                    status[role_id] = '未完成（机检）'
                    part[role + '_status'] = ('partial' if (role == 'J2' and
                        any(part.get('J2_counts', {}).values())) or (role == 'A' and part.get('A_pending')) else 'failed')
                    part[role + '_error'] = str(exc)
                    write_json(state_path, state)
                    continue
            all_facts.extend(part.get('facts', []))
            previous_plans.extend(part.get('plans', []))
            previous_people.extend(part.get('J2', {}).get('people', []))
        prediction = assemble(materials, state['chapters'])
        author = build_views(materials, state['chapters'])
        status['H6'] = author['status']
        write_json(output / 'prediction.json', prediction)
        write_json(output / 'author_store.json', author)
        complete = all(value in ('完成', 'complete') for value in status.values())
        empty_roles = [role + ':' + m['chapter'] for m in materials for role in ('B', 'A', 'J2')
                       if not (state['chapters'][m['chapter']].get('facts') if role == 'B'
                               else state['chapters'][m['chapter']].get('plans') if role == 'A'
                               else any(state['chapters'][m['chapter']].get('J2', {}).values()))]
        write_json(output / 'run_status.json', {'roles': status, 'complete': complete,
                    'identity': budget.identity, 'requests': budget.spent()[0], 'charged_tokens': budget.spent()[1],
                    'C_mode': 'program', 'C_formal': False,
                    'empty_views': [name for name, rows in author['views'].items() if not rows],
                    'empty_roles': empty_roles,
                    'eligible_for_blind': blind_admission(complete, status, budget.spent()[1], empty_roles)})
        budget.close('本次运行完成' if complete else '本次运行有未完成岗位，不进盲测')
        return {'complete': complete, 'roles': status}
    except (TotalLimit, Halt, OSError) as exc:
        write_json(state_path, state)
        write_json(output / 'run_status.json', {'roles': status, 'complete': False,
                    'error': str(exc), 'error_type': type(exc).__name__, 'eligible_for_blind': False,
                    'identity': budget.identity, 'requests': budget.spent()[0], 'charged_tokens': budget.spent()[1]})
        budget.close('停止新请求：' + str(exc))
        raise


def main():
    parser = argparse.ArgumentParser(description='从正文运行有限预算小说管线')
    parser.add_argument('input_package')
    parser.add_argument('book_id')
    parser.add_argument('chapter_range')
    parser.add_argument('output_dir')
    parser.add_argument('budget_file')
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    import shlex
    (out / 'run_command.txt').write_text('执行身份：Codex\n' + shlex.join(sys.argv) + '\n')
    class Tee:
        def __init__(self, terminal, log): self.terminal, self.log = terminal, log
        def write(self, value): self.terminal.write(value); self.log.write(value)
        def flush(self): self.terminal.flush(); self.log.flush()
    from contextlib import redirect_stdout, redirect_stderr
    with (out / 'run.log').open('a') as log:
        log.write('执行身份：Codex\n')
        with redirect_stdout(Tee(sys.stdout, log)), redirect_stderr(Tee(sys.stderr, log)):
            try:
                result = execute(args.input_package, args.book_id, chapter_range(args.chapter_range), args.output_dir, args.budget_file)
                print(json.dumps({'execution_identity': 'Codex', **result}, ensure_ascii=False))
                return 2 if result.get('complete') is False else 0
            except Exception as exc:
                print(json.dumps({'execution_identity': 'Codex', 'error_type': type(exc).__name__, 'error': str(exc)}, ensure_ascii=False))
                raise



if __name__ == '__main__':
    raise SystemExit(main())
